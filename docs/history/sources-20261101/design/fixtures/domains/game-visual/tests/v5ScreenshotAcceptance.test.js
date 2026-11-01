import test from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

function readPngSize(path) {
  const png = readFileSync(path);
  assert.equal(png.subarray(1, 4).toString('ascii'), 'PNG');
  return { width: png.readUInt32BE(16), height: png.readUInt32BE(20) };
}

test('V5 acceptance harness and official portrait runtime captures are checked in', () => {
  const harness = resolve(root, 'scripts', 'v5-canvas-acceptance.html');
  assert.ok(existsSync(harness), 'production Canvas acceptance harness must exist');

  for (const [name, expected] of [
    ['v5-runtime-393x852.png', { width: 393, height: 852 }],
    ['v5-runtime-360x640.png', { width: 360, height: 640 }],
    ['v5-runtime-identity-393x852.png', { width: 393, height: 852 }],
    ['v5-runtime-identity-360x640.png', { width: 360, height: 640 }],
    ['v5-runtime-high-risk-393x852.png', { width: 393, height: 852 }],
    ['v5-runtime-high-risk-360x640.png', { width: 360, height: 640 }],
    ['v5-runtime-protocol-query-393x852.png', { width: 393, height: 852 }],
    ['v5-runtime-protocol-query-360x640.png', { width: 360, height: 640 }],
    ['v5-runtime-debrief-393x852.png', { width: 393, height: 852 }],
    ['v5-runtime-debrief-360x640.png', { width: 360, height: 640 }],
  ]) {
    const capture = resolve(root, 'docs', 'screenshots', name);
    assert.ok(existsSync(capture), `${name} must be captured from the runtime renderer`);
    assert.deepEqual(readPngSize(capture), expected);
  }
});
