#!/usr/bin/env python3
"""Verify typed cross-module dependencies, and reconcile the declared edges against real imports.

Shape validation alone was the defect: the manifest said `runtimeEdges: []` and "runtime coupling
forbidden" while four tracked observer files import workflow-assistance code at runtime. A manifest
that is never read against the tree is a description, not a gate, so the declared edge set and the
measured edge set must now agree in BOTH directions — an undeclared import and a declaration whose
import is gone are both red.

Scanned coupling forms (the three the tree actually uses):
  * `import X` / `from X import ...` where X resolves to a module file under the other canonical root;
  * `sys.path.insert|append|extend(...)` pointing into the other root — that line is what makes the
    bare-stem import on the next line resolve at all;
  * `importlib.util.spec_from_file_location(name, <path>)` loading a file out of the other root,
    including when the path reaches the call through a module-level constant.

Only files inside a canonical module root are scanned, and only imports that resolve into the other
canonical root are edges: `scripts/`, `services/`, `integrations/` and `tests/` are supporting source
surfaces, not module roots (machine authority: `.project/governance/module-ownership.json`), so a
repo-owned script reaching into `packages/client-neutral-core/scripts` is not a cross-MODULE edge.
"""
from __future__ import annotations

import argparse
import ast
import json
import subprocess
import sys
from pathlib import Path, PurePosixPath

EXPECTED_MODULES = {
    "workflow-assistance": "packages/client-neutral-core",
    "work-lab-observer": "apps/observer",
}
TYPES = {"governance", "runtime", "build", "handoff", "observed-by", "fixture", "archive-of"}
# Directories a filesystem fallback scan must never treat as source: they are build output or vendored
# trees, and `git ls-files` already excludes them. Kept in sync with the tracked-source rule.
SKIP_DIRS = {"node_modules", "target", "dist", "build", "__pycache__", ".venv", "venv", ".git"}
SYSCALLS = ("insert", "append", "extend", "remove")
PATH_LOADERS = ("spec_from_file_location", "spec_from_loader", "SourceFileLoader")


def verify(root: Path) -> list[str]:
    errors: list[str] = []
    path = root / ".project/governance" / "module-dependencies.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"unreadable: {exc}"]
    modules = data.get("modules")
    if not isinstance(modules, dict) or set(modules) != set(EXPECTED_MODULES):
        return ["modules must exactly match the two canonical active modules"]
    if set(data.get("dependencyTypes", [])) != TYPES:
        errors.append("dependencyTypes must include v2 governance/runtime/build/handoff/observed-by/fixture/archive-of")
    for module_id, expected_path in EXPECTED_MODULES.items():
        entry = modules[module_id]
        if entry.get("path") != expected_path:
            errors.append(f"{module_id}: path mismatch")
        observed_by = entry.get("observedBy")
        if not isinstance(observed_by, list):
            errors.append(f"{module_id}: observer relation missing")
        elif module_id == "workflow-assistance" and "work-lab-observer" not in observed_by:
            errors.append(f"{module_id}: observer relation missing")
        elif module_id == "work-lab-observer" and observed_by:
            errors.append("work-lab-observer: observer cannot observe itself")
        for dependency in entry.get("dependencies", []):
            target = dependency.get("module")
            if target not in EXPECTED_MODULES or target == module_id:
                errors.append(f"{module_id}: invalid dependency target {target}")
            types = set(dependency.get("types", []))
            if not types or not types <= TYPES:
                errors.append(f"{module_id}->{target}: invalid dependency type")
            if "runtime" in types:
                errors.append(f"{module_id}->{target}: runtime coupling is not allowed")

    # `runtimeEdges` is the approved-and-measured runtime coupling register. `dependencies[].types`
    # still forbids "runtime" (the check above is unchanged): declaring a measured edge here is what
    # policy.crossModuleRuntimeCoupling = "forbidden-unless-explicitly-approved" means, and an entry
    # without a basis is not an approval.
    edges = data.get("runtimeEdges")
    if not isinstance(edges, list):
        errors.append("runtimeEdges must be a list of measured, justified runtime edges")
        edges = []
    seen_pairs: set[tuple[str, str]] = set()
    for index, edge in enumerate(edges):
        if not isinstance(edge, dict):
            errors.append(f"runtimeEdges[{index}]: an edge must be an object")
            continue
        source, target = edge.get("from"), edge.get("to")
        if source not in EXPECTED_MODULES or target not in EXPECTED_MODULES or source == target:
            errors.append(f"runtimeEdges[{index}]: invalid edge endpoints {source}->{target}")
            continue
        pair = (source, target)
        if pair in seen_pairs:
            errors.append(f"runtimeEdges[{index}]: duplicate edge declaration {source}->{target}")
        seen_pairs.add(pair)
        if not edge.get("coupling"):
            errors.append(f"{source}->{target}: an edge must name its coupling form")
        if not str(edge.get("basis", "")).strip():
            errors.append(f"{source}->{target}: runtime coupling without a basis is not approved")
        if not str(edge.get("authority", "")).strip():
            errors.append(f"{source}->{target}: runtime coupling without an authority is not approved")
        sites = edge.get("sites")
        if not isinstance(sites, list) or not sites:
            errors.append(f"{source}->{target}: an approved edge must name its sites")
            continue
        for site in sites:
            file = site.get("file") if isinstance(site, dict) else None
            if not file or file not in tracked_source_files(root):
                errors.append(f"{source}->{target}: declared site {file} is not a tracked source file")
    if data.get("policy", {}).get("observedByIsReadOnly") is not True:
        errors.append("observedBy must be read-only")
    if data.get("policy", {}).get("runtimeEdgesAreReconciledAgainstRealImports") is not True:
        errors.append("policy.runtimeEdgesAreReconciledAgainstRealImports must be true")
    return errors


