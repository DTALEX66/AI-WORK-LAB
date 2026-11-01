"""Verify that every Markdown document at the repository root declares its disposition.

The hazard this closes: a root file whose name reads like an assignment
(`HANDOFF-*.md`, `*_REPORT.md`, `*_MANIFEST.md`) is opened by a new session before the
authority chain is, and it can command work that the CURRENT taskpack already closed.
On 2026-10-19 the six such documents were moved (not deleted) to
`docs/history/archive/root-ui-records-20261019/` by explicit user directive, after their
consumers were repointed: the uppercase-falsifier fixtures now use `NOTICE.md` (root-level
because `docs/` is a non-diffable root), and `taskpacks/current/error-ledger.json` keeps its
historical citation as evidence. The root now holds five documents. This guard still
classifies every tracked root Markdown file, so a new assignment-shaped file cannot appear
unlabelled, and it still verifies that the registry's authority set is derived from the
machine index rather than copied.

Verdicts, all red, never a silent skip:
  ROOT_DISPOSITIONS_PASS        every tracked root document is classified and labelled
  ROOT_DISPOSITIONS_FAIL        named findings (unclassified / stale row / no marker /
                                pointer not current / body bytes changed / bad vocabulary)
  ROOT_DISPOSITIONS_NO_GIT      the tracked-file population could not be enumerated
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = REPO / ".project/governance" / "root-document-dispositions.json"
AUTHORITY_INDEX = REPO / ".project/governance" / "project-authority-index.json"
BEGIN_MARK = "<!-- ROOT-DISPOSITION:BEGIN NON-NORMATIVE-HISTORICAL -->"
END_MARK = "<!-- ROOT-DISPOSITION:END -->"
VOCABULARY = ("authority", "convention-current", "historical-non-normative")
MARKER = "NON-NORMATIVE-HISTORICAL"


def tracked_root_markdown(root: Path) -> list[str]:
    """Root-level tracked ``.md`` files, NUL-split so non-ASCII names survive."""
    result = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, capture_output=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    names = result.stdout.decode("utf-8", "replace").split("\0")
    return sorted(n for n in names if n and "/" not in n and n.lower().endswith(".md"))


def head_bytes(root: Path, rel: str) -> bytes:
    result = subprocess.run(
        ["git", "show", f"HEAD:{rel}"], cwd=root, capture_output=True
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode("utf-8", "replace").strip())
    return result.stdout


def authority_named_root_documents(index: dict) -> set[str]:
    """Every root document name the machine authority itself points a reader at.

    Derived from the index instead of copied into the registry, so demoting an authority
    document in the registry is a finding rather than an edit.
    """
    fields = [index.get("topHumanAuthority", "")]
    for key in ("auditBootstrap", "sourcePrecedence"):
        fields.extend(index.get(key, []))
    text = " ".join(str(entry) for entry in fields)
    return {token for token in text.split() if token.lower().endswith(".md")}


def same_text(left: str, right: str) -> bool:
    """Compare text, not line terminators.

    The repository normalizes on check-in (`text=auto`), so a tracked `.md` is stored with LF and checked out
    with CRLF on Windows. A byte comparison therefore convicts every historical root document the moment it is
    committed -- which is what it did at `0db79f9f`, having had nothing to compare against while the files were
    still untracked. What this guard exists to catch is a REWRITE of the body, and a terminator is not a word.
    """
    return (left.replace("\r\n", "\n").replace("\r", "\n")
            == right.replace("\r\n", "\n").replace("\r", "\n"))


def strip_banner(text: str) -> str:
    """Return the document as it was before its disposition block was inserted."""
    lines = text.splitlines(keepends=True)
    start = next((i for i, line in enumerate(lines) if BEGIN_MARK in line), None)
    if start is None:
        return text
    end = next((i for i in range(start + 1, len(lines)) if END_MARK in lines[i]), None)
    if end is None:
        return text
    return "".join(lines[:start] + lines[end + 1:])


def check_document(rel: str, entry: dict | None, disk_text: str, prior_text: str,
                   current_taskpack: str) -> list[str]:
    findings: list[str] = []
    if entry is None:
        return [f"UNCLASSIFIED_ROOT_DOCUMENT {rel}: tracked at the root and in no "
                f"disposition registry"]
    disposition = entry.get("disposition")
    if disposition not in VOCABULARY:
        return [f"BAD_DISPOSITION {rel}: {disposition!r} is not one of "
                f"{', '.join(VOCABULARY)}"]
    if not str(entry.get("reason", "")).strip():
        findings.append(f"MISSING_REASON {rel}: a classification without a reason is a list, not a control")

    if disposition == "historical-non-normative":
        head = "".join(disk_text.splitlines(keepends=True)[:12])
        if MARKER not in head:
            findings.append(f"UNLABELLED_HISTORICAL {rel}: a reader sees no disposition in "
                            f"its first 12 lines")
        elif current_taskpack not in disk_text[:4000]:
            findings.append(f"STALE_POINTER {rel}: its banner does not name the current "
                            f"taskpack {current_taskpack!r}")
        # Both sides are stripped: the committed version of these documents CARRIES the banner from the moment
        # the labelling round is committed, so comparing a stripped body against an unstripped baseline convicts
        # every historical file -- which is what it did at `0db79f9f`, the first commit that contained them.
        # What remains under comparison is exactly what the verdict promises: text outside the disposition
        # block, differing from the committed bytes. A rewrite already committed is out of this guard's scope
        # by construction, and the test below says so rather than implying a history audit it does not do.
        if not same_text(strip_banner(disk_text), strip_banner(prior_text)):
            findings.append(f"BODY_REWRITTEN {rel}: text outside the disposition block "
                            f"differs from the committed bytes")
    if disposition in ("authority", "convention-current"):
        if BEGIN_MARK in disk_text:
            findings.append(f"CONTRADICTION {rel}: classified {disposition} yet carries a "
                            f"non-normative banner")
    return findings


def run(root: Path) -> tuple[str, list[str], int]:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    index = json.loads(AUTHORITY_INDEX.read_text(encoding="utf-8"))
    population = tracked_root_markdown(root)
    entries = {row["path"]: row for row in registry["documents"]}
    taskpack = index["currentTaskpack"]
    findings: list[str] = []

    derived = authority_named_root_documents(index)
    declared = {p for p, e in entries.items() if e.get("disposition") == "authority"}
    if derived != declared:
        findings.append(
            "AUTHORITY_SET_MISMATCH authority-named={}".format(sorted(derived))
            + f" registry-authority={sorted(declared)}")
    for rel in population:
        if rel not in entries:
            findings.extend(check_document(rel, None, "", "", taskpack))
    for rel in sorted(entries):
        if rel not in population:
            findings.append(f"STALE_REGISTRY_ROW {rel}: classified but not tracked at the root")
        path = root / rel
        if not path.is_file():
            findings.append(f"REGISTRY_POINTS_AT_NOTHING {rel}")
            continue
        disk = path.read_text(encoding="utf-8")
        try:
            prior = head_bytes(root, rel).decode("utf-8")
        except Exception as exc:  # noqa: BLE001 - reported, never swallowed
            findings.append(f"NO_COMMITTED_BYTES {rel}: {exc}")
            continue
        findings.extend(check_document(rel, entries[rel], disk, prior, taskpack))

    counts = {word: sum(1 for e in entries.values() if e.get("disposition") == word)
              for word in VOCABULARY}
    summary = "root_md={} authority={} convention={} historical={}".format(
        len(population), counts["authority"], counts["convention-current"],
        counts["historical-non-normative"])
    if findings:
        return "ROOT_DISPOSITIONS_FAIL", findings + [summary], 1
    return "ROOT_DISPOSITIONS_PASS", [summary], 0


def main() -> int:
    try:
        token, lines, code = run(REPO)
    except FileNotFoundError as exc:
        print(f"ROOT_DISPOSITIONS_NO_GIT git ls-files unavailable: {exc}")
        return 2
    except RuntimeError as exc:
        print(f"ROOT_DISPOSITIONS_NO_GIT cannot enumerate the tracked root: {exc}")
        return 2
    print(token)
    for line in lines:
        print("  " + line)
    return code


if __name__ == "__main__":
    sys.exit(main())
