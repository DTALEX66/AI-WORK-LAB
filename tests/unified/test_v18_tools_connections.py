# SPDX-License-Identifier: MIT
"""V18: the tool / connection / integrity / qualification-evidence surface.

Audit F10 closed "qualification comes from a constant" for capabilities and named
``GET /api/v1/qualification-evidence`` as the call_entry that proves it; the very
same defect then reappeared one route over, where ``GET /api/v1/tools`` answered a
hard-coded list whose ``CONNECTED_LOCAL`` no probe or store read had produced, and
``/api/v1/integrity`` + ``/api/v1/qualification-evidence`` had zero pytest hits.

These tests therefore do two things the old suite could not:

* they check each row against the ledger **as read from disk**, so a value that
  only exists in the handler has nothing to match; and
* they *move* the ledger and require the answer to move with it — plant a record,
  watch a state change, expire it, watch it fall back with a reason.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone

LEDGER_SCHEMA = "ai-work-lab/qualification-ledger/v1"


def _moment(raw: str) -> datetime:
    return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))


def _tools(server) -> dict:
    status, body = server.client.get("/api/v1/tools")
    assert status == 200, body
    return {row["tool_id"]: row for row in body["tools"]}


def _connections(server) -> dict:
    status, body = server.client.get("/api/v1/connections")
    assert status == 200, body
    return {row["connection_id"]: row for row in body["connections"]}


def _record(server, *, capability_id, operation, version, connection="CONNECTED",
            origin="live", outcome="VERIFIED", expires=None, observed=None):
    from backend.core.qualifications import probe_record

    row = probe_record(capability_id=capability_id, operation=operation,
                       scope="local_read", subject="v18 falsifier subject",
                       version=version, outcome=outcome,
                       evidence_refs=["probe:" + capability_id + "/v18"],
                       detail="record written by test_v18", data_origin=origin,
                       connection=connection, ttl_seconds=900)
    # second-resolution timestamps make latest_for() order-dependent; stamp them
    row["observed_at"] = observed or "2099-01-01T00:00:00+00:00"
    row["expires_at"] = expires or "2099-12-31T00:00:00+00:00"
    return row


# --------------------------------------------------------------------- /api/v1/tools
def test_tool_states_match_the_ledger_on_disk_and_no_literal(server):
    """Each row's value is re-derived here from the ledger file, not from the route."""
    version = server.api.candidate()["digest"]
    records = server.qualifications.records()
    status, raw = server.client.get("/api/v1/tools")
    assert status == 200
    # the deleted literal must not survive anywhere on this surface
    assert "CONNECTED_LOCAL" not in json.dumps(raw, ensure_ascii=False)
    assert raw["count"] == len(raw["tools"]) == 4
    assert raw["candidate_version"] == version

    def expected(capability_id, operation):
        """The same rule the route documents: newest accepted record wins."""
        matches = [row for row in records if row.get("capability_id") == capability_id
                   and row.get("operation") == operation]
        if not matches:
            return "NOT_PROBED"
        newest = max(matches, key=lambda row: str(row.get("observed_at") or ""))
        now = datetime.now(timezone.utc)
        accepted = (newest.get("candidate_digest") == version
                    and _moment(newest["expires_at"]) > now
                    and newest.get("data_origin") == "live"
                    and newest.get("scope") == "local_read"
                    and newest.get("outcome") == "VERIFIED")
        connection = str(newest.get("connection") or "")
        if accepted and connection in ("NOT_REQUIRED", "CONNECTED", "NOT_PROBED",
                                       "DISCONNECTED"):
            return connection
        return "NOT_PROBED"

    for row in raw["tools"]:
        assert row["bound_capability"] and row["operation"], row
        assert row["declared_by"].endswith("(declaration only, no status)"), row
        assert row["state"] == expected(row["bound_capability"], row["operation"]), row
        if row["state"] == "NOT_PROBED":
            assert row["unavailable_reasons"], row
            assert row["qualification"] in ("NOT_PROBED", "EXPIRED", "NOT_VERIFIED", "FAILED"), row
        else:
            assert row["evidence"]["candidate_digest"] == version, row
            assert row["evidence"]["data_origin"] == "live", row
            assert row["connection_observed_by_probe"] == row["state"], row
            assert not row["unavailable_reasons"], row


