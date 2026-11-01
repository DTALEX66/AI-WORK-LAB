"""Contract tests for single-project parallelism (WL3-400 / MR-14).

Covers one-writer-per-checkout, path overlap blocking, schema dependency
serialization, evidence-only commit coordinator.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from parallelism_coordinator import (CommitCoordinator, PathLease,
                                     SchemaDependencyResolver)


class PathLeaseTests(unittest.TestCase):
    def test_disjoint_paths_parallel_ok(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            leases = PathLease(Path(tmp))
            self.assertEqual(leases.acquire("t1", ["a.py"])["status"], "HELD")
            self.assertEqual(leases.acquire("t2", ["b.py"])["status"], "HELD")

    def test_overlap_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            leases = PathLease(Path(tmp))
            leases.acquire("t1", ["scripts/x.py"])
            result = leases.acquire("t2", ["scripts/x.py"])
            self.assertEqual(result["status"], "BLOCKED")
            self.assertEqual(result["reason_code"], "PATH_OVERLAP")

    def test_ancestor_overlap_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            leases = PathLease(Path(tmp))
            leases.acquire("t1", ["scripts/workflow"])
            result = leases.acquire("t2", ["scripts/workflow/x.py"])
            self.assertEqual(result["status"], "BLOCKED")

    def test_release_frees_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            leases = PathLease(Path(tmp))
            leases.acquire("t1", ["a.py"])
            leases.release("t1")
            self.assertEqual(leases.acquire("t2", ["a.py"])["status"], "HELD")


class SchemaDependencyTests(unittest.TestCase):
    def test_shared_schema_conflicts(self) -> None:
        resolver = SchemaDependencyResolver()
        resolver.register("t1", ["s1.json"])
        resolver.register("t2", ["s1.json"])
        self.assertEqual(resolver.conflicts("t1"), ["t2"])

    def test_disjoint_schemas_no_conflict(self) -> None:
        resolver = SchemaDependencyResolver()
        resolver.register("t1", ["s1.json"])
        resolver.register("t2", ["s2.json"])
        self.assertEqual(resolver.conflicts("t1"), [])


class CommitCoordinatorTests(unittest.TestCase):
    def test_assembles_evidence_only(self) -> None:
        coordinator = CommitCoordinator()
        result = coordinator.assemble("t1", {"tree_hash": "abc"})
        self.assertEqual(result["status"], "EVIDENCE_READY")
        self.assertEqual(result["git_side_effect"], "WAITING_APPROVAL")

    def test_requires_tree_hash(self) -> None:
        coordinator = CommitCoordinator()
        with self.assertRaises(ValueError):
            coordinator.assemble("t1", {})


if __name__ == "__main__":
    unittest.main()
