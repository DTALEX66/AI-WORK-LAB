"""Mandatory gate: the three WUI-17 surfaces stay under the policy each one earned.

The verifier has three moving parts that can silently stop working: the population (git-driven), the
external-copy declaration (which must keep covering real surfaces), and the ratchet (which must convict
both growth AND a repaired pointer). Each negative control below mutates one of those and requires the
verifier to exit non-zero with the row named -- a control that cannot be made red guards nothing.
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
SCRIPT = ROOT / "scripts" / "ci" / "verify_refs_surface_policies.py"
POLICY = ROOT / ".project" / "governance" / "refs-surface-policies.json"

sys.path.insert(0, str(ROOT / "scripts" / "ci"))
import verify_refs_surface_policies as verifier  # noqa: E402


def run(policy: Path | None = None) -> subprocess.CompletedProcess:
    args = [sys.executable, str(SCRIPT)]
    if policy is not None:
        args += ["--policy", policy.relative_to(ROOT).as_posix()]
    return subprocess.run(args, cwd=ROOT, text=True, encoding="utf-8", errors="replace",
                          capture_output=True)


class ShippedRepository(unittest.TestCase):
    def test_the_shipped_policy_passes_with_a_measured_ratchet(self) -> None:
        result = run()
        self.assertEqual(0, result.returncode, result.stdout + result.stderr)
        self.assertIn("REFS_SURFACE_POLICIES_PASS", result.stdout)
        self.assertIn("new=0 fixed=0", result.stdout)
        # The baseline must not have quietly become empty or drifted -- asserted as a property, not a
        # frozen count. After the six root-level UI records and design.qa.yaml moved to
        # docs/history/archive/root-ui-records-20261019/, the ratcheted population was re-measured at 295
        # rows (it was 386 on 2026-10-18: 93 broken refs left the root surface, +2 came from AGENTS.md's
        # owner-gated stale pointers). The ratchet already requires new=0 fixed=0 (every recorded row is
        # still broken today and no repair drifted), so the residual guard is "the recorded baseline is a
        # live, non-empty measurement": its length must equal the verifier's own ratchet_broken_today count.
        policy = json.loads(POLICY.read_text(encoding="utf-8"))
        baseline_rows = len(policy["ratchet"]["baseline"])
        self.assertGreater(baseline_rows, 0)
        self.assertIn(f"ratchet_baseline={baseline_rows}", result.stdout)
        self.assertIn(f"ratchet_broken_today={baseline_rows}", result.stdout)


class TheRatchetCanGoRed(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = Path(tempfile.mkdtemp(prefix="refs-policy-", dir=str(_runtime_root())))
        self.addCleanup(shutil.rmtree, self.dir, True)
        self.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def write(self) -> Path:
        path = self.dir / "policy.json"
        path.write_text(json.dumps(self.policy, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def test_a_new_broken_reference_is_named(self) -> None:
        removed = self.policy["ratchet"]["baseline"].pop(0)
        result = run(self.write())
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("NEW_BROKEN", result.stdout)
        self.assertIn(f"{removed['target']}:{removed['line']}", result.stdout)

    def test_a_repaired_pointer_requires_the_baseline_to_be_reissued(self) -> None:
        self.policy["ratchet"]["baseline"].append(
            {"target": "reports/NEVER-MEASURED.md", "line": 1, "ref": "src/never.ts", "kind": "file"})
        result = run(self.write())
        self.assertEqual(1, result.returncode, result.stdout + result.stderr)
        self.assertIn("FIXED_BUT_BASELINE_STALE", result.stdout)
        self.assertIn("reports/NEVER-MEASURED.md:1", result.stdout)

    def test_the_written_policy_keeps_the_ratchet_rule_and_the_declaration(self) -> None:
        """Reissuing a baseline rewrites this file, so the next writer must not lose the two-sided rule."""
        self.assertIn("may not grow", self.policy["ratchet"]["policy"])
        self.assertIn("reissue", self.policy["ratchet"]["policy"])
        self.assertTrue(self.policy["externalSkillCopies"]["prefixes"])


class ClassificationAndFloors(unittest.TestCase):
    def setUp(self) -> None:
        self.policy = json.loads(POLICY.read_text(encoding="utf-8"))

    def test_external_copies_are_declared_not_ratcheted(self) -> None:
        for target in ("knowledge-staging/asset-provenance/deep/nested/notes.md",
                       "reports/audit-evidence/some/SKILL.md",
                       "reports/skills/nested/page.md"):
            self.assertTrue(verifier.is_external_skill_copy(target, self.policy), target)
        for target in ("reports/PROJECT-FULL-STAGE-AUDIT-20260928.md", "AGENTS.md",
                       "NOTICE.md"):
            self.assertFalse(verifier.is_external_skill_copy(target, self.policy), target)

    def test_a_duplicate_reference_is_counted_twice(self) -> None:
        row = {"target": "a.md", "line": 1, "ref": "src/x.ts", "kind": "file"}
        new, fixed = verifier.compare([row], [row, dict(row)])
        self.assertEqual([row], new)
        self.assertEqual([], fixed)

    def test_a_scan_below_its_floors_is_a_broken_instrument(self) -> None:
        result = {"targets": 1, "refs": 1, "externalSurfaces": 0}
        findings = verifier.population_violations(result, self.policy)
        self.assertEqual(3, len(findings), findings)
        self.assertTrue(any("surface floor" in finding for finding in findings))
        self.assertTrue(any("reference floor" in finding for finding in findings))
        self.assertTrue(any("external declaration floor" in finding for finding in findings))

    def test_the_population_comes_from_the_tracked_tree_not_from_a_list(self) -> None:
        tracked = ["AGENTS.md", "reports/a.md", "knowledge-staging/b.md",
                   "docs/current/c.md", "apps/observer/README.md", "reports/not-markdown.json"]
        self.assertEqual(["AGENTS.md", "knowledge-staging/b.md", "reports/a.md"],
                         verifier.population(tracked, self.policy))


def _runtime_root() -> Path:
    root = ROOT / ".project-local" / "runs"
    root.mkdir(parents=True, exist_ok=True)
    return root


if __name__ == "__main__":
    unittest.main()
