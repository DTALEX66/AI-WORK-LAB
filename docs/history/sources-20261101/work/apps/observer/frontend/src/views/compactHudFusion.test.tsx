// 2026-10-19 · compact-HUD fusion contracts (Agent HUD execution model × v3 truth).
//
// The fusion adds the reference HUD's lanes (segmented views, per-source
// detail, sessions, waits) WITHOUT adding data it does not have:
//   * input/output are summed only over reported values, and "unclassified"
//     stays uncomputable when any project lacks a part;
//   * sessions are executions[] ordered by state priority, never by elapsed
//     time the projection does not carry;
//   * execution waits and workspace.plan.approvals are two different objects
//     and are counted separately;
//   * the approval lane is READ-ONLY: no approve/deny/allow control exists;
//   * tab and selected source travel in the URL.
import { describe, it, expect, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import { CompactHUD } from './CompactHUD'
import {
  buildHudApprovals, buildHudProviders, buildHudSessions, hudAgentBar,
  hudTabFromParam, sessionTokenDelta, type TokenSample,
} from './hudModel'
import { mkExecution, mkProject, mkSnap } from '@/test/snapshotFixture'

afterEach(cleanup)

beforeEach(() => {
  window.history.replaceState(null, '', '/')
})

function token(over: { input?: number | null; output?: number | null; total: number | null }) {
  return {
    inputTokens: over.input === undefined ? over.total : over.input,
    outputTokens: over.output === undefined ? over.total : over.output,
    totalTokens: over.total,
    costQuality: 'EXACT' as const,
  }
}

describe('fusion read model · per-source token split', () => {
  it('sums input/output only over reported values and keeps a partial split uncomputable', () => {
    const snap = mkSnap({
      projects: [
        mkProject({ projectId: 'a', agentPlatform: 'codex', token: token({ input: 100, output: 50, total: 200 }) }),
        // A second project in the same group reports only a total.
        mkProject({ projectId: 'b', agentPlatform: 'codex', token: token({ input: null, output: null, total: 300 }) }),
      ],
    })
    const [codex] = buildHudProviders(snap)
    expect(codex.totalTokens).toBe(500)
    expect(codex.inputTokens).toBe(100)
    expect(codex.outputTokens).toBe(50)
    // 500-150 would silently treat the unreported split as "unclassified".
    expect(codex.unclassifiedTokens).toBeNull()
    expect(hudAgentBar(codex).known).toBe(false)
  })

  it('draws the stacked bar only for a complete triple', () => {
    const [complete] = buildHudProviders(mkSnap({
      projects: [mkProject({ token: token({ input: 60, output: 30, total: 100 }) })],
    }))
    expect(hudAgentBar(complete)).toEqual({ known: true, input: 60, output: 30, unclassified: 10 })

    // Parts larger than the reported total cannot be rendered as widths.
    const [overflow] = buildHudProviders(mkSnap({
      projects: [mkProject({ token: token({ input: 90, output: 90, total: 100 }) })],
    }))
    expect(hudAgentBar(overflow).known).toBe(false)
  })

  it('an entirely unreported token group keeps null parts, not zeros', () => {
    const [unknown] = buildHudProviders(mkSnap({
      projects: [mkProject({ agentPlatform: 'hermes', token: token({ total: null }) })],
    }))
    expect(unknown.totalTokens).toBeNull()
    expect(unknown.inputTokens).toBeNull()
    expect(unknown.outputTokens).toBeNull()
    expect(unknown.unclassifiedTokens).toBeNull()
    expect(unknown.costQuality).toBe('UNKNOWN')
  })

  it('reports the worst cost quality among the projects that reported a total', () => {
    const snap = mkSnap({
      projects: [
        mkProject({ projectId: 'a', agentPlatform: 'codex', token: { inputTokens: 1, outputTokens: 1, totalTokens: 10, costQuality: 'EXACT' } }),
        mkProject({ projectId: 'b', agentPlatform: 'codex', token: { inputTokens: 1, outputTokens: 1, totalTokens: 10, costQuality: 'ESTIMATED' } }),
        // An UNKNOWN-quality row that reported no total must not drag the group
        // into UNKNOWN: quality describes the values that exist.
        mkProject({ projectId: 'c', agentPlatform: 'codex', token: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' } }),
      ],
    })
    expect(buildHudProviders(snap)[0].costQuality).toBe('ESTIMATED')
  })

  it('lists the largest reporting projects for the detail pane', () => {
    const snap = mkSnap({
      projects: [
        mkProject({ projectId: 'a', displayName: 'A', agentPlatform: 'codex', token: token({ total: 10 }) }),
        mkProject({ projectId: 'b', displayName: 'B', agentPlatform: 'codex', token: token({ total: 90 }) }),
        mkProject({ projectId: 'c', displayName: 'C', agentPlatform: 'codex', token: token({ total: 50 }) }),
        mkProject({ projectId: 'd', displayName: 'D', agentPlatform: 'codex', token: token({ total: 70 }) }),
      ],
    })
    const [codex] = buildHudProviders(snap)
    expect(codex.topProjects.map((p) => p.projectId)).toEqual(['b', 'd', 'c'])
  })
})

describe('fusion read model · sessions', () => {
  it('orders waits first, then running, then ended, and joins the anchor project', () => {
    const snap = mkSnap({
      executions: [
        mkExecution({ executionId: 'ex-ended', state: 'COMPLETED', anchorProjectId: 'design-lab' }),
        mkExecution({ executionId: 'ex-run', state: 'RUNNING', anchorProjectId: 'work-lab' }),
        mkExecution({ executionId: 'ex-ask', state: 'WAITING_USER', anchorProjectId: 'work-lab' }),
        mkExecution({ executionId: 'ex-approve', state: 'WAITING_APPROVAL', anchorProjectId: 'work-lab' }),
      ],
    })
    const summary = buildHudSessions(snap)
    expect(summary.rows.map((r) => r.executionId)).toEqual(['ex-approve', 'ex-ask', 'ex-run', 'ex-ended'])
    expect(summary.rows[0].projectLabel).toBe('WORK-LAB')
    expect(summary.rows[3].projectLabel).toBe('DESIGN-LAB')
    expect(summary).toMatchObject({
      total: 4, waiting: 2, waitingApproval: 1, waitingUser: 1, active: 1, completed: 1, failed: 0,
    })
  })

  it('keeps an unknown anchor visible instead of dropping or inventing a project', () => {
    const snap = mkSnap({
      executions: [mkExecution({ executionId: 'ex-x', anchorProjectId: 'not-in-registry' })],
    })
    const [row] = buildHudSessions(snap).rows
    expect(row.projectKnown).toBe(false)
    expect(row.projectLabel).toBe('not-in-registry')
  })

  it('an execution state the model does not know is UNKNOWN, not silently active', () => {
    const snap = mkSnap({
      executions: [mkExecution({ executionId: 'ex-?', state: 'SOMETHING_NEW' as never })],
    })
    const summary = buildHudSessions(snap)
    expect(summary.rows[0].state).toBe('UNKNOWN')
    expect(summary.unknown).toBe(1)
    expect(summary.active).toBe(0)
  })

  it('with no snapshot there are no rows and no counts', () => {
    const summary = buildHudSessions(null)
    expect(summary).toMatchObject({ rows: [], total: 0, waiting: 0, active: 0 })
  })

  it('session delta needs two observations; one point is not a trend', () => {
    const one: TokenSample[] = [{ revision: 11, total: 100 }]
    expect(sessionTokenDelta(one)).toBeNull()
    expect(sessionTokenDelta([])).toBeNull()
    expect(sessionTokenDelta([...one, { revision: 12, total: 250 }])).toBe(150)
  })
})

describe('fusion read model · waits', () => {
  it('counts execution waits, keeps plan approvals separate, and drops closed plan rows', () => {
    const snap = mkSnap({
      executions: [
        mkExecution({ executionId: 'ex-a', state: 'WAITING_APPROVAL' }),
        mkExecution({ executionId: 'ex-q', state: 'WAITING_USER' }),
        mkExecution({ executionId: 'ex-r', state: 'RUNNING' }),
      ],
      workspace: {
        plan: {
          approvals: [
            { label: 'rollout A', state: 'PENDING' },
            { label: 'rollout B', state: 'DEFERRED', detail: 'waiting on owner' },
            { label: 'rollout C', state: 'APPROVED' },
          ],
        },
      },
    })
    const approvals = buildHudApprovals(snap)
    expect(approvals.count).toBe(2)
    expect(approvals.waiting.map((r) => r.executionId)).toEqual(['ex-a'])
    expect(approvals.questions.map((r) => r.executionId)).toEqual(['ex-q'])
    expect(approvals.planPresent).toBe(true)
    expect(approvals.plan.map((p) => p.label)).toEqual(['rollout A', 'rollout B'])
    // The plan rows are not permission requests and never inflate the badge.
    expect(approvals.count).not.toBe(approvals.plan.length + 2)
  })

  it('an absent plan key is reported as absent, not as an empty list', () => {
    const absent = buildHudApprovals(mkSnap())
    expect(absent.planPresent).toBe(false)
    expect(absent.plan).toEqual([])
    const empty = buildHudApprovals(mkSnap({ workspace: { plan: { approvals: [] } } }))
    expect(empty.planPresent).toBe(true)
    expect(empty.plan).toEqual([])
  })

  it('a malformed plan row gets a visible placeholder label, not an empty row', () => {
    const approvals = buildHudApprovals(mkSnap({
      workspace: { plan: { approvals: [{ state: 'PENDING' }] } },
    }))
    expect(approvals.plan[0].label).toBe('(未命名事项)')
  })

  it('accepts only the known tab words', () => {
    expect(hudTabFromParam('sessions')).toBe('sessions')
    expect(hudTabFromParam('approvals')).toBe('approvals')
    expect(hudTabFromParam('usage')).toBe('usage')
    expect(hudTabFromParam('anything')).toBe('usage')
    expect(hudTabFromParam(null)).toBe('usage')
  })
})

describe('CompactHUD fusion rendering', () => {
  function waitingSnap() {
    return mkSnap({
      executions: [
        mkExecution({ executionId: 'ex-run', state: 'RUNNING', anchorProjectId: 'work-lab', agent: 'codex', workingArea: 'apps/observer' }),
        mkExecution({ executionId: 'ex-approve', state: 'WAITING_APPROVAL', anchorProjectId: 'work-lab', agent: 'codex', workingArea: 'apps/observer' }),
        mkExecution({ executionId: 'ex-ask', state: 'WAITING_USER', anchorProjectId: 'design-lab', agent: 'hermes', workingArea: 'specs' }),
      ],
      workspace: {
        plan: { approvals: [{ label: 'rollout A', state: 'PENDING' }] },
      },
    })
  }

  it('offers the three segmented views, with the waiting count on the badge', () => {
    const { container } = render(<CompactHUD snap={waitingSnap()} live={true} />)
    const tabs = screen.getAllByRole('tab').map((t) => t.textContent)
    expect(tabs).toEqual(['用量', '会话3', '审批2'])
    expect(container.querySelector('.hud-notch-badge')?.textContent).toBe('2')
    expect(container.querySelector('.compact-hud')?.getAttribute('data-attention')).toBe('true')
    // Usage is active; the other lanes are mounted but hidden.
    expect(container.querySelector('.hud-view:not([hidden])')?.getAttribute('data-view')).toBe('usage')
    expect(container.querySelectorAll('.hud-view[hidden]')).toHaveLength(2)
  })

  it('mounts every panel so each tab\'s aria-controls names a real element', () => {
    const { container } = render(<CompactHUD snap={waitingSnap()} live={true} />)
    for (const tab of screen.getAllByRole('tab')) {
      const id = tab.getAttribute('aria-controls')
      expect(id, `tab ${tab.textContent} has no aria-controls`).toBeTruthy()
      expect(container.querySelector('#' + id)).not.toBeNull()
    }
    // The inactive panels must leave layout, not merely be styled away.
    const hiddenPanel = container.querySelector('.hud-view[data-view="sessions"]') as HTMLElement
    expect(hiddenPanel.hidden).toBe(true)
  })

  it('no waiting means no badge and no attention glow', () => {
    const { container } = render(<CompactHUD snap={mkSnap()} live={true} />)
    expect(container.querySelector('.hud-notch-badge')).toBeNull()
    expect(container.querySelector('.compact-hud')?.getAttribute('data-attention')).toBe('false')
  })

  it('the sessions view lists executions in state priority order and declares its gaps', () => {
    const { container } = render(<CompactHUD snap={waitingSnap()} live={true} />)
    fireEvent.click(screen.getByRole('tab', { name: /会话/ }))
    const rows = [...container.querySelectorAll('.hud-session')]
    expect(rows).toHaveLength(3)
    expect(rows[0].getAttribute('data-state')).toBe('WAITING_APPROVAL')
    expect(rows[1].getAttribute('data-state')).toBe('WAITING_USER')
    expect(rows[2].getAttribute('data-state')).toBe('RUNNING')
    expect(rows[0].textContent).toContain('WORK-LAB')
    expect(rows[0].textContent).toContain('等待批准')
    expect(rows[1].textContent).toContain('DESIGN-LAB')
    // The reference HUD shows per-session tokens and elapsed time; v3 has
    // neither, and the lane must say so rather than print placeholders.
    expect(container.textContent).toContain('不显示每会话用量与耗时')
  })

  it('an empty executions list is "not recorded", not "nothing ran"', () => {
    const { container } = render(<CompactHUD snap={mkSnap()} live={true} />)
    fireEvent.click(screen.getByRole('tab', { name: /会话/ }))
    expect(container.querySelectorAll('.hud-session')).toHaveLength(0)
    expect(container.textContent).toContain('不等于 agent 没有运行')
  })

  it('the approvals view separates execution waits from plan approvals and is read-only', () => {
    const { container } = render(<CompactHUD snap={waitingSnap()} live={true} />)
    fireEvent.click(screen.getByRole('tab', { name: /审批/ }))

    const cards = [...container.querySelectorAll('.hud-approval')]
    expect(cards).toHaveLength(2)
    expect(cards[0].getAttribute('data-kind')).toBe('approval')
    expect(cards[1].getAttribute('data-kind')).toBe('question')
    expect(cards[0].textContent).toContain('Observer 只读投影')

    const planRows = [...container.querySelectorAll('.hud-plan-list li')]
    expect(planRows).toHaveLength(1)
    expect(planRows[0].textContent).toContain('rollout A')
    expect(planRows[0].textContent).toContain('PENDING')
    expect(container.textContent).toContain('不是 agent 权限请求')

    // Read-only contract: the lane offers no action control at all.
    expect(screen.queryByRole('button', { name: /批准|拒绝|允许|deny|allow/i })).toBeNull()
    const buttons = [...container.querySelectorAll('.hud-view[data-view="approvals"] button')]
    expect(buttons).toHaveLength(0)
  })

  it('with no waits the approvals view says which condition is empty', () => {
    const { container } = render(<CompactHUD snap={mkSnap()} live={true} />)
    fireEvent.click(screen.getByRole('tab', { name: /审批/ }))
    expect(container.textContent).toContain('没有 WAITING_APPROVAL / WAITING_USER')
    // planPresent=false is a different answer from an empty list.
    expect(container.textContent).toContain('workspace.plan.approvals 缺失')
  })

  it('the usage view names the lanes the snapshot cannot fill', () => {
    const { container } = render(<CompactHUD snap={waitingSnap()} live={true} />)
    expect(container.textContent).toContain('无真值')
    expect(container.textContent).toContain('不把缺失画成低活跃')
    expect(container.querySelector('.hud-spark-svg')).toBeNull()
  })

  it('selecting a source card shows its split and persists the selection in the URL', () => {
    const snap = mkSnap({
      projects: [
        mkProject({ projectId: 'a', displayName: 'A', agentPlatform: 'codex', token: token({ input: 60, output: 30, total: 100 }) }),
        mkProject({ projectId: 'b', displayName: 'B', agentPlatform: 'hermes', token: token({ input: 20, output: 10, total: 50 }) }),
      ],
    })
    const { container } = render(<CompactHUD snap={snap} live={true} />)
    expect(container.querySelector('.hud-detail-name')?.textContent).toContain('codex')

    fireEvent.click(container.querySelector('.hud-agent[data-provider="hermes"]') as HTMLElement)
    expect(container.querySelector('.hud-detail-name')?.textContent).toContain('hermes')
    // The selected card carries the pressed state for assistive tech.
    expect(container.querySelector('.hud-agent[data-provider="hermes"]')?.getAttribute('aria-pressed')).toBe('true')
    expect(new URLSearchParams(window.location.search).get('agent')).toBe('hermes')
  })

  it('deep-links the active view from the URL and clears it when usage is chosen', () => {
    window.history.replaceState(null, '', '/?hud=sessions')
    const { container } = render(<CompactHUD snap={waitingSnap()} live={true} />)
    expect(container.querySelector('.hud-view:not([hidden])')?.getAttribute('data-view')).toBe('sessions')

    fireEvent.click(screen.getByRole('tab', { name: '用量' }))
    expect(container.querySelector('.hud-view:not([hidden])')?.getAttribute('data-view')).toBe('usage')
    expect(new URLSearchParams(window.location.search).get('hud')).toBeNull()
  })

  it('moves the tab selection with the arrow keys', () => {
    render(<CompactHUD snap={waitingSnap()} live={true} />)
    const usage = screen.getByRole('tab', { name: '用量' })
    usage.focus()
    fireEvent.keyDown(usage, { key: 'ArrowRight' })
    expect(screen.getByRole('tab', { name: /会话/ }).getAttribute('aria-selected')).toBe('true')
    expect(document.activeElement).toBe(screen.getByRole('tab', { name: /会话/ }))
  })

  it('a source with no reported split says so instead of drawing a zero remainder', () => {
    const snap = mkSnap({
      projects: [mkProject({ agentPlatform: 'codex', token: token({ input: null, output: null, total: 500 }) })],
    })
    const { container } = render(<CompactHUD snap={snap} live={true} />)
    const bar = container.querySelector('.hud-agent-bar')
    expect(bar?.getAttribute('data-known')).toBe('false')
    expect(bar?.children).toHaveLength(0)
    expect(container.textContent).toContain('未分类保持不可计算')
  })
})
