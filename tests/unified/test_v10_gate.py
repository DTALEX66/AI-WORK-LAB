# SPDX-License-Identifier: MIT
"""V10: the acceptance gate refuses completion claims that only assert VERIFIED,
forge receipts, or carry no evidence — and it separates *historical fact* from
*currently backed*.

The 2026-10-30 audit's F04 counterexample was a store where a result bound to a
non-existent attempt and pack, with an empty command, no evidence and an
unrelated fingerprint, was written one line of PASS and the gate still answered
``BACKED / exit 0``. The gate's own contract changed to close that, so the tests
changed with it. What each test still means is unchanged — a forged or expired
support must not read as readiness — and the way a forgery is now *created* is
different on purpose:

* the store API refuses to mint those rows at all, so a test that wants a forged
  row has to write it around the API, the way a pre-existing database would
  already contain it;
* both halves are asserted: the API refuses to write it, **and** the gate refuses
  to honour it once it exists.
"""
from __future__ import annotations

import json
import os
import sqlite3
import subprocess
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
GATE = TARGET_ROOT / "scripts" / "acceptance_gate.py"
#: venv 解释器的布局是平台的，不是机器的：Windows 是 Scripts/python.exe，POSIX 是 bin/python（审计 N05）。
VENV_PYTHON = TARGET_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

_TABLES = (
    "CREATE TABLE projects (project_id TEXT PRIMARY KEY, source TEXT NOT NULL,"
    " display_name TEXT NOT NULL, root_path TEXT, data_origin TEXT NOT NULL DEFAULT 'live',"
    " origin_provenance TEXT, registered_at TEXT NOT NULL);",
    "CREATE TABLE tasks (task_id TEXT PRIMARY KEY, project_id TEXT NOT NULL, kind TEXT NOT NULL,"
    " lifecycle TEXT NOT NULL DEFAULT 'DRAFT', title TEXT NOT NULL, input_refs TEXT NOT NULL,"
    " acceptance TEXT NOT NULL, professional_required INTEGER NOT NULL DEFAULT 0,"
    " current_attempt_id TEXT, revision INTEGER NOT NULL DEFAULT 1,"
    " data_origin TEXT NOT NULL DEFAULT 'live', origin_provenance TEXT,"
    " created_at TEXT NOT NULL, updated_at TEXT NOT NULL);",
    "CREATE TABLE attempts (attempt_id TEXT PRIMARY KEY, task_id TEXT NOT NULL,"
    " base_fingerprint TEXT NOT NULL DEFAULT '', execution_mode TEXT NOT NULL, executor_ref TEXT,"
    " execution_state TEXT NOT NULL, idempotency_key TEXT NOT NULL, pack_plan_id TEXT,"
    " pack_ref TEXT, binding_sha256 TEXT, candidate_version TEXT, handoff TEXT,"
    " revision INTEGER NOT NULL DEFAULT 1, data_origin TEXT NOT NULL DEFAULT 'live',"
    " origin_provenance TEXT, started_at TEXT, finished_at TEXT, created_at TEXT NOT NULL,"
    " updated_at TEXT NOT NULL, UNIQUE(task_id, idempotency_key));",
    "CREATE TABLE results (result_id TEXT PRIMARY KEY, task_id TEXT NOT NULL, attempt_id TEXT NOT NULL,"
    " pack_id TEXT, declared_result_id TEXT, subject_fingerprint TEXT NOT NULL DEFAULT '',"
    " artifact_refs TEXT NOT NULL DEFAULT '[]', content_sha256 TEXT NOT NULL,"
    " digest_vocabulary TEXT, binding TEXT, candidate_version TEXT, origin_chain TEXT,"
    " raw TEXT NOT NULL, data_origin TEXT NOT NULL DEFAULT 'live', origin_provenance TEXT,"
    " received_at TEXT NOT NULL);",
    "CREATE TABLE verifications (verification_id TEXT PRIMARY KEY, result_id TEXT NOT NULL,"
    " axis TEXT NOT NULL, outcome TEXT NOT NULL, subject_fingerprint TEXT NOT NULL DEFAULT '',"
    " command_ref TEXT, evidence_refs TEXT NOT NULL DEFAULT '[]', verifier_ref TEXT,"
    " approval_ref TEXT, identity_state TEXT, checks TEXT, current_validity TEXT,"
    " candidate_version TEXT, origin_chain TEXT, detail TEXT,"
    " data_origin TEXT NOT NULL DEFAULT 'live', origin_provenance TEXT, observed_at TEXT NOT NULL);",
)


