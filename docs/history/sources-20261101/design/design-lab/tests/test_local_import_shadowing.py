#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A function must not read a name that a later local import rebinds.

The owner audit of 2026-10-26 found `doctor --task` dying with `UnboundLocalError` on every input:
`design_lab.runtime.doctor.main()` carried `from .paths import PathPolicyError, resolve_paths`
inside its `--paths` branch, which makes `resolve_paths` local to the WHOLE function, so the
`--task` branch above it read an unbound local. Nothing in the suite called `--task`, so the crash
was invisible.

The rule is deliberately narrow, because a wide one is a noise machine: it convicts only the shape
that shipped -- a name already bound at module level, read on a line earlier than an `import`
statement that rebinds it **in the same function scope** (nested functions and lambdas are excluded:
their reads resolve when they are called, which is a different question). Verified non-vacuous by
running it over the pre-fix file (convicted) and the fixed one (silent).
"""
from __future__ import annotations
import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
PREFIXES = ('src/', 'scripts/', 'design-lab/scripts/', 'packages/')
NESTED = (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda, ast.ClassDef)


def statements(body):
    """This scope's statements, descending into if/try/for/while/with but never into nested defs."""
    for node in body:
        yield node
        if isinstance(node, NESTED):
            continue
        for field in ('body', 'orelse', 'finalbody'):
            child = getattr(node, field, None)
            if isinstance(child, list):
                yield from statements(child)
        for handler in getattr(node, 'handlers', []) or []:
            yield from statements(handler.body)


def module_bound(tree) -> set:
    names = set()
    for node in tree.body:
        if isinstance(node, (ast.Import, ast.ImportFrom)):
            names.update((a.asname or a.name).split('.')[0] for a in node.names)
        elif isinstance(node, ast.Assign):
            names.update(t.id for t in node.targets if isinstance(t, ast.Name))
    return names


def scope_bindings(func):
    """(name -> first import line that rebinds it locally, name -> first load line) for one scope."""
    imports, reads, params = {}, {}, set()
    for node in statements(func.body):
        if isinstance(node, NESTED):
            continue
        for sub in ast.walk(node):
            if isinstance(sub, (ast.Import, ast.ImportFrom)):
                for alias in sub.names:
                    local = (alias.asname or alias.name).split('.')[0]
                    imports[local] = max(imports.get(local, 0), sub.lineno)
            elif isinstance(sub, ast.Name) and isinstance(sub.ctx, ast.Load):
                reads.setdefault(sub.id, sub.lineno)
            elif isinstance(sub, ast.arg):
                params.add(sub.arg)
    return {k: v for k, v in imports.items() if k not in params}, reads


def shadowing(path: Path) -> list:
    """[(read_line, function, name, import_line)] for the shipped-defect shape, in this file."""
    tree = ast.parse(path.read_text(encoding='utf-8', errors='replace'))
    mods = module_bound(tree)
    found = []
    for func in (n for n in ast.walk(tree)
                 if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))):
        imports, reads = scope_bindings(func)
        for name, import_line in sorted(imports.items()):
            first = reads.get(name)
            if name in mods and first is not None and first < import_line:
                found.append((first, func.name, name, import_line))
    return found


def tracked_python_files(repo: Path = ROOT) -> list:
    """The population comes from git's own index, not from a list someone maintains beside the code."""
    proc = subprocess.run(['git', 'ls-files', '-z', '--', '*.py'], cwd=str(repo),
                          capture_output=True, text=True, encoding='utf-8')
    if proc.returncode != 0:
        raise AssertionError(f'git ls-files failed: {proc.stderr[:200]}')
    names = [n for n in proc.stdout.split('\0') if n]
    return [Path(n) for n in names if n.startswith(PREFIXES) and (repo / n).is_file()]


SAMPLE = '''
from .paths import PathPolicyError, PROJECT_ROOT, resolve_paths


def main(argv):
    if argv.task:
        print(resolve_paths(project_root=PROJECT_ROOT).describe())
    if argv.paths:
        from .paths import PathPolicyError, resolve_paths
        print(resolve_paths().describe())
'''


class LocalImportShadowingTests(unittest.TestCase):
    def test_the_population_is_the_tracked_python_and_not_a_hand_list(self) -> None:
        files = tracked_python_files()
        self.assertGreaterEqual(len(files), 100,
                                f'only {len(files)} files enumerated; this gate would pass on a '
                                f'population it did not really read')
        self.assertIn('src/design_lab/runtime/doctor.py',
                      [f.as_posix() for f in files],
                      'the file that carried the shipped defect is outside the population')

    def test_the_rule_convicts_the_shape_that_shipped(self) -> None:
        """Without this the green below could be a detector that finds nothing at all."""
        probe = Path('design-lab/tests/_shadow_sample_prefix.py')
        self.assertFalse(probe.exists(), 'the plant file is still on disk from an earlier run')
        probe.write_text(SAMPLE, encoding='utf-8', newline='\n')
        try:
            findings = shadowing(probe)
        finally:
            probe.unlink()
        # Asserted structurally rather than against literal line numbers: what has to be true is
        # that the shape is convicted with the read landing before the import, not where the lines
        # of this fixture happen to sit.
        self.assertEqual(len(findings), 1, f'the shipped shape was not convicted: {findings}')
        read_line, func, name, import_line = findings[0]
        self.assertEqual((func, name), ('main', 'resolve_paths'), findings)
        self.assertLess(read_line, import_line, findings)

    def test_nested_reads_are_not_convicted_because_they_resolve_at_call_time(self) -> None:
        sample = '''
from http import HTTPStatus


def outer():
    def inner():
        return HTTPStatus.OK
    from http import HTTPStatus
    return inner()
'''
        probe = Path('design-lab/tests/_shadow_sample_nested.py')
        self.assertFalse(probe.exists())
        probe.write_text(sample, encoding='utf-8', newline='\n')
        try:
            self.assertEqual(shadowing(probe), [])
        finally:
            probe.unlink()

    def test_no_tracked_module_rebinds_a_name_it_already_read(self) -> None:
        offenders = []
        for rel in tracked_python_files():
            for line, func, name, import_line in shadowing(ROOT / rel):
                offenders.append(f'{rel.as_posix()}:{line} {func}() reads {name!r} which a local '
                                 f'import rebinds at line {import_line}')
        self.assertEqual(offenders, [],
                         'these raise UnboundLocalError as written: ' + '; '.join(offenders[:10]))


if __name__ == '__main__':
    unittest.main(verbosity=2)
