# SPDX-License-Identifier: MIT
"""Actual filesystem and HTTP controls for an unopenable design-project store."""
from __future__ import annotations

import csv
import io
import json
import os
from pathlib import Path
import secrets
import sqlite3
import subprocess
import sys
import tempfile
import threading
from contextlib import closing, contextmanager

import pytest

from design_lab.http_service import make_server
from design_lab.service import ProjectService
from tests.conftest import Client, TARGET_ROOT, remove_sandboxes


def _extended(path: Path) -> str:
    return "\\\\?\\" + str(path) if os.name == "nt" else str(path)


@contextmanager
def _project(*, deep: bool):
    local = TARGET_ROOT / ".project-local"
    local.mkdir(exist_ok=True)
    sandbox = Path(tempfile.mkdtemp(prefix="store-path-", dir=local))
    try:
        root = sandbox / "project"
        if deep:
            # Keep mkdir below Windows' shorter directory limit while the selected
            # database name crosses MAX_PATH. The store and HTTP are both real.
            while len(str(root)) < 205:
                remaining = 205 - len(str(root)) - 1
                if remaining <= 0:
                    break
                root /= "x" * min(remaining, 48)
        root.mkdir(parents=True)
        (root / "AGENTS.md").write_text("# isolated test project\n", encoding="utf-8")
        service = ProjectService(root)
        if deep:
            service.database = service.database.with_name("state-" + "x" * 28 + ".db")
        os.makedirs(_extended(service.database.parent))
        yield service
    finally:
        removed, failed = remove_sandboxes([sandbox])
        assert removed == 1 and not failed, failed


@contextmanager
def _deny_new_files(directory: Path):
    """Remove and then restore write access on this test's own directory."""
    if os.name == "nt":
        result = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                                capture_output=True, text=True, check=True)
        sid = next(csv.reader(io.StringIO(result.stdout)))[1]
        result = subprocess.run(["icacls", _extended(directory), "/deny",
                                 "*" + sid + ":(WD,AD)"], capture_output=True)
        assert result.returncode == 0, "could not set the test directory ACL"
        try:
            yield
        finally:
            restored = subprocess.run(["icacls", _extended(directory), "/remove:d",
                                       "*" + sid], capture_output=True)
            assert restored.returncode == 0, "could not restore the test directory ACL"
    else:
        old_mode = directory.stat().st_mode
        directory.chmod(0o555)
        try:
            yield
        finally:
            directory.chmod(old_mode)


def _assert_real_write_denial(directory: Path):
    marker = Path(_extended(directory)) / "permission-probe"
    try:
        with marker.open("xb"):
            pass
    except PermissionError:
        return
    marker.unlink()
    pytest.fail("test prerequisite unmet: this process can write to the denied directory")


@contextmanager
def _client(service):
    token = secrets.token_hex(32)
    httpd = make_server(service, token)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    client = Client()
    client.port, client.token = httpd.server_port, token
    try:
        yield client
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _sqlite_refuses(path):
    with pytest.raises(sqlite3.OperationalError) as captured:
        sqlite3.connect(str(path)).close()
    assert captured.value.sqlite_errorcode & 0xff == sqlite3.SQLITE_CANTOPEN


def test_deep_windows_store_open_reports_path_failure_over_http():
    with _project(deep=True) as service:
        db = service.database
        if os.name != "nt":
            # On systems that support the path, long alone is not a failure.
            with _client(service) as client:
                status, body = client.post("/api/projects", {"name": "path control"})
            assert status == 201, body
            return
        assert len(str(db.parent)) < 248 and len(str(db)) >= 260
        try:
            os.stat(str(db))
        except OSError as ordinary:
            try:
                os.stat(_extended(db))
            except OSError as extended:
                inaccessible = ordinary.winerror == 3 and extended.winerror == 2
            else:
                inaccessible = ordinary.winerror == 3
        else:
            inaccessible = False
        if not inaccessible:
            # A machine configured for long paths must not be mislabeled.
            with _client(service) as client:
                status, body = client.post("/api/projects", {"name": "path control"})
            assert status == 201, body
            return
        _sqlite_refuses(db)
        with _client(service) as client:
            status, body = client.post("/api/projects", {"name": "path control"})
        assert (status, body) == (503, {"error": "PROJECT_PATH_TOO_LONG"})


