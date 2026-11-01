---
name: anomaly-monitor-hud
zh_name: "异常监控 HUD"
description: "Optional visual specialization for CCTV, surveillance, anomaly monitoring, and control-console interfaces; not a universal minigame default."
triggers:
  - "异常监控"
  - "CCTV HUD"
  - "监控终端"
  - "control console"
---

# Anomaly Monitor HUD

这是按需加载的**可选视觉专精**，用于 dark surveillance、monitoring-room、CCTV、anomaly-detection 和 hardware-control 界面。不要把所有小游戏默认设计成 CCTV；只有 brief 明确要求监控、异常侦测、安防或控制台题材时才启用。

## Inputs

- `scene`: custom from brief; examples include elevator, hospital, security, factory, subway or hotel.
- `riskLevel`: `low`, `medium`, `high`, `critical`.
- `surface`: `mobile`, `desktop`, `tablet`, `stream-overlay`.

## Visual rules

1. CCTV/monitor content must be the hero surface.
2. Controls look like hardware, not survey buttons.
3. Telemetry appears as short chips, codes, meters, and status strips.
4. Logs are compact and atmospheric, never a paragraph wall.
5. Red is reserved for danger; cyan/green is reserved for system state.
6. Glitch/noise supports readability; it never covers the primary controls.

## Output contract

```text
1. Scene summary
2. HUD layout zones
3. Control model
4. Telemetry model
5. CCTV/asset references
6. Color/type/material notes
7. Responsive behavior
8. Implementation prompt
```

## Local template references

Use these local references before generating:

```text
design-lab/templates/layouts/mobile-menu.md
design-lab/templates/motion/motion-system.md
design-lab/templates/typography/cjk-ui-typography.md
design-lab/templates/design-systems/style-reference-index.md
design-lab/assets/visual-packs/anomaly-monitor-cctv/manifest.json
```
