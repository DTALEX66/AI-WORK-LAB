"""Path containment decided from text, so one input gives one answer on every host.

This module is the single home of the rule that has now produced three CI refutations in one day when it
was applied inconsistently:

* `os.path.normpath`/`normcase` and `Path.resolve()` are host-specific. On the Linux runner a Windows-shaped
  path has neither a drive nor a leading slash, so posixpath reads it as RELATIVE and anchors it inside
  the current project -- which is how the same boundary assertions were ACCEPTED on one machine and
  REFUSED on another.
* Case-folding is correct for COMPARISON and wrong for OPENING a file: a folded path simply does not exist
  on a case-sensitive filesystem, and `Path.relative_to` between a folded value and an original-case root
  raises `ValueError`, which a `try/except` reading "not ours to read" turns into a security refusal.

So callers get two distinct operations: `inside_root` / `relative_inside` for the verdict, and the
declared-case remainder for any subsequent I/O. Nothing here touches the filesystem.
"""

from __future__ import annotations

import re
from typing import Any

_DRIVE_RELATIVE = re.compile(r"^([a-z]:[^/])")
_DRIVE_ANCHORED = re.compile(r"^([a-z]:)(/.*)?$")


def normalise_path(text: Any) -> str:
    """Case-fold, unify separators and collapse a path as TEXT, deliberately without the host's help."""
    unified = str(text).replace("\\", "/").lower().strip()
    if unified.startswith("//"):
        leading, rest = "//", unified[2:]
    else:
        drive = _DRIVE_ANCHORED.match(unified)
        if drive:
            leading, rest = drive.group(1) + "/", (drive.group(2) or "").lstrip("/")
        elif unified.startswith("/"):
            leading, rest = "/", unified[1:]
        else:
            leading, rest = "", unified
    collapsed: list[str] = []
    for part in rest.split("/"):
        if part in ("", "."):
            continue
        if part == "..":
            if collapsed and collapsed[-1] != "..":
                collapsed.pop()
                continue
            if leading:
                continue  # `..` cannot climb above an anchored root
            collapsed.append("..")
            continue
        collapsed.append(part)
    return leading + "/".join(collapsed)


def path_is_drive_relative(text: Any) -> bool:
    """`E:secrets` means "relative to whatever the current directory on E: happens to be"."""
    return bool(_DRIVE_RELATIVE.match(str(text).replace("\\", "/").lower().strip()))


def path_is_unc(text: Any) -> bool:
    return str(text).startswith(("\\\\", "//"))


def path_is_anchored(text: Any) -> bool:
    """Absolute in either vocabulary: a drive plus a slash, or a leading slash. Never a bare `E:`."""
    raw = str(text).replace("\\", "/")
    return bool(re.match(r"^[a-z]:/", raw.lower())) or raw.startswith("/")


def inside_root(candidate: Any, root: Any) -> tuple[bool, str, str]:
    """Containment by text alone: the same normalised path, or below the root's own boundary.

    Returns (inside, normalised root, normalised candidate) so a refusal can print both values and a red on
    another machine explains itself instead of inviting a theory.
    """
    root_lex = normalise_path(root).rstrip("/")
    lexical = normalise_path(candidate)
    return lexical == root_lex or lexical.startswith(root_lex + "/"), root_lex, lexical


def relative_inside(candidate: Any, root: Any) -> str | None:
    """The declared path relative to the root, decided by the folded test but keeping the given case.

    The read must find the file the caller named, so the remainder is cut from the unfolded text; the
    comparison that authorises it is the folded one. When the two do not line up -- dot-segments in the
    middle of the declared path, a root written with different length -- this returns None rather than
    handing back a guessed remainder.
    """
    lexical = normalise_path(candidate)
    root_lex = normalise_path(root).rstrip("/")
    if lexical == root_lex:
        return ""
    if not lexical.startswith(root_lex + "/"):
        return None
    unified = str(candidate).replace("\\", "/").rstrip("/")
    remainder = unified[len(root_lex):].lstrip("/")
    if normalise_path(remainder) != lexical[len(root_lex) + 1:]:
        return None
    return remainder
