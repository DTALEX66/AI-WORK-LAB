# Anomaly Content Schema Reference

> For clue-hunting / observation mini-games where the core loop is:
> **observe → compare screen vs panel → decide (release / lockdown)**

## Schema Structure

Every anomaly entry is a triple of `screenData`, `panelData`, and `primaryConflict`:

```js
{
  id: 'floor_jump',             // unique ID, matches skin.json anomaly ID
  title: '楼层编号跳跃',          // short display title
  severity: 2,                   // 1=low 2=mid 3=high (gameplay impact)
  difficulty: 2,                 // 1=obvious conflict 2=needs checking 3=needs context/trend
  correctDecision: 'lockdown',   // always 'lockdown' for anomalies

  // What the CCTV / observation screen shows
  screenData: {
    floor: 9,
    passengers: 1,
    door: 'closed',
    direction: 'up',
  },

  // What the control panel / telemetry says
  panelData: {
    floor: 5,
    passengers: 1,
    door: 'closed',
    direction: 'up',
  },

  // Human-readable contradiction — must name a SPECIFIC observable clue
  primaryConflict: 'CCTV 层 9 ≠ 控制台层 5（非连续移动，帧丢失）',

  // Lore explanation (for archive/post-game)
  explanation: 'GPS 楼层定位模块在校准前后记录的楼层编号不一致。...',

  // Asset/feedback references
  visualState: '16_wrong_floor',     // CCTV state image ID
  audioCue: 'anomaly',               // sound effect cue
  resolutionAction: 'inspectLog',    // what the system auto-executes

  // Resource penalties
  stabilityPenalty: -12,
  powerPenalty: -10,

  // What a matching NORMAL scene looks like (same floor, same state)
  normalVariant: {
    floor: 5,
    passengers: 1,
    door: 'closed',
    direction: 'up',
  },
}
```

## Difficulty Classification

| Difficulty | Pattern | Example |
|---|---|---|
| 1 (obvious) | Single field different between screen and panel | `phantom_floor`: floor=13 vs floor=1 |
| 2 (needs checking) | Two+ fields different, or single field with context needed | `camera_delay`: floor=5 vs floor=7; `floor_jump`: floor=9 vs floor=5 |
| 3 (needs context) | All screen fields match panel, but system state reveals the conflict | `auto_button`: buttons self-lighting; `stop_failure`: emergency stop fails |

## Zero-Field Anomalies

When `screenData === panelData` but the situation is still anomalous, the `primaryConflict` must name a **specific non-field observable**. The test suite rejects vague strings with a regex guard:

```
✓ 含"日志" / "按钮" / "电源" / "急停" / "灯光" / "应急" / "重复" / "自动"
✗ "所有数据一致" / "画面显示异常" / "数据有矛盾" (too vague)
```

## Normal Variant Design

Generate 10+ normal variants. They must include:

```
Same floors as anomalies:   13, -1, 5, 9, 3, 7, 8, 10
Empty cabins:               floor=1, passengers=0
Single passenger:           floor=3/7/10, passengers=1
Multi passenger:            floor=5/2/8, passengers=2-3
Door open:                  floor=2/4/13
Door closed:                floor=1/3/5/7/8/9
Moving up:                  floor=3/5/7
Moving down:                floor=6/9/10
Stationary:                 floor=1/4/8/13
```

The goal: the CCTV changing appearance (different floor, different passengers, door state, direction) must NOT be a reliable anomaly signal. Only data *contradiction* is reliable.

## Data Integrity Tests

Place in `tests/<domain>Content.test.js`:

```js
// Structural
all entries have required fields              // id, title, severity, screenData, panelData, etc.
each entry has at least one conflict field    // zero-field anomalies need keyword regex
all value ranges are valid                    // floor, passengers, door, direction enums

// Cross-reference
all content IDs match skin.json IDs            // bi-directional: no orphan in either file
findAnomalyContent(id) returns correct entry  // lookups work for all IDs
findAnomalyContent(nonexistent) returns null  // unknown ID safety

// Anti-pattern matching
normal variants include anomaly-matching floors  // overlap >= 1
normal variants are fully consistent             // screenData === panelData for all 4 fields

// Semantic
isDataConsistent returns false for all anomalies  // at least one field differs (or zero-field check)
correctDecision is 'lockdown' for all anomalies   // anomaly = conflict = lockdown
```
