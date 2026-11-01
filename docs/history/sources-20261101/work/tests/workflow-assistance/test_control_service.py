"""Gate: the Control Surface service is the only write boundary, and it answers honestly.

P1-06 / AG-15 / T04. What this pins, in the order the product can be lied about:

1. a request that does not fit the contract is REFUSED before anything runs;
2. an operation with no native capability answers NOT_IMPLEMENTED with its own reason and an EMPTY
   receipt — it cannot return a success shape, and evidence_level cannot be raised by the caller;
3. a real write goes through the existing permission gate, into the ONE canonical store the Observer
   also reads, and is then re-read: a handler return is not a verified write;
4. idempotent replay returns the same record instead of a second one, and a foreign idempotency key on
   an existing task_id is refused rather than overwriting someone else's work unit;
5. a boundary outside this repository — including E:/F: — is refused by name;
6. every result validates against ``control-operation-result.schema.json``, so the two languages cannot
   drift into two different stories;
7. the transport is loopback-only, and the write method set is exactly POST /api/control/operations.

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

import ast
import json
import re
import shutil
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
from project_temp import fixture_dir  # noqa: E402
from snapshot_api import project_task_record  # noqa: E402

RESULT_SCHEMA = json.loads((ROOT / "packages/contracts/schemas/workflow/"
                            "control-operation-result.schema.json").read_text(encoding="utf-8"))
RESULT_VALIDATOR = jsonschema.Draft202012Validator(RESULT_SCHEMA, format_checker=jsonschema.FormatChecker())


def request_payload(**over):
    payload = {
        "schema_version": "worklab/control-operation/v1",
        "operation": "work-unit.create",
        "project_id": "work-lab",
        "task_id": "WL-CONTROL-1",
        "revision": None,
        "attempt": None,
        "scope": {"boundaries": [str(ROOT)], "granted_by": "owner 2026-10-08 授权批次 C"},
        "expected_version": None,
        "idempotency_key": "idem-control-0001",
        "actor": "qoder-session",
        "requested_at": "2026-10-08T00:00:00Z",
        "payload": {"goal": "把 Control 首条写链接到 Observer 读回"},
    }
    payload.update(over)
    return payload


class ControlPlaneTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.runtime = fixture_dir(prefix="control-plane-")
        self.plane = control_service.build_plane(self.runtime, ROOT)

    def tearDown(self) -> None:
        self.plane.store.close()

    def assert_result_shape(self, result: dict) -> None:
        errors = list(RESULT_VALIDATOR.iter_errors(result))
        self.assertEqual(errors, [], json.dumps({"errors": [e.message for e in errors],
                                                 "result": result}, ensure_ascii=False)[:900])

    # -- 1 contract first ---------------------------------------------------
    def test_a_request_that_does_not_fit_the_contract_never_runs(self) -> None:
        missing_key = request_payload()
        del missing_key["idempotency_key"]
        result = self.plane.execute(missing_key)
        self.assert_result_shape(result)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "INVALID_REQUEST")
        self.assertIn("idempotency_key", result["reason"])
        self.assertEqual(self.plane.store.list_tasks(), [], "an unauthorised request produced a row")

    def test_an_unknown_verb_is_refused_not_invented(self) -> None:
        result = self.plane.execute(request_payload(operation="work-unit.teleport"))
        self.assert_result_shape(result)
        self.assertNotEqual(result["status"], "ACCEPTED")
        self.assertIn(result["status"], ("REFUSED", "NOT_IMPLEMENTED"))

    def test_extra_properties_are_not_silently_accepted(self) -> None:
        smuggled = request_payload()
        smuggled["as_root"] = True
        result = self.plane.execute(smuggled)
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "INVALID_REQUEST")

    # -- 2 NOT_IMPLEMENTED is a real answer ---------------------------------
    def test_operations_without_a_native_capability_refuse_success(self) -> None:
        for operation in ("work-unit.dispatch", "approval.decide", "execution.cancel",
                          "config.apply", "config.rollback", "work-unit.revise", "execution.resume",
                          "execution.retry", "config.readback", "config.discover"):
            with self.subTest(operation=operation):
                result = self.plane.execute(request_payload(operation=operation,
                                                            task_id="WL-CONTROL-1"))
                self.assert_result_shape(result)
                self.assertEqual(result["status"], "NOT_IMPLEMENTED")
                self.assertIsNone(result["receipt"], "an unimplemented operation returned a receipt")
                self.assertTrue(result["reason"].strip())
                self.assertTrue(result["next_action"])
        self.assertEqual(self.plane.store.list_tasks(), [], "a refused operation wrote state")

    # -- 3 the real write chain --------------------------------------------
    def test_create_writes_then_rereads_and_is_visible_to_the_observer_projection(self) -> None:
        result = self.plane.execute(request_payload())
        self.assert_result_shape(result)
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        self.assertEqual(result["evidence_level"], "SYNTHETIC",
                         "an in-repo fixture store may not claim more than SYNTHETIC")
        self.assertEqual(result["readback"]["status"], "QUEUED")
        self.assertEqual(len(result["receipt"]["digest"]), 64)

        rows = self.plane.store.list_tasks()
        self.assertEqual([row["task_id"] for row in rows], ["WL-CONTROL-1"])
        projected = project_task_record(rows[0])
        self.assertEqual(projected, {k: v for k, v in result["readback"].items() if k != "replayed"})

    def test_the_goal_text_stays_in_the_store_and_out_of_the_projection(self) -> None:
        goal = "读取我的私人会话并总结"
        result = self.plane.execute(request_payload(payload={"goal": goal}))
        self.assertEqual(result["status"], "ACCEPTED")
        serialised = json.dumps(result, ensure_ascii=False)
        self.assertNotIn(goal, serialised, "a control result leaked the goal into the read side")
        stored = self.plane.store.list_tasks()[0]
        self.assertEqual(stored["checkpoint"]["goal"], goal, "the store is the right place for the goal")

    def test_a_missing_goal_is_refused_instead_of_creating_an_empty_unit(self) -> None:
        result = self.plane.execute(request_payload(payload={"goal": "   "}))
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "GOAL_REQUIRED")

    def test_a_write_that_cannot_be_read_back_is_not_reported_as_success(self) -> None:
        """Fail-closed proof: if the readback disappears, the answer is READBACK_MISMATCH."""
        original = self.plane.store.list_tasks

        def lying_store(*args, **kwargs):
            rows = original(*args, **kwargs)
            return [] if rows else rows

        self.plane.store.list_tasks = lying_store
        try:
            result = self.plane.execute(request_payload())
        finally:
            self.plane.store.list_tasks = original
        self.assert_result_shape(result)
        self.assertEqual(result["status"], "READBACK_MISMATCH")

    # -- 4 idempotency ------------------------------------------------------
    def test_a_create_never_clobbers_a_live_lease(self) -> None:
        """A control-plane create carries no lease, so it must not write lease columns at all.

        The write used to be an upsert whose ON CONFLICT branch took lease_holder, lease_expires_at and
        fencing_token from the incoming record -- all absent for a create, i.e. NULL. A replay under a
        foreign identity therefore wiped whoever held the task and sent the fencing token backwards, the
        exact property the fence exists to hold, and the identity check itself ran outside any lock the
        sidecar shares.
        """
        first = self.plane.execute(request_payload(
            task_id="WL-LEASE-1", idempotency_key="idem-lease-1",
            payload={"goal": "keep my lease"},
        ))
        self.assertEqual(first["status"], "ACCEPTED", first["reason"])
        self.assertTrue(self.plane.store.acquire_lease("WL-LEASE-1", "executor-7", ttl_seconds=300))
        before = {r["task_id"]: r for r in self.plane.store.list_tasks()}["WL-LEASE-1"]
        self.assertEqual(before["lease_holder"], "executor-7")

        conflict = self.plane.execute(request_payload(
            task_id="WL-LEASE-1", idempotency_key="idem-lease-DIFFERENT",
            payload={"goal": "hijack"},
        ))
        self.assertEqual(conflict["status"], "REFUSED", conflict["reason"])
        self.assertEqual(conflict["reason_code"], "IDEMPOTENCY_CONFLICT")
        after = {r["task_id"]: r for r in self.plane.store.list_tasks()}["WL-LEASE-1"]
        self.assertEqual(after["lease_holder"], "executor-7", "a create overwrote a live holder")
        self.assertEqual(after["fencing_token"], before["fencing_token"], "the fencing token moved backwards")
        self.assertNotEqual(str((after.get("checkpoint") or {}).get("goal")), "hijack")

    def test_replay_of_the_same_identity_keeps_a_lease_it_did_not_claim(self) -> None:
        self.plane.execute(request_payload(task_id="WL-LEASE-2", idempotency_key="idem-lease-2",
                                           payload={"goal": "replay me"}))
        self.plane.store.acquire_lease("WL-LEASE-2", "executor-8", ttl_seconds=300)
        replay = self.plane.execute(request_payload(task_id="WL-LEASE-2", idempotency_key="idem-lease-2",
                                                    payload={"goal": "replay me"}))
        self.assertEqual(replay["status"], "ACCEPTED", replay["reason"])
        row = {r["task_id"]: r for r in self.plane.store.list_tasks()}["WL-LEASE-2"]
        self.assertEqual(row["lease_holder"], "executor-8")

    def test_containment_is_decoded_from_the_text_not_from_the_filesystem(self) -> None:
        """The verdict must not depend on which operating system asks.

        Same boundary string, same project root, two machines: this passed locally and flipped on the CI
        runner twice — first through `Path.resolve()`, then through `os.path.normcase/normpath`, because on
        the Linux job a Windows-style path has no drive and no leading slash and reads as RELATIVE, which
        anchored another project inside this one. The helper is pure string work now, and these rows are
        written so they mean the same thing on Windows, Linux and macOS.
        """
        inside = control_service._inside_project
        root = Path("D:/a/WORK-LAB/WORK-LAB")
        for candidate, expected in (
                (Path("D:/a/WORK-LAB/WORK-LAB/services/control"), True),
                (Path("D:/a/WORK-LAB/WORK-LAB"), True),
                (Path("D:/a/WORK-LAB/WORK-LAB/../OTHER"), False),
                (Path("D:/a/WORK-LAB"), False),
                (Path("D:/a/WORK-LAB/WORK-LABX"), False),
                (Path("D:/All projects/OTHER-PROJECT"), False),
                (Path("C:/Users/anyone/config.yaml"), False),
                (Path("d:/a/work-lab/work-lab/config"), True),
                ("D:\\a\\WORK-LAB\\WORK-LAB\\services", True),
                ("D:/a/WORK-LAB/WORK-LAB/./services/../services", True),
                ("/etc/passwd", False),
                ("services/control", False)):  # unanchored text is not yet a project path
            with self.subTest(candidate=str(candidate)):
                self.assertIs(inside(candidate, root)[0], expected)

    def test_the_authorisation_check_never_asks_the_host_about_paths(self) -> None:
        """No `os.path` call may decide authority: an AST check, because the last two fixes went stale quietly.

        The first guard asserted behaviour I had just changed with os.path, which was host-specific and kept
        failing on the runner. Enumerating the syntax that reaches the host is the only assertion that cannot
        rot into a lie the next time someone adds a convenient `os.path.join`.
        """
        tree = ast.parse(Path(control_service.__file__).read_text(encoding="utf-8"))
        offenders = []
        for node in ast.walk(tree):
            if (isinstance(node, ast.Attribute) and isinstance(node.value, ast.Attribute)
                    and isinstance(node.value.value, ast.Name)
                    and node.value.value.id == "os" and node.value.attr == "path"):
                offenders.append((node.lineno, node.attr))
        self.assertEqual(offenders, [], "host-dependent path calls in the control service: %s" % offenders)
        # `relative_to` is the same class of fault one level up: it compares with the host's case rules, so a
        # case-folded lexical path fails against an original-case root on Linux and succeeds on Windows. It
        # raised ValueError in `_is_non_diffable_target`, which the diff read as "not ours to read" and turned
        # into three refused config targets on the runner while the same tests passed locally.
        relative_to_calls = [node.lineno for node in ast.walk(tree)
                             if isinstance(node, ast.Attribute) and node.attr == "relative_to"
                             and not (isinstance(node.value, ast.Constant))]
        self.assertEqual(relative_to_calls, [],
                         "Path.relative_to in the control service decides with the filesystem's case rules: "
                         f"lines {relative_to_calls}")
        # the third host query of this series: `Path.resolve()` inside the authorising class. It turned
        # `/home/runner/...` into `D:/home/runner/...` on Windows, so a POSIX-shaped root and its own boundary
        # stopped matching and every operation refused -- found by running the same decision against four root
        # shapes on one machine, which is the only way a Windows-only check can ever see it.
        planes = [node for node in ast.walk(tree)
                  if isinstance(node, ast.ClassDef) and node.name == "ControlPlane"]
        self.assertEqual(1, len(planes), "expected exactly one ControlPlane class to guard")
        host_queries = [(node.lineno, node.func.attr) for node in ast.walk(planes[0])
                        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                        and node.func.attr in {"resolve", "absolute", "cwd", "expanduser", "home"}]
        self.assertEqual([], host_queries,
                         f"the authorising class asks the host where it is: {host_queries}")
        self.assertEqual(control_service.normalise_path("D:\\A\\x\\..\\y"), "d:/a/y")
        self.assertEqual(control_service.normalise_path("/etc/../etc"), "/etc")
        self.assertEqual(control_service.normalise_path("D:/a/b/../.."), "d:/")
        self.assertEqual(control_service.normalise_path("D:/a/b/.."), "d:/a")
        self.assertTrue(control_service.path_is_drive_relative("E:secrets"))
        self.assertFalse(control_service.path_is_drive_relative("E:/secrets"))
        self.assertTrue(control_service.path_is_anchored("D:/x"))
        self.assertTrue(control_service.path_is_anchored("/x"))
        self.assertFalse(control_service.path_is_anchored("x/y"))

    def test_a_refusal_names_the_two_normalised_paths_it_compared(self) -> None:
        """A red on another machine has to explain itself, not be re-derived by whoever comes next."""
        result = self.plane.execute(request_payload(
            scope={"boundaries": ["D:/Clearly-Outside-This-Project"], "granted_by": "owner"},
            idempotency_key="idem-lexicon-1"))
        self.assertEqual(result["status"], "REFUSED", result["reason"])
        self.assertEqual(result["reason_code"], "OUT_OF_PROJECT_SCOPE")
        self.assertIn("规范化后", result["reason"])
        self.assertEqual(self.plane.store.list_tasks(), [])

    def test_replaying_the_same_key_returns_the_same_record(self) -> None:
        first = self.plane.execute(request_payload())
        again = self.plane.execute(request_payload())
        self.assertEqual(first["status"], "ACCEPTED")
        self.assertEqual(again["readback"]["replayed"], True)
        self.assertEqual(again["receipt"]["kind"], "REPLAY")
        self.assertEqual(len(self.plane.store.list_tasks()), 1)

    def test_a_foreign_idempotency_key_on_an_existing_task_is_refused(self) -> None:
        self.plane.execute(request_payload())
        hijack = self.plane.execute(request_payload(idempotency_key="idem-other-owner-2",
                                                   payload={"goal": "改掉别人的工作单元"}))
        self.assertEqual(hijack["status"], "REFUSED")
        self.assertEqual(hijack["reason_code"], "IDEMPOTENCY_CONFLICT")
        stored = self.plane.store.list_tasks()[0]
        self.assertEqual(stored["checkpoint"]["idempotency_key"], "idem-control-0001",
                         "a refused replay overwrote the original identity")

    # -- 5 boundaries -------------------------------------------------------
    def test_protected_and_outside_boundaries_are_refused_by_name(self) -> None:
        for boundary, code in (("E:/somewhere", "FORBIDDEN_ROOT"),
                              ("F:/somewhere", "FORBIDDEN_ROOT"),
                              ("D:/All projects/OTHER-PROJECT", "OUT_OF_PROJECT_SCOPE"),
                              (" ", "EMPTY_BOUNDARY")):
            with self.subTest(boundary=boundary):
                result = self.plane.execute(request_payload(scope={"boundaries": [boundary],
                                                                  "granted_by": "owner"}))
                self.assertEqual(result["status"], "REFUSED")
                self.assertEqual(result["reason_code"], code)
        self.assertEqual(self.plane.store.list_tasks(), [])

    def test_a_relative_boundary_stays_allowed_and_is_recorded(self) -> None:
        result = self.plane.execute(request_payload(scope={"boundaries": ["services/control"],
                                                          "granted_by": "owner"}))
        self.assertEqual(result["status"], "ACCEPTED")
        self.assertEqual(self.plane.store.list_tasks()[0]["checkpoint"]["boundaries"], ["services/control"])

    # -- 6 the plan-only config path ---------------------------------------
    def test_config_diff_decides_the_same_under_every_root_shape(self) -> None:
        """The exact CI refusal, reproduced on one machine: a case-folded target vs an original-case root.

        The runner reported `TARGET_SENSITIVE` for `.project/governance/work-lab.project-profile.yaml`,
        which is not a credential name at all: `_is_non_diffable_target` called `Path.relative_to` with the
        lower-cased lexical path against `/home/runner/work/WORK-LAB/WORK-LAB`, that raised ValueError on a
        case-sensitive filesystem, and the except branch means "refuse". Windows case-insensitivity hid it.
        Roots here are strings, no filesystem is consulted for the decision, so all three must agree.
        """
        for root_text in ("D:/All projects/WORK-LAB", "/home/runner/work/WORK-LAB/WORK-LAB",
                          "/github/workspace", str(ROOT)):
            plane = control_service.build_plane(fixture_dir(prefix="cfg-diff-root-"), Path(root_text))
            try:
                result = plane.execute(request_payload(
                    scope={"boundaries": [root_text], "granted_by": "owner 2026-10-08"},
                    operation="config.diff",
                    payload={"target_file": ".project/governance/work-lab.project-profile.yaml",
                             "field": "schema_version", "value": "work-lab-project-profile/v2"}))
                self.assertEqual("PLANNED", result["status"],
                                 f"root {root_text}: {result['reason_code']} {result['reason']}")
                self.assertEqual(".project/governance/work-lab.project-profile.yaml",
                                 result["readback"]["target"], f"root {root_text}")
                refused = plane.execute(request_payload(
                    scope={"boundaries": [root_text], "granted_by": "owner 2026-10-08"},
                    operation="config.diff",
                    payload={"target_file": "docs/audits/TOOL_INVENTORY_2026-10-07.json",
                             "field": "trackedTools", "value": 1}))
                self.assertEqual("REFUSED", refused["status"], f"root {root_text}")
                self.assertEqual("TARGET_SENSITIVE", refused["reason_code"], f"root {root_text}")
                outside = plane.execute(request_payload(
                    scope={"boundaries": [root_text], "granted_by": "owner 2026-10-08"},
                    operation="config.diff",
                    payload={"target_file": "D:/Other Vendor App/config.yaml",
                             "field": "model", "value": "x"}))
                self.assertEqual("REFUSED", outside["status"], f"root {root_text}")
                self.assertEqual("TARGET_OUT_OF_PROJECT", outside["reason_code"], f"root {root_text}")
            finally:
                plane.store.close()

    def test_config_diff_returns_a_plan_and_says_it_did_not_write(self) -> None:
        result = self.plane.execute(request_payload(
            operation="config.diff",
            payload={"target_file": ".project/governance/work-lab.project-profile.yaml",
                     "field": "schema_version", "value": "work-lab-project-profile/v2"},
        ))
        self.assert_result_shape(result)
        self.assertEqual(result["status"], "PLANNED", result["reason"])
        self.assertIsNone(result["receipt"], "a plan is not a receipt")
        self.assertTrue(result["readback"]["plan_only"])
        self.assertIs(result["readback"]["written"], False)
        # the key exists in that document, so the plan must say present_before -- proof it read the real
        # target. It is a KEY question: the same operation used to answer "is this substring anywhere in
        # the file", which turns any in-repo file into a content oracle one yes/no at a time.
        change = result["readback"]["changes"][0]
        self.assertTrue(change["present_before"], result["readback"]["target"])
        self.assertEqual(result["readback"]["target"], ".project/governance/work-lab.project-profile.yaml")

    def test_the_diff_reads_the_declared_case_not_the_folded_path(self) -> None:
        """The CI failure at 7ca2fd45: containment folds case, I/O must not.

        `NOTICE.md` is a tracked file whose NAME is uppercase, so the folded path
        `notice.md` does not exist on a case-sensitive filesystem while opening it
        succeeds on Windows. (The earlier fixture was `UI_IMPLEMENTATION_REPORT.md`, which moved to
        `docs/history/archive/root-ui-records-20261019/` on 2026-10-19; `docs/` is a non-diffable root,
        so a root-level uppercase file is required.) Asserting the echoed target keeps the declared
        case is what makes this falsifiable on one machine: before the fix the readback reported the
        folded name on every host.
        """
        result = self.plane.execute(request_payload(
            operation="config.diff",
            payload={"target_file": "NOTICE.md",
                     "field": "schema_version", "value": "whatever"}))
        self.assertEqual("PLANNED", result["status"], result["reason"])
        self.assertEqual("NOTICE.md", result["readback"]["target"],
                         "the readback echoed a case-folded path, which no case-sensitive host has")
        # a key that is genuinely present must read as present; FILE_ABSENT here is the folded-path bug
        present = self.plane.execute(request_payload(
            operation="config.diff",
            payload={"target_file": "NOTICE.md",
                     "field": "Control", "value": "x"}))
        self.assertNotEqual("FILE_ABSENT", present["readback"]["changes"][0]["presenceBasis"],
                            "the document was read as absent: the folded path does not exist on Linux")

    def test_relative_inside_keeps_case_and_refuses_a_guessed_remainder(self) -> None:
        cases = [
            ("D:/All projects/WORK-LAB", "D:/All projects/WORK-LAB/UI_REPORT.md", "UI_REPORT.md"),
            ("/home/Runner/work/WORK-LAB", "/home/Runner/work/WORK-LAB/Config.YAML", "Config.YAML"),
            ("/home/runner/work/WORK-LAB", "/home/runner/WORK-LAB/other/x", None),
            # a dot-segment is collapsed for the containment decision and preserved for the read,
            # because Path("/srv/app/./x") is the same file the caller named
            ("/srv/app", "/srv/app/./x", "./x"),
        ]
        for root, candidate, expected in cases:
            with self.subTest(root=root, candidate=candidate):
                self.assertEqual(expected, control_service.relative_inside(candidate, root))

    def test_config_diff_answers_key_questions_not_substring_questions(self) -> None:
        """A string that is present in the file but is not a declared key must read as absent."""
        result = self.plane.execute(request_payload(
            operation="config.diff",
            payload={"target_file": ".project/governance/work-lab.project-profile.yaml",
                     "field": "gates", "value": "workflow"},
        ))
        self.assertEqual(result["status"], "PLANNED", result["reason"])
        change = result["readback"]["changes"][0]
        self.assertTrue(change["present_before"])
        probe = self.plane.execute(request_payload(
            operation="config.diff",
            payload={"target_file": ".project/governance/work-lab.project-profile.yaml",
                     "field": "workflow", "value": "anything"},
        ))
        self.assertIs(probe["readback"]["changes"][0]["present_before"], False,
                      "'workflow' occurs in that document as a value, but it is not a declared key")
        self.assertEqual(probe["readback"]["changes"][0]["presenceBasis"], "KEY_PATH_RESOLVES")

    def test_config_diff_refuses_a_credential_shaped_target(self) -> None:
        """Refusing by name, before reading: the boundary is not the only thing that decides.

        Two layers can answer first -- the policy's prefix denials and the operation's own name test -- so
        the assertion is on the outcome that matters: REFUSED, with a reason that names why. An allowed
        reason list is not a weakened test; it is the honest shape of a defence with two independent
        layers, and any third path that answers PLANNED fails here.
        """
        for target in (".hermes/task-runtime/x/canonical.sqlite", "config/.env",
                       ".project-local/artifacts/backup/hermes/config.yaml",
                       ".project-local/runs/tmp/cookies.sqlite"):
            with self.subTest(target=target):
                result = self.plane.execute(request_payload(
                    operation="config.diff", payload={"target_file": target, "field": "a"},
                ))
                self.assertEqual(result["status"], "REFUSED", result["reason"])
                self.assertIn(result["reason_code"],
                              {"TARGET_SENSITIVE", "GATE_DENIED", "GATE_NEEDS_HUMAN"})

    def test_config_diff_reports_an_unparseable_document_as_unknown(self) -> None:
        """A file that is not a mapping gets no boolean: 'cannot tell' is not 'not declared'."""
        result = self.plane.execute(request_payload(
            operation="config.diff",
            payload={"target_file": "services/control/control_service.py", "field": "SCHEMA_VERSION"},
        ))
        self.assertEqual(result["status"], "PLANNED", result["reason"])
        change = result["readback"]["changes"][0]
        self.assertIsNone(change["present_before"])
        # Which of the two unknown states it lands in is the parser's business (.py is either a scalar or
        # invalid YAML); that it is unknown and named is the property this operation must never lose.
        self.assertTrue(str(change["presenceBasis"]).startswith("DOCUMENT"), change["presenceBasis"])

    def test_a_credential_target_is_denied_before_the_operation_is_reached(self) -> None:
        """The gate sees the subject, not the operation name -- so CRITICAL escalation is reachable.

        This is the regression ERR-166-style review found: `target=request["operation"]` meant the
        permission gate's own '.env / credential / secret / auth' rule could never match anything, because
        an operation id contains none of those words even when the payload names a keystore.
        """
        for field in ("path", "target_file", "file", "target"):
            with self.subTest(field=field):
                payload = {field: ".hermes/task-runtime/x/canonical.sqlite", "field": "a"}
                result = self.plane.execute(request_payload(operation="config.diff", payload=payload))
                self.assertEqual(result["status"], "REFUSED", result["reason"])
                decision = self.plane.gate.evaluate(
                    "filesystem", target=self.plane._subject({"operation": "config.diff", "payload": payload}))
                self.assertNotEqual(decision.status.value, "allowed", decision.reason)

    def test_config_diff_refuses_a_target_outside_the_repository(self) -> None:
        result = self.plane.execute(request_payload(
            operation="config.diff", payload={"target_file": "C:/Users/anyone/config.yaml", "field": "a"},
        ))
        self.assertEqual(result["status"], "REFUSED")
        self.assertEqual(result["reason_code"], "TARGET_OUT_OF_PROJECT")

    def test_receipts_are_tracked_in_the_runtime_root(self) -> None:
        goal = "把回执写进运行根"
        self.plane.execute(request_payload(payload={"goal": goal}))
        receipts = (self.runtime / control_service.RECEIPTS_PATH)
        self.assertTrue(receipts.is_file())
        line = json.loads(receipts.read_text(encoding="utf-8").splitlines()[0])
        self.assertEqual(line["receipt"]["kind"], "WORK_UNIT_QUEUED")
        serialised = json.dumps(line["record"], ensure_ascii=False)
        # the design: key NAMES and a digest travel to the read side, the VALUES never do
        self.assertNotIn(goal, serialised)
        self.assertIn("goal", line["record"]["checkpointKeys"])
        self.assertEqual(len(line["record"]["checkpointDigest"]), 64)


class TestFixturesDoNotAssumeTheAuthorMachine(unittest.TestCase):
    """The literal that made CI red: 18 refusals while every local run was green.

    The default request fixture named *this developer's* checkout as the authorised scope
    boundary. The containment rule (`f9f38d6`) is what made that literal observable, and it
    refused correctly -- so the defect was the fixture, not the rule. A fixture that is only true
    on one machine tests nothing on another, and the failure lands on the machine that cannot
    edit it.
    """

    def test_default_boundary_is_the_checkout_under_test(self) -> None:
        boundaries = request_payload()["scope"]["boundaries"]
        self.assertEqual([str(ROOT)], boundaries,
                         "fixture boundary must be derived from this file's own root, never a "
                         "hard-coded machine path")

    def test_every_default_boundary_is_inside_the_planes_project_root(self) -> None:
        inside = control_service._inside_project
        plane_root = ROOT
        for boundary in request_payload()["scope"]["boundaries"]:
            ok, root_text, lexical = inside(boundary, plane_root)
            self.assertTrue(ok, f"{boundary} resolves outside {root_text} (lexical {lexical}); "
                                f"the plane would refuse every write in this suite")

    def test_the_fixture_proves_the_refusal_still_works_for_a_foreign_root(self) -> None:
        """Fixing the fixture must not quietly delete the guard it was caught by."""
        plane = control_service.build_plane(fixture_dir(prefix="control-machine-"), ROOT)
        try:
            result = plane.execute(request_payload(
                scope={"boundaries": ["D:/All projects/OTHER-PROJECT"], "granted_by": "x"}))
            self.assertNotEqual("ACCEPTED", result["status"], result)
        finally:
            plane.store.close()


    def test_a_relative_project_root_is_refused_at_construction(self) -> None:
        """Without `resolve()` a relative root would mean "whatever the cwd is" -- so refuse it outright.

        The refusal must happen before any sqlite handle exists: an earlier version opened the store and
        then raised, and on Windows the open handle made the fixture directory undeletable
        (`WinError 32`), which is the residue that poisoned the next test in the batch.
        """
        runtime = fixture_dir(prefix="relative-root-")
        with self.assertRaises(ValueError) as caught:
            control_service.build_plane(runtime, Path("some/relative/root"))
        self.assertIn("not anchored", str(caught.exception))
        shutil.rmtree(runtime, ignore_errors=False)
        self.assertFalse(runtime.exists(),
                         "a refused root left residue behind, which means a handle was opened first")
        for anchored in ("/srv/work-lab", "D:/All projects/WORK-LAB", str(ROOT)):
            plane = control_service.build_plane(fixture_dir(prefix="anchored-root-"), Path(anchored))
            plane.store.close()


class ControlTransportTests(unittest.TestCase):
    """The loopback boundary is behaviour, not a comment."""

    def setUp(self) -> None:
        self.runtime = fixture_dir(prefix="control-http-")
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

    def _get(self, path: str, headers: dict | None = None):
        req = urllib.request.Request(self.base + path, headers=headers or {})
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def _post(self, path: str, body: dict, headers: dict | None = None):
        req = urllib.request.Request(self.base + path, data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json", **(headers or {})},
                                     method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def _status_of_rejected_method(self, method: str) -> int:
        req = urllib.request.Request(self.base + "/api/control/operations", data=b"{}", method=method)
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def test_a_refusal_arrives_whole_even_when_the_caller_sent_a_body(self) -> None:
        """The 405 is a promise, so it must be the whole response -- not the caller's JSON in front of it.

        A PUT that carried a body used to be refused with the body still sitting in the socket buffer. On a
        keep-alive connection the next read then starts with those bytes instead of a status line, which is
        how a transport test saw a broken status where it expected 405. This test speaks raw so it can see
        the byte order, not just the parsed status.
        """
        import socket
        from urllib.parse import urlparse

        parsed = urlparse(self.base)
        with socket.create_connection((parsed.hostname, parsed.port), timeout=5) as sock:
            sock.sendall(b"PUT /api/control/operations HTTP/1.1\r\nHost: 127.0.0.1\r\n"
                         b"Content-Length: 11\r\nConnection: close\r\n\r\n{\"leftover\":")
            received = b""
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                received += chunk
        head, _, tail = received.partition(b"\r\n\r\n")
        status_line = head.split(b"\r\n", 1)[0].decode("latin-1")
        self.assertTrue(status_line.startswith("HTTP/1."),
                        f"the response did not begin with a status line: {status_line!r}")
        self.assertIn(" 405 ", status_line, status_line)
        self.assertNotIn(b"leftover", head, "the request body was reflected ahead of the refusal")
        self.assertIn(b"405", head)
        self.assertTrue(tail, "the refusal carried no body")
        self.assertNotIn(b"leftover", tail[:30], "unconsumed request bytes preceded the refusal body")

    def test_binds_loopback_and_publishes_a_dynamic_endpoint_descriptor(self) -> None:
        self.assertEqual(self.server.host, "127.0.0.1")
        self.assertGreater(self.server.bound_port, 0)
        descriptor_path = self.runtime / control_service.DESCRIPTOR_PATH
        descriptor = self.server.write_descriptor(descriptor_path)
        self.assertEqual(json.loads(descriptor_path.read_text(encoding="utf-8")), descriptor)
        self.assertEqual(descriptor["port"], self.server.bound_port)
        self.assertEqual(descriptor["transport"], "loopback-only")
        self.assertIn("evidence_ceiling", descriptor)

    def test_a_non_loopback_host_header_is_refused(self) -> None:
        code = self._status_of_request_with_host("example.com")
        self.assertEqual(code, 403)

    def _status_of_request_with_host(self, host: str) -> int:
        req = urllib.request.Request(self.base + "/api/control/descriptor", headers={"Host": host})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status
        except urllib.error.HTTPError as error:
            return error.code

    def test_a_foreign_origin_is_refused(self) -> None:
        try:
            self._get("/api/control/descriptor", headers={"Origin": "https://evil.example"})
            self.fail("a non-loopback origin was served")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 403)

    def test_write_methods_other_than_the_single_post_are_405(self) -> None:
        for method in ("PUT", "PATCH", "DELETE"):
            with self.subTest(method=method):
                self.assertEqual(self._status_of_rejected_method(method), 405)

    def test_descriptor_lists_every_operation_with_its_own_support_level(self) -> None:
        status, descriptor = self._get("/api/control/descriptor")
        self.assertEqual(status, 200)
        self.assertEqual(descriptor["schema_version"], control_service.SCHEMA_VERSION)
        listed = {entry["operation"]: entry for entry in descriptor["operations"]}
        self.assertEqual(set(listed), set(control_service.OPERATIONS))
        self.assertEqual(listed["work-unit.create"]["support"], "IMPLEMENTED")
        self.assertEqual(listed["approval.decide"]["support"], "NOT_IMPLEMENTED")
        self.assertTrue(listed["approval.decide"]["reason_code"])

    def _raw_get(self, path: str):
        req = urllib.request.Request(self.base + path)
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, dict(response.headers), response.read().decode("utf-8")

    def test_the_shell_is_served_by_the_write_origin_and_offers_no_auth_surface(self) -> None:
        """The boundary the owner set: local use, no login / token / key / account field, ever."""
        status, headers, html = self._raw_get("/")
        self.assertEqual(status, 200)
        self.assertIn("text/html", headers.get("Content-Type", ""))
        self.assertIn("default-src 'none'", headers.get("Content-Security-Policy", ""))
        lowered = html.lower()
        # prose may mention these words (the page states the boundary); a CONTROL may not be one of them
        controls = re.findall(r"<input\b[^>]*>", lowered)
        self.assertTrue(controls, "the create form should have inputs")
        for forbidden in ("password", "api key", "api_key", "token", "oauth", "jwt", "vault", "credential",
                          "login", "锁屏"):
            for control in controls:
                self.assertNotIn(forbidden, control, f"the shell grew an auth control: {control}")
        self.assertIn('src="/control-shell.js"', html, "no inline script may satisfy a 'script-src self' CSP")
        script_status, _, script = self._raw_get("/control-shell.js")
        self.assertEqual(script_status, 200)
        self.assertNotIn("http://", script, "the shell must not reach outside its own origin")
        self.assertNotIn("https://", script)

    def test_an_unknown_read_path_is_404_not_a_open_proxy(self) -> None:
        try:
            self._raw_get("/proxy?target=https://example.com")
            self.fail("an unknown read path was served")
        except urllib.error.HTTPError as error:
            self.assertEqual(error.code, 404)

    def test_a_write_through_http_lands_in_the_store_the_observer_reads(self) -> None:
        status, result = self._post("/api/control/operations", request_payload())
        self.assertEqual(status, 200)
        errors = list(RESULT_VALIDATOR.iter_errors(result))
        self.assertEqual(errors, [])
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        rows = self.plane.store.list_tasks()
        self.assertEqual([row["task_id"] for row in rows], ["WL-CONTROL-1"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
