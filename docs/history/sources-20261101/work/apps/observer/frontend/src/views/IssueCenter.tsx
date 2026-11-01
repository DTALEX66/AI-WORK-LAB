// CL-07 · the problem centre, mounted on the existing 项目监控 page.
//
// Three statements this panel must never fold into one:
//   * `snap.issues` absent  -> no source answered; the state is UNKNOWN and no count is invented;
//   * `snap.issues` empty WITH `issuesSummary.complete === true` -> every source was read, nothing is wrong;
//   * `snap.issues` empty without a complete scope report -> the scan was cut short, so "no issues" is not
//     a claim this page is allowed to make.
//
// The copy action writes the exact `handoffText` the sidecar rendered from the same projection the CLI
// uses. It never sends, executes or approves anything: after a successful copy the material still reads
// 未发送, and there is no dispatch control on this surface.
import * as React from 'react'
import { Badge } from '@/components/ui/badge'
import { EmptyState, UnknownState } from '@/components/ui/states'
import { fmtTimestamp, repairPacksEndpoint } from '@/lib/api'
import {
  makeHttpRepairPackReader, packForProject, writeClipboardText,
  type ManualRepairPack, type RepairPackReader, type RepairPacksView,
} from '@/lib/repairPack'
import type { IssueRecord, SnapshotV3 } from '@/types'

export interface IssueCenterProps {
  snap: SnapshotV3 | null
  /** Injected by tests; the page derives the real reader from the loopback descriptor. */
  reader?: RepairPackReader
  endpoint?: string | null
}

const CLASS_LABELS: Record<string, { label: string; impact: string }> = {
  SOURCE_CIRCUIT_OPEN: { label: '来源熔断', impact: '该来源的采集被熔断，新的证据没有进来。' },
  SOURCE_REFUSAL: { label: '来源拒绝', impact: '来源拒绝了本次读取，事实可能不完整。' },
  SOURCE_FAILURE: { label: '来源失败', impact: '来源读取失败，事实可能不完整。' },
  SOURCE_DATA_DROPPED: { label: '数据被丢弃', impact: '部分记录没有进入投影。' },
  SOURCE_STALE: { label: '来源过期', impact: '读数可能已不是当前状态。' },
  SOURCE_INCOMPLETE_COVERAGE: { label: '覆盖不完整', impact: '部分采集器没有作答。' },
  EXECUTION_STALLED: { label: '执行停滞', impact: '执行长时间没有进展。' },
  EXECUTION_CONFLICT: { label: '执行冲突', impact: '多个执行占用了同一工作区。' },
  TASK_BLOCKED: { label: '任务受阻', impact: '任务处于 BLOCKED，无法继续。' },
  TASK_FAILED: { label: '任务失败', impact: '任务以 FAILED 结束。' },
}

const PRIORITY_VARIANT: Record<string, 'error' | 'warning' | 'muted'> = {
  P1: 'error', P2: 'warning', P3: 'muted',
}

function classText(issue: IssueRecord): { label: string; impact: string } {
  return CLASS_LABELS[issue.class] || {
    label: issue.class,
    impact: '未登记的问题类：只按原始字段阅读，不推断影响。',
  }
}

function attributionText(issue: IssueRecord): string {
  if (issue.softwareId) {
    return issue.softwareVersion
      ? `${issue.softwareId} @ ${issue.softwareVersion}`
      : `${issue.softwareId}（版本 UNKNOWN）`
  }
  switch (issue.softwareVersionSource) {
    case 'source-names-no-software': return '来源没有命名软件'
    case 'identity-source-absent': return '身份源缺席（归属 UNKNOWN）'
    case 'unmatched': return '未匹配到已登记软件'
    case 'ambiguous': return '归属有歧义（多个软件命中）'
    case 'not-discovered': return '未发现版本（归属 UNKNOWN）'
    default: return '归属 UNKNOWN'
  }
}

function nextStepText(issue: IssueRecord): string {
  return issue.projectId
    ? '准备交接材料，复制给你选择的外部工具；WORK-LAB 不发送、不执行。'
    : '先确认项目归属；没有归属的问题不能生成交接包。'
}

