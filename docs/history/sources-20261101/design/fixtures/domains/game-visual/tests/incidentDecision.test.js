import assert from 'node:assert/strict';
import test from 'node:test';

import { createInitialState } from '../src/state.js';
import { expireInspection, openInspection, submitInspection } from '../src/incidentDecision.js';

test('normal baseline must be explicitly classified and rewards a correct decision', () => {
  const opened = openInspection(createInitialState(), {
    id: 'baseline-0',
    kind: 'normal',
    title: '当前监控未见异常',
    duration: 6,
  });
  assert.equal(opened.inspection.status, 'pending');
  assert.equal(opened.inspection.expiresAt, 6);

  const result = submitInspection(opened, 'normal');
  assert.equal(result.accepted, true);
  assert.equal(result.correct, true);
  assert.equal(result.state.inspection.status, 'resolved');
  assert.equal(result.state.decisionsCorrect, 1);
  assert.equal(result.state.decisionsWrong, 0);
  assert.equal(result.state.tutorialStep, 1);
  assert.equal(result.state.score, 160);
  assert.equal(result.state.streak, 1);
});

test('guided first two decisions keep coaching repeated wrong taps without punishment', () => {
  const normal = openInspection(createInitialState(), {
    id: 'baseline-0', kind: 'normal', title: '核对画面与数据', duration: 6,
  });
  const wrongNormal = submitInspection(normal, 'anomaly');
  assert.equal(wrongNormal.accepted, false);
  assert.equal(wrongNormal.state.inspection.status, 'pending');
  assert.equal(wrongNormal.state.stability, 100);
  const wrongNormalAgain = submitInspection(wrongNormal.state, 'anomaly');
  assert.equal(wrongNormalAgain.accepted, false);
  assert.equal(wrongNormalAgain.state.stability, 100);
  assert.equal(wrongNormalAgain.state.decisionsWrong, 0);

  const anomalyState = { ...createInitialState(), tutorialStep: 1, activeAnomaly: 'phantom_floor' };
  const anomaly = openInspection(anomalyState, {
    id: 'phantom_floor', kind: 'anomaly', title: '核对画面与数据', duration: 6,
  });
  const wrongAnomaly = submitInspection(anomaly, 'normal');
  assert.equal(wrongAnomaly.accepted, false);
  assert.equal(wrongAnomaly.state.inspection.status, 'pending');
  assert.equal(wrongAnomaly.state.stability, 100);
  const wrongAnomalyAgain = submitInspection(wrongAnomaly.state, 'normal');
  assert.equal(wrongAnomalyAgain.accepted, false);
  assert.equal(wrongAnomalyAgain.state.stability, 100);
  assert.equal(wrongAnomalyAgain.state.decisionsWrong, 0);
});

test('guided timeouts preserve resources and advance the fixed tutorial sequence', () => {
  const first = openInspection(createInitialState(), {
    id: 'baseline', kind: 'normal', title: '核对画面与数据', duration: 3,
  });
  const firstExpired = expireInspection({ ...first, elapsed: 3 });
  assert.equal(firstExpired.coached, true);
  assert.equal(firstExpired.state.tutorialStep, 1);
  assert.equal(firstExpired.state.stability, 100);
  assert.equal(firstExpired.state.decisionsWrong, 0);

  const anomalyBase = {
    ...createInitialState(), tutorialStep: 1, activeAnomaly: 'floor_jump', stability: 88,
  };
  const second = openInspection(anomalyBase, {
    id: 'floor_jump', kind: 'anomaly', title: '核对画面与数据', duration: 3,
  });
  const secondExpired = expireInspection({ ...second, elapsed: 3 });
  assert.equal(secondExpired.coached, true);
  assert.equal(secondExpired.state.tutorialStep, 2);
  assert.equal(secondExpired.state.stability, 88);
  assert.equal(secondExpired.state.activeAnomaly, 'floor_jump');
});

test('third inspection is independent and closes onboarding after any accepted judgment', () => {
  const base = { ...createInitialState(), tutorialStep: 3 };
  const pending = openInspection(base, {
    id: 'independent-third',
    kind: 'normal',
    title: '核对画面与数据',
    duration: 5,
  });
  const result = submitInspection(pending, 'normal');
  assert.equal(result.accepted, true);
  assert.equal(result.state.tutorialStep, 4);
});

test('misclassifying an anomaly applies a real gameplay penalty', () => {
  const initial = { ...createInitialState(), elapsed: 12, stability: 80, anomalyLevel: 2, tutorialStep: 2 };
  const opened = openInspection(initial, {
    id: 'phantom_floor',
    kind: 'anomaly',
    title: '楼层显示与建筑图纸不一致',
    duration: 7,
  });
  const result = submitInspection(opened, 'normal');
  assert.equal(result.accepted, true);
  assert.equal(result.correct, false);
  assert.equal(result.state.stability, 68);
  assert.equal(result.state.anomalyLevel, 3);
  assert.equal(result.state.decisionsWrong, 1);
});

test('correctly reporting an anomaly reduces pressure but keeps its operational consequence', () => {
  const initial = { ...createInitialState(), anomalyLevel: 3, activeAnomaly: 'phantom_floor', tutorialStep: 1 };
  const opened = openInspection(initial, {
    id: 'phantom_floor',
    kind: 'anomaly',
    title: '不存在的楼层',
    duration: 7,
  });
  const result = submitInspection(opened, 'anomaly');
  assert.equal(result.correct, true);
  assert.equal(result.state.anomalyLevel, 2);
  assert.equal(result.state.activeAnomaly, 'phantom_floor');
});

test('inspection timeout cannot overwrite an already successful settlement', () => {
  const state = openInspection(createInitialState(), {
    id: 'last-second', kind: 'normal', title: '最终巡检', duration: 3,
  });
  const settled = { ...state, elapsed: 60, remaining: 0, gameOver: true, result: 'success', stability: 5 };
  const expired = expireInspection(settled);
  assert.equal(expired.timedOut, false);
  assert.equal(expired.state.result, 'success');
  assert.equal(expired.state.stability, 5);
});

test('inspection timeout penalizes exactly once', () => {
  const opened = openInspection({ ...createInitialState(), elapsed: 5, tutorialStep: 4 }, {
    id: 'baseline-5',
    kind: 'normal',
    title: '常规巡检',
    duration: 4,
  });
  const expired = expireInspection({ ...opened, elapsed: 9 });
  assert.equal(expired.timedOut, true);
  assert.equal(expired.state.inspection.status, 'expired');
  assert.equal(expired.state.stability, 92);
  const again = expireInspection({ ...expired.state, elapsed: 20 });
  assert.equal(again.timedOut, false);
  assert.equal(again.state.stability, 92);
});
