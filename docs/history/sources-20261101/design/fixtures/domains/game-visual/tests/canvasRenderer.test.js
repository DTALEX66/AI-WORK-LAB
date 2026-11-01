import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

import { getAvailableActions } from '../src/actions.js';
import { createInitialState } from '../src/state.js';
import { loadSkin } from '../src/skinManager.js';
import securitySkin from '../src/skins/security/skin.json' with { type: 'json' };
import elevatorSkin from '../src/skins/elevator/skin.json' with { type: 'json' };
import { getCanvasActionButtons, getCanvasCameraTabs, getCanvasCctvTreatment, getCanvasFailureOverlayCopy, getCanvasLayout, getCanvasMeterBars, getCanvasMuteControl, getCanvasOverlayCloseButton, getCanvasOverlayModel, getCanvasProtocolItems, getCanvasProtocolSummary, getCanvasStaticLabels, getCanvasStatusItems, getCanvasToolButtons, getCanvasViewportMetrics, getCanvasVisibleActionButtons, getCanvasVisibleLogs, getV5CctvScreenId, onCanvasClick } from '../platform/canvasRenderer.js';
import { getDomLabels } from '../src/uiLabels.js';

const canvasRendererSource = readFileSync(new URL('../platform/canvasRenderer.js', import.meta.url), 'utf8');

test('Canvas V4 uses one dominant CCTV, three large readings and a two-button thumb zone', () => {
  const layout = getCanvasLayout(1334);
  const cssScale = 393 / 750;
  assert.ok(layout.monitor.w > 700 && layout.monitor.h >= 479);
  assert.ok(layout.readings.y > layout.monitor.y + layout.monitor.h);
  assert.ok(layout.actions.y > layout.readings.y + layout.readings.h);
  assert.equal(layout.actions.columns, 2);
  assert.ok(layout.actions.buttonH * cssScale >= 48);
  assert.ok(layout.actions.buttonH * (360 / 750) >= 48, 'short 360px phones keep full-size thumb targets');
  assert.ok(layout.feedback.y > layout.actions.y + layout.actions.h);
  assert.ok(layout.feedback.y + layout.feedback.h <= 1334, '360x640 design-height viewport must not clip feedback');
  assert.equal(layout.logs, undefined);
  assert.equal(layout.status, undefined);
});

test('Canvas V5 reserves native protocol and CAM rows without displacing the dominant CCTV', () => {
  const layout = getCanvasLayout(1334);
  assert.ok(layout.protocolBar.y > layout.topbar.y + layout.topbar.h);
  assert.ok(layout.cameraTabs.y > layout.protocolBar.y + layout.protocolBar.h);
  assert.ok(layout.monitor.y > layout.cameraTabs.y + layout.cameraTabs.h);
  assert.ok(layout.monitor.h >= 479);
  assert.ok(layout.monitor.h > layout.protocolBar.h + layout.cameraTabs.h);
});

test('Canvas V5 layout matches both official portrait acceptance viewports', () => {
  const cases = [
    { width: 393, height: 852, safeTop: 28, expectedCctv: 360 },
    { width: 360, height: 640, safeTop: 22, expectedCctv: 230 },
  ];
  for (const item of cases) {
    const ratio = 750 / item.width;
    const metrics = getCanvasViewportMetrics({
      windowWidth: item.width,
      windowHeight: item.height,
      safeArea: { top: item.safeTop },
    });
    const layout = getCanvasLayout(metrics.height, metrics.safeTop);
    const css = value => value / ratio;
    assert.ok(Math.abs(css(layout.monitor.h) - item.expectedCctv) <= 2,
      `${item.width}x${item.height} CCTV height follows the handoff`);
    assert.ok(css(layout.actions.buttonH) >= 48, 'primary actions retain 48px touch height');
    assert.ok(css(layout.feedback.y + layout.feedback.h) <= item.height, 'feedback remains inside viewport');
    assert.ok(layout.monitor.h > layout.protocolBar.h + layout.cameraTabs.h, 'CCTV remains the largest gameplay surface');
  }
});

