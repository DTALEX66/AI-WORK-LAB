// SPDX-License-Identifier: MIT
// Enhanced motion layer. Owner directive 2026-10-25: the Stitch pack describes static screens
// (「STITCH 更多是静态页面」), so after the 1:1 static reproduction the interaction layer gets
// real motion of its own. It stays OFF unless `?motion=enhanced` is in the URL, because the
// static reproduction is what the pack and every geometry gate were measured against; the
// primitives below only write `transform`, so an element's own ink and backdrop move together
// and no WCAG ratio changes -- interpolating colour is what put an undeclared grey on screen
// in section 5.55, and this file must never do that again.

export type MotionMode = 'static' | 'enhanced';

const BAND_MS = 150;
const MAGNET_PX = 3;
const TILT_DEG = 4;

export function motionMode(): MotionMode {
  if (typeof window === 'undefined' || typeof document === 'undefined') return 'static';
  let requested = false;
  try {
    requested = new URLSearchParams(window.location.search).get('motion') === 'enhanced';
  } catch {
    requested = false;
  }
  if (!requested) return 'static';
  // The OS signal wins over the URL: `enhanced` may ask for motion, it may not override a
  // request for none. style.css does the same job for CSS transitions and @keyframes.
  return reducedMotion() ? 'static' : 'enhanced';
}

function reducedMotion(): boolean {
  try {
    return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  } catch {
    return true;
  }
}

function move(el: HTMLElement, x: number, y: number, extra: string): void {
  el.style.transform = `translate3d(${x.toFixed(2)}px,${y.toFixed(2)}px,0)${extra}`;
}

/** Entrance slide. transform only -- fading a text-bearing node with opacity walks the glyph
 *  through every alpha between 0 and its resting value, which is the same class of bug as
 *  interpolating its colour. */
export function slideReveal(el: HTMLElement): void {
  el.style.transform = 'translate3d(0,10px,0)';
  requestAnimationFrame(() => {
    el.style.transition = `transform ${BAND_MS}ms cubic-bezier(.2,0,0,1)`;
    el.style.transform = '';
    // Hand the element back once it has landed: `.row-card` is a tilt host too, and a
    // permanent inline `transition` would make every later pointer write interpolate.
    setTimeout(() => {
      el.style.transition = '';
    }, BAND_MS + 40);
  });
}

// No count-up lives here. The shell already animates `strong[data-count]` on mount
// (shell.ts animateKpiCount, called for the dashboard grid), so a second animator on the same
// elements would double-run, and inventing a `[data-motion="count"]` marker nobody renders would
// be a decoration the product cannot show.

export interface MotionWiring {
  mode: MotionMode;
  magnetic: number;
  tilt: number;
  revealed: number;
  particles: string;
}

/** Ambient particle field, drawn on the canvas layer that already sits below the content.
 *
 *  `?motion=enhanced&particles=static` paints ONE deterministic frame and stops; `particles=live`
 *  animates it. The static pose exists for two reasons that are not convenience: it is the
 *  low-performance fallback the pack asks for (「低性能或系统关闭透明时回退实底」), and it is the
 *  state the contrast gate can measure -- an animation cannot be certified frame-by-frame, but a
 *  fixed frame can, and the frame is drawn from the same seeded positions the live mode starts
 *  from, so measuring it is not measuring a different picture.
 *
 *  Nothing here touches text: the canvas sits at --layer-canvas-ambient, below every panel, and
 *  the only colours are the two brand inks at low alpha. Interpolating ink is section 5.55's
 *  defect class and a canvas that paints over glyphs would be worse -- this one paints under them.
 */
const PARTICLE_COUNT = 24;
const PARTICLE_INKS = ['#EEF2F5', '#17212B'];

function seeded(i: number): number {
  // A cheap deterministic scatter: same field on every machine, so the static pose the gate
  // measures is the pose a person sees.
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
}

export function mountAmbientParticles(doc: Document, live: boolean): string {
  const app = doc.querySelector('.app');
  if (!app) return 'no-app-host';
  const existing = doc.querySelector('canvas.motion-particles');
  const canvas = (existing || doc.createElement('canvas')) as HTMLCanvasElement;
  if (!existing) {
    canvas.className = 'motion-particles';
    canvas.setAttribute('aria-hidden', 'true');
    app.insertBefore(canvas, app.firstChild);
  }
  const box = (canvas.parentElement as HTMLElement).getBoundingClientRect();
  const dpr = Math.min(2, (window.devicePixelRatio || 1));
  canvas.width = Math.max(1, Math.round(box.width * dpr));
  canvas.height = Math.max(1, Math.round(box.height * dpr));
  const ctx = canvas.getContext('2d');
  if (!ctx) return 'no-2d-context';
  const draw = (phase: number): void => {
    ctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let i = 0; i < PARTICLE_COUNT; i += 1) {
      const x = (seeded(i) + phase * (0.02 + seeded(i + 99) * 0.05)) % 1;
      const y = (seeded(i + 7) + phase * 0.01) % 1;
      const r = (2 + seeded(i + 31) * 5) * dpr;
      ctx.globalAlpha = 0.10 + seeded(i + 53) * 0.12;
      ctx.fillStyle = PARTICLE_INKS[i % PARTICLE_INKS.length];
      ctx.beginPath();
      ctx.arc(x * canvas.width, y * canvas.height, r, 0, Math.PI * 2);
      ctx.fill();
    }
  };
  draw(0);
  if (!live) return 'static';
  const step = (now: number): void => {
    draw(now / 12000);
    requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
  return 'live';
}

