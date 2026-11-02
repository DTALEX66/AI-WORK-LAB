# SPDX-License-Identifier: MIT
"""V17 / L12末条 / L15「失败恢复」: the running surface restarted for real.

Every other "restart readback" in this suite reopens sqlite files inside the same
pytest process (`test_v03_work_loop.py:161-175`, `test_v06_knowledge.py:87-91`). That
proves the rows are durable; it proves nothing about the code that runs when a process
actually starts. `backend/app.py:44` calls
`design_lab.service.ProjectService.reconcile_interrupted_attempts()`, which takes a
per-attempt non-blocking OS recovery lock and hands the answer to
`job_store.recover_orphaned_attempts()` (`domains/design/design_lab/runtime/job_store.py:329`).
Before this file nothing under `tests/` named either function.

So this boots `python -B -X utf8 -m backend --workspace <scratch> --port 0` twice as two
genuine child processes — token on stdin only, loopback only — and between them leaves a
RUNNING attempt in the design job store whose worker no longer exists. The three claims
are read separately:

(a) the unified facts (task, attempt, result, both technical verdicts) answer identically
    from the second process, byte for byte, on the same instance of the HTTP surface;
(b) the second boot's own LISTENING line reports the orphan (`reconciled_attempts`);
(c) the orphan lands in the documented "outcome unknown, reconcile before any retry"
    state -- `OUTCOME_UNKNOWN`, not terminal, not receipted, with the transition event
    recorded -- while a second RUNNING attempt whose recovery lock the test process
    still holds is left alone, which is the half of the rule that stops recovery from
    relabelling live work.

Nothing here runs a host, a model or a real human handoff: the loop below is the same
test-simulated declaration `test_v03_work_loop.py` records, and the recovery it measures
is the crash-recovery step, not a completed production run.
"""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import subprocess
import sys
import time
from contextlib import closing
from pathlib import Path
from types import SimpleNamespace

from tests.conftest import (Client, LIVE_WORK_ROOT, produced_after, seed_issue,
                            write_grants)
from tests.unified.test_v03_work_loop import COLLECTOR, _result_document

REPO = Path(__file__).resolve().parents[2]
LOCAL_RELATIVE = Path(".project-local") / "ai-work-lab"
BOOT_TIMEOUT_SECONDS = 120.0
REQUEST_HASH = hashlib.sha256(b"v17-restart-fixture").hexdigest()


def _boot(workspace: Path, token: str):
    """Start one real backend process and read its LISTENING line.

    The token goes in on stdin and is never written to argv, a file or a URL; the port is
    the child's own choice, reported back on the same line.
    """
    environment = dict(os.environ)
    environment.pop("PROJECT_LOCAL_ROOT", None)
    process = subprocess.Popen(
        [sys.executable, "-B", "-X", "utf8", "-m", "backend",
         "--workspace", str(workspace), "--port", "0"],
        cwd=str(REPO), stdin=subprocess.PIPE, stdout=subprocess.PIPE,
        stderr=subprocess.PIPE, text=True, encoding="utf-8", errors="replace",
        env=environment)
    seen: list[str] = []
    try:
        process.stdin.write(token + "\n")
        process.stdin.flush()
    except (BrokenPipeError, ValueError) as error:  # the child died before reading it
        pass
    deadline = time.monotonic() + BOOT_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        line = process.stdout.readline()
        if line == "":
            break
        seen.append(line.rstrip("\n"))
        try:
            payload = json.loads(line)
        except ValueError:
            continue
        if payload.get("status") == "LISTENING":
            client = Client()
            client.port = payload["port"]
            client.token = token
            assert payload["host"] == "127.0.0.1", payload
            return process, payload, client
        if payload.get("status") == "ERROR":
            break
    returncode = process.poll()
    process.terminate()
    raise AssertionError(
        "the backend process never reported LISTENING (exit %r, stdout %r)"
        % (returncode, seen))


def _stop(process: subprocess.Popen) -> int:
    """End one boot. terminate() is the closest thing this suite has to a crash: the
    process is stopped from outside, so no shutdown hook of its own runs."""
    process.terminate()
    try:
        return process.wait(timeout=30)
    except subprocess.TimeoutExpired:  # pragma: no cover - defensive
        process.kill()
        return process.wait(timeout=30)


