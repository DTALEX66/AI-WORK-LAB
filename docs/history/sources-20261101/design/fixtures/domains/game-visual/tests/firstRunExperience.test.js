import test from 'node:test';
import assert from 'node:assert/strict';

import CONFIG from '../src/gameConfig.js';
import { createInitialState } from '../src/state.js';
import { summarizeFailure } from '../src/feedback.js';
import { getOperatorCue } from '../src/firstRunGuidance.js';

test('first session surfaces an anomaly within the first 10 seconds', () => {
  assert.ok(CONFIG.anomaly.firstTriggerAt <= 10, 'first anomaly should appear quickly enough for a first-session hook');
});

test('operator cue teaches the one-sentence release rule before the first anomaly', () => {
  const state = createInitialState();
  const cue = getOperatorCue(state, CONFIG.anomaly.firstTriggerAt);

  assert.match(cue, /三项一致.*放行/);
  assert.match(cue, /\d+ 秒/);
});

test('operator cue confirms automatic isolation without opening a second control layer', () => {
  const state = {
    ...createInitialState(),
    elapsed: 8,
    activeAnomaly: 'camera_delay',
    anomalyLevel: 1,
    anomaliesTriggeredTotal: 1,
  };

  const cue = getOperatorCue(state, CONFIG.anomaly.firstTriggerAt);

  assert.match(cue, /系统正在自动处置/);
  assert.doesNotMatch(cue, /选择处置|黄色|推荐|日志/);
});

test('first failure summary teaches revive and the next read target', () => {
  const state = {
    ...createInitialState(),
    elapsed: 12,
    power: 0,
    gameOver: true,
    anomaliesTriggeredTotal: 1,
    adRevivesUsed: 0,
  };

  const summary = summarizeFailure(state);

  assert.match(summary, /复活/);
  assert.match(summary, /画面.*楼层.*人数.*门状态/);
  assert.doesNotMatch(summary, /日志|推荐按键|黄色描边/);
});
