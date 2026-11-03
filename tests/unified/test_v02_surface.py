# SPDX-License-Identifier: MIT
"""V02: real loopback HTTP surface — health, projects, capabilities, boundaries."""
from __future__ import annotations


def test_health_is_real_service_metadata(server):
    status, body = server.client.get("/api/v1/health")
    assert status == 200
    assert body["service"] == "ai-work-lab"
    assert body["data_mode"] == "live"
    assert body["envelope"].endswith("v1-draft")


def test_projects_register_and_read_back_both_sources(server, tmp_path):
    work_root = tmp_path / "work-root"
    work_root.mkdir()
    status, work_project = server.client.post("/api/v1/projects", {
        "name": "演示工作项目", "source": "work", "root_path": str(work_root)})
    assert status == 201
    assert work_project["source"] == "work"

    status, design_project = server.client.post("/api/v1/projects", {
        "name": "演示设计项目", "source": "design"})
    assert status == 201

    status, listing = server.client.get("/api/v1/projects")
    assert status == 200
    sources = {p["source"] for p in listing["unified"]}
    assert sources == {"work", "design"}
    assert any(p["id"] == design_project["root_path"] for p in listing["design_runtime"])


def test_capabilities_are_honest_and_derived(server):
    status, body = server.client.get("/api/v1/capabilities")
    assert status == 200
    by_id = {c["capability_id"]: c for c in body["capabilities"]}
    # implemented + locally verified this batch
    assert by_id["core.tasks"]["can_invoke"] is True
    assert by_id["design.knowledge.search"]["can_invoke"] is True
    # retained but not host-verified: honest refusal with named reasons
    executors = by_id["work.executors"]
    assert executors["can_invoke"] is False
    assert any("qualification" in reason or "connection" in reason
               for reason in executors["unavailable_reasons"])
    # deferred surfaces keep their phase and never claim availability
    assert by_id["core.evolution"]["implementation"] == "DECLARED"
    assert by_id["core.evolution"]["can_invoke"] is False


def test_write_boundary_unknown_project_and_kind(server):
    status, body = server.client.post("/api/v1/tasks", {
        "project_id": "0" * 32, "kind": "work", "title": "x"})
    assert status == 404
    assert body["error"] == "PROJECT_NOT_FOUND"

    status, project = server.client.post("/api/v1/projects", {
        "name": "p", "source": "design"})
    status, body = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "chat", "title": "x"})
    assert status == 400
    assert body["error"].startswith("TASK_KIND_UNKNOWN")


def test_kernel_guards_apply_to_v1_routes(server):
    # wrong Host → the kernel refuses before any v1 logic runs
    status, body = server.client.get("/api/v1/health", host="evil.example:1")
    assert status == 403
    assert body["error"] == "HOST_DENIED"
    # missing token → 401
    status, body = server.client.get("/api/v1/health", token=None)
    assert status == 401
    assert body["error"] == "UNAUTHORIZED"
    # wrong token → 401
    status, body = server.client.get("/api/v1/health", token="f" * 64)
    assert status == 401
    # unknown route → 404 with the kernel's stable code
    status, body = server.client.get("/api/v1/nothing-here")
    assert status == 404
    assert body["error"] == "NOT_FOUND"


def test_design_domain_read_routes_answer_real_data(server):
    status, project = server.client.post("/api/v1/projects", {"name": "d", "source": "design"})
    assert status == 201
    design_project_id = project["root_path"]
    status, plans = server.client.get("/api/v1/design/plans?project_id=" + design_project_id)
    assert status == 200
    # an empty list is legal data; the route must say so, not fail
    assert isinstance(plans, dict)
    status, profiles = server.client.get("/api/v1/design/target-profiles")
    assert status == 200
    assert isinstance(profiles, dict)


def _project(server, name, *, source, tmp_path=None):
    """Register one project of each domain and hand back the id every task row is filed under."""
    body = {"name": name, "source": source}
    if source == "work":
        root = tmp_path / name
        root.mkdir()
        body["root_path"] = str(root)
    status, project = server.client.post("/api/v1/projects", body)
    assert status == 201, project
    return project["project_id"]


def _task(server, project_id, title, kind):
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project_id, "kind": kind, "title": title,
        "acceptance": {"professional_required": False, "data_origin": "test"}})
    assert status == 201, task
    return task["task_id"]


# The project filter on the task list, measured over real HTTP rather than by calling the handler:
# cloud audit N02 was exactly the gap between the two. The route declares `exact=True`, dispatch
# then compares it against the *raw* request target unless the route also declares `path_only`, so
# a handler that parses `?project_id=` is unreachable code while the flag is missing -- the list
# route answered 404 for a filter its own code had already implemented.
def test_task_list_filter_returns_one_projects_tasks_not_the_whole_table(server, tmp_path):
    first = _project(server, "筛选-A", source="work", tmp_path=tmp_path)
    second = _project(server, "筛选-B", source="design")
    first_tasks = [_task(server, first, "A1", "work"), _task(server, first, "A2", "repair")]
    second_tasks = [_task(server, second, "B1", "design")]

    status, listed = server.client.get("/api/v1/tasks")
    assert status == 200, listed
    unfiltered = {row["task_id"] for row in listed["tasks"]}
    assert unfiltered == set(first_tasks) | set(second_tasks), (
        "the query-less request is the whole table; if it is not, the three legs below "
        "cannot tell a filter from a bug")

    for project_id, expected, others in ((first, first_tasks, second_tasks),
                                         (second, second_tasks, first_tasks)):
        status, body = server.client.get("/api/v1/tasks?project_id=" + project_id)
        assert status == 200, body
        rows = body["tasks"]
        # the store orders by (created_at, task_id) and tasks made in the same instant are
        # therefore ordered by their random ids, so the filter's answer is a set, not a sequence
        assert {row["task_id"] for row in rows} == set(expected), (
            "filter %s answered %s" % (project_id, [row["task_id"] for row in rows]))
        assert all(row["project_id"] == project_id for row in rows), (
            "a task from another project leaked into the filtered answer")
        assert not ({row["task_id"] for row in rows} & set(others)), (
            "the other project's tasks are present, which is the swallow the audit reported")
        assert len(rows) < len(unfiltered), (
            "the filtered answer is the same size as the unfiltered one: the query was ignored")


def test_task_list_filter_tells_an_empty_project_apart_from_an_unknown_one(server):
    empty = _project(server, "筛选-空", source="design")
    unknown = "0" * 32

    status, body = server.client.get("/api/v1/tasks?project_id=" + empty)
    assert status == 200, body
    assert body["tasks"] == [], (
        "a project with no tasks has to answer as data, not as a refusal")

    status, body = server.client.get("/api/v1/tasks?project_id=" + unknown)
    assert status == 404, body
    assert body == {"error": "PROJECT_NOT_FOUND"}, (
        "the same code POST /api/v1/tasks answers for the same unknown project; an empty 200 "
        "here is indistinguishable from 'this project has no tasks yet'")


def test_task_list_filter_refuses_its_parameters_by_name(server, tmp_path):
    """A misspelled, blank or duplicated filter must not become the full task table.

    Each leg asserts `"tasks" not in body`: the refusal is only honest if no list rides along
    with it, because a client that renders `body.tasks` would otherwise show every project's
    work under one project's heading.
    """
    known = _project(server, "筛选-拒绝", source="work", tmp_path=tmp_path)

    refusals = (
        ("/api/v1/tasks?project_id=", "TASK_FILTER_PROJECT_ID_EMPTY"),
        ("/api/v1/tasks?project_id=%20", "TASK_FILTER_PROJECT_ID_EMPTY"),
        ("/api/v1/tasks?project_id=%s&project_id=%s" % (known, "0" * 32),
         "TASK_FILTER_PROJECT_ID_DUPLICATE"),
        ("/api/v1/tasks?projectId=" + known, "TASK_FILTER_PARAM_UNKNOWN"),
        ("/api/v1/tasks?limit=5", "TASK_FILTER_PARAM_UNKNOWN"),
    )
    for path, code in refusals:
        status, body = server.client.get(path)
        assert status == 400, (path, status, body)
        assert body == {"error": code}, (path, body)
        assert "tasks" not in body, (path, body)


# ===========================================================================
# 追加节点（登记行 04#L5 / L6 / L8 / L18 / L36 / L39 / L51）
#
# 这七行在 migration/ui-entry-disposition.csv 里都写着「本仓无 pytest 断言」（验证证据
# NONE 或缺数据断言）。下面每个节点只做一件事：先用真实服务把这一份对象写进去，再 GET
# 该行点名的那一条路由，要求读回的标识（id / 条数 / 修订 / 投影字段）恰好是我写的那一份，
# 并且「空台账」与「有一条数据」两种回答的差集就是那一条。路由是否存在、判定与顶层键一律
# 以 migration/route-surface.csv 与现读的服务答复为准，不在这里重述为通过。
#
# 每个节点的「没证明」都写在它自己的 docstring 里：这些断言全部是读回断言，不是宿主证据、
# 不是真人验收、不是真实软件被探测过（NOT_PROBED 边界不因加了断言而改变）。
# ===========================================================================
import json
import secrets
import threading
import time
from pathlib import Path

from tests.conftest import Client


def _serve(workspace: Path):
    """在 `workspace` 上再起一个真实环回服务，返回 (client, stop)。

    只有主体是「服务启动时打开一次的受管台账」的节点才需要它：`server` fixture 先建服务、
    后交给测试，测试已经来不及往 `.project/paths.json` 里写东西，所以按台账现读的那两条断言
    必须自己按「写台账 → 起服务 → 读回」的顺序起第二个服务。transport 与 fixture 完全同一套
    （同一个 build_server、同一个 pinned Client、令牌随机、`--port 0` 由 OS 选口）。
    """
    workspace.mkdir(parents=True, exist_ok=True)
    (workspace / "AGENTS.md").write_text("# appended-node workspace", encoding="utf-8")
    from backend.app import build_server

    token = secrets.token_hex(32)
    httpd, context = build_server(workspace, token, 0)
    client = Client()
    client.port = httpd.server_port
    client.token = token
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    time.sleep(0.2)

    def stop():
        httpd.shutdown()
        context["unified"].close()
        context["work"].close()

    return client, stop


def test_project_detail_route_returns_the_one_project_written(server):
    """登记行 04#L5|work:project-detail → GET /api/projects/([0-9a-f]{32})（_get_project）。

    证明：这条兼容路由空台账时答复是具名拒绝（404 PROJECT_NOT_FOUND），不是 200 空壳；写入两个
    名字不同的项目后，各自的详情读回各自那一份，且与 `ProjectService.get_project()` 从同一行读出
    的字典逐字段相等（没有第二副本，也没有把另一个项目的名字张冠李戴过来）；项目列表从 0 条变成
    2 条，差集恰是我写进去的两个 id。
    没证明：详情体里只有身份三字段——对象计数、修订、待办都在项目列表那一行（04#L45），不在本
    节点范围；项目名是夹具字符串；没有任何真实宿主、真实文件或 E3/E4 证据。
    """
    status, empty = server.client.get("/api/projects")
    assert status == 200, empty
    assert empty["projects"] == [], empty

    status, missing = server.client.get("/api/projects/" + "a" * 32)
    assert status == 404, missing
    assert missing["error"] == "PROJECT_NOT_FOUND"

    status, first = server.client.post("/api/projects", {"name": "详情探针·甲"})
    assert status == 201, first
    status, second = server.client.post("/api/projects", {"name": "详情探针·乙"})
    assert status == 201, second
    first_id = first["project"]["id"]
    second_id = second["project"]["id"]
    assert first_id != second_id

    details = {}
    for project_id, expected_name in ((first_id, "详情探针·甲"),
                                      (second_id, "详情探针·乙")):
        status, detail = server.client.get("/api/projects/" + project_id)
        assert status == 200, detail
        assert set(detail) == {"project"}, sorted(detail)
        assert detail["project"]["id"] == project_id, detail
        assert detail["project"]["name"] == expected_name, detail
        # 读回的内容就是服务层那一行，不另起炉灶
        assert detail["project"] == server.design_service.get_project(project_id)
        details[project_id] = detail

    other_name = "详情探针·乙" if first_id in details else "详情探针·甲"
    assert other_name not in json.dumps(details[first_id], ensure_ascii=False)

    status, listing = server.client.get("/api/projects")
    assert status == 200, listing
    assert {row["id"] for row in listing["projects"]} == {first_id, second_id}, listing
    assert len(listing["projects"]) == 2