test('Canvas V5 keeps large invisible touch targets around compact camera and tool visuals', () => {
  const layout = getCanvasLayout(1334);
  assert.ok(layout.cameraTabs.hitH >= 90);
  assert.ok(layout.cameraTabs.hitY < layout.cameraTabs.y);
  assert.ok(layout.tools.hitH >= 96);
  assert.ok(layout.tools.hitY < layout.tools.y);
});

test('Canvas V5 exposes power and contamination telemetry in the live feedback surface', () => {
  assert.match(canvasRendererSource, /电力/);
  assert.match(canvasRendererSource, /污染/);
  assert.match(canvasRendererSource, /state\.contamination\?\.value/);
});

test('Canvas V5 derives protocol summaries and available CAM tabs from scheduled night state', () => {
  const state = {
    ...createInitialState(),
    night: {
      ...createInitialState().night,
      activeProtocols: [
        { id: 'p1', category: 'floor', text: '13 层不存在，任何请求必须封锁。' },
        { id: 'p2', category: 'device', text: 'CAM-07 固定延迟两秒。' },
      ],
      currentShift: {
        evidence: { cameras: { cam01: [], cam03: [], cam07: [] } },
      },
    },
    investigation: { ...createInitialState().investigation, activeCamera: 'cam03' },
  };
  assert.deepEqual(getCanvasProtocolItems(state).map(item => item.id), ['p1', 'p2']);
  assert.deepEqual(getCanvasCameraTabs(state), [
    { id: 'cam01', label: 'CAM-01', active: false },
    { id: 'cam03', label: 'CAM-03', active: true },
    { id: 'cam07', label: 'CAM-07', active: false },
  ]);
});

test('Canvas V5 compacts protocol copy so both rules remain visible on short portrait screens', () => {
  assert.equal(getCanvasProtocolSummary([
    { text: '13层请求必须封锁并复核来源' },
    { text: '维修人员必须核验胸牌与目标楼层' },
  ]), '1.13层请求必须封锁并复核来源  2.维修人员必须核验胸牌与目标楼…');
  // 截断上限 14 字：必须保留结论子句（如“必须封锁/不属于异常”），不得截掉关键语义。
  assert.equal(getCanvasProtocolSummary([{ text: 'CAM-07 固定延迟两秒属于校准，延迟本身不属于异常' }]),
    '1.CAM-07 固定延迟两秒属…');
});

test('Canvas V5 CAM tabs dispatch camera switches through their native hit targets', () => {
  const state = {
    ...createInitialState(),
    night: {
      ...createInitialState().night,
      currentShift: { evidence: { cameras: { cam01: [], cam03: [], cam07: [] } } },
    },
  };
  const tabs = getCanvasLayout(1334).cameraTabs;
  let selected = null;
  onCanvasClick(tabs.x + tabs.w / 2, tabs.y + tabs.h / 2, state, {
    onCameraSwitch: id => { selected = id; },
  });
  assert.equal(selected, 'cam03');
});

test('Canvas V5 exposes three native investigation tools with live resource state', () => {
  const state = createInitialState();
  state.investigation.power = 7;
  state.investigation.tools.thermal.remaining = 2;
  state.investigation.tools.replay.remaining = 0;
  assert.deepEqual(getCanvasToolButtons(state), [
    { id: 'thermal', label: '热源扫描', meta: '2次 · 8电', disabled: true },
    { id: 'replay', label: '三秒回放', meta: '0次 · 4电', disabled: true },
    { id: 'protocol', label: '夜班协议', meta: '不限次', disabled: false },
  ]);
});

