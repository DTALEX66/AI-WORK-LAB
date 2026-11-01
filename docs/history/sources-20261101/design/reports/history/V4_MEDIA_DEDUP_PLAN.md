# ODA4-0106 Media Deduplication & Volume Governance

## Diagnosis (2026-08-07)

- Tracked media files: 363 (PNG/WAV/GIF/JPG under fixtures/domains/game-visual/)
- Unique content hashes: 111
- Duplicate groups: 90
- **Total duplicate waste: 106.55 MB** (matches V3 audit exactly)
- Repo worktree: 238 MB total; minigame-runtime = 231 MB

## Canonical asset map

| Canonical source (KEEP) | Derived platform dirs (REMOVE from Git, build-generated) |
|---|---|
| `assets/minigame-audio/` (10 wav) | `android-minigame/audio/`, `douyin-minigame/audio/`, `wechat-minigame/audio/` |
| `games/find-anomaly/elevator-console/assets/abnormal_elevator_visual_assets/` (73) | `android-minigame/visual/`, `douyin-minigame/visual/`, `wechat-minigame/visual/`, `android-webview/app/src/main/assets/assets/abnormal_elevator_visual_assets/` |

`build.js` `syncAssetDirectory()` already regenerates audio + visual into every
platform `outputDir` from these canonical sources. `prepare-android-webview.mjs`
regenerates the webview asset copy. So the derived copies are pure build
artifacts and can be dropped from Git.

## Dedup migration plan

1. Write `.gitignore` rules for the derived dirs.
2. `git rm --cached` the derived media (they remain on disk until a build).
3. Rebuild android + webview to confirm generation still works.
4. `git diff --exit-code` after rebuild (drift gate) to prove determinism.
5. Commit: removal of ~142 duplicate tracked files (~106 MB) + gitignore.

## LFS / release-artifact policy

- `assets/generated/*.gif` (8-12 MB each) and large `*.png` are CANONICAL
  unique files — keep in Git for now (single copy, no duplicate).
- Any NEW binary > 1 MiB must use LFS or Release Artifact (enforced by review).
- GIFs are the heaviest; optional future step: move to Release Artifact /
  regenerate deterministically. Kept tracked since they are canonical and
  non-duplicated.

## Verification
- `npm test` (321) after removal.
- `node scripts/check-android-drift.mjs` (deterministic rebuild).
- `git status` clean after build.

## Evidence
- Required: E2 (isolated rebuild + drift gate).
- Duplicate waste target: reduce >=80% (106.55 MB -> ~10 MB, removing derived copies).