def test_environment_projection_reads_the_paths_ledger_at_boot(server, tmp_path):
    """登记行 04#L6|work:environment → GET /api/environment（_environment → paths.describe()）。

    证明：这一面读的是受管台账 `<workspace>/.project/paths.json`，启动时现读、不落第二副本。
    没有台账时 tools/shared_inputs 都是空对象、来源词写 "default"；写进台账后投影响应里的
    条目名与路径值与文件一字不差，且条目数恰等于文件声明的条目数；把台账里那一个
    shared_inputs 路径改掉再读，投影里变的只有该项的路径字面和依赖它的工具行归属，其余键与值
    全部保持原样；投影没有引入台账里没有的键。工具行的判决是词表判决（BOUND /
    DECLARED_OUTSIDE_SHARED_ROOT / DECLARED_VALUE_INVALID），共享输入一律 DECLARED_NOT_PROBED
    ——即使那个目录真的存在，它也写「未探测」。
    没证明：没有任何本机软件被探测、启动或运行；agent_profile 仍写 PRIVATE_NOT_INSPECTED，
    write_trace 与 migration 仍写 NOT_EXECUTED；台账里的 .exe 是测试自造的 0 字节合成文件。
    """
    status, baseline = server.client.get("/api/environment")
    assert status == 200, baseline
    assert baseline["status"] == "PATHS_RESOLVED", baseline
    assert baseline["tools"] == {}, baseline["tools"]
    assert baseline["shared_inputs"] == {}, baseline["shared_inputs"]
    assert baseline["sources"] == {"project_local_root": "default"}, baseline["sources"]

    workspace = tmp_path / "ledger-workspace"
    inside_root = workspace / ".project-local" / "synthetic-libraries"
    inside_root.mkdir(parents=True)
    tool = inside_root / "fixture-tool.exe"          # 合成文件，与任何真实软件无关
    tool.write_text("synthetic fixture", encoding="utf-8")
    ledger = {"schemaVersion": "design-lab/project-paths/v2",
              "shared_inputs": {"synthetic-libs": inside_root.as_posix()},
              "tools": {"fixture-tool": tool.as_posix(),
                        "elsewhere-tool": "D:/synthetic/outside/thing.exe",
                        "blank-tool": ""}}
    config_dir = workspace / ".project"
    config_dir.mkdir(parents=True)
    (config_dir / "paths.json").write_text(json.dumps(ledger, ensure_ascii=False),
                                           encoding="utf-8")

    client, stop = _serve(workspace)
    try:
        status, seeded = client.get("/api/environment")
        assert status == 200, seeded
        assert seeded["project_root"] == str(workspace.absolute()).replace("\\", "/"), seeded
        # —— 台账里有什么，投影就有什么：名字与值现读，不多不少
        assert set(seeded["shared_inputs"]) == set(ledger["shared_inputs"]), seeded
        assert set(seeded["tools"]) == set(ledger["tools"]), seeded
        assert seeded["shared_inputs"]["synthetic-libs"]["path"] == ledger[
            "shared_inputs"]["synthetic-libs"], seeded["shared_inputs"]
        assert seeded["tools"]["fixture-tool"]["path"] == ledger["tools"]["fixture-tool"]
        # —— 判决是词表判决，不是探测结果
        assert seeded["tools"]["fixture-tool"]["status"] == "BOUND", seeded["tools"]
        assert seeded["tools"]["fixture-tool"]["owner"] == "synthetic-libs", seeded["tools"]
        assert seeded["tools"]["elsewhere-tool"]["status"] == "DECLARED_OUTSIDE_SHARED_ROOT"
        assert seeded["tools"]["elsewhere-tool"]["owner"] is None, seeded["tools"]
        assert seeded["tools"]["blank-tool"]["status"] == "DECLARED_VALUE_INVALID", seeded["tools"]
        assert seeded["shared_inputs"]["synthetic-libs"]["status"] == "DECLARED_NOT_PROBED"
        assert seeded["shared_inputs"]["synthetic-libs"]["writable"] is False
        # —— 不引入台账没有的字段
        assert set(seeded["shared_inputs"]["synthetic-libs"]) == {"path", "writable", "status"}
        assert set(seeded["tools"]["fixture-tool"]) == {"path", "owner", "status"}
        assert set(seeded["tools"]["elsewhere-tool"]) == {"path", "owner", "status", "reason"}

        moved = workspace.as_posix() + "/.project-local/other-libs"   # 该目录并不存在
        (config_dir / "paths.json").write_text(
            json.dumps({**ledger, "shared_inputs": {"synthetic-libs": moved}},
                       ensure_ascii=False), encoding="utf-8")
        client2, stop2 = _serve(workspace)
        try:
            status, changed = client2.get("/api/environment")
            assert status == 200, changed
        finally:
            stop2()
        assert set(changed) == set(seeded), (sorted(changed), sorted(seeded))
        # 台账里改的那一项，投影里跟着变
        assert changed["shared_inputs"]["synthetic-libs"]["path"] == moved, changed
        assert changed["tools"]["fixture-tool"]["status"] == "DECLARED_OUTSIDE_SHARED_ROOT"
        assert changed["tools"]["fixture-tool"]["owner"] is None
        # 没改的项一个都没动；不存在的共享根照样只写「声明未探测」
        assert changed["tools"]["elsewhere-tool"] == seeded["tools"]["elsewhere-tool"]
        assert changed["tools"]["blank-tool"] == seeded["tools"]["blank-tool"]
        assert changed["shared_inputs"]["synthetic-libs"]["status"] == "DECLARED_NOT_PROBED"
        # 两份答复的差集恰是我改的那一处台账声明，别处一字不动
        assert {key for key in changed if changed[key] != seeded[key]} == \
            {"shared_inputs", "tools"}, sorted(seeded)
        # 与「没有台账」的那次相比，只有台账派生的两节变了；诚实字段照旧
        for key in ("schemaVersion", "status", "sources", "agent_profile", "write_trace",
                    "migration"):
            assert changed[key] == seeded[key] == baseline[key], key
    finally:
        stop()


#: GET /api/work/observer/projection 的 usage 分组里，本测试要求存在的聚合列。
#: 抄自 domains/work/workflow_core/canonical_store.py::projection 的 SELECT，
#: 质量词表按仓内采集器自己写的词（orchestration/collectors.py:243、:393 的
#: EXACT_SOURCE / UNKNOWN），不是本测试发明的词。键集故意不钉死：这一列的聚合形状
#: 仍在 usage 这条线上演进，钉死键名只会让下一个改投影的人顺手删断言。要钉的是
#: 「每个数字都等于写进去的那几条」与「质量划分里一行都不许消失」。
USAGE_REQUIRED_KEYS = {
    "provider", "model", "samples", "samples_with_tokens", "input_tokens", "output_tokens",
    "tokens", "observed_at", "token_coverage", "measured_tokens", "unattributed_tokens",
    "samples_with_reconciled_cost", "samples_with_estimated_cost", "cost_reconciled_total",
    "cost_estimate_total", "cost_coverage", "quality_samples", "tokens_by_quality",
}
#: 覆盖词的封闭词表：没数、部分有数、全有数是三句话。
USAGE_COVERAGE_WORDS = {"NONE", "PARTIAL", "FULL"}


def test_observer_projection_usage_reports_what_the_store_holds(server):
    """登记行 04#L8|work:usage → GET /api/work/observer/projection（usage 键）。

    证明：usage 是 canonical 台账现读的聚合，不是我抄的数——空台账答 []；写进四条样本后只出现
    我写的那三个 (provider, model) 分组，`store` 就是我写进去的那个库文件，分组里的每个数字都
    等于我写的那几条（samples / samples_with_tokens / input_tokens / output_tokens / tokens /
    observed_at / 两个成本合计 / 两个贡献计数）；「实测与估计分开」在两侧都成立：token 侧
    EXACT_SOURCE 那条的 150 只进 measured_tokens，UNKNOWN 那条在 tokens_by_quality 里是 null
    而不是 0，钱侧 cost_reconciled_total(0.42) 与 cost_estimate_total(0.11) 各算各的、彼此不等、
    也都不等于 tokens；「未知不填 0」：一组全无数时 input/output/tokens/measured/unattributed
    与两个成本合计一律 null，覆盖词写 NONE；质量词表外的写法（LEGACY_SOURCE）不被折成实测
    ——measured_tokens 仍是 null，而那一条也没有从质量划分里消失（划分求和等于 samples）。
    前后两次答复的差集只在 usage 一处。
    没证明：任何真实计费、真实模型用量或采集器跑过；四条样本是本测试用 canonical 写入口灌进
    临时库的合成记录（与 conftest.seed_issue 同一写法），cost 字段未经任何外部对账。
    """
    status, before = server.client.get("/api/work/observer/projection")
    assert status == 200, before
    assert before["usage"] == [], before["usage"]
    store = server.work.store
    assert str(store.path) == before["store"], before["store"]

    store.record_usage_sample({
        "sample_id": "v02-usage-exact", "project_id": "v02-probe-project",
        "provider": "v02-probe-provider", "model": "v02-probe-model",
        "observed_at": "2026-10-30T09:00:00Z", "input_tokens": 120, "output_tokens": 30,
        "quality": "EXACT_SOURCE", "cost_reconciled": 0.42})
    store.record_usage_sample({
        "sample_id": "v02-usage-unknown", "project_id": "v02-probe-project",
        "provider": "v02-probe-provider", "model": "v02-probe-model",
        "observed_at": "2026-10-30T09:10:00Z", "quality": "UNKNOWN", "cost_estimate": 0.11})
    store.record_usage_sample({
        "sample_id": "v02-usage-empty-group", "project_id": "v02-probe-project",
        "provider": "v02-other-provider", "model": "v02-other-model",
        "observed_at": "2026-10-30T09:00:00Z", "input_tokens": None, "output_tokens": None,
        "quality": "UNKNOWN"})
    store.record_usage_sample({
        "sample_id": "v02-usage-strange-word", "project_id": "v02-probe-project",
        "provider": "v02-word-provider", "model": "v02-word-model",
        "observed_at": "2026-10-30T09:00:00Z", "input_tokens": 5, "output_tokens": 5,
        "quality": "LEGACY_SOURCE"})

    status, after = server.client.get("/api/work/observer/projection")
    assert status == 200, after
    groups = {(row["provider"], row["model"]): row for row in after["usage"]}
    assert set(groups) == {("v02-probe-provider", "v02-probe-model"),
                           ("v02-other-provider", "v02-other-model"),
                           ("v02-word-provider", "v02-word-model")}, after["usage"]

    for pair, group in groups.items():
        assert USAGE_REQUIRED_KEYS <= set(group), (pair, sorted(set(group)))
        # 质量划分与 token 归属用同一套词，且每一条样本都在划分里
        assert set(group["tokens_by_quality"]) <= set(group["quality_samples"]), pair
        assert sum(group["quality_samples"].values()) == group["samples"], pair
        assert group["token_coverage"] in USAGE_COVERAGE_WORDS, pair
        assert set(group["cost_coverage"]) == {"reconciled", "estimated"}, pair
        assert set(group["cost_coverage"].values()) <= USAGE_COVERAGE_WORDS, pair

    measured = groups[("v02-probe-provider", "v02-probe-model")]
    assert measured["samples"] == 2 and measured["samples_with_tokens"] == 1, measured
    assert measured["token_coverage"] == "PARTIAL", measured
    assert measured["input_tokens"] == 120, measured      # 只有 EXACT_SOURCE 那条有数
    assert measured["output_tokens"] == 30, measured
    assert measured["tokens"] == 150, measured            # = 120 + 30，我写进去的那份
    assert measured["observed_at"] == "2026-10-30T09:10:00Z", measured
    assert measured["measured_tokens"] == 150, measured
    assert measured["tokens_by_quality"]["EXACT_SOURCE"] == 150, measured
    # 未知不填 0：UNKNOWN 这一格是缺失，不是 0
    assert measured["tokens_by_quality"]["UNKNOWN"] is None, measured
    assert measured["quality_samples"]["EXACT_SOURCE"] == 1, measured
    assert measured["quality_samples"]["UNKNOWN"] == 1, measured
    # —— 钱侧的实测与估计分开：两个合计各自来自各自的列，互不相等
    assert measured["cost_reconciled_total"] == 0.42, measured
    assert measured["cost_estimate_total"] == 0.11, measured
    assert measured["cost_reconciled_total"] != measured["cost_estimate_total"], measured
    assert measured["samples_with_reconciled_cost"] == 1, measured
    assert measured["samples_with_estimated_cost"] == 1, measured
    assert measured["cost_coverage"] == {"reconciled": "PARTIAL", "estimated": "PARTIAL"}

    # —— 一组全无数：所有聚合列保持缺失
    unknown = groups[("v02-other-provider", "v02-other-model")]
    assert unknown["samples"] == 1 and unknown["samples_with_tokens"] == 0, unknown
    assert unknown["token_coverage"] == "NONE", unknown
    for key in ("input_tokens", "output_tokens", "tokens", "measured_tokens",
                "unattributed_tokens", "cost_reconciled_total", "cost_estimate_total"):
        assert unknown[key] is None, (key, unknown[key])
    assert unknown["cost_coverage"] == {"reconciled": "NONE", "estimated": "NONE"}, unknown

    # —— 词表外的质量词不被折成实测，但这条样本不许从划分里消失
    strange = groups[("v02-word-provider", "v02-word-model")]
    assert strange["tokens"] == 10 and strange["measured_tokens"] is None, strange
    assert strange["quality_samples"].get("EXACT_SOURCE", 0) == 0, strange
    assert sum(strange["quality_samples"].values()) == 1, strange

    stored = {row["sample_id"]: row for row in store.list_usage_samples()}
    assert stored["v02-usage-exact"]["cost_reconciled"] == 0.42, stored
    assert stored["v02-usage-unknown"]["cost_estimate"] == 0.11, stored

    assert set(after) == set(before), (sorted(after), sorted(before))
    for key in set(after) - {"usage", "observed_at"}:
        assert after[key] == before[key], (key, before[key], after[key])


