# SPDX-License-Identifier: MIT
"""No verification script may be orphaned without a recorded reason.

`canonical-verify.yml` enumerates its gates one step per script -- there is no glob and no
manifest -- so a `verify_*.py` that nobody adds a step for never runs, and nothing anywhere
says so. That is how `scripts/audit_workbench_ui.py` came to report twelve live Workbench
violations (including a 23px-tall sole mobile navigation control) while every required CI
context was green.

This test is the anti-recurrence gate: the set of unreachable verifiers must equal the
explicit exemption list below, in both directions. A new orphan fails, and so does an
exemption that has gone stale -- either because the script was wired in, or because it was
deleted while its excuse stayed behind.
"""
from __future__ import annotations

import ast
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# Scripts that are legitimately not CI-invoked, each with the reason.
MANUAL_GATES = {
    "verify_fresh_clone.py":
        "clones the whole repository (~236 MiB pack) into an ignored directory; it is a "
        "local clean-room check and CI already proves a clean wheel install separately",
    "verify_clean_tree.py":
        "judges the working tree's uncommitted state, which is vacuous in CI where the "
        "checkout is clean by construction",
    "verify_r5_intake.py":
        "verifies intake of the superseded DL-TP-20260908-R5 taskpack; historical, not a "
        "current gate",
    "capture_workbench_screenshots.mjs":
        "capture tool driven through scripts/capture_workbench_screenshots.py by a human "
        "or by the browser gates",
    # `deepseek_content_audit.py` was exempted here as a one-off historical audit. It is no longer
    # one-off: design-lab/scripts/verify_projection_freshness.py names its --check as a
    # RECEIPT_CHECK, and this test's stale-exemption rule is what surfaced the leftover row --
    # the same shape as `deepseek_foundation_audit.py` above. An exemption kept after the script
    # became reachable is a register that no longer describes the repository.
    "deepseek_directory_audit.py": "one-off historical audit run",
    # `deepseek_foundation_audit.py` was exempted as a one-off. It is no longer one-off:
    # design-lab/scripts/verify_projection_freshness.py invokes its --check as an entry, and this
    # test's stale-exemption rule is what surfaced that -- an exemption kept after the script
    # became reachable is a register that no longer describes the repository.
    "deepseek_post_cleanup_audit.py": "one-off historical audit run",
    "deepseek_size_audit.py": "one-off historical audit run",
    # The U01 reconciliation writer/auditor for the 2026-10-09 desktop batch. Its --check demands
    # byte equality with the committed archive-2026-10-19/current-records/UI-DESKTOP-RECONCILIATION-2026-10-09.md, and
    # that document embeds the HEAD it was rendered at, so it can only ever match at the commit
    # that wrote it; the committed copy also carries a hand-written 2026-10-12 correction that the
    # renderer does not produce. Measured 2026-10-13 in this tree and in a clean clone at
    # 7799fbe6: rc=1, UI_RECONCILIATION_DRIFT, both trees. It is run by hand when the
    # reconciliation is republished; see its DECLARED_BUT_UNINVOKED row for what must change
    # before CI can require it.
    "audit_ui_desktop_reconcile_20261009.py":
        "point-in-time reconciliation auditor whose committed document embeds the commit it was "
        "written at, so its --check is red in every tree by construction, not by drift",
}

CANDIDATE = re.compile(r"(verify|audit|check|no_overclaim|clean_tree)")


def script_candidates() -> dict[str, Path]:
    found: dict[str, Path] = {}
    for directory in ("scripts", "design-lab/scripts"):
        for path in (ROOT / directory).glob("*.py"):
            if CANDIDATE.search(path.name):
                found[path.name] = path
    for path in (ROOT / "design-lab/tests/e2e").glob("*.mjs"):
        found[path.name] = path
    return found


def reachable_names(candidates: dict[str, Path]) -> set[str]:
    """Fixed point over 'who names whom', starting from CI's own entry points.

    This module is excluded from the scan: it lists every manual gate by name in its own
    exemption table, so counting it as a caller would make those gates reachable by
    virtue of being exempted -- which the stale-exemption assertion duly caught on the
    first run.
    """
    self_name = Path(__file__).name
    sources: dict[str, str] = {}
    for pattern in (".github/workflows/*.yml", "design-lab/tests/*.py",
                    "design-lab/tests/e2e/*.mjs", "scripts/*.py", "design-lab/scripts/*.py"):
        for path in ROOT.glob(pattern):
            if path.name == self_name:
                continue
            try:
                sources[path.name] = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
    workflows = [name for name in sources if (ROOT / ".github/workflows" / name).is_file()]
    # Every test module is run by scripts/run_python_tests.py, so a test naming a script
    # makes that script reachable.
    runners = set(workflows) | {name for name in sources if name.startswith("test_")}
    live = {name for name in candidates if any(name in sources.get(r, "") for r in runners)}
    frontier = set(live)
    while True:
        nxt = set()
        for src in frontier:
            text = sources.get(src, "")
            for cand in candidates:
                if cand not in live and cand in text:
                    nxt.add(cand)
        if not nxt:
            return live
        live |= nxt
        frontier = nxt


class GateReachabilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.candidates = script_candidates()
        self.reachable = reachable_names(self.candidates)
        self.orphaned = sorted(set(self.candidates) - self.reachable)

    def test_the_scan_itself_sees_a_meaningful_population(self) -> None:
        # Positive control: if the glob or the reachability walk silently broke, the
        # equality assertions below would pass against empty sets.
        self.assertGreater(len(self.candidates), 60,
                           f"only {len(self.candidates)} candidates found -- the scanner broke")
        self.assertGreater(len(self.reachable), 50,
                           f"only {len(self.reachable)} reachable -- the walker broke")

    def test_every_orphaned_gate_is_exempted_with_a_reason(self) -> None:
        unexplained = [name for name in self.orphaned if name not in MANUAL_GATES]
        self.assertEqual(unexplained, [],
                         f"{len(unexplained)} verifier(s) are named by no workflow and no test, "
                         f"so they never run: {unexplained}. Wire them in (a test module that "
                         "shells out is the route that avoids editing the SHA-pinned "
                         "canonical-verify.yml) or record why they are manual.")

    def test_no_exemption_has_gone_stale(self) -> None:
        stale = sorted(name for name in MANUAL_GATES if name not in set(self.candidates))
        self.assertEqual(stale, [], f"exemptions for scripts that no longer exist: {stale}")
        wired = sorted(name for name in MANUAL_GATES if name in self.reachable)
        self.assertEqual(wired, [], f"exempted but actually reachable now: {wired}")

    def test_each_exemption_states_a_reason(self) -> None:
        for name, reason in MANUAL_GATES.items():
            self.assertGreater(len(reason), 20, f"{name} has a placeholder exemption")


