/* WORK-LAB Observer — fixed portable desktop component contract. */

"use strict";

const assert = require("assert");
const fs = require("fs");
const path = require("path");

const ROOT = path.resolve(__dirname, "..");
const CONFIG = path.join(ROOT, "src-tauri", "tauri.conf.json");
const CAPABILITIES = path.join(ROOT, "src-tauri", "capabilities", "default.json");

function run() {
  const config = JSON.parse(fs.readFileSync(CONFIG, "utf8"));
  const caps = JSON.parse(fs.readFileSync(CAPABILITIES, "utf8"));
  const windows = Object.fromEntries((config.app && config.app.windows || []).map((w) => [w.label, w]));
  let pass = 0;
  let fail = 0;

  function test(name, fn) {
    try {
      fn();
      console.log("  PASS  " + name);
      pass += 1;
    } catch (err) {
      console.log("  FAIL  " + name);
      console.log("        " + err.message);
      fail += 1;
    }
  }

  test("frontendDist points to the embedded local web frontend", () => {
    assert.strictEqual(config.build.frontendDist, "../frontend/dist");
  });

  // The configured entry URL is pinned verbatim so any drift fails loudly. The
  // query is additionally parsed because the cold-start UNKNOWN state is the
  // contract being tested: without a separate assertion, re-pinning this string
  // for an unrelated edit (a new param, a theme change) could silently drop
  // mode=UNKNOWN and still pass. shell=tauri is how the frameless shell declares
  // itself to the frontend, which has no other deterministic way to know it is
  // not a plain-browser entry.
  function query(url) {
    return new URL(url, "http://tauri.localhost").searchParams;
  }

  test("main window starts UNKNOWN and uses an opaque desktop canvas", () => {
    assert.strictEqual(windows.main.url,
      "index.html?view=full&mode=UNKNOWN&theme=dark&shell=tauri&surface=daily");
    assert.strictEqual(query(windows.main.url).get("mode"), "UNKNOWN");
    assert.strictEqual(query(windows.main.url).get("view"), "full");
    // 2026-10-24 (CL-08, owner 「完成全部前后端任务」): the desktop default entry IS the
    // daily shell, declared by surface=daily. shell=tauri stays because it is how the
    // frameless window declares itself — dropping it would leave the frontend guessing.
    assert.strictEqual(query(windows.main.url).get("surface"), "daily");
    assert.strictEqual(query(windows.main.url).get("shell"), "tauri");
    assert.strictEqual(windows.main.decorations, false);
    assert.strictEqual(windows.main.transparent, false);
  });

  test("panel window is a fixed compact component entry", () => {
    assert.strictEqual(windows.panel.url, "index.html?view=compact&mode=UNKNOWN&theme=dark&shell=tauri");
    assert.strictEqual(query(windows.panel.url).get("mode"), "UNKNOWN");
    assert.strictEqual(query(windows.panel.url).get("view"), "compact");
    assert.strictEqual(windows.panel.width, 440);
    // 680, not 780 (changed 2026-10-13, WUI-19 §7.1): a non-resizable window's declared size IS its
    // physical demand, so 780 logical needed 1560 physical at 200% display scaling and did not fit a
    // 2560x1392 work area. 680 needs 1360. The height and its floor move together -- a window whose
    // minHeight exceeded its height would be a different defect, not a tolerant one.
    assert.strictEqual(windows.panel.height, 680);
    assert.strictEqual(windows.panel.minWidth, 440);
    assert.strictEqual(windows.panel.minHeight, 680);
    assert.strictEqual(windows.panel.resizable, false);
    assert.strictEqual(windows.panel.alwaysOnTop, true);
    assert.strictEqual(windows.panel.skipTaskbar, true);
    assert.strictEqual(windows.panel.visible, false);
  });

  test("hud window is the CL-12 native narrow strip, docked and tray-toggled", () => {
    assert.strictEqual(windows.hud.url, "index.html?surface=hud&mode=UNKNOWN&theme=dark");
    assert.strictEqual(query(windows.hud.url).get("surface"), "hud");
    // The strip is its OWN surface: measured at 150 logical, the compact panel's
    // TopStatusBar pushes ten controls past the viewport while .app{overflow:hidden}
    // keeps scrollWidth at 150 — an unreachable control bar, not a narrow HUD.
    assert.ok(windows.hud.width >= 140 && windows.hud.width <= 160,
      "CL-12 demands a 140-160px native 窄窗, got " + windows.hud.width);
    assert.strictEqual(windows.hud.alwaysOnTop, true);
    assert.strictEqual(windows.hud.skipTaskbar, true);
    assert.strictEqual(windows.hud.decorations, false);
    assert.strictEqual(windows.hud.transparent, false);
    assert.strictEqual(windows.hud.visible, false);
    assert.strictEqual(windows.hud.resizable, true,
      "the panel must stay the only non-resizable declared window (label-resolution contract)");
    assert.ok(caps.windows.includes("hud"),
      "data-tauri-drag-region is inert on a label the capability does not cover");
  });

  test("the settings page quotes the panel size the shell actually declares", () => {
    // Measured 2026-10-13: the HUD's declared height moved 780 -> 680 for 200% display scaling, and this
    // user-visible label still said 440×780. A number on the production surface is a claim, and a claim
    // about a declared window belongs to the declaration -- so the label is compared with tauri.conf.json
    // instead of being trusted.
    const view = fs.readFileSync(path.join(ROOT, "frontend", "src", "views", "SettingsPrivacyView.tsx"), "utf8");
    const quoted = windows.panel.width + "×" + windows.panel.height;
    assert.ok(view.includes(quoted),
      "the settings page must state the declared panel size " + quoted +
      "; a stale one is a false claim on the production surface");
    assert.ok(!/44[0-9]×7[0-9]0/.test(view),
      "a second, older panel size is still written on the production surface");
  });

  test("portable bundle remains active without updater or mutation capability", () => {    assert.strictEqual(config.bundle.active, true);
    assert(!JSON.stringify(config).match(/updater|createUpdaterArtifacts/i));
    const permissions = JSON.stringify(caps.permissions || []);
    assert(!permissions.match(/shell|process|fs:allow|http:allow|os:allow/i));
  });

  // Tauri v2 denies every mutating window/webview command by default:
  // core:default carries only readers (is-maximized, inner-size, title…), so a
  // caption button that calls close() against an ungranted ACL rejects
  // asynchronously and the user just sees a dead button. Deriving the called
  // set from the shipped source is what keeps that from recurring — an
  // un-mapped new call, or a dropped grant, fails here rather than on someone's
  // desktop.
  const NATIVE_CALL_PERMISSIONS = {
    minimize: "core:window:allow-minimize",
    toggleMaximize: "core:window:allow-toggle-maximize",
    close: "core:window:allow-close",
    startDragging: "core:window:allow-start-dragging",
    setZoom: "core:webview:allow-set-webview-zoom",
  };

  function nativeCallsInFrontend() {
    const srcRoot = path.join(ROOT, "frontend", "src");
    const calls = new Map();
    const walk = (dir) => {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const fp = path.join(dir, entry.name);
        if (entry.isDirectory()) { walk(fp); continue; }
        if (!/\.(ts|tsx)$/.test(entry.name)) continue;
        const src = fs.readFileSync(fp, "utf8");
        const found = [
          ...[...src.matchAll(/\(await win\(\)\)\.(\w+)\(/g)].map((m) => m[1]),
          ...[...src.matchAll(/getCurrentWebview\(\)\.(\w+)\(/g)].map((m) => m[1]),
          ...( /data-tauri-drag-region/.test(src) ? ["startDragging"] : []),
        ];
        for (const c of found) {
          if (!calls.has(c)) calls.set(c, path.relative(ROOT, fp));
        }
      }
    };
    walk(srcRoot);
    return calls;
  }

  const nativeCalls = nativeCallsInFrontend();

  test("every native call the frontend makes maps to an ACL identifier", () => {
    const unmapped = [...nativeCalls.keys()].filter(
      (c) => !Object.prototype.hasOwnProperty.call(NATIVE_CALL_PERMISSIONS, c));
    assert.deepStrictEqual(unmapped, [],
      "add the permission identifier for: " + unmapped.join(", "));
  });

  test("the capability grants every native call the frontend makes", () => {
    const granted = new Set(caps.permissions || []);
    const missing = [...nativeCalls].filter(
      ([call, file]) => !granted.has(NATIVE_CALL_PERMISSIONS[call]))
      .map(([call, file]) => `${call} (${file}) → ${NATIVE_CALL_PERMISSIONS[call]}`);
    assert.deepStrictEqual(missing, [],
      "capability does not grant:\n        " + missing.join("\n        "));
  });

  // Both windows are frameless, so the top of the layout IS the edge of the OS
  // window: a rule with no vertical clearance puts content directly against the
  // border, which is exactly what the owner found by eye after a visual audit
  // that only ever measured overflow to the right and bottom. These assertions
  // keep the measured clearance from being zeroed again.
  const SHELL_CSS = fs.readFileSync(
    path.join(ROOT, "frontend", "src", "skins", "l10b-shell.css"), "utf8");

  function px(property, where) {
    const block = SHELL_CSS.match(where);
    if (!block) return null;
    const found = new RegExp(property + ":\\s*(-?[\\d.]+)px").exec(block[0]);
    return found ? parseFloat(found[1]) : null;
  }

  test("the frameless shell keeps the top row clear of the window edge", () => {
    const fixedCluster = /\.winctl\s*\{[^}]*position:\s*fixed[^}]*\}/;
    const top = px("padding-top", /\.topbar\s*\{[^}]*padding-top[^}]*\}/);
    const bottom = px("padding-bottom", /\.topbar\s*\{[^}]*padding-bottom[^}]*\}/);
    const clusterTop = px("top", fixedCluster);
    const clusterRight = px("right", fixedCluster);
    for (const [name, value] of [[".topbar padding-top", top],
                                 [".topbar padding-bottom", bottom],
                                 [".winctl top", clusterTop],
                                 [".winctl right", clusterRight]]) {
      assert(typeof value === "number", `${name} is not declared in px`);
      assert(value >= 10, `${name} = ${value}px gives a frameless window no clearance`);
    }
  });

  // B-1 (UI-CHECK-20261006, blocker): b10.css hides the whole action strip under
  // 840px, which strands theme / compact / Context / notifications on a narrow
  // window and on touch. The repair lives in the shell layer because D-11 pins
  // b10.css verbatim, so it only holds while the shell is imported AFTER b10 and
  // re-declares the same selector at the same specificity. That ordering is the
  // fix — nothing else about it is load-bearing — so the ordering is what gets
  // pinned, and it is the kind of thing a later "cleanup" silently breaks.
  test("narrow screens keep the top action cluster reachable (b10 hide is overridden)", () => {
    const B10 = fs.readFileSync(path.join(ROOT, "frontend", "src", "skins", "b10.css"), "utf8");
    const shellBlock = /\.top-actions\s*\{[^}]*display:\s*flex/.exec(SHELL_CSS);
    assert(shellBlock, "the shell never re-shows .top-actions under the narrow breakpoint");
    assert(/\.top-actions\{display:none\}/.test(B10.replace(/\s+/g, "")),
      "b10.css no longer hides .top-actions; re-read which layer the fix belongs to");
    const MAIN = fs.readFileSync(path.join(ROOT, "frontend", "src", "main.tsx"), "utf8");
    const b10At = MAIN.indexOf("skins/b10.css");
    const shellAt = MAIN.indexOf("skins/l10b-shell.css");
    assert(b10At >= 0 && shellAt >= 0, "both skin imports must exist in main.tsx");
    assert(shellAt > b10At,
      "l10b-shell.css must be imported after b10.css or its unlayered override loses");
  });

  // N-1: the Overview lane has no registry entry, so its label was written by
  // hand in three files; three literals can disagree with nobody noticing.
  test("the overview lane label has exactly one source", () => {
    const REGISTRY = fs.readFileSync(
      path.join(ROOT, "frontend", "src", "lib", "viewRegistry.ts"), "utf8");
    assert(/export const OVERVIEW_LABEL\s*=\s*'[^']+'/.test(REGISTRY),
      "viewRegistry.ts must export OVERVIEW_LABEL");
    const offenders = ["App.tsx", "components/layout/Sidebar.tsx", "views/OverviewView.tsx"]
      .map((rel) => [rel, fs.readFileSync(path.join(ROOT, "frontend", "src", rel), "utf8")])
      .filter(([, body]) => /['\"]总览['\"]/.test(body))
      .map(([rel]) => rel);
    assert.deepStrictEqual(offenders, [],
      "overview label hardcoded again in: " + offenders.join(", "));
  });

  // N-2: CompactHUD claimed 320px-safe while pinning four equal tracks inline,
  // which overrode the shell's fluid auto-fit grid and its 820px container
  // collapse. Grid geometry belongs to the shell, not to a view.
  test("the compact HUD leaves KPI grid geometry to the shell", () => {
    const HUD = fs.readFileSync(
      path.join(ROOT, "frontend", "src", "views", "CompactHUD.tsx"), "utf8");
    assert(!/gridTemplateColumns/.test(HUD),
      "CompactHUD.tsx sets gridTemplateColumns inline and defeats the shell's fluid .kpi-grid");
    assert(/grid-template-columns:\s*repeat\(auto-fit/.test(SHELL_CSS),
      "the shell must keep a fluid auto-fit .kpi-grid");
    assert(/@container page \(max-width:\s*820px\)\s*\{\s*\.kpi-grid/.test(SHELL_CSS),
      "the container-driven two-column collapse for .kpi-grid is gone");
  });

  // An error boundary that exists but is never mounted protects nothing. Both
  // layouts render their lane inside <section id="content">, so every one of those
  // sections has to open with the boundary.
  test("every content section renders inside an error boundary", () => {
    const APP = fs.readFileSync(path.join(ROOT, "frontend", "src", "App.tsx"), "utf8");
    assert(/import \{ LaneErrorBoundary \} from '@\/components\/ui\/lane-error-boundary'/.test(APP),
      "App.tsx does not import LaneErrorBoundary");
    const sections = (APP.match(/<section className="content" id="content">/g) || []).length;
    const guarded = (APP.match(
      /<section className="content" id="content">\s*<LaneErrorBoundary[^>]*>/g) || []).length;
    assert(sections >= 2, `expected a content section in both layouts, found ${sections}`);
    assert(guarded === sections,
      `${guarded} of ${sections} content sections open with LaneErrorBoundary`);
  });

  console.log("\n==== WORK-LAB desktop component contract tests ====");
  console.log(`TOTAL: ${pass} passed, ${fail} failed`);
  return { pass, fail };
}

if (require.main === module) {
  const result = run();
  if (result.fail) process.exitCode = 1;
}

module.exports = { run };
