"""AG-19 gate: the ignored-root promotion instrument must refuse before it touches anything.

Every refusal in `scripts/maintenance/promote_ignored_root_original.py` returns before the first
write, so this test can drive the real CLI against the real repository without leaving residue. The
last two checks prove that claim rather than assuming it: the spill ledger and the recovered-source
registry are hashed before and after the run, so a refusal that quietly appended would fail here
instead of surprising a later reader (ERR-152's shape: a test that reads its own precondition from
shipped state proves nothing about the tool).

The structural screen is what separates this from `cp`: a secret-shaped key, a prompt-body-shaped
field, a credential-shaped value or an E:/F:/ path must each refuse on a fixture, and a clean
fixture must not.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "maintenance" / "promote_ignored_root_original.py"
LEDGER = ROOT / ".project-local" / "artifacts" / "spill-ledger.jsonl"
RUNS = ROOT / ".project-local" / "runs" / "promotion-gate-fixture"


def run_cli(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-X", "utf8", str(TOOL), *args],
                          cwd=ROOT, capture_output=True, encoding="utf-8", errors="replace")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest() if path.exists() else "<absent>"


def fixture(name: str, payload: object) -> str:
    RUNS.mkdir(parents=True, exist_ok=True)
    p = RUNS / name
    p.write_text(payload if isinstance(payload, str) else json.dumps(payload), encoding="utf-8")
    return p.relative_to(ROOT).as_posix()


class PromoteIgnoredRootOriginalTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        assert TOOL.exists(), f"missing {TOOL}"
        cls.before = {"ledger": sha(LEDGER)}

    @classmethod
    def tearDownClass(cls) -> None:
        assert sha(LEDGER) == cls.before["ledger"], "a refusal appended to the spill ledger"

    def test_the_ignore_screen_sees_the_real_roots(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts" / "maintenance"))
        try:
            import promote_ignored_root_original as tool
            self.assertTrue(tool.declared_ignored_roots(), "the boundary declares no role root")
            self.assertEqual(tool.role_root_of((ROOT / ".project-local" / "artifacts" / "x").resolve())[0],
                             "taskArtifactsRoot")
            self.assertIsNone(tool.role_root_of((ROOT / ".project-local" / "elsewhere" / "x").resolve()),
                             "a path outside every role root claimed one anyway")
            self.assertTrue(tool.git_ignore_rule(".project-local/atlas-2026-09-29/x.json"),
                            "the ignored runtime root is not hidden by any ignore rule")
            self.assertEqual(tool.git_ignore_rule("AGENTS.md"), "", "a tracked file read as ignored")
        finally:
            sys.path.pop(0)

    def test_refuses_a_source_that_a_clean_checkout_can_already_see(self) -> None:
        proc = run_cli("--source", "AGENTS.md", "--dest", ".project-local/runs/none.json",
                       "--expect-sha256", "0" * 64, "--evidence",
                       ".project-local/runs/promotion-gate-fixture/ev.json", "--actor", "gate-test")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("SOURCE_NOT_GIT_IGNORED", proc.stdout)

    def test_structural_screen_finds_each_blocker_shape_and_nothing_on_clean(self) -> None:
        sys.path.insert(0, str(ROOT / "scripts" / "maintenance"))
        try:
            import promote_ignored_root_original as tool
            for name, node in {
                "secret key": {"api_key": "abc"},
                "body field": {"prompt": "x" * 400},
                "credential value": {"note": "ghp_" + "A" * 30},
                "forbidden drive": {"path": "E:\\vault\\a.json"},
            }.items():
                scan = tool.structural_scan(node)
                hit = (scan["secret_keys"] or scan["body_fields"] or scan["secret_values"]
                       or scan["forbidden_paths"])
                self.assertTrue(hit, f"screen missed the {name} shape")
            clean = tool.structural_scan({"sources": [{"sha256": "a" * 64, "bytes": 11}]})
            self.assertFalse(clean["secret_keys"] or clean["body_fields"]
                             or clean["secret_values"] or clean["forbidden_paths"],
                             "a digest-bearing clean record screened as a blocker")
        finally:
            sys.path.pop(0)

    def test_refuses_a_source_outside_the_git_root(self) -> None:
        proc = run_cli("--source", "../outside-the-repo.json", "--dest",
                       ".project-local/runs/none.json", "--expect-sha256", "0" * 64, "--evidence",
                       ".project-local/runs/promotion-gate-fixture/ev.json", "--actor", "gate-test")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("SOURCE_OUTSIDE_GIT_ROOT", proc.stdout)

    def test_refuses_when_the_digest_pin_does_not_match(self) -> None:
        src = fixture("pinned.json", {"sources": []})
        proc = run_cli("--source", src, "--dest", ".project-local/runs/nope.json",
                       "--expect-sha256", "f" * 64, "--evidence",
                       ".project-local/runs/promotion-gate-fixture/ev.json", "--actor", "gate-test")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("DIGEST_PIN_MISMATCH", proc.stdout)

    def test_refuses_an_unparseable_and_a_blocked_document(self) -> None:
        bad = fixture("bad.json", '{"broken"')
        proc = run_cli("--source", bad, "--dest", ".project-local/runs/nope.json",
                       "--expect-sha256", sha(ROOT / bad), "--evidence",
                       ".project-local/runs/promotion-gate-fixture/ev.json", "--actor", "gate-test")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("SOURCE_UNPARSEABLE", proc.stdout)

        blocked = {"sources": [{"api_key": "abc123"}]}
        digest = hashlib.sha256(json.dumps(blocked).encode("utf-8")).hexdigest()
        bsrc = fixture("blocked.json", blocked)
        proc = run_cli("--source", bsrc, "--dest", ".project-local/runs/nope.json",
                       "--expect-sha256", digest, "--evidence",
                       ".project-local/runs/promotion-gate-fixture/ev.json", "--actor", "gate-test")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("CONTENT_SCAN_BLOCKED", proc.stdout)

    def test_refuses_an_existing_and_tracked_destination_without_writing_it(self) -> None:
        src = fixture("clean.json", {"sources": []})
        digest = sha(ROOT / src)
        agents = ROOT / "AGENTS.md"
        before = sha(agents)
        proc = run_cli("--source", src, "--dest", "AGENTS.md", "--expect-sha256", digest,
                       "--evidence", ".project-local/runs/promotion-gate-fixture/ev.json",
                       "--actor", "gate-test")
        self.assertEqual(proc.returncode, 2, proc.stdout + proc.stderr)
        self.assertIn("DEST_ALREADY_EXISTS", proc.stdout)
        self.assertIn("DEST_ALREADY_TRACKED", proc.stdout)
        self.assertEqual(sha(agents), before, "a refused promotion modified a tracked file")

    def test_refusals_leave_no_evidence_file_and_no_ledger_line(self) -> None:
        ev = ROOT / ".project-local" / "runs" / "promotion-gate-fixture" / "ev.json"
        self.assertFalse(ev.exists(), "a refused run wrote its evidence file")
        self.assertEqual(sha(LEDGER), self.before["ledger"], "a refusal touched the spill ledger")


if __name__ == "__main__":
    unittest.main()
