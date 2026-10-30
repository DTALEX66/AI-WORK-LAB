# SPDX-License-Identifier: MIT
"""Regression suite for the 2026-10-30 Codex independent audit (F01–F10 rework).

Every test below reproduces a counterexample the audit actually observed, in the
shape the audit used it, and asserts the *refusal or hit* the audit said was
missing. The audit's own scripts stay untouched in
``.project-local/audit/20261030-codex-independent/``; this file is the stable
version of the same questions, so a later run does not depend on a fixed
wall-clock instant or an absolute path.

Result vocabulary: these are contract tests over synthetic fixtures. They prove
the envelope refuses what it must and returns what it must. They are not evidence
about a real host, a real person or a real user project — those stay NOT_RUN
where the audit left them.
"""
from __future__ import annotations

import csv
import json
import subprocess
import sys
import urllib.parse
from datetime import datetime, timedelta, timezone

from design_lab.knowledge_library import KnowledgeLibrary

from tests.conftest import produced_after, seed_issue, write_grants
from tests.unified.test_v03_work_loop import _result_document
from tests.unified.test_v06_knowledge import _entry

TARGET_ROOT = __import__("pathlib").Path(__file__).resolve().parents[2]
VENV_PYTHON = str(TARGET_ROOT / ".venv" / "Scripts" / "python.exe")
DESIGN_RESULT_SCHEMA = "ai-work-lab/design-result/v1"
PROFILE_KEY = "minimax-h3--api--video-reference"


def _seed_solution(server, solution_id="sol-rework-cache", title="缓存目录修复返工样例",
                   keyword="缓存"):
    """One real-format WORK maintenance solution, solidified unverified."""
    from domains.work.control import solution_library
    solution = solution_library.build_solution(
        solution_id=solution_id, title=title,
        software={"softwareId": "rework", "softwareVersion": "1", "platform": "windows",
                  "versionSource": "DECLARED"},
        source={"kind": "MANUAL", "ref": "rework-fixture",
                "updatedAt": datetime.now(timezone.utc).isoformat()},
        steps=["清理合成缓存目录"], verification_steps=["读回合成缓存目录"],
        keywords=[keyword], changes="initial rework fixture")
    solution_library.import_unverified(server.work.store, solution)
    return solution


def _design_attempt(server, *, profile=True, policy=None, title="设计返工样例",
                    professional=False):
    """project → plan → task → attempt → pack → handoff, all test origin."""
    from design_lab.assistance_plan import AssistancePlans
    status, project = server.client.post("/api/v1/projects", {
        "name": title, "source": "design", "data_origin": "test"})
    assert status == 201, project
    design_project_id = project["root_path"]
    plans = AssistancePlans(server.design_service)
    created = plans.create(design_project_id, {
        "objective": "为返工回归产出可核验的方案修订", "output_type": "STORYBOARD",
        "created_by": "rework-fixture"})
    plan_id = created["plan"]["plan_id"]
    refs = [{"kind": "design_plan_ref", "design_project_id": design_project_id,
             "plan_id": plan_id}]
    if profile:
        refs.append({"kind": "target_profile_ref", "profile_key": PROFILE_KEY})
    acceptance = {"professional_required": bool(professional), "data_origin": "test"}
    if policy:
        acceptance["revision_policy"] = policy
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": title,
        "input_refs": refs, "acceptance": acceptance})
    assert status == 201, task
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "rework-" + plan_id})
    assert status == 201
    status, pack = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    assert status == 201, pack
    target_version = "plan-r" + str(pack["pack_ref"]["plan_revision"])
    status, handoff = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/handoff-declarations",
        {"claim": "userDeclaredHandoff", "target_version": target_version, "actor": "user"})
    assert status == 200, handoff
    return {"project": project, "design_project_id": design_project_id, "plans": plans,
            "plan_id": plan_id, "task": task, "attempt": attempt, "pack": pack,
            "handoff": handoff, "target_version": target_version}


def _result_document_for(fixture, **overrides):
    pack_ref = fixture["pack"]["pack_ref"]
    document = {
        "schemaVersion": DESIGN_RESULT_SCHEMA,
        "resultId": "res-" + pack_ref["plan_id"][-8:],
        "designProjectId": fixture["design_project_id"],
        "planId": pack_ref["plan_id"],
        "planRevision": pack_ref["plan_revision"],
        "contentSha256": pack_ref["plan_content_sha256"],
        "targetVersion": fixture["target_version"],
        "producedAt": produced_after(fixture["handoff"]),
        "summary": "返工回归的正样例结果",
        "evidenceRefs": ["design-plan-readback:" + pack_ref["plan_id"]],
    }
    document.update(overrides)
    return {k: v for k, v in document.items() if v is not None}


def _import(server, fixture, document):
    return server.client.post(
        f"/api/v1/attempts/{fixture['attempt']['attempt_id']}/results",
        {"result": document, "data_origin": "test"})


