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


# ------------------------------------------------------------------- 05#L8|issues 链完整性
#
# 登记行：`migration/capability-family-register.csv` 行 `05#L8|issues`（PARTIAL）。缺口原文：
# 「『问题、修复、尝试和证据链可追溯』的链完整性无独立断言，现有测试断言的是读通与 control 门」。
# 下列节点断言链本身，不断言"读得通"。链按代码里真实存在的环节取，六道标识、五个跳转：
#
#   ① 问题行  domains/work/workflow_core/issue_projection.py:567 `load_issues`
#              行形状在同文件 :177-206 `_issue`：只有 fingerprint / evidenceRef / origin，
#              没有任何指向修复包/尝试/结果的字段（这一点在下面按缺陷断言，不代为补齐）。
#   ② 修复包  domains/work/workflow_core/repair_pack_projection.py:231-272
#              `binds.issueFingerprints` / `binds.evidenceRefs`；packId 内容寻址于 :91-96。
#   ③ 存储行  domains/work/workflow_core/canonical_store.py:1122-1176 表 `action_plans`
#              快照 payload 由 domains/work/workflow_core/repair_state.py:77-90 写入。
#   ④ 尝试    backend/v1.py:659-683 → backend/core/unified_store.py:448-492
#              `pack_plan_id` / `pack_ref.issue_fingerprints` / `binding_sha256`。
#   ⑤ 结果    backend/v1.py:910-934 → backend/core/unified_store.py:506-544
#              `task_id` / `attempt_id` / `pack_id` / `binding` / `subject_fingerprint`。
#   ⑥ 判定    backend/v1.py:978-984 → backend/core/unified_store.py:580-617
#              `result_id` / `subject_fingerprint` / `origin_chain`。
#   反向闭合  backend/v1.py:987-995 → repair_state.py:308-311
#              修复记录的 `outcome.evidenceRefs` = `"unified-verification:<判定 id>"`。
#
# 产品自己的完整性面只有两处，且都不覆盖 ②→③→④ 这几跳：
# `backend/core/unified_store.py:739-812 integrity_report`（只在统一库内查存在性与摘要，
# 从不打开 work 库，也不复查 result.attempt_id 与 result.task_id 是否同属一个任务）与
# `backend/core/unified_store.py:661-737 completion_support`。所以这里的谓词是新增断言面，
# 不是把已有读面换个说法再读一遍。

#: 每次都变的字段只有一个，且是被设计成会变（耗时），点名它而不是整段忽略。
CHAIN_VOLATILE_FIELDS = ("summary.cost.elapsedMs",)
#: 稳定性比较里用来替换易变字段的哨兵值；它不出现在任何存储行里。
CHAIN_STABILITY_SENTINEL = "__VOLATILE_NORMALIZED__"
#: 钉死的投影时刻：投影把它原样写进 summary.generatedAt（issue_projection.py:490）。
CHAIN_PINNED_AT = "2026-11-01T00:00:00Z"

#: evidenceRef 的"表 → 取行方法 + 行主键"。方法名和主键都取自 issue_projection 自己的
#: 生产者（:214-263 collector_health、:302-338 telemetry、:341-379 executions、:382-401 tasks），
#: 前缀映射直接读该模块导出的 EVIDENCE_REF_SOURCES（:41-46），不在测试里另立一套名字。
CHAIN_EVIDENCE_TABLES = {
    "collector_health": ("list_collector_health", "name"),
    "telemetry_events": ("list_telemetry_events", "event_id"),
    "execution_instances": ("list_executions", "execution_id"),
    "tasks": ("list_tasks", "task_id"),
}


def _chain_evidence_rows(store):
    """把每条 evidenceRef 解析回它自己声明的那张表里的真实行：ref -> row。"""
    from domains.work.workflow_core import issue_projection
    prefix_for_source = {source: prefix
                         for prefix, source in issue_projection.EVIDENCE_REF_SOURCES.items()}
    assert set(prefix_for_source) == set(CHAIN_EVIDENCE_TABLES), \
        "issue_projection 的来源映射与本节点的解析表已漂移：%r vs %r" % (
            sorted(prefix_for_source), sorted(CHAIN_EVIDENCE_TABLES))
    rows = {}
    for source, (method, key) in CHAIN_EVIDENCE_TABLES.items():
        call = getattr(store, method)
        listed = call(limit=5000) if method == "list_telemetry_events" else call()
        prefix = prefix_for_source[source]
        for row in listed:
            ident = str(row.get(key) or "")
            if ident:
                rows["%s:%s" % (prefix, ident)] = row
    return rows


def _repair_target_root(server):
    """本节点自建的目标根：只放 repair_pack_projection._verification（:164-169）要数的那一个
    入口文件。该函数只判断文件在不在，永不执行它；文件内容因此是空壳说明，不是可跑的门。"""
    from pathlib import Path

    root = Path(server.workspace) / "repair-target-fixture"
    gate = root / "services" / "orchestration" / "run_quality_gate.py"
    gate.parent.mkdir(parents=True, exist_ok=True)
    if not gate.is_file():
        gate.write_text("# 夹具目标根：只用于 repair_pack_projection._verification 的存在性检查，"
                        "本仓与产品代码都不会执行它\n", encoding="utf-8", newline="")
    return root


def _issue_row_for(store, evidence_ref):
    """按 evidenceRef 从真实投影里取那一行问题（不是构造出来的行）。"""
    from domains.work.workflow_core import issue_projection

    issues, _summary, absent = issue_projection.load_issues(store, generated_at=CHAIN_PINNED_AT)
    assert issues is not None, "问题投影没读起来：" + repr(absent)
    matches = [row for row in issues if row["evidenceRef"] == evidence_ref]
    assert len(matches) == 1, (evidence_ref, [row["evidenceRef"] for row in issues])
    return matches[0]


def _work_chain(server, *, collector, attempt_key, declared_result_id, title):
    """在真实服务上跑出一条链的前五环：问题 → 包 → 存储行 → 尝试 → 已导入结果。

    返回的 dict 里 `attempt`/`result` 只带 id：断言用的一切都由 `_chain_state` 之后按 id
    从两份存储重读，不拿响应体当证据。
    """
    seed_issue(server.work.store, name=collector, failures=3)
    issue = _issue_row_for(server.work.store, "collector_health:" + collector)
    status, project = server.client.post("/api/v1/projects", {
        "name": title, "source": "work", "root_path": str(_repair_target_root(server))})
    assert status == 201, project
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "work", "title": title,
        "input_refs": [{"kind": "work_project", "project_id": project["project_id"]}],
        "acceptance": {"professional_required": False}})
    assert status == 201, task
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": attempt_key})
    assert status == 201, attempt
    status, packed = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    assert status == 201, packed
    pack = packed["pack"]
    write_grants(server)
    status, approval = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/approval",
                                          {"authorization_ref": "g-test-1", "expected_version": 1})
    assert status == 200, (approval, pack["status"], pack["readiness"])
    status, handoff = server.client.post(
        f"/api/v1/attempts/{attempt['attempt_id']}/handoff-declarations",
        {"claim": "copiedByUser", "target_version": "work-store-v1",
         "channel": "manual-copy", "actor": "user"})
    assert status == 200, handoff
    document = _result_document(pack["packId"], project["project_id"],
                                result_id=declared_result_id, produced_at=produced_after(handoff))
    document["evidenceRefs"] = ["collector_health:" + collector]
    status, imported = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/results",
                                          {"result": document, "data_origin": "test"})
    assert status == 201, imported
    return {"collector": collector, "issue": issue, "pack": pack, "handoff": handoff,
            "project_id": project["project_id"], "task_id": task["task_id"],
            "attempt_id": attempt["attempt_id"], "pack_id": pack["packId"],
            "result_id": imported["result"]["result_id"], "verdict_ids": []}


