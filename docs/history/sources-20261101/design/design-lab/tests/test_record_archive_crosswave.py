# SPDX-License-Identifier: MIT
"""Teeth for design-lab/scripts/verify_record_archive_crosswave.py.

The register it guards is the pointer layer over every tracked archive/source manifest under
`docs/`: which archived material two or more waves both claim, and where the committed bytes
actually are. Four ways that go quietly wrong, and each is driven here with a planted fault:

* a reader that only understands one manifest shape reports a smaller census, and a smaller census
  says "no overlap" about material it never looked at;
* a census whose population is a hand-kept tuple drifts behind the repository: the first cut of
  this register listed the six manifests under `docs/history` and missed the two in
  `docs/taskpacks`, which hid 175 member rows and one genuine cross-wave claim. The enumeration
  guard is tested in both directions here;
* a canonical path that no longer carries the digest it names would send a migration to the wrong
  file, so every `canonicalPaths` entry is re-hashed from the committed blob in these tests;
* a verdict that is unconditional passes on an empty population, so the floors and the drift check
  are each shown red.
"""
from __future__ import annotations

import importlib.util
import io
import json
import contextlib
import hashlib
import pathlib
import subprocess
import unittest

from unittest import mock

REPO = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = REPO / 'design-lab' / 'scripts' / 'verify_record_archive_crosswave.py'
REGISTER = REPO / 'design-lab' / 'config' / 'record-archive-crosswave.json'


