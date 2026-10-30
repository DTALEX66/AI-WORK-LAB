# SPDX-License-Identifier: MIT
"""DL-P0-031 Design decision ledger: options considered, choice, rationale.

A decision records what was rejected as well as what was chosen, so a later
review can tell a considered tradeoff from an accident. Human gates are
structural, not advisory: a decision that carries a gate (DIRECTION, QUALITY,
RIGHTS, PRODUCTION, RELEASE) can only be decided or reversed by a human actor,
and no agent — including this one — may sign it.
"""
from __future__ import annotations

import json
import re

from .store import CreativeError, dumps, now, require_job, transaction
from .requirement_ledger import requirement

GATES = ("DIRECTION", "QUALITY", "RIGHTS", "PRODUCTION", "RELEASE", "METHOD")
HUMAN_ONLY = ("DIRECTION", "QUALITY", "RIGHTS", "PRODUCTION", "RELEASE")
KINDS = ("PROPOSED", "DECIDED", "SUPERSEDED", "REVERSED")
POSITIVE_GATE_CHOICES = frozenset(("APPROVE", "APPROVED", "PASS", "ACCEPT", "ACCEPTED"))
_IDENTITY = re.compile(r"^DEC-[A-Za-z0-9_.-]{1,64}$")
_REQ = re.compile(r"^REQ-[A-Za-z0-9_.-]{1,64}$")


def _identity(value) -> str:
    if not isinstance(value, str) or not _IDENTITY.match(value):
        raise CreativeError(f"decision id must match DEC-<name>: {value!r}")
    return value


def _text(value, field) -> str:
    if not isinstance(value, str) or not value.strip():
        raise CreativeError(f"{field} must be a nonempty string")
    return value


def _actor(actor, actor_kind) -> tuple:
    actor = _text(actor, "actor")
    if actor_kind not in ("human", "agent"):
        raise CreativeError(f"actor_kind must be human or agent: {actor_kind!r}")
    return actor, actor_kind


def _options(options) -> list:
    if not isinstance(options, (list, tuple)) or not options:
        raise CreativeError("a decision must list at least one option")
    normalized, seen = [], set()
    for option in options:
        if not isinstance(option, dict):
            raise CreativeError("options must be objects")
        unknown = set(option) - {"option_id", "summary", "tradeoffs"}
        if unknown:
            raise CreativeError("unknown option field: " + ", ".join(sorted(unknown)))
        option_id = _text(option.get("option_id"), "option_id")
        if option_id in seen:
            raise CreativeError(f"duplicate option_id {option_id!r}")
        seen.add(option_id)
        normalized.append({"option_id": option_id, "summary": _text(option.get("summary"), "option summary"),
                           "tradeoffs": option.get("tradeoffs", "")})
    return normalized


def _current(conn, dec_id: str):
    return conn.execute("SELECT job_id, kind, gate, options_json, chosen, rationale, actor, actor_kind "
                        "FROM decision_event WHERE dec_id=? ORDER BY event_no DESC LIMIT 1", (dec_id,)).fetchone()


def decision(conn, dec_id: str) -> dict:
    """Latest state plus the proposal that defined the options and the gate."""
    state = _current(conn, _identity(dec_id))
    if not state:
        raise CreativeError(f"unknown decision: {dec_id!r}")
    proposal = conn.execute("SELECT gate, options_json, requirement_refs, actor, actor_kind FROM decision_event "
                            "WHERE dec_id=? AND options_json IS NOT NULL ORDER BY event_no LIMIT 1",
                            (dec_id,)).fetchone()
    gate = proposal[0] if proposal else state[2]
    options = json.loads(proposal[1]) if proposal else []
    refs = json.loads(proposal[2]) if proposal and proposal[2] else []
    return {"dec_id": dec_id, "job_id": state[0], "state": state[1], "gate": gate,
            "options": options, "requirement_refs": refs, "chosen": state[4], "rationale": state[5],
            "actor": state[6], "actor_kind": state[7],
            "proposed_by": {"actor": proposal[3], "actor_kind": proposal[4]} if proposal else None}


def propose(conn, *, job_id: str, dec_id: str, options, actor: str, actor_kind: str = "agent",
            gate=None, requirement_refs=(), supersedes=None, rationale=None) -> dict:
    require_job(conn, job_id)
    dec_id = _identity(dec_id)
    actor, actor_kind = _actor(actor, actor_kind)
    normalized = _options(options)
    if gate is not None and gate not in GATES:
        raise CreativeError(f"unknown gate: {gate!r}")
    refs = []
    for ref in requirement_refs:
        if not isinstance(ref, str) or not _REQ.match(ref):
            raise CreativeError(f"requirement_refs must be REQ- ids: {ref!r}")
        requirement(conn, ref)
        refs.append(ref)
    if supersedes is not None:
        _identity(supersedes)
    with transaction(conn):
        if _current(conn, dec_id):
            raise CreativeError("decision id is already used; decisions are append-only")
        previous = None
        if supersedes:
            # Validate under the same IMMEDIATE transaction as the successor
            # insert. Two writers cannot both observe one live predecessor and
            # create a forked lineage.
            previous = decision(conn, supersedes)
            if previous["job_id"] != job_id:
                raise CreativeError("a decision may only supersede another decision in the same job")
            if previous["state"] not in ("PROPOSED", "DECIDED"):
                raise CreativeError(f"decision {supersedes!r} is not active and cannot be superseded")
            if previous["gate"] in HUMAN_ONLY and actor_kind != "human":
                raise CreativeError(f"{previous['gate']} gate requires a human supersession")
        conn.execute("INSERT INTO decision_event "
                     "(dec_id, job_id, kind, gate, actor, actor_kind, options_json, requirement_refs, "
                     "supersedes, rationale, at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                     (dec_id, job_id, "PROPOSED", gate, actor, actor_kind, dumps(normalized),
                      dumps(refs) if refs else None, supersedes, rationale, now()))
        if supersedes:
            conn.execute("INSERT INTO decision_event "
                         "(dec_id, job_id, kind, gate, actor, actor_kind, rationale, supersedes, at) "
                         "VALUES (?,?,?,?,?,?,?,?,?)",
                         (supersedes, previous["job_id"], "SUPERSEDED", previous["gate"], actor, actor_kind,
                          f"superseded by {dec_id}", dec_id, now()))
    return decision(conn, dec_id)


