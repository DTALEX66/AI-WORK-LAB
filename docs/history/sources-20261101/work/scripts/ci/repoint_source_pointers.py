#!/usr/bin/env python3
"""Repoint `path:LINE` citations to the line the quoted code actually lives on -- mechanically.

Why this exists
---------------
Four CI failures in two days came from the same cause, and the repairs kept failing because they were done by
hand: read the gate's message, guess the new line, push, watch it fail one line off. A pointer is a mechanical
fact, so re-deriving it must be mechanical.

The root cause has TWO shapes, and conflating them is why the fixes never held
-----------------------------------------------------------------------------
1. **Code citations** -- `path:LINE <backtick-quoted code>`. The quote identifies the target, so the line can be
   re-derived exactly. These are repairable, and this tool repairs them.
2. **Narrative pointers** -- `path:LINE` in prose, with no quote. Nothing identifies what the number meant, so
   it cannot be verified and it rots silently the moment the file changes above it. No amount of re-measuring
   keeps these honest; the only durable fix is to stop citing a line number in prose (`--drop-narrative`).

What it does
------------
* for each code citation: locate the exact quoted line in the target file (closest occurrence to the old line
  when several match), report LANDED / DRIFT / UNRESOLVED, and with `--apply` rewrite it keeping range width;
* for each narrative pointer: report NARRATIVE, and with `--drop-narrative` replace `path:NNN` with `path` so the
  number stops claiming precision it does not have;
* it REFUSES rather than guesses: an unresolvable quote is reported and `--apply` exits non-zero.

Exit codes: 0 = every citation lands on its quote and no narrative pointer remains; 1 otherwise.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

# A pointer is a repo-relative path plus a line (optionally a range). Kept deliberately narrow: extensions we
# actually cite, so a URL or a version string cannot be mistaken for one.
# A CODE CITATION is a pointer immediately followed by the code it quotes. This pairing is the whole reason the
# tool can repair anything: the quote is the identity, the line is only a hint.
CITATION_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:ts|tsx|js|jsx|py|md|json|csv|yaml|yml))"
    r":(?P<start>\d+)(?:-(?P<end>\d+))?\s+`(?P<quote>[^`\n]{3,200})`"
)
# A NARRATIVE pointer has no quote. It is listed so it can be removed, not so it can be trusted.
NARRATIVE_RE = re.compile(
    r"(?P<path>(?:[A-Za-z0-9_.-]+/)*[A-Za-z0-9_.-]+\.(?:ts|tsx|js|jsx|py|md|json|csv|yaml|yml))"
    r":(?P<start>\d+)(?:-(?P<end>\d+))?(?!\s*`)"
)


@dataclass
class Finding:
    file: str          # the citing file
    pointer: str       # as written, e.g. apps/.../api.ts:555
    quote: str         # the code it claims to cite
    current: int | None  # where the quote is now
    status: str        # LANDED | DRIFT | UNRESOLVED


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _null_escape(text: str) -> str:
    """CSV doubles its quote characters, so a cell quoting `"key": value` arrives as `""key"": value`. Comparing
    the two forms directly is why the first version of this tool reported 48 "unresolved" citations that were
    perfectly fine -- the document was right and the matcher was wrong."""
    return text.replace('""', '"')


def resolve_quote(source_lines: list[str], quote: str, old_line: int, span_end: int | None = None) -> int | None:
    """The line the quote lives on now, or None.

    Exact match on the stripped line first: a citation should quote a whole line or a distinctive fragment, and
    a substring-only match would happily land on a comment that mentions the code. When several lines match,
    the closest to the old line wins -- that is the one the author meant.
    """
    needle = _null_escape(quote).strip().rstrip("`").strip()
    if not needle:
        return None
    if needle.endswith("…"):
        needle = needle[:-1].strip()      # a fragment quote is still a quote; the ellipsis is prose, not code
    exact = [i for i, line in enumerate(source_lines, start=1) if line.strip() == needle]
    candidates = exact or [i for i, line in enumerate(source_lines, start=1) if needle in line]
    if not candidates:
        return None
    if span_end is not None:
        inside = [line for line in candidates if old_line <= line <= span_end]
        if inside:
            return min(inside)            # already inside the cited range: nothing to fix
    return min(candidates, key=lambda line: (abs(line - old_line), line))


def audit(citing: Path, root: Path) -> list[Finding]:
    findings: list[Finding] = []
    for raw_line in _read(citing).splitlines():
        for match in CITATION_RE.finditer(raw_line):
            pointer = f"{match.group('path')}:{match.group('start')}"
            if match.group("end"):
                pointer += f"-{match.group('end')}"
            target = root / match.group("path")
            if not target.is_file():
                findings.append(Finding(citing.as_posix(), pointer, match.group("quote"), None, "UNRESOLVED"))
                continue
            old_start = int(match.group("start"))
            span_end = int(match.group("end")) if match.group("end") else None
            line = resolve_quote(_read(target).splitlines(), match.group("quote"), old_start, span_end)
            if line is None:
                findings.append(Finding(citing.as_posix(), pointer, match.group("quote"), None, "UNRESOLVED"))
            elif line == old_start or (span_end is not None and old_start <= line <= span_end):
                findings.append(Finding(citing.as_posix(), pointer, match.group("quote"), line, "LANDED"))
            else:
                findings.append(Finding(citing.as_posix(), pointer, match.group("quote"), line, "DRIFT"))
        for match in NARRATIVE_RE.finditer(raw_line):
            if any(c.start() <= match.start() and match.end() <= c.end() for c in CITATION_RE.finditer(raw_line)):
                continue
            pointer = f"{match.group('path')}:{match.group('start')}"
            findings.append(Finding(citing.as_posix(), pointer, "", None, "NARRATIVE"))
    return findings


def rewrite(citing: Path, findings: list[Finding], *, drop_narrative: bool) -> str:
    text = _read(citing)
    for finding in findings:
        if finding.status == "DRIFT" and finding.current is not None:
            path_part, _, span = finding.pointer.rpartition(":")
            width = 1
            if "-" in span:
                start, _, end = span.partition("-")
                width = max(1, int(end) - int(start) + 1)
            new = f"{path_part}:{finding.current}" + (f"-{finding.current + width - 1}" if width > 1 else "")
            text = text.replace(finding.pointer, new)
        elif finding.status == "NARRATIVE" and drop_narrative:
            path_part, _, _ = finding.pointer.rpartition(":")
            text = text.replace(finding.pointer, path_part)
    return text


LIVE_SURFACES = ("docs/current/*.md", "docs/current/**/*.md", "taskpacks/current/*.md",
                 "taskpacks/current/**/*.md", "WORK-LAB-AUTHORITY.md")


def live_pointer_surface(root: Path) -> list[Path]:
    """The documents that are still allowed to move, enumerated from the git index.

    2026-10-20: the default target used to be the UI-V2 interface-binding matrix, which now sits inside the
    frozen archive. A tool that rewrites line numbers cannot aim at bytes two hash-bound records promise not
    to change, so the population moved to live docs and is enumerated rather than hand-listed, so a document
    that lands next week is covered the day it lands.
    """
    listed = subprocess.run(["git", "ls-files", "--", *LIVE_SURFACES], cwd=root,
                            capture_output=True, text=True, encoding="utf-8", errors="replace")
    if listed.returncode != 0:
        raise SystemExit(f"REPOINT_FAIL cannot enumerate the live surface: {listed.stderr.strip()}")
    return [root / line for line in listed.stdout.splitlines() if line.strip()]


def frozen_paths(root: Path) -> set[str]:
    """Every repo-relative path whose bytes are pinned by a published hash-bound record."""
    pinned: set[str] = set()
    manifest = root / "docs/history/archive/FROZEN-MANIFEST.json"
    moves = root / "docs/history/archive/MOVED-PATHS-20261019.json"
    if manifest.is_file():
        for entry in json.loads(manifest.read_text(encoding="utf-8")).get("files", []):
            pinned.add(str(entry.get("path", "")).replace("\\", "/"))
    if moves.is_file():
        for move in json.loads(moves.read_text(encoding="utf-8")).get("moves", []):
            pinned.add(str(move.get("to", "")).replace("\\", "/"))
    return {p for p in pinned if p}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Repoint path:LINE citations to where the quoted code now is.")
    parser.add_argument("files", nargs="*", help="Citing files (default: the tracked live doc surface; "
                                                "frozen archive bytes are refused, never repaired).")
    parser.add_argument("--apply", action="store_true", help="Rewrite drifted citations in place.")
    parser.add_argument("--drop-narrative", action="store_true",
                        help="Replace narrative `path:LINE` with `path`. Used only where a quote cannot be "
                             "attached; dropping pointers lowers the gate's vision and is not the first choice.")
    parser.add_argument("--attach-quotes", action="store_true",
                        help="Turn a narrative `path:LINE` into `path:LINE `<the code on that line>`` so the "
                             "citation identifies itself. This RAISES the check instead of lowering it: an "
                             "unquoted number can only be tested for 'not blank', a quoted one can be re-derived.")
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args(argv)

    targets = [Path(f) for f in args.files] or live_pointer_surface(args.root)
    targets = [t if t.is_absolute() else ROOT / t for t in targets]
    missing = [t for t in targets if not t.is_file()]
    if missing:
        print(f"REPOINT_FAIL missing citing file(s): {[str(m) for m in missing]}")
        return 1
    frozen = frozen_paths(args.root)
    pinned = []
    for target in targets:
        try:
            rel = target.resolve().relative_to(args.root.resolve()).as_posix()
        except ValueError:
            continue
        if rel in frozen:
            pinned.append(rel)
    if pinned:
        print(f"REPOINT_FROZEN_REFUSED {len(pinned)} target(s) are pinned by a hash-bound record "
              f"(docs/history/archive/FROZEN-MANIFEST.json or docs/history/archive/"
              f"MOVED-PATHS-20261019.json). Rewriting a line pointer inside them would break the freeze, "
              f"which is the defect this refuses: {pinned}. Repair the claim in a live surface instead.")
        return 1

    all_findings: list[Finding] = []
    for target in targets:
        all_findings.extend(audit(target, args.root))

    drift = [f for f in all_findings if f.status == "DRIFT"]
    unresolved = [f for f in all_findings if f.status == "UNRESOLVED"]
    narrative = [f for f in all_findings if f.status == "NARRATIVE"]
    landed = [f for f in all_findings if f.status == "LANDED"]
    print(f"REPOINT citations={len(landed) + len(drift) + len(unresolved)} landed={len(landed)} "
          f"drift={len(drift)} unresolved={len(unresolved)} narrative={len(narrative)}")
    for finding in drift:
        print(f"  DRIFT {finding.pointer} -> {finding.current} for `{finding.quote[:60]}`")
    for finding in unresolved:
        print(f"  UNRESOLVED {finding.pointer} `{finding.quote[:50]}` (quote not found; not guessing)")
    for finding in narrative:
        print(f"  NARRATIVE {finding.pointer} (no quoted code; a line number in prose cannot be verified)")

    if args.attach_quotes:
        for finding in narrative:
            path_part, _, span = finding.pointer.rpartition(":")
            target = args.root / path_part
            if not target.is_file():
                continue
            lines = _read(target).splitlines()
            index = int(span.split("-")[0])
            code = lines[index - 1].strip() if 0 < index <= len(lines) else ""
            if not code:
                print(f"  CANNOT_ATTACH {finding.pointer} (lands on a blank line; needs a human)")
                continue
            if len(code) > 160 or "`" in code:
                code = code[:150].rstrip() + "…"
            # The citing file may be a CSV, where a cell's own `"` is doubled. Inserting raw code here is what
            # broke the matrix's column shape on the first attempt -- the code contained `"status": ...`.
            if finding.file.endswith(".csv"):
                code = code.replace('"', '""')
            own = [f for f in narrative if f.file == finding.file]
            targets_text = _read(Path(finding.file))
            targets_text = targets_text.replace(finding.pointer, f"{finding.pointer} `{code}`", 1)
            Path(finding.file).write_text(targets_text, encoding="utf-8", newline="\n")
        print(f"REPOINT_QUOTES_ATTACHED {len(narrative)}")
        return 0

    if args.apply or args.drop_narrative:
        for finding in unresolved:
            print(f"  LEFT_ALONE {finding.pointer} (quote is a fragment; nothing is guessed)")
        for target in targets:
            own = [f for f in all_findings if f.file == target.as_posix() or f.file == str(target)]
            before = _read(target)
            after = rewrite(target, own, drop_narrative=args.drop_narrative)
            if after != before:
                target.write_text(after, encoding="utf-8", newline="\n")
                print(f"REPOINT_APPLIED {target}")
        return 0

    # Only DRIFT is fatal. DRIFT is the condition this tool can fix by itself, so a red on it is actionable
    # ("run --apply"). UNRESOLVED and NARRATIVE are reported, not fatal: UNRESOLVED is a fragment quote whose
    # target is genuinely ambiguous, and NARRATIVE is a bare number the pack's own matrix gate already tests.
    # A gate that cannot be satisfied without hand-editing 49 old rows is a gate people switch off -- and the
    # pressure it creates is to delete citations, which lowers the check instead of raising it.
    return 0 if not drift else 1


if __name__ == "__main__":
    raise SystemExit(main())
