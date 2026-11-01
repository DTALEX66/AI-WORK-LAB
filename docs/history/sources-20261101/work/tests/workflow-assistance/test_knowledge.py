"""Tests for the knowledge-promotion gate (WL-P1-290 / ch 37): the
last ALLOW/REJECT door into ArcheAxis, enforcing ch 44 item 19.

Repo convention: load the service file by spec, pre-register in
sys.modules under a stable name.  The gate is content-deterministic; every
test drives it with synthetic records so the forbidden-content detectors
are exercised without touching a real ArcheAxis store.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KNOW = ROOT / "services" / "knowledge"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, KNOW / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _cand(**over):
    kg = _load("promotion_gate.py", "kn_kg")
    d = dict(candidate_id="k1", category="verified_lesson",
             content="portable builds beat ad-hoc scripts; use the taskpack",
             verified=True, provenance="codex:s1")
    d.update(over)
    return kg.KnowledgeCandidate(**d)


class WhitelistTests(unittest.TestCase):
    def test_all_eight_categories_are_whitelisted(self):
        kg = _load("promotion_gate.py", "kn_kg")
        gate = kg.KnowledgePromotionGate()
        for cat in kg.KnowledgeCategory.ALLOWED:
            v = gate.promote(_cand(candidate_id=cat, category=cat))
            self.assertTrue(v.allowed, f"{cat} should be allowed")
            int(v.receipt_sha256(), 16)

    def test_off_whitelist_category_is_refused(self):
        kg = _load("promotion_gate.py", "kn_kg")
        v = kg.KnowledgePromotionGate().promote(_cand(category="random_thought"))
        self.assertFalse(v.allowed)
        self.assertTrue(any("not one of" in r for r in v.reasons))


class ForbiddenContentTests(unittest.TestCase):
    def test_unverified_candidate_is_refused(self):
        kg = _load("promotion_gate.py", "kn_kg")
        v = kg.KnowledgePromotionGate().promote(_cand(verified=False))
        self.assertFalse(v.allowed)
        self.assertIn("unverified_candidate", v.forbidden_kinds)

    def test_secret_in_content_is_refused(self):
        kg = _load("promotion_gate.py", "kn_kg")
        v = kg.KnowledgePromotionGate().promote(
            _cand(content="deploy creds: aws_access_key_id=AKIAABCDEFGHIJKLMNOP"))
        self.assertFalse(v.allowed)
        self.assertIn("secrets", v.forbidden_kinds)

    def test_raw_bash_transcript_is_refused(self):
        kg = _load("promotion_gate.py", "kn_kg")
        bash = (
            "user@host:~$ cd /tmp\n"
            "user@host:/tmp$ python build.py\n"
            "user@host:/tmp$ echo done\n"
        )
        v = kg.KnowledgePromotionGate().promote(_cand(category="stable_workflow",
                                                      content=bash))
        self.assertFalse(v.allowed)
        self.assertIn("raw_bash", v.forbidden_kinds)

    def test_a_documented_single_command_is_not_raw_bash(self):
        # a stable workflow can cite ONE command in prose without tripping
        kg = _load("promotion_gate.py", "kn_kg")
        v = kg.KnowledgePromotionGate().promote(_cand(
            category="stable_workflow",
            content="the stable step runs `python -m worklab build`; see doc"))
        self.assertTrue(v.allowed)

    def test_full_chat_dump_is_refused(self):
        kg = _load("promotion_gate.py", "kn_kg")
        chat = '[{"role":"user","content":"hi"},{"role":"assistant","content":"yo"}]'
        v = kg.KnowledgePromotionGate().promote(_cand(content=chat))
        self.assertFalse(v.allowed)
        self.assertIn("all_chat", v.forbidden_kinds)

    def test_temp_log_is_refused(self):
        kg = _load("promotion_gate.py", "kn_kg")
        log = "\n".join([
            "2026-09-13T01:00:00 INFO boot",
            "2026-09-13T01:00:01 INFO start",
            "2026-09-13T01:00:02 WARN slow",
        ])
        v = kg.KnowledgePromotionGate().promote(_cand(content=log))
        self.assertFalse(v.allowed)
        self.assertIn("temp_log", v.forbidden_kinds)


class ProvenanceTests(unittest.TestCase):
    def test_clean_content_without_provenance_is_refused(self):
        kg = _load("promotion_gate.py", "kn_kg")
        v = kg.KnowledgePromotionGate().promote(
            _cand(content="clean distilled note", provenance=""))
        self.assertFalse(v.allowed)
        self.assertTrue(any("provenance" in r for r in v.reasons))

    def test_memory_boundary_provenance_suffices(self):
        kg = _load("promotion_gate.py", "kn_kg")
        v = kg.KnowledgePromotionGate().promote(
            _cand(content="clean distilled note", provenance="",
                  from_memory_boundary=True))
        self.assertTrue(v.allowed)


class BatchTests(unittest.TestCase):
    def test_batch_receipt_is_deterministic(self):
        kg = _load("promotion_gate.py", "kn_kg")
        gate = kg.KnowledgePromotionGate()
        cands = [_cand(candidate_id="ok", category="benchmark_result"),
                 _cand(candidate_id="bad", category="verified_lesson", verified=False)]
        rep1 = gate.batch(cands)
        rep2 = gate.batch(cands)
        self.assertEqual(rep1["allowed"], ["ok"])
        self.assertEqual(rep1["rejected"], ["bad"])
        # determinism: same input -> same verdicts
        self.assertEqual([v["receipt_sha256"] for v in rep1["verdicts"]],
                         [v["receipt_sha256"] for v in rep2["verdicts"]])


if __name__ == "__main__":
    unittest.main(verbosity=2)
