import test from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, mkdirSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import vm from 'node:vm';

const root = resolve(import.meta.dirname, '..');
const output = resolve(root, 'wechat-minigame', 'game.js');
const douyinOutput = resolve(root, 'douyin-minigame', 'game.js');
const douyinProjectOutput = resolve(root, 'douyin-minigame', 'project.config.json');
const douyinGameConfigOutput = resolve(root, 'douyin-minigame', 'game.json');
const douyinPrivateConfigOutput = resolve(root, 'douyin-minigame', 'project.private.config.json');
const privateConfigOutput = resolve(root, 'wechat-minigame', 'project.private.config.json');
const tempDir = resolve(root, '.tmp');
const tempReleaseConfig = resolve(tempDir, 'release-test.config.json');
const trackedDouyinProjectConfig = readFileSync(douyinProjectOutput);
const restoreTrackedDouyinProjectConfig = () => {
  writeFileSync(douyinProjectOutput, trackedDouyinProjectConfig);
};

test.after(restoreTrackedDouyinProjectConfig);
process.on('exit', restoreTrackedDouyinProjectConfig);

test('wechat build output is deterministic across repeated runs', () => {
  execFileSync(process.execPath, ['build.js', 'wechat'], { cwd: root, stdio: 'pipe' });
  const first = readFileSync(output, 'utf8');

  execFileSync(process.execPath, ['build.js', 'wechat'], { cwd: root, stdio: 'pipe' });
  const second = readFileSync(output, 'utf8');

  assert.equal(second, first);
});

test('generated mini-game bundle injects deterministic V5 content containers', () => {
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const first = readFileSync(douyinOutput, 'utf8');
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const second = readFileSync(douyinOutput, 'utf8');

  assert.equal(second, first, 'content injection must not make repeated builds drift');
  assert.match(first, /\/\/ --- V5 content \(deterministic\) ---\nvar __V5_CONTENT__ = /);

  const bundle = first.replace(
    'startMiniGame();\n})();',
    'globalThis.__bundleContent = __V5_CONTENT__;\n})();',
  );
  const sandbox = vm.createContext({ console, Promise, setTimeout, clearTimeout });
  vm.runInContext(bundle, sandbox, { filename: 'douyin-minigame/game.js' });

  assert.deepEqual(Object.keys(sandbox.__bundleContent), [
    'anomalies', 'endings', 'eventChains', 'normalShifts', 'passengers', 'protocols',
  ]);
  assert.equal(sandbox.__bundleContent.anomalies.length, 30);
  assert.equal(sandbox.__bundleContent.normalShifts.length, 10);
  assert.equal(sandbox.__bundleContent.passengers.length, 5);
  assert.equal(sandbox.__bundleContent.protocols.length, 6);
});

