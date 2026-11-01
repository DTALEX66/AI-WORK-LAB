#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Count which declared objects the product itself validates against -- and pin the answer.

design-lab/config/object-model.json declares 21 objects and names a schema for each. Two questions
get asked about those schemas today: does the file exist (verify_design_kernel.py), and does the
Workbench render the shape (the route payload gates). Neither asks the one that matters for the
contract layer: does any product code validate a payload against it, or is the only thing that ever
reads the file a verifier script?

So this measures, per object, whether the schema's file name or its version stamp
(``properties.schemaVersion.const``, else ``$id``) appears in the product sources (src/, packages/,
apps/workbench/) or only in design-lab/scripts/. Three outcomes:

* PRODUCT          -- product code touches the shape, so the declaration is live;
* TOOLING_ONLY     -- only a verifier reads it, so the schema documents an audit, not a boundary;
* UNREFERENCED     -- nothing reads it at all.

Every object outside PRODUCT is pinned below with what implements it instead, and the counts are
pinned, so a schema gaining or losing a product reference cannot pass unnoticed in either direction.

Deliberately literal, because a smarter-looking scan here produced a false report: a name search
claimed the design-system, the artifact and the jury record were unimplemented (they are not) merely
because the version they write -- ``design-lab/assurance-jury-record/v2`` -- does not contain the
identifier the object model chose. This file only ever claims what a substring can be checked
against, and the reasons carry the rest.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MODEL_REL = 'design-lab/config/object-model.json'
SCHEMA_BASE = 'design-lab'
PRODUCT_SCOPES = ('src', 'packages', 'apps/workbench')
TOOLING_SCOPES = ('design-lab/scripts',)
SUFFIXES = {'.py', '.ts', '.mjs'}
EXCLUDED = {'__pycache__', 'node_modules', 'build', 'dist'}

#: Objects the product never validates against this schema, and what does. Dated 2026-10-08 against
#: HEAD c0d44f00. A row must be removed -- not reworded -- when product code starts using the schema.
TOOLING_ONLY = {
    'brief': 'the product persists and reads briefs through src/design_lab/design_layer.py and the '
             'service store; the only readers of schemas/design-brief.schema.json are '
             'verify_reference_e2e.py and scaffold_open_design_plugin.py',
    'direction': 'directions live in src/design_lab/design_layer.py; the schema is read only when a '
                 'plugin scaffold is generated',
    'quality-assessment': 'the design-critique schema is named only by '
                          'design-lab/scripts/scaffold_open_design_plugin.py; the quality path the '
                          'product runs is the jury record (quality-report above), so this shape is a '
                          'second name for a thing already audited elsewhere',
    'evidence-record': 'evidence bundles are written and hashed by the task runners and read back by '
                       'verify_host_e3_evidence.py; no product path validates one against this schema',
    'project': 'project state is the service store plus src/design_lab/runtime/paths.py; '
               'design-project-state.schema.json is read by verify_design_kernel.py, '
               'verify_runtime_contracts_v3.py and verify_review_surface.py, not by the service',
    'command': 'the CLI parses arguments directly (src/design_lab/cli.py); design-command.schema.json '
               'is read only by verify_design_kernel.py',
    'execution-result': 'task attempts are recorded by src/design_lab/native_tasks.py; '
                        'execution-result.schema.json is checked only by verify_design_kernel.py',
    'memory-record': 'the design-memory store writes rows; design-memory.schema.json is read only by '
                     'verify_design_memory.py',
    'extraction-job': 'the extraction chain runs without loading its own schema; '
                      'extraction-job.schema.json is read only by verify_extraction_chain.py',
    'preflight-report': 'the profiles under design-lab/production/profiles/ are what '
                        'preflight.schema.json judges, and production_preflight.py loads them through '
                        'load_profile() -- which reads the profile JSON, never the schema. The report '
                        'the product emits is bound to a different file '
                        '(schemas/artifact-preflight.schema.json) and compared by '
                        'verify_artifact_preflight_contract.py; preflight.schema.json appears in src/ '
                        'only inside docstrings, which is the prose this gate stopped counting on '
                        '2026-10-08',
}

