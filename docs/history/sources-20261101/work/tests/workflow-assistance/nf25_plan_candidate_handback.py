"""AG-16 negative controls: the super-entry planning handback contract.

The super-entry chain is ContextEnvelope -> PlanningCandidate -> check/authorize
-> user-selected executor -> Receipt. This file pins the middle link's safety
properties. The two that matter most, and that a naive implementation gets wrong:

* planning output NEVER authorizes execution, so a candidate that claims
  `approved: true` must still come back AWAITING_AUTHORIZATION;
* a verdict is NOT an execution, so even a fully authorized candidate returns
  executionStatus = NOT_EXECUTED.

Pure and deterministic: no network, no filesystem, no model call.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import plan_candidate as pc  # noqa: E402


class _Registry:
    """Minimal stand-in for CapabilityRoleRegistry."""

    def __init__(self, mapping: dict[str, list[str]]) -> None:
        self._m = mapping

    def roles_with_capability(self, capability: str, **_: object) -> list[str]:
        return list(self._m.get(capability, []))


def draft(**overrides: object) -> dict:
    base = {
        "planningSoftware": "web-gpt",
        "workUnitId": "WU-1",
        "taskRevision": 1,
        "baseline": {"commit": "a" * 40},
        "contextRef": "capsule-1",
        "contextDigest": "d" * 64,
        "changes": [{"path": "docs/x.md", "op": "edit"}],
        "verification": ["run the quality gate"],
    }
    base.update(overrides)
    return base


class BuildContract(unittest.TestCase):
    def test_builds_and_is_content_addressed(self) -> None:
        c = pc.build_candidate(draft())
        self.assertEqual(c["schemaVersion"], pc.SCHEMA_VERSION)
        self.assertTrue(c["candidateId"].startswith("pc-"))
        self.assertEqual(len(c["contentDigest"]), 64)

    def test_same_content_under_two_ids_dedupes_to_one_digest(self) -> None:
        a = pc.build_candidate(draft(candidateId="one", createdAt="T1"))
        b = pc.build_candidate(draft(candidateId="two", createdAt="T2"))
        self.assertEqual(a["contentDigest"], b["contentDigest"])

    def test_changed_content_changes_the_digest(self) -> None:
        a = pc.build_candidate(draft())
        b = pc.build_candidate(draft(changes=[{"path": "docs/y.md", "op": "edit"}]))
        self.assertNotEqual(a["contentDigest"], b["contentDigest"])

    def test_missing_required_field_raises_rather_than_defaulting(self) -> None:
        for field in pc.REQUIRED_DRAFT_FIELDS:
            with self.subTest(field=field):
                broken = draft()
                del broken[field]
                with self.assertRaises(ValueError):
                    pc.build_candidate(broken)

    def test_baseline_must_carry_commit_or_digest(self) -> None:
        with self.assertRaises(ValueError):
            pc.build_candidate(draft(baseline={"kind": "git"}))

    def test_revision_must_be_positive(self) -> None:
        with self.assertRaises(ValueError):
            pc.build_candidate(draft(taskRevision=0))


class PlanningNeverAuthorizes(unittest.TestCase):
    """The central rule of the super-entry architecture."""

    def test_self_claiming_approval_is_ignored(self) -> None:
        c = pc.build_candidate(draft(approved=True, scope="full", permission="write"))
        v = pc.check_candidate(c, trusted_grants={"grant-1": "write"})
        self.assertEqual(v["status"], pc.R_AWAITING_AUTHORIZATION)
        self.assertEqual(sorted(v["ignoredSelfClaims"]), ["approved", "permission", "scope"])

    def test_unresolvable_grant_ref_does_not_authorize(self) -> None:
        c = pc.build_candidate(draft(authorizationRef="ghost-grant"))
        v = pc.check_candidate(c, trusted_grants={"grant-1": "write"})
        self.assertEqual(v["status"], pc.R_AWAITING_AUTHORIZATION)

    def test_trusted_grant_authorizes_but_does_not_execute(self) -> None:
        c = pc.build_candidate(draft(authorizationRef="grant-1"))
        v = pc.check_candidate(c, trusted_grants={"grant-1": "docs-only"})
        self.assertEqual(v["status"], pc.R_AUTHORIZED)
        self.assertEqual(v["authorizedScope"], "docs-only")
        self.assertEqual(v["executionStatus"], pc.EXECUTION_STATUS)

    def test_no_verdict_ever_reports_execution(self) -> None:
        cases = [
            pc.check_candidate(pc.build_candidate(draft())),
            pc.check_candidate(pc.build_candidate(draft(authorizationRef="g")),
                               trusted_grants={"g": "read"}),
            pc.check_candidate({"schemaVersion": "nope"}),
        ]
        for verdict in cases:
            self.assertEqual(verdict["executionStatus"], "NOT_EXECUTED")
            self.assertNotIn("executed", verdict)


class BlockingItemsGate(unittest.TestCase):
    def test_blocking_item_requires_input_before_anything_else(self) -> None:
        c = pc.build_candidate(draft(
            authorizationRef="grant-1",
            unresolved=[{"id": "Q1", "blocking": True, "title": "which executor?"}],
        ))
        v = pc.check_candidate(c, trusted_grants={"grant-1": "write"})
        # Even WITH a valid grant, an unanswered question stops it.
        self.assertEqual(v["status"], pc.R_NEEDS_INPUT)
        self.assertEqual(v["blocking"], ["Q1"])

    def test_plain_string_unresolved_counts_as_blocking(self) -> None:
        c = pc.build_candidate(draft(unresolved=["who owns the rollback?"]))
        v = pc.check_candidate(c)
        self.assertEqual(v["status"], pc.R_NEEDS_INPUT)

    def test_explicitly_non_blocking_item_does_not_block(self) -> None:
        c = pc.build_candidate(draft(
            unresolved=[{"id": "N1", "blocking": False}],
        ))
        v = pc.check_candidate(c, trusted_grants={"g": "read"}, )
        # Falls through the blocking gate (no grant ref -> awaiting authorization).
        self.assertEqual(v["status"], pc.R_AWAITING_AUTHORIZATION)

    def test_empty_unresolved_does_not_block(self) -> None:
        v = pc.check_candidate(pc.build_candidate(draft()))
        self.assertNotEqual(v["status"], pc.R_NEEDS_INPUT)


class CapabilityGate(unittest.TestCase):
    def test_unavailable_capability_is_refused_by_name(self) -> None:
        c = pc.build_candidate(draft(targetCapability="code.write", authorizationRef="g"))
        v = pc.check_candidate(c, trusted_grants={"g": "write"},
                               capability_registry=_Registry({}))
        self.assertEqual(v["status"], pc.R_REFUSED_CAPABILITY)
        self.assertIn("code.write", v["reason"])

    def test_available_capability_proceeds_to_authorization(self) -> None:
        c = pc.build_candidate(draft(targetCapability="code.read", authorizationRef="g"))
        v = pc.check_candidate(c, trusted_grants={"g": "read"},
                               capability_registry=_Registry({"code.read": ["hermes"]}))
        self.assertEqual(v["status"], pc.R_AUTHORIZED)

    def test_registry_that_errors_does_not_count_as_available(self) -> None:
        class Boom:
            def roles_with_capability(self, capability: str) -> list[str]:
                raise RuntimeError("registry offline")

        c = pc.build_candidate(draft(targetCapability="code.read", authorizationRef="g"))
        v = pc.check_candidate(c, trusted_grants={"g": "read"}, capability_registry=Boom())
        self.assertEqual(v["status"], pc.R_REFUSED_CAPABILITY)


class Deduplication(unittest.TestCase):
    def test_redelivered_plan_is_duplicate_not_reapplied(self) -> None:
        ledger = pc.CandidateLedger()
        first = pc.build_candidate(draft())
        second = pc.build_candidate(draft(candidateId="different-id"))
        self.assertEqual(ledger.record(first)["status"], "RECORDED")
        self.assertEqual(ledger.record(second)["status"], pc.R_DUPLICATE)

    def test_check_reports_duplicate_against_known_digests(self) -> None:
        c = pc.build_candidate(draft())
        v = pc.check_candidate(c, already_seen_digests=[c["contentDigest"]])
        self.assertEqual(v["status"], pc.R_DUPLICATE)

    def test_duplicate_is_checked_before_authorization(self) -> None:
        # A duplicate must not consume or consult a grant.
        c = pc.build_candidate(draft(authorizationRef="g"))
        v = pc.check_candidate(c, trusted_grants={"g": "write"},
                               already_seen_digests=[c["contentDigest"]])
        self.assertEqual(v["status"], pc.R_DUPLICATE)
        self.assertIsNone(v["authorizedScope"])

    def test_ledger_indexes_by_work_unit(self) -> None:
        ledger = pc.CandidateLedger()
        ledger.record(pc.build_candidate(draft(workUnitId="WU-1")))
        ledger.record(pc.build_candidate(draft(workUnitId="WU-2")))
        self.assertEqual(len(ledger.for_work_unit("WU-1")), 1)
        self.assertEqual(len(ledger.for_work_unit("WU-2")), 1)


class MalformedInput(unittest.TestCase):
    def test_wrong_schema_is_draft_invalid(self) -> None:
        v = pc.check_candidate({"schemaVersion": "workflow/other/v1"})
        self.assertEqual(v["status"], pc.R_DRAFT_INVALID)

    def test_non_mapping_is_draft_invalid(self) -> None:
        self.assertEqual(pc.check_candidate(None)["status"], pc.R_DRAFT_INVALID)

    def test_ledger_requires_a_digest(self) -> None:
        with self.assertRaises(ValueError):
            pc.CandidateLedger().record({"candidateId": "x"})


if __name__ == "__main__":
    unittest.main()
