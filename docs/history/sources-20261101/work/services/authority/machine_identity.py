#!/usr/bin/env python3
"""Report and explicitly register a privacy-preserving project machine identity.

The identity is a random per-project installation UUID. It is not derived from
hardware, Windows machine GUIDs, MAC addresses, serial numbers, usernames,
credentials, or provider state. Status is read-only by default; both local
initialization and tracked registry updates require an explicit write flag.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "worklab/project-machine-identity/v1"
REGISTRY_SCHEMA_VERSION = "worklab/project-machine-registry/v1"
LOCAL_STATE_RELATIVE = Path(".hermes/task-runtime/machine-identity.json")
REGISTRY_RELATIVE = Path("config/machine-registry.json")
PROFILE_RELATIVE = Path("config/user-environment-profile.json")
UUID_RE = re.compile(r"^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$")
SENSITIVE_PATH_PARTS = {
    ".env", "auth", "auth.json", "credential", "credentials", "cookie",
    "cookies", "memory", "private", "secret", "secrets", "session",
    "sessions", "state.db", "token", "tokens",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _reject_protected_drive(path: Path) -> None:
    value = str(path).replace("/", "\\")
    if re.match(r"^[EF]:\\", value, flags=re.IGNORECASE):
        raise ValueError("E: and F: are protected drives and cannot be accessed by machine identity diagnostics")


def _reject_sensitive_path(path: Path) -> None:
    parts = {part.lower() for part in path.parts}
    if parts & SENSITIVE_PATH_PARTS or path.name.lower().endswith(".env"):
        raise ValueError("machine identity diagnostics cannot access credential or private-state paths")


def _is_reparse_point(path: Path) -> bool:
    if path.is_symlink():
        return True
    if os.name == "nt":
        try:
            return bool(path.stat().st_file_attributes & stat.FILE_ATTRIBUTE_REPARSE_POINT)
        except AttributeError:
            return False
        except FileNotFoundError:
            return False
    return False


def _reject_reparse_ancestors(project_root: Path, path: Path) -> None:
    current = path
    while True:
        try:
            is_reparse = _is_reparse_point(current)
        except OSError as exc:
            raise ValueError("machine identity path could not be inspected safely") from exc
        if current != project_root and is_reparse:
            raise ValueError("machine identity path cannot traverse a symlink or reparse point")
        if current == project_root:
            return
        if project_root not in current.parents:
            raise ValueError("machine identity path escaped the project root")
        current = current.parent


def _require_project_root(project_root: Path) -> Path:
    """Accept only a direct Git root with this module's declared profile."""
    root = Path(os.path.abspath(str(project_root)))
    _reject_protected_drive(root)
    if not root.is_dir():
        raise ValueError("project root does not exist")
    if _is_reparse_point(root):
        raise ValueError("project root cannot be a symlink or reparse point")
    _reject_reparse_ancestors(root, root)
    if not (root / ".git").is_dir() or not (root / PROFILE_RELATIVE).is_file():
        raise ValueError("project root must contain .git and the declared user environment profile")
    return root


def _profile_digest(project_root: Path) -> str:
    profile = _project_path(project_root, PROFILE_RELATIVE)
    _reject_protected_drive(profile)
    if not profile.is_file():
        return "PROFILE_NOT_FOUND"
    return hashlib.sha256(profile.read_bytes()).hexdigest()


def _read_json(path: Path, *, default: Any) -> Any:
    _reject_protected_drive(path)
    _reject_sensitive_path(path)
    if not path.is_file():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_machine_id(value: Any) -> str:
    if not isinstance(value, str) or not UUID_RE.fullmatch(value.lower()):
        raise ValueError("invalid project machine identity")
    return value.lower()


def _project_root(value: str | None) -> Path:
    raw_root = Path(value or Path.cwd())
    _reject_protected_drive(raw_root)
    root = raw_root.resolve()
    _reject_protected_drive(root)
    if not root.is_dir():
        raise ValueError(f"project root does not exist: {root}")
    # The documented invocation runs from this module directory. Resolve the
    # enclosing WORK-LAB Git root without inspecting any user-level location.
    candidate = root
    while candidate != candidate.parent:
        if (candidate / ".git").exists() and (candidate / PROFILE_RELATIVE).is_file():
            root = candidate
            break
        candidate = candidate.parent
    return _require_project_root(root)


