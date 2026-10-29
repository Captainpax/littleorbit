"""Build a code-only recovery archive over an exact, already installed image.

No resolver, wheel installer, daemon, registry or execution API is available.
Base-layer placeholders deliberately require the admitted classic image cache;
a cache miss must fail import, never fetch or substitute a base. This archive
is only an artifact until native import, dependency and runtime gates pass.
"""

from __future__ import annotations

from copy import deepcopy
import hashlib
import io
import json
from pathlib import PurePosixPath
import re
import tarfile
from typing import Any
from typing import cast

SHA = re.compile(r"[0-9a-f]{64}")
IMAGE = re.compile(r"sha256:[0-9a-f]{64}")
PACKAGES = {"little_orbit_api", "little_orbit_ai"}
PREFIX = "opt/little-orbit-recovery/lib/"
MAX_SOURCE_BYTES = 16 * 1024**2


class OverlayError(ValueError):
    """Sanitized input refusal; never include production values in messages."""


def need(value: bool, reason: str) -> None:
    if not value:
        raise OverlayError(reason)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def canonical(value: Any) -> bytes:
    return (json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n").encode()


def admit_base(raw: bytes, expected: str) -> dict[str, Any]:
    need(type(expected) is str and IMAGE.fullmatch(expected) is not None, "BASE_ID")
    need(0 < len(raw) <= 1024**2 and "sha256:" + digest(raw) == expected, "BASE_CONFIG_HASH")
    try:
        value = json.loads(raw)
    except (ValueError, UnicodeError) as error:
        raise OverlayError("BASE_CONFIG_JSON") from error
    need(type(value) is dict and value.get("os") == "linux"
         and value.get("architecture") == "amd64", "BASE_PLATFORM")
    admit_base_runtime(value.get("config"))
    admit_base_layers(value.get("rootfs"))
    need(type(value.get("history", [])) is list, "BASE_HISTORY")
    return cast("dict[str, Any]", value)


def admit_base_runtime(config: Any) -> None:
    need(type(config) is dict and config.get("User") == "65532:65532"
         and not config.get("Entrypoint") and not config.get("Volumes"), "BASE_RUNTIME")
    environment = config.get("Env")
    need(type(environment) is list and all(type(item) is str and "=" in item for item in environment),
         "BASE_ENVIRONMENT")
    need("PYTHON_VERSION=3.12.11" in environment, "BASE_PYTHON_ABI")


def admit_base_layers(rootfs: Any) -> None:
    need(type(rootfs) is dict and rootfs.get("type") == "layers", "BASE_ROOTFS")
    layers = rootfs.get("diff_ids")
    need(type(layers) is list and 1 <= len(layers) <= 64
         and all(type(item) is str and IMAGE.fullmatch(item) is not None for item in layers),
         "BASE_LAYER_CLOSURE")


def source_manifest(files: dict[str, bytes]) -> tuple[list[dict[str, Any]], str]:
    need(type(files) is dict and 2 <= len(files) <= 512, "SOURCE_COUNT")
    rows: list[dict[str, Any]] = []
    for name, data in sorted(files.items()):
        path = PurePosixPath(name)
        need(type(name) is str and str(path) == name and not path.is_absolute()
             and path.parts[0] in PACKAGES and len(path.parts) >= 2
             and all(re.fullmatch(r"[a-zA-Z0-9_][a-zA-Z0-9_.-]*", part) for part in path.parts),
             "SOURCE_PATH")
        need(path.suffix in {".py", ".json", ".md", ".txt"} or path.name == "py.typed", "SOURCE_TYPE")
        need(type(data) is bytes and len(data) <= 1024**2, "SOURCE_FILE_BYTES")
        rows.append({"path": name, "bytes": len(data), "sha256": digest(data)})
    need(sum(row["bytes"] for row in rows) <= MAX_SOURCE_BYTES, "SOURCE_TOTAL_BYTES")
    need(all(f"{package}/__init__.py" in files for package in PACKAGES), "SOURCE_PACKAGE_ROOTS")
    return rows, digest(canonical(rows))


def provenance(value: dict[str, Any], tree_sha: str, base_id: str) -> dict[str, Any]:
    need(type(value) is dict and set(value) == {"sourceCommit", "reviewSha256",
         "dependencyInventorySha256", "schemaAndDependencyGitDiffSha256"}, "PROVENANCE_FIELDS")
    need(type(value["sourceCommit"]) is str
         and re.fullmatch(r"[0-9a-f]{40}", value["sourceCommit"]) is not None, "SOURCE_COMMIT")
    for name in ("reviewSha256", "dependencyInventorySha256"):
        need(type(value[name]) is str and SHA.fullmatch(value[name]) is not None, "PROVENANCE_PIN")
    need(value["schemaAndDependencyGitDiffSha256"] == digest(b""), "SCHEMA_OR_DEPENDENCY_CHANGED")
    return {"schema": "CACHED_IMMUTABLE_BASE_SOURCE_OVERLAY_V1", **value,
            "sourceTreeSha256": tree_sha, "baseImageId": base_id,
            "newDependenciesInstalled": False, "nativeAcceptance": False}


def add_file(archive: tarfile.TarFile, name: str, data: bytes) -> None:
    info = tarfile.TarInfo(name)
    info.size = len(data)
    info.mode = 0o644
    info.uid = info.gid = info.mtime = 0
    archive.addfile(info, io.BytesIO(data))


def code_layer(files: dict[str, bytes], proof: dict[str, Any]) -> bytes:
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.PAX_FORMAT) as archive:
        parents = {"opt", "opt/little-orbit-recovery", PREFIX.rstrip("/")}
        for name in files:
            parents.update(str(parent) for parent in PurePosixPath(PREFIX + name).parents
                           if str(parent) != ".")
        for name in sorted(parents, key=lambda item: (item.count("/"), item)):
            info = tarfile.TarInfo(name)
            info.type, info.mode = tarfile.DIRTYPE, 0o755
            archive.addfile(info)
        for name, data in sorted(files.items()):
            add_file(archive, PREFIX + name, data)
        add_file(archive, "opt/little-orbit-recovery/provenance.json", canonical(proof))
    return stream.getvalue()


