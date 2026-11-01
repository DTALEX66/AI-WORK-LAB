# Motion design and accessibility

- Every motion has purpose: orientation, relationship, feedback, attention or expression.
- Define duration, delay, easing, distance, origin, interruption and completion state as tokens.
- Productive and expressive motion use separate ranges.
- Non-essential interaction motion must honor `prefers-reduced-motion` or the platform equivalent.
- Primary motion animates only `transform` and `opacity`; layout-triggering properties (`width`, `height`, `top`, `left`, `right`, `bottom`, `margin*`, `padding*`) must not be animated. [SRC-T07-MOTION-COMPOSITED]
- Reduced-motion mode replaces spatial movement with opacity, instant state change or shorter transitions; it must not remove information.
- Lottie assets are schema-validated, expression-free by default, font-safe and tested in target renderers.
- Video/motion deliverables record dimensions, frame rate, codec, color space, audio, captions and safe areas.