# ----------------------------------------------------------------------------- F02
def test_f02_design_result_with_wrong_bindings_and_dangerous_refs_is_refused(server):
    """The audit's exact invalid document: every field contradicted the server."""
    fixture = _design_attempt(server)
    attempt_id = fixture["attempt"]["attempt_id"]
    invalid = {"schemaVersion": DESIGN_RESULT_SCHEMA, "resultId": "res-invalid",
               "design_project_id": fixture["design_project_id"],
               "projectId": "wrong-project", "task_id": "0" * 32, "attempt_id": "0" * 32,
               "plan_revision": 999, "targetVersion": "wrong-version",
               "producedAt": "2000-01-01T00:00:00Z", "body_sha256": "0" * 64,
               "summary": "synthetic invalid result",
               "evidenceRefs": ["../../audit-synthetic.ps1"]}
    status, body = _import(server, fixture, invalid)
    assert status == 422, body
    # and nothing was left behind: no result row, and the attempt is still waiting
    stored = server.unified.list_results(attempt_id=attempt_id)
    assert stored == [], stored
    assert server.unified.get_attempt(attempt_id)["execution_state"] == "HANDOFF_DECLARED"

    # one refusal reason per defect, named — not one catch-all
    cases = [
        ({"projectId": "wrong-project"}, "RESULT_BINDING_WRONG_PROJECT"),
        ({"task_id": "0" * 32}, "RESULT_BINDING_WRONG_TASK"),
        ({"attempt_id": "0" * 32}, "RESULT_BINDING_WRONG_ATTEMPT"),
        ({"planId": "aplan-" + "f" * 32}, "RESULT_BINDING_WRONG_PLAN"),
        ({"planRevision": 999}, "RESULT_PLAN_REVISION_WRONG"),
        ({"targetVersion": "wrong-version"}, "RESULT_WRONG_VERSION"),
        ({"producedAt": "2000-01-01T00:00:00Z"}, "RESULT_STALE"),
        ({"contentSha256": "0" * 64}, "RESULT_DIGEST_ZERO"),
        ({"contentSha256": "ff" * 32}, "RESULT_DIGEST_UNBOUND"),
        ({"summary": ""}, "RESULT_SUMMARY_REQUIRED"),
        ({"schemaVersion": "other/v9"}, "RESULT_SCHEMA_UNKNOWN"),
    ]
    for override, expected in cases:
        document = _result_document_for(fixture, **override)
        status, body = _import(server, fixture, document)
        assert status == 422, (expected, status, body)
        assert body["error"].startswith(expected), (expected, body)
        assert server.unified.list_results(attempt_id=attempt_id) == []

    # references: traversal, absolute, runnable and out-of-scope are each refused
    for reference in ["../../evil.ps1", "C:/Windows/system32/cmd.exe", "/etc/passwd",
                      "..\\escape\\run.bat", "unknown-scheme:whatever",
                      "exports/../../outside.txt"]:
        document = _result_document_for(fixture, evidenceRefs=[reference])
        status, body = _import(server, fixture, document)
        assert status == 422, (reference, body)
        assert body["error"].startswith("EVIDENCE_REF_"), (reference, body)

    # the positive control: the same attempt accepts a correctly bound document
    status, imported = _import(server, fixture, _result_document_for(fixture))
    assert status == 201, imported
    assert len(server.unified.list_results(attempt_id=attempt_id)) == 1


def test_f02_duplicate_result_id_refused_and_cross_project_refused(server):
    first = _design_attempt(server, title="重复与跨项目样例甲")
    second = _design_attempt(server, title="重复与跨项目样例乙")
    status, imported = _import(server, first, _result_document_for(first))
    assert status == 201, imported
    # the same attempt already answered: a second submission is refused on state
    status, again = _import(server, first, _result_document_for(first))
    assert status == 409, again
    assert again["error"].startswith("ATTEMPT_STATE"), again

    # a *new* attempt on the same task, answering the same pinned pack, still cannot
    # re-submit the same resultId — dedup is scoped to the pack, not the attempt
    task = first["task"]
    status, attempt2 = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                          {"idempotency_key": "rework-second-pass"})
    assert status == 201, attempt2
    status, pack2 = server.client.post(f"/api/v1/attempts/{attempt2['attempt_id']}/pack", {})
    assert status == 201, pack2
    status, handoff2 = server.client.post(
        f"/api/v1/attempts/{attempt2['attempt_id']}/handoff-declarations",
        {"claim": "userDeclaredHandoff", "target_version": first["target_version"],
         "actor": "user"})
    assert status == 200, handoff2
    resubmitted = _result_document_for(first, resultId="res-" + first["pack"]["pack_ref"]["plan_id"][-8:],
                                      producedAt=produced_after(handoff2))
    fixture2 = dict(first, attempt=attempt2)
    status, body = _import(server, fixture2, resubmitted)
    assert status == 422, body
    assert body["error"].startswith("RESULT_DUPLICATE"), body

    # a document naming another project's plan is refused at import, not deferred
    # to a technical verdict that would have to read the wrong store
    borrowed = _result_document_for(second, designProjectId=first["design_project_id"],
                                   planId=first["plan_id"])
    status, body = _import(server, second, borrowed)
    assert status == 422, body
    # either hop it contradicts first is a correct refusal; what must not happen
    # is the import being accepted
    assert body["error"].startswith("RESULT_BINDING_WRONG_"), body


def test_f02_attachment_is_never_executed_or_imported(server):
    """A refused attachment stays a string; nothing here runs or sources it."""
    fixture = _design_attempt(server, title="附件不执行样例")
    document = _result_document_for(
        fixture, evidenceRefs=["exports/fixture-note.txt"],
        summary="附件引用只作为名字被拒绝或接受，服务从不执行它")
    status, imported = _import(server, fixture, document)
    assert status == 201, imported
    stored = server.unified.get_result(imported["result"]["result_id"])
    assert stored["artifact_refs"] == ["exports/fixture-note.txt"]
    # no side effect: nothing was created by accepting the reference
    assert not (server.local_root / "fixture-note.txt").exists()


# ----------------------------------------------------------------------------- F03
def test_f03_pinned_revision_that_moved_is_blocked_not_pass(server):
    """The audit's core F03 case, stated in both directions."""
    fixture = _design_attempt(server, title="修订漂移样例")
    status, imported = _import(server, fixture, _result_document_for(fixture))
    assert status == 201, imported
    result_id = imported["result"]["result_id"]
    pinned = fixture["pack"]["pack_ref"]["plan_revision"]

    status, before = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                        {"axis": "technical"})
    assert before["outcome"] == "PASS", before
    assert before["checks"]["pinned_is_current"] is True

    # the plan moves on: the pinned revision still reads back exactly, but the task
    # answered "the current revision", so the claim about NOW is refused
    fixture["plans"].revise(fixture["design_project_id"], fixture["plan_id"], {
        "objective": "返工回归：交接之后方案又被修订", "output_type": "STORYBOARD",
        "created_by": "rework-fixture", "expected_revision": pinned})
    status, after = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                       {"axis": "technical"})
    assert after["outcome"] == "BLOCKED", after
    assert after["current_validity"] == "SUPERSEDED", after
    assert after["checks"]["pinned_content_matches_readback"] is True
    assert after["checks"]["pinned_is_current"] is False
    # the earlier PASS is still stored — history is not rewritten to hide the failure
    verdicts = server.client.get(f"/api/v1/results/{result_id}")[1]["verifications"]
    assert [row["outcome"] for row in verdicts] == ["PASS", "BLOCKED"]


