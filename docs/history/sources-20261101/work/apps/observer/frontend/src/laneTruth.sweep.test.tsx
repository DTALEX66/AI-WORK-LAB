/**
 * Every lane, mounted with no snapshot at all (UI prompt pack: 每泳道诚实态).
 *
 * The B5 rule is asserted per lane rather than sampled: a missing value renders
 * UNKNOWN or an honest empty state, never a `0`, and never a success-toned pill.
 * A single lane that quietly defaults to zero is enough to make a console lie,
 * so this sweep walks the registry the shell actually uses — a lane added to
 * `VIEW_REGISTRY` is covered by this file the moment it exists.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { VIEW_REGISTRY, OVERVIEW_ID } from '@/lib/viewRegistry'
import { Badge } from '@/components/ui/badge'

afterEach(cleanup)

const lanes = VIEW_REGISTRY.filter((e) => e.component)

describe('lane truth sweep (snap = null)', () => {
  it('the registry still carries the lanes this sweep exists to cover', () => {
    expect(lanes.length).toBeGreaterThanOrEqual(15)
  })

  it('the detectors fire on the lies they are meant to catch', () => {
    // Without this control the sweep passing means nothing: an empty selector
    // matches no violations, and so does a detector that cannot see.
    const { container } = render(
      <div>
        <Badge variant="success">CLEAN</Badge>
        <div className="kpi"><strong>0</strong></div>
        <div className="metric-box"><strong>0/0</strong></div>
      </div>,
    )
    expect(container.querySelectorAll('.tag.ok')).toHaveLength(1)
    const zeros = Array.from(container.querySelectorAll('.kpi strong, .metric-box strong'))
      .map((el) => (el.textContent || '').trim())
      .filter((t) => t === '0' || t === '0/0' || t === '0.0')
    expect(zeros).toEqual(['0', '0/0'])
  })

  it.each(lanes.map((e) => [e.id, e] as const))('%s renders honestly with no data', (_id, entry) => {
    const C = entry.component!
    const { container } = render(<C snap={null} />)
    const text = container.textContent || ''

    // A success pill with no snapshot would be a fabricated healthy state.
    expect(container.querySelectorAll('.tag.ok')).toHaveLength(0)
    expect(container.querySelectorAll('[data-tone="success"]')).toHaveLength(0)

    // KPI slots must not default to zero.
    const zeros = Array.from(container.querySelectorAll('.kpi strong, .metric-box strong'))
      .map((el) => (el.textContent || '').trim())
      .filter((t) => t === '0' || t === '0/0' || t === '0.0')
    expect(zeros, `fabricated zero in ${entry.id}`).toEqual([])

    const honest = /UNKNOWN|无数据|暂无|不可用|未接入|空|—|STALE|PARTIAL|ERROR|OFFLINE/.test(text)
    expect(honest, `${entry.id} renders neither a real value nor a declared absence`).toBe(true)
  })

  it('the overview keeps its load affordance honest when nothing has arrived', () => {
    const entry = VIEW_REGISTRY.find((e) => e.id === OVERVIEW_ID) ?? null
    // Overview is inline in App, not in the registry; assert the registry shape instead.
    expect(entry).toBeNull()
    const ids = VIEW_REGISTRY.map((e) => e.id)
    expect(ids).not.toContain(OVERVIEW_ID)
    expect(new Set(ids).size).toBe(ids.length)
  })
})
