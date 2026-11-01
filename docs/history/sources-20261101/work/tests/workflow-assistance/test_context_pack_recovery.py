"""C1 recovery tests: the Context Pack must recover machine-truth state, not
silently skip or reconstruct missing material, and must not promote an
unmerged PR / a historical path / a no-receipt task into "done".

Negative controls required by prompt C1:
  * an unmerged PR must not be presented as main;
  * a historical/archived path must not be presented as a current path;
  * a task without a receipt must not be presented as completed;
  * after a session/executor change the critical constraints must survive;
  * a successful generation is NOT proof of a complete recovery.
"""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages/client-neutral-core" / "scripts" / "build_context_pack.py"
sys.path.insert(0, str(SCRIPT.parent))

import project_temp  # noqa: E402


def load_module():
    spec = importlib.util.spec_from_file_location("build_context_pack", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _git(root: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=root, check=False, capture_output=True,
                   text=True, encoding="utf-8", errors="replace")


def _make_tmp_repo() -> Path:
    # A nested `git init` inside the ignored runtime root is still its own toplevel, which is what
    # `build_context_pack.git_root()` resolves; the release goes through `project_temp` because these
    # five fixtures used to depend on a rmtree that ignored its own WinError 5.
    tmp = project_temp.fixture_dir(prefix="wl-context-pack-")
    _git(tmp, "init", "-q")
    _git(tmp, "config", "user.email", "test@local")
    _git(tmp, "config", "user.name", "test")
    # build_context_pack (not write_context_pack) is called directly, so no
    # git-ignored-output check runs on the temp repo.
    return tmp


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


class AuthorityMaterialsFromIndexTests(unittest.TestCase):
    """C1: the material set is resolved from the authority index, not a second
    hand-written path list."""

    def test_index_declared_materials_are_resolved(self) -> None:
        module = load_module()
        tmp = _make_tmp_repo()
        try:
            index = {
                "topHumanAuthority": "WORK-LAB-AUTHORITY.md",
                "topMachineAuthority": ".project/governance/project-authority-index.json",
                "scopedAuthorities": {"taskpack": ".project/governance/taskpack-authority-index.json"},
                "currentTaskpack": "taskpacks/current/CURRENT-TASKPACK.md",
                "currentOpenTaskRegister": "taskpacks/current/OPEN-TASK-REGISTER.md",
            }
            _write(tmp / ".project/governance/project-authority-index.json", json.dumps(index))
            _git(tmp, "add", ".")
            _git(tmp, "commit", "-q", "-m", "seed")
            materials = module.authority_materials(tmp)
            for declared in (
                "WORK-LAB-AUTHORITY.md",
                ".project/governance/project-authority-index.json",
                ".project/governance/taskpack-authority-index.json",
                "taskpacks/current/CURRENT-TASKPACK.md",
                "taskpacks/current/OPEN-TASK-REGISTER.md",
            ):
                self.assertIn(declared, materials, f"index-declared material not resolved: {declared}")
        finally:
            project_temp.force_release(tmp)


class MissingMaterialExplicitTests(unittest.TestCase):
    """A declared-but-missing material is marked MISSING, never silently
    dropped and never reconstructed from memory."""

    def test_missing_declared_material_is_marked_not_reconstructed(self) -> None:
        module = load_module()
        tmp = _make_tmp_repo()
        try:
            index = {
                "topHumanAuthority": "WORK-LAB-AUTHORITY.md",
                "topMachineAuthority": ".project/governance/project-authority-index.json",
                "currentTaskpack": "taskpacks/current/CURRENT-TASKPACK.md",
                "currentOpenTaskRegister": "taskpacks/current/OPEN-TASK-REGISTER.md",
            }
            _write(tmp / ".project/governance/project-authority-index.json", json.dumps(index))
            # Only TWO of the declared files actually exist:
            _write(tmp / "WORK-LAB-AUTHORITY.md", "# top authority\n")
            _write(tmp / "taskpacks/current/OPEN-TASK-REGISTER.md", "# register\n")
            # currentTaskpack is declared but absent.
            _git(tmp, "add", ".")
            _git(tmp, "commit", "-q", "-m", "seed")
            pack = module.build_context_pack(tmp, max_chars=module.HARD_MAX_CHARS)
            self.assertIn("## Missing Materials", pack, "missing materials must be explicitly surfaced")
            self.assertIn("MISSING `taskpacks/current/CURRENT-TASKPACK.md`", pack)
            # Present material is excerpted; missing material is NOT.
            self.assertIn("## Excerpt: `WORK-LAB-AUTHORITY.md`", pack)
            self.assertNotIn("## Excerpt: `taskpacks/current/CURRENT-TASKPACK.md`", pack)
        finally:
            project_temp.force_release(tmp)


class RecoveryChecklistSentinelTests(unittest.TestCase):
    """The pack must carry the recovery sentinels: generation success !=
    recovery complete; an unmerged PR is not main; a no-receipt task is not
    done; a historical path is not a current path."""

    def test_recovery_checklist_sentinels_present(self) -> None:
        module = load_module()
        tmp = _make_tmp_repo()
        try:
            _write(tmp / "README.md", "# x\n")
            _git(tmp, "add", ".")
            _git(tmp, "commit", "-q", "-m", "seed")
            pack = module.build_context_pack(tmp, max_chars=module.HARD_MAX_CHARS)
            self.assertIn("## Recovery Checklist", pack)
            self.assertIn("generation success != recovery complete", pack)
            self.assertIn("an unmerged PR is not main", pack)
            self.assertIn("A historical or archived path is not a current path", pack)
            self.assertIn("without a receipt is not complete", pack)
        finally:
            project_temp.force_release(tmp)


class CriticalConstraintSurvivalTests(unittest.TestCase):
    """After a session/executor change the critical constraints (owner,
    forbidden roots, single-writer) must re-derive from machine truth, not
    from prose memory."""

    def test_critical_constraints_rederive_from_machine_truth(self) -> None:
        module = load_module()
        tmp = _make_tmp_repo()
        try:
            ownership = {
                "singleWriter": True,
                "modules": {
                    "workflow-assistance": {"path": "packages/client-neutral-core", "owner": "workflow"},
                },
                "rootOwnedPaths": [".project/governance"],
            }
            boundary = {"forbiddenExternalRoots": ["E:", "F:"], "runtimeRoot": ".project-local"}
            _write(tmp / ".project/governance/module-ownership.json", json.dumps(ownership))
            _write(tmp / ".project/governance/project-data-boundary.json", json.dumps(boundary))
            _git(tmp, "add", ".")
            _git(tmp, "commit", "-q", "-m", "seed")
            pack = module.build_context_pack(tmp, max_chars=module.HARD_MAX_CHARS)
            self.assertIn("## Critical Constraints (must survive compression)", pack)
            self.assertIn("Single-writer checkout: yes", pack)
            self.assertIn("Module workflow-assistance: root `packages/client-neutral-core`", pack)
            self.assertIn("`E:`", pack)
            self.assertIn("`F:`", pack)
            self.assertIn("`.project-local`", pack)
        finally:
            project_temp.force_release(tmp)


class SkillCountLiveTests(unittest.TestCase):
    """Skill count is derived from the live inventory, never a fixed
    historical number."""

    def test_skill_inventory_reads_live_module_root(self) -> None:
        module = load_module()
        tmp = _make_tmp_repo()
        try:
            ownership = {"modules": {"workflow-assistance": {"path": "packages/client-neutral-core", "owner": "workflow"}}}
            _write(tmp / ".project/governance/module-ownership.json", json.dumps(ownership))
            # Two live skills on disk:
            _write(tmp / "packages/client-neutral-core/skills/a/SKILL.md", "# a\n")
            _write(tmp / "packages/client-neutral-core/skills/b/SKILL.md", "# b\n")
            _git(tmp, "add", ".")
            _git(tmp, "commit", "-q", "-m", "seed")
            skills = module.skill_inventory(tmp)
            self.assertEqual(len(skills), 2, f"live skill count expected 2, got {len(skills)}")
            # Add a third: the count must track it (not stay fixed).
            _write(tmp / "packages/client-neutral-core/skills/c/SKILL.md", "# c\n")
            self.assertEqual(len(module.skill_inventory(tmp)), 3)
        finally:
            project_temp.force_release(tmp)


if __name__ == "__main__":
    unittest.main()


class BudgetDisciplineTests(unittest.TestCase):
    """W08 (2026-10-15): the budget removes WHOLE sections and names them, or it refuses.

    The defect this class pins: the pack used to cut the rendered string at the budget, so the tail of the
    text disappeared and the digest had been computed before that cut -- a pack could quote a SHA for a text
    nobody would ever read, and the recovery checklist (the section that says what a receiver must NOT assume)
    could be the part that vanished.
    """

    def _fixture(self) -> tuple[object, Path]:
        module = load_module()
        tmp = _make_tmp_repo()
        index = {
            "topHumanAuthority": "WORK-LAB-AUTHORITY.md",
            "topMachineAuthority": ".project/governance/project-authority-index.json",
            "currentTaskpack": "taskpacks/current/CURRENT-TASKPACK.md",
            "currentOpenTaskRegister": "taskpacks/current/OPEN-TASK-REGISTER.md",
        }
        _write(tmp / ".project/governance/project-authority-index.json", json.dumps(index))
        # Enough excerpt material that a budget cut has something to drop.
        _write(tmp / "WORK-LAB-AUTHORITY.md", "# top authority\n" + "authority line\n" * 200)
        _write(tmp / "taskpacks/current/CURRENT-TASKPACK.md", "# taskpack\n" + "task line\n" * 100)
        _write(tmp / "taskpacks/current/OPEN-TASK-REGISTER.md", "# register\n" + "register line\n" * 100)
        _git(tmp, "add", ".")
        _git(tmp, "commit", "-q", "-m", "seed")
        return module, tmp

    def test_sections_are_dropped_whole_and_named_never_cut(self) -> None:
        module, tmp = self._fixture()
        try:
            full = module.build_context_pack(tmp, max_chars=module.HARD_MAX_CHARS)
            pack = module.build_context_pack(tmp, max_chars=len(full) - 400)
            self.assertNotIn("[context pack truncated", pack, "a prefix cut is not an omission")
            self.assertIn("## Omitted Sections", pack, "dropped sections must be declared by name")
            # Only the sections this fixture actually produces: the tmp repo has no module-ownership or
            # boundary contract, so `Critical Constraints` is legitimately absent here. Asserting a section
            # the fixture cannot build would be a test of the fixture, not of the budget.
            for sentinel in ("## Safety Boundary", "## Current Task State (live register head)",
                             "## Recovery Checklist"):
                self.assertIn(sentinel, pack, f"required section must survive the budget: {sentinel}")
            self.assertLessEqual(len(pack), len(full) - 400)
        finally:
            project_temp.force_release(tmp)

    def test_a_budget_too_small_for_the_names_still_declares_the_count(self) -> None:
        """The detail may degrade; the fact of the omission may not.

        The tightest renderable budget is found by bisection instead of a guessed offset: the two tiers differ
        by how much room the omission list has, so a fixed `len(full) - N` lands in whichever tier the fixture
        happens to fall into, and then the test measures the fixture rather than the rule.
        """
        module, tmp = self._fixture()
        try:
            full = module.build_context_pack(tmp, max_chars=module.HARD_MAX_CHARS)

            def renders(budget: int) -> bool:
                try:
                    module.build_context_pack(tmp, max_chars=budget)
                    return True
                except SystemExit:
                    return False

            low, high = 300, len(full)
            while low < high:
                mid = (low + high) // 2
                if renders(mid):
                    high = mid
                else:
                    low = mid + 1
            pack = module.build_context_pack(tmp, max_chars=low)
            self.assertTrue(renders(low) and not renders(low - 1), "bisection must land on the boundary")
            self.assertIn("omitted", pack, "the omission must still be declared at the tightest budget")
            self.assertNotIn("[context pack truncated", pack)
        finally:
            project_temp.force_release(tmp)

    def test_a_budget_below_the_required_set_refuses_by_name(self) -> None:
        module, tmp = self._fixture()
        try:
            with self.assertRaises(SystemExit) as caught:
                module.build_context_pack(tmp, max_chars=300)
            self.assertIn("CONTEXT_PACK_REQUIRED_EXCEEDS_BUDGET", str(caught.exception))
        finally:
            project_temp.force_release(tmp)

    def test_the_two_digests_are_different_identities(self) -> None:
        """The rendered digest must recompute from what was rendered; the candidate names the full set."""
        import hashlib
        import re

        module, tmp = self._fixture()
        try:
            full = module.build_context_pack(tmp, max_chars=module.HARD_MAX_CHARS)
            pack = module.build_context_pack(tmp, max_chars=len(full) - 600)
            rendered = re.search(r"rendered\): `([0-9a-f]{16})`", pack)
            candidate = re.search(r"before declared omission\): `([0-9a-f]{16})`", pack)
            self.assertIsNotNone(rendered)
            self.assertIsNotNone(candidate)
            blanked = "\n".join(line for line in pack.splitlines()
                                if not line.startswith("- Generated UTC:"))
            blanked = blanked.replace(rendered.group(1), "").replace(candidate.group(1), "")
            self.assertEqual(hashlib.sha256(blanked.encode()).hexdigest()[:16], rendered.group(1),
                             "the rendered digest must describe the rendered text")
            self.assertNotEqual(rendered.group(1), candidate.group(1),
                                "a pack that dropped sections has two different texts and needs two digests")
        finally:
            project_temp.force_release(tmp)
