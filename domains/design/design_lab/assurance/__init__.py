# SPDX-License-Identifier: MIT
"""DLDS-F070 assurance package boundary and primitives.

This package owns the separated assurance planes of DESIGN-LAB:

* :mod:`~design_lab.assurance.qa_plane` -- the QA plane split (deterministic /
  model-assisted / human) and its evidence ceilings;
* :mod:`~design_lab.assurance.human_jury` -- the human jury record structure;
* :mod:`~design_lab.assurance.quality_record` -- the sealed per-artifact
  QualityRecord (DL-CLOUDAUDIT-B3): three physically separated fields
  ``quality.{deterministic, automated_judge, human_jury}`` that cannot overwrite
  one another, a validator, and the guarantee that an automated judge can never
  reach the gate or fill the human field.

The knowledge-feedback candidate module is back in the tree under the current
integrated TaskPack (T16/U09). It is still a contract module only: it can build a
PENDING_HUMAN_APPROVAL candidate, record a named human's approval or rejection,
revoke, and produce the outbound projection, but it has no ArcheAxis transport.
``src/design_lab/knowledge_review.py`` is the persistence/readback façade.

Boundary: structural contracts and validators only. Nothing in this package
runs a check, calls a provider, opens a host, reads an artifact, writes a file,
touches the network or invents a human identity. Work that would need a live
tool or a real human fails closed with :class:`AssuranceError`.

Evidence rule held by every module here: an AI agent may never sign a human
gate. No function in this package can produce a human verdict, a human
attestation or an approved export; automated planes may only ever produce a
recommendation. The shared primitives below exist so the three modules cannot
drift apart on what a digest, a timestamp or an identifier is.
"""
from __future__ import annotations

from datetime import datetime, timezone
import re

from ..runtime.attempt_contract import canonical_hash

__all__ = [
    "AssuranceError",
    "RFC3339_PATTERN",
    "require_text",
    "require_digest",
    "require_rfc3339",
    "utc_now_rfc3339",
]


class AssuranceError(RuntimeError):
    """An assurance contract violation; every caller must fail closed."""


# Python's datetime.fromisoformat accepts date-only and naive values, and the
# installed jsonschema has no 'date-time' checker (rfc3339-validator is absent),
# so the RFC3339 requirement is enforced explicitly here instead of by "format".
RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}[Tt]\d{2}:\d{2}:\d{2}(\.\d+)?([Zz]|[+-]\d{2}:\d{2})$"
)


def require_text(value, field: str) -> str:
    """Return a non-empty string or fail closed naming the offending field."""
    if not isinstance(value, str) or not value.strip():
        raise AssuranceError(f"{field} must be a non-empty string; got {value!r}")
    return value


def require_digest(value, field: str) -> str:
    """Return a canonical nonzero ``sha256:`` digest or fail closed."""
    try:
        return canonical_hash(value)
    except ValueError as exc:
        raise AssuranceError(
            f"{field} must be a nonzero lowercase sha256: digest ({exc}); got {value!r}"
        ) from exc


def require_rfc3339(value, field: str) -> str:
    """Return an RFC3339 timestamp text with an explicit offset, or fail closed."""
    text = require_text(value, field)
    if not RFC3339_PATTERN.match(text):
        raise AssuranceError(
            f"{field} must be an RFC3339 date-time with an explicit UTC offset "
            f"(for example 2026-09-12T00:00:00Z); got {text!r}"
        )
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00").replace("z", "+00:00"))
    except ValueError as exc:  # pragma: no cover - regex already bounds the shape
        raise AssuranceError(f"{field} is not a parseable RFC3339 date-time: {text!r}") from exc
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise AssuranceError(f"{field} must carry an explicit UTC offset: {text!r}")
    return text


def utc_now_rfc3339() -> str:
    """Current UTC time in the RFC3339 shape this package accepts."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
