// L10 (2026-09-27): B10 `.progress` bar — rounded track with the
// primary->secondary gradient fill + glow. value is the caller's truth
// (0..100); `unknown` renders an honest dashed empty track, never a fake %.
import * as React from 'react'
import { cn } from '@/lib/utils'

export function Progress({
  value,
  label,
  className,
}: {
  /** 0..100; null = unknown (honest empty track) */
  value: number | null
  label?: string
  className?: string
}) {
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value))
  return (
    <div className={cn('w-full', className)}>
      {label ? (
        <div className="mb-1 flex items-center justify-between text-[12px] text-muted">
          <span>{label}</span>
          <span className="tabular-nums">{value == null ? 'UNKNOWN' : `${pct}%`}</span>
        </div>
      ) : null}
      <div
        className="h-2.5 w-full overflow-hidden rounded-full border border-border/55 bg-panel2/82"
        role="progressbar"
        aria-valuenow={value ?? undefined}
        aria-valuemin={0}
        aria-valuemax={100}
        aria-label={label ?? '进度'}
      >
        <div
          className="h-full rounded-full transition-[width] duration-base"
          style={{
            width: value == null ? '0%' : `${pct}%`,
            background: 'linear-gradient(90deg, rgb(var(--primary-rgb)), color-mix(in srgb, rgb(var(--secondary-rgb)) 45%, rgb(var(--primary-rgb))))',
            boxShadow: value == null ? 'none' : '0 0 20px color-mix(in srgb, rgb(var(--primary-rgb)) 30%, transparent)',
          }}
        />
      </div>
    </div>
  )
}
