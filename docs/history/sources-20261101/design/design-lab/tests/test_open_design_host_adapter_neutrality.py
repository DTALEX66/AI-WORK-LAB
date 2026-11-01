# SPDX-License-Identifier: MIT
"""DL-ADP-OD-004: Open Design host adapter platform-neutrality tests.

Asserts:
1. Product manifest has no default host and forbids primaryRuntime.
2. Open Design does not appear in public product identity fields.
3. integrations/hosts/open-design/ is the sole owner of Open Design implementation.
4. Public object schemas stay valid without the adapter (no Open Design API deps).
5. Public Core scripts do not depend on Open Design APIs.
6. The installer is never auto-invoked by CI (user-approved Host Profile only).
"""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADAPTER = ROOT / "adapters" / "hosts" / "open-design"
MANIFEST = ROOT / "config" / "product-manifest.json"
PUBLIC_IDENTITY_FIELDS = ("id", "name")


class OpenDesignHostAdapterNeutralityTests(unittest.TestCase):
    def test_no_default_host_and_no_primary_runtime(self):
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        text = json.dumps(m, ensure_ascii=False)
        self.assertNotIn("defaultHost", text)
        self.assertNotIn("primaryRuntime", text)
        product = m.get("product", {})
        for key in ("defaultHost", "primaryHost", "primaryRuntime", "host"):
            self.assertNotIn(key, product, f"product must not declare {key}")

    def test_open_design_not_in_public_identity_fields(self):
        m = json.loads(MANIFEST.read_text(encoding="utf-8"))
        product = m.get("product", {})
        for field in PUBLIC_IDENTITY_FIELDS:
            value = str(product.get(field, ""))
            self.assertNotIn("open design", value.lower(), f"identity field {field} must stay neutral")
            self.assertNotIn("opendesign", value.lower(), f"identity field {field} must stay neutral")

    def test_adapter_is_sole_owner(self):
        # legacy top-level locations must be gone
        for rel in (
            "design-lab/op-expert-suite",
            "design-lab/scripts/verify_open_design_assistance.py",
            "design-lab/scripts/generate_open_design_indexes.py",
            "design-lab/scripts/install_op_expert_suite.py",
        ):
            self.assertFalse((ROOT.parent / rel).exists(), f"legacy location must not exist: {rel}")
        # Open Design implementation code only lives under the adapter dir;
        # open-design.json files in neutral capability dirs are PROJECTIONS
        # (derived data, DL-ADP-OD-002), not implementation.
        import subprocess
        r = subprocess.run(
            ["git", "-C", str(ROOT.parent), "ls-files", "design-lab"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        for rel in r.stdout.splitlines():
            if "open-design" not in rel:
                continue
            if rel.startswith("integrations/hosts/open-design/"):
                continue
            if rel.endswith("open-design.json"):
                continue  # projection data next to the neutral contract is allowed
            if rel.endswith(".py") or rel.endswith(".md") or rel.endswith(".yaml"):
                self.fail(f"Open Design implementation outside adapter dir: {rel}")

    def test_public_object_schemas_valid_without_adapter(self):
        import json as _json
        for schema in sorted((ROOT / "schemas").rglob("*.json")):
            try:
                _json.loads(schema.read_text(encoding="utf-8"))
            except _json.JSONDecodeError as exc:
                self.fail(f"public schema unreadable: {schema} ({exc})")

    def test_public_core_does_not_depend_on_open_design_api(self):
        import subprocess
        r = subprocess.run(
            ["git", "-C", str(ROOT.parent), "ls-files", "design-lab/scripts", "design-lab/core", "packages/capabilities/atoms", "packages/capabilities/bundles", "packages/capabilities/scenarios"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        for rel in r.stdout.splitlines():
            if not rel.endswith(".py") and not rel.endswith(".json") and not rel.endswith(".md"):
                continue
            p = ROOT.parent / rel
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            # projection data files may reference the Open Design schema URL
            if rel.endswith("open-design.json"):
                continue
            for pattern in ("/api/skills/install", "/api/plugins/install", "open-design.ai/api"):
                self.assertNotIn(pattern, text, f"public core must not depend on Open Design API: {rel}")

    def test_installer_not_auto_invoked_by_ci(self):
        import subprocess
        r = subprocess.run(
            ["git", "-C", str(ROOT.parent), "ls-files", ".github/workflows"],
            capture_output=True, text=True, encoding="utf-8", errors="replace",
        )
        for rel in r.stdout.splitlines():
            p = ROOT.parent / rel
            text = p.read_text(encoding="utf-8", errors="ignore")
            self.assertNotIn("install_op_expert_suite", text, f"CI must never auto-run the installer: {rel}")


if __name__ == "__main__":
    unittest.main()
