// U07 front-truth discipline: the api.ts formatters + projections must keep
// UNKNOWN as UNKNOWN and never fabricate 0 / a monetary amount / a false
// "success". These are the pure functions that carry the whole front's truth
// discipline, so they are the highest-value behavior tests.
import { describe, it, expect, vi } from 'vitest'
import {
  fmtTokens, fmtCostQuality,
  stateTone, activityTone,
  executionsToRows, snapshotToTransportTruth,
  fetchSnapshot, SNAPSHOT_TIMEOUT_MS,
} from '@/lib/api'
import type { SnapshotV3, Execution, Project } from '@/types'

function mkSnap(over: Partial<SnapshotV3> = {}): SnapshotV3 {
  return {
    schemaVersion: 'workflow/snapshot/v3',
    revision: 0,
    generatedAt: '2026-10-08T00:00:00Z',
    sourceWatermark: null,
    transport: {
      transportState: 'UNKNOWN', freshnessState: 'UNKNOWN',
      connectedSince: null, eventsUrl: null,
    },
    coverage: { numerator: null, denominator: null, scope: null },
    governance: {
      state: 'UNKNOWN',
      families: {
        rules: { state: 'UNKNOWN', current: null, drift: null },
        skills: { state: 'UNKNOWN', current: null, drift: null },
        memory: { state: 'UNKNOWN', current: null, drift: null },
        adapters: { state: 'UNKNOWN', current: null, drift: null },
      },
    },
    workspace: {},
    projects: [],
    executions: [],
    tasks: {},
    tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
    git: { localSha: null, remoteSha: null, ciSha: null, matchState: 'NO_LOCAL_CLAIM' },
    ci: [],
    sourceRefs: [],
    ...over,
  }
}

function mkProject(over: Partial<Project> = {}): Project {
  return {
    projectId: 'work-lab', displayName: null, agentPlatform: null,
    identityState: 'UNRESOLVED', activityState: 'REGISTERED',
    attentionState: 'NONE', activeExecutionCount: 0, workingAreas: [],
    visibility: 'UNKNOWN', quality: 'UNKNOWN', lastStrongEvidenceAt: null,
    repositories: [],
    git: { localSha: null, remoteSha: null, matchState: 'NO_LOCAL_CLAIM', branch: null, dirtyCount: null, observedAt: null, quality: null, freshness: null, sourceRef: null, sourceProjectId: null },
    token: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
    ci: [], executionIds: [], sourceRefs: [],
    ...over,
  }
}

function mkExec(over: Partial<Execution> = {}): Execution {
  return {
    executionId: 'e1', anchorProjectId: 'work-lab', workingArea: null,
    state: 'UNKNOWN', stateQuality: 'UNKNOWN', agent: null, sessionId: null, sourceRef: null,
    ...over,
  }
}

describe('U07 truth formatters (no fabricated 0 / cost / success)', () => {
  it('fmtTokens: null/undefined -> UNKNOWN, never "0"', () => {
    expect(fmtTokens(null)).toBe('UNKNOWN')
    expect(fmtTokens(undefined)).toBe('UNKNOWN')
    expect(fmtTokens(1234)).toBe('1k')
    expect(fmtTokens(2_500_000)).toBe('2.50M')
  })

  it('fmtCostQuality: absent -> UNKNOWN', () => {
    expect(fmtCostQuality(null)).toBe('UNKNOWN')
    expect(fmtCostQuality(undefined)).toBe('UNKNOWN')
    expect(fmtCostQuality('EXACT')).toBe('EXACT')
  })

  it('stateTone: no silent fallthrough to a positive tone', () => {
    expect(stateTone('RUNNING')).toBe('running')
    expect(stateTone('WAITING_APPROVAL')).toBe('pending')
    expect(stateTone('BLOCKED')).toBe('blocked')
    expect(stateTone('FAILED')).toBe('failed')
    expect(stateTone('COMPLETED')).toBe('done')
    expect(stateTone('UNKNOWN')).toBe('unknown') // not "done"/"running"
  })

  it('activityTone: unknown activity is "unknown", not "active"', () => {
    expect(activityTone('ACTIVE')).toBe('active')
    expect(activityTone('UNKNOWN')).toBe('unknown')
  })
})

