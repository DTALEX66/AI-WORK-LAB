# Anti-AI-slop design checklist

Use before accepting an Open Design output. Inspired by open-source anti-slop design skills, but rewritten as local review gates.

## Hard fails

Reject or regenerate if any are true:

- Generic centered hero with vague gradient blobs and no product-specific structure.
- Four-card feature grid with interchangeable icons and empty marketing copy.
- UI looks like a survey/form/admin template when the brief asked for product, game, poster, or campaign design.
- Everything has the same radius, same shadow, same spacing, same font weight.
- No clear focal point within 3 seconds.
- Text hierarchy is fake: all labels feel like subtitles or lorem ipsum.
- Mobile layout is just desktop squeezed down.
- Navigation has no active state, grouping, or affordance.
- The design could be reused for any company by changing colors.

## Required pre-emit critique

Ask the agent to answer before final output:

```text
1. What is the macrostructure?
2. What is the main visual bet?
3. Which common AI-design default did you avoid?
4. What did you intentionally remove?
5. What will still look good in a screenshot thumbnail?
```

## Variation rule

For important work, demand three directions:

```text
safe: obvious and production-ready
premium: sharper hierarchy, stronger visual identity
weird: memorable, still usable, not random
```

## Scorecard

| Gate | Score |
|---|---:|
| Specific to brief | /5 |
| Strong focal point | /5 |
| Real layout structure | /5 |
| Typography contrast | /5 |
| Non-generic components | /5 |
| Mobile/readability | /5 |
| Visual restraint | /5 |
| Implementation realism | /5 |

Reject below 32/40.
