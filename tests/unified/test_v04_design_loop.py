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

