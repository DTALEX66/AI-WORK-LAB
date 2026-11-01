/**
 * canvasRenderer.js — Canvas 渲染器
 *
 * 完全替代 index.html + styles.css 的 DOM 渲染。
 * 在小游戏平台（微信/抖音）上使用 Canvas 渲染，
 * 在浏览器中也可作为独立渲染模式。
 *
 * 设计宽度：750px（标准移动端设计尺寸）
 */

import { getAvailableActions } from '../src/actions.js';
import { t, getSkin, actionLabel } from '../src/skinManager.js';
import { summarizeFailure } from '../src/feedback.js';
import { getCanvasDecodedMonitorText, getCanvasDirectionLabel, getCanvasDoorLabel, getCanvasLabels } from './canvasLabels.js';
import { deriveVisualState } from '../src/visualState.js';
import { createCanvasAssetStore } from './canvasAssets.js';

// ── 尺寸常量 ──
const DW = 750;       // 设计宽度
let canvas, ctx;
let scale = 1;        // 实际像素/设计像素比例
let DH = 1334;        // 设计高度（自适应）
let safeInsetTop = 0; // 全面屏安全区折算到设计坐标
let menuButtonLeft = Number.POSITIVE_INFINITY; // 平台胶囊左边界（设计坐标）
let assetStore = null; // 真实 CCTV / 控制台视觉资产

// ── 颜色 ──
const COLORS = {
  bg: '#07090a',
  panel: '#101314',
  panelRaised: '#1a1f20',
  line: 'rgba(195,200,190,0.24)',
  text: '#e7e2d5',
  muted: '#8e928c',
  green: '#79d6a3',
  amber: '#e1a84b',
  red: '#e75c4f',
  cyan: '#84b9b0',
  darkRed: '#a52e38',
};

export function getCanvasViewportMetrics(systemInfo = {}) {
  const windowWidth = Number(systemInfo.windowWidth) || 750;
  const windowHeight = Number(systemInfo.windowHeight) || 1334;
  const ratio = DW / windowWidth;
  const safeTop = Math.max(0, Number(systemInfo.safeArea?.top ?? systemInfo.statusBarHeight) || 0) * ratio;
  const capsuleLeft = Number(systemInfo.menuButtonRect?.left);
  return {
    width: DW,
    height: Math.max(1334, windowHeight * ratio),
    safeTop,
    menuButtonLeft: Number.isFinite(capsuleLeft) ? capsuleLeft * ratio : Number.POSITIVE_INFINITY,
  };
}

export function getCanvasLayout(height = 1334, safeTop = 0) {
  // V5：协议与 CAM 使用原生 Canvas 行；大 CCTV 仍是最大单一表面。
  const topbar = { x: 14, y: 12 + safeTop, w: 722, h: 76 };
  const protocolBar = { x: 14, y: 96 + safeTop, w: 722, h: 66 };
  const cameraTabs = {
    x: 14, y: 170 + safeTop, w: 722, h: 54, gap: 8,
    hitY: 146 + safeTop, hitH: 94,
  };
  // Match the two official V5 portrait frames: 360×640 uses a compact 230px CCTV,
  // while 393×852 spends the extra vertical room on a 360px CCTV. Interpolation
  // keeps intermediate phones fluid without creating a dead area below the monitor.
  const monitorH = Math.max(479, Math.min(687, 479 + (height - 1334) * (208 / 291)));
  const monitor = { x: 14, y: 232 + safeTop, w: 722, h: monitorH };
  const readings = { x: 14, y: monitor.y + monitor.h + 12, w: 722, h: 108 };
  const tools = {
    x: 14, y: readings.y + readings.h + 12, w: 722, h: 76, gap: 10,
    hitY: readings.y + readings.h + 2, hitH: 100,
  };
  const actions = {
    x: 14, y: tools.y + tools.h + 12, w: 722, h: 146,
    columns: 2, gap: 14, buttonH: 104,
  };
  actions.startY = actions.y + 42;
  actions.buttonW = (actions.w - 32 - actions.gap) / 2;
  const feedbackY = actions.y + actions.h + 12;
  return {
    topbar,
    rule: protocolBar,
    protocolBar,
    cameraTabs,
    monitor,
    readings,
    tools,
    actions,
    feedback: { x: 14, y: feedbackY, w: 722, h: Math.max(90, height - feedbackY - 18) },
  };
}

export function getCanvasStartControls(height = 1334, safeTop = 0) {
  const cardH = 650;
  const cardY = Math.max(118 + safeTop, (height - cardH) / 2);
  return {
    card: { x: 55, y: cardY, w: 640, h: cardH },
    start: { x: 85, y: cardY + 424, w: 580, h: 104 },
    sidebar: { x: 85, y: cardY + 546, w: 580, h: 86 },
  };
}

export function getCanvasMuteControl(height = 1334, safeTop = 0, started = true) {
  if (!started) {
    const { card } = getCanvasStartControls(height, safeTop);
    return { x: card.x + card.w - 112, y: card.y + 4, w: 88, h: 86, visualOffsetY: 12, visualH: 54 };
  }
  return { x: 644, y: 92 + safeTop, w: 88, h: 86, visualOffsetY: 12, visualH: 54 };
}

// ── Measure text ──
function measure(text, size, bold = false) {
  ctx.font = `${bold ? 'bold ' : ''}${size}px "Microsoft YaHei", sans-serif`;
  return ctx.measureText(text).width;
}

// ── Draw rounded rect ──
function roundRect(x, y, w, h, r, fill, stroke) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.arcTo(x + w, y, x + w, y + r, r);
  ctx.lineTo(x + w, y + h - r);
  ctx.arcTo(x + w, y + h, x + w - r, y + h, r);
  ctx.lineTo(x + r, y + h);
  ctx.arcTo(x, y + h, x, y + h - r, r);
  ctx.lineTo(x, y + r);
  ctx.arcTo(x, y, x + r, y, r);
  ctx.closePath();
  if (fill) { ctx.fillStyle = fill; ctx.fill(); }
  if (stroke) { ctx.strokeStyle = stroke; ctx.lineWidth = 1; ctx.stroke(); }
}

function drawIndustrialPanel(x, y, w, h, accent = 'rgba(195,200,190,0.34)') {
  const metal = ctx.createLinearGradient(0, y, 0, y + h);
  metal.addColorStop(0, '#272b2a');
  metal.addColorStop(0.08, '#161918');
  metal.addColorStop(0.92, '#0b0d0d');
  metal.addColorStop(1, '#242826');
  roundRect(x, y, w, h, 3, metal, accent);
  ctx.strokeStyle = 'rgba(255,255,255,0.07)';
  ctx.strokeRect(x + 5, y + 5, w - 10, h - 10);
  for (const [bx, by] of [[x + 10, y + 10], [x + w - 10, y + 10], [x + 10, y + h - 10], [x + w - 10, y + h - 10]]) {
    ctx.fillStyle = '#050606';
    ctx.beginPath();
    ctx.arc(bx, by, 3, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(210,218,207,0.22)';
    ctx.beginPath();
    ctx.moveTo(bx - 2, by);
    ctx.lineTo(bx + 2, by);
    ctx.stroke();
  }
}

// ── 绘制背景 ──
function drawBackground() {
  ctx.fillStyle = COLORS.bg;
  ctx.fillRect(0, 0, DW, DH);
  ctx.strokeStyle = 'rgba(255,255,255,0.018)';
  ctx.lineWidth = 1;
  for (let y = 0; y < DH; y += 24) {
    ctx.beginPath();
    ctx.moveTo(0, y);
    ctx.lineTo(DW, y);
    ctx.stroke();
  }
  const glow = ctx.createRadialGradient(DW / 2, 0, 0, DW / 2, 0, 520);
  glow.addColorStop(0, 'rgba(225,168,75,0.06)');
  glow.addColorStop(1, 'transparent');
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, DW, DH);
}

export function getCanvasStaticLabels() {
  const labels = getCanvasLabels();
  return {
    countdown: labels.countdown,
    monitorPanel: labels.monitorPanel,
    actionPanel: labels.actionPanel,
    logPanel: labels.logPanel,
    failureTitle: labels.failureTitle,
    failureEyebrow: labels.failureEyebrow,
    revive: labels.revive,
    restart: labels.restart,
    revealTruth: labels.revealTruth,
  };
}

export function getCanvasFailureOverlayCopy(state) {
  return {
    eyebrow: state.fakeEndingTriggered ? t('fakeEnding.eyebrow') : getCanvasStaticLabels().failureEyebrow,
    title: state.fakeEndingTriggered ? t('fakeEnding.title') : getCanvasStaticLabels().failureTitle,
    adHintLine: state.lastAdHint ? t('failure.adHintPrefix', { hint: state.lastAdHint }) : '',
  };
}

