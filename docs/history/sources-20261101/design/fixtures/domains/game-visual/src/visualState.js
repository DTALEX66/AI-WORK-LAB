/**
 * visualState.js — 驱动 CCTV 视觉状态的核心映射
 *
 * V4 重构原则：
 * - CCTV 状态由 anomalyContent.js 的 visualState 字段驱动
 * - 所有异常必须有对应的 visualState 映射
 * - 正常运行期间 CCTV 反映的是实时移动/门体状态而非残余数值
 * - 电源/异常等级警报仅在真正有风险时覆盖画面
 */
import { getAllAnomalyContents, getAnomalyCctvState } from './anomalyContent.js';

function clampVisualValue(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

// ─── 异常动作提示（用于 V3 DOM 界面 / 非 base 模式的遗留兼容） ──
const ACTIVE_ANOMALY_ACTION_HINTS = Object.freeze({
  stop_failure: 'restartSystem',
  door_refuse: 'closeDoor',
  phantom_floor: 'inspectLog',
  camera_delay: 'inspectLog',
  log_echo: 'inspectLog',
  auto_button: 'restartSystem',
  floor_jump: 'inspectLog',
  zero_passenger_shadow: 'inspectLog',
  negative_floor: 'inspectLog',
  weight_mismatch: 'inspectLog',
  power_drain: 'restartSystem',
  light_flicker: 'restartSystem',
  emergency_lights: 'restartSystem',
  passenger_duplicate: 'closeDoor',
  door_gap_whisper: 'closeDoor',
  camera_blackout: 'inspectLog',
});

export function getAnomalyResolutionAction(anomalyId) {
  return ACTIVE_ANOMALY_ACTION_HINTS[anomalyId] || null;
}

function getHighlightAction(state) {
  if (state.gameOver) return 'restartSystem';
  if (state.activeAnomaly && ACTIVE_ANOMALY_ACTION_HINTS[state.activeAnomaly]) {
    return ACTIVE_ANOMALY_ACTION_HINTS[state.activeAnomaly];
  }
  // 正常运行且无活动异常时不高亮任何动作
  if (isNormalRunning(state)) return null;
  if (state.anomalyLevel >= 4) return 'restartSystem';
  if (state.anomalyLevel >= 2) return 'inspectLog';
  return null;
}

function getTone(anomalyLevel, gameOver) {
  if (gameOver) return 'danger';
  if (anomalyLevel >= 4) return 'critical';
  if (anomalyLevel >= 1) return 'warn';
  return 'normal';
}

/**
 * 判断当前是否处于"正常运行"状态——没有活动异常、正在或即将巡检、非结算。
 * 此时 CCTV 应反映面板数据（楼层/门/方向），不因残余数值泄题。
 */
function isNormalRunning(safeState) {
  return !safeState.gameOver
    && safeState.result !== 'success'
    && !safeState.activeAnomaly
    && !safeState.fakeEndingCooldownRemaining;
}

function getCctvState(state, anomalyLevel) {
  // ── 终局覆盖 ──
  if (state.result === 'success') return '19_stabilized';
  if (state.gameOver || anomalyLevel >= 5) return '20_threat_high';

  // ── 活动异常 CCTV 状态 ──
  if (state.activeAnomaly) {
    const cctvState = getAnomalyCctvState(state.activeAnomaly);
    if (cctvState) return cctvState;
  }

  // ── 假结局冷却 ──
  if (state.fakeEndingCooldownRemaining > 0) return '23_cooldown_safe';

  // ── 正常运行：优先反映面板数据（方向/门），不展示残余数值 ──
  if (isNormalRunning(state)) {
    if (state.direction === 'up') return '04_moving_up';
    if (state.direction === 'down') return '05_moving_down';
    if (state.door === 'open') return '01_door_open';
    if (state.door === 'opening') return '02_door_opening';
    if (state.door === 'closing') return '03_door_closing';
    // 待机状态：稳定度高时显示 stabilized，否则显示默认 idle
    if (state.stability >= 92 && state.elapsed > 0) return '19_stabilized';
    return '00_idle_closed';
  }

  // ── 异常活跃期间视觉警报 ──
  if (state.power <= 5) return '07_power_outage';
  if (state.power <= 22) return '06_power_low';
  if (state.direction === 'up') return '04_moving_up';
  if (state.direction === 'down') return '05_moving_down';
  if (state.door === 'open') return '01_door_open';
  if (state.door === 'opening') return '02_door_opening';
  if (state.door === 'closing') return '03_door_closing';
  if (state.stability >= 92 && state.elapsed > 0) return '19_stabilized';
  if (anomalyLevel >= 3) return '13_entity_near';
  if (anomalyLevel > 0) return '10_signal_lost';
  return '00_idle_closed';
}

export function deriveVisualState(state) {
  const rawAnomaly = Number(state?.anomalyLevel ?? 0);
  const success = state?.result === 'success';
  const gameOver = Boolean(state?.gameOver);

  // 在正常运行且无活动异常时，不再因为残余 anomalyLevel 非零而触发警报视觉
  const normalRunning = isNormalRunning(state);
  const anomalyLevel = normalRunning ? 0 : rawAnomaly;

  const active = Boolean(state?.gameOver && !success) || (!success && (Boolean(state?.activeAnomaly) || (!normalRunning && anomalyLevel > 0)));
  const pressure = clampVisualValue(anomalyLevel / 6, 0, 1);
  const safeState = state ?? {};

  return {
    tone: success ? 'normal' : getTone(anomalyLevel, gameOver),
    glitch: active,
    shake: Boolean(state?.gameOver && !success) || (!success && (!normalRunning && anomalyLevel >= 4)),
    noise: success ? 0.18 : gameOver ? 1 : Number((0.18 + pressure * 0.82).toFixed(2)),
    highlightAction: getHighlightAction(safeState),
    cctvState: getCctvState(safeState, anomalyLevel),
  };
}
