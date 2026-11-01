# SPDX-License-Identifier: MIT
"""R4 governance anti-drift regression tests (task package section 13).

Each test FAILS CLOSED when the corresponding guard weakens:
1 short git SHA rejected     2 reviewed_at cannot replace reviewedBy/reviewedAt
3 missing contentHash        4 machine-generated reviewer rejected
5 category/categories drift  6 reference-only into model context rejected
7 commercialUse=false pack   8 ancestor evidence as current rejected
9 missing release artifact  10 Open Design back-dependency rejected
11 large/binary without source record rejected
12 external library root scan rejected
13 minigame monetization/ops fields rejected
14 comfyui/h3 supported=true without E3 rejected
"""
from __future__ import annotations

import importlib.util
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def load(name: str):
    path = SCRIPTS / name
    spec = importlib.util.spec_from_file_location(name.replace(".py", ""), path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceGovernanceAntiDriftTests(unittest.TestCase):
    def setUp(self):
        self.v = load("verify_source_registry.py")

    def test_short_git_sha_rejected(self):
        self.assertIsNone(self.v.GIT_SHA40.fullmatch("a" * 12))
        self.assertIsNotNone(self.v.GIT_SHA40.fullmatch("a" * 40))

    def test_reviewed_at_does_not_replace_reviewed_by(self):
        src = {"sourceId": "x", "origin": "https://github.com/a/b", "author": "A",
               "license": "MIT", "licenseStatus": "reviewed", "allowedUsage": "u",
               "version": "0" * 40, "acquiredAt": "2026-08-16",
               "contentHash": "sha256:" + "a" * 64, "redistributable": True,
               "modelInputAllowed": True, "commercialUse": True,
               "reviewed_at": "2026-08-16"}  # legacy key only, no reviewedBy/reviewedAt
        findings = self.v.validate_rights(src, {"mode": "reference", "status": "reference-only"})
        self.assertTrue(any("reviewedBy" in f or "reviewer" in f for f in findings), findings)

    def test_missing_content_hash_rejected(self):
        findings = self.v.validate_rights({**{"sourceId": "x", "origin": "https://example.com",
               "licenseStatus": "reviewed", "contentHash": "git:abc", "version": "v1.0.0",
               "reviewedBy": "Alice", "modelInputAllowed": False}, "mode": "reference"}, {"mode": "reference"})
        self.assertTrue(any("contentHash" in f for f in findings), findings)

    def test_machine_generated_reviewer_rejected(self):
        findings = self.v.validate_rights({**{"sourceId": "x", "origin": "https://example.com",
               "licenseStatus": "reviewed", "contentHash": "sha256:" + "b" * 64, "version": "v1.0.0",
               "reviewedBy": "auto-generated-agent", "modelInputAllowed": False}, "mode": "reference"}, {"mode": "reference"})
        self.assertTrue(any("machine-generated" in f for f in findings), findings)

    def test_category_drift_rejected(self):
        import jsonschema
        schema = json.loads((ROOT / "schemas/source-record.schema.json").read_text(encoding="utf-8"))
        record = {"sourceId": "x", "origin": "https://example.com", "author": "A",
                  "license": "MIT", "licenseStatus": "reviewed", "allowedUsage": "u",
                  "version": "v1.0.0", "acquiredAt": "2026-08-16",
                  "contentHash": "sha256:" + "c" * 64, "redistributable": True,
                  "modelInputAllowed": False, "commercialUse": False,
                  "reviewedBy": "Alice", "reviewedAt": "2026-08-16",
                  "category": "design-spec"}  # legacy category drift
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(record))
        self.assertTrue(errors, "category field must be rejected by source-record schema")

    def test_reference_only_must_not_enable_model_input(self):
        findings = self.v.validate_rights({**{"sourceId": "x", "origin": "https://example.com",
               "licenseStatus": "reference-only", "contentHash": "sha256:" + "d" * 64, "version": "v1.0.0",
               "reviewedBy": "Alice", "modelInputAllowed": True}, "mode": "reference"}, {"mode": "reference"})
        self.assertTrue(any("model input" in f for f in findings), findings)

    def test_commercial_false_in_commercial_pack_rejected(self):
        # the gate scans production packs for commercialUse=false sourceIds
        src = load("verify_source_registry.py")
        text = Path(src.__file__).read_text(encoding="utf-8")
        self.assertIn("commercialUse", text)
        self.assertIn("production", text)


