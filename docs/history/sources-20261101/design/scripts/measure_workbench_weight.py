#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure the workbench's shipped weight before anyone claims it got lighter (DL-KB-13).

The card's rule is 先量基线再改 and 给出实测读数与阈值，而不是「感觉变快了」. So this file reports
only what it can read off the bytes in front of it, and refuses three temptations:

* it prints no frames-per-second, no "snappier", no percentage improvement -- none of those are
  observable here, and inference latency is reported elsewhere and never mixed into these numbers;
* it does not invent a performance budget: `design.qa.yaml` declares none today, so a ceiling is
  an explicit owner decision. The one hard rule checked here is the one already implied by the
  project's own offline claim -- a shipped file that reaches for a remote URL is a finding;
* it does not judge the *source* tree. Every byte figure is the artifact the browser actually
  loads, so a rebuild that doubles the bundle cannot hide behind unchanged sources.

Two readings the card also demands were missing, and are measured here rather than guessed at:

* **列表初始行数** -- every list-bearing GET route is read out of the live `ROUTES` table, and the
  row bound a route has is found in the code that enforces it (a `limit=` the handler passes, a
  method's default, an `ORDER BY ... LIMIT n`, a `rows[:n]` slice). A route where none of those
  exist is reported as `NONE`, not as zero and not as bounded;
* **附件缩略图策略** -- what listing attachments really costs, on real files. The asset list is
  timed against a corpus built through the same `ImageAssets` write path a person uses, and the
  time is split into path check / read / sha256 / image decode so the next round can say which
  one it moved. That part writes fixtures, so it is opt-out of the CI verdict path: `--check`
  stays as fast and as read-only as it always was, and says so in a printed line.

Stdlib plus this repository's own first-party modules (the same ones
`design-lab/scripts/verify_workbench_route_calls.py` already imports). Read-only except the
`.project-local/task-runtime/kb13-weight/` corpus the attachment baseline seeds.

    python scripts/measure_workbench_weight.py            # readings
    python scripts/measure_workbench_weight.py --check    # fail on a remote reference
    python scripts/measure_workbench_weight.py --no-assets      # skip the seeded corpus
    python scripts/measure_workbench_weight.py --clean          # ... and remove it after
"""
from __future__ import annotations

import argparse
import ast
import gzip
import importlib.util
import json
import re
import statistics
import sys
import time
from functools import lru_cache
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
SRC = REPO / 'src'
SHIPPED = [
    ('bundle', REPO / 'apps/workbench/build/main.js'),
    ('stylesheet', REPO / 'apps/workbench/style.css'),
    ('document', REPO / 'apps/workbench/index.html'),
]
# The three surfaces that page a list for the operator, read from the code that enforces them.
PAGE_SIZES = {
    'knowledge list default': ('src/design_lab/knowledge_library.py', 'DEFAULT_LIMIT'),
    'knowledge list maximum': ('src/design_lab/knowledge_library.py', 'MAX_LIMIT'),
    'plan list default': ('src/design_lab/assistance_plan.py', 'DEFAULT_LIMIT'),
    'target profile list default': ('src/design_lab/target_profile.py', 'DEFAULT_LIMIT'),
    'plan feedback list default': ('src/design_lab/plan_feedback.py', 'DEFAULT_LIMIT'),
}
# An XML namespace is an identifier, not a fetch: all four `http:` hits in the shipped bundle were
# createElementNS("http://www.w3.org/2000/svg"). Convicting them would make this check cry wolf,
# and a check that cries wolf gets switched off. Real fetches still are findings.
NAMESPACES = ('http://www.w3.org/1999/xhtml', 'http://www.w3.org/2000/svg',
              'http://www.w3.org/1999/xlink', 'http://purl.org/dc/elements/1.1/',
              'https://design-lab.local/')
REMOTE = re.compile(r'''https?://[^\s"')]+|(?:cdn\.|unpkg\.|jsdelivr\.)[a-z0-9.-]+'''
                    r'''|googleapis\.com|gstatic\.com|googleusercontent\.com''')


def remote_refs(text: str) -> list[str]:
    """Every URL-shaped reference in these bytes that is not a namespace identifier."""
    return [hit for hit in REMOTE.findall(text) if not hit.startswith(NAMESPACES)]
DATA_URI = re.compile(r'data:[a-z0-9.+-]+/[a-z0-9.+-]+;base64,[A-Za-z0-9+/=]*')
EL_CALL = re.compile(r"\bel\('")
ROUTE_VIEWS = re.compile(r"hash:\s*'[^']*'")
# The delivered plan asks for 模块与资源占比 before anyone tries to get lighter, so the bundle is
# attributed rather than guessed at. The build contract keeps this file un-minified precisely so a
# top-level declaration still starts at column 0 -- that is what makes a byte span measurable here.
TOP_LEVEL = re.compile(r'^(?:async function|function|class|const|let|var)\s+([A-Za-z0-9_$]+)')


def read(path: Path) -> bytes:
    if not path.is_file():
        raise SystemExit(f'MEASURE_UNREADABLE {path.relative_to(REPO)} is not a file')
    return path.read_bytes()


def limits() -> dict[str, int]:
    out = {}
    for label, (rel, name) in PAGE_SIZES.items():
        match = re.search(rf'^{name} = (\d+)', read(REPO / rel).decode('utf-8'), re.M)
        if match is None:
            raise SystemExit(f'MEASURE_SOURCE_MOVED {rel} no longer declares {name}')
        out[label] = int(match.group(1))
    return out


def modules(bundle_text: str) -> dict:
    """Byte share per top-level declaration of the shipped bundle, largest first.

    A span runs from one column-0 declaration to the next, so the numbers add up to what the
    browser actually downloads. `coverage` is the share of the file this accounts for at all: if
    the shape of the bundle ever changes so that attribution stops seeing it, that number falls and
    the reading says so instead of reporting a confident empty table.
    """
    starts = []
    offset = 0
    for line in bundle_text.splitlines(keepends=True):
        match = TOP_LEVEL.match(line)
        if match:
            starts.append((offset, match.group(1)))
        offset += len(line)
    spans = []
    for index, (start, name) in enumerate(starts):
        end = starts[index + 1][0] if index + 1 < len(starts) else offset
        spans.append({'name': name, 'bytes': end - start})
    total = len(bundle_text)
    for span in spans:
        span['sharePercent'] = round(100.0 * span['bytes'] / total, 2) if total else 0.0
    spans.sort(key=lambda s: -s['bytes'])
    attributed = sum(s['bytes'] for s in spans)
    return {'declarations': len(spans),
            'coveragePercent': round(100.0 * attributed / total, 1) if total else 0.0,
            'largest': spans[:12]}


HTTP_REL = 'src/design_lab/http_service.py'
# The handlers that page a list are named for what they do; this is the service's own convention,
# not a guess: `_list_*` and the one `_search_*` read are every GET route that answers a collection.
LIST_ACTION_PREFIXES = ('_list_', '_search_')
SQL_LIMIT = re.compile(r'\bLIMIT\s+(\d{1,7})\b', re.IGNORECASE)
CLIENT_INLINE_LIMIT = re.compile(r'\blimit=(\d{1,7})', re.IGNORECASE)
CLIENT_PARAM_LIMIT = re.compile(r"""set\(\s*['\"]limit['\"]\s*,\s*['\"](\d{1,7})['\"]""")
ROUTE_CALL_GATE = REPO / 'design-lab' / 'scripts' / 'verify_workbench_route_calls.py'
WORKBENCH_DIR = REPO / 'apps' / 'workbench'
# Methods that are plumbing on a handler's delegate chain, not the read being paginated.
NOT_A_READ = {'send_json', 'groups', 'get', 'set', 'append', 'extend', 'items', 'keys'}
# A `[:n]` only bounds a LIST when what is being sliced is the row collection. `_TERM.findall(
# query)[:8]` in the search read slices query terms, not rows, and would otherwise be reported as
# an 8-row page -- a number the route never promised.
ROW_COLLECTION_NAMES = {'rows', 'page', 'records', 'entries', 'results', 'items'}


def first_party():
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))


