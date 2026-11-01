import assert from 'node:assert/strict';
import test from 'node:test';

import protocols from '../src/content/protocols.json' with { type: 'json' };
import {
  evaluateNightProtocolSet,
  generateNightProtocols,
  protocolAppliesToShift,
  evaluateProtocolDecision,
} from '../src/protocolEngine.js';

test('a night protocol set changes the shift decision only through applicable rules', () => {
  const selected = [
    protocols.find(item => item.id === 'floor_13_forbidden'),
    protocols.find(item => item.id === 'cam07_delay_expected'),
  ];
  const shift = {
    screenData: { floor: 13, passengers: 0, door: 'closed' },
    panelData: { floor: 13, passengers: 0, door: 'closed' },
    evidence: { cameraDelayMs: 2000 },
    protocolTags: ['floor'],
  };

  const result = evaluateNightProtocolSet(selected, shift);

  assert.equal(result.decision, 'lockdown');
  assert.deepEqual(result.appliedProtocolIds, ['floor_13_forbidden']);
  assert.deepEqual(result.violatedProtocolIds, ['floor_13_forbidden']);
  assert.ok(result.verificationPaths.includes('cam07'));
});

test('protocol catalogue uses one-sentence player-readable rules', () => {
  assert.ok(protocols.length >= 5);
  for (const protocol of protocols) {
    assert.match(protocol.id, /^[a-z0-9_]+$/);
    assert.ok(['floor', 'personnel', 'time', 'device', 'identity'].includes(protocol.category));
    assert.ok(protocol.text.length <= 44);
    assert.equal(/[。！？]/g.test(protocol.text.slice(0, -1)), false, `${protocol.id} must be one sentence`);
  }
});

test('night protocol generation returns 2-3 unique rules and guarantees one applicable rule', () => {
  const shifts = [{ protocolTags: ['device'], evidence: { camera: 'cam07' } }];
  const selected = generateNightProtocols({ protocols, shifts, count: 3, random: () => 0 });

  assert.equal(selected.length, 3);
  assert.equal(new Set(selected.map(item => item.id)).size, 3);
  assert.ok(selected.some(protocol => shifts.some(shift => protocolAppliesToShift(protocol, shift))));
});

test('protocol-dependent decision is deterministic and includes a reliable verification path', () => {
  const protocol = protocols.find(item => item.id === 'floor_13_forbidden');
  const shift = {
    screenData: { floor: 13, passengers: 0, door: 'closed' },
    panelData: { floor: 13, passengers: 0, door: 'closed' },
    protocolTags: ['floor'],
    evidence: { cameras: ['cam01', 'cam07'], tools: ['protocol'] },
  };

  const result = evaluateProtocolDecision(protocol, shift);
  assert.equal(result.decision, 'lockdown');
  assert.equal(result.violated, true);
  assert.ok(result.verificationPaths.length >= 1);
});
