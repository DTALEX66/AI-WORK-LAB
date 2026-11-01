import assert from 'node:assert/strict';
import test from 'node:test';

import {
  countPassengersForPanel,
  verifyPassengerIdentity,
} from '../src/identitySystem.js';

const maintenance = {
  id: 'worker_001',
  name: '张伟',
  role: 'maintenance',
  badge: 'yellow',
  allowedFloors: ['B2', '8'],
  countMode: 'ignore',
};

test('maintenance identity requires the configured badge and allowed floor', () => {
  const valid = verifyPassengerIdentity(maintenance, { badge: 'yellow', requestedFloor: '8' });
  assert.equal(valid.valid, true);
  assert.deepEqual(valid.conflicts, []);

  const wrongBadge = verifyPassengerIdentity(maintenance, { badge: 'red', requestedFloor: '8' });
  assert.equal(wrongBadge.valid, false);
  assert.deepEqual(wrongBadge.conflicts, ['badge']);
});

test('passenger count follows countMode instead of visual headcount', () => {
  const passenger = { id: 'resident_001', countMode: 'normal' };
  assert.equal(countPassengersForPanel([maintenance, passenger]), 1);
});
