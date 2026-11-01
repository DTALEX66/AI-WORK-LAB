#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-CONTRACT-BINDINGS: every declared contract is either honoured or named as inert.

Why this gate exists. ``design-lab/schemas/contracts/`` holds 32 JSON Schemas and NONE of
them is read at runtime: ``grep -rn "schemas/contracts" src/`` returns nothing, and the
apparent hits in ``src/design_lab/`` are prose or version literals belonging to a different
document (``interop/delivery_receipt.py`` loads the ROOT-level
``interop-delivery-receipt-v2.schema.json``, not ``contracts/delivery-receipt.schema.json``).
Enforcement was a synthetic-fixture test (``tests/test_contract_schema_integrity.py``) that
invents its own instances, so the directory read as coverage while the product answered a
different vocabulary. "Declared but unread" is the same false-green shape as a vocabulary
nobody emits: a reader sees a schema and assumes a boundary is enforced.

This gate does not pretend the directory is real. It records, per schema, whether a place in
``src/`` produces or consumes that exact shape, and it re-checks that claim on every run --
so a BINDING cannot rot into fiction and an INERT row cannot be laundered into "future work".

What it enforces:

1. COVERAGE -- every file in ``design-lab/schemas/contracts/`` has exactly one row in
   ``design-lab/config/contract-bindings.json``. A new schema with no row is red
   (UNLISTED_SCHEMA); a listed schema that vanished is red (SCHEMA_ROW_ABSENT); two rows for
   one file is red (DUPLICATE_SCHEMA_ROW).
2. BINDING TEETH -- a row may say BINDING only if it names ``path:line`` producers/consumers
   in ``src/`` that still exist AND still contain the declared version string
   (BINDING_ROTTEN). The row's version must equal the schema's ``schemaVersion`` const
   (VERSION_DRIFT), so a one-sided bump is a finding, not an orphaned document.
3. INERT HONESTY -- an INERT row must carry a reason, must name no instance
   (INERT_ROW_HAS_INSTANCE: the schema is live, reclassify it), and must not phrase the truth
   as pending work (INERT_REASON_EVASIVE).
4. BOUNDARY COVERAGE -- every route ``src/design_lab/http_service.py`` dispatches on must
   have exactly one ledger row. Each row names its handler symbol, which must still appear in
   ``http_service.py`` (ROUTE_HANDLER_MISSING), and is either BOUND_SCHEMA -- a schema file
   that exists, carries the version string, and an emitter in ``src/`` that still produces
   that version -- or SCHEMA_LESS with a reason that says why nothing validates it. This is
   the check that would have caught the artifact-preflight gap (commit 1ea64bbe: a payload
   claiming ``design-lab/artifact-preflight/v1`` with no schema behind it).
5. STALE IN EITHER DIRECTION -- a SCHEMA_LESS row whose payload declares a version for which
   a schema now exists is red (SCHEMA_LESS_STALE): the ledger describes a debt someone has
   already paid.
6. NOTHING TO COMPARE IS A FAILURE. Zero schema files, zero ledger rows, zero routes found,
   zero route rows, or zero BOUND_SCHEMA route rows are each red. A gate that matched nothing
   must not report a pass.
