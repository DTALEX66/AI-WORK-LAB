/**
 * anomalyArchive.test.js — 异常档案与决策时间线测试
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  resetTimeline,
  getTimeline,
  recordDecision,
  getLastDecision,
  getDecisionStats,
  getArchiveEntry,
  getArchiveIndex,
  createDecisionTelemetry,
  serializeTimelineForTelemetry,
} from '../src/anomalyArchive.js';
import { getAllAnomalyContents } from '../src/anomalyContent.js';

const ALL = getAllAnomalyContents();

test('timeline starts empty and can be reset', () => {
  resetTimeline();
  assert.equal(getTimeline().length, 0);
  assert.equal(getLastDecision(), null);
});

test('recordDecision adds entries to the timeline', () => {
  resetTimeline();
  const entry = recordDecision({
    elapsed: 6,
    kind: 'normal',
    playerChoice: 'release',
    correctChoice: 'release',
    screenSnapshot: { floor: 1, passengers: 0, door: 'closed', direction: 'idle' },
    panelSnapshot: { floor: 1, passengers: 0, door: 'closed', direction: 'idle' },
  });
  assert.ok(entry.correct);
  assert.equal(entry.kind, 'normal');
  assert.equal(getTimeline().length, 1);
});

test('recordDecision marks correct anomaly timelock', () => {
  resetTimeline();
  const entry = recordDecision({
    elapsed: 15,
    kind: 'anomaly',
    anomalyId: 'phantom_floor',
    playerChoice: 'lockdown',
    correctChoice: 'lockdown',
    timedOut: false,
    screenSnapshot: { floor: 13, passengers: 1, door: 'closed', direction: 'idle' },
    panelSnapshot: { floor: 1, passengers: 1, door: 'closed', direction: 'idle' },
  });
  assert.ok(entry.correct);
  assert.equal(entry.anomalyId, 'phantom_floor');
  assert.deepEqual(entry.conflicts, ['floor']);
  assert.ok(entry.explanation.length > 10);
});

test('recordDecision marks wrong decision', () => {
  resetTimeline();
  const entry = recordDecision({
    elapsed: 20,
    kind: 'anomaly',
    anomalyId: 'floor_jump',
    playerChoice: 'release',
    correctChoice: 'lockdown',
    screenSnapshot: { floor: 9, passengers: 1, door: 'closed', direction: 'up' },
    panelSnapshot: { floor: 5, passengers: 1, door: 'closed', direction: 'up' },
  });
  assert.equal(entry.correct, false);
  assert.deepEqual(entry.conflicts, ['floor']);
});

test('recordDecision handles timeouts', () => {
  resetTimeline();
  const entry = recordDecision({
    elapsed: 12,
    kind: 'anomaly',
    anomalyId: 'power_drain',
    playerChoice: null,
    correctChoice: 'lockdown',
    timedOut: true,
  });
  assert.equal(entry.timedOut, true);
  assert.equal(entry.correct, false);
});

test('getLastDecision returns the most recent entry', () => {
  resetTimeline();
  recordDecision({ elapsed: 6, kind: 'normal', playerChoice: 'release', correctChoice: 'release' });
  recordDecision({ elapsed: 15, kind: 'anomaly', anomalyId: 'door_refuse', playerChoice: 'lockdown', correctChoice: 'lockdown' });
  const last = getLastDecision();
  assert.equal(last.kind, 'anomaly');
  assert.equal(last.anomalyId, 'door_refuse');
});

test('getDecisionStats calculates correct/wrong/timeout counts', () => {
  resetTimeline();
  recordDecision({ elapsed: 6, kind: 'normal', playerChoice: 'release', correctChoice: 'release' });
  recordDecision({ elapsed: 15, kind: 'anomaly', anomalyId: 'phantom_floor', playerChoice: 'lockdown', correctChoice: 'lockdown' });
  recordDecision({ elapsed: 22, kind: 'anomaly', anomalyId: 'floor_jump', playerChoice: 'release', correctChoice: 'lockdown' });
  recordDecision({ elapsed: 30, kind: 'anomaly', anomalyId: 'power_drain', playerChoice: null, correctChoice: 'lockdown', timedOut: true });
  const stats = getDecisionStats();
  assert.equal(stats.total, 4);
  assert.equal(stats.correct, 2);
  assert.equal(stats.wrong, 1);
  assert.equal(stats.timeout, 1);
  assert.equal(stats.accuracy, 0.5);
});

test('getArchiveEntry returns structured data for every anomaly', () => {
  for (const a of ALL) {
    const entry = getArchiveEntry(a.id);
    assert.ok(entry, `${a.id}: archive entry should exist`);
    assert.equal(entry.title, a.title);
    assert.equal(entry.severity, a.severity);
    assert.equal(entry.difficulty, a.difficulty);
    assert.ok(entry.primaryConflict.length > 5);
    assert.ok(entry.explanation.length > 20);
    assert.ok(Array.isArray(entry.conflicts));
    assert.ok(entry.screenData);
    assert.ok(entry.panelData);
  }
});

test('getArchiveEntry returns null for unknown IDs', () => {
  assert.equal(getArchiveEntry('nonexistent'), null);
});

test('getArchiveIndex returns all 12 anomalies with core fields', () => {
  const index = getArchiveIndex();
  assert.equal(index.length, 12);
  for (const item of index) {
    assert.ok(item.id);
    assert.ok(item.title);
    assert.ok(item.severity >= 1 && item.severity <= 3);
    assert.ok(item.difficulty >= 1 && item.difficulty <= 3);
    assert.ok(item.primaryConflict.length > 5);
  }
});

test('createDecisionTelemetry returns normalized event object', () => {
  resetTimeline();
  const entry = recordDecision({
    elapsed: 15, kind: 'anomaly', anomalyId: 'negative_floor',
    playerChoice: 'lockdown', correctChoice: 'lockdown',
  });
  const telemetry = createDecisionTelemetry(entry);
  assert.equal(telemetry.event, 'decision');
  assert.equal(telemetry.anomalyId, 'negative_floor');
  assert.equal(telemetry.playerChoice, 'lockdown');
  assert.equal(telemetry.correct, true);
  assert.equal(telemetry.timedOut, false);
});

test('serializeTimelineForTelemetry converts all entries', () => {
  resetTimeline();
  recordDecision({ elapsed: 6, kind: 'normal', playerChoice: 'release', correctChoice: 'release' });
  recordDecision({ elapsed: 15, kind: 'anomaly', anomalyId: 'camera_delay', playerChoice: 'lockdown', correctChoice: 'lockdown' });
  const events = serializeTimelineForTelemetry();
  assert.equal(events.length, 2);
  assert.equal(events[0].event, 'decision');
  assert.equal(events[0].anomalyId, '(normal)');
  assert.equal(events[1].anomalyId, 'camera_delay');
});