def _project_path(project_root: Path, candidate: Path) -> Path:
    # Keep symlink/reparse components visible. ``Path.resolve()`` would erase
    # the evidence before the ancestor check below; abspath normalizes ``..``
    # without following links.
    path = Path(os.path.abspath(str(candidate if candidate.is_absolute() else project_root / candidate)))
    _reject_protected_drive(path)
    try:
        path.relative_to(project_root)
    except ValueError as exc:
        raise ValueError("machine identity paths must stay inside the project root") from exc
    _reject_reparse_ancestors(project_root, path)
    return path


def _identity_path(project_root: Path, identity_file: Path | None, scope: str) -> Path:
    if scope == "project":
        if identity_file is not None:
            raise ValueError("--identity-file is only valid with --scope device")
        path = _project_path(project_root, LOCAL_STATE_RELATIVE)
    elif scope == "device":
        if identity_file is None:
            raise ValueError("device scope requires an explicit --identity-file")
        path = _project_path(project_root, identity_file)
    else:
        raise ValueError("scope must be project or device")
    _reject_protected_drive(path)
    return path


def load_local_identity(
    project_root: Path,
    identity_file: Path | None = None,
    *,
    scope: str = "project",
) -> dict[str, Any] | None:
    path = _identity_path(project_root, identity_file, scope)
    raw = _read_json(path, default=None)
    if raw is None:
        return None
    if raw.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported local machine identity schema")
    machine_id = _validate_machine_id(raw.get("machine_id"))
    expected_scope = f"{scope}_local_installation"
    if raw.get("identity_scope") != expected_scope:
        raise ValueError("unsupported machine identity scope")
    return {
        "schema_version": SCHEMA_VERSION,
        "machine_id": machine_id,
        "identity_scope": raw["identity_scope"],
        "created_at": raw.get("created_at", "UNKNOWN"),
        "profile_digest": raw.get("profile_digest", "UNKNOWN"),
    }


def load_registry(project_root: Path, registry_path: Path | None = None) -> list[dict[str, str]]:
    path = _project_path(project_root, registry_path or REGISTRY_RELATIVE)
    raw = _read_json(path, default={"schema_version": REGISTRY_SCHEMA_VERSION, "machines": []})
    if raw.get("schema_version") != REGISTRY_SCHEMA_VERSION:
        raise ValueError("unsupported machine registry schema")
    machines = raw.get("machines", [])
    if not isinstance(machines, list):
        raise ValueError("machine registry machines must be a list")
    result: list[dict[str, str]] = []
    for item in machines:
        if not isinstance(item, dict):
            raise ValueError("machine registry entry must be an object")
        result.append({
            "machine_id": _validate_machine_id(item.get("machine_id")),
            "identity_scope": str(item.get("identity_scope", "project_local_installation")),
            "label": str(item.get("label", "UNLABELLED")),
            "first_seen": str(item.get("first_seen", "UNKNOWN")),
        })
    return result


