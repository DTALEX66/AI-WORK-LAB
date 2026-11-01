/** P1-04 · one test per Inspector dimension.
 *
 * The panel answers a fixed list of questions about the focused record, and the register's rule is that a
 * dimension is either a real projected value or an explicit source gap with its reason. This file walks
 * `TASK_DIMENSION_KEYS` / `EXECUTION_DIMENSION_KEYS` one at a time against a real-shape fixture (the same
 * field set `snapshot_api.py::project_task_record` emits) and asserts, per dimension:
 *
 *  - the row exists and renders visible text (a row that renders nothing is not an answer);
 *  - PROJECTED rows carry the fixture's own value and do NOT say 来源缺口;
 *  - SOURCE_GAP rows say 来源缺口 and name the reason, and do NOT leak a fabricated value (0, UNKNOWN-as-a-
 *    number, the neighbouring project-level data);
 *  - a field the projection carries as `null` is its own third state — neither a gap nor a zero.
 *
 * `data-origin` is asserted together with the visible text, never instead of it: a marker alone is not
 * proof that the owner can see the difference.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { WorkView } from '@/views/WorkView'
import {
  TASK_DIMENSION_KEYS, EXECUTION_DIMENSION_KEYS,
  buildTaskDimensions, buildExecutionDimensions,
} from '@/views/RecordInspector'
import { mkSnap, mkTaskRecord, mkExecution } from '@/test/snapshotFixture'
import type { SnapshotV3, TaskRecord } from '@/types'

afterEach(cleanup)

const RECORD = mkTaskRecord()

function snapWith(records: TaskRecord[]): SnapshotV3 {
  return mkSnap({
    taskRecords: records,
    executions: [mkExecution()],
    ci: [{
      runId: 'r-1', workflow: 'wlr-060', headSha: 'c0ffee1111111111111111111111111111111111',
      status: 'completed', conclusion: 'success', sourceRef: null,
    }],
    workspace: { plan: { approvals: [{ state: 'WAITING_APPROVAL' }] }, governance: { contracts: 3 } },
  })
}

const FOCUS = { taskId: RECORD.taskId, executionId: null }

/** The origin each dimension must answer with for a fully-populated record. Anything else in this table is
 *  the two shapes this product forbids: a gap dressed as a value, or a value dressed as a gap. */
const TASK_EXPECTED_ORIGIN: Record<string, 'PROJECTED' | 'SOURCE_GAP'> = {
  identity: 'PROJECTED', project: 'PROJECTED', status: 'PROJECTED', lease: 'PROJECTED',
  checkpoint: 'PROJECTED', timeline: 'PROJECTED',
  goal: 'SOURCE_GAP', revision: 'SOURCE_GAP', attempt: 'SOURCE_GAP', planner: 'SOURCE_GAP',
  routes: 'SOURCE_GAP', diff: 'SOURCE_GAP', tests: 'SOURCE_GAP', ci: 'SOURCE_GAP',
  receipts: 'SOURCE_GAP', approval: 'SOURCE_GAP', handoff: 'SOURCE_GAP', nextAction: 'SOURCE_GAP',
}

/** The fixture value the row has to show, or the reason text a gap has to name. */
const TASK_EXPECTED_TEXT: Record<string, string> = {
  identity: 'WL-900',
  project: 'work-lab',
  status: 'WAITING_APPROVAL',
  lease: 'worker-9 · fence 7 · 到期 2026-10-08T01:30:00Z',
  checkpoint: '键 cursor / stage · digest bbbbbbbbbbbb',
  timeline: '2026-10-08T01:00:00Z → 2026-10-08T01:20:00Z',
  goal: '目标文本属提示词面',
  revision: 'Task Ledger',
  attempt: 'fencingToken',
  planner: '计划与路由未投影',
  routes: '计划与路由未投影',
  diff: '差异面未投影',
  tests: '测试结论未投影',
  ci: 'task↔run 外键',
  receipts: '回执、审批与交接未投影',
  approval: '回执、审批与交接未投影',
  handoff: '回执、审批与交接未投影',
  nextAction: '下一步由操作员判定',
}

function renderFocused(over: Partial<TaskRecord> = {}) {
  const record = mkTaskRecord(over)
  return render(
    <WorkView snap={snapWith([record])} focus={{ taskId: record.taskId, executionId: null }} onFocus={() => {}} />,
  )
}

function rowOf(container: HTMLElement, key: string): HTMLElement | null {
  const block = container.querySelector('[data-record-kind="task"]')
  return (block?.querySelector(`[data-dim="${key}"]`) as HTMLElement) ?? null
}

