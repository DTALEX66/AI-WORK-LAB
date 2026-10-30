# SPDX-License-Identifier: MIT
"""R3-07 evidence-qualified selection. Never launches or grants execution authority.

Only controlled probe/approval producers may populate the evidence catalog.
Integrity checks cannot turn a caller's assertions into independent acceptance.
Callers must requalify immediately before dispatch and apply Human Gates.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import PurePosixPath
import re

from jsonschema import Draft202012Validator, FormatChecker

from .paths import PROJECT_ROOT, resolve_paths

SCHEMA_PATH = PROJECT_ROOT / "design-lab/schemas/profile-evidence.schema.json"
DEFAULT_CATALOG = PROJECT_ROOT / "design-lab/config/profiles.json"
DEFAULT_PURPOSE = "PERSONAL_RESEARCH_NONCOMMERCIAL"
HASH = re.compile(r"(?!0{64}$)[a-f0-9]{64}")
MAX_ARTIFACT_BYTES = 512 * 1024 * 1024
STEPS = [
    "Probe the exact current host/adapter version and launch result.",
    "Run the requested format/operation with required editability and offline constraints.",
    "Record fixture/output SHA-256, reopen/readback and rollback results.",
    "Verify purpose-specific license, region, resource and dependency receipts.",
    "Refresh expired evidence, then requalify before dispatch; retain Human Gates.",
]


def _unique(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("duplicate JSON key")
        result[key] = value
    return result


def _json(path):
    return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=_unique,
                      parse_constant=lambda value: (_ for _ in ()).throw(ValueError("nonfinite JSON")))


def _time(value):
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.tzinfo is None:
        raise ValueError("timezone required")
    return result


def _fresh(record, now):
    try:
        return _time(record["observed_at"]) <= now < _time(record["expires_at"])
    except (KeyError, TypeError, ValueError, AttributeError):
        return False


def _artifact_ok(ref, layout):
    """Only explicit, bounded project-owned evidence; no external/profile reads."""
    try:
        raw = ref["path"]
        if not isinstance(raw, str) or any(c in raw for c in ("\\", ":", "\x00")):
            return False
        parts = raw.split("/")
        if any(not part or part in (".", "..") or part.startswith(".") and part != ".project-local"
               or any(word in part.casefold() for word in ("credential", "keychain", "session", "memory", "token"))
               for part in parts):
            return False
        relative = PurePosixPath(raw)
        path = layout.checked_path(layout.project_root / relative)
        if not path.is_relative_to(layout.evidence_root) or path.suffix.lower() not in {
            ".json", ".png", ".jpg", ".webp", ".svg", ".pdf", ".psd", ".ai", ".mp4", ".log", ".txt", ".bin",
            ".cdr", ".psb", ".eps", ".fig", ".blend"
        }:
            return False
        before = path.stat()
        if not path.is_file() or before.st_nlink != 1 or before.st_size > MAX_ARTIFACT_BYTES:
            return False
        digest = hashlib.sha256()
        total = 0
        with path.open("rb") as stream:
            while chunk := stream.read(min(1024 * 1024, MAX_ARTIFACT_BYTES - total + 1)):
                total += len(chunk)
                if total > MAX_ARTIFACT_BYTES:
                    return False
                digest.update(chunk)
        after = path.stat()
        return (before.st_ino, before.st_size, before.st_mtime_ns) == (
            after.st_ino, after.st_size, after.st_mtime_ns
        ) and digest.hexdigest() == ref["sha256"]
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        return False


def _valid_record(record, validator):
    try:
        if not validator.is_valid(record):
            return False
        # JSON Schema numeric bounds alone do not reject Python float NaN.
        json.dumps(record, allow_nan=False)
        return True
    except (TypeError, ValueError, RecursionError):
        return False


def _catalog(value):
    if (not isinstance(value, dict) or set(value) != {"schema_version", "profiles"}
            or value["schema_version"] != "design-lab/profiles/v1"
            or not isinstance(value["profiles"], list) or len(value["profiles"]) > 1000):
        raise ValueError("invalid profiles catalog")
    seen = set()
    for profile in value["profiles"]:
        if (not isinstance(profile, dict)
                or set(profile) - {"id", "kind", "default_enabled", "evidence", "model_sha256", "preference"}
                or not isinstance(profile.get("id"), str)
                or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,127}", profile["id"])
                or profile["id"] in seen or profile.get("kind") not in ("host", "model")
                or type(profile.get("default_enabled")) is not bool):
            raise ValueError("invalid or duplicate profile")
        seen.add(profile["id"])
    return value["profiles"]


def resolve(evidence: dict, *, catalog=None, context=None, now=None, project_root=None):
    """Resolve a request against current, version-bound probe records.

    context is supplied by the current probe/dispatch layer, never inferred from
    historical records: repo_sha, os, versions[id] = {host, adapter}.
    With no current context or no evidence, all candidates fail closed.
    """
    if not isinstance(evidence, dict) or set(evidence) - {
        "format", "operation", "offline", "editable", "rights", "region", "manual_profile", "resources"
    }:
        raise ValueError("invalid selection request")
    for key in ("offline", "editable"):
        if key in evidence and type(evidence[key]) is not bool:
            raise ValueError(key + " must be boolean")
    for key in ("format", "operation", "rights", "manual_profile"):
        if key in evidence and (not isinstance(evidence[key], str) or not evidence[key].strip()):
            raise ValueError(key + " must be nonempty text")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.+_-]{0,31}", evidence.get("format", "").lower()):
        raise ValueError("format required")
    region = evidence.get("region")
    if region is not None and (not isinstance(region, str) or not region.strip()):
        raise ValueError("invalid region")
    now = now or datetime.now(timezone.utc)
    if not isinstance(now, datetime) or now.tzinfo is None:
        raise ValueError("timezone-aware clock required")
    resources = evidence.get("resources", {})
    if (not isinstance(resources, dict) or len(resources) > 32
            or any(not isinstance(k, str) or not re.fullmatch(r"[a-z][a-z0-9_]{0,63}", k)
                   or type(v) not in (int, float) or not 0 <= v <= 1e15 for k, v in resources.items())):
        raise ValueError("resources must be finite nonnegative quantities with explicit unit keys")
    purpose = evidence.get("rights", DEFAULT_PURPOSE)
    profiles = _catalog(_json(DEFAULT_CATALOG) if catalog is None else catalog)
    validator = Draft202012Validator(_json(SCHEMA_PATH), format_checker=FormatChecker())
    context = context if isinstance(context, dict) else {}
    layout = resolve_paths(project_root=project_root or PROJECT_ROOT)
    ranked, rejected = [], []

    for profile in sorted(profiles, key=lambda item: item["id"]):
        pid = profile["id"]
        blockers = []
        def block(code, detail):
            blockers.append({"code": code, "detail": detail})
        if not profile["default_enabled"]:
            block("DISABLED", "Enable only after qualification and approval; manual selection is not an override.")
        record = profile.get("evidence")
        if record is None:
            block("EVIDENCE_MISSING", "Installed/declaration state does not prove tested capability.")
        elif not _valid_record(record, validator):
            block("EVIDENCE_INVALID", "Record does not satisfy the profile evidence schema.")
        else:
            if not _fresh(record, now):
                block("EVIDENCE_EXPIRED_OR_FUTURE", "Refresh the current probe and all condition receipts.")
            versions = context.get("versions", {})
            current = versions.get(pid, {}) if isinstance(versions, dict) else {}
            current = current if isinstance(current, dict) else {}
            expected = {"profile_id": pid, "repo_sha": context.get("repo_sha"), "os": context.get("os"),
                        "host_version": current.get("host"), "adapter_version": current.get("adapter")}
            for key, value in expected.items():
                if not value or record[key] != value:
                    block("BINDING_MISMATCH", key + " does not match the current dispatch context.")
            if record["level"] not in ("E2", "E3", "E4", "E5"):
                block("UNTESTED", "E0/E1 is not a functional runtime test.")
            for key in ("launch", "readback", "rollback"):
                if record[key] != "PASS":
                    block(key.upper() + "_" + record[key], "A successful " + key + " receipt is required.")
            for key, condition in record["conditions"].items():
                if not _fresh(condition, now):
                    block(key.upper() + "_EXPIRED_OR_FUTURE", "Refresh this condition independently of the host probe.")
                if condition["status"] != "PASS":
                    block(key.upper() + "_" + condition["status"], condition["source"])
                if not _artifact_ok(condition["receipt"], layout):
                    block(key.upper() + "_RECEIPT_INVALID", "Condition evidence is missing, changed or outside the evidence root.")
            if purpose not in record["purposes"]:
                block("PURPOSE_NOT_AUTHORIZED", "No verified permission for the exact requested purpose.")
            if region is None or region not in record["regions"]:
                block("REGION_NOT_AUTHORIZED", "Current region is unknown or not covered.")
            for key, required in resources.items():
                capacity = record.get("resource_capacity", {}).get(key)
                if capacity is None or not required <= capacity <= 1e15:
                    block("RESOURCE_CAPACITY", key + " is unknown or insufficient for the request.")
            matches = [c for c in record["capabilities"] if c["format"] == evidence["format"].lower()
                       and c["operation"] == evidence.get("operation", "export")]
            if not matches:
                block("CAPABILITY_UNTESTED", "No current test of this format and operation.")
            elif not any((not evidence.get("editable", False) or c["editable"])
                         and (not evidence.get("offline", False) or c["offline"]) for c in matches):
                block("CAPABILITY_CONSTRAINT", "No matching test jointly proves editability and offline requirements.")
            for key in ("fixture", "artifact"):
                if not _artifact_ok(record[key], layout):
                    block("ARTIFACT_INVALID", key + " is missing, changed or outside the evidence root.")
            if profile["kind"] == "model":
                digest = profile.get("model_sha256")
                if not isinstance(digest, str) or not HASH.fullmatch(digest) or digest != record.get("model_sha256"):
                    block("MODEL_INTEGRITY_UNKNOWN", "A verified nonzero checksum must match the configured model.")
        if blockers:
            rejected.append({"profile": pid, "blockers": blockers,
                             "reasons": [b["code"] + ": " + b["detail"] for b in blockers],
                             "validation_steps": list(STEPS)})
            continue
        preference = profile.get("preference")
        score, score_reason = 100, "Equal priority; no verified cost or performance preference."
        if isinstance(preference, dict) and _fresh(preference, now):
            proposed = preference.get("score")
            if type(proposed) in (int, float) and 0 <= proposed <= 100 and isinstance(preference.get("source"), str) and preference["source"].strip():
                score, score_reason = proposed, preference["source"]
        ranked.append({"profile": pid, "score": score, "score_reason": score_reason,
                       "evidence_level": record["level"], "expires_at": record["expires_at"]})
    ranked.sort(key=lambda item: (-item["score"], item["profile"]))
    selected = ranked[0]["profile"] if ranked else None
    manual = None
    if "manual_profile" in evidence:
        pid = evidence["manual_profile"]
        qualified = any(row["profile"] == pid for row in ranked)
        selected = pid if qualified else None
        manual = {"profile": pid, "qualified": qualified,
                  "validation_steps": [] if qualified else list(STEPS)}
    return {"ranked": ranked, "rejected": rejected, "selected": selected, "manual": manual,
            "purpose": purpose, "execution_authorized": False}
