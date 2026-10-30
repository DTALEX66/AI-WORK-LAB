// SPDX-License-Identifier: MIT
// DESIGN-LAB Workbench - shared UI primitives (D07 split, batch 1).
//
// Owns only what every screen needs to exist at all: the `el`/`en` DOM constructors and
// the readback-honesty helpers (shape notice / disconnected notice / empty wording).
// Nothing here reads the service, imports a screen, or holds mutable module state, so a
// screen module can import it without a cycle back into shell.ts.
//
// The seam itself (`apiOrEmpty`) deliberately stays in shell.ts: the native-UI AST gate
// counts `function apiOrEmpty` declarations in shell.ts and refuses to pass when the
// definition moves (apps/workbench/tests/shape-notice-coverage.mjs). These are the
// helpers it calls, not the call site.

export function el<K extends keyof HTMLElementTagNameMap>(tag: K, attrs: Record<string, unknown> = {}, ...children: (Node | string)[]): HTMLElementTagNameMap[K] {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined) continue;
    if (key === 'class') node.className = String(value);
    else if (key === 'dataset') for (const [dk, dv] of Object.entries(value as Record<string, unknown>)) (node as HTMLElement).dataset[dk] = String(dv);
    else if (key.startsWith('on') || key === 'type' || key === 'value' || key === 'placeholder')
      (node as unknown as Record<string, unknown>)[key] = value;
    // `style` MUST go through the CSSOM. The service serves every workbench
    // response with `style-src 'self'` and NO 'unsafe-inline' (CSP in
    // src/design_lab/workbench.py), which blocks a `style` ATTRIBUTE and logs an
    // "Applying inline style violates..." console error that the browser E2E
    // treats as a hard failure; CSSStyleDeclaration writes are exempt. Probed
    // against the exact CSP in a real browser: setAttribute('style') blocked,
    // while style.cssText / setProperty / property assignment all applied.
    // The vm DOM mocks have no CSSStyleDeclaration, so fall back to the
    // attribute there (a vm context enforces no CSP).
    else if (key === 'style' && (node as HTMLElement).style) (node as HTMLElement).style.cssText = String(value);
    else node.setAttribute(key, String(value));
  }
  node.append(...children);
  return node;
}

// Machine-state words stay English on purpose -- they are the service's own
// vocabulary, and translating them would create exactly the second vocabulary
// that verify_state_vocabularies.py exists to prevent. Inside a lang="zh-CN"
// document they must be marked instead, or a screen reader pronounces them with
// Chinese phonemes (WCAG 3.1.2 Language of Parts).
export function en(text: string): HTMLElement {
  return el('span', { lang: 'en' }, text);
}

export const SHAPE_MISSING = Symbol.for('design-lab/shape-missing');
// The seam's other failure mode: with no session it hands out an honest EMPTY payload
// so the page structure still renders. That empty is not evidence the ledger has
// nothing in it, so it is marked at the source and no view may describe it as a zero.
export const DISCONNECTED = Symbol.for('design-lab/disconnected');

export function normaliseShape(live: Record<string, unknown>, template: unknown, prefix = ''): string[] {
  if (template === null || typeof template !== 'object') return [];
  const missing: string[] = [];
  for (const [key, want] of Object.entries(template as Record<string, unknown>)) {
    const field = prefix ? `${prefix}.${key}` : key;
    if (Array.isArray(want)) {
      if (!Array.isArray(live[key])) { live[key] = []; missing.push(field); }
    } else if (want !== null && typeof want === 'object') {
      if (live[key] === null || typeof live[key] !== 'object') { live[key] = {}; missing.push(field); }
      missing.push(...normaliseShape(live[key] as Record<string, unknown>, want, field));
    }
    // null and primitive fallbacks are skipped: null is a legal live value for
    // chosen_direction / active_binding / next_cursor, so requiring one would
    // fabricate a failure the service never produced.
  }
  return missing;
}

// One row per view that had to invent a collection because the service left it out.
// Spread into the view's children; empty means nothing to report, so a healthy read
// adds no noise. This is deliberately per-view rather than one shared accumulator:
// renders run off-DOM and race, and a losing generation would otherwise leak its
// notice into the view that won.
export function shapeNoticeRows(...values: unknown[]): HTMLElement[] {
  const notes = values.map(shapeNotice).filter(Boolean);
  return notes.length ? [el('p', { class: 'error' }, notes.join('；'))] : [];
}

// What a view must say when the service answered 200 but left a collection out.
export function shapeNotice(value: unknown): string {
  const missing = (value as Record<symbol, unknown> | null)?.[SHAPE_MISSING];
  return Array.isArray(missing) && missing.length
    ? `未读回：响应缺少 ${missing.join('、')}` : '';
}

// The per-field question shapeNotice cannot answer: it reports the whole list, and a view
// that is about to describe an EMPTY collection needs to know whether THAT field is one
// the seam invented. An empty <ul> may be called 尚无 only when the service really
// answered "nothing here"; when the seam had to supply the empty, saying 尚无 would be
// the claim the notice two lines down contradicts.
export function shapeFieldMissing(value: unknown, field: string): boolean {
  const missing = (value as Record<symbol, unknown> | null)?.[SHAPE_MISSING];
  return Array.isArray(missing) && missing.includes(field);
}

export function markDisconnected<T extends object>(payload: T): T {
  const mark = (target: object): void => {
    Object.defineProperty(target, DISCONNECTED, { value: true, enumerable: false });
  };
  mark(payload);
  // Views hold the collection they walked (`layer`, not the response root), so the
  // marker has to survive one level of nesting to be reachable where it is needed.
  for (const value of Object.values(payload)) {
    if (value !== null && typeof value === 'object') mark(value);
  }
  return payload;
}

// What a view must say when there was no readback at all. Distinct from shapeNotice:
// there the service answered and omitted a field; here nothing was ever asked.
export function disconnectedNotice(value: unknown): string {
  return (value as Record<symbol, unknown> | null)?.[DISCONNECTED] === true
    ? '未读回：未连接本机设计服务' : '';
}

// The two headings an empty collection may carry. `noun` (尚无X) is a claim about the
// ledger, so it is allowed only on a real readback. Both directions matter: the offline
// case may not borrow the confident wording, and a real empty may not hide behind 未读回.
export function emptyWording(value: unknown, noun: string, hint: string): [string, string] {
  const offline = disconnectedNotice(value);
  return offline ? ['未读回', offline] : [noun, hint];
}

export function emptyLi(value: unknown, noun: string, hint: string): HTMLElement {
  const [head, note] = emptyWording(value, noun, hint);
  return el('li', { class: 'list-item' }, el('div', {}, el('strong', {}, head), el('small', {}, note)));
}

export function emptyTd(value: unknown, noun: string, hint: string, colspan: number): HTMLElement {
  const [head, note] = emptyWording(value, noun, hint);
  // One text node, not a <small> caption: inside a table cell the 0.8em small is the
  // size the overflow gate measures, and it failed at every width on the first run.
  return el('td', { colspan: String(colspan) }, `${head} ${note}`);
}
