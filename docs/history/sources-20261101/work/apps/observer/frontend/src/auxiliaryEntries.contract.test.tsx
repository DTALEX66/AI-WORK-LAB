/**
 * AUXILIARY ENTRY CONTRACT (WL-REC-0103 §2 -- "诊断与隐私为辅助入口").
 *
 * The pack asks for two things that are easy to fake: a 诊断 entry and a 隐私 entry, grouped as auxiliary
 * rather than as destinations. This repo already owned both surfaces -- `monitoring` is the bounded
 * diagnostics lane WUI-11 shipped and `privacy` is the collection-lifecycle page WUI-12 shipped -- so the
 * correct change is a grouping, NOT a third projection and NOT a new lane id. The assertions below are
 * written so that each of the shortcuts I could have taken shows up as a red:
 *
 *   * inventing a `diagnostics` lane would duplicate 监控's projection (assertion 2 fails: an auxiliary id
 *     that is not a registry lane);
 *   * naming a group 辅助 without putting anything in it would leave the word unreachable (assertion 4);
 *   * asserting the palette's filter by re-typing its predicate would pass while the real search is blind,
 *     so the test imports `filterItems` from the overlay itself and drives a query that must return nothing.
 *
 * The word 诊断 is deliberately not inside either lane's own label (`监控`, `隐私与采集`); it lives in the
 * section caption, which is the second field the palette matches. That is the mechanism, and assertion 4
 * is what proves it is the mechanism rather than a coincidence of the label text.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { Sidebar } from '@/components/layout/Sidebar'
import { filterItems, type PaletteItem } from '@/components/ui/command-palette'
import { VIEW_REGISTRY } from '@/lib/viewRegistry'
import { mkSnap } from '@/test/snapshotFixture'
import {
  AUXILIARY_GROUP_KEY, NAV_GROUPS, auxiliaryLaneIds, groupOfLane, isOnDefaultNav,
  navInvariantViolations, paletteGroupForLane,
} from '@/lib/navigation'

afterEach(cleanup)

/** The palette list exactly as App builds it: every registry lane, labelled and grouped by the same two
 *  functions the shell uses. Nothing here is a fixture of "expected palette content". */
const paletteItems = (): PaletteItem[] =>
  VIEW_REGISTRY.map((entry) => ({
    id: `nav-${entry.id}`,
    label: entry.label,
    group: paletteGroupForLane(entry.id),
    run: () => {},
  }))

describe('auxiliary entries (WUI-22)', () => {
  it('the grouping model is still self-consistent after the move', () => {
    expect(navInvariantViolations(),
           `nav invariants broken: ${navInvariantViolations().join(' | ')}`).toEqual([])
  })

  it('the auxiliary section holds exactly the two existing lanes, and adds no new projection', () => {
    const ids = auxiliaryLaneIds()
    expect(ids).toEqual(['monitoring', 'privacy'])
    const registryIds = new Set(VIEW_REGISTRY.map((entry) => entry.id))
    for (const id of ids) {
      expect(registryIds.has(id),
             `auxiliary lane ${id} is not a registry lane -- an auxiliary entry must be an existing surface`)
        .toBe(true)
      expect(isOnDefaultNav(id), `auxiliary lane ${id} is off the rail, so it is not an entry`).toBe(true)
      expect(groupOfLane(id)?.key).toBe(AUXILIARY_GROUP_KEY)
    }
    // one lane, one group: the duplicate-group rule is what keeps a caption from claiming the same entry twice
    const flat = NAV_GROUPS.flatMap((group) => group.ids)
    expect(flat.filter((id) => ids.includes(id))).toHaveLength(ids.length)
  })

  it('the rail renders the 诊断与隐私 caption and both lanes inside its own region', () => {
    const { container } = render(<Sidebar activeView="overview" onSelect={() => {}} />)
    const toggles = Array.from(container.querySelectorAll<HTMLButtonElement>('.nav button.nav-group-toggle'))
    const caption = toggles.find((button) => (button.textContent ?? '').includes('诊断与隐私'))
    expect(caption, 'no rail section is captioned 诊断与隐私').toBeTruthy()
    const regionId = caption?.getAttribute('aria-controls')
    expect(regionId, 'the auxiliary caption is not a disclosure control').toBeTruthy()
    const region = container.querySelector(`#${regionId}`)
    expect(region, `aria-controls ${regionId} names no element`).not.toBeNull()
    for (const id of auxiliaryLaneIds()) {
      expect(region?.querySelector(`button[data-lane="${id}"]`),
             `lane ${id} is not painted inside the auxiliary region`).not.toBeNull()
    }
  })

  it('typing 诊断 or 隐私 in the real palette finds the auxiliary entries', () => {
    const byDiagnostics = filterItems(paletteItems(), '诊断').map((item) => item.id)
    expect(byDiagnostics, 'nothing in the palette matches 诊断 -- the entry is unfindable by its own name')
      .toContain('nav-monitoring')
    expect(byDiagnostics).toContain('nav-privacy')
    expect(filterItems(paletteItems(), '隐私').map((item) => item.id)).toContain('nav-privacy')
    // negative control: the filter is not a match-anything function, so the hits above mean something
    expect(filterItems(paletteItems(), 'zzz-not-a-lane-zzz'),
           'the palette filter returned rows for a query no label or group contains').toEqual([])
  })

  it('no section caption still claims 隐私 while the lane itself lives in the auxiliary group', () => {
    // Two claimants for one word is how a nav model starts lying about its own structure.
    const claiming = NAV_GROUPS.filter((group) => group.label.includes('隐私')
      && group.key !== AUXILIARY_GROUP_KEY)
    expect(claiming.map((group) => `${group.key}=${group.label}`),
           'a non-auxiliary group also names 隐私').toEqual([])
  })

  it('the 诊断 lane mounts the eight-state matrix, so the auxiliary entry has content behind the name', () => {
    // WUI-11 shipped StateMatrixCard and nothing rendered it: the component was reachable only from its own
    // unit test, which is how a delivered feature becomes an unreferenced file. Mounting is asserted through
    // the registry entry the rail actually opens, not by importing the card again here.
    const entry = VIEW_REGISTRY.find((candidate) => candidate.id === 'monitoring')
    expect(entry, 'the registry has no monitoring lane').toBeTruthy()
    const Lane = entry!.component
    const { container } = render(<Lane snap={mkSnap()} />)
    const matrix = container.querySelector('[data-testid="state-matrix"]')
    expect(matrix, '诊断泳道没有挂载产品状态矩阵：只被自己的测试渲染的组件等于没有交付').not.toBeNull()
    const rows = Array.from(matrix?.querySelectorAll('[data-state]') ?? [])
    expect(rows).toHaveLength(8)
    const honest = rows.filter((row) => (row.textContent ?? '').includes('快照不携带'))
    expect(honest.length,
           'no row admits which states the shipped projection cannot answer').toBeGreaterThanOrEqual(2)
  })
})