@lru_cache(maxsize=None)
def parse(rel: str) -> ast.Module:
    return ast.parse(read(REPO / rel).decode('utf-8'))


@lru_cache(maxsize=None)
def module_tables(tree: ast.Module):
    """(module-level int constants, classes, functions) keyed by name for one file."""
    consts, classes, funcs = {}, {}, {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            classes.setdefault(node.name, node)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            funcs.setdefault(node.name, node)
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, int) and not isinstance(node.value.value, bool):
            consts.setdefault(node.targets[0].id, (node.value.value, node.lineno))
    return consts, classes, funcs


def imported_from(tree: ast.Module) -> dict:
    """name -> (repo-relative file, original name) for every first-party import."""
    out = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level and node.module:
            rel = 'src/design_lab/' + node.module.replace('.', '/') + '.py'
            for alias in node.names:
                out[alias.asname or alias.name] = (rel, alias.name)
    return out


def int_of(node, consts):
    """An int literal, or a module constant named by an identifier; None otherwise."""
    if node is None:
        return None
    if isinstance(node, ast.Constant) and isinstance(node.value, int) \
            and not isinstance(node.value, bool):
        return node.value
    if isinstance(node, ast.Name) and node.id in consts:
        return consts[node.id][0]
    return None


def defaults_of(args: ast.arguments) -> dict:
    """arg name -> default expression, for positional and keyword-only parameters."""
    out, positional = {}, list(args.posonlyargs) + list(args.args)
    if args.defaults:
        for arg, value in zip(positional[len(positional) - len(args.defaults):], args.defaults):
            out[arg.arg] = value
    for arg, value in zip(args.kwonlyargs, args.kw_defaults):
        if value is not None:
            out[arg.arg] = value
    return out


def handler_delegates(func):
    """What one route handler actually calls: (class, method, limit, maximum) per read call.

    `images = ImageAssets(service)` then `images.list(...)` is the same call as
    `ImageAssets(service).list(...)`, so both shapes are resolved; a name bound to something that
    is not an imported first-party class (a local `params` dict) is plumbing and is skipped.
    """
    bound = {}
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 \
                and isinstance(node.targets[0], ast.Name) \
                and isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
            bound[node.targets[0].id] = node.value.func.id
    found = []
    for node in ast.walk(func):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr in NOT_A_READ:
            continue
        obj = node.func.value
        cls = None
        if isinstance(obj, ast.Call) and isinstance(obj.func, ast.Name):
            cls = obj.func.id                              # ImageAssets(service).list(...)
        elif isinstance(obj, ast.Name):
            cls = bound.get(obj.id)                        # images = ImageAssets(service)
        if not cls:
            continue
        kwargs = {k.arg: k.value for k in node.keywords if k.arg}
        found.append({'class': cls, 'method': node.func.attr, 'limit': kwargs.get('limit'),
                      'maximum': kwargs.get('maximum'), 'line': node.lineno})
    return found


