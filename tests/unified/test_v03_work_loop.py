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


# ---------------------------------------------------------------------------
# 2026-11-01：入口登记行闭合（migration/ui-entry-disposition.csv）
#
# 下列节点逐行对应登记表里的入口：04#L14|work:tools、04#L15|work:monitoring、
# 04#L21|work:audit、04#L28|work:execution-detail、04#L47|design:records、
# 04#L48|design:deliverables、04#L49|design:evidence（注意：L47/L48/L49 三行的
# 实际 `来源行标识` 前缀是 design:，不是 work:；本文件按 CSV 现读的行执行，
# work:evidence 是另一行 04#L29，已由 test_v11_audit_rework.py 的 F09 节点覆盖，
# 不在这里重复）。每行的断言实质都是「读回内容 = 我刚写进去的那个对象」，
# 每条断言配一个可执行的植入反证节点（_falsification 后缀）：把返回里的标识
# 改掉、把条数顶成常量，谓词必须报红；谓词函数与主节点共用同一份实现。
# STITCH 边界：L47/L48/L49 登记的验收原文含「视图未生成」的前端渲染要求，
# 本文件只断言后端数据面那一半，渲染不由这些节点证明（见各 docstring）。
# ---------------------------------------------------------------------------

ENTRY_COLLECTOR = "demo-collector"  # 与模块级 _result_document 的 evidenceRefs 同轴


def _tools_row_problems(row, *, expected_state, candidate_digest, record=None,
                        expected_qualification=None, expected_qualification_detail=None):
    """工具行是否真由资格台账里那条记录派生；返回问题清单，空即通过。"""
    problems = []
    if row.get("candidate_version") != candidate_digest:
        problems.append("candidate_version-names-a-different-build")
    if row.get("state") != expected_state:
        problems.append("state-not-" + expected_state)
    if expected_qualification is not None and row.get("qualification") != expected_qualification:
        problems.append("qualification-not-" + expected_qualification)
    if (expected_qualification_detail is not None
            and row.get("qualification_detail") != expected_qualification_detail):
        problems.append("qualification_detail-not-as-expected")
    evidence = row.get("evidence")
    if record is None:
        if evidence is not None:
            problems.append("evidence-present-without-appended-record")
    elif not isinstance(evidence, dict):
        problems.append("evidence-missing-for-appended-record")
    else:
        if evidence.get("observed_at") != record["observed_at"]:
            problems.append("evidence.observed_at-not-the-appended-instant")
        if evidence.get("candidate_digest") != record["candidate_digest"]:
            problems.append("evidence.candidate_digest-not-the-appended-record")
        if not set(record.get("evidence_refs") or []) <= set(evidence.get("evidence_refs") or []):
            problems.append("evidence.evidence_refs-not-the-appended-refs")
    return problems


def test_entry_work_tools_state_is_read_from_the_qualification_ledger(server):
    """04#L14|work:tools — GET /api/v1/tools 的 quality-gate 行由台账记录派生。

    同一入口在「该 capability+operation 无记录」与「有我刚追加的记录」两种状态下的
    回答必须不同，且不同之处就是我写入的那条：observed_at 时间戳、evidence_refs、
    candidate_digest 全部来自我刚 append 的台账行。两步递进：
    ① test-origin 记录 → 状态仍 NOT_PROBED，但 qualification_detail 点名
      "synthetic probe origin"，evidence 块出现且等于我写的那条；
    ② 真跑的 loopback 探测记录（子进程真的对 /api/v1/health 发了一次 200 认证 GET）
      → state 从记录 connection 轴读出（NOT_REQUIRED），qualification VERIFIED。

    明确没有证明：quality gate 本身可用（②的探测对象是 /api/v1/health，不是门）；
    「工具/我的工具」前端视图渲染（STITCH 边界，登记为视图未生成）。
    """
    from backend.core.qualifications import loopback_http_probe, probe_record

    status, health = server.client.get("/api/v1/health")
    assert status == 200, health
    candidate = health["candidate_version"]
    digest = candidate["digest"]

    status, payload = server.client.get("/api/v1/tools")
    assert status == 200, payload
    rows = {row["tool_id"]: row for row in payload["tools"]}
    assert payload["count"] == len(payload["tools"])
    assert payload["candidate_version"] == digest, \
        "tools 与 health 报的不是同一个运行版本"
    assert _tools_row_problems(rows["quality-gate"], expected_state="NOT_PROBED",
                               candidate_digest=digest) == []

    status, ledger0 = server.client.get("/api/v1/qualification-evidence")
    assert status == 200, ledger0

    # 写入一：test-origin 记录（观察时刻钉在过去，过期窗口钉在未来，保证后写的
    # live 记录在 latest_for 的 max(observed_at) 上严格胜出）
    synthetic = probe_record(capability_id="work.quality_gate", operation="quality_gate.run",
                             scope="local_read", subject="entry-probe-fixture",
                             version=candidate, outcome="VERIFIED",
                             evidence_refs=["probe:work.quality_gate/entry-probe-fixture"],
                             detail="入口登记读回夹具", data_origin="test",
                             connection="CONNECTED")
    synthetic["observed_at"] = "2000-01-01T00:00:00+00:00"
    synthetic["expires_at"] = "2999-12-31T00:00:00+00:00"
    server.qualifications.append(synthetic)

    status, payload = server.client.get("/api/v1/tools")
    rows = {row["tool_id"]: row for row in payload["tools"]}
    assert _tools_row_problems(
        rows["quality-gate"], expected_state="NOT_PROBED", candidate_digest=digest,
        record=synthetic, expected_qualification="NOT_VERIFIED",
        expected_qualification_detail="synthetic probe origin") == []

    status, ledger1 = server.client.get("/api/v1/qualification-evidence")
    assert ledger1["count"] == ledger0["count"] + 1, (ledger0["count"], ledger1["count"])
    mine = [row for row in ledger1["records"]
            if "probe:work.quality_gate/entry-probe-fixture" in (row["evidence_refs"] or [])]
    assert len(mine) == 1 and mine[0]["observed_at"] == synthetic["observed_at"], \
        "台账读回的不是我刚写的那条"

    # 写入二：真执行的 loopback 探测（子进程独立发一次带 Bearer 的 GET，令牌走 stdin）
    live = loopback_http_probe(capability_id="work.quality_gate", operation="quality_gate.run",
                               version=candidate, base_url="http://127.0.0.1:%d" % server.port,
                               path="/api/v1/health", command=[], token=server.token)
    assert live["outcome"] == "VERIFIED", live["detail"]
    server.qualifications.append(live)

    status, payload = server.client.get("/api/v1/tools")
    rows = {row["tool_id"]: row for row in payload["tools"]}
    assert _tools_row_problems(
        rows["quality-gate"], expected_state="NOT_REQUIRED", candidate_digest=digest,
        record=live, expected_qualification="VERIFIED") == []
    assert rows["quality-gate"]["evidence"]["matches_running_candidate"] is True


