# SPDX-License-Identifier: MIT
"""Professional acceptance: the submitter's claim and a named human's verdict are
different objects (audit F08).

The old rule was ``if verdict == PASS and verifier_ref is non-empty``. That let
``verifier_ref = "agent:codex-synthetic"`` close a task, so the envelope claimed a
human acceptance it had never obtained. Two things were wrong at once: any string
passed as a person, and a row that then pretended the identity was checked.

This module keeps both honest for a single-user local machine without inventing
an account system:

* a **submission claim** is whatever the caller says they did. It is stored, it
  is attributable, and it can never satisfy professional acceptance;
* a **named human verdict** resolves against a local approval ledger whose rows
  are minted by a human typing at a terminal (``scripts/human_approval.py``).
  The ledger row binds the exact result id and content digest, so a stale or
  borrowed approval does not resolve;
* even then the row says ``identity_state = ATTESTED_AT_LOCAL_GATE`` — the gate
  records that a person signed this file on this machine, it does not proof who
  they are. A ``human:`` prefix is never treated as verification.

Synthetic fixtures are supported on purpose (the contract must be testable), but
they are written with ``data_origin = test`` and are therefore unable to produce
a live professional PASS anywhere downstream.
"""
from __future__ import annotations

import json
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

APPROVAL_SCHEMA_VERSION = "ai-work-lab/human-approval/v1"
#: Who the ledger believes signed a row, and what it explicitly does not believe.
IDENTITY_STATE = "ATTESTED_AT_LOCAL_GATE"
IDENTITY_LIMITS = (
    "identity is self-attested at a local terminal gate; no credential, no directory, "
    "no biometric and no remote identity proof was consulted",
    "the gate proves a keystroke happened on this machine, not who was sitting at it",
)

#: References that name a machine role. These are refused as human verdicts even
#: when they look like a name, because the audit's counterexample was exactly an
#: agent reference wearing a verifier_ref field.
NON_HUMAN_ROLES = ("agent", "model", "service", "bot", "ai", "system", "assistant",
                   "pipeline", "script", "daemon", "qoder", "codex", "claude", "gpt")

#: A person's name: letters/digits of any script, spaces, and the few marks a
#: name legitimately carries. Shape only — see IDENTITY_LIMITS for what this does
#: not prove.
_NAME_RE = re.compile(r"^[\w .'\-一-鿿]{2,80}$", re.UNICODE)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ApprovalError(ValueError):
    """A professional-acceptance request this contract refuses."""


def validate_human_ref(ref) -> str:
    """Shape check only. A shape is not an identity — see IDENTITY_LIMITS."""
    if not isinstance(ref, str) or not ref.strip():
        raise ApprovalError("VERIFIER_REF_REQUIRED a named human verdict needs a verifier reference")
    text = ref.strip()
    scheme = text.split(":", 1)[0].lower()
    if scheme in NON_HUMAN_ROLES:
        raise ApprovalError("VERIFIER_REF_NOT_HUMAN " + repr(scheme)
                            + " is a machine role; an agent, model or service reference can never "
                            "stand in for professional acceptance by a named person")
    if scheme != "human":
        raise ApprovalError("VERIFIER_REF_SCHEME_UNKNOWN expected 'human:<name>', found "
                            + repr(text[:40]))
    name = text.split(":", 1)[1].strip()
    if not name or name.lower() in NON_HUMAN_ROLES:
        raise ApprovalError("VERIFIER_REF_NEEDS_NAME a role word is not a person")
    if not _NAME_RE.match(name):
        raise ApprovalError("VERIFIER_REF_NAME_MALFORMED " + repr(name[:40])
                            + " is not a name this gate records (2-80 letters/digits, spaces, "
                            "apostrophe, dot or hyphen)")
    return text


