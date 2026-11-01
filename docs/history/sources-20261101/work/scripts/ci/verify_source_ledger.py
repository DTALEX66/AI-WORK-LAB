#!/usr/bin/env python3
"""Verify the WORK-LAB Source Ledger V3 against real local readback."""
from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

try:
    import jsonschema
except ImportError:  # pragma: no cover
    jsonschema = None


ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / ".project/governance" / "source-ledger.json"
SCHEMA = ROOT / ".project/governance" / "contracts" / "source-ledger.schema.json"
FORBIDDEN_DESIGN_TOKENS = ("20-" + "design/open-design", "opendesign-assistance", "open-design-benchmark")


def _git_head(root: Path = ROOT) -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            text=True, encoding="utf-8", errors="replace",
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "UNKNOWN"


def _reviewed_scope_is_unchanged(root: Path, reviewed_commit: str | None, paths: list[str]) -> bool:
    if not reviewed_commit or reviewed_commit == "UNKNOWN" or not paths:
        return False
    result = subprocess.run(
        ["git", "diff", "--quiet", f"{reviewed_commit}..HEAD", "--", *paths],
        cwd=root,
        text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.returncode == 0


def _validate_shape(ledger: dict[str, Any], schema: dict[str, Any]) -> None:
    if jsonschema is not None:
        jsonschema.Draft202012Validator(schema).validate(ledger)
        return
    if ledger.get("schemaVersion") != "work-lab/source-ledger/v4" or ledger.get("ledgerVersion") != 4:
        raise ValueError("source ledger schema identity mismatch")
    if ledger.get("scope") != ["workflow-assistance", "work-lab-observer"]:
        raise ValueError("source ledger scope must contain only Workflow and Observer")


def verify(root: Path = ROOT) -> dict[str, Any]:
    ledger = json.loads((root / LEDGER.relative_to(ROOT)).read_text(encoding="utf-8"))
    schema = json.loads((root / SCHEMA.relative_to(ROOT)).read_text(encoding="utf-8"))
    _validate_shape(ledger, schema)
    entries = ledger["entries"]
    errors: list[str] = []
    statuses: list[dict[str, str]] = []
    head = _git_head(root)
    for entry in entries:
        serialized = json.dumps(entry, ensure_ascii=False, sort_keys=True).lower()
        if any(token in serialized for token in FORBIDDEN_DESIGN_TOKENS):
            errors.append(f"{entry['id']}: Open Design source must not be in active Source Ledger")
        effective = entry["implementationStatus"]
        if entry["implementationStatus"] == "local-verified":
            scoped_paths = list(dict.fromkeys(entry["targetPaths"] + entry["tests"]))
            if not _reviewed_scope_is_unchanged(root, entry.get("reviewedCommit"), scoped_paths):
                effective = "STALE_REVIEW"
            for target in scoped_paths:
                if not (root / target).exists():
                    effective = "BLOCKED_MISSING_TARGET_OR_TEST"
                    errors.append(f"{entry['id']}: missing readback path {target}")
            controls = entry["controls"]
            if controls["network"] or controls["telemetry"] or controls["credentials"]:
                effective = "BLOCKED_UNSAFE_CONTROL"
                errors.append(f"{entry['id']}: local source controls must be offline and credential-free")
        statuses.append({"id": entry["id"], "decision": entry["decisionStatus"], "declared": entry["implementationStatus"], "effective": effective})
    if len(entries) != len({entry["id"] for entry in entries}):
        errors.append("entry ids must be unique")
    if errors:
        raise ValueError("; ".join(errors))
    return {"entries": len(entries), "statuses": statuses, "head": head}


def main() -> int:
    try:
        result = verify()
    except (OSError, json.JSONDecodeError, ValueError, subprocess.CalledProcessError) as exc:
        print(f"SOURCE_LEDGER_FAIL {exc}")
        return 1
    local = sum(item["effective"] == "local-verified" for item in result["statuses"])
    blocked = sum(item["effective"].startswith("BLOCKED") or item["effective"] == "STALE_REVIEW" for item in result["statuses"])
    print(f"SOURCE_LEDGER_PASS entries={result['entries']} local_readback={local} blocked={blocked} scope=workflow,observer")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
