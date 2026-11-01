#!/usr/bin/env python
"""WUI slice evidence — render the built Observer against the live sidecar and capture screens.

Uses `scripts/audit/topbar_geometry_via_cdp.serve_and_eval`, the browser bootstrap the shipped geometry
gate already trusts (port reservation believed from Chrome's own announcement, first-run UI suppressed,
CDP device metrics for a true floor viewport). Rolling my own launch/discovery was tried first and stalled
in target discovery, so this file deliberately owns no browser logic of its own.

Data is the real v3 projection from a FRESH canonical store under .project-local with the worker disabled:
the honest shape of that evidence is one registered project and an OFFLINE transport, which is exactly what
the UI must render as UNKNOWN rather than pad with zeros. Nothing here is a fixture; `?api=` points the
page at the running sidecar so the shot shows a live read path, not a bundled demo state.

Screenshots and the receipt stay inside the repository boundary (.project-local/artifacts/wui-20261009).
The receipt names the bytes it rendered (`servedBundle`, from `bundle_provenance`), because on 2026-10-10
every shot in this set had been taken against a `dist` that was rebuilt afterwards, and nothing on the
page said so.

usage: scripts/audit/wui_slice_capture.py http://127.0.0.1:PORT [label-prefix]
"""
from __future__ import annotations

import json
import sys
import time
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))

import bundle_provenance  # noqa: E402
import topbar_geometry_via_cdp as gate  # noqa: E402

ARTIFACTS = ROOT / ".project-local" / "artifacts" / "wui-20261009"

READBACK = """JSON.stringify({
  innerWidth: window.innerWidth,
  innerHeight: window.innerHeight,
  palette: document.documentElement.getAttribute('data-palette'),
  // the painted colours, not the attribute: an overlay that sets the attribute and matches no rule
  // renders exactly like the default, and only these numbers tell the two apart
  bodyBackground: getComputedStyle(document.body).backgroundColor,
  railBackground: (function(){var el=document.querySelector('.sidebar');return el?getComputedStyle(el).backgroundColor:null;})(),
  accentOfActiveLane: (function(){var el=document.querySelector('.nav button.active');return el?getComputedStyle(el).color:null;})(),
  themeClass: document.documentElement.className || '(dark default)',
  railLanes: document.querySelectorAll('.nav button[data-lane]').length,
  dailyLanes: document.querySelectorAll('.nav button[data-lane][data-daily="true"]').length,
  groupToggles: document.querySelectorAll('.nav button.nav-group-toggle').length,
  workflowEditorOnRail: !!document.querySelector('.nav button[data-lane="workflow-editor"]'),
  pageHeadings: Array.from(document.querySelectorAll('.page-head h2')).map(function(e){return e.textContent;}),
  panelTitles: Array.from(document.querySelectorAll('.panel h3')).map(function(e){return e.textContent;}),
  tableRows: document.querySelectorAll('.table tbody tr').length,
  detailLinks: document.querySelectorAll('[data-testid^="project-detail-link-"]').length,
  offNavNote: !!document.querySelector('[data-testid="off-nav-entry-note"]'),
  unknownCount: (document.body.innerText.match(/UNKNOWN/g) || []).length,
  collaborationSummary: document.body.innerText.indexOf('协作摘要') >= 0,
  // WUI-08's six-step chain: presence alone proved nothing when a lane rendered the header and no
  // stages, so this reads the per-stage state attributes, then scrolls the card into view and
  // hit-tests its centre -- the screenshot has to show the block the receipt claims, not a card
  // parked below the fold.
  wui08Chain: (function(){
    var heads = Array.prototype.slice.call(document.querySelectorAll('[data-migration-chain]'));
    var stages = Array.prototype.slice.call(document.querySelectorAll('[data-migration-stage]'));
    var first = heads.length ? heads[0] : null;
    var card = first ? (first.closest('.card') || first.parentElement) : null;
    var before = window.scrollY;
    if (card) {
      document.documentElement.style.scrollBehavior = 'auto';
      card.scrollIntoView({block: 'start'});
    }
    var r = card ? card.getBoundingClientRect() : null;
    var hit = null;
    if (r && r.width > 0 && r.height > 0) {
      var px = Math.round(r.left + r.width / 2);
      var py = Math.round(Math.max(1, Math.min(r.top + r.height / 2, window.innerHeight - 1)));
      var el = document.elementFromPoint(px, py);
      hit = el ? (el.closest('[data-migration-stage]') ? 'stage' : (el.closest('.card') === card ? 'own-card' : el.tagName)) : null;
    }
    return {
      groups: heads.length,
      subjects: heads.map(function(e){return e.getAttribute('data-migration-chain');}),
      stageIds: stages.map(function(e){return e.getAttribute('data-migration-stage');}),
      stageStates: stages.map(function(e){return e.getAttribute('data-stage-state');}),
      projected: stages.filter(function(e){return e.getAttribute('data-stage-state') === 'PROJECTED';}).length,
      notProjected: stages.filter(function(e){return e.getAttribute('data-stage-state') === 'NOT_PROJECTED';}).length,
      cardHeadline: card ? (card.innerText || '').slice(0, 160) : null,
      rect: r ? {x: Math.round(r.x), y: Math.round(r.y), w: Math.round(r.width), h: Math.round(r.height)} : null,
      scrollMoved: before !== window.scrollY,
      centreHit: hit,
      controlsInsideCard: card ? card.querySelectorAll('button, input, select, textarea').length : null
    };
  })(),
  disabledButtons: Array.from(document.querySelectorAll('button:disabled')).map(function(b){return b.textContent.trim();}),
  smallestText: (function(){
    var min = 999, sample = null;
    Array.prototype.forEach.call(document.querySelectorAll('body *'), function(el){
      var own = null;
      for (var i = 0; i < el.childNodes.length; i++) {
        var t = el.childNodes[i];
        if (t.nodeType === 3 && t.textContent.trim().length) { own = t.textContent.trim(); break; }
      }
      if (!own) return;
      var px = parseFloat(getComputedStyle(el).fontSize);
      if (px < min) { min = px; sample = own.slice(0, 24); }
    });
    return {px: min === 999 ? null : min, sample: sample};
  })(),
})"""


