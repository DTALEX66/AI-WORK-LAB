import { getSkin, t } from './skinManager.js';

export function getDomLabels() {
  const skin = getSkin();
  const status = skin.statusLabels || {};
  const canvas = skin.canvasLabels || {};

  return {
    countdown: canvas.countdown || '值守倒计时',
    statusPanel: status.panelTitle || '电梯状态',
    monitorPanel: canvas.monitorPanel || '监控画面',
    actionPanel: canvas.actionPanel || '操作面板',
    logPanel: canvas.logPanel || '系统日志',
    forceAnomaly: canvas.forceAnomaly || t('ui.triggerTest'),
    failureTitle: canvas.failureTitle || '系统崩溃',
    failureEyebrow: canvas.failureEyebrow || 'SYSTEM FAILURE',
    monitorSignal: {
      stable: canvas.monitorSignalStable || 'SIGNAL: STABLE',
      unstable: canvas.monitorSignalUnstable || 'SIGNAL: UNSTABLE',
      corrupted: canvas.monitorSignalCorrupted || 'SIGNAL: CORRUPTED',
    },
    monitorThreat: (level) => (canvas.monitorThreat || 'THREAT: {level}').replace('{level}', level),
    failureMetrics: [
      { key: 'power', label: status.power || '电源' },
      { key: 'stability', label: canvas.failureMetricStability || status.stability || '稳定度' },
      { key: 'anomalyLevel', label: canvas.failureMetricAnomaly || status.anomalyLevel || '异常' },
      { key: 'remaining', label: canvas.failureMetricRemaining || '剩余' },
    ],
    revive: t('ui.viewAd'),
    restart: t('ui.restart'),
    revealTruth: t('ui.revealTruth'),
    start: {
      title: t('ui.startTitle'),
      copy: t('ui.startCopy'),
      checklist: t('ui.startChecklist').split('\n').filter(Boolean),
      failureRulesTitle: t('ui.startFailureRulesTitle'),
      failureRules: t('ui.startFailureRules').split('\n').filter(Boolean),
      button: t('ui.startButton'),
    },
    status: {
      floor: status.floor || '楼层',
      door: status.door || '门状态',
      direction: status.direction || '方向',
      passengers: status.passengers || '乘客',
      power: status.power || '电源',
      stability: status.stability || '稳定度',
      anomalyLevel: status.anomalyLevel || '异常等级',
      reviveCount: status.reviveCount || '复活',
      adHintsCount: status.adHintsCount || '加密解码',
      hiddenLogsCount: status.hiddenLogsCount || '待解码',
    },
  };
}

export function getDecodedMonitorText(hiddenLog) {
  return `${t('ui.decodePrefix')} ${hiddenLog.title}\n${hiddenLog.content}`;
}

export function getDoorLabel(value) {
  const labels = getSkin().doorLabels || { open: '开启', closed: '关闭' };
  return labels[value] || value;
}

export function getDirectionLabel(value) {
  const labels = getSkin().directionLabels || { up: '上行', down: '下行', idle: '待机' };
  return labels[value] || value;
}
