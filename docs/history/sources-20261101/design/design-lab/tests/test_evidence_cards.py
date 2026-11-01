# SPDX-License-Identifier: MIT
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "verify_evidence_cards.py"
REGISTRY = ROOT / "evals" / "evidence" / "evidence-cards.json"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_evidence_cards", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class EvidenceCardTests(unittest.TestCase):
    def test_all_benchmarks_have_non_authoritative_cards(self):
        module = load_module()
        errors = module.verify(REGISTRY)
        self.assertEqual(errors, [])
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(len(data["cards"]), 12)
        self.assertTrue(all(card["card_status"] == "not-run" for card in data["cards"]))

    def test_accepted_card_requires_completed_human_calibration(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        data["cards"][0]["card_status"] = "accepted"
        data["cards"][0]["human_calibration"]["status"] = "pending"
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence-cards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = module.verify(path)
        self.assertTrue(any("human calibration" in error for error in errors))


class EvidenceAppendOnlyTests(unittest.TestCase):
    """DL-CLOUDAUDIT-B5 (R13): append-only evidence identity + supersedes chain."""

    def _base(self, card):
        # Every B5 case derives from cards[0] (the layout-hierarchy card): a
        # genesis id, a revision, an overwritten record, or an accepted card
        # that lacks the id. We slot it in place of cards[0] rather than
        # searching for the (modified) card by equality, which would only
        # match the untouched fixture object.
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        data["cards"][0] = card
        return data

    def _check(self, card, expect_any=()):
        data = self._base(card)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence-cards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            return load_module().verify(path)

    def test_identity_is_stable_under_revision(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        card0 = data["cards"][0]
        genesis = dict(card0)
        genesis["evidence_id"] = module.content_identity(genesis)
        revision = deepcopy(genesis)
        revision["card_status"] = "isolated"
        revision["supersedes"] = genesis["evidence_id"]
        revision["evidence_id"] = module.content_identity(revision)
        self.assertEqual(genesis["evidence_id"], revision["supersedes"])
        self.assertNotEqual(genesis["evidence_id"], revision["evidence_id"])
        self.assertEqual(module.content_identity(genesis), genesis["evidence_id"])
        self.assertEqual(module.content_identity(revision), revision["evidence_id"])

    def test_genesis_with_identity_passes(self):
        module = load_module()
        card0 = json.loads(REGISTRY.read_text(encoding="utf-8"))["cards"][0]
        genesis = dict(card0)
        genesis["evidence_id"] = module.content_identity(genesis)
        errors = self._check(genesis)
        self.assertEqual(errors, [])

    def test_linear_chain_passes(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        card0 = data["cards"][0]
        genesis = dict(card0)
        genesis["evidence_id"] = module.content_identity(genesis)
        revision = deepcopy(genesis)
        revision["card_status"] = "isolated"
        revision["supersedes"] = genesis["evidence_id"]
        revision["evidence_id"] = module.content_identity(revision)
        data["cards"][0] = genesis
        data["cards"].append(revision)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence-cards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = module.verify(path)
        self.assertEqual(errors, [])

    def test_in_place_overwrite_fails(self):
        module = load_module()
        card0 = json.loads(REGISTRY.read_text(encoding="utf-8"))["cards"][0]
        genesis = dict(card0)
        genesis["evidence_id"] = module.content_identity(genesis)
        overwritten = deepcopy(genesis)
        overwritten["evidence_level"] = "E2"
        errors = self._check(overwritten, expect_any=("does not match",))
        self.assertTrue(any("does not match content identity" in error for error in errors))

    def test_accepted_card_requires_evidence_id(self):
        module = load_module()
        card0 = json.loads(REGISTRY.read_text(encoding="utf-8"))["cards"][0]
        card = dict(card0)
        card["card_status"] = "accepted"
        card["human_calibration"]["status"] = "completed"
        card["hard_gates"] = [{"id": "no-signature-copy", "status": "pass"}]
        errors = self._check(card, expect_any=("accepted card requires evidence_id",))
        self.assertTrue(any("accepted card requires evidence_id" in error for error in errors))

    def test_revision_requires_evidence_id(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        card0 = data["cards"][0]
        genesis = dict(card0)
        genesis["evidence_id"] = module.content_identity(genesis)
        revision = deepcopy(genesis)
        revision["supersedes"] = genesis["evidence_id"]
        revision.pop("evidence_id", None)
        data["cards"][0] = genesis
        data["cards"].append(revision)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence-cards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = module.verify(path)
        self.assertTrue(any("revision requires evidence_id" in error for error in errors))

    def test_dangling_supersedes_fails(self):
        module = load_module()
        card0 = json.loads(REGISTRY.read_text(encoding="utf-8"))["cards"][0]
        genesis = dict(card0)
        genesis["evidence_id"] = module.content_identity(genesis)
        revision = deepcopy(genesis)
        revision["supersedes"] = "sha256:" + "0" * 64
        revision["evidence_id"] = module.content_identity(revision)
        errors = self._check(revision, expect_any=("dangling",))
        self.assertTrue(any("dangling" in error for error in errors))

    def test_fork_fails(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        card0 = data["cards"][0]
        genesis = dict(card0)
        genesis["evidence_id"] = module.content_identity(genesis)
        data["cards"][0] = genesis
        fork_a = deepcopy(genesis)
        fork_a["card_status"] = "isolated"
        fork_a["supersedes"] = genesis["evidence_id"]
        fork_a["evidence_id"] = module.content_identity(fork_a)
        fork_b = deepcopy(genesis)
        fork_b["card_status"] = "human-review"
        fork_b["supersedes"] = genesis["evidence_id"]
        fork_b["evidence_id"] = module.content_identity(fork_b)
        data["cards"].append(fork_a)
        data["cards"].append(fork_b)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence-cards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = module.verify(path)
        self.assertTrue(any("two records supersede" in error for error in errors))

    def test_cycle_fails(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        card0 = data["cards"][0]
        a = dict(card0)
        a["evidence_id"] = module.content_identity(a)
        b = deepcopy(a)
        b["card_status"] = "isolated"
        b["supersedes"] = a["evidence_id"]
        b["evidence_id"] = module.content_identity(b)
        a["supersedes"] = b["evidence_id"]
        a["evidence_id"] = module.content_identity(a)
        data["cards"][0] = a
        data["cards"].append(b)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence-cards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = module.verify(path)
        self.assertTrue(any("exactly one genesis" in error for error in errors))

    def test_silent_duplicate_card_id_still_fails(self):
        module = load_module()
        data = json.loads(REGISTRY.read_text(encoding="utf-8"))
        duplicate = deepcopy(data["cards"][0])
        data["cards"].append(duplicate)
        with tempfile.TemporaryDirectory() as raw:
            path = Path(raw) / "evidence-cards.json"
            path.write_text(json.dumps(data), encoding="utf-8")
            errors = module.verify(path)
        self.assertTrue(any("genesis" in error for error in errors))


if __name__ == "__main__":
    unittest.main()
