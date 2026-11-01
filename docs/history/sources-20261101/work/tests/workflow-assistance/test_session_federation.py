"""Tests for the session federation core (WL-P0-020/021/022/030/090).

Repo convention: modules under services/ are loaded by spec (no package
__init__), so these tests load each file via importlib and pre-register
the required module names in sys.modules.
"""
from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / "services" / "session-federation"
# Appended, not prepended: this file spec-loads the modules it exercises out of
# services/session-federation, and `capsule.py` also exists in the core scripts directory, so
# putting that directory first could resolve a name to the wrong module.
sys.path.append(str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import project_temp  # noqa: E402


def _load(name: str, module_name: str):
    spec = importlib.util.spec_from_file_location(module_name, SERVICES / name)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


class CanonicalSessionTests(unittest.TestCase):
    def test_roundtrip_and_digest_stability(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        session = canonical.CanonicalSession(
            universal_session_id="us-1",
            workspace_id="w",
            project_id="work-lab",
            source_agent="hermes",
            source_session_id="s-1",
            source_format="hermes-jsonl",
            native_path="C:/state/db",
            native_hash="abc",
            messages=({"role": "user", "text": "goal"}, {"role": "assistant", "text": "done"}),
            decisions=({"decision": "use v2", "why": "better"},),
            todos=({"text": "t", "state": "open"},),
            changed_files=("a.py",),
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"progress": "step 2/5"},
        )
        text = session.to_json()
        back = canonical.CanonicalSession.from_json(text)
        self.assertEqual(back, session)
        self.assertEqual(back.content_digest(), session.content_digest())
        self.assertEqual(back.to_dict()["schema_version"], canonical.SCHEMA_VERSION)

    def test_l3_requires_verified_native_resume(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        with self.assertRaisesRegex(ValueError, "L3"):
            canonical.CanonicalSession(
                universal_session_id="x",
                workspace_id="w",
                project_id="p",
                source_agent="a",
                source_session_id="s",
                source_format="f",
                portability_level=canonical.PortabilityLevel.L3_NATIVE_RESUME,
            )
        ok = canonical.CanonicalSession(
            universal_session_id="x",
            workspace_id="w",
            project_id="p",
            source_agent="a",
            source_session_id="s",
            source_format="f",
            portability_level=canonical.PortabilityLevel.L3_NATIVE_RESUME,
            metadata={"native_resume": {"verified": True}},
        )
        self.assertIs(ok.portability_level, canonical.PortabilityLevel.L3_NATIVE_RESUME)

    def test_unknown_event_type_rejected_fail_closed(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        self.assertEqual(canonical.canonical_event_type("tool_call"), canonical.EventType.TOOL_CALL)
        with self.assertRaises(ValueError):
            canonical.canonical_event_type("quantum_leap")

    def test_loss_report_bounds(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        report = canonical.LossReport(messages=0.5)
        self.assertEqual(report.messages, 0.5)
        with self.assertRaises(ValueError):
            canonical.LossReport(messages=1.5)

    def test_capsule_render_rejects_l0(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        l0 = canonical.CanonicalSession(
            universal_session_id="x",
            workspace_id="w",
            project_id="p",
            source_agent="a",
            source_session_id="s",
            source_format="f",
        )
        with self.assertRaises(ValueError):
            canonical.render_capsule(l0)


class ProviderHandoffTests(unittest.TestCase):
    def _provider(self):
        canonical = _load("canonical.py", "test_session_federation.canonical")
        provider = _load("provider.py", "test_session_federation.provider")

        class _P(provider.SessionProvider):  # type: ignore[misc]
            source_agent = "codex"

            def discover(self, project_id: str):
                return []

            def read(self, ref):
                raise NotImplementedError

            def health(self):
                return {"ok": True}

        return canonical, provider, _P()

    def test_handoff_writes_triple_with_honest_loss_report(self) -> None:
        canonical, provider, p = self._provider()
        session = canonical.CanonicalSession(
            universal_session_id="us-9",
            workspace_id="w",
            project_id="work-lab",
            source_agent="codex",
            source_session_id="c-9",
            source_format="codex-json",
            messages=({"role": "user", "text": "build it"},),
            todos=({"text": "wire tests", "state": "open"},),
            changed_files=("main.py",),
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
        )
        with tempfile.TemporaryDirectory() as td:
            result = p.handoff(session, td)
            for key in ("handoff", "capsule", "loss_report"):
                self.assertTrue(Path(result[key]).is_file(), key)
            doc = json.loads(Path(result["handoff"]).read_text(encoding="utf-8"))
            self.assertEqual(doc["schema"], "handoff-v1")
            self.assertEqual(doc["from_agent"], "codex")
            loss = json.loads(Path(result["loss_report"]).read_text(encoding="utf-8"))
            self.assertEqual(loss["native_state_available"], False)
            self.assertFalse(loss["system_prompt_transferred"])
            capsule = Path(result["capsule"]).read_text(encoding="utf-8")
            self.assertIn("Session Capsule", capsule)
            self.assertIn("wire tests", capsule)

    def test_export_import_roundtrip(self) -> None:
        canonical, provider, p = self._provider()
        session = canonical.CanonicalSession(
            universal_session_id="us-2",
            workspace_id="w",
            project_id="work-lab",
            source_agent="hermes",
            source_session_id="h-2",
            source_format="hermes-jsonl",
        )
        with tempfile.TemporaryDirectory() as td:
            out = p.export(session, td)
            self.assertTrue(Path(out["exported"]).is_file())
            back = json.loads(Path(out["exported"]).read_text(encoding="utf-8"))
            rehydrated = p.import_session(back, td)
            self.assertEqual(rehydrated.content_digest(), session.content_digest())
            self.assertEqual(rehydrated.universal_session_id, session.universal_session_id)
            self.assertEqual(rehydrated.source_agent, session.source_agent)
            self.assertEqual(rehydrated.to_dict(), session.to_dict())


class HermesProviderTests(unittest.TestCase):
    def test_discover_jsonl_and_read_normalizes_l1(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        provider_mod = _load("provider.py", "test_session_federation.provider")
        sys.modules["services_session_federation_provider"] = provider_mod
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.hermes_provider", SERVICES / "hermes_provider.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)

        with tempfile.TemporaryDirectory() as td:
            home = Path(td) / ".hermes"
            sessions = home / "sessions"
            sessions.mkdir(parents=True)
            transcript = sessions / "s-1.jsonl"
            transcript.write_text(
                json.dumps({"session_id": "s-1", "project": "work-lab", "workspace": "w", "type": "user_message", "text": "hi", "ts": "2026-09-01T00:00:00Z"}) + "\n"
                + json.dumps({"type": "assistant_message", "text": "ok", "ts": "2026-09-01T00:00:05Z"}) + "\n"
                + json.dumps({"type": "decision", "choice": "use v2", "reason": "better", "ts": "2026-09-01T00:00:09Z"}) + "\n",
                encoding="utf-8",
            )
            p = module.HermesSessionProvider(home=str(home))
            refs = list(p.discover("work-lab"))
            self.assertEqual(len(refs), 1)
            ref = refs[0]
            self.assertEqual(ref.source_session_id, "s-1")
            self.assertEqual(ref.project_id, "work-lab")
            loaded = p.read(ref)
            self.assertEqual(len(loaded.messages), 2)
            self.assertEqual(loaded.portability_level, canonical.PortabilityLevel.L1_HANDOFF)
            self.assertEqual(loaded.decisions[0]["decision"], "use v2")
            health = p.health()
            # sessions dir exists → provider is reachable; state.db absence is noted
            self.assertTrue(health["ok"])
            self.assertIn("state.db missing", health["notes"])
            self.assertEqual(p.resume_native(loaded), "hermes --resume s-1")

    def test_discover_missing_store_is_soft_empty(self) -> None:
        _load("canonical.py", "test_session_federation.canonical")
        provider_mod = _load("provider.py", "test_session_federation.provider")
        sys.modules["services_session_federation_provider"] = provider_mod
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.hermes_provider2", SERVICES / "hermes_provider.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as td:
            p = module.HermesSessionProvider(home=str(Path(td) / "absent-home"))
            self.assertEqual(list(p.discover("anything")), [])
            self.assertFalse(p.health()["ok"])


class SessionIndexTests(unittest.TestCase):
    """WL-P0-050 unified session history index."""

    def _index(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.index", SERVICES / "index.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_index_and_search_roundtrip(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        index_mod = self._index()
        with tempfile.TemporaryDirectory() as td:
            idx = index_mod.SessionIndex(Path(td) / "index.sqlite")
            s1 = canonical.CanonicalSession(
                universal_session_id="us-1",
                workspace_id="w",
                project_id="work-lab",
                source_agent="hermes",
                source_session_id="h-1",
                source_format="hermes-jsonl",
                messages=({"role": "user", "text": "build the pipeline"},),
                decisions=({"decision": "use SQLite", "why": "portable"},),
                todos=({"text": "add tests", "state": "open"},),
                changed_files=("pipeline.py",),
                metadata={"model": "agnes"},
                started_at="2026-09-01T00:00:00Z",
                portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            )
            s2 = canonical.CanonicalSession(
                universal_session_id="us-2",
                workspace_id="w",
                project_id="work-lab",
                source_agent="codex",
                source_session_id="c-1",
                source_format="codex-json",
                changed_files=("pipeline.py", "tests.py"),
                metadata={"model": "gpt"},
                started_at="2026-09-02T00:00:00Z",
                portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            )
            self.assertEqual(idx.index_session(s1)["status"], "INDEXED")
            self.assertEqual(idx.index_session(s2)["status"], "INDEXED")

            # FTS search
            results = idx.search("pipeline")
            self.assertGreaterEqual(len(results), 2)
            self.assertTrue(all("pipeline" in r["changed_files"] or "pipeline" in r["semantic_summary"] for r in results))

            # structured filter by agent
            hermes_only = idx.list_sessions(agent="hermes")
            self.assertEqual(len(hermes_only), 1)
            self.assertEqual(hermes_only[0]["universal_session_id"], "us-1")

            # date + model filter
            model_hit = idx.list_sessions(model="agnes")
            self.assertEqual(len(model_hit), 1)
            self.assertEqual(model_hit[0]["source_agent"], "hermes")
            ranged = idx.list_sessions(since="2026-09-02T00:00:00Z", until="2026-09-02T23:59:59Z")
            self.assertEqual(len(ranged), 1)
            self.assertEqual(ranged[0]["universal_session_id"], "us-2")

            # idempotent re-index
            before = idx.health()["sessions"]
            idx.index_session(s1)
            self.assertEqual(idx.health()["sessions"], before)

            # health
            health = idx.health()
            self.assertTrue(health["ok"])
            self.assertEqual(health["sessions"], 2)
            self.assertEqual(health["schema_version"], index_mod.INDEX_SCHEMA_VERSION)
            idx.close()

    def test_decision_and_error_keyword_search(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        index_mod = self._index()
        with tempfile.TemporaryDirectory() as td:
            idx = index_mod.SessionIndex(Path(td) / "index.sqlite")
            s = canonical.CanonicalSession(
                universal_session_id="us-3",
                workspace_id="w",
                project_id="work-lab",
                source_agent="dsh",
                source_session_id="d-1",
                source_format="dsh-jsonl",
                decisions=({"decision": "rollback migration", "why": "CI failed"},),
                events=({"type": "error", "text": "schema drift"},),
                portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            )
            idx.index_session(s)
            hits = idx.search("rollback")
            self.assertEqual(len(hits), 1)
            self.assertEqual(hits[0]["source_agent"], "dsh")
            # decision keyword shows up in semantic summary
            self.assertIn("rollback migration", hits[0]["semantic_summary"])
            idx.close()


class ContinuesPocTests(unittest.TestCase):
    """WL-P0-040 cross-agent continues POC."""

    def _load_continues(self):
        # canonical must be pre-loaded so the L3 enum identity check in
        # _recommendation compares against the same enum class the test built
        _load("canonical.py", "test_session_federation.canonical")
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.continues", SERVICES / "continues.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _sample_session(self, canonical):
        return canonical.CanonicalSession(
            universal_session_id="us-c",
            workspace_id="w",
            project_id="work-lab",
            source_agent="codex",
            source_session_id="cx-1",
            source_format="codex-json",
            messages=({"role": "user", "text": "build"}, {"role": "assistant", "text": "ok"}),
            decisions=({"decision": "x", "why": "y"},),
            todos=({"text": "t", "state": "open"},),
            changed_files=("a.py",),
            events=({"type": "tool_call", "data": "run tests"},),
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"model": "gpt"},
        )

    def test_capsule_matches_context_capsule_v1_schema(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        k = self._load_continues()
        doc = k.build_capsule_doc(self._sample_session(canonical), "hermes")
        self.assertEqual(doc["schema_version"], "work-lab/context-capsule/v1")
        self.assertEqual(doc["content"]["type"], "handoff")
        self.assertEqual(doc["integrity"]["algorithm"], "sha256")
        import re as _re
        self.assertRegex(doc["integrity"]["contentHash"], r"^[a-f0-9]{64}$")

    def test_continues_report_recommends_adopt_for_full_retention(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        k = self._load_continues()
        with tempfile.TemporaryDirectory() as td:
            report = k.run_continues(self._sample_session(canonical), "hermes", td)
            self.assertEqual(report["recommendation"], "ADOPT")
            self.assertEqual(report["retention"]["message_retention"], 1.0)
            self.assertTrue(Path(report["report_path"]).is_file())
            self.assertTrue(Path(report["capsule_path"]).is_file())

    def test_pairs_cover_the_six_mandatory_transitions(self) -> None:
        k = self._load_continues()
        self.assertEqual(k.CONTINUES_PAIRS, (
            ("codex", "hermes"),
            ("hermes", "codex"),
            ("codex", "dsh"),
            ("dsh", "codex"),
            ("claude", "codex"),
            ("opencode", "codex"),
        ))

    def test_l3_session_recommends_absorb(self) -> None:
        canonical = _load("canonical.py", "test_session_federation.canonical")
        k = self._load_continues()
        s = canonical.CanonicalSession(
            universal_session_id="us-l3",
            workspace_id="w",
            project_id="work-lab",
            source_agent="hermes",
            source_session_id="h-l3",
            source_format="hermes-jsonl",
            portability_level=canonical.PortabilityLevel.L3_NATIVE_RESUME,
            metadata={"native_resume": {"verified": True}},
        )
        metric = k.retention_metric(s, target_agent="hermes")
        self.assertEqual(metric.resume_usability, "native-resume")
        self.assertEqual(k._recommendation(metric, s), "ABSORB")


class AcpFacadeTests(unittest.TestCase):
    """WL-P0-060 ACP session facade."""

    def _load_facade(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.acp_facade", SERVICES / "acp_facade.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    class _StubProvider:
        def __init__(self):
            self._handoff_result = {"loss_report": {"dropped_channels": ["raw_context"]}}
        def discover(self, project_id): return iter([])
        def read(self, ref): raise NotImplementedError
        def resume_native(self, session):
            # simulate: native resume command available
            return "codex resume <session>"
        def handoff(self, source_session, out_dir):
            import json
            from pathlib import Path
            d = Path(out_dir); d.mkdir(parents=True, exist_ok=True)
            return {"loss_report": self._handoff_result["loss_report"], "written": str(d / "handoff.json")}
        def export(self, session, directory): return {"exported": directory + "/out.json"}
        def health(self): return {"ok": True, "notes": []}

    def test_all_five_operations(self):
        import importlib.util
        facade_mod = self._load_facade()
        stub = self._StubProvider()
        facade = facade_mod.AcpSessionFacade({"codex": stub})
        self.assertEqual(facade.registered_agents(), ["codex"])

        r_new = facade.session_new("codex", "work-lab")
        self.assertEqual(r_new.outcome, facade_mod.Outcome.NEW_SESSION)

        r_list = facade.session_list("codex", "work-lab")
        self.assertEqual(r_list.outcome, facade_mod.Outcome.LISTED)
        self.assertEqual(r_list.session_id, "0")

        r_close = facade.session_close("codex", "sess-1")
        self.assertEqual(r_close.outcome, facade_mod.Outcome.CLOSED)

        r_prompt = facade.session_prompt("codex", "sess-1", "do the thing")
        self.assertEqual(r_prompt.outcome, facade_mod.Outcome.PROMPTED)

        r_prompt_empty = facade.session_prompt("codex", "sess-1", "   ")
        self.assertEqual(r_prompt_empty.outcome, facade_mod.Outcome.UNAVAILABLE)

        r_missing = facade.session_new("dsh", "work-lab")
        self.assertEqual(r_missing.outcome, facade_mod.Outcome.UNAVAILABLE)

    def test_resume_downgrades_without_verified_marker(self):
        import importlib.util
        facade_mod = self._load_facade()
        _load("canonical.py", "test_session_federation.canonical")
        canonical = sys.modules["test_session_federation.canonical"]
        s = canonical.CanonicalSession(
            universal_session_id="us-x", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
        )
        facade = facade_mod.AcpSessionFacade({"codex": self._StubProvider()})
        r = facade.session_resume("codex", s)
        # No verified native-resume marker → must downgrade to NEW_SESSION
        self.assertEqual(r.outcome, facade_mod.Outcome.NEW_SESSION)
        self.assertTrue(any("opening new session" in n for n in r.notes))

    def test_resume_with_verified_marker_reports_resumed(self):
        import importlib.util
        facade_mod = self._load_facade()
        _load("canonical.py", "test_session_federation.canonical")
        canonical = sys.modules["test_session_federation.canonical"]
        s = canonical.CanonicalSession(
            universal_session_id="us-y", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s2", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L3_NATIVE_RESUME,
            metadata={"native_resume": {"verified": True}},
        )
        facade = facade_mod.AcpSessionFacade({"codex": self._StubProvider()})
        r = facade.session_resume("codex", s)
        self.assertEqual(r.outcome, facade_mod.Outcome.RESUMED)
        self.assertEqual(r.session_id, "s2")

    def test_new_with_source_writes_handoff(self):
        import importlib.util
        import tempfile
        facade_mod = self._load_facade()
        _load("canonical.py", "test_session_federation.canonical")
        canonical = sys.modules["test_session_federation.canonical"]
        s = canonical.CanonicalSession(
            universal_session_id="us-z", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s3", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
        )
        facade = facade_mod.AcpSessionFacade({"codex": self._StubProvider()})
        with tempfile.TemporaryDirectory() as td:
            r = facade.session_new("codex", "work-lab", source_session=s, out_dir=td)
            self.assertEqual(r.outcome, facade_mod.Outcome.NEW_SESSION)
            self.assertEqual(r.loss_report["dropped_channels"], ["raw_context"])
        # without out_dir must be UNAVAILABLE
        r2 = facade.session_new("codex", "work-lab", source_session=s)
        self.assertEqual(r2.outcome, facade_mod.Outcome.UNAVAILABLE)


class RecommenderTests(unittest.TestCase):
    """WL-P0-070 session recommendation engine."""

    def _load_recommender(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.recommender", SERVICES / "recommender.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _index_with_sessions(self):
        import importlib.util
        import tempfile
        import os

        spec = importlib.util.spec_from_file_location(
            "test_session_federation.index", SERVICES / "index.py"
        )
        idx_mod = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = idx_mod
        spec.loader.exec_module(idx_mod)

        # A plain fixture dir (not TemporaryDirectory): the index has to outlive a context-manager
        # exit that would delete the database underneath it. idx.close() is registered so the
        # SQLite handle is dropped before project_temp's sweeper removes the directory.
        td = project_temp.fixture_dir(prefix="sf-index-")
        idx = idx_mod.SessionIndex(Path(td) / "index.sqlite")
        self.addCleanup(idx.close)

        spec2 = importlib.util.spec_from_file_location("test_session_federation.canonical2", SERVICES / "canonical.py")
        canonical = importlib.util.module_from_spec(spec2)
        sys.modules["test_session_federation.canonical2"] = canonical
        spec2.loader.exec_module(canonical)

        def session(sid, agent, summary, files, started, port, loss, extra_meta=None):
            meta = {"summary": summary, "changed_files": list(files), "loss_report": loss}
            if extra_meta:
                meta.update(extra_meta)
            return canonical.CanonicalSession(
                universal_session_id=sid, workspace_id="w", project_id="work-lab",
                source_agent=agent, source_session_id=sid, source_format=agent + "-protocol",
                portability_level=port,
                metadata=meta,
                started_at=started,
            )

        loss_full = {}
        loss_partial = {"dropped_channels": ["raw_context"]}
        sessions = [
            session("us-a", "codex", "pipeline refactor", ("pipeline.py",), "2026-09-01T00:00:00Z",
                    canonical.PortabilityLevel.L1_HANDOFF, loss_full),
            session("us-b", "hermes", "ci gate fix", ("ci.yml",), "2026-09-10T00:00:00Z",
                    canonical.PortabilityLevel.L1_HANDOFF, loss_partial),
            session("us-c", "codex", "pipeline test", ("pipeline.py", "tests.py"), "2026-09-11T00:00:00Z",
                    canonical.PortabilityLevel.L3_NATIVE_RESUME, {},
                    extra_meta={"native_resume": {"verified": True}}),
        ]
        for s in sessions:
            idx.index_session(s)
        return idx

    def test_recommend_returns_scored_candidates(self):
        import importlib.util
        idx = self._index_with_sessions()
        rec_mod = self._load_recommender()
        rec = rec_mod.SessionRecommender(idx, target_agent="codex", half_life_hours=24.0, min_score=0.0)
        cands = rec.recommend("pipeline", limit=5)
        self.assertGreater(len(cands), 0)
        top = cands[0]
        self.assertEqual(top.source_agent, "codex")
        self.assertIn("semantic_match", top.score_breakdown)
        self.assertIn("agent_fit", top.score_breakdown)
        # scores must be monotonically decreasing
        scores = [c.score for c in cands]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_same_agent_scores_higher(self):
        import importlib.util
        idx = self._index_with_sessions()
        rec_mod = self._load_recommender()
        rec_c = rec_mod.SessionRecommender(idx, target_agent="codex", min_score=0.0)
        rec_h = rec_mod.SessionRecommender(idx, target_agent="hermes", min_score=0.0)
        cands_c = {c.universal_session_id: c for c in rec_c.recommend("pipeline", limit=5)}
        cands_h = {c.universal_session_id: c for c in rec_h.recommend("pipeline", limit=5)}
        # codex candidate should rank at least as high under codex target
        if "us-a" in cands_c and "us-a" in cands_h:
            self.assertGreaterEqual(cands_c["us-a"].score, cands_h["us-a"].score)

    def test_recommendation_report_schema(self):
        idx = self._index_with_sessions()
        rec_mod = self._load_recommender()
        rec = rec_mod.SessionRecommender(idx, target_agent="codex", min_score=0.0)
        cands = rec.recommend("pipeline", limit=3)
        report = rec_mod.build_recommendation_report("pipeline", cands, target_agent="codex", project_id="work-lab")
        self.assertEqual(report["schema"], "work-lab/session-recommendations/v1")
        self.assertEqual(report["project_id"], "work-lab")
        self.assertIn("recommended", report)
        self.assertIsInstance(report["candidates"], list)
        if cands:
            self.assertEqual(report["recommended"], cands[0].universal_session_id)

    def test_no_match_returns_empty(self):
        idx = self._index_with_sessions()
        rec_mod = self._load_recommender()
        rec = rec_mod.SessionRecommender(idx, target_agent="codex", min_score=0.0)
        # FTS query with no hits → empty list
        cands = rec.recommend("zzz_nonexistent_token_xyz", limit=5)
        self.assertEqual(cands, [])


class CodexProviderTests(unittest.TestCase):
    """WL-P0-070 (Codex session reader) — read-only discovery + L1 normalisation."""

    def _load_codex(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.codex", SERVICES / "codex_provider.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _make_rollout(self, root: Path, content: str) -> Path:
        """Lay out a minimal ~/.codex/sessions/YYYY/MM/DD/rollout-*.jsonl tree."""
        day = root / "sessions" / "2026" / "09" / "13"
        day.mkdir(parents=True, exist_ok=True)
        f = day / "rollout-2026-09-13T02-58-28-abcdef00-1111-2222-3333-444455556666.jsonl"
        f.write_text(content, encoding="utf-8")
        return f

    def test_discover_and_read_roundtrip(self):
        import json as _json
        import tempfile
        c = self._load_codex()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            rollout = "\n".join([
                _json.dumps({"timestamp": "2026-09-13T02:58:28Z", "ordinal": 0, "type": "session_meta",
                             "payload": {"session_id": "abcdef00", "cwd": "D:/All projects/WORK-LAB",
                                        "model_provider": "test-prov",
                                        "git": {"commit": "deadbeef"}}}),
                _json.dumps({"timestamp": "2026-09-13T02:58:30Z", "ordinal": 1, "type": "turn_context",
                             "payload": {"cwd": "D:/All projects/WORK-LAB", "model": "gpt-x"}}),
                _json.dumps({"timestamp": "2026-09-13T02:58:31Z", "ordinal": 2, "type": "response_item",
                             "payload": {"type": "message", "role": "user",
                                         "content": [{"type": "input_text", "text": "fix the gate"}]}}),
                _json.dumps({"timestamp": "2026-09-13T02:58:32Z", "ordinal": 3, "type": "response_item",
                             "payload": {"type": "custom_tool_call", "name": "apply_patch",
                                         "call_id": "c1", "input": {"path": "gate.py"}}}),
                _json.dumps({"timestamp": "2026-09-13T02:58:33Z", "ordinal": 4, "type": "response_item",
                             "payload": {"type": "custom_tool_call_output", "call_id": "c1", "output": "ok"}}),
                _json.dumps({"timestamp": "2026-09-13T02:58:34Z", "ordinal": 5, "type": "token_usage_record",
                             "payload": {"usage": {"total_tokens": 42}}}),
            ])
            self._make_rollout(root, rollout)

            prov = c.CodexSessionProvider(home=str(root))
            refs = list(prov.discover("work-lab"))
            self.assertEqual(len(refs), 1)
            self.assertEqual(refs[0].source_agent, "codex")
            self.assertEqual(refs[0].source_session_id, "abcdef00")
            self.assertEqual(refs[0].started_at, "2026-09-13T02:58:28")
            # discover no longer infers a model name from the provider
            self.assertIsNone(refs[0].model)

            sess = prov.read(refs[0])
            self.assertEqual(sess.universal_session_id, "codex:abcdef00")
            self.assertEqual(sess.source_agent, "codex")
            self.assertEqual(sess.source_format, "codex-rollout-jsonl")
            self.assertEqual(len(sess.messages), 1)
            self.assertEqual(sess.messages[0]["role"], "user")
            self.assertEqual(sess.git_commit, "deadbeef")
            self.assertEqual(sess.metadata.get("model"), "gpt-x")
            self.assertEqual(sess.metadata.get("usage_total_tokens"), 42)
            self.assertEqual(sess.changed_files, ("gate.py",))
            # events: 1 tool_call + 1 tool_result + event_msg sub-types if any
            self.assertGreaterEqual(len(sess.events), 2)
            self.assertEqual(sess.portability_level.name, "L1_HANDOFF")

    def test_missing_store_degrades_not_fails(self):
        import tempfile
        c = self._load_codex()
        with tempfile.TemporaryDirectory() as td:
            prov = c.CodexSessionProvider(home=str(Path(td) / "nowhere"))
            self.assertEqual(list(prov.discover("x")), [])
            health = prov.health()
            self.assertFalse(health["ok"])
            self.assertIn("sessions dir missing", health["notes"])

    def test_read_only_source_never_mutated(self):
        import json as _json
        import tempfile
        c = self._load_codex()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            content = _json.dumps({"timestamp": "2026-09-13T02:58:28Z", "ordinal": 0,
                                   "type": "session_meta",
                                   "payload": {"session_id": "s9", "cwd": "x"}}) + "\n"
            self._make_rollout(root, content)
            prov = c.CodexSessionProvider(home=str(root))
            refs = list(prov.discover("x"))
            self.assertEqual(len(refs), 1)
            sess = prov.read(refs[0])
            self.assertEqual(sess.source_session_id, "s9")
            # source file must be byte-identical after read
            self.assertEqual(refs[0].native_path and open(refs[0].native_path, encoding="utf-8").read(), content)


class DshProviderTests(unittest.TestCase):
    """WL-P0-080 (DSH session reader) — read-only projcache discovery + L1 handoff."""

    def _load_dsh(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.dsh", SERVICES / "dsh_provider.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _cell(self, val):
        """Wrap a value in the projcache row cell shape {ver, seq, val}."""
        return {"ver": 1, "seq": 100, "val": val}

    def _make_projcache(self, root: Path, cwd: str) -> Path:
        """Lay out a minimal ~/.dsh/storages/session_projcache/sessions/<uuid>.json."""
        d = root / "storages" / "session_projcache" / "sessions"
        d.mkdir(parents=True, exist_ok=True)
        doc = {
            "version": 5,
            "record": {
                "identity": {"createdAt": 1789312345138, "cwd": cwd, "isSeeded": False},
                "rows": {
                    "turnOutline": self._cell({"turns": [
                        {"turn": 1, "seq": 6, "prompt": "fix the gate",
                         "response": "done, here is the report"}], "draft": ""}),
                    "todos": self._cell([
                        {"content": "step a", "status": "completed"},
                        {"content": "step b", "status": "in_progress"}]),
                    "modelSelection": self._cell({"lastUsed": {
                        "provider": "deepseek-official", "model": "deepseek-v4-flash",
                        "reasoningEffort": "high"}, "pending": None}),
                    "sessionListMetadata": self._cell({"blank": False, "lastPromptAt": 1789312999000}),
                    "tokenUsage": self._cell({"totals": {"outputTokens": 100, "cacheReadTokens": 5}}),
                    "permissions": self._cell({"preset": "read-only", "approval": "ask"}),
                },
            },
        }
        f = d / "abc-0001.json"
        f.write_text(json.dumps(doc), encoding="utf-8")
        return f

    def test_discover_filters_by_project(self):
        import tempfile
        d = self._load_dsh()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_projcache(root, "D:/All projects/DESIGN-LAB")
            prov = d.DshSessionProvider(home=str(root))
            self.assertEqual(len(list(prov.discover("design-lab"))), 1)
            # a different project must NOT match this session's cwd
            self.assertEqual(len(list(prov.discover("work-lab"))), 0)

    def test_read_normalises_to_l1(self):
        import tempfile
        d = self._load_dsh()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            self._make_projcache(root, "D:/All projects/DESIGN-LAB")
            prov = d.DshSessionProvider(home=str(root))
            ref = list(prov.discover("design-lab"))[0]
            sess = prov.read(ref)
            self.assertEqual(sess.source_agent, "dsh")
            self.assertEqual(sess.universal_session_id, "dsh:abc-0001")
            self.assertEqual(sess.source_format, "dsh-projcache")
            # two outline turns -> user + assistant messages
            self.assertEqual(len(sess.messages), 2)
            self.assertEqual(sess.messages[0]["role"], "user")
            self.assertEqual(sess.messages[1]["role"], "assistant")
            self.assertEqual(len(sess.todos), 2)
            self.assertEqual(sess.metadata.get("model"), "deepseek-v4-flash")
            self.assertEqual(sess.metadata.get("model_provider"), "deepseek-official")
            self.assertEqual(sess.metadata.get("reasoning_effort"), "high")
            self.assertEqual(sess.metadata.get("token_usage_totals"), {"outputTokens": 100, "cacheReadTokens": 5})
            self.assertEqual(sess.portability_level.name, "L1_HANDOFF")
            # honest loss accounting: tool channels unavailable in projection
            self.assertEqual(sess.metadata["loss_report"]["tool_calls"], 0.0)
            self.assertFalse(sess.metadata["loss_report"]["native_state_available"])
            self.assertIn("zstd_transcript", sess.metadata["loss_report"]["notes"])

    def test_missing_store_degrades(self):
        import tempfile
        d = self._load_dsh()
        with tempfile.TemporaryDirectory() as td:
            prov = d.DshSessionProvider(home=str(Path(td) / "nowhere"))
            self.assertEqual(list(prov.discover("x")), [])
            health = prov.health()
            self.assertFalse(health["ok"])
            self.assertEqual(health["session_count"], 0)

    def test_read_only_source_never_mutated(self):
        import tempfile
        d = self._load_dsh()
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            p = self._make_projcache(root, "D:/All projects/DESIGN-LAB")
            before = p.read_text(encoding="utf-8")
            prov = d.DshSessionProvider(home=str(root))
            ref = list(prov.discover("design-lab"))[0]
            prov.read(ref)
            self.assertEqual(p.read_text(encoding="utf-8"), before)


class HandoffAuditTests(unittest.TestCase):
    """WL-P0-080 handoff audit ledger."""

    def _load_audit(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "test_session_federation.audit", SERVICES / "audit.py"
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _ledger_with_records(self):
        a = self._load_audit()
        td = project_temp.fixture_dir(prefix="sf-audit-")
        ledger = a.HandoffAuditLedger(Path(td) / "handoff-audit.jsonl")
        # Build a two-hop chain: us-a → us-b → us-c
        r1 = ledger.record_handoff(
            universal_session_id="us-a", source_agent="codex", target_agent="hermes",
            portability_level="L1_HANDOFF",
            loss_report={"messages": 1.0, "tool_calls": 0.8, "tool_results": 1.0},
            dropped_channels=("tool_calls",),
            capsule_bytes=b'{"content":"body"}',
            capsule_path=str(Path(td) / "capsule1.json"),
            target_universal_session_id="us-b",
            notes=("first hop",),
        )
        # write a capsule file matching the recorded hash
        (Path(td) / "capsule1.json").write_bytes(b'{"content":"body"}')
        r2 = ledger.record_handoff(
            universal_session_id="us-b", source_agent="hermes", target_agent="codex",
            portability_level="L1_HANDOFF",
            loss_report={"messages": 0.9, "tool_calls": 1.0, "tool_results": 1.0},
            dropped_channels=(),
            target_universal_session_id="us-c",
        )
        self.assertTrue(r1.audit_id)
        self.assertTrue(r2.audit_id)
        return a, ledger, r1, r2

    def test_append_and_read(self):
        a, ledger, r1, r2 = self._ledger_with_records()
        records = ledger.read_all()
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0].audit_id, r1.audit_id)
        self.assertEqual(records[1].audit_id, r2.audit_id)
        self.assertEqual(records[0].universal_session_id, "us-a")
        self.assertEqual(records[0].target_universal_session_id, "us-b")

    def test_capsule_integrity_verify(self):
        a, ledger, r1, r2 = self._ledger_with_records()
        result = ledger.verify_capsule_integrity(r1)
        self.assertTrue(result["ok"])
        self.assertEqual(result["recorded_sha"], result["actual_sha"])
        # r2 had no capsule → recorded_sha is None → integrity fail
        result2 = ledger.verify_capsule_integrity(r2)
        self.assertFalse(result2["ok"])

    def test_provenance_chain(self):
        a, ledger, r1, r2 = self._ledger_with_records()
        chain = ledger.build_provenance_chain("us-a")
        self.assertEqual(chain["chain_length"], 2)
        self.assertTrue(chain["complete"])
        self.assertEqual(chain["outgoing_hops"][0]["universal_session_id"], "us-a")
        self.assertEqual(chain["outgoing_hops"][1]["universal_session_id"], "us-b")

    def test_read_for_session_includes_incoming(self):
        a, ledger, r1, r2 = self._ledger_with_records()
        # us-b is the target of r1 and source of r2
        records = ledger.read_for_session("us-b")
        self.assertEqual(len(records), 2)
        self.assertTrue(any(r.audit_id == r1.audit_id for r in records))
        self.assertTrue(any(r.audit_id == r2.audit_id for r in records))

    def test_health_clean(self):
        a, ledger, r1, r2 = self._ledger_with_records()
        h = ledger.health()
        self.assertTrue(h["ok"])
        self.assertEqual(h["total_records"], 2)
        self.assertEqual(h["malformed_records"], 0)

    def test_audit_id_is_sortable(self):
        a, ledger, r1, r2 = self._ledger_with_records()
        # audit_ids embed UTC timestamp — r1 < r2 lexicographically
        self.assertLess(r1.audit_id, r2.audit_id)


class AguProjectionTests(unittest.TestCase):
    """WL-P0-070 AGUI_PROJECTION — canonical -> AG-UI event stream."""

    def _load(self, name):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"test_session_federation.{name}", SERVICES / name
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _session(self, canonical, *, messages, events=(), metadata=None):
        return canonical.CanonicalSession(
            universal_session_id="us-aggui",
            workspace_id="w",
            project_id="work-lab",
            source_agent="hermes",
            source_session_id="s-aggui",
            source_format="hermes-jsonl",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            messages=tuple(messages),
            events=tuple(events),
            metadata=metadata or {},
        )

    def test_full_stream_shape(self):
        ag = self._load("agui_projection.py")
        canonical = self._load("canonical.py")
        sess = self._session(
            canonical,
            messages=[{"role": "user", "text": "hi"}, {"role": "assistant", "text": "hello"}],
            events=[{"type": "tool_call", "call_id": "c1", "tool": "apply_patch"},
                    {"type": "tool_result", "call_id": "c1", "output": "ok"}],
        )
        events = ag.project_agui_events(sess)
        types = [e["type"] for e in events]
        # framing + messages + state, in order
        self.assertEqual(types[0], "RUN_STARTED")
        self.assertEqual(types[-1], "RUN_FINISHED")
        self.assertIn("TEXT_MESSAGE_CONTENT", types)
        self.assertIn("TOOL_CALL_START", types)
        self.assertIn("STATE_SNAPSHOT", types)
        self.assertIn("STATE_DELTA", types)
        # snapshot carries semantic state
        snap = next(e for e in events if e["type"] == "STATE_SNAPSHOT")["snapshot"]
        self.assertEqual(snap["agent"], "hermes")
        self.assertEqual(snap["universal_session_id"], "us-aggui")
        # every event is a JSON-serialisable dict (no CanonicalSession objects)
        json.dumps(events, sort_keys=True)

    def test_honest_state_delta_from_loss_report(self):
        ag = self._load("agui_projection.py")
        canonical = self._load("canonical.py")
        sess = self._session(
            canonical,
            messages=[{"role": "user", "text": "x"}],
            metadata={"loss_report": {"messages": 0.5, "tool_calls": 0.0, "tool_results": 0.0,
                                      "reasoning": None, "native_state_available": False,
                                      "notes": {"zstd_transcript": "undecodable"}}},
        )
        events = ag.project_agui_events(sess)
        delta = next(e for e in events if e["type"] == "STATE_DELTA")["delta"]
        # ratios surfaced as percentages (LossReport = retention, not loss)
        self.assertEqual(delta["retention"]["messages"], 50)
        self.assertEqual(delta["retention"]["tool_calls"], 0)
        self.assertIsNone(delta["retention"]["reasoning"])
        self.assertFalse(delta["native_state_available"])
        self.assertIn("zstd_transcript", delta["notes"])

    def test_l0_discovery_refuses_messages(self):
        ag = self._load("agui_projection.py")
        canonical = self._load("canonical.py")
        sess = canonical.CanonicalSession(
            universal_session_id="us-l0", workspace_id="w", project_id="p",
            source_agent="hermes", source_session_id="s", source_format="x",
            portability_level=canonical.PortabilityLevel.L0_DISCOVERY,
        )
        events = ag.project_agui_events(sess)
        # no message events for a discovery-only session
        self.assertNotIn("TEXT_MESSAGE_START", [e["type"] for e in events])
        # run framing still present
        self.assertEqual(events[0]["type"], "RUN_STARTED")


class RegistryTests(unittest.TestCase):
    """WL-050 SESSION_REGISTRY — write-side authority with single-writer lease."""

    def _load(self, name):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"test_session_federation.{name}", SERVICES / name
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def _session(self, canonical, uid="hermes:s1", digest_summary="demo"):
        return canonical.CanonicalSession(
            universal_session_id=uid, workspace_id="w", project_id="work-lab",
            source_agent="hermes", source_session_id="s1", source_format="hermes-jsonl",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"summary": digest_summary},
        )

    def test_register_requires_lease(self):
        reg = self._load("registry.py")
        td = project_temp.fixture_dir(prefix="sf-registry-")
        r = reg.Registry(Path(td) / "r.sqlite", writer_id="C")
        # Registry.close() is thread-local-safe and idempotent; without it the SQLite handle keeps
        # the fixture directory undeletable on Windows (WinError 32) and the sweep can only report.
        self.addCleanup(r.close)
        canonical = self._load("canonical.py")
        with self.assertRaises(reg.LeaseHeldError):
            r.register(self._session(canonical))

    def test_single_writer_and_idempotent(self):
        reg = self._load("registry.py")
        canonical = self._load("canonical.py")
        td = project_temp.fixture_dir(prefix="sf-registry-")
        db = Path(td) / "reg.sqlite"
        a = reg.Registry(db, writer_id="A", lease_ttl_seconds=60)
        b = reg.Registry(db, writer_id="B", lease_ttl_seconds=60)
        self.addCleanup(a.close)
        self.addCleanup(b.close)
        a.acquire_lease()
        # B is refused while A holds a live lease
        with self.assertRaises(reg.LeaseHeldError):
            b.acquire_lease()
        sess = self._session(canonical)
        self.assertEqual(a.register(sess)["status"], "REGISTERED")
        self.assertEqual(a.register(sess)["status"], "ALREADY_REGISTERED")
        self.assertEqual(a.count(), 1)
        self.assertEqual(a.known_projects(), ["work-lab"])
        self.assertEqual(a.get("hermes:s1")["source_agent"], "hermes")

    def test_expired_lease_takes_over(self):
        import time
        reg = self._load("registry.py")
        td = project_temp.fixture_dir(prefix="sf-registry-")
        db = Path(td) / "e.sqlite"
        e = reg.Registry(db, writer_id="E", lease_ttl_seconds=0.05)
        self.addCleanup(e.close)
        e.acquire_lease()
        time.sleep(0.06)  # E's lease now expired
        x = reg.Registry(db, writer_id="X", lease_ttl_seconds=60)
        self.addCleanup(x.close)
        # a different writer can take over an expired foreign lease
        x.acquire_lease()
        self.assertEqual(x.lease_holder()["writer_id"], "X")


class OtelCorrelationTests(unittest.TestCase):
    """WL-P0-080 OTEL_CORRELATION — universal_session_id -> gen_ai.conversation.id."""

    def _load(self, name):
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            f"test_session_federation.{name}", SERVICES / name
        )
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = module
        spec.loader.exec_module(module)
        return module

    def test_conversation_id_is_universal_id(self):
        ot = self._load("otel_correlation.py")
        canonical = self._load("canonical.py")
        sess = canonical.CanonicalSession(
            universal_session_id="us-otel", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="native-42", source_format="codex-rollout-jsonl",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"model": "gpt-x", "model_provider": "openai"},
        )
        attrs = ot.otel_attributes(sess)
        self.assertEqual(attrs[ot.CONVERSATION_ID_ATTR], "us-otel")
        self.assertEqual(attrs[ot.AGENT_SYSTEM_ATTR], "codex")
        self.assertEqual(attrs[ot.NATIVE_SOURCE_ATTR], "native-42")
        self.assertEqual(attrs[ot.MODEL_ATTR], "gpt-x")

    def test_traceparent_deterministic_and_w3c(self):
        ot = self._load("otel_correlation.py")
        tp1 = ot.traceparent_for("us-otel")
        tp2 = ot.traceparent_for("us-otel")
        self.assertEqual(tp1, tp2)
        parts = tp1.split("-")
        self.assertEqual(len(parts), 4)
        self.assertEqual(len(parts[1]), 32)   # trace-id
        self.assertEqual(len(parts[2]), 16)   # span-id
        self.assertEqual(parts[0], "00")
        self.assertEqual(parts[3], "00")
        # a different session -> a different trace
        self.assertNotEqual(ot.trace_id_for("us-otel"), ot.trace_id_for("us-other"))

    def test_native_reverse_resolution(self):
        ot = self._load("otel_correlation.py")
        canonical = self._load("canonical.py")
        sess = canonical.CanonicalSession(
            universal_session_id="dsh:native-7", workspace_id="w", project_id="p",
            source_agent="dsh", source_session_id="native-7", source_format="dsh-projcache",
        )
        corr = ot.ConversationCorrelator()
        corr.register(sess)
        # registered pair resolves to the universal id
        self.assertEqual(corr.resolve("dsh", "native-7"), "dsh:native-7")
        # unregistered pair falls back to the canonical <agent>:<source> id
        self.assertEqual(corr.resolve("pi", "never-seen"), "pi:never-seen")
        self.assertIn("dsh:native-7", corr.known_conversations())

    def test_accepts_serialised_dict(self):
        ot = self._load("otel_correlation.py")
        # callers holding a to_dict() payload must still correlate
        d = {"universal_session_id": "us-d", "source_agent": "pi",
             "source_session_id": "src-9", "project_id": "p",
             "portability_level": "L1_HANDOFF", "metadata": {"model": "m1"}}
        attrs = ot.otel_attributes(d)
        self.assertEqual(attrs[ot.CONVERSATION_ID_ATTR], "us-d")
        self.assertEqual(attrs[ot.MODEL_ATTR], "m1")


if __name__ == "__main__":
    unittest.main()
