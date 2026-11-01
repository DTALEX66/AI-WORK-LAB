function compare(value, operator, expected) {
  if (operator === 'equals') return value === expected;
  if (operator === 'lte') return Number(value) <= Number(expected);
  if (operator === 'gte') return Number(value) >= Number(expected);
  if (operator === 'truthy') return Boolean(value);
  return false;
}

export function protocolAppliesToShift(protocol, shift = {}) {
  const tags = new Set(shift.protocolTags || []);
  return (protocol.protocolTags || []).some(tag => tags.has(tag));
}

export function evaluateProtocolDecision(protocol, shift = {}) {
  const condition = protocol?.condition || {};
  const observed = shift.screenData?.[condition.field]
    ?? shift.panelData?.[condition.field]
    ?? shift.evidence?.[condition.field];
  const matched = compare(observed, condition.operator, condition.value);
  const violated = protocol?.decision === 'lockdown' ? matched : !matched;
  return {
    violated,
    decision: violated ? 'lockdown' : 'release',
    observed,
    expected: condition.value,
    verificationPaths: [...(protocol?.verificationPaths || [])],
  };
}

export function evaluateNightProtocolSet(protocols = [], shift = {}) {
  const applied = protocols.filter(protocol => protocolAppliesToShift(protocol, shift));
  const results = applied.map(protocol => ({ protocol, result: evaluateProtocolDecision(protocol, shift) }));
  const violated = results.filter(item => item.result.violated);
  return {
    decision: violated.length ? 'lockdown' : 'release',
    appliedProtocolIds: applied.map(protocol => protocol.id),
    violatedProtocolIds: violated.map(item => item.protocol.id),
    verificationPaths: [...new Set(results.flatMap(item => item.result.verificationPaths))].sort(),
  };
}

export function generateNightProtocols({ protocols = [], shifts = [], count = 2, random = Math.random } = {}) {
  const target = Math.max(2, Math.min(3, Math.trunc(count || 2)));
  const applicable = protocols.filter(protocol => shifts.some(shift => protocolAppliesToShift(protocol, shift)));
  const selected = [];
  if (applicable.length) selected.push(applicable[Math.floor(random() * applicable.length) % applicable.length]);
  const remaining = protocols.filter(protocol => !selected.some(item => item.id === protocol.id));
  while (selected.length < target && remaining.length) {
    const index = Math.floor(random() * remaining.length) % remaining.length;
    selected.push(remaining.splice(index, 1)[0]);
  }
  return selected;
}
