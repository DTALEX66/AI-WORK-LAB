import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import test from 'node:test';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

test('douyin strict checker accepts the generated Canvas project', () => {
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const output = execFileSync(process.execPath, ['scripts/check-douyin-bundle.mjs', '--strict'], {
    cwd: root,
    encoding: 'utf8',
  });
  assert.match(output, /runtime blocker\(s\): 0/);
  assert.match(output, /packageBytes/);
});

test('Douyin release package script is removed under fixture boundary', () => {
  // Taskpack H2: release/package scripts are removed; only build/check remain.
  assert.throws(
    () => readFileSync(resolve(root, 'scripts', 'package-douyin-release.mjs'), 'utf8'),
    'package-douyin-release.mjs should be removed (fixture boundary)'
  );
});

test('douyin strict checker rejects a known-broken project', () => {
  const broken = resolve(root, '.tmp', 'douyin-broken');
  rmSync(broken, { recursive: true, force: true });
  mkdirSync(broken, { recursive: true });
  writeFileSync(resolve(broken, 'game.js'), 'tt.createCanvas();');
  writeFileSync(resolve(broken, 'game.json'), JSON.stringify({ deviceOrientation: 'portrait' }));
  writeFileSync(resolve(broken, 'project.config.json'), JSON.stringify({ compileType: 'game', appid: 'touristappid' }));

  assert.throws(() => execFileSync(process.execPath, ['scripts/check-douyin-bundle.mjs', '--strict'], {
    cwd: root,
    env: { ...process.env, DOUYIN_PROJECT_DIR: broken },
    stdio: 'pipe',
  }));
  rmSync(broken, { recursive: true, force: true });
});