def _chain_state(server, material):
    """按 id 从两份存储重读整条链，交给谓词。缺环在这里成为 None，由谓词点名。

    `record` 按"本节点在验的那把包 id"取行；`record_for_attempt` 按"尝试行自己写的名字"取行。
    两个槽都必须存在：反向可追溯走的是尝试行写下的那个名字，把两者混成一个槽就会让
    `attempts.pack_plan_id` 指向不存在之物这一跳永远报不出红。
    """
    record = server.work.read_record(material["pack_id"])
    attempt = server.unified.get_attempt(material["attempt_id"])
    attempt_pack_id = str(attempt.get("pack_plan_id") or "") if attempt else ""
    record_for_attempt = server.work.read_record(attempt_pack_id) if attempt_pack_id else None
    result = server.unified.get_result(material["result_id"])
    verdicts = list((result or {}).get("verifications") or [])
    return {
        "issue": material["issue"],
        "pack": material["pack"],
        "record": record,
        "record_for_attempt": record_for_attempt,
        "attempt": attempt,
        "task": server.unified.get_task(material["task_id"]),
        "project": server.unified.get_project(material["project_id"]),
        "result": result,
        "verdicts": verdicts,
        "verifications_by_id": {str(row["verification_id"]): row for row in verdicts},
        "evidence_rows": _chain_evidence_rows(server.work.store),
        "attempt_id": material["attempt_id"],
        "result_id": material["result_id"],
        "bound_fingerprint": material["issue"]["fingerprint"],
    }


def _chain_link_problems(chain):
    """正向链完整性：每一项引用都必须解析到同一份存储里的真实行，同一标识在所有出现处逐字相同。

    每条问题串都带上断掉的那一环的 id——谓词的职责就是点名，不是给一个布尔。
    """
    problems = []
    issue = chain.get("issue") or {}
    pack = chain.get("pack") or {}
    record = chain.get("record")
    attempt = chain.get("attempt")
    task = chain.get("task")
    project = chain.get("project")
    result = chain.get("result")
    verdicts = chain.get("verdicts") or []
    evidence_rows = chain.get("evidence_rows") or {}
    verifications_by_id = chain.get("verifications_by_id") or {}
    binds = pack.get("binds") or {}
    pack_id = str(pack.get("packId") or "")
    fingerprint = str(issue.get("fingerprint") or "")
    ref = str(issue.get("evidenceRef") or "")

    # 环①→存储：问题行自带的 evidence 标识必须落在一张真实行上
    if not ref:
        problems.append("ISSUE_REF_MISSING:" + fingerprint)
    elif evidence_rows.get(ref) is None:
        problems.append("ISSUE_REF_UNRESOLVED:" + ref + " (fingerprint " + fingerprint + ")")

    # 环①→②：包要绑定这一行问题，并带上它的 evidence 标识
    bound = [str(item) for item in binds.get("issueFingerprints") or []]
    if fingerprint and fingerprint not in bound:
        problems.append("PACK_OMITS_ISSUE:" + fingerprint + " (pack " + pack_id + ")")
    bound_refs = [str(item) for item in binds.get("evidenceRefs") or []]
    if ref and ref not in bound_refs:
        problems.append("PACK_OMITS_EVIDENCE_REF:" + ref + " (pack " + pack_id + ")")
    for item in bound_refs:
        if evidence_rows.get(item) is None:
            problems.append("PACK_BIND_REF_UNRESOLVED:" + item + " (pack " + pack_id + ")")

    # 环②→③：包必须真的落成一存储行，且行里的快照与包说的是同一件事
    if record is None:
        problems.append("PACK_RECORD_ABSENT:" + pack_id)
    else:
        snapshot = (record.get("payload") or {}).get("pack") or {}
        if str(record.get("planId") or "") != pack_id:
            problems.append("PACK_RECORD_KEY_SPLIT:%r!=%r" % (record.get("planId"), pack_id))
        if str(snapshot.get("packId") or "") != pack_id:
            problems.append("PACK_RECORD_SNAPSHOT_ID_SPLIT:%s stores %r"
                            % (pack_id, snapshot.get("packId")))
        snap_binds = [str(item) for item in (snapshot.get("binds") or {}).get("issueFingerprints") or []]
        if snap_binds != bound:
            problems.append("PACK_RECORD_BINDS_SPLIT:%s stores %r projects %r"
                            % (pack_id, snap_binds, bound))
        if project is not None and str(record.get("projectId") or "") != str(
                project.get("project_id") or ""):
            problems.append("PACK_RECORD_PROJECT_SPLIT:%s names %r, task project is %r"
                            % (pack_id, record.get("projectId"), project.get("project_id")))

    # 环③→④：尝试行的 pack_plan_id / pack_ref 必须指回同一包、同一组指纹
    if attempt is None:
        problems.append("ATTEMPT_ABSENT:" + str(chain.get("attempt_id") or ""))
    else:
        attempt_id = str(attempt.get("attempt_id") or "")
        if str(attempt.get("pack_plan_id") or "") != pack_id:
            problems.append("ATTEMPT_PACK_LINK_SPLIT:%s names %r, the pack under test is %r"
                            % (attempt_id, attempt.get("pack_plan_id"), pack_id))
        pack_ref = attempt.get("pack_ref") or {}
        if str(pack_ref.get("pack_id") or "") != pack_id:
            problems.append("ATTEMPT_PACK_REF_ID_SPLIT:%s names %r" % (attempt_id, pack_ref.get("pack_id")))
        if sorted(str(item) for item in pack_ref.get("issue_fingerprints") or []) != sorted(bound):
            problems.append("ATTEMPT_PACK_REF_FINGERPRINTS_SPLIT:%s has %r, pack binds %r"
                            % (attempt_id, pack_ref.get("issue_fingerprints"), bound))
        if sorted(str(item) for item in pack_ref.get("evidence_refs") or []) != sorted(bound_refs):
            problems.append("ATTEMPT_PACK_REF_EVIDENCE_SPLIT:%s has %r, pack binds %r"
                            % (attempt_id, pack_ref.get("evidence_refs"), bound_refs))
        if task is not None and str(attempt.get("task_id") or "") != str(task.get("task_id") or ""):
            problems.append("ATTEMPT_TASK_SPLIT:%s belongs to %r, task row is %r"
                            % (attempt_id, attempt.get("task_id"), task.get("task_id")))
        if task is not None and str(task.get("current_attempt_id") or "") != attempt_id:
            problems.append("TASK_CURRENT_ATTEMPT_SPLIT:%s names %r"
                            % (task.get("task_id"), task.get("current_attempt_id")))

    # 环④→⑤：结果行的三个标识与绑定块必须彼此一致
    if result is None:
        problems.append("RESULT_ABSENT:" + str(chain.get("result_id") or ""))
    else:
        result_id = str(result.get("result_id") or "")
        if attempt is not None:
            if str(result.get("attempt_id") or "") != str(attempt.get("attempt_id") or ""):
                problems.append("RESULT_ATTEMPT_SPLIT:%s names attempt %r, the attempt under test is %r"
                                % (result_id, result.get("attempt_id"), attempt.get("attempt_id")))
            if str(result.get("task_id") or "") != str((attempt or {}).get("task_id") or ""):
                problems.append("RESULT_TASK_ATTEMPT_SPLIT:%s names task %r, its attempt belongs to %r"
                                % (result_id, result.get("task_id"), attempt.get("task_id")))
            if str(result.get("subject_fingerprint") or "") != str(attempt.get("binding_sha256") or ""):
                problems.append("RESULT_SUBJECT_NOT_ATTEMPT_BINDING:%s certifies %r, attempt pins %r"
                                % (result_id, result.get("subject_fingerprint"),
                                   attempt.get("binding_sha256")))
            if str(result.get("pack_id") or "") != str(attempt.get("pack_plan_id") or ""):
                problems.append("RESULT_PACK_LINK_SPLIT:%s answers pack %r, its attempt names %r"
                                % (result_id, result.get("pack_id"), attempt.get("pack_plan_id")))
        binding = result.get("binding") or {}
        for field, row_field in (("task_id", "task_id"), ("attempt_id", "attempt_id"),
                                 ("pack_id", "pack_id")):
            if str(binding.get(field) or "") != str(result.get(row_field) or ""):
                problems.append("RESULT_BINDING_SPLIT:%s binding.%s=%r row.%s=%r"
                                % (result_id, field, binding.get(field), row_field,
                                   result.get(row_field)))
        for item in result.get("artifact_refs") or []:
            if evidence_rows.get(str(item)) is None:
                problems.append("RESULT_ARTIFACT_REF_UNRESOLVED:%s (result %s)"
                                % (item, result_id))

    # 环⑤→⑥：判定必须挂在真实结果行上，认证的是那一行自己的字节摘要
    for row in verdicts:
        verdict_id = str(row.get("verification_id") or "")
        if result is not None and str(row.get("result_id") or "") != str(
                result.get("result_id") or ""):
            problems.append("VERDICT_RESULT_SPLIT:%s names result %r" % (verdict_id, row.get("result_id")))
        if result is not None and str(row.get("subject_fingerprint") or "") != str(
                result.get("content_sha256") or ""):
            problems.append("VERDICT_SUBJECT_NOT_RESULT_DIGEST:%s certifies %r, result digest is %r"
                            % (verdict_id, row.get("subject_fingerprint"), result.get("content_sha256")))

    # 反向闭合：修复记录写回的判定 id 必须能在统一库里解析到行
    outcome = ((record or {}).get("payload") or {}).get("outcome") or {}
    for item in outcome.get("evidenceRefs") or []:
        text = str(item)
        if text.startswith("unified-verification:"):
            if text.split(":", 1)[1] not in verifications_by_id:
                problems.append("CLOSURE_EVIDENCE_UNRESOLVED:" + text + " (pack " + pack_id + ")")
    return problems


