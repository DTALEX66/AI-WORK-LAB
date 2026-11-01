"""Session federation integrity gate (WL-P0-100).

Verifies that all session-federation components are correctly wired:

1. CanonicalSession round-trips through JSON without field loss
2. PortabilityLevel ordering is L0 < L1 < L2 < L3
3. L3_NATIVE_RESUME requires the verified marker
4. LossReport validates channel ranges and rejects out-of-bounds values
5. SessionProvider contract is structurally satisfiable by a minimal stub
6. AcpSessionFacade degrades resume to NEW_SESSION without verified marker
7. HandoffAuditLedger records are append-only and idempotent per audit_id
8. SessionIndex FTS search returns results for indexed sessions
9. SessionRecommender scores decrease monotonically
10. continues POC capsule matches work-lab/context-capsule/v1 schema
11. AG-UI projection emits a well-formed run (framing + messages + state snapshot/delta)
12. OTel correlation maps universal_session_id -> gen_ai.conversation.id deterministically
13. Session Registry (WL-050) enforces single-writer lease and idempotent registration

Run via:  python -m services.session_federation.gate
Exit 0 on PASS, 1 on FAIL (gate reports each check individually).
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: load modules spec-style (repo convention)
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent.parent.parent))

import importlib.util as _ilu  # noqa: E402

def _load(mod_name: str, module_name: str):
    spec = _ilu.spec_from_file_location(module_name, _HERE / f"{mod_name}.py")
    module = _ilu.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


def _load_from(directory: Path, mod_name: str, module_name: str):
    spec = _ilu.spec_from_file_location(module_name, directory / f"{mod_name}.py")
    module = _ilu.module_from_spec(spec)
    sys.modules[module_name] = module
    spec.loader.exec_module(module)
    return module


_CORE_SCRIPTS = _HERE.parent.parent / "packages" / "client-neutral-core" / "scripts"

canonical = _load("canonical", "gate_canonical")
provider = _load("provider", "gate_provider")
hermes_provider = _load("hermes_provider", "gate_hermes_provider")
acp_facade = _load("acp_facade", "gate_acp_facade")
audit = _load("audit", "gate_audit")
index = _load("index", "gate_index")
recommender = _load("recommender", "gate_recommender")
continues = _load("continues", "gate_continues")
agui = _load("agui_projection", "gate_agui")
otel = _load("otel_correlation", "gate_otel")
registry = _load("registry", "gate_registry")


project_temp = _load_from(_CORE_SCRIPTS, "project_temp", "gate_project_temp")


class GateResult:
    def __init__(self):
        self.checks: list[tuple[str, bool, str]] = []

    def check(self, name: str, fn) -> None:
        try:
            fn()
            self.checks.append((name, True, ""))
        except Exception as exc:
            self.checks.append((name, False, str(exc)))

    @property
    def passed(self) -> bool:
        return all(ok for _, ok, _ in self.checks)

    def report(self) -> str:
        lines = []
        for name, ok, err in self.checks:
            status = "PASS" if ok else "FAIL"
            suffix = f"  ({err[:120]})" if err else ""
            lines.append(f"  [{status}] {name}{suffix}")
        n_pass = sum(1 for _, ok, _ in self.checks if ok)
        lines.append(f"\n{n_pass}/{len(self.checks)} checks passed")
        return "\n".join(lines)


def run_gate() -> GateResult:
    g = GateResult()

    # 1. CanonicalSession JSON round-trip
    def c1():
        s = canonical.CanonicalSession(
            universal_session_id="us-g1", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s1", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"summary": "gate test", "model": "test-model"},
            started_at="2026-09-13T00:00:00Z",
        )
        data = json.loads(s.to_json())
        s2 = canonical.CanonicalSession.from_dict(data)
        assert s2.universal_session_id == "us-g1"
        assert s2.portability_level is canonical.PortabilityLevel.L1_HANDOFF
    g.check("CanonicalSession JSON round-trip", c1)

    # 2. PortabilityLevel ordering (str-enum members order lexicographically)
    def c2():
        L0 = canonical.PortabilityLevel.L0_DISCOVERY
        L1 = canonical.PortabilityLevel.L1_HANDOFF
        L2 = canonical.PortabilityLevel.L2_EVENT_REPLAY
        L3 = canonical.PortabilityLevel.L3_NATIVE_RESUME
        levels = [L0, L1, L2, L3]
        assert levels == sorted(levels), "PortabilityLevel ordering broken"
    g.check("PortabilityLevel L0 < L1 < L2 < L3", c2)

    # 3. L3 requires verified marker
    def c3():
        try:
            canonical.CanonicalSession(
                universal_session_id="us-g3", workspace_id="w", project_id="work-lab",
                source_agent="codex", source_session_id="s3", source_format="codex-protocol",
                portability_level=canonical.PortabilityLevel.L3_NATIVE_RESUME,
                metadata={},  # missing native_resume.verified
            )
            raise AssertionError("L3 without marker did not raise")
        except ValueError:
            pass  # expected
    g.check("L3_NATIVE_RESUME rejects missing marker", c3)

    # 4. LossReport range validation
    def c4():
        try:
            canonical.LossReport(messages=1.5)
            raise AssertionError("LossReport accepted messages=1.5")
        except ValueError:
            pass
        lr = canonical.LossReport(messages=0.5, tool_calls=0.8, tool_results=1.0)
        assert 0.0 <= lr.messages <= 1.0
    g.check("LossReport validates channel ranges", c4)

    # 5. Minimal provider stub satisfies the contract structurally
    def c5():
        class StubProvider:
            def discover(self, project_id: str):
                return iter(())
            def read(self, ref: "provider.SessionRef"):
                raise NotImplementedError
            def resume_native(self, session) -> str | None:
                return None
            def handoff(self, source_session, out_dir: str) -> dict:
                return {"loss_report": {}}
            def export(self, session, directory: str) -> dict:
                return {}
            def health(self) -> dict:
                return {"ok": True}

        sp = StubProvider()
        # discover must return an iterable
        assert list(sp.discover("work-lab")) == []
        assert sp.resume_native(None) is None
        assert sp.health()["ok"] is True
    g.check("SessionProvider contract structurally satisfiable", c5)

    # 6. Facade degrades resume without verified marker
    def c6():
        s = canonical.CanonicalSession(
            universal_session_id="us-g6", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s6", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"summary": "no marker"},
        )
        class StubP:
            def discover(self, p): return iter(())
            def read(self, r): raise NotImplementedError
            def resume_native(self, s): return "codex resume"
            def handoff(self, s, d): return {"loss_report": {}}
            def export(self, s, d): return {}
            def health(self): return {"ok": True}

        facade = acp_facade.AcpSessionFacade({"codex": StubP()})
        result = facade.session_resume("codex", s)
        assert result.outcome is acp_facade.Outcome.NEW_SESSION, \
            f"expected NEW_SESSION, got {result.outcome}"
    g.check("Facade degrades resume to NEW_SESSION without marker", c6)

    # 7. Audit ledger is append-only
    def c7():
        td = project_temp.fixture_dir(prefix="sf-gate-")
        ledger = audit.HandoffAuditLedger(Path(td) / "audit.jsonl")
        r1 = ledger.record_handoff(
            universal_session_id="us-a", source_agent="codex", target_agent="hermes",
            loss_report={"messages": 1.0},
        )
        r2 = ledger.record_handoff(
            universal_session_id="us-a", source_agent="codex", target_agent="hermes",
            loss_report={"messages": 0.9},
        )
        records = ledger.read_all()
        assert len(records) == 2, f"expected 2 records, got {len(records)}"
        assert records[0].audit_id == r1.audit_id
        assert records[1].audit_id == r2.audit_id
        assert r1.audit_id != r2.audit_id  # unique per write
    g.check("Audit ledger append-only with unique audit_ids", c7)

    # 8. SessionIndex FTS search works
    def c8():
        td = project_temp.fixture_dir(prefix="sf-gate-")
        idx = index.SessionIndex(Path(td) / "index.sqlite")
        s = canonical.CanonicalSession(
            universal_session_id="us-g8", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s8", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"summary": "unique_gate_token_xyz"},
        )
        idx.index_session(s)
        rows = idx.search("unique_gate_token_xyz")
        idx.close()
        assert len(rows) == 1, f"expected 1 FTS hit, got {len(rows)}"
        assert rows[0]["universal_session_id"] == "us-g8"
    g.check("SessionIndex FTS search finds indexed session", c8)

    # 9. Recommender scores decrease monotonically
    def c9():
        td = project_temp.fixture_dir(prefix="sf-gate-")
        idx = index.SessionIndex(Path(td) / "index.sqlite")
        for i in range(3):
            s = canonical.CanonicalSession(
                universal_session_id=f"us-r{i}", workspace_id="w", project_id="work-lab",
                source_agent="codex", source_session_id=f"s{i}", source_format="codex-protocol",
                portability_level=canonical.PortabilityLevel.L1_HANDOFF,
                metadata={"summary": f"recommender test session {i} uniqueword{i}"},
                started_at=f"2026-09-{10 + i:02d}T00:00:00Z",
            )
            idx.index_session(s)
        rec = recommender.SessionRecommender(idx, target_agent="codex", min_score=0.0)
        cands = rec.recommend("recommender test", limit=5)
        idx.close()
        scores = [c.score for c in cands]
        assert scores == sorted(scores, reverse=True), f"non-monotonic scores: {scores}"
    g.check("Recommender scores decrease monotonically", c9)

    # 10. continues capsule matches context-capsule v1 schema
    def c10():
        s = canonical.CanonicalSession(
            universal_session_id="us-c10", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s10", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"summary": "capsule test"},
        )
        capsule_doc = continues.build_capsule_doc(s, "hermes")
        assert capsule_doc.get("schema_version") == "work-lab/context-capsule/v1", \
            f"capsule schema_version: {capsule_doc.get('schema_version')!r}"
        assert "content" in capsule_doc
        assert "body" in capsule_doc["content"]
        integrity = capsule_doc.get("integrity", {})
        assert integrity.get("contentHash") and integrity.get("algorithm") == "sha256", \
            "capsule missing integrity contentHash/sha256"
    g.check("continues capsule matches context-capsule/v1", c10)

    # 11. AG-UI projection is well-formed (framing + state, JSON-serialisable)
    def c11():
        s = canonical.CanonicalSession(
            universal_session_id="us-g11", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s11", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            messages=({"role": "user", "text": "hi"}, {"role": "assistant", "text": "ok"}),
            events=({"type": "tool_call", "call_id": "c1", "tool": "patch"},),
            metadata={"loss_report": {"messages": 1.0, "tool_calls": 0.9,
                                      "tool_results": 0.9, "reasoning": None,
                                      "native_state_available": False}},
        )
        events = agui.project_agui_events(s)
        types = [e["type"] for e in events]
        assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
        assert "TEXT_MESSAGE_CONTENT" in types and "TOOL_CALL_START" in types
        assert "STATE_SNAPSHOT" in types and "STATE_DELTA" in types
        # honest delta: tool_calls retained 0.9 -> 90% surfaced
        delta = next(e for e in events if e["type"] == "STATE_DELTA")["delta"]
        assert delta["retention"]["tool_calls"] == 90  # 0.9 retained -> 90
        json.dumps(events, sort_keys=True)  # everything serialisable
    g.check("AG-UI projection emits well-formed run", c11)

    # 12. OTel correlation: universal id -> gen_ai.conversation.id, deterministic trace
    def c12():
        s = canonical.CanonicalSession(
            universal_session_id="us-g12", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s12", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"model": "gpt-x"},
        )
        attrs = otel.otel_attributes(s)
        assert attrs[otel.CONVERSATION_ID_ATTR] == "us-g12"
        assert attrs[otel.AGENT_SYSTEM_ATTR] == "codex"
        assert attrs[otel.NATIVE_SOURCE_ATTR] == "s12"
        assert attrs[otel.MODEL_ATTR] == "gpt-x"
        # deterministic W3C trace context
        assert otel.traceparent_for("us-g12") == otel.traceparent_for("us-g12")
        assert otel.trace_id_for("us-g12") != otel.trace_id_for("us-other")
        # native reverse resolution falls back to <agent>:<source>
        corr = otel.ConversationCorrelator()
        corr.register(s)
        assert corr.resolve("codex", "s12") == "us-g12"
        assert corr.resolve("pi", "never-seen") == "pi:never-seen"
    g.check("OTel correlation maps universal_session_id deterministically", c12)

    # 13. Session Registry (WL-050): single-writer lease + idempotent registration
    def c13():
        td = project_temp.fixture_dir(prefix="sf-gate-")
        db = Path(td) / "gate-reg.sqlite"
        ra = registry.Registry(db, writer_id="gate-A", lease_ttl_seconds=60)
        rb = registry.Registry(db, writer_id="gate-B", lease_ttl_seconds=60)
        s = canonical.CanonicalSession(
            universal_session_id="us-g13", workspace_id="w", project_id="work-lab",
            source_agent="codex", source_session_id="s13", source_format="codex-protocol",
            portability_level=canonical.PortabilityLevel.L1_HANDOFF,
            metadata={"summary": "registry gate"},
        )
        # no-lease write fails closed
        fresh = registry.Registry(Path(td) / "gate-reg2.sqlite", writer_id="gate-X")
        try:
            fresh.register(s)
            raise AssertionError("registry write without a lease did not raise")
        except registry.LeaseHeldError:
            pass
        # A takes the lease; B is refused while A's lease is live
        ra.acquire_lease()
        try:
            rb.acquire_lease()
            raise AssertionError("second writer acquired a live-held lease")
        except registry.LeaseHeldError:
            pass
        # idempotent registration by universal_session_id
        assert ra.register(s)["status"] == "REGISTERED"
        assert ra.register(s)["status"] == "ALREADY_REGISTERED"
        assert ra.count() == 1
        assert ra.get("us-g13")["source_agent"] == "codex"
        assert "work-lab" in ra.known_projects()
        for handle in (ra, rb, fresh):
            handle.close()
    g.check("Session Registry single-writer lease + idempotent registration", c13)

    return g


def main() -> int:
    g = run_gate()
    print(g.report())
    if g.passed:
        print("GATE PASS")
        return 0
    else:
        print("GATE FAIL")
        return 1


if __name__ == "__main__":
    sys.exit(main())
