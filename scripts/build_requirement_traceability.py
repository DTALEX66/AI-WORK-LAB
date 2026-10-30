# SPDX-License-Identifier: MIT
"""Requirement traceability: every handoff-table row gets a *mechanically checked* disposition.

Why this exists
---------------
``AI-WORK-LAB_HANDOFF_20261029/`` ships four tables that together describe the whole
product promise -- 56 legacy UI entries (04), 30 capability families (05), 25 explicit
requirements and preferences (11) and 15 proposed API endpoints (08). The closure
documents only ever cited the 198 WORK gap rows and the per-file source coverage, so
those four tables had **no** reconciliation against the code: a reader could not tell
whether "PROPOSED_NOT_IMPLEMENTED" was still true, partly true, or simply stale.

This builder makes every row carry a verifiable disposition. It is fail-closed by
construction, not by wording:

* a ``file:line`` location is read from disk -- the path must exist, the line must
  exist, and the line must be non-blank;
* a route location must match a **live** entry imported from
  ``backend.v1.V1_ROUTES`` (75 routes, including the 49 WORK-surface routes) or
  ``design_lab.http_service.ROUTES`` (89 compatibility routes) -- never prose;
* a test citation resolves only when the file exists **and** declares that test name;
* an evidence citation resolves only when the JSON exists under
  ``.project-local/audit/20261030-qoder-ed9037/`` **and** the dotted key path is present;
* ``DEFERRED_P2``/``DEFERRED_P3`` must be backed by the row's own 分期 text or by a task
  id that ``09_任务分期与验收.json`` really records with that phase;
* ``EXCLUDED_BY_OWNER`` must quote, verbatim, a decision string that is present in the
  source row itself -- an exclusion invented by this script downgrades to ``GAP``;
* ``PARTIAL`` must name its missing part with the marker ``缺口：``, otherwise it is not
  a partial, it is a gap;
* ``IMPLEMENTED_VERIFIED`` is reachable only when the location *and* every evidence
  citation resolve. Code that exists but is not covered by a test/探测 stays
  ``IMPLEMENTED_UNVERIFIED``.

A status is therefore never inherited from a document saying "done": the docstring of
this file, ``docs/CODEX-AUDIT-ENTRY.md`` and the frozen handoff tables are all inputs to
be checked, never authorities to be copied.

The authored part is the judgement in ``basis`` (which anchor represents this promise,
what the cited test actually proves, what is still missing). The machine part is whether
those anchors resolve. Both are written into the same column so a reader can tell them
apart: ``[判定]`` prefixes the authored judgement, ``[机验]`` the resolved result.

Registers written (all four are NEW files; nothing existing is modified):
``migration/ui-entry-disposition.csv``,
``migration/capability-family-register.csv``,
``migration/requirement-traceability.csv``,
``migration/api-contract-check.json``.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
HANDOFF = REPO_ROOT / "AI-WORK-LAB_HANDOFF_20261029"
UI_TABLE = HANDOFF / "04_原界面入口映射.csv"
FAMILY_TABLE = HANDOFF / "05_能力族分期.csv"
REQUIREMENT_TABLE = HANDOFF / "11_需求追溯.csv"
PROTOCOL_TABLE = HANDOFF / "08_前后端交接约定.json"
PHASING_TABLE = HANDOFF / "09_任务分期与验收.json"
OUT_DIR = REPO_ROOT / "migration"
EVIDENCE_DIR = REPO_ROOT / ".project-local" / "audit" / "20261030-qoder-ed9037"

#: The closed status vocabulary. Nothing outside this tuple may be written.
STATUSES = (
    "IMPLEMENTED_VERIFIED",
    "IMPLEMENTED_UNVERIFIED",
    "PARTIAL",
    "GAP",
    "DEFERRED_P2",
    "DEFERRED_P3",
    "EXCLUDED_BY_OWNER",
)

#: Sentinels used inside the claim tables below.
ABSENT = "ABSENT"          # no implementation location exists for this promise
NO_EVIDENCE = "NONE"       # nothing measures this row
PARTIAL_MARKER = "缺口："   # a PARTIAL row must name what is missing

LOCATION_LINE_RE = re.compile(r"^(?P<path>.+):(?P<line>\d+)$")
PHASE_TASK_RE = re.compile(r"\bL(\d{2})\b")


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# --------------------------------------------------------------------------
# live route tables (imported, never grepped)
# --------------------------------------------------------------------------

_ROUTE_CACHE = None


def live_routes() -> dict[tuple[str, str], dict]:
    """{(method, pattern): {"table": ..., "handler": ...}} from the two live tables."""
    global _ROUTE_CACHE
    if _ROUTE_CACHE is None:
        for entry in (str(REPO_ROOT), str(REPO_ROOT / "domains" / "design")):
            if entry not in sys.path:
                sys.path.insert(0, entry)
        from backend.v1 import V1_ROUTES
        from design_lab.http_service import ROUTES as COMPAT_ROUTES

        table: dict[tuple[str, str], dict] = {}
        for route in V1_ROUTES:
            table[(route.method, route.pattern)] = {
                "table": "backend.v1.V1_ROUTES", "handler": route.action}
        for route in COMPAT_ROUTES:
            table.setdefault((route.method, route.pattern), {
                "table": "design_lab.http_service.ROUTES", "handler": route.action})
        table[("__counts__", "__counts__")] = {
            "v1_routes": len(V1_ROUTES), "compat_routes": len(COMPAT_ROUTES)}
        _ROUTE_CACHE = table
    return _ROUTE_CACHE


def route_counts() -> tuple[int, int]:
    entry = live_routes()[("__counts__", "__counts__")]
    return int(entry["v1_routes"]), int(entry["compat_routes"])


def find_definition(name: str, relative: str) -> str | None:
    """``relative`` -> ``file:line`` of the first ``def name``/``class name`` header."""
    path = REPO_ROOT / relative
    if not path.is_file():
        return None
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    pattern = re.compile(r"^\s*(?:def|class)\s+%s\b" % re.escape(name))
    for index, text in enumerate(lines, start=1):
        if pattern.search(text):
            return "%s:%d" % (relative, index)
    return None


# --------------------------------------------------------------------------
# verification primitives
# --------------------------------------------------------------------------

def check_location(spec: str) -> tuple[bool, str]:
    """Resolve one 当前实现位置 claim. Never trusts the author."""
    if spec == ABSENT:
        return (False, "无实现位置（按声明）")
    route = re.match(r"^(GET|POST|PUT|PATCH|DELETE) (/.*)$", spec)
    if route:
        key = (route.group(1), route.group(2))
        entry = live_routes().get(key)
        if entry is None:
            return (False, "路由 %s %s 不在实测路由表（V1_ROUTES 与兼容表）中" % key)
        return (True, "路由 %s %s 存在于 %s，handler=%s"
                % (key[0], key[1], entry["table"], entry["handler"]))
    match = LOCATION_LINE_RE.match(spec)
    if not match:
        return (False, "位置写法既不是 file:line 也不是「METHOD /pattern」：%s" % spec)
    path = REPO_ROOT / match.group("path")
    wanted = int(match.group("line"))
    if not path.is_file():
        return (False, "文件不存在：%s" % match.group("path"))
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError as exc:
        return (False, "文件不可读：%s（%s）" % (match.group("path"), type(exc).__name__))
    if wanted < 1 or wanted > len(lines):
        return (False, "%s 只有 %d 行，第 %d 行不存在" % (match.group("path"), len(lines), wanted))
    if not lines[wanted - 1].strip():
        return (False, "%s 第 %d 行为空行，不能作为实现位置" % (match.group("path"), wanted))
    return (True, "%s:%d 存在且非空：%s"
            % (match.group("path"), wanted, lines[wanted - 1].strip()[:80]))


def check_evidence(spec: str) -> tuple[bool, str]:
    """Resolve one 验证证据 citation: pytest node id or an evidence-JSON key path."""
    if spec == NO_EVIDENCE:
        return (False, "无验证证据（NONE）")
    ok_all, notes = True, []
    for part in [piece.strip() for piece in spec.split(";") if piece.strip()]:
        resolved, note = _check_one_evidence(part)
        ok_all = ok_all and resolved
        notes.append(("✓" if resolved else "✗") + " " + note)
    return (ok_all, " ｜ ".join(notes))


def _check_one_evidence(part: str) -> tuple[bool, str]:
    if part.startswith("evidence:"):
        body = part[len("evidence:"):]
        file_name, _, dotted = body.partition("#")
        path = EVIDENCE_DIR / file_name
        if not path.is_file():
            return (False, "证据文件不存在：.project-local/audit/20261030-qoder-ed9037/" + file_name)
        try:
            document = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            return (False, "证据 JSON 不可解析：%s（%s）" % (file_name, type(exc).__name__))
        if not dotted:
            return (True, "%s 可读" % file_name)
        cursor = document
        for step in dotted.split("."):
            if isinstance(cursor, dict) and step in cursor:
                cursor = cursor[step]
            elif isinstance(cursor, list) and step.isdigit() and int(step) < len(cursor):
                cursor = cursor[int(step)]
            else:
                return (False, "%s 中没有键路径 %s" % (file_name, dotted))
        return (True, "%s#%s 存在（值 %s）"
                % (file_name, dotted, json.dumps(cursor, ensure_ascii=True)[:60]))
    if "::" not in part:
        return (False, "证据写法既不是 tests/…py::test_* 也不是 evidence:…#key：" + part)
    file_part, _, test_name = part.partition("::")
    path = REPO_ROOT / file_part
    if not path.is_file():
        return (False, "测试文件不存在：" + file_part)
    text = path.read_text(encoding="utf-8", errors="replace")
    if not re.search(r"^\s*def\s+%s\b" % re.escape(test_name), text, re.M):
        return (False, "%s 中没有名为 %s 的测试" % (file_part, test_name))
    return (True, "%s::%s 已声明" % (file_part, test_name))


# --------------------------------------------------------------------------
# the reconciliation itself
# --------------------------------------------------------------------------

def phasing_tasks() -> dict[str, str]:
    """task id -> declared phase, read from 09_任务分期与验收.json."""
    document = json.loads(PHASING_TABLE.read_text(encoding="utf-8"))
    return {item["id"]: item["phase"] for item in document["tasks"]}


def reconcile(kind: str, row_key: str, source_text: str, phase_text: str,
              claim: dict) -> dict:
    """Apply the closed vocabulary to one authored claim, downgrading what cannot resolve.

    ``source_text`` is the verbatim source row (used to prove an owner exclusion really
    is the owner's words); ``phase_text`` is that row's own 分期/运行实现分期 column.
    """
    location = claim["location"]
    evidence = claim["evidence"]
    authored = claim["status"]
    basis = claim["basis"].strip()
    downgrades: list[str] = []

    if authored not in STATUSES:
        raise SystemExit("STATUS_VOCABULARY_VIOLATION " + kind + " " + row_key)

    loc_ok, loc_note = check_location(location)
    ev_ok, ev_note = check_evidence(evidence)

    if authored in ("IMPLEMENTED_VERIFIED", "IMPLEMENTED_UNVERIFIED", "PARTIAL"):
        if not loc_ok:
            downgrades.append("位置未解析（%s）→ 降级 GAP" % loc_note)
            authored = "GAP"
        elif authored == "IMPLEMENTED_VERIFIED" and not ev_ok:
            downgrades.append("声明 VERIFIED 但证据未解析（%s）→ 降级 IMPLEMENTED_UNVERIFIED" % ev_note)
            authored = "IMPLEMENTED_UNVERIFIED"
        elif authored == "PARTIAL" and PARTIAL_MARKER not in basis:
            downgrades.append("声明 PARTIAL 但未用「%s」写明缺什么 → 降级 GAP" % PARTIAL_MARKER)
            authored = "GAP"
    elif authored in ("DEFERRED_P2", "DEFERRED_P3"):
        wanted = authored.split("_")[1]
        cited = [task for task in PHASE_TASK_RE.findall(basis)
                 if phasing_tasks().get("L" + task) == wanted]
        if wanted not in phase_text and not cited:
            downgrades.append("声明 %s 但该行分期文本无「%s」，且未引用 09 分期表中该期的任务 id → 降级 GAP"
                              % (authored, wanted))
            authored = "GAP"
        elif cited:
            ev_note = ("机验：引用的分期任务 %s 在 09_任务分期与验收.json 中确为 %s"
                       % ("、".join("L" + task for task in cited), wanted)) + " ｜ " + ev_note
    elif authored == "EXCLUDED_BY_OWNER":
        quoted = [token for token in claim.get("decision_quotes", []) if token in source_text]
        if not quoted:
            downgrades.append("声明 EXCLUDED_BY_OWNER 但引用的 owner 原话未逐字出现在来源行中 → 降级 GAP")
            authored = "GAP"
        else:
            ev_note = ("机验：排除决定逐字命中来源行——" + "、".join(quoted)) + " ｜ " + ev_note

    if authored == "GAP" and not basis:
        raise SystemExit("GAP_ROW_WITHOUT_REASON " + kind + " " + row_key)

    verdict = "[机验] 位置：%s ｜ 证据：%s" % (loc_note, ev_note)
    if downgrades:
        verdict += " ｜ [降级] " + "；".join(downgrades)
    return {
        "来源行标识": row_key,
        "要求原文": source_text,
        "当前实现位置": location if loc_ok or location == ABSENT else "GAP（原引用 %s 未能解析）" % location,
        "验证证据": evidence,
        "状态": authored,
        "依据说明": "[判定] " + basis + " " + verdict,
        "_authored_status": claim["status"],
        "_authored_location": location,
        "_authored_evidence": evidence,
        "_location_ok": loc_ok,
        "_evidence_ok": ev_ok,
        "_downgraded": bool(downgrades),
    }


def join_verbatim(fields: list[str]) -> str:
    return " | ".join(field.strip() for field in fields)


# --------------------------------------------------------------------------
# authored judgements (input to the machine; never the other way round)
# --------------------------------------------------------------------------

def ui_claims() -> dict[str, dict]:
    """One judgement per 04 row, keyed ``来源仓:原入口ID``.

    Semantics used here for this table (stated in each row's 依据说明 as well):
    IMPLEMENTED_VERIFIED needs BOTH a real fused landing spot (the shipped workbench
    navigation) AND a test in this repo over the endpoint that spot reads; the fused
    product shell is STITCH's deliverable and is recorded NOT_RUN, so the 31 WORK
    entries — which have no navigation in this repo at all — can at best be PARTIAL
    (backend surface verified, fused UI missing) or GAP (no surface either).
    """
    manual = "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart"
    projection = "tests/unified/test_v11_audit_rework.py::test_f01_unified_service_serves_the_migrated_work_projection"
    f09 = "tests/unified/test_v11_audit_rework.py::test_f09_observer_reads_answer_and_control_gate_is_enforced"
    f09w = "tests/unified/test_v11_audit_rework.py::test_f09_observer_writes_are_refused_and_recorded"
    caps = "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived"
    projects = "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources"
    conn = "tests/unified/test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe"
    knowledge = "tests/unified/test_v06_knowledge.py::test_create_search_short_queries_and_no_result"
    unified_search = "tests/unified/test_v06_knowledge.py::test_unified_search_endpoint_merges_both_libraries"
    handoff_guard = "tests/unified/test_v05_rejections.py::test_external_receipt_claim_is_not_declarable"
    import_guard = "tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused"
    stale_guard = "tests/unified/test_v05_rejections.py::test_stale_result_refused"
    dispatch_guard = "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch"
    f10 = "tests/unified/test_v11_audit_rework.py::test_f10_qualification_needs_a_probe_bound_to_this_candidate"
    improvements = "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only"

    def partial(basis: str) -> dict:
        return {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "PARTIAL",
                "basis": basis}

    no_ui = "融合后的统一桌面壳（总览/工具/任务/知识/设置 五组导航）由 STITCH 前端交付，本轮实测登记为 NOT_RUN（evidence:delivery-summary.json#outstanding 含 FRONTEND_STITCH）；"

    work = {
        "work:work": {"location": "GET /api/work/observer/projection", "evidence": projection,
                      "status": "PARTIAL",
                      "basis": no_ui + "缺口：新产品的「总览/当前工作」视图未生成；WORK 侧当前工作的只读投影已在统一内核挂载并有断言。"},
        "work:agents": {"location": "GET /api/v1/connections", "evidence": conn,
                        "status": "PARTIAL",
                        "basis": "该行分期为「P1 投影；P2真实接线」：P1 投影已有（连接态只会是未连接，客户端不能自证 CONNECTED）。" + no_ui
                                 + "缺口：P2 真实执行器接线未做（09 的 L21 单个执行器适配为 P2 条件项；a01-a10-results.json#results.P2_native_hosts 记 NOT_RUN）。"},
        "work:projects": {"location": "GET /api/v1/projects", "evidence": projects,
                          "status": "PARTIAL",
                          "basis": "两域项目在同一端点注册并读回（work/design 同表）。" + no_ui + "缺口：「项目/列表」视图未生成。"},
        "work:project-detail": {"location": "GET /api/projects/([0-9a-f]{32})",
                                "evidence": NO_EVIDENCE, "status": "PARTIAL",
                                "basis": "DESIGN 兼容面已有单项目读取路由；" + no_ui
                                         + "缺口：本仓 pytest 未断言该兼容路由的读回，且 WORK 项目详情视图未生成。"},
        "work:environment": {"location": "GET /api/environment", "evidence": NO_EVIDENCE,
                             "status": "PARTIAL",
                             "basis": "本机环境读面在兼容路由中；" + no_ui + "缺口：无 pytest/探测断言其内容口径，视图未生成。"},
        "work:capabilities": {"location": "GET /api/v1/capabilities", "evidence": caps + ";" + f10,
                              "status": "PARTIAL",
                              "basis": "能力目录由实现/资格/依赖/连接/授权/策略派生，不可用带原因，资格只认绑定当前候选版本的探测记录；"
                                       + no_ui + "缺口：「工具/能力目录」视图未生成。"},
        "work:usage": {"location": "GET /api/work/observer/projection", "evidence": projection,
                       "status": "PARTIAL",
                       "basis": "投影响应内含 usage_summary 字段并由该测试读回；" + no_ui
                                + "缺口：「实测与估计分开、未知不填 0」这一验收口径无专门断言（见 05 usage 行同一缺口）。"},
        "work:rules-adaptation": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                                  "basis": "两张实测路由表中不存在任何规则适配端点，backend/ 与 domains/ 下亦无对应读写面；本行不声称已具备。"},
        "work:privacy": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                         "basis": "「隐私与采集」在产品边界上成立（私有正文限制、原始任务内容与遥测分离写在 08 的 invariants 与 INTEGRATION_POLICY §5），但没有实现该设置的读写面与开关，故是缺口而不是半成品。"},
        "work:executions": {"location": "GET /api/v1/tasks/([0-9a-f]{32})", "evidence": manual,
                            "status": "PARTIAL",
                            "basis": "执行记录以 Attempt 形式随任务读回；" + no_ui + "缺口：「任务/执行记录」视图未生成。"},
        "work:models": {"location": "GET /api/models", "evidence": NO_EVIDENCE, "status": "PARTIAL",
                        "basis": "该行分期为「P1档案；P2真实连接」：模型档案面已在兼容路由，模型目录不做锁定、默认 fail-closed；"
                                 + no_ui + "缺口：P2 真实连接与「工具/模型与入口」视图未生成，本仓无 pytest 断言 /api/models 口径。"},
        "work:memory": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                        "basis": "该行自身约束「不复制原生私有记忆」，因此保留的是接缝而不是实现；统一后端无会话/记忆端点，「知识/上下文与经验」视图也未生成。"},
        "work:tools": {"location": "GET /api/v1/tools", "evidence": NO_EVIDENCE, "status": "PARTIAL",
                       "basis": "工具台账端点真实存在；" + no_ui + "缺口：本仓 pytest 未覆盖 /api/v1/tools，「工具/我的工具」视图未生成。"},
        "work:monitoring": {"location": "GET /api/work/observer/snapshot", "evidence": f09,
                            "status": "PARTIAL",
                            "basis": "运行观察快照经同一内核读同一 CanonicalStore；" + no_ui
                                     + "缺口：持续 watcher/SSE 推送仍在独立 sidecar（docs/CODEX-AUDIT-ENTRY.md §7），「项目/运行状态」视图未生成。"},
        "work:delivery": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                          "basis": "WORK 侧「任务/交付」没有端点：交付面（bundles/receipt）只存在于 DESIGN 兼容路由，未与统一任务信封接通，也没有 WORK 交付台账。"},
        "work:trust": {"location": "GET /api/v1/tasks/([0-9a-f]{32})/completion", "evidence": stale_guard,
                       "status": "PARTIAL",
                       "basis": "核验与可信详情由 completion 计算 + 结果时效（stale 拒绝）支撑；" + no_ui + "缺口：「任务/核验与可信详情」视图未生成。"},
        "work:software": {"location": "domains/work/orchestration/software_installation_identity.py:78",
                          "evidence": NO_EVIDENCE, "status": "PARTIAL",
                          "basis": "安装身份分类逻辑已迁入（classify_installation）；" + no_ui
                                   + "缺口：本仓无 pytest 断言「安装、版本、探测、授权、可执行」分别记录，视图未生成。"},
        "work:settings": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                          "basis": "「设置」作为总入口没有对应的统一读写面：/api/v1/health 与 /api/environment 只回答服务与本机构环境，规则/隐私/审批策略的持久化设置在两表中均无端点。"},
        "work:rules-policy": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                              "basis": "同 work:rules-adaptation：实测路由表中无规则策略端点，domains/ 下无策略账本读写实现。"},
        "work:audit": {"location": "GET /api/v1/integrity", "evidence": NO_EVIDENCE, "status": "PARTIAL",
                       "basis": "完整性/诊断读面存在（integrity）；" + no_ui
                                + "缺口：本仓无 pytest 断言 integrity 口径，「设置/诊断与审计」视图未生成。"},
        "work:approvals": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/approval",
                           "evidence": "tests/unified/test_v10_gate.py::test_gate_accepts_backed_completions;" + f09w,
                           "status": "PARTIAL",
                           "basis": "审批写面 + 真人门（本地 Human Gate 账本，拒绝 Agent 身份冒名）已实现并有断言；"
                                    + no_ui + "缺口：「任务/待确认与权限抽屉」视图未生成，权限抽屉无实现。"},
        "work:integrations": {"location": "GET /api/v1/connections", "evidence": conn, "status": "PARTIAL",
                              "basis": "该行分期「P1档案；P2真实连接」：连接档案与探测态可读；" + no_ui
                                       + "缺口：MCP/集成真实连接属 P2（09 的 L21），未接线，视图未生成。"},
        "work:task-packs": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/pack",
                            "evidence": manual + ";" + handoff_guard, "status": "PARTIAL",
                            "basis": "人工任务包生成/声明/导入/核验全链路有测试；生成本身不声明交接。" + no_ui
                                     + "缺口：「任务/人工任务包」视图未生成。"},
        "work:workflows": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                           "basis": "该行写「P1保留既有」，但本仓没有任何工作流模板/流程端点：workflow_core 只有 repair pack 状态机与投影，模板与流程的读写面缺失。"},
        "work:workflow-editor": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "DEFERRED_P3",
                                 "basis": "该行分期「P1保留既有；P3复杂新增」：高级流程编辑器属复杂新增，按 09 分期表 L30/L31（P3）延期，来源与接缝保留，本行不声称已实现。"},
        "work:observer": {"location": "GET /api/work/observer/snapshot", "evidence": f09,
                          "status": "PARTIAL",
                          "basis": "该行要求 P1 只读：Observer 读面只读、写请求被拒并落拒绝记录（GET /api/work/observer/refusals）；" + no_ui
                                   + "缺口：「项目/运行观察详情」视图未生成。"},
        "work:execution-detail": {"location": "GET /api/v1/attempts/([0-9a-f]{32})",
                                  "evidence": NO_EVIDENCE, "status": "PARTIAL",
                                  "basis": "单 Attempt 读取路由存在；" + no_ui + "缺口：本仓 pytest 未单独断言该读路由，「任务/执行详情」视图未生成。"},
        "work:evidence": {"location": "GET /api/work/observer/evidence-range", "evidence": f09,
                          "status": "PARTIAL",
                          "basis": "证据区间读面存在且经同一内核；" + no_ui + "缺口：「任务/证据抽屉」视图未生成。"},
        "work:trial-plan": {"location": "backend/core/probes.py:43",
                            "evidence": f10 + ";" + conn, "status": "PARTIAL",
                            "basis": "受控探测试（run_read_probes）与资格派生分离实现，探测与执行分开写在 08 的 invariants；" + no_ui
                                     + "缺口：「工具/受控试用/方案」视图未生成，试用方案的编排面未接入自动路径。"},
        "work:trial-failure": {"location": "backend/core/qualifications.py:169", "evidence": f10,
                               "status": "PARTIAL",
                               "basis": "失败/过期/外来候选记录不授予资格由 derive() 判定并有断言；" + no_ui + "缺口：「工具/受控试用/失败」视图未生成。"},
        "work:trial-readback": {"location": "backend/core/qualifications.py:283", "evidence": f10,
                                "status": "PARTIAL",
                                "basis": "loopback 读回探测存在且只绑定当前候选版本；" + no_ui + "缺口：「工具/受控试用/读回」视图未生成。"},
    }

    def design_row(nav_line: int, status: str, basis: str, evidence: str = NO_EVIDENCE,
                   location: str | None = None) -> dict:
        return {"location": location or ("apps/workbench/shell.ts:%d" % nav_line),
                "evidence": evidence, "status": status,
                "basis": "[判定] 入口已落在 apps/workbench/shell.ts 的导航表内（该行的 view id 与来源表 04 的原入口ID 同名）"
                         + basis}

    plan_test = "tests/legacy/design/test_assistance_plan.py::test_a_plan_is_saved_with_its_basis_and_reads_back_after_a_restart"
    revision_test = "tests/legacy/design/test_assistance_plan.py::test_a_stale_revision_is_refused_with_the_actual_number"
    knowledge_test = "tests/legacy/design/test_knowledge_library.py::test_every_minimum_field_is_stored_and_a_silent_field_is_unknown"
    target_test = "tests/legacy/design/test_target_profile.py::test_seeded_profiles_are_served_from_the_tracked_config_with_no_database_copy"
    design_read = "tests/unified/test_v02_surface.py::test_design_domain_read_routes_answer_real_data"
    design_loop = "tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending"

    design = {
        "design:workbench": design_row(346, "IMPLEMENTED_UNVERIFIED",
                                        "；默认视图真实存在，但本仓 pytest 不断言工作台渲染，故不标 VERIFIED。"),
        "design:assistant": design_row(349, "IMPLEMENTED_VERIFIED",
                                       "；其后端合同（辅助方案存/读回/修订）由具名测试断言。", plan_test),
        "design:dashboard": design_row(350, "IMPLEMENTED_UNVERIFIED",
                                       "；「总览/设计摘要」无专门聚合端点，本仓无对应断言。"),
        "design:intake": design_row(351, "IMPLEMENTED_UNVERIFIED",
                                    "；briefs 读写路由在兼容面存在，但本仓无 pytest 覆盖输入与目标的连续状态。"),
        "design:analysis": design_row(352, "IMPLEMENTED_VERIFIED",
                                      "；分析与方案的修订冲突按真实数字拒绝，由具名测试断言。", revision_test),
        "design:prompt-intelligence": design_row(353, "PARTIAL",
                                                 "；该行分期「P1既有；P3复杂新增」，入口与既有提示词面在，" + PARTIAL_MARKER
                                                 + "P3 复杂新增（模型执行）未做（09 分期表 L32 为 P3）；提示词路由在本仓无 pytest 断言。",
                                                 NO_EVIDENCE),
        "design:research": design_row(354, "PARTIAL",
                                      "；该行分期「P1保留；外部检索本批不调用」，" + PARTIAL_MARKER
                                      + "外部检索按 INTEGRATION_POLICY §1 与 00 §四 的本地执行边界不调用，research 读写路由无本仓断言。",
                                      NO_EVIDENCE),
        "design:capabilities": design_row(355, "IMPLEMENTED_VERIFIED",
                                          "；「工具/能力目录/设计筛选」读的是已实测的能力目录端点，诚实性与派生由具名测试断言。",
                                          caps),
        "design:design-domains": design_row(356, "IMPLEMENTED_UNVERIFIED",
                                            "；/api/domains 路由在，本仓无 pytest 断言 13 领域包可加载。"),
        "design:brand-systems": design_row(357, "IMPLEMENTED_UNVERIFIED",
                                           "；设计系统与 tokens 读写路由在，本仓无对应断言（P1保留既有）。"),
        "design:creative-tools": design_row(358, "PARTIAL",
                                            "；该行分期「P1档案；P2真实调用」，" + PARTIAL_MARKER
                                            + "P2 真实宿主调用-保存-重开-读回仍 BLOCKED（需逐次 Human Gate，见 docs/CODEX-AUDIT-ENTRY.md §5；09 分期表 L20 为 P2）。",
                                            "tests/unified/test_v14_registers.py::test_host_bridge_script_is_reachable_where_the_adapter_probes"),
        "design:knowledge": design_row(360, "IMPLEMENTED_VERIFIED",
                                       "；「知识/设计知识与提示词」的条目存读、修订与索引重建均有本仓断言。",
                                       knowledge_test + ";" + knowledge + ";" + unified_search),
        "design:projects": design_row(362, "IMPLEMENTED_VERIFIED",
                                      "；「项目/设计筛选」读的是统一项目端点，两域来源同表注册并读回由具名测试断言。", projects),
        "design:plan": design_row(363, "IMPLEMENTED_VERIFIED",
                                  "；「设计/目标生成包与任务关联」走统一设计闭环，专业验收在真人门前保持 pending 由具名测试断言。",
                                  design_loop + ";" + design_read),
        "design:records": design_row(365, "IMPLEMENTED_UNVERIFIED",
                                     "；「设计/我的方案与任务记录」入口在，聚合读面复用方案列表路由，本仓无针对记录视图的断言。"),
        "design:deliverables": design_row(366, "IMPLEMENTED_UNVERIFIED",
                                         "；交付路由（bundles/receipt/preflight）在兼容面存在，本仓无 pytest 覆盖「任务/交付/设计筛选」。"),
        "design:evidence": design_row(367, "IMPLEMENTED_UNVERIFIED",
                                      "；证据投影路由在，本仓无针对该视图读回的断言（结果/核验链由统一侧测试覆盖，不是同一件事）。"),
        "design:preflight-qa": design_row(368, "PARTIAL",
                                          "；该行分期「P1保留既有；P2宿主；P3复杂新增」，" + PARTIAL_MARKER
                                          + "宿主 preflight 的真调用属 P2（09 分期表 L20），复杂 Jury 属 P3（L31）；预检路由无本仓断言。",
                                          NO_EVIDENCE),
        "design:settings": design_row(370, "IMPLEMENTED_UNVERIFIED",
                                      "；设置视图入口在，本仓无覆盖设置读写面的 pytest。"),
        "design:model-selection": design_row(374, "PARTIAL",
                                             "；该行分期「P1档案；P2真实连接」：模型选择档案与 choose 记录在（选择不等于连接和执行），"
                                             + PARTIAL_MARKER + "P2 真实连接未接线；用户显式选择只记录动作、不改合格状态。",
                                             NO_EVIDENCE),
        "design:target-profiles": design_row(378, "IMPLEMENTED_VERIFIED",
                                             "；「设计/目标组合」的软件×模型×入口种子由具名测试断言（无数据库副本、逐轴原因保留）。",
                                             target_test),
        "design:automation-connectors": design_row(381, "PARTIAL",
                                                   "；该行分期「P1档案；P2真实连接」，连接器档案路由在，" + PARTIAL_MARKER
                                                   + "P2 真实连接未接线，本仓无该路由断言。", NO_EVIDENCE),
        "design:collaboration": {"location": "apps/workbench/shell.ts:382", "evidence": NO_EVIDENCE,
                                 "status": "EXCLUDED_BY_OWNER",
                                 "decision_quotes": ["企业团队不进入主导航"],
                                 "basis": "owner 在本行的分期列写明「范围复核：个人评审归设计；企业团队不进入主导航」，并与 11_需求追溯.csv 的 P06"
                                          "「个人使用，不扩手机或企业团队平台」一致：企业团队协作平台是被明确排除的范围，不是缺口也不是待办。"
                                          "注意：该行原入口仍留在 workbench 导航里（来源保留），本登记只裁范围，不声称该能力已交付。"},
        "design:ui-states": design_row(383, "IMPLEMENTED_UNVERIFIED",
                                       "；该行分期「P1工程交接」：界面状态规范作为交接文档在 workbench 内，本仓无自动断言（人工交接物，不算运行能力）。"),
        "design:ui-components": design_row(384, "IMPLEMENTED_UNVERIFIED",
                                           "；同上，组件规范是工程交接物，本仓无自动断言。"),
    }
    claims = {}
    claims.update(work)
    claims.update(design)
    return claims


def family_claims() -> dict[str, dict]:
    manual = "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart"
    namespace = "tests/unified/test_v12_data_migration.py::test_cross_domain_same_id_is_namespaced_not_merged"
    projection = "tests/unified/test_v11_audit_rework.py::test_f01_unified_service_serves_the_migrated_work_projection"
    read_path = "tests/unified/test_v11_audit_rework.py::test_f01_read_path_starts_no_collector_and_opens_no_socket"
    f09 = "tests/unified/test_v11_audit_rework.py::test_f09_observer_reads_answer_and_control_gate_is_enforced"
    caps = "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived"
    return {
        "project": {"location": "POST /api/v1/tasks",
                    "evidence": "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources;" + namespace,
                    "status": "IMPLEMENTED_VERIFIED",
                    "basis": "项目/工作单元与任务在同一统一存储中登记并跨域命名空间隔离，验收的「项目ID、来源路径、关联任务可读回，无跨项目污染」有直接断言。"},
        "task": {"location": "POST /api/v1/tasks", "evidence": manual + ";" + "tests/unified/test_v05_rejections.py::test_duplicate_result_refused_on_second_attempt",
                 "status": "IMPLEMENTED_VERIFIED",
                 "basis": "幂等键 (task_id, idempotency_key) 唯一、重启读回、重复结果拒绝均有具名断言；人工交接与结果核验见 04 work:task-packs。"},
        "execution": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/handoff-declarations",
                      "evidence": "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch;" + "tests/unified/test_v05_rejections.py::test_external_receipt_claim_is_not_declarable",
                      "status": "PARTIAL",
                      "basis": PARTIAL_MARKER + "P2 单个真实执行器连接、P3 多 Agent 未接线（09 分期表 L21/L30）；本轮只有 P1 人工闭环，"
                              "且一个会话一个拥有者、取消与结果不伪造只到「声明与拒绝」层，没有真实执行器可对账。"},
        "permissions": {"location": "domains/work/control/permission_gate.py:107",
                        "evidence": "tests/unified/test_v02_surface.py::test_write_boundary_unknown_project_and_kind;" + f09,
                        "status": "PARTIAL",
                        "basis": "Observer 只读（写请求 405 并落拒绝记录）与 Control 写入门控有断言；" + PARTIAL_MARKER
                                + "验收的「写入校验范围与状态」只覆盖已挂载的操作面，独立授权账本未建。"},
        "telemetry": {"location": "backend/core/work_surfaces.py:82", "evidence": read_path,
                      "status": "PARTIAL",
                      "basis": "真实投影走同一 CanonicalStore，且读路径不启动采集器、不开套接字（该测试正是证明这一点）；" + PARTIAL_MARKER
                              + "持续采集/watcher 仍在独立 sidecar，统一内核只提供有界帧（docs/CODEX-AUDIT-ENTRY.md §7）。"},
        "usage": {"location": "GET /api/work/observer/projection", "evidence": projection,
                  "status": "PARTIAL",
                  "basis": "usage_summary 随投影读回；" + PARTIAL_MARKER
                          + "验收口径「实测与估计分开，未知不填0」没有专门断言，本仓无法证明未知值没有被写成 0。"},
        "issues": {"location": "domains/work/workflow_core/issue_projection.py:567", "evidence": f09,
                   "status": "PARTIAL",
                   "basis": "问题投影与 repair-packs 读面真实存在并被读回；" + PARTIAL_MARKER
                           + "「问题、修复、尝试和证据链可追溯」的链完整性无独立断言，现有测试断言的是读通与 control 门。"},
        "solutions": {"location": "GET /api/work/observer/solutions",
                      "evidence": "tests/unified/test_v11_audit_rework.py::test_f05_unified_search_returns_work_solutions;" + "tests/unified/test_v11_audit_rework.py::test_f05_solution_revision_conflict_and_restart_readback",
                      "status": "IMPLEMENTED_VERIFIED",
                      "basis": "中文检索命中真实 WORK 方案、修订冲突与重启读回都有具名断言（F05 返工项）。"},
        "software": {"location": "domains/work/orchestration/software_installation_identity.py:78",
                     "evidence": NO_EVIDENCE, "status": "IMPLEMENTED_UNVERIFIED",
                     "basis": "安装身份分类与 config/software-registry.json 已迁入；本仓无 pytest/探测断言"
                             "「安装、版本、探测、授权、可执行」分别记录，故不标 VERIFIED。"},
        "configuration": {"location": "backend/core/capabilities.py:97", "evidence": caps,
                          "status": "PARTIAL",
                          "basis": "受管能力目录由真实派生并诚实标注不可用原因；" + PARTIAL_MARKER
                                  + "「局部配置可恢复，不覆盖原生认证和全局环境」未测；config/adapter-registry.json 内含本机绝对路径，恢复语义无回归断言。"},
        "evidence": {"location": "POST /api/v1/results/([0-9a-f]{32})/verifications",
                     "evidence": "tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused;tests/unified/test_v10_gate.py::test_gate_refuses_forged_result_and_verdict",
                     "status": "IMPLEMENTED_VERIFIED",
                     "basis": "验收「拒绝错任务、错版本、重复和假回执」逐条对应到具名反例测试（错项目/错包、stale、重复、伪造回执与伪 PASS）。"},
        "session": {"location": "backend/core/unified_store.py:393", "evidence": NO_EVIDENCE,
                    "status": "PARTIAL",
                    "basis": "Attempt 信封携带 native_session_ref 且与会话引用分离；" + PARTIAL_MARKER
                            + "该行运行实现分期「P1保留既有；P2协议接续」的 P2 接续未做，「不复制私人会话」是执行策略约束而非被测行为。"},
        "candidate": {"location": "GET /api/projects/([0-9a-f]{32})/knowledge-candidates",
                      "evidence": NO_EVIDENCE, "status": "IMPLEMENTED_UNVERIFIED",
                      "basis": "候选与导出的读写合同保留（RETAIN_CONTRACT），P3 深度 AAOS 明确延期且 AAOS 不是依赖；"
                              "本仓无 pytest 断言候选导出为「读回不是发送」，故只能标 UNVERIFIED。"},
        "cleanup": {"location": "scripts/build_migration_map.py:1",
                    "evidence": "tests/unified/test_v07_migration.py::test_prune_reports_only_paths_this_tool_recorded",
                    "status": "PARTIAL",
                    "basis": "已有的是迁移工具的 prune——只报告本工具登记过的路径、默认不删；" + PARTIAL_MARKER
                            + "面向运行产品的「清单范围清理与恢复可读回」未实现，不删除用户作品目前靠不实现删除来保证。"},
        "radar": {"location": "domains/design/design_lab/model_catalog.py:97", "evidence": NO_EVIDENCE,
                  "status": "IMPLEMENTED_UNVERIFIED",
                  "basis": "模型/情报目录从 readiness/model-radar.json 等本机文档现读；"
                          "「信息来源、日期、探测与资格有区别」在本仓无断言，故不标 VERIFIED。"},
        "design-knowledge": {"location": "domains/design/design_lab/knowledge_library.py:531",
                             "evidence": "tests/unified/test_v06_knowledge.py::test_create_search_short_queries_and_no_result;tests/unified/test_v06_knowledge.py::test_revision_conflict_and_index_rebuild",
                             "status": "IMPLEMENTED_VERIFIED",
                             "basis": "内容/来源/修订、中文短词与无结果、索引重建与重启读回都有具名断言。"},
        "design-prompt": {"location": "domains/design/design_lab/prompt_intelligence.py:129",
                          "evidence": NO_EVIDENCE, "status": "PARTIAL",
                          "basis": "生成与反推的既有实现按「P1迁既有」迁入；" + PARTIAL_MARKER
                                  + "「P3新增模型执行」未做（09 分期表 L32），且本仓无 pytest 覆盖提示词路由，"
                                  "「提示词导出不算作品生成」只有约定而没有断言。"},
        "design-plan": {"location": "domains/design/design_lab/assistance_plan.py:121",
                        "evidence": "tests/legacy/design/test_assistance_plan.py::test_a_plan_is_saved_with_its_basis_and_reads_back_after_a_restart;tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
                        "status": "IMPLEMENTED_VERIFIED",
                        "basis": "方案修订不可变、旧修订按自身读回、与任务信封关联后专业验收保持 pending，均由具名测试断言；旧只读合同兼容。"},
        "design-target": {"location": "domains/design/design_lab/target_profile.py:326",
                          "evidence": "tests/legacy/design/test_target_profile.py::test_seeded_profiles_are_served_from_the_tracked_config_with_no_database_copy;tests/unified/test_v04_design_loop.py::test_target_profile_reference_must_address_a_real_profile",
                          "status": "IMPLEMENTED_VERIFIED",
                          "basis": "软件×模型×入口档案从受管配置现读且不落第二副本；引用必须指向真实档案——「选择不等于连接和执行」由资格层断言。"},
        "design-domain": {"location": "domains/design/design_lab/domain_packs.py:199",
                          "evidence": NO_EVIDENCE, "status": "IMPLEMENTED_UNVERIFIED",
                          "basis": "领域包构建器在（含逐包 checker 与说明），/api/domains 路由在；"
                                  "但「13 领域包与资源可加载、资格分别标记」在本仓没有对应断言，数字未经复算。"},
        "design-assets": {"location": "GET /api/projects/([0-9a-f]{32})/assets(?:/(img-[0-9a-f]{64})/content)?", "evidence": NO_EVIDENCE,
                          "status": "IMPLEMENTED_UNVERIFIED",
                          "basis": "输入/输出/版本/引用的读写路由在兼容面存在；本仓无断言「可恢复」，也未声明素材平台扩张。"},
        "design-reconstruction": {"location": "packages/capabilities/reconstruction/contracts.py:117",
                                  "evidence": NO_EVIDENCE, "status": "IMPLEMENTED_UNVERIFIED",
                                  "basis": "RIR 校验与规范化摘要在包内实现并被 native_plan 使用；"
                                          "「结构与视觉规格分开验收」需人审，本仓无 pytest 断言，故不标 VERIFIED。"},
        "design-quality": {"location": "domains/design/design_lab/assurance/human_jury.py:251",
                           "evidence": "tests/unified/test_v11_audit_rework.py::test_f08_agent_and_unresolved_verifiers_cannot_satisfy_professional",
                           "status": "IMPLEMENTED_VERIFIED",
                           "basis": "验收「技术核验与专业人工验收分开」有直接反例断言：Agent 引用与未解析 verifier 不能充当真人验收。"},
        "design-tools": {"location": "domains/design/design_lab/adapters/photoshop_com.py:79",
                         "evidence": "tests/unified/test_v14_registers.py::test_host_bridge_script_is_reachable_where_the_adapter_probes",
                         "status": "PARTIAL",
                         "basis": "桥接脚本在适配层实际探测的包内路径且与真值逐字节一致（漂移由守卫拦截）；" + PARTIAL_MARKER
                                 + "P2「已可用宿主的真调用/保存/重开/读回」仍 BLOCKED（需逐次 Human Gate），P3 多宿主未做（09 分期表 L20/L31）——登记不算连接。"},
        "desktop": {"location": "apps/workbench/shell.ts:346", "evidence": NO_EVIDENCE,
                    "status": "PARTIAL",
                    "basis": "现有 workbench 导航与逐视图读回渲染在（未重画 UI，符合「不默认重画」）；" + PARTIAL_MARKER
                            + "「56 旧入口有去向」这一验收由本次生成的 ui-entry-disposition.csv 满足；"
                            "统一桌面壳与合成首页属 STITCH 前端，本轮实测登记为 NOT_RUN（evidence:delivery-summary.json#outstanding）。"},
        "contracts": {"location": "packages/contracts/schemas/workflow/action-plan.schema.json:1",
                      "evidence": NO_EVIDENCE, "status": "IMPLEMENTED_UNVERIFIED",
                      "basis": "公共 Schema 目录随包发布并被 store/服务读取；"
                              "「现有消费者与版本兼容、错误输入与资源路径回归」没有针对 packages/contracts 的具名测试，故不标 VERIFIED。"},
        "research": {"location": "research/candidates/CANDIDATE-TAXONOMY.json:1", "evidence": NO_EVIDENCE,
                     "status": "IMPLEMENTED_UNVERIFIED",
                     "basis": "研究资料按「资料不是运行事实」留在 research/ 内且未被任何运行路径导入；"
                             "联网检索延期（09 分期表 L30 属 P3），本行不声称已具备检索能力。"},
        "evolution": {"location": "GET /api/v1/improvements", "evidence": "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only;" + caps,
                      "status": "PARTIAL",
                      "basis": "改进面诚实回答 CONTRACT_ONLY / activation_state=UNAVAILABLE，能力目录把 core.evolution 标为 DECLARED 且 can_invoke=false；" + PARTIAL_MARKER
                              + "「P3 完整执行链」——技能/插件/前后端修改分开、独立验收与回退——未实现（09 分期表 L32）。"},
        "build-test": {"location": "scripts/verify_isolated_install.py:185",
                       "evidence": "evidence:a01-a10-results.json#results.A08;tests/unified/test_v14_registers.py::test_coverage_register_accounts_for_every_source_file",
                       "status": "IMPLEMENTED_VERIFIED",
                       "basis": "wheel 离线构建并安装到隔离目录、安装态 __file__ 全部指向安装树（A08 实测记录），真实 loopback HTTP 与持久化由本仓回归覆盖；未继承旧 CI 绿。"},
        "unclassified": {"location": "migration/review/unclassified-review.json:4", "evidence": NO_EVIDENCE,
                         "status": "PARTIAL",
                         "basis": "复核登记自述 8/8 已复核并逐条给出归属与处置；" + PARTIAL_MARKER
                                 + "该「已复核」目前只是文件自述，没有测试重算条数与处置一致性，故按未机器核实处理，不标 VERIFIED。"},
    }


def requirement_claims() -> dict[str, dict]:
    manual = "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart"
    caps = "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived"
    projects = "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources"
    return {
        "U01": {"location": "POST /api/v1/projects", "evidence": projects, "status": "PARTIAL",
                "basis": "两域已在同一后端、同一任务/数据入口上共同读写（work 与 design 同表注册并读回）；" + PARTIAL_MARKER
                        + "「单壳」尚未交付——统一桌面壳属 STITCH 前端，本轮登记为 NOT_RUN（evidence:delivery-summary.json#outstanding）。"},
        "U02": {"location": "migration/source-coverage-work.csv:2",
                "evidence": "tests/unified/test_v14_registers.py::test_coverage_register_accounts_for_every_source_file;" + "tests/unified/test_v12_data_migration.py::test_migration_preserves_revisions_digests_and_references",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "四个维度各自有面：源文件=逐文件覆盖登记（类别之和=行数由测试现算），语义=mapping.csv 与 198 条去向，"
                        "行为=tests/unified 回归，数据=test_v12 受控迁移（含幂等/回滚/命名空间）。去重按 EQUIVALENT_MERGED/PRESENT_IN_TARGET 逐条判定。"},
        "U03": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/pack", "evidence": manual,
                "status": "PARTIAL",
                "basis": "确定流程直调工具（人工任务包/迁移工具/CLI）不依赖 Agent 即可闭环，且有测试；" + PARTIAL_MARKER
                        + "「成熟能力优先复用」目前只有迁入清单与去向判定支撑，没有复用度指标可测。"},
        "U04": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/handoff-declarations",
                "evidence": "evidence:a01-a10-results.json#results.P3_multi_agent;" + "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch",
                "status": "DEFERRED_P2",
                "basis": "本行交付原文即「本批保留合同，真实接线按条件分期」：合同（Attempt/执行模式枚举/拒绝外部回执冒充）已保留并有测试，"
                        "真实多 Agent 派发按 09 分期表 L21（P2 单个执行器）与 L30（P3 多 Agent）分期，实测登记 P3_multi_agent 未运行。"},
        "U05": {"location": "POST /api/v1/attempts/([0-9a-f]{32})/handoff-declarations",
                "evidence": "tests/unified/test_v05_rejections.py::test_import_before_declared_handoff_refused;" + "tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "P1 两域人工闭环：WORK 侧生成包→人工声明交接→导入结果→核验；DESIGN 侧同链路且专业验收在真人门前保持 pending。"
                        "生成本身不产生交接声明、外部回执不可声明，均为具名反例断言。"},
        "U06": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "DEFERRED_P3",
                "basis": "BOT 是交互/消息入口，本行交付原文「渠道后置，不新建重复总控」：统一后端没有第二总控（只有一个 CanonicalStore 与一张路由表），"
                        "BOT 渠道本身按 09 分期表 L30（P3 复杂多Agent/BOT/跨机协作）延期，本行不声称已实现。"},
        "U07": {"location": "pyproject.toml:1", "evidence": NO_EVIDENCE, "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "「局部机制适配，不默认整仓换底」在技术上成立：产品仍是迁移过来的 Python 标准库后端 + Vanilla TypeScript/Vite 前端，"
                        "未引入参考项目的底座；但这是结构事实而非被测行为，本仓无断言，故不标 VERIFIED。参考资料的登记在 research/candidates 与 vendor/。"},
        "U08": {"location": "GET /api/v1/improvements", "evidence": "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only",
                "status": "PARTIAL",
                "basis": "候选合同、独立验收门（拒绝伪 PASS）与升级/恢复的数据合同在；" + PARTIAL_MARKER
                        + "本行交付原文把执行划为 P3（09 分期表 L32 完整自改写激活与回退未实现）。"},
        "U09": {"location": ABSENT, "evidence": "evidence:a01-a10-results.json#results.FRONTEND_STITCH", "status": "GAP",
                "basis": "提示词文件只在只读任务包内（01_STITCH_完整前端提示词.txt），其交付物——前端设计稿与实现——本轮未产生，实测登记 FRONTEND_STITCH 为未运行；"
                        "F01-F10 帧与 J1-J9 在本仓没有任何对应实现或断言，本行是缺口而不是延期项（09 分期表把它列为必做波次的交接物）。"},
        "U10": {"location": "backend/v1.py:132", "evidence": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata;" + manual,
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "后端闭环按 P0/P1 落实：V1_ROUTES 现读到 75 条路由（含 49 条 WORK 消费面），真实 loopback HTTP + 持久化 + 重启读回由具名测试断言。"},
        "U11": {"location": ".git/HEAD:1", "evidence": "evidence:delivery-summary.json#git", "status": "IMPLEMENTED_VERIFIED",
                "basis": "本仓确在本地工作分支 integration/local-fusion-20261029 上执行（.git/HEAD 第一行就是该 branch ref），"
                        "增量保全由 delivery-summary.json#git 与 snapshot-before/after 逐文件摘要证明；注意 HEAD 仍是 unborn（无提交），"
                        "本行不据此声称已提交或已同步。"},
        "U12": {"location": "backend/core/capabilities.py:97", "evidence": caps + ";" + "tests/unified/test_v11_audit_rework.py::test_f01_registered_gap_paths_all_have_a_real_disposition",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "两条都可测：延期面在能力目录里保持 DECLARED/DEFERRED 并带 phase、can_invoke=false（不降级冒充）；"
                        "来源与接缝的保留由 198 条去向登记 + 逐文件覆盖登记断言，延期不等于删除。"},
        "U13": {"location": "backend/v1.py:527",
                "evidence": "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch;" + "tests/unified/test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "运行面上没有任何可把项目/数据推向远端的入口：外部派发在 pack 处直接 400 拒绝，"
                        "且不存在把连接改成 CONNECTED 的路由（POST /api/v1/connections 实测 404）。"
                        "本行只声称代码层不被绕过；系统级出站隔离未被证明（INTEGRATION_POLICY §2），2026-10-31 的首次上传是 owner 单独放行的例外（§6），不改变本行的禁止面。"},
        "U14": {"location": "backend/v1.py:527", "evidence": "tests/unified/test_v05_rejections.py::test_adapter_dispatch_is_not_allowed_this_batch;" + "evidence:a01-a10-results.json#results.A08",
                "status": "PARTIAL",
                "basis": "全部构建/测试/安装都在本地：A08 是离线隔离安装实测，工具与模型方式已在 INTEGRATION_POLICY §4 逐条核实；" + PARTIAL_MARKER
                        + "「禁止云构建/远程派发/自动同步」在代码与流程上成立，但系统级出站隔离未被证明，且执行本任务的模型本身是云端会话模型（§2 如实登记）。"},
        "U15": {"location": "docs/CODEX-AUDIT-ENTRY.md:1",
                "evidence": "evidence:a01-a10-results.json#results;" + "evidence:f01-f10-closure.json#items",
                "status": "PARTIAL",
                "basis": "我方一侧的交付齐了可被独立审的东西：候选摘要、原始日志、逐条反例与重跑记录；" + PARTIAL_MARKER
                        + "「由本地 Codex 审计」这一步在 owner 侧执行，其结论不由本仓生成也无法本仓自证，所以不能标 VERIFIED。"
                        "位置列只给出审计入口文件，不作为完成依据。"},
        "U16": {"location": "AI-WORK-LAB_HANDOFF_20261029/00_阅读顺序与需求确认.txt:1",
                "evidence": "evidence:delivery-summary.json#outstanding",
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "共同约定文本已随任务包只读留存并在 08 与三份提示词中成形，本登记把它拆成 25 条逐行可对账的要求；"
                        "但「确认理解」是人的动作，无自动断言，故不标 VERIFIED。"},
        "P01": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                "basis": "本行引用 STITCH 帧 F01/F02 与 SCREEN_12 画板，属前端交付；本轮前端 NOT_RUN，"
                        "且 SCREEN_12 未进入本仓（只读任务包内亦无位图证据），紧凑层级无从对照，故记缺口不记完成。"},
        "P02": {"location": "GET /api/v1/design/plans",
                "evidence": "tests/legacy/design/test_assistance_plan.py::test_a_plan_is_saved_with_its_basis_and_reads_back_after_a_restart;" + "tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
                "status": "PARTIAL",
                "basis": "后端连续状态可测：方案存/读回/修订、目标组合引用、专业验收 pending 均有断言，D01/D02/D04 所需的数据合同在；" + PARTIAL_MARKER
                        + "「自由切换、修订与目标组合」的画面按 F04 属前端，未交付。"},
        "P03": {"location": "apps/workbench/style.css:1", "evidence": NO_EVIDENCE,
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "共用 token 与深色/冷色布局在迁入的 workbench 样式内延续，未改成暖色；"
                        "这是视觉判断，需人审，本仓无 token 断言，故不标 VERIFIED。"},
        "P04": {"location": "apps/workbench/shell.ts:346", "evidence": NO_EVIDENCE,
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "导航是「入口 + 按需详情」的紧凑结构，未新增巨大流程仪表盘；"
                        "同样属视觉/信息密度判断，无自动断言，需人审，故不标 VERIFIED。"},
        "P05": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                "basis": "HUD（F10 轻量浮层不替代主界面）在本仓不存在：apps/workbench 全部源文件中检索不到 hud 相关实现，"
                        "后端也无 HUD 状态面；本行记缺口，不以前端提示词的存在充当实现。"},
        "P06": {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "EXCLUDED_BY_OWNER",
                "decision_quotes": ["不扩手机或企业团队平台"],
                "basis": "本行本身就是 owner 的范围裁定：「个人使用，不扩手机或企业团队平台」，交付原文只要求「保留来源、解释范围，避免新平台」。"
                        "04 表 design:collaboration 行的「企业团队不进入主导航」与之呼应；本登记满足其「解释范围」部分。"
                        "排除不是缺口也不是待办，解除只认 owner 新的明确授权。"},
        "P07": {"location": "GET /api/projects/([0-9a-f]{32})/knowledge-candidates",
                "evidence": "evidence:a01-a10-results.json#results.A06_real_user_data;" + manual,
                "status": "PARTIAL",
                "basis": "「当前独立可运行」是可机验的：统一后端在没有 AAOS 的情况下跑通闭环（WORK 人工闭环测试全程不引用任何外部知识系统），"
                        "两张实测路由表中也不存在 AAOS 端点，保留的接缝是版本化的 KnowledgeCandidate 读面；真实用户数据迁移按 A06_real_user_data"
                        "登记为未运行，没有把未来接缝写成本轮依赖。" + PARTIAL_MARKER
                        + "「未来接缝」目前只有路由与合同：候选出口在本仓无具名断言（同 05 candidate 行），故不能标 VERIFIED。"},
        "E01": {"location": "AI-WORK-LAB_HANDOFF_20261029/12_来源基线.json:1",
                "evidence": "evidence:a01-a10-results.json#results.F01",
                "status": "IMPLEMENTED_VERIFIED",
                "basis": "本机增量已按 INTEGRATION_POLICY §4 重新核实（来源多于云端锚点 → 以本地现状为迁移来源，锚点仅作研究参照，不回退），"
                        "并落成逐文件覆盖登记 + 198 条去向 + F01 迁移注册表三条实测记录；来源基线是研究锚点而不是完成清单这一口径由该断言守住。"},
        "E02": {"location": "docs/CODEX-AUDIT-ENTRY.md:1", "evidence": "evidence:delivery-summary.json#conclusion",
                "status": "IMPLEMENTED_UNVERIFIED",
                "basis": "原型/实现/构建/运行/部署五态在本登记与 delivery-summary 中被分开记录（例如 U11 明写 HEAD unborn、"
                        "design-tools 明写登记不算连接、U15 明写审计在 owner 侧）；但「全交付状态和限制一致」需要跨文档一致性检查，"
                        "本仓无自动比对，故不标 VERIFIED，只把口径写死在每一行的依据里。"},
    }


# --------------------------------------------------------------------------
# row assembly
# --------------------------------------------------------------------------

def read_table(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def build_ui_rows() -> list[dict]:
    claims = ui_claims()
    rows, missing = [], []
    for index, row in enumerate(read_table(UI_TABLE), start=2):
        key = "%s:%s" % (row["来源仓"], row["原入口ID"])
        claim = claims.get(key)
        source_text = join_verbatim([row["原名称"], "→ " + row["拟融合位置"], "分期 " + row["分期"]])
        if claim is None:
            missing.append(key)
            claim = {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                     "basis": "生成器未对该行给出判定（不应发生：行数守卫会失败）"}
        result = reconcile("ui-entry", "04#L%d|%s" % (index, key), source_text, row["分期"], claim)
        result["来源仓"] = row["来源仓"]
        result["原入口ID"] = row["原入口ID"]
        result["原名称"] = row["原名称"]
        result["拟融合位置"] = row["拟融合位置"]
        result["分期"] = row["分期"]
        result["来源表状态"] = row["状态"]
        rows.append(result)
    if missing:
        raise SystemExit("UNAUTHORED_UI_ROWS " + ",".join(missing))
    if len(rows) != len(claims):
        raise SystemExit("AUTHORED_KEYS_DO_NOT_MATCH_TABLE %d!=%d" % (len(rows), len(claims)))
    return rows


def build_family_rows() -> list[dict]:
    claims = family_claims()
    rows, missing = [], []
    for index, row in enumerate(read_table(FAMILY_TABLE), start=2):
        key = row["能力族ID"]
        claim = claims.get(key)
        source_text = join_verbatim([row["名称"], row["原拟处理"], row["拟模块边界"],
                                     "运行实现分期 " + row["运行实现分期"], "核心验收 " + row["核心验收"]])
        if claim is None:
            missing.append(key)
            claim = {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                     "basis": "生成器未对该能力族给出判定（不应发生：行数守卫会失败）"}
        result = reconcile("capability-family", "05#L%d|%s" % (index, key), source_text,
                           row["运行实现分期"] + " " + row["保全批次"], claim)
        result["能力族ID"] = key
        result["名称"] = row["名称"]
        result["原拟处理"] = row["原拟处理"]
        result["拟模块边界"] = row["拟模块边界"]
        result["运行实现分期"] = row["运行实现分期"]
        result["核心验收"] = row["核心验收"]
        result["来源表状态"] = row["状态"]
        rows.append(result)
    if missing:
        raise SystemExit("UNAUTHORED_FAMILY_ROWS " + ",".join(missing))
    if len(rows) != len(claims):
        raise SystemExit("AUTHORED_KEYS_DO_NOT_MATCH_TABLE %d!=%d" % (len(rows), len(claims)))
    return rows


def build_requirement_rows() -> list[dict]:
    claims = requirement_claims()
    rows, missing = [], []
    for index, row in enumerate(read_table(REQUIREMENT_TABLE), start=2):
        key = row["需求ID"]
        claim = claims.get(key)
        source_text = join_verbatim([row["来源性质"], row["需求"], "交付或验收 " + row["交付或验收"]])
        if claim is None:
            missing.append(key)
            claim = {"location": ABSENT, "evidence": NO_EVIDENCE, "status": "GAP",
                     "basis": "生成器未对该需求给出判定（不应发生：行数守卫会失败）"}
        result = reconcile("requirement", "11#L%d|%s" % (index, key), source_text, "", claim)
        result["需求ID"] = key
        result["来源性质"] = row["来源性质"]
        result["需求"] = row["需求"]
        result["交付或验收"] = row["交付或验收"]
        rows.append(result)
    if missing:
        raise SystemExit("UNAUTHORED_REQUIREMENT_ROWS " + ",".join(missing))
    if len(rows) != len(claims):
        raise SystemExit("AUTHORED_KEYS_DO_NOT_MATCH_TABLE %d!=%d" % (len(rows), len(claims)))
    return rows


#: ``08_前后端交接约定.json`` spells identifiers as ``{task_id}``/``{attempt_id}``/
#: ``{result_id}`` while the live tables compile them as 32-hex capture groups. The
#: contract itself demands this be recorded rather than ignored ("实际路径有差异需记录兼容
#: 表"), so the check normalises the placeholder and requires the normalised pattern to
#: resolve in a live table -- and writes which form matched into the register. A proposal
#: that resolves only after normalisation is still a real route, but the difference is
#: reported instead of being silently smoothed over.
ID_PLACEHOLDER = re.compile(r"\{[A-Za-z_]+\}")
ID_CAPTURE_GROUP = "([0-9a-f]{32})"


def build_api_checks() -> list[dict]:
    document = json.loads(PROTOCOL_TABLE.read_text(encoding="utf-8"))
    proposals = document["api_proposals"]
    rows = []
    for index, proposal in enumerate(proposals, start=1):
        method, pattern, purpose = proposal[0], proposal[1], proposal[2]
        entry = live_routes().get((method, pattern))
        matched_via = "合同路径与实测路由逐字相同"
        live_pattern = pattern
        if entry is None and ID_PLACEHOLDER.search(pattern):
            normalized = ID_PLACEHOLDER.sub(ID_CAPTURE_GROUP, pattern)
            entry = live_routes().get((method, normalized))
            if entry is not None:
                live_pattern = normalized
                matched_via = ("占位符归一后命中：%s → %s（差异按合同要求记录，不视为无差异）"
                               % (pattern, normalized))
        handler = entry["handler"] if entry else None
        table = entry["table"] if entry else None
        handler_location = None
        if handler:
            handler_location = (find_definition(handler, "backend/v1.py")
                                or find_definition(handler, "backend/core/work_surfaces.py"))
        evidence = API_EVIDENCE.get("%s %s" % (method, pattern), NO_EVIDENCE)
        #: 当前实现位置 must be a *live* route, so the normalised pattern is what gets
        #: cited; the contract's own spelling stays in 路径 and the gap between the two
        #: stays in 匹配方式. Nothing here silently pretends the two are the same string.
        claim = {"location": "%s %s" % (method, live_pattern), "evidence": evidence,
                 "status": "IMPLEMENTED_VERIFIED" if entry and handler_location else "GAP",
                 "basis": ("合同条目在实测路由表中存在（%s），handler %s 定义在 %s；%s。匹配方式：%s"
                           % (table, handler, handler_location, purpose, matched_via))
                          if entry and handler_location else
                          ("%s %s 不在实测路由表中（含占位符归一后仍未命中），合同条目未落实"
                           % (method, pattern))}
        result = reconcile("api-contract", "08#api_proposals[%d]" % (index - 1),
                           join_verbatim([method, pattern, purpose]), "", claim)
        result["提案序号"] = index
        result["方法"] = method
        result["路径"] = pattern
        result["实测路由pattern"] = live_pattern
        result["匹配方式"] = matched_via if entry else "未命中"
        result["合同意图"] = purpose
        result["实测路由表"] = table or ""
        result["handler"] = handler or ""
        result["handler位置"] = handler_location or ""
        rows.append(result)
    return rows


#: Which in-repo test measures each proposed endpoint. Every entry is checked by the
#: builder: a name that does not resolve downgrades that row out of IMPLEMENTED_VERIFIED.
API_EVIDENCE = {
    "GET /api/v1/health": "tests/unified/test_v02_surface.py::test_health_is_real_service_metadata",
    "GET /api/v1/projects": "tests/unified/test_v02_surface.py::test_projects_register_and_read_back_both_sources",
    "GET /api/v1/capabilities": "tests/unified/test_v02_surface.py::test_capabilities_are_honest_and_derived;tests/unified/test_v09_honesty.py::test_unavailable_capabilities_carry_reasons",
    "GET /api/v1/connections": "tests/unified/test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe",
    "POST /api/v1/tasks": "tests/unified/test_v02_surface.py::test_write_boundary_unknown_project_and_kind",
    "GET /api/v1/tasks/{task_id}": "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart",
    "POST /api/v1/tasks/{task_id}/attempts": "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart;tests/unified/test_v05_rejections.py::test_stale_result_refused",
    "POST /api/v1/attempts/{attempt_id}/pack": "tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart;tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused",
    "POST /api/v1/attempts/{attempt_id}/handoff-declarations": "tests/unified/test_v05_rejections.py::test_import_before_declared_handoff_refused;tests/unified/test_v05_rejections.py::test_external_receipt_claim_is_not_declarable",
    "POST /api/v1/attempts/{attempt_id}/results": "tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused;tests/unified/test_v11_audit_rework.py::test_f02_design_result_with_wrong_bindings_and_dangerous_refs_is_refused",
    "POST /api/v1/results/{result_id}/verifications": "tests/unified/test_v11_audit_rework.py::test_f03_pinned_revision_that_moved_is_blocked_not_pass;tests/unified/test_v10_gate.py::test_gate_refuses_forged_result_and_verdict",
    "GET /api/v1/knowledge/search": "tests/unified/test_v06_knowledge.py::test_create_search_short_queries_and_no_result",
    "GET /api/v1/design/plans": "tests/unified/test_v02_surface.py::test_design_domain_read_routes_answer_real_data;tests/unified/test_v11_audit_rework.py::test_f03_separation_of_stages",
    "GET /api/v1/design/target-profiles": "tests/unified/test_v04_design_loop.py::test_target_profile_reference_must_address_a_real_profile",
    "GET /api/v1/improvements": "tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only",
}


# --------------------------------------------------------------------------
# writers
# --------------------------------------------------------------------------

#: Column order of the three registers: identity, then source, then verdict.
CSV_COLUMNS = ["来源行标识", "要求原文", "当前实现位置", "验证证据", "状态", "依据说明"]


def write_csv(rows: list[dict], path: Path, extra_columns: list[str]) -> None:
    fieldnames = ["来源行标识"] + extra_columns + ["要求原文", "当前实现位置", "验证证据",
                                                   "状态", "依据说明"]
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames, extrasaction="ignore",
                                lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def histogram(rows: list[dict]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["状态"]] = counts.get(row["状态"], 0) + 1
    return counts


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", type=Path, default=OUT_DIR)
    args = parser.parse_args(argv)

    ui_rows = build_ui_rows()
    family_rows = build_family_rows()
    requirement_rows = build_requirement_rows()
    api_rows = build_api_checks()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    write_csv(ui_rows, args.out_dir / "ui-entry-disposition.csv",
              ["来源仓", "原入口ID", "原名称", "拟融合位置", "分期", "来源表状态"])
    write_csv(family_rows, args.out_dir / "capability-family-register.csv",
              ["能力族ID", "名称", "原拟处理", "拟模块边界", "运行实现分期", "核心验收", "来源表状态"])
    write_csv(requirement_rows, args.out_dir / "requirement-traceability.csv",
              ["需求ID", "来源性质", "需求", "交付或验收"])

    document = json.loads(PROTOCOL_TABLE.read_text(encoding="utf-8"))
    v1_count, compat_count = route_counts()
    api_payload = {
        "schema": "ai-work-lab/api-contract-check/v1",
        "generated_at": now(),
        "source": "AI-WORK-LAB_HANDOFF_20261029/08_前后端交接约定.json",
        "protocol": document["protocol"],
        "source_status": document["status"],
        "method": "逐条与实测路由表比对（backend.v1.V1_ROUTES / design_lab.http_service.ROUTES），"
                  "再解析 handler 定义位置与具名测试；比对对象是路由表，不是文档叙述。",
        "live_route_counts": {"v1_routes": v1_count, "compat_routes": compat_count},
        "api_proposals_total": len(document["api_proposals"]),
        "path_differences": [
            {"提案": row["来源行标识"], "合同路径": row["路径"], "实测pattern": row["实测路由pattern"],
             "匹配方式": row["匹配方式"]}
            for row in api_rows if row["匹配方式"] != "合同路径与实测路由逐字相同"],
        "status_counts": histogram(api_rows),
        "checks": [{key: value for key, value in row.items() if not key.startswith("_")}
                   for row in api_rows],
    }
    (args.out_dir / "api-contract-check.json").write_text(
        json.dumps(api_payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8", newline="\n")

    registers = {
        "ui-entry-disposition.csv": ui_rows,
        "capability-family-register.csv": family_rows,
        "requirement-traceability.csv": requirement_rows,
        "api-contract-check.json": api_rows,
    }
    source_totals = {
        "ui-entry-disposition.csv": len(read_table(UI_TABLE)),
        "capability-family-register.csv": len(read_table(FAMILY_TABLE)),
        "requirement-traceability.csv": len(read_table(REQUIREMENT_TABLE)),
        "api-contract-check.json": len(document["api_proposals"]),
    }
    downgraded = [{"register": name, "row": row["来源行标识"],
                   "from": row["_authored_status"], "to": row["状态"]}
                  for name, rows in registers.items() for row in rows if row["_downgraded"]]
    summary = {
        "schemaVersion": "ai-work-lab/requirement-traceability/v1",
        "generated_at": now(),
        "live_route_counts": {"v1_routes": v1_count, "compat_routes": compat_count},
        "registers": {name: {"rows": len(rows), "source_rows": source_totals[name],
                             "reconciles": len(rows) == source_totals[name],
                             "status_counts": histogram(rows)}
                      for name, rows in registers.items()},
        "downgraded_rows": downgraded,
        "downgrade_count": len(downgraded),
        "unverified_claims": {
            "implemented_unverified": [row["来源行标识"]
                                       for rows in registers.values() for row in rows
                                       if row["状态"] == "IMPLEMENTED_UNVERIFIED"],
        },
        "note": "状态由位置/证据/分期/排除四项机验决定，文档叙述不参与；"
                "IMPLEMENTED_VERIFIED 只可能出现在锚点全部解析成功的行上。",
    }
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    ok = all(item["reconciles"] for item in summary["registers"].values())
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