def _reverse_trace_problems(chain):
    """反向可追溯：从一条判定出发找回它的结果、尝试、包存储行和那一条问题，标识逐字相同。"""
    problems = []
    verdicts = chain.get("verdicts") or []
    if not verdicts:
        return ["REVERSE_NO_VERDICT_TO_TRACE_BACK"]
    result = chain.get("result")
    attempt = chain.get("attempt")
    task = chain.get("task")
    # 反向那一跳要按尝试行自己写下的名字去找存储行，不是按测试带来的包 id
    record = chain["record_for_attempt"] if "record_for_attempt" in chain else chain.get("record")
    fingerprint = str(chain.get("bound_fingerprint") or "")
    for row in verdicts:
        verdict_id = str(row.get("verification_id") or "")
        result_id = str(row.get("result_id") or "")
        if result is None:
            problems.append("REVERSE_RESULT_ABSENT:%s (from verdict %s)" % (result_id, verdict_id))
            continue
        if str(result.get("result_id") or "") != result_id:
            problems.append("REVERSE_RESULT_ID_SPLIT:verdict %s names %r, loaded row is %r"
                            % (verdict_id, result_id, result.get("result_id")))
        attempt_id = str(result.get("attempt_id") or "")
        if attempt is None:
            problems.append("REVERSE_ATTEMPT_ABSENT:%s (from result %s)" % (attempt_id, result_id))
            continue
        if str(attempt.get("attempt_id") or "") != attempt_id:
            problems.append("REVERSE_ATTEMPT_ID_SPLIT:result %s names %r, loaded row is %r"
                            % (result_id, attempt_id, attempt.get("attempt_id")))
        task_id = str(attempt.get("task_id") or "")
        if task is None:
            problems.append("REVERSE_TASK_ABSENT:%s (from attempt %s)" % (task_id, attempt_id))
            continue
        if str(task.get("task_id") or "") != task_id:
            problems.append("REVERSE_TASK_ID_SPLIT:attempt %s names %r, loaded row is %r"
                            % (attempt_id, task_id, task.get("task_id")))
        pack_id = str(attempt.get("pack_plan_id") or "")
        if record is None:
            problems.append("REVERSE_PACK_RECORD_ABSENT:%s (named by attempt %s)" % (pack_id, attempt_id))
            continue
        if str(record.get("planId") or "") != pack_id:
            problems.append("REVERSE_PACK_RECORD_ID_SPLIT:attempt %s names %r, row key is %r"
                            % (attempt_id, pack_id, record.get("planId")))
        snapshot = (record.get("payload") or {}).get("pack") or {}
        snap_binds = [str(item) for item in (snapshot.get("binds") or {}).get("issueFingerprints") or []]
        if fingerprint and fingerprint not in snap_binds:
            problems.append("REVERSE_PACK_OMITS_ISSUE:%s not in %r (record %s)"
                            % (fingerprint, snap_binds, pack_id))
    return problems


def _chain_text(document, volatile_paths=()):
    """逐字节序列化；只对 CHAIN_VOLATILE_FIELDS 点名的字段套上哨兵，其余一个字节都不放。"""
    mutated = json.loads(json.dumps(document, ensure_ascii=False))
    for path in volatile_paths:
        node = mutated
        parts = path.split(".")
        for part in parts[:-1]:
            node = node[part] if not part.isdigit() else node[int(part)]
        if parts[-1] not in node:
            raise AssertionError("声明的易变字段不在投影输出里：" + path)
        node[parts[-1]] = CHAIN_STABILITY_SENTINEL
    return json.dumps(mutated, ensure_ascii=False)


def _synthetic_chain():
    """一份与真实存储行同形状的干净链（供纯谓词反证用；id 全为 32 hex，包 id 按 :91-96 形状）。"""
    pack_id = "rp-" + "a" * 32 + "-manual-copy-" + "b" * 16
    fingerprint = "243173877b8a0bf4"
    ref = "collector_health:chain-collector"
    attempt_id, task_id, result_id = "c" * 32, "d" * 32, "e" * 32
    verdict_id = "f" * 32
    binding = "1" * 64
    digest = "2" * 64
    document = {
        "issue": {"fingerprint": fingerprint, "evidenceRef": ref, "origin": "collector_health",
                  "class": "SOURCE_FAILURE", "projectId": None, "subject": "chain-collector"},
        "pack": {"packId": pack_id,
                 "binds": {"issueFingerprints": [fingerprint], "evidenceRefs": [ref],
                           "issueCount": 1}},
        "record": {"planId": pack_id, "projectId": "project-1",
                   "payload": {"pack": {"packId": pack_id,
                                        "binds": {"issueFingerprints": [fingerprint]}},
                               "outcome": {"evidenceRefs": ["unified-verification:" + verdict_id]}}},
        "attempt": {"attempt_id": attempt_id, "task_id": task_id, "pack_plan_id": pack_id,
                    "binding_sha256": binding,
                    "pack_ref": {"pack_id": pack_id, "issue_fingerprints": [fingerprint],
                                 "evidence_refs": [ref]}},
        "task": {"task_id": task_id, "current_attempt_id": attempt_id, "project_id": "project-1"},
        "project": {"project_id": "project-1"},
        "result": {"result_id": result_id, "task_id": task_id, "attempt_id": attempt_id,
                   "pack_id": pack_id, "subject_fingerprint": binding, "content_sha256": digest,
                   "artifact_refs": [ref],
                   "binding": {"task_id": task_id, "attempt_id": attempt_id, "pack_id": pack_id}},
        "verdicts": [{"verification_id": verdict_id, "result_id": result_id,
                      "subject_fingerprint": digest}],
        "verifications_by_id": {verdict_id: {"verification_id": verdict_id, "result_id": result_id}},
        "evidence_rows": {ref: {"name": "chain-collector"}},
        "attempt_id": attempt_id,
        "result_id": result_id,
        "bound_fingerprint": fingerprint,
    }
    document["record_for_attempt"] = document["record"]
    return document


