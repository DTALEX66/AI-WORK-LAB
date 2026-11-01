#!/usr/bin/env python
"""Make every path cited in the DEFAULT-LOAD documents followable from the repository root.

WUI-17's clause is narrow on purpose: "from now on only handle consumers that still affect default
loading". A document a new session is told to read is exactly such a consumer, and a citation it cannot
open is a dead end at the top of the chain. Measured 2026-10-10 across the seven documents the audit
bootstrap names: 167 backticked path citations, of which 30 were bare filenames or front-end-relative
shorthands (they resolve to a real file, but only for someone who already knows where to look) and 14 more
were ambiguous-by-name -- `BOUNDARY.md` exists under three service roots, so a reader cannot tell which one
the sentence means. Frozen history (`docs/history/**`, `taskpacks/history/**`) is NOT in scope: those files
are evidence about their own date, and rewriting them would be editing provenance.

This tool rewrites what resolves uniquely, and refuses on anything ambiguous or unresolved so a human
decision is recorded instead of guessed. Pass --apply to write.

usage: python scripts/audit/normalise_doc_citations.py [--apply]
"""
from __future__ import annotations

import os
import re
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# The order AGENTS.md prescribes for resolving authority, plus the round's own entry points.
SCOPE = (
    "AGENTS.md",
    "README.md",
    "WORK-LAB-AUTHORITY.md",
    ".project/governance/project-authority-index.json",
    "docs/current/DOCUMENT-CENSUS.md",
    # auditBootstrap step 5 is the CURRENT taskpack, which since 2026-10-19 is the authority-convergence
    # package. The superseded UI taskpack stays frozen history, not a document a new session is told to read.
    "taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md",
    # The live register is step 6 of auditBootstrap, so it is part of the chain a new session loads by
    # default; leaving it out of SCOPE meant the document that carries every citation this round wrote
    # was the one document nobody checked (measured 2026-10-10: 223 citations covered, register 0).
    "taskpacks/current/OPEN-TASK-REGISTER.md",
    # This round's own entry points: the convergence report and roadmap.
    "docs/current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md",
    "docs/current/authority-convergence-20261019/ROADMAP.md",
)
JSON_SCOPES = (".project/governance/project-authority-index.json",)

CITATION = re.compile(r"(?<![\w:./-])(?<!/)([A-Za-z0-9_][A-Za-z0-9_./\-]*\.(?:py|md|json|ya?ml|csv|tsx|ts|js|jsonl))"
                      r"(?::\d[\d,\-]*)?(?![\w./-])")
