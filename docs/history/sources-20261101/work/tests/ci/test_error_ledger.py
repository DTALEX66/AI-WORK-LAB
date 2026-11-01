from __future__ import annotations

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts/ci/verify_error_ledger.py"
LEDGER = ROOT / "taskpacks/current/error-ledger.json"


def load_module():
    spec = importlib.util.spec_from_file_location("verify_error_ledger", SCRIPT)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ErrorLedgerTests(unittest.TestCase):
    def test_canonical_ledger_passes(self) -> None:
        module = load_module()
        self.assertEqual(module.main(), 0)

    def test_tampered_summary_fails_closed(self) -> None:
        module = load_module()
        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            (root / ".git").mkdir()
            (root / "services").mkdir()
            target = root / module.LEDGER_REL
            target.parent.mkdir(parents=True)
            data = json.loads(LEDGER.read_text(encoding="utf-8"))
            data["summary"]["total"] += 1
            target.write_text(json.dumps(data), encoding="utf-8")
            module.repo_root = lambda: root
            self.assertEqual(module.main(), 1)

    def test_sensitive_like_values_are_rejected_by_contract(self) -> None:
        data = json.loads(LEDGER.read_text(encoding="utf-8"))
        joined = json.dumps(data, ensure_ascii=False)
        self.assertNotRegex(joined, r"(?:api[_-]?key|password|authorization)\s*[:=]")
        self.assertNotIn("prompt_response_bodies_included\": true", joined)


if __name__ == "__main__":
    unittest.main()