test('generated mini-game bundle isolates module lexical scopes and remains executable', () => {
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const rawBundle = readFileSync(douyinOutput, 'utf8');

  assert.match(
    rawBundle,
    /\/\/ --- src\/protocolEngine\.js ---\nvar __exports_src_protocolEngine_js = \{\};\n\{\n/,
    'each source module should have its own lexical block so private names cannot collide',
  );

  const bundle = rawBundle.replace(
    'startMiniGame();\n})();',
    'globalThis.__bundleTest = { createInitialState, createInvestigationState, createRuntimeSession, content: __V5_CONTENT__ };\n})();',
  );
  const sandbox = vm.createContext({ console, Promise, setTimeout, clearTimeout });
  vm.runInContext(bundle, sandbox, { filename: 'douyin-minigame/game.js' });

  const state = sandbox.__bundleTest.createInitialState();
  const investigation = sandbox.__bundleTest.createInvestigationState({ power: 64 });
  assert.equal(state.result, 'playing');
  assert.equal(investigation.power, 64);
  const session = sandbox.__bundleTest.createRuntimeSession({
    content: sandbox.__bundleTest.content,
    random: () => 0,
  });
  assert.equal(session.state.night.activeProtocols.length, 3);
  assert.equal(session.state.night.currentShift.id, 'normal_shift_01');
  assert.equal(session.state.night.roundType, 'investigation');
});

test('release config can inject private AppID into generated files', () => {
  mkdirSync(tempDir, { recursive: true });
  writeFileSync(tempReleaseConfig, JSON.stringify({
    wechat: {
      appid: 'wx_real_release_test_appid',
      projectname: 'MINIGAME_TEST',
    },
  }, null, 2));

  try {
    execFileSync(process.execPath, ['build.js', 'wechat'], {
      cwd: root,
      env: { ...process.env, RELEASE_CONFIG_PATH: tempReleaseConfig },
      stdio: 'pipe',
    });

    const bundle = readFileSync(output, 'utf8');
    const privateConfig = JSON.parse(readFileSync(privateConfigOutput, 'utf8'));
    const sourceConfig = readFileSync(resolve(root, 'src/gameConfig.js'), 'utf8');
    const gitignore = readFileSync(resolve(root, '.gitignore'), 'utf8');

    assert.equal(privateConfig.appid, 'wx_real_release_test_appid');
    assert.equal(privateConfig.projectname, 'MINIGAME_TEST');
    assert.match(gitignore, /release\.config\.json/);
    assert.match(gitignore, /wechat-minigame\/project\.private\.config\.json/);
  } finally {
    if (existsSync(privateConfigOutput)) rmSync(privateConfigOutput, { force: true });
    if (existsSync(tempReleaseConfig)) rmSync(tempReleaseConfig, { force: true });
    execFileSync(process.execPath, ['build.js', 'wechat'], { cwd: root, stdio: 'pipe' });
  }
});

test('douyin build emits a tracked import-ready project with target-specific metadata', () => {
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const first = readFileSync(douyinOutput, 'utf8');
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const second = readFileSync(douyinOutput, 'utf8');
  const project = JSON.parse(readFileSync(douyinProjectOutput, 'utf8'));
  const game = JSON.parse(readFileSync(douyinGameConfigOutput, 'utf8'));
  const gitignore = readFileSync(resolve(root, '.gitignore'), 'utf8');

  assert.equal(second, first);
  assert.match(second, /MINIGAME - 抖音 小游戏构建/);
  assert.equal(project.compileType, 'game');
  const localReleaseConfigPath = resolve(root, 'release.config.json');
  const expectedAppId = existsSync(localReleaseConfigPath)
    ? JSON.parse(readFileSync(localReleaseConfigPath, 'utf8')).douyin?.appid || 'touristappid'
    : 'touristappid';
  assert.equal(project.appid, expectedAppId);
  assert.equal(project.miniprogramRoot, './');
  assert.equal(game.deviceOrientation, 'portrait');
  assert.equal(game.showStatusBar, false);
  assert.doesNotMatch(gitignore, /^douyin-minigame\/$/m, 'the release project itself must be tracked');
  assert.match(gitignore, /douyin-minigame\/project\.private\.config\.json/);
});

test('douyin release build injects private AppID', () => {
  mkdirSync(tempDir, { recursive: true });
  writeFileSync(tempReleaseConfig, JSON.stringify({
    douyin: {
      appid: 'tt_real_release_test_appid',
      projectname: 'MINIGAME_DOUYIN_TEST',
    },

  }, null, 2));

  try {
    execFileSync(process.execPath, ['build.js', 'douyin'], {
      cwd: root,
      env: { ...process.env, RELEASE_CONFIG_PATH: tempReleaseConfig },
      stdio: 'pipe',
    });
    const bundle = readFileSync(douyinOutput, 'utf8');
    const privateConfig = JSON.parse(readFileSync(douyinPrivateConfigOutput, 'utf8'));
    const projectConfig = JSON.parse(readFileSync(douyinProjectOutput, 'utf8'));

    assert.doesNotMatch(bundle, /adunit-|releaseMode|ttad-/, 'boundary: no ad/release semantics in bundle');
    assert.doesNotMatch(bundle, /releaseMode|adunit-/, 'boundary: no ad/release semantics in bundle');
    assert.equal(privateConfig.appid, 'tt_real_release_test_appid');
    assert.equal(projectConfig.appid, 'tt_real_release_test_appid');
    assert.equal(privateConfig.projectname, 'MINIGAME_DOUYIN_TEST');
  } finally {
    if (existsSync(douyinPrivateConfigOutput)) rmSync(douyinPrivateConfigOutput, { force: true });
    if (existsSync(tempReleaseConfig)) rmSync(tempReleaseConfig, { force: true });
    execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  }
});
