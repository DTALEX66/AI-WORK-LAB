from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/verify_source_ledger.py"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_source_ledger", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SourceLedgerTests(unittest.TestCase):
    def test_reviewed_commit_accepts_unchanged_scoped_tree(self) -> None:
        module = load_module()
        head = module._git_head(ROOT)
        self.assertTrue(
            module._reviewed_scope_is_unchanged(
                ROOT,
                head,
                ["packages/client-neutral-core", "packages/client-neutral-core/tests"],
            )
        )

    def test_schema_id_is_absolute_for_offline_validation(self) -> None:
        schema = json.loads(
            (ROOT / ".project/governance/contracts/source-ledger.schema.json").read_text(encoding="utf-8")
        )
        self.assertTrue(schema["$id"].startswith("https://"))

    def test_real_ledger_is_scope_limited_and_readback_passes(self) -> None:
        result = load_module().verify(ROOT)
        # WLOSS-000 expanded the ledger to a 17-entry intake ledger (v4).
        self.assertGreaterEqual(result["entries"], 17)
        statuses = {item["id"]: item["effective"] for item in result["statuses"]}
        # A rebase/merge shifts reviewed scope SHAs; the freshness guard must
        # not fail on STALE_REVIEW (which simply means "re-review required").
        self.assertIn(statuses["work-lab-workflow-module"], {"local-verified", "STALE_REVIEW"})
        self.assertIn(statuses["work-lab-observer-module"], {"local-verified", "STALE_REVIEW"})
        self.assertNotIn("open-design", " ".join(item["id"] for item in result["statuses"]))

    def test_missing_target_degrades_local_status(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / ".project/governance/contracts").mkdir(parents=True)
            (root / "scripts/ci").mkdir(parents=True)
            ledger = json.loads((ROOT / ".project/governance/source-ledger.json").read_text(encoding="utf-8"))
            schema = json.loads((ROOT / ".project/governance/contracts/source-ledger.schema.json").read_text(encoding="utf-8"))
            (root / ".project/governance/source-ledger.json").write_text(json.dumps(ledger), encoding="utf-8")
            (root / ".project/governance/contracts/source-ledger.schema.json").write_text(json.dumps(schema), encoding="utf-8")
            with self.assertRaises(ValueError):
                module.verify(root)


if __name__ == "__main__":
    unittest.main()
