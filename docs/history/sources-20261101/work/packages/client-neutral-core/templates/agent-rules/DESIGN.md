# DESIGN.md — UI/UX Quality Baseline

## Principle

Functional is not enough. UI work should produce something usable, polished, and consistent with the product’s tone.

## Before UI Changes

1. Inspect the current UI structure, routes, components, CSS/theme files, and screenshots if available.
2. Identify whether the problem is layout, information architecture, visual style, performance, or copywriting.
3. Prefer a cohesive usage layer over isolated CSS tweaks.

## Baseline Requirements

- Clear hierarchy: hero/primary action/secondary actions/status.
- Empty/loading/error states are designed, not left blank.
- Mobile layouts fit one screen where the product requires it.
- Repeated UI patterns use reusable components or tokens.
- Text is concise and user-facing, not debug-only.

## Verification

Run the app/build/test command and inspect at least one rendered output path when possible.
