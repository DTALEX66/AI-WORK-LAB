// U04: the view registry is the single source of truth for navigation. The
// legacy array-index coupling (Sidebar had 8 items, the views array had 10)
// left Delivery/Trust/Settings unreachable. These regression tests pin:
//   1. every registry lane has a real component (no orphan / unreachable view)
//   2. the lanes required by the taskpack all exist
//   3. unknown ids don't crash (App falls back to Overview)
import { describe, it, expect } from 'vitest'
import { VIEW_REGISTRY, VIEW_BY_ID, OVERVIEW_ID } from '@/lib/viewRegistry'
import {
  NAV_GROUPS, DAILY_DESTINATION_IDS, HOME_LANE_ID, OFF_DEFAULT_NAV_IDS, OFF_NAV_NOTES,
  knownLaneIds, isOnDefaultNav, railLaneIds, navInvariantViolations, paletteGroupForLane,
} from '@/lib/navigation'

describe('U04 view registry (no orphan / unreachable view)', () => {
  it('every registry entry has a non-null component', () => {
    for (const v of VIEW_REGISTRY) {
      expect(v.component, `view ${v.id} has no component`).toBeDefined()
    }
  })

  it('the taskpack-required lanes are all reachable by stable id', () => {
    const ids = new Set(VIEW_REGISTRY.map((v) => v.id))
    for (const required of ['agents', 'executions', 'models', 'memory', 'tools', 'monitoring', 'delivery', 'trust', 'settings', 'projects']) {
      expect(ids.has(required), `lane ${required} missing`).toBe(true)
    }
  })

  it('VIEW_BY_ID exposes every id and has no duplicate ids', () => {
    const ids = VIEW_REGISTRY.map((v) => v.id)
    expect(new Set(ids).size).toBe(ids.length)
    for (const id of ids) {
      expect(VIEW_BY_ID[id], `registry lookup failed for ${id}`).toBeDefined()
    }
  })

  it('S31/32 software lane is present as a read-only projection view', () => {
    expect(VIEW_BY_ID['software']).toBeDefined()
  })

  it('OVERVIEW is the synthetic landing lane (not a registry component)', () => {
    expect(OVERVIEW_ID).toBe('overview')
    expect(VIEW_REGISTRY.find((v) => v.id === OVERVIEW_ID)).toBeUndefined()
  })

  // P1-01 (2026-09-26) pinned "exactly 7 primary nav groups". That number was a snapshot of one IA, and
  // WUI-01 changes the IA — the taskpack's rule is to repair the stale count assertion rather than
  // substitute a permanent 5, so these assertions are derived from the navigation model itself: the
  // partition must be exact, unique and complete, whatever number of groups that turns out to be.
  it('the navigation model partitions every reachable lane exactly once', () => {
    expect(navInvariantViolations(), 'lib/navigation reports an incoherent IA').toEqual([])
    const flat = NAV_GROUPS.flatMap((g) => g.ids)
    expect(new Set(flat).size, 'no lane may appear in two groups').toBe(flat.length)
    expect(new Set(NAV_GROUPS.map((g) => g.key)).size).toBe(NAV_GROUPS.length)
    expect(new Set(railLaneIds())).toEqual(new Set([...knownLaneIds()].filter(isOnDefaultNav)))
  })

  it('the home is a daily destination and there is exactly one of them', () => {
    expect(HOME_LANE_ID).toBe(OVERVIEW_ID)
    expect(DAILY_DESTINATION_IDS.filter((id) => id === HOME_LANE_ID)).toHaveLength(1)
    expect(isOnDefaultNav(HOME_LANE_ID)).toBe(true)
    // 不建立双首页: no registry lane may claim the landing role alongside the synthetic home.
    const homeNamed = VIEW_REGISTRY.filter((entry) => entry.id === HOME_LANE_ID)
    expect(homeNamed).toEqual([])
  })

  // WUI-01: workflow-editor left the default nav. Deleting it would have destroyed a working surface and
  // broken its deep link, so the contract is that it is DEMOTED — implementation and address intact, a
  // stated reason present, and the palette still the way in.
  it('a lane can leave the default nav without losing its implementation, address or explanation', () => {
    expect(OFF_DEFAULT_NAV_IDS.length).toBeGreaterThan(0)
    for (const id of OFF_DEFAULT_NAV_IDS) {
      expect(VIEW_BY_ID[id], `off-nav lane ${id} lost its registry entry`).toBeDefined()
      expect(VIEW_BY_ID[id].component, `off-nav lane ${id} lost its component`).toBeDefined()
      expect(OFF_NAV_NOTES[id], `off-nav lane ${id} leaves the rail with no stated reason`).toBeTruthy()
      expect(isOnDefaultNav(id)).toBe(false)
      expect(paletteGroupForLane(id), `the palette must name ${id} as an experimental entry`)
        .toBe('实验入口（不在默认导航）')
    }
  })

  it('every other reachable lane still has exactly one rail home', () => {
    for (const entry of VIEW_REGISTRY) {
      if (OFF_DEFAULT_NAV_IDS.includes(entry.id)) continue
      const groups = NAV_GROUPS.filter((g) => g.ids.includes(entry.id))
      expect(groups, `lane ${entry.id} is in no nav group`).toHaveLength(1)
    }
    expect(NAV_GROUPS.filter((g) => g.ids.includes(OVERVIEW_ID)), 'the home lane is in no nav group')
      .toHaveLength(1)
  })
})
