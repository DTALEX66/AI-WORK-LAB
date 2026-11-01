# SPDX-License-Identifier: MIT
"""Real test entries must own temp/cache writes and reject zero-test success."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
ENTRIES = ('scripts/run_python_tests.py', 'design-lab/scripts/run_test_isolation.py')

# Execute each actual main with a tiny dedicated test directory. Discovery and
# unittest execution remain real; do not recursively invoke the full repo suite.
DRIVER = r'''
import importlib.util, json, os, pathlib, sys, tempfile
entry, fixture, stale, observation, *args = sys.argv[1:]
tempfile.tempdir = stale
keys = ('TEMP','TMP','TMPDIR','XDG_CACHE_HOME','HF_HOME','TORCH_HOME','PROJECT_LOCAL_ROOT','PYTHONDONTWRITEBYTECODE')
before = {key:os.environ.get(key) for key in keys}
spec = importlib.util.spec_from_file_location('entry_under_test', entry)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
module.TEST_DIR = pathlib.Path(fixture)
os.environ['DESIGN_TEST_OBSERVATION'] = observation
sys.argv = [entry, *args]
code = module.main()
print('ENTRY_RESULT '+json.dumps({'code':code,'environment_restored':before=={key:os.environ.get(key) for key in keys},'tempfile_restored':tempfile.tempdir==stale}))
raise SystemExit(code)
'''

FIXTURE = r'''
import json, os, pathlib, subprocess, sys, tempfile, unittest
class DedicatedProbe(unittest.TestCase):
    def test_real_temp_and_child(self):
        handle = tempfile.NamedTemporaryFile(delete=False)
        handle.write(b'owned entry fixture')
        handle.close()
        child = subprocess.run([sys.executable,'-B','-c',
            'import json,tempfile; f=tempfile.NamedTemporaryFile(delete=False); f.write(b"child fixture"); f.close(); print(json.dumps({"path":f.name}))'],
            capture_output=True, text=True, encoding="utf-8", errors="replace", check=True)
        observed = {'file':handle.name,'child_file':json.loads(child.stdout)['path'],
                    'tempfile':tempfile.gettempdir(),
                    'environment':{key:os.environ[key] for key in ('TEMP','TMP','TMPDIR','XDG_CACHE_HOME','HF_HOME','TORCH_HOME')},
                    'bytecode_disabled':sys.dont_write_bytecode}
        pathlib.Path(os.environ['DESIGN_TEST_OBSERVATION']).write_text(json.dumps(observed),encoding='utf-8')
        EXPECTED_RESULT
'''


class TestEntryEnvironmentTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT/'.project-local/task-runtime/test-entry-regression'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name)
        self.stale = self.base/'stale-temp'
        self.stale.mkdir()
        self.cases = 0

    def run_entry(self, entry, *, failing=False, empty=False, arguments=(), override=None):
        self.cases += 1
        fixture = self.base/f'fixture-{self.cases}'
        fixture.mkdir()
        if not empty:
            (fixture/'test_owned_probe.py').write_text(FIXTURE.replace(
                'EXPECTED_RESULT', "self.fail('intentional fixture failure')" if failing else 'self.assertTrue(True)'), encoding='utf-8')
        observation = fixture/'observation.json'
        selected = self.base/'.project-local/selected'
        environment = {**os.environ, 'PROJECT_LOCAL_ROOT':str(selected) if override is None else override,
                       'TEMP':str(self.stale), 'TMP':str(self.stale), 'TMPDIR':str(self.stale), 'PYTHONUTF8':'1',
                       'XDG_CACHE_HOME':str(self.stale), 'HF_HOME':str(self.stale), 'TORCH_HOME':str(self.stale)}
        result = subprocess.run([sys.executable, '-B', '-c', DRIVER, str(ROOT/entry), str(fixture),
                                 str(self.stale), str(observation), *arguments],
                                cwd=fixture, env=environment, capture_output=True,
                                text=True, encoding='utf-8', timeout=25)
        return result, observation, selected

    def assert_owned(self, result, observation, selected, expected_code):
        self.assertEqual(result.returncode, expected_code, result.stdout+result.stderr)
        self.assertTrue(observation.is_file(), result.stdout+result.stderr)
        observed = json.loads(observation.read_text(encoding='utf-8'))
        for key in ('file','child_file','tempfile'):
            self.assertTrue(Path(observed[key]).is_relative_to(selected), (key, observed[key]))
        for value in observed['environment'].values():
            self.assertTrue(Path(value).is_relative_to(selected), value)
            self.assertTrue(Path(value).is_dir(), value)
        self.assertEqual(Path(observed['file']).read_bytes(), b'owned entry fixture')
        self.assertEqual(Path(observed['child_file']).read_bytes(), b'child fixture')
        summary = json.loads(next(line.removeprefix('ENTRY_RESULT ') for line in result.stdout.splitlines() if line.startswith('ENTRY_RESULT ')))
        self.assertTrue(summary['environment_restored'])
        self.assertTrue(summary['tempfile_restored'])
        self.assertTrue(observed['bytecode_disabled'])
        self.assertFalse(list(observation.parent.glob('__pycache__/*')))

    def test_root_entry_owns_temp_cache_and_child_writes_despite_cached_tempdir(self):
        self.assert_owned(*self.run_entry(ENTRIES[0]), expected_code=0)

    def test_isolation_entry_owns_temp_cache_and_child_writes_despite_cached_tempdir(self):
        self.assert_owned(*self.run_entry(ENTRIES[1]), expected_code=0)

    def test_failing_suite_stays_nonzero_and_restores_environment(self):
        for entry in ENTRIES:
            with self.subTest(entry=entry):
                self.assert_owned(*self.run_entry(entry, failing=True), expected_code=1)

    def test_no_discovered_cases_cannot_report_success(self):
        for entry in ENTRIES:
            with self.subTest(entry=entry):
                result, _, _ = self.run_entry(entry, empty=True)
                self.assertEqual(result.returncode, 2, result.stdout+result.stderr)

    def test_unmatched_module_filter_cannot_report_success(self):
        result, observation, _ = self.run_entry(ENTRIES[1], arguments=('--modules','test_not_present'))
        self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
        self.assertFalse(observation.exists())

    def test_invalid_runtime_root_stops_before_running_tests(self):
        for entry in ENTRIES:
            with self.subTest(entry=entry):
                result, observation, _ = self.run_entry(entry, override='.hermes')
                self.assertEqual(result.returncode, 2, result.stdout+result.stderr)
                self.assertFalse(observation.exists())


if __name__ == '__main__':
    unittest.main()
