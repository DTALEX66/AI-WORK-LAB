import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { findRollbackSnapshot } from '../src/rollback.js';
import { createInitialState, cloneState, checkFailure, recordFailure, recordSuccessfulShift, revive, saveSnapshot, tickState } from '../src/state.js';
import CONFIG from '../src/gameConfig.js';

test('createInitialState returns the elevator console baseline', () => {
  const state = createInitialState();

  assert.equal(state.floor, 1);
  assert.equal(state.door, 'closed');
  assert.equal(state.moving, false);
  assert.equal(state.direction, 'idle');
  assert.equal(state.power, 100);
  assert.equal(state.stability, 100);
  assert.equal(state.anomalyLevel, 0);
  assert.equal(state.passengers, 0);
  assert.equal(state.gameOver, false);
  assert.equal(state.result, 'playing');
  assert.equal(state.adRevivesUsed, 0);
  assert.ok(Array.isArray(state.logs));
  assert.ok(Array.isArray(state.snapshots), 'snapshots should be initialized as empty array');
  assert.equal(state.snapshots.length, 0);
});

test('elevator skin initial monitor copy matches the zero-passenger baseline', () => {
  const skin = JSON.parse(readFileSync(new URL('../src/skins/elevator/skin.json', import.meta.url), 'utf8'));
  assert.equal(CONFIG.initial.passengers, 0);
  assert.match(skin.monitor.initial, /为空|0 名乘客/);
  assert.doesNotMatch(skin.monitor.initial, /1 名乘客/);
});

test('cloneState creates a deep copy suitable for rollback snapshots', () => {
  const state = createInitialState();
  const copy = cloneState(state);
  copy.logs.push({ type: 'test', text: 'mutated' });

  assert.equal(state.logs.length, 1);
  assert.notEqual(copy.logs, state.logs);
});

test('initial state includes an isolated V5 night and investigation baseline', () => {
  const first = createInitialState();
  const second = createInitialState();

  assert.deepEqual(first.night, {
    activeProtocols: [],
    currentShift: null,
    roundType: 'quick',
    shiftIndex: 0,
    decisions: [],
    eventChains: {},
    eventChainFlags: [],
    eventChainHistory: [],
    timelineSequence: 0,
    nextShiftModifiers: [],
  });
  assert.equal(first.investigation.power, first.power);
  assert.equal(first.investigation.activeCamera, 'cam01');
  assert.deepEqual(first.investigation.discoveredEvidence, []);
  assert.equal(first.investigation.tools.thermal.remaining, 2);
  assert.equal(first.investigation.tools.replay.remaining, 2);
  assert.equal(first.investigation.tools.protocol.powerCost, 0);

  first.night.activeProtocols.push({ id: 'protocol-mutated' });
  first.investigation.tools.thermal.remaining = 0;
  assert.deepEqual(second.night.activeProtocols, []);
  assert.equal(second.investigation.tools.thermal.remaining, 2);
});

test('ad revive rolls back V5 night and investigation state as deep copies', () => {
  const prepared = createInitialState();
  prepared.elapsed = 20;
  prepared.night.activeProtocols = [{ id: 'protocol-floor-13' }];
  prepared.night.currentShift = { id: 'shift-07', evidence: { cameras: { cam01: [] } } };
  prepared.night.roundType = 'investigation';
  prepared.investigation.activeCamera = 'cam07';
  prepared.investigation.tools.thermal.remaining = 1;
  prepared.investigation.discoveredEvidence.push({ id: 'evidence-before-failure' });

  const snapshotted = saveSnapshot(prepared);
  const failed = {
    ...snapshotted,
    elapsed: 49,
    gameOver: true,
    result: 'failure',
    anomalyLevel: CONFIG.failure.anomalyLevelMax,
  };
  failed.night.currentShift.evidence.cameras.cam01.push({ id: 'late-evidence' });
  failed.investigation.discoveredEvidence.push({ id: 'late-discovery' });

  const revived = revive(failed);

  assert.equal(revived.night.roundType, 'investigation');
  assert.equal(revived.night.currentShift.id, 'shift-07');
  assert.deepEqual(revived.night.currentShift.evidence.cameras.cam01, []);
  assert.equal(revived.investigation.activeCamera, 'cam07');
  assert.equal(revived.investigation.tools.thermal.remaining, 1);
  assert.deepEqual(revived.investigation.discoveredEvidence, [{ id: 'evidence-before-failure' }]);

  revived.night.activeProtocols[0].id = 'mutated-after-revive';
  revived.investigation.discoveredEvidence[0].id = 'mutated-after-revive';
  assert.equal(failed.snapshots[0].state.night.activeProtocols[0].id, 'protocol-floor-13');
  assert.equal(failed.snapshots[0].state.investigation.discoveredEvidence[0].id, 'evidence-before-failure');
});

