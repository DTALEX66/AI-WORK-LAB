"""WUI-10: the managed command boundary can be RE-QUERIED by the identity it already used.

The taskpack acceptance for this slice is one authorized transaction proven four ways — positive success,
conflict, refusal, recovery — plus the rule that the server checks actor / scope / prior state / version /
idempotency. The inbound owner material (WL-REC-0103 §6, judged in
`docs/history/archive/ui-priority-20261009/UI-V2-INTAKE-20261010.md`) adds three constraints, and the second one is
what this module buys:

  后台刷新丢失时保留操作身份并查询同一操作，禁止以新幂等键自动重复写入。

Measured before this module: the control service served exactly two read endpoints (`descriptor`, `health`)
and the shell minted a fresh idempotency key in `main()` on EVERY page load. So a reload after a submit
left the operator with no answer to "did that write happen?" and a page that would send a NEW identity on
the next click. The write side already refused a foreign key on an existing task_id, which stops a silent
duplicate — it does not tell the operator anything, and "the record is there, and here is what it says"
was simply not obtainable.

`GET /api/control/operations/<task_id>` is that answer, and the tests below pin the four things that make
it honest rather than a convenience:

1. it reads the ONE canonical store and the append-only receipts — no second ledger, no in-memory table;
2. its three outcomes are separate (`写入唯一账本` / `原生加载读回` / `目标行为确认`), and a landed write
   CONFIRMS only the first; the other two report the live support level of the operations that would have
   to produce them, so this answer cannot rot into a claim that outlives the gap;
3. replaying the identity it returned adds no second row, and a NEW key on the same task_id is refused
   while the row count stays at one;
4. it exposes nothing the read-only projection did not already expose: no checkpoint VALUES (the goal text
   stays in the store), and it is loopback-gated exactly like the write path.

The answer shape is inline, the same disposition `worklab/control-error/v1` already has — it is not
registered in `.project/governance/contracts/contract-catalog.json`, and that is recorded as a deviation
rather than smuggled in as "46 contracts".

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import hashlib
import json
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

import control_service  # noqa: E402
from project_temp import fixture_dir  # noqa: E402
from snapshot_api import project_task_record  # noqa: E402

GOAL_TEXT = "把这条规则落到受管客户端，并让 Observer 只读地看见它"


def request_payload(**over):
    payload = {
        "schema_version": "worklab/control-operation/v1",
        "operation": "work-unit.create",
        "project_id": "work-lab",
        "task_id": "WL-IDENTITY-1",
        "revision": None,
        "attempt": None,
        "scope": {"boundaries": [str(ROOT)], "granted_by": "owner 2026-10-11 WUI-10 事务演练"},
        "expected_version": None,
        "idempotency_key": "idem-identity-first",
        "actor": "control-shell",
        "requested_at": "2026-10-11T00:00:00Z",
        "payload": {"goal": GOAL_TEXT},
    }
    payload.update(over)
    return payload


class ControlIdentityReadTests(unittest.TestCase):
    """One real plane, one real loopback HTTP server, one canonical store per test."""

    def setUp(self) -> None:
        self.runtime = fixture_dir(prefix="control-identity-")
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

    def _status_with_host(self, path: str, host: str) -> tuple[int, dict]:
        req = urllib.request.Request(self.base + path, headers={"Host": host})
        try:
            with urllib.request.urlopen(req, timeout=5) as response:
                return response.status, json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            return error.code, json.loads(error.read().decode("utf-8"))

    def _post(self, body: dict):
        req = urllib.request.Request(self.base + "/api/control/operations",
                                     data=json.dumps(body).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=5) as response:
            return response.status, json.loads(response.read().decode("utf-8"))

    def rows_for(self, task_id: str) -> list[dict]:
        return [row for row in self.plane.store.list_tasks() if row["task_id"] == task_id]

    # -- the positive transaction, then the same identity read back ------------------------------------
    def test_a_landed_write_can_be_read_back_by_the_identity_it_used(self) -> None:
        status, result = self._post(request_payload())
        self.assertEqual(status, 200)
        self.assertEqual(result["status"], "ACCEPTED", result["reason"])
        code, answer = self._get("/api/control/operations/WL-IDENTITY-1")
        self.assertEqual(code, 200)
        self.assertEqual(answer["schema_version"], control_service.IDENTITY_SCHEMA)
        self.assertTrue(answer["found"], json.dumps(answer, ensure_ascii=False)[:400])
        self.assertEqual(answer["status"], "QUEUED")
        self.assertEqual(answer["project_id"], "work-lab")
        self.assertEqual(answer["idempotency_key"], "idem-identity-first")
        self.assertEqual(answer["record_digest"], hashlib.sha256(json.dumps(
            project_task_record(self.rows_for("WL-IDENTITY-1")[0]),
            ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")).hexdigest())
        kinds = [receipt["kind"] for receipt in answer["receipts"]]
        self.assertIn("WORK_UNIT_QUEUED", kinds, kinds)
        write = [item for item in answer["outcomes"] if item["id"] == "write"][0]
        self.assertEqual(write["state"], "CONFIRMED", write)

    def test_the_three_outcomes_stay_three_and_only_the_write_is_confirmed(self) -> None:
        self._post(request_payload())
        _code, answer = self._get("/api/control/operations/WL-IDENTITY-1")
        self.assertEqual([item["id"] for item in answer["outcomes"]],
                         ["write", "nativeLoad", "targetBehaviour"],
                         "the acceptance names three outcomes; folding or renaming one is how a write "
                         "starts talking about a native load")
        states = {item["id"]: item["state"] for item in answer["outcomes"]}
        self.assertEqual(states["write"], "CONFIRMED")
        for step in ("nativeLoad", "targetBehaviour"):
            self.assertEqual(states[step], "NOT_PROJECTED",
                             f"{step} was allowed to read as settled from a store write alone")
        for item in answer["outcomes"][1:]:
            self.assertTrue(item.get("owner"), f"{item['id']} names no producer that owes the field")
            self.assertRegex(item["detail"], r"NOT_IMPLEMENTED|没有|未实现|需要",
                             f"{item['id']} did not say which way it is missing")
        text = json.dumps(answer, ensure_ascii=False)
        self.assertNotIn("REAL", text, "a local control write must never claim native evidence level")

    def test_the_identity_answer_carries_no_checkpoint_values(self) -> None:
        """The public-exposure half of the acceptance: this route may not become a body reader."""
        self._post(request_payload())
        _code, answer = self._get("/api/control/operations/WL-IDENTITY-1")
        text = json.dumps(answer, ensure_ascii=False)
        self.assertNotIn(GOAL_TEXT, text,
                         "the goal text stays in the store; the Observer projection publishes key NAMES "
                         "and a digest, and a wider read here would be the smuggle the module docstring "
                         "of control_service.py names")
        self.assertIn("checkpoint_fields", answer)
        self.assertIn("goal", answer["checkpoint_fields"],
                       "the field must be LISTED by name, or the claim that values are withheld is empty")
        self.assertNotIn("granted_by", answer, "the authorization line is not this answer's to publish")

    # -- the lost refresh, and what must NOT happen next ------------------------------------------------
    def test_a_lost_refresh_replays_the_identity_it_read_back_instead_of_writing_twice(self) -> None:
        self._post(request_payload())
        _code, answer = self._get("/api/control/operations/WL-IDENTITY-1")
        recovered_key = answer["idempotency_key"]
        self.assertTrue(recovered_key)
        status, replay = self._post(request_payload(idempotency_key=recovered_key))
        self.assertEqual(status, 200)
        self.assertEqual(replay["status"], "ACCEPTED", replay["reason"])
        self.assertTrue(replay["readback"]["replayed"], replay["readback"])
        self.assertEqual(replay["receipt"]["kind"], "REPLAY")
        self.assertEqual(len(self.rows_for("WL-IDENTITY-1")), 1,
                         "a re-submitted identity must not grow the ledger")

    def test_a_fresh_key_on_an_existing_identity_is_refused_and_adds_no_row(self) -> None:
        """The exact shape of "以新幂等键自动重复写入": the ledger says no, and says it without writing."""
        self._post(request_payload())
        _code, answer = self._get("/api/control/operations/WL-IDENTITY-1")
        status, conflict = self._post(request_payload(idempotency_key="idem-identity-second"))
        self.assertEqual(status, 200, "a refusal rides 200 with its own reason code, per control-error shape")
        self.assertEqual(conflict["status"], "REFUSED", conflict)
        self.assertEqual(conflict["reason_code"], "IDEMPOTENCY_CONFLICT")
        self.assertEqual(len(self.rows_for("WL-IDENTITY-1")), 1)
        self.assertEqual(answer["idempotency_key"], "idem-identity-first",
                         "the stored identity is what a reader must get back, not the attempt that failed")

    # -- refusals on the read side ----------------------------------------------------------------------
    def test_an_unknown_identity_is_no_record_not_an_empty_success(self) -> None:
        code, answer = self._get("/api/control/operations/WL-NEVER-SENT")
        self.assertEqual(code, 200)
        self.assertFalse(answer["found"])
        self.assertEqual(answer["reason_code"], "OPERATION_NOT_FOUND")
        self.assertEqual(answer["receipts"], [])
        self.assertEqual({item["state"] for item in answer["outcomes"]}, {"NO_RECORD"},
                         "nothing known must read as nothing known, not as three refusals")
        self.assertNotIn("goal", answer, "an absent record must not be projected as a shape with values")

    def test_the_route_reads_one_identity_and_refuses_to_enumerate_or_walk(self) -> None:
        self._post(request_payload())
        for path in ("/api/control/operations",
                     "/api/control/operations/../..",
                     "/api/control/operations/a%2Fb",
                     "/api/control/operations/%5C..%5Chealth",
                     "/api/control/operations/" + "T" * 90,
                     "/api/control/operations/"):
            try:
                status, body = self._get(path)
                self.fail(f"an over-broad identity read was served: {path} -> {status} {body}")
            except urllib.error.HTTPError as error:
                self.assertEqual(error.code, 404, path)
                refused = json.loads(error.read().decode("utf-8"))
                self.assertEqual(refused["schema_version"], "worklab/control-error/v1", refused)
                self.assertEqual(refused["reason_code"], "UNKNOWN_READ", refused)
        # and the honest one still works after those refusals
        _code, answer = self._get("/api/control/operations/WL-IDENTITY-1")
        self.assertTrue(answer["found"])

    def test_the_identity_read_is_loopback_gated_exactly_like_the_write(self) -> None:
        self._post(request_payload())
        code, refused = self._status_with_host("/api/control/operations/WL-IDENTITY-1", "example.com")
        self.assertEqual(code, 403, refused)
        self.assertEqual(refused["reason_code"], "NOT_LOOPBACK")
        code, _ = self._status_with_host("/api/control/operations/WL-IDENTITY-1", "127.0.0.1")
        self.assertEqual(code, 200)

    def test_the_shell_carries_the_identity_across_a_reload_and_mints_no_key_for_it(self) -> None:
        """The page side, asserted as behaviour-by-construction on the shipped script.

        No browser is driven here: this pins that the reload path exists in the file the service actually
        serves (the CSP forbids inline script, so `control-shell.js` IS the page logic), that it reads the
        identity from the URL BEFORE minting, and that the minted-key branch is the else-branch. The real
        click-through is proven by `.project-local/runs/wui-20261011/shell-identity-evidence.json`, which
        drives the served page from Chrome.
        """
        script = (ROOT / "apps" / "control-surface" / "control-shell.js").read_text(encoding="utf-8")
        self.assertIn("function operationFromUrl", script)
        self.assertRegex(script, r"const restored = operationFromUrl\(\)[\s\S]{0,400}?"
                                 r"state\.idempotencyKey = \"\"",
                         "the restored branch must not mint a key; minting is the failure this path exists "
                         "to prevent")
        self.assertIn("carryOperationInUrl(result.task_id)", script)
        self.assertIn("restoreOperation(restored, createView)", script)
        self.assertIn("/api/control/operations/", script)
        self.assertNotIn("http://", script, "the shell must not reach outside its own origin")
        self.assertNotIn("https://", script)
        # the create-identity listeners must drop a stale URL identity, or the next reload re-asks about a
        # task_id the operator has already replaced. Scoped to the two listeners that mint the CREATE key:
        # the materialize form owns a different identity and must not clear this one.
        for anchor in ('el("task-id").addEventListener', 'el("regen").addEventListener'):
            start = script.index(anchor)
            block = script[start:start + 320]
            self.assertIn("newIdempotencyKey", block, block[:120])
            self.assertIn("clearOperationInUrl()", block,
                          f"{anchor} mints a fresh identity but leaves the old one in the URL")

    def test_a_plane_that_publishes_no_receipts_says_so_instead_of_calling_the_write_unverified(self) -> None:
        _status, result = self._post(request_payload())
        self.assertEqual(result["status"], "ACCEPTED")
        silent = control_service.ControlPlane(self.plane.store, project_root=ROOT,
                                             receipts_path=None, grants_path=self.plane.grants_path)
        answer = silent.operation_identity("WL-IDENTITY-1")
        write = [item for item in answer["outcomes"] if item["id"] == "write"][0]
        self.assertEqual(write["state"], "NO_RECEIPT_PUBLISHED", write)
        self.assertTrue(answer["found"], "the record exists whether or not this plane appends receipts")

    def test_a_row_whose_receipt_digest_diverged_is_not_reported_as_confirmed(self) -> None:
        """Falsifies CONFIRMED from the other side: the digest is the CURRENT projection, not any receipt.

        Built the way it happens: the write landed and was receipted, then the row moved under it (an
        in-place update by another writer of the same store). The receipt is still there and still names
        this identity, so a reader that only asked "is there a receipt?" would still say CONFIRMED.
        """
        self._post(request_payload())
        row = self.rows_for("WL-IDENTITY-1")[0]
        moved = json.loads(json.dumps(row))
        # The projection publishes key NAMES and a digest, not the goal text, so moving the goal would not
        # move the digest at all. Status is published, and status is what another writer of this store
        # actually changes under a receipt.
        moved["status"] = "RUNNING"
        self.plane.store.upsert_task(moved)
        _code, answer = self._get("/api/control/operations/WL-IDENTITY-1")
        write = [item for item in answer["outcomes"] if item["id"] == "write"][0]
        self.assertEqual(write["state"], "RECEIPT_DIGEST_DIVERGED", write)
        self.assertEqual(len(answer["receipts"]), 1, answer["receipts"])
        self.assertNotEqual(answer["record_digest"], answer["receipts"][0]["digest"],
                            "the diverged branch is only meaningful if the two digests really differ")
        self.assertIn("没有与当前摘要一致的回执", write["detail"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
