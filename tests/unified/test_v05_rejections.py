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


# 云端审计 N03：`professional_required` 是"这条任务必须有具名真人判定才收得了口"的唯一开关。
# 旧实现只读 `acceptance` 里那一个，再把读到的东西塞进 `bool()`。本机在同一份代码上按真实 HTTP
# 逐条复现（.project-local/runs/n03-before.json）：顶层 true → 201 而库里存的是 0；顶层 true 配
# 嵌套 false → 201 存 0（谁赢由解析顺序决定，不报错）；嵌套字符串 "false" → 201 存 **1**，因为
# `bool("false")` 为真——替没要门的人立了一道门。下面两组节点要求：两种拼写都算数、声明值必须
# 是 JSON 布尔、两种拼写不一致要具名拒绝、只有两者都没出现才落到库自己声明的"不要求"。
# 拒绝组逐条断言答复里没有 task_id **并且任务表一行没多**：这个缺陷的形态正是"被接受的 201"，
# 任何 4xx 都不许在库里留下任务。
def _design_project(server, name):
    status, project = server.client.post("/api/v1/projects", {"name": name, "source": "design"})
    assert status == 201, project
    return project["project_id"]


def _prof_request(title, project_id, extra_top, nested):
    """One task-creation body with the requirement spelled however the case says.

    ``nested is None`` means the nested key is absent, not that it carries ``None`` -- the two
    differ for the conflict legs, and a null is tested on purpose in the type node.
    """
    body = {"project_id": project_id, "kind": "design", "title": title,
            "acceptance": {"data_origin": "test"}}
    if nested is not None:
        body["acceptance"]["professional_required"] = nested
    body.update(extra_top)
    return body


def _prof_tasks(server):
    status, listed = server.client.get("/api/v1/tasks")
    assert status == 200, listed
    return listed["tasks"]


def test_professional_requirement_is_read_from_either_spelling_and_named_by_the_gate(server):
    project_id = _design_project(server, "专业门-N03")

    def create(title, extra_top, nested):
        status, task = server.client.post("/api/v1/tasks",
                                         _prof_request(title, project_id, extra_top, nested))
        assert status == 201, (title, status, task)
        return task

    cases = (("(top,true)", {"professional_required": True}, None, 1),
             ("(nested,true)", {}, True, 1),
             ("(both,true)", {"professional_required": True}, True, 1),
             ("(top,false)", {"professional_required": False}, None, 0),
             ("(nested,false)", {}, False, 0),
             ("(undeclared)", {}, None, 0))
    for title, extra_top, nested, expected in cases:
        task = create(title, extra_top, nested)
        assert task["professional_required"] == expected, (title, task)
        status, stored = server.client.get("/api/v1/tasks/" + task["task_id"])
        assert status == 200 and stored["professional_required"] == expected, (title, stored)

    # the flag is not decoration: the completion projection has to name the missing human verdict
    # for the three declared-true shapes and stay out of the way for the three not-required ones
    problems = {}
    for title, _extra, _nested, expected in cases:
        task = next(row for row in _prof_tasks(server) if row["title"] == title)
        status, completion = server.client.get("/api/v1/tasks/%s/completion" % task["task_id"])
        assert status == 200, (title, status, completion)
        problems[title] = [problem.split(" ")[0] for problem in completion["problems"]]
    for title, _extra, _nested, expected in cases:
        named = "PROFESSIONAL_ACCEPTANCE_MISSING" in problems[title]
        assert named == (expected == 1), (title, problems[title])


def test_non_boolean_professional_requirement_is_refused_by_name(server):
    """A declared value has to be a JSON boolean; `bool()` of anything else is not a reading.

    The audited line ran whatever it found through ``bool()``, so the string ``"false"`` stored
    ``1`` -- a professional gate put on a task whose caller asked for none, in the opposite
    direction from the dropped top-level ``true`` the sibling node covers.
    """
    project_id = _design_project(server, "专业门-类型-N03")
    for title, extra_top, nested in (
            ("嵌套写成字符串 false", {}, "false"),
            ("嵌套写成字符串 true", {}, "true"),
            ("嵌套写成整数 1", {}, 1),
            ("嵌套写成整数 0", {}, 0),
            ("顶层写成 null", {"professional_required": None}, None),
            ("顶层写成列表", {"professional_required": [True]}, None),
            ("顶层写成字符串 false", {"professional_required": "false"}, None)):
        status, body = server.client.post(
            "/api/v1/tasks", _prof_request(title, project_id, extra_top, nested))
        assert status == 400, (title, status, body)
        assert body == {"error": "PROFESSIONAL_REQUIRED_NOT_BOOLEAN"}, (title, body)
        assert "task_id" not in body, (title, body)
    assert _prof_tasks(server) == [], (
        "a refused create still wrote a task row: %s" % _prof_tasks(server))


def test_conflicting_professional_requirement_spellings_are_refused_by_name(server):
    """Two spellings that disagree is an ambiguous request, not a precedence rule.

    The old code never saw the top-level value at all, so ``true`` beside ``false`` answered 201
    with whichever spelling happened to be read; a caller that sent both got a silent decision.
    """
    project_id = _design_project(server, "专业门-冲突-N03")
    for title, extra_top, nested in (
            ("顶层 true 与嵌套 false", {"professional_required": True}, False),
            ("顶层 false 与嵌套 true", {"professional_required": False}, True)):
        status, body = server.client.post(
            "/api/v1/tasks", _prof_request(title, project_id, extra_top, nested))
        assert status == 400, (title, status, body)
        assert body == {"error": "PROFESSIONAL_REQUIRED_CONFLICT"}, (title, body)
        assert "task_id" not in body, (title, body)
    assert _prof_tasks(server) == [], (
        "a refused create still wrote a task row: %s" % _prof_tasks(server))


