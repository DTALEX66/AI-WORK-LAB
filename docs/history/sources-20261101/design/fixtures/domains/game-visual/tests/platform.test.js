import test from 'node:test';
import assert from 'node:assert/strict';

import { createRewardedAd, env } from '../platform/platform.js';

test('platform detects Node test environment as browser fallback', () => {
  assert.equal(env, 'browser');
});

// MiniGame 边界（DL-MIG）：免费奖励，无广告位/模拟广告/发布模式。
test('free reward grants immediately without ad APIs', async () => {
  let rewarded = false;
  let errors = 0;
  const show = createRewardedAd('revive', {
    onReward: () => { rewarded = true; },
    onError: () => { errors += 1; },
  });
  await show();
  assert.equal(rewarded, true);
  assert.equal(errors, 0);
});

test('free reward settles each attempt once across duplicate shows', async () => {
  let rewards = 0;
  const metas = [];
  const show = createRewardedAd('decode', {
    onReward: (meta) => { rewards += 1; metas.push(meta); },
  });
  await Promise.all([show({ runToken: 1 }), show({ runToken: 1 })]);
  assert.equal(rewards, 2);
  assert.equal(metas[0].context.runToken, 1);
  await show({ runToken: 2 });
  assert.equal(rewards, 3);
});

test('free reward never depends on host rewarded-video APIs', async () => {
  const originalWx = globalThis.wx;
  const originalTt = globalThis.tt;
  delete globalThis.wx;
  delete globalThis.tt;
  try {
    const platform = await import(`../platform/platform.js?free=${Date.now()}`);
    let rewards = 0;
    const show = platform.createRewardedAd('truth', { onReward: () => { rewards += 1; } });
    await show();
    assert.equal(rewards, 1);
  } finally {
    if (originalWx === undefined) delete globalThis.wx;
    else globalThis.wx = originalWx;
    if (originalTt === undefined) delete globalThis.tt;
    else globalThis.tt = originalTt;
  }
});
