# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_rights_registry.py.

Two obligations, both tested:

1. the shipped gate is TRUE of the shipped repository -- the real rights registry passes it,
   and it reports a non-empty inventory rather than matching nothing;
2. each refusal goes RED FOR ITS OWN REASON against a mutated COPY of the tree. The scratch
   tree is assembled from the sources the registry itself cites, and the unmutated copy is
   asserted green first: a mutation that goes red because the scratch tree was assembled badly
   proves nothing, and a mutation that stays green means the gate cannot see that defect.

A finding whose code is not the named one does not count. This is the check that keeps the
gate honest about the thing it was written for: the RIGHTS link had a 74-subject requirements
list, a hand-written band table claiming to classify it, and a summary block nothing recomputed.
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import sys
import types
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
GATE_PATH = REPO / 'design-lab' / 'scripts' / 'verify_rights_registry.py'
SCRATCH_BASE = REPO / '.project-local' / 'task-runtime' / 'rights-registry-scratch'

sys.path.insert(0, str(REPO / 'src'))

#: Every refusal the gate can raise. A code outside this list is a bug in the gate, and a code
#: here with no test is a refusal nobody has ever seen work.
EXPECTED_CODES = (
    'REGISTRY_UNREADABLE',
    'REGISTRY_UNBOUND',
    'REGISTRY_EMPTY',
    'ENTRY_MALFORMED',
    'SUBJECT_DUPLICATE',
    'COMBINER_UNREADABLE',
    'STATE_UNCLASSIFIED',
    'COUNT_DISAGREES',
    'CITATION_UNRESOLVED',
    'FIELD_LIST_EMPTY',
)


def load_gate(path: Path = None):
    target = Path(path or GATE_PATH)
    spec = importlib.util.spec_from_file_location('verify_rights_registry_under_test', target)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def build_scratch(dest: Path, mutate=None) -> Path:
    """A tree the gate can judge: the registry plus the sources the registry itself cites."""
    gate = load_gate()
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    registry = json.loads((REPO / gate.REGISTRY_REL).read_text(encoding='utf-8'))
    cited = list(registry.get('generated_from') or [])
    cited += [e['evidence_source'] for e in registry['entries']
              if isinstance(e.get('evidence_source'), str)]
    for raw in sorted(set(cited)):
        target = dest / raw.rstrip('/')
        if raw.endswith('/'):
            target.mkdir(parents=True, exist_ok=True)
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text('cited source placeholder\n', encoding='utf-8')
    if mutate is not None:
        mutate(registry, dest)
    path = dest / gate.REGISTRY_REL
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(registry, ensure_ascii=False, indent=2), encoding='utf-8')
    return dest


def outcome(dest: Path):
    """(sorted refusal codes, summary) -- exceptions and findings are the same currency here."""
    gate = load_gate()
    try:
        findings, summary = gate.scan(dest)
    except gate.RegistryError as exc:
        return [exc.code], {}
    codes = sorted({line.split(' ', 1)[0] for line in findings})
    return codes, summary


class ShippedRegistryTests(unittest.TestCase):
    def test_the_shipped_registry_passes_the_shipped_gate(self):
        gate = load_gate()
        findings, summary = gate.scan(REPO)
        self.assertEqual(findings, [], '\n'.join(findings[:5]))
        self.assertEqual(summary['entries'], 74)
        self.assertEqual(summary['counts_recorded'], summary['counts_derived'])
        # Liveness: a gate that classified nothing would also report no findings.
        tally = summary['band_tally']
        self.assertEqual(tally['BLOCKER'] + tally['WARNING'] + tally['CLEAN'] + tally['ABSENT'],
                         summary['entries'] * len(summary['fields']))
        self.assertEqual(tally['UNCLASSIFIED'], 0)

    def test_the_gate_uses_the_bands_from_the_module_not_a_copy(self):
        """The gate must classify with the live combiner, or it drifts with it."""
        from design_lab.assurance import handoff_readiness
        gate = load_gate()
        combiner = gate.load_combiner()
        self.assertIs(combiner.RIGHTS_FIELDS, handoff_readiness.RIGHTS_FIELDS)
        self.assertIs(combiner.rights_band, handoff_readiness.rights_band)
        self.assertEqual(tuple(combiner.RIGHTS_FIELDS),
                         ('territory.state', 'use_restriction', 'output_restriction',
                          'redistribution'))

    def test_every_refusal_code_the_gate_can_raise_is_declared_here(self):
        gate = load_gate()
        self.assertEqual(set(gate.REFUSALS), set(EXPECTED_CODES))
        source = GATE_PATH.read_text(encoding='utf-8')
        for code in EXPECTED_CODES:
            self.assertIn(code, source, f'{code} is declared but never emitted')