# 云端审计 N04：`POST /api/v1/projects` 的 `source` 只写了「是不是 work」，不是「是不是这两种之一」。
# 本机真实 HTTP 复现（.project-local/runs/n04-before.json）里，`not-a-supported-source`、`WORK`、
# `Design` 三支都得到 201，且统一库与设计域各多出一行——错误输入静默换了一个域。修法是先在两个
# 库都不碰之前按名字拒绝；大小写不折叠（`WORK` 拒），`_require` 已有的首尾空白裁剪保持
# （`"  work  "` 仍走 work 支，缺根时回 `WORK_PROJECT_ROOT_REQUIRED`，这条也在下面钉住）。
def test_project_source_is_enumerated_and_a_refusal_writes_in_neither_store(server, tmp_path):
    def listing():
        status, body = server.client.get("/api/v1/projects")
        assert status == 200, body
        return (len(body["unified"]), len(body["design_runtime"]),
                sorted(row["display_name"] for row in body["unified"]),
                sorted({row["source"] for row in body["unified"]}))

    work_root = tmp_path / "合法-work-根"
    work_root.mkdir()
    baseline = listing()

    # the control: a blanket refusal would make every leg below green, so the two legal values are
    # read back first, in this same node, on this same server
    status, work_project = server.client.post(
        "/api/v1/projects", {"name": "合法-work", "source": "work", "root_path": str(work_root)})
    assert status == 201 and work_project["source"] == "work", work_project
    status, design_project = server.client.post(
        "/api/v1/projects", {"name": "合法-design", "source": "design"})
    assert status == 201 and design_project["source"] == "design", design_project

    after_legal = listing()
    assert after_legal[0] == baseline[0] + 2 and after_legal[1] == baseline[1] + 1, after_legal

    refusals = (
        ({"name": "未知词", "source": "not-a-supported-source"}, "PROJECT_SOURCE_UNKNOWN"),
        ({"name": "全大写", "source": "WORK"}, "PROJECT_SOURCE_UNKNOWN"),
        ({"name": "混合大小写", "source": "Design"}, "PROJECT_SOURCE_UNKNOWN"),
        ({"name": "两个值拼一起", "source": "work,design"}, "PROJECT_SOURCE_UNKNOWN"),
        ({"name": "近似拼写", "source": "wrok"}, "PROJECT_SOURCE_UNKNOWN"),
        # a wrong source beside a missing work root is a source problem first: the old code never
        # reached the root check for a value it silently treated as design
        ({"name": "双错", "source": "bogus"}, "PROJECT_SOURCE_UNKNOWN"),
        ({"name": "空串", "source": ""}, "PROJECT_SOURCE_REQUIRED"),
        ({"name": "只有空白", "source": "   "}, "PROJECT_SOURCE_REQUIRED"),
        ({"name": "空值", "source": None}, "PROJECT_SOURCE_REQUIRED"),
        ({"name": "整数", "source": 123}, "PROJECT_SOURCE_REQUIRED"),
        ({"name": "缺字段"}, "INVALID_PROJECT_FIELDS"),
    )
    for body, code in refusals:
        status, answer = server.client.post("/api/v1/projects", body)
        assert status == 400, (body, status, answer)
        assert answer == {"error": code}, (body, answer)
        assert "project_id" not in answer, (body, answer)

    # "拒绝后两库无新增记录" is a measurement here, not an inference from the 400
    now = listing()
    assert now[:2] == after_legal[:2], (
        "a refused source still created rows: %s -> %s" % (after_legal[:2], now[:2]))
    assert now[2] == after_legal[2], (
        "the unified table or the design domain gained a project nobody asked for: %s"
        % sorted(set(now[2]) - set(after_legal[2])))
    assert now[3] == ["design", "work"], (
        "the unified table holds a source outside the enumerated two: %s" % now[3])

    # padding is trimmed and case is not folded: this leg must reach the *work* branch, which is
    # where it has to land to prove the enum check did not reroute it to design
    status, answer = server.client.post(
        "/api/v1/projects", {"name": "带空白的 work", "source": "  work  "})
    assert status == 400 and answer == {"error": "WORK_PROJECT_ROOT_REQUIRED"}, answer


# ===========================================================================
# 追加段：capability-family 行 `05#L27|contracts`（公共协议与 Schema）
# 核心验收原文：「现有消费者与版本兼容，错误输入和资源路径回归」。
#
# 本段只测 `packages/contracts` 的**真实读取点**。读取点是现读的，不是登记抄来的：
#   - domains/work/control/control_service.py:76,328-330  读 control-operation.schema.json，
#     :501-507 用 jsonschema 拒绝并给出具名 reason_code "INVALID_REQUEST"；
#     该 Schema 由 GET /api/work/control/descriptor 这条活路由触发读取
#     （backend/core/work_surfaces.py:274-285 → :256-271 → ControlPlane.__init__）。
#   - domains/work/orchestration/adapter_capability_projection.py:154-179 读
#     client-adapter.schema.json 并与 config/capability-matrix.json 交叉核对，
#     不一致时 raise ValueError("adapter interface verb drift: …")；消费端是
#     domains/work/control/snapshot_validator.py:90-125（再由 :106 的卡片规则使用）。
#   - domains/work/control/solution_library.py:165-169 读 solution.schema.json，
#     :180-195 把它交给 Draft202012Validator，:219-221/:296-298 以 "SOLUTION_INVALID" 抛出。
#   - domains/work/workflow_core/repair_pack_projection.py:383-385 是 action-plan 合同的
#     产品侧校验分支（schema 由调用方注入；仓内唯一注入方是
#     tests/legacy/work/test_repair_pack_projection.py，产品调用方一律传 None ——
#     这一点在本段被断言为事实，而不是被登记措辞掩盖）。
#   - domains/work/workflow_core/canonical_store.py:1093-1176 是 action_plan 行的唯一真值
#     读写方，具名冲突码 ACTION_PLAN_VERSION_CONFLICT（:1149-1158）。
#   - domains/work/control/snapshot_validator.py:24,136-137 对 workflow/snapshot/v3
#     是「比较字面量、不重新推导」，旧版本号被显式拒绝（不是被宽容接受）。
#
# 不在本段证明的：真实跨版本历史快照回放、真实宿主/真人的 E3/E4、以及任何"文件存在即通过"。
# 追加为纯追加：上方既有节点与既有行未改动，新节点全部只读跟踪文件，临时副本只进
# tmp_path（由 --basetemp 落到 .project-local/runs/ 下，Git 忽略）。
# ===========================================================================

import copy as _copy
import hashlib as _hashlib
import re as _re
import shutil as _shutil
from pathlib import Path as _Path

import pytest

_CONTRACT_ROOT = _Path(__file__).resolve().parents[2]
_CONTRACTS_DIR = _CONTRACT_ROOT / "packages" / "contracts"
_WORKFLOW_SCHEMAS = "packages/contracts/schemas/workflow"


def _contract(relative: str) -> _Path:
    """One published contract file, addressed relative to the repository root."""
    return _CONTRACT_ROOT / relative


def _contract_json(relative: str):
    return json.loads(_contract(relative).read_text(encoding="utf-8"))


def _control_request(**overrides):
    """A control-operation request that satisfies the published contract as written.

    Every key here is required by `control-operation.schema.json:8`; `operation` is the
    closed enum at :11-28; `work-unit.revise` is the one enumerated operation whose
    spec is declared NOT implemented (control_service.py:196-200), so a document that
    clears the contract stops at a *downstream* named code and can never be mistaken
    for a contract pass.
    """
    document = {
        "schema_version": "worklab/control-operation/v1",
        "operation": "work-unit.revise",
        "project_id": "contracts-probe",
        "task_id": None,
        "revision": 1,
        "attempt": 1,
        "scope": {"boundaries": ["docs/"], "granted_by": "owner-probe"},
        "expected_version": None,
        "idempotency_key": "contracts-probe-key",
        "actor": "contracts-probe",
        "requested_at": "2026-11-01T09:00:00Z",
        "payload": {"title": "合同探针"},
    }
    for key, value in overrides.items():
        if value is _DELETE:
            document.pop(key, None)
        else:
            document[key] = value
    return document


