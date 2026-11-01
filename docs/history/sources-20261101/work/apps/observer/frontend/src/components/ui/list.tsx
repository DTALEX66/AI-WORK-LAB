// L10 (2026-09-27) · L10b: B04 `.list` / `.list-item` + Timeline variant —
// dense read-only rows with hover lift (L6 120ms).
//
// L10b: the row is the verbatim B10 structure
//   <div class="list-item">
//     <div><strong>title</strong><small>sub</small></div>
//     <span class="tag …">state</span>
//   </div>
// `.list-item` supplies surface2 fill, 14px radius, 13/14px padding and the
// hover lift; `small` is muted (B10 `.list-item small`). The optional leading
// mono column is an observer-side extension (timeline / execution id) and keeps
// the same font-mono muted treatment.
import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'
import type { BadgeVariant } from './badge'
import { StatusPill } from './status'

export interface ListItem {
  title: ReactNode
  /** muted secondary line */
  sub?: ReactNode
  /** right-side state pill */
  state?: { text: string; variant?: BadgeVariant }
  /** optional leading mono column (timeline time / execution id) */
  leading?: ReactNode
}

export function ListView({ items, className }: { items: ListItem[]; className?: string }) {
  return (
    <div className={cn('list', className)}>
      {items.map((it, i) => (
        <div key={i} className="list-item">
          <div className="flex min-w-0 items-center gap-3">
            {it.leading ? (
              <span className="shrink-0 font-mono text-[12px] text-muted tabular-nums">{it.leading}</span>
            ) : null}
            <div className="min-w-0">
              <strong className="block truncate text-[13px] font-semibold text-ink">{it.title}</strong>
              {it.sub != null ? <small className="truncate">{it.sub}</small> : null}
            </div>
          </div>
          {it.state ? <StatusPill variant={it.state.variant ?? 'muted'}>{it.state.text}</StatusPill> : null}
        </div>
      ))}
    </div>
  )
}

export function Timeline({ items, className }: { items: ListItem[]; className?: string }) {
  return (
    <div className={cn('relative flex flex-col gap-2.5 pl-4', className)}>
      <div className="absolute left-1 top-2 bottom-2 w-px bg-border/60" aria-hidden="true" />
      {items.map((it, i) => (
        <div key={i} className="relative">
          <span className="absolute -left-[13px] top-1/2 h-2 w-2 -translate-y-1/2 rounded-full bg-primary shadow-[0_0_8px_var(--glow-primary)]" aria-hidden="true" />
          <ListView items={[it]} className="px-2" />
        </div>
      ))}
    </div>
  )
}
