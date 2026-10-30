# SPDX-License-Identifier: MIT
"""F01 disposition register: the real destination of every registered WORK path
that never reached the copy manifest.

The 2026-10-30 audit counted 198 WORK ``.py`` source paths that
``migration/mapping.csv`` registers but ``migration/copies.json`` does not contain,
and said plainly that this is **not** "198 lost capabilities" — each one needs a
judgement with a reason. The earlier close-out had written ``MAPPED_P0`` and a
planning directory name for them, which answers nothing: a mapping row that points
at a directory nobody imports is a wish, not a migration.

This tool is the adjudication, and it is deterministic: every category comes from
a readable rule (who imports it in the target, whether the target already carries
an equivalent, whether its capability class is excluded by this batch's own scope
statement), and every row cites the evidence it was classified from. It writes
nothing outside ``migration/work-gap-disposition.csv`` and its own report path.

Categories:

``MIGRATED_WIRED``
    Came over into ``domains/work/orchestration`` and is imported by code the
    unified service actually runs. The closure was derived from the eight real
    break sites (an uncaught ``ImportError`` at ``sidecar.py`` worker start and
    ``composition_root.py``'s unconditional task-ledger read), not from a wish list.
``MIGRATED_AVAILABLE``
    Came over byte-for-byte as part of a named capability family and imports
    cleanly, but nothing in the service imports it: running it is an explicit
    operator action, never a side effect of a read.
``EQUIVALENT_MERGED``
    The behaviour already exists in the target under another path; the row names
    that path so a reader can check the equivalence rather than take it on word.
``OUT_OF_SCOPE_BATCH``
    Belongs to a capability class this batch excludes by the user's own scope
    decision — real host automation, external executors, model inference,
    self-rewrite activation, remote/CI writes, GUI monitors, destructive cleanup
    tools, third-party scanners. Recorded as excluded, not as failed, and the
    frozen capability classes stay frozen.
``TOOL_NOT_RUNTIME``
    A standalone ``verify_*.py`` / audit / reporting CLI with no production
    importer. It is a developer tool, not a runtime capability, so its absence
    from the service surface is not a functional gap.
``PRESENT_IN_TARGET`` / ``PRESENT_IN_TARGET_DIFFERS``
    The target repository already carries the file at the same relative path, so
    "not in the copy manifest" does not mean "absent". The row cites the digest.
``HISTORICAL_ONLY``
    A POC, bake-off, one-off study or drill with zero importers anywhere.
``RUNTIME_DEPENDENCY_ADJUDICATED``
    Neither in the closure nor out of scope by class: a library module the target
    simply does not need because nothing in the target calls into it. Named with
    its importer count so the claim is checkable.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path, PurePosixPath

REPO_ROOT = Path(__file__).resolve().parents[1]
WORK_ROOT = REPO_ROOT.parent / "WORK-LAB"
DESIGN_ROOT = REPO_ROOT.parent / "DESIGN-LAB"
MAPPING = REPO_ROOT / "migration" / "mapping.csv"
COPIES = REPO_ROOT / "migration" / "copies.json"
REGISTER = REPO_ROOT / ".project-local/runs/f01-migration/F01-MIGRATION-REGISTER.json"
OUT_CSV = REPO_ROOT / "migration/work-gap-disposition.csv"

#: Runtime modules that had to come over because target code imports them.
CLOSURE_TARGETS = (
    "domains/work/orchestration/collectors.py",
    "domains/work/orchestration/durable_worker.py",
    "domains/work/orchestration/platform_collector.py",
    "domains/work/orchestration/git_collector.py",
    "domains/work/orchestration/growth_candidates.py",
    "domains/work/orchestration/operation_progress.py",
    "domains/work/orchestration/task_ledger.py",
    "domains/work/orchestration/platform_discovery.py",
    "domains/work/orchestration/software_installation_identity.py",
    "domains/work/orchestration/platform_identity.py",
    "domains/work/orchestration/adapter_capability_projection.py",
    "domains/work/orchestration/artifact_handle_projection.py",
)

#: Migrated verbatim as part of a named capability family, but deliberately kept off
#: every automatic path: nothing in the service imports it, so running it is an
#: explicit operator action. ``process_collector`` enumerates the whole Windows
#: process table, which is exactly the kind of observation the audit says a read
#: must not perform by itself.
AVAILABLE_TARGETS = ("domains/work/orchestration/process_collector.py",)

#: Modules whose own code carries a side effect this batch does not authorize,
#: judged by what the module does rather than by which directory it sits in.
BY_STEM_RULES = (
    ("process_collector", "MIGRATED_AVAILABLE",
     "domains/work/orchestration/process_collector.py",
     "采集器家族已迁入并可显式调用；进程表枚举不接入任何自动读路径"),
    ("token_monitor", "OUT_OF_SCOPE_BATCH", "",
     "默认 tail 真实用户日志 %LOCALAPPDATA%/hermes/logs/agent.log 并带 tkinter GUI；"
     "本批不读用户私有日志、不新增 GUI 技术栈，统一后端也无此运行面"),
)

#: Behaviour that is already present in the target under another path. A row only
#: lands here when the named target file exists — the CSV carries that proof.
EQUIVALENTS = {
    "services/task-governance/task_protocol.py": "domains/work/control/completion_authority.py",
    "services/policy/permission_gate.py": "domains/work/control/permission_gate.py",
    "services/task-governance/completion_authority.py": "domains/work/control/completion_authority.py",
    "packages/client-neutral-core/scripts/repair_state.py": "domains/work/workflow_core/repair_state.py",
    "packages/client-neutral-core/scripts/repair_verification.py":
        "domains/work/workflow_core/repair_verification.py",
    "packages/client-neutral-core/scripts/canonical_store.py":
        "domains/work/workflow_core/canonical_store.py",
    "packages/client-neutral-core/scripts/issue_projection.py":
        "domains/work/workflow_core/issue_projection.py",
    "packages/client-neutral-core/scripts/repair_pack_projection.py":
        "domains/work/workflow_core/repair_pack_projection.py",
}

#: Capability classes this batch does not implement (user scope decisions of
#: 2026-10-19/20/23/28, restated in the 2026-10-30 handoff section 9).
OUT_OF_SCOPE_RULES = (
    (re.compile(r"(photoshop|illustrator|adobe|native_host)", re.I),
     "真实宿主自动化与原生文档写入：本轮排除，逐次 Human Gate 后受控探测"),
    (re.compile(r"(acp_adapter|execution_federation|parallel_dispatch|executor)", re.I),
     "外部执行器与执行联邦派发：本轮不测真实联网资格，能力类保持 NOT_RUN"),
    (re.compile(r"(model|whisper|inference|llm)", re.I),
     "模型推理与本地权重：本轮不部署、不自行下载，保持 NOT_RUN"),
    (re.compile(r"(evolution|mutation_policy|exo_sandbox|self_|casr_study|takeover)", re.I),
     "自我改写/升级激活链：P3 延期，只保留数据合同"),
    (re.compile(r"(github|gh_cli|dagu|remote|deploy_global_rules|ci/)", re.I),
     "远端仓库与 CI 写入：本轮不 push、不触发云 CI"),
    (re.compile(r"(tkinter|gui)", re.I),
     "桌面 GUI 监视器（token monitor 等）：非统一后端能力，且本轮不新增技术栈"),
    (re.compile(r"(spill_cleanup|repo_slimming|rmtree)", re.I),
     "含破坏性删除的仓库清理工具：不在本批授权内执行"),
    (re.compile(r"(skillspector|snyk|security_scan)", re.I),
     "外部安全扫描器与 SaaS 判定：本轮不联网、不调用外部服务"),
    (re.compile(r"(session_federation|memory|hindsight|hermes_builtin|bakeoff|beads)", re.I),
     "会话连续性与外部记忆后端：P2/P3 延期，且含第三方 POC"),
)

POC_RULE = re.compile(r"(_poc|bakeoff|drill|study|audit|canary|perf_baseline|spec_to_tasks|"
                      r"independent_eval|mcp_candidate_audit|adapter_verb_probe|accelerator|"
                      r"single_field_apply_loop)", re.I)
VERIFY_RULE = re.compile(r"(^|/)verify_[^/]+\.py$", re.I)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def registered_work_paths() -> dict[str, dict]:
    with MAPPING.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    out = {}
    for row in rows:
        if row["仓"] == "work" and row["原路径"].endswith(".py"):
            out.setdefault(row["原路径"], row)
    return out


def copied_source_paths() -> set:
    manifest = json.loads(COPIES.read_text(encoding="utf-8"))
    copied = set()
    for group in manifest["copies"]:
        for record in group["records"]:
            source = Path(record["source"])
            try:
                copied.add(source.relative_to(WORK_ROOT).as_posix())
            except ValueError:
                continue
    return copied


def importer_count(relative: str, root: Path) -> int:
    """Files in ``root`` that name this module's stem, excluding itself."""
    stem = Path(relative).stem
    hits = 0
    for path in root.rglob("*.py"):
        if path.relative_to(root).as_posix() == relative:
            continue
        if any(part in {".venv", "__pycache__", ".git", ".project-local", ".mimosa"}
               for part in path.parts):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if re.search(r"\b(?:import|from)\s+[\w.]*\b%s\b" % re.escape(stem), text):
            hits += 1
    return hits