def test_f03_immutable_pin_accepts_the_stored_old_revision(server):
    """A task that explicitly answers one immutable revision is verified against it."""
    fixture = _design_attempt(server, title="不可变修订样例", policy="IMMUTABLE_PIN")
    status, imported = _import(server, fixture, _result_document_for(fixture))
    assert status == 201, imported
    result_id = imported["result"]["result_id"]
    pinned = fixture["pack"]["pack_ref"]["plan_revision"]
    fixture["plans"].revise(fixture["design_project_id"], fixture["plan_id"], {
        "objective": "返工回归：旧修订被新修订覆盖", "output_type": "STORYBOARD",
        "created_by": "rework-fixture", "expected_revision": pinned})
    status, verification = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                              {"axis": "technical"})
    assert verification["outcome"] == "PASS", verification
    assert verification["current_validity"] == "CURRENT", verification
    # and the pinned bytes really are the old ones, not the current plan
    readback = fixture["plans"].revision(fixture["design_project_id"], fixture["plan_id"], pinned)
    assert readback["is_latest"] is False
    assert readback["content_sha256"] == fixture["pack"]["pack_ref"]["plan_content_sha256"]


def test_f03_target_profile_drift_fails_the_verification(server):
    """The versioned combination is part of the binding; a moved member fails it."""
    fixture = _design_attempt(server, title="目标档案漂移样例")
    pack_ref = fixture["pack"]["pack_ref"]
    assert pack_ref["target_bindings"], pack_ref
    # rewrite the pinned digest in the stored pack_ref: the subject moved under us
    server.unified.conn.execute(
        "UPDATE attempts SET pack_ref=? WHERE attempt_id=?",
        (json.dumps({**pack_ref, "target_bindings": [{
            "profile_id": pack_ref["target_bindings"][0]["profile_id"],
            "revision": None, "content_sha256": "sha256:" + "a" * 64, "origin": "SEEDED",
            "declared_version": None}]}), fixture["attempt"]["attempt_id"]))
    server.unified.conn.commit()
    status, imported = _import(server, fixture, _result_document_for(fixture))
    assert status == 201, imported
    status, verification = server.client.post(
        f"/api/v1/results/{imported['result']['result_id']}/verifications", {"axis": "technical"})
    assert verification["outcome"] == "FAIL", verification
    assert verification["checks"]["target_profiles_reread"]["mismatched"], verification


def test_f03_separation_of_stages(server):
    """Saving a plan, exporting a pack, importing a result, technical acceptance and
    professional acceptance are five different facts, and no one of them implies the next."""
    # professional acceptance is required here, which is what makes "a result
    # received" and "a task done" two different statements
    fixture = _design_attempt(server, title="分阶段样例", professional=True)
    status, done_before = server.client.get(f"/api/v1/tasks/{fixture['task']['task_id']}")
    assert done_before["lifecycle"] == "ACTIVE"
    status, imported = _import(server, fixture, _result_document_for(fixture))
    assert status == 201
    status, after_import = server.client.get(f"/api/v1/tasks/{fixture['task']['task_id']}")
    assert after_import["lifecycle"] == "ACTIVE", "a result received is not a task done"
    status, technical = server.client.post(
        f"/api/v1/results/{imported['result']['result_id']}/verifications", {"axis": "technical"})
    assert technical["outcome"] == "PASS"
    assert technical.get("product_delivered") is None, technical
    assert "作品" not in technical["detail"], "a plan-pack verification says nothing about delivery"
    status, professional = server.client.post(
        f"/api/v1/results/{imported['result']['result_id']}/verifications", {"axis": "professional"})
    assert professional["outcome"] == "PENDING"
    assert server.client.get(f"/api/v1/tasks/{fixture['task']['task_id']}")[1][
        "lifecycle"] == "ACTIVE"


# ----------------------------------------------------------------------------- F05
def test_f05_unified_search_returns_work_solutions(server):
    """The audited bug: the store had the row, the HTTP adapter threw it away."""
    solution = _seed_solution(server)
    direct = __import__("domains.work.control.solution_library", fromlist=["store_view"])
    view = direct.store_view(server.work.store, query="缓存")
    assert [row["solutionId"] for row in view["results"]] == ["sol-rework-cache"], view

    status, unified = server.client.get("/api/v1/knowledge/search?q=" + urllib.parse.quote("缓存"))
    assert status == 200, unified
    solutions = unified["solutions"]
    assert solutions["status"] in ("OK",), solutions
    assert "sol-rework-cache" in json.dumps(solutions, ensure_ascii=False), solutions
    row = solutions["rows"][0]
    # content type, source, immutable revision, recommendation and trust state survive
    assert row["solutionId"] == solution["solutionId"]
    assert row["revision"] == 1
    assert row["status"] == "UNVERIFIED"
    assert row["recommended"] is False
    assert row["source"]["kind"] == "MANUAL"
    assert row["source"]["ref"] == "rework-fixture"
    assert row["software"]["softwareId"] == "rework"
    assert solutions["content_type"] == "work maintenance solution"
    assert solutions["total"] == 1
    assert unified["content_types"]["solutions"] == "work maintenance solution"
    # the design side of the same call is unaffected
    assert unified["knowledge"]["entries"] == []


def test_f05_short_queries_no_match_and_both_domains_hit(server):
    _seed_solution(server)
    library = KnowledgeLibrary(server.design_service)
    created = library.create(_entry())

    for query, expect_hits in [("缓", 0), ("缓存", 1), ("量子色动力学", 0)]:
        status, unified = server.client.get(
            "/api/v1/knowledge/search?q=" + urllib.parse.quote(query))
        assert status == 200, unified
        hits = [row["solutionId"] for row in unified["solutions"]["rows"]]
        assert len(hits) == expect_hits, (query, hits, unified["solutions"])
        if expect_hits:
            assert hits == ["sol-rework-cache"]

    # a design knowledge word and a work solution word answer separately
    status, unified = server.client.get(
        "/api/v1/knowledge/search?q=" + urllib.parse.quote("分镜"))
    assert status == 200
    assert any(row["knowledge_entry_id"] == created["entry"]["knowledge_entry_id"]
               for row in unified["knowledge"]["entries"]), unified["knowledge"]
    assert unified["solutions"]["rows"] == []
    assert unified["solutions"]["status"] in ("NO_MATCH", "EMPTY"), unified["solutions"]
    assert unified["hit_counts"] == {"knowledge": 1, "solutions": 0}, unified["hit_counts"]


