"""Gate the executor live probe: it may measure, and it may not upgrade itself.

The point of this instrument is that `config/adapter-registry.json` says UNVERIFIED for all ten
adapters, so nothing downstream can name a probed executor (AG-16's missing link). That only becomes
useful if the probe refuses to overstate — a tool that hands out LIVE_VERIFIED for whatever answers
would be worse than the gap it fills, because the register would then read as closed.
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "audit" / "executor_live_probe.py"
# The gate follows the newest receipt. The 2026-10-07 one stays in the tree as the dated evidence it is,
# but it pins the registry as it read before the directory convergence, so keeping the gate on it turned
# "the receipt describes an older tree" into a permanent red that could only be silenced by launching
# someone's desktop applications. `--no-launch` exists for exactly that reason.
RECORD = ROOT / "docs" / "audits" / "EXECUTOR_LIVE_PROBE_2026-10-20.json"
REGISTRY_REL = "config/adapter-registry.json"

spec = importlib.util.spec_from_file_location("executor_live_probe", SCRIPT)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)  # type: ignore[attr-defined]


def entry(claimed: str) -> dict:
    return {"id": "x", "provenance": {"version": claimed}}


class AdjudicationTests(unittest.TestCase):
    def test_only_agreement_with_a_real_claim_becomes_live_verified(self) -> None:
        state, detail = probe.adjudicate(entry("0.160.1"),
                                         {"invoked": True, "exitCode": 0, "observedVersion": "0.160.1"})
        self.assertEqual("LIVE_VERIFIED", state, detail)

    def test_a_nonzero_exit_can_never_report_live_verified(self) -> None:
        for code in (1, 2, 127):
            state, _ = probe.adjudicate(entry("1.2.3"), {"invoked": True, "exitCode": code,
                                                        "observedVersion": "1.2.3"})
            self.assertEqual("PROBE_FAILED", state, code)

    def test_a_timeout_is_its_own_named_category(self) -> None:
        state, detail = probe.adjudicate(entry("1.2.3"), {"invoked": True, "exitCode": None,
                                                         "reason": "PROBE_TIMEOUT_25s"})
        self.assertEqual("PROBE_TIMEOUT", state, detail)
        self.assertIn("PROBE_TIMEOUT_25s", detail)

    def test_the_placeholder_word_in_the_registry_is_not_treated_as_a_version(self) -> None:
        # Measured, then caught by eye: comparing against the literal string UNVERIFIED produced a
        # confident VERSION_MOVED for the two executors that really answered.
        state, detail = probe.adjudicate(entry("UNVERIFIED"), {"invoked": True, "exitCode": 0,
                                                             "observedVersion": "2.98.0"})
        self.assertEqual("MEASURED_NO_CLAIM_TO_COMPARE", state, detail)
        self.assertNotIn("VERSION_MOVED", state)

    def test_a_real_disagreement_is_reported_without_being_reconciled(self) -> None:
        state, detail = probe.adjudicate(entry("0.21.5"), {"invoked": True, "exitCode": 0,
                                                          "observedVersion": "0.22.0"})
        self.assertEqual("VERSION_MOVED", state, detail)
        self.assertIn("0.21.5", detail)
        self.assertIn("0.22.0", detail)

    def test_an_unresolved_entry_point_is_never_a_pass(self) -> None:
        state, _ = probe.adjudicate(entry("1.0.0"), {"invoked": False, "reason": "ENTRY_NOT_EXECUTABLE"})
        self.assertEqual("ENTRY_NOT_RESOLVED", state)

    def test_a_build_date_on_the_claim_does_not_fake_a_drift(self) -> None:
        """Measured 2026-10-20: the registry claims `2.98.0 (2026-08-20)` because that is what the
        Windows version resource prints, while `gh --version` answers `2.98.0`. Same install, and the
        old raw-string compare reported it as a version change."""
        state, detail = probe.adjudicate(entry("2.98.0 (2026-08-20)"),
                                         {"invoked": True, "exitCode": 0, "observedVersion": "2.98.0"})
        self.assertEqual("LIVE_VERIFIED", state, detail)

    def test_normalising_the_decoration_still_reports_real_drift(self) -> None:
        state, detail = probe.adjudicate(entry("2.98.0 (2026-08-20)"),
                                         {"invoked": True, "exitCode": 0, "observedVersion": "2.99.0"})
        self.assertEqual("VERSION_MOVED", state, detail)
        self.assertIn("2.98.0", detail)
        self.assertIn("2.99.0", detail)


class RecordTests(unittest.TestCase):
    def setUp(self) -> None:
        if not RECORD.is_file():
            self.skipTest("the probe record has not been produced on this machine")
        self.doc = json.loads(RECORD.read_text(encoding="utf-8"))

    def test_the_record_declares_itself_read_only_and_pins_the_registry_it_read(self) -> None:
        self.assertTrue(self.doc["readOnly"])
        self.assertEqual(64, len(self.doc["registrySha256"]))

    def test_the_pinned_registry_is_the_one_the_commit_carries(self) -> None:
        """A length-64 hash proves formatting; only comparison proves the receipt is about this registry.

        On 2026-10-07 I re-pointed hermes' declared version at its install stamp and re-ran the probe
        without `--out`, so the printed summary was new while the shipped receipt still pinned the old
        registry and quoted the superseded version. The gate accepted it, because nothing had ever
        checked the pin against the file. The index is read first (ERR-153): in a CI checkout it equals
        HEAD, so this asks the runner for nothing extra.
        """
        index = subprocess.run(["git", "show", f":{REGISTRY_REL}"], cwd=ROOT, capture_output=True)
        if index.returncode != 0:
            index = subprocess.run(["git", "show", f"HEAD:{REGISTRY_REL}"], cwd=ROOT,
                                   capture_output=True)
        self.assertEqual(0, index.returncode, f"{REGISTRY_REL} is not readable from git")
        self.assertEqual(hashlib.sha256(index.stdout).hexdigest(), self.doc["registrySha256"],
                         "the receipt pins a different registry than the tree carries, so its "
                         "claimedVersion rows describe an older declaration")

    def test_counts_are_derived_from_the_rows_not_typed(self) -> None:
        derived: dict[str, int] = {}
        for row in self.doc["results"]:
            derived[row["state"]] = derived.get(row["state"], 0) + 1
        self.assertEqual(derived, self.doc["counts"])

    def test_no_row_was_upgraded_without_a_measured_agreement(self) -> None:
        for row in self.doc["results"]:
            if row["state"] == "LIVE_VERIFIED":
                observed = (row.get("probe") or {}).get("observedVersion")
                self.assertEqual(0, (row.get("probe") or {}).get("exitCode"), row["adapter"])
                # Compared on the version token, not the raw string: a claim copied from a Windows
                # version resource carries a build date the CLI does not print, and the instrument
                # agrees on the token. The teeth live in the adjudication tests above, where a real
                # numeric difference still has to come back as VERSION_MOVED.
                self.assertEqual(probe.version_token(row["claimedVersion"]),
                                 probe.version_token(observed or ""),
                                 f"{row['adapter']}: claimed {row['claimedVersion']!r} observed "
                                 f"{observed!r} — agreement was asserted without equal versions")

    def test_every_row_names_its_category(self) -> None:
        allowed = {"LIVE_VERIFIED", "MEASURED_NO_CLAIM_TO_COMPARE", "PROBED_NO_VERSION_READBACK",
                   "VERSION_MOVED", "PROBE_FAILED", "PROBE_TIMEOUT", "ENTRY_NOT_RESOLVED",
                   "RESOLVER_ERROR", "NOT_PROBED_DECLARATIVE_ONLY", "PROBE_SKIPPED_NO_LAUNCH"}
        offenders = [r["state"] for r in self.doc["results"] if r["state"] not in allowed]
        self.assertEqual([], offenders)

    def test_a_skipped_entry_records_a_refusal_not_a_result(self) -> None:
        """`--no-launch` must be visible as a refusal: no resolved command, no probe payload, and never
        an upgrade. A skipped row that carried a version would be the inflation this gate exists to stop."""
        skipped = [r for r in self.doc["results"] if r["state"] == "PROBE_SKIPPED_NO_LAUNCH"]
        self.assertTrue(skipped, "the shipped receipt was produced without --no-launch")
        for row in skipped:
            self.assertNotIn("command", row, row["adapter"])
            self.assertNotIn("probe", row, row["adapter"])
            self.assertIn("--no-launch", row["detail"])

    def test_the_headless_allowlist_is_the_two_entries_proven_not_to_open_a_window(self) -> None:
        self.assertEqual({"codex", "github"}, set(probe.HEADLESS_ENTRYPOINTS))
        probed = {r["adapter"] for r in self.doc["results"] if "probe" in r}
        self.assertTrue(probed <= set(probe.HEADLESS_ENTRYPOINTS),
                        f"entries outside the allowlist were executed: {sorted(probed)}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
