"""Artifact handle projection: the list that was missing behind REQ-RANGE-20261007.

The read side already had a viewer: ``GET /api/v1/evidence-range`` returns an exact byte interval of one
evidence artifact plus a slice digest. What it never had was a list of things it may be asked to view, so
the record sat at ``UI_LANDING_BLOCKED_ON_HANDLE_PROJECTION``. This module supplies that list and nothing
more than the list: identity only, never content.

Why each row is shaped the way it is:

* **handle** — an absolute path produced under exactly the predicates ``evidence_range_reader.read_range``
  applies (absolute, inside the repository, on a declared evidence surface, a regular file, not
  credential-shaped). A projected handle is therefore a handle the range route will accept, which is the
  only claim this projection is qualified to make;
* **surface** — the boundary-declaration key the artifact sits on, so a reader can tell canonical evidence
  from transient runtime output without re-reading the declaration;
* **sizeBytes / modifiedAt** — from the directory listing, never from reading the file;
* **digest** — present only when some *project record* already states it (a manifest pair, a spill-ledger
  line, a Task Ledger evidence row). Nothing here hashes file content: ``read_range`` deliberately refuses
  to compute a whole-file digest because it would turn a cheap interval read into a full read, and a
  projection that copied that behaviour would read the entire evidence tree to build a list of paths.
  ``digestRecorded`` says positively that no digest exists, which is a fact, not a blank;
* **kind** — what a viewer would render it as, decided from the extension only.

Hard refusals (ERR-166 is the reason these exist and are not optional):
* credential-shaped names are refused by name even when they sit inside an evidence root — the token list
  is IMPORTED from ``evidence_range_reader`` so the two layers cannot drift apart;
* nothing outside the declared evidence surfaces is enumerated; the surfaces come from
  ``declared_evidence_roots()``, i.e. from ``project-data-boundary.json`` itself;
* file bytes never enter any field. This module opens only digest-BEARING RECORDS (bounded count and size),
  and indexes their stated digests, never their prose.

Cost discipline, because this runs inside the read path (twice per snapshot: the live-gate skeleton and the
snapshot itself, TTL-cached at 60 s by the composition root): the canonical evidence surface is walked
completely (measured 1.3k files, ~27 ms) and the runtime surface is walked to a declared depth with
regenerable trees pruned (~2.9k files, ~60 ms). Anything that did not reach the snapshot is declared in
``artifactHandlesSummary`` — an enumeration can be capped, it can never be quietly capped.

Which rows the cap keeps is a policy, not a side effect of the walk, and it is stated as one constant:
``ORDERING_KEY`` (newest ``modifiedAt`` first, ties broken by ascending handle). Every bound this module
takes — the cap, the per-surface quotas, the digest reserve, and the digest-record budget that decides
which citations exist at all — ranks through ``_rank``/``_rank_row``, so the projected set is a function of
the repository's state rather than of directory listing order, and the same input yields byte-identical
rows. The summary repeats the key alongside ``cap``/``projectedCount``/``enumeratedCount``/``omittedCount``
/``truncated``, because a reader who is being truncated has to be able to tell what they are missing and
why; ``snapshot_validator`` refuses a ``truncated: true`` list that names no ordering key.
"""
from __future__ import annotations

import json
import os
import stat as stat_module
import time
from datetime import datetime, timezone
from pathlib import Path, PurePath
from typing import Any, Iterator, NamedTuple

# MIGRATED (F01, change class b): both helpers already live in this repository's
# `domains/work/control` package; the bare names were an artefact of the WORK-LAB flat
# script directory.
from ..control.evidence_range_reader import declared_evidence_roots, name_is_sensitive
from ..control.path_text import inside_root, normalise_path, path_is_anchored, relative_inside

SUMMARY_SCHEMA_VERSION = "worklab/artifact-handles-summary/v1"
BOUNDARY_DECLARATION = ".project/governance/project-data-boundary.json"