def derived_config(base: dict[str, Any], layer_sha: str, proof: dict[str, Any]) -> bytes:
    value = deepcopy(base)
    config = value["config"]
    replaced = {"PYTHONPATH", "PYTHONDONTWRITEBYTECODE", "PYTHONUNBUFFERED"}
    config["Env"] = [item for item in config["Env"] if item.split("=", 1)[0] not in replaced]
    config["Env"] += ["PYTHONPATH=/opt/little-orbit-recovery/lib", "PYTHONDONTWRITEBYTECODE=1",
                      "PYTHONUNBUFFERED=1"]
    config["Entrypoint"] = None
    config["Cmd"] = ["python", "-m", "little_orbit_api.worker"]
    config.pop("Healthcheck", None)
    config["Labels"] = {**(config.get("Labels") or {}),
        "org.little-orbit.recovery.source": proof["sourceCommit"],
        "org.little-orbit.recovery.tree": proof["sourceTreeSha256"],
        "org.little-orbit.recovery.base": proof["baseImageId"]}
    value["rootfs"]["diff_ids"].append("sha256:" + layer_sha)
    value["history"] = value.get("history", []) + [{
        "created_by": "Verified code-only recovery overlay; cached dependencies unchanged",
        "comment": proof["sourceTreeSha256"]}]
    return canonical(value)


def build_archive(base_raw: bytes, base_id: str, files: dict[str, bytes],
                  authority: dict[str, Any]) -> tuple[bytes, dict[str, Any]]:
    """Return a bounded artifact and proof, never publish/import/start it."""
    base = admit_base(base_raw, base_id)
    rows, tree_sha = source_manifest(files)
    proof = provenance(authority, tree_sha, base_id)
    layer = code_layer(files, proof)
    layer_sha = digest(layer)
    config = derived_config(base, layer_sha, proof)
    config_sha = digest(config)
    cached = [f"cached/{index:03d}.tar" for index in range(len(base["rootfs"]["diff_ids"]))]
    manifest = [{"Config": config_sha + ".json", "RepoTags": [],
                 "Layers": [*cached, "recovery-layer.tar"]}]
    stream = io.BytesIO()
    with tarfile.open(fileobj=stream, mode="w", format=tarfile.USTAR_FORMAT) as archive:
        for name in cached:
            add_file(archive, name, b"")
        add_file(archive, "recovery-layer.tar", layer)
        add_file(archive, config_sha + ".json", config)
        add_file(archive, "manifest.json", canonical(manifest))
    result = stream.getvalue()
    return result, {**proof, "imageId": "sha256:" + config_sha,
        "sourceFiles": rows, "newLayerDiffId": "sha256:" + layer_sha,
        "baseDiffIds": base["rootfs"]["diff_ids"], "archiveSha256": digest(result),
        "archiveBytes": len(result), "requiresExistingExactClassicLayerCache": True,
        "missingCacheMustRefuse": True, "daemonOrRegistryContacted": False}