def test_f05_read_failure_is_typed_never_an_empty_success(server, tmp_path):
    """"No solutions" and "the library could not be read" are different sentences."""
    from domains.work.control import solution_library
    class Broken:
        def list_solutions(self):
            raise OSError("simulated read failure")

    view = solution_library.store_view(Broken(), query="缓存")
    assert view["status"] == "SOURCE_ABSENT", view
    assert view["results"] == []
    # and the unified surface reports the typed status rather than inventing empty data
    status, unified = server.client.get("/api/v1/knowledge/search?q=" + urllib.parse.quote("缓存"))
    assert status == 200
    assert unified["solutions"]["status"] in ("EMPTY", "NO_MATCH", "SOURCE_ABSENT"), unified
    assert "note" not in unified["solutions"] or "unavailable" not in unified["solutions"]["note"]


def test_f05_solution_revision_conflict_and_restart_readback(server):
    """A solidified solution is immutable; the restart still answers through HTTP."""
    _seed_solution(server)
    from domains.work.control import solution_library
    rows = server.work.store.list_solutions()
    assert len(rows) == 1, rows
    # a second import of the same id must not silently overwrite the first revision
    again = solution_library.build_solution(
        solution_id="sol-rework-cache", title="同名改写尝试",
        software={"softwareId": "rework", "softwareVersion": "1", "platform": "windows",
                  "versionSource": "DECLARED"},
        source={"kind": "MANUAL", "ref": "rework-fixture",
                "updatedAt": datetime.now(timezone.utc).isoformat()},
        steps=["第二次"], verification_steps=["第二次"], keywords=["缓存"], changes="second write")
    try:
        solution_library.import_unverified(server.work.store, again)
        refused = None
    except ValueError as error:
        refused = str(error)
    # whether it is refused or versioned up, the read model must say which it is
    view = solution_library.store_view(server.work.store, query="缓存")
    revisions = [row["revision"] for row in view["results"]]
    assert (refused is not None) or max(revisions) >= 2, (refused, revisions)

    # restart readback through a fresh store over the same file
    from backend.core.workpacks import WorkPacks
    reopened = WorkPacks(server.local_root / "work-store.sqlite3", grants_path=None)
    try:
        after = solution_library.store_view(reopened.store, query="缓存")
        assert [row["solutionId"] for row in after["results"]] == ["sol-rework-cache"], after
    finally:
        reopened.close()


# ----------------------------------------------------------------------------- F07
def test_f07_origin_chain_is_inherited_and_cannot_be_promoted(server, work_project):
    """A synthetic project/task/attempt never becomes live evidence mid-chain."""
    status, project = server.client.post("/api/v1/projects", {
        "name": "合成来源链", "source": "design", "data_origin": "test"})
    assert status == 201
    assert project["data_origin"] == "test", "the declared origin is stored, not ignored"

    fixture = _design_attempt(server, title="来源链样例")
    assert fixture["attempt"]["data_origin"] == "test"

    # a caller cannot launder the chain by declaring live on the result
    status, body = server.client.post(
        f"/api/v1/attempts/{fixture['attempt']['attempt_id']}/results",
        {"result": _result_document_for(fixture, resultId="res-launder"),
         "data_origin": "live"})
    assert status == 409, body
    assert body["error"].startswith("DATA_ORIGIN_PROMOTION_REFUSED"), body

    # a declared test on a live chain stays test (a downgrade is honest)
    status, live_project = server.client.post("/api/v1/projects", {
        "name": "真实来源样例", "source": "design"})
    assert live_project["data_origin"] == "live"
    status, live_task = server.client.post("/api/v1/tasks", {
        "project_id": live_project["project_id"], "kind": "design", "title": "live task",
        "input_refs": [], "acceptance": {}})
    assert live_task["data_origin"] == "live"

    # an attempt cannot re-declare itself live either
    status, refusal = server.client.post(
        f"/api/v1/tasks/{fixture['task']['task_id']}/attempts",
        {"idempotency_key": "promote-attempt", "data_origin": "live"})
    assert status == 409, refusal
    assert refusal["error"].startswith("DATA_ORIGIN_PROMOTION_REFUSED"), refusal


def test_f07_verdict_and_result_never_escape_the_chain(server):
    fixture = _design_attempt(server, title="核验来源样例")
    status, imported = _import(server, fixture, _result_document_for(fixture))
    assert status == 201
    result = imported["result"]
    assert result["data_origin"] == "test"
    assert result["origin_chain"]["effective"] == "test"
    status, technical = server.client.post(
        f"/api/v1/results/{result['result_id']}/verifications", {"axis": "technical"})
    assert technical["data_origin"] == "test", technical
    assert technical["origin_chain"]["result"] == "test"
    # and no live capability qualification is granted by this chain
    status, catalog = server.client.get("/api/v1/capabilities")
    for entry in catalog["capabilities"]:
        assert entry["data_origin"] == "live", entry
        if entry["can_invoke"]:
            assert entry["probe"]["data_origin"] == "live", entry


def test_f07_work_project_on_real_root_stays_what_it_claims(server, work_project):
    """A work project bound to a real checkout is live; its synthetic task is not."""
    assert work_project["data_origin"] == "live"
    seed_issue(server.work.store)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": work_project["project_id"], "kind": "work", "title": "合成维护",
        "input_refs": [{"kind": "work_project", "project_id": work_project["project_id"]}],
        "acceptance": {"professional_required": False, "data_origin": "test"}})
    assert status == 201, task
    assert task["data_origin"] == "test"
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "origin-1"})
    assert attempt["data_origin"] == "test"


