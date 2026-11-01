# SPDX-License-Identifier: MIT
"""Report which repository files the HTTP service can reach, and whether the wheel ships them.

Why this exists: `PROJECT_ROOT` is `Path(__file__).parents[3]`, which is the checkout in a source
tree but the interpreter's own `Lib` inside an installed wheel. A route that opens its contract that
way answers a refusal there, and nothing in a source checkout can see it -- in 2026-10-23 one such
read answered `500 INTERNAL`, another `503 PROJECT_STORE_UNAVAILABLE` (blaming the user's database),
and a third answered `409 NATIVE_BUNDLE_UNVERIFIED`, i.e. a missing packaged file wearing the mask of
a judgement about the work.

This walks an import closure from `src/design_lab/http_service.py` -- module level and function
level, because the service defers several imports into handlers -- and reports every expression that
builds a repository path from the root, plus whether pyproject's wheel force-include ships it under
`design_lab/resources/repo/` (the prefix `runtime/state_resources.repo_resource()` looks in).

Two limits are stated rather than hidden, because a green-looking "0 remaining" from this tool is not
proof:
  * a root reached through arithmetic or a call the tool does not model (a function returning the
    root, a name resolved only at runtime) is still not followed. A name bound anywhere in the
    module IS resolved now, transitively and through `or`. A module-level root name AND module-level `str` /
    `Path()` constants ARE followed now (`root_names_of`, `string_constants_of`): the parked-variable
    form used to be a documented blind spot and it is exactly how the automation projection hid.
  * a reader that resolves packaged-first to a *different* packaged prefix (the Adobe bridges under
    `design_lab/resources/adobe/`) is reported as not declared and is correct.
The claim that an installed wheel really serves the product is carried by the behavioural gate:
`design-lab/tests/test_standalone_chain_http.py` under `DL_LAUNCH_INSTALLED=1`, which CI's clean-wheel
job runs.

`--control` proves the detector fires: it pulls the pre-fix bytes of readers that spelled the root in
each recognised form out of git and asserts they are found. A detector that reports nothing is
indistinguishable from a fixed tree unless something demonstrates it can still see the disease.
"""
from __future__ import annotations

import argparse
import ast
import re
import subprocess
import sys
import tempfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / 'src' / 'design_lab'
DATA = re.compile(r'^(design-lab|packages|vendor|research|integrations|apps|docs)')
REPO_RESOURCE_PREFIX = 'design_lab/resources/repo/'
CONTROL_REF = '91186bc7'
# The automation projection's own pre-fix bytes, still reachable at the merge commit that carried
# them: `REPO_ROOT = Path(__file__).resolve().parents[2]` joined to a module-level `Path()` constant.
# That is the parked-variable-plus-constant form this tool used to document as a blind spot, and an
# installed wheel measured it as `connectors=0` -- so it is now a named control, not a caveat.
PRE_FIX_REF = 'aa65fc70'
CONTROL_EVIDENCE = [
    (CONTROL_REF, 'src/design_lab/assurance/production_preflight.py',
     'design-lab/production/profiles'),
    (CONTROL_REF, 'src/design_lab/model_catalog.py', 'design-lab/config/provider-capabilities.json'),
    (PRE_FIX_REF, 'src/design_lab/automation_connectors.py', 'integrations/adapter-registry.json'),
    (PRE_FIX_REF, 'src/design_lab/automation_connectors.py',
     'docs/history/record-archive-2026-10-28-design-automation/ARCHIVE-MANIFEST.json'),
]


def force_include_pairs(pyproject_text: str) -> set[tuple[str, str]]:
    return set(re.findall(r'"([^"]+)"\s*=\s*"(design_lab/resources[^"]+)"', pyproject_text))


def is_shipped(relative: str, pairs) -> bool:
    """Whether some force-include line ships this path, by its own key or an ancestor directory key.

    Judged on the path's own spelling: the first version of this comparison re-prefixed every
    candidate with `design-lab/`, so a record that lives at `integrations/...` or `docs/...` could
    never be read as shipped even after it was declared -- a tool that can only say NOT-SHIPPED
    about half the repository is a tool whose green line means nothing.
    """
    parts = Path(relative).parts
    for depth in range(len(parts), 0, -1):
        source = '/'.join(parts[:depth])
        if (source, REPO_RESOURCE_PREFIX + source) in pairs:
            return True
    return False


