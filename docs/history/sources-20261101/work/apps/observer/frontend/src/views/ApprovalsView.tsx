// UI_VIEWS (20260921) · L10b (2026-09-27): Approvals lane — the backend
// snapshot has NO approvals[] array. The only real approval data that can exist
// today is snap.workspace.plan.approvals (when the plan carries it).
//
// L10b keeps the B10 `.panel > .table-wrap > .table` shape (the request / risk /
// submitter / status columns) but renders it strictly READ-ONLY: the B10 demo's
// 审批 action column is deliberately absent, because Observer is a pure
// projection and must never expose 批准 / 拒绝 / 撤销. Everything the snapshot
// does not carry stays UNKNOWN.
import { Card, CardContent } from '@/components/ui/card'
import { Badge } from '@/components/ui/badge'
import { UnknownState, PermissionState } from '@/components/ui/states'
import { PageHeader } from '@/components/ui/page-header'

function approvalVariant(state: string | undefined): 'success' | 'warning' | 'error' | 'muted' {
  const s = (state ?? '').toLowerCase()
  if (s === 'approved' || s === 'granted') return 'success'
  if (s === 'pending' || s === 'requested' || s === 'in_review') return 'warning'
  if (s === 'denied' || s === 'revoked' || s === 'rejected') return 'error'
  return 'muted'
}

function riskOf(a: { risk?: unknown; state?: string }): { text: string; variant: 'error' | 'warning' | 'muted' } {
  const raw = typeof a.risk === 'string' ? a.risk.toLowerCase() : ''
  if (raw === 'high' || raw === 'critical') return { text: '高风险', variant: 'error' }
  if (raw === 'medium' || raw === 'moderate') return { text: '中风险', variant: 'warning' }
  if (raw === 'low') return { text: '低风险', variant: 'muted' }
  return { text: 'UNKNOWN', variant: 'muted' }
}

export function ApprovalsView({ snap }: { snap: any }) {
  const plan = snap?.workspace?.plan
  const approvals: { state?: string; [k: string]: unknown }[] | undefined =
    plan?.approvals && Array.isArray(plan.approvals) ? plan.approvals : undefined

  return (
    <div className="flex flex-col gap-4">
      <PageHeader
        title="Approval Center / 审批中心"
        description="审批真值来自后端审批契约（workspace.plan.approvals）。本视图只读：不渲染批准 / 拒绝 / 撤销按钮，不构成第二个审批 Authority；缺失即 UNKNOWN，不伪造已审批状态。"
      />
      <Card>
        <div className="mb-3.5 flex items-center justify-between gap-3">
          <h3 className="m-0">审批中心（只读投影）</h3>
          <span className="text-[12px] text-muted">
            {approvals?.length ? `${approvals.length} 项审批记录` : '无审批数据'}
          </span>
        </div>
        <CardContent>
          {approvals && approvals.length > 0 ? (
            <>
            <div className="table-wrap">
              <table className="table">
                <thead>
                  <tr>
                    <th>请求</th>
                    <th>风险</th>
                    <th>状态</th>
                  </tr>
                </thead>
                <tbody>
                  {approvals.map((a, i) => {
                    const risk = riskOf(a)
                    return (
                      <tr key={i}>
                        <td>
                          <strong className="font-mono">
                            {String(a.taskId ?? a.id ?? `approval-${i + 1}`)}
                          </strong>
                          {a.reason ? <span className="ml-2 text-muted">{String(a.reason)}</span> : null}
                        </td>
                        <td><Badge variant={risk.variant}>{risk.text}</Badge></td>
                        <td>
                          <Badge variant={approvalVariant(a.state)}>
                            {a.state ?? 'UNKNOWN'}
                          </Badge>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
            {/* G1: rows exist, so the reader must be told where the decision
                lives rather than finding a table with no action column. */}
            <PermissionState
              blocked="本视图不提供批准 / 拒绝 / 撤销"
              reason="裁决由后端审批契约与 Permission Gate 持有，Observer 不构成第二个审批 Authority"
              stillAvailable="每一行的请求、风险与真实状态仍可完整阅读"
            />
            </>
          ) : (
            <UnknownState
              title="审批数据未知"
              description="当前快照未携带审批契约（无 approvals[] 数组）。审批数据将由后续审批契约投影至本页面；Observer 保持 UNKNOWN，不伪造已审批状态，也不提供审批操作。"
            />
          )}
        </CardContent>
      </Card>
      <Card>
        <h3>原则</h3>
        <CardContent className="text-xs text-muted">
          审批真值来自后端审批契约（workspace.plan.approvals）。本视图只读：
          不渲染批准 / 拒绝 / 撤销按钮，不构成第二个审批 Authority。
        </CardContent>
      </Card>
    </div>
  )
}