def read_path_functions(rel: str, class_name: str, method_name: str):
    """The entry method plus everything it reaches through `self.<name>()` (depth 3)."""
    consts, classes, funcs = module_tables(parse(rel))
    entry = None
    if class_name in classes:
        entry = next((m for m in classes[class_name].body
                      if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                      and m.name == method_name), None)
    if entry is None:
        entry = funcs.get(method_name)
    if entry is None:
        return None, None
    owner = None
    if class_name in classes:
        owner = {m.name for m in classes[class_name].body
                 if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))}
    reached, queue, seen = [], [(entry, 0)], set()
    while queue:
        func, depth = queue.pop(0)
        if func.name in seen:
            continue
        seen.add(func.name)
        reached.append(func)
        if depth >= 3:
            continue
        for node in ast.walk(func):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                    and isinstance(node.func.value, ast.Name) and node.func.value.id == 'self' \
                    and (owner is None or node.func.attr in owner):
                nested = funcs.get(node.func.attr) if owner is None else next(
                    (m for m in classes[class_name].body
                     if isinstance(m, (ast.FunctionDef, ast.AsyncFunctionDef))
                     and m.name == node.func.attr), None)
                if nested is not None and nested.name not in seen:
                    queue.append((nested, depth + 1))
    return reached, consts


def row_bounds(rel: str, class_name: str, method_name: str) -> dict:
    """Every row bound the read path states about itself, in the file that states it.

    Four signals are collected because the service uses all four: a `limit=` the handler passes,
    a method's own default, an `ORDER BY ... LIMIT n` in the SQL, and a `rows[:n]` slice. `LIMIT 1`
    is not a page -- it is a correlated subquery picking one artifact per row -- so it is counted
    separately and never reported as the list bound.
    """
    funcs, consts = read_path_functions(rel, class_name, method_name)
    if funcs is None:
        return {'caps': [], 'single': 0, 'maximum': None,
                'reason': f"{Path(rel).name} has no {class_name}.{method_name}()"}
    caps, singles = [], 0
    for func in funcs:
        default = defaults_of(func.args).get('limit')
        value = int_of(default, consts) if default is not None else None
        if value is not None:
            name = default.id if isinstance(default, ast.Name) else None
            at = f'{Path(rel).name}:{consts[name][1] if name else default.lineno}({name or "literal"})'
            caps.append({'value': value, 'kind': 'limit default', 'at': at})
        for node in ast.walk(func):
            if isinstance(node, ast.Subscript) and isinstance(node.slice, ast.Slice) \
                    and node.slice.lower is None and isinstance(node.value, ast.Name) \
                    and node.value.id in ROW_COLLECTION_NAMES:
                cap = int_of(node.slice.upper, consts)
                if cap:
                    caps.append({'value': cap, 'kind': 'row slice',
                                 'at': f'{Path(rel).name}:{node.lineno}(rows[:n])'})
            elif isinstance(node, ast.Constant) and isinstance(node.value, str):
                for hit in SQL_LIMIT.finditer(node.value):
                    number = int(hit.group(1))
                    if number > 1:
                        caps.append({'value': number, 'kind': 'SQL LIMIT',
                                     'at': f'{Path(rel).name}:{node.lineno}(LIMIT {number})'})
                    else:
                        singles += 1
            elif isinstance(node, ast.Name) and node.id.endswith('LIMIT') and node.id in consts:
                caps.append({'value': consts[node.id][0], 'kind': node.id,
                             'at': f'{Path(rel).name}:{consts[node.id][1]}({node.id})'})
    maximum = consts.get('MAX_LIMIT')
    return {'caps': caps, 'single': singles,
            'maximum': maximum[0] if maximum else None,
            'maximum_at': f'{Path(rel).name}:{maximum[1]}' if maximum else None,
            'reason': None}


