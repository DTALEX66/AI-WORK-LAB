#!/usr/bin/env python3
"""Bounded, read-only GitHub Actions observer.

This watcher never reruns workflows, writes GitHub state, or blocks a writer
lease. It can consume a sanitized runs JSON fixture for deterministic tests or
query `gh run list` once and emit a versioned observation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterable


DEFERRED_STATES = {"DISCOVERING", "QUEUED_NO_JOB", "QUEUED_WITH_JOB", "RUNNING", "CI_OUTAGE", "PLATFORM_OUTAGE", "CI_RATE_LIMITED", "DEFERRED_CI"}
TERMINAL_STATES = {"SUCCEEDED", "FAILED_PRODUCT", "FAILED_INFRASTRUCTURE", "TIMED_OUT", "CANCELLED", "STALE", "BLOCKED"}


@dataclass(frozen=True)
class WatcherPolicy:
    base_delay_seconds: int = 6
    max_delay_seconds: int = 120
    observation_window_seconds: int = 1200
    queue_stall_seconds: int = 600
    retry_budget: int = 1

    def delay(self, observation_index: int, retry_after: int | None = None) -> int:
        exponential = min(self.max_delay_seconds, self.base_delay_seconds * (2 ** max(0, observation_index)))
        requested = retry_after if retry_after is not None else exponential
        return max(1, min(self.max_delay_seconds, requested))


def _parse_time(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_exact(runs: Iterable[dict[str, Any]], workflow: str, head: str) -> dict[str, Any] | None:
    matches = [run for run in runs if (run.get("workflowName") or run.get("name")) == workflow and run.get("headSha") == head]
    if not matches:
        return None
    return max(matches, key=lambda run: (int(run.get("runAttempt") or run.get("attempt") or 0), str(run.get("createdAt") or "")))


def classify_error(message: str) -> tuple[str, int | None]:
    lowered = message.lower()
    retry_after = None
    for marker in ("retry-after:", "retry after "):
        if marker in lowered:
            tail = lowered.split(marker, 1)[1].strip().split()[0]
            try:
                retry_after = int(tail)
            except ValueError:
                pass
    if "rate limit" in lowered or "429" in lowered or "secondary rate" in lowered:
        return "CI_RATE_LIMITED", retry_after
    if any(token in lowered for token in ("502", "503", "504", "service unavailable", "github api", "network", "connection reset")):
        return "PLATFORM_OUTAGE", retry_after
    if any(token in lowered for token in ("permission denied", "authentication", "not found", "forbidden")):
        return "BLOCKED", retry_after
    return "CI_OUTAGE", retry_after


def classify_runs(
    runs: list[dict[str, Any]],
    required_workflows: tuple[str, ...],
    head: str,
    *,
    aggregate_status: dict[str, str] | None = None,
    now: datetime | None = None,
    policy: WatcherPolicy = WatcherPolicy(),
) -> tuple[str, dict[str, Any]]:
    now = now or datetime.now(timezone.utc)
    if not required_workflows:
        return "BLOCKED", {"message": "no required workflow identity configured"}
    selected = {workflow: _latest_exact(runs, workflow, head) for workflow in required_workflows}
    missing = [workflow for workflow, run in selected.items() if run is None]
    if missing:
        other_head_runs = [run for run in runs if run.get("headSha") and run.get("headSha") != head]
        if not runs or other_head_runs:
            return "QUEUED_NO_JOB", {"workflow": missing[0], "message": "exact-SHA run not visible yet"}
        return "DISCOVERING", {"workflow": missing[0], "message": "discovering exact-SHA workflow run"}

    failures = []
    pending = []
    for workflow, run in selected.items():
        status = str(run.get("status") or "").lower()
        conclusion = str(run.get("conclusion") or "").lower()
        if status != "completed":
            pending.append((workflow, "QUEUED_WITH_JOB" if status in {"queued", "waiting"} else "RUNNING"))
        elif conclusion != "success":
            failures.append((workflow, conclusion))
    if failures:
        infrastructure = {"cancelled", "timed_out", "startup_failure", "action_required", "stale"}
        state = "FAILED_INFRASTRUCTURE" if any(conclusion in infrastructure for _, conclusion in failures) else "FAILED_PRODUCT"
        return state, {"workflow": failures[0][0], "message": "exact-SHA workflow failed", "failures": failures}
    if pending:
        return pending[0][1], {"workflow": pending[0][0], "message": "exact-SHA workflow is still active"}

    if aggregate_status:
        aggregate_values = set(aggregate_status.values())
        if "failed" in aggregate_values:
            return "FAILED_PRODUCT", {"message": "stable aggregate job failed"}
        if aggregate_values - {"success"}:
            return "QUEUED_WITH_JOB", {"message": "stable aggregate job is not complete"}
    return "SUCCEEDED", {"message": "all required exact-SHA workflows and aggregate checks succeeded"}


def make_observation(
    repository: str,
    commit: str,
    state: str,
    *,
    workflow: str | None = None,
    run_id: object = None,
    attempt: int | None = None,
    message: str = "",
    retry_budget: int = 0,
    observation_index: int = 0,
    retry_after: int | None = None,
    policy: WatcherPolicy = WatcherPolicy(),
    observed_at: datetime | None = None,
) -> dict[str, Any]:
    observed_at = observed_at or datetime.now(timezone.utc)
    observation_key = f"{repository}|{commit}|{state}|{workflow or ''}|{run_id or ''}|{attempt or ''}"
    observation_id = hashlib.sha256(observation_key.encode("utf-8")).hexdigest()
    payload: dict[str, Any] = {
        "schema_version": "workflow/ci-observation/v1",
        "observation_id": observation_id,
        "repository": repository,
        "commit": commit,
        "state": state,
        "workflow": workflow,
        "run_id": run_id,
        "attempt": attempt,
        "queue_age_seconds": None,
        "job_count": None,
        "observed_at": observed_at.isoformat().replace("+00:00", "Z"),
        "next_observation_at": None,
        "retry_budget": retry_budget,
        "message": message,
    }
    if state in DEFERRED_STATES:
        delay = policy.delay(observation_index, retry_after)
        payload["next_observation_at"] = (observed_at + timedelta(seconds=delay)).isoformat().replace("+00:00", "Z")
    return payload


def query_runs(repository: str, commit: str) -> list[dict[str, Any]]:
    result = subprocess.run(
        ["gh", "run", "list", "--repo", repository, "--commit", commit, "--limit", "20", "--json", "status,conclusion,workflowName,name,url,databaseId,headSha,attempt,createdAt"],
        check=False,
        text=True, encoding="utf-8", errors="replace",
        capture_output=True,
    )
    if result.returncode:
        state, retry_after = classify_error(result.stderr.strip() or result.stdout.strip())
        raise RuntimeError(json.dumps({"state": state, "retry_after": retry_after, "message": "gh run list failed"}))
    payload = json.loads(result.stdout or "[]")
    if not isinstance(payload, list):
        raise RuntimeError("gh run list returned a non-list response")
    return [run for run in payload if isinstance(run, dict)]


def _write_github_output(path: Path, observation: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write("observation_state=" + str(observation["state"]) + "\n")
        handle.write("observation_json<<WORK_LAB_CI_OBSERVATION\n")
        handle.write(json.dumps(observation, ensure_ascii=False, sort_keys=True) + "\nWORK_LAB_CI_OBSERVATION\n")


def _write_observation(path: Path, observation: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_suffix(path.suffix + ".tmp")
    temp.write_text(json.dumps(observation, ensure_ascii=False, sort_keys=True) + "\n", encoding="utf-8")
    os.replace(temp, path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--commit", required=True)
    parser.add_argument("--workflow", action="append", required=True)
    parser.add_argument("--runs-json", type=Path)
    parser.add_argument("--error")
    parser.add_argument("--observation-index", type=int, default=0)
    parser.add_argument("--retry-budget", type=int, default=1)
    parser.add_argument("--retry-after", type=int)
    parser.add_argument("--github-output", type=Path)
    parser.add_argument("--observation-path", type=Path)
    args = parser.parse_args(argv)
    policy = WatcherPolicy(retry_budget=args.retry_budget)
    if args.error:
        state, retry_after = classify_error(args.error)
        observation = make_observation(args.repository, args.commit, state, message="classified watcher error", retry_budget=args.retry_budget, observation_index=args.observation_index, retry_after=args.retry_after or retry_after, policy=policy)
    else:
        try:
            runs = json.loads(args.runs_json.read_text(encoding="utf-8")) if args.runs_json else query_runs(args.repository, args.commit)
            if not isinstance(runs, list):
                raise ValueError("runs JSON must be a list")
            state, details = classify_runs(runs, tuple(args.workflow), args.commit, policy=policy)
            observation = make_observation(args.repository, args.commit, state, workflow=details.get("workflow"), message=str(details.get("message", "")), retry_budget=args.retry_budget, observation_index=args.observation_index, retry_after=args.retry_after, policy=policy)
        except (OSError, ValueError, json.JSONDecodeError, RuntimeError) as exc:
            state, retry_after = classify_error(str(exc))
            observation = make_observation(args.repository, args.commit, state, message="watcher read failed", retry_budget=args.retry_budget, observation_index=args.observation_index, retry_after=args.retry_after or retry_after, policy=policy)
    if args.github_output:
        _write_github_output(args.github_output, observation)
    if args.observation_path:
        _write_observation(args.observation_path, observation)
    print(json.dumps(observation, ensure_ascii=False, sort_keys=True))
    if observation["state"] == "SUCCEEDED":
        return 0
    if observation["state"] in DEFERRED_STATES:
        return 3
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
