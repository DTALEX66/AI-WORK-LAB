"""Gate: the AG-16 handback evidence may only claim what the contract actually did.

AG-16 shipped a contract with 24 negative controls and one honest gap: the row itself says no
structured handback had ever been round-tripped. This gate protects the *shape* of the answer now that
it has been run once, so a future edit cannot quietly turn "the plan was refused" into "the chain works".

Re-derived from `docs/audits/AG16_HANDBACK_ROUNDTRIP_2026-10-07.json`:
  - nothing executed, and no executor was selected, in any case;
  - no model-origin case is ever AUTHORIZED, and no AUTHORIZED case lacks `grantSource=fixture`;
  - the bare model return must be a refusal (the contract will not infer the envelope);
  - re-delivering identical content under a fresh id must be the duplicate verdict;
  - counts must equal the cases, the response digest must be a real digest, and the model that
    answered must be one the server listed in that same run.
"""
from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AUDIT = ROOT / "docs" / "audits" / "AG16_HANDBACK_ROUNDTRIP_2026-10-07.json"
HEX64 = re.compile(r"[0-9a-f]{64}")


def sha256_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _walk_keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _walk_keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_keys(v)


def _walk_strings(node):
    if isinstance(node, str):
        yield node
    elif isinstance(node, dict):
        for v in node.values():
            yield from _walk_strings(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_strings(v)


def violations(doc: dict) -> list[str]:
    out = []
    cases = doc["cases"]
    by_case = {c["case"]: c for c in cases}
    for c in cases:
        if c.get("executionStatus") != "NOT_EXECUTED":
            out.append(f"{c['case']}: executionStatus {c.get('executionStatus')!r}, "
                       "this round-trip may not report execution")
        if c.get("executorSelected") is not None:
            out.append(f"{c['case']}: names an executor; none was selected")
        if c["origin"].startswith("MODEL") and c["verdictStatus"].startswith("AUTHORIZED"):
            out.append(f"{c['case']}: a model-produced plan came back AUTHORIZED with no real grant")
        if c["verdictStatus"].startswith("AUTHORIZED") and c.get("grantSource") != "fixture":
            out.append(f"{c['case']}: AUTHORIZED without grantSource=fixture")
        if "contentDigest" in c and not HEX64.fullmatch(str(c["contentDigest"])):
            out.append(f"{c['case']}: contentDigest is not 64 lowercase hex")
    bare = by_case.get("model-return-without-envelope")
    if bare is None:
        out.append("missing case: the bare model return, which must be refused")
    elif not bare["verdictStatus"].startswith("REFUSED"):
        out.append(f"bare model return verdict {bare['verdictStatus']!r}; the contract must refuse "
                   "to infer baseline/contextDigest/planningSoftware/workUnitId/taskRevision")
    envelope = by_case.get("model-content-in-real-envelope")
    if envelope is None:
        out.append("missing case: model content inside a real envelope")
    elif envelope.get("replaySameContentFreshId") != "DUPLICATE_CONTENT":
        out.append("re-delivery of identical content under a fresh id was not detected as duplicate")
    elif not envelope.get("envelopeSources"):
        out.append("the envelope's factual fields are not attributed to a source")
    shape = doc["returnShape"]
    if not HEX64.fullmatch(str(shape.get("responseSha256"))):
        out.append("responseSha256 is not a digest")
    if doc["planningEnd"]["modelRequested"] not in doc["planningEnd"]["servedModels"]:
        out.append("the answering model is not among the models the server listed in this run")
    counts = doc["counts"]
    if counts["cases"] != len(cases):
        out.append(f"counts.cases={counts['cases']} but {len(cases)} cases are recorded")
    if counts["authorized"] != sum(1 for c in cases
                                   if c["verdictStatus"].startswith("AUTHORIZED")):
        out.append("counts.authorized disagrees with the cases")
    if counts["executed"] != 0:
        out.append("counts.executed must be 0")
    if counts["authorizedWithoutFixtureGrant"] != 0:
        out.append("a real grant exists, or the count no longer matches the cases")
    return out


class Ag16HandbackEvidenceGate(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = json.loads(AUDIT.read_text(encoding="utf-8"))

    def test_the_shipped_evidence_makes_no_forbidden_claim(self) -> None:
        self.assertEqual(violations(self.doc), [])

    def test_the_round_trip_actually_ran_against_a_live_planning_end(self) -> None:
        self.assertGreater(self.doc["planningEnd"]["responseSeconds"], 0)
        self.assertGreaterEqual(len(self.doc["planningEnd"]["servedModels"]), 1)
        self.assertIn(self.doc["planningEnd"]["responseFormatMode"], {"json_schema", "text"})
        self.assertEqual(self.doc["returnShape"]["jsonParseOk"], True,
                         "the planning end did not return parseable structure; that is a finding, "
                         "not a pass — re-run before claiming the link works")

    def test_bodies_are_not_copied_into_the_record(self) -> None:
        # substring checks over the whole document are useless here — the endpoint path itself
        # contains "completions" — so the rule is on key names and on string sizes instead
        seen = list(_walk_keys(self.doc))
        for forbidden in ("promptText", "responseText", "rawResponse", "messages", "content",
                          "completion"):
            self.assertNotIn(forbidden, seen, f"a {forbidden} key would carry a body into the record")
        # a body would reproduce its own digest; prose notes may be longer than the response
        stored = list(_walk_strings(self.doc))
        for target, label in ((self.doc["returnShape"]["responseSha256"], "response"),
                              (self.doc["requestPromptSha256"], "prompt")):
            self.assertFalse(any(sha256_of(s) == target for s in stored),
                             f"the {label} body is present verbatim somewhere in the record")
        self.assertTrue(HEX64.fullmatch(self.doc["requestPromptSha256"]))

    def test_the_capability_vocabulary_gap_is_recorded_not_hidden(self) -> None:
        self.assertIn("capabilityVocabularyFinding", self.doc)
        self.assertIn("ERR-138", self.doc["capabilityVocabularyFinding"])

    # ---------------- negative controls
    def _clone(self):
        return json.loads(json.dumps(self.doc))

    def test_a_claim_that_something_executed_is_refused(self) -> None:
        doc = self._clone()
        doc["cases"][0]["executionStatus"] = "EXECUTED"
        self.assertTrue(any("may not report execution" in v for v in violations(doc)))

    def test_an_authorized_model_plan_is_refused(self) -> None:
        doc = self._clone()
        next(c for c in doc["cases"] if c["origin"].startswith("MODEL"))["verdictStatus"] = \
            "AUTHORIZED"
        self.assertTrue(any("no real grant" in v for v in violations(doc)))

    def test_a_silently_accepted_bare_return_is_refused(self) -> None:
        doc = self._clone()
        next(c for c in doc["cases"]
             if c["case"] == "model-return-without-envelope")["verdictStatus"] = "AWAITING_AUTHORIZATION"
        self.assertTrue(any("must refuse to infer" in v for v in violations(doc)))

    def test_a_missed_duplicate_is_refused(self) -> None:
        doc = self._clone()
        next(c for c in doc["cases"]
             if c["case"] == "model-content-in-real-envelope")["replaySameContentFreshId"] = \
            "NEEDS_INPUT"
        self.assertTrue(any("not detected as duplicate" in v for v in violations(doc)))

    def test_a_named_executor_is_refused(self) -> None:
        doc = self._clone()
        doc["cases"][0]["executorSelected"] = "lmstudio"
        self.assertTrue(any("names an executor" in v for v in violations(doc)))

    def test_a_count_that_disagrees_with_the_cases_is_refused(self) -> None:
        doc = self._clone()
        doc["counts"]["cases"] = 99
        self.assertTrue(any("counts.cases" in v for v in violations(doc)))

    def test_an_answering_model_the_server_never_listed_is_refused(self) -> None:
        doc = self._clone()
        doc["planningEnd"]["modelRequested"] = "gpt-omnipotent-9"
        self.assertTrue(any("not among the models" in v for v in violations(doc)))


if __name__ == "__main__":
    unittest.main(verbosity=2)
