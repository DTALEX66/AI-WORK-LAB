# Full-screen UI handoff → runtime Canvas assets

Use this when a visual handoff contains full-screen reference renders plus larger AI-generated source images.

## Classification

Split the handoff into three classes before copying anything:

1. **Full-screen reference renders** (`393x852/`, `360x640/`): layout/spacing/touch-target specifications only. Never ship them as runtime backgrounds because they bake text, buttons, scores, answers and one fixed state.
2. **Source images** (often 1024×1536): art-direction sources, not automatically runtime-safe. They may include a decorative cabinet, fixed icons or pseudo-controls even when they contain no text.
3. **Runtime scene crops**: only the authored scene region declared by the handoff (`SCENE` coordinates or equivalent), normalized to a reusable viewport size.

## Deterministic extraction

- Read the handoff renderer/script and reuse its exact crop coordinates.
- Crop first, then use `ImageOps.fit`/equivalent to the canonical CCTV size.
- Preserve subject and scene; exclude cabinet chrome, fixed controls and baked HUD.
- Apply only the same color/contrast treatment documented by the handoff.
- Save a checked-in script so extraction is reproducible.
- Visually inspect at least one extracted frame and verify: no text, no HUD, no cabinet buttons, no answer-bearing labels, subject intact.

## Runtime integration

- Register extracted scenes in the Canvas asset manifest as a separate family (for example `v5Cctv`), rather than overloading legacy machine-state IDs.
- Preload and expose a typed getter with a safe fallback.
- Ensure the custom IIFE bundler copies every manifest path into WeChat/Douyin outputs.
- Do not claim Phase/UI completion from manifest registration alone. Separate: source accepted → crop generated → manifest registered → renderer draws it → runtime state reaches it → official screenshot proves it.

## Cascading count tests

Adding N runtime assets often breaks several legitimate inventory assertions. Search and update all affected contracts, not just the first failure:

- source asset-pack file count;
- Canvas manifest/preload count;
- generated bundle image-source count;
- Android/WebView synchronized mobile CCTV count;
- package inventory/count checks.

Express counts semantically where possible (for example `24 legacy + 8 V5`) and assert a representative V5 filename, rather than replacing one unexplained magic number with another.

## Package budget

- Run the target strict checker after copying assets and record exact package bytes.
- Full-screen reference renders must remain outside packages.
- If close to the platform cap, stop adding duplicate resolutions; prefer one reusable crop, on-demand loading, stronger compression or a supported smaller canonical resolution.
- A green unit suite does not override package-byte evidence.

## Acceptance checklist

- [ ] Full-screen references are not in runtime packages.
- [ ] Runtime crops contain no baked text/HUD/fixed answers.
- [ ] Extraction is deterministic and scripted.
- [ ] Manifest, preload and target copy paths agree.
- [ ] Source, Canvas, bundle and Android inventory tests pass.
- [ ] Full project suite passes.
- [ ] Target strict checker reports zero runtime blockers and package below limit.
- [ ] UI remains explicitly incomplete until renderer/state/click paths and official screenshots are verified.
