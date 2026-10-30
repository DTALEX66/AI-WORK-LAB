# SPDX-License-Identifier: MIT
"""Pytest fixtures for the AI-WORK-LAB unified backend tests.

Runs the real loopback server (migrated kernel + /api/v1 delegate) against a
per-test temp workspace, and drives it over real HTTP with kernel-grade
headers (Host pinning + bearer token), so every assertion is about behavior of
the actual service, not of an imported function.

The client transport is pinned: the connection target is the literal loopback
host 127.0.0.1 and this client's own server port; only the request path varies
and it must be a slash-led relative path on that fixed origin.
"""
from __future__ import annotations

import http.client
import json
import secrets
import sys
import threading
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[1]
for entry in (str(TARGET_ROOT), str(TARGET_ROOT / "domains" / "design")):
    if entry not in sys.path:
        sys.path.insert(0, entry)

from backend.app import build_server  # noqa: E402

WORK_SOURCE_ROOT = Path(r"D:\All projects\WORK-LAB")

_DEFAULT = object()


class Client:
    def request(self, method: str, path: str, body: dict | None = None, *,
                host: str | None = None, token=_DEFAULT):
        target = str(path)
        if not target.startswith("/"):
            raise ValueError("request path must be relative to the pinned origin")
        headers = {"Host": host or "127.0.0.1:" + str(self.port)}
        if token is _DEFAULT:
            token = self.token
        if token is not None:
            headers["Authorization"] = "Bearer " + token
        payload = None
        if body is not None:
            payload = json.dumps(body, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        connection = http.client.HTTPConnection("127.0.0.1", self.port, timeout=10)
        try:
            connection.request(method, target, body=payload, headers=headers)
            response = connection.getresponse()
            text = response.read().decode("utf-8")
            try:
                return response.status, json.loads(text)
            except json.JSONDecodeError:
                return response.status, {"raw": text}
        finally:
            connection.close()

    def get(self, path: str, **kwargs):
        return self.request("GET", path, **kwargs)

    def post(self, path: str, body: dict | None = None, **kwargs):
        return self.request("POST", path, body, **kwargs)


@pytest.fixture()
def server(tmp_path: Path):
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text("# unified backend test workspace", encoding="utf-8")
    token = secrets.token_hex(32)
    httpd, context = build_server(workspace, token, 0)
    client = Client()
    client.port = httpd.server_port
    client.token = token
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.2)
    yield SimpleNamespace(
        client=client,
        port=httpd.server_port,
        token=token,
        workspace=workspace,
        unified=context["unified"],
        work=context["work"],
        design_service=context["service"],
        local_root=context["local_root"],
        api=context["api"],
        qualifications=context["api"].qualifications,
        approvals=context["api"].approvals,
    )
    httpd.shutdown()
    context["unified"].close()
    context["work"].close()


@pytest.fixture()
def work_project(server):
    """A registered work project whose root is the real WORK-LAB checkout (read-only probe)."""
    status, project = server.client.post("/api/v1/projects", {
        "name": "WORK-LAB", "source": "work", "root_path": str(WORK_SOURCE_ROOT)})
    assert status == 201, project
    return project


def seed_issue(work_store, name: str = "demo-collector", failures: int = 2) -> None:
    """Seed one open SOURCE_FAILURE issue through the migrated canonical store."""
    work_store.upsert_collector_health({
        "name": name,
        "consecutiveFailures": failures,
        "totalRuns": failures + 1,
        "lastRunAt": "2026-10-30T08:00:00Z",
    })


def write_grants(server, scope: str = "*"):
    grants_path = server.local_root / "trusted-grants.json"
    grants_path.write_text(json.dumps({
        "grants": [{"grant_id": "g-test-1", "scope": scope,
                    "note": "test fixture authorization; not a production grant"}]
    }, ensure_ascii=False), encoding="utf-8")


def declared_at(handoff_response: dict) -> str:
    """The server's own handoff instant, as the migrated staleness rule reads it."""
    return handoff_response["attempt"]["handoff"]["declared_at"]


def produced_after(handoff_response: dict, *, seconds: int = 5) -> str:
    """An instant after the handoff was declared — what a real executor produces.

    A result document must not predate the handoff it answers, so fixtures derive
    their ``producedAt`` from the server's own declaration instant. Hard-coding a
    wall-clock date here made the suite fail the moment the clock passed it: on
    2026-10-30 three tests went red with ``EXTERNAL_RESULT_STALE`` for no change
    in any code, and the audit ran them before that instant. Deriving keeps the
    rule strict and the suite stable.
    """
    from datetime import datetime, timedelta

    moment = datetime.fromisoformat(declared_at(handoff_response).replace("Z", "+00:00"))
    return (moment + timedelta(seconds=seconds)).isoformat().replace("+00:00", "Z")
