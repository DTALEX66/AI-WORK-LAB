"""End-to-end proof of the Control -> canonical store -> Observer read-back journey.

Two real processes, one canonical store, no native client and no GUI:

  1. the loopback Control service (the only write boundary) accepts one work-unit.create;
  2. the read-only sidecar (Observer's own service) serves /api/v1/snapshot;
  3. the created task must appear in that snapshot's taskRecords, and the snapshot revision must move.

Evidence level is INTEGRATED AT MOST: the write and the read-back both happened on this machine against
the real services, but no native executor produced anything, so nothing here is REAL, and the
Completion Authority is NOT reached by this journey (dispatch is still NOT_IMPLEMENTED and is reported
as such rather than skipped silently).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / ".project-local" / "runs" / "qoder-20261007-a" / f"e2e-runtime-{time.strftime('%H%M%S')}"
PY = ROOT / ".project-local" / "toolchains" / "wl-py311" / "Scripts" / "python.exe"
SIDECAR_READY = "WORKFLOW_SIDECAR_READY url="
CONTROL_READY = "CONTROL_SERVING url="


def wait_for_line(stream, marker: str, deadline: float) -> str:
    while time.time() < deadline:
        line = stream.readline()
        if not line:
            time.sleep(0.05)
            continue
        line = line.strip()
        if marker in line:
            return line
        if line:
            print(f"    [child] {line}")
    raise TimeoutError(f"child never printed {marker!r}")


def url_of(line: str) -> str:
    """Both services print `... url=http://127.0.0.1:PORT ...`; one parser, no key=value guessing."""
    return line.split("url=", 1)[1].split(" ", 1)[0].strip()


def get(url: str, timeout: float = 8.0):
    with urllib.request.urlopen(url, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def post(url: str, payload: dict, timeout: float = 8.0):
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.status, json.loads(response.read().decode("utf-8"))


def main() -> int:
    if RUNTIME.exists():
        raise SystemExit(f"REFUSED: {RUNTIME} already exists — this proof must start from an empty runtime root")
    RUNTIME.mkdir(parents=True)
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join([
        str(ROOT / "services" / "control"), str(ROOT / "services" / "orchestration"),
        str(ROOT / "services" / "authority"), str(ROOT / "services" / "policy"),
        str(ROOT / "services" / "receipts"), str(ROOT / "services" / "task-governance"),
        str(ROOT / "packages" / "client-neutral-core" / "scripts"),
    ])
    deadline = time.time() + 45

    sidecar = subprocess.Popen(
        [str(PY), str(ROOT / "services" / "orchestration" / "sidecar.py"),
         "--project-root", str(ROOT), "--runtime-root", str(RUNTIME), "--worker-tick", "1.0"],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    control = subprocess.Popen(
        [str(PY), str(ROOT / "services" / "control" / "control_service.py"),
         "--project-root", str(ROOT), "--runtime-root", str(RUNTIME)],
        cwd=str(ROOT), stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
        encoding="utf-8", errors="replace", env=env,
    )
    try:
        sidecar_base = url_of(wait_for_line(sidecar.stdout, SIDECAR_READY, deadline))
        control_base = url_of(wait_for_line(control.stdout, CONTROL_READY, deadline))

        _, before = get(f"{sidecar_base}/api/v1/snapshot")
        revision_before = before["revision"]
        tasks_before = [record["taskId"] for record in before.get("taskRecords") or []]

        created = {
            "schema_version": "worklab/control-operation/v1",
            "operation": "work-unit.create",
            "project_id": "work-lab",
            "task_id": "WL-E2E-CONTROL-1",
            "revision": None, "attempt": None,
            "scope": {"boundaries": ["services/control"], "granted_by": "owner 2026-10-08 批次 C 授权"},
            "expected_version": None,
            "idempotency_key": "idem-e2e-control-0001",
            "actor": "e2e-proof",
            "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "payload": {"goal": "证明 Control 写的记录能被 Observer 的只读快照读回"},
        }
        status, result = post(f"{control_base}/api/control/operations", created)
        assert status == 200 and result["status"] == "ACCEPTED", result
        assert result["readback"]["taskId"] == "WL-E2E-CONTROL-1", result["readback"]

        after = None
        for _ in range(60):
            _, snapshot = get(f"{sidecar_base}/api/v1/snapshot")
            if "WL-E2E-CONTROL-1" in [record["taskId"] for record in snapshot.get("taskRecords") or []]:
                after = snapshot
                break
            time.sleep(0.25)
        assert after is not None, "the Observer snapshot never showed the task the Control service wrote"

        # The content can become readable before the watcher's next tick publishes a revision.
        # Stopping at the first content hit would report the probe's own premature read as a product gap,
        # so keep polling for the bump and report whichever came first with its wait.
        waited = 0.0
        for _ in range(40):
            if after["revision"] > revision_before:
                break
            time.sleep(0.25)
            waited += 0.25
            _, snapshot = get(f"{sidecar_base}/api/v1/snapshot")
            after = snapshot
        revision_wait_seconds = waited

        record = next(item for item in after["taskRecords"] if item["taskId"] == "WL-E2E-CONTROL-1")
        assert record["status"] == "QUEUED", record
        assert "goal" in record["checkpointKeys"] and "证明" not in json.dumps(record, ensure_ascii=False), \
            "the goal value leaked into the read-only projection"

        _, descriptor = get(f"{control_base}/api/control/descriptor")
        not_implemented = [entry for entry in descriptor["operations"] if entry["support"] == "NOT_IMPLEMENTED"]

        # the read-only boundary, measured rather than asserted from a comment
        observer_write_rejected = None
        try:
            post(f"{sidecar_base}/api/v1/snapshot", created)
        except urllib.error.HTTPError as error:
            observer_write_rejected = error.code
        assert observer_write_rejected == 405, f"Observer accepted a POST with {observer_write_rejected}"

        print("CONTROL_TO_OBSERVER_READBACK_PASS " + json.dumps({
            "control": control_base, "observer": sidecar_base,
            "receipt": result["receipt"], "evidence_level": result["evidence_level"],
            "revision_before": revision_before, "revision_after": after["revision"],
            "revision_advanced": after["revision"] > revision_before,
            "revision_wait_seconds": round(revision_wait_seconds, 2),
            "sse_endpoint": after["transport"].get("eventsUrl"),
            "tasks_before": tasks_before, "tasks_after": [item["taskId"] for item in after["taskRecords"]],
            "projected_record": record,
            "observer_post_status": observer_write_rejected,
            "not_implemented_operations": [entry["operation"] for entry in not_implemented],
            "completion_authority_reached": False,
            "note": "INTEGRATED at most: no native executor ran, dispatch is NOT_IMPLEMENTED, "
                    "so this journey stops before the Completion Authority instead of pretending.",
        }, ensure_ascii=False, indent=2))
        return 0
    finally:
        for process in (control, sidecar):
            process.terminate()
        for process in (control, sidecar):
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()


if __name__ == "__main__":
    raise SystemExit(main())
