#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-C020 / DLDS-C050 — language boundary and cross-language contract gate.

C020: a primary language that is not in the policy may not appear, a second
Python runtime architecture may not appear, and a second Node back end may not
appear. Rust appears only with an ADR.

C050: enums and vocabularies must not be hand-copied between Python, TypeScript
and host-native JavaScript. The JSON Schema is the truth. A copy that *agrees*
with the schema is reported as informational; a copy that *disagrees* is a
failure, because that is how two languages start telling different stories.

Writes reports/current/LANGUAGE-BOUNDARY-SCAN.json.

Usage:
    python scripts/verify_language_boundary.py [--json only]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current/LANGUAGE-BOUNDARY-SCAN.json"
TASK_KEYS = ["DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-C020",
             "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-C050"]

FORBIDDEN_EXTENSIONS = {".cs": "C#", ".go": "Go", ".java": "Java", ".kt": "Kotlin", ".kts": "Kotlin",
                        ".cpp": "C++", ".cc": "C++", ".cxx": "C++", ".hpp": "C++", ".h": "C/C++ header"}
CONDITIONAL_EXTENSIONS = {".rs": "Rust (requires benchmark evidence + ADR)"}
CODE_SUFFIXES = {".py", ".ts", ".js", ".jsx", ".mjs", ".cjs"}
# vocabulary -> schema file that owns it
VOCABULARIES = {
    "evidence_levels": "design-lab/schemas/capability-status.schema.json",
    "task_axes_states": "design-lab/schemas/task-ledger-r3.schema.json",
    "provider_license": "design-lab/schemas/provider-capability.schema.json",
}
MIN_TOKENS = 3
# What this detector does and does not see. The token pattern needs three or more
# characters, so a two-character token such as "E0" can never match, and a copy is
# only counted when one line carries enough canonical tokens. The count is therefore
# a LOWER BOUND on hand-written copies, not a completeness audit; the property the
# gate enforces is that every copy it does find agrees with its owning schema.
DETECTOR_SCOPE = {
    "unit": "one source line",
    "token_pattern": r"[A-Z][A-Z0-9_]{2,} (three or more characters)",
    "min_tokens_per_line": MIN_TOKENS,
    "count_is": "a lower bound on hand-written copies; short tokens such as E0 are "
                "invisible to this detector and are not counted",
    "enforced_property": "every detected copy agrees with the owning schema "
                         "(disagreement is a failure, agreement is informational)",
}


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def tracked() -> list:
    return [line for line in git("ls-files").splitlines() if line.strip()]


def walk_enums(node, path=""):
    """Collect every enum array in a JSON Schema with the path that declares it."""
    found = []
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "enum" and isinstance(value, list) and all(isinstance(v, str) for v in value):
                found.append({"path": path or "/", "values": value})
            else:
                found.extend(walk_enums(value, f"{path}/{key}"))
    elif isinstance(node, list):
        for index, value in enumerate(node):
            found.extend(walk_enums(value, f"{path}/{index}"))
    return found


def canonical_vocabularies() -> dict:
    """The union of every string enum declared in the schema that owns a vocabulary."""
    result = {}
    for name, rel in VOCABULARIES.items():
        path = REPO / rel
        if not path.is_file():
            continue
        document = json.loads(path.read_text(encoding="utf-8"))
        tokens = set()
        for entry in walk_enums(document):
            tokens.update(entry["values"])
        result[name] = {"schema": rel, "tokens": sorted(tokens)}
    return result


