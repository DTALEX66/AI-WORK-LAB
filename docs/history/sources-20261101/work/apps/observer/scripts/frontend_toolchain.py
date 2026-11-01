#!/usr/bin/env python
"""One tracked entry point for building and serving the Observer front end.

Every fact this script encodes was a trap hit on 2026-10-08, and each one looked like a missing
capability rather than a missing route:

* **The runtime is declared, not guessed.** `.project/governance/toolchain-declarations.json` names manager
  `node-observer-frontend` with `install: npm ci`, its lockfile, and a `knownGap` that already records the
  local Node root. The first session concluded "this machine has no node.exe" without reading that file.
  The root is resolved from the declaration (falling back to the recorded path) and never hardcoded.
* **`npm ci` was the whole "missing toolchain" story.** `frontend/node_modules` held 24 directories with no
  `vite`, `react` or `typescript`; the declared install restored 279 packages in 5 seconds.
* **`vite preview` binds `localhost`, which resolves to `::1` first on this host.** A window pointed at
  `127.0.0.1:4173` then gets a connection refusal while the server looks healthy, and the orphaned
  IPv6-only listener holds the port so the next start dies with "already in use". Preview therefore binds
  an explicit address and reports it.
* **Everything this produces stays inside the Git root**: npm cache, temp and the Chrome profile all point
  under `.project-local/`, per `.project/governance/project-data-boundary.json`.

Usage:
    python apps/observer/scripts/frontend_toolchain.py resolve      # print the binding, change nothing
    python apps/observer/scripts/frontend_toolchain.py install      # declared `npm ci`
    python apps/observer/scripts/frontend_toolchain.py build        # tsc -b && vite build
    python apps/observer/scripts/frontend_toolchain.py preview      # serve dist on 127.0.0.1:4173
    python apps/observer/scripts/frontend_toolchain.py window       # preview + one visible CDP window

Exit: 0 on the verdict line, 1 when the binding cannot be resolved, 2 on a failed child command.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
import webbrowser
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
FRONTEND = REPO / "apps" / "observer" / "frontend"
DECLARATIONS = REPO / ".project" / "governance" / "toolchain-declarations.json"
MANAGER_ID = "node-observer-frontend"
LOCAL_RUNS = REPO / ".project-local" / "runs"
DEFAULT_NODE_ROOTS = (
    Path("C:/Users/ALEX/AppData/Local/OpenHuman/node-runtime"),
    Path("C:/Users/ALEX/AppData/Local/hermes/tools"),
)
PREVIEW_HOST = "127.0.0.1"
PREVIEW_PORT = 4173


def declared_manager() -> dict:
    data = json.loads(DECLARATIONS.read_text(encoding="utf-8"))
    for manager in data.get("managers", []):
        if manager.get("id") == MANAGER_ID:
            return manager
    raise SystemExit(f"RESOLVE_FAIL manager {MANAGER_ID!r} is not declared in {DECLARATIONS.name}")


def _candidate_roots() -> list[Path]:
    """Paths named by the tracked declaration, then the machine-level defaults.

    The `knownGap` prose is mined for a Windows path token, and the token is normalised: an earlier
    version here took the sentence's `.../node-runtime.` with its trailing period, which Win32 happily
    resolves for `node.exe` while Node's own module loader will not traverse it for `npm-cli.js`. A
    half-bound runtime is worse than none, because the failure surfaces three calls later.
    """
    gap = declared_manager().get("knownGap") or ""
    roots: list[Path] = []
    for token in gap.replace(",", " ").split():
        if ":" in token and ("/" in token or "\\" in token):
            cleaned = token.rstrip(".,;").replace("\\", "/")
            candidate = Path(cleaned)
            if candidate not in roots:
                roots.append(candidate)
    return roots + list(DEFAULT_NODE_ROOTS)


def _bound(root: Path) -> Path | None:
    """A root is bound only when both the interpreter and the npm CLI it must drive are present."""
    for directory in (root, *sorted(root.glob("node-*"))):
        node = directory / "node.exe"
        npm_cli = directory / "node_modules" / "npm" / "bin" / "npm-cli.js"
        if node.is_file() and npm_cli.is_file():
            return node
    return None


def find_node() -> Path:
    """A node.exe under a declared root, accepted only together with its npm CLI."""
    roots = _candidate_roots()
    for root in roots:
        bound = _bound(root)
        if bound is not None:
            return bound
    raise SystemExit(f"RESOLVE_FAIL no root with both node.exe and npm-cli.js among: {[str(r) for r in roots]}")


def env_for(node: Path) -> dict:
    (LOCAL_RUNS / "tmp").mkdir(parents=True, exist_ok=True)
    (LOCAL_RUNS / "cache" / "npm").mkdir(parents=True, exist_ok=True)
    (LOCAL_RUNS / "cache" / "node-compile-cache").mkdir(parents=True, exist_ok=True)
    env = dict(os.environ)
    env.update({
        "PATH": f"{node.parent}{os.pathsep}{env.get('PATH', '')}",
        "TMP": str(LOCAL_RUNS / "tmp"), "TEMP": str(LOCAL_RUNS / "tmp"), "TMPDIR": str(LOCAL_RUNS / "tmp"),
        # Node 22 writes its module compile cache next to TMPDIR, and `runs/tmp` is the root the
        # fixture-residue guard censuses — a build cache that ages past the floor shows up as an
        # orphaned fixture. Measured: NODE_COMPILE_CACHE is honoured by the declared runtime
        # (v22.11.0-x64-*), so the cache goes to the boundary's declared cacheRoot instead.
        "NODE_COMPILE_CACHE": str(LOCAL_RUNS / "cache" / "node-compile-cache"),
        "npm_config_cache": str(LOCAL_RUNS / "cache" / "npm"),
        "npm_config_audit": "false", "npm_config_fund": "false", "npm_config_update_notifier": "false",
        "PYTHONIOENCODING": "utf-8",
    })
    return env


def npm(node: Path, args: list[str], env: dict) -> int:
    cli = node.parent / "node_modules" / "npm" / "bin" / "npm-cli.js"
    if not cli.is_file():
        raise SystemExit(f"RESOLVE_FAIL npm-cli.js is not beside {node}")
    return subprocess.run([str(node), str(cli), *args], cwd=str(FRONTEND), env=env).returncode


def port_open(host: str, port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        probe.settimeout(0.4)
        return probe.connect_ex((host, port)) == 0


def command(node: Path, args: list[str], env: dict) -> int:
    return subprocess.run([str(node), "node_modules/vite/bin/vite.js", *args], cwd=str(FRONTEND), env=env).returncode


def cmd_resolve(_: argparse.Namespace) -> int:
    node = find_node()
    version = subprocess.run([str(node), "--version"], capture_output=True, text=True,
                             encoding="utf-8", errors="replace").stdout.strip()
    print(f"NODE_BOUND node={node} version={version}")
    print(f"NPM_BOUND npm_cli={node.parent / 'node_modules' / 'npm' / 'bin' / 'npm-cli.js'} "
          f"exists={(node.parent / 'node_modules' / 'npm' / 'bin' / 'npm-cli.js').is_file()}")
    print(f"DECLARED install={declared_manager().get('install')} lockfile={declared_manager().get('lockfile')}")
    return 0


def cmd_install(_: argparse.Namespace) -> int:
    node, env = find_node(), {}
    env = env_for(node)
    code = npm(Path(node), ["ci", "--no-audit", "--no-fund"], env)
    print(f"INSTALL_EXIT={code}")
    return code


def cmd_build(_: argparse.Namespace) -> int:
    node = find_node()
    env = env_for(node)
    code = npm(node, ["run", "build"], env)
    print(f"BUILD_EXIT={code}")
    return code


def cmd_preview(args: argparse.Namespace) -> int:
    node = find_node()
    env = env_for(node)
    if port_open(args.host, args.port):
        print(f"PREVIEW_FAIL port {args.host}:{args.port} is already held; an earlier IPv6-only listener "
              f"looks healthy from curl's point of view and refuses 127.0.0.1 -- find it with "
              f"`netstat -ano | grep :{args.port}` and stop that process before retrying")
        return 2
    proc = subprocess.Popen([str(node), "node_modules/vite/bin/vite.js", "preview",
                             "--host", args.host, "--port", str(args.port), "--strictPort"],
                            cwd=str(FRONTEND), env=env)
    for _ in range(60):
        try:
            with urllib.request.urlopen(f"http://{args.host}:{args.port}/", timeout=2) as response:
                if response.status == 200:
                    print(f"PREVIEW_READY http://{args.host}:{args.port}/")
                    break
        except Exception:
            time.sleep(0.5)
    else:
        print("PREVIEW_NOT_READY")
        proc.terminate()
        return 1
    if args.window:
        profile = LOCAL_RUNS / "chrome-profile-preview"
        profile.mkdir(parents=True, exist_ok=True)
        chrome = os.environ.get("WL_CHROME")
        if chrome and Path(chrome).is_file():
            subprocess.Popen([chrome, f"--user-data-dir={profile}", "--remote-debugging-port=9334",
                              "--no-first-run", f"--app=http://{args.host}:{args.port}/"])
            print(f"WINDOW_OPENED via {chrome} debug_port=9334 profile={profile}")
        else:
            webbrowser.open(f"http://{args.host}:{args.port}/")
            print("WINDOW_OPENED via the default browser (set WL_CHROME for the declared Chromium)")
    proc.wait()
    return 0


def cmd_contracts(args: argparse.Namespace) -> int:
    """Run the two front-end contract suites so a local PASS means the same thing as CI.

    Both are CI-only in the sense that mattered: the `observer` job runs the JS suite through the
    `observer-web-contracts` group and vitest through `observer-frontend-test`, and until this stage existed
    neither had a local route. That gap produced two reds on a green local gate — the legibility micro-role
    rule, and an action row that folded every control away under jsdom. (A claim added on 2026-10-25 that the
    JS suite had no CI runner at all was false: it came from grepping only the Python files under `scripts/ci/`
    and not `scripts/ci/required_groups.json`, where the group's command actually lives.) A host where the
    declared runtime cannot be resolved prints a named NOT_RUN and exits non-zero, because a silently skipped
    required check is the defect this project keeps having to re-learn.
    """
    try:
        node = find_node()
    except SystemExit as unresolved:
        print(f"OBSERVER_FRONTEND_CONTRACTS_NOT_RUN {unresolved}")
        return 1
    env = env_for(node)
    print(f"CONTRACTS_NODE node={node} version="
          f"{subprocess.run([str(node), '--version'], capture_output=True, text=True, encoding='utf-8', errors='replace').stdout.strip()}")
    js_code = subprocess.run([str(node), "tests/run_all_tests.js"],
                             cwd=str(REPO / "apps" / "observer"), env=env).returncode
    vitest_code = subprocess.run([str(node), "node_modules/vitest/vitest.mjs", "run"],
                                 cwd=str(FRONTEND), env=env).returncode
    print(f"OBSERVER_JS_CONTRACTS exit={js_code}")
    print(f"OBSERVER_VITEST exit={vitest_code}")
    verdict = 0 if js_code == 0 and vitest_code == 0 else 1
    print(f"OBSERVER_FRONTEND_CONTRACTS_{'PASS' if verdict == 0 else 'FAIL'} "
          f"js={js_code} vitest={vitest_code}")
    return verdict


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="mode", required=True)
    sub.add_parser("resolve").set_defaults(func=cmd_resolve)
    sub.add_parser("install").set_defaults(func=cmd_install)
    sub.add_parser("build").set_defaults(func=cmd_build)
    sub.add_parser("contracts").set_defaults(func=cmd_contracts)
    preview = sub.add_parser("preview")
    preview.add_argument("--host", default=PREVIEW_HOST)
    preview.add_argument("--port", type=int, default=PREVIEW_PORT)
    preview.add_argument("--window", action="store_true")
    preview.set_defaults(func=cmd_preview)
    window = sub.add_parser("window")
    window.add_argument("--host", default=PREVIEW_HOST)
    window.add_argument("--port", type=int, default=PREVIEW_PORT)
    window.set_defaults(func=lambda a: cmd_preview(argparse.Namespace(host=a.host, port=a.port, window=True)))
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
