# SPDX-License-Identifier: MIT
"""``python -m backend`` — the AI-WORK-LAB unified local backend entry.

The service token is read from stdin (one line, 64 hex chars), never from argv,
files or URLs — the same handshake the migrated DESIGN-LAB launcher uses. The
server binds 127.0.0.1 only and prints one LISTENING json line, then serves.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import threading
from pathlib import Path

from backend.app import build_server


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="AI-WORK-LAB unified local backend")
    parser.add_argument("--workspace", default=str(Path(__file__).resolve().parents[1] / "workspace"),
                        help="workspace root (runtime state lives in its .project-local)")
    parser.add_argument("--port", type=int, default=0, help="loopback port (0 = pick a free one)")
    args = parser.parse_args(argv)
    if sys.stdin.isatty():
        print(json.dumps({"status": "ERROR",
                          "reason": "SERVICE_REQUIRES_LAUNCHER_STDIN"}), flush=True)
        return 2
    token = sys.stdin.readline(66).rstrip("\r\n")
    if not re.fullmatch(r"[0-9a-f]{64}", token):
        print(json.dumps({"status": "ERROR", "reason": "INVALID_SERVICE_TOKEN"}), flush=True)
        return 2
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    httpd, context = build_server(Path(args.workspace), token, args.port)
    print(json.dumps({"status": "LISTENING", "host": "127.0.0.1", "port": httpd.server_port,
                      "workspace": str(Path(args.workspace).resolve()),
                      "reconciled_attempts": len(context["reconciled"]),
                      "unified_store": str(context["unified"].path)}), flush=True)
    # Serving runs in a worker thread so this process can probe its own loopback
    # port from a separate one and record what it saw: "the HTTP surface answers"
    # becomes an observation with an exit code, not a constant in the catalog.
    serving = threading.Thread(target=httpd.serve_forever, daemon=True)
    serving.start()
    stopping = threading.Event()
    try:
        from backend.core import probes
        probes.run_http_probe(context["api"],
                              base_url="http://127.0.0.1:" + str(httpd.server_port),
                              port=httpd.server_port, token=token)
    except Exception as exc:  # noqa: BLE001 - a failed probe is recorded, never fatal
        print(json.dumps({"status": "PROBE_FAILED", "reason": type(exc).__name__}), flush=True)
    try:
        stopping.wait()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.shutdown()
        context["unified"].close()
        context["work"].close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
