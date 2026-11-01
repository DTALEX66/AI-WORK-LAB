"""CL-04 gate: a repair pack gets a durable lifecycle, and every transition has to earn itself.

CL-03 could prepare and export material; nothing remembered that the material existed. This module uses the
canonical store's `action_plans` table (shipped with zero access methods and zero rows) as the one place a
pack identity lives, and the tests insist on the parts an "approval feature" usually fakes:

* **recording is not deciding.** The projection/export path can only store WAITING_APPROVAL or BLOCKED. The
  test forges APPROVED and a `sent=true` claim and proves both are refused before a row exists.
* **approval is a grant that resolves.** A grant id that is absent, expired, or scoped to another work unit
  is refused, and an approval without any grant is refused by name. The reader mirrors Control's own
  `_trusted_grants`; a fixture is fed to both so the two copies cannot drift.
* **claims never collapse.** `copiedByUser` and `userDeclaredHandoff` are writable statements; the external
  receipt is not. A user saying "I handed it over" leaves `externalReceipt.received=false` forever until an
  imported document fills it (CL-05).
* **closing needs evidence.** SUCCEEDED needs reproducible/independent evidence with a reference; a
  self-report cannot close anything, and a closed record takes no further outcome or claim.
* **restart and retry.** The same pack file re-recorded is a no-op at version 1; a reopened store returns
  the same issue fingerprint and the same evidence refs. A stale `expected_version` is refused, not applied.

The retention rule is pinned here too: `action_plans` holds current state, so a retention ceiling on it is
refused rather than deleting the row a later result is checked against.
"""
from __future__ import annotations

import copy
import json
import sqlite3
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "services" / "control", ROOT / "packages" / "client-neutral-core" / "scripts"):
    sys.path.insert(0, str(entry))

import control_service  # noqa: E402
import project_temp  # noqa: E402
import repair_pack_projection as projection  # noqa: E402
import repair_state  # noqa: E402
from canonical_store import RETENTION_EXEMPT_TABLES, CanonicalStore  # noqa: E402