// ── 绘制顶栏 ──
function drawTopbar(state) {
  const { x, y, w, h } = getCanvasLayout(DH, safeInsetTop).topbar;
  const meta = getSkin().meta;
  drawIndustrialPanel(x, y, w, h, 'rgba(121,214,163,0.42)');
  ctx.fillStyle = COLORS.green;
  ctx.fillRect(x + 5, y + 5, 6, h - 10);

  ctx.fillStyle = COLORS.text;
  ctx.font = 'bold 40px "Microsoft YaHei", sans-serif';
  const title = String(meta?.name || '异常电梯').replace(/控制台|中控|调度台/g, '').trim();
  ctx.fillText(title || '异常电梯', x + 26, y + 50, 236);

  ctx.fillStyle = COLORS.muted;
  ctx.font = '22px "Microsoft YaHei", sans-serif';
  ctx.fillText(`得分 ${Math.round(state.score || 0)}`, x + 286, y + 47);
  ctx.fillStyle = (state.streak || 0) >= 3 ? COLORS.amber : COLORS.green;
  ctx.font = 'bold 22px "Microsoft YaHei", sans-serif';
  ctx.fillText(`连击${state.streak || 0}`, x + 390, y + 47);

  // 倒计时位于抖音胶囊左侧，避免系统控件遮挡。
  const cardW = 104;
  const fallbackX = x + w - cardW - 170;
  const cardX = Number.isFinite(menuButtonLeft)
    ? Math.min(x + w - cardW - 18, menuButtonLeft - cardW - 12)
    : fallbackX;
  roundRect(cardX, y + 8, cardW, h - 16, 2, '#070808', 'rgba(225,168,75,0.64)');
  ctx.fillStyle = COLORS.amber;
  ctx.font = 'bold 34px Consolas, monospace';
  ctx.textAlign = 'center';
  ctx.fillText(Math.ceil(state.remaining).toString(), cardX + cardW / 2, y + 49);
  ctx.textAlign = 'left';
}

function getRuleCopy(state) {
  const pending = state.inspection?.status === 'pending';
  const step = Number(state.tutorialStep || 0);
  if (pending && step === 0 && state.inspection?.kind === 'normal') return t('ui.tutorialNormal');
  if (pending && step === 1 && state.inspection?.kind === 'anomaly') return t('ui.tutorialAnomaly');
  if (!pending && state.activeAnomaly) return '系统正在自动处置，无需额外操作';
  return t('ui.coreRule');
}

export function getCanvasProtocolItems(state) {
  return (state?.night?.activeProtocols || []).slice(0, 3).map(protocol => ({
    id: protocol.id,
    category: protocol.category || 'protocol',
    text: protocol.text || protocol.id,
  }));
}

export function getCanvasProtocolSummary(protocols = []) {
  return protocols.map((protocol, index) => {
    const text = String(protocol?.text || protocol?.id || '');
    const compact = text.length > 14 ? `${text.slice(0, 14)}…` : text;
    return `${index + 1}.${compact}`;
  }).join('  ');
}

function drawProtocolBar(state) {
  const { x, y, w, h } = getCanvasLayout(DH, safeInsetTop).protocolBar;
  drawIndustrialPanel(x, y, w, h, 'rgba(225,168,75,0.40)');
  const protocols = getCanvasProtocolItems(state);
  ctx.fillStyle = protocols.length ? COLORS.amber : COLORS.green;
  ctx.fillRect(x + 6, y + 6, 7, h - 12);
  ctx.fillStyle = COLORS.text;
  ctx.font = 'bold 20px "Microsoft YaHei", sans-serif';
  ctx.fillText('夜班协议', x + 28, y + 26);
  ctx.font = '20px "Microsoft YaHei", sans-serif';
  const guided = Number(state.tutorialStep || 0) < 2 && state.inspection?.status === 'pending';
  const summary = guided || !protocols.length
    ? getRuleCopy(state)
    : getCanvasProtocolSummary(protocols);
  ctx.fillText(summary, x + 28, y + 52, w - 52);
}

export function getCanvasCameraTabs(state) {
  const cameras = Object.keys(state?.night?.currentShift?.evidence?.cameras || {});
  const activeCamera = state?.investigation?.activeCamera || 'cam01';
  return ['cam01', 'cam03', 'cam07']
    .filter(id => cameras.includes(id))
    .map(id => ({ id, label: id.replace('cam', 'CAM-'), active: id === activeCamera }));
}

function drawCameraTabs(state) {
  const layout = getCanvasLayout(DH, safeInsetTop).cameraTabs;
  const tabs = getCanvasCameraTabs(state);
  if (!tabs.length) return;
  const tabW = (layout.w - layout.gap * (tabs.length - 1)) / tabs.length;
  tabs.forEach((tab, index) => {
    const x = layout.x + index * (tabW + layout.gap);
    roundRect(x, layout.y, tabW, layout.h, 2,
      tab.active ? '#17352a' : '#101314',
      tab.active ? 'rgba(121,214,163,0.78)' : 'rgba(195,200,190,0.24)');
    ctx.fillStyle = tab.active ? COLORS.green : COLORS.muted;
    ctx.font = 'bold 22px Consolas, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(tab.label, x + tabW / 2, layout.y + 35);
    drawPressShade(x, layout.y, tabW, layout.h, getPressDepth(tab.id));
  });
  ctx.textAlign = 'left';
}

export function getCanvasReadings(state, motion = null) {
  const floor = Number(motion?.floorReel ?? state.floor ?? 0);
  const moving = motion?.active && (motion.kind === 'moveUp' || motion.kind === 'moveDown');
  const activeId = typeof state.activeAnomaly === 'string' ? state.activeAnomaly : state.activeAnomaly?.id;
  const floorMismatch = ['phantom_floor', 'floor_jump', 'negative_floor'].includes(activeId);
  return [
    {
      id: 'floor', label: '楼层',
      value: moving ? floor.toFixed(1) : String(Math.round(floor)).padStart(2, '0'),
      clue: '主控读数',
      danger: floorMismatch && state.inspection?.status !== 'pending',
    },
    { id: 'passengers', label: '人数', value: String(state.passengers ?? 0), clue: '载重计数', danger: false },
    { id: 'door', label: '门状态', value: getCanvasDoorLabel(state.door), clue: '安全回路', danger: false },
  ];
}

function drawReadings(state, motion = null) {
  const { x, y, w, h } = getCanvasLayout(DH, safeInsetTop).readings;
  drawIndustrialPanel(x, y, w, h, 'rgba(121,214,163,0.34)');
  const values = getCanvasReadings(state, motion);
  const cellW = (w - 28) / 3;
  values.forEach((item, index) => {
    const cx = x + 14 + index * cellW;
    if (index > 0) {
      ctx.strokeStyle = 'rgba(195,200,190,0.20)';
      ctx.beginPath();
      ctx.moveTo(cx, y + 14);
      ctx.lineTo(cx, y + h - 14);
      ctx.stroke();
    }
    ctx.fillStyle = COLORS.muted;
    ctx.font = '22px "Microsoft YaHei", sans-serif';
    ctx.fillText(item.label, cx + 18, y + 35);
    ctx.fillStyle = item.danger ? COLORS.amber : COLORS.text;
    ctx.font = 'bold 32px "Microsoft YaHei", sans-serif';
    ctx.fillText(item.value, cx + 18, y + 75);
    ctx.fillStyle = item.danger ? COLORS.amber : COLORS.green;
    ctx.font = '22px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'right';
    ctx.fillText(item.clue, cx + cellW - 18, y + 74, cellW - 80);
    ctx.textAlign = 'left';
  });
}

function drawFeedback(state) {
  const { x, y, w, h } = getCanvasLayout(DH, safeInsetTop).feedback;
  drawIndustrialPanel(x, y, w, h, toneBorder(state));
  const message = state.lastFeedback || t('ui.initialFeedback');
  const pending = state.inspection?.status === 'pending';
  ctx.fillStyle = state.activeAnomaly && !pending ? COLORS.amber : COLORS.text;
  ctx.font = 'bold 26px "Microsoft YaHei", sans-serif';
  ctx.fillText(message, x + 24, y + 42, w - 180);
  ctx.fillStyle = COLORS.muted;
  ctx.font = '22px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(pending ? '等待判断' : `安全 ${Math.round(state.stability || 0)}%`, x + w - 24, y + 42);
  ctx.textAlign = 'left';
  ctx.fillStyle = COLORS.muted;
  ctx.font = '20px "Microsoft YaHei", sans-serif';
  const power = Math.max(0, Math.min(100, Math.round(Number(state.power) || 0)));
  const contamination = Math.max(0, Math.min(100, Math.round(Number(state.contamination?.value) || 0)));
  ctx.fillText(`电力 ${power}%`, x + 24, y + 70);
  ctx.fillStyle = contamination >= 51 ? COLORS.red : contamination >= 26 ? COLORS.amber : COLORS.cyan;
  ctx.fillText(`污染 ${contamination}%`, x + 168, y + 70);
  const barY = y + Math.min(h - 22, 78);
  roundRect(x + 24, barY, w - 48, 12, 2, 'rgba(255,255,255,0.08)');
  if (!pending) {
    roundRect(x + 24, barY, Math.max(0, (w - 48) * ((state.stability || 0) / 100)), 12, 2,
      state.stability < 35 ? COLORS.red : COLORS.green);
  }
}

export function getCanvasStatusItems(state) {
  const labels = getCanvasLabels().status;

  return [
    { id: 'floor', label: labels.floor, value: state.floor },
    { id: 'door', label: labels.door, value: getCanvasDoorLabel(state.door) },
    { id: 'direction', label: labels.direction, value: getCanvasDirectionLabel(state.direction) },
    { id: 'passengers', label: labels.passengers, value: state.passengers },
    { id: 'power', label: labels.power, value: `${Math.round(state.power)}%` },
    { id: 'stability', label: labels.stability, value: `${Math.round(state.stability)}%` },
    { id: 'anomalyLevel', label: labels.anomalyLevel, value: state.anomalyLevel },
    { id: 'reviveCount', label: labels.reviveCount, value: state.adRevivesUsed },
    { id: 'adHintsCount', label: labels.adHintsCount, value: state.adHintsUsed },
    { id: 'hiddenLogsCount', label: labels.hiddenLogsCount, value: state.hiddenLogs.filter(h => h.locked).length },
  ];
}

