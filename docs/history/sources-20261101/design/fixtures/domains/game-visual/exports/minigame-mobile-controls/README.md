# Minigame mobile controls Open Design export

Self-contained Open Design export for the anomaly elevator / minigame mobile controls layout.

## Contents

```text
index.html                 Standalone front-end preview artifact
index.html.artifact.json   Open Design artifact metadata
critique.json              Open Design critique panel result
implementation-handoff.md  Hand-off note for production integration
.open-design/project.json  Open Design project metadata
assets/*.png               Local CCTV visual assets used by index.html
```

## Purpose

This export captures the latest Open Design visual prototype for a mobile HUD/control layout:

- CCTV feed remains the first visual focus.
- Primary thumb controls are reduced to three high-frequency actions.
- Low-frequency controls move into a bottom secondary action sheet.
- The HTML preview is self-contained inside this folder and does not depend on `D:\All projects\MINIGAME`.

## Smoke test

Open `index.html` in a browser and confirm that these asset URLs resolve locally:

```text
assets/cctv-elevator-corridor-clear.png
assets/cctv-elevator-corridor-warp.png
assets/cctv-elevator-corridor-figure.png
```