def test_entry_work_tools_ledger_record_falsification():
    """植入反证（tools）：把 evidence 的 observed_at 换成别的时刻、state 顶成
    CONNECTED、candidate_version 换成别的构建 → 谓词必须逐条报红。"""
    digest = "a" * 64
    record = {"observed_at": "2026-11-01T00:00:00+00:00", "candidate_digest": digest,
              "evidence_refs": ["probe:work.quality_gate/fixture"]}
    clean = {"state": "NOT_PROBED", "candidate_version": digest,
             "qualification": "NOT_VERIFIED",
             "qualification_detail": "synthetic probe origin",
             "evidence": {"observed_at": record["observed_at"],
                          "candidate_digest": digest,
                          "evidence_refs": list(record["evidence_refs"])}}
    kwargs = dict(expected_state="NOT_PROBED", candidate_digest=digest, record=record,
                  expected_qualification="NOT_VERIFIED",
                  expected_qualification_detail="synthetic probe origin")
    assert _tools_row_problems(clean, **kwargs) == []

    tampered = json.loads(json.dumps(clean))
    tampered["evidence"]["observed_at"] = "1970-01-01T00:00:00+00:00"
    assert "evidence.observed_at-not-the-appended-instant" in _tools_row_problems(tampered, **kwargs)

    tampered = json.loads(json.dumps(clean))
    tampered["state"] = "CONNECTED"
    assert "state-not-NOT_PROBED" in _tools_row_problems(tampered, **kwargs)

    tampered = json.loads(json.dumps(clean))
    tampered["candidate_version"] = "b" * 64
    assert "candidate_version-names-a-different-build" in _tools_row_problems(tampered, **kwargs)

    no_record = {"state": "NOT_PROBED", "candidate_version": digest, "evidence": None}
    assert _tools_row_problems(no_record, expected_state="NOT_PROBED",
                               candidate_digest=digest) == []
    assert "evidence-present-without-appended-record" in _tools_row_problems(
        dict(no_record, evidence={"observed_at": "x"}), expected_state="NOT_PROBED",
        candidate_digest=digest)


def _snapshot_collector_problems(collectors, seeded):
    """监控快照里的采集器行是否等于我刚写入 store 的那一条。"""
    matches = [row for row in collectors if row.get("collector") == seeded["name"]]
    if len(matches) != 1:
        return ["collector-row-count-%d-not-1" % len(matches)]
    row = matches[0]
    problems = []
    for field, expected in (("consecutiveFailures", seeded["consecutiveFailures"]),
                            ("totalRuns", seeded["totalRuns"]),
                            ("lastRunAt", seeded["lastRunAt"])):
        if row.get(field) != expected:
            problems.append("collector.%s-not-the-written-value" % field)
    return problems


