/** Every lane must tell the transport truth it was handed (UI prompt pack: 诚实态, 不伪造).
 *
 * This sweep exists because a text search cannot make the claim: measuring 21 lanes × 4 transport
 * scenarios showed the words LIVE/DELAYED/OFFLINE appearing in lanes that were *explaining the rule*
 * ("非实时健康度", "LIVE 仅当 live-gate verdict 为 LIVE"), so an assertion over `textContent` would have
 * failed honest UI. The properties pinned here are the element-level ones the measurement supports:
 *
 *  1. a success-toned pill may never read `LIVE` while the snapshot says the transport is not LIVE;
 *  2. the lanes whose subject *is* the transport carry the snapshot's own state word;
 *  3. a snapshot with no collected data draws no fabricated zero.
 *
 * The first case is the detector self-control: a pill fabricated against an OFFLINE snapshot must be
 * refused, otherwise "all lanes clean" and "the detector is blind" share one verdict.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { VIEW_REGISTRY } from '@/lib/viewRegistry'
import { Badge } from '@/components/ui/badge'
import { mkSnap, UNKNOWN_GOVERNANCE } from '@/test/snapshotFixture'
import type { SnapshotV3 } from '@/types'

afterEach(cleanup)

const lanes = VIEW_REGISTRY.filter((e) => e.component)

const scenarios: Array<[string, SnapshotV3]> = [
  ['LIVE', mkSnap()],
  ['OFFLINE', mkSnap({ transport: { transportState: 'OFFLINE', freshnessState: 'STALE', connectedSince: null, eventsUrl: null } })],
  ['CONNECTING', mkSnap({ transport: { transportState: 'CONNECTING', freshnessState: 'UNKNOWN', connectedSince: null, eventsUrl: null }, governance: UNKNOWN_GOVERNANCE })],
  ['DELAYED', mkSnap({ transport: { transportState: 'DELAYED', freshnessState: 'STALE', connectedSince: null, eventsUrl: null }, governance: UNKNOWN_GOVERNANCE })],
]

/** The lanes that render the transport itself, not a projection of collected data. */
const TRANSPORT_LANES = ['executions', 'trust', 'observer', 'settings', 'monitoring']

function successPills(container: HTMLElement): string[] {
  return Array.from(container.querySelectorAll('.tag.ok, [data-tone="success"]'))
    .map((el) => (el.textContent || '').trim())
}

describe('lane transport truth', () => {
  it('the registry still carries the lanes this sweep exists to cover', () => {
    expect(lanes.length).toBeGreaterThanOrEqual(15)
    const present = lanes.map((e) => e.id)
    for (const lane of TRANSPORT_LANES) {
      expect(present, `transport lane ${lane} left the registry; this sweep would shrink silently`)
        .toContain(lane)
    }
  })

  it('a success pill reading LIVE against an OFFLINE snapshot is refused', () => {
    const { container } = render(
      <div><Badge variant="success">LIVE</Badge></div>,
    )
    const snap = mkSnap({ transport: { transportState: 'OFFLINE', freshnessState: 'STALE', connectedSince: null, eventsUrl: null } })
    expect(successPills(container)).toEqual(['LIVE'])
    const lying = successPills(container).filter((t) => /LIVE/.test(t) && snap.transport.transportState !== 'LIVE')
    expect(lying).not.toEqual([])
  })

  it.each(scenarios)('%s: no lane decorates a non-LIVE transport as LIVE', (state, snap) => {
    for (const lane of lanes) {
      const C = lane.component as (props: { snap: SnapshotV3 | null }) => JSX.Element
      const { container } = render(<C snap={snap} />)
      const lies = state !== 'LIVE'
        ? successPills(container).filter((t) => /\bLIVE\b/.test(t))
        : []
      expect(lies, `${lane.id} shows a LIVE success pill while transport=${state}`).toEqual([])
    }
  })

  it.each(scenarios)('%s: the transport lanes carry the snapshot state word', (state, snap) => {
    for (const id of TRANSPORT_LANES) {
      const entry = lanes.find((e) => e.id === id)
      expect(entry, `lane ${id} disappeared from the registry`)
        .toBeDefined()
      const C = (entry as { component: (p: { snap: SnapshotV3 | null }) => JSX.Element }).component
      const { container } = render(<C snap={snap} />)
      expect(container.textContent || '', `${id} does not surface transport=${state}`)
        .toContain(state)
    }
  })

  it('an empty collection set draws no fabricated zero in any lane', () => {
    const snap = mkSnap({
      projects: [], executions: [], tasks: {}, tokenSummary: undefined,
      coverage: { numerator: 0, denominator: 0, scope: 'collectors' },
      governance: UNKNOWN_GOVERNANCE,
    })
    for (const lane of lanes) {
      const C = lane.component as (props: { snap: SnapshotV3 | null }) => JSX.Element
      const { container } = render(<C snap={snap} />)
      const zeros = Array.from(container.querySelectorAll('.kpi strong, .metric-box strong, .kpi-number'))
        .map((el) => (el.textContent || '').trim())
        .filter((t) => /^0(\/0|\.0)?$/.test(t))
      expect(zeros, `${lane.id} prints a zero where the snapshot has nothing`).toEqual([])
    }
  })
})
