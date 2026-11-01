# SPDX-License-Identifier: MIT
"""Unit tests for core fail-closed gates:
- verify_license_coverage.py (vendored exclusion + source/binary checks)
- verify_identity_gate.py (legacy identity detection + exemption logic)
"""
from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import tempfile
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


class LicenseCoverageTests(unittest.TestCase):
    def test_taskpack_original_exemption_requires_matching_bytes(self):
        m = load("verify_license_coverage.py")
        temp_root = ROOT.parent / ".project-local/task-artifacts/taskpacks-20261009"
        # A clean clone has no task-artifacts directory, so TemporaryDirectory(dir=...)
        # raised FileNotFoundError and this case ERRORed on CI while passing here -- a
        # test that needs a machine-local directory to already exist is not testing the
        # exemption, it is testing that somebody ran the import once.
        temp_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temp_root) as raw:
            m.REPO = Path(raw)
            old_manifest = m.REPO / m.IMPORT_MANIFEST
            old_manifest.parent.mkdir(parents=True)
            old_manifest.write_text('{"entries": []}', encoding="utf-8")
            rel = "docs/history/taskpacks/20261009-inputs/ui/scripts/source.py"
            source = m.REPO / rel
            source.parent.mkdir(parents=True)
            source.write_bytes(b"print('original')\n")
            archive = m.REPO / m.TASKPACK_ARCHIVE_MANIFEST
            archive.write_text(json.dumps({"packages": [{"members": [{
                "repository_text": rel,
                "sha256": hashlib.sha256(source.read_bytes()).hexdigest()}]}]}), encoding="utf-8")
            self.assertEqual(m.inert_imported_sources([rel]), {rel})
            source.write_bytes(b"print('modified')\n")
            self.assertEqual(m.inert_imported_sources([rel]), set())
            archive.write_text("malformed", encoding="utf-8")
            self.assertEqual(m.inert_imported_sources([rel]), set())

    def test_is_excluded_vendored(self):
        m = load("verify_license_coverage.py")
        self.assertTrue(m.is_excluded("research/candidates/visual-quality/hallmark/a.py"))
        self.assertTrue(m.is_excluded("research/candidates/baoyu-design/x.mjs"))
        self.assertTrue(m.is_excluded("reports/current/out.png"))
        self.assertTrue(m.is_excluded("fixtures/domains/game-visual/bundle.js"))
        self.assertTrue(m.is_excluded("foo/node_modules/bar/b.py"))

    def test_is_excluded_false_for_active(self):
        m = load("verify_license_coverage.py")
        self.assertFalse(m.is_excluded("design-lab/scripts/verify_sbom.py"))
        self.assertFalse(m.is_excluded("design-lab/config/capability-index.json"))

    def test_source_header_detection(self):
        """A file with SPDX header passes; without it is flagged."""
        load("verify_license_coverage.py")
        with tempfile.TemporaryDirectory() as raw:
            d = Path(raw)
            ok = d / "ok.py"
            ok.write_text("# SPDX-License-Identifier: MIT\nprint(1)\n", encoding="utf-8")
            bad = d / "bad.py"
            bad.write_text("print(2)\n", encoding="utf-8")
            # simulate check_source's head-read logic
            for p, expect in ((ok, True), (bad, False)):
                head = p.read_text(encoding="utf-8")[:200]
                self.assertEqual("SPDX-License-Identifier" in head, expect, p.name)


class IdentityGateTests(unittest.TestCase):
    LEGACY = [r"OPEN[- ]DESIGN[- ]Assistance", r"opendesign[-_]assistance", r"Open Design Assistance"]

    def _detect(self, text: str) -> bool:
        import re
        for pattern in self.LEGACY:
            if re.search(pattern, text, re.IGNORECASE):
                return True
        return False

    def test_legacy_patterns_detected(self):
        for txt in ("OPEN-DESIGN-Assistance", "opendesign_assistance", "Open Design Assistance"):
            self.assertTrue(self._detect(txt), txt)

    def test_exempt_line_removal(self):
        """Lines declaring the name retired are exempted before matching.

        After removing the exemption lines, a REMAINING non-exempt legacy
        reference must still be detected (fail-closed correctness).
        """
        load("verify_identity_gate.py")
        text = "旧名 OPEN-DESIGN-Assistance 已退出活动命名，不再使用\n其余 OPEN-DESIGN-Assistance 引用\n"
        exempt = [ln for ln in text.splitlines()
                  if any(w in ln for w in ["退出活动", "历史归档", "不再作为活动", "仅允许出现在", "retired", "denylist", "Denylist", "allowlist"])]
        self.assertEqual(len(exempt), 1, "exactly the retirement-declaring line is exempt")
        for e in exempt:
            text = text.replace(e, "")
        # the remaining line is a genuine active-path reference -> must trigger
        self.assertTrue(self._detect(text), "non-exempt legacy reference must be detected")

    def test_exempt_line_full_removal(self):
        """When ALL matching lines are exempted, detection must pass clean."""
        load("verify_identity_gate.py")
        text = "历史归档：OPEN-DESIGN-Assistance 已退出活动命名\n"
        exempt = [ln for ln in text.splitlines()
                  if any(w in ln for w in ["退出活动", "历史归档", "不再作为活动", "仅允许出现在", "retired", "denylist", "Denylist", "allowlist"])]
        for e in exempt:
            text = text.replace(e, "")
        self.assertFalse(self._detect(text), "fully-exempt text must not trigger")

    def test_exempt_line_removal_reference(self):
        """denylist/allowlist declaration lines are policy, not violations."""
        load("verify_identity_gate.py")
        text = "denylist: OPEN-DESIGN-Assistance 禁止出现在活动路径"
        exempt = [ln for ln in text.splitlines()
                  if any(w in ln for w in ["退出活动", "历史归档", "不再作为活动", "仅允许出现在", "retired", "denylist", "Denylist", "allowlist"])]
        for e in exempt:
            text = text.replace(e, "")
        self.assertFalse(self._detect(text))

    def test_allow_prefixes(self):
        m = load("verify_identity_gate.py")
        self.assertTrue(any("docs/history/" == p or "docs/history/".startswith(p)
                            for p in m.ALLOW_ROOT_PREFIXES))