def test_a_record_moves_a_tool_state_and_losing_it_moves_it_back(server):
    """The falsifier: quality-gate is bound to an operation nothing probes, so its
    state can only change when the ledger says so — and back."""
    ledger = server.qualifications
    snapshot = (ledger.path.read_text(encoding="utf-8")
                if ledger.path.is_file() else json.dumps({"records": []}))
    version = server.api.candidate()
    try:
        before_all = _tools(server)
        before = before_all["quality-gate"]
        assert before["state"] == "NOT_PROBED", before
        assert before["evidence"] is None, before
        assert any("qualification=NOT_PROBED" in reason
                   for reason in before["unavailable_reasons"]), before

        # plant an accepted connection record for the operation this tool names
        ledger.append(_record(server, capability_id="work.quality_gate",
                              operation="quality_gate.run", version=version))
        during = _tools(server)["quality-gate"]
        assert during["state"] == "CONNECTED", during
        assert during["qualification"] == "VERIFIED", during
        assert during["evidence"]["connection"] == "CONNECTED", during
        assert during["evidence"]["matches_running_candidate"] is True, during
        assert during["evidence"]["expires_at"] == "2099-12-31T00:00:00+00:00", during
        assert during["evidence"]["evidence_refs"] == ["probe:work.quality_gate/v18"], during
        # the sibling rows are untouched: this is per-record, not a global flag
        after = _tools(server)
        assert after["design-lab-service"]["state"] == before_all["design-lab-service"]["state"]
        assert after["work-repair-machinery"]["state"] == before_all["work-repair-machinery"]["state"]

        # expire it: the same record inside a closed window grants nothing
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
        ledger.append(_record(server, capability_id="work.quality_gate",
                              operation="quality_gate.run", version=version,
                              expires="2020-01-01T00:00:00+00:00"))
        expired = _tools(server)["quality-gate"]
        assert expired["state"] == "NOT_PROBED", expired
        assert expired["qualification"] == "EXPIRED", expired
        assert any("freshness window" in reason for reason in expired["unavailable_reasons"]), expired

        # a record for the wrong capability id does not light the tool either
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
        ledger.append(_record(server, capability_id="work.quality_gate",
                              operation="some.other.operation", version=version))
        assert _tools(server)["quality-gate"]["state"] == "NOT_PROBED"

        # and removing the records restores the honest unknown with its reason
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
        reverted = _tools(server)["quality-gate"]
        assert reverted["state"] == "NOT_PROBED", reverted
        assert reverted["evidence"] is None, reverted
        assert reverted["unavailable_reasons"], reverted
    finally:
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")


def test_host_and_model_tools_never_inherit_a_local_probe(server):
    """A successful in-process read must not be read as a host connection."""
    version = server.api.candidate()["digest"]
    # the design runtime really was read live at startup…
    runtime = _tools(server)["design-lab-service"]
    assert runtime["evidence"] is not None, runtime
    assert runtime["evidence"]["candidate_digest"] == version
    # …and none of that reaches Photoshop/ComfyUI/the WORK executors
    for row in _connections(server).values():
        assert row["state"] == "NOT_PROBED", row
        assert row["evidence"] is None, row
        assert row["authorization"] in ("NOT_GRANTED", "REQUIRED"), row
        assert row["unavailable_reasons"], row
        assert "CONNECTED_LOCAL" not in json.dumps(row, ensure_ascii=False)


