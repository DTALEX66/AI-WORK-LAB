#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""A utility class must be the only thing setting its property on an element.

Found the hard way on 2026-10-19: twenty repeated inline `style:` strings in the shell were folded
into `.spaced-top` / `.grid-stack`. One of those elements also carried `.quick-launch`, whose
`margin-top:0` had never applied because the inline style outranked it. Removing the inline style
let the dead rule win by source order and moved the panel 16px -- and every browser gate stayed
green, because they measure overflow, boundaries, contrast and control size, not inter-panel spacing.

This is the static version of the check that would have caught it before rendering: for each element
the shell actually builds, if a utility class sets a property and any *other* class on that same
element also sets it, the winner is decided by file order and nothing says so out loud.

Scope, stated so nobody over-reads it: selectors made only of classes (single or compound), and class
sets are the literal `class: '...'` strings in shell.ts. A compound rule that covers the element's own
classes counts as the conflict being resolved out loud. Descendant selectors, `!important`, and classes
assembled at runtime are out of scope -- this is a tripwire for the shape that broke, not a CSS engine.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CSS = REPO / 'apps/workbench/style.css'
SHELL = REPO / 'apps/workbench/shell.ts'

# The classes this project treats as layout utilities: they exist to set exactly one thing.
UTILITIES = {'spaced-top': {'margin-top'}, 'grid-stack': {'display', 'gap'}}

RULE = re.compile(r'([^{}]+)\{([^{}]*)\}')
COMPOUND_ONLY = re.compile(r'^\.[a-zA-Z0-9_-]+(\.[a-zA-Z0-9_-]+)*$')
DECL = re.compile(r'([a-z-]+)\s*:\s*([^;]+)')


def strip_comments(text: str) -> str:
    return re.sub(r'/\*.*?\*/', '', text, flags=re.S)


def class_properties(css: str) -> tuple[dict, dict]:
    """({class: {prop: value}}, {frozenset(classes): {prop: value}}) for class-only rules.

    The second map holds compound selectors like `.row-card.grid-stack`: those are how a utility
    states its intent at a specificity that does not depend on where either rule sits in the file,
    so they resolve a conflict rather than being one.
    """
    singles: dict[str, dict[str, str]] = {}
    compounds: dict[frozenset, dict[str, str]] = {}
    for selectors, body in RULE.findall(strip_comments(css)):
        props = {p.strip(): v.strip() for p, v in DECL.findall(body)}
        for part in selectors.split(','):
            part = part.strip()
            if COMPOUND_ONLY.match(part):
                names = frozenset(part.lstrip('.').split('.'))
                compounds.setdefault(names, {}).update(props)
                if len(names) == 1:
                    singles.setdefault(next(iter(names)), {}).update(props)
    return singles, compounds


def applied_class_sets(shell: str) -> list[tuple[str, tuple[str, ...]]]:
    """Every literal `class: '...'` in the shell, with the line it appears on."""
    found = []
    for line_no, line in enumerate(shell.splitlines(), start=1):
        for raw in re.findall(r"class: '([^']*)'", line):
            names = tuple(raw.split())
            if any(n in UTILITIES for n in names):
                found.append((str(line_no), names))
    return found


def conflicts(css_text: str, shell_text: str) -> list[str]:
    props_by_class, compounds = class_properties(css_text)
    problems = []
    for line_no, names in applied_class_sets(shell_text):
        applied = set(names)
        for name in names:
            owned = UTILITIES.get(name)
            if not owned:
                continue
            for other in names:
                if other == name:
                    continue
                shared = owned & set(props_by_class.get(other, {}))
                for prop in sorted(shared):
                    resolved = any(classes <= applied and {name, other} <= classes
                                   and prop in values
                                   for classes, values in compounds.items())
                    if resolved:
                        continue
                    problems.append(
                        f'shell.ts:{line_no} class="{ " ".join(names) }": .{name} sets '
                        f'{prop}:{props_by_class[name][prop]}, but .{other} also sets '
                        f'{prop}:{props_by_class[other][prop]} -- file order decides, not intent '
                        f'(resolve it out loud with a `.{other}.{name}{{...}}` rule)')
    return problems


def main(argv: list[str] | None = None) -> int:
    args = argv or sys.argv[1:]
    css = CSS.read_text(encoding='utf-8')
    shell = SHELL.read_text(encoding='utf-8')
    sites = applied_class_sets(shell)
    if not sites:
        print('UTILITY_CONFLICTS=FAIL no element applies a layout utility class; '
              'the check has nothing to guard and should not be called green')
        return 1
    problems = conflicts(css, shell)
    if problems:
        for line in problems:
            print('FAIL ' + line)
        print(f'UTILITY_CONFLICTS=FAIL checked={len(sites)} conflicts={len(problems)}')
        return 1
    print(f'UTILITY_CONFLICTS=PASS checked={len(sites)} utilities={sorted(UTILITIES)}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
