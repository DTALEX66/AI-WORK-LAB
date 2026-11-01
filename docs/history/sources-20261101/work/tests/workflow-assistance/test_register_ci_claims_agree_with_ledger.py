"""Gate: a register row's CI claim must agree with the ledger, without touching the network.

Measured 2026-10-08 by comparing every CI-shaped status token in the live register against GitHub's own
check-runs at the SHA each row pins: 13 rows make such a claim and **4 of them were wrong**. Two were stale
in the harmless-looking direction ("exact-SHA CI not run" at `5037dd2` and `6f323a3`, which each had 24 of
24 runs succeed); two were worse, because a red verdict had been written as an absence -- `f9f38d6` and
`9bbadaf` both had 4 failed runs and 20 successes, and the rows said "not run (no commit authorization)" and
"not read". An absence is unfalsifiable, so nobody re-checked it; a number is not.

CI itself cannot reach GitHub, and a gate that needs the network becomes a flake or a silent skip. So this
gate enforces the part that is decidable from tracked records alone, which is exactly the agreement between
the two authority surfaces:

  * a row may claim green at a SHA only if some ledger record carries `verifiedCommit` == that SHA -- the
    stamper writes that field only when every run at the head completed green, so it is the repository's own
    proof of an exact-SHA verdict;
  * a row that says CI was not run / not read / owed must not name a SHA the ledger has verified, because the
    ledger would then be holding evidence the row denies exists;
  * a row that claims red at a SHA must not coincide with a `verifiedCommit` at that same SHA.

The live comparison (asking GitHub what really happened) is `scripts/ci/verify_register_ci_claims_live.py`;
it refuses on a host with no credentials and is run by hand, with the result written into the row it
contradicts.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
# The 2026-10-09 UI-priority cutover replaced this ledger with the WUI-00..24 register, and the frozen
# original tree is where the rows carrying measured CI verdicts now live
# (`docs/history/archive/ui-priority-20261009/LEGACY-TASK-DISPOSITION.json` records the per-row inheritance).
# Repointing the guard keeps it reading a real register — the file it must not silently stop covering --
# rather than deleting a check whose subject moved.
REGISTER = (ROOT / "taskpacks/history/UI-PRIORITY-CUTOVER-20261009/original-tree"
            / "taskpacks/current" / "OPEN-TASK-REGISTER.md")
LEDGER = ROOT / "taskpacks/current" / "error-ledger.json"
MEASUREMENT_GLOB = "docs/audits/REGISTER_CI_CLAIMS_*.json"

CELL = re.compile(r"(?<!\\)\|")
SHA = re.compile(r"\b[0-9a-f]{7,40}\b")
CLAIMS_GREEN = re.compile(r"EXACT_SHA_CI_GREEN_AT_([0-9a-f]{7,40})")
CLAIMS_RED = re.compile(r"EXACT_SHA_CI_RED_AT_([0-9a-f]{7,40})")
CLAIMS_ABSENT = re.compile(r"EXACT_SHA_CI_NOT_RUN|EXACT_SHA_CI_NOT_READ|EXACT_SHA_CI NOT_RUN|"
                           r"CI_READBACK_OWED|EXACT_SHA_CI_NOT_AT_THIS_COMMIT|NOT_AT_THIS_COMMIT")
# How many rows the register is expected to speak about CI at all. A drop to zero means this scan went
# blind (a renamed token, a changed table), not that the debt vanished.
CI_CLAIM_ROW_FLOOR = 8


def register_rows() -> list[tuple[int, str, str]]:
    text = REGISTER.read_text(encoding="utf-8")
    rows = []
    for number, line in enumerate(text.splitlines(), 1):
        if not line.startswith("| ") or line.startswith("| ID |"):
            continue
        cells = [c.strip() for c in CELL.split(line)]
        if len(cells) < 5:
            continue
        rows.append((number, cells[1], " ".join(cells[2:])))
    return rows


def verified_commits() -> set[str]:
    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    out = set()
    for record in data["errors"]:
        value = (record.get("lifecycle") or {}).get("verifiedCommit")
        if isinstance(value, str) and re.fullmatch(r"[0-9a-f]{40}", value):
            out.add(value)
    return out


def agrees(prefix: str, full: set[str]) -> str | None:
    for sha in full:
        if sha.startswith(prefix):
            return sha
    return None


def measurements() -> dict[str, dict]:
    """The newest published live measurement of GitHub's runs, keyed by full SHA.

    CI cannot call GitHub, and a gate that needs the network is a flake or a silent skip. So the register's
    claims about an external system are checked against this tracked artifact, which
    `scripts/ci/verify_register_ci_claims_live.py` writes on a machine that can reach it. With no file the
    gate does not go vacuous: only the ledger path can then back a green claim.
    """
    candidates = sorted(ROOT.glob(MEASUREMENT_GLOB))
    if not candidates:
        return {}
    doc = json.loads(candidates[-1].read_text(encoding="utf-8"))
    return dict(doc.get("bySha") or {})


def full_sha(prefix: str, keys) -> str | None:
    for key in keys:
        if key.startswith(prefix):
            return key
    return None


class RegisterCiClaimTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = register_rows()
        cls.verified = verified_commits()
        cls.measured = measurements()

    def test_the_measurement_artifact_is_read_when_present(self) -> None:
        # A capability check on this test's own eyes: if the published measurement exists, the scan must
        # see its SHAs, or every "backed by measurement" verdict below is an unread file called evidence.
        if not self.measured:
            self.skipTest("no docs/audits/REGISTER_CI_CLAIMS_*.json in this checkout; a clean CI run "
                          "legitimately has none, and then only the ledger can back a green claim")
        self.assertTrue(all(re.fullmatch(r"[0-9a-f]{40}", sha) for sha in self.measured),
                        "the measurement is keyed by abbreviated SHAs, which cannot be matched to pins "
                        "without a second lookup -- the tool must publish full hashes")

    def test_the_scan_still_sees_ci_claims(self) -> None:
        claims = [row for row in self.rows if CLAIMS_GREEN.search(row[2]) or CLAIMS_RED.search(row[2])
                  or CLAIMS_ABSENT.search(row[2])]
        self.assertGreaterEqual(
            len(claims), CI_CLAIM_ROW_FLOOR,
            f"only {len(claims)} register rows carry a CI token; the measured population on 2026-10-08 was "
            "13, so a drop this far means the matcher stopped recognising the vocabulary -- not that every "
            "row now agrees with CI",
        )

    def test_every_green_claim_is_backed_by_evidence_this_repo_can_check(self) -> None:
        unbacked = []
        for number, row_id, text in self.rows:
            match = CLAIMS_GREEN.search(text)
            if not match:
                continue
            pin = match.group(1)
            if agrees(pin, self.verified):
                continue
            sha = full_sha(pin, self.measured)
            verdict = self.measured.get(sha or "")
            if verdict and verdict.get("runs", 0) > 0 and verdict.get("success") == verdict.get("runs"):
                continue
            unbacked.append(f"line {number} {row_id}: claims green at {pin[:7]} with "
                            + ("no runs in the published measurement" if verdict
                               else "no verifiedCommit and no published measurement"))
        self.assertEqual(
            unbacked, [],
            f"{len(unbacked)} row(s) assert an exact-SHA CI green nothing in the repository backs: "
            f"{unbacked} -- the stamper writes verifiedCommit only when every run at that head was green, "
            "and the live tool publishes what GitHub actually reported; a green token needs one of the two",
        )

    def test_no_claim_is_refuted_by_the_published_measurement(self) -> None:
        refuted = []
        for number, row_id, text in self.rows:
            green = CLAIMS_GREEN.search(text)
            red = CLAIMS_RED.search(text)
            match = green or red
            if not match:
                continue
            pin = match.group(1)
            sha = full_sha(pin, self.measured)
            verdict = self.measured.get(sha or "")
            if not verdict:
                continue
            if green and (verdict.get("failure", 0) or verdict.get("runs", 0) == 0):
                refuted.append(f"line {number} {row_id}: green at {pin[:7]} but measured "
                               f"runs={verdict.get('runs')} failure={verdict.get('failure')}")
            if red and verdict.get("failure", 0) == 0 and verdict.get("runs", 0):
                refuted.append(f"line {number} {row_id}: red at {pin[:7]} but measured "
                               f"failure=0 of runs={verdict.get('runs')}")
        self.assertEqual(refuted, [], f"the register contradicts committed evidence: {refuted}")

    def test_no_absence_claim_denies_evidence_the_ledger_holds(self) -> None:
        contradicted = []
        for number, row_id, text in self.rows:
            if not CLAIMS_ABSENT.search(text):
                continue
            verified_here = [pin for pin in SHA.findall(text) if agrees(pin, self.verified)]
            if verified_here:
                contradicted.append(
                    f"line {number} {row_id}: says CI did not run, yet the ledger has verifiedCommit "
                    f"{[v[:7] for v in verified_here]}")
        self.assertEqual(
            contradicted, [],
            f"{len(contradicted)} row(s) describe an absence that the machine authority already disproves: "
            f"{contradicted} -- this is exactly how `f9f38d6` and `9bbadaf` sat there labelled 'not read' "
            "while their runs had come back red",
        )

    def test_no_red_claim_collides_with_a_verified_head(self) -> None:
        collisions = []
        for number, row_id, text in self.rows:
            match = CLAIMS_RED.search(text)
            if match and agrees(match.group(1), self.verified):
                collisions.append(f"line {number} {row_id}: claims red at {match.group(1)[:7]} which the "
                                  "ledger records as verified")
        self.assertEqual(collisions, [], f"red and verified cannot both hold for one head: {collisions}")

    def test_the_four_measured_corrections_are_present(self) -> None:
        # Pins the corrected state itself, so a later edit that quietly restores the stale wording fails.
        expected = {
            "P1-06-CONTROL-SURFACE-20261008": "EXACT_SHA_CI_RED_AT_f9f38d6",
            "SECURITY-REVIEW-20261008": "EXACT_SHA_CI_RED_AT_9bbadaf",
            "GATE-RECHECK-20261006": "EXACT_SHA_CI_GREEN_AT_6f323a3",
        }
        by_id = {row_id: text for _n, row_id, text in self.rows}
        for row_id, token in expected.items():
            self.assertIn(row_id, by_id, f"row {row_id} disappeared from the register")
            self.assertIn(token, by_id[row_id],
                          f"row {row_id} lost the measured CI verdict it now carries")


if __name__ == "__main__":
    unittest.main()
