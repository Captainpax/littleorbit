"""Read-only admission contract for the separate Little Orbit array recovery.

This module never formats, mounts, creates directories, copies application data,
starts Docker, or admits application/runtime health. Sealed producer artifacts
are preserved as evidence; their hashes do not make their contents accepted.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
from pathlib import Path
import re
from typing import Any


GIB = 1024**3
ROOT = "/mnt/disk2/little-orbit-recovery"
DOCKER_IMAGE = "/mnt/disk2/system/docker-little-orbit/docker.img"
DISK_SERIAL = "S64ANL0T821299K"
DISK_ID = f"Samsung_SSD_980_1TB_{DISK_SERIAL}"
SERVICES = (
    "gateway", "web", "api", "postgres", "worker", "context-fetcher",
    "ollama", "media-worker", "clamav",
)
PATHS = {name: f"{ROOT}/{name}" for name in (
    "live", "deploy", "secrets", "gpu-coordinator", "rollback",
)}
PATHS["dockerImage"] = DOCKER_IMAGE
PROVENANCE_KINDS = {
    "source-inventory", "cold-rollback", "database-state", "runtime-images",
    "models", "gpu-acceptance", "jobs-hold", "firewall",
}
PENDING_GATES = sorted(PROVENANCE_KINDS | {
    "metadata-and-content-review", "fresh-on-host-recheck", "compose-model-review",
    "isolated-runtime-acceptance", "public-route-acceptance", "autostart-acceptance",
})
MAX_JSON_BYTES = 2 * 1024**2


class AdmissionError(ValueError):
    """A bounded, content-free admission failure."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AdmissionError(message)


def integer(value: Any, label: str, minimum: int = 0) -> int:
    require(type(value) is int and value >= minimum, f"Invalid {label}")
    return int(value)


def exact_keys(value: Any, keys: set[str], label: str) -> dict[str, Any]:
    require(isinstance(value, dict) and set(value) == keys, f"Invalid {label} fields")
    return value


def _unique_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        require(key not in result, "Duplicate JSON field")
        result[key] = value
    return result


def decode_json(payload: bytes) -> dict[str, Any]:
    require(0 < len(payload) <= MAX_JSON_BYTES, "Evidence JSON size is outside bounds")
    try:
        value = json.loads(payload, object_pairs_hook=_unique_pairs)
    except (UnicodeError, json.JSONDecodeError) as error:
        raise AdmissionError("Malformed evidence JSON") from error
    require(isinstance(value, dict), "Evidence JSON is not an object")
    return value


def read_sealed_json(path: Path, expected_sha256: str) -> tuple[dict[str, Any], bytes]:
    require(bool(re.fullmatch(r"[0-9a-f]{64}", expected_sha256)), "Invalid evidence digest")
    require(not path.is_symlink() and path.is_file(), "Evidence is not a plain file")
    require(path.stat().st_size <= MAX_JSON_BYTES, "Evidence JSON exceeds its bound")
    with path.open("rb") as handle:
        payload = handle.read(MAX_JSON_BYTES + 1)
    require(hashlib.sha256(payload).hexdigest() == expected_sha256, "Evidence digest differs")
    return decode_json(payload), payload


def verify_artifact(item: Any) -> tuple[dict[str, Any], bytes]:
    record = exact_keys(item, {"path", "bytes", "sha256"}, "artifact descriptor")
    require(isinstance(record["path"], str), "Invalid artifact path")
    path = Path(record["path"])
    require(path.is_absolute(), "Artifact path is not absolute")
    size = integer(record["bytes"], "artifact length", 1)
    value, payload = read_sealed_json(path, record["sha256"])
    require(len(payload) == size, "Evidence exact length differs")
    return value, payload


def timestamp(value: Any) -> dt.datetime:
    require(isinstance(value, str), "Invalid observation timestamp")
    try:
        parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise AdmissionError("Malformed observation timestamp") from error
    require(parsed.tzinfo is not None and parsed.utcoffset() == dt.timedelta(0),
            "Observation timestamp must be UTC")
    return parsed


def parse_status(value: Any) -> dict[str, str]:
    require(isinstance(value, str) and 0 < len(value) <= 128 * 1024,
            "Invalid mdcmd evidence")
    fields: dict[str, str] = {}
    for line in value.splitlines():
        if not line.strip():
            continue
        key, separator, item = line.partition("=")
        require(bool(separator) and key not in fields, "Malformed or duplicate mdcmd field")
        fields[key] = item
    return fields