def list_row_readings() -> dict:
    """One line per list-bearing GET route: its bound, and what the shipped UI asks for."""
    tree = parse(HTTP_REL)
    _, _, http_funcs = module_tables(tree)
    imports = imported_from(tree)
    routes = live_routes()
    calls, gate_error, scanned = [], None, 0
    gate = None
    try:
        # The row a page asks for is only half the reading; the other half is what the page asks
        # WITH. That mapping already exists and is gated in both directions, so it is imported
        # rather than re-implemented: a second scanner here would be a second, looser truth.
        spec = importlib.util.spec_from_file_location('workbench_route_calls_reader',
                                                      ROUTE_CALL_GATE)
        gate = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = gate
        spec.loader.exec_module(gate)
        for path in sorted(WORKBENCH_DIR.glob('*.ts')):
            text = read(path).decode('utf-8')
            calls += [(path.name, text, site) for site in gate.scan(text, path.name)]
        scanned = len(calls)
    except Exception as exc:                                # noqa: BLE001 -- a reading, not a fix
        gate_error = f'{type(exc).__name__}: {exc}'
        gate = None
    rows = []
    for route in routes:
        if route.method != 'GET' or not route.action.startswith(LIST_ACTION_PREFIXES):
            continue
        handler = http_funcs.get(route.action)
        caps, notes = [], []
        if handler is None:
            notes.append('HANDLER_NOT_FOUND')
        else:
            for delegate in handler_delegates(handler):
                # `limit=number('limit', DEFAULT_LIMIT, maximum=PROFILE_MAX_LIMIT)` names the
                # constant in the handler but owns it in the store module, so every identifier in
                # the expression is resolved back to the `NAME = <int>` line that gives the number.
                for node, kind in ((delegate['limit'], 'page limit'),
                                   (delegate['maximum'], 'max limit')):
                    if node is None:
                        continue
                    for identifier in ast.walk(node):
                        found = named_constant(identifier, imports)
                        if found:
                            caps.append(found)
                home = imports.get(delegate['class'])
                if home is None:
                    notes.append(f"{delegate['class']} not imported by http_service")
                    continue
                bounds = row_bounds(home[0], home[1], delegate['method'])
                if bounds['reason']:
                    notes.append(bounds['reason'])
                caps += bounds['caps']
                if bounds['maximum'] is not None:
                    caps.append({'value': bounds['maximum'], 'kind': 'max limit',
                                 'at': f'{bounds["maximum_at"]}(MAX_LIMIT)'})
        page = [c for c in caps if c['kind'] != 'max limit']
        ceiling = [c for c in caps if c['kind'] == 'max limit']
        matched = []
        if gate is not None:
            for file_name, _text, site in calls:
                if site.method != 'GET' or not site.template:
                    continue
                try:
                    if gate.route_matches(route, 'GET', site.template):
                        matched.append((file_name, site))
                except ValueError:
                    notes.append(f'{file_name}: dynamic call shape')
        asked, bare, lines = set(), 0, {}
        for file_name, site in matched:
            if file_name not in lines:
                lines[file_name] = read(WORKBENCH_DIR / file_name).decode('utf-8').splitlines()
            # A 10-line window above the call, because `params.set('limit', '50')` is written a
            # few lines before the fetch that uses it. This is a textual reading of the shipped
            # source, not a data-flow proof; a call with no limit nearby is counted, not guessed.
            window = '\n'.join(lines[file_name][max(0, site.line - 11):site.line + 2])
            values = CLIENT_INLINE_LIMIT.findall(site.template) + CLIENT_PARAM_LIMIT.findall(window)
            if values:
                asked |= {int(value) for value in values}
            else:
                bare += 1
        rows.append({'method': route.method, 'pattern': route.pattern, 'action': route.action,
                     'initialRows': min((c['value'] for c in page), default=None),
                     'boundAt': (sorted(page, key=lambda c: c['value'])[0]['at'] if page else None),
                     'boundKind': (sorted(page, key=lambda c: c['value'])[0]['kind']
                                   if page else None),
                     'maxRows': max((c['value'] for c in ceiling), default=None),
                     'signals': len(caps), 'unresolved': sorted(set(notes)),
                     'clientCalls': len(matched), 'clientLimits': sorted(asked),
                     'clientCallsWithoutLimit': bare})
    return {'routes': rows, 'frontendCallSites': scanned,
            # Two channels, because they mean two different things. `readerError` is fatal: it
            # says this file could not read the route table at all. `callSiteError` is a
            # limitation: the canonical route-call matcher lives in design-lab/scripts and
            # imports the product's third-party dependencies, so a job that runs this script
            # with a bare interpreter (the workbench strict-TS job installs no Python packages)
            # loses only the "what does the page ask for" column. Collapsing both into one field
            # made a dep-free job fail as if the reader had gone blind.
            'readerError': None if rows else 'no list-bearing GET route was produced from the '
                                             'parsed ROUTES table',
            'callSiteError': gate_error,
            'listRoutes': len(rows),
            'bounded': len([r for r in rows if r['initialRows'] is not None]),
            'withoutLimit': [r['action'] for r in rows if r['initialRows'] is None],
            'unresolved': [r['action'] for r in rows
                           if r['initialRows'] is None and r['unresolved']]}


def named_constant(identifier, imports):
    """Resolve one identifier to `module.py:line(NAME) = <int>` through the import map."""
    if not isinstance(identifier, ast.Name) or identifier.id not in imports:
        return None
    rel, original = imports[identifier.id]
    value = module_tables(parse(rel))[0].get(original)
    if not value:
        return None
    return {'value': value[0], 'kind': 'page limit' if original != 'MAX_LIMIT' else 'max limit',
            'at': f'{Path(rel).name}:{value[1]}({original})'}


class ParsedRoute:
    """A ROUTES entry read from source text, shaped like the real Route for the canonical matcher.

    `verify_workbench_route_calls.route_matches` calls `route.accepts(match)`, so a bare data
    object is not compatible with the one owner of that logic. A route carrying a `when=`
    predicate cannot be evaluated from AST, and answering `True` for it would over-match: so
    it raises `ValueError`, which is the exception the caller already catches and reports as
    "dynamic call shape". Exactly one GET route carries `when` today, and it is not a list route.
    """

    __slots__ = ('method', 'pattern', 'action', 'exact', 'path_only', 'has_when')

    def __init__(self, method, pattern, action, exact, path_only, has_when):
        self.method = method
        self.pattern = pattern
        self.action = action
        self.exact = exact
        self.path_only = path_only
        self.has_when = has_when

    def accepts(self, match):
        if not self.has_when:
            return True
        raise ValueError(f'{self.action} carries a when= predicate this text reader cannot '
                         'evaluate; treating it as a dynamic call shape rather than guessing')