describe('P1-04 · every task dimension answers', () => {
  it('the dimension list the detail card is asked about is the list the Inspector walks', () => {
    // A key that leaves the model silently removes a question the Inspector used to answer.
    expect(TASK_DIMENSION_KEYS).toEqual([
      'identity', 'project', 'status', 'lease', 'checkpoint', 'timeline',
      'goal', 'revision', 'attempt', 'planner', 'routes', 'diff', 'tests',
      'ci', 'receipts', 'approval', 'handoff', 'nextAction',
    ])
    const built = buildTaskDimensions(RECORD, snapWith([RECORD])).map((d) => d.key)
    // two extra rows are allowed, and only these: the adjacent-scope rows, which never replace their
    // task-level counterpart
    expect(built.filter((key) => key !== 'ciProject' && key !== 'approvalPlan')).toEqual([...TASK_DIMENSION_KEYS])
    expect(built.filter((key) => key === 'ciProject' || key === 'approvalPlan').sort()).toEqual(['approvalPlan', 'ciProject'])
    expect(built.indexOf('ciProject')).toBeLessThan(built.indexOf('receipts'))
  })

  it.each(TASK_DIMENSION_KEYS)('task dimension "%s" renders a value or a named gap, never a blank', (key) => {
    const { container } = renderFocused()
    const row = rowOf(container, key)
    expect(row, `dimension ${key} has no row in the Inspector`).not.toBeNull()
    const text = (row!.textContent || '').trim()
    expect(text.length, `dimension ${key} renders an empty cell`).toBeGreaterThan(12)

    const expected = TASK_EXPECTED_ORIGIN[key]
    expect(row!.getAttribute('data-origin'), `${key} answered with the wrong origin`).toBe(expected)
    if (expected === 'PROJECTED') {
      expect(text).toContain(TASK_EXPECTED_TEXT[key])
      expect(text).not.toContain('来源缺口')
    } else {
      expect(text).toContain('来源缺口')
      expect(text).toContain(TASK_EXPECTED_TEXT[key])
      // a gap must not be padded into an answer
      expect(text).not.toMatch(/\b0\b|UNKNOWN（默认|无记录/)
    }
  })

  it('the adjacent project-level CI row states its own scope instead of becoming the task answer', () => {
    const { container } = renderFocused()
    const row = container.querySelector('[data-dim="ciProject"]') as HTMLElement
    expect(row.getAttribute('data-origin')).toBe('PROJECTED')
    expect(row.textContent).toContain('项目级')
    expect(row.textContent).toContain('c0ffee1')
    expect(row.textContent).toContain('success')
    expect(row.textContent).not.toContain('本任务的 CI')
    // and the task-level row beside it is still a gap
    expect((rowOf(container, 'ci')!).getAttribute('data-origin')).toBe('SOURCE_GAP')
  })

  it('a lease with no holder is 投影为 null, not a gap and not a zero', () => {
    const { container } = renderFocused({ leaseHolder: null, fencingToken: null, leaseExpiresAt: null })
    const row = rowOf(container, 'lease')!
    expect(row.getAttribute('data-origin')).toBe('NULL_FIELD')
    const text = row.textContent || ''
    expect(text).toContain('投影为 null')
    expect(text).not.toContain('来源缺口')
    // no fence count and no expiry may be conjured for a lease that does not exist
    expect(text).not.toMatch(/fence\s*[\d-]/)
    expect(text).not.toMatch(/到期\s*[\dT]/)
  })

  it('a record without a checkpoint says so from the projection, without inventing keys or a digest', () => {
    const { container } = renderFocused({ checkpointPresent: false, checkpointKeys: [], checkpointDigest: null })
    const row = rowOf(container, 'checkpoint')!
    expect(row.getAttribute('data-origin')).toBe('PROJECTED')
    expect(row.textContent).toContain('无检查点')
    expect(row.textContent).not.toContain('digest')
  })

  it('a snapshot without taskRecords gives the Inspector nothing to answer with, and says which absence it is', () => {
    const snapshot = mkSnap({ executions: [mkExecution()] })
    const { container } = render(
      <WorkView snap={snapshot} focus={{ taskId: 'WL-900', executionId: null }} onFocus={() => {}} />,
    )
    const block = container.querySelector('[data-record-kind="task"]')
    expect(block?.textContent).toContain('后端未提供')
    expect(block?.textContent).not.toContain('无任务记录')
    expect(block?.textContent).not.toContain('worker-9')
  })

  it('a wanted record the projection does not contain is named, and does not borrow another record', () => {
    const { container } = render(
      <WorkView snap={snapWith([RECORD])} focus={{ taskId: 'WL-gone', executionId: null }} onFocus={() => {}} />,
    )
    const block = container.querySelector('[data-record-kind="task"]')
    expect(block?.textContent).toContain('WL-gone')
    expect(block?.textContent).toContain('没有这条记录')
    expect(block?.textContent).not.toContain('WL-900')
  })
})

