import { useEffect, useLayoutEffect, useRef, useState } from 'react'

/**
 * The action row's overflow收纳 (UI debt #34).
 *
 * `.top-actions` used to be `flex-wrap: wrap`, so on a narrow window the four controls stacked into a
 * vertical column — measured at 430px the row had 76px of usable width and the buttons simply piled up.
 * That satisfies no published pattern: Fluent's CommandBar keeps a "see more" button and moves primary
 * commands into the secondary area when space runs out, and Carbon's OverflowMenu is the named control
 * for "more options exist but space is constrained". A wrapping column is neither, and it also breaks
 * SCREEN_SPEC's one-row band contract.
 *
 * So the row measures its own children and folds the unpinned tail into a real menu: `aria-expanded` on
 * the trigger, `role="menu"`/`role="menuitem"`, Escape dismisses and returns focus to the trigger, and a
 * click outside closes it. Pinned controls stay visible whatever happens — the theme toggle is how a
 * user gets out of a theme that stops making sense, so it must never be the thing that disappears.
 */

export type ActionDef = {
  key: string
  label: string
  title?: string
  ariaLabel?: string
  /** Optional because the caller's own handlers are optional; a missing one renders an inert control
   *  rather than being papered over with a synthetic no-op. */
  run?: () => void
  /** Kept in the row at every width. */
  pinned?: boolean
}

/** The trigger's own footprint plus the gap before it, so folding leaves room for itself. */
const MORE_FOOTPRINT = 64

/**
 * Ask the band, not the row.
 *
 * `.top-actions` is `flex: 0 1 auto`, so the band shrinks it to whatever is left (measured 204px at a
 * 1400px window while its four controls need 296px). Measuring `row.clientWidth` therefore asks
 * "how wide did you end up?" after the fold already narrowed the row — a hysteresis loop where one
 * control folds, the row gets narrower, and the next fold is justified by the space the first fold
 * took away. The row can never widen back, and it folds at desktop widths where the band had room.
 *
 * So the probe forces the row to its intrinsic width for one layout pass and reads whether the band
 * overflows as a result. That is the question the fold exists to answer.
 */
function bandOverflow(row: HTMLElement): { overflow: number; bar: HTMLElement } | null {
  const bar = row.parentElement
  if (!bar) return null
  const previousRow = row.style.flex
  const previousWrap = bar.style.flexWrap
  // The band is `flex-wrap: wrap`, so an over-full band wraps onto a second row instead of reporting
  // horizontal overflow — which is the exact "second row of controls floating with no boundary" the
  // owner reported. Probe the single-line case the fold exists to prevent, then restore.
  row.style.flex = '0 0 auto'
  bar.style.flexWrap = 'nowrap'
  const scrollWidth = (bar as HTMLElement).scrollWidth
  const clientWidth = (bar as HTMLElement).clientWidth
  row.style.flex = previousRow
  bar.style.flexWrap = previousWrap
  return { overflow: scrollWidth - clientWidth, bar }
}

