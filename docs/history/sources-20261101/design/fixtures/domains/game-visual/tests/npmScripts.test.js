import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

const pkg = JSON.parse(readFileSync(new URL('../package.json', import.meta.url), 'utf8'));
const launcher = readFileSync(new URL('../scripts/run-tests.cjs', import.meta.url), 'utf8');
const previewScript = readFileSync(new URL('../scripts/preview-server.mjs', import.meta.url), 'utf8');

test('npm test uses a Node16-compatible launcher', () => {
  assert.equal(pkg.scripts.test, 'node scripts/run-tests.cjs');
  assert.match(launcher, /findModernNode/, 'launcher should locate a modern bundled Node');
  assert.match(launcher, /LOCALAPPDATA/, 'launcher should support Hermes bundled Node on Windows');
  assert.match(launcher, /--test/, 'launcher should invoke the real node:test runner');
  assert.match(launcher, /--test-concurrency=1/, 'launcher should serialize build-output tests to avoid generated-bundle races');
});

test('android inspect script verifies APK launcher metadata', () => {
  const inspectScript = readFileSync(new URL('../scripts/check-apk-metadata.mjs', import.meta.url), 'utf8');

  assert.equal(pkg.scripts['android:inspect'], 'node scripts/check-apk-metadata.mjs');
  assert.match(inspectScript, /dump', 'badging'/, 'script should inspect APK badging via aapt');
  assert.match(inspectScript, /application-label:'\$\{expected\.label\}'/, 'script should assert launcher label');
  assert.match(inspectScript, /launcher icon is branded ic_launcher resource/, 'script should assert launcher icon resource');
});

test('preview server anchors static files to its runtime root', () => {
  assert.doesNotMatch(previewScript, /resolve\(process\.cwd\(\)\)/, 'preview should not depend on caller cwd');
  assert.match(previewScript, /fileURLToPath\(new URL\('\.\.', import\.meta\.url\)\)/, 'preview should derive root from its own entrypoint');
});

test('verify script runs the full release acceptance gate', () => {
  const verifyScript = readFileSync(new URL('../scripts/verify-all.cjs', import.meta.url), 'utf8');

  assert.equal(pkg.scripts.verify, 'node scripts/verify-all.cjs');
  assert.equal(pkg.scripts['verify:summary'], 'node scripts/verify-all.cjs --summary');
  assert.match(verifyScript, /const RUNTIME_ROOT = join\(__dirname, '\.\.'\)/, 'verify should anchor commands to the runtime root');
  assert.match(verifyScript, /cwd: RUNTIME_ROOT/, 'verify should not depend on the caller cwd');
  assert.doesNotMatch(verifyScript, /npmCommand/, 'verify should avoid spawning npm.cmd inside Git Bash on Windows');
  assert.match(verifyScript, /modern\.executable, \['scripts\/run-tests\.cjs'\]/, 'verify should run tests through the modern Node launcher');
  assert.match(verifyScript, /--summary/, 'verify should support a compact summary mode');
  assert.match(verifyScript, /\[verify\] tests: pass/, 'summary mode should print test result line');
  assert.match(verifyScript, /\[verify\] wechat strict: 0 blocker/, 'summary mode should print strict bundle result line');
  assert.match(verifyScript, /\[verify\] android build: OK/, 'summary mode should print Android build result line');
  assert.match(verifyScript, /\[verify\] apk metadata: OK/, 'summary mode should print APK metadata result line');
  assert.match(verifyScript, /\['build\.js', 'wechat'\]/, 'verify should build WeChat bundle');
  assert.match(verifyScript, /check-wechat-bundle\.mjs', '--strict'/, 'verify should run WeChat strict check');
  assert.match(verifyScript, /\['build\.js', 'douyin'\]/, 'verify should build Douyin bundle');
  assert.match(verifyScript, /check-douyin-bundle\.mjs', '--strict'/, 'verify should run Douyin strict check');
  assert.match(verifyScript, /build-android-debug\.mjs/, 'verify should build Android APK');
  assert.match(verifyScript, /check-apk-metadata\.mjs/, 'verify should inspect APK metadata');
  assert.match(verifyScript, /Android debug APK build: BLOCKED/, 'missing Android tooling must block acceptance');
  assert.match(verifyScript, /process\.exitCode = 2/, 'blocked Android acceptance must return a non-zero exit code');
});

test('Douyin scripts provide build and strict validation commands', () => {
  assert.equal(pkg.scripts['douyin:build'], 'node build.js douyin');
  assert.equal(pkg.scripts['douyin:check'], 'node scripts/check-douyin-bundle.mjs --strict');
  assert.equal(pkg.scripts['douyin:compliance'], undefined, 'release compliance commands are removed (fixture boundary)');
  assert.equal(pkg.scripts['douyin:release:check'], undefined, 'release commands are removed (fixture boundary)');
  assert.equal(pkg.scripts['douyin:package'], undefined, 'release commands are removed (fixture boundary)');
  assert.equal(pkg.scripts['release:check'], undefined, 'release commands are removed (fixture boundary)');
});

test('release gate scripts are removed under fixture boundary', () => {
  // Taskpack H2: release/publish commands and their gate scripts are removed
  // from the game-visual fixture; only build/verify commands remain.
  assert.equal(pkg.scripts['release:check'], undefined);
  assert.equal(pkg.scripts['douyin:package'], undefined);
  const releaseScript = new URL('../scripts/check-release-readiness.mjs', import.meta.url);
  assert.throws(() => readFileSync(releaseScript, 'utf8'), 'release gate script should be removed');
});
