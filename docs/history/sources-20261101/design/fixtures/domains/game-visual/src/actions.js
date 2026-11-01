import { appendLog, checkFailure, clamp, cloneState } from './state.js';
import CONFIG from './gameConfig.js';
import { t, actionLabel } from './skinManager.js';
import { getAnomalyResolutionAction } from './visualState.js';

const ACTIONS = {
  openDoor(state) {
    if (state.moving) return fail(state, t('actionFailMessages.openDoor_moving'));
    let next = cloneState(state);
    next.door = 'open';
    next.transition = {
      kind: 'doorOpening', duration: 1, remaining: 1,
      fromDoor: state.door, toDoor: 'open',
    };
    next.monitor = t('monitor.actions.openDoor', { floor: next.floor });
    next = appendLog(next, 'info', t('actionLogMessages.openDoor', { floor: next.floor }));
    return ok(next, t('actionFeedback.openDoor'));
  },

  closeDoor(state) {
    let next = cloneState(state);
    next.door = 'closed';
    next.transition = {
      kind: 'doorClosing', duration: 1, remaining: 1,
      fromDoor: state.door, toDoor: 'closed',
    };
    next.monitor = t('monitor.actions.closeDoor');
    next = appendLog(next, 'info', t('actionLogMessages.closeDoor'));
    return ok(next, t('actionFeedback.closeDoor'));
  },

  moveUp(state) {
    if (state.door !== 'closed') return fail(state, t('actionFailMessages.moveUp_doorNotClosed'));
    let next = cloneState(state);
    const a = CONFIG.actions.moveUp;
    const fromFloor = next.floor;
    next.floor += 1;
    next.moving = true;
    next.direction = 'up';
    next.transition = {
      kind: 'movingUp', duration: 2, remaining: 2,
      fromFloor, toFloor: next.floor,
    };
    next.power = clamp(next.power - a.powerCost, 0, 100);
    next.stability = clamp(next.stability - a.stabilityCost, 0, 100);
    next.monitor = t('monitor.actions.moveUp', { floor: next.floor });
    next = appendLog(next, 'info', t('actionLogMessages.moveUp', { floor: next.floor }));
    return ok(checkFailure(next), t('actionFeedback.moveUp'));
  },

  moveDown(state) {
    if (state.door !== 'closed') return fail(state, t('actionFailMessages.moveDown_doorNotClosed'));
    let next = cloneState(state);
    const a = CONFIG.actions.moveDown;
    const fromFloor = next.floor;
    next.floor -= 1;
    next.moving = true;
    next.direction = 'down';
    next.transition = {
      kind: 'movingDown', duration: 2, remaining: 2,
      fromFloor, toFloor: next.floor,
    };
    next.power = clamp(next.power - a.powerCost, 0, 100);
    next.stability = clamp(next.stability - a.stabilityCost, 0, 100);
    next.monitor = t('monitor.actions.moveDown', { floor: next.floor });
    next = appendLog(next, 'info', t('actionLogMessages.moveDown', { floor: next.floor }));
    return ok(checkFailure(next), t('actionFeedback.moveDown'));
  },

  emergencyStop(state) {
    let next = cloneState(state);
    const es = CONFIG.actions.emergencyStop;
    if (next.activeAnomaly === 'stop_failure') {
      next.anomalyLevel = clamp(next.anomalyLevel + 1, 0, 6);
      next.stability = clamp(next.stability - es.stabilityCostOnFailure, 0, 100);
      next = appendLog(next, 'danger', t('actionLogMessages.emergencyStop_fail'));
      return fail(checkFailure(next), t('actionFeedback.emergencyStop_fail'));
    }
    next.moving = false;
    next.direction = 'idle';
    next.transition = { kind: 'emergencyStop', duration: 1, remaining: 1 };
    next.stability = clamp(next.stability - es.stabilityCost, 0, 100);
    next.monitor = t('monitor.actions.emergencyStop');
    next = appendLog(next, 'warn', t('actionLogMessages.emergencyStop'));
    return ok(checkFailure(next), t('actionFeedback.emergencyStop'));
  },

  restartSystem(state) {
    let next = cloneState(state);
    const rs = CONFIG.actions.restartSystem;
    next.anomalyLevel = Math.max(0, next.anomalyLevel - rs.anomalyLevelReduce);
    next.stability = clamp(next.stability + rs.stabilityRestore, 0, 100);
    next.power = clamp(next.power - rs.powerCost, 0, 100);
    next.moving = false;
    next.direction = 'idle';
    next.transition = { kind: 'systemReboot', duration: 2, remaining: 2 };
    next.monitor = t('monitor.actions.restartSystem');
    next = appendLog(next, 'warn', t('actionLogMessages.restartSystem', { cost: rs.powerCost }));
    return ok(checkFailure(next), t('actionFeedback.restartSystem'));
  },

  inspectLog(state) {
    let next = appendLog(state, 'info', t('actionLogMessages.inspectLog'));
    const lockedCount = next.hiddenLogs.filter(h => h.locked).length;
    if (lockedCount > 0) {
      next = appendLog(next, 'system', t('actionLogMessages.inspectLog_hiddenRecords', { count: lockedCount }));
    }
    return ok(next, t('actionFeedback.inspectLog'));
  },

  unlockHiddenLog(state) {
    // 找到第一条仍锁定的隐藏日志
    const locked = state.hiddenLogs.find(h => h.locked);
    if (!locked) {
      return fail(state, t('actionFeedback.unlockHiddenLog_noLocked'));
    }
    const unlocked = state.adHintsUsed;
    if (unlocked >= CONFIG.hiddenLogs.maxUnlockedPerRun) {
      return fail(state, t('actionFeedback.unlockHiddenLog_limit', { count: unlocked }));
    }
    let next = cloneState(state);
    const idx = next.hiddenLogs.findIndex(h => h.id === locked.id);
    if (idx !== -1) {
      next.hiddenLogs[idx] = { ...next.hiddenLogs[idx], locked: false };
    }
    next.adHintsUsed += 1;
    next = appendLog(next, 'system', t('actionLogMessages.unlockHiddenLog_ok'));
    next.monitor = t('ui.decodeMonitor', { title: locked.title });
    return ok(next, t('ui.unlockResult', { title: locked.title }));
  },
};