# A citation never means a frozen copy. History is evidence about its own date, so `project-authority-index.json`
# in a current document points at `.project/governance/`, not at the 2026-10-09 cutover tree -- yet both are
# on disk, which is what made those tokens look ambiguous. They still resolve when written as full paths.
HISTORY_PREFIXES = ("taskpacks/history/", "docs/history/", "reports/audit-archive/")
# Frozen trees and inbound reference copies stay citable as explicit paths but are never the meaning of a
# bare name: measured 2026-10-10, `.ui-reference/WORK-LAB/**` carries its own types.ts and navigation.ts,
# so widening the population made two honest citations read as ambiguous.
NOT_INDEXED_PREFIXES = HISTORY_PREFIXES + (".ui-reference/",)
# Filenames a sentence uses as a CLASS, not as one specific file: `SKILL.md` in "every managed skill's
# SKILL.md", `FROZEN.md` in "each frozen surface carries a FROZEN.md". They are legitimately unresolved, and
# a rule that forced a full path here would teach the document to lie about being generic.
# Each entry is validated as USED, so an allowance nobody needs any more turns the run red instead of
# rotting quietly -- the failure mode ERR-219 recorded for a stale standard row.
GENERIC_CITATIONS = {
    "SKILL.md": "类指：每个受管技能各有一份 SKILL.md（AGENTS.md「Managed global configuration」段）",
    "FROZEN.md": "类指：三处冻结面各有一份 FROZEN.md（DOCUMENT-CENSUS §7.3 已统一约定）",
    "FROZEN-MANIFEST.json": "类指：与 FROZEN.md 同批补的逐面清单",
    "BOUNDARY.md": "类指：services/{knowledge,evolution,memory} 各有一份边界说明",
    "ARCHIVE-INDEX.json": "类指：沿用 reports/audit-archive/20260930/ARCHIVE-INDEX.json 的字段约定",
    "README.md": "类指：目录级说明文件，非仓库根 README",
    "AGENTS.md": "类指：模块级 AGENTS（apps/observer、templates/agent-rules）与根 AGENTS 同形",
    "config.yaml": "非本仓文件：Hermes Home 的 live 配置（同段已写明不得整体 promote）",
    "auth.json": "非本仓文件：Hermes Home 的凭据存储；ERR-250 的读回正是声明**未读**它，把它改写为仓内路径等于凭空造出一个不存在的目标",
    "tauri.conf.json": "两个应用各有一份（apps/observer、apps/token-monitor），同段主语已指明",
    "design_tokens.json": "两份入册材料各带一份（record 20261009 与 record-20261010），比对对象就是这两份",
    "SOURCE-INTEGRITY.json": "每个 record-* 目录一份完整性清单，此处指本次那份",
    "project-authority-index.json": "机器权威与其冻结副本同名，同段已指明读的是 .project/governance 那一份",
    "ui_read_model.ts": "包内文件（v1 包 contracts/ui_read_model.ts），不是本仓源码；引用它是为了说明该字段只在包里有声明",
    "usage.jsonl": "类指：collect_usage_files 的输入文件名形状（TOKEN_FILE_NAME_RE 认 usage|token|tokens|usage_rollup 的 .json/.jsonl），仓内没有也不该有这一份固定文件",
    "package.json": "类指：npm 包清单的文件名形状；OPEN-TASK-REGISTER 用它说明\"正文里的通用文件名不该被机械改写为某一条路径\"，而仓内恰有一份 apps/observer/frontend/package.json 会被当作改写目标",
}
# Paths a sentence quotes in order to say they are WRONG -- a correction record has to name the bad path.
# Matched by the full citation token, not the basename, so an allowance can never excuse a different file
# that happens to share a name. Validated as USED, exactly like a class reference.
QUOTED_AS_ABSENT = {
    # 2026-10-19 归档规范化：以下名字指移动前的仓库根位置，正文按当时的文件名记录清点。
    # 它们的最终位置是 docs/history/archive/root-ui-records-20261019/（哈希见 MOVED-PATHS-20261019.json）。
    # 键按**整条引用**匹配、逐条带理由、不再被使用即转红；漏掉任一条，basename 兜底会把历史句子
    # 改成今天某个同名文件的路径，那是把判决从文档里抹掉。
    "ASSET_REPLACEMENT_MANIFEST.md":
        "2026-10-19 归档记录名：指移动前的仓库根文件，现位于 docs/history/archive/root-ui-records-20261019/",
    "HANDOFF-UI-L10B.md":
        "2026-10-19 归档记录名：指移动前的仓库根文件，现位于 docs/history/archive/root-ui-records-20261019/",
    "UI_DECISIONS.md":
        "2026-10-19 归档记录名：指移动前的仓库根文件；本仓另有 apps/observer/UI_DECISIONS.md 同名不同物，"
        "按 basename 改写会把一句 2026-10-10 的清点指到另一份文档",
    "UI_IMPLEMENTATION_REPORT.md":
        "2026-10-19 归档记录名：指移动前的仓库根文件，现位于 docs/history/archive/root-ui-records-20261019/",
    "UI_REFERENCE_MANIFEST.md":
        "2026-10-19 归档记录名：指移动前的仓库根文件，现位于 docs/history/archive/root-ui-records-20261019/",
    "VISUAL_QA_REPORT.md":
        "2026-10-19 归档记录名：指移动前的仓库根文件，现位于 docs/history/archive/root-ui-records-20261019/",
    "design.qa.yaml":
        "2026-10-19 归档记录名：指移动前的仓库根配置，现位于 docs/history/archive/root-ui-records-20261019/",
    "workflow-assistance-AGENTS.md":
        "2026-10-19 归档记录名：指移动前 docs/current/ 下的模块指令文件，现位于 "
        "docs/history/archive/workflow-assistance/module-instructions-20261019.md",
    "apps/observer/frontend/src/lib/shared_rule_adaptation.ts":
        "WUI-23 更正记录：这条引用从未存在于仓库，是被逐行核对后替换掉的错误路径本身",
    "test_observer_no_business_write.py":
        "WUI-24 更正记录：验收行原先指向这个不存在的测试，已改为 tests/workflow-assistance/test_wlgm_privacy.py",
    # ERR-247 更正记录：绑定矩阵里有六条引用带着不存在的目录。登记时必须把坏形状原样写出，否则
    # resolve() 的 basename 兜底会把它们改成正确路径——一段"这里写错了"的记录被工具改写成"这里是对的"，
    # 正是把判决从文档里抹掉。逐条按全 token 允许，且用后即检（不再被引用即转红）。
    "services/control/handoff.py":
        "ERR-247 更正记录：矩阵 B24/B37 曾以该目录引用 handoff.py，真实位置在 packages/client-neutral-core/scripts/",
    "services/orchestration/impact_planner.py":
        "ERR-247 更正记录：矩阵 B18/B21 曾以该目录引用 impact_planner.py，真实位置在 packages/client-neutral-core/scripts/",
    "services/orchestration/perf_baseline.py":
        "ERR-247 更正记录：矩阵 B40 曾以该目录引用 perf_baseline.py，真实位置在 packages/client-neutral-core/scripts/",
    "scripts/single_field_apply_loop.py":
        "ERR-247 更正记录：矩阵 B29/B31 曾以该目录引用 single_field_apply_loop.py，真实位置在 services/policy/",
    "src/usageCache.contract.test.tsx":
        "ERR-247 更正记录：矩阵 B08 曾把该测试写成 src/ 直属，真实位置在 apps/observer/frontend/src/views/",
    "packages/.../project_identity_resolver.py":
        "ERR-247 更正记录：矩阵 B18 用过这种省略号缩写路径，真实位置在 packages/client-neutral-core/scripts/",
    "OPEN-TASK-REGISTER.md":
        "收据字面量：收敛报告逐字引用 verify_project_authority_reference.py 的输出 register=OPEN-TASK-REGISTER.md；改成全路径就不是那条命令打印的字节了",
}
# Roots a document may cite relative to in prose. Only one candidate may exist for the rewrite to be safe.
PROSE_ROOTS = ("apps/observer/frontend/", "packages/client-neutral-core/", "services/", "scripts/",
               "docs/current/workflow-assistance/", "docs/current/", "docs/decisions/")
