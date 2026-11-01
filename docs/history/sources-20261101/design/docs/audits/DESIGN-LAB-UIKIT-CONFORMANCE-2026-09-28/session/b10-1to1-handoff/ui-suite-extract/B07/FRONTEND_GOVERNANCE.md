# Three-Project Frontend Governance

## Shared ecosystem
The three products share:
- component APIs
- accessibility rules
- interaction states
- motion timing
- responsive breakpoints
- keyboard conventions
- page-state contracts
- engineering folder conventions

They do **not** share:
- brand palettes
- logos
- product navigation
- domain terminology
- content hierarchy
- project-specific visual personality

## Dependency rule
`shared-ui-core` may be imported by any project.
A project must never import another project's theme file or product feature module.

## Theme isolation
Each product is mounted with its own `data-theme`.
No component may infer another project's theme.
Theme values must be accessed via CSS variables only.

## Release governance
1. Update shared component contract
2. Run all three product visual regression suites
3. Confirm no cross-project token leakage
4. Confirm accessibility
5. Publish core
6. Upgrade products independently
