#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""TEMPLATE_CONTRACTS: every fill-in template must name a contract that its own bytes satisfy.

Measured on 2026-10-08 against HEAD c0d44f00, all three ``*.template.json`` files in this repository
were broken, in three different ways, and nothing in the gate chain could see any of it:

* ``design-lab/production/handoff/BOM.template.json`` pointed at ``schemas/bom.schema.json`` and
  failed it three times over -- a ``$schema`` key the schema's ``additionalProperties: false``
  forbids, an ``items[0].kind`` placeholder that is not one of the three allowed values, and a
  ``version`` of ``1.0.0`` where the contract pins a const;
* ``packages/capabilities/quality/jury/JuryRecord.template.json`` pointed at
  ``../../../schemas/jury-record.schema.json``, which resolves to ``packages/schemas/`` -- a path
  that has no file in it. The pointer itself was a lie, so the template documented a shape no
  reader could reach;
* ``design-lab/evals/templates/score-sheet.template.json`` named no schema at all, only a rubric.

A template is the shape a person copies to produce a real record. If the copy is already invalid,
then the honest workflow ("fill in the blanks, submit") ships a rejected document every time, and
the enum the template was supposed to teach is only discoverable by a validator nobody ran. So this
gate checks the pointer, the path, and the instance.

Rules, all of them falsifiable and all of them gated on a claim that is now false rather than on a
count that merely moved:

1. TEMPLATE_NOT_JSON / TEMPLATE_NOT_OBJECT -- the file cannot be read as the document it is.
2. NO_CONTRACT_POINTER -- it declares no ``$schema`` and no ``rubric``, so nothing can check it.
3. POINTER_UNRESOLVED -- a declared pointer names a path with no file in the repository.
4. POINTER_OUTSIDE_REPO -- a pointer that escapes the checkout (an absolute path or ``..`` past the
   root), because a template must be fillable from the repository alone.
5. SCHEMA_UNLOADABLE -- the named schema is missing, malformed, or not draft 2020-12.
6. TEMPLATE_INVALID -- the template's own bytes are rejected by the schema it claims. Validation
   uses one offline registry built from the in-repo ``$id`` values, so a ``$ref`` between schemas
   resolves from the checkout instead of reaching for the network.
7. RUBRIC_AXES_MISMATCH / RUBRIC_HAS_NO_AXES -- the sheet bills dimensions the rubric it names does
   not define, or names a rubric that defines none.
8. SCHEMA_REF_UNRESOLVABLE -- the schema reaches for a ``$ref`` that no in-repo ``$id`` answers. This
   is reported, not raised: jsonschema tries the network for such a reference, and a gate that dies
   on a malformed contract looks identical to a gate that found nothing.
9. NOTHING SCANNED IS A FAILURE -- zero templates found is red, not green.
10. INVENTORY_MOVED -- the set of templates is pinned below; adding or deleting one is a decision
   this file has to record, not an accident a run absorbs silently.

Rule 6 forced a decision about what a placeholder may say. A closed enum leaves no room for a
"replace-me" token, so every template now carries a legal value, and the value chosen is the one
that cannot overclaim: the jury template scores each axis at the minimum 1 rather than 0 (which the
schema forbids) and records ``deterministic.result`` as ``FAIL`` rather than the ``OK`` it used to
carry -- a template that pre-fills a passing automated check is a false green handed to whoever
copies it, which is the exact failure this repository is built to refuse. Free-text fields keep
their ``replace-with-`` wording so the unfilled state stays visible.

Run: python design-lab/scripts/verify_template_contracts.py [--json]
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / 'design-lab' / 'schemas'
SCOPES = ('design-lab', 'packages', 'fixtures', 'src', 'apps', 'docs')
EXCLUDED = {'__pycache__', 'node_modules', 'build', 'dist', '.project-local'}
SUFFIX = '.template.json'
SCHEMA_POINTER = '$schema'
RUBRIC_POINTER = 'rubric'

#: The templates that exist, dated 2026-10-08 against HEAD c0d44f00. A row is removed only when the
#: template is deleted; a new template has to be added here by whoever introduces it, because an
#: unchecked copy is how an invalid record gets produced at scale.
INVENTORY = (
    'design-lab/evals/templates/score-sheet.template.json',
    'design-lab/production/handoff/BOM.template.json',
    'packages/capabilities/quality/jury/JuryRecord.template.json',
)


def _interop():
    src = REPO / 'src'
    if str(src) not in sys.path:
        sys.path.insert(0, str(src))
    from design_lab.interop import InteropError, load_schema, resource_registry, schema_errors
    return InteropError, load_schema, resource_registry, schema_errors


