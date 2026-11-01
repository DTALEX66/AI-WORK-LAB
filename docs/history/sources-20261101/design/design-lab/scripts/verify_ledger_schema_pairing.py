#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Prove that every task ledger has a schema, and that it is the schema for its version.

The root cause this gate closes is a version string with no contract behind it: on
2026-09-09 the ledger moved from ``design-lab/task-ledger/r3-v1`` to
``design-lab/task-ledger/r5-v1`` and no r5-v1 schema file was ever written. The r3 schema
stayed in place, still correct for the r3 file it was written for -- the frozen predecessor
validates against it with zero errors -- while the live ledger lost its contract. Nothing
noticed, because nothing selected a schema by version: 105 schema errors reported against
the r3 file looked like ledger rot and were actually a missing pairing.

Four jobs, each a check and not a comment:

1. read the live ledger's own ``schemaVersion`` and resolve THAT to a schema file. An
   unresolvable version -- outside the table with no conventional file, or in the table but
   pointing at a file that has gone -- is a hard failure naming the exact path it looked for.
2. read the frozen r3 predecessor's own ``schemaVersion`` and resolve it too, so the
   predecessor keeps a job instead of being deleted as "stale" the next time somebody tidies
   ``design-lab/schemas/``.
3. check the pairing is honest: the selected schema's ``properties.schemaVersion.const`` must
   equal the version that selected it, and every ``task-ledger-*.schema.json`` on disk must
   be named by exactly one version. A file nobody selects is an unmaintained contract; a
   version nobody maps is this branch's defect.
4. make schema and data mutually accountable, the way this repo's other ledgers work (see
   ``verify_ledger_subject_binding.py``): a property present in the ledger and absent from the
   schema FAILS by path -- ``additionalProperties: false`` alone only says "not allowed", not
   which field -- and a property the schema declares that the live ledger never uses is
   reported: unsanctioned ones fail, and a sanction whose field the ledger has started using
   fails too, so the register cannot rot into a list of features nobody has.

What stays in Python because JSON Schema cannot say it: dependency acyclicity, the
task/receipt cross-references, equality of each task definition against the frozen taskpack,
and the derived ``required_axes``. That is ``src/design_lab/governance/r5_contract.py``, and
the schema says so in its own ``description`` instead of pretending with a weaker shape.

