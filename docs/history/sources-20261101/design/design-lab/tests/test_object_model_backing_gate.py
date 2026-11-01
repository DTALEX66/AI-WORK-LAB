# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_object_model_backing.py.

The gate's claim is narrow on purpose -- "does any product code name this object's schema, or is the
only reader a verifier?" -- so the tests check exactly that, on scratch trees, plus the one property
that bit me while writing it: the gate carries a filename inventory in its own source, so if its
corpus includes itself, the gate cites its own reasons as evidence and every object it mentions turns
into a reference. The first run did exactly that and reported 16 TOOLING_ONLY objects; the test below
keeps that from coming back.
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import json
import re
import shutil
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / 'design-lab' / 'scripts' / 'verify_object_model_backing.py'
SCRATCH_BASE = REPO / '.project-local' / 'task-runtime' / 'object-model-backing-scratch'

# Measured 2026-10-08 against HEAD a4a76c06, and pinned inside the gate as well: six of the 21
# declared objects are validated by product code, ten only by verifier scripts, five by nothing.
# These numbers are LOWER than the ones pinned a few hours earlier (7/9/5) because the classifier was
# fixed to stop counting prose: preflight-report, handoff-package and quality-report had been read as
# product references purely from docstrings, and quality-report became honest only after its row was
# re-pointed to the V2 schema human_jury.py really loads.
# PRODUCT is: delivery-manifest (assurance/delivery_bom.py), design-system (interop/dtcg.py),
# quality-report (assurance/human_jury.py), domain-pack (domain_packs.py), research-finding
# (assurance/research_store.py), and since 2026-10-19 candidate-knowledge
# (assurance/knowledge_feedback.py loads the V1 schema for its downward projection).
REAL_COUNTS = {'PRODUCT': 6, 'TOOLING_ONLY': 10, 'UNREFERENCED': 5, 'MISSING_SCHEMA_FILE': 0}


def load_gate(name: str):
    spec = importlib.util.spec_from_file_location(name, GATE_PATH)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_scratch(root: Path, objects, product_text='', tooling_text=''):
    """A minimal repository: an object model, its schemas, one product file, one verifier script."""
    if root.exists():
        shutil.rmtree(root)
    (root / 'design-lab' / 'config').mkdir(parents=True)
    (root / 'design-lab' / 'schemas').mkdir(parents=True)
    (root / 'src').mkdir(parents=True)
    (root / 'design-lab' / 'scripts').mkdir(parents=True)
    for obj in objects:
        schema_name = (obj.get('schemaRef') or '').split('/')[-1]
        if schema_name:
            (root / 'design-lab' / 'schemas' / schema_name).write_text(
                json.dumps({'$schema': 'https://json-schema.org/draft/2020-12/schema',
                            '$id': f'https://example.invalid/schemas/{schema_name}',
                            'type': 'object',
                            'properties': {'schemaVersion': {'const': obj['version']}}}),
                encoding='utf-8', newline='\n')
    (root / 'design-lab' / 'config' / 'object-model.json').write_text(
        json.dumps({'version': 'design-lab/object-model/v1',
                    'objects': [{k: v for k, v in obj.items() if k != 'version'}
                                for obj in objects]}, indent=2) + '\n',
        encoding='utf-8', newline='\n')
    (root / 'src' / 'product.py').write_text(product_text or '# no schema names here\n',
                                            encoding='utf-8', newline='\n')
    (root / 'design-lab' / 'scripts' / 'verifier.py').write_text(
        tooling_text or '# no schema names here\n', encoding='utf-8', newline='\n')
    return root


def audit(root: Path, check_counts=False):
    gate = load_gate('object_model_backing_scratch')
    return gate.audit(root, check_counts)