def status(
    project_root: Path,
    registry_path: Path | None = None,
    identity_file: Path | None = None,
    *,
    scope: str = "project",
) -> dict[str, Any]:
    project_root = _require_project_root(project_root)
    local = load_local_identity(project_root, identity_file, scope=scope)
    registry = load_registry(project_root, registry_path)
    profile_digest = _profile_digest(project_root)
    if local is None:
        return {
            "schema_version": SCHEMA_VERSION,
            "identity_scope": f"{scope}_local_installation",
            "machine_state": "IDENTITY_NOT_INITIALIZED",
            "machine_id": None,
            "registry_match": False,
            "profile_revision": "UNKNOWN",
            "profile_digest": profile_digest,
            "next_action": "review_then_init_local_identity",
        }
    known = next(
        (
            item
            for item in registry
            if item["machine_id"] == local["machine_id"]
            and item["identity_scope"] == local["identity_scope"]
        ),
        None,
    )
    profile_revision = "MATCH" if local["profile_digest"] == profile_digest else "PROFILE_CHANGED"
    if known is None:
        machine_state = "NEW_MACHINE"
        next_action = "review_then_record_machine"
    elif profile_revision == "PROFILE_CHANGED":
        machine_state = "CONFIGURATION_REVIEW_REQUIRED"
        next_action = "review_profile_and_run_plan_verify"
    else:
        machine_state = "KNOWN_MACHINE"
        next_action = "no_machine_registration_action"
    return {
        "schema_version": SCHEMA_VERSION,
        "identity_scope": local["identity_scope"],
        "machine_state": machine_state,
        "machine_id": local["machine_id"],
        "registry_match": known is not None,
        "registry_label": known["label"] if known else None,
        "profile_revision": profile_revision,
        "profile_digest": profile_digest,
        "next_action": next_action,
    }


def init_local_identity(
    project_root: Path,
    *,
    write: bool,
    identity_file: Path | None = None,
    scope: str = "project",
) -> dict[str, Any]:
    project_root = _require_project_root(project_root)
    path = _identity_path(project_root, identity_file, scope)
    existing = load_local_identity(project_root, identity_file, scope=scope)
    if existing is not None:
        return {"status": "ALREADY_INITIALIZED", **existing}
    result = {
        "schema_version": SCHEMA_VERSION,
        "identity_scope": f"{scope}_local_installation",
        "machine_id": str(uuid.uuid4()),
        "created_at": _utc_now(),
        "profile_digest": _profile_digest(project_root),
    }
    return {
        "status": "PLAN_ONLY",
        **result,
        "path": str(path),
        "next_action": "create_the_identity_file_through_a_reviewed_project_local_workflow",
    }


def record_machine(
    project_root: Path,
    *,
    label: str,
    write: bool,
    registry_path: Path | None = None,
    identity_file: Path | None = None,
    scope: str = "project",
) -> dict[str, Any]:
    project_root = _require_project_root(project_root)
    local = load_local_identity(project_root, identity_file, scope=scope)
    if local is None:
        raise ValueError("initialize the local identity first; no machine ID was generated")
    if not label or "\n" in label or "\r" in label or len(label) > 80:
        raise ValueError("label must be a short single-line review label")
    path = _project_path(project_root, registry_path or REGISTRY_RELATIVE)
    machines = load_registry(project_root, registry_path)
    if any(
        item["machine_id"] == local["machine_id"]
        and item.get("identity_scope", "project_local_installation") == local["identity_scope"]
        for item in machines
    ):
        return {"status": "ALREADY_REGISTERED", "machine_id": local["machine_id"], "label": label}
    entry = {
        "machine_id": local["machine_id"],
        "identity_scope": local["identity_scope"],
        "label": label,
        "first_seen": _utc_now(),
    }
    result = {
        "status": "PLAN_ONLY",
        "entry": entry,
        "path": str(REGISTRY_RELATIVE),
        "next_action": "add_the_entry_through_a_reviewed_git_change",
    }
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "init", "record"))
    parser.add_argument("--project-root", type=Path, default=Path.cwd())
    parser.add_argument("--registry", type=Path)
    parser.add_argument("--identity-file", type=Path)
    parser.add_argument("--scope", choices=("project", "device"), default="project")
    parser.add_argument("--label")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args(argv)
    root = _project_root(str(args.project_root))
    if args.command == "status":
        result = status(root, args.registry, args.identity_file, scope=args.scope)
    elif args.command == "init":
        result = init_local_identity(root, write=args.write, identity_file=args.identity_file, scope=args.scope)
    else:
        if args.label is None:
            parser.error("record requires --label")
        result = record_machine(
            root,
            label=args.label,
            write=args.write,
            registry_path=args.registry,
            identity_file=args.identity_file,
            scope=args.scope,
        )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
