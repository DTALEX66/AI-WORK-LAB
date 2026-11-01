#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-PREFLIGHT-CONTRACT: an emitted payload must satisfy the schema it claims.

Why this gate exists. A 2026-10-08 audit reported that `assurance/production_preflight.py`
returns `verdict` while `schemas/preflight.schema.json` requires `status`. Checked against
the files, that claim is false in both halves: `status` is not in that schema's top-level
`required` list at all (it exists only under the optional `result` object), and the schema
is bound to the PROFILE documents, which it identifies by `const schemaVersion
design-lab/preflight/v2` and by requiring `preflight_id` + `required_checks` -- fields the
artifact report has no business declaring. The artifact report carries its own version,
`design-lab/artifact-preflight/v1`, and until this gate existed NOTHING anywhere validated
it: the only contract surface for that payload was a TypeScript interface in shell.ts and a
regex test over the page's source. An unvalidated payload is how a drift returns silently,
so the payload now has a schema (schemas/artifact-preflight.schema.json) and this checker.

What it enforces, per binding:

1. the schema is a valid draft 2020-12 schema;
2. a REAL payload, produced by calling the emitter on real bytes in a temporary directory,
   validates against it;
3. BOTH directions of field disagreement are red: a field the schema `required` that the
   emitter did not produce (MISSING_FROM_EMITTER) and a field the emitter produced that a
   closed schema does not declare (UNDECLARED_BY_SCHEMA, the `additionalProperties: false`
   case). Nested object locations are compared too, because the fields the page actually
   renders (`findings[].criterion`, `findings[].outcome`, `counts.NOT_MEASURED`) live there;
4. the `schemaVersion` literal in the emitter source equals the `const` in the schema, so a
   version bump on one side alone is a finding rather than an orphaned document;
5. NOTHING TO COMPARE IS A FAILURE. Zero payloads, zero object locations reached, zero
   required fields seen, or a binding whose files are missing are all red. A gate that
   matched no case must not report a pass.

Usage:
    python design-lab/scripts/verify_artifact_preflight_contract.py
