// P1-04 · the Inspector's dimension contract.
//
// The Work lane's Inspector is the surface that answers "what does the projection actually know about this
// record?". Before this module the answer was twelve hard-coded rows that never changed with the selected
// record, so the panel could not tell a dimension the contract does not carry from a field the record
// happens to leave empty — and it stayed glued to the snapshot while the URL moved on.
//
// Three origins, never collapsed into each other:
//   PROJECTED  — the v3 snapshot carries it for THIS record, so the real value renders;
//   NULL_FIELD — the source was read and the field itself is null (a lease with no holder is a fact, and
//                rendering it as 来源缺口 would hide it, while rendering 0 would invent one);
//   SOURCE_GAP — the dimension is not in the contract at all, with the reason the gap exists.
//
// Adjacent data is shown as itself, never laundered into the task's own answer: a project-level CI run is
// labelled 项目级 and does not become a task-level verification. Binding them would need a task↔run key the
// projection does not have.
import * as React from 'react'
import type { Execution, SnapshotV3, TaskRecord } from '@/types'
import type { FocusState, RecordFocus } from '@/lib/recordFocus'
import { recordLink } from '@/lib/recordFocus'

// A single Inspector dimension. When `value` is empty we show an explicit
// source-gap marker, NOT a blank cell or a fake "0" — the prompt requires the
// gap to be visible so the user knows what is / is not wired yet.
export function Dim({ label, value, hint }: { label: string; value: React.ReactNode; hint?: string }) {
  const present = value !== null && value !== undefined && value !== '' && value !== false
  return (
    <div className="list-item flex-col items-stretch gap-1">
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{label}</div>
      {present ? (
        <div className="whitespace-pre-wrap text-[12px] text-ink">{value}</div>
      ) : (
        <div className="flex items-center gap-1.5 text-[12px] text-warning">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-secondary" aria-hidden="true" />
          来源缺口（当前 v3 快照未携带{hint ? ` · ${hint}` : ''}）
        </div>
      )}
    </div>
  )
}

export type DimensionOrigin = 'PROJECTED' | 'NULL_FIELD' | 'SOURCE_GAP'

export interface InspectorDimension {
  key: string
  label: string
  origin: DimensionOrigin
  /** the projected value — only meaningful when origin === 'PROJECTED' */
  value: string | null
  /** why the dimension is not answerable, for a gap / null field */
  note: string
}

const projected = (key: string, label: string, value: string | null, note: string): InspectorDimension =>
  value === null || value === ''
    ? { key, label, origin: 'NULL_FIELD', value: null, note }
    : { key, label, origin: 'PROJECTED', value, note: '' }

const gap = (key: string, label: string, note: string): InspectorDimension =>
  ({ key, label, origin: 'SOURCE_GAP', value: null, note })

const nullField = (key: string, label: string, note: string): InspectorDimension =>
  ({ key, label, origin: 'NULL_FIELD', value: null, note })

/** Every dimension the detail card is asked to answer, in reading order. A key that is missing from this
 *  list is a dimension the Inspector stopped being able to answer, so the tests walk this array. */
export const TASK_DIMENSION_KEYS = [
  'identity', 'project', 'status', 'lease', 'checkpoint', 'timeline',
  'goal', 'revision', 'attempt', 'planner', 'routes', 'diff', 'tests',
  'ci', 'receipts', 'approval', 'handoff', 'nextAction',
] as const

export const EXECUTION_DIMENSION_KEYS = [
  'identity', 'project', 'state', 'agent', 'session', 'area', 'sourceRef', 'timeline',
  'goal', 'revision', 'attempt', 'planner', 'routes', 'diff', 'tests',
  'ci', 'receipts', 'approval', 'handoff', 'nextAction',
] as const

const TASK_GAP_REASONS: Record<string, string> = {
  goal: '目标文本属提示词面，只读投影不带正文',
  revision: '修订与尝试由 Task Ledger 合同持有，尚未进入快照投影；快照顶层的 revision 是快照自己的修订，不是这条任务的',
  attempt: '尝试次数未投影；lease 的 fencingToken 是围栏令牌，不是尝试计数，不拿它冒充',
  planner: '计划与路由未投影',
  routes: '计划与路由未投影',
  diff: '差异面未投影 —— 不假装任务级 diff',
  tests: '测试结论未投影 —— 不冒充任务级验证',
  ci: 'CI 运行是项目级的，快照没有 task↔run 外键，因此不冒充任务级验证',
  receipts: '回执、审批与交接未投影',
  approval: '回执、审批与交接未投影',
  handoff: '回执、审批与交接未投影',
  nextAction: '下一步由操作员判定；Observer 只读',
}

