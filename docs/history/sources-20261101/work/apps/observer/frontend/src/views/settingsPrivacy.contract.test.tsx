/**
 * WUI-12 · the settings page keeps its controls where they belong.
 *
 * The property under test is narrow and easy to break by accident: a control may exist only where the
 * page can actually honour it. Appearance qualifies (theme / layout / palette are this window's own
 * state and already travel in the address). Collection defaults, retention, storage bounds and the four
 * different "stops" do not — they belong to the collector, the shell and the native tool. So this file
 * counts buttons and checks WHERE they are, not just that the page renders.
 */
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'

import { SettingsPrivacyView } from '@/views/SettingsPrivacyView'
import { COLLECTION_GAPS, LIFECYCLE_ACTIONS } from '@/lib/collectionLifecycle'
import { mkSnap } from '@/test/snapshotFixture'

const snap = mkSnap({})

afterEach(cleanup)

describe('SettingsPrivacyView (WUI-12)', () => {
  it('shows the three appearance facts it was handed and calls the owner to change them', () => {
    const onTheme = vi.fn(); const onLayout = vi.fn(); const onPalette = vi.fn()
    render(<SettingsPrivacyView snap={snap} theme="dark" layout="full" palette="worklab"
                                onTheme={onTheme} onLayout={onLayout} onPalette={onPalette} />)
    expect(screen.getByText('深色')).toBeTruthy()
    expect(screen.getByText(/主窗（默认 1280×820/)).toBeTruthy()
    // the badge carries the palette's own name; the travels line says the same words in prose, so the
    // assertion targets the exact label rather than a substring that appears twice
    expect(screen.getByText('现行配色（默认）')).toBeTruthy()
    fireEvent.click(screen.getByRole('button', { name: '切到浅色' })); expect(onTheme).toHaveBeenCalledWith('light')
    fireEvent.click(screen.getByRole('button', { name: '切到紧凑 HUD' })); expect(onLayout).toHaveBeenCalledWith('compact')
    fireEvent.click(screen.getByRole('button', { name: '改用母版建议配色' })); expect(onPalette).toHaveBeenCalledWith('master')
  })

  it('every control on the page is an appearance control, and there are exactly three', () => {
    const { container } = render(<SettingsPrivacyView snap={snap} theme="dark" layout="full" palette="worklab"
                                                      onTheme={() => {}} onLayout={() => {}} onPalette={() => {}} />)
    const buttons = Array.from(container.querySelectorAll('button'))
    expect(buttons).toHaveLength(3)
    for (const button of buttons) {
      expect(button.closest('[data-appearance]'),
        `${button.textContent} sits outside the appearance block`).not.toBeNull()
    }
    // no switch, slider or checkbox anywhere: collection state is not this page's to offer
    expect(container.querySelectorAll('input, select, [role="switch"]').length).toBe(0)
  })

  it('names each collection gap with the producer that owns the answer', () => {
    const { container } = render(<SettingsPrivacyView snap={snap} />)
    const text = container.textContent || ''
    for (const gap of COLLECTION_GAPS) expect(text, gap.key).toContain(gap.question)
    expect(text).toContain('sidecar.py:274')
    expect(text).toContain('sse_hub.py:53')
    expect(text).toContain('config-ownership.json')
    // the gaps must not be dressed up as configured values
    expect(text).not.toMatch(/保留期\s*[:：]\s*\d/)
    expect(text).not.toMatch(/白名单\s*[:：]\s*(开|启)/)
  })

  it('keeps the four stops four apart, each with its own owner', () => {
    const { container } = render(<SettingsPrivacyView snap={snap} />)
    const rows = container.querySelectorAll('[data-lifecycle]')
    expect(rows).toHaveLength(LIFECYCLE_ACTIONS.length)
    const owners = LIFECYCLE_ACTIONS.map((action) => action.owner)
    expect(new Set(owners).size).toBe(owners.length)
    const text = container.textContent || ''
    expect(text).toContain('暂停滚动'); expect(text).toContain('停止采集')
    expect(text).toContain('关闭观察窗口'); expect(text).toContain('停止被观察的原生软件')
    // and the page never claims a stop it cannot perform
    expect(text).not.toMatch(/已停止采集|停采成功/)
  })

  it('without props it still renders and says the state was not handed to it', () => {
    const { container } = render(<SettingsPrivacyView snap={null} />)
    const text = container.textContent || ''
    expect(text).toContain('未由壳传入')
    expect(container.querySelectorAll('button')).toHaveLength(0)
  })

  it('states the privacy boundary in its own words rather than as a toggle', () => {
    const { container } = render(<SettingsPrivacyView snap={snap} />)
    const text = container.textContent || ''
    expect(text).toContain('提示词/回复正文')
    expect(text).toContain('不写 web storage')
  })

  // WUI-18(e)/WUI-11: the delivery card must keep three states apart and add no control.
  it('says "health was never read" when the snapshot carries no collectors section', () => {
    const { container } = render(<SettingsPrivacyView snap={mkSnap({})} />)
    expect(container.querySelector('[data-collector-gap]')).toBeTruthy()
    const text = container.textContent || ''
    expect(text).toContain('快照没有 collectors 字段')
    expect(text).not.toContain('当前没有登记任何采集器')
  })

  it('says "read, none registered" for an empty list, in different words', () => {
    const { container } = render(<SettingsPrivacyView snap={mkSnap({ collectors: [] })} />)
    expect(container.querySelector('[data-collector-unregistered]')).toBeTruthy()
    const text = container.textContent || ''
    expect(text).toContain('当前没有登记任何采集器')
    expect(text).not.toContain('快照没有 collectors 字段')
  })

  it('renders each collector with its delivered and refused counts and names the refusal location', () => {
    const { container } = render(<SettingsPrivacyView snap={mkSnap({
      collectors: [
        {
          collector: 'usage-files', totalRuns: 5, lastRunAt: '2026-10-10T00:00:00Z',
          lastSuccessAt: '2026-10-10T00:00:00Z', consecutiveFailures: 0, circuitOpen: false,
          droppedEvents: 1, refusedRows: 3, deliveredRows: 11,
          lastRefusalReason: '3 row(s) refused, most frequent reason: ValueError: forbidden sensitive '
            + 'field(s) (first seen at .hermes/task-artifacts/usage.jsonl:4)', fresh: true,
        },
        {
          collector: 'git-ci', totalRuns: 2, lastRunAt: '2026-10-10T00:00:00Z',
          lastSuccessAt: null, consecutiveFailures: 2, circuitOpen: false, droppedEvents: 0,
          refusedRows: 0, deliveredRows: 0, lastRefusalReason: null, fresh: false,
        },
      ],
    })} />)
    const rows = container.querySelectorAll('[data-collector-row]')
    expect(Array.from(rows).map((r) => r.getAttribute('data-collector-row'))).toEqual(['usage-files', 'git-ci'])
    const text = container.textContent || ''
    expect(text).toContain('交出 11 行')
    expect(text).toContain('拒绝 3 行')
    expect(text, 'the refusal must stay traceable to a line').toContain('usage.jsonl:4')
    expect(text).toContain('连续失败 2 次')
    expect(text, 'no collector here has its breaker open').not.toContain('熔断打开')
    // a refusing, still-fresh collector is the combination coverage cannot express — it must be said
    expect(container.querySelector('[data-collector-fresh-but-refusing="1"]')).toBeTruthy()
    // and the clean collector gets no invented reason line
    const clean = rows[1] as HTMLElement
    expect(clean.textContent).toContain('拒绝 0 行')
    expect(clean.textContent).not.toContain('拒绝原因：')
  })

  it('never turns the two counters into a percentage and never adds a control', () => {
    const { container } = render(<SettingsPrivacyView snap={mkSnap({
      collectors: [{
        collector: 'usage-files', totalRuns: 4, lastRunAt: 'x', lastSuccessAt: 'x',
        consecutiveFailures: 0, circuitOpen: false, droppedEvents: 0, refusedRows: 1,
        deliveredRows: 3, lastRefusalReason: '1 row(s) refused', fresh: true,
      }],
    })} theme="dark" layout="full" palette="worklab"
       onTheme={() => {}} onLayout={() => {}} onPalette={() => {}} />)
    const text = container.textContent || ''
    expect(text).not.toMatch(/\d+(\.\d+)?\s*%/)
    expect(text).toContain('这里不算比率')
    // the three appearance controls are still the only controls on the page; a delivery card that grew a
    // "clear refusals" button would be a write affordance inside a read-only projection
    expect(container.querySelectorAll('button')).toHaveLength(3)
    expect(container.querySelectorAll('input, select, [role="switch"]')).toHaveLength(0)
    for (const button of Array.from(container.querySelectorAll('button'))) {
      expect(button.closest('[data-collector-row]')).toBeNull()
    }
  })
})