def test_short_unwritable_store_stays_unavailable_over_http():
    with _project(deep=False) as service:
        assert len(str(service.database)) < 260
        with _deny_new_files(service.database.parent):
            _assert_real_write_denial(service.database.parent)
            _sqlite_refuses(service.database)
            with _client(service) as client:
                status, body = client.post("/api/projects", {"name": "permission control"})
            assert (status, body) == (503, {"error": "PROJECT_STORE_UNAVAILABLE"})


def test_deep_unwritable_store_does_not_claim_path_is_only_problem():
    with _project(deep=True) as service:
        with _deny_new_files(service.database.parent):
            _assert_real_write_denial(service.database.parent)
            _sqlite_refuses(_extended(service.database))
            with _client(service) as client:
                status, body = client.post("/api/projects", {"name": "two failure causes"})
            assert (status, body) == (503, {"error": "PROJECT_STORE_UNAVAILABLE"})


@pytest.mark.parametrize("name", ["asset", "job", "state", "creative"])
def test_each_shared_store_opener_retains_the_proven_path_failure(name):
    from design_lab.creative import store as creative_store
    from design_lab.runtime import asset_store, job_store, sqlite_open, state_store

    openers = {"asset": asset_store.connect, "job": job_store.connect,
               "state": state_store.init_db, "creative": creative_store.connect}
    with _project(deep=True) as service:
        if os.name == "nt" and not service.database.exists():
            _sqlite_refuses(service.database)
            with pytest.raises(sqlite_open.ProjectStorePathTooLong):
                openers[name](service.database, project_root=service.paths.project_root)
        else:
            openers[name](service.database, project_root=service.paths.project_root).close()


def test_existing_deep_database_is_not_reported_as_an_empty_project_list():
    with _project(deep=True) as service:
        with closing(sqlite3.connect(_extended(service.database))) as conn:
            conn.execute("CREATE TABLE project(project_id, display_name, created_at)")
            conn.execute("INSERT INTO project VALUES ('p', 'existing project', 'today')")
            conn.commit()
        with _client(service) as client:
            status, body = client.get("/api/projects")
        if os.name == "nt" and not service.database.exists():
            assert (status, body) == (503, {"error": "PROJECT_PATH_TOO_LONG"})
        else:
            assert status == 200 and body["projects"][0]["id"] == "p", body


def test_existing_deep_database_is_not_reported_as_a_missing_audit_journal():
    from design_lab.runtime import audit_trail, sqlite_open

    with _project(deep=True) as service:
        with closing(sqlite3.connect(_extended(service.database))) as conn:
            conn.execute("CREATE TABLE audit_event(audit_id, actor, action, at)")
            conn.execute("INSERT INTO audit_event VALUES ('a', 'attempt', 'writer_takeover', 'today')")
            conn.commit()
        if os.name == "nt" and not service.database.exists():
            with pytest.raises(sqlite_open.ProjectStorePathTooLong):
                audit_trail.recent(service)
        else:
            assert audit_trail.recent(service)["status"] == "PRESENT"


def test_backend_startup_names_an_existing_unreachable_long_store():
    """The real launcher must name the storage error before serving, not traceback."""
    local = TARGET_ROOT / ".project-local"
    sandbox = Path(tempfile.mkdtemp(prefix="store-launch-", dir=local))
    try:
        workspace = sandbox / "workspace"
        while len(str(workspace)) < 216:
            remaining = 216 - len(str(workspace)) - 1
            if remaining <= 0:
                break
            workspace /= "x" * min(remaining, 48)
        workspace.mkdir(parents=True)
        (workspace / "AGENTS.md").write_text("# isolated workspace\n", encoding="utf-8")
        database = workspace / ".project-local/task-runtime/service/state.db"
        os.makedirs(_extended(database.parent))
        with closing(sqlite3.connect(_extended(database))):
            pass
        if os.name == "nt" and not database.exists():
            assert os.path.exists(_extended(database))
            result = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", "-m", "backend", "--workspace",
                 str(workspace), "--port", "0"], cwd=TARGET_ROOT, input="a" * 64 + "\n",
                capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=15)
            assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
            assert json.loads(result.stdout)["reason"] == "PROJECT_PATH_TOO_LONG"
            assert "Traceback" not in result.stderr
        else:
            # On a host that reaches this path, the same empty store can be recovered.
            assert ProjectService(workspace).reconcile_interrupted_attempts() == []
    finally:
        removed, failed = remove_sandboxes([sandbox])
        assert removed == 1 and not failed, failed