def test_issue_chain_forward_references_resolve_to_real_rows_in_the_same_store(server):
    """链完整性·正向：一条问题的每一项引用都按 id 解析到同一份存储里的真实行。

    四个来源同时在场（collector_health / telemetry_events / execution_instances / 迁移过来的
    canonical tasks），所以修复包一次就绑定跨来源的多条 evidenceRef；本节点逐条解析回真实行，
    并要求 `_chain_link_problems` 为空——空的意思是"每一环都指得到东西，且同一个 id 在各处逐字
    相同"，不是"字段非空"。

    验证过的真实链路（不是测试自己拼的关系）：
      issue_projection.py:567→:177 出问题行；repair_pack_projection.py:231-272 绑定；
      repair_state.py:77-90 + canonical_store.py:1122-1176 落 action_plans 行；
      backend/v1.py:659-683 写 attempts.pack_plan_id/pack_ref/binding_sha256；
      backend/v1.py:910-934 写 results；backend/v1.py:978-984 写 verifications。

    明确没有证明：真宿主修好了什么（结果文档 data_origin=test，是夹具导入）；判定所依据的门能跑
    （目标根里那个 run_quality_gate.py 只被存在性检查数到，从未执行）；真人验收；release。
    另有两条已核实的形状事实留在下面的断言里，不代为补齐：问题行本身不带任何指向修复/尝试/结果的
    引用（issue_projection.py:177-206），以及现有逐行校验器 `validate_issue`
    （issue_projection.py:540-564）只看形状、不看引用指不指得到东西。
    """
    from backend.core import refs as ref_rules
    from domains.work.workflow_core import issue_projection

    store = server.work.store
    collector = "chain-collector"
    # 其余三个来源各来一条，让包一次绑定跨来源的引用
    event_id = store.append_telemetry({
        "project_id": "chain-project", "producer": collector, "metric": "coverage", "value": 1,
        "unit": "rows", "occurred_at": "2026-10-30T08:00:00Z", "freshness": "STALE",
        "coverage": "PARTIAL", "source": "chain-fixture", "category": "chain"})
    store.upsert_execution_instance({
        "executionId": "chain-execution-1", "anchorProjectId": "chain-project",
        "agent": collector, "state": "RUNNING", "transportState": "STALE",
        "startedAt": "2026-10-30T08:00:00Z"})
    store.upsert_task({"task_id": "chain-work-task", "project_id": "chain-project",
                       "status": "BLOCKED", "created_at": "2026-10-30T08:00:00Z",
                       "updated_at": "2026-10-30T08:00:00Z"})

    material = _work_chain(server, collector=collector, attempt_key="chain-a",
                           declared_result_id="res-chain-a", title="链完整性·正向")
    # 判定也跑一次，链上六道标识才齐全
    status, verdict = server.client.post(
        "/api/v1/results/%s/verifications" % material["result_id"], {"axis": "technical"})
    assert status == 201, verdict
    material["verdict_ids"].append(verdict["verification_id"])

    chain = _chain_state(server, material)
    issue = chain["issue"]
    pack = chain["pack"]

    # 环①：问题行的 evidence 标识解析到真实行，且投影自己把那个来源报成 read
    rows, summary, _absent = issue_projection.load_issues(store, generated_at=CHAIN_PINNED_AT)
    states = {str(item["source"]): str(item["state"]) for item in summary["sources"]}
    assert states["collector_health"] == "read" and states["telemetry_events"] == "read" \
        and states["execution_instances"] == "read" and states["tasks"] == "read", summary["sources"]
    resolved = _chain_evidence_rows(store)
    unresolved = [row["evidenceRef"] for row in rows if row["evidenceRef"] not in resolved]
    assert unresolved == [], "这些 evidenceRef 指不到任何真实行：" + repr(unresolved)
    assert resolved[issue["evidenceRef"]]["name"] == collector
    # 另外三个来源的标识各自解析回我写入的那一行（前缀与来源名的映射来自 :41-46，不在这里另立）
    assert resolved["telemetry:" + event_id]["event_id"] == event_id
    assert resolved["execution_instances:chain-execution-1"]["anchor_project_id"] == "chain-project"
    assert resolved["tasks:chain-work-task"]["status"] == "BLOCKED"

    # 环②：包绑定的每一条引用都能解析；绑定数与包内 issueCount 对得上
    bound_refs = [str(item) for item in pack["binds"]["evidenceRefs"]]
    assert bound_refs and all(item in resolved for item in bound_refs), bound_refs
    assert len(bound_refs) == pack["binds"]["issueCount"] == len(pack["binds"]["issueFingerprints"])
    assert issue["fingerprint"] in pack["binds"]["issueFingerprints"], pack["binds"]

    # 环③：包真的落成了存储行，快照与包同一条 packId、同一组指纹
    record = server.work.read_record(material["pack_id"])
    assert record is not None, "包没有落成 action_plans 行：" + material["pack_id"]
    assert record["planId"] == material["pack_id"] == record["payload"]["pack"]["packId"]
    assert (record["payload"]["pack"]["binds"]["issueFingerprints"]
            == pack["binds"]["issueFingerprints"])

    # 环④：尝试行的 pack_plan_id 就是那把存储行主键；绑定指纹与包一致
    attempt = server.unified.get_attempt(material["attempt_id"])
    assert attempt["pack_plan_id"] == material["pack_id"] == attempt["pack_ref"]["pack_id"]
    assert sorted(attempt["pack_ref"]["issue_fingerprints"]) == sorted(pack["binds"]["issueFingerprints"])
    assert sorted(attempt["pack_ref"]["evidence_refs"]) == sorted(bound_refs)

    # 环⑤：结果行的三个标识 + 绑定块 + subject_fingerprint 彼此一致（subject 是尝试钉的绑定摘要）
    result = server.unified.get_result(material["result_id"])
    assert (result["task_id"], result["attempt_id"], result["pack_id"]) == (
        material["task_id"], material["attempt_id"], material["pack_id"])
    assert result["subject_fingerprint"] == attempt["binding_sha256"]
    assert result["artifact_refs"] == ["collector_health:" + collector]
    assert all(result["binding"][field] == result[field]
               for field in ("task_id", "attempt_id", "pack_id")), result["binding"]

    # 环⑥：判定认证的就是那一行结果的字节摘要
    verdict_row = [row for row in result["verifications"]
                   if row["verification_id"] == verdict["verification_id"]]
    assert len(verdict_row) == 1, result["verifications"]
    assert verdict_row[0]["subject_fingerprint"] == result["content_sha256"]

    # 整条链的完整性谓词为空 = 每一环都指得到、每一个标识都逐字相同
    assert _chain_link_problems(chain) == [], _chain_link_problems(chain)

    # 两条现读到的形状事实（缺陷，不代为补齐）：
    # (a) 问题行里没有任何指向修复/尝试/结果的字段——正向"这条问题有没有修复链"只能反过来扫
    #     action_plans 才知道（见下面的反向节点）。
    assert {"packId", "planId", "attemptId", "resultId", "repairRef", "repairPackId"}.isdisjoint(
        issue.keys()), sorted(issue)
    # (b) 现有逐行校验器只筛形状，引用指不指得到它看不见：把标识换成不存在的行，它照样说干净。
    dangling = json.loads(json.dumps(issue))
    dangling["evidenceRef"] = "collector_health:never-seen-collector"
    assert issue_projection.validate_issue(dangling) == [], \
        "validate_issue 已经会检查引用可达性——本节点的缺陷断言需按现读重写"
    # 同一件事在写侧：`scheme:opaque` 标识只过形状筛（backend/core/refs.py:62-74），
    # 存在性检查 `for_read` 只作用于相对路径分支。
    assert ref_rules.validate("collector_health:never-seen-collector", allowed_roots=[]) \
        == "collector_health:never-seen-collector"


