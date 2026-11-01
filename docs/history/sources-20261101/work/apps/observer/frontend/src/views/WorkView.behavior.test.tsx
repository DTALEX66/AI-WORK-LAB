// D3 (2026-09-26 stage D) behavior tests for the primary Work lane.
//
// Pins the prompt's D3 discipline against the REAL v3 snapshot contract:
//   1. the `work` lane is registered and covered exactly once by the nav model
//   2. with no snapshot, WorkView shows UNKNOWN/empty markers — never a
//      fabricated "0" execution count, CI count, or task count
//   3. the Inspector shows EXPLICIT source-gap markers for every dimension
//      the v3 snapshot does not carry (Decision refs / Constraints / Next
//      action) — a gap is visible, not a blank cell or fake success
//   4. with a real snapshot, real executions + their anchor project render
//      (the closed loop: project -> execution -> state -> CI -> evidence)
//   5. WorkView is read-only: it renders no approve/dispatch/retry/rollback
//      write affordances (the Observer §8 read-only law)
import { describe, it, expect } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'
import { WorkView } from '@/views/WorkView'
import type { SnapshotV3, TaskRecord } from '@/types'
import { VIEW_REGISTRY, VIEW_BY_ID, OVERVIEW_ID } from '@/lib/viewRegistry'
import { NAV_GROUPS, knownLaneIds, isOnDefaultNav, navInvariantViolations } from '@/lib/navigation'
import { EMPTY_FOCUS, readRecordFocus, type RecordFocus } from '@/lib/recordFocus'

// Minimal real-shape v3 snapshot (only the fields WorkView reads; the rest
// of the schema is irrelevant to this projection).
function realSnap(): SnapshotV3 {
  const s = {} as unknown as SnapshotV3
  s.schemaVersion = 'workflow/snapshot/v3'
  s.revision = 7
  s.generatedAt = new Date().toISOString()
  s.sourceWatermark = null
  s.transport = {
    transportState: 'LIVE', freshnessState: 'FRESH', connectedSince: null, eventsUrl: null,
  } as SnapshotV3['transport']
  s.coverage = { numerator: 1, denominator: 1, scope: 'workflow' }
  s.governance = {
    state: 'CLEAN',
    families: {
      rules: { state: 'CLEAN', current: null, drift: 0 },
      skills: { state: 'CLEAN', current: null, drift: 0 },
      memory: { state: 'CLEAN', current: null, drift: 0 },
      adapters: { state: 'CLEAN', current: null, drift: 0 },
    },
  }
  s.workspace = {
    plan: { status: 'running', counts: { open: 2, done: 1 } },
    governance: { contracts: 37 },
    history: { totalErrors: 2, recentErrors: [{ errorId: 'ERR-089', title: 'merge gate lesson' }] },
    sources: [{ evidenceKind: 'plan' }],
  }
  s.projects = [{
    projectId: 'work-lab', displayName: 'WORK-LAB', agentPlatform: 'hermes',
    identityState: 'RESOLVED', activityState: 'ACTIVE', attentionState: 'ok',
    activeExecutionCount: 1, workingAreas: ['/repo'], visibility: 'public',
    quality: 'high', lastStrongEvidenceAt: null, repositories: [],
    git: {
      localSha: '279e80e111111111111111111111111111111111', remoteSha: null,
      matchState: 'UNVERIFIED', branch: 'main', dirtyCount: 0, observedAt: null,
      quality: null, freshness: null, sourceRef: null,
    },
    token: { inputTokens: 1000, outputTokens: 500, totalTokens: 1500, costQuality: 'UNKNOWN' },
    ci: [{
      runId: '36258547707', projectId: 'work-lab', workflow: 'wlr-060', headSha: '20f42df111111111111111111111111111111111',
      status: 'success', conclusion: 'success', sourceRef: null,
    }],
    executionIds: ['ex-1'], sourceRefs: ['git:origin/main@279e80e'],
  } as unknown as SnapshotV3['projects'][number]]
  s.executions = [{
    executionId: 'ex-1', anchorProjectId: 'work-lab', workingArea: '/repo',
    state: 'RUNNING', stateQuality: 'strong', agent: 'codex', sessionId: 'sess-9',
    sourceRef: null,
  } as unknown as SnapshotV3['executions'][number]]
  s.tasks = { open: 2, done: 1 }
  s.tokenSummary = { inputTokens: 1000, outputTokens: 500, totalTokens: 1500, costQuality: 'UNKNOWN' }
  s.git = { localSha: '279e80e11111111111111111111111111111111', remoteSha: null, ciSha: '20f42df111111111111111111111111111111111', matchState: 'MISMATCH' }
  s.ci = [s.projects[0].ci[0]]
  s.sourceRefs = ['git:origin/main@279e80e']
  return s
}

