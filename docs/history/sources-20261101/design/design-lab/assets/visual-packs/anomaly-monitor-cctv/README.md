# Anomaly Monitor CCTV Visual Pack

This pack lists the retained runtime-critical CCTV/HUD assets. It intentionally does not duplicate large files; paths point back to `fixtures/domains/game-visual/assets/generated/`.

## Rule

Do not add throwaway generated stills to Git. Temporary visual references belong in:

```text
.tmp/generated-reference/
```

Only add new assets when a runtime, plugin manifest, or Open Design design-system package references them.
