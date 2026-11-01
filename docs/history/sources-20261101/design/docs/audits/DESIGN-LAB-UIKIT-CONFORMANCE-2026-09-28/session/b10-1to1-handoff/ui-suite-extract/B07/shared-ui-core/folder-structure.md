# Recommended Frontend Structure

```text
src/
  app/
    routes/
    providers/
    layouts/
  components/
    ui/
    data/
    graph/
    workflow/
    overlays/
  features/
    <domain-module>/
      api/
      components/
      hooks/
      state/
      types/
  pages/
  styles/
    tokens.css
    responsive.css
    motion.css
  lib/
    permissions/
    telemetry/
    storage/
    commands/
  assets/
```

Recommended stack:
- React + TypeScript
- React Router / TanStack Router
- Zustand or Redux Toolkit for app state
- TanStack Query for remote state
- Radix primitives for accessible overlays
- CSS Variables for theme tokens
- Optional Tailwind only as utility layer; do not encode brand identity solely in class strings
