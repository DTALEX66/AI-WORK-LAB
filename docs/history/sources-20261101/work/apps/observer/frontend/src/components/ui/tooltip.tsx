// L10 (2026-09-27): B06 hover Tooltip — pure-CSS/JS, no dependency.
// 120ms hover reveal (L6 motion-fast), z-index from the B10 token layer
// (.z-tooltip). Usage: <Tooltip text="…"><Button/></Tooltip>
//
// The keyboard half was missing until 2026-10-07: the whole reason a disabled action is disabled is
// this text, and a native `disabled` button is not focusable, so the explanation could only be reached
// with a mouse. The wrapper now takes the tab stop itself when it is hiding a disabled control, and the
// tip reveals on focus as well as hover.
import * as React from 'react'
import { cn } from '@/lib/utils'

export interface TooltipProps {
  text: string
  side?: 'top' | 'bottom'
  children: React.ReactNode
  className?: string
}

function wrapsDisabledControl(node: React.ReactNode): boolean {
  // Call sites wrap the control in a positioning span (`<Tooltip><span><Button disabled/></span>`),
  // so the disabled flag is not always on the direct child.
  let found = false
  React.Children.forEach(node, (child) => {
    if (found || !React.isValidElement(child)) return
    if ((child.props as { disabled?: unknown }).disabled === true) {
      found = true
      return
    }
    const nested = (child.props as { children?: React.ReactNode }).children
    if (nested !== undefined) found = wrapsDisabledControl(nested)
  })
  return found
}

export function Tooltip({ text, side = 'top', children, className }: TooltipProps) {
  const unreachable = wrapsDisabledControl(children)
  return (
    <span
      className={cn('group/tt relative inline-flex', className)}
      aria-label={text}
      // A hidden-but-present tab stop only when this tooltip is the sole way to read a refusal.
      tabIndex={unreachable ? 0 : undefined}
      role={unreachable ? 'note' : undefined}
    >
      {children}
      <span
        role="tooltip"
        className={cn(
          'pointer-events-none absolute left-1/2 -translate-x-1/2 z-tooltip whitespace-nowrap',
          'rounded-md border border-border bg-panel2 px-2.5 py-1.5 text-[12px] text-ink shadow-card',
          'opacity-0 transition-opacity duration-fast group-hover/tt:opacity-100',
          'group-focus-within/tt:opacity-100 group-focus/tt:opacity-100',
          side === 'top' ? 'bottom-full mb-1.5' : 'top-full mt-1.5',
        )}
      >
        {text}
      </span>
    </span>
  )
}
