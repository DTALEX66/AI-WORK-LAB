# SPDX-License-Identifier: MIT
"""V30: the three probes that `audit_objective_closure.py` owns must be able to say FAIL.

The terminal closure audit had no test behind it. That is the worst possible combination: a script
whose whole job is to decide whether the repository may be called closed, judged by nobody. Each node
below drives a probe at a throwaway checkout built by the node itself, so the only variable is the
condition the probe is supposed to detect -- and two of the five nodes assert the *passing* side of
the same rule, which is what makes the failing side mean something.

Why the fixtures live here and not in the real tree: the receipt clause was tightened on 2026-11-01
from "the receipt names this exact commit" (unsatisfiable -- rebinding the registers and rendering
the audit section necessarily produce commits *after* the measured one, so the clause would sit at
PENDING forever) to "the receipt's commit is an ancestor of HEAD, and everything that moved since it
is a document or a generated register, named one by one". The narrower allowance is only narrower if
a code file appearing in that range is actually a FAIL, and that is what is shown here.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TARGET_ROOT / "scripts"))
import audit_objective_closure as audit  # noqa: E402

RECEIPT_RELATIVE = Path(".project-local") / "audit" / "20261031-fullclosure" / "CLOSURE-STATE.json"
GIT_IDENTITY = ["-c", "user.name=closure-fixture", "-c", "user.email=closure@fixture.invalid"]


def _git(root: Path, *args: str) -> str:
    completed = subprocess.run(["git", *GIT_IDENTITY, *args], cwd=str(root),
                               capture_output=True, text=True, encoding="utf-8",
                               errors="replace", timeout=300)
    assert completed.returncode == 0, (args, completed.stdout, completed.stderr)
    return completed.stdout.strip()


def _checkout(tmp_path: Path, name: str = "repo") -> Path:
    root = tmp_path / name
    root.mkdir(parents=True)
    _git(root, "init", "-q", "-b", "main")
    (root / "scripts").mkdir(parents=True, exist_ok=True)
    (root / "docs").mkdir(parents=True, exist_ok=True)
    (root / ".gitignore").write_text(".project-local/\n", encoding="utf-8", newline="\n")
    (root / "scripts" / "a.py").write_text("VALUE = 1\n", encoding="utf-8", newline="\n")
    (root / "docs" / "base.md").write_text("# base\n", encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "base")
    return root


def _write_receipt(root: Path, head_commit: str, **overrides) -> str:
    """Drop a receipt where the real producer would put it, so the probe reads it as-is."""
    receipt = {"head_commit": head_commit, "candidate_digest": "0123456789abcdef" * 4,
               "candidate_files": 12,
               "suite": {"line": "42 passed in 1.00s", "passed": 42, "failed": 0, "errors": 0,
                         "failed_nodes": [], "error_nodes": []},
               "measurement_integrity": {"tracked_tree_clean_at_start": True,
                                         "tracked_bytes_moved_during_run": []}}
    for key, value in overrides.items():
        if key == "suite":
            receipt["suite"].update(value)
        else:
            receipt[key] = value
    path = root / RECEIPT_RELATIVE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(receipt, ensure_ascii=False), encoding="utf-8", newline="\n")
    return head_commit


def _touch_and_commit(root: Path, relative: str, commit: str) -> str:
    (root / relative).parent.mkdir(parents=True, exist_ok=True)
    (root / relative).write_text("moved\n", encoding="utf-8", newline="\n")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", commit)
    return _git(root, "rev-parse", "HEAD")


def test_documents_committed_after_the_receipt_keep_the_clause_green(tmp_path):
    """The allowance exists so the rebind can be shipped; using it must not read as a defect."""
    root = _checkout(tmp_path)
    measured = _git(root, "rev-parse", "HEAD")
    _write_receipt(root, measured)
    _touch_and_commit(root, "docs/CODEX-AUDIT-ENTRY.md", "render the measured section")
    _touch_and_commit(root, "migration/audit-item-closure.csv", "rebind the register")
    verdict = audit.probe_receipt_describes_this_commit(root)
    assert verdict["status"] == "PASS", verdict
    assert set(verdict["commited_after_receipt_documents_and_registers_only"]) == {
        "docs/CODEX-AUDIT-ENTRY.md", "migration/audit-item-closure.csv"}, verdict
    assert verdict["receipt_commit"] != verdict["head"], (
        "PASS must be reachable while the receipt names an ancestor, not only the exact commit")


def test_code_committed_after_the_receipt_turns_the_clause_red(tmp_path):
    """A fix landed after the measurement: the suite that ran cannot have contained it.

    This is the whole point of tightening the clause. Without this branch, "the receipt is an
    ancestor of HEAD" would let a changed gate or a changed test ride on a green measurement taken
    before it existed -- a PASS that reports on bytes never run.
    """
    root = _checkout(tmp_path)
    measured = _git(root, "rev-parse", "HEAD")
    _write_receipt(root, measured)
    _touch_and_commit(root, "scripts/a.py", "fix shipped after the measurement")
    verdict = audit.probe_receipt_describes_this_commit(root)
    assert verdict["status"] == "FAIL", verdict
    assert verdict["unexpected"] == ["scripts/a.py"], verdict


def test_a_receipt_whose_suite_recorded_failures_is_a_fail_not_a_pending(tmp_path):
    root = _checkout(tmp_path)
    measured = _git(root, "rev-parse", "HEAD")
    _write_receipt(root, measured, suite={"failed": 2, "failed_nodes": [
        "tests/unified/test_v30.py::test_documents_committed_after_the_receipt_keep_the_clause_green",
        "tests/unified/test_v30.py::test_code_committed_after_the_receipt_turns_the_clause_red"]})
    verdict = audit.probe_receipt_describes_this_commit(root)
    assert verdict["status"] == "FAIL", verdict
    assert len(verdict["failed_nodes"]) == 2, (
        "the receipt's own failure list is what a reviewer re-runs; losing it here is how a red "
        "suite gets flattened into an uninformative status")


def test_a_receipt_naming_a_diverged_commit_is_rejected(tmp_path):
    """Ancestor-ness, not 'is a commit in this repo': a receipt from a branch that was never merged
    describes a candidate HEAD does not contain, and would otherwise still read as PASS."""
    root = _checkout(tmp_path)
    measured = _git(root, "rev-parse", "HEAD")
    _touch_and_commit(root, "docs/side.md", "side branch commit")
    _git(root, "checkout", "-q", "-b", "other", measured)
    _touch_and_commit(root, "docs/other.md", "divergent commit")
    # the receipt names the side-branch commit, which HEAD does not descend from
    side = subprocess.run(["git", *GIT_IDENTITY, "rev-parse", "main"], cwd=str(root),
                          capture_output=True, text=True).stdout.strip()
    _write_receipt(root, side)
    verdict = audit.probe_receipt_describes_this_commit(root)
    assert verdict["status"] == "FAIL", verdict
    assert "祖先" in verdict["reason"], verdict


def test_uncommitted_tracked_edits_are_refused_before_any_binding_is_claimed(tmp_path):
    """A green receipt over a dirty worktree certifies bytes no commit -- and no run -- contains.

    The clause can only be this strict because the real producer refuses to start on a tracked-dirty
    tree (exit 3) and records `tracked_bytes_moved_during_run`; the probe reads both, so a hand-made
    or half-committed audit gets named file by file instead of a bare status.
    """
    root = _checkout(tmp_path)
    head = _git(root, "rev-parse", "HEAD")
    _write_receipt(root, head)
    assert audit.probe_receipt_describes_this_commit(root)["status"] == "PASS"
    (root / "scripts" / "a.py").write_text("VALUE = 2\n", encoding="utf-8", newline="\n")
    verdict = audit.probe_receipt_describes_this_commit(root)
    assert verdict["status"] == "FAIL", verdict
    assert verdict["uncommitted_tracked_files"] == ["scripts/a.py"], verdict


def test_the_raster_probe_fails_on_a_tracked_image_under_the_history_area(tmp_path):
    """Owner rule 「截图照片去掉」 has to be enforceable, not just stated.

    The same probe is then run against a checkout that carries only a text file: the PASS side is
    asserted too, because a probe whose detection path is broken reports PASS on every tree.
    """
    root = _checkout(tmp_path, "with_image")
    image = root / "docs" / "history" / "shot.png"
    image.parent.mkdir(parents=True, exist_ok=True)
    image.write_bytes(b"\x89PNG\r\n\x1a\n" + b"not really a png")
    _git(root, "add", "-A")
    _git(root, "commit", "-q", "-m", "a tracked screenshot")
    verdict = audit.probe_raster_not_tracked(root)
    assert verdict["status"] == "FAIL", verdict
    assert verdict["tracked_raster_count"] == 1, verdict

    clean = audit.probe_raster_not_tracked(_checkout(tmp_path, "without_image"))
    assert clean["status"] == "PASS", clean
