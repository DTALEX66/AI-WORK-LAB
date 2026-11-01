import '@testing-library/jest-dom/vitest'
import { afterEach } from 'vitest'
import { cleanup } from '@testing-library/react'

// L10 (2026-09-27): jsdom does not ship ResizeObserver (used by the B10
// workflow canvas for edge geometry). Stub a no-op observer so canvas tests
// can mount; production browsers provide it natively.
if (typeof globalThis.ResizeObserver === 'undefined') {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() { /* no-op in jsdom */ }
    unobserve() { /* no-op in jsdom */ }
    disconnect() { /* no-op in jsdom */ }
  } as unknown as typeof ResizeObserver
}

// after each test, unmount + reset URL so view/theme helpers don't leak
afterEach(() => {
  cleanup()
  window.history.replaceState(null, '', window.location.pathname)
})
