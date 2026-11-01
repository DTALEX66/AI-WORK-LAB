# SPDX-License-Identifier: MIT
"""R3-02: shared resolution must not depend on CWD or permit external writes."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT/'src'))


class ProjectPathsTests(unittest.TestCase):
    def setUp(self):
        from design_lab.runtime.paths import resolve_paths, PathPolicyError
        self.resolve = resolve_paths
        self.error = PathPolicyError
        parent = ROOT/'.project-local/task-runtime/r3-path-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        (self.root/'.project').mkdir()
        (self.root/'AGENTS.md').write_text('# dedicated project fixture', encoding='utf-8')

    def config(self, **values):
        (self.root/'.project/paths.json').write_text(json.dumps({
            'schemaVersion': 'design-lab/project-paths/v1', **values}), encoding='utf-8')

    def test_defaults_separate_transient_persistent_and_model_data(self):
        layout = self.resolve(project_root=self.root, environ={})
        self.assertEqual(layout.runtime_root, self.root/'.project-local/task-runtime')
        self.assertEqual(layout.projects_root, self.root/'.project-local/projects')
        self.assertEqual(layout.model_cache, self.root/'.project-local/cache/models')
        self.assertFalse((self.root/'.project-local').exists())

    def test_doctor_reuses_all_four_owner_declared_external_roots_without_write_permission(self):
        # Missing toolchain roots previously caused repeated install-location guessing.
        layout = self.resolve(project_root=ROOT, environ={})
        expected = {
            'design-assets': 'D:/All projects/Design assets',
            'model-library': 'D:/All projects/Model library',
            'os-toolchain': 'D:/All projects/OS External Configuration',
            'design-toolchain': 'D:/All projects/Design External Configuration',
        }
        observed = layout.describe()['shared_inputs']
        self.assertEqual(set(observed), set(expected))
        for alias, path in expected.items():
            with self.subTest(alias=alias):
                self.assertEqual(observed[alias], {
                    'path': path, 'writable': False, 'status': 'DECLARED_NOT_PROBED'})
                with self.assertRaises(self.error):
                    layout.checked_path(path + '/task-output.json')

    def test_explicit_over_environment_over_config_and_default(self):
        self.config(project_local_root='.project-local/configured')
        layout = self.resolve(project_root=self.root, environ={'PROJECT_LOCAL_ROOT':'.project-local/env'},
                              project_local_root='.project-local/explicit')
        self.assertEqual(layout.local_root, self.root/'.project-local/explicit')
        self.assertEqual(layout.sources['project_local_root'], 'explicit')
        layout = self.resolve(project_root=self.root, environ={'PROJECT_LOCAL_ROOT':'.project-local/env'})
        self.assertEqual(layout.sources['project_local_root'], 'environment:PROJECT_LOCAL_ROOT')
        self.assertEqual(layout.local_root, self.root/'.project-local/env')
        self.assertEqual(self.resolve(project_root=self.root, environ={}).local_root, self.root/'.project-local/configured')

    def test_escaping_and_legacy_roots_are_rejected_without_creation(self):
        for value in ('../escape', '.hermes', 'D:/outside', 'E:/protected', '//host/share',
                      '.project-local/../escape', '.project-local/data:stream', '.project-local/CON'):
            with self.subTest(value=value), self.assertRaises(self.error):
                self.resolve(project_root=self.root, environ={'PROJECT_LOCAL_ROOT':value})
        self.assertFalse((self.root/'.project-local').exists())

    def test_ambient_root_from_the_enclosing_checkout_cannot_relocate_this_project(self):
        """A child inherits PROJECT_LOCAL_ROOT; it names the parent checkout, not us.

        `child_environment()` exports the variable, and CI therefore runs every test with
        the real repository's `.project-local` in its environment. When the caller names a
        project root below that value, honouring the ambient root put this project's
        runtime outside its own owning project -- which is exactly how seven
        `test_audit_trail` cases failed in CI while passing locally.
        """
        enclosing = ROOT/'.project-local'
        self.assertTrue(enclosing in self.root.parents,
                        'the fixture must stay inside this checkout, as CI runs it')
        layout = self.resolve(project_root=self.root,
                              environ={'PROJECT_LOCAL_ROOT': str(enclosing)})
        self.assertEqual(layout.local_root, self.root/'.project-local',
                         'an ambient root from above may not move this project\'s runtime')
        self.assertEqual(layout.sources['project_local_root'], 'default')
        self.assertEqual(layout.sources.get('ambient_project_local_root_ignored'),
                         str(enclosing),
                         'the ignored ambient value must be recorded, not dropped silently')

    def test_ambient_root_from_elsewhere_still_fails_closed(self):
        """The narrow fallback must not become a way to accept an escaping ambient root."""
        for value in ('../escape', 'D:/outside', '.project-local/../escape', '.hermes'):
            with self.subTest(value=value), self.assertRaises(self.error):
                self.resolve(project_root=self.root, environ={'PROJECT_LOCAL_ROOT': value})

    def test_absolute_root_inside_project_is_supported(self):
        target = self.root/'.project-local/selected'
        layout = self.resolve(project_root=self.root, environ={'PROJECT_LOCAL_ROOT':str(target)})
        self.assertEqual(layout.local_root, target)

    def test_unknown_configuration_cannot_silently_redirect_paths(self):
        self.config(project_root='D:/another-project')
        with self.assertRaises(self.error):
            self.resolve(project_root=self.root, environ={})

    def test_directory_reparse_rejected_without_new_pathlib_helpers(self):
        import stat
        from types import SimpleNamespace
        from unittest.mock import patch
        local = self.root / '.project-local'
        local.mkdir()
        original = Path.lstat
        def metadata(path, *args, **kwargs):
            if path == local:
                return SimpleNamespace(st_file_attributes=1024, st_mode=stat.S_IFDIR)
            return original(path, *args, **kwargs)
        with patch.object(Path, 'lstat', metadata):
            with self.assertRaises(self.error):
                self.resolve(project_root=self.root, environ={})

    def test_duplicate_configuration_keys_are_rejected(self):
        (self.root/'.project/paths.json').write_text(
            '{"schemaVersion":"design-lab/project-paths/v1","project_local_root":".project-local",'
            '"project_local_root":".hermes"}', encoding='utf-8')
        with self.assertRaises(self.error):
            self.resolve(project_root=self.root, environ={})

    def test_private_profile_values_are_neither_read_nor_reported(self):
        layout = self.resolve(project_root=self.root, environ={'CODEX_HOME':'PRIVATE_SENTINEL',
                              'HERMES_HOME':'PRIVATE_SENTINEL', 'API_TOKEN':'PRIVATE_SENTINEL'})
        self.assertNotIn('PRIVATE_SENTINEL', json.dumps(layout.describe()))
        self.assertEqual(layout.describe()['agent_profile']['status'], 'PRIVATE_NOT_INSPECTED')

    def test_task_ids_cannot_escape_or_alias_windows_files(self):
        layout = self.resolve(project_root=self.root, environ={})
        for bad in ('../escape', 'a/b', 'x\\y', 'NUL', 'con.txt', 'trail.', 'a:stream', ''):
            with self.subTest(bad=bad), self.assertRaises(self.error):
                layout.task_dir('reconstruction', bad)
        self.assertEqual(layout.task_dir('reconstruction', 'run-1'),
                         self.root/'.project-local/task-runtime/reconstruction/run-1')

    def test_run_id_preserves_existing_128_character_contract_limit(self):
        layout = self.resolve(project_root=self.root, environ={})
        self.assertEqual(layout.task_dir('reconstruction', 'a'*128).name, 'a'*128)
        with self.assertRaises(self.error):
            layout.task_dir('reconstruction', 'a'*129)

    def test_child_temp_and_cache_paths_stay_with_task(self):
        layout = self.resolve(project_root=self.root, environ={})
        env = layout.child_environment('reconstruction', 'run-1')
        task = layout.task_dir('reconstruction', 'run-1')
        self.assertEqual(Path(env['TEMP']), task/'tmp')
        self.assertEqual(env['TMP'], env['TEMP'])
        self.assertEqual(Path(env['HF_HOME']), layout.model_cache/'huggingface')
        self.assertFalse(task.exists())

    def test_doctor_paths_matches_from_repo_and_foreign_cwd(self):
        command = [sys.executable, '-B', str(ROOT/'scripts/design_lab_doctor.py'), '--paths', '--json']
        env = {**os.environ, 'PROJECT_LOCAL_ROOT': str(ROOT/'.project-local')}
        outputs = [subprocess.run(command, cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8')
                   for cwd in (ROOT, self.root)]
        for output in outputs:
            self.assertEqual(output.returncode, 0, output.stderr)
        self.assertEqual(json.loads(outputs[0].stdout), json.loads(outputs[1].stdout))
        self.assertEqual(json.loads(outputs[0].stdout)['roots']['runtime']['path'],
                         (ROOT/'.project-local/task-runtime').as_posix())

    def test_doctor_rejects_outside_override_instead_of_falling_back(self):
        result = subprocess.run([sys.executable, '-B', str(ROOT/'scripts/design_lab_doctor.py'), '--paths', '--json'],
                                cwd=self.root, env={**os.environ, 'PROJECT_LOCAL_ROOT':'../escape'},
                                capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)['status'], 'PATH_POLICY_FAIL')

    def test_reconstruction_uses_same_override_and_validates_run_ids(self):
        code = """
