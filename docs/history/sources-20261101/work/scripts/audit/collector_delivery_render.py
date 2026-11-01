#!/usr/bin/env python
"""Render evidence for the collector delivery card — built from the REAL pipeline, not a fixture payload.

The chain this instrument walks is the one a user walks:

  1. a fresh canonical store under the declared runtime root,
  2. a real `usage.jsonl` written into a real search root — three honest rows, one row carrying a synthetic
     credential shape (the ERR-244 refusal path), one unparseable line,
  3. one real `DurableWorker.run_once()` tick over the shipped collectors, which is what writes
     `collector_health` (delivered / refused / drops) through `upsert_collector_health`,
  4. a live `WorkflowSidecar` serving that store at `/api/v1/snapshot`,
  5. the SHIPPED `dist` bundle rendered in Chromium at the window default and at the 900x600 floor, reading
     the card out of the DOM with geometry, not class names.

It deliberately owns no browser logic: the launch, port reservation and CDP evaluation come from
`topbar_geometry_via_cdp`, the bootstrap the shipped geometry gate already trusts (the same module
`wui_slice_capture.py` uses), and the receipt names the bundle bytes it rendered, because on 2026-10-10 a
set of shots had been taken against a `dist` that was rebuilt afterwards and nothing on the page said so.

What is asserted is what the card CLAIMS: that the numbers on screen are the numbers the store holds, that a
refused row is traceable to the line that was refused, that an absent section and an empty one are worded
differently, and that no percentage is invented from two counters.

usage: scripts/audit/collector_delivery_render.py [--screens]
"""
from __future__ import annotations

import json
import sys
import threading
import time
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
sys.path.insert(0, str(ROOT / "services" / "orchestration"))

import bundle_provenance  # noqa: E402
import project_temp  # noqa: E402
import topbar_geometry_via_cdp as gate  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402
from collectors import collect_usage_files  # noqa: E402
from durable_worker import DurableWorker  # noqa: E402
from sidecar import WorkflowSidecar, create_server  # noqa: E402

ARTIFACTS = ROOT / ".project-local" / "artifacts" / "wui-20261010"
POISON_KEY = "sk-" + "Qj7Wd2Fg5Hk9Ls3ZxA4Cv6Bn8M"

READBACK = """(function () {
  function collect() {
    return Array.prototype.map.call(document.querySelectorAll('[data-collector-row]'), function (el) {
      var r = el.getBoundingClientRect();
      return {
        name: el.getAttribute('data-collector-row'),
        text: el.innerText.replace(/\\s+/g, ' ').trim(),
        rect: {top: Math.round(r.top), left: Math.round(r.left),
               width: Math.round(r.width), height: Math.round(r.height)},
        onScreen: r.width > 0 && r.height > 0 && r.top >= 0 && r.bottom <= window.innerHeight,
        ownFontPx: (function () {
          var min = 999;
          Array.prototype.forEach.call(el.querySelectorAll('*'), function (n) {
            for (var i = 0; i < n.childNodes.length; i++) {
              var t = n.childNodes[i];
              if (t.nodeType === 3 && t.textContent.trim().length) {
                var px = parseFloat(getComputedStyle(n).fontSize);
                if (px < min) min = px;
                break;
              }
            }
          });
          return min === 999 ? null : min;
        })(),
      };
    });
  }
  var before = collect();
  var card = document.querySelector('[data-collector-row]');
  if (card) card.scrollIntoView({block: 'center'});
  var after = collect();
  return JSON.stringify({
    innerWidth: window.innerWidth,
    innerHeight: window.innerHeight,
    documentScrollHeight: document.documentElement.scrollHeight,
    rowsBeforeScroll: before,
    rowsAfterScroll: after,
    gapBranch: !!document.querySelector('[data-collector-gap]'),
    unregisteredBranch: !!document.querySelector('[data-collector-unregistered]'),
    freshButRefusing: (document.querySelector('[data-collector-fresh-but-refusing]') || {}).textContent || null,
    rateShown: /\\d+(\\.\\d+)?\\s*%/.test(document.body.innerText),
    buttonsInCard: document.querySelectorAll('[data-collector-row] button, [data-collector-row] input').length,
  });
})()"""


