# SPDX-License-Identifier: MIT
"""One rule for stamped, tracked registers: an unchanged payload keeps the stamp it already has.

WHY THIS EXISTS
    Four generators write tracked JSON with a ``generated_at`` field. Rebuilding them with no
    content change used to rewrite that one field, and the audited candidate digest is a hash over
    tracked bytes -- so a no-op recomputation moved the digest of a candidate that had not moved,
    and a receipt bound to the previous digest silently stopped describing the shipped tree. That is
    how this round's first measurement went stale: editing prose in
    ``docs/CODEX-AUDIT-ENTRY.md`` shifted the ``authority`` line numbers in the coverage registers,
    the refresh rewrote three further registers whose only real change was their own timestamp.

    Masking the stamp field before comparing answers the only question that matters: did the
    content change? If it did not, the recorded moment is kept and the tracked bytes are unchanged;
    if it did, the new moment is written along with it.

NOT A WAY TO HIDE STALENESS
    This decides what to *write*; ``--check`` in each generator still decides whether the published
    bytes match a recomputation, and it compares with the stamp folded out, so a real content
    change cannot hide behind an unchanged timestamp.
"""
from __future__ import annotations

import json
from pathlib import Path

STAMP_KEY = "generated_at"


def _masked(document: dict) -> str:
    clone = dict(document)
    clone.pop(STAMP_KEY, None)
    return json.dumps(clone, sort_keys=True, ensure_ascii=False)


def keeping_the_recorded_stamp(path: Path, payload: dict) -> dict:
    """Return ``payload`` with ``path``'s recorded ``generated_at`` when nothing else changed."""
    if not Path(path).is_file():
        return payload
    try:
        existing = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    except (OSError, ValueError):
        return payload
    if not isinstance(existing, dict) or not isinstance(payload, dict):
        return payload
    if _masked(existing) == _masked(payload):
        stamped = dict(payload)
        stamped[STAMP_KEY] = existing.get(STAMP_KEY, payload.get(STAMP_KEY))
        return stamped
    return payload