# ---------------------------------------------------------------------------
# Real-import scan
# ---------------------------------------------------------------------------
def _tracked(root: Path, args: list[str]) -> list[str]:
    try:
        done = subprocess.run(["git", "-C", str(root), "ls-files", *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              check=False)
    except OSError:
        return []
    if done.returncode != 0:
        return []
    return [line.strip() for line in done.stdout.splitlines() if line.strip()]


def tracked_source_files(root: Path) -> list[str]:
    files = _tracked(root, ["--", "*.py"])
    if files:
        return files
    # No git (a temp fixture tree): walk the canonical roots only, skipping build output.
    collected: list[str] = []
    for rel_root in EXPECTED_MODULES.values():
        base = root / rel_root
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*.py")):
            if SKIP_DIRS & set(path.parts):
                continue
            collected.append(path.relative_to(root).as_posix())
    return collected


def module_of(rel: str) -> str | None:
    for module_id, rel_root in EXPECTED_MODULES.items():
        if rel.startswith(rel_root + "/"):
            return module_id
    return None


def dotted_parts(rel_under_root: str) -> tuple[str, ...] | None:
    """The import path of a file relative to its module root, with the root's own directory kept.

    `scripts/canonical_store.py` yields ("scripts", "canonical_store") and the suffix "canonical_store",
    because every consumer in this tree puts `.../scripts` on sys.path and imports the bare stem.
    """
    path = PurePosixPath(rel_under_root)
    parts = list(path.parts)
    if not parts:
        return None
    if parts[-1] == "__init__.py":
        parts = parts[:-1]
    elif parts[-1].endswith(".py"):
        parts[-1] = parts[-1][:-3]
    else:
        return None
    return tuple(parts) or None


def import_index(files: list[str]) -> dict[str, set[str]]:
    index: dict[str, set[str]] = {}
    for rel in files:
        owner = module_of(rel)
        if owner is None:
            continue
        rel_root = EXPECTED_MODULES[owner]
        parts = dotted_parts(rel[len(rel_root) + 1:])
        if not parts:
            continue
        names = {".".join(parts[i:]) for i in range(len(parts))}
        for name in names:
            index.setdefault(name, set()).add(owner)
    return index


def resolves_cross_root(dotted: str, index: dict[str, set[str]], own: str) -> tuple[str, str] | None:
    """(resolved name, other module id) when the import resolves under another root and not under this one."""
    parts = dotted.split(".")
    for size in range(len(parts), 0, -1):
        name = ".".join(parts[:size])
        hits = index.get(name)
        if not hits:
            continue
        if own in hits:
            return None  # a local module of the same name shadows it: not cross-root
        others = sorted(hits - {own})
        if others:
            return name, others[0]
        return None
    return None


def literal_path(node: ast.AST, bindings: dict[str, ast.AST], depth: int = 3) -> str | None:
    """Join the string literals of a path expression into one posix path, following simple bindings.

    The tree builds these paths with the `/` operator over `Path(__file__)...` (no literals for the
    prefix) and reuses them through module-level constants, so a literal-only read of the call site
    would miss `spec_from_file_location("project_temp", PROJECT_TEMP_PATH)`.
    """
    if depth < 0:
        return None
    if isinstance(node, ast.Name) and node.id in bindings:
        return literal_path(bindings[node.id], bindings, depth - 1)
    if isinstance(node, ast.Call):
        return literal_path(node.args[0] if node.args else node, bindings, depth - 1)
    literals = _ordered_literals(node)
    joined = "/".join(part for part in literals if part)
    return joined or None


def _ordered_literals(node: ast.AST) -> list[str]:
    """String literals of a path expression in SOURCE order.

    `ast.walk` is breadth-first, so on `((ROOT / "packages") / "client-neutral-core") / "scripts"` it
    yields "scripts" before "packages" — a scrambled path that matches no root and would silently
    report zero dynamic edges. Walking children left-to-right keeps the fragments in the order the
    path is built.
    """
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return [node.value]
    collected: list[str] = []
    for child in ast.iter_child_nodes(node):
        collected.extend(_ordered_literals(child))
    return collected


def root_in_path(candidate: str | None) -> str | None:
    """Which canonical module root the path fragment lands in, or None."""
    if not candidate:
        return None
    segments = [s for s in PurePosixPath(candidate.replace("\\", "/")).parts if s]
    for module_id, rel_root in EXPECTED_MODULES.items():
        needle = [s for s in PurePosixPath(rel_root).parts if s]
        for start in range(len(segments) - len(needle) + 1):
            if segments[start:start + len(needle)] == needle:
                return module_id
    return None


def call_name(node: ast.Call) -> str:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr
    if isinstance(node.func, ast.Name):
        return node.func.id
    return ""


def bindings_of(tree: ast.AST) -> dict[str, ast.AST]:
    """Module-level and function-level `NAME = <expr>` bindings, for path-constant lookups."""
    found: dict[str, ast.AST] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    found.setdefault(target.id, node.value)
    return found


def scan_edges(root: Path) -> list[dict]:
    files = tracked_source_files(root)
    index = import_index(files)
    edges: list[dict] = []
    for rel in files:
        own = module_of(rel)
        if own is None:
            continue
        try:
            tree = ast.parse((root / rel).read_text(encoding="utf-8", errors="replace"))
        except (SyntaxError, OSError, UnicodeError):
            continue
        bindings = bindings_of(tree)
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    hit = resolves_cross_root(alias.name, index, own)
                    if hit:
                        edges.append(_edge(own, hit[1], rel, node.lineno, "import", hit[0]))
            elif isinstance(node, ast.ImportFrom):
                if node.module is None or node.level:
                    continue  # a relative import stays inside its own package
                hit = resolves_cross_root(node.module, index, own)
                if hit:
                    names = ",".join(sorted(alias.name for alias in node.names))
                    edges.append(_edge(own, hit[1], rel, node.lineno, "from-import",
                                       f"{hit[0]} -> {names}"))
            elif isinstance(node, ast.Call):
                edges.extend(_dynamic_edges(node, own, rel, index, bindings))
    return edges


def _edge(source: str, target: str, file: str, line: int, form: str, symbol: str) -> dict:
    return {"from": source, "to": target, "file": file, "line": line, "form": form, "symbol": symbol}


def _dynamic_edges(node: ast.Call, own: str, rel: str, index: dict[str, set[str]],
                   bindings: dict[str, ast.AST]) -> list[dict]:
    name = call_name(node)
    if name in SYSCALLS and isinstance(node.func, ast.Attribute) and \
            isinstance(node.func.value, ast.Attribute) and \
            isinstance(node.func.value.value, ast.Name) and node.func.value.value.id == "sys" \
            and node.func.value.attr == "path":
        argument = node.args[1] if name == "insert" and len(node.args) > 1 else \
            (node.args[0] if node.args else None)
        if name == "extend" and node.args and isinstance(node.args[0], (ast.List, ast.Tuple)):
            return [e for item in node.args[0].elts
                    for e in _path_edge(item, own, rel, node.lineno, bindings, "sys.path")]
        return _path_edge(argument, own, rel, node.lineno, bindings, "sys.path")
    if name in PATH_LOADERS:
        # spec_from_file_location(name, location): the second positional arg, or `location=`.
        argument = node.args[1] if len(node.args) > 1 else None
        if argument is None:
            argument = next((kw.value for kw in node.keywords if kw.arg == "location"), None)
        return _path_edge(argument, own, rel, node.lineno, bindings, "importlib-by-path")
    return []


def _path_edge(argument: ast.AST | None, own: str, rel: str, line: int,
               bindings: dict[str, ast.AST], form: str) -> list[dict]:
    if argument is None:
        return []
    candidate = literal_path(argument, bindings)
    target = root_in_path(candidate)
    if target is None or target == own:
        return []  # reaching into your own root is not a cross-module edge
    return [_edge(own, target, rel, line, form, candidate or "")]


def reconcile(root: Path) -> tuple[list[dict], list[str], list[str]]:
    """(measured edges, undeclared problems, stale problems)."""
    data = json.loads((root / ".project/governance" / "module-dependencies.json").read_text(encoding="utf-8"))
    declared = {tuple(pair) for pair in _declared_pairs(data)}
    declared_sites = _declared_sites(data)
    measured = scan_edges(root)
    measured_pairs = {(edge["from"], edge["to"]) for edge in measured}
    undeclared: list[str] = []
    stale = [f"{source}->{target} is declared but no import into that module was found"
             for source, target in sorted(declared) if (source, target) not in measured_pairs]
    for edge in measured:
        pair = (edge["from"], edge["to"])
        problem = (f"{edge['from']}->{edge['to']} {edge['file']}:{edge['line']} "
                   f"({edge['form']} {edge['symbol']})")
        if pair not in declared:
            undeclared.append(f"{problem} is not declared")
        elif pair in declared_sites and edge["file"] not in declared_sites[pair]:
            undeclared.append(f"{problem} is a new site on a declared edge")
    for (source, target), sites in sorted(declared_sites.items()):
        if (source, target) not in measured_pairs:
            continue  # already reported as a stale pair
        measured_files = {edge["file"] for edge in measured
                          if (edge["from"], edge["to"]) == (source, target)}
        for site in sorted(sites):
            if site not in measured_files:
                stale.append(f"{source}->{target}: declared site {site} no longer imports that module")
    return measured, undeclared, stale


def _declared_pairs(data: dict) -> list[list[str]]:
    return [[edge["from"], edge["to"]] for edge in data.get("runtimeEdges", [])
            if isinstance(edge, dict) and edge.get("from") and edge.get("to")]


def _declared_sites(data: dict) -> dict[tuple[str, str], set[str]]:
    sites: dict[tuple[str, str], set[str]] = {}
    for edge in data.get("runtimeEdges", []):
        if not isinstance(edge, dict) or not edge.get("from") or not edge.get("to"):
            continue
        pair = (edge["from"], edge["to"])
        bucket = sites.setdefault(pair, set())
        for site in edge.get("sites", []) or []:
            if isinstance(site, dict) and site.get("file"):
                bucket.add(site["file"])
    return sites


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=None, help="repository root (default: this script's repo)")
    parser.add_argument("--scan-only", action="store_true",
                        help="print the measured edges without judging the manifest")
    args = parser.parse_args(argv)
    root = Path(args.root).resolve() if args.root else Path(__file__).resolve().parents[2]

    errors = verify(root)
    try:
        measured, undeclared, stale = reconcile(root)
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"import scan unavailable: {exc}")
        measured, undeclared, stale = [], [], []
    for edge in measured:
        print(f"MODULE_DEPS_EDGE {edge['from']} -> {edge['to']} {edge['file']}:{edge['line']} "
              f"[{edge['form']} {edge['symbol']}]")
    if args.scan_only:
        print(f"MODULE_DEPS_SCANNED edges={len(measured)}")
        return 0
    for error in errors:
        print(f"MODULE_DEPENDENCIES_FAIL {error}")
    for problem in undeclared:
        print(f"MODULE_DEPS_UNDECLARED {problem}")
    for problem in stale:
        print(f"MODULE_DEPS_STALE {problem}")
    if errors or undeclared or stale:
        print(f"MODULE_DEPS_FAIL undeclared_edges={len(undeclared)} stale_edges={len(stale)} "
              f"shape_errors={len(errors)} -- every runtime edge in the tree has to be declared, "
              "and every declared edge has to still be in the tree")
        return 1
    print(f"MODULE_DEPENDENCIES_PASS modules=2 measured_edges={len(measured)} "
          f"declared_edges={len({(e['from'], e['to']) for e in measured})}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
