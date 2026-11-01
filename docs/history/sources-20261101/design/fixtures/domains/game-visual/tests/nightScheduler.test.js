import assert from 'node:assert/strict';
import test from 'node:test';

import anomalies from '../src/content/anomalies.json' with { type: 'json' };
import normalShifts from '../src/content/normalShifts.json' with { type: 'json' };
import protocols from '../src/content/protocols.json' with { type: 'json' };
import eventChains from '../src/content/eventChains.json' with { type: 'json' };
import { createInitialState } from '../src/state.js';
import {
  advanceCurrentNightEventChain,
  createNightSchedule,
  scheduleNextNightShift,
} from '../src/nightScheduler.js';

const content = { anomalies, normalShifts, protocols, eventChains };

test('night schedule deterministically installs protocols and the first normal shift', () => {
  const first = createNightSchedule(createInitialState(), content, { random: () => 0, protocolCount: 3 });
  const second = createNightSchedule(createInitialState(), content, { random: () => 0, protocolCount: 3 });

  assert.deepEqual(first.night, second.night);
  assert.equal(first.night.activeProtocols.length, 3);
  assert.equal(first.night.currentShift.id, normalShifts[0].id);
  assert.equal(first.night.currentShift.shiftKind, 'normal');
  assert.equal(first.night.roundType, normalShifts[0].roundType);
  assert.deepEqual(first.night.currentShift.activeProtocols, first.night.activeProtocols);
  assert.ok(first.night.activeProtocols.some(protocol => (
    protocol.protocolTags || []
  ).some(tag => first.night.currentShift.protocolTags.includes(tag))));
});

test('next shift alternates into anomaly content and advances roundType/index without mutating input', () => {
  const initial = createNightSchedule(createInitialState(), content, { random: () => 0 });
  const next = scheduleNextNightShift(initial, content, { random: () => 0 });

  assert.equal(initial.night.shiftIndex, 0);
  assert.equal(initial.night.currentShift.shiftKind, 'normal');
  assert.equal(next.night.shiftIndex, 1);
  assert.equal(next.night.currentShift.id, anomalies[0].id);
  assert.equal(next.night.currentShift.shiftKind, 'anomaly');
  assert.equal(next.night.roundType, anomalies[0].roundType);
  assert.deepEqual(next.night.currentShift.activeProtocols, next.night.activeProtocols);
  assert.equal(next.investigation.activeCamera, 'cam01');
  assert.deepEqual(next.investigation.discoveredEvidence, []);
});

test('event chains remain dormant during teaching and schedule their first real step after tutorial', () => {
  const initial = createNightSchedule(createInitialState(), content, { random: () => 0 });
  assert.equal(initial.night.activeEventChainId, 'duplicate_passenger');
  assert.equal(initial.night.currentShift.eventChainId, undefined);

  const ready = { ...initial, tutorialStep: 4 };
  const next = scheduleNextNightShift(ready, content, { random: () => 0 });
  assert.equal(next.night.currentShift.eventChainId, 'duplicate_passenger');
  assert.equal(next.night.currentShift.eventChainStep, 'first_visit');
  assert.equal(next.night.currentShift.id, 'normal_shift_02');
  assert.equal(next.night.roundType, 'identity');
});

test('completed event chain records all three outcomes and applies flagged consequence once', () => {
  let state = createNightSchedule(createInitialState(), content, { random: () => 0 });
  state = { ...state, tutorialStep: 4 };
  for (let index = 0; index < 3; index += 1) {
    state = scheduleNextNightShift(state, content, { random: () => 0 });
    const result = advanceCurrentNightEventChain(state, content, { correct: false });
    assert.equal(result.advanced, true);
    state = result.state;
  }
  assert.equal(state.night.eventChains.duplicate_passenger.completed, true);
  assert.equal(state.night.eventChainHistory.length, 3);
  assert.ok(state.night.eventChainFlags.includes('chain_compromised'));
  assert.equal(state.contamination.value, 18);
  assert.deepEqual(state.night.nextShiftModifiers, ['duplicate_feed']);
  const consumed = scheduleNextNightShift(state, content, { random: () => 0 });
  assert.deepEqual(consumed.night.currentShift.appliedModifiers, ['duplicate_feed']);
  assert.equal(consumed.night.currentShift.visualState, '14_duplicate_subject');
  assert.deepEqual(consumed.night.nextShiftModifiers, []);
});
test('scheduler rejects incomplete V5 content instead of silently creating a blank round', () => {
  assert.throws(
    () => createNightSchedule(createInitialState(), { normalShifts: [], anomalies, protocols }),
    /normalShifts/,
  );
  assert.throws(
    () => createNightSchedule(createInitialState(), { normalShifts, anomalies: [], protocols }),
    /anomalies/,
  );
});