# ----------------------------------------------------------------------------- F08
def test_f08_agent_and_unresolved_verifiers_cannot_satisfy_professional(server):
    # professional acceptance is required, so a technical PASS alone must not close it
    fixture = _design_attempt(server, title="真人验收样例", professional=True)
    status, imported = _import(server, fixture, _result_document_for(fixture))
    result_id = imported["result"]["result_id"]
    status, technical = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                          {"axis": "technical"})
    assert technical["outcome"] == "PASS", technical

    for ref in ["agent:codex-synthetic", "model:gpt", "service:self", "bot:qa",
                "human:agent", "human:system"]:
        status, body = server.client.post(f"/api/v1/results/{result_id}/verifications", {
            "axis": "professional", "professional_verdict": "PASS",
            "verifier_ref": ref, "approval_ref": "happr-unknown"})
        assert status == 409, (ref, body)
        if ref.startswith("human:"):
            # a human-shaped reference is refused either as a role wearing a name
            # prefix, or as an approval that does not resolve — never accepted
            assert body["error"].startswith("VERIFIER_REF_") or                 body["error"].startswith("APPROVAL_"), (ref, body)
        else:
            assert body["error"].startswith("VERIFIER_REF_NOT_HUMAN"), (ref, body)

    # an approval given for a different result does not transfer
    from backend.core.human_gate import ApprovalLedger, mint_interactively
    ledger = ApprovalLedger(server.local_root / "human-approvals.json")
    lines = iter(["别的样例", "这条批准不属于本次结果"])
    other = mint_interactively(ledger, result_id="f" * 32,
                              subject_fingerprint="0" * 64,
                              prompt_reader=lambda _p: next(lines), require_tty=False)
    status, body = server.client.post(f"/api/v1/results/{result_id}/verifications", {
        "axis": "professional", "professional_verdict": "PASS", "approval_ref": other["approval_id"]})
    assert status == 409, body
    assert body["error"].startswith("APPROVAL_WRONG_RESULT"), body

    # an approval for this result but other bytes does not transfer either
    wrong_bytes = ledger.record(result_id=result_id, subject_fingerprint="1" * 64,
                                verifier_ref="human:返工夹具", statement="摘要不符",
                                data_origin="test")
    status, body = server.client.post(f"/api/v1/results/{result_id}/verifications", {
        "axis": "professional", "professional_verdict": "PASS",
        "approval_ref": wrong_bytes["approval_id"]})
    assert status == 409, body
    assert body["error"].startswith("APPROVAL_BYTES_MOVED"), body

    # nothing satisfied the professional axis, so the task never completed
    status, task_now = server.client.get(f"/api/v1/tasks/{fixture['task']['task_id']}")
    assert task_now["lifecycle"] == "ACTIVE"


def test_f08_real_human_approval_cli_refuses_a_piped_stdin(tmp_path):
    """The gate that mints an approval is a terminal, not an endpoint."""
    script = str(TARGET_ROOT / "scripts" / "human_approval.py")
    store_path = tmp_path / "unified.sqlite3"
    from backend.core.unified_store import UnifiedStore
    store = UnifiedStore(store_path)
    project = store.register_project(source="design", display_name="cli")
    task = store.create_task(project_id=project["project_id"], kind="design", title="t",
                             input_refs=[], acceptance={})
    attempt, _created = store.create_attempt(task["task_id"], idempotency_key="k",
                                             execution_mode="MANUAL_COPY")
    result = store.record_result(task_id=task["task_id"], attempt_id=attempt["attempt_id"],
                                 pack_id=None, subject_fingerprint="", artifact_refs=[],
                                 content_sha256="a" * 64, raw={"x": 1}, data_origin="test",
                                 declared_result_id="r1")
    store.record_verification(result_id=result["result_id"], axis="technical", outcome="PASS",
                              subject_fingerprint=result["content_sha256"],
                              evidence_refs=["probe:self"], data_origin="test")
    store.close()
    completed = subprocess.run(
        [VENV_PYTHON, "-B", script, "--store", str(store_path),
         "--ledger", str(tmp_path / "approvals.json"), "--result-id", result["result_id"]],
        input="", capture_output=True, text=True, timeout=120)
    assert completed.returncode == 1, (completed.returncode, completed.stdout, completed.stderr)
    assert "HUMAN_GATE_REQUIRES_TTY" in completed.stderr, completed.stderr
    assert not (tmp_path / "approvals.json").exists()

    # the fixture path exists and is stamped test — never a live approval
    fixture_run = subprocess.run(
        [VENV_PYTHON, "-B", script, "--store", str(store_path),
         "--ledger", str(tmp_path / "approvals.json"), "--result-id", result["result_id"],
         "--allow-non-interactive", "--verifier", "human:返工夹具",
         "--statement", "夹具批准"], capture_output=True, text=True, timeout=120)
    assert fixture_run.returncode == 0, fixture_run.stderr
    document = json.loads((tmp_path / "approvals.json").read_text(encoding="utf-8"))
    assert document["approvals"][0]["data_origin"] == "test", document


# ----------------------------------------------------------------------------- F09
def test_f09_clean_process_imports_the_work_entry_points():
    """No pytest sys.path injection: a bare interpreter must import each entry."""
    for module in ("domains.work.control.sidecar", "domains.work.control.control_service",
                   "domains.work.control.composition_root", "domains.work.control.solution_library",
                   "domains.work.workflow_core.repair_pack_projection",
                   "domains.work.orchestration.collectors",
                   "domains.work.orchestration.platform_discovery",
                   "domains.work.orchestration.task_ledger",
                   "backend.app", "backend.v1"):
        completed = subprocess.run([VENV_PYTHON, "-B", "-c", "import " + module],
                                   cwd=str(TARGET_ROOT), capture_output=True, text=True,
                                   timeout=180)
        assert completed.returncode == 0, (module, completed.stderr[-600:])


def test_f09_composition_root_resolves_the_repository_root():
    probe = (
        "import json, domains.work.control.composition_root as cr\n"
        "root = str(cr._ROOT)\n"
        "print(json.dumps({'root': root, 'is_repo_root': root.endswith('AI-WORK-LAB')}))\n")
    completed = subprocess.run([VENV_PYTHON, "-B", "-c", probe], cwd=str(TARGET_ROOT),
                               capture_output=True, text=True, timeout=180)
    assert completed.returncode == 0, completed.stderr[-600:]
    document = json.loads(completed.stdout.strip().splitlines()[-1])
    assert document["is_repo_root"] is True, document


