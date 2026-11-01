"""A4: unknown usage must stay NULL, never a real-looking 0.

A cache-only probe ({cache_read_tokens: 5000}, input/output absent) used to be
written as total_tokens=0 labelled EXACT_SOURCE; SUM(total_tokens) in the
canonical projection and snapshot_api._sum then surfaced that 0 to the UI as a
number. The store must sum only what is known while a genuine {0, 0} sample
stays representable as 0.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import project_temp  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from snapshot_api import _token_summary  # noqa: E402


def _store() -> CanonicalStore:
    path = project_temp.fixture_dir(prefix="usage-unknown-") / "canonical.sqlite"
    store = CanonicalStore(path)
    store.register_project("work-lab", "<redacted>")
    return store


class UsageUnknownIsNotZeroTest(unittest.TestCase):
    def test_cache_only_sample_stores_null_total(self) -> None:
        store = _store()
        try:
            store.record_usage_sample(
                {
                    "sample_id": "s-cache-only",
                    "project_id": "work-lab",
                    "provider": "deepseek",
                    "model": "m1",
                    "cache_read_tokens": 5000,
                }
            )
            row = next(
                r for r in store.list_usage_samples() if r["sample_id"] == "s-cache-only"
            )
            self.assertIsNone(row["total_tokens"])
            self.assertEqual(row["cache_read_tokens"], 5000)
        finally:
            store.close()

    def test_real_zero_sample_stays_zero(self) -> None:
        store = _store()
        try:
            store.record_usage_sample(
                {
                    "sample_id": "s-zero",
                    "project_id": "work-lab",
                    "provider": "deepseek",
                    "model": "m1",
                    "input_tokens": 0,
                    "output_tokens": 0,
                }
            )
            row = next(
                r for r in store.list_usage_samples() if r["sample_id"] == "s-zero"
            )
            # 0 is a measured fact and must remain distinct from unknown NULL.
            self.assertEqual(row["total_tokens"], 0)
        finally:
            store.close()

    def test_partial_unknown_sums_known_addends_only(self) -> None:
        store = _store()
        try:
            store.record_usage_sample(
                {
                    "sample_id": "s-partial",
                    "project_id": "work-lab",
                    "provider": "deepseek",
                    "model": "m1",
                    "input_tokens": 120,
                    "output_tokens": None,
                }
            )
            row = next(
                r for r in store.list_usage_samples() if r["sample_id"] == "s-partial"
            )
            self.assertEqual(row["total_tokens"], 120)
        finally:
            store.close()

    def test_all_unknown_summary_is_none_not_zero(self) -> None:
        store = _store()
        try:
            store.record_usage_sample(
                {
                    "sample_id": "s-a",
                    "project_id": "work-lab",
                    "provider": "deepseek",
                    "model": "m1",
                    "cache_read_tokens": 5000,
                }
            )
            store.record_usage_sample(
                {
                    "sample_id": "s-b",
                    "project_id": "work-lab",
                    "provider": "deepseek",
                    "model": "m1",
                    "reasoning_tokens": 800,
                }
            )
            # SUM over an all-NULL group is NULL in SQLite; the projection
            # must carry that NULL through instead of coercing it to 0.
            group = next(
                u
                for u in store.projection()["usage_summary"]
                if u["provider"] == "deepseek" and u["model"] == "m1"
            )
            self.assertIsNone(group["tokens"])
            # snapshot_api._sum filters non-int values, so the tokenSummary
            # path reports UNKNOWN (None), not a reported 0.
            usage = [
                {
                    "inputTokens": None,
                    "outputTokens": None,
                    "totalTokens": None,
                    "costQuality": "UNKNOWN",
                }
            ]
            self.assertIsNone(_token_summary(usage)["totalTokens"])
        finally:
            store.close()


class AggregateCoverageTest(unittest.TestCase):
    """The same defect one level up: `SUM` ignores NULLs, so a partial sum arrived as a bare number.

    Three samples for one provider/model, only one of them knowing its token count, used to project as
    `tokens: 150` with nothing on the row to say it covered a third of the samples. The aggregate now
    carries how many rows contributed and classifies that with the collector's existing coverage words.
    """

    def _group(self, provider: str, model: str) -> dict:
        store = _store()
        try:
            store.record_usage_sample({"sample_id": f"{model}-known", "project_id": "work-lab",
                                       "provider": provider, "model": model,
                                       "input_tokens": 120, "output_tokens": 30})
            store.record_usage_sample({"sample_id": f"{model}-c1", "project_id": "work-lab",
                                       "provider": provider, "model": model, "cache_read_tokens": 5000})
            store.record_usage_sample({"sample_id": f"{model}-c2", "project_id": "work-lab",
                                       "provider": provider, "model": model, "reasoning_tokens": 800})
            return next(u for u in store.projection()["usage_summary"]
                        if u["provider"] == provider and u["model"] == model)
        finally:
            store.close()

    def test_a_partial_group_says_which_denominator_it_covers(self) -> None:
        group = self._group("deepseek", "m-partial")
        self.assertEqual(3, group["samples"])
        self.assertEqual(1, group["samples_with_tokens"],
                         "the projection cannot say how many samples actually carried a token count")
        self.assertEqual(150, group["tokens"])
        self.assertEqual("PARTIAL", group["token_coverage"])

    def test_all_unknown_group_stays_null_and_is_named_none(self) -> None:
        store = _store()
        try:
            store.record_usage_sample({"sample_id": "n1", "project_id": "work-lab",
                                       "provider": "hermes", "model": "m-none", "cache_read_tokens": 10})
            store.record_usage_sample({"sample_id": "n2", "project_id": "work-lab",
                                       "provider": "hermes", "model": "m-none", "reasoning_tokens": 20})
            group = next(u for u in store.projection()["usage_summary"]
                         if u["provider"] == "hermes" and u["model"] == "m-none")
            self.assertIsNone(group["tokens"])
            self.assertEqual(0, group["samples_with_tokens"])
            self.assertEqual("NONE", group["token_coverage"])
        finally:
            store.close()

    def test_a_group_where_every_sample_is_known_is_full(self) -> None:
        store = _store()
        try:
            store.record_usage_sample({"sample_id": "f1", "project_id": "work-lab",
                                       "provider": "codex", "model": "m-full",
                                       "input_tokens": 10, "output_tokens": 5})
            store.record_usage_sample({"sample_id": "f2", "project_id": "work-lab",
                                       "provider": "codex", "model": "m-full", "total_tokens": 0})
            group = next(u for u in store.projection()["usage_summary"]
                         if u["provider"] == "codex" and u["model"] == "m-full")
            self.assertEqual(2, group["samples_with_tokens"])
            self.assertEqual(15, group["tokens"])
            self.assertEqual("FULL", group["token_coverage"],
                             "a measured zero is a known value, not a missing one")
        finally:
            store.close()


if __name__ == "__main__":
    unittest.main()
