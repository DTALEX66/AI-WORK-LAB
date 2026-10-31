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
    等于台账里该条自己的值，qualified_local、default_enabled_true、weights_recorded 是从台账
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