Exit 0 when every binding holds, 1 otherwise.
"""
from __future__ import annotations

import hashlib
import io
import json
import shutil
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / 'src'
SCHEMA_DIR = REPO / 'design-lab' / 'schemas'

# concept -> the emitter that produces it and the schema that binds it.
# Adding a row here is how the next unschema'd payload gets caught; a row that points at
# absent files is red, so a placeholder cannot pass as coverage.
BINDINGS = [
    {
        'name': 'artifact-preflight',
        'schema': SCHEMA_DIR / 'artifact-preflight.schema.json',
        'emitter': SRC / 'design_lab' / 'assurance' / 'production_preflight.py',
        'cases': ('run_preflight(digital)', 'preflight_archive(print)'),
    },
]


def load_module(path: Path):
    """Import an emitter module from its real path (used for the payload producers).

    A weakened COPY of the emitter loaded from a scratch directory must still read the
    shipped profiles, otherwise the falsification would be testing a mutated input rather
    than a mutated emitter: PROFILE_DIR is derived from __file__, so it is re-pointed at
    the real profile directory when the copy's own path has none.
    """
    if str(SRC) not in sys.path:
        sys.path.insert(0, str(SRC))
    import importlib.util
    spec = importlib.util.spec_from_file_location(path.stem + '_under_gate', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    shipped = REPO / 'design-lab' / 'production' / 'profiles'
    if getattr(module, 'PROFILE_DIR', None) is not None and not Path(module.PROFILE_DIR).is_dir():
        module.PROFILE_DIR = shipped
    return module


def as_sent_on_the_wire(payload):
    """The payload the route writes: `json.dumps` of the emitter's dict.

    The consumer is an HTTP response, so the contract is over the serialised form, not over
    Python-only types (the emitter's `dpi` is a tuple in-process and an array on the wire).
    A value that cannot serialise is a real defect in a product path, so this raises rather
    than papering over it with a `default=`.
    """
    return json.loads(json.dumps(payload, ensure_ascii=False))


def build_real_payloads(emitter_path=None):
    """Ask the product to preflight real bytes; return [(label, payload)].

    The payloads are never assembled by this script. If the emitter's shape changes, what
    lands in the comparison is the changed shape -- that is the whole point.
    """
    from PIL import Image
    module = load_module(emitter_path or BINDINGS[0]['emitter'])
    scratch = Path(tempfile.mkdtemp(prefix='preflight-contract-',
                                    dir=str(REPO / '.project-local' / 'task-runtime')))
    cases = []
    try:
        def png(name, *, mode='RGB', dpi=None):
            stream = io.BytesIO()
            Image.new(mode, (180, 120), 'red' if mode == 'RGB' else 128).save(
                stream, format='PNG', **({'dpi': dpi} if dpi else {}))
            path = scratch / name
            path.write_bytes(stream.getvalue())
            return path

        image = png('poster.png', dpi=(300, 300))
        cases.append(('run_preflight(digital)',
                      as_sent_on_the_wire(module.run_preflight([image], profile='digital'))))

        # The archive entry is the one the HTTP route actually serves, and it is the only
        # one that adds the `archive` field, so it has to be a case of its own.
        logo = png('logo.png', mode='RGBA')
        manifest = {'files': {'logo.png': {'sha256': hashlib.sha256(logo.read_bytes()).hexdigest()}}}
        archive = scratch / 'delivery.zip'
        with zipfile.ZipFile(archive, 'w') as out:
            out.writestr('logo.png', logo.read_bytes())
            out.writestr('bundle-manifest.json', json.dumps(manifest))
        digest = hashlib.sha256(archive.read_bytes()).hexdigest()
        cases.append(('preflight_archive(print)',
                      as_sent_on_the_wire(module.preflight_archive(
                          archive, profile='print', expected_sha256=digest))))
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    return cases


def comparisons(schema, instance, path='$', out=None):
    """Pair every object location in the instance with the schema node that binds it.

    Returns one record per (location where the schema declares `properties` and the
    instance is a mapping): the required set, the declared set, and the produced set.
    """
    out = [] if out is None else out
    if not isinstance(schema, dict):
        return out
    if isinstance(instance, dict) and isinstance(schema.get('properties'), dict):
        props = schema['properties']
        out.append({
            'path': path,
            'required': set(schema.get('required') or []),
            'declared': set(props),
            'produced': set(instance),
            'closed': schema.get('additionalProperties') is False,
        })
        for key, subschema in props.items():
            if key in instance:
                comparisons(subschema, instance[key], f'{path}.{key}', out)
    if isinstance(instance, list) and isinstance(schema.get('items'), dict):
        for index, item in enumerate(instance):
            comparisons(schema['items'], item, f'{path}[{index}]', out)
    return out


def drift_errors(name, schema, payload, case_label):
    """Field-set disagreement in either direction, named so a fixer can act on it."""
    errors = []
    for node in comparisons(schema, payload):
        missing = sorted(node['required'] - node['produced'])
        if missing:
            errors.append(f'{name}/{case_label}@{node["path"]}: MISSING_FROM_EMITTER '
                          f'{missing} -- the schema requires fields the emitter does not produce')
        if node['closed']:
            extra = sorted(node['produced'] - node['declared'])
            if extra:
                errors.append(f'{name}/{case_label}@{node["path"]}: UNDECLARED_BY_SCHEMA '
                              f'{extra} -- the emitter produces fields a closed schema forbids')
    return errors


def version_errors(name, schema, emitter_text):
    """The emitter's own schemaVersion literal and the schema's const must be one version."""
    declared = (schema.get('properties') or {}).get('schemaVersion', {}).get('const')
    if not declared:
        return [f'{name}: the schema declares no `const` for schemaVersion, so the payload '
                'cannot be tied to a version'], None
    occurrences = emitter_text.count(f"'{declared}'") + emitter_text.count(f'"{declared}"')
    if occurrences == 0:
        return [f'{name}: the schema binds {declared!r} but the emitter source never produces '
                'that literal -- one side moved and the other did not'], 0
    return [], occurrences


def schema_field_count(schema):
    return len(((schema.get('properties') or {})))


def check_binding(binding, cases=None, schema_doc=None, emitter_text=None):
    """Run every check for one binding; return (errors, notes).

    `schema_doc` / `cases` / `emitter_text` are injectable so the teeth of this gate can be
    falsified against a weakened COPY without touching the shipped files.
    """
    import jsonschema
    errors, notes = [], []
    schema_path, emitter_path = binding['schema'], binding['emitter']
    if not schema_path.is_file():
        return [f'{binding["name"]}: schema {schema_path} does not exist'], notes
    if not emitter_path.is_file():
        return [f'{binding["name"]}: emitter {emitter_path} does not exist'], notes
    schema = schema_doc if schema_doc is not None else json.loads(schema_path.read_text(encoding='utf-8'))
    if emitter_text is None:
        emitter_text = emitter_path.read_text(encoding='utf-8')
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        return [f'{binding["name"]}: schema is not a valid draft 2020-12 schema: {exc.message}'], notes

    if cases is None:
        cases = build_real_payloads(emitter_path)
    cases = list(cases)
    if not cases:
        return [f'{binding["name"]}: NOTHING_TO_COMPARE -- no payload was produced, '
                'so this binding proves nothing'], notes
    version, count = version_errors(binding['name'], schema, emitter_text)
    errors.extend(version)
    if count == 0:
        errors.append(f'{binding["name"]}: NOTHING_TO_COMPARE -- the version literal was not '
                      'matched in the emitter source')

    compared_nodes = 0
    for label, payload in cases:
        if not isinstance(payload, dict) or not payload:
            errors.append(f'{binding["name"]}/{label}: NOTHING_TO_COMPARE -- the emitter '
                          'returned no mapping to check')
            continue
        nodes = comparisons(schema, payload)
        if not nodes:
            errors.append(f'{binding["name"]}/{label}: NOTHING_TO_COMPARE -- the schema '
                          'declares no bound object location for this payload')
            continue
        compared_nodes += len(nodes)
        if not any(node['required'] for node in nodes):
            errors.append(f'{binding["name"]}/{label}: NOTHING_TO_COMPARE -- no schema node '
                          'requires anything, so a wrong payload would sail through')
        validator = jsonschema.Draft202012Validator(schema)
        for error in sorted(validator.iter_errors(payload), key=lambda e: list(e.absolute_path)):
            spot = '/'.join(str(part) for part in error.absolute_path) or '<root>'
            errors.append(f'{binding["name"]}/{label}@{spot}: SCHEMA_VIOLATION {error.message}')
        errors.extend(drift_errors(binding['name'], schema, payload, label))
    notes.append(f'{binding["name"]}: cases={len(cases)} object locations compared='
                 f'{compared_nodes} schema fields={schema_field_count(schema)}')
    return errors, notes


def run(bindings=None):
    errors, notes = [], []
    effective = BINDINGS if bindings is None else list(bindings)
    if not effective:
        # A gate with no binding cannot fail to find a drift, which is exactly a pass
        # invented out of nothing.
        return ['NOTHING_TO_COMPARE: no emitter/schema binding is declared at all'], notes
    for binding in effective:
        case_errors, case_notes = check_binding(binding)
        errors.extend(case_errors)
        notes.extend(case_notes)
    return errors, notes


def main(argv=None) -> int:
    errors, notes = run()
    print(f'ARTIFACT_PREFLIGHT_CONTRACT={"FAIL" if errors else "PASS"} '
          f'bindings={len(BINDINGS)}')
    for note in notes:
        print('  compared', note)
    for error in errors:
        print('ERROR:', error)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
