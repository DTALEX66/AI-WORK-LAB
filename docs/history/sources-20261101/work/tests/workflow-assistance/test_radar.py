"""Tests for the intelligence plane (WL-370/380/390): radar core, the
12-axis ch 33 scoring, and auto POC routing.

Repo convention: load each service file by spec, pre-register in
sys.modules under a stable name.  No external source is contacted —
collectors are injectable adapters and the no-live-source case is the
honest UNAVAILABLE negative control.  The scorer reads metadata only
(ch 35 external-asset rule) and the router re-derives ch 33 tiers so its
thresholds are asserted not to drift from the scorer's.
"""
from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RAD = ROOT / "services" / "radar"


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, RAD / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class RadarCoreTests(unittest.TestCase):
    """WL-370: thirteen sources, 17-field Candidate, honest no-source."""

    def test_thirteen_sources(self):
        rc = _load("radar_core.py", "rad_rc")
        self.assertEqual(len(rc.RadarSource.ALL), 13)
        self.assertEqual(len(set(rc.RadarSource.ALL)), 13)   # no dup

    def test_candidate_has_seventeen_fields(self):
        rc = _load("radar_core.py", "rad_rc")
        c = rc.Candidate(canonical_url="https://github.com/x/y")
        self.assertEqual(len(c.to_dict()), 17)

    def test_discover_dedupes_and_sorts_desc(self):
        rc = _load("radar_core.py", "rad_rc")
        mk = lambda url, stars, growth: rc.Candidate(
            canonical_url=url, owner="o", repo="r", stars=stars, growth=growth)
        a1 = rc.StaticSourceAdapter("github", [mk("https://g/1", 900, 0.5),
                                               mk("https://g/2", 100, 0.9)])
        a2 = rc.StaticSourceAdapter("hf", [mk("https://g/1", 50, 0.1),
                                           mk("https://g/3", 400, 0.2)])
        core = rc.RadarCore([a1, a2])
        rows = core.discover("r")
        # dedup by canonical_url -> g/1, g/2, g/3
        self.assertEqual([r.canonical_url for r in rows],
                         ["https://g/1", "https://g/3", "https://g/2"])
        self.assertEqual(len(rows), 3)

    def test_empty_source_is_honestly_unavailable(self):
        rc = _load("radar_core.py", "rad_rc")
        empty = rc.StaticSourceAdapter("arxiv")            # no records
        self.assertFalse(empty.available())
        core = rc.RadarCore([empty])
        self.assertEqual(core.discover("anything"), [])   # skipped, not fabricated
        self.assertEqual(core.available_sources(), [])

    def test_receipt_is_deterministic(self):
        rc = _load("radar_core.py", "rad_rc")
        cands = [rc.Candidate(canonical_url="u", stars=5)]
        core = rc.RadarCore()
        self.assertEqual(core.receipt_sha256(cands),
                         rc.RadarCore().receipt_sha256(cands))


class RadarScoringTests(unittest.TestCase):
    """WL-380: the 12-axis ruler sums to 100; boundaries are exact."""

    def _scorer(self):
        return _load("radar_scoring.py", "rad_sc").RadarScorer()

    def test_default_weights_sum_to_100(self):
        sc = self._scorer()
        self.assertEqual(sum(sc.weights.values()), 100)
        self.assertEqual(len(sc.weights), 12)

    def test_benchmark_axis_is_never_fabricated(self):
        # a metadata-only candidate has no live benchmark: that axis is 0,
        # and no combination of other fields can give it points.
        rc = _load("radar_core.py", "rad_rc")
        cand = rc.Candidate(canonical_url="u", stars=20000, downloads=200000,
                            growth=1.0, api=True, cli=True, mcp=True,
                            windows=True, local=True, cost="free",
                            license="Apache-2.0", commit="abc",
                            project_fit="fits")
        receipt = self._scorer().score(cand)
        bench = next(a for a in receipt.axes if a.axis == "benchmark")
        self.assertEqual(bench.raw, 0.0)

    def test_strong_candidate_reaches_p0_audit(self):
        rc = _load("radar_core.py", "rad_rc")
        cand = rc.Candidate(canonical_url="u", owner="o", repo="strong",
                            commit="abc", license="Apache-2.0", stars=15000,
                            growth=1.0, downloads=120000, api=True,
                            cli=True, mcp=True, windows=True, local=True,
                            cost="free", project_fit="fits WORK-LAB")
        receipt = self._scorer().score(cand)
        self.assertEqual(receipt.tier, "P0_AUDIT")
        self.assertEqual(receipt.total, 95.0)   # 100 - the 5-point benchmark
        int(receipt.receipt_sha256(), 16)

    def test_tier_boundaries(self):
        sc = _load("radar_scoring.py", "rad_sc")
        self.assertEqual(sc.Tier.for_score(85.0), "P0_AUDIT")
        self.assertEqual(sc.Tier.for_score(84.9), "P1_POC")
        self.assertEqual(sc.Tier.for_score(70.0), "P1_POC")
        self.assertEqual(sc.Tier.for_score(69.9), "REFERENCE")
        self.assertEqual(sc.Tier.for_score(55.0), "REFERENCE")
        self.assertEqual(sc.Tier.for_score(54.9), "ARCHIVE")


