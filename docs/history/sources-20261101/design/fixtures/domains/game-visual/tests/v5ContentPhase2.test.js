import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const readJson = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), 'utf8'));
const anomalies = readJson('src/content/anomalies.json');
const normalShifts = readJson('src/content/normalShifts.json');
const passengers = readJson('src/content/passengers.json');
const eventChains = readJson('src/content/eventChains.json');

const categories = ['person', 'count', 'space', 'time', 'device', 'dynamic'];

test('Phase 2 ships exactly 30 anomalies split evenly across six categories', () => {
  assert.equal(anomalies.length, 30);
  for (const category of categories) {
    assert.equal(anomalies.filter(item => item.category === category).length, 5, category);
  }
  assert.equal(new Set(anomalies.map(item => item.id)).size, 30);
});

test('every V5 anomaly has at least two non-audio verification paths', () => {
  for (const anomaly of anomalies) {
    const paths = new Set(anomaly.silentEvidence);
    assert.ok(paths.size >= 2, anomaly.id);
    assert.equal(anomaly.availableTools.includes('camera'), true, anomaly.id);
    assert.ok(['quick', 'investigation', 'identity', 'highRisk'].includes(anomaly.roundType), anomaly.id);
  }
});

test('Phase 2 ships ten consistent normal shifts and five passenger identities', () => {
  assert.equal(normalShifts.length, 10);
  assert.equal(passengers.length, 5);
  for (const shift of normalShifts) assert.deepEqual(shift.screenData, shift.panelData, shift.id);
  for (const passenger of passengers) {
    assert.ok(passenger.id && passenger.name && passenger.role);
    assert.ok(Array.isArray(passenger.allowedFloors) && passenger.allowedFloors.length > 0);
  }
});

test('all Phase 2 content references resolve to existing records', () => {
  const anomalyIds = new Set(anomalies.map(item => item.id));
  const normalIds = new Set(normalShifts.map(item => item.id));
  const passengerIds = new Set(passengers.map(item => item.id));

  for (const anomaly of anomalies) {
    for (const normalId of anomaly.normalVariants) assert.ok(normalIds.has(normalId), `${anomaly.id} -> ${normalId}`);
  }
  for (const shift of normalShifts) {
    for (const passengerId of shift.passengerIds) assert.ok(passengerIds.has(passengerId), `${shift.id} -> ${passengerId}`);
  }
  for (const chain of eventChains) {
    for (const step of chain.steps) {
      assert.ok(anomalyIds.has(step.contentId) || normalIds.has(step.contentId), `${chain.id} -> ${step.contentId}`);
    }
  }
});

test('Phase 2 ships three named three-step event chains', () => {
  assert.deepEqual(eventChains.map(item => item.id), [
    'duplicate_passenger',
    'nonexistent_floor',
    'camera_replacement',
  ]);
  for (const chain of eventChains) assert.equal(chain.steps.length, 3, chain.id);
});