7. THE VERSION COMES FROM THE CODE, NOT FROM THE ROW. A row that names an emitter is held
   against what that file actually writes as a ``schemaVersion`` VALUE (parsed from the AST, so
   a docstring that quotes a version is not an emission and ``{'schemaVersion': SCHEMA_VERSION}``
   resolved through the module's own assignment is). If the file emits versions and the row's
   version is not one of them, that is EMITTER_VERSION_DISAGREES; if the row drops the version
   field while its emitter still writes one, that is SCHEMA_LESS_DEBT_UNNAMED. This is the check
   that stops a debt row being laundered into an unremarkable one by deleting the ``version``
   line -- and it is why a paid-off debt is flipped to BOUND_SCHEMA here and re-validated against
   a real response by design-lab/scripts/verify_route_payload_contracts.py, rather than quietly
   stopped being mentioned.
8. EVERY CITATION IS A PATH FIRST. Each ``instances`` / ``tests`` / ``fixtures`` entry must start
   with a repository path, the file must exist, and a ``:line`` anchor must fall inside it
   (CITATION_MALFORMED, CITATION_STALE, CITATION_LINE_OUT_OF_RANGE). One measured entry read
   'generated at run time by <path>:45' -- a sentence inside the field whose whole purpose is to be
   re-checkable, so the row looked evidenced while nothing checked it.
9. INERT IS A CLAIM ABOUT THE SOURCES, SO IT IS RE-MEASURED. An INERT row is red if any file under
   ``src/``, ``packages/``, ``apps/`` or ``integrations/`` names that schema (INERT_BUT_NAMED_BY_PRODUCT),
   which is how a schema someone wired up cannot keep hiding as unimplemented. Measured over the
   shipped tree this convicts nothing, so it is the strict direction with no false reds today.

Usage:
    python design-lab/scripts/verify_contract_bindings.py [--list-routes]
Exit 0 when the ledger is true, 1 otherwise. The last line printed is
``VERIFY_CONTRACT_BINDINGS=PASS|FAIL ...``.
"""
from __future__ import annotations

import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTRACT_DIR = 'design-lab/schemas/contracts'
LEDGER_REL = 'design-lab/config/contract-bindings.json'
HTTP_REL = 'src/design_lab/http_service.py'
SCHEMA_ROOT = 'design-lab/schemas'

BINDING = 'BINDING'
INERT = 'INERT'
STATUSES = (BINDING, INERT)

BOUND_SCHEMA = 'BOUND_SCHEMA'
SCHEMA_LESS = 'SCHEMA_LESS'
ROUTE_KINDS = (BOUND_SCHEMA, SCHEMA_LESS)

# An INERT row that says one of these is not reporting the truth it was asked to report.
EVASIVE = ('future work', 'roadmap', 'planned', 'to be implemented', 'will be implemented',
           'will implement', 'not yet', 'eventually', 'todo', 'for now', 'later')

# A SCHEMA_LESS row whose payload still declares a version must say so in plain words.
DEBT_PHRASES = ('no schema', 'nothing validates', 'never validated', 'unvalidated')


def declared_version(schema_doc) -> str | None:
    """The version a schema binds: its ``schemaVersion`` const, or its $id if it is a version."""
    const = ((schema_doc.get('properties') or {}).get('schemaVersion') or {}).get('const')
    if isinstance(const, str):
        return const
    ident = schema_doc.get('$id')
    return ident if isinstance(ident, str) and '/v' in ident else None


def schema_version_index(root: Path) -> dict[str, list[str]]:
    """version -> schema files declaring it, so a paid-off debt cannot stay listed as unpaid."""
    index: dict[str, list[str]] = {}
    for path in sorted(root.rglob('*.json')):
        if 'contracts' in path.parts:
            continue
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict):
            continue
        version = declared_version(doc)
        if version:
            index.setdefault(version, []).append(path.relative_to(root.parent).as_posix())
        # A schema may bind the version as an enum member or bare literal rather than a const.
        text = path.read_text(encoding='utf-8', errors='ignore')
        for token in set(WORD_VERSIONS.findall(text)):
            index.setdefault(token, [])
            if path.relative_to(root.parent).as_posix() not in index[token]:
                index[token].append(path.relative_to(root.parent).as_posix())
    return index


WORD_VERSIONS = re.compile(r'"(design-lab/[a-z0-9-]+/v[0-9]+)"')

#: A boundary version is `design-lab/<name>/v<N>`; an interop spec version ("2025.10") is not
#: one, so it is collected by the schema-text scan and never demanded of an emitter here.
VERSION_TOKEN = re.compile(r'^design-lab/[a-z0-9][a-z0-9.-]*/v[0-9]+$')
IDENTIFIER = re.compile(r'\b[A-Za-z_][A-Za-z0-9_]*\b')


def emitted_versions(path: Path) -> set[str]:
    """Every version this file WRITES as a ``schemaVersion`` value.

    Parsed from the AST for the same reason the route set is: a docstring that quotes
    ``design-lab/artifact-preflight/v1`` is prose, not an emission, while
    ``{'schemaVersion': SCHEMA_VERSION}`` is an emission whose value lives in a module-level
    assignment. Only a dict key literally named ``schemaVersion`` counts, so the registry
    comparison at ``task_resources.py:52`` (``doc.get("schemaVersion") != REGISTRY_SCHEMA``)
    stays an input check and is not mistaken for a boundary payload.
    """
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return set()
    names: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if not (isinstance(value, ast.Constant) and isinstance(value.value, str)):
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                names[target.id] = value.value
    found: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Dict):
            continue
        for key, value in zip(node.keys, node.values):
            if not (isinstance(key, ast.Constant) and key.value == 'schemaVersion'):
                continue
            literal = None
            if isinstance(value, ast.Constant) and isinstance(value.value, str):
                literal = value.value
            elif isinstance(value, ast.Name):
                literal = names.get(value.id)
            if isinstance(literal, str) and VERSION_TOKEN.match(literal):
                found.add(literal)
    return found



def module_string_constants(path: Path) -> dict[str, str]:
    """Top-level ``NAME = "string"`` assignments in one file.

    Needed because a pointer may legitimately land on ``"schemaVersion": SCHEMA_VERSION,`` -- the
    line does not spell the version out, and the value it names lives one assignment away.
    """
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return {}
    found: dict[str, str] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign) and node.value is not None:
            targets, value = [node.target], node.value
        else:
            continue
        if isinstance(value, ast.Constant) and isinstance(value.value, str):
            for target in targets:
                if isinstance(target, ast.Name):
                    found[target.id] = value.value
    return found


def prose_lines(path: Path) -> set[int]:
    """Line numbers covered by a bare string statement -- a module, class or function docstring.

    Versions get quoted in prose all the time (that is how a migration note explains what it
    changed), and a pointer that lands there honours nothing.
    """
    try:
        tree = ast.parse(path.read_text(encoding='utf-8', errors='ignore'), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return set()
    covered: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Expr) and isinstance(node.value, ast.Constant) \
                and isinstance(node.value.value, str):
            covered.update(range(node.lineno, (node.end_lineno or node.lineno) + 1))
    return covered


def emitter_pointer_errors(repo: Path, route: str, ref: str, version: str) -> list[str]:
    """Does the line the pointer names actually carry this version, or the constant holding it?

    A pointer without a number, a number past the end of the file, and a line that is about
    something else are three different findings, and all three mean the row's stated location is
    not where the value comes from.
    """
    head, _, tail = ref.partition(':')
    digits = ''
    for character in tail.strip():
        if not character.isdigit():
            break
        digits += character
    if not digits:
        return [f'{route}: EMITTER_POINTER_SHAPE {ref!r} -- an emitter pointer is `path:line`, and '
                'without a number there is nothing to honour']
    path = repo / head
    if not path.is_file():
        return []  # ROUTE_EMITTER_MISSING already says the file is gone; one defect, one line.
    lines = path.read_text(encoding='utf-8', errors='ignore').splitlines()
    number = int(digits)
    if not 1 <= number <= len(lines):
        return [f'{route}: EMITTER_POINTER_OUT_OF_RANGE {ref!r} -- that file has {len(lines)} '
                'lines, so the row points at a location that does not exist']
    line = lines[number - 1]
    prose = number in prose_lines(path)
    code = line.split('#', 1)[0] if '#' in line else line
    if prose:
        return [f'{route}: EMITTER_POINTER_IS_PROSE {ref!r} falls inside a docstring, and a '
                f'sentence that mentions {version!r} is not where that version comes from -- '
                '`emitted_versions` already refuses to count a quoted version as an emission, so '
                'the line half of the pointer has to agree with the file half']
    if version and version in code:
        return []
    constants = module_string_constants(path)
    if any(constants.get(token) == version for token in IDENTIFIER.findall(code)):
        return []
    if version and version in line:
        return [f'{route}: EMITTER_POINTER_IS_PROSE {ref!r} carries {version!r} only in a comment '
                'on that line, which is a note about the version rather than the version being '
                'written or compared']
    return [f'{route}: EMITTER_POINTER_NOT_THE_VERSION {ref!r} holds {line.strip()[:70]!r}, which '
            f'neither writes {version!r} nor names a module-level constant whose value it is -- the '
            'line is decoration: the gate reads the file half of this pointer only, so a row can '
            'keep pointing somewhere else entirely and still pass']


def route_tokens(path: Path) -> list[tuple[str, int]]:
    """Every path this dispatcher matches on, as (key, line).

    Parsed from the AST rather than a regex over the source: the patterns are written as
    adjacent string literals concatenated across lines with ``+ NAME +`` continuations, and a
    text regex either merges two routes or splits one. A Name in a concatenation is rendered
    ``<NAME>`` so the key stays stable when the referenced constant's value changes.

    Two populations are read: the module-level ``ROUTES`` table (the authenticated API
    surface, one entry per method so ``/api/projects`` legitimately appears for GET and POST),
    and any dispatch-site comparison still written directly in ``dispatch`` -- the three
    pre-auth entries (``/api/local-session``, ``/workbench``, ``workbench.ROUTES``). The second
    walk is what lets a reviewer add a route without touching the table and still be convicted
    as UNLISTED_ROUTE instead of silently invisible.
    """
    tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    found: list[tuple[str, int]] = []

    def literalise(node) -> str | None:
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        if isinstance(node, ast.JoinedStr):
            return None
        if isinstance(node, ast.Name):
            return f'<{node.id}>'
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            left, right = literalise(node.left), literalise(node.right)
            if left is not None and right is not None:
                return left + right
        return None

    # The table: `ROUTES = (Route('GET', <pattern>, '<handler>'), ...)`. The pattern is
    # argument 1; a Name concatenated into it becomes `<NAME>`, matching the ledger key.
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
                isinstance(target, ast.Name) and target.id == 'ROUTES'
                for target in node.targets):
            for element in getattr(node.value, 'elts', []):
                if isinstance(element, ast.Call) and len(element.args) >= 2:
                    key = literalise(element.args[1])
                    if key is not None and key.startswith('/'):
                        found.append((key, element.lineno))

    # A route may be dispatched on `self.path`, on `urlsplit(self.path).path`, or on a local
    # name bound to one of those. The third form is what the page branch uses now that the
    # query string is stripped before matching, and an indirected dispatch target is still a
    # dispatch target: refusing to see it would make a correct refactor read as a vanished
    # route, which is the same false red the gate exists to prevent on the other side.
    path_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and _is_self_path(node.value):
            path_names.update(t.id for t in node.targets if isinstance(t, ast.Name))

    for node in ast.walk(tree):
        if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
                and node.func.attr == 'fullmatch' and len(node.args) >= 2):
            pattern, target = literalise(node.args[0]), node.args[1]
            target_ok = isinstance(target, ast.Attribute) and target.attr == 'path'
            target_ok = target_ok or (isinstance(target, ast.Name) and target.id in path_names)
            if pattern and pattern.startswith('/') and target_ok:
                found.append((pattern, node.lineno))
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            op, comparator = node.ops[0], node.comparators[0]
            if isinstance(comparator, ast.Constant) and isinstance(comparator.value, str) \
                    and _is_self_path(node.left, path_names):
                if isinstance(op, ast.Eq):
                    found.append((comparator.value, node.lineno))
        if isinstance(node, ast.Compare) and len(node.ops) == 1 and isinstance(node.ops[0], ast.In) \
                and _is_self_path(node.left, path_names) \
                and isinstance(node.comparators[0], ast.Attribute) \
                and node.comparators[0].attr == 'ROUTES':
            found.append(('workbench.ROUTES', node.lineno))
    return found


def _is_self_path(node, path_names=frozenset()) -> bool:
    """``self.path``, ``urlsplit(self.path).path``, or a local name bound to either."""
    if isinstance(node, ast.Name) and node.id in path_names:
        return True
    if isinstance(node, ast.Attribute) and node.attr == 'path':
        value = node.value
        if isinstance(value, ast.Name) and value.id == 'self':
            return True
        if isinstance(value, ast.Call) and isinstance(value.func, ast.Name) \
                and value.func.id == 'urlsplit':
            inner = value.args[0] if value.args else None
            return isinstance(inner, ast.Attribute) and inner.attr == 'path'
    return False


def version_literals(path: Path, version: str) -> int:
    """How many times this source handles the version string ITSELF, not mentions it.

    The artifact-preflight gate counts quoted literals; this counts AST string constants
    whose value is exactly the version. The difference matters: ``production_preflight.py``
    carries the version in prose inside a docstring as well as in the emitted dict, and a
    substring test would call a docstring a producer. A docstring is one long Constant, so it
    cannot pass; ``{'schemaVersion': 'design-lab/x/v1'}``, ``x == 'design-lab/x/v1'`` and
    ``SCHEMA_VERSION = 'design-lab/x/v1'`` all do. A file that no longer assigns or compares
    the version is a rotted binding, which is what this gate is for.
    """
    text = path.read_text(encoding='utf-8', errors='ignore')
    try:
        tree = ast.parse(text, filename=str(path))
    except SyntaxError:
        return text.count(f"'{version}'") + text.count(f'"{version}"')
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and node.value == version)


def instance_path(ref: str) -> str:
    """`path:line` or `path:line note` -> `path`."""
    return ref.split(':', 1)[0].strip()


CITATION_PREFIXES = ('design-lab/', 'src/', 'apps/', 'packages/', 'scripts/', 'integrations/')
_LINE_SUFFIX = re.compile(r'^[^:]+:(\d+)')


def citation_errors(label: str, group: str, ref: str, repo: Path, *,
                    check_exists: bool = True) -> list[str]:
    """One citation in a row's instances / tests / fixtures list, judged as a path.

    These fields are how a row says 'this contract is exercised here', so an entry that is prose
    wearing a path's clothing is checked by nothing: one measured 2026-10-08 read 'generated at run
    time by design-lab/tests/host_fixtures/qualify_ocr_object_plan.py:45'.

    The rules are split so one defect yields one red line. Shape is checked for every group; a line
    anchor is checked whenever the file is present; absence is reported here only for ``fixtures``,
    because instances and tests already have their own rules for it (BINDING_ROTTEN,
    INERT_ROW_HAS_INSTANCE and TEST_ROW_STALE) and a second conviction for the same vanished file
    would make 'exactly N red lines' meaningless.
    """
    path = instance_path(ref)
    if not path.startswith(CITATION_PREFIXES):
        return [f'{label}: CITATION_MALFORMED {group} entry {ref!r} does not start with a '
                f'repository path ({", ".join(CITATION_PREFIXES)}); say what you mean in the reason']
    target = repo / path
    if not target.is_file():
        if check_exists:
            return [f'{label}: CITATION_STALE {group} entry {ref!r} -- {path} does not exist']
        return []
    match = _LINE_SUFFIX.match(ref)
    if not match:
        return []
    try:
        total = len(target.read_text(encoding='utf-8', errors='ignore').splitlines())
    except OSError as exc:
        return [f'{label}: CITATION_STALE {group} entry {ref!r} -- {path} cannot be read ({exc})']
    line = int(match.group(1))
    if line < 1 or line > total:
        return [f'{label}: CITATION_LINE_OUT_OF_RANGE {group} entry {ref!r} -- {path} has {total} '
                'lines; the cited anchor is not in it any more']
    return []


def product_corpus(repo: Path) -> dict[str, str]:
    """The text of every product source file, keyed by repo-relative path.

    Deliberately raw, comments and docstrings included. Measured 2026-10-08 this convicts nothing --
    no INERT schema is named by src/, packages/, apps/ or integrations/ even as prose -- so the
    stricter reading costs no false reds today, and it can only ever be over-strict, never blind:
    someone who writes a schema's file name into a product comment is being asked to justify the row,
    which is the right outcome for a claim that nothing implements it.
    """
    out = {}
    for scope in ('src', 'packages', 'apps', 'integrations'):
        base = repo / scope
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            if not path.is_file() or path.suffix not in {'.py', '.ts', '.mjs', '.json'}:
                continue
            if {'__pycache__', 'node_modules', 'build', 'dist'} & set(path.parts):
                continue
            try:
                out[path.relative_to(repo).as_posix()] = path.read_text(encoding='utf-8',
                                                                       errors='ignore')
            except OSError:
                continue
    return out


def check_contract_rows(repo: Path, rows, absent=frozenset()) -> tuple[list[str], dict]:
    errors, notes = [], []
    counted = {'BINDING': 0, 'INERT': 0}
    product = product_corpus(repo)
    for row in rows:
        rel = row.get('schema') or ''
        status = row.get('status')
        label = Path(rel).name or '<no schema path>'
        if status not in STATUSES:
            errors.append(f'{label}: BAD_STATUS {status!r} -- a row is either BINDING or INERT')
            continue
        counted[status] += 1
        path = repo / rel
        if not path.is_file():
            # The coverage pass already convicted this row once; a second red line for the same
            # defect would make "exactly N reds" meaningless.
            if rel not in absent:
                errors.append(f'{label}: SCHEMA_ROW_ABSENT {rel} -- listed in the ledger, not on disk')
            continue
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except ValueError as exc:
            errors.append(f'{label}: SCHEMA_ROW_ABSENT {rel} is not readable JSON: {exc}')
            continue
        declared = declared_version(doc)
        stated = row.get('version')
        if declared and stated != declared:
            errors.append(f'{label}: VERSION_DRIFT the schema binds {declared!r} but the ledger '
                          f'row says {stated!r}')
            continue
        instances = row.get('instances') or []
        tests = row.get('tests') or []
        fixtures = row.get('fixtures') or []
        for group, entries in (('instances', instances), ('tests', tests), ('fixtures', fixtures)):
            for ref in entries:
                errors.extend(citation_errors(label, group, ref, repo,
                                              check_exists=(group == 'fixtures')))
        for ref in tests:
            test_path = repo / instance_path(ref)
            if not test_path.is_file():
                errors.append(f'{label}: TEST_ROW_STALE {ref} -- the test that was said to '
                              'exercise this schema is gone')
        reason = (row.get('reason') or '').strip()
        if status == BINDING:
            if not instances:
                errors.append(f'{label}: BINDING_WITHOUT_INSTANCE -- a BINDING row must name a '
                              'src/ producer or consumer of this exact shape')
                continue
            live = 0
            for ref in instances:
                target = repo / instance_path(ref)
                if not target.is_file():
                    errors.append(f'{label}: BINDING_ROTTEN {ref} -- the named file no longer exists')
                    continue
                if not version_literals(target, stated):
                    errors.append(f'{label}: BINDING_ROTTEN {ref} -- the named file no longer '
                                  f'carries {stated!r} as a value it produces or compares; a '
                                  'prose mention is not a binding')
                    continue
                live += 1
            notes.append(f'{label}: BINDING instances={live} of {len(instances)} tests={len(tests)}')
        else:
            if instances:
                errors.append(f'{label}: INERT_ROW_HAS_INSTANCE -- the row says INERT but names '
                              f'{instances[0]!r}; an implemented schema must be BINDING')
            named = sorted(p for p, text in product.items() if label in text)
            if named:
                # The claim 'nothing implements this' is a claim about the product sources, so it is
                # re-checked against them rather than kept as prose. Either the row is stale because
                # someone wired the schema, or the name now appears in src/ for a reason worth
                # stating in this ledger instead of in a comment.
                errors.append(f'{label}: INERT_BUT_NAMED_BY_PRODUCT {named[0]} -- an INERT row may '
                              'not be named by product code; re-classify it or say why this is not '
                              'an implementation')
            if not reason:
                errors.append(f'{label}: INERT_REASON_MISSING -- an INERT row must say what is '
                              'actually true about it')
            else:
                lowered = reason.lower()
                hit = [word for word in EVASIVE if word in lowered]
                if hit:
                    errors.append(f'{label}: INERT_REASON_EVASIVE {hit} -- nothing implements '
                                  'this; say that instead of describing it as pending')
                notes.append(f'{label}: INERT')
    return errors, counted, notes


def check_route_rows(repo: Path, rows, http_text: str, index) -> tuple[list[str], dict]:
    errors, notes = [], []
    counted = {BOUND_SCHEMA: 0, SCHEMA_LESS: 0}
    for row in rows:
        route = row.get('route') or '<no route>'
        kind = row.get('kind')
        if kind not in ROUTE_KINDS:
            errors.append(f'{route}: BAD_ROUTE_KIND {kind!r} -- BOUND_SCHEMA or SCHEMA_LESS')
            continue
        counted[kind] += 1
        handler = row.get('handler') or ''
        if handler and handler not in http_text:
            errors.append(f'{route}: ROUTE_HANDLER_MISSING {handler} no longer appears in '
                          f'{HTTP_REL} -- the row describes a dispatcher that is not there')
        marker = row.get('marker')
        if marker and marker not in http_text:
            errors.append(f'{route}: ROUTE_MARKER_MISSING {marker!r} is not sent by {HTTP_REL}')
        version = row.get('version')
        emitter = row.get('emitter')
        reason = (row.get('reason') or '').strip()
        row_checks_start = len(errors)
        if emitter:
            # Rule 7: the version is taken from the emitter's own AST, so a row cannot keep
            # its claim by restating it. A file that writes no schemaVersion dict at all is
            # judged by what it does hold: the Adobe job validators compare the version rather
            # than minting it, and that is still a value the source produces or compares.
            # Where the old literal has vanished from the file outright, ROUTE_EMITTER_MISSING
            # below is the more specific finding and this stays quiet -- one defect, one line.
            target = repo / instance_path(emitter)
            emitted = emitted_versions(target)
            carries = version_literals(target, version) if version else 0
            if emitted and version and version not in emitted and carries:
                errors.append(f'{route}: EMITTER_VERSION_DISAGREES {emitter} writes '
                              f'{sorted(emitted)} as its schemaVersion, not {version!r} -- the '
                              'row binds a version this file no longer emits, while the old '
                              'literal still sits in the source and reads as a live binding')
            elif not version and emitter and kind == SCHEMA_LESS:
                errors.append(f'{route}: SCHEMA_LESS_DEBT_UNNAMED {emitter} is named as the '
                              'source of this payload while the row declares no version at all '
                              '-- dropping the debt line does not pay the debt')
            elif not emitted and version and kind == SCHEMA_LESS and not carries:
                errors.append(f'{route}: EMITTER_VERSION_DISAGREES {emitter} neither writes '
                              f'{version!r} as a schemaVersion nor carries it as a value it '
                              'produces or compares -- the row names an emitter that no longer '
                              'knows this version')
        if kind == BOUND_SCHEMA:
            if not (version and emitter and row.get('schema')):
                errors.append(f'{route}: BAD_ROUTE_KIND -- a BOUND_SCHEMA row must name schema, '
                              'version and emitter')
                continue
            schema_path = repo / row['schema']
            if not schema_path.is_file():
                errors.append(f'{route}: ROUTE_SCHEMA_ABSENT {row["schema"]} does not exist')
                continue
            text = schema_path.read_text(encoding='utf-8', errors='ignore')
            if version not in text:
                errors.append(f'{route}: ROUTE_VERSION_UNBOUND {schema_path.name} does not carry '
                              f'{version!r} -- the row binds a schema that does not bind it')
            else:
                try:
                    const = declared_version(json.loads(text))
                except ValueError:
                    const = None
                if const and const != version:
                    errors.append(f'{route}: ROUTE_VERSION_UNBOUND {schema_path.name} binds '
                                  f'{const!r}, not the {version!r} the row claims')
            target = repo / instance_path(emitter)
            if not target.is_file():
                errors.append(f'{route}: ROUTE_EMITTER_MISSING {emitter} does not exist')
            elif not version_literals(target, version):
                errors.append(f'{route}: ROUTE_EMITTER_MISSING {emitter} no longer carries '
                              f'{version!r} as a value it produces or compares -- one side '
                              'moved and the row rotted')
            notes.append(f'{route}: BOUND_SCHEMA {version} by {Path(instance_path(emitter)).name}')
        else:
            if not reason:
                errors.append(f'{route}: SCHEMA_LESS_WITHOUT_REASON -- a route with no schema '
                              'must say why nothing validates its payload')
            if version:
                holders = index.get(version) or []
                if not emitter:
                    errors.append(f'{route}: SCHEMA_LESS_DEBT_WITHOUT_EMITTER the payload '
                                  f'declares {version!r} but the row names no emitter, so the '
                                  'claim cannot be re-checked against the code that writes it')
                elif holders:
                    errors.append(f'{route}: SCHEMA_LESS_STALE {version} is declared by '
                                  f'{holders[0]} -- this row reports unpaid debt that has been paid')
                elif not any(phrase in reason.lower() for phrase in DEBT_PHRASES):
                    errors.append(f'{route}: SCHEMA_LESS_WITHOUT_REASON -- the payload declares '
                                  f'{version!r} but no schema exists; the reason must state that '
                                  'plainly instead of describing the route as unremarkable')
                else:
                    notes.append(f'{route}: SCHEMA_LESS debt {version}')
            else:
                notes.append(f'{route}: SCHEMA_LESS')
        # One defect, one line: the pointer is only asked when nothing else about this row failed.
        # If the emitter no longer writes the version at all, ROUTE_EMITTER_MISSING is the specific
        # finding, and a second red line for the same moved value would make the suite's "exactly
        # these errors" assertions meaningless -- which is how this check first went wrong.
        if emitter and version and len(errors) == row_checks_start:
            errors.extend(emitter_pointer_errors(repo, route, emitter, version))
    return errors, counted, notes


def run(repo: Path = REPO, ledger_path: Path | None = None) -> tuple[list[str], list[str], dict]:
    """Return (errors, notes, summary). Errors empty means the ledger is true."""
    repo = Path(repo)
    ledger_file = Path(ledger_path) if ledger_path else repo / LEDGER_REL
    errors: list[str] = []
    notes: list[str] = []

    files = sorted((repo / CONTRACT_DIR).glob('*.json'))
    if not files:
        return ([f'NOTHING_TO_COMPARE: no schema exists under {CONTRACT_DIR} -- the gate found '
                 'nothing to account for'], [], {'schemas': 0})
    if not ledger_file.is_file():
        return ([f'NOTHING_TO_COMPARE: {ledger_file.name} does not exist, so none of the '
                 f'{len(files)} declared contracts is accounted for'], [],
                {'schemas': len(files)})
    try:
        ledger = json.loads(ledger_file.read_text(encoding='utf-8'))
    except ValueError as exc:
        return ([f'NOTHING_TO_COMPARE: {ledger_file.name} is not readable JSON: {exc}'], [],
                {'schemas': len(files)})

    contract_rows = ledger.get('contracts') or []
    route_rows = ledger.get('routes') or []
    if not contract_rows:
        errors.append('NOTHING_TO_COMPARE: the ledger declares no contract rows at all')
    if not route_rows:
        errors.append('NOTHING_TO_COMPARE: the ledger declares no route rows at all')

    listed = [row.get('schema') for row in contract_rows]
    seen: set[str] = set()
    for rel in listed:
        if rel in seen:
            errors.append(f'DUPLICATE_SCHEMA_ROW {rel} is listed twice -- one row per schema')
        seen.add(rel)
    expected = {(repo / CONTRACT_DIR / p.name).relative_to(repo).as_posix() for p in files}
    for missing in sorted(expected - seen):
        errors.append(f'UNLISTED_SCHEMA {missing} exists on disk with no ledger row -- '
                      'a reader would assume it is enforced')
    for extra in sorted(seen - expected):
        errors.append(f'SCHEMA_ROW_ABSENT {extra} is listed but no longer on disk')

    row_errors, counts, row_notes = check_contract_rows(repo, contract_rows, seen - expected)
    errors.extend(row_errors)
    notes.extend(row_notes)

    http_path = repo / HTTP_REL
    if not http_path.is_file():
        errors.append(f'NOTHING_TO_COMPARE: {HTTP_REL} does not exist, so the boundary set '
                      'could not be read')
        return (errors, notes, {'schemas': len(files), 'binding': counts[BINDING],
                               'inert': counts[INERT], 'routes': 0, 'bound': 0})
    http_text = http_path.read_text(encoding='utf-8')
    try:
        tokens = route_tokens(http_path)
    except SyntaxError as exc:
        errors.append(f'NOTHING_TO_COMPARE: {HTTP_REL} does not parse: {exc}')
        tokens = []
    if not tokens:
        errors.append(f'NOTHING_TO_COMPARE: no route was found in {HTTP_REL} -- the boundary '
                      'ledger proved nothing')

    route_keys = [row.get('route') for row in route_rows]
    route_seen: set[str] = set()
    for key in route_keys:
        if key in route_seen:
            errors.append(f'DUPLICATE_ROUTE_ROW {key} is listed twice')
        route_seen.add(key)
    token_keys = {key for key, _ in tokens}
    for key in sorted(token_keys - route_seen):
        errors.append(f'UNLISTED_ROUTE {key} is dispatched by {HTTP_REL} but has no ledger row '
                      '-- a payload can cross the boundary unvalidated')
    for key in sorted(route_seen - token_keys):
        errors.append(f'ROUTE_ROW_ABSENT {key} is listed but {HTTP_REL} no longer dispatches it')

    index = schema_version_index(repo / SCHEMA_ROOT)
    route_errors, route_counts, route_notes = check_route_rows(repo, route_rows, http_text, index)
    errors.extend(route_errors)
    notes.extend(route_notes)

    if route_rows and route_counts[BOUND_SCHEMA] == 0:
        errors.append('NOTHING_TO_COMPARE: no route row is BOUND_SCHEMA -- a boundary ledger in '
                      'which nothing is actually validated proves nothing')

    # One ledger row can cover one path for two methods (/api/projects is GET+POST), so the
    # dispatched population is the distinct path set, not the table-entry count.
    summary = {'schemas': len(files), 'binding': counts[BINDING], 'inert': counts[INERT],
               'routes': len(route_rows), 'dispatched': len(token_keys),
               'bound': route_counts[BOUND_SCHEMA], 'schema_less': route_counts[SCHEMA_LESS]}
    return errors, notes, summary


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    repo = REPO
    if '--list-routes' in argv:
        for key, line in route_tokens(repo / HTTP_REL):
            print(f'{line:>4}  {key}')
        return 0
    errors, notes, summary = run(repo)
    for note in notes:
        print('  checked', note)
    for error in errors:
        print('ERROR:', error)
    # The verdict is the LAST line and starts with VERIFY_ on purpose:
    # design-lab/scripts/verify_design_lab.py scans its output from the end for a line starting
    # with VERIFY_ (or PASS/FAIL/EVIDENCE_) to summarise each gate, and a verdict printed first
    # among 80 detail lines shows up as no verdict at all.
    print(f'VERIFY_CONTRACT_BINDINGS={"FAIL" if errors else "PASS"} schemas={summary["schemas"]} '
          f'binding={summary["binding"]} inert={summary["inert"]} '
          f'routes={summary.get("routes", 0)} dispatched={summary.get("dispatched", 0)} '
          f'bound={summary.get("bound", 0)} schema_less={summary.get("schema_less", 0)}')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
