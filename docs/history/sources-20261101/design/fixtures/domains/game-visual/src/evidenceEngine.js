const CORE_FIELDS = Object.freeze(['floor', 'passengers', 'door']);
const FIELD_LABELS = Object.freeze({ floor: '楼层', passengers: '人数', door: '门状态' });

export function compareCoreEvidence(screenData = {}, panelData = {}) {
  return CORE_FIELDS
    .filter(field => screenData[field] !== panelData[field])
    .map(field => ({ field, screen: screenData[field], panel: panelData[field] }));
}

export function evaluateEvidence({ screenData = {}, panelData = {}, protocolResult = null } = {}) {
  const conflicts = compareCoreEvidence(screenData, panelData);
  if (protocolResult?.violated) {
    conflicts.push({ field: 'protocol', screen: protocolResult.observed, panel: protocolResult.expected });
  }
  const decision = conflicts.length ? 'lockdown' : 'release';
  const explanation = conflicts.length
    ? conflicts.map(item => `${FIELD_LABELS[item.field] || '协议'}不一致`).join('；')
    : '画面与主控数据一致。';
  return {
    decision,
    conflicts,
    explanation,
    presentationTone: 'neutral',
    highlightConflictBeforeDecision: false,
  };
}

export function evaluateInvestigationEvidence(discoveredEvidence = []) {
  const contradictions = discoveredEvidence.filter(item => item?.contradicts && item?.conflictKey && item?.source);
  const groups = new Map();
  for (const evidence of contradictions) {
    const sources = groups.get(evidence.conflictKey) || new Set();
    sources.add(evidence.source);
    groups.set(evidence.conflictKey, sources);
  }
  const corroborated = [...groups.entries()].filter(([, sources]) => sources.size >= 2);
  const verificationPaths = [...new Set(
    corroborated.flatMap(([, sources]) => [...sources]),
  )].sort();
  const ready = corroborated.length > 0;
  return {
    ready,
    decision: ready ? 'lockdown' : null,
    conflicts: corroborated.map(([conflictKey]) => conflictKey),
    verificationPaths,
    presentationTone: 'neutral',
  };
}

export function isEvidenceJudgeableWithoutAudio(shift = {}) {
  const conflicts = compareCoreEvidence(shift.screenData, shift.panelData);
  const cameras = shift.evidence?.cameras || [];
  const tools = shift.evidence?.tools || [];
  return conflicts.length > 0 || cameras.length > 0 || tools.some(tool => tool !== 'audio');
}