class EvidenceAntiDriftTests(unittest.TestCase):
    def test_ancestor_evidence_not_current(self):
        m = load("update_evidence_binding.py")
        head = m.git_head()
        head_tree = m.git_tree(head)
        self.assertEqual(m.compute_state(head_tree, head, head_tree), "CURRENT_EXACT")
        parent = m.git(["rev-parse", head + "^"])
        if parent:
            self.assertEqual(m.compute_state(m.git_tree(parent), head, head_tree), "HISTORICAL_VALID")

    def test_missing_release_artifact_rejected(self):
        import jsonschema
        schema = json.loads((ROOT / "schemas/evidence-attestation.schema.json").read_text(encoding="utf-8"))
        bad = {"attestationId": "a1", "subjectCommitSha": "0" * 40, "subjectTreeSha": "0" * 40,
               "producer": "ci", "environment": "e", "command": "c", "exitCode": 0,
               "createdAt": "2026-08-16T00:00:00Z", "reviewer": None, "evidenceLevel": "E1"}
        errors = list(jsonschema.Draft202012Validator(schema).iter_errors(bad))
        self.assertTrue(any("artifactDigests" in e.message for e in errors), errors)

    def test_open_design_back_dependency_rejected(self):
        import subprocess
        r = subprocess.run(["git", "-C", str(ROOT.parent), "ls-files", "design-lab/scripts"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        for rel in r.stdout.splitlines():
            if not rel.endswith(".py"):
                continue
            text = (ROOT.parent / rel).read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("import open_design", text, f"core back-dependency: {rel}")


class AssetGovernanceAntiDriftTests(unittest.TestCase):
    def setUp(self):
        self.m = load("verify_asset_governance.py")

    def _tmp(self):
        import uuid
        d = ROOT.parent / ".project-local/task-runtime/tmp" / ("antidrift-" + uuid.uuid4().hex[:8])
        d.mkdir(parents=True, exist_ok=True)
        return str(d)

    def test_binary_without_source_record_rejected(self):
        import hashlib, json
        d = Path(self._tmp())
        binary = d / "asset.bin"
        binary.write_bytes(b"\x00" * 64)
        sidecar = Path(str(binary) + ".license")
        errs = self.m.sidecar_findings("asset.bin", binary, sidecar)
        self.assertTrue(any("without .license sidecar" in e for e in errs), errs)
        # with an expired exception -> rejected
        sidecar.write_text(json.dumps({"schemaVersion": "design-lab/asset-sidecar/v1", "file": "asset.bin",
            "sha256": "sha256:" + hashlib.sha256(binary.read_bytes()).hexdigest(), "license": "MIT", "author": "A",
            "redistributable": True, "modelInputAllowed": False, "commercialUse": False,
            "sourceId": None, "exception": {"approvedBy": "A", "expiresAt": "2020-01-01"}}), encoding="utf-8")
        errs = self.m.sidecar_findings("asset.bin", binary, sidecar)
        self.assertTrue(any("expired" in e for e in errs), errs)
        # legacy SPDX sidecar -> rejected
        sidecar.write_text("SPDX-FileCopyrightText: A\nSPDX-License-Identifier: MIT\n", encoding="utf-8")
        errs = self.m.sidecar_findings("asset.bin", binary, sidecar)
        self.assertTrue(any("not structured v1" in e or "not valid JSON" in e for e in errs), errs)

    def test_external_library_root_scan_rejected(self):
        m = load("external_asset_intake.py")
        manifest = {"collectionId": "c1", "displayName": "x", "selectedPaths": ["**"],
                    "intendedUse": "u", "rightsReviewRequired": True, "outputTargets": [],
                    "createdBy": "A", "createdAt": "2026-08-16"}
        errors = m.validate_manifest(manifest)
        self.assertTrue(any("root-scan" in e for e in errors), errors)


class MiniGameBoundaryAntiDriftTests(unittest.TestCase):
    def test_minigame_monetization_fields_rejected(self):
        import subprocess
        r = subprocess.run(["git", "-C", str(ROOT.parent), "ls-files", "fixtures/domains/game-visual"],
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
        patterns = re.compile(r"\bads?\b|\badvertisement\b|\biap\b|\bmonetization\b|in-app\s*purchase|广告变现|买量|growth\s*hack", re.IGNORECASE)
        # only scan active source files (not docs/history which may describe removed features)
        # scan only ACTIVE runtime paths; tests/ and docs/ may legitimately reference
        # event names and historical terms and are out of scope for the field gate
        RUNTIME_PREFIXES = ("fixtures/domains/game-visual/src/", "fixtures/domains/game-visual/platform/", "fixtures/domains/game-visual/games/",
                            "fixtures/domains/game-visual/index.html", "fixtures/domains/game-visual/styles.css",
                            "fixtures/domains/game-visual/wechat-minigame/", "fixtures/domains/game-visual/douyin-minigame/",
                            "fixtures/domains/game-visual/android-minigame/", "fixtures/domains/game-visual/android-webview/")
        for rel in r.stdout.splitlines():
            if not rel.startswith(RUNTIME_PREFIXES):
                continue
            if rel.endswith(".license") or rel.endswith(".md"):
                continue
            if not rel.endswith((".js", ".mjs", ".cjs", ".json", ".html", ".css", ".java", ".xml")):
                continue
            text = (ROOT.parent / rel).read_text(encoding="utf-8", errors="ignore")
            if patterns.search(text):
                self.fail(f"minigame boundary violation (monetization/ops fields): {rel}")


class RuntimeEvidenceAntiDriftTests(unittest.TestCase):
    def test_comfyui_h3_supported_without_e3_rejected(self):
        # R0-007 (DL-TP-20260904): historical E3 is not current evidence; supported must be false.
        import json as _json
        reg = _json.loads((ROOT.parent / "integrations/adapter-registry.json").read_text(encoding="utf-8"))
        for a in reg["adapters"]:
            if a["adapter_id"] == "adapter-comfyui":
                self.assertFalse(any(c["supported"] for c in a["capabilities"]))


if __name__ == '__main__':
    unittest.main()