describe('D3 Work lane (read-only closed loop, honest source gaps)', () => {
  it('the work lane is registered and covered exactly once by the nav model', () => {
    expect(VIEW_BY_ID['work']).toBeDefined()
    expect(VIEW_BY_ID['work'].lane).toBe('work')
    // WUI-01 moved the grouping out of the Sidebar and re-cut the IA, so this asserts the partition
    // property rather than the old literal group count.
    expect(navInvariantViolations()).toEqual([])
    const knownIds = new Set<string>([OVERVIEW_ID, ...VIEW_REGISTRY.map((v) => v.id)])
    const flat = NAV_GROUPS.flatMap((g) => g.ids)
    // `work` is reachable (in some group) and no lane is doubled
    expect(flat.filter((id) => id === 'work')).toHaveLength(1)
    expect(new Set(flat).size).toBe(flat.length)
    expect(new Set(flat)).toEqual(new Set([...knownIds].filter(isOnDefaultNav)))
  })

  it('no snapshot -> UNKNOWN markers, never a fabricated 0 count', () => {
    render(<WorkView snap={null} />)
    // '数据源未接入' may appear in several empty-state panes — assert ≥1.
    expect(screen.getAllByText(/数据源未接入/).length).toBeGreaterThanOrEqual(1)
    // the execution pane's empty state must NOT claim "0 条" as if queried
    expect(screen.queryByText('0 条')).toBeNull()
  })

  it('the Inspector surfaces EXPLICIT source gaps for dimensions v3 does not carry', () => {
    render(<WorkView snap={null} />)
    // Decision refs / Constraints / Next action are not in the v3 snapshot ->
    // the gap marker (not a blank, not a fake value) must be visible.
    const gaps = screen.getAllByText(/来源缺口/)
    expect(gaps.length).toBeGreaterThanOrEqual(3)
  })

  it('real snapshot -> the closed loop renders project -> execution -> CI -> evidence', () => {
    const s = realSnap()
    render(<WorkView snap={s} />)
    expect(screen.getByText('ex-1')).toBeTruthy()
    // 'WORK-LAB' renders in both the execution-table anchor cell and the
    // "current projects" pane — assert presence (≥1), not single match.
    expect(screen.getAllByText('WORK-LAB').length).toBeGreaterThanOrEqual(1)
    expect(screen.getByText(/运行中/)).toBeTruthy()
    // CI real conclusion (from the snapshot, not invented)
    expect(screen.getByText('success')).toBeTruthy()
    // Context refs dimension is backed by sourceRefs -> present, not a gap
    expect(screen.getByText(/1 条证据引用/)).toBeTruthy()
  })

  it('WorkView is strictly read-only: zero interactive write affordances', () => {
    // The view is a pure read-only projection: it renders NO <button>/input/
    // textarea at all, so no approve/dispatch/retry/rollback/merge action can
    // be triggered from it (Observer §8 read-only law). Prose that merely
    // mentions those words in a "read-only note" card is allowed; controls
    // are not.
    const { container } = render(<WorkView snap={realSnap()} />)
    expect(container.innerHTML).not.toContain('<button')
    expect(container.innerHTML).not.toContain('<input')
    expect(container.innerHTML).not.toContain('<textarea')
  })
})

