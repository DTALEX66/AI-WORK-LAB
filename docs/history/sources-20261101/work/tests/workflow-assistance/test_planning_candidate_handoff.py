"""Gate: an authorized PlanningCandidate becomes a real work unit, and nothing else does.

AG-16 built the planning contract (`plan_candidate.build_candidate` / `check_candidate`) and
`scripts/audit/ag16_handback_roundtrip.py` round-tripped it, but the repo had ZERO consumers: a candidate
was produced, judged, and thrown away. That is plan-only, not progress. `work-unit.materialize` is the
consumer, and what it is allowed to claim is exactly what this file pins:

1. a candidate whose grant resolves in the LOCAL authorization record lands as a QUEUED work unit whose
   stored record reads back with the candidate's own identity (task_id == workUnitId, digest recorded);
2. a candidate whose verdict is not authorized is REFUSED with the verdict status in the reason and the
   store stays empty — the refusal is the honest answer, not a fallback;
3. a payload that *claims* authorization (`authorized: true`, a pasted verdict object, a self-declared
   scope) never becomes ACCEPTED: the claim is named in the refusal and ignored, because a claim is not
   evidence and the re-check runs server-side on every call;
4. the grant must cover THIS work unit — one grant id cannot authorize every plan;
5. a foreign idempotency key conflicts instead of double-writing, exactly like `work-unit.create`,
   because both operations run through the same `_write_work_unit` chain (gate, store, readback, receipt);
6. honest statuses only: the result says `planExecuted: false` and names `work-unit.dispatch` as
   NOT_IMPLEMENTED, and the candidate's own text stays in the store, out of the result and out of the
   read-only projection.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import json
import re
import sys
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "services" / "control", ROOT / "services" / "orchestration",
              ROOT / "services" / "task-governance", ROOT / "packages" / "client-neutral-core" / "scripts"):
    sys.path.insert(0, str(entry))

import jsonschema  # noqa: E402
import control_service  # noqa: E402
from plan_candidate import build_candidate  # noqa: E402
from project_temp import fixture_dir  # noqa: E402
from snapshot_api import project_task_record  # noqa: E402

RESULT_SCHEMA = json.loads((ROOT / "packages/contracts/schemas/workflow/"
                            "control-operation-result.schema.json").read_text(encoding="utf-8"))
RESULT_VALIDATOR = jsonschema.Draft202012Validator(RESULT_SCHEMA, format_checker=jsonschema.FormatChecker())

WORK_UNIT_ID = "WL-CAND-HANDOFF-1"
GRANT_ID = "grant-owner-20261008"
PLAN_TEXT = "把候选里的这条变更真的改掉：docs/current/live-doc-paths.md"


def candidate_draft(**over) -> dict:
    """A well-formed PlanningCandidate draft — every factual field present, nothing self-conferred."""
    draft = {
        "planningSoftware": "fixture-planning-end",
        "workUnitId": WORK_UNIT_ID,
        "taskRevision": 1,
        "baseline": {"commit": "0" * 40},
        "contextRef": "docs/current/workflow-assistance",
        "contextDigest": "d" * 64,
        "changes": [PLAN_TEXT],
        "verification": ["python -m unittest -q test_planning_candidate_handoff"],
        "unresolved": [],
        "targetCapability": "store",
        "authorizationRef": GRANT_ID,
    }
    draft.update(over)
    return draft


def request_payload(**over) -> dict:
    payload = {
        "schema_version": "worklab/control-operation/v1",
        "operation": "work-unit.materialize",
        "project_id": "work-lab",
        "task_id": WORK_UNIT_ID,
        "revision": 1,
        "attempt": None,
        "scope": {"boundaries": ["services/control"], "granted_by": "owner 2026-10-08 批次 C 授权"},
        "expected_version": None,
        "idempotency_key": "idem-cand-0001",
        "actor": "qoder-session",
        "requested_at": "2026-10-08T00:00:00Z",
        "payload": {"candidate": candidate_draft()},
    }
    payload.update(over)
    return payload


class StubRegistry:
    """The smallest thing that behaves like the repo's CapabilityRoleRegistry for one capability."""

    def __init__(self, *capabilities: str) -> None:
        self.capabilities = set(capabilities)

    def roles_with_capability(self, capability: str) -> list[str]:
        return ["executor"] if capability in self.capabilities else []


class CandidateHandoffTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = fixture_dir(prefix="cand-handoff-")
        self.plane = control_service.build_plane(self.runtime, ROOT)

    def tearDown(self) -> None:
        self.plane.store.close()

    # -- the local authorization record -----------------------------------
    def seed_grants(self, *entries: dict) -> None:
        document = {"schema_version": control_service.GRANT_RECORD_SCHEMA,
                    "grants": list(entries) or [{"grant_id": GRANT_ID, "scope": f"work-unit:{WORK_UNIT_ID}",
                                                 "granted_by": "owner"}]}
        (self.runtime / control_service.TRUSTED_GRANTS_PATH).write_text(
            json.dumps(document, ensure_ascii=False), encoding="utf-8")

    def assert_result_shape(self, result: dict) -> None:
        errors = list(RESULT_VALIDATOR.iter_errors(result))
        self.assertEqual(errors, [], json.dumps({"errors": [e.message for e in errors],
                                                 "result": result}, ensure_ascii=False)[:900])

    def assert_nothing_written(self, note: str) -> None:
        self.assertEqual(self.plane.store.list_tasks(), [], f"{note}: a refused candidate wrote a row")

    # -- 1 authorized candidate -> a real work unit ------------------------
    def test_an_authorized_candidate_lands_as_a_work_unit_with_the_same_identity(self) -> None:
        self.seed_grants()
        result = self.plane.execute(request_payload())
        self.assert_result_shape(result)
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        self.assertEqual(result["task_id"], WORK_UNIT_ID)

        rows = self.plane.store.list_tasks()
        self.assertEqual([row["task_id"] for row in rows], [WORK_UNIT_ID],
                         "the work unit must be the one the candidate names")
        stored = rows[0]
        self.assertEqual(stored["status"], "QUEUED")
        projected = project_task_record(stored)
        # the readback is the stored row, not a handler return: every projected field must match
        self.assertEqual({k: result["readback"][k] for k in projected}, projected)
        self.assertEqual(result["readback"]["taskId"], WORK_UNIT_ID)
        # and the candidate's own content identity is durable in the store
        recorded = stored["checkpoint"]["planningCandidate"]
        self.assertEqual(recorded["contentDigest"], build_candidate(candidate_draft())["contentDigest"])
        self.assertEqual(recorded["workUnitId"], WORK_UNIT_ID)
        self.assertEqual(result["receipt"]["receipt_id"], f"work-unit.materialize:{WORK_UNIT_ID}")
        self.assertEqual(result["receipt"]["kind"], "WORK_UNIT_QUEUED")
        self.assertEqual(len(result["receipt"]["digest"]), 64)
        self.assertEqual(result["evidence_level"], "SYNTHETIC",
                         "an in-repo fixture store may not claim more than SYNTHETIC")

    def test_the_landed_unit_says_the_plan_itself_was_not_executed(self) -> None:
        """Honesty clause: creating the unit is real; running the plan is not, and the result states it."""
        self.seed_grants()
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "ACCEPTED")
        self.assertIs(result["readback"]["planExecuted"], False)
        self.assertEqual(result["readback"]["executorDispatch"], "NOT_IMPLEMENTED(work-unit.dispatch)")
        self.assertEqual(result["readback"]["written"], True)
        self.assertIn("work-unit.dispatch", result["next_action"])
        # the operation table is the single place dispatch support is declared
        self.assertFalse(control_service.OPERATIONS["work-unit.dispatch"].implemented)

    # -- 2 an unauthorized candidate writes nothing -------------------------
    def test_a_candidate_with_no_grant_record_is_refused_and_writes_nothing(self) -> None:
        # deliberately no seed_grants(): no record at all is the default-deny case
        result = self.plane.execute(request_payload())
        self.assert_result_shape(result)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "CANDIDATE_NOT_AUTHORIZED")
        self.assertIn("AWAITING_AUTHORIZATION", result["reason"])
        self.assertIn("授权记录不存在", result["reason"])
        self.assertIsNone(result["receipt"])
        self.assertIsNone(result["readback"])
        self.assert_nothing_written("no grant")

    def test_a_grant_that_is_not_in_the_record_does_not_become_a_work_unit(self) -> None:
        self.seed_grants({"grant_id": "some-other-grant", "scope": f"work-unit:{WORK_UNIT_ID}"})
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "REFUSED", result["reason"])
        self.assertEqual(result["reason_code"], "CANDIDATE_NOT_AUTHORIZED")
        self.assertIn(GRANT_ID, result["reason"], "the reason must name the grant that did not resolve")
        self.assert_nothing_written("unknown grant id")

    def test_a_blocking_candidate_stays_refused_even_with_a_valid_grant(self) -> None:
        """plan_candidate's order is deliberate: unresolved questions outrank a grant."""
        self.seed_grants()
        payload = request_payload()
        payload["payload"]["candidate"] = candidate_draft(
            unresolved=[{"id": "Q1", "blocking": True, "title": "which executor runs this?"}])
        result = self.plane.execute(payload)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "CANDIDATE_NOT_AUTHORIZED")
        self.assertIn("NEEDS_INPUT", result["reason"])
        self.assert_nothing_written("blocking items")

    def test_an_expired_grant_is_not_an_authorization(self) -> None:
        self.seed_grants({"grant_id": GRANT_ID, "scope": f"work-unit:{WORK_UNIT_ID}",
                          "expires_at": "2020-01-01T00:00:00Z"})
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "CANDIDATE_NOT_AUTHORIZED")
        self.assert_nothing_written("expired grant")

    def test_an_unreadable_grant_record_fails_closed(self) -> None:
        (self.runtime / control_service.TRUSTED_GRANTS_PATH).write_text("{not json", encoding="utf-8")
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn("读不开", result["reason"])
        self.assert_nothing_written("unreadable record")

    # -- 3 the grant must cover THIS work unit ------------------------------
    def test_a_grant_for_another_work_unit_is_not_reusable(self) -> None:
        self.seed_grants({"grant_id": GRANT_ID, "scope": "work-unit:WL-SOMETHING-ELSE"})
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "GRANT_SCOPE_MISMATCH")
        self.assertIn("WL-SOMETHING-ELSE", result["reason"])
        self.assert_nothing_written("out-of-scope grant")

    def test_an_explicit_global_grant_scope_is_honoured_and_shown(self) -> None:
        self.seed_grants({"grant_id": GRANT_ID, "scope": "*"})
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        self.assertEqual(result["readback"]["grantScope"], "*")

    # -- 4 a payload claim is not evidence ----------------------------------
    def test_a_claimed_authorization_in_the_payload_never_becomes_accepted(self) -> None:
        payload = request_payload()
        payload["payload"].update({
            "authorized": True,
            "approved": "owner said yes",
            "permission_scope": f"work-unit:{WORK_UNIT_ID}",
            "verdict": {"status": "AUTHORIZED_NOT_EXECUTED", "grant": GRANT_ID},
        })
        result = self.plane.execute(payload)
        self.assert_result_shape(result)
        self.assertNotEqual(result["status"], "ACCEPTED")
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "CANDIDATE_NOT_AUTHORIZED")
        # the claim is not hidden: it is named as ignored
        for claim in ("authorized", "approved", "permission_scope"):
            self.assertIn(claim, result["reason"])
        self.assert_nothing_written("self-conferred grant")

    def test_a_candidate_that_grants_itself_is_refused_and_the_claim_is_reported(self) -> None:
        """plan_candidate records self-confer fields inside the candidate; this service reports them."""
        payload = request_payload()
        payload["payload"]["candidate"] = candidate_draft(approved=True, scope="write-everything")
        result = self.plane.execute(payload)
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn("approved", result["reason"])
        self.assert_nothing_written("self-authorized candidate")

    def test_a_real_grant_is_still_a_real_grant_when_the_payload_also_claims_one(self) -> None:
        """The claim must be inert in both directions: it cannot refuse a valid grant, only be ignored."""
        self.seed_grants()
        payload = request_payload()
        payload["payload"]["authorized"] = True
        result = self.plane.execute(payload)
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        self.assertIn("authorized", result["readback"]["ignoredSelfClaims"])

    def test_an_over_long_refusal_reason_still_fits_the_result_contract(self) -> None:
        """The echoed grant scope is unbounded text; the answer must stay schema-valid anyway."""
        self.seed_grants({"grant_id": GRANT_ID, "scope": "x" * 4000})
        result = self.plane.execute(request_payload())
        self.assert_result_shape(result)
        self.assertEqual(result["status"], "REFUSED")
        self.assertLessEqual(len(result["reason"]), 2000)
        self.assertTrue(result["reason"].endswith("…（已截断）"), "truncation must announce itself")
        self.assert_nothing_written("oversized scope")

    def test_the_request_cannot_repoint_an_authorized_plan_at_another_work_unit(self) -> None:
        self.seed_grants()
        payload = request_payload(task_id="WL-SOMETHING-ELSE")
        result = self.plane.execute(payload)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "CANDIDATE_IDENTITY_MISMATCH")
        self.assert_nothing_written("re-pointed identity")

    def test_a_malformed_candidate_is_refused_not_repaired(self) -> None:
        self.seed_grants()
        for label, draft in (("not-an-object", {"workUnitId": WORK_UNIT_ID}),
                             ("no-changes", candidate_draft(changes=[])),
                             ("no-baseline-commit", candidate_draft(baseline={"description": "vague"}))):
            with self.subTest(case=label):
                payload = request_payload()
                payload["payload"]["candidate"] = draft
                result = self.plane.execute(payload)
                self.assert_result_shape(result)
                self.assertEqual(result["status"], "REFUSED")
                self.assertIn(result["reason_code"], ("CANDIDATE_INVALID", "CANDIDATE_MISSING"))
        self.assert_nothing_written("malformed candidate")

    # -- 5 the SAME write machinery: idempotency, replay, conflict ----------
    def test_replaying_the_same_key_returns_the_same_unit(self) -> None:
        self.seed_grants()
        first = self.plane.execute(request_payload())
        again = self.plane.execute(request_payload())
        self.assertEqual(first["status"], "ACCEPTED")
        self.assertEqual(again["readback"]["replayed"], True)
        self.assertEqual(again["receipt"]["kind"], "REPLAY")
        self.assertEqual(len(self.plane.store.list_tasks()), 1)

    def test_a_foreign_idempotency_key_conflicts_instead_of_double_writing(self) -> None:
        self.seed_grants()
        self.assertEqual(self.plane.execute(request_payload())["status"], "ACCEPTED")
        hijack = self.plane.execute(request_payload(
            idempotency_key="idem-other-owner-9999",
            payload={"candidate": candidate_draft(changes=["换一条正文"]), "goal": "不该生效"}))
        self.assert_result_shape(hijack)
        self.assertEqual(hijack["status"], "REFUSED")
        self.assertEqual(hijack["reason_code"], "IDEMPOTENCY_CONFLICT")
        rows = self.plane.store.list_tasks()
        self.assertEqual(len(rows), 1, "a conflicting replay wrote a second row")
        self.assertEqual(rows[0]["checkpoint"]["idempotency_key"], "idem-cand-0001",
                         "a refused replay overwrote the original identity")

    def test_an_out_of_boundary_scope_is_refused_before_any_candidate_check(self) -> None:
        self.seed_grants()
        result = self.plane.execute(request_payload(scope={"boundaries": ["E:/somewhere"],
                                                          "granted_by": "owner"}))
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "FORBIDDEN_ROOT")
        self.assert_nothing_written("forbidden root")

    # -- 6 privacy: the plan's text stays in the store ----------------------
    def test_the_candidate_change_text_never_leaves_the_store(self) -> None:
        self.seed_grants()
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "ACCEPTED")
        self.assertNotIn(PLAN_TEXT, json.dumps(result, ensure_ascii=False))
        stored = self.plane.store.list_tasks()[0]
        self.assertIn(PLAN_TEXT, json.dumps(stored, ensure_ascii=False),
                      "the store is the right place for the plan body")
        recorded = stored["checkpoint"]["planningCandidate"]
        self.assertEqual(recorded["changes"], [PLAN_TEXT],
                         "a queued unit without its plan body is an empty shell, not a handoff")
        self.assertEqual(len(recorded["verification"]), 1)
        # the receipt line carries the projection: key names and a digest, never values
        line = json.loads((self.runtime / control_service.RECEIPTS_PATH)
                          .read_text(encoding="utf-8").splitlines()[0])
        self.assertNotIn(PLAN_TEXT, json.dumps(line, ensure_ascii=False))
        self.assertIn("planningCandidate", line["record"]["checkpointKeys"])

    def test_the_store_rejects_the_contract_field_name_and_the_service_records_it_as_grant_ref(self) -> None:
        """canonical_store refuses keys whose name contains 'authorization'; the recorded field is grantRef."""
        self.seed_grants()
        self.assertEqual(self.plane.execute(request_payload())["status"], "ACCEPTED")
        recorded = self.plane.store.list_tasks()[0]["checkpoint"]["planningCandidate"]
        self.assertEqual(recorded["grantRef"], GRANT_ID)
        self.assertNotIn("authorizationRef", recorded)

    def test_capability_refusal_names_the_capability_when_a_registry_is_wired(self) -> None:
        self.seed_grants()
        self.plane.capability_registry = StubRegistry("read")  # nobody advertises "store"
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "REFUSED")
        self.assertIn("REFUSED_CAPABILITY_UNAVAILABLE", result["reason"])
        self.assertIn("store", result["reason"])
        self.assert_nothing_written("unavailable capability")

    def test_an_advertised_capability_still_lands_and_reports_the_check(self) -> None:
        self.seed_grants()
        self.plane.capability_registry = StubRegistry("store")
        result = self.plane.execute(request_payload())
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        self.assertEqual(result["readback"]["capabilityCheck"], "CHECKED")


