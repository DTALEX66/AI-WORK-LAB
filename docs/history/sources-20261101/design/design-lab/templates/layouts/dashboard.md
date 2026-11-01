# Dashboard layout template

Use with `uiux-layout-director` for admin, analytics, cockpit, and monitoring products.

## Information architecture

```text
left rail or top nav: 5-7 destinations max
status strip: current system state, last sync, risk/severity
primary panel: chart/table/map/timeline that answers the main question
secondary panels: filters, alerts, drill-down, recent activity
action zone: high-value actions with confirmation for danger states
```

## Dashboard types

- Executive: fewer panels, stronger summary, trend and decisions.
- Operator: dense live state, alert priority, fast action controls.
- Analyst: filters, drill-down, comparison, export.
- Creator: content queue, draft states, publishing readiness.

## Rules

- Do not fill the screen with equal cards.
- Put the main object first: table, chart, map, CCTV, canvas, or queue.
- Use color sparingly for state/severity, not decoration.
- Menus need active state, group labels, and collapsed/mobile behavior.
- Empty states must teach the next action.

## Open Design prompt add-on

```text
Create a dashboard with a clear primary work surface, operator-grade hierarchy, grouped navigation, stateful controls, and responsive behavior. Avoid equal-weight card soup and decorative-only charts.
```
