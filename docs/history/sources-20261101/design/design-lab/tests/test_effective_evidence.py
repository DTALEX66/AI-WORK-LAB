# SPDX-License-Identifier: MIT
"""P1-B: recorded vs effective capability evidence (DL-EVD-002/003).

Covers the pure separation logic (clean record keeps its recorded level,
requalification and foreign subject SHA drop to the structural ceiling), the
floor comparison boundaries, the capability-evidence hard check that requires a
requalification marker, and the release-claim rejection for requalified
capabilities. Stdlib only; runnable directly:

    python design-lab/tests/test_effective_evidence.py
"""
from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCRIPTS = REPO / "design-lab" / "scripts"
# Deterministic stand-in for "the current tree SHA": no capability in the
# committed index binds it, so it only exercises the comparison logic.
CURRENT_SHA = "1" * 40
FOREIGN_SHA = "2" * 40


def load(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class EffectiveEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.m = load("effective_evidence.py")

    def test_clean_record_keeps_recorded_level(self):
        record = {"evidenceLevel": "E3"}
        self.assertEqual(self.m.effective_evidence(record, CURRENT_SHA, True), "E3")

    def test_record_bound_to_current_sha_keeps_recorded_level(self):
        record = {"evidenceLevel": "E2", "subjectSha": CURRENT_SHA}
        self.assertEqual(self.m.effective_evidence(record, CURRENT_SHA, True), "E2")

    def test_requalification_downgrades_to_structural_ceiling(self):
        record = {"evidenceLevel": "E3", "requiresRequalification": True}
        self.assertEqual(self.m.effective_evidence(record, CURRENT_SHA, True), "E1")

    def test_requalification_without_structural_pass_is_e0(self):
        record = {"evidenceLevel": "E3", "requiresRequalification": True}
        self.assertEqual(self.m.effective_evidence(record, CURRENT_SHA, False), "E0")

    def test_foreign_subject_sha_downgrades(self):
        record = {"evidenceLevel": "E4", "subjectSha": FOREIGN_SHA}
        self.assertEqual(self.m.effective_evidence(record, CURRENT_SHA, True), "E1")
        self.assertEqual(self.m.effective_evidence(record, CURRENT_SHA, False), "E0")

    def test_requalification_wins_even_for_a_current_sha_binding(self):
        record = {"evidenceLevel": "E5", "subjectSha": CURRENT_SHA, "requiresRequalification": True}
        self.assertEqual(self.m.effective_evidence(record, CURRENT_SHA, True), "E1")

    def test_level_order_is_the_canonical_ladder(self):
        self.assertEqual(self.m.LEVEL, {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5})

    def test_structural_pass_proxy_is_deterministic(self):
        self.assertTrue(self.m.structural_pass_from_recorded("E1"))
        self.assertTrue(self.m.structural_pass_from_recorded("E5"))
        self.assertFalse(self.m.structural_pass_from_recorded("E0"))
        self.assertFalse(self.m.structural_pass_from_recorded(None))

    def test_meets_floor_boundaries(self):
        self.assertTrue(self.m.meets_floor("E1", "E1"))
        self.assertTrue(self.m.meets_floor("E3", "E1"))
        self.assertTrue(self.m.meets_floor("E2", "E2"))
        self.assertFalse(self.m.meets_floor("E2", "E3"))
        self.assertFalse(self.m.meets_floor("E0", "E1"))

    def test_meets_floor_fails_closed_on_unknown_levels(self):
        self.assertFalse(self.m.meets_floor("E9", "E1"))
        self.assertFalse(self.m.meets_floor("E3", "E9"))
        self.assertFalse(self.m.meets_floor(None, "E1"))
        self.assertFalse(self.m.meets_floor("E3", None))


class IndexHelperTests(unittest.TestCase):
    def setUp(self):
        self.m = load("effective_evidence.py")

    def test_committed_index_flags_creative_toolchain(self):
        flagged = self.m.requalified(self.m.load_index(REPO))
        self.assertIn("creative-toolchain", flagged)
        self.assertTrue(all(flagged.values()))

    def test_index_resolves_from_repo_root_and_design_lab(self):
        self.assertEqual(self.m.load_index(REPO), self.m.load_index(REPO / "design-lab"))

    def test_requalified_returns_only_marked_capabilities(self):
        index = {
            "capabilities": [
                {"id": "a", "requiresRequalification": True},
                {"id": "b"},
                {"id": "c", "requiresRequalification": False},
                {"id": "", "requiresRequalification": True},
                "not-an-object",
            ]
        }
        self.assertEqual(self.m.requalified(index), {"a": True})
        self.assertEqual(self.m.requalified({}), {})
        self.assertEqual(self.m.requalified({"capabilities": "nope"}), {})


class CapabilityEffectiveCheckTests(unittest.TestCase):
    """The hard check in verify_capability_evidence_v4.py (additive)."""

    def setUp(self):
        self.v4 = load("verify_capability_evidence_v4.py")
        self.eff = load("effective_evidence.py")

    def findings(self, *capabilities):
        return self.v4.effective_evidence_findings(list(capabilities), CURRENT_SHA, self.eff)

    def test_requalified_capability_is_reported_without_error(self):
        info, errors = self.findings(
            {
                "id": "creative-toolchain",
                "minimumRequiredEvidence": "E3",
                "actualEvidence": "E3",
                "requiresRequalification": True,
            }
        )
        self.assertEqual(errors, [])
        self.assertEqual(
            info,
            [
                "EFFECTIVE_EVIDENCE creative-toolchain recorded=E3 effective=E1 "
                "requiresRequalification=true"
            ],
        )

    def test_stale_claim_without_marker_is_an_error(self):
        info, errors = self.findings(
            {
                "id": "silent-stale",
                "minimumRequiredEvidence": "E3",
                "actualEvidence": "E3",
                "subjectSha": FOREIGN_SHA,
            }
        )
        self.assertEqual(info, [])
        self.assertEqual(len(errors), 1)
        self.assertIn("without a requiresRequalification marker", errors[0])
        self.assertIn("silent-stale", errors[0])

    def test_recorded_level_below_floor_is_not_a_requalification_error(self):
        # design-intelligence records E1 against an E2 floor: that is the existing
        # floor/actual comparison, not a hidden stale-evidence claim.
        info, errors = self.findings(
            {"id": "design-intelligence", "minimumRequiredEvidence": "E2", "actualEvidence": "E1"}
        )
        self.assertEqual((info, errors), ([], []))

    def test_clean_capability_at_floor_is_untouched(self):
        info, errors = self.findings(
            {"id": "release-evidence", "minimumRequiredEvidence": "E1", "actualEvidence": "E1"}
        )
        self.assertEqual((info, errors), ([], []))

    def test_committed_index_reports_every_requalified_capability(self):
        index = self.eff.load_index(REPO)
        info, errors = self.v4.effective_evidence_findings(
            index["capabilities"], CURRENT_SHA, self.eff
        )
        self.assertEqual(errors, [])
        reported = {line.split()[1] for line in info}
        self.assertEqual(reported, set(self.eff.requalified(index)))

    def test_requalified_creative_toolchain_line_is_exact(self):
        index = self.eff.load_index(REPO)
        info, _ = self.v4.effective_evidence_findings(index["capabilities"], CURRENT_SHA, self.eff)
        lines = [line for line in info if line.startswith("EFFECTIVE_EVIDENCE creative-toolchain")]
        self.assertEqual(len(lines), 1)
        self.assertEqual(
            lines[0],
            "EFFECTIVE_EVIDENCE creative-toolchain recorded=E3 effective=E1 "
            "requiresRequalification=true",
        )


class ReleaseClaimRequalificationTests(unittest.TestCase):
    """verify_release_evidence.py refuses claims above the effective floor."""

    def setUp(self):
        self.rel = load("verify_release_evidence.py")
        self.eff = load("effective_evidence.py")
        self.index = self.eff.load_index(REPO)

    @staticmethod
    def claim(capability_id, level):
        return {"capability_id": capability_id, "evidence_level": level}

    def failures(self, capability_id, level):
        return self.rel.requalification_failures(
            self.claim(capability_id, level), self.index, self.eff
        )

    def test_e3_claim_on_requalified_capability_fails_with_exact_text(self):
        self.assertEqual(
            self.failures("creative-toolchain", "E3"),
            [
                "requalified capability cannot certify E3 on the current tree "
                "(effective floor E1); requiresRequalification=true in capability-evidence-index"
            ],
        )

    def test_e5_claim_on_requalified_capability_fails(self):
        self.assertEqual(len(self.failures("creative-toolchain", "E5")), 1)

    def test_structural_claim_on_requalified_capability_is_allowed(self):
        self.assertEqual(self.failures("creative-toolchain", "E1"), [])
        self.assertEqual(self.failures("creative-toolchain", "E0"), [])

    def test_claim_for_a_non_requalified_capability_is_untouched(self):
        self.assertEqual(self.failures("release-evidence", "E3"), [])
        self.assertEqual(self.failures("design-intelligence", "E4"), [])

    def test_unknown_capability_is_not_flagged_by_this_check(self):
        self.assertEqual(self.failures("does-not-exist", "E5"), [])

    def test_contract_rules_are_unchanged(self):
        try:
            import jsonschema  # noqa: F401
        except ImportError:  # pragma: no cover - venv always ships it
            self.skipTest("jsonschema not installed")
        record = {
            "schemaVersion": "design-lab/release-evidence/v1",
            "capability_id": "creative-toolchain",
            "subject": "uiux-golden-scenario",
            "version": "1.0",
            "branch": "main",
            "head_sha": "a" * 40,
            "tree_sha": "b" * 40,
            "worktree": "clean",
            "evidence_level": "E3",
            "state": "PASS",
            "claim": "release verified",
            "environment": "github-actions",
            "ci": {
                "workflow_name": "canonical",
                "run_id": "123",
                "head_sha": "a" * 40,
                "conclusion": "success",
            },
            "reviewer": "codex-reviewer",
            "timestamp": "2026-09-20T00:00:00Z",
            "read_back": {"remote_sha": "a" * 40, "remote_branch": "main", "verified": True},
        }
        # The contract layer still accepts it; only the requalification check fails it.
        self.assertEqual(self.rel.validate_contract(record), [])
        self.assertEqual(len(self.failures("creative-toolchain", "E3")), 1)

    def test_usage_branch_still_fails_closed_without_arguments(self):
        import io
        import contextlib
        import sys

        argv = sys.argv
        sys.argv = [argv[0]]
        buffer = io.StringIO()
        try:
            with contextlib.redirect_stdout(buffer):
                code = self.rel.main()
        finally:
            sys.argv = argv
        output = buffer.getvalue()
        self.assertEqual(code, 2)
        self.assertIn("USAGE: verify_release_evidence.py <release-evidence.json>", output)
        self.assertIn("RELEASE_EVIDENCE=FAIL", output)


class ReleaseEvidenceEndToEndTests(unittest.TestCase):
    """The real script (not just the helper) rejects an E3 claim end to end."""

    def setUp(self):
        self.rel = load("verify_release_evidence.py")
        runtime = REPO / ".project-local" / "task-runtime"
        self.dir = str(runtime) if runtime.is_dir() else None

    def _live(self, args):
        import subprocess

        return subprocess.run(
            ["git", *args], cwd=REPO, capture_output=True, text=True,
            encoding="utf-8", errors="replace",
        ).stdout.strip()

    def test_e3_release_claim_for_creative_toolchain_is_rejected(self):
        import json
        import subprocess
        import sys
        import tempfile

        head = self._live(["rev-parse", "HEAD"])
        tree = self._live(["rev-parse", "HEAD^{tree}"])
        branch = self._live(["rev-parse", "--abbrev-ref", "HEAD"])
        record = {
            "schemaVersion": "design-lab/release-evidence/v1",
            "capability_id": "creative-toolchain",
            "subject": "creative-toolchain-release-claim",
            "version": "0.1.0-alpha.0",
            "branch": branch,
            "head_sha": head,
            "tree_sha": tree,
            # The contract layer only accepts worktree=clean, so the record must
            # claim it to reach the live facts; the live worktree is reported by
            # the script itself and is not what this test is about.
            "worktree": "clean",
            "evidence_level": "E3",
            "state": "PASS",
            "claim": "stale E3 claim on the current tree",
            "environment": "local-test",
            "ci": {
                "workflow_name": "canonical-verify",
                "run_id": "1",
                "head_sha": head,
                "conclusion": "success",
            },
            "reviewer": "p1b-test",
            "timestamp": "2026-09-20T00:00:00Z",
            "read_back": {"remote_sha": head, "remote_branch": branch, "verified": True},
        }
        with tempfile.NamedTemporaryFile(
            "w", suffix="-p1b-release.json", delete=False, dir=self.dir
        ) as handle:
            json.dump(record, handle)
            path = handle.name
        try:
            result = subprocess.run(
                [sys.executable, str(SCRIPTS / "verify_release_evidence.py"), path],
                capture_output=True, text=True, encoding="utf-8", errors="replace",
                cwd=REPO,
            )
        finally:
            Path(path).unlink(missing_ok=True)
        self.assertNotEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn(
            "requalified capability cannot certify E3 on the current tree "
            "(effective floor E1); requiresRequalification=true in capability-evidence-index",
            result.stdout,
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
