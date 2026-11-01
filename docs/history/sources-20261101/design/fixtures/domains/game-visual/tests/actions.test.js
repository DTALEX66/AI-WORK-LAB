import test from 'node:test';
import assert from 'node:assert/strict';

import { createInitialState } from '../src/state.js';
import { getAvailableActions, performAction } from '../src/actions.js';
import CONFIG from '../src/gameConfig.js';
import { loadSkin } from '../src/skinManager.js';
import elevatorSkin from '../src/skins/elevator/skin.json' with { type: 'json' };
import securitySkin from '../src/skins/security/skin.json' with { type: 'json' };

test('available actions use current skin labels', () => {
  loadSkin(securitySkin);

  const labels = getAvailableActions().map(action => action.label);

  assert.ok(labels.includes('解锁门禁'));
  assert.ok(labels.includes('锁定门禁'));
  assert.ok(!labels.includes('开门'));

  loadSkin(elevatorSkin);
});

test('elevator cannot move while the door is open', () => {
  const open = performAction(createInitialState(), 'openDoor').state;
  const result = performAction(open, 'moveUp');

  assert.equal(result.ok, false);
  assert.equal(result.state.floor, 1);
  assert.match(result.message, /门未关闭/);
});

test('moveUp consumes power, changes floor, and emits feedback log', () => {
  const result = performAction(createInitialState(), 'moveUp');

  assert.equal(result.ok, true);
  assert.equal(result.state.floor, 2);
  assert.equal(result.state.power, CONFIG.initial.power - CONFIG.actions.moveUp.powerCost);
  assert.equal(result.state.direction, 'up');
  assert.match(result.state.logs.at(-1).text, /上行/);
});

test('recommended anomaly treatment clears the active anomaly and restores monitoring', () => {
  const cases = [
    ['door_refuse', 'closeDoor', { door: 'open' }],
    ['phantom_floor', 'inspectLog', {}],
    ['camera_delay', 'inspectLog', {}],
    ['stop_failure', 'restartSystem', {}],
  ];

  for (const [anomalyId, actionId, overrides] of cases) {
    const state = {
      ...createInitialState(),
      ...overrides,
      activeAnomaly: anomalyId,
      anomalyLevel: 3,
    };
    const result = performAction(state, actionId);
    assert.equal(result.ok, true, `${anomalyId} treatment should succeed`);
    assert.equal(result.state.activeAnomaly, null, `${anomalyId} should be cleared`);
    assert.ok(result.state.anomalyLevel < state.anomalyLevel, `${anomalyId} pressure should decrease`);
    assert.match(result.state.logs.at(-1).text, /解除当前异常/);
  }
});

test('wrong contextual treatment keeps anomaly active and applies an immediate readable penalty', () => {
  const state = {
    ...createInitialState(),
    activeAnomaly: 'phantom_floor',
    anomalyLevel: 2,
    stability: 80,
    streak: 3,
  };
  const wrong = performAction(state, 'restartSystem');
  assert.equal(wrong.ok, false);
  assert.equal(wrong.state.activeAnomaly, 'phantom_floor');
  assert.equal(wrong.state.stability, 74);
  assert.equal(wrong.state.anomalyLevel, 3);
  assert.equal(wrong.state.streak, 0);

  const correct = performAction(state, 'inspectLog');
  assert.equal(correct.ok, true);
  assert.equal(correct.state.activeAnomaly, null);
  assert.equal(correct.state.score, 150);
});

test('restartSystem reduces anomaly level and stabilizes the system', () => {
  const state = { ...createInitialState(), anomalyLevel: 4, stability: 45, power: 55 };
  const result = performAction(state, 'restartSystem');

  assert.equal(result.ok, true);
  assert.equal(result.state.anomalyLevel, 2);
  assert.equal(result.state.stability, 45 + CONFIG.actions.restartSystem.stabilityRestore);
  assert.equal(result.state.power, 55 - CONFIG.actions.restartSystem.powerCost);
});

test('emergencyStop failure uses current skin feedback copy', () => {
  const skin = structuredClone(elevatorSkin);
  skin.actionFeedback.emergencyStop_fail = '自定义急停失败反馈。';
  loadSkin(skin);

  const result = performAction({ ...createInitialState(), activeAnomaly: 'stop_failure' }, 'emergencyStop');

  assert.equal(result.ok, false);
  assert.equal(result.message, '自定义急停失败反馈。');

  loadSkin(elevatorSkin);
});

test('unknown action uses current skin failure copy', () => {
  const skin = structuredClone(elevatorSkin);
  skin.actionFailMessages.unknownAction = '未知皮肤操作：{actionId}';
  loadSkin(skin);

  const result = performAction(createInitialState(), 'debugOnlyAction');

  assert.equal(result.ok, false);
  assert.equal(result.message, '未知皮肤操作：debugOnlyAction');

  loadSkin(elevatorSkin);
});

test('unlockHiddenLog fails when no locked logs exist', () => {
  const result = performAction(createInitialState(), 'unlockHiddenLog');
  assert.equal(result.ok, false);
  assert.match(result.message, /没有待解码/);
});

test('unlockHiddenLog unlocks the first locked hidden log', () => {
  const state = {
    ...createInitialState(),
    hiddenLogs: [
      { id: 'log_a', title: 'Log A', content: 'Content A', locked: true },
      { id: 'log_b', title: 'Log B', content: 'Content B', locked: true },
    ],
  };
  const result = performAction(state, 'unlockHiddenLog');
  assert.equal(result.ok, true);
  assert.equal(result.state.hiddenLogs[0].locked, false);
  assert.equal(result.state.hiddenLogs[1].locked, true);
  assert.equal(result.state.adHintsUsed, 1);
});

test('unlockHiddenLog respects the configured per-run unlock limit', () => {
  const state = {
    ...createInitialState(),
    adHintsUsed: CONFIG.hiddenLogs.maxUnlockedPerRun,
    hiddenLogs: [
      { id: 'log_a', title: 'Log A', content: 'Content A', locked: true },
    ],
  };

  const result = performAction(state, 'unlockHiddenLog');

  assert.equal(result.ok, false);
  assert.equal(result.state.hiddenLogs[0].locked, true);
  assert.equal(result.state.adHintsUsed, CONFIG.hiddenLogs.maxUnlockedPerRun);
  assert.match(result.message, new RegExp(String(CONFIG.hiddenLogs.maxUnlockedPerRun)));
});

test('inspectLog reports locked hidden records when available', () => {
  const state = {
    ...createInitialState(),
    hiddenLogs: [
      { id: 'log_a', title: 'Log A', content: 'Content A', locked: true },
      { id: 'log_b', title: 'Log B', content: 'Content B', locked: false },
      { id: 'log_c', title: 'Log C', content: 'Content C', locked: true },
    ],
  };

  const result = performAction(state, 'inspectLog');

  assert.equal(result.ok, true);
  assert.match(result.state.logs.at(-1).text, /2 条待解码加密记录/);
});
