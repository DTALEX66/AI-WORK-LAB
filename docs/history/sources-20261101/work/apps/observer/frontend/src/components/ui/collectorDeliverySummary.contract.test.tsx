/**
 * WUI-11/WUI-18: one collector delivery read, three reachable surfaces.
 *
 * The classification (absent / empty / reporting) is tested in
 * `lib/collectorDelivery.test.ts`. This file pins the rendered contract and,
 * more importantly, that Settings, Monitoring and Work cannot drift apart:
 * all three mount the same component against the same snapshot key.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { CollectorDeliverySummary } from '@/components/ui/collector-delivery'
import { MonitoringView } from '@/views/Views'
import { WorkView } from '@/views/WorkView'
import { SettingsPrivacyView } from '@/views/SettingsPrivacyView'
import { mkSnap } from '@/test/snapshotFixture'
import type { CollectorDelivery } from '@/types'

const mkCollector = (over: Partial<CollectorDelivery> = {}): CollectorDelivery => ({
  collector: 'sidecar',
  totalRuns: 4,
  lastRunAt: '2026-10-19T00:00:00Z',
  lastSuccessAt: '2026-10-19T00:00:00Z',
  consecutiveFailures: 0,
  circuitOpen: false,
  droppedEvents: 0,
  refusedRows: 0,
  deliveredRows: 7,
  lastRefusalReason: null,
  fresh: true,
  ...over,
})

afterEach(cleanup)

describe('CollectorDeliverySummary', () => {
  it('renders an absent key as a source gap, not as an empty collector list', () => {
    const { container } = render(<CollectorDeliverySummary collectors={undefined} />)
    expect(container.querySelector('[data-collector-gap="true"]')?.textContent).toContain('来源缺口')
    expect(container.querySelectorAll('[data-collector-row]')).toHaveLength(0)
    expect(container.textContent).not.toContain('这里不算比率')
  })

  it('renders an empty list as registered-but-none, not as a gap', () => {
    const { container } = render(<CollectorDeliverySummary collectors={[]} />)
    expect(container.querySelector('[data-collector-unregistered="true"]')?.textContent).toContain('没有登记任何采集器')
    expect(container.querySelector('[data-collector-gap]')).toBeNull()
  })

  it('renders a measured zero as zero lines and no refusal', () => {
    const { container } = render(
      <CollectorDeliverySummary collectors={[mkCollector({ deliveredRows: 0, totalRuns: 0 })]} />,
    )
    const row = container.querySelector('[data-collector-row="sidecar"]')
    expect(row?.textContent).toContain('交出 0 行')
    expect(row?.textContent).toContain('拒绝 0 行')
    expect(row?.textContent).toContain('运行 0 次')
    expect(container.querySelector('[data-collector-fresh-but-refusing]')).toBeNull()
  })

  it('keeps fresh and still-refusing as two facts on the same row', () => {
    const { container } = render(
      <CollectorDeliverySummary
        collectors={[mkCollector({ refusedRows: 3, lastRefusalReason: 'schema mismatch', fresh: true })]}
      />,
    )
    const row = container.querySelector('[data-collector-row="sidecar"]')
    expect(row?.textContent).toContain('拒绝 3 行')
    expect(row?.textContent).toContain('schema mismatch')
    expect(container.querySelector('[data-collector-fresh-but-refusing="1"]')?.textContent)
      .toContain('新鲜却仍在拒绝行')
  })
})

describe('the three surfaces mount the same reading', () => {
  const snap = mkSnap({ collectors: [mkCollector()] })

  it('settings renders the shared row', () => {
    const { container } = render(<SettingsPrivacyView snap={snap} />)
    expect(container.querySelector('[data-collector-row="sidecar"]')?.textContent).toContain('交出 7 行')
  })

  it('monitoring renders the shared row', () => {
    const { container } = render(<MonitoringView snap={snap} />)
    expect(container.querySelector('[data-collector-row="sidecar"]')?.textContent).toContain('交出 7 行')
  })

  it('work renders the shared row and states that it cannot attribute it to the focused record', () => {
    const { container } = render(<WorkView snap={snap} />)
    const text = container.textContent || ''
    expect(container.querySelector('[data-collector-row="sidecar"]')?.textContent).toContain('交出 7 行')
    expect(text).toContain('不能把它算到当前记录名下')
  })
})
