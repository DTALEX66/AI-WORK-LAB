import assert from 'node:assert/strict';
import test from 'node:test';

import endings from '../src/content/endings.json' with { type: 'json' };
import {
  buildDebriefTimeline,
  selectNightEnding,
} from '../src/debriefTimeline.js';

test('debrief timeline reports decisions, chain stages and contamination in sequence', () => {
  const report = buildDebriefTimeline({
    decisions: [
      { sequence: 1, contentId: 'normal_shift_01', correct: true, choice: 'release' },
      { sequence: 3, contentId: 'device_camera_substitution', correct: false, choice: 'release' },
    ],
    eventHistory: [{ sequence: 2, chainId: 'camera_replacement', stepId: 'cam07_delay', correct: true }],
    contaminationHistory: [{ sequence: 3, delta: 12, value: 60, reason: 'wrong-decision' }],
  });

  assert.deepEqual(report.timeline.map(item => item.sequence), [1, 2, 3, 3]);
  assert.equal(report.summary.correct, 1);
  assert.equal(report.summary.wrong, 1);
  assert.equal(report.summary.accuracy, 0.5);
  assert.equal(report.summary.peakContamination, 60);
});

test('ending selection is deterministic and honors higher-priority chain consequences', () => {
  const ending = selectNightEnding(endings, {
    contamination: 82,
    accuracy: 0.7,
    flags: ['camera_chain_compromised'],
  });
  assert.equal(ending.id, 'camera_taken');
});
