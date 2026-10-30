# SPDX-License-Identifier: MIT
"""Service façade for the knowledge-feedback candidates of one project.

`assurance/knowledge_feedback.py` owns the contract: a candidate is always stored
`PENDING_HUMAN_APPROVAL`, only a named human can approve or reject it, and a
revocation record blocks export. This module is the layer a route can call. It
persists the document in the state database, keeps the review history
append-only, and reports what the store actually supports -- including the
things this product does NOT do:

* there is no ArcheAxis transport in this repository. ``outbound`` says
  ``NOT_CONNECTED`` and ``sent_count`` is 0 because nothing was sent, not because
  a send failed. ``export_ready`` is a local contract check, never a delivery;
* freshness compares the candidate's recorded DESIGN-LAB revision with the
  checkout's current HEAD. ``UNKNOWN`` (no git subject) is not ``CURRENT``;
* an approval is a claimed identity and timestamp. This service cannot verify
  that the named person exists or reviewed the content; that needs the
  out-of-band Human Gate attestation.

Conflicts are reported, not repaired: a supersede link to a missing candidate, a
forked supersede chain, a payload whose digest no longer matches, or a revoked
document with no receipt each appear in ``conflicts`` while the read itself still
answers 200.
"""
from __future__ import annotations

from collections import Counter
from contextlib import closing
import json
import os
import re
import sqlite3
import subprocess

from .assurance import AssuranceError, RFC3339_PATTERN, utc_now_rfc3339
from .assurance import knowledge_feedback
from .runtime.attempt_contract import request_hash
from .runtime.paths import PROJECT_ROOT
from .runtime.state_resources import state_schema

READBACK_VERSION = "design-lab/assurance-knowledge-candidate-readback/v1"
EXPORT_VERSION = "design-lab/assurance-knowledge-candidate-export-envelope/v1"

#: The route pattern's own vocabulary: a candidate id that cannot be addressed
#: by a later review/revoke URL is refused at creation rather than stored.
CANDIDATE_ADDRESS = re.compile(r"[A-Za-z0-9_.:-]{1,80}")
HEAD_SHA = re.compile(r"[0-9a-f]{40,64}")

_SCHEMA = state_schema("design-lab-state-knowledge-v1.sql")

DOES_NOT_SAY = (
    "传输未实现：本服务不连接 ArcheAxis，也不会自动重试；export_ready 只表示本地合同允许"
    "导出，不代表已经发送或对方已经接收。",
    "freshness 只比较候选记录的 design_lab_sha 与当前 checkout 的 HEAD；STALE 不等于知识"
    "过时，UNKNOWN 也不等于已经同步。",
    "review 绑定的是操作者提供的身份与时间戳；服务无法证明这个人真实存在，也无法证明"
    "他真的审阅了内容。",
    "撤销记录保存在本机；如果一次导出此前已经发生过，本地撤销不能召回对方已持有的副本。",
    "候选正文只写在本项目的状态库里；payload 在写入前会拒绝客户端素材、绝对路径、"
    "邮箱与转写文本。",
)