UNREFERENCED = {
    'reference-set': 'no code at all reads schemas/reference-set.schema.json; references are held as '
                     'design-asset rows and as the brief\'s own reference list',
    'artifact': 'implemented as rows: the artifact and asset_version tables are the real shape and '
                'src/design_lab/image_assets.py reads them by column; schemas/artifact.schema.json is '
                'named nowhere',
    'tool-run': 'nothing names schemas/tool-run.schema.json; tool executions are recorded as '
                'native_execution_v1 rows and task attempts',
    'method-card': 'nothing reads schemas/method-card.schema.json (method_id/name/steps/attribution) '
                   'at all, and the only MethodCards that exist in this repository follow a '
                   'different shape -- '
                   'schemas/visual-quality/master-method-card.schema.json '
                   '(id/name/thesis/transferable_methods/shallow_mimicry_risks), which the research '
                   'master studies and verify_style_master_method.py use. Two incompatible declared '
                   'cards, and no product code produces either',
    'handoff-package': 'nothing reads schemas/design-handoff.schema.json. The handoff the product '
                       'assembles is decided in src/design_lab/assurance/handoff_readiness.py, which '
                       'names the file only in its own docstring -- prose this gate stopped counting '
                       'on 2026-10-08 -- and emits "design-lab/handoff-readiness/v1", a payload '
                       'version no schema in this repository binds. So the declared handoff document '
                       'has a reader in the prose and none in the code',
}


def version_stamp(schema_path: Path) -> str:
    """The literal a payload must carry to claim this schema, falling back to the schema's own $id."""
    try:
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return ''
    const = ((schema.get('properties') or {}).get('schemaVersion') or {}).get('const')
    return const if isinstance(const, str) else (schema.get('$id') or '')


#: Kinds that carry no meaning for "did this statement start here".


def _statement_string(tokens, number: int) -> bool:
    """True when the STRING token at ``number`` is a docstring rather than a value in use.

    A docstring is a string that both begins and ends a statement: ignoring layout tokens, the last
    thing before it is a newline, an indent, or the colon that opens a block, and the next thing after
    it is the newline that ends it. A path handed to ``load_schema`` fails that test because it sits
    inside parentheses or after an equals sign -- which is exactly the difference this gate is for.
    Single-pass by construction: only the two neighbouring tokens are consulted, never a rescan.
    """
    import tokenize
    before = number - 1
    while before >= 0 and tokens[before].type in (tokenize.NEWLINE, tokenize.NL, tokenize.INDENT,
                                                 tokenize.DEDENT, tokenize.COMMENT):
        before -= 1
    after = number + 1
    while after < len(tokens) and tokens[after].type in (tokenize.NL, tokenize.COMMENT):
        after += 1
    starts_a_statement = (before < 0
                          or tokens[before].type in (tokenize.NEWLINE, tokenize.INDENT,
                                                     tokenize.DEDENT)
                          or tokens[before].string in (':', '->'))
    ends_a_statement = after < len(tokens) and tokens[after].type == tokenize.NEWLINE
    return starts_a_statement and ends_a_statement


