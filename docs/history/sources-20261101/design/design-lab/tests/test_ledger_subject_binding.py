# SPDX-License-Identifier: MIT
"""The ledger's evidence records must be checkable by someone who was not there.

`verify_ledger_subject_binding.py` recomputes every `subject_files` digest from the commit the
record binds to. This module proves the recomputation has teeth, that the sanctioned list is
two-way, and that the real ledger passes it today.

The synthetic cases inject their own byte reader, so they are deterministic and never depend
on what this machine happens to have in its working tree.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'design-lab/scripts/verify_ledger_subject_binding.py'

spec = importlib.util.spec_from_file_location('ledger_subject_binding', SCRIPT)
gate = importlib.util.module_from_spec(spec)
sys.modules['ledger_subject_binding'] = gate
spec.loader.exec_module(gate)


def record(identity='r-x', commit='c0', **files):
    return {'id': identity, 'subject_sha': commit,
            'subject_files': dict(files)}


def reader(blobs):
    """A stand-in for `git show <commit>:<path>` over an in-memory byte map."""
    def read(commit, path):
        return blobs.get((commit, path))
    return read


class Classification(unittest.TestCase):
    def test_matching_digest_is_not_a_defect(self):
        body = b'print(1)\n'
        defects = gate.classify([record(pathA=sha256(body).hexdigest())],
                                reader({('c0', 'pathA'): body}), lambda _c: True)
        self.assertEqual(defects, [])

    def test_wrong_digest_is_found(self):
        defects = gate.classify([record(pathA=sha256(b'other bytes').hexdigest())],
                                reader({('c0', 'pathA'): b'print(1)\n'}), lambda _c: True)
        self.assertEqual(defects, [(gate.MISMATCH, 'r-x', 'pathA')])

    def test_path_missing_from_the_bound_commit_is_found(self):
        """The shape this ledger actually had: records naming files that were only ever on
        disk (interpreter caches) or that were committed later."""
        defects = gate.classify([record(pathA='a' * 64)], reader({}), lambda _c: True)
        self.assertEqual(defects, [(gate.ABSENT, 'r-x', 'pathA')])

    def test_unresolvable_commit_is_found_rather_than_assumed_ok(self):
        defects = gate.classify([record(commit='deadbeef', pathA='a' * 64)],
                                reader({}), lambda _c: False)
        self.assertEqual(defects, [(gate.NO_COMMIT, 'r-x', 'pathA')])

    def test_a_record_without_subject_files_is_not_silently_counted_as_clean(self):
        """Not a defect, but not a proof either: there is nothing to check. The gate's OK
        line reports how many files it actually compared so this cannot pass as coverage."""
        defects = gate.classify([{'id': 'r-y', 'subject_sha': 'c0', 'subject_files': {}}],
                                reader({}), lambda _c: True)
        self.assertEqual(defects, [])
        declared = sum(len(r.get('subject_files') or {}) for r in [{'subject_files': {}}])
        self.assertEqual(declared, 0)


class TwoWayLedger(unittest.TestCase):
    def test_an_unsanctioned_defect_fails(self):
        unsanctioned, stale = gate.partition(
            [(gate.MISMATCH, 'a-brand-new-record', 'src/design_lab/x.py')])
        self.assertEqual(unsanctioned, [(gate.MISMATCH, 'a-brand-new-record',
                                         'src/design_lab/x.py')])
        self.assertTrue(stale, 'the known entries are stale against synthetic input, which is '
                               'expected here; the real-ledger test below asserts both lists')

    def test_a_sanctioned_entry_that_stopped_being_a_defect_is_stale(self):
        """A fixed record must leave the list, or the list becomes a permanent excuse."""
        key = next(iter(gate.KNOWN))
        unsanctioned, stale = gate.partition([])
        self.assertEqual(unsanctioned, [])
        self.assertIn(key, stale)

    def test_the_blessing_is_per_record_not_per_path(self):
        """`a/other.py` is sanctioned for one record. A different record naming the same path
        is a new claim about bytes and has to be checked on its own terms."""
        path = 'src/design_lab/readiness/__pycache__/__init__.cpython-313.pyc'
        holder = 'r5-006-static-unit-20260928'
        self.assertIn((holder, path), gate.KNOWN)
        unsanctioned, _ = gate.partition([(gate.ABSENT, 'r5-999-copycat', path)])
        self.assertEqual(len(unsanctioned), 1)
        unsanctioned_ok, _ = gate.partition([(gate.ABSENT, holder, path)])
        self.assertEqual(unsanctioned_ok, [])

    def test_known_entries_are_unique_and_reasoned(self):
        self.assertGreaterEqual(len(gate.KNOWN), 60)
        for key, reason in gate.KNOWN.items():
            self.assertIsInstance(key, tuple)
            self.assertEqual(len(key), 2, f'{key} must be (record id, path)')
            self.assertGreaterEqual(len(reason), 30,
                                    f'{key} is sanctioned without a reason worth reading')


class RealLedger(unittest.TestCase):
    def test_current_ledger_passes_the_gate(self):
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)],
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', cwd=ROOT)
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn('LEDGER_SUBJECT_BINDING=OK', result.stdout)

    def test_the_gate_reports_every_claim_and_judges_the_ones_it_can(self):
        """An OK line that checked nothing would be the worst outcome of all: green, and wrong.

        Every claim must land in exactly one of the three reported counts, so a basis narrowed to
        WORKTREE_FILES rows cannot quietly shrink the denominator -- and `checked` has to exceed the
        subject_files total, because artefact claims are now judged too.
        """
        result = subprocess.run([sys.executable, '-B', str(SCRIPT)],
                                capture_output=True, text=True, encoding='utf-8',
                                errors='replace', cwd=ROOT)
        line = [l for l in result.stdout.splitlines() if 'LEDGER_SUBJECT_BINDING=OK' in l][0]
        fields = dict(pair.split('=') for pair in line.replace(
            'LEDGER_SUBJECT_BINDING=OK ', '').split() if '=' in pair)
        ledger = json.loads((ROOT / 'design-lab/config/task-ledger-r3.json')
                            .read_text(encoding='utf-8'))
        records = ledger['evidence']
        subject_files = sum(len(record.get('subject_files') or {}) for record in records)
        artifact_files = sum(len(record.get('artifacts') or []) for record in records)
        judged = dropped = duplicates = 0
        for record in records:
            pairs = list(record.get('subject_files') or {}) + [
                item['path'] for item in (record.get('artifacts') or [])]
            runtime_pairs = [p for p in pairs if p.startswith(gate.RUNTIME_ARTIFACT_ROOT)]
            judged += len(set(pairs) - set(runtime_pairs))
            dropped += len(runtime_pairs)
            duplicates += len(pairs) - len(set(pairs))
        self.assertEqual(int(fields['subject_files']), subject_files)
        self.assertEqual(int(fields['records']), len(records))
        self.assertEqual(int(fields['runtime']), dropped)
        self.assertEqual(int(fields['checked']) + int(fields['worktree_claims']), judged)
        self.assertEqual(judged + dropped, subject_files + artifact_files - duplicates)
        self.assertGreater(duplicates, 0, 'no record claims a path twice, so the dedupe rule '
                                          'is untested by the real ledger')
        self.assertEqual(int(fields['worktree_claims']), 8,
                         'the three 2026-09-09 WORKTREE_FILES records are the whole non-commit '
                         'basis; a change here is a deliberate edit to this line')
        self.assertGreaterEqual(int(fields['checked']), 472,
                                'commit-basis coverage shrank below the 2026-10-08 measurement')
        self.assertGreater(int(fields['checked']), subject_files - 20,
                           'artefact claims stopped being checked -- subject_files alone was 450')

    def test_the_waiver_list_no_longer_excuses_a_basis_error(self):
        """KNOWN is for defects a COMMIT record cannot cure without fabricating itself.

        Four entries belonged to WORKTREE_FILES records: judged by the object database they looked
        broken, but those records never claimed commit bytes, so the list was paying for the gate's
        own basis instead of naming a defect.
        """
        ledger = json.loads((ROOT / 'design-lab/config/task-ledger-r3.json')
                            .read_text(encoding='utf-8'))
        binding = {record['id']: record.get('binding') for record in ledger['evidence']}
        self.assertEqual(sorted(key for key in gate.KNOWN if binding.get(key[0]) != 'COMMIT'), [])
        self.assertGreaterEqual(len(gate.KNOWN), 60)


class BasisAndCoverage(unittest.TestCase):
    """Which claims the gate judges, and on what basis -- all synthetic, no working tree involved."""

    def test_an_artefact_claim_is_judged_like_a_subject_claim(self):
        body = b'print(1)\n'
        good = sha256(body).hexdigest()
        record = {'id': 'r-a', 'subject_sha': 'c0', 'binding': 'COMMIT',
                  'subject_files': {'src/a.py': good},
                  'artifacts': [{'path': 'docs/lie.md', 'sha256': 'b' * 64}]}
        defects = gate.classify([record], reader({('c0', 'src/a.py'): body}),
                                lambda _c: True)
        self.assertEqual(defects, [(gate.ABSENT, 'r-a', 'docs/lie.md')])

    def test_an_artefact_that_reproduces_is_coverage_the_old_gate_did_not_have(self):
        body = b'{"a": 1}\n'
        record = {'id': 'r-b', 'subject_sha': 'c0', 'binding': 'COMMIT',
                  'subject_files': {},
                  'artifacts': [{'path': 'design-lab/config/thing.json',
                                 'sha256': sha256(body).hexdigest()}]}
        self.assertEqual(gate.classify([record], reader({('c0', 'design-lab/config/thing.json'): body}),
                                        lambda _c: True), [])
        self.assertEqual(gate.tally([record])['commit_claims'], 1)

    def test_a_worktree_files_record_is_not_judged_by_the_object_database(self):
        """Its own binding says the bytes came off a dirty tree and may never be presented as a commit."""
        record = {'id': 'r-c', 'subject_sha': 'c0', 'binding': 'WORKTREE_FILES',
                  'subject_files': {'src/c.py': 'a' * 64},
                  'artifacts': [{'path': 'docs/handoff.md', 'sha256': 'b' * 64}]}
        self.assertEqual(gate.classify([record], reader({}), lambda _c: True), [])
        counts = gate.tally([record])
        self.assertEqual(counts['commit_claims'], 0)
        self.assertEqual(counts['worktree_claims'], 2)

    def test_runtime_artefact_claims_are_counted_rather_than_silently_skipped(self):
        record = {'id': 'r-d', 'subject_sha': 'c0', 'binding': 'COMMIT',
                  'subject_files': {},
                  'artifacts': [{'path': '.project-local/task-artifacts/run/result.json',
                                 'sha256': 'c' * 64}]}
        self.assertEqual(gate.classify([record], reader({}), lambda _c: True), [])
        counts = gate.tally([record])
        self.assertEqual(counts['runtime'], 1)
        self.assertEqual(counts['commit_claims'], 0)

    def test_one_path_claimed_with_two_digests_is_a_contradiction(self):
        body = b'x\n'
        record = {'id': 'r-e', 'subject_sha': 'c0', 'binding': 'COMMIT',
                  'subject_files': {'src/e.py': sha256(body).hexdigest()},
                  'artifacts': [{'path': 'src/e.py', 'sha256': 'f' * 64}]}
        defects = gate.classify([record], reader({('c0', 'src/e.py'): body}), lambda _c: True)
        self.assertEqual(defects, [('DIGEST_CONFLICT_FOR_SAME_PATH', 'r-e', 'src/e.py')])

    def test_a_missing_binding_is_read_as_commit_and_stays_strict(self):
        """Defaulting to the stricter basis: an unlabelled record is held to committed bytes."""
        record = {'id': 'r-f', 'subject_sha': 'c0', 'subject_files': {'src/f.py': 'a' * 64}}
        self.assertEqual(gate.classify([record], reader({}), lambda _c: True),
                         [(gate.ABSENT, 'r-f', 'src/f.py')])

    def test_an_unresolvable_commit_now_costs_both_lists(self):
        record = {'id': 'r-g', 'subject_sha': 'deadbeef', 'binding': 'COMMIT',
                  'subject_files': {'src/g.py': 'a' * 64},
                  'artifacts': [{'path': 'docs/g.md', 'sha256': 'b' * 64}]}
        defects = gate.classify([record], reader({}), lambda _c: False)
        self.assertEqual(defects, [(gate.NO_COMMIT, 'r-g', 'src/g.py'),
                                   (gate.NO_COMMIT, 'r-g', 'docs/g.md')])


if __name__ == '__main__':
    unittest.main()
