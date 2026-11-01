import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const docs = [
  ['README.md', readFileSync(new URL('../README.md', import.meta.url), 'utf8')],
  ['android-webview/README.md', readFileSync(new URL('../android-webview/README.md', import.meta.url), 'utf8')],
  ['docs/ANDROID_APK_HANDOFF.md', readFileSync(new URL('../docs/ANDROID_APK_HANDOFF.md', import.meta.url), 'utf8')],
];

const requiredCommands = [
  'npm run verify',
  'npm run android:build',
  'npm run android:inspect',
  'npm run android:install',
];

const stalePhrases = [
  '当前环境缺少 Android 构建工具',
  '只有文字监控',
  '需要下拉整页',
];

test('entrypoint docs share current verification and release commands', () => {
  for (const [path, text] of docs) {
    for (const command of requiredCommands) {
      assert.match(text, new RegExp(escapeRegExp(command)), `${path} should mention ${command}`);
    }
  }
});

test('entrypoint docs do not keep stale platform or UX descriptions', () => {
  for (const [path, text] of docs) {
    for (const phrase of stalePhrases) {
      assert.doesNotMatch(text, new RegExp(escapeRegExp(phrase)), `${path} should not contain stale phrase: ${phrase}`);
    }
  }
});

function escapeRegExp(value) {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}
