"""Validate only the explicit serving delta, then replay every inert-model guard.

No lifecycle method exists here. Gate references are a *request* for independent
native acceptance, not all-true flags or evidence that a service may be started.
Never print an expanded production model or this module's private input contract.
"""

from __future__ import annotations

from copy import deepcopy
import re
from typing import Any

import array_recovery_profile as inert
from array_recovery_profile import fields, require
from array_serving_network import DNS_OPTIONS, EGRESS, validate_resolvers
from array_serving_resources import aware_utc, validate_resources

PROFILE = "array-serving-explicit-only"
GATES = frozenset({"harborBootAndSoak", "coldWorkingCopy", "daemonCohort", "imageClosure", "sourceAndSecrets",
    "existingPostgresSchema", "privacyExpiry", "amdGenerationAndEmbedding", "freshResources",
    "ownedNetwork", "privateFunctionalProof", "immutableApk", "mailCutover"})
HEALTH = {
    "worker": ["CMD", "python", "-c", "import pathlib, socket; assert b'little_orbit_api.worker' in pathlib.Path('/proc/1/cmdline').read_bytes(); socket.create_connection(('postgres', 5432), 3).close()"],
    "media-worker": ["CMD", "python", "-c", "import pathlib, socket; assert b'little_orbit_api.attachment_media' in pathlib.Path('/proc/1/cmdline').read_bytes(); socket.create_connection(('postgres', 5432), 3).close(); socket.create_connection(('clamav', 3310), 3).close()"],
}


def validate_request(value: Any) -> dict[str, Any]:
    """A phase-bound sealed-reference request cannot masquerade as live acceptance."""
    request = fields(value, {"schema", "phase", "gateReceipts"}, "serving request")
    require(request["schema"] == "LITTLE_ORBIT_SERVING_ADMISSION_REQUEST_V1"
            and request["phase"] == "SERVING_REQUESTED_NOT_ADMITTED", "Serving request phase differs")
    receipts = fields(request["gateReceipts"], set(GATES), "serving gate references")
    for item in receipts.values():
        ref = fields(item, {"path", "bytes", "sha256"}, "gate receipt")
        require(type(ref["path"]) is str and ref["path"].startswith(inert.ROOT + "/")
                and ".." not in ref["path"].split("/"), "Gate receipt path invalid")
        require(type(ref["bytes"]) is int and 0 < ref["bytes"] <= 16 * 1024**2,
                "Gate receipt size invalid")
        require(type(ref["sha256"]) is str and re.fullmatch(r"[0-9a-f]{64}", ref["sha256"])
                is not None, "Gate receipt seal invalid")
    return request


def validate_contract(value: Any) -> dict[str, Any]:
    """Validate private configuration separately from sanitized model results."""
    contract = fields(value, {"preparation", "cgroupParent", "resolvers", "smtpHost",
        "smtpPort", "mailCutover"}, "serving contract")
    inert.validate_contract(contract["preparation"])
    validate_resources(contract["preparation"]["resources"])
    parent = contract["cgroupParent"]
    require(type(parent) is str and parent.startswith("/") and parent != "/"
            and ".." not in parent.split("/"), "Owned cgroup parent invalid")
    require(len(validate_resolvers(contract["resolvers"])) == 1, "Serving profile requires one resolver")
    require(type(contract["smtpHost"]) is str and bool(contract["smtpHost"])
            and not any(char.isspace() for char in contract["smtpHost"]), "SMTP hostname missing")
    port = contract["smtpPort"]
    require(type(port) is int and 1 <= port <= 65535 and port != 465, "SMTP STARTTLS port invalid")
    cutoff = aware_utc(contract["mailCutover"])
    require(cutoff.isoformat() == contract["mailCutover"], "Mail cutoff must be canonical UTC")
    return contract


def validate_serving_common(model: dict[str, Any], contract: dict[str, Any]) -> None:
    for name, service in model["services"].items():
        require(service.get("profiles") == [PROFILE], "Serving profile differs")
        require(service.pop("cgroup_parent", None) == contract["cgroupParent"], "Cgroup parent differs")
        service["profiles"] = [inert.PROFILE]
        if name in EGRESS:
            require(service.pop("dns", None) == contract["resolvers"]
                    and service.pop("dns_opt", None) == DNS_OPTIONS, "Explicit DNS differs")


