import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const html = readFileSync(new URL('../index.html', import.meta.url), 'utf8');

test('browser preview exposes an explicit start handoff overlay', () => {
  assert.match(html, /id="startOverlay"/, 'preview should include a visible start handoff overlay');
  assert.match(html, /id="startButton"/, 'preview should include a dedicated start button');
  assert.match(html, /id="startFailureRules"/, 'preview should show explicit failure rules');
  assert.match(html, /id="failureMetrics"/, 'failure overlay should expose system metrics for review');
  assert.match(html, /id="fakeEndingEyebrow"/, 'fake-ending overlay should expose skin-backed eyebrow');
  assert.match(html, /id="fakeEndingTitle"/, 'fake-ending overlay should expose skin-backed title');
  assert.match(html, /id="monitorSignal"/, 'monitor should expose a visual signal state strip');
  assert.match(html, /id="monitorThreat"/, 'monitor should expose a visual threat badge');
  assert.match(html, /id="operatorCue"/, 'monitor should expose a compact first-run operator cue');
  assert.match(html, /class="cctv-stage"/, 'monitor should include a CCTV visual stage, not just text');
  assert.match(html, /id="monitorCaption"/, 'monitor copy should render as caption so visual layer is preserved');
  assert.match(html, /class="door-gap-glow"/, 'monitor anomaly should live inside the CCTV scene as a door-gap glow');
  assert.match(html, /class="distant-shadow"/, 'monitor should include an ambiguous CCTV shadow instead of an abstract scanner icon');
  assert.match(html, /class="thermal-ghost"/, 'monitor should express passenger/anomaly data as a broken thermal ghost');
  assert.match(html, /class="detection-corners"/, 'monitor should use subtle target-detection corners in the scene');
  assert.match(html, /class="cctv-multiview"/, 'monitor should feel like a multi-camera CCTV feed');
  assert.match(html, /class="camera-label"/, 'monitor should include camera labels instead of a generic box');
  assert.match(html, /class="camera-timecode"/, 'monitor should include an in-world timecode');
  assert.match(html, /class="cctv-noise"/, 'monitor should include visible sensor noise/static');
  assert.match(html, /class="hall-perspective"/, 'monitor should render an environment/shaft perspective, not only an elevator icon');
  assert.doesNotMatch(html, /class="anomaly-reticle"/, 'monitor should not use a centered abstract scanner reticle');
  assert.doesNotMatch(html, /class="elevator-car"/, 'monitor should not rely on a fake CSS elevator box over the CCTV photo');
  assert.match(html, /data-testid="start-handoff"/, 'start overlay should be easy to target in browser checks');
  assert.match(html, /id="postRunSummary"/, 'failure overlay should include a post-run summary for player debrief');
  assert.match(html, /id="openArchiveBtn"/, 'start overlay should include an archive button');
  assert.match(html, /id="archiveOverlay"/, 'archive overlay should be present for cross-session collection');
});

test('browser rewarded callbacks are bound to the originating run and valid state', () => {
  const js = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');
  assert.match(js, /shouldApplyReward\(meta, runToken, 'revive', state\)/, 'revive reward should reject stale runs and invalid settlement state');
  assert.match(js, /shouldApplyReward\(meta, runToken, 'decode', state\)/, 'decode reward should reject stale runs and ended games');
  assert.match(js, /shouldApplyReward\(meta, runToken, 'truth', state\)/, 'truth reward should require the active fake ending');
  assert.match(js, /showReviveAd\(\{ runToken \}\)/, 'ad show should capture the active run token');
  assert.match(js, /function restart\(\)[\s\S]*runToken \+= 1/, 'restart should invalidate outstanding ad callbacks');
});

test('browser preview renders a distinct success settlement without revive CTA', () => {
  const js = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');
  assert.match(js, /state\.result === 'success'/, 'DOM runtime should branch on explicit success result');
  assert.match(js, /state\.gameOver && state\.result === 'success'/, 'DOM loop should consume the state-machine result instead of reclassifying from remaining time');
  assert.match(js, /reviveButton\.hidden\s*=\s*isSuccess/, 'success settlement must hide the rewarded-revive CTA');
  assert.match(js, /overlay\.dataset\.result\s*=\s*isSuccess \? 'success' : 'failure'/, 'overlay should expose success/failure styling state');
});

test('CCTV anomaly overlays share one target axis instead of drifting apart', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.match(css, /--cctv-target-x:\s*50%/, 'CCTV target should be anchored to the scene center axis');
  assert.match(css, /\.door-gap-glow[\s\S]*left:\s*var\(--cctv-target-x\)/, 'door glow should use the shared target axis');
  assert.match(css, /\.thermal-ghost[\s\S]*left:\s*var\(--cctv-target-x\)/, 'thermal ghost should use the shared target axis');
  assert.match(css, /\.detection-corners[\s\S]*left:\s*var\(--cctv-target-x\)/, 'detection corners should use the shared target axis');
});

