import { Badge } from '@/components/ui/badge'
import type { AgentRow } from '@/lib/api'
import { stateTone, fmtTokens, fmtCostQuality } from '@/lib/api'

const STATE_TEXT: Record<string, string> = {
  RUNNING: '运行中', STARTING: '启动中', WAITING_USER: '待用户', WAITING_APPROVAL: '待审批',
  BLOCKED: '受阻', COMPLETED: '完成', FAILED: '失败', UNKNOWN: '未知',
}

function tone(row: AgentRow): 'success' | 'warning' | 'error' | 'muted' {
  const t = stateTone(row.state)
  if (t === 'running') return 'success'
  if (t === 'pending' || t === 'blocked') return 'warning'
  if (t === 'failed') return 'error'
  return 'muted'
}

/**
 * U07 · L10b: B10 `panel > table-wrap > table.table` — the real v3
 * `executions[]` joined with their anchor project (platform + token truth).
 * No fabricated cost/usage percentages — costQuality is the backend label,
 * null tokens render UNKNOWN. `.panel` supplies the 18px surface, `.table` the
 * 12px/10px cells, muted header and hover row tint (all B10-verbatim).
 */
export function ExecutionTable({ rows, hasData }: { rows: AgentRow[]; hasData: boolean }) {
  return (
    <div className="panel">
      <h3>执行</h3>
      <div className="mb-3 text-[12px] text-muted">{hasData ? rows.length + ' 条 · 真实' : '等待数据'}</div>
      <div className="table-wrap">
        {rows.length === 0 ? (
          <div className="empty py-10">
            <div className="icon" aria-hidden="true">◎</div>
            <p className="m-0 text-sm font-semibold text-ink">
              {hasData ? '暂无执行记录（UNKNOWN）' : '数据源未接入'}
            </p>
            <p className="mx-auto mt-1 max-w-md text-xs">保持 UNKNOWN — 不伪造执行行</p>
          </div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>执行</th>
                <th>状态</th>
                <th>平台</th>
                <th>项目</th>
                <th>Token</th>
              </tr>
            </thead>
            <tbody>
              {rows.slice(0, 20).map((a) => (
                <tr key={a.id}>
                  <td>
                    <strong className="block text-[12px] font-semibold text-ink">{a.name || a.id}</strong>
                    <small className="font-mono text-[12px] text-muted">{a.id}</small>
                  </td>
                  <td>
                    <Badge variant={tone(a)}>{STATE_TEXT[a.state] || a.state}</Badge>
                  </td>
                  <td className="text-muted">{a.platform || 'UNKNOWN'}</td>
                  <td>{a.anchorProjectId || 'UNKNOWN'}</td>
                  <td className="tabular-nums" title="成本质量（后端权威）">
                    {fmtTokens(a.totalTokens)} <span className="text-[12px] text-muted">{fmtCostQuality(a.costQuality)}</span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  )
}