export function getCanvasMeterBars(state) {
  const labels = getCanvasLabels().status;
  return [
    { id: 'power', label: labels.power, value: state.power, color: COLORS.cyan },
    { id: 'stability', label: labels.stability, value: state.stability, color: COLORS.green },
  ];
}

function getCanvasStatusPanelTitle() {
  return getCanvasLabels().statusPanel;
}

// ── 绘制状态面板 ──
function drawStatusPanel(state, motion = null) {
  const { x, y, w, h } = getCanvasLayout(DH, safeInsetTop).status;
  roundRect(x, y, w, h, 6, COLORS.panel, toneBorder(state));
  ctx.fillStyle = '#bbb9af';
  ctx.font = 'bold 12px Consolas, "Microsoft YaHei", monospace';
  ctx.fillText(`■ ${getCanvasStatusPanelTitle()}`, x + 14, y + 24);

  const coreIds = new Set(['floor', 'door', 'direction', 'passengers', 'power', 'stability', 'anomalyLevel']);
  const items = getCanvasStatusItems(state)
    .filter(item => coreIds.has(item.id))
    .map(item => item.id === 'floor' && motion?.active
      ? { ...item, value: Number(motion.floorReel).toFixed(1) }
      : item);
  const columns = 4;
  const gap = 8;
  const cardW = (w - 32 - gap * (columns - 1)) / columns;
  items.forEach(({ id, label, value }, i) => {
    const cx = x + 16 + (i % columns) * (cardW + gap);
    const cy = y + 36 + Math.floor(i / columns) * 54;
    const stroke = id === 'anomalyLevel' ? 'rgba(231,92,79,0.58)' : 'rgba(121,214,163,0.28)';
    roundRect(cx, cy, cardW, 46, 3, '#090b0c', stroke);
    ctx.fillStyle = COLORS.muted;
    ctx.font = '10px "Microsoft YaHei", sans-serif';
    ctx.fillText(label, cx + 8, cy + 15);
    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 17px Consolas, "Microsoft YaHei", monospace';
    ctx.textAlign = 'right';
    ctx.fillText(String(value), cx + cardW - 8, cy + 35);
    ctx.textAlign = 'left';
  });

  getCanvasMeterBars(state).forEach(({ label, value, color }, index) => {
    drawBar(x + 16, y + 148 + index * 20, w - 32, 14, label, value, color);
  });
}

function drawBar(x, y, w, h, label, value, color) {
  ctx.fillStyle = COLORS.muted;
  ctx.font = '11px "Microsoft YaHei", sans-serif';
  ctx.fillText(label, x, y + 12);

  const bx = x + 60, bw = w - 60;
  roundRect(bx, y, bw, h, 6, 'rgba(255,255,255,0.06)');
  const fillW = Math.max(0, (bw - 4) * (value / 100));
  roundRect(bx + 2, y + 2, fillW, h - 4, 4, color);

  ctx.fillStyle = COLORS.text;
  ctx.font = 'bold 11px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'right';
  ctx.fillText(`${Math.round(value)}`, bx + bw - 4, y + 12);
  ctx.textAlign = 'left';
}

function toneBorder(state) {
  if (state.inspection?.status === 'pending') return COLORS.line;
  const tone = deriveVisualState(state).tone;
  if (tone === 'danger') return 'rgba(255,77,109,0.55)';
  if (tone === 'critical') return 'rgba(255,209,102,0.38)';
  if (tone === 'warn') return 'rgba(255,209,102,0.38)';
  return COLORS.line;
}

// ── 绘制监控画面 ──
function drawMonitor(state, motion = null) {
  const { x, y, w, h } = getCanvasLayout(DH, safeInsetTop).monitor;
  drawIndustrialPanel(x, y, w, h, toneBorder(state));
  ctx.fillStyle = '#d8d4c8';
  ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
  ctx.fillText('实时监控', x + 24, y + 34);
  ctx.fillStyle = COLORS.green;
  ctx.beginPath();
  ctx.arc(x + 142, y + 26, 5, 0, Math.PI * 2);
  ctx.fill();

  const mx = x + 12, my = y + 48, mw = w - 24, mh = h - 60;
  roundRect(mx, my, mw, mh, 2, '#020505', 'rgba(121,214,163,0.28)');
  drawCctvScene(state, mx + 6, my + 6, mw - 12, mh - 12, motion);

  const frameTime = Number(motion?.frameTime ?? Date.now());
  const scanY = (frameTime / 100 * (mh - 12)) % (mh - 12);
  ctx.fillStyle = 'rgba(121,214,163,0.04)';
  ctx.fillRect(mx + 6, my + 6 + scanY, mw - 12, 4);

  if (state.inspection?.status === 'pending') {
    const seconds = Math.max(0, Math.ceil(state.inspection.expiresAt - state.elapsed));
    roundRect(x + w - 150, y + 8, 124, 36, 2, '#090b0b', 'rgba(225,168,75,0.64)');
    ctx.fillStyle = COLORS.amber;
    ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(`${seconds} 秒`, x + w - 88, y + 34);
    ctx.textAlign = 'left';
  }
}

export function getCanvasCctvTreatment(cctvState = '00_idle_closed') {
  const glitch = ['10_signal_lost', '11_camera_glitch', '17_loop_corridor'].includes(cctvState);
  const entity = ['13_entity_near', '14_shadow_inside', '15_anomaly_wandering'].includes(cctvState);
  const threat = ['08_emergency_stop', '09_door_jammed', '16_wrong_floor', '20_threat_high'].includes(cctvState);
  const darkness = cctvState === '07_power_outage' ? 0.62 : cctvState === '10_signal_lost' ? 0.38 : 0;
  const calm = cctvState === '19_stabilized' || cctvState === '23_cooldown_safe';
  const tint = threat
    ? 'rgba(255,77,109,0.16)'
    : calm
      ? 'rgba(97,255,190,0.12)'
      : 'rgba(97,255,190,0.05)';
  const border = threat
    ? 'rgba(255,77,109,0.85)'
    : glitch
      ? 'rgba(225,168,75,0.62)'
      : entity
        ? 'rgba(178,132,255,0.62)'
        : calm
          ? 'rgba(97,255,190,0.52)'
          : 'rgba(121,214,163,0.34)';
  return { tint, darkness, entity, glitch, threat, border };
}

function drawImageCover(image, x, y, w, h, fallbackWidth = 720, fallbackHeight = 420) {
  const sourceW = Number(image.width || image.naturalWidth) || fallbackWidth;
  const sourceH = Number(image.height || image.naturalHeight) || fallbackHeight;
  const sourceRatio = sourceW / sourceH;
  const targetRatio = w / h;
  let sx = 0, sy = 0, sw = sourceW, sh = sourceH;
  if (sourceRatio > targetRatio) {
    sw = sourceH * targetRatio;
    sx = (sourceW - sw) / 2;
  } else {
    sh = sourceW / targetRatio;
    sy = (sourceH - sh) / 2;
  }
  ctx.drawImage(image, sx, sy, sw, sh, x, y, w, h);
}

function drawCctvAtmosphere(state, x, y, w, h, treatment, frameTime = 0) {
  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();

  // 真实监控感：扫描线 + 镜头暗角 + 轻微色偏。三层均只作用于 CCTV，不污染按钮和协议。
  const scanlines = assetStore?.getOverlay('scanlines');
  const vignette = assetStore?.getOverlay('vignette');
  const frame = assetStore?.getOverlay('frame');
  if (scanlines) {
    ctx.globalAlpha = treatment.threat ? 0.38 : 0.24;
    ctx.drawImage(scanlines, x, y, w, h);
  }
  if (vignette) {
    ctx.globalAlpha = treatment.threat ? 0.82 : 0.62;
    ctx.drawImage(vignette, x, y, w, h);
  }
  ctx.globalAlpha = 1;

  if (treatment.tint) {
    ctx.fillStyle = treatment.tint;
    ctx.fillRect(x, y, w, h);
  }

  // 慢速 CRT 扫描带：比静态噪点更容易让玩家感到“摄像头正在工作”。
  const phase = ((frameTime / 1800) % 1 + 1) % 1;
  const beamY = y + phase * h;
  const beam = ctx.createLinearGradient(x, beamY - 30, x, beamY + 30);
  beam.addColorStop(0, 'rgba(97,255,190,0)');
  beam.addColorStop(0.5, treatment.threat ? 'rgba(255,77,109,0.30)' : 'rgba(97,255,190,0.22)');
  beam.addColorStop(1, 'rgba(97,255,190,0)');
  ctx.fillStyle = beam;
  ctx.fillRect(x, beamY - 30, w, 60);

  // 录制指示器与镜头角标是运行时 HUD，不泄露答案，只建立“夜班监控”语境。
  const pulse = 0.72 + Math.sin(frameTime / 170) * 0.22;
  ctx.globalAlpha = pulse;
  ctx.fillStyle = treatment.threat ? COLORS.red : '#ff5d67';
  ctx.beginPath();
  ctx.arc(x + 20, y + 22, 5, 0, Math.PI * 2);
  ctx.fill();
  ctx.globalAlpha = 1;
  ctx.fillStyle = '#e4e8df';
  ctx.font = 'bold 16px Consolas, monospace';
  ctx.fillText('REC', x + 32, y + 28);
  ctx.fillStyle = treatment.threat ? '#ff9a9f' : '#b4c4bb';
  ctx.font = '14px Consolas, monospace';
  const activeCamera = String(state?.investigation?.activeCamera || 'cam01').toUpperCase().replace('CAM', 'CAM-');
  ctx.fillText(`${activeCamera} // NIGHT WATCH`, x + 20, y + h - 18);

  // 角框比一整圈发光边框更克制，但会让 CCTV 从“普通图片”变成监控窗口。
  if (frame) {
    ctx.globalAlpha = 0.72;
    ctx.drawImage(frame, x, y, w, h);
    ctx.globalAlpha = 1;
  }
  ctx.strokeStyle = treatment.border || 'rgba(121,214,163,0.44)';
  ctx.lineWidth = treatment.threat ? 3 + Math.max(0, Math.sin(frameTime / 130)) : 2;
  ctx.strokeRect(x + 2, y + 2, w - 4, h - 4);

  if (treatment.threat) {
    ctx.globalAlpha = 0.72 + Math.sin(frameTime / 110) * 0.18;
    ctx.strokeStyle = COLORS.red;
    ctx.lineWidth = 4;
    ctx.strokeRect(x + 8, y + 8, w - 16, h - 16);
    ctx.globalAlpha = 1;
  }
  ctx.restore();
}