def is_repo_root_expression(node, parked=frozenset()) -> bool:
    if isinstance(node, ast.Name) and (node.id == 'PROJECT_ROOT' or node.id in parked):
        return True
    if isinstance(node, ast.Call):
        args = node.args or []
        if (len(args) == 1 and isinstance(args[0], ast.Name)
                and (args[0].id == 'PROJECT_ROOT' or args[0].id in parked)):
            return True
    probe = node
    if isinstance(probe, ast.Call) and isinstance(probe.func, ast.Name) and probe.func.id == 'Path':
        probe = probe.args[0] if probe.args else probe
    if (isinstance(probe, ast.Subscript) and isinstance(probe.value, ast.Attribute)
            and probe.value.attr == 'parents'):
        return '__file__' in {getattr(item, 'id', None) for item in ast.walk(probe.value.value)}
    return False


def root_names_of(tree) -> set:
    """Names anywhere in the module that hold the repository root, including `x = a or ROOT`.

    This is the form the original detector documented as a blind spot:
    `REPO_ROOT = Path(__file__).resolve().parents[2]` and then `base / SOMETHING`. It is how the
    automation projection spelled its read, and an installed wheel answered
    `connectors=0` -- a page claiming nothing is registered, because a checkout root inside a wheel
    is the interpreter's own `Lib`. A spelling the tool cannot see is worse than one it refuses to
    judge, so this form is followed now.
    """
    parked = set()
    for changed in range(4):
        added = False
        for node in ast.walk(tree):
            if not isinstance(node, ast.Assign) or len(node.targets) != 1:
                continue
            name = node.targets[0]
            if not (isinstance(name, ast.Name) and name.id not in parked):
                continue
            value = node.value
            candidates = ([value] if not isinstance(value, ast.BoolOp)
                          else list(value.values))
            if any(is_repo_root_expression(item, frozenset(parked))
                   or (isinstance(item, ast.Name) and item.id in parked)
                   for item in candidates):
                parked.add(name.id)
                added = True
        if not added:
            break
    return parked


def string_constants_of(tree) -> dict:
    """Module-level `NAME = 'a/b'` and `NAME = Path('a/b')`, so a joined constant can be resolved."""
    consts = {}
    for node in tree.body:
        if not isinstance(node, ast.Assign) or len(node.targets) != 1:
            continue
        name = node.targets[0]
        if not isinstance(name, ast.Name):
            continue
        value = node.value
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            consts[name.id] = value.value
        elif (isinstance(value, ast.Call) and isinstance(value.func, ast.Name)
              and value.func.id == 'Path' and value.args
              and isinstance(value.args[0], ast.Constant)
              and isinstance(value.args[0].value, str)):
            consts[name.id] = value.args[0].value
    return consts


def parts_of(node, parked=frozenset(), consts=None):
    """The literal pieces of `<repo root> / 'a' / NAME`, or None when this is not one.

    `NAME` counts when it is a module-level string or `Path(...)` constant: the point of the join
    is the path, not the token it was written with.
    """
    consts = consts or {}
    groups = []
    # The tree is walked right operand first, so every group is collected back-to-front and each
    # group keeps its own order. Flattening in one direction only is what makes
    # `ROOT / 'a/b' / 'c'` come out as `a/b/c`; splitting the literal and then reversing the flat
    # list produced `c/b/a`, which is a path that exists nowhere.
    while isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div):
        right = node.right
        if isinstance(right, ast.Constant) and isinstance(right.value, str):
            groups.append(Path(right.value).parts)
        elif isinstance(right, ast.Name) and right.id in consts:
            groups.append(Path(consts[right.id]).parts)
        else:
            return None
        node = node.left
        if is_repo_root_expression(node, parked):
            return [piece for group in reversed(groups) for piece in group]
    if is_repo_root_expression(node, parked):
        return [piece for group in reversed(groups) for piece in group]
    return None


def module_path(name: str, current: Path) -> Path:
    if name.startswith('.'):
        depth = len(name) - len(name.lstrip('.'))
        rest = name.lstrip('.').replace('.', '/')
        base = current.parent
        for _ in range(depth - 1):
            base = base.parent
        return (base / (rest + '.py')) if rest else (base / '__init__.py')
    return SRC / (name.replace('.', '/') + '.py')


def imports_of(path: Path) -> set[str]:
    found: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding='utf-8'))):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            base = ('.' * node.level) + (node.module or '')
            found.add(base)
            for alias in node.names:
                if alias.name != '*':
                    found.add(f'{base}.{alias.name}' if (node.module or node.level) else alias.name)
    return found


