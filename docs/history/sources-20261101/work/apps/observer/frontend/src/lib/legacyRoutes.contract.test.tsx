/**
 * WUI-13 · the 23 legacy routes, checked against the owner's own seed table.
 *
 * The point of this file is that the ledger is not a transcription someone can quietly stop maintaining:
 * it reads `frontend_route_mapping.proposed.csv` from the archived input and fails on any difference in
 * the id set, so adding a lane, demoting one, or editing the seed table all have to be reconciled here.
 * It then proves the two behaviours the taskpack actually demands of a compatibility entry: the old
 * address still resolves to a real lane, and an object id the projection does not carry produces an
 * explicit statement instead of "the newest one" or "the one with a similar name".
 */
import { readFileSync } from 'node:fs'
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

const mocks = vi.hoisted(() => ({
  live: { snap: null as any, source: 'live' as any, live: true, error: null as string | null },
}))
vi.mock('@/lib/api', async (importOriginal) => {
  const actual = await importOriginal<typeof import('@/lib/api')>()
  return { ...actual, useLiveSnapshot: () => mocks.live }
})

import App from '@/App'
import { VIEW_BY_ID, OVERVIEW_ID } from '@/lib/viewRegistry'
import { OFF_DEFAULT_NAV_IDS } from '@/lib/navigation'
import { EVIDENCE_PARAM_NAMES } from '@/lib/evidenceRange'
import { LEGACY_ROUTE_ROWS, LEGACY_SEED_IDS, laneForSeed, legacyRouteViolations, resolveLegacyRoute } from '@/lib/legacyRoutes'
import { readRecordFocus } from '@/lib/recordFocus'
import { mkSnap, mkExecution } from '@/test/snapshotFixture'

// vitest runs with the frontend directory as its working directory.
const SEED_CSV = '../../../docs/history/owner-inputs/20261009/final-readable/inputs/frontend_route_mapping.proposed.csv'

function seedColumn(): string[] {
  const lines = readFileSync(SEED_CSV, 'utf8').replace(/^﻿/, '').trim().split(/\r?\n/)
  const header = lines.shift() || ''
  expect(header.split(',')[0]).toBe('legacy_route_id')
  return lines.map((line) => line.split(',')[0].trim()).filter(Boolean)
}

afterEach(cleanup)

describe('legacy route ledger vs the owner seed table (WUI-13)', () => {
  it('covers exactly the 23 seed ids, in the same set', () => {
    const seeds = seedColumn()
    expect(seeds).toHaveLength(23)
    expect(new Set(seeds).size).toBe(23)
    expect([...LEGACY_SEED_IDS].sort()).toEqual([...seeds].sort())
  })

  it('the ledger is internally coherent', () => {
    expect(legacyRouteViolations()).toEqual([])
  })

  it('every seed resolves to a lane with a real component', () => {
    for (const row of LEGACY_ROUTE_ROWS) {
      const lane = laneForSeed(row.seedId)
      expect(lane, `seed ${row.seedId} resolves to nothing`).toBeTruthy()
      if (lane === OVERVIEW_ID) continue
      expect(VIEW_BY_ID[lane!].component, `seed ${row.seedId} resolves to a lane without a component`).toBeDefined()
    }
  })

  it('the demoted rows are exactly the lanes that left the default nav', () => {
    const demoted = LEGACY_ROUTE_ROWS.filter((row) => row.disposition === 'demoted')
      .map((row) => row.resolvesTo)
    expect(demoted.sort()).toEqual([...OFF_DEFAULT_NAV_IDS].sort())
  })

  it('keeps the four object namespaces as four separate addresses', () => {
    const recordRows = LEGACY_ROUTE_ROWS.filter((row) => row.params.length > 0)
    const params = new Set(recordRows.flatMap((row) => [...row.params]))
    expect(params.has('taskId')).toBe(true)
    expect(params.has('executionId')).toBe(true)
    expect(params.has('projectId')).toBe(true)
    for (const name of EVIDENCE_PARAM_NAMES) expect(params.has(name)).toBe(true)
    // no row may claim a parameter the URL reader would refuse
    const parsed = readRecordFocus('?view=work&taskId=WL-1&executionId=ex-9&projectId=work-lab')
    expect(parsed.rejected).toEqual([])
    expect(parsed.focus).toMatchObject({ taskId: 'WL-1', executionId: 'ex-9', projectId: 'work-lab' })
  })
})

describe('a compatibility entry never substitutes another object', () => {
  it('a stale executionId names the id it was asked for and shows no other execution', () => {
    mocks.live = {
      snap: mkSnap({ executions: [mkExecution({ executionId: 'ex-real', anchorProjectId: 'work-lab' })] }),
      source: 'live', live: true, error: null,
    }
    window.history.replaceState(null, '', '/index.html?view=work&executionId=ex-ghost')
    const { container } = render(<App />)
    const text = container.textContent || ''
    expect(text).toContain('ex-ghost')
    expect(screen.getByText(/快照的 executions 里没有这条执行/)).toBeTruthy()
    // Scoped to the Inspector: the lane's own list legitimately still shows the executions the
    // projection carries. The property is that the DETAIL of a stale address is not filled by a
    // neighbouring record — asserting the whole page would only prove the list is empty.
    const inspector = container.querySelector('[data-record-kind="execution"]')
    expect(inspector, 'the execution detail block did not render').not.toBeNull()
    expect(inspector!.textContent).toContain('ex-ghost')
    expect(inspector!.textContent).not.toContain('ex-real')
  })

  it('a stale projectId is refused by identity, not resolved to the closest name', () => {
    mocks.live = { snap: mkSnap({ projects: [mkSnap({}).projects[0]] }), source: 'live', live: true, error: null }
    window.history.replaceState(null, '', '/index.html?view=project-detail&projectId=some-other-repo')
    const { container } = render(<App />)
    const text = container.textContent || ''
    expect(text).toContain('some-other-repo')
    expect(text).toContain('该项目不在投影里')
    expect(text).not.toContain('工作轴 · 活动')
  })

  it('the demoted lane still answers its old address and explains why it left the rail', () => {
    const row = resolveLegacyRoute('workflow-editor')
    expect(row?.disposition).toBe('demoted')
    mocks.live = { snap: null, source: 'live', live: true, error: null }
    window.history.replaceState(null, '', '/index.html?view=workflow-editor')
    const { container } = render(<App />)
    expect(container.querySelector('[data-testid="off-nav-entry-note"]')).not.toBeNull()
  })
})
