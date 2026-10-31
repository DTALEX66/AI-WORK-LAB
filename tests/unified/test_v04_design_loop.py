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

The two ``knowledge_candidate`` nodes at the end close the gap register row
``05#L14|candidate`` named as "本仓无 pytest 断言候选导出为「读回不是发送」": over real
HTTP they require a locally contract-valid, human-approved, fully assembled export
document to leave ``outbound.transport == "NOT_CONNECTED"``, ``sent_count == 0`` and
``last_attempt_at is null`` untouched, and they require each contract refusal to
leave no stored row. Same honesty limit as the fixture approval above: the reviewer
identity used here is a fixture, not a person.
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


# ================================================== knowledge candidate readback (05#L14|candidate)
# 登记行 05#L14|candidate 说「本仓无 pytest 断言候选导出为『读回不是发送』」。下面两个节点
# 走真实 HTTP（server fixture 起的是真 `python -m backend`），把这句话变成可跑的检查：
# 列表读回、人工门批准、导出组装、然后读回仍然说自己一个字节都没发出去。
# 所有正文都是合成夹具；`reviewer_id` 用的是夹具身份，只证明机制，不代表真人审阅。

#: 合同必填的七个键（http_service._create_knowledge_candidate 的 body(fields=...) 就是这个集合）。
CANDIDATE_FIELDS = frozenset({"candidate_id", "candidate_type", "source", "rights", "payload",
                              "created_at", "revocation_entrypoint"})
#: 合成来源修订：不是任何仓库的提交，故意选一个必然与本机 HEAD 不一致的值（除非测试自己给出）。
SYNTHETIC_DESIGN_LAB_SHA = "deadbeef1234567"
SYNTHETIC_EVIDENCE_SHA = "sha256:" + "ab" * 32
CANDIDATE_CREATED_AT = "2026-09-12T00:00:00Z"
OUTBOUND_KEYS = ("transport", "destination", "sent_count", "last_attempt_at", "note")


def _candidate_route(project_id: str) -> str:
    return f"/api/projects/{project_id}/knowledge-candidates"


def _candidate_body(candidate_id: str, *, design_lab_sha: str = SYNTHETIC_DESIGN_LAB_SHA,
                    **overrides) -> dict:
    """一份合同合法的合成候选；`rights_gate_state` 由夹具声明，不代表做过真实权利判定。"""
    body = {
        "candidate_id": candidate_id,
        "candidate_type": "METHOD",
        "source": {"design_lab_sha": design_lab_sha, "job_id": "UNUSED",
                   "operation_id": "UNUSED", "evidence_sha256": SYNTHETIC_EVIDENCE_SHA},
        "rights": {"rights_gate_state": "CHECKED", "license_id": "MIT",
                   "contains_client_asset": False, "contains_third_party_asset": False,
                   "redaction_note": None},
        "payload": {"title": "分镜节奏方法（合成夹具）",
                    "statement": "先确认叙事信息密度，再决定镜头数量。",
                    "applies_to": ["motion-video"]},
        "created_at": CANDIDATE_CREATED_AT,
        "revocation_entrypoint": "design-lab/knowledge/revoke",
    }
    body.update(overrides)
    return body


def _read_back(server, design_project_id: str) -> dict:
    status, body = server.client.get(_candidate_route(design_project_id))
    assert status == 200, body
    return body


def _assert_never_sent(readback: dict, *, where: str) -> None:
    """读回里「发送」三件事必须是同一个说法：没接传输、发了 0 条、连一次尝试都没有。"""
    outbound = readback["outbound"]
    assert set(outbound) == set(OUTBOUND_KEYS), (where, sorted(outbound))
    assert outbound["transport"] == "NOT_CONNECTED", (where, outbound)
    assert outbound["destination"] == "ArcheAxis", (where, outbound)
    assert outbound["sent_count"] == 0, (where, outbound)
    assert outbound["last_attempt_at"] is None, (where, outbound)
    assert "从未发送" in outbound["note"], (where, outbound)