test('Canvas V5 derives bottom actions from roundType instead of a permanent deck', () => {
  const initial = createInitialState();
  const forRound = roundType => ({
    ...initial,
    tutorialStep: 4,
    inspection: { id: roundType, kind: 'normal', status: 'pending', expiresAt: 9 },
    night: { ...initial.night, roundType },
  });
  assert.deepEqual(getCanvasVisibleActionButtons(forRound('quick')).map(item => item.id), ['release', 'lockdown']);
  assert.deepEqual(getCanvasVisibleActionButtons(forRound('investigation')).map(item => item.id), ['markSuspicion', 'enterClassification']);
  assert.deepEqual(getCanvasVisibleActionButtons(forRound('identity')).map(item => item.id), ['identityRelease', 'identityReject', 'identityVerify']);
  assert.deepEqual(getCanvasVisibleActionButtons(forRound('classification')).map(item => item.id), [
    'classify:person', 'classify:quantity', 'classify:space', 'classify:time', 'classify:device', 'classify:dynamic',
  ]);
  assert.deepEqual(getCanvasVisibleActionButtons(forRound('highRisk')).map(item => item.id), [
    'highRisk:emergencyStop', 'highRisk:restart', 'highRisk:lockdownFloor',
  ]);
  assert.ok(getCanvasVisibleActionButtons(forRound('identity')).length < 7);
});

test('Canvas V5 exposes a bounded close target for native overlays', () => {
  const button = getCanvasOverlayCloseButton(1334, 0);
  assert.ok(button.w >= 500);
  assert.ok(button.h >= 60);
  assert.ok(button.y > 0);
});

test('Canvas V5 exposes protocol query and debrief as native overlay models', () => {
  const state = createInitialState();
  state.night.overlay = 'protocolQuery';
  state.night.protocolQuery = [{ id: 'p1', text: '必须核验胸牌' }];
  assert.deepEqual(getCanvasOverlayModel(state), {
    type: 'protocolQuery', title: '夜班协议查询', lines: ['必须核验胸牌'], action: 'closeOverlay',
  });
  state.night.overlay = 'debrief';
  state.night.debrief = { summary: { decisions: 2, accuracy: 0.5, peakContamination: 80 }, ending: { name: '带回来的夜班', summary: '污染进入下一次值守。' } };
  assert.equal(getCanvasOverlayModel(state).title, '局后复盘 · 带回来的夜班');
  assert.match(getCanvasOverlayModel(state).lines.join(' '), /50%/);
});

test('Canvas V5 native tool and dynamic action hit targets dispatch semantic callbacks', () => {
  const state = createInitialState();
  state.tutorialStep = 4;
  state.inspection = { id: 'shift', kind: 'normal', status: 'pending', expiresAt: 9 };
  state.night.roundType = 'investigation';
  const layout = getCanvasLayout(1334);
  let tool = null;
  let action = null;
  onCanvasClick(layout.tools.x + 20, layout.tools.y + layout.tools.h / 2, state, {
    onTool: id => { tool = id; },
  });
  onCanvasClick(layout.actions.x + 30, layout.actions.startY + 20, state, {
    onAction: id => { action = id; },
  });
  assert.equal(tool, 'thermal');
  assert.equal(action, 'markSuspicion');
});

test('Canvas mute control remains reachable before and during play', () => {
  const state = createInitialState();
  const preStartControl = getCanvasMuteControl(1334, 0, false);
  const playingControl = getCanvasMuteControl(1334, 0, true);
  const cssScale = 390 / 750;
  assert.ok(preStartControl.h * cssScale >= 44);
  assert.ok(playingControl.h * cssScale >= 44);
  let toggles = 0;
  onCanvasClick(
    preStartControl.x + preStartControl.w / 2,
    preStartControl.y + preStartControl.h / 2,
    state,
    { onToggleMute: () => { toggles += 1; } },
    { started: false, muted: false },
  );
  onCanvasClick(
    playingControl.x + playingControl.w / 2,
    playingControl.y + playingControl.h / 2,
    state,
    { onToggleMute: () => { toggles += 1; } },
    { started: true, muted: false },
  );
  assert.equal(toggles, 2);
});

