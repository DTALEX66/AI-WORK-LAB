# SPDX-License-Identifier: MIT
"""Subprocess contract tests; fake version output is not live tool evidence."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'src'))
from design_lab.runtime import doctor


class DoctorEvidenceTests(unittest.TestCase):
    def probe(self, tool='ffmpeg', output='ffmpeg version 7.0 Copyright', code=0, stderr='', error=None):
        with patch.object(doctor, 'EXPECTED', {tool: doctor.EXPECTED[tool]}), \
             patch.object(doctor.shutil, 'which', return_value='D:/fixture/' + tool + '.exe'), \
             patch.object(doctor.subprocess, 'run', side_effect=error,
                          return_value=subprocess.CompletedProcess([], code, output, stderr)) as run:
            status = doctor.probe_tools(bindings={})[0]
        return status, run.call_args

    def test_correct_ffmpeg_flag_and_success_still_not_workflow_verification(self):
        s, call = self.probe()
        self.assertEqual(call.args[0], ['D:/fixture/ffmpeg.exe', '-version'])
        self.assertEqual(s.version_status, 'VERSION_VERIFIED')
        self.assertEqual(s.workflow_status, 'NOT_EXECUTED')
        self.assertEqual(s.plugins_status, 'NOT_EXECUTED')
        self.assertEqual(s.exit_code, 0)

    def test_nonzero_with_version_text_is_failure(self):
        s, _ = self.probe(code=1)
        self.assertTrue(s.found)
        self.assertTrue(s.drift)
        self.assertEqual(s.exit_code, 1)
        self.assertEqual(s.version_status, 'PROBE_FAILED')

    def test_valid_versions_and_old_unknown_versions(self):
        for tool, good, old in [('git', 'git version 2.50.1.windows.1', 'git version 2.39.0'),
                                ('uv', 'uv 0.8.1', 'uv 0.3.0'),
                                ('node', 'v24.1.0', 'v18.0.0'),
                                ('ffmpeg', 'ffmpeg version 7.1-full_build', 'ffmpeg version 5.9')]:
            self.assertFalse(self.probe(tool, good)[0].drift)
            self.assertTrue(self.probe(tool, old)[0].drift)
            self.assertTrue(self.probe(tool, 'error version 99.0')[0].drift)

    def test_empty_stdout_can_use_valid_stderr_but_empty_both_fails(self):
        self.assertFalse(self.probe(output='', stderr='ffmpeg version 7.1')[0].drift)
        self.assertTrue(self.probe(output='')[0].drift)

    def test_packager_domain_and_copyright_are_not_prerelease_markers(self):
        text = 'ffmpeg version 8.1.2-full_build-www.gyan.dev Copyright (c) the FFmpeg developers'
        self.assertFalse(self.probe(output=text)[0].drift)
        for text in ['ffmpeg version 8.1.2-rc1', 'ffmpeg version 8.1.2dev', 'v24.0.0-nightly']:
            tool = 'node' if text.startswith('v') else 'ffmpeg'
            self.assertTrue(self.probe(tool, text)[0].drift)

    def test_missing_is_only_scoped_not_found(self):
        with patch.object(doctor.shutil, 'which', return_value=None), patch.object(doctor.subprocess, 'run') as run:
            statuses = doctor.probe_tools(bindings={})
        self.assertTrue(all(s.version_status == 'NOT_FOUND_IN_SEARCH_SCOPE' for s in statuses))
        self.assertTrue(all(s.search_scope for s in statuses))
        self.assertFalse(run.called)

    def test_timeout_and_start_failure_are_reported_without_crash(self):
        for error in [subprocess.TimeoutExpired('fixture', 8), PermissionError('fixture denied')]:
            status, _ = self.probe(error=error)
            self.assertTrue(status.drift)
            self.assertNotEqual(status.version_status, 'VERSION_VERIFIED')

    def test_cli_failure_is_nonzero_and_json_retains_provenance(self):
        s, _ = self.probe(code=1)
        output = io.StringIO()
        with patch.object(doctor, 'probe_tools', return_value=[s]), redirect_stdout(output):
            self.assertEqual(doctor.main(['--json']), 1)
        row = json.loads(output.getvalue())[0]
        self.assertEqual(row['path'], 'D:/fixture/ffmpeg.exe')
        self.assertEqual(row['path_source'], 'shutil.which')
        self.assertEqual(row['exit_code'], 1)

    def test_lock_probe_uses_owning_project_cwd_and_missing_is_not_pass(self):
        with patch.object(doctor.shutil, 'which', return_value='D:/fixture/uv.exe'), \
             patch.object(doctor.subprocess, 'run', return_value=subprocess.CompletedProcess([], 1, '', 'error')) as run:
            self.assertTrue(doctor.check_uv_lock())
        self.assertEqual(run.call_args.kwargs['cwd'], ROOT)
        with patch.object(doctor.shutil, 'which', return_value=None):
            self.assertTrue(doctor.check_uv_lock())


if __name__ == '__main__':
    unittest.main()
