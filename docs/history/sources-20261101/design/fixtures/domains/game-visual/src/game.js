import { getAvailableActions, performAction } from './actions.js';
import { applyAnomaly, pickNextAnomaly } from './events.js';
import { summarizeFailure } from './feedback.js';
import { recordFailure, recordSuccessfulShift, revive, saveSnapshot, tickState } from './state.js';
import CONFIG from './gameConfig.js';
import { playClick, playSuccess, playFail, playAnomaly, playWarning, playCrash, playRevive, playRestart, setMusicState, pauseMusic, resumeMusic, stopMusic } from './audio.js';
import { t, actionLabel, getSkin, getAnomalies } from './skinManager.js';
import { createRewardedAd } from '../platform/platform.js';
import { getDecodedMonitorText, getDirectionLabel, getDomLabels, getDoorLabel } from './uiLabels.js';
import { loadArchive, commitSessionToArchive, getArchiveSkinProgress } from './archive.js';
import { trackEvent } from './analytics.js';
import {
  createRuntimeSession,
  restartRuntimeSession,
  scheduleNextAnomalyAfterRevive,
  scheduleNextAnomalyAfterTrigger,
} from './runtimeSession.js';
import { deriveVisualState } from './visualState.js';
import { getOperatorCue } from './firstRunGuidance.js';
import { shouldApplyReward } from './rewardGuard.js';

const root = document.querySelector('.console-shell');
const debugMode = new URLSearchParams(window.location.search).get('debug') === '1';
const els = {
  remaining: document.querySelector('#remaining'),
  floor: document.querySelector('#floor'),
  door: document.querySelector('#door'),
  direction: document.querySelector('#direction'),
  passengers: document.querySelector('#passengers'),
  power: document.querySelector('#power'),
  powerText: document.querySelector('#powerText'),
  stability: document.querySelector('#stability'),
  stabilityText: document.querySelector('#stabilityText'),
  anomalyLevel: document.querySelector('#anomalyLevel'),
  reviveCount: document.querySelector('#reviveCount'),
  adHintsCount: document.querySelector('#adHintsCount'),
  hiddenLogsCount: document.querySelector('#hiddenLogsCount'),
  fakeEndingOverlay: document.querySelector('#fakeEndingOverlay'),
  fakeEndingEyebrow: document.querySelector('#fakeEndingEyebrow'),
  fakeEndingTitle: document.querySelector('#fakeEndingTitle'),
  fakeEndingText: document.querySelector('#fakeEndingText'),
  fakeEndingTruth: document.querySelector('#fakeEndingTruth'),
  fakeEndingTruthBtn: document.querySelector('#fakeEndingTruthBtn'),
  fakeEndingRestartBtn: document.querySelector('#fakeEndingRestartBtn'),
  monitor: document.querySelector('#monitor'),
  monitorCaption: document.querySelector('#monitorCaption'),
  monitorFloor: document.querySelector('#monitorFloor'),
  monitorSignal: document.querySelector('#monitorSignal'),
  operatorCue: document.querySelector('#operatorCue'),
  monitorThreat: document.querySelector('#monitorThreat'),
  actions: document.querySelector('#actions'),
  moreActions: document.querySelector('#moreActions'),
  secondaryActionCount: document.querySelector('#secondaryActionCount'),
  secondaryActionsSheet: document.querySelector('#secondaryActionsSheet'),
  secondaryActionsBackdrop: document.querySelector('#secondaryActionsBackdrop'),
  closeSecondaryActions: document.querySelector('#closeSecondaryActions'),
  secondaryActions: document.querySelector('#secondaryActions'),
  logs: document.querySelector('#logs'),
  forceAnomaly: document.querySelector('#forceAnomaly'),
  startOverlay: document.querySelector('#startOverlay'),
  startTitle: document.querySelector('#startTitle'),
  startCopy: document.querySelector('#startCopy'),
  startChecklist: document.querySelector('#startChecklist'),
  startFailureRules: document.querySelector('#startFailureRules'),
  startButton: document.querySelector('#startButton'),
  openArchiveBtn: document.querySelector('#openArchiveBtn'),
  archiveOverlay: document.querySelector('#archiveOverlay'),
  archiveStats: document.querySelector('#archiveStats'),
  archiveAnomalyList: document.querySelector('#archiveAnomalyList'),
  closeArchiveBtn: document.querySelector('#closeArchiveBtn'),
  overlay: document.querySelector('#failureOverlay'),
  failureReason: document.querySelector('#failureReason'),
  failureMetrics: document.querySelector('#failureMetrics'),
  postRunSummary: document.querySelector('#postRunSummary'),
  adHint: document.querySelector('#adHint'),
  reviveButton: document.querySelector('#reviveButton'),
  restartButton: document.querySelector('#restartButton'),
  remainingLabel: document.querySelector('#remainingLabel'),
  statusPanelTitle: document.querySelector('#statusPanelTitle'),
  monitorPanelTitle: document.querySelector('#monitorPanelTitle'),
  actionPanelTitle: document.querySelector('#actionPanelTitle'),
  logPanelTitle: document.querySelector('#logPanelTitle'),
  failureTitle: document.querySelector('#failureTitle'),
  floorLabel: document.querySelector('#floorLabel'),
  doorLabel: document.querySelector('#doorLabel'),
  directionLabel: document.querySelector('#directionLabel'),
  passengersLabel: document.querySelector('#passengersLabel'),
  powerLabel: document.querySelector('#powerLabel'),
  stabilityLabel: document.querySelector('#stabilityLabel'),
  anomalyLevelLabel: document.querySelector('#anomalyLevelLabel'),
  reviveCountLabel: document.querySelector('#reviveCountLabel'),
  adHintsCountLabel: document.querySelector('#adHintsCountLabel'),
  hiddenLogsCountLabel: document.querySelector('#hiddenLogsCountLabel'),
};

