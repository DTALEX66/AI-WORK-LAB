"""
future_candidate_registry validator (GOAL 31 / P2-06).

Machine-SSOT check for the deferred-candidate registry
`.project/governance/future-candidate-registry.json`.

Design (fail-open, like verify_contract_ssot.py):
- Validates every entry against `contracts/future-candidate-registry.schema.json`.
- Enforces the invariants a registry consumer relies on:
    * every candidate status is a known enum value;
    * every candidate has default_enabled == False unless status is PROMOTED
      (a PROMOTED candidate must have promotion evidence in the task register);
    * ids are unique and match ^FUT-\\d{3}$;
    * every candidate names a `blueprint_row` that exists in the landed §16 table,
      and every landed §16 row has at least one candidate (pool coverage);
    * the registry declares no execution authority (governance.production_authorized
      must stay false) so a registry row can never be mistaken for a pilot grant.
  and, since the 2026-10-07 decision pass, the ones that keep a row honest about
  what it knows:
    * a decision (PROMOTE / KEEP_CANDIDATE / REJECT) agreeing with the status word,
      with a reason for a retirement and a blocker for a kept row;
    * an identity verdict — RESOLVED rows carry the org/repo and the licence the
      readback actually returned, AMBIGUOUS and NOT_FOUND rows may not claim one;
    * every `native_evidence` path exists on disk, so "already covered natively"
      and "this is a pilot" are claims about code rather than adjectives;
    * no placeholder text in a trigger, criterion or overlap field.
- Schema-conformance failures are ADVISORY (exit 0 with warnings) so a new field
  in the registry never silently breaks the gate; structural integrity failures
  (duplicate ids, PROMOTED without authorization, non-boolean default_enabled)
  are HARD and fail the gate.

Exit codes: 0 = pass (or advisory warnings only); 1 = hard integrity violation.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / ".project/governance/future-candidate-registry.json"
SCHEMA = REPO / ".project/governance/contracts/future-candidate-registry.schema.json"
BLUEPRINT = REPO / "docs/future/WORK-LAB-BLUEPRINT-20261006.md"

STATUS_ENUM = {"DEFERRED", "PILOT_CANDIDATE", "PILOT", "PROMOTED", "REJECTED"}
DISCOVERY_ENUM = {"RESOLVED", "AMBIGUOUS", "NOT_FOUND"}
ABSORPTION_ENUM = {"NONE", "POC_IN_REPO", "ADAPTER_IN_FLEET", "CONSTRAINT_IN_CODE",
                   "REQUIREMENT_ONLY"}
DECISION_ENUM = {"PROMOTE", "KEEP_CANDIDATE", "REJECT"}
UPSTREAM_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
# Words that let a row look decided while nothing was checked. A placeholder in a
# trigger or criterion is how FUT-030 sat unverifiable for a year and nobody noticed.
PLACEHOLDER_NEEDLES = ("TBD", "not yet assessed", "recorded at DISCOVER")
DECISION_REQUIRED = [
    "discovery", "upstream", "license_spdx", "windows_evidence", "decision",
    "absorption", "native_evidence", "blocker",
]
ID_RE = re.compile(r"^FUT-\d{3}$")
ROW_RE = re.compile(r"^\| (16\.\d{2}) \|", re.M)
REQUIRED = [
    "id", "name", "role", "source", "license", "windows_support",
    "native_overlap", "integration_mode", "permissions", "data_boundary",
    "status", "default_enabled", "pilot_trigger", "promotion_criteria",
    "rejection_reason", "last_verified_at",
]


def blueprint_rows() -> tuple[set[str], str]:
    """The §16 candidate rows as landed in the repository copy of the blueprint.

    The registry used to be checked only against itself, so a source row could go
    unregistered and nothing noticed: the recorded gap was even stated as a count
    difference (19 - 14 = 5) rather than a name-level diff, which hid six rows.
    Landing the table gave the pool an in-repo anchor, so coverage is now checkable.
    """
    if not BLUEPRINT.is_file():
        return set(), f"blueprint landing missing: {BLUEPRINT.name}"
    rows = set(ROW_RE.findall(BLUEPRINT.read_text(encoding="utf-8", errors="replace")))
    if not rows:
        return set(), ("blueprint §16 carries no keyed candidate table; the gate "
                       "cannot check coverage")
    return rows, ""


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def decision_checks(c: dict, cid: str, hard: list[str]) -> None:
    """A pool row may only state what it can point at.

    Three kinds of claim are checked separately: an upstream identity (it must be
    a locatable org/repo and its licence must be what the readback said, not what
    the row would like), a native coverage claim (every cited path must exist on
    disk), and a decision (it must agree with the status word and carry a reason
    or a blocker). Placeholder prose in a trigger or criterion is a hard failure,
    because that is how a row stays unverifiable forever.
    """
    for field in DECISION_REQUIRED:
        if field not in c:
            hard.append(f"{cid}: no {field} - a pool row may not exist without a recorded decision")

    dec = c.get("decision")
    if dec not in DECISION_ENUM:
        hard.append(f"{cid}: decision {dec!r} not in {sorted(DECISION_ENUM)}")
    disc = c.get("discovery")
    if disc not in DISCOVERY_ENUM:
        hard.append(f"{cid}: discovery {disc!r} not in {sorted(DISCOVERY_ENUM)}")
    if c.get("absorption") not in ABSORPTION_ENUM:
        hard.append(f"{cid}: absorption {c.get('absorption')!r} not in {sorted(ABSORPTION_ENUM)}")

    evidence = c.get("native_evidence")
    if not isinstance(evidence, list):
        hard.append(f"{cid}: native_evidence must be a list of repository paths")
        evidence = []
    for path in evidence:
        if not (REPO / str(path)).exists():
            hard.append(f"{cid}: native_evidence path does not exist: {path}")
    if c.get("absorption") not in (None, "NONE") and not evidence:
        hard.append(f"{cid}: absorption={c.get('absorption')} claims code in this repository "
                    "but names no path that shows it")

    upstream = str(c.get("upstream") or "")
    spdx = str(c.get("license_spdx") or "")
    license_word = str(c.get("license") or "")
    if disc == "RESOLVED":
        if not UPSTREAM_RE.match(upstream):
            hard.append(f"{cid}: discovery=RESOLVED but upstream {upstream!r} is not an org/repo")
        if spdx in ("", "NOT_VERIFIED"):
            hard.append(f"{cid}: discovery=RESOLVED requires the licence the readback returned "
                        "(UNKNOWN is a valid answer when the repository has no licence field)")
        if not license_word.startswith(spdx):
            hard.append(f"{cid}: license {license_word!r} disagrees with license_spdx {spdx!r}")
        if "GitHub API readback" not in str(c.get("source") or ""):
            hard.append(f"{cid}: discovery=RESOLVED but source records no readback to rest on")
    else:
        if license_word != "NOT_VERIFIED":
            hard.append(f"{cid}: discovery={disc} cannot carry a verified licence")
        if upstream:
            hard.append(f"{cid}: discovery={disc} must leave upstream empty, found {upstream!r}")
        if c.get("windows_support") == "VERIFIED":
            hard.append(f"{cid}: windows_support=VERIFIED while the upstream was never located")
    if c.get("windows_support") == "VERIFIED" and not str(c.get("windows_evidence") or "").strip():
        hard.append(f"{cid}: windows_support=VERIFIED requires the artifact or command that proved it")

    if dec == "REJECT":
        if c.get("status") != "REJECTED":
            hard.append(f"{cid}: decision=REJECT must be reflected in status=REJECTED")
        reason = str(c.get("rejection_reason") or "")
        if not reason.strip():
            hard.append(f"{cid}: REJECT without a rejection_reason is a deletion dressed as a decision")
        elif not evidence and "discovery=" not in reason:
            hard.append(f"{cid}: REJECT with no native path must say which discovery verdict it rests on")
    if c.get("status") == "REJECTED" and dec != "REJECT":
        hard.append(f"{cid}: status=REJECTED but decision={dec!r} — a retirement needs the matching decision")
    if dec == "PROMOTE" and c.get("status") != "PROMOTED":
        hard.append(f"{cid}: decision=PROMOTE must be reflected in status=PROMOTED")
    if c.get("status") == "PILOT" and c.get("absorption") == "NONE":
        hard.append(f"{cid}: status=PILOT with absorption=NONE — a pilot needs code or a run, not a word")
    if dec == "KEEP_CANDIDATE" and not str(c.get("blocker") or "").strip():
        hard.append(f"{cid}: KEEP_CANDIDATE must name what is blocking it")
    if dec in ("KEEP_CANDIDATE", "PROMOTE") and not str(c.get("decision_basis") or "").strip():
        hard.append(f"{cid}: decision={dec} requires a decision_basis; a kept row must say why the "
                    "native code does not already cover it")

    for field in ("pilot_trigger", "promotion_criteria", "native_overlap", "decision_basis"):
        text = str(c.get(field) or "")
        for needle in PLACEHOLDER_NEEDLES:
            if needle in text:
                hard.append(f"{cid}: {field} still carries the placeholder {needle!r} — "
                            "a row cannot be kept alive by leaving its condition unwritten")
                break



def main() -> int:
    hard_errors: list[str] = []
    warnings: list[str] = []
    rows: set[str] = set()
    claimed: set[str] = set()

    if not REGISTRY.exists():
        hard_errors.append("registry missing: " + REGISTRY.name)
    else:
        reg = load_json(REGISTRY)

        if reg.get("schemaVersion") != "work-lab/future-candidate-registry/v1":
            warnings.append(f"schemaVersion={reg.get('schemaVersion')!r} (expected v1)")

        gov = reg.get("governance", {})
        if gov.get("production_authorized") is not False:
            hard_errors.append(
                "governance.production_authorized must stay false (registry grants no pilot authority)"
            )
        if gov.get("default_enabled") is not False:
            hard_errors.append(
                "governance.default_enabled must stay false (no candidate auto-enabled)"
            )
        if sorted(gov.get("decisions") or []) != sorted(DECISION_ENUM):
            hard_errors.append(
                f"governance.decisions {gov.get('decisions')!r} does not equal the vocabulary "
                f"the gate enforces {sorted(DECISION_ENUM)}"
            )

        seen_ids: set[str] = set()
        for c in reg.get("candidates", []):
            cid = c.get("id", "<no-id>")
            if not ID_RE.match(cid):
                hard_errors.append(f"candidate {cid}: id does not match ^FUT-\\d{{3}}$")
            if cid in seen_ids:
                hard_errors.append(f"duplicate candidate id {cid}")
            seen_ids.add(cid)

            missing = [k for k in REQUIRED if k not in c]
            if missing:
                warnings.append(f"{cid}: missing fields {missing}")

            if c.get("status") not in STATUS_ENUM:
                hard_errors.append(f"{cid}: status {c.get('status')!r} not in {sorted(STATUS_ENUM)}")

            de = c.get("default_enabled")
            if not isinstance(de, bool):
                hard_errors.append(f"{cid}: default_enabled must be boolean, got {type(de).__name__}")
            elif de and c.get("status") != "PROMOTED":
                hard_errors.append(
                    f"{cid}: default_enabled=true is only allowed when status=PROMOTED"
                )

            if c.get("status") == "PROMOTED":
                task_card = c.get("task_card")
                if not task_card:
                    hard_errors.append(
                        f"{cid}: PROMOTED requires a task_card path (promotion evidence in the register)"
                    )
                elif REPO.exists():
                    tc = REPO / task_card
                    if not tc.exists():
                        hard_errors.append(f"{cid}: task_card path missing: {task_card}")

            decision_checks(c, cid, hard_errors)

        # Row coverage: every landed §16 candidate row needs a registry claimant,
        # and every claimant must name a row that exists. This is the invariant
        # whose absence let six rows go unregistered.
        rows, rows_error = blueprint_rows()
        if rows_error:
            hard_errors.append(rows_error)
        claimed: set[str] = set()
        for c in reg.get("candidates", []):
            cid = c.get("id", "<no-id>")
            row = c.get("blueprint_row")
            if not isinstance(row, str) or not row:
                hard_errors.append(
                    f"{cid}: no blueprint_row — every candidate must name the §16 "
                    "source row it answers to")
                continue
            if row not in rows:
                hard_errors.append(
                    f"{cid}: blueprint_row {row!r} is not a landed §16 row")
                continue
            claimed.add(row)
        unclaimed = sorted(rows - claimed)
        if unclaimed:
            hard_errors.append(
                f"blueprint §16 rows with no registry candidate: {unclaimed} — "
                "register the candidate or retire the row with a reason; a count "
                "difference (19 - 14) is not coverage")

    # schema conformance is advisory
    if SCHEMA.exists():
        try:
            import jsonschema  # type: ignore
            schema = load_json(SCHEMA)
            reg = load_json(REGISTRY)
            errs = sorted(jsonschema.Draft202012Validator(schema).iter_errors(reg), key=str)
            for e in errs:
                warnings.append(f"schema: {e.message}")
        except Exception as exc:  # jsonschema absent or registry unreadable
            warnings.append(f"schema conformance skipped ({exc.__class__.__name__})")

    if warnings:
        print("FUTURE_CANDIDATE_REGISTRY_ADVISORY")
        for w in warnings:
            print("  - " + w)

    if hard_errors:
        print("FUTURE_CANDIDATE_REGISTRY_INTEGRITY_FAIL")
        for e in hard_errors:
            print("  ! " + e)
        return 1

    final = load_json(REGISTRY).get("candidates", []) if REGISTRY.exists() else []
    decided = {}
    located = {}
    for c in final:
        decided[c.get("decision", "?")] = decided.get(c.get("decision", "?"), 0) + 1
        located[c.get("discovery", "?")] = located.get(c.get("discovery", "?"), 0) + 1
    print("FUTURE_CANDIDATE_REGISTRY_PASS candidates=%d blueprint_rows=%d claimed_rows=%d "
          "decisions=%s discovery=%s"
          % (len(final), len(rows), len(claimed),
             ",".join(f"{k}:{v}" for k, v in sorted(decided.items())),
             ",".join(f"{k}:{v}" for k, v in sorted(located.items()))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
