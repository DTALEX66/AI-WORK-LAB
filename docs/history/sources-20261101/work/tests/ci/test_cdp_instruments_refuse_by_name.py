"""CL-14 (2026-10-25): the CDP instruments the observer job now requires must also be reachable locally.

`scripts/ci/verify_ci_check_reachability.py` exists because `verify_blueprint_coverage.py` ran only in CI and
turned two pushed heads red while the local gate printed PASS on the same tree -- a writer cannot see a rule
only the runner enforces. When this round wired `display_scaling_via_cdp.py`, `sse_revision_via_cdp.py` and
`control_shell_identity_via_cdp.py` into the `observer` job, that checker named all three CI-ONLY, so this
module is their local route.

It tests the refusal, not the pass: an instrument that is wired into CI has to fail *loudly* when its own
preconditions are missing, because a silent green on a machine with no bundle or no browser is how a required
gate stops meaning anything. The happy paths are measured separately with receipts
(`.project-local/runs/cl15/cdp-wire/` on 2026-10-25: `DISPLAY_SCALING_GATE_PASS`, `SSE_REVISION_GATE_PASS`,
`CONTROL_SHELL_IDENTITY_PASS screens=3/3`).
"""
from __future__ import annotations

import contextlib
import importlib.util
import io
import subprocess
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
import project_temp  # noqa: E402


def run_script(relative: str, *arguments: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(ROOT / relative), *arguments],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


class CdpRefusalTests(unittest.TestCase):
    def test_display_scaling_refuses_by_name_when_the_bundle_is_absent(self) -> None:
        empty = Path(project_temp.fixture_dir(prefix="cdp-nodist-"))
        proc = run_script("scripts/audit/display_scaling_via_cdp.py",
                          "--root", str(empty), "--json-out", str(empty / "r.json"))
        self.assertEqual(3, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("DISPLAY_SCALING_GATE_NOT_RUN DIST_ABSENT", proc.stdout, proc.stdout)

    def test_sse_revision_refuses_by_name_when_the_bundle_is_absent(self) -> None:
        empty = Path(project_temp.fixture_dir(prefix="cdp-nodist-sse-"))
        proc = run_script("scripts/audit/sse_revision_via_cdp.py",
                          "--root", str(empty), "--json-out", str(empty / "r.json"))
        self.assertEqual(3, proc.returncode, proc.stdout + proc.stderr)
        self.assertIn("SSE_REVISION_GATE_NOT_RUN DIST_ABSENT", proc.stdout, proc.stdout)

    def test_control_shell_refuses_by_name_when_no_browser_can_be_found(self) -> None:
        """The real stack runs up to the browser step; only the browser is taken away.

        The plane, the loopback server and the one accepted write are the instrument's own, so this exercises
        the branch the CI job would hit on a runner with no Chrome and no Edge -- it has to exit 3 with the
        reason in its name rather than report an empty success.
        """
        spec = importlib.util.spec_from_file_location(
            "control_shell_identity_under_test", ROOT / "scripts" / "audit" / "control_shell_identity_via_cdp.py")
        self.assertIsNotNone(spec)
        module = importlib.util.module_from_spec(spec)
        assert spec.loader is not None
        spec.loader.exec_module(module)
        stdout = io.StringIO()
        with patch.object(module.gate, "find_browser", return_value=None), \
                patch.object(sys, "argv", ["control_shell_identity_via_cdp.py"]), \
                contextlib.redirect_stdout(stdout):
            code = module.main()
        out = stdout.getvalue()
        self.assertEqual(3, code, out)
        self.assertIn("SHELL_EVIDENCE_NOT_RUN BROWSER_NOT_FOUND", out, out)
        self.assertIn("CONTROL_SERVING url=http://127.0.0.1:", out, "the refusal must come after the real write")


if __name__ == "__main__":
    unittest.main(verbosity=2)
