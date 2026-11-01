// L10 (2026-09-27): behavior tests for the four new B10 lanes
// (Workflows / Workflow Editor / Observer / Execution Detail).
// Pinned contracts:
//   * honest UNKNOWN when the v3 snapshot carries no projection for a lane
//   * the Workflow Editor canvas is INTERACTIVE (add/select/connect/delete
//     mutate real state — not a static flow diagram)
//   * Observer is strictly read-only: ZERO write/approve/deny/retry buttons
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, act, within } from '@testing-library/react'
import { WorkflowsView } from '@/views/WorkflowsView'
import { WorkflowEditorView } from '@/views/WorkflowEditorView'
import { ObserverView } from '@/views/ObserverView'
import { ExecutionDetailView } from '@/views/ExecutionDetailView'
import type { SnapshotV3 } from '@/types'

afterEach(cleanup)

const base: SnapshotV3 = {
  schemaVersion: 'workflow/snapshot/v3',
  revision: 7,
  generatedAt: '2026-09-27T00:00:00Z',
  sourceWatermark: null,
  transport: { transportState: 'LIVE', freshnessState: 'FRESH', connectedSince: null, eventsUrl: null },
  coverage: { numerator: 1, denominator: 1, scope: 'unit' },
  governance: {
    state: 'CLEAN',
    families: {
      rules: { state: 'CLEAN', current: null, drift: 0 },
      skills: { state: 'CLEAN', current: null, drift: 0 },
      memory: { state: 'CLEAN', current: null, drift: 0 },
      adapters: { state: 'CLEAN', current: null, drift: 0 },
    },
  },
  workspace: {},
  projects: [],
  executions: [
    {
      executionId: 'EX-1',
      anchorProjectId: 'work-lab',
      workingArea: 'apps/observer',
      state: 'RUNNING',
      stateQuality: 'EXACT',
      agent: 'hermes',
      sessionId: 's-1',
      sourceRef: 's3://audit/EX-1',
    },
  ],
  tasks: {},
  tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
  git: { localSha: null, remoteSha: null, ciSha: null, matchState: 'NO_LOCAL_CLAIM' },
  ci: [],
  sourceRefs: [],
}

const emptySnap: SnapshotV3 = {
  ...base,
  executions: [],
  transport: { transportState: 'OFFLINE', freshnessState: 'UNKNOWN', connectedSince: null, eventsUrl: null },
}

describe('L10 · Workflows lane (honest B10 structure)', () => {
  it('renders the B10 list structure + honest UnknownState when no workflows[] contract', () => {
    render(<WorkflowsView snap={base} />)
    expect(screen.getByText('Workflows / 工作流')).toBeTruthy()
    expect(screen.getByText('工作流数据未知')).toBeTruthy()
    expect(screen.getByText('新建工作流')).toBeTruthy()
    // search + filter controls exist (fully functional, honest empty)
    expect(screen.getByLabelText('搜索工作流')).toBeTruthy()
    expect(screen.getByLabelText('按状态筛选')).toBeTruthy()
  })

  it('projects a real workflows[] array when the contract carries it', () => {
    const snap = {
      ...base,
      workflows: [
        { id: 'wf-1', name: 'daily-gate', owner: 'hermes', version: 'v3', state: 'active' },
        { id: 'wf-2', name: 'legacy-route', owner: 'cc-switch', version: 'v1', state: 'archived' },
      ],
    } as SnapshotV3
    render(<WorkflowsView snap={snap} />)
    expect(screen.getByText('daily-gate')).toBeTruthy()
    expect(screen.getByText('legacy-route')).toBeTruthy()
    // state filter actually filters
    const select = screen.getByLabelText('按状态筛选') as HTMLSelectElement
    act(() => {
      select.value = 'active'
      fireEvent.change(select, { target: { value: 'active' } })
    })
    expect(screen.getByText('daily-gate')).toBeTruthy()
    expect(screen.queryByText('legacy-route')).toBeNull()
  })
})

