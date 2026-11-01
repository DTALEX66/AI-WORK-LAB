"""WLGM-110/120 tests: process + git fallback collectors."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from git_collector import collect_git_observation
from process_collector import collect_agent_processes


class ProcessCollectorTests(unittest.TestCase):
    @mock.patch(
        "process_collector._wmic_or_powershell",
        return_value=[
            {"ProcessId": "101", "ParentProcessId": "1", "Name": "Hermes.exe", "CreationDate": "20260814090000"},
            {"ProcessId": "102", "ParentProcessId": "1", "Name": "Hermes.exe", "CreationDate": "20260814090001"},
            {"ProcessId": "103", "ParentProcessId": "1", "Name": "Codex.exe", "CreationDate": "20260814090002"},
            {"ProcessId": "104", "ParentProcessId": "1", "Name": "notepad.exe", "CreationDate": "20260814090003"},
        ],
    )
    def test_dedupes_multi_session_electron(self, _mock) -> None:
        obs = collect_agent_processes(patterns=("hermes", "codex"))
        images = {o.image_name for o in obs}
        self.assertEqual(images, {"hermes.exe", "codex.exe"})
        # Two Hermes processes share the same parent -> one instance.
        self.assertEqual(len([o for o in obs if o.image_name == "hermes.exe"]), 1)
        self.assertEqual(len(obs), 2)

    @mock.patch("process_collector._wmic_or_powershell", return_value=[])
    def test_no_processes_returns_empty(self, _mock) -> None:
        self.assertEqual(collect_agent_processes(), [])

    def test_record_shape(self) -> None:
        from process_collector import ProcessObservation

        record = ProcessObservation(pid=1, parent_pid=None, image_name="hermes.exe").to_record()
        self.assertEqual(record["pid"], 1)
        self.assertIn("sanitizedArgs", record)


class GitCollectorTests(unittest.TestCase):
    def _repo(self) -> tuple[Path, tempfile.TemporaryDirectory]:
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        repo = Path(raw.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.email", "t@t"], check=True)
        subprocess.run(["git", "-C", str(repo), "config", "user.name", "t"], check=True)
        (repo / "a.txt").write_text("x", encoding="utf-8")
        subprocess.run(["git", "-C", str(repo), "add", "a.txt"], check=True)
        subprocess.run(["git", "-C", str(repo), "commit", "-q", "-m", "init"], check=True)
        return repo, raw

    def test_collects_head_and_no_lock(self) -> None:
        repo, _ = self._repo()
        obs = collect_git_observation(repo)
        self.assertEqual(len(obs.head_sha), 40)
        self.assertIsNotNone(obs.common_dir)
        # No index lock left behind.
        self.assertFalse((repo / ".git" / "index.lock").exists())

    def test_dirty_count(self) -> None:
        repo, _ = self._repo()
        (repo / "dirty.txt").write_text("y", encoding="utf-8")
        obs = collect_git_observation(repo)
        self.assertGreaterEqual(obs.dirty_count, 1)

    def test_remote_identity_normalized(self) -> None:
        repo, _ = self._repo()
        subprocess.run(["git", "-C", str(repo), "remote", "add", "origin", "git@github.com:DTALEX66/WORK-LAB.git"], check=True)
        obs = collect_git_observation(repo)
        self.assertEqual(obs.remote_identity, "github:DTALEX66/WORK-LAB")

    def test_dirty_disabled(self) -> None:
        repo, _ = self._repo()
        obs = collect_git_observation(repo, include_dirty=False)
        self.assertIsNone(obs.dirty_count)


if __name__ == "__main__":
    unittest.main()