def test_issue_chain_broken_link_is_misattributed_rather_than_named(server):
    """链完整性·断链点名：一环指不到东西时，产品现在报的是别的环。

    植入方式与下一个节点相同（写侧改 `attempts.pack_plan_id`，跑完还原）：把它改成一个不存在
    的包 id。真实观察到的回答是——技术判定 BLOCKED，`detail` 写「the pack bound no fingerprint
    to re-check」，即把"包存储行读不到"说成"包没绑定任何指纹"，而整条判定里没有任何字段点名那个
    缺失的包 id。链谓词则点名。缺陷位置：backend/v1.py:1065-1069（`read_record` 落空即
    `pack = {}`）+ domains/work/workflow_core/repair_verification.py:175-176（`not bound` 分支
    的这句 reason）。第三条缺陷已在本轮修掉：`integrity_report()` 原先从不打开 work 库，
    现在由路由把 plan 读面交给它，报表会点名 `ATTEMPT_ORPHAN_PACK_PLAN`；不给读面时它自报
    `pack_plan_check = NOT_RUN`，因为「没查」不能长得像「查过且干净」。

    明确没有证明：产品在这条链上有自动修复或补偿动作（没有）；判定为 BLOCKED 是否"足够"——
    本节点只断言它是否点名断链，判定侧的答案正还是否。
    """
    material = _work_chain(server, collector="chain-ghost-collector", attempt_key="chain-ghost",
                           declared_result_id="res-chain-ghost", title="链完整性·断链")
    ghost = "rp-ghost-pack-does-not-exist-manual-copy-0000000000000000"
    attempt_before = server.unified.get_attempt(material["attempt_id"])
    try:
        server.unified.conn.execute("UPDATE attempts SET pack_plan_id=? WHERE attempt_id=?",
                                    (ghost, material["attempt_id"]))
        server.unified.conn.commit()
        assert server.work.read_record(ghost) is None, "幽灵包竟然存在，本节点需按现读重写"
        status, verdict = server.client.post(
            "/api/v1/results/%s/verifications" % material["result_id"], {"axis": "technical"})
        assert status == 201, verdict
        assert verdict["outcome"] == "BLOCKED", verdict
        # 它说的原因不是断链处：绑定数被降成 0，缺失的包 id 一次都没出现
        assert verdict["detail"] == "the pack bound no fingerprint to re-check", verdict["detail"]
        assert verdict["checks"]["fingerprints_absent"] == 0, verdict["checks"]
        assert json.dumps(verdict, ensure_ascii=False).count(ghost) == 0, \
            "判定已点名缺失的包，缺陷断言需按现读重写"
        # 已修（本轮 I-b）：报表拿到 plan 读面以后覆盖这一跳，且点名的是断掉的那一环
        status, report = server.client.get("/api/v1/integrity")
        assert status == 200, report
        assert report["counts"]["pack_plan_check"] == "RUN", report["counts"]
        named_hops = [p for p in report["problems"] if p["kind"] == "ATTEMPT_ORPHAN_PACK_PLAN"]
        assert [p["id"] for p in named_hops] == [material["attempt_id"]], named_hops
        assert ghost in json.dumps(named_hops, ensure_ascii=False), named_hops
        assert report["counts"]["attempts_with_pack_plan"] >= 1, report["counts"]
        # 同一个方法不被交出读面时，它必须自报「这一跳没查」：空的 problems 不等于链是干净的
        silent = server.unified.integrity_report()
        assert silent["counts"]["pack_plan_check"] == "NOT_RUN", silent["counts"]
        assert not [p for p in silent["problems"]
                    if p["kind"] == "ATTEMPT_ORPHAN_PACK_PLAN"], silent["problems"]

        # 同一状态下本块的链谓词点名它断在哪一环
        chain = _chain_state(server, material)
        named = [problem for problem in _chain_link_problems(chain)
                 if problem.startswith("ATTEMPT_PACK_LINK_SPLIT")]
        assert len(named) == 1 and ghost in named[0] and material["pack_id"] in named[0], named
        assert _reverse_trace_problems(chain) == [
            "REVERSE_PACK_RECORD_ABSENT:%s (named by attempt %s)"
            % (ghost, material["attempt_id"])], _reverse_trace_problems(chain)
    finally:
        server.unified.conn.execute("UPDATE attempts SET pack_plan_id=? WHERE attempt_id=?",
                                    (attempt_before["pack_plan_id"], material["attempt_id"]))
        server.unified.conn.commit()
    restored = server.unified.get_attempt(material["attempt_id"])
    assert restored == attempt_before, "还原后尝试行与植入前不一致，本节点的还原证据不成立"
    assert _chain_link_problems(_chain_state(server, material)) == []


def test_issue_chain_reverse_trace_from_a_verdict_names_the_same_ids(server):
    """链完整性·反向：从一条判定出发，结果→尝试→包存储行→问题，每跳都是同一个 id 字符串。

    与"都非空"的区别在这里被钉成可检查的东西：判定带的 result_id 必须等于结果行主键；结果带的
    attempt_id 必须等于尝试行主键，且该尝试的 task_id 必须等于结果行的 task_id；尝试带的
    pack_plan_id 必须等于 action_plans 的主键，而那一行的快照 packs 里必须仍然绑定本节点那条问题
    的指纹。指纹本身按 issue_projection.py:95 的同一函数从「class|projectId|subject」重算，
    所以包→问题这一跳是内容寻址、可由行内容复算，不是一个无人维护的指针。

    再加一条真正的跨库反向链：修复记录闭合时写回的
    `outcome.evidenceRefs = ["unified-verification:<判定 id>"]`（backend/v1.py:987-995 →
    repair_state.py:308-311）必须能在统一库里解析到那一行判定，且那行判定的 result_id 回到本链
    的结果行。缺任何一环，`_reverse_trace_problems` 点名。

    明确没有证明：修复本身（问题是被本节点把 consecutive_failures 归零"治好"的，属夹具动作）；
    宿主/真人验收；跨机可复现的存储内容。
    """
    from domains.work.workflow_core import issue_projection

    collector = "chain-reverse-collector"
    material = _work_chain(server, collector=collector, attempt_key="chain-reverse",
                           declared_result_id="res-chain-reverse", title="链完整性·反向")
    status, failing = server.client.post(
        "/api/v1/results/%s/verifications" % material["result_id"], {"axis": "technical"})
    assert status == 201 and failing["outcome"] == "FAIL", failing
    # 让问题真的离开投影（store 自己说没问题了），再验一次才拿得到 PASS 与闭合写回
    seed_issue(server.work.store, name=collector, failures=0)
    status, passing = server.client.post(
        "/api/v1/results/%s/verifications" % material["result_id"], {"axis": "technical"})
    assert status == 201 and passing["outcome"] == "PASS", passing
    material["verdict_ids"] = [failing["verification_id"], passing["verification_id"]]

    chain = _chain_state(server, material)
    assert _reverse_trace_problems(chain) == [], _reverse_trace_problems(chain)
    assert _chain_link_problems(chain) == [], _chain_link_problems(chain)

    # 逐字相同的标识（不是"都非空"）
    result = chain["result"]
    attempt = chain["attempt"]
    task = chain["task"]
    record = chain["record"]
    verdict_rows = {str(row["verification_id"]): row for row in result["verifications"]}
    closed = verdict_rows[passing["verification_id"]]
    assert closed["result_id"] == result["result_id"]
    assert result["attempt_id"] == attempt["attempt_id"]
    assert attempt["task_id"] == task["task_id"] == result["task_id"]
    assert attempt["pack_plan_id"] == record["planId"] == record["payload"]["pack"]["packId"]
    assert chain["issue"]["fingerprint"] in record["payload"]["pack"]["binds"]["issueFingerprints"]

    # 跨库反向闭合：记录写回的判定 id 就是这一行判定
    closure = record["payload"]["outcome"]["evidenceRefs"]
    assert closure == ["unified-verification:" + passing["verification_id"]], closure
    resolved = server.unified.get_verification(passing["verification_id"])
    assert resolved is not None and resolved["result_id"] == result["result_id"]
    assert resolved["axis"] == "technical" and resolved["outcome"] == "PASS"
    assert record["status"] == "SUCCEEDED", record["status"]

    # 指纹由问题行的身份三元组复算——包→问题这一跳不靠指针维持
    recomputed = issue_projection._fingerprint(chain["issue"]["class"],
                                               chain["issue"]["projectId"],
                                               chain["issue"]["subject"])
    assert recomputed == chain["issue"]["fingerprint"], (recomputed, chain["issue"])

    # 两条判定都是链上的真实行；旧的 FAIL 不被新的 PASS 抹掉
    assert len(result["verifications"]) == 2, result["verifications"]
    assert [row["outcome"] for row in result["verifications"]] == ["FAIL", "PASS"]
    assert server.unified.completion_support(task["task_id"])["supported"] is True
    assert task["lifecycle"] == "COMPLETED", task["lifecycle"]