Read-only. No network. Deterministic given the two files.
"""
from __future__ import annotations

import json
import sys
from hashlib import sha256
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

REPO = Path(__file__).resolve().parents[2]
SCHEMA_DIR = REPO / 'design-lab' / 'schemas'
LEDGER = REPO / 'design-lab' / 'config' / 'task-ledger-r3.json'
PREDECESSOR = REPO / 'docs' / 'history' / 'taskpacks' / 'r3-ledger-pre-r5-20260909.json'

# version -> schema file. The r3 file keeps its historic name (no `-v1`) because its bytes
# are SHA-pinned inside six evidence records; renaming it would convict those receipts.
LEDGER_SCHEMAS = {
    'design-lab/task-ledger/r3-v1': 'task-ledger-r3.schema.json',
    'design-lab/task-ledger/r5-v1': 'task-ledger-r5-v1.schema.json',
}

# Schema path -> why the ledger of that version does not use it yet, and why the shape still
# belongs to the contract. Two-way: an entry here whose field the ledger has started using is
# a STALE sanction and fails, the same way a fixed KNOWN defect has to leave
# verify_ledger_subject_binding.py. Keyed by schemaVersion, so an excuse written for one
# version can never vouch for another.
DECLARED_BUT_UNUSED = {
    'design-lab/task-ledger/r5-v1': {
        '/tasks[]/condition_decisions':
            'r5_contract.py accepts a per-task case-condition decision map and AGENTS.md '
            'requires a case-selection record for conditional dependencies, so the shape '
            'belongs to the contract. The frozen R5 taskpack declares conditional_dependencies '
            'on exactly one task (DL-R5-019) and no owner decision has been recorded for it, so '
            'no task carries the key today. Delete this entry the moment one does.',
    },
}

# Schema path -> a field the ledger of that version really carries which its schema never
# declared. This is direction one of the accountability pair, recorded rather than ignored --
# and it only exists for r3-v1, whose task items were written without
# `additionalProperties: false`. Neither side of that pair can be repaired: the r3 schema's
# bytes are SHA-pinned inside six evidence records and the r3 ledger is frozen, so the honest
# move is a dated register that blocks a NEW undeclared field and convicts this one if it
# ever changes. The live r5 ledger has no entries here: every field it carries is declared.
UNDECLARED_IN_DATA = {
    'design-lab/task-ledger/r3-v1': {
        '/tasks[]/priority': 'Declared by the R3 taskpack source and read by the projections, '
                             'but task-ledger-r3.schema.json never listed it and closed its '
                             'task items with no additionalProperties: false. Frozen file, '
                             'SHA-pinned schema: recorded, not repaired.',
        '/tasks[]/environment': 'As /tasks[]/priority: present on all 24 frozen r3 tasks, '
                                'undeclared by the r3 schema, unfixable without editing bytes '
                                'six evidence records pin.',
        '/tasks[]/legacy_ids': 'As /tasks[]/priority: the R3 predecessor lineage the r3 schema '
                               'never declared; superseded in r5 by predecessor_task_ids, which '
                               'is declared.',
        '/tasks[]/baseline_existing': 'As /tasks[]/priority: a frozen r3 task field with no '
                                      'declaration behind it.',
        '/tasks[]/implementation': 'As /tasks[]/priority: the r3 planned-work list, undeclared '
                                   'by its schema; renamed to definition.implementation in r5.',
        '/tasks[]/deliverables': 'As /tasks[]/priority: the r3 delivery list, undeclared by its '
                                 'schema and dropped entirely in r5.',
        '/tasks[]/rollback': 'As /tasks[]/priority: the r3 rollback note, undeclared by its '
                             'schema; declared as definition.rollback in r5.',
    },
}

DELEGATED = 'x-contract-delegated'
MISSING_SCHEMA = 'NO_SCHEMA_FOR_VERSION'


class LedgerSchemaError(Exception):
    """A version that selects no schema file -- the defect this gate exists to catch."""


def load(path) -> dict:
    """Read one JSON document. A broken input is a stated defect, never a traceback and
    never a silent pass."""
    try:
        document = json.loads(Path(path).read_text(encoding='utf-8'))
    except FileNotFoundError as exc:
        raise LedgerSchemaError(f'missing_file: {path} is not there') from exc
    except (OSError, UnicodeDecodeError, ValueError) as exc:
        raise LedgerSchemaError(f'unreadable_json: {path}: {type(exc).__name__}: {exc}') from exc
    if not isinstance(document, dict):
        raise LedgerSchemaError(f'not_an_object: {path} parses to '
                                f'{type(document).__name__}, not a JSON object')
    return document


def schema_path_for(version, schema_dir: Path = SCHEMA_DIR) -> Path:
    """Resolve a ledger ``schemaVersion`` to the file that is its contract. Fail closed."""
    if not isinstance(version, str) or not version.strip():
        raise LedgerSchemaError(f'{MISSING_SCHEMA}: schemaVersion is absent or not a string '
                                f'({version!r}); no schema was selected')
    named = LEDGER_SCHEMAS.get(version)
    short = version.rsplit('/', 1)[-1] if '/' in version else version
    candidates = []
    if named:
        candidates.append(Path(schema_dir) / named)
    if short:
        # Conventional form, so a version added to a ledger without a table entry still finds
        # its own file -- and `pairing_errors` then reports the unmapped table entry.
        conventional = Path(schema_dir) / f'task-ledger-{short}.schema.json'
        if conventional not in candidates:
            candidates.append(conventional)
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    looked = ', '.join(f'design-lab/schemas/{c.name}' for c in candidates)
    raise LedgerSchemaError(f'{MISSING_SCHEMA}: schemaVersion {version!r} selects no schema '
                            f'file (looked for: {looked}); write the schema for this version or '
                            'stop shipping the version')


def declared_version(schema: dict):
    const = (schema.get('properties') or {}).get('schemaVersion', {}).get('const')
    return const if isinstance(const, str) else None


def pairing_errors(schema_dir: Path = SCHEMA_DIR) -> list[str]:
    """Every ledger schema on disk is selected by one known version, and vice versa."""
    errors: list[str] = []
    on_disk = {p.name for p in Path(schema_dir).glob('task-ledger-*.schema.json')}
    for orphan in sorted(on_disk - set(LEDGER_SCHEMAS.values())):
        errors.append(f'orphan_schema: design-lab/schemas/{orphan} is selected by no ledger '
                      'schemaVersion in LEDGER_SCHEMAS')
    for version, filename in sorted(LEDGER_SCHEMAS.items()):
        path = Path(schema_dir) / filename
        if not path.is_file():
            errors.append(f'missing_schema: {version} maps to design-lab/schemas/{filename}, '
                          'which does not exist')
            continue
        try:
            claims = declared_version(load(path))
        except LedgerSchemaError as exc:
            errors.append(f'unreadable_schema for {version}: {exc}')
            continue
        if claims != version:
            errors.append(f'version_mismatch: design-lab/schemas/{filename} declares '
                          f'schemaVersion const {claims!r}, not the {version!r} that selects it')
    return errors


def _pointer(root, ref: str):
    if not ref.startswith('#/'):
        raise LedgerSchemaError(f'unsupported $ref {ref!r}: a ledger schema may only point inside '
                                'its own document, so one file stays the whole contract')
    node = root
    for part in ref[2:].split('/'):
        part = part.replace('~1', '/').replace('~0', '~')
        if not isinstance(node, dict) or part not in node:
            raise LedgerSchemaError(f'broken $ref {ref!r}: no such pointer in the schema')
        node = node[part]
    return node


def resolve(node, root, depth=0):
    """Inline local $refs so one walk of the schema can match one walk of the data."""
    if depth > 64:
        raise LedgerSchemaError('recursive $ref in ledger schema')
    if isinstance(node, dict):
        ref = node.get('$ref')
        if isinstance(ref, str):
            merged = dict(resolve(_pointer(root, ref), root, depth + 1))
            for key, value in node.items():
                if key != '$ref':
                    merged[key] = resolve(value, root, depth + 1)
            return merged
        return {key: resolve(value, root, depth + 1) for key, value in node.items()}
    if isinstance(node, list):
        return [resolve(value, root, depth + 1) for value in node]
    return node


def declared_paths(resolved):
    """Named property paths the schema describes, plus the wildcard paths it leaves open."""
    named: set[str] = set()
    wildcards: set[str] = set()

    def walk(node, path):
        if not isinstance(node, dict) or DELEGATED in node:
            return
        for key, sub in (node.get('properties') or {}).items():
            named.add(f'{path}/{key}')
            walk(sub, f'{path}/{key}')
        extra = node.get('additionalProperties')
        if isinstance(extra, dict):
            wildcards.add(f'{path}/*')
            walk(extra, f'{path}/*')
        items = node.get('items')
        if isinstance(items, dict):
            walk(items, f'{path}[]')
        for branch in ('allOf', 'anyOf', 'oneOf'):
            for sub in node.get(branch) or []:
                walk(sub, path)

    walk(resolved, '')
    return named, wildcards


def observed_paths(data, resolved):
    """Named property paths the data actually carries.

    A key the schema leaves open (``additionalProperties`` as a schema) is recorded as the
    wildcard rather than as a property name: an interpreter version is not an undeclared field.
    """
    found: set[str] = set()

    def walk(value, node, path):
        if isinstance(value, dict):
            node = node if isinstance(node, dict) else {}
            properties = node.get('properties') or {}
            extra = node.get('additionalProperties')
            for key, child in value.items():
                if key in properties:
                    target = f'{path}/{key}'
                    found.add(target)
                    if DELEGATED not in (properties[key] or {}):
                        walk(child, properties[key], target)
                elif isinstance(extra, dict):
                    found.add(f'{path}/*')
                    if DELEGATED not in extra:
                        walk(child, extra, f'{path}/*')
                else:
                    found.add(f'{path}/{key}')
        elif isinstance(value, list):
            items = node.get('items') if isinstance(node, dict) else None
            if isinstance(items, dict):
                for element in value:
                    walk(element, items, f'{path}[]')

    walk(data, resolved, '')
    return found


def drift(schema, data):
    """(fields the data has and the schema does not, fields the schema has and the data does not)."""
    named, wildcards, observed = path_sets(schema, data)
    return sorted(observed - named - wildcards), sorted(named - observed)


def path_sets(schema, data):
    resolved = resolve(schema, schema)
    named, wildcards = declared_paths(resolved)
    return named, wildcards, observed_paths(data, resolved)


def prune_nested(paths):
    """Keep only the top of each affected subtree.

    If `/tasks[]/condition_decisions` is unused, its two child paths are unused too; listing
    all three would read as three defects when the schema author has one field to fix.
    """
    kept = []
    for path in sorted(paths, key=lambda p: (p.count('/'), p)):
        if any(path == parent or path.startswith(parent + '/') or path.startswith(parent + '[]')
               or path.startswith(parent + '/*') for parent in kept):
            continue
        kept.append(path)
    return sorted(kept)


def register_for(registers, version):
    """A sanction list is only valid for the version it names, so an excuse written for a
    version nobody runs cannot linger as cover for a different ledger."""
    unknown = sorted(set(registers) - set(LEDGER_SCHEMAS))
    return (registers.get(version) or {}), unknown


def partition(unused, undeclared, register_unused, register_undeclared):
    """Both directions, two ways each: an unsanctioned defect fails, a stale excuse fails."""
    unsanctioned_unused = sorted(path for path in unused if path not in register_unused)
    stale_unused = sorted(path for path in register_unused if path not in unused)
    unsanctioned_undeclared = sorted(path for path in undeclared if path not in register_undeclared)
    stale_undeclared = sorted(path for path in register_undeclared if path not in undeclared)
    return (unsanctioned_unused, stale_unused, unsanctioned_undeclared, stale_undeclared)


def validate_against(schema, data):
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = sorted(validator.iter_errors(data), key=lambda e: '/'.join(map(str, e.path)))
    return ['%s (at /%s)' % (e.message, '/'.join(map(str, e.path))) for e in errors[:8]]


def check_pair(label, data, schema, schema_name) -> tuple[list[str], dict]:
    errors = validate_against(schema, data)
    named, wildcards, observed = path_sets(schema, data)
    undeclared = prune_nested(sorted(observed - named - wildcards))
    unused = prune_nested(sorted(named - observed))
    version = declared_version(schema)
    register_unused, unknown_unused = register_for(DECLARED_BUT_UNUSED, version)
    register_undeclared, unknown_undeclared = register_for(UNDECLARED_IN_DATA, version)
    messages = [f'{label} :: unmapped_sanction {name} excuses a version that selects no schema'
                for name in sorted(set(unknown_unused) | set(unknown_undeclared))]
    unsanctioned_unused, stale_unused, unsanctioned_undeclared, stale_undeclared = partition(
        unused, undeclared, register_unused, register_undeclared)
    messages += [f'{label} :: {schema_name} :: {message}' for message in errors]
    messages += [f'{label} :: undeclared_field {path} is in the ledger but declared by no schema, '
                 'and no dated register admits it' for path in unsanctioned_undeclared]
    messages += [f'{label} :: stale_register {path} is excused as undeclared, but the ledger no '
                 'longer carries it; delete the excuse' for path in stale_undeclared]
    messages += [f'{label} :: unused_declaration {path} is declared by the schema but the ledger '
                 'never uses it, and no register explains why' for path in unsanctioned_unused]
    messages += [f'{label} :: stale_sanction {path} was registered as declared-but-unused, but '
                 'the ledger uses it now; delete the excuse' for path in stale_unused]
    stats = {'label': label, 'schema': schema_name, 'version': version,
             'schema_errors': len(errors), 'undeclared': len(unsanctioned_undeclared),
             'unused': len(unsanctioned_unused),
             'sanctioned_undeclared': len(register_undeclared) - len(stale_undeclared),
             'sanctioned_unused': len(register_unused) - len(stale_unused),
             'declared_paths': len(named), 'observed_paths': len(observed & named)}
    return messages, stats


def run(ledger_path=LEDGER, predecessor_path=PREDECESSOR, schema_dir=SCHEMA_DIR) -> dict:
    """Every defect found, plus the counts that make an OK line mean something."""
    try:
        return _run(ledger_path, predecessor_path, schema_dir)
    except LedgerSchemaError as exc:
        return {'failures': [str(exc)], 'stats': [], 'records': {}}


def _run(ledger_path, predecessor_path, schema_dir) -> dict:
    failures: list[str] = list(pairing_errors(schema_dir))
    stats: list[dict] = []
    records = {}
    ledger = load(ledger_path)
    version = ledger.get('schemaVersion')
    try:
        path = schema_path_for(version, schema_dir)
    except LedgerSchemaError as exc:
        failures.append(str(exc))
        return {'failures': failures, 'stats': stats, 'records': records}
    schema = load(path)
    messages, one = check_pair('live ledger', ledger, schema, path.name)
    failures += messages
    stats.append(one)

    predecessor = load(predecessor_path)
    try:
        pre_path = schema_path_for(predecessor.get('schemaVersion'), schema_dir)
        messages, two = check_pair('frozen r3 predecessor', predecessor, load(pre_path),
                                   pre_path.name)
        failures += messages
        stats.append(two)
    except LedgerSchemaError as exc:
        failures.append(f'frozen r3 predecessor :: {exc}')

    digest = sha256(Path(predecessor_path).read_bytes()).hexdigest()
    carried = (ledger.get('predecessor') or {}).get('sha256')
    if carried != digest:
        failures.append(f'predecessor_sha256: the ledger carries {carried!r} while '
                        f'{Path(predecessor_path).name} hashes to {digest}')
    if (ledger.get('predecessor') or {}).get('ledger') != predecessor:
        failures.append('predecessor_ledger: the inline copy in the live ledger is not '
                        'deep-equal to the frozen r3 file it claims to be')

    records = {'ledger_schema': path.name,
               'evidence_records': len(ledger.get('evidence') or []),
               'tasks': len(ledger.get('tasks') or []),
               'sanctioned_unused': sum(item['sanctioned_unused'] for item in stats),
               'sanctioned_undeclared': sum(item['sanctioned_undeclared'] for item in stats),
               'declared_paths': sum(item['declared_paths'] for item in stats),
               'observed_paths': sum(item['observed_paths'] for item in stats)}
    return {'failures': failures, 'stats': stats, 'records': records}


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    targets = {'ledger': LEDGER, 'predecessor': PREDECESSOR}
    index = 0
    while index < len(argv):
        flag = argv[index]
        if flag not in ('--ledger', '--predecessor') or index + 1 >= len(argv):
            print('LEDGER_SCHEMA_PAIRING=FAIL usage: [--ledger PATH] [--predecessor PATH]')
            return 2
        targets[flag[2:]] = Path(argv[index + 1])
        index += 2
    result = run(targets['ledger'], targets['predecessor'])
    for failure in result['failures']:
        print('  DEFECT', failure)
    for item in result['stats']:
        print(f"  pair {item['label']}: {item['schema']} schema_errors={item['schema_errors']} "
              f"undeclared={item['undeclared']} unused={item['unused']} "
              f"registered_undeclared={item['sanctioned_undeclared']} "
              f"registered_unused={item['sanctioned_unused']} "
              f"declared_paths={item['declared_paths']} observed_paths={item['observed_paths']}")
    records = result['records']
    ok = not result['failures']
    print(f"VERIFY_LEDGER_SCHEMA_PAIRING={'OK' if ok else 'FAIL'} "
          f"pairs={len(result['stats'])} schema={records.get('ledger_schema', 'UNRESOLVED')} "
          f"tasks={records.get('tasks', 0)} evidence_records={records.get('evidence_records', 0)} "
          f"registered_undeclared={records.get('sanctioned_undeclared', 0)} "
          f"registered_unused={records.get('sanctioned_unused', 0)} "
          f"defects={len(result['failures'])}")
    return 0 if ok else 1


if __name__ == '__main__':
    raise SystemExit(main())
