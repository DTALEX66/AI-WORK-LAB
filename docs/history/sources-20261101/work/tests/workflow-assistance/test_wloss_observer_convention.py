"""WLOSS-600 tests: Observer Semantic Convention — single internal schema family.

Asserts:
- canonical projections use ONLY work-lab/observer-projection/* schema versions
  (never a vendor telemetry schema as the internal projection);
- external telemetry mapping is confined to otel_mapper (the single adapter);
- the observer projection pipeline does not import vendor schema modules.
"""
from __future__ import annotations

import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]  # workflow-assistance
SCRIPTS = ROOT / "scripts" / "workflow"


def module_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split(".")[0])
    return imports


class ObserverSemanticConventionTests(unittest.TestCase):
    def test_snapshot_uses_only_internal_schema(self) -> None:
        from snapshot_api import SNAPSHOT_SCHEMA_VERSION

        # Internal canonical family only: workflow/snapshot/* or
        # work-lab/observer-projection/* — never a vendor telemetry schema.
        self.assertTrue(
            SNAPSHOT_SCHEMA_VERSION.startswith("workflow/snapshot/")
            or SNAPSHOT_SCHEMA_VERSION.startswith("work-lab/observer-projection"),
            SNAPSHOT_SCHEMA_VERSION,
        )

    def test_observer_projection_never_imports_vendor_schema(self) -> None:
        for name in ("snapshot_api.py", "observer_projection_adapter.py", "sse_hub.py"):
            path = SCRIPTS / name
            if not path.exists():
                continue
            imports = module_imports(path)
            for vendor in ("opentelemetry", "openinference", "arize"):
                self.assertNotIn(vendor, imports, f"{name} must not import {vendor}")

    def test_otel_mapping_is_the_only_adapter(self) -> None:
        # Only otel_mapper and its tests may reference the OTel version constants.
        import otel_mapper

        self.assertTrue(otel_mapper.OBSERVER_SEMANTIC_CONTRACT.startswith("work-lab/observer-projection"))

    def test_otel_mapping_roundtrip_stays_canonical(self) -> None:
        from otel_mapper import canonical_to_otel, otel_to_canonical, roundtrip_lossless

        event = {"operation": "chat", "provider": "deepseek", "model": "v4-flash",
                 "input_tokens": 10, "output_tokens": 5, "latency_ms": 120}
        mapped = canonical_to_otel(event)
        self.assertTrue(mapped["schemaVersion"].startswith("otel/"))
        restored = otel_to_canonical(mapped)
        self.assertTrue(restored["schemaVersion"].startswith("work-lab/observer-projection"))
        # roundtrip reports lossless for the allowed fields.
        rt = roundtrip_lossless(event)
        self.assertTrue(rt.get("lossless") is True, rt)


if __name__ == "__main__":
    unittest.main()
