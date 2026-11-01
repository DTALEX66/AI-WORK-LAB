#!/usr/bin/env python3
"""Redacted Hermes + CC Switch + Codex workflow diagnosis.

Default mode checks structure and reachability only. ``--live`` additionally
runs real provider and Codex execution smokes; only live markers prove execution.
"""
from __future__ import annotations

import argparse
import csv
import io
import ipaddress
import os
import re
import shutil
import socket
import subprocess
import sys
import tempfile
from pathlib import Path
from urllib.parse import urlsplit


def configure_console_output() -> None:
    """Keep a diagnostic report running on legacy Windows code pages."""

    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(errors="backslashreplace")


SECRET_PATTERNS = [
    (re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]{16,}", re.I), "Bearer [REDACTED]"),
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), "jwt-[REDACTED]"),
    (re.compile(r"github_pat_[A-Za-z0-9_]{20,}"), "github_pat_[REDACTED]"),
    (re.compile(r"gh[pousr]_[A-Za-z0-9_]{20,}"), "gh_[REDACTED]"),
    (re.compile(r"npm_[A-Za-z0-9]{20,}"), "npm_[REDACTED]"),
    (re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"), "xox-[REDACTED]"),
    (re.compile(r"sk-[A-Za-z0-9_-]{8,}"), "sk-[REDACTED]"),
    (
        re.compile(
            r"(?i)([\"'])(access[_-]?token|refresh[_-]?token|id[_-]?token|bearer[_-]?token|api[_-]?key|secret|password)\1(\s*[:=]\s*)([\"'])[^\"']+\4"
        ),
        r"\1\2\1\3\4[REDACTED]\4",
    ),
    (
        re.compile(
            r"(?i)(access[_-]?token|refresh[_-]?token|id[_-]?token|bearer[_-]?token|api[_-]?key|secret|password)\s*[:=]\s*[\"']?[^\s,}\]\"']+"
        ),
        r"\1=[REDACTED]",
    ),
]


def redact(text: str) -> str:
    for pattern, replacement in SECRET_PATTERNS:
        text = pattern.sub(replacement, text)
    return text


_MANAGED_LAUNCH_POLICY: list = []


def _managed_launch_policy():
    """Load the A-3 launch policy once, by path, so it resolves in any context."""

    if not _MANAGED_LAUNCH_POLICY:
        import importlib.util

        path = Path(__file__).resolve().parent / "managed_launch_policy.py"
        spec = importlib.util.spec_from_file_location("managed_launch_policy", path)
        if spec is None or spec.loader is None:  # pragma: no cover - environment guard
            raise SystemExit(f"cannot load managed_launch_policy: {path}")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MANAGED_LAUNCH_POLICY.append(module)
    return _MANAGED_LAUNCH_POLICY[0]


def run(command: list[str], *, timeout: int = 30, cwd: Path | None = None) -> tuple[int, str]:
    # A-3: managed launches are policy-checked before the process is created, so
    # an unapproved route (e.g. --ignore-user-config reaching a built-in default
    # provider) cannot be taken by any doctor probe.
    _managed_launch_policy().assert_managed_argv(command, what="hermes_workflow_doctor")
    try:
        completed = subprocess.run(
            command,
            cwd=cwd,
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            timeout=timeout,
        )
        return completed.returncode, redact((completed.stdout or "").strip())
    except Exception as exc:
        return 124, f"{type(exc).__name__}: {exc}"


def print_command(label: str, command: list[str], *, timeout: int = 30, max_lines: int = 20) -> tuple[int, str]:
    code, output = run(command, timeout=timeout)
    status = "OK" if code == 0 else f"WARN exit={code}"
    print(f"[{status}] {label}")
    lines = output.splitlines()
    for line in lines[:max_lines]:
        print("  " + line)
    if len(lines) > max_lines:
        print(f"  ... ({len(lines) - max_lines} more lines)")
    return code, output


def required_command(label: str, command: list[str], *, timeout: int = 30) -> bool:
    """Run a structural command whose non-zero exit must fail the doctor."""

    code, _ = print_command(label, command, timeout=timeout)
    return code == 0


