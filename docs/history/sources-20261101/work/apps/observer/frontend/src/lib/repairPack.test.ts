/** CL-07 · the repair-pack client refuses any body it cannot vouch for.
 *
 * HTTP status is transport; the body is the verdict. A 200 carrying a foreign schema, a status/packs
 * contradiction, or a pack that claims it was sent is BAD_PAYLOAD — never a handoff the page may copy.
 */
import { describe, it, expect, afterEach, vi } from 'vitest'
import {
  makeHttpRepairPackReader, parseRepairPacksView, packForProject,
  REPAIR_PACKS_VIEW_SCHEMA_VERSION,
} from '@/lib/repairPack'

afterEach(() => vi.unstubAllGlobals())

const ENDPOINT = 'http://127.0.0.1:61867/api/v1/repair-packs'

function pack(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schemaVersion: 'workflow/repair-pack/v1',
    packId: 'rp-work-lab-manual-abc123',
    generatedAt: '2026-10-23T02:01:00Z',
    status: 'WAITING_APPROVAL',
    readiness: { state: 'READY', reasons: [] },
    target: { kind: 'MANUAL_COPY', projectId: 'work-lab', projectName: 'WORK-LAB',
      projectRoot: 'D:/All projects/WORK-LAB', adapter: null, declaredOperations: [],
      operation: 'copy-handoff', routingSource: 'caller-choice' },
    binds: { issueFingerprints: ['0123456789abcdef'], evidenceRefs: ['tasks:WL-900'],
      classes: ['TASK_BLOCKED'], priorities: ['P1'], issueCount: 1, softwareIds: ['codex'],
      unattributedCount: 0 },
    verification: { known: true, command: 'python services/orchestration/run_quality_gate.py verify',
      basis: 'target root 实测存在' },
    handoff: { mode: 'manual-copy', copyable: true, sent: false, dispatched: false,
      requiresOwnerAction: '复制不等于发送' },
    handoffText: '# 修复任务包\n- 证据：tasks:WL-900',
    ...over,
  }
}

function view(over: Record<string, unknown> = {}): Record<string, unknown> {
  return {
    schemaVersion: REPAIR_PACKS_VIEW_SCHEMA_VERSION,
    status: 'OK',
    reason: '已生成人工交接材料',
    generatedAt: '2026-10-23T02:01:00Z',
    issuesSummary: null,
    packs: [pack()],
    summary: { openIssueCount: 1, packCount: 1, refusals: [] },
    ...over,
  }
}

describe('parseRepairPacksView', () => {
  it('accepts the projection shape and finds the pack by project', () => {
    const parsed = parseRepairPacksView(view())
    expect(parsed.ok).toBe(true)
    if (parsed.ok) {
      expect(parsed.view.packs).toHaveLength(1)
      expect(packForProject(parsed.view, 'work-lab')?.packId).toBe('rp-work-lab-manual-abc123')
      expect(packForProject(parsed.view, 'other')).toBeNull()
    }
  })

  it('refuses a foreign schema and an unknown status', () => {
    expect(parseRepairPacksView(view({ schemaVersion: 'other/v9' })).ok).toBe(false)
    expect(parseRepairPacksView(view({ status: 'DONE', packs: [] })).ok).toBe(false)
  })

  it('refuses a body whose status and packs contradict each other', () => {
    expect(parseRepairPacksView(view({ status: 'OK', packs: [] })).ok).toBe(false)
    expect(parseRepairPacksView(view({ status: 'NO_OPEN_ISSUES', packs: [pack()] })).ok).toBe(false)
  })

  it('refuses a pack that claims it was sent, and one with no copyable text', () => {
    const sent = parseRepairPacksView(view({ packs: [pack({
      handoff: { mode: 'manual-copy', copyable: true, sent: true, dispatched: false,
        requiresOwnerAction: 'x' } })] }))
    expect(sent.ok).toBe(false)
    if (!sent.ok) expect(sent.why).toContain('已发送')
    expect(parseRepairPacksView(view({ packs: [pack({ handoffText: '' })] })).ok).toBe(false)
    expect(parseRepairPacksView(view({ packs: [pack({ binds: {} })] })).ok).toBe(false)
  })
})

describe('makeHttpRepairPackReader', () => {
  it('is a GET with no body and no-store, and a 200 with a foreign body is BAD_PAYLOAD', async () => {
    const init: Array<Record<string, unknown>> = []
    vi.stubGlobal('fetch', vi.fn(async (_url: string, options?: RequestInit) => {
      init.push({ ...(options || {}) })
      return { ok: true, status: 200, json: async () => ({ status: 'OK' }) }
    }))
    const outcome = await makeHttpRepairPackReader(ENDPOINT)()
    expect(outcome.kind).toBe('BAD_PAYLOAD')
    expect(init).toHaveLength(1)
    expect(init[0].method).toBe('GET')
    expect(init[0].cache).toBe('no-store')
    expect(init[0].body).toBeUndefined()
  })

  it('reports an unreachable endpoint as UNREACHABLE, not as a refusal', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('Failed to fetch') }))
    const outcome = await makeHttpRepairPackReader(ENDPOINT)()
    expect(outcome.kind).toBe('UNREACHABLE')
  })

  it('a valid body is a RESULT carrying the projection', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => ({ ok: true, status: 200, json: async () => view() })))
    const outcome = await makeHttpRepairPackReader(ENDPOINT)()
    expect(outcome.kind).toBe('RESULT')
    if (outcome.kind === 'RESULT') expect(outcome.view.status).toBe('OK')
  })
})
