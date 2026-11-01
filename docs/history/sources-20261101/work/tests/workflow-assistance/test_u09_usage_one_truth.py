"""U09 deliverable #3 — ONE usage/cost truth, proven behaviorally.

Task B spec (taskpack 20260918 U09): "add a one-truth conformance test + a
fabricated-cost negative test."  The convergence statement (already enforced
by scripts/ci/verify_usage_convergence.py at the SCHEMA level) must ALSO hold
at the VALUE level: the two surfaces that read usage/cost truth —

    canonical : services/receipts/model_usage_mapper.map_usage
    observer  : apps/observer/src/observer_runtime.project_usage / project_cost

— produce *identical* usage for the same fixture, and NEITHER trusts a
divergent/fabricated cost on a not-metered source.

Every assertion here is grounded in .project-local/task-runtime/u09_one_truth_probe.py
(real outputs), so this test would flip RED if either surface regressed to
fabricating cost or to a divergent token rollup.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (file lives in tests/workflow-assistance/)
# Import the two truth surfaces directly. `services/receipts` is already on the
# governance-batch PYTHONPATH; `apps/observer/src` is NOT, so insert it here to
# keep this test self-contained (no change to the shared gate PYTHONPATH).
for _p in ("services/receipts", "apps/observer/src"):
    _sp = str(ROOT / _p)
    if _sp not in sys.path:
        sys.path.insert(0, _sp)

from model_usage_mapper import map_usage, QUALITY_UNAVAILABLE  # noqa: E402
from observer_runtime import project_usage, project_cost        # noqa: E402


def _events(observations: list[dict]) -> list[dict]:
    """Build observer events from the same raw observations the canonical
    mapper consumes — the 'same fixture, two surfaces' bridge."""
    events = []
    for idx, obs in enumerate(observations):
        inp = obs.get("input_tokens") or 0
        out = obs.get("output_tokens") or 0
        events.append({
            "eventId": f"evt-{idx}",
            "sourceId": obs.get("provider"),
            "usage": {"input_tokens": inp, "output_tokens": out,
                      "total_tokens": inp + out, "records": 1},
            "telemetry": {"model": obs.get("provider")},
        })
    return events


METERED = {"provider": "deepseek", "lifecycle": "ACTIVE", "input_tokens": 100,
           "output_tokens": 50, "cache_hit_tokens": 80, "cache_miss_tokens": 20,
           "cost_cents": 0.30}
CODEX = {"provider": "codex", "input_tokens": 10, "output_tokens": 5}
LOCAL = {"provider": "local", "input_tokens": 7, "output_tokens": 3}

PRICING = {
    "deepseek": {"alias": "deepseek", "billing": "metered", "source": "catalog",
                 "effective_at": "2026-01-01", "currency": "USD", "stale": False,
                 "input_per_million": 1.0, "output_per_million": 2.0},
    "codex": {"alias": "codex", "billing": "subscription", "source": "catalog",
              "effective_at": "2026-01-01", "currency": "USD", "stale": False,
              "input_per_million": 0, "output_per_million": 0},
}


class U09OneTruthTests(unittest.TestCase):
    def test_same_fixture_identical_usage(self) -> None:
        # one-truth invariant: canonical per-observation mapping, summed over the
        # fixture, must equal the observer's aggregation of the SAME fixture.
        observations = [METERED, CODEX, LOCAL]
        canon_in = sum(map_usage(o)["input_tokens"] for o in observations)
        canon_out = sum(map_usage(o)["output_tokens"] for o in observations)
        obs = project_usage(_events(observations))
        self.assertEqual(obs["input_tokens"], canon_in)
        self.assertEqual(obs["output_tokens"], canon_out)
        # observer total is the honest sum of the same two dimensions
        self.assertEqual(obs["total_tokens"], canon_in + canon_out)

    def test_no_cost_fabrication_on_not_metered(self) -> None:
        # a not-metered source must yield NO cost on either surface (never 0,
        # never a number) — 'no cost engine' + honest-null discipline.
        for provider in ("codex", "local"):
            obs = {"provider": provider, "input_tokens": 3, "output_tokens": 1}
            mapped = map_usage(obs)
            self.assertIsNone(mapped["cost_cents"], f"{provider} fabricated cost")
            self.assertEqual(mapped["cost_quality"], QUALITY_UNAVAILABLE)
            pc = project_cost(_events([obs]), PRICING)
            self.assertIsNone(pc["estimated_cost"], f"{provider} fabricated cost")

    def test_fabricated_cost_is_refused_by_both_surfaces(self) -> None:
        # deliverable #3 NEGATIVE: inject a divergent/fabricated cost_cents onto a
        # not-metered (subscription) source. Both surfaces must REFUSE it — a
        # fabricated cost never leaks into either truth.
        fabricated = dict(CODEX, cost_cents=9999.0)
        mapped = map_usage(fabricated)
        self.assertIsNone(mapped["cost_cents"])          # 9999.0 not trusted
        self.assertEqual(mapped["cost_quality"], QUALITY_UNAVAILABLE)
        self.assertEqual(mapped["cost_note"], "subscription_not_metered")
        pc = project_cost(_events([fabricated]), PRICING)
        self.assertIsNone(pc["estimated_cost"])
        self.assertIn(pc["cost_status"], ("subscription/not-metered", "stale", "unknown"))

    def test_fabricated_cost_would_fail_if_trusted(self) -> None:
        # vacuity guard: the negative assertion is real — if a surface regressed
        # to trusting the injected 9999.0, this exact check would not hold.
        self.assertNotEqual(map_usage(dict(CODEX, cost_cents=9999.0))["cost_cents"], 9999.0)


if __name__ == "__main__":
    unittest.main()