def test_software_projection_is_the_registry_read_now_not_a_copy(server, tmp_path):
    """登记行 04#L18|work:software → GET /api/work/observer/snapshot 的 software[]。

    该行「当前实现位置」点名的是 domains/work/orchestration/software_installation_identity.py
    里的 classify_installation（模块，不是路由）；这台服务对「本机软件」的 HTTP 读面是快照的
    software[]，其行由 config/software-registry.json 现读投影而来。断言落在「从文件现读、不落
    第二副本」这一语义上：先按产品自己的定位函数读台账，确认 software[] 的行与台账逐项同源；
    再把定位指到一份合成台账，行立刻只剩合成台账那两条（改 displayName 就跟着改，缺 displayName
    就是 null，没有 softwareId 的行不出现——投影不自造标识）；台账读不到时快照里没有 software
    这个键，而不是空数组。
    没证明：任何真实软件被安装、探测、授权或可执行——每行的安装/版本/可执行侧全是 null、
    locationStatus 恒为 NOT_PROBED，而 NOT_PROBED 不在 classify_installation 的判决词表里。
    合成台账与 0 字节 fixture 文件都在 tmp_path 里，与本机安装无关。
    """
    from domains.work.control import composition_root
    from domains.work.orchestration import software_installation_identity as sii

    ledger = json.loads(composition_root.software_registry_path().read_text(encoding="utf-8"))
    entries = ledger["software"]
    assert entries, "真实台账必须声明至少一项，否则下面的同源断言是空转"

    status, snapshot = server.client.get("/api/work/observer/snapshot")
    assert status == 200, snapshot
    rows = snapshot["software"]
    assert [row["softwareId"] for row in rows] == [e["softwareId"] for e in entries], rows
    assert [row["displayName"] for row in rows] == [e["displayName"] for e in entries], rows

    synthetic = tmp_path / "software-registry.json"
    synthetic.write_text(json.dumps({
        "schemaVersion": "workflow/software-registry/v1",
        "software": [
            {"softwareId": "v02-fixture-a", "displayName": "夹具甲"},
            {"softwareId": "v02-fixture-b", "displayName": None},
            {"displayName": "没有标识的行不该被投影成一条软件"},
        ],
    }, ensure_ascii=False), encoding="utf-8")

    original_locator = composition_root.software_registry_path
    try:
        composition_root.software_registry_path = lambda: synthetic
        composition_root.clear_software_discovery_cache()
        status, swapped = server.client.get("/api/work/observer/snapshot")
        assert status == 200, swapped
        assert [row["softwareId"] for row in swapped["software"]] == \
            ["v02-fixture-a", "v02-fixture-b"], swapped["software"]
        assert swapped["software"][0]["displayName"] == "夹具甲", swapped["software"]
        assert swapped["software"][1]["displayName"] is None, swapped["software"]

        # 改台账里的某一项 → 投影里对应值随之变化，其余保持不动
        synthetic.write_text(json.dumps({
            "schemaVersion": "workflow/software-registry/v1",
            "software": [
                {"softwareId": "v02-fixture-a", "displayName": "夹具甲·改名"},
                {"softwareId": "v02-fixture-b", "displayName": None},
            ],
        }, ensure_ascii=False), encoding="utf-8")
        composition_root.clear_software_discovery_cache()
        status, renamed = server.client.get("/api/work/observer/snapshot")
        assert status == 200, renamed
        assert renamed["software"][0]["displayName"] == "夹具甲·改名", renamed["software"]
        assert renamed["software"][1] == swapped["software"][1], renamed["software"]

        # 投影不引入台账里没有的软件事实：行形状固定，安装/版本/可执行侧一律缺失
        scaffold = {"installRoot": None, "executableRealpath": None, "discoveredVersion": None,
                    "releaseChannel": None, "updateAvailable": None,
                    "duplicateInstallation": False, "expectedLocation": None,
                    "observedLocation": None, "lastVerified": None}
        for row in renamed["software"]:
            assert set(row) == {"softwareId", "displayName", "locationStatus",
                                "discoverySource", "probeReason"} | set(scaffold), sorted(row)
            assert row["locationStatus"] == "NOT_PROBED", row
            assert row["locationStatus"] not in sii.LOCATION_STATUS, sii.LOCATION_STATUS
            assert row["discoverySource"] == "not-probed", row
            for key, value in scaffold.items():
                assert row[key] == value, (key, row[key])

        # 台账读不到：不是空数组，是这个键不出现（缺失与为空是两句话）
        composition_root.software_registry_path = lambda: tmp_path / "no-such-registry.json"
        composition_root.clear_software_discovery_cache()
        status, absent = server.client.get("/api/work/observer/snapshot")
        assert status == 200, absent
        assert "software" not in absent, sorted(absent)
    finally:
        composition_root.software_registry_path = original_locator
        composition_root.clear_software_discovery_cache()


def test_intake_brief_goals_and_revisions_read_back(server, tmp_path):
    """登记行 04#L36|design:intake → briefs 读写路由（输入与目标的连续状态）。

    证明：空台账的 GET /api/projects/{id}/briefs 答 briefs == []；POST 一份输入与目标后，列表
    里恰有那一条，brief_id、title、goals、constraints、spec_sha256、version=1 与写入返回的
    文档逐字段相同；GET 单条与 GET 列表给出同一份字节；再写一版修订时新行 version=2、旧行的
    superseded_by 指向新行、lineage 的 root_id/live_id/versions 里两版 goals 各自是我写的那句
    ——连续状态（草拟→修订→当前）在服务里可读，不在页面里猜；另一个项目的 briefs 依旧是空，
    说明读回绑的是这一个对象。
    没证明：# /intake 那张屏是否真的渲染了这些字段（前端由 STITCH 交付，本轮 NOT_RUN）；brief
    内容的专业对错、rights、是否被采纳；参考资产 id 的存在性由别的合同管。
    """
    status, project = server.client.post("/api/v1/projects",
                                         {"name": "输入与目标探针", "source": "design"})
    assert status == 201, project
    other = server.client.post("/api/v1/projects",
                               {"name": "隔壁项目", "source": "design"})
    assert other[0] == 201, other
    project_id = project["root_path"]

    status, empty = server.client.get(f"/api/projects/{project_id}/briefs")
    assert status == 200, empty
    assert empty["briefs"] == [], empty["briefs"]

    written = {"title": "封面节奏", "goals": ["让前三秒立住主体"],
               "constraints": "只用一个字体族", "reference_asset_ids": [],
               "idempotency_key": "v02-intake-brief-1"}
    status, created = server.client.post(f"/api/projects/{project_id}/briefs", written)
    assert status == 201, created
    brief = created["brief"]
    assert brief["version"] == 1 and brief["superseded_by"] is None, brief
    brief_id = brief["brief_id"]

    status, listed = server.client.get(f"/api/projects/{project_id}/briefs")
    assert status == 200, listed
    assert [row["brief_id"] for row in listed["briefs"]] == [brief_id], listed
    assert listed["briefs"][0] == brief, listed["briefs"][0]
    for field in ("title", "goals", "constraints", "reference_asset_ids"):
        assert brief[field] == written[field], (field, brief[field])

    status, single = server.client.get(f"/api/projects/{project_id}/briefs/{brief_id}")
    assert status == 200, single
    assert single["brief"] == brief, single["brief"]

    status, foreign = server.client.get(f"/api/projects/{other[1]['root_path']}/briefs")
    assert status == 200, foreign
    assert foreign["briefs"] == [], foreign["briefs"]

    revised = {**written, "title": "封面节奏 v2",
               "goals": ["前三秒立住主体，并把色带留在底部"],
               "idempotency_key": "v02-intake-brief-2"}
    status, next_version = server.client.post(
        f"/api/projects/{project_id}/briefs/{brief_id}/revisions", revised)
    assert status == 201, next_version
    new_id = next_version["brief"]["brief_id"]
    assert next_version["brief"]["version"] == 2, next_version["brief"]
    assert next_version["brief"]["goals"] == revised["goals"], next_version["brief"]

    status, parent = server.client.get(f"/api/projects/{project_id}/briefs/{brief_id}")
    assert status == 200, parent
    assert parent["brief"]["superseded_by"] == new_id, parent["brief"]
    assert parent["brief"]["goals"] == written["goals"], parent["brief"]

    status, lineage = server.client.get(f"/api/projects/{project_id}/briefs/{brief_id}/lineage")
    assert status == 200, lineage
    chain = lineage["lineage"]
    assert chain["root_id"] == brief_id, chain
    assert chain["live_id"] == new_id, chain
    assert [row["version"] for row in chain["versions"]] == [1, 2], chain["versions"]
    assert [row["goals"] for row in chain["versions"]] == [written["goals"], revised["goals"]]

    status, listed_after = server.client.get(f"/api/projects/{project_id}/briefs")
    assert status == 200, listed_after
    assert {row["brief_id"] for row in listed_after["briefs"]} == {brief_id, new_id}, listed_after