class CombinerRefusalsTests(unittest.TestCase):
    """The gate reads the bands from the live module; it must refuse a module that has none.

    Both cases swap a stand-in into the package attribute the gate imports through, so the
    refusal is the gate's own and not an ImportError nobody reached.
    """

    def with_combiner(self, gate, module):
        """Swap a stand-in into the package attribute the gate imports through.

        One gate instance per case: `load_gate()` compiles a fresh module each call, and its
        RegistryError is therefore a different class object from another call's.
        """
        import design_lab.assurance as assurance
        from design_lab.assurance import handoff_readiness  # binds the package attribute
        assurance.handoff_readiness = module
        try:
            return gate.load_combiner()
        finally:
            assurance.handoff_readiness = handoff_readiness

    def test_a_combiner_without_a_band_function_is_refused(self):
        gate = load_gate()
        stub = types.ModuleType('stub_readiness')
        stub.RIGHTS_FIELDS = ('use_restriction',)
        with self.assertRaises(gate.RegistryError) as caught:
            self.with_combiner(gate, stub)
        self.assertEqual(caught.exception.code, 'COMBINER_UNREADABLE')
        self.assertIn('rights_band', str(caught.exception))

    def test_a_combiner_that_classifies_no_field_is_refused(self):
        gate = load_gate()
        stub = types.ModuleType('stub_readiness2')
        stub.RIGHTS_FIELDS = ()
        stub.rights_band = lambda state: 'CLEAN'
        with self.assertRaises(gate.RegistryError) as caught:
            self.with_combiner(gate, stub)
        self.assertEqual(caught.exception.code, 'FIELD_LIST_EMPTY')

    def test_the_real_combiner_loads(self):
        self.assertTrue(load_gate().load_combiner().RIGHTS_FIELDS)