def validate_mount(value: Any) -> None:
    record = exact_keys(value, {"target", "source", "fstype", "options"}, "disk2 mount")
    require(record["target"] == "/mnt/disk2", "Disk2 mount target differs")
    require(record["source"] == "/dev/md2p1", "Disk2 is not the direct array device")
    require(record["fstype"] == "xfs", "Disk2 filesystem is not the reviewed XFS mount")
    require(isinstance(record["options"], str), "Invalid mount options")
    options = set(record["options"].split(","))
    require("rw" in options and "ro" not in options, "Disk2 is not writable")


def validate_array(value: Any) -> None:
    fields = parse_status(value)
    expected = {
        "mdState": "STARTED", "mdResync": "0", "sbSyncExit": "0", "sbSyncErrs": "0",
        "mdNumMissing": "0", "mdNumWrong": "0", "mdNumNew": "0", "diskId.2": DISK_ID,
    }
    for slot in (0, 1, 2):
        expected[f"rdevStatus.{slot}"] = "DISK_OK"
        expected[f"rdevNumErrors.{slot}"] = "0"
    require(all(fields.get(key) == item for key, item in expected.items()),
            "Array identity, health or inactive parity evidence differs")


def validate_observation(value: Any, now: dt.datetime) -> int:
    record = exact_keys(value, {
        "recordType", "observedAt", "hostname", "disk2Mount", "mdcmdStatus",
        "availableBytes", "rootBacking", "quarantine", "runtimeImage",
    }, "host observation")
    require(record["recordType"] == "little-orbit-array-observation/v1", "Wrong observer kind")
    require(record["hostname"] == "na-west-2", "Wrong observed host")
    age = (now - timestamp(record["observedAt"])).total_seconds()
    require(0 <= age <= 300, "Host observation is stale or from the future")
    validate_mount(record["disk2Mount"])
    validate_array(record["mdcmdStatus"])
    require(record["rootBacking"] == "rootfs", "Unexpected Unraid ROOTFS identity")
    quarantine = exact_keys(record["quarantine"], {
        "dockerEnabled", "libvirtEnabled", "dockerdProcesses", "containerdProcesses",
        "libvirtdProcesses", "cacheMounted",
    }, "quarantine")
    for name in ("dockerdProcesses", "containerdProcesses", "libvirtdProcesses"):
        integer(quarantine[name], name)
    require(type(quarantine["cacheMounted"]) is bool, "Invalid cache mount observation")
    require(quarantine == {
        "dockerEnabled": "no", "libvirtEnabled": "disable", "dockerdProcesses": 0,
        "containerdProcesses": 0, "libvirtdProcesses": 0, "cacheMounted": False,
    }, "Runtime quarantine no longer matches the admission stage")
    image = exact_keys(record["runtimeImage"], {"path", "state"}, "runtime image")
    require(image == {"path": DOCKER_IMAGE, "state": "ABSENT"},
            "New runtime path is occupied; preserve it and review separately")
    return integer(record["availableBytes"], "available bytes", 1)


def validate_budget(value: Any, available: int) -> dict[str, int]:
    budget = exact_keys(value, {
        "runtimeImageBytes", "applicationBytes", "modelBytes", "stagingBytes",
        "rollbackBytes", "residualBytes",
    }, "full-growth budget")
    numbers = {key: integer(item, key, 1) for key, item in budget.items()}
    require(numbers["runtimeImageBytes"] == 200 * GIB, "Runtime must budget exactly 200 GiB")
    require(numbers["residualBytes"] >= 100 * GIB, "Residual reserve is below 100 GiB")
    require(numbers["rollbackBytes"] >= numbers["applicationBytes"] + numbers["modelBytes"],
            "Rollback does not cover the whole application and model allocation")
    total = sum(numbers.values())
    require(available >= total, "Insufficient disk2 full-growth capacity and residual reserve")
    return {**numbers, "requiredAvailableBytes": total, "availableBytes": available,
            "headroomBeyondBudgetBytes": available - total}