def test_research_findings_read_back_only_what_was_filed(server):
    """登记行 04#L39|design:research → GET/POST /api/projects/{id}/research。

    证明：空台账 finding_count 0、findings []、research_verdict null；POST 一条洞察后读回的
    findings[0] 与我提交的那份文档逐字节相同（finding_id/claim/sourceRefs/confidence/
    notDesignRule），计数从 0 变 1 且 confidence_counts.medium、sourced_finding_count、
    source_ref_total 都等于我写的那一条；HTTP 提交者没有自报身份，所以它进
    unattributed_findings、actor_kinds 里是 null——系统不替人署名；再按 ?supersedes= 写一条更正
    后 finding_count=2、current_finding_count=1、superseded_finding_count=1，current_findings
    只有第二条，第一条仍在 findings 里可读（退役不是删除）。全程没有任何联网检索发生，读面也
    不给「研究完成」这个词。
    没证明：sourceRefs 指向的来源真实存在或被核对过（读面自己就写了 does_not_prove）；洞察的
    专业质量；这些条目不是 KnowledgeCandidate、不是对外导出。
    """
    status, project = server.client.post("/api/v1/projects",
                                         {"name": "研究洞察探针", "source": "design"})
    assert status == 201, project
    project_id = project["root_path"]

    status, empty = server.client.get(f"/api/projects/{project_id}/research")
    assert status == 200, empty
    assert empty["findings"] == [] and empty["finding_count"] == 0, empty
    assert empty["research_verdict"] is None, empty

    finding = {"finding_id": "v02-finding-1", "claim": "同类封面把主体放在左三分之一",
               "sourceRefs": ["reference:v02-probe-source"], "confidence": "medium",
               "notDesignRule": True}
    status, filed = server.client.post(f"/api/projects/{project_id}/research", finding)
    assert status == 201, filed
    assert filed == finding, filed

    status, one = server.client.get(f"/api/projects/{project_id}/research")
    assert status == 200, one
    assert one["findings"] == [finding], one["findings"]
    assert one["finding_count"] == 1 == one["current_finding_count"], one
    assert one["sourced_finding_count"] == 1, one
    assert one["source_ref_total"] == len(finding["sourceRefs"]), one
    assert one["confidence_counts"]["medium"] == 1, one["confidence_counts"]
    assert one["stated_confidence_count"] == 1, one
    assert one["unattributed_findings"] == ["v02-finding-1"], one
    assert one["actor_kinds"] == {"v02-finding-1": None}, one["actor_kinds"]
    assert one["research_verdict"] is None, one
    assert one["proves_design_quality"] is False and one["is_knowledge_export"] is False

    correction = {"finding_id": "v02-finding-2", "claim": "更正：主体在右下",
                  "sourceRefs": ["reference:v02-probe-source-2"], "confidence": "low",
                  "notDesignRule": True}
    status, filed2 = server.client.post(
        f"/api/projects/{project_id}/research?supersedes=v02-finding-1", correction)
    assert status == 201, filed2

    status, after = server.client.get(f"/api/projects/{project_id}/research")
    assert status == 200, after
    assert after["finding_count"] == 2, after
    assert after["current_finding_count"] == 1, after
    assert after["superseded_finding_count"] == 1, after
    assert {row["finding_id"] for row in after["findings"]} == \
        {"v02-finding-1", "v02-finding-2"}, after["findings"]
    assert list(after["current_findings"]) == ["v02-finding-2"], after["current_findings"]
    assert after["current_findings"]["v02-finding-2"]["claim"] == correction["claim"]
    assert after["research_verdict"] is None, after


def test_settings_read_set_answers_and_writes_nothing(server):
    """登记行 04#L51|design:settings → 设置屏的读集（GET /api/environment、/api/models、
    /api/knowledge-entries/search）。

    证明：这三处读回都在真实服务上答 200；模型目录的每个数字与每一行都是从两份受管台账现读的
    ——counts.models/endpoints 等于台账行数，model_id / provider_id 集合与台账一致，逐行的
    radar_state / placement / license_id / commercial_use / default_enabled / weights_recorded
    等于台账里该条自己的值，权重的三态答复（UNSTATED / REGISTERED_NONE / RECORDED）与两个出处格
    hash_source、qualified_by 也随路由原样带出（不只在进程内的投影里成立），三个状态计数相加
    恰等于条目数；qualified_local、default_enabled_true、weights_recorded 是从台账
    重算的（不是写死的 0），两份台账的合并不被冒领（join.key 为 null）；设置屏的索引行绑的是
    真数据——空库时 total 0 / entries []，POST 一条知识条目后 limit=1 的检索答的就是我刚写的
    那条，total 变 1，差集恰这一条；设置面写不进去：POST 到这三个读点是 404 NOT_FOUND，
    PUT/PATCH/DELETE 是 405 METHOD_NOT_ALLOWED，试过之后三处读回与试之前逐字段相同。
    没证明：模型被加载、下载、哈希或运行过；许可被裁定过；真实机器状态来自
    MACHINE_INVENTORY 记录而不是本次探测；# /settings 那张屏的渲染（前端由 STITCH 交付）；
    这一轮没有覆盖「设置里有开关」那类旧设想。
    """
    from design_lab import model_catalog
    from design_lab.readiness import model_radar

    radar = json.loads(model_radar.REGISTRY_PATH.read_text(encoding="utf-8"))
    providers = json.loads(model_catalog.PROVIDERS_PATH.read_text(encoding="utf-8"))
    radar_rows = {row["model_id"]: row for row in radar["entries"]}
    provider_rows = [row["provider_id"] for row in providers["providers"]]

    status, environment = server.client.get("/api/environment")
    assert status == 200, environment
    status, catalog = server.client.get("/api/models")
    assert status == 200, catalog
    status, index_before = server.client.get("/api/knowledge-entries/search?limit=1")
    assert status == 200, index_before
    assert index_before["total"] == 0 and index_before["entries"] == [], index_before

    assert catalog["sources"] == {"models": "design-lab/readiness/model-radar.json",
                                 "endpoints": "design-lab/config/provider-capabilities.json"}
    assert catalog["counts"]["models"] == len(radar["entries"]), catalog["counts"]
    assert catalog["counts"]["endpoints"] == len(provider_rows), catalog["counts"]
    assert [row["model_id"] for row in catalog["models"]] == list(radar_rows), catalog["models"]
    for row in catalog["models"]:
        source = radar_rows[row["model_id"]]
        assert row["radar_state"] == source["radar_state"], row
        assert row["placement"] == source["source"]["kind"], row
        assert row["license_id"] == source["rights"]["license_id"], row
        assert row["commercial_use"] == source["rights"]["commercial_use"], row
        assert row["default_enabled"] == source["default_enabled"], row
        assert row["weights_recorded"] == len(source.get("weights_sha256") or []), row
        # the two provenance cells and the three-state weight answer must survive the route,
        # not only the in-process projection the honesty suite drives
        assert row["hash_source"] == source.get("hash_source"), row
        assert row["qualified_by"] == source.get("qualified_by"), row
        assert row["weights_state"] in ("UNSTATED", "REGISTERED_NONE", "RECORDED"), row
        assert row["weights_state"] == (
            "RECORDED" if (source.get("weights_sha256") or []) else
            "UNSTATED" if "weights_sha256" not in source else "REGISTERED_NONE"), row
    counts = catalog["counts"]
    assert counts["weights_unstated"] + counts["weights_registered_none"] + counts["weights_recorded"] \
        == counts["models"], counts
    assert counts["weights_recorded"] == sum(
        1 for row in catalog["models"] if row["weights_state"] == "RECORDED"), counts
    assert catalog["counts"]["qualified_local"] == sum(
        1 for row in catalog["models"] if row["radar_state"] == "QUALIFIED_LOCAL"), catalog
    assert catalog["counts"]["default_enabled_true"] == sum(
        1 for row in catalog["models"] if row["default_enabled"] is True), catalog
    assert catalog["counts"]["weights_recorded"] == sum(
        1 for row in catalog["models"] if row["weights_recorded"]), catalog
    assert [row["provider_id"] for row in catalog["endpoints"]] == provider_rows, catalog
    assert catalog["join"]["key"] is None, catalog["join"]
    assert catalog["selection"]["transport"] == "NOT_CONNECTED", catalog["selection"]
    assert catalog["selection"]["executed"] is False, catalog["selection"]

    source = {"sourceId": "v02-settings-probe", "origin": "UNKNOWN", "author": "owner",
              "license": "UNKNOWN", "licenseStatus": "unknown", "allowedUsage": "UNKNOWN",
              "citationScope": "UNKNOWN", "version": "1",
              "observedAt": "2026-11-01T00:00:00Z", "contentHash": "UNKNOWN",
              "verification": "UNVERIFIED"}
    status, created = server.client.post("/api/knowledge-entries", {
        "entry_type": "METHOD", "title": "设置读集探针条目", "summary": "一条",
        "domain_tags": ["film"], "task_tags": ["storyboard"], "target_tools": ["probe"],
        "body": "正文", "applicability": "适用", "limits": "限制", "source": source,
        "related_capability_ids": [], "recommended": True, "created_by": "owner",
        "supersedes": None})
    assert status == 201, created
    entry_id = created["entry"]["knowledge_entry_id"]

    status, index_after = server.client.get("/api/knowledge-entries/search?limit=1")
    assert status == 200, index_after
    assert index_after["total"] == 1, index_after
    assert [row["knowledge_entry_id"] for row in index_after["entries"]] == [entry_id]
    assert index_after["entries"][0]["title"] == "设置读集探针条目", index_after["entries"]

    read_points = ("/api/environment", "/api/models", "/api/knowledge-entries/search?limit=1")
    for method, expected in (("POST", "NOT_FOUND"), ("PUT", "METHOD_NOT_ALLOWED"),
                             ("PATCH", "METHOD_NOT_ALLOWED"), ("DELETE", "METHOD_NOT_ALLOWED")):
        for path in read_points:
            # 不带请求体：路由表里就没有这些方法的路由，拒绝发生在读体之前
            status, refused = server.client.request(method, path)
            assert status in (404, 405), (method, path, status, refused)
            assert refused["error"] == expected, (method, path, refused)

    status, environment_again = server.client.get("/api/environment")
    status, catalog_again = server.client.get("/api/models")
    status, index_again = server.client.get("/api/knowledge-entries/search?limit=1")
    assert (environment_again, catalog_again, index_again) == \
        (environment, catalog, index_after), "设置面的读回被一次写尝试改动了"


# ===========================================================================
# 登记行 05#L11|configuration —「局部配置可恢复，不覆盖原生认证和全局环境」
#
# 下面四个节点把这句验收钉成真断言。夹具全程只把受管配置目录整份抄进 tmp_path 再改内容，
# 然后按产品自己的定位（`domains/work/control/composition_root.py:57` 的 `_ROOT`）指过去；
# 真实 `config/` 与产品代码一个字节都不写，每个节点末尾用逐文件 sha256 快照自证。
#
# 读链现读结论（写断言前先读的代码）：
#   GET /api/work/observer/snapshot → work_surfaces.observer_snapshot:105-120
#     → composition_root.build_v3_snapshot:746-812 的 `adapter_capabilities=` 入参:804
#     → composition_root._adapter_capability_rows:815-866 → adapter_capability_projection
#       .load_inputs:409-414（`<root>/config/adapter-registry.json` 等三份，每次请求现读）
#     → project_adapter_capabilities:274-363（本机绝对路径经 `versionSource`:341 透传）
#   GET /api/v1/capabilities → backend/v1.py:398-419 → capabilities.derive_catalog:97-128
#     ——它只遍历 CATALOG_SPEC 声明 + 资格台账，不打开 adapter-registry.json。
#   POST /api/work/control/operations → work_surfaces.control_execute:297-325
#     → control_service.ControlPlane.execute:500-540（合同 → 封闭 OPERATIONS 枚举:185-253
#       → _scope_failure:570-603 → PermissionGate（forbidden_paths=FORBIDDEN_TARGETS:108,323-327）
#       → 唯一实现的配置动词 _config_diff:870-920）。
# ===========================================================================