function drawCctvImage(image, x, y, w, h) {
  // CCTV 窗口保持主布局尺寸；素材 cover 铺满窗口：无拉伸变形、无黑边、不叠第二层背景。
  // 高竖屏窗口下中央裁掉两侧边缘，轿厢主体始终居中完整。
  drawImageCover(image, x, y, w, h);
}

// V5 阶段场景映射：夜班各回合使用交接包对应场景，运动/异常瞬时态仍回退 24 状态机图。
export function getV5CctvScreenId(state) {
  if (state?.night?.overlay === 'protocolQuery') return 'protocolQuery';
  const roundType = state?.night?.roundType;
  if (!state?.night?.currentShift) return null;
  return {
    quick: 'quick',
    investigation: 'investigation',
    identity: 'identity',
    classification: 'classification',
    highRisk: 'highRisk',
  }[roundType] || null;
}

function drawCctvScene(state, x, y, w, h, motion = null) {
  if (h <= 20) return;
  const baseVisual = deriveVisualState(state);
  const frameTime = Number(motion?.frameTime ?? Date.now());
  const cctvState = motion?.cctvState
    || state?.night?.currentShift?.visualState
    || baseVisual.cctvState;
  const visual = { ...baseVisual, cctvState, glitch: baseVisual.glitch || Number(motion?.glitchAlpha || 0) > 0 };
  const treatment = getCanvasCctvTreatment(cctvState);
  const v5ScreenId = motion?.active ? null : getV5CctvScreenId(state);
  const sceneImage = (v5ScreenId ? assetStore?.getV5Cctv(v5ScreenId) : null)
    || assetStore?.getCctv(cctvState);

  if (sceneImage) {
    ctx.save();
    ctx.beginPath();
    ctx.rect(x, y, w, h);
    ctx.clip();

    const zoom = Math.max(1, Number(motion?.zoom || 1));
    const drawW = w * zoom, drawH = h * zoom;
    const drawX = x - (drawW - w) / 2 + Number(motion?.offsetX || 0);
    const drawY = y - (drawH - h) / 2 + Number(motion?.offsetY || 0);
    const previousImage = motion?.active && motion.previousCctvState !== cctvState
      ? assetStore.getCctv(motion.previousCctvState)
      : null;
    const isMove = motion?.kind === 'moveUp' || motion?.kind === 'moveDown';
    const blend = motion?.active ? (isMove ? 1 : Math.min(1, motion.progress * 2.5)) : 1;
    if (previousImage && blend < 1) {
      ctx.globalAlpha = 1 - blend;
      drawCctvImage(previousImage, drawX, drawY, drawW, drawH);
    }
    ctx.globalAlpha = blend;
    drawCctvImage(sceneImage, drawX, drawY, drawW, drawH);
    ctx.globalAlpha = 1;

    drawCctvAtmosphere(state, x, y, w, h, treatment, frameTime);

    // 状态图已内置基础监控纹理，只叠加真正随时间变化的警报与干扰。
    const pendingDecision = state.inspection?.status === 'pending';
    const alert = treatment.threat && !pendingDecision ? assetStore.getOverlay('redAlert') : null;
    const glitchOverlay = treatment.glitch ? assetStore.getOverlay('glitch') : null;
    for (const [image, alpha] of [[alert, 0.72], [glitchOverlay, 0.36]]) {
      if (!image) continue;
      ctx.globalAlpha = alpha;
      ctx.drawImage(image, x, y, w, h);
    }
    ctx.globalAlpha = 1;

    // 待判定扫描光束随时间自上而下扫过，给出“系统正在核对”的活体感。
    const sweep = pendingDecision ? assetStore.getOverlay('sweep') : null;
    if (sweep) {
      const sweepH = Math.max(96, Math.floor(h * 0.38));
      const sweepPhase = (frameTime / 2100) % 1.45;
      if (sweepPhase <= 1) {
        const sweepY = y - sweepH + sweepPhase * (h + sweepH * 2);
        ctx.globalAlpha = 0.34;
        ctx.drawImage(sweep, x, sweepY, w, sweepH);
        ctx.globalAlpha = 1;
      }
    }

    const glitchAlpha = Math.max(0, Math.min(1, Number(motion?.glitchAlpha || 0)));
    if (glitchAlpha > 0) {
      ctx.globalAlpha = glitchAlpha;
      for (let i = 0; i < 4; i += 1) {
        const tearY = y + ((frameTime / (23 + i * 7) + i * 137) % h);
        const tearH = 3 + i * 2;
        ctx.fillStyle = i % 2 ? 'rgba(255,77,109,0.42)' : 'rgba(121,214,163,0.34)';
        ctx.fillRect(x + Math.sin(frameTime / (19 + i)) * 18, tearY, w, tearH);
      }
      ctx.globalAlpha = 1;
    }

    const flickerAlpha = Math.max(0, Math.min(1, Number(motion?.flickerAlpha || 0)));
    if (flickerAlpha > 0) {
      ctx.fillStyle = `rgba(0,0,0,${flickerAlpha})`;
      ctx.fillRect(x, y, w, h);
    }

    const scanPhase = Number(motion?.scanPhase || 0) % 1;
    const scanY = y + scanPhase * h;
    const scanGradient = ctx.createLinearGradient(x, scanY - 24, x, scanY + 24);
    scanGradient.addColorStop(0, 'rgba(121,214,163,0)');
    scanGradient.addColorStop(0.5, 'rgba(121,214,163,0.16)');
    scanGradient.addColorStop(1, 'rgba(121,214,163,0)');
    ctx.fillStyle = scanGradient;
    ctx.fillRect(x, scanY - 24, w, 48);

    // 替换图无烘焙 HUD；只绘制运行时楼层和状态标签，不覆盖电梯主体。
    const inspectionPending = state.inspection?.status === 'pending';
    const neutralBorder = inspectionPending ? 'rgba(195,200,190,0.34)' : treatment.border;
    ctx.strokeStyle = neutralBorder;
    ctx.globalAlpha = 0.72;
    ctx.strokeRect(x + 1, y + 1, w - 2, h - 2);
    ctx.globalAlpha = 1;

    const floorValue = Number(motion?.floorReel ?? state.floor ?? 0);
    // V4: 始终显示实际楼层，不因异常混淆画面楼层。
    // 玩家必须通过真实画面与面板数据的矛盾自行判断。
    const observedFloor = floorValue;
    roundRect(x + 16, y + 14, 126, 70, 2, 'rgba(3,10,9,0.92)', 'rgba(121,214,163,0.52)');
    ctx.fillStyle = motion?.active && (motion.kind === 'moveUp' || motion.kind === 'moveDown') ? COLORS.amber : COLORS.green;
    ctx.font = 'bold 30px Consolas, monospace';
    ctx.textAlign = 'center';
    ctx.fillText(motion?.active && (motion.kind === 'moveUp' || motion.kind === 'moveDown')
      ? observedFloor.toFixed(1)
      : String(Math.round(observedFloor)).padStart(2, '0'), x + 79, y + 50);
    ctx.fillStyle = COLORS.text;
    ctx.font = '22px "Microsoft YaHei", sans-serif';
    ctx.fillText('画面楼层', x + 79, y + 76);

    let feedLabel = '监控稳定';
    if (inspectionPending) feedLabel = '核对画面与数据';
    else if (state.activeAnomaly) feedLabel = '异常已封锁';
    else if (motion?.kind === 'moveUp') feedLabel = '电梯上行';
    else if (motion?.kind === 'moveDown') feedLabel = '电梯下行';
    else if (motion?.kind === 'openDoor' || cctvState === '01_door_open') feedLabel = '电梯门开启';
    else if (motion?.kind === 'closeDoor') feedLabel = '电梯门关闭';
    roundRect(x + w - 220, y + 18, 198, 46, 2, 'rgba(3,10,9,0.92)', neutralBorder);
    ctx.fillStyle = state.activeAnomaly && !inspectionPending ? COLORS.red : inspectionPending ? COLORS.amber : COLORS.green;
    ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
    ctx.fillText(feedLabel, x + w - 121, y + 49);
    ctx.textAlign = 'left';

    if (visual.glitch || treatment.glitch) drawCanvasAnomalyArtifacts(visual, x, y, w, h, frameTime);

    ctx.restore();
    return;
  }

  const bg = ctx.createLinearGradient(x, y, x, y + h);
  bg.addColorStop(0, 'rgba(7,30,32,0.92)');
  bg.addColorStop(1, 'rgba(0,5,7,0.98)');
  roundRect(x, y, w, h, 10, bg, 'rgba(97,255,190,0.12)');

  ctx.save();
  ctx.beginPath();
  ctx.rect(x, y, w, h);
  ctx.clip();

  ctx.fillStyle = treatment.tint;
  ctx.fillRect(x, y, w, h);
  if (treatment.darkness > 0) {
    ctx.fillStyle = `rgba(0,0,0,${treatment.darkness})`;
    ctx.fillRect(x, y, w, h);
  }

  ctx.strokeStyle = 'rgba(97,255,190,0.11)';
  ctx.lineWidth = 1;
  for (let yy = y + 12; yy < y + h; yy += 22) {
    ctx.beginPath();
    ctx.moveTo(x, yy);
    ctx.lineTo(x + w, yy);
    ctx.stroke();
  }
  for (const ratio of [0.18, 0.5, 0.82]) {
    ctx.beginPath();
    ctx.moveTo(x + w * ratio, y);
    ctx.lineTo(x + w * ratio, y + h);
    ctx.stroke();
  }

  const carW = Math.min(w * 0.42, 150);
  const carH = h * 0.76;
  const jitter = state.moving ? Math.sin(frameTime / 60) * 2 : 0;
  const carX = x + w / 2 - carW / 2 + jitter;
  const carY = y + h - carH - 8;
  const carFill = ctx.createLinearGradient(carX, carY, carX + carW, carY);
  carFill.addColorStop(0, 'rgba(191,255,240,0.13)');
  carFill.addColorStop(0.5, 'rgba(0,12,14,0.72)');
  carFill.addColorStop(1, 'rgba(191,255,240,0.10)');
  roundRect(carX, carY, carW, carH, 8, carFill, 'rgba(191,255,240,0.42)');

  const open = state.door === 'open';
  const doorGap = open ? carW * 0.18 : 0;
  ctx.fillStyle = 'rgba(97,255,190,0.09)';
  ctx.fillRect(carX + doorGap, carY + 2, carW / 2 - doorGap, carH - 4);
  ctx.fillRect(carX + carW / 2, carY + 2, carW / 2 - doorGap, carH - 4);
  ctx.strokeStyle = 'rgba(97,255,190,0.24)';
  ctx.beginPath();
  ctx.moveTo(carX + carW / 2, carY + 4);
  ctx.lineTo(carX + carW / 2, carY + carH - 4);
  ctx.stroke();

  const heatAlpha = treatment.entity ? 0.98 : state.passengers > 0 ? 0.55 : 0.12;
  const heat = ctx.createRadialGradient(carX + carW / 2, carY + carH * 0.58, 4, carX + carW / 2, carY + carH * 0.58, 34);
  heat.addColorStop(0, `rgba(255,209,102,${heatAlpha})`);
  heat.addColorStop(0.45, `rgba(255,77,109,${heatAlpha * 0.7})`);
  heat.addColorStop(1, 'transparent');
  ctx.fillStyle = heat;
  ctx.fillRect(carX + carW / 2 - 38, carY + carH * 0.28, 76, carH * 0.62);

  roundRect(x + 10, y + h - 28, 58, 20, 8, 'rgba(0,0,0,0.48)', 'rgba(97,255,190,0.24)');
  ctx.fillStyle = COLORS.text;
  ctx.font = 'bold 12px Consolas, monospace';
  ctx.fillText(`F${state.floor}`, x + 18, y + h - 14);

  const reticleX = x + w - 42;
  const reticleY = y + h - 42;
  const reticleThreat = treatment.threat || state.anomalyLevel > 0;
  ctx.strokeStyle = reticleThreat ? 'rgba(255,77,109,0.88)' : 'rgba(97,255,190,0.32)';
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.arc(reticleX, reticleY, 22 + (reticleThreat ? Math.sin(frameTime / 120) * 2 : 0), 0, Math.PI * 2);
  ctx.stroke();
  ctx.beginPath();
  ctx.moveTo(reticleX - 18, reticleY);
  ctx.lineTo(reticleX + 18, reticleY);
  ctx.moveTo(reticleX, reticleY - 18);
  ctx.lineTo(reticleX, reticleY + 18);
  ctx.stroke();

  if (visual.glitch || treatment.glitch) {
    const artifactVisual = treatment.glitch
      ? { ...visual, glitch: true, noise: Math.max(0.72, visual.noise) }
      : visual;
    drawCanvasAnomalyArtifacts(artifactVisual, x, y, w, h, frameTime);
  }

  ctx.restore();
}