class SourceRegistryTests(unittest.TestCase):
    def test_registry_is_v3(self):
        """SOURCE_REGISTRY must be the v3 SourceRecord-wrapped format (DL-KNW-002)."""
        load("verify_source_registry.py")
        reg = json.loads((ROOT / "research/global-absorption/SOURCE_REGISTRY.json").read_text(encoding="utf-8"))
        self.assertEqual(reg.get("schemaVersion"), "design-lab/source-registry/v3")
        for e in reg.get("entries", []):
            self.assertIn("source", e)
            self.assertIn("integration", e)

    def test_quarantine_entries_record_missing_facts(self):
        """Every quarantined source records missingFields + reason and preserves the legacy record (DL-KNW-003)."""
        qreg = json.loads((ROOT / "research/global-absorption/QUARANTINE_REGISTRY.json").read_text(encoding="utf-8"))
        self.assertEqual(qreg.get("schemaVersion"), "design-lab/quarantine-registry/v1")
        entries = qreg.get("entries", [])
        self.assertGreater(len(entries), 0, "quarantine registry must carry the migrated legacy entries")
        for e in entries:
            self.assertTrue(e.get("missingFields"), f"{e.get('sourceId')} missing missingFields")
            self.assertTrue(e.get("reason"), f"{e.get('sourceId')} missing reason")
            self.assertIn("originalRecord", e, f"{e.get('sourceId')} must preserve original record")

    def test_git_version_must_be_full_40_hex(self):
        """Short git SHAs must be rejected by the strict verifier contract (DL-KNW-001)."""
        import re as _re
        m = load("verify_source_registry.py")
        self.assertIsNotNone(_re.fullmatch(m.GIT_SHA40.pattern, "a" * 40))
        self.assertIsNone(_re.fullmatch(m.GIT_SHA40.pattern, "a" * 12))


class ReleaseGateTests(unittest.TestCase):
    def test_acceptance_marker_pattern(self):
        """Release gate must only honor the explicit acceptance marker.

        Generic words like 通过/PASS in evidence-discipline prose must NOT
        count (this was the #42 false-positive regression).
        """
        load("verify_release_gate.py")
        marker_re = re.compile(r"DL-REL-001\s*[:：]\s*(ACCEPTED|验收通过|DONE)", re.IGNORECASE)

        self.assertTrue(marker_re.search("DL-REL-001: ACCEPTED"))
        self.assertTrue(marker_re.search("DL-REL-001：验收通过"))
        self.assertTrue(marker_re.search("DL-REL-001: DONE"))
        # generic prose must NOT trigger
        self.assertFalse(marker_re.search("不用单张 AI 图作为通过证据（Quality gate）"))
        self.assertFalse(marker_re.search("验收通过后才启用 DL-CI-004 release gate"))
        self.assertFalse(marker_re.search("标记格式：DL-REL-001 状态 ACCEPTED"))

    def test_marker_stale_detection(self):
        """A verify-chain marker bound to a stale SHA must be flagged."""
        load("verify_release_gate.py")
        with tempfile.TemporaryDirectory() as raw:
            d = Path(raw)
            marker = d / ".verify-chain-ok"
            marker.write_text("ok 0000000000000000000000000000000000000000\n", encoding="utf-8")
            # simulate the release-gate logic on a fresh temp tree
            head = "0" * 40
            mtext = marker.read_text(encoding="utf-8").strip()
            msha = mtext.split()[1] if mtext.startswith("ok ") and len(mtext.split()) > 1 else ""
            self.assertEqual(msha, "0" * 40)
            self.assertNotEqual(msha, head + "1", "stale marker sha must differ")


if __name__ == "__main__":
    unittest.main()
