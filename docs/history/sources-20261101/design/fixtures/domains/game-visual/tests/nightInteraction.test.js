import test from 'node:test';
import assert from 'node:assert/strict';

import anomalies from '../src/content/anomalies.json' with { type: 'json' };
import endings from '../src/content/endings.json' with { type: 'json' };
import normalShifts from '../src/content/normalShifts.json' with { type: 'json' };
import { createInitialState } from '../src/state.js';
import {
  classifyCurrentShift,
  closeProtocolQuery,
  createNightDebrief,
  openProtocolQuery,
  resolveCurrentHighRisk,
  resolveIdentityDecision,
  verifyCurrentIdentity,
} from '../src/nightInteraction.js';

function withShift(shift) {
  const state = createInitialState();
  state.night.currentShift = structuredClone(shift);
  state.night.roundType = shift.roundType;
  state.night.activeProtocols = [{ id: 'p1', text: '13 层请求必须封锁' }];
  return state;
}

test('protocol query opens and closes a runtime-owned overlay without consuming resources', () => {
  const state = withShift(anomalies[0]);
  const opened = openProtocolQuery(state);
  assert.equal(opened.night.overlay, 'protocolQuery');
  assert.deepEqual(opened.night.protocolQuery.map(item => item.id), ['p1']);
  assert.deepEqual(opened.investigation.tools, state.investigation.tools);
  assert.equal(closeProtocolQuery(opened).night.overlay, null);
});

test('identity verification reveals evidence without forcing anomaly classification', () => {
  const shift = normalShifts.find(item => item.id === 'normal_shift_02');
  const result = verifyCurrentIdentity(withShift(shift));
  assert.equal(result.accepted, true);
  assert.equal(result.state.night.roundType, 'identity');
  assert.match(result.state.lastFeedback, /核验结果/);
  assert.equal(result.state.investigation.discoveredEvidence.at(-1).id, 'normal_shift_02_cam01');
  assert.equal(result.state.night.decisions.length, 0);
});

test('identity release and reject settle normal or anomalous identities and record contamination', () => {
  const normal = normalShifts.find(item => item.id === 'normal_shift_02');
  const anomaly = anomalies.find(item => item.id === 'person_unknown_identity');
  const allowed = resolveIdentityDecision(withShift(normal), 'release');
  const rejected = resolveIdentityDecision(withShift(anomaly), 'reject');
  const wrong = resolveIdentityDecision(withShift(anomaly), 'release');

  assert.equal(allowed.accepted, true);
  assert.equal(allowed.correct, true);
  assert.equal(rejected.correct, true);
  assert.equal(rejected.state.night.decisions.at(-1).choice, 'identity:reject');
  assert.equal(wrong.correct, false);
  assert.ok(wrong.state.contamination.value > 0);
  assert.equal(wrong.state.gameOver, false);
});

test('classification records the category and routes high-risk anomalies to contextual disposal', () => {
  const shift = anomalies.find(item => item.roundType === 'highRisk');
  const result = classifyCurrentShift(withShift(shift), shift.category);
  assert.equal(result.correct, true);
  assert.equal(result.state.night.roundType, 'highRisk');
  assert.equal(result.state.night.decisions.at(-1).classification, shift.category);
  assert.equal(result.state.night.decisions.at(-1).correct, true);
});

test('high-risk disposal consumes power, records consequences and never ends the run on a mistake', () => {
  const shift = anomalies.find(item => item.id === 'space_floor_13');
  const classified = classifyCurrentShift(withShift(shift), shift.category).state;
  const wrong = resolveCurrentHighRisk(classified, 'restart');
  assert.equal(wrong.accepted, true);
  assert.equal(wrong.correct, false);
  assert.equal(wrong.state.gameOver, false);
  assert.ok(wrong.state.power < classified.power);
  assert.equal(wrong.state.night.decisions.at(-1).action, 'restart');
});

test('debrief selects chain endings from eventChainFlags and keeps modifiers as separate report data', () => {
  const state = createInitialState();
  state.night.eventChainFlags = ['camera_chain_compromised'];
  state.night.nextShiftModifiers = ['unreliable_cam07'];
  const report = createNightDebrief(state, endings);
  assert.equal(report.ending.id, 'camera_taken');
  assert.deepEqual(report.nextShiftModifiers, ['unreliable_cam07']);
});
test('debrief derives timeline, accuracy and deterministic ending from live night state', () => {
  const state = createInitialState();
  state.night.decisions = [
    { sequence: 1, contentId: 'a', correct: true, choice: 'release' },
    { sequence: 2, contentId: 'b', correct: false, classification: 'device' },
  ];
  state.contamination = { value: 80, tier: 'severe', history: [{ sequence: 3, value: 80 }] };
  state.night.eventChainHistory = [
    { chainId: 'duplicate_passenger', stepId: 'first_visit', correct: false },
  ];
  const report = createNightDebrief(state, endings);
  assert.equal(report.summary.accuracy, 0.5);
  assert.equal(report.ending.id, 'contaminated_survivor');
  assert.equal(report.timeline.length, 4);
});
