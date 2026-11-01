import * as React from 'react'
import { Badge, type BadgeVariant } from './badge'
import { cn } from '@/lib/utils'

/**
 * UI_COMPONENTS (20260921): Tag = status pill built on the existing Badge
 * contract (L4: status colors success/warning/error/info + neutral).
 * Adds an optional dot indicator for KPI/status surfaces.
 */
export type TagVariant = BadgeVariant | 'neutral'

const tagVariantMap: Record<TagVariant, BadgeVariant> = {
  success: 'success',
  warning: 'warning',
  error: 'error',
  info: 'info',
  muted: 'muted',
  neutral: 'muted',
}

const dotColor: Record<TagVariant, string> = {
  success: 'bg-success',
  warning: 'bg-warning',
  error: 'bg-error',
  info: 'bg-info',
  muted: 'bg-zinc-400',
  neutral: 'bg-zinc-400',
}

export interface TagProps extends React.HTMLAttributes<HTMLSpanElement> {
  variant?: TagVariant
  /** show a leading status dot */
  dot?: boolean
}

export function Tag({ variant = 'neutral', dot = false, className, children, ...props }: TagProps) {
  const v = tagVariantMap[variant]
  return (
    <Badge variant={v} className={cn('uppercase tracking-wide', className)} {...props}>
      {dot ? <span className={cn('h-1.5 w-1.5 rounded-full', dotColor[variant])} aria-hidden="true" /> : null}
      {children}
    </Badge>
  )
}