class ShellSurfaceTests(unittest.TestCase):
    """The thin shell must actually be able to show what this operation answers.

    There is no JS engine on this machine, so the shell cannot be executed here. What CAN be gated
    statically is the failure mode that matters most: a script that reaches for an element id the document
    does not have would render UNKNOWN forever and look like a dead backend instead of a broken page.
    """

    def setUp(self) -> None:
        shell = ROOT / "apps" / "control-surface"
        self.html = (shell / "index.html").read_text(encoding="utf-8")
        self.script = (shell / "control-shell.js").read_text(encoding="utf-8")
        self.css = (shell / "control-shell.css").read_text(encoding="utf-8")

    def _referenced_ids(self) -> set[str]:
        found = set(re.findall(r'el\("([^"]+)"\)', self.script))
        for match in re.finditer(r"const \w*[Vv]iew\w* = \{", self.script):
            start = match.end() - 1
            depth = 0
            for index in range(start, len(self.script)):
                if self.script[index] == "{":
                    depth += 1
                elif self.script[index] == "}":
                    depth -= 1
                    if depth == 0:
                        block = self.script[start:index + 1]
                        found |= {value for key, value in re.findall(r'(\w+): "([^"]+)"', block)
                                  if key != "operation"}
                        break
        return found

    def test_every_element_the_script_reaches_for_exists_in_the_document(self) -> None:
        present = set(re.findall(r'id="([^"]+)"', self.html))
        referenced = self._referenced_ids()
        self.assertTrue(referenced, "the script stopped referencing the document at all")
        self.assertEqual(sorted(referenced - present), [],
                         "the shell would throw on load and show UNKNOWN forever")

    def test_the_shell_offers_the_materialize_action_and_shows_receipt_readback_and_unknown(self) -> None:
        self.assertIn("work-unit.materialize", self.script)
        self.assertIn('id="candidate-json"', self.html)
        self.assertIn('id="materialize-readback"', self.html)
        self.assertIn('id="grant-record"', self.html)
        # receipt, readback, and an explicit UNKNOWN for each — never a blank where a refusal should be
        for marker in ("回执", "读回 UNKNOWN", "状态 UNKNOWN", "支持度 UNKNOWN"):
            with self.subTest(marker=marker):
                self.assertIn(marker, self.script)

    def test_the_shell_claims_no_authority_for_itself(self) -> None:
        """The page must say the server re-checks, not that the page decided."""
        self.assertIn("授权来源", self.script)
        self.assertIn("本地授权记录", self.html)
        self.assertIn("已忽略的自我授权声明", self.script)
        self.assertIn("planExecuted", self.script, "the shell must surface that the plan was not executed")

    def test_the_shell_reaches_only_its_own_origin_and_only_post_as_a_write(self) -> None:
        self.assertEqual({m.group(1) for m in re.finditer(r'fetch\("([^"]+)"', self.script)},
                         {"/api/control/descriptor", "/api/control/operations"})
        self.assertEqual({m.group(1) for m in re.finditer(r'method: "([A-Z]+)"', self.script)}, {"POST"})
        for forbidden in ("http://", "https://"):
            self.assertNotIn(forbidden, self.script)
        self.assertNotIn("style=", self.html, "the CSP allows no inline style; a style attribute is a lie")
        self.assertNotIn("<style", self.html)
        self.assertIn('src="/control-shell.js"', self.html)

    def test_the_script_survives_a_transport_level_refusal_without_lying(self) -> None:
        """A 403/413/400 answer carries a reason_code but no status; the shell must not print "undefined"."""
        self.assertIn("normalizeAnswer", self.script)
        self.assertIn("ANSWER_WITHOUT_STATUS", self.script)
        # no JS engine exists on this machine, so delimiter balance is the cheapest tripwire against a
        # half-applied edit that would leave the whole page dead on load
        for opener, closer in (("{", "}"), ("(", ")"), ("[", "]")):
            self.assertEqual(self.script.count(opener), self.script.count(closer),
                             f"unbalanced {opener}{closer} in control-shell.js")

    def test_no_auth_surface_grew_with_the_candidate_editor(self) -> None:
        controls = re.findall(r"<input\b[^>]*>", self.html.lower())
        self.assertTrue(controls)
        for forbidden in ("password", "api key", "api_key", "token", "oauth", "jwt", "vault",
                          "credential", "login"):
            for control in controls:
                self.assertNotIn(forbidden, control, f"the shell grew an auth control: {control}")
        self.assertNotIn('type="password"', self.html.lower())


