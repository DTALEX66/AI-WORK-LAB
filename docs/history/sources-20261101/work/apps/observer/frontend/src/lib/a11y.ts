// U03 / WlA11y parity — WCAG 2.2 AA live-region announcements for the React
// Observer UI.
//
// This is the one *valid* accessibility capability that the retired static
// web/ surface (web/scripts/accessibility.js `WlA11y.announce`) provides and
// the React UI previously lacked: a polite status live region that announces
// state transitions (theme switch, data-source transitions) to assistive
// tech. React's state-driven views + URL routing already replace the
// static surface's in-page anchor nav (WlA11y.bindSectionNav / setActiveNav),
// so ONLY the announcer is valid surface to migrate.
//
// Deliberately NOT migrated here:
//   * WlCharts — the static v3 snapshot carries no time-series, so a chart
//     would be a fabricated KPI. Not valid surface; left for a data-source
//     task, not U03.
//   * WlFormat — only `escapeHtml` is used by the running static app, and
//     React auto-escapes string children, so it is redundant.
//
// Pure + deterministic: no network, no React dependency. The document is the
// source of truth (a single reusable live-region node is queried, not cached
// in module state), so test teardown that removes the DOM never leaves a
// stale reference behind.

const SELECTOR = 'div[role="status"][aria-live="polite"]'

function regionExists(): boolean {
  return typeof document !== 'undefined' && !!document.querySelector(SELECTOR)
}

function findOrCreateRegion(): HTMLElement | null {
  if (typeof document === 'undefined') return null
  const existing = document.querySelector(SELECTOR)
  if (existing) return existing as HTMLElement
  const el = document.createElement('div')
  el.setAttribute('role', 'status')
  el.setAttribute('aria-live', 'polite')
  el.className = 'sr-only'
  document.body.appendChild(el)
  return el
}

/**
 * Announce a status change to assistive tech. An empty message is a no-op so
 * callers can be called unconditionally. A repeated identical message is still
 * re-announced by re-setting textContent (assistive tech re-reads on change).
 */
export function announce(message: string): void {
  if (!message) return
  const r = findOrCreateRegion()
  if (!r) return // SSR: nothing to announce into.
  r.textContent = ''
  // Force a reflow so a second identical message still re-announces. Guarded
  // for detached nodes.
  try {
    void (r as HTMLElement).offsetHeight
  } catch {
    /* detached: no reflow available */
  }
  r.textContent = message
}

/** The currently-announced message (or '' if nothing / no DOM). */
export function lastAnnouncement(): string {
  if (typeof document === 'undefined') return ''
  const r = document.querySelector(SELECTOR)
  return r ? (r.textContent ?? '') : ''
}

/** How many polite status live regions are currently in the document. */
export function liveRegionCount(): number {
  if (typeof document === 'undefined') return 0
  return document.querySelectorAll(SELECTOR).length
}
