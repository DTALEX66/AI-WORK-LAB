# SPDX-License-Identifier: MIT
"""Run the honesty gates that existed but were never invoked.

Discovered while wiring the Workbench UI audit into CI: `scripts/verify_no_overclaim.py`,
`scripts/verify_evidence_levels.py` and `scripts/verify_supply_chain.py` all pass, all
guard claims rather than counts, and none of them is named in any workflow or test --
CI lists its gates one step at a time, so a script nobody writes a step for simply never
runs. `test_gate_reachability.py` keeps that from recurring.

Each assertion requires the verdict token in the output, not just exit 0: a gate that
prints nothing and exits 0 has not examined anything.

They are invoked with `--check`, not bare. Measured on 2026-10-09: all three also *write* a
tracked report in bare mode, so every suite run rewrote
`reports/current/{SUPPLY-CHAIN-REPORT,EVIDENCE-LEVEL-AUDIT,NO-OVERCLAIM-AUDIT}.json` -- one of
the reasons "a full run can never be clean" was ever true -- and each of those reports carried
`subject_sha: ""` because the writer called `git("rev-parse HEAD")` as one argv element, which
git rejects and the helper returned as empty text. `--check` compares the stored record against
a fresh computation and writes nothing, which is the stronger claim anyway: the report in the
repository agrees with what the tool computes now.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

GATES = (
    ("scripts/verify_no_overclaim.py", "NO_OVERCLAIM=PASS"),
    ("scripts/verify_evidence_levels.py", "EVIDENCE_LEVELS=PASS"),
    ("scripts/verify_supply_chain.py", "SUPPLY_CHAIN=PASS"),
)

# The tracked artefacts those three gates would rewrite if run in their writer form.
GATE_OUTPUTS = (
    "reports/current/NO-OVERCLAIM-AUDIT.json",
    "reports/current/EVIDENCE-LEVEL-AUDIT.json",
    "reports/current/SUPPLY-CHAIN-REPORT.json",
)


class ClaimHonestyGateTests(unittest.TestCase):
    def run_gate(self, relative: str, token: str, *extra: str) -> str:
        script = ROOT / relative
        self.assertTrue(script.is_file(), f'gate missing: {relative}')
        proc = subprocess.run([sys.executable, '-X', 'utf8', '-B', str(script), *extra],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding='utf-8', errors='replace', timeout=900)
        output = (proc.stdout or '') + (proc.stderr or '')
        self.assertEqual(proc.returncode, 0, f'{relative} exited {proc.returncode}:\n{output[-800:]}')
        self.assertIn(token, output,
                      f'{relative} exited 0 without emitting {token!r}; output was:\n{output[-800:]}')
        return output

    def test_no_overclaim_passes_and_reports_what_it_examined(self) -> None:
        output = self.run_gate(*GATES[0], '--check')
        counts = re.search(r"claims=(\d+).*?unsupported=(\d+)", output, re.S)
        self.assertIsNotNone(counts,
                             f'no_overclaim passed without reporting its counts: {output[:240]}')
        self.assertGreater(int(counts.group(1)), 0,
                           'the gate examined zero claims, so its PASS covers nothing')
        self.assertEqual(int(counts.group(2)), 0,
                         'the gate passed while unsupported claims were present')

    def test_evidence_levels_keeps_historical_evidence_honest(self) -> None:
        self.run_gate(*GATES[1], '--check')

    def test_supply_chain_lock_is_consistent(self) -> None:
        self.run_gate(*GATES[2], '--check')

    def test_running_the_gates_leaves_no_tracked_report_modified(self) -> None:
        """The suite must not be a writer. This is the shape that made every run dirty.

        Asserted on the porcelain for exactly the three paths those gates own, so a future
        refactor that points a test back at bare mode fails here instead of quietly becoming
        the reason a clean checkout is impossible.
        """
        for relative, token in GATES:
            self.run_gate(relative, token, '--check')
        proc = subprocess.run(['git', 'status', '--porcelain', '--', *GATE_OUTPUTS],
                              cwd=str(ROOT), capture_output=True, text=True,
                              encoding='utf-8', errors='replace')
        self.assertEqual(proc.stdout.strip(), '',
                         'a gate run rewrote a tracked report: ' + proc.stdout)

    def test_the_three_reports_name_a_commit(self) -> None:
        """`subject_sha` was empty in all three for the whole time they existed."""
        for relative in GATE_OUTPUTS:
            document = json.loads((ROOT / relative).read_text(encoding='utf-8'))
            subject = str(document.get('subject_sha') or '')
            self.assertRegex(subject, r'^[0-9a-f]{40}$',
                             f'{relative} binds itself to {subject!r}, which names no commit')

    def test_supply_chain_sees_the_derived_revision_record(self) -> None:
        """The join, asserted.

        `revision_coverage` read only the lock and reported 0 while PR #242's derived
        record held 37 revisions. A gate that under-reports its own coverage is worse
        than no gate, because the number is what people trust.
        """
        report = ROOT / "reports" / "current" / "SUPPLY-CHAIN-REPORT.json"
        self.assertTrue(report.is_file(), "the gate ran but wrote no report to inspect")
        check = json.loads(report.read_text(encoding="utf-8"))["checks"]["G000_sources_lock"]
        self.assertGreater(check["revision_coverage"], 0,
                           "revision_coverage is zero again: the lock and the derived "
                           "revision record have stopped being read together")
        self.assertEqual(check["revision_record_ids_not_in_lock"], [],
                         "the revision record describes sources the lock no longer has")
        self.assertEqual(check["absorb_without_revision"], [],
                         "an ABSORB source appears in neither the resolved nor the "
                         "unresolved revision list -- that is a hole in the record")
        # Recorded §9 gaps, not failures: source known, revision pending. Pinning the set
        # means a third one cannot join silently.
        self.assertEqual(sorted(check["absorb_unresolved"]),
                         ["ai-product-os-frontend", "front-end-design-checklist"],
                         "the set of absorbed-without-revision sources changed; either "
                         "close the gap or record why the expectation moved")
        # Measured 2026-10-07: none of the nine is resolvable offline. Two have a repo
        # URL in the lock notes but no commit anywhere in their SOURCE.md / skills-lock.json,
        # and the only 40-hex strings in those directories are truncated SHA-256 content
        # hashes -- which the revision regex would accept as a commit. Seven have no URL
        # at all, so a human has to identify the upstream before any lookup is possible.
        self.assertEqual(sorted(check["revision_unresolved_with_url"]),
                         ["ai-product-os-frontend", "front-end-design-checklist"])
        self.assertEqual(len(check["revision_unresolved_without_url"]), 7)
        self.assertEqual(check["revision_record"]["resolved"]
                         + len(check["revision_unresolved_with_url"])
                         + len(check["revision_unresolved_without_url"]),
                         check["entries"],
                         "resolved + unresolved no longer accounts for every lock entry")


if __name__ == '__main__':
    unittest.main()
