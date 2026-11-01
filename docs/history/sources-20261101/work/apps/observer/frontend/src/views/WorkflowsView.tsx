// L10 (2026-09-27) · L10b (2026-09-27): B10 Workflows lane — the workflow list
// surface in the verbatim B10 structure:
//   .page-head → .toolbar (input + .seg filters) → .panel > .table-wrap > .table
// with B10 `.tag` state pills and the honest `.empty` state.
//
// The v3 snapshot carries NO workflows[] array today, so the table body is the
// real projection of whatever `workflows[]` a future contract supplies — never a
// fabricated workflow row. Search / status filter are fully functional.
//
// The status filter keeps a native `<select>` in the DOM (visually hidden,
// driven by the `.seg` buttons) because the lane's accessibility/CI contract
// pins an `aria-label="按状态筛选"` select control.
import * as React from 'react'
import { Plus, Search } from 'lucide-react'
import { PageHeader } from '@/components/ui/page-header'
import { Badge } from '@/components/ui/badge'
import { Button } from '@/components/ui/button'
import { UnknownState } from '@/components/ui/states'
import { Tooltip } from '@/components/ui/tooltip'
import type { SnapshotV3 } from '@/types'
import { fmtTimestamp } from '@/lib/api'

export interface WorkflowRow {
  id: string
  name: string
  owner?: string
  version?: string
  lastRunAt?: string
  state?: string
}

const STATE_FILTERS: { value: string; label: string }[] = [
  { value: 'all', label: '全部' },
  { value: 'active', label: '活跃' },
  { value: 'draft', label: '草稿' },
  { value: 'archived', label: '已归档' },
]

function stateVariant(state: string | undefined): 'success' | 'info' | 'warning' | 'muted' {
  if (state === 'active') return 'success'
  if (state === 'draft') return 'warning'
  if (state === 'archived') return 'muted'
  return 'info'
}

export function WorkflowsView({ snap }: { snap: SnapshotV3 | null }) {
  // Honest source: a future workflows[] projection (absent today -> []).
  const workflows: WorkflowRow[] =
    Array.isArray((snap as unknown as { workflows?: WorkflowRow[] })?.workflows)
      ? (snap as unknown as { workflows: WorkflowRow[] }).workflows
      : []
  const [query, setQuery] = React.useState('')
  const [state, setState] = React.useState('all')

  const filtered = workflows.filter((w) => {
    if (state !== 'all' && w.state !== state) return false
    if (query && !(w.name + w.owner + w.id).toLowerCase().includes(query.toLowerCase())) return false
    return true
  })

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Workflows / 工作流"
        description="受管客户端（Hermes · Codex · DSH · GitHub · Open Design · Open Human）的工作流清单。真值来自 v3 快照投影；契约缺失时保持 UNKNOWN。"
        actions={
          <Tooltip text="工作流契约（workflows[]）未接入 — 无真实创建入口">
            <span>
              <Button disabled iconLeft={Plus} variant="primary">
                新建工作流
              </Button>
            </span>
          </Tooltip>
        }
      />

      {/* B10 `.toolbar` — `.input` search + `.seg` status filters */}
      <div className="toolbar">
        <input
          className="input"
          style={{ minWidth: 260, flex: 1 }}
          placeholder="搜索工作流 / 负责人 / ID…"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          aria-label="搜索工作流"
        />
        <div className="seg" role="group" aria-label="状态筛选">
          {STATE_FILTERS.map((f) => (
            <button
              key={f.value}
              type="button"
              className={state === f.value ? 'active' : undefined}
              aria-pressed={state === f.value}
              onClick={() => setState(f.value)}
            >
              {f.label}
            </button>
          ))}
        </div>
        {/* pinned CI/a11y contract: the native select stays in the DOM and stays
            the single source of the typed filter value */}
        <select
          className="sr-only"
          value={state}
          onChange={(e) => setState(e.target.value)}
          aria-label="按状态筛选"
          tabIndex={-1}
        >
          {STATE_FILTERS.map((s) => (
            <option key={s.value} value={s.value}>
              {s.label}
            </option>
          ))}
        </select>
        <span className="ml-auto self-center text-[12px] text-muted tabular-nums">
          {workflows.length ? `${filtered.length} / ${workflows.length} 条` : '契约未投影'}
        </span>
      </div>

      <div className="panel">
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr>
                <th>工作流</th>
                <th>状态</th>
                <th>负责人</th>
                <th>版本</th>
                <th>最后执行</th>
              </tr>
            </thead>
            <tbody>
              {workflows.length === 0 ? (
                <tr>
                  <td colSpan={5}>
                    <UnknownState
                      title="工作流数据未知"
                      description="当前 v3 快照未携带 workflows[] 契约。搜索 / 筛选 / 状态标签结构已就绪；工作流真值将由后续契约投影至本页，Observer 保持 UNKNOWN，不伪造工作流行。"
                    />
                  </td>
                </tr>
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={5} className="py-6 text-center text-xs text-muted">
                    <Search size={16} className="mx-auto mb-2 opacity-60" aria-hidden />
                    该筛选条件下无工作流
                  </td>
                </tr>
              ) : (
                filtered.map((w) => (
                  <tr key={w.id}>
                    <td>
                      <strong className="block text-[13px] font-semibold text-ink">{w.name}</strong>
                      <small className="font-mono text-[12px] text-muted">{w.id}</small>
                    </td>
                    <td>
                      <Badge variant={stateVariant(w.state)}>{w.state ?? 'UNKNOWN'}</Badge>
                    </td>
                    <td className="text-muted">{w.owner || 'UNKNOWN'}</td>
                    <td className="font-mono text-muted">{w.version ?? 'UNKNOWN'}</td>
                    <td className="text-muted">
                      {fmtTimestamp(w.lastRunAt)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