describe('L10 · Workflow Editor (interactive canvas, not a static diagram)', () => {
  it('adding a node from the toolbar mutates the canvas', () => {
    render(<WorkflowEditorView snap={base} />)
    const before = screen.getAllByText(/Trigger|Validate|Agent|Approval|Output/).length
    // click the first toolbar node-kind button (Trigger)
    const triggerBtn = screen.getByRole('button', { name: '添加 Trigger 节点' })
    fireEvent.click(triggerBtn)
    const after = screen.getAllByText(/Trigger|Validate|Agent|Approval|Output/).length
    expect(after).toBeGreaterThan(before)
  })

  it('selecting a node opens the property panel and 发布/运行 stay honestly disabled', () => {
    render(<WorkflowEditorView snap={base} />)
    fireEvent.click(screen.getByText('校验'))
    expect(screen.getByText('属性面板')).toBeTruthy()
    expect(screen.queryByText('未选中')).toBeNull() // panel now shows the kind
    const publish = screen.getByRole('button', { name: '保存并发布' })
    const run = screen.getByRole('button', { name: '运行' })
    expect(publish).toBeDisabled()
    expect(run).toBeDisabled()
    expect(screen.getByText(/真实 workflow-schema 契约接入前保持禁用/)).toBeTruthy()
  })

  it('deleting the selected node removes it from the canvas', () => {
    render(<WorkflowEditorView snap={base} />)
    fireEvent.click(screen.getByText('审批门'))
    fireEvent.click(screen.getByRole('button', { name: '删除所选节点' }))
    expect(screen.queryByText('审批门')).toBeNull()
  })
})

describe('L10 · Observer lane (strictly read-only)', () => {
  it('projects the B10 metric row from the REAL v3 transport/coverage truth', () => {
    render(<ObserverView snap={base} />)
    expect(screen.getByText('Observer / 观察者')).toBeTruthy()
    // metric values come from the snapshot, not fabricated
    expect(screen.getAllByText('LIVE').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText('FRESH')).toBeTruthy()
    expect(screen.getByText('1/1 · unit')).toBeTruthy()
    // topology surface present (Observer core + 6 satellite entities)
    const img = document.querySelector('[role="img"]')
    expect(img).toBeTruthy()
    expect((img as Element).getAttribute('aria-label') ?? '').toContain('观察者拓扑')
  })

  it('exposes ZERO write/approve/deny/retry controls (read-only iron law)', () => {
    render(<ObserverView snap={base} />)
    const buttons = Array.from(document.querySelectorAll('button')).map((b) => b.textContent || '')
    for (const forbidden of ['批准', '拒绝', '撤销', '重试', '应用', '回滚']) {
      expect(buttons.filter((t) => t.includes(forbidden))).toHaveLength(0)
    }
  })

  it('an honest OFFLINE snapshot keeps every metric UNKNOWN-ish, never a fake LIVE', () => {
    render(<ObserverView snap={emptySnap} />)
    // no LIVE pill on an OFFLINE transport
    expect(screen.queryByText('LIVE · 只读')).toBeNull()
    expect(screen.getAllByText(/OFFLINE/).length).toBeGreaterThanOrEqual(1)
  })
})

describe('L10 · Execution Detail lane (read-only detail projection)', () => {
  it('renders the real execution list + its detail fields', () => {
    render(<ExecutionDetailView snap={base} />)
    expect(screen.getByText('Execution Detail / 执行详情')).toBeTruthy()
    // the real execution id + agent + state text appear (list + detail panes)
    expect(screen.getAllByText('EX-1').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('hermes').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('运行中').length).toBeGreaterThanOrEqual(1)
    expect(screen.getAllByText('s3://audit/EX-1').length).toBeGreaterThanOrEqual(1)
  })

  it('stays honest (UnknownState) when the snapshot has no executions', () => {
    render(<ExecutionDetailView snap={emptySnap} />)
    expect(screen.getByText('无执行记录')).toBeTruthy()
  })
})