def test_knowledge_candidate_readback_is_a_read_and_never_a_send(server):
    """05#L14 的正证：候选可以本地合同合格、可以组装出导出文档，读回仍说一个字节都没发出。

    证明：
    * 新建候选只能是 PENDING_HUMAN_APPROVAL——合同的七个入参里没有任何 review 字段，
      多带一个 review 键会在门前就被拒（见第二个测试）；
    * 列表读回的 outbound 五项：transport=NOT_CONNECTED、destination=ArcheAxis、
      sent_count=0、last_attempt_at=null、note 说明「从未发送，不是一次失败的重试」；
    * 夹具人工门批准后 export_ready_count 从 0 变 1，而上述三项一动不动——
      「本地合同允许导出」与「已发送」是两个侧面，这正是登记行要的证据；
    * GET …/export 组装成功（200，status=CANDIDATE_EXPORT，outbound.bytes>0）之后再次读回
      列表，sent_count 仍是 0、last_attempt_at 仍是 null：组装与读回都不是发送；
    * 导出信封自己也只报 bytes（组装了多少字节）而不报任何发送时刻，
      does_not_say 是非空列表并写明传输未实现；
    * provenance 里 job_id/operation_id 原样回读为 "UNUSED"，状态写
      EXPLICITLY_UNUSED——服务没有替任何人补一个标识；
    * freshness 只比较 design_lab_sha 与本机 HEAD（这里用读回自己给出的 head_sha，
      所以是 CURRENT），CURRENT 也不改变发送三项：修订一致 ≠ 已经同步。

    没证明：任何真实传输（本仓没有 ArcheAxis 传输实现，也不许有）；夹具的
    `reviewer_id="夹具审阅人"` 与 `rights_gate_state="CHECKED"` 都是操作者 supplied 的字段，
    服务无法证明这个人真实存在或真的做过权利判定——合同自己的 does_not_say 就是这么写的。
    """
    status, project = server.client.post("/api/v1/projects", {
        "name": "知识候选读回", "source": "design", "data_origin": "test"})
    assert status == 201, project
    design_project_id = project["root_path"]
    assert len(design_project_id) == 32 and design_project_id == design_project_id.lower(), \
        design_project_id  # 路由只接 [0-9a-f]{32}
    route = _candidate_route(design_project_id)

    empty = _read_back(server, design_project_id)
    assert empty["schemaVersion"] == "design-lab/assurance-knowledge-candidate-readback/v1", empty
    assert set(empty) == {"schemaVersion", "project_id", "candidates", "candidate_count",
                          "unreadable_count", "pending_review_count", "approved_count",
                          "rejected_count", "revoked_count", "export_ready_count", "conflicts",
                          "revocation_receipts", "head_sha", "outbound", "does_not_say"}, \
        sorted(empty)
    assert empty["project_id"] == design_project_id
    assert empty["candidate_count"] == len(empty["candidates"]) == 0, empty
    _assert_never_sent(empty, where="empty ledger")
    assert isinstance(empty["does_not_say"], list) and empty["does_not_say"], empty["does_not_say"]
    assert any("传输未实现" in line for line in empty["does_not_say"]), empty["does_not_say"]

    # 新鲜度用服务自己读回的 HEAD，避免由测试编造一个修订号
    head = empty["head_sha"]
    hex_digits = set("0123456789abcdef")
    if isinstance(head, str) and head and set(head.lower()) <= hex_digits:
        used_sha = head[:12]
        expected_freshness = "CURRENT"
    else:
        used_sha = SYNTHETIC_DESIGN_LAB_SHA
        expected_freshness = "UNKNOWN"

    status, created = server.client.post(route, _candidate_body("kb-synthetic-0001",
                                                               design_lab_sha=used_sha))
    assert status == 201, created
    assert created["schemaVersion"] == "design-lab/assurance-knowledge-candidate/v2", created
    assert created["review"]["state"] == "PENDING_HUMAN_APPROVAL", created["review"]
    assert created["review"]["reviewer_id"] is None, created["review"]
    assert created["review"]["reviewer_kind"] is None, created["review"]
    assert created["created_at"] == CANDIDATE_CREATED_AT, created["created_at"]
    assert created["supersedes"] is None, created["supersedes"]
    assert created["revocation"] == {"revocable": True,
                                     "entrypoint": "design-lab/knowledge/revoke",
                                     "state": "ACTIVE", "reason": None, "revoked_by": None,
                                     "revoked_at": None}, created["revocation"]
    assert created["source"]["job_id"] == "UNUSED" and created["source"]["operation_id"] == "UNUSED"

    listed = _read_back(server, design_project_id)
    assert listed["candidate_count"] == 1 and listed["pending_review_count"] == 1, listed
    assert listed["approved_count"] == 0 and listed["export_ready_count"] == 0, listed
    row = listed["candidates"][0]
    assert row["candidate_id"] == "kb-synthetic-0001", row
    assert row["review_state"] == "PENDING_HUMAN_APPROVAL", row
    assert row["export_ready"] is False, row
    assert "PENDING_HUMAN_APPROVAL" in row["export_blocked_by"], row["export_blocked_by"]
    assert row["freshness"] == expected_freshness, (row, head, used_sha)
    _assert_never_sent(listed, where="pending candidate")

    # 合同不合格时导出不给 200 空体，而是具名拒绝（读回不是发送的另一半）
    status, refused = server.client.get(route + "/kb-synthetic-0001/export")
    assert status == 409, refused
    assert refused["error"] == "CANDIDATE_EXPORT_REFUSED", refused
    assert "PENDING_HUMAN_APPROVAL" in refused["detail"], refused

    # 夹具人工门：机制为真，专业/权利判定为假（does_not_say 第三条自己就这么说）
    status, approved = server.client.post(route + "/kb-synthetic-0001/review", {
        "decision": "APPROVE", "reviewer_id": "夹具审阅人", "reviewer_kind": "human",
        "reviewed_at": "2026-09-13T00:00:00Z", "note": None, "reason": None})
    assert status == 200, approved
    assert approved["review"]["state"] == "APPROVED", approved["review"]
    assert approved["review"]["reviewer_kind"] == "human", approved["review"]

    ready = _read_back(server, design_project_id)
    assert ready["approved_count"] == 1, ready
    assert ready["export_ready_count"] == 1, ready  # 本地合同此刻允许导出
    assert ready["candidates"][0]["export_ready"] is True, ready["candidates"][0]
    assert ready["candidates"][0]["export_blocked_by"] is None, ready["candidates"][0]
    # 这就是登记行的全部含义：export_ready 变了，发送三件事一件都没变
    _assert_never_sent(ready, where="export-ready candidate")
    assert ready["candidate_count"] == ready["pending_review_count"] + ready["approved_count"]

    status, envelope = server.client.get(route + "/kb-synthetic-0001/export")
    assert status == 200, envelope
    assert envelope["schemaVersion"] == \
        "design-lab/assurance-knowledge-candidate-export-envelope/v1", envelope
    assert envelope["status"] == "CANDIDATE_EXPORT", envelope
    assert envelope["revision"] == 2, envelope  # 批准是追加的第二版，不是原地改写
    # 导出信封的 outbound 只说三件事：没接传输、发了 0 条、这次组装出了多少字节。
    # bytes 是「组装」的计量，不是「发出」的计量；信封里没有任何发送时刻。
    assert set(envelope["outbound"]) == {"transport", "sent_count", "bytes"}, envelope["outbound"]
    assert envelope["outbound"]["transport"] == "NOT_CONNECTED", envelope["outbound"]
    assert envelope["outbound"]["sent_count"] == 0, envelope["outbound"]
    assert envelope["outbound"]["bytes"] > 0, envelope["outbound"]
    # 信封里没有任何「已发送/已送达/已确认」的时刻或字段
    assert not [key for key in envelope
                if any(mark in key.lower() for mark in
                       ("sent_at", "delivered", "acknowledged", "transmitted"))], sorted(envelope)
    assert not [key for key in envelope["outbound"] if key not in
                ("transport", "sent_count", "bytes")], envelope["outbound"]
    assert envelope["export"]["schemaVersion"] == \
        "design-lab/assurance-knowledge-candidate-export/v1", envelope["export"]
    assert envelope["export"]["review"] == {"state": "APPROVED", "reviewer_id": "夹具审阅人",
                                            "reviewer_kind": "human",
                                            "reviewed_at": "2026-09-13T00:00:00Z"}, \
        envelope["export"]["review"]
    assert envelope["v1_projection"]["schemaVersion"] == \
        "design-lab/candidate-knowledge/v1", envelope["v1_projection"]
    # V1 词表里的 "compiled" 是「人已批」的投影写法，不是交付回执；compiled_ref 保持 null，
    # 因为这个服务没有编译出任何可引用的产物。
    assert envelope["v1_projection"]["state"] == "compiled", envelope["v1_projection"]
    assert envelope["v1_projection"]["compiled_ref"] is None, envelope["v1_projection"]
    assert envelope["provenance"] == {"job_id": "UNUSED", "operation_id": "UNUSED",
                                      "job_id_state": "EXPLICITLY_UNUSED",
                                      "operation_id_state": "EXPLICITLY_UNUSED",
                                      "design_lab_sha": used_sha,
                                      "payload_sha256": envelope["export"]["payload_sha256"]}, \
        envelope["provenance"]
    assert envelope["freshness"] == expected_freshness, envelope["freshness"]
    assert isinstance(envelope["does_not_say"], list) and envelope["does_not_say"]

    # 导出组装完成之后，读回依旧不发送
    after_export = _read_back(server, design_project_id)
    _assert_never_sent(after_export, where="after an assembled export")
    assert after_export["export_ready_count"] == 1, after_export


