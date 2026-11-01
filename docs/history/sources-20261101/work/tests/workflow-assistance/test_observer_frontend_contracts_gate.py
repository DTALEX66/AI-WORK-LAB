"""Gate: the canonical runner must actually run the front-end suites CI runs, and be able to fail.

Why this module exists: `run_quality_gate.py verify` printed GATE_EXIT=0 twice while the CI `observer`
job went red — once on the legibility micro-role rule in `apps/observer/tests/run_all_tests.js`, once on
a vitest failure in `src/App.behavior.test.tsx`. Registering a gate is not the same as registering a
*working* gate, so every branch here is exercised: registered, present in the verify ordering, PASS,
FAIL, and the named NOT_RUN that a host without the declared runtime must produce instead of skipping.
"""
from __future__ import annotations

import io
import sys
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "services" / "orchestration", ROOT / "apps" / "observer" / "scripts"):
    if str(entry) not in sys.path:
        sys.path.insert(0, str(entry))

import frontend_toolchain as tool  # noqa: E402
import run_quality_gate as gate_runner  # noqa: E402

GATE_NAME = "observer-frontend-contracts"


class RegisteredTests(unittest.TestCase):
    def test_the_gate_is_declared(self) -> None:
        self.assertIn(GATE_NAME, gate_runner.GATES, "the canonical runner does not know this gate")

    def test_the_gate_runs_in_verify_order(self) -> None:
        """A gate nobody schedules is a gate that never fires."""
        scheduled = {name for name in gate_runner.VERIFY_ORDER}
        self.assertIn(GATE_NAME, scheduled, "registered but not scheduled by `verify`")


class VerdictBranchTests(unittest.TestCase):
    def setUp(self) -> None:
        self.node = Path("C:/fake/node.exe")

    def _run(self, js_exit: int, vitest_exit: int) -> tuple[int, str]:
        exits = {"js": js_exit, "vitest": vitest_exit}

        def fake_run(argv, **kwargs):
            key = "js" if str(argv[1]).endswith("run_all_tests.js") else "vitest"
            return mock.Mock(returncode=exits[key], stdout="v22.11.0\n")

        buffer = io.StringIO()
        with mock.patch.object(tool, "find_node", return_value=self.node), \
                mock.patch.object(tool, "env_for", return_value={}), \
                mock.patch.object(tool.subprocess, "run", fake_run):
            with redirect_stdout(buffer):
                code = tool.cmd_contracts(argparse_namespace())
        return code, buffer.getvalue()

    def test_both_suites_green_is_a_pass(self) -> None:
        code, out = self._run(0, 0)
        self.assertEqual(code, 0, out)
        self.assertIn("OBSERVER_FRONTEND_CONTRACTS_PASS", out)

    def test_a_red_vitest_fails_the_gate(self) -> None:
        # This is the branch that would have caught the App.behavior.test.tsx fold failure locally.
        code, out = self._run(0, 1)
        self.assertEqual(code, 1, out)
        self.assertIn("OBSERVER_FRONTEND_CONTRACTS_FAIL", out)
        self.assertIn("vitest=1", out)

    def test_a_red_js_suite_fails_the_gate(self) -> None:
        code, out = self._run(1, 0)
        self.assertEqual(code, 1, out)
        self.assertIn("js=1", out)

    def test_a_host_without_the_declared_runtime_reports_not_run_and_fails(self) -> None:
        buffer = io.StringIO()
        with mock.patch.object(tool, "find_node", side_effect=SystemExit("RESOLVE_FAIL no root")):
            with redirect_stdout(buffer):
                code = tool.cmd_contracts(argparse_namespace())
        out = buffer.getvalue()
        self.assertEqual(code, 1, out)
        self.assertIn("OBSERVER_FRONTEND_CONTRACTS_NOT_RUN", out)
        self.assertIn("RESOLVE_FAIL", out, "the refusal must name why the runtime could not be resolved")

    def test_the_node_version_probe_declares_its_encoding(self) -> None:
        # `--version` output is read into the verdict line; a text pipe without an encoding is the
        # ERR-211 class, and the tree-wide rule that catches it only looks at explicit text= calls.
        source = (ROOT / "apps" / "observer" / "scripts" / "frontend_toolchain.py").read_text(encoding="utf-8")
        self.assertNotIn("capture_output=True, text=True)", source,
                         "a text-mode pipe was added without encoding= and errors=")


def argparse_namespace():
    return mock.Mock()


if __name__ == "__main__":
    unittest.main()
