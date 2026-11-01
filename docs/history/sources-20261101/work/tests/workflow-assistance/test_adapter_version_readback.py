"""Gate: a registry version claim must be backed by the receipt that produced it.

`provenance.version` is allowed to carry only a natively verified value, and AG-07 gave it a structured
`version_readback` so drift is machine-checkable. Five entries were filled on 2026-10-07 from a Windows
version-resource read, so the claim now has an upstream artifact. This gate is what makes that pairing
enforceable instead of a promise in prose: a version without a matching, un-launched receipt fails, and so
does a version readback that quietly promotes a detection state a hash was supposed to own.
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / "config/adapter-registry.json"
RECEIPT = ROOT / "docs/audits/TOOL_VERSION_METADATA_PROBE_2026-10-07.json"

# manifest-only clients: no live entry point is declared, so nothing may be observed for them yet.
DECLARATIVE_ONLY = {"cursor", "claude-code", "workbuddy"}

# A source a reviewer can re-read on their own machine, without starting the application.
LAUNCH_FREE_SOURCES = ("windows-installer-registry", "windows-file-version-resource",
                       "install-stamp-readback")


def dsh_version_problems(entries: dict, receipt: dict) -> list[str]:
    """Every way a DeepSeek Harness version claim can fail to be backed, as data rather than assertions.

    Exposed as a function so the falsification test can plant each lie in a copy and prove the predicate
    catches it; an assertion that has never been seen to fail is not measuring anything.
    """
    problems: list[str] = []
    provenance = entries["deepseek-harness"]["provenance"]
    readback = provenance["version_readback"]
    if not readback["observed_at"].startswith(tuple("20")):
        problems.append("observed_at is not a date")
    if not any(readback["method"].startswith(token) for token in LAUNCH_FREE_SOURCES):
        problems.append(f"{readback['method']} would require starting an Electron app to re-read")
    if provenance["version"] != readback["verified_version"]:
        problems.append("version does not equal the readback's verified_version")
    if receipt.get("launchedAnyProcessForVersion") is not False:
        problems.append("the receipt admits it launched something")
    row = receipt["results"].get("deepseek-harness") or {}
    if row.get("launched") is not False:
        problems.append("the DSH row does not declare launched=false")
    if provenance["version"] != row.get("fileVersion"):
        problems.append(f"registry quotes {provenance['version']!r} but the binary's version resource "
                        f"answered {row.get('fileVersion')!r}")
    if not readback.get("superseded_observation"):
        problems.append("the previous build was deleted instead of superseded")
    superseded = (readback.get("superseded_observation") or {}).get("verified_version")
    historical = provenance.get("version_historical") or []
    if superseded and len([h for h in historical if h.startswith(superseded)]) != 1:
        problems.append(f"{superseded} must appear exactly once in version_historical")
    if any("(current" in h for h in historical):
        problems.append("a superseded version still carries a current label in history")
    return problems


class AdapterVersionReadbackGate(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        cls.entries = {e["id"]: e for e in cls.registry["entries"]}
        cls.receipt = json.loads(RECEIPT.read_text(encoding="utf-8"))

    def receipt_row(self, adapter: str) -> dict:
        return self.receipt["results"][adapter]

    def observed_version(self, adapter: str) -> str | None:
        row = self.receipt_row(adapter)
        if row.get("fileVersion"):
            return row["fileVersion"]
        if row.get("displayVersion"):
            return row["displayVersion"]
        binary = row.get("binary") or {}
        return binary.get("fileVersion")

    def test_the_receipt_declares_that_nothing_was_launched(self) -> None:
        self.assertIs(False, self.receipt["launchedAnyProcessForVersion"])
        for adapter, row in self.receipt["results"].items():
            if "launched" in row:
                self.assertIs(False, row["launched"], adapter)

    def test_every_version_readback_agrees_with_the_registry_version(self) -> None:
        for adapter, entry in self.entries.items():
            readback = entry["provenance"].get("version_readback")
            if not readback:
                continue
            self.assertEqual(entry["provenance"]["version"], readback["verified_version"], adapter)
            self.assertTrue(readback.get("observed_at"), f"{adapter}: an undated observation cannot age")
            self.assertTrue(readback.get("method"), adapter)
            self.assertNotIn("UNVERIFIED", readback["verified_version"],
                             f"{adapter}: a placeholder is not a verified version")

    def test_a_file_version_claim_is_reproducible_from_the_receipt(self) -> None:
        claimed = [a for a, e in self.entries.items()
                   if (e["provenance"].get("version_readback") or {}).get("method", "")
                   .startswith("windows-file-version-resource")]
        self.assertGreaterEqual(len(claimed), 4, "the gate must have real rows to check")
        for adapter in claimed:
            with self.subTest(adapter=adapter):
                observed = self.observed_version(adapter)
                readback = self.entries[adapter]["provenance"]["version_readback"]
                if observed is None:
                    # Measured 2026-10-20: OpenHuman's uninstall entry and executable are gone from this
                    # machine, so the read that backed its value can no longer be taken. That is allowed to
                    # be true only as a named state -- the row must say it is not reproducible and must
                    # quote the verdict the receipt actually answered.
                    self.assertIs(False, readback.get("reproducible"),
                                  f"{adapter}: the receipt read no version and the row does not admit it")
                    self.assertEqual(self.receipt["results"][adapter]["verdict"],
                                     readback.get("not_reproducible_verdict"),
                                     f"{adapter}: the row names a different failure than the receipt")
                    continue
                self.assertEqual(self.entries[adapter]["provenance"]["version"], observed,
                                 "registry version is not the number the receipt read from the binary")

    def test_an_unreproducible_claim_that_does_not_say_so_is_refused(self) -> None:
        """The escape hatch has to be the thing that is checked, or absence becomes a way to keep any claim."""
        dead = [a for a, e in self.entries.items() if a in self.receipt["results"]
                and self.observed_version(a) is None
                and (e["provenance"].get("version_readback") or {}).get("method", "")
                .startswith("windows-file-version-resource")]
        if not dead:
            self.skipTest("every file-version row is currently reproducible on this machine")
        import copy
        entries = copy.deepcopy(self.entries)
        entries[dead[0]]["provenance"]["version_readback"].pop("reproducible", None)
        problems = []
        for adapter in dead:
            readback = entries[adapter]["provenance"]["version_readback"]
            if readback.get("reproducible", True) is not False:
                problems.append(adapter)
        self.assertEqual([dead[0]], problems,
                         "stripping the marker should have left the row looking reproducible; it did not")

    def test_a_version_readback_never_promotes_a_detection_state(self) -> None:
        # A readback proves which binary is installed; it does not verify the package hash, so it cannot
        # buy evidence_state.
        for adapter, entry in self.entries.items():
            if entry["provenance"].get("version_readback"):
                self.assertIn(entry["detection"]["evidence_state"],
                              {"UNVERIFIED", "BLOCKED", "SKIPPED_OPTIONAL"}, adapter)

    def test_declared_only_clients_stay_unverified(self) -> None:
        for adapter in DECLARATIVE_ONLY:
            entry = self.entries[adapter]
            self.assertEqual("UNVERIFIED", entry["provenance"]["version"], adapter)
            self.assertNotIn("version_readback", entry["provenance"], adapter)

    def test_deepseek_harness_version_comes_from_a_source_that_needs_no_launch(self) -> None:
        """The pin this replaces demanded `observed_at <= 2026-10-07`. On 2026-10-20 the only way to satisfy
        it was to delete a true re-read, so the date was never the real requirement -- re-readability was.
        DSH now carries the same contract Hermes already had: a launch-free source, the registry quoting
        exactly what that source answered, and the previous build kept as superseded rather than removed."""
        self.assertEqual([], dsh_version_problems(self.entries, self.receipt))

    def test_each_lie_about_the_harness_version_is_caught(self) -> None:
        import copy
        cases = {
            "a launch-based method": ("entries", "method", "electron-cli-version-readback"),
            "a version the binary never answered": ("entries", "version", "9.9.9"),
            "the superseded build deleted": ("entries", "drop_superseded", None),
            "the receipt admitting a launch": ("receipt", "launched", True),
        }
        for label, (side, key, value) in cases.items():
            entries = copy.deepcopy(self.entries)
            receipt = copy.deepcopy(self.receipt)
            provenance = entries["deepseek-harness"]["provenance"]
            readback = provenance["version_readback"]
            if side == "entries":
                if key == "version":
                    provenance["version"] = value
                elif key == "drop_superseded":
                    readback.pop("superseded_observation", None)
                else:
                    readback["method"] = value
            else:
                receipt["results"]["deepseek-harness"]["launched"] = value
            self.assertTrue(dsh_version_problems(entries, receipt),
                            f"the predicate accepted {label} without a complaint")

    def test_hermes_version_comes_from_a_source_that_needs_no_launch(self) -> None:
        readback = self.entries["hermes"]["provenance"]["version_readback"]
        self.assertEqual("install-stamp-readback", readback["method"],
                         "hermes has no version resource and its --version times out; only the stamp "
                         "can be re-read here")
        self.assertIs(False, self.receipt["launchedAnyProcessForVersion"])
        self.assertIs(False, self.receipt_row("hermes").get("launched"))
        self.assertEqual(self.entries["hermes"]["provenance"]["version"],
                         readback["verified_version"])
        self.assertIn("install-stamp.json", readback["native_readback"])
        self.assertTrue(readback.get("superseded_observation"),
                        "the earlier CLI reading was deleted instead of superseded")
        superseded = readback["superseded_observation"]["verified_version"]
        historical = self.entries["hermes"]["provenance"]["version_historical"]
        matches = [h for h in historical if h.startswith(superseded)]
        self.assertEqual(1, len(matches),
                         f"{superseded} must appear once in version_historical, got {len(matches)}")
        self.assertFalse([h for h in historical if "(current" in h],
                         "a superseded version still carries a current label in history")

    def test_the_stamp_row_in_the_receipt_is_the_row_the_registry_quotes(self) -> None:
        row = self.receipt_row("hermes")
        self.assertEqual("LIVE_VERSION_FROM_INSTALL_STAMP", row["verdict"])
        self.assertNotIn("fileVersion", row,
                         "the stamp is not a file version resource and must not look like one")
        self.assertEqual(self.entries["hermes"]["provenance"]["version"], row["displayVersion"])
        self.assertEqual(self.entries["hermes"]["provenance"]["version_readback"]["commit"],
                         row["commit"])

    def test_a_stamp_source_that_only_exists_on_this_machine_is_claimed_as_such(self) -> None:
        """CI cannot see Hermes' install stamp, so the re-read is a named skip, never a silent pass."""
        row = self.receipt_row("hermes")
        stamp = Path(row["stampPath"])
        if not stamp.is_file():
            self.skipTest("the Hermes install stamp is outside the repository; a clean checkout "
                          "legitimately has no such file, so only the recorded claim is checkable here")
        live = json.loads(stamp.read_text(encoding="utf-8"))
        self.assertEqual(live["displayVersion"], row["displayVersion"])
        self.assertEqual(live["commit"], row["commit"])

    def test_the_wrapper_and_the_resourceless_binary_are_not_claimed_as_versions(self) -> None:
        hermes = self.receipt_row("hermes")
        self.assertNotIn("fileVersion", hermes)
        self.assertEqual("ENTRY_IS_WRAPPER_USE_LIVE_PROBE", self.receipt_row("codex")["verdict"])
        # The codex number in the registry therefore came from running the wrapper, not from a file.
        self.assertEqual("official-cli-version-readback",
                         self.entries["codex"]["provenance"]["version_readback"]["method"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
