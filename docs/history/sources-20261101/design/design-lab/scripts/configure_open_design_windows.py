#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""Configure Open Design on Windows to reuse this assistance repo (PLAN-ONLY revision).

V42-0103 (TaskPack v4.2 Phase 1 P0 fix):
- This script is strictly plan-only. It NEVER writes Open Design's private
  app-config.json and NEVER creates/overwrites a launcher .bat.
- It produces a machine-readable plan (stdout) and, with --export-plan <dir>,
  writes that plan JSON into the caller-provided directory (e.g. an ignored
  task-runtime folder) for human review.
- It does NOT read CODEX_HOME/auth.json content (only checks the file exists).
- It does NOT modify CODEX_HOME/config.toml or grant any wide writable/trusted root.
- It does NOT scan a wide permission root for .od-skills.

ODA4-0101 security remediation is preserved: fail-closed SECURITY_BLOCK runs
BEFORE any tool detection, and wide roots / drive roots / E: / user home are
rejected as project targets.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

# Sibling shared locator module (keeps the Open Design machine-location assumption
# in exactly one place; see design-lab/config/adapter-locator-inventory.json).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from resolve_open_design_locator import resolve_open_design_exe, resolver_receipt  # noqa: E402

DEFAULT_MODEL = "gpt-5.5"
DEFAULT_PROXY = "http://127.0.0.1:7890"
LOCATION_ID = "loc_open_design_assistance"
# Wide root is intentionally NOT a default. Caller must pass an exact project path.
DEFAULT_PROJECT_ROOT = Path.cwd()


def windows_home() -> Path:
    return Path(os.environ.get("USERPROFILE") or Path.home())


def default_config_path() -> Path:
    appdata = os.environ.get("APPDATA")
    if not appdata:
        appdata = str(windows_home() / "AppData" / "Roaming")
    return Path(appdata) / "Open Design" / "namespaces" / "release-stable-win" / "data" / "app-config.json"


def default_open_design_exe() -> Path | None:
    """Fail-closed default: explicit env / PATH resolution, no hard-coded machine
    install location (cloud audit 2026-09-25 Prompt B slice; replaces the
    previous owner-machine default)."""
    res = resolve_open_design_exe(None)
    return res.path


def default_codex_home() -> Path:
    return windows_home() / ".codex"


def find_codex_bin(explicit: str | None, required: bool) -> str | None:
    if explicit:
        return str(Path(explicit))
    candidates: list[Path] = []
    home = windows_home()
    codex_root = home / "AppData" / "Local" / "OpenAI" / "Codex" / "bin"
    if codex_root.exists():
        candidates.extend(sorted(codex_root.glob("*/codex.exe"), reverse=True))
        candidates.extend(sorted(codex_root.glob("*/codex.cmd"), reverse=True))
    for name in ("codex.cmd", "codex.exe", "codex"):
        found = shutil.which(name)
        if found:
            candidates.append(Path(found))
    if not candidates:
        if not required:
            # Plan-only: absence of Codex is informational, not fatal.
            return None
        raise SystemExit(
            "Could not find Codex CLI. Install/log in to Codex first, then pass --codex-bin explicitly."
        )
    return str(candidates[0])


def codex_auth_present(codex_home: Path) -> bool:
    """Presence-only check. NEVER reads auth.json contents."""
    return (codex_home / "auth.json").exists()


def smoke_codex(codex_bin: str, codex_home: Path) -> str:
    env = os.environ.copy()
    env["CODEX_HOME"] = str(codex_home)
    proc = subprocess_run([codex_bin, "--version"], env=env)
    return proc.strip()


def subprocess_run(argv: list[str], env: dict[str, str]) -> str:
    import subprocess

    proc = subprocess.run(
        argv,
        text=True,
        encoding="utf-8",
        errors="strict",
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        env=env,
        timeout=30,
    )
    if proc.returncode != 0:
        raise SystemExit(proc.stdout)
    return proc.stdout