describe('U07 projections keep the real v3 shape honest', () => {
  it('executionsToRows: unknown project -> null tokens + UNKNOWN quality (no 0)', () => {
    const snap = mkSnap({
      projects: [], // no matching project
      executions: [mkExec({ anchorProjectId: 'work-lab' })],
    })
    const rows = executionsToRows(snap)
    expect(rows).toHaveLength(1)
    expect(rows[0].totalTokens).toBeNull()
    expect(rows[0].costQuality).toBe('UNKNOWN')
  })

  it('executionsToRows: joins anchor project for real tokens + quality', () => {
    const snap = mkSnap({
      projects: [mkProject({ token: { inputTokens: 10, outputTokens: 5, totalTokens: 15, costQuality: 'EXACT' } })],
      executions: [mkExec()],
    })
    const rows = executionsToRows(snap)
    expect(rows[0].totalTokens).toBe(15)
    expect(rows[0].costQuality).toBe('EXACT')
  })

  it('snapshotToTransportTruth: null snap -> null (no fabricated LIVE)', () => {
    expect(snapshotToTransportTruth(null)).toBeNull()
  })

  it('snapshotToTransportTruth: surfaces real transport state', () => {
    const snap = mkSnap({
      transport: { transportState: 'LIVE', freshnessState: 'FRESH', connectedSince: '2026-01-01T00:00:00Z', eventsUrl: 'http://127.0.0.1:1/api/v1/events' },
      coverage: { numerator: 3, denominator: 4, scope: 'collectors' },
    })
    const t = snapshotToTransportTruth(snap)
    expect(t?.transportState).toBe('LIVE')
    expect(t?.coverageNumerator).toBe(3)
  })
})

// ---------------------------------------------------------------------------
// W05 (2026-10-14): a snapshot GET that never answers must not freeze the read loop.
//
// The recorded defect is structural, not cosmetic: `useLiveSnapshot` already coalesces bursts with
// `inFlight`/`followUp`, so one hung request does not stampede — it freezes. `inFlight` stays true, every
// later tick only sets `followUp`, and the surface keeps its last good snapshot while still claiming to
// poll. These two cases pin the two halves of the fix at the function that owns the socket.
// ---------------------------------------------------------------------------
describe('W05 · a hung snapshot read is aborted, not merely awaited', () => {
  const ok = (body: unknown) => ({ ok: true, json: async () => body }) as Response

  it('aborts the GET at the deadline, answers null, and the next read still succeeds', async () => {
    vi.useFakeTimers()
    let aborts = 0
    const fetchMock = vi.fn((_url: RequestInfo | URL, init?: RequestInit) => {
      if (fetchMock.mock.calls.length === 1) {
        return new Promise<Response>((_res, reject) => {
          init?.signal?.addEventListener('abort', () => {
            aborts += 1
            reject(new DOMException('aborted', 'AbortError'))
          })
        })
      }
      return Promise.resolve(ok(mkSnap({ revision: 7 })))
    })
    vi.stubGlobal('fetch', fetchMock)
    try {
      const hung = fetchSnapshot()
      await vi.advanceTimersByTimeAsync(SNAPSHOT_TIMEOUT_MS + 1)
      await expect(hung).resolves.toBeNull()
      expect(aborts).toBe(1)
      const next = await fetchSnapshot()
      expect(next?.revision).toBe(7)
      expect(fetchMock).toHaveBeenCalledTimes(2)
    } finally {
      vi.unstubAllGlobals()
      vi.useRealTimers()
    }
  })

  it('forwards an outer abort, so tearing the surface down releases the socket', async () => {
    let aborts = 0
    vi.stubGlobal('fetch', vi.fn((_url: RequestInfo | URL, init?: RequestInit) =>
      new Promise<Response>((_res, reject) => {
        init?.signal?.addEventListener('abort', () => {
          aborts += 1
          reject(new DOMException('aborted', 'AbortError'))
        })
      })))
    try {
      const outer = new AbortController()
      const pending = fetchSnapshot(outer.signal)
      outer.abort()
      await expect(pending).resolves.toBeNull()
      expect(aborts).toBe(1)
    } finally {
      vi.unstubAllGlobals()
    }
  })
})