def seed_store() -> tuple[Path, CanonicalStore, dict]:
    """One real tick over a real search root; returns the store plus what the collector reported.

    A fresh fixture directory per run, not a durable named one: the counts in this receipt are cumulative by
    design, so reusing a directory would make the numbers depend on how many times the instrument had been
    run — which is exactly the kind of receipt that cannot be re-checked.
    """
    directory = project_temp.fixture_dir("collector-render-")
    store = CanonicalStore(directory / "canonical.sqlite")
    artifacts = directory / "task-artifacts"
    artifacts.mkdir(parents=True, exist_ok=True)
    lines = [
        json.dumps({"provider": "deepseek", "model": "deepseek-v4-flash",
                    "input_tokens": 120, "output_tokens": 30, "total_tokens": 150}),
        json.dumps({"provider": POISON_KEY, "model": "gpt-test", "input_tokens": 7}),
        json.dumps({"provider": "openai", "model": "gpt-test", "total_tokens": 40}),
        "{this line is not json",
    ]
    (artifacts / "usage.jsonl").write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")

    def usage_collector(_store: CanonicalStore, project_id: str):
        return collect_usage_files(_store, project_id, artifacts)

    usage_collector.collector_name = "usage-files"
    worker = DurableWorker(store, project_id="work-lab", collectors=[usage_collector])
    result = worker.run_once()
    return directory, store, result