GENERATED_AT = "2026-10-23T00:00:00Z"
FINGERPRINT = "a" * 16
REGISTRY = {"entries": [
    {"id": "codex", "display_name": "Codex", "support_level": "deep",
     "operations": ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"]},
]}


def issue_row(fingerprint: str = FINGERPRINT, project: str = "work-lab") -> dict:
    return {
        "schemaVersion": "workflow/issue/v1", "fingerprint": fingerprint, "class": "SOURCE_STALE",
        "projectId": project, "subject": "subject", "origin": "telemetry_events",
        "evidenceRef": f"telemetry_events:{fingerprint}", "priority": "P2",
        "priorityRule": "rule", "safeToReread": True, "firstSeenAt": GENERATED_AT,
        "lastSeenAt": GENERATED_AT, "occurrences": 1, "magnitude": {}, "detail": "d",
        "status": "OPEN", "softwareId": None, "softwareVersion": None,
        "softwareVersionSource": "unattributable",
    }


def make_pack(project_root: Path, *, gate: bool = True) -> dict:
    project_root.mkdir(parents=True, exist_ok=True)
    if gate:
        entry = project_root / projection.OWN_GATE_RELATIVE_PATH
        entry.parent.mkdir(parents=True, exist_ok=True)
        entry.write_text("# gate fixture\n", encoding="utf-8")
    projects = [{"project_id": "work-lab", "root_path": project_root.as_posix(),
                 "display_name": "work-lab", "status": "REGISTERED"}]
    out = projection.project_repair_packs(issues=[issue_row()], projects=projects, registry=REGISTRY,
                                          adapters=["codex"], generated_at=GENERATED_AT)
    return out["packs"][0]


class RepairStateTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("repair-state-")
        self.runtime = Path(self.fixture)
        self.project = self.runtime / "project"
        self.store = CanonicalStore(self.runtime / "canonical.sqlite")
        self.pack = make_pack(self.project)

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    def record(self, pack: dict | None = None) -> dict:
        return repair_state.record_pack(self.store, pack or self.pack)

    def approved(self, grants: dict[str, str] | None = None) -> dict:
        recorded = self.record()
        return repair_state.approve_pack(
            self.store, self.pack["packId"],
            authorization_ref="grant-1",
            grants=grants or {"grant-1": f"work-unit:{self.pack['packId']}"},
            expected_version=recorded["version"], approved_at="2026-10-23T01:00:00Z")

    def write_grants(self, entries: list[dict]) -> Path:
        path = self.runtime / "control-trusted-grants.json"
        path.write_text(json.dumps({"schema_version": control_service.GRANT_RECORD_SCHEMA,
                                    "grants": entries}, ensure_ascii=False), encoding="utf-8")
        return path


class RecordTests(RepairStateTestCase):
    def test_a_recorded_pack_survives_a_restart_with_the_same_issue_and_material(self) -> None:
        first = self.record()
        self.assertEqual("WAITING_APPROVAL", first["status"])
        self.assertEqual(1, first["version"])
        self.assertTrue(first["changed"])
        self.store.close()

        reopened = CanonicalStore(self.runtime / "canonical.sqlite")
        try:
            stored = repair_state.read_record(reopened, self.pack["packId"])
            self.assertIsNotNone(stored, "a restarted store lost the row it just wrote")
            self.assertEqual(self.pack["packId"], stored["planId"])
            self.assertEqual(self.pack["binds"]["issueFingerprints"],
                             stored["payload"]["pack"]["binds"]["issueFingerprints"])
            self.assertEqual(self.pack["binds"]["evidenceRefs"],
                             stored["payload"]["pack"]["binds"]["evidenceRefs"])
            text = projection.render_handoff_text(stored["payload"]["pack"])
            for ref in self.pack["binds"]["evidenceRefs"]:
                self.assertIn(ref, text)
            self.assertEqual([], projection.validate_handoff_text(stored["payload"]["pack"], text))
        finally:
            reopened.close()
            self.store = CanonicalStore(self.runtime / "canonical.sqlite")

    def test_repeating_the_same_record_is_a_no_op_at_the_same_version(self) -> None:
        first = self.record()
        again = self.record()
        self.assertFalse(again["changed"], "a retried record minted a second version")
        self.assertEqual(first["version"], again["version"])
        self.assertEqual(1, len(repair_state.list_records(self.store)))

    def test_an_export_cannot_write_approved(self) -> None:
        forged = copy.deepcopy(self.pack)
        forged["status"] = "APPROVED"
        with self.assertRaises(ValueError) as caught:
            self.record(forged)
        self.assertIn("REPAIR_RECORD_NOT_A_DRAFT", str(caught.exception))
        lying = copy.deepcopy(self.pack)
        lying["handoff"]["sent"] = True
        with self.assertRaises(ValueError) as caught:
            self.record(lying)
        self.assertIn("REPAIR_RECORD_INVALID", str(caught.exception))
        self.assertEqual([], repair_state.list_records(self.store), "a refused record left a row behind")

    def test_an_unknown_field_is_refused_with_the_writable_vocabulary(self) -> None:
        with self.assertRaises(ValueError) as caught:
            self.store.save_action_plan({"planId": "p", "projectId": "work-lab", "status": "BLOCKED",
                                         "payload": {}, "approved_by": "self"})
        message = str(caught.exception)
        self.assertIn("approved_by", message)
        self.assertIn("approvedAt", message, "the refusal must name the vocabulary it would accept")
        with self.assertRaises(ValueError) as caught:
            self.store.save_action_plan({"planId": "p", "status": "BLOCKED", "payload": {}})
        self.assertIn("projectId", str(caught.exception))
        self.assertEqual([], repair_state.list_records(self.store))

    def test_a_stale_version_cannot_overwrite_a_newer_write(self) -> None:
        first = self.record()
        second = repair_state.declare_handoff(self.store, self.pack["packId"], claim="copiedByUser",
                                              declared_at="2026-10-23T02:00:00Z", channel="clipboard",
                                              expected_version=first["version"])
        self.assertEqual(2, second["version"])
        with self.assertRaises(ValueError) as caught:
            repair_state.declare_handoff(self.store, self.pack["packId"], claim="userDeclaredHandoff",
                                         declared_at="2026-10-23T03:00:00Z", channel="chat",
                                         claimed_recipient="codex",
                                         expected_version=first["version"])
        self.assertIn("ACTION_PLAN_VERSION_CONFLICT", str(caught.exception))
        stored = repair_state.read_record(self.store, self.pack["packId"])
        self.assertEqual(2, stored["version"])
        self.assertFalse(stored["payload"]["handoffRecord"]["userDeclaredHandoff"]["declared"],
                         "the refused write still landed")
        updated = repair_state.declare_handoff(
            self.store, self.pack["packId"], claim="userDeclaredHandoff",
            declared_at="2026-10-23T03:00:00Z", channel="chat", claimed_recipient="codex",
            expected_version=stored["version"])
        self.assertEqual(3, updated["version"])
        with self.assertRaises(ValueError) as caught:
            self.store.save_action_plan({"planId": self.pack["packId"], "projectId": "work-lab",
                                         "status": "WAITING_APPROVAL", "payload": {"other": True}})
        self.assertIn("expected_version is required", str(caught.exception))


class ApprovalTests(RepairStateTestCase):
    def test_approval_needs_a_grant_that_resolves_and_covers_this_pack(self) -> None:
        recorded = self.record()
        with self.assertRaises(ValueError) as caught:
            repair_state.approve_pack(self.store, self.pack["packId"], authorization_ref="grant-x",
                                      grants={}, expected_version=recorded["version"])
        self.assertIn("REPAIR_GRANT_NOT_FOUND", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            repair_state.approve_pack(self.store, self.pack["packId"], authorization_ref="grant-x",
                                      grants={"grant-x": "work-unit:some-other-pack"},
                                      expected_version=recorded["version"])
        self.assertIn("REPAIR_GRANT_SCOPE_MISMATCH", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            repair_state.approve_pack(self.store, self.pack["packId"], authorization_ref="",
                                      grants={"grant-x": "*"}, expected_version=recorded["version"])
        self.assertIn("REPAIR_GRANT_REQUIRED", str(caught.exception))

        approved = repair_state.approve_pack(
            self.store, self.pack["packId"], authorization_ref="grant-x",
            grants={"grant-x": f"work-unit:{self.pack['packId']}"},
            expected_version=recorded["version"], approved_at="2026-10-23T01:00:00Z")
        self.assertEqual("APPROVED", approved["status"])
        self.assertEqual(2, approved["version"])
        self.assertEqual("grant-x", approved["payload"]["approval"]["authorizationRef"])
        self.assertEqual("2026-10-23T01:00:00Z", approved["approvedAt"])

        retried = repair_state.approve_pack(
            self.store, self.pack["packId"], authorization_ref="grant-x",
            grants={"grant-x": f"work-unit:{self.pack['packId']}"}, expected_version=1)
        self.assertFalse(retried["changed"], "a retried approval bumped the version")
        with self.assertRaises(ValueError) as caught:
            repair_state.approve_pack(self.store, self.pack["packId"], authorization_ref="grant-y",
                                      grants={"grant-y": "*"}, expected_version=2)
        self.assertIn("REPAIR_RECORD_ALREADY_APPROVED", str(caught.exception))

    def test_a_blocked_pack_has_no_verification_route_to_approve(self) -> None:
        blocked = make_pack(self.runtime / "project-no-gate", gate=False)
        self.assertEqual("BLOCKED", blocked["status"])
        recorded = self.record(blocked)
        with self.assertRaises(ValueError) as caught:
            repair_state.approve_pack(self.store, blocked["packId"], authorization_ref="grant-1",
                                      grants={"grant-1": "*"},
                                      expected_version=recorded["version"])
        self.assertIn("REPAIR_RECORD_NOT_APPROVABLE", str(caught.exception))

    def test_an_expired_grant_is_not_a_grant(self) -> None:
        path = self.write_grants([
            {"grant_id": "live", "scope": f"work-unit:{self.pack['packId']}",
             "granted_by": "fixture"},
            {"grant_id": "old", "scope": "*", "expires_at": "2026-10-22T00:00:00Z"},
            {"grant_id": "shape", "granted_by": "fixture"},
        ])
        grants, state = repair_state.load_grants(path, now="2026-10-23T00:00:00Z")
        self.assertEqual({"live": f"work-unit:{self.pack['packId']}"}, grants)
        self.assertEqual(1, state["expired"])
        self.assertEqual(1, state["malformed"])
        recorded = self.record()
        with self.assertRaises(ValueError) as caught:
            repair_state.approve_pack(self.store, self.pack["packId"], authorization_ref="old",
                                      grants=grants, expected_version=recorded["version"])
        self.assertIn("REPAIR_GRANT_NOT_FOUND", str(caught.exception))

    def test_the_grants_reader_agrees_with_the_control_plane_reader(self) -> None:
        path = self.write_grants([
            {"grant_id": "live", "scope": "work-unit:WL-1", "granted_by": "fixture"},
            {"grant_id": "any", "scope": "*"},
            {"grant_id": "old", "scope": "*", "expires_at": "2020-01-01T00:00:00Z"},
            {"grant_id": "shape"},
            "not-an-object",
        ])
        plane = control_service.ControlPlane(self.store, project_root=ROOT,
                                             receipts_path=self.runtime / "control-receipts.jsonl")
        plane_grants, plane_state = plane._trusted_grants()  # noqa: SLF001 - pinning the reader this mirrors
        state_grants, state = repair_state.load_grants(path, now="2026-10-23T00:00:00Z")
        self.assertEqual(plane_grants, state_grants,
                         "two readers of the same authorization record disagree; one of them is now an "
                         "authority nobody reviewed")
        for key in ("readable", "grants", "expired", "malformed"):
            self.assertEqual(plane_state[key], state[key], key)
        self.assertEqual(path.name, state["path"])


class HandoffClaimTests(RepairStateTestCase):
    def test_the_user_statement_never_fills_the_external_receipt(self) -> None:
        recorded = self.record()
        copied = repair_state.declare_handoff(self.store, self.pack["packId"], claim="copiedByUser",
                                              declared_at="2026-10-23T02:00:00Z", channel="clipboard",
                                              expected_version=recorded["version"])
        record = copied["payload"]["handoffRecord"]
        self.assertTrue(record["copiedByUser"]["declared"])
        self.assertFalse(record["userDeclaredHandoff"]["declared"])
        self.assertFalse(record["externalReceipt"]["received"])
        with self.assertRaises(ValueError) as caught:
            repair_state.declare_handoff(self.store, self.pack["packId"], claim="externalReceipt",
                                         expected_version=copied["version"])
        self.assertIn("REPAIR_CLAIM_EXTERNAL_ONLY", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            repair_state.declare_handoff(self.store, self.pack["packId"], claim="sent",
                                         expected_version=copied["version"])
        self.assertIn("REPAIR_CLAIM_UNKNOWN", str(caught.exception))
        stored = repair_state.read_record(self.store, self.pack["packId"])
        self.assertFalse(stored["payload"]["handoffRecord"]["externalReceipt"]["received"])
        self.assertFalse(stored["payload"]["pack"]["handoff"]["externalReceipt"]["received"],
                         "the immutable snapshot must never be edited into a receipt claim")

    def test_declaring_the_same_statement_twice_does_not_bump_the_version(self) -> None:
        recorded = self.record()
        first = repair_state.declare_handoff(self.store, self.pack["packId"], claim="userDeclaredHandoff",
                                             declared_at="2026-10-23T02:00:00Z", channel="chat",
                                             claimed_recipient="codex",
                                             expected_version=recorded["version"])
        second = repair_state.declare_handoff(self.store, self.pack["packId"], claim="userDeclaredHandoff",
                                              declared_at="2026-10-23T02:05:00Z", channel="chat",
                                              claimed_recipient="codex",
                                              expected_version=first["version"])
        self.assertFalse(second["changed"])
        self.assertEqual(first["version"], second["version"])
        self.assertEqual("2026-10-23T02:00:00Z",
                         second["payload"]["handoffRecord"]["userDeclaredHandoff"]["declaredAt"])


class OutcomeTests(RepairStateTestCase):
    def test_an_outcome_cannot_be_written_against_a_draft(self) -> None:
        recorded = self.record()
        with self.assertRaises(ValueError) as caught:
            repair_state.record_outcome(self.store, self.pack["packId"], outcome="FAILED",
                                        evidence_level="self", evidence_refs=["x:1"],
                                        expected_version=recorded["version"])
        self.assertIn("REPAIR_RECORD_NOT_APPROVED", str(caught.exception))

    def test_a_self_report_cannot_close_a_problem(self) -> None:
        approved = self.approved()
        with self.assertRaises(ValueError) as caught:
            repair_state.record_outcome(self.store, self.pack["packId"], outcome="SUCCEEDED",
                                        evidence_level="self",
                                        evidence_refs=["telemetry_events:abc"],
                                        expected_version=approved["version"])
        self.assertIn("REPAIR_OUTCOME_UNEVIDENCED", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            repair_state.record_outcome(self.store, self.pack["packId"], outcome="SUCCEEDED",
                                        evidence_level="reproducible", evidence_refs=[],
                                        expected_version=approved["version"])
        self.assertIn("at least one evidence reference", str(caught.exception))
        stored = repair_state.read_record(self.store, self.pack["packId"])
        self.assertEqual("APPROVED", stored["status"])
        self.assertIsNone(stored["payload"]["outcome"])

    def test_a_failed_outcome_is_durable_and_terminal(self) -> None:
        approved = self.approved()
        failed = repair_state.record_outcome(
            self.store, self.pack["packId"], outcome="FAILED", evidence_level="self",
            evidence_refs=["telemetry_events:still-present"],
            expected_version=approved["version"], recorded_at="2026-10-23T04:00:00Z",
            detail="the bound issue is still open")
        self.assertEqual("FAILED", failed["status"])
        stored = repair_state.read_record(self.store, self.pack["packId"])
        self.assertEqual("FAILED", stored["payload"]["outcome"]["status"])
        self.assertEqual(["telemetry_events:still-present"],
                         stored["payload"]["outcome"]["evidenceRefs"])
        with self.assertRaises(ValueError) as caught:
            repair_state.record_outcome(self.store, self.pack["packId"], outcome="SUCCEEDED",
                                        evidence_level="independent",
                                        evidence_refs=["telemetry_events:gone"],
                                        expected_version=stored["version"])
        self.assertIn("REPAIR_RECORD_TERMINAL", str(caught.exception))
        with self.assertRaises(ValueError) as caught:
            repair_state.declare_handoff(self.store, self.pack["packId"], claim="copiedByUser",
                                         expected_version=stored["version"])
        self.assertIn("REPAIR_RECORD_TERMINAL", str(caught.exception))

    def test_a_verified_success_closes_the_record_at_a_new_version(self) -> None:
        approved = self.approved()
        succeeded = repair_state.record_outcome(
            self.store, self.pack["packId"], outcome="SUCCEEDED", evidence_level="reproducible",
            evidence_refs=["telemetry_events:rerun"], expected_version=approved["version"],
            recorded_at="2026-10-23T04:00:00Z")
        self.assertEqual("SUCCEEDED", succeeded["status"])
        self.assertEqual(3, succeeded["version"])
        retried = repair_state.record_outcome(
            self.store, self.pack["packId"], outcome="SUCCEEDED", evidence_level="reproducible",
            evidence_refs=["telemetry_events:rerun"], expected_version=1,
            recorded_at="2026-10-23T05:00:00Z")
        self.assertFalse(retried["changed"], "a retried outcome tried to rewrite a closed record")

    def test_history_names_every_transition(self) -> None:
        recorded = self.record()
        approved = repair_state.approve_pack(
            self.store, self.pack["packId"], authorization_ref="grant-1",
            grants={"grant-1": f"work-unit:{self.pack['packId']}"},
            expected_version=recorded["version"], approved_at="2026-10-23T01:00:00Z")
        closed = repair_state.record_outcome(
            self.store, self.pack["packId"], outcome="FAILED", evidence_level="reproducible",
            evidence_refs=["telemetry_events:still-present"], expected_version=approved["version"],
            recorded_at="2026-10-23T04:00:00Z")
        events = [entry["event"] for entry in closed["payload"]["history"]]
        self.assertEqual(["APPROVED", "OUTCOME_RECORDED"], events)


class RetentionAndMigrationTests(RepairStateTestCase):
    def test_a_retention_ceiling_cannot_delete_a_plan_row(self) -> None:
        self.assertIn("action_plans", RETENTION_EXEMPT_TABLES)
        self.record()
        with self.assertRaises(ValueError) as caught:
            self.store.enforce_retention({"action_plans": 1}, allow_prune=True)
        self.assertIn("RETENTION_TABLE_NOT_PERMITTED", str(caught.exception))
        self.assertEqual(1, len(repair_state.list_records(self.store)),
                         "a refused retention policy still deleted the row")

    def test_a_pre_v5_database_gains_the_lifecycle_columns(self) -> None:
        legacy = self.runtime / "legacy.sqlite"
        connection = sqlite3.connect(legacy)
        connection.executescript(
            """
            CREATE TABLE schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT NOT NULL);
            INSERT INTO schema_migrations VALUES (1, '2026-10-01T00:00:00Z');
            INSERT INTO schema_migrations VALUES (2, '2026-10-01T00:00:00Z');
            INSERT INTO schema_migrations VALUES (3, '2026-10-01T00:00:00Z');
            INSERT INTO schema_migrations VALUES (4, '2026-10-01T00:00:00Z');
            CREATE TABLE action_plans (
                plan_id TEXT PRIMARY KEY,
                project_id TEXT NOT NULL,
                status TEXT NOT NULL,
                created_at TEXT NOT NULL,
                approved_at TEXT,
                payload TEXT NOT NULL
            );
            INSERT INTO action_plans VALUES ('legacy-plan', 'work-lab', 'WAITING_APPROVAL',
                                             '2026-10-02T00:00:00Z', NULL, '{"schemaVersion": "legacy"}');
            """
        )
        connection.commit()
        connection.close()
        migrated = CanonicalStore(legacy)
        try:
            versions = {row[0] for row in migrated._conn.execute(  # noqa: SLF001 - the migration is the subject
                "SELECT version FROM schema_migrations")}
            self.assertIn(5, versions)
            row = migrated.read_action_plan("legacy-plan")
            self.assertEqual(1, row["version"], "an existing row must start at version 1, not at 0 or NULL")
            self.assertEqual("2026-10-02T00:00:00Z", row["updatedAt"],
                             "updated_at must be backfilled from created_at, not invented")
            self.assertEqual("PARSED", row["payloadParseState"])
        finally:
            migrated.close()


class CliTests(RepairStateTestCase):
    def test_the_cli_refuses_to_create_a_store(self) -> None:
        missing = self.runtime / "no-such-runtime"
        code = repair_state.main(["list", "--runtime-root", str(missing)])
        self.assertEqual(3, code)
        self.assertFalse((missing / "canonical.sqlite").exists())

    def test_the_cli_records_a_pack_file_and_prints_the_lifecycle(self) -> None:
        pack_file = self.runtime / f"{self.pack['packId']}.json"
        pack_file.write_text(json.dumps(self.pack, ensure_ascii=False), encoding="utf-8")
        code = repair_state.main(["record", "--runtime-root", str(self.runtime),
                                  "--pack-file", str(pack_file)])
        self.assertEqual(0, code)
        stored = repair_state.read_record(self.store, self.pack["packId"])
        self.assertIsNotNone(stored)
        self.assertEqual("WAITING_APPROVAL", stored["status"])
        shown = repair_state.main(["show", "--runtime-root", str(self.runtime),
                                   "--plan-id", self.pack["packId"]])
        self.assertEqual(0, shown)


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
