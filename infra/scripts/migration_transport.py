"""Archive-free subprocess transports used by the direct migration runner."""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from pathlib import Path
import shutil
import subprocess
import tarfile

import migration_inventory as inventory


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
        command, check=True, text=True, env=env,
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


def send_file(command: Sequence[str], source: Path, suffix: bytes = b"") -> None:
    """Write one file and a fixed suffix directly to a process stdin."""

    with subprocess.Popen(command, stdin=subprocess.PIPE) as process:
        if process.stdin is None:
            raise RuntimeError("destination pipe was not created")
        with source.open("rb") as input_file:
            shutil.copyfileobj(input_file, process.stdin)
        process.stdin.write(suffix)
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
