# SPDX-License-Identifier: MIT
"""DLDS-F040 — Approval, projected from the decision ledger.

An approval is not a second kind of decision: it *is* a decision taken at a named
gate by a human. So the authoring source stays ``decision_event`` and this module
does two things:

* answers approval questions over that ledger (``approval_status``,
  ``pending_approvals``, ``require_approval``);
* maintains the pre-existing ``approval`` table of ``design-lab-state-v1.sql`` as
  a **projection** of it, so that table stops being an unused skeleton without
  becoming a second truth.

The human rule is not re-implemented here: ``decision_ledger`` refuses to let an
agent decide or reverse a gate, and this module cannot bypass that. An agent can
propose an approval and can read one; it can never grant one.
"""
from __future__ import annotations

from .decision_ledger import HUMAN_ONLY, GATES, decision, decisions, propose, decide, reverse
from .store import CreativeError, now, require_job, transaction

# Approval states, and how they project into the v1 approval table's state column.
# NOT_REVIEWED and PENDING are different facts and may not share a word: PENDING says
# somebody has been asked and owes an answer, NOT_REVIEWED says no request was ever
# filed. Collapsing them made an untouched rights gate read as "in review", which is
# how a gate nobody opened ends up looking like a gate somebody is about to close.
STATES = ("NOT_REVIEWED", "PENDING", "APPROVED", "REJECTED", "REVERSED")
APPROVAL_OPTIONS = (
    {"option_id": "APPROVE", "summary": "grant the approval", "tradeoffs": ""},
    {"option_id": "REJECT", "summary": "refuse the approval", "tradeoffs": ""},
)
_STATE_BY_CHOICE = {"APPROVE": "APPROVED", "REJECT": "REJECTED"}


def _gate(gate: str) -> str:
    if gate not in HUMAN_ONLY:
        raise CreativeError(f"not a human gate: {gate!r}; expected one of {list(HUMAN_ONLY)}")
    return gate


def approval_id(job_id: str, gate: str) -> str:
    """Deterministic identity, so a re-projection cannot create a second row."""
    return f"approval:{job_id}:{gate}"


def _projection_state(record) -> str:
    if record is None:
        # Nothing was ever filed for this gate. This is not "awaiting a human".
        return "NOT_REVIEWED"
    if record["state"] == "DECIDED":
        # A DECIDED row whose choice is not one of the two options the gate offers is a
        # data bug, and the gate stays ungranted rather than inventing a state for it.
        return _STATE_BY_CHOICE.get(record.get("chosen") or "", "PENDING")
    if record["state"] == "REVERSED":
        return "REVERSED"
    if record["state"] == "PROPOSED":
        return "PENDING"
    # SUPERSEDED: this request was replaced by another one, so no answer is outstanding
    # on it -- and it certainly has not been granted.
    return "NOT_REVIEWED"


def request_approval(conn, *, job_id: str, gate: str, actor: str, actor_kind: str = "agent",
                     rationale: str | None = None) -> dict:
    """Open an approval request at a gate. Anyone may ask; only a human may grant."""
    gate = _gate(gate)
    require_job(conn, job_id)
    dec_id = f"DEC-{gate.lower()}-{job_id}"
    propose(conn, job_id=job_id, dec_id=dec_id, options=APPROVAL_OPTIONS, actor=actor,
            actor_kind=actor_kind, gate=gate, rationale=rationale)
    sync_projection(conn, job_id=job_id, gate=gate)
    return approval_status(conn, job_id=job_id, gate=gate)


def grant(conn, *, job_id: str, gate: str, actor: str, rationale: str,
          actor_kind: str = "human") -> dict:
    """Grant an approval. A non-human actor is refused by the decision ledger."""
    gate = _gate(gate)
    dec_id = f"DEC-{gate.lower()}-{job_id}"
    try:
        decide(conn, dec_id=dec_id, chosen="APPROVE", rationale=rationale, actor=actor,
               actor_kind=actor_kind)
    except CreativeError as exc:
        if "PROPOSED" in str(exc) or "unknown decision" in str(exc):
            raise CreativeError(f"{gate} approval was never requested for {job_id!r}") from exc
        raise
    sync_projection(conn, job_id=job_id, gate=gate)
    return approval_status(conn, job_id=job_id, gate=gate)