test('saveSnapshot appends a deep copy without nesting snapshots inside the saved state', () => {
  const state = { ...createInitialState(), floor: 5, power: 80, elapsed: 30, snapshots: [] };
  const next = saveSnapshot(state);

  assert.equal(next.snapshots.length, 1);
  assert.equal(next.snapshots[0].at, 30);
  assert.equal(next.snapshots[0].state.floor, 5);
  assert.equal(next.snapshots[0].state.power, 80);
  assert.equal(next.snapshots[0].state.elapsed, 30);
  // The saved state must NOT include its own snapshots array
  assert.ok(!('snapshots' in next.snapshots[0].state), 'saved snapshot state should not nest snapshots');
});

test('saveSnapshot keeps existing snapshots', () => {
  const first = saveSnapshot({ ...createInitialState(), elapsed: 10, snapshots: [] });
  const second = saveSnapshot({ ...first, floor: 3, elapsed: 20 });

  assert.equal(second.snapshots.length, 2);
  assert.equal(second.snapshots[0].at, 10);
  assert.equal(second.snapshots[1].at, 20);
});

test('saveSnapshot trims history to configured maxSnapshots', () => {
  let state = { ...createInitialState(), snapshots: [] };
  for (let i = 1; i <= CONFIG.revive.maxSnapshots + 2; i += 1) {
    state = saveSnapshot({ ...state, elapsed: i * CONFIG.revive.snapshotInterval });
  }

  assert.equal(state.snapshots.length, CONFIG.revive.maxSnapshots);
  assert.equal(state.snapshots[0].at, 3 * CONFIG.revive.snapshotInterval);
  assert.equal(state.snapshots.at(-1).at, (CONFIG.revive.maxSnapshots + 2) * CONFIG.revive.snapshotInterval);
});

test('findRollbackSnapshot selects the snapshot closest to rollback window target', () => {
  const elapsed = 58;
  const target = elapsed - CONFIG.revive.rollbackWindow;
  const snapshots = [
    { at: target - 10, state: { floor: 1 } },
    { at: target, state: { floor: 2 } },
    { at: target + 10, state: { floor: 3 } },
  ];

  const found = findRollbackSnapshot(snapshots, elapsed);

  assert.equal(found.at, target);
  assert.equal(found.state.floor, 2);
});

test('revive restores from the closest snapshot within 30 seconds of rollback', () => {
  const snap1 = { at: 10, state: { floor: 2, door: 'closed', moving: false, direction: 'idle', power: 90, stability: 95, anomalyLevel: 1, passengers: 1, elapsed: 10, remaining: 50, adRevivesUsed: 0, monitor: 'snap at 10', logs: [] } };
  const snap2 = { at: 30, state: { floor: 4, door: 'closed', moving: false, direction: 'idle', power: 60, stability: 70, anomalyLevel: 3, passengers: 1, elapsed: 30, remaining: 30, adRevivesUsed: 0, monitor: 'snap at 30', logs: [] } };
  const snap3 = { at: 40, state: { floor: 6, door: 'open', moving: true, direction: 'up', power: 40, stability: 50, anomalyLevel: 4, passengers: 2, elapsed: 40, remaining: 20, adRevivesUsed: 0, monitor: 'snap at 40', logs: [] } };

  const failed = {
    ...createInitialState(),
    gameOver: true, power: 5, stability: 10, anomalyLevel: 6, elapsed: 58,
    snapshots: [snap1, snap2, snap3],
  };

  const revived = revive(failed);

  // Should roll back to snap at 30 (closest to elapsed - 30 = 28)
  assert.equal(revived.floor, 4, 'floor should be from snap at 30');
  assert.equal(revived.power, 60);
  assert.equal(revived.stability, 70);
  assert.equal(revived.anomalyLevel, 3);
  assert.equal(revived.elapsed, 30);
  assert.equal(revived.gameOver, false);
  assert.equal(revived.door, 'closed');
  assert.equal(revived.adRevivesUsed, 1);
  assert.match(revived.monitor, /回滚/);
  assert.match(revived.logs.at(-1).text, /复活/);
});

test('revive falls back to initial state when snapshots array is empty', () => {
  const failed = {
    ...createInitialState(),
    gameOver: true, power: 0, stability: 0, anomalyLevel: 6, elapsed: 55,
    snapshots: [],
  };

  const revived = revive(failed);

  assert.equal(revived.gameOver, false);
  assert.equal(revived.door, 'closed');
  assert.equal(revived.adRevivesUsed, 1);
  // No snapshots → fall back to initial baseline
  assert.equal(revived.floor, 1);
  assert.equal(revived.power, 100);
});

