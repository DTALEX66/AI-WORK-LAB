"""Skill-call index — per-project cache mapping task keywords -> skills.

First run scans SKILL.md descriptions and builds an index; later runs look up
the index directly instead of re-scanning every time. Optimization layer on top
of the "scan skills before executing" rule.
"""
from __future__ import annotations

import json
import re
import time
from pathlib import Path

INDEX_FILE = ".project-local/runs/skill-call-index.json"
WORD_RE = re.compile(r"[a-zA-Z0-9_\u4e00-\u9fff-]{3,}")


def _load(root):
    f = Path(root) / INDEX_FILE
    if not f.exists():
        return {"version": 1, "keywords": {}, "lastBuilt": None}
    return json.loads(f.read_text(encoding="utf-8"))


def _save(root, data):
    f = Path(root) / INDEX_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding="utf-8")


def build(root, skills_dir):
    idx = {"version": 1, "keywords": {}, "lastBuilt": time.time()}
    sp = Path(skills_dir)
    if not sp.exists():
        _save(root, idx)
        return idx
    for skill in sp.rglob("SKILL.md"):
        text = skill.read_text(encoding="utf-8", errors="ignore")
        # description: ... (frontmatter line)
        m = re.search(r"description:\s*(.+)", text)
        desc = (m.group(1) if m else "") + " " + skill.parent.name
        name = skill.parent.name
        for w in WORD_RE.findall(desc.lower()):
            idx["keywords"].setdefault(w, [])
            if name not in idx["keywords"][w]:
                idx["keywords"][w].append(name)
    _save(root, idx)
    return idx


def ensure_fresh(root, skills_dir, max_age=None):
    """Rebuild the index if stale: skills changed (mtime) or index missing.
    max_age (seconds) forces rebuild after N seconds regardless of mtime."""
    idx = _load(root)
    sp = Path(skills_dir)
    if not idx.get("keywords") or not idx.get("lastBuilt"):
        return build(root, sp)
    latest_skill_mtime = 0.0
    if sp.exists():
        for skill in sp.rglob("SKILL.md"):
            latest_skill_mtime = max(latest_skill_mtime, skill.stat().st_mtime)
    stale_by_mtime = latest_skill_mtime > idx["lastBuilt"]
    stale_by_age = max_age is not None and (time.time() - idx["lastBuilt"]) > max_age
    if stale_by_mtime or stale_by_age:
        return build(root, sp)
    return idx


def lookup(root, task):
    idx = _load(root)
    if not idx.get("keywords"):
        return []
    hits = {}
    for w in WORD_RE.findall(task.lower()):
        for skill in idx["keywords"].get(w, []):
            hits[skill] = hits.get(skill, 0) + 1
    return [s for s, _ in sorted(hits.items(), key=lambda kv: -kv[1])]


def record(root, task, skill):
    idx = _load(root)
    for w in WORD_RE.findall(task.lower()):
        idx["keywords"].setdefault(w, [])
        if skill not in idx["keywords"][w]:
            idx["keywords"][w].append(skill)
    _save(root, idx)
    return {"recorded": True, "skill": skill}
# --- CLI (WL-DLC-050: no manual python -c needed) ---
if __name__ == "__main__":
    import argparse
    import sys
    p = argparse.ArgumentParser(description="Skill-call index (per-project)")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("build", help="Build index from skills dir").add_argument("--skills-dir", required=True)
    lp = sub.add_parser("lookup", help="Look up skills for a task")
    lp.add_argument("--task", required=True)
    lp.add_argument("--skills-dir")
    lp.add_argument("--rebuild", action="store_true", help="Rebuild before lookup (stale detection)")
    rp = sub.add_parser("record", help="Record task->skill mapping")
    rp.add_argument("--task", required=True)
    rp.add_argument("--skill", required=True)
    a = p.parse_args()
    root = Path.cwd()
    if a.cmd == "build":
        r = build(root, Path(a.skills_dir))
        print(json.dumps({"built": len(r["keywords"])}, ensure_ascii=False))
    elif a.cmd == "lookup":
        if a.rebuild and a.skills_dir:
            ensure_fresh(root, Path(a.skills_dir))
        print(json.dumps(lookup(root, a.task), ensure_ascii=False))
    elif a.cmd == "record":
        print(json.dumps(record(root, a.task, a.skill), ensure_ascii=False))
