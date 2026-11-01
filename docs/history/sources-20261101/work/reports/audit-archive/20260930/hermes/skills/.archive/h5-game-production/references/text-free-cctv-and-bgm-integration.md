# Text-Free CCTV Asset Replacement and BGM Integration

## Exact-scope visual correction

When a user circles one baked label (for example `7F→8F`), first distinguish three separate fixes:

1. **Localized source repair** — remove only the marked text pixels and reconstruct the underlying scanline/scene texture. Preserve the cabin, doors, arrows, perspective, noise and all unmarked artwork.
2. **Full clean replacement pack** — if supplied, replace source assets by matching stable state IDs and dimensions. Do not retain old-asset crop/mask workarounds.
3. **Renderer overlay** — last resort only. Never add a broad black strip/card, duplicate floor readout, or replace the whole scene unless explicitly requested.

Verification must check the actual pixels, not only state IDs or unit tests. Sample both movement directions and anomaly states. Confirm no fixed floor, camera ID, REC, timestamp, English diagnosis or answer label remains.

## Replacement-pack workflow

1. Verify source inventory and dimensions before copying:
   - wide/mobile CCTV counts and state IDs;
   - button filenames and dimensions;
   - audio channels/rate/bit depth/duration/peak.
2. Copy only declared replacement directories into canonical source directories.
3. Preserve keep/reference/release directories exactly.
4. If new images are already safely cropped and text-free:
   - remove legacy `cropTop` / `cropBottom` / `usableH` logic;
   - use normal aspect-safe cover drawing;
   - remove opaque masks whose only purpose was hiding baked HUD;
   - keep HUD labels runtime-owned.
5. Regenerate platform copies through build scripts. Do not manually maintain generated WeChat/Douyin/Android asset folders.
6. Hash-compare canonical source assets against generated outputs and count each family.
7. Run full tests and platform strict checks.

## BGM architecture

Use a dedicated looping context/player separate from short SFX.

Required interface:

```text
setMusicState('calm' | 'pressure')
pauseMusic()
resumeMusic()
stopMusic()
```

Rules:

- Start only after the first user gesture.
- Calm during normal play; pressure while an anomaly/high-pressure state is active; return to calm after resolution.
- Reuse one dedicated music context/player or otherwise guarantee old loops stop before new loops begin.
- Static mute controls SFX and BGM together.
- Pause/stop for ads, app hide, browser visibility loss and terminal states; resume only if the same run is active, not muted and not over.
- Keep SFX louder than BGM.
- Build scripts must copy BGM from the canonical audio source directory.

## Evidence checklist

- Source: all state IDs present and dimensions expected.
- Pixels: text-free representative normal/movement/anomaly images.
- Buttons: no baked text/icon; semantic light strips preserved.
- Audio: format and dBFS measured from the real files.
- Generated packages: expected CCTV/button/overlay/SFX/BGM counts and source/output hashes match.
- Runtime tests: no old crop/mask, no parallel BGM, mute/lifecycle/ad behavior covered.
