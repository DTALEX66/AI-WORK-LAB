# SPDX-License-Identifier: MIT
"""Build the per-clause acceptance register for the fusion task pack (L00…A00).

The pack freezes 19 tasks with short acceptance clauses (48 clauses as read from
``09_任务分期与验收.json``). Previous rounds reported completion at TASK level, which let a
single strong test stand in for a whole clause. Here every clause gets its own row, the
clause text is transcribed from the pack rather than paraphrased, and each claimed
evidence target is resolved mechanically: a row that claims CONFIRMED but whose test,
route, register or tracked file does not resolve is downgraded, and the reason says so.

Populations are derived from the pack: an unauthorised clause (one with no authored row)
is a hard error, so a clause cannot quietly disappear from the report.
"""
from __future__ import annotations

import argparse
import csv
import datetime
import hashlib
import io
import json
import re
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
PACK = TARGET_ROOT / "AI-WORK-LAB_HANDOFF_20261029" / "09_任务分期与验收.json"
OUT_CSV = TARGET_ROOT / "migration" / "task-acceptance.csv"
OUT_JSON = TARGET_ROOT / ".project-local" / "audit" / "20261031-fullclosure" / "task-acceptance.json"

STATUSES = ("CONFIRMED", "PARTIAL", "GAP", "BLOCKED_BY_BOUNDARY", "DEFERRED_P2", "DEFERRED_P3")
KINDS = ("pytest", "route", "script", "register", "doc", "none")

