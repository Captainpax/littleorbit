"""Synthetic-only normalized models; never load .env, a daemon or recovery data."""

from copy import deepcopy
from pathlib import Path
import runpy
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import array_recovery_profile as inert
import array_serving_profile as serving
from array_serving_network import DNS_OPTIONS, EGRESS
from array_serving_resources import approved_resources

HERE = Path(__file__).resolve().parents[1]
OLD = runpy.run_path(str(HERE / "tests/test_array_recovery_profile.py"))


def contract() -> dict:
    preparation = OLD["fixture_contract"]()
    preparation["resources"] = approved_resources()
    return {"preparation": preparation, "cgroupParent": "/little-orbit-recovery",
        "resolvers": ["192.168.50.1"], "smtpHost": "smtp.example.invalid", "smtpPort": 587,
        "mailCutover": "2026-10-22T20:00:00+00:00"}


def request() -> dict:
    return {"schema": "LITTLE_ORBIT_SERVING_ADMISSION_REQUEST_V1",
        "phase": "SERVING_REQUESTED_NOT_ADMITTED", "gateReceipts": {name: {
            "path": f"{inert.ROOT}/evidence/{name}.json", "bytes": 10, "sha256": "a" * 64}
            for name in serving.GATES}}


def inert_model(inputs: dict) -> dict:
    preparation = inputs["preparation"]
    environments = OLD["environment_fixture"]()
    services = {}
    for name in inert.SERVICES:
        resource = preparation["resources"][name]
        service = {"profiles": [inert.PROFILE], "restart": "no", "pull_policy": "never",
            "image": preparation["images"][name], "user": preparation["users"][name],
            "cpus": resource["cpus"], "mem_limit": resource["memoryBytes"],
            "memswap_limit": resource["memoryBytes"], "pids_limit": resource["pids"],
            "read_only": True, "cap_drop": ["ALL"], "security_opt": ["no-new-privileges:true"],
            "logging": {"driver": "json-file", "options": {"max-size": "10m", "max-file": "3"}},
            "entrypoint": inert.COMMANDS[name][0], "command": inert.COMMANDS[name][1],
            "tmpfs": inert.TMPFS[name], "networks": {net: {} for net in inert.NETWORKS[name]},
            "volumes": [{"type": "bind", "source": source, "target": target,
                "read_only": readonly, "bind": {"create_host_path": False}}
                for target, (source, readonly) in inert.BINDS[name].items()]}
        if environments[name]["environment"]:
            service.update(environments[name])
        service["healthcheck"] = {"disable": True} if name in ("worker", "media-worker") else {
            "test": inert.HEALTH_TESTS[name]}
        if name in ("api", "worker"):
            service["env_file"] = [{"path": inert.ROOT + "/secrets/runtime.env", "required": True}]
        services[name] = deepcopy(service)
    services["gateway"]["cap_add"] = ["NET_BIND_SERVICE"]
    services["worker"]["group_add"] = ["2000"]
    services["worker"]["environment"]["GPU_AMD_PCI_BDF"] = preparation["gpu"]["pciBdf"]
    services["worker"]["environment"]["GPU_AMD_IDLE_VRAM_BYTES"] = str(preparation["gpu"]["idleVramBytes"])
    services["ollama"]["group_add"] = ["2000", str(preparation["gpu"]["renderGid"])]
    services["ollama"]["devices"] = [{"source": path, "target": path, "permissions": "rwm"}
        for path in ("/dev/dri/renderD128", "/dev/dri/card0")]
    for name, address in (("gateway", "10.253.14.2"), ("api", "10.253.14.3")):
        services[name]["networks"]["gateway-api"] = {"ipv4_address": address}
    networks = {name: {"name": f"little-orbit-recovery_{name}", "internal": name != "context-egress"}
        for name in {network for networks in inert.NETWORKS.values() for network in networks}}
    networks["gateway-api"]["ipam"] = {"config": [{"subnet": "10.253.14.0/28"}]}
    result = {"name": "little-orbit-recovery", "services": services, "networks": networks}
    inert.validate_model(result, preparation)
    return result


def model(inputs: dict | None = None) -> dict:
    inputs = inputs or contract()
    result = inert_model(inputs)
    for service in result["services"].values():
        service.update(profiles=[serving.PROFILE], cgroup_parent=inputs["cgroupParent"])
    worker = result["services"]["worker"]
    worker["environment"].update(WORKER_HOLD="false", GPU_RECOVERY_PROOF_MODE="false",
        RECOVERY_MAIL_NOT_BEFORE=inputs["mailCutover"], SMTP_HOST=inputs["smtpHost"],
        SMTP_PORT=str(inputs["smtpPort"]), SMTP_STARTTLS="true")
    media = result["services"]["media-worker"]
    media["environment"] = {"LITTLE_ORBIT_ENV": "production", "DATABASE_URL": "SYNTHETIC",
        "ATTACHMENT_STORAGE_DIR": "/var/lib/little-orbit/attachments", "CLAMAV_HOST": "clamav",
        "CLAMAV_PORT": "3310"}
    for role, module in (("worker", "worker"), ("media-worker", "attachment_media")):
        result["services"][role].update(entrypoint=["python", "-m"], command=[f"little_orbit_api.{module}"],
            healthcheck={"test": serving.HEALTH[role], "interval": "20s", "timeout": "5s",
                "retries": 5, "start_period": "20s"})
    for role, scope in EGRESS.items():
        result["services"][role].update(dns=inputs["resolvers"], dns_opt=DNS_OPTIONS)
        result["services"][role]["networks"][scope["network"]] = {"ipv4_address": scope["ip"]}
        result["networks"][scope["network"]] = {"name": "little-orbit-recovery_" + scope["network"],
            "driver": "bridge", "internal": False, "driver_opts": {
                "com.docker.network.bridge.name": scope["bridge"],
                "com.docker.network.bridge.enable_ip_masquerade": "false"},
            "ipam": {"config": [{"subnet": scope["subnet"], "gateway": scope["gateway"]}]}}
    return deepcopy(result)