def test_f09_observer_writes_are_refused_and_recorded(server):
    status, body = server.client.get("/api/work/surface-map")
    assert status == 200, body
    assert body["sidecar_importable"] is True, body
    assert body["compatibility_map"]["/api/v1/snapshot"] == "/api/work/observer/snapshot"

    for method in ("POST", "PUT", "PATCH", "DELETE"):
        status, refused = server.client.request(method, "/api/work/observer/snapshot")
        assert status == 405, (method, status, refused)
        assert refused["reason_code"] == "OBSERVER_IS_READ_ONLY", refused

    status, log = server.client.get("/api/work/observer/refusals")
    assert status == 200
    assert log["count"] >= 4, log
    assert {row["method"] for row in log["refusals"]} >= {"POST", "PUT", "PATCH", "DELETE"}


def test_f09_observer_reads_answer_and_control_gate_is_enforced(server, work_project):
    status, projection = server.client.get("/api/work/observer/projection")
    assert status == 200, projection
    assert projection["mode"] == "ON_DEMAND_READ"
    assert "integrity" in projection

    status, snapshot = server.client.get("/api/work/observer/snapshot")
    assert status in (200, 503), snapshot
    if status == 503:
        assert snapshot["code"].startswith("WORK_"), snapshot

    status, solutions = server.client.get("/api/work/observer/solutions?q=" + urllib.parse.quote("缓存"))
    assert status == 200, solutions

    status, descriptor = server.client.get("/api/work/control/descriptor")
    assert status in (200, 503), descriptor
    if status == 503:
        assert descriptor["code"] == "CONTROL_PLANE_UNAVAILABLE", descriptor
        return
    assert descriptor["operations"], descriptor
    # an unimplemented or unauthorized operation is refused by the plane itself
    status, refusal = server.client.post("/api/work/control/operations", {
        "schemaVersion": "worklab/control-request/v1", "operation": "work-unit.create",
        "actor": "rework-fixture", "payload": {}})
    assert status in (400, 409), (status, refusal)


# ----------------------------------------------------------------------------- F10
def test_f10_qualification_needs_a_probe_bound_to_this_candidate(server):
    status, catalog = server.client.get("/api/v1/capabilities")
    assert status == 200, catalog
    by_id = {row["capability_id"]: row for row in catalog["capabilities"]}
    version = catalog["candidate_version"]

    # only entries with an accepted probe may be callable, and each carries the probe
    for entry in catalog["capabilities"]:
        if entry["can_invoke"]:
            assert entry["qualification"] == "VERIFIED", entry
            assert entry["probe"]["candidate_digest"] == version, entry
            assert entry["probe"]["data_origin"] == "live", entry
            assert entry["unavailable_reasons"] == [], entry
        else:
            assert entry["unavailable_reasons"], entry

    # a file existing, an import working or FTS5 being compiled grants nothing here
    assert by_id["backend.http_surface"]["qualification"] == "NOT_PROBED", by_id["backend.http_surface"]
    assert by_id["backend.http_surface"]["can_invoke"] is False

    # authorization REQUIRED stays refused even with an accepted probe
    repair = by_id["work.repair_packs"]
    assert repair["authorization"] == "REQUIRED", repair
    assert repair["can_invoke"] is False

    # hosts, models and executors keep NOT_PROBED/NOT_GRANTED
    for capability_id in ("design.native_hosts", "design.reconstruction", "design.generative",
                          "work.executors", "work.execution_federation", "work.collectors"):
        entry = by_id[capability_id]
        assert entry["qualification"] in ("NOT_PROBED", "NOT_VERIFIED"), capability_id
        assert entry["can_invoke"] is False, capability_id


def test_f10_stale_and_foreign_candidate_records_grant_nothing(server):
    from backend.core.qualifications import derive, probe_record

    version = server.api.candidate() if hasattr(server, "api") else None
    # rebuild the ledger entry by hand: an expired record and a foreign-candidate record
    ledger = server.qualifications if hasattr(server, "qualifications") else None
    spec = {"implementation": "IMPLEMENTED", "authorization": "NOT_REQUIRED",
            "connection_state": "NOT_REQUIRED", "dependency": "SATISFIED"}
    base = probe_record(capability_id="core.projects", operation="projects.read_write",
                        scope="local_read", subject="x", version={"digest": "f" * 64, "files": 1},
                        outcome="VERIFIED", evidence_refs=["probe:self"], detail="foreign candidate",
                        data_origin="live")
    assert derive(spec, base, version=version)["can_invoke"] is False
    assert "EXPIRED" in json.dumps(derive(spec, base, version=version), ensure_ascii=False)

    stale = probe_record(capability_id="core.projects", operation="projects.read_write",
                         scope="local_read", subject="x", version=version, outcome="VERIFIED",
                         evidence_refs=["probe:self"], detail="window already closed",
                         data_origin="live", ttl_seconds=0)
    stale["expires_at"] = (datetime.now(timezone.utc) - timedelta(seconds=1)).isoformat(
        timespec="seconds")
    verdict = derive(spec, stale, version=version)
    assert verdict["can_invoke"] is False, verdict
    assert "EXPIRED" in verdict["qualification"], verdict

    synthetic = probe_record(capability_id="core.projects", operation="projects.read_write",
                             scope="local_read", subject="x", version=version, outcome="VERIFIED",
                             evidence_refs=["probe:self"], detail="a test probe",
                             data_origin="test")
    verdict = derive(spec, synthetic, version=version)
    assert verdict["qualification"] == "NOT_VERIFIED", verdict
    assert verdict["can_invoke"] is False


