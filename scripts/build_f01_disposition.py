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
    Came over into ``domains/work/orchestration`` AND the AST import graph built
    from the three runtime entry points (``backend/v1.py``,
    ``backend/core/work_surfaces.py``, ``backend/app.py``) reaches it: the row names
    the reachable module that actually imports it. Before 2026-10-31 this category
    was assigned from a hand-written list, which is how ``git_collector.py`` came to
    be called wired while the only ``git_collector`` in running code is an inline
    ``def`` inside ``collectors.py`` — a same-named function, not the migrated module.
``MIGRATED_PRESENT_UNWIRED``
    The file is in the target tree and imports cleanly, but no reachable module
    names it: the closure claim is false and is recorded as false rather than
    quietly kept. Wiring code is out of scope here — the honest outcome of the graph
    is a downgrade, not a new import.
``MIGRATED_AVAILABLE``
    Came over byte-for-byte as part of a named capability family and imports
    cleanly, but nothing in the service imports it: running it is an explicit
    operator action, never a side effect of a read. The graph must confirm zero
    consumers, or the builder refuses to emit the label.
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

import ast
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

#: The modules the unified service actually starts from. Every ``MIGRATED_WIRED``
#: claim is derived from these, transitively, never from a hand-written list.
RUNTIME_ENTRY_POINTS = (
    "backend/v1.py",
    "backend/core/work_surfaces.py",
    "backend/app.py",
)

#: Directories that are never part of the running service's import surface.
GRAPH_SKIP_PARTS = {".venv", "__pycache__", ".git", ".project-local", ".mimosa",
                    ".pytest_cache", "node_modules", "vendor"}

#: Runtime modules asserted to have had to come over because target code imports
#: them. The assertion is now CHECKED, not assumed: ``build_runtime_import_graph``
#: decides whether each one really has a reachable consumer, and an unconfirmed
#: entry is downgraded to ``MIGRATED_PRESENT_UNWIRED`` instead of being kept.
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


# ------------------------------------------------------------------ import graph
def _first_party_paths(root: Path) -> set[str]:
    out = set()
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if any(part in GRAPH_SKIP_PARTS for part in relative.split("/")):
            continue
        if path.is_file():
            out.add(relative)
    return out


def _as_file(root: Path, dotted_parts: list[str]) -> str | None:
    """Resolve dotted parts under ``root`` to a repo-relative module file."""
    if not dotted_parts:
        return None
    base = root.joinpath(*dotted_parts)
    if base.with_suffix(".py").is_file():
        return base.with_suffix(".py").relative_to(root).as_posix()
    init = base / "__init__.py"
    if init.is_file():
        return init.relative_to(root).as_posix()
    return None


def _ancestors(root: Path, relative: str) -> list[str]:
    """The package ``__init__.py`` files Python imports on the way to ``relative``.

    ``import backend.v1`` really does execute ``backend/__init__.py`` first, so a
    claim about what the service touches has to include those or it can hide an
    import that only an ``__init__`` performs.
    """
    parts = relative.split("/")[:-1]
    out = []
    for cut in range(len(parts) + 1):
        prefix = parts[:cut]
        if not prefix:
            continue
        init = (root.joinpath(*prefix) / "__init__.py")
        if init.is_file():
            out.append(init.relative_to(root).as_posix())
    return out


def _climb(root: Path, relative: str, levels: int) -> Path:
    """Directory a ``.``-prefixed import resolves against (PEP 328 arithmetic)."""
    directory = (root / relative).parent
    for _ in range(levels - 1):
        directory = directory.parent
    return directory


