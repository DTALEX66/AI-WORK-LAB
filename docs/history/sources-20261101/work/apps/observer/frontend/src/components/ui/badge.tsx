import * as React from 'react'
import { cn } from '@/lib/utils'

/**
 * UI_COMPONENTS (20260921) · L10b (2026-09-27): Badge → B10 `.tag`.
 *
 * B10 `.tag` (verbatim in src/skins/b10.css):
 *   .tag        inline-flex, 999px radius, 5/9 padding, 12px bold, white
 *   .tag.ok     gradient #27c86a → #11a74d
 *   .tag.warn   gradient #f2b541 → #c98c00
 *   .tag.bad    gradient #f86b6b → #cb3e3e
 *   .tag.info   gradient --primary → --secondary
 * A neutral/muted badge has no B10 modifier — it renders the bare `.tag`
 * contract layered with the repo's muted surface utilities.
 */
export type BadgeVariant = 'success' | 'warning' | 'error' | 'info' | 'muted'

const variants: Record<BadgeVariant, string> = {
  success: 'tag ok',
  warning: 'tag warn',
  error: 'tag bad',
  info: 'tag info',
  muted: 'tag bg-panel2 text-muted border border-border/60',
}

export function Badge({ variant = 'muted', className, children, ...props }: React.HTMLAttributes<HTMLSpanElement> & { variant?: BadgeVariant }) {
  return (
    <span className={cn(variants[variant], className)} {...props}>
      {children}
    </span>
  )
}
