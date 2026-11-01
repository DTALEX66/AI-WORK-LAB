"""Gate + behaviour tests for Quick Entry: the contract agrees with the code, and each §15.2 condition
produces its own outcome rather than a generic failure.

Why these particular assertions:

  * the verb enum is declared twice -- once in the JSON Schema, once as `entry_semantics.UNIFIED_VERBS` --
    and two owners of one predicate is the defect class this repository has already been burned by. The
    schema is the contract, so the tuple is checked against it here and a drift goes red.
  * blueprint §15.2 names five release conditions (输入修订、权限拒绝、客户端不可用、失败恢复与取消). A mode
    is only "implemented" if each one is reachable and distinguishable, so each gets its own case, plus a
    precedence case showing a cancelled request is not re-judged as a permission refusal.
  * `UNKNOWN` revision must not be folded into either branch of a comparison -- it is its own answer.
  * an accepted entry must actually assemble a ContextBundle: `context_bundle.ContextBundle` had zero
    non-test importers before this module, and a contract nobody consumes is documentation.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import quick_entry  # noqa: E402
from entry_semantics import UNIFIED_VERBS  # noqa: E402

CATALOG = ROOT / ".project" / "governance" / "contracts" / "contract-catalog.json"
SCHEMA = json.loads(quick_entry.SCHEMA_PATH.read_text(encoding="utf-8"))


def request(**overrides) -> dict:
    base = {
        "schema_version": "work-lab/quick-entry-request/v1",
        "requestId": "req-1",
        "verb": "publish",
        "input": {"baseRevision": "r-7", "currentRevision": "r-7"},
        "project": {"projectId": "atlas"},
        "permission": {"mode": "observe"},
        "client": {"hostId": "codex", "declaredAvailable": True},
    }
    for key, value in overrides.items():
        if isinstance(value, dict) and isinstance(base.get(key), dict):
            base[key] = {**base[key], **value}
        else:
            base[key] = value
    return base


HOSTS = {"codex": True, "dsh": False}
APPROVED = ("atlas",)
BUNDLE_FACTS = {
    "rulesRevision": "rules-3",
    "boundary": "packages/client-neutral-core only; no writes outside the project Git root",
    "acceptance": "ACCEPTANCE: python services/orchestration/run_quality_gate.py verify prints GATE_EXIT=0",
    "blocks": {"system_boundary": "boundary text", "project_rules": "rules summary"},
    "preserve": {
        "user_goal": "close OD05 with a real entry",
        "non_goals": "no new auth surface",
        "allowed_paths": "packages/client-neutral-core/scripts",
        "forbidden_paths": "E:/ and F:/",
        "data_boundary": ".project-local stays inside the repo",
        "base_sha_tree": "abc123",
        "known_failures": "none recorded",
        "acceptance_commands": "run_quality_gate.py verify",
        "rollback_method": "revert the commit",
    },
}


class ContractAgreementTests(unittest.TestCase):
    def test_the_schema_verb_enum_is_the_tuple_the_code_uses(self) -> None:
        self.assertEqual(tuple(SCHEMA["properties"]["verb"]["enum"]), tuple(UNIFIED_VERBS),
                         "the contract and entry_semantics.UNIFIED_VERBS disagree about which verbs exist")

    def test_the_schema_is_declared_in_the_catalogue_with_a_real_consumer(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        entry = [c for c in catalog["contracts"]
                 if c["schemaPath"].endswith("quick-entry-request.schema.json")]
        self.assertEqual(len(entry), 1, "the new schema must be declared exactly once in the catalogue")
        self.assertTrue(entry[0]["consumers"], "a contract with no consumer is documentation")
        self.assertTrue((ROOT / entry[0]["schemaPath"]).is_file())

    def test_a_request_missing_required_fields_is_refused_with_every_problem_named(self) -> None:
        broken = request()
        del broken["permission"]
        del broken["input"]["currentRevision"]
        problems = quick_entry.validate(broken)
        self.assertGreaterEqual(len(problems), 2, f"expected both gaps reported, got {problems}")
        decision = quick_entry.submit(broken, live_hosts=HOSTS, approved_project_ids=APPROVED)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_INVALID)

    def test_an_unknown_extra_field_is_refused_not_tolerated(self) -> None:
        # additionalProperties:false is the whole point of a field spec; a permissive schema teaches nothing.
        self.assertTrue(quick_entry.validate(request(someField="x")),
                        "the schema accepted a field it never declares")


class ReleaseConditionTests(unittest.TestCase):
    def setUp(self) -> None:
        self.kwargs = {"live_hosts": HOSTS, "approved_project_ids": APPROVED,
                       "bundle_facts": BUNDLE_FACTS}

    def test_input_revision_mismatch_is_its_own_outcome(self) -> None:
        decision = quick_entry.submit(request(input={"baseRevision": "r-7", "currentRevision": "r-8"}),
                                      **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_INPUT_REVISED)
        self.assertIn("moved since", decision.reason)

    def test_unknown_revision_is_reported_and_not_guessed_either_way(self) -> None:
        decision = quick_entry.submit(request(input={"baseRevision": "UNKNOWN",
                                                     "currentRevision": "r-8"}), **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_INPUT_REVISED)
        self.assertIn("UNKNOWN", decision.reason)

    def test_permission_outside_the_allowed_set_is_refused(self) -> None:
        decision = quick_entry.submit(request(permission={"mode": "execute"}),
                                      live_hosts=HOSTS, approved_project_ids=APPROVED,
                                      allowed_modes=("observe",))
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_PERMISSION_REFUSED)

    def test_an_unavailable_client_is_reported_even_when_the_caller_declared_it_available(self) -> None:
        decision = quick_entry.submit(request(client={"hostId": "dsh", "declaredAvailable": True}),
                                      **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_CLIENT_UNAVAILABLE)
        self.assertIn("declared True", decision.reason)

    def test_an_unregistered_host_is_not_silently_accepted(self) -> None:
        decision = quick_entry.submit(request(client={"hostId": "ghost"}), **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_CLIENT_UNAVAILABLE)
        self.assertIn("not registered", decision.reason)

    def test_cancellation_wins_over_every_other_judgement(self) -> None:
        # A cancelled request that ALSO lacks permission must read CANCELLED, not PERMISSION_REFUSED:
        # the caller asked to stop, and re-interpreting that as a refusal invents a decision they did not
        # receive.
        decision = quick_entry.submit(
            request(permission={"mode": "execute"}, cancellation={"requested": True}),
            live_hosts=HOSTS, approved_project_ids=APPROVED, allowed_modes=("observe",))
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_CANCELLED)

    def test_a_cancel_after_a_side_effect_says_it_is_not_a_rollback(self) -> None:
        decision = quick_entry.submit(
            request(cancellation={"requested": True, "sideEffectsAlreadyMade": True}), **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_CANCELLED)
        self.assertIn("not a rollback", decision.reason)

    def test_recovery_attempt_reports_recovered_and_carries_the_bundle(self) -> None:
        decision = quick_entry.submit(
            request(recovery={"attempt": 2, "previousOutcome": "FAILED",
                              "carriedForward": list(BUNDLE_FACTS["preserve"].keys())}),
            **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_RECOVERED)
        self.assertIsNotNone(decision.bundle, "a recovery that loses the assembled context is not recovery")
        self.assertEqual(decision.details["driftFactsNotMarkedCarried"], [])

    def test_a_recovery_that_marks_nothing_carried_does_not_claim_facts_survived(self) -> None:
        decision = quick_entry.submit(
            request(recovery={"attempt": 3, "previousOutcome": "TIMED_OUT"}), **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_RECOVERED)
        self.assertEqual(decision.details["carriedForward"], [],
                         "the caller never said what survived, so the decision must not invent it")

    def test_an_unapproved_project_is_refused_before_any_bundle_is_built(self) -> None:
        decision = quick_entry.submit(request(project={"projectId": "somewhere-else"}), **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_PROJECT_UNAPPROVED)
        self.assertIsNone(decision.bundle)

    def test_accepted_first_attempt_assembles_a_real_bundle(self) -> None:
        decision = quick_entry.submit(request(), **self.kwargs)
        self.assertEqual(decision.outcome, quick_entry.OUTCOME_ACCEPTED)
        self.assertIsNotNone(decision.bundle,
                             "ContextBundle must have a non-test consumer; an accepted entry that "
                             "assembles nothing is the gap this module exists to close")
        self.assertEqual(decision.details["projectId"], "atlas")
        self.assertEqual(decision.details["verb"], "publish")

    def test_a_bundle_missing_its_critical_facts_fails_closed_rather_than_passing_a_thin_bundle(self) -> None:
        thin = dict(BUNDLE_FACTS)
        thin["preserve"] = {"user_goal": "only one fact"}
        with self.assertRaises(ValueError) as caught:
            quick_entry.submit(request(), live_hosts=HOSTS, approved_project_ids=APPROVED,
                               bundle_facts=thin)
        self.assertIn("context_drift_missing", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
