# SPDX-License-Identifier: MIT
"""R3-01: projections must prove freshness and keep evidence axes separate."""
import copy
import hashlib
import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
import subprocess

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


class CurrentReportingTests(unittest.TestCase):
    def setUp(self):
        from design_lab.governance import reporting
        self.reporting = reporting
        runtime = ROOT / '.project-local/task-runtime/r3-reporting-tests'
        runtime.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.write('AGENTS.md', '# isolated report project')
        env_patch = patch.dict(self.reporting.os.environ, {'PROJECT_LOCAL_ROOT':str(self.root/'.project-local')})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.ledger = json.loads((ROOT / 'docs/history/taskpacks/r3-ledger-pre-r5-20260909.json').read_text(encoding='utf-8'))
        self.ledger['evidence'] = []
        for task in self.ledger['tasks']:
            for axis in task['axes'].values():
                axis.update(state='NOT_EXECUTED', evidence=[])
        self.write('design-lab/schemas/task-ledger-r3.schema.json', (ROOT/'design-lab/schemas/task-ledger-r3.schema.json').read_text())
        self.write(self.ledger['plan_path'], '# fixture plan')
        self.write('docs/history/taskpacks/r3-tasks-2026-09-06.json', (ROOT/'docs/history/taskpacks/r3-tasks-2026-09-06.json').read_text(encoding='utf-8'))
        self.write('src/logic.py', 'fixture = 1\n')
        self.write('.project-local/task-artifacts/test.log', 'controlled fixture passed\n')
        self.sha = 'a' * 40

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')

    def evidence(self, kind='local_test'):
        def digest(rel):
            return hashlib.sha256((self.root/rel).read_bytes()).hexdigest()
        receipt = dict(id='verified', kind=kind, outcome='PASS', subject_sha=self.sha,
                       task_ids=['R3-01', 'R3-02', 'R3-05'],
                       binding='WORKTREE_FILES', observed_at='2026-09-06T01:00:00Z', software={'python':'fixture'},
                       subject_files={'src/logic.py': digest('src/logic.py')},
                       artifacts=[{'path':'.project-local/task-artifacts/test.log','sha256':digest('.project-local/task-artifacts/test.log')}], note='test fixture')
        self.ledger['evidence'] = [receipt]
        return receipt

    def qualify(self, task_id='R3-01', **axes):
        task = next(t for t in self.ledger['tasks'] if t['id'] == task_id)
        for name, state in (axes or dict(implementation='IMPLEMENTED_LOCAL', unit='PASS')).items():
            task['axes'][name] = {'state':state, 'evidence':['verified']}

    def project(self):
        return self.reporting.project_ledger(self.root, self.ledger, self.sha)

    def row(self, tid='R3-01'):
        return next(t for t in self.project()['tasks'] if t['id']==tid)

    def test_valid_local_test_qualifies_only_required_local_axes(self):
        self.evidence()
        self.qualify()
        row = self.row()
        self.assertEqual(row['status'], 'DONE_LOCAL')
        self.assertEqual(row['axes']['host_live']['state'], 'NOT_EXECUTED')
        self.assertEqual(row['axes']['delivery']['state'], 'NOT_EXECUTED')

    def test_source_mutation_invalidates_prior_pass(self):
        self.evidence()
        self.qualify()
        self.write('src/logic.py', 'fixture = 2\n')
        row = self.row()
        self.assertEqual(row['axes']['unit']['state'], 'UNVERIFIED')
        self.assertNotEqual(row['status'], 'DONE_LOCAL')

    def test_evidence_for_another_task_cannot_qualify_this_task(self):
        receipt = self.evidence()
        receipt['task_ids'] = ['R3-05']
        self.qualify()
        self.assertEqual(self.row()['axes']['unit']['state'], 'UNVERIFIED')

    def test_rewritten_frozen_source_cannot_be_rebound_by_ledger(self):
        path = 'docs/history/taskpacks/r3-tasks-2026-09-06.json'
        original = json.loads((self.root/path).read_text(encoding='utf-8'))
        original['tasks'][0]['acceptance'] = ['weaker acceptance']
        self.ledger['tasks'][0]['acceptance'] = ['weaker acceptance']
        self.write(path, json.dumps(original))
        self.ledger['source']['tasks_sha256'] = hashlib.sha256((self.root/path).read_bytes()).hexdigest()
        with self.assertRaises(ValueError):
            self.project()

    def test_missing_artifact_does_not_reuse_declared_pass(self):
        receipt = self.evidence()
        receipt['artifacts'][0]['path'] = '.project-local/task-artifacts/missing.log'
        self.qualify()
        self.assertEqual(self.row()['axes']['unit']['state'], 'UNVERIFIED')

    def test_wrong_subject_commit_is_stale(self):
        receipt = self.evidence()
        receipt['subject_sha'] = 'b'*40
        self.qualify()
        self.assertNotEqual(self.row()['status'], 'DONE_LOCAL')

    def test_local_test_cannot_promote_host_or_delivery(self):
        self.evidence()
        self.qualify('R3-02', implementation='IMPLEMENTED_LOCAL', unit='PASS', host_live='PASS', delivery='PASS')
        row = self.row('R3-02')
        self.assertEqual(row['axes']['host_live']['state'], 'UNVERIFIED')
        self.assertEqual(row['axes']['delivery']['state'], 'UNVERIFIED')

    def test_done_axes_still_require_dependencies(self):
        self.evidence()
        self.qualify('R3-05')
        self.assertEqual(self.row('R3-05')['status'], 'PARTIAL')
        self.assertEqual(self.row('R3-05')['unmet_dependencies'], ['R3-01'])

    def test_missing_axes_is_rejected(self):
        del self.ledger['tasks'][0]['axes']['delivery']
        with self.assertRaises(ValueError):
            self.project()

    def test_duplicate_ids_and_unknown_dependencies_rejected(self):
        original = copy.deepcopy(self.ledger)
        self.ledger['tasks'][1]['id'] = self.ledger['tasks'][0]['id']
        with self.assertRaises(ValueError):
            self.project()
        self.ledger = original
        self.ledger['tasks'][0]['depends_on'] = ['nonexistent']
        with self.assertRaises(ValueError):
            self.project()

    def test_cycle_is_rejected(self):
        self.ledger['tasks'][0]['depends_on'] = ['R3-02']
        with self.assertRaises(ValueError):
            self.project()

    def test_private_and_escaping_evidence_paths_rejected(self):
        receipt = self.evidence()
        for path in ('../outside', 'C:/outside', '.env', '.hermes/session.db', '.git/config'):
            receipt['subject_files'] = {path:'a'*64}
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.project()

    def test_workflow_receipt_qualifies_then_expires_when_workflow_changes(self):
        for suffix in ('yml', 'yaml'):
            with self.subTest(suffix=suffix):
                path = f'.github/workflows/check.{suffix}'
                self.write(path, 'on: [push, pull_request]\n')
                receipt = self.evidence()
                receipt['subject_files'] = {
                    path: hashlib.sha256((self.root/path).read_bytes()).hexdigest()
                }
                self.qualify()
                self.assertEqual(self.row()['axes']['unit']['state'], 'PASS')
                self.write(path, 'on: [push]\n')
                self.assertEqual(self.row()['axes']['unit']['state'], 'UNVERIFIED')

    def test_workflow_exception_does_not_allow_other_github_or_private_paths(self):
        receipt = self.evidence()
        for path in ('.github/config.yml', '.github/workflows/auth.json',
                     '.github/workflows/.env.yml', '.github/workflows/run.py',
                     '.github/workflows/nested/check.yml',
                     '.github/workflows/../config.yml'):
            receipt['subject_files'] = {path: 'a'*64}
            with self.subTest(path=path), self.assertRaises(ValueError):
                self.project()

    def test_unknown_evidence_id_is_rejected(self):
        self.qualify()
        with self.assertRaises(ValueError):
            self.project()

    def test_projection_keeps_actual_observation_time(self):
        self.evidence()
        self.qualify()
        self.assertEqual(self.project()['evidence'][0]['observed_at'], '2026-09-06T01:00:00Z')

    def test_project_owned_custom_evidence_root_remains_readable_after_root_switch(self):
        receipt = self.evidence()
        relative = '.project-local/previous/task-artifacts/test.log'
        self.write(relative, 'controlled fixture passed\n')
        receipt['artifacts'][0]['path'] = relative
        self.qualify()
        with patch.dict(self.reporting.os.environ, {'PROJECT_LOCAL_ROOT':str(self.root/'.project-local/next')}):
            self.assertEqual(self.row()['axes']['unit']['state'], 'PASS')

    def test_report_index_covers_generated_project_status_and_detects_tamper(self):
        self.write('design-lab/config/task-ledger-r3.json', json.dumps(self.ledger))
        snapshot = {'sha':self.sha, 'branch':'fixture', 'origin_main':self.sha, 'source_worktree_clean':True, 'tracked_files':0}
        self.reporting.generate(self.root, snapshot=snapshot, generated_at='2026-09-06T02:00:00Z')
        index = json.loads((self.root/'design-lab/config/current-report-index.json').read_text())
        for name in ('PROJECT_STATUS.json','PROJECT_STATUS.md','TASK_PROGRESS.json'):
            self.assertIn(name, index['reports'])
            self.assertTrue((self.root/'reports/current'/name).is_file())
        self.assertEqual(self.reporting.generate(self.root, check=True, snapshot=snapshot), [])
        self.write('reports/current/PROJECT_STATUS.md', 'manual stale content')
        failures = self.reporting.generate(self.root, check=True, snapshot=snapshot)
        self.assertIn('reports/current/PROJECT_STATUS.md', failures)
        self.assertEqual((self.root/'reports/current/PROJECT_STATUS.md').read_text(), 'manual stale content')

    def test_check_missing_output_is_read_only(self):
        self.write('design-lab/config/task-ledger-r3.json', json.dumps(self.ledger))
        self.assertTrue(self.reporting.generate(self.root, check=True, snapshot={'sha':self.sha}))
        self.assertFalse((self.root/'reports/current').exists())

    def test_index_input_digest_is_deterministic_primary_binding(self):
        self.write('design-lab/config/task-ledger-r3.json', json.dumps(self.ledger))
        snapshot = {'sha':self.sha, 'branch':'fixture', 'origin_main':self.sha,
                    'source_worktree_clean':True, 'tracked_files':0}
        self.reporting.generate(self.root, snapshot=snapshot, generated_at='2026-09-06T02:00:00Z')
        index = json.loads((self.root/'design-lab/config/current-report-index.json').read_text())
        self.assertTrue(index['inputDigest'].startswith('sha256:'))
        self.assertEqual(len(index['inputDigest']), len('sha256:') + 64)
        first = index['inputDigest']
        self.reporting.generate(self.root, snapshot=snapshot, generated_at='2026-09-06T02:00:00Z')
        index2 = json.loads((self.root/'design-lab/config/current-report-index.json').read_text())
        self.assertEqual(index2['inputDigest'], first)

    def test_index_input_digest_tracks_inputs_not_git_observation(self):
        self.write('design-lab/config/task-ledger-r3.json', json.dumps(self.ledger))
        snapshot = {'sha':self.sha, 'branch':'fixture', 'origin_main':self.sha,
                    'source_worktree_clean':True, 'tracked_files':0}
        self.reporting.generate(self.root, snapshot=snapshot, generated_at='2026-09-06T02:00:00Z')
        base = json.loads((self.root/'design-lab/config/current-report-index.json').read_text())['inputDigest']
        # A changed generation-time observation (commit SHA) with unchanged inputs
        # must NOT move the primary binding: the SHA is an observation, not a binding.
        snapshot2 = dict(snapshot, sha='b'*40, origin_main='b'*40)
        self.reporting.generate(self.root, snapshot=snapshot2, generated_at='2026-09-06T02:00:00Z')
        after_sha = json.loads((self.root/'design-lab/config/current-report-index.json').read_text())['inputDigest']
        self.assertEqual(after_sha, base)
        # A changed input file MUST move the primary binding.
        self.write(self.ledger['plan_path'], '# changed acceptance input')
        self.reporting.generate(self.root, snapshot=snapshot2, generated_at='2026-09-06T02:00:00Z')
        after_input = json.loads((self.root/'design-lab/config/current-report-index.json').read_text())['inputDigest']
        self.assertNotEqual(after_input, base)

    def test_index_declares_sha_observation_and_digest_primary(self):
        self.write('design-lab/config/task-ledger-r3.json', json.dumps(self.ledger))
        snapshot = {'sha':self.sha, 'branch':'fixture', 'origin_main':self.sha,
                    'source_worktree_clean':True, 'tracked_files':0}
        self.reporting.generate(self.root, snapshot=snapshot, generated_at='2026-09-06T02:00:00Z')
        index = json.loads((self.root/'design-lab/config/current-report-index.json').read_text())
        self.assertIn('observation', index['subjectMeaning'])
        self.assertIn('not a freshness claim', index['subjectMeaning'])  # explicitly NOT a freshness claim
        self.assertIn('CI artifact', index['subjectMeaning'])
        self.assertIn('primary', index['inputDigestMeaning'])

    def test_report_staging_uses_selected_root(self):
        self.write('design-lab/config/task-ledger-r3.json', json.dumps(self.ledger))
        selected = self.root/'.project-local/selected'
        snapshot = {'sha':self.sha, 'branch':'fixture', 'origin_main':self.sha, 'source_worktree_clean':True, 'tracked_files':0}
        with patch.dict(self.reporting.os.environ, {'PROJECT_LOCAL_ROOT':str(selected)}):
            self.reporting.generate(self.root, snapshot=snapshot)
        self.assertTrue((selected/'task-runtime/current-reports').is_dir())
        self.assertFalse((self.root/'.project-local/task-runtime/current-reports').exists())

    def test_host_requirement_cannot_be_removed_from_task(self):
        self.ledger['tasks'][1]['required_axes'] = ['implementation', 'unit']
        with self.assertRaises(ValueError):
            self.project()

    def test_implementation_state_cannot_be_used_for_unit_axis(self):
        self.evidence()
        self.qualify(unit='IMPLEMENTED_LOCAL')
        with self.assertRaises(ValueError):
            self.project()

    def test_acceptance_text_must_match_frozen_task_definition(self):
        self.ledger['tasks'][0]['acceptance'] = ['easier replacement requirement']
        with self.assertRaises(ValueError):
            self.project()

    def test_git_porcelain_leading_space_is_preserved(self):
        result = subprocess.CompletedProcess(['git'], 0, b' M reports/current/PROJECT_STATUS.json\0', b'')
        with patch.object(self.reporting.subprocess, 'run', return_value=result):
            self.assertTrue(self.reporting._git(self.root, 'status').startswith(' M '))

    def test_report_commit_does_not_invalidate_bound_observation(self):
        self.write('design-lab/config/task-ledger-r3.json', json.dumps(self.ledger))
        self.write('.gitignore', '.project-local/\n')
        def git(*args):
            result = subprocess.run(
                ['git', '-c', 'user.name=Report Fixture', '-c',
                 'user.email=fixture@example.invalid', '-c', 'core.autocrlf=false',
                 *args], cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace")
            self.assertEqual(result.returncode, 0, result.stderr)
            return result.stdout.strip()
        git('init')
        git('add', '--', '.')
        git('commit', '-m', 'isolated source')
        observation_sha = git('rev-parse', 'HEAD')
        self.reporting.generate(self.root)
        git('add', '--', 'reports/current', self.reporting.INDEX)
        git('commit', '-m', 'publish observed reports')
        self.assertNotEqual(git('rev-parse', 'HEAD'), observation_sha)
        self.assertEqual(self.reporting.generate(self.root, check=True), [])
        report = json.loads((self.root/'reports/current/PROJECT_STATUS.json').read_text())
        self.assertEqual(report['subjectSha'], observation_sha)
        self.assertEqual(report['gitStateMeaning'], 'generation-time observation, not current HEAD')
        self.write(self.ledger['plan_path'], '# changed acceptance input')
        self.assertTrue(self.reporting.generate(self.root, check=True))


def _load_repo_root_generate():
    """Load scripts/generate_current_reports.py (the FA-03 CLI wrapper)."""
    import importlib.util
    path = ROOT / 'scripts' / 'generate_current_reports.py'
    spec = importlib.util.spec_from_file_location('generate_current_reports', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class Fa03CheckVerdictTests(unittest.TestCase):
    """DL-UCR-012 / FA-03: a byte-stable record whose subject HEAD has advanced
    past is STALE, never laundered into a bare CURRENT_REPORTS=PASS; the record
    identity (subject / manifest / run) is preserved. The exit code stays 0 so the
    zero-spill self-test coupling (which requires the wrapped --check to succeed)
    is not broken; the verdict WORD carries the staleness."""

    def setUp(self):
        self.mod = _load_repo_root_generate()

    def _run_main(self, failures, stored_subject, current_subject, check=True,
                  scope='bound-input-integrity', run='2026-09-13T18:57:37+00:00'):
        import io, contextlib
        # generate() returns the byte-drift list; _index_identity/_current_head
        # supply the record identity; capture stdout for the verdict.
        with patch.object(self.mod, 'generate', return_value=failures), \
             patch.object(self.mod, '_index_identity',
                         return_value=(stored_subject, scope, run)), \
             patch.object(self.mod, '_current_head', return_value=current_subject):
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                code = self.mod.main(['--check'] if check else [])
            return code, buf.getvalue().splitlines()

    def test_same_subject_byte_stable_is_pass(self):
        code, lines = self._run_main([], 'f' * 40, 'f' * 40)
        self.assertEqual(code, 0)
        self.assertIn('CURRENT_REPORTS=PASS mode=check', lines[0])

    def test_stale_subject_byte_stable_is_not_a_pass(self):
        code, lines = self._run_main([], 'a' * 40, 'b' * 40)  # HEAD advanced
        self.assertEqual(code, 0)  # byte-stable inputs; do not break the coupling
        self.assertIn('CURRENT_REPORTS=STALE', lines[0])
        self.assertNotIn('CURRENT_REPORTS=PASS', lines[0])
        # The record identity must be preserved, not laundered away.
        self.assertIn('stored_subject=a' + 'a' * 11, lines[0])
        self.assertIn('current_head=b' + 'b' * 11, lines[0])
        self.assertIn('run_identity=2026-09-13T18:57:37+00:00', lines[0])
        self.assertIn('not a product-pass claim', lines[0])

    def test_drift_still_fails_and_names_the_files(self):
        code, lines = self._run_main(
            ['reports/current/PROJECT_STATUS.json', 'reports/current/PROJECT_STATUS.md'],
            'a' * 40, 'b' * 40)
        self.assertEqual(code, 1)
        self.assertIn('CURRENT_REPORTS=DRIFT', lines[0])
        self.assertIn('reports/current/PROJECT_STATUS.json', lines[0])

    def test_generate_mode_is_unchanged_pass(self):
        code, lines = self._run_main([], 'a' * 40, 'b' * 40, check=False)
        self.assertEqual(code, 0)
        self.assertIn('CURRENT_REPORTS=PASS mode=generate', lines[0])

    def test_qualify_helper_is_pure(self):
        self.assertEqual(self.mod.qualify_check_verdict('x' * 40, 'x' * 40), ('PASS', 0))
        self.assertEqual(self.mod.qualify_check_verdict('a' * 40, 'b' * 40), ('STALE', 0))
        # A missing stored subject cannot claim staleness it did not record.
        self.assertEqual(self.mod.qualify_check_verdict(None, 'b' * 40), ('PASS', 0))


if __name__ == '__main__':
    unittest.main()
class EvidenceBindingBasisTests(unittest.TestCase):
    """A COMMIT receipt is re-checked against the commit it names, never against today's tree.

    Measured 2026-10-08 on the real ledger: the old rule compared a COMMIT receipt's blob digests
    against working-tree bytes and demanded the receipt name the projection's own commit. Both are
    impossible for a row bound to a parent commit, so 0 of 73 receipts were `verified`, no evidence
    axis could ever be promoted, and the flag carried no information. Re-checked on the basis the
    ledger's own `binding` enum declares, 36 of 73 are intact and 2 still describe today's bytes.
    """

    def setUp(self):
        from design_lab.governance import reporting
        self.reporting = reporting
        runtime = ROOT / '.project-local/task-runtime/r3-binding-basis-tests'
        runtime.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=runtime)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        env_patch = patch.dict(self.reporting.os.environ,
                               {'PROJECT_LOCAL_ROOT': str(self.root / '.project-local')})
        env_patch.start()
        self.addCleanup(env_patch.stop)
        self.write('AGENTS.md', '# isolated report project')
        self.ledger = json.loads(
            (ROOT / 'docs/history/taskpacks/r3-ledger-pre-r5-20260909.json').read_text(encoding='utf-8'))
        self.ledger['evidence'] = []
        for task in self.ledger['tasks']:
            for axis in task['axes'].values():
                axis.update(state='NOT_EXECUTED', evidence=[])
        self.write('design-lab/schemas/task-ledger-r3.schema.json',
                   (ROOT / 'design-lab/schemas/task-ledger-r3.schema.json').read_text(encoding='utf-8'))
        self.write(self.ledger['plan_path'], '# fixture plan')
        self.write('docs/history/taskpacks/r3-tasks-2026-09-06.json',
                   (ROOT / 'docs/history/taskpacks/r3-tasks-2026-09-06.json').read_text(encoding='utf-8'))
        self.write('src/logic.py', 'fixture = 1\n')
        self.write('docs/notes.md', '# notes\n')
        self.write('.gitignore', '.project-local/\n__pycache__/\n*.pyc\n')
        self.git('init')
        self.git('add', '--', '.')
        self.git('commit', '-m', 'observation subject')
        self.observed = self.git('rev-parse', 'HEAD')

    def write(self, rel, content):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding='utf-8', newline='\n')

    def write_bytes(self, rel, raw):
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)

    def git(self, *args):
        result = subprocess.run(
            ['git', '-c', 'user.name=Binding Fixture', '-c',
             'user.email=fixture@example.invalid', '-c', 'core.autocrlf=false', *args],
            cwd=self.root, capture_output=True, text=True, encoding='utf-8', errors='replace')
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip()

    def commit_change(self, rel, content, message='later change'):
        self.write(rel, content)
        self.git('add', '--', rel)
        self.git('commit', '-m', message)
        return self.git('rev-parse', 'HEAD')

    def blob(self, rel, sha=None):
        result = subprocess.run(['git', '-C', str(self.root), 'show', f'{sha or self.observed}:{rel}'],
                                capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        return hashlib.sha256(result.stdout).hexdigest()

    def receipt(self, *, binding='COMMIT', subject=None, subject_files=None, artifacts=None):
        subject = subject or self.observed
        claimed = subject_files or {'src/logic.py': self.blob('src/logic.py', subject)}
        listed = artifacts if artifacts is not None else [
            {'path': 'src/logic.py', 'sha256': self.blob('src/logic.py', subject)}]
        row = dict(id='bound', kind='local_test', outcome='PASS', subject_sha=subject,
                   binding=binding, task_ids=['R3-01', 'R3-02', 'R3-05'],
                   observed_at='2026-10-08T00:00:00Z', software={'python': 'fixture'},
                   subject_files=claimed, artifacts=listed, note='fixture')
        self.ledger['evidence'] = [row]
        return row

    def qualify(self, task_id='R3-01'):
        task = next(t for t in self.ledger['tasks'] if t['id'] == task_id)
        for name, state in (('implementation', 'IMPLEMENTED_LOCAL'), ('unit', 'PASS')):
            task['axes'][name] = {'state': state, 'evidence': ['bound']}

    def project(self, subject=None):
        result = self.reporting.project_ledger(self.root, self.ledger, subject or self.head())
        row = next(t for t in result['tasks'] if t['id'] == 'R3-01')
        return result['evidence'][0], row

    def head(self):
        return self.git('rev-parse', 'HEAD')

    def test_a_commit_receipt_verifies_at_a_later_commit_that_did_not_move_the_cited_file(self):
        self.receipt()
        self.qualify()
        head = self.commit_change('docs/notes.md', '# notes\n\nappended\n')
        evidence, row = self.project(head)
        self.assertEqual([], evidence['integrity_reasons'])
        self.assertEqual([], evidence['currency_reasons'])
        self.assertTrue(evidence['verified'])
        self.assertTrue(evidence['current'])
        self.assertNotIn('STALE_SUBJECT_SHA', evidence['reasons'])
        self.assertEqual(row['axes']['unit']['state'], 'PASS')
        self.assertEqual(row['status'], 'DONE_LOCAL')

    def test_a_normalised_working_tree_does_not_convict_a_commit_bound_receipt(self):
        """The real cause of the 2026-10-08 wall of red: CRLF bytes on disk, LF bytes in the blob.

        `design-lab/config/contract-bindings.json` is exactly this file in the product repository --
        its git attributes normalise it -- so every receipt naming it was reported changed while git
        itself called the tree clean.
        """
        self.write('.gitattributes', '*.py text eol=lf\n')
        self.git('add', '--', '.gitattributes')
        self.git('commit', '-m', 'normalise python')
        subject = self.git('rev-parse', 'HEAD')
        self.write_bytes('src/logic.py', b'fixture = 1\r\n')
        self.assertEqual('', self.git('diff', '--name-only', subject, '--', 'src/logic.py'),
                         'git must call this content unchanged, which is the condition under test')
        stored = self.blob('src/logic.py', subject)
        on_disk = hashlib.sha256((self.root / 'src/logic.py').read_bytes()).hexdigest()
        self.assertIn(b'\r\n', (self.root / 'src/logic.py').read_bytes())
        self.assertNotEqual(stored, on_disk, 'the fixture must reproduce blob-vs-worktree divergence')
        self.receipt(subject=subject, subject_files={'src/logic.py': stored},
                     artifacts=[{'path': 'src/logic.py', 'sha256': stored}])
        self.qualify()
        evidence, row = self.project(subject)
        self.assertEqual([], evidence['integrity_reasons'])
        self.assertEqual([], evidence['currency_reasons'])
        self.assertTrue(evidence['verified'], evidence['reasons'])
        self.assertEqual(row['status'], 'DONE_LOCAL')

    def test_a_receipt_about_bytes_that_have_since_moved_is_intact_history_not_current_evidence(self):
        self.receipt()
        self.qualify()
        head = self.commit_change('src/logic.py', 'fixture = 2\n')
        evidence, row = self.project(head)
        self.assertTrue(evidence['verified'], 'the bound commit still holds what the row hashed')
        self.assertFalse(evidence['current'])
        self.assertEqual(['MOVED_SINCE_BOUND_COMMIT:src/logic.py'], evidence['currency_reasons'])
        self.assertEqual(row['axes']['unit']['state'], 'UNVERIFIED')
        self.assertNotEqual(row['status'], 'DONE_LOCAL')

    def test_a_digest_the_bound_commit_never_held_is_named_and_costs_exactly_one_line(self):
        self.receipt(subject_files={'src/logic.py': 'e' * 64},
                     artifacts=[{'path': 'src/logic.py', 'sha256': 'e' * 64}])
        self.qualify()
        evidence, row = self.project()
        self.assertFalse(evidence['verified'])
        self.assertEqual(['DIGEST_NOT_REPRODUCIBLE_AT_BOUND_COMMIT:src/logic.py'],
                         evidence['integrity_reasons'])
        self.assertEqual(row['axes']['unit']['state'], 'UNVERIFIED')

    def test_a_path_that_first_appeared_after_the_bound_commit_is_not_in_it(self):
        self.receipt()
        self.qualify()
        head = self.commit_change('src/added_later.py', 'later = 1\n')
        receipt = self.receipt(
            subject_files={'src/added_later.py': self.blob('src/added_later.py', head)},
            artifacts=[{'path': 'src/added_later.py', 'sha256': self.blob('src/added_later.py', head)}])
        receipt['subject_sha'] = self.observed
        evidence, _row = self.project(head)
        self.assertFalse(evidence['verified'])
        self.assertEqual(['PATH_NOT_IN_BOUND_COMMIT:src/added_later.py'], evidence['integrity_reasons'])

    def test_an_artefact_no_commit_ever_held_is_called_unversioned_not_changed(self):
        cache = 'src/__pycache__/logic.cpython-313.pyc'
        (self.root / 'src/__pycache__').mkdir(parents=True, exist_ok=True)
        (self.root / cache).write_bytes(b'\x00\x0b\x61\x62 derived cache')
        digest = hashlib.sha256((self.root / cache).read_bytes()).hexdigest()
        self.receipt(subject_files={'src/logic.py': self.blob('src/logic.py')},
                     artifacts=[{'path': cache, 'sha256': digest}])
        self.qualify()
        evidence, row = self.project()
        self.assertFalse(evidence['verified'])
        self.assertEqual([f'ARTIFACT_IS_NOT_VERSIONED:{cache}'], evidence['integrity_reasons'])
        self.assertEqual(row['axes']['unit']['state'], 'UNVERIFIED')

    def test_one_path_claimed_with_two_digests_is_a_contradiction_in_the_row(self):
        self.receipt(subject_files={'src/logic.py': self.blob('src/logic.py')},
                     artifacts=[{'path': 'src/logic.py', 'sha256': 'a' * 64}])
        self.qualify()
        evidence, _row = self.project()
        self.assertFalse(evidence['verified'])
        self.assertEqual(['DIGEST_CONFLICT_FOR_SAME_PATH:src/logic.py'], evidence['integrity_reasons'])

    def test_a_runtime_artefact_is_judged_by_this_disk_and_its_absence_still_blocks(self):
        log = '.project-local/task-artifacts/run.log'
        self.write(log, 'controlled fixture passed\n')
        digest = hashlib.sha256((self.root / log).read_bytes()).hexdigest()
        self.receipt(artifacts=[{'path': 'src/logic.py', 'sha256': self.blob('src/logic.py')},
                                {'path': log, 'sha256': digest}])
        self.qualify()
        evidence, row = self.project()
        self.assertTrue(evidence['verified'], evidence['reasons'])
        self.assertEqual(row['axes']['unit']['state'], 'PASS')
        gone = self.receipt(artifacts=[{'path': 'src/logic.py', 'sha256': self.blob('src/logic.py')},
                                       {'path': '.project-local/task-artifacts/never-written.log',
                                        'sha256': digest}])
        self.qualify()
        evidence, row = self.project()
        self.assertFalse(evidence['verified'])
        self.assertEqual(
            ['RUNTIME_ARTIFACT_ABSENT_ON_THIS_MACHINE:.project-local/task-artifacts/never-written.log'],
            evidence['integrity_reasons'])
        self.assertEqual(row['axes']['unit']['state'], 'UNVERIFIED')
        self.assertIsNotNone(gone)

    def test_a_worktree_files_receipt_still_expires_on_a_different_subject(self):
        """The other half of the enum: a row that admits a dirty tree is only ever true of that tree."""
        digest = hashlib.sha256((self.root / 'src/logic.py').read_bytes()).hexdigest()
        self.receipt(binding='WORKTREE_FILES',
                     subject_files={'src/logic.py': digest},
                     artifacts=[{'path': 'src/logic.py', 'sha256': digest}])
        self.qualify()
        head = self.commit_change('docs/notes.md', '# notes\n\nlater\n')
        evidence, row = self.project(head)
        self.assertEqual([], evidence['integrity_reasons'])
        self.assertEqual(['STALE_SUBJECT_SHA'], evidence['currency_reasons'])
        self.assertTrue(evidence['verified'])
        self.assertFalse(evidence['current'])
        self.assertEqual(row['axes']['unit']['state'], 'UNVERIFIED')

    def test_a_locally_modified_cited_file_is_not_evidence_for_the_subject(self):
        self.receipt()
        self.qualify()
        self.write('src/logic.py', 'fixture = 99\n')
        evidence, row = self.project()
        self.assertTrue(evidence['verified'], 'the bound commit is untouched')
        self.assertEqual(['LOCALLY_MODIFIED_SINCE_SUBJECT:src/logic.py'], evidence['currency_reasons'])
        self.assertEqual(row['axes']['unit']['state'], 'UNVERIFIED')


