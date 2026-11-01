import test from 'node:test';
import assert from 'node:assert/strict';

import CONFIG from '../src/gameConfig.js';
import {
  createRuntimeSession,
  restartRuntimeSession,
  scheduleNextAnomalyAfterRevive,
  scheduleNextAnomalyAfterTrigger,
} from '../src/runtimeSession.js';

test('runtime session uses configured first anomaly time on start and restart', () => {
  const session = createRuntimeSession();
  assert.equal(session.nextAnomalyAt, CONFIG.anomaly.firstTriggerAt);

  const restarted = restartRuntimeSession({ ...session, nextAnomalyAt: 999 });
  assert.equal(restarted.nextAnomalyAt, CONFIG.anomaly.firstTriggerAt);
  assert.equal(restarted.state.elapsed, 0);
});

test('restart preserves cross-run fake-ending progression while clearing run state', () => {
  const restarted = restartRuntimeSession({
    ...createRuntimeSession(),
    state: {
      ...createRuntimeSession().state,
      consecutiveFailures: 4,
      fakeEndingCooldownRemaining: 2,
      fakeEndingTriggered: true,
      fakeEndingUnlocked: true,
      elapsed: 45,
      gameOver: true,
      result: 'failure',
    },
  });

  assert.equal(restarted.state.consecutiveFailures, 4);
  assert.equal(restarted.state.fakeEndingCooldownRemaining, 2);
  assert.equal(restarted.state.fakeEndingTriggered, false);
  assert.equal(restarted.state.fakeEndingUnlocked, false);
  assert.equal(restarted.state.elapsed, 0);
  assert.equal(restarted.state.gameOver, false);
  assert.equal(restarted.state.result, 'playing');
});

test('anomaly scheduling uses configured cooldown windows', () => {
  const elapsed = 20;

  assert.equal(
    scheduleNextAnomalyAfterTrigger(elapsed, () => 0),
    elapsed + CONFIG.anomaly.cooldownMin,
  );
  assert.equal(
    scheduleNextAnomalyAfterTrigger(elapsed, () => 0.999),
    elapsed + CONFIG.anomaly.cooldownMax,
  );
  assert.equal(
    scheduleNextAnomalyAfterRevive(elapsed),
    elapsed + CONFIG.anomaly.cooldownMin,
  );
});