export function buildTaskDimensions(record: TaskRecord, snap: SnapshotV3 | null): InspectorDimension[] {
  const dims: InspectorDimension[] = [
    projected('identity', 'Task ID', record.taskId,
      '投影里 task_id 为 null —— 这条记录没有可寻址标识，不是 0 也不是缺源'),
    projected('project', 'Project', record.projectId,
      '投影里 project_id 为 null，归属未记录'),
    projected('status', 'Status', record.status,
      '真实状态；状态机里没有的写法原样显示，不改写成成功'),
    record.leaseHolder
      ? projected('lease', 'Lease / Fencing',
          `${record.leaseHolder} · fence ${record.fencingToken ?? 'UNKNOWN'} · 到期 ${record.leaseExpiresAt || 'UNKNOWN'}`,
          '当前无持有者时为 null，不是 0')
      : nullField('lease', 'Lease / Fencing', '当前没有租约持有者（投影如实回报 null），不是 0 次租约'),
    record.checkpointPresent
      ? projected('checkpoint', 'Checkpoint 身份',
          `键 ${record.checkpointKeys.join(' / ') || '（无键）'} · digest ${record.checkpointDigest ? record.checkpointDigest.slice(0, 12) : 'UNKNOWN'}`,
          '检查点正文不进入只读投影，只投影键名与摘要（摘要随正文变化）')
      : projected('checkpoint', 'Checkpoint 身份', '无检查点（checkpointPresent=false）',
          '投影如实回报没有检查点'),
    (record.createdAt || record.updatedAt)
      ? projected('timeline', 'Timeline（投影携带的时间戳）',
          `${record.createdAt || 'UNKNOWN'} → ${record.updatedAt || 'UNKNOWN'}`,
          '时间戳缺失的一侧显示 UNKNOWN，不补零')
      : nullField('timeline', 'Timeline（投影携带的时间戳）',
          'created_at / updated_at 在这一条记录里都是 null'),
  ]
  for (const key of ['goal', 'revision', 'attempt', 'planner', 'routes', 'diff', 'tests', 'ci'] as const) {
    dims.push(gap(key, TASK_LABELS[key], TASK_GAP_REASONS[key]))
  }
  // Adjacent data, shown as itself: the snapshot DOES carry project-scoped CI runs and plan-level approval
  // rows. They render under their own scope so the task-level gap above stays the honest answer.
  const runs = snap?.ci || []
  dims.push(runs.length > 0 && snap
    ? {
        key: 'ciProject', label: 'CI · 项目级运行（非本任务）', origin: 'PROJECTED',
        value: `${runs.length} 次 · ${runs.slice(0, 3).map((r) => `${r.headSha ? r.headSha.slice(0, 7) : 'UNKNOWN'}/${r.conclusion || r.status || 'UNKNOWN'}`).join(' · ')}`,
        note: '',
      }
    : gap('ciProject', 'CI · 项目级运行（非本任务）', snap ? '快照的 ci 列表为空（已查询，无运行）' : '数据源未接入，不预填运行数'))
  const approvals = (snap?.workspace as { plan?: { approvals?: unknown[] } } | undefined)?.plan?.approvals
  dims.push(approvals && approvals.length > 0
    ? {
        key: 'approvalPlan', label: 'Approval · 计划级审批行（未绑定本任务）', origin: 'PROJECTED',
        value: `${approvals.length} 条审批行，状态 ${approvals.map((a) => String((a as { state?: string }).state ?? 'UNKNOWN')).join(' / ')}`,
        note: '',
      }
    : gap('approvalPlan', 'Approval · 计划级审批行（未绑定本任务）',
        approvals ? '计划里没有审批行（已投影，结果为空）' : '快照未携带 workspace.plan.approvals'))
  dims.push(gap('receipts', TASK_LABELS.receipts, TASK_GAP_REASONS.receipts))
  dims.push(gap('approval', TASK_LABELS.approval, TASK_GAP_REASONS.approval))
  dims.push(gap('handoff', TASK_LABELS.handoff, TASK_GAP_REASONS.handoff))
  dims.push(gap('nextAction', TASK_LABELS.nextAction, TASK_GAP_REASONS.nextAction))
  return dims
}