def decide(conn, *, dec_id: str, chosen: str, rationale: str, actor: str,
           actor_kind: str = "agent") -> dict:
    """Choose an option. Gate decisions require a human actor."""
    current = decision(conn, dec_id)
    if current["state"] != "PROPOSED":
        raise CreativeError(f"decision is {current['state']}, not PROPOSED")
    actor, actor_kind = _actor(actor, actor_kind)
    chosen = _text(chosen, "chosen option")
    if chosen not in {option["option_id"] for option in current["options"]}:
        raise CreativeError(f"chosen option is not one of the recorded options: {chosen!r}")
    if current["gate"] in HUMAN_ONLY and actor_kind != "human":
        raise CreativeError(f"{current['gate']} gate requires a human decision; an agent cannot sign it")
    with transaction(conn):
        conn.execute("INSERT INTO decision_event "
                     "(dec_id, job_id, kind, gate, actor, actor_kind, chosen, rationale, at) "
                     "VALUES (?,?,?,?,?,?,?,?,?)",
                     (dec_id, current["job_id"], "DECIDED", current["gate"], actor, actor_kind,
                      chosen, _text(rationale, "rationale"), now()))
    return decision(conn, dec_id)


def reverse(conn, *, dec_id: str, rationale: str, actor: str, actor_kind: str = "human") -> dict:
    """Reversal keeps the original decision visible; it does not rewrite it."""
    current = decision(conn, dec_id)
    if current["state"] != "DECIDED":
        raise CreativeError(f"only a DECIDED decision can be reversed; found {current['state']}")
    actor, actor_kind = _actor(actor, actor_kind)
    if current["gate"] in HUMAN_ONLY and actor_kind != "human":
        raise CreativeError(f"{current['gate']} gate requires a human reversal")
    with transaction(conn):
        conn.execute("INSERT INTO decision_event "
                     "(dec_id, job_id, kind, gate, actor, actor_kind, rationale, at) "
                     "VALUES (?,?,?,?,?,?,?,?)",
                     (dec_id, current["job_id"], "REVERSED", current["gate"], actor, actor_kind,
                      _text(rationale, "rationale"), now()))
    return decision(conn, dec_id)


def decisions(conn, job_id: str) -> list:
    require_job(conn, job_id)
    ids = [row[0] for row in conn.execute("SELECT DISTINCT dec_id FROM decision_event WHERE job_id=? "
                                          "ORDER BY dec_id", (job_id,))]
    return [decision(conn, dec_id) for dec_id in ids]


def decisions_for_requirement(conn, req_id: str) -> list:
    requirement(conn, req_id)
    rows = conn.execute("SELECT DISTINCT dec_id, requirement_refs FROM decision_event "
                        "WHERE requirement_refs IS NOT NULL ORDER BY dec_id").fetchall()
    return [decision(conn, dec_id) for dec_id, refs in rows if req_id in json.loads(refs)]


def open_gates(conn, job_id: str) -> list:
    """Gates that still lack a live human choice which permits progress."""
    signed = {d["gate"] for d in decisions(conn, job_id)
              if d["gate"] in HUMAN_ONLY and _gate_satisfied(d)}
    return [gate for gate in HUMAN_ONLY if gate not in signed]


def _gate_satisfied(item: dict) -> bool:
    """A direction choice selects a path; all other human gates must approve."""
    if item["state"] != "DECIDED" or item.get("actor_kind") != "human":
        return False
    if item["gate"] == "DIRECTION":
        return bool(item.get("chosen"))
    return str(item.get("chosen") or "").upper() in POSITIVE_GATE_CHOICES


def assert_gate(conn, job_id: str, gate: str) -> dict:
    """Fail closed unless the named gate has a live human choice that permits progress."""
    if gate not in HUMAN_ONLY:
        raise CreativeError(f"not a human gate: {gate!r}")
    blocking = None
    for item in decisions(conn, job_id):
        if item["gate"] == gate and _gate_satisfied(item):
            return item
        if item["gate"] == gate and item["state"] == "DECIDED":
            blocking = item
    if blocking is not None:
        raise CreativeError(
            f"{gate} gate decision {blocking.get('chosen')!r} does not approve progress")
    raise CreativeError(f"{gate} gate is unsigned: a human decision is required before this step")


def history(conn, dec_id: str) -> list:
    _identity(dec_id)
    return [{"event_no": row[0], "kind": row[1], "gate": row[2], "chosen": row[3], "actor": row[4],
             "actor_kind": row[5], "rationale": row[6], "at": row[7]} for row in conn.execute(
        "SELECT event_no, kind, gate, chosen, actor, actor_kind, rationale, at FROM decision_event "
        "WHERE dec_id=? ORDER BY event_no", (dec_id,))]