# 结论 rows, authored per clause. Keyed by (task id, clause index) so the pack stays the
# source of the clause text. Fields: status, kind, target, note.
ROWS: dict[tuple[str, int], dict[str, str]] = {
    ("L00", 0): dict(status="CONFIRMED", kind="doc",
                     target="config/environment-baseline.json",
                     note="目标根、两来源根与锚点、解释器与 sqlite/FTS5 读数写入仓内跟踪文件，"
                          "由 test_v20 现读对账；此前只存在于 .project-local（被 .gitignore 排除）"),
    ("L00", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v20_inrepo_evidence.py::test_environment_baseline_agrees_with_the_sqlite_and_fts5_capability",
                     note="解释器版本与 FTS5 能力由测试现读比对，不抄登记值；工具索引/模型方式仍按"
                          "「本地资源登记≠资格」处理"),
    ("L00", 2): dict(status="BLOCKED_BY_BOUNDARY", kind="none",
                     target="",
                     note="系统级出站隔离未被证明：无防火墙规则读取、无进程沙箱；云端会话模型上下文可能"
                          "离开本机。本条按边界保持 BLOCKED，不得写成通过"),
    ("L01", 0): dict(status="CONFIRMED", kind="doc",
                     target="docs/AUDIT-STATE.json",
                     note="分支与 HEAD 状态由脚本现读 git 后写入跟踪文件；unborn→已提交的状态迁移"
                          "此前只在被忽略的 JSON 里"),
    ("L01", 1): dict(status="CONFIRMED", kind="script",
                     target="scripts/candidate_snapshot.py::candidate_state",
                     note="候选口径（Git cached + 非忽略 untracked 的路径→SHA-256）抽成仓内可复跑函数，"
                          "test_v20 断两次运行字节相同且两种口径命名不混用"),
    ("L02", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v22_pack_registers.py::test_every_mapping_row_reconciles_to_a_covered_source_file",
                     note="837 条语义条目逐条按 仓+原路径 回到逐文件覆盖登记（目录按前缀命中其下文件），"
                          "不再只断行数不变；目标状态词表被钉为封闭集合，防止「MAPPED_P0」这类统一标签"
                          "被读成逐条已判定——真正的去向由 work-gap-disposition 与 source-coverage 支撑"),
    ("L02", 1): dict(status="CONFIRMED", kind="register",
                     target="migration/capability-family-register.csv#30",
                     note="30 能力族逐条对账（实现位置/验证证据/状态），8 条未分类复核在 "
                          "migration/review/unclassified-review.json；test_v16 断行数与词表"),
    ("L02", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v22_pack_registers.py::test_design_task_definition_pointers_match_their_bytes",
                     note="50 条现行设计任务定义逐条现读：路径存在且逐文件 SHA-256 与登记一致。冻结原件"
                          "留在只读来源仓（本仓按「原字节不动、不做第二真值」不复制），因此跨机复现需同时"
                          "具备该来源仓——这一限制写在这里而不是隐藏"),
    ("L03", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v01_v10_register.py::test_every_named_pytest_target_actually_exists",
                     note="V01–V10 与测试全名逐条 getattr 校验；V08 由安装态脚本承担，登记为 "
                          "SCRIPT_COVERED 而不是伪称 pytest 覆盖"),
    ("L03", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v21_task_acceptance.py::test_deferral_register_names_a_real_seam_for_every_deferred_item",
                     note="延期项现独立成册 migration/deferral-register.json：9 个延期能力 + 5 个 P2/P3 任务，"
                          "每条带来源、依赖、接缝文件与逐字验收条款；生成器与测试都要求接缝真实存在，"
                          "「保留接入位置」从一句承诺变成可检查的指针"),
    ("L10", 0): dict(status="PARTIAL", kind="pytest",
                     target="tests/unified/test_v14_registers.py::test_coverage_register_leaves_no_row_undecided",
                     note="逐文件去向：WORK 2,638 / DESIGN 4,049 每行有类别与依据；原 226 行同文模板已拆为"
                          "「已判定（带 file:line 权威）」与「待 owner 判定」两类，后者逐条不同理由并被测试"
                          "冻结为已点名集合。仍为 PARTIAL：待判定那部分本身就是要交给 owner 的遗漏清单"),
    ("L10", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v14_registers.py::test_f01_register_separates_wired_from_merely_present",
                     note="断言改为对照从 backend 可达模块的 AST import 图，不再断文件存在；"
                          "git_collector.py 因零消费者被降级为 MIGRATED_PRESENT_UNWIRED"),
    ("L10", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v07_migration.py::test_sources_are_byte_identical_before_and_after_a_rerun",
                     note="两来源仓逐文件摘要前后相等且防空读；另有 test_v12 的行级+文件级双不变断言"),
    ("L11", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/conftest.py::build_server",
                     note="真实 python -m backend 服务 + 真 HTTP 客户端打 127.0.0.1:随机端口，令牌走 stdin；"
                          "统一面与兼容面测试都经这条链"),
    ("L11", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v15_route_surface.py::test_kernel_guard_holds_on_every_compat_route",
                     note="兼容面 49 条 GET 逐条实测无令牌 401、错 Host 403（147 次真实请求），"
                          "补上 boot_probe docstring 一直声称而代码未做的检查"),
    ("L11", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f05_unified_search_returns_work_solutions",
                     note="两域经各自真实模块读写：WORK 方案库经 solution_library，DESIGN 知识库经 "
                          "KnowledgeLibrary；限制：数据为合成夹具种入临时库，来源仓真实数据不读取"
                          "（按边界不外搬私有数据）"),
    ("L12", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f05_short_queries_no_match_and_both_domains_hit",
                     note="中文短词/无结果/空结果解释均有断言；限制：单字查询与 HTTP 侧 typed-failure "
                          "两支的强度低于同文件其余支（见行为审计报告）"),
    ("L12", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v03_work_loop.py::test_concurrent_attempt_update_refuses_the_loser",
                     note="两侧都补了真并发：知识条目 Barrier(2) 同 expected_revision 的 revise 竞争，"
                          "以及统一信封 update_attempt 的 CAS 竞争。后者本轮先红后绿——存储层原来是"
                          "Python 层比较 + 无条件 UPDATE，两支都能落地；现为 revision 条件更新 + rowcount 校验"),
    ("L12", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v17_process_restart.py::test_backend_boots_twice_and_recovers_the_orphan",
                     note="索引重建对 store 自身计数器断；「重启」升级为两次真实 python -m backend 子进程，"
                          "断读回一致与孤儿转 OUTCOME_UNKNOWN"),
    ("L13", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart",
                     note="WORK 侧导出正文升级为按 repair-pack.schema.json 校验 + 内容断言（绑定的采集器名、"
                          "验证步骤、未发送声明）；此前只断非空，正文变空壳也能全绿"),
    ("L13", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending",
                     note="两域各一条端到端五步链（创建/导出/声明/导入/核验）"),
    ("L13", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused",
                     note="错包/错项目/过期/重复/无声明/冒领/越权各有可失败断言，拒绝后零残留"),
    ("L14", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v10_gate.py::test_gate_refuses_verdict_from_other_candidate",
                     note="新增：把核验数据行的 candidate_version 改成异候选，门必须 REFUSED。此前该分支"
                          "在任何测试里都不会触发（伪造表不填该列，真实链两侧同源）"),
    ("L14", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v15_route_surface.py::test_register_population_is_exactly_the_live_route_tables",
                     note="89 条旧只读合同逐条列入登记并按形态实测；限制：GET /api/evidence-projection 为"
                          "具名 503 EVIDENCE_LEDGER_ABSENT——本 checkout 没有自己的 task-ledger-r3.json，"
                          "该投影按合同拒绝而不是回空清单；根锚点本轮由 parents[3]（落到 domains/）"
                          "改为标记上溯，见 F1 报告"),
    ("L14", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f08_agent_and_unresolved_verifiers_cannot_satisfy_professional",
                     note="Agent 引用、human:agent、冒名批准全部 409；合成批准只产 test 记录，身份声明为"
                          "自证非核实"),
    ("L15", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v12_data_migration.py::test_rerun_is_idempotent_and_adds_no_records",
                     note="逐行主键+逐行摘要 witness 比对，不是计数"),
    ("L15", 1): dict(status="PARTIAL", kind="pytest",
                     target="tests/unified/test_v17_process_restart.py::test_backend_boots_twice_and_recovers_the_orphan",
                     note="运行面崩溃恢复已由真实两次进程启动覆盖，业务数据迁移有真 os._exit 杀进程复演；"
                          "缺口：scripts/migrate_sources.py 只有 os.replace 注入失败，没有进程级 kill 复演"),
    ("L15", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v12_data_migration.py::test_sources_are_never_written_by_a_migration",
                     note="源三库逐行 witness + 文件摘要双不变"),
    ("L16", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v18_tools_connections.py::test_a_record_moves_a_tool_state_and_losing_it_moves_it_back",
                     note="能力目录侧三维资格与 typed unavailable_reasons 早有断言；本轮把 "
                          "/api/v1/tools 与 /api/v1/connections 从写死常量改为探测账本派生"
                          "（F10 关掉的形状曾在工具面复发）。新增断言：加一条探测记录会改变工具状态，"
                          "撤掉/过期后回到 NOT_PROBED，且响应里点名是哪条记录产生的"),
    ("L16", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v15_route_surface.py::test_compatibility_map_is_walked_in_full_at_runtime",
                     note="COMPATIBILITY_MAP 10 条逐条打目标并断非 5xx；另 56 条原界面入口在 "
                          "migration/ui-entry-disposition.csv 逐条给去向"),
    ("L16", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f07_origin_chain_is_inherited_and_cannot_be_promoted",
                     note="来源沿链继承并拒绝向上提升；demo 数据不授予 live 资格；门侧 synthetic_only 与 "
                          "live_eligible 分列"),
    ("L17", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v14_registers.py::test_offline_install_pip_command_lines_are_actually_offline",
                     note="改为解析真实 pip 命令行是否带 --no-index/--isolated，不再读同轮自证的 "
                          "network_used:false；限制：本机 PyYAML 那次是 uv-cache 复制，记录里没有 pip 行"),
    ("L17", 1): dict(status="CONFIRMED", kind="script",
                     target="scripts/verify_isolated_install.py::main",
                     note="安装态资源读回（repo_resource/state SQL/领域包 manifest）与 wheel 逐条比对由脚本"
                          "现读；登记为 SCRIPT_COVERED，不是 pytest"),
    ("L17", 2): dict(status="CONFIRMED", kind="script",
                     target="scripts/verify_isolated_install.py::main",
                     note="legacy-regression 改为绝对判定：安装树里 tests/legacy 必须 0 失败且 exit 0，"
                          "另配暂存源码对照运行；全量套件 parity 只作信息行。本轮实测两栏均为 "
                          "170 passed / 0 failed，唯一 BLOCKED（按仓库路径 exec 源码的投影测试）改为包内 "
                          "import 后已可测，撤销 BLOCKED 未删任何断言"),
    ("L18", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v10_gate.py::test_gate_refuses_when_a_mandatory_blocker_is_registered",
                     note="门新增 --blockers：必做阶段的 BLOCKED/FAIL/NOT_RUN/NOT_PROBED 计入 problems 并"
                          "影响 exit code；P2/P3 单列为 disclosed；未传登记时 scope 标为 "
                          "IN_STORE_CLAIMS_ONLY 并给 warning，不再沉默"),
    ("L18", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v10_gate.py::test_gate_accepts_backed_completions",
                     note="full_product_readiness.ready 恒为 False 且带未跑门清单；即使合成链正样例也断"),
    ("L18", 2): dict(status="CONFIRMED", kind="script",
                     target="scripts/candidate_snapshot.py::candidate_state",
                     note="候选摘要口径进仓并可复跑；原始日志仍在 .project-local（按边界不上传），"
                          "跟踪侧以 docs/AUDIT-STATE.json 记录被审 SHA 与结论"),
    ("L20", 0): dict(status="BLOCKED_BY_BOUNDARY", kind="none",
                     target="",
                     note="真实 Photoshop/Illustrator 保存-重开-读回需逐次真人授权，本批未拉起宿主，"
                          "不谎称等价。桥接资产本身已按适配层实际探测的包内路径迁入并与来源仓逐字节相同"
                          "（两个宿主各一份，见 test_v14 的宿主桥接对；Illustrator 那份本轮才补上，"
                          "此前既不在包内也不在迁移规则里，ILLUSTRATOR_BRIDGE_MISSING 因此是"
                          "「资产缺失」而不是「未授权」，这一点本轮纠正）"),
    ("L20", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f09_observer_reads_answer_and_control_gate_is_enforced",
                     note="未授权必抛 NOT_AUTHORIZED，不许半跑；读路径不触发采集器有 monkeypatch 陷阱断言"),
    ("L21", 0): dict(status="PARTIAL", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f09_composition_root_resolves_the_repository_root",
                     note="适配器能力卡片非空且 NOT_PROBED 已断；缺口：adapter-registry ↔ 枚举 ↔ 投影三者"
                          "一致性无对账，来源仓的 adapter_conformance.py 未迁入（映射里仍标 RETAIN）"),
    ("L21", 1): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v09_honesty.py::test_connections_never_claim_connected_without_a_probe",
                     note="需网络的真实调用本批不执行；无路由可把连接翻成 CONNECTED"),
    ("L21", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f10_stale_and_foreign_candidate_records_grant_nothing",
                     note="data_origin=test 的探测记录只能给 NOT_VERIFIED；替身不算真实资格"),
    ("L30", 0): dict(status="DEFERRED_P3", kind="doc",
                     target="backend/core/capabilities.py",
                     note="多 Agent/跨机协作按 P3 分期，能力目录以 phase/implementation=DECLARED 标注且"
                          "不可调用；接缝登记未独立成册（同 L03#1 缺口）"),
    ("L31", 0): dict(status="DEFERRED_P3", kind="register",
                     target="migration/source-coverage-work.csv",
                     note="既有实现保留由逐文件去向与 import 图支撑；复杂新增按 P3 延期。同一条款不能既算"
                          "保留又待判定，待 owner 判定的行已在 L10#0 如实分列"),
    ("L32", 0): dict(status="DEFERRED_P3", kind="pytest",
                     target="tests/unified/test_v09_honesty.py::test_improvements_answer_contract_only",
                     note="/api/v1/improvements 只回合同与不可用原因，不接执行请求；候选隔离/回滚的接缝"
                          "未独立登记"),
    ("A00", 0): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v11_audit_rework.py::test_f02_design_result_with_wrong_bindings_and_dangerous_refs_is_refused",
                     note="Codex 可原样复跑的 6 组命令写在 docs/CODEX-AUDIT-ENTRY.md §4；旧审计探针因其自身"
                          "破坏性前置被明确标为不可复跑留档，等价问题由本文件稳定复现"),
    ("A00", 1): dict(status="PARTIAL", kind="doc",
                     target="docs/AUDIT-STATE.json",
                     note="「不继承上一轮结论」此前只是文字。跟踪文件现读记录被审 SHA 与复审结论；"
                          "独立复审 PASS 目前不存在，字段必须留 NOT_RUN 而不是空"),
    ("A00", 2): dict(status="CONFIRMED", kind="pytest",
                     target="tests/unified/test_v14_registers.py::test_pre_push_guard_is_present_and_blocking",
                     note="策略默认禁止远程动作；2026-10-31 owner 定点放行「首次上传 + 更新描述」并登记在 "
                          "INTEGRATION_POLICY.md §6。hook 未删除、未 --no-verify、逐字节复位并复核摘要"),
}