def test_knowledge_candidate_creation_refusals_leave_no_row_and_no_approval(server):
    """05#L14 的反证：合同拒绝就是拒绝——不写半行、不给 APPROVED、也不冒充已发送。

    证明：
    * `contains_client_asset=True` 而缺 `redaction_note` → 400
      KNOWLEDGE_CANDIDATE_REFUSED，detail 原句点名 redaction_note（按 handler 真实返回码
      与错误码断言，不是「我认为应该是」）；redaction_note 里带本机盘符路径同样被拒；
    * `candidate_id` 不合法（含空格 / 超过 80 字符）→ 400 CANDIDATE_ID_INVALID：一个后续
      review/revoke 路由无法寻址的 id 在门前就被挡下；
    * 请求体多带一个 `review` 键 → 400 INVALID_PROJECT_FIELDS：没有任何入参能把候选写成
      APPROVED，批准只能走人工门路由；
    * candidate_type / rights_gate_state / 布尔位 / evidence_sha256 的枚举与形状都各有一条
      具名拒绝；
    * 上述每一次拒绝之后，列表读回 candidate_count 仍是 0（没有半行残留），
      export_ready_count 仍是 0，发送三件事仍是 NOT_CONNECTED / 0 / null；
    * 最后一条合法 POST 让计数从 0 变 1，证明前面的 0 不是「路由根本写不进去」；
    * 用 agent 身份走人工门 → 400 KNOWLEDGE_HUMAN_REVIEW_REQUIRED，读回里该行仍是
      PENDING_HUMAN_APPROVAL、approved_count 仍是 0。

    没证明：权利门该不该开、这个人是谁——本测试只验证拒绝形状。
    """
    status, project = server.client.post("/api/v1/projects", {
        "name": "知识候选拒绝面", "source": "design", "data_origin": "test"})
    assert status == 201, project
    design_project_id = project["root_path"]
    route = _candidate_route(design_project_id)

    assert _read_back(server, design_project_id)["candidate_count"] == 0

    client_asset = _candidate_body("kb-refused-0001", rights={
        "rights_gate_state": "CHECKED", "license_id": "MIT", "contains_client_asset": True,
        "contains_third_party_asset": False})
    blank_note = _candidate_body("kb-refused-0002", rights={
        "rights_gate_state": "CHECKED", "license_id": "MIT", "contains_client_asset": True,
        "contains_third_party_asset": False, "redaction_note": "   "})
    leaked_note = _candidate_body("kb-refused-0003", rights={
        "rights_gate_state": "CHECKED", "license_id": "MIT", "contains_client_asset": True,
        "contains_third_party_asset": False, "redaction_note": "去除了 D:/All projects 的客户层"})
    spacey_id = _candidate_body("kb synthetic 0004")
    long_id = _candidate_body("kb-" + "x" * 80)
    wrong_type = _candidate_body("kb-refused-0006", candidate_type="REFERENCE")
    wrong_rights_state = _candidate_body("kb-refused-0007", rights={
        "rights_gate_state": "APPROVED", "license_id": "MIT", "contains_client_asset": False,
        "contains_third_party_asset": False, "redaction_note": None})
    string_bool = _candidate_body("kb-refused-0008", rights={
        "rights_gate_state": "CHECKED", "license_id": "MIT", "contains_client_asset": "true",
        "contains_third_party_asset": False, "redaction_note": None})
    zero_digest = _candidate_body("kb-refused-0009", source={
        "design_lab_sha": SYNTHETIC_DESIGN_LAB_SHA, "job_id": "UNUSED", "operation_id": "UNUSED",
        "evidence_sha256": "sha256:" + "0" * 64})

    expectations = (
        (client_asset, 400, "KNOWLEDGE_CANDIDATE_REFUSED", "redaction_note"),
        (blank_note, 400, "KNOWLEDGE_CANDIDATE_REFUSED", "redaction_note"),
        (leaked_note, 400, "KNOWLEDGE_CANDIDATE_REFUSED", "Windows drive path"),
        (spacey_id, 400, "CANDIDATE_ID_INVALID", "candidate_id must match"),
        (long_id, 400, "CANDIDATE_ID_INVALID", "candidate_id must match"),
        (wrong_type, 400, "KNOWLEDGE_CANDIDATE_REFUSED", "candidate_type must be one of"),
        (wrong_rights_state, 400, "KNOWLEDGE_CANDIDATE_REFUSED", "rights.rights_gate_state"),
        (string_bool, 400, "KNOWLEDGE_CANDIDATE_REFUSED", "must be a boolean"),
        (zero_digest, 400, "KNOWLEDGE_CANDIDATE_REFUSED", "evidence_sha256"),
    )
    for body, want_status, want_code, want_detail in expectations:
        assert set(body) == set(CANDIDATE_FIELDS), sorted(body)
        status, refused = server.client.post(route, body)
        assert status == want_status, (want_code, status, refused)
        assert refused.get("error") == want_code, (want_code, refused)
        assert want_detail in refused.get("detail", ""), (want_detail, refused)
        still_empty = _read_back(server, design_project_id)
        assert still_empty["candidate_count"] == 0, (refused, still_empty["candidates"])
        assert still_empty["unreadable_count"] == 0 and still_empty["conflicts"] == []
        assert still_empty["export_ready_count"] == 0
        _assert_never_sent(still_empty, where="after a refusal")

    # 请求面自己也关着：合同没有 review 入参，多带一个键连门都进不来
    status, extra = server.client.post(route, {**_candidate_body("kb-refused-0010"),
                                               "review": {"state": "APPROVED"}})
    assert status == 400, extra
    assert extra.get("error") == "INVALID_PROJECT_FIELDS", extra

    status, created = server.client.post(route, _candidate_body("kb-accepted-0001"))
    assert status == 201, created
    moved = _read_back(server, design_project_id)
    assert moved["candidate_count"] == 1, moved  # 上面的 0 不是「路由写不进去」
    assert moved["pending_review_count"] == 1 and moved["approved_count"] == 0, moved
    assert created["review"]["state"] == "PENDING_HUMAN_APPROVAL", created["review"]

    status, agent = server.client.post(route + "/kb-accepted-0001/review", {
        "decision": "APPROVE", "reviewer_id": "agent:synthetic", "reviewer_kind": "agent",
        "reviewed_at": "2026-09-13T00:00:00Z", "note": None, "reason": None})
    assert status == 400, agent
    assert agent.get("error") == "KNOWLEDGE_HUMAN_REVIEW_REQUIRED", agent
    unchanged = _read_back(server, design_project_id)
    assert unchanged["approved_count"] == 0 and unchanged["pending_review_count"] == 1, unchanged
    assert unchanged["candidates"][0]["review_state"] == "PENDING_HUMAN_APPROVAL"
    assert unchanged["candidates"][0]["reviewer_id"] is None, unchanged["candidates"][0]
    _assert_never_sent(unchanged, where="after an agent review attempt")


# ============================================= design asset readback (05#L22|design-assets)
# 登记行 05#L22|design-assets 的核心验收：「输入/输出/版本/引用可恢复，不扩素材平台」。
# 登记位置是兼容面路由
# `GET /api/projects/([0-9a-f]{32})/assets(?:/(img-[0-9a-f]{64})/content)?`、handler
# `design_lab.http_service._list_or_read_assets`；该行状态为 IMPLEMENTED_UNVERIFIED、
# 验证证据 NONE——本仓此前没有任何断言说这句话成立或不成立。下面四个节点把它拆成四条
# 可跑的检查，全走真实 HTTP（`server` fixture 起的是真服务），素材一律是测试自己合成的
# 字节，不读任何真实用户素材目录，也不联网。
#
# 断言按读到的真实形状写，先记下三件与直觉不同、必须写进证据的事：
# * `_list_or_read_assets` 只有两个动作：`ImageAssets.list`（集合）与 `ImageAssets.content`
#   （单份字节，base64 内联）。`ImageAssets._read` 的 SQL 写死了 `asset_kind='raster'` 和
#   `v.version_no=MAX(...)`（源码注释说明这是刻意的「当前版本」规则），所以这条路由按构造
#   只回栅格输入、只回当前版本：「历史版本可读」不可能靠这条路由多出一行去证明。真正的
#   不可变历史在台账里——`asset_store._record_version` 只 INSERT、从不改写旧行，每一版的
#   字节各自落在 `projects/<pid>/assets/versions/<publication_id>/` 互不重叠的位置，由同一
#   个类的 `_verified`（路由每次读回都走它）现算摘要比对。所以下面的历史读回走 `_verified`：
#   产品自己的校验器，不是测试把校验逻辑重写一遍再自证。
# * `POST /assets` 用 `sha256(project_id + ':' + idempotency_key)` 铸造 `asset_id`，换一把
#   幂等键得到的是**另一个资产**，不是同一资产的第二版。同一资产的第二版只能走
#   `import_image` 自己调用的那组 store 写入 API（`register_asset` → `acquire_writer` →
#   `writer_token` → `publish_version` → `release_writer`，外加 attempt 状态机）；下面的
#   `_publish_next_version` 逐字镜像这段调用序。
# * 「不扩素材平台」在这一面上是可以机验的缺席：路由表里该家族只有 4 条、方法只有 GET/POST，
#   读回载荷的键集合闭合在 8 个本地字段，没有任何「已同步/已上传/远程地址」的说法。
# 本节的「可恢复」边界（没证明的部分，写在节点里）：同一台机器、同一进程内的服务实例重开
# （对同一 workspace 目录再 build 一个真服务、另开数据库连接）读回是证了；**操作系统进程
# 重启、机器重启、断电后 rename 的可见性、`recover_publications` 的崩溃恢复语义都没有在这里
# 验证**——那是 store 的另一个面，也不该被这一行验收顺手宣称掉。

