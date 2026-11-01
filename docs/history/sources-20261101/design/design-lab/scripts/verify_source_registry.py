#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-KNW-004: strict fail-closed source registry verifier (replaces verify_source_registry_v2.py).

Validates the v3 SOURCE_REGISTRY (SourceRecord-wrapped entries) and the
QUARANTINE_REGISTRY under Draft 2020-12 JSON Schema. No compatibility
fallback: any missing/invalid field is a hard failure.

Checks:
1. SOURCE_REGISTRY v3 envelope + every entry.source validates against
   source-record.schema.json (Draft 2020-12, additionalProperties=false).
2. integration mode/status enums and required fields.
3. Git sources (origin on a known git host) must pin a full 40-char commit SHA.
4. contentHash must be sha256:<64hex> (commit SHAs never masquerade as content hashes).
5. licenseStatus unknown/reference-only must not use runtime modes
   (adapter / vendor-adapt).
6. Quarantine content must not appear in the capability index.
7. modelInputAllowed=false must not enter generation context.
8. commercialUse=false must not enter commercial production packs.
9. QUARANTINE_REGISTRY validates against quarantine-registry.schema.json.

Exit is non-zero unless SCHEMA_ERRORS=0, GOVERNANCE_GAPS=0 and
RUNTIME_RIGHTS_VIOLATIONS=0.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "research" / "global-absorption" / "SOURCE_REGISTRY.json"
QUARANTINE = ROOT / "research" / "global-absorption" / "QUARANTINE_REGISTRY.json"
SOURCE_RECORD_SCHEMA = ROOT / "schemas" / "source-record.schema.json"
REGISTRY_SCHEMA = ROOT / "schemas" / "source-registry.schema.json"
QUARANTINE_SCHEMA = ROOT / "schemas" / "quarantine-registry.schema.json"
CAPABILITY_INDEX = ROOT / "config" / "capability-index.json"
EVIDENCE_INDEX = ROOT / "config" / "capability-evidence-index.json"
# The vendor lock lives at the repository root, one level above design-lab/.
VENDOR_LOCK = ROOT.parent / "vendor" / "sources.lock.json"

GIT_SHA40 = re.compile(r"^[0-9a-f]{40}$")
SHA256 = re.compile(r"^sha256:[0-9a-f]{64}$")
GIT_HOSTS = ("github.com", "gitlab.com", "bitbucket.org", "codeberg.org", "gitee.com")
RUNTIME_MODES = {"adapter", "vendor-adapt"}
VALID_MODES = {"vendor-adapt", "adapter", "derive", "reference", "quarantine"}
VALID_STATUS = {"active", "reference-only", "review-required"}


def load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def is_git_origin(origin: str) -> bool:
    return origin.startswith("git@") or any(h in origin for h in GIT_HOSTS)



def validate_rights(src: dict, integration: dict) -> list[str]:
    """DL-KNW-004 rights-consistency checks for one SourceRecord.

    Returns violations:
    - reviewer must be a human (no auto/agent/generated/bot markers);
    - licenseStatus unknown/reference-only must not enable model input;
    - licenseStatus unknown/reference-only must not use runtime modes;
    - git origins must pin a full 40-char commit SHA;
    - contentHash must be sha256:<64hex>.
    """
    findings: list[str] = []
    source_id = src.get("sourceId", "?")
    if not src.get("reviewedBy") or not src.get("reviewedAt"):
        findings.append(f"{source_id}: reviewedBy/reviewedAt required; legacy reviewed_at cannot substitute (DL-KNW-001)")
    reviewer = str(src.get("reviewedBy", "") or "")
    if re.search(r"(auto|generated|automated|bot|agent)", reviewer, re.IGNORECASE):
        findings.append(f"{source_id}: reviewedBy looks machine-generated: {reviewer!r}")
    license_status = src.get("licenseStatus")
    mode = integration.get("mode")
    if license_status in ("unknown", "reference-only") and src.get("modelInputAllowed") is True:
        findings.append(f"{source_id}: licenseStatus={license_status} must not enable model input")
    if license_status in ("unknown", "reference-only") and mode in RUNTIME_MODES:
        findings.append(f"{source_id}: licenseStatus={license_status} must not use runtime mode {mode}")
    if is_git_origin(src.get("origin", "")) and not GIT_SHA40.match(src.get("version", "")):
        findings.append(f"{source_id}: git origin requires full 40-char version SHA")
    if not SHA256.match(src.get("contentHash", "")):
        findings.append(f"{source_id}: contentHash must be sha256:<64hex>")
    return findings


