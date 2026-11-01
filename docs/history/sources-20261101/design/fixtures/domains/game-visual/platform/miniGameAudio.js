const SOURCES = Object.freeze({
  click: 'audio/click.wav',
  anomaly: 'audio/anomaly.wav',
  result: 'audio/result.wav',
  boot: 'audio/boot.wav',
  release: 'audio/release.wav',
  lockdown: 'audio/lockdown.wav',
  motor: 'audio/motor.wav',
  wrong: 'audio/wrong.wav',
});

const MUSIC_SOURCES = Object.freeze({
  calm: 'audio/bgm-night-shift-loop.wav',
  pressure: 'audio/bgm-anomaly-pressure-loop.wav',
});

const V5_FEEDBACK_PROFILES = Object.freeze({
  camera: Object.freeze({ cue: 'click', haptic: 'light' }),
  'tool:thermal': Object.freeze({ cue: 'anomaly', haptic: 'medium' }),
  'tool:replay': Object.freeze({ cue: 'motor', haptic: 'light' }),
  'tool:protocol': Object.freeze({ cue: 'boot', haptic: 'light' }),
  'protocol:close': Object.freeze({ cue: 'release', haptic: 'light' }),
  'identity:verify': Object.freeze({ cue: 'boot', haptic: 'light' }),
  'identity:correct': Object.freeze({ cue: 'release', haptic: 'medium' }),
  'identity:wrong': Object.freeze({ cue: 'wrong', haptic: 'heavy' }),
  'classification:enter': Object.freeze({ cue: 'anomaly', haptic: 'medium' }),
  'classification:correct': Object.freeze({ cue: 'lockdown', haptic: 'medium' }),
  'classification:wrong': Object.freeze({ cue: 'wrong', haptic: 'heavy' }),
  'highRisk:correct': Object.freeze({ cue: 'lockdown', haptic: 'heavy' }),
  'highRisk:wrong': Object.freeze({ cue: 'wrong', haptic: 'heavy' }),
});

export function getV5FeedbackProfile(kind) {
  const profile = V5_FEEDBACK_PROFILES[kind] || V5_FEEDBACK_PROFILES.camera;
  return { ...profile };
}

export function createMiniGameAudio(api) {
  const contexts = new Map();
  let musicContext = null;
  let musicState = null;
  let musicPaused = true;
  let muted = false;

  function getContext(cue) {
    if (contexts.has(cue)) return contexts.get(cue);
    if (!api || typeof api.createInnerAudioContext !== 'function') return null;
    const context = api.createInnerAudioContext();
    context.autoplay = false;
    context.loop = false;
    context.volume = ({ anomaly: 0.34, lockdown: 0.36, release: 0.28, motor: 0.18, boot: 0.24, wrong: 0.27 }[cue] ?? 0.22);
    context.src = SOURCES[cue];
    contexts.set(cue, context);
    return context;
  }

  function getMusicContext() {
    if (musicContext) return musicContext;
    if (!api || typeof api.createInnerAudioContext !== 'function') return null;
    musicContext = api.createInnerAudioContext();
    musicContext.autoplay = false;
    musicContext.loop = true;
    musicContext.volume = 0.12;
    return musicContext;
  }

  function safePlay(context) {
    try {
      const result = context?.play?.();
      result?.catch?.(() => {});
      return Boolean(context && typeof context.play === 'function');
    } catch {
      return false;
    }
  }

  const controller = {
    play(cue) {
      if (muted || !SOURCES[cue]) return false;
      const context = getContext(cue);
      if (!context || typeof context.play !== 'function') return false;
      try {
        context.stop?.();
        context.seek?.(0);
        return safePlay(context);
      } catch {
        return false;
      }
    },
    setMusicState(nextState) {
      if (!MUSIC_SOURCES[nextState]) return false;
      musicState = nextState;
      if (muted) return false;
      const context = getMusicContext();
      if (!context) return false;
      if (context.src !== MUSIC_SOURCES[nextState]) {
        context.stop?.();
        context.src = MUSIC_SOURCES[nextState];
        context.loop = true;
        context.volume = nextState === 'pressure' ? 0.10 : 0.12;
        context.seek?.(0);
      }
      musicPaused = false;
      return safePlay(context);
    },
    pauseMusic() {
      musicContext?.pause?.();
      musicPaused = true;
    },
    resumeMusic() {
      if (muted || !musicState || !musicPaused) return false;
      const context = getMusicContext();
      if (!context) return false;
      context.src = MUSIC_SOURCES[musicState];
      context.loop = true;
      context.volume = musicState === 'pressure' ? 0.10 : 0.12;
      musicPaused = false;
      return safePlay(context);
    },
    stopMusic() {
      musicContext?.stop?.();
      musicPaused = true;
    },
    getMusicState() {
      return musicState;
    },
    stopAll() {
      for (const context of contexts.values()) context.stop?.();
      controller.stopMusic();
    },
    destroy() {
      for (const context of contexts.values()) context.destroy?.();
      contexts.clear();
      musicContext?.destroy?.();
      musicContext = null;
      musicState = null;
      musicPaused = true;
    },
    setMuted(value) {
      muted = Boolean(value);
      if (muted) controller.stopAll();
      return muted;
    },
    isMuted() {
      return muted;
    },
  };

  return controller;
}
