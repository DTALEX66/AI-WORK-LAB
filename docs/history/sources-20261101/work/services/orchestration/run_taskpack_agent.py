"""Run one TaskPack through one persistent Hermes writer lineage.

Unlike the retired fixed-window loop, this runner never kills and restarts a writer
on a timer. High-risk work is frozen, reviewed synchronously, resumed by session ID
for findings, and released only after an exact-tree GO.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

import yaml

try:
    from .task_ledger import TaskLedger
except ImportError:  # pragma: no cover - direct script execution
    try:
        from task_ledger import TaskLedger
    except ImportError:  # pragma: no cover - importlib test harness
        _candidates = [
            Path(__file__).with_name("task_ledger.py"),
            Path(__file__).resolve().parents[2] / "packages" / "client-neutral-core" / "scripts" / "task_ledger.py",
        ]
        _ledger_path = next((c for c in _candidates if c.is_file()), None)
        if _ledger_path is None:
            raise ImportError("unable to locate task_ledger.py (sibling or packages/client-neutral-core/scripts)")
        _ledger_spec = __import__("importlib.util", fromlist=["spec_from_file_location"]).spec_from_file_location(
            "task_ledger", _ledger_path
        )
        if _ledger_spec is None or _ledger_spec.loader is None:
            raise ImportError("unable to load task_ledger.py")
        _ledger_module = __import__("importlib.util", fromlist=["module_from_spec"]).module_from_spec(_ledger_spec)
        sys.modules[_ledger_spec.name] = _ledger_module
        _ledger_spec.loader.exec_module(_ledger_module)
        TaskLedger = _ledger_module.TaskLedger

DEFAULT_SKILLS = (
    "project-data-boundary,agent-workflow-fortress,test-driven-development,"
    "systematic-debugging,github-pr-workflow"
)
SESSION_PATTERN = re.compile(r"(?m)^session_id:\s*(\S+)\s*$")
FORCED_HIGH_PATH_PATTERNS = (
    re.compile(r"(?:^|[\s`'\"(])\.github/", re.I),
    re.compile(r"(?:^|[\s`'\"(])config/", re.I),
    re.compile(r"(?:^|[\s`'\"(])setup\.(?:sh|ps1)(?:$|[\s`'\")])", re.I),
    re.compile(r"(?:^|[\s`'\"(])bin/", re.I),
    re.compile(r"(?:^|[\s`'\"(])scripts/security/", re.I),
    re.compile(r"(?:^|[\s`'\"(])scripts/workflow/sync_[^\s`'\")]+", re.I),
    re.compile(r"(?:^|[\s`'\"(])scripts/workflow/switch_model\.py", re.I),
    re.compile(r"(?:^|[\s`'\"(])workflow-manifest\.yaml", re.I),
    re.compile(r"(?:^|[\s`'\"(])pyproject\.toml", re.I),
)
FORCED_HIGH_OPERATION_PATTERN = re.compile(
    r"\b(?:credential|credentials|authentication|permission|provider[ _-]?change|"
    r"dependency[ _-]?change|schema[ _-]?migration|delete|move|external[ _-]?path[ _-]?write|"
    r"backup[ _-]?restore|packaging|deployment|release|"
    r"github[ _-]?ruleset|live[ _-]?apply)\b",
    re.I,
)
CRITICAL_OPERATION_PATTERN = re.compile(
    r"\b(?:force[ _-]?push|history[ _-]?rewrite|production[ _-]?write|credential[ _-]?export|"
    r"project[ _-]?external[ _-]?delete)\b",
    re.I,
)
CODEX_REVIEW_SCHEMA = {
    "type": "object",
    "additionalProperties": False,
    "required": ["decision", "findings"],
    "properties": {
        "decision": {
            "type": "string",
            "enum": ["GO", "NO-GO"],
            "description": "GO only when findings is empty; otherwise NO-GO.",
        },
        "findings": {
            "type": "array",
            "description": "Every reportable review finding. Empty only for GO.",
            "items": {
                "type": "object",
                "additionalProperties": False,
                "required": ["severity", "file", "line", "detail"],
                "properties": {
                    "severity": {"type": "string", "enum": ["blocker", "high", "medium", "low"]},
                    "file": {"type": "string"},
                    "line": {"type": "integer", "minimum": 1},
                    "detail": {"type": "string"},
                },
            },
        },
    },
}


class RunnerError(RuntimeError):
    """Raised when an orchestration or release invariant fails."""


class LedgerSession:
    """Own one fenced writer lease and keep it alive during agent calls."""

    def __init__(self, ledger: TaskLedger, mission: str, baseline_head: str, risk: str) -> None:
        self.ledger = ledger
        self.task_id = "taskpack-" + hashlib.sha256(f"{mission}|{baseline_head}".encode("utf-8")).hexdigest()[:24]
        self.idempotency_key = hashlib.sha256(f"{self.task_id}|{risk}".encode("utf-8")).hexdigest()
        self.holder = f"runner:{os.getpid()}:{uuid.uuid4().hex[:12]}"
        self.fence: int | None = None
        self._stop = threading.Event()
        self._lock = threading.RLock()
        self._thread: threading.Thread | None = None
        self.heartbeat_error: Exception | None = None

    def start(self, baseline_tree: str) -> None:
        self.ledger.create(self.task_id, self.idempotency_key, time_budget_seconds=7200, tool_budget=1000)
        lease = self.ledger.acquire_lease(self.task_id, self.holder, ttl_seconds=120)
        self.fence = int(lease["fence"])
        self.ledger.transition(self.task_id, "PLANNING", holder=self.holder, fence=self.fence)
        self.ledger.checkpoint(self.task_id, {"phase": "baseline", "head": baseline_tree}, holder=self.holder, fence=self.fence)
        self.ledger.transition(self.task_id, "RUNNING", holder=self.holder, fence=self.fence)
        self._thread = threading.Thread(target=self._heartbeat_loop, name="task-ledger-heartbeat", daemon=True)
        self._thread.start()

    def _heartbeat_loop(self) -> None:
        while not self._stop.wait(30):
            with self._lock:
                if self.fence is None:
                    return
                try:
                    self.ledger.renew_lease(self.task_id, self.holder, self.fence, ttl_seconds=120)
                except Exception as exc:  # fail closed; the writer will observe this at phase boundary
                    self.heartbeat_error = exc
                    return

    def checkpoint(self, phase: str, **details: object) -> None:
        with self._lock:
            if self.fence is None:
                raise RunnerError("task ledger lease is not active")
            if self.heartbeat_error is not None:
                raise RunnerError(f"task ledger heartbeat failed: {self.heartbeat_error}")
            self.ledger.renew_lease(self.task_id, self.holder, self.fence, ttl_seconds=120)
            self.ledger.checkpoint(self.task_id, {"phase": phase, **details}, holder=self.holder, fence=self.fence)

    def complete(self) -> None:
        with self._lock:
            if self.fence is not None:
                task = self.ledger.get(self.task_id)
                if task["status"] not in {"COMPLETED", "FAILED", "CANCELLED", "BLOCKED"}:
                    self.ledger.transition(self.task_id, "COMPLETED", holder=self.holder, fence=self.fence)

    def fail(self, exc: Exception) -> None:
        with self._lock:
            if self.fence is None:
                return
            task = self.ledger.get(self.task_id)
            if task["status"] not in {"COMPLETED", "FAILED", "CANCELLED", "BLOCKED"}:
                self.ledger.record_error(self.task_id, type(exc).__name__, retryable=False, external_write=False, holder=self.holder, fence=self.fence)

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2)
        with self._lock:
            if self.fence is not None:
                try:
                    task = self.ledger.get(self.task_id)
                    if task.get("lease"):
                        self.ledger.release_lease(self.task_id, self.holder, self.fence)
                except Exception:
                    pass


def detect_task_risk(mission: str) -> str:
    """Detect TaskPack risk from the mission instead of trusting self-reporting."""

    normalized = mission.replace("\\", "/")
    normalized = re.sub(r"(^|[\s`'\"(])(?:\./)+", r"\1", normalized)
    if CRITICAL_OPERATION_PATTERN.search(normalized):
        return "high"
    if FORCED_HIGH_OPERATION_PATTERN.search(normalized) or any(
        pattern.search(normalized) for pattern in FORCED_HIGH_PATH_PATTERNS
    ):
        return "high"
    return "low"


def effective_task_risk(declared: str, mission: str) -> str:
    """Return max(user-declared risk, detected forced-high risk)."""

    if declared not in {"low", "high"}:
        raise ValueError("risk must be 'low' or 'high'")
    return "high" if declared == "high" or detect_task_risk(mission) == "high" else "low"


def project_runtime_environment(root: Path) -> dict[str, str]:
    """Return a project-owned environment for every child Agent process."""

    runtime = root.resolve() / ".hermes" / "task-runtime"
    paths = {
        "tmp": runtime / "tmp",
        "cache": runtime / "cache",
        "logs": runtime / "logs",
        "artifacts": runtime / "artifacts",
        "pip-cache": runtime / "pip-cache",
        "pycache": runtime / "pycache",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update({
        "TMP": str(paths["tmp"]),
        "TEMP": str(paths["tmp"]),
        "TMPDIR": str(paths["tmp"]),
        "XDG_CACHE_HOME": str(paths["cache"]),
        "PIP_CACHE_DIR": str(paths["pip-cache"]),
        "UV_CACHE_DIR": str(paths["cache"] / "uv"),
        "NPM_CONFIG_CACHE": str(paths["cache"] / "npm"),
        "npm_config_cache": str(paths["cache"] / "npm"),
        "YARN_CACHE_FOLDER": str(paths["cache"] / "yarn"),
        "PLAYWRIGHT_BROWSERS_PATH": str(paths["cache"] / "playwright-browsers"),
        "RUSTUP_HOME": str(paths["cache"] / "rustup"),
        "CARGO_HOME": str(paths["cache"] / "cargo"),
        "CARGO_TARGET_DIR": str(paths["cache"] / "cargo-target"),
        "RUFF_CACHE_DIR": str(paths["cache"] / "ruff"),
        "MYPY_CACHE_DIR": str(paths["cache"] / "mypy"),
        "PRE_COMMIT_HOME": str(paths["cache"] / "pre-commit"),
        "PYTHONPYCACHEPREFIX": str(paths["pycache"]),
        "HERMES_KANBAN_HOME": str(root.resolve() / ".hermes"),
        "HERMES_PROJECT_RUNTIME_ROOT": str(runtime),
        "HERMES_PROJECT_ROOT": str(root.resolve()),
        "HERMES_PROJECT_ARTIFACTS": str(paths["artifacts"]),
        "HERMES_PROJECT_LOGS": str(paths["logs"]),
    })
    return env


def _load_ci_profile(path: Path) -> dict[str, object]:
    value = yaml.safe_load(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise RunnerError(f"project profile is not a mapping: {path}")
    ci = value.get("ci")
    if not isinstance(ci, dict):
        raise RunnerError(f"project profile has no ci mapping: {path}")
    return ci


def discover_ci_identity(root: Path) -> tuple[tuple[str, ...], str | None]:
    """Discover a workflow name and aggregate job without assuming a product name.

    Prefers the workflow that carries the stable ``aggregate`` job (the main
    gate workflow); falls back to the first named workflow otherwise.
    """

    def _load(path: Path) -> dict | None:
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except (OSError, yaml.YAMLError):
            return None
        if not isinstance(data, dict) or not isinstance(data.get("name"), str):
            return None
        return data

    candidates = sorted((root / ".github" / "workflows").glob("*.y*ml"))
    # First pass: a workflow with the stable aggregate job wins (main gate).
    for path in candidates:
        workflow = _load(path)
        if not workflow:
            continue
        jobs = workflow.get("jobs")
        if isinstance(jobs, dict) and "aggregate" in jobs:
            return (workflow["name"],), "aggregate"
    # Second pass: any named workflow.
    for path in candidates:
        workflow = _load(path)
        if workflow:
            return (workflow["name"],), None
    return (), None


def resolve_ci_identity(
    root: Path,
    *,
    explicit_workflows: tuple[str, ...] = (),
    profile_path: Path | None = None,
) -> tuple[tuple[str, ...], str | None]:
    """Resolve CLI → project profile → repository workflow discovery."""

    profile = profile_path or (root / ".project/governance" / "work-lab.project-profile.yaml")
    profile_ci: dict[str, object] | None = None
    if profile.is_file():
        profile_ci = _load_ci_profile(profile)
    if explicit_workflows:
        aggregate = None
        if profile_ci:
            aggregate_value = profile_ci.get("stable_aggregate_job", profile_ci.get("stable_aggregate_check"))
            aggregate = str(aggregate_value) if aggregate_value else None
        return explicit_workflows, aggregate
    if profile_ci:
        workflow_name = profile_ci.get("workflow_name")
        if isinstance(workflow_name, str) and workflow_name:
            aggregate_value = profile_ci.get("stable_aggregate_job", profile_ci.get("stable_aggregate_check"))
            aggregate = str(aggregate_value) if aggregate_value else None
            return (workflow_name,), aggregate
    return discover_ci_identity(root)


@dataclass(frozen=True)
class AgentResult:
    stdout: str
    stderr: str
    session_id: str


class Repository(Protocol):
    def head(self) -> str: ...

    def head_tree(self) -> str: ...

    def staged_tree(self) -> str: ...

    def snapshot(self) -> tuple[str, str]: ...

    def verify_released(self, baseline_head: str, expected_tree: str | None = None, *, require_ci: bool = True) -> None: ...


class AgentBackend(Protocol):
    def run_writer(self, prompt: str, *, resume: str | None = None) -> AgentResult: ...

    def run_reviewer(self, prompt: str) -> str: ...


class ReviewerBackend(Protocol):
    def run_reviewer(self, prompt: str) -> str: ...


class GitRepository:
    def __init__(
        self,
        root: Path,
        *,
        remote_ref: str = "origin/main",
        required_workflows: tuple[str, ...] = (),
        stable_aggregate_job: str | None = None,
        ci_timeout_seconds: int = 1200,
        ci_poll_seconds: int = 6,
    ) -> None:
        self.root = root.resolve()
        self.env = project_runtime_environment(self.root)
        self.remote_ref = remote_ref
        self.required_workflows = required_workflows
        self.stable_aggregate_job = stable_aggregate_job
        self.ci_timeout_seconds = ci_timeout_seconds
        self.ci_poll_seconds = ci_poll_seconds

    def _git(self, *args: str) -> str:
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=False,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
        )
        if result.returncode:
            raise RunnerError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
        return result.stdout.rstrip("\r\n")

    def head(self) -> str:
        return self._git("rev-parse", "HEAD")

    def head_tree(self) -> str:
        return self._git("rev-parse", "HEAD^{tree}")

    def staged_tree(self) -> str:
        return self._git("write-tree")

    def snapshot(self) -> tuple[str, str]:
        return self.staged_tree(), self._git("status", "--porcelain=v1", "--untracked-files=all")

    def _remote_name(self) -> str:
        remote, separator, branch = self.remote_ref.partition("/")
        if not separator or not remote or not branch:
            raise RunnerError(
                "remote_ref must be in '<remote>/<branch>' form; "
                f"received {self.remote_ref!r}"
            )
        return remote

    def _github_repository(self) -> str:
        """Return ``owner/repository`` for the release remote, fail closed otherwise."""
        remote_url = self._git("remote", "get-url", self._remote_name()).strip()
        match = re.search(r"github\.com[:/]([^/\s]+)/([^/\s]+?)(?:\.git)?/?$", remote_url, re.I)
        if not match:
            raise RunnerError(
                "remote_ref must point at a GitHub owner/repository for exact-SHA CI; "
                f"received remote URL {remote_url!r}"
            )
        return f"{match.group(1)}/{match.group(2)}"

    def verify_released(self, baseline_head: str, expected_tree: str | None = None, *, require_ci: bool = True) -> None:
        tree, status = self.snapshot()
        del tree
        if status:
            raise RunnerError(f"writer returned with a dirty worktree:\n{status}")
        head = self.head()
        if head == baseline_head:
            raise RunnerError("writer did not create a release commit")
        if expected_tree is not None:
            actual_tree = self.head_tree()
            if actual_tree != expected_tree:
                raise RunnerError(
                    "release commit tree differs from the exact tree approved by reviewer: "
                    f"expected={expected_tree} actual={actual_tree}"
                )
        self.verify_remote_sync(head)
        if require_ci:
            self.observe_ci(head)
        else:
            print(
                "LOW_RISK_PUBLISH_NO_CI head=" + head +
                " (TARGETED/STAGE publish verifies remote sync only; exact-SHA CI is "
                "required only for RC/RELEASE or high-risk delivery)"
            )

    def verify_remote_sync(self, head: str) -> None:
        self._git("fetch", "--prune", self._remote_name())
        remote_head = self._git("rev-parse", self.remote_ref)
        if head != remote_head:
            raise RunnerError(f"release is not synchronized: HEAD={head} {self.remote_ref}={remote_head}")

    def observe_ci(self, head: str) -> None:
        if not self.required_workflows:
            raise RunnerError(
                "CI observation is BLOCKED: no required exact-SHA workflows are configured; "
                "absence of configuration must not be treated as CI success"
            )
        self._wait_for_ci(head)

    def _aggregate_status(self, repository: str, run: dict[str, object], head: str) -> str:
        """Read the stable aggregate job for the already-selected exact-SHA run."""

        if not self.stable_aggregate_job:
            return "success"
        run_id = run.get("databaseId")
        if run_id is None:
            return "missing"
        result = subprocess.run(
            ["gh", "run", "view", str(run_id), "--repo", repository, "--json", "headSha,jobs"],
            cwd=self.root,
            check=False,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            env=self.env,
        )
        if result.returncode:
            raise RunnerError(f"gh run view failed: {result.stderr.strip()}")
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RunnerError("gh run view returned invalid JSON") from exc
        if payload.get("headSha") != head:
            raise RunnerError("aggregate evidence head SHA does not match selected exact-SHA run")
        jobs = payload.get("jobs", [])
        if not isinstance(jobs, list):
            raise RunnerError("gh run view returned invalid jobs")
        matches = [job for job in jobs if isinstance(job, dict) and job.get("name") == self.stable_aggregate_job]
        if not matches:
            return "missing"
        job = matches[0]
        if job.get("status") != "completed":
            return "pending"
        return "success" if job.get("conclusion") == "success" else "failed"

    def _wait_for_ci(self, head: str) -> None:
        if not shutil.which("gh"):
            raise RunnerError("gh executable not found; cannot verify exact-SHA CI")
        repository = self._github_repository()
        deadline = time.monotonic() + self.ci_timeout_seconds
        while time.monotonic() < deadline:
            result = subprocess.run(
                [
                    "gh",
                    "run",
                    "list",
                    "--repo",
                    repository,
                    "--commit",
                    head,
                    "--limit",
                    "20",
                    "--json",
                    "status,conclusion,workflowName,name,url,databaseId,headSha,attempt,createdAt",
                ],
                cwd=self.root,
                check=False,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                env=self.env,
            )
            if result.returncode:
                raise RunnerError(f"gh run list failed: {result.stderr.strip()}")
            try:
                runs = json.loads(result.stdout)
            except json.JSONDecodeError as exc:
                raise RunnerError("gh run list returned invalid JSON") from exc
            if not isinstance(runs, list):
                raise RunnerError("gh run list returned a non-list response")

            required_runs: dict[str, list[dict[str, object]]] = {}
            for workflow in self.required_workflows:
                exact = [
                    run for run in runs
                    if (run.get("workflowName") or run.get("name")) == workflow
                    and run.get("headSha") == head
                ]
                if exact:
                    exact.sort(
                        key=lambda run: (
                            int(run.get("runAttempt") or run.get("attempt") or 0),
                            str(run.get("createdAt") or ""),
                        ),
                        reverse=True,
                    )
                    required_runs[workflow] = [exact[0]]
                else:
                    required_runs[workflow] = []
            missing = [workflow for workflow, workflow_runs in required_runs.items() if not workflow_runs]
            pending = [
                workflow
                for workflow, workflow_runs in required_runs.items()
                if workflow_runs and any(run.get("status") != "completed" for run in workflow_runs)
            ]
            failed = [
                run
                for workflow_runs in required_runs.values()
                for run in workflow_runs
                if run.get("status") == "completed" and run.get("conclusion") != "success"
            ]
            if failed:
                raise RunnerError(f"required exact-SHA CI failed: {json.dumps(failed, ensure_ascii=False)}")
            if missing and runs and all(run.get("status") == "completed" for run in runs):
                raise RunnerError(
                    "required workflow missing for exact-SHA CI: " + ", ".join(sorted(missing))
                )
            if not missing and not pending:
                aggregate_pending = False
                for workflow_runs in required_runs.values():
                    for run in workflow_runs:
                        aggregate_status = self._aggregate_status(repository, run, head)
                        if aggregate_status == "failed":
                            raise RunnerError(
                                f"stable aggregate job failed: {self.stable_aggregate_job}"
                            )
                        if aggregate_status == "pending":
                            aggregate_pending = True
                        if aggregate_status == "missing":
                            raise RunnerError(
                                "stable aggregate job missing for exact-SHA CI: "
                                f"{self.stable_aggregate_job}"
                            )
                if aggregate_pending:
                    time.sleep(self.ci_poll_seconds)
                    continue
                incomplete = [
                    workflow
                    for workflow, workflow_runs in required_runs.items()
                    for run in workflow_runs
                    if run.get("databaseId") is None
                    or (run.get("runAttempt") is None and run.get("attempt") is None)
                    or not run.get("url")
                    or run.get("headSha") != head
                ]
                if incomplete:
                    raise RunnerError(
                        "required exact-SHA CI evidence incomplete: " + ", ".join(sorted(incomplete))
                    )
                evidence = [
                    f"{workflow}:workflowName={run.get('workflowName') or run.get('name')}"
                    f" run={run.get('databaseId')}"
                    f" runAttempt={run.get('runAttempt') or run.get('attempt')}"
                    f" url={run.get('url')} headSha={run.get('headSha')}"
                    for workflow, workflow_runs in required_runs.items()
                    for run in workflow_runs
                ]
                aggregate_evidence = (
                    f" aggregate_job={self.stable_aggregate_job}"
                    if self.stable_aggregate_job
                    else ""
                )
                print("EXACT_SHA_CI_PASS " + " | ".join(evidence) + aggregate_evidence)
                return
            time.sleep(self.ci_poll_seconds)
        raise RunnerError(f"timed out waiting for exact-SHA CI for {head}")


class HermesAgentBackend:
    def __init__(
        self,
        root: Path,
        *,
        hermes: str = "hermes",
        skills: str = DEFAULT_SKILLS,
    ) -> None:
        executable = shutil.which(hermes)
        if not executable:
            raise RunnerError(f"Hermes executable not found: {hermes}")
        self.root = root.resolve()
        self.hermes = executable
        self.skills = skills
        self.env = project_runtime_environment(self.root)

    def _run(self, command: list[str]) -> subprocess.CompletedProcess[str]:
        result = subprocess.run(
            command,
            cwd=self.root,
            check=False,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            env=self.env,
        )
        if result.stdout:
            print(result.stdout, end="" if result.stdout.endswith("\n") else "\n", flush=True)
        if result.returncode:
            raise RunnerError(
                f"Hermes exited {result.returncode}: {result.stderr.strip() or result.stdout.strip()}"
            )
        return result

    def run_writer(self, prompt: str, *, resume: str | None = None) -> AgentResult:
        command = [
            self.hermes,
            "chat",
            "-Q",
            "--pass-session-id",
            "-t",
            "terminal,file",
            "-s",
            self.skills,
        ]
        if resume:
            command.extend(["--resume", resume])
        command.extend(["-q", prompt])
        result = self._run(command)
        match = SESSION_PATTERN.search(result.stderr)
        if not match:
            raise RunnerError(f"Hermes did not emit a parseable session_id: {result.stderr.strip()}")
        return AgentResult(result.stdout, result.stderr, match.group(1))

    def run_reviewer(self, prompt: str) -> str:
        result = self._run([self.hermes, "-t", "safe", "-z", prompt])
        return result.stdout.strip()


def resolve_codex_executable(configured: str | None = None) -> str:
    """Locate an installed Codex CLI without reading its configuration or auth."""

    candidates: list[Path] = []
    if configured:
        candidates.append(Path(configured).expanduser())
    if os.environ.get("CODEX_CLI"):
        candidates.append(Path(os.environ["CODEX_CLI"]).expanduser())
    candidates.extend(
        [
            Path.home() / "AppData/Local/OpenAI/Codex/bin/codex.exe",
            Path.home() / ".codex/plugins/.plugin-appserver/codex.exe",
        ]
    )
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    for name in ("codex.exe", "codex"):
        resolved = shutil.which(name)
        if resolved:
            return resolved
    raise RunnerError(
        "Codex executable not found; install/login Codex first or pass --codex with its executable path"
    )


def discover_codex_exec_flags(codex: str, *, env: dict[str, str]) -> set[str]:
    """Discover the installed CLI's exec flags instead of assuming a version contract."""

    result = subprocess.run(
        [codex, "exec", "--help"],
        cwd=env.get("HERMES_PROJECT_ROOT"),
        check=False,
        text=True, encoding="utf-8", errors="replace",
        capture_output=True,
        timeout=60,
        env=env,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RunnerError(f"Codex capability discovery failed: {detail}")
    return set(re.findall(r"--([a-z0-9-]+)\b", result.stdout))


def discover_codex_version(codex: str, *, env: dict[str, str]) -> str:
    """Record the installed runtime version as run evidence, never as a compatibility pin."""

    result = subprocess.run(
        [codex, "--version"],
        cwd=env.get("HERMES_PROJECT_ROOT"),
        check=False,
        text=True, encoding="utf-8", errors="replace",
        capture_output=True,
        timeout=60,
        env=env,
    )
    if result.returncode:
        detail = (result.stderr or result.stdout).strip()
        raise RunnerError(f"Codex version discovery failed: {detail}")
    version = (result.stdout or result.stderr).strip()
    if not version:
        raise RunnerError("Codex version discovery returned no version")
    return version


class CodexReviewBackend:
    """Run Codex as a read-only, prompt-aware independent TaskPack reviewer.

    The caller snapshots Git before and after this command. Codex's specialised
    ``exec review --uncommitted`` accepts neither TaskPack's exact-tree prompt
    nor a reliable final-message artifact on the verified CLI. Use generic
    ``exec`` instead: it accepts the exact staged-tree prompt, runs under an
    explicit read-only sandbox and emits a temporary JSON verdict. A validated
    GO is returned directly; every finding is fail-closed as NO-GO.
    """

    def __init__(
        self,
        root: Path,
        *, codex: str | None = None,
    ) -> None:
        self.root = root.resolve()
        self.codex = resolve_codex_executable(codex)
        self.env = project_runtime_environment(self.root)

    def run_reviewer(self, prompt: str) -> str:
        runtime = self.root / ".hermes" / "task-runtime"
        runtime.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".txt", prefix="codex-review-", dir=runtime, delete=False
        ) as handle:
            final_message = Path(handle.name)
        with tempfile.NamedTemporaryFile(
            mode="w", encoding="utf-8", suffix=".json", prefix="codex-review-schema-", dir=runtime, delete=False
        ) as handle:
            output_schema = Path(handle.name)
        output_schema.write_text(json.dumps(CODEX_REVIEW_SCHEMA), encoding="utf-8")
        try:
            discover_codex_version(self.codex, env=self.env)
            available_flags = discover_codex_exec_flags(self.codex, env=self.env)
            required_flags = {"sandbox", "ephemeral", "output-last-message", "output-schema"}
            missing_flags = sorted(required_flags - available_flags)
            if missing_flags:
                raise RunnerError(
                    "Codex exec capability discovery is missing required flags: " + ", ".join(missing_flags)
                )
            result = subprocess.run(
                [
                    self.codex,
                    "exec",
                    "--sandbox",
                    "read-only",
                    "--ephemeral",
                    "--output-last-message",
                    str(final_message),
                    "--output-schema",
                    str(output_schema),
                    prompt,
                ],
                cwd=self.root,
                check=False,
                text=True, encoding="utf-8", errors="replace",
                capture_output=True,
                timeout=600,
                env=self.env,
            )
            if result.returncode:
                detail = (result.stderr or result.stdout).strip()
                raise RunnerError(f"Codex review exited {result.returncode}: {detail}")
            review = final_message.read_text(encoding="utf-8").strip()
            if not review:
                raise RunnerError("Codex review produced no final output")
        finally:
            final_message.unlink(missing_ok=True)
            output_schema.unlink(missing_ok=True)
        try:
            payload = json.loads(review)
        except json.JSONDecodeError as exc:
            raise RunnerError("Codex review final output did not match the required JSON schema") from exc
        if not isinstance(payload, dict) or set(payload) != {"decision", "findings"}:
            raise RunnerError("Codex review final output did not match the required JSON schema")
        decision = payload.get("decision")
        findings = payload.get("findings")
        if decision not in {"GO", "NO-GO"} or not isinstance(findings, list):
            raise RunnerError("Codex review final output did not match the required JSON schema")
        if decision == "GO" and findings:
            raise RunnerError("Codex review returned GO with findings")
        if decision == "NO-GO":
            return "NO-GO\nCodex native pre-review:\n" + json.dumps(payload, ensure_ascii=False)
        return "GO\nCodex structured exact-tree review found no findings"


