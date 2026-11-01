"""Gate: the WUI-21 read-model contracts, and that the producer cannot claim more than the ledger answers.

The pack's §5 stage list (未开始 → 提交中 → 排队/运行 → 通过/失败/取消/未知, 超时=未知或超时) is the thing being
contracted, and the intake decision for it says the server contract comes first because "UI 不得先造字段"
(`docs/history/archive/ui-priority-20261009/UI-V2-INTAKE-20261010.md:39`). So this file drives a **real** `TaskLedger`
and asserts what its records may and may not say:

* `SUBMITTING` is absent from the state enum forever, because no module records the client-to-ledger handoff.
  If a producer ever adds it, the gap token disappears from the contract's own list and this test says so.
* An expired lease answers `UNKNOWN_OR_TIMEOUT`. A test that let it answer `FAILED` would be teaching the page
  to report a broken operation from a missing observation.
* A child that `COMPLETED` answers the **write** stage only. `target_behaviour` is answered solely from a
  reconciled external effect -- the three-separated-results rule the pack imposes on WUI-10/WUI-21, enforced by
  the shape (there is no aggregate success key to light up).

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages/client-neutral-core/scripts"))

import jsonschema  # noqa: E402  the same dependency the contract-catalog gate already requires
import project_temp  # noqa: E402
from operation_progress import (  # noqa: E402
    LEDGER_TO_STATE, build_isolated_trial, build_operation_progress,
)
from task_ledger import EXTERNAL_EFFECT_STATES, STATES, TaskLedger  # noqa: E402

SCHEMA_DIR = ROOT / "packages/contracts/schemas/workflow"
PROGRESS_SCHEMA = json.loads((SCHEMA_DIR / "operation-progress.schema.json").read_text(encoding="utf-8"))
TRIAL_SCHEMA = json.loads((SCHEMA_DIR / "isolated-trial.schema.json").read_text(encoding="utf-8"))
CATALOG = json.loads((ROOT / ".project/governance/contracts/contract-catalog.json").read_text(encoding="utf-8"))
PROGRESS_STATES = set(PROGRESS_SCHEMA["properties"]["state"]["enum"])


def validate(record: dict, schema: dict) -> None:
    jsonschema.validate(instance=record, schema=schema)


class ContractShapeTests(unittest.TestCase):
    def test_both_schemas_are_draft_2020_12_and_registered_as_workflow_contracts(self) -> None:
        for schema, schema_id in ((PROGRESS_SCHEMA, "worklab/operation-progress/v1"),
                                  (TRIAL_SCHEMA, "worklab/isolated-trial/v1")):
            jsonschema.Draft202012Validator.check_schema(schema)
            self.assertEqual(schema["$id"], schema_id)
            self.assertFalse(schema["additionalProperties"],
                             f"{schema_id} must reject an invented field, not tolerate it")
        ids = {entry["id"] for entry in CATALOG["contracts"]}
        for contract in ("workflow-operation-progress-v1", "workflow-isolated-trial-v1"):
            self.assertIn(contract, ids, f"{contract} is not in the single contract catalog")
        owners = {entry["id"]: (entry["owner"], entry["consumers"]) for entry in CATALOG["contracts"]}
        self.assertEqual(owners["workflow-operation-progress-v1"][0], "workflow",
                         "the Observer is a read-only projection; it cannot own this contract")

    def test_the_state_enum_covers_every_ledger_state_and_adds_no_invention(self) -> None:
        mapped = set(LEDGER_TO_STATE.values())
        self.assertTrue(mapped <= PROGRESS_STATES,
                        f"producer maps to states the contract forbids: {sorted(mapped - PROGRESS_STATES)}")
        for state in sorted(STATES):
            self.assertIn(state, LEDGER_TO_STATE,
                          f"the ledger can hold {state} but the producer has no rule for it, so a real state "
                          "would be reported as UNKNOWN")
        self.assertNotIn("SUBMITTING", PROGRESS_STATES,
                         "提交中 has no producer in this repository; adding it to the enum would let a page "
                         "render a stage nobody records")
        self.assertIn("UNKNOWN_OR_TIMEOUT", PROGRESS_STATES)
        self.assertNotIn("COMPLETED", PROGRESS_STATES,
                         "the contract spells the pack's verdict PASSED; two names for one verdict is how a "
                         "consumer starts guessing")

    def test_the_trial_contract_has_no_aggregate_success_field(self) -> None:
        props = set(TRIAL_SCHEMA["properties"])
        self.assertNotIn("success", props)
        self.assertNotIn("passed", props)
        self.assertEqual(sorted(TRIAL_SCHEMA["properties"]["separated_results"]["required"]),
                         ["native_readback", "target_behaviour", "write"],
                         "the three separated results are the contract; a rename that merges two of them fails here")


class ProducerAgainstRealLedgerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("operation-progress-gate-")
        self.ledger = TaskLedger(Path(self.fixture))

    def tearDown(self) -> None:
        project_temp.force_release(self.fixture)

    def test_a_running_task_produces_a_valid_progress_record_with_the_gap_named(self) -> None:
        self.ledger.create("t-1", "key-1")
        self.ledger.transition("t-1", "PLANNING")
        self.ledger.transition("t-1", "RUNNING")
        record = build_operation_progress(self.ledger, "t-1", transport_state="ONLINE",
                                          now="2026-10-10T00:00:00Z")
        validate(record, PROGRESS_SCHEMA)
        self.assertEqual(record["state"], "RUNNING")
        self.assertEqual(record["ledger_status"], "RUNNING")
        self.assertIn("SUBMITTING_STAGE", record["producer_gaps"])
        # transition() moves the status; it does not take a lease (task_ledger.py:355-377). So the freshest
        # witness here is updated_at, and a record that claimed a heartbeat would be describing a lease that
        # was never acquired.
        self.assertEqual(record["last_trusted_progress"]["basis"], "LEDGER_UPDATED_AT")
        self.ledger.acquire_lease("t-1", "worker-a", ttl_seconds=60, now="2026-10-10T00:00:00Z")
        leased = build_operation_progress(self.ledger, "t-1", now="2026-10-10T00:00:30Z")
        validate(leased, PROGRESS_SCHEMA)
        self.assertEqual(leased["last_trusted_progress"]["basis"], "LEDGER_HEARTBEAT",
                         "once a lease exists the heartbeat is the fresher witness and must be preferred")

    def test_an_expired_lease_is_unknown_or_timeout_and_never_a_failure(self) -> None:
        self.ledger.create("t-2", "key-2")
        self.ledger.transition("t-2", "PLANNING")
        self.ledger.transition("t-2", "RUNNING")
        self.ledger.acquire_lease("t-2", "worker-a", ttl_seconds=30, now="2026-10-10T00:00:00Z")
        record = build_operation_progress(self.ledger, "t-2", now="2026-10-10T00:05:00Z")
        validate(record, PROGRESS_SCHEMA)
        self.assertEqual(record["state"], "UNKNOWN_OR_TIMEOUT")
        self.assertEqual(record["ledger_status"], "RUNNING",
                         "the timeout verdict must still show what the ledger says, so the reader can see "
                         "the two facts are different")

    def test_a_missing_operation_answers_unknown_with_no_trusted_progress(self) -> None:
        record = build_operation_progress(self.ledger, "never-created", transport_state="OFFLINE")
        validate(record, PROGRESS_SCHEMA)
        self.assertEqual(record["state"], "UNKNOWN")
        self.assertIsNone(record["ledger_status"])
        self.assertEqual(record["last_trusted_progress"]["basis"], "NONE")
        self.assertIsNone(record["last_trusted_progress"]["at"],
                         "an empty timestamp would read as 'observed at the epoch'")
        self.assertEqual({"createdAt": None, "updatedAt": None, "heartbeatAt": None},
                         record["sourceTimes"],
                         "an unreadable operation attests no times; borrowing observed_at here would "
                         "present our own read clock as the source's word")

    def test_source_times_come_from_the_record_and_never_borrow_a_neighbour(self) -> None:
        """Measured 2026-10-13: the pack's `sourceTimes` had no producer at all.

        The point of the field is that `observed_at` (when WE read) and the source's own stamps are
        different claims. The failure mode to guard is a fallback: filling a missing heartbeat from
        `updated_at` would report a lease renewal that never happened.
        """
        self.ledger.create("t-4", "key-4")
        self.ledger.transition("t-4", "PLANNING")
        record = build_operation_progress(self.ledger, "t-4", now="2026-10-13T00:00:00Z")
        validate(record, PROGRESS_SCHEMA)
        task = self.ledger.get("t-4")
        self.assertEqual(record["sourceTimes"]["createdAt"], task["created_at"])
        self.assertEqual(record["sourceTimes"]["updatedAt"], task["updated_at"])
        self.assertIsNone(record["sourceTimes"]["heartbeatAt"],
                          "no lease has been taken yet, so there is no heartbeat to report")
        self.assertNotEqual(record["sourceTimes"]["heartbeatAt"], record["sourceTimes"]["updatedAt"],
                            "a missing heartbeat filled from updated_at is a lease renewal that never happened")
        self.ledger.acquire_lease("t-4", "worker-a", ttl_seconds=60, now="2026-10-13T00:00:30Z")
        leased = build_operation_progress(self.ledger, "t-4", now="2026-10-13T00:00:40Z")
        validate(leased, PROGRESS_SCHEMA)
        self.assertEqual(leased["sourceTimes"]["heartbeatAt"],
                         self.ledger.get("t-4")["lease"]["heartbeat_at"],
                         "once a lease exists its stamp is the heartbeat this field is for")

    def test_the_packs_sequence_is_a_named_gap_and_not_the_stores_revision(self) -> None:
        """`sequence` is named in the pack's read model; nothing here counts per-operation progress.

        The tempting substitute is the snapshot's `revision`, which is the STORE's cursor. Two different
        monotonic things made to look like one is the defect ERR-225 keeps recording under other names,
        so the field is carried as a declared gap and the record has no `sequence` key to misread.
        """
        self.ledger.create("t-5", "key-5")
        record = build_operation_progress(self.ledger, "t-5")
        validate(record, PROGRESS_SCHEMA)
        self.assertIn("PROGRESS_SEQUENCE", record["producer_gaps"])
        self.assertNotIn("sequence", record,
                         "a `sequence` key answered from the store's revision would be a different number "
                         "wearing this field's name")
        enum = json.loads((ROOT / "packages/contracts/schemas/workflow/operation-progress.schema.json")
                          .read_text(encoding="utf-8"))["properties"]["producer_gaps"]["items"]["enum"]
        self.assertIn("PROGRESS_SEQUENCE", enum,
                      "the gap must be declared in the contract, not only emitted by code")

    def test_completed_is_the_only_ledger_state_that_answers_passed(self) -> None:
        self.ledger.create("t-3", "key-3")
        self.ledger.transition("t-3", "PLANNING")
        self.ledger.transition("t-3", "RUNNING")
        self.ledger.transition("t-3", "REVIEWING")
        before = build_operation_progress(self.ledger, "t-3", now="2026-10-10T00:00:00Z")
        self.assertEqual(before["state"], "REVIEWING",
                         "REVIEWING is not a pass; the pack's 通过 arrives only with COMPLETED")
        self.ledger.transition("t-3", "COMPLETED")
        after = build_operation_progress(self.ledger, "t-3", now="2026-10-10T00:00:10Z")
        self.assertEqual(after["state"], "PASSED")

    def test_a_finished_trial_answers_write_only_and_target_behaviour_stays_a_gap(self) -> None:
        self.ledger.create("p-1", "pkey-1")
        self.ledger.create("c-1", "ckey-1")
        self.ledger.attach_child("p-1", "c-1")
        self.ledger.transition("c-1", "PLANNING")
        self.ledger.transition("c-1", "RUNNING")
        self.ledger.transition("c-1", "COMPLETED")
        trial = build_isolated_trial(self.ledger, "p-1", now="2026-10-10T00:00:00Z")
        validate(trial, TRIAL_SCHEMA)
        self.assertEqual(trial["separated_results"]["write"]["status"], "PASSED")
        self.assertEqual(trial["separated_results"]["target_behaviour"]["status"], "UNKNOWN")
        self.assertEqual(trial["separated_results"]["target_behaviour"]["basis"], "NO_PRODUCER",
                         "the source succeeding must not become the target's verdict (pack rule ①)")
        self.assertIn("TARGET_BEHAVIOUR_CONFIRMATION", trial["producer_gaps"])

    def test_a_reconciled_effect_is_what_answers_target_behaviour(self) -> None:
        self.ledger.create("p-2", "pkey-2")
        self.ledger.create("c-2", "ckey-2")
        self.ledger.attach_child("p-2", "c-2")
        self.ledger.record_external_effect("c-2", "eff-1", "apply-rule", "sha256:intent")
        mid = build_isolated_trial(self.ledger, "p-2", now="2026-10-10T00:00:00Z")
        self.assertEqual(mid["separated_results"]["target_behaviour"]["status"], "PENDING",
                         "a recorded-but-unreconciled effect is pending, and pending is not a pass")
        self.assertIn("TARGET_BEHAVIOUR_CONFIRMATION", mid["producer_gaps"])
        for state in sorted(EXTERNAL_EFFECT_STATES - {"PENDING"}):
            self.ledger.reconcile_external_effect("c-2", "eff-1", state, "sha256:observed")
            record = build_isolated_trial(self.ledger, "p-2", now="2026-10-10T00:01:00Z")
            validate(record, TRIAL_SCHEMA)
            expected = {"CONFIRMED": "PASSED", "ABSENT": "ABSENT", "CONFLICT": "CONFLICT"}[state]
            self.assertEqual(record["separated_results"]["target_behaviour"]["status"], expected)
            self.assertEqual(record["separated_results"]["target_behaviour"]["basis"],
                             "EXTERNAL_EFFECT_RECONCILED")
            self.assertNotIn("TARGET_BEHAVIOUR_CONFIRMATION", record["producer_gaps"],
                             "the gap must close when the producer really answers, and only then")
            break  # CONFIRMED first; the ledger refuses downgrading a confirmed effect afterwards

    def test_isolation_is_answered_from_an_execution_row_or_stays_a_gap(self) -> None:
        self.ledger.create("p-3", "pkey-3")
        self.ledger.create("c-3", "ckey-3")
        self.ledger.attach_child("p-3", "c-3")
        without = build_isolated_trial(self.ledger, "p-3", now="2026-10-10T00:00:00Z")
        self.assertEqual(without["isolation"], {"basis": "NONE", "value": None})
        self.assertIn("TRIAL_ISOLATION", without["producer_gaps"])
        with_row = build_isolated_trial(self.ledger, "p-3", now="2026-10-10T00:00:00Z",
                                        executions=[{"execution_id": "c-3", "worktree_id": "wt-77",
                                                     "session_id": "s-1"}])
        validate(with_row, TRIAL_SCHEMA)
        self.assertEqual(with_row["isolation"], {"basis": "WORKTREE_ID", "value": "wt-77"})
        self.assertNotIn("TRIAL_ISOLATION", with_row["producer_gaps"])

    def test_a_trial_with_no_child_says_absent_rather_than_idle(self) -> None:
        self.ledger.create("p-4", "pkey-4")
        trial = build_isolated_trial(self.ledger, "p-4", now="2026-10-10T00:00:00Z")
        validate(trial, TRIAL_SCHEMA)
        self.assertIsNone(trial["child_task_id"])
        self.assertEqual(trial["separated_results"]["write"]["status"], "ABSENT")


class NegativeControlTests(unittest.TestCase):
    """The schemas must refuse the shapes a well-meaning page would otherwise invent."""

    def base_progress(self) -> dict:
        return {
            "schema_version": "worklab/operation-progress/v1", "task_id": "t", "observed_at": "2026-10-10T00:00:00Z",
            "state": "RUNNING", "ledger_status": "RUNNING",
            "last_trusted_progress": {"state": "RUNNING", "at": "2026-10-10T00:00:00Z", "basis": "LEDGER_HEARTBEAT"},
            "transport_state": "ONLINE", "producer_gaps": ["SUBMITTING_STAGE"],
        }

    def test_the_contract_refuses_an_invented_stage_and_a_silently_dropped_gap(self) -> None:
        with self.assertRaises(jsonschema.ValidationError):
            validate({**self.base_progress(), "state": "SUBMITTING"}, PROGRESS_SCHEMA)
        for broken in ({**self.base_progress(), "progress_percent": 60},
                       {k: v for k, v in self.base_progress().items() if k != "producer_gaps"}):
            with self.assertRaises(jsonschema.ValidationError,
                                   msg=f"accepted {sorted(set(self.base_progress()) - set(broken)) or 'an extra field'}"):
                validate(broken, PROGRESS_SCHEMA)

    def test_the_trial_contract_refuses_a_stage_result_without_a_basis(self) -> None:
        trial = {
            "schema_version": "worklab/isolated-trial/v1", "trial_id": "x", "parent_task_id": "p",
            "child_task_id": "c", "observed_at": "2026-10-10T00:00:00Z",
            "isolation": {"basis": "NONE", "value": None},
            "separated_results": {"write": {"status": "PASSED"},
                                  "native_readback": {"status": "UNKNOWN", "basis": "NO_PRODUCER"},
                                  "target_behaviour": {"status": "UNKNOWN", "basis": "NO_PRODUCER"}},
            "producer_gaps": ["SUBMITTING_STAGE"],
        }
        with self.assertRaises(jsonschema.ValidationError):
            validate(trial, TRIAL_SCHEMA)
        trial["separated_results"]["write"]["basis"] = "LEDGER_STATE"
        validate(trial, TRIAL_SCHEMA)


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
