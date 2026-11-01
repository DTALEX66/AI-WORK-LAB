# SPDX-License-Identifier: MIT
"""W14 runtime sampling driver: real loopback service + pinned Chromium.

Mirrors the proven harness in design-lab/tests/test_workbench_design_layer_e2e.py:
the service is started HERE (Python) and the browser script is spawned as a child.
Node spawning Python with piped stdio is blocked in this environment, so the
direction matters -- Python -> Node, not the reverse.

Samples what the pack asks to sample FIRST (W14: "先采样现状", i.e. take a baseline
before setting any performance claim):
  - local first-interactive time
  - hot-route interaction latency (P50/P95) across the 12 routes
  - 1920x1080 / 2560x1440 at 100/125/150/200% scale: horizontal overflow + off-screen
    elements (clipped-by-scroll ancestors excluded, decoration/closures whitelisted)

Read-only with respect to the product: it connects as a client and navigates. The only
writes are into the gitignored .project-local/ evidence root.
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

# parents: [0]=external-recovery-2026-09-27 [1]=task-artifacts [2]=.project-local [3]=repo
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
NODE_SCRIPT = Path(os.environ.get("W14_NODE_SCRIPT", HERE / "w14-sampling.mjs"))
OUT = ROOT / ".project-local" / "task-artifacts" / "designlab-followup-taskpack-20260928" / "W14-RUNTIME-SAMPLING.json"
BROWSER = Path("D:/All projects/OS External Configuration/toolchains/playwright/chromium-1228/chrome-win64/chrome.exe")


def find_node_modules() -> str | None:
    for cand in (ROOT / "apps" / "workbench" / "node_modules",
                 ROOT / "node_modules",
                 ROOT / ".project-local" / "task-runtime" / "playwright"):
        if (cand / "playwright").exists() or (cand / ".pnpm").exists():
            return str(cand)
    return None


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("W14_SAMPLING=NO_NODE node not on PATH")
        return 2
    if not NODE_SCRIPT.is_file():
        print(f"W14_SAMPLING=NO_SCRIPT {NODE_SCRIPT}")
        return 2
    nm = find_node_modules()
    if not nm:
        print("W14_SAMPLING=NO_PLAYWRIGHT no in-repo playwright npm cache found")
        return 2
    if not BROWSER.exists():
        print(f"W14_SAMPLING=NO_BROWSER {BROWSER}")
        return 2

    sys.path.insert(0, str(ROOT / "src"))
    from design_lab.service import ProjectService
    from design_lab.http_service import make_server

    parent = ROOT / ".project-local" / "task-runtime" / "w14-sampling"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text("# synthetic w14 sampling project\n", encoding="utf-8")
        token = secrets.token_hex(32)
        with patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(root / ".project-local")}):
            service = ProjectService(str(root))
            server = make_server(service, token, port=0)
            port = server.server_address[1]
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                env = {
                    **os.environ,
                    "W14_SERVICE_URL": f"http://127.0.0.1:{port}",
                    "W14_TOKEN": token,
                    "W14_BROWSER": str(BROWSER),
                    "W14_OUT": str(OUT),
                }
                proc = subprocess.run([node, str(NODE_SCRIPT)], env=env, capture_output=True,
                                      text=True, encoding="utf-8", errors="replace",
                                      timeout=900, cwd=str(ROOT))
            finally:
                server.shutdown()
                worker.join()
                server.server_close()

    print(proc.stdout)
    if proc.stderr.strip():
        print("--- stderr ---")
        print(proc.stderr)
    if proc.returncode != 0:
        print(f"W14_SAMPLING=FAIL exit={proc.returncode}")
        return 1
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    print(f"W14_SAMPLING=OK routes={len(payload.get('hot_route', {}))} "
          f"matrix={len(payload.get('viewport_scale_matrix', []))} "
          f"first_interactive_ms={payload.get('first_interactive_ms')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
