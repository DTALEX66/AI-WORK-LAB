// L10 (2026-09-27) · L10b: shared B10 page header — the verbatim B10
// `.page-head` structure from the single-file:
//   <div class="page-head">
//     <div><h2>title</h2><p>description</p></div>
//     <div class="page-actions">…ghost/primary buttons…</div>
//   </div>
// `.page-head h2` = 32px (verbatim b10.css), `.page-head p` = muted, max 760px.
// Every page renders through this component; per-page actions are passed in
// (disabled/honest when the real contract is not wired yet).
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface PageHeaderProps {
  title: string
  description?: string
  /** page actions, rendered right-aligned in the B10 `.page-actions` slot */
  actions?: ReactNode
  className?: string
}

export function PageHeader({ title, description, actions, className }: PageHeaderProps) {
  return (
    <div className={cn('page-head', className)}>
      <div className="min-w-0">
        <h2>{title}</h2>
        {description ? <p>{description}</p> : null}
      </div>
      {actions ? <div className="page-actions">{actions}</div> : null}
    </div>
  )
}