import base64
import hashlib
import io
import re
import secrets
import sqlite3
import threading
import time
from contextlib import closing, contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

#: 登记行「当前实现位置」那一列的原样，节点直接拿它对照路由表，不另抄一份说法。
ASSETS_ROUTE = r"/api/projects/([0-9a-f]{32})/assets(?:/(img-[0-9a-f]{64})/content)?"
RASTER_ID_PATTERN = re.compile(r"img-[0-9a-f]{64}")
VERSION_ID_PATTERN = re.compile(r"v-[0-9a-f]{32}")
DIGEST_PATTERN = re.compile(r"sha256:[0-9a-f]{64}")
#: 一次栅格读回的全部键——真实形状，不多不少（第四条断言把它当闭合集合校验）。
RASTER_RECORD_KEYS = frozenset({"id", "version_id", "sha256", "byte_size", "rights",
                                "width", "height", "media_type"})
#: 输出侧的键集合与输入侧不同：没有 media_type/width/height，多了 kind/version_no/verification。
NATIVE_RECORD_KEYS = frozenset({"id", "kind", "version_id", "version_no", "byte_size",
                                "sha256", "rights", "verification"})
#: 素材平台的说法必须整体缺席：路由表的 pattern/action 与载荷的每个键名都不许出现这些词根。
PLATFORM_WORDS = ("upload", "sync", "remote", "fetch", "pull", "push", "download",
                  "platform", "cdn", "provider", "url", "link", "href", "location",
                  "etag", "proxy", "webhook", "external")
#: 该家族在 `ROUTES` 里的全部四条：一条集合读、一份字节读、两条本地派生写。没有第五条。
ASSET_SURFACE_ROUTES = (
    ("GET", ASSETS_ROUTE, "_list_or_read_assets"),
    ("POST", r"/api/projects/([0-9a-f]{32})/assets", "_import_asset"),
    ("POST", r"/api/projects/([0-9a-f]{32})/assets/(img-[0-9a-f]{64})/analysis",
     "_derive_asset_analysis"),
    ("POST", r"/api/projects/([0-9a-f]{32})/assets/(img-[0-9a-f]{64})/prompt-reversal",
     "_reverse_asset_prompt"),
)


def _synthetic_png(width: int, height: int, rgb: tuple) -> bytes:
    """测试自己生成的 PNG：本项目没有任何一处读取真实用户素材目录。"""
    from PIL import Image
    stream = io.BytesIO()
    Image.new("RGB", (width, height), rgb).save(stream, format="PNG")
    return stream.getvalue()


def _design_project(server, name: str) -> str:
    """统一登记一个 design 项目；`root_path` 就是兼容面路由用的 32 位十六进制项目 id。"""
    status, project = server.client.post("/api/v1/projects", {
        "name": name, "source": "design", "data_origin": "test"})
    assert status == 201, project
    design_project_id = project["root_path"]
    assert re.fullmatch(r"[0-9a-f]{32}", design_project_id), design_project_id
    return design_project_id


def _assets_url(project_id: str) -> str:
    return f"/api/projects/{project_id}/assets"


def _content_url(project_id: str, asset_id: str) -> str:
    return f"{_assets_url(project_id)}/{asset_id}/content"


def _record_url(project_id: str, asset_id: str, kind: str) -> str:
    """按 kind 选这一面的读回面：栅格走登记行那条兼容路由，宿主产物走 native-assets 的校验面。

    两个侧面本来就是两条路由（见断言三），所以「发布后读回当前记录」这句话也必须分头说。
    """
    if kind == "raster":
        return _content_url(project_id, asset_id)
    return f"/api/projects/{project_id}/native-assets/{asset_id}/verify"


def _import_asset(server, project_id: str, data: bytes, idempotency_key: str) -> dict:
    """真实 HTTP 登记一份输入素材，返回服务给出的那份资产记录（当前版本的引用标识）。"""
    status, created = server.client.post(_assets_url(project_id), {
        "content_base64": base64.b64encode(data).decode("ascii"),
        "idempotency_key": idempotency_key})
    assert status == 201, created
    return created


def _version_rows(service, asset_id: str) -> list:
    """台账里的全部版本行（按 version_no 升序）：这一句就是「历史是不是追加式」的读数。"""
    with closing(sqlite3.connect(service.database.as_uri() + "?mode=ro", uri=True)) as conn:
        return [dict(zip(("version_id", "version_no", "content_sha256", "state"), row))
                for row in conn.execute(
                    "SELECT version_id, version_no, content_sha256, state FROM asset_version "
                    "WHERE asset_id=? ORDER BY version_no", (asset_id,)).fetchall()]


def _artifact_row(service, asset_id: str, version_id: str):
    """`ImageAssets._verified` 期望的那一行五元组，与 `_read` 的 SELECT 同形同序。"""
    with closing(sqlite3.connect(service.database.as_uri() + "?mode=ro", uri=True)) as conn:
        row = conn.execute(
            "SELECT a.asset_id,v.version_id,f.path,f.sha256,f.byte_size FROM asset a "
            "JOIN asset_version v ON a.asset_id=v.asset_id "
            "JOIN artifact f ON f.version_id=v.version_id "
            "WHERE a.asset_id=? AND v.version_id=?", (asset_id, version_id)).fetchone()
    assert row is not None, (asset_id, version_id)
    return row


def _artifact_paths(service, asset_id: str) -> list:
    with closing(sqlite3.connect(service.database.as_uri() + "?mode=ro", uri=True)) as conn:
        return [row[0] for row in conn.execute(
            "SELECT f.path FROM asset_version v JOIN artifact f ON f.version_id=v.version_id "
            "WHERE v.asset_id=? ORDER BY v.version_no", (asset_id,)).fetchall()]


def _asset_kind(service, asset_id: str):
    with closing(sqlite3.connect(service.database.as_uri() + "?mode=ro", uri=True)) as conn:
        row = conn.execute("SELECT asset_kind FROM asset WHERE asset_id=?", (asset_id,)).fetchone()
    return row[0] if row else None


def _publish_next_version(server, project_id: str, asset_id: str, *, kind: str, data: bytes,
                          idempotency_key: str, artifact_name: str, scope: str) -> dict:
    """把同一 `asset_id` 的第二版字节发进去，调用序逐字镜像 `image_assets.import_image`。

    换幂等键只会铸出新资产，所以「同一资产改版」只能走 store 的写入 API；这里不写 SQL、
    不绕过 writer 锁：真实 attempt 作为租约持有者、真实 `publish_version` 落盘并登记摘要、
    真实 `release_writer` 释放。发布后从兼容面路由读回，返回服务认定的当前版本记录。
    """
    from design_lab.runtime import asset_store as assets, job_store as jobs
    from design_lab.runtime.attempt_contract import request_hash

    digest = "sha256:" + hashlib.sha256(data).hexdigest()
    identity = hashlib.sha256((project_id + ":" + idempotency_key).encode()).hexdigest()
    operation, job = "revision-" + identity, "job-" + identity
    service, owner = server.design_service, server.design_service.paths.project_root
    with closing(jobs.connect(service.database, project_root=owner)) as conn:
        attempt = jobs.begin_attempt(
            conn, job, operation_id=operation, idempotency_scope=scope + ":" + project_id,
            idempotency_key=idempotency_key,
            request_hash=request_hash({"project": project_id, "sha256": digest}))
        attempt = jobs.transition(conn, attempt["attempt_id"], "RUNNING")
        attempt_id = attempt["attempt_id"]
        source = service.paths.category_dir("runtime", "asset-revisions", attempt_id) / "input"
        source.parent.mkdir(parents=True, exist_ok=True)
        source.write_bytes(data)
        with closing(assets.connect(service.database, project_root=owner)) as asset_conn:
            assets.register_asset(asset_conn, project_id, asset_id, kind)
            resource = "asset:" + asset_id
            assert assets.acquire_writer(asset_conn, resource, attempt_id), "writer lease held"
            generation = assets.writer_token(asset_conn, resource, attempt_id)
            try:
                version_id = assets.publish_version(
                    asset_conn, asset_id, source,
                    store_root=service.paths.category_dir("projects", project_id, "assets"),
                    artifact_name=artifact_name, expected_sha256=digest,
                    holder_attempt_id=attempt_id, generation=generation, project_root=owner)
            finally:
                assets.release_writer(asset_conn, resource, attempt_id, generation=generation)
        jobs.transition(conn, attempt_id, "RECEIPTED", evidence={
            "operation_id": operation, "attempt_id": attempt_id, "artifact_sha256": digest,
            "readback_sha256": digest, "kind": "local-asset-revision", "rights": "NOT_REVIEWED"})
    # 新版确实进了台账，并且是台账自己认定的最新一版；随后从它所属的那一面读回同一版。
    versions = _version_rows(service, asset_id)
    assert versions[-1]["version_id"] == version_id, versions
    status, body = server.client.get(_record_url(project_id, asset_id, kind))
    assert status == 200, body
    assert body["asset"]["version_id"] == version_id, (version_id, body["asset"])
    return body["asset"]