import json, sys
sys.path.insert(0, sys.argv[1])
from reconstruction import runtime_roots as r
print(json.dumps({'runtime': str(r.RUNTIME_PARENT), 'run': r.runtime_root('run-1')}))
try:
    r.runtime_root('../escape')
except ValueError:
    pass
else:
    raise AssertionError('traversal accepted')
"""
        selected = ROOT/'.project-local/task-runtime/r3-path-tests/selected'
        result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT/'packages/capabilities')],
                                cwd=self.root, env={**os.environ, 'PROJECT_LOCAL_ROOT':str(selected)},
                                capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(result.returncode, 0, result.stderr)
        out = json.loads(result.stdout)
        self.assertEqual(Path(out['runtime']), selected/'task-runtime/reconstruction')
        self.assertEqual(out['run'], '.project-local/task-runtime/r3-path-tests/selected/task-runtime/reconstruction/run-1/')

    def test_actual_reconstruction_writes_are_inside_selected_root_from_two_cwds(self):
        # The production atomic writer, not the launcher, performs these writes.
        code = """
import hashlib, json, os, pathlib, sys
sys.path.insert(0, sys.argv[1])
from reconstruction.runtime_roots import RUNTIME_PARENT
from reconstruction.state import atomic_write
trace = []
def audit(event, args):
    paths = []
    if event == 'open' and isinstance(args[0], (str, bytes)):
        mode, flags = args[1], args[2]
        if (isinstance(mode, str) and any(c in mode for c in 'wxa+')) or flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT):
            paths = [os.fsdecode(args[0])]
    elif event in ('os.mkdir', 'os.remove'):
        paths = [os.fsdecode(args[0])]
    elif event == 'os.rename':
        paths = [os.fsdecode(args[0]), os.fsdecode(args[1])]
    for path in paths:
        trace.append({'pid': os.getpid(), 'ppid': os.getppid(), 'event': event, 'path': str(pathlib.Path(path).absolute())})