#: `_adapter_capability_rows` → `load_inputs` 会按 `<root>/config/<name>` 现读的三份受管台账。
CFG_REGISTRY_FILES = ("adapter-registry.json", "capability-conformance.json",
                      "capability-matrix.json")
#: 被局部改写的那一个条目与被整条移除的那一个条目（都是台账里真实存在的 id）。
CFG_LOCAL_CLIENT = "hermes"
CFG_DROPPED_CLIENT = "cursor"
#: 抄进 tmp 的全局环境台账里放的标记：任何答复带上它，就说明存在一条消费该台账的产品读面。
CFG_GLOBAL_ENV_MARKER = "SYNTHETIC-GLOBAL-ENV-05L11-NOT-A-PRODUCT-READ"
#: 合成控制请求的公共信封（`control-operation.schema.json:8` 的必填集，payload 随操作换）。
CFG_CONTRACT_TARGET = "packages/contracts/schemas/workflow/client-adapter.schema.json"


def _cfg_digest_tree(root: Path) -> dict:
    """一棵目录树的逐文件摘要快照：名单与内容一起比，才是「没被写过」。"""
    import hashlib

    return {str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(Path(root).rglob("*")) if path.is_file()}


def _cfg_shadow_root(tmp_path: Path) -> Path:
    """把受管配置面整份抄进 tmp，并补上投影链要点名的合同文件。

    `environment-baseline.json` 同样抄一份，但把全局环境的两处值改成可识别的标记：
    节点用它反向证明答复面里没有这条台账的消费者（而不是假设它没有）。
    """
    from domains.work.orchestration import resources

    shadow = tmp_path / "managed-config"
    (shadow / "config").mkdir(parents=True, exist_ok=True)
    for name in CFG_REGISTRY_FILES:
        (shadow / "config" / name).write_bytes(resources.config_path(name).read_bytes())
    baseline = json.loads(resources.config_path("environment-baseline.json")
                          .read_text(encoding="utf-8"))
    baseline["target_root"] = CFG_GLOBAL_ENV_MARKER
    baseline["generated_by"] = CFG_GLOBAL_ENV_MARKER
    (shadow / "config" / "environment-baseline.json").write_text(
        json.dumps(baseline, ensure_ascii=False, indent=2), encoding="utf-8")
    schema = CFG_CONTRACT_TARGET
    target = shadow / schema
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes((resources.repo_root() / schema).read_bytes())
    return shadow


def _cfg_apply_registry_variant(shadow: Path, tmp_path: Path, variant: str) -> dict:
    """把 tmp 里那份合成台账改成指定形态（只写 tmp），返回改后的文档。

    verbatim/restore 从真实文件逐字节重抄（恢复＝回到那份内容）；其余形态各自只动一处形状，
    global 是故意越界的反证形态，promote 是把「未探测」顶成「已验证」的反证形态。
    """
    from domains.work.orchestration import resources

    registry = shadow / "config" / CFG_REGISTRY_FILES[0]
    if variant in ("verbatim", "restore"):
        registry.write_bytes(resources.config_path(CFG_REGISTRY_FILES[0]).read_bytes())
        return json.loads(registry.read_text(encoding="utf-8"))
    document = json.loads(resources.config_path(CFG_REGISTRY_FILES[0])
                          .read_text(encoding="utf-8"))
    entries = document["entries"]
    if variant == "local":
        entry = next(item for item in entries if item.get("id") == CFG_LOCAL_CLIENT)
        entry["display_name"] = "合成·局部改名（不是本机观测）"
        entry["provenance"]["version_readback"]["source"] = \
            (tmp_path / "synthetic-install-stamp.json").as_posix()
    elif variant == "local-plus-drop":
        entry = next(item for item in entries if item.get("id") == CFG_LOCAL_CLIENT)
        entry["display_name"] = "合成·局部改名（不是本机观测）"
        document["entries"] = [item for item in entries
                               if item.get("id") != CFG_DROPPED_CLIENT]
    elif variant == "other-client":
        entry = next(item for item in entries if item.get("id") == CFG_DROPPED_CLIENT)
        entry["display_name"] = "合成·另一个客户端改名"
        entry["support_level"] = "synthetic-experimental"
    elif variant == "global":
        for index, item in enumerate(entries):
            item["display_name"] = f"合成·全局覆盖 {index}"
    elif variant == "promote":
        entry = next(item for item in entries if item.get("id") == CFG_LOCAL_CLIENT)
        entry["detection"]["evidence_state"] = "VERIFIED"
        entry["detection"]["mode"] = "live-session-readback"
    else:
        raise AssertionError("未知形态，夹具自身写错了: " + variant)
    registry.write_text(json.dumps(document, ensure_ascii=False, indent=2), encoding="utf-8")
    return document


def _cfg_snapshot(client) -> dict:
    status, snapshot = client.get("/api/work/observer/snapshot")
    assert status == 200, snapshot
    assert "adapterCapabilities" in snapshot, sorted(snapshot)
    return snapshot


def _cfg_cards(client) -> list:
    return _cfg_snapshot(client)["adapterCapabilities"]


def _cfg_card(cards: list, client_id: str) -> dict:
    return next(card for card in cards if card["clientId"] == client_id)


def _cfg_stripped(card: dict) -> dict:
    """去掉读时刻那一格：`observedAt` 每次答复都换，不是配置内容。"""
    return {key: value for key, value in card.items() if key != "observedAt"}


def _cfg_changed_clients(before: list, after: list) -> list:
    """两份答复之间，除读时刻外逐字段不同的客户端名（只比两边都在的条目）。

    「局部性」在这上面的可执行形式就是：这个列表恰等于我这次动过的那一个客户端。
    它返回清单而不是直接断言，是因为反证需要一个能变红的判断对象。
    """
    previous = {card["clientId"]: _cfg_stripped(card) for card in before}
    return sorted(card["clientId"] for card in after
                  if card["clientId"] in previous
                  and previous[card["clientId"]] != _cfg_stripped(card))