function drawCanvasAnomalyArtifacts(visual, x, y, w, h, frameTime = Date.now()) {
  const now = frameTime;
  ctx.save();
  ctx.globalCompositeOperation = 'screen';
  ctx.globalAlpha = Math.min(0.9, visual.noise);
  ctx.fillStyle = 'rgba(255,255,255,0.06)';
  for (let i = 0; i < 16; i += 1) {
    const yy = y + ((i * 17 + Math.floor(now / 40) * 9) % h);
    ctx.fillRect(x, yy, w, 1);
  }
  ctx.globalAlpha = 0.42;
  ctx.fillStyle = 'rgba(255,77,109,0.18)';
  ctx.fillRect(x + ((now / 30) % 12) - 6, y + h * 0.32, w, 5);
  ctx.fillStyle = 'rgba(81,214,255,0.16)';
  ctx.fillRect(x - ((now / 34) % 10), y + h * 0.58, w, 4);
  ctx.globalAlpha = visual.tone === 'critical' || visual.tone === 'danger' ? 0.34 : 0.18;
  const infrared = ctx.createRadialGradient(x + w * 0.52, y + h * 0.52, 4, x + w * 0.52, y + h * 0.52, Math.min(w, h) * 0.42);
  infrared.addColorStop(0, 'rgba(255,209,102,0.72)');
  infrared.addColorStop(0.46, 'rgba(255,77,109,0.28)');
  infrared.addColorStop(1, 'transparent');
  ctx.fillStyle = infrared;
  ctx.fillRect(x, y, w, h);
  if (visual.shake) {
    ctx.globalAlpha = 0.22;
    ctx.fillStyle = 'rgba(216,255,243,0.22)';
    ctx.fillRect(x, y, w, h);
  }
  ctx.restore();
}

function getMonitorText(state) {
  const unlockedHidden = state.hiddenLogs.filter(h => !h.locked);
  if (unlockedHidden.length > 0) {
    const last = unlockedHidden[unlockedHidden.length - 1];
    return getCanvasDecodedMonitorText(last);
  }
  return state.monitor;
}

export function getCanvasActionButtons(state) {
  const lockedCount = state.hiddenLogs.filter(h => h.locked).length;
  const visual = deriveVisualState(state);
  const operations = getAvailableActions()
    .filter(action => action.id !== 'unlockHiddenLog' || lockedCount > 0)
    .map(action => action.id === 'unlockHiddenLog'
      ? { id: action.id, label: actionLabel(action.id, lockedCount), recommended: visual.highlightAction === action.id }
      : { ...action, recommended: visual.highlightAction === action.id })
    .map(action => ({
      ...action,
      disabled: Boolean(state.transition) && !['emergencyStop', 'inspectLog', 'unlockHiddenLog'].includes(action.id),
    }));

  if (state.inspection?.status === 'pending') {
    const concealedOperations = operations.slice(0, 6).map(action => ({
      ...action,
      recommended: false,
      disabled: true,
    }));
    return [
      { id: 'reportNormal', label: t('ui.reportNormal'), decision: 'normal' },
      { id: 'reportAnomaly', label: t('ui.reportAnomaly'), decision: 'anomaly' },
      ...concealedOperations,
    ];
  }
  return operations;
}

const TOOL_LABELS = {
  thermal: '热源扫描',
  replay: '三秒回放',
  protocol: '夜班协议',
};

export function getCanvasToolButtons(state) {
  const investigation = state?.investigation || {};
  return ['thermal', 'replay', 'protocol'].map(id => {
    const tool = investigation.tools?.[id] || {};
    const remaining = tool.remaining;
    const unlimited = !Number.isFinite(remaining);
    const disabled = !unlimited && (remaining <= 0 || (investigation.power ?? 0) < (tool.powerCost || 0));
    return {
      id,
      label: TOOL_LABELS[id],
      meta: unlimited ? '不限次' : `${remaining || 0}次 · ${tool.powerCost || 0}电`,
      disabled,
    };
  });
}

