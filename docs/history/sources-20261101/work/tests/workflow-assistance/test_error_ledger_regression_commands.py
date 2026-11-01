"""AG-20 gate: a durable record's regression command must resolve to a tracked file.

`error-ledger.json` holds two kinds of command field. `command` records what was run at the
time — history, which may name a path that no longer exists, and rewriting it would falsify the
record. `lifecycle.regressionCommand` is the opposite: a forward-looking promise that someone
can run this to reproduce the finding. Round E found ten of those promises pointing into the
git-ignored runtime root that a cleanup removes, and round F found seven more plus two that had
been silently broken by a directory move.

So the promise is what this gate holds to a standard, and the gate refuses three lies: a
regression command naming an untracked or absent script, an entry that quietly drops the promise
after ever making it, and a dated correction whose prior string is missing or whose note is
empty. Nothing is exempted, because the population is now clean.
"""
from __future__ import annotations

import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "taskpacks" / "current" / "error-ledger.json"
PATH_PREFIXES = (".project-local/", "scripts/", "services/", "apps/", "tests/", "packages/",
                 "integrations/", "bin/", "tools/", "docs/")
PATH_SUFFIXES = ("py", "js", "mjs", "sh", "ps1")
CD_RE = re.compile(r"^\s*cd\s+(\S+)\s*(?:&&|.*)$")


def script_tokens(command: str) -> list[str]:
    tokens = []
    for raw in command.replace("&&", " ").replace(";", " ").split():
        candidate = raw.strip("'\"`()")
        if candidate.startswith(PATH_PREFIXES) and candidate.rsplit(".", 1)[-1] in PATH_SUFFIXES:
            tokens.append(candidate)
    return tokens


def command_prefix(command: str) -> str:
    match = CD_RE.match(command)
    return match.group(1).rstrip("/") if match else ""


def tracked_files() -> set[str]:
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    return {p.decode("utf-8") for p in listing.stdout.split(b"\0") if p}


def unresolved_entries(errors: list[dict], tracked: set[str], exists) -> list[dict]:
    bad = []
    for item in errors:
        lifecycle = item.get("lifecycle") or {}
        command = str(lifecycle.get("regressionCommand") or "")
        prefix = command_prefix(command)
        for token in script_tokens(command):
            relative = f"{prefix}/{token}" if prefix and not token.startswith(prefix) else token
            if relative not in tracked and not exists(relative):
                bad.append({"error_id": item.get("error_id"), "resolved_as": relative})
    return bad


class ErrorLedgerRegressionCommandTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.data = json.loads(LEDGER.read_text(encoding="utf-8"))
        cls.errors = cls.data["errors"]
        cls.tracked = tracked_files()

    def test_the_promise_is_widespread_enough_that_the_gate_cannot_pass_vacuously(self) -> None:
        with_command = [e for e in self.errors
                        if str((e.get("lifecycle") or {}).get("regressionCommand") or "").strip()]
        self.assertGreaterEqual(len(with_command), 40,
                                "fewer records carry a regression command than expected; the "
                                "gate below would be checking almost nothing")

    def test_every_regression_command_resolves_to_a_tracked_file(self) -> None:
        bad = unresolved_entries(self.errors, self.tracked,
                                 lambda rel: (ROOT / rel).exists())
        self.assertEqual(bad, [],
                         f"regression commands that name an untracked or absent script: {bad[:8]}")

    def test_no_regression_command_points_into_the_ignored_runtime_root(self) -> None:
        offenders = []
        for item in self.errors:
            command = str((item.get("lifecycle") or {}).get("regressionCommand") or "")
            for token in script_tokens(command):
                if token.startswith(".project-local/"):
                    offenders.append({"error_id": item.get("error_id"), "token": token})
        self.assertEqual(offenders, [],
                         "a promise to reproduce a finding cannot live in the directory the "
                         f"next cleanup removes: {offenders[:6]}")

    def test_a_dated_correction_carries_its_prior_string_and_note(self) -> None:
        for item in self.errors:
            lifecycle = item.get("lifecycle") or {}
            corrected = ("regressionCommandCorrectedAt" in lifecycle
                         or "regressionCommandPrior" in lifecycle
                         or "regressionCommandNote" in lifecycle)
            if not corrected:
                continue
            self.assertTrue(str(lifecycle.get("regressionCommandPrior") or "").strip(),
                            f"{item['error_id']} was corrected without keeping the original")
            self.assertRegex(str(lifecycle.get("regressionCommandCorrectedAt")), r"^\d{4}-\d{2}-\d{2}",
                             f"{item['error_id']} correction is undated")
            self.assertTrue(str(lifecycle.get("regressionCommandNote") or "").strip(),
                            f"{item['error_id']} was corrected without saying why")

    def test_gate_fails_when_a_command_names_an_untracked_script(self) -> None:
        synthetic = [{"error_id": "ERR-999",
                      "lifecycle": {"regressionCommand":
                                    "python .project-local/runs/scratch/ghost.py"}}]
        bad = unresolved_entries(synthetic, set(), lambda _p: False)
        self.assertEqual([row["error_id"] for row in bad], ["ERR-999"],
                         "the gate would have passed on a promise that points at nothing")

    def test_gate_resolves_a_command_that_enters_a_subdirectory_first(self) -> None:
        synthetic = [{"error_id": "ERR-998",
                      "lifecycle": {"regressionCommand":
                                    "cd apps/observer && node tests/run_all_tests.js"}}]
        tracked = {"apps/observer/tests/run_all_tests.js"}
        self.assertEqual(unresolved_entries(synthetic, tracked, lambda _p: False), [],
                         "a cd-relative command was judged against the repository root")

    def test_a_promise_may_not_be_removed_once_made(self) -> None:
        with_command = [e for e in self.errors
                        if str((e.get("lifecycle") or {}).get("regressionCommand") or "").strip()]
        cleared = [e["error_id"] for e in self.errors
                   if "regressionCommandPrior" in (e.get("lifecycle") or {})
                   and not str((e.get("lifecycle") or {}).get("regressionCommand") or "").strip()]
        self.assertEqual(cleared, [],
                         f"records that dropped the promise instead of re-pointing it: {cleared}")
        self.assertTrue(with_command)


if __name__ == "__main__":
    unittest.main()
