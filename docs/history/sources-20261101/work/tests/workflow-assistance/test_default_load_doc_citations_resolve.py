"""Gate: the documents a new session is told to read must be followable, not just quotable.

WUI-17's scope is deliberately narrow -- "only handle consumers that still affect default loading". The
highest-leverage such consumer is the audit bootstrap chain itself: `AGENTS.md` tells a session to read
seven documents in order, and those documents cite paths. Measured 2026-10-10, 56 of 201 citations in that
chain were names a reader could not open from the repository root (bare filenames, front-end-relative
`src/...`), and one document pointed at `HISTORICAL-KEY-POINTS.md` without saying it lives under
`docs/history/owner-inputs/`. The chain still "worked" for me because I already knew where things were --
which is exactly the property a default-load document must not have.

So the rule: every backticked path citation in the scope resolves to a file in the working tree, uniquely;
a citation that means a CLASS (`SKILL.md` for every skill, `BOUNDARY.md` for each service boundary) or an
out-of-repo file (Hermes Home's live `config.yaml`) must be declared in the tool's allowance map with a
reason, and every allowance must still be IN USE or the run goes red. Frozen history is excluded from
name-suggestion on purpose: a current sentence never means the 2026-10-09 cutover copy.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _load(name: str, rel: str):
    spec = importlib.util.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


normaliser = _load("normalise_doc_citations_under_test", "scripts/audit/normalise_doc_citations.py")

# Measured 2026-10-10: 201 citations across the 8 scoped documents. The floor is low enough that ordinary
# editing can only raise it, high enough that a broken regex or a missing scope list cannot pass.
CITATION_FLOOR = 150


class DefaultLoadChainCitationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.stats = normaliser.run(apply=False)

    def test_the_scope_is_the_bootstrap_chain_it_claims_to_be(self) -> None:
        for doc in normaliser.SCOPE:
            self.assertTrue((ROOT / doc).is_file(),
                            f"{doc} is in the default-load scope but is not on disk -- a scoped document "
                            "that has moved leaves the chain citing nothing")
        self.assertIn("AGENTS.md", normaliser.SCOPE)
        self.assertIn("WORK-LAB-AUTHORITY.md", normaliser.SCOPE)
        # auditBootstrap step 6 is the live register: the document this round writes its findings into.
        # Leaving it out of SCOPE meant 374 citations in it were never looked at (measured 2026-10-10).
        self.assertIn("taskpacks/current/OPEN-TASK-REGISTER.md", normaliser.SCOPE)

    def test_the_population_is_the_checkout_not_a_list_of_directories_i_thought_of(self) -> None:
        """`projections/agents/generate.py` is tracked and cited; the first walk could not see it.

        The population came from SOURCE_DIRS, an allowlist, so every tracked file outside those eleven
        roots measured as unresolved -- a false red against an honest citation, and no way for the chain
        to cite a real path in `projections/` or at the root at all.
        """
        paths, _ = normaliser.working_tree()
        for must_be_visible in ("projections/agents/generate.py", "scripts/ci/verify_error_ledger.py",
                                "apps/observer/frontend/src/lib/navigation.ts",
                                ".project/governance/root-document-dispositions.json"):
            self.assertIn(must_be_visible, paths,
                          f"{must_be_visible} is tracked but the citation population does not carry it")
        self.assertFalse(any(path.startswith(normaliser.RUNTIME_ROOT) for path in paths),
                         "runtime copies must not decide what a bare name means -- only checkout bytes do")

    def test_an_inbound_reference_copy_is_never_the_meaning_of_a_bare_name(self) -> None:
        """`.ui-reference/WORK-LAB/**` carries its own types.ts; that made two honest citations ambiguous."""
        _paths, by_name = normaliser.working_tree()
        for name in ("types.ts", "navigation.ts"):
            for candidate in by_name.get(name, []):
                self.assertFalse(candidate.startswith(".ui-reference/"),
                                 f"{candidate} is inbound reference material and must stay explicit-only")

    def test_every_citation_resolves_or_is_declared_a_class_reference(self) -> None:
        self.assertEqual(self.stats["blockers"], [],
                         f"{len(self.stats['blockers'])} citation(s) in the default-load chain do not "
                         f"resolve: {self.stats['blockers'][:8]}")

    def test_the_chain_is_normalised_not_merely_resolvable(self) -> None:
        """A citation a reader has to guess their way to is a defect even when it resolves.

        A bare `test_control_service.py` resolves by filename, so the blocker list stayed empty while
        the default-load chain still carried a path nobody can open from the repository root. Being
        resolvable and being readable are two different assertions; only the second one is a chain.
        """
        self.assertEqual(0, self.stats["rewritten"],
                         f"{self.stats['rewritten']} citation(s) are still shorthand; run "
                         "scripts/audit/normalise_doc_citations.py --apply, because 'resolves' is not "
                         "the same question as 'a reader can follow it'")

    def test_the_scan_sees_the_citations_it_claims(self) -> None:
        self.assertGreaterEqual(self.stats["citations"], CITATION_FLOOR,
                                f"only {self.stats['citations']} citations scanned across "
                                f"{len(normaliser.SCOPE)} documents; below {CITATION_FLOOR} the empty "
                                "blocker list means the matcher went blind, not that the chain is clean")

    def test_no_allowance_is_left_unused(self) -> None:
        self.assertEqual(self.stats["staleAllowances"], [],
                         f"these declarations are no longer needed and would excuse a future real error: "
                         f"{self.stats['staleAllowances']}")
        self.assertEqual(sorted(self.stats["genericAllowed"]), sorted(normaliser.GENERIC_CITATIONS),
                         "every declared class reference should be exercised by the current text")
        self.assertEqual(self.stats["staleAbsentAllowances"], [],
                         f"nothing quotes these as a wrong path any more: {self.stats['staleAbsentAllowances']}")
        self.assertEqual(sorted(self.stats["absentAllowed"]), sorted(normaliser.QUOTED_AS_ABSENT),
                         "every quoted-as-wrong path should still be quoted by the current text")

    def test_the_resolver_convicts_a_path_that_does_not_exist_and_suggests_a_shorthand(self) -> None:
        # Without this, "no blockers" could mean the resolver stopped reporting anything at all.
        paths, by_name = normaliser.working_tree()
        bad = normaliser.resolve("services/orchestration/no_such_tool_anywhere.py", paths, by_name)
        self.assertEqual(bad, ("unresolved", ""),
                         "a path that exists nowhere was not reported -- the gate cannot be relied on")
        shorthand = normaliser.resolve("src/lib/navigation.ts", paths, by_name)
        self.assertEqual(shorthand[0], "rewrite",
                         f"a front-end-relative citation should be repairable, got {shorthand}")
        self.assertEqual(shorthand[1], "apps/observer/frontend/src/lib/navigation.ts")
        history_copy = normaliser.resolve("project-authority-index.json", paths, by_name)
        self.assertEqual(history_copy, ("rewrite", ".project/governance/project-authority-index.json"),
                         "a bare name must never be suggested as its frozen history copy")

    def test_a_quoted_wrong_path_is_only_safe_because_of_its_allowance(self) -> None:
        """The quoted-as-wrong list is load-bearing: without it the tool would rewrite the correction record.

        Six of these paths are a directory that does not exist plus a file whose real copy sits elsewhere, and
        `resolve()` finds that copy by basename. So deleting an entry does not produce a blocker -- it produces
        a *silent improvement* of a sentence whose whole point is that the path was wrong. Asserting the
        rewrite-would-happen is the only way to keep the allowance from being mistaken for dead code.
        """
        paths, by_name = normaliser.working_tree()
        would_rewrite = [(token, normaliser.resolve(token, paths, by_name))
                         for token in normaliser.QUOTED_AS_ABSENT]
        repairable = [(token, value) for token, value in would_rewrite if value[0] == "rewrite"]
        self.assertGreaterEqual(len(repairable), 6,
                                f"only {len(repairable)} quoted-as-wrong paths could be silently rewritten; "
                                "if that number drops to zero the allowance is decoration and the shipped "
                                "text should then be re-checked rather than the allowance kept")
        for token, value in repairable:
            self.assertEqual(value[1].rsplit("/", 1)[-1], token.rsplit("/", 1)[-1],
                             f"{token} would be rewritten to {value[1]}, which is not even the same file")
            self.assertNotEqual(value[1], token,
                                f"{value[1]} resolves as itself, so it is not a wrong path and its allowance "
                                "should be deleted")


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