def templates(root: Path) -> list[Path]:
    found: list[Path] = []
    for scope in SCOPES:
        base = root / scope
        if not base.is_dir():
            continue
        for path in base.rglob(f'*{SUFFIX}'):
            if EXCLUDED & set(path.relative_to(root).parts):
                continue
            found.append(path)
    return sorted(found, key=lambda p: p.relative_to(root).as_posix())


def _registry(root: Path):
    """One offline ``referencing`` registry from every in-repo schema that declares an ``$id``."""
    _, _, resource_registry, _ = _interop()
    pairs = {}
    for path in sorted((root / 'design-lab' / 'schemas').rglob('*.json')):
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(document, dict) and isinstance(document.get('$id'), str):
            pairs[document['$id']] = document
    return resource_registry(pairs), len(pairs)


def _pointer_target(path: Path, value: str, root: Path) -> tuple[Path | None, str | None]:
    """Resolve a template's pointer, refusing anything that leaves the checkout.

    Two conventions are in use in this repository and both are honoured: ``$schema`` is written
    relative to the file that carries it, the score sheet's ``rubric`` relative to the repository
    root. A pointer is a lie only when neither reading finds a file, so both candidates are named
    in the failure.
    """
    if '://' in value:
        return None, ('POINTER_OUTSIDE_REPO: a remote URL -- the contract has to be readable from '
                      'the checkout, and a validator that reaches for the network is not offline')
    base = root.resolve()
    candidates = [(path.parent / value).resolve(), (base / value).resolve()]
    for candidate in candidates:
        if _inside(candidate, base) and candidate.is_file():
            return candidate, None
    inside = [candidate for candidate in candidates if _inside(candidate, base)]
    if not inside:
        return None, (f'POINTER_OUTSIDE_REPO: {value} resolves to {candidates[0]}, which is not '
                      'inside the repository, and the repository-root reading is the same path')
    named = ', '.join(candidate.relative_to(base).as_posix() for candidate in inside)
    return None, f'POINTER_UNRESOLVED: {value} resolves to no file in the checkout (tried {named})'


def _inside(candidate: Path, base: Path) -> bool:
    try:
        candidate.relative_to(base)
    except ValueError:
        return False
    return True


