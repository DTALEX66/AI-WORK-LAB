export function bindMiniGameLifecycle(api, handlers = {}) {
  const onPause = () => handlers.onPause?.();
  const onResume = (options) => handlers.onResume?.(options);
  api?.onHide?.(onPause);
  api?.onShow?.(onResume);
  return () => {
    api?.offHide?.(onPause);
    api?.offShow?.(onResume);
  };
}

export function checkDouyinSidebar(api) {
  if (!api || typeof api.navigateToScene !== 'function' || typeof api.checkScene !== 'function') {
    return Promise.resolve(false);
  }
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(Boolean(value));
    };
    try {
      const result = api.checkScene({
        scene: 'sidebar',
        success: (response) => finish(response?.isExist !== false),
        fail: () => finish(false),
      });
      if (result && typeof result.then === 'function') {
        result.then(response => finish(response?.isExist !== false)).catch(() => finish(false));
      }
    } catch {
      finish(false);
    }
  });
}

export function navigateToDouyinSidebar(api) {
  if (!api || typeof api.navigateToScene !== 'function') return Promise.resolve(false);
  return new Promise((resolve) => {
    let settled = false;
    const finish = (value) => {
      if (settled) return;
      settled = true;
      resolve(value);
    };
    try {
      const result = api.navigateToScene({
        scene: 'sidebar',
        success: () => finish(true),
        fail: () => finish(false),
      });
      if (result && typeof result.then === 'function') {
        result.then(() => finish(true)).catch(() => finish(false));
      }
    } catch {
      finish(false);
    }
  });
}
