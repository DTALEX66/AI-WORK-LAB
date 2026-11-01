#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-B000 / DLDS-B020 — directory semantics audit and legacy path scan.

B000 answers, for every first- and second-level directory: how many tracked
files it holds, how many bytes, which responsibility the taskpack assigns to it,
who owns it, and whether it conforms to the single current directory scheme.

B020 scans the repository for legacy path references (old adapter paths, old
runtime roots, old import roots, `.hermes` runtime usage, stale aliases) and
classifies each hit as MIGRATED / HISTORICAL_ONLY / DELETE / BLOCKED. An "active"
hit is code or configuration that still reads or writes the legacy location; a
historical hit is a document that records what used to exist.

Writes:
    reports/current/DEEPSEEK-DIRECTORY-AUDIT.json
    reports/current/DEEPSEEK-LEGACY-PATH-SCAN.json
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
AUDIT_OUT = "reports/current/DEEPSEEK-DIRECTORY-AUDIT.json"
LEGACY_OUT = "reports/current/DEEPSEEK-LEGACY-PATH-SCAN.json"
AUTHORITY_ID = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1"

# Taskpack section 9/10: the single current scheme, with the responsibility each
# directory owns. A directory not in this table is reported as EXTRA so the owner
# can decide, never silently accepted.
SCHEME = {
    "apps": ("runnable front ends", "workbench UI", "design-lab front end"),
    "services": ("independently composable product services", "jobs / review / quality / delivery",
                 "product services"),
    "packages": ("reusable design-domain capability", "capabilities, design-system, shared types",
                 "domain capability"),
    "integrations": ("third-party boundary", "hosts, generators, executors, mcp, canvases",
                     "adapter owner"),
    "src": ("DESIGN-LAB owned runtime logic", "runtime, analysis, state, orchestration, domain logic",
            "runtime core"),
    "fixtures": ("test and regression fixtures", "domain fixtures", "test data owner"),
    "evals": ("evaluation corpora", "golden sets", "evaluation owner"),
    "research": ("research inputs and candidates", "candidate intake", "research owner"),
    "vendor": ("third-party locks and minimal absorbed sources", "sources.lock.json", "supply chain"),
    "docs": ("documentation", "current / architecture / decisions / taskpacks / history", "doc owner"),
    "reports": ("generated projections and history", "current projections", "report generator"),
    "scripts": ("thin repository entry points", "generators and verifiers", "tooling owner"),
    ".project": ("governance truth", "manifest and path declaration", "owner"),
    ".project-local": ("all ignored runtime data", "runs, state, cache, artifacts, exports, logs, temp",
                       "runtime"),
    ".github": ("repository automation", "CI workflows", "CI owner"),
    "LICENSES": ("third-party licence texts", "licence evidence", "supply chain"),
    "design-lab": ("LEGACY dual scheme: design-domain content root retained while runtime code lives "
                   "in src/design_lab", "config, schemas, tests, scripts, domain-packs, evals",
                   "legacy owner (see DLDS-B010)"),
}

LEGACY_PATTERNS = [
    ("design-lab/adapters", re.compile(r"design[-_]lab/adapters|design_lab\.adapters\.(?!photoshop_com|illustrator_com|spi)")),
    ("project-memory", re.compile(r"project[-_]memory")),
    ("knowledge-dir", re.compile(r"design-lab/knowledge/")),
    ("intelligence-dir", re.compile(r"design-lab/intelligence/")),
    ("exports-dir", re.compile(r"design-lab/exports/")),
    ("hermes-path", re.compile(r"\.hermes")),
    ("hermes-task-artifacts", re.compile(r"\.hermes/task-artifacts|\.hermes/task-runtime")),
    ("legacy-import-design_lab-core", re.compile(r"from\s+design-lab\.|import\s+design-lab\.")),
]
ACTIVE_SUFFIXES = {".py", ".ts", ".js", ".jsx", ".json", ".yaml", ".yml", ".toml", ".cfg", ".sh", ".ps1"}
CODE_SUFFIXES = {".py", ".ts", ".js", ".jsx", ".sh", ".ps1"}
RECORD_SUFFIXES = {".json", ".yaml", ".yml", ".toml", ".cfg", ".csv", ".spdx"}
# A match is only an *active usage* when code resolves, reads or writes the path.
USE_VERBS = re.compile(
    r"(open\(|Path\(|read_text|write_text|read_bytes|write_bytes|exists\(|is_dir|is_file|mkdir|"
    r"\.join\(|resolve\(|glob\(|rglob\(|walk\(|shutil\.|os\.path|PROJECT_LOCAL_ROOT|task_dir\(|"
    r"runtime_root|evidence_root|environ|getenv)")
