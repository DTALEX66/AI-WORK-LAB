from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from typing import Any, Iterable


ALLOWED_FIELDS = {
    "line_id",
    "project_id",
    "source_digest",
    "content_digest",
    "status",
    "freshness",
    "supersedes",
    "goal",
    "current_state",
    "decisions",
    "constraints",
    "evidence_refs",
    "blockers",
    "next_action",
}
CONTENT_FIELDS = ("goal", "current_state", "decisions", "constraints", "evidence_refs", "blockers", "next_action")
SENSITIVE_KEYS = {"api_key", "authorization", "cookie", "password", "prompt", "response", "secret", "token"}


class ContextLineError(ValueError):
    """Raised when a ContextLine cannot be safely promoted into a pack."""


def _nested_keys(value: Any) -> set[str]:
    if isinstance(value, dict):
        return {str(key).lower() for key in value} | set().union(*(_nested_keys(item) for item in value.values()))
    if isinstance(value, list):
        return set().union(*(_nested_keys(item) for item in value)) if value else set()
    return set()


def _digest(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def normalize_context_lines(lines: Iterable[dict[str, Any]], *, project_id: str) -> list[dict[str, Any]]:
    if not isinstance(project_id, str) or not project_id:
        raise ContextLineError("project_id is required")
    normalized: dict[str, dict[str, Any]] = {}
    for raw in lines:
        if not isinstance(raw, dict):
            raise ContextLineError("ContextLine must be an object")
        if set(raw) - ALLOWED_FIELDS or _nested_keys(raw) & SENSITIVE_KEYS:
            raise ContextLineError("ContextLine contains an unknown or sensitive field")
        if raw.get("project_id") != project_id:
            raise ContextLineError("ContextLine belongs to another project")
        if not isinstance(raw.get("line_id"), str) or not raw["line_id"]:
            raise ContextLineError("line_id is required")
        if raw.get("status", "observed") not in {"observed", "proposed", "approved", "retired"}:
            raise ContextLineError("unsupported ContextLine status")
        if raw.get("freshness", "fresh") == "stale":
            continue
        if raw.get("freshness", "fresh") not in {"fresh", "unknown"}:
            raise ContextLineError("unsupported ContextLine freshness")
        item = {key: deepcopy(raw[key]) for key in ALLOWED_FIELDS if key in raw}
        for field in CONTENT_FIELDS:
            item.setdefault(field, [] if field.endswith("_refs") or field == "blockers" else "")
        if not isinstance(item["evidence_refs"], list) or not isinstance(item["blockers"], list):
            raise ContextLineError("evidence_refs and blockers must be arrays")
        item["content_digest"] = _digest({field: item[field] for field in CONTENT_FIELDS})
        normalized[item["line_id"]] = item
    superseded = {old for item in normalized.values() for old in item.get("supersedes", [])}
    result = [item for line_id, item in normalized.items() if line_id not in superseded and item.get("status") != "retired"]
    result.sort(key=lambda item: item["line_id"])
    return result


def render_context_lines(lines: Iterable[dict[str, Any]]) -> str:
    safe = normalize_context_lines(list(lines), project_id=next(iter(lines), {}).get("project_id", "unknown")) if not isinstance(lines, list) else lines
    sections = ["## Context Lines", ""]
    for item in safe:
        sections.append(f"### {item['line_id']}")
        sections.append(f"- Project: `{item['project_id']}`")
        sections.append(f"- Status: `{item.get('status', 'observed')}`")
        sections.append(f"- Source digest: `{item['source_digest']}`")
        for field in CONTENT_FIELDS:
            value = item.get(field)
            if value not in ("", [], None):
                sections.append(f"- {field}: {json.dumps(value, ensure_ascii=False, sort_keys=True)}")
        sections.append(f"- Content digest: `{item['content_digest']}`")
        sections.append("")
    return "\n".join(sections).rstrip() + "\n"
