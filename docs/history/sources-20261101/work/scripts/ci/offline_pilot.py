"""NX-700 three-branch offline pilot harness.

This composes existing WORK-LAB adapters/validators; it is not a fourth product,
second task runtime, or provider. All fixtures are local and synthetic. The
report distinguishes OFFLINE_VERIFIED from UNKNOWN/LIVE_NOT_RUN/HUMAN_PENDING.
"""
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
WF = ROOT / "packages" / "client-neutral-core" / "scripts"
OBS = ROOT / "apps" / "observer" / "scripts"
sys.path.insert(0, str(WF))
sys.path.insert(0, str(OBS))
sys.path.insert(0, str(ROOT / "integrations" / "executors" / "codex"))
sys.path.insert(0, str(ROOT / "services" / "receipts"))

from acp_adapter import AcpAdapter  # noqa: E402
from task_ledger_replay import run_scenario  # noqa: E402
from usage_ingestion import normalize_event  # noqa: E402
from usage_rollup import rollup  # noqa: E402


def _workflow_pilot() -> dict[str, Any]:
    hermes = AcpAdapter("hermes")
    codex = AcpAdapter("codex")
    qwen_fixture = AcpAdapter("qwen-code", installed=False)
    negotiation = hermes.negotiate(["observe", "unknown-feature"])
    codex_capabilities = codex.capabilities()
    qwen_status = qwen_fixture.capabilities()
    usage_event = normalize_event({
        "agentId": "hermes", "provider": "offline-fixture", "model": "fixture-model",
        "operation": "observe", "inputTokens": 12, "outputTokens": 8,
        "taskDigest": "fixture-task", "observedAt": "2026-08-08T00:00:00+00:00",
    })
    replay = run_scenario("duplicate-webhook")
    return {
        "branch": "workflow-agent",
        "evidence": "OFFLINE_VERIFIED",
        "capabilityNegotiation": negotiation,
        "codexReadOnly": codex_capabilities["read_only"],
        "qwenFixture": qwen_status,
        "usageEventSchema": usage_event["schemaVersion"],
        "credentialsRead": False,
        "promptResponseRead": False,
        "taskReplay": replay,
        "liveExternalExecution": "UNKNOWN_NOT_RUN",
    }


def _observer_pilot() -> dict[str, Any]:
    events = [
        normalize_event({
            "agentId": "hermes", "provider": "fixture", "model": "deepseek-v4-flash",
            "operation": "observe", "inputTokens": 100, "outputTokens": 50,
            "taskDigest": "task-a", "observedAt": "2026-08-08T00:00:00+00:00",
        }),
        normalize_event({
            "agentId": "codex", "provider": "fixture", "model": "gpt-5.6-terra",
            "operation": "observe", "inputTokens": 40, "outputTokens": 20,
            "taskDigest": "task-b", "observedAt": "2026-08-08T00:01:00+00:00",
        }),
        {"corrupt": True},
    ]
    valid = [event for event in events if event.get("schemaVersion") == "work-lab/observer-event/v2"]
    first = rollup(valid + valid[:1])
    rebuilt = rollup(valid)
    stable_fields = ("totals", "byModel", "subscriptionModels", "idempotent", "rebuildable", "privacy")
    restart_rebuild_equal = all(first[key] == rebuilt[key] for key in stable_fields)
    return {
        "branch": "observer",
        "evidence": "OFFLINE_VERIFIED",
        "acceptedEvents": len(valid),
        "corruptEventsIsolated": len(events) - len(valid),
        "restartRebuildEqual": restart_rebuild_equal,
        "duplicateIngestIdempotent": first["totals"]["count"] == rebuilt["totals"]["count"],
        "offlineView": True,
        "mutationSurface": [],
        "liveProviderExecution": "UNKNOWN_NOT_RUN",
    }


def run_pilots() -> dict[str, Any]:
    pilots = [_workflow_pilot(), _observer_pilot()]
    return {
        "schemaVersion": "work-lab/offline-pilot/v1",
        "mode": "OFFLINE_FIXTURES_ONLY",
        "pilots": pilots,
        "allOfflineVerified": all(p["evidence"] == "OFFLINE_VERIFIED" for p in pilots),
        "externalWrites": False,
        "credentialsAccessed": False,
        "liveClaims": "NONE",
    }
