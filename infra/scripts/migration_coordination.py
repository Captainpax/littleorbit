"""Cross-host exclusion guards for the one-time Little Orbit migration."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from contextlib import AbstractContextManager
import ctypes
from ctypes import wintypes
import os
from queue import Empty, Queue
import secrets
import subprocess
from threading import Thread
from types import TracebackType
from typing import Any, Literal


WINDOWS_MUTEX_NAME = r"Global\LittleOrbitOperationsRunner"
REMOTE_LOCK_HELPER = (
    "/mnt/cache/little-orbit-deploy/repo/infra/scripts/unraid-operation-lock.sh"
)


def _read_line(process: subprocess.Popen[str], timeout: int) -> str:
    output = process.stdout
    if output is None:
        raise RuntimeError("remote operations-lock output was unavailable")
    result: Queue[str | BaseException] = Queue(maxsize=1)

    def read() -> None:
        try:
            result.put(output.readline().strip())
        except BaseException as error:
            result.put(error)

    Thread(target=read, daemon=True).start()
    try:
        value = result.get(timeout=timeout)
    except Empty as error:
        raise RuntimeError("remote operations lock handshake timed out") from error
    if isinstance(value, BaseException):
        raise RuntimeError("remote operations lock handshake failed") from value
    return value


class LocalOperationsMutex(AbstractContextManager[None]):
    """Hold the same Windows mutex used by the legacy operations runner."""

    def __init__(self) -> None:
        self._handle: int | None = None

    def __enter__(self) -> None:
        if os.name != "nt":
            raise RuntimeError("direct migration must acquire the Windows operations mutex")
        kernel32: Any = ctypes.windll.kernel32
        kernel32.CreateMutexW.argtypes = [
            ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR,
        ]
        kernel32.CreateMutexW.restype = wintypes.HANDLE
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.WaitForSingleObject.restype = wintypes.DWORD
        kernel32.ReleaseMutex.argtypes = [wintypes.HANDLE]
        kernel32.ReleaseMutex.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL
        handle = kernel32.CreateMutexW(None, False, WINDOWS_MUTEX_NAME)
        if not handle:
            raise OSError("could not create the migration operations mutex")
        result = int(kernel32.WaitForSingleObject(handle, 0))
        if result not in {0x00000000, 0x00000080}:
            kernel32.CloseHandle(handle)
            if result == 0x00000102:
                raise RuntimeError("a local Little Orbit operation is already running")
            raise OSError("could not acquire the migration operations mutex")
        self._handle = int(handle)
        return None

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        del exc_type, traceback
        if self._handle is None:
            return False
        kernel32: Any = ctypes.windll.kernel32
        released = bool(kernel32.ReleaseMutex(self._handle))
        closed = bool(kernel32.CloseHandle(self._handle))
        self._handle = None
        if not released or not closed:
            error = OSError("could not release the migration operations mutex")
            if exc_value is not None:
                exc_value.add_note(str(error))
            else:
                raise error
        return False


class RemoteOperationsLock(AbstractContextManager[None]):
    """Keep an SSH process holding Unraid's operations flock for the whole run."""

    def __init__(self, command: Sequence[str]) -> None:
        self._command = list(command)
        self._process: subprocess.Popen[str] | None = None

    def __enter__(self) -> None:
        process = subprocess.Popen(
            self._command,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            text=True,
            bufsize=1,
        )
        self._process = process
        try:
            marker = _read_line(process, 20)
        except RuntimeError:
            self._stop()
            raise
        if marker != "little-orbit-migration-locked":
            code = self._stop()
            raise RuntimeError(f"could not acquire the remote operations lock ({code})")
        return None

    def _stop(self) -> int:
        process = self._process
        self._process = None
        if process is None:
            return 0
        if process.stdin is not None:
            try:
                process.stdin.close()
            except OSError:
                pass
        try:
            return process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                return process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                return process.wait(timeout=10)

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        del exc_type, traceback
        code = self._stop()
        if code != 0:
            error = RuntimeError("remote operations lock ended unexpectedly")
            if exc_value is not None:
                exc_value.add_note(str(error))
            else:
                raise error
        return False

    def assert_held(self) -> None:
        """Require the SSH process to still hold its remote flock."""

        process = self._process
        if process is None or process.poll() is not None or process.stdin is None:
            raise RuntimeError("remote operations lock is no longer held")
        try:
            process.stdin.write("ping\n")
            process.stdin.flush()
            marker = _read_line(process, 20)
        except (OSError, RuntimeError) as error:
            self._stop()
            raise RuntimeError("remote operations lock is no longer held") from error
        if marker != "little-orbit-migration-alive":
            self._stop()
            raise RuntimeError("remote operations lock returned an invalid heartbeat")


