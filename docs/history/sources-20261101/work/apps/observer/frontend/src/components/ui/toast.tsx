import * as React from 'react'
import { cn } from '@/lib/utils'
import { useEnterTransition } from '@/lib/useEnterTransition'

/** The skin's own `.toast{transition:.22s ease}` plus a frame of margin. A toast currently leaves by being
 *  removed from the list, so this is the budget an exit animation would have; it is declared next to the
 *  enter flip rather than duplicated in a timer somewhere else. */
export const TOAST_EXIT_MS = 240

/**
 * UI_COMPONENTS (20260921) · L10b (2026-09-27): Toast — B10 `.toast` contract.
 *
 * B10 single-file: `<div class="toast" id="toast">Done</div>` styled as a fixed
 * bottom-right panel that fades/lifts in with `.show` and auto-hides after
 * 1800ms (showToast → clearTimeout → remove `.show`). `.toast` / `.toast.show`
 * are B10-verbatim in src/skins/b10.css (right/bottom 18px, min 220px, primary
 * border, --shadow-soft, translateY(12px) scale(.98) → 0/1).
 *
 * The repo keeps a small stack (the original M3 contract) — this renders the
 * newest toast as the B10 `.toast.show` element and any additional items as the
 * same B10 element in its shown state, so the visual contract stays identical
 * while nothing is swallowed. Default lifetime is 1800ms (B10), overridable.
 *
 * Usage (imperative, no context dependency):
 *   const { toast, Toaster } = useToaster(1800)
 *   toast({ title: '暂无新的通知' })
 *   ... <Toaster />
 */
export type ToastVariant = 'success' | 'error' | 'info'

export interface ToastItem {
  id: number
  title: string
  description?: string
  variant?: ToastVariant
  /** Set by `dismiss` for the length of the skin's own fade-out; the row drops `.show` while this is true
   *  so the declared `transition:.22s ease` runs before the element leaves the document. */
  leaving?: boolean
}

export interface ToasterProps {
  toasts: ToastItem[]
  onDismiss: (id: number) => void
}

const VARIANT_TAG: Record<ToastVariant, string> = {
  success: 'tag ok',
  error: 'tag bad',
  info: 'tag info',
}

export function Toaster({ toasts, onDismiss }: ToasterProps) {
  if (toasts.length === 0) return null
  return (
    <div className="toast-stack">
      {toasts.map((t) => (
        <ToastRow key={t.id} toast={t} onDismiss={onDismiss} />
      ))}
    </div>
  )
}

/**
 * One toast, painted closed first so the skin's `.toast{opacity:0;transform:translateY(12px) …}` to
 * `.toast.show` transition actually runs. The row owns the flip because the stack is a list: a single
 * component-level flag would show every toast the moment the first one arrived.
 */
function ToastRow({ toast: t, onDismiss }: { toast: ToastItem; onDismiss: (id: number) => void }) {
  const { mounted, shown } = useEnterTransition(!t.leaving, TOAST_EXIT_MS)
  if (!mounted) return null
  return (
    <div
      className={cn('toast', shown && 'show')}
      // M-4: an error is not a status update. `role="status` is a polite
      // live region that assistive tech may not announce urgently, and a
      // failure that disappears on its own leaves the user with no record
      // of what went wrong. Errors announce assertively and stay until
      // dismissed.
      role={t.variant === 'error' ? 'alert' : 'status'}
      aria-live={t.variant === 'error' ? 'assertive' : 'polite'}
      onClick={() => onDismiss(t.id)}
    >
      <div className="flex items-start gap-3">
        <span className={cn(VARIANT_TAG[t.variant ?? 'info'], 'shrink-0')}>
          {t.variant === 'success' ? 'OK' : t.variant === 'error' ? 'ERR' : 'INFO'}
        </span>
        <div className="min-w-0 flex-1">
          <p className="m-0 text-sm font-medium text-ink">{t.title}</p>
          {t.description ? <p className="m-0 mt-1 text-xs text-muted">{t.description}</p> : null}
        </div>
      </div>
    </div>
  )
}

let seq = 0

export function useToaster(defaultMs = 1800) {
  const [toasts, setToasts] = React.useState<ToastItem[]>([])

  const dismiss = React.useCallback((id: number) => {
    // Mark it leaving first: removing the item from the list in the same tick would unmount the element
    // before the browser ever painted a frame without `.show`, and a transition needs two painted states.
    // The removal timer is the component's own budget, so it also runs when the skin turns transitions off.
    setToasts((prev) => prev.map((t) => (t.id === id ? { ...t, leaving: true } : t)))
    window.setTimeout(() => {
      setToasts((prev) => prev.filter((t) => t.id !== id))
    }, TOAST_EXIT_MS)
  }, [])

  const toast = React.useCallback(
    (input: { title: string; description?: string; variant?: ToastVariant; ms?: number }) => {
      const id = ++seq
      setToasts((prev) => [...prev.slice(-2), { id, ...input }])
      // An error survives the timer unless the caller sets an explicit ms.
      const ttl = input.ms ?? (input.variant === 'error' ? 0 : defaultMs)
      if (ttl > 0) {
        window.setTimeout(() => dismiss(id), ttl)
      }
      return id
    },
    [defaultMs, dismiss],
  )

  return { toasts, toast, dismiss, Toaster }
}
