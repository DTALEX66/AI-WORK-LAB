/**
 * audio.js — 程序化音效（Web Audio API，无需外部文件）
 *
 * 所有声音通过 OscillatorNode + GainNode 实时合成，
 * 初始化为惰性加载，首次用户交互时才会创建 AudioContext。
 */

let ctx = null;
let muted = false;
let music = null;
let musicState = null;
// 背景音乐资产（assets/minigame-audio/*.wav）已随视觉资产一并移除；
// MUSIC_SOURCES 保持空映射，使背景音乐功能静默降级，程序化音效不受影响。
const MUSIC_SOURCES = Object.freeze({});

export const AUDIO_LAYERS = Object.freeze({
  button: Object.freeze({ kind: 'beep', freq: 800, duration: 0.06, type: 'square', volume: 0.06 }),
  success: Object.freeze({ kind: 'beep', freq: 1000, duration: 0.1, type: 'sine', volume: 0.07 }),
  error: Object.freeze({ kind: 'beep', freq: 300, duration: 0.18, type: 'sawtooth', volume: 0.07 }),
  anomaly: Object.freeze({ kind: 'sweep', startFreq: 200, endFreq: 80, duration: 0.45, type: 'sawtooth', volume: 0.08 }),
  warning: Object.freeze({ kind: 'sweep', startFreq: 600, endFreq: 200, duration: 0.25, type: 'square', volume: 0.06 }),
  failure: Object.freeze({ kind: 'sweep', startFreq: 150, endFreq: 30, duration: 0.8, type: 'sawtooth', volume: 0.1 }),
  revive: Object.freeze({ kind: 'sweep', startFreq: 200, endFreq: 1200, duration: 0.5, type: 'sine', volume: 0.08 }),
  restart: Object.freeze({ kind: 'sequence', steps: [
    Object.freeze({ at: 0, kind: 'beep', freq: 600, duration: 0.08, type: 'sine', volume: 0.06 }),
    Object.freeze({ at: 100, kind: 'beep', freq: 800, duration: 0.1, type: 'sine', volume: 0.06 }),
  ] }),
});

export function setAudioMuted(value) {
  muted = Boolean(value);
  if (muted) pauseMusic();
  return muted;
}

function getMusic() {
  if (music) return music;
  if (typeof Audio !== 'function') return null;
  music = new Audio(MUSIC_SOURCES.calm);
  music.loop = true;
  music.preload = 'auto';
  music.volume = 0.12;
  return music;
}

export function setMusicState(nextState) {
  if (muted || !MUSIC_SOURCES[nextState]) return false;
  const player = getMusic();
  if (!player) return false;
  if (musicState === nextState && player.paused === false) return true;
  if (musicState !== nextState) {
    player.pause?.();
    player.src = MUSIC_SOURCES[nextState];
    player.currentTime = 0;
    player.volume = nextState === 'pressure' ? 0.10 : 0.12;
    musicState = nextState;
  }
  player.loop = true;
  const result = player.play?.();
  result?.catch?.(() => {});
  return true;
}

export function pauseMusic() {
  music?.pause?.();
}

export function resumeMusic() {
  if (muted || !musicState || !music) return false;
  const result = music.play?.();
  result?.catch?.(() => {});
  return true;
}

export function stopMusic() {
  if (!music) return;
  music.pause?.();
  try { music.currentTime = 0; } catch { /* optional browser behavior */ }
}

export function isAudioMuted() {
  return muted;
}

export function toggleAudioMuted() {
  return setAudioMuted(!muted);
}

export function getAudioLayer(layerId) {
  return AUDIO_LAYERS[layerId] ?? null;
}

export function playLayer(layerId) {
  if (muted) return false;
  const layer = getAudioLayer(layerId);
  if (!layer) return false;
  if (layer.kind === 'beep') {
    beep(layer.freq, layer.duration, layer.type, layer.volume);
    return true;
  }
  if (layer.kind === 'sweep') {
    sweep(layer.startFreq, layer.endFreq, layer.duration, layer.type, layer.volume);
    return true;
  }
  if (layer.kind === 'sequence') {
    for (const step of layer.steps) {
      window.setTimeout(() => {
        if (!muted && step.kind === 'beep') beep(step.freq, step.duration, step.type, step.volume);
        if (!muted && step.kind === 'sweep') sweep(step.startFreq, step.endFreq, step.duration, step.type, step.volume);
      }, step.at);
    }
    return true;
  }
  return false;
}

function getContext() {
  if (!ctx) {
    ctx = new (window.AudioContext || window.webkitAudioContext)();
  }
  // 某些浏览器在 user gesture 后需要 resume
  if (ctx.state === 'suspended') {
    ctx.resume().catch(() => {});
  }
  return ctx;
}

/**
 * 播放一个简单的单频音
 * @param {number} freq - 频率 Hz
 * @param {number} duration - 持续秒
 * @param {string} type - 波形类型
 * @param {number} volume - 音量 0-1
 */
function beep(freq, duration, type = 'square', volume = 0.08) {
  try {
    const ac = getContext();
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(freq, ac.currentTime);
    gain.gain.setValueAtTime(volume, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + duration);
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.start(ac.currentTime);
    osc.stop(ac.currentTime + duration);
  } catch {
    // 静默失败 — 音效不是关键功能
  }
}

/**
 * 播放一个扫频音（用于异常/警报）
 */
function sweep(startFreq, endFreq, duration, type = 'sawtooth', volume = 0.06) {
  try {
    const ac = getContext();
    const osc = ac.createOscillator();
    const gain = ac.createGain();
    osc.type = type;
    osc.frequency.setValueAtTime(startFreq, ac.currentTime);
    osc.frequency.exponentialRampToValueAtTime(endFreq, ac.currentTime + duration);
    gain.gain.setValueAtTime(volume, ac.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ac.currentTime + duration);
    osc.connect(gain);
    gain.connect(ac.destination);
    osc.start(ac.currentTime);
    osc.stop(ac.currentTime + duration);
  } catch {
    // 静默失败
  }
}

/** 按钮点击 — 短促的咔嗒声 */
export function playClick() {
  return playLayer('button');
}

/** 操作成功 — 确认音 */
export function playSuccess() {
  return playLayer('success');
}

/** 操作失败 — 拒绝音 */
export function playFail() {
  return playLayer('error');
}

/** 异常触发 — 低频警报扫频 */
export function playAnomaly() {
  return playLayer('anomaly');
}

/** 稳定度/电源危险 — 短促警告 */
export function playWarning() {
  return playLayer('warning');
}

/** 系统崩溃 — 低沉衰减 */
export function playCrash() {
  return playLayer('failure');
}

/** 复活 — 上升恢复音 */
export function playRevive() {
  return playLayer('revive');
}

/** 游戏重启 — 重置音 */
export function playRestart() {
  return playLayer('restart');
}
