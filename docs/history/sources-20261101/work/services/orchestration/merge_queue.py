"""Merge queue service — serialize branch landing (mainline-style).

Watches branches matching a prefix, merges them into main in FIFO order
(caller runs CI before enqueue; this enforces serialization so parallel
agents never clobber each other). Lightweight, runs as a daemon or one-shot.
"""
from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path

QUEUE_FILE = ".workflow/merge-queue.json"


def enqueue(root: Path, branch: str) -> dict:
    """Add a branch to the landing queue."""
    f = Path(root) / QUEUE_FILE
    q = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {"queue": []}
    if branch not in q["queue"]:
        q["queue"].append(branch)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(q, indent=1), encoding="utf-8")
    return {"enqueued": branch, "position": len(q["queue"])}


def process_queue(root: Path) -> dict:
    """Drain the queue: merge each branch into main in FIFO order."""
    f = Path(root) / QUEUE_FILE
    if not f.exists():
        return {"processed": 0}
    q = json.loads(f.read_text(encoding="utf-8"))
    merged = []
    for branch in list(q.get("queue", [])):
        r = subprocess.run(["git", "-C", str(root), "merge", "--no-ff", branch], capture_output=True, text=True, encoding="utf-8", errors="replace")
        if r.returncode == 0:
            merged.append(branch)
            subprocess.run(["git", "-C", str(root), "branch", "-d", branch], capture_output=True, text=True, encoding="utf-8", errors="replace")
        else:
            break  # stop on first conflict; leave rest queued
    q["queue"] = [b for b in q.get("queue", []) if b not in merged]
    f.write_text(json.dumps(q, indent=1), encoding="utf-8")
    return {"processed": len(merged), "merged": merged, "remaining": q["queue"]}


def status(root: Path) -> dict:
    f = Path(root) / QUEUE_FILE
    if not f.exists():
        return {"queue": []}
    return json.loads(f.read_text(encoding="utf-8"))