def _run_manual_loop(client) -> dict:
    """The L13 five steps over real HTTP, so there is something to read back."""
    status, project = client.post("/api/v1/projects", {
        "name": "WORK-LAB", "source": "work", "root_path": str(LIVE_WORK_ROOT)})
    assert status == 201, project
    status, task = client.post("/api/v1/tasks", {
        "project_id": project["project_id"], "kind": "work",
        "title": "重启样例：演示采集器连续失败",
        "input_refs": [{"kind": "work_project", "project_id": project["project_id"]}],
        "acceptance": {"professional_required": False}})
    assert status == 201, task
    task_id = task["task_id"]
    status, attempt = client.post(f"/api/v1/tasks/{task_id}/attempts",
                                  {"idempotency_key": "att-restart-1"})
    assert status == 201, attempt
    attempt_id = attempt["attempt_id"]
    status, pack_response = client.post(f"/api/v1/attempts/{attempt_id}/pack", {})
    assert status == 201, pack_response
    pack_id = pack_response["pack"]["packId"]
    status, approval = client.post(f"/api/v1/attempts/{attempt_id}/approval",
                                   {"authorization_ref": "g-test-1", "expected_version": 1})
    assert status == 200, approval
    status, handoff = client.post(f"/api/v1/attempts/{attempt_id}/handoff-declarations", {
        "claim": "copiedByUser", "target_version": "work-store-v1",
        "channel": "manual-copy", "actor": "user"})
    assert status == 200, handoff
    status, imported = client.post(f"/api/v1/attempts/{attempt_id}/results", {
        "result": _result_document(pack_id, project["project_id"],
                                   produced_at=produced_after(handoff)),
        "data_origin": "test"})
    assert status == 201, imported
    result_id = imported["result"]["result_id"]
    status, failing = client.post(f"/api/v1/results/{result_id}/verifications",
                                  {"axis": "technical"})
    assert status == 201 and failing["outcome"] == "FAIL", failing
    return {"task_id": task_id, "attempt_id": attempt_id, "result_id": result_id,
            "pack_id": pack_id}


def _read_back(client, facts: dict) -> dict:
    """Everything the restart must reproduce, straight off the HTTP surface."""
    status, task = client.get("/api/v1/tasks/" + facts["task_id"])
    assert status == 200, task
    status, attempt = client.get("/api/v1/attempts/" + facts["attempt_id"])
    assert status == 200, attempt
    status, result = client.get("/api/v1/results/" + facts["result_id"])
    assert status == 200, result
    status, completion = client.get("/api/v1/tasks/" + facts["task_id"] + "/completion")
    assert status == 200, completion
    return {"task": task, "attempt": attempt, "result": result, "completion": completion}


def _seed_open_issue(workspace: Path) -> None:
    """One open SOURCE_FAILURE row, written before any backend process exists."""
    from backend.core.workpacks import WorkPacks

    work = WorkPacks(workspace / LOCAL_RELATIVE / "work-store.sqlite3", grants_path=None)
    try:
        seed_issue(work.store, name=COLLECTOR)
    finally:
        work.close()


def _mark_issue_fixed(workspace: Path) -> None:
    from backend.core.workpacks import WorkPacks

    work = WorkPacks(workspace / LOCAL_RELATIVE / "work-store.sqlite3", grants_path=None)
    try:
        seed_issue(work.store, name=COLLECTOR, failures=0)
    finally:
        work.close()


def _plant_running_attempts(workspace: Path):
    """Two RUNNING design-layer attempts, left exactly as a dead worker leaves them."""
    from design_lab.runtime import job_store
    from design_lab.service import ProjectService

    service = ProjectService(str(workspace))
    with closing(job_store.connect(service.database,
                                   project_root=service.paths.project_root)) as conn:
        created = {}
        for label in ("orphan", "live"):
            attempt = job_store.begin_attempt(
                conn, job_id="job-" + label, operation_id="op-" + label,
                idempotency_scope="v17-restart", idempotency_key=label,
                request_hash=REQUEST_HASH)
            job_store.transition(conn, attempt["attempt_id"], "RUNNING",
                                 note="worker died here" if label == "orphan"
                                 else "worker is still held")
            created[label] = attempt["attempt_id"]
    return service, created


