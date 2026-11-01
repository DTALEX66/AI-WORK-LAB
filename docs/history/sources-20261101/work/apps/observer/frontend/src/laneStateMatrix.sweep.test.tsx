/** Per-lane state matrix: what each lane can actually render when data is absent or refused.
 *
 * The prompt's state list is ten states (success / empty / loading / offline / stale / unknown /
 * backend-not-implemented / permission-denied / error / cancelled / recovering). Two of them were never
 * measured per lane, and the gap matters in opposite directions:
 *
 *  - `loading` must not be painted as `unknown`-looking zero data, and must never show a success pill;
 *  - `permission-denied` may only appear on a lane that has an action to be denied. A read-only lane that
 *    renders a permission widget is faking a capability the product does not have — the same lie in the
 *    other direction.
 *
 * So this sweep measures every registry lane twice (no snapshot yet, and a refused-action snapshot),
 * prints the matrix it observed, and asserts only properties that are true for all lanes plus the two
 * per-lane rules above. It deliberately does not require a read-only lane to have a permission state.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { VIEW_REGISTRY, OVERVIEW_ID } from '@/lib/viewRegistry'
import { OverviewView } from '@/views/OverviewView'
import { mkSnap } from '@/test/snapshotFixture'
import type { SnapshotV3 } from '@/types'

afterEach(cleanup)

const lanes = VIEW_REGISTRY.filter((entry) => entry.component)

/** Lanes whose subject includes an operator action, so 无权限 is a real state for them. */
const ACTION_LANES = ['approvals']

function successPills(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll('.tag.ok, [data-tone="success"]'))
    .map((element) => (element.textContent || '').trim())
}

function renderLane(entryId: string, snap: SnapshotV3 | null) {
  if (entryId === OVERVIEW_ID) return render(<OverviewView snap={snap as never} source="stale" live={false} />)
  const entry = VIEW_REGISTRY.find((item) => item.id === entryId)!
  const Component = entry!.component as unknown as (props: { snap: SnapshotV3 | null }) => JSX.Element
  return render(<Component snap={snap} />)
}

describe('lane state matrix', () => {
  it('the sweep still covers every registered lane', () => {
    expect(lanes.length).toBeGreaterThanOrEqual(15)
    for (const lane of ACTION_LANES) {
      expect(lanes.map((entry) => entry.id), `action lane ${lane} left the registry`).toContain(lane)
    }
  })

  it('no lane shows a success pill or a fabricated zero before the first snapshot', () => {
    const observed: Array<{ lane: string; pills: number; hasEmptyState: boolean; showsUnknown: boolean }> = []
    for (const entry of lanes) {
      const { container } = renderLane(entry.id, null)
      const pills = successPills(container)
      const text = container.textContent || ''
      observed.push({
        lane: entry.id,
        pills: pills.length,
        hasEmptyState: Boolean(container.querySelector('.empty')),
        showsUnknown: /UNKNOWN|未接入|未知|来源缺口/.test(text),
      })
      expect(pills, `${entry.id} reported success with no snapshot: ${pills.join(',')}`).toEqual([])
      // a lane that has no data must not collapse into a bare "0" — the whole page saying zero is the
      // fabricated-zero shape this rule exists to catch
      expect(text.trim()).not.toMatch(/^0+$/)
    }
    // report, do not assert: an unmeasured lane must not be able to hide behind a vacuous pass
    console.info('LANE_STATE_MATRIX_NO_SNAPSHOT ' + JSON.stringify(observed))
    expect(observed.length).toBe(lanes.length)
    expect(observed.every((row) => row.pills === 0)).toBe(true)
  })

  it('a refused action is stated where an action exists and never invented where it does not', () => {
    // PermissionState's own default title is the signature, so both directions can fail: a missing
    // statement on a lane that has rows, and a permission block conjured up for rows that are not there.
    const MARKER = '此界面只读'
    const transport = { transportState: 'OFFLINE', freshnessState: 'STALE', connectedSince: null, eventsUrl: null }
    const noRows = mkSnap({ transport } as unknown as Partial<SnapshotV3>)
    const withRows = mkSnap({
      transport,
      workspace: {
        plan: { status: 'running', counts: {}, approvals: [{ id: 'AP-1', state: 'WAITING_APPROVAL', risk: 'high' }] },
      },
    } as unknown as Partial<SnapshotV3>)

    for (const entry of lanes) {
      const without = renderLane(entry.id, noRows)
      const withoutMarker = (without.container.textContent || '').includes(MARKER)
      cleanup()

      const withAction = renderLane(entry.id, withRows)
      const withMarker = (withAction.container.textContent || '').includes(MARKER)
      cleanup()

      if (ACTION_LANES.includes(entry.id)) {
        expect(withoutMarker, `${entry.id} showed a permission block with no rows to decide`).toBe(false)
        expect(withMarker,
          `${entry.id} has rows and must say what is blocked, why, and what remains readable`).toBe(true)
      } else {
        expect(withMarker, `${entry.id} rendered a permission state for an action it does not have`).toBe(false)
      }
    }
  })

  it('an offline snapshot never reads as a live projection in any lane', () => {
    const snapshot = mkSnap({
      transport: { transportState: 'OFFLINE', freshnessState: 'STALE', connectedSince: null, eventsUrl: null },
    })
    for (const entry of lanes) {
      const { container } = renderLane(entry.id, snapshot)
      const lying = successPills(container).filter((label) => /LIVE|已连接|在线/i.test(label))
      expect(lying, `${entry.id} claimed liveness against an OFFLINE snapshot`).toEqual([])
    }
  })

  it('the collector delivery card keeps gap, empty and measured states apart in its lane', () => {
    const LANE = 'privacy'

    const gap = renderLane(LANE, mkSnap({}))
    expect(gap.container.querySelector('[data-collector-gap="true"]')?.textContent).toContain('来源缺口')
    expect(gap.container.querySelectorAll('[data-collector-row]')).toHaveLength(0)
    cleanup()

    const empty = renderLane(LANE, mkSnap({ collectors: [] } as unknown as Partial<SnapshotV3>))
    expect(empty.container.querySelector('[data-collector-unregistered="true"]')?.textContent)
      .toContain('没有登记任何采集器')
    expect(empty.container.querySelector('[data-collector-gap]')).toBeNull()
    expect(empty.container.querySelectorAll('[data-collector-row]')).toHaveLength(0)
    cleanup()

    const measured = renderLane(LANE, mkSnap({
      collectors: [{
        collector: 'sidecar', totalRuns: 4,
        lastRunAt: '2026-10-19T00:00:00Z', lastSuccessAt: '2026-10-19T00:00:00Z',
        consecutiveFailures: 0, circuitOpen: false, droppedEvents: 0,
        refusedRows: 2, deliveredRows: 7, lastRefusalReason: 'schema mismatch', fresh: true,
      }],
    } as unknown as Partial<SnapshotV3>))
    const row = measured.container.querySelector('[data-collector-row="sidecar"]')
    expect(row?.textContent).toContain('交出 7')
    expect(row?.textContent).toContain('拒绝 2')
    expect(row?.textContent).not.toMatch(/\d+(\.\d+)?\s*%/)
    expect(measured.container.querySelector('[data-collector-fresh-but-refusing="1"]')).not.toBeNull()
  })
})