def code_text(text: str, suffix: str) -> str:
    """The executable text of a source file, with prose removed.

    A comment or a docstring that names a schema is documentation about that schema, not a reference
    to it. Without this rule the classifier reports a false PRODUCT the moment anyone writes an honest
    note in src/ -- measured 2026-10-08, when ``design_layer.py`` gained a comment explaining that
    ``design-brief.schema.json`` declares a model no code stores, and the gate answered
    "brief is now PRODUCT" off that comment alone.

    Python goes through ``tokenize``: comments are dropped, and a string literal that stands alone as
    a statement (a module, class or function docstring) is dropped, while a string inside a call, an
    assignment or a return -- which is how a path actually reaches code -- is kept. TypeScript and mjs
    drop whole-line ``//`` comments and ``/* ... */`` blocks; anything else a JS comment can hide in is
    left alone rather than guessed at.
    """
    if suffix == '.py':
        import io
        import tokenize
        pieces = []
        try:
            tokens = list(tokenize.generate_tokens(io.StringIO(text).readline))
        except (tokenize.TokenError, IndentationError, SyntaxError):
            # Unparsable to tokenize: fall back to whole-line comments rather than pretending prose
            # was code, so a malformed file never silently gains a reference.
            return '\n'.join(line for line in text.splitlines() if not line.strip().startswith('#'))
        for number, token in enumerate(tokens):
            kind, string = token.type, token.string
            if kind in (tokenize.COMMENT, tokenize.ENCODING):
                continue
            if kind == tokenize.STRING and _statement_string(tokens, number):
                continue
            pieces.append(string)
        return ' '.join(pieces)
    lines = []
    in_block = False
    for line in text.splitlines():
        stripped = line.strip()
        if in_block:
            if '*/' in stripped:
                in_block = False
            continue
        if stripped.startswith('/*'):
            if '*/' not in stripped:
                in_block = True
            continue
        if stripped.startswith('//'):
            continue
        lines.append(line)
    return '\n'.join(lines)


def corpus(root: Path, scopes) -> str:
    """The text of everything in these scopes except this file.

    The inventory below names schema files in its own reasons, so scanning this script would let the
    gate cite itself as evidence: the first run reported 16 objects as TOOLING_ONLY and five as
    UNREFERENCED->pinned-wrong, purely because the strings it was looking for sit in its own comments.
    """
    here = Path(__file__).resolve()
    pieces = []
    for label in scopes:
        base = root / label
        if not base.is_dir():
            continue
        for path in base.rglob('*'):
            if path.is_file() and path.suffix in SUFFIXES and not (EXCLUDED & set(path.parts)):
                if path.resolve() == here:
                    continue
                try:
                    raw = path.read_text(encoding='utf-8', errors='ignore')
                except OSError:
                    continue
                pieces.append(code_text(raw, path.suffix))
    return '\n'.join(pieces)


def classify(root: Path) -> tuple[dict[str, str], dict[str, str]]:
    """(id -> bucket, id -> schema file name) for the object model at this root."""
    model = json.loads((root / MODEL_REL).read_text(encoding='utf-8'))
    product = corpus(root, PRODUCT_SCOPES)
    tooling = corpus(root, TOOLING_SCOPES)
    buckets: dict[str, str] = {}
    names: dict[str, str] = {}
    for obj in model.get('objects') or []:
        identifier = obj.get('id') or '<no id>'
        ref = obj.get('schemaRef') or ''
        names[identifier] = ref.split('/')[-1]
        schema_path = root / SCHEMA_BASE / ref if ref else None
        if not ref or not schema_path or not schema_path.is_file():
            buckets[identifier] = 'MISSING_SCHEMA_FILE'
            continue
        stamp = version_stamp(schema_path)
        in_product = names[identifier] in product or bool(stamp and stamp in product)
        in_tooling = names[identifier] in tooling or bool(stamp and stamp in tooling)
        buckets[identifier] = ('PRODUCT' if in_product
                               else 'TOOLING_ONLY' if in_tooling else 'UNREFERENCED')
    return buckets, names