function scopeLine(snap: SnapshotV3): string {
  const summary = snap.issuesSummary
  if (!summary) return '问题列表没有来源范围报告（issuesSummary 缺席）— 无法判断是否漏读。'
  const pieces = [
    `已读来源 ${summary.sourcesRead}`,
    `未作答来源 ${summary.sourcesAbsent}`,
    `扫描行 ${summary.rowsScanned}`,
  ]
  const priority = summary.priorityCounts || {}
  pieces.push(`P1 ${priority.P1 ?? 0} / P2 ${priority.P2 ?? 0} / P3 ${priority.P3 ?? 0}`)
  if (summary.truncated) pieces.push(`列表已截断（上限 ${summary.cap}，省略 ${summary.omittedCount}）`)
  const scanTruncated = Object.values(summary.scanTruncated || {}).some(Boolean)
  if (scanTruncated) pieces.push('扫描被截断：未出现的指纹不能读成已修复')
  if (summary.complete === true) pieces.push('覆盖完整')
  return pieces.join(' · ')
}

type Preview =
  | { kind: 'idle' }
  | { kind: 'loading'; projectId: string }
  | { kind: 'view'; projectId: string; view: RepairPacksView }
  | { kind: 'failure'; projectId: string; detail: string }

export function IssueCenter({ snap, reader, endpoint }: IssueCenterProps) {
  const [preview, setPreview] = React.useState<Preview>({ kind: 'idle' })
  const [copyState, setCopyState] = React.useState<{ ok: boolean; message: string } | null>(null)
  const [showAll, setShowAll] = React.useState(false)
  // `alive` gates the awaited continuations of `loadProject` and `copyPack`, which live in `useCallback`
  // bodies, so it cannot be an effect-local closure. StrictMode runs setup -> cleanup -> setup on one
  // mount and the ref survives it: an effect that only ever un-armed the flag left a LIVE component
  // reading `false`, so the preview hung on 正在读取投影… and the copy confirmation was swallowed.
  // Re-arm on every setup. Pinned by `issueCenterStrictMode.contract.test.tsx`.
  const alive = React.useRef(true)
  const activeRead = React.useRef<AbortController | null>(null)

  React.useEffect(() => {
    alive.current = true
    return () => {
      alive.current = false
      activeRead.current?.abort()
    }
  }, [])

  // The page derives the endpoint from the same loopback descriptor the snapshot uses. Tests inject a
  // reader, so no test ever needs a live sidecar; `endpoint: null` is the honest "no trusted endpoint".
  const derivedEndpoint = React.useMemo(() => {
    if (endpoint === undefined) return repairPacksEndpoint()
    return endpoint ? { url: endpoint, authoritative: false } : null
  }, [endpoint])
  const activeReader = React.useMemo(
    () => reader ?? (derivedEndpoint ? makeHttpRepairPackReader(derivedEndpoint.url) : null),
    [reader, derivedEndpoint],
  )

  const issues = snap?.issues
  const summary = snap?.issuesSummary

  const loadProject = React.useCallback(async (projectId: string) => {
    if (!activeReader) {
      setPreview({ kind: 'failure', projectId, detail: '交接材料端点不可用：需要环回 sidecar 提供的只读端点。' })
      return
    }
    activeRead.current?.abort()
    const controller = new AbortController()
    activeRead.current = controller
    setCopyState(null)
    setPreview({ kind: 'loading', projectId })
    const outcome = await activeReader(controller.signal)
    if (!alive.current || controller.signal.aborted) return
    if (outcome.kind === 'RESULT') setPreview({ kind: 'view', projectId, view: outcome.view })
    else if (outcome.kind === 'BAD_PAYLOAD') {
      setPreview({ kind: 'failure', projectId, detail: `交接材料响应不可读：${outcome.why}` })
    } else {
      setPreview({ kind: 'failure', projectId, detail: `无法读取交接材料：${outcome.detail}` })
    }
  }, [activeReader])

  const copyPack = React.useCallback(async (pack: ManualRepairPack) => {
    const result = await writeClipboardText(pack.handoffText)
    if (!alive.current) return
    setCopyState(result.ok
      ? { ok: true, message: `已复制到剪贴板（仍未发送、未执行）：${pack.target.projectId}` }
      : { ok: false, message: `${result.why}；请在下方文本中手动复制。` })
  }, [])

  if (!snap) {
    return (
      <div className="panel p-4" data-testid="issue-center">
        <h3 className="mb-3">问题与交接</h3>
        <UnknownState
          title="问题状态 UNKNOWN"
          description="数据源未接入：没有快照，就不能说没有问题，也不显示 0 个问题。"
        />
      </div>
    )
  }

  if (issues === undefined) {
    return (
      <div className="panel p-4" data-testid="issue-center">
        <h3 className="mb-3">问题与交接</h3>
        <UnknownState
          title="问题投影缺席（无来源作答）"
          description={summary
            ? 'issuesSummary 已到达但问题列表缺席 — 投影不完整，保持 UNKNOWN，不补 0。'
            : '问题列表缺席 = 没有来源作答。这与「读完了，没有问题」是两种不同的状态。'}
        />
      </div>
    )
  }

  if (issues.length === 0) {
    const complete = summary?.complete === true
    const incomplete = !!summary && (
      summary.truncated
      || summary.sourcesAbsent > 0
      || Object.values(summary.scanTruncated || {}).some(Boolean)
    )
    return (
      <div className="panel p-4" data-testid="issue-center">
        <h3 className="mb-3">问题与交接</h3>
        {complete && !incomplete ? (
          <EmptyState
            title="所有来源已读，未发现问题"
            description={scopeLine(snap)}
          />
        ) : (
          <UnknownState
            title="列表为空，但不能读成无问题"
            description={summary
              ? `扫描不完整或报告未声明覆盖完整 — 保持 UNKNOWN。${scopeLine(snap)}`
              : '问题列表为空，但 issuesSummary 缺席：没有范围报告就不能声称全部来源已读。'}
          />
        )}
      </div>
    )
  }

  const visible = showAll ? issues : issues.slice(0, 6)
  const active = preview.kind === 'idle' ? null : preview
  const view = active && active.kind === 'view' ? active.view : null
  const pack = active && active.kind === 'view' ? packForProject(active.view, active.projectId) : null
  const relevantRefusals = active && active.kind === 'view'
    ? (active.view.summary?.refusals || []).filter((r) => !r.projectId || r.projectId === active.projectId)
    : []

  return (
    <div className="panel p-4" data-testid="issue-center">
      <div className="mb-3 flex flex-wrap items-baseline justify-between gap-2">
        <h3 className="m-0">问题与交接</h3>
        <span className="text-[12px] text-muted">
          {`共 ${issues.length} 个问题`}
        </span>
      </div>
      <div className="mb-3 text-[12px] text-muted" data-testid="issue-scope">
        {scopeLine(snap)}
      </div>
      {summary?.truncated ? (
        <div className="mb-3 text-[12px] text-muted" data-testid="issue-truncated">
          当前列表被截断：不要把它读成「其余问题不存在」。
        </div>
      ) : null}

      <div className="list">
        {visible.map((issue) => {
          const cls = classText(issue)
          const canHandoff = !!issue.projectId
          return (
            <div key={issue.fingerprint} className="list-item" data-testid="issue-row">
              <div className="min-w-0">
                <strong className="block truncate text-[13px] font-semibold text-ink">
                  {cls.label} · {issue.subject || issue.evidenceRef}
                </strong>
                <div className="mt-1 text-[12px] text-muted">
                  <span>影响（按问题类）：{cls.impact}</span>
                </div>
                {issue.detail ? (
                  <div className="mt-1 text-[12px] text-muted">详情：{issue.detail}</div>
                ) : null}
                <div className="mt-1 text-[12px] text-muted">
                  软件：{attributionText(issue)} · 更新：{fmtTimestamp(issue.lastSeenAt ?? null)}
                  {' · '}重复 {issue.occurrences} 次
                </div>
                <div className="mt-1 break-all font-mono text-[12px] text-muted">
                  证据：{issue.evidenceRef}
                  {issue.safeToReread === false ? '（不可安全重读）' : ''}
                </div>
                <div className="mt-1 text-[12px] text-muted">下一步：{nextStepText(issue)}</div>
              </div>
              <div className="flex shrink-0 flex-col items-end gap-2">
                <Badge variant={PRIORITY_VARIANT[issue.priority] || 'muted'}>{issue.priority}</Badge>
                {canHandoff ? (
                  <button
                    type="button"
                    className="ghost-btn"
                    onClick={() => { void loadProject(String(issue.projectId)) }}
                    data-testid="issue-handoff-button"
                  >
                    准备交接材料
                  </button>
                ) : null}
              </div>
            </div>
          )
        })}
      </div>

      {issues.length > visible.length || showAll ? (
        <div className="mt-3">
          <button type="button" className="ghost-btn" onClick={() => setShowAll((v) => !v)}>
            {showAll ? '收起' : `展开全部 ${issues.length} 条`}
          </button>
        </div>
      ) : null}

      {active ? (
        <div className="mt-4 border-t border-line pt-4" data-testid="handoff-preview">
          <h4 className="mb-2">交接材料预览</h4>
          {active.kind === 'loading' ? (
            <p className="text-[12px] text-muted">正在读取投影…</p>
          ) : null}
          {active.kind === 'failure' ? (
            <p className="text-[12px] text-ink" role="alert">{active.detail}</p>
          ) : null}
          {view ? (
            <>
              {view.status === 'SOURCE_ABSENT' ? (
                <p className="text-[12px] text-ink" data-testid="handoff-empty">
                  问题投影缺席：没有来源作答，不能生成交接材料。
                </p>
              ) : null}
              {view.status === 'NO_OPEN_ISSUES' ? (
                <p className="text-[12px] text-ink" data-testid="handoff-empty">
                  已读取问题投影：当前没有待交接的问题。
                </p>
              ) : null}
              {!pack && (view.status === 'NO_PACK' || view.status === 'OK') ? (
                <p className="text-[12px] text-ink" data-testid="handoff-refused">
                  该项目没有可交接的包
                  {relevantRefusals.length
                    ? `：${relevantRefusals.map((r) => r.reason).join('、')}`
                    : '（summary 未列出原因）'}
                </p>
              ) : null}
              {pack ? (
                <div data-testid="handoff-pack">
                  <div className="text-[12px] text-muted">
                    项目：{pack.target.projectName || pack.target.projectId}
                    {' · '}包：<span className="font-mono">{pack.packId}</span>
                    {' · '}状态：<Badge variant={pack.status === 'BLOCKED' ? 'warning' : 'info'}>{pack.status}</Badge>
                  </div>
                  <div className="mt-1 text-[12px] text-muted">
                    绑定问题 {pack.binds.issueCount} 条 · 证据引用 {pack.binds.evidenceRefs.length} 条
                    {pack.binds.unattributedCount ? ` · 其中无归属 ${pack.binds.unattributedCount} 条` : ''}
                  </div>
                  <div className="mt-1 text-[12px] text-muted">
                    {pack.verification.known
                      ? `验证方法：${pack.verification.command}`
                      : '验证命令未识别：包为 BLOCKED，复制后仍需你确认核验方法。'}
                  </div>
                  {pack.readiness.reasons.length ? (
                    <div className="mt-1 text-[12px] text-muted">
                      待确认：{pack.readiness.reasons.join('、')}
                    </div>
                  ) : null}
                  <div className="mt-2 text-[12px] text-ink" data-testid="handoff-draft-state">
                    草稿：未发送、未执行。复制不等于发送；WORK-LAB 不会替你发送或执行。
                  </div>
                  <div className="mt-2 flex flex-wrap items-center gap-2">
                    <button type="button" className="ghost-btn" onClick={() => { void copyPack(pack) }}>
                      复制交接材料
                    </button>
                    {copyState ? (
                      <span
                        className="text-[12px] text-ink"
                        role={copyState.ok ? 'status' : 'alert'}
                        data-testid="copy-state"
                      >
                        {copyState.message}
                      </span>
                    ) : null}
                  </div>
                  <details className="mt-3">
                    <summary className="cursor-pointer text-[12px] text-muted">查看完整交接文本</summary>
                    <pre className="mt-2 max-h-80 overflow-auto whitespace-pre-wrap break-words text-[12px] text-ink">
                      {pack.handoffText}
                    </pre>
                  </details>
                </div>
              ) : null}
            </>
          ) : null}
        </div>
      ) : null}
    </div>
  )
}