class ShippedTreeTests(unittest.TestCase):
    def test_the_shipped_tree_passes_with_the_counts_the_gate_pins(self):
        gate = load_gate('object_model_backing_shipped')
        counts, errors, buckets, names = gate.audit(REPO)
        self.assertEqual(errors, [], f'the shipped tree is red: {errors[:4]}')
        self.assertEqual(counts, REAL_COUNTS)
        self.assertEqual(len(buckets), sum(REAL_COUNTS.values()))

    def test_main_reports_the_verdict_line_and_exits_zero(self):
        gate = load_gate('object_model_backing_main')
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = gate.main([])
        self.assertEqual(code, 0, buffer.getvalue())
        self.assertIn('OBJECT_MODEL_BACKING=OK', buffer.getvalue())

    def test_every_non_product_object_carries_a_sentence_naming_what_implements_it(self):
        """An exemption without a sentence is a way of never looking at the object again.

        The reason has to point somewhere a reader can open -- a path -- or state the absence in words
        that can be falsified ("no code at all reads…", "nothing names…"). A reason that only
        restates the bucket ("not wired yet") is the placeholder this refuses.
        """
        gate = load_gate('object_model_backing_reasons')
        path_like = re.compile(r'(src|packages|apps|design-lab)/[\w./-]+|[\w-]+\.py')
        absence = ('no code', 'nothing names', 'no product code', 'no product path', 'nowhere',
                   'no producer')
        for table in (gate.TOOLING_ONLY, gate.UNREFERENCED):
            for identifier, reason in table.items():
                self.assertGreaterEqual(len(reason.strip()), 60,
                                        f'{identifier} has a placeholder exemption')
                self.assertTrue(path_like.search(reason) or any(word in reason for word in absence),
                                f'{identifier}: {reason[:70]!r} names no path and no stated absence')

    def test_the_two_inventories_do_not_claim_the_same_object_twice(self):
        gate = load_gate('object_model_backing_overlap')
        shared = set(gate.TOOLING_ONLY) & set(gate.UNREFERENCED)
        self.assertEqual(shared, set(), f'{sorted(shared)} sits in both buckets')
        _, _, buckets, _ = gate.audit(REPO)
        for identifier, bucket in buckets.items():
            if bucket == 'TOOLING_ONLY':
                self.assertIn(identifier, gate.TOOLING_ONLY)
            elif bucket == 'UNREFERENCED':
                self.assertIn(identifier, gate.UNREFERENCED)


    def test_a_row_repointed_to_satisfy_the_matcher_must_name_the_file_the_product_opens(self):
        """The design-system row was moved on 2026-10-08 onto the schema dtcg really loads.

        The classifier is deliberately substring-based, which means a registry edit could make an
        object look PRODUCT by pointing it at a schema whose name only appears in a comment. For the
        one row this wave re-pointed, the strongest form is asserted instead: the file the object
        model names is the file the module opens at runtime, and the retired shape is named by no
        row at all.
        """
        sys.path.insert(0, str(REPO / 'src'))
        from design_lab.interop import dtcg
        model = json.loads((REPO / 'design-lab' / 'config' / 'object-model.json')
                           .read_text(encoding='utf-8'))
        row = next(item for item in model['objects'] if item['id'] == 'design-system')
        declared = (REPO / 'design-lab' / row['schemaRef']).resolve()
        self.assertEqual(dtcg.SCHEMA_PATH.resolve(), declared,
                         'the object row must name the schema design_layer/dtcg validates against')
        self.assertNotIn('design-system.schema.json', json.dumps(model, ensure_ascii=False),
                         'a retired shape may not stay bound to an object')
        gate = load_gate('object_model_backing_repoint')
        _counts, errors, buckets, _names = gate.audit(REPO)
        self.assertEqual([], errors)
        self.assertEqual('PRODUCT', buckets['design-system'])

    def test_both_repointed_rows_name_the_file_the_product_opens(self):
        """design-system and quality-report were each moved onto an enforced schema; prove both."""
        sys.path.insert(0, str(REPO / 'src'))
        from design_lab.assurance import human_jury
        from design_lab.interop import dtcg
        model = json.loads((REPO / 'design-lab' / 'config' / 'object-model.json')
                           .read_text(encoding='utf-8'))
        rows = {item['id']: item for item in model['objects']}
        for identifier, opened in (('design-system', dtcg.SCHEMA_PATH),
                                   ('quality-report', human_jury.SCHEMA_PATH)):
            declared = (REPO / 'design-lab' / rows[identifier]['schemaRef']).resolve()
            self.assertEqual(opened.resolve(), declared,
                             f'{identifier} does not name the schema its emitter loads')
        self.assertNotIn('jury-record.schema.json', json.dumps(model, ensure_ascii=False),
                         'the V1 jury shape may not stay bound to an object')


