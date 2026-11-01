#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-ROUTE-CALLS: the Workbench's API calls and the service's route table must agree.

Why this gate exists. ``verify_contract_bindings.py`` proves the service's dispatched routes
and the boundary ledger are the same set, and ``verify_route_payload_contracts.py`` proves the
payloads those routes write validate. Neither asks the question a page actually depends on:
does the TypeScript that runs in the browser call a path the service still serves? A renamed
route could keep every backend gate green -- ledger row, payload schema, HTTP test updated
together -- while the view kept fetching the old path and showing its error state.

What it enforces, in both directions:

1. FRONTEND CALLS ARE SERVED. Every ``api(...)`` / ``apiOrEmpty(...)`` / ``fetch(...)`` call
   in ``apps/workbench/*.ts`` that constructs an ``/api`` path -- from a string, a template
   literal, or ``'/api' + <const>`` -- must match a ``Route`` in
   ``src/design_lab/http_service.py`` ROUTES with the same HTTP method. ``api(path)`` is GET;
   ``api(path, body)`` is POST (the transport decides by the presence of a body);
   ``apiOrEmpty`` and ``fetch`` are GET. Template holes are tried against the id vocabularies
   the routes themselves declare (32/64 hex, brief-/direction-/img-/job-/native-..., design
   system names, the print/digital/video profiles), so a shape is compared, not a spelling.
2. BACKEND ROUTES ARE REACHED OR NAMED. Every ROUTES entry is either matched by a frontend
   call of the same method or listed in ``BACKEND_ONLY`` with a reason. The reasons are
   claims about the product: a route nobody can reach from the desktop UI is a deliberate
   surface, not an oversight, and saying so is what keeps the table honest.
3. EXEMPTIONS GO STALE IN BOTH DIRECTIONS. A BACKEND_ONLY entry whose route vanished is red
   (STALE_BACKEND_ONLY), and so is one whose route the frontend now calls (the exemption is
   no longer true). A dynamic fetch allowlist entry that no longer appears in the sources is
   red for the same reason.
4. NOTHING TO COMPARE IS A FAILURE. Zero routes, zero call sites, or a call-expression
   grammar that finds nothing is red; a gate that matched nothing must not report a pass.
5. THE SPECIAL ROUTES ARE EXPLICIT. ``/api/local-session`` is served before authentication
   and is deliberately not part of ROUTES; the page routes are browser navigations with no
   TypeScript call site. Both are declared here with reasons rather than silently ignored.

Scope: TypeScript product sources under ``apps/workbench/``. Tests and the built bundle are
not the product's call sites and are excluded.

Usage:
    python design-lab/scripts/verify_workbench_route_calls.py [--list]
Exit 0 when the two populations agree, 1 otherwise. The last line printed is
``VERIFY_WORKBENCH_ROUTE_CALLS=PASS|FAIL ...``.
"""
from __future__ import annotations

import itertools
import re
import sys
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
WORKBENCH = REPO / 'apps' / 'workbench'
SRC = REPO / 'src'
HTTP_REL = 'src/design_lab/http_service.py'

if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from design_lab.design_layer import DESIGN_SYSTEM_NAME_PATTERN  # noqa: E402
from design_lab.http_service import ROUTES  # noqa: E402

HEX32 = '0123456789abcdef' * 2
HEX64 = '0123456789abcdef' * 4

#: Values a template hole is tried against. These are the concrete vocabularies the route
#: patterns themselves declare; trying all of them per hole compares the *shape* of a call,
#: so renaming a variable or changing how an id is obtained cannot hide a dead call.
CANDIDATES = (
    HEX32,
    HEX64,
    'brief-' + HEX32,
    'direction-' + HEX32,
    'img-' + HEX64,
    'native-' + HEX64,
    'job-' + HEX64,
    'native-job-' + HEX64,
    'bundle-native-' + HEX64,
    'v-' + HEX32,
    # 2026-10-22: prompt result ids are `prompt-`/`reversal-` + 32 hex (the shape
    # src/design_lab/prompt_intelligence.py mints and the review route's pattern requires). Added
    # deliberately: without a probe of that shape the gate would read the page's own
    # `…/prompt-results/${id}/review` call as unserved, which is the useful direction for a mistake
    # but the wrong answer for a call the backend really does dispatch.
    'prompt-' + HEX32,
    'reversal-' + HEX32,
    # 2026-10-23: knowledge library entry ids are `kentry-` + 32 hex (the shape
    # src/design_lab/knowledge_library.py mints and the read/revise route patterns require).
    'kentry-' + HEX32,
    # 2026-10-24: assistance plan ids are `aplan-` + 32 hex, the shape
    # src/design_lab/assistance_plan.py mints and the detail/choose/revision patterns require.
    'aplan-' + HEX32,
    # 2026-10-24 (DL-KB-10): target profile ids are `tprof-` + 32 hex -- the shape
    # src/design_lab/target_profile.py mints for a draft (uuid4().hex) and derives for a seeded
    # row (sha256 of its own profile_key), and both the detail and the /validate patterns require
    # it. Added for the same reason as the two above: without a probe of that shape the gate reads
    # the selection panel's own `/target-profiles/${profile_id}` call as FRONTEND_ROUTE_UNSERVED,
    # which would convict a call the service really does dispatch.
    'tprof-' + HEX32,
    'design-system',
    'print',
    'digital',
    'video',
    'task',
    '0',
    # 2026-10-24 (DL-KB-12): `…/revisions/${revision}` is served by a pattern that requires
    # `[1-9][0-9]{0,8}` -- an ordinal a person picks from the plan's own revision list, never an id
    # this repository mints. '0' above is the only numeric probe and it cannot match a pattern that
    # excludes zero, so the comparison page's real call read as FRONTEND_ROUTE_UNSERVED. '1' is the
    # smallest value that shape accepts.
    '1',
    '',
)
MAX_COMBINATIONS = 20_000

#: Routes served outside ROUTES. Each must still be called by the page (stale-checked).
SPECIAL_ROUTES = {
    ('GET', '/api/local-session'):
        'served before authentication by dispatch (the personal launcher handshake); it is '
        'not an authenticated API route, so it cannot live in ROUTES',
}

#: Backend routes with no Workbench call site, and why that is the product's actual shape.
#: Each reason names the measured consumer (a test or the aggregate route the page does use),
#: because "nobody calls it" and "the UI reads the same data another way" are different claims.
BACKEND_ONLY: dict[tuple[str, str], str] = {
    ('POST', r'/api/projects/([0-9a-f]{32})/assets/(img-[0-9a-f]{64})/analysis'):
        'the Workbench cannot supply observations for this route: no local OCR backend is qualified '
        '(design-lab/readiness/model-radar.json reports QUALIFIED_LOCAL=0 with every entry '
        'default_enabled:false), and routing the structure a person typed on the page through here '
        'would add nothing to what the page already composes locally. The route is exercised live by '
        'design-lab/tests/test_asset_analysis.py and by the `design-lab analyze` verb, which is the '
        'operator path until the owner qualifies a model.',
    ('GET', r'/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})'):
        'the design view reads briefs, directions and their bindings in one round trip through '
        'GET .../design-layer; the single-brief read is exercised for external clients by '
        'design-lab/tests/test_design_layer_http.py',
    ('GET', r'/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})'):
        'the chosen and live direction arrive inside the design-layer projection; the '
        'single-direction read is exercised by design-lab/tests/test_design_layer_http.py',
    ('GET', r'/api/design-briefs/(brief-[0-9a-f]{32})/lineage'):
        'the page addresses lineage through the project-scoped alias it always holds a project '
        'id for; this by-id form is exercised by design-lab/tests/test_design_layer_revision.py '
        'for clients that hold only a brief id',
    ('GET', r'/api/design-directions/(direction-[0-9a-f]{32})/lineage'):
        'the page addresses lineage through the project-scoped alias it always holds a project '
        'id for; this by-id form is exercised by design-lab/tests/test_design_layer_revision.py '
        'for clients that hold only a direction id',
    ('GET', r'/api/projects/([0-9a-f]{32})/design-system-tokens/('
            + DESIGN_SYSTEM_NAME_PATTERN + r')(/lineage)?'):
        'the Workbench lists token documents and writes them (POST .../design-system-tokens/'
        '{name}); reading one document and its lineage is exercised by '
        'design-lab/tests/test_design_system_tokens_http.py',
    ('GET', r'/api/projects/([0-9a-f]{32})'):
        'the page reads projects through the EXACT /api/projects list; the per-project GET is '
        'exercised by design-lab/tests/test_service_http.py for external clients',
    ('POST', r'/api/projects/([0-9a-f]{32})/jury/proposal'):
        'the Workbench records juror verdicts through .../jury/verdict; proposals are the '
        'service-side path exercised by design-lab/tests/test_jury_http.py and '
        'design-lab/scripts/verify_route_payload_contracts.py',
    ('POST', r'/api/design-briefs/(brief-[0-9a-f]{32})/revisions'):
        'every in-repo caller (the Workbench and test_design_layer_revision.py) uses the '
        'project-scoped route; this by-id alias has no caller in this repository and is kept '
        'as a published service surface -- deleting a route is an owner decision, not a gate\'s',
    ('POST', r'/api/design-directions/(direction-[0-9a-f]{32})/revisions'):
        'every in-repo caller (the Workbench and test_design_layer_revision.py) uses the '
        'project-scoped route; this by-id alias has no caller in this repository and is kept '
        'as a published service surface -- deleting a route is an owner decision, not a gate\'s',
}

#: Non-route fetch expressions, keyed by the exact argument source text.
DYNAMIC_FETCH = {
    'path':
        'apiOrEmpty() forwards its own path argument to api(); the call sites of apiOrEmpty '
        'are the inventory, not this wrapper',
    "'/api' + path":
        'the api() transport prefixes /api to the path it is given; route literals live at '
        'the call sites this gate scans, never in the wrapper',
    'data.download_path':
        'the bundle URL is read back from the service payload; the page adopts the served '
        'location instead of constructing a route it would have to keep in sync',
}


@dataclass(frozen=True)
class CallSite:
    file: str
    line: int
    method: str
    template: str
    expression: str


def leading_literal(expression: str):
    """The string/template literal an expression starts with, or None.

    Only the leading literal is returned: ``template + (cond ? '?after=' : '')`` is one
    call whose query is optional, and the base path is what must resolve. The full
    expression is kept separately so the wrapper and dynamic cases can be recognised.
    """
    text = expression.lstrip()
    if not text or text[0] not in "'\"`":
        return None
    quote = text[0]
    out = []
    escaped = False
    for character in text[1:]:
        if escaped:
            out.append(character)
            escaped = False
            continue
        if character == '\\':
            escaped = True
            continue
        if character == quote:
            return ''.join(out), quote
        out.append(character)
    return None


def matching_paren(text: str, open_index: int) -> int:
    """Index of the `)` that closes the call opened at `open_index`."""
    depth = 0
    index = open_index
    quote = None
    escaped = False
    while index < len(text):
        character = text[index]
        if quote:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == quote:
                quote = None
        elif character in "'\"`":
            quote = character
        elif character in '([{':
            depth += 1
        elif character in ')]}':
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return -1


def split_arguments(content: str) -> list[str]:
    """Top-level comma split, respecting nested brackets and string literals."""
    parts, current, depth, quote, escaped = [], [], 0, None, False
    for character in content:
        if quote:
            current.append(character)
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == quote:
                quote = None
            continue
        if character in "'\"`":
            quote = character
            current.append(character)
        elif character in '([{':
            depth += 1
            current.append(character)
        elif character in ')]}':
            depth -= 1
            current.append(character)
        elif character == ',' and depth == 0:
            parts.append(''.join(current))
            current = []
        else:
            current.append(character)
    parts.append(''.join(current))
    return parts


CALL = re.compile(r'\b(apiOrEmpty|api|fetch)\s*(?:<[^()]*>)?\s*\(')
CONST_TEMPLATE = re.compile(
    r'\bconst\s+([A-Za-z_$][\w$]*)\s*=\s*(`(?:[^`\\]|\\.)*`|\'(?:[^\'\\]|\\.)*\'|"(?:[^"\\]|\\.)*")')
PATH_FIELD = re.compile(r"\bpath\s*:\s*(`(?:[^`\\]|\\.)*`|'(?:[^'\\]|\\.)*'|\"(?:[^\"\\]|\\.)*\")")


def strip_comments(text: str) -> str:
    """Blank out JS comments while keeping every offset and newline.

    A code comment that names `apiOrEmpty(...)` is prose about the gate, not a call; the
    first run of this scanner counted one, so comments are removed before the call grammar
    sees them. Strings and template literals are left untouched.
    """
    out = list(text)
    index, quote, escaped = 0, None, False
    while index < len(text):
        character = text[index]
        if quote:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == quote:
                quote = None
            index += 1
            continue
        if character in "'\"`":
            quote = character
            index += 1
            continue
        if text.startswith('//', index):
            end = text.find('\n', index)
            end = len(text) if end < 0 else end
            for cursor in range(index, end):
                out[cursor] = ' '
            index = end
            continue
        if text.startswith('/*', index):
            end = text.find('*/', index + 2)
            end = len(text) - 2 if end < 0 else end
            for cursor in range(index, min(end + 2, len(text))):
                if out[cursor] != '\n':
                    out[cursor] = ' '
            index = end + 2
            continue
        index += 1
    return ''.join(out)