const TASK_LABELS: Record<string, string> = {
  identity: 'Task ID', project: 'Project', status: 'Status', lease: 'Lease / Fencing',
  checkpoint: 'Checkpoint 身份', timeline: 'Timeline',
  goal: 'Goal', revision: 'Revision', attempt: 'Attempt', planner: 'Planner', routes: 'Agent Routes',
  diff: 'Diff', tests: 'Tests', ci: 'exact-SHA CI', receipts: 'Receipts', approval: 'Approval',
  handoff: 'Handoff', nextAction: 'Next Action',
}

const EXECUTION_GAP_REASONS: Record<string, string> = {
  timeline: '执行记录没有投影时间戳，不拿快照的 generatedAt 冒充执行时刻',
  goal: '目标文本属提示词面，只读投影不带正文',
  revision: '修订由 Task Ledger 合同持有，未进入快照投影',
  attempt: '尝试次数未投影；fence 令牌不是计数',
  planner: '计划层未投影',
  routes: '执行只带 agent 名，计划层的路由决策未投影',
  diff: '差异面未投影',
  tests: '测试结论未投影',
  ci: 'CI 运行是项目级的，快照没有 execution↔run 外键',
  receipts: '回执与交接未投影',
  approval: '审批裁决由后端契约持有，未投影到执行',
  handoff: '回执与交接未投影',
  nextAction: '下一步由操作员判定；Observer 只读',
}

const EXECUTION_LABELS: Record<string, string> = {
  identity: 'Execution ID', project: 'Anchor project', state: 'State', agent: 'Planner / Agent Routes',
  session: 'Session', area: 'Working area', sourceRef: 'Source ref', timeline: 'Execution Timeline',
  goal: 'Goal', revision: 'Revision', attempt: 'Attempt', planner: 'Planner', routes: 'Agent Routes',
  diff: 'Diff', tests: 'Tests', ci: 'exact-SHA CI', receipts: 'Receipts', approval: 'Approval',
  handoff: 'Handoff', nextAction: 'Next Action',
}

const STATE_TEXT: Record<string, string> = {
  RUNNING: '运行中', STARTING: '启动中', WAITING_USER: '待用户', WAITING_APPROVAL: '待审批',
  BLOCKED: '受阻', COMPLETED: '完成', FAILED: '失败', UNKNOWN: '未知',
}

export function buildExecutionDimensions(record: Execution): InspectorDimension[] {
  const dims: InspectorDimension[] = [
    projected('identity', 'Execution ID', record.executionId, '投影里 execution_id 为 null'),
    record.anchorProjectId
      ? projected('project', 'Anchor project', record.anchorProjectId, '归属未记录')
      : nullField('project', 'Anchor project', '该执行没有锚定项目（null），不是无项目'),
    projected('state', 'State', `${STATE_TEXT[record.state] || record.state}（质量 ${record.stateQuality || 'UNKNOWN'}）`,
      '状态质量未投影'),
    record.agent
      ? projected('agent', 'Planner / Agent Routes', `agent ${record.agent}`, 'agent 为 null 时不写「无 agent」')
      : nullField('agent', 'Planner / Agent Routes', 'agent 字段为 null —— 未记录，不等于没有路由'),
    record.sessionId
      ? projected('session', 'Session', record.sessionId, '会话标识未投影')
      : nullField('session', 'Session', 'sessionId 为 null，不伪造会话标识'),
    record.workingArea
      ? projected('area', 'Working area', record.workingArea, '工作区未投影')
      : nullField('area', 'Working area', 'workingArea 为 null'),
    record.sourceRef
      ? projected('sourceRef', 'Source ref', record.sourceRef, '来源引用未投影')
      : nullField('sourceRef', 'Source ref', 'sourceRef 为 null —— 这条执行没有可点名的来源'),
  ]
  for (const key of ['timeline', 'goal', 'revision', 'attempt', 'planner', 'routes', 'diff', 'tests',
    'ci', 'receipts', 'approval', 'handoff', 'nextAction'] as const) {
    dims.push(gap(key, EXECUTION_LABELS[key], EXECUTION_GAP_REASONS[key]))
  }
  return dims
}