# Surface names come from the boundary declaration's own keys — a second hardcoded directory opinion is
# exactly how the two layers drift apart.
SURFACE_KEY_NAMES: dict[str, str] = {
    "canonicalEvidenceRoot": "canonical-evidence",
    "taskArtifactsRoot": "task-artifacts",
    "runtimeRoot": "runtime",
}
UNNAMED_SURFACE = "declared"
KNOWN_SURFACES: frozenset[str] = frozenset(SURFACE_KEY_NAMES.values()) | {UNNAMED_SURFACE}
# When one path is declared under two keys (this project declares `.project-local/artifacts` as both the
# canonical evidence root and the task artifacts root), the stronger name wins.
SURFACE_PRIORITY: tuple[str, ...] = ("canonical-evidence", "task-artifacts", "runtime", UNNAMED_SURFACE)

ARTIFACT_KINDS: frozenset[str] = frozenset(
    {"structured-record", "report", "log", "image", "archive", "source-code", "binary", "other"})

KIND_BY_SUFFIX: dict[str, str] = {
    ".json": "structured-record", ".jsonl": "structured-record", ".ndjson": "structured-record",
    ".yaml": "structured-record", ".yml": "structured-record", ".csv": "structured-record",
    ".xml": "structured-record", ".toml": "structured-record", ".ini": "structured-record",
    ".md": "report", ".markdown": "report", ".txt": "report", ".html": "report", ".pdf": "report",
    ".rst": "report", ".log": "log", ".out": "log", ".err": "log",
    ".png": "image", ".jpg": "image", ".jpeg": "image", ".gif": "image", ".svg": "image",
    ".webp": "image", ".ico": "image",
    ".zip": "archive", ".tar": "archive", ".gz": "archive", ".bz2": "archive", ".7z": "archive",
    ".rar": "archive", ".whl": "archive", ".jar": "archive",
    ".py": "source-code", ".pyi": "source-code", ".js": "source-code", ".ts": "source-code",
    ".tsx": "source-code", ".jsx": "source-code", ".css": "source-code", ".rs": "source-code",
    ".go": "source-code", ".java": "source-code", ".sql": "source-code", ".ps1": "source-code",
    ".bat": "source-code", ".cmd": "source-code", ".sh": "source-code",
    ".exe": "binary", ".dll": "binary", ".so": "binary", ".pyd": "binary", ".rlib": "binary",
    ".rmeta": "binary", ".pdb": "binary", ".woff": "binary", ".woff2": "binary",
}

# Enumeration bounds. MAX_HANDLES is a projection cap, always declared in the summary, never applied in
# silence. The runtime surface is deeper and 25x larger than the canonical one (measured 13.2k vs 1.3k
# files), so it is walked to a declared depth instead of in full; the canonical surface stays complete.
MAX_HANDLES = 200
# Per-surface selection budget. The canonical surface is what a viewer came for and is small enough to
# treat as first-class; the runtime surface is recency-ranked churn, so it gets a smaller share of the cap.
SURFACE_QUOTAS: dict[str, int] = {"canonical-evidence": 100, "task-artifacts": 100,
                                  "runtime": 60, UNNAMED_SURFACE: 60}
DEFAULT_QUOTA = 60
# Seats held for artifacts another project record already states a digest for (see _select_by_surface).
DIGEST_RESERVE = 40
SCAN_MAX_DEPTH: dict[str, int | None] = {
    "canonical-evidence": None, "task-artifacts": None, "runtime": 4, UNNAMED_SURFACE: 4,
}
DEFAULT_SCAN_MAX_DEPTH = 4
# Regenerable build/cache/scratch trees are not evidence and are not walked into; the prune is counted,
# not hidden. This also keeps another writer's `tmp` fixture out of a projection of THIS project's evidence.
PRUNED_DIRECTORY_NAMES = frozenset({
    "__pycache__", "node_modules", "target", "cache", ".git", "dist", "build", ".next", ".cargo",
    "object-snapshots", "site-packages", ".venv", "venv", ".inline-cache", "tmp", "temp", ".tmp",
})

# Digest records: bounded by count and size, canonical surface first, and only names that state digests
# for a living.
DIGEST_RECORD_NAME_MARKS = ("manifest", "baseline", "readback", "receipt", "provenance",
                            "ledger", "inventory", "spill")
MAX_DIGEST_RECORDS = 60
MAX_DIGEST_RECORD_BYTES = 131_072
MAX_DIGEST_PAIRS = 4000
DIGEST_VALUE_KEYS = ("sha256", "digest", "contentdigest", "content_digest", "hash", "checksum")
DIGEST_PATH_KEYS = ("path", "file", "filepath", "file_path", "target", "location", "relativepath",
                    "relative_path", "handle", "artifact", "source")
