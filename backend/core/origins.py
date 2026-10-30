# SPDX-License-Identifier: MIT
"""Controlled data-origin propagation (audit F07).

The envelope has one origin rule instead of a per-table default. `live` is a
claim about real user work, so it may only appear when *nothing* upstream of it
said otherwise: a project, task, attempt, handoff, result or verification that
was created as `test` or `demo` keeps every row it produces non-live.

Rules implemented here:

* ``combine`` returns the least authoritative origin in a chain. Any `test` wins
  over anything else, then `demo`, and only an all-`live` chain is `live`.
* ``refuse_promotion`` is what the service uses before a write: a caller cannot
  erase an upstream `test` by declaring `live` here. The request is refused
  rather than silently rewritten, because quietly changing what the caller
  claimed would hide the mismatch from the audit trail.
* ``live_eligible`` answers the readiness question: a chain that ever carried a
  synthetic row is never live evidence, whatever the stored column says.
* legacy rows written before this rule existed carry ``origin_provenance`` =
  ``UNENFORCED_LEGACY`` and are never live-eligible on their own account.
"""
from __future__ import annotations

ORIGINS = ("live", "demo", "test")
_RANK = {"live": 0, "demo": 1, "test": 2}
SYNTHETIC = ("demo", "test")

#: A row this build wrote with the chain rule applied.
PROVENANCE_ENFORCED = "ENFORCED_CHAIN"
#: A row that predates the chain rule; its stored origin was never checked.
PROVENANCE_LEGACY_UNENFORCED = "UNENFORCED_LEGACY"


class OriginError(ValueError):
    """An origin vocabulary or promotion the contract refuses."""


def check(origin) -> str:
    if origin not in _RANK:
        raise OriginError("DATA_ORIGIN_UNKNOWN " + repr(origin) + " outside " + repr(list(ORIGINS)))
    return origin


def combine(*origins) -> str:
    """The least authoritative of the given origins (missing entries ignored)."""
    values = [check(o) for o in origins if o is not None]
    if not values:
        return "live"
    return max(values, key=lambda value: _RANK[value])


def is_synthetic(origin) -> bool:
    return check(origin) in SYNTHETIC


def refuse_promotion(declared, chain_origin: str, *, where: str = "REQUEST"):
    """Refuse a call that would raise a non-live chain back to `live`."""
    declared = check(declared)
    chain_origin = check(chain_origin)
    if _RANK[declared] < _RANK[chain_origin]:
        raise OriginError(
            "DATA_ORIGIN_PROMOTION_REFUSED " + where + " declares " + repr(declared)
            + " but its upstream chain is " + repr(chain_origin)
            + "; a synthetic project/task/attempt is not washed by re-declaring the origin")
    return combine(declared, chain_origin)


def live_eligible(*origins, provenance: str | None = None) -> bool:
    """True only when every origin in the chain is live and the chain was enforced."""
    if provenance == PROVENANCE_LEGACY_UNENFORCED:
        return False
    values = [o for o in origins if o is not None]
    return bool(values) and all(check(value) == "live" for value in values)