const ROUND_ACTIONS = {
  quick: [
    { id: 'release', label: '放行', sublabel: '画面数据一致', decision: 'normal' },
    { id: 'lockdown', label: '封锁', sublabel: '发现任意矛盾', decision: 'anomaly' },
  ],
  investigation: [
    { id: 'markSuspicion', label: '标记疑点', sublabel: '保留当前证据' },
    { id: 'enterClassification', label: '进入分类', sublabel: '提交异常类型' },
  ],
  identity: [
    { id: 'identityRelease', label: '放行', sublabel: '身份一致' },
    { id: 'identityReject', label: '拒绝', sublabel: '身份冲突' },
    { id: 'identityVerify', label: '核验', sublabel: '查看胸牌与权限' },
  ],
  classification: [
    { id: 'classify:person', label: '人物', sublabel: '身份/外观' },
    { id: 'classify:quantity', label: '数量', sublabel: '人数/载重' },
    { id: 'classify:space', label: '空间', sublabel: '楼层/位置' },
    { id: 'classify:time', label: '时间', sublabel: '时序/回放' },
    { id: 'classify:device', label: '设备', sublabel: '信号/读数' },
    { id: 'classify:dynamic', label: '动态', sublabel: '移动/变化' },
  ],
  highRisk: [
    { id: 'highRisk:emergencyStop', label: '急停', sublabel: '消耗 15 电' },
    { id: 'highRisk:restart', label: '重启', sublabel: '消耗 10 电' },
    { id: 'highRisk:lockdownFloor', label: '封锁楼层', sublabel: '消耗 12 电' },
  ],
};

export function getCanvasVisibleActionButtons(state) {
  if (state.inspection?.status === 'pending') {
    if (Number(state.tutorialStep || 0) < 2) return [
      { id: 'reportNormal', label: t('ui.reportNormal'), sublabel: '画面数据一致', decision: 'normal' },
      { id: 'reportAnomaly', label: t('ui.reportAnomaly'), sublabel: '发现任意矛盾', decision: 'anomaly' },
    ];
    if (Number(state.tutorialStep || 0) === 3) return ROUND_ACTIONS.quick;
    return ROUND_ACTIONS[state?.night?.roundType] || ROUND_ACTIONS.quick;
  }

  const activeId = typeof state.activeAnomaly === 'string' ? state.activeAnomaly : state.activeAnomaly?.id;
  if (activeId) {
    return [{ id: 'autoTreatment', label: '系统处置中', sublabel: '无需额外操作', disabled: true, wide: true }];
  }

  return [{ id: 'standby', label: t('ui.standby'), sublabel: '监控自动运行', disabled: true, wide: true }];
}

function drawTools(state) {
  const layout = getCanvasLayout(DH, safeInsetTop).tools;
  const tools = getCanvasToolButtons(state);
  const buttonW = (layout.w - 24 - layout.gap * 2) / 3;
  tools.forEach((tool, index) => {
    const x = layout.x + 12 + index * (buttonW + layout.gap);
    ctx.save();
    if (tool.disabled) ctx.globalAlpha = 0.42;
    roundRect(x, layout.y, buttonW, layout.h, 2, '#101716', tool.disabled ? COLORS.line : 'rgba(132,185,176,0.62)');
    ctx.fillStyle = tool.disabled ? COLORS.muted : COLORS.cyan;
    ctx.font = 'bold 22px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(tool.label, x + buttonW / 2, layout.y + 31);
    ctx.fillStyle = COLORS.muted;
    ctx.font = '18px "Microsoft YaHei", sans-serif';
    ctx.fillText(tool.meta, x + buttonW / 2, layout.y + 58);
    drawPressShade(x, layout.y, buttonW, layout.h, getPressDepth(tool.id));
    ctx.restore();
  });
  ctx.textAlign = 'left';
}