HEX_DIGITS = frozenset("0123456789abcdefABCDEF")
FILE_ATTRIBUTE_REPARSE_POINT = 0x00000400  # junctions and symlinks, from the listing's own attributes

# A row that carries any of these keys would be carrying content, which is the whole point of refusing it.
CONTENT_BEARING_KEYS = frozenset({"content", "body", "text", "bytes", "data", "raw", "preview",
                                  "excerpt", "snippet", "head", "tail", "lines", "value"})

# THE ordering rule, stated once and applied everywhere a bound is taken.
#
# Why this exists as a named key rather than as folklore: the cap is smaller than the enumeration (measured
# 4.1k artifacts against MAX_HANDLES=200), so ranking is not a presentation choice, it IS the selection. A
# cap applied to whatever the walk reached first makes the projected set a function of directory listing
# order, which means the Observer's evidence lane can show one set now and another set after any other run
# writes a file, and two readers of the same snapshot revision can be shown different evidence. Recency is
# the ranked term because it is what a reader wants to inspect; the handle is the tiebreak because it is
# the only field that is unique, stable and already in the row.
#
# The ranked term is the modification time AT THE RESOLUTION THAT IS DISCLOSED (`modifiedAt` is whole
# seconds), not the raw float the filesystem returned. Ranking on sub-second precision the row does not show
# would leave a reader auditing the list with apparent tie-break inversions — measured 28 of 200 rows on this
# machine — which is precisely the unfalsifiable folklore this key exists to remove. Two artifacts written
# inside one second are therefore ordered by handle, and the emitted list reproduces from its own fields.
ORDERING_KEY = "modifiedAt-second-desc,handle-asc"
# The coarse label of the ranked term, kept under its original name for consumers that read `order`.
ORDER_LABEL = "modifiedAt-desc"
ORDERING_RULE = (
    "candidate rows are ranked by modifiedAt (whole seconds, as disclosed on the row) newest first, and "
    "every tie — including two artifacts written inside the same second — is broken by the ascending "
    "handle string; the cap, the per-surface quotas, the digest reserve and the digest-record budget are "
    "all applied to that one ranking, so the projected set is a function of the repository state and "
    "never of directory listing order")


def _rank(mtime_second: int, handle: str) -> tuple[int, str]:
    """The sort key behind ORDERING_KEY. Every bound in this module ranks through here or not at all."""
    return (-mtime_second, handle)


def _rank_row(row: dict[str, Any]) -> tuple[int, str]:
    return _rank(row["mtimeSecond"], row["handle"])


class Surface(NamedTuple):
    name: str
    relative: str
    absolute: Path
    max_depth: int | None


def _now_iso(moment: float) -> str:
    return (datetime.fromtimestamp(moment, timezone.utc)
            .isoformat(timespec="seconds").replace("+00:00", "Z"))


def _is_sensitive_name(name: str) -> bool:
    """The reader's own per-component test, with the reader's own token list.

    ``read_range`` applies this to every component of the resolved path; here the directory components are
    tested once per descended directory and the file component once per file, which is the same set of
    tests at a fraction of the calls.
    """
    lowered = name.lower()
    return name_is_sensitive(Path(lowered))