PRUNE = {".git", "node_modules", "dist", "target", "__pycache__", ".venv", "runs", "toolchains",
         "atlas-2026-09-29", "model-library", "worktrees", "quarantine", "wlc", "task-runtime",
         "pre-reinstall-archive-20261001"}
RUNTIME_ROOT = ".project-local"


def working_tree() -> tuple[set[str], dict[str, list[str]]]:
    """Every file a citation could mean, and a basename index. Runtime copies of the repo are excluded."""
    paths: set[str] = set()
    by_name: dict[str, list[str]] = defaultdict(list)

    def add(rel: str) -> None:
        if not rel or rel in paths:
            return
        paths.add(rel)
        if rel.startswith(NOT_INDEXED_PREFIXES):
            return  # kept as an explicit path, never offered as the meaning of a bare name
        by_name[Path(rel).name].append(rel)

    # The population is the checkout, not an allowlist of directories I happened to think of: the first
    # version walked SOURCE_DIRS and so `projections/agents/generate.py` -- a tracked file the register
    # cites -- measured as unresolved. Tracked bytes and walked bytes are unioned because each misses
    # what the other catches (an uncommitted new instrument; a file that is tracked but pruned from the walk).
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    if tracked.returncode == 0:
        for rel in tracked.stdout.decode("utf-8", "replace").split("\0"):
            if rel:
                add(rel.replace("\\", "/"))
    for dirpath, dirnames, filenames in os.walk(ROOT, onerror=lambda error: None):
        dirnames[:] = [name for name in dirnames if name not in PRUNE]
        relative = Path(dirpath).relative_to(ROOT)
        if relative == Path("."):
            dirnames[:] = [name for name in dirnames if name != RUNTIME_ROOT]
            for name in filenames:
                add(name)
            continue
        for name in filenames:
            add((relative / name).as_posix())
    return paths, by_name