sys.addaudithook(audit)
run = RUNTIME_PARENT / sys.argv[2]
target = run / 'probe.json'
digest = atomic_write(target, b'{"fixture":true}', run, immutable=True)
assert hashlib.sha256(target.read_bytes()).hexdigest() == digest
print(json.dumps({'trace': trace, 'target': str(target), 'hash': digest}))
"""
        selected = self.root/'.project-local/trace'
        # Explicit roots are anchored to the owning checkout, not fixture project.
        env = {**os.environ, 'PROJECT_LOCAL_ROOT': str(selected)}
        for number, cwd in enumerate((ROOT, self.root)):
            result = subprocess.run([sys.executable, '-B', '-c', code, str(ROOT/'packages/capabilities'), f'run-{number}'],
                                    cwd=cwd, env=env, capture_output=True, text=True, encoding='utf-8')
            self.assertEqual(result.returncode, 0, result.stderr)
            observed = json.loads(result.stdout)
            self.assertGreater(len(observed['trace']), 2)
            self.assertTrue(any(e['event'] == 'os.rename' for e in observed['trace']))
            for event in observed['trace']:
                path = Path(event['path'])
                self.assertTrue(path.is_relative_to(ROOT/'.project-local'), event)
                self.assertTrue(path.is_relative_to(selected) or
                                (event['event'] == 'os.mkdir' and selected.is_relative_to(path)), event)
                self.assertGreater(event['pid'], 0)
            self.assertEqual(Path(observed['target']).read_bytes(), b'{"fixture":true}')
            print('WRITE_TRACE ' + json.dumps(observed, sort_keys=True))


if __name__ == '__main__':
    unittest.main()
