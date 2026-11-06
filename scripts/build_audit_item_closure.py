# SPDX-License-Identifier: MIT
"""Build the tracked F01–F10 / A01–A10 closure register (handoff §七/§八.2).

The 2026-10-30 handoff asks, verbatim, for "一份新的 F01–F10 与 A01–A10/V01–V10 追
踪表", each item carrying ID、适用要求、根因/待核假设、实际修改文件与调用入口、当前
结果、独立命令与 cwd/解释器、真实 exit code、日志/产物路径、受测候选摘要、限制与下
一步, using only PASS/FAIL/BLOCKED/NOT_RUN/DEFERRED, with 测试/合成/真实来源 kept as a
separate column. That table existed only in ``.project-local/``, which ``.gitignore``
line 2 excludes, so a clone could not see it -- and could not even see what "F04" means.
This file moves the table into the candidate.

Division of labour, so no two registers own the same claim:

* the 48 task-pack clauses (L00…A00) belong to `migration/task-acceptance.csv`;
* the ten frozen acceptance ids V01…V10 belong to
  `tests/unified/test_v01_v10_register.py`, which resolves each id to a real callable
  test with importlib. This register cites those ids but does not restate them;
* the F/A closure table is owned here.

要求原文 is parsed from the definition files, never retyped: A01–A10 from the tracked
`03_CODEX_独立审计提示词.txt`, F01–F10 from the tracked verbatim extract
`14_CODEX返工项F01-F10_原文.txt` (the gitignored handoff's §四 lines 112–182, kept with
its source digest). Each row therefore carries where its own definition came from and
the digest of the file it was read out of, so editing a definition silently is visible.

当前结果 is authored per item, but a row may not say PASS unless its evidence target
resolves in this tree -- the same fail-closed resolver `build_task_acceptance_register`
uses. Exit codes, the measurement instant and the candidate digest come from the run
receipt `.project-local/audit/20261031-fullclosure/CLOSURE-STATE.json` when that receipt
is on this machine; where it is not (a fresh clone), the row says so instead of keeping
a stale number. 独立复审 is NOT_RUN for every row: an independent review of this
candidate has not happened, and a self-test may not write it.
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
sys.path.insert(0, str(TARGET_ROOT / "scripts"))

from build_task_acceptance_register import _resolve  # noqa: E402

PACK_DIR = TARGET_ROOT / "AI-WORK-LAB_HANDOFF_20261029"
A_SOURCE = PACK_DIR / "03_CODEX_独立审计提示词.txt"
F_SOURCE = TARGET_ROOT / "docs" / "CODEX_REWORK_ITEMS_F01-F10.md"
PACK_JSON = PACK_DIR / "09_任务分期与验收.json"
OUT_CSV = TARGET_ROOT / "migration" / "audit-item-closure.csv"
RECEIPT = (TARGET_ROOT / ".project-local" / "audit" / "20261031-fullclosure"
           / "CLOSURE-STATE.json")
#: The receipt is re-written in place by each measurement run, so "compare the register with
#: the newest receipt" is a loop: refreshing the receipt invalidates the register, which is a
#: tracked file, which moves the candidate the next receipt measures. The register therefore
#: names one archived receipt -- copied here under its own candidate digest -- and the guard
#: reads *that* file. A refresh no longer contradicts what is already published.
ARCHIVE_DIR = (TARGET_ROOT / ".project-local" / "audit" / "20261031-fullclosure"
               / "receipt-archive")

RESULTS = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "DEFERRED")
INDEPENDENT_REVIEW = "NOT_RUN"

#: Recorded independent reviews. A row may leave NOT_RUN only when a record names it -- and the
#: cell then carries the SHA that was reviewed and the reviewer's own tool, because 「不继承上一轮
#: 结论」 is worth nothing if the reading cannot be traced. Built by
#: scripts/build_independent_review_record.py from the reviewer's own output, never typed.
REVIEWS_JSON = Path(__file__).resolve().parents[1] / "config" / "independent-reviews.json"
_REVIEWS: dict | None = None


def independent_reviews() -> dict:
    global _REVIEWS
    if _REVIEWS is None:
        _REVIEWS = (json.loads(REVIEWS_JSON.read_text(encoding="utf-8-sig"))
                    if REVIEWS_JSON.is_file() else {"records": []})
    return _REVIEWS


def independent_review_for(identifier: str) -> str:
    for record in reversed(independent_reviews().get("records", [])):
        if identifier not in record.get("verified_items", []):
            continue
        problem = _review_record_is_traceable(record)
        if problem:
            # Named, and never a fallback to an older record's verdict: silently skipping an
            # untraceable record would let a stale PASS certify the row again.
            return "RECORD_UNTRACEABLE（%s）——这一格拿不到可核验的复审依据" % problem
        return "%s @ %s（%s 现读 %s；逐项见 %s）" % (
            record["verdict"], record["reviewed_sha"][:12], record["reviewer"],
            record["reviewed_at"], record["artifact"])
    return INDEPENDENT_REVIEW


#: The three answers an independent reviewer is allowed to give.
REVIEW_VERDICTS = ("PASS", "PASS_WITH_FINDINGS", "FAIL")
_ANCESTRY: dict[str, bool] = {}


def _review_record_is_traceable(record: dict) -> str | None:
    """Why this record may not certify a row, or ``None`` when it may.

    A record is somebody else's claim about a commit, and every row that inherits its verdict turns
    that claim into a project-level statement. So the two things that make it checkable are re-checked
    here rather than trusted from the file: the SHA is a full 40-hex commit id that is an ancestor of
    this checkout's HEAD, and the verdict is one of the three an actual reviewer may answer with.

    Independent review round 3 named the absence of this check as a blocker with a concrete plant --
    ``reviewed_sha`` of forty ``f`` characters came back as ``PASS @ ffffffffffff``. The recorder
    validates at write time; nothing validated at read time, which is the side that publishes.
    """
    sha = str(record.get("reviewed_sha") or "")
    if not re.fullmatch(r"[0-9a-f]{40}", sha):
        return "reviewed_sha 不是 40 位提交号：%s" % (sha[:16] or "空")
    if record.get("verdict") not in REVIEW_VERDICTS:
        return "verdict 不是复审者可答的三种之一：%r" % (record.get("verdict"),)
    if sha not in _ANCESTRY:
        _ANCESTRY[sha] = subprocess_ancestor(sha)
    if not _ANCESTRY[sha]:
        return "reviewed_sha 不在本检出历史里（不是 HEAD 的祖先）：%s" % sha[:12]
    return None
INTERPRETER = ".venv/Scripts/python.exe (CPython 3.13, 见 config/environment-baseline.json)"
CWD = "<REPO>"
UNMEASURED = "未在本机测量（收据 .project-local/audit/20261031-fullclosure/CLOSURE-STATE.json 不在 Git 内）"

_COLUMNS = ("ID", "系列", "适用要求", "定义出处", "定义文件摘要", "根因与待核假设",
            "实际修改文件与调用入口", "当前结果", "证据种类", "未验证子项", "独立复审",
            "独立命令", "cwd", "解释器", "真实exit_code", "测量时刻UTC", "受测候选摘要",
            "运行收据", "日志/产物路径", "机验证据目标", "机验结果", "限制与下一步")

SUITE_CMD = ("%PY% -B -m pytest tests\\unified tests\\legacy -q -p no:cacheprovider "
             "--basetemp .project-local\\runs\\codex-regression")
GATE_CMD = "%PY% -B scripts\\acceptance_gate.py <unified.sqlite3> --blockers config\\blocker-register.json"
BOOT_CMD = "%PY% -B -X utf8 scripts\\boot_probe.py"
MIGRATE_CMD = "%PY% -B -X utf8 scripts\\migrate_sources.py --plan"
INSTALL_CMD = ("%PY% -B -X utf8 scripts\\build_offline_install.py && %PY% -B -X utf8 "
               "scripts\\verify_isolated_install.py")


def _pytest(target: str, **kw) -> dict:
    return dict(kind="pytest", target=target, **kw)


# One authored judgement per id. kind/target feed the resolver; everything else is text.
ROWS: dict[str, dict] = {
    # ---------------------------------------------------------------- F01–F10 (返工项)
    "F01": dict(
        result="PASS", kinds="测试(合成夹具) + 逐文件真实来源摘要对账",
        root="审计时 198 个登记为 WORK 来源的 .py 路径不在复制清单里（本轮迁入 adapter_conformance.py 后为 197，去向登记、报告与文件三方现在按同一 population 对账，不再钉字面数）；composition_root 把仓库根算成 "
             "parents[2] 落到 domains/，两个发现模块 try-import 后为 None，软件投影恒空；"
             "migrate_sources 默认 rmtree 目标树，一次重跑能抹掉任何已存在的返工。",
        entry="scripts/migrate_sources.py（plan/apply 引擎）、scripts/migrate_work_modules.py、"
              "scripts/build_f01_disposition.py、migration/work-gap-disposition.csv、"
              "domains/work/orchestration/*（13 个迁入模块）、domains/work/control/composition_root.py、"
              "调用入口 GET /api/work/observer/snapshot|projection|solutions、"
              "POST /api/work/control/operations、GET /api/v1/knowledge/search",
        unverified="32 行来源去向待 owner 判定（WORK 18 / DESIGN 14）；真实用户数据迁移不在本项范围",
        cmd=SUITE_CMD, log="migration/work-gap-disposition.csv（197 行，逐行带去向）",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f01_registered_gap_paths_all_have_a_real_disposition"),
        limit="本项只宣称「197 条差额逐条有去向且去向可回读」，不宣称「无未解释缺口」——"
              "后者要等 owner 对 OWNER_DECISION_PENDING 逐行判定（任务条款 L10#0 仍 PARTIAL）。"
              "只读观察不启动采集器/不探测模型由 test_f01_read_path_starts_no_collector_and_opens_no_socket 钉住"),
    "F02": dict(
        result="PASS", kinds="测试(合成夹具)",
        root="结果入库校验只在 work pack 分支执行，设计域错项目/错任务/错尝试、旧时间、错版本、"
             "零摘要与 ../../*.ps1 引用仍能 201 入库。",
        entry="backend/v1.py 的统一结果入库合同（两域同一处强制）、POST /api/v1/results",
        unverified="真实用户结果导入=NOT_RUN；本项全部用合成夹具验证合同",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py -q -k f02",
        log="随全量回归一起产生（无独立产物文件）",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f02_design_result_with_wrong_bindings_and_dangerous_refs_is_refused"),
        limit="原审计只证明危险引用被接收，没有证明附件被执行；本项把「不执行附件」也写成断言"
              "（test_f02_attachment_is_never_executed_or_imported），并要求失败请求不留半条结果"),
    "F03": dict(
        result="PASS", kinds="测试(合成夹具)",
        root="完整包摘要与 plan detail 摘要口径不同，相等/不等两支都 PASS；包固定 revision 1，"
             "读到 revision 2 仍宣称修订 1 通过，实际未固定目标组合。",
        entry="backend/v1.py 技术核验分支（统一口径 + 不可变旧修订读回）、"
              "POST /api/v1/verifications/technical",
        unverified="作品生成/宿主产出=NOT_RUN（本项只验证方案包结构与引用口径，不宣称交付作品）",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py -q -k f03",
        log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f03_pinned_revision_that_moved_is_blocked_not_pass"),
        limit="方案保存、导出、结果导入、产物生成、技术验收、专业验收六件事被分别断言"
              "（test_f03_separation_of_stages）；合法旧修订仍可按合同精确读回，不是把旧版一律拒绝"),
    "F04": dict(
        result="PASS", kinds="测试(合成夹具) + 门禁实测",
        root="result 可绑定不存在的 attempt/pack，空命令/空证据、错 fingerprint、手写一行 PASS "
             "就能拿到 BACKED 且 exit 0；后来出现的 FAIL 不能阻止旧 PASS 继续支撑就绪判定。",
        entry="scripts/acceptance_gate.py（关联完整性、候选版本绑定、证据可读且适用、时序与当前有效性）、"
              "backend/core/unified_store.py 的写入约束",
        unverified="独立复审=NOT_RUN（门的输出只表达本批就绪，不替代 Codex 复审）",
        cmd=GATE_CMD, log="门禁 JSON 输出（本轮实测 verdict=REFUSED、exit 1，见 docs/CODEX-AUDIT-ENTRY.md §11）",
        claim=_pytest("tests/unified/test_v10_gate.py::test_gate_refuses_forged_result_and_verdict"),
        receipt_key="gate",
        limit="门本轮输出 REFUSED/exit 1 是「P0/P1 未全通过」的机器表达，不是本项失败；"
              "正例仍可通过由 test_gate_accepts_backed_completions 覆盖，历史 FAIL 阻断当前就绪由 "
              "test_latest_failure_stops_supporting_readiness 覆盖"),
    "F05": dict(
        result="PASS", kinds="测试(合成夹具，含真实格式夹具)",
        root="store_view(query='缓存') 能命中合成方案，但统一 HTTP 层调用不存在的 "
             "solution_library.search，丢弃已算出的结果并返回 unavailable/空列表；原 V06 只断言 "
             "solutions 字段存在。",
        entry="backend/v1.py 统一检索（调用真实签名）、domains/work/control/solution_library.py、"
              "GET /api/v1/knowledge/search、GET /api/v1/solutions/search",
        unverified="真实用户知识库内容=未使用（合成夹具），不外溢真实素材",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py -q -k f05",
        log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f05_unified_search_returns_work_solutions"),
        limit="命中要求被写成「种入真实格式方案后必须命中」，读失败被要求显式类型化而不是伪装成"
              "「无结果」（test_f05_read_failure_is_typed_never_an_empty_success）；1 字/2 字/无结果、"
              "修订冲突与进程重启读回均有断言"),
    "F06": dict(
        result="PASS", kinds="安装态实测（隔离目录，无网络） + 测试",
        root="仓库根没有 pyproject.toml/setup.py/setup.cfg，离线 pip --target 实际 not installable、exit 1；"
             "资源收录（13 领域包、schema、配置、宿主桥接）从未在切换 cwd、清除 PYTHONPATH 之后验收过。",
        entry="pyproject.toml、scripts/build_offline_install.py、scripts/verify_isolated_install.py、"
              "config/isolated-install-verdict.json（由脚本从安装报告现读生成）",
        unverified="克隆内不可复现该收据：安装树与原始报告留在 .project-local/build/（被 Git 排除），"
                   "克隆须按「独立命令」重建后才能核对；PyYAML 等依赖的离线可用性结论见收据 wheel 摘要",
        cmd=INSTALL_CMD, log="config/isolated-install-verdict.json（跟踪） + "
                             ".project-local/build/offline-*/verify-report.json（本机原始报告，Git 排除）",
        claim=dict(kind="doc", target="config/isolated-install-verdict.json"),
        limit="本轮实测：安装树 170 passed、overall PASS、blocked=[]；此前那条 BLOCKED"
              "（regression-path-loading-test）被撤销的方式是把按路径 exec 改成包内导入并要求绝对 0 失败，"
              "没有删除或放宽断言"),
    "F07": dict(
        result="PASS", kinds="测试(合成夹具) + 全链路重启读回",
        root="project 忽略 data_origin，而 task/result 标为 test 时 attempt 与技术/专业核验默认 live，"
             "等于允许把测试数据洗成真实证据。",
        entry="backend/v1.py、backend/core/unified_store.py 的来源沿链传播与提升拒绝；"
              "既有记录的保守兼容处理",
        unverified="真实用户库的历史记录批量改写=未做（边界：不无依据改真实数据）",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py -q -k f07",
        log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f07_origin_chain_is_inherited_and_cannot_be_promoted"),
        limit="用户传入 live 不能洗掉上游 test，跨链提升被拒绝（test_f07_verdict_and_result_never_escape_the_chain）；"
              "合成数据、模拟连接与「测试人工声明」都不能成为 live 证据或真实工具 VERIFIED"),
    "F08": dict(
        result="PASS", kinds="测试(合成夹具) + CLI 实测",
        root="verifier_ref='agent:codex-synthetic' 配 professional_verdict=PASS 即可让任务完成，"
             "非空字符串被当成具名真人。",
        entry="backend/v1.py 专业验收分支、scripts/human_approval.py（只接受具名真人的交互确认，"
              "管道 stdin 直接拒绝）、GET /api/v1/tasks 的专业验收投影",
        unverified="真人专业验收签字=NOT_RUN（本轮不存在任何真实专业 PASS；合成审批只产生 test 记录）",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py -q -k f08",
        log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f08_agent_and_unresolved_verifiers_cannot_satisfy_professional"),
        limit="按边界：QODER 不代签真实专业验收；身份无法确认时保持 PENDING，而不是补一个 "
              "human: 前缀就宣称已核实（test_f08_real_human_approval_cli_refuses_a_piped_stdin 实测 CLI 拒绝）"),
    "F09": dict(
        result="PASS", kinds="干净子进程实测 + 测试",
        root="干净子进程 import sidecar 报 canonical_store 不存在，只有在 pytest 先 import control_service "
             "注入路径时才表现为正常——入口可用性依赖偶然的导入顺序。",
        entry="domains/work/control/sidecar.py、domains/work/control/composition_root.py（仓库根锚点改为标记向上查找）、"
              "GET /api/work/observer/*（只读）、POST /api/work/control/operations（范围/状态/修订/权限校验）、"
              "SSE 事件面",
        unverified="真实宿主写入、外部 Agent 派发=BLOCKED/DEFERRED（Human Gate 与授权边界）；"
                   "HTTP 200 不被当作投影正确，本项读的是投影内容",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py -q -k f09",
        log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f09_clean_process_imports_the_work_entry_points"),
        limit="Observer 写请求被真实拒绝并留痕、Control 校验生效、composition_root 现读解析到仓库根；"
              "旧兼容消费者的映射在 migration/route-surface.csv 逐条登记（164 个端点全部实测）"),
    "F10": dict(
        result="PASS", kinds="测试(合成夹具) + 受控本地探测记录",
        root="纯函数常量、SQLite 文件存在或 FTS5 编译选项就能产生 VERIFIED；_derive 在 "
             "authorization=REQUIRED 时仍可给出 can_invoke=true。",
        entry="backend/core/capabilities.py（implementation/qualification/connection/authorization/"
              "dependency/data_origin 六面分离）、资格台账（绑定 candidate_version 摘要与 TTL）、"
              "GET /api/v1/tools、/api/v1/connections、/api/v1/capabilities",
        unverified="宿主/模型/外部执行器资格=NOT_PROBED（不拉起宿主）；已有内置本地操作只获得限定资格，"
                   "不因此升格为 VERIFIED",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py tests/unified/test_v18_tools_connections.py -q",
        log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f10_qualification_needs_a_probe_bound_to_this_candidate"),
        limit="过期/错候选/伪造记录都不授予资格，未知枚举与缺依赖 fail closed；"
              "同一份探测证据被所有派生面引用（test_evidence_added_by_a_probe_reaches_every_derived_surface），"
              "can_invoke=true 必然指向一条本路由可展示的记录"),
    # ------------------------------------------------------------- A01–A10 (审计项)
    "A01": dict(
        result="PASS", kinds="真实进程启动 + loopback HTTP 实测",
        root="待核假设：上一轮「启动成功」只看 200，未证明返回值来自实际模块/持久数据。",
        entry="python -m backend（统一 CLI）+ GET /api/health、/api/projects、/api/v1/capabilities、"
              "/api/v1/tools 与两域代表接口；scripts/boot_probe.py 逐路由执行",
        unverified="不代表所有 WORK 旧接口已完成融合；兼容面 89 条按 migration/route-surface.csv 单独判定",
        cmd=BOOT_CMD, log="migration/route-surface.csv（164 行逐路由实测判定）",
        claim=dict(kind="register", target="migration/route-surface.csv#164"),
        receipt_key="boot_probe",
        limit="独立复审=NOT_RUN；本轮新增：/api/health 在未构建 UI 的检出里不再谎报 store 故障"
              "（test_v24 三个用例双向钉住）"),
    "A02": dict(
        result="PASS", kinds="测试(合成维护场景) + 重启读回",
        root="待核假设：测试事件可能被当成真实用户交接。",
        entry="建任务→导出人工包→受控测试授权→标记为测试的人工交接→合法导入→独立核验→"
              "重启后按精确 ID 读回（backend/core/unified_store.py）",
        unverified="真实用户派发=NOT_RUN；测试授权明确记为 test，不冒充真人交接",
        cmd="%PY% -B -m pytest tests/unified/test_v03_work_loop.py -q", log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v03_work_loop.py::test_work_maintenance_loop_completes_and_survives_restart"),
        limit="本轮顺带修掉一处真实并发缺陷：attempt 更新原先读改写不判 rowcount，两个写入都报成功；"
              "现在 CAS 谓词为 WHERE revision=?，冲突方被拒（test_concurrent_attempt_update_refuses_the_loser）"),
    "A03": dict(
        result="PASS", kinds="测试(合成方案/目标组合)",
        root="待核假设：方案导出可能被当成「已生成作品」。",
        entry="真实方案修订与版本化目标组合绑定同一任务、技术核验按固定修订、专业验收默认 PENDING；"
              "POST /api/v1/design/*",
        unverified="作品生成与宿主可编辑性=NOT_RUN；本项只证明结构与引用绑定成立",
        cmd="%PY% -B -m pytest tests/unified/test_v04_design_loop.py -q", log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v04_design_loop.py::test_design_loop_keeps_professional_acceptance_pending"),
        limit="文档与断言均不宣称生成了作品；目标档案引用必须指向真实档案"
              "（test_target_profile_reference_must_address_a_real_profile）"),
    "A04": dict(
        result="PASS", kinds="测试(合成拒绝面) + 残留检查",
        root="待核假设：危险导入是否真的不执行、失败是否留半条记录。",
        entry="两域拒绝错绑定/旧版/过期/重复/伪摘要/无源版本/路径穿越/危险附件；"
              "backend/v1.py 入库前合同",
        unverified="不声称覆盖未知攻击面：本项按原审计列出的枚举逐项复现",
        cmd="%PY% -B -m pytest tests/unified/test_v05_rejections.py -q", log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v05_rejections.py::test_wrong_pack_and_wrong_project_results_refused"),
        limit="失败请求不留成功状态或半条结果由逐表行数核对；导入不执行附件脚本"),
    "A05": dict(
        result="PASS", kinds="测试(真实格式夹具) + 索引重建 + 重启",
        root="待核假设：检索「有字段」不等于「命中」。",
        entry="知识与方案两侧 1 字/2 字/无结果检索、修订与并发冲突、索引重建、服务重启后读回；"
              "GET /api/v1/knowledge/search",
        unverified="真实用户语料=未使用",
        cmd="%PY% -B -m pytest tests/unified/test_v06_knowledge.py -q", log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v06_knowledge.py::test_create_search_short_queries_and_no_result"),
        limit="统一端点必须合并两域命中（test_unified_search_endpoint_merges_both_libraries），"
              "不再只断言字段存在"),
    "A06": dict(
        result="PASS", kinds="源码迁入实测 + 业务数据合成迁移实测（两条分开）",
        root="原 A06/V07 只验证了源码复制，却把业务数据库迁移也填成 PASS；"
             "复制工具还会在失败前 rmtree 目标树。",
        entry="scripts/migrate_sources.py（plan/apply、write-then-move、--fail-after 进程级崩溃复演）、"
              "scripts/migrate_business_data.py（预检/范围/失败恢复/证据）",
        unverified="真实用户数据迁移=NOT_RUN（边界：不覆盖生产库、不动真实私有库；"
                   "test_real_private_source_root_is_blocked_with_the_authorization_text 证明默认拒绝）",
        cmd=MIGRATE_CMD, log="迁移计划 JSON（.project-local/runs/，Git 排除）+ migration/copies.json（跟踪）",
        claim=_pytest("tests/unified/test_v12_data_migration.py::test_injected_exception_rolls_back_every_target_then_retry_completes"),
        receipt_key="migration",
        limit="本轮补上进程级证据：--fail-after 在 os.replace 之前 os._exit(9)，实测崩溃点最多一个 "
              ".migrating、无目标被就地截断，续跑后与一次干净运行逐文件摘要相同"
              "（test_a_killed_migration_lands_the_same_bytes_as_a_clean_one）。"
              "来源两仓摘要在前后两次读数中不变（按字节，不是数脏文件数）"),
    "A07": dict(
        result="PASS", kinds="干净进程 + loopback HTTP 实测",
        root="待核假设：Observer 的只读是靠约定还是靠强制。",
        entry="domains/work/control/sidecar.py（只读入口）、POST /api/work/control/operations 的"
              "范围/状态/修订/权限校验、默认 loopback 绑定",
        unverified="公网绑定检查按启动参数与实读监听地址判定；未做系统级防火墙证明（任务条款 L00#2 仍 BLOCKED）",
        cmd="%PY% -B -m pytest tests/unified/test_v11_audit_rework.py -q -k f09",
        log="随全量回归一起产生",
        claim=_pytest("tests/unified/test_v11_audit_rework.py::test_f09_observer_writes_are_refused_and_recorded"),
        limit="Observer 写请求被真实拒绝并留痕；Control 的每次拒绝都带可判别的错误码"),
    "A08": dict(
        result="PASS", kinds="安装态实测（隔离目录） + 旧回归",
        root="待核假设：仓库根 import 成功不等于安装态可用。",
        entry="scripts/build_offline_install.py → scripts/verify_isolated_install.py；"
              "切换 cwd、清除人为 PYTHONPATH、按 __file__ 与 sys.path 证明导入来自安装目录",
        unverified="克隆内不可复现收据（安装树与被 Git 排除的报告在本机）；重建命令见「独立命令」",
        cmd=INSTALL_CMD, log="config/isolated-install-verdict.json（跟踪，由脚本现读生成）",
        claim=dict(kind="doc", target="config/isolated-install-verdict.json"),
        limit="本轮实测 170 passed / overall PASS / blocked=[]；13 领域包、schema、必需配置与相关旧回归"
              "都在安装态读回，不是在源码根读回"),
    "A09": dict(
        result="PASS", kinds="测试(合成状态) + 受控本地探测记录",
        root="待核假设：诚实状态是否只是常量。",
        entry="backend/core/capabilities.py 与资格台账：无宿主/无连接/无授权/延期/测试数据保持诚实资格，"
              "未知默认拒绝",
        unverified="宿主与模型的真实连接=NOT_PROBED（本批不拉起宿主、不探测模型）",
        cmd="%PY% -B -m pytest tests/unified/test_v18_tools_connections.py tests/unified/test_v09_honesty.py tests/unified/test_v27_adapter_conformance.py -q",
        log="config/adapter-conformance-verdict.json（三方对账判定，跟踪） + 随全量回归一起产生",
        claim=_pytest("tests/unified/test_v18_tools_connections.py::test_host_and_model_tools_never_inherit_a_local_probe"),
        limit="测试替身不赋予真实工具 VERIFIED；live/demo 数据不升级为真实证据；本轮另把 adapter-registry ↔ 枚举 ↔ 投影三方对账落成 config/adapter-conformance-verdict.json，并把两处无来源的 STATIC_PASS 降为 STATIC_UNVERIFIED；"
              "投影与台账逐工具一致（test_tool_states_match_the_ledger_on_disk_and_no_literal）"),
    "A10": dict(
        result="PASS", kinds="门禁实测 + 正/负例测试",
        root="待核假设：门的 exit 0 是否只由状态字段决定。",
        entry="scripts/acceptance_gate.py（--blockers 消费必做阻塞登记）、"
              "backend/core/unified_store.py 的完成支撑判定",
        unverified="完整产品就绪=另判（门的 batch_readiness 只表达本批）；独立复审=NOT_RUN",
        cmd=GATE_CMD, log="门禁 JSON 输出 + config/blocker-register.json（跟踪）",
        claim=_pytest("tests/unified/test_v10_gate.py::test_latest_failure_stops_supporting_readiness"),
        receipt_key="gate",
        limit="仅改生命周期、填 VERIFIED、伪回执、孤儿/跨任务引用、失效或错候选证据均非零拒绝；"
              "本轮把必做阶段的非通过条款接入阻断集，--blockers 缺席时显式标 "
              "IN_STORE_CLAIMS_ONLY 并给 warning，不再沉默"),
}

#: 每项在任务包/交接文档中适用的其它标识（不重述其判定，只标注关联）。
def _digest_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def _definitions() -> dict[str, tuple[str, str, str]]:
    """id -> (适用要求原文, 定义出处, 定义文件摘要). Parsed, never retyped."""
    found: dict[str, tuple[str, str, str]] = {}
    a_text = A_SOURCE.read_text(encoding="utf-8")
    for match in re.finditer(r"^(A\d{2}) (.+)$", a_text, re.MULTILINE):
        line = a_text[:match.start()].count("\n") + 1
        found[match.group(1)] = (match.group(2).strip(),
                                 A_SOURCE.relative_to(TARGET_ROOT).as_posix() + ":" + str(line),
                                 _digest_of(A_SOURCE))
    f_text = F_SOURCE.read_text(encoding="utf-8")
    headers = list(re.finditer(r"^(F\d{2})｜(.+)$", f_text, re.MULTILINE))
    for index, match in enumerate(headers):
        stop = headers[index + 1].start() if index + 1 < len(headers) else len(f_text)
        block = f_text[match.start():stop].strip()
        # the block already carries 位置/事实/要求/验收; the register quotes it whole so
        # that a reviewer reads the acceptance condition, not a paraphrase of it
        line = f_text[:match.start()].count("\n") + 1
        found[match.group(1)] = (block, F_SOURCE.relative_to(TARGET_ROOT).as_posix() + ":"
                                 + str(line), _digest_of(F_SOURCE))
    return found


def suite_is_green(document: dict) -> bool:
    """Did this measurement end with nothing failing? Absence of the field is not green either."""
    suite = document.get("suite") or {}
    return not suite.get("failed") and not suite.get("errors")


def _label(document: dict) -> str:
    suite = document.get("suite") or {}
    return "%s… @ %s (failed=%s errors=%s)" % (
        str(document.get("candidate_digest", ""))[:16], str(document.get("head_commit", ""))[:12],
        suite.get("failed", "?"), suite.get("errors", "?"))


def candidate_receipts() -> list[tuple[str, dict, Path]]:
    """Every measurement this machine could bind the register to, newest first, live included.

    The live ``CLOSURE-STATE.json`` is re-written by every run and the archive holds one copy per
    candidate digest, so both are candidates; `generated_at` decides the order because mtime
    follows copies. The path travels with the document, because archiving the chosen measurement
    means copying *that* file -- copying whatever happens to be live would publish one run's digest
    next to another run's bytes.
    """
    found: dict[str, tuple[str, dict, Path]] = {}
    sources = [("live", RECEIPT)]
    if ARCHIVE_DIR.is_dir():
        sources += [("archive", path) for path in ARCHIVE_DIR.glob("CLOSURE-STATE-*.json")]
    for origin, path in sources:
        try:
            document = json.loads(path.read_text(encoding="utf-8-sig"))
        except (OSError, ValueError):
            continue
        digest = str(document.get("candidate_digest", "")) or str(path)
        found.setdefault(digest, (origin, document, path))
    return sorted(found.values(),
                  key=lambda item: str(item[1].get("generated_at", "")), reverse=True)


def _receipt() -> tuple[dict, Path | None, list[str]]:
    """Choose which measurement the register may rest on: the newest one, and only a green one.

    Until this function existed, the choice was simply "whichever file is live". That let a
    re-publish bind every row to a run that ended in failures -- measured here, not argued: receipt
    #6 finished `5 failed`, I re-published the registers minutes later, and every row then cited a
    measurement that certified nothing. Thirteen gates stayed green through that, because
    ``--check`` reproduced the same red binding it was asked to verify; the only thing that noticed
    was a test inside the *next* full suite, 47 minutes into receipt #7. Refusing at write time
    costs milliseconds, and it turns `build_audit_item_closure.py --check` into the gate that says
    "this register is bound to a failed measurement" the second somebody tries to publish it.
    """
    skipped = []
    for origin, document, path in candidate_receipts():
        if not suite_is_green(document):
            skipped.append(_label(document))
            continue
        head = document.get("head_commit", "")
        if head and not subprocess_ancestor(head):
            # a candidate from another line of development is not a fallback; it is a different
            # subject, and reading it would describe bytes nobody measured together. Named in the
            # report instead of raised, because a stray archive from an old branch is a fact about
            # the archive directory, not a reason the builder may stop producing the register.
            skipped.append(_label(document) + "（不在本分支上）")
            continue
        return document, path, skipped
    return {}, None, skipped



def subprocess_ancestor(sha: str) -> bool:
    import subprocess
    finished = subprocess.run(["git", "merge-base", sha, "HEAD"], cwd=str(TARGET_ROOT),
                              capture_output=True, text=True, encoding="utf-8", errors="replace")
    return finished.stdout.strip() == sha


def _resolve_target(target: str) -> tuple[bool, str]:
    """Re-resolve a register cell without the caller having to remember its kind.

    The stored kind string is deliberately not trusted here: a row that labelled a CSV as
    ``pytest`` would then be checked by the wrong branch. The shape of the target says
    which predicate applies.
    """
    if not target:
        return False, "无证据目标"
    head, _, tail = target.partition("#")
    if tail and head.endswith(".csv"):
        kind = "register"
    elif "::" not in target and target.endswith((".json", ".md")):
        kind = "doc"
    else:
        kind = "pytest"
    return _resolve(kind, target)


def _row(identifier: str, claim: dict, definition: tuple[str, str, str],
         receipt: dict, archive: str) -> dict:
    authored = ROWS[identifier]
    resolved, detail = _resolve_target(claim["target"])
    step = authored.get("receipt_key")
    exit_code = measured_at = candidate = UNMEASURED
    if receipt:
        candidate = "%s… @ %s" % (receipt["candidate_digest"][:16], receipt["head_commit"][:12])
        measured_at = receipt["generated_at"]
        if step:
            exit_code = str(receipt[step]["exit_code"])
        elif identifier[0] == "F" or identifier[0] == "A":
            exit_code = str(receipt["suite"]["exit_code"]) + "（全量回归）"
    return dict(zip(_COLUMNS, [
        identifier,
        "Codex 审计返工项" if identifier[0] == "F" else "Codex 独立审计项",
        definition[0], definition[1], definition[2],
        authored["root"], authored["entry"], authored["result"], authored["kinds"],
        authored["unverified"], independent_review_for(identifier),
        authored["cmd"], CWD, INTERPRETER,
        exit_code, measured_at, candidate, archive, authored["log"], claim["target"],
        ("已解析：" if resolved else "未解析：") + detail,
        authored["limit"]]))


def _csv_text(rows: list[dict]) -> str:
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(_COLUMNS), extrasaction="ignore",
                            lineterminator="\r\n")
    writer.writeheader()
    for row in rows:
        writer.writerow(row)
    return buffer.getvalue()


#: Columns whose value is read out of the run receipt. A clone has no receipt, so `--check`
#: there compares every other column in full and says which four it exempted -- the numbers
#: stay the audit machine's, the claims stay everybody's, and nobody gets to pretend a clone
#: verified a figure it cannot see.
RECEIPT_COLUMNS = ("真实exit_code", "测量时刻UTC", "受测候选摘要", "运行收据")


def _without_receipt_columns(text: str):
    if text is None:
        return None
    parsed = list(csv.DictReader(io.StringIO(text, newline="")))
    for row in parsed:
        for column in RECEIPT_COLUMNS:
            row[column] = ""
    return _csv_text(parsed)


def _published_rows() -> list[dict]:
    if not OUT_CSV.is_file():
        return []
    with OUT_CSV.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def archived_receipt_copy(named: str):
    """The archived receipt the register names, or ``None`` where it was never written.

    This is the single lookup that decides whether the three receipt-derived columns can be
    reproduced on this machine -- a fresh clone has no local working directory, so the archived
    copy is not there either. It is a function so a test can drive the no-receipt branch by
    redirecting this call instead of retargeting ``TARGET_ROOT``, which half a dozen other reads
    depend on.
    """
    path = TARGET_ROOT / ".project-local" / "audit" / "20261031-fullclosure" / named
    return path if path.is_file() else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true",
                        help="rebuild and compare only; never write the tracked register")
    parser.add_argument("--json-out")
    args = parser.parse_args(argv[1:])

    definitions = _definitions()
    pack = json.loads(PACK_JSON.read_text(encoding="utf-8-sig"))
    frozen = set(pack.get("acceptance_ids", []))
    missing = sorted(set(ROWS) - set(definitions))
    if missing:
        print(json.dumps(dict(error="UNPARSED_DEFINITIONS", ids=missing), ensure_ascii=True),
              file=sys.stderr)
        return 2
    unauthored = sorted(set(definitions) - set(ROWS))
    if unauthored:
        print(json.dumps(dict(error="UNAUTHORED_ITEMS", ids=unauthored), ensure_ascii=True),
              file=sys.stderr)
        return 2

    receipt, receipt_source, skipped_red = _receipt()
    if args.check and OUT_CSV.is_file():
        # Verify the binding the register actually declares -- but only if that binding is one the
        # builder is still allowed to make. Reproducing a red receipt because the published file
        # names one is how `--check` stayed green while the suite said the register certified nothing.
        named = _published_rows()
        values = {row.get("运行收据", "") for row in named}
        if named and len(values) == 1:
            value = values.pop()
            if value and not value.startswith("未在本机测量"):
                archived = archived_receipt_copy(value)
                if archived is not None:
                    document = json.loads(archived.read_text(encoding="utf-8-sig"))
                    head = document.get("head_commit", "")
                    if (not head or subprocess_ancestor(head)) and suite_is_green(document):
                        receipt, receipt_source = document, archived
    archive = UNMEASURED
    if receipt:
        archive = "receipt-archive/CLOSURE-STATE-%s.json" % receipt["candidate_digest"][:16]
        if not args.check:
            # --check is a reader; archiving is a write, and it belongs to the run that
            # publishes the register, not to every verification of it
            ARCHIVE_DIR.mkdir(parents=True, exist_ok=True)
            destination = ARCHIVE_DIR / Path(archive).name
            if receipt_source is not None and (
                    not destination.is_file()
                    or destination.resolve() != receipt_source.resolve()):
                # copy the bytes of the measurement being cited, not of whatever is live right now
                destination.write_bytes(receipt_source.read_bytes())
    rows = [_row(identifier, ROWS[identifier]["claim"], definitions[identifier], receipt,
                 archive)
            for identifier in sorted(ROWS)]
    # A PASS that names nothing it left out is not a reading, it is a claim of total completion, and
    # this register is the one every readiness sentence is quoted from. All twenty rows carry a named
    # unverified half today, but that was authoring discipline, not a check: the audit entry counted
    # "PASS 与待决并存" as three cells because nobody had ever asked the register how many there are.
    unscoped = [row["ID"] for row in rows
                if str(row["当前结果"]).startswith("PASS")
                and not str(row["未验证子项"] or "").strip()]
    if unscoped:
        print(json.dumps(dict(error="PASS_WITHOUT_A_NAMED_UNVERIFIED_SUBITEM", ids=unscoped),
                         ensure_ascii=False), file=sys.stderr)
        return 2
    downgraded = [row["ID"] for row in rows
                  if row["当前结果"] == "PASS" and row["机验结果"].startswith("未解析")]
    rendered = _csv_text(rows)
    drift = None
    exempted: list[str] = []
    if args.check:
        on_disk = (OUT_CSV.read_text(encoding="utf-8-sig").replace("\r\n", "\n")
                   if OUT_CSV.is_file() else None)
        if receipt:
            drift = on_disk != rendered.replace("\r\n", "\n")
        else:
            # no receipt here, so the three receipt-derived columns cannot be reproduced by
            # definition. Everything else must match byte for byte.
            exempted = list(RECEIPT_COLUMNS)
            drift = (_without_receipt_columns(on_disk.replace("\r\n", "\n")
                                             if on_disk else None)
                     != _without_receipt_columns(rendered.replace("\r\n", "\n")))
    else:
        OUT_CSV.write_text(rendered, encoding="utf-8-sig", newline="")

    summary = dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        items=len(rows), f_items=sum(1 for r in rows if r["ID"].startswith("F")),
        a_items=sum(1 for r in rows if r["ID"].startswith("A")),
        frozen_acceptance_ids=sorted(frozen),
        v_ids_owned_by="tests/unified/test_v01_v10_register.py",
        results={result: sum(1 for r in rows if r["当前结果"] == result) for result in RESULTS},
        independent_review_cell={state: sum(1 for r in rows
                                            if r["独立复审"].split(" @")[0] == state)
                                 for state in sorted({r["独立复审"].split(" @")[0] for r in rows})},
        independent_review_records=len(independent_reviews().get("records", [])),
        independent_review_items=sum(len(record.get("verified_items", []))
                                     for record in independent_reviews().get("records", [])),
        pass_with_unresolved=downgraded,
        receipt_present=bool(receipt),
        # Which measurements were looked at and refused. Without this the refusal is invisible: a
        # reader of a register bound to an older run cannot tell whether the newer one was red
        # (correct to skip) or simply never considered (a bug in the chooser).
        red_receipts_not_bound=skipped_red,
        receipt_columns_exempted=sorted(exempted),
        register_drift=drift)
    summary["verdict"] = ("DRIFT" if drift else
                          "NOT_OBSERVABLE_HERE" if args.check and not receipt else "MATCHES")
    if args.json_out:
        Path(args.json_out).write_text(json.dumps(dict(summary=summary, rows=rows),
                                                  ensure_ascii=False, indent=2),
                                       encoding="utf-8", newline="\n")
    print(json.dumps(summary, ensure_ascii=True, indent=2))
    if downgraded or drift:
        # a receipt that cannot be read never excuses a register that disagrees with its own
        # non-receipt columns, and never excuses a PASS that was downgraded to unresolved
        return 1
    if args.check and not receipt:
        # The three receipt-derived columns are exempted from the comparison by necessity, so a
        # clone answering 0 here would be a silent pass on the binding this register exists to
        # publish. The exemption is named and the exit code says what was not observable.
        return 3
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
