import * as React from 'react'

/**
 * M-3 (UI-CHECK-20261006): a `role="dialog"` with `aria-modal="true"` promises
 * keyboard users that Tab cannot leave the dialog. Declaring it without trapping
 * is worse than not declaring it — the announcement is a lie, and the user tabs
 * into the UI behind the overlay without seeing it.
 *
 * Used by Modal, Drawer and CommandPalette: focus moves to the first control
 * inside on open, Tab/Shift+Tab cycle within it, and the element that had focus
 * before opening gets focus back on close.
 *
 * Visibility is judged by computed `visibility` and by `aria-hidden`/`hidden`,
 * NOT by `offsetParent`: jsdom performs no layout, so an offsetParent filter
 * would silently return an empty list in every test and the trap would look
 * correct while never having been exercised.
 */
const FOCUSABLE = [
  'a[href]',
  'button:not([disabled])',
  'input:not([disabled])',
  'select:not([disabled])',
  'textarea:not([disabled])',
  '[tabindex]:not([tabindex="-1"])',
].join(',')

function isReachable(el: HTMLElement): boolean {
  if (el.hasAttribute('disabled')) return false
  if (el.getAttribute('aria-hidden') === 'true') return false
  if (el.closest('[hidden], [aria-hidden="true"]')) return false
  try {
    return window.getComputedStyle(el).visibility !== 'hidden'
  } catch {
    return true
  }
}

function tabbables(container: HTMLElement): HTMLElement[] {
  return Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE)).filter(
    (el) => el !== container && isReachable(el),
  )
}

export function useFocusTrap(
  open: boolean,
  containerRef: React.RefObject<HTMLElement | null>,
): void {
  const returnFocusRef = React.useRef<HTMLElement | null>(null)

  React.useEffect(() => {
    const container = containerRef.current
    if (!open || !container) return

    returnFocusRef.current = document.activeElement as HTMLElement | null

    const items = tabbables(container)
    if (items.length) {
      items[0].focus()
    } else {
      // Nothing to receive focus (an information-only panel): the dialog itself
      // becomes the tab stop so Esc and screen-reader context still land inside.
      if (!container.hasAttribute('tabindex')) container.setAttribute('tabindex', '-1')
      container.focus()
    }

    const onKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return
      const list = tabbables(container)
      if (!list.length) {
        e.preventDefault()
        return
      }
      const first = list[0]
      const last = list[list.length - 1]
      const active = document.activeElement as HTMLElement | null
      if (!active || !container.contains(active)) {
        e.preventDefault()
        ;(e.shiftKey ? last : first).focus()
      } else if (e.shiftKey && (active === first || active === container)) {
        e.preventDefault()
        last.focus()
      } else if (!e.shiftKey && active === last) {
        e.preventDefault()
        first.focus()
      }
    }

    container.addEventListener('keydown', onKeyDown)
    return () => {
      container.removeEventListener('keydown', onKeyDown)
      returnFocusRef.current?.focus?.()
      returnFocusRef.current = null
    }
  }, [open, containerRef])
}
