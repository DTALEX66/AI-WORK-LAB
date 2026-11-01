#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the quantitative Workbench UI audit against the real service + Chromium.

Wraps `design-lab/tests/e2e/audit_workbench_ui.mjs`: it refuses to measure a
locally rebuilt bundle (the numbers must describe the committed bytes), starts a
real `ProjectService` on loopback in an isolated runtime root, and writes a
machine-readable report so the measurements survive the run.

Claims E1/E2 UI proof only: no host render, no human jury verdict.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_paths import display_path  # noqa: E402
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
DRIVER = REPO / "design-lab" / "tests" / "e2e" / "audit_workbench_ui.mjs"


def find_node() -> str | None:
    return shutil.which("node")


def find_node_modules_dir() -> Path | None:
    override = os.environ.get("E2E_NODE_MODULES")
    if override and (Path(override) / "node_modules" / "playwright").is_dir():
        return Path(override)
    for candidate in (REPO / "apps" / "workbench", REPO):
        if (candidate / "node_modules" / "playwright").is_dir():
            return candidate
    return None


def find_browser() -> Path | None:
    """Prefer a FULL Chromium build; the headless-shell build is a fallback."""
    override = os.environ.get("AUDIT_BROWSER")
    if override and Path(override).is_file():
        return Path(override)
    roots = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        roots.append(Path(local_appdata) / "ms-playwright")
    roots.append(Path.home() / ".cache" / "ms-playwright")
    preferred = ("chrome.exe", "chrome")
    fallback_names = ("chrome-headless-shell.exe", "chrome-headless-shell")
    fallback = None
    for root in roots:
        if not root.is_dir():
            continue
        for name in sorted(root.iterdir(), reverse=True):
            if not name.name.startswith("chromium-"):
                continue
            for candidate in sorted(name.rglob("*"), reverse=True):
                if candidate.is_file() and candidate.name in preferred:
                    return candidate
        for name in sorted(root.iterdir(), reverse=True):
            if not name.name.startswith("chromium_headless_shell-"):
                continue
            for candidate in sorted(name.rglob("*"), reverse=True):
                if candidate.is_file() and candidate.name in fallback_names:
                    fallback = fallback or candidate
    return fallback


def git_head() -> str:
    result = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip() or "unknown"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out",
                        default=".project-local/task-artifacts/ui-audit/report.json")
    parser.add_argument("--widths", default="1280,1920,2560")
    args = parser.parse_args()

    node = find_node()
    if not node:
        print("AUDIT_BLOCKED: node is not on PATH")
        return 3
    nm = find_node_modules_dir()
    if not nm:
        print("AUDIT_BLOCKED: playwright node_modules not found")
        return 3
    browser = find_browser()
    if not browser:
        print("AUDIT_BLOCKED: no locally installed Chromium found")
        return 3
    if not DRIVER.is_file():
        print(f"AUDIT_BLOCKED: driver missing: {DRIVER}")
        return 3

    drift = subprocess.run(["git", "-C", str(REPO), "diff", "--exit-code", "--quiet",
                            "--", "apps/workbench/build"],
                            capture_output=True, text=True)
    if drift.returncode != 0:
        print("AUDIT_BLOCKED: apps/workbench/build differs from HEAD; commit the "
              "rebuilt bundle before measuring so the numbers match the shipped bytes")
        return 3

    out_path = (REPO / args.out).resolve()
    out_path.parent.mkdir(parents=True, exist_ok=True)

    sys.path.insert(0, str(REPO / "src"))
    from design_lab.service import ProjectService
    from design_lab.http_service import make_server

    runtime = REPO / ".project-local" / "task-runtime" / "ui-audit"
    runtime.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    with tempfile.TemporaryDirectory(dir=runtime) as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text("# synthetic ui audit project", encoding="utf-8")
        with patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(root / ".project-local")}):
            service = ProjectService(str(root))
            server = make_server(service, token, port=0)
            port = server.server_address[1]
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            env = {
                **os.environ,
                "E2E_SERVICE_URL": f"http://127.0.0.1:{port}",
                "E2E_TOKEN": token,
                "E2E_NODE_MODULES": str(nm),
                "E2E_BROWSER": str(browser),
                "AUDIT_WIDTHS": args.widths,
            }
            try:
                proc = subprocess.run([node, str(DRIVER)], env=env, cwd=str(REPO),
                                      capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=1800)
            finally:
                server.shutdown()
                worker.join()
                server.server_close()

    try:
        report = json.loads(proc.stdout)
    except json.JSONDecodeError:
        print(proc.stdout)
        print(proc.stderr)
        print(f"AUDIT_FAILED: driver produced no JSON (exit={proc.returncode})")
        return proc.returncode or 4

    report["environment"] = {
        "commit": git_head(),
        "pythonVersion": (f"{sys.version_info.major}.{sys.version_info.minor}."
                          f"{sys.version_info.micro}"),
        "nodePath": node,
        "browserPath": browser.as_posix(),
        "widths": args.widths,
        "serviceUrl": "loopback ephemeral port (token-only, never logged)",
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    out_path.write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                        encoding="utf-8")

    violations = report.get("violations", [])
    print("AUDIT_REPORT %s" % display_path(out_path, REPO))
    print("AUDIT_SCOPES %s violations=%s ok=%s"
          % (report.get("notes", {}).get("totalMetrics"), len(violations),
             report.get("ok")))
    for line in violations:
        print("  " + line)
    if proc.returncode != 0 and not violations:
        print(proc.stderr)
        print(f"AUDIT_FAILED exit={proc.returncode}")
    return proc.returncode


if __name__ == "__main__":
    raise SystemExit(main())
