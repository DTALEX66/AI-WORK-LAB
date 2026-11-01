#!/usr/bin/env python3
"""GitHub Collector for TokenTelemetry integration (WLR-110 absorption).

Collects GitHub usage data via gh CLI:
  - Actions workflow runs (token cost, duration, status)
  - API rate limit usage
  - Repository activity (commits, PRs, issues)

Emits events compatible with TokenTelemetry's /telemetry/event API.
"""
import json, os, subprocess, sys
from datetime import datetime, timezone

GH_BIN = os.environ.get("GH_BIN", "gh")


def _gh(*args, timeout=30):
    """Run gh CLI and return parsed JSON or None."""
    try:
        r = subprocess.run(
            [GH_BIN] + list(args),
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=timeout,
        )
        if r.returncode == 0 and r.stdout.strip():
            return json.loads(r.stdout)
    except Exception:
        pass
    return None


def collect_actions_usage(repo=None, limit=20):
    """Collect recent GitHub Actions workflow run usage."""
    cmd = ["run", "list", "--json", "databaseId,name,status,conclusion,createdAt,updatedAt,headBranch,event"]
    if repo:
        cmd.extend(["--repo", repo])
    cmd.extend(["--limit", str(limit)])
    runs = _gh(*cmd) or []

    events = []
    for run in runs:
        # Estimate token cost (GitHub Actions minutes → rough token equivalent)
        started = run.get("createdAt")
        ended = run.get("updatedAt")
        duration_ms = 0
        if started and ended:
            try:
                t0 = datetime.fromisoformat(started.replace("Z", "+00:00"))
                t1 = datetime.fromisoformat(ended.replace("Z", "+00:00"))
                duration_ms = int((t1 - t0).total_seconds() * 1000)
            except Exception:
                pass

        events.append({
            "agent_type": "github",
            "session_id": str(run.get("databaseId", "unknown")),
            "model": f"github-actions:{run.get('name', 'unknown')}",
            "input_tokens": 0,
            "output_tokens": 0,
            "tool_calls": 1,
            "outcome": run.get("conclusion") or run.get("status", "unknown"),
            "started_at": started,
            "finished_at": ended,
            "duration_ms": duration_ms,
            "metadata": {
                "workflow": run.get("name"),
                "branch": run.get("headBranch"),
                "event": run.get("event"),
                "status": run.get("status"),
                "conclusion": run.get("conclusion"),
            },
        })
    return events


def collect_rate_limit():
    """Collect current GitHub API rate limit status."""
    data = _gh("api", "rate_limit")
    if not data:
        return None
    core = data.get("resources", {}).get("core", {})
    return {
        "agent_type": "github",
        "session_id": "rate-limit",
        "model": "github-api",
        "input_tokens": core.get("remaining", 0),
        "output_tokens": 0,
        "tool_calls": 0,
        "outcome": "ok",
        "metadata": {
            "limit": core.get("limit"),
            "remaining": core.get("remaining"),
            "reset": core.get("reset"),
        },
    }


def collect_recent_commits(repo=None, limit=10):
    """Collect recent commits for activity tracking."""
    cmd = ["log", "--json", "--limit", str(limit)]
    if repo:
        cmd.extend(["--repo", repo])
    else:
        cmd.extend(["-C", os.getcwd()])

    try:
        r = subprocess.run(
            [GH_BIN] + cmd if not repo else ["git"] + cmd,
            capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=15,
        )
        if r.returncode != 0:
            return []
        commits = json.loads(r.stdout) if r.stdout.strip() else []
    except Exception:
        return []

    events = []
    for c in commits:
        events.append({
            "agent_type": "github",
            "session_id": c.get("oid", "unknown")[:12],
            "model": "git-commit",
            "input_tokens": 0,
            "output_tokens": len(c.get("message", "")),
            "tool_calls": 1,
            "outcome": "ok",
            "started_at": c.get("author", {}).get("date"),
            "metadata": {
                "message": c.get("message", "").split("\n")[0][:80],
                "author": c.get("author", {}).get("name"),
            },
        })
    return events


def emit_tokentelemetry_event(event):
    """Convert to TokenTelemetry format."""
    return {
        "agent": event.get("agent_type", "github"),
        "sessionId": event.get("session_id", "unknown"),
        "model": event.get("model", "unknown"),
        "inputTokens": event.get("input_tokens", 0),
        "outputTokens": event.get("output_tokens", 0),
        "toolCalls": event.get("tool_calls", 0),
        "outcome": event.get("outcome", "unknown"),
        "startedAt": event.get("started_at"),
        "finishedAt": event.get("finished_at"),
        "metadata": event.get("metadata"),
    }


if __name__ == "__main__":
    repo = sys.argv[1] if len(sys.argv) > 1 else None
    events = []
    events.extend(collect_actions_usage(repo))
    rl = collect_rate_limit()
    if rl:
        events.append(rl)
    events.extend(collect_recent_commits(repo))
    print(json.dumps([emit_tokentelemetry_event(e) for e in events], indent=2))
