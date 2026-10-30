# SPDX-License-Identifier: MIT
"""Validation of verifier receipts, not a substitute for host readback."""
from __future__ import annotations

import hashlib
import json
import re


def canonical_hash(value: str) -> str:
    if not isinstance(value, str):
        raise ValueError("expected SHA-256 string")
    value = value.removeprefix("sha256:").lower()
    if not re.fullmatch(r"[0-9a-f]{64}", value) or value == "0" * 64:
        raise ValueError("expected nonzero SHA-256")
    return "sha256:" + value


def request_hash(request: dict) -> str:
    """Hash JSON independently of object-key order; array order is significant."""
    payload = json.dumps(request, sort_keys=True, ensure_ascii=False,
                         separators=(",", ":"), allow_nan=False).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def validate_evidence(evidence: dict | None, *, operation_id: str | None = None,
                      attempt_id: str | None = None) -> dict:
    if not isinstance(evidence, dict):
        raise ValueError("success requires artifact and readback evidence")
    result = dict(evidence)
    for field in ("operation_id", "attempt_id"):
        if not isinstance(result.get(field), str) or not result[field].strip():
            raise ValueError(f"missing evidence binding: {field}")
    for field, expected in (("operation_id", operation_id), ("attempt_id", attempt_id)):
        if expected is not None and result[field] != expected:
            raise ValueError(f"evidence {field} does not match current work")
    for field in ("artifact_sha256", "readback_sha256"):
        result[field] = canonical_hash(result.get(field))
    json.dumps(result, allow_nan=False)
    return result
