"""Archive-free subprocess transports used by the direct migration runner."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import re
import shutil
import subprocess
import tarfile

import migration_inventory as inventory


ENV_ASSIGNMENT = re.compile(rb"^[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)[ \t]*=")
ENV_DEFINITION = re.compile(
    rb"^[ \t]*(?:export[ \t]+)?([A-Za-z_][A-Za-z0-9_]*)"
    rb"(?:[ \t]*=|[ \t]*(?:\r?\n)?$)"
)


def _environment_overrides(overrides: bytes) -> tuple[list[bytes], set[bytes]]:
    replacement_lines = [line for line in overrides.splitlines() if line]
    replacement_names: set[bytes] = set()
    for line in replacement_lines:
        match = ENV_ASSIGNMENT.match(line)
        if match is None:
            raise ValueError("runtime environment override is malformed")
        name = match.group(1)
        if name in replacement_names:
            raise ValueError("runtime environment override is duplicated")
        replacement_names.add(name)
    if not replacement_names:
        raise ValueError("runtime environment overrides are empty")
    return replacement_lines, replacement_names


def _remove_environment_overrides(source: bytes, names: set[bytes]) -> bytes:
    retained: list[bytes] = []
    source_counts = {name: 0 for name in names}
    for line in source.splitlines(keepends=True):
        match = ENV_DEFINITION.match(line)
        if match is not None and match.group(1) in source_counts:
            source_counts[match.group(1)] += 1
            continue
        retained.append(line)
    if any(count > 1 for count in source_counts.values()):
        raise ValueError("source runtime environment has duplicate fixed definitions")
    return b"".join(retained)


def _assert_unique_environment(result: bytes, names: set[bytes]) -> None:
    counts = {name: 0 for name in names}
    for line in result.splitlines():
        match = ENV_ASSIGNMENT.match(line)
        if match is not None and match.group(1) in counts:
            counts[match.group(1)] += 1
    if any(count != 1 for count in counts.values()):
        raise ValueError("rebuilt runtime environment is ambiguous")


def rebuild_environment(source: bytes, overrides: bytes) -> bytes:
    """Replace fixed environment assignments once without retaining a temp file."""

    replacement_lines, replacement_names = _environment_overrides(overrides)
    rebuilt = _remove_environment_overrides(source, replacement_names)
    if rebuilt and not rebuilt.endswith((b"\n", b"\r")):
        rebuilt += b"\n"
    rebuilt += b"\n".join(replacement_lines) + b"\n"
    _assert_unique_environment(rebuilt, replacement_names)
    return rebuilt


def remove_tree(path: Path) -> None:
    """Remove one validated dedicated tree, including sealed read-only files."""

    def make_writable(function: Callable[[str], object], name: str, _error: object) -> None:
        Path(name).chmod(0o700)
        function(name)

    shutil.rmtree(path, onerror=make_writable)


def run_checked(
    command: Sequence[str], *, capture: bool = False,
    env: Mapping[str, str] | None = None,
) -> str:
    """Run one command without printing its possibly sensitive arguments."""

    result = subprocess.run(
        command, check=True, text=True, encoding="utf-8", env=env,
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture and result.stdout else ""


def pipe_commands(
    source: Sequence[str], destination: Sequence[str], *,
    source_env: Mapping[str, str] | None = None,
    destination_env: Mapping[str, str] | None = None,
) -> None:
    """Pipe bytes between processes without retaining an archive."""

    with subprocess.Popen(source, stdout=subprocess.PIPE, env=source_env) as producer:
        if producer.stdout is None:
            raise RuntimeError("source pipe was not created")
        with subprocess.Popen(destination, stdin=producer.stdout, env=destination_env) as consumer:
            producer.stdout.close()
            consumer_code = consumer.wait()
        producer_code = producer.wait()
    if producer_code != 0 or consumer_code != 0:
        raise RuntimeError("direct migration stream failed")


def send_file(
    command: Sequence[str], source: Path | bytes, suffix: bytes = b"", *,
    rebuild_env: bool = False,
) -> None:
    """Write one file and a fixed suffix directly to a process stdin."""

    payload: bytes | None = None
    if rebuild_env:
        original = source if isinstance(source, bytes) else source.read_bytes()
        payload = rebuild_environment(original, suffix)
    elif isinstance(source, bytes):
        payload = source + suffix
    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        if process.stdin is None:
            raise RuntimeError("destination pipe was not created")
        if payload is None:
            assert isinstance(source, Path)
            with source.open("rb") as input_file:
                shutil.copyfileobj(input_file, process.stdin)
            process.stdin.write(suffix)
        else:
            process.stdin.write(payload)
        process.stdin.close()
        if process.wait() != 0:
            raise RuntimeError("direct file stream failed")


def send_tar(command: Sequence[str], root: Path) -> None:
    """Write a directory as a tar stream directly to a process stdin."""

    with subprocess.Popen(command, stdin=subprocess.PIPE) as consumer:
        if consumer.stdin is None:
            raise RuntimeError("tar destination pipe was not created")
        with tarfile.open(fileobj=consumer.stdin, mode="w|") as archive:
            for path in sorted(root.rglob("*")):
                archive.add(path, arcname=path.relative_to(root), recursive=False)
        consumer.stdin.close()
        if consumer.wait() != 0:
            raise RuntimeError("tar stream failed")


def receive_release_tar(command: Sequence[str], root: Path) -> None:
    """Safely receive a release tar stream without persisting the archive."""

    with subprocess.Popen(command, stdout=subprocess.PIPE) as producer:
        if producer.stdout is None:
            raise RuntimeError("tar source pipe was not created")
        try:
            inventory.extract_release_archive(producer.stdout, root)
        except BaseException:
            producer.terminate()
            producer.wait()
            raise
        if producer.wait() != 0:
            raise RuntimeError("tar stream failed")