def _read_declaration(root: Path) -> dict[str, Any] | None:
    try:
        document = json.loads((Path(root) / BOUNDARY_DECLARATION).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return document if isinstance(document, dict) else None


def enumerate_surfaces(root: Path) -> tuple[list[Surface], str | None]:
    """Declared evidence surfaces only, named by the boundary key that declared them.

    ``declared_evidence_roots`` is the single path authority; the declaration is re-read only to attach a
    name to each path it returned and to locate the spill ledger, never to widen the surface.
    """
    root = Path(root).resolve()
    declared = declared_evidence_roots(root)
    document = _read_declaration(root)
    named: dict[str, str] = {}
    spill_path: str | None = None
    if document:
        for key, name in SURFACE_KEY_NAMES.items():
            value = document.get(key)
            if isinstance(value, str) and value:
                named.setdefault(PurePath(value).as_posix(), name)
        spill = ((document.get("spillGovernance") or {}).get("ledger") or {}).get("path")
        if isinstance(spill, str) and spill:
            spill_path = spill
    surfaces: list[Surface] = []
    # Dedup on normalised TEXT, not on Path objects: Path.__eq__ is case-insensitive on Windows and
    # case-sensitive on Linux, so a set of Paths can collapse two declared surfaces on one host and keep
    # both on another -- which changes the row set the projection ships.
    seen: set[str] = set()
    for relative in declared:
        absolute = (root / relative).resolve()
        key = normalise_path(absolute)
        if key in seen:
            continue
        seen.add(key)
        if not absolute.is_dir():
            # An absent surface is a real machine state, reported, not a surface to fabricate rows from.
            continue
        if not inside_root(absolute, root)[0]:
            continue
        name = named.get(PurePath(relative).as_posix(), UNNAMED_SURFACE)
        surfaces.append(Surface(name, str(relative), absolute, SCAN_MAX_DEPTH.get(name, DEFAULT_SCAN_MAX_DEPTH)))
    surfaces.sort(key=lambda item: SURFACE_PRIORITY.index(item.name))
    return surfaces, spill_path


def surface_state(root: Path) -> list[dict[str, Any]]:
    """Every declared surface with whether it exists here — the absent-source report the UI needs."""
    root = Path(root).resolve()
    states = []
    for relative in declared_evidence_roots(root):
        absolute = (root / relative).resolve()
        exists = absolute.is_dir()
        states.append({"root": str(relative), "exists": bool(exists),
                       "insideRepository": inside_root(absolute, root)[0]})
    return states


def _is_reparse_point(entry: os.DirEntry) -> bool:
    """A junction or symlinked directory would let a row resolve outside the surface it was listed under.

    Read from the attributes the directory listing already returned, so on Windows this costs no extra
    syscall — which is the only reason the check can afford to run on every descended directory.
    """
    try:
        info = entry.stat(follow_symlinks=False)
    except OSError:
        return True
    return bool(getattr(info, "st_file_attributes", 0) & FILE_ATTRIBUTE_REPARSE_POINT)


def _walk(surface: Surface) -> tuple[list[dict[str, Any]], dict[str, int]]:
    """Cheap by necessity: only cached type checks and the cached directory-entry stat per file.

    A per-entry ``is_symlink()`` and ``Path.resolve()`` measured 900 ms over this machine's 20k entries —
    each one is an extra syscall, and this runs inside the read path. ``stat(follow_symlinks=False)`` is
    served from the listing itself and also answers the symlink question, since a symlinked file is not a
    regular file under lstat; reparse directories are refused here rather than per row later.
    """
    rows: list[dict[str, Any]] = []
    counters = {"filesObserved": 0, "refusedNames": 0, "prunedDirectories": 0,
                "unreadable": 0, "directoriesWalked": 0, "entriesScanned": 0,
                "reparseDirectories": 0, "notRegularFile": 0}
    stack: list[tuple[str, int]] = [(str(surface.absolute), 0)]
    while stack:
        current, depth = stack.pop()
        counters["directoriesWalked"] += 1
        try:
            iterator = os.scandir(current)
        except OSError:
            counters["unreadable"] += 1
            continue
        with iterator:
            for entry in iterator:
                counters["entriesScanned"] += 1
                if _is_sensitive_name(entry.name):
                    counters["refusedNames"] += 1
                    continue
                try:
                    if entry.is_dir(follow_symlinks=False):
                        if entry.name.lower() in PRUNED_DIRECTORY_NAMES:
                            counters["prunedDirectories"] += 1
                            continue
                        if _is_reparse_point(entry):
                            counters["reparseDirectories"] += 1
                            continue
                        if surface.max_depth is None or depth + 1 < surface.max_depth:
                            stack.append((os.path.normpath(entry.path), depth + 1))
                        continue
                    info = entry.stat(follow_symlinks=False)
                    if not stat_module.S_ISREG(info.st_mode):
                        # Covers a symlink, a device/special file, and anything read_range would call
                        # NOT_A_FILE: no row is promised for it.
                        counters["notRegularFile"] += 1
                        continue
                except OSError:
                    counters["unreadable"] += 1
                    continue
                counters["filesObserved"] += 1
                rows.append({"handle": os.path.normpath(entry.path), "name": entry.name,
                             "surface": surface.name, "surfaceRoot": surface.relative,
                             "sizeBytes": int(info.st_size), "modifiedAt": _now_iso(info.st_mtime),
                             # the ranked term, at the resolution `modifiedAt` discloses
                             "mtimeSecond": int(info.st_mtime), "directory": current})
    return rows, counters


def _walk_all(root: Path, surfaces: list[Surface]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, int]]:
    collected: list[dict[str, Any]] = []
    per_surface: list[dict[str, Any]] = []
    totals = {"refusedNames": 0, "prunedDirectories": 0, "unreadable": 0, "entriesScanned": 0,
              "reparseDirectories": 0, "notRegularFile": 0}
    for surface in surfaces:
        rows, counters = _walk(surface)
        collected.extend(rows)
        for key in totals:
            totals[key] += counters[key]
        per_surface.append({
            "name": surface.name, "root": surface.relative,
            "maxDepth": surface.max_depth, "completeEnumeration": surface.max_depth is None,
            "filesObserved": counters["filesObserved"], "directoriesWalked": counters["directoriesWalked"],
            "refusedBySensitiveName": counters["refusedNames"],
            "prunedRegenerableDirectories": counters["prunedDirectories"],
            "refusedReparseDirectories": counters["reparseDirectories"],
            "refusedNotRegularFile": counters["notRegularFile"],
            "unreadableEntries": counters["unreadable"],
        })
    return collected, per_surface, totals