class CandidateHandoffTransportTests(unittest.TestCase):
    """The same chain over the loopback boundary, because the shell reaches it over HTTP."""

    def setUp(self) -> None:
        self.runtime = fixture_dir(prefix="cand-handoff-http-")
        self.plane = control_service.build_plane(self.runtime, ROOT)
        self.server = control_service.ControlServer(self.plane)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{self.server.bound_port}"

    def tearDown(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        self.plane.store.close()

    def _post(self, body: dict):
        request = urllib.request.Request(self.base + "/api/control/operations",
                                         data=json.dumps(body).encode("utf-8"),
                                         headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(request, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def _get(self, path: str) -> dict:
        with urllib.request.urlopen(self.base + path, timeout=5) as response:
            return json.loads(response.read().decode("utf-8"))

    def test_a_materialize_over_loopback_lands_in_the_store_the_observer_reads(self) -> None:
        (self.runtime / control_service.TRUSTED_GRANTS_PATH).write_text(
            json.dumps({"schema_version": control_service.GRANT_RECORD_SCHEMA,
                        "grants": [{"grant_id": GRANT_ID, "scope": f"work-unit:{WORK_UNIT_ID}"}]}),
            encoding="utf-8")
        result = self._post(request_payload())
        errors = list(RESULT_VALIDATOR.iter_errors(result))
        self.assertEqual(errors, [], json.dumps(errors, default=str)[:500])
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        self.assertEqual([row["task_id"] for row in self.plane.store.list_tasks()], [WORK_UNIT_ID])
        # the write method set did not widen for the sake of the new operation
        for method in ("PUT", "PATCH", "DELETE"):
            request = urllib.request.Request(self.base + "/api/control/operations", data=b"{}",
                                             method=method)
            try:
                with urllib.request.urlopen(request, timeout=5) as response:
                    self.fail(f"{method} was served with {response.status}")
            except urllib.error.HTTPError as error:  # noqa: F821 - raised by the 405, which is the point
                self.assertEqual(error.code, 405)

    def test_the_descriptor_publishes_the_authorization_record_state_instead_of_unknown(self) -> None:
        state = self._get("/api/control/descriptor")["authorization_record"]
        self.assertEqual(state["path"], control_service.TRUSTED_GRANTS_PATH)
        self.assertFalse(state["readable"], "a fresh runtime root has no signed record yet")
        self.assertEqual(state["grants"], 0)
        self.assertTrue(state["note"], "the shell must have a reason to show, not a blank")

        (self.runtime / control_service.TRUSTED_GRANTS_PATH).write_text(
            json.dumps({"schema_version": control_service.GRANT_RECORD_SCHEMA,
                        "grants": [{"grant_id": GRANT_ID, "scope": "*"}]}), encoding="utf-8")
        after = self._get("/api/control/descriptor")["authorization_record"]
        self.assertTrue(after["readable"])
        self.assertEqual(after["grants"], 1)

    def test_the_new_operation_is_declared_in_the_descriptor_and_in_the_closed_enum(self) -> None:
        listed = {entry["operation"]: entry
                  for entry in self._get("/api/control/descriptor")["operations"]}
        self.assertEqual(set(listed), set(control_service.OPERATIONS))
        self.assertEqual(listed["work-unit.materialize"]["support"], "IMPLEMENTED")
        self.assertTrue(listed["work-unit.materialize"]["reason"].strip())
        enum = json.loads((ROOT / "packages/contracts/schemas/workflow/"
                           "control-operation.schema.json").read_text(encoding="utf-8"))
        self.assertEqual(set(enum["properties"]["operation"]["enum"]), set(control_service.OPERATIONS),
                         "the closed enum and the operation table drifted apart")


if __name__ == "__main__":
    unittest.main(verbosity=2)
