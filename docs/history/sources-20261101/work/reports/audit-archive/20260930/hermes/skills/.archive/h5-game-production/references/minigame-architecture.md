# MINIGAME Project Architecture Reference

Last updated: 2026-06-30
Repo: DTALEX66/MINIGAME
Path: D:\All projects\MINIGAME

## Current Phase Status

| Phase | Status | Commit |
|---|---|---|
| P0 MVP Polish | ✅ Complete | 41b419a |
| P1 Monetization Loop | ✅ Complete | 913d3cc |
| P2 Skinning System | ✅ Complete | 014f76d |
| P3 Platform Adaptation | ✅ Complete | b760c59 |

## Project Structure

```
MINIGAME/
├── src/
│   ├── gameConfig.js      ← Balance parameters (tune difficulty here)
│   ├── state.js           ← State machine
│   ├── actions.js         ← Player actions (7 + unlockHiddenLog)
│   ├── events.js          ← Anomaly events (12 types, skin-driven)
│   ├── feedback.js        ← Failure summaries + tone
│   ├── game.js            ← Game loop + DOM UI binding
│   ├── audio.js           ← Web Audio API procedural sounds
│   ├── skinManager.js     ← Skin loader + t() template system
│   └── skins/
│       ├── elevator/skin.json   ← Skin A: 异常电梯控制台
│       └── security/skin.json   ← Skin B: 异常安防监控
├── platform/
│   ├── platform.js        ← Platform abstraction (wx/tt/browser)
│   └── canvasRenderer.js  ← Canvas rendering (mini-game mode)
├── wechat-minigame/       ← WeChat mini-game project (built)
│   ├── game.js (44KB)     ← Bundled entry
│   ├── game.json
│   └── project.config.json
├── docs/
│   ├── PROJECT_CONTEXT.md
│   ├── GAME_DESIGN.md
│   ├── WORKFLOW.md
│   ├── P1_MONETIZATION_LOOP.md
│   ├── P2_SKINNING_SYSTEM.md
│   └── P3_PLATFORM_ADAPTATION.md
├── index.html
├── styles.css
├── build.js
├── tests/
└── package.json
```

## Key Files for Future Sessions

### SkinManager API
```
t('meta.name')              → Game title from active skin
t('actionLabels.openDoor')   → Button label
t('monitor.actions.moveUp', {floor: 5})  → Monitor text with params
t('failure.summaries.power') → Failure reason
t('fakeEnding.text', {count, threshold}) → Fake ending
t('ui.decodePrefix')        → "[解码记录]"
getAnomalies()              → Current skin's anomaly definitions
getHiddenLog(id)            → Hidden log for anomaly
actionLabel(actionId, count?) → Button label with optional count
```

### Game Config (gameConfig.js)
- `CONFIG.initial.duration`: 60 (shift timer)
- `CONFIG.tick.*`: power/stability drain rates
- `CONFIG.actions.*`: move costs, restart effects
- `CONFIG.failure.*`: failure thresholds
- `CONFIG.anomaly.*`: trigger timing, cooldown, pressure
- `CONFIG.adRevive.*`: rollback window, snapshot interval
- `CONFIG.hiddenLogs.maxUnlockedPerRun`: 5
- `CONFIG.fakeEnding.consecutiveFailuresThreshold`: 5

### Build
```bash
node build.js wechat  # Builds wechat-minigame/game.js
python -m http.server 5173  # Serve H5 version
```

### Next Steps (TODO)
- [ ] Replace appid in wechat-minigame/project.config.json with real WeChat AppID
- [ ] Apply for rewarded video ad units on WeChat platform
- [ ] Wire real adUnitIds into platform.js createRewardedAd calls
- [ ] Test Canvas renderer in WeChat dev tools
- [ ] Create skin C (third theme) to further validate skinning system
- [ ] Game balance tuning via gameConfig.js (difficulty curve)
