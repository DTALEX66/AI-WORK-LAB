/**
 * WUI-14 · a new snapshot must not steal focus, selection, or reading position.
 *
 * The taskpack clause is 不抢焦点/选中/阅读位置. Two of the three are properties of a *live update*: the
 * user is mid-keystroke or mid-sentence when the projection arrives, and the screen must not move under
 * them. jsdom has no layout, so this file proves the mechanism that decides the pixel outcome — the
 * scrolling element and the text the user selected must survive the update as the SAME DOM nodes — and
 * the shipped production tree contains no `scrollTo`/`scrollTop =`/`removeAllRanges` call at all (grep
 * verified 2026-10-09 over `src/`), so node survival is the whole story. The pixel half is a real
 * browser's job, not this file's.
 *
 * The update is pushed through the real hook's own state setter rather than by re-rendering from the
 * test, because "the parent re-rendered harmlessly" is not the event the product has to survive.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, fireEvent, cleanup, act } from '@testing-library/react'

import { mkProject, mkSnap } from '@/test/snapshotFixture'

const mocks = vi.hoisted(() => ({ push: null as null | ((snap: unknown) => void) }))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  const React = await import('react')
  const { mkProject, mkSnap } = await import('@/test/snapshotFixture')
  return {
    ...actual,
    useLiveSnapshot: () => {
      const [snap, setSnap] = React.useState(() => mkSnap({ projects: [mkProject()] }))
      // The real hook returns {snap, dataUpdatedAt, source, live, error}; App reads four of them.
      mocks.push = (next: unknown) => setSnap(next as typeof snap)
      return { snap, source: 'live' as const, live: true, error: null as string | null }
    },
  }
})

import App from '@/App'

// The lane's OWN root element, whichever view is on screen. `#content` is the shell's section and never
// remounts, so its first child is the mounted lane. The first draft of this file tracked
// `document.querySelector('h1,h2,h3')` instead, which resolved to shell chrome: the negative control went
// red because a lane switch left that heading connected — the honest way to discover the instrument was
// measuring the wrong node.
const laneRoot = (): Element => {
  const node = document.querySelector('#content')?.firstElementChild
  if (!node) throw new Error('no lane is mounted inside #content')
  return node
}

const paletteField = (): HTMLInputElement => {
  const field = document.querySelector<HTMLInputElement>('.palette.open input')
  if (!field) throw new Error('the open palette rendered no text input')
  return field
}

const pressKey = (target: EventTarget, init: KeyboardEventInit) => {
  act(() => {
    target.dispatchEvent(new KeyboardEvent('keydown', { bubbles: true, cancelable: true, ...init }))
  })
}

const openPalette = () => pressKey(window, { key: 'k', ctrlKey: true })

/** Navigate the way a user does, through the palette, so the negative control exercises a real lane switch. */
const goToLane = (label: string) => {
  openPalette()
  const field = paletteField()
  fireEvent.change(field, { target: { value: label } })
  pressKey(field, { key: 'Enter' })
}

describe('a snapshot arriving under the user', () => {
  afterEach(() => {
    cleanup()
    mocks.push = null
    window.history.replaceState(null, '', '/index.html?view=overview')
  })

  it('keeps the lane that did not change mounted, so its scroll offset survives', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    const before = laneRoot()
    act(() => { mocks.push!(mkSnap({ revision: 12, projects: [mkProject()] })) })
    // A remount would disconnect `before`; a re-render would not. This is the difference between the
    // reading position holding and the page jumping to the top under someone mid-sentence.
    expect(before.isConnected, 'the revision bump remounted the lane').toBe(true)
    expect(laneRoot()).toBe(before)
  })

  it('keeps the caret in a field the user is typing in', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    openPalette()
    const field = paletteField()
    field.focus()
    fireEvent.change(field, { target: { value: '隐私' } })
    field.setSelectionRange(1, 2)
    act(() => { mocks.push!(mkSnap({ revision: 13, projects: [mkProject()] })) })
    expect(document.activeElement, 'the update moved focus out of the field').toBe(field)
    expect(field.value).toBe('隐私')
    expect([field.selectionStart, field.selectionEnd]).toEqual([1, 2])
  })

  it('keeps a text selection the user made in the lane', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    const subject = laneRoot()
    const selection = window.getSelection()
    if (!selection) throw new Error('the harness exposes no Selection API')
    selection.selectAllChildren(subject)
    expect(selection.anchorNode, 'nothing was selected to protect').not.toBeNull()
    act(() => { mocks.push!(mkSnap({ revision: 14, projects: [mkProject()] })) })
    expect(selection.rangeCount, 'the update dropped the range').toBe(1)
    expect(selection.anchorNode!.isConnected, 'the selected text node left the document').toBe(true)
  })

  it('keeps the rail scroll container itself mounted across an update', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    const nav = document.querySelector('.nav, .sidebar')
    if (!nav) throw new Error('the rail rendered no scroll container to track')
    act(() => { mocks.push!(mkSnap({ revision: 15, projects: [mkProject()] })) })
    expect(nav.isConnected, 'the rail was rebuilt, so its scroll offset is gone').toBe(true)
    expect(document.querySelector('.nav, .sidebar')).toBe(nav)
  })

  // Negative control: four of the assertions above lean on `isConnected` staying true, so the check has
  // to be able to report false. A lane switch is the update that SHOULD remount, and the heading the
  // user was reading has to go disconnected when it happens. Without this row the guard is decoration.
  it('does remount when the user actually changes lane', () => {
    window.history.replaceState(null, '', '/index.html?view=overview')
    render(<App />)
    const before = laneRoot()
    goToLane('隐私与采集')
    expect(window.location.search, 'the palette did not navigate to the requested lane')
      .toContain('view=privacy')
    expect(before.isConnected, 'a lane switch left the previous lane mounted').toBe(false)
  })
})
