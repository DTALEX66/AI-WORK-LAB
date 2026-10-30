# SPDX-License-Identifier: MIT
"""V04: a design plan revision and a target-profile reference travel the same
task-pack envelope, professional acceptance stays PENDING, and the task does not
complete on technical verification alone.

The acceptance meaning of this file is unchanged from the audited version. What
changed is what the envelope now requires to make those statements verifiable
(2026-10-30 audit F02/F03/F08), so three inputs are spelled out rather than
assumed:

* a target profile is addressed by its real ``profile_key`` / ``profile_id``.
  A prose hint is not an address, so the pack cannot pin a member of the
  combination it claims to answer;
* a design result declares the versioned schema and the result id the dedup and
  the audit trail run on;
* a named human verdict resolves against the local human-approval ledger. The
  fixture below mints that approval through the same code path a person uses at a
  terminal, stamped ``data_origin=test`` — it proves the *mechanism*, and it is
  explicitly not a real professional acceptance.
"""
from __future__ import annotations

import json

from tests.conftest import produced_after

PLAN_OUTPUT_TYPE = "STORYBOARD"
#: One profile that actually exists in the tracked config.
PROFILE_KEY = "minimax-h3--api--video-reference"


def _create_plan(server, design_project_id: str) -> dict:
    from design_lab.assistance_plan import AssistancePlans
    plans = AssistancePlans(server.design_service)
    created = plans.create(design_project_id, {
        "objective": "为一支 45 秒短片产出可执行分镜表（测试样例）",
        "output_type": PLAN_OUTPUT_TYPE,
        "created_by": "owner",
    })
    return created


def _fixture_approval(server, result_id: str, subject_fingerprint: str) -> str:
    """Mint a named-human approval through the ledger's own code path (test origin)."""
    from backend.core.human_gate import ApprovalLedger, mint_interactively
    ledger = ApprovalLedger(server.local_root / "human-approvals.json")
    lines = iter(["fixture-reviewer", "夹具：技术核验读回一致，专业验收按合同记录"])
    reader = lambda _prompt: next(lines)  # noqa: E731 - fixed two-field fixture input
    row = mint_interactively(ledger, result_id=result_id,
                             subject_fingerprint=subject_fingerprint,
                             prompt_reader=reader, require_tty=False)
    assert row["data_origin"] == "test", row
    return row["approval_id"]


