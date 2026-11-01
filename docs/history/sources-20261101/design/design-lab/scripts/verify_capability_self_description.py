#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CAPABILITY-SELF-DESCRIPTION: the Workbench describes its own coverage; that text is a claim.

The Workbench carries two machine-readable statements about what the product can actually do:
``VIEW_NOT_OPEN`` (the copy a slot shows when it has no backend route -- "研究洞察页未开放：
当前服务没有研究结论的持久化路由") and ``CAPABILITY_REGISTRY`` (one row per capability with a
declared ``route`` and an ``implementationState`` of PLANNED / BLOCKED / IMPLEMENTED). They exist
because a task pack required that a blueprint page with no backend must not claim to be usable.

Nothing checked them against the service. On 2026-10-08 the store, the read-back façade and both
routes for persisted research findings landed, and both statements stayed exactly as they were:
the research slot still told the operator that no route persisted conclusions, and the registry
row still said PLANNED. A stale self-description is not a cosmetic bug -- it is the product
advertising a capability gap it no longer has, which is the same false-green shape inverted, and
it is the reason a reader cannot trust the table that is supposed to tell them what to trust.

What it enforces, per refusal code:

1. ``CAPABILITY_CLAIM_STALE`` -- a view that declares itself unbacked must not have a route the
   service dispatches for it. The linkage is structural: a route's terminal literal path segment
   names the resource it serves (``/api/projects/([0-9a-f]{32})/research`` -> ``research``), and
   a segment that is not plain literal text (it carries a group, a class or a query) is skipped
   rather than guessed at. The same rule runs on registry rows: a PLANNED or BLOCKED row whose
   declared route is dispatched is a claim that has already been paid off.
2. ``CAPABILITY_ROUTE_ABSENT`` -- the mirror. A row that says IMPLEMENTED must name a route the
   service really dispatches, with its `{id}`-style placeholders matched segment by segment.
   Without this direction the table could be repaired by simply typing IMPLEMENTED.
3. ``NOT_OPEN_COPY_VAGUE`` -- "not open yet" must name the missing route, because a slot that is
   empty for a reason the reader can check is a disclosure and a slot that is empty for no stated
   reason is a dead link.
4. ``ROUTE_READER_BROKEN`` / ``NOTHING_TO_COMPARE`` -- zero dispatched routes, zero registry rows,
   zero terminal segments or an unreadable route reader is red. A comparison that examined nothing
   must not report a pass.

The route list comes from ``verify_contract_bindings.route_tokens``, the AST reader the boundary
ledger already uses, so this gate and that ledger cannot come to different answers about what the
service dispatches. It reads ``shell.ts``, the source, not the built bundle: the bundle is a
derived artefact and the claim lives in the source.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SHELL_REL = 'apps/workbench/shell.ts'
HTTP_REL = 'src/design_lab/http_service.py'
BINDINGS_GATE_REL = 'design-lab/scripts/verify_contract_bindings.py'

#: The states that assert the route does not exist yet, and the state that asserts it does.
UNBUILT = ('PLANNED', 'BLOCKED')
SHIPPED = 'IMPLEMENTED'
STATES = UNBUILT + (SHIPPED,)

#: A "not open" message has to say a route is missing. Chinese copy in this repository names it
#: 路由; the check is on the word, not on the sentence, so the reason stays checkable.
ROUTE_WORD = '路由'

REFUSALS = (
    'CAPABILITY_CLAIM_STALE',
    'CAPABILITY_ROUTE_ABSENT',
    'NOT_OPEN_COPY_VAGUE',
    'ROUTE_READER_BROKEN',
    'NOTHING_TO_COMPARE',
    'SELF_DESCRIPTION_UNREADABLE',
)


