// U03 (2026-10-07): the eight projection-truth contracts that lived ONLY in the
// retired static surface (`apps/observer/tests/test_projection_contract.js`)
// re-anchored to the production tree. Each title names the legacy assertion it
// replaces, so the parity matrix maps 1:1 and deleting `web/` can never delete a
// truth test with it.
//
// Port discipline: where v3 dropped a field entirely (no monetary cost, no
// subscriptionUsage), the legacy assertion is ported as the STRONGER property
// the v3 shape implies (the front must not render a currency amount at all),
// not as a claim that the old field still renders.
//
// Scope of THIS file: behavior of the production projection functions. The
// file-level halves of the same ports (typed-model drift, no embedded snapshot
// literal, no currency wording) live in
// `apps/observer/tests/test_production_surface_static_contract.js`, because the
// frontend tsconfig has no @types/node and must not scan the disk from a test.
import { describe, it, expect } from 'vitest'
import {
  fmtTokens, fmtCostQuality, fmtTimestamp, isRfc3339,
  executionsToRows, snapshotToTransportTruth, snapshotToProjectTokens,
  tokenTruth, stateTone, activityTone, loadRuntimeDescriptor,
} from '@/lib/api'
import type { SnapshotV3, Execution, Project } from '@/types'

function mkToken(over: Partial<Project['token']> = {}): Project['token'] {
  return { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN', ...over }
}

function mkSnap(over: Partial<SnapshotV3> = {}): SnapshotV3 {
  return {
    schemaVersion: 'workflow/snapshot/v3',
    revision: 7,
    generatedAt: '2026-10-07T09:12:33.421Z',
    sourceWatermark: '2026-10-07T09:12:30Z',
    transport: {
      transportState: 'LIVE', freshnessState: 'FRESH',
      connectedSince: '2026-10-07T08:00:00Z', eventsUrl: 'http://127.0.0.1:61867/api/v1/events',
    },
    coverage: { numerator: 3, denominator: 4, scope: 'collectors' },
    governance: {
      state: 'CLEAN',
      families: {
        rules: { state: 'CLEAN', current: null, drift: 0 },
        skills: { state: 'CLEAN', current: null, drift: 0 },
        memory: { state: 'UNKNOWN', current: null, drift: null },
        adapters: { state: 'CLEAN', current: null, drift: 0 },
      },
    },
    workspace: {},
    projects: [mkProject()],
    executions: [mkExec()],
    tasks: { PENDING: 2, RUNNING: 1 },
    tokenSummary: { inputTokens: 64391, outputTokens: 26821, totalTokens: 91212, costQuality: 'ESTIMATED' },
    git: { localSha: 'abc1234', remoteSha: 'abc1234', ciSha: 'abc1234', matchState: 'MATCH' },
    ci: [],
    sourceRefs: ['runs/x/evidence.json'],
    ...over,
  }
}

function mkProject(over: Partial<Project> = {}): Project {
  return {
    projectId: 'work-lab', displayName: 'WORK-LAB', agentPlatform: 'codex',
    identityState: 'RESOLVED', activityState: 'ACTIVE',
    attentionState: 'NONE', activeExecutionCount: 1, workingAreas: ['apps/observer'],
    visibility: 'LOCAL', quality: 'EXACT', lastStrongEvidenceAt: '2026-10-07T08:59:59Z',
    repositories: [],
    git: { localSha: 'abc1234', remoteSha: 'abc1234', matchState: 'MATCH', branch: 'main', dirtyCount: 0, observedAt: '2026-10-07T09:00:00Z', quality: 'EXACT', freshness: 'FRESH', sourceRef: null, sourceProjectId: 'work-lab' },
    token: mkToken({ inputTokens: 64391, outputTokens: 26821, totalTokens: 91212, costQuality: 'ESTIMATED' }),
    ci: [], executionIds: ['e1'], sourceRefs: [],
    ...over,
  }
}

function mkExec(over: Partial<Execution> = {}): Execution {
  return {
    executionId: 'e1', anchorProjectId: 'work-lab', workingArea: 'apps/observer',
    state: 'RUNNING', stateQuality: 'EXACT', agent: 'codex', sessionId: 's1', sourceRef: null,
    ...over,
  }
}

const DATE_KEY_RE = /(At|Watermark|Verified)$/

describe('U03 port — projection truth contracts re-anchored from web/ to the production tree', () => {
  it('legacy "fixture parses as valid JSON object with core keys": a v3 snapshot carries every key the front reads, with the declared type', () => {
    const snap = mkSnap()
    const CORE_KEYS = [
      'schemaVersion', 'revision', 'generatedAt', 'sourceWatermark', 'transport', 'coverage',
      'governance', 'workspace', 'projects', 'executions', 'tasks', 'tokenSummary',
      'git', 'ci', 'sourceRefs',
    ] as const
    for (const k of CORE_KEYS) expect(k in snap, `missing core key ${k}`).toBe(true)
    expect(typeof snap.schemaVersion).toBe('string')
    expect(typeof snap.revision).toBe('number')
    expect(Array.isArray(snap.projects)).toBe(true)
    expect(Array.isArray(snap.executions)).toBe(true)
    expect(Array.isArray(snap.sourceRefs)).toBe(true)
    expect(typeof snap.tasks).toBe('object')
    // `software` is the only optional top-level projection; its absence must not
    // break anything the front reads (the panel shows UNKNOWN instead of Healthy).
    expect('software' in snap).toBe(false)
    expect(() => snapshotToProjectTokens(snap)).not.toThrow()
  })

  it('legacy "inline API FIXTURE matches authoritative fixture numbers": with no injected endpoint the descriptor is the labelled non-authoritative loopback fallback, never a fabricated source', () => {
    // The legacy front hard-coded a FIXTURE; the production front has exactly one
    // data source (the sidecar endpoint) and must label the dev-preview default
    // as non-authoritative so it can never be presented as truth.
    const d = loadRuntimeDescriptor()
    expect(d.authoritative).toBe(false)
    expect(d.source).toBe('static-preview')
    expect(d.snapshotUrl).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/api\/v1\/snapshot$/)
    expect(d.eventsUrl).toMatch(/^http:\/\/127\.0\.0\.1:\d+\/api\/v1\/events$/)
  })

  it('legacy "cost shown as API estimate / USD, never as an exact bill" + "subscriptionUsage=not-metered renders as 订阅未计量, never 0": the token summary carries counts plus a quality label and nothing that could be read as a bill', () => {
    // v3 truth: tokenSummary is exactly token counts + a quality label. A missing
    // quality is UNKNOWN — never 0, never a currency figure. The file-level half
    // of this port (no currency wording anywhere) is pinned in the node suite.
    expect(Object.keys(mkSnap().tokenSummary).sort()).toEqual(
      ['costQuality', 'inputTokens', 'outputTokens', 'totalTokens'],
    )
    expect(fmtCostQuality('ESTIMATED')).toBe('ESTIMATED')
    expect(fmtCostQuality(undefined)).toBe('UNKNOWN')
    expect(fmtTokens(null)).toBe('UNKNOWN')
    const rows = snapshotToProjectTokens(mkSnap({ projects: [mkProject({ token: mkToken() })] }))
    expect(rows[0].totalTokens).toBeNull()
    expect(rows[0].costQuality).toBe('UNKNOWN')
  })

  it('legacy "all fixture dates are strict RFC3339": real dates localise, malformed ones render UNKNOWN, never "Invalid Date"', () => {
    const seen: string[] = []
    const walk = (o: unknown) => {
      if (!o || typeof o !== 'object') return
      for (const [k, v] of Object.entries(o as Record<string, unknown>)) {
        if (typeof v === 'string' && DATE_KEY_RE.test(k)) {
          seen.push(k)
          expect(isRfc3339(v), `fixture ${k}=${v} must be strict RFC3339`).toBe(true)
        } else if (v && typeof v === 'object') walk(v)
      }
    }
    walk(mkSnap())
    expect(seen.length).toBeGreaterThanOrEqual(3)

    // Calendar-invalid, wrong separator, bare epoch, non-string: all UNKNOWN.
    // `Date.parse` accepts "2026-02-30" by rolling it over to March 2, so shape
    // alone is not enough — a corrupt day must not become a plausible timestamp.
    expect(fmtTimestamp('2026-02-30T10:00:00Z')).toBe('UNKNOWN')
    expect(fmtTimestamp('2026-02-29T10:00:00Z')).toBe('UNKNOWN')
    expect(fmtTimestamp('2026-13-01T10:00:00Z')).toBe('UNKNOWN')
    expect(fmtTimestamp('2026-10-07T25:00:00Z')).toBe('UNKNOWN')
    expect(fmtTimestamp('2026-10-07T10:61:00Z')).toBe('UNKNOWN')
    expect(fmtTimestamp('2026-10-07T10:00:00+08:60')).toBe('UNKNOWN')
    expect(fmtTimestamp('2024-02-29T10:00:00Z')).not.toBe('UNKNOWN')
    expect(fmtTimestamp('2026-10-07 09:12:33')).toBe('UNKNOWN')
    expect(fmtTimestamp('1759837953000')).toBe('UNKNOWN')
    expect(fmtTimestamp('not-a-date')).toBe('UNKNOWN')
    expect(fmtTimestamp(null)).toBe('UNKNOWN')
    expect(fmtTimestamp(undefined)).toBe('UNKNOWN')
    expect(fmtTimestamp(123 as unknown as string)).toBe('UNKNOWN')

    // A real value renders — and the failure string the old code leaked is gone.
    for (const v of [fmtTimestamp('2026-10-07T09:12:33.421Z'), fmtTimestamp('2026-10-07T09:12:33+08:00'), fmtTimestamp('2026-10-07T09:12:33Z', 'time')]) {
      expect(v).not.toBe('UNKNOWN')
      expect(v).not.toMatch(/Invalid/)
    }
  })

  it('legacy "coverage has numerator/denominator/scope": the triple survives projection, a real 0 stays 0, an absent triple stays null', () => {
    const t = snapshotToTransportTruth(mkSnap())
    expect(t?.coverageNumerator).toBe(3)
    expect(t?.coverageDenominator).toBe(4)
    expect(t?.coverageScope).toBe('collectors')

    const absent = snapshotToTransportTruth(mkSnap({ coverage: { numerator: null, denominator: null, scope: null } }))
    expect(absent?.coverageNumerator).toBeNull()
    expect(absent?.coverageDenominator).toBeNull()
    expect(absent?.coverageScope).toBeNull()

    // 0/0 is a measurement (e.g. every collector failed), not missing data.
    const zero = snapshotToTransportTruth(mkSnap({ coverage: { numerator: 0, denominator: 0, scope: 'collectors' } }))
    expect(zero?.coverageNumerator).toBe(0)
    expect(zero?.coverageDenominator).toBe(0)
  })

  it('legacy "unknown/new fields are forward compatible (extra keys ignored, no crash)": extra keys at any level and unknown enum values never fabricate a positive', () => {
    const base = mkSnap()
    const ext = JSON.parse(JSON.stringify(base)) as Record<string, unknown>
    ext.futureField = { a: 1 }
    ;(ext.coverage as Record<string, unknown>).futureRatio = 0.5
    ;((ext.projects as Record<string, unknown>[])[0].token as Record<string, unknown>).someNewMetric = 12345
    ;(ext.executions as Record<string, unknown>[])[0]._newMeta = 'x'

    const rows = executionsToRows(ext as unknown as SnapshotV3)
    expect(rows).toHaveLength(1)
    expect(rows[0].totalTokens).toBe(91212)
    expect(rows[0].costQuality).toBe('ESTIMATED')
    const truth = snapshotToTransportTruth(ext as unknown as SnapshotV3)
    expect(truth?.coverageNumerator).toBe(3)
    expect(snapshotToProjectTokens(ext as unknown as SnapshotV3)).toHaveLength(1)

    // A newer sidecar state word must land in `unknown`, never in a positive tone.
    expect(stateTone('PAUSED_BY_ORCHESTRATOR' as never)).toBe('unknown')
    expect(activityTone('DECOMMISSIONED' as never)).toBe('unknown')
    expect(stateTone(undefined as never)).toBe('unknown')
  })

  it('legacy "missing required core keys degrade gracefully (no crash, partial/unknown shown)": absent nested objects degrade to UNKNOWN/null instead of throwing or 0', () => {
    const stripped = JSON.parse(JSON.stringify(mkSnap())) as Record<string, unknown>
    delete stripped.transport
    delete stripped.coverage
    delete stripped.projects
    delete stripped.executions
    delete stripped.tokenSummary
    const snap = stripped as unknown as SnapshotV3

    expect(() => snapshotToTransportTruth(snap)).not.toThrow()
    const t = snapshotToTransportTruth(snap)
    expect(t?.transportState).toBe('UNKNOWN')
    expect(t?.freshnessState).toBe('UNKNOWN')
    expect(t?.eventsUrl).toBeNull()
    expect(t?.connectedSince).toBeNull()
    expect(t?.coverageNumerator).toBeNull()
    expect(t?.revision).toBe(7)

    expect(executionsToRows(snap)).toEqual([])
    expect(snapshotToProjectTokens(snap)).toEqual([])
    expect(tokenTruth(snap)).toBeNull()
    expect(fmtTokens(tokenTruth(snap)?.totalTokens)).toBe('UNKNOWN')

    // A project without its token object still projects, as UNKNOWN.
    const noToken = mkSnap({ projects: [mkProject({ token: undefined as unknown as Project['token'] })] })
    const row = snapshotToProjectTokens(noToken)[0]
    expect(row.totalTokens).toBeNull()
    expect(row.costQuality).toBe('UNKNOWN')
    expect(executionsToRows(noToken)[0].totalTokens).toBeNull()
  })

  it('legacy "empty-new-install fixture renders (empty state, no crash, no fake success)": an empty install projects zero rows and an UNKNOWN transport', () => {
    const empty = mkSnap({
      revision: 0,
      transport: { transportState: 'UNKNOWN', freshnessState: 'UNKNOWN', connectedSince: null, eventsUrl: null },
      coverage: { numerator: null, denominator: null, scope: null },
      projects: [], executions: [], tasks: {}, sourceRefs: [],
      tokenSummary: { inputTokens: null, outputTokens: null, totalTokens: null, costQuality: 'UNKNOWN' },
    })
    expect(executionsToRows(empty)).toEqual([])
    expect(snapshotToProjectTokens(empty)).toEqual([])
    const t = snapshotToTransportTruth(empty)
    expect(t?.transportState).toBe('UNKNOWN')
    expect(t?.transportState).not.toBe('LIVE')
    expect(fmtTokens(tokenTruth(empty)?.totalTokens)).toBe('UNKNOWN')
    expect(fmtCostQuality(tokenTruth(empty)?.costQuality)).toBe('UNKNOWN')
  })
})