def test_design_loop_keeps_professional_acceptance_pending(server):
    # design project through the unified registration (creates the runtime project too)
    status, project = server.client.post("/api/v1/projects", {
        "name": "设计样例", "source": "design", "data_origin": "test"})
    assert status == 201
    design_project_id = project["root_path"]
    assert project["data_origin"] == "test", project

    created = _create_plan(server, design_project_id)
    plan_id = created["plan"]["plan_id"]
    revision = created["revision"]

    # revise the plan once: a new revision, the old bytes untouched
    from design_lab.assistance_plan import AssistancePlans
    plans = AssistancePlans(server.design_service)
    revised = plans.revise(design_project_id, plan_id, {
        "objective": "为一支 45 秒短片产出可执行分镜表（测试样例·修订一）",
        "output_type": PLAN_OUTPUT_TYPE,
        "created_by": "owner",
        "expected_revision": revision,
    })
    assert revised["revision"] == revision + 1

    # revision conflict is refused by the migrated store: stale writer loses
    try:
        plans.revise(design_project_id, plan_id, {
            "objective": "过期写入应被拒绝", "output_type": PLAN_OUTPUT_TYPE,
            "created_by": "owner", "expected_revision": revision})
        raise AssertionError("stale revision write should be refused")
    except ValueError as error:
        assert getattr(error, "code", "") == "ASSISTANCE_PLAN_REVISION_CONFLICT"

    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design",
        "title": "设计样例：分镜方案修订执行",
        "input_refs": [{"kind": "design_plan_ref", "design_project_id": design_project_id,
                        "plan_id": plan_id},
                       {"kind": "target_profile_ref", "profile_key": PROFILE_KEY,
                        "entry_mode": "MANUAL_COPY"}],
        "acceptance": {"professional_required": True, "delivery": "分镜表一份",
                       "data_origin": "test"}})
    assert status == 201, task
    task_id = task["task_id"]

    status, attempt = server.client.post(f"/api/v1/tasks/{task_id}/attempts",
                                         {"idempotency_key": "att-design-1"})
    assert status == 201
    attempt_id = attempt["attempt_id"]

    status, pack_response = server.client.post(f"/api/v1/attempts/{attempt_id}/pack", {})
    assert status == 201, pack_response
    pack_ref = pack_response["pack_ref"]
    assert pack_ref["flavor"] == "design_task_pack"
    assert pack_ref["plan_id"] == plan_id
    assert pack_ref["plan_revision"] == revision + 1
    # the pack now pins content, not a name: a digest of the stored revision row
    # and one binding digest over the whole combination.
    # the design store publishes a revision digest as sha256:<hex>; the pack carries
    # that exact spelling, and the binding digest is this envelope's own canonical one
    assert pack_ref["plan_content_sha256"].startswith("sha256:")
    assert len(pack_ref["plan_content_sha256"]) == len("sha256:") + 64
    assert len(pack_response["attempt"]["binding_sha256"]) == 64
    binding_profile = pack_ref["target_bindings"][0]
    assert binding_profile["profile_id"].startswith("tprof-")
    assert binding_profile["content_sha256"].startswith("sha256:")
    assert pack_ref["revision_policy"] == "LATEST_AT_PACK"
    pack_body = pack_response["pack_body"]
    assert "分镜" in pack_body
    assert pack_response["attempt"]["execution_state"] == "WAITING_HANDOFF"
    assert pack_response["attempt"]["data_origin"] == "test", "an attempt inherits its task"

    status, handoff = server.client.post(f"/api/v1/attempts/{attempt_id}/handoff-declarations", {
        "claim": "userDeclaredHandoff", "target_version": "plan-r" + str(revision + 1),
        "claimed_recipient": "外部设计工具（人工复制）", "actor": "user"})
    assert status == 200, handoff

    status, imported = server.client.post(f"/api/v1/attempts/{attempt_id}/results", {
        "result": {"schemaVersion": "ai-work-lab/design-result/v1",
                   "resultId": "res-design-1",
                   "designProjectId": design_project_id,
                   "planId": plan_id,
                   "planRevision": revision + 1,
                   "targetVersion": "plan-r" + str(revision + 1),
                   "producedAt": produced_after(handoff),
                   "summary": "外部工具已按修订执行（测试夹具）",
                   "evidenceRefs": ["design-plan-readback:" + plan_id]},
        "data_origin": "test"})
    assert status == 201, imported
    result_id = imported["result"]["result_id"]
    assert imported["result"]["data_origin"] == "test"
    assert imported["result"]["binding"]["plan_content_sha256"] == pack_ref["plan_content_sha256"]

    # technical axis: the pinned plan revision reads back → PASS
    status, technical = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                           {"axis": "technical"})
    assert status == 201
    assert technical["outcome"] == "PASS", technical
    assert technical["current_validity"] == "CURRENT", technical
    assert technical["data_origin"] == "test", "a verdict inherits its result's origin"
    assert technical["checks"]["pinned_content_matches_readback"] is True

    # professional acceptance without a named human stays PENDING — always
    status, pending = server.client.post(f"/api/v1/results/{result_id}/verifications",
                                         {"axis": "professional"})
    assert status == 201
    assert pending["outcome"] == "PENDING"

    status, body = server.client.post(f"/api/v1/results/{result_id}/verifications", {
        "axis": "professional", "professional_verdict": "PASS"})
    assert status == 409
    assert body["error"].startswith("PROFESSIONAL_VERDICT_NEEDS_LOCAL_APPROVAL")
    # an agent reference is refused before the ledger is even consulted
    status, agent = server.client.post(f"/api/v1/results/{result_id}/verifications", {
        "axis": "professional", "professional_verdict": "PASS",
        "verifier_ref": "agent:qoder-synthetic"})
    assert status == 409, agent
    assert agent["error"].startswith("VERIFIER_REF_NOT_HUMAN"), agent

    # a verdict stays PENDING while the technical axis is not yet satisfied either:
    # the task is ACTIVE, not completed
    status, mid = server.client.get(f"/api/v1/tasks/{task_id}")
    assert mid["lifecycle"] == "ACTIVE"

    # with a named human verdict that resolves in the local ledger, the task completes
    approval_id = _fixture_approval(server, result_id,
                                    imported["result"]["content_sha256"])
    status, accepted = server.client.post(f"/api/v1/results/{result_id}/verifications", {
        "axis": "professional", "professional_verdict": "PASS", "approval_ref": approval_id})
    assert status == 201, accepted
    assert accepted["outcome"] == "PASS"
    assert accepted["identity_state"] == "ATTESTED_AT_LOCAL_GATE", accepted
    assert accepted["data_origin"] == "test", "a fixture approval is a test record"

    status, done = server.client.get(f"/api/v1/tasks/{task_id}")
    assert done["lifecycle"] == "COMPLETED"

    # a professional-only completion is impossible: a second task with no technical
    # verdict cannot be completed through the store either
    status, task2 = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design",
        "title": "设计样例二：无技术核验",
        "input_refs": [{"kind": "design_plan_ref", "design_project_id": design_project_id,
                        "plan_id": plan_id}],
        "acceptance": {"professional_required": True, "data_origin": "test"}})
    assert status == 201
    assert task2["lifecycle"] in ("DRAFT", "READY", "ACTIVE")

    from backend.core.unified_store import StoreError, UnifiedStore
    store = UnifiedStore(server.local_root / "unified.sqlite3")
    try:
        try:
            store.set_task_lifecycle(task2["task_id"], "COMPLETED")
            raise AssertionError("a task with no verdict chain cannot be marked COMPLETED")
        except StoreError as error:
            assert str(error).startswith("COMPLETION_UNSUPPORTED"), error
    finally:
        store.close()