def _run_gate(store_path: Path, work_store: Path | None = None,
              blockers: Path | None = None) -> tuple[int, dict]:
    command = [str(VENV_PYTHON), "-B", str(GATE), str(store_path)]
    if work_store is not None:
        command += ["--work-store", str(work_store)]
    if blockers is not None:
        command += ["--blockers", str(blockers)]
    completed = subprocess.run(command, capture_output=True, text=True, timeout=180,
                               encoding="utf-8", errors="replace")
    assert completed.stdout.strip(), (completed.returncode, completed.stderr[-2000:])
    return completed.returncode, json.loads(completed.stdout)


def _backed_chain(server, work_project, key: str) -> dict:
    """Drive the real API to a genuinely backed completion; returns ids for reuse.

    Both new tests need a store the gate actually accepts, so that a refusal can only
    come from the thing each test changes — the blocker register, or the verdict's
    candidate version.
    """
    from tests.conftest import produced_after, seed_issue, write_grants
    from tests.unified.test_v03_work_loop import _result_document
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "门与新断言 " + key,
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False, "data_origin": "test"}})
    assert status == 201, task
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": key})
    status, pack_response = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    write_grants(server)
    server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/approval",
                       {"authorization_ref": "g-" + key, "expected_version": 1})
    status, handoff = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/handoff-declarations",
        {"claim": "copiedByUser", "target_version": "v1", "actor": "user"})
    assert status == 200, handoff
    doc = _result_document(pack_response["pack"]["packId"], work_project["project_id"],
                           result_id="res-" + key, produced_at=produced_after(handoff))
    doc["targetVersion"] = "v1"
    doc["evidenceRefs"] = ["collector_health:demo-collector"]
    status, imported = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/results",
        {"result": doc, "data_origin": "test"})
    assert status == 201, imported
    seed_issue(server.work.store, failures=0)
    status, verification = server.client.post(
        f"/api/v1/results/{imported['result']['result_id']}/verifications", {"axis": "technical"})
    assert verification["outcome"] == "PASS", verification
    return dict(task_id=task["task_id"], result_id=imported["result"]["result_id"])


def test_gate_refuses_when_a_mandatory_blocker_is_registered(server, work_project, tmp_path):
    """L18「必做阻塞为0才本批完成」was narrative: the gate could print ready=true in the
    same round whose evidence named a BLOCKED item, because the two halves were never
    connected. Now a register is an input, and it moves the exit code."""
    _backed_chain(server, work_project, "gate-blk")
    store = server.local_root / "unified.sqlite3"
    work_store = server.local_root / "work-store.sqlite3"

    plain_code, plain = _run_gate(store, work_store=work_store)
    assert plain_code == 0 and plain["verdict"] == "BACKED", plain
    # running without the register is possible but is labelled, not silently trusted
    assert plain["batch_readiness"]["scope"] == "IN_STORE_CLAIMS_ONLY"
    assert any(w.startswith("MANDATORY_BLOCKER_REGISTER_NOT_SUPPLIED") for w in plain["warnings"])

    register = tmp_path / "blockers.json"
    register.write_text(json.dumps({"results": {"L17_legacy_projection": "BLOCKED"}}),
                        encoding="utf-8", newline="\n")
    code, verdict = _run_gate(store, work_store=work_store, blockers=register)
    assert code == 1, verdict
    assert verdict["verdict"] == "REFUSED"
    assert "MANDATORY_BLOCKER_REGISTERED" in [p["kind"] for p in verdict["problems"]]
    assert verdict["batch_readiness"]["ready"] is False
    assert verdict["warnings"] == []

    # completion_rule puts P2/P3 单列 — a conditional-phase gap is disclosed, not blocking
    register.write_text(json.dumps({"results": {"P2_native_hosts": "BLOCKED"}}),
                        encoding="utf-8", newline="\n")
    code2, second = _run_gate(store, work_store=work_store, blockers=register)
    assert code2 == 0 and second["verdict"] == "BACKED", second
    assert [row["id"] for row in second["blocker_register"]["disclosed"]] == ["P2_native_hosts"]
    assert second["blocker_register"]["blocking"] == []

    # a mandatory item the owner excluded from scope is listed with its authority,
    # and does not silently vanish either
    register.write_text(json.dumps({"items": [{
        "id": "A06_real_user_data", "status": "NOT_RUN", "phase": "P1",
        "scope_excluded_by_owner": True,
        "authority": "交接提示词 §边界：不主动迁移真实私有数据库"}]}),
        encoding="utf-8", newline="\n")
    code3, third = _run_gate(store, work_store=work_store, blockers=register)
    assert code3 == 0 and third["verdict"] == "BACKED", third
    disclosed = third["blocker_register"]["disclosed"]
    assert [row["id"] for row in disclosed] == ["A06_real_user_data"]
    assert disclosed[0]["authority"].startswith("交接提示词")