def _select_by_surface(rows: list[dict[str, Any]], index: dict[str, tuple[str, str]],
                       max_handles: int) -> tuple[list[dict[str, Any]], dict[str, dict[str, int]], int]:
    """Choose the projection's candidates: a reserved share for cited artifacts, then recency per surface.

    The reserve exists because recency alone is the wrong ranking for evidence. On this machine the 163
    artifacts another record already states a digest for are the curated packages of September, and a
    newest-first cap of 200 would have projected none of them — leaving the viewer with a list in which
    nothing it could verify was clickable. A digest is a citation, so a cited artifact gets a declared seat.

    The seats are reserved BEFORE the cap is applied, not after: a reserve that is ordered last is a reserve
    that is trimmed away, which is exactly how the first version of this behaved and what ``seatsFilled``
    would then have contradicted.
    """
    by_surface: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_surface.setdefault(row["surface"], []).append(row)
    report: dict[str, dict[str, int]] = {}
    chosen: dict[str, dict[str, Any]] = {}
    digested = sorted((row for row in rows if row["handle"].lower() in index), key=_rank_row)
    reserve = [row for row in digested[:DIGEST_RESERVE] if len(chosen) < max_handles]
    for row in reserve:
        chosen[row["handle"]] = row
    report["digestReserve"] = {"observed": len(digested), "quota": int(DIGEST_RESERVE),
                               "taken": len(reserve)}
    for name, group in sorted(by_surface.items()):
        quota = SURFACE_QUOTAS.get(name, DEFAULT_QUOTA)
        group.sort(key=_rank_row)
        taken = 0
        for row in group:
            if len(chosen) >= max_handles or taken >= quota:
                break
            if row["handle"] in chosen:
                continue
            chosen[row["handle"]] = row
            taken += 1
        report[name] = {"observed": len(group), "quota": quota, "poolTaken": taken}
    candidates = sorted(chosen.values(), key=_rank_row)
    return candidates, report, len(digested)


def _verify(candidate: dict[str, Any], *, root: Path, surfaces: list[Surface]) -> tuple[str | None, str | None]:
    """Structural re-check of one handle, in pure string terms.

    What is already guaranteed by the walk is not paid for twice: the entry was a regular file under lstat
    (no symlink, no device), it was not under a reparse directory, and every path component it passed was
    name-checked. What is checked here is the claim a reader actually relies on — the handle is absolute,
    stays inside the repository and inside the declared surface it is labelled with, and carries no
    credential-shaped component. Existence is deliberately NOT re-tested per row: ``read_range`` re-checks
    it on use and answers ``NOT_A_FILE``, so a file deleted between projection and click is a typed
    refusal, not a phantom row.
    """
    handle = str(candidate["handle"])
    if not path_is_anchored(handle):
        return None, "not-absolute"
    surface = next((item for item in surfaces if item.name == candidate["surface"]), None)
    if surface is None:
        return None, "unknown-surface"
    # `relative_to` raised ValueError for a case-mismatched or cross-vocabulary path, and the except arm
    # means "outside the declared surface" -- the same conflation CI punished twice in the control plane.
    # Containment is therefore decided from text, and only the case-preserving remainder is used later.
    if not inside_root(handle, root)[0]:
        return None, "outside-declared-surface"
    relative_text = relative_inside(handle, surface.absolute)
    if relative_text is None:
        return None, "outside-declared-surface"
    if any(_is_sensitive_name(part) for part in PurePath(handle).parts):
        return None, "sensitive-name"
    return str(PurePath(handle)), None


