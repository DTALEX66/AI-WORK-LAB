import { appendLog, checkFailure, clamp, cloneState } from './state.js';
import { t } from './skinManager.js';

export function openInspection(state, options) {
  const duration = Math.max(3, Math.floor(options.duration ?? 7));
  let next = cloneState(state);
  next.inspection = {
    id: options.id,
    kind: options.kind === 'anomaly' ? 'anomaly' : 'normal',
    title: options.title,
    openedAt: next.elapsed ?? 0,
    expiresAt: (next.elapsed ?? 0) + duration,
    status: 'pending',
    choice: null,
  };
  next.lastFeedback = t('ui.inspectionReady');
  next = appendLog(next, 'info', t('ui.inspectionPrompt', {
    title: options.title,
    seconds: duration,
  }));
  return next;
}

export function submitInspection(state, choice) {
  const inspection = state.inspection;
  if (!inspection || inspection.status !== 'pending') {
    return { state, accepted: false, correct: false };
  }

  let next = cloneState(state);
  const normalizedChoice = choice === 'anomaly' ? 'anomaly' : 'normal';
  const correct = normalizedChoice === inspection.kind;
  const tutorialStep = Number(next.tutorialStep || 0);
  const guidedRound = (tutorialStep === 0 && inspection.kind === 'normal')
    || (tutorialStep === 1 && inspection.kind === 'anomaly');

  // 首两轮用实际操作教学：点错不扣资源、不结束题目，直接在原画面上纠正。
  if (guidedRound && !correct) {
    next.lastFeedback = t('ui.wrongTutorial');
    next = appendLog(next, 'info', next.lastFeedback);
    return { state: next, accepted: false, correct: false, coached: true };
  }

  next.inspection = {
    ...inspection,
    status: 'resolved',
    choice: normalizedChoice,
    correct,
    resolvedAt: next.elapsed ?? 0,
  };
  next.decisionsCorrect = (next.decisionsCorrect ?? 0) + (correct ? 1 : 0);
  next.decisionsWrong = (next.decisionsWrong ?? 0) + (correct ? 0 : 1);

  if (correct) {
    const secondsLeft = Math.max(0, Math.ceil((inspection.expiresAt ?? next.elapsed ?? 0) - (next.elapsed ?? 0)));
    const points = 100 + secondsLeft * 10;
    next.score = (next.score ?? 0) + points;
    next.streak = (next.streak ?? 0) + 1;
    next.bestStreak = Math.max(next.bestStreak ?? 0, next.streak);
    if (guidedRound) next.tutorialStep = Math.min(2, tutorialStep + 1);
    next.stability = clamp((next.stability ?? 0) + 4, 0, 100);
    if (inspection.kind === 'anomaly') {
      next.anomalyLevel = clamp((next.anomalyLevel ?? 0) - 1, 0, 6);
    }
    next.lastFeedback = t(
      inspection.kind === 'anomaly' ? 'ui.inspectionCorrectAnomaly' : 'ui.inspectionCorrectNormal',
    );
    next = appendLog(next, 'success', next.lastFeedback);
  } else {
    next.streak = 0;
    next.stability = clamp((next.stability ?? 0) - 12, 0, 100);
    next.anomalyLevel = clamp((next.anomalyLevel ?? 0) + 1, 0, 6);
    next.lastFeedback = t('ui.inspectionWrong');
    next = appendLog(next, 'danger', next.lastFeedback);
  }

  if (tutorialStep === 3) next.tutorialStep = 4;
  return { state: checkFailure(next), accepted: true, correct };
}

export function expireInspection(state) {
  if (state.gameOver) return { state, timedOut: false };
  const inspection = state.inspection;
  if (!inspection || inspection.status !== 'pending' || (state.elapsed ?? 0) < inspection.expiresAt) {
    return { state, timedOut: false };
  }

  let next = cloneState(state);
  const tutorialStep = Number(next.tutorialStep || 0);
  const guidedTimeout = (tutorialStep === 0 && inspection.kind === 'normal')
    || (tutorialStep === 1 && inspection.kind === 'anomaly');
  next.inspection = {
    ...inspection,
    status: 'expired',
    choice: null,
    correct: false,
    resolvedAt: next.elapsed ?? 0,
  };
  if (guidedTimeout) {
    next.tutorialStep = tutorialStep + 1;
    next.lastFeedback = t('ui.wrongTutorial');
    next = appendLog(next, 'info', next.lastFeedback);
    return { state: next, timedOut: true, coached: true };
  }
  next.decisionsWrong = (next.decisionsWrong ?? 0) + 1;
  next.streak = 0;
  next.stability = clamp((next.stability ?? 0) - 8, 0, 100);
  if (Number(next.tutorialStep || 0) === 3) next.tutorialStep = 4;
  next.lastFeedback = t('ui.inspectionTimeout');
  next = appendLog(next, 'warn', next.lastFeedback);
  return { state: checkFailure(next), timedOut: true };
}
