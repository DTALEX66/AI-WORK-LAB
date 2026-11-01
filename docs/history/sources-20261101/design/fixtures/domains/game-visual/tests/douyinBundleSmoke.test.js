import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { readFileSync } from 'node:fs';
import test from 'node:test';
import vm from 'node:vm';
import { resolve } from 'node:path';

const root = resolve(import.meta.dirname, '..');

test('generated Douyin bundle boots against the tt Canvas contract', () => {
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const bundle = readFileSync(resolve(root, 'douyin-minigame', 'game.js'), 'utf8');
  const text = [];
  const imageSources = [];
  let drawImageCalls = 0;
  const gradient = { addColorStop() {} };
  const ctx = new Proxy({
    measureText(value) { return { width: String(value).length * 16 }; },
    fillText(value) { text.push(String(value)); },
    drawImage() { drawImageCalls += 1; },
    createLinearGradient() { return gradient; },
    createRadialGradient() { return gradient; },
  }, {
    get(target, key) {
      if (key in target) return target[key];
      return () => {};
    },
    set(target, key, value) {
      target[key] = value;
      return true;
    },
  });
  const canvas = { width: 0, height: 0, getContext: () => ctx };
  let onTouchStart;
  let onHide;
  let onShow;
  let sidebarOptions;
  let nextFrame;
  let now = 1_000;
  const tt = {
    createCanvas: () => canvas,
    getSystemInfoSync: () => ({ windowWidth: 390, windowHeight: 844, safeArea: { top: 47 } }),
    requestAnimationFrame(callback) { nextFrame = callback; return 1; },
    onTouchStart(callback) { onTouchStart = callback; },
    onHide(callback) { onHide = callback; },
    onShow: fn => { onShow = fn; },
    checkScene: options => options.success?.({ isExist: true }),
    navigateToScene: options => { sidebarOptions = options; options.success?.({}); },
    createImage() {
      const image = { onload: null, onerror: null, _src: '' };
      Object.defineProperty(image, 'src', {
        set(value) { image._src = value; imageSources.push(value); image.onload?.(); },
        get() { return image._src; },
      });
      return image;
    },
    createInnerAudioContext() {
      return { play() {}, stop() {}, seek() {}, destroy() {} };
    },
  };
  const sandbox = vm.createContext({
    tt,
    console,
    Date: { now: () => now },
    Promise,
    setTimeout,
    clearTimeout,
  });
  vm.runInContext(bundle, sandbox, { filename: 'douyin-minigame/game.js' });

  assert.equal(canvas.width, 750);
  assert.ok(canvas.height > 1623 && canvas.height < 1624);
  assert.equal(typeof onTouchStart, 'function');
  assert.equal(typeof onHide, 'function');
  assert.equal(typeof onShow, 'function');
  assert.equal(typeof nextFrame, 'function');
  assert.ok(text.includes('异常电梯'));
  assert.ok(text.includes('夜班值守许可'));
  assert.ok(text.includes('开始接管'));
  assert.ok(text.includes('侧边栏入口'));
  assert.equal(imageSources.length, 46, 'all shipped Canvas visual assets should preload');
  assert.ok(imageSources.includes('visual/cctv/00_idle_closed_mobile.png'));
  assert.ok(imageSources.includes('visual/cctv/v5_02_investigation_mobile.png'));
  assert.ok(imageSources.includes('visual/buttons/btn_stop_danger.png'));
  assert.ok(drawImageCalls >= 1, 'the first render should draw the production CCTV state');

  onTouchStart({ touches: [{ screenX: 375 * 390 / 750, screenY: 1075 * 844 / canvas.height }] });
  assert.equal(sidebarOptions?.scene, 'sidebar');
  onTouchStart({ touches: [{ screenX: 375 * 390 / 750, screenY: 962 * 844 / canvas.height }] });
  // 第一班教学：画面与数据一致，点击放行。
  onTouchStart({ touches: [{ screenX: 199 * 390 / 750, screenY: 1323 * 844 / canvas.height }] });
  now += 8_000;
  nextFrame();
  assert.ok(text.includes('封锁'), 'first anomaly should expose the simple lockdown decision');
  assert.ok(text.includes('放行'), 'release and lockdown choices should stay paired');
  // 第二班教学：封锁后应由系统自动处置，不出现第二层玩家按钮。
  onTouchStart({ touches: [{ screenX: 551 * 390 / 750, screenY: 1323 * 844 / canvas.height }] });
  nextFrame();
  assert.ok(text.includes('封锁成功，系统已自动处置'));
  assert.ok(text.includes('等待下一班'));
  onHide();
  onShow({ scene: '021036' });
});

