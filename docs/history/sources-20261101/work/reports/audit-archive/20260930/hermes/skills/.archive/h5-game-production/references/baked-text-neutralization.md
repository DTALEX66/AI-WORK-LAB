# Baked-Text Neutralization in CCTV Assets

## Problem

Pre-made CCTV/security camera assets often contain **baked text** — floor numbers, status labels (STABILIZED, SIGNAL VARIANCE), English diagnostic titles, or frame counters — burned into the PNG pixels at production time. This text:

- Cycles independently of runtime state (a moving-up GIF loop always shows floors 1→2→3→... even when the real position is 05)
- Can leak the anomaly answer (e.g. `07_power_outage` image has baked "07" — player sees the state ID)
- Contradicts panel data (CCTV shows "7F→8F" while panel reads floor 1.1)
- Is invisible to static audit tools — it lives in pixel data, not the DOM

## Asset Types

### Type A: Static ID in the image (e.g. `07_power_outage`)

State image contains its own number as a visual element.

**Defense layers:**
1. **Top-edge HUD shade** — `createLinearGradient` from `#020707` to transparent, covering the top ~112px. Catches fixed-position labels.
2. **Full-image shade for power-outage/emergency** — extend the shade to cover the center if the baked text sits outside the top edge. If the baked text is the *only* distinguishing feature of that state, crop or replace the asset.

### Type B: Animation-cycle floor numbers (e.g. `04_moving_up`, `05_moving_down`)

Movement GIF shows elevator passing floors that loop independently of game time.

**Fix:** Central overlay — fully opaque `#020707`, 340×90px centered in the CCTV area, showing actual `floorReel` (amber 44px bold) + direction text. Only during `moveUp`/`moveDown` timelines. Semi-transparent overlays are insufficient — baked text shows through at any alpha < 1.0.

### Type C: English labels ("STABILIZED", "SYSTEM: STABLE")

Top-edge HUD shade covers these. Verify by screenshot.

### Type D: Scrolling floor numbers (inside shaft animation, no fixed position)

Central overlay (Type B) covers because the 340×90 span is wide enough.

## Verification

- [ ] Capture screenshots of every CCTV state with baked text
- [ ] HUD shade covers all top-baked elements
- [ ] Movement central overlay fires during moveUp/moveDown only, shows correct floorReel
- [ ] Overlay is OFF for non-movement states
- [ ] No baked floor numbers visible outside overlay during movement
- [ ] Runtime labels cover areas where English equivalents were baked

## Principle

Never let the asset author's baked frame labels or loop animations become the player's visible gameplay surface. Every number and status the player uses for decisions must be runtime-owned.
