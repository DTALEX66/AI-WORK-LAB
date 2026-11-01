# DESIGN-LAB Frontend Architecture

## Product role
AI-native, platform-neutral design intelligence and production laboratory.

## Architecture principles
1. Shared `AppShell`, interaction contracts, accessibility rules and component API.
2. Project-specific theme tokens, information architecture and domain modules.
3. Page routes remain thin; business logic lives under `features/<domain>`.
4. Remote state and server cache are separated from local UI state.
5. All destructive or governance actions are auditable.
6. Empty/loading/error/permission states are mandatory for every data surface.

## Primary modules
- Projects
- Research
- BrandSystems
- DesignDomains
- Tools
- Preflight
- Deliverables
- Evidence
- Collaboration

## Roles
- Owner
- DesignLead
- Designer
- Reviewer
- Producer
- Viewer

## Recommended page contract
Every page provides:
- title / description
- primary action
- filter/search state
- loading / empty / error / permission state
- keyboard navigation
- responsive transformation
- telemetry event namespace
- optional audit metadata

## Responsive
- Desktop ≥ 1200: persistent sidebar, 12-col grid
- Tablet 768–1199: collapsible sidebar, 2-col content grid
- Mobile ≤ 767: single column, bottom/overlay navigation, drawer for secondary actions

## Accessibility
- Text contrast ≥ 4.5:1
- Focus visible on all interactive elements
- 44×44 minimum hit target
- Color is never the only state signal
- `Esc` closes top overlay
- `Enter` confirms primary action when safe
