# Douyin Canvas visual-asset integration audit

Use this reference when connecting a PNG state pack to a native Douyin/WeChat Canvas renderer and build pipeline.

## Read-only audit discipline

- Record `git status --short` before inspection and again before reporting.
- If files change during the audit, treat them as concurrent external edits: re-read the current diff and do not attribute them to the audit.
- Do not run a build merely to inspect it when the build writes generated directories. Inspect copy lists and generated-module order statically, or run only in an isolated temporary copy when execution is necessary.

## Establish the reachable state set

Do not copy an asset pack wholesale just because its manifest lists every image.

1. Trace the renderer to the shared state derivation function.
2. Preserve its exact condition precedence (success, game-over/escalation, active anomaly, cooldown, resource thresholds, movement, door, generic anomaly, baseline).
3. Enumerate all outputs reachable from current code.
4. Compare that set with the pack manifest and identify unreachable/future states.
5. Use the reachable set as the minimal copy manifest; add future assets only when the state machine can emit them.
6. Add tests that assert both the exact mapping and equality between the reachable-state set and build copy list.

A generic “the renderer calls `deriveVisualState()`” assertion is insufficient. Test every shipped anomaly ID and all precedence collisions, especially success versus game-over and high anomaly level versus a specific active anomaly.

## Audit the pixels, not just filenames

Inspect contact sheets and representative source images. Record:

- dimensions, encoded bytes, color mode, and hashes;
- baked HUD text, state labels, floor numbers, borders, scanlines, vignette, and alert effects;
- whether images conflict with dynamic runtime data;
- whether overlays would duplicate effects already baked into the state image;
- whether button sprites contain fixed language/action semantics.

Button art with baked “up”, “close”, or “scan” labels is not a generic recommended/default/disabled skin. Use it only for the exact action or defer it until a complete action-state mapping exists.

## Geometry and drawing

Compute the exact renderer destination rectangle from source layout code. Compare source and target aspect ratios.

- Avoid blind four-argument `drawImage(image, x, y, w, h)` when aspect ratios differ.
- Prefer centered cover cropping with the nine-argument overload:

```js
function drawImageCover(ctx, image, x, y, w, h) {
  const sourceAspect = image.width / image.height;
  const targetAspect = w / h;
  let sx = 0, sy = 0, sw = image.width, sh = image.height;
  if (sourceAspect > targetAspect) {
    sw = image.height * targetAspect;
    sx = (image.width - sw) / 2;
  } else {
    sh = image.width / targetAspect;
    sy = (image.height - sh) / 2;
  }
  ctx.drawImage(image, sx, sy, sw, sh, x, y, w, h);
}
```

If edge HUD/borders are baked into the image, quantify the crop and decide whether small distortion, letterboxing, or selective HUD reconstruction is safer.

## `tt.createImage` compatibility

For native mini games, inject an image factory from the same detected host API that created the Canvas:

```js
init(canvas, systemInfo, () => api.createImage());
```

This is safer and more testable than independently probing globals inside the renderer.

Register callbacks before assigning `src`. Prefer the official event API when present, with property callbacks as compatibility fallback:

```js
const image = imageFactory();
if (typeof image.addEventListener === 'function') {
  image.addEventListener('load', onLoad);
  image.addEventListener('error', onError);
} else {
  image.onload = onLoad;
  image.onerror = onError;
}
image.src = 'visual/cctv/state.png';
```

Use package-relative POSIX paths: no leading slash and no Windows separators. Deduplicate loads by path. Until load completes—or after failure—render a procedural fallback rather than a stale image for the wrong state or a blank frame.

Official reference: <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/api/javascript-api/drawing/picture/tt-create-image>

## Package size versus decoded memory

Measure both:

- encoded package bytes from actual files;
- decoded RGBA estimate: `width × height × 4 × simultaneously resident images`.

A set of compressed PNGs can fit the upload limit while consuming tens of MiB after decoding. Avoid eagerly decoding every state plus full-resolution overlays. Load the baseline immediately and other states on demand, or preheat only common transitions.

For current ordinary Douyin games, re-check the official package page before citing limits. The documented baseline at the time of this reference was: no subpackages ≤20 MB total; with subpackages ≤20 MB overall and ≤4 MB main package. Do not mix ordinary-game limits with Unity/instant-play limits.

Official reference: <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/guide/basic-function/subpackages/introduction>

## Build-chain closure

A source import is not enough when a custom bundler strips ESM syntax. Verify all of the following:

1. The asset-loader module appears before the renderer in the bundler module order.
2. Generated code contains the loader definition and no residual import.
3. The build copies every manifest path to the exact generated package-relative location.
4. Copying removes stale generated assets safely.
5. Reference-only contact sheets, desktop duplicates, metadata folders, and unreachable states stay out of the release package.
6. The untouched generated bundle starts under a minimal `tt` VM mock.

Missing the loader from the bundler list produces a runtime `ReferenceError` even though source-module tests pass. Missing the copy step silently forces every image into the fallback path.

## Minimum regression assertions

### Mapping

- baseline, movement, door, power, cooldown, success, failure, and every anomaly ID map exactly;
- precedence collisions are explicit;
- reachable IDs equal copied IDs.

### Loader

- one Image per path;
- load-before/get-null, load-after/get-image, error/get-null;
- both `addEventListener` and `onload/onerror` mocks;
- unknown IDs use a documented fallback path;
- no per-frame retry storm.

### Renderer

- loaded state selects the corresponding image;
- pending/error state uses procedural fallback;
- nine-argument crop geometry is asserted;
- baked overlays are not redundantly redrawn.

### Artifact

- generated loader definition exists before use;
- every manifest file exists in output;
- output contains exactly the intended assets;
- total package bytes remain below the current official limit;
- untouched generated bundle runs with `tt.createCanvas` and `tt.createImage` mocks through load and error callbacks.

Developer-tool verification should include baseline, representative anomalies, high-threat/failure, success, and one forced image-load failure.