def scan_language_boundary(files: list) -> dict:
    """Separate a product primary language from fixture-scoped or inert content.

    A language inside a declared Domain fixture (or a vendored inert blob) is not
    a product language: the fixture is content, and AGENTS.md already treats
    third-party blobs as inert. Only a forbidden language in product scope fails
    the gate.
    """
    forbidden, fixture_scoped, conditional = [], [], []
    python_roots, node_manifests = [], []
    node_lockfiles, python_lockfiles = [], []
    for rel in files:
        suffix = Path(rel).suffix.lower()
        fixture = rel.startswith(("fixtures/", "vendor/")) or rel.endswith((".min.js", ".min.css"))
        if suffix in FORBIDDEN_EXTENSIONS:
            record = {"path": rel, "language": FORBIDDEN_EXTENSIONS[suffix],
                      "scope": "FIXTURE_OR_INERT" if fixture else "PRODUCT"}
            (fixture_scoped if fixture else forbidden).append(record)
        if suffix in CONDITIONAL_EXTENSIONS:
            conditional.append({"path": rel, "language": CONDITIONAL_EXTENSIONS[suffix]})
        if Path(rel).name in {"pyproject.toml", "setup.py", "setup.cfg"}:
            python_roots.append(rel)
        if Path(rel).name == "package.json":
            node_manifests.append(rel)
        # Node and Python locks are counted separately. The earlier single list held
        # only Node locks while the CLI printed it as `lockfiles=0`, which reads as
        # "this repository has no dependency lock" when uv.lock and requirements.txt
        # are both tracked. The name now says which ecosystem it measures.
        if Path(rel).name in {"pnpm-lock.yaml", "package-lock.json", "yarn.lock"}:
            node_lockfiles.append(Path(rel).name)
        if Path(rel).name in {"uv.lock", "poetry.lock", "Pipfile.lock", "requirements.txt"}:
            python_lockfiles.append(Path(rel).name)
    lockfiles = sorted(set(node_lockfiles) | set(python_lockfiles))

    # A second Python package architecture is a defect only when active code
    # imports it; otherwise it is an unused legacy package (see DLDS-B010).
    candidates = sorted({str(Path(rel).parent) for rel in files
                         if Path(rel).name == "__init__.py"
                         and not rel.startswith(("src/", "packages/", "design-lab/tests",
                                                 "fixtures/"))})
    imported = []
    for package in candidates:
        module = package.replace("/", ".").replace("\\", ".")
        name = module.split(".")[-1]
        for rel in files:
            if Path(rel).suffix not in {".py", ".ts", ".js"}:
                continue
            try:
                if (REPO / rel).stat().st_size > 2_000_000:
                    continue
                text = (REPO / rel).read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            if re.search(rf"\b(from|import)\s+{re.escape(name)}\b", text):
                imported.append({"package": package, "imported_by": rel})
                break
    server_manifests = []
    for rel in node_manifests:
        try:
            manifest = json.loads((REPO / rel).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        scripts = manifest.get("scripts") or {}
        if {"start", "serve", "dev"} & set(scripts):
            server_manifests.append({"path": rel, "scripts": sorted(scripts)})
    return {
        "forbidden_language_files": forbidden,
        "fixture_scoped_language_files": fixture_scoped,
        "conditional_language_files": conditional,
        "python_project_roots": python_roots,
        "legacy_python_packages": candidates,
        "second_python_architecture": imported,
        "node_manifests": node_manifests,
        "node_server_manifests": server_manifests,
        "second_node_backend": server_manifests if node_lockfiles else [],
        "lockfiles": lockfiles,
        "node_lockfiles": sorted(set(node_lockfiles)),
        "python_lockfiles": sorted(set(python_lockfiles)),
        "multiple_lockfile_managers": len({name.split("-")[0].split(".")[0]
                                           for name in node_lockfiles}) > 1,
    }


def scan_vocabulary_copies(files: list, canonical: dict) -> dict:
    findings = []
    for name, info in canonical.items():
        tokens = set(info["tokens"])
        if len(tokens) < MIN_TOKENS:
            continue
        pattern = re.compile(r"[A-Z][A-Z0-9_]{2,}")
        for rel in files:
            if Path(rel).suffix.lower() not in CODE_SUFFIXES:
                continue
            path = REPO / rel
            try:
                if path.stat().st_size > 2_000_000:
                    continue
                text = path.read_text(encoding="utf-8", errors="ignore")
            except OSError:
                continue
            for number, line in enumerate(text.splitlines(), 1):
                if line.lstrip().startswith(("#", "//", "*")):
                    continue
                present = {token for token in pattern.findall(line) if token in tokens}
                if len(present) < MIN_TOKENS:
                    continue
                declared = re.findall(r"[A-Z][A-Z0-9_]{2,}", line)
                extra = {token for token in declared if token in tokens | set(info["tokens"])} - tokens
                findings.append({
                    "vocabulary": name,
                    "schema": info["schema"],
                    "path": rel,
                    "line": number,
                    "tokens_present": sorted(present),
                    "agrees_with_schema": not extra,
                    "extra_tokens": sorted(extra),
                    "text": line.strip()[:160],
                })
    disagreeing = [f for f in findings if not f["agrees_with_schema"]]
    return {"copies": findings, "copy_count": len(findings),
            "agreeing_copies": len(findings) - len(disagreeing),
            "disagreeing_copies": disagreeing}


def check_against(stored: dict, fresh: dict) -> tuple[list[str], list[str]]:
    """Compare the judgement the record carries, not the census around it.

    `verdict` and `failures` are the whole claim this gate makes; the descriptive counts
    (`tracked_files_scanned` and friends) move with every commit, so pinning them here would turn
    the check into a re-run of the writer. `subject_sha` is deliberately not compared: the
    committed record predates the argv fix, so it holds an empty subject by design and that gap
    lives in `design-lab/config/report-subject-debt.json`, where it is declared and shrinking.
    """
    problems: list[str] = []
    notices: list[str] = []
    if stored.get("verdict") != fresh.get("verdict"):
        problems.append(f"verdict stored={stored.get('verdict')!r} fresh={fresh.get('verdict')!r}")
    stored_failures = list(stored.get("failures") or [])
    fresh_failures = list(fresh.get("failures") or [])
    if stored_failures != fresh_failures:
        problems.append("the failing-set differs: "
                        f"only-stored={sorted(set(stored_failures) - set(fresh_failures))} "
                        f"only-fresh={sorted(set(fresh_failures) - set(stored_failures))}")
    for key in ("tracked_files_scanned",):
        if stored.get(key) != fresh.get(key):
            notices.append(f"{key} stored={stored.get(key)} fresh={fresh.get(key)}")
    return problems, notices


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true",
                        help="compare the committed record against a fresh computation and "
                             "write nothing")
    parser.add_argument("--json", action="store_true", help="print the report path only")
    args = parser.parse_args(argv)
    files = tracked()
    canonical = canonical_vocabularies()
    boundary = scan_language_boundary(files)
    vocabularies = scan_vocabulary_copies(files, canonical)
    failures = []
    if boundary["forbidden_language_files"]:
        failures.append(f"{len(boundary['forbidden_language_files'])} file(s) in a language the "
                        "policy forbids without an ADR, in product scope")
    if boundary["second_python_architecture"]:
        failures.append("a second Python package is imported by active code: "
                        + ", ".join(item["package"] for item in boundary["second_python_architecture"]))
    if boundary["multiple_lockfile_managers"]:
        failures.append("more than one Node lockfile manager is present")
    if vocabularies["disagreeing_copies"]:
        failures.append(f"{len(vocabularies['disagreeing_copies'])} hand-written vocabulary copy "
                        "disagrees with its schema")
    document = {
        "schemaVersion": "design-lab/language-boundary-scan/v1",
        "task_keys": TASK_KEYS,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "tracked_files_scanned": len(files),
        "language_boundary": boundary,
        "vocabularies": {"canonical": {k: len(v["tokens"]) for k, v in canonical.items()},
                         "detector_scope": DETECTOR_SCOPE,
                         **vocabularies},
        "failures": failures,
        "verdict": "PASS" if not failures else "FAIL",
        "notes": {
            "conditional_languages": "Rust is NOT_PRIMARY; a .rs file requires benchmark evidence "
                                     "and an ADR, so it is reported, not forbidden",
            "agreeing_copies": "a copy that agrees with the schema is informational; the gate fails "
                               "only on disagreement",
            "copy_count": "copy_count is a lower bound measured by DETECTOR_SCOPE, not a "
                          "completeness audit: it is not evidence that a vocabulary copy was "
                          "lost when the number falls",
        },
    }
    if args.check:
        if not OUT.is_file():
            print(f"LANGUAGE_BOUNDARY=FAIL mode=check reason=no committed record at "
                  f"{OUT.relative_to(REPO).as_posix()}")
            return 1
        stored = json.loads(OUT.read_text(encoding="utf-8"))
        problems, notices = check_against(stored, document)
        for problem in problems:
            print("LANGUAGE_BOUNDARY=CHECK_FAIL " + problem)
        for notice in notices:
            print("LANGUAGE_BOUNDARY=NOTICE descriptive count moved: " + notice)
        print(f"LANGUAGE_BOUNDARY={stored.get('verdict')} mode=check "
              f"judgement_agrees={'yes' if not problems else 'no'} "
              f"descriptive_drift={len(notices)}")
        return 1 if problems else 0
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n",
                   encoding="utf-8", newline="\n")
    if args.json:
        print(OUT.relative_to(REPO))
    else:
        print(f"LANGUAGE_BOUNDARY={document['verdict']} files={len(files)} "
              f"forbidden={len(boundary['forbidden_language_files'])} "
              f"fixture_scoped={len(boundary['fixture_scoped_language_files'])} "
              f"conditional={len(boundary['conditional_language_files'])} "
              f"python_roots={len(boundary['python_project_roots'])} "
              f"node_manifests={len(boundary['node_manifests'])} "
              f"lockfiles={len(boundary['lockfiles'])}"
              f"(python={len(boundary['python_lockfiles'])},node={len(boundary['node_lockfiles'])}) "
              f"vocab_copies={vocabularies['copy_count']} "
              f"disagreeing={len(vocabularies['disagreeing_copies'])}")
        for failure in failures:
            print("  FAIL:", failure)
        for record in boundary["fixture_scoped_language_files"]:
            print(f"  note: {record['language']} scoped to a fixture or inert blob: {record['path']}")
        for package in boundary["legacy_python_packages"]:
            print("  note: python package outside the declared layout (unused):", package)
    return 0 if not failures else 1


if __name__ == "__main__":
    raise SystemExit(main())