def string_spans(text: str) -> list[tuple[int, int]]:
    """Half-open spans of every string/template literal and comment in the source.

    `strip_comments` flattens comments, but a *string* that names a call (a help sentence, a
    test fixture embedded in the page) still sits in the code the grammar scans. A CALL match
    that begins inside one of these spans is prose, not an invocation.
    """
    spans: list[tuple[int, int]] = []
    index, start, quote, escaped = 0, 0, None, False
    while index < len(text):
        character = text[index]
        if quote:
            if escaped:
                escaped = False
            elif character == '\\':
                escaped = True
            elif character == quote:
                spans.append((start, index + 1))
                quote = None
            index += 1
            continue
        if character in "'\"`":
            quote, start = character, index
            index += 1
            continue
        if text.startswith('//', index):
            newline = text.find('\n', index)
            end = len(text) if newline < 0 else newline
            spans.append((index, end))
            index = end
            continue
        if text.startswith('/*', index):
            end = text.find('*/', index + 2)
            end = len(text) if end < 0 else end + 2
            spans.append((index, end))
            index = end
            continue
        index += 1
    if quote:
        spans.append((start, len(text)))
    return spans


def resolve_identifier(identifier: str, text: str, upto: int):
    """The nearest preceding `const NAME = '<literal>'` in the same file, if any."""
    resolved = None
    for match in CONST_TEMPLATE.finditer(text, 0, upto):
        if match.group(1) == identifier:
            resolved = leading_literal(match.group(2))
            if resolved:
                resolved = resolved[0]
    return resolved


