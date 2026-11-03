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
import os
import re
import secrets
import shutil
import stat
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

#: F07's rule is "a project bound to a directory that really exists is live" -- the rule is about
#: existence, not about which repository happens to sit on this machine. `work_project` therefore
#: registers an in-checkout directory: the assertion stays exactly as strong, and a clone without
#: the two read-only source repositories stops failing for a reason unrelated to the behaviour
#: under test (measured: 12 of the 15 nodes that broke when the source paths were redirected).
LIVE_WORK_ROOT = TARGET_ROOT / "tests" / "fixtures" / "live-work-root"

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


#: Project-owned scratch roots. They are gitignored, so a fresh clone has none of them, and
#: several legacy tests pass ``.project-local/task-runtime`` to ``mkdtemp`` as its *parent*
#: — mkdtemp refuses a missing parent, which made the suite uncreatable on a machine that
#: had never worked in this checkout, exactly the machine the audit entry invites to clone
#: and rerun §4. Creating only directories, never files.
SCRATCH_ROOTS = (".project-local/task-runtime", ".project-local/runs", ".project-local/build")

#: The same ``mkdtemp`` calls, measured on 2026-11-03: every full-suite run left **80**
#: directories under ``task-runtime`` -- 1,040 on disk, 286 MB -- because nobody removes them.
#: Named subdirectories of that root (``penpot-import``, ``kit-register``, ``reconstruction``…)
#: are cited as evidence paths by tracked documents, so the sweep takes only ``tmp``-prefixed
#: entries that appeared during this session.
SWEEP_ROOT = ".project-local/task-runtime"
SWEEP_SUMMARY = ".project-local/runs/sandbox-sweep-latest.json"
#: ``mkdtemp`` names are ``tmp`` plus eight characters from ``[a-z0-9_]``, so the underscore has to
#: be allowed immediately after the prefix -- measured on 2026-11-03, a first sweep that let
#: ``tmp_s1j7k3i`` through because the class started with alphanumerics.
SANDBOX_NAME = re.compile(r"tmp[A-Za-z0-9_]{6,}$")


def sandboxes_created(root: Path, before: set, started_at: float | None = None) -> list:
    """The mkdtemp sandboxes that appeared in ``root`` after the snapshot ``before`` was taken.

    Two independent conditions rather than one, because the first one alone was demonstrably
    dangerous: while falsifying this fixture on 2026-11-03 a mutation that dropped the snapshot
    check ran in a live pytest session and deleted 1,041 accumulated sandboxes. The age floor is
    the backstop -- a directory that predates the session is not this session's to remove, even if
    every other condition matches.
    """
    if not root.is_dir():
        return []
    selected = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or not SANDBOX_NAME.match(path.name) or path.name in before:
            continue
        if started_at is not None and path.stat().st_mtime < started_at:
            continue
        selected.append(path)
    return selected


def _clear_read_only(func, path, exc_info):
    """Windows teardown error handler: a read-only file is the common case, not the exotic one."""
    try:
        os.chmod(path, stat.S_IWRITE)
        func(path)
    except OSError:
        raise exc_info[1]


def remove_sandboxes(paths) -> tuple:
    """Delete sandboxes; report what survived instead of failing the session over it.

    A still-open handle or a read-only file inside a sandbox must not turn a green suite into a
    collection error at teardown. The leftovers are returned by name, so a leak that came back is
    visible in the sweep summary rather than hidden by a swallowed exception.
    """
    removed, failed = 0, []
    for path in paths:
        try:
            shutil.rmtree(path, onerror=_clear_read_only)
            removed += 1
        except OSError:
            failed.append(path.name)
    return removed, failed


@pytest.fixture(scope="session", autouse=True)
def ensure_scratch_roots():
    for relative in SCRATCH_ROOTS:
        (TARGET_ROOT / relative).mkdir(parents=True, exist_ok=True)
    yield


@pytest.fixture(scope="session", autouse=True)
def sweep_test_sandboxes():
    """No sandbox outlives the session that made it, and the count is published, not assumed."""
    root = TARGET_ROOT / SWEEP_ROOT
    started_at = time.time()
    before = {path.name for path in root.iterdir()} if root.is_dir() else set()
    yield
    created = sandboxes_created(root, before, started_at)
    removed, failed = remove_sandboxes(created)
    summary = {"root": SWEEP_ROOT, "present_before_session": len(before),
               "sandboxes_created_this_session": len(created),
               "removed": removed, "left_behind": failed,
               "selection_rule": "name matches tmp<mkdtemp alphabet>, is a directory, absent from "
                                 "the snapshot taken at session start, and modified after it",
               "note": "created = leaked-and-not-cleaned by a test; named directories are never "
                       "candidates because they are cited as evidence paths"}
    destination = TARGET_ROOT / SWEEP_SUMMARY
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
                           encoding="utf-8", newline="\n")


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
    """A registered work project bound to a directory that really exists in this checkout."""
    status, project = server.client.post("/api/v1/projects", {
        "name": "work-live-root", "source": "work", "root_path": str(LIVE_WORK_ROOT)})
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
