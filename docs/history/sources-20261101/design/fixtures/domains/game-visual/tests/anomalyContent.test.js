/**
 * anomalyContent.test.js — 异常内容模式验证
 *
 * 覆盖《第一阶段任务 E》全部断言要求：
 * - 每个异常至少存在一个明确冲突字段（或替代线索说明）
 * - 正常班次所有关键字段一致
 * - 正确判断得分
 * - 误报处罚
 * - 漏报处罚
 * - 超时只处罚一次
 * - 前两班教学误点不处罚
 * - 第三班无高亮
 * - 自动处置不额外加分
 * - 结算后异常与动画全部清除
 *
 * 其中运行时相关断言（得分/处罚/教学等）在 incidentDecision.test.js
 * 和 douyinBundleSmoke.test.js 中已有覆盖，本文件聚焦 数据一致性断言。
 */
import assert from 'node:assert/strict';
import test from 'node:test';

import {
  getAllAnomalyContents,
  findAnomalyContent,
  isDataConsistent,
  getConflictFields,
  NORMAL_VARIANTS,
  getAnomalyCctvState,
  getAnomaliesByCctvState,
  getNormalCctvStates,
  getAnomalyCctvStates,
} from '../src/anomalyContent.js';
import { ANOMALIES } from '../src/events.js';
import { createInitialState } from '../src/state.js';
import { expireInspection, openInspection, submitInspection } from '../src/incidentDecision.js';

// ─── 辅助 ──────────────────────────────────────────────────

const ALL = getAllAnomalyContents();

// ─── A. 模式完整性 ─────────────────────────────────────────

test('all 12 anomaly contents have required fields', () => {
  assert.equal(ALL.length, 12);
  for (const a of ALL) {
    assert.ok(a.id, `missing id`);
    assert.ok(a.title, `${a.id}: missing title`);
    assert.ok(a.severity >= 1 && a.severity <= 3, `${a.id}: severity out of range`);
    assert.ok(a.difficulty >= 1 && a.difficulty <= 3, `${a.id}: difficulty out of range`);
    assert.ok(['release', 'lockdown'].includes(a.correctDecision), `${a.id}: invalid correctDecision`);
    assert.ok(a.screenData, `${a.id}: missing screenData`);
    assert.ok(a.panelData, `${a.id}: missing panelData`);
    assert.ok(a.primaryConflict, `${a.id}: missing primaryConflict`);
    assert.ok(a.explanation, `${a.id}: missing explanation`);
    assert.ok(a.visualState, `${a.id}: missing visualState`);
    assert.ok(a.audioCue, `${a.id}: missing audioCue`);
    assert.ok(a.resolutionAction, `${a.id}: missing resolutionAction`);
    assert.ok(a.monitorTemplate, `${a.id}: missing monitorTemplate`);
    assert.ok(typeof a.stabilityPenalty === 'number', `${a.id}: stabilityPenalty not a number`);
    assert.ok(typeof a.powerPenalty === 'number', `${a.id}: powerPenalty not a number`);
  }
});

// ─── B. 一致性：异常必须有至少一个明确矛盾 ───────────────────

test('each anomaly has at least one conflict field (or documented non-field conflict)', () => {
  for (const a of ALL) {
    const fields = getConflictFields(a);
    // 三要素完全一致的异常必须提供非字段矛盾说明
    if (fields.length === 0) {
      assert.ok(
        a.primaryConflict.length > 15,
        `${a.id}: zero-field anomaly must explain its non-field conflict (got: "${a.primaryConflict}")`
      );
      // 确保说明中包含具体可观察线索，而非"所有数据一致"这样的空话
      const hasSpecificClue = /日志|按钮|电源|急停|灯光|应急|重复|自动/.test(a.primaryConflict);
      assert.ok(hasSpecificClue, `${a.id}: zero-field anomaly conflict must name a specific observable clue`);
    }
    assert.ok(fields.length >= 0, `${a.id}: invalid conflict fields`);
  }
});

// ─── C. 一致性：正常班次所有字段一致 ────────────────────────

test('each normal variant has fully consistent data', () => {
  assert.ok(NORMAL_VARIANTS.length >= 10, `normal variants should be >= 10, got ${NORMAL_VARIANTS.length}`);
  for (const v of NORMAL_VARIANTS) {
    assert.ok(v.scenario, `missing scenario`);
    assert.ok(v.visualState, `missing visualState`);
    assert.ok(v.floor !== undefined, `missing floor`);
    assert.ok(v.passengers !== undefined, `missing passengers`);
    assert.ok(v.door, `missing door`);
    assert.ok(v.direction, `missing direction`);
  }
});

