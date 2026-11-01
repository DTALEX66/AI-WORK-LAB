"""Final audit (WL-430 / ch 42 + ch 44 item 20): the G01-G14 gate set.

ch 42 defines fourteen acceptance gates, G01..G14, and one rule that
trumps all of them::

    any single gate failing -> Promotion is forbidden.

This is the final audit of the Phase-1 (and whole taskpack) done-when:
ch 44 item 20 is "G01-G14 PASS".  Each gate is evaluated from evidence the
caller supplies — a gate with NO evidence is PENDING, never a guessed
PASS (the honest default), and a gate whose evidence is negative is FAIL.
Promotion is allowed only when all fourteen are PASS.

Gates that are live-environment dependent (CI green, secret scan, Windows
run) report their status exactly as the evidence says; when that evidence
has not been produced, the gate is PENDING so a later run can close it —
this module does not fabricate a green.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional


class GateStatus:
    PASS = "PASS"
    FAIL = "FAIL"
    PENDING = "PENDING"

    _MEMBERS = frozenset({PASS, FAIL, PENDING})


class Gate:
    """The fourteen ch 42 gates, with a one-line meaning each."""

    G01 = ("G01", "repo_clean", "no stray / out-of-bound files; spill + size clean")
    G02 = ("G02", "ci_green", "workflows green on the target SHA")
    G03 = ("G03", "license_verified", "licenses verified against policy")
    G04 = ("G04", "secret_scan", "no leaked secrets / credentials")
    G05 = ("G05", "runtime_boundary", "project data stays inside its runtime root")
    G06 = ("G06", "zero_spill", "no data spilled outside sanctioned roots")
    G07 = ("G07", "windows", "verified to run on Windows")
    G08 = ("G08", "rollback", "a rollback path exists and was exercised")
    G09 = ("G09", "evidence_complete", "every claim is backed by cited evidence")
    G10 = ("G10", "independent_acceptance", "an independent authority accepted it")
    G11 = ("G11", "security", "security gate passed")
    G12 = ("G12", "cost", "cost within budget")
    G13 = ("G13", "performance", "performance within baseline")
    G14 = ("G14", "ssot_docs", "SSOT / docs are consistent")

    ALL = [
        G01, G02, G03, G04, G05, G06, G07, G08,
        G09, G10, G11, G12, G13, G14,
    ]
    _BY_ID = {g[0]: g for g in ALL}
    _COUNT = len(ALL)   # 14


@dataclass
class GateResult:
    gate_id: str
    name: str
    status: str
    note: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class FinalAudit:
    """Evaluates the fourteen gates from per-gate evidence."""

    SCHEMA = "work-lab/final-audit/v1"

    def __init__(self, evidence: Optional[Dict[str, Any]] = None) -> None:
        # evidence[gate_id] = {"pass": bool, "note": str}  (optional)
        self._evidence = evidence or {}

    def evaluate_gate(self, gate_id: str) -> GateResult:
        gate = Gate._BY_ID.get(gate_id)
        if gate is None:
            return GateResult(gate_id, "unknown", GateStatus.FAIL,
                              "unknown gate id")
        _gid, name, meaning = gate
        ev = self._evidence.get(gate_id)
        if ev is None:
            # no evidence -> honest PENDING, never a guessed PASS
            return GateResult(gate_id, name, GateStatus.PENDING,
                              "no evidence supplied; gate not closed")
        ok = bool(ev.get("pass", False))
        note = ev.get("note", "")
        status = GateStatus.PASS if ok else GateStatus.FAIL
        return GateResult(gate_id, name, status,
                          note or (meaning if ok else f"failed: {meaning}"))

    def run(self) -> Dict[str, Any]:
        results = [self.evaluate_gate(g[0]) for g in Gate.ALL]
        by_id = {r.gate_id: r for r in results}
        passed = [r.gate_id for r in results if r.status == GateStatus.PASS]
        failed = [r.gate_id for r in results if r.status == GateStatus.FAIL]
        pending = [r.gate_id for r in results if r.status == GateStatus.PENDING]
        all_pass = not failed and not pending
        return {
            "schema": self.SCHEMA,
            "gate_count": Gate._COUNT,
            "pass_count": len(passed),
            "results": [r.to_dict() for r in results],
            "passed": passed,
            "failed": failed,
            "pending": pending,
            "all_pass": all_pass,
            "promotion_allowed": self.promotion_allowed(all_pass),
        }

    @staticmethod
    def promotion_allowed(all_pass: bool) -> bool:
        """ch 42: a single failing (or still-pending) gate forbids
        promotion.  Only 14/14 PASS opens it."""
        return bool(all_pass)

    def receipt_sha256(self, report: Optional[Dict[str, Any]] = None) -> str:
        import hashlib
        report = report if report is not None else self.run()
        payload = json.dumps(
            {k: report[k] for k in
             ("gate_count", "pass_count", "results", "all_pass",
              "promotion_allowed")},
            sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def all_pass_evidence() -> Dict[str, Any]:
    """A fully-closing evidence set: PASS on all fourteen gates.  Tests use
    this to prove the 14/14 path; production builds it from real gate
    evidence, and any gate left without evidence stays PENDING."""
    return {gid: {"pass": True, "note": "evidenced"}
            for gid, _n, _m in Gate.ALL}