export function renderDimension(dimension: InspectorDimension): React.ReactNode {
  if (dimension.origin === 'PROJECTED') {
    return (
      <div className="list-item flex-col items-stretch gap-1" data-dim={dimension.key} data-origin="PROJECTED">
        <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{dimension.label}</div>
        <div className="whitespace-pre-wrap break-words text-[12px] text-ink">{dimension.value}</div>
      </div>
    )
  }
  if (dimension.origin === 'NULL_FIELD') {
    return (
      <div className="list-item flex-col items-stretch gap-1" data-dim={dimension.key} data-origin="NULL_FIELD">
        <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{dimension.label}</div>
        <div className="flex items-center gap-1.5 text-[12px] text-muted">
          <span className="inline-block h-1.5 w-1.5 rounded-full bg-zinc-500" aria-hidden="true" />
          投影为 null · {dimension.note}
        </div>
      </div>
    )
  }
  return (
    <div className="list-item flex-col items-stretch gap-1" data-dim={dimension.key} data-origin="SOURCE_GAP">
      <div className="text-[12px] uppercase tracking-[0.12em] text-muted">{dimension.label}</div>
      <div className="flex items-center gap-1.5 text-[12px] text-warning">
        <span className="inline-block h-1.5 w-1.5 rounded-full bg-secondary" aria-hidden="true" />
        来源缺口（当前 v3 快照未携带 · {dimension.note}）
      </div>
    </div>
  )
}

export interface RecordInspectorProps {
  taskState: FocusState<TaskRecord>
  executionState: FocusState<Execution>
  focus: RecordFocus
  snap: SnapshotV3 | null
  /** the address that clears the focus — a link, never a control */
  clearHref: string
  onClearClick: (event: React.MouseEvent) => void
}

const focusLabel = (focus: RecordFocus): string =>
  [focus.taskId ? `taskId=${focus.taskId}` : null, focus.executionId ? `executionId=${focus.executionId}` : null]
    .filter(Boolean).join(' · ')

export function RecordInspector({
  taskState, executionState, focus, snap, clearHref, onClearClick,
}: RecordInspectorProps) {
  const addressed = focusLabel(focus)
  const blocks: React.ReactNode[] = []

  if (taskState.kind === 'matched') {
    blocks.push(
      <div className="list" key="task" data-record-kind="task">
        {buildTaskDimensions(taskState.record, snap).map((dimension) => (
          <React.Fragment key={dimension.key}>{renderDimension(dimension)}</React.Fragment>
        ))}
      </div>,
    )
  } else if (taskState.kind !== 'unasked') {
    const wanted = taskState.kind === 'not-found' ? taskState.wanted : null
    blocks.push(
      <div className="list" key="task" data-record-kind="task">
        {renderDimension(gap('identity', 'Task ID',
          wanted
            ? `地址要求 taskId=${wanted}，快照里没有这条记录（已删除 / 属其他项目 / 未投影），这里不会改选别的记录`
            : '后端未提供 taskRecords 字段（生产者未查询任务表），与「查询过但没有任务」是两件事'))}
      </div>,
    )
  }

  if (executionState.kind === 'matched') {
    blocks.push(
      <div className="list" key="execution" data-record-kind="execution">
        {buildExecutionDimensions(executionState.record).map((dimension) => (
          <React.Fragment key={dimension.key}>{renderDimension(dimension)}</React.Fragment>
        ))}
      </div>,
    )
  } else if (executionState.kind !== 'unasked') {
    const wanted = executionState.kind === 'not-found' ? executionState.wanted : null
    blocks.push(
      <div className="list" key="execution" data-record-kind="execution">
        {renderDimension(gap('identity', 'Execution ID',
          wanted
            ? `地址要求 executionId=${wanted}，快照的 executions 里没有这条执行`
            : '快照未接入，执行列表无从解析'))}
      </div>,
    )
  }

  if (blocks.length === 0) {
    blocks.push(
      <div className="text-xs text-muted" key="unasked" data-record-kind="unasked">
        未定位记录：地址里没有 taskId / executionId，因此下面只有快照级维度。
        记录级维度（Goal / Revision / Attempt / Planner / Routes / Timeline / Diff / Tests / CI /
        Receipts / Approval / Handoff / Next Action）需要一条记录才能回答，
        <a href={recordLink('work', { taskId: null, executionId: null }, '')} className="text-secondary-ink"> 从列表选择</a>。
      </div>,
    )
  }

  return (
    <>
      {blocks}
      {addressed && (
        <div className="mt-2 break-all font-mono text-[12px] text-muted" data-testid="inspector-focus-address">
          定位：{addressed} ·
          <a href={clearHref} onClick={onClearClick} className="ml-1" data-testid="inspector-clear">清除</a>
        </div>
      )}
    </>
  )
}