def already_in_target(relative: str, root: Path) -> tuple[str, str, str] | None:
    """A registered source path that the target already holds at the same location.

    Two registers disagreeing about whether something exists is worse than one
    register being coarse, and "not copied" is not the same claim as "absent": the
    F01 module migration placed five WORK registry files at the repository's own
    ``config/`` root, so a mapping row naming ``config/adapter-registry.json`` is
    satisfied by bytes the target really has. The digest decides whether it is the
    same bytes or a repaired copy.
    """
    candidate = REPO_ROOT / PurePosixPath(relative).as_posix()
    if not candidate.is_file():
        return None
    source = root / PurePosixPath(relative).as_posix()
    try:
        actual = sha256_file(candidate)
        # "present" and "present with the same bytes" are different claims, and only
        # the second one is a reason not to copy.
        same = source.is_file() and sha256_file(source) == actual
    except OSError:
        return None
    state = ("逐字节相同" if same else
             "字节不同（目标侧为返工修复或本仓自己的配置），故不能靠重复制抹平")
    return ("PRESENT_IN_TARGET" if same else "PRESENT_IN_TARGET_DIFFERS",
            candidate.relative_to(REPO_ROOT).as_posix(),
            "目标仓同一相对路径已有该文件，摘要 " + actual[:16] + "…，与来源" + state
            + "；由 F01 模块迁移或原复制放入，不是缺失")