def scan(text: str, filename: str) -> list[CallSite]:
    text = strip_comments(text)
    spans = string_spans(text)
    calls: list[CallSite] = []
    # A call may name a field instead of a literal -- `apiOrEmpty(group.path, {})` walks a
    # local table whose entries carry `path: '/capabilities'`. The literal values are the
    # reachable paths, so each one is emitted as its own call site; a `.path` field with no
    # `/`-prefixed literal anywhere in the file stays unresolved and is reported as such.
    field_templates = [value if value.startswith('/api') else '/api' + value
                       for value in (leading_literal(match.group(1))[0]
                                     for match in PATH_FIELD.finditer(text))
                       if value.startswith('/')]
    for match in CALL.finditer(text):
        if any(start <= match.start() < end for start, end in spans):
            continue
        if re.search(r'\bfunction\s+$', text[max(0, match.start() - 32):match.start()]):
            continue
        name = match.group(1)
        open_index = match.end() - 1
        close_index = matching_paren(text, open_index)
        if close_index < 0:
            continue
        args = split_arguments(text[open_index + 1:close_index])
        first = args[0].strip() if args else ''
        if not first:
            continue
        method = 'GET'
        # A trailing comma (`api<T>(expr,)`) leaves an empty second argument; the transport
        # decides by `body !== undefined`, so only a real expression is a write.
        if name == 'api' and len(args) >= 2 and args[1].strip() not in ('', 'undefined'):
            method = 'POST'
        expression = first
        line = text[:match.start()].count('\n') + 1
        if re.fullmatch(r'[A-Za-z_$][\w$]*\.path', expression) and field_templates:
            for template in field_templates:
                calls.append(CallSite(file=filename, line=line, method=method,
                                      template=template, expression=expression))
            continue
        literal = leading_literal(first)
        template = None
        if literal is not None:
            value, _ = literal
            if value == '/api' and re.fullmatch(
                    r"'/api'\s*\+\s*([A-Za-z_$][\w$]*)", first):
                identifier = re.fullmatch(
                    r"'/api'\s*\+\s*([A-Za-z_$][\w$]*)", first).group(1)
                resolved = resolve_identifier(identifier, text, match.start())
                template = ('/api' + resolved) if resolved else None
            elif name == 'fetch':
                template = value if value.startswith('/api') else None
            else:
                template = '/api' + value
        calls.append(CallSite(
            file=filename, line=line, method=method,
            template=template, expression=expression))
    return calls


