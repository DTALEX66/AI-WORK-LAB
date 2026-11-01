export function getOperatorCue(state, nextAnomalyAt) {
  const elapsed = Math.max(0, Math.floor(state?.elapsed ?? 0));
  const firstAnomalySeen = (state?.anomaliesTriggeredTotal ?? 0) > 0;

  if (state?.gameOver) {
    return '先看本轮结果，再决定复活或重新值守。';
  }

  if (state?.activeAnomaly) {
    return '异常已封锁：系统正在自动处置。';
  }

  if (!firstAnomalySeen) {
    const seconds = Math.max(0, Math.ceil((nextAnomalyAt ?? elapsed) - elapsed));
    return `首班 ${seconds} 秒内到达：三项一致就放行。`;
  }

  return '对得上就放行，对不上就封锁。';
}
