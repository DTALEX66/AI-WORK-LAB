#!/usr/bin/env python3
"""RETIRED entry — WORK-LAB Observer standalone live server.

Retirement record (NF-09, 2026-09-13):
- Old capability: ad-hoc standalone HTTP server on :61867 serving the web
  frontend plus /api/v1/* endpoints (snapshot/tokens/dagu/agents/events).
- Why retired:
  1. It imported the deleted ``tokentelemetry`` package
     (``backend.collectors.dagu_collector``) and cannot even start
     (ModuleNotFoundError at import time).
  2. It fabricated truth: hardcoded git SHA "221083e" + matchState MATCH,
     transport LIVE/fresh with eventStreamConnected=True while
     /api/v1/events was a stub — exactly the A05 fake-state defect.
  3. It read the user's private Hermes state.db and ~/.dagu by default
     (A06: private-DB default dependency).
  4. Zero consumers: no test, no web asset, no Tauri path, and no CI job
     references this file; the production chain is the Workflow-owned
     loopback sidecar + the read-only React frontend (apps/observer/frontend,
     schema workflow/snapshot/v3) per apps/observer/README.md.
- New location of the capability: services/orchestration/sidecar.py
  (canonical /api/v1/snapshot + /api/v1/events SSE) with the frontend in
  apps/observer/frontend; read-only dashboard entry documented in the README.
- Data impact: none — this server never owned durable state.
- Recovery: `git revert` this file's retirement commit restores the old
  implementation verbatim.

This stub intentionally fails closed with exit code 2 so no wrapper or
shortcut can silently present it as a working entry.
"""
import sys

REASON = (
    "observer_live_server.py is RETIRED. The canonical read-only Observer "
    "stack is: python services/orchestration/sidecar.py --project-root . "
    "--runtime-root .project-local/runs/workflow (serves "
    "http://127.0.0.1:61867/api/v1/snapshot + /api/v1/events) with the "
    "static frontend in apps/observer/frontend. See apps/observer/README.md."
)


def main() -> int:
    print(f"RETIRED: {REASON}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
