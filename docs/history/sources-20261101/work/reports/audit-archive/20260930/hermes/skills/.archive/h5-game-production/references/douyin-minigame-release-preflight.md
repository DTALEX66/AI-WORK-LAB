# Douyin Mini Game release preflight (official-doc research)

Use this reference when adapting a Canvas game to a native Douyin mini game or auditing a release candidate. Re-check upstream pages before relying on numeric limits or review policy; Douyin updates these rules frequently. Cite only `developer.open-douyin.com` when the user requests first-party evidence.

## Responsibility split

Always label every checklist item as one of:

- **Code**: repository/build output can satisfy it.
- **Developer Tool**: requires Douyin IDE/CLI, preview, device debugging, or upload.
- **Console/account**: requires developer identity, application permissions, qualifications, filing, ad-unit creation, or review submission.
- **Joint**: code plus console configuration, such as secure-domain allowlists, privacy declarations, ads, and anti-addiction.

Do not imply that code can complete filing, qualification, ad-service activation, or release.

## Native project baseline

Required root files:

```text
.
├── game.js
├── game.json
└── project.config.json
```

The runtime is a JavaScript VM with `tt.*` APIs and no browser BOM/DOM. The first `tt.createCanvas()` call returns the sole onscreen Canvas.

Official guide: <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/guide/bytedance-mini-game>

### `game.json`

Important documented fields include `deviceOrientation`, `showStatusBar`, `networkTimeout`, `workers`, `openDataContext`, `subPackages`, `menuButtonStyle`, `enableIOSHighPerformanceMode`, and `plugins`. Default orientation is `landscape`; explicitly set the intended orientation. `subPackages` is camel-case. Remove unsupported/unneeded plugin declarations. `ttNavigateToMiniGameAppIdList` relates to deprecated APIs and should not be recommended for new work.

Official configuration: <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/framework/mini-game-configuration>

### `project.config.json`

The ordinary-game guide only demonstrates a minimal object with `description` and `setting.es6`. Do not invent or copy WeChat-specific fields as Douyin requirements. Keep actual output strict JSON even when an instructional snippet contains explanatory comments.

## Current ordinary-game package limits

From the ordinary code-package page:

- No subpackages: total uploaded code package ≤ 20 MB.
- With subpackages: overall directory ≤ 20 MB; virtual-payment games ≤ 30 MB.
- Main package ≤ 4 MB.
- Each subpackage ≤ 20 MB; virtual-payment games ≤ 30 MB.
- Subpackages require base library ≥ 1.88.0 and developer tool ≥ 2.0.6.

Do not mix these limits with Unity/UE instant-play limits.

A subpackage can reference its own JS/resources but not another subpackage's. Use `tt.loadSubpackage`, handle success/failure/progress, show progress during startup loads, and feature-detect for old clients.

Official pages:

- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/guide/basic-function/subpackages/introduction>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/guide/basic-function/subpackages/basic>

## Lifecycle, touch, safe area

- Register `tt.onShow`/`tt.onHide`; pause/resume loops, audio, timers, and persistence correctly.
- Touch events are `tt.onTouchStart/Move/End/Cancel`; use Touch `identifier`, `screenX`, and `screenY`; always recover from cancellation.
- `tt.getSystemInfo` returns window/screen dimensions, `pixelRatio`, orientation, and `safeArea` (`left/right/top/bottom/width/height`). Officially `safeArea` is described in portrait-positive orientation, so landscape transforms require device verification.
- Audit notches, punch holes, Home Indicator, framework/menu-button overlap, hit regions, and rendering-vs-input coordinate scaling.

Official pages:

- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/api/system/lifecycle/tt-on-show>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/api/system/click-event/tt-on-touch-start>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/api/system/system-information/tt-get-system-info>

## Sidebar revisit is a release gate

All mini games must integrate sidebar revisit. The technical guide warns of rejection risk for new launch and version updates when absent.

Implementation essentials:

