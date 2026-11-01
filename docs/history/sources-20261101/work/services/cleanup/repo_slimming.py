"""Repo slimming audit (WL-400 / ch 34): read-only size + spill report.

ch 34 asks WORK-LAB to scan a repo for ten classes of bloat
(node_modules / venv / binaries / models / assets / ZIP / Docker /
runtime / history / duplicate reports) and emit four JSON reports::

    repository-size.json   largest-files.json   external-data.json
    spill-report.json

This is an AUDIT, not a deleter.  Nothing here removes a byte — every
report records what is present, how large it is, and (for external-data
and spill-report) what SHOULD be moved or regenerated under the ch 35
external-asset rule.  Actual deletion is a user-authorised step, never
this module's (the standing no-delete-without-authorization rule).

Pure stdlib, reads only the repo it is pointed at, skips .git internals,
and caps per-file size probing so a multi-GB model never gets read.
"""
from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# ch 34's ten bloat classes.
CATEGORIES = ("node_modules", "venv", "binaries", "models", "assets",
              "docker", "runtime", "history", "duplicate_reports", "code")

# extension buckets
_BIN_EXT = {".exe", ".dll", ".so", ".dylib", ".pyd", ".bin", ".wasm"}
_MODEL_EXT = {".pt", ".pth", ".gguf", ".safetensors", ".onnx", ".ckpt",
              ".bin", ".tflite", ".npz"}
_ASSET_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".mp4", ".mov",
              ".pdf", ".zip", ".tar", ".gz", ".7z", ".ico", ".svg", ".woff",
              ".woff2"}
_DOCKER_NAMES = {"dockerfile", "docker-compose.yml", "docker-compose.yaml"}

# dirs we never walk into.  .git is pruned (version-control internals are not
# the working tree we size).  node_modules / venv / __pycache__ are KEPT in the
# walk on purpose: the external-data report must be able to FLAG them as
# regenerable / external-asset bloat, so the auditor has to see them.
_SKIP_DIRS = {".git"}


def _classify(rel: str, name: str, size: int) -> str:
    low = name.lower()
    rel_l = rel.replace(os.sep, "/").lower()
    ext = os.path.splitext(low)[1]
    parts = rel_l.split("/")
    if "node_modules" in parts:
        return "node_modules"
    if "venv" in parts or ".venv" in parts:
        return "venv"
    if low in _DOCKER_NAMES or low.startswith("docker-compose"):
        return "docker"
    if ext in _MODEL_EXT:
        return "models"
    if ext in _BIN_EXT and ext not in _MODEL_EXT:
        return "binaries"
    if ext in _ASSET_EXT:
        return "assets"
    if ".project-local" in parts or ".hermes" in parts or "runtime" in parts:
        return "runtime"
    if ".log" in low or low.endswith(".log") or "history" in low:
        return "history"
    return "code"