def validate_provenance(value: Any) -> dict[str, dict[str, Any]]:
    require(isinstance(value, list), "Invalid provenance descriptors")
    kinds: dict[str, dict[str, Any]] = {}
    for item in value:
        record = exact_keys(item, {"kind", "artifact"}, "provenance descriptor")
        kind = record["kind"]
        require(kind in PROVENANCE_KINDS and kind not in kinds, "Unknown or duplicate proof kind")
        artifact, _ = verify_artifact(record["artifact"])
        kinds[kind] = artifact
    return kinds


def validate_size_provenance(records: dict[str, dict[str, Any]], budget: dict[str, int]) -> None:
    require("source-inventory" in records, "A sealed source size inventory is required")
    source = exact_keys(records["source-inventory"], {
        "recordType", "sourceImageSha256", "sourceImageBytes", "inventorySha256",
        "applicationLogicalBytes", "modelLogicalBytes",
    }, "cold size inventory")
    require(source["recordType"] == "little-orbit-cold-size-inventory/v1", "Wrong size producer kind")
    require(source["sourceImageBytes"] == 2000398934016
            and type(source["sourceImageBytes"]) is int, "Wrong source image length")
    require(source["sourceImageSha256"] ==
            "4827cda6514ce4548e50d9b22afee024a7441bfcd99116dcf649852a3be22e54",
            "Wrong accepted source image identity")
    require(isinstance(source["inventorySha256"], str)
            and bool(re.fullmatch(r"[0-9a-f]{64}", source["inventorySha256"])),
            "Invalid source inventory seal")
    for budget_key, source_key in (("applicationBytes", "applicationLogicalBytes"),
                                   ("modelBytes", "modelLogicalBytes")):
        observed = integer(source[source_key], source_key)
        require(budget[budget_key] >= observed, "Budget is below its sealed source allocation")


def admit(manifest: Any, now: dt.datetime) -> dict[str, Any]:
    record = exact_keys(manifest, {
        "recordType", "target", "paths", "services", "restartPolicy", "jobPolicy",
        "budget", "hostObservation", "provenanceFiles",
    }, "admission manifest")
    require(record["recordType"] == "little-orbit-array-admission/v1", "Wrong admission kind")
    require(record["target"] == {"hostname": "na-west-2", "disk2Serial": DISK_SERIAL},
            "Wrong recovery target")
    require(record["paths"] == PATHS, "Recovery paths differ from the separate fixed profile")
    require(record["services"] == list(SERVICES), "Essential service allowlist differs")
    require(record["restartPolicy"] == "no", "Recovery restarts must remain disabled")
    require(record["jobPolicy"] == "HOLD_UNTIL_SEPARATE_REVIEW", "Automatic jobs are not held")
    observation, _ = verify_artifact(record["hostObservation"])
    available = validate_observation(observation, now)
    budget = validate_budget(record["budget"], available)
    sealed = validate_provenance(record["provenanceFiles"])
    validate_size_provenance(sealed, budget)
    return {
        "recordType": "little-orbit-array-admission-result/v1",
        "stage": "PINNED_OBSERVATION_AND_BUDGET_ADMITTED_NOT_RUNTIME_ACCEPTANCE",
        "observationAt": observation["observedAt"], "budget": budget,
        "sealedArtifactKinds": sorted(sealed), "pendingAcceptanceGates": PENDING_GATES,
        "runtimeActionsAvailable": [], "servicesMayBeStarted": [],
    }


def proposed_stage_argv(stage: str) -> list[str]:
    """Return a non-executed proposal, never an authorization or shell command."""
    stages = {
        "database": ["postgres"], "gpu": ["ollama"],
        "private-frontend": ["api", "web", "gateway"],
        "held-workers": ["context-fetcher", "clamav", "worker", "media-worker"],
    }
    require(stage in stages, "Unknown proposed recovery stage")
    repo = f"{ROOT}/deploy/repo"
    return [
        "docker", "--host", "unix:///var/run/docker.sock", "compose",
        "--project-name", "little-orbit-recovery", "--project-directory", f"{repo}/infra",
        "--env-file", f"{ROOT}/secrets/runtime.env", "-f", f"{repo}/infra/compose.yaml",
        "-f", f"{repo}/infra/compose.rx480.yaml", "-f", f"{repo}/infra/compose.array-recovery.yaml",
        "up", "--no-deps", "--no-build", "--pull", "never", "--wait",
        "--wait-timeout", "600", *stages[stage],
    ]
