#!/usr/bin/env python3
"""Neutral skill lifecycle: usage tracking + archive-with-recovery.

Client-neutral re-implementation of the personal-agent self-improvement
pattern (usage sidecar, active/stale/archived states, pin opt-out,
archive-not-delete, backup before transitions, provenance filter). It does
not depend on Hermes, Codex, or any agent runtime — it operates on any
skills root passed to it.

Managed set: SKILL.md files whose frontmatter contains `created_by: agent`.
Everything else (repository-owned, bundled, hub-installed, manually authored)
is off-limits — exactly like the source pattern's provenance filter.

State:
  <root>/.usage.json        sidecar: per-skill counters + lifecycle fields
  <root>/.archive/<name>/   archived skills (recoverable via restore)
  <root>/.backups/          pre-transition copies

Transitions:
  active -> stale    last_activity_at older than stale_after_days (30)
  stale  -> archived last_activity_at older than archive_after_days (90)
  pinned skills bypass all transitions. Archive is never delete.

CLI:
  status                  list skills with state/pinned/activity
  record <name> <event>   bump use/view/patch counter + touch activity
  run [--dry-run]         apply transitions (archive stale skills)
  archive <name>          archive a skill now (after backup)
  restore <name>          restore from .archive back to <root>
  pin <name> | unpin <name>
  backup <name>           copy skill to .backups before a change

Usage:
  python scripts/workflow/skill_lifecycle.py status --root <skills-root>
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

STATE_ACTIVE = "active"
STATE_STALE = "stale"
STATE_ARCHIVED = "archived"
_VALID_STATES = {STATE_ACTIVE, STATE_STALE, STATE_ARCHIVED}
DEFAULT_STALE_AFTER_DAYS = 30
DEFAULT_ARCHIVE_AFTER_DAYS = 90

_FRONTMATTER = re.compile(r"\A---\n(.*?)\n---", re.S)
_CREATED_BY_AGENT = re.compile(r"(?m)^\s*created_by\s*:\s*agent\s*$")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_iso(value: str) -> datetime:
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return datetime.now(timezone.utc)


def _is_agent_created(skill_dir: Path) -> bool:
    """Provenance filter: only `created_by: agent` SKILL.md files are managed."""
    skill_md = skill_dir / "SKILL.md"
    if not skill_md.is_file():
        return False
    text = skill_md.read_text(encoding="utf-8", errors="replace")
    match = _FRONTMATTER.search(text)
    if not match:
        return False
    return bool(_CREATED_BY_AGENT.search(match.group(1)))


def _skill_names(root: Path) -> list[str]:
    if not root.is_dir():
        return []
    return sorted(
        p.name for p in root.iterdir()
        if p.is_dir() and (p / "SKILL.md").is_file()
    )


def _usage_path(root: Path) -> Path:
    return root / ".usage.json"


def _load_usage(root: Path) -> dict:
    path = _usage_path(root)
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _atomic_write_usage(root: Path, data: dict) -> None:
    path = _usage_path(root)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2, sort_keys=True)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def _record(root: Path, name: str, event: str) -> str:
    usage = _load_usage(root)
    entry = usage.setdefault(name, {"state": STATE_ACTIVE, "pinned": False})
    entry["last_activity_at"] = _now()
    key = {"use": "use_count", "view": "view_count", "patch": "patch_count"}.get(event)
    if key:
        entry[key] = int(entry.get(key, 0)) + 1
    _atomic_write_usage(root, usage)
    return entry["last_activity_at"]


def _backup(root: Path, name: str) -> Path | None:
    skill_dir = root / name
    if not skill_dir.is_dir():
        return None
    backups = root / ".backups"
    backups.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    target = backups / f"{name}-{stamp}"
    shutil.copytree(skill_dir, target)
    return target


def _archive(root: Path, name: str, dry_run: bool = False) -> str:
    skill_dir = root / name
    if not skill_dir.is_dir():
        return f"NOT_FOUND {name}"
    usage = _load_usage(root)
    if usage.get(name, {}).get("pinned"):
        return f"PINNED_SKIP {name}"
    if not _is_agent_created(skill_dir):
        return f"NOT_MANAGED {name}"
    if dry_run:
        return f"WOULD_ARCHIVE {name}"
    backup = _backup(root, name)
    archive_dir = root / ".archive" / name
    archive_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(skill_dir), str(archive_dir))
    usage.setdefault(name, {})["state"] = STATE_ARCHIVED
    usage[name]["last_activity_at"] = usage.get(name, {}).get("last_activity_at") or _now()
    _atomic_write_usage(root, usage)
    return f"ARCHIVED {name} backup={backup.name if backup else 'none'}"


def _restore(root: Path, name: str) -> str:
    archive_dir = root / ".archive" / name
    if not archive_dir.is_dir():
        return f"NOT_ARCHIVED {name}"
    target = root / name
    if target.exists():
        return f"DEST_EXISTS {name}"
    shutil.move(str(archive_dir), str(target))
    usage = _load_usage(root)
    usage.setdefault(name, {})["state"] = STATE_ACTIVE
    usage[name]["last_activity_at"] = _now()
    _atomic_write_usage(root, usage)
    return f"RESTORED {name}"


def _set_pinned(root: Path, name: str, pinned: bool) -> str:
    usage = _load_usage(root)
    usage.setdefault(name, {})["pinned"] = pinned
    _atomic_write_usage(root, usage)
    return f"{'PINNED' if pinned else 'UNPINNED'} {name}"


def _apply_transitions(root: Path, dry_run: bool = False) -> list[str]:
    """Deterministic inactivity transitions: active -> stale -> archived."""
    now = datetime.now(timezone.utc)
    stale_after = timedelta(days=DEFAULT_STALE_AFTER_DAYS)
    archive_after = timedelta(days=DEFAULT_ARCHIVE_AFTER_DAYS)
    usage = _load_usage(root)
    results: list[str] = []
    for name in _skill_names(root):
        entry = usage.get(name, {})
        if entry.get("pinned"):
            continue
        if not _is_agent_created(root / name):
            continue
        last = _parse_iso(entry.get("last_activity_at") or _now())
        age = now - last
        state = entry.get("state", STATE_ACTIVE)
        if state != STATE_ARCHIVED and age > archive_after:
            results.append(_archive(root, name, dry_run=dry_run))
        elif state != STATE_ARCHIVED and age > stale_after:
            entry["state"] = STATE_STALE
            results.append(f"STALE {name}")
    if results:
        # _archive persists its own archived state; overlay the in-memory
        # STALE updates onto a fresh read so archived is never reverted.
        fresh = _load_usage(root)
        for name in _skill_names(root):
            if usage.get(name, {}).get("state") == STATE_STALE:
                fresh.setdefault(name, {})["state"] = STATE_STALE
        _atomic_write_usage(root, fresh)
    return results


def _status(root: Path) -> list[str]:
    usage = _load_usage(root)
    lines: list[str] = []
    for name in _skill_names(root):
        entry = usage.get(name, {})
        managed = "managed" if _is_agent_created(root / name) else "repo-owned"
        lines.append(
            f"{name:42s} state={entry.get('state', STATE_ACTIVE):8s} "
            f"pinned={str(entry.get('pinned', False)):5s} {managed} "
            f"last={str(entry.get('last_activity_at', '-'))[:19]}"
        )
    archived = sorted(p.name for p in (root / ".archive").iterdir()) if (root / ".archive").is_dir() else []
    for name in archived:
        lines.append(f"{name:42s} state=archived  (in .archive, restore-able)")
    return lines


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description="Neutral skill lifecycle")
    parser.add_argument("--root", default=".", help="skills root (default: cwd)")
    sub = parser.add_subparsers(dest="verb", required=True)
    sub.add_parser("status")
    rec = sub.add_parser("record")
    rec.add_argument("name")
    rec.add_argument("event", choices=["use", "view", "patch"])
    run = sub.add_parser("run")
    run.add_argument("--dry-run", action="store_true")
    arc = sub.add_parser("archive")
    arc.add_argument("name")
    res = sub.add_parser("restore")
    res.add_argument("name")
    for verb in ("pin", "unpin", "backup"):
        p = sub.add_parser(verb)
        p.add_argument("name")
    args = parser.parse_args(argv)

    root = Path(args.root).resolve()
    if args.verb == "status":
        for line in _status(root):
            print(line)
        return 0
    if args.verb == "record":
        print(_record(root, args.name, args.event))
        return 0
    if args.verb == "run":
        results = _apply_transitions(root, dry_run=args.dry_run)
        for r in results:
            print(r)
        print(f"run complete ({len(results)} transitions)")
        return 0
    if args.verb == "archive":
        print(_archive(root, args.name))
        return 0
    if args.verb == "restore":
        print(_restore(root, args.name))
        return 0
    if args.verb in ("pin", "unpin"):
        print(_set_pinned(root, args.name, args.verb == "pin"))
        return 0
    if args.verb == "backup":
        target = _backup(root, args.name)
        print(f"BACKUP {target}" if target else f"NOT_FOUND {args.name}")
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
