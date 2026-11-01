import assert from 'node:assert/strict';
import test from 'node:test';

import {
  AUDIO_LAYERS,
  getAudioLayer,
  isAudioMuted,
  playLayer,
  setAudioMuted,
  toggleAudioMuted,
} from '../src/audio.js';

test('audio layers separate game feedback categories', () => {
  assert.deepEqual(Object.keys(AUDIO_LAYERS), [
    'button',
    'success',
    'error',
    'anomaly',
    'warning',
    'failure',
    'revive',
    'restart',
  ]);
  assert.equal(getAudioLayer('button').kind, 'beep');
  assert.equal(getAudioLayer('error').kind, 'beep');
  assert.equal(getAudioLayer('anomaly').kind, 'sweep');
  assert.equal(getAudioLayer('failure').kind, 'sweep');
  assert.equal(getAudioLayer('revive').kind, 'sweep');
});

test('audio mute gate prevents layer playback and can be toggled', () => {
  setAudioMuted(false);
  assert.equal(isAudioMuted(), false);
  assert.equal(toggleAudioMuted(), true);
  assert.equal(isAudioMuted(), true);
  assert.equal(playLayer('button'), false);
  assert.equal(setAudioMuted(false), false);
  assert.equal(isAudioMuted(), false);
});

test('unknown audio layer is ignored instead of throwing', () => {
  setAudioMuted(false);
  assert.equal(getAudioLayer('missing'), null);
  assert.equal(playLayer('missing'), false);
});
