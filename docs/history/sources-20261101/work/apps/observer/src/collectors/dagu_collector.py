#!/usr/bin/env python3
"""Dagu Collector for TokenTelemetry integration (WLR-110 absorption).

Reads Dagu's local data (~/.dagu/) and emits telemetry events compatible
with TokenTelemetry's /telemetry/event API.

Data sources:
  - ~/.dagu/data/dag-runs/<dag>/.../dag.json     — DAG definition + steps
  - ~/.dagu/data/dag-runs/<dag>/.../status.jsonl  — per-step execution status
  - ~/.dagu/logs/<dag>/dag-run_*/dag-run_*.log    — execution logs

Emits: token usage (N/A for shell steps), step timing, success/failure,
       DAG-level cost aggregation.
"""
import json, os, sys, glob, base64
from pathlib import Path
from datetime import datetime

DAGU_HOME = Path(os.environ.get("DAGU_HOME") or (Path.home() / ".dagu")).expanduser()
DAG_RUNS_DIR = DAGU_HOME / "data" / "dag-runs"
LOGS_DIR = DAGU_HOME / "logs"

# Dagu status codes
STATUS_MAP = {0: "pending", 1: "running", 2: "cancelled", 3: "skipped", 4: "succeeded", 5: "failed"}


def _decode_steps(dag_def):
    """Decode steps from dag.json — they live in yamlData (base64 YAML)."""
    steps = dag_def.get("steps")
    if steps:
        return steps
    yaml_b64 = dag_def.get("yamlData", "")
    if yaml_b64:
        try:
            import yaml
            parsed = yaml.safe_load(base64.b64decode(yaml_b64).decode())
            return parsed.get("steps", [])
        except Exception:
            pass
    return []


def scan_dag_runs():
    """Scan all DAG runs and yield structured telemetry events."""
    events = []
    if not DAG_RUNS_DIR.exists():
        return events

    for dag_dir in DAG_RUNS_DIR.iterdir():
        if not dag_dir.is_dir():
            continue
        dag_name = dag_dir.name
        for run_dir in dag_dir.rglob("dag.json"):
            try:
                dag_def = json.loads(run_dir.read_text(encoding="utf-8"))
                status_file = run_dir.parent / "status.jsonl"
                status_data = None
                if status_file.exists():
                    with open(status_file, encoding="utf-8") as fh:
                        first_line = fh.readline().strip()
                        if first_line:
                            status_data = json.loads(first_line)

                steps = _decode_steps(dag_def)
                nodes = status_data.get("nodes", []) if status_data else []

                # Compute timing
                started = status_data.get("startedAt") if status_data else None
                finished = status_data.get("finishedAt") if status_data else None
                overall_status = STATUS_MAP.get(
                    status_data.get("status", -1) if status_data else -1, "unknown"
                )

                # Step-level telemetry
                step_events = []
                for node in nodes:
                    step_name = node.get("step", {}).get("name", "unknown")
                    step_status = STATUS_MAP.get(node.get("status", -1), "unknown")
                    step_started = node.get("startedAt")
                    step_finished = node.get("finishedAt")
                    duration_ms = 0
                    if step_started and step_finished:
                        try:
                            t0 = datetime.fromisoformat(step_started)
                            t1 = datetime.fromisoformat(step_finished)
                            duration_ms = int((t1 - t0).total_seconds() * 1000)
                        except Exception:
                            pass

                    step_events.append({
                        "step_name": step_name,
                        "status": step_status,
                        "duration_ms": duration_ms,
                        "stdout_path": node.get("stdout"),
                        "stderr_path": node.get("stderr"),
                    })

                event = {
                    "agent_type": "dagu",
                    "session_id": status_data.get("dagRunId", "unknown") if status_data else "unknown",
                    "dag_name": dag_name,
                    "status": overall_status,
                    "started_at": started,
                    "finished_at": finished,
                    "step_count": len(steps),
                    "steps": step_events,
                    "model": "shell",  # Dagu runs shell commands, not LLMs
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "tool_calls": len(steps),
                }
                events.append(event)
            except Exception as e:
                events.append({"agent_type": "dagu", "error": str(e), "dag_name": dag_name})

    return events


def emit_tokentelemetry_event(event):
    """Emit a single event in TokenTelemetry's expected format."""
    return {
        "agent": "dagu",
        "sessionId": event.get("session_id", "unknown"),
        "model": event.get("model", "shell"),
        "inputTokens": event.get("input_tokens", 0),
        "outputTokens": event.get("output_tokens", 0),
        "toolCalls": event.get("tool_calls", 0),
        "outcome": event.get("status", "unknown"),
        "startedAt": event.get("started_at"),
        "finishedAt": event.get("finished_at"),
        "metadata": {
            "dag_name": event.get("dag_name"),
            "step_count": event.get("step_count"),
            "steps": event.get("steps"),
        },
    }


if __name__ == "__main__":
    events = scan_dag_runs()
    print(json.dumps([emit_tokentelemetry_event(e) for e in events], indent=2))
