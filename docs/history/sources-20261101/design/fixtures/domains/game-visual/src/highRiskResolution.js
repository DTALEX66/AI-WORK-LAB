const HIGH_RISK_ACTIONS = Object.freeze(['emergencyStop', 'restart', 'lockdownFloor']);

function cloneHighRiskState(state) {
  return {
    ...state,
    resolvedEvents: [...(state.resolvedEvents || [])],
    nextShiftModifiers: [...(state.nextShiftModifiers || [])],
    history: [...(state.history || [])],
  };
}

export function createHighRiskState({ power = 100 } = {}) {
  return {
    power: Math.max(0, Number(power) || 0),
    resolvedEvents: [],
    nextShiftModifiers: [],
    history: [],
    gameOver: false,
  };
}

export function resolveHighRiskAction(state, event = {}, action) {
  if (!HIGH_RISK_ACTIONS.includes(action)) return { state, accepted: false, correct: false, reason: 'unknown-action' };
  const cost = Math.max(0, Number(event.costs?.[action] || 0));
  if ((state.power ?? 0) < cost) return { state, accepted: false, correct: false, reason: 'insufficient-power' };

  const next = cloneHighRiskState(state);
  next.power -= cost;
  const correct = (event.acceptedActions || []).includes(action);
  if (correct && event.id && !next.resolvedEvents.includes(event.id)) next.resolvedEvents.push(event.id);
  const modifier = correct ? event.successModifier : event.wrongModifiers?.[action];
  if (modifier && !next.nextShiftModifiers.includes(modifier)) next.nextShiftModifiers.push(modifier);
  next.history.push({ eventId: event.id ?? null, action, correct, powerCost: cost });
  return { state: next, accepted: true, correct };
}
