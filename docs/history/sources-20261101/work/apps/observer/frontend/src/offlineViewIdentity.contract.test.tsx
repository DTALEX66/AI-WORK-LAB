// The degraded surface must name the view it is failing for.
//
// With one identical offline card for all 22 views, a user clicking through the rail sees nothing
// change and reports the navigation as dead — which is exactly what happened (owner, 2026-10-08:
// 「左侧导航没反应 是卡了 还是什么问题」). The rail was working; the report was anonymous. SCREEN_SPEC's
// "degraded state must be distinguishable per view" clause had no test until this file.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  live: { snap: null, source: 'offline', live: false, error: 'snapshot fetch refused' },
}))

vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => mocks.live }
})

const announced = vi.hoisted(() => [] as string[])
vi.mock('@/lib/a11y', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/a11y')>()
  return { ...actual, announce: (message: string) => announced.push(message) }
})

import App from '@/App'
import { VIEW_REGISTRY, OVERVIEW_ID, OVERVIEW_LABEL } from '@/lib/viewRegistry'

function renderOffline(viewId: string): void {
  cleanup()
  window.history.replaceState(null, '', `/index.html?view=${viewId}`)
  render(<App />)
}

describe('the offline surface identifies its view', () => {
  afterEach(() => {
    cleanup()
    announced.length = 0
  })

  it('the registry still carries the views this contract is claimed over', () => {
    // Without this, an empty registry would make every loop above pass by running zero times.
    expect(VIEW_REGISTRY.length).toBeGreaterThanOrEqual(20)
    const labels = VIEW_REGISTRY.map((e) => e.label)
    expect(new Set(labels).size).toBe(labels.length)
  })

  it('names the active view in the heading, for every registered lane', () => {
    const seen: string[] = []
    for (const entry of VIEW_REGISTRY) {
      renderOffline(entry.id)
      const heading = screen.getByRole('alert').textContent || ''
      expect(heading, `${entry.id} renders an anonymous offline card`).toContain(entry.label)
      seen.push(heading)
    }
    // Distinctness is the actual product property: N identical headings would satisfy "contains a
    // label" only if every label were the same string, and this catches the shared-text regression.
    // A duplicate here means two views are genuinely indistinguishable when the transport is down.
    expect(new Set(seen).size).toBe(VIEW_REGISTRY.length)
  })

  it('names the overview by its own word rather than as an unknown id', () => {
    renderOffline(OVERVIEW_ID)
    expect(screen.getByRole('alert').textContent).toContain(OVERVIEW_LABEL)
    expect(screen.getByRole('alert').textContent).not.toContain('未知视图')
  })

  it('states what stays UNKNOWN and why switching is not the fix', () => {
    renderOffline('agents')
    const status = screen.getAllByRole('status').map((el) => el.textContent || '').join(' ')
    expect(status).toContain('「智能体」读不到快照')
    expect(status).toContain('UNKNOWN')
    expect(status).toContain('不是界面卡住')
  })

  it('announces the same view name to assistive tech', () => {
    renderOffline('work')
    expect(announced.some((m) => m.includes('「工作」') && m.includes('OFFLINE'))).toBe(true)
  })

  it('never claims a number the snapshot did not carry', () => {
    renderOffline('models')
    const text = document.body.textContent || ''
    expect(text).not.toMatch(/\b0\s*(次|个|tokens|¥|\$)/i)
    expect(text).toContain('保持 UNKNOWN 真相')
  })

  it('shows no spinner of its own, because the strip already answers "still fetching?"', () => {
    // The card used to pass an `animate-spin` icon into StateShell's `action` slot. That slot is a
    // left-aligned block meant for a control, so the glyph rendered as a stray mark under the
    // description — visible in the desktop screenshot while every text assertion stayed green.
    // SCREEN_SPEC gives the first-frame strip that job; the card reports the failure, not the effort.
    renderOffline('overview')
    expect(document.querySelectorAll('[class*="animate-spin"]')).toHaveLength(0)
    expect(screen.getAllByRole('status').length).toBeGreaterThan(0)
  })
})
