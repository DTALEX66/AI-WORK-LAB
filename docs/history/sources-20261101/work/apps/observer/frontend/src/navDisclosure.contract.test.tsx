/**
 * NAV GROUP DISCLOSURE CONTRACT (SCREEN_SPEC rule 3, ARIA APG Disclosure Navigation).
 *
 * The rail is a real scroll box since `36f9a297`, and scrolling alone was measured insufficient: at the
 * 600px window floor the content is 1505px over a 595px box, so the group captions double as disclosure
 * buttons. SCREEN_SPEC.md asserted until today that this collapse "is not implemented" — the claim was
 * stale, and it stayed stale because nothing tested the behaviour, so a reader could not tell working code
 * from absent code. These tests are the difference: every group exposes its state, the hidden items leave
 * the document (they are not merely invisible), the toggle is the only way back, and Escape returns focus
 * to the toggle of the group that holds the active view.
 *
 * The collapse state lives in the component and nowhere else: no web storage, no URL parameter, because the
 * owner's rule is that UI state travels through the URL and localStorage is forbidden outright.
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, fireEvent, cleanup } from '@testing-library/react'

import { Sidebar } from '@/components/layout/Sidebar'

afterEach(cleanup)

const toggles = (root: HTMLElement) =>
  Array.from(root.querySelectorAll<HTMLButtonElement>('.nav button.nav-group-toggle'))
const lanes = (root: HTMLElement) =>
  Array.from(root.querySelectorAll<HTMLButtonElement>('.nav button[data-lane]'))

describe('nav group disclosure', () => {
  it('every group caption is a disclosure button that points at a real region', () => {
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const buttons = toggles(container)
    expect(buttons.length).toBeGreaterThanOrEqual(7)
    for (const button of buttons) {
      expect(button.getAttribute('aria-expanded')).toBe('true')
      const controls = button.getAttribute('aria-controls')
      expect(controls, `toggle ${button.textContent} has no aria-controls`).toBeTruthy()
      expect(container.querySelector(`#${controls}`),
             `aria-controls ${controls} names no element`).not.toBeNull()
    }
    // a caption is also the control, so it must carry the group's name as its accessible text, and it must
    // be a real button -- native Enter/Space activation is what the spec's "Space/Enter toggles" clause
    // relies on, and jsdom cannot demonstrate a keypress turning into a click on a synthetic control
    for (const button of buttons) {
      expect(button.tagName).toBe('BUTTON')
      expect(button.getAttribute('type')).toBe('button')
      expect(button.disabled).toBe(false)
      expect((button.textContent || '').trim().length, 'a disclosure with no name is unreachable')
        .toBeGreaterThan(0)
    }
  })

  it('collapsing a group removes exactly its own lanes and leaves the others reachable', () => {
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const before = lanes(container).map((b) => b.getAttribute('data-lane'))
    const [first, second] = toggles(container)
    const firstRegion = container.querySelector(`#${first.getAttribute('aria-controls')}`)
    const firstIds = Array.from(firstRegion?.querySelectorAll('button[data-lane]') || [])
      .map((b) => b.getAttribute('data-lane'))
    expect(firstIds.length, 'the first group holds no lanes').toBeGreaterThan(0)

    fireEvent.click(first)

    expect(first.getAttribute('aria-expanded')).toBe('false')
    const after = lanes(container).map((b) => b.getAttribute('data-lane'))
    expect(after.length).toBe(before.length - firstIds.length)
    for (const id of firstIds) expect(after).not.toContain(id)
    // the second group is untouched, and its region is still in the document
    expect(second.getAttribute('aria-expanded')).toBe('true')
    expect(container.querySelector(`#${second.getAttribute('aria-controls')}`)).not.toBeNull()
    // the hidden lanes are gone from the document, not merely styled away
    expect(container.querySelector(`#${first.getAttribute('aria-controls')}`)).toBeNull()
    // and the control that hides them is also the only way to bring them back
    expect(first.getAttribute('title')).toContain('展开')
  })

  it('expanding again restores the identical lane set', () => {
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const before = lanes(container).map((b) => b.getAttribute('data-lane'))
    const button = toggles(container)[0]
    fireEvent.click(button)
    fireEvent.click(button)
    expect(button.getAttribute('aria-expanded')).toBe('true')
    expect(lanes(container).map((b) => b.getAttribute('data-lane'))).toEqual(before)
  })

  it('Escape from a lane collapses its own group and moves focus to that group toggle', () => {
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const group = toggles(container).find((button) => {
      const region = container.querySelector(`#${button.getAttribute('aria-controls')}`)
      return Array.from(region?.querySelectorAll('button[data-lane]') || [])
        .some((lane) => lane.hasAttribute('aria-current'))
    })
    expect(group, 'the active view is not inside any collapsible group').toBeDefined()
    const laneInside = container
      .querySelector(`#${group!.getAttribute('aria-controls')} button[aria-current="page"]`)!
    fireEvent.keyDown(laneInside, { key: 'Escape' })

    expect(group!.getAttribute('aria-expanded')).toBe('false')
    expect(document.activeElement).toBe(group)
    expect(lanes(container).map((b) => b.getAttribute('data-lane'))).not.toContain(
      laneInside.getAttribute('data-lane'))
  })

  it('Escape while already on a toggle does not steal focus or collapse another group', () => {
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const [first, second] = toggles(container)
    first.focus()
    fireEvent.keyDown(first, { key: 'Escape' })
    expect(first.getAttribute('aria-expanded')).toBe('true')
    expect(second.getAttribute('aria-expanded')).toBe('true')
    expect(document.activeElement).toBe(first)
  })

  it('navigation stays navigation: a disclosure button is not a write affordance', () => {
    const seen: string[] = []
    const { container } = render(<Sidebar activeView="overview" onSelect={(id) => seen.push(id)} />)
    fireEvent.click(toggles(container)[0])
    fireEvent.click(toggles(container)[0])
    expect(seen, 'a group toggle must never select a lane').toEqual([])
    const laneButtons = lanes(container)
    fireEvent.click(laneButtons[0])
    expect(seen).toEqual([laneButtons[0].getAttribute('data-lane')])
  })

  it('the collapse state is component state only: no web storage, no URL write', () => {
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const locationBefore = window.location.href
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const all = toggles(container)
    for (const button of all) fireEvent.click(button)
    expect(lanes(container)).toHaveLength(0)
    fireEvent.click(toggles(container)[0])
    expect(setItem, 'the rail wrote UI state into web storage').not.toHaveBeenCalled()
    setItem.mockRestore()
    expect(window.location.href).toBe(locationBefore)
    // exactly the one group that was opened again is expanded; the rest stay collapsed in the component
    expect(container.querySelectorAll('.nav button.nav-group-toggle[aria-expanded="true"]').length)
      .toBe(1)
    expect(container.querySelectorAll('.nav button.nav-group-toggle[aria-expanded="false"]').length)
      .toBe(all.length - 1)
  })
})