test('Canvas V4 removes the four-key deck and exposes only the current two-choice task', () => {
  loadSkin(elevatorSkin);
  const idle = getCanvasVisibleActionButtons(createInitialState());
  assert.equal(idle.length, 1);
  assert.equal(idle[0].disabled, true);

  const anomaly = {
    ...createInitialState(),
    activeAnomaly: 'phantom_floor',
    inspection: { id: 'phantom_floor', kind: 'anomaly', status: 'resolved' },
  };
  const treatment = getCanvasVisibleActionButtons(anomaly);
  assert.equal(treatment.length, 1);
  assert.equal(treatment[0].id, 'autoTreatment');
  assert.equal(treatment[0].disabled, true);
  assert.equal(treatment.some(button => button.recommended), false);
});

test('canvas action buttons use current skin labels', () => {
  loadSkin(securitySkin);
  const labels = getCanvasActionButtons(createInitialState()).map(button => button.label);

  assert.ok(labels.includes('解锁门禁'));
  assert.ok(labels.includes('锁定门禁'));
  assert.ok(labels.includes('查看安防日志'));
  assert.ok(!labels.includes('开门'));

  loadSkin(elevatorSkin);
});

test('canvas action buttons show locked hidden-log count', () => {
  loadSkin(elevatorSkin);
  const state = {
    ...createInitialState(),
    hiddenLogs: [
      { id: 'a', title: 'A', content: 'A', locked: true },
      { id: 'b', title: 'B', content: 'B', locked: true },
    ],
  };

  const labels = getCanvasActionButtons(state).map(button => button.label);

  assert.ok(labels.includes('解码加密记录 (2)'));
});

test('canvas action buttons use the shared action list', () => {
  loadSkin(elevatorSkin);
  const buttons = getCanvasActionButtons(createInitialState());
  const expectedIds = getAvailableActions()
    .map(action => action.id)
    .filter(id => id !== 'unlockHiddenLog');

  assert.deepEqual(buttons.map(button => button.id), expectedIds);
});

test('pending inspection promotes normal/anomaly decisions to the first two controls', () => {
  loadSkin(elevatorSkin);
  const state = {
    ...createInitialState(),
    inspection: { id: 'baseline', kind: 'normal', title: '当前画面', status: 'pending', expiresAt: 6 },
  };
  const buttons = getCanvasActionButtons(state);
  assert.deepEqual(buttons.slice(0, 2).map(button => button.id), ['reportNormal', 'reportAnomaly']);
  assert.deepEqual(buttons.slice(0, 2).map(button => button.label), ['放行', '封锁']);
});

test('pending anomaly hides answer-giving logs and operational highlights until classified', () => {
  loadSkin(elevatorSkin);
  const state = {
    ...createInitialState(),
    activeAnomaly: { id: 'mirror_mismatch' },
    elapsed: 8,
    inspection: { id: 'mirror_mismatch', kind: 'anomaly', status: 'pending', openedAt: 8, expiresAt: 15 },
    logs: [
      { time: 2, type: 'info', text: '旧日志' },
      { time: 8, type: 'warn', text: '异常答案与操作提示' },
    ],
  };
  assert.deepEqual(getCanvasVisibleLogs(state).map(log => log.text), ['旧日志']);
  assert.equal(getCanvasActionButtons(state).slice(2).some(button => button.recommended), false);
  assert.equal(getCanvasActionButtons(state).slice(2).every(button => button.disabled), true);

  const resolved = { ...state, inspection: { ...state.inspection, status: 'resolved' } };
  assert.equal(getCanvasVisibleLogs(resolved).at(-1).text, '异常答案与操作提示');
});

test('inspection controls dispatch semantic decisions instead of maintenance actions', () => {
  loadSkin(elevatorSkin);
  const state = {
    ...createInitialState(),
    inspection: { id: 'anomaly', kind: 'anomaly', title: '异常', status: 'pending', expiresAt: 7 },
  };
  const layout = getCanvasLayout(1334).actions;
  let decision = null;
  let action = null;
  const x = layout.x + 16 + layout.buttonW / 2;
  const y = layout.startY + layout.buttonH / 2;
  onCanvasClick(x, y, state, {
    onDecision: value => { decision = value; },
    onAction: value => { action = value; },
  });
  assert.equal(decision, 'normal');
  assert.equal(action, null);

  const operationX = layout.x + 16 + 2 * (layout.buttonW + layout.gap) + layout.buttonW / 2;
  onCanvasClick(operationX, y, state, {
    onDecision: value => { decision = value; },
    onAction: value => { action = value; },
  });
  assert.equal(action, null, 'operations stay disabled until the inspection is classified');
});