def test_entry_work_monitoring_snapshot_collector_row_is_the_one_written(server):
    """04#L15|work:monitoring — GET /api/work/observer/snapshot 的 collectors 块
    读回的就是我写进 CanonicalStore 的那一行。

    空台账状态：快照里不存在这个采集器名；写入一条（name/consecutiveFailures=3/
    totalRuns=5/lastRunAt 全部由我定），再读：行数恰好多 1，且这 1 行的三个字段
    就是我写的值；revision 来自 store 自己的 seed_revision()，不是常量。

    明确没有证明：持续 watcher/SSE 推送（登记缺口写明仍在独立 sidecar）；
    issues 投影的实时性（_build_issues_projection 有进程内 TTL 缓存，本节点
    刻意不碰它）；「项目/运行状态」前端视图渲染（STITCH 边界）。
    """
    name = "v03-monitor-entry-collector"
    seeded = {"name": name, "consecutiveFailures": 3, "totalRuns": 5,
              "lastRunAt": "2026-10-31T09:00:00Z"}

    status, snapshot = server.client.get("/api/work/observer/snapshot")
    assert status == 200, snapshot
    assert snapshot.get("collectors") is not None, \
        "快照没有 collectors 块（store 不可读时它会缺席）：" + str(snapshot.get("code"))
    rows0 = snapshot["collectors"]
    assert not any(row.get("collector") == name for row in rows0), \
        "空台账状态下不应已有我命名的采集器行"

    server.work.store.upsert_collector_health(seeded)

    status, snapshot = server.client.get("/api/work/observer/snapshot")
    assert status == 200, snapshot
    rows1 = snapshot["collectors"]
    assert len(rows1) == len(rows0) + 1, (len(rows0), len(rows1))
    assert _snapshot_collector_problems(rows1, seeded) == []
    assert snapshot["revision"] == server.work.store.seed_revision(), \
        "快照 revision 不是 store 自己报的修订号"


def test_entry_work_monitoring_snapshot_collector_falsification():
    """植入反证（monitoring）：把读回的 consecutiveFailures 顶成 7、把行丢掉、
    把行数顶成常量 → 谓词必须报红；正确行必须为绿。"""
    seeded = {"name": "n-1", "consecutiveFailures": 3, "totalRuns": 5,
              "lastRunAt": "2026-10-31T09:00:00Z"}
    clean = [{"collector": "n-1", "consecutiveFailures": 3, "totalRuns": 5,
              "lastRunAt": "2026-10-31T09:00:00Z"}]
    assert _snapshot_collector_problems(clean, seeded) == []

    tampered = json.loads(json.dumps(clean))
    tampered[0]["consecutiveFailures"] = 7
    assert "collector.consecutiveFailures-not-the-written-value" in \
        _snapshot_collector_problems(tampered, seeded)

    assert _snapshot_collector_problems([], seeded) == ["collector-row-count-0-not-1"]
    assert _snapshot_collector_problems(clean + clean, seeded) == ["collector-row-count-2-not-1"]


def _integrity_problems(report, *, expected_counts, tampered_result_id=None):
    """integrity 报表的计数与具名问题是否恰由我写入/篡改的行派生。"""
    problems = []
    if report.get("counts") != expected_counts:
        problems.append("counts-not-the-rows-written:%r" % (report.get("counts"),))
    found = report.get("problems") or []
    if tampered_result_id is None:
        if found:
            problems.append("unexpected-problems-" + str(sorted(p["kind"] for p in found)))
    else:
        mismatches = [p for p in found if p.get("kind") == "RESULT_DIGEST_MISMATCH"]
        if len(mismatches) != 1:
            problems.append("digest-mismatch-problem-count-not-1")
        elif mismatches[0].get("id") != tampered_result_id:
            problems.append("digest-problem-does-not-name-my-result")
        if len(found) != 1:
            problems.append("problem-set-larger-than-the-tampering")
    return problems