test('CCTV monitor uses animated GIF-like surveillance loops', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.match(css, /\.cctv-loop/, 'monitor should expose a dedicated animated CCTV loop layer');
  assert.match(css, /@keyframes\s+cctvDoorLoop/, 'door-gap glow should loop like an animated surveillance feed');
  assert.match(css, /@keyframes\s+thermalGhostLoop/, 'thermal ghost should shimmer as a loop instead of a static marker');
  assert.match(css, /@keyframes\s+cameraMicroShake/, 'CCTV frame should have subtle camera motion');
});

test('action buttons render elevator-specific icons beside labels', () => {
  const js = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');
  for (const actionId of ['openDoor', 'closeDoor', 'moveUp', 'moveDown', 'emergencyStop', 'restartSystem', 'inspectLog']) {
    assert.match(js, new RegExp(`${actionId}:`), `icon map should include ${actionId}`);
  }
  assert.match(js, /className\s*=\s*'action-icon'/, 'action buttons should include an icon node');
  assert.match(js, /className\s*=\s*'action-label'/, 'action buttons should preserve readable labels beside icons');
});

test('game UI keeps onboarding and controls icon-first with low text density', () => {
  assert.match(html, /class="mission-strip"/, 'start overlay should use compact mission chips instead of a prose menu');
  assert.match(html, /class="hud-icon"/, 'status tiles should expose icon-first HUD affordances');
  const js = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');
  assert.match(js, /className\s*=\s*'action-keycap'/, 'actions should render as hardware-style keycaps');
  assert.match(html, /id="moreActions"/, 'secondary actions should move behind a thumb-reachable more control');
  assert.match(html, /id="secondaryActionsSheet"/, 'low-frequency actions should render in a dedicated bottom sheet');
  assert.match(html, /class="action-guide"/, 'desktop action panel should include compact guidance cards');
  assert.match(html, /先看 CCTV/, 'guidance should reinforce CCTV-first play');
  assert.match(html, /按推荐键/, 'guidance should explain recommended action highlighting');
  assert.match(html, /data-role="primary-start"/, 'start button should be a single primary handoff control');
  assert.doesNotMatch(html, /class="start-checklist"/, 'start overlay should not render a text-heavy checklist');
  assert.doesNotMatch(html, /class="start-rules"/, 'start overlay should not render rule badges as a menu');
  assert.doesNotMatch(html, /目标：值守 60 秒/, 'start overlay should not ship prose-like instruction copy');
});

test('debug trigger is hidden outside explicit debug mode and action labels stay short', () => {
  const js = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.match(js, /ACTION_SHORT_LABELS/, 'runtime should map long action names to short HUD labels');
  assert.match(js, /restartSystem:\s*'重启'/, 'restart action should use a compact HUD label');
  assert.match(js, /inspectLog:\s*'日志'/, 'log action should use a compact HUD label');
  assert.match(js, /unlockHiddenLog:\s*'解码'/, 'decode action should use a compact HUD label');
  assert.match(js, /PRIMARY_ACTION_IDS\s*=\s*new Set\(\['closeDoor', 'moveUp', 'emergencyStop'\]\)/, 'mobile HUD should keep only the three highest-frequency actions visible');
  assert.match(js, /URLSearchParams[\s\S]*debug/, 'diagnostic controls should require an explicit debug query flag');
  assert.match(js, /forceAnomaly\.hidden\s*=\s*!debugMode/, 'diagnostic trigger should be hidden by default');
  assert.match(html, /class="secondary diagnostic-trigger"/, 'force anomaly control should remain available to debug mode');
  assert.match(css, /#forceAnomaly[\s\S]*position:\s*absolute/, 'diagnostic trigger should not occupy the main control deck');
});

test('first-run guidance stays HUD-like and not tutorial prose', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  const js = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');
  assert.match(js, /getOperatorCue/, 'runtime should compute first-run guidance from game state');
  assert.match(css, /\.operator-cue/, 'operator cue should have a dedicated HUD style');
  assert.doesNotMatch(html, /class="tutorial"/, 'first-run guidance should not add a tutorial panel');
});

test('layout makes CCTV the dominant play surface over chrome', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.match(css, /grid-template-columns:\s*0\.52fr\s+1\.48fr/, 'desktop layout should bias space toward the CCTV monitor');
  assert.match(css, /\.monitor-panel[\s\S]*min-height:\s*560px/, 'monitor panel should be taller than supporting status chrome');
  assert.match(css, /\.status-list div[\s\S]*min-height:\s*50px/, 'status tiles should compress into a secondary instrument rail');
  assert.match(css, /\.game-title[\s\S]*font-size:\s*clamp\(1\.4rem/, 'top title should be compact so it does not compete with the monitor');
  assert.match(css, /\.start-card[\s\S]*opacity:\s*0\.78/, 'start handoff should be subdued so it does not steal focus from CCTV');
  assert.match(css, /\.start-card button\[data-role="primary-start"\][\s\S]*filter:\s*saturate\(0\.72\)/, 'OVERRIDE button should be visually quieter than the monitor');
});