def audit(root: Path, check_counts: bool = True):
    """(counts, errors, buckets, names) for the object model sitting at this root.

    Split out of main() so a test can point the rules at a scratch tree and watch one named finding
    fire; the pinned counts are the part that only means something against the real repository.
    """
    buckets, names = classify(root)
    errors = []
    counts = {'PRODUCT': 0, 'TOOLING_ONLY': 0, 'UNREFERENCED': 0, 'MISSING_SCHEMA_FILE': 0}
    for identifier, bucket in buckets.items():
        counts[bucket] += 1
        if bucket == 'TOOLING_ONLY' and identifier not in TOOLING_ONLY:
            errors.append(f'{identifier}: product code never validates this shape and the row is not '
                          'pinned -- say what implements it today (schemas/visual-quality/* is not an '
                          'answer that transfers) or wire the schema')
        if bucket == 'UNREFERENCED' and identifier not in UNREFERENCED:
            errors.append(f'{identifier}: no code at all reads {names[identifier]} and the row is not '
                          'pinned -- state what does, or retire the declaration')
        if bucket == 'MISSING_SCHEMA_FILE':
            errors.append(f'{identifier}: schemaRef names {names[identifier]}, which does not exist')
    # A pinned row is only stale if the object it describes is still declared. When an object leaves
    # the model entirely, the bucket counts are what catch it -- and keeping this loop scoped to the
    # model is what lets a test exercise one object at a time.
    for identifier in sorted(set(TOOLING_ONLY) & set(buckets)
                            - {k for k, v in buckets.items() if v == 'TOOLING_ONLY'}):
        errors.append(f'{identifier}: pinned as TOOLING_ONLY but it is now '
                      f'{buckets.get(identifier, "not in the model")} -- a paid debt must not leave a '
                      'stale claim behind')
    for identifier in sorted(set(UNREFERENCED) & set(buckets)
                            - {k for k, v in buckets.items() if v == 'UNREFERENCED'}):
        errors.append(f'{identifier}: pinned as UNREFERENCED but it is now '
                      f'{buckets.get(identifier, "not in the model")} -- the inventory is a claim about '
                      'today, not a permanent exemption')
    for table, label in ((TOOLING_ONLY, 'TOOLING_ONLY'), (UNREFERENCED, 'UNREFERENCED')):
        for identifier, reason in table.items():
            if not isinstance(reason, str) or len(reason.strip()) < 60:
                errors.append(f'{identifier}: a {label} row needs a sentence naming what implements it '
                              f'({len((reason or "").strip())} chars is a placeholder)')
    # The counts are pinned as well as the membership, because a bucket that quietly changes size is
    # how a contract layer erodes one object at a time. 5/10/6 -> 6/10/5 on 2026-10-19 (T16/U09):
    # candidate-knowledge is now PRODUCT because assurance/knowledge_feedback.py loads the V1 schema
    # to validate its downward projection, so the pinned UNREFERENCED row was deleted rather than
    # reworded and the two buckets moved together.
    expected = {'PRODUCT': 6, 'TOOLING_ONLY': 10, 'UNREFERENCED': 5, 'MISSING_SCHEMA_FILE': 0}
    for bucket, want in (expected.items() if check_counts else ()):
        if counts[bucket] != want:
            errors.append(f'{bucket}: {counts[bucket]} objects, expected {want} -- measured '
                          '2026-10-08 against HEAD c0d44f00; move the membership rows as well as this '
                          'number, or the count hides a swap')
    return counts, errors, buckets, names


def main(argv=None) -> int:
    counts, errors, buckets, names = audit(REPO)
    if not buckets:
        print('OBJECT_MODEL_BACKING=FAIL objects=0 -- nothing was classified, which is not a pass')
        return 1
    print(f'objects={len(buckets)} ' + ' '.join(f'{k.lower()}={v}' for k, v in sorted(counts.items())))
    for identifier, bucket in sorted(buckets.items()):
        if bucket != 'PRODUCT':
            print(f'  {bucket:12} {identifier} schema={names[identifier]}')
    for error in errors:
        print(f'ERROR {error}')
    if errors:
        print(f'OBJECT_MODEL_BACKING=FAIL defects={len(errors)}')
        return 1
    print(f'OBJECT_MODEL_BACKING=OK objects={len(buckets)} product={counts["PRODUCT"]} '
          f'tooling_only={counts["TOOLING_ONLY"]} unreferenced={counts["UNREFERENCED"]}')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