def test_entry_work_audit_integrity_names_the_tampered_result(server):
    """04#L21|work:audit — GET /api/v1/integrity 的口径直读 unified store 的行。

    三段状态差：
    ① 空台账：counts 全 0、problems 为空；
    ② 经 HTTP 建项目+任务+attempt，再按存储合同（同一 result_digest 口径）写入
      一条摘要正确的结果：counts.tasks/attempts/results 各 1（与 /api/v1/tasks
      条数交叉核对），problems 仍为空——约束下的合法写入不产生问题；
    ③ 绕过合同直接把 results.content_sha256 改成别的摘要（该报表存在的理由正是
      约束只挡新写的引用关系，挡不住值列被篡改/落地前的坏行，报表要能点名）：
      problems 恰好 1 条 RESULT_DIGEST_MISMATCH，id 就是我写入的那条服务端生成
      的 result_id，counts 不变。读回的标识就是我写进去的那一个。
    （新库外键禁止 ATTEMPT_ORPHAN_TASK 型孤儿行，故篡改选在可覆写的摘要列。）

    明确没有证明：修复建议或自动清理（报表只点名不删改）；「设置/诊断与审计」
    前端视图渲染（STITCH 边界）。
    """
    from backend.core.unified_store import DIGEST_V2, result_digest

    status, report = server.client.get("/api/v1/integrity")
    assert status == 200, report
    assert _integrity_problems(report, expected_counts={"tasks": 0, "attempts": 0,
                                                        "results": 0}) == []

    status, project = server.client.post("/api/v1/projects", {
        "name": "审计入口样例", "source": "design", "data_origin": "test"})
    assert status == 201, project
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design",
        "title": "入口登记 04#L21：审计口径读回",
        "acceptance": {"professional_required": False, "data_origin": "test"}})
    assert status == 201, task
    status, attempt = server.client.post(
        f"/api/v1/tasks/{task['task_id']}/attempts", {"idempotency_key": "att-audit-1"})
    assert status == 201, attempt

    raw = {"schemaVersion": "ai-work-lab/entry-integrity-probe/v0",
           "note": "integrity 口径探针结果（测试夹具）"}
    stored = server.unified.record_result(
        task_id=task["task_id"], attempt_id=attempt["attempt_id"], pack_id=None,
        subject_fingerprint="sha256:" + "1" * 64, artifact_refs=[],
        content_sha256=result_digest(raw, DIGEST_V2), raw=raw, data_origin="test",
        declared_result_id="res-entry-04L21")

    status, report = server.client.get("/api/v1/integrity")
    assert _integrity_problems(report, expected_counts={"tasks": 1, "attempts": 1,
                                                         "results": 1}) == []
    status, listed = server.client.get("/api/v1/tasks")
    assert len(listed["tasks"]) == report["counts"]["tasks"] == 1

    server.unified.conn.execute("UPDATE results SET content_sha256=? WHERE result_id=?",
                                ("sha256:" + "9" * 64, stored["result_id"]))
    server.unified.conn.commit()

    status, report = server.client.get("/api/v1/integrity")
    assert _integrity_problems(
        report, expected_counts={"tasks": 1, "attempts": 1, "results": 1},
        tampered_result_id=stored["result_id"]) == []


def test_entry_work_audit_integrity_falsification():
    """植入反证（audit）：把 counts 顶成常量、把摘要不符问题的 id 换成别的
    result、再塞一条额外问题 → 谓词全部报红；与行一致的报表为绿。"""
    counts = {"tasks": 1, "attempts": 1, "results": 1}
    clean = {"counts": counts, "problems": [{"kind": "RESULT_DIGEST_MISMATCH",
                                             "id": "a" * 32,
                                             "detail": "stored content_sha256 does not "
                                                       "recompute from the raw row"}]}
    kwargs = dict(expected_counts=counts, tampered_result_id="a" * 32)
    assert _integrity_problems(clean, **kwargs) == []
    assert _integrity_problems({"counts": counts, "problems": []},
                               expected_counts=counts) == []

    tampered = json.loads(json.dumps(clean))
    tampered["counts"]["tasks"] = 5
    assert any(p.startswith("counts-not-the-rows-written") for p in
               _integrity_problems(tampered, **kwargs))

    tampered = json.loads(json.dumps(clean))
    tampered["problems"][0]["id"] = "b" * 32
    assert "digest-problem-does-not-name-my-result" in _integrity_problems(tampered, **kwargs)

    tampered = json.loads(json.dumps(clean))
    tampered["problems"].append({"kind": "RESULT_ORPHAN_TASK", "id": "c" * 32,
                                 "detail": "planted extra"})
    assert "problem-set-larger-than-the-tampering" in _integrity_problems(tampered, **kwargs)


def _attempt_readback_problems(attempt, *, attempt_id, task_id, base_fingerprint,
                               execution_state, expected_declared_result_ids=None):
    """单 Attempt 读回是否逐字段等于那一条存储行（含 results 子表）。"""
    problems = []
    if attempt.get("attempt_id") != attempt_id:
        problems.append("attempt_id-not-the-one-requested")
    if attempt.get("task_id") != task_id:
        problems.append("task_id-not-the-parent-of-this-attempt")
    if attempt.get("base_fingerprint") != base_fingerprint:
        problems.append("base_fingerprint-not-the-one-posted")
    if attempt.get("execution_state") != execution_state:
        problems.append("execution_state-not-" + execution_state)
    if not isinstance(attempt.get("revision"), int) or attempt.get("revision") < 1:
        problems.append("revision-missing-or-zero")
    if not attempt.get("created_at"):
        problems.append("created_at-absent")
    if expected_declared_result_ids is not None:
        got = [row.get("declared_result_id") for row in (attempt.get("results") or [])]
        if got != list(expected_declared_result_ids):
            problems.append("results-not-the-imported-rows:%r" % (got,))
    return problems


