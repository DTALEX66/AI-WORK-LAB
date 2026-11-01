"""C3/C4/C5 recovery-materials negative controls.

C3: the exact-SHA CI gate's content validation fails closed on every hollow
evidence shape (empty / bad JSON / wrong repo / wrong SHA / failed-or-missing
required check / unverifiable self-filled source / tampered digest), and a
valid locally-derived evidence object passes.

C4: a ``Ran 0 tests`` banner or an all-skipped run is NOT execution — the
governance batch must report a named hollow outcome, not a PASS.

C5: a changed path that matches no gate scope (and is not a recognized
fast-only surface) fails safe to the full canonical verify; pinned fast-only
surfaces keep their fast selection.
"""
from __future__ import annotations

import copy
import hashlib
import importlib.util
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "services/orchestration" / "run_quality_gate.py"


def load_runner():
    spec = importlib.util.spec_from_file_location("quality_gate", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _valid_evidence(repo: str, commit: str, tree: str, module) -> dict:
    """Build a minimal structurally-valid exact-SHA evidence object."""
    evidence = {
        "schema_version": "workflow/exact-sha-ci-evidence/v1",
        "observed_at": "2026-09-26T00:00:00Z",
        "produced_by": "github-actions",
        "repository": repo,
        "commit": commit,
        "tree": tree,
        "ci": {
            "provider": "github-actions",
            "run_id": "36235408380",
            "head_sha": commit,
            "jobs": [
                {"name": "workflow", "conclusion": "success"},
                {"name": "observer", "conclusion": "success"},
            ],
        },
        "required_checks": ["workflow", "observer"],
    }
    evidence["content_sha256"] = module.exact_sha_ci_evidence_digest(evidence)
    return evidence


class ExactShaCiContentValidationTests(unittest.TestCase):
    """C3 negative controls: hollow evidence must fail closed."""

    def setUp(self) -> None:
        self.m = load_runner()
        self.commit = "279e80efac" * 4  # 40-hex
        assert len(self.commit) == 40
        self.tree = "a" * 40
        self.repo = "DTALEX66/WORK-LAB"

    def _validate(self, evidence: dict) -> list[str]:
        return self.m.validate_exact_sha_ci_evidence(
            evidence, expected_repo=self.repo, expected_commit=self.commit, expected_tree=self.tree
        )

    def test_valid_evidence_passes(self) -> None:
        self.assertEqual(self._validate(_valid_evidence(self.repo, self.commit, self.tree, self.m)), [])

    def test_empty_object_fails(self) -> None:
        issues = self._validate({})
        self.assertTrue(issues)
        self.assertTrue(any("commit" in i for i in issues))

    def test_bad_json_represented_as_non_dict_fails(self) -> None:
        self.assertIn("evidence root is not an object", self.m.validate_exact_sha_ci_evidence(
            ["not", "an", "object"], expected_repo=self.repo, expected_commit=self.commit, expected_tree=self.tree
        ))

    def test_wrong_repository_fails(self) -> None:
        ev = _valid_evidence("Other/Repo", self.commit, self.tree, self.m)
        self.assertTrue(any("repository mismatch" in i for i in self._validate(ev)))

    def test_wrong_commit_fails(self) -> None:
        ev = _valid_evidence(self.repo, "f" * 40, self.tree, self.m)
        self.assertTrue(any("commit mismatch" in i for i in self._validate(ev)))

    def test_wrong_tree_fails(self) -> None:
        ev = _valid_evidence(self.repo, self.commit, "b" * 40, self.m)
        self.assertTrue(any("tree mismatch" in i for i in self._validate(ev)))

    def test_failed_required_check_fails(self) -> None:
        ev = _valid_evidence(self.repo, self.commit, self.tree, self.m)
        ev["ci"]["jobs"][0]["conclusion"] = "failure"
        issues = self._validate(ev)
        # digest now mismatched too; the semantic failure must be present.
        self.assertTrue(any("required check not success" in i for i in issues))

    def test_missing_required_check_fails(self) -> None:
        ev = _valid_evidence(self.repo, self.commit, self.tree, self.m)
        ev["required_checks"].append("aggregate")
        self.assertTrue(any("required check missing" in i for i in self._validate(ev)))

    def test_unverifiable_self_filled_source_fails(self) -> None:
        for source in ("local", "self", "self-filled", "manually-authored", ""):
            ev = _valid_evidence(self.repo, self.commit, self.tree, self.m)
            ev["produced_by"] = source
            issues = self._validate(ev)
            self.assertTrue(
                any("unverifiable" in i for i in issues),
                f"source={source!r} must be refused: {issues}",
            )

    def test_tampered_content_fails_digest(self) -> None:
        ev = _valid_evidence(self.repo, self.commit, self.tree, self.m)
        ev["ci"]["run_id"] = "12345"  # tamper a tamper-bearing field
        issues = self._validate(ev)
        self.assertTrue(any("content_sha256" in i for i in issues))

    def test_digest_recomputes_over_core_fields_only(self) -> None:
        ev = _valid_evidence(self.repo, self.commit, self.tree, self.m)
        original = ev["content_sha256"]
        ev["observed_at"] = "2030-01-01T00:00:00Z"  # non-tamper-bearing field
        self.assertEqual(self.m.exact_sha_ci_evidence_digest(ev), original)
        # and the recorded digest still matches because it covers core fields only
        self.assertEqual(self._validate(ev), [])


class GovernanceExecutionTruthTests(unittest.TestCase):
    """C4: zero-tests and all-skipped runs are named hollow outcomes."""

    def setUp(self) -> None:
        self.m = load_runner()

    def test_ran_zero_tests_is_not_execution(self) -> None:
        ok, state = self.m._governance_execution_truth("Ran 0 tests in 0.000s\nOK\n", True)
        self.assertFalse(ok)
        self.assertIn("zero-tests", state)

    def test_ran_missing_is_not_execution(self) -> None:
        ok, state = self.m._governance_execution_truth("some other output\n", True)
        self.assertFalse(ok)
        self.assertIn("not-run", state)

    def test_all_skipped_is_not_execution(self) -> None:
        out = "Ran 12 tests in 0.2s\nOK (skipped=12)\n"
        ok, state = self.m._governance_execution_truth(out, True)
        self.assertFalse(ok)
        self.assertIn("all-skipped", state)

    def test_partial_skips_are_execution(self) -> None:
        out = "Ran 12 tests in 0.2s\nOK (skipped=2)\n"
        ok, state = self.m._governance_execution_truth(out, True)
        self.assertTrue(ok)
        self.assertIn("executed=10", state)

    def test_ordinary_pass_is_execution(self) -> None:
        out = "Ran 10 tests in 0.2s\nOK\n"
        ok, state = self.m._governance_execution_truth(out, True)
        self.assertTrue(ok)

    def test_script_only_batch_is_execution(self) -> None:
        ok, state = self.m._governance_execution_truth("nf-script ok\n", False)
        self.assertTrue(ok)
        self.assertIn("script-only", state)


class GovernanceSkipIdentityTests(unittest.TestCase):
    """A skip count without identities cannot tell an environment boundary from a dead check."""

    def setUp(self) -> None:
        self.m = load_runner()

    def test_each_verbose_skip_line_yields_its_case_and_reason(self) -> None:
        out = ("test_symlink_needs_privilege (tests.x.K.test_symlink_needs_privilege) "
               "... skipped 'requires symlink privilege on Windows'\n"
               "test_vendor_cache (tests.y.K.test_vendor_cache) ... skipped \"no vendor cache here\"\n"
               "Ran 20 tests in 3.1s\nOK (skipped=2)\n")
        identities = self.m.governance_skip_identities(out)
        self.assertEqual(len(identities), 2)
        self.assertEqual(identities[0][1], "'requires symlink privilege on Windows'")
        self.assertIn("test_vendor_cache", identities[1][0])
        reported, agrees = self.m._governance_skip_truth("executed=18 ran=20 skipped=2", identities)
        self.assertEqual(reported, 2)
        self.assertTrue(agrees)

    def test_a_skip_the_parser_cannot_name_fails_the_gate_instead_of_passing(self) -> None:
        # The banner says three; only two lines carry a reason. That gap is the whole point of the
        # check: the third skip is unattributable, which is exactly what a silently-collected-zero
        # module looks like from the outside.
        out = ("test_a (m.K.test_a) ... skipped 'x'\n"
               "test_b (m.K.test_b) ... skipped 'y'\n"
               "Ran 10 tests in 1s\nOK (skipped=3)\n")
        identities = self.m.governance_skip_identities(out)
        reported, agrees = self.m._governance_skip_truth("executed=7 ran=10 skipped=3", identities)
        self.assertEqual(reported, 3)
        self.assertFalse(agrees)

    def test_a_clean_run_agrees_on_zero_and_needs_no_identities(self) -> None:
        identities = self.m.governance_skip_identities("Ran 10 tests in 1s\nOK\n")
        self.assertEqual(identities, [])
        self.assertEqual(self.m._governance_skip_truth("executed=10 ran=10 skipped=0", identities),
                         (0, True))

    def test_a_skip_reason_hanging_off_a_multiline_docstring_still_counts(self) -> None:
        # unittest -v prints a test with a multi-line docstring as its name, then the docstring, and
        # attaches ` ... skipped` to the LAST docstring line. Counting lines is what the agreement
        # check needs; the case label for such a test is the tail of a sentence, and this records
        # that limit rather than pretending the parser is exact.
        out = ("test_c (m.K.test_c) ... skipped 'no packaged install in a source checkout'\n"
               "Ran 4 tests in 0.5s\nOK (skipped=1)\n")
        identities = self.m.governance_skip_identities(out)
        self.assertEqual(len(identities), 1)
        self.assertIn("source checkout", identities[0][1])


class ChangedPathSafetyFallbackTests(unittest.TestCase):
    """C5: unknown changes fail safe to the full suite; fast-only surfaces stay fast."""

    def setUp(self) -> None:
        self.m = load_runner()

    def test_unknown_path_fails_safe_to_full_verify(self) -> None:
        selected = self.m.select_gates_for_changed(["unclassified/new-surface/file.py"])
        self.assertEqual(selected, self.m.VERIFY_ORDER)

    def test_github_workflow_stays_fast_only(self) -> None:
        selected = self.m.select_gates_for_changed([".github/workflows/work-lab-gate.yml"])
        self.assertEqual(set(selected), {"compile"})

    def test_known_specific_path_keeps_scoped_selection(self) -> None:
        selected = self.m.select_gates_for_changed(["packages/client-neutral-core/scripts/snapshot_api.py"])
        self.assertIn("snapshot-schema-v3", selected)
        self.assertLess(len(selected), len(self.m.VERIFY_ORDER))

    def test_mixed_known_and_unknown_fails_safe(self) -> None:
        selected = self.m.select_gates_for_changed(
            ["packages/client-neutral-core/scripts/snapshot_api.py", "unclassified/new-surface/file.py"]
        )
        self.assertEqual(selected, self.m.VERIFY_ORDER)


if __name__ == "__main__":
    unittest.main()