def _cfg_machine_path(value) -> bool:
    """解析后的值（含嵌套）里是否带本机绝对路径：盘符式（C 冒号加反斜杠或斜杠），或 UNC 共享名。

    比较的是 JSON 解析出来的字符串，不是对外卖出的转义文本——序列化会把一个反斜杠写成两个，
    拿台账里的路径去搜序列化文本会得到"没有"这个假结论（本节点的上一版就是这么错的）。
    """
    import re

    drive = re.compile(r"[A-Za-z]:[\\/]")
    if isinstance(value, str):
        return bool(drive.search(value)) or value.startswith(chr(92) * 2)
    if isinstance(value, dict):
        return any(_cfg_machine_path(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_cfg_machine_path(item) for item in value)
    return False


def _cfg_strings(node, collected: list) -> list:
    """答复里所有字符串值（含键名对应的嵌套），用于"这条路径有没有被端出去"的字面比对。"""
    if isinstance(node, str):
        collected.append(node)
    elif isinstance(node, dict):
        for key, value in node.items():
            collected.append(str(key))
            _cfg_strings(value, collected)
    elif isinstance(node, (list, tuple)):
        for value in node:
            _cfg_strings(value, collected)
    return collected


def _cfg_registry_machine_paths() -> list:
    """真实 adapter-registry 里"整格值就是一条本机绝对路径"的那些值。"""
    from domains.work.orchestration import resources

    import re
    rooted = re.compile(r"^(?:[A-Za-z]:[\\/]|[\\\\]{2})")
    document = json.loads(resources.config_path(CFG_REGISTRY_FILES[0])
                          .read_text(encoding="utf-8"))
    values = _cfg_strings(document, [])
    return sorted({text for text in values if rooted.match(text)})


def _cfg_path_spread_violations(cards: list) -> list:
    """带本机绝对路径的卡片，路径旁边必须仍是「未探测/未合格」。空清单才是不变量成立。

    规则来自投影自己的声明（adapter_capability_projection.py:16-19）：登记是声明不是探测，
    版本读回不是包哈希核验，所以一条路径只能待在路径格里，不能被写成合格/已连接的依据。
    """
    violations = []
    for card in cards:
        carriers = sorted(key for key, value in card.items() if _cfg_machine_path(value))
        unexpected = [key for key in carriers if key not in ("versionSource", "entryProbe")]
        if unexpected:
            violations.append({"clientId": card["clientId"],
                               "rule": "PATH_SITS_IN_A_NON_PATH_FIELD", "fields": unexpected})
        if "versionSource" not in carriers:
            continue
        if card["detectionEvidenceState"] not in ("UNVERIFIED", "UNKNOWN"):
            violations.append({"clientId": card["clientId"],
                               "rule": "READBACK_PATH_PROMOTED_TO_VERIFIED",
                               "value": card["detectionEvidenceState"]})
        if card["nativeStatus"] != "NOT_IMPLEMENTED":
            violations.append({"clientId": card["clientId"], "rule": "NATIVE_STATUS_PROMOTED",
                               "value": card["nativeStatus"]})
        registered = card["layers"][0]
        if (registered["layer"] != "REGISTERED" or registered["state"] != "MET"
                or registered["evidenceLevel"] != "SYNTHETIC"):
            violations.append({"clientId": card["clientId"],
                               "rule": "DECLARED_LAYER_CREDITED_AS_OBSERVED",
                               "value": registered})
        elif "声明" not in registered["reason"] or "探测" not in registered["reason"]:
            violations.append({"clientId": card["clientId"],
                               "rule": "DECLARED_LAYER_LOST_ITS_HONEST_REASON",
                               "value": registered["reason"]})
    return violations


def _cfg_control_request(operation: str, payload: dict | None = None, **overrides) -> dict:
    """一份满足已发布合同的控制请求（必填集抄 control-operation.schema.json:8）。"""
    document = {
        "schema_version": "worklab/control-operation/v1",
        "operation": operation,
        "project_id": "05l11-configuration-probe",
        "task_id": None,
        "revision": None,
        "attempt": None,
        "scope": {"boundaries": ["."], "granted_by": "owner-probe"},
        "expected_version": None,
        "idempotency_key": "05l11-" + operation + "-key",
        "actor": "05l11-probe-actor",
        "requested_at": "2026-11-01T09:00:00Z",
        "payload": payload or {},
    }
    document.update(overrides)
    return document


def test_local_profile_entry_restore_leaves_native_auth_and_global_environment(server,
                                                                               tmp_path,
                                                                               monkeypatch):
    """登记行 05#L11|configuration 的「局部性」与「不覆盖原生认证和全局环境」。

    证明：把 tmp 里那份合成台账的**一个** adapter profile 条目改掉（显示名 + 它自己的版本读回
    出处），`GET /api/work/observer/snapshot` 的 `adapterCapabilities` 里变的只有这一个客户端，
    其余客户端逐字段（除读时刻 `observedAt`）不变；连这同一张卡片上没动的字段也逐字段不变——
    变的就是 `displayName` 与 `versionSource` 两格。认证侧一格未动：`detectionEvidenceState`
    仍是 UNVERIFIED、`nativeStatus` 仍是 NOT_IMPLEMENTED、`protocolConformance` 三份协议状态
    不变、来自 capability-matrix 的原生归属默认值 `configOwnershipDefault` 与台账现读值一致
    （layer=USER_OVERLAY / mode=MANAGE / preserve_unknown=True，即"未知键保留不动"）。全局环境侧
    一格未动：`GET /api/environment` 整份答复与改前完全相等，`GET /api/v1/capabilities` 整份
    相等，`GET /api/work/control/descriptor` 除 `observed_at` 外 `authorization_record`（原生授权
    记录的可读状态、条数、失效数）与 `operations` 词表逐字段相等，且工作区里那份授权记录文件
    始终不存在（缺记录＝没有授权）。最后：真实 `config/` 整目录逐文件 sha256 与开始时相同。
    反证①：把"局部改写"做成"全局覆盖"（每个条目都改显示名），上面那条"只有 hermes 变了"
    立刻变红（变动清单变成全部客户端）；还原成只改一处，再读又是绿的。
    没证明：没有任何本机软件被探测、启动或连接；被改的出处路径与合成显示名都是夹具字符串；
    `config/environment-baseline.json` 那份全局环境台账被抄进 tmp 时已写成标记值，而三处答复里
    都查不到这个标记——这证明的是"答复不带它"，代码事实是**产品运行期没有任何读面消费这份台账**
    （现读：`backend/`、`domains/` 内无引用，只有 `tests/unified/test_v20_inrepo_evidence.py`
    读它做对账），所以登记行把它算进本族"受管配置"时，它的"不覆盖"只能以"没有读面、也没有
    写面"的形式成立，不是"有写面但被拦住"。
    """
    from domains.work.control import composition_root, control_service
    from domains.work.orchestration import resources

    registry_path = resources.adapter_registry_path()
    registry_bytes_before = registry_path.read_bytes()
    managed_config_before = _cfg_digest_tree(resources.config_dir())
    grants_path = server.local_root / control_service.TRUSTED_GRANTS_PATH

    cards_before = _cfg_cards(server.client)
    assert len(cards_before) >= 3, [card["clientId"] for card in cards_before]
    hermes_before = _cfg_card(cards_before, CFG_LOCAL_CLIENT)
    status, environment_before = server.client.get("/api/environment")
    assert status == 200, environment_before
    status, descriptor_before = server.client.get("/api/work/control/descriptor")
    assert status == 200, descriptor_before
    status, catalog_before = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog_before
    matrix = json.loads(resources.config_path("capability-matrix.json")
                        .read_text(encoding="utf-8"))
    matrix_ownership = next(entry["config_ownership_default"] for entry in matrix["clients"]
                            if entry.get("id") == CFG_LOCAL_CLIENT)
    assert grants_path.is_file() is False, str(grants_path)

    shadow = _cfg_shadow_root(tmp_path)
    _cfg_apply_registry_variant(shadow, tmp_path, "local")
    monkeypatch.setattr(composition_root, "_ROOT", shadow)

    cards_after = _cfg_cards(server.client)
    # —— 改一处，其余客户端一格没动 ——
    assert _cfg_changed_clients(cards_before, cards_after) == [CFG_LOCAL_CLIENT], \
        _cfg_changed_clients(cards_before, cards_after)
    hermes_after = _cfg_card(cards_after, CFG_LOCAL_CLIENT)
    changed_fields = sorted(key for key in hermes_after
                            if key != "observedAt" and hermes_after[key] != hermes_before[key])
    assert changed_fields == ["displayName", "versionSource"], changed_fields
    assert hermes_after["displayName"] == "合成·局部改名（不是本机观测）", hermes_after
    assert CFG_GLOBAL_ENV_MARKER not in hermes_after["versionSource"]

    # —— 原生认证相关字段保持原值（不是"读得通"，是逐字节没动）——
    for field in ("detectionEvidenceState", "detectionMode", "nativeStatus", "supportLevel",
                  "registryStatus", "writePolicy", "role", "risk", "declaredVersion",
                  "versionReadbackMethod", "versionObservedAt", "versionDrift", "entryProbe",
                  "protocolConformance", "configOwnershipDefault", "declaredOperations",
                  "matrixOperations", "operationsDrift", "layers"):
        assert hermes_after[field] == hermes_before[field], field
    assert hermes_after["detectionEvidenceState"] == "UNVERIFIED", hermes_after
    assert hermes_after["nativeStatus"] == "NOT_IMPLEMENTED", hermes_after
    assert hermes_after["configOwnershipDefault"] == matrix_ownership == \
        hermes_before["configOwnershipDefault"], hermes_after["configOwnershipDefault"]
    assert hermes_after["configOwnershipDefault"]["preserve_unknown"] is True

    status, descriptor_after = server.client.get("/api/work/control/descriptor")
    assert status == 200, descriptor_after
    assert descriptor_after["authorization_record"] == descriptor_before["authorization_record"]
    assert descriptor_after["operations"] == descriptor_before["operations"]
    assert descriptor_after["evidence_ceiling"] == descriptor_before["evidence_ceiling"]
    assert descriptor_after["transport"] == descriptor_before["transport"] == "loopback-only"
    assert descriptor_after["authorization_record"]["grants"] == 0, descriptor_after
    assert descriptor_after["authorization_record"]["path"] == control_service.TRUSTED_GRANTS_PATH

    # —— 全局环境字段保持原值 ——
    status, environment_after = server.client.get("/api/environment")
    assert status == 200, environment_after
    assert environment_after == environment_before, \
        (sorted(environment_after), sorted(environment_before))
    assert environment_after["agent_profile"]["writable"] is False, environment_after
    assert environment_after["write_trace"] == "NOT_EXECUTED"
    status, catalog_after = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog_after
    assert catalog_after == catalog_before, "局部配置改写改到了能力目录答复上"

    # —— 全局环境台账：标记没有出现在任何答复里（这条读面不存在）——
    snapshot_after = _cfg_snapshot(server.client)
    for name, body in (("environment", environment_after), ("catalog", catalog_after),
                       ("snapshot", snapshot_after), ("descriptor", descriptor_after)):
        assert CFG_GLOBAL_ENV_MARKER not in json.dumps(body, ensure_ascii=False), name

    # —— 反证①：局部性做成全局覆盖 → 上面那条判断必须红；还原 → 复绿 ——
    _cfg_apply_registry_variant(shadow, tmp_path, "global")
    overwritten = _cfg_cards(server.client)
    globally_changed = _cfg_changed_clients(cards_before, overwritten)
    assert globally_changed != [CFG_LOCAL_CLIENT], globally_changed
    assert len(globally_changed) == len(overwritten), (globally_changed, len(overwritten))
    _cfg_apply_registry_variant(shadow, tmp_path, "local")
    assert _cfg_changed_clients(cards_before, _cfg_cards(server.client)) == [CFG_LOCAL_CLIENT]

    # —— 真实受管配置面与授权记录没有被写 ——
    assert registry_path.read_bytes() == registry_bytes_before
    assert _cfg_digest_tree(resources.config_dir()) == managed_config_before
    assert grants_path.is_file() is False, str(grants_path)


def test_no_write_entry_reaches_managed_config_native_auth_or_global_environment(server,
                                                                                 monkeypatch):
    """登记行 05#L11|configuration 的「不覆盖」：写面存在与否，按代码真实形状钉。

    结论是"存在计划面、不存在写面"，三层都要断言，缺一层就会把这句话读成它没有的意思：
    (1) 操作枚举封闭：`packages/contracts/schemas/workflow/control-operation.schema.json` 的
        enum 与 `control_service.OPERATIONS` 的键集现读相等；其中 `config.discover` /
        `config.apply` / `config.readback` / `config.rollback` 四条 `implemented=False`，逐条答
        `NOT_IMPLEMENTED` + 各自的具名 code（READ_LANDED_ELSEWHERE / TARGET_NOT_AUTHORISED /
        NO_WRITE_TO_READ_BACK / NO_RECOVERY_HANDLE），`receipt=None`、`readback=None`、
        `evidence_level=NO_EVIDENCE`。所有 EXTERNAL_MUTATION / DESTRUCTIVE 类操作都未实现，
        实现集恰为 {work-unit.create, work-unit.materialize, config.diff}。
    (2) 唯一实现的配置动词 `config.diff` 是计划面：合法目标（合同 JSON）答 `PLANNED` +
        `readback.plan_only=True` + `written=False`，值不外泄（`before` 写
        "<read-only: value not projected>"），只回一个"这个键路径存在吗"的判断；对 `.py`
        这种非映射文档它回 `present_before=None` + `presenceBasis=DOCUMENT_UNPARSEABLE`，
        不降级成子串搜索。目标拦截四层：`config/adapter-registry.json` → `REFUSED`
        `GATE_DENIED`（"target is on the forbidden list"，来自 `FORBIDDEN_TARGETS`:108 里的
        `config/` 前缀，经 `PermissionGate(Policy(forbidden_paths=...))`:323-327）；原生认证类
        名字 `.env` / `credentials.json` / `auth_store.json` → `NEEDS_HUMAN` `GATE_NEEDS_HUMAN`
        （risk CRITICAL ≥ 策略阈值 HIGH）；`docs/` 下的副本 → `REFUSED` `TARGET_SENSITIVE`；
        仓库外与缺输入 → `TARGET_OUT_OF_PROJECT` / `DIFF_INPUT_INCOMPLETE`。
    (3) HTTP 面到不了写：`POST /api/work/control/operations` 带一份完全合合同的文档仍是
        `400 INVALID_PROJECT_FIELDS` 且答复体里没有 `reason_code`——`control_execute` 的
        `handler.body(fields={})` 在 `plane.execute` 之前就把带键的请求体拒了
        （`backend/core/work_surfaces.py:319`），所以这条被 surface-map 称作
        `control_write_entry` 的入口在本统一进程里不是可用的配置写入口；Observer 只读面
        POST/PUT/PATCH/DELETE 一律 `405 OBSERVER_IS_READ_ONLY` 并把拒绝记进工作区台账；
        整张路由表（`backend.v1.V1_ROUTES`，含 WORK 面）里非 GET 的方法没有任何一条的
        pattern 提到 config。原生授权记录 `control-trusted-grants.json` 与全局环境台账
        `<workspace>/.project/paths.json` 全程保持不存在，`/api/environment` 仍答
        `agent_profile.writable=False`、`sources.project_local_root=default`。
    反证②：把 `FORBIDDEN_TARGETS` 里的 `config/` 前缀摘掉，另建一个平面（同一个 store，
    不落回执、不指授权记录）再发同一条 `config.diff`——它立刻从 `GATE_DENIED` 变成 `PLANNED`，
    证明拦住受管配置的正是那一行声明；同时原平面（策略在构造时绑定）仍答 `GATE_DENIED`，
    还原声明后新建平面也重新被拦。全程真实 `config/` 逐文件摘要不变。
    没证明：`config.apply` 被授权后会不会写——本仓没有它的实现分支，所以这一条不是"实现被
    绕过"而是"实现不存在"；没有真实宿主、真实客户端配置或真实凭证被读过；合同要求的
    `requested_at` 是夹具常量；`UNKNOWN_OPERATION`（:511）在合同文档面前不可达（封闭枚举
    先拒），节点把这件事如实钉成 `INVALID_REQUEST` 而不是假装能走到那条 code。
    """
    from domains.work.control import control_service
    from backend.core import work_surfaces
    from domains.work.orchestration import resources

    plane = work_surfaces.control_plane(server.api)
    grants_path = server.local_root / control_service.TRUSTED_GRANTS_PATH
    receipt_path = server.local_root / control_service.RECEIPTS_PATH
    paths_ledger = server.workspace / ".project" / "paths.json"
    managed_config_before = _cfg_digest_tree(resources.config_dir())

    # (1) 枚举封闭 + 未实现的配置写/读回/回滚动词
    contract = json.loads(control_service.REQUEST_CONTRACT.read_text(encoding="utf-8"))
    assert sorted(contract["properties"]["operation"]["enum"]) == \
        sorted(control_service.OPERATIONS), (contract["properties"]["operation"]["enum"],
                                             sorted(control_service.OPERATIONS))
    implemented = sorted(name for name, spec in control_service.OPERATIONS.items()
                         if spec.implemented)
    assert implemented == ["config.diff", "work-unit.create", "work-unit.materialize"], \
        implemented
    for name, code in (("config.discover", "READ_LANDED_ELSEWHERE"),
                       ("config.apply", "TARGET_NOT_AUTHORISED"),
                       ("config.readback", "NO_WRITE_TO_READ_BACK"),
                       ("config.rollback", "NO_RECOVERY_HANDLE")):
        answer = plane.execute(_cfg_control_request(
            name, {"target_file": CFG_CONTRACT_TARGET, "field": "properties"}))
        assert answer["status"] == "NOT_IMPLEMENTED", answer
        assert answer["reason_code"] == code, answer
        assert answer["receipt"] is None and answer["readback"] is None, answer
        assert answer["evidence_level"] == "NO_EVIDENCE", answer
        assert answer["next_action"], answer
    assert not [spec for spec in control_service.OPERATIONS.values()
                if spec.implemented and spec.action.value in ("EXTERNAL_MUTATION", "DESTRUCTIVE")], \
        [(spec.operation, spec.action.value) for spec in control_service.OPERATIONS.values()]

    # (2) 唯一的实现体是计划面，且它被拦在受管配置、原生认证与仓库之外
    planned = plane.execute(_cfg_control_request(
        "config.diff", {"target_file": CFG_CONTRACT_TARGET, "field": "properties.entries",
                        "value": "synthetic"}))
    assert planned["status"] == "PLANNED", planned
    assert planned["reason_code"] == "PLAN_COMPUTED", planned
    assert planned["readback"]["plan_only"] is True and planned["readback"]["written"] is False
    assert planned["readback"]["target"] == CFG_CONTRACT_TARGET, planned["readback"]
    assert planned["readback"]["changes"] == [{
        "field": "properties.entries", "before": "<read-only: value not projected>",
        "after_declared": True, "present_before": True, "presenceBasis": "KEY_PATH_RESOLVES"}], \
        planned["readback"]["changes"]
    assert planned["receipt"] is None and planned["evidence_level"] == "SYNTHETIC", planned

    non_mapping = plane.execute(_cfg_control_request(
        "config.diff", {"target_file": "domains/work/control/control_service.py",
                        "field": "OPERATIONS"}))
    assert non_mapping["status"] == "PLANNED", non_mapping
    assert non_mapping["readback"]["changes"][0]["presenceBasis"] == "DOCUMENT_UNPARSEABLE", \
        non_mapping["readback"]
    assert non_mapping["readback"]["changes"][0]["present_before"] is None

    def refusal(operation: str, payload: dict):
        answer = plane.execute(_cfg_control_request(operation, payload))
        return answer["status"], answer["reason_code"]

    assert refusal("config.diff", {"target_file": "config/adapter-registry.json",
                                   "field": "entries"}) == ("REFUSED", "GATE_DENIED")
    for auth_named in (".env", "credentials.json", "auth_store.json"):
        assert refusal("config.diff", {"target_file": auth_named, "field": "a"}) == \
            ("NEEDS_HUMAN", "GATE_NEEDS_HUMAN"), auth_named
    critical = plane.execute(_cfg_control_request("config.diff", {"target_file": ".env",
                                                                 "field": "a"}))
    assert "CRITICAL" in critical["reason"], critical["reason"]
    assert refusal("config.diff", {"target_file": "docs/x.json", "field": "a"}) == \
        ("REFUSED", "TARGET_SENSITIVE")
    assert refusal("config.diff", {"target_file": "../outside/thing.json", "field": "a"}) == \
        ("REFUSED", "TARGET_OUT_OF_PROJECT")
    assert refusal("config.diff", {"target_file": CFG_CONTRACT_TARGET}) == \
        ("REFUSED", "DIFF_INPUT_INCOMPLETE")
    invented = plane.execute(_cfg_control_request("credentials.rotate", {}))
    assert invented["reason_code"] == "INVALID_REQUEST", invented
    assert "is not one of" in invented["reason"], invented["reason"]

    # (3) HTTP 面：声明的写入口不可用；Observer 写方法只有拒绝处理器；路由表无 config 写面
    status, body = server.client.post("/api/work/control/operations",
                                      _cfg_control_request("config.apply",
                                                           {"target_file": "config/"
                                                                            "adapter-registry.json"}))
    assert status == 400 and body.get("error") == "INVALID_PROJECT_FIELDS", (status, body)
    assert "reason_code" not in body, body
    for method in ("POST", "PUT", "PATCH", "DELETE"):
        status, refused = server.client.request(method, "/api/work/observer/snapshot")
        assert status == 405, (method, status, refused)
        assert refused["reason_code"] == "OBSERVER_IS_READ_ONLY", (method, refused)
        assert refused["method"] == method and refused["path"] == "/api/work/observer/snapshot"
    status, recorded = server.client.get("/api/work/observer/refusals")
    assert status == 200 and recorded["count"] == 4, recorded
    assert recorded["path"] == str(server.local_root / "observer-write-refusals.jsonl")

    from backend.v1 import V1_ROUTES

    writes = sorted({(route.method, route.pattern) for route in V1_ROUTES if route.method != "GET"})
    assert any(pattern == "/api/work/control/operations" for _, pattern in writes), writes
    assert [pair for pair in writes if "config" in pair[1].lower()] == [], writes
    status, surface_map = server.client.get("/api/work/surface-map")
    assert status == 200, surface_map
    assert surface_map["control_write_entry"] == "POST /api/work/control/operations"
    assert "refused" in surface_map["observer_writes"], surface_map["observer_writes"]

    # 原生认证记录与全局环境台账：没有任何入口把它们写出来
    assert grants_path.is_file() is False, str(grants_path)
    assert paths_ledger.is_file() is False, str(paths_ledger)
    status, environment = server.client.get("/api/environment")
    assert status == 200, environment
    assert environment["agent_profile"]["writable"] is False, environment["agent_profile"]
    assert environment["agent_profile"]["status"] == "PRIVATE_NOT_INSPECTED"
    assert environment["write_trace"] == "NOT_EXECUTED"
    assert environment["sources"] == {"project_local_root": "default"}, environment["sources"]
    assert _cfg_digest_tree(resources.config_dir()) == managed_config_before

    # —— 反证②：拦住的只是 FORBIDDEN_TARGETS 那一行声明 ——
    assert "config/" in control_service.FORBIDDEN_TARGETS, control_service.FORBIDDEN_TARGETS
    monkeypatch.setattr(control_service, "FORBIDDEN_TARGETS",
                        tuple(item for item in control_service.FORBIDDEN_TARGETS
                              if item != "config/"))
    unguarded = control_service.ControlPlane(server.work.store,
                                             project_root=plane.project_root,
                                             evidence_ceiling=plane.evidence_ceiling,
                                             receipts_path=None, grants_path=None)
    naked = unguarded.execute(_cfg_control_request(
        "config.diff", {"target_file": "config/adapter-registry.json", "field": "entries"}))
    assert naked["status"] == "PLANNED" and naked["reason_code"] == "PLAN_COMPUTED", naked
    assert naked["readback"]["written"] is False, naked["readback"]
    still_gated = plane.execute(_cfg_control_request(
        "config.diff", {"target_file": "config/adapter-registry.json", "field": "entries"}))
    assert (still_gated["status"], still_gated["reason_code"]) == ("REFUSED", "GATE_DENIED")
    monkeypatch.undo()
    regated = control_service.ControlPlane(server.work.store, project_root=plane.project_root,
                                          evidence_ceiling=plane.evidence_ceiling,
                                          receipts_path=None, grants_path=None)
    answer = regated.execute(_cfg_control_request(
        "config.diff", {"target_file": "config/adapter-registry.json", "field": "entries"}))
    assert (answer["status"], answer["reason_code"]) == ("REFUSED", "GATE_DENIED"), answer
    assert _cfg_digest_tree(resources.config_dir()) == managed_config_before
    assert grants_path.is_file() is False and receipt_path.is_file() is False


def test_managed_config_restore_follows_the_file_and_lands_no_new_persistent_write(server,
                                                                                   tmp_path,
                                                                                   monkeypatch):
    """登记行 05#L11|configuration 的「可恢复」：答复随受管文件变，且恢复不落新的持久写入。

    证明：`adapterCapabilities` 每次请求都现读 `<root>/config/adapter-registry.json`
    （`_adapter_capability_rows`:840 → `load_inputs`:409-414），没有第二副本。四轮同进程读：
    逐字节照抄的合成副本 → 与真实台账同样的卡片集（10 条、除读时刻外逐字段相同，说明这一致
    是文件内容带来的，不是缓存带来的）；换成"改一个 profile + 删一个条目"的合法内容 → 卡片
    少一条、只有 hermes 变；把原文件重新抄回去 → 答复回到基线（这才叫可恢复）；第四轮换成了
    只动 cursor 的另一份合法内容 → 条目数回到基线、跟着变的只有 cursor。恢复过程中工作区
    （含 `.project-local` 的台账与 canonical store 文件）逐文件 sha256 与名单集合完全不变，
    真实 `config/` 整目录也不变，即"恢复"没有产生任何新的持久写入。
    同时钉住登记行"当前实现位置"的实情：`GET /api/v1/capabilities` 的四轮答复**逐字节相同**
    ——`capabilities.derive_catalog`:97-128 只遍历 `CATALOG_SPEC` 声明加资格台账，从不打开
    adapter-registry.json，那一格 `source_refs` 里的 `work:config/adapter-registry.json` 只是
    引用字符串。所以"从受管配置现读出的目录、答复随文件改变"这条验收在代码里成立的face是
    WORK 快照的 `adapterCapabilities`，不是能力目录；登记把位置写在 capabilities.py:97 与代码
    不符，节点按代码真实行为断言，不为绿而改产品。
    反证③：在 `load_inputs` 上装一个"第一次读就记住"的缓存（模拟第二副本），换文件后答复不再
    跟着变（变动清单变空、条目数回到 10）——上面那条"随文件变"的判断当场变红；卸掉缓存复绿。
    没证明：卡片里出现的版本串、出处路径都是台账里的既有声明或夹具字符串，没有本机软件被探测；
    `observedAt` 每次答复都换，已从比较里排除；没有真实宿主/真人/E3/E4 证据；恢复只测读侧
    一致性，写入与回滚本身在本仓没有实现分支（见上一节点）。
    """
    from domains.work.control import composition_root
    from domains.work.orchestration import adapter_capability_projection as acp
    from domains.work.orchestration import resources

    cards_before = _cfg_cards(server.client)
    assert len(cards_before) >= 3, [card["clientId"] for card in cards_before]
    baseline_ids = [card["clientId"] for card in cards_before]
    assert CFG_LOCAL_CLIENT in baseline_ids and CFG_DROPPED_CLIENT in baseline_ids, baseline_ids
    managed_config_before = _cfg_digest_tree(resources.config_dir())
    workspace_before = _cfg_digest_tree(server.workspace)

    shadow = _cfg_shadow_root(tmp_path)
    monkeypatch.setattr(composition_root, "_ROOT", shadow)
    verbatim = _cfg_cards(server.client)
    assert [card["clientId"] for card in verbatim] == baseline_ids, verbatim
    assert _cfg_changed_clients(cards_before, verbatim) == [], _cfg_changed_clients(cards_before,
                                                                                    verbatim)

    _cfg_apply_registry_variant(shadow, tmp_path, "local-plus-drop")
    edited = _cfg_cards(server.client)
    assert [card["clientId"] for card in edited] == \
        [cid for cid in baseline_ids if cid != CFG_DROPPED_CLIENT], edited
    assert _cfg_changed_clients(cards_before, edited) == [CFG_LOCAL_CLIENT]

    _cfg_apply_registry_variant(shadow, tmp_path, "restore")
    restored = _cfg_cards(server.client)
    assert [card["clientId"] for card in restored] == baseline_ids, restored
    assert _cfg_changed_clients(cards_before, restored) == [], _cfg_changed_clients(cards_before,
                                                                                    restored)

    # —— 反证③：装一个"第二副本"，答复就不再跟着文件走 ——
    real_load_inputs = acp.load_inputs
    memo: dict = {}

    def caching_load_inputs(root):
        if "triple" not in memo:
            memo["triple"] = real_load_inputs(root)
        return memo["triple"]

    acp.load_inputs = caching_load_inputs
    try:
        # 先用当前（已还原的）那份把缓存填满，再换文件：缓存版才会露出"第二副本"的形状
        warmed = _cfg_cards(server.client)
        assert _cfg_changed_clients(cards_before, warmed) == [], warmed
        _cfg_apply_registry_variant(shadow, tmp_path, "local-plus-drop")
        cached = _cfg_cards(server.client)
        assert [card["clientId"] for card in cached] == baseline_ids, cached
        assert _cfg_changed_clients(cards_before, cached) == [], cached
        assert _cfg_card(cached, CFG_LOCAL_CLIENT)["displayName"] == \
            _cfg_card(cards_before, CFG_LOCAL_CLIENT)["displayName"]
    finally:
        acp.load_inputs = real_load_inputs

    # 卸掉缓存：同一份被换过的文件立刻被现读出来
    following = _cfg_cards(server.client)
    assert [card["clientId"] for card in following] == \
        [cid for cid in baseline_ids if cid != CFG_DROPPED_CLIENT], following
    assert _cfg_changed_clients(cards_before, following) == [CFG_LOCAL_CLIENT]

    # 再换一份合法内容：这一份只动 cursor，跟着变的也只有它（hermes 回到原值）
    _cfg_apply_registry_variant(shadow, tmp_path, "other-client")
    third = _cfg_cards(server.client)
    assert [card["clientId"] for card in third] == baseline_ids, third
    assert _cfg_changed_clients(cards_before, third) == [CFG_DROPPED_CLIENT], \
        _cfg_changed_clients(cards_before, third)
    assert _cfg_card(third, CFG_DROPPED_CLIENT)["supportLevel"] == "synthetic-experimental"
    assert _cfg_card(third, CFG_LOCAL_CLIENT)["displayName"] == \
        _cfg_card(cards_before, CFG_LOCAL_CLIENT)["displayName"]

    # —— 能力目录不是这条读链：台账换了它一个字都不动 ——
    catalog_rounds = [server.client.get("/api/v1/capabilities")[1] for _ in range(2)]
    assert catalog_rounds[0] == catalog_rounds[1]
    executors = _cfg_catalog_row(catalog_rounds[0], "work.executors")
    assert executors["source_refs"] == ["work:config/adapter-registry.json"], executors
    assert executors["declared_by"].startswith("backend.core.capabilities.CATALOG_SPEC"), executors

    # —— 恢复没有落新的持久写入 ——
    assert _cfg_digest_tree(resources.config_dir()) == managed_config_before
    assert _cfg_digest_tree(server.workspace) == workspace_before, \
        (sorted(set(_cfg_digest_tree(server.workspace)) ^ set(workspace_before)),
         {key: value for key, value in _cfg_digest_tree(server.workspace).items()
          if workspace_before.get(key) != value})


def _cfg_catalog_row(body: dict, capability_id: str) -> dict:
    return next(row for row in body["capabilities"] if row["capability_id"] == capability_id)


def test_machine_absolute_paths_travel_as_paths_not_as_verified_evidence(server, tmp_path,
                                                                        monkeypatch):
    """登记行 05#L11|configuration 的「本机绝对路径不扩散」。

    事实先摆明：`config/adapter-registry.json` 里确实带本机绝对路径（整格值就是一条路径的那格是
    hermes 的 `provenance.version_readback.source`，一台机器上的 install-stamp 位置；另有多条
    note/prose 里写死过测量路径）。节点的断言不是"把路径删掉"，而是它对外答复时的身份：
    (a) 上面那条台账路径没有出现在 `GET /api/v1/capabilities`、`/api/v1/connections`、
        `/api/v1/tools`、`/api/work/control/descriptor`、`/api/work/surface-map` 任何一面的
        字符串值里（逐格比对解析后的值——序列化文本会把一个反斜杠写成两个，拿它比对出来的
        "没有"是假的，节点第一次就是这么错的）。这五面里确实存在的盘符串只有两类，都不是这份
        台账的路径：本地读探测记下的工作库位置，和控制面自报的 `project_root`。而能力目录里
        指向这份台账的那一格 `work.executors` 恰恰 `probe=None` + `can_invoke=False` +
        `qualification=NOT_PROBED` + `connection_state=NOT_PROBED`，`source_refs` 只有仓内相对
        引用 `work:config/adapter-registry.json`；带路径的目录行只允许出现在 `probe` 这一格里，
        且那一格自己写明 `scope=local_read`、`command=backend.core.probes.run_read_probes
        (read-only)`。连接面的 `work-adapters` 行同样答 `state=NOT_PROBED`、
        `authorization=NOT_GRANTED`、`evidence=None`、`connection_observed_by_probe=None`。
    (b) 唯一把这些路径端出去的产品答复是 WORK 快照的 `adapterCapabilities`，而路径只待在
        路径格里（本轮全量卡片里带盘符的键集合恰为 {"versionSource"}），带路径的那张卡片旁边
        必须仍是未探测/未合格的词：`detectionEvidenceState=UNVERIFIED`、
        `nativeStatus=NOT_IMPLEMENTED`、七层里唯一 MET 的是 REGISTERED 且
        `evidenceLevel=SYNTHETIC`、reason 自己写明"是声明不是探测"；整份快照里出现的
        `*VERIFIED` 词只有 UNVERIFIED 与 STATIC_UNVERIFIED，没有裸 VERIFIED。
    反证④：在 tmp 的合成台账里把 hermes 的 `detection.evidence_state` 顶成 VERIFIED、mode 写成
    live-session-readback——上面的不变量清单立刻非空（具名规则
    READBACK_PATH_PROMOTED_TO_VERIFIED），且卡片答复确实把 VERIFIED 端了出去（证明这条判断
    不是空转）；把该条目逐字节还原，清单重新为空。
    没证明：路径本身对不对、那台机器上装了什么——节点只约束它作为"依据"的资格；`/api/environment`
    里的 `C:/…` 是本工作区自己的根路径（全局环境答复的本分），不在本节点的禁止清单里，已按面
    分开断言；没有真实宿主探测、没有真人验收；`entryProbe` 本轮恒为 None（受管探测记录不在仓内），
    所以"路径可以出现在 entryProbe 的 argv 里"这一格只是把未来的合法形状留着，不是宣称它已发生。
    """
    import re

    from domains.work.control import composition_root
    from domains.work.orchestration import resources

    registry_bytes_before = resources.adapter_registry_path().read_bytes()
    managed_config_before = _cfg_digest_tree(resources.config_dir())

    # 台账里"整格就是一条本机绝对路径"的值——先证明这个集合非空，下面的比对才不是空转
    machine_paths = _cfg_registry_machine_paths()
    assert machine_paths, "adapter-registry 里应至少有一格整值就是本机绝对路径"
    bodies: dict = {}
    for path in ("/api/v1/capabilities", "/api/v1/connections", "/api/v1/tools",
                 "/api/work/control/descriptor", "/api/work/surface-map"):
        status, body = server.client.get(path)
        assert status == 200, (path, body)
        bodies[path] = body
        values = _cfg_strings(body, [])
        leaked = sorted(item for item in machine_paths
                        if any(item in value for value in values))
        assert leaked == [], (path, leaked)

    status, catalog = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog
    carriers = sorted({key for row in catalog["capabilities"] for key, value in row.items()
                       if _cfg_machine_path(value)})
    assert carriers == ["probe"], carriers          # 路径只在探测格里，不在判决格里
    probed = [row for row in catalog["capabilities"] if _cfg_machine_path(row.get("probe"))]
    assert probed and all(row["probe"]["scope"] == "local_read" for row in probed), \
        [(row["capability_id"], row["probe"]["scope"]) for row in probed]
    assert all(row["probe"]["command"] == "backend.core.probes.run_read_probes (read-only)"
               for row in probed), {row["probe"]["command"] for row in probed}
    assert all(row["qualification"] in ("VERIFIED", "NOT_VERIFIED", "EXPIRED")
               for row in probed), [(row["capability_id"], row["qualification"])
                                    for row in probed]
    executors = _cfg_catalog_row(catalog, "work.executors")
    assert executors["source_refs"] == ["work:config/adapter-registry.json"], executors
    assert executors["qualification"] == "NOT_PROBED" == executors["connection_state"], executors
    assert executors["can_invoke"] is False and executors["probe"] is None, executors
    assert any("qualification" in reason for reason in executors["unavailable_reasons"])
    status, connections = server.client.get("/api/v1/connections")
    adapters = next(row for row in connections["connections"]
                    if row["connection_id"] == "work-adapters")
    assert adapters["tool_ref"] == "config/adapter-registry.json", adapters
    assert adapters["state"] == "NOT_PROBED" and adapters["authorization"] == "NOT_GRANTED"
    assert adapters["evidence"] is None and adapters["connection_observed_by_probe"] is None

    snapshot = _cfg_snapshot(server.client)
    cards = snapshot["adapterCapabilities"]
    card_carriers = sorted({key for card in cards for key, value in card.items()
                            if _cfg_machine_path(value)})
    assert card_carriers == ["versionSource"], card_carriers
    with_path = [card["clientId"] for card in cards if _cfg_machine_path(card.get("versionSource"))]
    assert with_path, "本轮台账里应至少有一条带本机路径的读回出处，否则下面的邻接断言是空转"
    assert _cfg_path_spread_violations(cards) == [], _cfg_path_spread_violations(cards)
    for card in cards:
        if card["clientId"] not in with_path:
            assert card.get("versionSource") in (None, "") or not _cfg_machine_path(
                card["versionSource"]), card["clientId"]
    hermes = _cfg_card(cards, CFG_LOCAL_CLIENT)
    assert hermes["detectionEvidenceState"] == "UNVERIFIED", hermes
    assert hermes["nativeStatus"] == "NOT_IMPLEMENTED", hermes
    met = [layer["layer"] for layer in hermes["layers"] if layer["state"] == "MET"]
    assert met == ["REGISTERED"], met
    assert hermes["layers"][0]["evidenceLevel"] == "SYNTHETIC", hermes["layers"][0]
    assert "声明" in hermes["layers"][0]["reason"] and "探测" in hermes["layers"][0]["reason"]
    assert re.sub(r"UNVERIFIED|STATIC_UNVERIFIED", "", json.dumps(snapshot,
                                                                  ensure_ascii=False)
                  ).count("VERIFIED") == 0, "快照里出现了没有被 UN/STATIC_UN 前缀保护的 VERIFIED"

    # —— 反证④：把未探测顶成已验证 ——
    shadow = _cfg_shadow_root(tmp_path)
    _cfg_apply_registry_variant(shadow, tmp_path, "promote")
    monkeypatch.setattr(composition_root, "_ROOT", shadow)
    promoted = _cfg_cards(server.client)
    assert _cfg_card(promoted, CFG_LOCAL_CLIENT)["detectionEvidenceState"] == "VERIFIED"
    violations = _cfg_path_spread_violations(promoted)
    assert violations and {item["rule"] for item in violations} == \
        {"READBACK_PATH_PROMOTED_TO_VERIFIED"}, violations
    _cfg_apply_registry_variant(shadow, tmp_path, "restore")
    assert _cfg_path_spread_violations(_cfg_cards(server.client)) == []

    assert resources.adapter_registry_path().read_bytes() == registry_bytes_before
    assert _cfg_digest_tree(resources.config_dir()) == managed_config_before
