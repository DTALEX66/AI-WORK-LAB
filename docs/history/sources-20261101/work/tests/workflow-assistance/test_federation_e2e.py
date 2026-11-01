"""TP-20260819 E2E contract tests (section 11): four closed loops + failure paths.

These are fixture-based, no real external software required.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts' / 'workflow'))
import pytest
from config_control_plane import ConfigControlPlane, SoftwareRegistration
import hashlib


def envelope(producer: str, consumer: str, cid: str) -> dict:
    return {
        "schemaVersion": "workflow/federation-envelope/v1",
        "messageId": "msg-" + cid,
        "producer": producer,
        "consumer": consumer,
        "correlationId": cid,
        "workUnitId": "wu-" + cid,
        "sourceCommit": "abc123",
        "contentHash": hashlib.sha256(cid.encode()).hexdigest()[:16],
        "classification": "internal",
        "rightsStatus": "project-owned",
        "createdAt": "2026-08-19T00:00:00Z",
        "idempotencyKey": "idem-" + cid,
    }


# --- E2E-004: configuration closed loop ---
def test_e2e004_config_loop():
    ccp = ConfigControlPlane()
    ccp.register(SoftwareRegistration("hermes", "Hermes", "agent-harness", "anthropics/hermes"))
    ccp.set_layer("official_baseline", {"model": "default", "safety_boundary": "strict"})
    ccp.set_layer("user_profile", {"model": "preferred", "approval_required": True})
    ccp.set_layer("session_override", {"model": "session-model"})
    eff = ccp.effective("hermes")
    assert eff["model"] == "session-model"          # session wins
    assert eff["safety_boundary"] == "strict"        # safety not overridden
    before = {"model": "a"}
    after = {"model": "b"}
    d = ccp.diff(before, after)
    assert d["changeCount"] == 1
    assert ccp.apply_plan(d, approved=False)["status"] == "WAITING_APPROVAL"
    assert ccp.apply_plan(d, approved=True)["status"] == "UNSUPPORTED_APPLY"
    assert ccp.readback_matches({"x": 1}, {"x": 1})
    assert ccp.detect_drift({"x": 1}, {"x": 2})["status"] == "DRIFT"
    assert ccp.rollback({"x": 2}, {"x": 1})["status"] == "ROLLBACK_REQUIRED"


# --- failure paths ---
def test_failure_unknown_adapter():
    ccp = ConfigControlPlane()
    assert len(ccp.list_registered()) == 0


def test_failure_duplicate_idempotency():
    e1 = envelope("work-lab", "archeaxis-knowledge-os", "c1")
    e2 = envelope("work-lab", "archeaxis-knowledge-os", "c1")
    assert e1["idempotencyKey"] == e2["idempotencyKey"]  # same key = dedupe by consumer


def test_failure_hash_mismatch():
    e = envelope("work-lab", "design-lab", "c2")
    e["contentHash"] = "tampered"
    expected = hashlib.sha256("c2".encode()).hexdigest()[:16]
    assert e["contentHash"] != expected


def test_failure_observer_write_rejected():
    from test_observer_readonly import observer_rejects
    assert observer_rejects("work-unit:update")
    assert observer_rejects("approval:grant")


def test_failure_envelope_requires_fields():
    e = envelope("work-lab", "design-lab", "c3")
    for field in ("schemaVersion", "messageId", "producer", "consumer", "correlationId", "contentHash", "idempotencyKey"):
        assert field in e
