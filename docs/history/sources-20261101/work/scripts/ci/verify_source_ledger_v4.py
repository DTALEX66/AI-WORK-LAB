"""WLOSS-000: OSS intake ledger verification.

Validates .project/governance/source-ledger.json against the intake contract:
- schemaVersion is the current v4;
- integrationMode ∈ {VENDOR, DEPENDENCY, EXTERNAL_TOOL, ADAPTER, DERIVE,
  REFERENCE, QUARANTINE, REJECT};
- every entry carries the full intake fields (canonicalUrl, reviewedCommit or
  reviewedTag, license fields, controls, freshness, rollback);
- an entry with freshness=review-required or UNKNOWN license must NOT be
  claimed as integrated (implementationStatus stays not-implemented) — the
  License + Revision review gates the execution chain.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

LEDGER_REL = Path(".project/governance/source-ledger.json")
INTEGRATION_MODES = {"VENDOR", "DEPENDENCY", "EXTERNAL_TOOL", "ADAPTER", "DERIVE", "REFERENCE", "QUARANTINE", "REJECT"}
REQUIRED_FIELDS = (
    "id", "canonicalUrl", "license", "spdx", "codeLicense", "modelDataLicense",
    "windowsSupport", "runtimeWeight", "integrationMode", "freshness", "rollback",
    "controls", "owner",
)
CONTROL_FIELDS = ("network", "telemetry", "credentials", "scripts")


def find_root() -> Path:
    current = Path.cwd()
    for _ in range(6):
        if (current / LEDGER_REL).is_file():
            return current
        if current.parent == current:
            break
        current = current.parent
    raise FileNotFoundError("cannot locate WORK-LAB root")


def verify() -> dict[str, object]:
    root = find_root()
    path = root / LEDGER_REL
    errors: list[str] = []
    warnings: list[str] = []

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {"valid": False, "errors": [f"ledger unreadable: {exc}"], "warnings": [], "entries": 0}

    if data.get("schemaVersion") != "work-lab/source-ledger/v4":
        errors.append("schemaVersion must be work-lab/source-ledger/v4")

    entries = data.get("entries")
    if not isinstance(entries, list) or not entries:
        errors.append("entries must be a non-empty list")
        return {"valid": not errors, "errors": errors, "warnings": warnings, "entries": len(entries) if isinstance(entries, list) else 0}

    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            errors.append(f"entries[{index}] must be an object")
            continue
        eid = entry.get("id")
        if not isinstance(eid, str) or not eid:
            errors.append(f"entries[{index}].id required")
        elif eid in seen:
            warnings.append(f"duplicate id {eid!r}")
        else:
            seen.add(eid)

        for field in REQUIRED_FIELDS:
            if field not in entry:
                errors.append(f"{eid or f'entries[{index}]'}.{field} missing")

        mode = entry.get("integrationMode")
        if mode not in INTEGRATION_MODES:
            errors.append(f"{eid}.integrationMode {mode!r} not in allowed set")

        controls = entry.get("controls")
        if not isinstance(controls, dict):
            errors.append(f"{eid}.controls must be an object")
        else:
            for control in CONTROL_FIELDS:
                if control not in controls:
                    errors.append(f"{eid}.controls.{control} missing")

        freshness = entry.get("freshness", "")
        implementation = entry.get("implementationStatus", "")
        if freshness in ("review-required", "unknown") and implementation not in ("not-implemented",):
            errors.append(f"{eid} claims {implementation} but freshness={freshness} (License+Revision review gates execution)")

    return {"valid": not errors, "errors": errors, "warnings": warnings, "entries": len(entries)}


if __name__ == "__main__":
    report = verify()
    print(json.dumps({k: v for k, v in report.items()}, ensure_ascii=False, indent=2))
    print(f"SOURCE_LEDGER {'PASS' if report['valid'] else 'FAIL'} entries={report['entries']}")
    raise SystemExit(0 if report["valid"] else 1)