def vendor_lock_findings(lock_path: Path | None = None) -> list[str]:
    """An absent vendor reference may stay only as a *declared* historical reference.

    `vendor/sources.lock.json` lists 46 sources; 6 of them point at directories deleted
    on 2026-09-04, and until 2026-10-08 `SOURCE_REGISTRY=PASS` said nothing about that --
    two of the six looked "backed" only because the isolation record listed a *file* inside
    them and the check was a substring. Presence is measured by
    `scripts/amend_source_lock_presence.py` and committed here, so this gate's job is the
    other half: refuse a dangling reference, a missing content identity, a license claim
    that disagrees with the record inside the retired tree, and a revision invented rather
    than declared.
    """
    path = lock_path or VENDOR_LOCK
    try:
        lock = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return [f"vendor sources.lock.json unreadable: {exc}"]
    audit = lock.get("presenceAudit") or {}
    if audit.get("schemaVersion") != "design-lab/vendor-presence/v1":
        return [f"vendor lock has no presence audit (schemaVersion "
                f"{audit.get('schemaVersion')!r}) — run scripts/amend_source_lock_presence.py"]
    findings: list[str] = []
    for source in lock.get("sources") or []:
        if source.get("presence") != "ABSENT_FROM_GIT":
            continue
        sid = source.get("id", "?")
        path_str = str(source.get("path") or "")
        if not source.get("pathNamedInIsolationRecord"):
            findings.append(f"{sid}: absent from git with no retirement declaration naming "
                            f"`{path_str}` in docs/THIRD_PARTY_ISOLATION.md")
        for field in ("retiredIn", "retiredTreeSha"):
            value = str(source.get(field) or "")
            if not re.fullmatch(r"[0-9a-f]{7,40}", value):
                findings.append(f"{sid}: {field} is {value!r}, not a commit/tree sha read "
                                f"from git history")
        if not str(source.get("upstreamRepo") or "").startswith("https://"):
            findings.append(f"{sid}: no upstream URL recovered from the retired tree's "
                            f"SOURCE.md, so the reference cannot be re-acquired or audited")
        if not source.get("sourceRecordPresent") and not str(source.get("provenanceAbsentReason") or "").strip():
            findings.append(f"{sid}: retired tree carries no SOURCE.md and states no reason "
                            f"— silence is not a declaration")
        # One field carries the whole answer, and it is generated from the retired record
        # rather than typed by whoever edits the lock: commit / branch-only / never-recorded
        # are all acceptable, an empty string is not.
        statement = str(source.get("revisionStatement") or "").strip()
        if not statement:
            findings.append(f"{sid}: no revisionStatement — the lock must say whether a commit "
                            f"was pinned, only a branch was named, or neither was recorded")
        elif re.fullmatch(r"commit [0-9a-f]{7,40} recorded in SOURCE\.md", statement)                 and not re.fullmatch(r"[0-9a-f]{7,40}", str(source.get("upstreamRevision") or "")):
            findings.append(f"{sid}: revisionStatement claims a commit but upstreamRevision "
                            f"is {source.get('upstreamRevision')!r}")
    for key in ("absentReferencesNotNamedInIsolationRecord", "licenseRecordMismatch"):
        value = audit.get(key)
        if value:
            findings.append(f"presenceAudit.{key} is not empty: {value}")
    return findings