def _candidate_digest_records(rows: list[dict[str, Any]], spill_path: str | None, root: Path) -> list[Path]:
    """Records that may state digests: manifest-shaped files the walk already saw, canonical surface first.

    Deliberately built from the enumerated row set rather than by a second recursive scan — an unbounded
    ``rglob`` over the runtime surface measured 6.4 s, which is not something a read path may afford. The
    canonical evidence surface ranks above the runtime surface because that is where this project files the
    digests it intends to be cited; a newest-first order alone let another writer's scratch records crowd
    the budget out.

    The budget below (``MAX_DIGEST_RECORDS``) is applied to a TOTAL order — surface, then the disclosed
    modification second, then handle — because this ranking decides which records get read and therefore
    which rows get a digest and a reserved seat. A partial order here would silently re-inherit walk order
    at the exact point where the projection stops listing and starts choosing.
    """
    candidates: list[Path] = []
    seen: set[str] = set()
    ranked = sorted(rows, key=lambda row: (SURFACE_PRIORITY.index(row["surface"]),
                                           _rank_row(row)))
    for row in ranked:
        name = row["name"].lower()
        if not name.endswith((".json", ".jsonl", ".ndjson")):
            continue
        if not any(mark in name for mark in DIGEST_RECORD_NAME_MARKS):
            continue
        if row["sizeBytes"] > MAX_DIGEST_RECORD_BYTES or row["sizeBytes"] <= 0:
            continue
        if row["handle"] in seen:
            continue
        seen.add(row["handle"])
        candidates.append(Path(row["handle"]))
        if len(candidates) >= MAX_DIGEST_RECORDS:
            break
    if spill_path:
        spill = (Path(root) / spill_path).resolve()
        if str(spill) not in seen and spill.is_file():
            candidates.append(spill)
    ownership = Path(root) / "config" / "config-ownership.json"
    if ownership.is_file() and str(ownership) not in seen:
        candidates.append(ownership)
    return candidates


def _relative(path: Path, root: Path) -> str:
    """Repository-relative provenance, so a digest names the record it came from without a machine path.

    Text containment, not `relative_to`: the old version raised on a case-mismatched pair on a
    case-sensitive host and silently degraded the provenance to a bare filename, which is a weaker citation
    that nothing downstream noticed.
    """
    remainder = relative_inside(path, root)
    if remainder is not None and remainder != "":
        return remainder
    return Path(path).name


def _pairs(node: Any, record: Path, root: Path, index: dict[str, tuple[str, str]],
           lookup: dict[str, str]) -> int:
    """Collect (row handle -> (digest, provenance)) pairs already stated inside a record.

    A stated path is matched against the ALREADY ENUMERATED rows by normalized string comparison, never by
    touching the filesystem: the first version of this join ran ``resolve()`` and ``is_file()`` per stated
    pair and cost 1.1 s over this machine's records, which is the read path's whole budget. A pair that
    names no enumerated row is not indexed — it is either a file that is gone, a source-tree path (never
    enumerated here by design), or a machine path outside the declared surfaces.
    """
    found = 0
    stack: list[Any] = [node]
    while stack:
        current = stack.pop()
        if isinstance(current, dict):
            lowered = {str(key).lower(): value for key, value in current.items()}
            digest = next((lowered[key] for key in DIGEST_VALUE_KEYS
                           if isinstance(lowered.get(key), str)), None)
            stated = next((lowered[key] for key in DIGEST_PATH_KEYS
                           if isinstance(lowered.get(key), str)), None)
            if digest and stated:
                digest = digest.strip()
                if len(digest) == 64 and all(character in HEX_DIGITS for character in digest):
                    for handle in _stated_handles(stated, record, root, lookup):
                        key = handle.lower()
                        if key in index:
                            continue
                        index[key] = (digest.lower(), f"record:{_relative(record, root)}")
                        found += 1
                        if len(index) >= MAX_DIGEST_PAIRS:
                            return found
            stack.extend(current.values())
        elif isinstance(current, list):
            stack.extend(current)
    return found


