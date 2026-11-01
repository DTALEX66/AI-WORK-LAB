function timelineItem(type, entry) {
  return { type, ...entry, sequence: Number(entry.sequence || 0) };
}

export function buildDebriefTimeline({ decisions = [], eventHistory = [], contaminationHistory = [] } = {}) {
  const timeline = [
    ...decisions.map(entry => timelineItem('decision', entry)),
    ...eventHistory.map(entry => timelineItem('event-chain', entry)),
    ...contaminationHistory.map(entry => timelineItem('contamination', entry)),
  ].sort((a, b) => a.sequence - b.sequence);
  const correct = decisions.filter(item => item.correct).length;
  const wrong = decisions.length - correct;
  const peakContamination = contaminationHistory.reduce(
    (peak, item) => Math.max(peak, Number(item.value || 0)),
    0,
  );
  return {
    timeline,
    summary: {
      decisions: decisions.length,
      correct,
      wrong,
      accuracy: decisions.length ? correct / decisions.length : 0,
      peakContamination,
      eventStages: eventHistory.length,
    },
  };
}

function matchesEnding(ending, result) {
  const condition = ending.condition || ending.conditions || {};
  if (condition.requiredFlag && !(result.flags || []).includes(condition.requiredFlag)) return false;
  if (condition.minContamination != null && result.contamination < condition.minContamination) return false;
  if (condition.maxContamination != null && result.contamination > condition.maxContamination) return false;
  if (condition.minAccuracy != null && result.accuracy < condition.minAccuracy) return false;
  if (condition.maxAccuracy != null && result.accuracy > condition.maxAccuracy) return false;
  return true;
}

export function selectNightEnding(endings = [], result = {}) {
  return [...endings]
    .filter(ending => matchesEnding(ending, result))
    .sort((a, b) => Number(b.priority || 0) - Number(a.priority || 0) || a.id.localeCompare(b.id))[0] ?? null;
}
