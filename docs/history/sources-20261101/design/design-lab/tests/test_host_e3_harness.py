# SPDX-License-Identifier: MIT
"""Host E3 harness tests (Batch F-4).

These tests exist to prove the *negative*: a fabricated E3 cannot pass the
machine checks, and an empty evidence store never reads as E3. They build
records in temporary directories, so nothing here creates real evidence, touches
the repo's evidence store, or starts any host application.

Covered:
1. fake E3 (level E3, no ``host`` block)                  -> INVALID
2. ``host`` present but artifact sha256 wrong             -> INVALID
3. ``host`` present, hashes right, boundTreeSha == HEAD   -> VALID
4. ``host`` present, boundTreeSha is an ancestor of HEAD  -> VALID
5. ``host`` present, boundTreeSha unrelated to HEAD       -> INVALID
6. empty evidence directory                              -> NO_RECORD (never VALID/E3)
7. named-but-missing --record                            -> INVALID
8. the built-in (stdlib-only) validator rejects the fake E3 too
9. the probe reports HOST_ABSENT without a configured endpoint
10. neither tool writes anything into the evidence store
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

TESTS_DIR = Path(__file__).resolve().parent
DESIGN_LAB = TESTS_DIR.parent
REPO = DESIGN_LAB.parent
SCRIPTS = DESIGN_LAB / "scripts"
VERIFIER_PATH = SCRIPTS / "verify_host_e3_evidence.py"
PROBE_PATH = SCRIPTS / "host_e3_probe.py"
EVIDENCE_STORE = REPO / ".project-local" / "task-artifacts" / "host-e3"
SUMMARY_RE = re.compile(r"^HOST_E3=(NO_RECORD|VALID|INVALID) records=(\d+) findings=(\[.*\])$")
PROBE_RE = re.compile(r"^HOST_E3_PROBE=(HOST_PRESENT|HOST_ABSENT) details=(.+)$")


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader, f"cannot load {path}"
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


VERIFIER = load_module("verify_host_e3_evidence_under_test", VERIFIER_PATH)
PROBE = load_module("host_e3_probe_under_test", PROBE_PATH)


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip()


HEAD = git("rev-parse", "HEAD")


def sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def make_record(level: str = "E3", bound_tree_sha: str | None = None, approver: str = "owner:alex",
                host: dict | None = None) -> dict:
    record = {
        "evidenceId": "ev-test-0001",
        "level": level,
        "boundTreeSha": bound_tree_sha if bound_tree_sha is not None else HEAD,
        "owner": "design-lab",
        "timestamp": "2026-09-20T12:00:00Z",
        "command": "python design-lab/scripts/verify_host_e3_evidence.py",
        "environment": "fixture",
        "inputHash": "sha256:" + "b" * 64,
        "result": "fixture",
        "approver": approver,
    }
    if host is not None:
        record["host"] = host
    return record


def make_host(artifact_path: Path, artifact_sha: str | None = None,
              adapter_sha: str = "a" * 64) -> dict:
    return {
        "product": "Adobe Photoshop",
        "productVersion": "26.0.0",
        "adapterId": "adapter-adobe-photoshop",
        "adapterVersion": "0.1.0",
        "adapterSha256": adapter_sha,
        "invocation": "uxp executeAsModal -> prepareRunRelativeLayers",
        "readback": ["layer-tree readback ok", "dimensions 1920x1080", "rollback verified"],
        "artifacts": [{"path": str(artifact_path), "sha256": artifact_sha or ""}],
    }


class HarnessCase(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory(prefix="host-e3-harness-")
        self.tmp = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)

    def write_record(self, record: dict, name: str = "record.json") -> Path:
        path = self.tmp / name
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return path

    def run_verifier(self, *args: str, env: dict | None = None) -> subprocess.CompletedProcess:
        environment = {**os.environ, "PYTHONIOENCODING": "utf-8"}
        environment.pop("DL_HOST_E3_FORCE_FALLBACK", None)
        if env:
            environment.update(env)
        return subprocess.run([sys.executable, "-B", str(VERIFIER_PATH), *args],
                              capture_output=True, text=True, encoding="utf-8", errors="replace",
                              cwd=str(REPO), env=environment)

    def parse_summary(self, stdout: str) -> tuple[str, int, list]:
        line = next((ln for ln in stdout.splitlines() if ln.startswith("HOST_E3=")), None)
        self.assertIsNotNone(line, f"no HOST_E3 summary line in output:\n{stdout}")
        match = SUMMARY_RE.match(line)
        self.assertIsNotNone(match, f"summary line violates the output contract: {line!r}")
        return match.group(1), int(match.group(2)), json.loads(match.group(3))


class FakeE3RejectionTests(HarnessCase):
    def test_fake_e3_without_host_block_is_invalid(self):
        """The whole point: level E3 with no host provenance must not pass."""
        path = self.write_record(make_record(level="E3"))
        result = self.run_verifier("--record", str(path))
        verdict, records, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertEqual(records, 1)
        self.assertEqual(result.returncode, 1)
        joined = " | ".join(findings)
        self.assertIn("host", joined)
        self.assertIn("required property", joined)

    def test_fake_e3_rejected_by_builtin_validator_too(self):
        """No jsonschema available must not open a hole."""
        path = self.write_record(make_record(level="E3"))
        result = self.run_verifier("--record", str(path),
                                   env={"DL_HOST_E3_FORCE_FALLBACK": "1"})
        verdict, _, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertEqual(result.returncode, 1)
        self.assertIn("builtin", " ".join(findings))

    def test_host_with_wrong_artifact_sha256_is_invalid(self):
        artifact = self.tmp / "readback.psd"
        artifact.write_bytes(b"fixture bytes that were never really produced")
        host = make_host(artifact, artifact_sha="0" * 64)
        path = self.write_record(make_record(level="E3", host=host))
        result = self.run_verifier("--record", str(path))
        verdict, _, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertEqual(result.returncode, 1)
        self.assertIn("sha256 mismatch", " ".join(findings))

    def test_host_with_missing_artifact_file_is_invalid(self):
        host = make_host(self.tmp / "does-not-exist.psd", artifact_sha="0" * 64)
        path = self.write_record(make_record(level="E3", host=host))
        result = self.run_verifier("--record", str(path))
        verdict, _, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertIn("not found", " ".join(findings))

    def test_unrelated_bound_tree_sha_is_invalid(self):
        artifact = self.tmp / "readback.psd"
        payload = b"real bytes, real hash"
        artifact.write_bytes(payload)
        host = make_host(artifact, artifact_sha=sha256_bytes(payload))
        path = self.write_record(make_record(level="E3", bound_tree_sha="0" * 40, host=host))
        result = self.run_verifier("--record", str(path))
        verdict, _, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertIn("neither HEAD", " ".join(findings))

    def test_empty_approver_is_invalid(self):
        artifact = self.tmp / "readback.psd"
        payload = b"real bytes, real hash"
        artifact.write_bytes(payload)
        host = make_host(artifact, artifact_sha=sha256_bytes(payload))
        path = self.write_record(make_record(level="E3", approver="   ", host=host))
        result = self.run_verifier("--record", str(path))
        verdict, _, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertIn("approver is empty", " ".join(findings))

    def test_non_e3_level_is_not_counted_as_host_e3(self):
        path = self.write_record(make_record(level="E1"))
        result = self.run_verifier("--record", str(path))
        verdict, _, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertIn("is not 'E3'", " ".join(findings))

    def test_missing_named_record_is_invalid(self):
        result = self.run_verifier("--record", str(self.tmp / "absent.json"))
        verdict, records, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "INVALID")
        self.assertEqual(records, 1)
        self.assertEqual(result.returncode, 1)
        self.assertIn("not found", " ".join(findings))


class ValidE3Tests(HarnessCase):
    def test_real_hashes_and_bound_tree_are_valid(self):
        artifact = self.tmp / "readback.psd"
        payload = b"native fixture bytes, hashed for real"
        artifact.write_bytes(payload)
        host = make_host(artifact, artifact_sha=sha256_bytes(payload))
        path = self.write_record(make_record(level="E3", host=host))
        result = self.run_verifier("--record", str(path))
        verdict, records, findings = self.parse_summary(result.stdout)
        self.assertEqual(findings, [])
        self.assertEqual(verdict, "VALID")
        self.assertEqual(records, 1)
        self.assertEqual(result.returncode, 0)

    def test_ancestor_bound_tree_sha_is_valid(self):
        ancestor = git("rev-parse", "HEAD~1")
        self.assertTrue(ancestor, "fixture precondition: HEAD~1 must resolve")
        artifact = self.tmp / "readback.psd"
        payload = b"bytes bound to an ancestor tree"
        artifact.write_bytes(payload)
        host = make_host(artifact, artifact_sha=sha256_bytes(payload))
        path = self.write_record(make_record(level="E3", bound_tree_sha=ancestor, host=host))
        result = self.run_verifier("--record", str(path))
        verdict, _, findings = self.parse_summary(result.stdout)
        self.assertEqual(findings, [])
        self.assertEqual(verdict, "VALID")

    def test_multiple_records_are_all_checked(self):
        good_artifact = self.tmp / "good.psd"
        good_payload = b"good"
        good_artifact.write_bytes(good_payload)
        good = self.write_record(make_record(level="E3",
                                             host=make_host(good_artifact,
                                                            artifact_sha=sha256_bytes(good_payload))),
                                 name="good.json")
        bad = self.write_record(make_record(level="E3"), name="bad.json")
        result = self.run_verifier("--record", str(good), "--record", str(bad))
        verdict, records, findings = self.parse_summary(result.stdout)
        self.assertEqual(records, 2)
        self.assertEqual(verdict, "INVALID")
        self.assertTrue(findings)
        self.assertTrue(all("bad.json" in finding for finding in findings),
                        f"only the fabricated record may produce findings: {findings}")


class NoRecordTests(HarnessCase):
    """No record must read as NO_RECORD — never VALID, never E3."""

    def test_empty_directory_is_no_record(self):
        empty = self.tmp / "empty"
        empty.mkdir()
        result = self.run_verifier("--dir", str(empty))
        verdict, records, findings = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "NO_RECORD")
        self.assertEqual(records, 0)
        self.assertEqual(findings, [])
        self.assertEqual(result.returncode, 0, "an empty store is not a failure")
        self.assertIn("当前没有 host E3 证据，能力等级不得因此提升", result.stdout)

    def test_absent_directory_is_no_record(self):
        result = self.run_verifier("--dir", str(self.tmp / "never-created"))
        verdict, records, _ = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "NO_RECORD")
        self.assertEqual(records, 0)
        self.assertEqual(result.returncode, 0)

    def test_no_record_is_never_reported_as_e3_or_valid(self):
        """Guards against the 'silence becomes a level' failure mode."""
        empty = self.tmp / "empty"
        empty.mkdir()
        result = self.run_verifier("--dir", str(empty))
        summary = next(ln for ln in result.stdout.splitlines() if ln.startswith("HOST_E3="))
        self.assertNotIn("VALID", summary)
        self.assertNotIn("INVALID", summary)

    def test_scan_directory_without_json_is_no_record(self):
        store = self.tmp / "store"
        store.mkdir()
        (store / "notes.txt").write_text("no records here\n", encoding="utf-8")
        result = self.run_verifier("--dir", str(store))
        verdict, records, _ = self.parse_summary(result.stdout)
        self.assertEqual(verdict, "NO_RECORD")
        self.assertEqual(records, 0)


class ProbeTests(HarnessCase):
    def test_probe_without_endpoint_is_absent(self):
        environment = {k: v for k, v in os.environ.items() if k != "DL_HOST_E3_ENDPOINT"}
        environment["PYTHONIOENCODING"] = "utf-8"
        result = subprocess.run([sys.executable, "-B", str(PROBE_PATH)],
                                capture_output=True, text=True, encoding="utf-8",
                                errors="replace", cwd=str(REPO), env=environment)
        self.assertEqual(result.returncode, 0)
        line = next((ln for ln in result.stdout.splitlines() if ln.startswith("HOST_E3_PROBE=")), None)
        self.assertIsNotNone(line, result.stdout)
        match = PROBE_RE.match(line)
        self.assertIsNotNone(match, f"probe line violates the output contract: {line!r}")
        self.assertEqual(match.group(1), "HOST_ABSENT")
        self.assertIn("endpoint=unset", match.group(2))
        self.assertIn("host_launched=false", match.group(2))

    def test_probe_logic_is_env_driven_and_launches_nothing(self):
        absent, details = PROBE.probe({})
        self.assertEqual(absent, "HOST_ABSENT")
        self.assertIn("host_launched=false", details)
        present, present_details = PROBE.probe({"DL_HOST_E3_ENDPOINT": "uxp://fixture-session"})
        self.assertEqual(present, "HOST_PRESENT")
        self.assertIn("endpoint=set", present_details)
        self.assertNotIn("uxp://fixture-session", present_details,
                         "the probe must not echo credentials or full endpoints")


class NoSideEffectTests(HarnessCase):
    """Neither tool may create evidence or promote a level."""

    def store_snapshot(self) -> list:
        if not EVIDENCE_STORE.is_dir():
            return []
        return sorted(str(p) for p in EVIDENCE_STORE.rglob("*"))

    def test_verifier_writes_nothing_into_the_evidence_store(self):
        before = self.store_snapshot()
        result = self.run_verifier("--dir", str(self.tmp / "empty-store"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(self.store_snapshot(), before,
                         "the verifier must never write into the evidence store")

    def test_verifier_module_exposes_no_promotion_helper(self):
        names = {name for name in dir(VERIFIER) if not name.startswith("_")}
        forbidden = {"promote", "write_record", "generate_record", "emit_e3", "create_evidence"}
        self.assertEqual(names & forbidden, set(),
                         "the verifier must not offer any way to create or promote E3")

    def test_main_is_callable_without_touching_stdout_contract(self):
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            code = VERIFIER.main(["--dir", str(self.tmp / "absent")])
        self.assertEqual(code, 0)
        self.assertIn("HOST_E3=NO_RECORD", buffer.getvalue())


if __name__ == "__main__":
    unittest.main(verbosity=2)
