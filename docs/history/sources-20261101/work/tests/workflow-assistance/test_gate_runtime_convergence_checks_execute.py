"""Gate: every runtime-convergence check must actually run, not just exist.

Why this file exists: `packages/client-neutral-core/scripts/verify_gate_runtime_convergence.py` carries
ten `check_N()` functions, and three of them were migrated to `project_temp.fixture_root(...)` in
d22d21eb while their `import tempfile` line stayed behind -- so the name they used was never bound in
that scope. CI met it at 82a24df7 as soon as the earlier stage stopped failing first:

    File ".../verify_gate_runtime_convergence.py", line 112, in check_5_no_fabricated_exact
        with project_temp.fixture_root(prefix='gate-runtime-conv-') as td:
    NameError: name 'project_temp' is not defined
    QUALITY_GATE_FAIL gate=runtime-convergence exit_code=1

Nothing caught it locally because the local run had been `governance`, and this verifier is a different
stage. A check that raises is not a check that failed: it answered no question at all, and a report
built from ten claims is only worth what the ten calls returned. So the gate here is the call itself --
drive every check, require a report-shaped dict from each, and require the aggregate to name all ten.
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages" / "client-neutral-core" / "scripts" / "verify_gate_runtime_convergence.py"

spec = importlib.util.spec_from_file_location("vgrc", SCRIPT)
vgrc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(vgrc)

CHECK_NAMES = [name for name in dir(vgrc) if name.startswith("check_")]


class RuntimeConvergenceChecksExecute(unittest.TestCase):
    def test_every_check_is_discovered_and_callable(self) -> None:
        self.assertEqual(10, len(CHECK_NAMES),
                         f"the verifier exposes {len(CHECK_NAMES)} checks, expected 10: {CHECK_NAMES}; "
                         "a renamed or dropped check silently shrinks the acceptance surface")

    def test_no_check_raises_before_it_reports(self) -> None:
        for name in CHECK_NAMES:
            with self.subTest(check=name):
                report = getattr(vgrc, name)()
                self.assertIsInstance(report, dict, f"{name}() returned no report")
                for key in ("id", "name", "pass"):
                    self.assertIn(key, report, f"{name}() report is missing {key}")
                if not report["pass"]:
                    evidence = str(report.get("evidence", ""))
                    self.assertTrue(evidence.strip(),
                                    f"{name}() reports a failure with no evidence text, so a reader cannot "
                                    "tell a real failure from an environment-limited PENDING")

    def test_run_all_names_all_ten_checks_and_their_verdicts(self) -> None:
        report = vgrc.run_all()
        self.assertEqual(10, report["total"], report)
        self.assertEqual([c["id"] for c in report["checks"]], list(range(1, 11)),
                         "the aggregate must report the ten checks in order, or a member can vanish while "
                         "the totals still read plausible")
        self.assertLessEqual(report["passed"], report["total"])
        # Environment-limited PENDING (ids 1, 6, 9) is a declared state, not a crash; anything else that
        # does not pass has to be a real finding the owner sees.
        for item in report["pending"]:
            self.assertIn(item["id"], {1, 6, 9},
                          f"check {item['id']} ({item['name']}) fails outside the declared "
                          "environment-limited set")
            self.assertIn("PENDING", item["evidence"], item)


if __name__ == "__main__":
    unittest.main()