def refuse(conn, *, job_id: str, gate: str, actor: str, rationale: str,
           actor_kind: str = "human") -> dict:
    gate = _gate(gate)
    dec_id = f"DEC-{gate.lower()}-{job_id}"
    decide(conn, dec_id=dec_id, chosen="REJECT", rationale=rationale, actor=actor,
           actor_kind=actor_kind)
    sync_projection(conn, job_id=job_id, gate=gate)
    return approval_status(conn, job_id=job_id, gate=gate)


def revoke(conn, *, job_id: str, gate: str, actor: str, rationale: str,
           actor_kind: str = "human") -> dict:
    """Withdraw a granted approval. The history keeps the original grant visible."""
    gate = _gate(gate)
    dec_id = f"DEC-{gate.lower()}-{job_id}"
    reverse(conn, dec_id=dec_id, rationale=rationale, actor=actor, actor_kind=actor_kind)
    sync_projection(conn, job_id=job_id, gate=gate)
    return approval_status(conn, job_id=job_id, gate=gate)


def approval_status(conn, *, job_id: str, gate: str) -> dict:
    gate = _gate(gate)
    require_job(conn, job_id)
    dec_id = f"DEC-{gate.lower()}-{job_id}"
    try:
        record = decision(conn, dec_id)
    except CreativeError:
        record = None
    state = _projection_state(record)
    return {
        "job_id": job_id,
        "gate": gate,
        "approval_id": approval_id(job_id, gate),
        "state": state,
        "granted": state == "APPROVED",
        "decision_id": dec_id if record else None,
        "actor": record["actor"] if record else None,
        "actor_kind": record["actor_kind"] if record else None,
        "chosen": record.get("chosen") if record else None,
        "human_required": True,
        "source": "decision_event (approvals are gate decisions, not a second ledger)",
    }


def pending_approvals(conn, job_id: str) -> list:
    require_job(conn, job_id)
    return [gate for gate in HUMAN_ONLY
            if approval_status(conn, job_id=job_id, gate=gate)["state"] != "APPROVED"]


def require_approval(conn, *, job_id: str, gate: str) -> dict:
    """Fail closed unless the gate holds a granted, unrevoked human approval."""
    status = approval_status(conn, job_id=job_id, gate=gate)
    if not status["granted"]:
        raise CreativeError(f"{gate} approval is {status['state']} for {job_id!r}; "
                            f"a human must grant it before this step")
    return status


def sync_projection(conn, *, job_id: str, gate: str) -> dict:
    """Maintain the v1 approval table as a projection. It is never a source."""
    gate = _gate(gate)
    status = approval_status(conn, job_id=job_id, gate=gate)
    with transaction(conn):
        conn.execute("INSERT INTO approval (approval_id, action_kind, actor, state) VALUES (?,?,?,?) "
                     "ON CONFLICT(approval_id) DO UPDATE SET actor=excluded.actor, "
                     "state=excluded.state",
                     (status["approval_id"], f"gate:{gate}", status["actor"] or "unassigned",
                      status["state"]))
    return status


def projection(conn, job_id: str) -> list:
    """Every gate of a job, as the projection table currently records it."""
    require_job(conn, job_id)
    rows = conn.execute("SELECT approval_id, action_kind, actor, state FROM approval "
                        "WHERE approval_id LIKE ? ORDER BY action_kind",
                        (f"approval:{job_id}:%",)).fetchall()
    return [{"approval_id": row[0], "action_kind": row[1], "actor": row[2], "state": row[3],
             "source": "projection of decision_event"} for row in rows]


def gate_inventory(conn, job_id: str) -> dict:
    """All gates with their projected state, for a delivery or release check."""
    require_job(conn, job_id)
    statuses = {gate: approval_status(conn, job_id=job_id, gate=gate)["state"] for gate in HUMAN_ONLY}
    return {"job_id": job_id, "gates": statuses,
            "open_gates": [gate for gate in HUMAN_ONLY if statuses[gate] != "APPROVED"],
            "granted": [gate for gate in HUMAN_ONLY if statuses[gate] == "APPROVED"],
            "checked_at": now()}


def history(conn, *, job_id: str, gate: str) -> list:
    """The decisions behind an approval, oldest first."""
    _gate(gate)
    try:
        return decisions(conn, job_id)
    except CreativeError:
        return []


def all_gates() -> tuple:
    return GATES
