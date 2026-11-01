import assert from 'node:assert/strict';
import test from 'node:test';

import { createCanvasAssetStore, getCanvasVisualAssetManifest } from '../platform/canvasAssets.js';

test('Canvas visual manifest maps every shipped CCTV state and production component family', () => {
  const manifest = getCanvasVisualAssetManifest();
  assert.equal(Object.keys(manifest.cctv).length, 25);
  assert.equal(Object.keys(manifest.v5Cctv).length, 8);
  assert.equal(manifest.v5Cctv.investigation, 'visual/cctv/v5_02_investigation_mobile.png');
  assert.equal(manifest.cctv['13_entity_near'], 'visual/cctv/13_entity_near_mobile.png');
  assert.equal(manifest.buttons.danger, 'visual/buttons/btn_stop_danger.png');
  assert.equal(manifest.buttons.disabled, 'visual/buttons/btn_disabled.png');
  assert.equal(manifest.overlays.vignette, 'visual/overlays/overlay_vignette.png');
});

test('Canvas asset store preloads real images and exposes loaded state assets', () => {
  const created = [];
  const store = createCanvasAssetStore(() => {
    const image = { onload: null, onerror: null, _src: '' };
    Object.defineProperty(image, 'src', {
      set(value) {
        image._src = value;
        image.onload?.();
      },
      get() { return image._src; },
    });
    created.push(image);
    return image;
  });
  store.preload();

  assert.equal(store.getStatus().total, 46);
  assert.equal(store.getStatus().loaded, 46);
  assert.equal(store.getStatus().failed, 0);
  assert.match(store.getCctv('13_entity_near').src, /13_entity_near_mobile\.png$/);
  assert.match(store.getV5Cctv('investigation').src, /v5_02_investigation_mobile\.png$/);
  assert.match(store.getButton('danger').src, /btn_stop_danger\.png$/);
  assert.match(store.getOverlay('frame').src, /overlay_cctv_frame\.png$/);
  assert.equal(created.length, 46);
});
