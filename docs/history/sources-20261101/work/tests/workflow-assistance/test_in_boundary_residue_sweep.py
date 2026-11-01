"""Gate the in-boundary residue sweep: it may only delete what it can prove is reproducible.

The tool exists because the runtime root had accumulated 3 GB of its own scratch. That is a lot of
bytes to hand a `shutil.rmtree`, so the gate tests the screens rather than the happy path: a file
that is nowhere in git and nowhere in the working tree must stop its whole directory; the cargo
target tree must not be a declared pattern at all; and report mode must touch nothing.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOL = ROOT / "scripts" / "audit" / "in_boundary_residue_sweep.py"
RUN = ROOT / ".project-local" / "runs" / "residue-sweep-tests"
RUN.mkdir(parents=True, exist_ok=True)

spec = importlib.util.spec_from_file_location("residue_sweep", TOOL)
sweep = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sweep)  # type: ignore[attr-defined]


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def write(path: Path, text: str) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    return path


class RecoveryProofTests(unittest.TestCase):
    def test_bytes_that_are_nowhere_in_the_repo_stop_the_directory(self) -> None:
        rel = "definitely-not-a-tracked-path-8ff1c2.md"
        unique = "nothing in git or on disk matches this\n"
        ok, how = sweep.is_recoverable(rel, sha(unique.encode()), {"allowed_members": ()},
                                       sweep.TrackedMatcher(), "x")
        self.assertFalse(ok, how)
        self.assertIn("unique bytes", how)

    def test_a_copy_of_a_file_the_repository_already_holds_is_recoverable(self) -> None:
        agents = ROOT / "AGENTS.md"
        body = agents.read_text(encoding="utf-8")
        ok, how = sweep.is_recoverable("AGENTS.md", sha(body.encode("utf-8")),
                                       {"allowed_members": ()}, sweep.TrackedMatcher(), "x")
        self.assertTrue(ok, how)
        # Either repo-backed proof is acceptable — HEAD or the working tree — because both mean the
        # bytes survive the deletion. What must NOT be the answer is the scratch-shape fallback.
        self.assertTrue(how.startswith("tracked bytes") or how.startswith("working-tree bytes"), how)
        self.assertNotIn("scratch shape", how)

    def test_a_declared_scratch_shape_is_recoverable_by_its_own_pattern(self) -> None:
        spec = {"allowed_members": ("udf-",)}
        ok, how = sweep.is_recoverable("udf-123/Default/Bookmarks", sha(b"x"), spec,
                                       sweep.TrackedMatcher(), "x")
        self.assertTrue(ok, how)
        self.assertEqual("declared scratch shape", how)

    def test_the_cargo_target_tree_is_not_a_deletable_pattern(self) -> None:
        # 1.4 GB of the only locally runnable desktop evidence, rebuildable only with a toolchain
        # this machine does not have on PATH. Naming it would turn cleanup into destruction.
        self.assertNotIn("u19-msvc", sweep.RESIDUE)
        self.assertFalse(any(k.startswith("u19") for k in sweep.RESIDUE))
        for pattern, spec in sweep.RESIDUE.items():
            self.assertTrue(spec.get("regeneratedBy"), f"{pattern} declares no regenerating command")


class SweepBehaviourTests(unittest.TestCase):
    def setUp(self) -> None:
        self.dir = RUN / "gate-fixture"
        self._cleanup()

    def tearDown(self) -> None:
        self._cleanup()

    def _cleanup(self) -> None:
        import shutil
        if self.dir.exists():
            shutil.rmtree(self.dir)

    def _make(self, files: dict[str, str]) -> Path:
        base = RUN / "gate-fixture"
        for rel, body in files.items():
            write(base / rel, body)
        return base

    def _cli(self, extra: list[str]) -> subprocess.CompletedProcess:
        shim = write(RUN / "shim.py",
                     "\n".join([
                         "import sys, pathlib",
                         f"sys.path.insert(0, {str(TOOL.parent)!r})",
                         "import in_boundary_residue_sweep as m",
                         "import json",
                         f"m.RUNS = pathlib.Path({str(RUN)!r})",
                         f"m.REPO = pathlib.Path({str(ROOT)!r})",
                         f"m.ARTIFACTS = pathlib.Path({str(RUN / 'artifacts')!r})",
                         f"m.LEDGER = pathlib.Path({str(RUN / 'ledger.jsonl')!r})",
                         "m.RESIDUE = json.loads(pathlib.Path("
                         f"{str(RUN / 'patterns.json')!r}).read_text(encoding='utf-8'))",
                         f"sys.argv = [str(m.__file__)] + {extra!r}",
                         "raise SystemExit(m.main())",
                     ]) + "\n")
        return subprocess.run([sys.executable, str(shim)], capture_output=True, text=True,
                              encoding="utf-8", errors="replace", cwd=str(ROOT))

    def _patterns(self, spec: dict) -> None:
        write(RUN / "patterns.json", json.dumps({"gate-fixture": spec}, ensure_ascii=False))

    def test_report_mode_deletes_nothing(self) -> None:
        base = self._make({"keep.txt": "unique content not in git\n"})
        self._patterns({"regeneratedBy": "true", "why": "fixture", "allowed_members": ()})
        proc = self._cli([])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RESIDUE_SWEEP_REPORTED", proc.stdout)
        self.assertIn("BLOCKED", proc.stdout)
        self.assertTrue((base / "keep.txt").is_file())

    def test_a_candidate_is_removed_and_manifest_recorded_with_per_file_digests(self) -> None:
        base = self._make({"udf-x/a.json": '{"a":1}', "udf-x/b.bin": "bytes"})
        self._patterns({"regeneratedBy": "python -m unittest -h", "why": "fixture scratch",
                        "allowed_members": ("udf-x",)})
        proc = self._cli(["--apply"])
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("RESIDUE_SWEEP_APPLIED", proc.stdout)
        self.assertFalse(base.exists())
        ledgers = (RUN / "ledger.jsonl").read_text(encoding="utf-8").splitlines()
        line = json.loads(ledgers[-1])
        for field in ("at", "actor", "action", "outOfRoot", "target", "source", "trace", "locate",
                      "clean", "migrate", "reversible"):
            self.assertIn(field, line), f"ledger line missing {field}"
        self.assertFalse(line["outOfRoot"])
        manifest = json.loads((ROOT / line["target"]).read_text(encoding="utf-8"))
        entry = manifest["entries"][0]
        self.assertEqual({f["path"].split("/")[-1] for f in entry["files"]}, {"a.json", "b.bin"})
        for f in entry["files"]:
            self.assertEqual(len(f["sha256"]), 64)
            self.assertGreater(f["bytes"], 0)

    def test_one_unique_file_blocks_the_whole_directory_from_deletion(self) -> None:
        base = self._make({"udf-x/a.json": "declared", "notes.md": "I am unique and I matter\n"})
        self._patterns({"regeneratedBy": "true", "why": "fixture", "allowed_members": ("udf-x",)})
        proc = self._cli(["--apply"])
        self.assertIn("BLOCKED", proc.stdout)
        self.assertTrue((base / "notes.md").is_file(), "a blocked directory was still touched")
        self.assertTrue((base / "udf-x" / "a.json").is_file(),
                        "the declared shape inside a blocked directory must survive too")


if __name__ == "__main__":
    unittest.main(verbosity=2)
