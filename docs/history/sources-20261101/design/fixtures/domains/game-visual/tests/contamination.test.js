import assert from 'node:assert/strict';
import test from 'node:test';

import {
  applyDecisionContamination,
  createContaminationState,
  changeContamination,
  getContaminationTier,
  deriveContaminationEffects,
} from '../src/contamination.js';
import { createInitialState } from '../src/state.js';

test('a wrong decision changes later information reliability without ending the night', () => {
  const base = createContaminationState(48);
  const changed = applyDecisionContamination(base, {
    correct: false,
    contentId: 'device_camera_substitution',
    contaminationEffects: { onMiss: 12, onCorrect: -2 },
  });

  assert.equal(changed.value, 60);
  const effects = deriveContaminationEffects(changed.value);
  assert.equal(effects.tier, 'medium');
  assert.ok(effects.unreliableVerificationPaths.includes('panel'));
  assert.equal('gameOver' in changed, false);
});

test('contamination starts at zero and clamps to 0-100', () => {
  const base = createContaminationState();
  assert.equal(base.value, 0);
  assert.equal(changeContamination(base, 140, 'test').value, 100);
  assert.equal(changeContamination(base, -20, 'test').value, 0);
});

test('contamination tiers use the V5 boundaries', () => {
  assert.equal(getContaminationTier(0), 'normal');
  assert.equal(getContaminationTier(26), 'light');
  assert.equal(getContaminationTier(51), 'medium');
  assert.equal(getContaminationTier(76), 'severe');
});

test('contamination records causal history', () => {
  const changed = changeContamination(createContaminationState(), 18, 'released_anomaly');
  assert.equal(changed.history.length, 1);
  assert.deepEqual(changed.history[0], { delta: 18, reason: 'released_anomaly', value: 18 });
});

test('initial game state carries the Phase A contamination state', () => {
  const state = createInitialState();
  assert.deepEqual(state.contamination, createContaminationState());
});

test('contamination effects never reveal whether the current shift is anomalous', () => {
  for (const value of [0, 30, 60, 90]) {
    const effects = deriveContaminationEffects(value);
    assert.equal('isAnomaly' in effects, false);
    assert.equal('correctDecision' in effects, false);
    assert.ok(effects.reliableVerificationPaths.length >= 1);
  }
});
