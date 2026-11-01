# Mobile menu and navigation template

Use when Open Design generates app/mobile web layouts.

## Menu patterns

Choose one:

```text
bottom tabs: 3-5 primary destinations
side drawer: many destinations, lower frequency
command sheet: task-first actions
segmented header: 2-4 peer views
floating radial/console controls: game/HUD contexts only
```

## Required states

```text
active
inactive
pressed
disabled
danger
loading
badge/count
```

## Rules

- Thumb zone first: primary actions in lower half.
- Top area belongs to context/status, not too many buttons.
- Labels should be short: 1-3 Chinese words or 1-2 English words.
- Do not hide destructive actions beside primary actions.
- Icons need labels unless the icon is universal.
- For game/HUD UI, controls should feel like hardware or console chips, not form buttons.

## Open Design prompt add-on

```text
Design mobile navigation with explicit active/pressed/disabled states, thumb-reachable primary actions, compact labels, and clear grouping. Avoid desktop nav squeezed into a phone.
```
