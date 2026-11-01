"""Control Surface service (P1-06 / AG-15 / T04): the loopback-only write boundary.

Why this exists as its own process and not as extra routes on the Observer: ``apps/observer`` is
permanently strictly read-only (AGENTS.md, ``apps/observer/AGENTS.md``,
``scripts/ci/verify_observer_readonly_boundary.py``). A unified UI may offer both kinds of surface, but
the read-only service must never hold a write path. So this module is the only place a control request
is accepted, and it delegates every decision to the control plane that already exists —
``services/task-governance/permission_gate.py`` for authorisation and the workflow-owned canonical store
for state — instead of inventing a second ledger, a second receipt engine or a second approval flow.

Rules this module enforces rather than assumes:

* loopback only, dynamic port, and an endpoint descriptor the shell discovers — never a fixed production port;
* the operation enum is closed, and an operation without a native capability answers ``NOT_IMPLEMENTED``
  with its own reason. It never returns a success shape, and no caller-supplied field can raise the
  evidence level: an in-repo fixture store is SYNTHETIC, a live local store is INTEGRATED, and REAL is
  reserved for a verifiable native handle plus readback, which a local write is not;
* ``plan != write``: the config operations that only compute a diff say so, and the ones that would write
  to a target outside this repository answer REFUSED until an exact target is authorised;
* ``authorized != executed``: ``work-unit.materialize`` is the consumer side of the AG-16 planning
  handback. It re-runs ``plan_candidate.check_candidate`` server-side on every call against the local
  authorization record, so a client that sends ``{"authorized": true}`` — or a whole verdict object — in
  the payload changes nothing but the refusal text naming the claim it ignored. What lands is the work
  unit the candidate describes (status QUEUED, read back from the store); what never lands here is the
  plan's execution, which stays behind ``work-unit.dispatch`` until an executor has a native receipt;
* the goal text a Work Unit carries stays in the store. The read-only Observer projection deliberately
  publishes checkpoint key names and a digest, never the values, so a control write cannot smuggle a
  prompt body into the Observer.
"""
from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

import sys

_ROOT = Path(__file__).resolve().parents[2]
for _entry in (
    _ROOT / "services" / "task-governance",
    _ROOT / "services" / "orchestration",
    _ROOT / "packages" / "client-neutral-core" / "scripts",
):
    sys.path.insert(0, str(_entry))

import jsonschema  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from evidence_range_reader import name_is_sensitive  # noqa: E402
from permission_gate import ActionKind, PermissionGate, Policy, RiskTier  # noqa: E402
from plan_candidate import (R_AUTHORIZED, SELF_CONFER_FIELDS, build_candidate,  # noqa: E402
                            check_candidate)
from project_temp import fixture_dir  # noqa: E402
from path_text import (  # noqa: E402  single home for the text rule: see path_text's docstring
    inside_root as _inside_project,
    normalise_path,
    path_is_anchored,
    path_is_drive_relative,
    path_is_unc,
    relative_inside,
)

from sidecar import _allowed_origin, _is_loopback_host  # noqa: E402
from sidecar_endpoint import read_descriptor, validate_descriptor  # noqa: E402
from snapshot_api import project_task_record  # noqa: E402

SIDECAR_DESCRIPTOR_PATH = "sidecar-endpoint.json"
SCHEMA_VERSION = "worklab/control-service/v1"
REQUEST_CONTRACT = _ROOT / "packages/contracts/schemas/workflow/control-operation.schema.json"
MAX_BODY_BYTES = 65_536
DESCRIPTOR_PATH = "control-endpoint.json"
RECEIPTS_PATH = "control-receipts.jsonl"
# The identity read route (WUI-10): one operation, addressed by the task_id it already used.
IDENTITY_SCHEMA = "worklab/control-operation-identity/v1"
WRITE_RECEIPT_KINDS = ("WORK_UNIT_QUEUED", "REPLAY")
# The append-only file is scanned from the end and stopped here, because `task_id` arrives from a caller
# and a reader that walks an unbounded file is a denial of service waiting for a long receipts log.
MAX_RECEIPT_SCAN = 400
# The three outcomes the owner's constraints separate: a write landing is not a native load, and a native
# load is not the target doing the work. Each is judged only from evidence of its own step.
OUTCOME_STEPS = (("write", "写入唯一账本"),
                 ("nativeLoad", "原生加载读回"),
                 ("targetBehaviour", "目标行为确认"))

# The local authorization record (see ControlPlane._trusted_grants). It is a DECISION record, not a
# credential store: grant id -> scope text, signed out of band by the human gate. This service only ever
# reads it, there is no API that writes it, and it holds no secret of any kind.
TRUSTED_GRANTS_PATH = "control-trusted-grants.json"
GRANT_RECORD_SCHEMA = "worklab/control-trusted-grants/v1"
# Vocabulary the service understands in a grant scope. Anything else fails closed: an unrecognised scope
# is not a licence, it is a record this code cannot interpret.
GRANT_SCOPE_ANY = "*"
GRANT_SCOPE_WORK_UNIT_PREFIX = "work-unit:"
# What the gate is asked about. Passing the operation name meant the gate's own escalation -- a
# filesystem target naming .env / credential / secret / auth is CRITICAL -- could never fire, because
# "config.diff" contains none of those words. The subject is the thing acted on.
SUBJECT_FIELDS = ("target_file", "path", "target", "file", "workUnitId", "taskId", "candidateId")
# Prefix denials for the places this repository keeps live configuration and session state. The name test
# in evidence_range_reader is the finer-grained layer; these are the coarse ones that hold even when a file
# is named innocently.
FORBIDDEN_TARGETS = ("config/", ".hermes/task-runtime/", ".hermes/task-artifacts/")
# The read route refuses every name in that shared vocabulary. This operation exists to inspect a
# *configuration document*, so the three tokens that describe configuration files rather than credential
# stores are not refused here -- and the answer it may give is limited to "this key path exists or does
# not", which is what makes the narrower list safe to carry.
_DIFFABLE_EXEMPTIONS = ("config.yaml", "config.yml")
# A restored backup or an evidence copy of a config file is not the live configuration this operation is
# allowed to reason about: it can carry another machine's providers, paths and field names, and it is not
# what a plan would change. Config documents are diffable only on a declared configuration surface.
NON_DIFFABLE_ROOTS = (".project-local/", ".hermes/", "docs/", "tests/")


def relative_within_root(lexical: str, lexical_root: str) -> str | None:
    """The path of the target relative to the project, computed as TEXT.

    `Path.relative_to` is the third host query in this file's history: `normalise_path` case-folds so that
    containment reads the same on every machine, and the lower-cased lexical path then fails to compare
    against the original-case root on a case-SENSITIVE filesystem while succeeding on Windows. That raised
    ValueError, which the diff treated as "not ours to read" -- so on the Linux runner every legitimate
    config target was refused while the same assertions passed locally.
    """
    prefix = lexical_root.rstrip("/") + "/"
    return lexical[len(prefix):] if lexical.startswith(prefix) else None


