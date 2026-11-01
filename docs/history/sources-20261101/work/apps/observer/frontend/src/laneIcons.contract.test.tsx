// WUI-03 gap 10: the per-lane icon set stops being data nobody renders.
//
// `apps/observer/frontend/src/lib/viewRegistry.ts` has declared one Lucide component per lane since long
// before this test existed, and the rail painted 31 identical `.nav-dot` circles instead — a field with zero
// consumers reads as delivered in every source-level grep and as absent on the screen. These cases bind the
// painted row to the registry row, keep the lane's NAME on screen (the first attempt at this gap hid the
// labels and produced 23 indistinguishable rows; `apps/observer/frontend/DESIGN.md` gap 10 records it), and
// derive their own population from the registry so the assertions cannot run over an empty list.
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import type { LucideIcon } from 'lucide-react'
import { createElement } from 'react'
import { Sidebar } from '@/components/layout/Sidebar'
import { VIEW_REGISTRY, OVERVIEW_ID, OVERVIEW_ICON } from '@/lib/viewRegistry'
import { NAV_GROUPS, isOnDefaultNav } from '@/lib/navigation'

function railRows() {
  const { container } = render(<Sidebar activeView={OVERVIEW_ID} onSelect={() => {}} />)
  return Array.from(container.querySelectorAll<HTMLElement>('nav.nav button[data-lane]'))
}

function onNavLanesWithComponents() {
  const ids = NAV_GROUPS.flatMap((group) => group.ids).filter(isOnDefaultNav)
  const byId = new Map(VIEW_REGISTRY.map((e) => [e.id, e]))
  return ids.map((id) => ({ id, entry: byId.get(id) })).filter((row) => row.entry?.component)
}

// An SVG node's `className` is an SVGAnimatedString, so the comparable thing is the `class` attribute.
const classOf = (node: Element | null | undefined) => node?.getAttribute('class') ?? ''
const iconClass = (Icon: LucideIcon) => classOf(render(createElement(Icon)).container.firstElementChild)

const REGISTRY_ICON_CLASS = new Map(VIEW_REGISTRY.map((e) => [e.id, iconClass(e.icon)]))

describe("the rail paints each lane's own declared glyph", () => {
  it('the population is the rail itself, not a hand-picked sample', () => {
    const lanes = onNavLanesWithComponents()
    expect(lanes.length).toBeGreaterThanOrEqual(20)
    const rows = railRows()
    expect(rows.map((r) => r.getAttribute('data-lane'))).toHaveLength(rows.length)
    // overview is a synthetic lane with no registry row; every other rail row must be in the population
    for (const lane of lanes) expect(rows.some((r) => r.getAttribute('data-lane') === lane.id)).toBe(true)
  })

  it('every rail row carries exactly one glyph, and it is the glyph that lane declares', () => {
    for (const row of railRows()) {
      const id = row.getAttribute('data-lane') as string
      const glyphs = Array.from(row.querySelectorAll('[data-lane-icon]'))
      expect(glyphs, `lane ${id} paints no icon at all`).toHaveLength(1)
      if (id === OVERVIEW_ID) {
        expect(classOf(row.querySelector('svg'))).toBe(iconClass(OVERVIEW_ICON))
        continue
      }
      expect(glyphs[0].getAttribute('data-lane-icon')).toBe(id)
      expect(classOf(row.querySelector('svg'))).toBe(REGISTRY_ICON_CLASS.get(id))
    }
  })

  it('the dot no longer rides along, so a row cannot grow two markers', () => {
    const { container } = render(<Sidebar activeView={OVERVIEW_ID} onSelect={() => {}} />)
    expect(container.querySelector('.nav-dot')).toBeNull()
  })

  it('adding a glyph never costs a lane its name', () => {
    for (const row of railRows()) {
      const id = row.getAttribute('data-lane') as string
      const label = row.querySelector('span')?.textContent?.trim() ?? ''
      expect(label, `lane ${id} lost its visible name`).not.toBe('')
      expect(row.getAttribute('title')).toBe(label)
    }
  })

  it('the rail is exactly as distinguishing as the data it renders', () => {
    const painted = new Map(railRows().map((row) =>
      [row.getAttribute('data-lane'), classOf(row.querySelector('svg'))]))
    const declared = new Map(onNavLanesWithComponents().map((l) => [l.id, REGISTRY_ICON_CLASS.get(l.id) ?? '']))
    declared.set(OVERVIEW_ID, iconClass(OVERVIEW_ICON))
    // Row for row, the picture IS the registry. If someone gives two lanes one glyph by mistake the
    // `declared` map still says two different things, so this fails rather than agreeing by construction.
    expect(painted).toEqual(declared)
    // 31 identical markers was the defect; a population that collapsed back to a handful of glyphs is
    // caught by the same equality above, so the only extra floor here is that the population is real.
    expect(new Set(declared.values()).size).toBeGreaterThan(1)
    expect(painted.size).toBeGreaterThanOrEqual(20)
  })
})
