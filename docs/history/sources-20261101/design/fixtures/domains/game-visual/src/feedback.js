import { findRollbackSnapshot } from './rollback.js';
import { t } from './skinManager.js';

export function classifyFeedbackPriority(type) {
  if (type === 'danger') return 'high';
  if (type === 'success') return 'success';
  if (type === 'warn') return 'medium';
  return 'normal';
}

export function createFeedbackLine(type, message, time = 0) {
  const safeTime = Math.max(0, Math.floor(time));
  const minutes = String(Math.floor(safeTime / 60)).padStart(2, '0');
  const seconds = String(safeTime % 60).padStart(2, '0');
  return {
    type,
    priority: classifyFeedbackPriority(type),
    time: safeTime,
    text: `[${minutes}:${seconds}] ${message}`,
  };
}

export function summarizeFailure(state) {
  const reasons = [];
  const s = state;
  if (s.power <= 0) reasons.push(t('failure.summaries.power'));
  if (s.stability <= 0) reasons.push(t('failure.summaries.stability'));
  if (s.anomalyLevel >= 6) reasons.push(t('failure.summaries.anomalyLevel'));
  if (s.passengers < 0) reasons.push(t('failure.summaries.passengers'));
  if (reasons.length === 0) reasons.push(t('failure.summaries.default'));

  const snapshots = s.snapshots || [];
  let rollbackSec = 0;
  if (snapshots.length > 0) {
    const best = findRollbackSnapshot(snapshots, s.elapsed);
    rollbackSec = s.elapsed - best.at;
  }

  const firstRunAdvice = s.adRevivesUsed === 0 && (s.anomaliesTriggeredTotal ?? 0) <= 1
    ? ` ${t('failure.firstRunAdvice')}`
    : '';

  if (snapshots.length > 0) {
    return `${reasons.join('、')}。${t('failure.snapshotFallback', { seconds: rollbackSec })}${firstRunAdvice}`;
  }
  return `${reasons.join('、')}。${t('failure.noSnapshotFallback')}${firstRunAdvice}`;
}

export function getToneForState(state) {
  if (state.result === 'success') return 'normal';
  if (state.gameOver) return 'danger';
  if (state.anomalyLevel >= 4 || state.stability < 35) return 'critical';
  if (state.anomalyLevel >= 2 || state.power < 45) return 'warn';
  return 'normal';
}