def test_target_profile_reference_must_address_a_real_profile(server):
    """"A combination member that cannot be resolved is refused, not dropped."""
    status, project = server.client.post("/api/v1/projects", {
        "name": "引用样例", "source": "design", "data_origin": "test"})
    assert status == 201
    design_project_id = project["root_path"]
    created = _create_plan(server, design_project_id)
    status, task = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "无地址的目标档案",
        "input_refs": [{"kind": "design_plan_ref", "design_project_id": design_project_id,
                        "plan_id": created["plan"]["plan_id"]},
                       {"kind": "target_profile_ref", "software_ref": "storyboarder",
                        "entry_mode": "MANUAL_COPY"}],
        "acceptance": {"data_origin": "test"}})
    assert status == 201, task
    status, attempt = server.client.post(f"/api/v1/tasks/{task['task_id']}/attempts",
                                         {"idempotency_key": "att-unresolved"})
    assert status == 201
    status, body = server.client.post(f"/api/v1/attempts/{attempt['attempt_id']}/pack", {})
    assert status == 409, body
    assert body["error"].startswith("TARGET_PROFILE_REF_UNRESOLVED")

    status, unknown = server.client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "design", "title": "不存在的档案键",
        "input_refs": [{"kind": "design_plan_ref", "design_project_id": design_project_id,
                        "plan_id": created["plan"]["plan_id"]},
                       {"kind": "target_profile_ref", "profile_key": "no-such--key--x"}],
        "acceptance": {"data_origin": "test"}})
    assert status == 201
    status, attempt2 = server.client.post(f"/api/v1/tasks/{unknown['task_id']}/attempts",
                                          {"idempotency_key": "att-unknown-key"})
    status, body = server.client.post(f"/api/v1/attempts/{attempt2['attempt_id']}/pack", {})
    assert status == 409, body
    assert body["error"].startswith("TARGET_PROFILE_KEY_UNKNOWN")
