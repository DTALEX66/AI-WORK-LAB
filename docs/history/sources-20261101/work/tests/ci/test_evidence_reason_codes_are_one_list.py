"""Gate: the evidence-range reason codes are ONE list, not two that happen to agree today.

The client mirrors the reader's verdict vocabulary in `apps/observer/frontend/src/lib/evidenceRange.ts`
(`EVIDENCE_BACKEND_REASON_CODES`) and labels anything outside it 未登记的判定码. Nothing pinned the two
lists to each other, so a code the reader stops producing stays on screen forever, and a code the reader
starts producing is silently "unregistered" — the exact shape that let `DIGEST_UNAVAILABLE` outlive the
parameter that created it (ERR-284: the false-pass fix removed that code from the reader, and only this
gate would have said so).

Both lists are PARSED from the tracked bytes, never retyped here: a guard that carries its own copy of the
population is a second truth about it.
"""
from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READER = ROOT / "packages" / "client-neutral-core" / "scripts" / "evidence_range_reader.py"
SIDECAR = ROOT / "services" / "orchestration" / "sidecar.py"
CLIENT = ROOT / "apps" / "observer" / "frontend" / "src" / "lib" / "evidenceRange.ts"

# Codes written inline in a return statement rather than through REFUSALS.
INLINE_IN_READER = ("READ_OK", "LIMIT_NON_POSITIVE", "OFFSET_NEGATIVE", "OFFSET_PAST_END")


def reader_refusal_codes(text: str) -> set[str]:
    """The keys of the module-level REFUSALS dict."""
    block = re.search(r"^REFUSALS = \{(.*?)^\}", text, re.S | re.M)
    if block is None:
        raise AssertionError("the reader no longer declares a REFUSALS dict — this gate is stale, not green")
    return set(re.findall(r"^\s{4}\"([A-Z0-9_]+)\":", block.group(1), re.M))


def reader_emitted_codes(text: str) -> set[str]:
    """Everything the reader can put in `reason_code`: refusals plus the inline out-of-range answers."""
    return reader_refusal_codes(text) | {
        code for code in INLINE_IN_READER if f'"reason_code": "{code}"' in text
    }


def route_codes(text: str) -> set[str]:
    """The codes the sidecar route itself answers with, before the reader is ever called."""
    return set(re.findall(r'"reason_code": "([A-Z0-9_]+)"', text))


def client_registered_codes(text: str) -> set[str]:
    block = re.search(r"export const EVIDENCE_BACKEND_REASON_CODES = \[(.*?)\] as const", text, re.S)
    if block is None:
        raise AssertionError("the client no longer declares EVIDENCE_BACKEND_REASON_CODES — gate is stale")
    return set(re.findall(r"'([A-Z0-9_]+)'", block.group(1)))


def verdict(backend: set[str], client: set[str]) -> dict[str, list[str]]:
    """The whole assertion as a pure function so the falsifiers below can feed it planted shapes."""
    return {
        "unregistered_in_client": sorted(backend - client),
        "client_names_a_code_the_backend_cannot_emit": sorted(client - backend - {"READ_OK"}),
    }


class EvidenceReasonCodeDriftTests(unittest.TestCase):
    def setUp(self) -> None:
        self.reader = READER.read_text(encoding="utf-8")
        self.sidecar = SIDECAR.read_text(encoding="utf-8")
        self.client = CLIENT.read_text(encoding="utf-8")

    def test_the_shipped_lists_agree(self) -> None:
        backend = reader_emitted_codes(self.reader) | route_codes(self.sidecar)
        report = verdict(backend, client_registered_codes(self.client))
        self.assertEqual([], report["unregistered_in_client"],
                         "the reader or the route emits a code the client would label 未登记的判定码")
        self.assertEqual([], report["client_names_a_code_the_backend_cannot_emit"],
                         "the client registers a code nothing emits — a verdict that can never arrive")

    def test_the_false_pass_code_stays_retired(self) -> None:
        """DIGEST_UNAVAILABLE existed only because the caller supplied both sides of the comparison.

        Removing it is the point of ERR-284; this case is what stops it being re-added by a future
        "let the caller tell us the actual digest" change.
        """
        for name, text in (("reader", self.reader), ("client", self.client)):
            self.assertNotIn("DIGEST_UNAVAILABLE", text, f"{name} still names the retired code")
        self.assertIn("IDENTITY_TOO_LARGE_TO_MEASURE", self.reader)
        self.assertIn("IDENTITY_TOO_LARGE_TO_MEASURE", self.client)

    def test_a_code_only_the_backend_emits_is_convicted(self) -> None:
        report = verdict({"READ_OK", "NEW_FAULT"}, {"READ_OK"})
        self.assertEqual(["NEW_FAULT"], report["unregistered_in_client"])

    def test_a_code_only_the_client_registers_is_convicted(self) -> None:
        report = verdict({"READ_OK"}, {"READ_OK", "DEAD_CODE"})
        self.assertEqual(["DEAD_CODE"], report["client_names_a_code_the_backend_cannot_emit"])

    def test_an_unparsable_population_fails_instead_of_passing_empty(self) -> None:
        for text, fn in (('REFUSALS = ()\n', reader_refusal_codes),
                         ("const x = 1\n", lambda t: client_registered_codes(t))):
            with self.subTest(surface=fn.__name__):
                with self.assertRaises(AssertionError):
                    fn(text)

    def test_the_route_answered_codes_are_all_registered(self) -> None:
        emitted = route_codes(self.sidecar)
        self.assertTrue(emitted, "the sidecar route emits no typed reason code at all — the parse broke")
        self.assertEqual([], sorted(emitted - client_registered_codes(self.client)))


if __name__ == "__main__":
    unittest.main()
