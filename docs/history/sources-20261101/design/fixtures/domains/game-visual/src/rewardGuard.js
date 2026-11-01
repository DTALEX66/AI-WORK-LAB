export function shouldApplyReward(meta, currentRunToken, kind, state) {
  if (meta?.context?.runToken !== currentRunToken || !state) return false;

  if (kind === 'decode') {
    return !state.gameOver && Boolean(state.hiddenLogs?.some(entry => entry.locked));
  }

  if (kind === 'revive') {
    return state.gameOver === true
      && state.result === 'failure'
      && !state.fakeEndingTriggered;
  }

  if (kind === 'truth') {
    return state.gameOver === true
      && state.result === 'failure'
      && state.fakeEndingTriggered === true
      && !state.fakeEndingUnlocked;
  }

  return false;
}