def test_entry_work_execution_detail_attempt_is_the_stored_row(server, work_project):
    """04#L28|work:execution-detail — GET /api/v1/attempts/<id> 逐字段读回存储行。

    同一时刻并存两个 attempt（各自带唯一 base_fingerprint），每个入口只回自己那条；
    空台账状态 results==[]；跑完整条导入链（pack→grants 审批→用户交接声明→结果
    导入，结果文档带具名 resultId）后 results 恰好等于我导入的那条，且
    content_sha256 是服务端对存储 raw 行重算的摘要、revision 随链推进而增大；
    另一个 attempt 的读回不受任何影响（对象隔离）。伪造 id 点名 ATTEMPT_NOT_FOUND。

    明确没有证明：执行器真跑过（结果文档 data_origin=test，是夹具导入）；
    「任务/执行详情」前端视图渲染（STITCH 边界）。
    """
    import re as _re
    from tests.conftest import produced_after, seed_issue, write_grants

    seed_issue(server.work.store, name=ENTRY_COLLECTOR)

    def _prepared(key, fingerprint):
        status, task = server.client.post("/api/v1/tasks", {
            "project_id": work_project["project_id"], "kind": "work",
            "title": "入口登记 04#L28：" + key,
            "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
            "acceptance": {"professional_required": False}})
        assert status == 201, task
        status, attempt = server.client.post(
            f"/api/v1/tasks/{task['task_id']}/attempts",
            {"idempotency_key": key, "base_fingerprint": fingerprint})
        assert status == 201, attempt
        return task["task_id"], attempt["attempt_id"], attempt["revision"]

    task_a, attempt_a, rev_a0 = _prepared("att-alpha", "fp-alpha-entry-04L28")
    task_b, attempt_b, _rev_b0 = _prepared("att-beta", "fp-beta-entry-04L28")

    status, got_a = server.client.get(f"/api/v1/attempts/{attempt_a}")
    assert status == 200, got_a
    assert _attempt_readback_problems(
        got_a, attempt_id=attempt_a, task_id=task_a, base_fingerprint="fp-alpha-entry-04L28",
        execution_state="PREPARED", expected_declared_result_ids=[]) == []
    status, got_b = server.client.get(f"/api/v1/attempts/{attempt_b}")
    assert got_b["base_fingerprint"] == "fp-beta-entry-04L28", \
        "两个 attempt 的读回串了对象"

    status, body = server.client.get("/api/v1/attempts/" + "0" * 32)
    assert status == 404 and body["error"] == "ATTEMPT_NOT_FOUND", (status, body)

    # 把 A 推进到 RESULT_RECEIVED：与 v03 闭环同款链，具名结果 id 由本节点指定
    declared_result_id = "res-entry-04L28"
    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt_a}/pack", {})
    assert status == 201, pack_response
    pack_id = pack_response["pack"]["packId"]
    write_grants(server)
    status, approval = server.client.post(f"/api/v1/attempts/{attempt_a}/approval",
                                          {"authorization_ref": "g-test-1",
                                           "expected_version": 1})
    assert status == 200, approval
    status, handoff = server.client.post(
        f"/api/v1/attempts/{attempt_a}/handoff-declarations",
        {"claim": "copiedByUser", "target_version": "work-store-v1",
         "channel": "manual-copy", "actor": "user"})
    assert status == 200, handoff
    status, imported = server.client.post(f"/api/v1/attempts/{attempt_a}/results", {
        "result": _result_document(pack_id, work_project["project_id"],
                                  result_id=declared_result_id,
                                  produced_at=produced_after(handoff)),
        "data_origin": "test"})
    assert status == 201, imported

    status, got_a = server.client.get(f"/api/v1/attempts/{attempt_a}")
    assert _attempt_readback_problems(
        got_a, attempt_id=attempt_a, task_id=task_a, base_fingerprint="fp-alpha-entry-04L28",
        execution_state="RESULT_RECEIVED",
        expected_declared_result_ids=[declared_result_id]) == []
    assert got_a["revision"] > rev_a0, (rev_a0, got_a["revision"])
    assert got_a["results"][0]["content_sha256"] == imported["result"]["content_sha256"]
    assert _re.fullmatch(r"[0-9a-f]{32}", got_a["results"][0]["result_id"])

    status, got_b = server.client.get(f"/api/v1/attempts/{attempt_b}")
    assert got_b["results"] == [] and got_b["execution_state"] == "PREPARED", \
        "A 链上的写入渗进了 B 的读回"


def test_entry_work_execution_detail_readback_falsification():
    """植入反证（execution-detail）：把读回的 attempt_id 换成另一个对象、
    base_fingerprint 顶成常量、results 顶成常量非空 → 谓词全部报红。"""
    base = {"attempt_id": "a" * 32, "task_id": "b" * 32,
            "base_fingerprint": "fp-alpha", "execution_state": "PREPARED",
            "revision": 1, "created_at": "2026-11-01T00:00:00Z", "results": []}
    kwargs = dict(attempt_id="a" * 32, task_id="b" * 32, base_fingerprint="fp-alpha",
                  execution_state="PREPARED", expected_declared_result_ids=[])
    assert _attempt_readback_problems(base, **kwargs) == []

    tampered = json.loads(json.dumps(base))
    tampered["attempt_id"] = "c" * 32
    assert "attempt_id-not-the-one-requested" in _attempt_readback_problems(tampered, **kwargs)

    tampered = json.loads(json.dumps(base))
    tampered["base_fingerprint"] = "constant-laundered"
    assert "base_fingerprint-not-the-one-posted" in _attempt_readback_problems(tampered, **kwargs)

    tampered = json.loads(json.dumps(base))
    tampered["results"] = [{"declared_result_id": "res-phantom"}]
    assert any(p.startswith("results-not-the-imported-rows") for p in
               _attempt_readback_problems(tampered, **kwargs))