let session = createRuntimeSession();
let state = session.state;
let nextAnomalyAt = session.nextAnomalyAt;
let timer = null;
let lastTone = 'normal';
let crashPlayed = false;
let fakeEndingTracked = false;
let runToken = 0;
let musicStarted = false;

function analyticsPayload(extra = {}) {
  return {
    skinId: getSkin().meta?.id,
    elapsed: state.elapsed,
    remaining: state.remaining,
    anomalyLevel: state.anomalyLevel,
    ...extra,
  };
}

function ensureTimer() {
  if (timer) return;
  if (els.startOverlay) els.startOverlay.hidden = true;
  timer = window.setInterval(loop, 1000);
  trackEvent('game_start', analyticsPayload());
}

function bindPress(element, handler) {
  if (!element) return;
  let handledAt = 0;
  const run = (event) => {
    event?.preventDefault?.();
    const now = Date.now();
    if (now - handledAt < 350) return;
    handledAt = now;
    handler(event);
  };
  element.addEventListener('click', run);
  element.addEventListener('touchend', run, { passive: false });
  element.addEventListener('pointerup', run);
}

const showReviveAd = createRewardedAd('revive', {
  onReward: (meta) => {
    if (!shouldApplyReward(meta, runToken, 'revive', state)) return;
    trackEvent('revive_reward', analyticsPayload({}));
    playRevive();
    state = revive(state);
    nextAnomalyAt = scheduleNextAnomalyAfterRevive(state.elapsed);
    render();
  },
});
const showDecodeAd = createRewardedAd('decode', {
  onReward: (meta) => {
    if (!shouldApplyReward(meta, runToken, 'decode', state)) return;
    const before = state.adHintsUsed;
    runAction('unlockHiddenLog');
    if (state.adHintsUsed > before) {
      trackEvent('hidden_log_unlock', analyticsPayload({}));
    }
  },
});
const showTruthAd = createRewardedAd('truth', {
  onReward: (meta) => {
    if (!shouldApplyReward(meta, runToken, 'truth', state)) return;
    playRevive();
    state = structuredClone(state);
    state.fakeEndingUnlocked = true;
    render();
  },
});

