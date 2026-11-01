import * as React from 'react'
import { cn } from '@/lib/utils'
import { useFocusTrap } from '@/lib/useFocusTrap'

/**
 * UI_COMPONENTS (20260921) · L10b (2026-09-27): Modal — L6 interaction
 * authority: Esc closes, focus moves into the dialog on open and returns to the
 * trigger on close, aria-modal + role=dialog.
 *
 * L10b: the DOM is the verbatim B10 overlay structure —
 *   <div class="overlay open" role="dialog" aria-modal="true" aria-label=…>
 *     <div class="modal">
 *       <h3>title</h3>
 *       <div class="body">…children…</div>
 *       <div class="actions">…footer (B10 default: 取消 + 确认)…</div>
 *     </div>
 *   </div>
 * `.overlay` (fixed, blur backdrop, show via `.open`) / `.modal` (min(760px,96vw),
 * 22px radius, primary border, --shadow) / `.modal .body` / `.modal .actions`
 * are B10-verbatim in src/skins/b10.css. Keeping role=dialog on the `.overlay`
 * element preserves `getByRole('dialog')` + `aria-modal` + `aria-label`
 * exactly as the component test pins them.
 */
export interface ModalProps {
  open: boolean
  onClose: () => void
  title: string
  children: React.ReactNode
  footer?: React.ReactNode
  /** extra classes for the panel (width etc.) */
  className?: string
}

export function Modal({ open, onClose, title, children, footer, className }: ModalProps) {
  const overlayRef = React.useRef<HTMLDivElement>(null)
  const panelRef = React.useRef<HTMLDivElement>(null)

  React.useEffect(() => {
    if (!open) return
    const onKey = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose()
    }
    document.addEventListener('keydown', onKey)
    return () => document.removeEventListener('keydown', onKey)
  }, [open, onClose])

  // M-3: focus enters the dialog, stays inside it, and returns to the trigger.
  useFocusTrap(open, overlayRef)

  // L10b: B10 shows/hides the overlay with `.open`, but the repo's component
  // contract pins "closed Modal renders nothing" — so the overlay is only
  // mounted while open (the `.overlay`/`.open` classes are still applied so the
  // B10 fixed/blurred backdrop + `.modal` panel are exactly the B10 elements).
  if (!open) return null

  return (
    <div
      ref={overlayRef}
      role="dialog"
      aria-modal="true"
      aria-label={title}
      className={cn('overlay', open && 'open')}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose()
      }}
    >
      <div ref={panelRef} tabIndex={-1} className={cn('modal focus:outline-none', className)}>
        <h3>{title}</h3>
        <div className="body">{children}</div>
        {footer ? <div className="actions">{footer}</div> : null}
      </div>
    </div>
  )
}