def remote_lock_script(token: str) -> str:
    """Return the content-free command that holds Unraid's shared flock."""

    if len(token) != 64 or any(value not in "0123456789abcdef" for value in token):
        raise ValueError("migration lock token is invalid")
    return " ".join((
        "exec", "bash", REMOTE_LOCK_HELPER, "hold-migration", token,
    ))


def assert_local_schedules_disabled(run: Callable[..., str]) -> None:
    """Reject enabled Windows tasks that can start the legacy runner."""

    script = (
        "$active=@(Get-ScheduledTask -ErrorAction Stop | Where-Object {"
        "$_.State -ne 'Disabled' -and "
        "@($_.Actions | Where-Object {"
        "$_.Execute -match 'operations-runner\\.ps1' -or "
        "$_.Arguments -match 'operations-runner\\.ps1'}).Count -gt 0"
        "}); if($active.Count -ne 0){exit 75}"
    )
    run([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script,
    ])


def assert_remote_schedules_disabled(
    run: Callable[..., str], ssh: Sequence[str], shell: Callable[[str], str],
) -> None:
    """Reject active Little Orbit User Scripts entries and stale cron lines."""

    script = r'''
schedule=/boot/config/plugins/user.scripts/schedule.json
runtime_schedule=/tmp/user.scripts/schedule.json
cron=/boot/config/plugins/user.scripts/customSchedule.cron
check_schedule() {
  file=$1
  test ! -f "$file" || jq -e '[to_entries[] | select(
      ((.key | contains("/little-orbit-")) or
       ((.value.script // "") | contains("/little-orbit-"))) and
      ((.value.frequency // "") != "disabled")
    )] | length == 0' "$file" >/dev/null
}
check_cron() {
  file=$1
  test ! -f "$file" ||
    ! grep -E '^[[:space:]]*[^#[:space:]].*/scripts/little-orbit-' "$file" >/dev/null
}
check_schedule "$schedule"
check_schedule "$runtime_schedule"
check_cron "$cron"
for live_cron in /var/spool/cron/crontabs/root /var/spool/cron/root; do
  check_cron "$live_cron"
done
'''.strip()
    run([*ssh, shell(script)])


class MigrationExclusion(AbstractContextManager["MigrationExclusion"]):
    """Acquire both host locks and prove every scheduler is inactive."""

    def __init__(
        self,
        *,
        run: Callable[..., str],
        ssh: Sequence[str],
        shell: Callable[[str], str],
    ) -> None:
        self._run = run
        self._ssh = list(ssh)
        self._shell = shell
        self._token = secrets.token_hex(32)
        self._local = LocalOperationsMutex()
        self._remote = RemoteOperationsLock([
            *self._ssh, self._shell(remote_lock_script(self._token)),
        ])

    @property
    def token(self) -> str:
        """Return the content-free capability accepted only by this lock holder."""

        return self._token

    def __enter__(self) -> MigrationExclusion:
        self._local.__enter__()
        try:
            assert_local_schedules_disabled(self._run)
            self._remote.__enter__()
            assert_remote_schedules_disabled(
                self._run, self._ssh, self._shell,
            )
        except BaseException as error:
            self._remote.__exit__(type(error), error, error.__traceback__)
            self._local.__exit__(type(error), error, error.__traceback__)
            raise
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: TracebackType | None,
    ) -> Literal[False]:
        self._remote.__exit__(exc_type, exc_value, traceback)
        self._local.__exit__(exc_type, exc_value, traceback)
        return False

    def assert_held(self) -> None:
        """Fail before commit if the remote flock holder exited early."""

        self._remote.assert_held()
