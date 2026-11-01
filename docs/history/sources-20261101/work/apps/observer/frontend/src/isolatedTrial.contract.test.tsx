/** WUI-21 — the isolated-trial pages, read through the rules the pack states word for word.
 *
 * The rules being enforced here are the ones a UI is most likely to break:
 *   · a stage without a basis can never be summarised into a friendly verdict;
 *   · 超时只写「未知或超时」 — UNKNOWN_OR_TIMEOUT is not FAILED and not PASSED;
 *   · 「生产者未投影」 and 「已查询 · 无记录」 are two different sentences;
 *   · the surface carries no control at all, because the Observer is read-only and a retry button
 *     here would be a write affordance wearing a report's face;
 *   · nothing is padded to a zero before the first snapshot arrives.
 */
import { describe, it, expect, afterEach } from 'vitest'
import { render, cleanup } from '@testing-library/react'

import { TrialPlanView, TrialFailureView, TrialReadbackView } from '@/views/IsolatedTrialView'
import { mkSnap } from '@/test/snapshotFixture'
import type { IsolatedTrialRecord, OperationProgressRecord } from '@/types'

afterEach(cleanup)

const NO_PRODUCER_STAGE = { status: 'UNKNOWN', basis: 'NO_PRODUCER', note: '' }
const TIMEOUT_PROGRESS: OperationProgressRecord = {
  schema_version: 'worklab/operation-progress/v1',
  task_id: 't-timeout',
  observed_at: '2026-10-12T00:00:00Z',
  state: 'UNKNOWN_OR_TIMEOUT',
  ledger_status: 'RUNNING',
  last_trusted_progress: { state: null, at: '2026-10-11T23:00:00Z', basis: 'LEDGER_HEARTBEAT' },
  transport_state: 'LIVE',
  producer_gaps: ['TARGET_BEHAVIOUR_CONFIRMATION'],
  target_behaviour: null,
}

const TRIAL: IsolatedTrialRecord = {
  schema_version: 'worklab/isolated-trial/v1',
  trial_id: 'p1.trial.c1',
  parent_task_id: 'p1',
  child_task_id: 'c1',
  observed_at: '2026-10-12T00:00:00Z',
  isolation: { basis: 'WORKTREE_ID', value: 'wt-9' },
  separated_results: {
    write: { status: 'PASSED', basis: 'LEDGER_STATE', note: '子任务账本状态为 COMPLETED。' },
    native_readback: NO_PRODUCER_STAGE,
    target_behaviour: { status: 'PENDING', basis: 'NO_PRODUCER', note: '外部效应核对状态为 PENDING。' },
  },
  producer_gaps: ['NATIVE_READBACK', 'TARGET_BEHAVIOUR_CONFIRMATION'],
}

function snapWith(over: Record<string, unknown>) {
  return mkSnap(over as never) as unknown as { [k: string]: unknown }
}

const scenes = [
  ['方案', TrialPlanView as (p: { snap: never }) => JSX.Element],
  ['失败', TrialFailureView as (p: { snap: never }) => JSX.Element],
  ['读回', TrialReadbackView as (p: { snap: never }) => JSX.Element],
] as const

describe('isolated trial scenes', () => {
  it.each(scenes)('%s: with no snapshot the pages say so and fabricate nothing', (_name, View) => {
    const { container } = render(<View snap={null as never} />)
    expect(container.textContent).toContain('生产者未投影')
    const zeros = Array.from(container.querySelectorAll('.kpi strong, .metric-box strong, .kpi-number'))
      .map((el) => (el.textContent || '').trim())
      .filter((t) => /^0(\/0)?$/.test(t))
    expect(zeros).toEqual([])
  })

  it.each(scenes)('%s: an empty projected section is not the same sentence as a missing one', (_name, View) => {
    const { container } = render(<View snap={snapWith({ operationProgress: [], isolatedTrials: [] }) as never} />)
    expect(container.textContent).toContain('已查询 · 无记录')
    expect(container.textContent).not.toContain('生产者未投影')
  })

  it.each(scenes)('%s: the surface carries no control', (_name, View) => {
    const { container } = render(
      <View snap={snapWith({ operationProgress: [TIMEOUT_PROGRESS], isolatedTrials: [TRIAL] }) as never} />,
    )
    expect(container.querySelectorAll('button, input, select, textarea')).toHaveLength(0)
  })
})

describe('stage honesty', () => {
  it('a NO_PRODUCER stage is printed with its basis, never as a bare verdict', () => {
    const { container } = render(
      <TrialReadbackView snap={snapWith({ isolatedTrials: [TRIAL] }) as never} />,
    )
    const stage = container.querySelector('[data-trial-stage="native_readback"]')
    expect(stage?.textContent).toContain('NO_PRODUCER')
    // The page must not print a success word for a stage nothing observed.
    expect(container.textContent).not.toContain('试用通过')
  })

  it('UNKNOWN_OR_TIMEOUT stays its own word and keeps the ledger status beside it', () => {
    const { container } = render(
      <TrialFailureView snap={snapWith({ operationProgress: [TIMEOUT_PROGRESS] }) as never} />,
    )
    const state = container.querySelector('[data-progress-state="UNKNOWN_OR_TIMEOUT"]')
    expect(state).not.toBeNull()
    expect(container.textContent).toContain('账本 RUNNING')
    expect(container.textContent).not.toContain('FAILED')
  })

  it('the three separated stages are printed separately, with no aggregate verdict', () => {
    const { container } = render(
      <TrialReadbackView snap={snapWith({ isolatedTrials: [TRIAL] }) as never} />,
    )
    for (const stage of ['write', 'native_readback', 'target_behaviour']) {
      expect(container.querySelector(`[data-trial-stage="${stage}"]`), stage).not.toBeNull()
    }
    expect(container.textContent).toContain('PASSED（LEDGER_STATE）')
    expect(container.textContent).toContain('PENDING（NO_PRODUCER）')
  })

  it('declared producer gaps are shown, not smoothed over', () => {
    const { container } = render(
      <TrialPlanView snap={snapWith({ isolatedTrials: [TRIAL] }) as never} />,
    )
    expect(container.textContent).toContain('NATIVE_READBACK')
    expect(container.textContent).toContain('TARGET_BEHAVIOUR_CONFIRMATION')
  })
})