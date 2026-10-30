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
* 401 without a token (kernel guard still applies on the compat surface)
"""
from __future__ import annotations

import http.client
import json
import secrets
import subprocess
import sys
import threading
import time
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
PYTHON = TARGET_ROOT / ".venv" / "Scripts" / "python.exe"


def probe(port: int, token: str, method: str, path: str, *, auth: bool) -> tuple[int, str]:
    headers = {"Host": f"127.0.0.1:{port}"}
    if auth:
        headers["Authorization"] = "Bearer " + token
    connection = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    try:
        connection.request(method, path, headers=headers)
        response = connection.getresponse()
        return response.status, response.read(200).decode("utf-8", errors="replace")
    finally:
        connection.close()


def main() -> int:
    workspace = TARGET_ROOT / "workspace"
    token = secrets.token_hex(32)
    process = subprocess.Popen(
        [str(PYTHON), "-X", "utf8", "-m", "backend", "--workspace", str(workspace), "--port", "8765"],
        cwd=str(TARGET_ROOT), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT, text=True, encoding="utf-8")
    try:
        process.stdin.write(token + "\n")
        process.stdin.flush()
        listening = None
        deadline = time.time() + 30
        while time.time() < deadline:
            line = process.stdout.readline()
            if not line:
                break
            if '"status": "LISTENING"' in line or '"status":"LISTENING"' in line:
                listening = json.loads(line)
                break
        if listening is None:
            print(json.dumps({"verdict": "FAILED", "reason": "no LISTENING line"}))
            return 1
        port = listening["port"]
        results = {}
        checks = [
            ("v1_health", "GET", "/api/v1/health", True),
            ("design_compat_health", "GET", "/api/health", True),
            ("design_compat_capabilities", "GET", "/api/capabilities", True),
            ("design_compat_knowledge_search", "GET", "/api/knowledge-entries/search", True),
            ("workbench_shell", "GET", "/workbench", False),
            ("v1_health_no_token", "GET", "/api/v1/health", False),
        ]
        ok = True
        for name, method, path, auth in checks:
            status, body = probe(port, token, method, path, auth=auth)
            results[name] = {"status": status, "head": body[:120]}
            expected = {"v1_health_no_token": 401}.get(name, 200)
            ok = ok and status == expected
        print(json.dumps({"verdict": "OK" if ok else "FAILED",
                          "listening": listening, "probes": results},
                         ensure_ascii=False, indent=2))
        return 0 if ok else 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()


if __name__ == "__main__":
    sys.exit(main())
