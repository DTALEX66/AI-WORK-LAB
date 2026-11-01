#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Diagnose a Windows Open Design + Codex + DESIGN-LAB setup (SAFE revision).

ODA4-0101 security remediation:
- Does NOT read CODEX_HOME/auth.json content; only reports presence.
- Does NOT scan a wide permission root for .od-skills.
- Does NOT report wide writable/trusted root expectations (wide-root granting is removed).
- Remains read-only.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import tomllib
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# Sibling shared locator module (keeps the Open Design machine-location assumption
# in exactly one place; see design-lab/config/adapter-locator-inventory.json).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_open_design_locator import resolve_open_design_exe, resolver_receipt  # noqa: E402

DEFAULT_MODEL = "gpt-5.6-luna"
DEFAULT_PORTS = (5294, 5499)
LOCATION_ID = "loc_open_design_assistance"


@dataclass
class Check:
    name: str
    ok: bool
    detail: str = ""


def windows_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA") or str(windows_home() / "AppData" / "Roaming")
    return Path(appdata) / "Open Design" / "namespaces" / "release-stable-win" / "data" / "app-config.json"


def default_open_design_exe() -> Path | None:
    """Fail-closed default: explicit env / PATH resolution, no hard-coded machine
    install location (cloud audit 2026-09-25 Prompt B slice; replaces the
    previous owner-machine default)."""
    res = resolve_open_design_exe(None)
    return res.path


def default_codex_home() -> Path:
    return windows_home() / ".codex"