def _plan_list_problems(payload, *, plan_id, objective, created_by="owner", revision=1):
    """方案列表读回的那一条是否就是我创建的那一个方案。"""
    problems = []
    if payload.get("total") != 1:
        problems.append("total-not-1:%r" % (payload.get("total"),))
    rows = payload.get("plans") or []
    if len(rows) != 1:
        problems.append("plans-row-count-%d-not-1" % len(rows))
        return problems
    row = rows[0]
    if row.get("plan_id") != plan_id:
        problems.append("plan_id-not-the-created-plan")
    if row.get("objective") != objective:
        problems.append("objective-not-the-created-objective")
    if row.get("revision") != revision:
        problems.append("revision-not-as-created")
    if row.get("created_by") != created_by:
        problems.append("created_by-not-as-posted")
    if not row.get("created_at"):
        problems.append("created_at-not-store-timestamped")
    return problems


def test_entry_design_records_plan_list_reads_back_created_plan(server):
    """04#L47|design:records — 「制作记录」聚合读面（方案列表路由）读回我建的方案。

    空台账：GET /api/projects/<id>/assistance-plans total==0、plans==[]；
    经同一 HTTP 面 POST 创建一个 objective 带本节点具名标记的方案；再读：
    total 从 0 变 1，唯一的行就是我那个 plan_id/objective/revision==1，
    created_at 是存储时间戳（不来自请求体）；统一聚合面
    GET /api/v1/design/plans?project_id= 读到同一个 plan_id。

    明确没有证明：「设计/我的方案与任务记录」前端视图渲染（STITCH 边界，
    登记的验收原文要求的是视图生成，本节点不证明渲染）；编号列（job_id/
    operation_id）的 owner 填写语义。
    """
    objective = "入口登记 04#L47：制作记录读回样例"
    status, project = server.client.post("/api/v1/projects", {
        "name": "记录入口样例", "source": "design", "data_origin": "test"})
    assert status == 201, project
    design_project_id = project["root_path"]

    status, listed = server.client.get(
        "/api/projects/%s/assistance-plans" % design_project_id)
    assert status == 200, listed
    assert listed["total"] == 0 and listed["plans"] == [], \
        "空台账状态下方案列表不应有行"

    status, created = server.client.post(
        "/api/projects/%s/assistance-plans" % design_project_id, {
            "objective": objective, "output_type": "STORYBOARD",
            "neutral_creative": "测试中性创意", "brand_constraints": [],
            "role_constraints": [], "lens": None, "sound": None,
            "references": [], "external_steps": [], "known_gaps": [],
            "limits": [], "created_by": "owner"})
    assert status == 201, created
    plan_id = created["plan"]["plan_id"]

    status, listed = server.client.get(
        "/api/projects/%s/assistance-plans" % design_project_id)
    assert _plan_list_problems(listed, plan_id=plan_id, objective=objective) == []

    status, unified = server.client.get(
        "/api/v1/design/plans?project_id=" + design_project_id)
    assert status == 200, unified
    assert [row["plan_id"] for row in unified["plans"]] == [plan_id], \
        "统一聚合面与内核面读到的不是同一个方案"


def test_entry_design_records_plan_list_falsification():
    """植入反证（records）：objective 换成别的文案、plan_id 换成另一对象、
    total 顶成常量 → 谓词报红；正确读回为绿。"""
    payload = {"total": 1, "plans": [{"plan_id": "aplan-" + "a" * 32, "revision": 1,
                                      "objective": "入口登记 04#L47",
                                      "created_at": "2026-11-01T00:00:00Z",
                                      "created_by": "owner"}]}
    kwargs = dict(plan_id="aplan-" + "a" * 32, objective="入口登记 04#L47")
    assert _plan_list_problems(payload, **kwargs) == []

    tampered = json.loads(json.dumps(payload))
    tampered["plans"][0]["objective"] = "常量顶包"
    assert "objective-not-the-created-objective" in _plan_list_problems(tampered, **kwargs)

    tampered = json.loads(json.dumps(payload))
    tampered["plans"][0]["plan_id"] = "aplan-" + "b" * 32
    assert "plan_id-not-the-created-plan" in _plan_list_problems(tampered, **kwargs)

    tampered = json.loads(json.dumps(payload))
    tampered["total"] = 42
    assert any(p.startswith("total-not-1") for p in _plan_list_problems(tampered, **kwargs))


