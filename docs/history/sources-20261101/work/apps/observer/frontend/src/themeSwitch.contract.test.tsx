// Theme switching contract: the address bar carries the state, web storage carries none, and the
// palette change lands in one frame instead of easing through colours nobody chose.
//
// The middle clause is not my preference — `apps/observer/tests/test_production_surface_static_
// contract.js` fails the build on any `localStorage`/`sessionStorage` use in the UI layer, because a
// projection whose appearance depends on hidden client state cannot be reproduced from its URL. That
// contract is why the persistence these tests replaced was reverted, and these tests are the reason it
// stays reverted: the shipped pre-render bytes are executed here, so a future `localStorage.getItem`
// inside `index.html` is caught by behaviour, not by grep.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  live: { snap: null, source: 'stale', live: false, error: null },
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => mocks.live }
})

import App from '@/App'

function preRenderScript(): string {
  // Relative to the frontend root, the same way `src/theme/tokensMirror.contract.test.ts` reads the sheets:
  // vitest runs with that directory as its working path, and `import.meta.url` is an http: URL under
  // jsdom, so it cannot name a file here.
  const html = readFileSync('index.html', 'utf8')
  const match = /<script>([\s\S]*?)<\/script>/.exec(html)
  if (!match) throw new Error('index.html carries no inline pre-render script any more')
  if (!match[1].includes('location.search')) {
    throw new Error('the pre-render script no longer reads the URL, so the state contract moved')
  }
  return match[1]
}

function runPreRender(): void {
  // eslint-disable-next-line no-new-func
  new Function(preRenderScript())()
}

function goTo(search: string): void {
  window.history.replaceState(null, '', `/index.html${search}`)
}

function resetShell(): void {
  document.documentElement.classList.remove('light', 'theme-instant')
  document.documentElement.style.colorScheme = ''
}

describe('the pre-render contract is the URL and nothing else', () => {
  beforeEach(() => {
    goTo('')
    window.localStorage.clear()
    resetShell()
  })

  afterEach(() => {
    window.localStorage.clear()
    resetShell()
  })

  it('the shipped script touches no web storage', () => {
    expect(preRenderScript()).not.toMatch(/localStorage|sessionStorage/)
  })

  it('a seeded storage value cannot turn the first paint light', () => {
    window.localStorage.setItem('worklab.observer.theme', 'light')
    runPreRender()
    expect(document.documentElement.classList.contains('light')).toBe(false)
    expect(document.documentElement.style.colorScheme).toBe('dark')
  })

  it('the url can, and sets colorScheme with it', () => {
    goTo('?theme=light')
    runPreRender()
    expect(document.documentElement.classList.contains('light')).toBe(true)
    expect(document.documentElement.style.colorScheme).toBe('light')
  })
})

describe('the app keeps theme state in the address bar', () => {
  beforeEach(() => {
    goTo('')
    window.localStorage.clear()
    resetShell()
  })

  afterEach(() => {
    cleanup()
    window.localStorage.clear()
    resetShell()
  })

  it('clicking the control writes ?theme= and no storage key', () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /浅色|深色/ }))
    expect(document.documentElement.classList.contains('light')).toBe(true)
    expect(window.location.search).toContain('theme=light')
    expect(window.localStorage.length).toBe(0)
  })

  it('reloading that address opens in light — the sanctioned persistence', () => {
    goTo('?theme=light')
    render(<App />)
    // The control names the theme it will switch TO, so "切换到深色主题" is the proof the app
    // opened in light from the URL alone.
    expect(screen.getByRole('button', { name: /切换到深色主题/ })).toBeTruthy()
  })

  it('holds the crossfade off for the switch and releases it afterwards', async () => {
    render(<App />)
    fireEvent.click(screen.getByRole('button', { name: /浅色|深色/ }))
    expect(document.documentElement.classList.contains('theme-instant')).toBe(true)
    // Wait on the frames themselves, not on two `setTimeout(0)`: jsdom schedules rAF on its own
    // clock, so a timer-based wait returned while the hold was still on and the release looked broken.
    await new Promise((resolveFrame) => {
      requestAnimationFrame(() => requestAnimationFrame(() => resolveFrame(null)))
    })
    expect(document.documentElement.classList.contains('theme-instant')).toBe(false)
  })

  it('the sheet rule that holds it off exists and outranks the pinned skin', () => {
    const css = readFileSync('src/skins/l10b-shell.css', 'utf8')
    expect(css).toMatch(/\.theme-instant[^{]*\{[^}]*transition:\s*none\s*!important/)
  })
})
