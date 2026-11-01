"""Gate: the committed CURRENT_STATE projection must describe the tree that carries it.

Why this file exists: `python scripts/ci/generate_current_state.py --check-current` is a command the
GitHub workflow runs (`.github/workflows/work-lab-gate.yml`, the `Run current state tests` step of the
integration job) and NO local gate member ran. At 47d13507 that asymmetry produced the exact signature
this repo has recorded before -- local governance gate `GATE_EXIT=0`, CI red:

    CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch: recorded=3992b069931e recomputed=55f3237b0127

Both machines recomputed the same digest, so the check is not machine-dependent: the published
projection was simply stale, and it went stale because `.githooks/pre-commit` -- whose whole job is to
regenerate it at commit time -- had been a silent no-op (bare `python` on a PATH that has none,
`git add` of the pre-convergence `00-governance/generated/…` paths, and a shell script checked out with
CRLF because it has no extension). See ERR-261.

The negative control points `--check-current` at a scratch COPY of the projection with a planted digest,
so the branch that convicts staleness is proven to fire rather than assumed from the CI log.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GENERATOR = ROOT / "scripts" / "ci" / "generate_current_state.py"
PROJECTION_JSON = Path(".project/governance/generated/CURRENT_STATE.json")
PROJECTION_MD = Path(".project/governance/generated/CURRENT_STATE.md")


def run_check(*extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(GENERATOR), "--root", str(ROOT), "--check-current",
                           *extra], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          errors="replace")


class CurrentStateProjectionFreshness(unittest.TestCase):
    def test_the_committed_projection_is_fresh_for_this_tree(self) -> None:
        result = run_check()
        self.assertEqual(0, result.returncode,
                         f"the published projection does not describe this tree:\n"
                         f"{result.stdout[-1200:]}\n{result.stderr[-400:]}")
        self.assertIn("CURRENT_STATE_FRESHNESS_PASS", result.stdout)
        digest = json.loads((ROOT / PROJECTION_JSON).read_text(encoding="utf-8"))["source_digest"]
        self.assertIn(digest, result.stdout,
                      "the passing check must name the same digest the record carries, or the two "
                      "numbers a reader compares are not the same fact")

    def test_the_check_convicts_a_projection_whose_digest_is_stale(self) -> None:
        scratch = Path(tempfile.mkdtemp(prefix="current-state-stale-",
                                        dir=ROOT / ".project-local" / "runs"))
        try:
            planted_json = scratch / PROJECTION_JSON.name
            planted_md = scratch / PROJECTION_MD.name
            shutil.copyfile(ROOT / PROJECTION_JSON, planted_json)
            shutil.copyfile(ROOT / PROJECTION_MD, planted_md)
            state = json.loads(planted_json.read_text(encoding="utf-8"))
            state["source_digest"] = "0" * len(state["source_digest"])
            planted_json.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                                    encoding="utf-8", newline="\n")

            result = run_check("--json-out", str(planted_json), "--markdown-out", str(planted_md))
            self.assertEqual(1, result.returncode,
                             "a projection carrying a stale source digest must be refused: this is the "
                             "branch that would otherwise let a commit publish a claim about a tree it "
                             "no longer describes")
            self.assertIn("CURRENT_STATE_FRESHNESS_FAIL source-digest-mismatch", result.stdout)
        finally:
            shutil.rmtree(scratch, ignore_errors=True)

    def test_the_generator_names_the_paths_the_repository_actually_uses(self) -> None:
        # The hook that regenerates this projection once added the pre-convergence `00-governance/…`
        # paths and reported success while staging nothing. A constant that points at a directory the
        # repo no longer has is the same defect one layer down, so the target is read from the tool.
        source = GENERATOR.read_text(encoding="utf-8")
        for rel in (PROJECTION_JSON.as_posix(), PROJECTION_MD.as_posix()):
            self.assertIn(rel, source, f"the generator does not declare {rel} as its output")
        self.assertNotIn("00-governance/generated", source,
                         "the generator still names the superseded layout; the hook would stage nothing")
        for path in (ROOT / PROJECTION_JSON, ROOT / PROJECTION_MD):
            self.assertTrue(path.is_file(), f"{path.relative_to(ROOT)} is not in the checkout")


if __name__ == "__main__":
    unittest.main()
