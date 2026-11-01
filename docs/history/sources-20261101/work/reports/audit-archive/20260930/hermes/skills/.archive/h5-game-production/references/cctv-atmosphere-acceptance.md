# CCTV Atmosphere Acceptance

Use this after a user rejects a Canvas surveillance/horror screen as “ugly,” “flat,” or “without atmosphere.” This is a visual-composition gate, not a package-size report.

## Failure model

A CCTV pass can be technically wired yet visually fail in three distinct ways:

1. **Registered only** — the manifest/preload contains scene and overlay assets.
2. **Drawn only** — the scene image appears, but the screen still reads as a clean dashboard.
3. **Composed** — scene, monitor treatment, runtime HUD, motion, and threat response form one surveillance surface.

Do not report stage 1 or 2 as visual completion.

## Required inspection

- Trace `manifest → preload → getOverlay/getV5Cctv → renderer draw order`.
- Confirm `frame`, `scanlines`, `vignette`, `glitch`, `alert`, and `sweep` are actually drawn, not merely named.
- Confirm all treatment layers are clipped to CCTV bounds and cannot darken or cover controls.
- Confirm all time-based layers use the pausable motion timestamp; no independent wall-clock animation in renderer effects.
- Confirm scene aspect fit is deliberate (`cover`, contain, or fixed ratio) and no duplicate scene is stacked behind it.
- Keep runtime HUD inside the scene semantic: `REC`, camera ID, night-watch status, signal state. Never bake answer text or fixed floor values into art.

## Minimum horror/monitoring stack

For a calm surveillance state:

- text-free scene art;
- restrained scanlines;
- vignette/edge falloff;
- a subtle moving scan beam;
- recording indicator and camera label;
- a bounded monitor frame.

For an active threat:

- stronger chromatic/tint shift;
- red or amber edge pulse;
- bounded glitch/tear treatment;
- semantic alert cue and state-specific audio/haptic feedback;
- visible subject change or transition, not only border/noise.

Avoid turning every frame red or adding random noise as a substitute for art direction. Atmosphere should come from hierarchy, contrast, temporal behavior, and semantic state changes.

## Screenshot evidence

Capture the same viewport and state before/after. Quantitatively check:

- image dimensions unchanged;
- CCTV crop region has a meaningful pixel diff;
- calm and threat states are not pixel-identical;
- overlay changes stay inside CCTV crop;
- no black bars, duplicated subject, or covered action deck;
- runtime HUD remains readable at 393×852 and 360×640.

A diff proves that pixels changed, not that the result is good. Pair it with a human/user visual check and, when available, an official Developer Tool/device capture.

## Response discipline

When the user says the result is ugly, start by acknowledging the composition failure and name the concrete missing layer or hierarchy decision. Do not lead with test counts, package budget, or “assets loaded.” Fix one coherent visual slice, recapture, then run normal build/package gates.
