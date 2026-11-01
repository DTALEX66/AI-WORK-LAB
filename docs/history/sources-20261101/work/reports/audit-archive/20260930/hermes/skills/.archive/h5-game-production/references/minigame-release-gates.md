# Mini-game release gates and private publish config

Use this reference when an H5/Canvas mini-game is ready for platform packaging but still uses placeholder publishing credentials.

## Problem pattern

Development builds can pass while release is not actually publishable because:

- WeChat/Douyin `project.config.json` still contains placeholder AppID values.
- Rewarded-video ad units in `gameConfig.js` are safe placeholders.
- Real AppID/adUnitId values should not be committed to source control.
- A generic `npm test` does not catch publish blockers.

## Recommended gate split

Keep two separate commands:

1. **Development acceptance gate** — should pass without secrets.
   - tests
   - platform bundle build
   - runtime blocker checks
   - Android/WebView APK build and metadata checks when applicable
   - example command: `npm run verify`

2. **Release readiness gate** — should fail closed on placeholders.
   - real platform AppID available via private local config
   - real rewarded-video adUnit IDs available via private local config
   - generated bundle has no runtime blockers
   - package metadata is valid
   - example command: `npm run release:check`

## Private config overlay pattern

Commit only an example template:

```text
release.config.example.json
```

Ignore real local files:

```gitignore
release.config.json
wechat-minigame/project.private.config.json
douyin-minigame/project.private.config.json
```

Typical template shape:

```json
{
  "wechat": {
    "appid": "wx_your_real_mini_game_appid",
    "projectname": "MINIGAME"
  },
  "douyin": {
    "appid": "tt_your_real_mini_game_appid",
    "projectname": "MINIGAME"
  },
  "adUnits": {
    "revive": "adunit-your-real-revive-id",
    "decode": "adunit-your-real-decode-id",
    "truth": "adunit-your-real-truth-id"
  }
}
```

Build scripts may read `release.config.json` or `RELEASE_CONFIG_PATH` to inject private ad units into generated bundles and generate ignored `project.private.config.json` files for platform dev tools. Source files should keep safe placeholders.

## Regression tests to add

- `npm run verify` runs all development checks and passes without real credentials.
- `npm run release:check` exits non-zero on default placeholders.
- A temp private config via `RELEASE_CONFIG_PATH` injects values into generated bundles.
- Temporary private values do not remain in tracked files after tests.
- `.gitignore` protects real local config files.

## Pitfalls

- Do not make the normal development gate fail because real AppID/adUnitId is missing; that blocks local iteration.
- Do not commit real platform IDs or ad unit IDs.
- Do not rely only on WeChat DevTools warnings; encode release blockers as script checks.
- Always verify there are no fake test credentials left in generated or tracked files after tests.