test('canvas status items use current skin status labels', () => {
  loadSkin(securitySkin);
  const labels = getCanvasStatusItems(createInitialState()).map(item => item.label);
  const domLabels = getDomLabels();

  assert.ok(labels.includes('区域'));
  assert.ok(labels.includes('门禁'));
  assert.ok(labels.includes('人员'));
  assert.ok(!labels.includes('楼层'));
  assert.deepEqual(labels, Object.values(domLabels.status));

  loadSkin(elevatorSkin);
});

test('canvas meter bars use current skin status labels', () => {
  loadSkin(securitySkin);
  const bars = getCanvasMeterBars({ ...createInitialState(), power: 42, stability: 77 });

  assert.deepEqual(bars.map(bar => bar.label), ['电力', '安保等级']);
  assert.deepEqual(bars.map(bar => bar.value), [42, 77]);

  loadSkin(elevatorSkin);
});

test('canvas static labels use current skin copy', () => {
  loadSkin(securitySkin);
  const labels = getCanvasStaticLabels();
  const domLabels = getDomLabels();

  assert.equal(labels.countdown, '值守倒计时');
  assert.equal(labels.monitorPanel, '安防监控');
  assert.equal(labels.actionPanel, '安防操作');
  assert.equal(labels.logPanel, '安防日志');
  assert.equal(labels.forceAnomaly, undefined, 'Canvas bundle must not expose the browser debug trigger');
  assert.equal(labels.failureTitle, '安防系统崩溃');
  assert.equal(labels.failureEyebrow, 'SECURITY FAILURE');
  assert.equal(labels.countdown, domLabels.countdown);
  assert.equal(labels.monitorPanel, domLabels.monitorPanel);
  assert.equal(labels.actionPanel, domLabels.actionPanel);
  assert.equal(labels.logPanel, domLabels.logPanel);
  assert.notEqual(labels.forceAnomaly, domLabels.forceAnomaly);
  assert.equal(labels.failureTitle, domLabels.failureTitle);
  assert.equal(labels.failureEyebrow, domLabels.failureEyebrow);
  assert.equal(labels.revive, domLabels.revive);
  assert.equal(labels.restart, domLabels.restart);
  assert.equal(labels.revealTruth, domLabels.revealTruth);

  loadSkin(elevatorSkin);
});

test('canvas failure overlay copy uses current skin text', () => {
  const skin = structuredClone(securitySkin);
  skin.canvasLabels.failureEyebrow = 'SECURITY FAILURE';
  loadSkin(skin);

  const fakeEndingCopy = getCanvasFailureOverlayCopy({
    ...createInitialState(),
    gameOver: true,
    fakeEndingTriggered: true,
  });
  assert.equal(fakeEndingCopy.eyebrow, '⚠ SYSTEM ANOMALY DETECTED');
  assert.equal(fakeEndingCopy.title, '值班员关联异常');

  const failureCopy = getCanvasFailureOverlayCopy({
    ...createInitialState(),
    gameOver: true,
    lastAdHint: '先锁门。',
  });
  assert.equal(failureCopy.eyebrow, 'SECURITY FAILURE');
  assert.equal(failureCopy.adHintLine, '系统提示：先锁门。');

  loadSkin(elevatorSkin);
});

test('canvas renderer distinguishes success settlement from failure', () => {
  assert.match(canvasRendererSource, /state\.result === 'success'/, 'Canvas overlay should branch on explicit success result');
  assert.match(canvasRendererSource, /if \(!isSuccess\)[\s\S]*labels\.revive/, 'Canvas success settlement should omit rewarded-revive CTA');
});

