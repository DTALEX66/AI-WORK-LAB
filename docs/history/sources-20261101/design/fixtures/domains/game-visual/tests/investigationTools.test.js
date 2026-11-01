import assert from 'node:assert/strict';
import test from 'node:test';

import {
  createInvestigationState,
  switchCamera,
  useInvestigationTool,
} from '../src/investigationTools.js';

test('camera switch exposes only the evidence assigned to that camera', () => {
  const state = createInvestigationState();
  const shift = {
    cameras: ['cam01', 'cam03', 'cam07'],
    evidence: {
      cameras: {
        cam01: [{ id: 'cam01_person', observation: '轿厢内有一名乘客。' }],
        cam03: [{ id: 'cam03_empty', observation: '电梯厅无人进入。' }],
        cam07: [{ id: 'cam07_entry', observation: '井道记录显示乘客提前进入。' }],
      },
    },
  };

  const result = switchCamera(state, 'cam03', shift);

  assert.equal(result.accepted, true);
  assert.equal(result.state.activeCamera, 'cam03');
  assert.deepEqual(result.visibleEvidence, shift.evidence.cameras.cam03);
  assert.equal(result.state.discoveredEvidence.some(item => item.id === 'cam01_person'), false);
});

test('protocol query returns current rules without consuming power or charges', () => {
  const state = createInvestigationState({ power: 40 });
  const shift = {
    activeProtocols: [
      { id: 'floor_13_forbidden', text: '13 层不存在。' },
      { id: 'cam07_delay_expected', text: 'CAM-07 固定延迟两秒。' },
    ],
  };

  const result = useInvestigationTool(state, 'protocol', shift);

  assert.equal(result.accepted, true);
  assert.equal(result.state.power, 40);
  assert.equal(result.state.tools.protocol.remaining, Number.POSITIVE_INFINITY);
  assert.deepEqual(result.discoveredEvidence, shift.activeProtocols);
});

test('replay is limited to two uses and cannot spend below zero', () => {
  const shift = { evidence: { replay: { id: 'replay_loop', type: 'replay', observation: '三秒动作完全重复。' } } };
  const first = useInvestigationTool(createInvestigationState({ power: 20 }), 'replay', shift);
  const second = useInvestigationTool(first.state, 'replay', shift);
  const third = useInvestigationTool(second.state, 'replay', shift);

  assert.equal(first.accepted, true);
  assert.equal(second.accepted, true);
  assert.equal(second.state.power, 12);
  assert.equal(second.state.tools.replay.remaining, 0);
  assert.equal(third.accepted, false);
  assert.equal(third.reason, 'no-uses');
  assert.strictEqual(third.state, second.state);
});

test('tools reject insufficient power without consuming a charge', () => {
  const state = createInvestigationState({ power: 7 });
  const result = useInvestigationTool(state, 'thermal', { evidence: {} });

  assert.equal(result.accepted, false);
  assert.equal(result.reason, 'insufficient-power');
  assert.strictEqual(result.state, state);
  assert.equal(state.tools.thermal.remaining, 2);
});

test('thermal scan consumes one charge and power but only reveals evidence', () => {
  const state = createInvestigationState({ power: 100 });
  const shift = {
    evidence: {
      thermal: {
        id: 'thermal_01',
        type: 'thermal',
        cameraId: 'cam01',
        observation: '轿厢内检测到 1 个稳定热源。',
      },
    },
  };

  const result = useInvestigationTool(state, 'thermal', shift);

  assert.equal(result.accepted, true);
  assert.equal(result.state.power, 92);
  assert.equal(result.state.tools.thermal.remaining, 1);
  assert.deepEqual(result.discoveredEvidence, shift.evidence.thermal);
  assert.equal('decision' in result, false, 'investigation tools must never return the answer');
});
