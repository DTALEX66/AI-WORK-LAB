import assert from 'node:assert/strict';
import test from 'node:test';

import {
  compareCoreEvidence,
  evaluateEvidence,
  evaluateInvestigationEvidence,
  isEvidenceJudgeableWithoutAudio,
} from '../src/evidenceEngine.js';

test('one tool clue is insufficient but two independent sources can corroborate a conflict', () => {
  const thermalOnly = evaluateInvestigationEvidence([
    { id: 'thermal_none', source: 'thermal', conflictKey: 'presence', observation: '未检测到生命热源。', contradicts: true },
  ]);
  assert.equal(thermalOnly.ready, false);
  assert.equal(thermalOnly.decision, null);

  const corroborated = evaluateInvestigationEvidence([
    { id: 'thermal_none', source: 'thermal', conflictKey: 'presence', observation: '未检测到生命热源。', contradicts: true },
    { id: 'cam03_empty', source: 'cam03', conflictKey: 'presence', observation: '电梯厅没有入梯记录。', contradicts: true },
  ]);
  assert.equal(corroborated.ready, true);
  assert.equal(corroborated.decision, 'lockdown');
  assert.deepEqual(corroborated.verificationPaths, ['cam03', 'thermal']);
});

test('matching floor passenger and door evidence is normal', () => {
  const data = { floor: 3, passengers: 1, door: 'closed' };
  assert.deepEqual(compareCoreEvidence(data, data), []);
  assert.equal(evaluateEvidence({ screenData: data, panelData: data }).decision, 'release');
});

test('single-field contradiction names the exact conflicting field', () => {
  const result = evaluateEvidence({
    screenData: { floor: 3, passengers: 1, door: 'closed' },
    panelData: { floor: 3, passengers: 0, door: 'closed' },
  });

  assert.equal(result.decision, 'lockdown');
  assert.deepEqual(result.conflicts.map(item => item.field), ['passengers']);
  assert.match(result.explanation, /人数/);
});

test('audio cue is never the only verification path', () => {
  const shift = {
    screenData: { floor: 3, passengers: 1, door: 'closed' },
    panelData: { floor: 3, passengers: 0, door: 'closed' },
    audioCue: 'weight_sensor',
    evidence: { cameras: ['cam01'], tools: [] },
  };
  assert.equal(isEvidenceJudgeableWithoutAudio(shift), true);
});

test('evidence evaluation does not reveal the answer through visual tone', () => {
  const result = evaluateEvidence({
    screenData: { floor: 4, passengers: 0, door: 'open' },
    panelData: { floor: 4, passengers: 0, door: 'closed' },
  });
  assert.equal(result.presentationTone, 'neutral');
  assert.equal(result.highlightConflictBeforeDecision, false);
});