def _register_output_asset(server, project_id: str, label: str, data: bytes) -> dict:
    """在**同一套台账**里登记一个「输出产物」：`native-` 前缀 + `asset_kind='psd'`。

    字节是合成的（一个带标签的假文档）：这一面只哈希、不解析宿主格式，所以合成字节足以
    证明输入/输出在 kind、id 前缀与读回字段上的区分，不证明任何宿主文件的可打开性。
    """
    asset_id = "native-" + hashlib.sha256(label.encode("utf-8")).hexdigest()
    assert _asset_kind(server.design_service, asset_id) is None, asset_id
    record = _publish_next_version(server, project_id, asset_id, kind="psd", data=data,
                                   idempotency_key="out-" + label, artifact_name="native.psd",
                                   scope="synthetic-output")
    assert record["id"] == asset_id, record
    return record


def _key_names(value, prefix: str = "") -> set:
    """递归收集载荷里出现的每一个键名（含嵌套），平台词扫描按名字集合而不是按字符串碰运气。"""
    if isinstance(value, dict):
        found = set()
        for key, child in value.items():
            found.add(prefix + str(key))
            found |= _key_names(child, prefix + str(key) + ".")
        return found
    if isinstance(value, list):
        return set().union(*(_key_names(item, prefix) for item in value)) if value else set()
    return set()


def _assert_no_platform_claim(value, *, where: str) -> None:
    """任何声称「已同步/已上传/远程可取」的字段都必须整体缺席：键名不含平台词根，值里没有 URL。

    值侧只扫 URL 形状（`://`、`www.`），不扫裸 `http` 四个字母——base64 正文里理论上可能碰巧
    出现这个子串，拿它当「有远程地址」的证据会把测试写成随机红。
    """
    names = _key_names(value)
    offenders = sorted(name for name in names
                       if any(word in name.lower() for word in PLATFORM_WORDS))
    assert not offenders, (where, offenders)
    text = json.dumps(value, ensure_ascii=False).lower()
    assert "://" not in text, (where, "载荷里出现了 URL scheme")
    assert not re.search(r"(https?|s3|gs|ftp|file)://", text), where
    assert "www." not in text, where


# ------------------------------------------------------------------ 四条检查（各自可复跑，配合植入反证）
def _check_version_recovery(server, project_id: str, asset_id: str, *, first: dict,
                            first_bytes: bytes, second: dict, second_bytes: bytes) -> None:
    """版本可恢复：当前版与历史版是两份不同字节，且旧版的摘要/大小没跟着新版变。"""
    from design_lab.image_assets import ImageAssets

    # (1) 路由侧的真实形状：兼容面按构造只回当前版本，同一资产也不会被列两遍。
    status, listed = server.client.get(_assets_url(project_id))
    assert status == 200, listed
    mine = [item for item in listed["assets"] if item["id"] == asset_id]
    assert len(mine) == 1, mine
    assert mine[0]["version_id"] == second["version_id"], mine[0]
    status, current = server.client.get(_content_url(project_id, asset_id))
    assert status == 200, current
    assert base64.b64decode(current["content_base64"]) == second_bytes, current["asset"]

    # (2) 台账侧：两版并存、都还是 ACTIVE、摘要互不相同、旧行的摘要与大小一个字节都没动。
    versions = _version_rows(server.design_service, asset_id)
    assert [row["version_no"] for row in versions] == [1, 2], versions
    assert {row["version_id"] for row in versions} == {first["version_id"],
                                                      second["version_id"]}, versions
    assert all(row["state"] == "ACTIVE" for row in versions), versions
    assert versions[0]["content_sha256"] == first["sha256"], versions
    assert versions[1]["content_sha256"] == second["sha256"], versions
    assert versions[0]["content_sha256"] != versions[1]["content_sha256"], versions

    # (3) 字节侧：两版各自的可变位置互不重叠，旧位置不是被覆盖的；产品自己的 `_verified`
    #     现算摘要后仍能把两版都认下来。
    images = ImageAssets(server.design_service)
    old_record, old_bytes = images._verified(
        project_id, _artifact_row(server.design_service, asset_id, first["version_id"]))
    new_record, new_bytes = images._verified(
        project_id, _artifact_row(server.design_service, asset_id, second["version_id"]))
    assert old_bytes != new_bytes, "两版折叠成了同一份字节：历史已被覆盖"
    assert old_bytes == first_bytes and new_bytes == second_bytes
    assert DIGEST_PATTERN.fullmatch(old_record["sha256"]), old_record
    assert old_record["version_id"] == first["version_id"], old_record
    assert old_record["sha256"] == first["sha256"], old_record
    assert old_record["byte_size"] == len(first_bytes), old_record
    assert new_record["sha256"] == second["sha256"], new_record

    paths = _artifact_paths(server.design_service, asset_id)
    assert len(set(paths)) == 2, paths
    for path, expected in zip(paths, (first["sha256"], second["sha256"])):
        on_disk = "sha256:" + hashlib.sha256(Path(path).read_bytes()).hexdigest()
        assert on_disk == expected, (path, on_disk, expected)


def _check_asset_reference(server, project_id: str, other_project_id: str, asset_id: str,
                           *, record: dict, data: bytes) -> None:
    """引用可恢复：读回自带引用标识且与字节互相咬合，同一引用两次读回字节一致，越权被拒。"""
    assert RASTER_ID_PATTERN.fullmatch(asset_id), asset_id
    assert VERSION_ID_PATTERN.fullmatch(record["version_id"]), record
    assert DIGEST_PATTERN.fullmatch(record["sha256"]), record

    first_status, first = server.client.get(_content_url(project_id, asset_id))
    second_status, second = server.client.get(_content_url(project_id, asset_id))
    assert (first_status, second_status) == (200, 200), (first, second)
    # 引用标识先要真的是标识：读回来的每一条都必须还能按同一形状寻址回来。
    assert RASTER_ID_PATTERN.fullmatch(first["asset"]["id"]), first["asset"]
    assert VERSION_ID_PATTERN.fullmatch(first["asset"]["version_id"]), first["asset"]
    assert DIGEST_PATTERN.fullmatch(str(first["asset"]["sha256"])), first["asset"]
    assert first == second, "同一引用两次读回不是同一份字节"
    payload = base64.b64decode(first["content_base64"])
    assert payload == data
    assert first["asset"]["sha256"] == "sha256:" + hashlib.sha256(payload).hexdigest(), first
    assert first["asset"]["byte_size"] == len(payload), first["asset"]

    listed = server.client.get(_assets_url(project_id))[1]["assets"]
    by_id = {item["id"]: item for item in listed}
    assert by_id[asset_id] == first["asset"], (by_id.get(asset_id), first["asset"])

    # 越权与畸形：具名拒绝，不是空列表糊过去（真实错误码按 handler/`require_project` 读来）。
    assert server.client.get(_content_url(other_project_id, asset_id)) == (
        404, {"error": "ASSET_NOT_FOUND"})
    assert server.client.get(_assets_url(other_project_id)) == (200, {"assets": []})
    stranger = "0" * 32
    assert server.client.get(_assets_url(stranger))[:2] == (404, {"error": "PROJECT_NOT_FOUND"})
    assert server.client.get(_content_url(stranger, asset_id))[:2] == (
        404, {"error": "PROJECT_NOT_FOUND"})
    assert server.client.get(_assets_url(project_id) + "/not-an-asset-id/content") == (
        404, {"error": "NOT_FOUND"})
    assert server.client.get(_content_url(project_id, "img-" + "b" * 64)) == (
        404, {"error": "ASSET_NOT_FOUND"})