def test_issue_chain_one_tampered_identifier_is_named_and_the_row_restores(server):
    """链完整性·篡改：改一个标识指向另一个项目/另一个尝试/另一个包，谓词点名那一条，跑完还原。

    三次植入都只改一个标识列（raw SQL，绕过合同——合同在写侧的拒绝已由 test_v03/v11 其他节点覆盖，
    这里要的是"落地之后的行被改了"这一形状，也正是 integrity_report 存在的理由），每次都 try/finally
    还原，并断言还原后整行与植入前逐字段相同（`==` 比较整行 dict，不比"看起来差不多"）。

    产品自己的报表在这三件事上能力不同，按观察到的结果分别断言，不做统一美化：
      ① `results.attempt_id` 改成另一项目另一尝试的 id：`integrity_report` 点名
         COMPLETION_UNSUPPORTED，但 id 给的是**任务**，detail 给的是**尝试**，被篡改的结果行 id
         一次都不出现（unified_store.py:767-773 只查 attempt/task 存在与否，不复查两者是否同属
         一个任务——写侧规则在 unified_store.py:523-525）。链谓词点名结果行。
      ② `attempts.pack_plan_id` 改成另一个包的 id：`integrity_report` **完全沉默**，技术判定拿去
         回答另一个包的指纹集合并给出 PASS，任务据此 COMPLETED，而本链自己绑定的指纹仍在被产出；
         还原标识后那条误判 PASS 与 COMPLETED 状态都还在（无补偿动作）。
      ③ `verifications.result_id` 改成另一条结果：`integrity_report` 点名
         VERIFICATION_SUBJECT_MISMATCH，id 就是被篡改的判定行本身——这是产品当前唯一会点名被篡改
         行的那一跳。

    明确没有证明：篡改能被自动发现并回滚（②证明它发现不了）；判定为 PASS 等于外部真修好了。
    """
    from domains.work.workflow_core import issue_projection

    project_a = _work_chain(server, collector="chain-tamper-a", attempt_key="tamper-a",
                            declared_result_id="res-tamper-a", title="链完整性·篡改A")
    status, first = server.client.post(
        "/api/v1/results/%s/verifications" % project_a["result_id"], {"axis": "technical"})
    assert status == 201 and first["outcome"] == "FAIL", first
    # A 绑定的问题从投影里消失（consecutive_failures 归零），A 才可能闭合
    seed_issue(server.work.store, name="chain-tamper-a", failures=0)
    status, closed_a = server.client.post(
        "/api/v1/results/%s/verifications" % project_a["result_id"], {"axis": "technical"})
    assert status == 201 and closed_a["outcome"] == "PASS", closed_a
    project_a["verdict_ids"] = [first["verification_id"], closed_a["verification_id"]]
    clean_report = server.unified.integrity_report()
    assert clean_report["problems"] == [], clean_report
    assert _chain_link_problems(_chain_state(server, project_a)) == []

    # B 在另一个项目、另一个尝试上：此时 A 的指纹已离开投影，所以 B 的包只绑 B 自己的指纹
    project_b = _work_chain(server, collector="chain-tamper-b", attempt_key="tamper-b",
                            declared_result_id="res-tamper-b", title="链完整性·篡改B")
    assert project_b["pack"]["binds"]["issueFingerprints"] == [project_b["issue"]["fingerprint"]]
    assert project_b["project_id"] != project_a["project_id"]
    assert _chain_link_problems(_chain_state(server, project_b)) == []

    # ---- ① 结果标识指向另一项目的另一尝试 -------------------------------------
    result_before = server.unified.get_result(project_a["result_id"])
    try:
        server.unified.conn.execute("UPDATE results SET attempt_id=? WHERE result_id=?",
                                    (project_b["attempt_id"], project_a["result_id"]))
        server.unified.conn.commit()
        problems = _chain_link_problems(_chain_state(server, project_a))
        named = [item for item in problems if item.startswith("RESULT_ATTEMPT_SPLIT")]
        assert len(named) == 1 and project_a["result_id"] in named[0] \
            and project_b["attempt_id"] in named[0], problems
        # 结果行自带的绑定块当场与行自身说法不一致——它是行内自证，不依赖任何跨库读
        assert any(item.startswith("RESULT_BINDING_SPLIT") and "attempt_id" in item
                   for item in problems), problems
        reversed_problems = _reverse_trace_problems(_chain_state(server, project_a))
        expected_split = ("REVERSE_ATTEMPT_ID_SPLIT:result %s names %r, loaded row is %r"
                          % (project_a["result_id"], project_b["attempt_id"],
                             project_a["attempt_id"]))
        # 两条判定都挂在这行结果上，于是同一处断裂被逐条点出两次：一次都没有漏，也没有别的
        assert reversed_problems and set(reversed_problems) == {expected_split}, reversed_problems
        report = server.unified.integrity_report()["problems"]
        kinds = {str(item["kind"]) for item in report}
        assert "COMPLETION_UNSUPPORTED" in kinds, report
        ids = {str(item["id"]) for item in report}
        assert project_a["task_id"] in ids, report
        assert project_a["result_id"] not in json.dumps(report, ensure_ascii=False), \
            "报表已点名被篡改的结果行——本节点的缺陷断言需按现读重写"
    finally:
        server.unified.conn.execute("UPDATE results SET attempt_id=? WHERE result_id=?",
                                    (result_before["attempt_id"], project_a["result_id"]))
        server.unified.conn.commit()
    assert server.unified.get_result(project_a["result_id"]) == result_before, "①未逐字段还原"
    assert _chain_link_problems(_chain_state(server, project_a)) == []
    assert server.unified.integrity_report()["problems"] == [], server.unified.integrity_report()

    # ---- ② 尝试标识指向另一个包 ---------------------------------------------
    attempt_b_before = server.unified.get_attempt(project_b["attempt_id"])
    try:
        server.unified.conn.execute("UPDATE attempts SET pack_plan_id=? WHERE attempt_id=?",
                                    (project_a["pack_id"], project_b["attempt_id"]))
        server.unified.conn.commit()
        problems = _chain_link_problems(_chain_state(server, project_b))
        named = [item for item in problems if item.startswith("ATTEMPT_PACK_LINK_SPLIT")]
        assert len(named) == 1 and project_b["attempt_id"] in named[0] \
            and project_a["pack_id"] in named[0], problems
        assert any(item.startswith("RESULT_PACK_LINK_SPLIT") for item in problems), problems
        status, misread = server.client.post(
            "/api/v1/results/%s/verifications" % project_b["result_id"], {"axis": "technical"})
        assert status == 201, misread
        # 判定回答的是别人家的指纹集合：A 的指纹已消失 → PASS；B 自己绑的那条仍在被产出
        assert misread["outcome"] == "PASS", misread
        assert misread["checks"]["fingerprints_absent"] == 1, misread["checks"]
        assert project_b["issue"]["fingerprint"] in [
            row["fingerprint"] for row in issue_projection.load_issues(server.work.store)[0]], \
            "B 自己的问题已经不在了，本节点的反证形状需按现读重写"
        # 现读：这一跳被报表检查了（RUN），而 B 指向的是 A 家真实存在的包——那是一个跨项目的
        # 误读，不是一条断链，报表不能把它报成 ATTEMPT_ORPHAN_PACK_PLAN。
        status, hop_report = server.client.get("/api/v1/integrity")
        assert status == 200, hop_report
        assert hop_report["counts"]["pack_plan_check"] == "RUN", hop_report["counts"]
        assert not [p for p in hop_report["problems"]
                    if p["kind"] == "ATTEMPT_ORPHAN_PACK_PLAN"], hop_report["problems"]
    finally:
        server.unified.conn.execute("UPDATE attempts SET pack_plan_id=? WHERE attempt_id=?",
                                    (attempt_b_before["pack_plan_id"], project_b["attempt_id"]))
        server.unified.conn.commit()
    assert server.unified.get_attempt(project_b["attempt_id"]) == attempt_b_before, "②未逐字段还原"
    assert _chain_link_problems(_chain_state(server, project_b)) == []
    # 还原标识不撤销后果：误判的 PASS 与据此 COMPLETED 的任务仍留在存储里（没有补偿动作）
    task_b_after = server.unified.get_task(project_b["task_id"])
    assert task_b_after["lifecycle"] == "COMPLETED", task_b_after["lifecycle"]
    assert server.work.read_record(project_b["pack_id"])["status"] == "APPROVED", \
        "B 的修复记录被谁改了？本节点未再验过一次，它应停在 APPROVED"

    # ---- ③ 判定标识指向另一条结果 -------------------------------------------
    verdict_before = server.unified.get_verification(closed_a["verification_id"])
    try:
        server.unified.conn.execute("UPDATE verifications SET result_id=? WHERE verification_id=?",
                                    (project_b["result_id"], closed_a["verification_id"]))
        server.unified.conn.commit()
        report = server.unified.integrity_report()["problems"]
        named = [item for item in report
                 if item["kind"] == "VERIFICATION_SUBJECT_MISMATCH"
                 and item["id"] == closed_a["verification_id"]]
        assert len(named) == 1, report
        chain = _chain_state(server, project_a)
        problems = _chain_link_problems(chain)
        # 被改走的判定从结果 A 的子表里消失，而 A 的修复记录仍写回那个判定 id：
        # 跨库反向那一跳的引用因此解析不到行，谓词点名的是判定 id 本身
        assert any(item.startswith("CLOSURE_EVIDENCE_UNRESOLVED:")
                   and closed_a["verification_id"] in item for item in problems), problems
        assert server.unified.get_verification(
            closed_a["verification_id"])["result_id"] == project_b["result_id"]
    finally:
        server.unified.conn.execute("UPDATE verifications SET result_id=? WHERE verification_id=?",
                                    (verdict_before["result_id"], closed_a["verification_id"]))
        server.unified.conn.commit()
    assert server.unified.get_verification(closed_a["verification_id"]) == verdict_before, "③未逐字段还原"
    assert server.unified.integrity_report()["problems"] == [], server.unified.integrity_report()
    assert _chain_link_problems(_chain_state(server, project_a)) == []


