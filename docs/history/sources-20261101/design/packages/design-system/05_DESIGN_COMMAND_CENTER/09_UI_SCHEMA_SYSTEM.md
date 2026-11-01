# 09｜UI SCHEMA SYSTEM

UI Schema 是 Codex 实现游戏 UI 的唯一结构依据。

```json
{
  "screen": "monitor_main",
  "theme": "anomaly_monitor_dark",
  "layout": {
    "type": "vertical",
    "sections": [
      {"id": "status_bar", "height": 64, "components": ["alarm_code", "time", "anomaly_level"]},
      {"id": "monitor_view", "height": 360, "components": ["camera_frame", "noise_overlay", "target_marker"]},
      {"id": "log_panel", "height": 160, "components": ["rule_text", "system_warning"]},
      {"id": "action_panel", "height": 180, "components": ["action_buttons"]}
    ]
  },
  "states": {
    "anomalyLevel": {"0-30": "normal", "31-60": "warning", "61-100": "danger"}
  }
}
```

没有 UI Schema，不调用 Codex 实现。Codex 不允许自行改变 layout 或 token。
