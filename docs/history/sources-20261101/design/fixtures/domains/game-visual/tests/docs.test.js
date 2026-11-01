import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const rootReadme = readFileSync(new URL('../README.md', import.meta.url), 'utf8');
const androidReadme = readFileSync(new URL('../android-webview/README.md', import.meta.url), 'utf8');

test('root README documents current verification gates', () => {
  assert.match(rootReadme, /npm run verify/, 'README should advertise the one-command development gate');
  assert.doesNotMatch(rootReadme, /\b[0-9]+\/[0-9]+\s*pass\b/, 'README should avoid stale hardcoded test count');
  assert.match(rootReadme, /测试数以实际输出为准/, 'README should direct readers to real verify output');
  assert.match(rootReadme, /android-webview\/app\/build\/outputs\/apk\/debug\/app-debug\.apk/, 'README should point to APK output');
  assert.match(rootReadme, /CCTV 状态.*已移除/, 'README should document the visual fixture after asset removal');
  assert.match(rootReadme, /Game Visual Design Fixture/, 'README should declare the game-visual fixture contract');
  assert.doesNotMatch(rootReadme, /小游戏合集平台/, 'README must not describe a collection platform');
});

test('android README reflects the current portable APK build flow', () => {
  assert.match(androidReadme, /npm run android:build/, 'Android README should use the supported build script');
  assert.match(androidReadme, /npm run android:inspect/, 'Android README should document APK metadata inspection');
  assert.match(androidReadme, /项目内便携工具链可构建/, 'Android README should reflect the verified portable toolchain');
  assert.match(androidReadme, /定制 launcher icon/, 'Android README should mention branded app icon');
  assert.match(androidReadme, /一屏内可玩/, 'Android README should document the one-screen mobile UX');
  assert.doesNotMatch(androidReadme, /当前环境缺少 Android 构建工具/, 'Android README must not keep stale blocker text');
});
