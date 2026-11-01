"""A shipped derived projection must equal what the tree measures today, not what it measured once.

This repository has been bitten by the ordering before (ERR-151: an inventory digest taken before `git add`;
ERR-161: a receipt that stamped the head at write time). Measured again 2026-10-08: commit 7b5a4502 shipped
two derived artifacts that contradicted its own tree. Reproduced by running this module inside a detached
worktree at that commit -- 2 failures:

* `docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json` published the operand
  `reports/audit-archive` as GONE, but that same commit added `reports/audit-archive/FROZEN-MANIFEST.json`,
  which makes it DIR_NOT_FILE (a tracked directory is not a file promise). The artifact had been measured
  before those bytes were staged.
* `docs/audits/TOOL_INVENTORY_2026-10-07.json` published 5 citing surfaces for
  `scripts/audit/generate_frozen_surface_manifest.py` where that same commit's tree yields 6. The missing
  citation is the inventory itself: it scans its own file, so the first publication of a newly added tool is
  stale by exactly that self-citation and only converges once the artifact is republished. The freshness
  check is what forces that second publish inside the same commit; excluding the self-citation is the owed
  alternative (ERR-222).

The canonical gate came back green at that head (.project-local/runs/gate-frozen/gate-verify-7b5a4502.log),
so nothing in the suite could tell a current measurement from a file that once said OK.

These tests are that missing check. Each generator runs once per module, into a temporary directory, and the
result is compared against the committed bytes -- ignoring only the fields that name the moment of
measurement. A red here means the committed artifact is stale; it cannot mean the tree moved under the test,
because a separate assertion proves the redirected runs never touched the repository.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path
from shutil import rmtree
from tempfile import mkdtemp

REPO = Path(__file__).resolve().parents[2]
RUNS = REPO / ".project-local" / "runs"
# `.project-local/` is git-ignored, so a clean checkout -- CI, another machine, a detached worktree -- has
# no such directory. Creating it here is the difference between a control and a crash: measured 2026-10-08,
# the first version of this module died in setUpModule inside a fresh worktree with WinError 3.
RUNS.mkdir(parents=True, exist_ok=True)

# Fields that name when, or in what mode, the tool ran -- never what the tree contains. The list is short
# and one test pins it: a generator that quietly started publishing content under one of these names would
# otherwise be excused by its own comparison.
VOLATILE = {"at", "apply", "generatedAt", "generated_at", "generatedFromCommit", "generatedFromTree"}

SHIPPED = {
    "targets": REPO / "docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json",
    "inventory": REPO / "docs/audits/TOOL_INVENTORY_2026-10-07.json",
    "state": REPO / ".project/governance/generated/CURRENT_STATE.json",
    "stateMd": REPO / ".project/governance/generated/CURRENT_STATE.md",
}

# Measured here: the inventory digest costs ~34s because it asks git about every tracked tool, while the
# other two generators finish in a tenth of a second. So each runs exactly once per module and every test
# reads the cached bytes rather than re-invoking it.
FRESH: dict[str, Path] = {}
COMMITTED: dict[str, bytes] = {}
AFTER: dict[str, bytes] = {}
TMP = Path()


def brief(value: object) -> str:
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return text if len(text) <= 90 else text[:87] + "..."


def _child(path: str, key: str) -> str:
    return f"{path}.{key}" if path else key


def _element(path: str, index: int) -> str:
    return f"{path}[{index}]" if path else f"[{index}]"


def json_drift(shipped: object, fresh: object, path: str = "") -> list[str]:
    """Differences that are about content, not about the moment of measurement.

    Lists are walked element by element. Measured 2026-10-08: the first real drift this control caught was a
    citation list whose length moved by one, and an elementwise comparison would have printed the two
    identical-looking prefixes of a 60-character brief -- a report that names the index is what makes the
    red actionable instead of mysterious.
    """
    if isinstance(shipped, dict) and isinstance(fresh, dict):
        found: list[str] = []
        for key in sorted(set(shipped) | set(fresh)):
            if key in VOLATILE:
                continue
            here = _child(path, key)
            if key not in shipped:
                found.append(f"{here} ONLY_IN_FRESH={brief(fresh[key])}")
            elif key not in fresh:
                found.append(f"{here} ONLY_IN_SHIPPED={brief(shipped[key])}")
            else:
                found.extend(json_drift(shipped[key], fresh[key], here))
        return found
    if isinstance(shipped, list) and isinstance(fresh, list):
        if len(shipped) != len(fresh):
            return [f"{path} LENGTH shipped={len(shipped)} fresh={len(fresh)} "
                    f"tail_shipped={brief(shipped[-1:] or [''])} tail_fresh={brief(fresh[-1:] or [''])}"]
        found = []
        for index, (a, b) in enumerate(zip(shipped, fresh)):
            found.extend(json_drift(a, b, _element(path, index)))
        return found
    if shipped != fresh:
        return [f"{path} SHIPPED={brief(shipped)} FRESH={brief(fresh)}"]
    return []


def normalized(text: str) -> str:
    """Every line of the prose projection except the one naming the moment it was written."""
    return "\n".join(line for line in text.replace("\r\n", "\n").splitlines()
                     if not line.startswith("Generated at:"))


def _run(script: str, *args: str) -> None:
    proc = subprocess.run([sys.executable, str(REPO / script), *args], cwd=REPO, capture_output=True)
    output = (proc.stdout + proc.stderr).decode("utf-8", "replace")
    assert proc.returncode == 0, f"{script} exited {proc.returncode}: {output[-500:]}"


def setUpModule() -> None:
    """Measure all three projections once into a temp dir, keeping the committed bytes as evidence."""
    global TMP
    TMP = Path(mkdtemp(prefix="projection-fresh-", dir=str(RUNS)))
    for key, path in SHIPPED.items():
        COMMITTED[key] = path.read_bytes()
    _run("scripts/audit/ledger_regression_command_targets.py", "--audit-out", str(TMP / "targets.json"),
         "--json-out", str(TMP / "detail.json"))
    _run("scripts/audit/tool_inventory_readback.py", "--out", str(TMP / "inventory.json"))
    _run("scripts/ci/generate_current_state.py", "--json-out", str(TMP / "CURRENT_STATE.json"),
         "--markdown-out", str(TMP / "CURRENT_STATE.md"))
    for key, path in SHIPPED.items():
        AFTER[key] = path.read_bytes()
    FRESH.update({"targets": TMP / "targets.json", "inventory": TMP / "inventory.json",
                  "state": TMP / "CURRENT_STATE.json", "stateMd": TMP / "CURRENT_STATE.md"})


def tearDownModule() -> None:
    rmtree(TMP, ignore_errors=True)


class ProjectionsAgainstTheirOwnTree(unittest.TestCase):
    def assert_current(self, key: str) -> None:
        drift = json_drift(json.loads(COMMITTED[key].decode("utf-8")),
                           json.loads(FRESH[key].read_text(encoding="utf-8")))
        self.assertEqual([], drift[:8],
                         f"the committed {SHIPPED[key].name} is not what this tree measures; republish it "
                         f"in the same commit as its inputs. First drifts: {drift[:8]}")

    def test_the_shipped_ledger_target_projection_is_the_current_measurement(self) -> None:
        self.assert_current("targets")

    def test_the_shipped_tool_inventory_is_the_current_measurement(self) -> None:
        self.assert_current("inventory")

    def test_the_shipped_current_state_is_the_current_measurement(self) -> None:
        self.assert_current("state")

    def test_the_prose_projection_matches_what_this_tree_produces(self) -> None:
        """CURRENT_STATE.md is the file a reader opens; a stale paragraph there is still a false claim."""
        committed = normalized(COMMITTED["stateMd"].decode("utf-8"))
        fresh = normalized(FRESH["stateMd"].read_text(encoding="utf-8"))
        self.assertEqual(committed, fresh, "the committed CURRENT_STATE.md is not what this tree produces")
        self.assertNotEqual(committed, fresh.replace("# WORK-LAB current state",
                                                     "# WORK-LAB current state SWEPT"),
                            "a changed paragraph must be visible to this comparison")

    def test_a_redirected_run_never_moves_a_committed_artifact(self) -> None:
        """The control must not be a writer, or a green suite would mean the tool fixed its own drift."""
        for key, before in COMMITTED.items():
            self.assertEqual(hashlib.sha256(before).hexdigest(),
                             hashlib.sha256(AFTER[key]).hexdigest(),
                             f"{SHIPPED[key].name} moved while the projections were measured into a temp dir")


class TheComparisonItselfIsTested(unittest.TestCase):
    """A freshness control that cannot report drift is how the last two stale artifacts got through."""

    def test_a_changed_value_is_reported_by_name(self) -> None:
        shipped = {"records": 219, "stateDigest": "aa", "at": "2026-10-08T20:32:35Z"}
        fresh = {"records": 220, "stateDigest": "bb", "at": "2026-10-08T21:32:47Z"}
        drift = json_drift(shipped, fresh)
        self.assertEqual(2, len(drift), drift)
        self.assertIn("records SHIPPED=219 FRESH=220", drift)
        self.assertIn("stateDigest SHIPPED=aa FRESH=bb", drift)

    def test_a_reclassified_operand_is_reported_whichever_key_it_lands_under(self) -> None:
        """The exact defect this round found: GONE became DIR_NOT_FILE once the directory gained a file."""
        shipped = {"gone": [{"errorId": "ERR-115", "operand": "reports/audit-archive"}]}
        fresh = {"gone": [], "dirNotFile": [{"errorId": "ERR-115", "operand": "reports/audit-archive"}]}
        drift = json_drift(shipped, fresh)
        self.assertEqual(2, len(drift), drift)
        self.assertTrue(any(d.startswith("gone LENGTH shipped=1 fresh=0") for d in drift), drift)
        self.assertTrue(any(d.startswith("dirNotFile") and "ONLY_IN_FRESH" in d for d in drift), drift)

    def test_only_the_named_moment_fields_are_ignored(self) -> None:
        """The drop list is a bound, not a loophole: `apply` is a mode, `records` is content."""
        self.assertEqual([], json_drift({"at": "T1", "apply": True, "records": 219},
                                        {"at": "T2", "apply": False, "records": 219}),
                         "a re-measurement of the same tree is not drift")
        self.assertTrue(json_drift({"records": 1}, {"records": 2}))
        self.assertEqual({"at", "apply", "generatedAt", "generated_at",
                          "generatedFromCommit", "generatedFromTree"}, VOLATILE,
                         "a field is excused here only with a named reason")

    def test_a_missing_list_entry_is_named_by_its_length_and_tail(self) -> None:
        """The first real drift this control caught was a citation list that grew by one entry.

        Measured at HEAD 7b5a4502: `tools[18].citedBy` published 5 where the committed tree yields 6, so the
        shipped inventory contradicted its own commit. A report that only printed the identical-looking head
        of the list would have left the next session guessing.
        """
        drift = json_drift({"states": ["A", "B"]}, {"states": ["A"]})
        self.assertEqual(1, len(drift), drift)
        self.assertIn("states LENGTH shipped=2 fresh=1", drift[0])
        self.assertIn('tail_shipped=["B"]', drift[0], drift[0])

    def test_a_changed_element_is_reported_at_its_index(self) -> None:
        shipped = {"tools": [{"path": "a.py", "cited": 1}, {"path": "b.py", "cited": 2}]}
        fresh = {"tools": [{"path": "a.py", "cited": 1}, {"path": "b.py", "cited": 7}]}
        drift = json_drift(shipped, fresh)
        self.assertEqual(["tools[1].cited SHIPPED=2 FRESH=7"], drift)

    def test_a_whole_absent_section_is_named_not_flattened(self) -> None:
        drift = json_drift({"rows": [{"a": 1}], "counts": {"RESOLVES": 9}}, {"counts": {"RESOLVES": 9}})
        self.assertEqual(['rows ONLY_IN_SHIPPED=[{"a": 1}]'], drift)


if __name__ == "__main__":
    unittest.main()