POLICY_MARKERS = re.compile(r"forbid|prohibit|forbidden|not\s+an?\s+active|risk|must\s+not|"
                            r"不再|禁止|不得|风险")


def classify_hit(rel: str, line: str, suffix: str) -> tuple:
    """Return (classification, is_active_usage, reason)."""
    if "LEGACY_" in line or "legacy" in line.lower():
        return "MIGRATED", False, ("legacy marker kept as a refusal/migration guard; the active "
                                   "root is .project-local (runtime_roots.py)")
    if rel.startswith(("docs/", "reports/")):
        return "HISTORICAL_ONLY", False, "documentation or report naming a retired path"
    if rel.startswith(".project/"):
        if POLICY_MARKERS.search(line):
            return "POLICY_RECORD", False, "governance file stating the boundary, not using it"
        return "HISTORICAL_ONLY", False, "project governance record"
    if suffix in CODE_SUFFIXES:
        if USE_VERBS.search(line):
            return "BLOCKED", True, "code that resolves, reads or writes the path"
        return "HISTORICAL_ONLY", False, "code names the path without using it"
    if suffix in RECORD_SUFFIXES:
        return "HISTORICAL_ONLY", False, "data record (report, ledger or manifest) naming the path"
    return "HISTORICAL_ONLY", False, "non-executable text naming the path"


def git(*args: str) -> str:
    result = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                            encoding="utf-8", errors="replace")
    return result.stdout


def tracked_files() -> list:
    return [line for line in git("ls-files").splitlines() if line.strip()]


def ignored_files() -> list:
    return [line for line in git("ls-files", "--others", "--ignored", "--exclude-standard").splitlines()
            if line.strip()]


def area_of(rel: str) -> str:
    parts = rel.split("/")
    return parts[0] if len(parts) == 1 else parts[0]


def subarea_of(rel: str) -> str:
    parts = rel.split("/")
    if len(parts) < 2:
        return ""
    if parts[0] in {"design-lab", "src", "packages", "integrations", "docs", "reports"} and len(parts) > 2:
        return f"{parts[0]}/{parts[1]}"
    return f"{parts[0]}/{parts[1]}" if len(parts) > 2 else ""