test('generated Douyin bundle keeps tutorial order and auto-isolates timed-out anomalies', () => {
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const bundle = readFileSync(resolve(root, 'douyin-minigame', 'game.js'), 'utf8');
  const text = [];
  const gradient = { addColorStop() {} };
  const ctx = new Proxy({
    measureText(value) { return { width: String(value).length * 16 }; },
    fillText(value) { text.push(String(value)); },
    drawImage() {},
    createLinearGradient() { return gradient; },
    createRadialGradient() { return gradient; },
  }, {
    get(target, key) { return key in target ? target[key] : () => {}; },
    set(target, key, value) { target[key] = value; return true; },
  });
  const canvas = { width: 0, height: 0, getContext: () => ctx };
  let onTouchStart;
  let nextFrame;
  let now = 1_000;
  const tt = {
    createCanvas: () => canvas,
    getSystemInfoSync: () => ({ windowWidth: 390, windowHeight: 844, safeArea: { top: 47 } }),
    requestAnimationFrame(callback) { nextFrame = callback; return 1; },
    onTouchStart(callback) { onTouchStart = callback; },
    onHide() {}, onShow() {},
    checkScene: options => options.success?.({ isExist: false }),
    createImage() {
      const image = { onload: null };
      Object.defineProperty(image, 'src', { set() { image.onload?.(); } });
      return image;
    },
    createInnerAudioContext: () => ({ play() {}, stop() {}, seek() {}, destroy() {} }),
  };
  vm.runInContext(bundle, vm.createContext({
    tt, console, Date: { now: () => now }, Promise, setTimeout, clearTimeout,
  }), { filename: 'douyin-minigame/game.js' });

  onTouchStart({ touches: [{ screenX: 375 * 390 / 750, screenY: 962 * 844 / canvas.height }] });
  text.length = 0;
  now += 6_000;
  nextFrame();
  assert.ok(text.some(line => line.includes('再看一眼')), 'first guided timeout should coach without punishment');

  text.length = 0;
  now += 2_000;
  nextFrame();
  assert.ok(text.includes('发现矛盾，点击封锁'), 'second class must still be the fixed anomaly lesson');
  // V4: 始终显示实际楼层，不再混淆画面楼层。
  // 画面楼层角标与面板数据一致，玩家通过画面与数据的全局检查发现矛盾。
  assert.ok(text.includes('05'), 'floor-jump should show floor 05 in the badge');

  text.length = 0;
  now += 5_000;
  nextFrame();
  assert.ok(text.includes('判断超时，系统已自动隔离'), 'timed-out anomaly must be auto-isolated');
  assert.ok(text.includes('等待下一班'), 'scheduler must not remain blocked by activeAnomaly');

  text.length = 0;
  now += 2_000;
  nextFrame();
  assert.ok(text.includes('放行') && text.includes('封锁'));
  assert.equal(text.includes('点这里'), false, 'third class must be an unprompted independent judgment');
});

test('generated Douyin bundle settles rewarded-ad completion, cancellation, error and stale guards safely', async () => {
  execFileSync(process.execPath, ['build.js', 'douyin'], { cwd: root, stdio: 'pipe' });
  const rawBundle = readFileSync(resolve(root, 'douyin-minigame', 'game.js'), 'utf8');
  assert.match(rawBundle, /function shouldApplyReward\s*\(/, 'reward guard must be present in the generated bundle');
  const bundle = rawBundle.replace(
    'startMiniGame();\n})();',
    'globalThis.__bundleTest = { createMiniGameRewardedAd, shouldApplyReward };\n})();',
  );
  const sandbox = vm.createContext({ console, Promise, setTimeout, clearTimeout });
  vm.runInContext(bundle, sandbox, { filename: 'douyin-minigame/game.js' });
  const { createMiniGameRewardedAd, shouldApplyReward } = sandbox.__bundleTest;

  let hostAdCalls = 0;
  const api = {
    createRewardedVideoAd() {
      hostAdCalls += 1;
      throw new Error('boundary: host rewarded-video APIs must not be used');
    },
  };
  let rewards = 0;
  let errors = 0;
  let starts = 0;
  let settlements = 0;
  const show = createMiniGameRewardedAd(api, 'revive', {
    onReward: () => { rewards += 1; },
    onError: () => { errors += 1; },
    onStart: () => { starts += 1; },
    onSettled: () => { settlements += 1; },
  });

  await show({ runToken: 1 });
  await show({ runToken: 2 });
  await show({ runToken: 3 });

  assert.equal(hostAdCalls, 0, 'free reward must not touch host ad APIs');
  assert.deepEqual({ rewards, errors, starts, settlements }, {
    rewards: 3, errors: 0, starts: 3, settlements: 3,
  });
  assert.equal(shouldApplyReward(
    { context: { runToken: 7 } }, 7, 'revive', { gameOver: true, result: 'failure' },
  ), true);
  assert.equal(shouldApplyReward(
    { context: { runToken: 6 } }, 7, 'revive', { gameOver: true, result: 'failure' },
  ), false, 'stale run callbacks must not apply rewards');
});