test('left support rail prioritizes critical elevator telemetry', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.match(html, /data-priority="critical"[^>]*><span class="hud-icon">F<\/span>/, 'floor tile should be marked as critical telemetry');
  assert.match(html, /data-priority="critical"[^>]*><span class="hud-icon">▯<\/span>/, 'door tile should be marked as critical telemetry');
  assert.match(html, /data-priority="danger"[^>]*><span class="hud-icon danger">!<\/span>/, 'anomaly tile should be marked as danger telemetry');
  assert.match(css, /\.status-list div\[data-priority="critical"\][\s\S]*border-color:\s*rgba\(97,255,190,0\.42\)/, 'critical tiles should have higher contrast borders');
  assert.match(css, /\.status-list div\[data-priority="secondary"\][\s\S]*opacity:\s*0\.62/, 'secondary telemetry should be visually de-emphasized');
  assert.match(css, /\.status-list div::after[\s\S]*display:\s*none/, 'decorative circles should be removed from dense rail tiles');
});

test('start handoff is a compact authorization strip, not a second status panel', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  assert.match(css, /\.start-overlay[\s\S]*position:\s*static/, 'start handoff should be in document flow rather than covering the rail');
  assert.match(css, /\.start-overlay[\s\S]*justify-content:\s*end/, 'start handoff should sit as a low global authorization strip');
  assert.match(css, /\.start-card[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s+auto/, 'start card should become a compact authorization strip');
  assert.match(css, /\.start-card \.eyebrow,[\s\S]*\.risk-strip \{\s*display:\s*none/, 'decorative onboarding chips should be hidden visually');
  assert.match(css, /\.start-card h2[\s\S]*font-size:\s*0\.82rem/, 'handoff title should not compete with telemetry');
});

test('default elevator bottom HUD reports system state, not camera signal state', () => {
  const skin = readFileSync(new URL('../src/skins/elevator/skin.json', import.meta.url), 'utf8');
  assert.match(skin, /"monitorSignalStable":\s*"SYSTEM: STABLE"/, 'bottom HUD should describe system state');
  assert.doesNotMatch(skin, /"monitorSignalStable":\s*"SIGNAL: STABLE"/, 'bottom HUD should not conflict with camera SIGNAL DEGRADED label');
});

test('portrait mobile layout keeps the full playable surface in one viewport', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  const marker = '/* Mobile portrait final pass: keep CCTV first and keep the start strip reachable. */';
  const finalMobile = css.slice(css.lastIndexOf(marker));

  assert.ok(finalMobile.startsWith(marker), 'mobile portrait should have one final authoritative override pass');
  assert.match(finalMobile, /html, body \{ height:\s*100%; min-height:\s*100dvh; overflow:\s*hidden;/, 'final mobile rule should prohibit page-level scrolling');
  assert.match(finalMobile, /\.console-shell\s*\{[\s\S]*width:\s*100%;[\s\S]*height:\s*100dvh;[\s\S]*display:\s*grid;[\s\S]*overflow:\s*hidden/, 'mobile shell should fit the available viewport without scrollbar-width overflow');
  assert.doesNotMatch(finalMobile, /width:\s*100vw/, 'mobile shell must not use 100vw because the vertical scrollbar can clip the right edge');
  assert.match(finalMobile, /grid-template-areas:\s*"monitor"\s*"actions"\s*"status"\s*"logs"/, 'mobile should keep CCTV first, then controls, telemetry, logs');
  assert.match(finalMobile, /\.start-overlay[\s\S]*position:\s*static;[\s\S]*justify-content:\s*center/, 'mobile start strip should stay in flow and centered, not overlay panels');
  assert.match(finalMobile, /\.start-card[\s\S]*width:\s*min\(100%,\s*420px\)/, 'mobile start strip should be full-width constrained for thumb reach');
  assert.match(finalMobile, /\.action-dock\s*\{[\s\S]*grid-template-columns:\s*minmax\(0,\s*1fr\)\s*68px/, 'mobile controls should reserve one thumb column for more actions');
  assert.match(finalMobile, /\.actions\s*\{[\s\S]*grid-template-columns:\s*repeat\(3,\s*minmax\(0,\s*1fr\)\)/, 'mobile controls should keep only three primary keycaps visible');
  assert.match(finalMobile, /\.secondary-actions-panel[\s\S]*border-radius:\s*18px 18px 0 0/, 'secondary controls should open as a bottom sheet');
});
