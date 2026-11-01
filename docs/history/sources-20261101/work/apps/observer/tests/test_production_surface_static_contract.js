/* WORK-LAB Observer — production-surface static contracts (U03 cutover step 1).
   The legacy tree guarded these properties with tests/test_read_only_surface.js and
   tests/test_responsive_contract.js, which read web/index.html and web/styles/*.css.
   The production surfaces are frontend/index.html plus frontend/src/skins/*.css and
   frontend/src/**, so the same guarantees have to be pinned there before apps/observer/web
   can be retired — otherwise deleting the legacy UI deletes the only assertions that hold
   the read-only and no-fabrication rules. Static checks, runnable without a browser. */

"use strict";

const fs = require("fs");
const path = require("path");

const FRONTEND = path.join(__dirname, "..", "frontend");
const SRC = path.join(FRONTEND, "src");

let pass = 0, fail = 0;
function t(name, fn) {
  try { fn(); console.log("  PASS  " + name); pass += 1; }
  catch (err) { console.log("  FAIL  " + name); console.log("        " + err.message); fail += 1; }
}
function assert(cond, msg) { if (!cond) throw new Error(msg); }
function read(rel) { return fs.readFileSync(path.join(FRONTEND, rel), "utf-8"); }

function walk(dir, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) { if (entry.name !== "node_modules") walk(full, out); }
    else out.push(full);
  }
  return out;
}

const SUB_FLOOR_RULE = /([^{}]+)\{([^}]*)\}/g;
const FONT_SIZE_DECL = /font-size:\s*(\d+(?:\.\d+)?)px/;
const TYPE_FLOOR_PX = 12;

function subFloorRules(css) {
  // Every rule in the sheet that sets text below the DESIGN.md floor. Comments are stripped first:
  // these sheets document the numbers they fix (`b10 pins .brand small{font-size:10px}`), and an
  // explanation is not a declaration. Without the strip the guard could report a rule that paints
  // nothing, which is how a documentation edit reads as a legibility violation.
  const stripped = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const found = [];
  for (const [, selector, body] of stripped.matchAll(SUB_FLOOR_RULE)) {
    const m = FONT_SIZE_DECL.exec(body);
    if (m && parseFloat(m[1]) < TYPE_FLOOR_PX) {
      found.push({ selector: selector.replace(/\s+/g, " ").trim(), px: parseFloat(m[1]) });
    }
  }
  return found;
}

function microRoleFindings(css, allowed) {
  // Two questions, because an allowlist answers only one of them today:
  //   offenders — sub-floor text that no named role claims (a real violation), and
  //   dead — named roles that no sub-floor text matches (a permission nobody granted and nobody
  //           needs, which silently outlives the bug it was written for and exempts the next one).
  const rules = subFloorRules(css);
  return {
    count: rules.length,
    offenders: rules.filter((r) => !allowed.some((re) => re.test(r.selector)))
                    .map((r) => r.selector + " → " + r.px + "px"),
    dead: allowed.filter((re) => !rules.some((r) => re.test(r.selector))).map(String),
  };
}

