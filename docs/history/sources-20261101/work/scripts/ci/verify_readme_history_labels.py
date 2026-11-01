"""Fail when the workflow README points a reader at a frozen record without saying it is frozen.

`docs/current/workflow-assistance/workflow/active-authority-index.md` states the rule; until now nothing
checked it, and the README carried 14 links into history roots while its tests only asserted that a couple
of strings appear somewhere. Most of those links are honest provenance inside an index of archived
documents. One was not: the upgrade-recovery runbook introduced an archived 2026-08-13 handoff with
"today's ... recovery procedure is at ...", which is exactly how a frozen record gets followed as current
guidance.

The decidable form: a line linking into `docs/history/` or `taskpacks/history/` must be labelled as past
either in its own prose or by the heading it sits under (an archive index is legitimate; a runbook
delegating today's procedure is not).

Worth keeping the reason the first version was wrong: it searched the raw line for words like `archive`,
and every one of these paths contains `history/archive/` -- so the link matched its own URL and the gate
passed on 14 of 14 links, including the violation it exists to catch. Link targets and inline code are
therefore stripped before any word is looked for.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
README = REPO / "docs" / "current" / "workflow-assistance-README.md"
HISTORY_LINK = re.compile(r"(?:docs|taskpacks)/history/")
ARCHIVAL_LABEL = re.compile(
    r"归档|存档|历史|审计|仅作|已取代|冻结|证据|登记|frozen|superseded|archiv", re.I)
INLINE_CODE = re.compile(r"`[^`]*`")
LINK_TARGET = re.compile(r"\]\([^)]*\)")
HEADING = re.compile(r"^#{1,6}\s+(.*)$")
CONTEXT_LINES = 2


def prose_of(line: str) -> str:
    """The human words on a line: link targets and code spans removed, because paths are not labels."""
    return LINK_TARGET.sub(" ", INLINE_CODE.sub(" ", line))


def violations(lines: list[str]) -> list[tuple[int, str]]:
    """(1-based line, excerpt) for each history link that neither it nor its section calls past."""
    heading_at: list[str] = []
    current = ""
    for line in lines:
        match = HEADING.match(line)
        if match:
            current = match.group(1)
        heading_at.append(current)

    found = []
    for index, line in enumerate(lines):
        if not HISTORY_LINK.search(line):
            continue
        # the label may sit on the line, in the sentence right above it (prose that introduces a link
        # usually ends in a colon), or in the governing heading
        window = " ".join(prose_of(lines[j])
                          for j in range(max(0, index - CONTEXT_LINES), index + 1))
        window += " " + heading_at[index]
        if not ARCHIVAL_LABEL.search(window):
            found.append((index + 1, line.strip()[:120]))
    return found


def main() -> int:
    if not README.is_file():
        print(f"README_LABEL_FAIL missing {README.relative_to(REPO)}")
        return 1
    lines = README.read_text(encoding="utf-8").split("\n")
    links = sum(1 for l in lines if HISTORY_LINK.search(l))
    bad = violations(lines)
    for line, excerpt in bad:
        print(f"README_LABEL_FAIL line {line}: history link with no archival label :: {excerpt}")
    if bad:
        print(f"README_LABEL_FAIL unlabelled={len(bad)} of history_links={links}")
        return 1
    print(f"README_LABEL_PASS history_links={links} all_labelled_by_prose_or_heading")
    return 0


if __name__ == "__main__":
    sys.exit(main())
