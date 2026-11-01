"""A03: negative controls for the authority-reference verifier.

Each test mutates a throwaway copy of the repository's authority package under the project-local
runtime root (`.project-local/runs/`, git-ignored) and asserts the verifier fails closed with the
exact named reason. The live repository is never mutated, and no copy is ever written to the system
temp directory — an earlier version used a bare `mkdtemp(prefix="auth-ref-")`, whose `ignore_errors`
teardown left nineteen mirrors of the governance package in %TEMP%, outside the project boundary
(ERR-140).
"""
from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VERIFIER = ROOT / "scripts" / "ci" / "verify_project_authority_reference.py"

# Minimal authority files the verifier requires, copied into the fixture.
_REQUIRED = [
    "WORK-LAB-AUTHORITY.md",
    ".project/governance/project-authority-index.json",
    ".project/governance/taskpack-authority-index.json",
    ".project/governance/module-ownership.json",
    "taskpacks/current/OPEN-TASK-REGISTER.md",
]


def _load_verifier():
    spec = importlib.util.spec_from_file_location("verify_project_authority_reference", VERIFIER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _runtime_root() -> Path:
    """The git-ignored in-boundary runtime root, auto-created (same convention the other suites use)."""
    p = ROOT / ".project-local" / "runs"
    p.mkdir(parents=True, exist_ok=True)
    return p


def _make_fixture() -> Path:
    """Copy the live authority package into a fixture root that verifies clean.

    `dir=` is mandatory: without it the fixture lands in the system temp directory, outside the
    project boundary declared by .project/governance/project-data-boundary.json.
    """
    tmp = Path(tempfile.mkdtemp(prefix="auth-ref-", dir=_runtime_root()))
    # Build the fixture from live files so it reflects the real package.
    for rel in _REQUIRED:
        source = ROOT / rel
        target = tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_file():
            shutil.copy2(source, target)
    # The allowlist files declared by the project index must exist in the
    # fixture for the clean copy to pass check 6.
    pidx = json.loads((tmp / ".project/governance/project-authority-index.json").read_text(encoding="utf-8"))
    for entry in pidx.get("operationalCompatibilityAllowlist", []):
        src = ROOT / entry["path"]
        dst = tmp / entry["path"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            shutil.copy2(src, dst)
    # The CURRENT taskpack file must exist under taskpacks/current/.
    tidx = json.loads((tmp / ".project/governance/taskpack-authority-index.json").read_text(encoding="utf-8"))
    current = tidx["classification"]["CURRENT"]
    assert len(current) == 1
    live_current = ROOT / "taskpacks" / "current" / f"{current[0]}.md"
    dest = tmp / "taskpacks" / "current" / f"{current[0]}.md"
    dest.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(live_current, dest)
    # P0-01: referenced paths the index points at (decisions[].path/ledger and
    # staticHandoffViews[].entry_record) must exist in the fixture so the clean
    # copy passes check 6b. Copy each live target that exists.
    referenced = []
    for decision in tidx.get("decisions", []):
        if not isinstance(decision, dict):
            continue
        for key in ("path", "ledger"):
            value = decision.get(key)
            if isinstance(value, str) and value:
                referenced.append(value)
    for view in tidx.get("staticHandoffViews", []):
        if not isinstance(view, dict):
            continue
        entry_record = view.get("entry_record")
        if isinstance(entry_record, str) and entry_record:
            referenced.append(entry_record)
    for rel in referenced:
        src = ROOT / rel
        dst = tmp / rel
        dst.parent.mkdir(parents=True, exist_ok=True)
        if src.is_file():
            shutil.copy2(src, dst)
    # P0-03: current task cards declared by the index (and the registry they
    # bind against) must exist in the fixture for the clean copy to pass.
    for card in tidx.get("currentTaskCards", []):
        if isinstance(card, dict) and isinstance(card.get("path"), str):
            src = ROOT / card["path"]
            dst = tmp / card["path"]
            dst.parent.mkdir(parents=True, exist_ok=True)
            if src.is_file():
                shutil.copy2(src, dst)
    reg_src = ROOT / ".project" / "governance" / "future-candidate-registry.json"
    if reg_src.is_file():
        dst = tmp / ".project/governance/future-candidate-registry.json"
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reg_src, dst)
    return tmp


def _read(tmp: Path, rel: str) -> dict:
    return json.loads((tmp / rel).read_text(encoding="utf-8"))


def _write(tmp: Path, rel: str, data: dict) -> None:
    (tmp / rel).write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


class AuthorityReferenceNegativeTests(unittest.TestCase):
    def setUp(self) -> None:
        self.verifier = _load_verifier()
        self.tmp = _make_fixture()
        try:
            # fixture sanity: the unmutated copy must PASS.
            self.assertEqual(self.verifier.verify(self.tmp), 0)
        finally:
            pass

    def tearDown(self) -> None:
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_clean_fixture_passes(self) -> None:
        self.assertEqual(self.verifier.verify(self.tmp), 0)

    def test_missing_top_authority_fails(self) -> None:
        (self.tmp / "WORK-LAB-AUTHORITY.md").unlink()
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_project_index_missing_fails(self) -> None:
        (self.tmp / ".project/governance/project-authority-index.json").unlink()
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_multiple_current_taskpacks_fail(self) -> None:
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        tidx["classification"]["CURRENT"].append("SOME-OTHER-TASKPACK")
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_current_taskpack_file_missing_fails(self) -> None:
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        current = tidx["classification"]["CURRENT"][0]
        (self.tmp / "taskpacks/current" / f"{current}.md").unlink()
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_open_register_missing_fails(self) -> None:
        (self.tmp / "taskpacks/current/OPEN-TASK-REGISTER.md").unlink()
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_frozen_history_marked_normative_fails(self) -> None:
        # A frozen/historical record must not be promoted to the current taskpack.
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        tidx["classification"]["CURRENT"] = ["WORK-LAB-FROZEN-LEGACY-INDEX-20260918"]
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_forbidden_root_reactivation_fails(self) -> None:
        mo = _read(self.tmp, ".project/governance/module-ownership.json")
        # Re-declare a forbidden legacy root as a live module root.
        mo["modules"]["legacy-regression"] = {
            "path": "50-taskpacks",
            "owner": "workflow",
            "releasePrefix": "workflow",
        }
        _write(self.tmp, ".project/governance/module-ownership.json", mo)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_dangling_allowlist_reference_fails(self) -> None:
        pidx = _read(self.tmp, ".project/governance/project-authority-index.json")
        pidx.setdefault("operationalCompatibilityAllowlist", []).append(
            {"path": "taskpacks/current/DOES-NOT-EXIST.md", "role": "x"}
        )
        _write(self.tmp, ".project/governance/project-authority-index.json", pidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_project_index_invalid_json_fails(self) -> None:
        (self.tmp / ".project/governance/project-authority-index.json").write_text("{not json", encoding="utf-8")
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    # --- P0-01 negative controls -------------------------------------------------
    def test_dangling_index_reference_fails(self) -> None:
        # A decision points at a tracked path that does not exist on disk.
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        tidx["decisions"].append(
            {"id": "DANGLING", "path": "taskpacks/current/DOES-NOT-EXIST-P001.md", "status": "OPEN"}
        )
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_index_admits_missing_references_fails(self) -> None:
        # The index itself declares indexReferencesExist=false -> fail closed.
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        tidx.setdefault("acceptance", {})["indexReferencesExist"] = False
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_supersedes_partition_conflict_fails(self) -> None:
        # A taskpack sits in two classification buckets (CURRENT + SUPERSEDED).
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        current_id = tidx["classification"]["CURRENT"][0]
        tidx["classification"]["SUPERSEDED"].append(current_id)
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    # --- P0-03 negative controls (subordinate current task cards) ----------
    def _with_card(self, card) -> None:
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        tidx["currentTaskCards"] = [card]
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)

    def test_task_card_missing_on_disk_fails(self) -> None:
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        tidx["currentTaskCards"] = [
            {"id": "X-1", "path": "taskpacks/current/DOES-NOT-EXIST-CARD.md"}
        ]
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_task_card_not_in_register_fails(self) -> None:
        card_path = self.tmp / "taskpacks/current/ADHOC-CARD.md"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(
            "PLANNED card, no execution authority; execution stays OPEN pending "
            "per-operation user authorization.", encoding="utf-8")
        self._with_card({"id": "ADHOC-CARD", "path": "taskpacks/current/ADHOC-CARD.md"})
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_task_card_self_claims_authority_fails(self) -> None:
        card_path = self.tmp / "taskpacks/current/ADHOC-CARD.md"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(
            "This card is the TOP-LEVEL AUTHORITY of this repository and grants "
            "execution authority without further approval. no execution authority",
            encoding="utf-8")
        reg = self.tmp / "taskpacks/current/OPEN-TASK-REGISTER.md"
        reg.write_text(reg.read_text(encoding="utf-8")
                       + "\nADHOC-CARD taskpacks/current/ADHOC-CARD.md\n",
                       encoding="utf-8")
        self._with_card({"id": "ADHOC-CARD", "path": "taskpacks/current/ADHOC-CARD.md"})
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_task_card_without_deferral_marker_fails(self) -> None:
        card_path = self.tmp / "taskpacks/current/ADHOC-CARD.md"
        card_path.parent.mkdir(parents=True, exist_ok=True)
        card_path.write_text(
            "# ADHOC CARD\nThis card immediately executes and applies changes "
            "with full authority.\n", encoding="utf-8")
        reg = self.tmp / "taskpacks/current/OPEN-TASK-REGISTER.md"
        reg.write_text(reg.read_text(encoding="utf-8")
                       + "\nADHOC-CARD taskpacks/current/ADHOC-CARD.md\n",
                       encoding="utf-8")
        self._with_card({"id": "ADHOC-CARD", "path": "taskpacks/current/ADHOC-CARD.md"})
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_task_card_registry_binding_conflict_fails(self) -> None:
        # Orca card's declared registry_entry is FUT-001; point it at FUT-002
        # whose task_card does not reference this card path -> conflict.
        card = {
            "id": "ORCA-PILOT-TASK-CARD-20260925",
            "path": "taskpacks/current/ORCA-PILOT-TASK-CARD-20260925.md",
            "registry_entry": "FUT-002",
        }
        self._with_card(card)
        self.assertEqual(self.verifier.verify(self.tmp), 1)

    def test_task_card_in_taskpack_bucket_fails(self) -> None:
        tidx = _read(self.tmp, ".project/governance/taskpack-authority-index.json")
        card = {
            "id": "ORCA-PILOT-TASK-CARD-20260925",
            "path": "taskpacks/current/ORCA-PILOT-TASK-CARD-20260925.md",
            "registry_entry": "FUT-001",
        }
        tidx["currentTaskCards"] = [card]
        # Reclassify the card id into the HISTORICAL taskpack bucket.
        tidx["classification"]["HISTORICAL"].append("ORCA-PILOT-TASK-CARD-20260925")
        _write(self.tmp, ".project/governance/taskpack-authority-index.json", tidx)
        self.assertEqual(self.verifier.verify(self.tmp), 1)


if __name__ == "__main__":
    unittest.main()
