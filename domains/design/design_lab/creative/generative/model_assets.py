# SPDX-License-Identifier: MIT
"""DL-P0-091 Model as external asset: declare, verify, resolve, fail closed.

Model weights are never bundled into this repository. A model is an external
asset declared by an alias (``model-library``, ``design-toolchain``, ...), with
expected files, digests and a licence. The resolver refuses anything that is not
qualified — unknown, unhashed, licence-unclear or hardware-exceeding models all
fail closed rather than silently falling back to a smaller model.

The stage vocabulary is the one the repository already uses in
``design_lab.analysis.model_manifest`` so a model cannot be "verified" twice
under two different meanings.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from jsonschema import Draft202012Validator

from ...runtime.paths import PathPolicyError, PROJECT_ROOT, resolve_paths
from .errors import GenerativeError

SCHEMA = PROJECT_ROOT / "design-lab/schemas/generative-model-asset.schema.json"
SCHEMA_VERSION = "design-lab/generative-model-asset/v1"
STATES = ("DECLARED", "PRESENT_UNVERIFIED", "HASH_VERIFIED", "LICENSE_CLEARED", "QUALIFIED", "BLOCKED")
MACHINE_STATES = ("ABSENT", "METADATA_ONLY", "WEIGHTS_COMPLETE", "LOAD_VERIFIED", "INFERENCE_VERIFIED")
# Repo-owned root: models staged under .project-local are project assets, not
# external shared inputs, but they resolve through the same alias discipline.
PROJECT_LOCAL_ALIAS = "project-local"
PROJECT_LOCAL_PREFIX = ".project-local/"


def _schema() -> dict:
    return json.loads(SCHEMA.read_text(encoding="utf-8"))


def _require(condition, message):
    if not condition:
        raise GenerativeError(message)


def model_entry(*, model_id: str, family: str, source: dict, root_alias: str, files, state: str,
                rights: dict, hardware: dict, machine_state: str = "ABSENT",
                default_enabled: bool = False, notes: str = "") -> dict:
    """Build and validate one registry entry (raises instead of guessing)."""
    entry = {"schemaVersion": SCHEMA_VERSION, "model_id": model_id, "family": family,
             "source": dict(source), "root_alias": root_alias, "files": [dict(item) for item in files],
             "state": state, "machine_state": machine_state, "rights": dict(rights),
             "hardware": dict(hardware), "default_enabled": bool(default_enabled), "notes": notes}
    errors = list(Draft202012Validator(_schema()).iter_errors(entry))
    if errors:
        raise GenerativeError(f"model entry violates its schema: {errors[0].message}")
    validate_entry(entry)
    return entry


def validate_entry(entry: dict) -> None:
    """Semantic rules the schema cannot express."""
    state = entry["state"]
    _require(state in STATES, f"unknown model state: {state!r}")
    machine_state = entry["machine_state"]
    _require(machine_state in MACHINE_STATES, f"unknown machine state: {machine_state!r}")
    if entry["default_enabled"]:
        _require(state == "QUALIFIED",
                 "default_enabled requires a QUALIFIED model; an unqualified model must stay disabled")
    if state == "BLOCKED":
        _require(not entry["default_enabled"], "a licence-blocked model must not be enabled by default")
    if state in {"HASH_VERIFIED", "LICENSE_CLEARED", "QUALIFIED"}:
        _require(any(item.get("sha256") for item in entry["files"]),
                 f"{state} requires at least one recorded file digest")
    if state == "QUALIFIED":
        _require(entry["rights"].get("commercial_use") != "UNKNOWN",
                 "QUALIFIED requires an adjudicated commercial-use position")
        _require(entry["rights"].get("license_id") not in (None, "", "unverified"),
                 "QUALIFIED requires a named licence")
        _require(machine_state in {"LOAD_VERIFIED", "INFERENCE_VERIFIED"},
                 "QUALIFIED requires at least LOAD_VERIFIED machine evidence")
    for item in entry["files"]:
        digest = item.get("sha256")
        if digest is not None:
            _require(isinstance(digest, str) and len(digest) == 71 and digest.startswith("sha256:")
                     and digest[7:] == digest[7:].lower() and digest != "sha256:" + "0" * 64,
                     f"file {item.get('path')!r} digest must be a nonzero sha256:<64 lowercase hex>")


def validate_registry(registry: dict) -> dict:
    _require(isinstance(registry, dict), "registry must be an object")
    _require(registry.get("schemaVersion") == "design-lab/generative-model-registry/v1",
             "unsupported model registry schemaVersion")
    entries = registry.get("models")
    _require(isinstance(entries, list), "registry requires a models array")
    seen = set()
    for entry in entries:
        validate_entry(entry)
        _require(entry["model_id"] not in seen, f"duplicate model id {entry['model_id']}")
        seen.add(entry["model_id"])
    return {"schemaVersion": registry["schemaVersion"], "count": len(entries),
            "model_ids": sorted(seen), "enabled": sorted(e["model_id"] for e in entries if e["default_enabled"])}


def declared_path(entry: dict, file_entry: dict, *, project_root=None):
    """Resolve an alias-relative file path without touching the filesystem.

    Traversal, absolute paths and unknown aliases are refused: an external asset
    declaration never points outside its declared root.
    """
    alias = entry["root_alias"]
    relative = file_entry["path"]
    _require(isinstance(relative, str) and relative and not relative.startswith(("/", "\\")),
             "declared file paths are relative to the alias root")
    _require(":" not in relative and ".." not in relative.split("/") and ".." not in relative.split("\\"),
             f"declared file path escapes its alias root: {relative!r}")
    try:
        layout = resolve_paths(project_root=project_root)
    except PathPolicyError as exc:
        raise GenerativeError(str(exc)) from exc
    roots = layout.shared_inputs
    if alias == PROJECT_LOCAL_ALIAS:
        root = Path(layout.local_root)
    else:
        _require(alias in roots, f"unknown path alias {alias!r}; declared aliases: "
                                 f"{sorted([*roots, PROJECT_LOCAL_ALIAS])}")
        root = Path(roots[alias])
    target = (root / relative).resolve()
    _require(target.is_relative_to(root.resolve()) or target == root.resolve(),
             f"declared file path escapes its alias root: {relative!r}")
    return target


def present_files(entry: dict, *, project_root=None) -> list:
    """Which declared files exist on disk. Read-only; nothing is opened or hashed."""
    result = []
    for item in entry["files"]:
        try:
            path = declared_path(entry, item, project_root=project_root)
        except GenerativeError as exc:
            result.append({"path": item["path"], "present": False, "reason": str(exc)})
            continue
        result.append({"path": item["path"], "present": path.is_file(),
                       "bytes": path.stat().st_size if path.is_file() else None})
    return result


def hash_file(path, *, limit_bytes=8 * 1024 * 1024 * 1024) -> str:
    """Read-only streaming digest; refuses oversized or zero-byte files."""
    size = path.stat().st_size
    _require(size > 0, f"refusing to hash an empty file: {path.name}")
    _require(size <= limit_bytes, f"refusing to hash a file above the limit: {path.name}")
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return "sha256:" + digest.hexdigest()


def _reason(entry: dict, *, require_present: bool, project_root) -> str:
    if entry["state"] == "BLOCKED":
        return "BLOCKED_BY_LICENSE"
    if entry["rights"].get("commercial_use") == "UNKNOWN":
        return "RIGHTS_UNKNOWN"
    if entry["state"] != "QUALIFIED":
        return f"NOT_QUALIFIED:{entry['state']}"
    if entry["hardware"].get("verdict") == "EXCEEDS":
        return "HARDWARE_INSUFFICIENT"
    if require_present and not all(item["present"] for item in present_files(entry, project_root=project_root)):
        return "FILES_MISSING"
    return ""


def resolve(registry: dict, model_id: str, *, require_present: bool = False, project_root=None) -> dict:
    """Return an entry only when it is qualified; otherwise fail closed."""
    validate_registry(registry)
    entry = next((item for item in registry["models"] if item["model_id"] == model_id), None)
    if entry is None:
        raise GenerativeError(f"unknown model {model_id!r}; the resolver does not fall back to another model")
    reason = _reason(entry, require_present=require_present, project_root=project_root)
    if reason:
        raise GenerativeError(f"model {model_id!r} cannot be resolved: {reason}")
    return entry


def default_enabled(entry: dict) -> bool:
    """Enablement is derived from qualification, never from presence."""
    validate_entry(entry)
    return entry["state"] == "QUALIFIED" and bool(entry["default_enabled"])


def registry_report(registry: dict) -> dict:
    validate_registry(registry)
    refused = {}
    for entry in registry["models"]:
        reason = _reason(entry, require_present=False, project_root=None)
        if reason:
            refused[entry["model_id"]] = reason
    return {"count": len(registry["models"]),
            "by_state": {state: sum(1 for e in registry["models"] if e["state"] == state) for state in STATES},
            "enabled": sorted(e["model_id"] for e in registry["models"] if default_enabled(e)),
            "refused": refused}


# --------------------------------------------------------------------------- #
# Join with the model radar (DL-P1-100)
# --------------------------------------------------------------------------- #
# The radar registry is the single place where a model's presence, licence and
# hardware position are recorded. This module is the runtime resolver, so it
# projects radar entries instead of maintaining a second registry.
RADAR_TO_ASSET_STATE = {
    "QUALIFIED_LOCAL": "QUALIFIED",
    "BLOCKED_BY_LICENSE": "BLOCKED",
    "REJECTED": "BLOCKED",
    "EVALUATING": "DECLARED",
    "WATCH": "DECLARED",
}
# The radar and this contract grew their own family spellings; the join maps
# them explicitly instead of letting either side drift silently.
RADAR_TO_ASSET_FAMILY = {
    "3d": "three-d",
    "upscaling": "upscale",
    "vision-encoding": "embedding",
    "vision-language": "vision-language",
}


def _split_alias(local_path) -> tuple:
    if isinstance(local_path, str) and local_path.startswith(PROJECT_LOCAL_PREFIX):
        return PROJECT_LOCAL_ALIAS, local_path[len(PROJECT_LOCAL_PREFIX):]
    if not isinstance(local_path, str) or ":" not in local_path:
        raise GenerativeError(
            "radar local_path must be '<alias>:<relative path>' or '.project-local/<path>' to resolve "
            f"as an external asset; got {local_path!r}")
    alias, _, relative = local_path.partition(":")
    if not alias or not relative:
        raise GenerativeError(f"radar local_path is incomplete: {local_path!r}")
    return alias, relative


def from_radar_entry(entry: dict) -> dict:
    """Project one model-radar entry into a resolvable model-asset entry."""
    if not isinstance(entry, dict) or "model_id" not in entry:
        raise GenerativeError("radar entry must be an object with a model_id")
    radar_state = entry.get("radar_state")
    if radar_state not in RADAR_TO_ASSET_STATE:
        raise GenerativeError(f"unknown radar_state: {radar_state!r}")
    hashes = [value for value in entry.get("weights_sha256") or () if value]
    local_path = entry.get("local_path")
    if local_path is None:
        alias = "model-library"
        files = [{"path": f"UNRESOLVED/{entry['model_id']}", "sha256": None, "bytes": None}]
    else:
        alias, relative = _split_alias(local_path)
        files = [{"path": relative, "sha256": hashes[0] if hashes else None, "bytes": entry.get("bytes")}]
    source = entry.get("source") if isinstance(entry.get("source"), dict) else {}
    raw_family = entry.get("family") or "other"
    family = RADAR_TO_ASSET_FAMILY.get(raw_family, raw_family)
    if family not in ("image-generation", "image-edit", "upscale", "segmentation", "detection", "ocr",
                      "asr", "tts", "audio-generation", "video-generation", "three-d", "embedding",
                      "vision-language", "other"):
        raise GenerativeError(
            f"radar family {raw_family!r} has no counterpart in the model-asset contract; map it "
            "explicitly rather than letting the two vocabularies drift")
    rights_source = entry.get("rights") if isinstance(entry.get("rights"), dict) else {}
    rights = {"license_id": rights_source.get("license_id") or "unverified",
              "territory_limits": list(rights_source.get("territory_limits") or ()),
              "commercial_use": rights_source.get("commercial_use") or "UNKNOWN"}
    hardware = dict(entry.get("hardware_fit") or {"vram_gib_required": None, "verdict": "UNKNOWN"})
    notes = " | ".join(part for part in (
        entry.get("notes"), entry.get("blocking_reason"), f"radar_state={radar_state}",
        f"radar_family={raw_family}" if family != raw_family else None,
        f"evidence_ref={entry['evidence_ref']}" if entry.get("evidence_ref") else None,
        f"source={source.get('ref')}" if source.get("ref") else None,
    ) if part)
    return model_entry(
        model_id=entry["model_id"], family=family,
        source={"kind": source.get("kind", "unknown"), "ref": source.get("ref", entry["model_id"]),
                "license_id": source.get("license_id") or "unverified"},
        root_alias=alias, files=files, state=RADAR_TO_ASSET_STATE[radar_state],
        machine_state=entry.get("machine_state") or "ABSENT", rights=rights, hardware=hardware,
        # Qualification is never invented here: the radar stays the source, and a
        # licence-blocked entry can never become enabled through this projection.
        default_enabled=False, notes=notes)


def registry_from_radar(radar: dict) -> dict:
    """Build the resolver's view of the radar registry; the radar stays the source."""
    if not isinstance(radar, dict) or not isinstance(radar.get("entries"), list):
        raise GenerativeError("radar registry must expose an entries array")
    registry = {"schemaVersion": "design-lab/generative-model-registry/v1",
                "models": [from_radar_entry(entry) for entry in radar["entries"]]}
    validate_registry(registry)
    return registry