class MutatedRegistryTests(unittest.TestCase):
    """Each defect must convict under its own code, against a copy of the tree."""

    def assert_red(self, mutate, code, phrase):
        dest = build_scratch(SCRATCH_BASE / 'case', mutate)
        codes, _ = outcome(dest)
        self.assertIn(code, codes, f'expected {code}, got {codes}')
        gate = load_gate()
        findings, _ = gate.scan(dest)
        line = next((f for f in findings if f.startswith(code)), '')
        self.assertIn(phrase, line, f'{code} fired but did not say {phrase!r}: {line}')

    def setUp(self):
        control = build_scratch(SCRATCH_BASE / 'control')
        codes, summary = outcome(control)
        self.assertEqual(codes, [], f'the control copy must be green first: {codes}')
        self.assertTrue(summary['entries'])

    def test_a_state_no_band_classifies_is_refused(self):
        def mutate(registry, dest):
            registry['entries'][0]['use_restriction'] = 'LITIGATION_HOLD'
        self.assert_red(mutate, 'STATE_UNCLASSIFIED', 'in no rights band')

    def test_a_hand_edited_summary_is_refused(self):
        def mutate(registry, dest):
            registry['counts']['adjudicated'] = registry['counts']['adjudicated'] + 3
        self.assert_red(mutate, 'COUNT_DISAGREES', 'derive')

    def test_a_duplicated_subject_is_refused(self):
        def mutate(registry, dest):
            registry['entries'].append(dict(registry['entries'][3]))
            registry['counts']['subjects'] = len(registry['entries'])
        self.assert_red(mutate, 'SUBJECT_DUPLICATE', 'counted twice')

    def test_a_citation_that_does_not_resolve_is_refused(self):
        def mutate(registry, dest):
            (dest / 'NOTICE').unlink()
        self.assert_red(mutate, 'CITATION_UNRESOLVED', 'does not exist')

    def test_a_citation_outside_the_repository_is_refused(self):
        def mutate(registry, dest):
            registry['entries'][0]['evidence_source'] = '../../etc/passwd'
        self.assert_red(mutate, 'CITATION_UNRESOLVED', 'outside the repository')

    def test_an_entry_without_a_subject_id_is_refused(self):
        def mutate(registry, dest):
            del registry['entries'][2]['subject_id']
        codes, _ = outcome(build_scratch(SCRATCH_BASE / 'nosubject', mutate))
        self.assertEqual(codes, ['ENTRY_MALFORMED'])

    def test_an_empty_registry_is_refused_not_passed(self):
        """The vacuity floor: a registry that lists nothing requires nothing."""
        def mutate(registry, dest):
            registry['entries'] = []
            registry['counts'] = {'subjects': 0, 'adjudicated': 0, 'awaiting_adjudication': 0,
                                  'blocked_pending_owner': 0}
        codes, _ = outcome(build_scratch(SCRATCH_BASE / 'empty', mutate))
        self.assertEqual(codes, ['REGISTRY_EMPTY'])

    def test_a_registry_bound_to_another_version_is_refused(self):
        def mutate(registry, dest):
            registry['schemaVersion'] = 'design-lab/rights-registry/v2'
        codes, _ = outcome(build_scratch(SCRATCH_BASE / 'unbound', mutate))
        self.assertEqual(codes, ['REGISTRY_UNBOUND'])

    def test_unparseable_json_is_refused(self):
        gate = load_gate()
        dest = build_scratch(SCRATCH_BASE / 'broken')
        (dest / gate.REGISTRY_REL).write_text('{not json', encoding='utf-8')
        codes, _ = outcome(dest)
        self.assertEqual(codes, ['REGISTRY_UNREADABLE'])

    def test_a_registry_that_is_not_an_object_is_refused(self):
        gate = load_gate()
        dest = build_scratch(SCRATCH_BASE / 'listform')
        (dest / gate.REGISTRY_REL).write_text('[]', encoding='utf-8')
        codes, _ = outcome(dest)
        self.assertEqual(codes, ['REGISTRY_UNREADABLE'])

    def test_the_shipped_check_is_what_convicts_not_the_scratch_setup(self):
        """Weaken the gate and the same defect walks through -- so the check is load-bearing.

        Without this case, a red mutation could be blamed on the scratch tree and a green one
        on a test that never looked at the gate.
        """
        def mutate(registry, dest):
            registry['entries'][0]['use_restriction'] = 'LITIGATION_HOLD'
        dest = build_scratch(SCRATCH_BASE / 'weakened', mutate)
        weakened = SCRATCH_BASE / 'verify_rights_registry_weakened.py'
        source = GATE_PATH.read_text(encoding='utf-8')
        self.assertIn("            if band == 'UNCLASSIFIED':", source)
        # emit the finding for every OTHER band but never for the unclassified one
        source = source.replace(
            "            if band == 'UNCLASSIFIED':",
            "            if band == 'UNCLASSIFIED' and False:")
        self.assertNotEqual(source, GATE_PATH.read_text(encoding='utf-8'),
                            'the weakened copy changed no bytes -- the anchor is stale')
        weakened.write_text(source, encoding='utf-8')
        try:
            weak = load_gate(weakened)
            findings, _ = weak.scan(dest)
        finally:
            weakened.unlink()
        self.assertEqual([f for f in findings if f.startswith('STATE_UNCLASSIFIED')], [],
                         'a gate that cannot report an unclassified state still reported one')
        strict, _ = load_gate().scan(dest)
        self.assertTrue([f for f in strict if f.startswith('STATE_UNCLASSIFIED')],
                        'the shipped gate must report what the weakened copy let through')


if __name__ == '__main__':
    unittest.main()
