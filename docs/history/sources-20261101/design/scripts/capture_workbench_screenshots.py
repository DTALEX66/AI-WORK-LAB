#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Capture Workbench viewport screenshots from the real service + real Chromium.

Writes PNGs plus `screenshot-manifest.json` (sha256 / bytes / viewport / URL /
timestamp / commit / browser+service version) into the documentation folder, so
the UI screenshot claim can be checked against bytes that exist on disk.
Claims E1/E2 visual proof only: no host render, no human jury.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
DRIVER = REPO / "design-lab" / "tests" / "e2e" / "capture_workbench_screenshots.mjs"


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
    override = os.environ.get("CAP_BROWSER")
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
    parser.add_argument("--out", default=".project-local/task-artifacts/workbench-screenshots")
    parser.add_argument("--widths", default="1280,1920,2560")
    parser.add_argument("--source-image",
                        default="design-lab/evals/reconstruction/cases/"
                                "poster-sunrise-001/reference.png")
    parser.add_argument("--seed-native-plan", action="store_true",
                        help="create ONE synthetic native plan in the throwaway capture state, so "
                             "the screenshots show the affordances a zero-row project cannot render. "
                             "This is capture scaffolding, not product data: it is written down in "
                             "capture-scaffold.json and dies with the temporary project root.")
    parser.add_argument("--seed-assistance-plan", action="store_true",
                        help="create ONE synthetic assistance plan (two shot rows, a second "
                             "revision, a named choice, one voluntary report) in the throwaway "
                             "capture state, so the screenshots render the plan detail -- the four "
                             "state chips, the 镜头表, the material formats, the feedback history "
                             "and the revision comparison are states of a stored plan and appear on "
                             "no screenshot of an empty form. Capture scaffolding, not product data: "
                             "written down in capture-scaffold-assistance.json, named as synthetic, "
                             "and it dies with the temporary project root.")
    args = parser.parse_args()

    node = find_node()
    if not node:
        print("CAP_BLOCKED: node is not on PATH")
        return 3
    nm = find_node_modules_dir()
    if not nm:
        print("CAP_BLOCKED: playwright node_modules not found")
        return 3
    browser = find_browser()
    if not browser:
        print("CAP_BLOCKED: no locally installed Chromium found")
        return 3
    if not DRIVER.is_file():
        print(f"CAP_BLOCKED: driver missing: {DRIVER}")
        return 3

    # Build Output Truth: the screenshots are evidence for an exact commit, so
    # the served bundle must be the committed byte, not a local rebuild.
    drift = subprocess.run(["git", "-C", str(REPO), "diff", "--exit-code", "--quiet",
                            "--", "apps/workbench/build"], capture_output=True, text=True)
    if drift.returncode != 0:
        print("CAP_BLOCKED: apps/workbench/build differs from HEAD; "
              "commit the rebuilt bundle before capturing evidence")
        return 3

    out_dir = (REPO / args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    source_image = (REPO / args.source_image).resolve()

    sys.path.insert(0, str(REPO / "src"))
    from design_lab.service import ProjectService
    from design_lab.http_service import make_server

    runtime = REPO / ".project-local" / "task-runtime" / "screenshot-capture"
    runtime.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    with tempfile.TemporaryDirectory(dir=runtime) as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text("# synthetic screenshot capture project",
                                        encoding="utf-8")
        with patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(root / ".project-local")}):
            service = ProjectService(str(root))
            server = make_server(service, token, port=0)
            port = server.server_address[1]
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            # The seeding itself happens inside the driver, once this run's project exists.
            env = {
                **os.environ,
                "E2E_SERVICE_URL": f"http://127.0.0.1:{port}",
                "E2E_TOKEN": token,
                "E2E_NODE_MODULES": str(nm),
                "E2E_BROWSER": str(browser),
                "CAP_OUT_DIR": str(out_dir),
                "CAP_WIDTHS": args.widths,
                "CAP_COMMIT": git_head(),
                "CAP_PYTHON_VERSION": (f"{sys.version_info.major}."
                                       f"{sys.version_info.minor}.{sys.version_info.micro}"),
            }
            if args.seed_native_plan:
                env["CAP_SEED_NATIVE_PLAN"] = "1"
            if args.seed_assistance_plan:
                env["CAP_SEED_ASSISTANCE_PLAN"] = "1"
            if source_image.is_file():
                env["CAP_SOURCE_IMAGE"] = str(source_image)
            try:
                proc = subprocess.run([node, str(DRIVER)], env=env, cwd=str(REPO),
                                      capture_output=True, text=True,
                                      encoding="utf-8", errors="replace", timeout=900)
            finally:
                server.shutdown()
                worker.join()
                server.server_close()

    for line in proc.stdout.strip().splitlines():
        print(line)
    if proc.returncode != 0:
        print(proc.stderr)
        print(f"CAP_FAILED exit={proc.returncode}")
        return proc.returncode

    manifest = out_dir / "screenshot-manifest.json"
    payload = json.loads(manifest.read_text(encoding="utf-8"))
    print("CAP_MANIFEST shots=%s commit=%s browser=%s" % (
        len(payload["screenshots"]), payload["commit"], payload["browser"]["version"]))
    print(json.dumps(payload["screenshots"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
