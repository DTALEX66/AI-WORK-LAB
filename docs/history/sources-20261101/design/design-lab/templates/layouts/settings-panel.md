# Settings panel layout template

Use with `uiux-layout-director` for account, workspace, admin, game options, and system preference screens.

## Structure

```text
01 side nav or segmented tabs: grouped settings areas
02 page header: title + short consequence statement
03 status summary: current plan/state/connection/security
04 primary settings group: most-used controls first
05 advanced group: collapsed by default if risky
06 danger zone: visually isolated, explicit confirmation
07 sticky save bar or auto-save status
```

## Grouping rules

- Group by user mental model, not database model.
- Use 4-7 items per group max.
- Put account/security/billing/integrations in separate areas.
- Destructive actions never sit beside positive CTAs.
- Every toggle needs a current state and consequence copy.

## Required states

```text
saved
saving
unsaved changes
failed validation
permission locked
requires upgrade
danger confirmation
```

## Open Design prompt add-on

```text
Design a settings panel with grouped navigation, clear current states, readable helper copy, a separated danger zone, and responsive mobile behavior. Avoid a long undifferentiated form.
```
