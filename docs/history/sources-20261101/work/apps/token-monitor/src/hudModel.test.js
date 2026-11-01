import test from 'node:test';
import assert from 'node:assert/strict';
import {
  activityLabel,
  activityRate,
  buildHudModel,
  displayCompact,
  displayCount,
  displayFull,
  knownMetric,
  knownTotal,
  percentLabel,
  providerShares,
  ringGeometry,
  sparkSeries,
  splitAggregate,
  splitProvider,
  statusOf,
  timestampMs,
  topModels,
} from './hudModel.js';

test('unknown usage stays unknown instead of becoming zero', () => {
  const unknown = { recognized_requests: 0, total_tokens: 0 };
  assert.equal(knownTotal(unknown), null);
  assert.equal(knownMetric(unknown, 'input_tokens'), null);
  assert.equal(displayCompact(0, 0), '—');
  assert.equal(displayFull(0, 0), '—');
  assert.equal(displayCount(0, false), '—');
});

test('known zero survives formatting', () => {
  assert.equal(displayCompact(0, 3), '0');
  assert.equal(displayFull(0, 3), '0');
  assert.equal(displayCount(0, true), '0');
  assert.equal(knownMetric({ recognized_requests: 2, input_tokens: 0 }, 'input_tokens'), 0);
  assert.equal(knownTotal({ recognized_requests: 2, total_tokens: 0, providers: [] }), 0);
});

test('knownTotal falls back to provider sums only when the snapshot is silent', () => {
  assert.equal(knownTotal(null), null);
  assert.equal(knownTotal({ recognized_requests: 0, total_tokens: 0, providers: [{ total_tokens: 70 }, { total_tokens: 30 }] }), 100);
  assert.equal(knownTotal({ recognized_requests: 4, total_tokens: 500, providers: [{ total_tokens: 9 }] }), 500);
});

test('provider shares are token shares and never a quota', () => {
  const shares = providerShares([
    { provider: 'A', total_tokens: 3 },
    { provider: 'B', total_tokens: 1 },
  ]);
  assert.equal(shares[0].share, 0.75);
  assert.equal(shares[1].share, 0.25);
  assert.equal(providerShares([{ provider: 'A', total_tokens: 0 }])[0].share, null);
  assert.equal(percentLabel(0), '0%');
  assert.equal(percentLabel(0.004), '<1%');
  assert.equal(percentLabel(0.5), '50%');
  assert.equal(percentLabel(1), '100%');
  assert.equal(percentLabel(null), '—');
});

test('ring geometry tracks the share and reports unknown', () => {
  const circumference = 2 * Math.PI * 42;
  const half = ringGeometry(0.5);
  assert.equal(half.known, true);
  assert.equal(Number.parseFloat(half.dasharray), circumference * 0.5);
  const unknown = ringGeometry(null);
  assert.equal(unknown.known, false);
  assert.equal(Number.parseFloat(unknown.dasharray), 0);
  assert.equal(ringGeometry(2).dasharray, `${circumference} ${circumference}`);
});

test('aggregate segments split cached and reasoning without double counting', () => {
  const segments = splitAggregate({
    input_tokens: 100,
    output_tokens: 50,
    cached_input_tokens: 80,
    reasoning_tokens: 20,
    total_tokens: 170,
  });
  const byKey = Object.fromEntries(segments.map((item) => [item.key, item.value]));
  assert.equal(byKey.input, 20);
  assert.equal(byKey.cache, 80);
  assert.equal(byKey.output, 30);
  assert.equal(byKey.reasoning, 20);
  assert.equal(byKey.other, 20);
  assert.equal(segments.reduce((sum, item) => sum + item.value, 0), 170);

  const clamped = splitAggregate({ input_tokens: 10, output_tokens: 5, cached_input_tokens: 50, reasoning_tokens: 50, total_tokens: 15 });
  assert.equal(clamped.find((item) => item.key === 'cache').value, 10);
  assert.equal(clamped.find((item) => item.key === 'reasoning').value, 5);
  assert.ok(clamped.every((item) => item.value >= 0));
});

test('provider segments carry an explicit unclassified remainder', () => {
  const segments = splitProvider({ input_tokens: 30, output_tokens: 20, total_tokens: 100 });
  const byKey = Object.fromEntries(segments.map((item) => [item.key, item.value]));
  assert.equal(byKey.input, 30);
  assert.equal(byKey.output, 20);
  assert.equal(byKey.other, 50);
  assert.equal(Math.round(segments.reduce((sum, item) => sum + item.pct, 0)), 100);
});

