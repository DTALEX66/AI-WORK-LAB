# Motion system template

Use when Open Design creates interactive prototypes, landing pages, HUDs, dashboards, or presentation artifacts.

## Motion tokens

```text
instant: 80-120ms, tap feedback, chip press
fast: 160-220ms, menu open, tab switch
standard: 240-360ms, panel transition, card reveal
slow: 480-700ms, hero reveal, modal entrance
ambient: 3-12s, background scanlines, subtle loops
```

## Easing

```text
productive: cubic-bezier(.2,.8,.2,1)
mechanical: cubic-bezier(.3,0,.1,1)
soft: cubic-bezier(.16,1,.3,1)
warning: steps(2,end) or short jitter, sparingly
```

## Motion roles

- Confirm input: press, ripple, chip activation.
- Explain structure: panel enters from its source.
- Show priority: alerts interrupt; background does not.
- Add atmosphere: scanlines, glow, parallax, dust, but keep content readable.
- Reduce cognitive load: animate layout changes, not every decoration.

## HUD/game constraints

- Critical alerts can blink, but not more than 2-3Hz.
- CCTV/HUD ambient loops should stay behind text.
- Disable or reduce motion for dense reading states.

## Open Design prompt add-on

```text
Define a motion system with tokens, easing, and roles. Use motion to clarify state and hierarchy, not as decoration. Include reduced-motion behavior.
```
