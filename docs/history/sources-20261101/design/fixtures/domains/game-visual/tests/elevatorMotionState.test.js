import assert from 'node:assert/strict';
import test from 'node:test';

import { performAction } from '../src/actions.js';
import { createInitialState, tickState } from '../src/state.js';

test('door actions expose a real transition phase before settling', () => {
  const opened = performAction(createInitialState(), 'openDoor');
  assert.equal(opened.ok, true);
  assert.deepEqual(opened.state.transition, {
    kind: 'doorOpening',
    duration: 1,
    remaining: 1,
    fromDoor: 'closed',
    toDoor: 'open',
  });

  const settled = tickState(opened.state, 1);
  assert.equal(settled.transition, null);
  assert.equal(settled.door, 'open');
});

test('movement cannot be stacked while a transition is active, but emergency stop can interrupt it', () => {
  const first = performAction(createInitialState(), 'moveUp');
  const stacked = performAction(first.state, 'moveUp');
  assert.equal(stacked.ok, false);
  assert.equal(stacked.state.floor, 2);
  assert.match(stacked.message, /尚未完成|等待/);

  const stopped = performAction(first.state, 'emergencyStop');
  assert.equal(stopped.ok, true);
  assert.equal(stopped.state.moving, false);
  assert.equal(stopped.state.transition.kind, 'emergencyStop');
});

test('elevator movement lasts two ticks and automatically returns to idle', () => {
  const moved = performAction(createInitialState(), 'moveUp');
  assert.equal(moved.ok, true);
  assert.equal(moved.state.floor, 2);
  assert.equal(moved.state.moving, true);
  assert.equal(moved.state.direction, 'up');
  assert.deepEqual(moved.state.transition, {
    kind: 'movingUp',
    duration: 2,
    remaining: 2,
    fromFloor: 1,
    toFloor: 2,
  });

  const midway = tickState(moved.state, 1);
  assert.equal(midway.moving, true);
  assert.equal(midway.transition.remaining, 1);

  const settled = tickState(midway, 1);
  assert.equal(settled.moving, false);
  assert.equal(settled.direction, 'idle');
  assert.equal(settled.transition, null);
  assert.equal(settled.floor, 2);
});
