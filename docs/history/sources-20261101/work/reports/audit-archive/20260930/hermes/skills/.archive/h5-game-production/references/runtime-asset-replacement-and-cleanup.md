# Runtime asset replacement and repository cleanup

## Exact-scope visual correction

When a user marks one baked element in supplied art (for example `7F→8F`), treat the marked pixels as the whole requested scope unless they explicitly broaden it.

1. Preserve the authored scene, cabin, doors, arrows, perspective, scanlines and composition.
2. Remove only the baked text/number pixels from the source asset, preferably with a bounded mask plus inpainting.
3. Process every directional/resolution variant that contains the same defect.
4. Do not replace the scene with a procedural black frame.
5. Do not add a broad black strip/card or a second redundant runtime readout.
6. Verify the repaired source images visually before changing the renderer.
7. Rebuild generated platform copies from source; do not hand-maintain them.

If a full text-free replacement pack is supplied, use it instead of inpainting:

- Verify state IDs, counts and dimensions first.
- Copy only replacement directories named by the handoff.
- Remove legacy source-specific crop/mask code (`cropTop`, `cropBottom`, broad HUD shades) so safe-cropped replacement art is drawn with normal cover behavior.
- Keep HUD labels, floor values, camera IDs and timecodes runtime-owned.
- Hash-compare generated platform assets against source after the official build scripts.

## Audio handoff integration

For BGM handoffs:

- Verify channel count, sample rate, bit depth, duration and peak level before copying.
- Use a dedicated looping music context, separate from short SFX contexts.
- Start only after the first user gesture.
- Switch calm/pressure tracks from runtime state without parallel loops.
- Link mute, ads, lifecycle hide/show, pause/resume and game-over.
- Build platform copies from the source audio directory and count outputs.

## Evidence-driven capacity cleanup

Classify disk use before deleting:

1. **Ignored, reproducible caches** — `.tmp`, `.gradle`, Android build outputs: delete safely after recording sizes.
2. **Installed-tool download archives** — remove after confirming installed tool binaries exist.
3. **Duplicate portable apps** — remove only if another verified installation exists and project scripts do not reference the portable path.
4. **Versioned toolchains** — retain the version required by project locks; remove older unreferenced versions only after exact reference search.
5. **Tracked reference assets** — delete only after checking code, CSS, tests, manifests and docs; update every stale path and inventory assertion.
6. **Generated platform projects** — retain when they are documented import-ready/release artifacts or test fixtures; do not equate duplication with uselessness. For an ignored intermediate project such as `android-minigame/`, delete the local copy after proving `build.js <target>` recreates it. For tracked WebView staging files that a prepare script deletes and rewrites deterministically, ignore/untrack the whole staging directory while retaining the native project shell.
7. **Release screenshots/evidence** — preserve unless explicitly asked to remove.

### Zero-state regeneration proof

Generated-output cleanup is complete only when tested from an absent tree:

1. Confirm the official build/install path invokes the prepare script automatically.
2. Delete the ignored intermediate and staging directories.
3. Run the narrow prepare/runtime test from that zero state and verify expected files/content.
4. Run the full suite once if tracked ignore rules or inventory tests changed.
5. Delete the regenerated ignored copies again before measuring final disk usage.

Do not run a heavyweight APK/Gradle build after deleting its caches unless that specific proof is required; it can immediately recreate hundreds of MiB. State the most recent full-build evidence and run the lightweight source/staging gate instead.

Keep functional asset replacement and capacity deletion in separate commits. If a late audit finds another deterministic generated layer, use a second cleanup commit rather than rewriting or mixing the already verified asset change.

Safety sequence:

- List exact repository-relative deletion targets first.
- Guard against absolute paths and `..` traversal.
- Delete only inside the repository.
- Run stale-reference search.
- Run tests, schema checks and target builds without immediately recreating large caches that were intentionally removed.
- Report before/after byte counts and explain the remaining large directories.

A cleanup should optimize **working-tree capacity without destroying build capability**. If a large directory is a required portable SDK/JDK/Gradle stack, preserve it and state the optional trade-off separately.