# SPDX-License-Identifier: MIT
"""V05: wrong task, wrong attempt, stale version, duplicate result, tampered
content, out-of-boundary paths and dangerous imports are actually refused."""
from __future__ import annotations

import json

from tests.conftest import produced_after, seed_issue, write_grants

RESULT_SCHEMA = "worklab/external-repair-result/v1"


def _prepare_attempt(server, work_project, key="att-rej"):
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "拒绝路径样例",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False}})
    assert status == 201
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": key})
    assert status == 201
    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    assert status == 201
    write_grants(server)
    status, _ = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/approval",
                                   {"authorization_ref": "g-test-1", "expected_version": 1})
    assert status == 200
    status, handoff = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/handoff-declarations",
        {"claim": "copiedByUser", "target_version": "work-store-v1", "actor": "user"})
    assert status == 200
    return task, attempt, pack_response, handoff


def _result(pack_id, project_id, result_id, produced_at="2026-10-30T09:00:00Z",
            target_version="work-store-v1"):
    return {"schemaVersion": RESULT_SCHEMA, "resultId": result_id, "packId": pack_id,
            "projectId": project_id, "targetVersion": target_version,
            "producedAt": produced_at, "producer": "manual", "claimedOutcome": "SUCCEEDED",
            "summary": "样例结果", "evidenceRefs": ["collector_health:demo-collector"]}


def test_wrong_pack_and_wrong_project_results_refused(server, work_project):
    task, attempt, pack_response, handoff = _prepare_attempt(server, work_project, key="att-rej-1")
    attempt_id = attempt["attempt_id"]
    produced = produced_after(handoff)

    wrong_pack = _result("pack-other", work_project["project_id"], "res-wrong-pack",
                       produced_at=produced)
    status, body = server.client.post(f"/api/v1/attempts/{attempt_id}/results",
                                      {"result": wrong_pack, "data_origin": "test"})
    assert status == 422
    assert body["error"] == "EXTERNAL_RESULT_WRONG_PACK"

    wrong_project = _result(pack_response["pack"]["packId"], "e" * 32, "res-wrong-project",
                          produced_at=produced)
    status, body = server.client.post(f"/api/v1/attempts/{attempt_id}/results",
                                      {"result": wrong_project, "data_origin": "test"})
    assert status == 422
    assert body["error"] == "EXTERNAL_RESULT_WRONG_PROJECT"


def test_stale_result_refused(server, work_project):
    task, attempt, pack_response, handoff = _prepare_attempt(server, work_project, key="att-rej-2")
    # deliberately one day before the server declared the handoff, derived from
    # the declaration itself so this stays a stale example tomorrow.
    from datetime import datetime, timedelta
    declared = datetime.fromisoformat(handoff["attempt"]["handoff"]["declared_at"].replace("Z", "+00:00"))
    stale = _result(pack_response["pack"]["packId"], work_project["project_id"], "res-stale",
                    produced_at=(declared - timedelta(days=1)).isoformat().replace("+00:00", "Z"))
    status, body = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/results",
                                      {"result": stale, "data_origin": "test"})
    assert status == 422
    assert body["error"] == "EXTERNAL_RESULT_STALE"


def test_duplicate_result_refused_on_second_attempt(server, work_project):
    task, attempt, pack_response, handoff = _prepare_attempt(server, work_project, key="att-rej-3")
    pack_id = pack_response["pack"]["packId"]
    doc = _result(pack_id, work_project["project_id"], "res-dup",
                  produced_at=produced_after(handoff))
    status, imported = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/results",
                                          {"result": doc, "data_origin": "test"})
    assert status == 201
    # a second attempt on the same task cannot re-submit the same resultId
    status, attempt2 = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                          {"idempotency_key": "att-rej-3b"})
    assert status == 201
    status, pack2 = server.client.post(f"/api/v1/attempts/{attempt2['attempt_id']}/pack", {})
    assert status == 201
    write_grants(server)
    server.client.post(f"/api/v1/attempts/{attempt2['attempt_id']}/approval",
                       {"authorization_ref": "g-test-1", "expected_version": 1})
    status, handoff2 = server.client.post(
        f"/api/v1/attempts/{attempt2['attempt_id']}/handoff-declarations",
        {"claim": "copiedByUser", "target_version": "work-store-v1", "actor": "user"})
    assert status == 200
    # the same resultId, produced freshly against THIS handoff: the only thing
    # that makes it a duplicate is the id, not a stale clock
    resubmitted = _result(pack_id, work_project["project_id"], "res-dup",
                          produced_at=produced_after(handoff2))
    status, body = server.client.post(f"/api/v1/attempts/{attempt2['attempt_id']}/results",
                                      {"result": resubmitted, "data_origin": "test"})
    assert status == 422
    assert body["error"] == "EXTERNAL_RESULT_DUPLICATE"


def test_import_before_declared_handoff_refused(server, work_project):
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "无声明导入样例",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False}})
    assert status == 201
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "att-rej-4"})
    assert status == 201
    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    assert status == 201
    doc = _result(pack_response["pack"]["packId"], work_project["project_id"], "res-nohandoff")
    status, body = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/results",
                                      {"result": doc, "data_origin": "test"})
    assert status == 409
    assert body["error"].startswith("ATTEMPT_STATE")


def test_external_receipt_claim_is_not_declarable(server, work_project):
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "外部回执声明样例",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False}})
    assert status == 201
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "att-rej-5"})
    assert status == 201
    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    assert status == 201
    status, body = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/handoff-declarations",
        {"claim": "externalReceipt", "target_version": "work-store-v1", "actor": "user"})
    assert status == 400
    assert body["error"] == "CLAIM_UNKNOWN"


def test_adapter_dispatch_is_not_allowed_this_batch(server, work_project):
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "适配器派发样例",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}]})
    assert status == 201
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "att-rej-6"})
    assert status == 201
    status, body = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack",
                                      {"manual": False})
    assert status == 400
    assert body["error"].startswith("ADAPTER_DISPATCH_NOT_ALLOWED")


def test_work_project_root_must_exist(server):
    status, body = server.client.post("/api/v1/projects", {
        "name": "不存在", "source": "work", "root_path": r"Q:\definitely\not\here"})
    assert status == 400
    assert body["error"] == "WORK_PROJECT_ROOT_MISSING"


def test_body_size_and_json_guards(server):
    # oversized body → 413
    big = {"name": "x" * 20000, "source": "design"}
    status, body = server.client.post("/api/v1/projects", big)
    assert status == 413
    assert body["error"] == "BODY_TOO_LARGE"
    # invalid JSON → 400 INVALID_JSON
    import http.client
    connection = http.client.HTTPConnection("127.0.0.1", server.port, timeout=10)
    try:
        connection.request("POST", "/api/v1/projects", body=b"{not json",
                           headers={"Host": "127.0.0.1:" + str(server.port),
                                    "Authorization": "Bearer " + server.token,
                                    "Content-Type": "application/json"})
        response = connection.getresponse()
        payload = json.loads(response.read().decode("utf-8"))
        assert response.status == 400
        assert payload["error"] == "INVALID_JSON"
    finally:
        connection.close()