_DELETE = object()


def _fake_project_root(value: str):
    """The root probe `build_repair_pack` asks for: does the verification entry exist here.

    Mirrors the object the product code actually uses (join + exists/is_file), so the
    projection keeps its real shape instead of being re-implemented here.
    """
    class _Entry:
        def is_file(self_inner):
            return True

        def as_posix(self_inner):
            return value.replace("\\", "/") + "/gate"

    class _Root:
        def exists(self_inner):
            return True

        def is_file(self_inner):
            return True

        def as_posix(self_inner):
            return value.replace("\\", "/")

        def __truediv__(self_inner, other):
            return _Entry()

    def probe(_value):
        return _Root()

    return probe


def _issue_row(fingerprint: str) -> dict:
    return {
        "schemaVersion": "workflow/issue/v1", "fingerprint": fingerprint,
        "class": "SOURCE_STALE", "projectId": "contracts-proj", "subject": "s",
        "origin": "telemetry_events", "evidenceRef": f"telemetry_events:{fingerprint}",
        "priority": "P2", "priorityRule": "rule", "safeToReread": True,
        "firstSeenAt": "2026-10-22T00:00:00Z", "lastSeenAt": "2026-10-22T00:00:00Z",
        "occurrences": 1, "magnitude": {}, "detail": "d", "status": "OPEN",
        "softwareId": None, "softwareVersion": None,
        "softwareVersionSource": "unattributable",
    }


def _json_pointer(node, pointer: str):
    """Resolve a same-document JSON Pointer. Returns a sentinel on a broken hop.

    `MISSING` (not None) is used because a `$defs` member legitimately holding null
    would otherwise read as a broken reference.
    """
    _MISSING = ("__absent__",)
    if pointer in ("#", "#/"):
        return node
    if not pointer.startswith("#/"):
        return _MISSING
    current = node
    for part in pointer[2:].split("/"):
        part = part.replace("~1", "/").replace("~0", "~")
        if isinstance(current, dict):
            if part not in current:
                return _MISSING
            current = current[part]
        elif isinstance(current, list) and part.isdigit() and int(part) < len(current):
            current = current[int(part)]
        else:
            return _MISSING
    return current


