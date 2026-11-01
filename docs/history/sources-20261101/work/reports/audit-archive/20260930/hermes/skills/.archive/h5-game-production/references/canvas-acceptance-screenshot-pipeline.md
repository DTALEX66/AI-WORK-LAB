# Canvas Acceptance Screenshot Pipeline (Headless Chrome)

Deterministic pipeline for regenerating dual-size acceptance captures of a Canvas mini-game renderer outside the WeChat/Douyin dev tools. Developed for MINIGAME Game001 V5 (`.tmp/capture-v5.mjs` in that repo is a working instance).

## When to use

- Acceptance screenshots must prove real runtime rendering (not docs-only mockups).
- The renderer loads image assets via a manifest (`visual/cctv/...`, `visual/overlays/...`).
- Official dev tools are unavailable or the user asked for an automated evidence loop.

## Failure mode this prevents

A plain-browser harness where the renderer's image factory only probes `tt.createImage` / `wx.createImage` / `canvas.createImage` loads **zero images** — every capture shows the procedural fallback art while existence+size tests stay green. Always verify asset reachability (see step 5) before trusting captures.

## Pipeline

1. **Harness page** (`scripts/<game>-acceptance.html`) imports the PRODUCTION renderer and state factory — never a second UI copy. Requirements:
   - `<base href="../">` when asset manifest paths are package-relative (e.g. `visual/cctv/x.png` must resolve to the server-mapped asset root, not `/scripts/visual/...`).
   - `init(canvas, systemInfo, { imageFactory: () => document.createElement('img') })` — the renderer must accept an **injected** image factory. Do NOT add a `document` fallback inside the shipped renderer: platform no-DOM gates scan bundle text and block even guarded references.
   - Deterministic state injection per query param (`?round=identity&width=393&height=852`).
   - A re-render loop after `load` (e.g. 14 frames × 120 ms) so async image loads land before capture; set `document.documentElement.dataset.ready` when done.
   - Optional probe: `new Image()` on one manifest path writing `naturalWidth` into `dataset.imgOk` for load verification.

2. **Capture server** (plain `node:http`): serve the repo root plus a rewrite mapping the package asset prefix to the real asset directory:
   ```js
   if (url.pathname.startsWith('/visual/')) filePath = resolve(visualRoot, url.pathname.slice(8));
   ```
   Send `cache-control: no-store`. Listen on port 0 (ephemeral).

3. **Headless Chrome capture** (one process per shot, sequential):
   ```
   chrome --headless=new --disable-gpu --hide-scrollbars --mute-audio \
     --window-size=W,H --screenshot=out.png \
     --virtual-time-budget=8000 --user-data-dir=<tmp-profile> URL
   ```
   `--screenshot` mode is reliable; `--dump-dom` can hang on Windows — avoid it. Byte-size jump (e.g. 99 KB → 233 KB for the same scene) is a fast tell that real art replaced fallback art.

4. **PIL pixel verification** (acceptance, not eyeballing):
   - Compute the scene region from design coordinates × (cssWidth / designWidth).
   - Diff the region across rounds/states: **diff ≈ 0 across states = fallback art or broken state mapping** — fail the acceptance.
   - Check dark-pixel ratio and colorfulness for black-bar/dead-region regressions.

5. **Report** byte sizes, per-round diffs, and which gates ran (targeted tests → full suite → bundle build → platform strict check) before commit. Keep the capture script in the repo's ignored `.tmp/` unless it is promoted to a checked-in `scripts/` tool.

## Gotchas

- `const`/`let` module-level state in the renderer is fine for press-FX maps etc. — TDZ only matters during module evaluation, not per-frame rendering.
- Updating a source-locked test: when a test asserts the OLD drawing behavior (e.g. `ctx.drawImage(image, x, y, w, h)` stretch), flip the assertion in the same commit as the renderer change and say why in the test message.
- Protocol/copy truncation changes ripple into source-string tests — recount CJK characters in expected strings instead of guessing (a 14-char slice of `CAM-07 固定延迟两秒属于校准…` ends mid-word).
