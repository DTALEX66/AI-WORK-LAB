# SPDX-License-Identifier: MIT
"""Preflight must consult the declared tool roots that `.project/paths.json` registers.

`doctor.probe_tools` already lets a registered binding win over the PATH scan, for the
concrete reason recorded in its own comment: node and ffmpeg are installed under the
declared toolchain root yet were reported NOT_FOUND because neither is on PATH. The task
-resource probe did not do the same, so the two resolvers of one fact disagreed -- while
`/api/task-preflight` is documented as "the same preflight the CLI doctor uses, so
workbench and CLI can never disagree". These tests pin the agreement, and pin the limits:
a binding that is not BOUND, or whose file is gone, must NOT buy a READY.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))

from design_lab.runtime.task_resources import _probe_tool, preflight  # noqa: E402

TASK = 'DL-TEST::T-TOOL'
REGISTRY = {
    'schemaVersion': 'design-lab/task-resources/v1',
    'resources': {'tool-node': {'kind': 'tool', 'name': 'node', 'version': '>=20'}},
    'tasks': {TASK: ['tool-node']},
}


def _binding(path: str, status: str = 'BOUND') -> dict:
    return {'tools': {'node': {'path': path, 'owner': 'os-toolchain', 'status': status}}}


class DeclaredBindingProbeTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = Path(self.tmp.name) / 'node.exe'
        self.exe.write_bytes(b'#!/bin/sh\n')

    def test_a_bound_declared_path_resolves_when_path_does_not_contain_it(self):
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('node', '>=20', _binding(str(self.exe))['tools'])
        self.assertEqual(record['state'], 'RESOLVED')
        self.assertEqual(record['resolved_path'], str(self.exe))
        self.assertTrue(record['path_source'].startswith('declared:.project/paths.json#tools.'))
        self.assertEqual(record['search_scope'], 'declared binding, then current process PATH')

    def test_path_still_wins_when_nothing_is_registered(self):
        with patch('design_lab.runtime.task_resources.shutil.which', return_value='/usr/bin/node'):
            record = _probe_tool('node', '>=20', None)
        self.assertEqual(record['state'], 'RESOLVED')
        self.assertEqual(record['path_source'], 'shutil.which')
        self.assertNotIn('declared_binding_state', record)

    def test_a_bound_path_that_no_longer_exists_does_not_buy_ready(self):
        gone = str(Path(self.tmp.name) / 'moved-away.exe')
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('node', '>=20', _binding(gone)['tools'])
        self.assertEqual(record['state'], 'UNAVAILABLE')
        self.assertIsNone(record['resolved_path'])
        self.assertEqual(record['declared_binding_state'], 'BOUND_PATH_NOW_MISSING')

    def test_a_binding_outside_every_declared_root_is_never_executed(self):
        # tool_bindings() only grants BOUND to paths inside a declared shared root; a
        # caller that handed us some other status must not get to resolve through it.
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('node', '>=20',
                                 _binding(str(self.exe), status='DECLARED_OUTSIDE_SHARED_ROOT')['tools'])
        self.assertEqual(record['state'], 'UNAVAILABLE')
        self.assertEqual(record['declared_binding_state'], 'DECLARED_OUTSIDE_SHARED_ROOT')

    def test_probe_without_bindings_is_the_old_path_only_behaviour(self):
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('node', '>=20')
        self.assertEqual(
            {k: record[k] for k in ('state', 'resolved_path', 'path_source', 'search_scope')},
            {'state': 'UNAVAILABLE', 'resolved_path': None, 'path_source': None,
             'search_scope': 'current process PATH only'})


class PreflightVerdictTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.exe = Path(self.tmp.name) / 'node.exe'
        self.exe.write_bytes(b'#!/bin/sh\n')

    def _verdict(self, bindings):
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            return preflight(Path(self.tmp.name), TASK, registry=REGISTRY,
                             paths_describe=bindings)

    def test_the_task_verdict_follows_the_declared_binding(self):
        blocked = self._verdict(None)
        self.assertEqual(blocked['verdict'], 'BLOCKED')
        self.assertEqual(blocked['blocked_resources'], ['tool-node'])

        ready = self._verdict(_binding(str(self.exe)))
        self.assertEqual(ready['verdict'], 'READY')
        self.assertEqual(ready['blocked_resources'], [])
        self.assertNotEqual(blocked['verdict'], ready['verdict'],
                            'the two runs must not be indistinguishable')

    def test_an_unusable_binding_leaves_the_verdict_blocked(self):
        result = self._verdict(_binding(str(Path(self.tmp.name) / 'absent.exe')))
        self.assertEqual(result['verdict'], 'BLOCKED')
        self.assertEqual(result['resources'][0]['declared_binding_state'],
                         'BOUND_PATH_NOW_MISSING')


class ProjectVenvResolutionTests(unittest.TestCase):
    """`python-project-venv` declares its source as the project venv; the probe must answer
    that declaration without any machine-specific absolute path being written anywhere."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def _make(self, layout):
        exe = self.root / layout
        exe.parent.mkdir(parents=True, exist_ok=True)
        exe.write_bytes(b'')
        return exe

    def test_windows_venv_layout_resolves_when_path_misses(self):
        self._make('.venv/Scripts/python.exe')
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('python', '>=3.11', None, root=self.root,
                                 resolution='project-venv')
        self.assertEqual(record['state'], 'RESOLVED')
        self.assertIn('.venv/Scripts/python.exe', record['resolved_path'].replace('\\', '/'))
        self.assertEqual(record['path_source'], 'project-venv:.venv')

    def test_posix_venv_layout_resolves_when_path_misses(self):
        self._make('.venv/bin/python')
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('python', '>=3.11', None, root=self.root,
                                 resolution='project-venv')
        self.assertEqual(record['state'], 'RESOLVED')

    def test_no_venv_falls_through_to_path_rather_than_claiming_one(self):
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('python', '>=3.11', None, root=self.root,
                                 resolution='project-venv')
        self.assertEqual(record['state'], 'UNAVAILABLE')
        self.assertIsNone(record['resolved_path'])

    def test_a_non_venv_resource_never_borrows_the_venv_answer(self):
        self._make('.venv/Scripts/python.exe')
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('python', '>=3.11', None, root=self.root, resolution=None)
        self.assertEqual(record['state'], 'UNAVAILABLE')

    def test_a_registered_binding_outranks_the_venv(self):
        bound = self._make('elsewhere/python.exe')
        self._make('.venv/Scripts/python.exe')
        with patch('design_lab.runtime.task_resources.shutil.which', return_value=None):
            record = _probe_tool('python', '>=3.11', {'python': {'path': str(bound),
                                                                 'status': 'BOUND'}},
                                 root=self.root, resolution='project-venv')
        self.assertEqual(record['path_source'], 'declared:.project/paths.json#tools.python')


class RegistryWiringTests(unittest.TestCase):
    def test_the_declared_source_is_actually_declared(self):
        """The venv answer only applies to an entry that says so; if the registry entry
        loses its `resolution`, the probe silently reverts to PATH and the task goes
        BLOCKED again -- so pin the wiring, not just the mechanism."""
        registry = json.loads((ROOT / 'design-lab/config/task-resources.json')
                              .read_text(encoding='utf-8'))
        entry = registry['resources']['python-project-venv']
        self.assertEqual(entry.get('resolution'), 'project-venv')
        self.assertEqual(entry.get('name'), 'python')


if __name__ == '__main__':
    unittest.main()
