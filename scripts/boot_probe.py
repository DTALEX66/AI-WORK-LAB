# SPDX-License-Identifier: MIT
"""Real CLI boot probe: start `python -m backend` exactly as the launcher would
(token on stdin), then probe the compatibility and unified surfaces over real
HTTP and print one json verdict. Evidence goes to stdout; the caller logs it.

Probes:
* GET /api/v1/health            (unified envelope, bearer auth required)
* GET /api/health               (migrated DESIGN-LAB compatibility surface)
* GET /api/capabilities         (migrated capability catalog, compat surface)
* GET /api/knowledge-entries/search?q= (compat search)
* GET /workbench                (migrated compatibility UI shell)
* 401 without a token on BOTH surfaces (kernel guard still applies on the
  compat surface -- asserted here, not merely narrated)
* 403 with a wrong Host on the compat surface

The check list and its expectations are module-level data (`CHECKS` /
`EXPECTED`) precisely so that this docstring cannot outrun the code again:
`tests/unified/test_v15_route_surface.py` imports them and fails if a claimed
compat-surface guard is not actually in `CHECKS`. Until that was true, the
"kernel guard on the compat surface" sentence lived only in prose while the
executed list probed 401 on `/api/v1/health` alone.

Output is written with `ensure_ascii=True`: the Windows console this script is
invoked from is cp936 and raising UnicodeEncodeError on a CJK body would hide
the verdict it exists to report.
"""
from __future__ import annotations

import http.client
import json
import os
import secrets
import subprocess
import sys
import time
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
#: venv 解释器的布局是平台的，不是机器的：Windows 是 Scripts/python.exe，POSIX 是 bin/python（审计 N05）。
PYTHON = TARGET_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

#: (name, method, path, send_token) -- the executed probe list, in order.
CHECKS = (
    ("v1_health", "GET", "/api/v1/health", True),
    ("design_compat_health", "GET", "/api/health", True),
    ("design_compat_capabilities", "GET", "/api/capabilities", True),
    ("design_compat_knowledge_search", "GET", "/api/knowledge-entries/search", True),
    ("workbench_shell", "GET", "/workbench", False),
    ("v1_health_no_token", "GET", "/api/v1/health", False),
    # The compat-surface guard this docstring has always claimed.
    ("design_compat_health_no_token", "GET", "/api/health", False),
    ("design_compat_health_wrong_host", "GET", "/api/health", True),
)

#: Every check states its own expected status. There is no implicit 200 default:
#: a new check without an entry here fails the probe instead of passing quietly.
EXPECTED = {
    "v1_health": 200,
    "design_compat_health": 200,
    "design_compat_capabilities": 200,
    "design_compat_knowledge_search": 200,
    "workbench_shell": 200,
    "v1_health_no_token": 401,
    "design_compat_health_no_token": 401,
    "design_compat_health_wrong_host": 403,
}

WRONG_HOST_CHECKS = {"design_compat_health_wrong_host"}


def probe(port: int, token: str, method: str, path: str, *, auth: bool,
          host: str | None = None) -> tuple[int, str]:
    headers = {"Host": host or f"127.0.0.1:{port}"}
    if auth:
        headers["Authorization"] = "Bearer " + token
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        return response.status, response.read(200).decode("utf-8", errors="replace")
    finally:
        connection.close()


def run_checks(port: int, token: str) -> tuple[dict, bool]:
    """Execute CHECKS verbatim and return (per-check evidence, all_as_declared)."""
    results: dict[str, dict] = {}
    ok = True
    for name, method, path, auth in CHECKS:
        expected = EXPECTED[name]
        host = None
        if name in WRONG_HOST_CHECKS:
            # A Host that is not this server's own pinned authority: the kernel
            # must refuse before it ever reaches the compat handler.
            host = f"localhost:{port}"
        status, body = probe(port, token, method, path, auth=auth, host=host)
        expected_set = expected if isinstance(expected, tuple) else (expected,)
        results[name] = {"method": method, "path": path, "auth": auth,
                         "expected": list(expected_set), "status": status,
                         "as_declared": status in expected_set, "head": body[:120]}
        ok = ok and status in expected_set
    return results, ok


def main() -> int:
    workspace = TARGET_ROOT / "workspace"
    # Initialise through the CLI itself, the way a first run on a fresh clone has to: the default
    # workspace directory is Git-excluded, so a probe that assumed it already existed could only
    # ever pass on a machine that had run the service before. `--init` writes a marker or nothing.
    initialised = subprocess.run(
        [str(PYTHON), "-X", "utf8", "-m", "backend", "--init", "--workspace", str(workspace)],
        cwd=str(TARGET_ROOT), capture_output=True, text=True, encoding="utf-8")
    try:
        workspace_init = json.loads(initialised.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        workspace_init = {"status": "ERROR", "reason": "INIT_PRINTED_NO_JSON",
                          "stdout": (initialised.stdout or "")[:200]}
    if initialised.returncode != 0:
        print(json.dumps({"verdict": "FAILED", "reason": "WORKSPACE_INIT_REFUSED",
                          "workspace_init": workspace_init}, ensure_ascii=True))
        return 1
    token = secrets.token_hex(32)
    process = subprocess.Popen(
        [str(PYTHON), "-X", "utf8", "-m", "backend", "--workspace", str(workspace), "--port", "8765"],
        cwd=str(TARGET_ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    try:
        process.stdin.write(token + "\n")
        process.stdin.flush()
        listening = None
        seen: list[str] = []
        deadline = time.time() + 30
        while time.time() < deadline:
            line = process.stdout.readline()
            if not line:
                break
            seen.append(line.rstrip()[:300])
            if '"status": "LISTENING"' in line or '"status":"LISTENING"' in line:
                listening = json.loads(line)
                break
        if listening is None:
            # the child's own last lines: a structured refusal from the CLI is the evidence of why,
            # and dropping it here would turn a clear "reason" into an unanswerable "it did not start"
            print(json.dumps({"verdict": "FAILED", "reason": "no LISTENING line",
                              "child_last_lines": seen[-4:]}, ensure_ascii=True))
            return 1
        port = listening["port"]
        results, ok = run_checks(port, token)
        print(json.dumps({"verdict": "OK" if ok else "FAILED",
                          "listening": listening,
                          "workspace_init": workspace_init,
                          "checks": len(CHECKS),
                          "probes": results},
                         ensure_ascii=True, indent=2))
        return 0 if ok else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    sys.exit(main())
