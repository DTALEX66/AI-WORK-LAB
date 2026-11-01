/** W01 / task #31 — the transport badge is derived, and its gate population is two-dimensional.
 *
 * The audit's finding: `TopStatusBar` computed `live ? 'LIVE' : (ts || 'UNKNOWN')`, so a local flag
 * outranked the backend verdict, and the sweep that was supposed to catch it (`laneTransportTruth`) could
 * not construct the failing case at all — "a payload that claims LIVE while the sampling has expired" was
 * outside its population. So this file sweeps the CROSS PRODUCT (transport state × freshness × read-path
 * health), not one axis: every cell must be printable without lying.
 *
 * The cells that matter:
 *   transport=LIVE, freshness=STALE, still reading -> "LIVE · 采样已过期" (connected, sampling expired)
 *   transport=LIVE, read path failed              -> OFFLINE  (the payload's word is not ours to repeat)
 *   transport=LIVE, not reading                   -> UNVERIFIED (we hold a projection, not a verdict)
 *   no snapshot                                   -> UNKNOWN, and no watermark claim either
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { TopStatusBar } from '@/components/layout/TopStatusBar'
import { transportTruth } from '@/lib/api'
import { mkSnap } from '@/test/snapshotFixture'
import type { SnapshotV3, TransportState } from '@/types'

afterEach(cleanup)

const TRANSPORT: Array<TransportState | 'UNSET'> = ['LIVE', 'OFFLINE', 'CONNECTING', 'DELAYED', 'UNSET']
const FRESHNESS = ['FRESH', 'STALE', 'UNKNOWN'] as const

function snapWith(
  state: TransportState | 'UNSET',
  freshness: (typeof FRESHNESS)[number],
  watermark?: string | null,
): SnapshotV3 {
  return mkSnap({
    transport: {
      transportState: state === 'UNSET' ? 'UNKNOWN' : state,
      freshnessState: freshness,
      connectedSince: null,
      eventsUrl: null,
    },
    sourceWatermark: watermark === undefined ? '2026-10-11T08:00:00Z' : watermark,
  }) as SnapshotV3
}

function render1(props: Partial<Parameters<typeof TopStatusBar>[0]> = {}) {
  return render(
    <TopStatusBar
      snap={mkSnap()}
      source="live"
      live={false}
      theme="dark"
      layout="full"
      onCycleTheme={() => {}}
      onCycleLayout={() => {}}
      {...props}
    />,
  )
}

function badgeWord(container: HTMLElement): string {
  const el = container.querySelector('[data-transport-state]')
  return (el?.textContent || '').trim()
}

function dotBackground(container: HTMLElement): string {
  const el = container.querySelector('.status-pulse') as HTMLElement | null
  return el?.style.background || ''
}

describe('transport truth derivation', () => {
  it('the read path failing outranks a payload that still says LIVE', () => {
    const snap = snapWith('LIVE', 'FRESH')
    expect(transportTruth(snap, true, '事件流中断').state).toBe('OFFLINE')
    expect(badgeWord(render1({ snap, live: true, error: '事件流中断' }).container)).toBe('OFFLINE')
  })

  it('not reading is UNVERIFIED, not the payload word', () => {
    const snap = snapWith('LIVE', 'FRESH')
    expect(transportTruth(snap, false, null).state).toBe('UNVERIFIED')
    expect(badgeWord(render1({ snap, live: false, error: null }).container)).toBe('UNVERIFIED')
  })

  it('no snapshot is UNKNOWN and carries no sampling claim', () => {
    const truth = transportTruth(null, false, null)
    expect(truth.state).toBe('UNKNOWN')
    expect(truth.watermark).toBeNull()
    expect(badgeWord(render1({ snap: null }).container)).toBe('UNKNOWN')
  })
})

describe('transport truth · freshness cross product', () => {
  for (const state of TRANSPORT) {
    for (const freshness of FRESHNESS) {
      it(`${state} × ${freshness}: the badge never prints a plain LIVE it cannot support`, () => {
        const snap = snapWith(state, freshness)
        const { container } = render1({ snap, live: true, error: null })
        const word = badgeWord(container)
        const claimed = state === 'LIVE' && freshness === 'FRESH'
        if (claimed) {
          expect(word).toBe('LIVE')
        } else {
          // The old code printed 'LIVE' whenever the local `live` flag was set, for every cell here.
          expect(word, `${state} × ${freshness} printed ${word}`).not.toBe('LIVE')
        }
        if (state === 'LIVE' && freshness !== 'FRESH') {
          expect(word).toContain('采样已过期')
        }
      })
    }
  }

  it('a LIVE transport with expired sampling is not coloured as healthy', () => {
    const healthy = render1({ snap: snapWith('LIVE', 'FRESH'), live: true }).container
    const stale = render1({ snap: snapWith('LIVE', 'STALE'), live: true }).container
    expect(dotBackground(healthy)).not.toBe('')
    expect(dotBackground(stale)).not.toBe(dotBackground(healthy))
  })

  it('the sampling moment travels with the claim', () => {
    const { container } = render1({ snap: snapWith('LIVE', 'FRESH', '2026-10-11T08:00:00Z'), live: true })
    const wm = container.querySelector('[data-transport-watermark]')
    expect(wm?.getAttribute('data-transport-watermark')).toBe('2026-10-11T08:00:00Z')
    expect(wm?.textContent).toContain('2026-10-11T08:00:00Z')
  })

  it('an absent watermark says so instead of printing a time', () => {
    const { container } = render1({ snap: snapWith('LIVE', 'STALE', null), live: true })
    const wm = container.querySelector('[data-transport-watermark]')
    expect(wm?.getAttribute('data-transport-watermark')).toBe('none')
    expect(wm?.textContent).toContain('采样时刻未投影')
  })
})