def audit(root: Path = REPO, inventory: tuple[str, ...] = INVENTORY) -> dict:
    interop_error, load_schema, _, schema_errors = _interop()
    registry, ids_loaded = _registry(root)
    rows, errors = [], []

    found = templates(root)
    names = [path.relative_to(root).as_posix() for path in found]
    if not found:
        errors.append(f'NOTHING_SCANNED: no *{SUFFIX} found under {", ".join(SCOPES)} '
                      '-- an empty scan is not a pass')
    for expected in inventory:
        if expected not in names:
            errors.append(f'INVENTORY_MOVED: {expected} is pinned here but no longer exists')
    for name in names:
        if name not in inventory:
            errors.append(f'INVENTORY_MOVED: {name} is not pinned in this gate')

    for path in found:
        rel = path.relative_to(root).as_posix()
        row = {'template': rel, 'declared': [], 'pointers': {}, 'state': 'OK', 'problems': []}
        try:
            document = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, json.JSONDecodeError) as exc:
            row['state'] = 'BROKEN'
            row['problems'].append(f'TEMPLATE_NOT_JSON: {exc}')
            rows.append(row)
            errors.append(f'{rel}: TEMPLATE_NOT_JSON: {exc}')
            continue
        if not isinstance(document, dict):
            row['state'] = 'BROKEN'
            row['problems'].append('TEMPLATE_NOT_OBJECT: the document is not an object')
            rows.append(row)
            errors.append(f'{rel}: TEMPLATE_NOT_OBJECT: the document is a '
                          f'{type(document).__name__}, not an object')
            continue

        declared = [key for key in (SCHEMA_POINTER, RUBRIC_POINTER) if key in document]
        row['declared'] = declared
        if not declared:
            problem = (f'NO_CONTRACT_POINTER: names neither {SCHEMA_POINTER} nor {RUBRIC_POINTER}, '
                       'so the shape it teaches cannot be checked against anything')
            row['state'] = 'UNDECLARED'
            row['problems'].append(problem)
            errors.append(f'{rel}: {problem}')
            rows.append(row)
            continue

        for key in declared:
            value = document[key]
            target, why = _pointer_target(path, value if isinstance(value, str) else '', root)
            if not isinstance(value, str) or not value.strip():
                errors.append(f'{rel}: {key} is not a non-empty string')
                row['problems'].append(f'{key}: not a usable pointer')
                continue
            if target is None:
                problem = why
                row['state'] = 'BROKEN'
                row['problems'].append(f'{key}: {problem}')
                errors.append(f'{rel}: {problem}')
                continue
            row['pointers'][key] = target.relative_to(root).as_posix()

            if key == SCHEMA_POINTER:
                try:
                    schema = load_schema(target)
                except interop_error as exc:
                    problem = f'SCHEMA_UNLOADABLE: {exc}'
                    row['state'] = 'BROKEN'
                    row['problems'].append(problem)
                    errors.append(f'{rel}: {problem}')
                    continue
                try:
                    reported = schema_errors(schema, document, registry=registry, limit=10)
                except interop_error as exc:
                    # A $ref that names no in-repo $id cannot be resolved offline, and jsonschema
                    # answers that with an exception rather than a finding. Crashing here would leave
                    # a malformed contract reported as a broken gate, so it is a finding instead.
                    problem = f'SCHEMA_REF_UNRESOLVABLE: {exc}'
                    row['state'] = 'BROKEN'
                    row['problems'].append(problem)
                    errors.append(f'{rel}: {problem}')
                    continue
                problems = [f'TEMPLATE_INVALID: {error}' for error in reported]
                if problems:
                    row['state'] = 'INVALID'
                    row['problems'].extend(problems)
                    errors.extend(f'{rel}: {problem}' for problem in problems)
                else:
                    row['schema_required'] = len(schema.get('required') or [])
                continue

            try:
                rubric = json.loads(target.read_text(encoding='utf-8'))
            except (OSError, json.JSONDecodeError) as exc:
                problem = f'RUBRIC_UNREADABLE: {exc}'
                row['state'] = 'BROKEN'
                row['problems'].append(problem)
                errors.append(f'{rel}: {problem}')
                continue
            axes = [str(axis.get('id')) for axis in (rubric.get('axes') or [])
                    if isinstance(axis, dict) and axis.get('id')]
            if not axes:
                problem = (f'RUBRIC_HAS_NO_AXES: {row["pointers"][key]} declares no axes with an id, '
                           'so the sheet cannot bill anything against it')
                row['state'] = 'BROKEN'
                row['problems'].append(problem)
                errors.append(f'{rel}: {problem}')
                continue
            scores = document.get('scores')
            if not isinstance(scores, dict):
                problem = 'RUBRIC_AXES_MISMATCH: the template declares a rubric but has no scores object'
                row['state'] = 'BROKEN'
                row['problems'].append(problem)
                errors.append(f'{rel}: {problem}')
                continue
            billed, defined = set(scores), set(axes)
            if billed != defined:
                problem = ('RUBRIC_AXES_MISMATCH: billed by the sheet but not in the rubric -- '
                           + (', '.join(sorted(billed - defined)) or 'none')
                           + '; in the rubric but not billed -- '
                           + (', '.join(sorted(defined - billed)) or 'none'))
                row['state'] = 'INVALID'
                row['problems'].append(problem)
                errors.append(f'{rel}: {problem}')
            else:
                row['axes'] = len(axes)
        rows.append(row)

    return {'rows': rows, 'errors': errors, 'templates': len(rows),
            'schemas_with_id': ids_loaded, 'inventory': list(inventory)}


def main(argv: list[str]) -> int:
    root = REPO
    result = audit(root)
    if '--json' in argv:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return 1 if result['errors'] else 0
    checked = sum(1 for row in result['rows'] if not row['problems'])
    print(f'TEMPLATE_CONTRACTS={"FAIL" if result["errors"] else "OK"} '
          f'templates={result["templates"]} clean={checked} '
          f'schemas_with_id={result["schemas_with_id"]}')
    for row in result['rows']:
        detail = []
        if 'schema_required' in row:
            detail.append(f'schema requires {row["schema_required"]} fields')
        if 'axes' in row:
            detail.append(f'{row["axes"]} rubric axes billed')
        resolved = ', '.join(f'{key}->{value}' for key, value in sorted(row['pointers'].items()))
        print(f'  {row["state"]:10} {row["template"]}'
              + (f'  declares {", ".join(row["declared"])}' if row['declared'] else '  declares nothing'))
        if resolved:
            print(f'               {resolved}' + (f'  |  {"; ".join(detail)}' if detail else ''))
        for problem in row['problems']:
            print(f'      {problem}')
    for error in result['errors']:
        print(f'ERROR {error}')
    if result['errors']:
        print(f'TEMPLATE_CONTRACTS=FAIL defects={len(result["errors"])}')
        return 1
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
