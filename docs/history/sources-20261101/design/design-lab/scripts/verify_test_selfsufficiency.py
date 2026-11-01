#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Every tracked test module must run its own tests, and import what it imports, on its own.

Two properties, both checkable without executing anything, and both were violated in this
repository until 2026-10-08:

1. EXECUTABLE -- ``python design-lab/tests/test_x.py`` has to actually run tests. 17 modules defined
   their TestCases but had no ``if __name__ == '__main__': unittest.main()`` block, so running one
   of them exited 0 having executed nothing. A per-module sweep that reads exit codes -- mine, twice
   today -- recorded those as passes. Discovery in one process hides it; a file you can only run one
   particular way is a library named test_*.py, not a test module.

2. SELF-SUFFICIENT IMPORTS -- if a module imports a top-level name that only exists under a
   second-party root (``src`` -> design_lab, ``packages/capabilities`` -> reconstruction, ...), that
   root has to reach ``sys.path`` from the module itself or from a sibling it imports. CI's runner
   only adds ``src``, so any other name is reachable in the shared process purely because some
   earlier module inserted the path: ``test_reconstruction_semantics.py`` carried 13 errors under a
   fresh process and passed under discovery, and the errors were reported as a missing capability
   while the code sits at packages/capabilities/reconstruction/.