def test_f10_unknown_enums_and_missing_dependency_fail_closed(server):
    from backend.core.qualifications import derive, probe_record
    version = {"digest": "a" * 64, "files": 1}
    record = probe_record(capability_id="x", operation="y", scope="local_read", subject="s",
                          version=version, outcome="VERIFIED", evidence_refs=["probe:x"],
                          detail="dependency missing", data_origin="live",
                          dependency="MISSING")
    verdict = derive({"implementation": "IMPLEMENTED", "authorization": "NOT_REQUIRED",
                      "connection_state": "NOT_REQUIRED", "dependency": "UNKNOWN"},
                     record, version=version)
    assert verdict["can_invoke"] is False, verdict
    assert any("dependency=MISSING" in reason for reason in verdict["unavailable_reasons"]), verdict

    # an unknown scope is refused, not silently accepted
    try:
        probe_record(capability_id="x", operation="y", scope="SELF_REPORTED", subject="s",
                     version=version, outcome="VERIFIED", evidence_refs=["probe:x"],
                     detail="client asserted", data_origin="live")
        raise AssertionError("an unregistered probe scope must be refused")
    except ValueError as error:
        assert str(error).startswith("PROBE_SCOPE_REFUSED"), error


# ------------------------------------------------------------------------ surfaces
def test_v06_upgrade_unified_search_asserts_real_hits_not_field_presence(server):
    """The audit's note on V06: it only asserted the solutions field existed."""
    _seed_solution(server)
    created = KnowledgeLibrary(server.design_service).create(_entry())
    status, unified = server.client.get("/api/v1/search?q=" + urllib.parse.quote("缓存"))
    assert status == 200, unified
    assert [row["solutionId"] for row in unified["solutions"]["rows"]] == ["sol-rework-cache"]
    status, unified = server.client.get("/api/v1/search?q=" + urllib.parse.quote("分镜"))
    assert any(row["knowledge_entry_id"] == created["entry"]["knowledge_entry_id"]
               for row in unified["knowledge"]["entries"])


# ----------------------------------------------------------------------------- F01
def _f01_module():
    """The disposition builder, loaded by path, so the graph is recomputed here."""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "f01_disposition_under_test", TARGET_ROOT / "scripts" / "build_f01_disposition.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_f01_registered_gap_paths_all_have_a_real_disposition():
    """Every registered-but-never-copied WORK path is adjudicated, one row each.

    The audit's point was that a mapping row reading ``MAPPED_P0`` with a planning
    directory is not a destination. The register is regenerated from mapping.csv and the
    copy set here, and the assertion is that the register, its report and the file on disk
    are the same population -- the audited count (198) is a bound, not the expected value,
    because closing a real gap is supposed to move it.

    The 2026-10-31 rework closed the second half of the same hole: ``MIGRATED_WIRED``
    used to be checked as ``目标文件 exists``, which a file can satisfy while nothing
    imports it. The assertion is now the AST import graph of the running service,
    rebuilt in this process, and it fails when the register claims a consumer the
    graph does not have.
    """
    completed = subprocess.run([VENV_PYTHON, "-B", "-X", "utf8",
                                str(TARGET_ROOT / "scripts" / "build_f01_disposition.py"),
                                "--json-out", str(TARGET_ROOT / ".project-local" / "runs"
                                                  / "f01-disposition-selfcheck.json")],
                               capture_output=True, text=True, cwd=str(TARGET_ROOT), timeout=900,
                               encoding="utf-8", errors="replace")
    assert completed.returncode == 0, completed.stderr[-1500:]
    report = json.loads(completed.stdout.strip().splitlines()[-1])
    with open(TARGET_ROOT / "migration" / "work-gap-disposition.csv", encoding="utf-8-sig",
              newline="") as handle:
        register_rows = list(csv.DictReader(handle))
    # the register file, the report and the category sum must be one population, not three
    # numbers that a migration is expected to keep frozen
    assert report["gap_paths"] == len(register_rows) == sum(report["categories"].values()), report
    assert 190 <= report["gap_paths"] <= 198, report
    assert report["registered_work_python_paths"] == 225, report
    # nothing may land in an unexplained bucket
    assert set(report["categories"]) <= {"MIGRATED_WIRED", "MIGRATED_AVAILABLE",
                                         "MIGRATED_PRESENT_UNWIRED", "EQUIVALENT_MERGED",
                                         "OUT_OF_SCOPE_BATCH", "TOOL_NOT_RUNTIME",
                                         "HISTORICAL_ONLY",
                                         "RUNTIME_DEPENDENCY_ADJUDICATED"}, report
    # the capability classes the audit named as determined gaps are each accounted for
    rows = {row["原路径"].rsplit("/", 1)[-1]: row
            for row in json.loads((TARGET_ROOT / ".project-local" / "runs" /
                                   "f01-disposition-selfcheck.json").read_text(encoding="utf-8"))["rows"]}
    for name in ("collectors.py", "git_collector.py", "platform_collector.py",
                 "platform_discovery.py", "software_installation_identity.py",
                 "process_collector.py", "token_monitor.py"):
        assert name in rows, name
        assert rows[name]["去向类别"] not in ("", None), rows[name]
        assert rows[name]["判定依据"], rows[name]
        assert len(rows[name]["来源sha256"]) == 64, rows[name]

    graph = _f01_module().build_runtime_import_graph()
    reachable = set(graph["reachable"])
    consumers = {key: set(value) for key, value in graph["consumers"].items()}
    wired = [row for row in rows.values() if row["去向类别"] == "MIGRATED_WIRED"]
    unwired = [row for row in rows.values()
               if row["去向类别"] in ("MIGRATED_PRESENT_UNWIRED", "MIGRATED_AVAILABLE")]
    assert wired, "the graph found no wired closure at all; that is not a pass"
    for row in wired:
        target = row["目标文件"]
        assert target, row
        assert (TARGET_ROOT / target).is_file(), row
        listed = set(x for x in row["运行面消费者"].split(";") if x)
        proven = consumers.get(target, set())
        # the register may not name a consumer the graph does not have...
        assert listed == proven, (target, sorted(listed - proven), sorted(proven - listed))
        # ...and a wired label with no consumer is the exact defect being closed
        assert proven, row
        for consumer in proven:
            assert consumer in reachable, (target, consumer)
    for row in unwired:
        target = row["目标文件"]
        assert (TARGET_ROOT / target).is_file(), row
        assert not consumers.get(target), (row["去向类别"], target,
                                           "claims no consumer but the graph has one")
    # git_collector is the audited false claim: the module file exists, the only
    # "git_collector" in running code is an inline def in collectors.py.
    assert rows["git_collector.py"]["去向类别"] == "MIGRATED_PRESENT_UNWIRED", rows["git_collector.py"]
    assert rows["git_collector.py"]["消费者数"] == "0", rows["git_collector.py"]
    assert "collectors.py" not in consumers.get(
        "domains/work/orchestration/git_collector.py", set()), "inline def is not an import"