function run() {
  const html = read("index.html");
  const shell = read("src/skins/l10b-shell.css");
  const base10 = read("src/skins/b10.css");
  const skins = shell + base10;
  const TESTDIR = path.join(SRC, "test") + path.sep;
  // src/test/** holds vitest-only helpers (setup.ts, the shared snapshot fixture). They are not the
  // shipped front, so a snapshot literal living there is not "embedded in production source" — but the
  // exclusion below is only honest while nothing in the front imports them, which the next assertion
  // proves rather than assumes.
  const sources = walk(SRC).filter((p) => /\.(ts|tsx)$/.test(p) && !/\.test\.(ts|tsx)$/.test(p)
                                      && !p.startsWith(TESTDIR));
  const appCode = sources.map((p) => fs.readFileSync(p, "utf-8")).join("\n");
  // The editor lane persists a canvas model locally and is the one sanctioned
  // storage user. Paths come back with the platform separator, so normalise
  // before matching — an un-normalised test excluded nothing and reported the
  // editor's own four uses as a violation of a rule it never broke.
  const isEditor = (p) => /views[/\\]WorkflowEditorView/.test(p);
  const uiCode = sources.filter((p) => !isEditor(p))
    .map((p) => fs.readFileSync(p, "utf-8")).join("\n");

  console.log("\n==== WORK-LAB Observer production-surface static contracts ====");

  t("the production entry loads no remote runtime, framework or CDN", () => {
    const remote = [...html.matchAll(/(?:src|href)\s*=\s*["']([^"']+)["']/g)]
      .map((m) => m[1]).filter((u) => /^https?:\/\//i.test(u));
    assert(remote.length === 0, "remote references in index.html: " + remote.join(", "));
  });

  t("the skins never reach out to the network", () => {
    const urls = skins.match(/url\(\s*["']?https?:\/\//gi) || [];
    assert(urls.length === 0, urls.length + " remote url() references in the skins");
    const imports = skins.match(/@import\s+["']?https?:/gi) || [];
    assert(imports.length === 0, "remote @import in the skins");
  });

  t("read-only: no write request leaves the UI layer", () => {
    const mutating = appCode.match(/method\s*:\s*["'](POST|PUT|PATCH|DELETE)["']/gi) || [];
    assert(mutating.length === 0, "mutating HTTP methods in src: " + mutating.join(", "));
    const verbs = [...appCode.matchAll(/\bfetch\s*\(\s*[^,)]+,\s*\{([\s\S]*?)\}\s*\)/g)];
    const undeclared = verbs.filter((m) => !/method\s*:\s*["']GET["']/.test(m[1]));
    // An implicit GET is not enough for a read-only surface: this is the
    // "only GET fetch exists" half of the legacy contract, and it had no owner
    // until the production read started declaring its method explicitly.
    assert(verbs.length > 0, "the scan found no options-bearing fetch — re-check it before trusting this PASS");
    assert(undeclared.length === 0,
      "fetch with an options object must declare method: 'GET' — offenders: "
      + undeclared.map((m) => m[1].replace(/\s+/g, " ").slice(0, 48)).join(" | "));
  });

  t("read-only: no credential, auth store or env read in the UI layer", () => {
    const hits = [];
    for (const pattern of [/process\.env/, /\bauthorization\b/i, /\bbearer\s+[A-Za-z0-9._-]{6,}/,
                           /\bapi[_-]?key\b/i, /\bcookie\b/i, /auth\.json/i]) {
      if (pattern.test(uiCode)) hits.push(String(pattern));
    }
    assert(hits.length === 0, "forbidden reads present: " + hits.join(", "));
  });

  t("theme and layout state never persist to web storage", () => {
    const storage = uiCode.match(/localStorage|sessionStorage/gi) || [];
    assert(storage.length === 0, storage.length + " web-storage uses outside the editor lane");
  });

  t("responsive: horizontal page overflow is suppressed by construction", () => {
    assert(/overflow-x:\s*hidden/.test(shell) || /min-width:\s*0/.test(shell),
      "the shell neither hides horizontal overflow nor gives flex children min-width:0");
    assert(/\.main\s*\{\s*min-width:\s*0/.test(shell) || /min-width:\s*0/.test(shell),
      "the content column can be widened past the viewport by an unshrinkable child");
  });

  t("responsive: numeric columns use tabular numerals", () => {
    assert(/font-variant-numeric:\s*[^;]*tabular-nums|tabular-nums/.test(skins),
      "no tabular-nums in the production skins, so numbers jitter between rows");
  });

  t("responsive: long CJK, SHA and token strings wrap instead of overflowing", () => {
    assert(/overflow-wrap:\s*(anywhere|break-word)|word-break:\s*break-all/.test(shell),
      "no wrapping rule for long unbroken strings");
  });

  t("motion: a reduced-motion preference is honoured", () => {
    assert(/prefers-reduced-motion/.test(skins),
      "neither skin reacts to prefers-reduced-motion");
  });

  t("legibility: no rule sets the page or lane base text below 12px", () => {
    // The skins inherit the UA base (16px) and never shrink it; what the rule
    // has to catch is a future `body{font-size:10px}` or a container that drops
    // the reading level of real content. Comments are stripped for the same reason
    // as the micro-role check below: the sheets quote the numbers they fix.
    const rules = skins.replace(/\/\*[\s\S]*?\*\//g, "");
    const offenders = [];
    for (const [, selector, body] of rules.matchAll(/([^{}]+)\{([^}]*)\}/g)) {
      const m = /font-size:\s*(\d+(?:\.\d+)?)px/.exec(body);
      if (!m) continue;
      if (/^\s*(?:html|body)\s*$/.test(selector.trim()) && parseFloat(m[1]) < 12) {
        offenders.push(selector.trim() + " { " + m[0] + " }");
      }
    }
    assert(offenders.length === 0, "base text under 12px: " + offenders.join(", "));
    const bodyDeclared = /(?:^|\})\s*(?:html|body)[^{}]*\{[^}]*font-size/.test(rules);
    assert(!bodyDeclared || parseFloat(/(?:html|body)[^{}]*\{[^}]*font-size:\s*(\d+(?:\.\d+)?)/
      .exec(rules)[1]) >= 12, "body base font-size dropped below 12px");
  });

  t("legibility: every sub-12px declaration is a named micro role, and every named role is real", () => {
    // Small type survives in exactly one place: the brand lockup caption, which `b10.css` pins at
    // 10px verbatim (decision D-11 forbids editing it) and which `l10b-shell.css` overrides to the
    // floor. This used to carry seven roles — `.winctl-zoom`, `.load-strip`, `.topbar-brand-word`,
    // `.tag`, `.badge`, `.kpi small` besides the brand caption — because each of them had once
    // measured sub-floor. After the floor sweep none of them do, so six entries were permissions
    // nobody held: the assertion still printed "no offenders" while the list rotted, and a new 10px
    // paragraph inside any of those six selectors would have passed for the same reason.
    // A permission that matches nothing is now as much a failure as a violation.
    const ALLOWED = [/\.brand\s+small/];
    const found = microRoleFindings(skins, ALLOWED);
    assert(found.count > 0, "no sub-12px rule anywhere in the sheets: this test's premise is gone, "
      + "retire it deliberately rather than letting it pass on an empty set");
    assert(found.offenders.length === 0,
      "small text outside the micro roles:\n        " + found.offenders.join("\n        "));
    assert(found.dead.length === 0,
      "stale micro-role permissions that no sub-12px declaration matches any more: "
      + found.dead.join(", ") + " — drop them, or the next sub-floor rule under one of these "
      + "selectors is exempted by a permission nobody granted");
  });

  t("the micro-role detector sees a planted violation, a stale permission, and a quoted number", () => {
    // Negative controls for the assertion above: a check that cannot go red is not a check.
    const planted = microRoleFindings(".prose{font-size:10px}", [/\.brand\s+small/]);
    assert(planted.count === 1 && planted.offenders.length === 1 && planted.dead.length === 1,
      "a 10px paragraph outside the roles was not reported: " + JSON.stringify(planted));

    const permitted = microRoleFindings(".brand small{font-size:10px}", [/\.brand\s+small/]);
    assert(permitted.offenders.length === 0 && permitted.dead.length === 0,
      "the one legitimate role does not satisfy its own detector: " + JSON.stringify(permitted));

    const stale = microRoleFindings(".brand small{font-size:10px}",
                                   [/\.brand\s+small/, /\.badge\b/]);
    assert(stale.offenders.length === 0 && stale.dead.length === 1 && stale.dead[0] === "/\\.badge\\b/",
      "a permission matching nothing went unnoticed: " + JSON.stringify(stale));

    // The sheets document the numbers they fix. A comment must never read as a declaration.
    const quoted = microRoleFindings("/* b10 pins .old{font-size:9px} */ .x{color:red}", []);
    assert(quoted.count === 0, "a number inside a comment was measured as a rule: "
      + JSON.stringify(quoted));
  });

  // --- file-level halves of the projection-truth ports (U03 step 1b) ---
  // The behavior halves are in frontend/src/lib/projectionTruthContract.test.ts;
  // these three need the disk, which the frontend tsconfig (no @types/node) must
  // not do from a test.
  t("the typed front model declares the v3 core keys, and only the named optional ones", () => {
    const types = fs.readFileSync(path.join(SRC, "types.ts"), "utf-8");
    const block = /export interface SnapshotV3 \{([\s\S]*?)\n\}/.exec(types);
    assert(block, "types.ts must declare SnapshotV3");
    const declared = [...block[1].matchAll(/^\s+(\w+)(\??):/gm)]
      .map((m) => ({ name: m[1], optional: m[2] === "?" }));
    const CORE = ["schemaVersion", "revision", "generatedAt", "sourceWatermark", "transport",
                  "coverage", "governance", "workspace", "projects", "executions", "tasks",
                  "tokenSummary", "git", "ci", "sourceRefs"];
    for (const k of CORE) {
      assert(declared.some((d) => d.name === k && !d.optional), "types.ts must declare required " + k);
    }
    // Each optional key is optional for the same reason: the producer omits it when its source was not
    // read, and an empty array would claim "the source was read and declared nothing". Naming the set here
    // is the point -- an unlisted new optional key means somebody added a projection without deciding
    // whether absent and empty are different statements.
    // artifactHandles/artifactHandlesSummary are listed as a pair because the producer builds them as one
    // conditional spread (snapshot_api.py:115-118): absent means no caller supplied an enumeration, while []
    // means the walk enumerated nothing. snapshot_validator.py:366-377 refuses a summary without its list and
    // a list without its scope, so the type must never let a reader hold one of the two alone.
    // collectors is absent-only by the same rule: composition_root._collector_delivery_rows returns None when
    // the health table cannot be read (its `except` branch exists precisely so an unreadable source is not
    // reported as "no collectors"), and snapshot_api.py:121 spreads the key only when it is not None.
    // operationProgress / isolatedTrials (WUI-21, 2026-07-12) are absent-only for a different reason: they
    // carry the worklab/operation-progress/v1 and worklab/isolated-trial/v1 contracts verbatim, and the
    // producer omits the whole section when it could not read its source. An empty array there would claim
    // "the section was read and it is empty" -- the false negative the WUI-19 audit turned up -- so the key
    // is optional in the type AND omitted from the spread when its source was unreadable.
    // issues / issuesSummary (问题中心, 2026-10-22) are absent-only under the artifactHandles rule: the
    // producer (issue_projection.load_issues) returns (None, None, reason) when no source answered, and
    // snapshot_api spreads the pair together or not at all. An empty pair there would say "every source was
    // read and nothing is wrong", which is the opposite claim -- so both keys stay optional in the type even
    // though CL-07's IssueCenter now consumes them and both are in PINNED_REFINEMENT_PATHS: optionality here
    // is about the producer's absent/empty distinction, not about whether a lane renders the section.
    const OPTIONAL = ["software", "taskRecords", "adapterCapabilities",
                      "artifactHandles", "artifactHandlesSummary", "collectors",
                      "operationProgress", "isolatedTrials", "issues", "issuesSummary"];
    const optional = declared.filter((d) => d.optional).map((d) => d.name).sort();
    assert(JSON.stringify(optional) === JSON.stringify([...OPTIONAL].sort()),
      "optional keys must be exactly " + OPTIONAL.join("/") + ", got " + (optional.join(", ") || "none"));
  });

  t("no v3 snapshot literal is embedded in the production source", () => {
    // The legacy front hard-coded WlApi.FIXTURE and pinned its numbers to the
    // real fixture; the production front's only data source is the sidecar.
    // The scan is anchored on the assignment shape (a property holding the
    // schema id), so a validator COMPARING schemaVersion is not mistaken for an
    // embedded snapshot — the first version of this needle flagged api.ts's own
    // parseSnapshotPayload as a violation.
    const embedded = /[,{\s]schemaVersion\s*:\s*["']workflow\/snapshot\/v3["']/;
    const hits = sources
      .filter((p) => embedded.test(fs.readFileSync(p, "utf-8")))
      .map((p) => path.relative(SRC, p));
    assert(hits.length === 0, "files embedding a v3 snapshot literal: " + hits.join(", "));
  });

  t("the excluded test-helper directory stays unreachable from production source", () => {
    // The companion of the exclusion above: if any production file imported a snapshot from src/test/,
    // the literal would ship and the rule would be silent exactly where it mattered.
    const dir = path.join(SRC, "test");
    assert(fs.existsSync(dir), "src/test/ vanished, so the exclusion above hides nothing");
    const helpers = walk(dir).filter((p) => /\.(ts|tsx)$/.test(p));
    assert(helpers.length > 0, "src/test/ is empty; re-check the exclusion's purpose");
    for (const h of helpers) {
      const base = path.basename(h).replace(/\.(ts|tsx)$/, "");
      const shape = new RegExp("from\\s*['\"][^'\"]*/" + base + "['\"]|from\\s*['\"]\\.{1,2}/[^'\"]*" + base + "['\"]");
      const importers = sources.filter((p) => shape.test(fs.readFileSync(p, "utf-8")))
        .map((p) => path.relative(SRC, p));
      assert(importers.length === 0,
        path.relative(SRC, h) + " is imported by production source: " + importers.join(", "));
    }
    console.log("        (checked " + helpers.length + " test helpers)");
  });

  t("the production tree renders no currency amount and no subscription wording", () => {
    // Port of "cost shown as API estimate / USD, never as an exact bill" and
    // "subscriptionUsage=not-metered renders as 订阅未计量, never 0". v3 has no
    // monetary field at all, so the ported rule is stronger: money never appears.
    // The needle is a bill SHAPE, not a bare `$` — api.ts legitimately contains
    // `$1` inside a URL replacement.
    const money = /(?:US?\$|RMB|¥|￥)\s?\d|\$\s?\d+\.\d|\bUSD\b|人民币|账单|订阅/;
    const hits = sources.filter((p) => money.test(fs.readFileSync(p, "utf-8")))
      .map((p) => path.relative(SRC, p));
    const inMarkup = [];
    if (money.test(html)) inMarkup.push("index.html");
    if (money.test(skins)) inMarkup.push("skins");
    assert(hits.length === 0 && inMarkup.length === 0,
      "currency/subscription wording in: " + [...hits, ...inMarkup].join(", "));
  });

  t("the production entry declares a responsive viewport and the compact shell keeps its 320px floor", () => {
    // Ports of the legacy responsive checks that hold in the production tree but
    // had no owner: the entry meta tag, and the min-width floor that lives in
    // src/index.css (a file the skins-based cases above never read).
    const viewport = /<meta[^>]+name=["']viewport["'][^>]+content=["'][^"']*width=device-width[^"']*["']/i.test(html);
    assert(viewport, "frontend/index.html must declare width=device-width");
    const indexCss = fs.readFileSync(path.join(SRC, "index.css"), "utf-8");
    assert(/\[data-layout="compact"\][^{]*\{[^}]*min-width:\s*320px/.test(indexCss.replace(/\s+/g, " ")),
      "the compact shell must keep a 320px min-width floor in src/index.css");
  });

  t("the UI layer names no endpoint outside the loopback read-only v1 API", () => {
    // Port of "web tree has no server/backoffice entry points", re-anchored to
    // frontend/src. Anchored on a scheme: `@tauri-apps/api/window` is a module
    // path, not an endpoint, and the first version of this needle reported it as
    // one. If the scan finds no URL at all it fails — an empty result and a
    // clean result must not share a verdict.
    const urls = [...new Set(appCode.match(/https?:\/\/[A-Za-z0-9._~:/?#@!=;()[\]-]+/g) || [])];
    assert(urls.length > 0, "the scan matched no URL — re-check it before trusting this PASS");
    const ok = /^http:\/\/(?:127(?:\.\d{1,3}){3}|localhost|\[::1\])(?::\d+)?\/api\/v1\/(?:snapshot|events)$/;
    const offenders = urls.filter((u) => !ok.test(u));
    assert(offenders.length === 0, "non-loopback or non-v1 URLs in the UI layer: " + offenders.join(", "));
  });

  // --- U03 step 4: the visual/brand ports, and the read-only wording ---
  const BRAND = path.join(SRC, "assets", "brand");
  const BRAND_FILES = ["design-tokens.json", "observer-icons.svg",
                       "work-lab-observer-symbol.svg", "work-lab-observer-tray.svg", "app-icon-512.png"];

  t("the brand set is preserved inside the production tree, locally and structurally valid", () => {
    // Port of "R2 brand assets are checked in" + "R2 brand SVGs are local and
    // structurally valid". Without this the SVGs and the icon exist only under
    // web/assets/brand and would be lost with the tree they live in.
    for (const name of BRAND_FILES) {
      assert(fs.existsSync(path.join(BRAND, name)), "missing frontend/src/assets/brand/" + name);
    }
    for (const name of BRAND_FILES.filter((n) => n.endsWith(".svg"))) {
      const svg = fs.readFileSync(path.join(BRAND, name), "utf-8");
      assert(/^\s*<svg\b/.test(svg), name + " must start with an <svg> root");
      assert(!/<(?:image|use|script)[^>]+(?:href|src)=["']https?:\/\//i.test(svg),
        name + " references a remote asset");
    }
  });

  t("the production brand tokens declare the approved themes/views and the read-only constraints", () => {
    // Port of the R2 constraints assertion: this is the machine-readable place
    // the read-only iron law is stated for the visual layer.
    const tokens = JSON.parse(fs.readFileSync(path.join(BRAND, "design-tokens.json"), "utf-8"));
    assert(tokens.version === "2.0.0", "expected R2 token version 2.0.0, got " + tokens.version);
    assert(tokens.themes.includes("dark") && tokens.themes.includes("light"), "themes must list dark and light");
    assert(tokens.views.includes("full") && tokens.views.includes("compact"), "views must list full and compact");
    assert(tokens.constraints.readOnly === true, "constraints.readOnly must be true");
    assert(tokens.constraints.externalMutation === false, "constraints.externalMutation must be false");
    assert(tokens.constraints.modelSummary === false, "constraints.modelSummary must be false");
  });

  t("the read-only iron law and the no-fabrication rule are stated on the production surface", () => {
    // Port of "index uses only local visual assets and preserves read-only web
    // surface" — the wording half, which lived in web/index.html and moved into
    // the React shell without a named owner. Scoped to the two files that carry
    // the statements, so the scan cannot pass by matching its own test text.
    const views = read("src/views/Views.tsx");
    const app = read("src/App.tsx");
    assert(/只读/.test(views), "Views.tsx no longer states the 只读 rule");
    assert(/第二 Update Authority/.test(views), "Views.tsx no longer states the no-second-authority rule");
    assert(/不伪造|保持 UNKNOWN 真相/.test(app), "App.tsx no longer states the no-fabrication rule");
  });

  t("the compact surface keeps the four contracted truth readings", () => {
    // Port of "compact R2 hierarchy keeps four KPIs". The 2026-10-19 HUD fusion
    // retired the four-cell KPI strip: the same four truths now live in the hero
    // (Token), the facts row (项目), the hero meta (质量) and the status bar
    // (传输). The contract is the readings and their honest UNKNOWN paths, not
    // the retired cell array, so this asserts the producers instead.
    const hud = fs.readFileSync(path.join(SRC, "views", "CompactHUD.tsx"), "utf-8");
    assert(/const total = tt\?\.totalTokens \?\? null/.test(hud),
      "Token reading no longer comes from tokenSummary.totalTokens with a null fallback");
    assert(/const totalLabel = fmtExactTokens\(total\)/.test(hud),
      "Token reading no longer formats through fmtExactTokens");
    assert(/tokenSummary 未报告/.test(hud),
      "a missing token summary no longer prints its explicit UNKNOWN reason");
    assert(/String\(snap\.projects\.length\)/.test(hud),
      "项目 reading no longer comes from snap.projects");
    assert(/' · 质量 ' \+ fmtCostQuality\(tt\?\.costQuality\)/.test(hud),
      "质量 reading no longer comes from tokenTruth.costQuality");
    assert(/transportTruth\(snap, live, error\)/.test(hud),
      "传输 reading no longer comes from transportTruth");
    assert(/\{transport\}/.test(hud),
      "the transport reading is no longer rendered in the compact surface");
  });

  t("the shell collapses its grid layouts at its own declared breakpoints", () => {
    // Port of the legacy "truth cards reflow at the DPI-safe breakpoints". The
    // production breakpoints differ by design (container queries, not the 800/640
    // media queries), so the ported rule is the collapse behaviour, not the
    // numbers — and it reads the declaration value, so `1fr 1fr` cannot pass.
    const block = /@container page \(max-width: 760px\)\s*\{([\s\S]*?)\n\}/.exec(shell);
    assert(block, "l10b-shell.css has no @container page (max-width: 760px) block");
    const values = [...block[1].matchAll(/([^{}]+)\{([^}]*)\}/g)]
      .filter(([, sel]) => /\.two-col|\.split|\.three-col/.test(sel))
      .map(([, , body]) => /grid-template-columns:\s*([^;]+)/.exec(body))
      .filter(Boolean).map((m) => m[1].trim());
    assert(values.length > 0, "the 760px container block sets no grid-template-columns any more");
    assert(values.every((v) => v === "1fr"),
      "narrow layouts must collapse to one column, got: " + values.join(" | "));
    assert(/@media \(max-width: 840px\)/.test(shell), "the 840px viewport reflow is gone");
    assert(/min-width:\s*320px/.test(fs.readFileSync(path.join(SRC, "index.css"), "utf-8")),
      "the 320px floor disappeared from src/index.css");
  });

  t("the shell declares one unconditional two-track grid and one HUD track", () => {
    // 2026-10-07, superseded by the owner's desktop-first instruction (「先删除手机端其他端」).
    // The version of this contract below pinned `@media (min-width: 841px)` because the rail was
    // `display:none` underneath it, and a hidden rail is not a grid item — measured by CDP, `.main`
    // had been auto-placed into the 210px rail track. The mobile shell is now deleted instead of
    // accommodated: the rail is a grid item at every width the main window can take (its floor is
    // 900x600 in src-tauri/tauri.conf.json), so the two-track form is unconditional and the gate
    // that protects the original defect is that no `.app` track rule may sit behind a width query.
    const twoTrack = /^\.app\s*\{\s*grid-template-columns:\s*clamp\([^)]*\)\s+minmax\(0, *1fr\);\s*\}/m;
    assert(twoTrack.test(shell),
      "the shell must declare the rail+content two-track grid unconditionally");
    const hudTrack = /^\.app\.app-compact\s*\{\s*grid-template-columns:\s*minmax\(0, *1fr\);\s*\}/m;
    assert(hudTrack.test(shell), "the compact HUD must own a single shrinkable track");
    assert(!/@media \(min-width: 841px\)/.test(shell.replace(/\/\*[\s\S]*?\*\//g, "")),
      "a width query is gating the desktop shell again");
    // The property that actually mattered: the content track must be shrinkable, and the rail must
    // be re-shown inside the pinned skin's own <=840px hiding rule rather than by editing b10.css.
    assert(/\.main\s*\{\s*min-width:\s*0;?\s*\}/.test(shell), ".main must stay shrinkable");
    assert(/@media \(max-width: 840px\)\s*\{\s*\.sidebar\.sidebar-slot\s*\{\s*display:\s*flex/.test(shell),
      "the shell must re-show the rail inside the b10 width query it cannot edit");
    assert(/\.sidebar\{display:none\}/.test(skins),
      "b10.css must stay verbatim — the override, not the skin, carries the desktop decision");
  });

  t("a disabled control is visually disabled", () => {
    // b10.css ships no :disabled rule and keeps `button{cursor:pointer}` plus a
    // hover lift, so the permanently-disabled 导出状态 / 新建执行 buttons rendered
    // exactly like working ones. D-11 pins b10 verbatim, so the shell must carry
    // the affordance; this case is what keeps it from silently disappearing.
    assert(/button:disabled[^{]*\{[^}]*cursor:\s*not-allowed/.test(shell),
      "the shell declares no cursor:not-allowed affordance for disabled buttons");
    assert(/button:disabled[^{]*\{[^}]*opacity/.test(shell),
      "disabled buttons must be visually dimmed, not identical to enabled ones");
    assert(/button:disabled:hover[^{]*\{[^}]*transform:\s*none/.test(shell),
      "the b10 hover lift is still active on disabled buttons");
  });

  t("the declared read-only constraints agree between TypeScript and the brand JSON", () => {
    // Work-order 14's real point is not that the constraints are written down
    // somewhere, but that the two places they are written down cannot disagree:
    // tokens.ts is what the code imports, design-tokens.json is what non-TS
    // consumers (packaging, audits, the desktop shell) read.
    const tokens = fs.readFileSync(path.join(SRC, "theme", "tokens.ts"), "utf-8");
    const block = /export const VIEW_CONSTRAINTS\s*=\s*\{([\s\S]*?)\}/.exec(tokens);
    assert(block, "theme/tokens.ts must export VIEW_CONSTRAINTS");
    const declared = {};
    for (const [, key, val] of block[1].matchAll(/(\w+):\s*(true|false)/g)) declared[key] = val === "true";
    const json = JSON.parse(fs.readFileSync(path.join(BRAND, "design-tokens.json"), "utf-8"));
    for (const key of ["readOnly", "externalMutation", "modelSummary"]) {
      assert(key in declared, `VIEW_CONSTRAINTS does not declare ${key}`);
      assert(key in json.constraints, `design-tokens.json does not declare constraints.${key}`);
      assert(declared[key] === json.constraints[key],
        `${key} disagrees: tokens.ts=${declared[key]} design-tokens.json=${json.constraints[key]}`);
    }
    assert(declared.readOnly === true && declared.externalMutation === false && declared.modelSummary === false,
      "the iron law itself has changed: readOnly must be true, externalMutation and modelSummary false");
  });

  console.log(`TOTAL: ${pass} passed, ${fail} failed`);
  return { pass, fail };
}

if (require.main === module) {
  if (run().fail) process.exitCode = 1;
}

module.exports = { run };
