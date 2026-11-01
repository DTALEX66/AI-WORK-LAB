import assert from 'node:assert/strict';
import test from 'node:test';

import {
  advanceEventChain,
  createEventChainState,
  getCurrentEventStep,
} from '../src/eventChainEngine.js';

const chain = {
  id: 'duplicate_passenger',
  initialFlags: [],
  steps: [
    { id: 'first_visit', onWrongFlags: ['trusted_duplicate'] },
    { id: 'repeated_motion', onWrongFlags: ['motion_ignored'] },
    { id: 'simultaneous_presence', onWrongFlags: ['chain_compromised'] },
  ],
  consequences: [{ flag: 'chain_compromised', contaminationDelta: 18 }],
};

test('event chain advances one stage and preserves wrong-decision consequences', () => {
  const initial = createEventChainState([chain]);
  const first = advanceEventChain(initial, chain, { correct: false });

  assert.equal(first.state.chains.duplicate_passenger.stepIndex, 1);
  assert.ok(first.state.flags.includes('trusted_duplicate'));
  assert.equal(getCurrentEventStep(first.state, chain).id, 'repeated_motion');
});

test('event chain completion emits configured long-term consequences', () => {
  let state = createEventChainState([chain]);
  state = advanceEventChain(state, chain, { correct: true }).state;
  state = advanceEventChain(state, chain, { correct: true }).state;
  const completed = advanceEventChain(state, chain, { correct: false });

  assert.equal(completed.completed, true);
  assert.ok(completed.state.flags.includes('chain_compromised'));
  assert.deepEqual(completed.consequences, chain.consequences);
});