def read_json(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        return json.loads(path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:  # noqa: BLE001 - diagnostic script should report any parse failure.
        return None, f"invalid json: {exc}"


def read_toml(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, "missing"
    try:
        return tomllib.loads(path.read_text(encoding="utf-8")), "ok"
    except Exception as exc:  # noqa: BLE001
        return None, f"invalid toml: {exc}"


def find_codex_bin(config: dict[str, Any] | None, explicit: str | None) -> str | None:
    if explicit:
        return explicit
    configured = (((config or {}).get("agentCliEnv") or {}).get("codex") or {}).get("CODEX_BIN")
    if configured and Path(str(configured)).exists():
        return str(configured)
    for name in ("codex.cmd", "codex.exe", "codex"):
        found = shutil.which(name)
        if found:
            return found
    root = windows_home() / "AppData" / "Local" / "OpenAI" / "Codex" / "bin"
    if root.exists():
        for pattern in ("*/codex.exe", "*/codex.cmd"):
            found = sorted(root.glob(pattern), reverse=True)
            if found:
                return str(found[0])
    return None


def codex_auth_present(codex_home: Path) -> bool:
    """Presence-only. Never reads auth.json contents."""
    return (codex_home / "auth.json").exists()


def run_version(exe: str, codex_home: Path) -> tuple[bool, str]:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    try:
        proc = subprocess.run([exe, "--version"], text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, timeout=30)
    except Exception as exc:  # noqa: BLE001
        return False, str(exc)
    return proc.returncode == 0, proc.stdout.strip()


def port_open(port: int, timeout: float = 0.35) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=timeout):
            return True
    except OSError:
        return False


def git_clean(project_root: Path) -> tuple[bool, str]:
    if not (project_root / ".git").exists():
        return False, "not a git repository"
    proc = subprocess.run(["git", "status", "--short", "--branch"], cwd=project_root, text=True, encoding="utf-8", errors="replace", stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=30)
    lines = [line for line in proc.stdout.splitlines() if line.strip()]
    clean = proc.returncode == 0 and len(lines) == 1 and "origin/" in lines[0]
    return clean, proc.stdout.strip()


def diagnose(args: argparse.Namespace) -> list[Check]:
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config)
    # Fail-closed exe resolution (cloud audit 2026-09-25 Prompt B): explicit
    # --open-design-exe wins; otherwise the shared locator (env OPEN_DESIGN_EXE,
    # then PATH). When unresolved the doctor reports it, never assumes a path.
    open_design_exe = (
        Path(args.open_design_exe)
        if args.open_design_exe
        else resolve_open_design_exe(None).path
    )
    codex_home = Path(args.codex_home)
    launcher = Path(args.launcher) if args.launcher else (open_design_exe.with_name("Open Design - GPT Codex Proxy.bat") if open_design_exe else Path("Open Design - GPT Codex Proxy.bat"))

    config, config_status = read_json(config_path)
    codex_bin = find_codex_bin(config, args.codex_bin)
    project_locations = (config or {}).get("projectLocations") or []
    location_paths = {str(loc.get("path")) for loc in project_locations if isinstance(loc, dict)}
    default_location = (config or {}).get("defaultProjectLocationId")
    model = (((config or {}).get("agentModels") or {}).get("codex") or {}).get("model")

    checks = [
        Check("project root exists", project_root.exists(), str(project_root)),
        Check("Open Design executable exists",
              (open_design_exe.exists() if open_design_exe is not None else False),
              (str(open_design_exe) if open_design_exe is not None
               else "UNRESOLVED (fail-closed; no download attempted) — " + resolver_receipt(None).splitlines()[0])),
        Check("app-config.json valid", config is not None, f"{config_path} ({config_status})"),
        Check("agentId is codex", (config or {}).get("agentId") == "codex", str((config or {}).get("agentId"))),
        Check("default model configured", model == args.expected_model, str(model)),
        Check("project location registered", str(project_root) in location_paths, str(project_root)),
        Check("default project location selected", default_location == LOCATION_ID, str(default_location)),
        Check("Codex home exists", codex_home.exists(), str(codex_home)),
        Check("Codex auth.json present (not read)", codex_auth_present(codex_home), str(codex_home / "auth.json")),
        Check("Codex executable discovered", bool(codex_bin), codex_bin or "missing"),
        Check("proxy launcher exists", launcher.exists(), str(launcher)),
        Check("portable setup doc exists", (project_root / "design-lab" / "usage-notes" / "PORTABLE_OPEN_DESIGN_SETUP.md").exists()),
        Check("plugin workspace exists", (project_root / "design-lab" / "plugins").exists()),
        Check("repo is clean and tracks origin", *git_clean(project_root)),
    ]

    if codex_bin:
        ok, version = run_version(codex_bin, codex_home)
        checks.append(Check("Codex CLI runs", ok, version))

    for port in args.ports:
        checks.append(Check(f"Open Design local port {port} reachable", port_open(port), "optional; false is OK when app is closed"))

    log = config_path.with_name("logs") / "latest.log"
    fallback_log = config_path.parent / "latest.log"
    checks.append(Check("daemon latest.log seen", log.exists() or fallback_log.exists(), str(log if log.exists() else fallback_log)))
    return checks


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Read-only safe doctor for Open Design + DESIGN-LAB on Windows.")
    parser.add_argument("--project-root", default=str(Path.cwd()), help="DESIGN-LAB clone")
    parser.add_argument("--config", default=str(default_config_path()), help="Open Design app-config.json")
    parser.add_argument("--open-design-exe", default=None,
                        help="Open Design.exe path; when omitted, resolved via the "
                             "shared fail-closed locator (env OPEN_DESIGN_EXE, then PATH)")
    parser.add_argument("--codex-bin", default=None, help="Optional explicit codex.exe/codex.cmd path")
    parser.add_argument("--codex-home", default=str(default_codex_home()), help="Codex home")
    parser.add_argument("--launcher", default=None, help="Optional launcher .bat path")
    parser.add_argument("--expected-model", default=DEFAULT_MODEL, help="Expected Codex model")
    parser.add_argument("--ports", nargs="*", type=int, default=list(DEFAULT_PORTS), help="Local ports to probe")
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on any required failure")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    checks = diagnose(args)
    required_names = {
        "project root exists",
        "app-config.json valid",
        "agentId is codex",
        "default model configured",
        "project location registered",
        "default project location selected",
        "Codex home exists",
        "Codex executable discovered",
        "Codex CLI runs",
        "portable setup doc exists",
        "repo is clean and tracks origin",
    }
    print("OPEN_DESIGN_ASSISTANCE_DOCTOR")
    failed_required = []
    for check in checks:
        status = "PASS" if check.ok else ("WARN" if check.name not in required_names else "FAIL")
        print(f"{status} {check.name}: {check.detail}")
        if not check.ok and check.name in required_names:
            failed_required.append(check.name)
    if failed_required:
        print("DOCTOR_RESULT=FAIL")
        if args.strict:
            raise SystemExit(1)
    else:
        print("DOCTOR_RESULT=OK")


if __name__ == "__main__":
    main()
