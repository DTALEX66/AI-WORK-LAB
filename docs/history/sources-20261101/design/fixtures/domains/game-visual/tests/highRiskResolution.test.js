import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createHighRiskState,
  resolveHighRiskAction,
} from '../src/highRiskResolution.js';

test('correct high-risk action resolves the event and consumes its real resource cost', () => {
  const state = createHighRiskState({ power: 40 });
  const event = { id: 'shaft_entry', acceptedActions: ['emergencyStop'], costs: { emergencyStop: 15 } };
  const result = resolveHighRiskAction(state, event, 'emergencyStop');

  assert.equal(result.accepted, true);
  assert.equal(result.correct, true);
  assert.equal(result.state.power, 25);
  assert.equal(result.state.resolvedEvents.includes('shaft_entry'), true);
});

test('wrong high-risk action changes later shifts instead of ending immediately', () => {
  const state = createHighRiskState({ power: 40 });
  const event = {
    id: 'camera_replacement',
    acceptedActions: ['restart'],
    costs: { lockdownFloor: 10 },
    wrongModifiers: { lockdownFloor: 'unreliable_cam07' },
  };
  const result = resolveHighRiskAction(state, event, 'lockdownFloor');

  assert.equal(result.accepted, true);
  assert.equal(result.correct, false);
  assert.equal(result.state.power, 30);
  assert.ok(result.state.nextShiftModifiers.includes('unreliable_cam07'));
  assert.equal(result.state.gameOver, false);
});
