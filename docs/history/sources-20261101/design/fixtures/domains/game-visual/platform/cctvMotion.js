import { deriveVisualState } from '../src/visualState.js';

const ACTION_DURATIONS = Object.freeze({
  openDoor: 1000,
  closeDoor: 1000,
  moveUp: 2000,
  moveDown: 2000,
  emergencyStop: 900,
  restartSystem: 1600,
});

function clamp01(value) {
  return Math.max(0, Math.min(1, value));
}

function easeInOut(progress) {
  return 0.5 - Math.cos(Math.PI * clamp01(progress)) / 2;
}

function settledFrame(state, now) {
  const visual = deriveVisualState(state);
  const signalPhase = now / 1000;
  const glitchState = ['10_signal_lost', '11_camera_glitch', '17_loop_corridor'].includes(visual.cctvState);
  const entityState = ['13_entity_near', '14_shadow_inside', '15_anomaly_wandering', '20_threat_high'].includes(visual.cctvState);
  return {
    active: false,
    kind: 'ambient',
    progress: 1,
    eased: 1,
    cctvState: visual.cctvState,
    previousCctvState: visual.cctvState,
    floorReel: Number(state.floor ?? 0),
    offsetX: glitchState ? Math.sin(signalPhase * 31) * 3 : 0,
    offsetY: state.moving ? Math.sin(signalPhase * 38) * 4 : 0,
    zoom: entityState ? 1.015 + Math.sin(signalPhase * 2.2) * 0.01 : 1,
    glitchAlpha: glitchState ? 0.18 + Math.abs(Math.sin(signalPhase * 17)) * 0.28 : 0,
    flickerAlpha: visual.cctvState === '07_power_outage' ? 0.45 + Math.abs(Math.sin(signalPhase * 13)) * 0.45 : 0,
    scanPhase: signalPhase % 1,
    frameTime: now,
  };
}

export function createCctvMotionController(now = () => Date.now()) {
  let timeline = null;
  let pausedAt = null;

  function startAction(actionId, beforeState, afterState) {
    const duration = ACTION_DURATIONS[actionId];
    if (!duration) return null;
    pausedAt = null;
    timeline = {
      type: 'action',
      kind: actionId,
      startedAt: now(),
      duration,
      beforeState,
      afterState,
      fromCctvState: deriveVisualState(beforeState).cctvState,
      toCctvState: deriveVisualState(afterState).cctvState,
    };
    return timeline;
  }

  function startAnomaly(beforeState, afterState) {
    pausedAt = null;
    timeline = {
      type: 'anomaly',
      kind: 'anomalyReveal',
      startedAt: now(),
      duration: 1300,
      beforeState,
      afterState,
      fromCctvState: deriveVisualState(beforeState).cctvState,
      toCctvState: deriveVisualState(afterState).cctvState,
    };
    return timeline;
  }

  function sample(state, at = now()) {
    at = pausedAt ?? at;
    if (!timeline) return settledFrame(state, at);
    const raw = (at - timeline.startedAt) / timeline.duration;
    if (raw >= 1) {
      timeline = null;
      return settledFrame(state, at);
    }

    const progress = clamp01(raw);
    const eased = easeInOut(progress);
    const base = settledFrame(state, at);
    const result = {
      ...base,
      active: true,
      kind: timeline.kind,
      progress,
      eased,
      previousCctvState: timeline.fromCctvState,
    };

    if (timeline.type === 'anomaly') {
      result.cctvState = timeline.toCctvState;
      result.offsetX = Math.sin((at - timeline.startedAt) * 0.095) * (8 * (1 - progress) + 2);
      result.offsetY = Math.cos((at - timeline.startedAt) * 0.067) * 3;
      result.zoom = 1 + eased * 0.035;
      result.glitchAlpha = 0.28 + Math.abs(Math.sin((at - timeline.startedAt) * 0.044)) * 0.62;
      return result;
    }

    const fromFloor = Number(timeline.beforeState.floor ?? state.floor ?? 0);
    const toFloor = Number(timeline.afterState.floor ?? state.floor ?? fromFloor);
    result.fromFloor = fromFloor;
    result.toFloor = toFloor;
    result.floorReel = fromFloor + (toFloor - fromFloor) * eased;

    if (timeline.kind === 'openDoor') {
      result.cctvState = progress < 0.16
        ? timeline.fromCctvState
        : progress < 0.84 ? '02_door_opening' : '01_door_open';
      result.zoom = 1 + Math.sin(progress * Math.PI) * 0.015;
    } else if (timeline.kind === 'closeDoor') {
      result.cctvState = progress < 0.16
        ? timeline.fromCctvState
        : progress < 0.84 ? '03_door_closing' : '00_idle_closed';
      result.zoom = 1 + Math.sin(progress * Math.PI) * 0.012;
    } else if (timeline.kind === 'moveUp' || timeline.kind === 'moveDown') {
      result.cctvState = timeline.kind === 'moveUp' ? '04_moving_up' : '05_moving_down';
      result.offsetY = Math.sin((at - timeline.startedAt) * 0.08) * 5
        + Math.sin((at - timeline.startedAt) * 0.021) * 3;
      result.offsetX = Math.sin((at - timeline.startedAt) * 0.037) * 1.8;
      result.zoom = 1.025 + Math.sin(progress * Math.PI) * 0.012;
    } else if (timeline.kind === 'emergencyStop') {
      result.cctvState = '08_emergency_stop';
      result.offsetX = Math.sin((at - timeline.startedAt) * 0.12) * 7 * (1 - progress);
      result.glitchAlpha = 0.22 + (1 - progress) * 0.38;
    } else if (timeline.kind === 'restartSystem') {
      result.cctvState = progress < 0.72 ? '22_system_reboot' : '19_stabilized';
      result.glitchAlpha = Math.max(0, 0.5 - progress * 0.45);
      result.scanPhase = progress;
    }
    return result;
  }

  function pause(at = now()) {
    if (pausedAt === null) pausedAt = at;
  }

  function resume(at = now()) {
    if (pausedAt === null) return;
    if (timeline) timeline.startedAt += Math.max(0, at - pausedAt);
    pausedAt = null;
  }

  function reset() {
    timeline = null;
    pausedAt = null;
  }

  return { startAction, startAnomaly, sample, pause, resume, reset };
}