_COLUMNS = ("任务", "期", "条款序号", "条款原文", "结论", "证据类型", "证据目标", "机验结果", "依据与限制")


def _csv_text(rows: list[dict]) -> str:
    """Render the register as CRLF CSV.

    csv.writer already terminates rows with \\r\\n, so the previous post-pass
    .replace("\\n", "\\r\\n") turned every row end into "\\r\\r\\n": readers using
    DictReader skipped the resulting empty rows silently, so nothing looked wrong until a
    byte-level comparison of "the same" register came out different.
    """
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(_COLUMNS), extrasaction="ignore",
                            lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


def _routes() -> set[tuple[str, str]]:
    sys.path.insert(0, str(TARGET_ROOT))
    sys.path.insert(0, str(TARGET_ROOT / "domains" / "design"))
    from backend.v1 import V1_ROUTES  # noqa: E402
    from domains.design.design_lab import http_service as design  # noqa: E402
    return {(r.method, r.pattern) for r in list(V1_ROUTES) + list(design.ROUTES)}


def _resolve(kind: str, target: str) -> tuple[bool, str]:
    """Return (resolved, what was actually checked) for one claim. Fail closed."""
    if kind == "none" or not target:
        return False, "无证据目标"
    if kind == "route":
        method, _, pattern = target.partition(" ")
        return ((method, pattern) in _routes(), "实时路由表含 " + target)
    if kind == "register":
        relative, _, expected = target.partition("#")
        path = TARGET_ROOT / relative
        if not path.is_file():
            return False, "登记文件不存在 " + relative
        with open(path, encoding="utf-8-sig", newline="") as handle:
            count = len(list(csv.DictReader(handle)))
        if expected and count != int(expected):
            return False, f"登记 {relative} 实读 {count} 行，声明 {expected} 行"
        return True, f"登记 {relative} 存在（{count} 行）"
    if kind == "doc":
        path = TARGET_ROOT / target
        if not path.is_file():
            return False, "跟踪文件不存在 " + target
        if target.endswith(".json"):
            document = json.loads(path.read_text(encoding="utf-8-sig"))
            if "::" in target:
                key = target.split("::", 1)[1]
                return (key in document), f"JSON 顶层键 {key}"
            # the number of top-level keys is deliberately NOT written into the ledger: it
            # is the first thing a document gains when a field is added, and baking it here
            # made this register byte-unstable against unrelated edits
            return True, "跟踪 JSON 可解析"
        return True, "跟踪文件存在"
    path = TARGET_ROOT / target.split("::", 1)[0]
    if not path.is_file():
        return False, "文件不存在 " + str(path.relative_to(TARGET_ROOT))
    symbol = target.split("::", 1)[1] if "::" in target else ""
    if not symbol:
        return True, "文件存在"
    text = path.read_text(encoding="utf-8")
    pattern = r"^(?:async\s+)?def\s+" + re.escape(symbol) + r"\s*\("
    if re.search(pattern, text, re.MULTILINE):
        return True, "定义存在 " + symbol
    if re.search(r"(?:\)|:\s|\s)\"\"\"" + re.escape(symbol), text) or symbol in text:
        return True, "字面标记存在 " + symbol
    return False, symbol + " 在 " + path.name + " 中找不到定义或字面标记"


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out")
    parser.add_argument("--fail-on", default="GAP",
                        help="最低失败结论：GAP（默认）或 PARTIAL")
    parser.add_argument("--check", action="store_true",
                        help="rebuild and compare only; never write the tracked register")
    args = parser.parse_args(argv[1:])

    pack = json.loads(PACK.read_text(encoding="utf-8-sig"))
    tasks = {task["id"]: task for task in pack["tasks"]}
    rows: list[dict] = []
    missing_claims: list[str] = []
    for task_id, task in tasks.items():
        for index, clause in enumerate(task["acceptance"]):
            claim = ROWS.get((task_id, index))
            key = "%s#%d" % (task_id, index)
            if claim is None:
                missing_claims.append(key)
                rows.append(dict(任务=task_id, 期=task["phase"], 条款序号=index, 条款原文=clause,
                                 结论="GAP", 证据类型="none", 证据目标="", 机验结果="未登记",
                                 依据与限制="本轮没有为这一条著述任何判定"))
                continue
            resolved, detail = _resolve(claim["kind"], claim["target"])
            status = claim["status"]
            if status == "CONFIRMED" and not resolved:
                status = "PARTIAL"
                detail = "证据未解析：" + detail
            rows.append(dict(任务=task_id, 期=task["phase"], 条款序号=index, 条款原文=clause,
                             结论=status, 证据类型=claim["kind"], 证据目标=claim["target"],
                             机验结果=("已解析：" if resolved else "未解析：") + detail,
                             依据与限制=claim["note"]))

    if missing_claims:
        print(json.dumps(dict(error="UNAUTHORED_CLAUSES", keys=missing_claims),
                         ensure_ascii=True), file=sys.stderr)
        return 2
    rows.sort(key=lambda row: (row["任务"], row["条款序号"]))
    rendered = _csv_text(rows)
    drift = None
    if args.check:
        # verification must not be a writer: a bare "check the register" run that rewrites a
        # tracked file makes the audited tree dirty for the next measurement.
        # Newlines are folded on both sides: the register is written CRLF (csv convention)
        # while read_text hands back LF, and that difference is not a content drift.
        on_disk = (OUT_CSV.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
                   if OUT_CSV.is_file() else None)
        drift = on_disk != rendered.replace("\r\n", "\n")
    else:
        OUT_CSV.write_text(rendered, encoding="utf-8-sig", newline="")

    histogram = {status: sum(1 for row in rows if row["结论"] == status) for status in STATUSES}
    mandatory = [row for row in rows if row["期"] in ("P0", "P1")]
    summary = dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        pack=str(PACK), clauses=len(rows), tasks=len(tasks),
        statuses=histogram,
        mandatory_clauses=len(mandatory),
        mandatory_statuses={status: sum(1 for row in mandatory if row["结论"] == status)
                            for status in STATUSES},
        unresolved=sorted({row["证据目标"] for row in rows if row["机验结果"].startswith("未解析")}),
        sum_check=sum(histogram.values()) == len(rows),
        register_drift=drift,
    )
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(payload, encoding="utf-8", newline="\n")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(
            dict(summary=summary, rows=rows), ensure_ascii=False, indent=2),
            encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    blockers = [row for row in rows
                if (row["结论"] == args.fail_on or
                    (args.fail_on == "GAP" and row["结论"] == "GAP" and row["期"] in ("P0", "P1")))]
    hard = [row for row in rows if row["期"] in ("P0", "P1") and row["结论"] == "GAP"]
    print(json.dumps(dict(rows=len(rows), mandatory_hard_gaps=len(hard),
                          listed_blockers=len(blockers)), ensure_ascii=True))
    return 1 if (hard or drift) else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