@dataclass
class FileRecord:
    path: str
    size: int
    category: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class RepoSlimmingAuditor:
    """Reads a repo once and produces the four ch 34 reports."""

    SCHEMA = "work-lab/repo-slimming/v1"

    def __init__(self, repo_root: str, skip_dirs: Optional[List[str]] = None,
                 top: int = 25) -> None:
        self.repo_root = os.path.abspath(repo_root)
        self._skip = set(skip_dirs or _SKIP_DIRS)
        self._top = top

    # -- the read -----------------------------------------------------------
    def scan(self) -> List[FileRecord]:
        records: List[FileRecord] = []
        for dirpath, dirnames, filenames in os.walk(self.repo_root):
            # prune in place; keep .git out entirely (no object-dir bloat)
            dirnames[:] = [d for d in dirnames if d not in self._skip]
            rel_dir = os.path.relpath(dirpath, self.repo_root)
            for fn in filenames:
                full = os.path.join(dirpath, fn)
                try:
                    size = os.path.getsize(full)
                except OSError:
                    continue
                rel = fn if rel_dir == "." else os.path.join(rel_dir, fn)
                records.append(FileRecord(rel, size, _classify(rel, fn, size)))
        return records

    # -- the four ch 34 reports (each returns a serialisable dict) ---------
    def repository_size(self, records: Optional[List[FileRecord]] = None) -> Dict[str, Any]:
        records = records if records is not None else self.scan()
        by_cat: Dict[str, int] = {}
        for r in records:
            by_cat[r.category] = by_cat.get(r.category, 0) + r.size
        total = sum(r.size for r in records)
        return {
            "schema": self.SCHEMA,
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "repo_root": self.repo_root,
            "file_count": len(records),
            "total_bytes": total,
            "by_category_bytes": dict(
                sorted(by_cat.items(), key=lambda kv: -kv[1])),
        }

    def largest_files(self, records: Optional[List[FileRecord]] = None) -> Dict[str, Any]:
        records = records if records is not None else self.scan()
        rows = sorted(records, key=lambda r: -r.size)[: self._top]
        return {"schema": self.SCHEMA, "top": self._top,
                "files": [r.to_dict() for r in rows]}

    def external_data(self, records: Optional[List[FileRecord]] = None) -> Dict[str, Any]:
        """ch 35: flag what is VENDORED third-party data — the classes that
        the external-asset rule says should be a register-and-recipe entry,
        not bytes in the repo.  Recommendation only; this never deletes."""
        records = records if records is not None else self.scan()
        findings: List[Dict[str, Any]] = []
        for r in records:
            if r.category in ("node_modules", "venv"):
                findings.append({"path": r.path, "bytes": r.size,
                                 "kind": r.category,
                                 "recommendation": "regenerate from lockfile; "
                                                    "do not commit"})
            elif r.category == "models" and r.size >= 1024 * 1024:
                findings.append({"path": r.path, "bytes": r.size,
                                 "kind": "model",
                                 "recommendation": "external asset: record "
                                                  "name/url/version/hash/recipe, "
                                                  "not the bytes (ch 35)"})
            elif r.category == "binaries" and r.size >= 1024 * 1024:
                findings.append({"path": r.path, "bytes": r.size,
                                 "kind": "binary",
                                 "recommendation": "external asset: reference, "
                                                  "do not vendor"})
        findings.sort(key=lambda f: -f["bytes"])
        total = sum(f["bytes"] for f in findings)
        return {"schema": self.SCHEMA, "flagged_bytes": total,
                "flagged_count": len(findings), "findings": findings}

    def spill_report(self, records: Optional[List[FileRecord]] = None) -> Dict[str, Any]:
        """Flag runtime / generated / local data that SHOULD stay inside
        .project-local (the ch 44 runtime root) or .gitignore.  A 'spill'
        is such data sitting outside the sanctioned roots."""
        records = records if records is not None else self.scan()
        spills: List[Dict[str, Any]] = []
        for r in records:
            rel_l = r.path.replace(os.sep, "/").lower()
            sanctioned = rel_l.startswith(".project-local/") or \
                rel_l.startswith(".hermes/")
            # runtime/history/generated data that is NOT under a sanctioned root
            if sanctioned:
                continue
            looks_generated = (
                rel_l.endswith(".log") or ".pyc" in rel_l or
                "__pycache__" in rel_l or rel_l.endswith(".sqlite3") or
                rel_l.endswith(".sqlite") or rel_l.startswith(".project-local")
            )
            if looks_generated:
                spills.append({"path": r.path, "bytes": r.size,
                               "reason": "generated/local data outside "
                                         ".project-local runtime root",
                               "recommendation": "move to .project-local/ or "
                                                 "gitignore; do not delete"})
        spills.sort(key=lambda s: s["path"])
        return {"schema": self.SCHEMA, "spill_count": len(spills),
                "spill_bytes": sum(s["bytes"] for s in spills), "spills": spills}

    # -- one-shot ------------------------------------------------------------
    def audit(self) -> Dict[str, Any]:
        records = self.scan()
        return {
            "repository_size": self.repository_size(records),
            "largest_files": self.largest_files(records),
            "external_data": self.external_data(records),
            "spill_report": self.spill_report(records),
        }

    def audit_to_files(self, out_dir: str) -> Dict[str, str]:
        """Write the four ch 34 JSON reports to ``out_dir``.  Returns the
        four written paths.  This is the sanctioned, reversible artifact;
        no file outside out_dir is touched."""
        os.makedirs(out_dir, exist_ok=True)
        reports = self.audit()
        names = {"repository_size": "repository-size.json",
                 "largest_files": "largest-files.json",
                 "external_data": "external-data.json",
                 "spill_report": "spill-report.json"}
        written: Dict[str, str] = {}
        for key, fname in names.items():
            path = os.path.join(out_dir, fname)
            with open(path, "w", encoding="utf-8") as fh:
                json.dump(reports[key], fh, indent=2, ensure_ascii=False,
                          sort_keys=True)
            written[key] = path
        return written