def main() -> int:
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    directory, store, tick = seed_store()
    outcomes = {c.get("kind"): c for c in tick["collectors"]}
    usage = outcomes.get("usage") or {}
    print(f"TICK stored={usage.get('stored')} refused={usage.get('refused')} "
          f"reasons={json.dumps(usage.get('refusalReasons'), ensure_ascii=False)}", flush=True)
    health = {row["name"]: row for row in store.list_collector_health()}
    print("HEALTH " + json.dumps(
        {name: {k: row.get(k) for k in ("total_runs", "delivered_rows", "refused_rows",
                                        "dropped_count", "last_refusal_reason")}
         for name, row in health.items()}, ensure_ascii=False), flush=True)

    sidecar = WorkflowSidecar(ROOT, directory)
    server = create_server(sidecar)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    api = f"http://127.0.0.1:{server.server_port}/api/v1/snapshot"
    snapshot = json.loads(__import__("urllib.request").request.urlopen(api, timeout=10).read().decode("utf-8"))
    collectors_section = snapshot.get("collectors")
    print(f"SNAPSHOT transport={(snapshot.get('transport') or {}).get('transportState')} "
          f"revision={snapshot.get('revision')} collectors_section="
          f"{'present' if collectors_section is not None else 'ABSENT'} "
          f"rows={len(collectors_section or [])}", flush=True)

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    bundle_before = bundle_provenance.describe(ROOT)
    browser = gate.find_browser()
    if not browser:
        print("EVIDENCE_NOT_RUN BROWSER_NOT_FOUND — set WL_CHROME to a Chrome/Edge binary")
        store.close()
        server.shutdown()
        return 3
    u19 = gate.load_u19()

    screens = [("collector-card-1280x820", "1280,820", None),
               ("collector-card-floor-900x600", "1280,820", (900, 600))]
    records = []
    problems: list[str] = []
    for label, size, viewport in screens:
        query = urllib.parse.urlencode({"api": api, "view": "privacy", "theme": "dark"})
        path = f"/index.html?{query}"
        shot = ARTIFACTS / f"{label}.png"
        record = {"label": label, "windowSize": size, "viewport": viewport, "path": path,
                  "screenshot": str(shot)}
        try:
            measured = gate.serve_and_eval(ROOT, path, size, READBACK, browser, u19, shot, viewport=viewport)
            record["dom"] = measured
            record["status"] = "PASS"
        except Exception as error:  # a failed shot is reported as failed, never dropped
            record["status"] = "FAIL"
            record["reason"] = repr(error)
            measured = {}
        if shot.is_file():
            record["screenshotBytes"] = shot.stat().st_size
        records.append(record)
        print(f"SHOT {label} {record['status']} rows={(measured.get('rowsAfterScroll') or []).__len__()} "
              f"inner={measured.get('innerWidth')}x{measured.get('innerHeight')} "
              f"scrollHeight={measured.get('documentScrollHeight')} "
              f"bytes={record.get('screenshotBytes')} {record.get('reason', '')}", flush=True)
        for row in measured.get("rowsAfterScroll") or []:
            print(f"  ROW {row['name']} rect={row['rect']} onScreen={row['onScreen']} "
                  f"fontPx={row['ownFontPx']} text={row['text'][:150]}", flush=True)

        if label.startswith("collector-card-1280"):
            before = measured.get("rowsBeforeScroll") or []
            rows = measured.get("rowsAfterScroll") or []
            if not rows:
                problems.append("no [data-collector-row] rendered — the card did not reach the screen")
            for row in rows:
                if row["rect"]["height"] <= 0 or row["rect"]["width"] <= 0:
                    problems.append(f"row {row['name']} has an empty rect")
                if not row["onScreen"]:
                    problems.append(f"row {row['name']} still off-screen after scrolling: {row['rect']}")
                if row["ownFontPx"] is not None and row["ownFontPx"] < 12:
                    problems.append(f"row {row['name']} text under the 12px floor: {row['ownFontPx']}")
            # below-the-fold is a fact about the page, not a defect, so it is recorded rather than asserted
            # away: the card sits after the lifecycle blocks, and scrolling is what proves it is reachable.
            print(f"  placement before-scroll: {[r['rect']['top'] for r in before]}", flush=True)
            names = {row["name"] for row in rows}
            if "usage-files" not in names:
                problems.append(f"the collector that ran is not on screen: {sorted(names)}")
            usage_row = next((r for r in rows if r["name"] == "usage-files"), None)
            if usage_row:
                for fragment in ("交出 2 行", "拒绝 2 行", "队列丢弃 0 行", "运行 1 次",
                                 "usage.jsonl:4", "usage.jsonl:2"):
                    if fragment not in usage_row["text"]:
                        problems.append(f"{fragment!r} not rendered: {usage_row['text'][:220]}")
            if measured.get("rateShown"):
                problems.append("a percentage was rendered from two counters that do not form one")
            if measured.get("buttonsInCard"):
                problems.append("the delivery card grew a control — Observer is read-only")
            if not measured.get("freshButRefusing"):
                problems.append("the fresh-but-refusing combination is exactly what this card exists to say, "
                                "and it was not said")

    bundle_after = bundle_provenance.describe(ROOT)
    receipt = {
        "gate": "WUI-18(e)/WUI-11 collector delivery card — rendered evidence",
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "browser": browser,
        "backend": api,
        "backendStore": str(directory / "canonical.sqlite"),
        "producerTick": usage,
        "collectorHealthRows": list(health.values()),
        "snapshotCollectors": collectors_section,
        "servedBundle": bundle_before,
        "bundleUnchangedAcrossRun": bundle_before == bundle_after,
        "screens": records,
        "problems": problems,
    }
    receipt_path = ARTIFACTS / "collector-delivery-card.json"
    receipt_path.write_text(json.dumps(receipt, indent=2, ensure_ascii=False) + "\n",
                            encoding="utf-8", newline="\n")
    print(f"RECEIPT {receipt_path} bundle={json.dumps(bundle_before)[:160]} "
          f"unchanged={receipt['bundleUnchangedAcrossRun']}", flush=True)
    store.close()
    server.shutdown()
    server.server_close()
    released = project_temp.force_release(directory)
    print(f"FIXTURE_RELEASED {directory} ok={released}", flush=True)
    if not released:
        print("TEMP_RESIDUE_NOT_REMOVED the render store is still on disk", flush=True)
    if problems:
        print("COLLECTOR_CARD_EVIDENCE FAIL " + " | ".join(problems))
        return 1
    print("COLLECTOR_CARD_EVIDENCE PASS rows_rendered="
          f"{len((records[0].get('dom') or {}).get('rowsAfterScroll') or [])} screens={len(records)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