def test_gate_refuses_verdict_from_other_candidate(server, work_project):
    """L14「版本绑定」used to be untestable on data rows: the gate implemented
    VERDICT_FROM_OTHER_CANDIDATE but no store in any test ever carried a foreign
    candidate digest, so the branch could not fire. This writes one."""
    chain = _backed_chain(server, work_project, "gate-cand")
    store = server.local_root / "unified.sqlite3"
    conn = sqlite3.connect(str(store))
    try:
        changed = conn.execute("UPDATE verifications SET candidate_version=?",
                               ("b" * 64,)).rowcount
        conn.commit()
    finally:
        conn.close()
    assert changed >= 1, chain
    code, verdict = _run_gate(store, work_store=server.local_root / "work-store.sqlite3")
    assert code == 1, verdict
    kinds = [problem["kind"] for problem in verdict["problems"]]
    assert "VERDICT_FROM_OTHER_CANDIDATE" in kinds, verdict["problems"]


def _forge(path: Path, rows: list[tuple[str, tuple]]) -> None:
    """Write rows the way a pre-existing database holds them: around the API.

    The envelope now refuses to mint orphaned or unregistered rows, so a forged
    history can only be simulated at the storage layer — which is exactly the
    situation the gate exists to survive.
    """
    conn = sqlite3.connect(str(path))
    try:
        conn.executescript(" ".join(_TABLES))
        for statement, parameters in rows:
            conn.execute(statement, parameters)
        conn.commit()
    finally:
        conn.close()


def test_gate_accepts_backed_completions(server, work_project):
    from tests.conftest import produced_after, seed_issue, write_grants
    from tests.unified.test_v03_work_loop import RESULT_SCHEMA, _result_document
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "验收门正样例",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False, "data_origin": "test"}})
    assert status == 201, task
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "gate-1"})
    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    write_grants(server)
    server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/approval",
                       {"authorization_ref": "g-test-1", "expected_version": 1})
    status, handoff = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/handoff-declarations",
        {"claim": "copiedByUser", "target_version": "v1", "actor": "user"})
    assert status == 200, handoff
    doc = _result_document(pack_response["pack"]["packId"], work_project["project_id"],
                           result_id="res-gate-1", produced_at=produced_after(handoff))
    doc["targetVersion"] = "v1"
    doc["evidenceRefs"] = ["collector_health:demo-collector"]
    status, imported = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/results",
                                          {"result": doc, "data_origin": "test"})
    assert status == 201, imported
    seed_issue(server.work.store, failures=0)
    status, verification = server.client.post(
        f"/api/v1/results/{imported['result']['result_id']}/verifications", {"axis": "technical"})
    assert verification["outcome"] == "PASS", verification

    returncode, verdict = _run_gate(server.local_root / "unified.sqlite3",
                                   work_store=server.local_root / "work-store.sqlite3")
    assert returncode == 0, verdict
    assert verdict["verdict"] == "BACKED", verdict
    # a test-origin chain is supported but is never live evidence
    assert verdict["batch_readiness"]["live_eligible"] == []
    assert verdict["batch_readiness"]["synthetic_only"] == [task["task_id"]]
    assert verdict["full_product_readiness"]["ready"] is False