def live_routes():
    """Read the route table out of the source text instead of importing it.

    The first version imported `design_lab.http_service` for ROUTES. That made this script's
    dependency set equal the product's, and the workbench strict-TS job runs it with plain
    `python3` in a node job that installs no Python third-party packages at all -- so the
    import reached `image_assets`, wanted `PIL`, and the step died on
    `MEASURE_SOURCE_MOVED cannot import the route table: ModuleNotFoundError: No module
    named 'PIL'`. It passed locally because the project venv does have Pillow, which is
    exactly the shape of a false green: a measuring tool that needs more than the toolchain
    the gate actually has is not a gate.

    The static reader this file already uses for constants (`parse` / `module_tables`) is the
    right owner, so ROUTES is now parsed from the source. Only `method`, `pattern` and `action`
    are consumed downstream; a pattern built from a named constant is resolved where the
    constant is a plain string and marked `<expr>` otherwise, because a fabricated pattern
    would be worse than an admitted imprecise one.
    """
    tree = parse(HTTP_REL)
    routes_node = None
    tables = module_tables(tree)[0]
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(t, ast.Name) and t.id == 'ROUTES' for t in node.targets):
            routes_node = node.value
            break
    if not isinstance(routes_node, (ast.Tuple, ast.List)):
        raise SystemExit('MEASURE_SOURCE_MOVED no ROUTES tuple literal found in '
                         f'{HTTP_REL} -- the route inventory is no longer a literal this '
                         'reader can follow')

    def literal(node):
        if isinstance(node, ast.Constant):
            return node.value if isinstance(node.value, str) else None
        if isinstance(node, ast.JoinedStr):
            return ''.join(str(v.value) if isinstance(v, ast.Constant) else '<expr>'
                           for v in node.values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = literal(node.left), literal(node.right)
            return f'{left if left is not None else "<expr>"}' \
                   f'{right if right is not None else "<expr>"}'
        if isinstance(node, ast.Name):
            entry = tables.get(node.id)
            if entry:
                return entry[0]
            return '<expr>'
        return '<expr>'

    routes = []
    for call in routes_node.elts:
        if not (isinstance(call, ast.Call) and getattr(call.func, 'id', '') == 'Route'):
            raise SystemExit(f'MEASURE_SOURCE_MOVED a ROUTES member is not a Route(...) call: '
                             f'{ast.dump(call)[:80]}')
        positional = [literal(a) for a in call.args]
        if len(positional) < 3:
            raise SystemExit('MEASURE_SOURCE_MOVED Route(...) lost its (method, pattern, action) '
                             'positional shape')
        method, pattern, action = positional[0], positional[1], positional[2]
        keywords = {k.arg: (getattr(k.value, 'value', None)) for k in call.keywords}
        routes.append(ParsedRoute(method=method, pattern=pattern, action=action,
                                  exact=bool(keywords.get('exact')),
                                  path_only=bool(keywords.get('path_only')),
                                  has_when='when' in keywords))
    if not routes:
        raise SystemExit('MEASURE_SOURCE_MOVED the ROUTES tuple parsed to zero routes')
    return routes


# ---------------------------------------------------------------------------
# 附件缩略图策略 (DL-KB-13 ①). The card asks what the attachment listing actually costs BEFORE
# anyone proposes a thumbnail, so two things are separated on purpose:
#
# * the POLICY, read out of the shipped bundle and the store on the asset read path -- does a
#   scaled variant exist anywhere, does a first paint pull image bytes, what box scales them;
# * the PRICE, measured against real files written through the real import path, because a
#   strategy nobody has timed is an opinion. No production behaviour is changed by this file:
#   it calls the same `ImageAssets.list()` that `GET /api/projects/<id>/assets` delegates to
#   (`http_service.py:_list_or_read_assets` is a one-line delegation), so what is timed here is
#   the handler's own cost centre, not a simulation of it.
# ---------------------------------------------------------------------------
ASSET_COUNTS = (1, 10, 50, 200)
ASSET_SIDE = 128
KB13_ROOT = REPO / '.project-local' / 'task-runtime' / 'kb13-weight'
SLED = re.compile(r'thumbnail|thumb\b|resize|rescaled|scale_|max_dim|preview_size', re.I)


def function_region(text: str, name: str) -> str:
    """The body of a top-level `function <name>` in the shipped bundle, up to its closing brace."""
    start = text.find('function ' + name)
    if start < 0:
        return ''
    end = text.find('\n}\n', start)
    return text[start:end] if end > 0 else text[start:]


def thumbnail_policy() -> dict:
    """What the shipped client and the asset store actually do about attachment pixels."""
    bundle = read(REPO / 'apps/workbench/build/main.js').decode('utf-8')
    store = read(REPO / 'src/design_lab/image_assets.py').decode('utf-8')
    picker = function_region(bundle, 'referencePickerForProject')
    panel = function_region(bundle, 'renderReferencePanel')
    style = read(REPO / 'apps/workbench/style.css').decode('utf-8')
    rules = re.findall(r'\.ref-preview\s*\{([^}]*)\}', style)
    box = re.findall(r'(object-fit\s*:\s*[\w-]+|max-width\s*:\s*[\w%]+|max-height\s*:\s*[\w%]+)',
                     '\n'.join(rules))
    return {
        'listRoute': '/api/projects/:id/assets',
        'pixelRoute': '/api/projects/:id/assets/:img/content',
        'scaledVariantSymbolsInStore': sorted({m.group(0) for m in SLED.finditer(store)}),
        'listRowsWithImgElement': picker.count('el("img"'),
        'listRowsFetchingContent': picker.count('/content'),
        'panelImgElements': panel.count('el("img"'),
        'panelContentFetches': panel.count('/assets/'),
        'panelClickHandlers': panel.count('addEventListener("click"'),
        'previewAssetDefined': 'previewAsset' in panel,
        'previewBoxRules': box,
        'assetContentFetchesInBundle': len(re.findall(r'/assets/\$\{[A-Za-z0-9_]*\}/content',
                                                      bundle)),
        'bundleRegionBytes': {'referencePickerForProject': len(picker),
                              'renderReferencePanel': len(panel)},
    }


def png_fixture(width: int, height: int) -> bytes:
    """A valid PNG built from stdlib only.

    Same chunk grammar as `design-lab/tests/test_design_layer_http.py::_png_bytes()` (that helper
    makes a 1x1), at a size that actually decodes -- a 1x1 would measure call overhead, not the
    cost of verifying real reference material.
    """
    import struct
    import zlib
    signature = b'\x89PNG\r\n\x1a\n'

    def chunk(tag, data):
        out = struct.pack('>I', len(data)) + tag + data
        return out + struct.pack('>I', zlib.crc32(tag + data) & 0xFFFFFFFF)

    rows = bytearray()
    for y in range(height):
        rows.append(0)                                     # filter type 0 per scanline
        for x in range(width):
            rows += bytes(((x * 7 + y * 3) % 256, (x * 3) % 256, (y * 5) % 256))
    return (signature
            + chunk(b'IHDR', struct.pack('>IIBBBBB', width, height, 8, 2, 0, 0, 0))
            + chunk(b'IDAT', zlib.compress(bytes(rows), 6))
            + chunk(b'IEND', b''))


def asset_list_baseline(counts=ASSET_COUNTS, side=ASSET_SIDE, passes=3, clean=False,
                        corpus=None) -> dict:
    """The wall time, bytes and per-step split of the attachment list, at four corpus sizes."""
    import base64
    import hashlib
    import platform
    import shutil

    first_party()
    from design_lab.image_assets import ImageAssets, inspect_image
    from design_lab.service import ProjectService

    root = Path(corpus) if corpus else KB13_ROOT / 'corpus'
    if root.exists():
        # Reusing a leftover corpus would report somebody else's bytes as this run's measurement,
        # which is the one thing a baseline may not do.
        shutil.rmtree(root)
    project_root = root / 'project'
    project_root.mkdir(parents=True)
    (project_root / 'AGENTS.md').write_text('# DL-KB-13 attachment baseline corpus\n',
                                            encoding='utf-8', newline='\n')
    data = png_fixture(side, side)
    encoded = base64.b64encode(data).decode('ascii')
    points, seeded, start = [], 0, time.perf_counter()
    try:
        service = ProjectService(project_root)
        project = service.create_project('DL-KB-13 attachment baseline')['id']
        images = ImageAssets(service)
        for target in counts:
            while seeded < target:
                images.import_image(project, encoded, f'kb13-{seeded:05d}')
                seeded += 1
            walls, first = [], None
            for _ in range(passes):
                began = time.perf_counter()
                rows = images.list(project)
                elapsed = (time.perf_counter() - began) * 1000.0
                if first is None:
                    first = elapsed
                walls.append(elapsed)
            # The same steps `_verified()` runs per row, timed one at a time on the same rows.
            # The loop's own wall is measured too: comparing the parts against a *different* pass
            # (the median above) is how an instrument reports a negative "everything else".
            check = read_ms = hash_ms = decode_ms = 0.0
            total_bytes = 0
            began_split = time.perf_counter()
            for row in images._read(project):
                began = time.perf_counter()
                path = images.paths.checked_path(row[2])
                if path.is_relative_to(images.paths.category_dir('projects', project)):
                    path.stat()
                check += time.perf_counter() - began
                began = time.perf_counter()
                payload = path.read_bytes()
                read_ms += time.perf_counter() - began
                total_bytes += len(payload)
                began = time.perf_counter()
                hashlib.sha256(payload).hexdigest()
                hash_ms += time.perf_counter() - began
                began = time.perf_counter()
                inspect_image(payload)
                decode_ms += time.perf_counter() - began
            split_wall = (time.perf_counter() - began_split) * 1000.0
            began = time.perf_counter()
            content = images.content(project, rows[0]['id'])
            content_ms = (time.perf_counter() - began) * 1000.0
            payload_text = json.dumps({'assets': rows}).encode('utf-8')
            payload_bytes = len(payload_text)
            points.append({
                'assets': len(rows),
                'listMedianMs': round(statistics.median(walls), 2),
                'listMinMs': round(min(walls), 2), 'listMaxMs': round(max(walls), 2),
                'firstPassMs': round(first, 2),
                'msPerRow': round(statistics.median(walls) / max(len(rows), 1), 3),
                'bytesRead': total_bytes,
                'perAssetBytes': len(data),
                'splitWallMs': round(split_wall, 2),
                'pathCheckMs': round(check * 1000.0, 2),
                'readMs': round(read_ms * 1000.0, 2),
                'hashMs': round(hash_ms * 1000.0, 2),
                'decodeMs': round(decode_ms * 1000.0, 2),
                'unattributedMs': round(split_wall - (check + read_ms + hash_ms + decode_ms) * 1000.0, 2),
                'pathCheckPercent': round(100.0 * check * 1000.0 / split_wall, 1),
                'readPercent': round(100.0 * read_ms * 1000.0 / split_wall, 1),
                'hashPercent': round(100.0 * hash_ms * 1000.0 / split_wall, 1),
                'decodePercent': round(100.0 * decode_ms * 1000.0 / split_wall, 1),
                'listJsonBytes': payload_bytes,
                'listJsonGzipBytes': len(gzip.compress(payload_text, 9)),
                'previewAllBase64Bytes': sum(4 * ((row['byte_size'] + 2) // 3) for row in rows),
                'onePreviewMs': round(content_ms, 2),
                'onePreviewJsonBytes': len(json.dumps(content).encode('utf-8')),
            })
        return {'host': f'{platform.system()} {platform.release()} / {platform.machine()} / '
                        f'{platform.python_version()}',
                'corpus': str(root.relative_to(REPO)),
                'corpusBytes': sum(f.stat().st_size for f in root.rglob('*') if f.is_file()),
                'fixtureSide': side, 'fixtureBytes': len(data),
                'seedSeconds': round(time.perf_counter() - start, 1),
                'points': points, 'removed': clean}
    finally:
        if clean:
            shutil.rmtree(root, ignore_errors=True)


def measure(with_assets: bool = False, clean: bool = False) -> dict:
    files = {}
    remote_hits = []
    inline_bytes = 0
    inline_count = 0
    bundle_text = ''
    for label, path in SHIPPED:
        raw = read(path)
        files[label] = {'bytes': len(raw), 'gzip': len(gzip.compress(raw, 9)),
                        'sha256': __import__('hashlib').sha256(raw).hexdigest()[:16]}
        text = raw.decode('utf-8', errors='replace')
        if label == 'bundle':
            bundle_text = text
        remote_hits += [f'{label}: {hit}' for hit in remote_refs(text)]
        for uri in DATA_URI.finditer(text):
            inline_count += 1
            inline_bytes += len(uri.group(0))
    shell = read(REPO / 'apps/workbench/shell.ts').decode('utf-8')
    budget = 'budget' in (REPO / 'design.qa.yaml').read_text(encoding='utf-8').lower()
    return {'files': files, 'remoteReferences': remote_hits,
            'inlineDataUris': {'count': inline_count, 'bytes': inline_bytes,
                               'shareOfBundlePercent': round(
                                   100.0 * inline_bytes / files['bundle']['bytes'], 2)},
            'mountPoints': len(EL_CALL.findall(shell)),
            'routedViews': len(ROUTE_VIEWS.findall(
                shell[shell.index('export const ROUTE_VIEWS'):shell.index('\n];',
                                                                          shell.index('export const ROUTE_VIEWS'))])),
            'pageSizes': limits(),
            'modules': modules(bundle_text),
            'listRows': list_row_readings(),
            'thumbnailPolicy': thumbnail_policy(),
            'assetListBaseline': asset_list_baseline(clean=clean) if with_assets else None,
            'assetsMeasured': with_assets,
            'budgetDeclared': budget}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--no-assets', action='store_true',
                        help='skip the seeded attachment corpus (no writes at all)')
    parser.add_argument('--with-assets', action='store_true',
                        help='force the attachment baseline even together with --check')
    parser.add_argument('--clean', action='store_true',
                        help='remove the attachment corpus after measuring')
    args = parser.parse_args()
    # `--check` is the CI verdict step (.github/workflows/canonical-verify.yml). It stays as fast
    # and as read-only as it has always been unless somebody asks for the corpus there too.
    with_assets = (args.with_assets or not args.check) and not args.no_assets
    data = measure(with_assets=with_assets, clean=args.clean)
    if args.json:
        print(json.dumps(data, ensure_ascii=False, sort_keys=True))
    else:
        for label, entry in data['files'].items():
            print(f'WEIGHT {label:10} bytes={entry["bytes"]:>8} gzip={entry["gzip"]:>7} '
                  f'sha={entry["sha256"]}')
        print(f'WEIGHT inline-data count={data["inlineDataUris"]["count"]} '
              f'bytes={data["inlineDataUris"]["bytes"]} '
              f'share={data["inlineDataUris"]["shareOfBundlePercent"]}% of the bundle')
        print(f'WEIGHT mountPoints={data["mountPoints"]} routedViews={data["routedViews"]}')
        for label, value in data['pageSizes'].items():
            print(f'WEIGHT page {label} = {value}')
        for span in data['modules']['largest']:
            print(f'WEIGHT module {span["name"]:34} bytes={span["bytes"]:>7} '
                  f'share={span["sharePercent"]:>5}%')
        print(f'WEIGHT modules declarations={data["modules"]["declarations"]} '
              f'coverage={data["modules"]["coveragePercent"]}% of the bundle')
        print_list_rows(data['listRows'])
        print_thumbnail_policy(data['thumbnailPolicy'])
        if data['assetListBaseline'] is None:
            print('THUMBNAIL baseline SKIPPED (--no-assets, or --check without --with-assets): '
                  'the attachment price is the part of 先量 that needs a seeded corpus, so run '
                  'without --check to get it. Nothing above this line wrote a file.')
        else:
            print_asset_baseline(data['assetListBaseline'])
        print(f'WEIGHT remoteReferences={len(data["remoteReferences"])} '
              f'budgetDeclared={data["budgetDeclared"]}')
        for hit in data['remoteReferences']:
            print(f'WEIGHT REMOTE_REFERENCE {hit}')
    if not data['budgetDeclared']:
        print('WEIGHT NOTE design.qa.yaml declares no performance budget; a ceiling is an owner '
              'decision, so these are baseline readings, not a pass/fail judgement on size.')
    if args.check:
        # An empty or blind attribution would let this script keep printing a confident table of
        # nothing, so the share it actually accounts for is part of the verdict.
        if data['modules']['coveragePercent'] < 80.0:
            print(f"WORKBENCH_WEIGHT_GATE=FAIL module attribution covers only "
                  f"{data['modules']['coveragePercent']}% of the bundle -- the bundle is no longer"
                  f" shaped like this reader assumes")
            return 1
        rows = data['listRows']
        # The same rule the route-call gate already follows: a reader that matched nothing must
        # not report a pass. Zero list routes means the ROUTES table or the handler naming moved,
        # and a blind reader is how a stale "no limit here" claim reaches an owner.
        if not rows['listRoutes'] or rows['readerError']:
            print('WORKBENCH_WEIGHT_GATE=FAIL the list-row reader found no list route '
                  f"(routes={rows['listRoutes']} frontend_calls={rows['frontendCallSites']} "
                  f'reason={rows["readerError"]}) -- the route table or the call-site scanner is '
                  'no longer shaped like this reader assumes')
            return 1
        if data['remoteReferences']:
            print('WORKBENCH_WEIGHT_GATE=FAIL remote references in shipped bytes: '
                  f'{len(data["remoteReferences"])}')
            return 1
        print(f'WORKBENCH_WEIGHT_GATE=OK remote=0 bundle_gzip={data["files"]["bundle"]["gzip"]}')
    return 0


def print_list_rows(rows: dict) -> None:
    """列表初始行数, one line per list-bearing GET route."""
    print(f'LISTROWS list_routes={rows["listRoutes"]} bounded={rows["bounded"]} '
          f'without_limit={len(rows["withoutLimit"])} '
          f'frontend_call_sites_scanned={rows["frontendCallSites"]}')
    if rows['callSiteError']:
        print('LISTROWS NOTE the canonical route-call matcher did not load in this '
              f"interpreter: {rows['callSiteError']} -- the bound readings above come from the "
              'parsed route table and stand on their own; only the "what the page asks for" '
              f"column is missing (frontend_call_sites={rows['frontendCallSites']}) "
              '-- the client half below is absent, not zero.')
    for row in rows['routes']:
        initial = 'NONE' if row['initialRows'] is None else str(row['initialRows'])
        at = row['boundAt'] or '-'
        ceiling = '-' if row['maxRows'] is None else str(row['maxRows'])
        asked = '-' if not row['clientLimits'] else ','.join(str(v) for v in row['clientLimits'])
        kind = (row['boundKind'] or '-').replace(' ', '-')
        print(f'LISTROWS {row["action"]:30} initial_rows={initial:>4} kind={kind:<13} '
              f'at={at:<34} max_rows={ceiling:>4} client_calls={row["clientCalls"]} '
              f'client_limits={asked} client_without_limit={row["clientCallsWithoutLimit"]}')
        for note in row['unresolved']:
            print(f'LISTROWS NOTE {row["action"]}: {note}')
    if rows['withoutLimit']:
        print('LISTROWS without_limit=' + ','.join(rows['withoutLimit']))
    print('LISTROWS NOTE initial_rows is the bound the READ PATH states about itself (a limit the '
          'handler passes, a method default, an SQL LIMIT, a rows[:n] slice), at the file:line '
          'printed; client_limits is what the shipped workbench source asks for with it. NONE '
          'means none of those four exists, so the first paint returns every stored row.')


def print_thumbnail_policy(policy: dict) -> None:
    print(f'THUMBNAIL policy list={policy["listRoute"]} pixels={policy["pixelRoute"]}')
    print(f'THUMBNAIL policy server_scaled_variant='
          f'{"ABSENT" if not policy["scaledVariantSymbolsInStore"] else ",".join(policy["scaledVariantSymbolsInStore"])}'
          f' (image_assets.py has no thumbnail/resize/scale symbol)')
    print(f'THUMBNAIL policy first_paint_rows_img={policy["listRowsWithImgElement"]} '
          f'first_paint_rows_bytes_fetched={policy["listRowsFetchingContent"]} '
          f'(referencePickerForProject region, {policy["bundleRegionBytes"]["referencePickerForProject"]} B '
          'of shipped bundle)')
    print(f'THUMBNAIL policy on_click_preview img={policy["panelImgElements"]} '
          f'fetches={policy["panelContentFetches"]} clicks={policy["panelClickHandlers"]} '
          f'previewAsset={policy["previewAssetDefined"]} '
          f'content_fetches_in_whole_bundle={policy["assetContentFetchesInBundle"]}')
    print(f'THUMBNAIL policy preview_box={";".join(policy["previewBoxRules"]) or "-"} '
          '(full-resolution bytes scaled by the browser; no server-side downscaled variant exists)')


def print_asset_baseline(baseline: dict) -> None:
    print(f'THUMBNAIL baseline host={baseline["host"]}')
    print(f'THUMBNAIL baseline fixture={baseline["fixtureSide"]}px png '
          f'per_asset_bytes={baseline["fixtureBytes"]} '
          f'corpus={baseline["corpus"]} corpus_bytes={baseline["corpusBytes"]} '
          f'seed_seconds={baseline["seedSeconds"]} '
          f'removed={baseline["removed"]}')
    for point in baseline['points']:
        print(f'THUMBNAIL assetlist n={point["assets"]:<4} wall_ms={point["listMedianMs"]:<7} '
              f'(first={point["firstPassMs"]} min={point["listMinMs"]} max={point["listMaxMs"]}) '
              f'ms_per_row={point["msPerRow"]:<6} bytes_read={point["bytesRead"]:<9} '
              f'list_json_bytes={point["listJsonBytes"]:<7} '
              f'list_json_gzip={point["listJsonGzipBytes"]:<6} '
              f'preview_all_base64_bytes={point["previewAllBase64Bytes"]}')
    for point in baseline['points']:
        print(f'THUMBNAIL breakdown n={point["assets"]:<4} split_wall_ms={point["splitWallMs"]:<7} '
              f'path_check={point["pathCheckMs"]}ms({point["pathCheckPercent"]}%) '
              f'read={point["readMs"]}ms({point["readPercent"]}%) '
              f'hash={point["hashMs"]}ms({point["hashPercent"]}%) '
              f'decode={point["decodeMs"]}ms({point["decodePercent"]}%) '
              f'unattributed={point["unattributedMs"]}ms '
              f'| one_preview={point["onePreviewMs"]}ms '
              f'({point["onePreviewJsonBytes"]} B json)')
    print('THUMBNAIL NOTE 这是基线测量（先量），不是优化：本轮没有改任何生产行为，没有加缩略图，'
              '没有删内容，没有换栈。语料由本脚本用真实写入路径（ImageAssets.import_image）现做，'
              '字节刚写下时多在 OS 缓存里，first_pass 是同一轮里最接近冷缓存的一遍。'
              '计时对象是 GET /api/projects/<id>/assets 的处理器本体（一行委派到 ImageAssets.list），'
              '不含 HTTP 传输与序列化以外的东西。')


if __name__ == '__main__':
    raise SystemExit(main())
