import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

import { getCanvasStartControls, getCanvasViewportMetrics, onCanvasClick } from '../platform/canvasRenderer.js';
import { bindMiniGameLifecycle, checkDouyinSidebar, navigateToDouyinSidebar } from '../platform/douyinIntegration.js';
import { createMiniGameClock } from '../platform/miniGameClock.js';
import { createInitialState } from '../src/state.js';

test('mini-game clock does not consume time before explicit start', () => {
  let now = 1_000;
  const clock = createMiniGameClock(() => now);
  now += 5_000;
  assert.equal(clock.consumeDeltaSeconds(), 0);
  clock.start();
  now += 3_200;
  assert.equal(clock.consumeDeltaSeconds(), 3);
});

test('mini-game clock excludes background time after hide and show', () => {
  let now = 1_000;
  const clock = createMiniGameClock(() => now);
  clock.start();
  now += 2_000;
  assert.equal(clock.consumeDeltaSeconds(), 2);
  clock.pause();
  now += 25_000;
  assert.equal(clock.consumeDeltaSeconds(), 0);
  clock.resume();
  now += 1_000;
  assert.equal(clock.consumeDeltaSeconds(), 1);
});

test('canvas viewport follows the real device aspect ratio and safe area', () => {
  const metrics = getCanvasViewportMetrics({
    windowWidth: 390,
    windowHeight: 844,
    safeArea: { top: 47 },
    menuButtonRect: { left: 306 },
  });
  assert.equal(metrics.width, 750);
  assert.ok(metrics.height > 1623 && metrics.height < 1624);
  assert.ok(metrics.safeTop > 90 && metrics.safeTop < 91);
  assert.ok(metrics.menuButtonLeft > 588 && metrics.menuButtonLeft < 589);
});

test('canvas start gate exposes separate start and Douyin sidebar targets', () => {
  const state = createInitialState();
  const controls = getCanvasStartControls(1334, 0);
  let starts = 0;
  let sidebar = 0;
  onCanvasClick(
    controls.start.x + controls.start.w / 2,
    controls.start.y + controls.start.h / 2,
    state,
    { onStart: () => { starts += 1; }, onSidebar: () => { sidebar += 1; } },
    { started: false, sidebarAvailable: true },
  );
  onCanvasClick(
    controls.sidebar.x + controls.sidebar.w / 2,
    controls.sidebar.y + controls.sidebar.h / 2,
    state,
    { onStart: () => { starts += 1; }, onSidebar: () => { sidebar += 1; } },
    { started: false, sidebarAvailable: true },
  );
  assert.equal(starts, 1);
  assert.equal(sidebar, 1);
});

test('mini-game lifecycle binds hide and show without assuming one host', () => {
  let hideHandler;
  let showHandler;
  let pauses = 0;
  let resumes = 0;
  const api = {
    onHide(handler) { hideHandler = handler; },
    onShow(handler) { showHandler = handler; },
  };
  bindMiniGameLifecycle(api, {
    onPause: () => { pauses += 1; },
    onResume: () => { resumes += 1; },
  });
  hideHandler();
  showHandler({ scene: '021036' });
  assert.equal(pauses, 1);
  assert.equal(resumes, 1);
});

test('Douyin sidebar availability uses the official checkScene contract', async () => {
  let options;
  const api = {
    navigateToScene() {},
    checkScene(value) {
      options = value;
      value.success?.({ isExist: true });
    },
  };
  assert.equal(await checkDouyinSidebar(api), true);
  assert.equal(options.scene, 'sidebar');
  assert.equal(await checkDouyinSidebar({ navigateToScene() {} }), false);
});

test('Douyin sidebar integration calls the official sidebar scene and fails safely elsewhere', async () => {
  let options;
  const api = {
    navigateToScene(value) {
      options = value;
      value.success?.({});
    },
  };
  assert.equal(await navigateToDouyinSidebar(api), true);
  assert.equal(options.scene, 'sidebar');
  assert.equal(await navigateToDouyinSidebar({}), false);
});

test('mini-game runtime wires explicit start, lifecycle pause, real viewport and sidebar capability', () => {
  const source = readFileSync(new URL('../platform/miniGameRuntime.js', import.meta.url), 'utf8');
  assert.match(source, /createMiniGameClock/);
  assert.match(source, /createMiniGameAudio/);
  assert.match(source, /openInspection/);
  assert.match(source, /submitInspection/);
  assert.match(source, /expireInspection/);
  assert.match(source, /onDecision:\s*handleDecision/);
  assert.match(source, /getStorageSync/);
  assert.match(source, /setStorageSync/);
  assert.match(source, /onToggleMute:\s*toggleMute/);
  for (const cue of ['boot', 'release', 'lockdown', 'wrong']) {
    assert.match(source, new RegExp(`audio\\.play\\(['\"]${cue}['\"]\\)`));
  }
  assert.match(source, /vibrateShort/);
  assert.match(source, /getMenuButtonBoundingClientRect/);
  assert.match(source, /bindMiniGameLifecycle/);
  assert.match(source, /navigateToDouyinSidebar/);
  assert.match(source, /init\(canvas, info\)/);
  assert.match(source, /onStart:\s*start/);
  assert.match(source, /onSidebar:\s*openSidebar/);
  assert.match(source, /clock\.consumeDeltaSeconds\(\)/);
});
