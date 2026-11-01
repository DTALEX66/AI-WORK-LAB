import test from 'node:test';
import assert from 'node:assert/strict';

import {
  commitSessionToArchive,
  getArchiveSkinProgress,
  loadArchive,
} from '../src/archive.js';

function installStorage(initial = null) {
  const store = new Map();
  if (initial) store.set('minigame_archive_v1', JSON.stringify(initial));
  globalThis.localStorage = {
    getItem(key) { return store.has(key) ? store.get(key) : null; },
    setItem(key, value) { store.set(key, String(value)); },
    removeItem(key) { store.delete(key); },
    clear() { store.clear(); },
  };
  return store;
}

test('loadArchive migrates old archives with skin progress defaults', () => {
  installStorage({
    sessionsPlayed: 2,
    encounteredAnomalies: { stop_failure: 1 },
    unlockedLogs: { stop_failure_log: true },
  });

  const archive = loadArchive();

  assert.equal(archive.sessionsPlayed, 2);
  assert.deepEqual(archive.skins, {});
});

test('commitSessionToArchive records global and per-skin collection progress', () => {
  installStorage();

  const archive = commitSessionToArchive({
    skinId: 'subway',
    anomaliesTriggeredTotal: 3,
    maxAnomalySeverity: 4,
    anomalyIds: ['phantom_platform', 'phantom_platform', 'brake_failure'],
    unlockedLogIds: ['phantom_platform_log'],
  });

  assert.equal(archive.sessionsPlayed, 1);
  assert.equal(archive.totalAnomaliesTriggered, 3);
  assert.equal(archive.highestSeverity, 4);
  assert.deepEqual(archive.encounteredAnomalies, {
    phantom_platform: 2,
    brake_failure: 1,
  });
  assert.equal(archive.unlockedLogs.phantom_platform_log, true);

  assert.deepEqual(archive.skins.subway, {
    sessionsPlayed: 1,
    totalAnomaliesTriggered: 3,
    totalLogsUnlocked: 1,
    highestSeverity: 4,
    encounteredAnomalies: {
      phantom_platform: 2,
      brake_failure: 1,
    },
    unlockedLogs: {
      phantom_platform_log: true,
    },
  });
});

test('getArchiveSkinProgress summarizes current-skin collection completion', () => {
  const archive = {
    skins: {
      subway: {
        sessionsPlayed: 2,
        encounteredAnomalies: { phantom_platform: 1, brake_failure: 1 },
        unlockedLogs: { phantom_platform_log: true },
        totalAnomaliesTriggered: 2,
        totalLogsUnlocked: 1,
        highestSeverity: 3,
      },
    },
  };
  const catalog = [
    { id: 'phantom_platform' },
    { id: 'brake_failure' },
    { id: 'station_jump' },
  ];

  assert.deepEqual(getArchiveSkinProgress(archive, 'subway', catalog), {
    skinId: 'subway',
    sessionsPlayed: 2,
    encounteredCount: 2,
    unlockedLogsCount: 1,
    totalAnomalies: 3,
    completionRate: 2 / 3,
    logCompletionRate: 1 / 3,
    highestSeverity: 3,
    totalAnomaliesTriggered: 2,
  });
});
