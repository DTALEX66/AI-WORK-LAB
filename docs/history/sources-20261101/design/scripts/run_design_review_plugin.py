#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Run the external design-review plugin's deterministic auditors on the real product.

WHY THIS EXISTS
    DESIGN-LAB's UI claims were measured only by gates this repository wrote for
    itself. An outside implementation of the same questions (design debt, axe-core
    accessibility) had never produced a number here, because the plugin's own
    dependencies are not installed in its cache directory and Node resolves bare
    specifiers from the importing file. `.project-local/runs/node-libs/register.mjs`
    installs a resolve hook that answers those specifiers from this repository.

WHAT IT DOES
    1. `audit-design-debt.mjs` over the committed Workbench source set (design.qa.yaml).
    2. `audit-a11y.mjs` (axe-core in real Chromium) over the screens of design.qa.yaml,
       against the SAME bundle served by the product's own loopback service on the port
       design.qa.yaml names, auto-connected through the official `/api/local-session`
       handshake -- so the scan sees authenticated views, not a login wall.

WHAT IT REFUSES TO DO
    It will not measure a locally rebuilt bundle (the drift guard is the one
    `scripts/audit_workbench_ui.py` uses), will not fall back to a random port, and will
    not report a scan that produced no report file. Absent plugin, absent Node, absent
    harness, busy port -> a stated blocker and a non-zero exit.

    This is a measurement tool, NOT a CI gate: findings are printed and archived, never
    turned into a pass/fail verdict about the repository.

Usage:
    python scripts/run_design_review_plugin.py                 # both auditors
    python scripts/run_design_review_plugin.py --only debt
    python scripts/run_design_review_plugin.py --only a11y
