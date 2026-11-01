# SPDX-License-Identifier: MIT
"""Manifest hashes/shard closure use synthetic bytes, not real model inference."""
import copy
from datetime import datetime, timedelta, timezone
from functools import partial
import hashlib
import json
import os
import subprocess
from pathlib import Path
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))


class ModelManifestTests(unittest.TestCase):
    def setUp(self):
        from unittest.mock import patch
        environment = patch.dict(os.environ, {'PROJECT_LOCAL_ROOT': '.project-local'})
        environment.start()
        self.addCleanup(environment.stop)
        from design_lab.analysis.model_manifest import verify_model_files
        parent = ROOT / '.project-local/task-runtime/model-manifest-tests'
        parent.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(self.temp.cleanup)
        self.project = Path(self.temp.name)
        (self.project / 'AGENTS.md').write_text('Synthetic owning project', encoding='utf-8')
        self.root = self.project / '.project-local/cache/model'
        self.root.mkdir(parents=True)
        self.verify = partial(verify_model_files, project_root=self.project)
        self.manifest = {'schema_version': 'design-lab/model-manifest/v1', 'model_id': 'org/model',
                         'revision': 'a' * 40, 'source': 'synthetic test', 'files': []}
        self.add_file('config.json', b'{}', 'config')
        self.add_file('part1.safetensors', b'first synthetic shard', 'weight')
        self.add_file('part2.safetensors', b'second synthetic shard', 'weight')
        self.add_file('model.safetensors.index.json', json.dumps({'weight_map': {
            'layer1': 'part1.safetensors', 'layer2': 'part2.safetensors'}}).encode(), 'index')

    def add_file(self, name, data, role):
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
        self.manifest['files'].append({'path': name, 'size': len(data), 'sha256': hashlib.sha256(data).hexdigest(), 'role': role})

    def check(self, manifest=None, *, trusted=True):
        manifest = self.manifest if manifest is None else manifest
        registry = self.project / 'design-lab/config/model-manifest-trust.json'
        registry.parent.mkdir(parents=True, exist_ok=True)
        now = datetime.now(timezone.utc)
        approved = {'model_id': manifest['model_id'], 'revision': manifest['revision'],
                    'manifest_sha256': hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest(),
                    'approved_by': 'synthetic-reviewer', 'source': 'synthetic upstream inventory',
                    'observed_at': (now - timedelta(days=1)).isoformat(),
                    'expires_at': (now + timedelta(days=1)).isoformat()}
        registry.write_text(json.dumps({'schema_version': 'design-lab/model-manifest-trust/v1',
                                       'approved': [approved] if trusted else []}), encoding='utf-8')
        return self.verify(self.root, manifest)

    def test_self_authored_manifest_does_not_approve_itself(self):
        r = self.check(trusted=False)
        self.assertEqual(r['state'], 'METADATA_ONLY')
        self.assertIn('MANIFEST_UNTRUSTED', [x['code'] for x in r['issues']])

    def test_manifest_changed_after_approval_is_not_weights_complete(self):
        self.check()
        self.manifest['files'] = self.manifest['files'][1:2]
        r = self.verify(self.root, self.manifest)
        self.assertEqual(r['state'], 'METADATA_ONLY')

    def test_approval_removed_during_hashing_does_not_qualify(self):
        from unittest.mock import patch
        original = Path.open
        def observe(path, *args, **kwargs):
            if path == self.root / 'part1.safetensors':
                registry = self.project / 'design-lab/config/model-manifest-trust.json'
                registry.write_text('{"schema_version":"design-lab/model-manifest-trust/v1","approved":[]}', encoding='utf-8')
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', observe):
            self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_complete_manifest_only_proves_weights_not_load_or_inference(self):
        result = self.check()
        self.assertEqual(result['state'], 'WEIGHTS_COMPLETE')
        self.assertEqual(result['load'], 'NOT_EXECUTED')
        self.assertEqual(result['inference'], 'NOT_EXECUTED')
        self.assertEqual(len(result['verified_files']), 4)

    def test_config_only_cannot_prove_weights(self):
        self.manifest['files'] = self.manifest['files'][:1]
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_missing_or_truncated_shard_blocks(self):
        (self.root / 'part1.safetensors').unlink()
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')
        (self.root / 'part1.safetensors').write_bytes(b'f')
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_same_size_corruption_is_detected_by_full_hash(self):
        path = self.root / 'part2.safetensors'
        data = path.read_bytes()
        path.write_bytes(data[:-1] + b'X')
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_all_index_referenced_shards_must_be_manifest_weights(self):
        self.manifest['files'] = [f for f in self.manifest['files'] if f['path'] != 'part2.safetensors']
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_index_cannot_reference_config_as_weight(self):
        self.manifest['files'][-1]['sha256'] = 'b' * 64
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')
        self.manifest['files'].pop()
        self.add_file('new.index.json', b'{"weight_map":{"layer":"config.json"}}', 'index')
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_duplicate_case_paths_zero_hash_and_unpinned_revision_rejected(self):
        for mutate in ['duplicate', 'zero', 'revision', 'unknown']:
            m = copy.deepcopy(self.manifest)
            if mutate == 'duplicate':
                m['files'].append({**m['files'][1], 'path': 'PART1.safetensors'})
            elif mutate == 'zero':
                m['files'][1]['sha256'] = '0' * 64
            elif mutate == 'revision':
                m['revision'] = 'main'
            else:
                m['permission'] = 'auto'
            self.assertEqual(self.check(m)['state'], 'METADATA_ONLY')

    def test_selectors_checked_before_any_payload_is_opened(self):
        from unittest.mock import patch
        m = copy.deepcopy(self.manifest); m['files'][-1]['path'] = '../outside.json'
        original = Path.open
        opened = []
        def observe(path, *args, **kwargs):
            if path.is_relative_to(self.root):
                opened.append(path)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'open', observe):
            self.assertEqual(self.check(m)['state'], 'METADATA_ONLY')
        self.assertEqual(opened, [])

    def test_missing_directory_is_scoped_absent(self):
        r = self.verify(self.root / 'missing', self.manifest)
        self.assertEqual(r['state'], 'ABSENT')
        self.assertEqual(r['search_scope'], str(self.root / 'missing'))

    def test_real_doctor_cli_does_not_trust_model_local_approval(self):
        self.check()
        (self.root / 'manifest.json').write_text(json.dumps(self.manifest), encoding='utf-8')
        result = subprocess.run([sys.executable, '-B', str(ROOT / 'scripts/design_lab_doctor.py'),
                                 '--model-root', str(self.root), '--model-manifest', 'manifest.json', '--json'],
                                cwd=self.root, capture_output=True, text=True, encoding="utf-8", errors="replace",
                                env={**os.environ, 'PYTHONDONTWRITEBYTECODE': '1', 'PYTHONUTF8': '1'})
        self.assertEqual(result.returncode, 2)
        report = json.loads(result.stdout)
        self.assertEqual(report['state'], 'METADATA_ONLY')
        self.assertIn('MANIFEST_UNTRUSTED', [x['code'] for x in report['issues']])
        self.assertEqual(report['inference'], 'NOT_EXECUTED')

    def test_foreign_private_and_parent_roots_rejected(self):
        for value in ['E:/models', 'C:/Users/ALEX/.cache/huggingface', str(self.root / '..' / 'outside')]:
            with self.assertRaises(ValueError):
                self.verify(Path(value), self.manifest)

    def test_private_manifest_selectors_rejected_before_payload_reads(self):
        for name in ['.env', 'auth.json', 'credentials.json', 'sessions/state.bin']:
            m = copy.deepcopy(self.manifest)
            m['files'][0]['path'] = name
            self.assertEqual(self.check(m)['state'], 'METADATA_ONLY')
            self.assertIn('MANIFEST_INVALID', [x['code'] for x in self.check(m)['issues']])

    def test_hardlinked_payload_is_not_followed(self):
        link = self.root / 'alias.safetensors'
        os.link(self.root / 'part1.safetensors', link)
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_reparse_metadata_is_rejected_without_is_junction_api(self):
        from types import SimpleNamespace
        from unittest.mock import patch
        import stat
        from design_lab.analysis.model_manifest import checked_cache_root
        original = Path.lstat
        def lstat(path, *args, **kwargs):
            if path == self.root:
                return SimpleNamespace(st_file_attributes=stat.FILE_ATTRIBUTE_REPARSE_POINT, st_mode=stat.S_IFDIR)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', lstat):
            with self.assertRaises(ValueError):
                checked_cache_root(self.root, project_root=self.project)

    def test_link_target_private_selector_rejected_before_target_stat(self):
        from unittest.mock import patch
        from design_lab.analysis.model_manifest import _file
        candidate = self.root / 'part1.safetensors'
        original = Path.is_symlink
        with patch.object(Path, 'is_symlink', lambda path: path == candidate or original(path)), \
             patch('design_lab.analysis.model_manifest.os.readlink', return_value='auth.json'):
            with self.assertRaisesRegex(ValueError, 'private'):
                _file(self.root, 'part1.safetensors')

    def test_duplicate_index_keys_rejected_even_when_hash_matches(self):
        self.manifest['files'].pop()
        self.add_file('bad.index.json', b'{"weight_map":{"x":"part1.safetensors","x":"part2.safetensors"}}', 'index')
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')

    def test_budget_failure_is_not_weights_complete(self):
        r = self.verify(self.root, self.manifest, max_total_bytes=3)
        self.assertEqual(r['state'], 'METADATA_ONLY')
        self.assertIn('BYTE_BUDGET', [x['code'] for x in r['issues']])

    def test_read_only_probe_leaves_bytes_and_mtimes_unchanged(self):
        before = {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()}
        self.check()
        self.assertEqual(before, {p.name: (p.read_bytes(), p.stat().st_mtime_ns) for p in self.root.iterdir()})

    def test_cache_symlink_to_own_blob_supported_but_escape_and_broken_rejected(self):
        path = self.root / 'part1.safetensors'
        data = path.read_bytes(); path.unlink()
        blob = self.root / 'blobs/hash'; blob.parent.mkdir(); blob.write_bytes(data)
        try:
            path.symlink_to('blobs/hash')
        except OSError as exc:
            if getattr(exc, 'winerror', None) == 1314:
                self.skipTest('ENVIRONMENT_FAIL: native symlink creation lacks Windows privilege (1314)')
            raise
        self.assertEqual(self.check()['state'], 'WEIGHTS_COMPLETE')
        path.unlink(); path.symlink_to('blobs/missing')
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')
        path.unlink(); path.symlink_to('../outside')
        self.assertEqual(self.check()['state'], 'METADATA_ONLY')


if __name__ == '__main__':
    unittest.main()
