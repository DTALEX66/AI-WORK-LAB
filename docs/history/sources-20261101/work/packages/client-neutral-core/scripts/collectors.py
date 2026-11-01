"""Four bounded collectors for the Workflow Assistance worker (WL3-510).

All collectors are read-only against their sources and write normalized
canonical facts. No prompt/response bodies, credentials, tokens, or sensitive
absolute paths are ever stored. Degraded sources produce STALE/UNKNOWN values
and last-good ages instead of fabricated EXACT/LIVE/0 values.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import stat
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from canonical_store import CanonicalStore
from durable_worker import CollectorResult

TOKEN_FILE_NAME_RE = re.compile(r".*?(usage|token|tokens|usage_rollup).*\.jsonl?$", re.IGNORECASE)
SENSITIVE_PATH_FRAGMENTS = ("appdata", "users", "documents", "desktop", "downloads", "keys", "secrets")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _stable_id(prefix: str, *parts: object) -> str:
    encoded = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(encoded).hexdigest()[:32]}"


def _note_refusal(counts: dict[str, int], samples: dict[str, str], reason: str, where: str) -> None:
    """Count a row the collector could not turn into a fact, and keep the first place it happened.

    A bare count is a number; a count with one location is a lead. The sample is deliberately the FIRST
    occurrence, because a refusal that keeps overwriting its own sample reports only the newest symptom.
    """
    counts[reason] = counts.get(reason, 0) + 1
    samples.setdefault(reason, where)


def _git(root: Path, *args: str) -> str | None:
    try:
        result = subprocess.run(
            ["git", *args], cwd=root, text=True, encoding="utf-8", errors="replace", capture_output=True, check=False, timeout=30
        )
    except (OSError, subprocess.SubprocessError):
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _sanitize_path(path: str) -> str:
    """Keep only a stable, non-sensitive project-relative key."""
    normalized = path.replace("\\", "/")
    for fragment in SENSITIVE_PATH_FRAGMENTS:
        if fragment in normalized.lower():
            return "<redacted-home-path>"
    return normalized


def _resolved_path(path: Path) -> Path:
    """The real location behind `path`, links followed. A seam the containment tests convict through."""
    return Path(os.path.realpath(path))


def _is_link(path: Path) -> bool:
    """True for a symlink AND for the Windows junction/mount point that `is_symlink()` does not see.

    Measured on this host (CPython 3.11, NTFS): a directory junction reports `Path.is_symlink() == False`
    and `os.path.islink() == False`, while `st_file_attributes` carries the reparse bit -- and `rglob("*")`
    walks through it, handing back files whose bytes live outside the searched root. So the two predicates
    here are only a fast rejection of a linked leaf; the containment of the RESOLVED target in
    `_confined_read` is what actually convicts a link sitting in an ancestor directory.
    """
    if path.is_symlink():
        return True
    reparse = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0)
    if not reparse:  # POSIX: no reparse attribute exists, is_symlink() already covered the case
        return False
    try:
        info = path.lstat()
    except OSError:
        return False
    return bool(getattr(info, "st_file_attributes", 0) & reparse)


def _walk_confined(search_root: Path, root_resolved: Path) -> tuple[list[Path], list[Path]]:
    """Files reachable inside the root, plus the directory links that escape it -- at most one entry each.

    `rglob("*")` follows every directory link, so one planted escape was counted once per file behind it
    and the total came out platform-dependent: the same fixture that produced one refusal here produced a
    different count on a POSIX runner, which is what turned CI red over a locally green run. The walk is
    explicit now. A link resolving INSIDE the root is traversed -- its files are still read and still
    cited by where the bytes really live -- and a link resolving OUTSIDE is reported once, undescended.
    """
    files: list[Path] = []
    escapes: list[Path] = []
    stack = [search_root]
    visited = {str(root_resolved)}
    while stack:
        current = stack.pop()
        try:
            entries = sorted(os.scandir(current), key=lambda e: e.name)
        except OSError:
            continue
        for entry in entries:
            path = Path(entry.path)
            if _is_link(path):
                resolved = _resolved_path(path)
                if not resolved.is_relative_to(root_resolved):
                    escapes.append(path)
                elif resolved.is_dir():
                    if str(resolved) not in visited:
                        visited.add(str(resolved))
                        stack.append(path)
                elif resolved.is_file():
                    files.append(path)
                continue
            if entry.is_dir(follow_symlinks=False):
                stack.append(path)
            elif entry.is_file(follow_symlinks=False):
                files.append(path)
    return files, escapes


@dataclass(frozen=True)
class _ConfinedRead:
    """Outcome of one guarded read: either text plus the location it truly came from, or a named refusal."""
    text: str | None = None
    resolved: Path | None = None
    reason: str | None = None
    detail: str = ""


def _confined_read(candidate: Path, root_resolved: Path) -> _ConfinedRead:
    """Read `candidate` only while it provably stays inside `root_resolved`.

    The resolved-path containment is re-checked at READ time, not only where the directory walk produced the
    name: enumeration and read are separate syscalls, so a link that was inside the root when the name was
    listed can point outside by the time the bytes are taken (and the other way round). The identity compare
    on the opened fd is what makes the bytes themselves evidence, because the fd stays bound to the inode it
    opened -- anything repointed after the open cannot redirect this read.

    How far that actually closes the window is stated per platform, and it is not closed everywhere:
      * POSIX -- `os.O_NOFOLLOW` makes the open itself refuse a leaf link, and the `fstat`/`stat`
        `st_dev`/`st_ino` comparison convicts a swap of the leaf or of an ancestor between check and open.
      * Windows -- no `O_NOFOLLOW` and no stdlib fd-to-final-path call, so the only closing evidence is the
        re-resolve immediately before reading plus the identity compare (meaningful on NTFS, where `st_ino`
        is the file id; vacuous where a filesystem reports a constant id). A repoint landing after that
        re-resolve and before `handle.read()` is NOT detectable with stdlib. Narrowed, not closed.
    """
    if _is_link(candidate):
        return _ConfinedRead(reason="symlink_candidate_refused", detail="leaf is a link")
    try:
        checked = os.stat(candidate)
    except OSError as exc:
        return _ConfinedRead(reason="file_unreadable", detail=type(exc).__name__)
    resolved = _resolved_path(candidate)
    if not resolved.is_relative_to(root_resolved):
        return _ConfinedRead(reason="symlink_outside_root", detail="resolved target escapes the root")
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    try:
        fd = os.open(candidate, flags)
    except OSError as exc:
        return _ConfinedRead(reason="file_unreadable", detail=type(exc).__name__)
    try:
        opened = os.fstat(fd)
        if (checked.st_dev, checked.st_ino) != (opened.st_dev, opened.st_ino):
            return _ConfinedRead(reason="file_identity_moved_before_read", detail="fd is not the checked file")
        recheck = _resolved_path(candidate)
        if not recheck.is_relative_to(root_resolved):
            return _ConfinedRead(reason="symlink_outside_root", detail="escape seen at read time")
        try:
            with os.fdopen(fd, "r", encoding="utf-8", errors="replace", closefd=False) as handle:
                text = handle.read()
        except OSError as exc:
            return _ConfinedRead(reason="file_unreadable", detail=type(exc).__name__)
    finally:
        os.close(fd)
    return _ConfinedRead(text=text, resolved=recheck)


def collect_task_ledger(store: CanonicalStore, project_id: str) -> CollectorResult:
    """Collector 1: task ledger counts as canonical facts, for THIS project.

    Two things the previous version got wrong with one constant. It counted `store.list_tasks()` -- every
    project's rows -- while stamping the record with a single `project_id`, so a second registered project
    was silently included in the first one's totals. And it wrote `coverage: "PARTIAL"` unconditionally,
    which `issue_projection` turns into a standing `SOURCE_INCOMPLETE_COVERAGE` issue that no repair can
    ever close, because it was never an observation. Coverage is now derived: the ledger is the whole
    population of tasks it holds, so a complete read is FULL, and what makes it PARTIAL is a row this
    collector actually could not attribute -- an empty `project_id`, or a status it cannot classify.
    """
    tasks = store.list_tasks()
    mine = [task for task in tasks if str(task.get("project_id") or "") == project_id]
    unattributed = sum(1 for task in tasks if not str(task.get("project_id") or "").strip())
    by_status: dict[str, int] = {}
    for task in mine:
        status = str(task.get("status") or "UNKNOWN")
        by_status[status] = by_status.get(status, 0) + 1
    unclassified = by_status.get("UNKNOWN", 0)
    coverage = "FULL" if not (unattributed or unclassified) else "PARTIAL"
    records = [
        {
            "event_id": _stable_id("task-ledger", project_id, by_status, unattributed),
            "project_id": project_id,
            "producer": "task-ledger-collector",
            "occurred_at": _now(),
            "freshness": "EXACT_SOURCE",
            "coverage": coverage,
            "quality": "EXACT_SOURCE",
            "task_counts": by_status,
            "total": len(mine),
            "unattributed": unattributed,
            "coverage_why": (
                "台账内每行都归到了本项目且状态可分类" if coverage == "FULL"
                else f"{unattributed} 行无项目归属、{unclassified} 行状态为 UNKNOWN"),
        }
    ]
    return CollectorResult(kind="telemetry", ok=True, records=records)


def collect_git_ci(store: CanonicalStore, project_id: str, project_root: Path) -> CollectorResult:
    """Collector 2: read-only git/CI status for the owning project."""
    head = _git(project_root, "rev-parse", "HEAD")
    branch = _git(project_root, "branch", "--show-current")
    dirty_raw = _git(project_root, "status", "--porcelain=v1") or ""
    dirty = len([line for line in dirty_raw.splitlines() if line.strip()])
    records: list[dict[str, Any]] = []
    if head:
        records.append(
            {
                "row_id": f"git-{project_id}",
                "project_id": project_id,
                "scope": "git",
                "quality": "EXACT_SOURCE" if head else "UNKNOWN",
                "coverage": "PARTIAL",
                "freshness": "STALE",
                "observed_at": _now(),
                "last_good_at": _now() if head else None,
                "head_sha": head,
                "branch": branch or "detached",
                "dirty_count": dirty,
                "sourceRef": "git-rev-parse",
            }
        )
    return CollectorResult(kind="quality", ok=True, records=records)


def collect_usage_files(store: CanonicalStore, project_id: str, search_root: Path) -> CollectorResult:
    """Collector 3: explicit usage counters from local JSON/JSONL, never estimates.

    Only numeric usage fields are accepted; auth tokens and prompt/response
    bodies are rejected by the store. Files are found only inside the project
    runtime root, never by scanning user profile paths.

    The root is a *containment* boundary, not just a search prefix: a directory link planted in the root
    would otherwise hand back bytes that live outside it while the record cited an in-root name.
    `_walk_confined` is what enforces that, and it counts an escape once instead of once per file behind
    it -- the per-file count was platform-dependent and made the same fixture disagree between runners.
    """
    records: list[dict[str, Any]] = []
    refusals: dict[str, int] = {}
    samples: dict[str, str] = {}
    if search_root.is_dir():
        root_resolved = _resolved_path(search_root)
        found, escaped_links = _walk_confined(search_root, root_resolved)
        for escaped in sorted(escaped_links):
            try:
                escaped_ref = escaped.relative_to(search_root).as_posix()
            except ValueError:
                escaped_ref = escaped.name
            # One escape, one count. The locator is the in-root name: a refusal sample rides into the
            # sidecar snapshot, and the outside target it points at is never written out.
            _note_refusal(refusals, samples, "symlink_outside_root",
                          f"{escaped_ref}: directory link escapes the search root")
        for candidate in sorted(found):
            if not candidate.is_file():
                continue
            if not TOKEN_FILE_NAME_RE.match(candidate.name):
                continue
            try:
                listed_ref = candidate.relative_to(search_root).as_posix()
            except ValueError:
                listed_ref = candidate.name
            outcome = _confined_read(candidate, root_resolved)
            if outcome.reason:
                # Locator is the IN-ROOT name only. The outside target is deliberately never written out:
                # a refusal sample rides into the sidecar snapshot, and an absolute home path there is the
                # leak this module's docstring forbids.
                _note_refusal(refusals, samples, outcome.reason,
                              f"{listed_ref}: {outcome.detail}" if outcome.detail else listed_ref)
                continue
            text = outcome.text or ""
            resolved = outcome.resolved or candidate
            try:
                # `source_ref` cites where the bytes actually live. For a plain file that is the same
                # in-root path as before; for a file reached through a link that stays inside the root it
                # names the real location instead of laundering the origin into the link's name.
                source_ref = resolved.relative_to(root_resolved).as_posix()
            except ValueError:
                source_ref = resolved.name
            content_occurrences: dict[str, int] = {}
            for line_number, line in enumerate(text.splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    item = json.loads(line)
                except json.JSONDecodeError:
                    _note_refusal(refusals, samples, "line_unparseable_json",
                                  f"{source_ref}:{line_number}")
                    continue
                if not isinstance(item, dict):
                    _note_refusal(refusals, samples, "line_not_an_object", f"{source_ref}:{line_number}")
                    continue
                tokens = {
                    key: item[key]
                    for key in (
                        "input_tokens", "output_tokens", "cache_read_tokens",
                        "cache_write_tokens", "reasoning_tokens", "tool_tokens",
                        "subagent_tokens", "total_tokens",
                    )
                    if isinstance(item.get(key), int) and item[key] >= 0
                }
                if not tokens:
                    _note_refusal(refusals, samples, "line_has_no_usable_token_fields",
                                  f"{source_ref}:{line_number}")
                    continue
                provider = str(item.get("provider", "unknown"))
                model = str(item.get("model", "unknown"))
                content_identity = json.dumps(
                    {"provider": provider, "model": model, **tokens},
                    ensure_ascii=False,
                    sort_keys=True,
                    separators=(",", ":"),
                )
                content_occurrences[content_identity] = content_occurrences.get(content_identity, 0) + 1
                if candidate.suffix.lower() == ".jsonl":
                    # JSONL is an event log. Keep identities stable across
                    # prepend/reorder while preserving identical real events.
                    sample_identity: object = (
                        content_identity,
                        content_occurrences[content_identity],
                    )
                else:
                    # A .json rollup is a mutable snapshot; its row updates in
                    # place instead of accumulating every observed value.
                    sample_identity = line_number
                records.append(
                    {
                        "project_id": project_id,
                        "provider": provider,
                        "model": model,
                        "observed_at": _now(),
                        "quality": "EXACT_SOURCE",
                        "source_ref": _sanitize_path(source_ref),
                        "sample_id": _stable_id("usage", project_id, source_ref, sample_identity),
                        # Diagnostic locator only: `record_usage_sample` inserts named columns, so this key is
                        # never persisted. Without it a store-level refusal (a credential shape in `provider`)
                        # could name the file but not the line, and "which line did we refuse" is the question
                        # the surface is asked.
                        "source_line": line_number,
                        **tokens,
                    }
                )
    # Coverage is derived from what this walk actually refused, the same rule `collect_growth_watcher`
    # follows -- it is not a word written next to the records. `refusals` is only final once the walk is
    # done, so the stamp goes on afterwards; a link escape counted here is a real incomplete read, and a
    # clean read of an empty directory stays FULL.
    coverage = "PARTIAL" if refusals else "FULL"
    coverage_why = (
        f"{sum(refusals.values())} 项被具名拒绝：" + "、".join(sorted(refusals))
        if refusals else "根目录内候选文件全部在边界内读取")
    for record in records:
        # Diagnostic only, like `source_line`: `record_usage_sample` inserts named columns, so neither key
        # is persisted; the counted refusals reach the surface through `CollectorResult.refusals`.
        record["coverage"] = coverage
        record["coverage_why"] = coverage_why
    return CollectorResult(kind="usage", ok=True, records=records, refusals=refusals,
                           refusal_samples=samples)


def collect_source_quality(store: CanonicalStore, project_id: str, project_root: Path) -> CollectorResult:
    """Collector 4: source-quality facts (freshness/coverage/quality)."""
    head = _git(project_root, "rev-parse", "HEAD")
    quality = "EXACT_SOURCE" if head else "UNKNOWN"
    record = {
        "row_id": f"quality-{project_id}-source",
        "project_id": project_id,
        "scope": "source",
        "quality": quality,
        "coverage": "PARTIAL",
        "freshness": "STALE",
        "observed_at": _now(),
        "last_good_at": _now() if head else None,
        "sourceRef": "git-head" if head else "unavailable",
    }
    return CollectorResult(kind="quality", ok=True, records=[record])


def collect_growth_watcher(store: CanonicalStore, project_id: str, search_root: Path) -> CollectorResult:
    """Collector 5 (WL3-300): discovery watcher over allowed project-adjacent dirs.

    Looks for candidate growth assets (skills/plugins/context packs) in the
    project's own runtime boundaries and classifies them with the existing
    growth pipeline state machine. Pure metadata (names, digests, statuses);
    never copies content bodies and never promotes anything automatically.
    """
    from growth_candidates import intake, source_digest

    candidates: list[dict[str, Any]] = []
    refusals: dict[str, int] = {}
    samples: dict[str, str] = {}
    probe_dirs = [
        search_root / ".hermes" / "growth-candidates",
        search_root / ".agents" / "skills",
        search_root / ".hermes" / "desktop-attachments",
    ]
    for probe_dir in probe_dirs:
        if not probe_dir.is_dir():
            continue
        try:
            entries = sorted(probe_dir.iterdir())
        except OSError as exc:
            _note_refusal(refusals, samples, "probe_dir_unreadable",
                          f"{probe_dir.name}: {type(exc).__name__}")
            continue
        for entry in entries:
            if not entry.is_file():
                continue
            name = entry.name.lower()
            if not (name.endswith((".md", ".json", ".yaml", ".yml")) or name.endswith(".zip")):
                continue
            candidates.append(
                {
                    "candidate_id": f"{project_id}-{entry.name}",
                    "origin": "local-discovery",
                    "classification": "learn",
                    "risk": "low",
                    "source": {"name": entry.name, "size": entry.stat().st_size},
                }
            )
    records: list[dict[str, Any]] = []
    for candidate in candidates:
        try:
            item = intake(
                candidate["candidate_id"],
                candidate["origin"],
                candidate["classification"],
                candidate["risk"],
                candidate["source"],
            )
        except ValueError as exc:
            # The old comment here read "quarantine implicitly by omission". Implicit omission is exactly
            # what the truth discipline refuses: a candidate that was found and then rejected must arrive
            # as a named, counted refusal, or the empty list reads as "nothing to grow from".
            _note_refusal(refusals, samples, "candidate_rejected_by_intake",
                          f"{candidate['candidate_id']}: {str(exc)[:120]}")
            continue
        records.append(
            {
                "event_id": _stable_id("growth", item["candidateId"], source_digest(candidate["source"])),
                "project_id": project_id,
                "producer": "growth-watcher-collector",
                "occurred_at": _now(),
                "freshness": "EXACT_SOURCE",
                # Derived, not declared: a candidate this collector could not intake is the only thing that
                # makes the growth read incomplete, and that count is already computed above.
                "coverage": "PARTIAL" if refusals else "FULL",
                "coverage_why": (f"{sum(refusals.values())} 个候选被具名拒绝" if refusals
                                 else "扫描到的候选全部入账"),
                "quality": "EXACT_SOURCE",
                "candidate_id": item["candidateId"],
                "candidate_status": item["status"],
                "candidate_risk": item["risk"],
                "source_digest": source_digest(candidate["source"]),
            }
        )
    return CollectorResult(kind="telemetry", ok=True, records=records, refusals=refusals,
                           refusal_samples=samples)


def build_standard_collectors(project_root: Path) -> list[Any]:
    """Standard collector set bound to a project root."""
    from durable_worker import CollectorFn

    def task_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
        return collect_task_ledger(store, project_id)

    def git_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
        # Multi-project: collect git truth for every approved project root.
        # Unapproved roots are never scanned; missing roots are skipped.
        rows = store.list_projects()
        records: list[dict[str, Any]] = []
        ok_any = False
        err: str | None = None
        for row in rows:
            pid = str(row.get("project_id") or row.get("projectId") or "")
            if not pid:
                continue
            definition = store.get_project_definition(pid)
            if definition and not definition.get("approved", False):
                continue
            root = (definition or {}).get("root_path") or row.get("root_path")
            if not root:
                continue
            rp = Path(root)
            if not (rp / ".git").exists():
                continue
            result = collect_git_ci(store, pid, rp)
            records.extend(result.records)
            ok_any = ok_any or result.ok
            if result.error:
                err = result.error
        return CollectorResult(kind="quality", ok=ok_any or bool(records), records=records,
                               error=err)

    def usage_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
        return collect_usage_files(
            store,
            project_id,
            project_root / ".hermes" / "task-artifacts",
        )

    def quality_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
        return collect_source_quality(store, project_id, project_root)

    def growth_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
        return collect_growth_watcher(store, project_id, project_root)

    def platform_collector(store: CanonicalStore, project_id: str) -> CollectorResult:
        from platform_collector import collect_platform_observations
        return collect_platform_observations(store, project_id)

    return [task_collector, git_collector, usage_collector, quality_collector,
            growth_collector, platform_collector]


if __name__ == "__main__":
    import argparse

    from project_temp import require_runtime_root

    parser = argparse.ArgumentParser(description="Run the standard collectors once")
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--project-id", default="work-lab")
    parser.add_argument("--runtime-root", type=Path)
    args = parser.parse_args()
    runtime_root = require_runtime_root(args.runtime_root, "workflow-assistance-collectors")
    store = CanonicalStore(runtime_root / "canonical.sqlite")
    try:
        results = []
        for collector in build_standard_collectors(args.project_root):
            outcome = collector(store, args.project_id)
            results.append({"kind": outcome.kind, "ok": outcome.ok, "records": len(outcome.records)})
        print(json.dumps({"collectors": results, "integrity": store.integrity_check()}, ensure_ascii=False, indent=2))
    finally:
        store.close()