def _is_non_diffable_target(resolved: Path, relative: str | None) -> bool:
    if relative is None:
        return True  # outside this project there is nothing for this operation to plan against
    if name_is_sensitive(resolved, exempt=_DIFFABLE_EXEMPTIONS):
        return True
    return any(relative.lower().startswith(prefix) for prefix in NON_DIFFABLE_ROOTS)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _field_presence(text: str | None, field: str) -> tuple[bool | None, str]:
    """Answer "does this config declare this field" as a key question, never as a substring question.

    `field in before` turned the diff into a content oracle: a caller could binary-search any in-repo file
    one yes/no at a time, which is the same hole ERR-166 describes on the read side. Parsing the document
    and walking dotted keys means the only thing learnable about a file is its configuration shape; an
    unparseable or non-mapping document reports UNKNOWN rather than falling back to a text search.
    """
    if text is None:
        return None, "FILE_ABSENT"
    document: Any = None
    try:
        document = json.loads(text)
    except (json.JSONDecodeError, ValueError):
        try:
            import yaml  # declared in work-lab-python-deps.json alongside jsonschema

            document = yaml.safe_load(text)
        except Exception:  # noqa: BLE001 - any parser failure is "cannot tell", which is the honest state
            return None, "DOCUMENT_UNPARSEABLE"
    if not isinstance(document, dict):
        return None, "DOCUMENT_NOT_A_MAPPING"
    node: Any = document
    for part in field.split("."):
        if not isinstance(node, dict) or part not in node:
            return False, "KEY_PATH_RESOLVES"
        node = node[part]
    return True, "KEY_PATH_RESOLVES"


@dataclass(frozen=True)
class OperationSpec:
    operation: str
    implemented: bool
    action: ActionKind
    reason_code: str
    reason: str
    next_action: str | None


OPERATIONS: dict[str, OperationSpec] = {
    "work-unit.create": OperationSpec(
        "work-unit.create", True, ActionKind.FILESYSTEM, "WORK_UNIT_CREATED",
        "任务写入 canonical store 的 tasks 表（唯一账本），状态 QUEUED，等待执行器领取。",
        "在 Observer 的 Work 泳道用 ?view=work&taskId=… 读回这条记录。",
    ),
    "work-unit.materialize": OperationSpec(
        "work-unit.materialize", True, ActionKind.FILESYSTEM, "CANDIDATE_MATERIALIZED",
        "已授权的 PlanningCandidate 由服务端重新核验授权后，经与 work-unit.create 相同的写链落为 QUEUED 工作单元；"
        "候选描述的变更本身没有被执行，派发仍受 work-unit.dispatch 的 NOT_IMPLEMENTED 阻塞。",
        "工作单元已在队列里；要真正跑起来需要 work-unit.dispatch 接上一个能给出 native receipt 的执行器。",
    ),
    "work-unit.revise": OperationSpec(
        "work-unit.revise", False, ActionKind.FILESYSTEM, "NO_REVISION_CONTRACT_WIRED",
        "修订合同在 Task Ledger 里存在，但还没有受控的写入口；不假装能改。",
        "需要一条明确的修订合同接线（含 monotonic floor 与旧修订拒绝）。",
    ),
    "work-unit.dispatch": OperationSpec(
        "work-unit.dispatch", False, ActionKind.EXTERNAL_MUTATION, "EXECUTOR_NOT_IMPLEMENTED",
        "原生执行器的 ACP 动词目前逐条返回 NOT_IMPLEMENTED（AG-06/G06），派发没有原生副作用可验证。",
        "先接一个真实执行器的 dispatch 动词与 native receipt，再开放这一项。",
    ),
    "approval.decide": OperationSpec(
        "approval.decide", False, ActionKind.EXTERNAL_MUTATION, "NO_APPROVAL_WRITE_CONTRACT",
        "审批面在快照里是只读投影；没有可写的审批合同就不提供批准按钮。",
        "需要审批决定合同（决定人、范围、被决定修订、回执）。",
    ),
    "execution.cancel": OperationSpec(
        "execution.cancel", False, ActionKind.EXTERNAL_MUTATION, "EXECUTOR_NOT_IMPLEMENTED",
        "取消需要执行器真实停止；取消后不得再写，这一条目前无法 native 读回。",
        "执行器 cancel 动词接通后启用。",
    ),
    "execution.retry": OperationSpec(
        "execution.retry", False, ActionKind.EXTERNAL_MUTATION, "EXECUTOR_NOT_IMPLEMENTED",
        "重试必须不重复副作用；没有幂等身份的执行器就没有可保证的重试。",
        "执行器 retry 动词与幂等身份接通后启用。",
    ),
    "execution.resume": OperationSpec(
        "execution.resume", False, ActionKind.EXTERNAL_MUTATION, "EXECUTOR_NOT_IMPLEMENTED",
        "恢复要求原生会话身份可回读；facade 目前把 resume 降级为 NEW_SESSION。",
        "带 verified marker 的原生 resume 接通后启用。",
    ),
    "config.discover": OperationSpec(
        "config.discover", False, ActionKind.FILESYSTEM,
        "READ_LANDED_ELSEWHERE",
        "发现是读操作，已由配置控制平面与 Observer 读侧承担；控制服务不提供只读动词。",
        "在 Observer 查看配置投影；写侧用 config.diff / config.apply。",
    ),
    "config.diff": OperationSpec(
        "config.diff", True, ActionKind.FILESYSTEM, "PLAN_COMPUTED",
        "按 ownership 计算精确 diff：这是计划，plan != write，不下任何写结论。",
        "确认 expected-before/after 后再发 config.apply。",
    ),
    "config.apply": OperationSpec(
        "config.apply", False, ActionKind.EXTERNAL_MUTATION, "TARGET_NOT_AUTHORISED",
        "写真实客户端配置需要 exact target 授权（项目/路径/字段），本轮授权不含它；拒绝而不是模拟成功。",
        "给出确切目标与字段范围后可在项目内 fixture 上验证写链与 rollback。",
    ),
    "config.readback": OperationSpec(
        "config.readback", False, ActionKind.FILESYSTEM, "NO_WRITE_TO_READ_BACK",
        "readback 只在真实写之后有意义；没有写就不返回一个看起来像验证的读数。",
        "config.apply 被授权并执行后启用。",
    ),
    "config.rollback": OperationSpec(
        "config.rollback", False, ActionKind.DESTRUCTIVE, "NO_RECOVERY_HANDLE",
        "回滚需要恢复句柄；没有句柄时不提供看起来安全的撤销。",
        "写入时同步产出恢复句柄后启用。",
    ),
}

_STATUS_BY_DECISION = {"allowed": None, "needs_human": "NEEDS_HUMAN", "denied": "REFUSED"}

# The kinds this service is even allowed to put in front of the gate, derived from what the implemented
# operations actually declare: adding an operation cannot quietly widen it, and a kind outside scope is
# DENIED by the gate rather than allowed by default.
GATED_KINDS = frozenset(spec.action for spec in OPERATIONS.values() if spec.implemented)


def _is_loopback_authority(host_header: str | None) -> bool:
    """Accept a Host header with or without the port (`127.0.0.1:8123` is still loopback).

    The shared sidecar helper takes a bare host; feeding it a `host:port` pair makes it fail closed,
    which would refuse the shell this service exists to serve. A missing port is a bare IP or name, so
    splitting on the last colon cannot turn a loopback literal into a non-loopback one.
    """
    if not host_header:
        return False
    candidate, port = _split_host_port(host_header)
    if port and not port.isdigit():
        return False
    return _is_loopback_host(candidate)


def _split_host_port(value: str) -> tuple[str, str]:
    """Separate a Host header into host and port, including the bracketed IPv6 form.

    `[::1]:8123` has two colons, so a `count(":") == 1` test leaves `::1]:8123` in place and the loopback
    literal fails its own check -- a self-lockout, but a wrong one worth fixing rather than working around.
    """
    text = value.strip()
    if text.startswith("["):
        end = text.find("]")
        if end != -1:
            return text[1:end], text[end + 1:].lstrip(":")
        return text.rstrip("]"), ""
    host, separator, port = text.rpartition(":")
    if separator and host and ":" not in host:
        return host, port
    return text, ""


