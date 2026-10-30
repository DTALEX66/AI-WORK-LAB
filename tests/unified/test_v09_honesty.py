# SPDX-License-Identifier: MIT
"""V09: unavailable executors, hosts and deferred capabilities answer honest
states; a simulated connection success cannot mint real qualification."""
from __future__ import annotations

import json

from backend.core.qualifications import probe_record


def _connection_rows(server) -> dict:
    status, body = server.client.get("/api/v1/connections")
    assert status == 200, body
    assert body["connections"]
    return {row["connection_id"]: row for row in body["connections"]}


def test_connections_never_claim_connected_without_a_probe(server):
    """The falsifiable version of the old same-source check.

    What used to sit here compared the route's hard-coded list against the string
    ``"CONNECTED"`` — a constant checked against a constant, so the assertion could
    never fail (audit category (c)).  The route now reads the qualification ledger,
    which means this test can move the ledger and watch the answer move with it.
    Every step below is a state the endpoint did not already know.
    """
    ledger = server.qualifications
    snapshot = (ledger.path.read_text(encoding="utf-8")
                if ledger.path.is_file() else json.dumps({"records": []}))
    version = server.api.candidate()
    # timestamps are second-resolution and ``latest_for`` picks the newest, so each
    # fixture step is stamped later than the one before it and the outcome never
    # depends on how long the test takes to run.
    stamps = iter(["2099-01-01T00:00:0" + str(step) + "+00:00" for step in range(1, 9)])

    def append(*, origin="live", connection="CONNECTED", digest=None, expires=None,
               outcome="VERIFIED"):
        row = probe_record(capability_id="work.executors", operation="executor.invoke",
                           scope="local_read", subject="work adapter registry",
                           version={"digest": digest or version["digest"],
                                    "files": version["files"]},
                           outcome=outcome, evidence_refs=["probe:work.executors/falsifier"],
                           detail="falsifier fixture written by test_v09",
                           data_origin=origin, connection=connection, ttl_seconds=900)
        row["observed_at"] = next(stamps)
        row["expires_at"] = expires or "2099-12-31T00:00:00+00:00"
        ledger.append(row)
        return row

    def restore():
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")

    # 0. baseline — nothing in this build records a connection, so the ledger's
    #    silence is reported as NOT_PROBED with a reason, never as a green default.
    baseline = _connection_rows(server)["work-adapters"]
    assert baseline["state"] == "NOT_PROBED", baseline
    assert baseline["evidence"] is None
    assert baseline["unavailable_reasons"], baseline
    # the deleted literal must not come back through any other door
    for row in _connection_rows(server).values():
        assert row["state"] != "CONNECTED_LOCAL", row
    assert set(_connection_rows(server)) == {"design-native-hosts", "design-comfy",
                                             "work-adapters"}

    # 1. a live record bound to THIS candidate that observed a connection flips it
    append()
    moved = _connection_rows(server)["work-adapters"]
    assert moved["state"] == "CONNECTED", moved
    assert moved["qualification"] == "VERIFIED", moved
    assert moved["evidence"]["candidate_digest"] == version["digest"], moved
    assert moved["evidence"]["data_origin"] == "live", moved
    # the other axes stay separate: a connection does not launder a PARTIAL
    # implementation or a NOT_GRANTED authorization into readiness
    assert any("implementation=PARTIAL" in reason for reason in moved["unavailable_reasons"]), moved
    assert any("authorization=NOT_GRANTED" in reason
               for reason in moved["unavailable_reasons"]), moved
    assert not any("qualification=" in reason for reason in moved["unavailable_reasons"]), moved

    # 2. the same claim from a synthetic probe does not earn it
    append(origin="test")
    synthetic = _connection_rows(server)["work-adapters"]
    assert synthetic["state"] == "NOT_PROBED", synthetic
    assert any("data_origin" in reason or "synthetic" in reason
               for reason in synthetic["unavailable_reasons"]), synthetic

    # 3. nor does a record written against a different candidate
    append(origin="live", digest="f" * 64)
    foreign = _connection_rows(server)["work-adapters"]
    assert foreign["state"] == "NOT_PROBED", foreign
    assert foreign["qualification"] == "EXPIRED", foreign
    assert any("candidate" in reason for reason in foreign["unavailable_reasons"]), foreign

    # 4. nor one whose freshness window has passed
    append(expires="2020-01-01T00:00:00+00:00")
    stale = _connection_rows(server)["work-adapters"]
    assert stale["state"] == "NOT_PROBED", stale
    assert any("freshness window" in reason for reason in stale["unavailable_reasons"]), stale

    # 5. a FAILED observation is not a connection either
    append(outcome="FAILED")
    failed = _connection_rows(server)["work-adapters"]
    assert failed["state"] == "NOT_PROBED", failed
    assert failed["qualification"] == "FAILED", failed

    # 6. take the records away and the surface goes back to NOT_PROBED by itself
    restore()
    reverted = _connection_rows(server)["work-adapters"]
    assert reverted["state"] == "NOT_PROBED", reverted
    assert reverted["evidence"] is None, reverted
    assert reverted["unavailable_reasons"], reverted

    # 7. and there is still no route that writes a connection from the client side
    status, body = server.client.post("/api/v1/connections", {"state": "CONNECTED"})
    assert status == 404  # no such route exists
    assert _connection_rows(server)["work-adapters"]["state"] == "NOT_PROBED"


def test_tool_state_names_the_record_that_produced_it(server):
    """Every tool row is traceable: a value is either a record's own connection
    axis or NOT_PROBED with the reason the ledger is silent."""
    status, body = server.client.get("/api/v1/tools")
    assert status == 200, body
    version = server.api.candidate()["digest"]
    records = server.qualifications.records()
    for row in body["tools"]:
        assert row["state"] != "CONNECTED_LOCAL", row
        assert row["state"] in ("NOT_REQUIRED", "CONNECTED", "NOT_PROBED", "DISCONNECTED"), row
        candidates = [record for record in records
                      if record.get("capability_id") == row["bound_capability"]
                      and record.get("operation") == row["operation"]]
        if row["state"] == "NOT_PROBED":
            assert row["unavailable_reasons"], row
            continue
        assert row["evidence"], row
        assert row["evidence"]["candidate_digest"] == version, row
        assert row["evidence"]["data_origin"] == "live", row
        assert any(record.get("connection") == row["state"] for record in candidates), row
    assert body["state_rule"]


def test_unavailable_capabilities_carry_reasons(server):
    status, body = server.client.get("/api/v1/capabilities")
    assert status == 200
    for capability in body["capabilities"]:
        if capability["can_invoke"] is False:
            assert capability["unavailable_reasons"], capability["capability_id"]
        if capability["implementation"] == "DEFERRED":
            assert capability["phase"].startswith("P"), capability["capability_id"]


def test_improvements_answer_contract_only(server):
    status, body = server.client.get("/api/v1/improvements")
    assert status == 200
    assert body["status"] == "CONTRACT_ONLY"
    assert body["activation_state"] == "UNAVAILABLE"


def test_demo_data_origin_cannot_grant_live_qualification(server):
    status, project = server.client.post("/api/v1/projects", {"name": "d", "source": "design"})
    assert status == 201
    # a task created with demo origin is stored as demo…
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "演示任务",
        "acceptance": {"data_origin": "demo"}})
    assert status == 201
    assert task["data_origin"] == "demo"
    # …and the capability catalog still reports live entries only — a demo task
    # record never appears as a live qualification anywhere
    status, caps = server.client.get("/api/v1/capabilities")
    for capability in caps["capabilities"]:
        assert capability["data_origin"] == "live"