const ACTION_ICONS = {
  openDoor: '◀▯▶',
  closeDoor: '▶▯◀',
  moveUp: '▲',
  moveDown: '▼',
  emergencyStop: 'STOP',
  restartSystem: '↻',
  inspectLog: 'LOG',
  unlockHiddenLog: 'KEY',
};

const ACTION_SHORT_LABELS = {
  openDoor: '开门',
  closeDoor: '关门',
  moveUp: '上行',
  moveDown: '下行',
  emergencyStop: '急停',
  restartSystem: '重启',
  inspectLog: '日志',
  unlockHiddenLog: '解码',
};

const PRIMARY_ACTION_IDS = new Set(['closeDoor', 'moveUp', 'emergencyStop']);

function isPrimaryAction(actionId) {
  return PRIMARY_ACTION_IDS.has(actionId);
}

function closeSecondaryActions() {
  if (!els.secondaryActionsSheet) return;
  els.secondaryActionsSheet.hidden = true;
  if (els.moreActions) els.moreActions.setAttribute('aria-expanded', 'false');
}

function openSecondaryActions() {
  if (!els.secondaryActionsSheet) return;
  els.secondaryActionsSheet.hidden = false;
  if (els.moreActions) els.moreActions.setAttribute('aria-expanded', 'true');
}

function createActionButton(action, lockedCount, visual) {
  const button = document.createElement('button');
  button.type = 'button';
  button.dataset.action = action.id;
  button.dataset.recommended = String(visual.highlightAction === action.id);
  const keycap = document.createElement('span');
  keycap.className = 'action-keycap';
  const icon = document.createElement('span');
  icon.className = 'action-icon';
  icon.setAttribute('aria-hidden', 'true');
  icon.textContent = ACTION_ICONS[action.id] || '●';
  const label = document.createElement('span');
  label.className = 'action-label';
  label.textContent = ACTION_SHORT_LABELS[action.id] || (action.id === 'unlockHiddenLog'
    ? actionLabel(action.id, lockedCount)
    : action.label);
  button.setAttribute('aria-label', action.id === 'unlockHiddenLog'
    ? actionLabel(action.id, lockedCount)
    : action.label);
  keycap.append(icon, label);
  button.append(keycap);
  bindPress(button, () => dispatchAction(action.id));
  return button;
}

function renderActions(visual = deriveVisualState(state)) {
  els.actions.replaceChildren();
  els.secondaryActions?.replaceChildren();
  const lockedCount = state.hiddenLogs.filter(h => h.locked).length;
  let secondaryCount = 0;
  let secondaryRecommended = false;
  for (const action of getAvailableActions()) {
    // 解码加密记录按钮只在有锁定日志时显示
    if (action.id === 'unlockHiddenLog' && lockedCount === 0) continue;
    const button = createActionButton(action, lockedCount, visual);
    if (isPrimaryAction(action.id) || !els.secondaryActions) {
      els.actions.append(button);
    } else {
      secondaryCount += 1;
      if (visual.highlightAction === action.id) secondaryRecommended = true;
      els.secondaryActions.append(button);
    }
  }
  if (els.secondaryActionCount) els.secondaryActionCount.textContent = String(secondaryCount);
  if (els.moreActions) {
    els.moreActions.hidden = secondaryCount === 0;
    els.moreActions.dataset.recommended = String(secondaryRecommended);
    if (secondaryCount === 0) closeSecondaryActions();
  }
}

