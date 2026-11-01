import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

test('wechat bundle regression check passes with no runtime blockers', () => {
  execFileSync(process.execPath, ['build.js', 'wechat'], { cwd: root, stdio: 'pipe' });
  const result = spawnSync(process.execPath, ['scripts/check-wechat-bundle.mjs'], {
    cwd: root,
    encoding: 'utf8',
  });

  assert.equal(result.status, 0);
  assert.match(result.stdout, /domDependency/);
  assert.match(result.stdout, /windowDependency/);
  assert.match(result.stdout, /hiddenLogAlias/);
  assert.match(result.stdout, /canvasRenderer/);
  assert.match(result.stdout, /0 blocker\(s\)/);
});

test('wechat bundle strict check succeeds for Canvas mini-game runtime', () => {
  execFileSync(process.execPath, ['build.js', 'wechat'], { cwd: root, stdio: 'pipe' });
  const result = spawnSync(process.execPath, ['scripts/check-wechat-bundle.mjs', '--strict'], {
    cwd: root,
    encoding: 'utf8',
  });

  assert.equal(result.status, 0);
  assert.doesNotMatch(result.stdout, /BLOCKER/);
  assert.match(result.stdout, /0 blocker\(s\)/);
});
