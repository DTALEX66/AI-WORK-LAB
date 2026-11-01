/** CL-07 · the problem centre, mounted, with the four states it must keep apart.
 *
 * Fixtures are the wire shapes `issue_projection.py` and `repair_pack_projection.py` emit. The panel is
 * rendered on the real 项目监控 page (`OverviewView`) in the mount test, because a component that no lane
 * renders is not a feature.
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup, waitFor, fireEvent } from '@testing-library/react'

import { OverviewView } from '@/views/OverviewView'
import { IssueCenter } from '@/views/IssueCenter'
import { mkSnap } from '@/test/snapshotFixture'
import type { IssueRecord, IssuesSummary, SnapshotV3 } from '@/types'
import type {
  ManualRepairPack, RepairPackReader, RepairPacksOutcome, RepairPacksView,
} from '@/lib/repairPack'

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

const HANDOFF_TEXT = [
  '# 修复任务包 rp-work-lab-manual-abc123',
  '',
  '- 状态：`WAITING_APPROVAL`（等待授权，未发送、未执行）',
  '- 目标项目：work-lab',
  '- 证据：tasks:WL-900',
].join('\n')

const ISSUE: IssueRecord = {
  schemaVersion: 'workflow/issue/v1',
  fingerprint: '0123456789abcdef',
  class: 'TASK_BLOCKED',
  projectId: 'work-lab',
  subject: 'WL-900',
  origin: 'tasks',
  evidenceRef: 'tasks:WL-900',
  priority: 'P1',
  priorityRule: 'BLOCKED task 阻断闭环，按 P1 处理',
  safeToReread: true,
  firstSeenAt: '2026-10-23T01:00:00Z',
  lastSeenAt: '2026-10-23T02:00:00Z',
  occurrences: 2,
  magnitude: { status: 'BLOCKED' },
  detail: 'task=WL-900 处于 BLOCKED',
  status: 'OPEN',
  softwareId: 'codex',
  softwareVersion: '1.2.3',
  softwareVersionSource: 'discovered',
}

function mkSummary(over: Partial<IssuesSummary> = {}): IssuesSummary {
  return {
    schemaVersion: 'worklab/issues-summary/v1',
    generatedAt: '2026-10-23T02:00:00Z',
    sources: [{ source: 'tasks', state: 'read' }],
    sourcesRead: 1,
    sourcesAbsent: 0,
    rowsScanned: 12,
    distinctIssueCount: 1,
    emittedCount: 1,
    omittedCount: 0,
    foldedOccurrences: 2,
    cap: 200,
    truncated: false,
    complete: true,
    priorityCounts: { P1: 1, P2: 0, P3: 0 },
    softwareAttribution: {
      attributed: 1, unmatched: 0, ambiguous: 0, unattributable: 0,
      versionKnown: 1, identitySourceAbsent: false,
    },
    orderingKey: 'priority,lastSeenAt,fingerprint',
    ...over,
  }
}

function mkPack(over: Partial<ManualRepairPack> = {}): ManualRepairPack {
  return {
    schemaVersion: 'workflow/repair-pack/v1',
    packId: 'rp-work-lab-manual-abc123',
    generatedAt: '2026-10-23T02:01:00Z',
    status: 'WAITING_APPROVAL',
    readiness: { state: 'READY', reasons: [] },
    target: {
      kind: 'MANUAL_COPY',
      projectId: 'work-lab',
      projectName: 'WORK-LAB',
      projectRoot: 'D:/All projects/WORK-LAB',
      adapter: null,
      declaredOperations: [],
      operation: 'copy-handoff',
      routingSource: 'caller-choice',
    },
    binds: {
      issueFingerprints: [ISSUE.fingerprint],
      evidenceRefs: [ISSUE.evidenceRef],
      classes: ['TASK_BLOCKED'],
      priorities: ['P1'],
      issueCount: 1,
      softwareIds: ['codex'],
      unattributedCount: 0,
    },
    verification: { known: true, command: 'python services/orchestration/run_quality_gate.py verify',
      basis: 'target root 实测存在' },
    handoff: {
      mode: 'manual-copy', copyable: true, sent: false, dispatched: false,
      requiresOwnerAction: '把本材料复制给你选择的任意工具执行；复制不等于发送',
    },
    handoffText: HANDOFF_TEXT,
    ...over,
  }
}

function mkView(over: Partial<RepairPacksView> = {}): RepairPacksView {
  return {
    schemaVersion: 'worklab/repair-packs-view/v1',
    status: 'OK',
    reason: '已生成人工交接材料：复制不等于发送，WORK-LAB 不执行任何操作。',
    generatedAt: '2026-10-23T02:01:00Z',
    issuesSummary: mkSummary(),
    packs: [mkPack()],
    summary: {
      openIssueCount: 1, packCount: 1, refusalCount: 0, refusals: [],
      sent: false, dispatchPerformed: false,
    },
    ...over,
  }
}

const readerOf = (outcome: RepairPacksOutcome): RepairPackReader =>
  vi.fn(async () => outcome)

function snapWith(over: Partial<SnapshotV3>): SnapshotV3 {
  return mkSnap(over)
}

function clipboardStub(impl?: () => Promise<void>) {
  const writeText = vi.fn(impl ?? (async () => undefined))
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText }, configurable: true,
  })
  return writeText
}

describe('CL-07 · 问题投影的缺席 / 空 / 截断是三种说法', () => {
  it('no snapshot at all stays UNKNOWN, and never renders a zero', () => {
    const { container } = render(<IssueCenter snap={null} />)
    const text = container.textContent || ''
    expect(text).toContain('问题状态 UNKNOWN')
    expect(text).toContain('不显示 0 个问题')
  })

  it('an absent issues key is 无来源作答, not 无问题', () => {
    const { container } = render(<IssueCenter snap={snapWith({})} />)
    const text = container.textContent || ''
    expect(text).toContain('问题投影缺席（无来源作答）')
    expect(text).not.toContain('所有来源已读')
    expect(text).not.toContain('共 0 个问题')
  })

  it('an empty list with a complete scope report says 未发现问题', () => {
    const { container } = render(<IssueCenter
      snap={snapWith({ issues: [], issuesSummary: mkSummary({
        distinctIssueCount: 0, emittedCount: 0, foldedOccurrences: 0,
        priorityCounts: { P1: 0, P2: 0, P3: 0 },
        softwareAttribution: {
          attributed: 0, unmatched: 0, ambiguous: 0, unattributable: 0,
          versionKnown: 0, identitySourceAbsent: false,
        },
      }) })}
    />)
    expect(container.textContent || '').toContain('所有来源已读，未发现问题')
  })

  it('an empty list during a truncated scan is NOT read as 无问题', () => {
    const { container } = render(<IssueCenter
      snap={snapWith({ issues: [], issuesSummary: mkSummary({
        distinctIssueCount: 0, emittedCount: 0, truncated: true,
        scanTruncated: { telemetry_events: true }, complete: false,
      }) })}
    />)
    const text = container.textContent || ''
    expect(text).toContain('列表为空，但不能读成无问题')
    expect(text).not.toContain('所有来源已读')
  })
})

describe('CL-07 · a problem row carries impact / software / update / next step', () => {
  it('renders the projected facts, including a truncated-list warning', () => {
    const { container } = render(<IssueCenter
      snap={snapWith({ issues: [ISSUE], issuesSummary: mkSummary({ truncated: true, omittedCount: 3 }) })}
    />)
    const text = container.textContent || ''
    expect(text).toContain('任务受阻')
    expect(text).toContain('影响（按问题类）')
    expect(text).toContain('codex @ 1.2.3')
    expect(text).toContain('更新：')
    expect(text).toContain('证据：tasks:WL-900')
    expect(text).toContain('下一步：准备交接材料')
    expect(text).toContain('当前列表被截断')
  })

  it('an unattributed issue says 归属 UNKNOWN and offers no handoff button', () => {
    const orphan: IssueRecord = {
      ...ISSUE, projectId: null, softwareId: null, softwareVersion: null,
      softwareVersionSource: 'source-names-no-software',
    }
    const { container, queryByTestId } = render(<IssueCenter
      snap={snapWith({ issues: [orphan], issuesSummary: mkSummary() })}
    />)
    const text = container.textContent || ''
    expect(text).toContain('来源没有命名软件')
    expect(text).toContain('没有归属的问题不能生成交接包')
    expect(queryByTestId('issue-handoff-button')).toBeNull()
  })
})

describe('CL-07 · 看到问题 → 复制交接材料', () => {
  it('loads the pack, copies the exact handoff text, and still says 未发送 afterwards', async () => {
    const writeText = clipboardStub()
    const reader = readerOf({ kind: 'RESULT', view: mkView(), httpStatus: 200,
      endpoint: 'http://127.0.0.1:61867/api/v1/repair-packs' })
    const { getByTestId, getByText, queryByText } = render(<IssueCenter
      snap={snapWith({ issues: [ISSUE], issuesSummary: mkSummary() })}
      reader={reader}
    />)

    fireEvent.click(getByTestId('issue-handoff-button'))
    await waitFor(() => expect(getByTestId('handoff-pack')).toBeTruthy())
    expect(reader).toHaveBeenCalledTimes(1)
    expect(getByText(/绑定问题 1 条/)).toBeTruthy()
    expect(getByTestId('handoff-draft-state').textContent).toContain('未发送、未执行')

    fireEvent.click(getByText('复制交接材料'))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(HANDOFF_TEXT))
    expect(getByTestId('copy-state').textContent).toContain('仍未发送')
    // The draft state is not rewritten to look delivered by a successful copy.
    expect(getByTestId('handoff-draft-state').textContent).toContain('未发送、未执行')
    expect(queryByText(/自动执行/)).toBeNull()
  })

  it('a payload that claims it was sent is unreadable, never rendered as a handoff', async () => {
    const reader = readerOf({
      kind: 'BAD_PAYLOAD', httpStatus: 200,
      why: 'pack rp-work-lab-manual-abc123 声称已发送或已派发；本页面只展示未发送的草稿',
      endpoint: 'http://127.0.0.1:61867/api/v1/repair-packs',
    })
    const { getByTestId, queryByTestId, container } = render(<IssueCenter
      snap={snapWith({ issues: [ISSUE], issuesSummary: mkSummary() })}
      reader={reader}
    />)
    fireEvent.click(getByTestId('issue-handoff-button'))
    await waitFor(() => expect(container.textContent || '').toContain('交接材料响应不可读'))
    expect(queryByTestId('handoff-pack')).toBeNull()
  })

  it('a project with no pack shows the refusal reason instead of inventing material', async () => {
    const reader = readerOf({ kind: 'RESULT', httpStatus: 200,
      endpoint: 'http://127.0.0.1:61867/api/v1/repair-packs',
      view: mkView({
        status: 'NO_PACK',
        packs: [],
        summary: {
          openIssueCount: 1, packCount: 0, refusalCount: 1,
          refusals: [{ adapter: 'manual', reason: 'project-root-missing', projectId: 'work-lab' }],
        },
      }) })
    const { getByTestId, container } = render(<IssueCenter
      snap={snapWith({ issues: [ISSUE], issuesSummary: mkSummary() })}
      reader={reader}
    />)
    fireEvent.click(getByTestId('issue-handoff-button'))
    await waitFor(() => expect(getByTestId('handoff-refused')).toBeTruthy())
    expect(container.textContent || '').toContain('project-root-missing')
  })
})

describe('CL-07 · the panel is mounted on the landing page', () => {
  it('项目监控 renders 问题与交接 and the projected issue', () => {
    const { container } = render(
      <OverviewView snap={snapWith({ issues: [ISSUE], issuesSummary: mkSummary() })} source="live" live />,
    )
    const text = container.textContent || ''
    expect(text).toContain('问题与交接')
    expect(text).toContain('任务受阻')
  })
})