// ── 绘制操作按钮 ──
function drawActions(state) {
  const layout = getCanvasLayout(DH, safeInsetTop).actions;
  const { x, y, w, h, gap, buttonH, startY } = layout;
  drawIndustrialPanel(x, y, w, h, 'rgba(195,200,190,0.34)');
  ctx.fillStyle = '#d8d4c8';
  ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
  ctx.fillText(state.activeAnomaly && state.inspection?.status !== 'pending' ? '系统处置' : '当前判断', x + 24, y + 31);

  const btns = getCanvasVisibleActionButtons(state);
  const columns = btns.length === 1 ? 1 : btns.length === 6 ? 6 : btns.length === 3 ? 3 : 2;
  const buttonW = columns === 1 ? w - 32 : (w - 32 - gap * (columns - 1)) / columns;
  btns.forEach((btn, i) => {
    ctx.save();
    if (btn.disabled) ctx.globalAlpha = 0.48;
    const bx = x + 16 + (i % columns) * (buttonW + gap);
    const by = startY;
    const danger = btn.id === 'reportAnomaly';
    const safe = btn.id === 'reportNormal';
    const accent = danger ? COLORS.red : safe ? COLORS.green : COLORS.amber;
    const fill = ctx.createLinearGradient(0, by, 0, by + buttonH);
    fill.addColorStop(0, danger ? '#512723' : safe ? '#214436' : '#37311f');
    fill.addColorStop(0.12, danger ? '#321512' : safe ? '#142b22' : '#211d13');
    fill.addColorStop(0.86, '#090a0a');
    fill.addColorStop(1, '#262928');
    roundRect(bx, by, buttonW, buttonH, 3, fill, accent);
    ctx.strokeStyle = 'rgba(0,0,0,0.86)';
    ctx.strokeRect(bx + 7, by + 7, buttonW - 14, buttonH - 14);

    for (const sx of [bx + 13, bx + buttonW - 13]) {
      ctx.fillStyle = '#050606';
      ctx.beginPath();
      ctx.arc(sx, by + 13, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.beginPath();
      ctx.arc(sx, by + buttonH - 13, 4, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.shadowColor = accent;
    ctx.shadowBlur = btn.disabled ? 0 : 12;
    ctx.fillStyle = accent;
    ctx.beginPath();
    ctx.arc(bx + buttonW / 2, by + 18, 7, 0, Math.PI * 2);
    ctx.fill();
    ctx.shadowBlur = 0;

    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 28px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(btn.label, bx + buttonW / 2, by + 57);
    ctx.fillStyle = '#b5b8b1';
    ctx.font = '19px "Microsoft YaHei", sans-serif';
    ctx.fillText(btn.sublabel || '', bx + buttonW / 2, by + 86, buttonW - 20);
    drawPressShade(bx, by, buttonW, buttonH, getPressDepth(btn.id));

    const guidedIndex = Number(state.tutorialStep || 0);
    const guided = (state.inspection?.status === 'pending'
      && ((guidedIndex === 0 && btn.id === 'reportNormal') || (guidedIndex === 1 && btn.id === 'reportAnomaly')))
      || (guidedIndex === 2 && btn.recommended);
    if (guided) {
      ctx.strokeStyle = accent;
      ctx.lineWidth = 4;
      ctx.strokeRect(bx - 4, by - 4, buttonW + 8, buttonH + 8);
      ctx.fillStyle = accent;
      ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
      ctx.fillText('点这里', bx + buttonW / 2, by - 12);
    }
    ctx.textAlign = 'left';
    ctx.restore();
  });
}

// ── 绘制系统日志 ──
export function getCanvasVisibleLogs(state, maxRows = Number.POSITIVE_INFINITY) {
  let logs = state.logs || [];
  if (state.inspection?.kind === 'anomaly' && state.inspection?.status === 'pending') {
    logs = logs.filter(log => log.time < state.inspection.openedAt);
  }
  return Number.isFinite(maxRows) ? logs.slice(-maxRows) : logs;
}

function drawLogs(state) {
  const { x, y, w, h } = getCanvasLayout(DH, safeInsetTop).logs;
  const labels = getCanvasStaticLabels();
  roundRect(x, y, w, h, 6, COLORS.panel, COLORS.line);
  ctx.fillStyle = '#bbb9af';
  ctx.font = 'bold 12px Consolas, "Microsoft YaHei", monospace';
  ctx.fillText(`■ ${labels.logPanel}`, x + 14, y + 24);

  const maxRows = Math.min(5, Math.max(3, Math.floor((h - 48) / 22)));
  const logs = getCanvasVisibleLogs(state, maxRows);
  logs.forEach((log, i) => {
    const lx = x + 18, ly = y + 38 + i * 22;
    const colorMap = { warn: COLORS.amber, danger: COLORS.red, system: COLORS.cyan, success: COLORS.green };
    ctx.fillStyle = colorMap[log.type] || '#aeb4ad';
    ctx.font = '12px Consolas, "Microsoft YaHei", monospace';
    ctx.fillText(`${i + 1}. ${log.text}`, lx, ly + 12, w - 36);
  });
}

export function getCanvasOverlayCloseButton(height = 1334, safeTop = 0) {
  const x = 55, w = 640, h = 430;
  const y = Math.max(150 + safeTop, (height - h) / 2);
  return { x: x + 32, y: y + h - 88, w: w - 64, h: 60 };
}

export function getCanvasOverlayModel(state) {
  if (state?.night?.overlay === 'protocolQuery') {
    return {
      type: 'protocolQuery',
      title: '夜班协议查询',
      lines: (state.night.protocolQuery || []).map(item => item.text || item.id),
      action: 'closeOverlay',
    };
  }
  if (state?.night?.overlay === 'debrief' && state.night.debrief) {
    const { summary = {}, ending = {} } = state.night.debrief;
    return {
      type: 'debrief',
      title: `局后复盘 · ${ending.name || '未决记录'}`,
      lines: [
        `判断 ${summary.decisions || 0} 次 · 准确率 ${Math.round((summary.accuracy || 0) * 100)}%`,
        `污染峰值 ${summary.peakContamination || 0}`,
        ending.summary || '',
      ].filter(Boolean),
      action: 'closeOverlay',
    };
  }
  return null;
}

function drawNightOverlay(state) {
  const model = getCanvasOverlayModel(state);
  if (!model) return;
  ctx.fillStyle = 'rgba(0,0,0,0.76)';
  ctx.fillRect(0, 0, DW, DH);
  const x = 55, w = 640, h = 430, y = Math.max(150 + safeInsetTop, (DH - h) / 2);
  drawIndustrialPanel(x, y, w, h, 'rgba(225,168,75,0.72)');
  ctx.fillStyle = COLORS.amber;
  ctx.font = 'bold 34px "Microsoft YaHei", sans-serif';
  ctx.fillText(model.title, x + 32, y + 58, w - 64);
  ctx.fillStyle = COLORS.text;
  ctx.font = '26px "Microsoft YaHei", sans-serif';
  model.lines.forEach((line, index) => wrapText(`${index + 1}. ${line}`, x + 32, y + 112 + index * 62, w - 64, 32));
  const closeButton = getCanvasOverlayCloseButton(DH, safeInsetTop);
  roundRect(closeButton.x, closeButton.y, closeButton.w, closeButton.h, 3, '#17352a', 'rgba(121,214,163,0.72)');
  ctx.fillStyle = COLORS.green;
  ctx.font = 'bold 26px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText('返回监控', closeButton.x + closeButton.w / 2, closeButton.y + 39);
  ctx.textAlign = 'left';
}

// ── 绘制失败弹窗 ──
function drawFailureOverlay(state) {
  if (!state.gameOver) return;

  // 半透明背景
  ctx.fillStyle = 'rgba(0,0,0,0.72)';
  ctx.fillRect(0, 0, DW, DH);

  const cardW = 640, cardH = 520;
  const cx = (DW - cardW) / 2, cy = (DH - cardH) / 2;

  const labels = getCanvasStaticLabels();
  const copy = getCanvasFailureOverlayCopy(state);
  const isSuccess = state.result === 'success';
  if (!isSuccess && state.fakeEndingTriggered) {
    // 假结局
    roundRect(cx, cy, cardW, cardH, 8, '#211013', 'rgba(231,92,79,0.72)');

    ctx.fillStyle = COLORS.darkRed;
    ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
    ctx.fillText(copy.eyebrow, cx + 30, cy + 42);

    ctx.fillStyle = '#ff315f';
    ctx.font = 'bold 46px "Microsoft YaHei", sans-serif';
    ctx.fillText(copy.title, cx + 30, cy + 102);

    const text = state.fakeEndingText || '';
    ctx.fillStyle = '#ff8ba3';
    ctx.font = '24px "Microsoft YaHei", sans-serif';
    wrapText(text, cx + 30, cy + 146, cardW - 60, 34);

    if (state.fakeEndingUnlocked) {
      ctx.fillStyle = '#bffff0';
      ctx.font = '24px "Microsoft YaHei", sans-serif';
      const truth = state.fakeEndingTruth || '';
      wrapText(truth, cx + 30, cy + 280, cardW - 60, 34);
    }
  } else {
    roundRect(
      cx,
      cy,
      cardW,
      cardH,
      8,
      '#111415',
      isSuccess ? 'rgba(97,255,190,0.62)' : 'rgba(255,77,109,0.52)',
    );

    ctx.fillStyle = isSuccess ? COLORS.green : COLORS.red;
    ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
    ctx.fillText(isSuccess ? '本轮结算' : copy.eyebrow, cx + 30, cy + 42);

    ctx.fillStyle = isSuccess ? COLORS.green : COLORS.red;
    ctx.font = 'bold 48px "Microsoft YaHei", sans-serif';
    ctx.fillText(isSuccess ? t('ui.shiftComplete') : labels.failureTitle, cx + 30, cy + 106);

    ctx.fillStyle = COLORS.text;
    ctx.font = '26px "Microsoft YaHei", sans-serif';
    const reason = isSuccess ? t('ui.successfulShift') : summarizeFailure(state);
    wrapText(reason, cx + 30, cy + 154, cardW - 60, 38);

    ctx.fillStyle = COLORS.amber;
    ctx.font = 'bold 34px "Microsoft YaHei", sans-serif';
    ctx.fillText(`得分 ${Math.round(state.score || 0)}`, cx + 30, cy + 270);
    ctx.fillStyle = COLORS.text;
    ctx.font = '26px "Microsoft YaHei", sans-serif';
    ctx.fillText(`最高连击 ${state.bestStreak || 0}`, cx + 30, cy + 312);

    if (!isSuccess && state.lastAdHint) {
      ctx.fillStyle = COLORS.amber;
      ctx.font = '24px "Microsoft YaHei", sans-serif';
      ctx.fillText(copy.adHintLine, cx + 30, cy + 352, cardW - 60);
    }
  }

  // 按钮
  const btnY = cy + cardH - 106;
  if (!isSuccess) {
    const btnW2 = (cardW - 60) / 2;
    roundRect(cx + 20, btnY, btnW2, 86, 5, '#17352a', 'rgba(121,214,163,0.7)');
    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 26px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    const btnLabel = state.fakeEndingTriggered && !state.fakeEndingUnlocked
      ? labels.revealTruth
      : state.fakeEndingTriggered
      ? labels.restart
      : labels.revive;
    ctx.fillText(btnLabel, cx + 20 + btnW2 / 2, btnY + 50);
    ctx.textAlign = 'left';

    roundRect(cx + 40 + btnW2, btnY, btnW2, 86, 5, '#202425', 'rgba(195,200,190,0.24)');
    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 26px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(labels.restart, cx + 40 + btnW2 + btnW2 / 2, btnY + 50);
    ctx.textAlign = 'left';
  } else {
    roundRect(cx + 20, btnY, cardW - 40, 86, 5, '#17352a', 'rgba(121,214,163,0.7)');
    ctx.fillStyle = COLORS.text;
    ctx.font = 'bold 26px "Microsoft YaHei", sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText(labels.restart, cx + cardW / 2, btnY + 50);
    ctx.textAlign = 'left';
  }
}

function drawMuteControl(viewState) {
  const control = getCanvasMuteControl(DH, safeInsetTop, viewState.started !== false);
  const visualY = control.y + control.visualOffsetY;
  roundRect(control.x, visualY, control.w, control.visualH, 4, '#141819', 'rgba(195,200,190,0.34)');
  ctx.fillStyle = viewState.muted ? COLORS.amber : COLORS.green;
  ctx.font = 'bold 22px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(
    t(viewState.muted ? 'ui.audioOff' : 'ui.audioOn'),
    control.x + control.w / 2,
    visualY + control.visualH / 2 + 5,
  );
  ctx.textAlign = 'left';
}

function drawStartOverlay(viewState = {}) {
  const controls = getCanvasStartControls(DH, safeInsetTop);
  const { card, start, sidebar } = controls;
  ctx.fillStyle = 'rgba(2,3,3,0.88)';
  ctx.fillRect(0, 0, DW, DH);
  drawIndustrialPanel(card.x, card.y, card.w, card.h, 'rgba(121,214,163,0.56)');
  ctx.fillStyle = COLORS.green;
  ctx.fillRect(card.x + 8, card.y + 8, 8, card.h - 16);

  ctx.fillStyle = COLORS.text;
  ctx.font = 'bold 52px "Microsoft YaHei", sans-serif';
  ctx.fillText('异常电梯', card.x + 34, card.y + 76);
  ctx.fillStyle = COLORS.amber;
  ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
  ctx.fillText('夜班值守许可', card.x + 36, card.y + 116);

  ctx.fillStyle = '#d1d2cb';
  ctx.font = '26px "Microsoft YaHei", sans-serif';
  wrapText(t('ui.startCopy'), card.x + 36, card.y + 164, card.w - 72, 38);

  roundRect(card.x + 36, card.y + 252, card.w - 72, 70, 2, '#10251d', 'rgba(121,214,163,0.62)');
  ctx.fillStyle = COLORS.green;
  ctx.font = 'bold 30px "Microsoft YaHei", sans-serif';
  ctx.fillText('三项一致', card.x + 58, card.y + 297);
  ctx.fillStyle = COLORS.text;
  ctx.textAlign = 'right';
  ctx.fillText('放行', card.x + card.w - 58, card.y + 297);
  ctx.textAlign = 'left';

  roundRect(card.x + 36, card.y + 334, card.w - 72, 70, 2, '#2b1513', 'rgba(231,92,79,0.70)');
  ctx.fillStyle = COLORS.red;
  ctx.font = 'bold 30px "Microsoft YaHei", sans-serif';
  ctx.fillText('任意矛盾', card.x + 58, card.y + 379);
  ctx.fillStyle = COLORS.text;
  ctx.textAlign = 'right';
  ctx.fillText('封锁', card.x + card.w - 58, card.y + 379);
  ctx.textAlign = 'left';

  const startFill = ctx.createLinearGradient(0, start.y, 0, start.y + start.h);
  startFill.addColorStop(0, '#2b5b48');
  startFill.addColorStop(0.15, '#183d2e');
  startFill.addColorStop(1, '#08110d');
  roundRect(start.x, start.y, start.w, start.h, 3, startFill, 'rgba(121,214,163,0.88)');
  ctx.fillStyle = COLORS.text;
  ctx.font = 'bold 34px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(t('ui.startButton'), start.x + start.w / 2, start.y + 65);

  const sidebarEnabled = viewState.sidebarAvailable === true;
  roundRect(sidebar.x, sidebar.y, sidebar.w, sidebar.h, 2,
    sidebarEnabled ? '#24211a' : '#111313',
    sidebarEnabled ? 'rgba(225,168,75,0.64)' : 'rgba(195,200,190,0.18)');
  ctx.fillStyle = sidebarEnabled ? COLORS.amber : '#666a66';
  ctx.font = 'bold 24px "Microsoft YaHei", sans-serif';
  ctx.fillText(t('ui.sidebarEntry'), sidebar.x + sidebar.w / 2, sidebar.y + 54);
  ctx.textAlign = 'left';
}

function drawPauseOverlay() {
  ctx.fillStyle = 'rgba(2,3,3,0.72)';
  ctx.fillRect(0, 0, DW, DH);
  const w = 430, h = 150, x = (DW - w) / 2, y = (DH - h) / 2;
  roundRect(x, y, w, h, 7, '#111415', 'rgba(225,168,75,0.56)');
  ctx.fillStyle = COLORS.amber;
  ctx.font = 'bold 28px "Microsoft YaHei", sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(t('ui.pausedTitle'), DW / 2, y + 68);
  ctx.fillStyle = COLORS.muted;
  ctx.font = '15px "Microsoft YaHei", sans-serif';
  ctx.fillText(t('ui.pausedCopy'), DW / 2, y + 106);
  ctx.textAlign = 'left';
}

// ── 文字换行 ──
function wrapText(text, x, y, maxWidth, lineHeight) {
  if (!text) return;
  const lines = text.split('\n');
  let cy = y;
  for (const line of lines) {
    let currentLine = '';
    for (const char of line) {
      const testLine = currentLine + char;
      const tw = ctx.measureText(testLine).width;
      if (tw > maxWidth && currentLine) {
        ctx.fillText(currentLine, x, cy);
        currentLine = char;
        cy += lineHeight;
      } else {
        currentLine = testLine;
      }
    }
    if (currentLine) {
      ctx.fillText(currentLine, x, cy);
      cy += lineHeight;
    }
  }
}

// ── 按压反馈 ──
const pressFx = new Map();
const PRESS_FX_MS = 180;

export function noteCanvasPress(id) {
  if (id) pressFx.set(id, Date.now());
}

function getPressDepth(id) {
  const at = pressFx.get(id);
  if (!Number.isFinite(at)) return 0;
  const age = Date.now() - at;
  if (age > PRESS_FX_MS) {
    pressFx.delete(id);
    return 0;
  }
  return 1 - age / PRESS_FX_MS;
}

function drawPressShade(x, y, w, h, depth) {
  if (depth <= 0) return;
  ctx.save();
  ctx.globalAlpha = 0.3 * depth;
  roundRect(x + 2, y + 2, w - 4, h - 4, 2, '#000000');
  ctx.globalAlpha = 0.5 * depth;
  ctx.strokeStyle = 'rgba(255,255,255,0.75)';
  ctx.lineWidth = 2;
  ctx.strokeRect(x + 5, y + 5, w - 10, h - 10);
  ctx.restore();
}

// ── 点击检测 ──
let clickHandlers = {};

export function onCanvasClick(x, y, state, callbacks, viewState = { started: true }) {
  const { onAdRevive, onRestart, onAction, onDecision, onTool, onCameraSwitch, onToggleMute, onStart, onSidebar } = callbacks;
  const inside = (rect) => x >= rect.x && x <= rect.x + rect.w && y >= rect.y && y <= rect.y + rect.h;
  const muteControl = getCanvasMuteControl(DH, safeInsetTop, viewState.started !== false);
  if (!state.gameOver && inside(muteControl)) {
    onToggleMute?.();
    return;
  }

  if (viewState.started === false) {
    const controls = getCanvasStartControls(DH, safeInsetTop);
    if (inside(controls.start)) onStart?.();
    else if (viewState.sidebarAvailable === true && inside(controls.sidebar)) onSidebar?.();
    return;
  }

  if (viewState.paused === true) return;

  if (getCanvasOverlayModel(state)) {
    if (inside(getCanvasOverlayCloseButton(DH, safeInsetTop))) onAction?.('closeOverlay');
    return;
  }

  // 失败弹窗按钮检测
  if (state.gameOver) {
    const cardW = 640, cardH = 520;
    const cx2 = (DW - cardW) / 2, cy2 = (DH - cardH) / 2;
    const btnY = cy2 + cardH - 106;
    if (state.result === 'success') {
      if (x >= cx2 + 20 && x <= cx2 + cardW - 20 && y >= btnY && y <= btnY + 86) {
        onRestart?.();
      }
      return;
    }
    const btnW2 = (cardW - 60) / 2;

    // 左按钮
    if (x >= cx2 + 20 && x <= cx2 + 20 + btnW2 && y >= btnY && y <= btnY + 86) {
      if (state.fakeEndingTriggered && !state.fakeEndingUnlocked) {
        onAdRevive?.('truth');
      } else if (state.fakeEndingTriggered) {
        onRestart?.();
      } else {
        onAdRevive?.('revive');
      }
      return;
    }
    // 右按钮
    if (x >= cx2 + 40 + btnW2 && x <= cx2 + 40 + btnW2 * 2 && y >= btnY && y <= btnY + 86) {
      onRestart?.();
      return;
    }
    return;
  }

  const cameraLayout = getCanvasLayout(DH, safeInsetTop).cameraTabs;
  const cameraTabs = getCanvasCameraTabs(state);
  const cameraHit = { ...cameraLayout, y: cameraLayout.hitY ?? cameraLayout.y, h: cameraLayout.hitH ?? cameraLayout.h };
  if (cameraTabs.length && inside(cameraHit)) {
    const tabW = (cameraLayout.w - cameraLayout.gap * (cameraTabs.length - 1)) / cameraTabs.length;
    for (let index = 0; index < cameraTabs.length; index += 1) {
      const tabX = cameraLayout.x + index * (tabW + cameraLayout.gap);
      if (x >= tabX && x <= tabX + tabW) {
        noteCanvasPress(cameraTabs[index].id);
        onCameraSwitch?.(cameraTabs[index].id);
      }
    }
    return;
  }

  const toolLayout = getCanvasLayout(DH, safeInsetTop).tools;
  const toolHit = { ...toolLayout, y: toolLayout.hitY ?? toolLayout.y, h: toolLayout.hitH ?? toolLayout.h };
  if (inside(toolHit)) {
    const tools = getCanvasToolButtons(state);
    const buttonW = (toolLayout.w - 24 - toolLayout.gap * 2) / 3;
    for (let index = 0; index < tools.length; index += 1) {
      const toolX = toolLayout.x + 12 + index * (buttonW + toolLayout.gap);
      if (x >= toolX && x <= toolX + buttonW && !tools[index].disabled) {
        noteCanvasPress(tools[index].id);
        onTool?.(tools[index].id);
      }
    }
    return;
  }

  // V5 动态任务点击检测，与绘制布局共用同一组按钮数据。
  const layout = getCanvasLayout(DH, safeInsetTop).actions;
  const buttons = getCanvasVisibleActionButtons(state);
  const columns = buttons.length === 1 ? 1 : buttons.length === 6 ? 6 : buttons.length === 3 ? 3 : 2;
  const buttonW = columns === 1 ? layout.w - 32 : (layout.w - 32 - layout.gap * (columns - 1)) / columns;
  for (let i = 0; i < buttons.length; i += 1) {
    const bx = layout.x + 16 + (i % columns) * (buttonW + layout.gap);
    const by = layout.startY;
    if (x >= bx && x <= bx + buttonW && y >= by && y <= by + layout.buttonH) {
      if (buttons[i].disabled) return;
      noteCanvasPress(buttons[i].id);
      if (buttons[i].decision) {
        onDecision?.(buttons[i].decision);
      } else onAction?.(buttons[i].id);
      return;
    }
  }
}

// ── 主渲染函数 ──
export function render(state, viewState = { started: true, paused: false }) {
  if (!ctx) return;

  drawBackground();
  drawTopbar(state);
  drawProtocolBar(state);
  drawCameraTabs(state);
  drawMonitor(state, viewState.cctvMotion);
  drawReadings(state, viewState.cctvMotion);
  drawTools(state);
  drawActions(state);
  drawFeedback(state);
  drawFailureOverlay(state);
  drawNightOverlay(state);
  if (viewState.started === false) drawStartOverlay(viewState);
  else if (viewState.paused === true) drawPauseOverlay();
  if (!state.gameOver) drawMuteControl(viewState);
}

// ── 初始化 ──
export function init(canvasEl, systemInfo = {}, options = {}) {
  canvas = canvasEl;
  ctx = canvas.getContext('2d');

  const metrics = getCanvasViewportMetrics(systemInfo);
  DH = metrics.height;
  safeInsetTop = metrics.safeTop;
  menuButtonLeft = metrics.menuButtonLeft;

  canvas.width = metrics.width;
  canvas.height = metrics.height;
  scale = 1;

  // 小游戏运行时优先 wx/tt createImage；浏览器验收 harness 通过 options.imageFactory 注入 DOM Image，
  // 使发布 bundle 不含任何 document/window 引用。
  const imageFactory = options.imageFactory || (() => {
    if (typeof tt !== 'undefined' && typeof tt.createImage === 'function') return tt.createImage();
    if (typeof wx !== 'undefined' && typeof wx.createImage === 'function') return wx.createImage();
    if (typeof canvas.createImage === 'function') return canvas.createImage();
    return null;
  });
  assetStore = createCanvasAssetStore(imageFactory);
  assetStore.preload();

  return { width: DW, height: DH };
}
