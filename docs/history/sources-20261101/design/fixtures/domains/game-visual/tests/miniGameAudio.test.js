import assert from 'node:assert/strict';
import test from 'node:test';

import { createMiniGameAudio, getV5FeedbackProfile } from '../platform/miniGameAudio.js';

test('mini-game audio maps semantic cues to bundled local files', () => {
  const played = [];
  const api = {
    createInnerAudioContext() {
      return {
        set src(value) { this._src = value; },
        get src() { return this._src; },
        play() { played.push(this.src); },
        stop() {},
        destroy() {},
      };
    },
  };
  const audio = createMiniGameAudio(api);
  for (const cue of ['click', 'anomaly', 'result', 'boot', 'release', 'lockdown', 'motor', 'wrong']) {
    assert.equal(audio.play(cue), true);
  }
  assert.deepEqual(played, [
    'audio/click.wav', 'audio/anomaly.wav', 'audio/result.wav', 'audio/boot.wav',
    'audio/release.wav', 'audio/lockdown.wav', 'audio/motor.wav', 'audio/wrong.wav',
  ]);
});

test('mini-game music uses one dedicated looping context and switches tracks without overlap', () => {
  const contexts = [];
  const api = {
    createInnerAudioContext() {
      const context = {
        autoplay: false, loop: false, volume: 1, src: '',
        plays: 0, pauses: 0, stops: 0,
        play() { this.plays += 1; },
        pause() { this.pauses += 1; },
        stop() { this.stops += 1; },
        seek() {}, destroy() {},
      };
      contexts.push(context);
      return context;
    },
  };
  const audio = createMiniGameAudio(api);
  assert.equal(audio.setMusicState('calm'), true);
  assert.equal(contexts.length, 1);
  assert.equal(contexts[0].loop, true);
  assert.equal(contexts[0].src, 'audio/bgm-night-shift-loop.wav');
  assert.equal(contexts[0].volume, 0.12);

  assert.equal(audio.setMusicState('pressure'), true);
  assert.equal(contexts.length, 1, 'track switch must reuse the dedicated music context');
  assert.equal(contexts[0].src, 'audio/bgm-anomaly-pressure-loop.wav');
  assert.ok(contexts[0].stops >= 1, 'old loop must stop before pressure music starts');
});

test('music pause resume and mute are linked without double playback', () => {
  const context = { playCount: 0, pauseCount: 0, stopCount: 0, play() { this.playCount += 1; }, pause() { this.pauseCount += 1; }, stop() { this.stopCount += 1; }, seek() {}, destroy() {} };
  const audio = createMiniGameAudio({ createInnerAudioContext: () => context });
  audio.setMusicState('calm');
  audio.pauseMusic();
  assert.equal(audio.resumeMusic(), true);
  audio.setMuted(true);
  assert.equal(audio.resumeMusic(), false);
  assert.ok(context.pauseCount >= 1);
  assert.ok(context.stopCount >= 1);
});

test('V5 interactions use distinct semantic audio and haptic profiles', () => {
  assert.deepEqual(getV5FeedbackProfile('camera'), { cue: 'click', haptic: 'light' });
  assert.deepEqual(getV5FeedbackProfile('tool:thermal'), { cue: 'anomaly', haptic: 'medium' });
  assert.deepEqual(getV5FeedbackProfile('tool:replay'), { cue: 'motor', haptic: 'light' });
  assert.deepEqual(getV5FeedbackProfile('tool:protocol'), { cue: 'boot', haptic: 'light' });
  assert.deepEqual(getV5FeedbackProfile('classification:enter'), { cue: 'anomaly', haptic: 'medium' });
  assert.deepEqual(getV5FeedbackProfile('classification:correct'), { cue: 'lockdown', haptic: 'medium' });
  assert.deepEqual(getV5FeedbackProfile('classification:wrong'), { cue: 'wrong', haptic: 'heavy' });
  assert.deepEqual(getV5FeedbackProfile('highRisk:correct'), { cue: 'lockdown', haptic: 'heavy' });
  assert.deepEqual(getV5FeedbackProfile('highRisk:wrong'), { cue: 'wrong', haptic: 'heavy' });
});

test('V5 protocol and identity actions have distinct audio semantics', () => {
  assert.notDeepEqual(getV5FeedbackProfile('protocol:close'), getV5FeedbackProfile('camera'));
  assert.deepEqual(getV5FeedbackProfile('identity:verify'), { cue: 'boot', haptic: 'light' });
  assert.deepEqual(getV5FeedbackProfile('identity:correct'), { cue: 'release', haptic: 'medium' });
  assert.deepEqual(getV5FeedbackProfile('identity:wrong'), { cue: 'wrong', haptic: 'heavy' });
});

test('mini-game audio can be muted and fails safely without host audio API', () => {
  const audio = createMiniGameAudio({});
  assert.equal(audio.play('click'), false);
  audio.setMuted(true);
  assert.equal(audio.isMuted(), true);
  assert.equal(audio.play('result'), false);
});