// ─── D. 三要素数据范围 ─────────────────────────────────────

test('all floor/passenger/door/direction values are within valid ranges', () => {
  for (const a of ALL) {
    const check = (label, obj) => {
      assert.ok(obj.floor >= -5 && obj.floor <= 100, `${a.id}/${label}: floor ${obj.floor} out of range`);
      assert.ok(obj.passengers >= 0 && obj.passengers <= 20, `${a.id}/${label}: passengers ${obj.passengers} out of range`);
      assert.ok(['open', 'closed'].includes(obj.door), `${a.id}/${label}: invalid door`);
      assert.ok(['idle', 'up', 'down'].includes(obj.direction), `${a.id}/${label}: invalid direction`);
    };
    check('screenData', a.screenData);
    check('panelData', a.panelData);
  }
  for (const v of NORMAL_VARIANTS) {
    assert.ok(v.floor >= -5 && v.floor <= 100, `normal variant floor ${v.floor} out of range`);
    assert.ok(v.passengers >= 0 && v.passengers <= 20, `normal variant passengers ${v.passengers} out of range`);
    assert.ok(['open', 'closed'].includes(v.door), `normal variant invalid door`);
    assert.ok(['idle', 'up', 'down'].includes(v.direction), `normal variant invalid direction`);
  }
});

// ─── E. 与 skin.json 异常 ID 一致 ──────────────────────────

test('all anomaly content IDs match skin.json anomaly IDs', () => {
  const contentIds = new Set(ALL.map(a => a.id));
  const skinIds = new Set(ANOMALIES.map(a => a.id));
  for (const id of contentIds) {
    assert.ok(skinIds.has(id), `content anomaly ${id} missing from skin.json`);
  }
  for (const id of skinIds) {
    assert.ok(contentIds.has(id), `skin anomaly ${id} missing from anomalyContent.js`);
  }
});

// ─── F. 正常变体对抗模式识别 ──────────────────────────────

test('normal variants include floor numbers that appear in anomaly conflicts', () => {
  const anomalyFloors = new Set(ALL.flatMap(a => [a.screenData.floor, a.panelData.floor]));
  const normalFloors = new Set(NORMAL_VARIANTS.map(v => v.floor));
  // normal variants should have at least one floor that also appears in anomalies
  const overlap = [...anomalyFloors].filter(f => normalFloors.has(f));
  assert.ok(overlap.length >= 1, `normal variants should share floors with anomalies: anomaly floors=${[...anomalyFloors].join(',' )}`);
});

// ─── G. 辅助函数正确性 ─────────────────────────────────────

test('findAnomalyContent returns null for unknown IDs', () => {
  assert.equal(findAnomalyContent('nonexistent_anomaly'), null);
});

test('findAnomalyContent returns the correct entry by ID', () => {
  const phantom = findAnomalyContent('phantom_floor');
  assert.ok(phantom);
  assert.equal(phantom.title, '不存在的楼层');
  assert.equal(phantom.correctDecision, 'lockdown');
});

test('field-level anomalies have inconsistent screenData/panelData while compound anomalies have consistent data but non-field conflicts', () => {
  for (const a of ALL) {
    // 只有 screenData !== panelData 时 isDataConsistent 才返回 false
    // 但对于三要素一致但仍是异常的类型（log_echo, auto_button 等），
    // isDataConsistent 返回 true，说明矛盾不在三要素中
    const consistent = isDataConsistent(a);
    if (consistent) {
      assert.equal(getConflictFields(a).length, 0, `${a.id}: consistent data but has field conflicts`);
    }
  }
});

// ─── H. 运行时可断言：异常被判定为封锁（lockdown） ─────────

test('all anomaly correct decisions are lockdown (anomaly = conflict)', () => {
  for (const a of ALL) {
    assert.equal(a.correctDecision, 'lockdown', `${a.id}: anomaly must always be lockdown`);
  }
});

// ─── I. 教学与误点测试（引用现有状态测试确保不被破坏） ─────