function particleMode(): 'off' | 'static' | 'live' {
  try {
    const wanted = new URLSearchParams(window.location.search).get('particles');
    if (wanted === 'live' || wanted === 'static') return wanted;
  } catch {
    /* vm harness */
  }
  return 'off';
}

// Every name below has to be a surface the shipped product actually builds -- the guard in
// design-lab/tests/test_workbench_contrast_gate.py reads every apps/workbench/*.ts source and
// index.html for each class token and fails on one nobody builds. `.seg button`, `.review-card`,
// a `[data-motion="count"]` marker and `.soft-btn` were listed here until that check showed zero
// renderers (`.soft-btn` is styled in style.css and produced by nothing, which is a finding in its
// own right, not a host to wire). There is also no count-up in this layer: the shell already
// animates `strong[data-count]` (shell.ts animateKpiCount, called for the dashboard grid), so a
// second animator would double-run the same numbers.
const MAGNETIC_SELECTOR = '.ghost-btn,.primary-btn,.danger-btn,.stage-nav-btn,.nav button';
const TILT_SELECTOR = '.row-card,.capability-card,.panel';
const REVEAL_SELECTOR = '#tp-verdicts>*,.list-item,.row-card,.grid-stack>*';

/** One delegated handler per behaviour. The shell re-renders route views, so per-element
 *  listeners wired at boot would silently detach on the next navigation; delegation survives
 *  every re-render and costs two listeners for the whole application. */
function delegate(root: Document, selector: string,
  onTarget: (el: HTMLElement, event: PointerEvent, box: DOMRect) => void,
  onLeave?: (el: HTMLElement) => void): void {
  let current: HTMLElement | null = null;
  let queued = false;
  let pending: [HTMLElement, PointerEvent, DOMRect] | null = null;
  const paint = () => {
    queued = false;
    if (!pending) return;
    onTarget(pending[0], pending[1], pending[2]);
  };
  root.addEventListener('pointermove', (event: PointerEvent) => {
    const target = (event.target as Element | null)
      && (event.target as Element).closest ? (event.target as Element).closest(selector) : null;
    const host = target as HTMLElement | null;
    if (!host) {
      if (current && onLeave) onLeave(current);
      current = null;
      pending = null;
      return;
    }
    if (current !== host) {
      if (current && onLeave) onLeave(current);
      current = host;
      host.style.willChange = 'transform';
    }
    const box = host.getBoundingClientRect();
    if (!box.width || !box.height) return;
    pending = [host, event, box];
    if (!queued) {
      queued = true;
      requestAnimationFrame(paint);
    }
  }, {passive: true});
  root.addEventListener('pointerleave', () => {
    if (current && onLeave) onLeave(current);
    current = null;
    pending = null;
  }, {passive: true});
}

export function mountEnhancedMotion(root: Document | HTMLElement): MotionWiring {
  const scope = (root as Document).body ? (root as Document) : (root as HTMLElement);
  const hostsOf = (selector: string): HTMLElement[] => {
    try {
      return Array.from((scope as ParentNode).querySelectorAll<HTMLElement>(selector));
    } catch {
      return [];
    }
  };
  const mode = motionMode();
  if (mode !== 'enhanced') {
    return {mode: 'static', magnetic: 0, tilt: 0, revealed: 0, particles: 'off'};
  }
  const doc = scope as Document;
  // style.css keys the opt-in ambient loop off this attribute, so the static screens keep the
  // pack's 「无持续循环」 rule and only this mode gets the float.
  try {
    doc.documentElement.dataset.motion = 'enhanced';
  } catch {
    /* vm harness */
  }
  delegate(doc, MAGNETIC_SELECTOR, (el, event, box) => {
    move(el, (event.clientX - box.left - box.width / 2) / box.width * MAGNET_PX,
      (event.clientY - box.top - box.height / 2) / box.height * MAGNET_PX, '');
  }, (el) => {
    move(el, 0, 0, '');
    el.style.willChange = '';
  });
  delegate(doc, TILT_SELECTOR, (el, event, box) => {
    el.style.transform = `perspective(900px) rotateX(${
      (-(event.clientY - box.top - box.height / 2) / box.height * TILT_DEG).toFixed(2)}deg) `
      + `rotateY(${
        ((event.clientX - box.left - box.width / 2) / box.width * TILT_DEG).toFixed(2)}deg)`;
  }, (el) => {
    el.style.transform = '';
    el.style.willChange = '';
  });
  const revealed = hostsOf(REVEAL_SELECTOR);
  revealed.forEach(slideReveal);
  const wanted = particleMode();
  const particles = wanted === 'off'
    ? 'off' : mountAmbientParticles(doc, wanted === 'live');
  return {
    mode,
    magnetic: hostsOf(MAGNETIC_SELECTOR).length,
    tilt: hostsOf(TILT_SELECTOR).length,
    revealed: revealed.length,
    particles,
  };
}
