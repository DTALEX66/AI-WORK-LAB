// UI_VIEWS (20260921) · L10b (2026-09-27): Task Packs lane — projects the REAL
// task-family counts (snap.tasks) and, when present, the plan's task list
// (snap.workspace.plan.tasks), with the verbatim B10 `.panel` + `.metric-row`
// (4 metric boxes) + `.table` structure.
// Honest discipline: counts are shown only when the backend carried them; an
// empty tasks map renders the B10 `.empty` state, never a fabricated
// "N task packs running".
import { Card, CardContent } from '@/components/ui/card'
import { EmptyState } from '@/components/ui/states'
import { PageHeader } from '@/components/ui/page-header'
import { StatusPill } from '@/components/ui/status'

export function TaskPacksView({ snap }: { snap: any }) {
  const tasks: Record<string, number> = snap?.tasks ?? {}
  const planTasks: { taskId?: string; [k: string]: unknown }[] | undefined =
    snap?.workspace?.plan?.tasks && Array.isArray(snap.workspace.plan.tasks)
      ? snap.workspace.plan.tasks
      : undefined
  const total = Object.values(tasks).reduce((a, b) => a + (b || 0), 0)
  const hasCounts = Object.keys(tasks).length > 0

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Task Packs / 任务包"
        description="任务家族计数（snap.tasks）与计划任务明细（workspace.plan.tasks）的真实投影。缺失即 UNKNOWN，不伪造任务包运行态，不新增任务操作入口。"
      />

      <Card>
        <div className="mb-3.5 flex items-center justify-between gap-3">
          <h3 className="m-0">任务包 · 家族计数（真实投影）</h3>
          {hasCounts ? <StatusPill variant="info">合计 {total} 项</StatusPill> : <StatusPill variant="muted">无计数数据</StatusPill>}
        </div>
        <CardContent>
          {!hasCounts ? (
            <EmptyState
              title="无任务包计数"
              description="当前快照未携带 tasks 家族计数（snap.tasks 为空）。Observer 保持 UNKNOWN，不伪造任务包状态。"
            />
          ) : (
            <div className="metric-row">
              {Object.entries(tasks).map(([family, count]) => (
                <div key={family} className="metric-box">
                  <div className="muted text-[12px]">{family}</div>
                  <div className="big-number mt-1">{count}</div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <h3>计划任务明细</h3>
        <CardContent>
          {planTasks && planTasks.length > 0 ? (
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>任务 ID</th>
                    <th>属性</th>
                  </tr>
                </thead>
                <tbody>
                  {planTasks.map((t, i) => {
                    const props = Object.entries(t).filter(([k]) => k !== 'taskId')
                    return (
                      <tr key={i}>
                        <td className="font-mono text-secondary-ink">{t.taskId ?? `task-${i + 1}`}</td>
                        <td className="text-muted">
                          {props.length ? props.map(([k, v]) => `${k}=${String(v)}`).join(' · ') : '—'}
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <div className="py-4 text-center text-xs text-muted">
              当前快照未携带计划任务明细（workspace.plan.tasks 缺失）。
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <h3>原则</h3>
        <CardContent className="text-xs text-muted">
          任务包计数来自后端真实投影（snap.tasks / workspace.plan.tasks）。
          缺失即 UNKNOWN，不伪造任务包运行态，不新增任务操作入口。
        </CardContent>
      </Card>
    </div>
  )
}