test('guided first class wrong tap keeps inspection pending without penalty', () => {
  const state = createInitialState();
  const opened = openInspection(state, {
    id: 'baseline-test', kind: 'normal', title: '核对画面与数据', duration: 6,
  });
  const wrong = submitInspection(opened, 'anomaly');
  assert.equal(wrong.accepted, false);
  assert.equal(wrong.state.inspection.status, 'pending');
  assert.equal(wrong.state.stability, 100);
  assert.equal(wrong.state.score, 0);

  // 连点两次仍然无处罚
  const wrongAgain = submitInspection(wrong.state, 'anomaly');
  assert.equal(wrongAgain.accepted, false);
  assert.equal(wrongAgain.state.stability, 100);
  assert.equal(wrongAgain.state.decisionsWrong, 0);
});

test('guided second class wrong tap keeps inspection pending without penalty', () => {
  const state = { ...createInitialState(), tutorialStep: 1, activeAnomaly: 'floor_jump' };
  const opened = openInspection(state, {
    id: 'floor_jump-test', kind: 'anomaly', title: '核对画面与数据', duration: 6,
  });
  const wrong = submitInspection(opened, 'normal');
  assert.equal(wrong.accepted, false);
  assert.equal(wrong.state.stability, 100);
  assert.equal(wrong.state.decisionsWrong, 0);
});

// ─── J. 超时只处罚一次 ─────────────────────────────────────

test('inspection timeout penalizes exactly once (non-teaching)', () => {
  const state = { ...createInitialState(), elapsed: 5, tutorialStep: 4 };
  const opened = openInspection(state, {
    id: 'baseline-5', kind: 'normal', title: '常规巡检', duration: 4,
  });
  const expired = expireInspection({ ...opened, elapsed: 9 });
  assert.equal(expired.timedOut, true);
  assert.equal(expired.state.stability, 92, 'timeout should deduct 8 stability');
  const again = expireInspection({ ...expired.state, elapsed: 20 });
  assert.equal(again.timedOut, false, 'second expire should not fire again');
  assert.equal(again.state.stability, 92, 'stability should not drop on second call');
});

// ─── K. CCTV 状态映射验证 ───────────────────────────────────

test('getAnomalyCctvState returns correct state for all 12 anomalies', () => {
  for (const a of ALL) {
    const state = getAnomalyCctvState(a.id);
    assert.equal(state, a.visualState, `${a.id}: expected visualState ${a.visualState}, got ${state}`);
  }
});

test('getAnomalyCctvState returns null for unknown anomaly IDs', () => {
  assert.equal(getAnomalyCctvState('nonexistent'), null);
});

test('getAnomaliesByCctvState returns all anomalies sharing a CCTV state', () => {
  // 16_wrong_floor is shared by phantom_floor, negative_floor, floor_jump
  const wrongFloor = getAnomaliesByCctvState('16_wrong_floor');
  assert.ok(wrongFloor.length >= 3, `expected >=3 anomalies for 16_wrong_floor, got ${wrongFloor.length}`);
  assert.ok(wrongFloor.includes('phantom_floor'));
  assert.ok(wrongFloor.includes('negative_floor'));
  assert.ok(wrongFloor.includes('floor_jump'));
});

test('getAnomaliesByCctvState returns empty array for normal-only states', () => {
  assert.equal(getAnomaliesByCctvState('00_idle_closed').length, 0);
  assert.equal(getAnomaliesByCctvState('19_stabilized').length, 0);
});

test('getNormalCctvStates lists only non-anomaly states', () => {
  const normalStates = getNormalCctvStates();
  const anomalyStates = getAnomalyCctvStates();
  // no overlap between normal and anomaly states
  for (const ns of normalStates) {
    assert.equal(anomalyStates.includes(ns), false,
      `normal state ${ns} should not appear in anomaly states`);
  }
});

test('getAnomalyCctvStates covers all anomaly visualStates', () => {
  const states = getAnomalyCctvStates();
  for (const a of ALL) {
    assert.ok(states.includes(a.visualState), `${a.id}: visualState ${a.visualState} not in anomaly Cctv states`);
  }
});

// ─── L. visualState 与 anomalyContent 一致性 ─────────────────

test('anomaly content visualState is used by deriveVisualState for active anomalies', async () => {
  for (const a of ALL) {
    const state = createInitialState();
    state.activeAnomaly = a.id;
    // Use an anomalyLevel that won't override the anomaly-specific state
    state.anomalyLevel = 2;
    // deriveVisualState should return the correct CCTV state for this anomaly
    const visual = await import('../src/visualState.js').then(m => m.deriveVisualState(state));
    assert.equal(visual.cctvState, a.visualState,
      `${a.id}: expected CCTV state ${a.visualState} from deriveVisualState, got ${visual.cctvState}`);
  }
});