def _collect_refs(node, breadcrumb=""):
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "$ref" and isinstance(value, str):
                found.append((breadcrumb or "<root>", value))
            else:
                found.extend(_collect_refs(value, f"{breadcrumb}/{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(_collect_refs(value, f"{breadcrumb}/{index}"))
    return found


def _unresolved_refs(root: _Path) -> list[str]:
    """Every `$ref` in every published schema, resolved back to a real in-repo document.

    Three ref spellings exist in this tree and each gets its own resolution rule:
    ``#/…`` (same document), an absolute URI whose base must be the ``$id`` of exactly
    one published file, and a relative path such as ``./source-record.schema.json``.
    A reference that resolves to nothing is a break, reported with file + pointer +
    reason; this is the predicate the register sentence "资源路径回归" needs, and node
    `test_contracts_planted_broken_ref_makes_the_resource_predicate_red` proves it can
    go red.
    """
    files = sorted(root.rglob("*.json"))
    documents: dict[_Path, object] = {}
    breaks: list[str] = []
    for path in files:
        try:
            documents[path] = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            breaks.append(f"{path.relative_to(root).as_posix()}::<file>:: UNPARSEABLE: {exc}")
    by_id: dict[str, list[_Path]] = {}
    for path, document in documents.items():
        if isinstance(document, dict) and isinstance(document.get("$id"), str):
            by_id.setdefault(document["$id"], []).append(path)

    def resolve_in(target_document, fragment):
        # A same-document pointer arrives as "#/…"; a fragment cut out of an absolute URI
        # arrives as "/…", and the two spellings mean the same location.
        if fragment and not fragment.startswith("#"):
            fragment = "#" + fragment
        return _json_pointer(target_document, fragment or "#")

    _MISSING = ("__absent__",)
    for path in files:
        document = documents.get(path)
        if not isinstance(document, dict):
            continue
        relative = path.relative_to(root).as_posix()
        for breadcrumb, reference in _collect_refs(document, relative):
            if reference.startswith("#"):
                if resolve_in(document, reference) is _MISSING:
                    breaks.append(f"{breadcrumb} -> {reference}: pointer resolves to nothing "
                                  "inside the same document")
                continue
            if reference.startswith(("http://", "https://")):
                base, _, fragment = reference.partition("#")
                owners = by_id.get(base)
                if not owners:
                    breaks.append(f"{breadcrumb} -> {reference}: no published schema declares "
                                  f"$id {base!r}, so the reference resolves to no file in this repo")
                    continue
                if len(owners) > 1:
                    breaks.append(f"{breadcrumb} -> {reference}: $id {base!r} is declared by "
                                  f"{len(owners)} files, the reference is ambiguous")
                    continue
                if resolve_in(documents[owners[0]], fragment) is _MISSING:
                    breaks.append(f"{breadcrumb} -> {reference}: fragment does not resolve inside "
                                  f"{owners[0].relative_to(root).as_posix()}")
                continue
            target = (path.parent / reference).resolve()
            try:
                inside = target.relative_to(root.resolve())
            except ValueError:
                inside = None
            if inside is None:
                breaks.append(f"{breadcrumb} -> {reference}: resolves outside the published root")
            elif not target.is_file():
                breaks.append(f"{breadcrumb} -> {reference}: no such file "
                              f"({inside.as_posix() if inside else target})")
    return breaks


def test_contracts_control_plane_reads_the_published_request_contract(server):
    """Consumer 1: the Control service. The Schema file is read on a live HTTP route.

    Proves: `GET /api/work/control/descriptor` (backend/core/work_surfaces.py:274-285)
    constructs the plane, whose __init__ opens
    `packages/contracts/schemas/workflow/control-operation.schema.json` (:76,:328), and
    that the operation list the service publishes is *the same closed set* the file
    declares in two directions — an operation the code knows but the contract does not
    enumerate could never be requested, and an enumerated operation with no spec would
    answer UNKNOWN_OPERATION instead of a declared reason.
    """
    from backend.core import work_surfaces
    from domains.work.control import control_service

    status, descriptor = server.client.get("/api/work/control/descriptor")
    assert status == 200, descriptor
    schema = _contract_json(f"{_WORKFLOW_SCHEMAS}/control-operation.schema.json")
    published = schema["properties"]["operation"]["enum"]
    served = [row["operation"] for row in descriptor["operations"]]
    assert sorted(served) == sorted(published), (served, published)
    assert set(control_service.OPERATIONS) == set(published)
    plane = work_surfaces.control_plane(server.api)
    assert plane._schema == schema, "the descriptor is served from the file this test just read"
    assert schema["properties"]["schema_version"]["const"] == "worklab/control-operation/v1"
    assert schema["title"] == "Control Surface Operation Request"
    assert schema["additionalProperties"] is False


def test_contracts_control_request_documents_accepted_and_refused_with_named_code(server):
    """Consumer 1, error-input half: accepted → a downstream code; refused → INVALID_REQUEST.

    The accepted document must reach `NO_REVISION_CONTRACT_WIRED`, which control_service
    only emits *after* the contract check returns no errors (:509-516), so reaching it is
    proof the schema layer passed. Each malformed document must come back with the named
    code `INVALID_REQUEST` (:504) and the jsonschema message that only the published file
    can produce — a hand-written check could not name `'rollback'-style pointer text, an
    unknown verb would otherwise read as `UNKNOWN_OPERATION` (:511).
    """
    from backend.core import work_surfaces

    plane = work_surfaces.control_plane(server.api)

    accepted = plane.execute(_control_request())
    assert accepted["status"] == "NOT_IMPLEMENTED"
    assert accepted["reason_code"] == "NO_REVISION_CONTRACT_WIRED"

    refusals = {
        "missing required field": (_control_request(idempotency_key=_DELETE),
                                   "'idempotency_key' is a required property"),
        "wrong type": (_control_request(revision="3"),
                       "'3' is not of type 'integer', 'null'"),
        "unknown extra field": (_control_request(unexpected=1),
                                "Additional properties are not allowed"),
        "older schema_version": (_control_request(schema_version="worklab/control-operation/v0"),
                                 "'worklab/control-operation/v1' was expected"),
        "verb outside the closed enum": (_control_request(operation="work-unit.teleport"),
                                         "is not one of"),
    }
    for label, (document, fragment) in refusals.items():
        result = plane.execute(document)
        assert result["reason_code"] == "INVALID_REQUEST", (label, result)
        assert result["status"] == "REFUSED", (label, result)
        assert fragment in result["reason"], (label, result["reason"])
        assert "control-operation 合同" in result["reason"], (label, result["reason"])

    # Version compatibility is a refusal here, not a silent widening: the contract binds a
    # `const`, so v0 is never accepted as "close enough". Recorded as observed, not assumed.
    assert plane.execute(_control_request(schema_version="worklab/control-operation/v0"))[
        "reason_code"] == "INVALID_REQUEST"

    # The unified HTTP mount is NOT a live consumer of this contract today, and the register
    # line treats it as one. `control_execute` calls `handler.body(fields={}, optional={})`
    # (backend/core/work_surfaces.py:319) and that helper refuses any body with keys
    # (domains/design/design_lab/http_service.py:539-541), so no request ever reaches
    # plane.execute over POST. Pinned so a future fix has to re-classify this row.
    status, body = server.client.post("/api/work/control/operations", _control_request())
    assert status == 400 and body.get("error") == "INVALID_PROJECT_FIELDS", (status, body)
    assert "reason_code" not in body, body


def test_contracts_control_result_envelope_matches_published_result_contract(server):
    """Consumer 1, output half: what the code stamps is what the contract binds.

    `ControlPlane.result()` writes the envelope at control_service.py:347-360; the
    published `control-operation-result.schema.json` declares the required key set and
    the version `const`. Both directions are asserted, then a real answer from the plane
    is validated against that file, so an added/renamed key or a bumped stamp cannot ship
    while the published contract still says otherwise.
    """
    import jsonschema

    from backend.core import work_surfaces

    schema = _contract_json(f"{_WORKFLOW_SCHEMAS}/control-operation-result.schema.json")
    plane = work_surfaces.control_plane(server.api)
    answer = plane.execute(_control_request())
    assert set(answer) == set(schema["required"]), (sorted(answer), sorted(schema["required"]))
    assert schema["properties"]["schema_version"]["const"] == answer["schema_version"]
    errors = sorted(jsonschema.Draft202012Validator(schema).iter_errors(answer),
                    key=lambda e: list(e.absolute_path))
    assert [e.message for e in errors] == [], [e.message for e in errors]


def test_contracts_action_plan_product_generated_pack_satisfies_published_schema():
    """Consumer anchor for the file the register names: `action-plan.schema.json`.

    `repair_pack_projection.py:383-385` is the product-side branch that validates a plan
    body against that contract — with the schema *injected by the caller*. No in-repo
    product caller injects it (`repair_state.py:115` and :413 call it with the default
    None), so this node drives the product branch with the published file itself:
    a pack the product projection actually generates must validate clean, and three
    mutations must be refused with the module's own named prefix
    "plan body violates workflow/action-plan/v1:".
    """
    from domains.work.workflow_core import repair_pack_projection as rpp

    schema = _contract_json(f"{_WORKFLOW_SCHEMAS}/action-plan.schema.json")
    assert rpp.PLAN_SCHEMA_VERSION == schema["properties"]["schema_version"]["const"]

    pack, reason = rpp.build_repair_pack(
        adapter=None, project_id="contracts-proj", bound_rows=[_issue_row("c" * 64)],
        projects=[{"project_id": "contracts-proj", "root_path": "D:/contracts-probe",
                   "display_name": "probe", "status": "REGISTERED"}],
        registry=None, generated_at="2026-10-22T00:00:00Z",
        root_probe=_fake_project_root("D:/contracts-probe"), manual=True)
    assert pack is not None, reason
    assert [p for p in rpp.validate_repair_pack(pack, schema=schema)] == []

    def violating(document):
        return [p for p in rpp.validate_repair_pack(document, schema=schema)
                if "violates workflow/action-plan/v1" in p]

    old_version = _copy.deepcopy(pack)
    old_version["plan"]["schema_version"] = "workflow/action-plan/v0"
    assert violating(old_version), "an older plan version must not be accepted as current"
    missing = _copy.deepcopy(pack)
    del missing["plan"]["rollback"]
    assert any("'rollback' is a required property" in p for p in violating(missing)), violating(missing)
    empty_steps = _copy.deepcopy(pack)
    empty_steps["plan"]["steps"] = []
    assert any("should be non-empty" in p for p in violating(empty_steps)), violating(empty_steps)
    # Without the injected schema the same pack passes: the refusal above therefore comes
    # from the published file, not from the module's hand-written rules.
    assert violating(_copy.deepcopy(pack)) == []


def test_contracts_action_plan_published_examples_are_the_contract_test_docs():
    """The two example documents shipped beside the contract must agree with it.

    `schemas/workflow/examples/` is a published resource path: the valid document must
    validate clean and the invalid one must be refused for the reason its name states.
    """
    import jsonschema

    schema = _contract_json(f"{_WORKFLOW_SCHEMAS}/action-plan.schema.json")
    validator = jsonschema.Draft202012Validator(schema)
    valid = _contract_json(f"{_WORKFLOW_SCHEMAS}/examples/valid-action-plan.json")
    invalid = _contract_json(f"{_WORKFLOW_SCHEMAS}/examples/invalid-action-plan.json")
    assert [e.message for e in validator.iter_errors(valid)] == []
    messages = [e.message for e in validator.iter_errors(invalid)]
    assert messages, "the shipped invalid example validates clean — the contract no longer binds it"
    assert any("is a required property" in m for m in messages), messages


def test_contracts_action_plan_store_row_version_compat_and_solution_consumer_refusal(server):
    """Version compatibility on the store that holds action plans, plus the next consumer.

    `canonical_store.save_action_plan` (:1093-1176) is the only durable writer for a plan
    row and it refuses optimistic-concurrency violations with the named code
    `ACTION_PLAN_VERSION_CONFLICT` (:1149-1158). `solution_library.solidify_solution`
    (:210-232) is a second consumer of the same row and refuses a payload that is not a
    repair record with `SOLUTION_RECORD_UNREADABLE`. Both are asserted against the real
    store the unified service already owns.
    """
    from domains.work.control import solution_library as sl

    store = server.work.store
    plan = _contract_json(f"{_WORKFLOW_SCHEMAS}/examples/valid-action-plan.json")
    record = {"planId": "plan-contracts-probe", "projectId": "contracts-proj",
              "status": "DRAFT", "payload": {"schemaVersion": "workflow/action-plan/v1",
                                             "plan": plan}}
    first = store.save_action_plan(record)
    assert first["version"] == 1 and first["payloadParseState"] == "PARSED"
    assert store.save_action_plan(record)["changed"] is False, "an identical re-delivery must not mint a version"
    row = store.read_action_plan("plan-contracts-probe")
    assert row["payload"]["plan"] == plan, "the plan body must read back byte-for-byte equivalent"

    with pytest.raises(ValueError, match="ACTION_PLAN_VERSION_CONFLICT"):
        store.save_action_plan({**record, "status": "APPROVED"})
    with pytest.raises(ValueError, match="ACTION_PLAN_VERSION_CONFLICT"):
        store.save_action_plan({**record, "status": "APPROVED"}, expected_version=99)
    bumped = store.save_action_plan({**record, "status": "APPROVED"}, expected_version=1)
    assert bumped["changed"] is True and bumped["version"] == 2

    # Second consumer: a plan row whose payload is not a repair record cannot mint a recipe.
    document = sl.build_solution(
        solution_id="sol-contracts-probe", title="合同探针方案",
        software={"softwareId": "probe", "softwareVersion": "1.0", "platform": "windows",
                  "versionSource": "MEASURED"},
        source={"kind": "REPAIR_RECORD",
                "ref": "action_plan:plan-contracts-probe#verification:v1",
                "updatedAt": "2026-11-01T09:00:00Z"},
        steps=["跑一次"], verification_steps=["重跑读回"], keywords=["合同", "探针"],
        changes="追加段的样例修订", status="VERIFIED")
    assert sl.validate_solution(document, schema=sl.load_schema()) == []
    with pytest.raises(ValueError, match="SOLUTION_RECORD_UNREADABLE"):
        sl.solidify_solution(store, "plan-contracts-probe", document, schema=sl.load_schema())


def test_contracts_solution_schema_consumer_accepts_and_refuses_with_named_code(server):
    """Consumer 2: the solution library, which loads its contract from packages/contracts.

    `solution_library.load_schema()` (:165-169) opens
    `packages/contracts/schemas/workflow/solution.schema.json` — this asserts it is that
    exact file, that the emitter's key set equals the contract's required set in both
    directions, and that a real import through the store happens only for a document the
    contract accepts. Error inputs must be refused with the named code `SOLUTION_INVALID`,
    and a document that passes the module's hand-written rules but breaks `additionalProperties:
    false` must still be refused — that refusal can only come from the published file.
    """
    import jsonschema

    from domains.work.control import solution_library as sl

    schema = _contract_json(f"{_WORKFLOW_SCHEMAS}/solution.schema.json")
    assert sl.load_schema() == schema
    assert sl.SOLUTION_SCHEMA_VERSION == schema["properties"]["schemaVersion"]["const"]

    def sample(**overrides):
        document = sl.build_solution(
            solution_id="sol-contracts-solution", title="合同样例方案",
            software={"softwareId": "probe", "softwareVersion": "1.0", "platform": "windows",
                      "versionSource": "MEASURED"},
            source={"kind": "MANUAL", "ref": "manual:contracts-probe",
                    "updatedAt": "2026-11-01T09:00:00Z"},
            steps=["跑一次"], verification_steps=["重跑读回"], keywords=["合同", "探针"],
            changes="追加段的样例")
        for key, value in overrides.items():
            if value is _DELETE:
                document.pop(key, None)
            else:
                document[key] = value
        return document

    good = sample()
    assert set(good) == set(schema["required"]), (sorted(good), sorted(schema["required"]))
    assert sl.validate_solution(good, schema=schema) == []
    imported = sl.import_unverified(server.work.store, good, schema=schema)
    assert imported["status"] == "IMPORTED"
    view = sl.store_view(server.work.store, query="合同样例")
    assert [row["solutionId"] for row in view["results"]] == ["sol-contracts-solution"], view

    stale_version = sl.validate_solution(sample(schemaVersion="workflow/solution/v0"), schema=schema)
    assert any(p.startswith("schemaVersion must be workflow/solution/v1") for p in stale_version)
    assert any("violates workflow/solution/v1" in p for p in stale_version), stale_version
    with pytest.raises(ValueError, match="SOLUTION_INVALID"):
        sl.import_unverified(server.work.store, sample(schemaVersion="workflow/solution/v0"),
                             schema=schema)

    only_the_contract_refuses = sl.validate_solution(sample(notAContractField=1), schema=schema)
    assert len(only_the_contract_refuses) == 1, only_the_contract_refuses
    assert "violates workflow/solution/v1" in only_the_contract_refuses[0]
    with pytest.raises(ValueError, match="SOLUTION_INVALID"):
        sl.import_unverified(server.work.store, sample(notAContractField=1), schema=schema)

    missing_required = sl.validate_solution(sample(evidenceRefs=_DELETE), schema=schema)
    assert any("'evidenceRefs' is a required property" in p for p in missing_required), missing_required
    wrong_type = sl.validate_solution(sample(revision="2"), schema=schema)
    assert any("violates workflow/solution/v1" in p for p in wrong_type), wrong_type
    # The same document with the contract removed is refused only by hand rules — proof the
    # schema layer above is what adds the contract-side refusals.
    hand_only = sl.validate_solution(sample(notAContractField=1), schema=None)
    assert hand_only == [], hand_only
    assert jsonschema.Draft202012Validator(schema).is_valid(good)


def test_contracts_client_adapter_verb_vocabulary_agrees_across_schema_matrix_and_snapshot_consumer(tmp_path):
    """Consumer 3: the adapter verb list, cross-checked by the snapshot validator.

    `adapter_capability_projection.contract_verb_vocabulary()` (:154-179) reads
    `client-adapter.schema.json` and `config/capability-matrix.json` and raises on
    disagreement; `snapshot_validator._verb_vocabulary()` (:90-103) is the product caller
    and `_validate_verb_evidence()` (:106-125) is the rule that consumes the list. This
    asserts all four spellings of the same closed verb set agree, that a card naming a
    verb outside the set is refused, and — with a planted copy under tmp_path — that a
    single removed verb makes the predicate go red instead of quietly re-deriving it.
    """
    from domains.work.control import snapshot_validator as sv
    from domains.work.orchestration import adapter_capability_projection as acp

    schema = _contract_json(f"{_WORKFLOW_SCHEMAS}/client-adapter.schema.json")
    matrix = _contract_json("config/capability-matrix.json")
    from_schema = tuple(schema["properties"]["interface"]["const"])
    from_declaration = tuple(schema["properties"]["entries"]["items"]
                             ["properties"]["operations"]["items"]["enum"])
    from_matrix = tuple(matrix["interface_contract"])
    discovered = acp.contract_verb_vocabulary(_CONTRACT_ROOT)
    assert (from_schema, from_declaration, from_matrix) == (discovered, discovered, discovered)
    assert sv.VERB_VOCABULARY_SOURCE == "adapter_capability_projection"
    assert sv._verb_vocabulary() == discovered, "the product read path must not be degraded to None"

    assert sv._validate_verb_evidence(0, [{"verb": "invoke", "state": "NOT_PROBED",
                                           "evidenceLevel": "NO_EVIDENCE",
                                           "reason": "探针拒绝执行该动词"}]) == []
    refused = sv._validate_verb_evidence(0, [{"verb": "teleport", "state": "NOT_PROBED",
                                              "evidenceLevel": "NO_EVIDENCE", "reason": "x"}])
    assert len(refused) == 1 and "not an adapter interface verb" in refused[0], refused

    # Planted counter-evidence: one verb dropped from the contract, everything else untouched.
    staged = tmp_path / "drift"
    (staged / "packages/contracts/schemas/workflow").mkdir(parents=True)
    (staged / "config").mkdir(parents=True)
    tampered = _copy.deepcopy(schema)
    tampered["properties"]["interface"]["const"] = list(from_schema[:-1])
    (staged / "packages/contracts/schemas/workflow/client-adapter.schema.json").write_text(
        json.dumps(tampered), encoding="utf-8")
    (staged / "config/capability-matrix.json").write_text(json.dumps(matrix), encoding="utf-8")
    with pytest.raises(ValueError, match="adapter interface verb drift"):
        acp.contract_verb_vocabulary(staged)
    emptied = _copy.deepcopy(schema)
    emptied["properties"]["interface"]["const"] = []
    (staged / "packages/contracts/schemas/workflow/client-adapter.schema.json").write_text(
        json.dumps(emptied), encoding="utf-8")
    with pytest.raises(ValueError, match="verb list is absent from the tracked schema"):
        acp.contract_verb_vocabulary(staged)


def test_contracts_snapshot_v3_version_is_compared_not_rederived(server):
    """Consumer 4: the Observer snapshot version literal, on a real served document.

    `snapshot_validator.SNAPSHOT_SCHEMA_VERSION` (:24) is compared against the served
    document at :136-137 — an older version is refused, not accepted. `GET
    /api/work/observer/snapshot` is a live producer, so the assertion runs against the
    document the service actually emits today. The `workflow/snapshot/v3` const in the
    published file must equal the constant, and the register-excerpt bound that
    `open_task_register_projection.py:52-56` claims is mirrored by that file is checked
    here (the test name that comment cites does not exist in this repository).
    """
    from domains.work.control import open_task_register_projection as otp
    from domains.work.control import snapshot_validator as sv

    schema = _contract_json(f"{_WORKFLOW_SCHEMAS}/snapshot-v3.schema.json")
    assert schema["properties"]["schemaVersion"]["const"] == sv.SNAPSHOT_SCHEMA_VERSION
    assert schema["title"] == "WORK-LAB read-only Observer snapshot (workflow/snapshot/v3)"

    status, served = server.client.get("/api/work/observer/snapshot")
    assert status == 200, served
    assert served["schemaVersion"] == sv.SNAPSHOT_SCHEMA_VERSION
    verdict = sv.validate_snapshot(served)
    assert verdict["valid"] is True, verdict["errors"][:5]

    reissued = _copy.deepcopy(served)
    reissued["schemaVersion"] = "workflow/snapshot/v2"
    errors = sv.validate_snapshot(reissued)["errors"]
    assert f"schemaVersion must be {sv.SNAPSHOT_SCHEMA_VERSION}" in errors, errors
    assert any("schemaVersion" in e for e in
               sv.validate_snapshot({"schemaVersion": "workflow/snapshot/v2", "revision": 1,
                                     "generatedAt": "2026-11-01T00:00:00Z",
                                     "projects": []})["errors"])

    work_field = schema["properties"]["taskRecords"]["items"]["properties"]["register"]["properties"]["work"]
    assert work_field["maxLength"] == otp.WORK_EXCERPT_CHARS, (
        f"projection caps the excerpt at {otp.WORK_EXCERPT_CHARS}, contract says {work_field['maxLength']}")


def test_the_excerpt_bound_and_the_schema_max_length_are_the_same_number():
    """The pin that `open_task_register_projection.py:55` and the snapshot contract each name.

    The projection truncates the Work cell at ``WORK_EXCERPT_CHARS``; the published contract
    declares ``maxLength`` on the same field and its own description promises that "a test pins
    them together". One number, asserted in one place -- plus the two things that make the pin
    non-decorative: ``excerpt`` must really cut at it and disclose the cut, and the product file
    must still cite this node by name, because a citation that rots leaves two files claiming a
    guard that no longer runs. The off-by-one calls are the planted faults.
    """
    from domains.work.control import open_task_register_projection as otp

    def bounds_disagree(max_length: int, cap: int) -> bool:
        return max_length != cap

    work_field = _contract_json(
        "%s/snapshot-v3.schema.json" % _WORKFLOW_SCHEMAS,
    )["properties"]["taskRecords"]["items"]["properties"]["register"]["properties"]["work"]
    assert not bounds_disagree(work_field["maxLength"], otp.WORK_EXCERPT_CHARS)
    assert bounds_disagree(work_field["maxLength"] + 1, otp.WORK_EXCERPT_CHARS)
    assert bounds_disagree(work_field["maxLength"] - 1, otp.WORK_EXCERPT_CHARS)

    long_cell = "\u5b57" * (otp.WORK_EXCERPT_CHARS + 7)
    prefix, count, truncated = otp.excerpt(long_cell)
    assert len(prefix) == otp.WORK_EXCERPT_CHARS
    assert count == len(long_cell)
    assert truncated is True
    assert otp.excerpt("x" * 12) == ("x" * 12, 12, False)

    cited_by = (_CONTRACT_ROOT / "domains" / "work" / "control"
                / "open_task_register_projection.py").read_text(encoding="utf-8")
    assert "test_the_excerpt_bound_and_the_schema_max_length_are_the_same_number" in cited_by
    contract_text = _contract("%s/snapshot-v3.schema.json" % _WORKFLOW_SCHEMAS).read_text(
        encoding="utf-8")
    assert "open_task_register_projection.WORK_EXCERPT_CHARS" in contract_text


def test_contracts_every_published_schema_ref_resolves_to_a_real_repo_file():
    """Resource paths: no `$ref` in the published directory resolves to nothing.

    462 references across the published tree, three spellings, all resolved by
    `_unresolved_refs`. Also binds every `$id` to be unique (an ambiguous `$id` would make
    a cross-file reference resolvable to two files) and every published file to parse.
    """
    breaks = _unresolved_refs(_CONTRACTS_DIR)
    assert breaks == [], "\n".join(breaks[:20])

    ids: dict[str, list[str]] = {}
    for path in sorted(_CONTRACTS_DIR.rglob("*.json")):
        document = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(document, dict) and isinstance(document.get("$id"), str):
            ids.setdefault(document["$id"], []).append(path.relative_to(_CONTRACT_ROOT).as_posix())
    ambiguous = {uri: owners for uri, owners in ids.items() if len(owners) > 1}
    assert ambiguous == {}, ambiguous


def test_contracts_planted_broken_ref_makes_the_resource_predicate_red(tmp_path):
    """The resolution predicate above can actually fail: three planted breaks, all caught.

    A green path means nothing until the same predicate goes red on a real break, so the
    published tree is copied (never edited) under tmp_path and three reference spellings
    are broken — a same-document pointer, a cross-file `$id`, and a relative path. The
    tracked tree is then re-checked and digest-compared to prove nothing was modified.
    """
    def digest(root: _Path) -> str:
        h = _hashlib.sha256()
        for path in sorted(root.rglob("*")):
            if path.is_file():
                h.update(path.relative_to(root).as_posix().encode("utf-8"))
                h.update(path.read_bytes())
        return h.hexdigest()

    before = digest(_CONTRACTS_DIR)
    staged = tmp_path / "contracts-copy"
    _shutil.copytree(_CONTRACTS_DIR, staged)

    manifest = staged / "schemas/workflow/evidence-manifest.schema.json"
    pointer = next(ref for _b, ref in _collect_refs(
        json.loads(manifest.read_text(encoding="utf-8"))) if ref.startswith("#/$defs/"))
    manifest.write_text(manifest.read_text(encoding="utf-8").replace(
        pointer, "#/$defs/this-def-does-not-exist", 1), encoding="utf-8")

    readback = staged / "schemas-design/assistance-plan-readback-v1.schema.json"
    remote = next(ref for _b, ref in _collect_refs(
        json.loads(readback.read_text(encoding="utf-8"))) if ref.startswith("http"))
    readback.write_text(readback.read_text(encoding="utf-8").replace(
        remote, remote.replace("/schemas/assistance-plan-v1.schema.json",
                              "/schemas/assistance-plan-v9-does-not-exist.json"), 1), encoding="utf-8")

    registry = staged / "schemas-design/source-registry.schema.json"
    relative = next(ref for _b, ref in _collect_refs(
        json.loads(registry.read_text(encoding="utf-8"))) if not ref.startswith(("http", "#")))
    registry.write_text(registry.read_text(encoding="utf-8").replace(
        relative, "./source-record-planted-missing.schema.json", 1), encoding="utf-8")

    planted = _unresolved_refs(staged)
    assert len(planted) == 3, planted
    assert any("pointer resolves to nothing" in p for p in planted), planted
    assert any("no published schema declares $id" in p for p in planted), planted
    assert any("no such file" in p for p in planted), planted

    # Restore evidence: the copy is throwaway and the tracked tree was never written to.
    assert _unresolved_refs(_CONTRACTS_DIR) == []
    assert digest(_CONTRACTS_DIR) == before
    assert (staged / "schemas/workflow/evidence-manifest.schema.json").is_file()


def _declared_rework_map():
    """The migration script's own ``DECLARED_REWORK`` table, read from the file on disk."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_sources_for_contracts", _CONTRACT_ROOT / "scripts" / "migrate_sources.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.DECLARED_REWORK


def _published_contract_state(tail: str, current: bytes, recorded_digest: str,
                              declared: dict) -> str:
    """identical | declared_rework | stale for one published contract file.

    The copy ledger records the bytes the migration run wrote. A later declared repair changes
    those bytes on purpose, and the plan (`migrate_sources.py --plan`) attests the new digest;
    so the chain is ledger-then-declaration, not the ledger alone. Anything matching neither is
    an unexplained change to a public contract and stays red.
    """
    digest_now = _hashlib.sha256(current).hexdigest()
    if digest_now == recorded_digest:
        return "identical"
    attestation = declared.get("%s/%s" % (_CONTRACTS_PREFIX, tail))
    if attestation and attestation[0] == digest_now and len(current) == attestation[1]:
        return "declared_rework"
    return "stale"


_CONTRACTS_PREFIX = _CONTRACTS_DIR.relative_to(_CONTRACT_ROOT).as_posix()

#: A Windows home directory written out with a literal account name. Placeholders (`<HOME>`,
#: `%USERPROFILE%`, `$HOME`) are how a contract may describe the same root without publishing
#: which machine it was written on.
_HOME_PATH_RE = _re.compile(r"[A-Za-z]:[\\/]{1,2}Users[\\/]{1,2}([^\"'\\/<>%$]+)")


def _home_path_findings(root: _Path) -> list[str]:
    hits = []
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        text = path.read_bytes().decode("utf-8", "replace")
        for match in _HOME_PATH_RE.finditer(text):
            hits.append("%s: %s" % (path.relative_to(root).as_posix(), match.group(0)))
    return hits


def test_published_contracts_do_not_name_a_machine_account():
    """Public contracts travel to other people's checkouts; they must not carry this machine's path.

    Scope is stated precisely, because a green here is not a repository-wide promise:
    ``packages/contracts`` -- the directory the packaging declaration ships -- holds no literal
    ``C:\\Users\\<account>`` at all. ``config/adapter-registry.json`` is deliberately NOT covered:
    its rows are probe records whose evidence *is* the real install path, and replacing those bytes
    would turn an observation into a fabrication. The planted file below shows the predicate bites,
    so the passing assertion over the real directory is a measurement rather than a blind scan.
    """
    assert _home_path_findings(_CONTRACTS_DIR) == [], _home_path_findings(_CONTRACTS_DIR)


def test_the_home_path_predicate_names_a_planted_account_path(tmp_path):
    staged = tmp_path / "contracts" / "schemas"
    staged.mkdir(parents=True)
    (staged / "clean.schema.json").write_text(
        '{"description": "falls back to %USERPROFILE%\\\\.dsh or <HOME>\\\\.dsh"}', encoding="utf-8")
    assert _home_path_findings(tmp_path / "contracts") == [], "placeholders must not be flagged"
    (staged / "planted.schema.json").write_text(
        '{"description": "falls back to C:\\\\Users\\\\someone\\\\.dsh"}', encoding="utf-8")
    found = _home_path_findings(tmp_path / "contracts")
    assert len(found) == 1 and "someone" in found[0], found


def test_contracts_published_inventory_and_consumed_set_do_not_drift(server, monkeypatch):
    """Contract drift: what is published, what is registered, and what is actually opened.

    Three set equations, all bidirectional:
      1. the JSON files on disk under `packages/contracts` == the JSON targets registered
         by `migration/copies.json` (the copy ledger that made this directory a published
         package) — a schema dropped in without a ledger record is red. The comparison is made
         on the path tail plus the digest each record carries, because the ledger spells its
         targets as absolute paths inside the checkout that ran the migration: tail-and-bytes is
         what survives a clone (measured: 225 records, one recorded root, and every registered
         file explained by one of the two states below), while resolving those absolute strings
         onto a clone raises ValueError
         and proves nothing about the files. A file may therefore be either the bytes the
         migration wrote, or the bytes a *declared* repair is attested at
         (`migrate_sources.DECLARED_REWORK`) — one of the published contracts is in that second
         state and the test names it; anything matching neither is an unexplained edit, which is
         also asserted directly against the classifier;
      2. the contract files *opened at runtime* — discovered by instrumenting
         `pathlib.Path.read_text` while the three real consumers run, not by grepping —
         == the set named here, so a consumer that starts reading a fourth contract (or
         stops reading one) is red;
      3. every contract path `config/capability-matrix.json#sources` declares as an input
         exists and parses.
    It also pins the honest gap the register wording hides: the claim 「公共 Schema 目录
    随包发布并被 store/服务读取」 holds for three files, not for the directory.
    """
    from backend.core import work_surfaces
    from domains.work.control import solution_library as sl
    from domains.work.orchestration import adapter_capability_projection as acp

    published = {path.relative_to(_CONTRACT_ROOT).as_posix()
                 for path in _CONTRACTS_DIR.rglob("*.json")}
    ledger = json.loads(_contract("migration/copies.json").read_text(encoding="utf-8"))
    declared = _declared_rework_map()
    registered: set[str] = set()
    roots: set[str] = set()
    stale: list[str] = []
    states: dict[str, str] = {}
    # The ledger spells its targets as absolute paths inside the checkout that ran the migration, so
    # resolving them onto a clone is impossible and not the point. What travels between checkouts is
    # the path tail plus the digest recorded for those bytes, and both are re-checked here: the file
    # set is compared by tail, and every published file is re-hashed against its own record -- or,
    # where a declared repair later moved the bytes, against the digest that repair is attested at.
    contracts_prefix = _CONTRACTS_DIR.relative_to(_CONTRACT_ROOT).as_posix()
    for group in ledger["copies"]:
        for record in group.get("records") or []:
            relative = record["target"].replace("\\", "/")
            if "/packages/contracts/" not in relative or not relative.endswith(".json"):
                continue
            head, _, tail = relative.partition("/packages/contracts/")
            roots.add(head)
            registered.add("%s/%s" % (contracts_prefix, tail))
            published_path = _CONTRACT_ROOT / contracts_prefix / tail
            if not published_path.is_file():
                stale.append(tail + " (registered but absent)")
                continue
            current = published_path.read_bytes()
            states[tail] = _published_contract_state(
                tail, current, record["sha256_target"], declared)
            if states[tail] == "stale":
                stale.append(tail + " (bytes match neither the migration record nor a declared repair)")
    assert len(roots) == 1, sorted(roots)
    assert stale == [], stale[:5]
    # the declared branch is not a free pass: name exactly which published contracts are NOT the
    # bytes the migration wrote, and prove that a third kind of change still reads as stale
    reworked = sorted(tail for tail, state in states.items() if state == "declared_rework")
    assert reworked == ["schemas-design/model-catalog-v1.schema.json",
                        "schemas/workflow/software-update-postflight.schema.json"], reworked
    assert all(len(_contract("packages/contracts/" + tail).read_bytes())
               == declared["packages/contracts/" + tail][1] for tail in reworked), reworked
    assert _published_contract_state(reworked[0], b"planted undeclared bytes",
                                     "0" * 64, declared) == "stale"
    assert registered <= published, sorted(registered - published)[:5]
    assert published == registered, (
        f"{len(published - registered)} published JSON contract files carry no migration "
        f"copy record: {sorted(published - registered)[:5]}")

    opened: set[str] = set()
    original = _Path.read_text

    def spying(self, *args, **kwargs):
        path = _Path(self)
        try:
            relative = path.resolve().relative_to(_CONTRACT_ROOT).as_posix()
        except ValueError:
            relative = ""
        if relative.startswith("packages/contracts/"):
            opened.add(relative)
        return original(self, *args, **kwargs)

    monkeypatch.setattr(_Path, "read_text", spying)
    sl.load_schema()
    acp.contract_verb_vocabulary(_CONTRACT_ROOT)
    work_surfaces.control_plane(server.api)
    monkeypatch.undo()

    assert opened == {
        f"{_WORKFLOW_SCHEMAS}/client-adapter.schema.json",
        f"{_WORKFLOW_SCHEMAS}/control-operation.schema.json",
        f"{_WORKFLOW_SCHEMAS}/solution.schema.json",
    }, sorted(opened)
    assert opened <= published

    matrix = _contract_json("config/capability-matrix.json")
    declared = [item for item in matrix["sources"] if item.startswith("packages/contracts/")]
    assert declared, matrix["sources"]
    for item in declared:
        assert _contract(item).is_file(), item
        json.loads(_contract(item).read_text(encoding="utf-8"))
    unread = published - opened
    assert set(declared) - opened == {f"{_WORKFLOW_SCHEMAS}/adapter-registry.schema.json"}, (
        "the capability matrix declares adapter-registry.schema.json as an input and no "
        f"consumer opens it; anything else in this set is new drift: {sorted(set(declared) - opened)}")
    assert opened < published and len(unread) == len(published) - 3, (
        "the register sentence reads as if the whole published directory is consumed; "
        f"measured: {len(opened)} opened vs {len(published)} published")