class ControlPlane:
    """Executes one control request against the existing authority chain."""

    def __init__(self, store: CanonicalStore, *, project_root: Path, evidence_ceiling: str = "SYNTHETIC",
                 receipts_path: Path | None = None, grants_path: Path | None = None,
                 capability_registry: Any | None = None) -> None:
        self.store = store
        # No `.resolve()` here: it consults the host, and the host invents a drive letter for a
        # POSIX-shaped root on Windows, so the same (root, boundary) pair decided differently per machine.
        # Callers pass an absolute checkout root; containment and relative paths are computed from text.
        self.project_root = Path(project_root)
        if not path_is_anchored(str(self.project_root)):
            raise ValueError(
                f"project_root {self.project_root} is not anchored: a root that depends on the current "
                "working directory would make every boundary decision machine-relative")
        self.evidence_ceiling = evidence_ceiling
        self.receipts_path = receipts_path
        # Default: the authorization record sits next to the receipts in the same runtime root the
        # sidecar owns. A caller may point it elsewhere (a live deployment, a fixture) but no request
        # field can — a client that could choose its own grant source would be authorising itself.
        self.grants_path = Path(grants_path) if grants_path is not None else (
            Path(receipts_path).parent / TRUSTED_GRANTS_PATH if receipts_path is not None else None)
        self.capability_registry = capability_registry
        # A bare Policy() would auto-allow every kind that exists, which makes the gate decorative: the
        # service would "delegate every decision to the permission gate" while the gate had nothing to say.
        # Scope is the kinds the implemented operations actually are, and a HIGH risk needs a human -- so a
        # target that names a credential is refused by policy rather than by this file remembering to check.
        self.gate = PermissionGate(Policy(
            scope=GATED_KINDS,
            human_gate_from=RiskTier.HIGH,
            forbidden_paths=FORBIDDEN_TARGETS,
        ))
        self._schema = json.loads(REQUEST_CONTRACT.read_text(encoding="utf-8"))
        self._validator = jsonschema.Draft202012Validator(self._schema,
                                                          format_checker=jsonschema.FormatChecker())
        self._lock = threading.Lock()

    # -- answers -----------------------------------------------------------
    @staticmethod
    def _bounded(text: str, limit: int) -> str:
        """The contract caps reason/next_action length, so an over-long answer would be an invalid answer.

        Truncation is marked, never silent: a clipped reason must announce that it was clipped.
        """
        text = str(text or "")
        return text if len(text) <= limit else text[: limit - 12] + "…（已截断）"

    def result(self, spec: OperationSpec | None, status: str, reason_code: str, reason: str,
               *, request: dict[str, Any] | None = None, task_id: str | None = None,
               receipt: dict[str, Any] | None = None, readback: dict[str, Any] | None = None,
               evidence: str | None = None, next_action: str | None = None) -> dict[str, Any]:
        return {
            "schema_version": "worklab/control-operation-result/v1",
            "operation": (spec.operation if spec else (request or {}).get("operation", "unknown")),
            "idempotency_key": (request or {}).get("idempotency_key", "unparsed"),
            "status": status,
            "reason_code": self._bounded(reason_code, 120),
            "reason": self._bounded(reason, 2000),
            "task_id": task_id,
            "receipt": receipt,
            "readback": readback,
            "evidence_level": evidence or "NO_EVIDENCE",
            "observed_at": _now(),
            "next_action": self._bounded(next_action, 2000) if next_action else next_action,
        }

    def descriptor(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "observed_at": _now(),
            "transport": "loopback-only",
            "evidence_ceiling": self.evidence_ceiling,
            # Read state of the local authorization record, so the shell can tell the operator "there is
            # no grant record to check against" instead of letting every candidate fail opaquely. Counts
            # and a relative file name only — the record's contents are never published.
            "authorization_record": self._trusted_grants()[1],
            "operations": [
                {
                    "operation": spec.operation,
                    "support": "IMPLEMENTED" if spec.implemented else "NOT_IMPLEMENTED",
                    "reason_code": spec.reason_code,
                    "reason": spec.reason,
                    "next_action": spec.next_action,
                }
                for spec in OPERATIONS.values()
            ],
        }

    # -- the lost-refresh path: re-query the operation an identity already names -------------------------
    def receipts_for(self, task_id: str, *, limit: int = 20) -> list[dict[str, Any]]:
        """The receipts this plane appended for one task identity, oldest first, bounded.

        The append-only file is the only durable answer to "did that write already happen" once the page
        that sent it is gone: this process keeps no in-memory operation table, and adding one would be a
        second ledger for the same fact. Only the receipt's own handle fields are republished -- kind,
        moment, digest -- never the record body that sits next to it in the same line.
        """
        if self.receipts_path is None or not self.receipts_path.is_file():
            return []
        try:
            lines = self.receipts_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            return []
        found: list[dict[str, Any]] = []
        for line in lines[-MAX_RECEIPT_SCAN:]:
            try:
                entry = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not isinstance(entry, dict) or not isinstance(entry.get("receipt"), dict):
                continue
            record = entry.get("record")
            if not isinstance(record, dict):
                continue
            # `_append_receipt` stores the OBSERVER projection next to the receipt, and that projection
            # spells its identity `taskId`. Reading only `task_id` found nothing for every real write and
            # the honest-looking answer was NO_RECEIPT_FOR_IDENTITY over a receipts file that did contain
            # the line -- the two spellings are checked because this reader must not inherit a rename.
            if record.get("taskId") != task_id and record.get("task_id") != task_id:
                continue
            receipt = entry["receipt"]
            found.append({"receipt_id": self._bounded(receipt.get("receipt_id"), 120),
                          "kind": self._bounded(receipt.get("kind"), 60),
                          "observed_at": self._bounded(receipt.get("observed_at"), 40),
                          "digest": self._bounded(receipt.get("digest"), 64)})
        return found[-limit:]

    def operation_identity(self, task_id: str) -> dict[str, Any]:
        """What the ledger and the receipts say about one identity right now, step by separate step.

        This exists because the acceptance separates three outcomes that a single "success" string would
        fuse: the write reaching the唯一账本, a native client having loaded it, and the target behaving
        accordingly. Only the first has evidence here; the other two report the support level of the
        operation that would have to produce them, read live from OPERATIONS so this answer cannot rot
        into a claim that outlives the gap.
        """
        rows = {row["task_id"]: row for row in self.store.list_tasks()}
        row = rows.get(task_id)
        answer: dict[str, Any] = {
            "schema_version": IDENTITY_SCHEMA,
            "task_id": self._bounded(task_id, 80),
            "observed_at": _now(),
            "found": row is not None,
            "transport": "loopback-only",
        }
        if row is None:
            answer["reason_code"] = "OPERATION_NOT_FOUND"
            answer["reason"] = (f"唯一账本里没有 {task_id}。这不是一次失败的写，也不代表什么都没发生过；"
                                "它只代表这个身份在本账本里没有记录。")
            answer["outcomes"] = [{"id": step_id, "label": label, "state": "NO_RECORD",
                                   "basis": "canonical store tasks 表",
                                   "detail": "没有该身份的账本行，三步都无从判断。"}
                                  for step_id, label in OUTCOME_STEPS]
            answer["receipts"] = []
            return answer

        projected = project_task_record(row)
        digest = hashlib.sha256(json.dumps(projected, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")).encode("utf-8")).hexdigest()
        checkpoint = row.get("checkpoint") or {}
        key = str(checkpoint.get("idempotency_key") or "")
        receipts = self.receipts_for(task_id)
        matched = [item for item in receipts if item["digest"] == digest and item["kind"] in WRITE_RECEIPT_KINDS]
        if matched:
            write_state = "CONFIRMED"
        elif self.receipts_path is None:
            write_state = "NO_RECEIPT_PUBLISHED"
        elif receipts:
            write_state = "RECEIPT_DIGEST_DIVERGED"
        else:
            write_state = "NO_RECEIPT_FOR_IDENTITY"
        readback_spec = OPERATIONS.get("config.readback")
        dispatch_spec = OPERATIONS.get("work-unit.dispatch")
        answer.update({
            "status": self._bounded(row.get("status"), 40),
            "project_id": self._bounded(row.get("project_id"), 80),
            # The key is the operation's identity, and the page that minted it is exactly the caller that
            # has lost it; the Observer's projection deliberately does not publish checkpoint VALUES, this
            # loopback route publishes only this one field plus the key NAMES the snapshot already lists.
            "idempotency_key": self._bounded(key, 120) if key else None,
            "idempotency_key_present": bool(key),
            "record_digest": digest,
            "checkpoint_fields": sorted(checkpoint),
            "receipts": receipts,
            "outcomes": [
                {"id": "write", "label": "写入唯一账本", "state": write_state,
                 "basis": "canonical store 行 + 本身份的回执摘要一致",
                 "detail": (f"回执 {len(matched)} 条与当前投影摘要一致。" if matched else
                            "有账本行，但没有与当前摘要一致的回执：写没有被证实，不写成成功。")},
                {"id": "nativeLoad", "label": "原生加载读回", "state": "NOT_PROJECTED",
                 "basis": f"config.readback support={getattr(readback_spec, 'implemented', False)}",
                 "detail": (getattr(readback_spec, "reason", "没有该操作声明。")
                            if readback_spec else "没有 config.readback 声明。"),
                 "owner": "services/control/config.readback 的生产者"},
                {"id": "targetBehaviour", "label": "目标行为确认", "state": "NOT_PROJECTED",
                 "basis": f"work-unit.dispatch support={getattr(dispatch_spec, 'implemented', False)}",
                 "detail": (getattr(dispatch_spec, "reason", "没有该操作声明。")
                            if dispatch_spec else "没有 work-unit.dispatch 声明。"),
                 "owner": "能给出 native receipt 的执行器"},
            ],
        })
        return answer

    # -- the one entry point ------------------------------------------------
    def execute(self, request: dict[str, Any]) -> dict[str, Any]:
        errors = sorted(self._validator.iter_errors(request), key=lambda e: list(e.absolute_path))
        if errors:
            first = errors[0]
            return self.result(None, "REFUSED", "INVALID_REQUEST",
                               f"请求不符合 control-operation 合同：{first.message}（路径 {'/'.join(map(str, first.absolute_path)) or '<root>'}）",
                               request=request,
                               next_action="按合同补齐该字段；缺字段不会被当作空值执行。")

        spec = OPERATIONS.get(request["operation"])
        if spec is None:
            return self.result(None, "REFUSED", "UNKNOWN_OPERATION",
                               f"没有声明过的操作不执行：{request['operation']}", request=request)

        if not spec.implemented:
            return self.result(spec, "NOT_IMPLEMENTED", spec.reason_code, spec.reason,
                               request=request, next_action=spec.next_action)

        scope_failure = self._scope_failure(request)
        if scope_failure is not None:
            code, reason = scope_failure
            return self.result(spec, "REFUSED", code, reason, request=request,
                               next_action="把边界收窄到本仓库内的项目路径。")

        decision = self.gate.evaluate(spec.action, target=self._subject(request),
                                      scope=";".join(request["scope"]["boundaries"]),
                                      executor=request["actor"])
        if decision.status.value != "allowed":
            status = _STATUS_BY_DECISION.get(decision.status.value, "REFUSED")
            return self.result(spec, status, f"GATE_{decision.status.value.upper()}", decision.reason,
                               request=request,
                               next_action="该决定由策略给出，执行器与调用方都不是最终授权源。")

        if request["operation"] == "work-unit.create":
            return self._create_work_unit(request, spec)
        if request["operation"] == "work-unit.materialize":
            return self._materialize_candidate(request, spec)
        if request["operation"] == "config.diff":
            return self._config_diff(request, spec)
        return self.result(spec, "NOT_IMPLEMENTED", "DISPATCH_MISSING",
                           "该操作通过了检查但没有实现分支。", request=request)

    # -- checks -------------------------------------------------------------
    def _subject(self, request: dict[str, Any]) -> str:
        """What the operation actually acts on, as a project-relative path or an identity.

        The gate's own escalation ("a filesystem target naming .env / credential / secret / auth is
        CRITICAL") reads the target, so passing the operation name made that branch structurally
        unreachable: `config.diff` never contains those words even when the payload diffs `.env`. A
        relative path is resolved against this project so a caller cannot dodge the prefix denials by
        naming `config/../.env`.
        """
        payload = request.get("payload")
        raw = ""
        if isinstance(payload, dict):
            for field in SUBJECT_FIELDS:
                if payload.get(field):
                    raw = str(payload[field])
                    break
        if not raw:
            raw = str(request.get("task_id") or "")
        if not raw:
            return str(request["operation"])
        anchored = raw if path_is_anchored(raw) else f"{normalise_path(self.project_root)}/{raw}"
        inside, _root, lexical = _inside_project(anchored, self.project_root)
        if inside:
            root = normalise_path(self.project_root).rstrip("/")
            return lexical[len(root) + 1:] if lexical != root else "."
        return lexical

    def _scope_failure(self, request: dict[str, Any]) -> tuple[str, str] | None:
        """Every declared boundary must resolve inside this repository.

        A request may name the project it acts on; it may not widen that project's filesystem. E:/F: are
        forbidden roots (project-data-boundary.json) and are refused by name so the reason is legible.
        """
        for raw in request["scope"]["boundaries"]:
            text = str(raw or "").strip()
            if not text:
                return ("EMPTY_BOUNDARY", "边界为空，不能代表一个范围。")
            lowered = text.replace("\\", "/").lower()
            if lowered.startswith(("e:/", "f:/")):
                return ("FORBIDDEN_ROOT", f"边界 {text} 位于受保护的外部盘根，本项目的边界合同禁止读写。")
            if path_is_drive_relative(text):
                # `E:secrets` means "relative to whatever the current directory on E: happens to be", so it
                # cannot be verified or narrowed. Detected from the text: Path.drive only reports a drive on
                # the platform that owns the path syntax, and says nothing on the other one.
                return ("DRIVE_RELATIVE_BOUNDARY",
                        f"边界 {text} 是盘符相对路径，指向随当前目录而变的对象，无法验证也无法收窄。")
            if path_is_unc(text):
                # UNC has no drive and does not report itself as absolute on Windows, so it used to fall
                # through the containment test and be recorded as granted scope.
                return ("UNANCHORED_BOUNDARY",
                        f"边界 {text} 是 UNC 路径，无法在本机之外判定它包含于哪个项目根，控制服务不接受不能验证的边界。")
            # Anchoring is decided from the string, not from Path: on the Linux job a Windows-style absolute
            # path looks relative to posixpath, and joining it under the project root turns "refuse this
            # other project" into "grant a write inside this one".
            candidate = text if path_is_anchored(text) else f"{normalise_path(self.project_root)}/{text}"
            inside, lexical_root, lexical = _inside_project(candidate, self.project_root)
            if not inside:
                return ("OUT_OF_PROJECT_SCOPE",
                        f"边界 {text} 在本仓库之外（规范化后 {lexical} 不在 {lexical_root} 之内），"
                        "控制服务不接受越界写。")
        return None

    def _ceiling(self, requested: str) -> str:
        order = ["NO_EVIDENCE", "SIMULATED", "SYNTHETIC", "INTEGRATED", "REAL"]
        return requested if order.index(requested) <= order.index(self.evidence_ceiling) else self.evidence_ceiling

    def _trusted_grants(self) -> tuple[dict[str, str], dict[str, Any]]:
        """Read the ONE local authorization record: grant id -> granted scope.

        AG-16's rule is that a plan may only *reference* a grant that resolves in a trusted local record,
        so this is the side that resolves it, on every call. Re-read each time (never cached): a grant
        that was revoked or expired between two requests must not keep working. Every unparseable shape
        yields an empty grant set plus a legible state — a record this code cannot read is not a grant,
        and it is also not a silent pass.
        """
        state: dict[str, Any] = {"path": None, "readable": False, "grants": 0, "expired": 0,
                                 "malformed": 0, "note": "没有配置授权记录路径，任何候选都不会通过核验。"}
        if self.grants_path is None:
            return {}, state
        state["path"] = self.grants_path.name
        if not self.grants_path.is_file():
            state["note"] = f"授权记录不存在：{self.grants_path.name}（缺记录＝没有授权，不是放行）"
            return {}, state
        try:
            document = json.loads(self.grants_path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError) as error:
            state["note"] = f"授权记录读不开：{type(error).__name__}，按没有授权处理。"
            return {}, state
        entries = document.get("grants") if isinstance(document, dict) else None
        if not isinstance(entries, list):
            state["note"] = "授权记录形状不对（grants 不是数组），按没有授权处理。"
            return {}, state
        now = _now()
        grants: dict[str, str] = {}
        for entry in entries:
            if not isinstance(entry, dict):
                state["malformed"] += 1
                continue
            grant_id = str(entry.get("grant_id") or "").strip()
            scope = str(entry.get("scope") or "").strip()
            if not grant_id or not scope:
                state["malformed"] += 1
                continue
            expires_at = entry.get("expires_at")
            if isinstance(expires_at, str) and expires_at.strip():
                # ISO-8601 UTC strings sort as strings, which is exactly what the store's own lease
                # expiry comparison relies on.
                if expires_at.strip() <= now:
                    state["expired"] += 1
                    continue
            grants[grant_id] = scope
        state.update(readable=True, grants=len(grants),
                     note=f"本地授权记录已读：{len(grants)} 条有效（内容不对外投影）。")
        return grants, state

    @staticmethod
    def _grant_covers(scope: str, work_unit_id: str) -> bool:
        """Does this grant authorise THIS work unit? Resolving a grant is not the same as scoping it.

        ``check_candidate`` hands back the scope text the record carries; without this second check a
        single grant id would authorise any candidate that names it.
        """
        text = str(scope or "").strip()
        if text == GRANT_SCOPE_ANY:
            return True
        return text == f"{GRANT_SCOPE_WORK_UNIT_PREFIX}{str(work_unit_id).strip()}"

    @staticmethod
    def _claims_in(payload: dict[str, Any]) -> list[str]:
        """Self-confer fields a caller tried to smuggle in the request payload (never honoured)."""
        return sorted(key for key in SELF_CONFER_FIELDS if (payload or {}).get(key))


    # -- implemented operations --------------------------------------------
    def _create_work_unit(self, request: dict[str, Any], spec: OperationSpec) -> dict[str, Any]:
        task_id = str(request["task_id"] or "").strip()
        if not task_id:
            return self.result(spec, "REFUSED", "TASK_ID_REQUIRED",
                               "创建 Work Unit 必须给出确定性的 task_id：幂等重放靠它，不靠时间去猜。",
                               request=request)
        goal = str((request.get("payload") or {}).get("goal") or "").strip()
        if not goal:
            return self.result(spec, "REFUSED", "GOAL_REQUIRED",
                               "没有目标的工作单元不是一个可执行对象；不接受空目标。", request=request)
        return self._write_work_unit(request, spec, task_id=task_id, goal=goal)

    def _write_work_unit(self, request: dict[str, Any], spec: OperationSpec, *, task_id: str, goal: str,
                         origin: dict[str, Any] | None = None,
                         extra_readback: dict[str, Any] | None = None) -> dict[str, Any]:
        """The single write chain: canonical store under its lease/fencing rules, readback, receipt digest.

        Both ``work-unit.create`` and ``work-unit.materialize`` come through here. One ledger, one
        idempotency rule, one receipt engine — an operation that reached the same store by a second path
        would be a second story about the same fact.
        """
        checkpoint: dict[str, Any] = {
            "goal": goal,
            "boundaries": list(request["scope"]["boundaries"]),
            "granted_by": request["scope"]["granted_by"],
            "idempotency_key": request["idempotency_key"],
            "requested_at": request["requested_at"],
        }
        # origin keys must stay clear of the store's forbidden-field vocabulary (canonical_store
        # .validate_record rejects any key whose normalised name contains "authorization", "secret",
        # "prompt", ...). That is why the candidate's `authorizationRef` is recorded as `grantRef`.
        checkpoint.update(origin or {})

        record = {
            "task_id": task_id,
            "project_id": request["project_id"],
            "status": "QUEUED",
            "checkpoint": checkpoint,
        }
        with self._lock:
            # Insert-or-conflict, decided by the row that exists afterwards -- not by a snapshot taken
            # before a lock this process does not share with the sidecar. The old shape read the whole
            # table, then upserted, so a concurrent writer's lease could be wiped by a create that never
            # claimed one, and the identity check could pass on a row that changed in between.
            created = self.store.insert_task_if_absent(record)

        readback_row = {row["task_id"]: row for row in self.store.list_tasks()}.get(task_id)
        replayed = False
        if not created:
            prior_key = str(((readback_row or {}).get("checkpoint") or {}).get("idempotency_key") or "")
            if prior_key and prior_key != request["idempotency_key"]:
                return self.result(spec, "REFUSED", "IDEMPOTENCY_CONFLICT",
                                   f"task_id {task_id} 已存在且属于另一个幂等身份；不覆盖别人的工作单元。",
                                   request=request, task_id=task_id)
            replayed = True
        if readback_row is None:
            return self.result(spec, "READBACK_MISMATCH", "READBACK_MISSING",
                               f"写入后读不到 {task_id}：写没有被证实，不返回成功。",
                               request=request, task_id=task_id)
        projected = project_task_record(readback_row)
        digest = hashlib.sha256(json.dumps(projected, ensure_ascii=False, sort_keys=True,
                                          separators=(",", ":")).encode("utf-8")).hexdigest()
        receipt = {
            "receipt_id": f"{spec.operation}:{task_id}",
            "kind": "REPLAY" if replayed else "WORK_UNIT_QUEUED",
            "observed_at": _now(),
            "digest": digest,
        }
        self._append_receipt(receipt, projected)
        return self.result(spec, "ACCEPTED", spec.reason_code, spec.reason,
                           request=request, task_id=task_id, receipt=receipt,
                           readback={**projected, "replayed": replayed, **(extra_readback or {})},
                           evidence=self._ceiling("SYNTHETIC"), next_action=spec.next_action)

    # -- the AG-16 consumer: authorized candidate -> real work unit ---------
    def _materialize_candidate(self, request: dict[str, Any], spec: OperationSpec) -> dict[str, Any]:
        """Turn an authorized PlanningCandidate into the work unit it describes.

        The candidate arrives as content, nothing else counts as authority:
        1. it is rebuilt with ``build_candidate`` so the identity is the content digest this process
           computed, not a digest the caller asserted;
        2. ``task_id`` must equal the candidate's own ``workUnitId`` — a request cannot re-point an
           authorized plan at a different unit of work;
        3. ``check_candidate`` runs AGAIN here, against the local authorization record, so a payload
           claiming ``authorized: true`` (or carrying a verdict object) is only ever evidence of a claim
           that gets named in the refusal text;
        4. the resolved grant scope must cover this exact work unit;
        5. the goal text is derived from the candidate, never taken from the payload, and the plan body is
           stored in the work unit (so an executor has something to run) while the read result carries
           only counts and digests — the candidate's text never rides back out of the read side.
        Dispatching the plan is a different operation (``work-unit.dispatch``) and stays NOT_IMPLEMENTED;
        this writes a QUEUED unit and says so.
        """
        payload = request.get("payload") or {}
        draft = payload.get("candidate")
        if not isinstance(draft, dict) or not draft:
            return self.result(spec, "REFUSED", "CANDIDATE_MISSING",
                               "payload.candidate 必须是一个规划候选对象；没有候选就没有可核验的计划。",
                               request=request,
                               next_action="把 PlanningCandidate 的原文放进 payload.candidate。")
        try:
            candidate = build_candidate(draft)
        except (ValueError, TypeError) as error:
            return self.result(spec, "REFUSED", "CANDIDATE_INVALID",
                               f"候选不合格，拒绝而不是猜：{str(error)[:400]}", request=request,
                               next_action="补齐候选缺的字段；缺失的事实字段不会被默认值填上。")

        task_id = str(request["task_id"] or "").strip()
        work_unit_id = str(candidate.get("workUnitId") or "").strip()
        if not task_id:
            return self.result(spec, "REFUSED", "TASK_ID_REQUIRED",
                               "物化候选必须给出 task_id，而且它必须等于候选的 workUnitId。",
                               request=request, task_id=None)
        if task_id != work_unit_id:
            return self.result(spec, "REFUSED", "CANDIDATE_IDENTITY_MISMATCH",
                               f"task_id {task_id} 与候选描述的 workUnitId {work_unit_id} 不一致："
                               "一条授权不能挪到另一个工作单元上用。", request=request, task_id=task_id)

        grants, grant_state = self._trusted_grants()
        verdict = check_candidate(candidate, trusted_grants=grants,
                                  capability_registry=self.capability_registry)
        claims = self._claims_in(payload)
        ignored = sorted(set(claims) | set(verdict.get("ignoredSelfClaims") or []))
        if verdict.get("status") != R_AUTHORIZED:
            return self.result(
                spec, "REFUSED", "CANDIDATE_NOT_AUTHORIZED",
                f"服务端复核未通过（候选状态 {verdict.get('status')}）：{verdict.get('reason')}"
                f"｜授权记录：{grant_state.get('note')}"
                + (f"｜已忽略请求里的自我授权声明：{'/'.join(ignored)}" if ignored else ""),
                request=request, task_id=task_id,
                next_action="在人方签署的本地授权记录里补上这条 grant 的 scope，"
                            "或在候选里引用一个已存在的 grant；请求字段不构成授权。")

        scope = str(verdict.get("authorizedScope") or "")
        if not self._grant_covers(scope, work_unit_id):
            return self.result(
                spec, "REFUSED", "GRANT_SCOPE_MISMATCH",
                f"grant {candidate.get('authorizationRef')} 的 scope 是 {scope or '空'}，"
                f"它不覆盖 {work_unit_id}；授权按 scope 生效，不按 grant 存在与否生效。",
                request=request, task_id=task_id,
                next_action=f"授权记录里把 scope 写成 {GRANT_SCOPE_WORK_UNIT_PREFIX}{work_unit_id}，"
                            f"或明确写成 {GRANT_SCOPE_ANY}。")

        changes = candidate.get("changes") or []
        verification = candidate.get("verification") or []
        baseline = candidate.get("baseline") or {}
        goal = (f"物化已授权的规划候选 {candidate['candidateId']}"
                f"（修订 {candidate['taskRevision']}，计划 {len(changes)} 项变更 / "
                f"{len(verification)} 项验收，基线 {str(baseline.get('commit') or baseline.get('digest') or 'unknown')[:12]}）")
        origin = {
            "planningCandidate": {
                "candidateId": candidate["candidateId"],
                "contentDigest": candidate["contentDigest"],
                "workUnitId": work_unit_id,
                "taskRevision": candidate["taskRevision"],
                "contextDigest": candidate.get("contextDigest"),
                "baseline": baseline,
                "planningSoftware": candidate.get("planningSoftware"),
                "targetCapability": candidate.get("targetCapability") or "",
                # `authorizationRef` is the contract's field name; the store refuses any key whose
                # normalised form contains "authorization", so the recorded field is `grantRef` and the
                # value is only an identifier of a decision that was verified in the local record.
                "grantRef": candidate.get("authorizationRef") or "",
                "grantScope": scope,
                # The plan body itself. A materialized unit that carries only a summary would be an empty
                # shell with nothing to run, which is the plan-only state this operation exists to end.
                # It stays here: `project_task_record` publishes key names and a digest, never values, so
                # the candidate's text reaches the executor and not the read-only projection.
                "changes": [str(item) for item in changes],
                "verification": [str(item) for item in verification],
                "verifiedBy": "control-service/check_candidate@" + _now(),
            },
        }
        capability = candidate.get("targetCapability") or ""
        extra = {
            "source": "planning-candidate",
            "candidateId": candidate["candidateId"],
            "candidateDigest": candidate["contentDigest"],
            "taskRevision": candidate["taskRevision"],
            "changesCount": len(changes),
            "verificationCount": len(verification),
            "grantScope": scope,
            "authorizationSource": "trusted-local-record",
            "ignoredSelfClaims": ignored,
            "capabilityCheck": ("NOT_CHECKED" if self.capability_registry is None else "CHECKED"),
            "capabilityDeclared": capability,
            "planExecuted": False,
            "executorDispatch": "NOT_IMPLEMENTED(work-unit.dispatch)",
            "written": True,
        }
        return self._write_work_unit(request, spec, task_id=task_id, goal=goal, origin=origin,
                                     extra_readback=extra)

    def _config_diff(self, request: dict[str, Any], spec: OperationSpec) -> dict[str, Any]:
        """Compute a plan through the existing config control plane. Plan is never reported as a write."""
        payload = request.get("payload") or {}
        target = str(payload.get("target_file") or "").strip()
        field = str(payload.get("field") or "").strip()
        wanted = payload.get("value")
        if not target or not field:
            return self.result(spec, "REFUSED", "DIFF_INPUT_INCOMPLETE",
                               "diff 需要 target_file 与 field；缺输入不产出看起来像计划的空答案。",
                               request=request)
        # Relative targets are relative to the project, never to whatever directory the caller ran
        # the service from — a diff computed against the wrong file is a plan built on nothing.
        # The refusal is decided from the text (see `_inside_project`); only after that is a real path built,
        # so a Linux runner can never turn "outside this project" into "a file inside it".
        root_text = self.project_root.as_posix()
        anchored = target if path_is_anchored(target) else f"{root_text}/{target}"
        inside, lexical_root, lexical = _inside_project(anchored, self.project_root)
        if not inside:
            return self.result(spec, "REFUSED", "TARGET_OUT_OF_PROJECT",
                               f"配置目标 {target} 不在本仓库内（规范化后 {lexical} 不在 {lexical_root} 之内）；"
                               "本轮没有对它之外的写权或读权。", request=request)
        # `anchored` keeps the declared case; `lexical` is only ever used to decide containment.
        resolved = Path(anchored)
        relative_target = relative_inside(anchored, self.project_root)
        if _is_non_diffable_target(resolved, relative_target):
            # The diff answers "does this document declare this key", which makes any file an oracle if the
            # answer is a substring test -- see ERR-166 for the same hole on the read side one commit
            # earlier. Credential, session and database files are refused outright; a config document is the
            # legitimate subject of this operation and is answered structurally, never by content search.
            return self.result(spec, "REFUSED", "TARGET_SENSITIVE",
                               f"配置目标 {resolved.name} 属于凭证、会话库或本地数据库类文件，或位于备份/证据副本这类"
                               "不是现行配置面的目录下；控制面不提供对它的一致性探测。",
                               request=request)
        before = resolved.read_text(encoding="utf-8", errors="replace") if resolved.is_file() else None
        present, present_state = _field_presence(before, field)
        changes = [{
            "field": field,
            "before": "<read-only: value not projected>" if before is not None else None,
            "after_declared": True if wanted is not None else False,
            "present_before": present,
            "presenceBasis": present_state,
        }]
        # PLANNED, not ACCEPTED: a diff that wrote nothing must not arrive in the same status shape
        # as a write that was verified by readback.
        return self.result(spec, "PLANNED", spec.reason_code, spec.reason, request=request,
                           receipt=None,
                           readback={"plan_only": True, "target": relative_target,
                                     "changes": changes,
                                     "written": False,
                                     "next": "config.apply 需要对该 exact target 的单独授权"},
                           evidence=self._ceiling("SYNTHETIC"), next_action=spec.next_action)

    def _append_receipt(self, receipt: dict[str, Any], projected: dict[str, Any]) -> None:
        if self.receipts_path is None:
            return
        line = json.dumps({"receipt": receipt, "record": projected}, ensure_ascii=False, sort_keys=True)
        self.receipts_path.parent.mkdir(parents=True, exist_ok=True)
        with self.receipts_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")


# ---------------------------------------------------------------------------
# loopback HTTP boundary
# ---------------------------------------------------------------------------
class _Handler(BaseHTTPRequestHandler):
    server_version = "WORK-LAB-Control/1"

    @property
    def plane(self) -> ControlPlane:
        return self.server.plane  # type: ignore[attr-defined]

    def log_message(self, *args: Any) -> None:  # no request bodies in logs
        return

    def _declared_length(self) -> int:
        try:
            return max(0, int(self.headers.get("Content-Length") or 0))
        except (TypeError, ValueError):
            return 0

    def _read_request_body(self) -> bytes:
        """The request body, read AT MOST ONCE and cached.

        Both halves of this handler need the same bytes: the POST path consumes them as the operation, and
        a refusal has to clear them so a keep-alive client's next read starts at a status line. A second
        `rfile.read(Content-Length)` after the body was already consumed blocks until the client times out
        -- which is exactly what the first version of this drain did to the success path.
        """
        cached = getattr(self, "_request_body_cache", None)
        if cached is not None:
            return cached
        length = self._declared_length()
        if length <= 0 or length > MAX_BODY_BYTES:
            # never buffer a request this handler has already decided not to serve
            self.close_connection = True
            data = b""
        else:
            try:
                data = self.rfile.read(length)
            except OSError:
                data = b""
            self.close_connection = True
        self._request_body_cache = data
        return data

    def _drain_request_body(self) -> None:
        """Clear a request body before a refusal is written, so the refusal is what the client reads.

        A 405 for a PUT that carried bytes left them in the socket buffer, and a client that keeps the
        connection open reads them as the beginning of the next response -- which is how a transport test
        came to see a broken status line instead of the refusal it was asserting.
        """
        self._read_request_body()

    def _send(self, status: int, payload: dict[str, Any]) -> None:
        self._drain_request_body()
        body = json.dumps(payload, ensure_ascii=False, sort_keys=True).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        try:
            self.wfile.write(body)
        except (ConnectionResetError, BrokenPipeError, OSError):
            # the peer went away; that is not a reason to log a traceback as if the service failed
            self.close_connection = True

    def _refused(self, status: int, code: str, reason: str) -> None:
        self._send(status, {"schema_version": "worklab/control-error/v1", "reason_code": code,
                            "reason": reason, "observed_at": _now()})

    def _origin_ok(self) -> bool:
        origin = self.headers.get("Origin")
        if origin is None:
            return True  # same-origin tools (curl, the shell opened from disk) send no Origin
        return _allowed_origin(origin)

    def _loopback_ok(self) -> bool:
        """The peer address, not just the Host header, has to be loopback.

        A header is what the client chose to say. ERR-166's lesson applies to the write side too: the one
        boundary I checked was the one a caller does not control -- a HOSTS entry or a forwarded socket can
        make a non-loopback client look like `127.0.0.1:8123` in its own header.
        """
        try:
            peer = ipaddress.ip_address(str(self.client_address[0]))
        except ValueError:
            return False
        return peer.is_loopback and _is_loopback_authority(self.headers.get("Host")) and self._origin_ok()

    SHELL_ASSETS = {
        "/": ("index.html", "text/html; charset=utf-8"),
        "/control-shell.css": ("control-shell.css", "text/css; charset=utf-8"),
        "/control-shell.js": ("control-shell.js", "text/javascript; charset=utf-8"),
    }

    def _serve_shell(self, path: str) -> None:
        """Serve the thin shell from the same loopback origin as the write API.

        One origin means one place to reason about: the page that can post an operation is delivered by
        the process that executes it, so there is no cross-origin grant to widen and no second server to
        keep honest. CSP is emitted on the response as well as in the document, and no inline script or
        style is allowed by either.
        """
        asset = self.SHELL_ASSETS[path]
        source = self.plane.project_root / "apps" / "control-surface" / asset[0]
        if not source.is_file():
            self._refused(404, "SHELL_ASSET_MISSING", f"薄壳文件缺失：{asset[0]}")
            return
        body = source.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", asset[1])
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Security-Policy",
                         "default-src 'none'; script-src 'self'; style-src 'self'; connect-src 'self'; form-action 'none'")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - http.server contract
        if not self._loopback_ok():
            self._refused(403, "NOT_LOOPBACK", "控制服务只监听回环地址，只接受回环来源。")
            return
        # The route is the path WITHOUT its query: the shell carries `?operation=<task_id>` so a reload can
        # re-query one identity, and `/` with a query is still `/`. Matching the raw `self.path` here would
        # make the page that just learned to survive a refresh unreachable the moment it used that ability.
        route = urlsplit(self.path).path
        if route in self.SHELL_ASSETS:
            self._serve_shell(route)
        elif route == "/api/control/descriptor":
            self._send(200, self.plane.descriptor())
        elif route.startswith("/api/control/operations/"):
            # ONE identity per request, addressed by the id the caller already has. There is deliberately
            # no list-all route: "which operations exist" is a question the Observer's read-only snapshot
            # already answers, and repeating it here would widen what a loopback read can enumerate for no
            # step of the lost-refresh path.
            identity = unquote(route[len("/api/control/operations/"):])
            if not identity or "/" in identity or "\\" in identity or len(identity) > 80:
                self._refused(404, "UNKNOWN_READ", "身份读端点只接受 /api/control/operations/<task_id>。")
                return
            self._send(200, self.plane.operation_identity(identity))
        elif route == "/health":
            self._send(200, {"schema_version": SCHEMA_VERSION, "status": "SERVING", "observed_at": _now()})
        else:
            self._refused(404, "UNKNOWN_READ",
                          "控制服务只暴露 descriptor、health 与单个身份的 operations/<task_id> 三个读端点。")

    def do_POST(self) -> None:  # noqa: N802 - http.server contract
        if not self._loopback_ok():
            self._refused(403, "NOT_LOOPBACK", "控制服务只监听回环地址，只接受回环来源。")
            return
        if self.path != "/api/control/operations":
            self._refused(404, "UNKNOWN_WRITE", "写入口只有一个：POST /api/control/operations。")
            return
        try:
            length = int(self.headers.get("Content-Length") or "0")
        except ValueError:
            length = 0
        if length <= 0:
            self._refused(400, "EMPTY_BODY", "没有请求体，无法构成一个操作。")
            return
        if length > MAX_BODY_BYTES:
            self._refused(413, "BODY_TOO_LARGE", f"操作请求超过 {MAX_BODY_BYTES} 字节上限。")
            return
        raw = self._read_request_body()
        try:
            request = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as error:
            self._refused(400, "UNPARSEABLE_REQUEST", f"请求不是合法 JSON：{type(error).__name__}")
            return
        if not isinstance(request, dict):
            self._refused(400, "REQUEST_NOT_OBJECT", "操作请求必须是一个对象。")
            return
        # A refused decision is still a 200 answer: the contract carries the verdict, HTTP 200 does not
        # mean the work happened, and the shell reads status/reason_code/reason from the typed result.
        self._send(200, self.plane.execute(request))

    def do_PUT(self) -> None: self._method_not_allowed()      # noqa: N802
    def do_PATCH(self) -> None: self._method_not_allowed()    # noqa: N802
    def do_DELETE(self) -> None: self._method_not_allowed()   # noqa: N802

    def _method_not_allowed(self) -> None:
        self._refused(405, "METHOD_NOT_ALLOWED", "控制服务只接受 POST 一个写方法与 GET 两个读方法。")


class ControlServer(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False

    def __init__(self, plane: ControlPlane, host: str = "127.0.0.1", port: int = 0) -> None:
        if host not in ("127.0.0.1", "localhost", "::1"):
            raise ValueError(f"the control service binds loopback only, refused: {host}")
        super().__init__((host, port), _Handler)
        # `localhost` is a name this machine's HOSTS file can point anywhere. Checking the address the
        # socket actually got is the only version of "loopback only" that is not a claim about a name.
        bound = str(self.server_address[0])
        try:
            address = ipaddress.ip_address(bound)
        except ValueError:
            self.server_close()
            raise ValueError(f"the control service cannot confirm its bound address: {bound!r}")
        if not address.is_loopback:
            self.server_close()
            raise ValueError(f"the control service binds loopback only, {host!r} resolved to {bound!r}")
        self.plane = plane
        self.host, self.bound_port = host, self.server_address[1]

    def endpoint_descriptor(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "host": self.host,
            "port": self.bound_port,
            "pid": os.getpid(),
            "started_at": _now(),
            "transport": "loopback-only",
            "endpoints": ["/api/control/descriptor", "/api/control/operations", "/health"],
            "evidence_ceiling": self.plane.evidence_ceiling,
        }

    def write_descriptor(self, path: Path) -> dict[str, Any]:
        """Publish where this process actually listens, so a shell discovers it instead of guessing a port."""
        descriptor = self.endpoint_descriptor()
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(descriptor, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
        return descriptor

    def serve_loop(self, descriptor_path: Path | None = None) -> None:
        if descriptor_path is not None:
            self.write_descriptor(descriptor_path)
        try:
            self.serve_forever()
        finally:
            if descriptor_path is not None and descriptor_path.is_file():
                descriptor_path.unlink()


def verified_evidence_ceiling(runtime_root: Path | None) -> tuple[str, str]:
    """INTEGRATED only when a live sidecar proves the read side uses this same runtime root.

    A CLI flag naming a directory is not evidence of anything: passing `--runtime-root` used to promote the
    receipt ceiling on its own, so a receipt could claim INTEGRATED for a store nobody reads. The descriptor
    is the observable -- it is written by a running sidecar into that root, and validating it checks the pid
    is still alive, the host is loopback, and the start time is neither forged nor stale.
    """
    if runtime_root is None:
        return "SYNTHETIC", "本轮新建的 fixture 运行根，读侧不在这里。"
    root = Path(runtime_root)
    descriptor = read_descriptor(root / SIDECAR_DESCRIPTOR_PATH)
    if descriptor is None:
        return "SYNTHETIC", f"{root} 下没有可读的 sidecar 端点描述文件，无法证明读侧正在使用这个运行根。"
    validation = validate_descriptor(descriptor)
    if not validation.valid:
        return "SYNTHETIC", "描述文件未通过校验：" + "; ".join(validation.errors)
    return "INTEGRATED", f"{root} 由存活 sidecar（pid {descriptor.get('pid')}）的端点描述确认。"


def build_plane(runtime_root: Path, project_root: Path, *, evidence_ceiling: str = "SYNTHETIC") -> ControlPlane:
    """Open the ONE canonical store the Observer also reads, then hand the control plane to it.

    The root is validated BEFORE the store is opened: refusing after `CanonicalStore` exists leaves an
    open sqlite handle, and on Windows that makes the whole fixture directory undeletable
    (`PermissionError [WinError 32]`), which then contaminates whichever test the batch runs next.
    """
    project_root = Path(project_root)
    if not path_is_anchored(str(project_root)):
        raise ValueError(
            f"project_root {project_root} is not anchored: a root that depends on the current working "
            "directory would make every boundary decision machine-relative")
    store = CanonicalStore(Path(runtime_root).resolve() / "canonical.sqlite")
    return ControlPlane(store, project_root=project_root, evidence_ceiling=evidence_ceiling,
                        receipts_path=Path(runtime_root) / RECEIPTS_PATH,
                        grants_path=Path(runtime_root) / TRUSTED_GRANTS_PATH)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", type=Path, default=_ROOT)
    parser.add_argument("--runtime-root", type=Path,
                        help="the same runtime root the sidecar uses; omit for a fresh in-boundary fixture")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=0)
    args = parser.parse_args()
    runtime_root = args.runtime_root or fixture_dir(prefix="control-service-")
    ceiling, ceiling_reason = verified_evidence_ceiling(args.runtime_root)
    plane = build_plane(runtime_root, args.project_root, evidence_ceiling=ceiling)
    server = ControlServer(plane, host=args.host, port=args.port)
    # flush=True is not decoration: a launcher that reads this pipe waits on the port line, and a
    # buffered stdout would make a correctly-starting service look hung (the sidecar flushes for the
    # same reason).
    print(f"CONTROL_SERVING url=http://{server.host}:{server.bound_port} runtime_root={runtime_root}",
          flush=True)
    try:
        server.serve_loop(Path(runtime_root) / DESCRIPTOR_PATH)
    except KeyboardInterrupt:
        pass
    finally:
        plane.store.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