class ReadOnlyModeTests(unittest.TestCase):
    """A declared `--check` that nothing invokes is a gate that exists on paper only.

    `test_every_orphaned_gate_is_exempted_with_a_reason` asks whether a *script* is named by CI.
    It cannot see the mode: `deepseek_hermes_migration.py --verify` was reachable by name (its own
    module-level constants are imported elsewhere) while its read-only form had been printing FAIL
    in both trees for weeks, unheard, because no table ever passed the flag. This test asks the
    mode question, and it answers it from the same source set the reachability walk uses.

    Measured 2026-10-09 in both the primary tree and a clean detached worktree at 5f3e5d1d
    (porcelain 0 before and after): the ten rows below are declared with the verdict each printed.
    Four forms that were green in both trees and read tracked text only got wired into
    `verify_projection_freshness.py` as RECEIPT_CHECKS in the same commit, so this register holds
    only what cannot yet be required -- which is what makes it shrinkable.

    The first version of this predicate looked for a name and a flag within three lines of each
    other and matched the exemption tables themselves -- eight declared rows lit up as "invoked"
    because a docstring two lines away said `--check`. Reading the tables as objects replaced that.
    Its helper was then named `test_module_calls`, which unittest collected as a test case and ran
    with no arguments: a `TypeError: missing 1 required positional argument`, i.e. a helper whose
    name makes it a test. It is `call_sites_in` now, and the planted-call control says a prose
    mention must not count.
    """

    READ_ONLY_FLAGS = ("--check", "--self-test", "--verify")
    INVOKED_WITH_A_FLAG = (
        # positive controls: forms CI demonstrably runs, so a broken predicate shows up as
        # "nothing is invoked" rather than as a silent pass
        "scripts/verify_language_boundary.py",
        "design-lab/scripts/verify_projection_freshness.py",
        "scripts/deepseek_hermes_migration.py",
        "scripts/deepseek_spill_census.py",
        "scripts/deepseek_test_gate_report.py",
        "scripts/verify_no_overclaim.py",
    )

    DECLARED_BUT_UNINVOKED = {
        "audit_ui_desktop_reconcile_20261009.py":
            "rc=1, UI_RECONCILIATION_DRIFT, measured 2026-10-13 in this tree and in a clean clone "
            "at 7799fbe6. The diff is entirely in the two lines render() cannot reproduce: the "
            "observed-HEAD line moves with every commit, and the committed copy carries a "
            "hand-written 2026-10-12 correction. The predicate is byte equality, so no commit "
            "after the one that wrote the document can pass. Wire it in once --check judges the "
            "derived body instead of the document that embeds its own commit",
        "build_candidate_taxonomy.py":
            "declares --check but the parser requires --observation, so the read-only form cannot "
            "be invoked as shipped -- measured rc=2 with an argparse usage error in both trees on "
            "2026-10-09. Either default the observation to a tracked file or drop the flag",
        "deepseek_directory_audit.py":
            "DIRECTORY_AUDIT=FAIL in both trees and the cause is not yet diagnosed, so wiring it "
            "would make the aggregate red on a claim nobody can explain yet",
        "deepseek_final_closeout.py":
            "FINAL_CLOSEOUT=FAIL in both trees; it reads ledger state that has moved since "
            "2026-09-14. Diagnose what it now refuses, then require it",
        "deepseek_size_audit.py":
            "SIZE_AUDIT=PASS, but its input is this machine's .git pack (236 MiB measured on "
            "2026-10-08) and a runner's clone shape changes that number, so it must state a "
            "machine-independent judgement before CI can require it",
        "deepseek_worktree_reconciliation.py":
            "WORKTREE_INVENTORY=PASS against this machine's registered worktrees; a CI checkout "
            "has exactly one, so the inventory it compares is not a repository property",
        "generate_current_reports.py":
            "CURRENT_REPORTS=DRIFT: three projections disagree here, nine in a clean checkout. "
            "Measured 2026-10-13 by running the writer form and diffing it: the fields that move "
            "are `generatedAt` (a timestamp), the whole `gitObservation` block (branch, sha, "
            "origin_main, tracked_files, worktree_changes, worktree_digest) and `inputDigest`, "
            "which is derived from them. So the record names the commit that wrote it and cannot "
            "match one commit later -- the same shape as the D08 reconciliation document that "
            "embeds its own HEAD. `verify_contract_graph` already carries the pattern that makes "
            "such a record requirable: it passes while declaring `generated_at`/`subject_sha` "
            "generation-time. Applying that rule here is a decision about what this record is "
            "for, not a repair, so it stays the owner's open ruling -- and when the "
            "non-repository fields stop counting, this becomes a required check",
        "generate_ssot_projections.py":
            "SSOT_PROJECTIONS=DRIFT CAPABILITY_INDEX.json / EVIDENCE_INDEX.json in both trees: the "
            "generated indices differ from their authoring sources. Republish, or record which "
            "side is authoritative",
        "render_brand_asset.py":
            "BRAND_ASSET=OK (png=4953B inlined=4953B) but it is an asset-pipeline step rather than "
            "a record verifier; requiring it would make CI depend on the renderer being present",
        "verify_zero_spill.py":
            "ZERO_SPILL_SELF_TEST=FAIL in both trees because its own self-test drives "
            "generate_current_reports.py --check and inherits that DRIFT -- a self-test must use a "
            "command that is green by construction, not one that is currently owed",
    }

    def declared(self) -> dict[str, list[str]]:
        out: dict[str, list[str]] = {}
        for directory in ("scripts", "design-lab/scripts"):
            for path in sorted((ROOT / directory).glob("*.py")):
                try:
                    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
                except (SyntaxError, UnicodeDecodeError):
                    continue
                flags = set()
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) \
                            and node.func.attr == "add_argument":
                        for arg in node.args:
                            if isinstance(arg, ast.Constant) and arg.value in self.READ_ONLY_FLAGS:
                                flags.add(arg.value)
                if flags:
                    out[path.name] = sorted(flags)
        return out

    CALL_FORM = re.compile(r'["\']([\w./-]+\.py)["\']\s*,\s*\[([^\]]*)\]')

    @classmethod
    def call_sites_in(cls, text: str) -> list[tuple[str, list[str]]]:
        return [(Path(match.group(1)).name,
                 [part.strip().strip('"\'') for part in match.group(2).split(",")])
                for match in cls.CALL_FORM.finditer(text)]

    def invocations(self) -> list[tuple[str, list[str]]]:
        """Every CI-surface call site as (script name, argv), read as data, never as prose.

        The first version of this predicate looked for a name and a flag within three lines of
        each other, and matched the exemption tables themselves -- eight declared rows lit up as
        "invoked" because a docstring two lines away said `--check`. So: the three invocation
        tables are parsed as Python objects, the workflow lines as shell, and a test module only
        counts when the script and its argv list sit in the same bracketed call.
        """
        found: list[tuple[str, list[str]]] = []
        sys.path.insert(0, str(ROOT / "scripts"))
        sys.path.insert(0, str(ROOT / "design-lab" / "scripts"))
        import verify_authority_gates  # noqa: E402
        import verify_design_lab  # noqa: E402
        import verify_projection_freshness as fresh  # noqa: E402
        for name in verify_design_lab.SCRIPTS:
            found.append((Path(name).name, []))
        for _label, args in verify_design_lab.EXTRA_CHECKS:
            found.append((Path(str(args[0])).name, [str(a) for a in args[1:]]))
        for _label, script, argv in verify_authority_gates.GATES:
            found.append((Path(str(script)).name, [str(a) for a in argv]))
        for _record, script, argv in fresh.ENTRIES:
            found.append((Path(str(script)).name, [str(a) for a in argv]))
        for script, argv in fresh.RECEIPT_CHECKS:
            found.append((Path(str(script)).name, [str(a) for a in argv]))
        for path in ROOT.glob(".github/workflows/*.yml"):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                for match in re.finditer(r"python3?\s+\S*?([\w.-]+\.py)(.*)", line):
                    found.append((match.group(1), match.group(2).split()))
        for path in ROOT.glob("design-lab/tests/*.py"):
            if path.name == Path(__file__).name:
                continue
            for name, argv in self.call_sites_in(
                    path.read_text(encoding="utf-8", errors="replace")):
                found.append((name, argv))
        return found

    def setUp(self) -> None:
        self.invoked = self.invocations()
        self.declared = self.declared()
        with_flag: dict[str, list[str]] = {}
        for name, argv in self.invoked:
            flags = [a for a in argv if a in self.READ_ONLY_FLAGS]
            if flags:
                with_flag.setdefault(name, []).extend(flags)
        self.with_flag = with_flag
        self.uninvoked = sorted(name for name in self.declared if name not in with_flag)


    def test_the_scanner_sees_a_meaningful_population(self) -> None:
        # Without this control the equality assertions below would pass against empty sets.
        self.assertGreaterEqual(len(self.declared), 25,
                                f"only {len(self.declared)} scripts declare a read-only form")
        self.assertGreaterEqual(len(self.with_flag), 15,
                                f"only {len(self.with_flag)} read-only call sites found -- the "
                                "table reader broke, so 'uninvoked' would be meaningless")
        for name in self.INVOKED_WITH_A_FLAG:
            if name not in self.declared:
                continue      # `verify_projection_freshness.py` itself declares none
            self.assertIn(name, self.with_flag,
                          f"{name} has a read-only form that this scan cannot find invoked -- "
                          "the predicate broke, the script is not un-checked")

    def test_the_predicate_fires_on_a_call_shape_and_not_on_a_mention(self) -> None:
        planted = ('run_gate("scripts/invented_gate.py", ["--check"])\n'
                   'EXEMPT = {"invented_gate.py": "one-off, and this line says --check in prose"}\n')
        found = [name for name, argv in self.call_sites_in(planted)
                 if any(flag in self.READ_ONLY_FLAGS for flag in argv)]
        self.assertEqual(found, ["invented_gate.py"],
                         "a prose mention must not count as an invocation")


    def test_every_read_only_form_is_invoked_or_declared_with_its_measured_verdict(self) -> None:
        unexplained = [name for name in self.uninvoked if name not in self.DECLARED_BUT_UNINVOKED]
        self.assertEqual(unexplained, [],
                         f"{unexplained} declare a read-only form that no CI table, chain entry or "
                         "test ever invokes -- wire it in or record the measured verdict that "
                         "explains why it cannot be required yet")

    def test_no_declaration_has_gone_stale_or_been_wired_already(self) -> None:
        stale = sorted(name for name in self.DECLARED_BUT_UNINVOKED if name not in self.declared)
        self.assertEqual(stale, [], "declared for a script that no longer has that read-only form")
        wired = sorted(name for name in self.DECLARED_BUT_UNINVOKED if name not in set(self.uninvoked))
        self.assertEqual(wired, [],
                         "declared as uninvoked but something invokes its read-only form now; "
                         "delete the row and it becomes a required check")

    def test_each_declaration_states_a_verdict_not_an_apology(self) -> None:
        for name, reason in self.DECLARED_BUT_UNINVOKED.items():
            self.assertGreater(len(reason), 60, f"{name} has a placeholder reason")
            self.assertTrue(re.search(r"=|rc=", reason),
                            f"{name}'s reason names no measured verdict: {reason[:80]}")


if __name__ == '__main__':
    unittest.main()
