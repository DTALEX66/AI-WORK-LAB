"""Three-way managed-asset guard for the portable Hermes sync.

Design constraints this module must satisfy (independent-review findings
R1, R2, R4, R6):

* **No adoption bypass.** Recording a baseline for live content is a separate,
  explicit operation that touches no asset bytes. It never lets a publish skip
  the refusal checks, and it can only cover targets an operator named together
  with the exact digest they reviewed. (R1)
* **Converged targets are not rewritten.** Only ``CLEAN_UPDATE`` targets are
  published, and every target that will be written is re-evaluated immediately
  before the write. (R2)
* **Deleting a known asset is drift, not a fresh install.** A target that has a
  recorded baseline but is missing live is refused; only a target with no
  baseline at all is created. (R4)
* **The commit is diagnosable, not pretended to be transactional.** A pending
  marker names the run id, the frozen candidate digests and the phase reached,
  so an interrupted run can be classified instead of guessed. (R6)

The module stays pure policy: digests are supplied by the caller so it cannot
drift from the sync's own digest definition.

Verdicts
--------
CONVERGED           live already equals the candidate      -> NOT written
CLEAN_UPDATE        live equals the recorded baseline      -> written
                    (or absent with no baseline: new install)
DELETED_DRIFT       baseline exists but live is missing    -> REFUSE
UNKNOWN_LIVE_CHANGE live differs from baseline & candidate -> REFUSE
NO_BASELINE         live exists with no recorded provenance -> REFUSE
CANDIDATE_ABSENT    repository source is missing           -> REFUSE
SUSPENDED           operator-suspended unit                -> NOT written
"""
from __future__ import annotations

import datetime as dt
import json
import os
from pathlib import Path
from typing import Any, Iterable, Mapping

BASELINE_FILENAME = ".workflow-assistance-baseline.json"
PENDING_FILENAME = ".workflow-assistance-baseline.pending.json"
SCHEMA_VERSION = "workflow/managed-asset-baseline/v1"
PENDING_SCHEMA_VERSION = "workflow/managed-asset-pending/v1"

REFUSING_VERDICTS = frozenset(
    {"UNKNOWN_LIVE_CHANGE", "NO_BASELINE", "DELETED_DRIFT", "CANDIDATE_ABSENT"}
)
PUBLISHABLE_VERDICTS = frozenset({"CLEAN_UPDATE"})


def state_path(home: Path) -> Path:
    return Path(home) / BASELINE_FILENAME


def pending_path(home: Path) -> Path:
    return Path(home) / PENDING_FILENAME


def _empty_state() -> dict[str, Any]:
    return {"schema_version": SCHEMA_VERSION, "targets": {}, "suspended": [], "adopted": []}


# --------------------------------------------------------------------------- #
# state I/O
# --------------------------------------------------------------------------- #
def load_state(home: Path) -> dict[str, Any]:
    """Read the baseline state; a missing or unreadable file yields an empty state."""

    path = state_path(home)
    if not path.is_file():
        return _empty_state()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return _empty_state()
    if not isinstance(data, dict) or data.get("schema_version") != SCHEMA_VERSION:
        return _empty_state()
    if not isinstance(data.get("targets"), dict):
        data["targets"] = {}
    if not isinstance(data.get("suspended"), list):
        data["suspended"] = []
    if not isinstance(data.get("adopted"), list):
        data["adopted"] = []
    return data