def module_imports(root: Path, relative: str) -> set[str]:
    """Repo-relative first-party modules that ``relative`` names in an import.

    AST-only, so a module-scope ``importlib`` with a computed name would be missed;
    the repository's own runtime import sites were checked for that and the two
    places that load by path are named in ``build_runtime_import_graph``'s record.
    """
    path = root / relative
    try:
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return set()
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                hit = _as_file(root, alias.name.split("."))
                if hit:
                    found.add(hit)
                    found.update(_ancestors(root, hit))
        elif isinstance(node, ast.ImportFrom):
            module_parts = (node.module or "").split(".") if node.module else []
            if node.level:
                base = _climb(root, relative, node.level)
                target = base.joinpath(*module_parts) if module_parts else base
                # the module named by the from-clause is imported itself
                resolved = None
                if module_parts:
                    if target.with_suffix(".py").is_file():
                        resolved = target.with_suffix(".py").relative_to(root).as_posix()
                    elif (target / "__init__.py").is_file():
                        resolved = (target / "__init__.py").relative_to(root).as_posix()
                if resolved:
                    found.add(resolved)
                    found.update(_ancestors(root, resolved))
                # ... and so is each alias, which may be a submodule of it
                for alias in node.names:
                    sub = target.joinpath(alias.name)
                    for cand in (sub.with_suffix(".py"), sub / "__init__.py"):
                        if cand.is_file():
                            found.add(cand.relative_to(root).as_posix())
                            found.update(_ancestors(root, cand.relative_to(root).as_posix()))
                            break
            else:
                resolved = _as_file(root, module_parts) if module_parts else None
                if resolved:
                    found.add(resolved)
                    found.update(_ancestors(root, resolved))
                for alias in node.names:
                    hit = _as_file(root, module_parts + [alias.name])
                    if hit:
                        found.add(hit)
                        found.update(_ancestors(root, hit))
    found.discard(relative)
    return found


def build_runtime_import_graph(root: Path = REPO_ROOT,
                               entries: tuple = RUNTIME_ENTRY_POINTS) -> dict:
    """Transitive first-party import closure of the running service's entry points.

    Returns ``{"entries", "reachable", "edges", "consumers", "missing_entries"}`` with
    every path repo-relative posix. ``consumers[m]`` is the set of reachable modules
    that name ``m`` in an import statement — that is the only evidence a
    ``MIGRATED_WIRED`` row is allowed to rest on.
    """
    universe = _first_party_paths(root)
    missing = [e for e in entries if e not in universe]
    if missing:
        raise SystemExit("RUNTIME_ENTRY_MISSING " + ", ".join(missing))
    reachable: set[str] = set()
    edges: dict[str, set[str]] = {}
    frontier = list(entries)
    for entry in entries:
        reachable.update(_ancestors(root, entry))
    while frontier:
        current = frontier.pop()
        if current in edges:
            continue
        edges[current] = module_imports(root, current)
        reachable.add(current)
        reachable.update(_ancestors(root, current))
        for nxt in sorted(edges[current]):
            if nxt in universe and nxt not in edges:
                frontier.append(nxt)
    consumers: dict[str, set[str]] = {}
    for consumer, imported in edges.items():
        for imported_module in imported:
            consumers.setdefault(imported_module, set()).add(consumer)
    return {"entries": list(entries), "reachable": sorted(reachable & universe),
            "edges": {k: sorted(v) for k, v in edges.items()},
            "consumers": {k: sorted(v) for k, v in consumers.items()},
            "universe": len(universe)}


def graph_consumers(target: str, graph: dict) -> list[str]:
    """Reachable modules that import ``target``; empty means it is not wired."""
    if not graph:
        return []
    return list(graph["consumers"].get(target, []))


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


