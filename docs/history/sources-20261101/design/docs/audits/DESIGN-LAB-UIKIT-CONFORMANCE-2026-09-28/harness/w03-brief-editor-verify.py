# SPDX-License-Identifier: MIT
"""W03 driver: verify the real Brief flow in the route shell against the real service.

Same proven direction as the repo E2E and the W14 sampler: the service is started HERE
(Python) and the browser script is spawned as a child.

Checks exactly W03's acceptance lines:
  1. 从项目卡进入真实Brief并保存读回   -> create a brief from /projects/:id, save, read back
  2. 刷新保留项目上下文                 -> reload keeps the project context and the briefs
  3. 失败不弹「保存成功」               -> a STALE_REVISION write shows the error, never success
  4. 无假KPI                            -> an empty project shows honest zeros, no invented numbers
"""
from __future__ import annotations

import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import threading
from pathlib import Path
from unittest.mock import patch

# [0]=external-recovery-2026-09-27 [1]=task-artifacts [2]=.project-local [3]=repo
ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
NODE_SCRIPT = Path(os.environ.get("W03_NODE_SCRIPT", HERE / "w03-brief-editor.mjs"))
# Honoured from the environment: this driver is shared by several W03 harnesses, and the
# first version hard-coded OUT, so a caller's W03_OUT was silently ignored -- the triage
# evidence was written over round 12's file and the path the caller expected ended up as a
# ZERO-BYTE file, which then failed the repo's JSON scan with "invalid JSON: char 0".
_DEFAULT_OUT = ROOT / ".project-local" / "task-artifacts" / "designlab-followup-taskpack-20260928" / "W03-BRIEF-EDITOR.json"
OUT = Path(os.environ["W03_OUT"]) if os.environ.get("W03_OUT") else _DEFAULT_OUT
BROWSER = Path("D:/All projects/OS External Configuration/toolchains/playwright/chromium-1228/chrome-win64/chrome.exe")


def main() -> int:
    node = shutil.which("node")
    if not node:
        print("W03_BRIEF=NO_NODE")
        return 2
    if not NODE_SCRIPT.is_file():
        print(f"W03_BRIEF=NO_SCRIPT {NODE_SCRIPT}")
        return 2
    if not BROWSER.exists():
        print(f"W03_BRIEF=NO_BROWSER {BROWSER}")
        return 2

    sys.path.insert(0, str(ROOT / "src"))
    from design_lab.service import ProjectService
    from design_lab.http_service import make_server

    parent = ROOT / ".project-local" / "task-runtime" / "w03-brief"
    parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=parent) as tmp:
        root = Path(tmp)
        (root / "AGENTS.md").write_text("# synthetic w03 brief project\n", encoding="utf-8")
        token = secrets.token_hex(32)
        with patch.dict(os.environ, {"PROJECT_LOCAL_ROOT": str(root / ".project-local")}):
            service = ProjectService(str(root))
            server = make_server(service, token, port=0)
            port = server.server_address[1]
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                env = {
                    **os.environ,
                    "W03_SERVICE_URL": f"http://127.0.0.1:{port}",
                    "W03_TOKEN": token,
                    "W03_BROWSER": str(BROWSER),
                    "W03_OUT": str(OUT),
                }
                proc = subprocess.run([node, str(NODE_SCRIPT)], env=env, capture_output=True,
                                      text=True, encoding="utf-8", errors="replace",
                                      timeout=600, cwd=str(ROOT))
            finally:
                server.shutdown()
                worker.join()
                server.server_close()

    print(proc.stdout)
    if proc.stderr.strip():
        print("--- stderr ---")
        print(proc.stderr)

    # VOCAB cross-check: the UI's triage sets must match the AUTHORITY (job_store.py).
    # This is checked from Python rather than exercised with real FAILED tasks, because
    # reaching FAILED/OUTCOME_UNKNOWN needs a dispatched host. The guard means the UI
    # cannot silently drift from the state machine it claims to follow.
    sys.path.insert(0, str(ROOT / "src"))
    from design_lab.runtime.job_store import ALLOWED, TERMINAL
    import re
    shell = (ROOT / "apps" / "workbench" / "shell.ts").read_text(encoding="utf-8")

    def ts_set(name: str) -> set[str]:
        m = re.search(rf"const {name} = new Set\(\[([^\]]*)\]\)", shell)
        return set(re.findall(r"'([A-Z_]+)'", m.group(1))) if m else set()

    failed, human, in_flight = ts_set("FAILED_STATES"), ts_set("HUMAN_STATES"), ts_set("IN_FLIGHT_STATES")
    expected_failed = set(TERMINAL) - {"RECEIPTED"}
    all_attempt_states = set(ALLOWED)
    covered = failed | human | in_flight | {"RECEIPTED"}
    vocab_checks = [
        ("FAILED_STATES == TERMINAL - {RECEIPTED}", failed == expected_failed, sorted(failed)),
        ("OUTCOME_UNKNOWN is 待审, NOT 失败", "OUTCOME_UNKNOWN" in human and "OUTCOME_UNKNOWN" not in failed, sorted(human)),
        ("every ALLOWED attempt state is classified",
         all_attempt_states <= covered | {"CANCELING"}, sorted(all_attempt_states - covered)),
        ("no invented states beyond the service vocabulary",
         (failed | human | in_flight) <= all_attempt_states, sorted((failed | human | in_flight) - all_attempt_states)),
    ]
    for label, ok, detail in vocab_checks:
        print(f"  {'PASS' if ok else '**FAIL**'}  VOCAB: {label} {detail}")
    vocab_failed = [label for label, ok, _ in vocab_checks if not ok]
    # Record the cross-check alongside the browser evidence when the driver is asked to.
    if os.environ.get("W03_VOCAB_TO_STDOUT_ONLY") != "1" and OUT.is_file():
        payload = json.loads(OUT.read_text(encoding="utf-8"))
        payload["vocab_cross_check"] = [
            {"name": label, "pass": ok, "detail": detail} for label, ok, detail in vocab_checks
        ]
        OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    if proc.returncode != 0 or vocab_failed:
        print(f"W03_BRIEF=FAIL exit={proc.returncode} vocab_failed={vocab_failed}")
        return 1
    payload = json.loads(OUT.read_text(encoding="utf-8"))
    failed_checks = [c["name"] for c in payload["checks"] if not c["pass"]]
    # Generic verdict: this runner is shared by several harnesses, so report the kind it
    # actually ran rather than a hard-coded W03 label.
    print(f"HARNESS={payload.get('kind')} checks={len(payload['checks'])} "
          f"passed={len(payload['checks']) - len(failed_checks)}")
    print(f"W03_BRIEF={'OK' if not failed_checks else 'CHECKS_FAILED'} "
          f"checks={len(payload['checks'])} failed={failed_checks} vocab={len(vocab_checks)}")
    return 0 if not failed_checks else 1


if __name__ == "__main__":
    raise SystemExit(main())
