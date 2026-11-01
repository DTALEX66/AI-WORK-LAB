import { applyDecisionContamination } from './contamination.js';
import { buildDebriefTimeline, selectNightEnding } from './debriefTimeline.js';
import { createHighRiskState, resolveHighRiskAction } from './highRiskResolution.js';

const CATEGORIES = Object.freeze(['person', 'quantity', 'space', 'time', 'device', 'dynamic']);
const HIGH_RISK_COSTS = Object.freeze({ emergencyStop: 15, restart: 10, lockdownFloor: 12 });

function clone(value) {
  if (Array.isArray(value)) return value.map(clone);
  if (value && typeof value === 'object') {
    return Object.fromEntries(Object.entries(value).map(([key, item]) => [key, clone(item)]));
  }
  return value;
}

function appendDecision(state, decision) {
  const next = clone(state);
  const decisions = next.night.decisions || [];
  const sequence = Number(next.night.timelineSequence || 0) + 1;
  next.night.timelineSequence = sequence;
  decisions.push({ sequence, ...decision });
  next.night.decisions = decisions;
  return next;
}

export function openProtocolQuery(state) {
  const next = clone(state);
  next.night.overlay = 'protocolQuery';
  next.night.protocolQuery = clone(next.night.activeProtocols || []);
  return next;
}

export function closeProtocolQuery(state) {
  const next = clone(state);
  next.night.overlay = null;
  return next;
}

export function verifyCurrentIdentity(state) {
  const shift = state?.night?.currentShift;
  if (!shift || state?.night?.roundType !== 'identity') {
    return { state, accepted: false, reason: 'not-identity-round' };
  }
  const evidence = shift.evidence?.cameras?.cam01?.[0];
  if (!evidence) return { state, accepted: false, reason: 'identity-evidence-missing' };
  const next = clone(state);
  const discovered = next.investigation.discoveredEvidence || [];
  if (!discovered.some(item => item.id === evidence.id)) discovered.push(clone(evidence));
  next.investigation.discoveredEvidence = discovered;
  next.lastFeedback = `核验结果：${evidence.observation}`;
  return { state: next, accepted: true, evidence: clone(evidence) };
}

export function resolveIdentityDecision(state, choice) {
  const shift = state?.night?.currentShift;
  if (!shift || state?.night?.roundType !== 'identity' || !['release', 'reject'].includes(choice)) {
    return { state, accepted: false, correct: false, reason: 'invalid-identity-decision' };
  }
  const expected = shift.decision === 'anomaly' ? 'reject' : 'release';
  const correct = choice === expected;
  let next = appendDecision(state, {
    contentId: shift.id,
    choice: `identity:${choice}`,
    correct,
  });
  next.contamination = applyDecisionContamination(next.contamination, {
    correct,
    contentId: shift.id,
    contaminationEffects: shift.contaminationEffects,
  });
  next.night.roundType = 'quick';
  next.lastFeedback = correct
    ? (choice === 'release' ? '身份一致，准予放行' : '身份冲突，拒绝通行')
    : '身份判断错误，污染已影响后续班次';
  next.gameOver = false;
  return { state: next, accepted: true, correct };
}

export function classifyCurrentShift(state, category) {
  const shift = state?.night?.currentShift;
  if (!shift || !CATEGORIES.includes(category)) {
    return { state, accepted: false, correct: false, reason: 'invalid-classification' };
  }
  const correct = shift.category === category;
  let next = appendDecision(state, {
    contentId: shift.id,
    choice: 'classification',
    classification: category,
    correct,
  });
  next.contamination = applyDecisionContamination(next.contamination, {
    correct,
    contentId: shift.id,
    contaminationEffects: shift.contaminationEffects,
  });
  next.night.overlay = null;
  next.night.roundType = shift.roundType === 'highRisk' || shift.highRisk ? 'highRisk' : 'quick';
  next.lastFeedback = correct ? `分类确认：${category}` : `分类不符：${category}`;
  return { state: next, accepted: true, correct };
}

function acceptedHighRiskAction(shift) {
  if (shift.resolutionAction === 'emergencyStop') return 'emergencyStop';
  if (shift.resolutionAction === 'restart') return 'restart';
  return 'lockdownFloor';
}

export function resolveCurrentHighRisk(state, action) {
  const shift = state?.night?.currentShift;
  if (!shift || state?.night?.roundType !== 'highRisk') {
    return { state, accepted: false, correct: false, reason: 'not-high-risk' };
  }
  const highRisk = createHighRiskState({ power: state.power });
  highRisk.nextShiftModifiers = clone(state.night.nextShiftModifiers || []);
  const result = resolveHighRiskAction(highRisk, {
    id: shift.id,
    acceptedActions: [acceptedHighRiskAction(shift)],
    costs: HIGH_RISK_COSTS,
    successModifier: `resolved:${shift.id}`,
    wrongModifiers: {
      emergencyStop: 'power-grid-stress',
      restart: 'control-reliability-down',
      lockdownFloor: 'camera-delay',
    },
  }, action);
  if (!result.accepted) return { ...result, state };
  let next = appendDecision(state, {
    contentId: shift.id,
    choice: 'highRisk',
    action,
    correct: result.correct,
  });
  next.power = result.state.power;
  next.investigation.power = result.state.power;
  next.night.nextShiftModifiers = result.state.nextShiftModifiers;
  next.night.roundType = 'quick';
  next.lastFeedback = result.correct ? '高危处置完成' : '处置失误已影响后续班次';
  next.gameOver = false;
  return { state: next, accepted: true, correct: result.correct };
}

export function createNightDebrief(state, endings = []) {
  const report = buildDebriefTimeline({
    decisions: state?.night?.decisions || [],
    eventHistory: state?.night?.eventChainHistory || Object.values(state?.night?.eventChains || {}).flatMap(chain => chain.history || []),
    contaminationHistory: state?.contamination?.history || [],
  });
  const eventChainFlags = state?.night?.eventChainFlags || [];
  const nextShiftModifiers = state?.night?.nextShiftModifiers || [];
  return {
    ...report,
    nextShiftModifiers: [...nextShiftModifiers],
    ending: selectNightEnding(endings, {
      flags: eventChainFlags,
      contamination: Number(state?.contamination?.value || 0),
      accuracy: report.summary.accuracy,
    }),
  };
}