def has_exact_marker(output: str, marker: str) -> bool:
    """Accept only a standalone response line, never a marker embedded in an echoed prompt."""

    return any(line.strip() == marker for line in output.splitlines())


def marker_smoke(label: str, command: list[str], marker: str, *, timeout: int = 120, cwd: Path | None = None) -> bool:
    code, output = run(command, timeout=timeout, cwd=cwd)
    passed = code == 0 and has_exact_marker(output, marker)
    print(f"[{'OK' if passed else 'FAIL'}] {label}: marker={marker!r}, exit={code}")
    if not passed and output:
        for line in output.splitlines()[-8:]:
            print("  " + line)
    return passed


def port_open(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=1.0):
            return True
    except OSError:
        return False


def proxy_environment_summary(name: str) -> str:
    """Classify a proxy variable without printing its endpoint or credentials."""

    value = os.environ.get(name)
    if not value:
        return f"{name}=unset"
    if name == "NO_PROXY":
        return "NO_PROXY=set entries=redacted"
    try:
        parsed = urlsplit(value)
        scheme = parsed.scheme.lower()
        host = (parsed.hostname or "").lower()
        credentials = "present-redacted" if parsed.username or parsed.password else "none"
    except ValueError:
        return f"{name}=set scheme=invalid local_loopback=unknown credentials=redacted"
    if scheme not in {"http", "https", "socks4", "socks5", "socks5h"} or not host:
        return f"{name}=set scheme=invalid local_loopback=unknown credentials=redacted"
    try:
        loopback = host == "localhost" or ipaddress.ip_address(host).is_loopback
    except ValueError:
        loopback = False
    return (
        f"{name}=set scheme={scheme} local_loopback={'yes' if loopback else 'no'} "
        f"credentials={credentials}"
    )


