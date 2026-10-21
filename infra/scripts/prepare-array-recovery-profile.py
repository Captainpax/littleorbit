#!/usr/bin/env python3
"""Read-only operator preparation; bounded rendered Compose JSON on stdin only.

No subprocess, Docker API, lifecycle, copy, mount, pull or filesystem mutation.
The expanded model may contain secret URLs: never write it to disk or tee/log it.
Input contract is image IDs, numeric identities/resources and GPU metadata only.
This does not solve the target's missing-Python execution gap or enable Docker.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
from pathlib import Path
import sys
import types

sys.path.insert(0, str(Path(__file__).resolve().parent))
from array_recovery_profile import ProfileError, validate_model

CORE_SHA256 = "e9489a4eefcae1f3e99ff34272215eee20c47882fb1b3edebbccc04b6f709985"
MAX_MODEL_BYTES = 2 * 1024**2


def load_core(path: Path) -> types.ModuleType:
    if path.is_symlink() or not path.is_file() or path.stat().st_size > 64 * 1024:
        raise ProfileError("Unsafe admission core")
    with path.open("rb") as handle:
        payload = handle.read(64 * 1024 + 1)
    if hashlib.sha256(payload).hexdigest() != CORE_SHA256:
        raise ProfileError("Admission core seal differs; review the revision")
    module = types.ModuleType("pinned_array_admission")
    exec(compile(payload, str(path), "exec"), module.__dict__)
    return module


def prepare(core: types.ModuleType, manifest: dict, model: dict, contract: dict) -> dict:
    admission = core.admit(manifest, dt.datetime.now(dt.timezone.utc))
    result = validate_model(model, contract)
    result["admissionStage"] = admission["stage"]
    result["observationAt"] = admission["observationAt"]
    result["budget"] = admission["budget"]
    result["pendingGates"] = sorted(set(result["pendingGates"]) | set(admission["pendingAcceptanceGates"]))
    return result


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--admission-core", type=Path, default=Path(__file__).with_name("array_recovery_admission.py"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--manifest-sha256", required=True)
    parser.add_argument("--contract", type=Path, required=True)
    parser.add_argument("--contract-sha256", required=True)
    parser.add_argument("--model-stdin-sha256", required=True)
    return parser.parse_args()


def main() -> int:
    import json

    args = arguments()
    try:
        core = load_core(args.admission_core)
        manifest, _ = core.read_sealed_json(args.manifest, args.manifest_sha256)
        contract, _ = core.read_sealed_json(args.contract, args.contract_sha256)
        payload = sys.stdin.buffer.read(MAX_MODEL_BYTES + 1)
        if not 0 < len(payload) <= MAX_MODEL_BYTES or hashlib.sha256(payload).hexdigest() != args.model_stdin_sha256:
            raise ProfileError("Bounded stdin model seal differs")
        model = core.decode_json(payload)
        result = prepare(core, manifest, model, contract)
        print(json.dumps(result, sort_keys=True, separators=(",", ":")))
        return 0
    except Exception:
        # Never stringify third-party/parser exceptions carrying expanded config.
        print('{"stage":"BLOCKED_PRESERVE_EVIDENCE","error":"Read-only profile preparation failed"}', file=sys.stderr)
        return 78


if __name__ == "__main__":
    raise SystemExit(main())
