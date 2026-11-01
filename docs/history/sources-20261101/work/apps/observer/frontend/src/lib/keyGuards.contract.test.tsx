/**
 * WUI-14 · Chinese IME composition must not trigger a shortcut or run a command.
 *
 * The instrumented live run could not test this at all (`Input.dispatchKeyEvent` has no composition
 * state), and the repo had zero `isComposing` / keyCode-229 handling before this file. So the guard is
 * proven at the handler level: a key event that the input method still owns must be inert for the shell
 * and for the palette, while the same key with composition finished behaves exactly as before.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, fireEvent, cleanup, act } from '@testing-library/react'

import { isImeComposing } from '@/lib/keyGuards'

const mocks = vi.hoisted(() => ({
  live: { snap: null as any, source: 'live' as any, live: true, error: null as string | null },
}))
vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => mocks.live }
})

import App from '@/App'

describe('isImeComposing', () => {
  it('reads the flag from the event and from the native event', () => {
    expect(isImeComposing({ isComposing: true })).toBe(true)
    expect(isImeComposing({ nativeEvent: { isComposing: true } })).toBe(true)
    expect(isImeComposing({ isComposing: false })).toBe(false)
    expect(isImeComposing(null)).toBe(false)
  })

  it('treats keyCode 229 as composition even when the flag is absent', () => {
    expect(isImeComposing({ keyCode: 229 })).toBe(true)
    expect(isImeComposing({ nativeEvent: { keyCode: 229 } })).toBe(true)
    expect(isImeComposing({ keyCode: 13 })).toBe(false)
  })
})

describe('the shell shortcut ignores a composing keystroke', () => {
  afterEach(cleanup)

  // `fireEvent.keyDown(el, { isComposing: true })` cannot express this: jsdom defines `isComposing` as a
  // read-only prototype getter, so the property assignment testing-library performs is silently
  // discarded and the event arrives with `isComposing: false`. A real KeyboardEvent init is the only way
  // to hand the handler the state an input method actually produces — wrapped in `act`, because a raw
  // dispatch leaves React's state update unflushed and the DOM assertion would read a stale shell.
  const press = (target: EventTarget, init: KeyboardEventInit) => {
    act(() => {
      target.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init }))
    })
  }

  const openPalette = () => press(window, { key: 'k', ctrlKey: true })
  // The dialog stays mounted by design (`command-palette.tsx:117-125`: the repo pins a queryable
  // role=dialog, and its CONTENT is built only while open), so openness is the `.open` class.
  const paletteOpen = () => !!document.querySelector('.palette.open')
  // A missing field throws instead of returning null: the surface under test would then fail loudly here,
  // rather than handing a `HTMLInputElement | null` to the dispatch below and leaving tsc to audit it.
  const paletteInput = (): HTMLInputElement => {
    const field = document.querySelector<HTMLInputElement>('.palette.open input')
    if (!field) throw new Error('the open palette rendered no text input')
    return field
  }

  it('Ctrl/Cmd+K opens the palette only when no input method owns the key', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    expect(paletteOpen()).toBe(false)
    press(window, { key: 'k', ctrlKey: true, isComposing: true })
    expect(paletteOpen(), 'a composing Ctrl+K opened the palette').toBe(false)
    press(window, { key: 'k', ctrlKey: true, keyCode: 229 })
    expect(paletteOpen(), 'a keyCode-229 Ctrl+K opened the palette').toBe(false)
    openPalette()
    expect(paletteOpen()).toBe(true)
  })

  it('Enter during composition does not run the highlighted command', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    openPalette()
    const field = paletteInput()
    fireEvent.change(field, { target: { value: '隐私与采集' } })
    press(field, { key: 'Enter', isComposing: true })
    expect(paletteOpen(), 'a composing Enter ran the command and closed the palette').toBe(true)
    expect(window.location.search).not.toContain('view=privacy')
    // the same Enter with composition finished does navigate
    press(field, { key: 'Enter' })
    expect(window.location.search).toContain('view=privacy')
  })

  it('Esc during composition leaves the overlay standing for the input method to consume', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    openPalette()
    press(paletteInput(), { key: 'Escape', keyCode: 229 })
    expect(paletteOpen(), 'a composing Esc closed the overlay').toBe(true)
    press(paletteInput(), { key: 'Escape' })
    expect(paletteOpen()).toBe(false)
  })
})