class TaskPackRunner:
    def __init__(
        self,
        *,
        repo: Repository,
        agent: AgentBackend,
        reviewer: ReviewerBackend | None = None,
        max_review_rounds: int = 3,
        release_ref: str = "origin/main",
        publish: bool = False,
        ledger: TaskLedger | None = None,
    ) -> None:
        if max_review_rounds < 1:
            raise ValueError("max_review_rounds must be positive")
        self.repo = repo
        self.agent = agent
        self.reviewer = reviewer or agent
        self.max_review_rounds = max_review_rounds
        self.release_ref = release_ref
        self.publish = publish
        self.ledger = ledger
        self.last_task_id: str | None = None

    def run(self, mission: str, *, risk: str) -> None:
        if self.ledger is None:
            return self._run_core(mission, risk=risk)
        baseline_head = self.repo.head()
        _, baseline_status = self.repo.snapshot()
        if baseline_status:
            raise RunnerError(f"TaskPack must start from a clean worktree:\n{baseline_status}")
        session = LedgerSession(self.ledger, mission, baseline_head, risk)
        self.last_task_id = session.task_id
        try:
            session.start(self.repo.head_tree())
            result = self._run_core(mission, risk=risk)
            session.checkpoint("runner_complete", head=self.repo.head())
            session.complete()
            return result
        except Exception as exc:
            session.fail(exc)
            raise
        finally:
            session.close()

    def _run_core(self, mission: str, *, risk: str) -> None:
        if risk not in {"low", "high"}:
            raise ValueError("risk must be 'low' or 'high'")
        risk = effective_task_risk(risk, mission)
        baseline_head = self.repo.head()
        baseline_tree = self.repo.head_tree()
        _, baseline_status = self.repo.snapshot()
        if baseline_status:
            raise RunnerError(f"TaskPack must start from a clean worktree:\n{baseline_status}")

        if risk == "low":
            prompt = (
                self._low_risk_publish_prompt(mission, self.release_ref)
                if self.publish
                else self._low_risk_stage_prompt(mission)
            )
            result = self.agent.run_writer(prompt)
            if not result.session_id:
                raise RunnerError("writer session ID is empty")
            if self.publish:
                # Low-risk (TARGETED/STAGE) publish: verify remote sync only.
                # exact-SHA CI is reserved for RC/RELEASE and high-risk delivery (WLG-040).
                self.repo.verify_released(baseline_head, require_ci=False)
            else:
                self._assert_frozen(baseline_head, baseline_tree)
            return

        result = self.agent.run_writer(self._freeze_prompt(mission))
        session_id = result.session_id
        self._assert_frozen(baseline_head, baseline_tree)

        for review_round in range(1, self.max_review_rounds + 2):
            frozen_tree, frozen_status = self.repo.snapshot()
            review = self.reviewer.run_reviewer(
                self._review_prompt(mission, frozen_tree, review_round)
            )
            if self.repo.snapshot() != (frozen_tree, frozen_status):
                raise RunnerError("reviewer changed the frozen tree or worktree status")
            decision = self._review_decision(review)
            if decision == "GO":
                if not self.publish:
                    return
                result = self.agent.run_writer(
                    self._release_prompt(mission, frozen_tree, review, self.release_ref), resume=session_id
                )
                session_id = result.session_id
                del session_id
                self.repo.verify_released(baseline_head, frozen_tree)
                return

            if review_round > self.max_review_rounds:
                raise RunnerError(
                    "review did not reach GO after "
                    f"{self.max_review_rounds} repair rounds"
                )

            previous_tree = frozen_tree
            result = self.agent.run_writer(
                self._repair_prompt(mission, frozen_tree, review), resume=session_id
            )
            session_id = result.session_id
            self._assert_frozen(baseline_head, baseline_tree)
            if self.repo.staged_tree() == previous_tree:
                raise RunnerError("writer returned the same frozen tree after NO-GO findings")

        raise RunnerError(f"review did not reach GO in {self.max_review_rounds} rounds")

    def _assert_frozen(self, baseline_head: str, baseline_tree: str) -> None:
        if self.repo.head() != baseline_head:
            raise RunnerError("high-risk writer committed before reviewer GO")
        staged_tree, status = self.repo.snapshot()
        if not status or staged_tree == baseline_tree:
            raise RunnerError("writer did not produce a staged frozen tree for review")
        invalid = [
            line
            for line in status.splitlines()
            if len(line) < 3 or line[:2] == "??" or line[0] == " " or line[1] != " "
        ]
        if invalid:
            raise RunnerError(
                "frozen review state must be fully staged with no untracked, unstaged, "
                f"or conflicted files: {invalid}"
            )

    @staticmethod
    def _review_decision(review: str) -> str:
        first_line = next((line.strip() for line in review.splitlines() if line.strip()), "")
        if first_line == "GO":
            return "GO"
        if first_line == "NO-GO":
            return "NO-GO"
        raise RunnerError("reviewer output must start with GO or NO-GO on its own line")

    @staticmethod
    def _freeze_prompt(mission: str) -> str:
        return f"""Execute exactly one HIGH-RISK TaskPack in this repository.

MISSION:
{mission}

Use RED -> GREEN and affected checks while developing. Keep one writer session. Do not
spawn background reviewers. Do not commit or push. When implementation and the one
required full local gate are complete, stage only the intended files, verify staged diff,
secret scan and conventions, then stop with a frozen tree ready for exact-tree review.
Your final response must report READY_FOR_REVIEW plus git write-tree and test evidence.
"""

    @staticmethod
    def _low_risk_stage_prompt(mission: str) -> str:
        return f"""Execute exactly one LOW-RISK TaskPack in this repository.

MISSION:
{mission}

Use RED -> GREEN and affected checks during development, then stage only the intended
files and stop. Do not commit, push, create a PR, or start CI. Your final response must
report READY_FOR_RELEASE plus git write-tree and test evidence for an explicit publisher.
"""

    @staticmethod
    def _low_risk_publish_prompt(mission: str, release_ref: str) -> str:
        return f"""Execute exactly one LOW-RISK TaskPack end to end in this repository.

MISSION:
{mission}

Use RED -> GREEN, affected checks during development, and one full gate after freezing the
diff. Do not spawn background reviewers. Stage only intended files, commit, fetch/prune,
refuse remote divergence, push, wait for the exact commit's CI, and leave a clean worktree
with HEAD equal to {release_ref}. Do not return a plan; finish or report a real blocker.
"""

    @staticmethod
    def _review_prompt(mission: str, tree: str, review_round: int) -> str:
        return f"""Read-only independent review. Never edit, stage, commit, or write files.
Review exact staged tree {tree} for Blocker/High findings only. Confirm git write-tree is
still {tree} before concluding. Check correctness, data loss, security, rollback and test
proof relevant to the mission below.

MISSION:
{mission}

REVIEW ROUND: {review_round}
Output GO on the first non-empty line if there are no Blocker/High findings. Otherwise
output NO-GO on the first non-empty line followed by exact file:line findings.
"""

    @staticmethod
    def _repair_prompt(mission: str, tree: str, review: str) -> str:
        return f"""Continue the SAME TaskPack and writer lineage after an exact-tree NO-GO.
The reviewed tree was {tree}. Fix every finding below at its root, add RED/GREEN proof,
rerun affected checks and the full gate only after refreezing, stage only intended files,
and stop without committing or pushing.

MISSION:
{mission}

REVIEW FINDINGS:
{review}
"""

    @staticmethod
    def _release_prompt(mission: str, tree: str, review: str, release_ref: str) -> str:
        return f"""Continue the SAME TaskPack after reviewer GO for exact tree {tree}.
First verify git write-tree is still exactly {tree}; do not alter reviewed production
content. Commit the frozen tree, fetch/prune, refuse remote divergence, push, wait for the
exact commit's CI, and leave a clean worktree with HEAD equal to {release_ref}. Report real
SHA, CI run URL and evidence.

MISSION:
{mission}

REVIEW RESULT:
{review}
"""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mission = parser.add_mutually_exclusive_group(required=True)
    mission.add_argument("--mission", help="Inline TaskPack mission")
    mission.add_argument("--mission-file", type=Path, help="UTF-8 mission file")
    parser.add_argument("--risk", choices=("low", "high"), required=True)
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    parser.add_argument(
        "--remote-ref",
        required=True,
        help="Exact remote ref for this TaskPack; pass the active branch explicitly.",
    )
    parser.add_argument("--max-review-rounds", type=int, default=3)
    parser.add_argument(
        "--required-workflow",
        action="append",
        default=[],
        help=(
            "Repeatable exact-SHA GitHub workflow name required before release; "
            "overrides project profile and repository discovery."
        ),
    )
    parser.add_argument(
        "--project-profile",
        type=Path,
        help="Optional project profile; defaults to .project/governance/work-lab.project-profile.yaml.",
    )
    parser.add_argument(
        "--publish",
        action="store_true",
        help="Explicitly allow commit, push and exact-SHA CI after the TaskPack is ready.",
    )
    parser.add_argument("--skills", default=DEFAULT_SKILLS)
    parser.add_argument("--hermes", default="hermes")
    parser.add_argument(
        "--reviewer",
        choices=("hermes", "codex"),
        default="hermes",
        help="Exact-tree reviewer backend; Codex uses native exec review in ephemeral mode.",
    )
    parser.add_argument(
        "--codex",
        help="Optional Codex executable path when --reviewer codex is selected.",
    )
    args = parser.parse_args()
    if args.reviewer == "codex" and args.risk != "high":
        parser.error("--reviewer codex is only valid with --risk high")
    return args


def main() -> int:
    args = _parse_args()
    mission = (
        args.mission_file.read_text(encoding="utf-8")
        if args.mission_file is not None
        else args.mission
    )
    required_workflows, aggregate_job = resolve_ci_identity(
        args.repo.resolve(),
        explicit_workflows=tuple(args.required_workflow),
        profile_path=args.project_profile,
    )
    repo = GitRepository(
        args.repo,
        remote_ref=args.remote_ref,
        required_workflows=required_workflows,
        stable_aggregate_job=aggregate_job,
    )
    agent = HermesAgentBackend(args.repo, hermes=args.hermes, skills=args.skills)
    reviewer: ReviewerBackend | None = None
    if args.reviewer == "codex":
        reviewer = CodexReviewBackend(args.repo, codex=args.codex)
    ledger = TaskLedger(args.repo.resolve() / ".hermes" / "task-runtime" / "task-ledger")
    TaskPackRunner(
        repo=repo,
        agent=agent,
        reviewer=reviewer,
        max_review_rounds=args.max_review_rounds,
        release_ref=args.remote_ref,
        publish=args.publish,
        ledger=ledger,
    ).run(mission, risk=args.risk)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
