export function createMiniGameClock(now = () => Date.now()) {
  let started = false;
  let paused = false;
  let lastTickAt = now();

  return {
    start() {
      started = true;
      paused = false;
      lastTickAt = now();
    },
    pause() {
      paused = true;
    },
    resume() {
      paused = false;
      lastTickAt = now();
    },
    reset() {
      started = false;
      paused = false;
      lastTickAt = now();
    },
    isStarted() {
      return started;
    },
    isPaused() {
      return paused;
    },
    consumeDeltaSeconds() {
      if (!started || paused) return 0;
      const current = now();
      const delta = Math.max(0, Math.floor((current - lastTickAt) / 1000));
      if (delta > 0) lastTickAt += delta * 1000;
      return delta;
    },
  };
}