def windows_listener_owner(port: int) -> str | None:
    """Return a local listener image/PID on Windows without reading app config."""

    if os.name != "nt":
        return None
    try:
        netstat = subprocess.run(
            ["netstat", "-ano", "-p", "tcp"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
    except OSError:
        return None
    pid: str | None = None
    for line in netstat.stdout.splitlines():
        columns = line.split()
        if len(columns) >= 5 and columns[1].endswith(f":{port}") and columns[3] == "LISTENING":
            pid = columns[-1]
            break
    if not pid:
        return None
    try:
        tasklist = subprocess.run(
            ["tasklist", "/FI", f"PID eq {pid}", "/FO", "CSV", "/NH"],
            text=True,
            encoding="utf-8",
            errors="replace",
            stdout=subprocess.PIPE,
            stderr=subprocess.DEVNULL,
            timeout=8,
        )
        rows = list(csv.reader(io.StringIO(tasklist.stdout)))
        image = rows[0][0] if rows and rows[0] and rows[0][0] != "INFO: No tasks are running" else "unknown"
    except OSError:
        image = "unknown"
    return f"pid={pid} image={image}"


def hermes_home() -> Path:
    if os.environ.get("HERMES_HOME"):
        return Path(os.environ["HERMES_HOME"])
    if os.name == "nt":
        root = os.environ.get("LOCALAPPDATA")
        return Path(root) / "hermes" if root else Path.home() / "AppData/Local/hermes"
    return Path.home() / ".hermes"


def configured_model(env_name: str) -> str | None:
    """Return a user-selected model without inventing a provider default."""

    value = os.environ.get(env_name, "").strip()
    return value or None


def hermes_managed_node() -> Path | None:
    """Return Hermes' bundled Node before consulting the ambient PATH.

    Windows often has several unrelated Node installations.  The workflow's
    desktop build and MCP wrappers are intentionally owned by Hermes' bundled
    runtime, so reporting whichever `node` happens to appear first on PATH is
    misleading and can hide a working Hermes installation.
    """

    home = hermes_home()
    candidates = [home / "node" / "node.exe", home / "node" / "bin" / "node"]
    return next((candidate for candidate in candidates if candidate.exists()), None)


def codex_candidates() -> list[Path]:
    """Prefer the desktop/plugin binary; PATH wrappers may lag behind it."""

    candidates = [
        Path.home() / "AppData/Local/OpenAI/Codex/bin/codex.exe",
        Path.home() / ".codex/plugins/.plugin-appserver/codex.exe",
    ]
    path_binary = shutil.which("codex")
    if path_binary:
        candidates.append(Path(path_binary))
    result: list[Path] = []
    for candidate in candidates:
        if candidate.exists() and candidate not in result:
            result.append(candidate)
    return result


def resolve_live_codex_workspace(project_root: Path, requested: Path | None) -> Path:
    """Return a project-local runtime parent for the ephemeral Codex smoke repo."""

    supplied = project_root.resolve()
    result = subprocess.run(
        ["git", "-C", str(supplied), "rev-parse", "--show-toplevel"],
        capture_output=True,
        text=True, encoding="utf-8", errors="replace",
        check=False,
    )
    if result.returncode:
        raise SystemExit("--live Codex smoke must run from a Git project root")
    # Git yields a canonical working-tree spelling on Windows, avoiding a mix
    # of 8.3 and long path aliases in containment checks.
    project = Path(result.stdout.strip()).resolve()
    if not os.path.samefile(supplied, project):
        raise SystemExit("--live Codex smoke must run from a Git project root")
    runtime = (project / ".hermes/task-runtime").resolve()
    candidate = requested if requested is not None else Path(".hermes/task-runtime")
    if not candidate.is_absolute():
        candidate = project / candidate
    candidate = candidate.resolve()
    try:
        candidate.relative_to(runtime)
    except ValueError as exc:
        raise SystemExit(
            "--codex-workdir must stay under the current project's .hermes/task-runtime"
        ) from exc
    return candidate


def main() -> int:
    configure_console_output()
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--live",
        action="store_true",
        help="run execution smokes for explicitly selected models (network/model usage)",
    )
    parser.add_argument(
        "--network",
        action="store_true",
        help="run local route, HTTP reachability and MCP checks without provider markers",
    )
    parser.add_argument(
        "--codex-workdir",
        type=Path,
        metavar="PATH",
        help="project-local parent for the ephemeral Codex smoke repo (must be under .hermes/task-runtime)",
    )
    args = parser.parse_args()
    failures: list[str] = []
    live_skips: list[str] = []

    print("Hermes workflow doctor (redacted)")
    print(f"HERMES_HOME={hermes_home()}")

    print("\n=== Hermes structure ===")
    if not shutil.which("hermes"):
        print("[FAIL] hermes command not found")
        return 1
    if not required_command("Hermes version", ["hermes", "--version"]):
        failures.append("Hermes version")
    if not required_command("Hermes config check", ["hermes", "config", "check"], timeout=60):
        failures.append("Hermes config check")
    if not required_command("Hermes auth inventory", ["hermes", "auth", "list"], timeout=60):
        failures.append("Hermes auth inventory")
    if not required_command("Hermes MCP inventory", ["hermes", "mcp", "list"], timeout=60):
        failures.append("Hermes MCP inventory")

    network_checks = args.network or args.live
    if network_checks:
        print("\n=== Network / route structure ===")
        print("[INFO] Proxy environment (endpoint and credentials withheld)")
        for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "NO_PROXY"):
            print("  " + proxy_environment_summary(name))
        for port, role in (
            (7890, "Local network proxy (route tool owner is reported when available)"),
            (15721, "Local Codex router (optional; native Codex OAuth does not depend on it)"),
        ):
            open_now = port_open(port)
            owner = windows_listener_owner(port) if open_now else None
            owner_detail = f"; {owner}" if owner else ""
            print(f"[{'OK' if open_now else 'WARN'}] {role} 127.0.0.1:{port} = {'open' if open_now else 'closed'}{owner_detail}")
        print_command(
            "DeepSeek HTTP reachability (HTTP 401 is reachable, not authenticated)",
            ["curl", "-sSI", "--max-time", "8", "https://api.deepseek.com"],
            timeout=12,
            max_lines=5,
        )
        if port_open(7890):
            print_command(
                "ChatGPT through proxy (HTTP 403 still proves only transport reachability)",
                ["curl", "-sSI", "--proxy", "http://127.0.0.1:7890", "--max-time", "12", "https://chatgpt.com"],
                timeout=15,
                max_lines=6,
            )

    print("\n=== Node / configured MCP ===")
    managed_node = hermes_managed_node()
    if managed_node:
        print_command("Hermes managed Node", [str(managed_node), "--version"])
    else:
        print_command("PATH Node (Hermes managed Node missing)", ["node", "--version"])
    if network_checks:
        print_command("Configured Context7", ['hermes', 'mcp', 'test', 'context7'], timeout=90)
    else:
        print("[SKIP] Context7 MCP connectivity (use --network or --live)")

    print("\n=== Codex structure ===")
    candidates = codex_candidates()
    versions: list[tuple[Path, str]] = []
    for candidate in candidates:
        code, output = print_command(f"Codex version ({candidate})", [str(candidate), "--version"])
        if code == 0:
            versions.append((candidate, output.strip()))
    if not candidates:
        print("[FAIL] Codex executable not found")
        failures.append("codex missing")
    elif not versions:
        failures.append("Codex version")
    elif len({version for _, version in versions}) > 1:
        print("[WARN] Codex version drift detected; plugin binary is the preferred execution path")

    print("[INFO] Codex private config is intentionally not inspected; use executable, listener and live smoke evidence.")

    if args.live:
        print("\n=== LIVE execution smokes ===")
        gpt_model = configured_model("HERMES_GPT_MODEL")
        if gpt_model:
            if not marker_smoke(
                "Hermes GPT OAuth",
                ["hermes", "chat", "-Q", "--provider", "openai-codex", "-m", gpt_model, "-q", "Only reply OK_GPT_LIVE"],
                "OK_GPT_LIVE",
                timeout=180,
            ):
                failures.append("GPT live smoke")
        else:
            print("[SKIP] Hermes GPT OAuth: set HERMES_GPT_MODEL or pass an explicit model to switch_model.py")
            live_skips.append("GPT model not selected")

        deepseek_model = configured_model("HERMES_DEEPSEEK_MODEL")
        if deepseek_model:
            if not marker_smoke(
                "Hermes DeepSeek",
                ["hermes", "chat", "-Q", "--provider", "deepseek", "-m", deepseek_model, "-q", "Only reply OK_DEEPSEEK_LIVE"],
                "OK_DEEPSEEK_LIVE",
                timeout=180,
            ):
                failures.append("DeepSeek live smoke")
        else:
            print("[SKIP] Hermes DeepSeek: set HERMES_DEEPSEEK_MODEL or pass an explicit model to switch_model.py")
            live_skips.append("DeepSeek model not selected")
        if candidates:
            workspace = resolve_live_codex_workspace(Path.cwd(), args.codex_workdir)
            workspace.mkdir(parents=True, exist_ok=True)
            with tempfile.TemporaryDirectory(prefix="codex-live-", dir=workspace) as raw:
                workdir = Path(raw)
                run(["git", "init", "-q"], cwd=workdir)
                if not marker_smoke(
                    "Codex exec",
                    [str(candidates[0]), "exec", "--sandbox", "read-only", "Only reply OK_CODEX_LIVE"],
                    "OK_CODEX_LIVE",
                    timeout=180,
                    cwd=workdir,
                ):
                    failures.append("Codex live smoke")
    else:
        print("\n[INFO] structural checks do not prove provider execution; rerun with --live for real smokes")

    print("\n=== Summary ===")
    if failures:
        print("[FAIL] " + ", ".join(failures))
        return 1
    if args.live:
        if live_skips:
            print("[OK] selected live execution markers passed; skipped=" + ", ".join(live_skips))
        else:
            print("[OK] selected live execution markers passed")
    else:
        print("[OK] structural checks completed; provider execution remains unverified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
