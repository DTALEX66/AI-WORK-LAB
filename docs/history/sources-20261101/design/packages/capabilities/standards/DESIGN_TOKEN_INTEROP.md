# Design-token interoperability

Canonical project tokens use the DTCG format. `DESIGN.md` remains the human/agent contract and exports a DTCG representation.

## Required mapping

- `$type` and `$value` are explicit for all canonical tokens.
- Aliases use `{group.token}` paths and must not form cycles.
- Color records retain original color space and an sRGB fallback when needed.
- Typography records separate family, size, weight, line height, letter spacing and feature settings.
- Components reference semantic tokens; raw values are prohibited in production artifact code unless promoted into tokens.
- Every export records source version, transform and lossy fields.
- Extracted tokens are untrusted third-party input until reviewed: a single page is not proof of a whole product design system, and components or semantic tokens that were not clearly extracted may not be inferred. [SRC-T07-EXTRACT-SCOPE]

Supported targets should include CSS custom properties, Tailwind v4, Open Design `DESIGN.md`, Figma variables, native mobile formats and JSON.