function render() {
  const labels = getDomLabels();
  const visual = deriveVisualState(state);
  if (musicStarted) {
    if (state.gameOver) stopMusic();
    else setMusicState(state.activeAnomaly ? 'pressure' : 'calm');
  }
  renderActions(visual);
  root.dataset.tone = visual.tone;
  els.remaining.textContent = Math.ceil(state.remaining);
  els.floor.textContent = state.floor;
  els.door.textContent = getDoorLabel(state.door);
  els.direction.textContent = getDirectionLabel(state.direction);
  els.passengers.textContent = state.passengers;
  els.power.value = state.power;
  els.powerText.textContent = Math.round(state.power);
  els.stability.value = state.stability;
  els.stabilityText.textContent = Math.round(state.stability);
  els.anomalyLevel.textContent = state.anomalyLevel;
  els.reviveCount.textContent = state.adRevivesUsed;

  // 隐藏日志统计
  const lockedCount = state.hiddenLogs.filter(h => h.locked).length;
  const unlockedCount = state.hiddenLogs.filter(h => !h.locked).length;
  if (els.hiddenLogsCount) els.hiddenLogsCount.textContent = lockedCount;
  if (els.adHintsCount) els.adHintsCount.textContent = state.adHintsUsed;
  const tone = visual.tone;
  if (els.monitorSignal) {
    const signal = tone === 'danger' || tone === 'critical'
      ? labels.monitorSignal.corrupted
      : state.anomalyLevel > 0 || tone === 'warn'
        ? labels.monitorSignal.unstable
        : labels.monitorSignal.stable;
    els.monitorSignal.textContent = signal;
  }
  if (els.monitorThreat) els.monitorThreat.textContent = labels.monitorThreat(state.anomalyLevel);
  if (els.operatorCue) {
    const recommendedLabel = visual.highlightAction ? (ACTION_SHORT_LABELS[visual.highlightAction] || actionLabel(visual.highlightAction)) : null;
    els.operatorCue.textContent = getOperatorCue(state, nextAnomalyAt, recommendedLabel);
  }
  // 显示已解锁的隐藏日志内容
  const unlockedHidden = state.hiddenLogs.filter(h => !h.locked);
  const monitorText = unlockedHidden.length > 0
    ? getDecodedMonitorText(unlockedHidden[unlockedHidden.length - 1])
    : state.monitor;
  if (els.monitorCaption) els.monitorCaption.textContent = monitorText;
  else els.monitor.textContent = monitorText;
  if (els.monitorFloor) els.monitorFloor.textContent = state.floor;
  if (els.monitor) {
    els.monitor.dataset.door = state.door;
    els.monitor.dataset.moving = String(state.moving);
    els.monitor.dataset.anomaly = visual.glitch ? 'active' : 'clear';
    els.monitor.dataset.glitch = String(visual.glitch);
    els.monitor.dataset.shake = String(visual.shake);
    els.monitor.dataset.cctvState = visual.cctvState;
    els.monitor.style.setProperty('--cctv-noise', String(visual.noise));
    els.monitor.dataset.passengers = state.passengers > 0 ? 'present' : 'missing';
  }

  els.logs.replaceChildren();
  for (const line of state.logs.slice(-CONFIG.logs.displayLines)) {
    const li = document.createElement('li');
    li.className = [line.type, line.priority ? `log-priority-${line.priority}` : 'log-priority-normal'].join(' ');
    li.textContent = line.text;
    els.logs.append(li);
  }
  els.logs.scrollTop = els.logs.scrollHeight;

  if (state.gameOver) {
    const isSuccess = state.result === 'success';
    if (!isSuccess && state.fakeEndingTriggered) {
      // 假结局
      els.overlay.hidden = true;
      els.fakeEndingOverlay.hidden = false;
      const threshold = CONFIG.fakeEnding.consecutiveFailuresThreshold;
      els.fakeEndingText.textContent = t('fakeEnding.text', {
        count: state.fakeEndingCount || CONFIG.fakeEnding.consecutiveFailuresThreshold,
        threshold: threshold,
      });
      if (state.fakeEndingUnlocked) {
        els.fakeEndingTruth.textContent = t('fakeEnding.truthContent');
        els.fakeEndingTruthBtn.hidden = true;
      } else {
        els.fakeEndingTruth.textContent = t('fakeEnding.truthPlaceholder');
        els.fakeEndingTruthBtn.hidden = false;
      }
    } else {
      // 正常失败
      els.fakeEndingOverlay.hidden = true;
      els.overlay.hidden = false;
      els.overlay.dataset.result = isSuccess ? 'success' : 'failure';
      els.failureTitle.textContent = isSuccess ? t('ui.shiftComplete') : labels.failureTitle;
      els.failureReason.textContent = isSuccess ? t('ui.successfulShift') : summarizeFailure(state);
      els.reviveButton.hidden = isSuccess;
      els.adHint.hidden = isSuccess;
      if (els.failureMetrics) {
        const metrics = labels.failureMetrics.map(({ key, label }) => {
          const value = key === 'remaining' ? Math.ceil(state.remaining) : Math.round(state[key]);
          return [label, value];
        });
        els.failureMetrics.replaceChildren(...metrics.map(([label, value]) => {
          const item = document.createElement('span');
          const labelEl = document.createElement('b');
          const valueEl = document.createElement('strong');
          labelEl.textContent = label;
          valueEl.textContent = value;
          item.append(labelEl, valueEl);
          return item;
        }));
      }
      els.adHint.textContent = state.lastAdHint
        ? t('failure.adHintPrefix', { hint: state.lastAdHint })
        : t('failure.defaultHint');
      // 局后复盘
      if (els.postRunSummary) {
        const unlockedLogs = state.hiddenLogs.filter(h => !h.locked).length;
        const totalAnomalies = state.anomaliesTriggeredTotal || 0;
        const peakSeverity = state.maxAnomalySeverity || 0;
        const severityLabel = peakSeverity >= 4 ? '致命' : peakSeverity >= 2 ? '高' : peakSeverity > 0 ? '低' : '无';
        const items = [
          ['存活秒数', state.elapsed],
          ['触发异常', totalAnomalies],
          ['最高威胁', `${peakSeverity}（${severityLabel}）`],
          ['解锁日志', unlockedLogs],
          ['复活次数', state.adRevivesUsed || 0],
        ];
        if (state.fakeEndingTriggered) items.push(['假结局', '已触发']);
        els.postRunSummary.replaceChildren(...items.map(([label, value]) => {
          const item = document.createElement('span');
          const labelEl = document.createElement('b');
          const valueEl = document.createElement('strong');
          labelEl.textContent = label;
          valueEl.textContent = value;
          item.append(labelEl, valueEl);
          return item;
        }));
      }
    }
  } else {
    els.overlay.hidden = true;
    els.fakeEndingOverlay.hidden = true;
  }
}