def project_worker(service: dict[str, Any], contract: dict[str, Any]) -> None:
    require(service.get("entrypoint") == ["python", "-m"]
            and service.get("command") == ["little_orbit_api.worker"], "Serving worker command differs")
    environment = service.get("environment", {})
    expected = {"WORKER_HOLD": "false", "GPU_RECOVERY_PROOF_MODE": "false",
        "RECOVERY_MAIL_NOT_BEFORE": contract["mailCutover"], "SMTP_HOST": contract["smtpHost"],
        "SMTP_PORT": str(contract["smtpPort"]), "SMTP_STARTTLS": "true"}
    require(all(environment.get(key) == value for key, value in expected.items()), "Serving worker boundary differs")
    for key in ("RECOVERY_MAIL_NOT_BEFORE", "SMTP_HOST", "SMTP_PORT", "SMTP_STARTTLS"):
        environment.pop(key)
    environment.update(WORKER_HOLD="true", GPU_RECOVERY_PROOF_MODE="true")
    project_held(service, "worker")


def project_media(service: dict[str, Any]) -> None:
    require(service.get("entrypoint") == ["python", "-m"] and service.get("command") == [
        "little_orbit_api.attachment_media"], "Serving media command differs")
    environment = fields(service.get("environment"), {"LITTLE_ORBIT_ENV", "DATABASE_URL",
        "ATTACHMENT_STORAGE_DIR", "CLAMAV_HOST", "CLAMAV_PORT"}, "media environment")
    require(environment["LITTLE_ORBIT_ENV"] == "production" and environment["CLAMAV_HOST"] == "clamav"
            and environment["CLAMAV_PORT"] == "3310", "Media dependency differs")
    require(environment["ATTACHMENT_STORAGE_DIR"] == "/var/lib/little-orbit/attachments"
            and type(environment["DATABASE_URL"]) is str and bool(environment["DATABASE_URL"]),
            "Media working storage/credential missing")
    service["environment"] = {"WORKER_HOLD": "true"}
    project_held(service, "media-worker")


def project_held(service: dict[str, Any], role: str) -> None:
    """Validate genuine serving fields before making an explicit inert comparison copy."""
    require(service.get("healthcheck") == {"test": HEALTH[role], "interval": "20s",
        "timeout": "5s", "retries": 5, "start_period": "20s"}, "Worker health differs")
    service.update(entrypoint=inert.HELD_ENTRYPOINT, command=inert.HELD_COMMAND,
                   healthcheck={"disable": True})


def project_networks(model: dict[str, Any]) -> None:
    networks = model["networks"]
    for role, scope in EGRESS.items():
        name = scope["network"]
        network = networks.get(name)
        keys = {"name", "driver", "driver_opts", "ipam"}
        require(type(network) is dict and set(network) in (keys, keys | {"internal"}),
                "Serving egress network fields differ")
        # Compose omits an explicit false default in config JSON. Only this
        # representation difference is accepted; actual true/unknown still fails.
        require(type(network.get("internal", False)) is bool, "Network internal flag invalid")
        require({**network, "internal": network.get("internal", False)} == {
            "name": f"little-orbit-recovery_{name}", "driver": "bridge",
            "internal": False, "driver_opts": {"com.docker.network.bridge.name": scope["bridge"],
                "com.docker.network.bridge.enable_ip_masquerade": "false"},
            "ipam": {"config": [{"subnet": scope["subnet"], "gateway": scope["gateway"]}]}},
            "Owned egress network differs")
        service_networks = model["services"][role]["networks"]
        require(service_networks.pop(name, None) == {"ipv4_address": scope["ip"]},
                "Owned egress address differs")
    networks.pop("worker-mail-egress")
    networks["context-egress"] = {"name": "little-orbit-recovery_context-egress"}
    model["services"]["context-fetcher"]["networks"]["context-egress"] = {}


def validate_model(value: Any, contract: Any, request: Any) -> dict[str, Any]:
    """Return no private model fields and no lifecycle permissions."""
    expected = validate_contract(contract)
    validate_request(request)
    require(type(value) is dict, "Serving model invalid")
    model = deepcopy(value)
    require(type(model.get("services")) is dict and set(model["services"]) == set(inert.SERVICES),
            "Serving service map differs")
    require(type(model.get("networks")) is dict, "Serving networks missing")
    model.pop("x-array-serving", None)
    validate_serving_common(model, expected)
    project_worker(model["services"]["worker"], expected)
    project_media(model["services"]["media-worker"])
    project_networks(model)
    inert.validate_model(model, expected["preparation"])
    return {"schema": "LITTLE_ORBIT_SERVING_MODEL_VALIDATED_V1",
        "stage": "MODEL_ONLY_NOT_NATIVE_ADMISSION", "services": list(inert.SERVICES),
        "requiredGateReceipts": sorted(GATES), "publicHostPorts": [],
        "runtimeActionsAvailable": [], "servicesMayBeStarted": [], "runtimeAccepted": False}
