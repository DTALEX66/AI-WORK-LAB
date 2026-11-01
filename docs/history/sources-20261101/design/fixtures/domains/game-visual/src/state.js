import CONFIG from './gameConfig.js';
import { createFeedbackLine } from './feedback.js';
import { findRollbackSnapshot } from './rollback.js';
import { t } from './skinManager.js';
import { createContaminationState } from './contamination.js';
import { createInvestigationState } from './investigationTools.js';

function createNightState() {
  return {
    activeProtocols: [],
    currentShift: null,
    roundType: 'quick',
    shiftIndex: 0,
    decisions: [],
    eventChains: {},
    eventChainFlags: [],
    eventChainHistory: [],
    timelineSequence: 0,
    nextShiftModifiers: [],
  };
}

export function createInitialState() {
  const c = CONFIG.initial;
  return {
    floor: c.floor,
    door: c.door,
    moving: c.moving,
    direction: c.direction,
    transition: null,
    power: c.power,
    stability: c.stability,
    anomalyLevel: c.anomalyLevel,
    contamination: createContaminationState(),
    night: createNightState(),
    investigation: createInvestigationState({ power: c.power }),
    passengers: c.passengers,
    gameOver: c.gameOver,
    result: 'playing',
    elapsed: 0,
    remaining: c.duration,
    adRevivesUsed: 0,
    hiddenLogsUnlocked: 0,
    lastAdHint: '',
    monitor: t('monitor.initial'),
    activeAnomaly: null,
    snapshots: [],
    hiddenLogs: [],
    adHintsUsed: 0,
    consecutiveFailures: 0,
    fakeEndingCount: 0,
    fakeEndingCooldownRemaining: 0,
    fakeEndingTriggered: false,
    fakeEndingUnlocked: false,
    // 复盘统计（局内累积）
    anomaliesTriggeredTotal: 0,
    maxAnomalySeverity: 0,
    inspection: null,
    decisionsCorrect: 0,
    decisionsWrong: 0,
    score: 0,
    streak: 0,
    bestStreak: 0,
    tutorialStep: 0,
    lastFeedback: t('ui.initialFeedback'),
    logs: [createFeedbackLine('info', t('ui.initialLog'), 0)],
  };
}

function cloneValue(value) {
  if (value === undefined || value === null) return value;
  return JSON.parse(JSON.stringify(value));
}

export function cloneState(state) {
  return cloneValue(state);
}

export function appendLog(state, type, message) {
  const next = cloneState(state);
  next.logs.push(createFeedbackLine(type, message, next.elapsed ?? 0));
  if (next.logs.length > CONFIG.logs.maxLines) next.logs = next.logs.slice(-CONFIG.logs.maxLines);
  return next;
}

export function clamp(value, min, max) {
  return Math.max(min, Math.min(max, value));
}

export function checkFailure(state) {
  const next = cloneState(state);
  const f = CONFIG.failure;
  if (next.power <= f.powerMin || next.stability <= f.stabilityMin || next.anomalyLevel >= f.anomalyLevelMax || next.passengers < f.passengersMin) {
    next.gameOver = true;
    next.result = 'failure';
    next.moving = false;
    next.direction = 'idle';
    next.transition = null;
  }
  return next;
}

export function saveSnapshot(state) {
  const snapshots = [...(state.snapshots || [])];
  // Build a clean copy of the state without the snapshots array (no nesting)
  const clean = {};
  for (const key of Object.keys(state)) {
    if (key === 'snapshots') continue;
    clean[key] = cloneValue(state[key]);
  }
  snapshots.push({ at: state.elapsed, state: clean });
  const next = cloneState(state);
  next.snapshots = snapshots.slice(-CONFIG.revive.maxSnapshots);
  return next;
}


export function revive(state) {
  const snapshots = state.snapshots || [];
  const best = findRollbackSnapshot(snapshots, state.elapsed);

  let next;
  if (best) {
    next = cloneState(best.state);
    next.snapshots = snapshots; // preserve snapshot history
    next.rollbackSeconds = state.elapsed - best.at;
  } else {
    // No snapshot early enough — fall back to initial baseline
    next = createInitialState();
    next.snapshots = snapshots;
    next.rollbackSeconds = state.elapsed;
    next.elapsed = state.elapsed; // keep the clock running
    next.remaining = Math.max(1, state.remaining);
  }

  next.gameOver = false;
  next.result = 'playing';
  next.door = 'closed';
  next.moving = false;
  next.direction = 'idle';
  next.transition = null;
  next.activeAnomaly = null;
  next.adRevivesUsed += 1;
  next.monitor = t('failure.reviveMonitor', { seconds: next.rollbackSeconds });
  next = appendLog(next, 'success', t('failure.reviveRollback', { seconds: next.rollbackSeconds }));
  return next;
}

export function tickState(state, seconds = 1) {
  let next = cloneState(state);
  const tk = CONFIG.tick;
  next.elapsed += seconds;
  next.remaining = clamp(next.remaining - seconds, 0, CONFIG.initial.duration);
  if (next.moving) {
    next.power = clamp(next.power - seconds * tk.powerDrainMoving, 0, 100);
    next.stability = clamp(next.stability - seconds * tk.stabilityDrainMoving, 0, 100);
  } else {
    next.power = clamp(next.power - seconds * tk.powerDrainIdle, 0, 100);
  }
  if (next.transition) {
    next.transition.remaining = Math.max(0, Number(next.transition.remaining || 0) - seconds);
    if (next.transition.remaining <= 0) {
      if (next.transition.kind === 'movingUp' || next.transition.kind === 'movingDown') {
        next.moving = false;
        next.direction = 'idle';
      }
      next.transition = null;
    }
  }
  if (next.remaining <= 0) {
    next.gameOver = true;
    next.result = 'success';
    next.activeAnomaly = null;
    next.inspection = null;
    next.transition = null;
    next.moving = false;
    next.direction = 'idle';
    next.lastFeedback = t('ui.successfulShift');
    next = appendLog(next, 'success', next.lastFeedback);
    return next;
  }

  return checkFailure(next);
}

export function recordSuccessfulShift(state) {
  let next = cloneState(state);
  next.result = 'success';
  next.consecutiveFailures = 0;
  next.fakeEndingCooldownRemaining = 0;
  next.fakeEndingTriggered = false;
  next.fakeEndingUnlocked = false;
  next.fakeEndingCount = 0;
  next = appendLog(next, 'success', t('ui.shiftComplete'));
  return next;
}

export function recordFailure(state) {
  const fe = CONFIG.fakeEnding;
  const next = cloneState(state);
  next.result = 'failure';
  next.consecutiveFailures += 1;

  if (next.fakeEndingCooldownRemaining > 0) {
    next.fakeEndingCooldownRemaining -= 1;
    next.fakeEndingTriggered = false;
    return next;
  }

  if (next.consecutiveFailures >= fe.consecutiveFailuresThreshold) {
    next.fakeEndingTriggered = true;
    next.fakeEndingUnlocked = false;
    next.fakeEndingCount = next.consecutiveFailures;
    next.consecutiveFailures = 0;
    next.fakeEndingCooldownRemaining = fe.cooldownFailures;
  }

  return next;
}