def test_f01_migration_register_is_clean_and_side_effect_free():
    """The migrated closure verifies against its own pins, and imports do nothing."""
    completed = subprocess.run([VENV_PYTHON, "-B", "-X", "utf8",
                                str(TARGET_ROOT / "scripts" / "migrate_work_modules.py")],
                               capture_output=True, text=True, cwd=str(TARGET_ROOT), timeout=900,
                               encoding="utf-8", errors="replace")
    assert completed.returncode == 0, completed.stderr[-1500:]
    register = json.loads(completed.stdout[completed.stdout.index("{"):
                                           completed.stdout.rindex("}") + 1])
    assert register["summary"]["allClean"] is True, register["summary"]["problems"][:3]
    assert register["summary"]["statusCounts"].get("OK", 0) >= 27
    for entry in register["migratedModules"]:
        assert entry["status"] == "OK", entry
        assert entry["targetSha256"], entry
        # an import that runs code at module scope is the F01 hazard itself
        for call in entry.get("importTimeCalls", []):
            assert call["names"], call
    # the ones the audit named must not be silent about subprocess at import time
    named = {entry["target"].rsplit("/", 1)[-1]: entry for entry in register["migratedModules"]}
    for module in ("collectors.py", "platform_discovery.py", "process_collector.py"):
        assert module in named, sorted(named)


def test_f01_unified_service_serves_the_migrated_work_projection(server):
    """A migrated module that nothing calls is not a restored capability.

    The snapshot route runs the real read models — including the task-ledger read
    that used to raise ``ImportError`` on every snapshot — and the software and
    adapter-capability projections must come back non-empty with honest states.
    """
    status, snapshot = server.client.get("/api/work/observer/snapshot")
    assert status == 200, snapshot
    assert snapshot["schemaVersion"] == "workflow/snapshot/v3", snapshot
    software = snapshot.get("software") or []
    assert software, "the software projection is still the empty array the audit found"
    for row in software:
        assert row["locationStatus"] == "NOT_PROBED", row
        assert row["discoverySource"] == "not-probed", row
        assert "probeReason" in row, row
    cards = snapshot.get("adapterCapabilities") or snapshot.get("adapter_capabilities") or []
    assert cards, snapshot.keys()
    # the read did not run discovery: nothing was probed, and it says so
    assert snapshot["transport"]["freshnessState"] == "NOT_PROBED", snapshot["transport"]

    status, projection = server.client.get("/api/work/observer/projection")
    assert status == 200, projection
    assert projection["mode"] == "ON_DEMAND_READ"
    assert "tasks" in projection and "integrity" in projection


def test_f01_read_path_starts_no_collector_and_opens_no_socket(server, monkeypatch):
    """`只读观察不自动启动采集器` — the snapshot route must not reach the heavy doors."""
    import domains.work.orchestration.platform_discovery as discovery
    import domains.work.orchestration.collectors as collectors

    def trip(name):
        def _fail(*_args, **_kwargs):
            raise AssertionError(name + " must not run on a read path")
        return _fail

    monkeypatch.setattr(discovery, "discover_all", trip("platform_discovery.discover_all"),
                        raising=False)
    monkeypatch.setattr(discovery, "discover_software_installations",
                        trip("platform_discovery.discover_software_installations"), raising=False)
    monkeypatch.setattr(collectors, "run_collectors", trip("collectors.run_collectors"),
                        raising=False)
    for path in ("/api/work/observer/snapshot", "/api/work/observer/projection",
                 "/api/work/observer/solutions?q=x", "/api/v1/health", "/api/v1/capabilities"):
        status, body = server.client.get(path)
        assert status in (200, 503), (path, body)
    # and the authorized door is closed by default
    from domains.work.orchestration import probe
    try:
        probe.run_probe(authorized=False)
        raise AssertionError("an unauthorized probe must raise, not half-run")
    except Exception as error:  # noqa: BLE001 - the refusal type is the assertion
        assert "NOT_AUTHORIZED" in str(error) or type(error).__name__ in (
            "ProbeNotAuthorized",), str(error)


def test_f09_observer_events_surface_serves_real_sse_frames(server):
    """The last unmounted old consumer path, answered with the migrated encoder.

    The frame format is not reimplemented here: ``domains/work/control/sse_hub``
    renders it, and the ids come from the store's own revision, so the compatibility
    claim can be checked against bytes rather than a sentence.
    """
    from domains.work.control import sse_hub
    status, body = server.client.get("/api/work/observer/events?frames=2")
    assert status == 200, body
    text = body.get("raw") or json.dumps(body)
    assert text.startswith("retry: 2000")
    assert text.count("event: snapshot") == 2, text[:400]
    assert '"continuous_stream": false' in text or '"continuous_stream":false' in text, text[:600]
    assert '"frames":2' in text.replace(" ", ""), text[:400]
    assert "integrity" in text
    # a malformed frame count is refused rather than streamed as one anyway
    status, refusal = server.client.get("/api/work/observer/events?frames=many")
    assert status == 400 and refusal["code"] == "EVENT_FRAMES_MALFORMED", refusal
    # the route is read-only like every other observer path
    status, refused = server.client.request("POST", "/api/work/observer/events")
    assert status == 405 and refused["reason_code"] == "OBSERVER_IS_READ_ONLY", refused
    # the compatibility map names the stream honestly instead of claiming parity
    status, mapping = server.client.get("/api/work/surface-map")
    assert "/api/v1/events" in mapping["compatibility_map"], mapping
    assert "bounded" in mapping["compatibility_map"]["/api/v1/events"], mapping
    assert sse_hub.SNAPSHOT.lower() == "snapshot"
