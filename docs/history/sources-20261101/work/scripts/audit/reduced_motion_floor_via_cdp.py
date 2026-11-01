#!/usr/bin/env python3
"""Read the reduced-motion promise off the painted page instead of out of the stylesheet text.

CL-16 step 2's third clause asked for exactly this conversion: "reduced-motion 断言改为对每个面读计算样式
而不是 grep 字符串". Until 2026-10-29 the only guard on this standard was
`apps/observer/frontend/src/reducedMotion.contract.test.ts`, which read `src/skins/l10b-shell.css` from disk
and asserted the characters `transition: none !important` appear after a comment. That text can be true while
the browser answers a different question: a later `!important` in another sheet, a selector that misses a
pseudo-element, or a rule that a component overrides inline, each leaves the grep green and the motion playing.
Measured with this instrument on 2026-10-29 (five surfaces x two pinned preferences, `.project-local/runs/
live-probe-20261029/reduced-motion-census.json`), the floor does hold as computed style:

    professional      65 transitions / 4 animations  ->  0 / 0
    panel-h01          9 transitions / 4 animations   ->  0 / 0
    daily-home         5 transitions / 0 animations   ->  0 / 0
    daily-governance  35 transitions / 0 animations    ->  0 / 0
    strip-h01          0 transitions / 0 animations     ->  0 / 0   <- NO motion in either branch

The last row is what the census found that no other gate could see, and why the two branches are both walked:
a surface that reports zero motion under `reduce` proves nothing on its own, because it also reports zero when
the preference is off. The HUD strip's hover/expand is JavaScript state, not a CSS transition, so the floor has
nothing to flatten there. This gate therefore asserts the floor and reports the coverage, and its population
clause convicts the instrument if every surface is motionless in both branches — a gate that can only ever see
`0` is guarding nothing.

Headless Chrome answers `prefers-reduced-motion: reduce` by itself (measured 2026-10-26 on the pressed-state
gate), so each branch pins the preference over CDP and reads `matchMedia` back from the page before believing
any number. A pin that did not land is refused, not scored.

Exit: 0 REDUCED_MOTION_FLOOR_GATE_PASS, 1 ..._FAIL, 3 ..._NOT_RUN, 2 ..._NOT_RUN for a named bad argument.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "audit"))

import bundle_provenance  # noqa: E402
import text_legibility_via_cdp as legibility  # noqa: E402
import topbar_geometry_via_cdp as geometry  # noqa: E402
import hud_strip_geometry_via_cdp as hud  # noqa: E402

OUT_DIR = ROOT / ".project-local" / "runs" / "reduced-motion-gate"

# The professional shell is the one surface the strip gate does not declare, and it is where the most motion
# lives (65 transitions measured), so it is stated here with the shared bootstrap's own mount selector.
PROFESSIONAL = {"label": "professional", "query": "view=full", "size": (1280, 820),
                "mount": geometry.MOUNT_SELECTOR, "minNodes": legibility.MIN_NODES}

# Keyed by the strip gate's surface names, so a rename there lands here as a failure rather than a silent
# drop — the same reason `text_legibility_via_cdp.shell_surfaces()` reads that list instead of copying it.
SHELL_SURFACES = ("strip-h01", "panel-h01", "daily-home", "daily-governance")

# Walk every node, its two pseudo-elements, and the root's scroll behaviour, and hand back the counts plus
# enough examples to read. "Motion" is a property the browser would actually animate: a duration above zero
# AND a property other than `none` — `transition: none !important` sets both, so the floor reads as no motion
# whether it lands through the duration or through the property.
MOTION_CENSUS_JS = r"""(function(){
  const anyPositive = (v) => String(v || '').split(',').some((x) => parseFloat(x) > 0);
  const label = (el) => el.tagName.toLowerCase() +
      (el.id ? '#' + el.id : '') +
      (typeof el.className === 'string' && el.className
         ? '.' + el.className.trim().split(/\s+/).slice(0, 3).join('.') : '');
  const out = {elements: 0, pseudoScanned: 0, transitions: [], animations: [],
               transitionCount: 0, animationCount: 0, scroll: null, measuredAt: null};
  const nodes = [document.documentElement].concat(Array.from(document.querySelectorAll('*')));
  out.elements = nodes.length;
  const take = (el, cs, suffix) => {
    if (cs.transitionProperty !== 'none' && anyPositive(cs.transitionDuration)) {
      out.transitionCount++;
      if (out.transitions.length < 12) {
        out.transitions.push({node: label(el) + suffix, prop: cs.transitionProperty,
                              dur: cs.transitionDuration});
      }
    }
    if (cs.animationName !== 'none' && anyPositive(cs.animationDuration)) {
      out.animationCount++;
      if (out.animations.length < 12) {
        out.animations.push({node: label(el) + suffix, name: cs.animationName,
                             dur: cs.animationDuration, iter: cs.animationIterationCount});
      }
    }
  };
  for (const el of nodes) { take(el, getComputedStyle(el), ''); }
  for (const el of nodes.slice(0, 900)) {
    for (const pe of ['::before', '::after']) {
      const cs = getComputedStyle(el, pe);
      if (!cs || cs.animationName === undefined) continue;
      out.pseudoScanned++;
      take(el, cs, pe);
    }
  }
  out.scroll = getComputedStyle(document.documentElement).scrollBehavior;
  out.measuredAt = performance.now();
  return JSON.stringify(out);
})()"""

PIN_READBACK_JS = ("JSON.stringify({reduce: window.matchMedia('(prefers-reduced-motion: reduce)').matches,"
                   " noPreference: window.matchMedia('(prefers-reduced-motion: no-preference)').matches})")

# The two branches have to be separated by a style recalc, not read back to back.
PREF_SETTLE_S = 0.3


def surfaces(strip, wanted: list[str]) -> list[dict]:
    """The surfaces to census, taken from the strip gate's own declarations (query, size, mount, floor)."""
    out = [PROFESSIONAL]
    for spec in strip.SURFACES:
        if spec["name"] not in SHELL_SURFACES:
            continue
        out.append({"label": spec["name"], "query": spec["query"], "size": spec["size"],
                    "mount": strip.MOUNT_SELECTOR[spec["kind"]],
                    "minNodes": legibility.SHELL_SURFACE_KINDS[spec["name"]]})
    missing = sorted(set(SHELL_SURFACES) - {s["label"] for s in out})
    if missing:
        raise RuntimeError(f"SURFACE_MISSING {missing} — the strip gate no longer declares them")
    unknown = sorted(set(wanted) - {s["label"] for s in out})
    if unknown:
        raise RuntimeError(f"UNKNOWN_SURFACE {unknown} — declared: {[s['label'] for s in out]}")
    return [s for s in out if s["label"] in wanted]


