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
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from jsonschema import Draft202012Validator

from tests.conftest import produced_after, seed_issue, write_grants

RESULT_SCHEMA = "worklab/external-repair-result/v1"
COLLECTOR = "demo-collector"
PACK_SCHEMA_PATH = (Path(__file__).resolve().parents[2]
                    / "packages" / "contracts" / "schemas" / "workflow"
                    / "repair-pack.schema.json")


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
        "evidenceRefs": ["collector_health:" + COLLECTOR],
    }


def test_work_maintenance_loop_completes_and_survives_restart(server, work_project):
    # the work store starts empty: seed one open issue through the migrated store
    seed_issue(server.work.store, name=COLLECTOR)
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
    body = pack_response["handoff_text"]
    assert pack["status"] == "WAITING_APPROVAL"
    assert pack_response["attempt"]["execution_state"] == "WAITING_HANDOFF"

    # -- 导出 is a claim about content, not about a non-empty string. A body that
    # drops every bound issue and every verification step still passes `.strip()`,
    # so the material a human carries away is checked against what the pack bound
    # and against the published contract, here and not only in the install-mode
    # BLOCKED legacy projection file.
    pack_schema = json.loads(PACK_SCHEMA_PATH.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(pack_schema).iter_errors(pack),
                    key=lambda item: list(item.absolute_path))
    assert errors == [], "the exported pack violates repair-pack.schema.json: %s" % [
        (list(err.absolute_path), err.message) for err in errors]
    assert pack["schemaVersion"] == "workflow/repair-pack/v1"
    assert pack["binds"]["issueCount"] == 1
    assert pack["binds"]["evidenceRefs"] == ["collector_health:" + COLLECTOR]
    assert pack["binds"]["classes"] == ["SOURCE_FAILURE"]
    assert pack["binds"]["issueFingerprints"], "the pack bound no issue row to re-read"

    step_ids = [step["id"] for step in pack["plan"]["steps"]]
    assert "verify" in step_ids, "a handoff with no check step cannot be verified: %s" % step_ids
    assert len(step_ids) >= 4, step_ids
    for ref in pack["binds"]["evidenceRefs"]:
        assert "`%s`" % ref in body, "the material omits bound evidence " + repr(ref)
    for step_id in step_ids:
        assert step_id in body, "the material omits the " + repr(step_id) + " step"
    assert pack["verification"]["command"] in body, \
        "the material dropped the verification command the pack says it knows"
    assert pack["packId"] in body, "the material does not name the pack it belongs to"
    assert "未发送" in body or "sent=false" in body, \
        "the material must state that no handoff was sent"
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
    seed_issue(server.work.store, name=COLLECTOR, failures=0)
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


def _prepared_attempt(server, work_project, key: str):
    """A task with one PREPARED attempt, returned with the revision it exposes."""
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work",
        "title": "并发样例：" + key,
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False}})
    assert status == 201, task
    status, attempt = server.client.post(
        f"/api/v1/tasks/{task['task_id']}/attempts", {"idempotency_key": key})
    assert status == 201, attempt
    return task["task_id"], attempt["attempt_id"], attempt["revision"]


def test_concurrent_attempt_update_refuses_the_loser(server, work_project):
    """L12「并发修订冲突」on the unified envelope: two writers prepared against the
    SAME revision cannot both land.

    The knowledge side races one writer against another through
    ``tests/legacy/design/test_knowledge_library.py``; this is the same clause on the
    other state machine, because ``revision`` here is the only thing standing between
    a stale writer and a lost update. Two connections to the same file are used — the
    model of the second process the restart clause (L15) says may exist — so what is
    measured is the compare-and-swap itself, not sqlite3's single-connection
    statement interleaving (which is worse: on the shipped one-connection store a
    concurrent pair can also raise an untyped ``sqlite3.InterfaceError`` and leave
    BOTH writes uncommitted while one caller is told ``wrote``).

    The serial control at the bottom keeps the finding honest: the refusal word
    ``ATTEMPT_REVISION_CONFLICT`` does exist and does fire when the loser reads
    *after* the winner committed. What is untested — and what this test exists to
    pin — is the window where both read before either writes.
    """
    from backend.core.unified_store import StoreError, UnifiedStore

    writers = [UnifiedStore(server.local_root / "unified.sqlite3") for _ in range(2)]
    try:
        for round_index in range(3):
            _task_id, attempt_id, revision = _prepared_attempt(
                server, work_project, "race-%d" % round_index)
            barrier = threading.Barrier(2)

            def write(store, execution_state):
                barrier.wait()
                try:
                    store.update_attempt(attempt_id, expected_revision=revision,
                                         execution_state=execution_state)
                    return "wrote"
                except StoreError as error:
                    return str(error).split(" ")[0]
                except Exception as error:  # noqa: BLE001
                    return "UNTYPED:" + type(error).__name__

            with ThreadPoolExecutor(max_workers=2) as pool:
                futures = [pool.submit(write, writers[0], "RUNNING"),
                           pool.submit(write, writers[1], "QUEUED")]
                outcomes = sorted(future.result() for future in futures)
            landed = server.unified.get_attempt(attempt_id)
            assert outcomes == ["ATTEMPT_REVISION_CONFLICT", "wrote"], (
                "both writers prepared against revision %d were accepted; the loser "
                "was never refused: %s (execution_state is now %r, revision %d) — "
                "backend/core/unified_store.py:438-476 checks expected_revision in "
                "Python and then issues UPDATE ... WHERE attempt_id=? with no "
                "AND revision=? and no BEGIN IMMEDIATE, so the second write silently "
                "replaces the first" % (revision, outcomes, landed["execution_state"],
                                        landed["revision"]))
            assert landed["revision"] == revision + 1, landed
            assert landed["execution_state"] in ("RUNNING", "QUEUED"), landed

        # serial control: a writer that reads the committed revision and still
        # prepares against the old one is refused in exactly those words
        _task_id, attempt_id, revision = _prepared_attempt(server, work_project, "stale-1")
        server.unified.update_attempt(attempt_id, expected_revision=revision,
                                      execution_state="RUNNING")
        try:
            server.unified.update_attempt(attempt_id, expected_revision=revision,
                                          execution_state="QUEUED")
            raise AssertionError("a stale writer was accepted")
        except StoreError as error:
            assert str(error).startswith("ATTEMPT_REVISION_CONFLICT"), error
            assert repr(revision + 1) in str(error), (
                "the refusal must name the revision that exists now: %s" % error)
    finally:
        for store in writers:
            store.close()