class ProseIsNotAReferenceTests(unittest.TestCase):
    """A comment or docstring naming a schema documents it; it does not use it.

    This rule earned itself on 2026-10-08: the classifier matched substrings over raw file text, so
    three rows were counted as validated by product code because a module docstring mentioned the file
    name -- and a comment I added explaining that ``design-brief.schema.json`` describes a model no
    code stores would have quietly promoted ``brief`` to PRODUCT too. A gate whose buckets can be moved
    by writing prose about the bucket is not measuring anything.
    """

    OBJ = [{'id': 'thing', 'name': 'Thing', 'description': 'd',
            'schemaRef': 'schemas/thing.schema.json', 'version': 'x/thing/v1'}]

    def bucket(self, name, product_text):
        """Classify one scratch object whose schema a verifier script loads in code."""
        root = build_scratch(SCRATCH_BASE / f'prose-{name}', self.OBJ,
                             product_text=product_text,
                             tooling_text="SCHEMA = 'schemas/thing.schema.json'\n")
        _counts, _errors, buckets, _names = audit(root)
        return buckets['thing']

    def test_a_whole_line_comment_is_not_a_product_reference(self):
        self.assertEqual('TOOLING_ONLY',
                         self.bucket('line', '# the shape is schemas/thing.schema.json\n'
                                             'VALUE = 1\n'))

    def test_a_trailing_comment_is_not_a_product_reference(self):
        self.assertEqual('TOOLING_ONLY',
                         self.bucket('trailing', 'VALUE = 1  # schemas/thing.schema.json\n'))

    def test_a_module_docstring_is_not_a_product_reference(self):
        self.assertEqual('TOOLING_ONLY',
                         self.bucket('moddoc', '"""See schemas/thing.schema.json."""\nVALUE = 1\n'))

    def test_a_function_docstring_is_not_a_product_reference(self):
        self.assertEqual('TOOLING_ONLY', self.bucket(
            'funcdoc', 'def load():\n    """Reads schemas/thing.schema.json."""\n    return 1\n'))

    def test_a_path_in_code_still_is_one(self):
        """The strip must not swallow real references: this is how a loader names its schema."""
        self.assertEqual('PRODUCT', self.bucket('assign', "SCHEMA = 'schemas/thing.schema.json'\n"))

    def test_a_path_inside_a_call_still_is_one(self):
        self.assertEqual('PRODUCT', self.bucket(
            'call', "load_schema('schemas/thing.schema.json')\n"))