@lru_cache(maxsize=None)
def template_probes(template: str) -> tuple[str, ...]:
    """Concrete paths for a template, one per string hole substitution."""
    pieces: list[object] = []
    buffer = []
    index = 0
    while index < len(template):
        if template.startswith('${', index):
            depth, cursor = 0, index + 1
            while cursor < len(template):
                if template[cursor] == '{':
                    depth += 1
                elif template[cursor] == '}':
                    depth -= 1
                    if depth == 0:
                        break
                cursor += 1
            pieces.append(''.join(buffer))
            buffer = []
            pieces.append(None)
            index = cursor + 1
            continue
        buffer.append(template[index])
        index += 1
    pieces.append(''.join(buffer))
    holes = pieces.count(None)
    if len(CANDIDATES) ** holes > MAX_COMBINATIONS:
        raise ValueError(
            f'template has {holes} holes; {len(CANDIDATES)} candidates each exceeds the '
            f'{MAX_COMBINATIONS}-combination budget -- widen the vocabulary deliberately')
    probes = []
    for combination in itertools.product(CANDIDATES, repeat=holes):
        iterator = iter(combination)
        probes.append(''.join(piece if piece is not None else next(iterator)
                              for piece in pieces))
    return tuple(probes)


def route_matches(route, method: str, template: str) -> bool:
    if route.method != method:
        return False
    try:
        probes = template_probes(template)
    except ValueError:
        raise
    for probe in probes:
        target = probe.split('?', 1)[0] if route.path_only else probe
        if route.exact:
            if target == route.pattern:
                return True
            continue
        match = re.fullmatch(route.pattern, target)
        if match is not None and route.accepts(match):
            return True
    return False