class SelfDescriptionError(RuntimeError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        if code not in REFUSALS:
            raise AssertionError(f'undocumented capability refusal code {code!r}')
        self.code = code


def route_reader():
    path = REPO / BINDINGS_GATE_REL
    spec = importlib.util.spec_from_file_location('capability_route_reader', path)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:
        raise SelfDescriptionError(f'{BINDINGS_GATE_REL} cannot be loaded: {exc}',
                                   'ROUTE_READER_BROKEN')
    if not hasattr(module, 'route_tokens'):
        raise SelfDescriptionError(f'{BINDINGS_GATE_REL} no longer exposes route_tokens()',
                                   'ROUTE_READER_BROKEN')
    return module


def dispatched_routes(root: Path = REPO) -> list[str]:
    reader = route_reader()
    try:
        tokens = reader.route_tokens(root / HTTP_REL)
    except (OSError, SyntaxError) as exc:
        raise SelfDescriptionError(f'{HTTP_REL} cannot be parsed: {exc}', 'ROUTE_READER_BROKEN')
    paths = [key for key, _ in tokens if key.startswith('/')]
    if not paths:
        raise SelfDescriptionError(f'{HTTP_REL} yielded zero /api routes, so nothing was compared',
                                   'NOTHING_TO_COMPARE')
    return paths


def terminal_segments(routes: list[str]) -> dict[str, list[str]]:
    """resource -> the routes whose terminal literal segment names it.

    A segment carrying regex syntax (a group, a class, an optional query) is not a resource name
    and is skipped rather than guessed at; a documented skip is honest, a silent one is not, so
    the caller receives the full route list and can show which routes produced no segment.
    """
    out: dict[str, list[str]] = {}
    for route in routes:
        last = [part for part in route.split('/') if part][-1]
        if not re.fullmatch(r'[a-z][a-z0-9-]*', last):
            continue
        out.setdefault(last, []).append(route)
    return out


def segment_of_declared_route(route: str) -> str | None:
    """The terminal segment of a row's declared route; `{id}`-style braces count as wildcards."""
    text = (route or '').strip()
    match = re.match(r'^(?:GET|POST|PUT|PATCH|DELETE)\s+', text)
    if match:
        text = text[match.end():]
    parts = [part for part in text.split('/') if part]
    if not parts:
        return None
    last = parts[-1]
    if last in ('…', '...', '*'):
        return None
    return last


def route_is_dispatched(declared: str, routes: list[str]) -> bool:
    """Match a declared route pattern against the dispatched set, segment by segment.

    `{id}` and friends stand for one segment; a dispatched regex group does too. Compared as
    segment counts plus literal positions, because the two vocabularies differ in syntax only.
    """
    text = (declared or '').strip()
    text = re.sub(r'^(?:GET|POST|PUT|PATCH|DELETE)\s+', '', text)
    wanted = [part for part in text.split('/') if part]
    if not wanted or wanted[-1] in ('…', '...', '*'):
        return False
    for route in routes:
        have = [part for part in route.split('/') if part]
        if len(have) != len(wanted):
            continue
        if all(_segments_match(want, got) for want, got in zip(wanted, have)):
            return True
    return False


def _segments_match(want: str, got: str) -> bool:
    if want.startswith('{') and want.endswith('}'):
        return True
    if want != got:
        return False
    return True


def parse_view_not_open(shell: str) -> dict[str, str]:
    block = _block(shell, r'export const VIEW_NOT_OPEN[^=]*=\s*\{', r'^\};')
    entries = re.findall(r"^\s*'?([a-z][a-z0-9-]*)'?:\s*'([^']*)'", block, re.M)
    return dict(entries)


def parse_registry(shell: str) -> list[dict]:
    block = _block(shell, r'const CAPABILITY_REGISTRY[^=]*=\s*\[', r'^\];')
    rows = []
    # Rows are `{ capabilityId: 'x', ...` with the key on the opening line, so the split point is
    # the object opener itself; each row is the text between one opener and the next.
    starts = list(re.finditer(r"\{\s*capabilityId:\s*'([^']+)'", block))
    for index, match in enumerate(starts):
        stop = starts[index + 1].start() if index + 1 < len(starts) else len(block)
        chunk = block[match.start():stop]
        row = {'capabilityId': match.group(1)}
        for field in ('route', 'implementationState', 'reason', 'slot'):
            found = re.search(field + r":\s*'([^']*)'", chunk)
            row[field] = found.group(1) if found else ''
        rows.append(row)
    return rows


def _block(text: str, opener: str, closer: str) -> str:
    start = re.search(opener, text, re.M)
    if not start:
        raise SelfDescriptionError(f'no block matched {opener!r} in {SHELL_REL}',
                                   'SELF_DESCRIPTION_UNREADABLE')
    tail = text[start.end():]
    end = re.search(closer, tail, re.M)
    if not end:
        raise SelfDescriptionError(f'block opened by {opener!r} never closed in {SHELL_REL}',
                                   'SELF_DESCRIPTION_UNREADABLE')
    return tail[:end.start()]


def scan(root: Path = REPO) -> tuple[list, dict]:
    shell_path = root / SHELL_REL
    try:
        shell = shell_path.read_text(encoding='utf-8')
    except OSError as exc:
        raise SelfDescriptionError(f'{SHELL_REL} cannot be read: {exc}',
                                   'SELF_DESCRIPTION_UNREADABLE')
    routes = dispatched_routes(root)
    segments = terminal_segments(routes)
    not_open = parse_view_not_open(shell)
    rows = parse_registry(shell)
    if not rows:
        raise SelfDescriptionError(f'{SHELL_REL} yielded zero capability rows, so the registry '
                                   'was never read', 'NOTHING_TO_COMPARE')
    if not segments:
        raise SelfDescriptionError(f'none of the {len(routes)} dispatched routes ended in a plain '
                                   'literal segment, so no view could be matched to a route',
                                   'NOTHING_TO_COMPARE')

    findings: list = []
    for view, copy in sorted(not_open.items()):
        if ROUTE_WORD not in copy:
            findings.append(f'NOT_OPEN_COPY_VAGUE view {view!r} says it is not open without '
                            f'naming a missing route ({ROUTE_WORD!r}): {copy[:90]!r}')
        hits = segments.get(view)
        if hits:
            findings.append(
                f'CAPABILITY_CLAIM_STALE view {view!r} tells the operator '
                f'{copy[:48]!r}... while the service dispatches '
                f'{", ".join(sorted(hits))}: the slot is backed now, so either read it back or '
                'say what is genuinely still missing')
    for row in rows:
        state, declared = row['implementationState'], row['route']
        if state not in STATES:
            findings.append(f'CAPABILITY_CLAIM_STALE row {row["capabilityId"]!r} declares state '
                            f'{state!r}, outside {list(STATES)}')
            continue
        live = route_is_dispatched(declared, routes)
        if state in UNBUILT and live:
            findings.append(
                f'CAPABILITY_CLAIM_STALE row {row["capabilityId"]!r} is {state} with route '
                f'{declared!r}, which the service dispatches: a paid-off debt left listed as '
                'unpaid teaches a reader not to trust the table')
        if state == SHIPPED and not live:
            findings.append(
                f'CAPABILITY_ROUTE_ABSENT row {row["capabilityId"]!r} says IMPLEMENTED but no '
                f'route it names ({declared!r}) is dispatched by {HTTP_REL}')
        if state in UNBUILT and not row['reason']:
            findings.append(f'NOT_OPEN_COPY_VAGUE row {row["capabilityId"]!r} is {state} with no '
                            'reason, so the reader cannot tell what would change it')
        # The slot is the explicit view linkage. Without it a row could keep a prose `route`
        # value that no longer describes reality, and a nav slot that is backed would still read
        # as unbacked -- which is exactly the defect this gate was written for.
        slot = row['slot']
        if slot and state == SHIPPED and slot in not_open:
            findings.append(
                f'CAPABILITY_CLAIM_STALE row {row["capabilityId"]!r} is {state} for slot '
                f'{slot!r} while VIEW_NOT_OPEN still shows that slot its "no route" notice')
        if slot and state in UNBUILT and segments.get(slot):
            findings.append(
                f'CAPABILITY_CLAIM_STALE row {row["capabilityId"]!r} is {state} for slot '
                f'{slot!r}, but the service dispatches '
                f'{", ".join(sorted(segments[slot]))} for it')

    summary = {'shell': SHELL_REL, 'routes': len(routes), 'terminal_resources': sorted(segments),
               'views_declared_unopen': sorted(not_open), 'rows': len(rows),
               'rows_by_state': {state: sum(1 for r in rows if r['implementationState'] == state)
                                 for state in STATES}}
    return findings, summary


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if hasattr(sys.stdout, 'reconfigure'):
        # The findings quote Chinese copy out of shell.ts; the console default would mangle it.
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        findings, summary = scan()
    except SelfDescriptionError as exc:
        print(f'CAPABILITY_SELF_DESCRIPTION=FAIL {exc.code}: {exc}')
        return 1
    for line in findings:
        print(f'CAPABILITY_SELF_DESCRIPTION=FAIL {line}')
    if '--json' in argv:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    print(f"CAPABILITY_SELF_DESCRIPTION={'FAIL' if findings else 'OK'} "
          f"routes={summary['routes']} resources={len(summary['terminal_resources'])} "
          f"rows={summary['rows']} unopen_views={len(summary['views_declared_unopen'])} "
          f"findings={len(findings)}")
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