function dispatchAction(actionId) {
  ensureTimer();
  playClick();
  closeSecondaryActions();
  trackEvent('action_click', analyticsPayload({ actionId }));
  if (actionId === 'unlockHiddenLog') {
    trackEvent('hidden_log_start', analyticsPayload({}));
    showDecodeAd({ runToken });
    return;
  }
  runAction(actionId);
}

function runAction(actionId) {
  const result = performAction(state, actionId);
  state = result.state;
  if (result.ok) {
    playSuccess();
  } else {
    playFail();
  }
  render();
}

function triggerAnomaly() {
  if (state.gameOver) return;
  ensureTimer();
  const picked = pickNextAnomaly(state);
  const result = applyAnomaly(state, picked.id);
  state = result.state;
  trackEvent('anomaly_trigger', analyticsPayload({
    anomalyId: result.event.id,
    severity: result.event.severity,
  }));
  playAnomaly();
  nextAnomalyAt = scheduleNextAnomalyAfterTrigger(state.elapsed);
  render();
}

function loop() {
  if (state.gameOver) {
    if (!crashPlayed) {
      const isSuccess = state.result === 'success';
      if (isSuccess) playSuccess();
      else playCrash();
      crashPlayed = true;
      trackEvent('game_over', analyticsPayload({
        result: state.result,
        reason: isSuccess ? 'shift_complete' : summarizeFailure(state),
        anomaliesTriggeredTotal: state.anomaliesTriggeredTotal || 0,
        maxAnomalySeverity: state.maxAnomalySeverity || 0,
      }));
      // 提交本局数据到跨局档案库
      try {
        const ids = state.hiddenLogs?.map(h => h.id?.replace(/_log$/, '')).filter(Boolean) || [];
        const unlockedIds = state.hiddenLogs?.filter(h => !h.locked).map(h => h.id) || [];
        commitSessionToArchive({
          skinId: getSkin().meta?.id,
          anomaliesTriggeredTotal: state.anomaliesTriggeredTotal || 0,
          maxAnomalySeverity: state.maxAnomalySeverity || 0,
          anomalyIds: ids,
          unlockedLogIds: unlockedIds,
        });
        refreshArchiveButton();
      } catch { /* localStorage unavailable — skip */ }
    }
    render();
    return;
  }
  crashPlayed = false;
  fakeEndingTracked = false;
  state = tickState(state, 1);

  // 成功值守 → 重置连续失败计数
  if (state.gameOver && state.result === 'success') {
    state = recordSuccessfulShift(state);
    render();
    return;
  }

  // 检测失败 → 递增连续失败计数
  if (state.gameOver) {
    state = recordFailure(state);
    if (state.fakeEndingTriggered && !fakeEndingTracked) {
      fakeEndingTracked = true;
      trackEvent('fake_ending_trigger', analyticsPayload({
        fakeEndingCount: state.fakeEndingCount,
      }));
    }
  }
  // Save a snapshot on interval for revive rollback
  const ar = CONFIG.revive;
  if (state.elapsed > 0 && state.elapsed % ar.snapshotInterval === 0) {
    state = saveSnapshot(state);
  }
  if (!state.gameOver && state.elapsed >= nextAnomalyAt) triggerAnomaly();
  // Play warning sound on tone transitions to critical/danger
  const currentTone = deriveVisualState(state).tone;
  if (currentTone === 'danger' || currentTone === 'critical') {
    if (lastTone !== currentTone) playWarning();
  }
  lastTone = currentTone;
  render();
}

