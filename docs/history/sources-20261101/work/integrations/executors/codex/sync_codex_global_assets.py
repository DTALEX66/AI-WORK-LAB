from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import json
import os
import re
import shutil
import tempfile
import tomllib
from pathlib import Path
from typing import Any

GUIDANCE_BEGIN = "<!-- BEGIN WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY -->"
GUIDANCE_END = "<!-- END WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY -->"
CONFIG_BEGIN = "# BEGIN WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY"
CONFIG_END = "# END WORKFLOW-ASSISTANCE MANAGED CODEX OVERLAY"
STATE_FILE = ".workflow-assistance-state.json"
LOCK_FILE = ".workflow-assistance-sync.lock"
RULE_RELATIVE = Path("rules/workflow-assistance.rules")
MANAGED_CONFIG: dict[str, Any] = {
    "approval_policy": "on-request",
    "sandbox_mode": "workspace-write",
    "project_doc_max_bytes": 65536,
}
VERSION = 3
NO_EXPECTATION = object()


class ManagedConflict(RuntimeError):
    pass


def _sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _plan_digest(plan: dict[str, Any]) -> str:
    """Return a stable, redacted approval binding for a dry-run write set."""

    reviewed = {
        key: plan[key]
        for key in (
            "target_scope_digest",
            "managed_config_fields",
            "preserved_user_config_fields",
            "actions",
            "write_set_count",
        )
    }
    encoded = json.dumps(reviewed, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return _sha256_bytes(encoded)


def _target_scope_digest(codex_home: Path, agent_home: Path, source_root: Path) -> str:
    """Bind approval to a target/source triple without disclosing local paths."""

    payload = "\0".join(
        str(Path(path).resolve()) for path in (codex_home, agent_home, source_root)
    ).encode("utf-8")
    return _sha256_bytes(payload)


def _tree_hash(root: Path) -> str:
    digest = hashlib.sha256()
    if not root.is_dir():
        raise FileNotFoundError(root)
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def _read_optional_bytes(path: Path) -> bytes | None:
    return path.read_bytes() if path.exists() else None


def _atomic_write(
    path: Path,
    data: bytes,
    *,
    expected_current: bytes | None | object = NO_EXPECTATION,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        if expected_current is not NO_EXPECTATION and _read_optional_bytes(path) != expected_current:
            raise ManagedConflict(f"concurrent modification detected: {path}")
        os.replace(temporary, path)
    except BaseException:
        try:
            os.unlink(temporary)
        except FileNotFoundError:
            pass
        raise


@contextmanager
def _operation_lock(codex_home: Path):
    """Serialize cooperating synchronizers without reading Codex private state."""

    codex_home.mkdir(parents=True, exist_ok=True)
    path = codex_home / LOCK_FILE
    _assert_safe_managed_path(codex_home, path)
    try:
        descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError as exc:
        raise ManagedConflict(f"another overlay operation is active: {path}") from exc
    try:
        with os.fdopen(descriptor, "wb") as stream:
            stream.write(b"workflow-assistance overlay operation\n")
            stream.flush()
            os.fsync(stream.fileno())
        yield
    finally:
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _managed_block(text: str, begin: str, end: str) -> str | None:
    start = text.find(begin)
    finish = text.find(end)
    if start == -1 and finish == -1:
        return None
    if start == -1 or finish == -1 or finish < start:
        raise ManagedConflict(f"malformed managed block: {begin}")
    if text.find(begin, start + len(begin)) != -1 or text.find(end, finish + len(end)) != -1:
        raise ManagedConflict(f"duplicate managed block: {begin}")
    return text[start : finish + len(end)]


def _block_hash(block: str) -> str:
    # Codex Desktop 重写 config.toml 时会写 CRLF 行尾；归一化后 hash 与 LF 一致，
    # 避免 "block changed after apply" 误判（2026-08-14 DESIGN-LAB 交接复核：
    # CRLF 块 hash 50d589cb vs LF state c2e56fdf → fail-closed BLOCK）。
    normalized = block.replace("\r\n", "\n").replace("\r", "\n")
    return _sha256_bytes(normalized.encode("utf-8"))


def _is_link_or_reparse(path: Path) -> bool:
    try:
        stat_result = path.lstat()
    except FileNotFoundError:
        return False
    return path.is_symlink() or bool(getattr(stat_result, "st_file_attributes", 0) & 0x400)


def _assert_safe_managed_path(root: Path, target: Path) -> None:
    """Reject descendant symlinks/junctions that escape a declared managed root."""

    declared_root = Path(os.path.abspath(root))
    declared_target = Path(os.path.abspath(target))
    try:
        declared_target.relative_to(declared_root)
    except ValueError as exc:
        raise ManagedConflict(f"managed target escapes declared root: {target}") from exc
    current = declared_target
    while current != declared_root:
        if _is_link_or_reparse(current):
            raise ManagedConflict(f"managed target crosses a symlink or junction: {current}")
        current = current.parent


def _remove_managed_block(text: str, begin: str, end: str) -> tuple[str, bool]:
    start = text.find(begin)
    finish = text.find(end)
    if start == -1 and finish == -1:
        return text, False
    if start == -1 or finish == -1 or finish < start:
        raise ManagedConflict(f"malformed managed block: {begin}")
    if text.find(begin, start + len(begin)) != -1 or text.find(end, finish + len(end)) != -1:
        raise ManagedConflict(f"duplicate managed block: {begin}")
    finish += len(end)
    while finish < len(text) and text[finish] in "\r\n":
        finish += 1
    base = (text[:start].rstrip() + "\n" + text[finish:].lstrip()).strip()
    return (base + "\n" if base else ""), True


def _render_guidance(existing: str, overlay: str) -> str:
    base, _ = _remove_managed_block(existing, GUIDANCE_BEGIN, GUIDANCE_END)
    # A reviewed universal block may already live outside the legacy overlay.
    # Move an identical block into the new overlay once; refuse divergent or
    # malformed blocks instead of silently erasing user-maintained content.
    begin = "## BEGIN UNIVERSAL_AGENT_CORE v1.0.0"
    end = "## END UNIVERSAL_AGENT_CORE v1.0.0"
    desired_core = _managed_block(overlay, begin, end)
    if desired_core is not None:
        current_core = _managed_block(base, begin, end)
        if current_core is not None:
            if current_core.strip() != desired_core.strip():
                raise ManagedConflict("universal core differs from reviewed overlay; review before apply")
            base, _ = _remove_managed_block(base, begin, end)
    block = f"{GUIDANCE_BEGIN}\n{overlay.strip()}\n{GUIDANCE_END}\n"
    return f"{base.rstrip()}\n\n{block}" if base.strip() else block


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    raise TypeError(f"unsupported managed TOML value: {type(value).__name__}")


def _expected_config_block(fields: list[str]) -> str:
    lines = [CONFIG_BEGIN]
    lines.extend(f"{key} = {_toml_value(MANAGED_CONFIG[key])}" for key in MANAGED_CONFIG if key in fields)
    lines.append(CONFIG_END)
    return "\n".join(lines)


def _expected_guidance_block(overlay: str) -> str:
    return f"{GUIDANCE_BEGIN}\n{overlay.strip()}\n{GUIDANCE_END}"


def _render_config(existing: str) -> tuple[str, list[str], dict[str, Any]]:
    base, _ = _remove_managed_block(existing, CONFIG_BEGIN, CONFIG_END)
    parsed = tomllib.loads(base) if base.strip() else {}
    appended: list[str] = []
    preserved: dict[str, Any] = {}
    for key, desired in MANAGED_CONFIG.items():
        if key in parsed:
            preserved[key] = parsed[key]
        else:
            appended.append(key)
    if not appended:
        return base, appended, preserved
    lines = [CONFIG_BEGIN]
    lines.extend(f"{key} = {_toml_value(MANAGED_CONFIG[key])}" for key in appended)
    lines.append(CONFIG_END)
    block = "\n".join(lines) + "\n"
    if not base.strip():
        rendered = block
    else:
        base_lines = base.rstrip().splitlines()
        first_table = next(
            (index for index, line in enumerate(base_lines) if line.lstrip().startswith("[")),
            len(base_lines),
        )
        before = "\n".join(base_lines[:first_table]).rstrip()
        after = "\n".join(base_lines[first_table:]).lstrip()
        sections = [section for section in (before, block.rstrip(), after) if section]
        rendered = "\n\n".join(sections) + "\n"
    tomllib.loads(rendered)
    return rendered, appended, preserved


def _load_state(codex_home: Path) -> dict[str, Any]:
    path = codex_home / STATE_FILE
    if not path.exists():
        return {}
    try:
        state = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ManagedConflict(f"invalid managed state: {path}") from exc
    if not isinstance(state, dict) or state.get("version") not in {1, 2, VERSION}:
        raise ManagedConflict(f"unsupported managed state: {path}")
    if not isinstance(state.get("target_hashes"), dict):
        raise ManagedConflict(f"incomplete managed state: {path}")
    if state.get("version") == 1 and "managed_skill_names" not in state:
        state["managed_skill_names"] = sorted(
            key.removeprefix("skills/")
            for key in state["target_hashes"]
            if isinstance(key, str) and key.startswith("skills/")
        )
    if not isinstance(state.get("managed_skill_names"), list) or not state["managed_skill_names"]:
        raise ManagedConflict(f"incomplete managed state: {path}")
    for name in state["managed_skill_names"]:
        if not isinstance(name, str) or not re.fullmatch(r"workflow-assistance-[a-z0-9-]+", name):
            raise ManagedConflict(f"invalid managed skill name in state: {path}")
    managed_fields = state.get("managed_config_fields", [])
    if (
        not isinstance(managed_fields, list)
        or len(managed_fields) != len(set(managed_fields))
        or any(field not in MANAGED_CONFIG for field in managed_fields)
    ):
        raise ManagedConflict(f"invalid managed config fields in state: {path}")
    expected_hash_keys = {RULE_RELATIVE.as_posix()} | {
        f"skills/{name}" for name in state["managed_skill_names"]
    }
    if set(state["target_hashes"]) != expected_hash_keys:
        raise ManagedConflict(f"incomplete target hashes in state: {path}")
    if any(
        not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
        for value in state["target_hashes"].values()
    ):
        raise ManagedConflict(f"invalid target hash in state: {path}")
    if state.get("version") == VERSION:
        if state.get("phase") not in {"applied", "applying", "rolling_back"}:
            raise ManagedConflict(f"invalid managed state phase: {path}")
        block_hashes = state.get("managed_block_hashes")
        if not isinstance(block_hashes, dict) or "AGENTS.md" not in block_hashes:
            raise ManagedConflict(f"incomplete managed block hashes: {path}")
        if managed_fields and "config.toml" not in block_hashes:
            raise ManagedConflict(f"incomplete managed config hash: {path}")
        if any(
            not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
            for value in block_hashes.values()
        ):
            raise ManagedConflict(f"invalid managed block hash: {path}")
        for key in ("previous_block_hashes", "previous_target_hashes"):
            previous = state.get(key, {})
            if not isinstance(previous, dict) or any(
                not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None
                for value in previous.values()
            ):
                raise ManagedConflict(f"invalid {key} in state: {path}")
    else:
        state.setdefault("phase", "applied")
    return state


def _skill_sources(source_root: Path) -> list[Path]:
    skill_root = source_root / "skills"
    skills = sorted(path.parent for path in skill_root.glob("workflow-assistance-*/SKILL.md"))
    if not skills:
        raise ManagedConflict(f"Codex skill pack incomplete: found {len(skills)}")
    return skills


def _current_block_hashes(config_text: str, guidance_text: str) -> dict[str, str]:
    hashes: dict[str, str] = {}
    config_block = _managed_block(config_text, CONFIG_BEGIN, CONFIG_END)
    guidance_block = _managed_block(guidance_text, GUIDANCE_BEGIN, GUIDANCE_END)
    if config_block is not None:
        hashes["config.toml"] = _block_hash(config_block)
    if guidance_block is not None:
        hashes["AGENTS.md"] = _block_hash(guidance_block)
    return hashes


def _validate_existing_ownership(
    state: dict[str, Any],
    config_text: str,
    guidance_text: str,
    guidance_overlay: str,
) -> dict[str, str]:
    """Prove managed mixed-ownership blocks have not been edited in place."""

    if state.get("phase") != "applied":
        raise ManagedConflict("incomplete overlay operation requires rollback before another plan/apply")
    try:
        tomllib.loads(config_text) if config_text.strip() else None
    except tomllib.TOMLDecodeError as exc:
        raise ManagedConflict("Codex config is invalid or contains duplicate top-level fields") from exc

    current = _current_block_hashes(config_text, guidance_text)
    managed_fields = state.get("managed_config_fields", [])
    legacy = state.get("version") != VERSION
    if managed_fields:
        actual = current.get("config.toml")
        if state.get("version") == VERSION:
            expected = state["managed_block_hashes"].get("config.toml")
        else:
            expected = _block_hash(_expected_config_block(managed_fields))
        if actual != expected:
            # Legacy v1/v2 states predate the managed config block hash. A
            # config rewrite (e.g. Codex Desktop regenerating config.toml) can
            # dissolve the block without user intent; _render_config only ever
            # appends fields the user has not set, so re-insertion cannot
            # overwrite user values. A present-but-mismatched block still
            # fails closed below.
            if not (legacy and actual is None):
                raise ManagedConflict("managed config block changed after apply")
    elif "config.toml" in current:
        raise ManagedConflict("unexpected managed config block for preserved user fields")

    actual_guidance = current.get("AGENTS.md")
    if state.get("version") == VERSION:
        expected_guidance = state["managed_block_hashes"].get("AGENTS.md")
    else:
        # Legacy v1/v2 states never recorded guidance hashes. Ownership is
        # proven by the managed markers, not by byte-equality with the
        # current source; requiring equality wedges migration whenever the
        # source advanced after the legacy apply. An unmarked block is user
        # content and still fails closed.
        expected_guidance = _block_hash(_expected_guidance_block(guidance_overlay))
    if actual_guidance != expected_guidance:
        if not (legacy and GUIDANCE_BEGIN in guidance_text and GUIDANCE_END in guidance_text):
            raise ManagedConflict("managed guidance block changed after apply")
    return current


def _preflight(codex_home: Path, agent_home: Path, source_root: Path, *, skills_only: bool = False) -> dict[str, Any]:
    guidance_source = source_root / "global-guidance.md"
    rules_source = source_root / RULE_RELATIVE
    if not guidance_source.is_file() or not rules_source.is_file():
        raise ManagedConflict("Codex asset source is incomplete")
    guidance_overlay = guidance_source.read_text(encoding="utf-8")
    _assert_safe_managed_path(codex_home, codex_home / STATE_FILE)
    state = _load_state(codex_home)
    if skills_only and (state.get("version") != VERSION or state.get("phase") != "applied"):
        raise ManagedConflict("skills-only sync requires an applied current ownership state")
    previous = state.get("target_hashes", {}) if isinstance(state.get("target_hashes", {}), dict) else {}

    config_path = codex_home / "config.toml"
    _assert_safe_managed_path(codex_home, config_path)
    config_original_bytes = None if skills_only else _read_optional_bytes(config_path)
    config_text = config_original_bytes.decode("utf-8") if config_original_bytes is not None else ""
    guidance_path = codex_home / "AGENTS.md"
    _assert_safe_managed_path(codex_home, guidance_path)
    guidance_original_bytes = None if skills_only else _read_optional_bytes(guidance_path)
    guidance_text = guidance_original_bytes.decode("utf-8") if guidance_original_bytes is not None else ""
    previous_block_hashes: dict[str, str] = {}
    if state and not skills_only:
        previous_block_hashes = _validate_existing_ownership(
            state,
            config_text,
            guidance_text,
            guidance_overlay,
        )
    elif (
        CONFIG_BEGIN in config_text
        or CONFIG_END in config_text
        or GUIDANCE_BEGIN in guidance_text
        or GUIDANCE_END in guidance_text
    ):
        raise ManagedConflict("managed markers exist without an ownership state file")

    rules_target = codex_home / RULE_RELATIVE
    _assert_safe_managed_path(codex_home, rules_target)
    rules_current_bytes = None if skills_only else _read_optional_bytes(rules_target)
    if rules_target.exists() and not skills_only:
        if not state:
            raise ManagedConflict(f"unowned rule target already exists: {rules_target}")
        current = _sha256_bytes(rules_current_bytes or b"")
        source = _sha256_bytes(rules_source.read_bytes())
        old = previous.get(RULE_RELATIVE.as_posix())
        if current != source and current != old:
            raise ManagedConflict(f"user-owned rule conflict: {rules_target}")

    skills: list[dict[str, Any]] = []
    current_skill_names: set[str] = set()
    for source in _skill_sources(source_root):
        current_skill_names.add(source.name)
        target = agent_home / "skills" / source.name
        _assert_safe_managed_path(agent_home, target)
        source_hash = _tree_hash(source)
        relative = f"skills/{source.name}"
        current_hash: str | None = None
        if target.exists():
            if not state:
                raise ManagedConflict(f"unowned skill target already exists: {target}")
            current_hash = _tree_hash(target)
            old_hash = previous.get(relative)
            if current_hash != source_hash and current_hash != old_hash:
                raise ManagedConflict(f"user-owned skill conflict: {target}")
        skills.append(
            {
                "name": source.name,
                "source": source,
                "target": target,
                "hash": source_hash,
                "current_hash": current_hash,
            }
        )

    retired_skills: list[dict[str, Any]] = []
    for name in sorted(set(state.get("managed_skill_names", [])) - current_skill_names):
        target = agent_home / "skills" / name
        _assert_safe_managed_path(agent_home, target)
        expected = previous.get(f"skills/{name}")
        current_hash = _tree_hash(target) if target.exists() else None
        if not expected or (current_hash is not None and current_hash != expected):
            raise ManagedConflict(f"retired managed skill changed after apply: {target}")
        retired_skills.append(
            {"name": name, "target": target, "hash": expected, "current_hash": current_hash}
        )

    rendered_config, appended_fields, preserved_fields = _render_config(config_text)
    rendered_guidance = _render_guidance(guidance_text, guidance_overlay)
    if skills_only:
        rendered_config = config_text
        rendered_guidance = guidance_text
        appended_fields = state.get("managed_config_fields", [])
        preserved_fields = state.get("preserved_user_config_fields", [])
    return {
        "state": state,
        "rules_source": rules_source,
        "rules_target": rules_target,
        "rules_current_bytes": rules_current_bytes,
        "skills": skills,
        "retired_skills": retired_skills,
        "config_path": config_path,
        "config_original": config_text,
        "config_original_bytes": config_original_bytes,
        "config_rendered": rendered_config,
        "appended_fields": appended_fields,
        "preserved_fields": preserved_fields,
        "guidance_path": guidance_path,
        "guidance_original": guidance_text,
        "guidance_original_bytes": guidance_original_bytes,
        "guidance_rendered": rendered_guidance,
        "previous_block_hashes": previous_block_hashes,
        "state_original_bytes": _read_optional_bytes(codex_home / STATE_FILE),
    }


def build_plan(codex_home: Path, agent_home: Path, source_root: Path, *, skills_only: bool = False) -> dict[str, Any]:
    data = _preflight(codex_home, agent_home, source_root, skills_only=skills_only)
    actions: list[dict[str, str]] = []
    if data["state"] and data["state"].get("version") != VERSION:
        actions.append({"action": "MIGRATE_OWNERSHIP_STATE", "target": f"CODEX_HOME/{STATE_FILE}"})
    if data["config_original"] != data["config_rendered"]:
        actions.append({"action": "PATCH_MANAGED_FIELDS", "target": "CODEX_HOME/config.toml"})
    if data["guidance_original"] != data["guidance_rendered"]:
        actions.append({"action": "MERGE_MANAGED_BLOCK", "target": "CODEX_HOME/AGENTS.md"})
    rules_source: Path = data["rules_source"]
    rules_target: Path = data["rules_target"]
    if not skills_only and (not rules_target.exists() or rules_target.read_bytes() != rules_source.read_bytes()):
        actions.append({"action": "REPLACE_OWNED_FILE", "target": RULE_RELATIVE.as_posix()})
    for skill in data["skills"]:
        target: Path = skill["target"]
        if not target.exists() or _tree_hash(target) != skill["hash"]:
            actions.append({"action": "REPLACE_OWNED_SKILL", "target": f"skills/{skill['name']}"})
    for skill in data["retired_skills"]:
        if skill["target"].exists():
            actions.append({"action": "REMOVE_RETIRED_OWNED_SKILL", "target": f"skills/{skill['name']}"})
    plan = {
        "status": "DRY_RUN",
        "target_scope_digest": _target_scope_digest(codex_home, agent_home, source_root) + (":skills-only" if skills_only else ""),
        "managed_config_fields": [] if skills_only else sorted(MANAGED_CONFIG),
        "preserved_user_config_fields": sorted(data["preserved_fields"]),
        "actions": actions,
        "write_set_count": len(actions),
    }
    plan["plan_digest"] = _plan_digest(plan)
    return plan


def apply_overlay(
    codex_home: Path,
    agent_home: Path,
    source_root: Path,
    *,
    approved_plan_digest: str | None,
    skills_only: bool = False,
) -> dict[str, Any]:
    """Apply only an explicitly reviewed, current, target-bound ActionPlan."""

    if not approved_plan_digest:
        raise ManagedConflict("ACTION_PLAN_DIGEST_REQUIRED build and explicitly approve a current plan first")
    with _operation_lock(codex_home):
        current_plan = build_plan(codex_home, agent_home, source_root, skills_only=skills_only)
        if approved_plan_digest != current_plan["plan_digest"]:
            raise ManagedConflict("ACTION_PLAN_DIGEST_MISMATCH rerun plan and review the current target write set")
        data = _preflight(codex_home, agent_home, source_root, skills_only=skills_only)
        config_path: Path = data["config_path"]
        guidance_path: Path = data["guidance_path"]
        rules_source: Path = data["rules_source"]
        rules_target: Path = data["rules_target"]
        state_path = codex_home / STATE_FILE

        config_bytes = None if skills_only else data["config_rendered"].encode("utf-8")
        guidance_bytes = None if skills_only else data["guidance_rendered"].encode("utf-8")
        rules_bytes = None if skills_only else rules_source.read_bytes()
        target_hashes: dict[str, str] = {
            **{key: value for key, value in data["state"].get("target_hashes", {}).items() if skills_only and not key.startswith("skills/")},
            **({RULE_RELATIVE.as_posix(): _sha256_bytes(rules_bytes)} if rules_bytes is not None else {}),
            **{f"skills/{skill['name']}": skill["hash"] for skill in data["skills"]},
        }
        config_block = _managed_block(data["config_rendered"], CONFIG_BEGIN, CONFIG_END)
        guidance_block = _managed_block(data["guidance_rendered"], GUIDANCE_BEGIN, GUIDANCE_END)
        if guidance_block is None and not skills_only:
            raise ManagedConflict("rendered guidance is missing its managed block")
        managed_block_hashes = dict(data["state"].get("managed_block_hashes", {})) if skills_only else {"AGENTS.md": _block_hash(guidance_block)}
        if data["appended_fields"] and not skills_only:
            if config_block is None:
                raise ManagedConflict("rendered config is missing its managed block")
            managed_block_hashes["config.toml"] = _block_hash(config_block)

        final_state = {
            "version": VERSION,
            "phase": "applied",
            "managed_config_fields": list(data["appended_fields"]),
            "preserved_user_config_fields": sorted(data["preserved_fields"]),
            "managed_skill_names": [skill["name"] for skill in data["skills"]],
            "managed_block_hashes": managed_block_hashes,
            "target_hashes": target_hashes,
        }
        final_state_bytes = (
            json.dumps(final_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

        changed = any(
            (
                data["config_original_bytes"] != config_bytes,
                data["guidance_original_bytes"] != guidance_bytes,
                data["rules_current_bytes"] != rules_bytes,
                data["state_original_bytes"] != final_state_bytes,
                bool(data["retired_skills"]),
                any(skill["current_hash"] != skill["hash"] for skill in data["skills"]),
            )
        )
        if not changed:
            verification = verify_overlay(codex_home, agent_home, source_root, skills_only=skills_only)
            if verification["status"] != "PASS":
                raise ManagedConflict(f"post-apply verification failed: {verification['issues']}")
            return {
                "status": "NO_CHANGE",
                "managed_config_fields": [] if skills_only else sorted(MANAGED_CONFIG),
                "installed_skills": len(data["skills"]),
                "preserved_user_config_fields": sorted(data["preserved_fields"]),
            }

        pending_names = sorted(
            {skill["name"] for skill in data["skills"]}
            | {skill["name"] for skill in data["retired_skills"]}
        )
        pending_hashes = dict(target_hashes)
        pending_hashes.update(
            {f"skills/{skill['name']}": skill["hash"] for skill in data["retired_skills"]}
        )
        pending_state = {
            **final_state,
            "phase": "applying",
            "managed_skill_names": pending_names,
            "target_hashes": pending_hashes,
            "previous_block_hashes": data["previous_block_hashes"],
            "previous_target_hashes": dict(data["state"].get("target_hashes", {})),
        }
        pending_state_bytes = (
            json.dumps(pending_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        _atomic_write(
            state_path,
            pending_state_bytes,
            expected_current=data["state_original_bytes"],
        )

        if data["config_original_bytes"] != config_bytes:
            _atomic_write(
                config_path,
                config_bytes,
                expected_current=data["config_original_bytes"],
            )
        if data["guidance_original_bytes"] != guidance_bytes:
            _atomic_write(
                guidance_path,
                guidance_bytes,
                expected_current=data["guidance_original_bytes"],
            )
        if data["rules_current_bytes"] != rules_bytes:
            _atomic_write(
                rules_target,
                rules_bytes,
                expected_current=data["rules_current_bytes"],
            )

        for skill in data["skills"]:
            source: Path = skill["source"]
            target: Path = skill["target"]
            if skill["current_hash"] == skill["hash"]:
                continue
            current_hash = _tree_hash(target) if target.exists() else None
            if current_hash != skill["current_hash"]:
                raise ManagedConflict(f"concurrent skill modification detected: {target}")
            target.parent.mkdir(parents=True, exist_ok=True)
            temporary = Path(tempfile.mkdtemp(prefix=f".{target.name}.staging-", dir=target.parent))
            try:
                shutil.copytree(source, temporary, dirs_exist_ok=True)
                if _tree_hash(temporary) != skill["hash"]:
                    raise ManagedConflict(f"staged skill hash mismatch: {source}")
                if target.exists():
                    shutil.rmtree(target)
                os.replace(temporary, target)
            finally:
                if temporary.exists():
                    shutil.rmtree(temporary)

        for skill in data["retired_skills"]:
            target: Path = skill["target"]
            if not target.exists():
                continue
            if _tree_hash(target) != skill["current_hash"]:
                raise ManagedConflict(f"concurrent retired-skill modification detected: {target}")
            shutil.rmtree(target)

        _atomic_write(
            state_path,
            final_state_bytes,
            expected_current=pending_state_bytes,
        )
        verification = verify_overlay(codex_home, agent_home, source_root, skills_only=skills_only)
        if verification["status"] != "PASS":
            raise ManagedConflict(f"post-apply verification failed: {verification['issues']}")
        return {
            "status": "APPLIED",
            "managed_config_fields": [] if skills_only else sorted(MANAGED_CONFIG),
            "installed_skills": len(data["skills"]),
            "preserved_user_config_fields": sorted(data["preserved_fields"]),
        }


def verify_overlay(codex_home: Path, agent_home: Path, source_root: Path, *, skills_only: bool = False) -> dict[str, Any]:
    if skills_only:
        _assert_safe_managed_path(codex_home, codex_home / STATE_FILE)
        state = _load_state(codex_home)
        return _verify_skill_assets(state, agent_home, source_root, [])
    issues: list[str] = []
    config_path = codex_home / "config.toml"
    _assert_safe_managed_path(codex_home, codex_home / STATE_FILE)
    _assert_safe_managed_path(codex_home, config_path)
    config_text = ""
    try:
        config_text = config_path.read_text(encoding="utf-8")
        config = tomllib.loads(config_text)
    except (OSError, tomllib.TOMLDecodeError):
        config = {}
        issues.append("config_invalid")
    state = _load_state(codex_home)
    if not state:
        issues.append("state_missing")
    elif state.get("phase") != "applied":
        issues.append(f"state_incomplete:{state.get('phase')}")
    managed_fields = state.get("managed_config_fields", []) if isinstance(state, dict) else []
    for key in managed_fields:
        if config.get(key) != MANAGED_CONFIG.get(key):
            issues.append(f"config_drift:{key}")
    try:
        config_block = _managed_block(config_text, CONFIG_BEGIN, CONFIG_END)
    except ManagedConflict:
        config_block = None
        issues.append("config_managed_block_missing_or_duplicate")
    if managed_fields:
        if config_block is None:
            issues.append("config_managed_block_missing_or_duplicate")
        else:
            expected_config_hash = (
                state.get("managed_block_hashes", {}).get("config.toml")
                if state.get("version") == VERSION
                else _block_hash(_expected_config_block(managed_fields))
            )
            if _block_hash(config_block) != expected_config_hash:
                issues.append("config_managed_block_drift")
    elif config_block is not None:
        issues.append("config_unexpected_managed_block")

    guidance_path = codex_home / "AGENTS.md"
    _assert_safe_managed_path(codex_home, guidance_path)
    guidance = guidance_path.read_text(encoding="utf-8") if guidance_path.exists() else ""
    try:
        guidance_block = _managed_block(guidance, GUIDANCE_BEGIN, GUIDANCE_END)
    except ManagedConflict:
        guidance_block = None
    if guidance_block is None:
        issues.append("guidance_missing_or_duplicate")
    else:
        guidance_source = (source_root / "global-guidance.md").read_text(encoding="utf-8")
        expected_guidance_hash = (
            state.get("managed_block_hashes", {}).get("AGENTS.md")
            if state.get("version") == VERSION
            else _block_hash(_expected_guidance_block(guidance_source))
        )
        if _block_hash(guidance_block) != expected_guidance_hash:
            issues.append("guidance_owned_block_drift")
        if guidance_block != _expected_guidance_block(guidance_source):
            issues.append("guidance_drift")

    rules_source = source_root / RULE_RELATIVE
    rules_target = codex_home / RULE_RELATIVE
    _assert_safe_managed_path(codex_home, rules_target)
    rule_hash = _sha256_bytes(rules_source.read_bytes())
    if state and state.get("target_hashes", {}).get(RULE_RELATIVE.as_posix()) != rule_hash:
        issues.append("rules_state_drift")
    if not rules_target.exists() or _sha256_bytes(rules_target.read_bytes()) != rule_hash:
        issues.append("rules_drift")

    return _verify_skill_assets(state, agent_home, source_root, issues, config_fields=sorted(MANAGED_CONFIG))


def _verify_skill_assets(state: dict[str, Any], agent_home: Path, source_root: Path, issues: list[str], *, config_fields: list[str] | None = None) -> dict[str, Any]:
    if not state:
        issues.append("state_missing")
    elif state.get("phase") != "applied":
        issues.append(f"state_incomplete:{state.get('phase')}")
    skills = _skill_sources(source_root)
    source_names = {source.name for source in skills}
    state_names = set(state.get("managed_skill_names", [])) if state else set()
    if state and source_names != state_names:
        issues.append("managed_skill_set_drift")
    for source in skills:
        target = agent_home / "skills" / source.name
        _assert_safe_managed_path(agent_home, target)
        source_hash = _tree_hash(source)
        if state and state.get("target_hashes", {}).get(f"skills/{source.name}") != source_hash:
            issues.append(f"skill_state_drift:{source.name}")
        if not target.exists() or _tree_hash(target) != source_hash:
            issues.append(f"skill_drift:{source.name}")
    return {
        "status": "PASS" if not issues else "FAIL",
        "issues": issues,
        "managed_config_fields": config_fields or [],
        "installed_skills": len(skills),
    }


def rollback_overlay(codex_home: Path, agent_home: Path, source_root: Path) -> dict[str, Any]:
    with _operation_lock(codex_home):
        _assert_safe_managed_path(codex_home, codex_home / STATE_FILE)
        state = _load_state(codex_home)
        state_path = codex_home / STATE_FILE
        state_original_bytes = _read_optional_bytes(state_path)
        config_path = codex_home / "config.toml"
        guidance_path = codex_home / "AGENTS.md"
        rules_target = codex_home / RULE_RELATIVE
        _assert_safe_managed_path(codex_home, config_path)
        _assert_safe_managed_path(codex_home, guidance_path)
        _assert_safe_managed_path(codex_home, rules_target)
        config_original_bytes = _read_optional_bytes(config_path)
        guidance_original_bytes = _read_optional_bytes(guidance_path)
        config_text = config_original_bytes.decode("utf-8") if config_original_bytes is not None else ""
        guidance_text = (
            guidance_original_bytes.decode("utf-8") if guidance_original_bytes is not None else ""
        )
        if not state:
            managed_looking_skills = [
                agent_home / "skills" / source.name
                for source in _skill_sources(source_root)
                if (agent_home / "skills" / source.name).exists()
            ]
            if (
                CONFIG_BEGIN in config_text
                or CONFIG_END in config_text
                or GUIDANCE_BEGIN in guidance_text
                or GUIDANCE_END in guidance_text
                or rules_target.exists()
                or managed_looking_skills
            ):
                raise ManagedConflict("managed-looking assets exist without an ownership state file")
            return {"status": "NO_CHANGE"}

        recovering = state.get("phase") in {"applying", "rolling_back"}
        target_hashes = state["target_hashes"]
        previous_target_hashes = state.get("previous_target_hashes", {}) if recovering else {}
        block_hashes = state.get("managed_block_hashes", {})
        previous_block_hashes = state.get("previous_block_hashes", {}) if recovering else {}
        managed_skill_names = state["managed_skill_names"]
        managed_fields = state.get("managed_config_fields", [])

        try:
            config_block = _managed_block(config_text, CONFIG_BEGIN, CONFIG_END)
            guidance_block = _managed_block(guidance_text, GUIDANCE_BEGIN, GUIDANCE_END)
        except ManagedConflict as exc:
            raise ManagedConflict("managed mixed-ownership block is malformed") from exc

        if managed_fields:
            accepted_config_hashes = {
                value
                for value in (
                    block_hashes.get("config.toml")
                    if state.get("version") == VERSION
                    else _block_hash(_expected_config_block(managed_fields)),
                    previous_block_hashes.get("config.toml"),
                )
                if value
            }
            if config_block is None:
                if not recovering:
                    raise ManagedConflict(f"managed config block changed after apply: {config_path}")
            elif _block_hash(config_block) not in accepted_config_hashes:
                raise ManagedConflict(f"managed config block changed after apply: {config_path}")
        elif config_block is not None:
            raise ManagedConflict(f"unexpected managed config block: {config_path}")

        guidance_source = (source_root / "global-guidance.md").read_text(encoding="utf-8")
        accepted_guidance_hashes = {
            value
            for value in (
                block_hashes.get("AGENTS.md")
                if state.get("version") == VERSION
                else _block_hash(_expected_guidance_block(guidance_source)),
                previous_block_hashes.get("AGENTS.md"),
            )
            if value
        }
        if guidance_block is None:
            if not recovering:
                raise ManagedConflict(f"managed guidance block changed after apply: {guidance_path}")
        elif _block_hash(guidance_block) not in accepted_guidance_hashes:
            raise ManagedConflict(f"managed guidance content changed after apply: {guidance_path}")

        accepted_rule_hashes = {
            value
            for value in (
                target_hashes.get(RULE_RELATIVE.as_posix()),
                previous_target_hashes.get(RULE_RELATIVE.as_posix()),
            )
            if value
        }
        if rules_target.exists():
            if _sha256_bytes(rules_target.read_bytes()) not in accepted_rule_hashes:
                raise ManagedConflict(f"managed rule changed after apply: {rules_target}")
        elif not recovering:
            raise ManagedConflict(f"managed rule changed after apply: {rules_target}")

        skill_targets: list[tuple[Path, set[str]]] = []
        for name in managed_skill_names:
            target = agent_home / "skills" / name
            _assert_safe_managed_path(agent_home, target)
            accepted = {
                value
                for value in (
                    target_hashes.get(f"skills/{name}"),
                    previous_target_hashes.get(f"skills/{name}"),
                )
                if value
            }
            if target.exists():
                if _tree_hash(target) not in accepted:
                    raise ManagedConflict(f"managed skill changed after apply: {target}")
            elif not recovering:
                raise ManagedConflict(f"managed skill changed after apply: {target}")
            skill_targets.append((target, accepted))

        changed = False
        if state.get("phase") != "rolling_back":
            journal_block_hashes = dict(block_hashes)
            if state.get("version") != VERSION:
                journal_block_hashes = {}
                if config_block is not None:
                    journal_block_hashes["config.toml"] = _block_hash(config_block)
                if guidance_block is None:
                    raise ManagedConflict(f"managed guidance block changed after apply: {guidance_path}")
                journal_block_hashes["AGENTS.md"] = _block_hash(guidance_block)
            rollback_state = {
                **state,
                "version": VERSION,
                "phase": "rolling_back",
                "managed_block_hashes": journal_block_hashes,
            }
            rollback_state_bytes = (
                json.dumps(rollback_state, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
            ).encode("utf-8")
            _atomic_write(
                state_path,
                rollback_state_bytes,
                expected_current=state_original_bytes,
            )
            state_original_bytes = rollback_state_bytes
            changed = True
        if config_block is not None:
            rendered, removed = _remove_managed_block(config_text, CONFIG_BEGIN, CONFIG_END)
            if removed:
                tomllib.loads(rendered) if rendered.strip() else None
                _atomic_write(
                    config_path,
                    rendered.encode("utf-8"),
                    expected_current=config_original_bytes,
                )
                changed = True
        if guidance_block is not None:
            rendered, removed = _remove_managed_block(guidance_text, GUIDANCE_BEGIN, GUIDANCE_END)
            if removed:
                _atomic_write(
                    guidance_path,
                    rendered.encode("utf-8"),
                    expected_current=guidance_original_bytes,
                )
                changed = True

        if rules_target.exists():
            if _sha256_bytes(rules_target.read_bytes()) not in accepted_rule_hashes:
                raise ManagedConflict(f"concurrent rule modification detected: {rules_target}")
            rules_target.unlink()
            changed = True
        for target, accepted in skill_targets:
            if target.exists():
                if _tree_hash(target) not in accepted:
                    raise ManagedConflict(f"concurrent skill modification detected: {target}")
                shutil.rmtree(target)
                changed = True

        if _read_optional_bytes(state_path) != state_original_bytes:
            raise ManagedConflict(f"concurrent state modification detected: {state_path}")
        if state_path.exists():
            state_path.unlink()
            changed = True
        return {"status": "ROLLED_BACK" if changed else "NO_CHANGE"}


def _default_source_root() -> Path:
    return Path(__file__).resolve().parents[3] / "integrations" / "executors" / "codex"


def build_personal_guidance_plan(codex_home: Path, source: Path, backup: Path) -> dict[str, Any]:
    """Explicit user-rule replacement, separate from owned overlay deployment."""
    repo = Path(__file__).resolve().parents[3]
    if source.suffix.lower() != ".md":
        raise ManagedConflict("personal guidance source must be a Markdown rule file")
    _assert_safe_managed_path(repo, source)
    _assert_safe_managed_path(repo / ".project-local", backup)
    target = codex_home / "AGENTS.md"
    _assert_safe_managed_path(codex_home, target)
    desired = source.read_bytes()
    if not desired.strip():
        raise ManagedConflict("empty personal guidance source")
    current = _read_optional_bytes(target)
    plan = {
        "status": "DRY_RUN",
        "scope": "personal-guidance-only",
        "target": str(target),
        "source": str(source.resolve()),
        "backup": str(backup.resolve()),
        "current_sha256": _sha256_bytes(current) if current is not None else None,
        "source_sha256": _sha256_bytes(desired),
        "write_set_count": 0 if current == desired else 1,
    }
    plan["plan_digest"] = _sha256_bytes(json.dumps(plan, sort_keys=True).encode())
    return plan


def apply_personal_guidance(codex_home: Path, source: Path, backup: Path, approved_plan_digest: str | None) -> dict[str, Any]:
    if not approved_plan_digest:
        raise ManagedConflict("ACTION_PLAN_DIGEST_REQUIRED")
    with _operation_lock(codex_home):
        plan = build_personal_guidance_plan(codex_home, source, backup)
        if plan["plan_digest"] != approved_plan_digest:
            raise ManagedConflict("ACTION_PLAN_DIGEST_MISMATCH")
        if not plan["write_set_count"]:
            return {"status": "NO_CHANGE", "scope": plan["scope"]}
        target = codex_home / "AGENTS.md"
        current = _read_optional_bytes(target)
        desired = source.read_bytes()
        if (_sha256_bytes(current) if current is not None else None) != plan["current_sha256"] or _sha256_bytes(desired) != plan["source_sha256"]:
            raise ManagedConflict("concurrent guidance modification detected")
        if current is not None:
            if backup.exists():
                raise ManagedConflict("guidance backup already exists; preserve it")
            _atomic_write(backup, current, expected_current=None)
        _atomic_write(target, desired, expected_current=current)
        if target.read_bytes() != desired:
            raise ManagedConflict("guidance readback failed; restore reviewed backup")
        return {"status": "APPLIED", "scope": plan["scope"], "sha256": plan["source_sha256"], "backup": str(backup)}


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize the Workflow Assistance Codex user overlay")
    parser.add_argument("operation", choices=("plan", "apply", "verify", "rollback", "plan-personal-guidance", "apply-personal-guidance"))
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--agent-home", type=Path, default=Path.home() / ".agents")
    parser.add_argument("--source-root", type=Path, default=_default_source_root())
    parser.add_argument("--approved", action="store_true", help="explicitly approve the reviewed dry-run plan")
    parser.add_argument("--approved-plan-digest", help="SHA-256 digest printed by the reviewed plan")
    parser.add_argument("--skills-only", action="store_true", help="sync owned skills only; preserve guidance, config and rules")
    parser.add_argument("--personal-source", type=Path)
    parser.add_argument("--guidance-backup", type=Path)
    args = parser.parse_args()
    if args.skills_only and args.operation == "rollback":
        parser.error("skills-only rollback is not supported; restore the reviewed skill backup")
    if args.operation in {"apply", "apply-personal-guidance"} and not args.approved:
        print(json.dumps({
            "status": "BLOCKED",
            "reason": "ACTION_PLAN_BLOCKED approval_required=true run plan, review the target and write set, then use --approved",
        }, ensure_ascii=False))
        return 2
    try:
        if args.operation in {"plan-personal-guidance", "apply-personal-guidance"}:
            if not args.personal_source or not args.guidance_backup or args.skills_only:
                parser.error("personal guidance requires --personal-source and --guidance-backup without --skills-only")
            if args.operation == "plan-personal-guidance":
                result = build_personal_guidance_plan(args.codex_home, args.personal_source, args.guidance_backup)
            else:
                result = apply_personal_guidance(args.codex_home, args.personal_source, args.guidance_backup, args.approved_plan_digest)
        elif args.operation == "plan":
            result = build_plan(args.codex_home, args.agent_home, args.source_root, skills_only=args.skills_only)
        elif args.operation == "apply":
            if not args.approved_plan_digest:
                print(json.dumps({
                    "status": "BLOCKED",
                    "reason": "ACTION_PLAN_DIGEST_REQUIRED run plan, review its plan_digest, then provide --approved-plan-digest",
                }, ensure_ascii=False))
                return 2
            current_plan = build_plan(args.codex_home, args.agent_home, args.source_root, skills_only=args.skills_only)
            if args.approved_plan_digest != current_plan["plan_digest"]:
                print(json.dumps({
                    "status": "BLOCKED",
                    "reason": "ACTION_PLAN_DIGEST_MISMATCH rerun plan and review the current target write set",
                }, ensure_ascii=False))
                return 2
            result = apply_overlay(
                args.codex_home,
                args.agent_home,
                args.source_root,
                approved_plan_digest=args.approved_plan_digest,
                skills_only=args.skills_only,
            )
        elif args.operation == "verify":
            result = verify_overlay(args.codex_home, args.agent_home, args.source_root, skills_only=args.skills_only)
        else:
            result = rollback_overlay(args.codex_home, args.agent_home, args.source_root)
    except (ManagedConflict, FileNotFoundError, OSError, tomllib.TOMLDecodeError) as exc:
        print(json.dumps({"status": "BLOCKED", "error": str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    return 0 if result.get("status") not in {"FAIL", "BLOCKED"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