class ApprovalLedger:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def rows(self) -> list[dict]:
        if not self.path.is_file():
            return []
        try:
            document = json.loads(self.path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            return []
        rows = document.get("approvals") if isinstance(document, dict) else None
        return rows if isinstance(rows, list) else []

    def _save(self, rows: list[dict]) -> None:
        payload = json.dumps({"schemaVersion": APPROVAL_SCHEMA_VERSION,
                              "identity_state": IDENTITY_STATE,
                              "identity_limits": list(IDENTITY_LIMITS),
                              "approvals": rows}, ensure_ascii=False, indent=2)
        temporary = self.path.with_suffix(self.path.suffix + ".tmp")
        temporary.write_text(payload, encoding="utf-8")
        os.replace(temporary, self.path)

    def record(self, *, result_id: str, subject_fingerprint: str, verifier_ref: str,
               statement: str, data_origin: str = "live", scope: str = "professional") -> dict:
        verifier_ref = validate_human_ref(verifier_ref)
        if data_origin not in ("live", "test", "demo"):
            raise ApprovalError("DATA_ORIGIN_UNKNOWN " + repr(data_origin))
        if not str(statement or "").strip():
            raise ApprovalError("APPROVAL_STATEMENT_REQUIRED the person has to state what they accepted")
        if not re.fullmatch(r"[0-9a-f]{64}", str(subject_fingerprint or "")):
            raise ApprovalError("APPROVAL_FINGERPRINT_MALFORMED a 64 hex digest of the accepted "
                                "content is required; an empty or invented fingerprint binds nothing")
        row = {
            "approval_id": "happr-" + uuid.uuid4().hex,
            "schemaVersion": APPROVAL_SCHEMA_VERSION,
            "result_id": str(result_id),
            "subject_fingerprint": str(subject_fingerprint),
            "verifier_ref": verifier_ref,
            "statement": str(statement).strip(),
            "scope": scope,
            "identity_state": IDENTITY_STATE,
            "data_origin": data_origin,
            "authorized_at": _now().isoformat(timespec="seconds"),
            "minted_by": "scripts/human_approval.py" if data_origin == "live"
                         else "synthetic fixture",
        }
        rows = self.rows()
        rows.append(row)
        self._save(rows)
        return row

    def resolve(self, approval_id: str, *, result_id: str, subject_fingerprint: str) -> dict:
        """The approval row that answers for exactly this result and these bytes."""
        for row in self.rows():
            if row.get("approval_id") != str(approval_id):
                continue
            if row.get("result_id") != str(result_id):
                raise ApprovalError("APPROVAL_WRONG_RESULT the approval was given for result "
                                    + repr(row.get("result_id")) + ", not " + repr(result_id))
            if row.get("subject_fingerprint") != str(subject_fingerprint):
                raise ApprovalError("APPROVAL_BYTES_MOVED the approved digest does not match the "
                                    "content being accepted; the approval does not cover these bytes")
            return row
        raise ApprovalError("APPROVAL_NOT_FOUND no approval " + repr(str(approval_id))
                            + " is recorded in the local human-approval ledger")


def mint_interactively(ledger: ApprovalLedger, *, result_id: str, subject_fingerprint: str,
                       prompt_reader=None, require_tty: bool = True) -> dict:
    """Mint one approval from a person at a terminal.

    This is the only live-origin path. An HTTP client cannot reach it: the request
    surface only *resolves* an approval id, so a caller that never had a human
    type cannot produce one. ``--allow-non-interactive`` exists for tests and
    stamps the row ``data_origin=test`` — a fixture approval is a test record.
    """
    if require_tty:
        if not sys.stdin.isatty():
            raise ApprovalError(
                "HUMAN_GATE_REQUIRES_TTY professional acceptance is minted by a person at a "
                "terminal; a piped or automated stdin is refused. Use --allow-non-interactive "
                "only for a synthetic fixture, which is recorded as data_origin=test")
        reader = _read_line_from_tty
    else:
        reader = prompt_reader or _read_line_from_tty
    verifier = reader("你的姓名（用于 human:<姓名>）：").strip()
    # Accept either a bare name or an already-prefixed reference; inventing a
    # second "human:" in front of one the caller typed would produce a name that
    # is a scheme, and the shape check below would (correctly) refuse it.
    reference = verifier if verifier.lower().startswith("human:") else "human:" + verifier
    statement = reader("你验收了什么（一句话，会原文存档）：")
    return ledger.record(result_id=result_id, subject_fingerprint=subject_fingerprint,
                         verifier_ref=reference, statement=statement.strip(),
                         data_origin="live" if require_tty else "test")


def _read_line_from_tty(prompt: str) -> str:
    text = input(prompt)
    if not text.strip():
        raise ApprovalError("HUMAN_GATE_INPUT_REQUIRED " + repr(prompt))
    return text
