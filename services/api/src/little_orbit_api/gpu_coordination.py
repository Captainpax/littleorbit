"""Cross-process ownership of the one GPU shared by local services."""

import logging
import os
import stat
import sys
from pathlib import Path
from types import TracebackType
from typing import BinaryIO

_QUARANTINED_HANDLES: list[BinaryIO] = []
LOGGER = logging.getLogger(__name__)


class GpuFileLock:
    """Hold one advisory lock without ever replacing its stable inode."""

    def __init__(self, handle: BinaryIO) -> None:
        self._handle = handle
        self._released = False
        self._quarantined = False
        self._release_verification_pending = False

    def __enter__(self) -> "GpuFileLock":
        return self

    def __exit__(
        self,
        _exc_type: type[BaseException] | None,
        _exc: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.release()

    def release(self) -> None:
        """Release ownership while preserving the shared lock file."""

        if self._released or self._quarantined:
            return
        if self._release_verification_pending:
            self.quarantine()
            LOGGER.critical("GPU lock retained: verified cleanup did not finish")
            return
        _unlock(self._handle)
        self._handle.close()
        self._released = True

    def require_verified_release(self) -> None:
        """Arm retention before GPU work; exception replacement cannot bypass it."""

        if self._released or self._quarantined:
            raise RuntimeError("Cannot arm cleanup verification on an unavailable GPU lock")
        self._release_verification_pending = True

    def verify_release(self) -> None:
        """Disarm retention only after the caller proves fresh device cleanup."""

        if self._released or self._quarantined:
            raise RuntimeError("Cannot clear an unavailable GPU lock quarantine")
        self._release_verification_pending = False

    def quarantine(self) -> None:
        """Retain this exact locked inode until process exit after unsafe cleanup.

        No new file or false idle receipt is created. A process restart releases
        this descriptor, so the next owner must still pass a fresh host probe.
        """

        if self._released:
            raise RuntimeError("Cannot quarantine a released GPU lock")
        if not self._quarantined:
            _QUARANTINED_HANDLES.append(self._handle)
            self._quarantined = True


def try_acquire_gpu_lock(path: Path) -> GpuFileLock | None:
    """Return a non-blocking exclusive lock, or ``None`` when another service owns it."""

    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor = _open_stable_lock(path)
    handle = os.fdopen(descriptor, "r+b", buffering=0)
    try:
        _verify_stable_lock(path, handle)
    except Exception:
        handle.close()
        raise
    try:
        _lock_nonblocking(handle)
    except OSError:
        handle.close()
        return None
    try:
        _verify_stable_lock(path, handle)
    except Exception:
        handle.close()
        raise
    return GpuFileLock(handle)


def _open_stable_lock(path: Path) -> int:
    """Open an existing regular inode, creating it only when no entry exists."""

    no_follow = getattr(os, "O_NOFOLLOW", 0)
    try:
        return os.open(path, os.O_RDWR | no_follow)
    except FileNotFoundError:
        return os.open(path, os.O_RDWR | os.O_CREAT | os.O_EXCL | no_follow, 0o660)


def _verify_stable_lock(path: Path, handle: BinaryIO) -> None:
    """Reject links and path swaps before treating the descriptor as the shared lock."""

    descriptor_info = os.fstat(handle.fileno())
    path_info = path.lstat()
    if not stat.S_ISREG(descriptor_info.st_mode) or stat.S_ISLNK(path_info.st_mode):
        raise RuntimeError("GPU lock must be a regular file")
    if descriptor_info.st_nlink != 1:
        raise RuntimeError("GPU lock inode must have exactly one link")
    if (descriptor_info.st_dev, descriptor_info.st_ino) != (
        path_info.st_dev,
        path_info.st_ino,
    ):
        raise RuntimeError("GPU lock inode changed while it was being acquired")


def _lock_nonblocking(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        if os.fstat(handle.fileno()).st_size == 0:
            handle.write(b"\0")
            handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle: BinaryIO) -> None:
    if sys.platform == "win32":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
        return
    import fcntl

    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
