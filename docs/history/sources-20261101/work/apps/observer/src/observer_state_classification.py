"""Read-only projection state classification (integrated-taskpack NF-09).

Splits a client's observed state into five non-overlapping, evidence-backed
buckets so the Observer never shows a false LIVE and never conflates a real
zero with "unknown":

  LIVE          real collection, fresh + source-exact, authorized, >0 active.
  ACTUAL_ZERO   authorized, fresh + source-exact, and genuinely zero active —
                a real zero, distinct from UNKNOWN.
  STALE         evidence exists but is old / partial (broken chain, not live).
  UNKNOWN       no reliable evidence (chain broken or empty).
  UNAUTHORIZED  a client not in the authorized registry; its data is never
                counted as active (transferred / legacy projects excluded).

Every result carries its source time and scope.  The classifier is pure and
read-only: it returns evidence only, never a mutation surface, and cannot
change execution state (the "service interface stays read-only" guarantee is
locked separately via the projection's ``mutation_surface`` all-False set).
"""
from __future__ import annotations

from typing import Any

LIVE = "LIVE"
ACTUAL_ZERO = "ACTUAL_ZERO"
STALE = "STALE"
UNKNOWN = "UNKNOWN"
UNAUTHORIZED = "UNAUTHORIZED"

_ALL_STATES = (LIVE, ACTUAL_ZERO, STALE, UNKNOWN, UNAUTHORIZED)


def classify_client_state(evidence: dict[str, Any]) -> dict[str, Any]:
    """Classify one client's projection evidence into a single bucket.

    ``evidence`` keys (all optional, defaulting toward the conservative bucket):
      authorized   bool   client is in the authorized registry
      freshness    str    "fresh" | "delayed" | "stale" | "unknown"
      quality      str    "exact" | "partial" | "unknown"
      active_tasks int|None  how many active tasks the collection observed
      source_time  str|None  when the evidence was observed (for display)
      scope        str|None  the applicability scope the evidence covers
    """
    authorized = bool(evidence.get("authorized", False))
    freshness = str(evidence.get("freshness", "unknown"))
    quality = str(evidence.get("quality", "unknown"))
    active = evidence.get("active_tasks")
    source_time = evidence.get("source_time")
    scope = evidence.get("scope")

    base = {
        "state": None,
        "authorized": authorized,
        "freshness": freshness,
        "quality": quality,
        "active_tasks": active,
        "source_time": source_time,
        "scope": scope,
        "counted_in_active": False,
        "contributes_active": 0,
        "mutates_execution_state": False,  # classifier is read-only by construction
    }

    if not authorized:
        # Not counted as active regardless of any observed numbers.
        base["state"] = UNAUTHORIZED
        base["note"] = "client not in authorized registry; data excluded from active tally"
        return base

    # No reliable evidence -> UNKNOWN (never a false LIVE).
    if quality == "unknown" or freshness == "unknown":
        base["state"] = UNKNOWN
        base["note"] = "no reliable evidence (chain broken or empty); not asserted live"
        return base

    exact_and_fresh = quality == "exact" and freshness == "fresh"
    if exact_and_fresh and active == 0:
        base["state"] = ACTUAL_ZERO
        base["contributes_active"] = 0
        base["note"] = "authorized, fresh, source-exact, and genuinely zero active — a real zero"
        return base
    if exact_and_fresh:
        base["state"] = LIVE
        base["counted_in_active"] = True
        base["contributes_active"] = int(active or 0)
        base["note"] = "real collection: fresh + source-exact + authorized"
        return base
    # Evidence exists but is delayed/stale or only partially reliable.
    base["state"] = STALE
    base["note"] = "evidence present but stale/partial; retained, not asserted live"
    return base


def classify_all(evidence_by_client: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """Classify every client and summarize the active tally.

    Only LIVE/ACTUAL_ZERO are authorized buckets; UNAUTHORIZED is excluded and
    UNKNOWN/STALE are retained-but-not-live.  The active tally counts only the
    LIVE contributions.
    """
    results: dict[str, dict[str, Any]] = {}
    for client, ev in evidence_by_client.items():
        results[client] = classify_client_state(ev)
    tally = {
        "clients": len(results),
        "by_state": {},
        "active_tasks": 0,
    }
    for r in results.values():
        tally["by_state"][r["state"]] = tally["by_state"].get(r["state"], 0) + 1
    for r in results.values():
        if r["state"] == LIVE:
            tally["active_tasks"] += r["contributes_active"]
    return {"clients": results, "tally": tally}


def assert_read_only(projection: dict[str, Any]) -> dict[str, Any]:
    """Lock the service-interface read-only guarantee (NF-09 acceptance #2).

    The projection's ``mutationSurface`` must be all-False; the classifier adds
    no write of its own.  Returns the asserted surface; raises if any surface
    claims a mutation path.
    """
    surface = projection.get("mutationSurface", {})
    mutated = [k for k, v in surface.items() if v is True]
    if mutated:
        raise ValueError(f"projection claims a mutation surface: {mutated}")
    return {
        "read_only": True,
        "externalMutation": False,
        "ledgerMutation": False,
        "approvalMutation": False,
        "gitControl": False,
    }


def state_enum() -> tuple[str, ...]:
    return _ALL_STATES