class AutoPocRoutingTests(unittest.TestCase):
    """WL-390: the four dispositions + the P0 install-bypass guard."""

    def _router(self, **kw):
        ap = _load("auto_poc_routing.py", "rad_ap")
        return ap, ap.POCRouter(**kw)

    def test_four_tier_routing(self):
        ap, router = self._router()
        # (total, expected disposition)
        for total, disp in [(90.0, "audit"), (75.0, "poc"),
                            (60.0, "reference"), (40.0, "archive")]:
            d = router.route_candidate(total, "k")
            self.assertEqual(d.disposition, disp, f"total={total}")
            int(d.receipt_sha256(), 16)

    def test_p0_audit_forbids_install_bypass(self):
        ap, router = self._router()
        core = _load("radar_core.py", "rad_rc")
        sc = _load("radar_scoring.py", "rad_sc")
        cand = core.Candidate(canonical_url="u", owner="o", repo="strong",
                               commit="abc", license="Apache-2.0", stars=15000,
                               growth=1.0, downloads=120000, api=True,
                               cli=True, mcp=True, windows=True, local=True,
                               cost="free", project_fit="fits WORK-LAB")
        receipt = sc.RadarScorer().score(cand)
        self.assertEqual(receipt.tier, "P0_AUDIT")
        with self.assertRaises(ap.RoutingError):
            router.assert_no_install_bypass(receipt, audited=False)
        # once audited, the guard holds
        router.assert_no_install_bypass(receipt, audited=True)

    def test_poc_allowlist_relieves_work_lab_requirement(self):
        ap, router = self._router(auto_poc_allowlist={"cleared-key"})
        self.assertFalse(router.route_candidate(75.0, "cleared-key").requires_work_lab)
        self.assertTrue(router.route_candidate(75.0, "new-key").requires_work_lab)

    def test_router_thresholds_match_scorer_no_drift(self):
        # the router mirrors ch 33 thresholds; assert they never drift from
        # the scorer's canonical Tier.for_score.
        sc = _load("radar_scoring.py", "rad_sc")
        ap, router = self._router()
        for total in (54.9, 55.0, 69.9, 70.0, 84.9, 85.0, 100.0):
            self.assertEqual(sc.Tier.for_score(total),
                             router.route_candidate(total, "k").tier,
                             f"drift at total={total}")