def build_closure(start: Path = SRC / 'http_service.py') -> set[Path]:
    found, pending = set(), [start]
    while pending:
        path = pending.pop()
        if path in found:
            continue
        found.add(path)
        for name in imports_of(path):
            target = module_path(name, path)
            if target.is_file() and target not in found:
                pending.append(target)
    return found


def scan(paths) -> list[tuple[str, str]]:
    hits = []
    for path in paths:
        tree = ast.parse(path.read_text(encoding='utf-8'))
        parked = frozenset(root_names_of(tree))
        consts = string_constants_of(tree)
        for node in ast.walk(tree):
            targets = [node.value] if isinstance(node, ast.Assign) else []
            if isinstance(node, (ast.Return, ast.Call)):
                targets = [child for child in ast.walk(node) if isinstance(child, ast.BinOp)]
            for target in targets:
                pieces = parts_of(target, parked, consts)
                if pieces and DATA.search('/'.join(pieces)):
                    hits.append((str(path), '/'.join(pieces)))
    return hits


def control() -> int:
    """Prove the detector still sees every spelling it was written to see, by name.

    Each entry is a real pre-fix file pulled out of git plus the exact repository path it opened
    through the checkout root. Asserting pairs rather than a count means a detector that loses one
    form while gaining another cannot keep the job green.
    """
    work = Path(tempfile.mkdtemp(prefix='dl-root-reads-control-'))
    seen_files, paths, origin = set(), [], {}
    for ref, relative, _expect in CONTROL_EVIDENCE:
        if (ref, relative) in seen_files:
            continue
        seen_files.add((ref, relative))
        text = subprocess.run(['git', '-C', str(REPO), 'show', f'{ref}:{relative}'],
                              capture_output=True, text=True, encoding='utf-8').stdout
        if not text:
            print(f'CONTROL_REFUSING git show {ref}:{relative} returned nothing')
            return 2
        target = work / f'{ref}-{Path(relative).name}'
        target.write_text(text, encoding='utf-8', newline='\n')
        paths.append(target)
        origin[str(target)] = relative
    hits = {(Path(origin[module]).name, relative) for module, relative in scan(paths)}
    print('CONTROL evidence=' + str(len(CONTROL_EVIDENCE)) + ' hits=' + str(len(hits)))
    missing = [(ref, name, expect) for ref, name, expect in CONTROL_EVIDENCE
               if (Path(name).name, expect) not in hits]
    for ref, name, expect in missing:
        print(f'   CONTROL_MISS {ref} {name} -> {expect}')
    if missing:
        print('CONTROL_FAILED: the detector no longer sees the pre-fix spellings it was written for')
        return 1
    print('CONTROL=OK every pre-fix reader was found')
    return 0


def report(pairs) -> int:
    closure = build_closure()
    rows, seen = [], set()
    for module_file, relative in scan(sorted(closure)):
        if (module_file, relative) in seen:
            continue
        seen.add((module_file, relative))
        resolved = REPO / relative
        rows.append((str(Path(module_file).relative_to(SRC)), relative,
                     'SHIPPED' if is_shipped(relative, pairs) else 'NOT-SHIPPED',
                     'dir' if resolved.is_dir() else ('file' if resolved.exists() else 'absent')))
    print('REPO_ROOT_READS closure_modules=' + str(len(closure)) + ' paths=' + str(len(rows)))
    for module, relative, state, kind in sorted(rows):
        print(f'  {state:<11} {kind:<6} {module:<36} {relative}')
    undeclared = sorted({relative for _, relative, state, _ in rows if state == 'NOT-SHIPPED'})
    print('REPO_ROOT_READS=REPORT paths=' + str(len(rows))
          + ' not_shipped_under_resources_repo=' + str(len(undeclared))
          + ' NOT_SHIPPED=[' + ','.join(undeclared) + ']'
          + " (blind spots are listed in this file's docstring; the behavioural gate is "
          'the proof)')
    return 0


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--control', action='store_true',
                        help='prove the detector still finds the pre-fix spellings, and exit')
    options = parser.parse_args(argv)
    if options.control:
        return control()
    return report(force_include_pairs((REPO / 'pyproject.toml').read_text(encoding='utf-8')))


if __name__ == '__main__':
    sys.exit(main())
