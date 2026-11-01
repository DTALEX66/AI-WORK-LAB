import assert from 'node:assert/strict';
import test from 'node:test';
import { readFileSync } from 'node:fs';

const readJson = path => JSON.parse(readFileSync(new URL(`../${path}`, import.meta.url), 'utf8'));

const schemaFiles = [
  'schemas/protocol.schema.json',
  'schemas/normal-shift.schema.json',
  'schemas/anomaly-content.schema.json',
  'schemas/event-chain.schema.json',
  'schemas/passenger.schema.json',
  'schemas/ending.schema.json',
];
const contentFiles = [
  'src/content/protocols.json',
  'src/content/normalShifts.json',
  'src/content/anomalies.json',
  'src/content/eventChains.json',
  'src/content/passengers.json',
  'src/content/endings.json',
];

test('all V5 Phase A schemas are valid self-contained JSON schemas', () => {
  for (const path of schemaFiles) {
    const schema = readJson(path);
    assert.equal(schema.$schema, 'https://json-schema.org/draft/2020-12/schema');
    assert.equal(schema.type, 'object');
    assert.ok(Array.isArray(schema.required));
    assert.equal(schema.additionalProperties, false);
  }
});

test('all V5 content containers exist as JSON arrays', () => {
  for (const path of contentFiles) assert.ok(Array.isArray(readJson(path)), path);
});

test('anomaly schema requires evidence, protocol, contamination and silent-play fields', () => {
  const schema = readJson('schemas/anomaly-content.schema.json');
  for (const field of ['screenData', 'panelData', 'primaryConflict', 'decision', 'explanation',
    'resolutionAction', 'availableTools', 'protocolTags', 'contaminationEffects', 'silentEvidence']) {
    assert.ok(schema.required.includes(field), field);
  }
});
