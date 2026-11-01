#!/usr/bin/env python3
"""Read-only memory layering, growth watching and rule-drift projection."""

from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[3]
MEMORY_SCHEMA = ROOT / "packages/contracts/schemas/workflow/memory-record.schema.json"
DRIFT_SCHEMA = ROOT / "packages/contracts/schemas/workflow/rule-drift.schema.json"
# WL-P0-003 (2026-08-19): memory-record is runtime-context only (TTL, non-authoritative).
# Long-term experience must be submitted to ArcheAxis Candidate; WORK-LAB never holds long-term knowledge.
MEMORY_VERSION = "workflow/runtime-context-record/v1"
DRIFT_VERSION = "workflow/rule-drift/v1"
LAYERS = {"ephemeral", "session", "project", "domain", "global"}
PROMOTABLE_LAYERS = LAYERS - {"global", "ephemeral"}
RUNTIME_CONTEXT_TTL_DEFAULT_SECONDS = 86400  # 24h runtime context; not long-term knowledge


def _validate(value: dict[str, Any], schema_path: Path, label: str) -> dict[str, Any]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    errors = sorted(Draft202012Validator(schema).iter_errors(value), key=lambda item: list(item.path))
    if errors:
        raise ValueError(f"invalid {label}: {errors[0].message}")
    return value


def validate_memory(record: dict[str, Any]) -> dict[str, Any]:
    if "content" in record or "body" in record:
        raise ValueError("invalid memory: content bodies are not persisted")
    # WL-P0-003: runtime-context record requires TTL and is non-authoritative.
    if record.get("ttlSeconds") is None:
        record["ttlSeconds"] = RUNTIME_CONTEXT_TTL_DEFAULT_SECONDS
    record.setdefault("authoritative", False)
    if record.get("authoritative") is True:
        raise ValueError("WORK-LAB memory is non-authoritative runtime context; long-term knowledge goes to ArcheAxis Candidate")
    return _validate(record, MEMORY_SCHEMA, "memory")


def propose_memory(record: dict[str, Any], target_layer: str) -> dict[str, Any]:
    validate_memory(record)
    if record["status"] not in {"observed", "blocked"}:
        raise ValueError("memory can only be proposed from observed or blocked state")
    if target_layer not in PROMOTABLE_LAYERS:
        raise ValueError(f"global or ephemeral memory promotion is not allowed: {target_layer}")
    if record["promotion"] != "manual-approval":
        raise ValueError("manual approval is required for memory promotion")
    proposed = copy.deepcopy(record)
    proposed["layer"] = target_layer
    proposed["status"] = "proposed"
    return validate_memory(proposed)


def approve_memory(record: dict[str, Any], *, approval: bool = False) -> dict[str, Any]:
    validate_memory(record)
    if approval is not True:
        raise ValueError("explicit approval is required before memory promotion")
    if record["status"] != "proposed":
        raise ValueError("only proposed memory can be approved")
    approved = copy.deepcopy(record)
    approved["status"] = "approved"
    return validate_memory(approved)


def project_memory(records: list[dict[str, Any]], target_layer: str) -> list[dict[str, Any]]:
    if target_layer not in LAYERS:
        raise ValueError(f"unknown memory layer: {target_layer}")
    validated = [validate_memory(copy.deepcopy(record)) for record in records]
    return [
        record
        for record in validated
        if record["status"] == "approved"
        and (record["layer"] == target_layer or record["layer"] == "global")
    ]


def watch_candidates(candidates: list[dict[str, Any]], known: dict[str, str]) -> dict[str, Any]:
    new_ids: list[str] = []
    changed_ids: list[str] = []
    quarantined: list[str] = []
    for candidate in candidates:
        candidate_id = str(candidate.get("candidateId", "unknown"))
        digest = candidate.get("sourceDigest")
        if not isinstance(digest, str) or len(digest) != 64:
            quarantined.append(candidate_id)
            continue
        if candidate_id not in known:
            new_ids.append(candidate_id)
            quarantined.append(candidate_id)
        elif known[candidate_id] != digest:
            changed_ids.append(candidate_id)
            quarantined.append(candidate_id)
    status = "REVIEW_REQUIRED" if new_ids or changed_ids or quarantined else "STABLE"
    return {
        "status": status,
        "new_candidate_ids": sorted(new_ids),
        "changed_candidate_ids": sorted(changed_ids),
        "quarantined_candidate_ids": sorted(set(quarantined)),
        "mutated_source": False,
    }


def _drift_record(rule_id: str, baseline: str | None, observed: str | None, state: str) -> dict[str, Any]:
    severity = "high" if state in {"changed", "missing"} else "medium"
    action = "quarantine" if state == "missing" else "manual-review"
    drift_id = hashlib.sha256(f"{rule_id}:{baseline}:{observed}:{state}".encode("utf-8")).hexdigest()
    return _validate(
        {
            "schema_version": DRIFT_VERSION,
            "drift_id": drift_id,
            "rule_id": rule_id,
            "baseline_digest": baseline,
            "observed_digest": observed,
            "state": state,
            "severity": severity,
            "action": action,
        },
        DRIFT_SCHEMA,
        "rule drift",
    )


def project_rule_drift(baseline: dict[str, str], observed: dict[str, str]) -> dict[str, Any]:
    drift: list[dict[str, Any]] = []
    for rule_id in sorted(set(baseline) | set(observed)):
        old = baseline.get(rule_id)
        new = observed.get(rule_id)
        if old == new:
            continue
        state = "missing" if new is None else "new" if old is None else "changed"
        drift.append(_drift_record(rule_id, old, new, state))
    return {
        "status": "REVIEW_REQUIRED" if drift else "STABLE",
        "drift": drift,
        "mutated_baseline": False,
    }


if __name__ == "__main__":
    raise SystemExit("Use growth_watcher functions with offline metadata fixtures; no live watcher is exposed.")
