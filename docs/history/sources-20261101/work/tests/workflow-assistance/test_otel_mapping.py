"""NX-300: OTel/OpenInference mapping tests.

RED-GREEN coverage:
- Canonical event round-trips losslessly on mapped fields.
- Message bodies / prompt / response / secrets are never exported (raise).
- inputTokens / outputTokens (legit token metrics) are NOT blocked.
- Unknown fields go to isolated extension zone, not dropped.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/receipts'))
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

from otel_mapper import (  # noqa: E402
    canonical_to_otel, otel_to_canonical, roundtrip_lossless,
    PrivacyBlockedError,
)


def _sample() -> dict:
    return {
        "schemaVersion": "work-lab/observer-projection/v2",
        "provider": "deepseek", "model": "deepseek-v4-flash", "operation": "chat",
        "usage": {"inputTokens": 100, "outputTokens": 50, "cacheReadTokens": 20, "cacheWriteTokens": 5},
        "latencyMs": 123, "outcome": "ok", "errorClass": None,
        "taskDigest": "abc", "sourceDigest": "def",
    }


class OtelMappingTest(unittest.TestCase):
    def test_roundtrip_lossless_on_mapped_fields(self) -> None:
        rt = roundtrip_lossless(_sample())
        self.assertTrue(rt["lossless"], str(rt))

    def test_maps_model_and_tokens(self) -> None:
        otel = canonical_to_otel(_sample())
        self.assertEqual(otel["gen_ai.request.model"], "deepseek-v4-flash")
        self.assertEqual(otel["gen_ai.usage.input_tokens"], 100)
        self.assertEqual(otel["gen_ai.provider.name"], "deepseek")

    def test_input_output_tokens_not_blocked(self) -> None:
        otel = canonical_to_otel(_sample())
        self.assertIn("gen_ai.usage.input_tokens", otel)
        self.assertIn("gen_ai.usage.output_tokens", otel)

    def test_message_body_blocked(self) -> None:
        ev = _sample()
        ev["gen_ai.input.messages"] = [{"role": "user", "content": "secret"}]
        with self.assertRaises(PrivacyBlockedError):
            canonical_to_otel(ev)

    def test_prompt_body_blocked(self) -> None:
        ev = _sample()
        ev["prompt"] = "the actual prompt"
        with self.assertRaises(PrivacyBlockedError):
            canonical_to_otel(ev)

    def test_secret_blocked(self) -> None:
        ev = _sample()
        ev["api_key"] = "sk-xxxx"
        with self.assertRaises(PrivacyBlockedError):
            canonical_to_otel(ev)

    def test_unknown_field_in_extension_zone(self) -> None:
        ev = _sample()
        ev["customMetric"] = 42
        otel = canonical_to_otel(ev)
        self.assertEqual(otel["_extensions"]["worklab.ext.customMetric"], 42)

    def test_otel_to_canonical_preserves_mapped(self) -> None:
        otel = canonical_to_otel(_sample())
        back = otel_to_canonical(otel)
        self.assertEqual(back["model"], "deepseek-v4-flash")
        self.assertEqual(back["inputTokens"], 100)


if __name__ == "__main__":
    unittest.main()
