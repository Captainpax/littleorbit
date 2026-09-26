"""Content-free inventories for exact Little Orbit migration verification."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
import tarfile
from typing import Any, IO

BUFFER_SIZE = 1024 * 1024
DATABASE_INVENTORY_SQL = """
WITH table_counts AS (
    SELECT tablename,
           ((xpath(
               '/row/count/text()',
               query_to_xml(
                   format('SELECT count(*) AS count FROM %I.%I', schemaname, tablename),
                   false,
                   true,
                   ''
               )
           ))[1]::text)::bigint AS row_count
      FROM pg_tables
     WHERE schemaname = 'public'
), counts AS (
    SELECT COALESCE(
               jsonb_object_agg(tablename, row_count ORDER BY tablename),
               '{}'::jsonb
           ) AS value
      FROM table_counts
), heads AS (
    SELECT COALESCE(jsonb_agg(version_num ORDER BY version_num), '[]'::jsonb) AS value
      FROM alembic_version
)
SELECT jsonb_build_object('tables', counts.value, 'schema_heads', heads.value)
  FROM counts CROSS JOIN heads;
""".strip()
ACTIVE_AI_SQL = """
SELECT jsonb_build_object(
    'ai_runs_running', (SELECT count(*) FROM ai_runs WHERE status = 'running'),
    'admin_ai_jobs_running', (
        SELECT count(*) FROM admin_job_requests
         WHERE status = 'running'
           AND kind IN ('learn_quizzes', 'generate_quizzes', 'regenerate_quizzes')
    )
);
""".strip()


@dataclass(frozen=True)
class AttachmentInventory:
    """Aggregate attachment evidence that discloses no file paths."""

    file_count: int
    total_bytes: int
    aggregate_sha256: str


@dataclass(frozen=True)
class MigrationInventory:
    """All content-free state needed to prove an exact transfer."""

    database: dict[str, object]
    attachments: AttachmentInventory
    releases: dict[str, dict[str, object]]

    def serializable(self) -> dict[str, object]:
        """Return a stable JSON-ready representation."""

        return {
            "database": self.database,
            "attachments": asdict(self.attachments),
            "releases": self.releases,
        }


def _regular_files(root: Path) -> list[Path]:
    """Return sorted regular files while rejecting links and special entries."""

    values: list[Path] = []
    for path in sorted(root.rglob("*")):
        if path.is_symlink() or (not path.is_file() and not path.is_dir()):
            raise RuntimeError("inventory root contains a link or special entry")
        if path.is_file():
            values.append(path)
    return values


def _file_digest(path: Path) -> tuple[int, str]:
    """Return the byte count and streaming SHA-256 for one file."""

    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as source:
        while chunk := source.read(BUFFER_SIZE):
            digest.update(chunk)
            size += len(chunk)
    return size, digest.hexdigest()


def attachment_inventory(root: Path) -> AttachmentInventory:
    """Hash attachment paths and bytes but expose only one aggregate digest."""

    aggregate = hashlib.sha256()
    total_bytes = 0
    files = _regular_files(root)
    for path in files:
        relative = path.relative_to(root).as_posix().encode("utf-8")
        size, digest = _file_digest(path)
        aggregate.update(len(relative).to_bytes(8, "big"))
        aggregate.update(relative)
        aggregate.update(size.to_bytes(8, "big"))
        aggregate.update(bytes.fromhex(digest))
        total_bytes += size
    return AttachmentInventory(len(files), total_bytes, aggregate.hexdigest())


def release_inventory(root: Path) -> dict[str, dict[str, object]]:
    """Return public immutable release paths, sizes, and hashes."""

    values: dict[str, dict[str, object]] = {}
    for path in _regular_files(root):
        size, digest = _file_digest(path)
        values[path.relative_to(root).as_posix()] = {
            "bytes": size,
            "sha256": digest,
        }
    return values


def parse_database_inventory(raw: str) -> dict[str, object]:
    """Validate PostgreSQL's JSON inventory before comparing it."""

    parsed: Any = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("database inventory is not an object")
    tables = parsed.get("tables")
    heads = parsed.get("schema_heads")
    if not isinstance(tables, dict) or not all(
        isinstance(name, str) and isinstance(count, int) and count >= 0
        for name, count in tables.items()
    ):
        raise RuntimeError("database table counts are invalid")
    if not isinstance(heads, list) or not heads or not all(
        isinstance(head, str) and head for head in heads
    ):
        raise RuntimeError("database schema head is invalid")
    return {"tables": dict(sorted(tables.items())), "schema_heads": sorted(heads)}