def save_state(home: Path, state: Mapping[str, Any], *, run_id: str | None = None) -> Path:
    """Atomically replace the baseline state file."""

    path = state_path(home)
    payload = {
        "schema_version": SCHEMA_VERSION,
        "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "run_id": run_id,
        "live_root": str(home),
        "targets": dict(state.get("targets") or {}),
        "suspended": sorted(str(item) for item in state.get("suspended") or []),
        "adopted": list(state.get("adopted") or []),
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def load_pending(home: Path) -> dict[str, Any] | None:
    path = pending_path(home)
    if not path.is_file():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {"schema_version": PENDING_SCHEMA_VERSION, "phase": "unreadable", "run_id": None}
    return data if isinstance(data, dict) else None


def write_pending(home: Path, *, run_id: str, phase: str, records: Mapping[str, Any]) -> Path:
    path = pending_path(home)
    payload = {
        "schema_version": PENDING_SCHEMA_VERSION,
        "run_id": run_id,
        "phase": phase,
        "written_at": dt.datetime.now(dt.timezone.utc).isoformat(),
        "targets": dict(records),
    }
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(tmp, path)
    return path


def clear_pending(home: Path) -> None:
    path = pending_path(home)
    if path.exists():
        path.unlink()


def pending_diagnosis(home: Path) -> str | None:
    """Return a refusal message when a previous run did not complete.

    The marker exists so an interrupted run can be *classified* rather than
    guessed at: it records the phase that was reached and the frozen candidate
    digests that were about to be published.
    """

    data = load_pending(home)
    if data is None:
        return None
    return (
        "MANAGED_ASSET_RUN_INCOMPLETE a previous run did not finish; assets may be "
        f"partially replaced. run_id={data.get('run_id')} phase={data.get('phase')} "
        f"targets={sorted((data.get('targets') or {}))}. Inspect the listed targets, "
        "then remove the pending marker explicitly to proceed."
    )


def suspended_targets(state: Mapping[str, Any]) -> set[str]:
    return {str(item) for item in (state.get("suspended") or [])}


# --------------------------------------------------------------------------- #
# verdicts
# --------------------------------------------------------------------------- #
def classify(
    *,
    baseline_sha: str | None,
    live_sha: str | None,
    live_exists: bool,
    candidate_sha: str | None,
    suspended: bool = False,
) -> str:
    """Return the verdict for a single managed target."""

    if suspended:
        return "SUSPENDED"
    if candidate_sha is None:
        # The repository no longer provides this asset. Removing live content is
        # never this tool's decision to make on its own.
        return "CANDIDATE_ABSENT"
    if live_exists and live_sha == candidate_sha:
        return "CONVERGED"
    if not live_exists:
        # Absent with no recorded baseline is a genuine first install; absent
        # WITH a baseline means the asset was removed outside this tool.
        return "CLEAN_UPDATE" if baseline_sha is None else "DELETED_DRIFT"
    if baseline_sha is None:
        return "NO_BASELINE"
    if live_sha == baseline_sha:
        return "CLEAN_UPDATE"
    return "UNKNOWN_LIVE_CHANGE"


def evaluate(
    targets: Mapping[str, Mapping[str, Any]],
    state: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Evaluate every target.

    ``targets`` maps a home-relative path to
    ``{"live_sha256", "live_exists", "candidate_sha256"}``.
    """

    baseline = state.get("targets") or {}
    suspended = suspended_targets(state)
    rows: list[dict[str, Any]] = []
    for relative in sorted(targets):
        info = targets[relative]
        record = baseline.get(relative) if isinstance(baseline, dict) else None
        baseline_sha = record.get("sha256") if isinstance(record, dict) else None
        verdict = classify(
            baseline_sha=baseline_sha,
            live_sha=info.get("live_sha256"),
            live_exists=bool(info.get("live_exists")),
            candidate_sha=info.get("candidate_sha256"),
            suspended=relative in suspended,
        )
        rows.append(
            {
                "target": relative,
                "verdict": verdict,
                "baseline_sha256": baseline_sha,
                "live_sha256": info.get("live_sha256"),
                "candidate_sha256": info.get("candidate_sha256"),
                "live_exists": bool(info.get("live_exists")),
            }
        )
    return rows


def refusing_rows(rows: Iterable[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [dict(row) for row in rows if row.get("verdict") in REFUSING_VERDICTS]


def written_targets(rows: Iterable[Mapping[str, Any]]) -> list[str]:
    """Exactly the targets that a publish would write."""

    return [str(row["target"]) for row in rows if row.get("verdict") in PUBLISHABLE_VERDICTS]


def assert_ready(rows: Iterable[Mapping[str, Any]]) -> None:
    """Fail closed before any write. There is deliberately no bypass argument."""

    blockers = refusing_rows(rows)
    if not blockers:
        return
    detail = "; ".join(
        f"{row['target']} verdict={row['verdict']} baseline={row['baseline_sha256']} "
        f"live={row['live_sha256']} candidate={row['candidate_sha256']}"
        for row in blockers
    )
    raise RuntimeError(
        "MANAGED_ASSET_LIVE_CHANGE_REFUSED refusing to publish; resolve each target with "
        "`--adopt-baseline --adopt-target <target>@<reviewed-sha256>` (records a baseline only, "
        "never writes content) or `--suspend <target>`. " + detail
    )


def assert_publish_set_unchanged(
    planned_rows: Iterable[Mapping[str, Any]],
    fresh_rows: Iterable[Mapping[str, Any]],
    live_states: Mapping[str, Any],
) -> None:
    """Re-check every target that is about to be written.

    Two checks, both required: the live digest must not have moved since the
    plan, and the freshly computed verdict for that target must still permit a
    write. This narrows the plan-to-publish window; it does **not** close it.
    A native writer that can act between this call and the replacement is still
    unconstrained, so an affected unit must be suspended when quiescence cannot
    be guaranteed.
    """

    fresh = {str(row["target"]): str(row["verdict"]) for row in fresh_rows}
    problems = []
    for row in planned_rows:
        if row.get("verdict") not in PUBLISHABLE_VERDICTS:
            continue
        target = str(row["target"])
        now = live_states.get(target)
        if now != row.get("live_sha256"):
            problems.append(f"{target} digest moved: planned={row.get('live_sha256')} now={now}")
            continue
        rechecked = fresh.get(target)
        if rechecked not in PUBLISHABLE_VERDICTS:
            problems.append(f"{target} verdict changed on re-check: {rechecked}")
    if problems:
        raise RuntimeError(
            "MANAGED_ASSET_PUBLISH_SET_CHANGED refusing to publish: " + "; ".join(problems)
        )


# --------------------------------------------------------------------------- #
# baseline recording after a successful publish
# --------------------------------------------------------------------------- #
def baseline_records(rows: Iterable[Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Baseline to persist after a successful publish.

    Only targets that were actually written adopt the candidate digest. Suspended
    and refused targets keep whatever baseline they already had, and converged
    targets were not rewritten, so their recorded digest is already the candidate.
    """

    records: dict[str, dict[str, Any]] = {}
    for row in rows:
        target = str(row["target"])
        verdict = row.get("verdict")
        if verdict == "SUSPENDED":
            if row.get("baseline_sha256") is not None:
                records[target] = {"sha256": row["baseline_sha256"]}
            continue
        if verdict in PUBLISHABLE_VERDICTS or verdict == "CONVERGED":
            candidate = row.get("candidate_sha256")
            if candidate is not None:
                records[target] = {"sha256": candidate}
    return records


# --------------------------------------------------------------------------- #
# adoption: records a baseline, never writes asset content
# --------------------------------------------------------------------------- #
def adoption_candidates(
    *,
    reviewed: Mapping[str, str],
    live_digests: Mapping[str, Any],
    state: Mapping[str, Any],
) -> dict[str, dict[str, Any]]:
    """Resolve the targets an operator explicitly adopted.

    ``reviewed`` maps a target to the digest the operator actually reviewed. The
    digest is mandatory: without it there is nothing to prove that the live
    content was looked at, and without that proof adoption would be a blanket
    trust grant - the exact behaviour R1 rejected.

    This function performs no I/O against the live tree and returns a new
    ``targets`` mapping; the caller must never route an adoption through the
    publish path.
    """

    if not reviewed:
        raise ValueError(
            "ADOPTION_REQUIRES_EXPLICIT_TARGETS adoption must name at least one target "
            "together with the digest that was reviewed"
        )
    suspended = suspended_targets(state)
    resolved: dict[str, dict[str, Any]] = {}
    problems = []
    for target, reviewed_sha in sorted(reviewed.items()):
        if not isinstance(reviewed_sha, str) or len(reviewed_sha) < 8:
            problems.append(f"{target} reviewed digest is missing or too short")
            continue
        if target in suspended:
            problems.append(f"{target} is suspended; resume it before adopting")
            continue
        now = live_digests.get(target)
        if now is None:
            problems.append(f"{target} has no live content to adopt")
            continue
        if str(now) != reviewed_sha:
            problems.append(f"{target} changed since review: reviewed={reviewed_sha} now={now}")
            continue
        resolved[target] = {"sha256": reviewed_sha, "adopted_from": "operator-reviewed-live"}
    if problems:
        raise RuntimeError("ADOPTION_REFUSED " + "; ".join(problems))
    return resolved


def apply_adoption(
    state: Mapping[str, Any],
    resolved: Mapping[str, Mapping[str, Any]],
    *,
    operator: str | None = None,
) -> dict[str, Any]:
    """Return the new state with the adopted baselines recorded (no asset writes)."""

    targets = dict(state.get("targets") or {})
    adopted = list(state.get("adopted") or [])
    stamp = dt.datetime.now(dt.timezone.utc).isoformat()
    for target, record in resolved.items():
        targets[target] = {"sha256": record["sha256"]}
        adopted.append(
            {
                "target": target,
                "sha256": record["sha256"],
                "adopted_at": stamp,
                "operator": operator or "unspecified",
                "source": record.get("adopted_from", "operator-reviewed-live"),
            }
        )
    return {
        "targets": targets,
        "suspended": sorted(suspended_targets(state)),
        "adopted": adopted,
    }