def load_module():
    spec = importlib.util.spec_from_file_location('crosswave_under_test', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    import sys
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


MODULE = load_module()


def invoke(module, argv):
    buffer = io.StringIO()
    old_argv = list(__import__('sys').argv)
    __import__('sys').argv = [str(SCRIPT)] + argv
    try:
        with contextlib.redirect_stdout(buffer):
            code = module.main()
    finally:
        __import__('sys').argv = old_argv
    return code, buffer.getvalue().strip()


class ShippedRegisterTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.document = json.loads(REGISTER.read_text(encoding='utf-8'))

    def test_the_shipped_register_reproduces_from_its_own_inputs(self):
        code, out = invoke(MODULE, ['--check'])
        self.assertEqual(code, 0, out)
        self.assertIn('CROSSWAVE=OK', out)

    def test_every_canonical_path_really_carries_the_digest_it_is_credited_with(self):
        """The register's whole value is that a digest points at bytes; re-hash every one of them."""
        checked = 0
        for entry in self.document['crossWave']:
            self.assertGreaterEqual(len({c['manifest'] for c in entry['claimedBy']}), 2,
                                    'a listed cross-wave member is claimed by one wave only')
            self.assertTrue(entry['canonicalPaths'],
                            'an in-clone entry with no path: %s' % entry['sha256'][:12])
            for path in entry['canonicalPaths']:
                blob = subprocess.run(['git', 'cat-file', 'blob', 'HEAD:' + path],
                                      cwd=str(REPO), capture_output=True, check=True).stdout
                self.assertEqual(hashlib.sha256(blob).hexdigest(), entry['sha256'],
                                 '%s does not carry the digest the register credits it with' % path)
                checked += 1
        self.assertGreaterEqual(checked, 30,
                                'only %d canonical paths were re-hashed; the census has shrunk'
                                % checked)

    def test_the_register_carries_no_absolute_path_from_the_owner_volume(self):
        text = REGISTER.read_text(encoding='utf-8')
        self.assertNotIn('D:\\', text)
        self.assertNotIn('D:/', text)
        self.assertNotIn('C:\\', text)

    def test_a_wave_that_declares_a_member_is_listed_with_what_it_pointed_at(self):
        for entry in self.document['crossWave'] + self.document['crossWaveOutsideClone']:
            for claim in entry['claimedBy']:
                self.assertIn('pointsAt', claim,
                              'a claim without its own pointer is not a cross-wave fact: %s'
                              % entry['sha256'][:12])

    def test_the_outside_clone_half_says_what_it_means(self):
        self.assertIn('crossWaveOutsideCloneMeans', self.document)
        self.assertGreaterEqual(self.document['counts']['crossWaveWithoutBytesInClone'], 1,
                                'the outside-clone half went empty, so the register now hides the '
                                'material a migration has to fetch by digest')

    def test_the_census_covers_every_tracked_manifest_not_one_directory(self):
        """Positive control for the guard: the shipped scope must be the whole population."""
        self.assertEqual(MODULE.manifest_enumeration_problems(), [])
        discovered = MODULE.discover_manifests()
        self.assertGreaterEqual(len(discovered), 8,
                                'only %d manifests enumerated -- a tracked wave is invisible again'
                                % len(discovered))
        roots = {path.split('/')[1] for path in discovered}
        self.assertIn('taskpacks', roots,
                      'every censused wave sits under docs/history, which is how the two '
                      'docs/taskpacks waves got missed the first time')
        self.assertEqual(sorted(discovered), sorted(MODULE.MANIFESTS))


class PlantedFaultsAreConvicted(unittest.TestCase):
    def test_a_reader_that_only_knows_one_shape_is_convicted(self):
        document = {'source_files': [{'sha256': 'a' * 64, 'source_relative': 'x.md', 'bytes': 3}],
                    'members': [{'sha256': 'd' * 64, 'landingPath': 'docs/taskpacks/p/z.md',
                                 'bytes': 11, 'archiveName': 'p/z.md'}],
                    'packages': [{'source': 'C:/somewhere/p.zip',
                                  'members': [{'sha256': 'b' * 64, 'member': 'p/y.md',
                                               'repository_text': 'docs/history/y.md'}]}]}
        rows = MODULE.members_of(document)
        self.assertEqual(len(rows), 3, 'one of the three shapes was not read: %s' % rows)
        digests = [MODULE.claim_of('m', pkg, row) for pkg, row in rows]
        self.assertEqual(sorted(d[0] for d in digests if d),
                         sorted(['a' * 64, 'b' * 64, 'd' * 64]))
        claims = {d[0]: d[1] for d in digests if d}
        self.assertEqual(claims['d' * 64]['pointsAt'], 'docs/taskpacks/p/z.md',
                         'a wave that names its tracked copy as `landingPath` would be registered '
                         'with no pointer at all')
        self.assertEqual(claims['d' * 64]['insidePackage'], 'p/z.md')

    def test_a_wave_on_disk_that_the_tuple_does_not_declare_is_convicted(self):
        """The exact defect the first cut shipped: a manifest nobody added to MANIFESTS."""
        extra = sorted(list(MODULE.discover_manifests())
                       + ['docs/taskpacks/2026-99-99-fake/SOURCE-MANIFEST.json'])
        with mock.patch.object(MODULE, 'discover_manifests', return_value=extra):
            code, out = invoke(MODULE, ['--check'])
        self.assertEqual(code, 1, out)
        self.assertIn('MANIFEST_NOT_CENSUSED', out)

    def test_a_declared_manifest_that_is_no_longer_on_disk_is_convicted(self):
        short = MODULE.discover_manifests()[1:]
        with mock.patch.object(MODULE, 'discover_manifests', return_value=short):
            code, out = invoke(MODULE, ['--check'])
        self.assertEqual(code, 1, out)
        self.assertIn('MANIFEST_DECLARED_BUT_ABSENT', out)

    def test_a_member_row_without_a_digest_is_not_counted_as_a_claim(self):
        self.assertIsNone(MODULE.claim_of('m', None, {'source_relative': 'z.md', 'bytes': 9}))

    def test_the_package_is_recorded_by_name_not_by_the_owner_absolute_path(self):
        _digest, claim = MODULE.claim_of(
            'm', {'source': 'D:\\All projects\\Record\\包.zip'},
            {'sha256': 'c' * 64, 'member': 'in.zip'})
        self.assertEqual(claim['package'], '包.zip')
        self.assertNotIn('D:', json.dumps(claim, ensure_ascii=False))

    def test_the_population_floors_fire_on_a_census_that_stopped_seeing(self):
        base = MODULE.build()
        for field, value, verdict in (
                ('trackedFilesScanned', 12, 'TRACKED_POPULATION'),
                ('distinctDigests', 4, 'DIGEST_POPULATION'),
                ('crossWaveDigests', 2, 'CROSSWAVE_POPULATION')):
            doctored = json.loads(json.dumps(base))
            doctored['counts'][field] = value
            with mock.patch.object(MODULE, 'build', return_value=doctored):
                code, out = invoke(MODULE, ['--check'])
            self.assertEqual(code, 1, '%s passed with %s=%s' % (verdict, field, value))
            self.assertIn(verdict, out)

    def test_a_split_that_does_not_add_up_is_convicted(self):
        doctored = json.loads(json.dumps(MODULE.build()))
        doctored['counts']['crossWaveWithBytesInClone'] = 1
        with mock.patch.object(MODULE, 'build', return_value=doctored):
            code, out = invoke(MODULE, ['--check'])
        self.assertEqual(code, 1, out)
        self.assertIn('CROSSWAVE_SPLIT_DOES_NOT_ADD_UP', out)

    def test_a_register_that_no_longer_matches_its_inputs_reports_the_field(self):
        import tempfile
        real = MODULE.build()
        mutated = json.loads(json.dumps(real))
        mutated['counts']['declaredMemberRows'] += 7
        with tempfile.TemporaryDirectory(dir=REPO / '.project-local/task-runtime') as tmp:
            moved = pathlib.Path(tmp) / 'crosswave.json'
            moved.write_text(json.dumps(real, ensure_ascii=False, indent=2) + '\n',
                             encoding='utf-8', newline='\n')
            with mock.patch.object(MODULE, 'REGISTER', moved), \
                    mock.patch.object(MODULE, 'build', return_value=mutated):
                code, out = invoke(MODULE, ['--check'])
            self.assertEqual(code, 1, out)
            self.assertIn('DRIFT', out)
            self.assertIn('counts', out)

    def test_a_missing_register_is_a_failure_not_a_pass(self):
        missing = REPO / 'design-lab' / 'config' / 'definitely-not-a-register.json'
        with mock.patch.object(MODULE, 'REGISTER', missing):
            code, out = invoke(MODULE, ['--check'])
        self.assertEqual(code, 1, out)
        self.assertIn('REGISTER_ABSENT', out)

    def test_write_refuses_while_a_population_guard_is_firing(self):
        doctored = json.loads(json.dumps(MODULE.build()))
        doctored['counts']['manifests'] = 2
        with mock.patch.object(MODULE, 'build', return_value=doctored):
            code, out = invoke(MODULE, ['--write'])
        self.assertEqual(code, 1, out)
        self.assertIn('REFUSE MANIFEST_POPULATION 2', out)


if __name__ == '__main__':
    unittest.main()