"""
from __future__ import annotations

import argparse
import json
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from report_paths import display_path  # noqa: E402
from unittest.mock import patch

REPO = Path(__file__).resolve().parents[1]
CONFIG = REPO / "design.qa.yaml"
NODE_LIBS = REPO / ".project-local" / "runs" / "node-libs"
PLUGIN_MARKER = Path("skills/design-debt-review/scripts/audit-design-debt.mjs")

AUDITORS = {
    "debt": ("skills/design-debt-review/scripts/audit-design-debt.mjs", "design-debt.json"),
    "a11y": ("skills/accessibility-review/scripts/audit-a11y.mjs", "a11y.json"),
}

# Versions the harness is expected to carry. The plugin imports these as bare
# specifiers from its own cache directory, so they must be resolvable here.
HARNESS_PACKAGES = ("fast-glob", "yaml", "@axe-core/playwright", "axe-core",
                    "@playwright/test", "playwright", "playwright-core")


def blocked(reason: str) -> int:
    print(f"DESIGN_REVIEW_BLOCKED: {reason}")
    return 3


def find_node() -> str | None:
    return shutil.which("node")


def find_plugin_root() -> Path | None:
    """Highest installed version of the plugin, or nothing. Never a guessed path."""
    override = os.environ.get("DESIGN_REVIEW_PLUGIN_ROOT")
    if override:
        candidate = Path(override)
        return candidate if (candidate / PLUGIN_MARKER).is_file() else None
    base = (Path.home() / ".qoder-cn" / "plugins" / "cache"
            / "qoder-marketplace" / "design-review")
    if not base.is_dir():
        return None
    versions = sorted((p for p in base.iterdir() if (p / PLUGIN_MARKER).is_file()),
                      key=lambda p: p.name)
    return versions[-1] if versions else None


def config_value(pattern: str) -> str | None:
    if not CONFIG.is_file():
        return None
    match = re.search(pattern, CONFIG.read_text(encoding="utf-8"), re.MULTILINE)
    return match.group(1) if match else None


def report_path(which: str) -> Path:
    """Where the plugin writes, derived from the committed config rather than a guess."""
    output_dir = config_value(r'^\s*outputDir:\s*"?([^\s"]+)"?') or ".project-local/runs/design-review/.design-qa"
    return REPO / output_dir / "reports" / AUDITORS[which][1]


BROWSERS = REPO / ".project-local" / "runs" / "pw-browsers"


def browser_environment(env: dict[str, str]) -> dict[str, str]:
    """Point Playwright at the Chromium build this repository downloaded, when there is one.

    The plugin's auditor calls `chromium.launch()` with no executablePath, so the build is
    found through the default cache -- which on this machine holds revisions the pinned
    Playwright does not ask for. The alternative was to substitute a different engine and
    report a11y numbers measured on something else.
    """
    if BROWSERS.is_dir() and any(p.name.startswith("chromium") for p in BROWSERS.iterdir()):
        return {**env, "PLAYWRIGHT_BROWSERS_PATH": str(BROWSERS)}
    return env


def package_versions() -> dict[str, str]:
    """Record what actually ran: an outside tool's numbers mean nothing without the
    versions of the code that produced them."""
    out: dict[str, str] = {}
    root = NODE_LIBS / "node_modules"
    for name in HARNESS_PACKAGES:
        manifest = root / name / "package.json"
        if not manifest.is_file():
            continue
        try:
            out[name] = str(json.loads(manifest.read_text(encoding="utf-8"))
                            .get("version", "unknown"))
        except (OSError, ValueError):
            out[name] = "unreadable"
    return out


def git_head() -> str:
    result = subprocess.run(["git", "-C", str(REPO), "rev-parse", "HEAD"],
                            capture_output=True, text=True, encoding="utf-8")
    return result.stdout.strip() or "unknown"


def run_auditor(which: str, plugin: Path, node: str, env: dict[str, str]) -> dict | None:
    script, _ = AUDITORS[which]
    hook = NODE_LIBS.resolve().as_uri() + "/register.mjs"
    proc = subprocess.run([node, "--import", hook, str(plugin / script),
                           "--config", str(CONFIG)],
                          env=env, cwd=str(REPO), capture_output=True,
                          text=True, encoding="utf-8", errors="replace", timeout=1800)
    if proc.stdout.strip():
        print(proc.stdout.strip())
    if proc.returncode != 0:
        print(f"DESIGN_REVIEW_{which.upper()}_ERROR exit={proc.returncode}")
        print((proc.stderr or "").strip()[-2000:])
        return None
    destination = report_path(which)
    if not destination.is_file():
        print(f"DESIGN_REVIEW_{which.upper()}_NO_REPORT {destination}")
        return None
    payload = json.loads(destination.read_text(encoding="utf-8"))
    payload["__reportPath"] = display_path(destination, REPO)
    return payload


def serve_and_scan(plugin: Path, node: str, env: dict[str, str], port: int) -> dict | None:
    sys.path.insert(0, str(REPO / "src"))
    from design_lab import workbench
    from design_lab.http_service import make_server
    from design_lab.service import ProjectService

    runtime = REPO / ".project-local" / "task-runtime" / "design-review-plugin"
    runtime.mkdir(parents=True, exist_ok=True)
    token = secrets.token_hex(32)
    with tempfile.TemporaryDirectory(dir=runtime) as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text("# synthetic design-review plugin project",
                                       encoding="utf-8")
        with patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(root / ".project-local")}):
            server = make_server(ProjectService(str(root)), token, port=port,
                                 local_session=True)
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            served = {"bundleOrigin": workbench.bundle_origin(),
                      "bundleSha256": workbench.served_bundle_sha256()}
            try:
                report = run_auditor("a11y", plugin, node, env)
            finally:
                server.shutdown()
                worker.join()
                server.server_close()
    if report is not None:
        report["__servedBundle"] = served
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--only", choices=("debt", "a11y", "both"), default="both")
    parser.add_argument("--out",
                        default=".project-local/task-artifacts/design-review/plugin-run.json")
    args = parser.parse_args()

    node = find_node()
    if not node:
        return blocked("node is not on PATH (bind the toolchain root named by "
                       ".project/paths.json before running)")
    if not CONFIG.is_file():
        return blocked(f"missing committed run config: {CONFIG}")
    plugin = find_plugin_root()
    if plugin is None:
        return blocked("design-review plugin is not installed under "
                       "~/.qoder-cn/plugins/cache/qoder-marketplace/design-review")
    for part in ("register.mjs", "resolver.mjs"):
        if not (NODE_LIBS / part).is_file():
            return blocked(f"missing resolve hook: {NODE_LIBS / part}")
    if not (NODE_LIBS / "node_modules" / "yaml").is_dir():
        return blocked(
            f"missing dependency harness: {NODE_LIBS / 'node_modules'} needs fast-glob, "
            "yaml, @axe-core/playwright and @playwright/test@1.63.0 -- the one-time setup "
            "command, including the cache-root workaround this machine requires, is "
            "recorded in docs/audits/DESIGNLAB-EXTERNAL-DESIGN-REVIEW-2026-10-09.md")

    declared = config_value(r'^\s*baseUrl:\s*"?https?://127\.0\.0\.1:(\d+)"?')
    if not declared:
        return blocked("design.qa.yaml must declare project.baseUrl as a 127.0.0.1 URL")
    port = int(declared)

    env = browser_environment({**os.environ, "DESIGN_PLUGIN_ROOT": str(plugin)})
    out: dict = {
        "generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "commit": git_head(),
        "pluginRoot": plugin.as_posix(),
        "node": node,
        "nodeVersion": subprocess.run([node, "-v"], capture_output=True, text=True,
                                      encoding="utf-8").stdout.strip(),
        "dependencyVersions": package_versions(),
        "browsersRoot": env.get("PLAYWRIGHT_BROWSERS_PATH",
                                "(Playwright default cache -- no project-local build)"),
        "browserBuildsPresent": sorted(p.name for p in BROWSERS.iterdir()
                                       if p.is_dir()) if BROWSERS.is_dir() else [],
        "baseUrl": f"http://127.0.0.1:{port}",
    }

    if args.only in ("debt", "both"):
        out["designDebt"] = run_auditor("debt", plugin, node, env)
        if out["designDebt"] is None:
            return 4

    if args.only in ("a11y", "both"):
        drift = subprocess.run(["git", "-C", str(REPO), "diff", "--exit-code", "--quiet",
                                "--", "apps/workbench/build"],
                               capture_output=True, text=True)
        if drift.returncode != 0:
            return blocked("apps/workbench/build differs from HEAD; commit the rebuilt "
                           "bundle before measuring, so the numbers match shipped bytes")
        probe = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            probe.bind(("127.0.0.1", port))
        except OSError:
            return blocked(f"port {port} is busy; the port in design.qa.yaml is the one "
                           "the audit binds, and falling back to another would make the "
                           "committed config describe a different run")
        finally:
            probe.close()
        out["a11y"] = serve_and_scan(plugin, node, env, port)
        if out["a11y"] is None:
            return 4

    for key in ("designDebt", "a11y"):
        report = out.get(key)
        if report is None:
            continue
        print(f"PLUGIN_{key.upper()} findings={len(report.get('findings', []))} "
              f"ok={report.get('ok')} report={report.get('__reportPath')}")

    dest = REPO / args.out
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("DESIGN_REVIEW_PLUGIN=WRITTEN " + display_path(dest, REPO))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
