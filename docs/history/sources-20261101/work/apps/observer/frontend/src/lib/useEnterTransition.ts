import * as React from 'react'

/**
 * Paint the closed state first, then flip to the open one a frame later, so a transition the skin already
 * declares actually runs.
 *
 * `apps/observer/frontend/src/skins/b10.css` declares `.drawer{… transition:right .28s cubic-bezier(.2,0,0,1)}`
 * with `.drawer.open{right:0}`, and `.toast{opacity:0;transform:translateY(12px) scale(.98);transition:.22s ease}`
 * with `.toast.show{…}`. Mounting the element with the open class already applied — which is what both
 * components did — gives the browser nothing to change between two painted states, so the promised slide
 * never happens and the operator sees the panel appear at its destination.
 *
 * Two frames, not one: the first frame paints the closed state, the second changes it. A single
 * `requestAnimationFrame` can coalesce the initial paint and the change into the same frame, which is the
 * difference between a transition and a jump cut.
 *
 * `exitMs` unmounts the element only after the closing transition has had time to run, and it is bounded by
 * a timer rather than by `transitionend`: `apps/observer/frontend/src/skins/l10b-shell.css` turns
 * transitions off under `prefers-reduced-motion`, and an event that never fires would strand the overlay in
 * the document forever.
 */
export function useEnterTransition(active: boolean, exitMs: number): { mounted: boolean; shown: boolean } {
  const [mounted, setMounted] = React.useState(active)
  const [shown, setShown] = React.useState(false)

  React.useEffect(() => {
    if (active) {
      setMounted(true)
      let inner = 0
      const outer = requestAnimationFrame(() => {
        inner = requestAnimationFrame(() => setShown(true))
      })
      return () => {
        cancelAnimationFrame(outer)
        if (inner) cancelAnimationFrame(inner)
      }
    }
    setShown(false)
    const timer = setTimeout(() => setMounted(false), exitMs)
    return () => clearTimeout(timer)
  }, [active, exitMs])

  return { mounted, shown }
}
