function cloneChainState(state) {
  return {
    chains: Object.fromEntries(Object.entries(state.chains || {}).map(([id, value]) => [id, { ...value }])),
    flags: [...(state.flags || [])],
    history: [...(state.history || [])],
  };
}

export function createEventChainState(chains = []) {
  return {
    chains: Object.fromEntries(chains.map(chain => [chain.id, { stepIndex: 0, completed: false }])),
    flags: [...new Set(chains.flatMap(chain => chain.initialFlags || []))],
    history: [],
  };
}

export function getCurrentEventStep(state, chain) {
  const progress = state?.chains?.[chain.id];
  if (!progress || progress.completed) return null;
  return chain.steps?.[progress.stepIndex] ?? null;
}

export function advanceEventChain(state, chain, outcome = {}) {
  const progress = state?.chains?.[chain.id];
  if (!progress || progress.completed) return { state, accepted: false, completed: Boolean(progress?.completed), consequences: [] };
  const step = chain.steps?.[progress.stepIndex];
  if (!step) return { state, accepted: false, completed: true, consequences: [] };

  const next = cloneChainState(state);
  if (outcome.correct === false) {
    next.flags.push(...(step.onWrongFlags || []));
    next.flags = [...new Set(next.flags)];
  }
  const nextIndex = progress.stepIndex + 1;
  const completed = nextIndex >= chain.steps.length;
  next.chains[chain.id] = { stepIndex: nextIndex, completed };
  next.history.push({ chainId: chain.id, stepId: step.id, correct: outcome.correct !== false });
  const consequences = completed
    ? (chain.consequences || []).filter(item => !item.flag || next.flags.includes(item.flag))
    : [];
  return { state: next, accepted: true, completed, consequences };
}