// P1-02 · record-level deep links on the Work lane.
//
// The lane keeps its zero-control read-only law, so a record is addressed with links. These tests pin
// the four things that separate a real deep link from a decoration: the record renders, a missing
// record says so instead of quietly showing another one, "backend never queried" is not "no tasks",
// and every href in the lane is the same-path query link the URL writer uses.
describe('P1-02 · task and execution focus', () => {
  function taskRecord(over: Partial<TaskRecord> = {}): TaskRecord {
    return {
      taskId: 'WL-777', projectId: 'work-lab', status: 'RUNNING',
      createdAt: '2026-10-08T00:00:00Z', updatedAt: '2026-10-08T00:05:00Z',
      leaseHolder: 'worker-A', leaseExpiresAt: '2026-10-08T00:10:00Z', fencingToken: 3,
      checkpointPresent: true, checkpointKeys: ['cursor', 'stage'],
      checkpointDigest: 'a'.repeat(64),
      ...over,
    }
  }
  const task = taskRecord()

  function withTasks(records: NonNullable<SnapshotV3['taskRecords']>): SnapshotV3 {
    const s = realSnap()
    s.taskRecords = records
    return s
  }

  it('a focused task renders the detail card from real fields, gaps stay gaps', () => {
    render(<WorkView snap={withTasks([task])} focus={{ taskId: 'WL-777', executionId: null }} onFocus={() => {}} />)
    expect(screen.getByText(/任务详情/)).toBeTruthy()
    expect(screen.getByText('worker-A · fence 3 · 到期 2026-10-08T00:10:00Z')).toBeTruthy()
    expect(screen.getByText(/键 cursor \/ stage/)).toBeTruthy()
    // checkpoint values never cross the boundary; the digest is what renders
    expect(screen.getByText(/digest aaaaaaaaaa/)).toBeTruthy()
    // dimensions the contract does not carry stay explicit gaps
    expect(screen.getAllByText(/来源缺口/).length).toBeGreaterThanOrEqual(6)
  })

  it('an unknown taskId says 记录不存在 and does not select another record', () => {
    const { container } = render(
      <WorkView snap={withTasks([task])} focus={{ taskId: 'WL-deleted', executionId: null }} onFocus={() => {}} />,
    )
    expect(screen.getByText('记录不存在')).toBeTruthy()
    expect(container.textContent).toContain('WL-deleted')
    expect(screen.queryByText(/任务详情/)).toBeNull()
    expect(container.textContent).not.toContain('worker-A')
  })

  it('a snapshot without taskRecords is 后端未提供, never rendered as 无任务', () => {
    render(<WorkView snap={realSnap()} focus={{ taskId: 'WL-777', executionId: null }} onFocus={() => {}} />)
    expect(screen.getByText('后端未提供')).toBeTruthy()
    expect(screen.queryByText('无任务记录')).toBeNull()
    expect(screen.queryByText('记录不存在')).toBeNull()
  })

  it('queried-and-empty is the other statement: 无任务记录', () => {
    render(<WorkView snap={withTasks([])} focus={{ taskId: null, executionId: null }} onFocus={() => {}} />)
    expect(screen.getByText(/无任务记录/)).toBeTruthy()
    expect(screen.queryByText('后端未提供')).toBeNull()
  })

  it('a rejected id is reported with its reason and is not looked up', () => {
    const { container } = render(
      <WorkView snap={withTasks([task])} focus={EMPTY_FOCUS} onFocus={() => {}}
              focusRejected={['taskId · 定位标识包含非法字符，已拒绝']} />,
    )
    expect(screen.getByText('定位被拒绝')).toBeTruthy()
    expect(container.textContent).toContain('非法字符')
    expect(screen.queryByText(/任务详情/)).toBeNull()
  })

  it('the row link is the deep link, and clicking it navigates in place instead of reloading', () => {
    const calls: RecordFocus[] = []
    const onFocus = (next: RecordFocus) => calls.push(next)
    const { container } = render(<WorkView snap={withTasks([task])} focus={EMPTY_FOCUS} onFocus={onFocus} />)
    const rowLink = Array.from(container.querySelectorAll('a'))
      .find((anchor) => (anchor.getAttribute('href') || '').includes('taskId=WL-777'))
    expect(rowLink, 'the task row must carry its own addressable link').toBeTruthy()
    expect(rowLink!.getAttribute('href')).toContain('view=work')
    fireEvent.click(rowLink!)
    expect(calls).toEqual([{ taskId: 'WL-777', executionId: null }])
  })

  it('a focused record still renders zero controls and only same-path query links', () => {
    const { container } = render(
      <WorkView snap={withTasks([task])} focus={{ taskId: 'WL-777', executionId: 'ex-1' }} onFocus={() => {}} />,
    )
    expect(container.innerHTML).not.toContain('<button')
    expect(container.innerHTML).not.toContain('<input')
    expect(container.innerHTML).not.toContain('<textarea')
    const anchors = Array.from(container.querySelectorAll('a'))
    expect(anchors.length).toBeGreaterThan(0)
    for (const anchor of anchors) {
      const href = anchor.getAttribute('href') || ''
      expect(/^\/\?view=work(&|$)/.test(href), `link escaped the lane contract: ${href}`).toBe(true)
      expect(href.startsWith('//'), `protocol-relative link is not a deep link: ${href}`).toBe(false)
    }
  })

  it('an id with a slash round-trips through the link instead of becoming another id', () => {
    const slashed = taskRecord({ taskId: 'WL.777/x' })
    const { container } = render(
      <WorkView snap={withTasks([slashed])} focus={{ taskId: 'WL.777/x', executionId: null }} onFocus={() => {}} />,
    )
    const href = Array.from(container.querySelectorAll('a')).map((a) => a.getAttribute('href')).find((h) => h && h.includes('taskId='))
    expect(href).toContain('taskId=WL.777%2Fx')
    expect(readRecordFocus('?' + href!.split('?')[1]).focus.taskId).toBe('WL.777/x')
  })
})