test('revive preserves snapshot history after restore', () => {
  const snap = { at: 20, state: { floor: 3, door: 'closed', moving: false, direction: 'idle', power: 75, stability: 85, anomalyLevel: 2, passengers: 1, elapsed: 20, remaining: 40, adRevivesUsed: 0, monitor: 'ok', logs: [] } };

  const failed = {
    ...createInitialState(),
    gameOver: true, anomalyLevel: 6, elapsed: 48,
    snapshots: [snap],
  };

  const revived = revive(failed);
  assert.equal(revived.snapshots.length, 1, 'snapshot history should be preserved');
  assert.equal(revived.snapshots[0].at, 20);
});

test('initial state includes mobile score, streak and progressive tutorial fields', () => {
  const state = createInitialState();
  assert.equal(state.score, 0);
  assert.equal(state.streak, 0);
  assert.equal(state.bestStreak, 0);
  assert.equal(state.tutorialStep, 0);
});

test('initial state includes post-run summary tracking fields', () => {
  const s = createInitialState();
  assert.equal(s.anomaliesTriggeredTotal, 0, 'should start with zero triggered anomalies');
  assert.equal(s.maxAnomalySeverity, 0, 'should start with zero max severity');
});

test('successful countdown produces a success result rather than a failure overlay state', () => {
  const completed = tickState({
    ...createInitialState(),
    remaining: 1,
    activeAnomaly: 'floor_jump',
    inspection: { id: 'floor_jump', kind: 'anomaly', status: 'pending' },
  }, 1);

  assert.equal(completed.gameOver, true);
  assert.equal(completed.result, 'success');
  assert.equal(completed.activeAnomaly, null);
  assert.equal(completed.inspection, null);
  assert.match(completed.lastFeedback, /本轮结束/);
  assert.match(completed.logs.at(-1).text, /本轮结束|值守/);
});

test('countdown completion wins when a resource threshold is crossed in the same tick', () => {
  const completed = tickState({
    ...createInitialState(),
    remaining: 1,
    power: 0.1,
  }, 1);

  assert.equal(completed.gameOver, true);
  assert.equal(completed.result, 'success');
  assert.match(completed.logs.at(-1).text, /本轮结束|值守/);
  assert.doesNotMatch(completed.logs.at(-1).text, /崩溃/);
});

test('resource exhaustion produces an explicit failure result', () => {
  const failed = checkFailure({ ...createInitialState(), power: 0 });

  assert.equal(failed.gameOver, true);
  assert.equal(failed.result, 'failure');
});

test('revive restores the active playing result', () => {
  const revived = revive({
    ...createInitialState(),
    gameOver: true,
    result: 'failure',
    anomalyLevel: CONFIG.failure.anomalyLevelMax,
  });

  assert.equal(revived.gameOver, false);
  assert.equal(revived.result, 'playing');
});

test('recordFailure triggers fake ending at threshold and starts cooldown', () => {
  let state = createInitialState();
  for (let i = 0; i < CONFIG.fakeEnding.consecutiveFailuresThreshold; i += 1) {
    state = recordFailure(state);
  }

  assert.equal(state.fakeEndingTriggered, true);
  assert.equal(state.fakeEndingUnlocked, false);
  assert.equal(state.fakeEndingCount, CONFIG.fakeEnding.consecutiveFailuresThreshold);
  assert.equal(state.consecutiveFailures, 0);
  assert.equal(state.fakeEndingCooldownRemaining, CONFIG.fakeEnding.cooldownFailures);
});

test('recordFailure respects fake ending cooldown', () => {
  const state = recordFailure({
    ...createInitialState(),
    consecutiveFailures: CONFIG.fakeEnding.consecutiveFailuresThreshold - 1,
    fakeEndingCooldownRemaining: 1,
  });

  assert.equal(state.fakeEndingTriggered, false);
  assert.equal(state.fakeEndingCooldownRemaining, 0);
});

test('recordSuccessfulShift resets fake ending counters', () => {
  const state = recordSuccessfulShift({
    ...createInitialState(),
    consecutiveFailures: 3,
    fakeEndingCount: 5,
    fakeEndingCooldownRemaining: 2,
    fakeEndingTriggered: true,
    fakeEndingUnlocked: true,
  });

  assert.equal(state.consecutiveFailures, 0);
  assert.equal(state.fakeEndingCount, 0);
  assert.equal(state.fakeEndingCooldownRemaining, 0);
  assert.equal(state.fakeEndingTriggered, false);
  assert.equal(state.fakeEndingUnlocked, false);
  assert.match(state.logs.at(-1).text, /值守完成/);
});