def _stated_handles(stated: str, record: Path, root: Path, lookup: dict[str, str]) -> Iterator[str]:
    """A record states a path relative to itself or to the repository; try both, keep real rows."""
    text = stated.strip().strip('"')
    if not text or any(marker in text for marker in ("*", "$", "%")) or len(text) > 512:
        return
    candidate = PurePath(text.replace("\\", os.sep).replace("/", os.sep))
    for base in (record.parent, root):
        target = candidate if candidate.is_absolute() else (base / candidate)
        norm = os.path.normpath(str(target))
        if not PurePath(norm).is_absolute():
            continue
        hit = lookup.get(norm.lower())
        if hit is not None:
            yield hit


def _load_record(record: Path) -> list[Any]:
    """Parse a digest-bearing record: one document, or one document per line for a JSONL ledger."""
    text = record.read_text(encoding="utf-8", errors="replace")
    if record.suffix.lower() in (".jsonl", ".ndjson"):
        documents = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            documents.append(json.loads(line))
        return documents
    return [json.loads(text)]


def build_digest_index(rows: list[dict[str, Any]], *, root: Path,
                       spill_path: str | None) -> tuple[dict[str, tuple[str, str]], dict[str, int]]:
    """Index the digests project records already state about the rows that were enumerated.

    Windows paths are compared case-insensitively because records quote them with whatever casing their
    author typed; the emitted handle is the on-disk one from the directory listing.
    """
    root = Path(root)
    index: dict[str, tuple[str, str]] = {}
    stats = {"recordsScanned": 0, "recordsUnreadable": 0, "pairsIndexed": 0}
    lookup = {row["handle"].lower(): row["handle"] for row in rows}
    for record in _candidate_digest_records(rows, spill_path, root):
        stats["recordsScanned"] += 1
        try:
            if record.stat().st_size > MAX_DIGEST_RECORD_BYTES:
                continue
            documents = _load_record(record)
        except (OSError, ValueError):
            stats["recordsUnreadable"] += 1
            continue
        for document in documents:
            stats["pairsIndexed"] += _pairs(document, record, root, index, lookup)
    return index, stats