def resolve(token: str, paths: set[str], by_name: dict[str, list[str]]) -> tuple[str, str]:
    """(state, value). state: ok | rewrite | ambiguous | unresolved."""
    if token.startswith(".project-local/"):
        # A runtime root is not checkout-verifiable (ERR-142). Where there is no runtime root at all, the
        # citation cannot be judged either way, so it is exempt -- but on the machine that wrote it, an
        # absent receipt is a fabrication and gets named.
        if (ROOT / token).is_file() or not (ROOT / ".project-local").is_dir():
            return "ok", token
        return "unresolved", ""
    if token in paths:
        return "ok", token
    for root in PROSE_ROOTS:
        if (root + token) in paths:
            return "rewrite", root + token
    hits = by_name.get(Path(token).name, [])
    if len(hits) == 1:
        return "rewrite", hits[0]
    if len(hits) > 1:
        return "ambiguous", ", ".join(sorted(hits))
    return "unresolved", ""


def run(apply: bool = False) -> dict:
    """Rewrite (or just report) and return the counts, so a test can assert the floor as well as the zero."""
    paths, by_name = working_tree()
    rewrites = 0
    checked = 0
    generic_used: set[str] = set()
    absent_used: set[str] = set()
    blockers: list[str] = []
    for doc in SCOPE:
        file_path = ROOT / doc
        if not file_path.is_file():
            blockers.append(f"{doc}: scoped document is missing")
            continue
        text = file_path.read_text(encoding="utf-8")

        def replace(match: re.Match) -> str:
            nonlocal rewrites, checked
            token = match.group(1)
            checked += 1
            # Checked FIRST: an allowlisted name is often one a mechanical rewrite would happily corrupt.
            # `config.yaml` in AGENTS.md means the live Hermes Home file; the only repo match is
            # `config/config.yaml`, and rewriting it there would state something false about ownership.
            if Path(token).name in GENERIC_CITATIONS:
                generic_used.add(Path(token).name)
                return match.group(0)
            if token in QUOTED_AS_ABSENT:
                absent_used.add(token)
                return match.group(0)
            state, value = resolve(token, paths, by_name)
            if state == "ok":
                return match.group(0)
            if state == "rewrite":
                rewrites += 1
                return match.group(0).replace(token, value, 1)
            shown = ", ".join(value.split(", ")[:3]) + ("…" if len(value.split(", ")) > 3 else "")
            blockers.append(f"{doc}:{text[:match.start()].count(chr(10)) + 1}: {token} "
                            f"-- {state}: {shown}")
            return match.group(0)

        new_text = CITATION.sub(replace, text)
        if apply and not blockers and new_text != text:
            file_path.write_text(new_text, encoding="utf-8", newline="\n")
    unused = sorted(set(GENERIC_CITATIONS) - generic_used)
    unused_absent = sorted(set(QUOTED_AS_ABSENT) - absent_used)
    return {"citations": checked, "rewritten": rewrites, "blockers": blockers,
            "genericAllowed": sorted(generic_used), "staleAllowances": unused,
            "absentAllowed": sorted(absent_used), "staleAbsentAllowances": unused_absent}


def audit(apply: bool = False) -> int:
    """The command-line report. The verdict is the exit code; a clean run writes nothing to stdout."""
    stats = run(apply=apply)
    for blocker in stats["blockers"]:
        print("BLOCK", blocker)
    for name in stats["staleAllowances"]:
        print(f"STALE_ALLOWANCE {name} -- no citation needs it any more, so delete the entry "
              "(an allowance nobody uses is how a rule stops meaning anything)")
    for name in stats["staleAbsentAllowances"]:
        print(f"STALE_ABSENT_QUOTE {name} -- nothing quotes this as a wrong path any more, so delete the "
              "entry; an allowance that excuses no current text will excuse a future real one")
    dirty = stats["blockers"] or stats["staleAllowances"] or stats["staleAbsentAllowances"]
    applied = apply and not dirty
    print(f"DOC_CITATIONS {'APPLIED' if applied else 'CHECKED'} docs={len(SCOPE)} "
          f"citations={stats['citations']} rewritten={stats['rewritten']} "
          f"blocked={len(stats['blockers'])} generic_allowed={len(stats['genericAllowed'])} "
          f"absent_quoted={len(stats['absentAllowed'])} "
          f"stale_allowances={len(stats['staleAllowances']) + len(stats['staleAbsentAllowances'])}")
    return 1 if dirty else 0


if __name__ == "__main__":
    raise SystemExit(audit(apply="--apply" in sys.argv))