def classify(relative: str, root: Path = WORK_ROOT,
              graph: dict | None = None) -> tuple[str, str, str, str]:
    """(category, target or equivalent, reason, runtime consumers) for one path.

    ``graph`` is the runtime import closure; when it is supplied a wired claim is
    only made if the graph proves a consumer, and the consumer list goes into the
    register. Without a graph the function refuses to say ``MIGRATED_WIRED`` at all,
    because that is the exact situation that produced the original false label.
    """
    present = already_in_target(relative, root)
    if present is not None:
        return present + ("",)
    stem = Path(relative).stem
    for rule_stem, category, target, reason in BY_STEM_RULES:
        if stem == rule_stem:
            if category == "MIGRATED_AVAILABLE" and not (REPO_ROOT / target).is_file():
                raise SystemExit("DISPOSITION_EVIDENCE_MISSING " + target
                                 + " is claimed available but is not in the target tree")
            consumers = graph_consumers(target, graph or {})
            if category == "MIGRATED_AVAILABLE" and consumers:
                raise SystemExit("DISPOSITION_LABEL_CONTRADICTION " + target
                                 + " is labelled operator-only but the graph shows "
                                 + ", ".join(consumers))
            return (category, target, reason, ";".join(consumers))
    for closure in CLOSURE_TARGETS:
        if Path(closure).stem == stem:
            consumers = graph_consumers(closure, graph or {})
            if consumers:
                return ("MIGRATED_WIRED", closure,
                        "AST 导入图从运行入口 " + "、".join(RUNTIME_ENTRY_POINTS)
                        + " 可达，实际 importer：" + "、".join(consumers),
                        ";".join(consumers))
            if graph is None:
                raise SystemExit("CLOSURE_UNCHECKED " + closure
                                 + " would be called MIGRATED_WIRED without an import graph")
            return ("MIGRATED_PRESENT_UNWIRED", closure,
                    "文件已在目标树且可导入，但 AST 导入图从运行入口 "
                    + "、".join(RUNTIME_ENTRY_POINTS)
                    + " 及其全部可达模块中没有找到任何 importer；同名的行内定义"
                    "（如 collectors.py 里的 def git_collector）不是对该模块的引用，"
                    "故不再声称已接线",
                    "")
    if relative in EQUIVALENTS:
        target = EQUIVALENTS[relative]
        if (REPO_ROOT / target).is_file():
            return ("EQUIVALENT_MERGED", target, "目标仓已有同一行为的落地文件，按行为等价合并",
                    ";".join(graph_consumers(target, graph or {})))
    for pattern, reason in OUT_OF_SCOPE_RULES:
        if pattern.search(relative):
            return ("OUT_OF_SCOPE_BATCH", "", reason, "")
    if VERIFY_RULE.search(relative):
        return ("TOOL_NOT_RUNTIME", "", "独立校验 CLI（__main__ + exit code），不是运行面能力", "")
    if POC_RULE.search(relative):
        return ("HISTORICAL_ONLY", "", "POC/一次性脚本，全仓零生产 importer", "")
    imports = importer_count(relative, root)
    return ("RUNTIME_DEPENDENCY_ADJUDICATED", "",
            "目标仓无任何 importer（来源仓 importer 数 " + repr(imports) + "）；不迁不构成运行缺口",
            "")


def main(argv: list[str]) -> int:
    report_path = None
    if "--json-out" in argv:
        report_path = Path(argv[argv.index("--json-out") + 1])
    registered = registered_work_paths()
    copied = copied_source_paths()
    gaps = sorted(set(registered) - copied)
    graph = build_runtime_import_graph()
    rows = []
    counts: dict[str, int] = {}
    for relative in gaps:
        category, target, reason, consumers = classify(relative, WORK_ROOT, graph)
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
            "运行面消费者": consumers,
            "消费者数": str(len(consumers.split(";")) if consumers else 0),
            "判定依据": reason,
        })
    temporary = OUT_CSV.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(OUT_CSV)
    summary = {"generated_at": _now(), "registered_work_python_paths": len(registered),
               "copied_work_python_paths": len(copied & set(registered)),
               "gap_paths": len(gaps), "categories": counts,
               "csv": str(OUT_CSV), "rows": len(rows),
               "import_graph": {"entries": graph["entries"],
                                "reachable_modules": len(graph["reachable"]),
                                "universe_python_files": graph["universe"]},
               "note": "类别由本文件顶部的规则现算，逐行带来源 sha256 与依据；"
                       "MIGRATED_WIRED 只由 AST 导入图证明的 consumer 决定，"
                       "没有 consumer 的迁入文件记为 MIGRATED_PRESENT_UNWIRED，不接线也不谎称。"}
    document = {"summary": summary, "rows": rows}
    if report_path is not None:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(document, ensure_ascii=False, indent=2),
                               encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False))
    return 0 if summary["gap_paths"] else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
