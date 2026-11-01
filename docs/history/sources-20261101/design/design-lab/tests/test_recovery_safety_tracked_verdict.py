# SPDX-License-Identifier: MIT
"""A destructive-operation receipt must be auditable by someone who does not own the disk.

Measured on 2026-10-09 in two trees of commit `d6ba107f`: `verify_recovery_safety.py --check`
reported PASS here and DRIFT in a clean checkout, because its I000 half read its three manifests
from `.project-local`, which is gitignored -- all three came back `exists: False`, so the verdict
became FAIL and the recorded PASS could not be reproduced by anyone else. I010 was already fully
tracked (`ok=True`, zero findings in both trees), which is what made the split clean.

The fix archives the receipts under `reports/history/` and audits those bytes. So the properties
asserted here are: every verdict input is versioned content, a live copy that is missing or
different cannot change the verdict, and the doctrine checks still convict when a receipt is
swapped, stripped or stamped with an id its own tool never declared.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

import verify_recovery_safety as gate  # noqa: E402

RECEIPTS = sorted(gate.MANIFESTS)


class TrackedInputTests(unittest.TestCase):
    def test_every_audited_receipt_is_history_not_the_runtime_root(self) -> None:
        # The regression this test guards is subtle: a path under .project-local reads fine on
        # the machine that generated the record, so every other test still passes.
        for rel in RECEIPTS:
            self.assertTrue(rel.startswith(gate.RECEIPT_ROOT + "/"), rel)
            self.assertFalse(rel.startswith(".project-local/"), rel)

    def test_every_verdict_input_is_versioned_content(self) -> None:
        tracked = set(gate.git("ls-files").splitlines())
        for rel, (tool, _live) in gate.MANIFESTS.items():
            self.assertIn(rel, tracked, f"{rel} feeds the verdict but is not in git")
            self.assertIn(tool, tracked, f"{tool} feeds the verdict but is not in git")
        self.assertIn("reports/current/RECOVERY-SAFETY.json", tracked)

    def test_the_archived_bytes_are_the_receipts_they_came_from(self) -> None:
        # Measured at copy time on 2026-10-09: all three live copies MATCHES_ARCHIVED_COPY.
        # If this goes red, the archive was edited after the operation it receipts.
        for rel, (_tool, live) in gate.MANIFESTS.items():
            live_path = ROOT / live
            if not live_path.is_file():
                continue
            self.assertEqual(gate.file_digest(live_path), gate.file_digest(ROOT / rel), rel)

    def test_the_receipt_archive_is_byte_identical_lf_and_json_readable(self) -> None:
        for rel in RECEIPTS:
            raw = (ROOT / rel).read_bytes()
            self.assertNotIn(b"\r\n", raw, f"{rel} carries CRLF, so its digest is machine-bound")
            self.assertIsInstance(json.loads(raw.decode("utf-8")), dict, rel)


class AuditTests(unittest.TestCase):
    """The judgement functions, driven against planted receipts in a throwaway tree."""

    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.tmp = Path(self._tmp.name)
        self._repo, self._git = gate.REPO, gate.git
        gate.REPO = self.tmp
        # `receipt_is_versioned` asks git; in a throwaway tree there is no index, so the stub
        # says "yes" and lets each test plant exactly one defect at a time.
        gate.git = lambda *args: args[-1] if args and args[0] == "ls-files" else ""

    def tearDown(self) -> None:
        gate.REPO, gate.git = self._repo, self._git
        self._tmp.cleanup()

    def scaffold(self, override: dict | None = None) -> str:
        """Copy one archived receipt and its tool into the throwaway tree."""
        rel = next(r for r in gate.MANIFESTS if r.endswith("/DELETE-MANIFEST.json"))
        document = json.loads((self._repo / rel).read_text(encoding="utf-8"))
        if override:
            for key, value in override.items():
                if value is _REMOVE:
                    document.pop(key, None)
                else:
                    document[key] = value
        target = self.tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
        tool = gate.MANIFESTS[rel][0]
        tool_target = self.tmp / tool
        tool_target.parent.mkdir(parents=True, exist_ok=True)
        tool_target.write_bytes((self._repo / tool).read_bytes())
        return rel

    def audit(self, rel: str, live: str = ".project-local/nothing-here.json") -> dict:
        return gate.audit_manifest(rel, gate.MANIFESTS[rel][0], live)

    def test_an_absent_live_copy_leaves_the_verdict_alone(self) -> None:
        rel = self.scaffold()
        result = self.audit(rel)
        self.assertEqual(result["live_copy_state"], "LIVE_COPY_ABSENT")
        self.assertTrue(result["ok"], "a clean checkout cannot be a destructive-safety failure")

    def test_a_live_copy_that_differs_is_reported_not_judged(self) -> None:
        rel = self.scaffold()
        other = self.tmp / ".project-local/mutated.json"
        other.parent.mkdir(parents=True, exist_ok=True)
        other.write_text('{"schemaVersion": "mutated"}\n', encoding="utf-8", newline="\n")
        result = self.audit(rel, live=other.relative_to(self.tmp).as_posix())
        self.assertEqual(result["live_copy_state"], "DIFFERS_FROM_ARCHIVED_COPY")
        self.assertTrue(result["ok"],
                        "the live copy is machine state; drift there belongs in a report line")

    def test_a_missing_archived_receipt_is_a_failure(self) -> None:
        rel = self.scaffold()
        (self.tmp / rel).unlink()
        result = self.audit(rel)
        self.assertFalse(result["exists"])
        self.assertFalse(result["ok"])

    def test_a_receipt_stripped_of_its_receipt_field_is_convicted(self) -> None:
        rel = self.scaffold({"schemaVersion": _REMOVE, "created_at": _REMOVE})
        result = self.audit(rel)
        self.assertFalse(result["elements"]["receipt"])
        self.assertFalse(result["ok"])

    def test_a_receipt_from_another_operation_is_convicted(self) -> None:
        # Measured: the three tools declare disjoint operation ids (D030, A040, E020..E040),
        # so stamping one tool's manifest with another's id is detectable from tracked source.
        rel = self.scaffold({"task_key": f"{gate.AUTHORITY_ID}::DLDS-D030"})
        result = self.audit(rel)
        self.assertFalse(result["binding"]["names_the_tools_operation"])
        self.assertEqual(result["binding"]["ids_the_producing_tool_never_declares"], ["DLDS-D030"])
        self.assertFalse(result["ok"])

    def test_a_receipt_key_from_another_taskpack_is_convicted(self) -> None:
        rel = self.scaffold({"task_key": "DL-TP-20260908-R5::DLDS-A040"})
        result = self.audit(rel)
        self.assertEqual(result["binding"]["keys_outside_the_authority_pack"],
                         ["DL-TP-20260908-R5::DLDS-A040"])
        self.assertFalse(result["ok"])

    def test_a_receipt_naming_a_path_outside_the_repository_is_convicted(self) -> None:
        rel = next(r for r in gate.MANIFESTS if r.endswith("/DELETE-MANIFEST.json"))
        document = json.loads((self._repo / rel).read_text(encoding="utf-8"))
        document["files"][0]["path"] = "C:/Users/someone/Desktop/asset.psd"
        target = self.tmp / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                          encoding="utf-8", newline="\n")
        (self.tmp / gate.MANIFESTS[rel][0]).parent.mkdir(parents=True, exist_ok=True)
        (self.tmp / gate.MANIFESTS[rel][0]).write_bytes(
            (self._repo / gate.MANIFESTS[rel][0]).read_bytes())
        result = self.audit(rel)
        self.assertFalse(result["binding"]["paths_are_repo_relative"])
        self.assertIn("C:/Users/someone/Desktop/asset.psd", result["binding"]["non_repository_paths"])
        self.assertFalse(result["ok"])

    def test_repo_relative_is_measured_on_the_path_not_its_name(self) -> None:
        for good in ("design-lab/schemas/a.json", ".project-local/task-runtime/x",
                     "reports/current/RECOVERY-SAFETY.json"):
            self.assertTrue(gate.repo_relative(good), good)
        for bad in ("C:/x/y", "E:/assets", "/srv/x", "", "D:\\All projects"):
            self.assertFalse(gate.repo_relative(bad), bad)


class RuntimeTests(unittest.TestCase):
    def test_the_shipped_check_passes_and_writes_nothing(self) -> None:
        def porcelain() -> str:
            return subprocess.run(["git", "status", "--porcelain"], cwd=str(ROOT),
                                  capture_output=True, text=True, encoding="utf-8",
                                  errors="replace").stdout

        before = porcelain()
        result = subprocess.run([sys.executable, "-X", "utf8", "-B",
                                 str(ROOT / "scripts" / "verify_recovery_safety.py"), "--check"],
                                cwd=str(ROOT), capture_output=True, text=True,
                                encoding="utf-8", errors="replace", timeout=900)
        output = (result.stdout or "") + (result.stderr or "")
        self.assertEqual(result.returncode, 0, output[-900:])
        self.assertIn("RECOVERY_SAFETY=PASS", output)
        self.assertEqual(before, porcelain(), "the read-only form wrote a tracked file")

    def test_the_record_and_the_check_agree_on_the_machine_state_vocabulary(self) -> None:
        document = json.loads((ROOT / "reports" / "current" / "RECOVERY-SAFETY.json")
                              .read_text(encoding="utf-8"))
        states = {item["live_copy_state"]
                  for item in document["I000_destructive_operations"]["manifests"]}
        self.assertTrue(states <= {"MATCHES_ARCHIVED_COPY", "LIVE_COPY_ABSENT",
                                   "DIFFERS_FROM_ARCHIVED_COPY"}, states)
        self.assertEqual(document["I000_destructive_operations"]["failures"], [],
                         "the record was rebound while a receipt was failing")

    def test_the_verdict_is_recomputable_from_the_record_alone(self) -> None:
        document = json.loads((ROOT / "reports" / "current" / "RECOVERY-SAFETY.json")
                              .read_text(encoding="utf-8"))
        manifests = document["I000_destructive_operations"]["manifests"]
        recomputed = ("PASS" if not document["I000_destructive_operations"]["failures"]
                      and document["I010_unknown_outcome"]["ok"] else "FAIL")
        self.assertEqual(recomputed, document["verdict"])
        self.assertTrue(all(item["ok"] for item in manifests),
                        "a receipt reports ok=False while the verdict says PASS")


class _Marker:
    def __repr__(self) -> str:  # pragma: no cover - only used in failure messages
        return "<remove>"


_REMOVE = _Marker()


if __name__ == "__main__":
    unittest.main()