def project_artifact_handles(*, root: Path, generated_at: str | None = None,
                             max_handles: int = MAX_HANDLES,
                             with_digests: bool = True) -> dict[str, Any]:
    """Enumerate declared evidence artifacts and project them as identity-only rows.

    Returns ``{"handles": [...], "summary": {...}, "absentReason": null}`` when a surface exists, and
    ``{"handles": None, "summary": None, "absentReason": "..."}`` when none does — the caller must not
    collapse "no evidence surface on this machine" into "this project has no evidence".
    """
    started = time.perf_counter()
    root = Path(root).resolve()
    surfaces, spill_path = enumerate_surfaces(root)
    if not surfaces:
        return {"handles": None, "summary": None, "absentReason": "no-declared-evidence-surface",
                "surfaceState": surface_state(root)}
    rows, per_surface, totals = _walk_all(root, surfaces)
    index: dict[str, tuple[str, str]] = {}
    digest_stats = {"recordsScanned": 0, "recordsUnreadable": 0, "pairsIndexed": 0}
    if with_digests:
        index, digest_stats = build_digest_index(rows, root=root, spill_path=spill_path)

    pool, selection, digested_count = _select_by_surface(rows, index, max_handles)
    ordered: list[tuple[float, str, dict[str, Any]]] = []
    dropped: dict[str, int] = {}
    for candidate in pool:
        surface_name = candidate["surface"]
        resolved, reason = _verify(candidate, root=root, surfaces=surfaces)
        if resolved is None:
            dropped[reason or "unknown"] = dropped.get(reason or "unknown", 0) + 1
            continue
        stated = index.get(resolved.lower())
        projected = {
            "handle": resolved,
            "surface": surface_name,
            "surfaceRoot": candidate["surfaceRoot"],
            "kind": KIND_BY_SUFFIX.get(Path(candidate["name"]).suffix.lower(), "other"),
            "sizeBytes": candidate["sizeBytes"],
            "modifiedAt": candidate["modifiedAt"],
            "digestRecorded": stated is not None,
        }
        if stated is not None:
            projected["digest"] = stated[0]
            projected["digestSource"] = stated[1]
        ordered.append((candidate["mtimeSecond"], resolved, projected))
    ordered.sort(key=lambda item: _rank(item[0], item[1]))
    handles = [item[2] for item in ordered[:max_handles]]
    with_digest = sum(1 for row in handles if "digest" in row)

    observed = sum(int(item["observed"]) for name, item in selection.items() if name != "digestReserve")
    truncated = bool(observed > len(handles))
    for item in per_surface:
        item["quotaSelected"] = selection.get(item["name"], {}).get("quota", DEFAULT_QUOTA)
        item["projected"] = sum(1 for row in handles if row["surface"] == item["name"])
    elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
    summary = {
        "schemaVersion": SUMMARY_SCHEMA_VERSION,
        "generatedAt": generated_at or _now_iso(time.time()),
        "surfaces": per_surface,
        "surfaceState": surface_state(root),
        "order": ORDER_LABEL,
        # The disclosure a reader needs when the list is capped: the cap, how many were enumerated, how
        # many survived, whether the tail was cut, how many you are missing, and the exact key that
        # decided which rows those are. A truncation without its ordering key is a truncation that cannot
        # be audited, which is why the validator refuses it.
        "orderingKey": ORDERING_KEY,
        "orderingRule": ORDERING_RULE,
        "selection": {"policy": "digest-reserve-then-newest-per-surface",
                      "orderingKey": ORDERING_KEY,
                      "tieBrokenBy": "handle-asc",
                      "cap": int(max_handles),
                      "capTrimmedTail": bool(len(pool) > len(handles)),
                      "candidatesAfterQuotas": len(pool),
                      "digestReserve": {"artifactsWithRecordedDigest": int(digested_count),
                                        "seats": int(DIGEST_RESERVE),
                                        "filled": int(selection.get("digestReserve", {}).get("taken", 0))},
                      "perSurface": {name: {"observed": int(item["observed"]),
                                            "quota": int(item["quota"])}
                                     for name, item in selection.items() if name != "digestReserve"}},
        "enumeratedCount": observed,
        "projectedCount": len(handles),
        "omittedCount": max(0, observed - len(handles)),
        "cap": int(max_handles),
        "truncated": truncated,
        "complete": bool(not truncated and all(item["completeEnumeration"] for item in per_surface)),
        "refused": {
            "sensitiveNames": totals["refusedNames"],
            "reparseDirectories": totals["reparseDirectories"],
            "notRegularFiles": totals["notRegularFile"],
            "droppedOnVerification": dropped,
            "unreadableEntries": totals["unreadable"],
            "prunedRegenerableDirectories": totals["prunedDirectories"],
        },
        "enumerationScope": "declared-evidence-surfaces-only",
        "digestIndex": {**digest_stats, "rowsWithDigest": with_digest,
                        "rowsWithoutDigest": len(handles) - with_digest,
                        "computedByHashing": False},
        "contentIncluded": False,
        "cost": {"elapsedMs": elapsed_ms, "entriesScanned": totals["entriesScanned"]},
    }
    return {"handles": handles, "summary": summary, "absentReason": None,
            "surfaceState": summary["surfaceState"]}


def load_artifact_handles(root: Path, *, generated_at: str | None = None,
                          max_handles: int = MAX_HANDLES) -> tuple[list[dict[str, Any]] | None,
                                                                   dict[str, Any] | None,
                                                                   str | None]:
    """Composition-root entry point: (handles, summary, absentReason).

    A failure anywhere inside is reported as absent with the reason named, never as an empty list, and
    never as a crash in the read path.
    """
    try:
        projection = project_artifact_handles(root=root, generated_at=generated_at, max_handles=max_handles)
    except Exception as error:  # noqa: BLE001 - the read path must not die over a listing
        return None, None, f"projection-error:{type(error).__name__}"
    return projection["handles"], projection["summary"], projection["absentReason"]
