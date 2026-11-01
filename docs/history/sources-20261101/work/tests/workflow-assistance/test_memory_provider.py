"""Tests for the memory plane (WL-P0-190/200/210): the unified 9-op
provider contract, the three bakeoff candidates, the session/memory/
knowledge boundary, and the memory bakeoff scoring framework.

Repo convention (mirrors test_task_governance.py): load each service file
by spec, pre-register in sys.modules under a stable name.  All tests are
environment-safe — no external memory server is installed or started; the
bare POC providers are the negative controls that prove the honesty rules
(UNAVAILABLE / [] instead of fabricated data).
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MEM = ROOT / "services" / "memory"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, MEM / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class ProviderContractTests(unittest.TestCase):
    """The base 9-op contract: honest degradation, provenance on recall."""

    def _providers(self):
        p = _load("provider.py", "mem_provider")
        hb = _load("hermes_builtin.py", "mem_hb")
        return p, hb.HermesBuiltinProvider()

    def test_builtin_is_self_hosted_and_bootstraps(self):
        p, prov = self._providers()
        self.assertTrue(prov.health()["available"])      # self-hosted: always
        rec = p.MemoryRecord(record_id="r", kind=p.MemoryKind.MEMORY,
                             content="portable builds", origin="codex:s1",
                             tags=["build"])
        self.assertEqual(prov.retain(rec).status, "OK")
        hits = prov.recall("build")
        self.assertEqual([h.record.record_id for h in hits], ["r"])
        self.assertEqual(prov.revoke("r").status, "OK")

    def test_raw_session_material_is_not_retained(self):
        # ch 25: raw session cannot be stored as memory
        p, prov = self._providers()
        raw = {"events": [{"tool": "exec", "out": "ok"}], "tools": ["exec"]}
        res = prov.retain(raw)
        self.assertFalse(res.ok)
        self.assertEqual(res.status, "RAW_SESSION")

    def test_recall_is_provenanced_and_sorted(self):
        p, prov = self._providers()
        prov.retain(p.MemoryRecord("t1", p.MemoryKind.MEMORY, "note about builds",
                                   "a", ("build",)))
        prov.retain(p.MemoryRecord("t2", p.MemoryKind.MEMORY, "build systems",
                                   "b", ("build",)))
        hits = prov.recall("build", top_k=10)
        self.assertEqual([h.record.record_id for h in hits], ["t1", "t2"])
        for h in hits:
            self.assertEqual(h.store, "hermes-builtin")
            self.assertEqual(h.matched_on, "build")

    def test_export_is_portable_when_available(self):
        p, prov = self._providers()
        prov.retain(p.MemoryRecord("x", p.MemoryKind.MEMORY, "data", "o", ("t",)))
        out = prov.export()
        self.assertTrue(out["available"])
        self.assertTrue(out["portable"])     # builtin export is self-contained
        self.assertTrue(out["offline"])
        self.assertEqual(len(out["records"]), 1)


class PocHonestyTests(unittest.TestCase):
    """The two external POC candidates must NOT fabricate data."""

    def test_hindsight_bare_is_unavailable(self):
        p = _load("provider.py", "mem_provider")
        hs = _load("hindsight_poc.py", "mem_hindsight").HindsightPoc()
        rec = p.MemoryRecord("r", p.MemoryKind.MEMORY, "c", "o", ("t",))
        self.assertFalse(hs.health()["available"])
        self.assertEqual(hs.retain(rec).status, "UNAVAILABLE")
        self.assertEqual(hs.recall("c"), [])
        # its health flags the POC surface, not a live server
        self.assertIs(hs.health()["external_server"], True)

    def test_tencent_bare_is_unavailable(self):
        p = _load("provider.py", "mem_provider")
        tc = _load("tencent_poc.py", "mem_tc").TencentMemoryPoc()
        self.assertFalse(tc.health()["available"])
        # the three clients it is meant to serve are declared in health
        self.assertIn("dsh", tc.health()["shared_by"])
        self.assertEqual(tc.recall("x"), [])


class BoundaryTests(unittest.TestCase):
    """ch 25: the two forbiddens are structurally enforced."""

    def test_memory_is_not_a_session_db(self):
        sb = _load("session_memory_boundary.py", "mem_sb")
        p = _load("provider.py", "mem_provider")
        hb = _load("hermes_builtin.py", "mem_hb").HermesBuiltinProvider()
        b = sb.SessionMemoryBoundary(hb)
        self.assertTrue(b.assert_memory_is_not_session_db())
        # and the session store has no path into memory
        self.assertTrue(b.sessions.cannot_write_memory())

    def test_raw_log_cannot_skip_straight_to_knowledge(self):
        sb = _load("session_memory_boundary.py", "mem_sb")
        hb = _load("hermes_builtin.py", "mem_hb").HermesBuiltinProvider()
        b = sb.SessionMemoryBoundary(hb)
        with self.assertRaises(sb.RawLogToKnowledgeError):
            b.promote_to_knowledge({"events": [{}]}, target="archeaxis")

    def test_unverified_memory_cannot_be_promoted(self):
        sb = _load("session_memory_boundary.py", "mem_sb")
        p = _load("provider.py", "mem_provider")
        hb = _load("hermes_builtin.py", "mem_hb").HermesBuiltinProvider()
        b = sb.SessionMemoryBoundary(hb)
        unverified = p.MemoryRecord("u", p.MemoryKind.MEMORY, "lesson", "o")
        hb.retain(unverified)
        with self.assertRaises(sb.UnverifiedPromotionError):
            b.promote_to_knowledge(unverified)

    def test_verified_memory_promotes_to_knowledge(self):
        sb = _load("session_memory_boundary.py", "mem_sb")
        p = _load("provider.py", "mem_provider")
        hb = _load("hermes_builtin.py", "mem_hb").HermesBuiltinProvider()
        b = sb.SessionMemoryBoundary(hb)
        rec = p.MemoryRecord("v", p.MemoryKind.MEMORY, "verified lesson", "o")
        rec.verified = True
        hb.retain(rec)
        promoted = b.promote_to_knowledge(rec, target="archeaxis")
        self.assertEqual(promoted.kind.value, "knowledge")
        self.assertIn("archeaxis", promoted.origin)

    def test_distill_requires_real_content(self):
        sb = _load("session_memory_boundary.py", "mem_sb")
        hb = _load("hermes_builtin.py", "mem_hb").HermesBuiltinProvider()
        b = sb.SessionMemoryBoundary(hb)
        b.record_session({"events": [{}]}, session_id="s1")
        with self.assertRaises(sb.SessionAsMemoryError):
            b.distill("s1", content="   ")   # empty distillation is refused


class BakeoffTests(unittest.TestCase):
    """ch 24: the scoring framework is deterministic and POC-honest."""

    def _bakeoff(self):
        bk = _load("bakeoff.py", "mem_bk")
        hb = _load("hermes_builtin.py", "mem_hb").HermesBuiltinProvider()
        hs = _load("hindsight_poc.py", "mem_hindsight").HindsightPoc()
        tc = _load("tencent_poc.py", "mem_tc").TencentMemoryPoc()
        p = _load("provider.py", "mem_provider")
        hb.retain(p.MemoryRecord("a", p.MemoryKind.MEMORY, "x", "o", ("t",)))
        return bk, [hb, hs, tc]

    def test_ten_axes_and_deterministic_receipt(self):
        bk, providers = self._bakeoff()
        rep = bk.bakeoff(providers)
        self.assertEqual(rep.axis_total, 10)
        self.assertEqual(rep.receipt_sha256, bk.bakeoff(providers).receipt_sha256)
        int(rep.receipt_sha256, 16)   # real sha256 hex

    def test_bare_pocs_are_unevaluated_not_zero(self):
        bk, providers = self._bakeoff()
        rep = bk.bakeoff(providers)
        # hindsight/tencent have no live backend -> every axis UNEVALUATED,
        # and the mean is None (not a fabricated 0)
        for name in ("hindsight", "tencent-memory"):
            self.assertIsNone(rep.providers[name]["score"])
            self.assertEqual(rep.providers[name]["evaluated"], 0)
            self.assertEqual(rep.providers[name]["unevaluated"], 10)

    def test_live_builtin_scores_its_evidenced_axes(self):
        bk, providers = self._bakeoff()
        rep = bk.bakeoff(providers)
        d = rep.providers["hermes-builtin"]
        self.assertTrue(d["available"])
        self.assertIsNotNone(d["score"])
        self.assertGreater(d["evaluated"], 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