def _check_input_output_split(server, project_id: str, raster_id: str, native_id: str,
                              *, raster_bytes: bytes, native_bytes: bytes) -> None:
    """输入/输出可区分：两个侧面各走自己的路由与字段，读回不要求任何外部素材平台在线。"""
    status, listed = server.client.get(_assets_url(project_id))
    assert status == 200, listed
    raster_ids = [item["id"] for item in listed["assets"]]
    assert raster_ids == [raster_id], raster_ids          # 栅格面只有输入素材
    assert native_id not in raster_ids, raster_ids       # 输出产物不会被折进同一个大列表
    raster = listed["assets"][0]
    assert set(raster) == RASTER_RECORD_KEYS, sorted(raster)
    assert "kind" not in raster, raster                   # 输入侧没有 kind，靠 kind 区分就不成立

    status, native = server.client.get(f"/api/projects/{project_id}/native-assets")
    assert status == 200, native
    assert [item["id"] for item in native["assets"]] == [native_id], native["assets"]
    output = native["assets"][0]
    assert set(output) == NATIVE_RECORD_KEYS, sorted(output)
    assert output["kind"] == "psd", output
    assert output["verification"] == "METADATA_ONLY", output
    assert set(raster) - set(output) and set(output) - set(raster), (raster, output)

    assert _asset_kind(server.design_service, raster_id) == "raster"
    assert _asset_kind(server.design_service, native_id) == "psd"

    # 输入面连寻址都寻不到输出：路由的 id 段只认 `img-`，与 kind 过滤是同一件事的两半。
    assert server.client.get(_content_url(project_id, native_id)) == (404, {"error": "NOT_FOUND"})

    # 输出侧的字节由本机文件现算哈希确认，两侧都不问任何外部平台在线与否。
    status, verified = server.client.get(
        f"/api/projects/{project_id}/native-assets/{native_id}/verify")
    assert status == 200, verified
    assert verified["asset"]["verification"] == "HASH_VERIFIED", verified["asset"]
    assert verified["asset"]["sha256"] == (
        "sha256:" + hashlib.sha256(native_bytes).hexdigest()), verified["asset"]
    assert output["byte_size"] == len(native_bytes), output
    assert (raster["sha256"], raster["byte_size"]) == (
        "sha256:" + hashlib.sha256(raster_bytes).hexdigest(), len(raster_bytes)), raster


def _check_no_platform_channel(server, project_id: str, asset_id: str) -> None:
    """不扩素材平台：这一面的路由与载荷里，没有上传/同步/远程拉取的任何通道或声称。"""
    from design_lab import http_service

    family = [(route.method, route.pattern, route.action)
              for route in http_service.ROUTES if "/assets" in route.pattern]
    assert family == list(ASSET_SURFACE_ROUTES), family
    assert {item[0] for item in family} <= {"GET", "POST"}, family
    offenders = [item for item in family
                 if any(word in (item[1] + item[2]).lower() for word in PLATFORM_WORDS)]
    assert not offenders, offenders
    whole_table = [(route.method, route.pattern) for route in http_service.ROUTES
                   if any(word in (route.pattern + route.action).lower()
                          for word in ("upload", "sync", "remote", "fetch", "pull", "push",
                                        "download", "platform", "cdn", "proxy", "webhook"))]
    assert whole_table == [], whole_table

    status, listed = server.client.get(_assets_url(project_id))
    assert status == 200, listed
    assert set(listed) == {"assets"}, sorted(listed)
    status, content = server.client.get(_content_url(project_id, asset_id))
    assert status == 200, content
    assert set(content) == {"asset", "content_base64"}, sorted(content)
    assert set(content["asset"]) == RASTER_RECORD_KEYS, sorted(content["asset"])
    # 字节是内联回读的，不是一个「去哪儿取」的指针；权利位仍明说没审。
    assert content["asset"]["rights"] == "NOT_REVIEWED", content["asset"]
    assert listed["assets"][0]["rights"] == "NOT_REVIEWED", listed["assets"][0]
    _assert_no_platform_claim(listed, where="GET /assets")
    _assert_no_platform_claim(content, where="GET /assets/<id>/content")

    # 入参面同样关着：想交一个远程地址连门都进不来（handler.body 的键集合是闭合的）。
    for smuggled in ({"remote_url": "https://assets.example.invalid/reference.png"},
                     {"sync_target": "example-platform"},
                     {"upload_to": "example-platform"}):
        body = {"content_base64": base64.b64encode(b"not-an-image").decode("ascii"),
                "idempotency_key": "no-platform-1", **smuggled}
        refused = server.client.post(_assets_url(project_id), body)
        assert refused == (400, {"error": "INVALID_PROJECT_FIELDS"}), (smuggled, refused)


@contextmanager
def _reopen_service_readback(server):
    """对同一 workspace 目录再 build 一个真服务：新 `ProjectService`、新数据库连接、新 HTTP 端口。

    这只证明「换一个服务实例，一切从磁盘重读」，**不**是操作系统进程重启，也不主张断电语义。
    """
    from backend.app import build_server
    from tests.conftest import Client

    token = secrets.token_hex(32)
    httpd, context = build_server(server.workspace, token, 0)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    reopened = Client()
    reopened.port = httpd.server_port
    reopened.token = token
    try:
        yield SimpleNamespace(client=reopened, service=context["service"])
    finally:
        httpd.shutdown()
        context["unified"].close()
        context["work"].close()