export function ActionRow({ actions }: { actions: ActionDef[] }) {
  const rowRef = useRef<HTMLDivElement | null>(null)
  const sizerRef = useRef<HTMLDivElement | null>(null)
  const triggerRef = useRef<HTMLButtonElement | null>(null)
  const menuRef = useRef<HTMLDivElement | null>(null)
  const [visibleCount, setVisibleCount] = useState(actions.length)
  const [open, setOpen] = useState(false)

  useLayoutEffect(() => {
    const row = rowRef.current
    const sizer = sizerRef.current
    if (!row || !sizer) return
    // No ResizeObserver, or a container that reports no width, means there is no layout to reason
    // about — a jsdom mount, or a first paint before the shell has sized itself. Folding on
    // `available = 0` would hide every control from an accessibility tree that a test (and a screen
    // reader) legitimately expects to contain them, so an unmeasurable row shows everything.
    if (typeof ResizeObserver === 'undefined') {
      setVisibleCount(actions.length)
      return
    }

    const measure = () => {
      if (!row.clientWidth) {
        setVisibleCount(actions.length)
        return
      }
      const probe = bandOverflow(row)
      if (!probe || probe.overflow <= 1) {
        setVisibleCount(actions.length)
        return
      }
      const widths = Array.from(sizer.children).map((child) => (child as HTMLElement).offsetWidth)
      // Read the row's own gap instead of restating it: b10 declares `.top-actions{gap:10px}`, and a
      // hardcoded 8 here would silently mis-price every fold if the skin ever changed it.
      const gap = parseFloat(getComputedStyle(row).columnGap || getComputedStyle(row).gap || '0') || 0
      const foldable = actions.filter((action) => !action.pinned)
      // The last sizer child is the ellipsis probe: the first fold trades a control for the trigger,
      // so it saves less than its own width. Later folds save the whole control.
      const triggerCost = (widths[widths.length - 1] ?? MORE_FOOTPRINT) + gap
      let saved = 0
      let folded = 0
      for (let index = foldable.length - 1; index >= 0 && saved < probe.overflow; index -= 1) {
        const width = widths[actions.indexOf(foldable[index])] + gap
        saved += width - (folded === 0 ? triggerCost : 0)
        folded += 1
      }
      setVisibleCount(actions.length - folded)
    }

    measure()
    const observer = new ResizeObserver(measure)
    observer.observe(row)
    return () => observer.disconnect()
  }, [actions])

  useEffect(() => {
    if (!open) return
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        setOpen(false)
        triggerRef.current?.focus()
      }
    }
    const onPointerDown = (event: MouseEvent) => {
      const target = event.target as Node | null
      if (target && !menuRef.current?.contains(target) && target !== triggerRef.current) setOpen(false)
    }
    document.addEventListener('keydown', onKey)
    document.addEventListener('mousedown', onPointerDown)
    return () => {
      document.removeEventListener('keydown', onKey)
      document.removeEventListener('mousedown', onPointerDown)
    }
  }, [open])

  const shown = actions.slice(0, visibleCount)
  const folded = actions.slice(visibleCount)

  return (
    <div className="top-actions top-actions-fit" ref={rowRef}>
      {shown.map((action) => (
        <ActionButton key={action.key} action={action} />
      ))}
      {folded.length > 0 && (
        <div className="action-overflow" ref={menuRef}>
          <button
            type="button"
            className="ghost-btn action-more"
            ref={triggerRef}
            aria-expanded={open}
            aria-haspopup="menu"
            aria-label="更多操作"
            title="更多操作"
            onClick={() => setOpen((value) => !value)}
          >
            …
          </button>
          {open && (
            <div className="action-overflow-menu" role="menu">
              {folded.map((action) => (
                <button
                  key={action.key}
                  type="button"
                  role="menuitem"
                  className="action-overflow-item"
                  title={action.title ?? action.label}
                  onClick={() => {
                    setOpen(false)
                    action.run?.()
                  }}
                >
                  {action.label}
                </button>
              ))}
            </div>
          )}
        </div>
      )}
      {/* Off-screen sizer: real text, real font, real padding, so the widths above are the widths the
          row will actually need rather than a constant someone guessed. */}
      <div className="action-sizer" aria-hidden="true" ref={sizerRef}>
        {actions.map((action) => (
          <button key={action.key} type="button" className="ghost-btn" tabIndex={-1}>
            {action.label}
          </button>
        ))}
        <button type="button" className="ghost-btn" tabIndex={-1}>
          …
        </button>
      </div>
    </div>
  )
}

function ActionButton({ action }: { action: ActionDef }) {
  return (
    <button
      type="button"
      className="ghost-btn"
      onClick={action.run}
      title={action.title ?? action.label}
      aria-label={action.ariaLabel}
    >
      {action.label}
    </button>
  )
}
