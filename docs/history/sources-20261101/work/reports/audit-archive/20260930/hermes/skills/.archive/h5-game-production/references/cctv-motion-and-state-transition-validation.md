# CCTV Motion and State-Transition Validation

Use this when a Canvas mini-game uses static CCTV/state images but the player expects a visibly changing machine, vehicle, door, camera, or environment.

## Core distinction

A manifest containing many state images is **not** evidence of animation. Neither are:

- a shared `deriveVisualState()` mapping;
- a 60 FPS render loop that redraws the same image;
- one initial screenshot;
- passing asset-loader/bundle tests.

The acceptance target is a visible temporal chain in the official target runtime:

```text
pre-action → intermediate state(s) → terminal state → recovery/idle
```

## Failure patterns to audit

1. **Instant logical mutation**
   - `openDoor` immediately sets `door='open'` with no transient phase.
   - Floor increments immediately while the image merely says "moving".
2. **Non-terminating movement**
   - `moving=true` or `direction='up'` is never reset.
3. **Unreachable imported frames**
   - `door_opening` and `door_closing` exist in the manifest but no runtime state can select them.
4. **Derived-state precedence bugs**
   - A broad state such as `stabilized` is checked before concrete physical states such as open door or active movement, hiding the actual machine state.
5. **Wallpaper animation**
   - Scanlines/noise change, but the door, floor, object, light, or camera subject never does.
6. **Baked-answer leakage**
   - Source PNGs contain `FLOOR MISMATCH`, fixed floor numbers, route labels, threat names, or other answers before the player classifies the event.
7. **Background/ad time skip**
   - A wall-clock animation completes while hidden or during rewarded video even though gameplay time is paused.
8. **Action stacking**
   - Repeated taps enqueue multiple moves or floors while one transition is active.

## Recommended architecture

Keep deterministic game state and millisecond visual motion related but separate:

- Core state stores a serializable transition descriptor:
  - `kind`, `duration`, `remaining`, `fromFloor`, `toFloor`, etc.
- `tickState()` completes logical transitions and resets `moving/direction`.
- A pure motion controller samples the visual frame from `now()`:
  - `progress`, eased progress;
  - current/previous CCTV state;
  - floor reel;
  - offset/zoom;
  - glitch/flicker/scan phase;
  - `frameTime`, the same pausable timestamp used by every renderer effect.
- Runtime calls `startAction(before, after)` and `startAnomaly(before, after)`.
- Motion controller exposes `pause()/resume()/reset()` and is wired to both lifecycle and rewarded-ad pause paths.
- Renderer consumes the sampled motion object. Scan sweeps, signal tears, shake, reticles, procedural fallback art, and other time-based effects must use `motion.frameTime`, never independent `Date.now()` calls. A paused progress value with a live wall-clock renderer is still a broken pause implementation.

Suggested durations for a compact mobile game:

| Transition | Typical duration |
|---|---:|
| Door opening/closing | 0.8–1.2 s |
| One-floor movement | 1.6–2.2 s |
| Emergency stop | 0.7–1.0 s |
| System reboot | 1.3–2.0 s |
| Anomaly reveal | 1.0–1.5 s |

Allow an emergency-stop action to interrupt movement, but reject or disable ordinary stacked actions while a transition is active.

## Using static art without making a slideshow

Static frames can still produce useful motion when combined carefully:

- Crossfade closed → intermediate → open door frames.
- During movement, add low-amplitude vertical shake, slight horizontal drift, and restrained zoom.
- Render a real-time floor reel and route label from state.
- Use moving scan sweeps and bounded signal tears for camera faults.
- Use darkness/flicker for power loss and pulse zoom for entity approach.
- On completion, visibly settle to idle; never leave a static "MOVING" image indefinitely.

Subject motion must be readable without relying only on captions, logs, border colors, or scanline noise.

## Baked-text neutralization

If production art contains fixed diagnostic text or floor values:

