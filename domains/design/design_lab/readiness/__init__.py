# SPDX-License-Identifier: MIT
"""DL-P0-070 / DL-P1-100 / DL-P1-120: readiness layer (structural contracts only).

Module boundary: this package answers "what is *claimed*, what is *recorded*, and
what a runtime resolver must therefore *refuse*" for Adobe host capabilities,
candidate models, and the vectorisation provider/bench harness. It performs no
host launch, no model download, no load, no inference, and no network access.
Every document it produces or validates is E1 (STRUCTURAL) unless it merely
restates a machine fact already recorded in this repository, in which case the
recorded evidence level and observation date travel with the fact.

Nothing in this package may promote a capability on the strength of file
existence alone: an unverified claim stays `verified: false`,
`verification.state: "NOT_VERIFIED"`, and stays refused by `resolve()`.
"""
from __future__ import annotations


class ReadinessError(RuntimeError):
    """A readiness contract, registry, or resolution rule was violated.

    Raised with a precise, actionable message. Callers must treat it as a
    fail-closed outcome: an unreadable, unknown, unqualified, licence-blocked,
    or hardware-exceeding subject is never silently downgraded to "usable".
    """