function restart() {
  runToken += 1;
  if (timer) {
    window.clearInterval(timer);
    timer = null;
  }
  if (els.startOverlay) els.startOverlay.hidden = false;
  session = restartRuntimeSession({ state });
  state = session.state;
  nextAnomalyAt = session.nextAnomalyAt;
  fakeEndingTracked = false;
  render();
  refreshArchiveButton();
}

function refreshArchiveButton() {
  if (!els.openArchiveBtn) return;
  const archive = loadArchive();
  els.openArchiveBtn.hidden = archive.sessionsPlayed === 0;
}

function renderArchive() {
  const archive = loadArchive();
  const skinProgress = getArchiveSkinProgress(archive, getSkin().meta?.id, getAnomalies());
  if (els.archiveStats) {
    const ids = Object.keys(archive.encounteredAnomalies).length;
    const logs = Object.keys(archive.unlockedLogs).length;
    const items = [
      ['总场次', archive.sessionsPlayed],
      ['遭遇异常', ids],
      ['解锁日志', logs],
      ['总异常数', archive.totalAnomaliesTriggered],
      ['最高威胁', archive.highestSeverity],
      ['皮肤进度', `${skinProgress.encounteredCount}/${skinProgress.totalAnomalies}`],
      ['日志解锁', `${skinProgress.unlockedLogsCount}/${skinProgress.totalAnomalies}`],
    ];
    els.archiveStats.replaceChildren(...items.map(([label, value]) => {
      const item = document.createElement('span');
      const labelEl = document.createElement('b');
      const valueEl = document.createElement('strong');
      labelEl.textContent = label;
      valueEl.textContent = value;
      item.append(labelEl, valueEl);
      return item;
    }));
  }
  if (els.archiveAnomalyList) {
    const anomalies = getAnomalies();
    els.archiveAnomalyList.replaceChildren(...Object.entries(archive.encounteredAnomalies)
      .sort((a, b) => b[1] - a[1])
      .map(([id, count]) => {
        const def = anomalies.find(a => a.id === id);
        const item = document.createElement('div');
        item.className = 'anomaly-entry';
        const name = document.createElement('span');
        name.textContent = def?.title || id;
        const badge = document.createElement('strong');
        badge.textContent = `×${count}`;
        item.append(name, badge);
        return item;
      }));
  }
}

