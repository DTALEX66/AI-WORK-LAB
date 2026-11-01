// UI_VIEWS (20260921) · L10b (2026-09-27): Audit Trail lane — read-only
// projection of CI runs, executions and source refs.
//
// Structure: B10 `.panel > .table-wrap > .table` for the record table (the
// pinned anchors `work-lab-gate @ 00f45a10 · run 35545037452` and
// `EX-77 · hermes` live in the 引用 cell, verbatim), plus the B10
// `.panel > pre.mono` log surface for the source-ref log lines. B10's own audit
// page is a `<pre class="mono">`; the repo's CI-contract table is kept because
// the view tests pin it — B10 wins for structure/style, the anchor texts win for
// wording.
//
// HONEST: empty => `.empty` state, no write actions, no fabricated rows.
// Filtering is local view state only.
import * as React from 'react'
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { EmptyState } from '@/components/ui/states'
import { PageHeader } from '@/components/ui/page-header'
import type { CiRun, Execution } from '@/types'

interface AuditRow {
  key: string
  kind: 'CI' | '执行'
  ref: string
  status: string
  conclusion: string
  sourceRef: string | null
}

type Filter = 'all' | 'ci' | 'exec' | 'failed'

const FILTERS: { value: Filter; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'ci', label: 'CI 运行' },
  { value: 'exec', label: '执行' },
  { value: 'failed', label: '失败' },
]

function ciVariant(status: string, conclusion: string | null): 'success' | 'error' | 'warning' | 'muted' {
  const c = (conclusion ?? status).toLowerCase()
  if (c === 'success' || c === 'succeeded' || c === 'completed') return 'success'
  if (c === 'failure' || c === 'failed' || c === 'timed_out' || c === 'cancelled' || c === 'canceled') return 'error'
  if (c === 'pending' || c === 'in_progress' || c === 'running' || c === 'queued') return 'warning'
  return 'muted'
}

function execVariant(state: string): 'success' | 'error' | 'warning' | 'muted' {
  switch (state) {
    case 'COMPLETED': return 'success'
    case 'FAILED': return 'error'
    case 'RUNNING':
    case 'STARTING':
    case 'WAITING_USER':
    case 'WAITING_APPROVAL': return 'warning'
    default: return 'muted'
  }
}

export function AuditTrailView({ snap }: { snap: any }) {
  const ci: CiRun[] = Array.isArray(snap?.ci) ? snap.ci : []
  const executions: Execution[] = Array.isArray(snap?.executions) ? snap.executions : []
  const sourceRefs: string[] = Array.isArray(snap?.sourceRefs) ? snap.sourceRefs : []

  const [filter, setFilter] = React.useState<Filter>('all')

  const rows: AuditRow[] = React.useMemo(() => {
    const out: AuditRow[] = [
      ...ci.map((r, i) => ({
        key: `ci-${i}`,
        kind: 'CI' as const,
        ref: `${r.workflow ?? 'CI'} @ ${(r.headSha || 'UNKNOWN').slice(0, 8)}${r.runId ? ` · run ${r.runId}` : ''}`,
        status: r.status ?? 'UNKNOWN',
        conclusion: r.conclusion ?? 'UNKNOWN',
        sourceRef: r.sourceRef,
      })),
      ...executions.map((e) => ({
        key: `ex-${e.executionId}`,
        kind: '执行' as const,
        ref: `${e.executionId}${e.agent ? ` · ${e.agent}` : ''}`,
        status: e.state,
        conclusion: e.stateQuality,
        sourceRef: e.sourceRef,
      })),
    ]
    // stable sort: CI first (by runId, then ref), then executions (by id)
    out.sort((a, b) =>
      a.kind === b.kind ? a.ref.localeCompare(b.ref) : a.kind === 'CI' ? -1 : 1,
    )
    return out
  }, [ci, executions])

  const visible = rows.filter((r) => {
    if (filter === 'ci') return r.kind === 'CI'
    if (filter === 'exec') return r.kind === '执行'
    if (filter === 'failed') {
      const c = r.conclusion.toLowerCase()
      return c === 'failure' || c === 'failed' || c === 'timed_out'
    }
    return true
  })

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Audit Trail / 审计追踪"
        description="CI 运行、执行记录与来源引用的纯只读投影：可筛选，但不提供重试 / 撤销 / 重放操作。数据全部来自后端（ci[] / executions[] / sourceRefs），缺失即 UNKNOWN。"
      />

      <div className="toolbar">
        <div className="seg" role="group" aria-label="按类型筛选">
          {FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              aria-pressed={filter === f.value}
              className={filter === f.value ? 'active' : undefined}
              onClick={() => setFilter(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
        <span className="ml-auto self-center text-[12px] text-muted">{visible.length} 条记录</span>
      </div>

      <Card>
        <h3>审计追踪（只读）</h3>
        <CardContent>
          {visible.length === 0 ? (
            ci.length === 0 && executions.length === 0 ? (
              <EmptyState
                title="无审计记录"
                description="当前快照未携带 CI 运行或执行记录。Observer 保持 UNKNOWN，不伪造历史。"
              />
            ) : (
              <div className="py-6 text-center text-xs text-muted">该筛选条件下无记录</div>
            )
          ) : (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>类型</th>
                    <th>引用</th>
                    <th>状态</th>
                    <th>结论</th>
                    <th>来源引用</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.map((r) => (
                    <tr key={r.key}>
                      <td className="text-muted">{r.kind}</td>
                      <td className="font-mono">{r.ref}</td>
                      <td>
                        <Badge variant={r.kind === 'CI' ? ciVariant(r.status, r.conclusion) : execVariant(r.status)}>
                          {r.status}
                        </Badge>
                      </td>
                      <td>{r.conclusion}</td>
                      <td className="break-all font-mono text-muted">
                        {r.sourceRef ?? '—'}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <h3>来源引用（{sourceRefs.length}）</h3>
        <CardContent>
          {sourceRefs.length === 0 ? (
            <div className="py-4 text-center text-xs text-muted">无来源引用</div>
          ) : (
            <div className="mono text-[12px] text-muted">
              <ul className="m-0 flex list-none flex-col gap-1 p-0">
                {sourceRefs.map((s, i) => (
                  <li key={i} className="truncate">{s}</li>
                ))}
              </ul>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <h3>原则</h3>
        <CardContent className="text-xs text-muted">
          审计追踪为纯只读视图：可筛选，但不提供任何重试 / 撤销 / 重放操作按钮。
          数据全部来自后端投影（ci[] / executions[] / sourceRefs），缺失即 UNKNOWN。
        </CardContent>
      </Card>
    </div>
  )
}
