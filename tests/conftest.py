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
#: pytest's own per-test directories under ``--basetemp`` are named ``test_<node>0``; nobody
#: removed them, and one full-suite run left 1,649 of them behind (120.69 MiB, measured
#: 2026-11-04). ``SWEEP_ROOT`` never saw them, so the leak survived the sweep that fixed the others.
BASETEMP_NAME = re.compile(r"^test_.+\d+$")
#: a ``--basetemp`` root is swept only inside this project's scratch, and never when it IS one of
#: the shared evidence roots -- those hold named directories later rounds cite as evidence paths.
NOT_A_SWEEP_ROOT = (".project-local/runs", ".project-local/build", ".project-local/audit")
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


def basetemp_root(config) -> Path | None:
    """The session's ``--basetemp`` directory, when it is this project's own scratch to clean.

    ``None`` means "do not sweep": no root given, or a root outside ``.project-local`` (which may
    belong to a person's temp dir or another checkout), or one of the shared roots that carry
    named evidence directories.
    """
    raw = getattr(getattr(config, "option", None), "basetemp", None)
    if not raw:
        return None
    path = Path(str(raw)).resolve()
    if not path.is_relative_to((TARGET_ROOT / ".project-local").resolve()):
        return None
    if any(path == (TARGET_ROOT / relative).resolve() for relative in NOT_A_SWEEP_ROOT):
        return None
    return path


def basetemp_leftovers(root: Path, before: set, started_at: float | None = None) -> list:
    """The ``test_*<n>`` directories this session created under a ``--basetemp`` root.

    Same four independent conditions as :func:`sandboxes_created` -- name shape, is a directory,
    absent from the session-start snapshot, modified after it -- because the failure mode that
    made those conditions necessary (a mutation that dropped the snapshot check deleted 1,041
    directories in a live session) applies with equal force one level down.
    """
    if not root.is_dir():
        return []
    selected = []
    for path in sorted(root.iterdir()):
        if not path.is_dir() or not BASETEMP_NAME.match(path.name) or path.name in before:
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
def sweep_test_sandboxes(pytestconfig):
    """No sandbox outlives the session that made it, and the count is published, not assumed."""
    root = TARGET_ROOT / SWEEP_ROOT
    started_at = time.time()
    before = {path.name for path in root.iterdir()} if root.is_dir() else set()
    temp_root = basetemp_root(pytestconfig)
    temp_before = ({path.name for path in temp_root.iterdir()}
                   if temp_root is not None and temp_root.is_dir() else set())
    yield
    created = sandboxes_created(root, before, started_at)
    removed, failed = remove_sandboxes(created)
    summary = {"root": SWEEP_ROOT, "present_before_session": len(before),
               "sandboxes_created_this_session": len(created),
               "removed": removed, "left_behind": failed,
               "selection_rule": "name matches tmp<mkdtemp alphabet>, is a directory, absent from "
                                 "the snapshot taken at session start, and modified after it",
               "note": "created = leaked-and-not-cleaned by a test; named directories are never "
                       "candidates because they are cited as evidence paths",
               "roots": [{"root": SWEEP_ROOT, "created": len(created), "removed": removed,
                          "left_behind": failed}]}
    if temp_root is not None:
        made = basetemp_leftovers(temp_root, temp_before, started_at)
        temp_removed, temp_failed = remove_sandboxes(made)
        summary["basetemp"] = {"root": str(temp_root.relative_to(TARGET_ROOT)),
                               "present_before_session": len(temp_before),
                               "directories_created_this_session": len(made),
                               "removed": temp_removed, "left_behind": temp_failed,
                               "selection_rule": "name matches test_<node><digits>, is a directory, "
                                                 "absent from the session-start snapshot, and "
                                                 "modified after it"}
        summary["roots"].append({"root": summary["basetemp"]["root"], "created": len(made),
                                 "removed": temp_removed, "left_behind": temp_failed})
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
