# SPDX-License-Identifier: MIT
"""Top-level entry anti-drift check for the fused repository.

Why this exists: the merge of WORK-LAB and DESIGN-LAB is a decision about the *project*, and a
decision is not a migration report. The three root entries (``PROJECT_CURRENT.md``, ``README.md``,
``AGENTS.md``) are the first thing a new agent reads, so a stale figure or a leftover
"two separate products" framing there is worse than stale prose deeper in the repo -- it becomes
the premise the next session reasons from. This script re-derives every figure the entry quotes
from the registers on disk, resolves every repository path the entries cite, and refuses on
mismatch instead of printing advice.

Modes (exit codes are part of the contract, consumers depend on them):
  --check        0 clean, 1 findings, 3 a required input could not be read
  --print-block  0 and prints the figures block --check expects; the document is refreshed from
                 this output, never by typing numbers
  --json         the machine-readable report (default on --check)
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ENTRY = "PROJECT_CURRENT.md"
#: the promoted October-current authorities, listed at the repository root by owner rule
AUTHORITY_INDEX = "AUTHORITY-INDEX.md"
REQUIRED_ENTRIES = ("PROJECT_CURRENT.md", "README.md", "AGENTS.md", AUTHORITY_INDEX,
                    "LICENSE", "SECURITY.md", "CONTRIBUTING.md")
#: documents whose path-shaped tokens are claims about *this* repository. AUTHORITY-INDEX.md is
#: deliberately left out: its third column names paths inside the *source* repositories, and its
#: destinations are already verified byte by byte in check_authority_index().
CITING_ENTRIES = ("PROJECT_CURRENT.md", "README.md", "AGENTS.md",
                  "SECURITY.md", "CONTRIBUTING.md", "docs/LICENSING.md")
FIGURES_START = "<!-- entry-figures:start -->"
FIGURES_END = "<!-- entry-figures:end -->"
#: root directories a citation may start with; anything else is prose, not a path claim
KNOWN_ROOTS = ("apps", "backend", "config", "design-lab", "docs", "domains", "integrations",
               "migration", "packages", "research", "scripts", "tests", "vendor", "workspace")
ROOT_FILES = ("INTEGRATION_POLICY.md", "pyproject.toml", "README.md", "AGENTS.md",
              "PROJECT_CURRENT.md", ".gitattributes", ".gitignore")
#: wording that would re-assert the pre-merge identity as the current one
STALE = ("两个独立项目", "两个产品分别", "各自独立的产品", "仍是两个", "分别维护两套")
#: a line that names one of these is *talking about* the old framing, not using it
NEGATION = ("不", "未", "历史", "旧", "取代", "已替代", "排除", "不再是")
AUTHORITY_MARK = "唯一顶层入口"
BLOCKING_QUEUE = "L10#0"
ARCHIVE_REGISTER = "migration/archive-object-reconciliation-20261101.csv"
ARCHIVE_AREA = "docs/history/sources-20261101/MANIFEST.json"
ARCHIVE_IMPORT = "docs/history/archive-objects-20261101/ARCHIVE-OBJECTS-MANIFEST.csv"
TEST_CENSUS = "tests/node-census.json"
#: every disposition the reconciliation register is allowed to carry -- "we have not
#: decided yet" is deliberately absent, that is the state this check exists to forbid
ADMITTED_DISPOSITIONS = frozenset({
    "ARCHIVED_IN_REPO", "RECORDED_NOT_COPIED", "EXCLUDED_BY_OWNER_RULE",
    "REGISTERED_NOT_MIGRATED", "UNCLASSIFIED_RESIDUE"})


def rows(rel: str) -> list[dict]:
    raw = (ROOT / rel).read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw, newline="")))


#: areas whose bytes are attested elsewhere (digests in migration/copies.json and the manifests),
#: so their line endings are lineage, not taste -- never reformat them
BLOB_AREAS = ("docs/history/", "docs/authority-202610/", "domains/design/design_lab/resources/",
              "vendor/")


def _tracked_files(*patterns: str) -> list:
    listing = subprocess.run(["git", "ls-files", "-z", *patterns], cwd=str(ROOT),
                             capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout
    return [rel for rel in listing.split(chr(0)) if rel]


def line_endings() -> dict:
    """Tracked files that are purely CRLF, and those that contain LF, outside the attested areas.

    This number may fall (a real repair, one file at a time, with its digest re-attested) but may
    never grow: a new file written on the wrong side of that boundary silently expands the mix that
    `* -text` and the migration ledger are there to keep honest.
    """
    crlf = lf = 0
    for rel in _tracked_files():
        normalised = rel.replace(chr(92), "/")
        if any(normalised.startswith(area) for area in BLOB_AREAS):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        blob = path.read_bytes()
        pairs, ends = blob.count(b"\r\n"), blob.count(b"\n")
        if pairs and ends == pairs:
            crlf += 1
        elif ends:
            lf += 1
    return {"crlf": crlf, "lf": lf}


def spdx_claims() -> dict:
    """Well-formed SPDX lines in tracked Python, and the near-misses that would read as MIT anyway."""
    good = sloppy = missing = 0
    for rel in _tracked_files("*.py"):
        normalised = rel.replace(chr(92), "/")
        if any(normalised.startswith(area) for area in BLOB_AREAS):
            continue
        path = ROOT / rel
        if not path.is_file():
            continue
        head = path.read_bytes()[:400].decode("utf-8", errors="replace")
        claim = next((line for line in head.splitlines() if "SPDX-License-Identifier:" in line), None)
        if claim is None:
            missing += 1
        elif re.search(r"SPDX-License-Identifier:\s*[A-Za-z0-9.+-]+\s*$", claim):
            good += 1
        else:
            sloppy += 1
    return {"good": good, "sloppy": sloppy, "missing": missing}


def archive_summary() -> dict:
    """The history-area manifest as written by the copy run -- counts are read, never retyped."""
    document = json.loads((ROOT / ARCHIVE_AREA).read_text(encoding="utf-8"))
    actions = document["actions"]
    return dict(rows_total=document["rows_total"],
                actions={key: int(actions.get(key, 0)) for key in
                         ("COPIED", "DUPLICATED", "LINKED_IN_REPO", "LINKED_ARCHIVE",
                          "EXCLUDED_BY_OWNER_RULE", "FAILED")})


def derive_figures() -> dict:
    """Every figure the entry quotes, computed from the registers as they are right now."""
    work = rows("migration/source-coverage-work.csv")
    design = rows("migration/source-coverage-design.csv")
    work_paths = {row["path"] for row in work}
    design_paths = {row["path"] for row in design}
    copied = [row for row in work + design if row["class"].startswith("COPIED_")]
    acceptance = rows("migration/task-acceptance.csv")
    families = rows("migration/capability-family-register.csv")
    routes = rows("migration/route-surface.csv")
    unsettled = json.loads((ROOT / "migration" / "source-unsettled-detail-20261101.json")
                           .read_text(encoding="utf-8"))
    blockers = json.loads((ROOT / "config" / "blocker-register.json").read_text(encoding="utf-8"))
    accepted = Counter(row["结论"] for row in acceptance)
    verified = Counter(row["状态"] for row in families)
    archive = rows(ARCHIVE_REGISTER)
    ARCHIVE_SUMMARY = archive_summary()
    disposition = Counter(row["disposition"] for row in archive)
    hints = {row["source_hint"] for row in archive if row["source_hint"]}
    return {
        "archive_objects": len(archive),
        "archive_in_repo_objects": disposition["ARCHIVED_IN_REPO"],
        "archive_recorded_not_copied": disposition["RECORDED_NOT_COPIED"],
        "archive_excluded_raster_media": disposition["EXCLUDED_BY_OWNER_RULE"],
        "archive_registered_not_migrated": disposition["REGISTERED_NOT_MIGRATED"],
        "archive_unclassified_residue": disposition["UNCLASSIFIED_RESIDUE"],
        "archive_in_repo_bytes": sum(int(row["bytes"]) for row in archive
                                     if row["disposition"] == "ARCHIVED_IN_REPO"),
        "archive_import_verified": len(imported_rows()),
        "archive_source_hints": len(hints),
        "suite_test_files": json.loads((ROOT / TEST_CENSUS).read_text(encoding="utf-8"))["files"],
        "suite_test_nodes": json.loads((ROOT / TEST_CENSUS).read_text(encoding="utf-8"))["tests"],
        "crlf_tracked_files": line_endings()["crlf"],
        "lf_tracked_files": line_endings()["lf"],
        "spdx_claimed_files": spdx_claims()["good"],
        "spdx_malformed_lines": spdx_claims()["sloppy"],
        "source_rows_work": len(work),
        "source_rows_design": len(design),
        "source_rows_total": len(work) + len(design),
        "distinct_paths_work": len(work_paths),
        "distinct_paths_design": len(design_paths),
        "distinct_paths_union": len(work_paths | design_paths),
        "byte_copy_rows": len(copied),
        "task_acceptance_clauses": len(acceptance),
        "acceptance_confirmed": accepted["CONFIRMED"],
        "acceptance_partial": accepted["PARTIAL"],
        "acceptance_blocked_by_boundary": accepted["BLOCKED_BY_BOUNDARY"],
        "acceptance_deferred_p3": accepted["DEFERRED_P3"],
        "capability_families": len(families),
        "capability_implemented_verified": verified["IMPLEMENTED_VERIFIED"],
        "capability_partial": verified["PARTIAL"],
        "route_endpoints": len(routes),
        "unsettled_files": len(unsettled["rows"]),
        "authority_index_entries": len(_authority_rows()),
        "archive_manifest_rows": ARCHIVE_SUMMARY["rows_total"],
        "archived_objects_copied": ARCHIVE_SUMMARY["actions"]["COPIED"],
        "archived_objects_duplicated": ARCHIVE_SUMMARY["actions"]["DUPLICATED"],
        "archived_linked_in_repo": ARCHIVE_SUMMARY["actions"]["LINKED_IN_REPO"],
        "archived_linked_in_archive": ARCHIVE_SUMMARY["actions"]["LINKED_ARCHIVE"],
        "archived_excluded_cache_and_build": ARCHIVE_SUMMARY["actions"]["EXCLUDED_BY_OWNER_RULE"],
        "blocker_items": len(blockers["items"]),
    }


def parse_figures(text: str) -> dict:
    """The block the document carries, as {key: int}; a key without an integer is a finding."""
    if FIGURES_START not in text or FIGURES_END not in text:
        raise ValueError("MISSING_FIGURES_BLOCK")
    body = text.split(FIGURES_START, 1)[1].split(FIGURES_END, 1)[0]
    figures = {}
    for line in body.splitlines():
        match = re.fullmatch(r"([a-z][a-z0-9_]+)\s*=\s*(\d+)", line.strip())
        if match:
            figures[match.group(1)] = int(match.group(2))
        elif line.strip():
            raise ValueError("UNPARSEABLE_FIGURE_LINE " + repr(line[:60]))
    return figures


def cited_paths(text: str) -> list[str]:
    """Path-shaped tokens that claim to point into this repository.

    Only tokens whose first segment is a known root directory, or that name a root file outright,
    are treated as citations: a bare basename is not a path claim, and counting one would make the
    gate red on ordinary Chinese prose.
    """
    tokens = set()
    for match in re.finditer(r"[A-Za-z0-9_.\-/]+", text):
        token = match.group(0).strip("./")
        if not token or "." not in token and "/" not in token:
            continue
        head = token.split("/", 1)[0]
        # a token ending in -/_/* is shorthand for a family ("source-coverage-{work,design}",
        # "build_*.py"), not a claim that one path exists; the entry names the real files anyway
        if token.endswith(("-", "_", "*", ".")):
            continue
        if head in KNOWN_ROOTS or token in ROOT_FILES:
            tokens.add(token.split("#")[0])
    return sorted(tokens)


def tracked(path: str) -> bool:
    return bool(subprocess.run(["git", "ls-files", "--", path], cwd=str(ROOT),
                               capture_output=True, text=True,
                               encoding="utf-8", errors="replace").stdout.strip())


def check_entries(entry_path: Path) -> tuple[list, list]:
    """Returns (findings, machine_only_paths). Findings are strings that make the check red."""
    findings, machine_only = [], []
    for name in REQUIRED_ENTRIES:
        path = ROOT / name
        if not path.is_file():
            findings.append("ENTRY_MISSING " + name)
            continue
        if not tracked(name):
            findings.append("ENTRY_NOT_IN_GIT %s（一份克隆不会带上它，新 Agent 只能在这台机器上读到）" % name)

    entry_text = entry_path.read_text(encoding="utf-8") if entry_path.is_file() else ""
    readme_text = (ROOT / "README.md").read_text(encoding="utf-8") if (ROOT / "README.md").is_file() else ""
    agents_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8") if (ROOT / "AGENTS.md").is_file() else ""

    # identity must be in the first screenful, not somewhere the reader has to scroll to
    head_lines = [line for line in entry_text.splitlines()[:12] if line.strip()]
    joined = " ".join(head_lines)
    if "WORK-LAB" not in joined or "DESIGN-LAB" not in joined or "合并" not in joined:
        findings.append("IDENTITY_NOT_IN_FIRST_12_LINES " + joined[:80])

    # exactly one file may call itself the top-level entry
    claimants = [name for name in sorted(p.name for p in ROOT.glob("*.md"))
                 if AUTHORITY_MARK in (ROOT / name).read_text(encoding="utf-8", errors="replace")]
    if claimants != [ENTRY]:
        findings.append("SECOND_AUTHORITY %s（只允许 %s 自称%s）" % (claimants, ENTRY, AUTHORITY_MARK))

    if "PROJECT_CURRENT.md" not in "\n".join(readme_text.splitlines()[:10]):
        findings.append("README_DOES_NOT_LINK_ENTRY_IN_FIRST_10_LINES")
    for marker in ("必读顺序", "PROJECT_CURRENT.md", "更新责任"):
        if marker not in agents_text:
            findings.append("AGENTS_MISSING " + marker)

    for name in REQUIRED_ENTRIES:
        path = ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for line_no, line in enumerate(text.splitlines(), 1):
            for phrase in STALE:
                if phrase in line and not any(mark in line for mark in NEGATION):
                    findings.append("STALE_IDENTITY_WORDING %s:%d %s" % (name, line_no, phrase))

    # every top-level directory must be described by one of the entry documents: an undocumented
    # directory is where a future agent guesses, and guessing is how work drifts
    described = " ".join((ROOT / name).read_text(encoding="utf-8", errors="replace")
                         for name in CITING_ENTRIES if (ROOT / name).is_file())
    for entry in sorted(path.name for path in ROOT.iterdir()
                        if path.is_dir() and not path.name.startswith((".", "AI-WORK-LAB_"))):
        if entry not in described and not (entry + "/") in described:
            findings.append("ROOT_DIR_UNDOCUMENTED " + entry)
    for name in CITING_ENTRIES:
        path = ROOT / name
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        # a citation into .project-local names a run artefact Git does not carry: honest in the
        # entry, but it only resolves on the machine that ran the measurement, so record rather
        # than require it.
        machine_only += ["%s:%s" % (name, token) for token in
                         sorted(set(re.findall(r"[\w./\\-]*\.project-local[\w./\\-]*", text)))]
        for token in cited_paths(text):
            if not (ROOT / token).exists():
                findings.append("CITED_PATH_MISSING %s -> %s" % (name, token))
    malformed = spdx_claims()["sloppy"]
    if malformed:
        findings.append("SPDX_MALFORMED_LINES %d（声明读起来像 MIT，实际不合规）" % malformed)
    return findings, machine_only


def check_figures(entry_path: Path) -> list:
    if not entry_path.is_file():
        return ["ENTRY_MISSING " + str(entry_path)]
    try:
        stated = parse_figures(entry_path.read_text(encoding="utf-8"))
    except ValueError as exc:
        return [str(exc)]
    derived = derive_figures()
    findings = []
    for key in sorted(set(derived) | set(stated)):
        if key not in stated:
            findings.append("FIGURE_NOT_STATED " + key)
        elif key not in derived:
            findings.append("FIGURE_NOT_DERIVABLE " + key)
        elif stated[key] != derived[key]:
            findings.append("FIGURE_STALE %s 文档=%d 寄存器=%d" % (key, stated[key], derived[key]))
    blockers = json.loads((ROOT / "config" / "blocker-register.json").read_text(encoding="utf-8"))
    ids = [item.get("id") for item in blockers["items"]]
    if BLOCKING_QUEUE not in ids:
        findings.append("BLOCKING_QUEUE_MISSING " + BLOCKING_QUEUE)
    elif BLOCKING_QUEUE not in entry_path.read_text(encoding="utf-8"):
        findings.append("BLOCKING_QUEUE_NOT_DISCLOSED " + BLOCKING_QUEUE)
    return findings


def _authority_rows() -> list[list[str]]:
    """The promoted-authority table as cell lists, header and separator excluded."""
    path = ROOT / AUTHORITY_INDEX
    if not path.is_file():
        return []
    lines = [line for line in path.read_text(encoding="utf-8").splitlines()
             if line.startswith("|") and line.count("|") >= 9]
    body = [line for line in lines[1:] if not set(line.replace("|", "").strip()) <= {"-", " "}]
    return [[cell.strip() for cell in line.strip().strip("|").split("|")] for line in body]


def imported_rows() -> list:
    """The archive-object import, row by row -- each row must point at bytes this checkout holds."""
    path = ROOT / ARCHIVE_IMPORT
    return rows(ARCHIVE_IMPORT) if path.is_file() else []


def check_archive_coverage() -> list:
    """The anti-drift invariant: no archive object may sit in "we have not decided where it goes".

    Owner's instruction is 「确保内容全部归档到仓库 主要是防止任务漂移」. Completeness is what is
    asserted here, not how many bytes came in: every one of the archive's unique objects must carry a
    disposition in the admitted set, an object marked ARCHIVED_IN_REPO must really be on disk with the
    recorded digest, and an object deliberately left out must say why.
    """
    findings = []
    if not (ROOT / ARCHIVE_REGISTER).is_file():
        return ["ARCHIVE_REGISTER_MISSING"]
    for row in rows(ARCHIVE_REGISTER):
        # order matters and a plant proved it: judging "not in the admitted set" first would report
        # the undecided state as an unknown word and the dedicated finding below could never fire
        if row["disposition"] == "ARCHIVE_ONLY":
            findings.append("DESTINATION_UNDECIDED " + row["sha256"][:12])
        elif row["disposition"] not in ADMITTED_DISPOSITIONS:
            findings.append("UNKNOWN_DISPOSITION %s %s" % (row["sha256"][:12], row["disposition"]))
    import_rows = imported_rows()
    if not import_rows:
        findings.append("ARCHIVE_IMPORT_MANIFEST_MISSING")
    for row in import_rows:
        if row["action"] != "ARCHIVED_IN_REPO":
            continue
        target = ROOT / row["target_rel"]
        if not target.is_file():
            findings.append("IMPORTED_BYTES_MISSING " + row["target_rel"][:80])
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != row["sha256"]:
            findings.append("IMPORTED_DIGEST_STALE " + row["target_rel"][:80])
    return findings


def check_authority_index() -> list:
    """Re-hash every promoted file and compare it with the digest the top-level index records.

    The index is the thing a new agent reads to decide which October authority snapshot applies.
    A table whose SHA-256 column has rotted is worse than no table, because it looks like evidence.
    """
    if not (ROOT / AUTHORITY_INDEX).is_file():
        return ["AUTHORITY_INDEX_MISSING"]
    rows = _authority_rows()
    if not rows:
        return ["AUTHORITY_INDEX_HAS_NO_ROWS"]
    findings = []
    for cells in rows:
        location = cells[1].strip("`")
        recorded = cells[4].strip("`")
        target = ROOT / location
        if not target.is_file():
            findings.append("PROMOTED_FILE_MISSING " + location)
            continue
        digest = hashlib.sha256(target.read_bytes()).hexdigest()
        if digest != recorded:
            findings.append("PROMOTED_DIGEST_STALE %s 记录=%s… 现算=%s…" %
                            (location, recorded[:12], digest[:12]))
        declared = int(cells[5].replace(",", ""))
        if declared != target.stat().st_size:
            findings.append("PROMOTED_BYTES_STALE %s 记录=%d 现算=%d" %
                            (location, declared, target.stat().st_size))
    return findings


def figures_block() -> str:
    derived = derive_figures()
    return "\n".join("%s = %d" % (key, derived[key]) for key in sorted(derived))


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="compare the entries with the registers")
    mode.add_argument("--print-block", action="store_true",
                      help="print the figures block --check expects, derived live")
    parser.add_argument("--entry", type=Path, default=ROOT / ENTRY,
                       help="audit this copy of the entry document instead of the tracked one "
                            "(registers stay real; this is how the falsification test drives it)")
    args = parser.parse_args(argv)
    # the findings are Chinese; a cp936 console would raise instead of printing them
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if args.print_block:
        print(FIGURES_START)
        print(figures_block())
        print(FIGURES_END)
        return 0
    try:
        findings, machine_only = check_entries(args.entry)
        findings += check_figures(args.entry)
        findings += check_authority_index()
        findings += check_archive_coverage()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print(json.dumps({"verdict": "REFUSED", "error": "%s: %s" % (type(exc).__name__, exc),
                          "root": str(ROOT)}, ensure_ascii=False))
        return 3
    print(json.dumps({"verdict": "PASS" if not findings else "FAIL",
                      "root": str(ROOT),
                      "findings": findings,
                      "finding_count": len(findings),
                      "machine_bound_citations_not_required_in_a_clone": machine_only,
                      "figures_derived": len(derive_figures())},
                     ensure_ascii=False, indent=2))
    return 0 if not findings else 1


if __name__ == "__main__":
    raise SystemExit(main())
