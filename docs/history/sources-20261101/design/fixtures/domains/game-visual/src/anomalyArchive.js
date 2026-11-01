/**
 * anomalyArchive.js — 局内/局后异常档案与决策时间线
 *
 * 职责：
 * - 记录每班判断结果（时间线条目）
 * - 提供异常档案查询（供复盘和异常档案库使用）
 * - 跟踪决策级数据（供埋点使用）
 */
import { ANOMALY_CONTENTS, findAnomalyContent, getConflictFields } from './anomalyContent.js';

// ─── 时间线条目 ──────────────────────────────────

/** @type {import('./anomalyContent.js').AnomalyContent[]} */
const CONTENT_BY_ID = {};
for (const a of ANOMALY_CONTENTS) {
  CONTENT_BY_ID[a.id] = a;
}

/**
 * @typedef {Object} TimelineEntry
 * @property {number} elapsed            — 本条记录时的游戏秒数
 * @property {'normal'|'anomaly'} kind   — 巡检类型
 * @property {string} anomalyId          — 异常 ID（kind='anomaly'时有效）
 * @property {string|null} playerChoice  — 'release' | 'lockdown' | null(超时)
 * @property {string|null} correctChoice — 'release' | 'lockdown'
 * @property {boolean} correct           — 是否正确
 * @property {boolean} timedOut          — 是否超时
 * @property {string[]} conflicts        — 触发判断的矛盾字段
 * @property {string} explanation        — 异常原因/复盘说明
 * @property {Object} screenSnapshot     — 判断时的 screenData
 * @property {Object} panelSnapshot      — 判断时的 panelData
 */

/** @type {TimelineEntry[]} */
let timeline = [];

export function resetTimeline() {
  timeline = [];
}

export function getTimeline() {
  return [...timeline];
}

/**
 * 记录一次判断到时间线
 */
export function recordDecision({
  elapsed,
  kind,
  anomalyId,
  playerChoice,
  correctChoice,
  timedOut = false,
  screenSnapshot = {},
  panelSnapshot = {},
}) {
  const correct = !timedOut && playerChoice === correctChoice;
  const content = kind === 'anomaly' && anomalyId ? CONTENT_BY_ID[anomalyId] : null;
  const conflicts = kind === 'anomaly' && content
    ? getConflictFields(content)
    : [];
  const explanation = kind === 'anomaly' && content
    ? content.explanation
    : (correct ? '信息一致，正常放行' : '判断与数据不符');

  const entry = {
    elapsed,
    kind,
    anomalyId: anomalyId || null,
    playerChoice,
    correctChoice,
    correct,
    timedOut,
    conflicts,
    explanation,
    screenSnapshot,
    panelSnapshot,
  };
  timeline.push(entry);
  return entry;
}

/**
 * 获取最后一班判断
 */
export function getLastDecision() {
  return timeline.length > 0 ? timeline[timeline.length - 1] : null;
}

/**
 * 获取本局判断统计
 */
export function getDecisionStats() {
  const total = timeline.length;
  const correct = timeline.filter(t => t.correct && !t.timedOut).length;
  const wrong = timeline.filter(t => !t.correct && !t.timedOut).length;
  const timeout = timeline.filter(t => t.timedOut).length;
  return { total, correct, wrong, timeout, accuracy: total > 0 ? correct / total : 0 };
}

// ─── 异常档案 ─────────────────────────────────────

/**
 * 获取归档版异常数据（供异常档案库展示）
 */
export function getArchiveEntry(anomalyId) {
  const content = findAnomalyContent(anomalyId);
  if (!content) return null;
  return {
    id: content.id,
    title: content.title,
    severity: content.severity,
    difficulty: content.difficulty,
    primaryConflict: content.primaryConflict,
    explanation: content.explanation,
    visualState: content.visualState,
    resolutionAction: content.resolutionAction,
    screenData: content.screenData,
    panelData: content.panelData,
    conflicts: getConflictFields(content),
  };
}

/**
 * 获取所有归档异常索引（供档案库列表使用）
 */
export function getArchiveIndex() {
  return ANOMALY_CONTENTS.map(a => ({
    id: a.id,
    title: a.title,
    severity: a.severity,
    difficulty: a.difficulty,
    primaryConflict: a.primaryConflict,
  }));
}

// ─── 决策级埋点 ──────────────────────────────────

/**
 * @typedef {Object} DecisionTelemetry
 * @property {number} elapsed
 * @property {string} anomalyId
 * @property {'release'|'lockdown'|null} playerChoice
 * @property {'release'|'lockdown'} correctChoice
 * @property {boolean} timedOut
 * @property {string[]} conflicts
 */

/**
 * 生成决策埋点事件
 */
export function createDecisionTelemetry(entry) {
  return {
    event: 'decision',
    elapsed: entry.elapsed,
    anomalyId: entry.anomalyId || '(normal)',
    playerChoice: entry.playerChoice || '(timeout)',
    correctChoice: entry.correctChoice,
    correct: entry.correct,
    timedOut: entry.timedOut,
    conflicts: entry.conflicts,
  };
}

/**
 * 将全量时间线转为埋点事件数组
 */
export function serializeTimelineForTelemetry() {
  return timeline.map(entry => createDecisionTelemetry(entry));
}