def parse_active_ai(raw: str) -> dict[str, int]:
    """Validate content-free running/leased AI counts."""

    parsed: Any = json.loads(raw)
    expected = {"ai_runs_running", "admin_ai_jobs_running"}
    if not isinstance(parsed, dict) or set(parsed) != expected:
        raise RuntimeError("active AI inventory is invalid")
    if not all(isinstance(parsed[key], int) and parsed[key] >= 0 for key in expected):
        raise RuntimeError("active AI counts are invalid")
    return parsed


def parse_attachment_inventory(raw: str) -> AttachmentInventory:
    """Validate container-produced attachment aggregate evidence."""

    parsed: Any = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("attachment inventory is not an object")
    expected = {"file_count", "total_bytes", "aggregate_sha256"}
    if set(parsed) != expected:
        raise RuntimeError("attachment inventory has unexpected fields")
    digest = parsed["aggregate_sha256"]
    if not isinstance(digest, str) or len(digest) != 64:
        raise RuntimeError("attachment aggregate digest is invalid")
    try:
        bytes.fromhex(digest)
    except ValueError as error:
        raise RuntimeError("attachment aggregate digest is invalid") from error
    if not all(isinstance(parsed[key], int) and parsed[key] >= 0 for key in expected - {"aggregate_sha256"}):
        raise RuntimeError("attachment aggregate counts are invalid")
    return AttachmentInventory(**parsed)


def _safe_release_name(name: object) -> bool:
    if not isinstance(name, str) or not name:
        return False
    path = PurePosixPath(name)
    return not path.is_absolute() and ".." not in path.parts


def _valid_digest(value: object) -> bool:
    if not isinstance(value, str) or len(value) != 64:
        return False
    try:
        bytes.fromhex(value)
    except ValueError:
        return False
    return True


def _validate_release_item(name: object, details: object) -> None:
    """Validate one public release manifest entry."""

    if not _safe_release_name(name) or not isinstance(details, dict):
        raise RuntimeError("release inventory contains an unsafe path")
    if set(details) != {"bytes", "sha256"}:
        raise RuntimeError("release inventory has unexpected fields")
    if not isinstance(details["bytes"], int) or details["bytes"] < 0:
        raise RuntimeError("release byte count is invalid")
    if not _valid_digest(details["sha256"]):
        raise RuntimeError("release digest is invalid")


def parse_release_inventory(raw: str) -> dict[str, dict[str, object]]:
    """Validate container-produced immutable release evidence."""

    parsed: Any = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("release inventory is not an object")
    for name, details in parsed.items():
        _validate_release_item(name, details)
    return dict(sorted(parsed.items()))


def assert_matching(source: MigrationInventory, destination: MigrationInventory) -> None:
    """Fail closed unless every content-free inventory matches exactly."""

    if source != destination:
        raise RuntimeError("source and destination migration inventories differ")


def extract_release_archive(stream: IO[bytes], root: Path) -> None:
    """Extract regular release files from a stream without trusting tar paths."""

    with tarfile.open(fileobj=stream, mode="r|*") as archive:
        for member in archive:
            value = PurePosixPath(member.name)
            parts = tuple(part for part in value.parts if part != ".")
            if value.is_absolute() or ".." in parts:
                raise RuntimeError("release stream contains an unsafe path")
            if member.isdir():
                (root.joinpath(*parts)).mkdir(parents=True, exist_ok=True)
                continue
            if not member.isfile() or not parts:
                raise RuntimeError("release stream contains a non-regular entry")
            target = root.joinpath(*parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            source = archive.extractfile(member)
            if source is None:
                raise RuntimeError("release stream entry is unreadable")
            with target.open("xb") as output:
                while chunk := source.read(BUFFER_SIZE):
                    output.write(chunk)


def _cli() -> None:
    """Emit one trusted container inventory selected by the host runner."""

    if len(sys.argv) != 3 or sys.argv[1] not in {"attachments", "releases"}:
        raise SystemExit("usage: migration_inventory.py attachments|releases ROOT")
    root = Path(sys.argv[2])
    if sys.argv[1] == "attachments":
        print(json.dumps(asdict(attachment_inventory(root)), sort_keys=True))
    else:
        print(json.dumps(release_inventory(root), sort_keys=True))


if __name__ == "__main__":
    _cli()