def test_gate_refuses_doc_only_completion(tmp_path):
    """A COMPLETED row with nothing behind it is refused, not quietly believed."""
    store_path = tmp_path / "doc-only.sqlite3"
    _forge(store_path, [
        ("INSERT INTO projects(project_id, source, display_name, data_origin, origin_provenance,"
         " registered_at) VALUES(?,?,?,?,?,?)",
         ("p" * 32, "work", "fixture", "test", "ENFORCED_CHAIN", "2026-10-30T00:00:00+00:00")),
        ("INSERT INTO tasks(task_id, project_id, kind, lifecycle, title, input_refs, acceptance,"
         " data_origin, origin_provenance, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         ("t" * 32, "p" * 32, "work", "COMPLETED", "仅改状态", "[]", "{}", "test",
          "ENFORCED_CHAIN", "2026-10-30T00:00:00+00:00", "2026-10-30T00:00:00+00:00")),
    ])
    returncode, verdict = _run_gate(store_path)
    assert returncode == 1
    assert verdict["verdict"] == "REFUSED"
    kinds = [problem["kind"] for problem in verdict["problems"]]
    assert "COMPLETION_NOT_BACKED" in kinds, verdict
    assert "NO_CURRENT_ATTEMPT" in json.dumps(verdict, ensure_ascii=False), verdict


def test_gate_refuses_forged_result_and_verdict(tmp_path):
    """The audit's exact counterexample: an orphan result plus one PASS line."""
    store_path = tmp_path / "forged.sqlite3"
    raw = {"synthetic": True}
    _forge(store_path, [
        ("INSERT INTO tasks(task_id, project_id, kind, lifecycle, title, input_refs, acceptance,"
         " current_attempt_id, data_origin, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
         ("t" * 32, "0" * 32, "work", "COMPLETED", "synthetic forged completion", "[]", "{}",
          "a" * 32, "test", "2026-10-30T00:00:00+00:00", "2026-10-30T00:00:00+00:00")),
        ("INSERT INTO attempts(attempt_id, task_id, execution_mode, execution_state,"
         " idempotency_key, pack_plan_id, data_origin, created_at, updated_at) VALUES(?,?,?,?,?,?,?,?,?)",
         ("a" * 32, "t" * 32, "MANUAL_COPY", "RESULT_RECEIVED", "k", "does-not-exist",
          "test", "2026-10-30T00:00:00+00:00", "2026-10-30T00:00:00+00:00")),
        ("INSERT INTO results(result_id, task_id, attempt_id, pack_id, subject_fingerprint,"
         " artifact_refs, content_sha256, raw, data_origin, received_at) VALUES(?,?,?,?,?,?,?,?,?,?)",
         ("r" * 32, "t" * 32, "does-not-exist", "does-not-exist", "stale-source", "[]",
          "0" * 64, json.dumps(raw), "test", "2026-10-30T00:00:00+00:00")),
        ("INSERT INTO verifications(verification_id, result_id, axis, outcome,"
         " subject_fingerprint, evidence_refs, data_origin, observed_at) VALUES(?,?,?,?,?,?,?,?)",
         ("v" * 32, "r" * 32, "technical", "PASS", "unrelated", "[]", "test",
          "2026-10-30T00:00:01+00:00")),
    ])
    returncode, verdict = _run_gate(store_path)
    assert returncode == 1, verdict
    kinds = [problem["kind"] for problem in verdict["problems"]]
    assert "RESULT_ORPHAN_ATTEMPT" in kinds, verdict
    assert "VERIFICATION_PASS_WITHOUT_EVIDENCE" in kinds, verdict
    assert "VERIFICATION_SUBJECT_MISMATCH" in kinds, verdict
    assert "PACK_RECORD_ABSENT" in kinds or "TASK_ORPHAN_PROJECT" in kinds, verdict
    assert verdict["verdict"] == "REFUSED"