class KnowledgeReviewError(ValueError):
    def __init__(self, status, code, detail=None):
        self.status, self.code, self.detail = status, code, detail


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the state database with the knowledge tables present.

    Reuses `asset_store.connect` for its path policy, foreign-key pragma and its
    assets-v2 migration rather than applying schema files a second way here.
    """
    from .runtime.asset_store import connect as connect_assets

    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    connection.executescript(_SCHEMA.read_text(encoding="utf-8"))
    connection.commit()
    return connection


def _canonical(document) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def _now() -> str:
    return utc_now_rfc3339()


def _latest(conn, project_id, candidate_id):
    return conn.execute(
        "SELECT * FROM knowledge_candidate WHERE project_id = ? AND candidate_id = ?"
        " ORDER BY revision DESC LIMIT 1", (project_id, candidate_id)).fetchone()


def _latest_rows(conn, project_id):
    return conn.execute(
        "SELECT k.* FROM knowledge_candidate k WHERE k.project_id = ? AND k.revision = ("
        " SELECT MAX(m.revision) FROM knowledge_candidate m"
        " WHERE m.project_id = k.project_id AND m.candidate_id = k.candidate_id)"
        " ORDER BY k.recorded_at, k.candidate_id", (project_id,)).fetchall()


def _append(conn, project_id, document, recorded_at) -> None:
    """Append the next revision; the caller commits, so related writes are atomic."""
    previous = conn.execute(
        "SELECT MAX(revision) AS revision FROM knowledge_candidate"
        " WHERE project_id = ? AND candidate_id = ?",
        (project_id, document["candidate_id"])).fetchone()
    revision = (previous["revision"] or 0) + 1
    conn.execute(
        "INSERT INTO knowledge_candidate (project_id, candidate_id, revision,"
        " candidate_type, review_state, revocation_state, document_json, recorded_at)"
        " VALUES (?,?,?,?,?,?,?,?)",
        (project_id, document["candidate_id"], revision, document["candidate_type"],
         document["review"]["state"], document["revocation"]["state"],
         _canonical(document), recorded_at))


def _creation_key(document) -> str:
    """Everything the original submission pinned, minus the server-defaulted time."""
    return _canonical({key: value for key, value in document.items() if key != "created_at"})


def _document_or_corrupt(row) -> dict:
    try:
        document = json.loads(row["document_json"])
    except (TypeError, ValueError):
        document = None
    if not isinstance(document, dict):
        raise KnowledgeReviewError(
            500, "KNOWLEDGE_STORE_CORRUPT",
            f"stored candidate {row['candidate_id']!r} revision {row['revision']} "
            "is not a readable document")
    return document


def _head_sha() -> str | None:
    """The checkout's current revision, or None when this is not a git checkout.

    Bounded and read-only; a missing git (installed wheel, exported tree) is an
    honest UNKNOWN freshness, never a borrowed or invented revision.
    """
    try:
        result = subprocess.run(
            ["git", "-C", str(PROJECT_ROOT), "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            env={**os.environ, "GIT_OPTIONAL_LOCKS": "0"})
    except (OSError, subprocess.SubprocessError):
        return None
    value = result.stdout.strip() if result.returncode == 0 else ""
    return value if HEAD_SHA.fullmatch(value) else None


def _freshness(candidate_sha, head) -> str:
    if head is None or not isinstance(candidate_sha, str):
        return "UNKNOWN"
    return "CURRENT" if head.startswith(candidate_sha) else "STALE"


def _export_check(document) -> tuple:
    try:
        knowledge_feedback.export_payload(document)
    except AssuranceError as exc:
        return False, str(exc)
    return True, None


def _projection(row, document, head) -> dict:
    payload = document.get("payload") if isinstance(document.get("payload"), dict) else {}
    source = document.get("source") if isinstance(document.get("source"), dict) else {}
    rights = document.get("rights") if isinstance(document.get("rights"), dict) else {}
    review = document.get("review") if isinstance(document.get("review"), dict) else {}
    revocation = (document.get("revocation")
                  if isinstance(document.get("revocation"), dict) else {})
    applies_to = payload.get("applies_to")
    ready, blocked = _export_check(document)
    return {
        "candidate_id": row["candidate_id"],
        "candidate_type": document.get("candidate_type", row["candidate_type"]),
        "review_state": review.get("state") or row["review_state"],
        "revocation_state": revocation.get("state") or row["revocation_state"],
        "revision": row["revision"],
        "created_at": document.get("created_at"),
        "updated_at": row["recorded_at"],
        "source_design_lab_sha": source.get("design_lab_sha"),
        "payload_sha256": document.get("payload_sha256"),
        "supersedes": document.get("supersedes"),
        "title": payload.get("title"),
        "statement": payload.get("statement"),
        "applies_to": [item for item in applies_to if isinstance(item, str)]
        if isinstance(applies_to, list) else [],
        "license_id": rights.get("license_id"),
        "rights_gate_state": rights.get("rights_gate_state"),
        "reviewer_id": review.get("reviewer_id"),
        "reviewed_at": review.get("reviewed_at"),
        "revoked_by": revocation.get("revoked_by"),
        "revoked_at": revocation.get("revoked_at"),
        "revocation_reason": revocation.get("reason"),
        "freshness": _freshness(source.get("design_lab_sha"), head),
        "export_ready": ready,
        "export_blocked_by": blocked,
    }


def _conflicts(rows, documents, receipts) -> list:
    """Every disagreement between the stored rows and the contract, named."""
    by_id = {row["candidate_id"]: documents.get(row["candidate_id"]) for row in rows}
    superseders = Counter(
        document["supersedes"] for document in by_id.values()
        if isinstance(document, dict) and isinstance(document.get("supersedes"), str))
    found = []
    for row in rows:
        candidate_id = row["candidate_id"]
        document = by_id[candidate_id]
        if CANDIDATE_ADDRESS.fullmatch(candidate_id) is None:
            found.append({"candidate_id": candidate_id, "kind": "ADDRESS_INVALID",
                          "detail": "the stored id cannot be addressed by the review or "
                                    "revoke route"})
        if document is None:
            found.append({"candidate_id": candidate_id, "kind": "DOCUMENT_UNREADABLE",
                          "detail": "the stored document is not readable JSON"})
            continue
        try:
            knowledge_feedback.validate_candidate(document)
        except AssuranceError as exc:
            found.append({"candidate_id": candidate_id, "kind": "DOCUMENT_INVALID",
                          "detail": str(exc)})
        if document.get("candidate_id") != candidate_id:
            found.append({"candidate_id": candidate_id, "kind": "DOCUMENT_MISMATCH",
                          "detail": f"the document names {document.get('candidate_id')!r}"})
        payload = document.get("payload")
        try:
            recomputed = request_hash(dict(payload)) if isinstance(payload, dict) else None
        except (TypeError, ValueError):
            recomputed = None
        if recomputed is not None and recomputed != document.get("payload_sha256"):
            found.append({"candidate_id": candidate_id, "kind": "PAYLOAD_DIGEST_MISMATCH",
                          "detail": "payload_sha256 does not match the stored payload"})
        target = document.get("supersedes")
        if isinstance(target, str):
            if target not in by_id:
                found.append({"candidate_id": candidate_id, "kind": "SUPERSEDES_UNKNOWN",
                              "detail": f"supersedes {target!r}, which is not a candidate "
                                        "of this project"})
            elif superseders[target] > 1:
                found.append({"candidate_id": candidate_id, "kind": "SUPERSEDE_FORK",
                              "detail": f"{superseders[target]} candidates supersede "
                                        f"{target!r}; the replacement is undefined"})
        revocation = document.get("revocation")
        state = revocation.get("state") if isinstance(revocation, dict) else None
        if state == "REVOKED" and candidate_id not in receipts:
            found.append({"candidate_id": candidate_id,
                          "kind": "REVOCATION_RECEIPT_MISSING",
                          "detail": "the document is REVOKED but no receipt is stored"})
        if state != "REVOKED" and candidate_id in receipts:
            found.append({"candidate_id": candidate_id,
                          "kind": "REVOCATION_RECEIPT_UNAPPLIED",
                          "detail": "a receipt exists but the document is not marked REVOKED"})
    found.sort(key=lambda item: (item["candidate_id"], item["kind"]))
    return found


class KnowledgeReview:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return connect(self.paths.database_path(self.service.database),
                       project_root=self.paths.project_root)

    def _check_project(self, project_id):
        if self.service.get_project(project_id) is None:
            raise KnowledgeReviewError(404, "PROJECT_NOT_FOUND")

    def list(self, project_id) -> dict:
        self._check_project(project_id)
        head = _head_sha()
        with closing(self._connect()) as conn:
            rows = _latest_rows(conn, project_id)
            documents = {}
            for row in rows:
                try:
                    documents[row["candidate_id"]] = json.loads(row["document_json"])
                except (TypeError, ValueError):
                    documents[row["candidate_id"]] = None
            receipt_rows = conn.execute(
                "SELECT candidate_id, document_json FROM knowledge_revocation"
                " WHERE project_id = ? ORDER BY recorded_at, candidate_id",
                (project_id,)).fetchall()
        receipts = {}
        unreadable_receipts = 0
        for row in receipt_rows:
            try:
                record = json.loads(row["document_json"])
            except (TypeError, ValueError):
                record = None
            if isinstance(record, dict):
                receipts[row["candidate_id"]] = record
            else:
                unreadable_receipts += 1
        candidates = [_projection(row, documents[row["candidate_id"]], head)
                      for row in rows if documents[row["candidate_id"]] is not None]
        conflicts = _conflicts(rows, documents, receipts)
        if unreadable_receipts:
            conflicts.append({"candidate_id": "*", "kind": "REVOCATION_RECEIPT_UNREADABLE",
                              "detail": f"{unreadable_receipts} stored receipt(s) are not "
                                        "readable JSON"})
            conflicts.sort(key=lambda item: (item["candidate_id"], item["kind"]))
        # A count says what the store holds; an unreadable row is counted here and
        # named in conflicts rather than dropped from every sentence.
        unreadable = len(rows) - len(candidates)
        return {
            "schemaVersion": READBACK_VERSION,
            "project_id": project_id,
            "candidates": candidates,
            "candidate_count": len(candidates),
            "unreadable_count": unreadable,
            "pending_review_count": sum(
                1 for item in candidates
                if item["review_state"] == "PENDING_HUMAN_APPROVAL"),
            "approved_count": sum(
                1 for item in candidates if item["review_state"] == "APPROVED"),
            "rejected_count": sum(
                1 for item in candidates if item["review_state"] == "REJECTED"),
            "revoked_count": sum(
                1 for item in candidates if item["revocation_state"] == "REVOKED"),
            # Not a delivery count: the local contract would allow these bytes out,
            # and nothing in this repository can send them.
            "export_ready_count": sum(1 for item in candidates if item["export_ready"]),
            "conflicts": conflicts,
            "revocation_receipts": [receipts[key] for key in sorted(receipts)],
            "head_sha": head,
            "outbound": {
                "transport": "NOT_CONNECTED",
                "destination": "ArcheAxis",
                "sent_count": 0,
                "last_attempt_at": None,
                "note": "本服务没有 ArcheAxis 传输实现；sent_count 为 0 是因为从未发送，"
                        "不是一次失败的重试。",
            },
            "does_not_say": list(DOES_NOT_SAY),
        }

    def create(self, project_id, fields, *, supersedes=None) -> dict:
        self._check_project(project_id)
        candidate_id = fields.get("candidate_id")
        if (not isinstance(candidate_id, str)
                or CANDIDATE_ADDRESS.fullmatch(candidate_id) is None):
            raise KnowledgeReviewError(
                400, "CANDIDATE_ID_INVALID",
                "candidate_id must match [A-Za-z0-9_.:-]{1,80}; a later review or revoke "
                "route has to be able to address it")
        try:
            document = knowledge_feedback.build_candidate(
                candidate_id=candidate_id,
                candidate_type=fields.get("candidate_type"),
                source=fields.get("source"),
                rights=fields.get("rights"),
                payload=fields.get("payload"),
                supersedes=supersedes,
                created_at=fields.get("created_at") or None,
                revocation_entrypoint=(fields.get("revocation_entrypoint")
                                       or knowledge_feedback.DEFAULT_REVOCATION_ENTRYPOINT))
        except AssuranceError as exc:
            raise KnowledgeReviewError(400, "KNOWLEDGE_CANDIDATE_REFUSED",
                                       str(exc)) from None
        with closing(self._connect()) as conn:
            first = conn.execute(
                "SELECT document_json FROM knowledge_candidate WHERE project_id = ?"
                " AND candidate_id = ? AND revision = 1",
                (project_id, candidate_id)).fetchone()
            if first is not None:
                stored = _document_or_corrupt({**dict(first), "revision": 1,
                                               "candidate_id": candidate_id})
                if _creation_key(stored) == _creation_key(document):
                    latest = _latest(conn, project_id, candidate_id)
                    return _document_or_corrupt(latest)
                raise KnowledgeReviewError(
                    409, "CANDIDATE_ID_TAKEN",
                    f"candidate {candidate_id!r} already exists with different content; "
                    "a candidate id names one immutable submission")
            target = document.get("supersedes")
            if isinstance(target, str):
                if _latest(conn, project_id, target) is None:
                    raise KnowledgeReviewError(
                        409, "SUPERSEDES_UNKNOWN",
                        f"supersedes {target!r} is not a candidate of this project")
                superseders = []
                for row in _latest_rows(conn, project_id):
                    try:
                        other = json.loads(row["document_json"])
                    except (TypeError, ValueError):
                        continue
                    if (row["candidate_id"] != candidate_id
                            and isinstance(other, dict)
                            and other.get("supersedes") == target):
                        superseders.append(row["candidate_id"])
                if superseders:
                    raise KnowledgeReviewError(
                        409, "SUPERSEDE_FORK",
                        f"{target!r} is already superseded by "
                        f"{', '.join(sorted(superseders))}; a second replacement would "
                        "fork the chain and leave the current lesson undefined")
            try:
                _append(conn, project_id, document, recorded_at=_now())
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise KnowledgeReviewError(409, "KNOWLEDGE_CONCURRENT_UPDATE",
                                           str(exc)) from None
        return document

    def review(self, project_id, candidate_id, fields) -> dict:
        self._check_project(project_id)
        decision = fields.get("decision")
        if decision not in ("APPROVE", "REJECT"):
            raise KnowledgeReviewError(400, "INVALID_DECISION",
                                       "decision must be APPROVE or REJECT")
        reviewer_id = fields.get("reviewer_id")
        reviewer_kind = fields.get("reviewer_kind")
        reviewed_at = fields.get("reviewed_at")
        if reviewer_kind != knowledge_feedback.REVIEWER_KIND_HUMAN:
            raise KnowledgeReviewError(
                400, "KNOWLEDGE_HUMAN_REVIEW_REQUIRED",
                "an agent may not approve or reject an export: reviewer_kind must be "
                f"{knowledge_feedback.REVIEWER_KIND_HUMAN!r} with a named human reviewer "
                f"(got {reviewer_kind!r})")
        if not isinstance(reviewed_at, str) or RFC3339_PATTERN.match(reviewed_at) is None:
            raise KnowledgeReviewError(
                400, "INVALID_REVIEWED_AT",
                "reviewed_at must be an RFC3339 date-time with an explicit UTC offset")
        note = fields.get("note")
        if note is not None and not isinstance(note, str):
            raise KnowledgeReviewError(400, "INVALID_NOTE",
                                       "note must be a string or null")
        reason = fields.get("reason")
        if decision == "REJECT" and (not isinstance(reason, str) or not reason.strip()):
            raise KnowledgeReviewError(400, "REASON_REQUIRED",
                                       "a rejection must say why, in reason")
        with closing(self._connect()) as conn:
            row = _latest(conn, project_id, candidate_id)
            if row is None:
                raise KnowledgeReviewError(
                    404, "KNOWLEDGE_CANDIDATE_NOT_FOUND",
                    f"{candidate_id!r} is not a candidate of this project")
            document = _document_or_corrupt(row)
            review = document["review"]
            wanted = "APPROVED" if decision == "APPROVE" else "REJECTED"
            if (review["state"] == wanted
                    and review.get("reviewer_id") == reviewer_id
                    and review.get("reviewed_at") == reviewed_at):
                return document
            if review["state"] != "PENDING_HUMAN_APPROVAL":
                raise KnowledgeReviewError(
                    409, "KNOWLEDGE_CANDIDATE_DECIDED",
                    f"candidate {candidate_id!r} is already {review['state']} by "
                    f"{review.get('reviewer_id')!r}; a decision is not re-signed or upgraded")
            if document["revocation"]["state"] == "REVOKED":
                raise KnowledgeReviewError(
                    409, "KNOWLEDGE_CANDIDATE_REVOKED",
                    f"candidate {candidate_id!r} was revoked at "
                    f"{document['revocation'].get('revoked_at')!r}; an approval of bytes "
                    "that can never be exported would misreport the gate")
            try:
                if decision == "APPROVE":
                    updated = knowledge_feedback.approve(
                        document, reviewer_id=reviewer_id, reviewer_kind=reviewer_kind,
                        reviewed_at=reviewed_at, note=note)
                else:
                    updated = knowledge_feedback.reject(
                        document, reviewer_id=reviewer_id, reviewer_kind=reviewer_kind,
                        reviewed_at=reviewed_at, reason=reason)
            except AssuranceError as exc:
                code = ("KNOWLEDGE_RIGHTS_NOT_CHECKED" if "rights gate state" in str(exc)
                        else "KNOWLEDGE_REVIEW_REFUSED")
                raise KnowledgeReviewError(409, code, str(exc)) from None
            try:
                _append(conn, project_id, updated, recorded_at=_now())
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise KnowledgeReviewError(409, "KNOWLEDGE_CONCURRENT_UPDATE",
                                           str(exc)) from None
        return updated

    def revoke(self, project_id, candidate_id, fields) -> dict:
        self._check_project(project_id)
        reason = fields.get("reason")
        revoked_by = fields.get("revoked_by")
        revoked_at = fields.get("revoked_at") or None
        if not isinstance(reason, str) or not reason.strip():
            raise KnowledgeReviewError(400, "REASON_REQUIRED",
                                       "a revocation must say why, in reason")
        if not isinstance(revoked_by, str) or not revoked_by.strip():
            raise KnowledgeReviewError(400, "REVOKED_BY_REQUIRED",
                                       "a revocation must name who requested it")
        if (revoked_at is not None
                and (not isinstance(revoked_at, str)
                     or RFC3339_PATTERN.match(revoked_at) is None)):
            raise KnowledgeReviewError(
                400, "INVALID_REVOKED_AT",
                "revoked_at must be an RFC3339 date-time with an explicit UTC offset")
        with closing(self._connect()) as conn:
            row = _latest(conn, project_id, candidate_id)
            if row is None:
                raise KnowledgeReviewError(
                    404, "KNOWLEDGE_CANDIDATE_NOT_FOUND",
                    f"{candidate_id!r} is not a candidate of this project")
            document = _document_or_corrupt(row)
            receipt_row = conn.execute(
                "SELECT document_json FROM knowledge_revocation"
                " WHERE project_id = ? AND candidate_id = ?",
                (project_id, candidate_id)).fetchone()
            if document["revocation"]["state"] == "REVOKED":
                if receipt_row is not None:
                    try:
                        stored = json.loads(receipt_row["document_json"])
                    except (TypeError, ValueError):
                        stored = None
                    if (isinstance(stored, dict)
                            and stored.get("reason") == reason
                            and stored.get("revoked_by") == revoked_by):
                        return stored
                raise KnowledgeReviewError(
                    409, "KNOWLEDGE_ALREADY_REVOKED",
                    f"candidate {candidate_id!r} is already revoked; a different reason "
                    "or actor would rewrite the receipt")
            try:
                record = knowledge_feedback.revoke(
                    document, reason=reason, revoked_by=revoked_by,
                    revoked_at=revoked_at)
                updated = knowledge_feedback.apply_revocation(document, record)
            except AssuranceError as exc:
                raise KnowledgeReviewError(409, "KNOWLEDGE_REVOKE_REFUSED",
                                           str(exc)) from None
            recorded_at = _now()
            try:
                _append(conn, project_id, updated, recorded_at=recorded_at)
                conn.execute(
                    "INSERT INTO knowledge_revocation (project_id, candidate_id,"
                    " document_json, recorded_at) VALUES (?,?,?,?)",
                    (project_id, candidate_id, _canonical(record), recorded_at))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise KnowledgeReviewError(409, "KNOWLEDGE_CONCURRENT_UPDATE",
                                           str(exc)) from None
        return record

    def export_document(self, project_id, candidate_id) -> dict:
        """Produce both outbound projections of one stored candidate, or name the exact refusal.

        This is the caller ``export_payload`` and ``to_v1_projection`` never had: before it they were
        reachable only from their own self-label, so "exportable" existed as a boolean on the readback
        and no surface could ask for the document a transfer would carry. Producing it is still not a
        transfer -- ``outbound.transport`` stays ``NOT_CONNECTED`` and ``sent_count`` stays 0 because
        nothing is sent, and ``bytes`` counts what was assembled, not what left the machine.

        The refusal is the product answer and keeps its own reason: an unapproved candidate, an agent
        approval, an unchecked rights gate or a revoked document each say so rather than answering
        200 with an empty body. ``source.job_id`` / ``source.operation_id`` are echoed exactly as
        stored -- this method never fills a provenance field on anyone's behalf.
        """
        self._check_project(project_id)
        with closing(self._connect()) as conn:
            rows = [row for row in _latest_rows(conn, project_id)
                    if row["candidate_id"] == candidate_id]
        if not rows:
            raise KnowledgeReviewError(404, "CANDIDATE_NOT_FOUND")
        row = rows[0]
        try:
            document = json.loads(row["document_json"])
        except (TypeError, ValueError):
            raise KnowledgeReviewError(409, "CANDIDATE_DOCUMENT_UNREADABLE",
                                       f"stored revision {row['revision']} of {candidate_id} is not "
                                       "readable JSON; nothing is exported from an unreadable row"
                                       ) from None
        if not isinstance(document, dict):
            raise KnowledgeReviewError(409, "CANDIDATE_DOCUMENT_UNREADABLE",
                                       "the stored document is not an object")
        try:
            payload = knowledge_feedback.export_payload(document)
        except AssuranceError as exc:
            raise KnowledgeReviewError(409, "CANDIDATE_EXPORT_REFUSED", str(exc)) from None
        try:
            projection = knowledge_feedback.to_v1_projection(document)
        except AssuranceError as exc:
            raise KnowledgeReviewError(409, "CANDIDATE_V1_PROJECTION_REFUSED", str(exc)) from None
        canonical = _canonical(payload)
        source = document.get("source") if isinstance(document.get("source"), dict) else {}
        return {
            "schemaVersion": EXPORT_VERSION,
            "status": "CANDIDATE_EXPORT",
            "project_id": project_id,
            "candidate_id": candidate_id,
            "revision": row["revision"],
            "export": payload,
            "v1_projection": projection,
            "provenance": {"job_id": source.get("job_id"), "operation_id": source.get("operation_id"),
                            "job_id_state": knowledge_feedback.provenance_state(source.get("job_id")),
                            "operation_id_state": knowledge_feedback.provenance_state(
                                source.get("operation_id")),
                            "design_lab_sha": source.get("design_lab_sha"),
                            "payload_sha256": payload.get("payload_sha256")},
            "freshness": _freshness(source.get("design_lab_sha"), _head_sha()),
            "outbound": {"transport": "NOT_CONNECTED", "sent_count": 0,
                          "bytes": len(canonical.encode('utf-8'))},
            "does_not_say": list(DOES_NOT_SAY),
        }
