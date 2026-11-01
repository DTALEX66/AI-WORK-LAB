import assert from 'node:assert/strict';
import test from 'node:test';

import { createCctvMotionController } from '../platform/cctvMotion.js';
import { createInitialState } from '../src/state.js';

test('CCTV controller exposes visible closed-opening-open phases', () => {
  let now = 1000;
  const controller = createCctvMotionController(() => now);
  const before = createInitialState();
  const after = { ...before, door: 'open', transition: { kind: 'doorOpening', duration: 1, remaining: 1 } };
  controller.startAction('openDoor', before, after);

  assert.equal(controller.sample(after).cctvState, '00_idle_closed');
  now = 1250;
  assert.equal(controller.sample(after).cctvState, '02_door_opening');
  now = 1950;
  assert.equal(controller.sample(after).cctvState, '01_door_open');
  now = 2100;
  assert.equal(controller.sample(after).active, false);
});

test('CCTV movement animates shake, floor reel and then settles', () => {
  let now = 2000;
  const controller = createCctvMotionController(() => now);
  const before = createInitialState();
  const after = {
    ...before,
    floor: 2,
    moving: true,
    direction: 'up',
    transition: { kind: 'movingUp', duration: 2, remaining: 2, fromFloor: 1, toFloor: 2 },
  };
  controller.startAction('moveUp', before, after);

  now = 2450;
  const first = controller.sample(after);
  now = 2750;
  const second = controller.sample(after);
  assert.equal(first.cctvState, '04_moving_up');
  assert.equal(first.active, true);
  assert.notEqual(first.offsetY, second.offsetY);
  assert.ok(first.floorReel > 1 && first.floorReel < 2);
  assert.equal(first.fromFloor, 1);
  assert.equal(first.toFloor, 2);

  now = 4100;
  const settled = controller.sample({ ...after, moving: false, direction: 'idle', transition: null });
  assert.equal(settled.active, false);
  assert.equal(settled.floorReel, 2);
});

test('CCTV motion pauses with ads/background and resumes without skipping frames', () => {
  let now = 5000;
  const controller = createCctvMotionController(() => now);
  const before = createInitialState();
  const after = { ...before, floor: 2, moving: true, direction: 'up' };
  controller.startAction('moveUp', before, after);
  now = 5500;
  const beforePauseFrame = controller.sample(after);
  const beforePause = beforePauseFrame.progress;
  controller.pause();
  now = 8500;
  const pausedFrame = controller.sample(after);
  assert.equal(pausedFrame.progress, beforePause);
  assert.equal(pausedFrame.frameTime, beforePauseFrame.frameTime);
  controller.resume();
  now = 8800;
  const resumedFrame = controller.sample(after);
  assert.ok(resumedFrame.progress > beforePause);
  assert.ok(resumedFrame.frameTime > pausedFrame.frameTime);
});

test('anomaly reveal produces time-varying glitch instead of a static image swap', () => {
  let now = 3000;
  const controller = createCctvMotionController(() => now);
  const before = createInitialState();
  const after = { ...before, activeAnomaly: 'camera_delay', anomalyLevel: 2 };
  controller.startAnomaly(before, after);

  now = 3150;
  const a = controller.sample(after);
  now = 3475;
  const b = controller.sample(after);
  assert.equal(a.kind, 'anomalyReveal');
  assert.equal(a.cctvState, '11_camera_glitch');
  assert.notEqual(a.glitchAlpha, b.glitchAlpha);
  assert.notEqual(a.offsetX, b.offsetX);
});