def test_store_api_refuses_to_mint_the_forgery(server):
    """The other half of F04: the write path never produces those rows in the first place."""
    from backend.core.unified_store import StoreError, UnifiedStore
    store = UnifiedStore(server.local_root / "api-refusals.sqlite3")
    try:
        try:
            store.create_task(project_id="0" * 32, kind="work", title="orphan",
                              input_refs=[], acceptance={})
            raise AssertionError("a task under an unregistered project must be refused")
        except StoreError as error:
            assert str(error).startswith("PROJECT_NOT_FOUND"), error
        project = store.register_project(source="work", display_name="x")
        task = store.create_task(project_id=project["project_id"], kind="work", title="t",
                                 input_refs=[], acceptance={})
        try:
            store.record_result(task_id=task["task_id"], attempt_id="does-not-exist",
                                pack_id=None, subject_fingerprint="", artifact_refs=[],
                                content_sha256="0" * 64, raw={}, data_origin="test")
            raise AssertionError("a result bound to no attempt must be refused")
        except StoreError as error:
            assert str(error).startswith("RESULT_ATTEMPT_NOT_FOUND"), error
        try:
            store.record_verification(result_id="does-not-exist", axis="technical", outcome="PASS")
            raise AssertionError("a verdict for no result must be refused")
        except StoreError as error:
            assert str(error).startswith("VERIFICATION_RESULT_NOT_FOUND"), error
    finally:
        store.close()


def test_latest_failure_stops_supporting_readiness(server, work_project):
    """A FAIL after a PASS does not erase the PASS, but it ends the readiness claim."""
    from tests.conftest import produced_after, seed_issue, write_grants
    from tests.unified.test_v03_work_loop import _result_document
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "复发样例：FAIL 之后不得凭旧 PASS 宣称就绪",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False, "data_origin": "test"}})
    assert status == 201, task
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "recurrence"})
    attempt_id = attempt["attempt_id"]
    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt_id}/pack", {})
    assert status == 201, pack_response
    write_grants(server)
    server.client.post(f"/api/v1/attempts/{attempt_id}/approval",
                       {"authorization_ref": "g-test-1", "expected_version": 1})
    status, handoff = server.client.post(
        f"/api/v1/attempts/{attempt_id}/handoff-declarations",
        {"claim": "copiedByUser", "target_version": "work-store-v1", "actor": "user"})
    assert status == 200, handoff
    status, imported = server.client.post(f"/api/v1/attempts/{attempt_id}/results", {
        "result": _result_document(pack_response["pack"]["packId"], work_project["project_id"],
                                   produced_at=produced_after(handoff)),
        "data_origin": "test"})
    assert status == 201, imported
    result_id = imported["result"]["result_id"]
    seed_issue(server.work.store, failures=0)
    status, passing = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                         {"axis": "technical"})
    assert passing["outcome"] == "PASS", passing
    status, done = server.client.get(f"/api/v1/tasks/{task['task_id']}")
    assert done["lifecycle"] == "COMPLETED"
    # the fault comes back: a fresh verification reads the store and answers FAIL
    seed_issue(server.work.store, failures=3)
    status, failing = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                         {"axis": "technical"})
    assert failing["outcome"] == "FAIL", failing
    status, after = server.client.get(f"/api/v1/tasks/{task['task_id']}")
    assert after["lifecycle"] == "ACTIVE", after
    support = server.client.get(f"/api/v1/tasks/{task['task_id']}/completion")[1]
    assert support["supported"] is False
    assert "LATEST_TECHNICAL_VERDICT_NOT_PASS" in json.dumps(support, ensure_ascii=False), support
    # the earlier PASS is still a historical fact — the store does not delete it
    verdicts = server.client.get(f"/api/v1/results/{result_id}")[1]["verifications"]
    assert [row["outcome"] for row in verdicts] == ["PASS", "FAIL"]
    returncode, gate = _run_gate(server.local_root / "unified.sqlite3",
                                work_store=server.local_root / "work-store.sqlite3")
    assert returncode == 0, gate
    assert gate["historical_claims"], gate
    assert task["task_id"] not in gate["batch_readiness"]["supported_now"]
