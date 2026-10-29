"""Pure recovery-model preparation; no Docker/host/copy lifecycle authority.

The caller separately validates the pinned, fresh array admission manifest with
array_recovery_admission.admit. Resource/image inputs bind a reviewed contract;
their presence does not establish image contents, headroom or runtime acceptance.
Never persist or print an expanded production Compose model: it can hold secrets.
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
import re
from typing import Any

ROOT = "/mnt/disk2/little-orbit-recovery"
PROFILE = "array-recovery-explicit-only"
SERVICES = (
    "gateway", "web", "api", "postgres", "worker", "context-fetcher",
    "ollama", "media-worker", "clamav",
)
NETWORKS = {
    "gateway": {"gateway-api", "gateway-web"},
    "web": {"private", "gateway-web"}, "api": {"private", "gateway-api"},
    "postgres": {"private", "media-private"},
    "worker": {"private", "ai-private", "context-private"},
    "context-fetcher": {"context-private", "context-egress"},
    "ollama": {"ai-private"}, "media-worker": {"media-private"},
    "clamav": {"media-private"},
}
BINDS = {
    "gateway": {"/etc/caddy/Caddyfile": (
        f"{ROOT}/deploy/repo/infra/gateway/Caddyfile", True)},
    "web": {},
    "api": {"/var/lib/little-orbit/releases": (f"{ROOT}/live/releases", True),
            "/var/lib/little-orbit/attachments": (f"{ROOT}/live/attachments", False)},
    "postgres": {"/var/lib/postgresql/data": (f"{ROOT}/live/postgres", False)},
    "worker": {"/var/lib/little-orbit/attachments": (f"{ROOT}/live/attachments", False),
               "/run/gpu-coordinator/gpu.lock": (f"{ROOT}/gpu-coordinator/gpu.lock", False),
               "/run/gpu-probe": ("/run/little-orbit-gpu-probe", True)},
    "context-fetcher": {},
    "ollama": {"/root/.ollama": (f"{ROOT}/live/ollama", True),
               "/run/gpu-coordinator/gpu.lock": (f"{ROOT}/gpu-coordinator/gpu.lock", False)},
    "media-worker": {"/var/lib/little-orbit/attachments": (f"{ROOT}/live/attachments", False)},
    "clamav": {"/var/lib/clamav": (f"{ROOT}/live/clamav", True)},
}
HELD_ENTRYPOINT = ["python", "-I", "-S", "-c"]
HELD_COMMAND = ["import signal; signal.pause()"]
POSTGRES_GUARD = (
    'test -d "$${PGDATA}" && test ! -L "$${PGDATA}" && '
    'test -f "$${PGDATA}/PG_VERSION" && test ! -L "$${PGDATA}/PG_VERSION" && '
    'test "$$(cat "$${PGDATA}/PG_VERSION")" = 17 && '
    'test -s "$${PGDATA}/global/pg_control" && exec postgres -D "$${PGDATA}"'
)
COMMANDS = {
    "gateway": (["caddy"], ["run", "--config", "/etc/caddy/Caddyfile", "--adapter", "caddyfile"]),
    "web": (["node"], ["server.js"]),
    "api": (["uvicorn"], ["little_orbit_api.main:app", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers"]),
    "postgres": (["/bin/sh", "-ec"], [POSTGRES_GUARD]),
    "worker": (HELD_ENTRYPOINT, HELD_COMMAND),
    "context-fetcher": (["uvicorn"], ["little_orbit_api.public_context_fetcher:app", "--host", "0.0.0.0", "--port", "8010", "--no-proxy-headers"]),
    "ollama": (["ollama"], ["serve"]), "media-worker": (HELD_ENTRYPOINT, HELD_COMMAND),
    "clamav": (["clamd"], ["--foreground=true"]),
}
TMPFS = {
    "gateway": ["/data:size=16m,mode=1777", "/config:size=16m,mode=1777"],
    "web": ["/tmp:size=32m,mode=1777"],
    "api": ["/tmp:size=32m,mode=1770,uid=65532,gid=65532"],
    "postgres": ["/var/run/postgresql:size=16m,mode=0770,uid=999,gid=999", "/tmp:size=32m,mode=1770,uid=999,gid=999"],
    "worker": ["/tmp:size=32m,mode=1770,uid=65532,gid=65532"],
    "context-fetcher": ["/tmp:size=16m,mode=1770,uid=65532,gid=65532"],
    "ollama": ["/tmp:size=64m,mode=1777"],
    "media-worker": ["/tmp:size=512m,mode=1770,uid=65532,gid=65532"],
    "clamav": ["/tmp:size=32m,mode=1777", "/var/log/clamav:size=16m,mode=1777", "/run/clamav:size=16m,mode=1777"],
}
HEALTH_TESTS = {
    "gateway": ["CMD", "wget", "--spider", "--quiet", "http://127.0.0.1:8180/api/v1/health/live"],
    "web": ["CMD", "wget", "--spider", "--quiet", "http://127.0.0.1:3014/status"],
    "api": ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/v1/health/live', timeout=3)"],
    "postgres": ["CMD-SHELL", "pg_isready -h 127.0.0.1 -U $${POSTGRES_USER} -d $${POSTGRES_DB}"],
    "context-fetcher": ["CMD", "python", "-c", "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8010/v1/health/live', timeout=3)"],
    "ollama": ["CMD", "ollama", "list"],
    "clamav": ["CMD-SHELL", "clamdscan --ping 1 >/dev/null 2>&1"],
}
ALLOWED_SERVICE_KEYS = {
    "profiles", "restart", "pull_policy", "cap_drop", "cap_add", "security_opt", "logging",
    "image", "user", "cpus", "mem_limit", "memswap_limit", "pids_limit",
    "read_only", "entrypoint", "command", "volumes", "networks", "healthcheck",
    "environment", "env_file", "tmpfs", "group_add", "devices",
}
PENDING = [
    "fresh-exact-disk2-and-runtime-backing-recheck", "full-growth-residual-budget",
    "verified-cold-copy-and-rollback", "original-schema-and-credentials",
    "exact-local-image-content-and-entrypoint-review", "fresh-resource-headroom",
    "created-container-exact-mount-census-no-anonymous-volumes",
    "root-server-peercred-and-socket-dac-deployment", "both-models-actual-rx480-proof",
    "private-runtime-health", "privacy-expiry-working-copy-review",
    "npm-only-firewall-and-public-api-wss", "controlled-restart-soak-and-autostart",
]


class ProfileError(ValueError):
    """Sanitized model preparation failure; no private values in messages."""


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ProfileError(message)


def fields(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    require(type(value) is dict and set(value) == expected, f"Invalid {label} fields")
    return value


def positive_int(value: Any, label: str) -> int:
    require(type(value) is int and value > 0, f"Invalid {label}")
    return value


def rendered_bytes(value: Any) -> int:
    if type(value) is str and re.fullmatch(r"[1-9][0-9]*", value):
        return int(value)
    return positive_int(value, "rendered memory bytes")


def cpu(value: Any) -> Decimal:
    require(type(value) in (str, int, float), "Invalid CPU allocation")
    try:
        result = Decimal(str(value))
    except InvalidOperation as error:
        raise ProfileError("Invalid CPU allocation") from error
    require(result.is_finite() and 0 < result <= 128, "CPU allocation outside bounds")
    return result


def validate_contract(value: Any) -> dict[str, Any]:
    contract = fields(value, {"recordType", "images", "imageVolumeTargets", "users", "resources", "gpu"}, "profile contract")
    require(contract["recordType"] == "little-orbit-array-profile-input/v1", "Wrong contract kind")
    for key in ("images", "imageVolumeTargets", "users", "resources"):
        fields(contract[key], set(SERVICES), key)
    for name in SERVICES:
        require(type(contract["images"][name]) is str and bool(re.fullmatch(
            r"sha256:[0-9a-f]{64}", contract["images"][name])), "Image is not an exact local ID")
        require(type(contract["users"][name]) is str and bool(re.fullmatch(
            r"[0-9]+:[0-9]+", contract["users"][name])), "User must be reviewed numeric UID:GID")
        resource = fields(contract["resources"][name], {"cpus", "memoryBytes", "pids"}, "resources")
        cpu(resource["cpus"])
        require(16 * 1024**2 <= positive_int(resource["memoryBytes"], "memory") <= 64 * 1024**3,
                "Memory allocation outside bounds")
        require(16 <= positive_int(resource["pids"], "PID budget") <= 4096, "PID budget outside bounds")
    for name in ("api", "worker", "context-fetcher", "media-worker"):
        require(contract["users"][name] == "65532:65532", "Application identity differs")
    # The inspected pg17-bookworm image defines postgres as 999:999. The outer
    # recovered directory's historical GID is not the runtime image identity.
    require(contract["users"]["postgres"] == "999:999", "PostgreSQL identity differs")
    validate_gpu_contract(contract["gpu"])
    return contract


def validate_gpu_contract(value: Any) -> None:
    gpu = fields(value, {"pciBdf", "idleVramBytes", "renderGid", "cardGid"}, "GPU")
    require(type(gpu["pciBdf"]) is str and bool(re.fullmatch(
        r"[0-9a-f]{4}:[0-9a-f]{2}:[0-9a-f]{2}\.[0-7]", gpu["pciBdf"])), "Invalid GPU PCI identity")
    require(type(gpu["idleVramBytes"]) is int and 0 <= gpu["idleVramBytes"] < 8 * 1024**3,
            "Invalid quiet GPU baseline")
    for name in ("renderGid", "cardGid"):
        require(type(gpu[name]) is int and gpu[name] >= 0, "Invalid GPU group")
    require(gpu["renderGid"] == gpu["cardGid"] and gpu["renderGid"] != 2000,
            "Device groups require a separately reviewed profile change")


def validate_image_volumes(contract: dict[str, Any]) -> None:
    for name in SERVICES:
        targets = contract["imageVolumeTargets"][name]
        require(type(targets) is list and all(type(item) is str for item in targets)
                and len(targets) == len(set(targets)),
                "Invalid image-declared volume inventory")
        covered = set(BINDS[name]) | {item.split(":", maxsplit=1)[0] for item in TMPFS[name]}
        require(all(type(target) is str and target.startswith("/") and target in covered
                    for target in targets), "Image would create an uncovered anonymous volume")


def validate_capabilities(service: dict[str, Any], name: str) -> None:
    capabilities = ["NET_BIND_SERVICE"] if name == "gateway" else []
    require(service.get("cap_add", []) == capabilities, "Recovery capability bound differs")


def validate_common(service: dict[str, Any], expected: dict[str, Any], name: str) -> None:
    require(set(service) <= ALLOWED_SERVICE_KEYS, "Unexpected service configuration field")
    require(service.get("profiles") == [PROFILE] and service.get("restart") == "no"
            and service.get("pull_policy") == "never", "Recovery lifecycle guard differs")
    require(service.get("image") == expected["images"][name]
            and service.get("user") == expected["users"][name], "Image or user pin differs")
    resource = expected["resources"][name]
    require(cpu(service.get("cpus")) == cpu(resource["cpus"]), "CPU allocation differs")
    require(rendered_bytes(service.get("mem_limit")) == resource["memoryBytes"]
            and rendered_bytes(service.get("memswap_limit")) == resource["memoryBytes"]
            and service.get("pids_limit") == resource["pids"], "Memory/PID allocation differs")
    require(service.get("cap_drop") == ["ALL"] and service.get("read_only") is True
            and service.get("security_opt") == ["no-new-privileges:true"], "Container isolation differs")
    validate_capabilities(service, name)
    require(service.get("logging") == {"driver": "json-file", "options": {
        "max-size": "10m", "max-file": "3"}}, "Log bound differs")
    require(service.get("entrypoint") == COMMANDS[name][0]
            and service.get("command") == COMMANDS[name][1], "Service command differs")
    require(service.get("tmpfs", []) == TMPFS[name], "Temporary filesystem bound differs")
    if name not in ("worker", "ollama"):
        require(not service.get("group_add"), "Unexpected supplementary group")


def validate_mounts(service: dict[str, Any], name: str) -> None:
    mounts = service.get("volumes", [])
    require(type(mounts) is list and len(mounts) == len(BINDS[name]), "Unexpected bind count")
    found: set[str] = set()
    for mount in mounts:
        target = validate_bind_mount(mount, BINDS[name])
        require(target not in found, "Duplicate mount target")
        found.add(target)
    validate_environment_file(service, name)


def validate_bind_mount(mount: Any, expected: dict[str, tuple[str, bool]]) -> str:
    require(type(mount) is dict and set(mount) <= {
        "type", "source", "target", "read_only", "bind"}, "Unexpected mount field")
    target = mount.get("target")
    require(type(target) is str and target in expected, "Unexpected mount target")
    source, readonly = expected[target]
    require(mount.get("type") == "bind" and mount.get("source") == source
            and mount.get("read_only", False) is readonly
            and mount.get("bind") == {"create_host_path": False}, "Unsafe recovery bind")
    return target


def validate_environment_file(service: dict[str, Any], name: str) -> None:
    env_files = service.get("env_file", [])
    if name in ("api", "worker"):
        require(type(env_files) is list and len(env_files) == 1, "Runtime secret file count differs")
        record = env_files[0]
        require(type(record) is dict and set(record) <= {"path", "required"}, "Runtime secret descriptor differs")
        require(record.get("path") == f"{ROOT}/secrets/runtime.env"
                and record.get("required", True) is True,
                "Runtime secret file path differs")
    else:
        require(not env_files, "Unexpected environment file")


def validate_networks(model: dict[str, Any]) -> None:
    networks = model.get("networks")
    expected = {item for names in NETWORKS.values() for item in names}
    require(type(networks) is dict and set(networks) == expected, "Network allowlist differs")
    for name, item in networks.items():
        allowed = {"name", "internal", "ipam"}
        require(type(item) is dict and set(item) <= allowed, "Unexpected network field")
        require(item.get("name") == f"little-orbit-recovery_{name}", "Network name differs")
        require(item.get("internal", False) is (name != "context-egress"), "Network isolation differs")
        if name != "gateway-api":
            require(not item.get("ipam"), "Unexpected network address allocation")
    require(networks["gateway-api"].get("ipam") == {"config": [{"subnet": "10.253.14.0/28"}]},
            "Reserved gateway subnet differs")
    validate_service_networks(model["services"])


def validate_service_networks(services: dict[str, Any]) -> None:
    for name, service in services.items():
        require(type(service.get("networks")) is dict
                and set(service["networks"]) == NETWORKS[name], "Service network boundary differs")
        for network, options in service["networks"].items():
            expected_options = {}
            if network == "gateway-api":
                expected_options = {"ipv4_address": "10.253.14.2" if name == "gateway" else "10.253.14.3"}
            require((options or {}) == expected_options, "Service network options differ")


def validate_gpu(services: dict[str, Any], contract: dict[str, Any]) -> None:
    gpu, worker, ollama = contract["gpu"], services["worker"], services["ollama"]
    expected = {
        "WORKER_HOLD": "true", "GPU_PROBE_BACKEND": "amd-vulkan",
        "GPU_RECOVERY_PROOF_MODE": "true", "GPU_VERIFY_IDLE_PROCESSES": "true",
        "GPU_AMD_PROBE_SOCKET": "/run/gpu-probe/idle.sock", "GPU_AMD_PCI_BDF": gpu["pciBdf"],
        "GPU_AMD_DEVICE_ID": "0x67df", "GPU_AMD_RENDER_MAJOR": "226", "GPU_AMD_RENDER_MINOR": "128",
        "GPU_AMD_IDLE_VRAM_BYTES": str(gpu["idleVramBytes"]), "GPU_LOCK_PATH": "/run/gpu-coordinator/gpu.lock",
    }
    require(all(worker.get("environment", {}).get(key) == value for key, value in expected.items()),
            "GPU proof/hold configuration differs")
    require(worker.get("group_add") == ["2000"] and ollama.get("group_add") == [
        "2000", str(gpu["renderGid"])], "GPU groups differ")
    require(ollama.get("devices") == [
        {"source": "/dev/dri/renderD128", "target": "/dev/dri/renderD128", "permissions": "rwm"},
        {"source": "/dev/dri/card0", "target": "/dev/dri/card0", "permissions": "rwm"}], "GPU devices differ")
    require(ollama.get("entrypoint") == ["ollama"] and ollama.get("command") == ["serve"],
            "Unexpected model service command")
    for name in SERVICES:
        require(name == "ollama" or not services[name].get("devices"), "Unexpected device access")


def validate_commands(services: dict[str, Any]) -> None:
    for name, test in HEALTH_TESTS.items():
        health = services[name].get("healthcheck")
        require(type(health) is dict and set(health) <= {
            "test", "timeout", "interval", "retries", "start_period"}
                and health.get("test") == test, "Health check could execute unexpected work")
    for name in ("worker", "media-worker"):
        service = services[name]
        require(service.get("entrypoint") == HELD_ENTRYPOINT and service.get("command") == HELD_COMMAND,
                "Held process could execute application work")
        require(service.get("environment", {}).get("WORKER_HOLD") == "true"
                and service.get("healthcheck") == {"disable": True}, "Held state is not explicit")
    postgres = services["postgres"]
    require(postgres.get("entrypoint") == ["/bin/sh", "-ec"], "PostgreSQL init entrypoint not bypassed")
    require(postgres.get("environment", {}).get("PGDATA") == "/var/lib/postgresql/data/pgdata",
            "PostgreSQL cold root differs")
    require(postgres.get("command") == [POSTGRES_GUARD], "PostgreSQL guard differs")
    require(services["clamav"].get("entrypoint") == ["clamd"]
            and services["clamav"].get("command") == ["--foreground=true"], "Automatic AV updater not bypassed")


def validate_environment(services: dict[str, Any]) -> None:
    expected_keys = {
        "gateway": set(), "web": {"NODE_ENV", "PORT", "INTERNAL_API_URL", "NEXT_PUBLIC_BASE_URL"},
        "api": {"DATABASE_URL", "RELEASE_STORAGE_DIR", "ATTACHMENT_STORAGE_DIR", "TRUSTED_PROXY_IP"},
        "postgres": {"PGDATA", "POSTGRES_DB", "POSTGRES_USER"},
        "worker": {"WORKER_HOLD", "GPU_PROBE_BACKEND", "GPU_RECOVERY_PROOF_MODE", "GPU_VERIFY_IDLE_PROCESSES",
                   "GPU_AMD_PROBE_SOCKET", "GPU_AMD_PCI_BDF", "GPU_AMD_DEVICE_ID", "GPU_AMD_RENDER_MAJOR",
                   "GPU_AMD_RENDER_MINOR", "GPU_AMD_IDLE_VRAM_BYTES", "GPU_LOCK_PATH", "DATABASE_URL",
                   "ATTACHMENT_STORAGE_DIR", "PUBLIC_CONTEXT_FETCHER_URL"},
        "context-fetcher": set(),
        "ollama": {"OLLAMA_VULKAN", "GGML_VK_VISIBLE_DEVICES", "VK_DRIVER_FILES", "OLLAMA_NUM_PARALLEL",
                   "OLLAMA_MAX_LOADED_MODELS", "OLLAMA_CONTEXT_LENGTH"},
        "media-worker": {"WORKER_HOLD"}, "clamav": set(),
    }
    for name, service in services.items():
        environment = service.get("environment", {})
        require(type(environment) is dict and set(environment) == expected_keys[name],
                "Unexpected explicit environment variable")
        require(all(type(value) is str and value for value in environment.values()),
                "Missing required environment value")
    require(services["ollama"]["environment"] == {
        "OLLAMA_VULKAN": "1", "GGML_VK_VISIBLE_DEVICES": "0",
        "VK_DRIVER_FILES": "/usr/share/vulkan/icd.d/radeon_icd.json",
        "OLLAMA_NUM_PARALLEL": "1", "OLLAMA_MAX_LOADED_MODELS": "1", "OLLAMA_CONTEXT_LENGTH": "4096"},
            "Vulkan/model residency configuration differs")
    require(services["web"]["environment"] == {
        "NODE_ENV": "production", "PORT": "3014", "INTERNAL_API_URL": "http://api:8000",
        "NEXT_PUBLIC_BASE_URL": "https://lil-orb.pax-kun.com"}, "Web boundary differs")
    for name in ("api", "worker"):
        require(services[name]["environment"]["ATTACHMENT_STORAGE_DIR"] == "/var/lib/little-orbit/attachments",
                "Attachment root differs")
    require(services["api"]["environment"]["RELEASE_STORAGE_DIR"] == "/var/lib/little-orbit/releases"
            and services["worker"]["environment"]["PUBLIC_CONTEXT_FETCHER_URL"] == "http://context-fetcher:8010",
            "Release/context boundary differs")


def validate_model(model: Any, contract: Any) -> dict[str, Any]:
    """Validate config --no-env-resolution JSON; return no secret-bearing fields."""
    expected = validate_contract(contract)
    validate_image_volumes(expected)
    require(type(model) is dict and set(model) <= {"name", "services", "networks", "volumes",
            "x-array-common", "x-database-role-service", "x-logging"},
            "Unexpected top-level configuration")
    require(model.get("name") == "little-orbit-recovery", "Wrong Compose project")
    services = model.get("services")
    require(type(services) is dict and set(services) == set(SERVICES), "Essential service map differs")
    require(not model.get("volumes"), "Named/anonymous recovery volumes forbidden")
    for name, service in services.items():
        require(type(service) is dict, "Invalid service")
        validate_common(service, expected, name)
        validate_mounts(service, name)
    validate_networks(model)
    validate_gpu(services, expected)
    validate_commands(services)
    validate_environment(services)
    require(services["api"].get("environment", {}).get("TRUSTED_PROXY_IP") == "10.253.14.2",
            "Proxy trust differs")
    return {
        "recordType": "little-orbit-array-profile-preparation/v1",
        "stage": "MODEL_INVARIANTS_ONLY_NOT_START_AUTHORITY",
        "services": list(SERVICES), "publicHostPorts": [],
        "heldProcesses": ["worker", "media-worker"],
        "resourceLimits": {"cpus": str(sum(cpu(item["cpus"]) for item in expected["resources"].values())),
                           "memoryBytes": sum(item["memoryBytes"] for item in expected["resources"].values())},
        "pendingGates": PENDING, "servicesMayBeStarted": [], "runtimeActionsAvailable": [],
    }