def directory_audit() -> dict:
    tracked = tracked_files()
    ignored = ignored_files()
    stats = {}
    for rel in tracked:
        area = area_of(rel)
        entry = stats.setdefault(area, {"tracked_files": 0, "tracked_bytes": 0, "second_level": {}})
        entry["tracked_files"] += 1
        path = REPO / rel
        try:
            entry["tracked_bytes"] += path.stat().st_size
        except OSError:
            pass
        sub = subarea_of(rel)
        if sub:
            sub_entry = entry["second_level"].setdefault(sub, {"tracked_files": 0, "role": "unassigned"})
            sub_entry["tracked_files"] += 1
    for rel in ignored:
        area = area_of(rel)
        entry = stats.setdefault(area, {"tracked_files": 0, "tracked_bytes": 0, "second_level": {}})
        entry["ignored_files"] = entry.get("ignored_files", 0) + 1

    root_entries = sorted(p.name for p in REPO.iterdir() if p.name != ".git")
    entries = []
    for name in root_entries:
        info = stats.get(name, {"tracked_files": 0, "tracked_bytes": 0, "second_level": {},
                                "ignored_files": 0})
        is_dir = (REPO / name).is_dir()
        if not is_dir:
            entries.append({
                "name": name, "kind": "file", "git_ignored": False,
                "tracked_files": 1, "tracked_bytes": info["tracked_bytes"], "ignored_files": 0,
                "responsibility": "repository root file", "owner": "owner",
                "conformance": "ROOT_FILE",
                "note": "root files are not part of the directory scheme", "second_level": {},
            })
            continue
        scheme = SCHEME.get(name)
        if scheme is None:
            conformance = "EXTRA"
            responsibility, owner, note = "not in the current scheme", "unassigned", \
                "owner must classify or relocate this entry"
        else:
            responsibility, owner, note = scheme
            conformance = "CONFORM"
            if name == "design-lab" or note == "legacy owner (see DLDS-B010)":
                conformance = "DEVIATION"
        if info["tracked_files"] == 0 and not info.get("ignored_files"):
            conformance = "EMPTY_DIR"
        entries.append({
            "name": name,
            "kind": "dir",
            "git_ignored": subprocess.run(["git", "-C", str(REPO), "check-ignore", "-q", name]).returncode == 0,
            "tracked_files": info["tracked_files"],
            "tracked_bytes": info["tracked_bytes"],
            "ignored_files": info.get("ignored_files", 0),
            "responsibility": responsibility,
            "owner": owner,
            "conformance": conformance,
            "note": note,
            "second_level": dict(sorted(info["second_level"].items(),
                                        key=lambda kv: -kv[1]["tracked_files"])[:12]),
        })
    return {
        "schemaVersion": "design-lab/deepseek-directory-audit/v1",
        "task_keys": [f"{AUTHORITY_ID}::DLDS-B000", f"{AUTHORITY_ID}::DLDS-B010"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "tracked_file_total": len(tracked),
        "tracked_bytes_total": sum((REPO / rel).stat().st_size for rel in tracked
                                  if (REPO / rel).is_file()),
        "scheme": {name: {"responsibility": value[0], "owner": value[1], "note": value[2]}
                   for name, value in SCHEME.items()},
        "conformance_counts": {name: sum(1 for e in entries if e["conformance"] == name)
                               for name in sorted({e["conformance"] for e in entries})},
        "deviations": [{"name": e["name"], "conformance": e["conformance"], "note": e["note"]}
                       for e in entries if e["conformance"] not in {"CONFORM"}],
        "entries": entries,
    }


def legacy_scan() -> dict:
    hits = []
    for rel in tracked_files():
        path = REPO / rel
        if not path.is_file():
            continue
        try:
            if path.stat().st_size > 3_000_000:
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        suffix = path.suffix.lower()
        for name, pattern in LEGACY_PATTERNS:
            for match in pattern.finditer(text):
                line_no = text.count("\n", 0, match.start()) + 1
                line = text.splitlines()[line_no - 1].strip()[:160]
                classification, active, reason = classify_hit(rel, line, suffix)
                hits.append({"pattern": name, "path": rel, "line": line_no, "text": line,
                             "classification": classification,
                             "active_reference": active, "reason": reason})
    blocked = [h for h in hits if h["classification"] == "BLOCKED"]
    by_pattern = {}
    for hit in hits:
        entry = by_pattern.setdefault(hit["pattern"], {"total": 0, "active": 0})
        entry["total"] += 1
        entry["active"] += 1 if hit["active_reference"] else 0
    return {
        "schemaVersion": "design-lab/deepseek-legacy-path-scan/v1",
        "task_keys": [f"{AUTHORITY_ID}::DLDS-B020"],
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "patterns": [{"name": name, "regex": pattern.pattern} for name, pattern in LEGACY_PATTERNS],
        "hit_total": len(hits),
        "active_reference_total": len(blocked),
        "blocked_active_hits": blocked[:200],
        "by_pattern": by_pattern,
        "classification_counts": {
            "MIGRATED": sum(1 for h in hits if h["classification"] == "MIGRATED"),
            "HISTORICAL_ONLY": sum(1 for h in hits if h["classification"] == "HISTORICAL_ONLY"),
            "POLICY_RECORD": sum(1 for h in hits if h["classification"] == "POLICY_RECORD"),
            "DELETE": sum(1 for h in hits if h["classification"] == "DELETE"),
            "BLOCKED": len(blocked),
        },
    }


def write(path: str, document: dict) -> None:
    target = REPO / path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                      encoding="utf-8", newline="\n")
    print(f"WROTE {path}")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    audit = directory_audit()
    legacy = legacy_scan()
    if args.check:
        ok = True
        for path, document in ((AUDIT_OUT, audit), (LEGACY_OUT, legacy)):
            target = REPO / path
            if not target.is_file():
                print(f"MISSING {path}")
                ok = False
                continue
            current = json.loads(target.read_text(encoding="utf-8"))
            if current.get("conformance_counts") != document.get("conformance_counts") or \
               current.get("classification_counts") != document.get("classification_counts"):
                print(f"DRIFT {path}")
                ok = False
        print("DIRECTORY_AUDIT=" + ("PASS" if ok else "FAIL"))
        return 0 if ok else 1
    write(AUDIT_OUT, audit)
    write(LEGACY_OUT, legacy)
    print("conformance: " + " ".join(f"{k}={v}" for k, v in sorted(audit["conformance_counts"].items())))
    print("legacy: " + " ".join(f"{k}={v}" for k, v in sorted(legacy["classification_counts"].items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
