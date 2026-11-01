// UI_VIEWS (20260921): mount the five new L7 governance views against a
// minimal fake SnapshotV3 and pin the HONEST-STATE discipline:
//   * absent data source  -> EmptyState/UnknownState text, no fabricated KPIs
//   * present data source  -> the REAL field values render (ci runId, etc.)
//   * no write-action buttons are exposed (read-only observer contract)
import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { RulesPolicyView } from '@/views/RulesPolicyView'
import { AuditTrailView } from '@/views/AuditTrailView'
import { ApprovalsView } from '@/views/ApprovalsView'
import { IntegrationsView } from '@/views/IntegrationsView'
import { TaskPacksView } from '@/views/TaskPacksView'
import type { SnapshotV3 } from '@/types'

afterEach(cleanup)

// Minimal real-shaped snapshot: governance families all CLEAN, one CI run,
// one execution, a task-family count, a plan approval, an adapter family.
const base: SnapshotV3 = {
  schemaVersion: 'workflow/snapshot/v3',
  revision: 1,
  generatedAt: '2026-09-21T00:00:00Z',
  sourceWatermark: null,
  transport: {
    transportState: 'LIVE',
    freshnessState: 'FRESH',
    connectedSince: null,
    eventsUrl: null,
  },
  coverage: { numerator: 1, denominator: 1, scope: 'unit' },
  governance: {
    state: 'CLEAN',
    families: {
      rules: { state: 'CLEAN', current: null, drift: 0 },
      skills: { state: 'DRIFT', current: null, drift: 2 },
      memory: { state: 'UNKNOWN', current: null, drift: null },
      adapters: { state: 'CLEAN', current: null, drift: 0 },
    },
  },
  workspace: {
    plan: {
      status: 'active',
      approvals: [{ taskId: 'APPR-1', state: 'pending' }],
      tasks: [{ taskId: 'TASK-1', owner: 'agent' }],
    },
  },
  projects: [],
  executions: [
    {
      executionId: 'EX-77',
      anchorProjectId: null,
      workingArea: null,
      state: 'COMPLETED',
      stateQuality: 'EXACT',
      agent: 'hermes',
      sessionId: null,
      sourceRef: 's3://audit/EX-77',
    },
  ],
  tasks: { rules: 3, memory: 1 },
  tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
  git: { localSha: null, remoteSha: null, ciSha: null, matchState: 'NO_LOCAL_CLAIM' },
  ci: [
    {
      runId: '35545037452',
      workflow: 'work-lab-gate',
      headSha: '00f45a10',
      status: 'completed',
      conclusion: 'failure',
      sourceRef: 'gh.run/35545037452',
    },
  ],
  sourceRefs: ['gh.run/35545037452'],
}

const empty: SnapshotV3 = { ...base, ci: [], executions: [], tasks: {}, sourceRefs: [] }

describe('UI_VIEWS honest-state discipline', () => {
  it('RulesPolicyView renders real family states and drift numbers', () => {
    render(<RulesPolicyView snap={base} />)
    // real field values
    expect(screen.getByText('技能')).toBeTruthy()
    expect(screen.getByText('漂移')).toBeTruthy() // skills DRIFT
    expect(screen.getAllByText('2').length).toBeGreaterThan(0) // drift=2
    expect(screen.getByText('规则')).toBeTruthy()
  })

  it('RulesPolicyView falls back to an honest EmptyState when families are UNKNOWN-only', () => {
    const snap = {
      ...base,
      governance: {
        state: 'UNKNOWN',
        families: {
          rules: { state: 'UNKNOWN', current: null, drift: null },
          skills: { state: 'UNKNOWN', current: null, drift: null },
          memory: { state: 'UNKNOWN', current: null, drift: null },
          adapters: { state: 'UNKNOWN', current: null, drift: null },
        },
      },
    }
    render(<RulesPolicyView snap={snap} />)
    expect(screen.getByText('当前快照未携带治理契约明细')).toBeTruthy()
    // honest: the "漂移" badge (real drift state) must NOT appear
    expect(screen.queryByText('漂移')).toBeNull()
  })

  it('AuditTrailView renders the real CI runId + sourceRef, no write buttons', () => {
    render(<AuditTrailView snap={base} />)
    // real field values (ref cell carries workflow @ sha + run id)
    expect(screen.getByText('work-lab-gate @ 00f45a10 · run 35545037452')).toBeTruthy()
    expect(screen.getByText('EX-77 · hermes')).toBeTruthy()
    // sourceRef appears in the row + the 来源引用 card list (>=2 elements)
    expect(screen.getAllByText('gh.run/35545037452').length).toBeGreaterThanOrEqual(2)
    // read-only: no 重试/撤销/重放 buttons
    expect(screen.queryByText('重试')).toBeNull()
    expect(screen.queryByText('撤销')).toBeNull()
  })

  it('AuditTrailView falls back to an honest EmptyState when there are no records', () => {
    render(<AuditTrailView snap={empty} />)
    expect(screen.getByText('无审计记录')).toBeTruthy()
  })

  it('ApprovalsView renders the real plan approval and never a fake state', () => {
    render(<ApprovalsView snap={base} />)
    expect(screen.getByText('APPR-1')).toBeTruthy()
    expect(screen.getByText('pending')).toBeTruthy()
    // read-only: no approve/deny buttons
    expect(screen.queryByRole('button', { name: /批准|拒绝|撤销/ })).toBeNull()
  })

  it('ApprovalsView stays UNKNOWN when the plan has no approvals', () => {
    render(<ApprovalsView snap={{ ...base, workspace: {} }} />)
    expect(screen.getByText('审批数据未知')).toBeTruthy()
  })

  it('IntegrationsView renders the real adapters state and the static 7-client doc', () => {
    render(<IntegrationsView snap={base} />)
    // real adapters family = CLEAN
    expect(screen.getByText('CLEAN')).toBeTruthy()
    // static documentation clients
    expect(screen.getByText('cc-switch')).toBeTruthy()
    expect(screen.getByText('open-design')).toBeTruthy()
    // honest label that this is documentation, not live status (repeats per client row)
    expect(screen.getAllByText('受控（无实时状态投影）').length).toBeGreaterThan(0)
  })

  it('IntegrationsView falls back to an honest EmptyState when adapters are UNKNOWN', () => {
    render(
      <IntegrationsView
        snap={{
          ...base,
          governance: {
            state: 'UNKNOWN',
            families: {
              rules: { state: 'UNKNOWN', current: null, drift: null },
              skills: { state: 'UNKNOWN', current: null, drift: null },
              memory: { state: 'UNKNOWN', current: null, drift: null },
              adapters: { state: 'UNKNOWN', current: null, drift: null },
            },
          },
        }}
      />,
    )
    expect(screen.getByText('无集成明细')).toBeTruthy()
  })

  it('TaskPacksView renders the real task-family counts and plan tasks', () => {
    render(<TaskPacksView snap={base} />)
    expect(screen.getByText('rules')).toBeTruthy()
    expect(screen.getByText('3')).toBeTruthy()
    expect(screen.getByText('TASK-1')).toBeTruthy()
  })

  it('TaskPacksView stays honest when there are no task counts', () => {
    render(<TaskPacksView snap={{ ...base, tasks: {}, workspace: {} }} />)
    expect(screen.getByText('无任务包计数')).toBeTruthy()
  })
})
