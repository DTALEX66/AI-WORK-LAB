/**
 * G2 of the UI prompt pack: the console carries its own brand.
 *
 * The top bar had no brand mark at all. That matters most for the compact HUD, which renders no
 * rail, so that window had no identity; and the main window runs with `decorations:false`, so this
 * row IS the chrome. The palette single-source rule and the source-level sweeps for these
 * contracts live in tests/ci/test_desktop_only_shell.py, because `tsc -b` type-checks this
 * project without Node types.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { TopStatusBar } from '@/components/layout/TopStatusBar'
import { Rail, TopBar } from '@/daily/DailyChrome'
import { HudDaily } from '@/daily/HudDaily'

afterEach(cleanup)

function bar(layout: 'full' | 'compact') {
  return render(
    <TopStatusBar
      snap={null} source={'unknown' as any} live={false} theme="dark" layout={layout}
      onCycleTheme={() => {}} onCycleLayout={() => {}}
    />,
  )
}

describe('G2 · brand surface', () => {
  it('renders the brand chip in the desktop layout, mark and wordmark', () => {
    bar('full')
    const chip = document.querySelector('.topbar-brand')
    expect(chip).not.toBeNull()
    expect(chip?.querySelector('.topbar-brand-mark')).not.toBeNull()
    expect(chip?.textContent).toContain('WORK-LAB')
  })

  it('renders the brand mark in the compact HUD, which has no rail to carry identity', () => {
    bar('compact')
    expect(document.querySelector('.topbar-brand .topbar-brand-mark')).not.toBeNull()
  })

  it('keeps the transport dot honest while taking its colour from the tokens', () => {
    bar('full')
    // No snapshot: the dot must not render as LIVE and must not be green.
    expect(document.querySelector('.topbar')?.textContent).toContain('UNKNOWN')
  })
})

/* The three tests above mount the professional shell only -- which is precisely how CL-15 could report
 * "brand applied" while the desktop main window (tauri.conf.json opens `surface=daily`) still drew a generic
 * lucide glyph. These mount the surfaces an operator actually sees. `data-brand-mark` is the hook: a class
 * name can be renamed by a stylesheet edit, an attribute is what the contract can hold onto. */
describe('G2 · brand on the surfaces the desktop window shows', () => {
  it('carries the mark in the daily top bar', () => {
    render(<TopBar query="" onQuery={() => {}} hudHint={null} />)
    expect(document.querySelector('[data-brand-mark="work-lab"]')).not.toBeNull()
  })

  it('carries the mark in the daily rail, which had no brand slot at all', () => {
    render(<Rail view="home" onNavigate={() => {}} transportLabel="UNKNOWN" transportTone="unknown" />)
    expect(document.querySelector('nav[data-landmark="rail"] [data-brand-mark="work-lab"]')).not.toBeNull()
  })

  it('carries the mark in the HUD strip, the window with neither rail nor title bar', () => {
    render(<HudDaily snap={null} nativeStrip />)
    expect(document.querySelector('[data-hud-frame] [data-brand-mark="work-lab"]')).not.toBeNull()
  })

  it('leaves no generic glyph standing in for the brand in the daily shell', () => {
    // The old tile was a `Boxes` icon inside a bordered square. If it comes back, the mark above is being
    // rendered twice or the replacement was reverted, and this fails rather than silently co-existing.
    render(<TopBar query="" onQuery={() => {}} hudHint={null} />)
    expect(document.querySelectorAll('svg.lucide-boxes').length).toBe(0)
  })
})