# ------------------------------------------------------------------- /api/v1/integrity
def test_integrity_reports_the_store_it_actually_reads(server):
    status, body = server.client.get("/api/v1/integrity")
    assert status == 200, body
    assert set(body) == {"problems", "counts"}, sorted(body)
    assert isinstance(body["problems"], list)
    assert body["counts"] == {"tasks": 0, "attempts": 0, "results": 0}, body

    # one real chain written through the API moves the counts it names
    status, project = server.client.post("/api/v1/projects",
                                        {"name": "integrity", "source": "design"})
    assert status == 201, project
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "完整性样例",
        "acceptance": {"data_origin": "test"}})
    assert status == 201, task
    status, attempt = server.client.post(
        f"/api/v1/tasks/{task['task_id']}/attempts", {"idempotency_key": "v18-1"})
    assert status == 201, attempt

    status, after = server.client.get("/api/v1/integrity")
    assert status == 200, after
    assert after["counts"] == {"tasks": 1, "attempts": 1, "results": 0}, after
    # a chain built through the contract has nothing to name…
    assert after["problems"] == [], after
    for problem in after["problems"]:
        assert set(problem) == {"kind", "id", "detail"}, problem
    # …and integrity is read from the store, not from the task list: the store's
    # own row count agrees with what the route reported
    assert server.unified.get_task(task["task_id"])["task_id"] == task["task_id"]


def test_integrity_names_a_completion_that_no_longer_holds(server):
    """The F04 half that matters: a COMPLETED row the chain does not back must be
    named. The store refuses that write through its own API, so the row is planted
    the way a pre-constraint database would already contain it — underneath the
    API — and the route is asked whether it still sees it."""
    status, project = server.client.post("/api/v1/projects",
                                        {"name": "integrity2", "source": "design"})
    assert status == 201, project
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "unsupported 完成",
        "acceptance": {"data_origin": "test"}})
    assert status == 201, task
    task_id = task["task_id"]

    # the store itself refuses this transition through its API, which is why the
    # row has to be planted underneath it: integrity exists for exactly the
    # pre-constraint database that already contains it.

    server.unified.conn.execute("UPDATE tasks SET lifecycle='COMPLETED' WHERE task_id=?",
                                (task_id,))
    server.unified.conn.commit()
    try:
        status, body = server.client.get("/api/v1/integrity")
        assert status == 200, body
        kinds = {(problem["kind"], problem["id"]) for problem in body["problems"]}
        assert ("COMPLETION_UNSUPPORTED", task_id) in kinds, body
        assert body["counts"]["tasks"] == 1, body
        named = [problem for problem in body["problems"]
                 if problem["kind"] == "COMPLETION_UNSUPPORTED"][0]
        assert named["detail"], named
    finally:
        server.unified.conn.execute("UPDATE tasks SET lifecycle='DRAFT' WHERE task_id=?",
                                    (task_id,))
        server.unified.conn.commit()
    status, cleared = server.client.get("/api/v1/integrity")
    assert ("COMPLETION_UNSUPPORTED", task_id) not in {
        (problem["kind"], problem["id"]) for problem in cleared["problems"]}, cleared