1. Register `tt.onShow` synchronously/very early during `game.js` startup; a late listener can miss the return event.
2. Feature-detect and call `tt.checkScene`; hide the entry when unavailable.
3. On explicit user action call `tt.navigateToScene({scene: 'sidebar'})`.
4. Use the latest `tt.onShow` values, including `scene: '021036'`, `launch_from: 'homepage'`, `location: 'sidebar_card'` for the standard sidebar-card path.
5. Make reward settlement idempotent and test cold plus warm return.
6. Test in IDE scene simulation and on a real registered test device.
7. Since 2026-04-20 eligible releases automatically cover all partner apps, feature-detect APIs rather than relying on a Douyin-only host check.

Official pages:

- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/essential-skills>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/guide/open-ability/Introduction-for-tech>

## Ads

Code and account duties must be separated: traffic-owner activation, subject/corporate verification, and ad-unit creation happen in the console; code consumes real `adUnitId` values and must degrade safely.

### Rewarded video

- Require explicit user action and a clear platform-compliant video icon/text cue.
- Reward only on completed viewing (`onClose` completion state).
- Do not force ads for normal game/level access, default-select viewing, swap buttons under rapid taps, or promise one reward after multiple ads.
- Handle unsupported/no-fill/error paths without breaking the game. The ad operations rule explicitly requires fallback; in relevant cases directly show the result or grant the reward.

### Banner

Do not cover controls/hot zones, place Banner in the main game scene, shift controls to induce accidental taps, or blend it into native content. In portrait ad pages, bottom-center it and leave separation from clickable UI.

### Interstitial

Documented frequency controls:

- No interstitial in the first 30 seconds after launch.
- At least 60 seconds between interstitials.
- At least 60 seconds after rewarded video before an interstitial.

Listen for load/error/close and Promise rejection; do not retry in a tight loop. After a successful display, destroy and create a new instance for the next display.

Official pages:

- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/operation1/norms/norms>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/api/javascript-api/ads/interstitial-ad/interstitial-ad-notice>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/develop/api/ads/tt-create-rewarded-video-ad>

## Privacy and quality review

Code-side checks:

- Obtain explicit informed consent before collection; do not prompt for authorization on the first screen.
- Do not repeatedly request the same information across pages.
- On refusal/revocation, stop using and clear acquired profile/contact data as applicable.
- Support deletion requests except legally required retention.
- Never transmit private data in plaintext; use HTTPS/WSS and console allowlists.
- Mask displayed identity/contact data; keep data scoped to the declared mini game and purpose.
- Location needs specific consent and a directly related feature.

Console-side checks:

- Complete the mini game's privacy policy; name/entity must match the console.
- Ensure actual APIs, collected data, third-party SDKs, purposes, retention, and deletion route match the policy.
- Complete age suitability, self-inspection confirmation, and required secure domains.

Quality review also checks completion, crashes/white screens, network error UX, notch adaptation, full button hit areas, no debug/test UI, content/IP legality, and a full-feature test account when an account system exists.

Official pages:

- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/operation1/norms/standard>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/improve-information>

## External release gates

Console/account work includes developer onboarding, app creation, basic information review, software copyright certificate (all games), license for in-app-purchase games, IP authorization where applicable, age suitability, anti-addiction/real-name channel binding, ICP filing, and mini-game work filing. A game with an approved publication license does not repeat mini-game filing; otherwise basic information and a version must pass review before platform filing proceeds.

Upload/review flow:

1. Compile and upload in the IDE; enter version and changelog.
2. Up to 25 test versions/channels are supported; keep the cross-host candidate in the default channel.
3. In console Development Version Management, scan-test and submit the chosen package.
4. Provide three in-game screenshots and a full-access test account if needed.
5. First launch QA is documented as roughly 1–3 working days.
6. Since 2026-04-20 QA defaults to multi-host coverage; failure on any host requires correction and resubmission.
7. After approval choose immediate full release or gray release. Gray release requires an existing online version and automatically becomes full after 15 days; its percentage can increase but not decrease.

Official pages:

- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/improve-information>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/game-filing-application-works>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/examineguide>
- <https://developer.open-douyin.com/docs/resource/zh-CN/mini-game/guide/minigame/release>

## Research workflow pitfall

When clean-page extraction is unavailable, use the browser on the official documentation page and read `document.body.innerText` (or targeted slices around headings/terms). Official documentation often redirects legacy URLs to canonical routes; record the final URL after navigation. Search snippets are useful for discovery, but numerical limits and current review policy should be verified from the rendered official page before being stated.