# ---------------------------------------------------------------------- 05#L22 断言一：版本可恢复
def test_design_asset_versions_are_immutable_history_and_both_revisions_read_back(
        server, monkeypatch):
    """05#L22 的「版本可恢复」：改版得到第二版，当前版与历史版是两份不同字节，旧版不被改写。

    证明（全走真实 HTTP + 真实 store 写入序）：
    * 同一 `asset_id` 发第二版后，`asset_version` 是两行 `[1, 2]`、都还是 `ACTIVE`、摘要互不
      相同，第一行登记的 `content_sha256` 仍是当初 `POST /assets` 服务自己给出的那个值——历史
      是追加的，不是覆盖；
    * 两版各自的字节落在 `versions/<publication_id>/` 两个不重叠的位置，磁盘上现算的 sha256
      与登记值逐版相等；`ImageAssets._verified`（路由每次读回都走的产品校验器）能把两版都认下来，
      且 `old_bytes != new_bytes`、旧版 `byte_size` 没变；
    * 兼容面按构造只回当前版本（集合里同一资产只出现一次，内容读回给的是第二版字节）——这条
      真实形状一并写下，避免后人以为「列不出第二行」是缺陷或被当成历史已可读；
    * 对同一 workspace 再 build 一个真服务（新 `ProjectService`、新数据库连接）后，当前版仍从
      路由读回，历史版仍被 `_verified` 认下：可恢复不依赖第一次那个内存对象。

    植入反证两次，各自证明对应断言会红：①把 `_verified` 折成「无论问哪一版都回最新一版的字节」
    （版本历史被折叠成覆盖）；②让 `_verified` 给出的记录把旧版摘要写成最新版的摘要（旧版本摘要
    跟着变）。两次都 `pytest.raises(AssertionError)`，撤销补丁后复跑绿。

    没证明：操作系统进程/机器重启后的持久性、断电时 rename 的可见性、`recover_publications`
    的崩溃恢复语义、真实宿主产生的素材、任何真人验收（rights 仍是 NOT_REVIEWED）。
    """
    from design_lab.image_assets import ImageAssets

    project_id = _design_project(server, "素材版本历史")
    first_bytes = _synthetic_png(4, 4, (200, 10, 10))
    created = _import_asset(server, project_id, first_bytes, "rev-one")
    first, asset_id = created["asset"], created["asset"]["id"]
    assert set(first) == RASTER_RECORD_KEYS, sorted(first)

    second_bytes = _synthetic_png(6, 5, (10, 180, 40))
    second = _publish_next_version(server, project_id, asset_id, kind="raster",
                                   data=second_bytes, idempotency_key="rev-two",
                                   artifact_name="reference.png", scope="image-import")
    assert second["version_id"] != first["version_id"], (first, second)

    _check_version_recovery(server, project_id, asset_id, first=first, first_bytes=first_bytes,
                            second=second, second_bytes=second_bytes)

    original_verified = ImageAssets._verified

    # 反证①：历史折叠成覆盖——问哪一版都只回最新一版的字节。
    def _fold_history(self, project_id_, row):
        newest = _version_rows(self.service, row[0])[-1]
        return original_verified(self, project_id_,
                                 _artifact_row(self.service, row[0], newest["version_id"]))

    monkeypatch.setattr(ImageAssets, "_verified", _fold_history)
    with pytest.raises(AssertionError):
        _check_version_recovery(server, project_id, asset_id, first=first,
                                first_bytes=first_bytes, second=second, second_bytes=second_bytes)
    monkeypatch.undo()

    # 反证②：旧版本摘要跟着新版变——字节还是旧的，登记口径已经指到新版。
    def _drift_digest(self, project_id_, row):
        record, data = original_verified(self, project_id_, row)
        newest = _version_rows(self.service, row[0])[-1]
        return dict(record, sha256=newest["content_sha256"]), data

    monkeypatch.setattr(ImageAssets, "_verified", _drift_digest)
    with pytest.raises(AssertionError):
        _check_version_recovery(server, project_id, asset_id, first=first,
                                first_bytes=first_bytes, second=second, second_bytes=second_bytes)
    monkeypatch.undo()

    # 还原后复跑：两条反证都只活在打补丁的这几行里，产品代码与台账一个字节都没被改。
    _check_version_recovery(server, project_id, asset_id, first=first, first_bytes=first_bytes,
                            second=second, second_bytes=second_bytes)

    with _reopen_service_readback(server) as reopened:
        status, again = reopened.client.get(_content_url(project_id, asset_id))
        assert status == 200, again
        assert again["asset"] == second, again["asset"]
        assert base64.b64decode(again["content_base64"]) == second_bytes
        # 历史版也由这个新服务实例从磁盘重新认下来，不是第一个实例留下的内存
        old_record, old_data = ImageAssets(reopened.service)._verified(
            project_id, _artifact_row(reopened.service, asset_id, first["version_id"]))
        assert old_record["sha256"] == first["sha256"], old_record
        assert old_data == first_bytes


# ---------------------------------------------------------------------- 05#L22 断言二：引用可恢复
def test_design_asset_reference_pins_its_bytes_and_other_projects_are_refused(
        server, monkeypatch):
    """05#L22 的「引用可恢复」：读回自带可寻址引用且与字节互相咬合，别人的资产读不到。

    证明：
    * 引用标识真实存在且形状可寻址：`img-`+64 位十六进制、`v-`+32 位、`sha256:`+64 位；
      给出的摘要等于返回字节的现算值，`byte_size` 等于返回字节长度——引用钉住了内容；
    * 同一引用两次独立 HTTP 读回，整个载荷逐字段相等（不是「大概一样」）；集合读回与内容读回
      给出同一条资产记录，两处引用标识不会各说各话；
    * 跨项目与畸形寻址都是具名拒绝，按 handler 真实错误码断言：别人的项目要这份内容 →
      404 `ASSET_NOT_FOUND`（别人的集合读回是 200 空列表，不冒充可见）；不存在的项目 →
      404 `PROJECT_NOT_FOUND`；不合 `img-` 模式的 id → 404 `NOT_FOUND`；模式合但没登记过的
      id → 404 `ASSET_NOT_FOUND`；
    * store 层同一身份不能被别的项目重铸：拿 A 的 `asset_id` 去 B 登记 →
      `AssetError('asset identity is already bound to another project/kind')`；
    * 引用不是装饰：把落盘字节改成同样长度、不同内容的字节，路由立刻 409
      `ARTIFACT_HASH_MISMATCH`（集合读回同样拒绝），把原字节放回后读回重新为绿——登记的摘要
      每次读都重新算过，不是读一次就信了。

    植入反证三次：①让 `content` 每次多吐一个字节（同一引用两次读回不再一致）；②让 `_verified`
    把摘要写成 `None`（读回不再带引用标识）；③直接在落盘文件上换字节（引用与内容脱钩）。
    前两次撤销补丁后复跑绿，第三次把原字节放回后复跑绿。

    没证明：真实用户素材、任何外部素材平台的引用（本面就没有这个通道，见断言四）。
    """
    from design_lab.image_assets import ImageAssets
    from design_lab.runtime import asset_store as assets

    project_a = _design_project(server, "引用甲项目")
    project_b = _design_project(server, "引用乙项目")
    data = _synthetic_png(8, 3, (12, 34, 250))
    record = _import_asset(server, project_a, data, "ref-one")["asset"]
    asset_id = record["id"]

    _check_asset_reference(server, project_a, project_b, asset_id, record=record, data=data)

    # store 层的身份绑定：引用不能被第二个项目接走。
    with closing(assets.connect(server.design_service.database,
                                 project_root=server.design_service.paths.project_root)) as conn:
        with pytest.raises(assets.AssetError) as rebound:
            assets.register_asset(conn, project_b, asset_id, "raster")
        assert "already bound to another project" in str(rebound.value), str(rebound.value)
    assert server.client.get(_content_url(project_b, asset_id)) == (
        404, {"error": "ASSET_NOT_FOUND"})

    original_content = ImageAssets.content
    original_verified = ImageAssets._verified
    reads = {"n": 0}

    # 反证①：同一引用两次读回不再是同一份字节（每次多吐一个递增字节）。
    def _drifting_read(self, project_id_, asset_id_):
        payload = original_content(self, project_id_, asset_id_)
        reads["n"] += 1
        raw = base64.b64decode(payload["content_base64"]) + bytes([reads["n"] % 251])
        payload["content_base64"] = base64.b64encode(raw).decode("ascii")
        return payload

    monkeypatch.setattr(ImageAssets, "content", _drifting_read)
    with pytest.raises(AssertionError):
        _check_asset_reference(server, project_a, project_b, asset_id, record=record, data=data)
    monkeypatch.undo()

    # 反证②：读回不再带引用标识（摘要位被写成 None，形状检查当场红）。
    def _drop_digest(self, project_id_, row):
        rec, rec_data = original_verified(self, project_id_, row)
        return dict(rec, sha256=None), rec_data

    monkeypatch.setattr(ImageAssets, "_verified", _drop_digest)
    with pytest.raises(AssertionError):
        _check_asset_reference(server, project_a, project_b, asset_id, record=record, data=data)
    monkeypatch.undo()
    _check_asset_reference(server, project_a, project_b, asset_id, record=record, data=data)

    # 数据侧的植入反证：落盘字节被换掉，摘要必须当场拒绝；还原后引用重新可读。
    path = Path(_artifact_paths(server.design_service, asset_id)[0])
    pristine = path.read_bytes()
    try:
        path.write_bytes(b"X" * len(pristine))
        assert server.client.get(_content_url(project_a, asset_id)) == (
            409, {"error": "ARTIFACT_HASH_MISMATCH"})
        assert server.client.get(_assets_url(project_a))[1]["error"] == "ARTIFACT_HASH_MISMATCH"
    finally:
        path.write_bytes(pristine)
    _check_asset_reference(server, project_a, project_b, asset_id, record=record, data=data)


