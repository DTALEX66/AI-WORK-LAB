import { createInvestigationState } from './investigationTools.js';
import { generateNightProtocols } from './protocolEngine.js';
import { advanceEventChain, createEventChainState } from './eventChainEngine.js';
import { changeContamination } from './contamination.js';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function requireContentList(content, key) {
  const list = content?.[key];
  if (!Array.isArray(list) || list.length === 0) {
    throw new Error(`V5 night scheduler requires non-empty ${key}`);
  }
  return list;
}

function pick(list, random) {
  const value = Number(random());
  const normalized = Number.isFinite(value) ? Math.max(0, Math.min(0.999999999999, value)) : 0;
  return list[Math.floor(normalized * list.length)];
}

const NEXT_SHIFT_MODIFIER_VISUALS = Object.freeze({
  duplicate_feed: '14_duplicate_subject',
  floor_13_bleed: '16_wrong_floor',
  unreliable_cam07: '10_signal_lost',
});

function installShift(state, shift, shiftKind, shiftIndex, activeProtocols, eventMeta = null) {
  const next = clone(state);
  const protocols = clone(activeProtocols);
  const pendingModifiers = [...(next.night.nextShiftModifiers || [])];
  const modifierVisualState = pendingModifiers
    .map(modifier => NEXT_SHIFT_MODIFIER_VISUALS[modifier])
    .find(Boolean);
  next.night.activeProtocols = protocols;
  next.night.currentShift = {
    ...clone(shift),
    ...(modifierVisualState ? { visualState: modifierVisualState } : {}),
    ...(pendingModifiers.length ? { appliedModifiers: pendingModifiers } : {}),
    shiftKind,
    activeProtocols: clone(protocols),
    ...(eventMeta ? {
      eventChainId: eventMeta.chainId,
      eventChainStep: eventMeta.stepId,
    } : {}),
  };
  next.night.nextShiftModifiers = [];
  next.night.roundType = shift.roundType || 'quick';
  next.night.shiftIndex = shiftIndex;
  next.investigation = createInvestigationState({ power: next.power });
  return next;
}

function initialiseEventChains(state, content, random) {
  if (!Array.isArray(content?.eventChains) || content.eventChains.length === 0) return state;
  const next = clone(state);
  const chainState = createEventChainState(content.eventChains);
  next.night.eventChains = chainState.chains;
  next.night.eventChainFlags = chainState.flags;
  next.night.eventChainHistory = chainState.history;
  next.night.activeEventChainId = pick(content.eventChains, random).id;
  return next;
}

function getActiveChainStep(state, content) {
  if (Number(state?.tutorialStep || 0) < 4) return null;
  const chainId = state?.night?.activeEventChainId;
  const chain = content?.eventChains?.find(item => item.id === chainId);
  const progress = state?.night?.eventChains?.[chainId];
  if (!chain || !progress || progress.completed) return null;
  const step = chain.steps?.[progress.stepIndex];
  if (!step) return null;
  const shift = [...(content.normalShifts || []), ...(content.anomalies || [])]
    .find(item => item.id === step.contentId);
  return shift ? { chain, progress, step, shift } : null;
}

export function createNightSchedule(state, content, options = {}) {
  const normalShifts = requireContentList(content, 'normalShifts');
  const anomalies = requireContentList(content, 'anomalies');
  const protocols = requireContentList(content, 'protocols');
  const random = options.random || Math.random;
  const firstShift = pick(normalShifts, random);
  const activeProtocols = generateNightProtocols({
    protocols,
    shifts: [...normalShifts, ...anomalies],
    count: options.protocolCount ?? 3,
    random,
  });
  const scheduled = installShift(state, firstShift, 'normal', 0, activeProtocols);
  return initialiseEventChains(scheduled, content, random);
}

export function scheduleNextNightShift(state, content, options = {}) {
  requireContentList(content, 'normalShifts');
  requireContentList(content, 'anomalies');
  const random = options.random || Math.random;
  const nextIndex = Number(state?.night?.shiftIndex || 0) + 1;
  const activeProtocols = state?.night?.activeProtocols?.length
    ? state.night.activeProtocols
    : requireContentList(content, 'protocols');
  const chainStep = getActiveChainStep(state, content);
  if (chainStep) {
    return installShift(
      state,
      chainStep.shift,
      chainStep.shift.decision === 'anomaly' ? 'anomaly' : 'normal',
      nextIndex,
      activeProtocols,
      { chainId: chainStep.chain.id, stepId: chainStep.step.id },
    );
  }
  const shiftKind = nextIndex % 2 === 0 ? 'normal' : 'anomaly';
  const shift = pick(content[shiftKind === 'normal' ? 'normalShifts' : 'anomalies'], random);
  return installShift(state, shift, shiftKind, nextIndex, activeProtocols);
}

export function advanceCurrentNightEventChain(state, content, outcome) {
  if (Number(state?.tutorialStep || 0) < 4) return { state, advanced: false };
  const chainId = state?.night?.activeEventChainId;
  if (!chainId || !state?.night?.eventChains?.[chainId]) return { state, advanced: false };
  const chain = content?.eventChains?.find(item => item.id === chainId);
  if (!chain) return { state, advanced: false };
  const chainState = {
    chains: state.night.eventChains,
    flags: state.night.eventChainFlags || [],
    history: state.night.eventChainHistory || [],
  };
  const result = advanceEventChain(chainState, chain, outcome);
  const next = clone(state);
  let timelineSequence = Number(next.night.timelineSequence || 0);
  const eventHistory = result.state.history.map(item => {
    if (Number.isFinite(Number(item.sequence))) return item;
    timelineSequence += 1;
    return { ...item, sequence: timelineSequence };
  });
  next.night.timelineSequence = timelineSequence;
  next.night.eventChains = {
    ...next.night.eventChains,
    [chainId]: {
      ...result.state.chains[chainId],
      history: eventHistory.filter(item => item.chainId === chainId),
    },
  };
  next.night.eventChainFlags = result.state.flags;
  next.night.eventChainHistory = eventHistory;
  if (result.completed) next.night.activeEventChainId = null;
  for (const consequence of result.consequences || []) {
    if (Number(consequence.contaminationDelta || 0) !== 0) {
      next.contamination = changeContamination(
        next.contamination,
        Number(consequence.contaminationDelta),
        `event-chain:${chainId}`,
      );
      const history = next.contamination.history || [];
      if (history.length > 0 && !Number.isFinite(Number(history.at(-1).sequence))) {
        next.night.timelineSequence += 1;
        history[history.length - 1] = {
          ...history.at(-1),
          sequence: next.night.timelineSequence,
        };
        next.contamination.history = history;
      }
    }
    if (consequence.nextShiftModifier) {
      next.night.nextShiftModifiers = [
        ...(next.night.nextShiftModifiers || []),
        consequence.nextShiftModifier,
      ];
    }
  }
  return { state: next, advanced: true, completed: Boolean(result.completed), result };
}
