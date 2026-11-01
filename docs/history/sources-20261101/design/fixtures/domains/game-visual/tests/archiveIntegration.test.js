import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const gameSource = readFileSync(new URL('../src/game.js', import.meta.url), 'utf8');

test('browser archive commit records current skin and normalized anomaly ids', () => {
  assert.match(gameSource, /getArchiveSkinProgress/);
  assert.match(gameSource, /skinId:\s*getSkin\(\)\.meta\?\.id/);
  assert.match(gameSource, /replace\(\/_log\$\//);
});

test('browser archive panel renders current-skin collection progress', () => {
  assert.match(gameSource, /getArchiveSkinProgress\(archive, getSkin\(\)\.meta\?\.id, getAnomalies\(\)\)/);
  assert.match(gameSource, /皮肤进度/);
  assert.match(gameSource, /日志解锁/);
});
