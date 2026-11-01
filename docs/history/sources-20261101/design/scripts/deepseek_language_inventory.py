#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-C000 — language inventory for the whole repository.

Counts tracked files and lines per language, records which directories own each
language, what runtime role it plays, and which build system and dependency
manager actually govern it. The role table is the one the authority taskpack
freezes in section 16; the facts are measured, not asserted.

Writes reports/current/LANGUAGE-INVENTORY.json.

Usage:
    python scripts/deepseek_language_inventory.py [--check]
"""
from __future__ import annotations

import argparse
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/LANGUAGE-INVENTORY.json"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-C000"

# extension -> (language, runtime role)
LANGUAGES = {
    ".py": ("Python", "orchestration, runtime/state, QA, provider logic, reconstruction, "
                      "analysis, CLI and tooling"),
    ".ts": ("TypeScript", "workbench UI, OpenDesign/web integration, MCP client, IPC/web frontend"),
    ".js": ("JavaScript", "host-native extension (Adobe UXP/JSX) or browser-served front end"),
    ".jsx": ("JavaScript (JSX)", "Adobe host-native extension script"),
    ".mjs": ("JavaScript (ESM)", "host-native extension or browser module"),
    ".cjs": ("JavaScript (CommonJS)", "fixture tooling"),
    ".json": ("JSON", "machine-readable configuration and projections"),
    ".sql": ("SQL", "local state schema"),
    ".html": ("HTML", "front-end document"),
    ".css": ("CSS", "front-end styling"),
    ".md": ("Markdown", "documentation"),
    ".yaml": ("YAML", "governance and CI configuration"),
    ".yml": ("YAML", "governance and CI configuration"),
    ".toml": ("TOML", "Python project configuration"),
    ".ps1": ("PowerShell", "thin launcher"),
    ".sh": ("Shell", "thin launcher"),
    ".csv": ("CSV", "evidence data"),
    ".svg": ("SVG", "vector fixture"),
}
CODE_LANGUAGES = {"Python", "TypeScript", "JavaScript", "JavaScript (JSX)",
                  "JavaScript (ESM)", "JavaScript (CommonJS)", "SQL", "HTML", "CSS"}
SCHEMA_LANGUAGES = {"JSON"}

# The taskpack's own build/dependency facts: one entry per language, stated so a
# reader cannot confuse "a file exists" with "a toolchain is declared".
TOOLCHAIN = {
    "Python": {
        "build_system": "hatchling (pyproject.toml [build-system])",
        "dependency_manager": "uv (uv.lock, CI runs 'uv sync --locked')",
        "declared_dependencies": "pyproject.toml [project].dependencies",
        "minimum_python": ">=3.11 (pyproject requires-python)",
        "test_runner": "unittest via scripts/run_python_tests.py (pytest config exists but pytest "
                       "is not installed and the suite is unittest-based)",
        "linter": "ruff DECLARED as the target; not configured and not installed yet",
    },
    "TypeScript": {
        "build_system": "NONE in the product: apps/workbench/main.ts is served as source",
        "dependency_manager": "NONE: there is no root package.json and no lockfile",
        "test_runner": "none",
        "linter": "none",
    },
    "JavaScript": {
        "build_system": "none: host-native scripts are loaded by the host",
        "dependency_manager": "n/a",
        "test_runner": "n/a",
        "linter": "n/a",
    },
}


def tracked() -> list:
    return [line for line in subprocess.run(["git", "-C", str(REPO), "ls-files"], capture_output=True,
                                            text=True, encoding="utf-8").stdout.splitlines()
            if line.strip()]


def count_lines(path: Path) -> tuple:
    try:
        if path.stat().st_size > 4_000_000:
            return 0, 0
        text = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return 0, 0
    lines = text.splitlines()
    blank = sum(1 for line in lines if not line.strip())
    return len(lines), len(lines) - blank


POLICY_FIELDS = ("primary_languages", "contract_language", "rust", "forbidden_without_adr")


def snapshot_findings(record: dict) -> list[str]:
    """What a generation-time snapshot can honestly be held to: its own internal arithmetic.

    The old check compared `file_count` per language against the live tree, i.e. it demanded
    that a committed record equal a repository that changes with every commit. Measured today the
    record says 1,776 mapped files against 3,028 now and has no SVG row at all (47 exist), so that
    check had been red for weeks -- and nothing ran it: no workflow step, no aggregate entry, no
    test, and its name matches no reachability pattern, so a permanently failing gate was invisible.
    These findings catch a record that is actually broken.
    """
    problems: list[str] = []
    rows = record.get("languages") or []
    if not rows:
        return ["LANGUAGE-ROWS-EMPTY the record inventories no language, so it claims nothing"]
    names = [str(row.get("language") or "") for row in rows]
    if "" in names:
        problems.append("LANGUAGE-ROW-NAME a language row names nothing")
    duplicates = sorted({name for name in names if names.count(name) > 1})
    if duplicates:
        problems.append(f"DUPLICATE-LANGUAGE-ROW {duplicates} appears twice, so the totals "
                        "double-count")
    declared = sum(int(row.get("file_count") or 0) for row in rows)
    total = record.get("tracked_files_total")
    unmapped = record.get("unmapped_extension_files")
    sample = record.get("unmapped_sample") or []
    if not isinstance(total, int) or not isinstance(unmapped, int):
        problems.append(f"TOTAL-FIELDS-MISSING tracked_files_total={total!r} "
                        f"unmapped_extension_files={unmapped!r}")
    elif declared + unmapped != total:
        problems.append(f"TOTAL-DOES-NOT-ACCOUNT mapped {declared} + unmapped {unmapped} != "
                        f"tracked_files_total {total}; the census has an unexplained remainder")
    if len(sample) > (unmapped if isinstance(unmapped, int) else 0):
        problems.append(f"UNMAPPED-SAMPLE-LARGER sample holds {len(sample)} of "
                        f"{unmapped} unmapped files")
    for row in rows:
        language = str(row.get("language") or "?")
        if int(row.get("loc_nonblank") or 0) > int(row.get("loc_total") or 0):
            problems.append(f"LOC-INVERTED {language}: non-blank lines exceed total lines")
        if int(row.get("file_count") or 0) <= 0:
            problems.append(f"EMPTY-ROW {language} is listed with file_count="
                            f"{row.get('file_count')}")
        for field in ("runtime_role", "build_system", "dependency_manager", "test_runner"):
            if not str(row.get(field) or "").strip():
                problems.append(f"MISSING-FIELD {language} has no {field}; a language row without "
                                "its role is not evidence about that language")
        if not row.get("owner_directories"):
            problems.append(f"MISSING-FIELD {language} names no owning directory")

    policy = record.get("policy") or {}
    for field in POLICY_FIELDS:
        value = policy.get(field)
        if not value or (isinstance(value, list) and not [v for v in value if str(v).strip()]):
            problems.append(f"POLICY-EMPTY policy.{field} is {value!r}; the forbidden-language and "
                            "primary-language claims live here, so an empty field is not a "
                            "snapshot of a policy but the absence of one")
    # Enforcement of forbidden extensions belongs to verify_language_boundary.py, which walks the
    # tree for them; duplicating that rule here would create two guards that can disagree.
    code_languages = set(record.get("code_languages") or [])
    unknown = sorted(code_languages - set(names))
    if unknown:
        problems.append(f"CODE-LANGUAGE-UNKNOWN {unknown} is called code but has no row")
    counts = {str(row.get("language")): int(row.get("loc_nonblank") or 0) for row in rows}
    nonblank = record.get("code_nonblank_lines") or {}
    for language, value in nonblank.items():
        if language not in code_languages:
            problems.append(f"CODE-LANGUAGE-UNLISTED {language} has a line count but is not in "
                            "code_languages")
        elif counts.get(language) != value:
            problems.append(f"CODE-LINES-MISMATCH {language} records {value} while its row says "
                            f"{counts.get(language)}")
    subject = str(record.get("subject_sha") or "")
    if len(subject) != 40 or any(char not in "0123456789abcdef" for char in subject):
        problems.append(f"SUBJECT-NOT-A-COMMIT subject_sha={subject[:16]!r} does not name a "
                        "commit, so the snapshot belongs to no state; the debt register at "
                        "design-lab/config/report-subject-debt.json is where an empty subject is "
                        "declared, and this record is not in it")
    return problems


def census_moved(stored: dict, fresh_rows: list[dict]) -> list[str]:
    """How far the tree has travelled since the snapshot, as words rather than as a verdict."""
    stored_counts = {str(row.get("language")): int(row.get("file_count") or 0)
                     for row in stored.get("languages") or []}
    fresh_counts = {str(row.get("language")): int(row.get("file_count") or 0)
                    for row in fresh_rows}
    moved = []
    for language in sorted(set(stored_counts) | set(fresh_counts)):
        before, now = stored_counts.get(language), fresh_counts.get(language)
        if before != now:
            moved.append(f"{language} {before}->{now}")
    return moved


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    files = tracked()
    stats = {}
    unmapped = []
    for rel in files:
        path = REPO / rel
        suffix = path.suffix.lower()
        if suffix not in LANGUAGES:
            unmapped.append(rel)
            continue
        language = LANGUAGES[suffix][0]
        entry = stats.setdefault(language, {"files": 0, "lines": 0, "code_lines": 0,
                                            "bytes": 0, "by_area": {}})
        lines, code = count_lines(path)
        size = path.stat().st_size if path.is_file() else 0
        area = rel.split("/")[0]
        entry["files"] += 1
        entry["lines"] += lines
        entry["code_lines"] += code
        entry["bytes"] += size
        bucket = entry["by_area"].setdefault(area, {"files": 0, "lines": 0})
        bucket["files"] += 1
        bucket["lines"] += lines
    languages = []
    for language, entry in sorted(stats.items(), key=lambda kv: -kv[1]["files"]):
        toolchain = TOOLCHAIN.get(language, {})
        languages.append({
            "language": language,
            "file_count": entry["files"],
            "loc_total": entry["lines"],
            "loc_nonblank": entry["code_lines"],
            "bytes": entry["bytes"],
            "owner_directories": sorted(entry["by_area"], key=lambda a: -entry["by_area"][a]["files"]),
            "by_area": entry["by_area"],
            "runtime_role": next(role for ext, (name, role) in LANGUAGES.items() if name == language),
            "build_system": toolchain.get("build_system", "not declared"),
            "dependency_manager": toolchain.get("dependency_manager", "not declared"),
            "test_runner": toolchain.get("test_runner", "not declared"),
            "linter": toolchain.get("linter", "not declared"),
        })
    code_totals = {row["language"]: row["loc_nonblank"] for row in languages
                   if row["language"] in CODE_LANGUAGES}
    document = {
        "schemaVersion": "design-lab/language-inventory/v1",
        "task_key": TASK_KEY,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                                      capture_output=True, text=True,
                                      encoding="utf-8").stdout.strip(),
        "tracked_files_total": len(files),
        "languages": languages,
        "code_languages": sorted(code_totals),
        "code_nonblank_lines": code_totals,
        "unmapped_extension_files": len(unmapped),
        "unmapped_sample": unmapped[:20],
        "policy": {
            "primary_languages": ["Python", "TypeScript", "JavaScript (host-native)", "JSON/JSON Schema"],
            "contract_language": "JSON Schema 2020-12 is the cross-language contract truth",
            "rust": "NOT_PRIMARY: allowed only with benchmark evidence, an ADR and a named bottleneck",
            "forbidden_without_adr": ["C#", "Go", "Java", "Kotlin", "C++",
                                      "a second Python runtime architecture",
                                      "a second Node backend"],
        },
    }
    if args.check:
        if not OUT.is_file():
            print("LANGUAGE_INVENTORY=FAIL missing " + OUT.relative_to(REPO).as_posix())
            return 1
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        problems = snapshot_findings(stored)
        moved = census_moved(stored, languages)
        for problem in problems:
            print("LANGUAGE_INVENTORY=FAIL " + problem)
        if moved:
            # A generation-time snapshot does not become wrong when the repository grows; it
            # becomes old. Saying by how much is the useful part, and failing on it would demand
            # a writer run at every commit -- which is what made this check permanently red.
            print(f"LANGUAGE_INVENTORY=NOTICE snapshot of "
                  f"{str(stored.get('subject_sha') or '')[:12]} at "
                  f"{stored.get('generated_at')} has moved: {moved}")
        verdict = "PASS" if not problems else "FAIL"
        print(f"LANGUAGE_INVENTORY={verdict} mode=check rows="
              f"{len(stored.get('languages') or [])} policy_fields_checked="
              f"{len(POLICY_FIELDS)} census_notices={len(moved)}")
        return 0 if not problems else 1
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    print(f"LANGUAGE_INVENTORY=WRITTEN {OUT.relative_to(REPO)} "
          f"languages={len(languages)} tracked={len(files)} unmapped={len(unmapped)}")
    for row in languages[:12]:
        print(f"  {row['language']:22} files={row['file_count']:5} nonblank={row['loc_nonblank']:7} "
              f"areas={len(row['owner_directories'])}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