class ScratchTreeTests(unittest.TestCase):
    def test_an_unpinned_unreferenced_object_is_named(self):
        root = build_scratch(SCRATCH_BASE / 'unpinned', [
            {'id': 'mystery-card', 'name': 'Mystery', 'description': 'd',
             'schemaRef': 'schemas/mystery-card.schema.json', 'version': 'x/mystery/v1'}])
        counts, errors, buckets, _ = audit(root)
        self.assertEqual(buckets['mystery-card'], 'UNREFERENCED')
        self.assertIn('mystery-card', ' '.join(errors))
        self.assertIn('not pinned', ' '.join(errors))

    def test_an_object_pinned_as_unreferenced_that_gains_a_product_reference_is_reported(self):
        """Paying the debt must not leave the old claim sitting in the file."""
        root = build_scratch(SCRATCH_BASE / 'paid', [
            {'id': 'artifact', 'name': 'Artifact', 'description': 'd',
             'schemaRef': 'schemas/artifact.schema.json', 'version': 'x/artifact/v1'}],
            product_text="SCHEMA = 'artifact.schema.json'\n")
        counts, errors, buckets, _ = audit(root)
        self.assertEqual(buckets['artifact'], 'PRODUCT')
        joined = ' '.join(errors)
        self.assertIn('pinned as UNREFERENCED but it is now PRODUCT', joined)

    def test_a_missing_schema_file_is_its_own_finding(self):
        root = build_scratch(SCRATCH_BASE / 'missing', [
            {'id': 'ghost', 'name': 'Ghost', 'description': 'd',
             'schemaRef': 'schemas/ghost.schema.json', 'version': 'x/ghost/v1'}])
        (root / 'design-lab' / 'schemas' / 'ghost.schema.json').unlink()
        counts, errors, buckets, _ = audit(root)
        self.assertEqual(buckets['ghost'], 'MISSING_SCHEMA_FILE')
        self.assertIn('does not exist', ' '.join(errors))

    def test_a_placeholder_reason_is_rejected_even_when_the_bucket_is_right(self):
        root = build_scratch(SCRATCH_BASE / 'placeholder', [
            {'id': 'reference-set', 'name': 'R', 'description': 'd',
             'schemaRef': 'schemas/reference-set.schema.json',
             'version': 'x/reference-set/v1'}])
        gate = load_gate('object_model_backing_placeholder')
        gate.UNREFERENCED = {'reference-set': 'not wired'}
        counts, errors, buckets, _ = gate.audit(root)
        self.assertIn('needs a sentence', ' '.join(errors))

    def test_the_pinned_counts_are_only_checked_against_the_real_tree(self):
        """check_counts=False lets a scratch tree exercise the membership rules without inheriting
        the real repository's numbers, which is what makes the four cases above meaningful."""
        root = build_scratch(SCRATCH_BASE / 'counts', [
            {'id': 'reference-set', 'name': 'R', 'description': 'd',
             'schemaRef': 'schemas/reference-set.schema.json',
             'version': 'x/reference-set/v1'}])
        strict = audit(root, check_counts=True)
        loose = audit(root, check_counts=False)
        self.assertIn(f"expected {REAL_COUNTS['UNREFERENCED']}", ' '.join(strict[1]))
        self.assertEqual(loose[1], [], f'the scratch tree should be clean but: {loose[1]}')

    def test_an_empty_model_fails_closed_rather_than_passing_nothing(self):
        root = build_scratch(SCRATCH_BASE / 'empty', [])
        gate = load_gate('object_model_backing_empty')
        gate.REPO = root
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = gate.main([])
        self.assertEqual(code, 1, buffer.getvalue())
        self.assertIn('objects=0', buffer.getvalue())


class CorpusIntegrityTests(unittest.TestCase):
    def test_the_gate_must_not_cite_its_own_inventory_as_evidence(self):
        """Remove the self-exclusion and the gate starts reading its own reasons as references.

        This is not hypothetical: the first version of the gate reported 16 TOOLING_ONLY objects
        because its pinned reasons name schema files, and it was scanning the file those reasons live
        in. The numbers were wrong in the direction that hides a gap, which is the worst direction.
        """
        source = GATE_PATH.read_text(encoding='utf-8')
        self.assertEqual(source.count('if path.resolve() == here:'), 1)
        directory = SCRATCH_BASE / 'no-self-exclusion'
        if directory.exists():
            shutil.rmtree(directory)
        directory.mkdir(parents=True)
        path = directory / 'verify_object_model_backing.py'
        path.write_text(source.replace('                if path.resolve() == here:\n'
                                       '                    continue\n', ''),
                        encoding='utf-8', newline='\n')
        spec = importlib.util.spec_from_file_location('gate_without_self_exclusion', path)
        weak = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = weak
        spec.loader.exec_module(weak)
        counts, errors, buckets, _ = weak.audit(REPO)
        self.assertNotEqual(counts, REAL_COUNTS,
                            'the weakened gate agrees with the shipped one, so the corpus never '
                            'contained this file in the first place')
        self.assertGreater(counts['TOOLING_ONLY'], REAL_COUNTS['TOOLING_ONLY'],
                           f'expected self-citation to inflate TOOLING_ONLY, got {counts}')


if __name__ == '__main__':
    unittest.main()