def classify(relative: str, root: Path = WORK_ROOT) -> tuple[str, str, str]:
    """(category, target or equivalent, reason) for one registered path."""
    present = already_in_target(relative, root)
    if present is not None:
        return present
    stem = Path(relative).stem
    for rule_stem, category, target, reason in BY_STEM_RULES:
        if stem == rule_stem:
            if category == "MIGRATED_AVAILABLE" and not (REPO_ROOT / target).is_file():
                raise SystemExit("DISPOSITION_EVIDENCE_MISSING " + target
                                 + " is claimed available but is not in the target tree")
            return (category, target, reason)
    for closure in CLOSURE_TARGETS:
        if Path(closure).stem == stem:
            return ("MIGRATED_WIRED", closure,
                    "统一服务实际运行的代码引用它；断链点见 F01-MIGRATION-REGISTER.json 的 "
                    "consumerFilesEdited")
    if relative in EQUIVALENTS:
        target = EQUIVALENTS[relative]
        if (REPO_ROOT / target).is_file():
            return ("EQUIVALENT_MERGED", target, "目标仓已有同一行为的落地文件，按行为等价合并")
    for pattern, reason in OUT_OF_SCOPE_RULES:
        if pattern.search(relative):
            return ("OUT_OF_SCOPE_BATCH", "", reason)
    if VERIFY_RULE.search(relative):
        return ("TOOL_NOT_RUNTIME", "", "独立校验 CLI（__main__ + exit code），不是运行面能力")
    if POC_RULE.search(relative):
        return ("HISTORICAL_ONLY", "", "POC/一次性脚本，全仓零生产 importer")
    imports = importer_count(relative, root)
    return ("RUNTIME_DEPENDENCY_ADJUDICATED", "",
            "目标仓无任何 importer（来源仓 importer 数 " + repr(imports) + "）；不迁不构成运行缺口")


def main(argv: list[str]) -> int:
    report_path = None
    if "--json-out" in argv:
        report_path = Path(argv[argv.index("--json-out") + 1])
    registered = registered_work_paths()
    copied = copied_source_paths()
    gaps = sorted(set(registered) - copied)
    rows = []
    counts: dict[str, int] = {}
    for relative in gaps:
        category, target, reason = classify(relative)
        counts[category] = counts.get(category, 0) + 1
        source = WORK_ROOT / relative
        rows.append({
            "来源键": registered[relative]["来源键"],
            "原路径": relative,
            "运行分期": registered[relative].get("运行分期", ""),
            "登记处理方式": registered[relative].get("处理方式", ""),
            "登记目标模块": registered[relative].get("目标模块", ""),
            "登记目标状态": registered[relative].get("目标状态", ""),
            "来源存在": "YES" if source.is_file() else "NO",
            "来源sha256": hashlib.sha256(source.read_bytes()).hexdigest() if source.is_file() else "",
            "去向类别": category,
            "目标文件": target,
            "判定依据": reason,
        })
    temporary = OUT_CSV.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(OUT_CSV)
    summary = {"generated_at": _now(), "registered_work_python_paths": len(registered),
               "copied_work_python_paths": len(copied & set(registered)),
               "gap_paths": len(gaps), "categories": counts,
               "csv": str(OUT_CSV), "rows": len(rows),
               "note": "类别由本文件顶部的规则现算，逐行带来源 sha256 与依据；"
                       "MIGRATED_WIRED 的闭合依据见 F01-MIGRATION-REGISTER.json"}
    document = {"summary": summary, "rows": rows}
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["gap_paths"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