def test_backend_startup_names_an_unwritable_short_store():
    """An actual permission failure must not be labeled as a long path."""
    with _project(deep=False) as service:
        with closing(sqlite3.connect(str(service.database))):
            pass
        with _deny_new_files(service.database.parent):
            _assert_real_write_denial(service.database.parent)
            result = subprocess.run(
                [sys.executable, "-B", "-X", "utf8", "-m", "backend", "--workspace",
                 str(service.paths.project_root), "--port", "0"], cwd=TARGET_ROOT,
                input="a" * 64 + "\n", capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=15)
            assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
            assert json.loads(result.stdout)["reason"] == "PROJECT_STORE_UNAVAILABLE"
            assert "Traceback" not in result.stderr


@contextmanager
def _deny_store_file_data(database: Path):
    """Deny data access without denying permission to restore the test ACL."""
    if os.name == "nt":
        who = subprocess.run(["whoami", "/user", "/fo", "csv", "/nh"],
                             capture_output=True, text=True, check=True)
        sid = next(csv.reader(io.StringIO(who.stdout)))[1]
        denied = subprocess.run(["icacls", str(database), "/deny", "*" + sid + ":(RD,WD,AD)"],
                                capture_output=True)
        assert denied.returncode == 0, "could not deny test database data access"
        try:
            yield
        finally:
            restored = subprocess.run(["icacls", str(database), "/remove:d", "*" + sid],
                                      capture_output=True)
            assert restored.returncode == 0, "could not restore test database ACL"
    else:
        mode = database.stat().st_mode
        database.chmod(0)
        try:
            yield
        finally:
            database.chmod(mode)


def _launch_backend(workspace: Path):
    return subprocess.run([sys.executable, "-B", "-X", "utf8", "-m", "backend",
                           "--workspace", str(workspace), "--port", "0"], cwd=TARGET_ROOT,
                          input="a" * 64 + "\n", capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=15)


def test_backend_startup_names_an_unwritable_unified_store(tmp_path):
    workspace = tmp_path / "workspace"
    directory = workspace / ".project-local/ai-work-lab"
    directory.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("# isolated workspace\n", encoding="utf-8")
    with _deny_new_files(directory):
        _assert_real_write_denial(directory)
        result = _launch_backend(workspace)
        assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
        response = json.loads(result.stdout)
        assert response["reason"] == "PROJECT_STORE_UNAVAILABLE"
        assert "unified" in response["policy_detail"]
        assert "Traceback" not in result.stderr


def test_backend_startup_closes_unified_when_the_work_store_is_unavailable(tmp_path, monkeypatch):
    from backend import app
    from backend.workspace import WorkspaceRefused

    workspace = tmp_path / "workspace"
    directory = workspace / ".project-local/ai-work-lab"
    directory.mkdir(parents=True)
    (workspace / "AGENTS.md").write_text("# isolated workspace\n", encoding="utf-8")
    database = directory / "work-store.sqlite3"
    sqlite3.connect(database).close()
    opened = []
    real_store = app.UnifiedStore

    class ObservedUnifiedStore(real_store):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            opened.append(self)

    monkeypatch.setattr(app, "UnifiedStore", ObservedUnifiedStore)
    try:
        with _deny_store_file_data(database):
            with pytest.raises(sqlite3.OperationalError):
                sqlite3.connect(database).close()
            result = _launch_backend(workspace)
            assert result.returncode == 2, (result.returncode, result.stdout, result.stderr)
            response = json.loads(result.stdout)
            assert response["reason"] == "PROJECT_STORE_UNAVAILABLE"
            assert "WORK" in response["policy_detail"]
            assert "Traceback" not in result.stderr
            with pytest.raises(WorkspaceRefused) as refused:
                app.build_workspace(workspace)
            assert refused.value.reason == "PROJECT_STORE_UNAVAILABLE"
            assert len(opened) == 1
            with pytest.raises(sqlite3.ProgrammingError):
                opened[0].conn.execute("SELECT 1")
    finally:
        for store in opened:
            store.close()