Deliberately host-independent: no ``find_spec``, no site-packages probing. Whether a name is
installed differs between this venv and a clean checkout, and a gate that changes colour with the
host is a gate that will be silenced by the host that finds it inconvenient.
"""
from __future__ import annotations

import ast
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TEST_DIR = REPO / 'design-lab' / 'tests'

#: roots whose top-level names are NOT on sys.path by themselves, and the spelling a module must
#: use somewhere in its own sys.path.insert call to claim the root.
SECOND_PARTY = {
    'src': ('src',),
    'packages/capabilities': ('capabilities',),
}

STDLIB = set(sys.stdlib_module_names)


def provided_by(root_label: str) -> set[str]:
    root = REPO / root_label
    if not root.is_dir():
        return set()
    names = set()
    for child in root.iterdir():
        if child.is_dir() and (child / '__init__.py').is_file():
            names.add(child.name)
        elif child.suffix == '.py' and not child.name.startswith('__'):
            names.add(child.stem)
    return names


PROVIDED = {label: provided_by(label) for label in SECOND_PARTY}


def imports_of(tree: ast.Module) -> tuple[set[str], set[str]]:
    """(top-level imported names, names of sibling test modules imported)."""
    names: set[str] = set()
    siblings: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                names.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                continue
            head = (node.module or '').split('.')[0]
            if head:
                names.add(head)
    for name in list(names):
        if name.startswith('test_'):
            siblings.add(name)
    return names, siblings


def _is_sys_path(node) -> bool:
    return (isinstance(node, ast.Attribute) and node.attr == 'path'
            and isinstance(node.value, ast.Name) and node.value.id == 'sys')


def sys_path_statements(tree: ast.Module) -> list[ast.stmt]:
    """Every statement that mutates sys.path: insert / append / extend calls and slice assignment."""
    found = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and (
                node.func.attr in ('insert', 'append', 'extend') and _is_sys_path(node.func.value)):
            found.append(node)
        elif isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Subscript) and _is_sys_path(target.value)
                for target in node.targets):
            found.append(node)
    return found


def claims_root(tree: ast.Module, label: str) -> bool:
    """True when the module puts this root on sys.path itself.

    The root's spelling is looked for in string constants that are either inside a sys.path
    statement or bound by a module-level assignment -- the two shapes this repository actually uses
    (`sys.path[:0] = [str(ROOT/'packages/capabilities')]`, and `_PKG_ROOT = ROOT / "packages" /
    "capabilities"` inserted one call later). Prose is excluded because only constant nodes reached
    by those statements are read, and a substring match over the whole file would pass a module that
    never touched sys.path at all.
    """
    statements = sys_path_statements(tree)
    if not statements:
        return False
    literals: set[str] = set()
    for node in ast.walk(ast.Module(body=statements, type_ignores=[])):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            literals.add(node.value)
    for node in tree.body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            for name in ast.walk(node):
                if isinstance(name, ast.Name) and isinstance(name.ctx, ast.Store):
                    for inner in ast.walk(node):
                        if isinstance(inner, ast.Constant) and isinstance(inner.value, str):
                            literals.add(inner.value)
    return any(token in text for text in literals for token in SECOND_PARTY[label])


def main(argv=None) -> int:
    paths = sorted(TEST_DIR.glob('test_*.py'))
    blind = sorted(label for label, names in PROVIDED.items() if not names)
    if blind:
        # A declared root that yields no importable names means this is looking at the wrong tree,
        # and every import check below would then pass by having nothing to say.
        print(f'TEST_SELF_SUFFICIENCY=FAIL roots_with_nothing_provided={blind} modules='
              f'{len(paths)} -- fail closed rather than scan blind')
        return 1
    if not paths:
        print(f'TEST_SELF_SUFFICIENCY=FAIL modules=0 -- nothing was scanned, which is not a pass')
        return 1
    parsed: dict[str, ast.Module] = {}
    for path in paths:
        text = path.read_text(encoding='utf-8', errors='ignore')
        try:
            parsed[path.stem] = ast.parse(text, filename=str(path))
        except SyntaxError:
            # A file discovery cannot import is a module that runs nothing anywhere; the loop below
            # reports it as UNPARSEABLE because `parsed` simply has no entry for it.
            pass

    sibling_roots: dict[str, set[str]] = {}
    for stem, tree in parsed.items():
        names, _ = imports_of(tree)
        sibling_roots[stem] = {label for label, provided in PROVIDED.items()
                              if names & provided and claims_root(tree, label)}

    def roots_reachable(stem: str, seen=None) -> set[str]:
        """Own inserts plus the inserts of sibling test modules it imports, transitively."""
        seen = seen or set()
        if stem in seen:
            return set()
        seen.add(stem)
        found = set(sibling_roots.get(stem, set()))
        tree = parsed.get(stem)
        if tree is None:
            return found
        _, siblings = imports_of(tree)
        for sibling in siblings:
            if sibling in parsed:
                found |= roots_reachable(sibling, seen)
        return found

    violations = []
    executable = 0
    for path in paths:
        tree = parsed.get(path.stem)
        if tree is None:
            violations.append((path.name, 'UNPARSEABLE'))
            continue
        cases = 0
        for node in tree.body:
            if isinstance(node, ast.ClassDef):
                cases += sum(1 for item in node.body
                             if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
                             and item.name.startswith('test'))
        cases += sum(1 for node in tree.body
                     if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and node.name.startswith('test'))
        if cases == 0:
            violations.append((path.name, 'NO_CASES -- discovery would collect nothing'))
        guarded = any(isinstance(node, ast.If)
                      and isinstance(node.test, ast.Compare)
                      and getattr(node.test.left, 'id', '') == '__name__'
                      and 'unittest.main(' in ast.unparse(node)
                      for node in tree.body)
        if not guarded:
            violations.append((path.name, 'NOT_EXECUTABLE -- running this file executes no test'))
        else:
            executable += 1
        names, _ = imports_of(tree)
        reachable = roots_reachable(path.stem)
        for label, provided in PROVIDED.items():
            needed = names & provided
            if not needed:
                continue
            if label in reachable:
                continue
            violations.append((path.name, f'BORROWED_IMPORT_PATH -- imports '
                                f'{sorted(needed)[:3]} from {label} with no sys.path insert of its '
                                'own or a sibling that carries one'))
    print(f'scanned={len(paths)} executable={executable} second_party_roots='
          f'{sorted(PROVIDED)} provided={ {k: len(v) for k, v in PROVIDED.items()} }')
    if violations:
        for name, why in violations:
            print(f'VIOLATION {name}: {why}')
        print(f'TEST_SELF_SUFFICIENCY=FAIL modules={len(paths)} violations={len(violations)}')
        return 1
    print(f'TEST_SELF_SUFFICIENCY=OK modules={len(paths)} executable={executable} violations=0')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
