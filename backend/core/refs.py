# SPDX-License-Identifier: MIT
"""Evidence and artifact reference scoping (audit F02, F04).

A result document names the evidence it stands on. This module decides whether
such a name is admissible at all, and whether it can still be read now. It
never opens a reference for execution: the service does not run, import or
source anything a result attaches, and a reference that names a runnable object
is refused rather than "stored safely", because a stored runnable path is a
launch prompt in a later tool.

Two vocabularies, deliberately not mixed:

* ``scheme:opaque`` identifiers the service itself minted
  (``collector_health:``, ``unified-verification:``, ``design-plan-readback:`` …)
  are checked against the allowlist of schemes and against the shape of the
  opaque part;
* file references are relative paths that must resolve inside one of the
  declared evidence roots, with no traversal, no drive letter, no UNC, no
  backslash and no symlink hop out of the root.
"""
from __future__ import annotations

import hashlib
import re
import stat
from pathlib import Path

SCHEMA_VERSION = "ai-work-lab/evidence-ref/v1"

#: Opaque reference schemes this build is willing to read back.
ALLOWED_SCHEMES = {
    "collector_health", "unified-verification", "design-plan-readback",
    "target-profile-readback", "work-issue-projection", "work-pack-record",
    "probe", "migration", "file", "sha256",
}

#: Extensions that are never admissible as an attachment reference, whatever the
#: root says. This is a storage policy, not an execution guard: nothing here runs.
RUNNABLE_SUFFIXES = frozenset({
    ".ps1", ".psm1", ".psd1", ".bat", ".cmd", ".com", ".exe", ".msi", ".scr",
    ".sh", ".bash", ".zsh", ".vbs", ".vbe", ".js", ".jse", ".wsf", ".wsh",
    ".dll", ".ocx", ".jar", ".reg", ".lnk", ".appimage",
})

_OPAQUE_RE = re.compile(r"^[A-Za-z0-9._:@/+={}\[\]-]{1,300}$")
_HEX64_RE = re.compile(r"^[0-9a-f]{64}$")


class RefError(ValueError):
    """A reference this contract refuses. The message names the rule."""


def validate(ref, *, allowed_roots: list[Path], for_read: bool = False) -> str:
    """Return the reference unchanged when it is admissible, else raise RefError."""
    if not isinstance(ref, str) or not ref.strip():
        raise RefError("EVIDENCE_REF_REQUIRED reference must be a non-empty string")
    text = ref.strip()
    if len(text) > 400:
        raise RefError("EVIDENCE_REF_TOO_LONG reference exceeds 400 characters")
    if "\\" in text:
        raise RefError("EVIDENCE_REF_BACKSLASH Windows path separators are not admissible")
    if ":" in text.split("/", 1)[0]:
        head, _, rest = text.partition(":")
        scheme = head.lower()
        if scheme not in ALLOWED_SCHEMES:
            raise RefError("EVIDENCE_REF_SCHEME_UNKNOWN " + repr(scheme)
                           + " is not a reference scheme this build reads back")
        if scheme == "sha256" and not _HEX64_RE.match(rest):
            raise RefError("EVIDENCE_REF_DIGEST_MALFORMED sha256: needs 64 lowercase hex")
        if not _OPAQUE_RE.match(rest):
            raise RefError("EVIDENCE_REF_OPAQUE_MALFORMED " + repr(rest[:40]))
        if ".." in rest.split(":"):
            raise RefError("EVIDENCE_REF_TRAVERSAL " + repr(text))
        return text
    # A bare relative path: it has to live inside a declared evidence root.
    if text.startswith("/") or text[1:2] == ":":
        raise RefError("EVIDENCE_REF_ABSOLUTE absolute paths are not admissible")
    parts = Path(text).parts
    if not parts or ".." in parts or parts[0] in ("/", "\\"):
        raise RefError("EVIDENCE_REF_TRAVERSAL " + repr(text))
    if Path(text).suffix.lower() in RUNNABLE_SUFFIXES:
        raise RefError("EVIDENCE_REF_RUNNABLE_REFUSED " + repr(text)
                       + " names an executable object; results may not attach runnable files")
    resolved = _resolve_inside(Path(text), allowed_roots)
    if resolved is None:
        raise RefError("EVIDENCE_REF_OUT_OF_SCOPE " + repr(text)
                       + " does not resolve inside a declared evidence root")
    if for_read:
        _readable(resolved, text)
    return text


def validate_list(refs, *, allowed_roots: list[Path], for_read: bool = False,
                  allow_empty: bool = True) -> list[str]:
    if refs is None:
        refs = []
    if not isinstance(refs, list):
        raise RefError("EVIDENCE_REFS_MUST_BE_A_LIST")
    if not refs and not allow_empty:
        raise RefError("EVIDENCE_REFS_REQUIRED a claim with no reference is not evidence")
    return [validate(ref, allowed_roots=allowed_roots, for_read=for_read) for ref in refs]


def digest_of(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _resolve_inside(relative: Path, allowed_roots: list[Path]):
    for root in allowed_roots:
        root = Path(root).resolve()
        candidate = (root / relative)
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        # resolve() follows symlinks; a link that leaves the root fails the check.
        if resolved.is_relative_to(root):
            return resolved
    return None


def _readable(path: Path, text: str) -> None:
    if not path.exists():
        raise RefError("EVIDENCE_UNREADABLE " + repr(text) + " names a path that is not there")
    mode = path.stat().st_mode
    if not stat.S_ISREG(mode):
        raise RefError("EVIDENCE_UNREADABLE " + repr(text) + " is not a regular file")
    if path.stat().st_size == 0:
        raise RefError("EVIDENCE_EMPTY " + repr(text) + " is a zero-byte file")