describe('P1-04 · the Inspector follows the URL focus', () => {
  it('the record block changes when the addressed record changes', () => {
    const other = mkTaskRecord({
      taskId: 'WL-901', projectId: 'design-lab', status: 'BLOCKED', leaseHolder: 'worker-1',
      fencingToken: 4, checkpointDigest: 'c'.repeat(64), checkpointKeys: ['phase'],
    })
    const snapshot = snapWith([RECORD, other])

    const first = render(<WorkView snap={snapshot} focus={FOCUS} onFocus={() => {}} />)
    expect(first.container.querySelector('[data-dim="identity"]')?.textContent).toContain('WL-900')
    expect(first.container.querySelector('[data-record-kind="task"]')?.textContent).not.toContain('WL-901')
    first.unmount()

    const second = render(
      <WorkView snap={snapshot} focus={{ taskId: 'WL-901', executionId: null }} onFocus={() => {}} />,
    )
    const block = second.container.querySelector('[data-record-kind="task"]')
    expect(block?.textContent).toContain('WL-901')
    expect(block?.textContent).toContain('design-lab')
    expect(block?.textContent).toContain('worker-1 · fence 4')
    expect(block?.textContent).not.toContain('WL-900 · ')
    expect(block?.textContent).not.toContain('worker-9')
  })

  it('an execution focus answers the execution dimensions instead, including its real agent route', () => {
    const { container } = render(
      <WorkView snap={snapWith([RECORD])} focus={{ taskId: null, executionId: 'ex-9' }} onFocus={() => {}} />,
    )
    const block = container.querySelector('[data-record-kind="execution"]')
    expect(block, 'the Inspector must answer for the focused execution').not.toBeNull()
    expect(block!.textContent).toContain('ex-9')
    const agent = block!.querySelector('[data-dim="agent"]') as HTMLElement
    expect(agent.getAttribute('data-origin')).toBe('PROJECTED')
    expect(agent.textContent).toContain('codex')
    const session = block!.querySelector('[data-dim="session"]') as HTMLElement
    expect(session.textContent).toContain('sess-42')
    // its timeline really is a gap: executions carry no timestamps in v3
    const timeline = block!.querySelector('[data-dim="timeline"]') as HTMLElement
    expect(timeline.getAttribute('data-origin')).toBe('SOURCE_GAP')
    expect(timeline.textContent).toContain('来源缺口')
    // and a record that was not addressed is not answered
    expect(container.querySelector('[data-record-kind="task"]')).toBeNull()
  })

  it('an execution whose optional fields are null is not painted as a source gap', () => {
    const bare = { ...mkExecution(), sessionId: null, sourceRef: null, workingArea: null } as never
    const snapshot = mkSnap({ taskRecords: [RECORD], executions: [bare] })
    const { container } = render(
      <WorkView snap={snapshot} focus={{ taskId: null, executionId: 'ex-9' }} onFocus={() => {}} />,
    )
    const block = container.querySelector('[data-record-kind="execution"]')!
    for (const key of ['session', 'area', 'sourceRef']) {
      const row = block.querySelector(`[data-dim="${key}"]`) as HTMLElement
      expect(row.getAttribute('data-origin'), `${key} is carried and null, not missing`).toBe('NULL_FIELD')
      expect(row.textContent).toContain('投影为 null')
      expect(row.textContent).not.toContain('来源缺口')
    }
  })

  it('the whole execution dimension contract is answerable, one row per key', () => {
    const dims = buildExecutionDimensions(mkExecution())
    expect(dims.map((d) => d.key)).toEqual([...EXECUTION_DIMENSION_KEYS])
    // every row is answerable: a projected value, or a reason a reader can act on. A gap without a reason is
    // the shape that used to read as "the product has nothing to say" while the code simply forgot the text.
    const unanswered = dims.filter((d) => d.origin !== 'PROJECTED' && (d.note ?? '').trim().length < 4).map((d) => d.key)
    expect(unanswered, `gap dimensions carrying no reason: ${unanswered.join(', ')}`).toEqual([])
    const valueless = dims.filter((d) => d.origin === 'PROJECTED' && (d.value ?? '').trim().length < 4).map((d) => d.key)
    expect(valueless, `projected dimensions carrying no value: ${valueless.join(', ')}`).toEqual([])
    const taskDims = buildTaskDimensions(RECORD, snapWith([RECORD]))
    const taskUnanswered = taskDims
      .filter((d) => d.origin !== 'PROJECTED' && (d.note ?? '').trim().length < 4)
      .map((d) => d.key)
    expect(taskUnanswered, `task gaps carrying no reason: ${taskUnanswered.join(', ')}`).toEqual([])
    for (const key of TASK_DIMENSION_KEYS) {
      expect(taskDims.some((d) => d.key === key), `task dimension ${key} vanished`).toBe(true)
    }
  })

  it('no record addressed means no record answered: the panel says what it needs', () => {
    const { container } = render(<WorkView snap={snapWith([RECORD])} onFocus={() => {}} />)
    const block = container.querySelector('[data-record-kind="unasked"]')
    expect(block, 'the Inspector must state that no record is addressed').not.toBeNull()
    expect(block!.textContent).toContain('未定位记录')
    expect(container.querySelector('[data-record-kind="task"]')).toBeNull()
    expect(container.textContent).not.toContain('worker-9 · fence')
  })
})