test('canvas CCTV treatment consumes the shared cctvState mapping', () => {
  assert.deepEqual(getCanvasCctvTreatment('00_idle_closed'), {
    tint: 'rgba(97,255,190,0.05)', darkness: 0, entity: false, glitch: false, threat: false,
    border: 'rgba(121,214,163,0.34)',
  });
  assert.equal(getCanvasCctvTreatment('13_entity_near').entity, true);
  assert.equal(getCanvasCctvTreatment('20_threat_high').threat, true);
  assert.equal(getCanvasCctvTreatment('20_threat_high').border, 'rgba(255,77,109,0.85)');
  assert.equal(getCanvasCctvTreatment('10_signal_lost').glitch, true);
  assert.match(canvasRendererSource, /const cctvState = motion\?\.cctvState[\s\S]*state\?\.night\?\.currentShift\?\.visualState[\s\S]*baseVisual\.cctvState/);
  assert.match(canvasRendererSource, /getCanvasCctvTreatment\(cctvState\)/);
  assert.match(canvasRendererSource, /treatment\.border/, 'threat border must be consumed by the scene stroke');
});

test('canvas CCTV effects consume the pausable motion frame clock', () => {
  assert.match(canvasRendererSource, /const frameTime = Number\(motion\?\.frameTime/);
  assert.match(canvasRendererSource, /drawCanvasAnomalyArtifacts\(visual, x, y, w, h, frameTime\)/);
  assert.doesNotMatch(canvasRendererSource, /Math\.sin\(Date\.now\(\)/);
  assert.doesNotMatch(canvasRendererSource, /tearY[\s\S]{0,80}Date\.now\(\)/);
});

test('canvas CCTV cover-fills the fixed viewport without stretch or black bars', () => {
  const drawBlock = canvasRendererSource.match(/function drawCctvImage[\s\S]*?\n}/)?.[0] || '';
  assert.match(drawBlock, /drawImageCover\(image, x, y, w, h\)/,
    'CCTV art must cover-fill the fixed window so tall phones keep the source aspect ratio');
  assert.doesNotMatch(drawBlock, /cropTop|cropBottom|usableH|drawImageContain/);
  assert.doesNotMatch(drawBlock, /ctx\.drawImage\(image, x, y, w, h\)/,
    'direct stretch distorts the cabin by 1.5x on 393x852');
});

test('canvas V5 round types select handoff scene art with motion fallback', () => {
  assert.equal(getV5CctvScreenId({ night: { roundType: 'quick', currentShift: { id: 'x' } } }), 'quick');
  assert.equal(getV5CctvScreenId({ night: { roundType: 'identity', currentShift: { id: 'x' } } }), 'identity');
  assert.equal(getV5CctvScreenId({ night: { roundType: 'highRisk', currentShift: { id: 'x' } } }), 'highRisk');
  assert.equal(getV5CctvScreenId({ night: { roundType: 'quick', currentShift: { id: 'x' }, overlay: 'protocolQuery' } }), 'protocolQuery');
  assert.equal(getV5CctvScreenId({ night: { roundType: 'quick' } }), null);
  assert.match(canvasRendererSource, /motion\?\.active \? null : getV5CctvScreenId\(state\)/,
    'motion timelines must fall back to the 24-state machine art');
  assert.match(canvasRendererSource, /assetStore\?\.getV5Cctv\(v5ScreenId\)[\s\S]{0,120}assetStore\?\.getCctv\(cctvState\)/,
    'V5 handoff art must be preferred with the state machine as fallback');
});

test('canvas press feedback marks taps and shades pressed controls', () => {
  assert.match(canvasRendererSource, /export function noteCanvasPress/);
  assert.match(canvasRendererSource, /noteCanvasPress\(cameraTabs\[index\]\.id\)/);
  assert.match(canvasRendererSource, /noteCanvasPress\(tools\[index\]\.id\)/);
  assert.match(canvasRendererSource, /noteCanvasPress\(buttons\[i\]\.id\)/);
  assert.match(canvasRendererSource, /drawPressShade\(bx, by, buttonW, buttonH, getPressDepth\(btn\.id\)\)/);
  assert.match(canvasRendererSource, /drawPressShade\(x, layout\.y, buttonW, layout\.h, getPressDepth\(tool\.id\)\)/);
});

test('canvas CCTV atmosphere uses the supplied CRT treatment layers and runtime camera HUD', () => {
  assert.match(canvasRendererSource, /getOverlay\('scanlines'\)/);
  assert.match(canvasRendererSource, /getOverlay\('vignette'\)/);
  assert.match(canvasRendererSource, /getOverlay\('frame'\)/);
  assert.match(canvasRendererSource, /NIGHT WATCH/);
  assert.match(canvasRendererSource, /drawCctvAtmosphere\(state, x, y, w, h, treatment, frameTime\)/);
  assert.match(canvasRendererSource, /frameTime \/ 1800/);
  assert.match(canvasRendererSource, /treatment\.threat \? COLORS\.red/);
});

test('canvas CCTV atmosphere remains bounded to the CCTV clip', () => {
  assert.match(canvasRendererSource, /function drawCctvAtmosphere[\s\S]*?ctx\.rect\(x, y, w, h\)/);
  assert.match(canvasRendererSource, /function drawCctvAtmosphere[\s\S]*?ctx\.clip\(\)/);
  assert.match(canvasRendererSource, /function drawCctvAtmosphere[\s\S]*?ctx\.restore\(\)/);
});

test('canvas pending scan sweep animates with the pausable frame clock', () => {
  assert.match(canvasRendererSource, /sweepPhase = \(frameTime \/ 2100\)/,
    'scan sweep must move over time instead of a static band');
  assert.doesNotMatch(canvasRendererSource, /\[\[alert, 0\.72\], \[glitchOverlay, 0\.36\], \[sweep, 0\.28\]\]/);
});

test('canvas monitor uses text-free replacement art and runtime-owned HUD only', () => {
  assert.match(canvasRendererSource, /替换图无烘焙 HUD/);
  assert.match(canvasRendererSource, /始终显示实际楼层/);
  assert.match(canvasRendererSource, /画面楼层/);
  assert.doesNotMatch(canvasRendererSource, /hudShade|cropTop|cropBottom/);
  assert.doesNotMatch(canvasRendererSource, /CABIN FEED|SIGNAL VARIANCE|ANOMALY CONFIRMED/);
  assert.doesNotMatch(canvasRendererSource, /fillText\(['"]FLOOR MISMATCH/);
  assert.doesNotMatch(canvasRendererSource, /const barH = 80|fillRect\(x, barY, w, barH\)/,
    '不得用黑条遮挡移动电梯素材；固定楼层文字必须不存在于替换图');
});

test('Canvas V4 render path removes dashboard clutter and keeps gameplay type readable', () => {
  const renderBlock = canvasRendererSource.match(/export function render[\s\S]*?\n}/)?.[0] || '';
  assert.doesNotMatch(renderBlock, /drawStatusPanel/);
  assert.doesNotMatch(renderBlock, /drawLogs/);
  assert.match(renderBlock, /drawProtocolBar/);
  assert.match(renderBlock, /drawCameraTabs/);
  assert.match(renderBlock, /drawReadings/);
  assert.match(canvasRendererSource, /bold 34px [^\n]*Microsoft YaHei/);
  assert.match(canvasRendererSource, /font = '26px [^\n]*Microsoft YaHei/);
});

test('canvas monitor renderer draws a visual CCTV scene before caption text', () => {
  assert.match(canvasRendererSource, /function drawCctvScene/, 'Canvas mini-game monitor should include visual CCTV scene rendering');
  assert.match(canvasRendererSource, /drawCctvScene\(state/, 'drawMonitor should call the visual scene renderer');
  assert.match(canvasRendererSource, /heatAlpha/, 'Canvas monitor should draw passenger heat signature state');
});
