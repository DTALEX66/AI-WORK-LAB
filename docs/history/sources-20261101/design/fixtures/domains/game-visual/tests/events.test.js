import assert from 'node:assert/strict';
import test from 'node:test';

import { createInitialState } from '../src/state.js';
import { ANOMALIES, applyAnomaly, findAnomaly, pickNextAnomaly } from '../src/events.js';
import { loadSkin, getSkin } from '../src/skinManager.js';
import elevatorSkin from '../src/skins/elevator/skin.json' with { type: 'json' };
import CONFIG from '../src/gameConfig.js';

test('anomaly catalogue contains at least five playable events', () => {
  assert.ok(ANOMALIES.length >= 5);
  for (const event of ANOMALIES) {
    assert.ok(event.id);
    assert.ok(event.title);
    assert.ok(event.severity >= 1);
    assert.ok(event.adHint);
  }
});

test('applyAnomaly mutates system state and logs the event', () => {
  const state = createInitialState();
  const result = applyAnomaly(state, 'phantom_floor');

  assert.equal(result.state.floor, 3);
  assert.equal(result.state.anomalyLevel, 2);
  assert.match(result.state.logs.at(-1).text, /不存在的楼层/);
});

test('applyAnomaly uses current skin anomaly log copy', () => {
  const skin = structuredClone(elevatorSkin);
  skin.ui.anomalyEventLog = '皮肤异常：{title} / {hint}';
  loadSkin(skin);

  const result = applyAnomaly(createInitialState(), 'phantom_floor');

  assert.match(result.state.logs.at(-1).text, /皮肤异常：不存在的楼层/);
  loadSkin(elevatorSkin);
});

test('anomaly numeric effects add meters and apply delta floor values', () => {
  const state = { ...createInitialState(), floor: 1, passengers: 2, anomalyLevel: 2 };

  const floorResult = applyAnomaly(state, 'phantom_floor');
  assert.equal(floorResult.state.floor, 3, '+2 delta from floor 1');
  assert.equal(floorResult.state.anomalyLevel, 4, 'anomalyLevel 2 + skin 2');

  const passengerResult = applyAnomaly(state, 'zero_passenger_shadow');
  assert.equal(passengerResult.state.passengers, 0, 'passengers should be set to absolute skin value');
  assert.equal(passengerResult.state.anomalyLevel, 4, 'anomaly level should increase by skin value');
});

test('anomaly string delta effects clamp meter fields', () => {
  const result = applyAnomaly({ ...createInitialState(), floor: CONFIG.bounds.maxFloor - 1 }, 'floor_jump');

  assert.equal(result.state.floor, CONFIG.bounds.maxFloor, 'string delta floor effects should clamp to playable max floor');
});

test('anomaly catalogue contains at least 12 events for good variety', () => {
  assert.ok(ANOMALIES.length >= 12);
  const ids = ANOMALIES.map(e => e.id);
  const unique = new Set(ids);
  assert.equal(unique.size, ANOMALIES.length, 'all anomaly IDs must be unique');
});

test('pickNextAnomaly is deterministic when random source is injected', () => {
  const selected = pickNextAnomaly(createInitialState(), () => 0);
  assert.ok(selected);
  assert.ok(selected.id);
  assert.ok(selected.severity >= 1);
});

test('first anomaly is limited to teachable low or medium severity events', () => {
  const first = pickNextAnomaly(createInitialState(), () => 0);
  assert.ok(first.severity <= CONFIG.anomaly.firstMaxSeverity);
});

test('new anomalies: door_refuse forces door open', () => {
  const result = applyAnomaly(createInitialState(), 'door_refuse');
  assert.equal(result.state.door, 'open');
});

test('new anomalies: floor_jump skips floors', () => {
  const state = { ...createInitialState(), floor: 1 };
  const result = applyAnomaly(state, 'floor_jump');
  assert.equal(result.state.floor, 5);
});

test('new anomalies: emergency_lights drains significant power', () => {
  const state = { ...createInitialState(), power: 100 };
  const result = applyAnomaly(state, 'emergency_lights');
  assert.ok(result.state.power < 100);
});

test('applyAnomaly adds a locked hidden log to state', () => {
  const result = applyAnomaly(createInitialState(), 'phantom_floor');
  assert.ok(result.state.hiddenLogs.length >= 1);
  assert.equal(result.state.hiddenLogs[0].locked, true);
  assert.equal(result.state.hiddenLogs[0].id, 'phantom_floor_log');
});

test('applyAnomaly does not duplicate hidden logs', () => {
  const state = createInitialState();
  const first = applyAnomaly(state, 'phantom_floor');
  const second = applyAnomaly(first.state, 'phantom_floor');

  const phantomLogs = second.state.hiddenLogs.filter(l => l.id === 'phantom_floor_log');
  assert.equal(phantomLogs.length, 1);
});

test('all 12 anomalies have a corresponding hidden log entry', () => {
  const skin = getSkin();
  for (const a of ANOMALIES) {
    assert.ok(skin.hiddenLogs[a.id], `${a.id} has no hidden log entry`);
  }
});

test('applyAnomaly increments post-run summary tracking counters', () => {
  const state = createInitialState();
  const result = applyAnomaly(state, 'stop_failure');
  assert.equal(result.state.anomaliesTriggeredTotal, 1);
  assert.ok(result.state.maxAnomalySeverity >= 3);
});