def query(api: str, **params) -> str:
    pairs = {"api": api}
    pairs.update({k: v for k, v in params.items() if v is not None})
    return urllib.parse.urlencode(pairs)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: wui_slice_capture.py http://127.0.0.1:PORT [label-prefix]")
        return 2
    backend = sys.argv[1].rstrip("/")
    api = f"{backend}/api/v1/snapshot"
    only = sys.argv[2] if len(sys.argv) > 2 else None

    ARTIFACTS.mkdir(parents=True, exist_ok=True)
    bundle = bundle_provenance.describe(ROOT)
    with urllib.request.urlopen(api, timeout=10) as response:
        snap = json.loads(response.read().decode("utf-8"))
    projects = snap.get("projects") or []
    project_id = (projects[0] or {}).get("projectId") if projects else None
    print(f"SNAPSHOT projects={len(projects)} transport="
          f"{(snap.get('transport') or {}).get('transportState')} revision={snap.get('revision')} "
          f"firstProjectId={project_id}", flush=True)

    states = [
        ("01-main-dark", "1280,820", None, query(api, view="overview", theme="dark")),
        ("02-main-light", "1280,820", None, query(api, view="overview", theme="light")),
        ("03-master-palette-dark", "1280,820", None,
         query(api, view="overview", theme="dark", palette="master")),
        ("04-master-palette-light", "1280,820", None,
         query(api, view="overview", theme="light", palette="master")),
        ("05-floor-900x600", "1280,820", (900, 600), query(api, view="overview", theme="dark")),
        ("06-demoted-lane", "1280,820", None, query(api, view="workflow-editor", theme="dark")),
        ("08-compact-hud", "440,680", None, query(api, layout="compact", theme="dark")),
        # WUI-05/06/07/09: the four destination pages against the same live projection.
        ("09-usage-cache", "1280,820", None, query(api, view="usage", theme="dark")),
        ("10-software-environment", "1280,820", None, query(api, view="environment", theme="dark")),
        ("11-capability-assets", "1280,820", None, query(api, view="capabilities", theme="dark")),
        ("12-rules-adaptation", "1280,820", None, query(api, view="rules-adaptation", theme="dark")),
    ]
    if project_id:
        states.insert(6, ("07-object-detail", "1280,820", None,
                          query(api, view="project-detail", projectId=project_id, theme="dark")))

    browser = gate.find_browser()
    if not browser:
        print("EVIDENCE_NOT_RUN BROWSER_NOT_FOUND — set WL_CHROME to a Chrome/Edge binary")
        return 3
    u19 = gate.load_u19()

    records = []
    for label, size, viewport, qs in states:
        if only and not label.startswith(only):
            continue
        shot = ARTIFACTS / f"{label}.png"
        record = {"label": label, "windowSize": size, "viewport": viewport,
                  "path": f"/index.html?{qs}", "screenshot": str(shot)}
        started = time.time()
        try:
            measured = gate.serve_and_eval(ROOT, f"/index.html?{qs}", size, READBACK, browser, u19,
                                           shot, viewport=viewport)
            record["dom"] = measured
            record["status"] = "PASS"
        except Exception as error:  # a failed shot is reported as failed, never dropped
            record["status"] = "FAIL"
            record["reason"] = repr(error)
        record["seconds"] = round(time.time() - started, 1)
        if shot.is_file():
            record["screenshotBytes"] = shot.stat().st_size
        records.append(record)
        dom = record.get("dom") or {}
        print(f"SHOT {label} {record['status']} lanes={dom.get('railLanes')} daily={dom.get('dailyLanes')} "
              f"inner={dom.get('innerWidth')}x{dom.get('innerHeight')} palette={dom.get('palette')} "
              f"bg={dom.get('bodyBackground')} rail={dom.get('railBackground')} "
              f"chain={(dom.get('wui08Chain') or {}).get('stageIds')} "
              f"chainState={(dom.get('wui08Chain') or {}).get('stageStates')} "
              f"chainHit={(dom.get('wui08Chain') or {}).get('centreHit')} "
              f"bytes={record.get('screenshotBytes')} {record.get('reason', '')}", flush=True)

    moved = bundle_provenance.describe(ROOT)
    receipt = {
        "gate": "WUI-01/02/03 slice evidence",
        "capturedAt": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "browser": browser,
        "backend": backend,
        "backendStore": "fresh canonical store, worker disabled",
        "servedBundle": bundle,
        "bundleStayedPut": moved["bundleDigest"] == bundle["bundleDigest"],
        "snapshotFacts": {
            "projects": len(projects),
            "transportState": (snap.get("transport") or {}).get("transportState"),
            "revision": snap.get("revision"),
        },
        "shots": records,
    }
    out = ARTIFACTS / "evidence-receipt.json"
    out.write_text(json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    passed = sum(1 for r in records if r["status"] == "PASS")
    print(f"EVIDENCE captured={passed}/{len(records)} bundle={bundle['bundleDigest'][:16]} "
          f"stable={receipt['bundleStayedPut']} receipt={out}")
    if not receipt["bundleStayedPut"]:
        print("EVIDENCE_REFUSE the bundle changed between the first shot and the last; "
              "no single digest describes this set")
        return 1
    return 0 if passed == len(records) else 1


if __name__ == "__main__":
    raise SystemExit(main())