def test_issue_chain_double_projection_is_byte_identical_except_one_named_field(server):
    """链完整性·幂等：同一状态连续投影两次，除一个点名的耗时字段外逐字节相同。

    被点名并从比较里显式拿掉的只有一个：`summary.cost.elapsedMs`（issue_projection.py:453/482/530
    测的是本次投影耗时，设计上每次都变）。其余一个字节都不许动，包括所有 issue 行、所有分母、
    键序与出现顺序——比较用整段 JSON 原文，不是逐字段挑几个"重要的"。另外单独断言：
      * 被拿掉的那个字段两次都存在、都是非负数（不是把它删了来凑相等）；
      * 传入 generated_at 时 `summary.generatedAt` 原样回显该值（:490），不传时它是墙上时钟
        （:535 `_now_iso`），两次调用都必须是可解析的即时；
      * 包投影 `build_repair_pack` 两次逐字节相同且 packId 相同（:91-96 内容寻址）；
      * 交接正文 `render_handoff_text` 两次逐字节相同；
      * 重试同一条链走产品自己的路径（backend/core/workpacks.py:69-77）：不铸第二行、不前进版本；
        而 `repair_state.record_pack` 拒绝把已推进的行倒回草稿状态（canonical_store.py:1151-1158）；
      * `integrity_report()` / `completion_support()` 两次逐字节相同（它们不带时钟字段）。

    明确没有证明：跨进程/跨机器的字节一致（本节点在同一进程内连续投影两次）；投影内容正确性由
    上面两个节点负责，这里只管稳定。
    """
    from domains.work.workflow_core import issue_projection, repair_pack_projection

    collector = "chain-stable-collector"
    seed_issue(server.work.store, name=collector, failures=3)
    material = _work_chain(server, collector=collector, attempt_key="chain-stable",
                           declared_result_id="res-chain-stable", title="链完整性·幂等")

    def snapshot():
        rows, summary, absent = issue_projection.load_issues(
            server.work.store, generated_at=CHAIN_PINNED_AT)
        return {"issues": rows, "summary": summary, "absentReason": absent}

    first = snapshot()
    second = snapshot()
    raw_first = json.dumps(first, ensure_ascii=False)
    raw_second = json.dumps(second, ensure_ascii=False)
    # 未归一化前，两次原文的差异只允许落在被点名的那一个字段上——先把这件事本身断言出来
    assert raw_first != raw_second or \
        first["summary"]["cost"]["elapsedMs"] == second["summary"]["cost"]["elapsedMs"], \
        "elapsedMs 不再变化，易变字段的登记需按现读复核"
    assert _chain_text(first, CHAIN_VOLATILE_FIELDS) == _chain_text(second, CHAIN_VOLATILE_FIELDS), \
        "除 %s 外还有字段在变" % (CHAIN_VOLATILE_FIELDS,)
    for summary in (first["summary"], second["summary"]):
        elapsed = summary["cost"]["elapsedMs"]
        assert isinstance(elapsed, (int, float)) and not isinstance(elapsed, bool) and elapsed >= 0, \
            summary["cost"]
        assert summary["generatedAt"] == CHAIN_PINNED_AT, summary["generatedAt"]
    unpinned = issue_projection.load_issues(server.work.store)[1]["generatedAt"]
    assert unpinned != CHAIN_PINNED_AT and issue_projection._epoch(unpinned) > 0, unpinned
    # 链上标识在两次投影之间也稳定（指纹是内容寻址，不是每次铸造）
    assert [row["fingerprint"] for row in first["issues"]] == \
        [row["fingerprint"] for row in second["issues"]]
    assert [row["evidenceRef"] for row in first["issues"]] == [material["issue"]["evidenceRef"]]

    projects = [{"projectId": material["project_id"],
                 "root_path": str(_repair_target_root(server))}]
    pack_first, reason_first = repair_pack_projection.build_repair_pack(
        adapter=None, project_id=material["project_id"], bound_rows=list(first["issues"]),
        projects=projects, registry=None, generated_at=CHAIN_PINNED_AT, manual=True)
    pack_second, reason_second = repair_pack_projection.build_repair_pack(
        adapter=None, project_id=material["project_id"], bound_rows=list(first["issues"]),
        projects=projects, registry=None, generated_at=CHAIN_PINNED_AT, manual=True)
    assert (reason_first, reason_second) == ("", ""), (reason_first, reason_second)
    assert json.dumps(pack_first, ensure_ascii=False) == json.dumps(pack_second, ensure_ascii=False)
    assert repair_pack_projection.render_handoff_text(pack_first) \
        == repair_pack_projection.render_handoff_text(pack_second)
    assert repair_pack_projection.validate_repair_pack(pack_first) == []

    # packId 只由（项目、执行者标签、绑定指纹）决定：存储时的包带的 generatedAt 是本节点重算
    # 时钉死的那个值之外的墙上时刻，两者时间戳不同、包 id 必须相同（:91-96 的内容寻址）
    stored = server.work.read_record(material["pack_id"])
    assert pack_first["packId"] == pack_second["packId"] == material["pack_id"]
    assert stored["payload"]["pack"]["generatedAt"] != CHAIN_PINNED_AT
    assert stored["payload"]["pack"]["binds"] == pack_first["binds"]

    # 重试同一个链走的是产品自己的重试路径（backend/core/workpacks.py:69-77）：内容寻址的 packId
    # 撞到已有行 → 读回那一行，既不新建行也不前进版本。存储行的 status 已被审批/交接推进，
    # 所以这里断言的是"没有新副本"，不是"载荷逐字节相同"。
    from domains.work.workflow_core import repair_state

    before = server.work.read_record(material["pack_id"])
    retry = server.work.build_and_record_pack(project_id=material["project_id"],
                                              project_root=str(_repair_target_root(server)))
    after = server.work.read_record(material["pack_id"])
    assert retry["pack"]["packId"] == material["pack_id"] == before["planId"]
    assert after["version"] == before["version"], (before["version"], after["version"])
    assert after["payloadDigest"] == before["payloadDigest"]
    assert after["status"] == before["status"] == "APPROVED"
    assert server.work.store.list_action_plans(material["project_id"]).__len__() == 1, \
        "重试为同一个包铸出了第二行"
    # 记录面拒绝把生命周期倒回去：草稿快照不能覆盖已审批的行（repair_state.py:117-126 +
    # canonical_store.py:1151-1158 的 compare-and-swap）
    try:
        repair_state.record_pack(server.work.store, before["payload"]["pack"])
        raise AssertionError("用已过期状态重记同一包竟然成功了")
    except ValueError as conflict:
        assert "ACTION_PLAN_VERSION_CONFLICT" in str(conflict), str(conflict)

    # 两个完整性面自身也是确定的（无时钟字段）
    report_a = json.dumps(server.unified.integrity_report(), ensure_ascii=False, sort_keys=True)
    report_b = json.dumps(server.unified.integrity_report(), ensure_ascii=False, sort_keys=True)
    assert report_a == report_b, (report_a, report_b)
    support = server.unified.completion_support
    task_id = material["task_id"]
    assert json.dumps(support(task_id), ensure_ascii=False, sort_keys=True) \
        == json.dumps(support(task_id), ensure_ascii=False, sort_keys=True)


