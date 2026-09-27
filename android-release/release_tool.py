#!/usr/bin/env python3
"""Prepare and sign Android release candidates without exposing signer secrets."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import zipfile
from pathlib import Path
from typing import Any

BUILD_TOOLS_VERSION = "37.0.0"
HEX_DIGEST = re.compile(r"^[0-9a-f]{64}$")
SAFE_VALUE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class ReleaseError(RuntimeError):
    """A fail-closed release policy violation."""


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ReleaseError(f"{path.name} must contain a JSON object")
    return value


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_digest(value: str) -> str:
    digest = re.sub(r"[^0-9a-fA-F]", "", value).lower()
    if not HEX_DIGEST.fullmatch(digest):
        raise ReleaseError("expected certificate SHA-256 is malformed")
    return digest


def _tool(name: str) -> Path:
    sdk = Path(os.environ.get("ANDROID_HOME") or os.environ.get("ANDROID_SDK_ROOT", ""))
    if not sdk:
        raise ReleaseError("ANDROID_HOME is required")
    path = sdk / "build-tools" / BUILD_TOOLS_VERSION / name
    if not path.is_file():
        raise ReleaseError(f"Android Build Tools {BUILD_TOOLS_VERSION} is missing {name}")
    return path


def _run(arguments: list[str], *, expect_success: bool = True) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(arguments, text=True, capture_output=True, check=False)
    if expect_success and result.returncode != 0:
        detail = (result.stderr or result.stdout).strip()
        raise ReleaseError(f"release tool failed: {arguments[0]}: {detail}")
    return result


def _apk_identity(apk: Path) -> tuple[str, int, str]:
    result = _run([str(_tool("aapt")), "dump", "badging", str(apk)])
    line = next((item for item in result.stdout.splitlines() if item.startswith("package:")), "")
    match = re.search(
        r"name='([^']+)'\s+versionCode='([0-9]+)'\s+versionName='([^']+)'",
        line,
    )
    if match is None:
        raise ReleaseError("APK package metadata could not be read")
    return match.group(1), int(match.group(2)), match.group(3)


def _features_from_badging(value: str) -> set[str]:
    return set(
        re.findall(r"^\s*uses-feature:\s+name='([^']+)'\s*$", value, re.MULTILINE)
    )


def _assert_required_feature(apk: Path, module: dict[str, Any]) -> None:
    required = module.get("required_feature")
    if required is None:
        return
    if not isinstance(required, str) or not SAFE_VALUE.fullmatch(required):
        raise ReleaseError(f"{module['role']} required feature is invalid")
    result = _run([str(_tool("aapt")), "dump", "badging", str(apk)])
    if required not in _features_from_badging(result.stdout):
        raise ReleaseError(f"{module['role']} APK is missing required feature {required}")


def _assert_unsigned(apk: Path) -> None:
    result = _run([str(_tool("apksigner")), "verify", str(apk)], expect_success=False)
    if result.returncode == 0:
        raise ReleaseError("the isolated builder unexpectedly produced a signed APK")


def _signer_digest(apk: Path) -> str:
    result = _run([str(_tool("apksigner")), "verify", "--verbose", "--print-certs", str(apk)])
    count = re.search(r"^Number of signers:\s*([0-9]+)\s*$", result.stdout, re.MULTILINE)
    if count is not None and count.group(1) != "1":
        raise ReleaseError("release APK must have exactly one signer")
    match = re.search(
        r"certificate SHA-256 digest:\s*([0-9a-fA-F]{64})\s*$",
        result.stdout,
        re.MULTILINE,
    )
    if match is None:
        raise ReleaseError("release signer digest was not reported")
    return match.group(1).lower()


def _scan_forbidden(apk: Path, markers: list[str]) -> None:
    encoded = [(marker, marker.encode("utf-8")) for marker in markers]
    with zipfile.ZipFile(apk) as archive:
        for entry in archive.infolist():
            if entry.filename == "assets/little-orbit-wear-smoke.apk":
                raise ReleaseError("production APK contains the Wear QA artifact")
            content = archive.read(entry)
            for marker, needle in encoded:
                if needle in content:
                    raise ReleaseError(f"production APK contains QA-only material: {marker}")


def _empty_output(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)
    if any(path.iterdir()):
        raise ReleaseError(f"output directory must be empty: {path}")


def _module_metadata(root: Path, module: dict[str, Any]) -> tuple[Path, str, int]:
    metadata_path = root / str(module["metadata"])
    metadata = _read_json(metadata_path)
    elements = metadata.get("elements")
    if not isinstance(elements, list) or len(elements) != 1 or not isinstance(elements[0], dict):
        raise ReleaseError(f"{metadata_path} must describe exactly one APK")
    element = elements[0]
    version_name = str(element.get("versionName", ""))
    version_code = int(element.get("versionCode", 0))
    output_file = str(element.get("outputFile", ""))
    if not SAFE_VALUE.fullmatch(version_name) or version_code <= 0:
        raise ReleaseError(f"{module['role']} release metadata is invalid")
    if Path(output_file).name != output_file or not output_file.endswith(".apk"):
        raise ReleaseError(f"{module['role']} output filename is unsafe")
    return metadata_path.parent / output_file, version_name, version_code


def prepare_candidate(policy_path: Path, source: Path, output: Path) -> None:
    policy = _read_json(policy_path)
    _empty_output(output)
    records: list[dict[str, Any]] = []
    version_names: set[str] = set()
    for module in policy["modules"]:
        apk, version_name, version_code = _module_metadata(source, module)
        package, actual_code, actual_name = _apk_identity(apk)
        if (package, actual_code, actual_name) != (
            module["package"],
            version_code,
            version_name,
        ):
            raise ReleaseError(f"{module['role']} APK differs from Gradle metadata")
        _assert_required_feature(apk, module)
        _assert_unsigned(apk)
        _scan_forbidden(apk, list(policy.get("forbidden_markers", [])))
        target = output / str(module["candidate_name"])
        shutil.copyfile(apk, target)
        records.append(
            {
                "role": module["role"],
                "file": target.name,
                "package": package,
                "version_name": version_name,
                "version_code": version_code,
                "bytes": target.stat().st_size,
                "sha256": _sha256(target),
                "signed": False,
            }
        )
        version_names.add(version_name)
    if policy.get("require_same_version_name", False) and len(version_names) != 1:
        raise ReleaseError("phone and Wear release names differ")
    _write_json(
        output / "candidate-manifest.json",
        {"schema": 1, "product": policy["product"], "modules": records},
    )


def _safe_candidate(directory: Path, name: str) -> Path:
    if Path(name).name != name or not name.endswith(".apk"):
        raise ReleaseError("candidate manifest contains an unsafe filename")
    path = directory / name
    if not path.is_file():
        raise ReleaseError(f"candidate file is missing: {name}")
    return path


def _read_secret(path: Path, label: str) -> str:
    value = path.read_text(encoding="utf-8").strip()
    if not value or "\n" in value or "\r" in value:
        raise ReleaseError(f"{label} file must contain exactly one non-empty line")
    return value


def _expected_certificate(policy: dict[str, Any], certificate_file: Path | None) -> str:
    pinned = policy.get("certificate_sha256")
    if pinned:
        return _normalise_digest(str(pinned))
    if certificate_file is None:
        raise ReleaseError("an expected certificate digest file is required")
    return _normalise_digest(_read_secret(certificate_file, "certificate digest"))


def _validate_candidate(record: dict[str, Any], directory: Path) -> Path:
    path = _safe_candidate(directory, str(record["file"]))
    if path.stat().st_size != int(record["bytes"]) or _sha256(path) != record["sha256"]:
        raise ReleaseError(f"candidate bytes changed: {path.name}")
    _assert_unsigned(path)
    if _apk_identity(path) != (
        record["package"],
        record["version_code"],
        record["version_name"],
    ):
        raise ReleaseError(f"candidate identity changed: {path.name}")
    return path


def _positive_integer(value: Any, label: str) -> None:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ReleaseError(f"candidate {label} is invalid")


def _validate_candidate_record(record: dict[str, Any], module: dict[str, Any]) -> None:
    version_name = record.get("version_name")
    if record.get("file") != module["candidate_name"] or record.get("package") != module["package"]:
        raise ReleaseError("candidate module identity conflicts with release policy")
    if not isinstance(version_name, str) or not SAFE_VALUE.fullmatch(version_name):
        raise ReleaseError("candidate version name is invalid")
    _positive_integer(record.get("version_code"), "version code")
    _positive_integer(record.get("bytes"), "byte count")
    if not isinstance(record.get("sha256"), str) or not HEX_DIGEST.fullmatch(record["sha256"]):
        raise ReleaseError("candidate digest is invalid")
    if record.get("signed") is not False:
        raise ReleaseError("candidate manifest must describe unsigned APKs")


def _candidate_records(candidate: dict[str, Any], policy: dict[str, Any]) -> list[dict[str, Any]]:
    records = candidate.get("modules")
    modules = {str(module["role"]): module for module in policy["modules"]}
    if candidate.get("schema") != 1 or not isinstance(records, list):
        raise ReleaseError("candidate manifest schema is invalid")
    if len(records) != len(modules) or not all(isinstance(record, dict) for record in records):
        raise ReleaseError("candidate does not contain every required module")
    roles = [str(record.get("role", "")) for record in records]
    if len(set(roles)) != len(roles) or set(roles) != set(modules):
        raise ReleaseError("candidate module roles are missing or duplicated")
    for record in records:
        _validate_candidate_record(record, modules[str(record["role"])])
    return records


def _sign(
    source: Path,
    destination: Path,
    keystore: Path,
    alias: str,
    store_password: Path,
    key_password: Path,
) -> None:
    aligned = destination.with_suffix(".aligned.apk")
    _run([str(_tool("zipalign")), "-p", "-f", "4", str(source), str(aligned)])
    _run(
        [
            str(_tool("apksigner")),
            "sign",
            "--ks",
            str(keystore),
            "--ks-key-alias",
            alias,
            "--ks-pass",
            f"file:{store_password}",
            "--key-pass",
            f"file:{key_password}",
            "--v1-signing-enabled",
            "false",
            "--v2-signing-enabled",
            "true",
            "--v3-signing-enabled",
            "true",
            "--v4-signing-enabled",
            "false",
            "--out",
            str(destination),
            str(aligned),
        ]
    )
    aligned.unlink()


def _little_orbit_manifest(records: list[dict[str, Any]], certificate: str) -> dict[str, Any]:
    by_role = {str(record["role"]): record for record in records}
    phone = by_role["phone"]
    wear = by_role["wear"]
    return {
        "Version": phone["version_name"],
        "PhoneVersionCode": phone["version_code"],
        "WearVersionCode": wear["version_code"],
        "PhoneApk": phone["file"],
        "PhoneSha256": phone["sha256"],
        "PhoneSizeBytes": phone["bytes"],
        "WearApk": wear["file"],
        "WearSha256": wear["sha256"],
        "WearSizeBytes": wear["bytes"],
        "CertificateSha256": certificate,
        "NotificationTransport": "self-hosted-wss-polling",
    }


def _sign_record(
    record: dict[str, Any],
    module: dict[str, Any],
    candidate_dir: Path,
    work: Path,
    policy: dict[str, Any],
    keystore: Path,
    alias: str,
    store_password: Path,
    key_password: Path,
    expected_certificate: str,
) -> dict[str, Any]:
    role = str(record["role"])
    source = _validate_candidate(record, candidate_dir)
    filename = str(module["release_name"]).format(version=record["version_name"])
    if Path(filename).name != filename:
        raise ReleaseError("release output filename is unsafe")
    staged = work / filename
    _sign(source, staged, keystore, alias, store_password, key_password)
    if _apk_identity(staged) != (
        record["package"],
        record["version_code"],
        record["version_name"],
    ):
        raise ReleaseError(f"signed {role} APK identity changed")
    _assert_required_feature(staged, module)
    certificate = _signer_digest(staged)
    if certificate != expected_certificate:
        raise ReleaseError(f"signed {role} APK uses the wrong certificate")
    _scan_forbidden(staged, list(policy.get("forbidden_markers", [])))
    return {
        **record,
        "file": filename,
        "bytes": staged.stat().st_size,
        "sha256": _sha256(staged),
        "signed": True,
        "certificate_sha256": certificate,
    }


def sign_candidate(
    policy_path: Path,
    candidate_dir: Path,
    output: Path,
    work: Path,
    keystore: Path,
    store_password: Path,
    alias_file: Path,
    key_password: Path,
    certificate_file: Path | None,
) -> None:
    policy = _read_json(policy_path)
    candidate = _read_json(candidate_dir / "candidate-manifest.json")
    if candidate.get("product") != policy["product"]:
        raise ReleaseError("candidate belongs to a different product")
    records = _candidate_records(candidate, policy)
    _empty_output(output)
    work.mkdir(parents=True, exist_ok=True)
    alias = _read_secret(alias_file, "key alias")
    if not SAFE_VALUE.fullmatch(alias):
        raise ReleaseError("key alias is unsafe")
    expected_certificate = _expected_certificate(policy, certificate_file)
    signed: list[dict[str, Any]] = []
    modules = {str(module["role"]): module for module in policy["modules"]}
    for record in records:
        role = str(record.get("role", ""))
        if role not in modules:
            raise ReleaseError("candidate contains an unexpected module")
        signed.append(
            _sign_record(
                record,
                modules[role],
                candidate_dir,
                work,
                policy,
                keystore,
                alias,
                store_password,
                key_password,
                expected_certificate,
            )
        )
    if policy.get("manifest_format") == "little_orbit":
        manifest = _little_orbit_manifest(signed, expected_certificate)
    else:
        manifest = {
            "schema": 1,
            "product": policy["product"],
            "certificate_sha256": expected_certificate,
            "modules": signed,
        }
    for record in signed:
        shutil.copyfile(work / record["file"], output / record["file"])
        (output / f"{record['file']}.sha256").write_text(
            f"{record['sha256']}  {record['file']}\n", encoding="ascii"
        )
    _write_json(output / "release-manifest.json", manifest)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)
    prepare = subparsers.add_parser("prepare")
    prepare.add_argument("--policy", type=Path, required=True)
    prepare.add_argument("--source", type=Path, required=True)
    prepare.add_argument("--output", type=Path, required=True)
    sign = subparsers.add_parser("sign")
    sign.add_argument("--policy", type=Path, required=True)
    sign.add_argument("--candidate", type=Path, required=True)
    sign.add_argument("--output", type=Path, required=True)
    sign.add_argument("--work", type=Path, required=True)
    sign.add_argument("--keystore", type=Path, required=True)
    sign.add_argument("--store-password", type=Path, required=True)
    sign.add_argument("--key-alias", type=Path, required=True)
    sign.add_argument("--key-password", type=Path, required=True)
    sign.add_argument("--expected-certificate", type=Path)
    return parser


def main() -> int:
    arguments = _parser().parse_args()
    try:
        if arguments.command == "prepare":
            prepare_candidate(arguments.policy, arguments.source, arguments.output)
        else:
            sign_candidate(
                arguments.policy,
                arguments.candidate,
                arguments.output,
                arguments.work,
                arguments.keystore,
                arguments.store_password,
                arguments.key_alias,
                arguments.key_password,
                arguments.expected_certificate,
            )
    except (OSError, ValueError, KeyError, json.JSONDecodeError, zipfile.BadZipFile, ReleaseError) as error:
        print(f"release error: {error}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
