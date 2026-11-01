import { cn } from '@/lib/utils'

/**
 * L10 (2026-09-27) · L10b: B10 `.panel.kpi` card — the verbatim B10 structure:
 *
 *   <div class="panel kpi">
 *     <strong>12</strong>      ← 35px primary number (B10 `.kpi strong`)
 *     <small>运行中工作流</small> ← muted label (B10 `.kpi small`)
 *     <div class="trend up">↑ 18%</div>
 *   </div>
 *
 * `.panel`, `.kpi strong`, `.kpi small`, `.kpi .trend.up|.warn` are B10-verbatim
 * in src/skins/b10.css. The repo contract adds the `.kpi-number` hook on the
 * number element (App.behavior pins `.kpi-number` values) — it is kept on the
 * `<strong>` so both contracts hold at once.
 *
 * Truth discipline (U07): the value is the caller's truth. The caller passes
 * 'UNKNOWN' when there is no data; a KPI must never render a fabricated 0. The
 * trend line is only rendered when the caller supplies a REAL trend — an
 * unknown KPI shows no trend at all rather than an invented percentage.
 */
export function KPICard({
  title,
  value,
  sub,
  trend,
  trendTone = 'up',
}: {
  title: string
  value: string
  sub?: string
  /** real trend label (e.g. '↑ 18%'); omitted when the value is UNKNOWN */
  trend?: string
  trendTone?: 'up' | 'warn'
}) {
  return (
    <div className="panel kpi">
      <strong className="kpi-number">{value}</strong>
      <small>{title}</small>
      {sub ? <small className="mt-1 block text-[12px]">{sub}</small> : null}
      {trend ? <div className={cn('trend', trendTone)}>{trend}</div> : null}
    </div>
  )
}
