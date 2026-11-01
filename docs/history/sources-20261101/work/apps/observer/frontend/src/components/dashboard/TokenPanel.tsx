import { Progress } from '@/components/ui/progress'
import type { SnapshotV3 } from '@/types'
import { fmtTokens, fmtCostQuality, tokenTruth } from '@/lib/api'

/**
 * U07 · L10b: token panel reading the REAL v3 `tokenSummary` (the only
 * token+quality truth), rendered with the B10 `.panel` + `.list-item` rows and
 * the B10 `.progress` bar. No fabricated cost line, no quota, no FX. Nulls
 * render UNKNOWN.
 */
export function TokenPanel({ snap }: { snap: SnapshotV3 | null }) {
  const tt = tokenTruth(snap)
  const inT = tt?.inputTokens ?? null
  const outT = tt?.outputTokens ?? null
  const total = tt?.totalTokens ?? null
  const max = Math.max(inT ?? 0, outT ?? 0, 1)
  // B5: a progress bar needs a REAL source. The value text is always shown
  // honestly (fmtTokens(null) -> UNKNOWN, never "0"); the bar is only drawn
  // when at least one real token figure exists. No token data -> no fabricated
  // 0% bar, just the UNKNOWN values + the real state.
  const hasToken = inT != null || outT != null || total != null
  const rows = [
    { label: '输入', value: inT },
    { label: '输出', value: outT },
  ]
  return (
    <div className="panel">
      <h3>Token</h3>
      <div className="mb-3 text-[12px] text-muted">质量 {fmtCostQuality(tt?.costQuality)}</div>
      <div className="list">
        {rows.map((d) => (
          <div key={d.label} className="list-item flex-col items-stretch gap-2">
            <div className="flex items-center justify-between">
              <span className="text-muted">{d.label}</span>
              <span className="tabular-nums text-ink">{fmtTokens(d.value)}</span>
            </div>
            {hasToken ? <Progress value={max ? ((d.value ?? 0) / max) * 100 : 0} /> : null}
          </div>
        ))}
        <div className="list-item">
          <span className="text-muted">总计</span>
          <span className="tabular-nums text-ink">{fmtTokens(total)}</span>
        </div>
      </div>
      {!hasToken && (
        <p className="mt-3 text-[12px] text-muted">
          无 token 数据{snap ? ' · 快照已接入但 token 未知' : ' · 数据源未接入'}（不估算、不伪造 0%）
        </p>
      )}
      <p className="mt-2 text-[12px] text-muted">成本质量（EXACT/ESTIMATED/UNKNOWN）由后端投影，前端不估算金额、汇率或配额。</p>
    </div>
  )
}
