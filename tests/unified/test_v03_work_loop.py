# SPDX-License-Identifier: MIT
"""V03: the work-maintenance manual task-pack closed loop, end to end.

create task → attempt → pack (draft, WAITING_APPROVAL) → grant-backed approval →
user handoff declaration → controlled result import → server-side technical
verification through the migrated verify_repair_record → task completion →
service restart readback. The handoff declaration below is a TEST simulation
(data_origin=test on the result); it is not a real user handoff.
"""
from __future__ import annotations

import json

from tests.conftest import produced_after, seed_issue, write_grants

RESULT_SCHEMA = "worklab/external-repair-result/v1"


def _result_document(pack_id, project_id, result_id="res-demo-1",
                     produced_at=None, claimed="SUCCEEDED"):
    return {
        "schemaVersion": RESULT_SCHEMA,
        "resultId": result_id,
        "packId": pack_id,
        "projectId": project_id,
        "targetVersion": "work-store-v1",
        "producedAt": produced_at or "1970-01-01T00:00:00Z",
        "producer": "manual",
        "claimedOutcome": claimed,
        "summary": "演示采集器连续失败已修复（测试夹具）",
        "evidenceRefs": ["collector_health:demo-collector"],
    }


def test_work_maintenance_loop_completes_and_survives_restart(server, work_project):
    # the work store starts empty: seed one open issue through the migrated store
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "维护样例：演示采集器连续失败",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False}})
    assert status == 201, task
    task_id = task["task_id"]

    # attempt with idempotency: the same key reads back the same attempt
    status, attempt = server.client.post(f"/api/v1/tasks/{task_id}/attempts",
                                         {"idempotency_key": "att-1"})
    assert status == 201
    attempt_id = attempt["attempt_id"]
    status, attempt_again = server.client.post(f"/api/v1/tasks/{task_id}/attempts",
                                               {"idempotency_key": "att-1"})
    assert status == 200
    assert attempt_again["attempt_id"] == attempt_id
    assert attempt_again["execution_state"] == "PREPARED"

    # pack: a draft only — export never decides anything
    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt_id}/pack", {})
    assert status == 201, pack_response
    pack = pack_response["pack"]
    assert pack["status"] == "WAITING_APPROVAL"
    assert pack_response["handoff_text"].strip()
    assert pack_response["attempt"]["execution_state"] == "WAITING_HANDOFF"
    pack_id = pack["packId"]

    # approval needs a resolvable grant (fail closed without the grants file)
    status, body = server.client.post(f"/api/v1/attempts/{attempt_id}/approval",
                                      {"authorization_ref": "g-test-1", "expected_version": 1})
    assert status == 409
    assert body["error"].startswith("WORK_GRANTS_ABSENT")
    write_grants(server)
    status, approval = server.client.post(f"/api/v1/attempts/{attempt_id}/approval",
                                          {"authorization_ref": "g-test-1",
                                           "expected_version": 1})
    assert status == 200, approval
    assert approval["record"]["status"] == "APPROVED"

    # the user's own handoff statement; target_version is declared, not inferred
    status, handoff = server.client.post(f"/api/v1/attempts/{attempt_id}/handoff-declarations", {
        "claim": "copiedByUser", "target_version": "work-store-v1",
        "channel": "manual-copy", "actor": "user"})
    assert status == 200, handoff
    assert handoff["attempt"]["execution_state"] == "HANDOFF_DECLARED"

    # result import: wrong version is refused before anything is stored
    wrong = _result_document(pack_id, work_project["project_id"],
                             produced_at=produced_after(handoff))
    wrong["targetVersion"] = "some-other-version"
    status, body = server.client.post(f"/api/v1/attempts/{attempt_id}/results",
                                      {"result": wrong, "data_origin": "test"})
    assert status == 422
    assert body["error"] == "EXTERNAL_RESULT_WRONG_VERSION"

    # the real (test-fixture) result
    status, imported = server.client.post(f"/api/v1/attempts/{attempt_id}/results", {
        "result": _result_document(pack_id, work_project["project_id"],
                                   produced_at=produced_after(handoff)),
        "data_origin": "test"})
    assert status == 201, imported
    assert imported["attempt"]["execution_state"] == "RESULT_RECEIVED"
    assert imported["result"]["data_origin"] == "test"
    result_id = imported["result"]["result_id"]

    # technical verification against the store as it stands: issue still open → FAIL
    status, failing = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                         {"axis": "technical"})
    assert status == 201
    assert failing["outcome"] == "FAIL"

    status, task_now = server.client.get(f"/api/v1/tasks/{task_id}")
    assert task_now["lifecycle"] == "ACTIVE"

    # the store says fixed: the fingerprint leaves the projection → RESOLVED → PASS
    seed_issue(server.work.store, failures=0)
    status, passing = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                         {"axis": "technical"})
    assert status == 201
    assert passing["outcome"] == "PASS"

    status, completed = server.client.get(f"/api/v1/tasks/{task_id}")
    assert completed["lifecycle"] == "COMPLETED"

    # restart readback: fresh stores over the same files see the same facts
    from backend.core.unified_store import UnifiedStore
    from backend.core.workpacks import WorkPacks
    reopened_unified = UnifiedStore(server.local_root / "unified.sqlite3")
    reopened_work = WorkPacks(server.local_root / "work-store.sqlite3", grants_path=None)
    try:
        reopened_task = reopened_unified.get_task(task_id)
        assert reopened_task["lifecycle"] == "COMPLETED"
        assert reopened_task["attempts"][0]["execution_state"] == "RESULT_RECEIVED"
        record = reopened_work.read_record(pack_id)
        assert record["status"] == "SUCCEEDED"
        assert record["payload"]["pack"]["packId"] == pack_id
    finally:
        reopened_unified.close()
        reopened_work.close()
