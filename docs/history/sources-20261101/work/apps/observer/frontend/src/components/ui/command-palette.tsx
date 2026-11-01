import * as React from 'react'
import { cn } from '@/lib/utils'
// WUI-14: the same composition guard the shell shortcut uses, so one rule cannot be honoured in one
// handler and forgotten in the other.
import { isImeComposing } from '@/lib/keyGuards'

/**
 * UI_COMPONENTS (20260921) · L10b (2026-09-27): CommandPalette — L6 keyboard
 * authority (Ctrl/Cmd+K opens, Esc closes, arrow keys navigate, Enter runs the
 * item, case-insensitive `includes` filter).
 *
 * L10b: the panel is the verbatim B10 `.palette` structure —
 *   <div class="palette">
 *     <input placeholder="搜索页面、命令或模块…">
 *     <div class="item"><span>label</span><small>group</small></div> × N
 *   </div>
 * `.palette` / `.palette input` / `.palette .item` are B10-verbatim in
 * src/skins/b10.css (fixed at 11vh, min(820px,96vw), 20px radius, primary
 * border, show via `.open`). The repo behavior contract is preserved: the panel
 * stays MOUNTED with role=dialog + aria-modal so `getByRole('textbox')` and
 * Escape/Enter keep working, and the item buttons keep `aria-current` for the
 * active row. A transparent click-catcher sits behind the panel so
 * click-outside-to-close still works without adding a B10 backdrop (B10 has
 * none).
 */
export interface PaletteItem {
  id: string
  label: string
  icon?: React.ComponentType<{ className?: string }>
  group?: string
  run: () => void
}

export interface CommandPaletteProps {
  open: boolean
  onClose: () => void
  items: PaletteItem[]
  placeholder?: string
  /** optional heading shown above the list */
  title?: string
}

/** Exported so a contract test can drive the filter the overlay actually uses. A copy of this predicate
 *  in a test file would pass while the real search went blind. */
export function filterItems(items: PaletteItem[], query: string): PaletteItem[] {
  const q = query.trim().toLowerCase()
  if (!q) return items
  return items.filter(
    (it) => it.label.toLowerCase().includes(q) || (it.group ?? '').toLowerCase().includes(q),
  )
}

export function CommandPalette({
  open,
  onClose,
  items,
  placeholder = '搜索页面 / 命令 / 资源…',
  title,
}: CommandPaletteProps) {
  const [query, setQuery] = React.useState('')
  const [active, setActive] = React.useState(0)
  const inputRef = React.useRef<HTMLInputElement>(null)
  const dialogRef = React.useRef<HTMLDivElement>(null)
  const openerRef = React.useRef<HTMLElement | null>(null)

  const visible = React.useMemo(() => filterItems(items, query), [items, query])

  // reset + focus on open, and hand focus BACK on close. Opening from the top
  // bar's search field or from Ctrl/Cmd+K left focus inside a dialog that no
  // longer exists, so the next Tab restarted at the top of the document.
  React.useEffect(() => {
    if (open) {
      openerRef.current = document.activeElement as HTMLElement | null
      setQuery('')
      setActive(0)
      inputRef.current?.focus()
    } else {
      const returnTo = openerRef.current
      openerRef.current = null
      if (returnTo && document.contains(returnTo)) returnTo.focus()
    }
  }, [open])

  const runItem = (idx: number) => {
    const it = visible[idx]
    if (!it) return
    it.run()
    onClose()
  }

  const onKeyDown = (e: React.KeyboardEvent) => {
    // WUI-14: a candidate-confirming Enter from an input method must not run the highlighted command.
    if (isImeComposing(e)) return
    if (e.key === 'Escape') {
      e.preventDefault()
      onClose()
    } else if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((a) => Math.min(a + 1, visible.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((a) => Math.max(a - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      runItem(active)
    }
  }

  return (
    <>
      {open && (
        <div
          className="fixed inset-0"
          style={{ zIndex: 94, background: 'transparent' }}
          aria-hidden="true"
          onClick={onClose}
        />
      )}
      <div
        ref={dialogRef}
        role="dialog"
        aria-modal="true"
        aria-label={title ?? '命令面板'}
        className={cn('palette', open && 'open')}
        onKeyDown={onKeyDown}
      >
        {/* L10b: the B10 `.palette` is shown/hidden by `.open`. The panel stays
            mounted (the repo pins role=dialog + a queryable textbox), but its
            CONTENT is only built while open — otherwise a closed palette would
            duplicate every nav label into the document and break the shell's
            text queries. */}
        {open ? (
          <>
            <input
              ref={inputRef}
              value={query}
              onChange={(e) => {
                setQuery(e.target.value)
                setActive(0)
              }}
              placeholder={placeholder}
              aria-label={placeholder}
            />
            <div aria-label="命令列表">
              {visible.length === 0 ? (
                <div className="item"><span>没有匹配结果</span></div>
              ) : (
                visible.map((it, i) => {
                  const activeNow = i === active
                  return (
                    <button
                      key={it.id}
                      type="button"
                      onMouseEnter={() => setActive(i)}
                      onClick={() => runItem(i)}
                      className={cn('item w-full text-left', activeNow && 'active')}
                      style={activeNow ? { background: 'color-mix(in srgb, var(--primary) 15%, transparent)' } : undefined}
                      aria-current={activeNow ? 'true' : undefined}
                    >
                      <span className="truncate">{it.label}</span>
                      {it.group ? <small className="shrink-0 text-[12px] uppercase tracking-wide text-muted">{it.group}</small> : null}
                    </button>
                  )
                })
              )}
            </div>
          </>
        ) : null}
      </div>
    </>
  )
}
