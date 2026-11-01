"""CL-09: one real closed-loop vertical slice, plus the counter-examples that must not close it.

This is not a unit test of a helper. Every step runs the shipped surface a user would run:

* the source fact is a row in a real canonical store (a BLOCKED task), read through the live sidecar's
  `/api/v1/snapshot` and `/api/v1/repair-packs` routes over real HTTP;
* the handoff material is the route's own `handoffText`, saved to a file exactly as the browser would copy it;
* every lifecycle step is a separate `repair_state.py` PROCESS over that store (record, declare, approve,
  import-result, verify, show), so persistence is proved across process boundaries, not by an in-process
  object that could share a cache;
* the repair itself is a deterministic local tool that reads the handoff, extracts the task it names, changes
  the task through the canonical store's own writer, and emits a result document with a reference to bytes it
  actually wrote. No external AI client is invoked here; that leg is reported NOT_RUN, not simulated.

The counter-example family asks the opposite question at each step: a stale result, a duplicate submission, a
fixer's self-report with no re-read, a condition that is still being produced, and a result that arrives
after the record closed. None of them may turn the problem into "solved".
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
import threading
import unittest
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "packages" / "client-neutral-core" / "scripts",
              ROOT / "services" / "orchestration"):
    sys.path.insert(0, str(entry))

import composition_root  # noqa: E402
import project_temp  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from sidecar import WorkflowSidecar, create_server  # noqa: E402

CLI = ROOT / "packages" / "client-neutral-core" / "scripts" / "repair_state.py"
ARTIFACTS = ROOT / ".project-local" / "artifacts" / "cl09-vertical-slice"
PROJECT_ID = "work-lab"
TASK_ID = "WL-CL09-1"
TARGET_VERSION = "2026.10.23"
GRANT_ID = "G-CL09-LOCAL"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _after_handoff() -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=2)).isoformat().replace("+00:00", "Z")


def _version(stdout: str) -> int:
    matches = re.findall(r"version=(\d+)", stdout)
    if not matches:
        raise AssertionError(f"no version in CLI output:\n{stdout}")
    return int(matches[-1])


class ClosedLoopVerticalSliceTests(unittest.TestCase):
    def setUp(self) -> None:
        composition_root.clear_issues_cache()
        self.runtime = project_temp.fixture_dir(prefix="cl09-slice-")
        self.sidecar = WorkflowSidecar(ROOT, self.runtime)
        self.sidecar.store.upsert_task({
            "task_id": TASK_ID, "project_id": PROJECT_ID, "status": "BLOCKED",
            "created_at": "2026-10-23T01:00:00Z", "updated_at": "2026-10-23T02:00:00Z",
        })
        composition_root.clear_issues_cache()
        self.server = None
        self.thread = None
        self._start_server()
        self.addCleanup(self._stop_server)
        self.steps: list[dict] = []

    # -- harness -------------------------------------------------------------------------------------

    def _start_server(self) -> None:
        self.server = create_server(self.sidecar, port=0)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.base = f"http://127.0.0.1:{int(self.server.server_address[1])}"

    def _stop_server(self) -> None:
        if self.server is not None:
            self.server.shutdown()
            self.server.server_close()
            self.thread.join(timeout=2)
            self.server = None
            self.thread = None
        if self.sidecar is not None:
            self.sidecar.close()
            self.sidecar = None
        composition_root.clear_issues_cache()

    def _restart_everything(self) -> None:
        self._stop_server()
        composition_root.clear_issues_cache()
        self.sidecar = WorkflowSidecar(ROOT, self.runtime)
        self._start_server()

    def _get_json(self, path: str) -> dict:
        with urllib.request.urlopen(f"{self.base}{path}", timeout=10) as response:
            return json.loads(response.read().decode("utf-8"))

    def _cli(self, *args: str) -> subprocess.CompletedProcess:
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "packages" / "client-neutral-core" / "scripts"),
             str(ROOT / "services" / "orchestration"), env.get("PYTHONPATH", "")])
        env["PYTHONIOENCODING"] = "utf-8"
        completed = subprocess.run(
            [sys.executable, str(CLI), *args], cwd=str(ROOT), env=env,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120)
        self.steps.append({"argv": ["repair_state.py", *args], "rc": completed.returncode,
                           "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()})
        return completed

    def _assert_ok(self, completed: subprocess.CompletedProcess) -> None:
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)

    def _show(self, plan_id: str) -> dict:
        shown = self._cli("show", "--runtime-root", str(self.runtime), "--plan-id", plan_id)
        self._assert_ok(shown)
        return json.loads(shown.stdout[shown.stdout.index("{"):])

    def _begin(self) -> tuple[dict, str, Path]:
        """See the problem through the interface route, then persist it as a draft."""
        view = self._get_json("/api/v1/repair-packs")
        self.assertEqual(view["status"], "OK", view["reason"])
        pack = view["packs"][0]
        handoff_file = self.runtime / "handoff.txt"
        handoff_file.write_text(pack["handoffText"], encoding="utf-8")
        pack_file = self.runtime / f"{pack['packId']}.json"
        pack_file.write_text(json.dumps(pack, ensure_ascii=False), encoding="utf-8")
        recorded = self._cli("record", "--runtime-root", str(self.runtime),
                             "--pack-file", str(pack_file))
        self._assert_ok(recorded)
        self.assertEqual(_version(recorded.stdout), 1)
        return pack, pack["packId"], handoff_file

    def _prepare_approved(self) -> tuple[dict, str, Path, int]:
        pack, plan_id, handoff_file = self._begin()
        copied = self._cli("declare", "--runtime-root", str(self.runtime), "--plan-id", plan_id,
                           "--claim", "copiedByUser", "--channel", "clipboard",
                           "--expected-version", "1")
        self._assert_ok(copied)
        self.assertEqual(_version(copied.stdout), 2)
        declared = self._cli("declare", "--runtime-root", str(self.runtime), "--plan-id", plan_id,
                             "--claim", "userDeclaredHandoff", "--channel", "local-tool",
                             "--claimed-recipient", "cl09-local-repair",
                             "--target-version", TARGET_VERSION, "--expected-version", "2")
        self._assert_ok(declared)
        self.assertEqual(_version(declared.stdout), 3)
        grants = self.runtime / "control-trusted-grants.json"
        grants.write_text(json.dumps({"grants": [{
            "grant_id": GRANT_ID, "scope": f"work-unit:{plan_id}",
            "expires_at": "2099-01-01T00:00:00Z"}]}), encoding="utf-8")
        approved = self._cli("approve", "--runtime-root", str(self.runtime), "--plan-id", plan_id,
                             "--grant-ref", GRANT_ID, "--expected-version", "3")
        self._assert_ok(approved)
        self.assertEqual(_version(approved.stdout), 4)
        return pack, plan_id, handoff_file, 4

    def _result_document(self, plan_id: str, *, result_id: str = "R-CL09-1",
                         produced_at: str | None = None, evidence: list[str] | None = None,
                         claim: str = "SUCCEEDED") -> dict:
        return {
            "schemaVersion": "worklab/external-repair-result/v1",
            "resultId": result_id,
            "packId": plan_id,
            "projectId": PROJECT_ID,
            "targetVersion": TARGET_VERSION,
            "producedAt": produced_at or _after_handoff(),
            "producer": "cl09-local-repair",
            "claimedOutcome": claim,
            "evidenceRefs": evidence or [],
            "summary": "the blocked task was returned to RUNNING by the local repair tool",
        }

    def _import(self, plan_id: str, document: dict, version: int) -> subprocess.CompletedProcess:
        result_file = self.runtime / f"{document['resultId']}.json"
        result_file.write_text(json.dumps(document, ensure_ascii=False), encoding="utf-8")
        return self._cli("import-result", "--runtime-root", str(self.runtime), "--plan-id", plan_id,
                         "--result-file", str(result_file), "--expected-version", str(version))

    def _apply_repair(self, handoff_file: Path) -> Path:
        """The external tool's job, made deterministic: read the handoff, fix what it names."""
        tool = self.runtime / "apply_repair.py"
        tool.write_text(
            "import hashlib, json, re, sys\n"
            "from pathlib import Path\n"
            f"sys.path.insert(0, r'{ROOT / 'packages' / 'client-neutral-core' / 'scripts'}')\n"
            "from canonical_store import CanonicalStore\n"
            "runtime = Path(sys.argv[1])\n"
            "text = (runtime / 'handoff.txt').read_text(encoding='utf-8')\n"
            "match = re.search(r'tasks:([A-Za-z0-9._-]+)', text)\n"
            "assert match, 'the handoff names no task'\n"
            "task_id = match.group(1)\n"
            "store = CanonicalStore(runtime / 'canonical.sqlite')\n"
            "row = next(item for item in store.list_tasks() if item['task_id'] == task_id)\n"
            "assert row['status'] == 'BLOCKED', row['status']\n"
            "store.upsert_task({'task_id': task_id, 'project_id': row['project_id'], 'status': 'RUNNING',\n"
            "                   'created_at': row['created_at'], 'updated_at': row['updated_at'],\n"
            "                   'checkpoint': row['checkpoint'] or {}})\n"
            "store.close()\n"
            "output = runtime / 'repair-output.txt'\n"
            "output.write_text(json.dumps({'taskId': task_id, 'from': 'BLOCKED', 'to': 'RUNNING',\n"
            "                              'handoffSha256': hashlib.sha256(text.encode('utf-8')).hexdigest(),\n"
            "                              'at': '2026-10-23T05:00:00Z'}), encoding='utf-8')\n"
            "print('REPAIR_APPLIED task=' + task_id)\n",
            encoding="utf-8")
        env = os.environ.copy()
        env["PYTHONPATH"] = os.pathsep.join(
            [str(ROOT / "packages" / "client-neutral-core" / "scripts"), env.get("PYTHONPATH", "")])
        completed = subprocess.run([sys.executable, str(tool), str(self.runtime)], cwd=str(ROOT), env=env,
                                   capture_output=True, text=True, encoding="utf-8", errors="replace",
                                   timeout=60)
        self.steps.append({"argv": ["apply_repair.py", str(self.runtime)], "rc": completed.returncode,
                           "stdout": completed.stdout.strip(), "stderr": completed.stderr.strip()})
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        self.assertIn("REPAIR_APPLIED", completed.stdout)
        return self.runtime / "repair-output.txt"

    # -- the slice -----------------------------------------------------------------------------------

    def test_the_whole_loop_runs_and_survives_a_restart(self) -> None:
        snapshot = self._get_json("/api/v1/snapshot")
        issues = snapshot["issues"]
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0]["class"], "TASK_BLOCKED")
        self.assertEqual(issues[0]["evidenceRef"], f"tasks:{TASK_ID}")
        fingerprint = issues[0]["fingerprint"]

        pack, plan_id, handoff_file, version = self._prepare_approved()
        self.assertEqual(pack["target"]["kind"], "MANUAL_COPY")
        self.assertEqual(pack["binds"]["issueFingerprints"], [fingerprint])
        handoff_text = handoff_file.read_text(encoding="utf-8")
        self.assertIn(f"tasks:{TASK_ID}", handoff_text)

        repair_output = self._apply_repair(handoff_file)
        imported = self._import(plan_id, self._result_document(
            plan_id, evidence=[str(repair_output)]), version)
        self._assert_ok(imported)
        self.assertEqual(_version(imported.stdout), 5)

        verified = self._cli("verify", "--runtime-root", str(self.runtime), "--plan-id", plan_id,
                             "--expected-version", "5")
        self._assert_ok(verified)
        self.assertIn("outcome=RESOLVED", verified.stdout)
        self.assertIn("level=independent", verified.stdout)
        self.assertIn("status=SUCCEEDED", verified.stdout)

        # A new process, a new sidecar and a new store handle: the source says the problem is gone, and the
        # record still remembers how it got there.
        self._restart_everything()
        view_after = self._get_json("/api/v1/repair-packs")
        self.assertEqual(view_after["status"], "NO_OPEN_ISSUES", view_after["reason"])
        self.assertEqual(view_after["packs"], [])
        snapshot_after = self._get_json("/api/v1/snapshot")
        self.assertEqual(snapshot_after["issues"], [])
        shown = self._show(plan_id)
        self.assertEqual(shown["status"], "SUCCEEDED")
        self.assertEqual(shown["payload"]["outcome"]["status"], "SUCCEEDED")
        self.assertEqual(shown["payload"]["outcome"]["evidenceLevel"], "independent")
        self.assertEqual(shown["payload"]["verifications"][-1]["outcome"], "RESOLVED")
        self.assertFalse(shown["payload"]["verifications"][-1]["receiptAcceptedAsVerification"])
        self.assertTrue(shown["payload"]["handoffRecord"]["copiedByUser"]["declared"])
        self.assertTrue(shown["payload"]["handoffRecord"]["userDeclaredHandoff"]["declared"])
        self.assertTrue(shown["payload"]["handoffRecord"]["externalReceipt"]["received"])
        self.assertIsNone(shown["payload"].get("pendingVerification"))
        # CL-06 is a later slice: nothing here may pretend a reusable solution was saved.
        self.assertNotIn("solution", json.dumps(shown["payload"], ensure_ascii=False).lower())

        ARTIFACTS.mkdir(parents=True, exist_ok=True)
        receipt = {
            "schemaVersion": "worklab/cl09-vertical-slice/v1",
            "generatedAt": _now(),
            "runtimeRoot": str(self.runtime.relative_to(ROOT)),
            "source": {"issueClass": "TASK_BLOCKED", "fingerprint": fingerprint,
                       "evidenceRef": f"tasks:{TASK_ID}", "sourcesRead": snapshot["issuesSummary"]["sourcesRead"]},
            "pack": {"packId": plan_id, "kind": pack["target"]["kind"],
                     "handoffBytes": len(handoff_text.encode("utf-8")),
                     "handoffSha256": hashlib.sha256(handoff_text.encode("utf-8")).hexdigest(),
                     "sent": pack["handoff"]["sent"], "dispatched": pack["handoff"]["dispatched"]},
            "steps": self.steps,
            "restart": {"repairPacksStatus": view_after["status"], "snapshotIssueCount": 0,
                        "recordStatus": shown["status"],
                        "verificationOutcome": shown["payload"]["verifications"][-1]["outcome"],
                        "evidenceLevel": shown["payload"]["outcome"]["evidenceLevel"]},
            "externalAiTool": "NOT_RUN",
            "solutionLibrary": "NOT_EXECUTED (CL-06 is a later slice)",
        }
        (ARTIFACTS / "receipt.json").write_text(json.dumps(receipt, ensure_ascii=False, indent=2),
                                                encoding="utf-8")

    # -- counter-examples ----------------------------------------------------------------------------

    def test_a_stale_result_cannot_be_imported(self) -> None:
        _, plan_id, _, version = self._prepare_approved()
        stale = self._import(plan_id, self._result_document(
            plan_id, result_id="R-STALE", produced_at="2000-01-01T00:00:00Z"), version)
        self.assertEqual(stale.returncode, 1)
        self.assertIn("EXTERNAL_RESULT_STALE", stale.stdout)
        self.assertEqual(self._show(plan_id)["status"], "APPROVED")

    def test_a_second_submission_is_not_a_second_result(self) -> None:
        _, plan_id, _, version = self._prepare_approved()
        document = self._result_document(plan_id)
        first = self._import(plan_id, document, version)
        self._assert_ok(first)
        second = self._import(plan_id, document, _version(first.stdout))
        self.assertEqual(second.returncode, 1)
        self.assertIn("EXTERNAL_RESULT_DUPLICATE", second.stdout)

    def test_a_fixers_self_report_does_not_close_anything(self) -> None:
        _, plan_id, _, version = self._prepare_approved()
        imported = self._import(plan_id, self._result_document(plan_id), version)
        self._assert_ok(imported)
        shown = self._show(plan_id)
        self.assertEqual(shown["status"], "APPROVED")
        self.assertEqual(shown["payload"]["pendingVerification"]["resultId"], "R-CL09-1")
        self.assertIsNone(shown["payload"].get("outcome"))

    def test_a_condition_still_present_closes_failed_never_solved(self) -> None:
        _, plan_id, _, version = self._prepare_approved()
        imported = self._import(plan_id, self._result_document(plan_id), version)
        self._assert_ok(imported)
        verified = self._cli("verify", "--runtime-root", str(self.runtime), "--plan-id", plan_id,
                             "--expected-version", str(_version(imported.stdout)))
        self._assert_ok(verified)
        self.assertIn("outcome=UNRESOLVED", verified.stdout)
        self.assertIn("status=FAILED", verified.stdout)
        shown = self._show(plan_id)
        self.assertEqual(shown["status"], "FAILED")
        self.assertEqual(shown["payload"]["verifications"][-1]["outcome"], "UNRESOLVED")
        self.assertTrue(shown["payload"]["verifications"][-1]["fingerprintsPresent"])

    def test_a_late_result_cannot_reopen_a_closed_record(self) -> None:
        _, plan_id, handoff_file, version = self._prepare_approved()
        repair_output = self._apply_repair(handoff_file)
        imported = self._import(plan_id, self._result_document(plan_id, evidence=[str(repair_output)]),
                                version)
        self._assert_ok(imported)
        verified = self._cli("verify", "--runtime-root", str(self.runtime), "--plan-id", plan_id,
                             "--expected-version", str(_version(imported.stdout)))
        self._assert_ok(verified)
        late = self._import(plan_id, self._result_document(
            plan_id, result_id="R-LATE"), _version(verified.stdout))
        self.assertEqual(late.returncode, 1)
        self.assertIn("EXTERNAL_RESULT_RECORD_CLOSED", late.stdout)
        self.assertEqual(self._show(plan_id)["status"], "SUCCEEDED")


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