function ok(state, message) {
  return { ok: true, state, message };
}

function fail(state, message) {
  const next = appendLog(state, 'warn', message);
  return { ok: false, state: next, message };
}

export function performAction(state, actionId) {
  const action = ACTIONS[actionId];
  if (!action) return fail(state, t('actionFailMessages.unknownAction', { actionId }));
  if (state.gameOver && actionId !== 'inspectLog') return fail(state, t('actionFailMessages.gameOver'));
  const hasSpecificDoorFailure = ['moveUp', 'moveDown'].includes(actionId) && state.door !== 'closed';
  if (state.transition && !hasSpecificDoorFailure && !['emergencyStop', 'inspectLog', 'unlockHiddenLog'].includes(actionId)) {
    return fail(state, t('actionFailMessages.systemBusy'));
  }
  const activeAnomaly = state.activeAnomaly;
  const resolutionAction = activeAnomaly ? getAnomalyResolutionAction(activeAnomaly) : null;
  const preservesSpecificStopFailure = activeAnomaly === 'stop_failure' && actionId === 'emergencyStop';
  if (activeAnomaly && resolutionAction && resolutionAction !== actionId && !preservesSpecificStopFailure) {
    let next = cloneState(state);
    if (Number(next.tutorialStep || 0) === 2) {
      next.lastFeedback = t('ui.wrongTreatmentTutorial');
      next = appendLog(next, 'info', next.lastFeedback);
      return { ok: false, state: next, message: next.lastFeedback, coached: true };
    }
    next.stability = clamp((next.stability ?? 0) - 6, 0, 100);
    next.anomalyLevel = clamp((next.anomalyLevel ?? 0) + 1, 0, 6);
    next.streak = 0;
    next.lastFeedback = t('ui.wrongTreatment');
    next = appendLog(next, 'danger', next.lastFeedback);
    return { ok: false, state: checkFailure(next), message: next.lastFeedback };
  }

  const result = action(state);
  if (!result.ok || !activeAnomaly || resolutionAction !== actionId) {
    return result;
  }

  let next = cloneState(result.state);
  next.activeAnomaly = null;
  next.score = (next.score ?? 0) + 150;
  if (Number(next.tutorialStep || 0) === 2) next.tutorialStep = 3;
  if (result.state.activeAnomaly === activeAnomaly) {
    next.anomalyLevel = Math.min(next.anomalyLevel, Math.max(0, state.anomalyLevel - 1));
  }
  next.monitor = t('ui.anomalyResolvedMonitor');
  const message = t('ui.anomalyResolved', { action: actionLabel(actionId) });
  next.lastFeedback = message;
  next = appendLog(next, 'success', message);
  return ok(checkFailure(next), message);
}

const ACTION_IDS = [
  'openDoor',
  'closeDoor',
  'moveUp',
  'moveDown',
  'emergencyStop',
  'restartSystem',
  'inspectLog',
  'unlockHiddenLog',
];

export function getAvailableActions() {
  return ACTION_IDS.map(id => ({ id, label: actionLabel(id) }));
}
