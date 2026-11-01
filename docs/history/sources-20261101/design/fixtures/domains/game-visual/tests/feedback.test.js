import test from 'node:test';
import assert from 'node:assert/strict';

import { createInitialState } from '../src/state.js';
import { classifyFeedbackPriority, createFeedbackLine, getToneForState, summarizeFailure } from '../src/feedback.js';
import CONFIG from '../src/gameConfig.js';

test('createFeedbackLine formats timestamped console feedback', () => {
  const line = createFeedbackLine('warn', '门外检测到人影', 42);

  assert.deepEqual(line, {
    type: 'warn',
    priority: 'medium',
    time: 42,
    text: '[00:42] 门外检测到人影',
  });
});

test('classifyFeedbackPriority separates important log rows for UI highlighting', () => {
  assert.equal(classifyFeedbackPriority('danger'), 'high');
  assert.equal(classifyFeedbackPriority('ad'), 'normal');  // ad 已中性化（DL-MIG 边界）
  assert.equal(classifyFeedbackPriority('success'), 'success');
  assert.equal(classifyFeedbackPriority('warn'), 'medium');
  assert.equal(classifyFeedbackPriority('info'), 'normal');
});

test('successful result uses a calm tone instead of failure danger', () => {
  assert.equal(getToneForState({ ...createInitialState(), gameOver: true, result: 'success' }), 'normal');
});

test('summarizeFailure explains why the run ended', () => {
  const state = { ...createInitialState(), power: 0, stability: 12, anomalyLevel: 4 };
  const summary = summarizeFailure(state);

  assert.match(summary, /电源耗尽/);
  assert.match(summary, /复活/);
});

test('summarizeFailure uses configured rollback window for snapshot hint', () => {
  const elapsed = 58;
  const target = elapsed - CONFIG.revive.rollbackWindow;
  const state = {
    ...createInitialState(),
    elapsed,
    power: 0,
    snapshots: [
      { at: target - 10, state: {} },
      { at: target, state: {} },
      { at: target + 10, state: {} },
    ],
  };

  const summary = summarizeFailure(state);

  assert.match(summary, new RegExp(`回滚到 ${CONFIG.revive.rollbackWindow} 秒前`));
});
