# SPDX-License-Identifier: MIT
"""Synthetic receipts test selection policy, not live host qualification."""
import copy
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.runtime.profile_resolver import resolve
NOW = datetime(2026, 9, 6, 12, tzinfo=timezone.utc)
CONTEXT = {'repo_sha': 'a' * 40, 'os': 'Windows-test', 'versions': {
    k: {'host': '1', 'adapter': '2'} for k in ['photoshop', 'minimax-h3', 'other']}}


class ProfileEvidenceTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-artifacts/profile-resolver-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.artifact = Path(self.temp.name) / 'fixture.json'
        self.artifact.write_bytes(b'{"synthetic":true}\n')
        self.ref = {'path': self.artifact.relative_to(ROOT).as_posix(),
                    'sha256': hashlib.sha256(self.artifact.read_bytes()).hexdigest()}

    def profile(self, pid='photoshop', fmt='psd', kind='host'):
        return {'id': pid, 'kind': kind, 'default_enabled': True, 'evidence': {
            'schema_version': 'design-lab/profile-evidence/v1', 'profile_id': pid,
            'repo_sha': 'a' * 40, 'os': 'Windows-test', 'host_version': '1', 'adapter_version': '2',
            'level': 'E2', 'observed_at': '2026-09-06T11:00:00Z', 'expires_at': '2026-09-06T13:00:00Z',
            'launch': 'PASS', 'capabilities': [{'format': fmt, 'operation': 'export', 'editable': True, 'offline': True}],
            'conditions': {key: {'status': 'PASS', 'source': 'synthetic-test', 'receipt': self.ref.copy(),
                                'observed_at': '2026-09-06T11:00:00Z', 'expires_at': '2026-09-06T13:00:00Z'}
                           for key in ['license', 'region', 'resources', 'dependencies']},
            'purposes': ['PERSONAL_RESEARCH_NONCOMMERCIAL'], 'regions': ['TEST'],
            'fixture': self.ref.copy(), 'artifact': self.ref.copy(), 'readback': 'PASS',
            'rollback': 'PASS', 'action': 'synthetic export and reopen',
            'model_sha256': 'b' * 64 if kind == 'model' else None}}

    def run_resolver(self, profiles=None, **request):
        return resolve({'format': 'psd', 'region': 'TEST', **request},
                       catalog={'schema_version': 'design-lab/profiles/v1', 'profiles': profiles or [self.profile()]},
                       context=CONTEXT, now=NOW, project_root=ROOT)

    def codes(self, result):
        return {b['code'] for r in result['rejected'] for b in r['blockers']}

    def test_current_scoped_evidence_selects_but_does_not_authorize_execution(self):
        r = self.run_resolver(offline=True, editable=True)
        self.assertEqual(r['selected'], 'photoshop')
        self.assertEqual(r['purpose'], 'PERSONAL_RESEARCH_NONCOMMERCIAL')
        self.assertEqual(r['ranked'][0]['score'], 100)
        self.assertFalse(r['execution_authorized'])

    def test_missing_evidence_retains_manual_candidate_and_steps(self):
        p = self.profile(); p['evidence'] = None
        r = self.run_resolver([p], manual_profile='photoshop')
        self.assertIsNone(r['selected'])
        self.assertIn('EVIDENCE_MISSING', self.codes(r))
        self.assertEqual(r['manual']['profile'], 'photoshop')
        self.assertFalse(r['manual']['qualified'])
        self.assertTrue(r['manual']['validation_steps'])

    def test_each_denied_or_unknown_condition_blocks_separately(self):
        for key in ['license', 'region', 'resources', 'dependencies']:
            for status in ['DENIED', 'UNKNOWN']:
                with self.subTest(key=key, status=status):
                    p = self.profile(); p['evidence']['conditions'][key]['status'] = status
                    r = self.run_resolver([p], manual_profile='photoshop')
                    self.assertIsNone(r['selected'])
                    self.assertIn(key.upper() + '_' + status, self.codes(r))

    def test_launch_readback_rollback_and_declared_level_fail_closed(self):
        for key, value, code in [('launch', 'DENIED', 'LAUNCH_DENIED'), ('readback', 'UNKNOWN', 'READBACK_UNKNOWN'),
                                 ('rollback', 'DENIED', 'ROLLBACK_DENIED'), ('level', 'E0', 'UNTESTED')]:
            p = self.profile(); p['evidence'][key] = value
            r = self.run_resolver([p])
            self.assertIsNone(r['selected'])
            self.assertIn(code, self.codes(r))

    def test_expired_future_and_invalid_timestamps_block(self):
        for key, value in [('expires_at', '2026-09-06T12:00:00Z'), ('observed_at', '2026-09-07T12:00:00Z'),
                           ('expires_at', '2026-09-06T13:00:00'), ('expires_at', 'nonsense')]:
            p = self.profile(); p['evidence'][key] = value
            self.assertIsNone(self.run_resolver([p])['selected'])

    def test_binding_rejects_other_version_os_sha_or_profile(self):
        for key in ['repo_sha', 'os', 'host_version', 'adapter_version', 'profile_id']:
            p = self.profile(); p['evidence'][key] = 'f' * 40
            self.assertIsNone(self.run_resolver([p])['selected'])

    def test_capability_is_per_format_and_operation(self):
        p = self.profile()
        p['evidence']['capabilities'] = [
            {'format': 'psd', 'operation': 'export', 'editable': False, 'offline': False},
            {'format': 'svg', 'operation': 'export', 'editable': True, 'offline': True}]
        for request in [{'editable': True}, {'offline': True}, {'operation': 'import'}, {'format': 'cdr'}]:
            self.assertIsNone(self.run_resolver([p], **request)['selected'])

    def test_personal_use_does_not_grant_commercial_or_other_region(self):
        for request in [{'rights': 'COMMERCIAL'}, {'region': 'OTHER'}, {'region': None}]:
            self.assertIsNone(self.run_resolver(**request)['selected'])

    def test_h3_personal_use_is_condition_based_not_permanent_ban(self):
        p = self.profile('minimax-h3', 'mp4', 'model'); p['model_sha256'] = 'b' * 64
        self.assertEqual(self.run_resolver([p], format='mp4')['selected'], 'minimax-h3')
        p['evidence']['conditions']['resources']['status'] = 'DENIED'
        self.assertIn('RESOURCES_DENIED', self.codes(self.run_resolver([p], format='mp4')))

    def test_disabled_missing_or_mismatching_model_hash_blocks(self):
        for digest in [None, '0' * 64, 'c' * 64]:
            p = self.profile('minimax-h3', 'mp4', 'model'); p['model_sha256'] = digest
            self.assertIsNone(self.run_resolver([p], format='mp4')['selected'])
        p = self.profile(); p['default_enabled'] = False
        self.assertIsNone(self.run_resolver([p], manual_profile='photoshop')['selected'])

    def test_tampered_missing_and_outside_artifacts_block(self):
        self.artifact.write_bytes(b'changed')
        self.assertIsNone(self.run_resolver()['selected'])
        self.artifact.unlink()
        self.assertIsNone(self.run_resolver()['selected'])
        for path in ['E:/private.json', '../private.json', '.project-local/private.json',
                     '.project-local/task-artifacts/.env', 'C:/Users/ALEX/.codex/memories/MEMORY.md']:
            p = self.profile(); p['evidence']['fixture']['path'] = path
            self.assertIsNone(self.run_resolver([p])['selected'])

    def test_configured_preferences_and_deterministic_ties(self):
        a = self.profile(); b = self.profile('other')
        b['preference'] = {'score': 99, 'source': 'test preference',
                           'observed_at': '2026-09-06T11:00:00Z', 'expires_at': '2026-09-06T13:00:00Z'}
        self.assertEqual(self.run_resolver([b, a])['selected'], 'photoshop')
        b.pop('preference')
        self.assertEqual(self.run_resolver([a, b])['selected'], 'other')
        self.assertEqual(self.run_resolver([a, b]), self.run_resolver([b, a]))
        b['evidence']['launch'] = 'DENIED'
        self.assertEqual(self.run_resolver([b, a])['selected'], 'photoshop')

    def test_expired_preference_not_used_manual_never_falls_back(self):
        p = self.profile(); p['preference'] = {'score': 1, 'source': 'test preference',
                'observed_at': '2026-09-06T10:00:00Z', 'expires_at': '2026-09-06T11:00:00Z'}
        self.assertEqual(self.run_resolver([p])['ranked'][0]['score'], 100)
        self.assertIsNone(self.run_resolver(manual_profile='missing')['selected'])

    def test_invalid_request_and_duplicate_profiles_fail_closed(self):
        for value in ['false', 1, None]:
            with self.assertRaises(ValueError):
                self.run_resolver(offline=value)
        p = self.profile()
        with self.assertRaises(ValueError):
            self.run_resolver([p, copy.deepcopy(p)])

    def test_missing_context_does_not_infer_current_host(self):
        r = resolve({'format': 'psd'}, catalog={'schema_version': 'design-lab/profiles/v1',
                    'profiles': [self.profile()]}, now=NOW, project_root=ROOT)
        self.assertIsNone(r['selected'])

    def test_independently_expired_condition_is_not_refreshed_by_new_probe(self):
        for key in ['license', 'region', 'resources', 'dependencies']:
            p = self.profile()
            p['evidence']['conditions'][key]['expires_at'] = '2026-09-06T11:30:00Z'
            r = self.run_resolver([p])
            self.assertIsNone(r['selected'])
            self.assertIn(key.upper() + '_EXPIRED_OR_FUTURE', self.codes(r))

    def test_resource_request_requires_measured_capacity(self):
        p = self.profile()
        p['evidence']['resource_capacity'] = {'vram_mb': 8192, 'ram_mb': 16384}
        self.assertEqual(self.run_resolver([p], resources={'vram_mb': 4096})['selected'], 'photoshop')
        for needs in [{'vram_mb': 8193}, {'disk_mb': 1}]:
            r = self.run_resolver([p], resources=needs)
            self.assertIsNone(r['selected'])
            self.assertIn('RESOURCE_CAPACITY', self.codes(r))

    def test_invalid_numeric_resource_request_does_not_become_zero(self):
        for value in [-1, True, float('nan'), float('inf'), '4096']:
            with self.assertRaises(ValueError):
                self.run_resolver(resources={'vram_mb': value})

    def test_editable_and_offline_must_hold_in_same_test(self):
        p = self.profile()
        p['evidence']['capabilities'] = [
            {'format': 'psd', 'operation': 'export', 'editable': False, 'offline': True},
            {'format': 'psd', 'operation': 'export', 'editable': True, 'offline': False}]
        self.assertIsNone(self.run_resolver([p], offline=True, editable=True)['selected'])

    def test_resolver_does_not_mutate_input(self):
        p = self.profile(); original = copy.deepcopy(p)
        self.run_resolver([p])
        self.assertEqual(p, original)

    def test_changed_license_receipt_blocks_while_output_stays_valid(self):
        p = self.profile()
        p['evidence']['conditions']['license']['receipt']['sha256'] = 'c' * 64
        self.assertIn('LICENSE_RECEIPT_INVALID', self.codes(self.run_resolver([p])))

    def test_unknown_record_fields_are_not_silently_trusted(self):
        p = self.profile(); p['evidence']['unrecognized_permission'] = True
        self.assertIn('EVIDENCE_INVALID', self.codes(self.run_resolver([p])))

    def test_native_artifacts_are_not_rejected_by_filename_suffix(self):
        for suffix in ['.cdr', '.psb', '.eps', '.fig', '.blend']:
            with self.subTest(suffix=suffix):
                native = self.artifact.with_suffix(suffix)
                native.write_bytes(b'synthetic native container')
                p = self.profile(fmt=suffix[1:])
                p['evidence']['artifact'] = {'path': native.relative_to(ROOT).as_posix(),
                    'sha256': hashlib.sha256(native.read_bytes()).hexdigest()}
                self.assertEqual(self.run_resolver([p], format=suffix[1:])['selected'], 'photoshop')

    def test_nonfinite_receipt_number_is_invalid_without_resource_request(self):
        p = self.profile(); p['evidence']['resource_capacity'] = {'vram_mb': float('nan')}
        self.assertIn('EVIDENCE_INVALID', self.codes(self.run_resolver([p])))


if __name__ == '__main__':
    unittest.main()
