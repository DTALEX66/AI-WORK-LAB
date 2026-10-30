# SPDX-License-Identifier: MIT
"""V02: real loopback HTTP surface — health, projects, capabilities, boundaries."""
from __future__ import annotations


def test_health_is_real_service_metadata(server):
    status, body = server.client.get("/api/v1/health")
    assert status == 200
    assert body["service"] == "ai-work-lab"
    assert body["data_mode"] == "live"
    assert body["envelope"].endswith("v1-draft")


def test_projects_register_and_read_back_both_sources(server, tmp_path):
    work_root = tmp_path / "work-root"
    work_root.mkdir()
    status, work_project = server.client.post("/api/v1/projects", {
        "name": "演示工作项目", "source": "work", "root_path": str(work_root)})
    assert status == 201
    assert work_project["source"] == "work"

    status, design_project = server.client.post("/api/v1/projects", {
        "name": "演示设计项目", "source": "design"})
    assert status == 201

    status, listing = server.client.get("/api/v1/projects")
    assert status == 200
    sources = {p["source"] for p in listing["unified"]}
    assert sources == {"work", "design"}
    assert any(p["id"] == design_project["root_path"] for p in listing["design_runtime"])


def test_capabilities_are_honest_and_derived(server):
    status, body = server.client.get("/api/v1/capabilities")
    assert status == 200
    by_id = {c["capability_id"]: c for c in body["capabilities"]}
    # implemented + locally verified this batch
    assert by_id["core.tasks"]["can_invoke"] is True
    assert by_id["design.knowledge.search"]["can_invoke"] is True
    # retained but not host-verified: honest refusal with named reasons
    executors = by_id["work.executors"]
    assert executors["can_invoke"] is False
    assert any("qualification" in reason or "connection" in reason
               for reason in executors["unavailable_reasons"])
    # deferred surfaces keep their phase and never claim availability
    assert by_id["core.evolution"]["implementation"] == "DECLARED"
    assert by_id["core.evolution"]["can_invoke"] is False


def test_write_boundary_unknown_project_and_kind(server):
    status, body = server.client.post("/api/v1/tasks", {
        "project_id": "0" * 32, "kind": "work", "title": "x"})
    assert status == 404
    assert body["error"] == "PROJECT_NOT_FOUND"

    status, project = server.client.post("/api/v1/projects", {
        "name": "p", "source": "design"})
    status, body = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "chat", "title": "x"})
    assert status == 400
    assert body["error"].startswith("TASK_KIND_UNKNOWN")


def test_kernel_guards_apply_to_v1_routes(server):
    # wrong Host → the kernel refuses before any v1 logic runs
    status, body = server.client.get("/api/v1/health", host="evil.example:1")
    assert status == 403
    assert body["error"] == "HOST_DENIED"
    # missing token → 401
    status, body = server.client.get("/api/v1/health", token=None)
    assert status == 401
    assert body["error"] == "UNAUTHORIZED"
    # wrong token → 401
    status, body = server.client.get("/api/v1/health", token="f" * 64)
    assert status == 401
    # unknown route → 404 with the kernel's stable code
    status, body = server.client.get("/api/v1/nothing-here")
    assert status == 404
    assert body["error"] == "NOT_FOUND"


def test_design_domain_read_routes_answer_real_data(server):
    status, project = server.client.post("/api/v1/projects", {"name": "d", "source": "design"})
    assert status == 201
    design_project_id = project["root_path"]
    status, plans = server.client.get("/api/v1/design/plans?project_id=" + design_project_id)
    assert status == 200
    # an empty list is legal data; the route must say so, not fail
    assert isinstance(plans, dict)
    status, profiles = server.client.get("/api/v1/design/target-profiles")
    assert status == 200
    assert isinstance(profiles, dict)
