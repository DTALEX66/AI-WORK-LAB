# Canvas UI Art-Direction Recovery

Use this when a native mini-game technically loads supplied assets but the user says the result is worse than the original design.

## Failure pattern

A mechanically valid integration can still fail visually when it:

- inserts artwork into the old renderer layout instead of porting the supplied composition;
- gives secondary telemetry/logs more area than the core play surface;
- displays every action at once, producing a dense admin dashboard;
- paints over authored button sprites until only a border remains;
- stretches landscape CCTV art into a portrait slot;
- ignores host chrome such as the Douyin top-right capsule;
- treats “asset files were drawn” as equivalent to “the art direction was preserved.”

The user correction to internalize is: **provided layout references and component packs are product requirements, not merely an asset pool.** If the original/H5 version is visibly stronger, use it as the composition baseline.

## Recovery workflow

1. **Establish visual ground truth**
   - Capture the strongest original/H5/reference screen and the current target screen at the same viewport.
   - Compare area ratios, hierarchy, button count, typography, spacing, and host safe areas—not only colors.

2. **Extract composition before coding**
   - Record approximate viewport shares for title, play surface, primary controls, telemetry, and logs.
   - Identify which components are primary, contextual, and secondary.
   - Preserve the dominant play surface. For a CCTV game, CCTV should visibly dominate the viewport.

3. **Map components semantically**
   - Use a complete authored sprite only when its icon/text/state matches the live action.
   - Do not use a “close door” sprite as generic chrome for “open,” “restart,” or “inspect.”
   - If no semantic match exists, render a neutral dynamic control rather than showing a wrong icon.

4. **Reduce simultaneous controls**
   - Keep a compact primary deck (commonly four keys).
   - Promote the currently recommended action into the primary deck.
   - Move the remaining operations into a reachable paged drawer with explicit next/back controls.
   - During binary classification, show two large decision buttons instead of disabled clutter.

5. **Render media without distortion**
   - Use cover-crop for surveillance art when a taller target is required; preserve the central gameplay subject.
   - Use contain or authored aspect ratios for sprites whose outer silhouette matters.
   - Avoid layering baked scanlines/frame/vignette a second time; add only genuinely dynamic effects.

6. **Respect host chrome**
   - Reserve safe space for native capsules, status bars, notches, and review overlays.
   - Validate the countdown and other critical HUD elements in the official Developer Tool, not only a browser harness.

7. **Live visual QA loop**
   - Compile in the official tool.
   - Capture: start gate, decision state, normal primary deck, recommended-action replacement, secondary drawer, anomaly, and settlement.
   - Inspect readability, crop, semantic icon correctness, overlap, and touch reachability.
   - Iterate on the screenshot before running the final full gate.

## Acceptance criteria

- The target preserves or improves the hierarchy of the strongest supplied reference.
- Core gameplay occupies more visual area than logs and metadata.
- No wrong-action sprite is used as generic decoration.
- Primary controls are immediately readable; secondary controls remain reachable.
- Critical HUD avoids native platform chrome.
- Official-tool screenshots, not tests alone, prove the result.
- Runtime tests cover drawer navigation, semantic action dispatch, touch targets, and fallback rendering.

## Reporting discipline

When the user challenges visual quality, acknowledge the actual design failure directly. Do not answer with test counts or package-byte defenses first. Show the revised official-tool screenshot and explain which hierarchy/component decisions changed.