class RadarObservationLayerTests(unittest.TestCase):
    """2026-09-15 audit sidecar: observation ledger / unknown semantics /
    source reports / price records / kind-routed ranking.  Pure additive —
    the 17-field Candidate and discover() above stay untouched."""

    def _obs(self):
        m = _load("radar_observations.py", "rad_obs")
        return m

    def test_f1_later_update_is_supersede_not_dropped(self):
        m = self._obs()
        l1, l2 = m.ObservationLedger(), m.ObservationLedger()
        l1.add(m.Observation(entity="u1", price=m.PriceRecord(amount=1.0, currency="USD"),
                             license="MIT", observation_version=1))
        l2.add(l1.latest("u1"))
        l2.add(m.Observation(entity="u1", price=m.PriceRecord(amount=2.0, currency="USD"),
                             license="MIT", observation_version=2))
        d = l2.diff(l1, l2)
        self.assertEqual(d["u1"]["relation"], "superseded")
        self.assertEqual(d["u1"]["changed_fields"], ["price.amount"])
        # the earlier original is retained, not deleted
        self.assertEqual(len(l2.versions("u1")), 2)

    def test_f1_same_version_disagreement_is_conflict(self):
        m = self._obs()
        a, b = m.ObservationLedger(), m.ObservationLedger()
        a.add(m.Observation(entity="u1", license="MIT", observation_version=3))
        b.add(m.Observation(entity="u1", license="Apache-2.0", observation_version=3))
        self.assertEqual(a.diff(a, b)["u1"]["relation"], "conflict")

    def test_f2_unknown_vs_confirmed_false(self):
        m = self._obs()
        rc = _load("radar_core.py", "rad_rc")
        led = m.build_ledger([rc.StaticSourceAdapter("github", [rc.Candidate(canonical_url="u9", stars=0)])], "")
        obs = led.latest("u9")
        self.assertIsNone(obs.stars)          # Candidate(0) is unknown, not confirmed zero
        self.assertIsNone(obs.downloads)
        self.assertEqual(obs.surfaces, {"api": False, "cli": False, "mcp": False})  # confirmed absent

    def test_f3_empty_answer_is_available_unavailable_is_not(self):
        m = self._obs()
        ok = m.SourceReport("s", m.FetchStatus.FETCH_OK, items_count=3)
        empty = m.SourceReport("s", m.FetchStatus.FETCH_EMPTY, items_count=0)
        unavail = m.SourceReport("s", m.FetchStatus.UNAVAILABLE, items_count=0)
        self.assertTrue(ok.available())
        self.assertTrue(empty.available())      # legit zero updates != broken source
        self.assertFalse(unavail.available())
        self.assertFalse(m.SourceReport("s", m.FetchStatus.ERROR).available())

    def test_f4_price_unknown_never_rendered_as_zero(self):
        m = self._obs()
        p = m.PriceRecord()                      # no amount
        self.assertTrue(p.is_unknown)
        self.assertIsNone(p.amount)
        obs = m.Observation(entity="u2", price=m.PriceRecord(amount=0.5, currency="USD",
                              provider="openai", billing="per_million_tokens",
                              valid_from="2026-09-01", as_of="2026-09-15"))
        self.assertEqual(obs.get("price.amount"), 0.5)
        self.assertEqual(obs.get("price.currency"), "USD")
        self.assertEqual(obs.get("price.amount" ) and obs.to_dict()["price"]["billing"], "per_million_tokens")

    def test_f4_entitlement_and_standard_version_sidecar(self):
        m = self._obs()
        obs = m.Observation(entity="kimi", entitlement="subscription", standard_version="K2.8",
                            fits={"WORK-LAB": "agent executor candidate"})
        self.assertEqual(obs.entitlement, "subscription")
        self.assertEqual(obs.fits["WORK-LAB"], "agent executor candidate")

    def test_f5_ranking_signal_routes_by_entity_kind(self):
        m = self._obs()
        self.assertEqual(m.rank_signal(m.EntityKind.PAPER), ("recency", "citation"))
        self.assertEqual(m.rank_signal(m.EntityKind.MODEL), ("downloads", "quality"))
        self.assertEqual(m.rank_signal(m.EntityKind.REPO), ("stars", "growth"))
        rows = [m.Observation(entity="b", entity_kind=m.EntityKind.MODEL, downloads=50),
                m.Observation(entity="a", entity_kind=m.EntityKind.MODEL, downloads=500)]
        ranked = m.rank(rows, m.EntityKind.MODEL)
        self.assertEqual([o.entity for o in ranked], ["a", "b"])   # unknown(0) never outranks real

    def test_ledger_wraps_plain_adapters_without_observation_hook(self):
        m = self._obs()
        rc = _load("radar_core.py", "rad_rc")
        led = m.build_ledger([rc.StaticSourceAdapter("github",
                                 [rc.Candidate(canonical_url="https://g/x", owner="g", repo="x", stars=77)])], "")
        self.assertEqual(led.latest("https://g/x").stars, 77)

    def test_radar_core_contract_untouched(self):
        # the additive layer must not perturb the v1 hard contracts
        rc = _load("radar_core.py", "rad_rc")
        self.assertEqual(len(rc.Candidate("u").to_dict()), 17)
        self.assertEqual(rc.RadarCore().SCHEMA, "work-lab/radar-core/v1")

if __name__ == "__main__":
    unittest.main(verbosity=2)
