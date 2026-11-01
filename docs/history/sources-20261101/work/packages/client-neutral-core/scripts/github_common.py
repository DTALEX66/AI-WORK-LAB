"""Shared, fail-closed helpers for the optional GitHub delivery tools."""
from __future__ import annotations

import json
import os
import re
import subprocess
import urllib.error
import urllib.request
from pathlib import Path

API = "https://api.github.com"
ROOT = Path(__file__).resolve().parents[3]
REGISTRY = ROOT / ".project/governance/federation/federation-registry.v1.json"


def redact(value: str) -> str:
    value = re.sub(r"(https?://)[^/@\s]+@", r"\1[REDACTED]@", value)
    value = re.sub(r"(?i)(authorization\s*[:=]\s*)[^\r\n]+", r"\1[REDACTED]", value)
    value = re.sub(r"(?i)(authorization|password|token|secret)(\s*[:=]\s*)[^\s,;]+", r"\1\2[REDACTED]", value)
    value = re.sub(r"\b(?:gh[pousr]_[A-Za-z0-9_]+|github_pat_[A-Za-z0-9_]+)\b", "[REDACTED]", value)
    return value


def managed_repos() -> list[dict]:
    data = json.loads(REGISTRY.read_text(encoding="utf-8"))
    return [{"local": p["displayName"], "repo": p["repository"]} for p in data["projects"]]


MANAGED_REPOS = managed_repos()


def git(repo_dir: Path, *args: str) -> str:
    child_env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    try:
        result = subprocess.run(["git", "-C", str(repo_dir), *args], capture_output=True,
                                text=True, encoding="utf-8", errors="replace", timeout=60, env=child_env)
    except subprocess.TimeoutExpired:
        raise RuntimeError(f"git {args[0]} timed out") from None
    except OSError:
        raise RuntimeError(f"git {args[0]} could not start") from None
    if result.returncode:
        raise RuntimeError(redact(f"git {args[0]} failed (exit {result.returncode}): {result.stderr.strip()}"))
    return result.stdout.strip()


def local_path(entry: dict) -> Path:
    known = {p["local"]: p["repo"] for p in MANAGED_REPOS}
    name = entry["local"]
    if name not in known:
        raise ValueError("repository is not in the project registry")
    if name != ROOT.name and not entry.get("root"):
        raise ValueError("external repository requires an explicit --repo-root")
    candidate = Path(entry["root"]) if entry.get("root") else ROOT
    root = Path(git(candidate, "rev-parse", "--show-toplevel")).resolve()
    if root != candidate.resolve():
        raise ValueError("candidate path is not the expected Git root")
    remotes = (git(root, "remote", "get-url", "origin"),
               git(root, "remote", "get-url", "--push", "origin"))
    expected = known[name].lower()
    pattern = r"(?:git@github\.com:|https://github\.com/)" + re.escape(expected) + r"(?:\.git)?"
    if any(not re.fullmatch(pattern, remote.lower()) for remote in remotes):
        raise ValueError("origin does not match registered repository identity")
    return root


def credential() -> str:
    child_env = dict(os.environ, GIT_TERMINAL_PROMPT="0", GCM_INTERACTIVE="Never")
    try:
        result = subprocess.run(["git", "credential", "fill"],
                                input="protocol=https\nhost=github.com\n\n", text=True, encoding="utf-8", errors="replace",
                                capture_output=True, timeout=20, env=child_env)
    except (subprocess.TimeoutExpired, OSError):
        raise RuntimeError("Git credential lookup unavailable") from None
    if result.returncode:
        raise RuntimeError("Git credential lookup failed")
    fields = dict(line.split("=", 1) for line in result.stdout.splitlines() if "=" in line)
    if not fields.get("password"):
        raise RuntimeError("Git credential lookup returned no password")
    return fields["password"]


def request(method: str, path: str, payload: dict | None = None,
            repo: str = "DTALEX66/WORK-LAB") -> dict:
    if repo not in {p["repo"] for p in MANAGED_REPOS} or not path.startswith("/"):
        raise ValueError("unregistered repository or invalid API path")
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28"}
    if method != "GET":
        headers["Authorization"] = f"Bearer {credential()}"
    req = urllib.request.Request(f"{API}/repos/{repo}{path}", data=data, method=method,
                                 headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            raw = resp.read().decode("utf-8")
            return json.loads(raw) if raw else {}
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub API {method} failed (HTTP {exc.code})") from None
    except urllib.error.URLError:
        raise RuntimeError(f"GitHub API {method} network failure") from None
