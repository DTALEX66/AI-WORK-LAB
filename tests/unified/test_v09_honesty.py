# SPDX-License-Identifier: MIT
"""V09: unavailable executors, hosts and deferred capabilities answer honest
states; a simulated connection success cannot mint real qualification."""
from __future__ import annotations


def test_connections_never_claim_connected_without_a_probe(server):
    status, body = server.client.get("/api/v1/connections")
    assert status == 200
    assert body["connections"]
    for connection in body["connections"]:
        assert connection["state"] != "CONNECTED"
    # there is no route that flips a connection to CONNECTED — a client cannot
    # assert its way into qualification
    status, body = server.client.post("/api/v1/connections", {"state": "CONNECTED"})
    assert status == 404  # no such route exists


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
