"""Issue rows -> one repair pack per (project, chosen executor).

The audit's closed-loop row 3 said the loop has a case (ML-001) but no production entry point: a problem was
found, and a human carried it to an external agent by hand. This module is that entry point, and the first
version stops exactly where the audit says it must: it prepares and exports, it does not dispatch.

Three rules carry the honesty of the whole thing:

1. **The executor is chosen by a caller, never inferred.** Attribution (which software a problem belongs to)
   and routing (which software should fix it) are different claims; the 1b attribution rows are shipped as
   evidence *inside* the pack, and the adapter name comes from `--adapter`. A chosen adapter that does not
   declare `invoke` in `config/adapter-registry.json` is refused by name, because observe-only software
   cannot be handed a repair.
2. **The plan body is the existing contract.** `workflow/action-plan/v1` already declares what a plan is
   (target / steps / approval / rollback / constraints) and already has a table in the canonical store. This
   module wraps it in a handoff envelope rather than inventing a competing plan shape, and every generated
   body is validated against that shipped schema, not against a paraphrase of it.
3. **Unknown is said, not filled in.** A project that does not resolve, a root that is not on disk, or a
   verification command that WORK-LAB does not know each produce a named refusal reason and a count — never
   a pack with an invented command, and never an empty list that renders as "nothing needs fixing".

No I/O inside `build_repair_pack`: the caller passes the rows it already read, so "could not read" stays in
the composition root. Nothing here writes the store, sends anything, or authorizes anything.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

REPAIR_PACK_SCHEMA_VERSION = "workflow/repair-pack/v1"
PLAN_SCHEMA_VERSION = "workflow/action-plan/v1"
SUMMARY_SCHEMA_VERSION = "worklab/repair-packs-summary/v1"

EXECUTOR_OPERATION = "invoke"
MAX_PACKS = 20

# CL-03: a pack names ONE of two routes. `ADAPTER_INVOKE` is the route CL-02 shipped: the caller names an
# executor whose registry entry declares `invoke`. `MANUAL_COPY` names no adapter at all -- the material is
# copied to whatever tool a human chooses -- and therefore must not repeat any adapter-level claim. Keeping
# the two behind one enum is what stops a manual pack from reading as "an adapter that forgot its name".
TARGET_KINDS = ("ADAPTER_INVOKE", "MANUAL_COPY")
TARGET_OPERATIONS = {"ADAPTER_INVOKE": "invoke", "MANUAL_COPY": "copy-handoff"}
MANUAL_EXECUTOR_LABEL = "manual-copy"

# A rendered material may not contain these. `未发送`/`未执行` do not match: the ban is on the completed claim.
HANDOFF_FORBIDDEN_PHRASES = ("已发送", "已执行", "已批准")

# What a reader is missing, in words. One sentence per refusal reason the module can emit, so the material
# preview explains the condition instead of only naming a code.
MISSING_CONDITION_TEXT = {
    "no-open-issues": "没有待处理的问题，本包没有被绑定任何证据",
    "adapter-not-declared": "点名的执行者不在适配器注册表里；本包不能假装它存在",
    "adapter-does-not-declare-invoke": "点名的执行者没有声明 invoke；本包不替它抬高这项能力（可改用 --manual 走人工复制）",
    "project-unregistered": "问题所属项目不在注册表里，无法确认目标根",
    "project-root-missing": "目标项目的根路径不存在，交接材料没有可核对的落点",
    "issue-has-no-project": "问题没有项目归属，无法确定要交给谁",
    "verification-command-unknown": "目标项目根下没有 WORK-LAB 认识的检查入口，因此状态为 BLOCKED；"
                                    "请把目标项目自己的检查命令、退出码原样交回",
    "pack-cap-reached": "本次生成的包数达到上限，这个包没有导出；它绑定的问题仍计入未绑定",
}

# `workflow/action-plan/v1` allows eight statuses. A pack produced by this module may only ever hold two of
# them, and the vocabulary is kept short so a reader cannot mistake a draft for a running repair.
PACK_STATUSES = ("WAITING_APPROVAL", "BLOCKED")

READINESS_REASONS = (
    "no-open-issues",
    "adapter-not-declared",
    "adapter-does-not-declare-invoke",
    "project-unregistered",
    "project-root-missing",
    "issue-has-no-project",
    "verification-command-unknown",
    "pack-cap-reached",
)

# The one verification command WORK-LAB can name for its own repository: it is checked to exist at the
# target root before it is ever written into a step.
OWN_GATE_RELATIVE_PATH = "services/orchestration/run_quality_gate.py"
OWN_GATE_COMMAND = "python services/orchestration/run_quality_gate.py verify"


def _slug(value: str, limit: int) -> str:
    """Both halves of the pack id come from caller/registry text, and the contract pattern is
    `^[A-Za-z0-9._-]{3,120}$` -- an adapter id with a space would otherwise mint a pack the schema refuses."""
    return "".join(c if c.isalnum() or c in "._-" else "-" for c in value)[:limit]


def _pack_id(project_id: str, adapter: str, fingerprints: list[str]) -> str:
    """Content-addressed so re-running the same facts yields the same pack id (and a re-delivery dedupes)."""
    blob = json.dumps({"project": project_id, "adapter": adapter, "issues": sorted(fingerprints)},
                     sort_keys=True, ensure_ascii=False)
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]
    return f"rp-{_slug(project_id, 40)}-{_slug(adapter, 20)}-{digest}"


def _open_issues(issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in issues if str(row.get("status") or "OPEN") == "OPEN"]


def _evidence_phrase(evidence_refs: list[str]) -> str:
    """A step may quote only a prefix of the bound evidence, but it must say the rest exists: eight refs shown
    out of thirty read as thirty bound."""
    if not evidence_refs:
        return "（本包没有点名任何证据条目）"
    shown = evidence_refs[:8]
    phrase = ", ".join(shown)
    if len(evidence_refs) > len(shown):
        phrase += f"，另有 {len(evidence_refs) - len(shown)} 条在 binds.evidenceRefs 里逐条列出"
    return phrase


def _steps(project_id: str, evidence_refs: list[str], verification: dict[str, Any]) -> list[dict[str, Any]]:
    refs = _evidence_phrase(evidence_refs)
    verify_action = (
        f"跑读数确认问题不再出现：{verification['command']}" if verification["known"] else
        "跑目标项目自己的检查并把命令与退出码原样交回；WORK-LAB 不知道该项目的命令，"
        "本包因此标 verification-command-unknown，而不是编一条命令"
    )
    return [
        {"id": "read-evidence", "action": f"先重读本包点名的证据条目（{refs}），确认问题在当前代码上仍可复现",
         "mode": "read", "side_effects": []},
        {"id": "reproduce", "action": "按 evidenceRef 指向的采集器/任务现场复现一次；复现不了就回报，不要猜原因",
         "mode": "execute", "side_effects": []},
        {"id": "repair", "action": "只改足以让该问题不再出现的部分；观测面、任务与错误账本、适配器注册表、"
                                   "凭据存储都不是这次修复的对象。目标项目自己的禁区若本包说不出，"
                                   "先问再改，不要猜一个边界",
         "mode": "write", "side_effects": ["目标项目内被点名的源文件"]},
        {"id": "verify", "action": verify_action, "mode": "execute",
         "side_effects": ["执行目标项目的检查命令"]},
        {"id": "return-receipt", "action": "把改动、命令、退出码与读回结果交回 WORK-LAB，"
                                           "由独立验证决定是否关闭问题",
         "mode": "read", "side_effects": []},
    ]


def _plan_body(*, pack_id: str, project_id: str, project_root: str, executor_label: str,
               operation: str, evidence_refs: list[str], verification: dict[str, Any],
               blocked: bool) -> dict[str, Any]:
    return {
        "schema_version": PLAN_SCHEMA_VERSION,
        "plan_id": pack_id,
        "status": "BLOCKED" if blocked else "WAITING_APPROVAL",
        # `action-plan/v1` types `target.adapter` as a non-empty string. A manual pack still has to name who
        # executes, and the honest name is the human carrying the material -- not an adapter id it never
        # consulted. The envelope's `target.kind` is what distinguishes this reserved label from a registry id.
        "target": {"adapter": executor_label, "operation": operation, "project_root": project_root},
        "steps": _steps(project_id, evidence_refs, verification),
        # approval_required is a const in the contract; the value this module can honestly put there is the
        # one that says nothing has been approved.
        "approval": {"approval_required": True, "status": "PENDING"},
        # `available` is also a const. The strategy below is a requirement the handoff places on the
        # executor, not a claim that WORK-LAB can roll anything back: a pack applies nothing.
        "rollback": {
            "available": True,
            "strategy": "本包不施加任何改动，因此没有可回滚的写；交接要求外部执行者把修复落在单一可撤销提交上，"
                        "拒绝或失败即丢弃该提交",
        },
    }


def _verification(root: Path) -> dict[str, Any]:
    """A command may be named only if the file it runs exists under the target root."""
    if (root / OWN_GATE_RELATIVE_PATH).is_file():
        return {"known": True, "command": OWN_GATE_COMMAND,
                "basis": f"{root.as_posix()}/{OWN_GATE_RELATIVE_PATH} 实测存在"}
    return {"known": False, "command": "", "basis": "目标项目根下没有 WORK-LAB 认识的检查入口"}


def _adapter_refusal(adapter: str, registry: Mapping[str, Any]) -> str | None:
    """The executor-level answer, asked once per adapter: a refusal about the executor must not be repeated
    per project, and it must not carry a projectId, because the project has nothing to do with it."""
    entries = {str(entry.get("id") or ""): entry for entry in (registry.get("entries") or [])}
    if adapter not in entries:
        return "adapter-not-declared"
    declared = sorted(str(op) for op in (entries[adapter].get("operations") or []))
    if EXECUTOR_OPERATION not in declared:
        return "adapter-does-not-declare-invoke"
    return None


def build_repair_pack(*, adapter: str | None, project_id: str, bound_rows: list[dict[str, Any]],
                      projects: list[dict[str, Any]], registry: Mapping[str, Any] | None,
                      generated_at: str, root_probe: Any = Path,
                      manual: bool = False) -> tuple[dict[str, Any] | None, str]:
    """(pack, reason) for exactly one (project, executor) pair.

    One pack per pair, not one pack per call: an earlier shape picked `project_ids[0]` and quietly left the
    other projects' issues unbound, which is how a projection starts claiming a repair path exists for a
    project nobody handed it. Each way this can fail to be constructible returns its own reason instead of
    an empty pack, so a zero is always traceable to a named cause.

    `manual=True` is the CL-03 route: the material is for a human to copy to any tool. It consults no adapter
    and therefore may not repeat any adapter claim -- `adapter`/display/support are null, `declaredOperations`
    is empty, and `operation` is `copy-handoff` rather than the adapter-native `invoke`.
    """
    if manual:
        target_kind = "MANUAL_COPY"
        executor_label = MANUAL_EXECUTOR_LABEL
        adapter = None
        declared: list[str] = []
        entries: dict[str, Any] = {}
    else:
        target_kind = "ADAPTER_INVOKE"
        if not adapter:
            return None, "adapter-not-declared"
        entries = {str(entry.get("id") or ""): entry for entry in ((registry or {}).get("entries") or [])}
        refusal = _adapter_refusal(adapter, registry or {})
        if refusal:
            return None, refusal
        declared = sorted(str(op) for op in (entries[adapter].get("operations") or []))
        executor_label = adapter
    if not bound_rows:
        return None, "no-open-issues"

    by_id = {str(row.get("project_id") or "") if "project_id" in row else str(row.get("projectId") or ""): row
             for row in projects}
    project = by_id.get(project_id)
    if project is None:
        return None, "project-unregistered"
    root_value = str(project.get("root_path") or "")
    if not root_value:
        return None, "project-root-missing"
    root = root_probe(root_value)
    if not root.exists():
        return None, "project-root-missing"

    verification = _verification(root)
    fingerprints = [str(row.get("fingerprint") or "") for row in bound_rows]
    evidence_refs = [str(row.get("evidenceRef") or "") for row in bound_rows]
    # The pack id is content-addressed over the executor LABEL. A manual pack and an adapter pack for the
    # same issues are different materials, so they may not share an id.
    pack_id = _pack_id(project_id, executor_label, fingerprints)
    blocked = not verification["known"]
    plan = _plan_body(pack_id=pack_id, project_id=project_id, project_root=root_value,
                      executor_label=executor_label, operation=TARGET_OPERATIONS[target_kind],
                      evidence_refs=evidence_refs, verification=verification, blocked=blocked)

    reasons: list[str] = [] if not blocked else ["verification-command-unknown"]
    return ({
        "schemaVersion": REPAIR_PACK_SCHEMA_VERSION,
        "packId": pack_id,
        "generatedAt": generated_at,
        "status": plan["status"],
        "readiness": {"state": "BLOCKED" if blocked else "READY", "reasons": reasons},
        "target": {
            "kind": target_kind,
            "projectId": project_id,
            "projectName": str(project.get("display_name") or "") or None,
            "projectRoot": root_value,
            "projectStatus": str(project.get("status") or "") or None,
            "adapter": adapter,
            "adapterDisplayName": (str(entries[adapter].get("display_name") or "") or None
                                   if adapter else None),
            "adapterSupportLevel": (str(entries[adapter].get("support_level") or "") or None
                                    if adapter else None),
            "declaredOperations": declared,
            "operation": TARGET_OPERATIONS[target_kind],
            "routingSource": "caller-choice",
        },
        "binds": {
            "issueFingerprints": fingerprints,
            "evidenceRefs": evidence_refs,
            "classes": sorted({str(row.get("class") or "") for row in bound_rows}),
            "priorities": sorted({str(row.get("priority") or "") for row in bound_rows}),
            "issueCount": len(bound_rows),
            "softwareIds": sorted({str(row.get("softwareId") or "") for row in bound_rows
                                   if row.get("softwareId")}),
            "unattributedCount": sum(1 for row in bound_rows if not row.get("softwareId")),
        },
        "verification": dict(verification),
        "handoff": {
            "mode": "manual-copy",
            # Four claims, four fields, two pairs that must never collapse:
            #   copiedByUser (a local user action) vs sent (a transmission WORK-LAB never performed)
            #   userDeclaredHandoff (a user's statement) vs externalReceipt (the other side's response)
            "copyable": True,
            "sent": False,
            "dispatched": False,
            "copiedByUser": {"declared": False, "declaredAt": None, "channel": None},
            "userDeclaredHandoff": {"declared": False, "declaredAt": None, "channel": None,
                                    "claimedRecipient": None},
            "externalReceipt": {"received": False, "receivedAt": None, "externalId": None,
                                "source": None},
            "authorizationRef": None,
            "requiresOwnerAction": (
                "把本材料复制给你选择的任意工具执行；复制不等于发送，WORK-LAB 不会替你发送或执行"
                if manual else
                f"把本包的 handoff 文本交给 {adapter}，或据它建一个工作单元"),
        },
        "provenance": {
            "derivationScope": ("open-issue-rows-plus-registered-projects"
                                if manual else
                                "open-issue-rows-plus-registered-projects-plus-adapter-registry"),
            "inferencePerformed": False,
            "contentIncluded": False,
            "authorityClaimed": False,
            "applied": False,
        },
        "plan": plan,
    }, "")


def validate_repair_pack(pack: Mapping[str, Any], *, schema: Mapping[str, Any] | None = None) -> list[str]:
    """Machine checks the projection must pass on every emitted pack; empty means clean."""
    problems: list[str] = []
    if pack.get("schemaVersion") != REPAIR_PACK_SCHEMA_VERSION:
        problems.append("schemaVersion is not workflow/repair-pack/v1")
    if pack.get("status") not in PACK_STATUSES:
        problems.append(f"status {pack.get('status')!r} is outside {PACK_STATUSES}")
    handoff = pack.get("handoff") or {}
    if handoff.get("sent") is not False or handoff.get("dispatched") is not False:
        problems.append("a pack that claims it was sent or dispatched is not a draft")
    if handoff.get("mode") != "manual-copy":
        problems.append("the only delivery this projection produces is a material a human copies")
    if handoff.get("copyable") is not True:
        problems.append("a pack whose material cannot be copied is not a handoff")
    for field, claim in (("copiedByUser", "declared"), ("userDeclaredHandoff", "declared"),
                         ("externalReceipt", "received")):
        value = handoff.get(field)
        if not isinstance(value, dict) or value.get(claim) is not False:
            problems.append(f"handoff.{field}.{claim} must be false: a generated pack carries no user "
                            "statement and no external response, and the two are separate fields on purpose")
    if handoff.get("authorizationRef") is not None:
        problems.append("authorizationRef must be null until a real grant exists")
    if (pack.get("provenance") or {}).get("applied") is not False:
        problems.append("provenance.applied must be false: preparing a pack applies nothing")
    binds = pack.get("binds") or {}
    if int(binds.get("issueCount") or 0) != len(binds.get("issueFingerprints") or []):
        problems.append("binds.issueCount disagrees with the fingerprints bound")
    if len(set(binds.get("issueFingerprints") or [])) != len(binds.get("issueFingerprints") or []):
        problems.append("a pack may not bind the same issue fingerprint twice")
    if int(binds.get("unattributedCount") or 0) + len(binds.get("softwareIds") or []) > int(binds.get("issueCount") or 0):
        problems.append("software attribution exceeds the bound issue count")
    target = pack.get("target") or {}
    kind = target.get("kind")
    if kind not in TARGET_KINDS:
        problems.append(f"target.kind {kind!r} is outside {TARGET_KINDS}")
    elif target.get("operation") != TARGET_OPERATIONS[kind]:
        problems.append(f"a {kind} target must carry operation {TARGET_OPERATIONS[kind]!r}, never another "
                        "route's verb")
    if kind == "ADAPTER_INVOKE":
        if not isinstance(target.get("adapter"), str) or not target.get("adapter"):
            problems.append("an ADAPTER_INVOKE target must name the adapter it consulted")
    elif kind == "MANUAL_COPY":
        if target.get("adapter") is not None:
            problems.append("a MANUAL_COPY target names no adapter: copying material to an arbitrary tool is "
                            "not an adapter capability claim")
        if target.get("declaredOperations"):
            problems.append("a MANUAL_COPY target declares no operations: none were consulted")
    plan = pack.get("plan") or {}
    if plan.get("plan_id") != pack.get("packId"):
        problems.append("plan.plan_id must equal the pack id")
    if (plan.get("target") or {}).get("operation") != target.get("operation"):
        problems.append("plan.target.operation must be the same route verb as the envelope")
    if (plan.get("approval") or {}).get("status") != "PENDING":
        problems.append("a generated plan cannot carry an approved or rejected approval status")
    verification = pack.get("verification") or {}
    verify_steps = [step for step in (plan.get("steps") or []) if step.get("id") == "verify"]
    if not verify_steps:
        problems.append("a pack without a verify step hands the executor nothing to check against")
    readiness = pack.get("readiness") or {}
    if pack.get("status") == "BLOCKED" and readiness.get("state") != "BLOCKED":
        problems.append("a BLOCKED pack must also say BLOCKED in readiness.state")
    if pack.get("status") == "WAITING_APPROVAL" and readiness.get("state") != "READY":
        problems.append("a pack that is ready to hand off cannot be reported as blocked in one field and "
                        "waiting in the other")
    if readiness.get("state") == "BLOCKED" and not (readiness.get("reasons") or []):
        problems.append("a blocked pack must name what blocks it")
    if readiness.get("state") == "READY" and (readiness.get("reasons") or []):
        problems.append("a ready pack may not carry blocking reasons")
    plan_target = plan.get("target") or {}
    if plan_target.get("project_root") != target.get("projectRoot"):
        problems.append("the envelope and the plan body name different project roots")
    expected_executor = target.get("adapter") if kind == "ADAPTER_INVOKE" else MANUAL_EXECUTOR_LABEL
    if plan_target.get("adapter") != expected_executor:
        problems.append("the envelope and the plan body name different executors")
    if verification.get("known") is not True and any(
            str(step.get("action") or "").startswith("跑读数确认") for step in verify_steps):
        problems.append("the verify step names a command the pack says it does not know")
    if schema is not None:
        from jsonschema import Draft202012Validator
        for error in Draft202012Validator(schema).iter_errors(plan):
            problems.append(f"plan body violates workflow/action-plan/v1: {error.message}")
    return problems


def validate_repair_pack_set(packs: list[dict[str, Any]], summary: Mapping[str, Any]) -> list[str]:
    """Projection-level checks: what a set of packs must not be able to say about its own denominators.

    A single pack can be internally perfect and still double-count the store, which is exactly how the
    repeated-adapter defect looked green. These are the checks that would have caught it.
    """
    problems: list[str] = []
    ids = [str(pack.get("packId") or "") for pack in packs]
    if len(set(ids)) != len(ids):
        problems.append("two packs share one packId: a re-delivery under the same content must dedupe, "
                        "not appear twice")
    fingerprints = [fp for pack in packs for fp in (pack.get("binds") or {}).get("issueFingerprints") or []]
    if len(set(fingerprints)) != len(fingerprints):
        problems.append("one issue fingerprint is bound by more than one pack; count it once or say why twice")
    if int(summary.get("boundIssueCount") or 0) != len(fingerprints):
        problems.append("summary.boundIssueCount disagrees with the fingerprints the packs actually carry")
    open_count = summary.get("openIssueCount")
    if open_count is not None and int(summary.get("boundIssueCount") or 0) > int(open_count):
        problems.append("more issues bound than open: the denominators are invented, not measured")
    if open_count is not None and int(summary.get("boundIssueCount") or 0) + int(
            summary.get("unboundOpenIssueCount") or 0) != int(open_count):
        problems.append("bound + unbound must equal openIssueCount")
    for pack in packs:
        problems.extend(f"{pack.get('packId')}: {problem}" for problem in validate_repair_pack(pack))
    return problems


def project_repair_packs(*, issues: list[dict[str, Any]] | None, projects: list[dict[str, Any]] | None,
                         registry: Mapping[str, Any] | None, adapters: list[str],
                         generated_at: str, root_probe: Any = Path,
                         manual: bool = False) -> dict[str, Any]:
    """The whole projection: packs for the chosen executors plus the denominators that explain the rest.

    A source passed as None is reported as absent in the summary; the caller decides whether the key exists
    at all. Nothing here fabricates a pack to make the list non-empty.

    `manual=True` is the CL-03 route (material for a human to copy to any tool). It does not consult the
    adapter registry at all, so an unreadable registry is not an absent source on that route -- reporting it
    as one would blame a file the route never used.
    """
    target_kind = "MANUAL_COPY" if manual else "ADAPTER_INVOKE"
    sources = {"issues": issues is not None, "projects": projects is not None}
    if not manual:
        sources["adapterRegistry"] = registry is not None
    # A repeated --adapter used to mint two packs with one identical content-addressed id and count the same
    # issue into `boundIssueCount` twice, so the denominators disagreed with `openIssueCount` while every
    # individual pack stayed valid. Order-preserving dedupe, and the drop is disclosed rather than hidden.
    unique_adapters = list(dict.fromkeys(adapters))
    duplicate_adapters = len(adapters) - len(unique_adapters)
    if issues is None or projects is None or (registry is None and not manual):
        return {"packs": [], "summary": _summary(sources=sources, packs=[], refused=[],
                                                 issue_count=None, adapters=adapters,
                                                 absent=", ".join(sorted(k for k, v in sources.items() if not v))
                                                 or None, truncated=False, generated_at=generated_at,
                                                 duplicate_adapters=duplicate_adapters,
                                                 target_kind=target_kind)}

    packs: list[dict[str, Any]] = []
    refused: list[dict[str, str]] = []
    open_rows = _open_issues(issues)
    project_ids = sorted({str(row.get("projectId") or "") for row in open_rows if row.get("projectId")})
    if manual:
        # One manual pack per project: the human copying the material is the only executor, so an adapter
        # fan-out would multiply nothing but ids.
        if not open_rows:
            refused.append({"adapter": MANUAL_EXECUTOR_LABEL, "reason": "no-open-issues"})
        elif not project_ids:
            refused.append({"adapter": MANUAL_EXECUTOR_LABEL, "reason": "issue-has-no-project"})
        else:
            for project_id in project_ids:
                bound = [row for row in open_rows if str(row.get("projectId") or "") == project_id]
                pack, reason = build_repair_pack(adapter=None, project_id=project_id, bound_rows=bound,
                                                 projects=projects, registry=registry,
                                                 generated_at=generated_at, root_probe=root_probe,
                                                 manual=True)
                if pack is None:
                    refused.append({"adapter": MANUAL_EXECUTOR_LABEL, "reason": reason,
                                    "projectId": project_id})
                else:
                    packs.append(pack)
    else:
        for adapter in unique_adapters:
            if not open_rows:
                refused.append({"adapter": adapter, "reason": "no-open-issues"})
                continue
            if not project_ids:
                refused.append({"adapter": adapter, "reason": "issue-has-no-project"})
                continue
            refusal = _adapter_refusal(adapter, registry or {})
            if refusal:
                refused.append({"adapter": adapter, "reason": refusal})
                continue
            for project_id in project_ids:
                bound = [row for row in open_rows if str(row.get("projectId") or "") == project_id]
                pack, reason = build_repair_pack(adapter=adapter, project_id=project_id, bound_rows=bound,
                                                 projects=projects, registry=registry,
                                                 generated_at=generated_at, root_probe=root_probe)
                if pack is None:
                    refused.append({"adapter": adapter, "reason": reason, "projectId": project_id})
                else:
                    packs.append(pack)

    truncated = len(packs) > MAX_PACKS
    if truncated:
        for dropped in packs[MAX_PACKS:]:
            refused.append({"adapter": str(dropped["target"]["adapter"] or MANUAL_EXECUTOR_LABEL),
                            "projectId": str(dropped["target"]["projectId"]),
                            "reason": "pack-cap-reached"})
        packs = packs[:MAX_PACKS]

    return {"packs": packs,
            "summary": _summary(sources=sources, packs=packs, refused=refused,
                                issue_count=len(open_rows), adapters=adapters, absent=None,
                                truncated=truncated, generated_at=generated_at,
                                duplicate_adapters=duplicate_adapters,
                                projects_seen=len(project_ids),
                                issues_without_project=sum(1 for row in open_rows
                                                           if not row.get("projectId")),
                                target_kind=target_kind)}


def _summary(*, sources: dict[str, bool], packs: list[dict[str, Any]], refused: list[dict[str, str]],
             issue_count: int | None, adapters: list[str], absent: str | None,
             truncated: bool, generated_at: str, projects_seen: int = 0,
             issues_without_project: int = 0, duplicate_adapters: int = 0,
             target_kind: str = "ADAPTER_INVOKE") -> dict[str, Any]:
    reasons: dict[str, int] = {}
    for item in refused:
        reasons[item["reason"]] = reasons.get(item["reason"], 0) + 1
    return {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "generatedAt": generated_at,
        "targetKind": target_kind,
        "sources": {name: ("read" if read else "absent") for name, read in sorted(sources.items())},
        "absentReason": absent,
        "adaptersRequested": list(adapters),
        "openIssueCount": issue_count,
        "packCount": len(packs),
        "refusalCount": len(refused),
        "refusals": sorted(refused, key=lambda item: (item["adapter"], item["reason"])),
        "refusalReasons": dict(sorted(reasons.items())),
        "refusalReasonVocabulary": list(READINESS_REASONS),
        "truncated": truncated,
        "cap": MAX_PACKS,
        "boundIssueCount": sum(int(pack["binds"]["issueCount"]) for pack in packs),
        "unboundOpenIssueCount": (None if issue_count is None
                                  else issue_count - sum(int(pack["binds"]["issueCount"]) for pack in packs)),
        "verificationKnownCount": sum(1 for pack in packs if pack["verification"]["known"]),
        "projectsSeen": projects_seen,
        "issuesWithoutProject": issues_without_project,
        "duplicateAdaptersDropped": duplicate_adapters,
        "dispatchPerformed": False,
        "sent": False,
        "contentIncluded": False,
        "inferencePerformed": False,
        "derivationScope": "open-issue-rows-plus-registered-projects-plus-adapter-registry",
    }


def validate_handoff_text(pack: Mapping[str, Any], text: str) -> list[str]:
    """The two ways the copyable material can lie, checked against the pack it was rendered from.

    One: a bound evidence ref that does not appear in the text. The material is what a human carries to a
    tool that cannot read this repository, so a ref the text omits is a row nobody can re-read. Two: a
    completed-claim phrase. Printed text has no way to say "not yet" once it says 「已发送」, and a sentence a
    reader quotes out of context becomes a status claim the store never made.
    """
    problems: list[str] = []
    for ref in (pack.get("binds") or {}).get("evidenceRefs") or []:
        if str(ref) not in text:
            problems.append(f"handoff text omits bound evidence ref {ref!r}: every bound row must be "
                            "re-readable from the material itself")
    for phrase in HANDOFF_FORBIDDEN_PHRASES:
        if phrase in text:
            problems.append(f"handoff text contains {phrase!r}: the material is copied by a human; WORK-LAB "
                            "did not send, execute or approve anything")
    return problems


def render_handoff_text(pack: Mapping[str, Any]) -> str:
    """The copyable handoff a human gives to the external executor. Facts only, no invented authority."""
    target = pack["target"]
    binds = pack["binds"]
    handoff = pack["handoff"]
    manual = target.get("kind") == "MANUAL_COPY"
    if manual:
        executor_line = ("- 指定执行者：不指定适配器——材料可复制给任意工具；"
                         "本包不声明任何适配器的 invoke 能力")
    else:
        executor_line = (
            f"- 指定执行者：{target['adapter']}"
            + (f"（{target['adapterDisplayName']}）" if target.get("adapterDisplayName") else "")
            + f"\n- 该执行者声明的动词：{', '.join(target['declaredOperations']) or '（注册表没写）'}")
    reasons = list((pack.get("readiness") or {}).get("reasons") or [])
    lines = [
        f"# 修复任务包 {pack['packId']}",
        "",
        f"- 状态：`{pack['status']}`（等待授权，未发送、未执行）",
        f"- 目标项目：{target['projectId']} → `{target['projectRoot']}`",
        executor_line,
        "",
        "## 绑定的问题",
        "",
        f"- 问题数：{binds['issueCount']}，优先级：{', '.join(binds['priorities']) or 'UNKNOWN'}",
        f"- 类别：{', '.join(binds['classes']) or 'UNKNOWN'}",
        f"- 软件身份：{', '.join(binds['softwareIds']) or '未归属（unattributed=' + str(binds['unattributedCount']) + '）'}",
        "",
        "证据条目（逐条可重读，指向源表与源行）：",
        "",
    ]
    lines += [f"- `{ref}`" for ref in binds["evidenceRefs"]]
    lines += [
        "",
        "## 交给外部执行者的步骤",
        "",
    ]
    for step in pack["plan"]["steps"]:
        lines.append(f"{step['id']}（{step['mode']}）— {step['action']}")
    lines += [
        "",
        "## 还缺什么条件",
        "",
    ]
    if reasons:
        lines += [f"- `{reason}`：{MISSING_CONDITION_TEXT.get(reason, '未登记的原因')}" for reason in reasons]
    else:
        lines.append("- 无：项目根、绑定证据与验证入口都已核对；材料可以直接复制。")
    lines += [
        "",
        "## 交接状态（四个字段，互不替代）",
        "",
        "- 发送：未发生（sent=false）。复制是本地动作，和发送不是一回事。",
        f"- 用户声明复制：未声明（copiedByUser.declared={str(handoff['copiedByUser']['declared']).lower()}）",
        f"- 用户声明交接：未声明（userDeclaredHandoff.declared="
        f"{str(handoff['userDeclaredHandoff']['declared']).lower()}）——这只是用户的说法，不是对方的回执",
        f"- 外部接收回执：未收到（externalReceipt.received="
        f"{str(handoff['externalReceipt']['received']).lower()}）——只有外部系统自己的答复才能填这里",
        "",
        "## 回滚与授权",
        "",
        f"- {pack['plan']['rollback']['strategy']}",
        f"- 审批：{pack['plan']['approval']['status']}——需要 owner 的一句话才进入执行；本包不自授权。",
        f"- 来源范围：`{pack['provenance']['derivationScope']}`；不含内容正文（contentIncluded=false），"
        "不做因果推断（inferencePerformed=false），本包没有施加任何东西（applied=false）。",
    ]
    text = "\n".join(lines) + "\n"
    problems = validate_handoff_text(pack, text)
    if problems:
        raise ValueError("rendered handoff text violates its own guard: " + "; ".join(problems))
    return text


def load_repair_packs(store: Any, *, adapters: list[str], registry_path: Path,
                      generated_at: str, issues: list[dict[str, Any]] | None,
                      projects: list[dict[str, Any]] | None = None,
                      manual: bool = False) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Boundary entry point: reads the registry file and the store's projects, then projects."""
    if projects is None:
        projects = store.list_projects() if hasattr(store, "list_projects") else None
    try:
        registry = json.loads(Path(registry_path).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        registry = None
    projection = project_repair_packs(issues=issues, projects=projects, registry=registry,
                                      adapters=adapters, generated_at=generated_at,
                                      manual=manual)
    return projection["packs"], projection["summary"]



def main(argv: list[str] | None = None) -> int:
    """Export the handoff packs a caller asked for. Dry by default: nothing is written without --apply.

    The store path is refused rather than created when it is absent. `CanonicalStore(path)` builds a schema
    it can migrate, so a typo'd root would otherwise produce a zero-row store that reads back as "the
    projects table is empty" -- a confident statement about a file that was not there (measured 2026-10-22).
    """
    import argparse
    import datetime

    root = Path(__file__).resolve().parents[3]
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--adapter", action="append", dest="adapters", default=[],
                    help="an executor to prepare a pack for; repeatable. Nothing is inferred here.")
    ap.add_argument("--manual", action="store_true",
                    help="CL-03: prepare material for a human to copy to any tool. Names no adapter and "
                         "asserts no adapter capability; mutually exclusive with --adapter in one run")
    ap.add_argument("--runtime-root", type=Path, default=root / ".project-local" / "runs" / "issues-live-readback")
    ap.add_argument("--out-dir", type=Path, default=root / ".project-local" / "artifacts" / "repair-packs")
    ap.add_argument("--apply", action="store_true", help="write the pack json and handoff text")
    args = ap.parse_args(argv)

    # Two routes in one set used to be impossible to state honestly: the set check refuses to bind one issue
    # twice, so asking for both would either drop one route or double-count the issue. Say that instead.
    if args.manual and args.adapters:
        print("REPAIR_PACK_TARGET_CONFLICT --manual and --adapter are different routes; run them separately")
        return 4

    out_dir = args.out_dir.resolve()
    if not out_dir.is_relative_to(root.resolve()):
        print(f"REPAIR_PACK_REFUSED_OUT_OF_BOUNDARY {out_dir} is not inside the project Git root")
        return 2
    db = args.runtime_root / "canonical.sqlite"
    if not db.is_file():
        print(f"REPAIR_PACK_NO_STORE {db} -- refusing to create an empty store and report it as empty")
        return 3

    from canonical_store import CanonicalStore
    from issue_projection import load_issues

    store = CanonicalStore(db)
    generated_at = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    issues, issues_summary, absent_reason = load_issues(store)
    # The CLI does not run install discovery (only the composition root does), so every bound row says
    # identity-source-absent here. Print that instead of letting an empty binds.softwareIds read as
    # "this problem belongs to no software".
    attribution = (issues_summary or {}).get("softwareAttribution") or {}
    print("ISSUE_SOURCE issues=%s absent=%s softwareAttribution=%s" % (
        "absent" if issues is None else len(issues), absent_reason,
        json.dumps(attribution, ensure_ascii=False)))
    packs, packs_summary = load_repair_packs(store, adapters=args.adapters,
                                             registry_path=root / "config" / "adapter-registry.json",
                                             generated_at=generated_at, issues=issues,
                                             manual=args.manual)
    set_problems = validate_repair_pack_set(packs, packs_summary)
    print("REPAIR_PACKS targetKind=%s generated=%d refused=%d openIssues=%s bound=%s unbound=%s absentSources=%s "
          "duplicateAdaptersDropped=%d setProblems=%d apply=%d" % (
              packs_summary["targetKind"],
              packs_summary["packCount"], packs_summary["refusalCount"], packs_summary["openIssueCount"],
              packs_summary["boundIssueCount"], packs_summary["unboundOpenIssueCount"],
              packs_summary["absentReason"], packs_summary["duplicateAdaptersDropped"],
              len(set_problems), int(args.apply)))
    for problem in set_problems:
        print("  SET_PROBLEM", problem)
    if set_problems:
        print("REPAIR_PACKS_BLOCKED nothing written: the projection failed its own set checks")
        return 1
    for item in packs_summary["refusals"]:
        print("  REFUSED", json.dumps(item, ensure_ascii=False))
    if not args.apply:
        for pack in packs:
            print("  DRY", pack["packId"], pack["status"], pack["target"]["kind"],
                  pack["target"]["adapter"] or pack["target"]["operation"], pack["readiness"]["reasons"])
        return 0
    out_dir.mkdir(parents=True, exist_ok=True)
    for pack in packs:
        (out_dir / f"{pack['packId']}.json").write_text(
            json.dumps(pack, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
        (out_dir / f"{pack['packId']}.md").write_text(render_handoff_text(pack), encoding="utf-8", newline="")
        digest = hashlib.sha256((out_dir / f"{pack['packId']}.json").read_bytes()).hexdigest()[:12]
        print("  WROTE", pack["packId"], "sha12=%s" % digest)
    (out_dir / "repair-packs-summary.json").write_text(
        json.dumps(packs_summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
