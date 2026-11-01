#!/usr/bin/env python
"""Render the Control shell over a real write boundary and prove a lost refresh re-QUERIES.

WUI-10's second owner constraint is behavioural, not structural: 后台刷新丢失时保留操作身份并查询同一操作，
禁止以新幂等键自动重复写入. A Python test can prove the route answers; only a browser can prove the page
that the operator actually reloads does the querying, shows the ledger's own key, and never sends a write
on its own behalf.

What runs here is the shipped stack, in one process, on loopback: `control_service.build_plane` over a
canonical store under `.project-local`, `ControlServer` serving `apps/control-surface` and the API on the
SAME origin (that is the design — one origin for the page and its POST), one real `work-unit.create`
submitted over HTTP, then headless Chrome driven by the geometry gate's own bootstrap
(`topbar_geometry_via_cdp.serve_and_eval`, which is why nothing here launches a browser of its own).

Three screens, because the claim has three sides:
  restored   `/?operation=<the id that was written>`   -- the page reads the identity back
  fresh      `/`                                       -- the same page with no URL identity
  absent     `/?operation=<an id nothing wrote>`       -- a missing record stays a missing record

and the negative is the middle one: if the fresh page also said "来自账本读回", the restore branch would not
be what produced that sentence and screen one would be worth nothing.

After the browser is closed, the store and the append-only receipts file are read again: the whole point of
the constraint is that a reload must not add a write, so a second row or a second receipt line fails this
instrument even if every screen looked perfect.

usage: python scripts/audit/control_shell_identity_via_cdp.py [--json-out PATH]
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
import threading
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for _entry in (ROOT / "scripts" / "audit", ROOT / "services" / "control", ROOT / "services" / "orchestration",
               ROOT / "services" / "task-governance", ROOT / "packages" / "client-neutral-core" / "scripts"):
    sys.path.insert(0, str(_entry))

import bundle_provenance  # noqa: E402
import control_service  # noqa: E402
import topbar_geometry_via_cdp as gate  # noqa: E402
from project_temp import fixture_dir  # noqa: E402

ARTIFACTS = ROOT / ".project-local" / "artifacts" / "wui-20261011"
TASK_ID = "WL-SHELL-IDENTITY-1"

READBACK = """(function(){
  // Scroll the answer into view BEFORE measuring it. The first version of this instrument asserted the
  // panel's geometry where the page had left it, and the panel sits below the fold: the shot proved the
  // page loaded, not that the operator could read the sentence the claim is about.
  var result = document.getElementById('result');
  var before = window.scrollY;
  if (result) { document.documentElement.style.scrollBehavior = 'auto'; result.scrollIntoView({block: 'center'}); }
  var rect = null, centre = null;
  if (result) {
    var r = result.getBoundingClientRect();
    rect = {x:Math.round(r.x), y:Math.round(r.y), w:Math.round(r.width), h:Math.round(r.height)};
    if (r.width && r.height) {
      var top = Math.max(1, Math.min(r.y + r.height / 2, window.innerHeight - 1));
      var hit = document.elementFromPoint(Math.round(r.x + r.width / 2), Math.round(top));
      centre = hit ? (result === hit || result.contains(hit)) : false;
    }
  }
  return JSON.stringify({
  locationSearch: location.search,
  identityLine: (document.getElementById('idem') || {}).textContent || null,
  resultText: (document.getElementById('result') || {}).textContent || null,
  taskIdField: (document.getElementById('task-id') || {}).value || null,
  transportTag: (document.getElementById('transport') || {}).textContent || null,
  viewport: {w: window.innerWidth, h: window.innerHeight},
  scrollMoved: before !== window.scrollY,
  // geometry, not presence: a paragraph that exists above the fold and one that is 4000px down are
  // different answers about what the operator saw in the screenshot
  resultRect: rect,
  resultPaintedAtCentre: centre,
  writeControlsDisabled: Array.prototype.slice.call(document.querySelectorAll('button[type=submit]'))
      .map(function(b){return {id:b.id, disabled:!!b.disabled};}),
  });
})()"""


def post_operation(base: str, key: str) -> dict:
    payload = {
        "schema_version": "worklab/control-operation/v1",
        "operation": "work-unit.create",
        "project_id": "work-lab",
        "task_id": TASK_ID,
        "revision": None,
        "attempt": None,
        "scope": {"boundaries": [str(ROOT)], "granted_by": "owner 2026-10-11 WUI-10 事务演练"},
        "expected_version": None,
        "idempotency_key": key,
        "actor": "control-shell",
        "requested_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "payload": {"goal": "受管命令边界的身份读回实测（不执行任何外部动作）"},
    }
    request = urllib.request.Request(base + "/api/control/operations", data=json.dumps(payload).encode("utf-8"),
                                     headers={"Content-Type": "application/json"}, method="POST")
    with urllib.request.urlopen(request, timeout=10) as response:
        return json.loads(response.read().decode("utf-8"))


def _release(server, plane) -> None:
    """One way out: stop serving and drop the store handle, so every exit path leaves no locked file."""
    server.shutdown()
    server.server_close()
    plane.store.close()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json-out", default=None)
    args = parser.parse_args()

    failures: list[str] = []
    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    runtime = fixture_dir(prefix="control-shell-render-")
    plane = control_service.build_plane(runtime, ROOT)
    server = control_service.ControlServer(plane)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{server.bound_port}"
    print(f"CONTROL_SERVING url={base} runtime={runtime}", flush=True)

    served = {}
    for asset in ("/", "/control-shell.js"):
        with urllib.request.urlopen(base + asset, timeout=10) as response:
            served[asset] = hashlib.sha256(response.read()).hexdigest()

    created = post_operation(base, "idem-shell-first")
    if created.get("status") != "ACCEPTED":
        print(f"SHELL_EVIDENCE_NOT_RUN the real write did not land: {created}", flush=True)
        _release(server, plane)
        return 2

    browser = gate.find_browser()
    if not browser:
        print("SHELL_EVIDENCE_NOT_RUN BROWSER_NOT_FOUND — set WL_CHROME to a Chrome/Edge binary")
        # A refusal that leaves the store open behind it is not a clean exit: the fixture directory the run
        # registered for cleanup cannot be deleted while the sqlite handle is live, so the residue census
        # reports it. Close on the way out, the same way the measured paths do.
        _release(server, plane)
        return 3
    u19 = gate.load_u19()

    shots = [
        ("01-restored-identity", f"{base}/?operation={TASK_ID}"),
        ("02-fresh-no-identity", f"{base}/"),
        ("03-absent-identity", f"{base}/?operation=WL-NEVER-WRITTEN"),
    ]
    screens: dict[str, dict] = {}
    for label, url in shots:
        shot = ARTIFACTS / f"{label}.png"
        record = {"url": url, "screenshot": str(shot)}
        try:
            record["dom"] = gate.serve_and_eval(ROOT, "/", "1280,820", READBACK, browser, u19, shot,
                                                serve_url=url)
        except Exception as error:  # a failed screen is reported as failed, never dropped
            record["status"] = "FAIL"
            record["reason"] = repr(error)
        else:
            record["status"] = "PASS"
        if shot.is_file():
            record["screenshotBytes"] = shot.stat().st_size
        screens[label] = record
        dom = record.get("dom") or {}
        print(f"SCREEN {label} {record['status']} search={dom.get('locationSearch')} "
              f"bytes={record.get('screenshotBytes')} {record.get('reason', '')}", flush=True)

    # -- what the restored screen must say, and what only the ledger can say --
    restored = (screens["01-restored-identity"].get("dom") or {})
    fresh = (screens["02-fresh-no-identity"].get("dom") or {})
    absent = (screens["03-absent-identity"].get("dom") or {})
    text = restored.get("resultText") or ""
    if "CONFIRMED" not in text:
        failures.append(f"the restored screen did not show the write as CONFIRMED: {text[:220]!r}")
    if text.count("NOT_PROJECTED") != 2:
        failures.append(f"the two later outcomes must both read NOT_PROJECTED, got {text.count('NOT_PROJECTED')}: "
                        f"{text[:220]!r}")
    if "来自账本读回" not in (restored.get("identityLine") or ""):
        failures.append("the identity line does not say the key came from the ledger read-back: "
                        f"{(restored.get('identityLine') or '')!r}")
    if (restored.get("taskIdField") or "") != TASK_ID:
        failures.append(f"the form did not adopt the URL identity: {restored.get('taskIdField')!r}")
    if "来自账本读回" in (fresh.get("identityLine") or ""):
        failures.append("the fresh page claimed a ledger read-back too, so screen one proves nothing about "
                        "the restore branch")
    if not (fresh.get("identityLine") or "").startswith("idempotency ctl-"):
        failures.append(f"the fresh page should mint its own key: {(fresh.get('identityLine') or '')!r}")
    absent_text = absent.get("resultText") or ""
    if "OPERATION_NOT_FOUND" not in absent_text or "NO_RECORD" not in absent_text:
        failures.append(f"an absent identity did not stay absent on screen: {absent_text[:220]!r}")
    for label, record in screens.items():
        dom = record.get("dom") or {}
        rect = dom.get("resultRect") or {}
        if record["status"] != "PASS":
            failures.append(f"{label} did not render: {record.get('reason')}")
        elif not rect.get("w") or not rect.get("h") or not dom.get("resultPaintedAtCentre"):
            failures.append(f"{label} rendered the result panel but it is not painted where the screenshot "
                            f"saw it: rect={rect} centre={dom.get('resultPaintedAtCentre')}")

    # -- the reload must not have written: read the durable state, not the page's word --
    rows = [row for row in plane.store.list_tasks() if row["task_id"] == TASK_ID]
    receipt_lines = [line for line in plane.receipts_path.read_text(encoding="utf-8").splitlines()
                    if TASK_ID in line] if plane.receipts_path.is_file() else []
    if len(rows) != 1:
        failures.append(f"the rendered reloads changed the ledger: rows_for_identity={len(rows)}")
    if len(receipt_lines) != 1:
        failures.append(f"the rendered reloads appended receipts: {len(receipt_lines)} lines for {TASK_ID}")

    moved = bundle_provenance.describe(ROOT)
    out = Path(args.json_out) if args.json_out else ARTIFACTS / "control-shell-identity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    receipt = {
        "instrument": "control_shell_identity_via_cdp",
        "taskpack": "WUI-10 身份读回",
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "browser": browser,
        "servedBytes": {"sha256": served, "basis": "what the write boundary actually sent"},
        "operation": {"taskId": TASK_ID, "status": created["status"],
                      "receiptKind": (created.get("receipt") or {}).get("kind")},
        "ledgerAfterScreens": {"rowsForIdentity": len(rows), "receiptLinesForIdentity": len(receipt_lines)},
        "distBundleDigestUnaffected": moved["bundleDigest"],
        "screens": screens,
        "failures": failures,
    }
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    verdict = "CONTROL_SHELL_IDENTITY_PASS" if not failures else "CONTROL_SHELL_IDENTITY_FAIL"
    for failure in failures:
        print(f"FAIL {failure}")
    print(f"{verdict} screens={sum(1 for r in screens.values() if r['status'] == 'PASS')}/{len(shots)} "
          f"rows={len(rows)} receipts={len(receipt_lines)} receipt={out}")
    _release(server, plane)
    return 0 if not failures else 1


if __name__ == "__main__":
    sys.exit(main())
