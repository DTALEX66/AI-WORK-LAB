from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator


INTERFACE = ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"]


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def digest_files(root: Path, files: list[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(files):
        path = (root / relative).resolve()
        if not path.is_file() or root.resolve() not in path.parents:
            raise ValueError(f"hash file is missing or outside root: {relative}")
        digest.update(relative.replace("\\", "/").encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def verify(registry_path: Path, schema_path: Path, root: Path) -> tuple[int, str]:
    try:
        registry = load_json(registry_path)
        schema = load_json(schema_path)
    except (OSError, json.JSONDecodeError) as exc:
        return 2, f"ADAPTER_REGISTRY_FAIL cannot read input: {exc}"
    errors = sorted(Draft202012Validator(schema).iter_errors(registry), key=lambda error: list(error.path))
    if errors:
        return 2, "ADAPTER_REGISTRY_FAIL " + "; ".join(error.message for error in errors[:5])
    if registry["interface"] != INTERFACE:
        return 2, "ADAPTER_REGISTRY_FAIL interface drift"
    ids = [entry["id"] for entry in registry["entries"]]
    if len(ids) != len(set(ids)):
        return 2, "ADAPTER_REGISTRY_FAIL duplicate adapter id"
    unavailable = 0
    available = 0
    for entry in registry["entries"]:
        provenance = entry["provenance"]
        package_hash = provenance["hash"]
        if package_hash["state"] == "UNAVAILABLE":
            unavailable += 1
            if package_hash["value"] is not None:
                return 2, f"ADAPTER_REGISTRY_FAIL unavailable hash has value: {entry['id']}"
            if entry["detection"]["evidence_state"] not in {"UNVERIFIED", "BLOCKED", "SKIPPED_OPTIONAL"}:
                return 2, f"ADAPTER_REGISTRY_FAIL unavailable hash overstated as verified: {entry['id']}"
            continue
        available += 1
        if not package_hash["files"]:
            return 2, f"ADAPTER_REGISTRY_FAIL available hash has no files: {entry['id']}"
        observed = digest_files(root, package_hash["files"])
        if observed != package_hash["value"]:
            return 2, f"ADAPTER_REGISTRY_FAIL hash mismatch: {entry['id']}"
    return 0, (
        f"ADAPTER_REGISTRY_PASS entries={len(ids)} available_hash={available} "
        f"hash_unavailable={unavailable} explicit_quarantine=true"
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--registry", type=Path, required=True)
    parser.add_argument("--schema", type=Path, required=True)
    parser.add_argument("--root", type=Path, required=True)
    args = parser.parse_args()
    code, message = verify(args.registry, args.schema, args.root.resolve())
    print(message)
    return code


if __name__ == "__main__":
    raise SystemExit(main())