def _attempt_state(service, label: str, attempt_id: str) -> dict:
    from design_lab.runtime import job_store

    with closing(job_store.connect(service.database,
                                   project_root=service.paths.project_root)) as conn:
        record = job_store.latest_attempt(conn, "job-" + label)
        assert record["attempt_id"] == attempt_id, record
        record["operation_state"] = job_store.operation_status(
            conn, "op-" + label)["state"]
        record["events"] = [tuple(row) for row in conn.execute(
            "SELECT from_state, to_state, detail FROM attempt_event WHERE attempt_id=?"
            " ORDER BY rowid", (attempt_id,))]
        return record


def test_backend_boots_twice_and_recovers_the_orphan(tmp_path: Path):
    from design_lab.runtime.native_recovery_lock import recovery_lock

    workspace = tmp_path / "ws"
    workspace.mkdir()
    (workspace / "AGENTS.md").write_text("# v17 restart fixture", encoding="utf-8")
    local_root = workspace / LOCAL_RELATIVE
    local_root.mkdir(parents=True)
    os.environ.pop("PROJECT_LOCAL_ROOT", None)
    _seed_open_issue(workspace)
    write_grants(SimpleNamespace(local_root=local_root))
    token = secrets.token_hex(32)

    first, first_line, first_client = _boot(workspace, token)
    try:
        assert first_line["reconciled_attempts"] == 0, (
            "a workspace that never ran a worker must not report recovery work: %r"
            % first_line)
        facts = _run_manual_loop(first_client)
        _mark_issue_fixed(workspace)
        status, passing = first_client.post(
            f"/api/v1/results/{facts['result_id']}/verifications", {"axis": "technical"})
        assert status == 201 and passing["outcome"] == "PASS", passing
        status, task_now = first_client.get("/api/v1/tasks/" + facts["task_id"])
        assert task_now["lifecycle"] == "COMPLETED", task_now
        before = _read_back(first_client, facts)
    finally:
        _stop(first)

    service, planted = _plant_running_attempts(workspace)
    with recovery_lock(service.paths, planted["live"]):
        second, second_line, second_client = _boot(workspace, token)
        try:
            # (b) the boot itself reports the orphan it found -- and only the orphan
            assert second_line["reconciled_attempts"] >= 1, (
                "the second boot reported no recovery work although a RUNNING attempt "
                "was left in the workspace: %r" % second_line)
            assert second_line["reconciled_attempts"] == 1, (
                "recovery counted the attempt whose OS recovery lock is still held, so "
                "it relabels live work: %r" % second_line)

            # (a) the same HTTP surface, a different process, the same bytes
            after = _read_back(second_client, facts)
            assert after == before, (
                "the facts changed across a real process restart: %s"
                % [key for key in before if before[key] != after[key]])
            assert after["task"]["lifecycle"] == "COMPLETED"
            assert [row["outcome"] for row in after["result"]["verifications"]] == \
                ["FAIL", "PASS"], after["result"]["verifications"]
            assert after["completion"]["supported"] is True, after["completion"]

            # (c) the orphan is "result unknown", never a silent completion
            orphan = _attempt_state(service, "orphan", planted["orphan"])
            assert orphan["state"] == "OUTCOME_UNKNOWN", orphan
            assert orphan["operation_state"] == "OUTCOME_UNKNOWN", orphan
            assert ("RUNNING", "OUTCOME_UNKNOWN",
                    "worker interrupted; reconcile before any retry") in orphan["events"], \
                orphan["events"]
            from design_lab.runtime import job_store

            assert orphan["state"] not in job_store.TERMINAL, orphan
            assert orphan["ended_at"] is None, orphan
            assert second_client.get("/api/v1/integrity")[1]["problems"] == [], (
                "recovery left the unified envelope inconsistent")

            # and the live holder is untouched, which is the other half of the rule
            live = _attempt_state(service, "live", planted["live"])
            assert live["state"] == "RUNNING", live
            assert all(event[1] != "OUTCOME_UNKNOWN" for event in live["events"]), live
        finally:
            _stop(second)

    # releasing the lock does not retroactively change what the second boot saw
    assert _attempt_state(service, "live",
                          planted["live"])["state"] == "RUNNING"