test('status vocabulary distinguishes scanning, error, pause, empty, live and unknown', () => {
  assert.equal(statusOf({ loading: true }, null).key, 'scanning');
  assert.equal(statusOf({ error: 'boom', started: true }, { recognized_requests: 1 }).key, 'error');
  const paused = statusOf({ started: false, pauseReason: '数据源已轮转' }, null);
  assert.equal(paused.key, 'paused');
  assert.equal(paused.detail, '数据源已轮转');
  assert.equal(statusOf({ started: true }, { recognized_requests: 0 }).key, 'empty');
  assert.equal(statusOf({ started: true, baseline: { recognized_requests: 100 } }, { recognized_requests: 0 }).key, 'waiting');
  assert.equal(statusOf({ started: true, mode: 'history', baseline: { recognized_requests: 100 } }, { recognized_requests: 0 }).key, 'empty');
  assert.equal(statusOf({ started: true }, { recognized_requests: 2, confidence: 'exact' }).key, 'live');
  assert.equal(statusOf({ started: true }, { recognized_requests: 2, confidence: 'partial' }).key, 'unknown');
});

test('activity rate needs two known totals and never reports a negative rate', () => {
  assert.equal(activityRate(100, 220, 60000), 120);
  assert.equal(activityRate(100, 90, 60000), null);
  assert.equal(activityRate(null, 90, 60000), null);
  assert.equal(activityRate(100, 220, 0), null);
  assert.equal(activityLabel(null, {}, null, Date.now(), 220), '— / min');
  assert.equal(activityLabel({ recognized_requests: 1, total_tokens: 100 }, {}, 1000, 61000, 220), '120 / min');
});

test('timestamps accept seconds and milliseconds', () => {
  assert.equal(timestampMs(1700000000), 1700000000000);
  assert.equal(timestampMs(1700000000000), 1700000000000);
  assert.equal(timestampMs(0), null);
  assert.equal(timestampMs('1700000000'), null);
});

test('spark and model ranking keep bounded, ordered series', () => {
  const spark = sparkSeries([
    { day: 'a', total_tokens: 0 },
    { day: 'b', total_tokens: 100 },
    { day: 'c', total_tokens: 50 },
  ]);
  assert.equal(spark.length, 3);
  assert.equal(spark[0].height, 4);
  assert.equal(spark[1].height, 100);
  assert.equal(spark[2].height, 50);

  const models = topModels([
    { provider: 'A', model: 'small', total_tokens: 10 },
    { provider: 'A', model: 'large', total_tokens: 90 },
    { provider: 'B', model: 'other', total_tokens: 200 },
  ], 'A', 2);
  assert.deepEqual(models.map((item) => item.model), ['large', 'small']);
});

test('HUD model preserves honest labels, selection and demo provenance', () => {
  const snapshot = {
    source: 'demo source',
    scanned_files: 0,
    unknown_records: 0,
    recognized_requests: 4,
    total_tokens: 400,
    input_tokens: 300,
    output_tokens: 100,
    cached_input_tokens: 0,
    reasoning_tokens: 0,
    providers: [
      { provider: 'GPT / Codex', total_tokens: 300, input_tokens: 200, output_tokens: 100, requests: 3 },
      { provider: 'Kimi', total_tokens: 100, input_tokens: 100, output_tokens: 0, requests: 1 },
    ],
    models: [
      { provider: 'GPT / Codex', model: 'gpt-a', total_tokens: 100 },
      { provider: 'GPT / Codex', model: 'gpt-b', total_tokens: 200 },
      { provider: 'Kimi', model: 'kimi-a', total_tokens: 100 },
    ],
    days: [{ day: '2026-10-18', total_tokens: 400 }],
    updated_at: 1700000000,
    confidence: 'exact',
  };
  const model = buildHudModel({ snapshot, state: { demo: true, started: true }, selectedProvider: 'Kimi' });
  assert.equal(model.demo, true);
  assert.equal(model.empty, false);
  assert.equal(model.totalLabel, '400');
  assert.equal(model.scannedFilesLabel, '0');
  assert.equal(model.unknownLabel, '0');
  assert.equal(model.selectedProvider, 'Kimi');
  assert.equal(model.selected.provider, 'Kimi');
  assert.deepEqual(model.models.map((item) => item.model), ['kimi-a']);
  assert.equal(model.providers[0].shareLabel, '75%');
  assert.equal(model.providers[1].shareLabel, '25%');
  assert.equal(model.status.key, 'live');

  const unknownSelection = buildHudModel({ snapshot, state: { started: true }, selectedProvider: 'missing' });
  assert.equal(unknownSelection.selectedProvider, 'GPT / Codex');

  const empty = buildHudModel({ snapshot: null, state: { started: false } });
  assert.equal(empty.empty, true);
  assert.equal(empty.totalLabel, '—');
  assert.equal(empty.selected, null);
  assert.equal(empty.status.key, 'paused');
  assert.equal(empty.source, '尚未连接数据源');

  const pausedWithSource = buildHudModel({
    snapshot: null,
    state: { started: false, sourceText: 'C:\\Users\\ALEX\\.codex\\sessions' },
  });
  assert.equal(pausedWithSource.source, 'C:\\Users\\ALEX\\.codex\\sessions');
});