def main() -> int:
    errors: list[str] = []
    gaps: list[str] = []
    violations: list[str] = []

    # ---- schemas ----
    source_record_schema = load_json(SOURCE_RECORD_SCHEMA)
    quarantine_schema = load_json(QUARANTINE_SCHEMA)
    try:
        jsonschema.Draft202012Validator.check_schema(source_record_schema)
    except Exception as exc:
        print("SCHEMA_ERRORS=1")
        print(f"  invalid source-record.schema.json: {exc}")
        return 1

    # ---- registry ----
    try:
        reg = load_json(REGISTRY)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"SOURCE_REGISTRY=FAIL registry unreadable: {exc}")
        print("SCHEMA_ERRORS=1")
        print("GOVERNANCE_GAPS=1")
        print("RUNTIME_RIGHTS_VIOLATIONS=1")
        return 1

    if reg.get("schemaVersion") != "design-lab/source-registry/v3":
        errors.append(f"schemaVersion must be design-lab/source-registry/v3, got {reg.get('schemaVersion')!r}")

    record_validator = jsonschema.Draft202012Validator(source_record_schema)
    entries = reg.get("entries", [])
    for i, entry in enumerate(entries):
        prefix = f"entry[{i}]"
        if not isinstance(entry, dict) or "source" not in entry or "integration" not in entry:
            errors.append(f"{prefix}: must wrap {{source, integration}}")
            continue
        src = entry["source"]
        verrors = sorted(record_validator.iter_errors(src), key=lambda e: list(e.path))
        if verrors:
            for ve in verrors:
                where = "/".join(str(p) for p in ve.path) or "$"
                errors.append(f"{prefix} source.{where}: {ve.message}")
        integration = entry["integration"]
        mode = integration.get("mode")
        status = integration.get("status")
        if mode not in VALID_MODES:
            errors.append(f"{prefix} integration.mode invalid: {mode!r}")
        if status not in VALID_STATUS:
            errors.append(f"{prefix} integration.status invalid: {status!r}")
        if "target" in integration and not isinstance(integration["target"], str):
            errors.append(f"{prefix} integration.target must be string")
        # An `active` absorption claims the destination exists in the repo. Before
        # this line only checked the target was a string, so all six active
        # entries kept passing after DL-DIR-MIG-R1 (c9cde8a5) deleted the whole
        # design-lab/knowledge tree they pointed into. Existence is the claim.
        if status == "active" and isinstance(integration.get("target"), str):
            target = integration["target"]
            if target and not (ROOT.parent / target).exists():
                errors.append(
                    f"{prefix} integration.status=active but target is missing: {target}")

        # ---- governance checks (only for schema-clean entries) ----
        if verrors:
            continue
        source_id = src.get("sourceId", "?")
        origin = src.get("origin", "")
        version = src.get("version", "")
        content_hash = src.get("contentHash", "")
        license_status = src.get("licenseStatus")
        if is_git_origin(origin) and not GIT_SHA40.match(version):
            gaps.append(f"{prefix} {source_id}: git origin requires full 40-char version SHA, got {version!r}")
        if not SHA256.match(content_hash):
            gaps.append(f"{prefix} {source_id}: contentHash must be sha256:<64hex>, got {content_hash!r}")
        if license_status in ("unknown", "reference-only") and mode in RUNTIME_MODES:
            violations.append(f"{prefix} {source_id}: licenseStatus={license_status} must not use runtime mode {mode}")
        if src.get("modelInputAllowed") is False:
            # generation-context indexes must not reference this sourceId
            for idx_name, idx_path in (("capability-evidence-index", EVIDENCE_INDEX), ("capability-index", CAPABILITY_INDEX)):
                try:
                    text = idx_path.read_text(encoding="utf-8")
                except OSError:
                    continue
                if source_id in text:
                    violations.append(f"{prefix} {source_id}: modelInputAllowed=false found in {idx_name}")
        if src.get("commercialUse") is False:
            prod_root = ROOT / "production"
            if prod_root.exists():
                for p in prod_root.rglob("*"):
                    if p.is_file() and p.suffix.lower() in (".json", ".md", ".yaml", ".yml"):
                        try:
                            if source_id in p.read_text(encoding="utf-8", errors="ignore"):
                                violations.append(f"{prefix} {source_id}: commercialUse=false found in production pack {p.relative_to(ROOT)}")
                        except OSError:
                            pass

    # ---- quarantine not in capability index ----
    try:
        cap = load_json(CAPABILITY_INDEX)
        for c in cap.get("capabilities", []):
            path = c.get("path", "")
            if path.startswith("research/quarantine/") or path.startswith("research/global-absorption/"):
                violations.append(f"quarantine content in capability index: {path}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"capability-index.json unreadable: {exc}")

    # ---- quarantine registry validation ----
    try:
        qreg = load_json(QUARANTINE)
        if qreg.get("schemaVersion") != "design-lab/quarantine-registry/v1":
            errors.append(f"quarantine schemaVersion invalid: {qreg.get('schemaVersion')!r}")
        qvalidator = jsonschema.Draft202012Validator(quarantine_schema)
        for verr in sorted(qvalidator.iter_errors(qreg), key=lambda e: list(e.path)):
            where = "/".join(str(p) for p in verr.path) or "$"
            errors.append(f"quarantine {where}: {verr.message}")
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"QUARANTINE_REGISTRY unreadable: {exc}")

    presence_errors = vendor_lock_findings()
    if presence_errors:
        errors.extend(presence_errors)

    schema_errors = len(errors)
    governance_gaps = len(gaps)
    rights_violations = len(violations)

    print(f"SOURCES={len(entries)}")
    print(f"SCHEMA_ERRORS={schema_errors}")
    print(f"GOVERNANCE_GAPS={governance_gaps}")
    print(f"RUNTIME_RIGHTS_VIOLATIONS={rights_violations}")
    for e in errors[:20]:
        print("ERROR:", e)
    for g in gaps[:20]:
        print("GAP  :", g)
    for v in violations[:20]:
        print("VIOL :", v)
    if schema_errors or governance_gaps or rights_violations:
        print("SOURCE_REGISTRY=FAIL")
        return 1
    print("SOURCE_REGISTRY=PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
