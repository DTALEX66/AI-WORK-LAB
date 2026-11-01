import assert from 'node:assert/strict';
import test from 'node:test';

import { shouldApplyReward } from '../src/rewardGuard.js';
import { createInitialState } from '../src/state.js';

const meta = runToken => ({ context: { runToken } });

test('reward guard rejects stale attempts from an earlier run', () => {
  const failure = { ...createInitialState(), gameOver: true, result: 'failure' };
  assert.equal(shouldApplyReward(meta(3), 4, 'revive', failure), false);
});

test('reward guard validates reward type against current run state', () => {
  const playing = {
    ...createInitialState(),
    hiddenLogs: [{ id: 'locked', locked: true }],
  };
  const failure = { ...playing, gameOver: true, result: 'failure' };
  const fakeEnding = { ...failure, fakeEndingTriggered: true, fakeEndingUnlocked: false };
  const success = { ...playing, gameOver: true, result: 'success' };

  assert.equal(shouldApplyReward(meta(1), 1, 'decode', playing), true);
  assert.equal(shouldApplyReward(meta(1), 1, 'decode', success), false);
  assert.equal(shouldApplyReward(meta(1), 1, 'revive', failure), true);
  assert.equal(shouldApplyReward(meta(1), 1, 'revive', success), false);
  assert.equal(shouldApplyReward(meta(1), 1, 'revive', fakeEnding), false);
  assert.equal(shouldApplyReward(meta(1), 1, 'truth', fakeEnding), true);
  assert.equal(shouldApplyReward(meta(1), 1, 'truth', failure), false);
});