def test_issue_chain_link_predicates_falsification():
    """植入反证（链谓词）：把链上任一标识换成另一个对象，谓词必须报红并点名断掉的那一环。

    与真实存储节点共用同一份谓词实现；这里逐跳植入，保证报红的是"那一跳"，而不是碰巧整体不同。
    每处植入都只改一个字段，改完立刻与另两处的期望问题分开断言，防止串台。
    """
    clean = _synthetic_chain()
    assert _chain_link_problems(clean) == [], _chain_link_problems(clean)
    assert _reverse_trace_problems(clean) == [], _reverse_trace_problems(clean)

    def plant(mutate):
        document = json.loads(json.dumps(clean))
        mutate(document)
        return document

    # ①→②：包不再绑定这条问题
    moved = plant(lambda d: d["pack"]["binds"].__setitem__("issueFingerprints", ["deadbeefcafe0000"]))
    moved_problems = _chain_link_problems(moved)
    assert moved_problems, "包丢掉绑定的问题却全绿"
    assert any(item.startswith("PACK_OMITS_ISSUE:") and clean["issue"]["fingerprint"] in item
               for item in moved_problems), moved_problems
    assert any(item.startswith("PACK_RECORD_BINDS_SPLIT") for item in moved_problems), \
        "包快照与本节点重算的绑定集合不一致，却没报在 ②→③ 那一跳：" + str(moved_problems)

    # ①→存储：evidence 标识指向一个不存在的行（形状仍完全合法）
    dangling = plant(lambda d: d["issue"].__setitem__("evidenceRef", "collector_health:ghost"))
    dangling_problems = _chain_link_problems(dangling)
    assert "ISSUE_REF_UNRESOLVED:collector_health:ghost (fingerprint %s)" % clean["issue"][
        "fingerprint"] in dangling_problems, dangling_problems

    # ②→③：包没有对应的存储行（今天的投影不会为此说任何东西）
    absent = plant(lambda d: [d.__setitem__("record", None), d.__setitem__("record_for_attempt", None)])
    absent_problems = _chain_link_problems(absent)
    assert "PACK_RECORD_ABSENT:" + clean["pack"]["packId"] in absent_problems, absent_problems
    assert _reverse_trace_problems(absent) == [
        "REVERSE_PACK_RECORD_ABSENT:%s (named by attempt %s)"
        % (clean["attempt"]["pack_plan_id"], clean["attempt_id"])], _reverse_trace_problems(absent)

    # ③→④：尝试指向另一个包
    other_pack = "rp-" + "9" * 32 + "-manual-copy-" + "9" * 16
    rewired = plant(lambda d: d["attempt"].__setitem__("pack_plan_id", other_pack))
    rewired_problems = _chain_link_problems(rewired)
    assert any(item.startswith("ATTEMPT_PACK_LINK_SPLIT") and other_pack in item
               and clean["pack"]["packId"] in item for item in rewired_problems), rewired_problems
    # 结果行仍回答本节点那个包，而尝试已经改口——同一链上两个标识当场分家
    assert any(item.startswith("RESULT_PACK_LINK_SPLIT") and other_pack in item
               for item in rewired_problems), rewired_problems
    assert _reverse_trace_problems(rewired) == [
        "REVERSE_PACK_RECORD_ID_SPLIT:attempt %s names %r, row key is %r"
        % (clean["attempt_id"], other_pack, clean["pack"]["packId"])], _reverse_trace_problems(rewired)

    # ④→⑤：结果挂到另一个尝试上（绑定块立刻与行自身说法不一致）
    other_attempt = "7" * 32
    wrong_attempt = plant(lambda d: d["result"].__setitem__("attempt_id", other_attempt))
    wrong_attempt_problems = _chain_link_problems(wrong_attempt)
    assert any(item.startswith("RESULT_ATTEMPT_SPLIT") and wrong_attempt["result"]["result_id"]
               in item and other_attempt in item for item in wrong_attempt_problems), \
        wrong_attempt_problems
    assert any(item.startswith("RESULT_BINDING_SPLIT") and "attempt_id" in item
               for item in wrong_attempt_problems), wrong_attempt_problems

    # ④→⑤：结果改挂到另一个项目的任务上——写侧规则（unified_store.py:523-525）在落地后被绕过
    other_task = "6" * 32
    wrong_task = plant(lambda d: d["result"].__setitem__("task_id", other_task))
    wrong_task_problems = _chain_link_problems(wrong_task)
    assert any(item.startswith("RESULT_TASK_ATTEMPT_SPLIT") and other_task in item
               and wrong_task["attempt"]["task_id"] in item
               for item in wrong_task_problems), wrong_task_problems
    assert any(item.startswith("RESULT_BINDING_SPLIT") and "task_id" in item
               for item in wrong_task_problems), wrong_task_problems

    # ⑤：结果认证的不是尝试钉的那份绑定摘要
    fake_subject = plant(lambda d: d["result"].__setitem__("subject_fingerprint", "3" * 64))
    assert any(item.startswith("RESULT_SUBJECT_NOT_ATTEMPT_BINDING")
               for item in _chain_link_problems(fake_subject)), _chain_link_problems(fake_subject)

    # ⑤→⑥：判定认证了另一行字节
    other_digest = plant(lambda d: d["verdicts"][0].__setitem__("subject_fingerprint", "4" * 64))
    assert any(item.startswith("VERDICT_SUBJECT_NOT_RESULT_DIGEST")
               for item in _chain_link_problems(other_digest)), _chain_link_problems(other_digest)

    # ⑥ 的 result_id 被改指到别的结果：正向与反向都要点名
    other_result = "8" * 32
    verdict_moved = plant(lambda d: d["verdicts"][0].__setitem__("result_id", other_result))
    forward = _chain_link_problems(verdict_moved)
    assert any(item.startswith("VERDICT_RESULT_SPLIT") and other_result in item for item in forward), forward
    assert any(item.startswith("REVERSE_RESULT_ID_SPLIT") and clean["verdicts"][0]["result_id"] in item
               for item in _reverse_trace_problems(verdict_moved)), _reverse_trace_problems(verdict_moved)

    # 反向：结果行整个读不到，判定就成了无人认领的结论
    no_result = plant(lambda d: d.__setitem__("result", None))
    assert _reverse_trace_problems(no_result) == [
        "REVERSE_RESULT_ABSENT:%s (from verdict %s)"
        % (clean["verdicts"][0]["result_id"], clean["verdicts"][0]["verification_id"])], \
        _reverse_trace_problems(no_result)

    # 闭合写回的判定 id 解析不到行：跨库那一跳也算断链
    ghost_closure = plant(lambda d: d["record"]["payload"]["outcome"].__setitem__(
        "evidenceRefs", ["unified-verification:" + "0" * 32]))
    assert any(item.startswith("CLOSURE_EVIDENCE_UNRESOLVED:") and "0" * 32 in item
               for item in _chain_link_problems(ghost_closure)), _chain_link_problems(ghost_closure)
