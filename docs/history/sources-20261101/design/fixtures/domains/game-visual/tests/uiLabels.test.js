import test from 'node:test';
import assert from 'node:assert/strict';

import { loadSkin } from '../src/skinManager.js';
import securitySkin from '../src/skins/security/skin.json' with { type: 'json' };
import elevatorSkin from '../src/skins/elevator/skin.json' with { type: 'json' };
import { getDecodedMonitorText, getDirectionLabel, getDomLabels, getDoorLabel } from '../src/uiLabels.js';

test('DOM labels use current skin labels', () => {
  loadSkin(securitySkin);
  const labels = getDomLabels();

  assert.equal(labels.statusPanel, '安防状态');
  assert.equal(labels.status.floor, '区域');
  assert.equal(labels.status.door, '门禁');
  assert.equal(labels.status.passengers, '人员');
  assert.equal(labels.monitorPanel, '安防监控');
  assert.equal(labels.actionPanel, '安防操作');
  assert.equal(labels.logPanel, '安防日志');
  assert.equal(labels.forceAnomaly, '触发安防异常');
  assert.equal(labels.failureTitle, '安防系统崩溃');
  assert.equal(labels.monitorSignal.stable, 'SIGNAL: SECURE');
  assert.equal(labels.monitorSignal.unstable, 'SIGNAL: BREACHED');
  assert.equal(labels.monitorThreat(3), 'THREAT: 3');
  assert.deepEqual(labels.failureMetrics.map(item => item.label), ['电力', '安保', '威胁', '剩余']);
  assert.equal(labels.start.failureRulesTitle, '失守条件');
  assert.equal(labels.start.title, '等待接管安防系统');
  assert.equal(labels.start.button, '接管安防值守');
  assert.deepEqual(labels.start.failureRules, ['电力归零', '安保等级归零', '威胁等级失控']);

  loadSkin(elevatorSkin);
});

test('decoded monitor text uses current skin decode prefix', () => {
  const skin = structuredClone(elevatorSkin);
  skin.ui.decodePrefix = '[CUSTOM DECODE]';
  loadSkin(skin);

  const text = getDecodedMonitorText({ title: 'Log A', content: 'Content A' });

  assert.equal(text, '[CUSTOM DECODE] Log A\nContent A');

  loadSkin(elevatorSkin);
});

test('door and direction labels use the current skin value maps', () => {
  loadSkin(securitySkin);

  assert.equal(getDoorLabel('open'), '已解锁');
  assert.equal(getDoorLabel('closed'), '已锁定');
  assert.equal(getDoorLabel('jammed'), 'jammed');
  assert.equal(getDirectionLabel('up'), '巡逻中');
  assert.equal(getDirectionLabel('down'), '回防中');
  assert.equal(getDirectionLabel('idle'), '待命');
  assert.equal(getDirectionLabel('sideways'), 'sideways');

  loadSkin(elevatorSkin);
});