def build_project_location(project_root: Path) -> dict[str, Any]:
    """Build a minimal Open Design project-location entry for the exact project root only."""
    return {"id": LOCATION_ID, "name": "DESIGN-LAB", "path": str(project_root)}


def build_plan(project_root: Path, config_path: Path, open_design_exe: Path | None,
               codex_bin: str | None, codex_home: Path, proxy: str | None,
               model: str, launcher: Path, auth_present: bool, version: str) -> dict[str, Any]:
    """Assemble the exact config/launcher plan WITHOUT writing anything.

    The plan describes the minimal project-scoped configuration that a human
    could apply manually in Open Design's own UI/registry; this repo never
    writes Open Design's private app-config.json or a launcher itself.
    """
    config: dict[str, Any] = {}
    config["onboardingCompleted"] = True
    config["agentId"] = "codex"
    config.setdefault("agentModels", {}).setdefault("codex", {})["model"] = model
    config.setdefault("agentCliEnv", {}).setdefault("codex", {})["CODEX_BIN"] = codex_bin or "(auto-detect on manual apply)"
    config["agentCliEnv"]["codex"]["CODEX_HOME"] = str(codex_home)
    config["projectLocations"] = [build_project_location(project_root)]
    config["defaultProjectLocationId"] = LOCATION_ID

    launcher_lines = ["@echo off"]
    if proxy:
        launcher_lines.extend([f'set "HTTP_PROXY={proxy}"', f'set "HTTPS_PROXY={proxy}"'])
    launcher_lines.extend([
        f'set "CODEX_BIN={codex_bin}"',
        f'set "CODEX_HOME={codex_home}"',
    ])
    if open_design_exe is not None:
        launcher_lines.append(f'start "Open Design" "{open_design_exe}"')
    else:
        launcher_lines.append('rem Open Design exe UNRESOLVED (fail-closed). Set OPEN_DESIGN_EXE or register it in App Paths/PATH, then apply manually.')
    launcher_lines.append("")

    return {
        "schemaVersion": "design-lab/config-plan/v1",
        "task": "V42-0103",
        "mode": "plan-only",
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "security": {
            "project_root": str(project_root),
            "app_config_path_written": False,
            "launcher_written": False,
            "note": "This repo never writes Open Design private app-config.json or launcher files. Apply the plan manually in Open Design's own registry/UI."
        },
        "app_config_plan": config,
        "launcher_plan": {
            "path": str(launcher),
            "content": "\r\n".join(launcher_lines),
        },
        "detected": {
            "open_design_exe": str(open_design_exe) if open_design_exe is not None else None,
            "config_path": str(config_path),
            "codex_bin": codex_bin,
            "codex_home": str(codex_home),
            "codex_version": version,
            "codex_auth_present": auth_present,
        },
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Configure Open Design for DESIGN-LAB reuse on Windows (PLAN-ONLY: never writes private config or launchers)."
    )
    parser.add_argument("--project-root", default=str(DEFAULT_PROJECT_ROOT),
                        help="Exact DESIGN-LAB directory (must be an explicit project path, never a wide root)")
    parser.add_argument("--config", default=str(default_config_path()), help="Open Design app-config.json path (reported for manual apply only)")
    parser.add_argument("--open-design-exe", default=None,
                        help="Open Design.exe path; when omitted, resolved via the "
                             "shared fail-closed locator (env OPEN_DESIGN_EXE, then PATH)")
    parser.add_argument("--codex-bin", default=None, help="Native codex.exe/codex.cmd path; auto-detected when omitted")
    parser.add_argument("--codex-home", default=str(default_codex_home()), help="Codex home (presence-only OAuth check)")
    parser.add_argument("--model", default=DEFAULT_MODEL, help="Codex model shown in Open Design")
    parser.add_argument("--launcher", default=None, help="Optional launcher .bat path (plan output only, never written)")
    parser.add_argument("--no-proxy", action="store_true", help="Do not put proxy env vars into launcher plan")
    parser.add_argument("--export-plan", default=None,
                        help="Optional directory (e.g. an ignored task-runtime folder) to write the plan JSON for human review")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    project_root = Path(args.project_root).resolve()
    config_path = Path(args.config)
    codex_home = Path(args.codex_home)

    # Security guard: reject a wide root as the PROJECT target. A wide root is
    # exactly a drive root, the user home, or the D:\All projects parent itself.
    # Deep exact project sub-paths under D:\All projects ARE allowed.
    def norm_root(p: Path) -> str:
        return str(p).replace("/", "\\").rstrip("\\").lower()

    project_norm = norm_root(project_root)
    # Wide roots expressed as exact normalized values (drive roots, home, parent).
    drive_roots = {norm_root(Path(f"{d}:\\")) for d in ("C", "D", "E", "F")}
    wide_exact = {norm_root(Path(r"D:\All projects")), norm_root(Path(r"C:\Users"))}
    wide_exact |= drive_roots
    if project_norm in wide_exact:
        raise SystemExit(
            "SECURITY_BLOCK: wide root supplied as project target. Refusing to configure. "
            "Pass an exact project directory such as D:\\All projects\\DESIGN-LAB."
        )
    # Additionally forbid E: entirely; and forbid the user home as a project target.
    user_home_norm = norm_root(windows_home())
    if project_norm.startswith("e:") or project_norm == user_home_norm:
        raise SystemExit("SECURITY_BLOCK: forbidden root (E: drive or user home). Refusing to configure.")

    if not project_root.exists():
        raise SystemExit(f"Project root does not exist: {project_root}")

    # Tool detection runs AFTER the security boundary so the guard is fail-closed
    # even when the environment lacks Codex CLI (e.g. a CI runner).
    # Plan-only never requires Codex to be present.
    codex_bin = find_codex_bin(args.codex_bin, required=False)

    # Presence-only OAuth check (never reads content).
    auth_ok = codex_auth_present(codex_home)
    if not auth_ok:
        print(f"WARN: Codex auth.json not found at {codex_home}. OAuth presence check failed (not blocking).")

    version = smoke_codex(codex_bin, codex_home) if codex_bin else "(not found; plan-only)"

    # Fail-closed Open Design exe resolution (cloud audit 2026-09-25 Prompt B):
    # explicit --open-design-exe wins; otherwise env OPEN_DESIGN_EXE / PATH;
    # when unresolved the plan records it honestly instead of assuming a
    # machine path. No download, no install.
    open_design_exe = (
        Path(args.open_design_exe)
        if args.open_design_exe
        else resolve_open_design_exe(None).path
    )
    if open_design_exe is None:
        print(f"OPEN_DESIGN_EXE_UNRESOLVED (fail-closed; no download attempted). {resolver_receipt(None)}")

    launcher = Path(args.launcher) if args.launcher else (open_design_exe.with_name("Open Design - GPT Codex Proxy.bat") if open_design_exe else Path("Open Design - GPT Codex Proxy.bat"))
    plan = build_plan(
        project_root=project_root,
        config_path=config_path,
        open_design_exe=open_design_exe,
        codex_bin=codex_bin,
        codex_home=codex_home,
        proxy=None if args.no_proxy else DEFAULT_PROXY,
        model=args.model,
        launcher=launcher,
        auth_present=auth_ok,
        version=version,
    )

    if args.export_plan:
        out_dir = Path(args.export_plan).resolve()
        out_dir.mkdir(parents=True, exist_ok=True)
        out_file = out_dir / "open-design-config-plan.json"
        out_file.write_text(json.dumps(plan, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"PLAN_EXPORTED={out_file}")

    print("OPEN_DESIGN_ASSISTANCE_CONFIG_OK (plan-only; nothing was written)")
    print(f"project_root={project_root}")
    print(f"config_path={config_path} (NOT written; apply manually in Open Design)")
    print(f"launcher={launcher} (NOT written; plan only)")
    print(f"codex_bin={codex_bin}")
    print(f"codex_home={codex_home}")
    print(f"codex_version={version}")
    print(f"codex_auth_present={auth_ok}")
    print("mode=plan-only")


if __name__ == "__main__":
    main()