function applyDomLabels() {
  const labels = getDomLabels();
  els.remainingLabel.textContent = labels.countdown;
  els.statusPanelTitle.textContent = labels.statusPanel;
  els.monitorPanelTitle.textContent = labels.monitorPanel;
  els.actionPanelTitle.textContent = labels.actionPanel;
  els.logPanelTitle.textContent = labels.logPanel;
  els.failureTitle.textContent = labels.failureTitle;
  els.forceAnomaly.textContent = 'ANOM';
  els.forceAnomaly.setAttribute('aria-label', labels.forceAnomaly);
  els.forceAnomaly.hidden = !debugMode;
  els.reviveButton.textContent = labels.revive;
  els.restartButton.textContent = labels.restart;
  els.fakeEndingTruthBtn.textContent = labels.revealTruth;
  els.fakeEndingRestartBtn.textContent = labels.restart;
  if (els.fakeEndingEyebrow) els.fakeEndingEyebrow.textContent = t('fakeEnding.eyebrow');
  if (els.fakeEndingTitle) els.fakeEndingTitle.textContent = t('fakeEnding.title');
  if (els.startTitle) els.startTitle.textContent = '接管电梯';
  if (els.startCopy) els.startCopy.textContent = '看监控，按键救场。';
  if (els.startButton) els.startButton.textContent = 'OVERRIDE';
  if (els.startChecklist) {
    const compactMissions = ['60s', 'CCTV', 'CONTROL'];
    els.startChecklist.replaceChildren(...compactMissions.map((item) => {
      const chip = document.createElement('span');
      chip.textContent = item;
      return chip;
    }));
  }
  if (els.startFailureRules) {
    const compactRisks = ['POWER', 'STABILITY', 'ANOMALY'];
    els.startFailureRules.replaceChildren(...compactRisks.map((item) => {
      const chip = document.createElement('span');
      chip.textContent = item;
      return chip;
    }));
  }
  els.floorLabel.textContent = labels.status.floor;
  els.doorLabel.textContent = labels.status.door;
  els.directionLabel.textContent = labels.status.direction;
  els.passengersLabel.textContent = labels.status.passengers;
  els.powerLabel.textContent = labels.status.power;
  els.stabilityLabel.textContent = labels.status.stability;
  els.anomalyLevelLabel.textContent = labels.status.anomalyLevel;
  els.reviveCountLabel.textContent = labels.status.reviveCount;
  els.adHintsCountLabel.textContent = labels.status.adHintsCount;
  els.hiddenLogsCountLabel.textContent = labels.status.hiddenLogsCount;
}

applyDomLabels();
refreshArchiveButton();
bindPress(els.startButton, () => {
  playClick();
  musicStarted = true;
  setMusicState('calm');
  ensureTimer();
});
bindPress(els.forceAnomaly, triggerAnomaly);
bindPress(els.moreActions, openSecondaryActions);
bindPress(els.closeSecondaryActions, closeSecondaryActions);
bindPress(els.secondaryActionsBackdrop, closeSecondaryActions);
window.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeSecondaryActions();
});
bindPress(els.reviveButton, () => {
  trackEvent('revive_start', analyticsPayload({}));
  showReviveAd({ runToken });
});
bindPress(els.restartButton, () => {
  playRestart();
  restart();
});

// 假结局按钮
bindPress(els.fakeEndingTruthBtn, () => {
  showTruthAd({ runToken });
});
bindPress(els.fakeEndingRestartBtn, () => {
  playRestart();
  restart();
});

// 档案库
bindPress(els.openArchiveBtn, () => {
  renderArchive();
  els.archiveOverlay.hidden = false;
});
bindPress(els.closeArchiveBtn, () => {
  els.archiveOverlay.hidden = true;
});

// 从皮肤设置标题和副标题
const meta = getSkin().meta;
if (meta) {
  const titleEl = document.querySelector('#gameTitle');
  const subEl = document.querySelector('#gameSubtitle');
  if (titleEl) titleEl.textContent = meta.name;
  if (subEl) subEl.textContent = meta.subtitle;
  root.dataset.skin = meta.id;
}

render();
document.addEventListener('visibilitychange', () => {
  if (document.hidden) pauseMusic();
  else if (musicStarted && !state.gameOver) resumeMusic();
});
window.addEventListener('beforeunload', () => {
  window.clearInterval(timer);
  stopMusic();
});
