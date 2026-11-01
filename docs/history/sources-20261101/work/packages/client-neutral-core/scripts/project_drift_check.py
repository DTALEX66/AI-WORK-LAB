"""Project drift check — detect and report drift after multi-round task execution.

Records a baseline snapshot (hash of drift-sensitive files); after N rounds,
compares current state against the baseline and reports what drifted, so the
governance layer can converge it. Part of the execute lifecycle (before land).
"""
from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path

BASELINE_FILE = ".workflow/drift-baseline.json"
# Drift-sensitive files (project rules + governance state)
SENSITIVE_GLOBS = [
    "AGENTS.md",
    ".project/governance/**/*.json",
    "config/**/*.json",
    "config/SOUL.md",
]


def _hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def snapshot(root: Path) -> dict:
    """Compute current hashes of drift-sensitive files."""
    out = {}
    for glob in SENSITIVE_GLOBS:
        for f in Path(root).glob(glob):
            if f.is_file():
                rel = str(f.relative_to(root))
                out[rel] = _hash_file(f)
    return out


def record_baseline(root: Path) -> dict:
    """Record the baseline snapshot (call after a clean, verified state)."""
    base = {"version": 1, "recordedAt": time.time(), "files": snapshot(root)}
    f = Path(root) / BASELINE_FILE
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(base, indent=1), encoding="utf-8")
    return {"recorded": len(base["files"])}


def check_drift(root: Path) -> dict:
    """Compare current state to baseline; report drifted files."""
    f = Path(root) / BASELINE_FILE
    if not f.exists():
        return {"baselineMissing": True, "drift": {}, "hint": "record_baseline first"}
    base = json.loads(f.read_text(encoding="utf-8"))
    cur = snapshot(root)
    drift = {}
    for rel, h in base["files"].items():
        if cur.get(rel) != h:
            drift[rel] = {"baseline": h, "current": cur.get(rel, "MISSING")}
    for rel in cur:
        if rel not in base["files"]:
            drift[rel] = {"baseline": "NEW", "current": cur[rel]}
    return {"driftCount": len(drift), "drift": drift, "status": "DRIFT" if drift else "CLEAN"}


def converge(root: Path) -> dict:
    """Re-record baseline to current (accept drift as new baseline)."""
    return record_baseline(root)
