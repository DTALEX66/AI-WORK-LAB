import test from 'node:test';
import assert from 'node:assert/strict';

import {
  ANALYTICS_EVENTS,
  ANALYTICS_SCHEMA_VERSION,
  createConsoleAnalyticsSink,
  createAnalyticsSink,
  resetAnalyticsSink,
  setAnalyticsSink,
  trackEvent,
} from '../src/analytics.js';

test('analytics exposes the minigame monetization and gameplay event surface', () => {
  assert.deepEqual(ANALYTICS_EVENTS, Object.freeze([
    'game_start',
    'game_over',
    'revive_ad_start',
    'revive_ad_reward',
    'hidden_log_ad_start',
    'hidden_log_unlock',
    'fake_ending_trigger',
    'action_click',
    'anomaly_trigger',
  ]));
});

test('trackEvent sends normalized payloads to the injected sink', () => {
  const calls = [];
  setAnalyticsSink((event) => calls.push(event));

  try {
    const result = trackEvent('action_click', {
      actionId: 'openDoor',
      skinId: 'subway',
      elapsed: 12,
    }, {
      now: () => 12345,
    });

    assert.deepEqual(result, {
      name: 'action_click',
      ts: 12345,
      skinId: 'subway',
      elapsed: 12,
      actionId: 'openDoor',
      schema_version: ANALYTICS_SCHEMA_VERSION,
    });
    assert.deepEqual(calls, [result]);
  } finally {
    resetAnalyticsSink();
  }
});

test('trackEvent rejects unknown analytics events', () => {
  assert.throws(() => trackEvent('unknown_event'), /Unknown analytics event/);
});

test('console analytics sink logs a stable prefix and event payload', () => {
  const calls = [];
  const sink = createConsoleAnalyticsSink({
    log: (...args) => calls.push(args),
  });

  sink({ name: 'game_start', ts: 1, skinId: 'elevator' });

  assert.deepEqual(calls, [[
    '[analytics]',
    'game_start',
    { name: 'game_start', ts: 1, skinId: 'elevator' },
  ]]);
});

test('analytics separates development console and production transport sinks', () => {
  const developmentCalls = [];
  const productionCalls = [];
  const development = createAnalyticsSink({
    environment: 'development',
    logger: { log: (...args) => developmentCalls.push(args) },
  });
  const production = createAnalyticsSink({
    environment: 'production',
    logger: { log: () => { throw new Error('production must not log'); } },
    transport: (event) => productionCalls.push(event),
  });

  const event = { name: 'game_start', ts: 1, schema_version: ANALYTICS_SCHEMA_VERSION };
  development(event);
  production(event);
  assert.equal(developmentCalls.length, 1);
  assert.deepEqual(productionCalls, [event]);
});

test('analytics rejects sensitive payload keys', () => {
  assert.throws(() => trackEvent('game_start', { token: 'should-not-enter-events' }), /Sensitive/);
});
