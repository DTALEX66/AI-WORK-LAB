import { Badge } from '@/components/ui/badge'
import type { SnapshotV3 } from '@/types'
import { fmtTokens, fmtCostQuality, activityTone } from '@/lib/api'

/**
 * U07 · L10b: per-project panel reading the REAL v3 `projects[]` projection,
 * rendered with the B10 `.panel` + `.list` / `.list-item` structure.
 * activityState is real (ACTIVE/REGISTERED/IDLE/UNKNOWN); git dirty is the real
 * counter; token/costQuality is the backend label (no fabricated cost).
 */
export function ProjectPanel({ snap }: { snap: SnapshotV3 | null }) {
  const projects = snap?.projects || []
  return (
    <div className="panel">
      <h3>项目</h3>
      <div className="mb-3 text-[12px] text-muted">{snap ? projects.length + ' 个 · 真实' : '等待数据'}</div>
      {projects.length === 0 ? (
        <div className="empty py-10">
          <div className="icon" aria-hidden="true">◇</div>
          <p className="m-0 text-sm font-semibold text-ink">{snap ? 'registry 为空（UNKNOWN）' : '数据源未接入'}</p>
          <p className="mx-auto mt-1 max-w-md text-xs">不伪造项目身份与活动状态</p>
        </div>
      ) : (
        <div className="list">
          {projects.slice(0, 8).map((p) => {
            const tone = activityTone(p.activityState)
            const dirty = p.git.dirtyCount
            return (
              <div key={p.projectId} className="list-item">
                <div className="min-w-0">
                  <strong className="block truncate text-[13px] font-semibold text-ink">{p.displayName || p.projectId}</strong>
                  <small className="block font-mono">
                    {p.agentPlatform || '—'} · {p.activeExecutionCount} 执行 · {fmtTokens(p.token.totalTokens)}{' '}
                    {fmtCostQuality(p.token.costQuality)}
                  </small>
                  <small className="block font-mono">
                    {p.git.branch || '—'}@{p.git.localSha ? p.git.localSha.slice(0, 7) : '—'}
                  </small>
                </div>
                <div className="flex shrink-0 flex-col items-end gap-1">
                  <Badge variant={tone === 'active' ? 'success' : 'muted'}>{p.activityState || 'UNKNOWN'}</Badge>
                  {dirty == null ? <Badge variant="muted">脏 UNKNOWN</Badge>
                    : dirty ? <Badge variant="warning">脏 {dirty}</Badge>
                    : <Badge variant="muted">干净</Badge>}
                </div>
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}