1. Inventory all baked labels and determine whether they conflict with runtime state or reveal the answer.
2. Mask only the diagnostic/HUD zones, preserving the machine or anomaly subject.
3. Draw runtime-owned labels on top.
4. Before classification, provide a clue rather than the answer:
   - good: `LIVE FLOOR 01` versus `CABIN FEED 04`;
   - bad: `FLOOR MISMATCH`.
5. After classification, an explicit diagnosis is allowed.
6. Verify masks under zoom/shake so baked text does not peek outside the mask.

### Runtime floor overlay for baked animation frames

Movement state images (`04_moving_up`, `05_moving_down`) are often GIF-like loops that show the elevator passing floors 1→2→3→... over their animation frames. A single baked number at the top of the image can be fixed with a mask; a scrolling number in the *center* of the animation frame cannot.

**Fix:** during moveUp/moveDown, render a 260×70 semi-transparent overlay strip in the center of the CCTV area:

```
┌─────────────────────────┐
│            5F           │  ← amber, bold 36px, actual floorReel
│         ▲ 上行中        │  ← 18px direction indicator
└─────────────────────────┘
```

Implementation notes:
- Overlay uses `rgba(2,7,7,0.84)` fill with a subtle green border.
- Floor number comes from `motion.floorReel` (the interpolated value, not the static state).
- Direction indicator shows `▲ 上行中` for moveUp, `▼ 下行中` for moveDown.
- Only render during movement — door transitions and idle do not need it.
- The draw order is: draw image → draw glitch/overlays → draw floor overlay → draw hudShade → draw labels.
- Keep within `ctx.save/restore` so the CCTV clip region contains the overlay.
- Verify with a screenshot that the overlay number matches the panel data number.

## Low-cost Canvas budget

For static CCTV art animated at mobile mini-game frame rates:

- Steady state: target one main scene `drawImage` plus no more than two overlays.
- Transition peak: keep full-frame `drawImage` calls at four or fewer.
- Bound glitch slices to roughly five; precompute seeded offsets rather than allocating random objects every frame.
- Preload/decode all images before action; never create images during animation.
- Prefer `save/clip/translate/scale/globalAlpha` and translucent fills.
- Avoid `getImageData()`, per-pixel noise, high-radius blur, persistent `filter`, or heavy `shadowBlur`.
- After every branch restore `globalAlpha=1`, `globalCompositeOperation='source-over'`, transform, and clip.
- On representative low/mid devices, run the full shift and reject continuous multi-frame drops below the product's target frame-rate budget.

## Required tests

### Pure state tests

- Door action exposes a transient phase and settles.
- Movement lasts the intended ticks and automatically returns to idle.
- Repeated movement during transition is rejected.
- Emergency stop can interrupt.
- Concrete physical states outrank generic `stabilized` visuals.

### Motion-controller tests

Sample at fixed times and assert:

- closed → opening → open;
- floor reel progresses between source and destination;
- offsets change over time;
- final frame is inactive and stable;
- anomaly glitch values vary over time;
- pause freezes both transition progress and `frameTime`; resume continues both without a jump;
- source/behavior checks reject direct wall-clock timing inside renderer effects (`Date.now()` is allowed only as the motion controller's injectable default clock).

### Official-runtime evidence

In the actual Developer Tool/device:

1. Capture 4–6 frames across each representative transition.
2. Build a contact sheet and an animated GIF/video.
3. Inspect the subject, not only HUD text.
4. Compute adjacent-frame differences for the CCTV crop as a sanity check, not as sole visual proof.
5. Verify at least:
   - door transition;
   - movement + floor roll + automatic stop;
   - anomaly reveal;
   - post-treatment recovery.
6. Check baked text, crop, safe area, action locking, and final state consistency.

## Publishability language

Never answer a visual publishability challenge with only "tests pass", package bytes, or one static screenshot.

Report the gates separately:

- **Visual/runtime candidate:** temporal behavior proven in official Developer Tool/device.
- **Code/package gate:** tests, generated bundle, package limit, runtime blockers.
- **External release gate:** real AppID/ad units, operator/privacy data, console qualifications.
- **Final release gate:** true-device performance, real ads, upload/review.

If only the first two are green, call it a **release candidate for device/review validation**, not "ready to publish".
