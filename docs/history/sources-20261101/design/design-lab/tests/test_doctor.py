# SPDX-License-Identifier: MIT
"""DL-TP-R2-016: doctor tests."""
from __future__ import annotations
import sys, unittest
from pathlib import Path
SRC = Path(__file__).resolve().parents[2] / 'src'
sys.path.insert(0, str(SRC))


class DoctorTests(unittest.TestCase):
    def test_probe_git_found(self):
        from design_lab.runtime.doctor import probe_tools
        st = {s.tool: s for s in probe_tools()}
        self.assertIn('git', st)
        self.assertTrue(st['git'].found)  # git exists in this environment

    def test_drift_field_present(self):
        from design_lab.runtime.doctor import probe_tools
        for s in probe_tools():
            self.assertIsInstance(s.drift, list)


class DoctorTaskPreflightTests(unittest.TestCase):
    """`doctor --task` died on every input until the owner audit at 2026-10-26 found it.

    `main()` imported `resolve_paths` locally in its `--paths` branch, which makes that name local to
    the whole function, so the `--task` branch reading it first raised `UnboundLocalError` -- on a
    valid id and on an invalid one alike. Nothing exercised `--task`, so the crash was invisible to
    the suite. These two cases are the agreed formats: a refusal naming the expected shape, and a
    verdict that parses as JSON.
    """

    @staticmethod
    def _run(argv):
        import contextlib
        import io
        import json

        from design_lab.runtime.doctor import main
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = main(argv)
        return code, json.loads(buf.getvalue())

    def test_a_malformed_task_id_returns_the_agreed_refusal(self) -> None:
        code, payload = self._run(['--task', 'nonexistent', '--json'])
        self.assertEqual(code, 2, payload)
        self.assertEqual(payload['status'], 'TASK_PREFLIGHT_FAIL')
        self.assertIn('TASKPACK', payload['reason'],
                      'the refusal no longer names the shape it expects, so an operator cannot fix '
                      'the input from the output')

    def test_a_wellformed_task_id_returns_a_verdict_not_a_traceback(self) -> None:
        code, payload = self._run(['--task', 'DL-TP-20261023-DESKTOP-KB-R1::T01', '--json'])
        # The success envelope is the contract object, which carries no `status` key -- that word
        # belongs to the refusal path only. What matters here is that the branch produced the
        # contracted shape instead of an exception, which is exactly what the audit found missing.
        self.assertEqual(payload['schemaVersion'], 'design-lab/task-resource-preflight/v1', payload)
        self.assertEqual(payload['task_full_id'], 'DL-TP-20261023-DESKTOP-KB-R1::T01')
        self.assertEqual(payload['taskpack_id'], 'DL-TP-20261023-DESKTOP-KB-R1')
        self.assertEqual(payload['task_key'], 'T01')
        self.assertIn('resources', payload)
        self.assertIn(code, (0, 2), 'the exit code must track the verdict, not crash either way')

    def test_the_paths_branch_still_answers_after_the_shadowing_was_removed(self) -> None:
        code, payload = self._run(['--paths', '--json'])
        self.assertIn(payload['status'], ('PATHS_RESOLVED', 'PATH_POLICY_FAIL'), payload)
        self.assertEqual(code, 0 if payload['status'] == 'PATHS_RESOLVED' else 2)


if __name__ == '__main__':
    unittest.main()
