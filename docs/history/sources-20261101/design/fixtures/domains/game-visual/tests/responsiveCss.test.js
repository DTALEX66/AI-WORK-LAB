import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');

test('UI V3 Night Relay keeps a three-column desktop cockpit and a complete four-key mobile rail', () => {
  const marker = '/* UI V3 NIGHT RELAY — Monitor primary, Operate secondary. */';
  const v3 = css.slice(css.lastIndexOf(marker));
  assert.ok(v3.startsWith(marker), 'V3 final override must be the winning CSS pass');
  assert.match(v3, /grid-template-columns:\s*236px minmax\(0,\s*1fr\) 252px/, 'desktop should use instrumentation, CCTV, and action columns');
  assert.match(v3, /grid-template-areas:\s*"status monitor actions"\s*"logs monitor actions"/, 'CCTV should span the two desktop cockpit rows');
  assert.match(v3, /@media \(max-width:\s*700px\)[\s\S]*\.action-dock\s*\{[\s\S]*grid-template-columns:\s*repeat\(4,\s*minmax\(0,\s*1fr\)\)/, 'mobile should expose three primary actions plus More as four complete keys');
  assert.match(v3, /@media \(max-width:\s*700px\)[\s\S]*\.actions\s*\{\s*display:\s*contents/, 'nested primary actions should participate in the four-key rail');
  assert.match(v3, /\.actions button,[\s\S]*\.more-actions-button\s*\{[\s\S]*min-height:\s*56px/, 'all primary touch targets should be at least 56px high');
});

test('UI V3 start handoff is a reachable modal instead of a clipped horizontal pill', () => {
  const marker = '/* UI V3 NIGHT RELAY — Monitor primary, Operate secondary. */';
  const v3 = css.slice(css.lastIndexOf(marker));
  assert.match(v3, /\.start-overlay\s*\{[\s\S]*position:\s*fixed/, 'start handoff should overlay the cockpit');
  assert.match(v3, /\.start-card\s*\{[\s\S]*border-radius:\s*8px/, 'start card should use the industrial panel geometry');
  assert.match(v3, /@media \(max-width:\s*700px\)[\s\S]*\.start-overlay\s*\{[\s\S]*align-items:\s*end/, 'mobile start handoff should become a reachable bottom sheet');
  assert.match(v3, /button\[data-role="primary-start"\][\s\S]*min-height:\s*48px/, 'start action should preserve a full touch target');
});

test('wide start handoff preserves the CCTV monitor as the primary surface', () => {
  const css = readFileSync(new URL('../styles.css', import.meta.url), 'utf8');
  const marker = '/* UI V3 NIGHT RELAY — Monitor primary, Operate secondary. */';
  const v3 = css.slice(css.lastIndexOf(marker));

  assert.match(v3, /\.start-overlay\s*\{[\s\S]*justify-content:\s*end/, 'wide handoff should dock to the side instead of centering over CCTV');
  assert.match(v3, /\.start-overlay\s*\{[\s\S]*backdrop-filter:\s*none/, 'wide handoff should not blur the monitor');
  assert.match(v3, /\.start-card\s*\{[\s\S]*width:\s*min\(252px,\s*calc\(100vw\s*-\s*32px\)\)/, 'wide handoff card should fit the dedicated action rail');
  assert.match(v3, /\.start-card\s*\{[\s\S]*margin:\s*0\s+0\s+0\s+auto/, 'wide handoff card should dock exactly to the right edge');
  assert.match(v3, /@media \(max-width:\s*700px\)[\s\S]*\.start-overlay\s*\{[\s\S]*align-items:\s*end/, 'mobile handoff should remain a bottom sheet');
});


test('short portrait devices fall back to shell scrolling instead of clipping panels', () => {
  const marker = '/* Mobile portrait final pass: keep CCTV first and keep the start strip reachable. */';
  const finalMobile = css.slice(css.lastIndexOf(marker));

  assert.match(finalMobile, /@media \(max-width:\s*700px\) and \(orientation:\s*portrait\) and \(max-height:\s*620px\)/, 'short portrait devices need an explicit fallback');
  assert.match(finalMobile, /max-height:\s*620px[\s\S]*\.console-shell\s*\{[\s\S]*height:\s*100dvh;[\s\S]*overflow-y:\s*auto/, 'short portrait shell should scroll internally rather than clip content');
  assert.match(finalMobile, /max-height:\s*620px[\s\S]*\.grid\s*\{[\s\S]*height:\s*auto;[\s\S]*grid-template-rows:\s*minmax\(120px,\s*32vh\)\s+auto\s+auto\s+minmax\(44px,\s*12vh\)/, 'short portrait should retain a useful CCTV minimum and compact log row');
  assert.match(finalMobile, /padding-bottom:\s*max\([^;]*env\(safe-area-inset-bottom\)/, 'mobile shell should reserve bottom safe-area space');
});

test('mobile layout keeps overlays scrollable internally and controls reachable in one viewport', () => {
  const marker = '/* Mobile portrait final pass: keep CCTV first and keep the start strip reachable. */';
  const finalMobile = css.slice(css.lastIndexOf(marker));

  assert.match(css, /min-height:\s*100dvh/, 'mobile browsers should use dynamic viewport height');
  assert.match(css, /\.start-overlay,[\s\S]*?\.failure-overlay[\s\S]*?overflow:\s*auto/, 'modal overlays should scroll internally on short screens');
  assert.match(finalMobile, /"monitor"\s*"actions"\s*"status"\s*"logs"/, 'mobile layout should show controls right after monitor');
  assert.match(finalMobile, /html, body \{ height:\s*100%; min-height:\s*100dvh; overflow:\s*hidden;/, 'portrait should prevent page-level scrolling');
  assert.match(finalMobile, /grid-template-rows:\s*minmax\(0,\s*1fr\)\s+auto\s+auto\s+minmax\(58px,\s*0\.28fr\)/, 'compact layout should fit monitor/actions/status/logs into one viewport');
  assert.match(finalMobile, /\.monitor-caption[\s\S]*?max-height:\s*2\.6em/, 'monitor text should be a compact caption on phones');
  assert.match(css, /\.cctv-stage/, 'monitor should render a CCTV scene layer');
  assert.match(css, /@media \(max-height:\s*480px\) and \(orientation:\s*landscape\)/, 'phone landscape should have a dedicated compact rule');
});
