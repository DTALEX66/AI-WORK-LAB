function clamp(value, min = 0, max = 100) {
  return Math.max(min, Math.min(max, Number(value) || 0));
}

export function getContaminationTier(value) {
  const normalized = clamp(value);
  if (normalized >= 76) return 'severe';
  if (normalized >= 51) return 'medium';
  if (normalized >= 26) return 'light';
  return 'normal';
}

export function createContaminationState(value = 0) {
  const normalized = clamp(value);
  return { value: normalized, tier: getContaminationTier(normalized), history: [] };
}

export function changeContamination(state, delta, reason) {
  const current = state || createContaminationState();
  const value = clamp(current.value + Number(delta || 0));
  return {
    value,
    tier: getContaminationTier(value),
    history: [...(current.history || []), { delta: Number(delta || 0), reason, value }],
  };
}

export function applyDecisionContamination(state, decision = {}) {
  const effects = decision.contaminationEffects || {};
  const delta = decision.correct === false
    ? Number(effects.onMiss || 0)
    : Number(effects.onCorrect || 0);
  return changeContamination(state, delta, {
    type: decision.correct === false ? 'wrong-decision' : 'correct-decision',
    contentId: decision.contentId ?? null,
  });
}

export function deriveContaminationEffects(value) {
  const tier = getContaminationTier(value);
  const reliability = {
    normal: {
      reliable: ['panel', 'cam01', 'cam03', 'cam07', 'thermal', 'replay'],
      unreliable: [],
    },
    light: {
      reliable: ['panel', 'cam01', 'cam03', 'thermal', 'replay'],
      unreliable: ['cam07'],
    },
    medium: {
      reliable: ['cam01', 'thermal', 'replay'],
      unreliable: ['panel', 'cam07'],
    },
    severe: {
      reliable: ['thermal', 'replay'],
      unreliable: ['panel', 'cam01', 'cam03', 'cam07'],
    },
  }[tier];
  const effects = {
    tier,
    chromaticAberration: tier === 'normal' ? 0 : tier === 'light' ? 0.08 : tier === 'medium' ? 0.16 : 0.24,
    timecodeJitter: tier === 'medium' || tier === 'severe',
    edgeGhosting: tier !== 'normal',
    protocolGlyphDropout: tier === 'severe',
    audioDropout: tier === 'medium' || tier === 'severe',
    reliableVerificationPaths: reliability.reliable,
    unreliableVerificationPaths: reliability.unreliable,
  };
  return effects;
}
