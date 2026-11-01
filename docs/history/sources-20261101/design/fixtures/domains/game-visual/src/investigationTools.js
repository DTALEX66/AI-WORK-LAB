const TOOL_CONFIG = Object.freeze({
  thermal: Object.freeze({ uses: 2, powerCost: 8, evidenceKey: 'thermal' }),
  replay: Object.freeze({ uses: 2, powerCost: 4, evidenceKey: 'replay' }),
  protocol: Object.freeze({ uses: Number.POSITIVE_INFINITY, powerCost: 0, evidenceKey: 'protocol' }),
});

function cloneInvestigationState(state) {
  return {
    ...state,
    tools: Object.fromEntries(
      Object.entries(state.tools || {}).map(([id, tool]) => [id, { ...tool }]),
    ),
    discoveredEvidence: [...(state.discoveredEvidence || [])],
  };
}

export function createInvestigationState({ power = 100 } = {}) {
  return {
    power: Math.max(0, Number(power) || 0),
    activeCamera: 'cam01',
    tools: Object.fromEntries(
      Object.entries(TOOL_CONFIG).map(([id, config]) => [id, {
        remaining: config.uses,
        powerCost: config.powerCost,
      }]),
    ),
    discoveredEvidence: [],
  };
}

export function switchCamera(state, cameraId, shift = {}) {
  if (!(shift.cameras || []).includes(cameraId)) {
    return { state, accepted: false, reason: 'camera-unavailable', visibleEvidence: [] };
  }
  const next = cloneInvestigationState(state);
  next.activeCamera = cameraId;
  const visibleEvidence = [...(shift.evidence?.cameras?.[cameraId] || [])];
  for (const evidence of visibleEvidence) {
    if (!next.discoveredEvidence.some(item => item.id === evidence.id)) next.discoveredEvidence.push(evidence);
  }
  return { state: next, accepted: true, visibleEvidence };
}

export function useInvestigationTool(state, toolId, shift = {}) {
  const config = TOOL_CONFIG[toolId];
  const currentTool = state?.tools?.[toolId];
  if (!config || !currentTool) return { state, accepted: false, reason: 'unknown-tool' };
  if (currentTool.remaining <= 0) return { state, accepted: false, reason: 'no-uses' };
  if ((state.power ?? 0) < config.powerCost) return { state, accepted: false, reason: 'insufficient-power' };

  const next = cloneInvestigationState(state);
  next.power = Math.max(0, next.power - config.powerCost);
  if (Number.isFinite(next.tools[toolId].remaining)) next.tools[toolId].remaining -= 1;
  const discoveredEvidence = toolId === 'protocol'
    ? [...(shift.activeProtocols || [])]
    : shift.evidence?.[config.evidenceKey] ?? null;
  const evidenceItems = Array.isArray(discoveredEvidence)
    ? discoveredEvidence
    : discoveredEvidence ? [discoveredEvidence] : [];
  for (const evidence of evidenceItems) {
    if (!next.discoveredEvidence.some(item => item.id === evidence.id)) next.discoveredEvidence.push(evidence);
  }
  return { state: next, accepted: true, discoveredEvidence };
}
