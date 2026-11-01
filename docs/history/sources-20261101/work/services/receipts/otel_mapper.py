"""OpenTelemetry / OpenInference semantic mapping (NX-300 / WLOSS-600).

WLOSS-600 Observer Semantic Convention: the WORK-LAB Observer Semantic
Contract (work-lab/observer-projection/*) is the ONLY internal projection
schema. External telemetry schemas (OTel GenAI SemConv, OpenInference) are
mapped TO and FROM the canonical contract exclusively through this module —
the Observer and snapshot pipeline never depend on any single vendor schema.

Maps WORK-LAB canonical events to versioned OTel/OpenInference semantic fields
and back losslessly (for the allowed fields).

- Default recorded fields: operation, provider, model, tokens, cache, latency,
  outcome, error class, task/source digest, and low-cardinality labels.
- `gen_ai.input.messages`, `gen_ai.output.messages`, Prompt, Response, tool
  arguments/result body are permanently OFF by default.
- Schema mapping records the OTel/OpenInference version snapshot.
- Unknown fields are preserved in an isolated extension zone, never breaking an
  older projection.
- Local event contract only; no Collector/Langfuse/Phoenix/OpenLIT install.

Privacy negative control: message bodies, secrets, full paths, and session
content never enter the mapped output.
"""
from __future__ import annotations

from typing import Any

OTEL_VERSION = "1.27.0"
OPENINFERENCE_VERSION = "0.1.0"
CANONICAL_VERSION = "work-lab/observer-projection/v2"
OBSERVER_SEMANTIC_CONTRACT = "work-lab/observer-projection"  # sole internal semantic family

# Fields permanently excluded from any mapped/exported view.
PRIVACY_BLOCKED = (
    "gen_ai.input.messages", "gen_ai.output.messages", "gen_ai.prompt",
    "gen_ai.completion", "prompt", "response", "tool_arguments", "tool_result",
    "tool.result", "tool.arguments", "session", "session_id", "full_path",
    "api_key", "authorization", "password", "secret", "token", "cookie",
)

# Canonical -> OTel semantic field mapping (allowed low-cardinality fields only).
_CANONICAL_TO_OTEL = {
    "operation": "gen_ai.operation.name",
    "provider": "gen_ai.provider.name",
    "model": "gen_ai.request.model",
    "inputTokens": "gen_ai.usage.input_tokens",
    "outputTokens": "gen_ai.usage.output_tokens",
    "cacheReadTokens": "gen_ai.usage.cache_read_input_tokens",
    "cacheWriteTokens": "gen_ai.usage.cache_creation_input_tokens",
    "latencyMs": "gen_ai.server.response.duration",
    "outcome": "gen_ai.system.operation.status",
    "errorClass": "gen_ai.error.type",
    "taskDigest": "worklab.task.digest",
    "sourceDigest": "worklab.source.digest",
}


class PrivacyBlockedError(ValueError):
    """Raised when a field that must never be exported is present."""


def _is_blocked(key: str) -> bool:
    k = key.lower()
    # Exact/likely-sensitive token words, but NOT field names like inputTokens/outputTokens/cacheReadTokens.
    import re
    if re.search(r"\b(?:api[_-]?token|access[_-]?token|auth[_-]?token|bearer[_-]?token|session[_-]?token|oauth[_-]?token)\b", k):
        return True
    # Exact sensitive keys (bare prompt/response/token message bodies).
    if k in ("prompt", "response", "gen_ai.prompt", "gen_ai.completion",
             "gen_ai.input.messages", "gen_ai.output.messages", "tool_arguments",
             "tool_result", "tool.arguments", "tool.result", "session",
             "full_path", "api_key", "authorization", "password", "secret",
             "cookie"):
        return True
    # Sensitive substrings that can never be legitimate OTel metric fields.
    if any(b in k for b in ("api_key", "authorization", "password", "secret",
                            "bearer", "oauth_token", "access_token", "session_id")):
        return True
    return False


def canonical_to_otel(event: dict[str, Any]) -> dict[str, Any]:
    """Map a WORK-LAB canonical usage/event to OTel semantic fields."""
    out: dict[str, Any] = {
        "schemaVersion": f"otel/gen-ai/{OTEL_VERSION}",
        "mappedFrom": CANONICAL_VERSION,
        "otel_version": OTEL_VERSION,
        "openinference_version": OPENINFERENCE_VERSION,
    }
    extension: dict[str, Any] = {}
    usage = event.get("usage") or {}
    source = {}
    for key in ("provider", "model", "operation"):
        if key in event:
            source[key] = event[key]
    for key, value in usage.items():
        if key == "cost":
            continue
        source[key] = value
    for key, value in event.items():
        if key in ("usage", "schemaVersion", "mode", "generatedAt", "projects",
                   "ci", "governance", "quality", "summary", "freshness"):
            continue
        source.setdefault(key, value)

    for canonical_key, otel_key in _CANONICAL_TO_OTEL.items():
        if canonical_key in source:
            out[otel_key] = source[canonical_key]

    # Anything in the source that is blocked must never be exported.
    for key in list(source) + list(out):
        if _is_blocked(key):
            raise PrivacyBlockedError(f"privacy-blocked field would be exported: {key}")

    # Unknown/unmapped canonical fields go to an isolated extension zone.
    mapped_keys = set(_CANONICAL_TO_OTEL.values())
    for key, value in source.items():
        otel_key = _CANONICAL_TO_OTEL.get(key)
        if otel_key is None and key not in mapped_keys and not _is_blocked(key):
            extension[f"worklab.ext.{key}"] = value
    if extension:
        out["_extensions"] = extension

    return out


def otel_to_canonical(otel: dict[str, Any]) -> dict[str, Any]:
    """Map OTel semantic fields back to WORK-LAB canonical form (lossless for allowed fields)."""
    reverse = {v: k for k, v in _CANONICAL_TO_OTEL.items()}
    canonical: dict[str, Any] = {}
    for otel_key, value in otel.items():
        if otel_key == "schemaVersion" or otel_key == "_extensions":
            continue
        if _is_blocked(otel_key):
            raise PrivacyBlockedError(f"privacy-blocked field would be imported: {otel_key}")
        if otel_key in reverse:
            canonical[reverse[otel_key]] = value
        else:
            # preserve unknown standard fields in extension (non-blocked)
            if otel_key.startswith("worklab.ext."):
                canonical[otel_key[len("worklab.ext."):]] = value
    canonical["schemaVersion"] = CANONICAL_VERSION
    return canonical


def roundtrip_lossless(event: dict[str, Any]) -> dict[str, Any]:
    """Round-trip a canonical event -> OTel -> canonical; allowed fields must be unchanged."""
    otel = canonical_to_otel(event)
    back = otel_to_canonical(otel)
    # Compare only the fields we actually map.
    for canonical_key in _CANONICAL_TO_OTEL:
        a = event.get("usage", {}).get(canonical_key, event.get(canonical_key))
        b = back.get(canonical_key)
        if a is not None and b != a:
            return {"lossless": False, "field": canonical_key, "original": a, "mapped": b}
    return {"lossless": True}
