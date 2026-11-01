"""Contract tests for session/memory/cache isolation (WL3-330 / MR-11).

Covers taskpack §20.5 + §MR-11: project isolation, contamination, TTL,
promotion gating, namespace determinism, forbidden-body enforcement.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts/workflow"))

from memory_isolation import MemoryStore, Namespace, PromotionGate


def ns_a(task: str = "t1") -> Namespace:
    return Namespace("u1", "i1", "project-a", "c1", task_id=task)


def ns_b(task: str = "t1") -> Namespace:
    return Namespace("u1", "i1", "project-b", "c1", task_id=task)


class MemoryIsolationTests(unittest.TestCase):
    def test_project_isolation_keys_differ(self) -> None:
        self.assertNotEqual(ns_a().key("project_memory"), ns_b().key("project_memory"))
        self.assertNotEqual(ns_a().key("task_ephemeral"), ns_b().key("task_ephemeral"))

    def test_user_global_shared_across_projects(self) -> None:
        self.assertEqual(ns_a().key("user_global"), ns_b().key("user_global"))

    def test_unknown_layer_rejected(self) -> None:
        with self.assertRaises(ValueError):
            ns_a().key("bogus")

    def test_a_content_never_read_in_b(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.write(ns_a(), "task_ephemeral", "notes",
                        {"id": "n1", "text": "secret-a", "ttl_seconds": 3600})
            self.assertEqual(len(store.read(ns_b(), "task_ephemeral", "notes")), 0)
            self.assertEqual(len(store.read(ns_a(), "task_ephemeral", "notes")), 1)

    def test_ttl_expired_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.write(ns_a(), "task_ephemeral", "notes",
                        {"id": "n1", "text": "x", "ttl_seconds": 1,
                         "created_at": "2026-01-01T00:00:00+00:00"})
            entries = store.read(ns_a(), "task_ephemeral", "notes",
                                 now="2026-01-02T00:00:00+00:00")
            self.assertEqual(entries, [])

    def test_contaminated_excluded(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = MemoryStore(Path(tmp))
            store.write(ns_a(), "task_ephemeral", "notes",
                        {"id": "bad", "text": "x", "ttl_seconds": 3600})
            store.mark_contaminated(ns_a(), "task_ephemeral", "notes", "bad")
            self.assertEqual(store.read(ns_a(), "task_ephemeral", "notes"), [])

    def test_promotion_requires_evidence(self) -> None:
        gate = PromotionGate()
        ok, reason = gate.can_promote({"id": "x"})
        self.assertFalse(ok)
        self.assertEqual(reason, "memory_promotion_requires_evidence")

    def test_promotion_requires_approval_when_never(self) -> None:
        gate = PromotionGate(approval_policy="never")
        ok, reason = gate.can_promote({"id": "x", "evidence_hash": "abc"})
        self.assertFalse(ok)
        self.assertEqual(reason, "memory_promotion_requires_approval")

    def test_promotion_blocked_contaminated(self) -> None:
        gate = PromotionGate()
        ok, reason = gate.can_promote({"id": "x", "evidence_hash": "abc", "contaminated": True})
        self.assertFalse(ok)

    def test_promotion_approved_with_evidence(self) -> None:
        gate = PromotionGate()
        ok, _ = gate.can_promote({"id": "x", "evidence_hash": "abc"})
        self.assertTrue(ok)

    def test_isolation_key_includes_provider_binding(self) -> None:
        a = ns_a()
        b = Namespace("u1", "i1", "project-a", "c1", task_id="t1", provider_binding="deepseek")
        self.assertNotEqual(a.isolation_key(), b.isolation_key())


if __name__ == "__main__":
    unittest.main()