def evaluate(routes, calls, backend_only, special, dynamic):
    errors: list[str] = []
    if not routes:
        errors.append('NOTHING_TO_COMPARE: ROUTES is empty -- the backend inventory is gone')
    if not calls:
        errors.append('NOTHING_TO_COMPARE: no api()/apiOrEmpty()/fetch() call was found in '
                      f'{WORKBENCH.name} -- the scanner or the page changed shape')
    matched: set[tuple[str, str]] = set()
    dynamic_seen: set[str] = set()
    special_seen: set[tuple[str, str]] = set()
    for call in calls:
        if call.template is None:
            dynamic_seen.add(call.expression)
            if call.expression not in dynamic:
                errors.append(
                    f'{call.file}:{call.line}: FRONTEND_CALL_UNRESOLVED '
                    f'{call.expression!r} -- neither a literal /api path nor a declared '
                    'dynamic fetch; the gate cannot prove this call reaches a route')
            continue
        if (call.method, call.template) in special:
            special_seen.add((call.method, call.template))
            continue
        hits = [route for route in routes
                if route_matches(route, call.method, call.template)]
        if not hits:
            other = [route.method for route in routes
                     if route.method != call.method
                     and route_matches(route, route.method, call.template)]
            hint = (f' (the same shape is served as {", ".join(sorted(set(other)))} -- the '
                    'method disagrees)' if other else '')
            errors.append(
                f'{call.file}:{call.line}: FRONTEND_ROUTE_UNSERVED {call.method} '
                f'{call.template!r}{hint}; no Route in {HTTP_REL} answers it')
            continue
        matched.update((route.method, route.pattern) for route in hits)

    for route in routes:
        key = (route.method, route.pattern)
        if key in matched:
            continue
        reason = backend_only.get(key)
        if reason:
            continue
        errors.append(
            f'BACKEND_ROUTE_UNREACHED {key[0]} {key[1]!r} -- no Workbench call site reaches '
            'it and BACKEND_ONLY does not say why the desktop UI cannot')

    route_keys = {(route.method, route.pattern) for route in routes}
    for key, reason in backend_only.items():
        if key not in route_keys:
            errors.append(f'STALE_BACKEND_ONLY {key[0]} {key[1]!r} -- the route is gone; '
                          'delete the exemption')
        elif key in matched:
            errors.append(f'STALE_BACKEND_ONLY {key[0]} {key[1]!r} -- the frontend now calls '
                          'it; the exemption is no longer true')
    for key, reason in special.items():
        if key not in special_seen:
            errors.append(f'STALE_SPECIAL_ROUTE {key[0]} {key[1]!r} -- no frontend call uses '
                          'it; either the call moved or the special route is dead')
    for expression, reason in dynamic.items():
        if expression not in dynamic_seen:
            errors.append(f'STALE_DYNAMIC_FETCH {expression!r} -- no call site uses it; '
                          'delete the exemption')
    duplicates = {}
    for route in routes:
        key = (route.method, route.pattern)
        duplicates[key] = duplicates.get(key, 0) + 1
    for key, count in sorted(duplicates.items()):
        if count > 1:
            errors.append(f'DUPLICATE_ROUTE {key[0]} {key[1]!r} appears {count} times in '
                          'ROUTES -- a duplicated entry hides which handler is live')
    stats = {'calls': len(calls), 'routes': len(routes), 'matched': len(matched),
             'backend_only': len(backend_only), 'dynamic': len(dynamic_seen),
             'special': len(special_seen)}
    return errors, stats


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    files = sorted(WORKBENCH.glob('*.ts'))
    calls: list[CallSite] = []
    for path in files:
        calls.extend(scan(path.read_text(encoding='utf-8'), path.name))
    if '--list' in argv:
        for call in calls:
            print(f'{call.file}:{call.line} {call.method} '
                  f'{call.template or "<dynamic> " + call.expression}')
        return 0
    errors, stats = evaluate(ROUTES, calls, BACKEND_ONLY, SPECIAL_ROUTES, DYNAMIC_FETCH)
    for error in errors:
        print('ERROR:', error)
    print(f'VERIFY_WORKBENCH_ROUTE_CALLS={"FAIL" if errors else "PASS"} '
          f'calls={stats["calls"]} routes={stats["routes"]} matched={stats["matched"]} '
          f'backend_only={stats["backend_only"]} dynamic={stats["dynamic"]} '
          f'special={stats["special"]}')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