def _bundles_problems(payload, *, asset_id, version_id, sha256, byte_size):
    """交付列表读回的那一条 bundle 是否等于我在资产台账登记的那一行。"""
    rows = payload.get("bundles")
    if not isinstance(rows, list) or len(rows) != 1:
        return ["bundle-row-count-not-1:count-%d" % (len(rows) if isinstance(rows, list) else -1)]
    row = rows[0]
    problems = []
    if row.get("id") != asset_id:
        problems.append("bundle-id-not-the-registered-asset")
    if row.get("kind") != "design-bundle":
        problems.append("bundle-kind-not-projected-as-design-bundle")
    if row.get("version_id") != version_id:
        problems.append("version_id-not-the-stored-version")
    if row.get("version_no") != 1:
        problems.append("version_no-not-1")
    if row.get("sha256") != sha256:
        problems.append("sha256-not-the-artifact-digest")
    if row.get("byte_size") != byte_size:
        problems.append("byte_size-not-the-artifact-size")
    if row.get("rights") != "NOT_REVIEWED" or row.get("verification") != "METADATA_ONLY":
        problems.append("bundle-row-overclaims-rights-or-verification")
    return problems


def test_entry_design_deliverables_bundle_list_reads_back_registered_bundle(server):
    """04#L48|design:deliverables — GET /api/projects/<id>/bundles 读回资产台账行。

    空台账：bundles==[]。经产品自己的 asset_store 原语（register_asset +
    record_version，与宿主交付路径同一套写面，本机不启动任何宿主）登记一条
    asset_kind='other'、id 以 'bundle-' 开头的 ACTIVE 版本 + deliverable artifact；
    再读：唯一行的 id/version_id/sha256/byte_size 全等于我写进台账的值；
    另登记一个同为 'other' 但 id 不带 bundle- 前缀的资产，列表仍只有 1 行
    ——读面确实在按台账谓词过滤，不是把 assets 表整个倒出来。

    明确没有证明：真实宿主导出闭环（POST .../tasks/.../bundle 需要真机执行回执，
    属 Human Gate/冻结范围）；receipt 内容面（本节点只读列表）；
    「任务/交付/设计筛选」前端视图渲染（STITCH 边界）。
    """
    import hashlib
    import sqlite3
    from design_lab.runtime import asset_store

    status, project = server.client.post("/api/v1/projects", {
        "name": "交付入口样例", "source": "design", "data_origin": "test"})
    assert status == 201, project
    design_project_id = project["root_path"]

    status, listed = server.client.get("/api/projects/%s/bundles" % design_project_id)
    assert status == 200 and listed == {"bundles": []}, listed

    asset_id = "bundle-" + hashlib.sha256(b"entry-04L48").hexdigest()
    artifact_sha = hashlib.sha256(b"bundle-payload-bytes").hexdigest()
    content_sha = "sha256:" + hashlib.sha256(b"bundle-manifest").hexdigest()
    conn = sqlite3.connect(str(server.design_service.database))
    try:
        asset_store.register_asset(conn, design_project_id, asset_id, "other")
        version_id = asset_store.record_version(
            conn, asset_id, content_sha, state="ACTIVE",
            artifacts=[("delivery.zip", artifact_sha, 2048, "deliverable")])
        # 反谓词对照：同 kind、不带 bundle- 前缀的另一资产
        other_id = "doc-" + hashlib.sha256(b"entry-04L48-other").hexdigest()
        asset_store.register_asset(conn, design_project_id, other_id, "other")
        asset_store.record_version(
            conn, other_id, "sha256:" + hashlib.sha256(b"doc").hexdigest(), state="ACTIVE",
            artifacts=[("note.txt", hashlib.sha256(b"note").hexdigest(), 8, "deliverable")])
        conn.commit()
    finally:
        conn.close()

    status, listed = server.client.get("/api/projects/%s/bundles" % design_project_id)
    assert _bundles_problems(listed, asset_id=asset_id, version_id=version_id,
                             sha256="sha256:" + artifact_sha, byte_size=2048) == []


def test_entry_design_deliverables_bundle_list_falsification():
    """植入反证（deliverables）：sha256 换成别的摘要、行丢掉、条数顶成常量 2、
    rights 顶成 CLEARED → 谓词全部报红。"""
    row = {"id": "bundle-" + "a" * 64, "kind": "design-bundle",
           "version_id": "v-" + "b" * 32, "version_no": 1, "byte_size": 2048,
           "sha256": "sha256:" + "c" * 64, "rights": "NOT_REVIEWED",
           "verification": "METADATA_ONLY"}
    kwargs = dict(asset_id="bundle-" + "a" * 64, version_id="v-" + "b" * 32,
                  sha256="sha256:" + "c" * 64, byte_size=2048)
    assert _bundles_problems({"bundles": [row]}, **kwargs) == []

    tampered = json.loads(json.dumps({"bundles": [row]}))
    tampered["bundles"][0]["sha256"] = "sha256:" + "d" * 64
    assert "sha256-not-the-artifact-digest" in _bundles_problems(tampered, **kwargs)

    assert _bundles_problems({"bundles": []}, **kwargs) == ["bundle-row-count-not-1:count-0"]
    # 条数顶成常量 2（模拟把整表倒出来的读面）必须被行数检查抓住
    assert _bundles_problems({"bundles": [row, row]}, **kwargs) == ["bundle-row-count-not-1:count-2"]

    tampered = json.loads(json.dumps({"bundles": [row]}))
    tampered["bundles"][0]["rights"] = "CLEARED"
    assert "bundle-row-overclaims-rights-or-verification" in _bundles_problems(tampered, **kwargs)