def pin(cdp, value: str) -> dict:
    """Pin `prefers-reduced-motion` and prove the pin reached the page before anything is censused."""
    cdp.send("Emulation.setEmulatedMedia",
             {"features": [{"name": "prefers-reduced-motion", "value": value}]})
    time.sleep(PREF_SETTLE_S)
    raw = cdp.evaluate(PIN_READBACK_JS)
    return json.loads(raw) if isinstance(raw, str) else raw


def census(cdp) -> dict:
    raw = cdp.evaluate(MOTION_CENSUS_JS)
    return json.loads(raw) if isinstance(raw, str) else raw


def measure_surface(cdp) -> dict:
    """One document, both preferences, in the order that cannot flatter the floor.

    `no-preference` is censused first: if the environment were already flattened, walking the reduced branch
    first and the normal branch second would let a `0` on one side be read as the other side's answer.
    """
    normal_pin = pin(cdp, "no-preference")
    normal = census(cdp)
    reduce_pin = pin(cdp, "reduce")
    reduced = census(cdp)
    return {"normalPin": normal_pin, "normal": normal,
            "reducePin": reduce_pin, "reduce": reduced}


def _motion(box: dict) -> int:
    return int(box.get("transitionCount") or 0) + int(box.get("animationCount") or 0)


def verdict(measured: dict[str, dict]) -> dict:
    """Pure: the thresholds live here so a planted fault is a one-line data edit, not a rebuild."""
    checks: list[dict] = []
    reported: dict[str, str] = {}

    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"check": name, "pass": bool(ok), "detail": detail})

    add("gate_measured_a_surface", bool(measured),
        "surfaces=" + (json.dumps(sorted(measured)) if measured
                       else "none — nothing was censused, so nothing was proven"))

    for label, m in measured.items():
        normal, reduced = m.get("normal") or {}, m.get("reduce") or {}
        normal_pin, reduce_pin = m.get("normalPin") or {}, m.get("reducePin") or {}
        add(f"reduced_motion_preference_pinned[{label}]",
            normal_pin.get("reduce") is False and reduce_pin.get("reduce") is True,
            f"no-preference branch reduce={normal_pin.get('reduce')!r} "
            f"reduce branch reduce={reduce_pin.get('reduce')!r} "
            "(headless Chrome answers this preference by itself; unpinned, a `0` here would be the OS's "
            "answer rather than the sheet's)")

        # A census of a blank page reports no motion and would pass the floor clause for the wrong reason.
        # The node floors are the legibility gate's, so one standard keeps one owner.
        floor = m.get("minNodes")
        add(f"surface_was_painted_before_it_was_censused[{label}]",
            int(normal.get("elements") or 0) >= int(floor or 0)
            and int(reduced.get("elements") or 0) >= int(floor or 0),
            f"nodes={normal.get('elements')}/{reduced.get('elements')} floor={floor} "
            "(a census that walked an unmounted root sees zero motion without the floor having anything to do)")

        add(f"reduced_motion_floor_holds[{label}]",
            _motion(reduced) == 0 and reduced.get("scroll") != "smooth",
            f"reduce transitions={reduced.get('transitionCount')} animations={reduced.get('animationCount')} "
            f"scroll={reduced.get('scroll')!r} "
            + (f"examples={json.dumps(reduced.get('transitions') or [], ensure_ascii=False)[:150]}"
               if _motion(reduced) else ""))

        reported[label] = (f"no-preference:{_motion(normal)} reduce:{_motion(reduced)} "
                           f"nodes={reduced.get('elements')}")
        if _motion(normal) == 0:
            reported[label] += " NO_MOTION_DECLARED_IN_EITHER_BRANCH"

    # The instrument's own anti-vacuity check: some surface has to move while the preference is off, or every
    # `reduce transitions=0` above is a statement about a page that never had motion to flatten.
    moving = sorted([label for label, m in measured.items() if _motion(m.get("normal") or {}) > 0])
    add("some_surface_moves_when_the_preference_is_off", bool(moving),
        f"moving_surfaces={json.dumps(moving) if moving else 'none — the floor would be unmeasurable here'}")

    return {"passed": all(c["pass"] for c in checks), "checks": checks, "reported": reported,
            "surfaces": sorted(measured),
            "coverage": {"motionlessBothBranches": sorted(
                [label for label, m in measured.items()
                 if _motion(m.get("normal") or {}) == 0 and _motion(m.get("reduce") or {}) == 0])}}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=str(ROOT))
    ap.add_argument("--surface", action="append", default=None,
                    help=f"which surfaces to census (default: {' '.join([PROFESSIONAL['label'], *SHELL_SURFACES])})")
    ap.add_argument("--json-out", default=None)
    args = ap.parse_args()

    wanted = args.surface or [PROFESSIONAL["label"], *SHELL_SURFACES]
    root = Path(args.root).resolve()
    # Bad names are rejected before any disk or browser lookup: a typo is a typo regardless of what this
    # machine happens to have built.
    try:
        specs = surfaces(hud, wanted)
    except RuntimeError as exc:
        print(f"REDUCED_MOTION_FLOOR_GATE_NOT_RUN {exc}")
        return 2

    dist = root / "apps" / "observer" / "frontend" / "dist"
    if not (dist / "index.html").is_file():
        print(f"REDUCED_MOTION_FLOOR_GATE_NOT_RUN DIST_ABSENT {dist}")
        return 3
    browser = geometry.find_browser()
    if not browser:
        print("REDUCED_MOTION_FLOOR_GATE_NOT_RUN BROWSER_NOT_FOUND "
              "set WL_CHROME to a Chrome/Edge binary; a named category is not a pass")
        return 3

    geometry.OUT_DIR.mkdir(parents=True, exist_ok=True)
    u19 = geometry.load_u19()
    fixture = hud.SnapshotFixture(dist)
    fixture.start()
    measured: dict[str, dict] = {}
    try:
        for spec in specs:
            box: dict = {}

            def hook(cdp, _box=box) -> None:
                _box.update(measure_surface(cdp))

            url = fixture.url_for(spec["query"])
            geometry.serve_and_eval(root, "/index.html", "%dx%d" % spec["size"],
                                    "JSON.stringify({ok: true})", browser, u19, None,
                                    viewport=spec["size"], serve_url=url, after_mount=hook,
                                    mount_selector=spec["mount"])
            if not box:
                print(f"REDUCED_MOTION_FLOOR_GATE_NOT_RUN NO_CENSUS[{spec['label']}] "
                      "the browser returned no reading for this surface")
                return 3
            box["minNodes"] = spec["minNodes"]
            box["url"] = url
            measured[spec["label"]] = box
    finally:
        fixture.stop_server()

    if not measured:
        print("REDUCED_MOTION_FLOOR_GATE_NOT_RUN NO_MEASUREMENT — no surface produced a census")
        return 3

    result = verdict(measured)
    result["startedAt"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    result["browser"] = browser
    result["servedBundle"] = bundle_provenance.describe(root)
    result["measured"] = measured
    result["residue"] = list(geometry.RESIDUE)
    result["portAnnouncedMismatch"] = list(geometry.ANNOUNCED_MISMATCH)

    out = Path(args.json_out) if args.json_out else (OUT_DIR / f"floor_{int(time.time())}.json")
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    for check in result["checks"]:
        print(f"{check['check']:<52} {'PASS' if check['pass'] else 'FAIL'} {check['detail'][:150]}")
    for label, state in result["reported"].items():
        print(f"REDUCED_MOTION_REPORTED {label}: {state}")
    print(f"REDUCED_MOTION_FLOOR_GATE_{'PASS' if result['passed'] else 'FAIL'} "
          f"surfaces={len(result['surfaces'])} checks="
          f"{sum(1 for c in result['checks'] if c['pass'])}/{len(result['checks'])} out={out}")
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
