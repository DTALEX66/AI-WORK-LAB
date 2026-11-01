import { appendLog, checkFailure, clamp, cloneState } from './state.js';
import CONFIG from './gameConfig.js';
import { getAnomalies, getHiddenLog as _getHiddenLog, t } from './skinManager.js';

/**
 * 从皮肤数据动态构建异常事件数组
 */
function createAnomaly(skinDef) {
  return {
    id: skinDef.id,
    title: skinDef.title,
    severity: skinDef.severity,
    monitor: skinDef.monitor,
    adHint: skinDef.adHint,
    effects: skinDef.effects || {},
    apply(state) {
      const next = cloneState(state);
      const effects = skinDef.effects || {};
      // 计算难度倍率
      const elapsed = state.elapsed || 0;
      const diffScale = CONFIG.anomaly.difficultyScale || 1;
      const diffInterval = CONFIG.anomaly.difficultyInterval || 10;
      const multiplier = Math.pow(diffScale, elapsed / diffInterval);

      for (const [field, value] of Object.entries(effects)) {
        let adjusted = value;
        // 负数效果（消耗类）才乘难度系数
        if (typeof value === 'number' && value < 0) {
          adjusted = Math.round(value * multiplier);
        } else if (typeof value === 'string' && isDeltaEffect(value) && parseInt(value, 10) < 0) {
          const num = parseInt(value, 10);
          adjusted = `${Math.round(num * multiplier)}`;
        }
        if (typeof adjusted === 'number' && shouldAddNumericEffect(field, adjusted)) {
          next[field] = clamp((next[field] ?? 0) + adjusted, 0, 100);
        } else if (typeof adjusted === 'string' && isDeltaEffect(adjusted)) {
          next[field] = Math.min(CONFIG.bounds.maxFloor, (next[field] ?? 0) + parseInt(adjusted, 10));
        } else {
          next[field] = adjusted;
        }
      }
      next.anomalyLevel = clamp(next.anomalyLevel, 0, 6);
      next.stability = clamp(next.stability, 0, 100);
      next.power = clamp(next.power, 0, 100);
      next.activeAnomaly = skinDef.id;
      next.monitor = skinDef.monitor;
      return next;
    },
  };
}

function isDeltaEffect(value) {
  return /^[+-]\d+$/.test(value);
}

function shouldAddNumericEffect(field, value) {
  if (value < 0) return true;
  return field === 'power' || field === 'stability' || field === 'anomalyLevel';
}

/** 当前皮肤生成的异常事件列表 */
export const ANOMALIES = getAnomalies().map(createAnomaly);

export function findAnomaly(id) {
  return ANOMALIES.find((event) => event.id === id);
}

export function applyAnomaly(state, id) {
  const event = findAnomaly(id);
  if (!event) throw new Error(`Unknown anomaly: ${id}`);
  let next = event.apply(state);
  next.lastAdHint = event.adHint;
  // 复盘统计
  next.anomaliesTriggeredTotal = (next.anomaliesTriggeredTotal ?? 0) + 1;
  next.maxAnomalySeverity = Math.max(next.maxAnomalySeverity ?? 0, event.severity);
  // 添加关联隐藏日志（不重复）
  const raw = _getHiddenLog(id);
  if (raw && !next.hiddenLogs.some(h => h.id === id + '_log')) {
    next.hiddenLogs.push({ id: id + '_log', title: raw.title, content: raw.content, locked: true });
    next = appendLog(next, 'info', t('ui.hiddenLogCaptured', { title: raw.title }));
  }
  next = appendLog(next, event.severity >= 3 ? 'danger' : 'warn', t('ui.anomalyEventLog', {
    title: event.title,
    hint: event.adHint,
  }));
  return { event, state: checkFailure(next) };
}

export function pickNextAnomaly(state, random = Math.random) {
  const firstRunPool = (state.anomaliesTriggeredTotal ?? 0) === 0
    ? ANOMALIES.filter(event => event.severity <= CONFIG.anomaly.firstMaxSeverity)
    : ANOMALIES;
  const pool = firstRunPool.length > 0 ? firstRunPool : ANOMALIES;
  const pressure = Math.min(pool.length - 1, Math.floor(state.anomalyLevel / CONFIG.anomaly.pressureDivisor));
  const index = Math.min(pool.length - 1, Math.floor(random() * pool.length + pressure) % pool.length);
  return pool[index];
}

// 向后兼容导出
export function getHiddenLog(anomalyId) {
  return _getHiddenLog(anomalyId);
}

/** @deprecated 请使用 getHiddenLog() 代替 */
const _buildHiddenLogsMap = () => {
  const map = {};
  const anomalies = getAnomalies();
  for (const a of anomalies) {
    const hl = _getHiddenLog(a.id);
    if (hl) {
      map[a.id] = { id: `${a.id}_log`, title: hl.title, content: hl.content };
    }
  }
  return map;
};

export const HIDDEN_LOGS = _buildHiddenLogsMap();
