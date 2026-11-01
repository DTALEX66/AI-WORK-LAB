# SPDX-License-Identifier: MIT
"""DL-CLOUD-2026-09-25 Prompt I: the Quality->Jury->Rights->Preflight->Handoff
readiness combiner's acceptance cases, plus the RIGHTS band fail-closed cases.

The combiner is a pure backend decision layer (see
:mod:`design_lab.assurance.handoff_readiness`). These fixtures exercise the
closed vocabulary of the four existing contracts -- the sealed QualityRecord,
the rights-registry states the combiner classifies, the preflight check model,
and the commercial handoff -- and pin the acceptance cases the audit enumerates:

* an automated judge's high score never unblocks a human REJECT;
* a rights ``FORBIDDEN``/``NOT_ADJUDICATED`` field blocks;
* a missing-font preflight blocker blocks;
* a stale artifact hash blocks;
* a re-open failure (a failing reopen-readback preflight check) blocks;
* the all-pass case reaches READY_FOR_HANDOFF;
* the UI signals (BLOCKER band) mirror the backend decision exactly.

``RightsBandFailClosedTests`` pins the case the audit found by reading the band table against
the registry file: a rights state the table cannot classify must BLOCK, because a readiness
verdict is only "no blockers" and an unruled licence position is the least safe thing to pass
straight through to ``READY_FOR_HANDOFF``.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.assurance import human_jury  # noqa: E402
from design_lab.assurance import quality_record  # noqa: E402
from design_lab.assurance import handoff_readiness as hr  # noqa: E402

SUBJECT = "design-lab/job/job-1/deliverable/poster"
SHA = "sha256:" + "a" * 64
OTHER = "sha256:" + "b" * 64


def det(**o):
    d = {"finding_id": "f-det", "layer_id": "qa-deterministic",
         "check_id": "preflight.structural", "subject_ref": SUBJECT,
         "outcome": "PASS", "severity": "INFO", "evidence": {"artifact_sha256": SHA}}
    d.update(o)
    return d


def judge_high(**o):
    # an advisory model score that reads as "excellent" but must not gate
    d = {"finding_id": "f-judge", "layer_id": "qa-model-assisted",
         "check_id": "provider:aesthetic/laion", "subject_ref": SUBJECT,
         "outcome": "REVIEW_REQUIRED", "severity": "MINOR",
         "evidence": {"artifact_sha256": SHA, "confidence": 0.97, "score": 0.97},
         "recommendation": "aesthetic score is high; still human-gated"}
    d.update(o)
    return d


def approve():
    return {"schemaVersion": "design-lab/assurance-jury-record/v2", "kind": "JURY_VERDICT",
            "jury_record_id": "j-1", "subject_ref": SUBJECT, "artifact_sha256": SHA,
            "juror": {"juror_id": "dtalex66", "kind": "HUMAN",
                      "attestation": "calibrated-display review at 100%"},
            "criteria": [{"criterion_id": "anti-slop", "weight": 1.0, "score": 4.0, "note": None}],
            "verdict": "APPROVE", "decided_at": "2026-09-23T10:00:00Z",
            "supersedes": None, "evidence_refs": []}


def reject():
    # a REJECT verdict must carry evidence (the schema's REJECT branch demands
    # non-empty evidence_refs); it reuses the approve() base then overrides
    return {**approve(), "jury_record_id": "j-2", "verdict": "REJECT",
            "evidence_refs": ["reports/current/qa-rejection-evidence.json"]}


def qrec(approval, deterministic=None, judge=None):
    return quality_record.record_quality_record(
        quality_record_id="qr-1", subject_ref=SUBJECT, artifact_sha256=SHA,
        deterministic=deterministic if deterministic is not None else [det()],
        automated_judge=judge if judge is not None else [judge_high()],
        human_verdict=approval)


CLEAN_RIGHTS = [
    {"subject_id": "font:inter", "kind": "font", "license": "OFL-1.1",
     "territory": {"limits": [], "state": "ADJUDICATED"},
     "use_restriction": "ADJUDICATED", "output_restriction": "ADJUDICATED",
     "redistribution": "ADJUDICATED"},
]
BLOCK_RIGHTS = [
    {"subject_id": "model:h3", "kind": "provider", "license": "UNLICENSED",
     "territory": {"limits": ["commercial"], "state": "NOT_ADJUDICATED"},
     "use_restriction": "FORBIDDEN", "output_restriction": "NOT_ADJUDICATED",
     "redistribution": "NOT_ADJUDICATED"},
]

def preflight(status="pass", checks=None):
    cks = checks if checks is not None else [
        {"id": "font", "status": "pass"},
        {"id": "reopen_readback", "status": "pass"},
        {"id": "bleed", "status": "pass"},
    ]
    return {"preflight_id": "pf-1", "schemaVersion": "design-lab/preflight/v2",
            "profile": "print",
            "required_checks": [
                {"id": "font", "severity": "blocker", "tool": "fontkit"},
                {"id": "reopen_readback", "severity": "blocker", "tool": "adobe-uxp"},
                {"id": "bleed", "severity": "high", "tool": "prepress"},
            ],
            "result": {"status": status, "checks": cks}}


HANDOFF = {
    "project_id": "p-1", "version": "v3",
    "artifacts": [{"path": "poster.ai", "role": "source", "format": "pdf-x4",
                   "editable": True, "hash": SHA}],
    "assets": [], "licenses": [], "preflight_reports": ["pf-1"],
    "approvals": [{"role": "producer", "status": "approved"}],
}


def ready(*, quality, rights, pf, hf):
    return hr.decide(quality_record_doc=quality, rights_entries=rights,
                     preflight=pf, handoff=hf)


class PromptIHandoffReadinessTests(unittest.TestCase):
    def test_human_reject_with_high_model_score_blocks(self):
        d = ready(quality=qrec(reject()), rights=CLEAN_RIGHTS, pf=preflight(), hf=HANDOFF)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertEqual(d["quality_final_gate"], "BLOCKED")
        # the advisory judge is present but explicitly non-gating
        self.assertTrue(any("advisory" in s for s in d["info"]))
        self.assertTrue(any(s.startswith("human_gate") for s in d["blockers"]))

    def test_rights_blocker_blocks_even_on_human_approve(self):
        d = ready(quality=qrec(approve()), rights=BLOCK_RIGHTS, pf=preflight(), hf=HANDOFF)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any(s.startswith("rights:model:h3") for s in d["blockers"]))

    def test_restricting_rights_state_is_warning_not_blocker(self):
        restr = [{"subject_id": "img:stock", "kind": "image", "license": "CC-BY",
                  "territory": {"limits": [], "state": "ADJUDICATED"},
                  "use_restriction": "PERSONAL_RESEARCH_NONCOMMERCIAL_ONLY",
                  "output_restriction": "ADJUDICATED", "redistribution": "ADJUDICATED"}]
        d = ready(quality=qrec(approve()), rights=restr, pf=preflight(), hf=HANDOFF)
        # a personal-research restriction is a WARNING band, not a blocker:
        # with a signed human APPROVE and no blocker it still reads READY,
        # but the restriction must surface in the UI WARNING band
        self.assertEqual(d["readiness"], "READY_FOR_HANDOFF")
        self.assertNotIn("rights:img:stock:use_restriction=PERSONAL_RESEARCH_NONCOMMERCIAL_ONLY", d["blockers"])
        self.assertIn("rights:img:stock:use_restriction=PERSONAL_RESEARCH_NONCOMMERCIAL_ONLY", d["warnings"])

    def test_missing_font_preflight_blocker_blocks(self):
        pf = preflight(status="fail", checks=[
            {"id": "font", "status": "fail"},
            {"id": "reopen_readback", "status": "pass"},
            {"id": "bleed", "status": "pass"}])
        d = ready(quality=qrec(approve()), rights=CLEAN_RIGHTS, pf=pf, hf=HANDOFF)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any(s == "preflight:font=fail (severity=blocker)" for s in d["blockers"]))

    def test_reopen_failure_blocks(self):
        pf = preflight(status="fail", checks=[
            {"id": "font", "status": "pass"},
            {"id": "reopen_readback", "status": "fail"},
            {"id": "bleed", "status": "pass"}])
        d = ready(quality=qrec(approve()), rights=CLEAN_RIGHTS, pf=pf, hf=HANDOFF)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any(s.startswith("preflight:reopen_readback=fail") for s in d["blockers"]))

    def test_stale_artifact_blocks(self):
        stale_handoff = dict(HANDOFF, artifacts=[
            {"path": "poster.ai", "role": "source", "format": "pdf-x4",
             "editable": True, "hash": OTHER}])  # quality record says SHA
        d = ready(quality=qrec(approve()), rights=CLEAN_RIGHTS, pf=preflight(), hf=stale_handoff)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any(s.startswith("stale_artifact") for s in d["blockers"]))

    def test_live_reobserved_digest_mismatch_blocks(self):
        d = hr.decide(quality_record_doc=qrec(approve()), rights_entries=CLEAN_RIGHTS,
                      preflight=preflight(), handoff=HANDOFF, live_artifact_sha=OTHER)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any(s.startswith("stale_artifact") for s in d["blockers"]))

    def test_all_pass_reaches_ready_for_handoff(self):
        d = ready(quality=qrec(approve()), rights=CLEAN_RIGHTS, pf=preflight(), hf=HANDOFF)
        self.assertEqual(d["readiness"], "READY_FOR_HANDOFF")
        self.assertEqual(d["quality_final_gate"], "PASS")
        self.assertEqual(d["blockers"], [])
        self.assertEqual(d["ui_signals"]["BLOCKER"], [])

    def test_ui_backend_consistent(self):
        # the UI BLOCKER band is literally the backend blocker list
        d = ready(quality=qrec(reject()), rights=BLOCK_RIGHTS,
                  pf=preflight(status="fail", checks=[
                      {"id": "font", "status": "fail"},
                      {"id": "reopen_readback", "status": "pass"},
                      {"id": "bleed", "status": "pass"}]),
                  hf=HANDOFF)
        self.assertEqual(d["ui_signals"]["BLOCKER"], d["blockers"])
        self.assertEqual(d["readiness"], "BLOCKED")

    def test_no_preflight_report_blocks(self):
        d = hr.decide(quality_record_doc=qrec(approve()), rights_entries=CLEAN_RIGHTS,
                      preflight=None, handoff=HANDOFF)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any("no report supplied" in s for s in d["blockers"]))


class RightsBandFailClosedTests(unittest.TestCase):
    """A licence state the combiner cannot classify must block, never merely warn.

    The band table is a hand-written classification of values the registry records, and
    ``READY_FOR_HANDOFF`` is reachable whenever the BLOCKER band is empty. So while an
    unclassified state produced only a WARNING, every value the table did not know -- a state
    added under another taskpack, a misspelling of ``FORBIDDEN``, a legal hold -- read as
    "nothing blocks here". These tests pin the opposite: the unknown is the most dangerous
    input, and it is treated as one.
    """

    def test_unclassified_rights_state_blocks_the_handoff(self):
        held = [{"subject_id": "font:litigated", "kind": "font", "license": "OFL-1.1",
                 "territory": {"limits": [], "state": "ADJUDICATED"},
                 "use_restriction": "LITIGATION_HOLD", "output_restriction": "ADJUDICATED",
                 "redistribution": "ADJUDICATED"}]
        d = ready(quality=qrec(approve()), rights=held, pf=preflight(), hf=HANDOFF)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any("font:litigated:use_restriction" in s and "UNCLASSIFIED" in s
                            for s in d["blockers"]), d["blockers"])
        self.assertFalse(any("LITIGATION_HOLD" in s for s in d["warnings"]),
                         'an unclassified state must not be parked in the warning band')

    def test_misspelling_a_blocking_state_cannot_read_as_clean(self):
        typo = [{**BLOCK_RIGHTS[0], "redistribution": "FORBIDEN"}]
        d = ready(quality=qrec(approve()), rights=typo, pf=preflight(), hf=HANDOFF)
        self.assertEqual(d["readiness"], "BLOCKED")
        self.assertTrue(any("FORBIDEN" in s and "UNCLASSIFIED" in s for s in d["blockers"]))

    def test_a_state_absent_from_the_registry_is_still_only_a_warning(self):
        """The fix is about *unknown* values, not about missing ones."""
        gap = [{"subject_id": "font:inter", "kind": "font", "license": "OFL-1.1",
                "territory": {"limits": [], "state": "ADJUDICATED"},
                "use_restriction": None, "output_restriction": "ADJUDICATED",
                "redistribution": "ADJUDICATED"}]
        d = ready(quality=qrec(approve()), rights=gap, pf=preflight(), hf=HANDOFF)
        self.assertIn("rights:font:inter:use_restriction=ABSENT (registry recorded no value)",
                      d["warnings"])
        self.assertEqual(d["readiness"], "READY_FOR_HANDOFF")

    def test_nested_territory_state_is_read_through_its_path(self):
        """`territory.state` nests; a flat read of it would see None and stop blocking."""
        blocking = [{"subject_id": "model:h3", "kind": "model", "license": "UNLICENSED",
                     "territory": {"limits": ["commercial"], "state": "FORBIDDEN"},
                     "use_restriction": "ADJUDICATED", "output_restriction": "ADJUDICATED",
                     "redistribution": "ADJUDICATED"}]
        self.assertEqual(hr.rights_band("FORBIDDEN"), "BLOCKER")
        d = ready(quality=qrec(approve()), rights=blocking, pf=preflight(), hf=HANDOFF)
        self.assertIn("rights:model:h3:territory.state=FORBIDDEN", d["blockers"])

    def test_every_state_the_shipped_registry_records_is_classified(self):
        """The band table and the file it classifies agree today, on every field."""
        import json
        registry = json.loads((ROOT / "design-lab/config/rights-registry.json")
                              .read_text(encoding="utf-8"))
        entries = registry["entries"]
        self.assertTrue(entries, "an empty registry would make this test vacuous")
        readings = [(e["subject_id"], field, state_of(e, field))
                    for e in entries for field in hr.RIGHTS_FIELDS]
        unclassified = [f'{subject}:{field}={state!r}'
                        for subject, field, state in readings
                        if hr.rights_band(state) == "UNCLASSIFIED"]
        # Name the offenders in the message: 284 entries x 4 fields makes an assertEqual diff
        # unreadable ("Diff is 18272 characters long"), which tells an operator nothing.
        self.assertEqual(unclassified, [],
                         'no rights band classifies: ' + ', '.join(unclassified[:8])
                         + ('' if len(unclassified) <= 8 else
                            f' ... (+{len(unclassified) - 8} more)'))
        seen = sorted({state for _, _, state in readings})
        self.assertGreaterEqual(len(seen), 2, "a one-value vocabulary tests nothing")


def state_of(entry, field):
    """The registry records `territory.state` nested and the rest flat."""
    if field == "territory.state":
        return (entry.get("territory") or {}).get("state")
    return entry.get(field)


if __name__ == "__main__":
    unittest.main()