def _evidence_refusal_problems(payload, *, status, ledger_rel, ledger_present,
                               resolved_root, expected_root):
    """证据投影面在「本机检出没有账本」时的具名拒绝是否与磁盘事实一致。

    拒绝必须点名真正缺失的那条相对路径、不许携带 receipts 列表（0 条回执的
    「全部干净」正是合同禁止的形状），且解析出的检出根就是本仓根 —— 这些
    把「拒绝」变成由真实文件系统状态派生的读回，而不是常量。
    """
    problems = []
    if str(resolved_root) != str(expected_root):
        problems.append("checkout-root-resolved-elsewhere")
    if ledger_present:
        problems.append("fs-fact-ledger-present-but-route-refused")
        return problems
    if status != 409:
        problems.append("status-not-409:%r" % (status,))
    if payload.get("error") != "EVIDENCE_LEDGER_ABSENT":
        problems.append("error-not-the-named-refusal")
    details = payload.get("detail") or []
    if not any(ledger_rel in str(item) for item in details):
        problems.append("detail-does-not-name-the-absent-ledger")
    if not payload.get("meaning"):
        problems.append("meaning-missing")
    if "receipts" in payload:
        problems.append("refusal-answered-a-receipts-list")
    return problems


def test_entry_design_evidence_projection_refusal_names_the_absent_ledger(server):
    """04#L49|design:evidence — GET /api/evidence-projection 的拒绝由本机文件系统事实派生。

    现读事实：evidence_readback.REPO_ROOT 按标记走到本仓根；design-lab/ 目录在，
    但 reporting.LEDGER（design-lab/config/task-ledger-r3.json）不在本检出。路由
    据此回 409 EVIDENCE_LEDGER_ABSENT，detail 点名的正是那条缺失路径；断言把
    响应与独立复核过的文件系统事实绑在一起（换一台带了账本的机器，本节点的
    谓词会因 fs-fact 分支变红而不是跟着说谎），并拒绝 receipts 形状。

    明确没有证明：receipts 读回半面——融合检出有意不带 DESIGN-LAB 账本，那是
    owner 的产品/打包决定，不是补一个端点能解决的（本节点不为其伪造端点）；
    「任务/证据抽屉/设计」前端视图渲染（STITCH 边界，本节点不证明渲染）。
    """
    from pathlib import Path as _Path

    from design_lab.governance import evidence_readback, reporting

    repo_root = _Path(__file__).resolve().parents[2]
    resolved_root = evidence_readback.REPO_ROOT
    assert resolved_root is not None
    ledger_path = Path(resolved_root) / reporting.LEDGER
    ledger_present = ledger_path.is_file()
    assert ledger_present is False, \
        "本机出现了账本，登记事实已变，需按现读重写本节点：" + str(ledger_path)

    status, body = server.client.get("/api/evidence-projection")
    assert status == 409, (status, body)
    assert _evidence_refusal_problems(
        body, status=status, ledger_rel=reporting.LEDGER, ledger_present=ledger_present,
        resolved_root=resolved_root, expected_root=repo_root) == []


def test_entry_design_evidence_refusal_falsification():
    """植入反证（evidence）：detail 点名另一条路径、状态顶成 200+空 receipts、
    fs 事实说账本在场 → 谓词全部报红；与磁盘一致的拒绝为绿。"""
    kwargs = dict(status=409, ledger_rel="design-lab/config/task-ledger-r3.json",
                  ledger_present=False, resolved_root="X", expected_root="X")
    clean = {"error": "EVIDENCE_LEDGER_ABSENT",
             "detail": ["design-lab/config/task-ledger-r3.json is not in this checkout"],
             "meaning": "本检出没有证据账本"}
    assert _evidence_refusal_problems(clean, **kwargs) == []

    tampered = json.loads(json.dumps(clean))
    tampered["detail"] = ["some-other-file is not in this checkout"]
    assert "detail-does-not-name-the-absent-ledger" in _evidence_refusal_problems(tampered, **kwargs)

    laundering = {"error": "EVIDENCE_LEDGER_ABSENT", "receipts": [], "detail": list(clean["detail"])}
    assert "refusal-answered-a-receipts-list" in _evidence_refusal_problems(
        laundering, **kwargs)

    fake_green = {"schemaVersion": "design-lab/evidence-projection/v1", "receipts": [],
                  "totals": {"records": 0}}
    assert "error-not-the-named-refusal" in _evidence_refusal_problems(
        fake_green, status=200, ledger_rel=kwargs["ledger_rel"], ledger_present=False,
        resolved_root="X", expected_root="X")

    assert _evidence_refusal_problems(clean, status=409, ledger_rel=kwargs["ledger_rel"],
                                      ledger_present=True, resolved_root="X",
                                      expected_root="X") == [
        "fs-fact-ledger-present-but-route-refused"]

    assert "checkout-root-resolved-elsewhere" in _evidence_refusal_problems(
        clean, status=409, ledger_rel=kwargs["ledger_rel"], ledger_present=False,
        resolved_root="Y", expected_root="X")