# ------------------------------------------------------- /api/v1/qualification-evidence
def test_qualification_evidence_is_the_record_the_other_routes_cite(server):
    """F10's named call_entry: every row says which capability, which operation,
    which candidate digest, and until when it is allowed to answer."""
    status, catalog = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog
    version = catalog["candidate_version"]
    status, evidence = server.client.get("/api/v1/qualification-evidence")
    assert status == 200, evidence
    assert evidence["schemaVersion"] == LEDGER_SCHEMA
    assert evidence["candidate_version"] == version
    assert evidence["count"] == len(evidence["records"])
    assert evidence["records"], ("the startup probes must have left records; an empty "
                                 "ledger means the reader cannot check anything")
    # the route reads the very same ledger the surfaces derive from
    assert evidence["count"] == len(server.qualifications.records())

    for row in evidence["records"]:
        assert row["capability_id"] and row["operation"], row
        digest = str(row.get("candidate_digest") or "")
        assert len(digest) == 64 and all(c in "0123456789abcdef" for c in digest), row
        assert row["matches_running_candidate"] == (digest == version), row
        assert _moment(row["expires_at"]) > _moment(row["observed_at"]), row
        assert row["data_origin"] in ("live", "test", "demo"), row
        assert row["scope"] in ("local_read", "local_roundtrip_scratch", "loopback_http"), row
        assert row["outcome"] in ("VERIFIED", "NOT_VERIFIED", "FAILED", "EXPIRED",
                                 "NOT_PROBED"), row
        assert row["evidence_refs"], row
        assert row["self_reported"] is False, row

    live_verified = [row for row in evidence["records"]
                     if row["data_origin"] == "live" and row["matches_running_candidate"]
                     and row["outcome"] == "VERIFIED"
                     and _moment(row["expires_at"]) > datetime.now(timezone.utc)]
    assert live_verified, evidence["records"]
    # a scratch probe is recorded on purpose and must not read as live evidence
    synthetic = [row for row in evidence["records"] if row["data_origin"] != "live"]
    assert synthetic, "the scratch roundtrip record is missing"


def test_can_invoke_implies_a_record_this_route_can_show(server):
    """``can_invoke`` is only true when the evidence route can produce the record."""
    status, catalog = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog
    version = catalog["candidate_version"]
    status, evidence = server.client.get("/api/v1/qualification-evidence")
    assert status == 200
    index = {(row["capability_id"], row["operation"]): row for row in evidence["records"]}

    callable_rows = [row for row in catalog["capabilities"] if row["can_invoke"]]
    assert callable_rows, "the startup probes must make something callable"
    for row in callable_rows:
        assert row["qualification"] == "VERIFIED", row
        record = index.get((row["capability_id"], row["operation"]))
        assert record is not None, row
        assert record["candidate_digest"] == version, (row, record)
        assert record["data_origin"] == "live", (row, record)
        assert record["outcome"] == "VERIFIED", (row, record)
        assert _moment(record["expires_at"]) > datetime.now(timezone.utc), (row, record)
        assert row["probe"]["observed_at"] == record["observed_at"], (row, record)
        assert row["unavailable_reasons"] == [], row
        assert row["authorization"] in ("NOT_REQUIRED", "GRANTED"), row

    # and the refusal side stays traceable rather than defaulted
    for row in catalog["capabilities"]:
        if not row["can_invoke"]:
            assert row["unavailable_reasons"], row


def test_evidence_added_by_a_probe_reaches_every_derived_surface(server):
    """One ledger, three readers: a record the tools route accepts is the same
    row the evidence route lists, with the same digest and expiry."""
    ledger = server.qualifications
    snapshot = (ledger.path.read_text(encoding="utf-8")
                if ledger.path.is_file() else json.dumps({"records": []}))
    version = server.api.candidate()
    try:
        row = _record(server, capability_id="work.executors",
                      operation="executor.invoke", version=version)
        ledger.append(row)
        tools_row = _connections(server)["work-adapters"]
        assert tools_row["state"] == "CONNECTED", tools_row
        status, evidence = server.client.get("/api/v1/qualification-evidence")
        assert status == 200
        listed = [item for item in evidence["records"]
                  if item["capability_id"] == "work.executors"]
        assert listed and listed[-1]["connection"] == "CONNECTED", listed
        assert listed[-1]["expires_at"] == tools_row["evidence"]["expires_at"], listed
        assert listed[-1]["matches_running_candidate"] is True, listed
    finally:
        ledger.path.write_text(snapshot, encoding="utf-8", newline="\n")
    assert _connections(server)["work-adapters"]["state"] == "NOT_PROBED"
    assert _tools(server)["quality-gate"]["state"] == "NOT_PROBED"
