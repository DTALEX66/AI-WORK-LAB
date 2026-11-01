"""WLGM-050 tests: candidate discovery + allowlist boundary."""
from __future__ import annotations

import subprocess
import tempfile
import unittest
from pathlib import Path

from project_candidate_discovery import (
    DiscoveryConfig,
    discover_candidates,
)


class CandidateDiscoveryTests(unittest.TestCase):
    def _tree(self) -> tuple[Path, tempfile.TemporaryDirectory]:
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        return Path(raw.name), raw

    def _init_repo(self, path: Path, name: str) -> Path:
        repo = path / name
        repo.mkdir(parents=True)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo

    def test_discovers_repo_as_candidate_not_registered(self) -> None:
        root, _ = self._tree()
        self._init_repo(root, "alpha")
        config = DiscoveryConfig(discovery_root=root, max_depth=2)
        candidates = discover_candidates(config)
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].status, "CANDIDATE")
        self.assertNotIn("approved", candidates[0].minimal_metadata())

    def test_deny_list_skips_candidate(self) -> None:
        root, _ = self._tree()
        self._init_repo(root, "beta")
        config = DiscoveryConfig(discovery_root=root, max_depth=2, deny_list={"beta"})
        self.assertEqual(discover_candidates(config), [])

    def test_never_scan_root_skipped(self) -> None:
        root, _ = self._tree()
        self._init_repo(root, "gamma")
        config = DiscoveryConfig(discovery_root=root, max_depth=2, never_scan={str(root.resolve())})
        self.assertEqual(discover_candidates(config), [])

    def test_excluded_dirs_never_recursed(self) -> None:
        root, _ = self._tree()
        repo = self._init_repo(root, "delta")
        (repo / "node_modules").mkdir(parents=True)
        (repo / "node_modules" / "pkg").mkdir()
        subprocess.run(["git", "-C", str(repo), "init", "-q", str(repo / "node_modules" / "pkg")], check=False)
        config = DiscoveryConfig(discovery_root=root, max_depth=3)
        candidates = discover_candidates(config)
        # node_modules/pkg must NOT appear as a candidate.
        ids = [c.candidate_id for c in candidates]
        self.assertNotIn("pkg", ids)
        self.assertEqual(ids, ["delta"])

    def test_large_resource_trees_not_recursed(self) -> None:
        root, _ = self._tree()
        self._init_repo(root, "eps")
        (root / "design-assets" / "deep" / "deeper").mkdir(parents=True)
        self._init_repo(root / "design-assets" / "deep" / "deeper", "hidden-repo")
        config = DiscoveryConfig(discovery_root=root, max_depth=5)
        candidates = discover_candidates(config)
        ids = [c.candidate_id for c in candidates]
        self.assertNotIn("hidden-repo", ids)
        self.assertNotIn("design-assets", ids)

    def test_fingerprint_is_stable_and_secret_free(self) -> None:
        root, _ = self._tree()
        repo = self._init_repo(root, "zeta")
        config = DiscoveryConfig(discovery_root=root, max_depth=2)
        first = discover_candidates(config)[0]
        second = discover_candidates(config)[0]
        self.assertEqual(first.root_fingerprint, second.root_fingerprint)
        self.assertEqual(first.root_fingerprint, second.root_fingerprint)


if __name__ == "__main__":
    unittest.main()