# ------------------------------------------------------------ 05#L22 断言三：输入与输出是两个侧面
def test_design_input_material_and_output_artifact_stay_two_different_kinds(server,
                                                                           monkeypatch):
    """05#L22 的「输入/输出…可恢复」：输入素材与输出产物在同一台账里可区分，且读回不问外部平台。

    证明（两侧都是测试自己生成的合成字节）：
    * 同一个设计项目、同一套 `asset/asset_version/artifact` 台账里登记两份东西：输入素材是
      `img-` 前缀 + `asset_kind='raster'`（走真实 `POST /assets`），输出产物是 `native-` 前缀 +
      `asset_kind='psd'`（走 store 自己的写入序，宿主产物在台账里就是这个形状）；
    * 两个侧面各有路由、各有字段：`GET /assets` 只列输入，键集合是那 8 个栅格字段，里面
      **没有** `kind`；`GET /assets` 里绝不出现输出 id。`GET /native-assets` 只列输出，键集合
      含 `kind/version_no/verification` 而无 `media_type/width/height`；两个键集合互不相等，
      `kind='psd'` 与栅格的 `media_type='image/png'` 各说各话；
    * 输入面连寻址都寻不到输出：`GET /assets/<native-id>/content` → 404 `NOT_FOUND`（id 段只认
      `img-`），与 kind 过滤是同一道构造的两半；
    * 两侧读回都不要求任何外部素材平台在线：输入的摘要/大小由本机字节现算，输出的
      `verification` 从 `METADATA_ONLY` 到 `/verify` 的 `HASH_VERIFIED`——后者是产品自己打开
      本地文件重算哈希的结果，等于测试对该文件现算的值。

    植入反证：把 `ImageAssets.list` 改成「两种 kind 合成一条大列表」（正是素材平台化的折叠动作），
    上述区分立刻红；撤销后复跑绿。

    没证明：`native.psd` 是 Photoshop 真能打开的文件（字节是合成的，这一面只哈希不解析）；
    真实宿主产生输出的链路（宿主自动化仍按项目边界逐次走人工门）。
    """
    from design_lab.image_assets import ImageAssets
    from design_lab.native_assets import NativeAssets

    project_id = _design_project(server, "输入与输出")
    raster_bytes = _synthetic_png(5, 5, (7, 7, 200))
    raster = _import_asset(server, project_id, raster_bytes, "in-one")["asset"]
    native_bytes = b"SYNTHETIC-NATIVE-OUTPUT-FOR-TESTS\n" * 4
    output = _register_output_asset(server, project_id, "synthetic-output-1", native_bytes)

    _check_input_output_split(server, project_id, raster["id"], output["id"],
                              raster_bytes=raster_bytes, native_bytes=native_bytes)

    original_list = ImageAssets.list

    # 反证：两侧折成一条不分 kind 的大列表，就是「素材平台」那一侧的样子。
    def _merged_feed(self, project_id_):
        merged = list(original_list(self, project_id_))
        merged.extend(NativeAssets(self.service).list(project_id_)["assets"])
        return merged

    monkeypatch.setattr(ImageAssets, "list", _merged_feed)
    with pytest.raises(AssertionError):
        _check_input_output_split(server, project_id, raster["id"], output["id"],
                                  raster_bytes=raster_bytes, native_bytes=native_bytes)
    monkeypatch.undo()
    _check_input_output_split(server, project_id, raster["id"], output["id"],
                              raster_bytes=raster_bytes, native_bytes=native_bytes)


# -------------------------------------------------------------- 05#L22 断言四：不扩素材平台
def test_design_asset_surface_offers_no_external_platform_channel(server, monkeypatch):
    """05#L22 的「不扩素材平台」：这一面没有上传/同步/远程拉取的通道，也没有声称做过。

    证明（路由表与载荷两侧一起看，不靠注释）：
    * `ROUTES` 里带 `/assets` 的条目恰好是已登记的 4 条——一条集合读、一份字节读、两条本地
      派生写（analysis / prompt-reversal），方法集合 ⊆ {GET, POST}，pattern 与 action 里不含
      任何平台词根；整张路由表也搜不到 upload/sync/remote/fetch/pull/push/download/platform/
      cdn/proxy/webhook 这样的路由；
    * 读回载荷的键集合是闭合的：集合读只有 `assets`，内容读只有 `asset` + `content_base64`，
      资产记录只有那 8 个本地字段；递归扫过每一个键名（含嵌套）都不含平台词根，序列化文本里
      没有任何 URL（`://`、scheme、`www.` 都搜不到）——字节是内联回读的，不是「去哪儿取」的指针；
    * 权利位明说没审：两处 `rights` 都是 `NOT_REVIEWED`，服务没有替任何人声称三方素材可用；
    * 入参面同样关着：`POST /assets` 的键集合是闭合的 `{content_base64, idempotency_key}`，
      想递一个 `remote_url`／`sync_target`／`upload_to` 都得到 400 `INVALID_PROJECT_FIELDS`，
      连门都进不来（因此也不存在「交个地址让服务去外部拉」这条隐式通道）。

    植入反证：给 `content` 的载荷加一个 `remote_url` 和一个 `synced=True`，再给路由表加一条
    `POST /assets/upload`——两种「平台化」都被当场判红；撤销后复跑绿。

    没证明：别的表面（宿主 Adapter、bundle 交付）永不接触外部系统——本行验收只登记这一条路由，
    本节点也只断言这一条路由加整张路由表的名称面，不去宣称全局。
    """
    from design_lab import http_service
    from design_lab.image_assets import ImageAssets

    project_id = _design_project(server, "平台边界")
    data = _synthetic_png(3, 3, (99, 99, 99))
    record = _import_asset(server, project_id, data, "edge-one")["asset"]

    _check_no_platform_channel(server, project_id, record["id"])

    original_content = ImageAssets.content

    # 反证①：载荷开始声称「已经同步到某平台/可以去那儿取」。
    def _claims_a_platform(self, project_id_, asset_id_):
        payload = original_content(self, project_id_, asset_id_)
        payload["asset"]["synced"] = True
        payload["remote_url"] = "https://assets.example.invalid/reference.png"
        return payload

    monkeypatch.setattr(ImageAssets, "content", _claims_a_platform)
    with pytest.raises(AssertionError):
        _check_no_platform_channel(server, project_id, record["id"])
    monkeypatch.undo()

    # 反证②：路由表多出一条上传通道。
    monkeypatch.setattr(http_service, "ROUTES", tuple(http_service.ROUTES) + (
        http_service.Route("POST", r"/api/projects/([0-9a-f]{32})/assets/upload",
                           "_upload_asset"),))
    with pytest.raises(AssertionError):
        _check_no_platform_channel(server, project_id, record["id"])
    monkeypatch.undo()

    # 还原后复跑绿，并确认路由表回到登记值：反证只活在补丁里，没有在产品上留下任何东西。
    _check_no_platform_channel(server, project_id, record["id"])
    assert [(route.method, route.pattern, route.action) for route in http_service.ROUTES
            if "/assets" in route.pattern] == list(ASSET_SURFACE_ROUTES)

