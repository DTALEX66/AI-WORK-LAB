/**
 * CL-07 · `IssueCenter` under React 18 StrictMode.
 *
 * `main.tsx` mounts the whole app inside `<React.StrictMode>`, and in a development build React 18 runs
 * every effect setup -> cleanup -> setup. The panel gated its two click-driven async continuations on a
 * component-scope `useRef(true)` whose effect only ever returned a cleanup that set the flag to `false`
 * and never re-armed it. After the second setup the flag stayed `false` for the life of a live component,
 * so `loadProject` bailed after its await and `copyPack` swallowed its confirmation. The issue LIST still
 * painted, because it renders from the `snap.issues` prop — which is why the symptom is "the handoff
 * preview hangs on 正在读取投影…", not "the panel is empty". A production build does not double-invoke, so
 * this is a dev-only defect; these tests pin the dev behavior the shipped app actually runs in.
 *
 * What each case proves:
 *   1. the control — the list paints under StrictMode, so a green run here says nothing about the defect
 *      and a red run elsewhere cannot be blamed on "the whole panel is broken";
 *   2. the click path resolves under StrictMode, and the copy confirmation still renders (both guards);
 *   3. every remount re-arms: a fix that armed the flag only once would survive case 2 and die here.
 *
 * Assertions are scoped to the element or data-testid under test, never to page-wide prose matches, so a
 * string in this file's own comments cannot satisfy an assertion.
 */
import * as React from 'react'
import { describe, it, expect, afterEach, vi } from 'vitest'
import { render, cleanup, waitFor, fireEvent, type RenderResult } from '@testing-library/react'

import { IssueCenter } from '@/views/IssueCenter'
import { mkSnap } from '@/test/snapshotFixture'
import type { IssueRecord, IssuesSummary, SnapshotV3 } from '@/types'
import type {
  ManualRepairPack, RepairPackReader, RepairPacksOutcome, RepairPacksView,
} from '@/lib/repairPack'

afterEach(() => {
  cleanup()
  vi.restoreAllMocks()
})

/** The placeholder the panel prints while the projection read is in flight (`IssueCenter.tsx:286`). */
const LOADING_TEXT = '正在读取投影'

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
    verification: {
      known: true,
      command: 'python services/orchestration/run_quality_gate.py verify',
      basis: 'target root 实测存在',
    },
    handoff: {
      mode: 'manual-copy', copyable: true, sent: false, dispatched: false,
      requiresOwnerAction: '把本材料复制给你选择的任意工具执行；复制不等于发送',
    },
    handoffText: '# 修复任务包 rp-work-lab-manual-abc123\n\n- 状态：`WAITING_APPROVAL`（未发送、未执行）\n',
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

function mkSnapWithIssues(over: Partial<SnapshotV3> = {}): SnapshotV3 {
  return mkSnap({ issues: [ISSUE], issuesSummary: mkSummary(), ...over })
}

/** The reader is always injected: the panel stays read-only and no test needs a live sidecar. */
function readerReturning(outcome: RepairPacksOutcome): RepairPackReader {
  return vi.fn(async () => outcome)
}

function strict(snap: SnapshotV3, reader: RepairPackReader) {
  return (
    <React.StrictMode>
      <IssueCenter snap={snap} reader={reader} />
    </React.StrictMode>
  )
}

function clipboardStub() {
  const writeText = vi.fn(async () => undefined)
  Object.defineProperty(navigator, 'clipboard', {
    value: { writeText }, configurable: true,
  })
  return writeText
}

/** Click the handoff action of the first projected row and prove the preview reaches a terminal state. */
async function resolveHandoff(view: RenderResult, reader: RepairPackReader) {
  const button = view.getByTestId('issue-handoff-button')
  expect(button.textContent, 'the handoff action lost its label').toContain('准备交接材料')
  fireEvent.click(button)

  // Bounded so a hung preview fails inside the test instead of inheriting the runner-wide timeout.
  await waitFor(
    () => {
      const preview = view.getByTestId('handoff-preview')
      // Scoped to the preview element: the loading placeholder is a `<p>` inside it, so its removal is
      // provable without any page-wide prose match.
      expect(preview.textContent, 'the loading placeholder is still on screen').not.toContain(LOADING_TEXT)
      expect(preview.querySelector('[data-testid="handoff-pack"]'), 'the pack never rendered')
        .not.toBeNull()
    },
    { timeout: 2000, interval: 10 },
  )

  expect(reader, 'the click fired no projection read, so the guard bailed before it').toHaveBeenCalledTimes(1)
}

describe('CL-07 · StrictMode keeps a live IssueCenter able to read', () => {
  it('control: the issue list still paints under StrictMode (the defect never hid the list)', () => {
    const reader = readerReturning({
      kind: 'RESULT', httpStatus: 200, view: mkView(),
      endpoint: 'http://127.0.0.1:61867/api/v1/repair-packs',
    })
    const { container, getAllByTestId } = render(strict(mkSnapWithIssues(), reader))
    expect(getAllByTestId('issue-row')).toHaveLength(1)
    expect(container.querySelector('[data-testid="issue-scope"]')).not.toBeNull()
    expect(container.querySelector('[data-testid="handoff-preview"]'),
      'a preview appeared before any click').toBeNull()
  })

  it('the click path resolves under StrictMode and the copy confirmation still renders', async () => {
    const writeText = clipboardStub()
    const setItem = vi.spyOn(Storage.prototype, 'setItem')
    const reader = readerReturning({
      kind: 'RESULT', httpStatus: 200, view: mkView(),
      endpoint: 'http://127.0.0.1:61867/api/v1/repair-packs',
    })
    const view = render(strict(mkSnapWithIssues(), reader))

    await resolveHandoff(view, reader)

    const pack = view.getByTestId('handoff-pack')
    const copyButton = Array.from(pack.querySelectorAll('button'))
      .find((node) => (node.textContent || '').includes('复制交接材料'))
    expect(copyButton, 'the pack rendered without its copy action').toBeDefined()
    fireEvent.click(copyButton!)

    await waitFor(
      () => {
        const state = view.queryByTestId('copy-state')
        expect(state, 'the copy confirmation was swallowed').not.toBeNull()
      },
      { timeout: 2000, interval: 10 },
    )
    expect(writeText).toHaveBeenCalledTimes(1)
    // A successful copy must not rewrite the draft into something that looks delivered.
    expect(view.getByTestId('handoff-draft-state').textContent).toContain('未发送、未执行')
    // Read-only and URL-only: this surface may not persist anything to web storage.
    expect(setItem, 'the panel wrote state into web storage').not.toHaveBeenCalled()
    setItem.mockRestore()
  })

  it('every remount re-arms the flag: three StrictMode mounts in one container all resolve', async () => {
    const outcome: RepairPacksOutcome = {
      kind: 'RESULT', httpStatus: 200, view: mkView(),
      endpoint: 'http://127.0.0.1:61867/api/v1/repair-packs',
    }
    const snap = mkSnapWithIssues()
    const { container } = render(strict(snap, readerReturning(outcome)))
    cleanup()

    for (let cycle = 1; cycle <= 3; cycle += 1) {
      const reader = readerReturning(outcome)
      // Same container every cycle: a flag that went stale across a real unmount/mount is convicted here.
      const view = render(strict(snap, reader), { container })
      await resolveHandoff(view, reader)
      cleanup()
    }
  })
})
