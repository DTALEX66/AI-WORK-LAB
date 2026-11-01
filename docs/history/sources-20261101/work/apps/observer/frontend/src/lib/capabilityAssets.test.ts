// WUI-07 lib tests — pure functions, producer shapes pinned.
//
// These guard the read model before any pixel exists: the absent/empty splits, the ceiling the
// producer cannot cross, and the seven named gaps. Negative cases first-class: a helper that laundered
// an absent verbEvidence into "zero verbs" or a constant nativeStatus into a pass fails here.
import { describe, it, expect } from 'vitest'
import {
  CAPABILITY_DECLARED_SOURCES, CAPABILITY_SOURCE_GAPS, LADDER_ORDER, PRODUCER_CEILING, PROVENANCE_CLASSES,
  capabilityDeclarationsInSources, capabilityDeclarationsMissingFromSources,
  establishedFacts, groupAssetsByProvenance, workspaceSourceFacts,
} from '@/lib/capabilityAssets'
import type { AdapterCapabilityCard, AdapterVerbEvidenceRow, SnapshotV3 } from '@/types'
import { mkSnap } from '@/test/snapshotFixture'

/** A fresh card exactly as the producer makes one today: REGISTERED MET (SYNTHETIC, declared not probed),
 *  INSTALLED unprobed, layers 3–7 hardcoded NOT_PROBED, nativeStatus constant. */
export function freshCard(over: Partial<AdapterCapabilityCard> = {}): AdapterCapabilityCard {
  return {
    clientId: 'hermes', displayName: 'Hermes', supportLevel: 'deep',
    declaredOperations: ['detect', 'capabilities', 'invoke'],
    matrixOperations: ['detect', 'capabilities', 'invoke'],
    operationsDrift: false,
    registryStatus: 'active', writePolicy: 'approval_required', risk: 'high',
    runtimeAdapter: 'HermesAdapter',
    configOwnershipDefault: { layer: 'USER_OVERLAY', mode: 'MANAGE', preserve_unknown: true },
    clientNote: null,
    declaredVersion: '0.21.5+6948.gedd2476', versionReadbackMethod: 'install-stamp-readback',
    versionObservedAt: '2026-10-07', versionSource: 'install-stamp.json',
    detectionMode: 'isolated', detectionEvidenceState: 'UNVERIFIED',
    protocolConformance: { acp: 'STATIC_PASS', mcp: 'ABSENT' },
    observedAt: '2026-10-09T00:00:00Z',
    layers: [
      { layer: 'REGISTERED', state: 'MET', evidenceLevel: 'SYNTHETIC',
        source: 'config/adapter-registry.json#entries[id=hermes]',
        reason: '登记来自仓库声明文件，是声明不是探测' },
      { layer: 'INSTALLED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: '软件安装身份投影里没有该客户端的行' },
      { layer: 'LOADED_CONNECTED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: 'adapter 的 invoke/observe 动词仍返回 NOT_IMPLEMENTED' },
      { layer: 'QUALIFIED', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: '没有逐能力资格判定' },
      { layer: 'ENABLED_FOR_TASK', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: '派发未实现' },
      { layer: 'NATIVE_PROJECTION', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: '原生侧状态尚未进入 v3 快照合同' },
      { layer: 'OBSERVED_IN_EXECUTION', state: 'NOT_PROBED', evidenceLevel: 'NO_EVIDENCE', source: null,
        reason: '需要真实执行链上的 receipt/readback' },
    ],
    nativeStatus: 'NOT_IMPLEMENTED',
    ...over,
  } as AdapterCapabilityCard
}

function verbRow(over: Partial<AdapterVerbEvidenceRow> = {}): AdapterVerbEvidenceRow {
  return {
    verb: 'detect', state: 'MET', evidenceLevel: 'INTEGRATED',
    source: 'read-only version readback', reason: null, attempted: true,
    ...over,
  }
}

describe('groupAssetsByProvenance', () => {
  it('is one explicit 类别未知 group carrying every card — no class is assigned', () => {
    const cards = [freshCard(), freshCard({ clientId: 'codex', displayName: 'Codex' })]
    const groups = groupAssetsByProvenance(cards)
    expect(groups).toHaveLength(1)
    expect(groups[0].key).toBe('PROVENANCE_UNKNOWN')
    expect(groups[0].cards).toHaveLength(2)
    // the five classes never appear as a grouping key or per-card label
    for (const cls of PROVENANCE_CLASSES) {
      expect(groups.map((g) => g.key)).not.toContain(cls)
    }
    // but the reason states the question they cannot answer
    expect(groups[0].reason).toContain(PROVENANCE_CLASSES.join(' / '))
  })

  it('an empty card list groups to an empty group, never a fabricated class', () => {
    const groups = groupAssetsByProvenance([])
    expect(groups[0].cards).toHaveLength(0)
    expect(groups[0].key).toBe('PROVENANCE_UNKNOWN')
  })
})

describe('establishedFacts', () => {
  it('a fresh card establishes exactly REGISTERED — declared, not probed', () => {
    const facts = establishedFacts(freshCard())
    expect(facts.metLayers).toEqual(['REGISTERED'])
    expect(facts.highestMetLayer).toBe('REGISTERED')
    expect(facts.aboveCeilingMet).toEqual([])
    expect(facts.nativeVerified).toBe(false)
  })

  it('an INSTALLED MET is allowed (the computed layer), and nothing above it is inferred', () => {
    const card = freshCard({
      layers: freshCard().layers.map((l) =>
        l.layer === 'INSTALLED'
          ? { ...l, state: 'MET', evidenceLevel: 'INTEGRATED', source: 'apps/observer software identity projection', reason: '' }
          : l),
    })
    const facts = establishedFacts(card)
    expect(facts.metLayers).toEqual(['REGISTERED', 'INSTALLED'])
    expect(facts.highestMetLayer).toBe('INSTALLED')
    expect(facts.aboveCeilingMet).toEqual([])
  })

  it('seven answered verbs never promote a single layer', () => {
    const rows = ['detect', 'capabilities', 'plan', 'apply', 'invoke', 'observe', 'rollback']
      .map((verb) => verbRow({ verb }))
    const facts = establishedFacts(freshCard({ verbEvidence: rows }))
    expect(facts.verbsAnswered).toHaveLength(7)
    expect(facts.metLayers).toEqual(['REGISTERED'])
    expect(facts.highestMetLayer).toBe('REGISTERED')
  })

  it('the verb dimension keeps its three shapes apart: absent key ≠ empty list ≠ rows', () => {
    expect(establishedFacts(freshCard()).verbShape).toBe('ABSENT_KEY')
    expect(establishedFacts(freshCard({ verbEvidence: [] })).verbShape).toBe('EMPTY_LIST')
    expect(establishedFacts(freshCard({ verbEvidence: [verbRow()] })).verbShape).toBe('ROWS')
    // absent never reads as "declared zero" and empty never reads as "answered something"
    const absent = establishedFacts(freshCard())
    expect(absent.verbsAnswered).toEqual([])
    expect(absent.verbsDeclaredUnsupported).toEqual([])
  })

  it('splits NOT_PROBED by attempted: exercised-and-uncredited vs refused-to-run', () => {
    const facts = establishedFacts(freshCard({
      verbEvidence: [
        verbRow({ verb: 'observe', state: 'NOT_PROBED', attempted: true }),
        verbRow({ verb: 'apply', state: 'NOT_PROBED', attempted: false }),
        verbRow({ verb: 'rollback', state: 'NOT_SUPPORTED', attempted: false }),
      ],
    }))
    expect(facts.verbsAttemptedUncredited).toEqual(['observe'])
    expect(facts.verbsNeverAttempted).toEqual(['apply'])
    expect(facts.verbsDeclaredUnsupported).toEqual(['rollback'])
    expect(facts.verbsAnswered).toEqual([])
  })

  it('a MET above the producer ceiling is flagged as the anomaly it is, not dropped nor propagated', () => {
    const card = freshCard({
      layers: freshCard().layers.map((l) =>
        l.layer === 'QUALIFIED' ? { ...l, state: 'MET', evidenceLevel: 'REAL', source: 'x', reason: '' } : l),
    })
    const facts = establishedFacts(card)
    expect(facts.aboveCeilingMet).toEqual(['QUALIFIED'])
    // and the other layers keep their own projected state — no neighbour promotion in either direction
    expect(facts.metLayers).toEqual(['REGISTERED', 'QUALIFIED'])
  })

  it('nativeVerified is strict equality: only the literal NATIVELY_VERIFIED sets it', () => {
    expect(establishedFacts(freshCard({ nativeStatus: 'NOT_PROBED' })).nativeVerified).toBe(false)
    expect(establishedFacts(freshCard({ nativeStatus: 'NATIVELY_VERIFIED' })).nativeVerified).toBe(true)
  })

  it('PRODUCER_CEILING is INSTALLED and the ladder keeps its seven-step order', () => {
    expect(PRODUCER_CEILING).toBe('INSTALLED')
    expect(LADDER_ORDER).toEqual([
      'REGISTERED', 'INSTALLED', 'LOADED_CONNECTED', 'QUALIFIED',
      'ENABLED_FOR_TASK', 'NATIVE_PROJECTION', 'OBSERVED_IN_EXECUTION',
    ])
  })
})

describe('CAPABILITY_SOURCE_GAPS', () => {
  it('names all seven no-field questions with a non-empty reason each', () => {
    const keys = CAPABILITY_SOURCE_GAPS.map((g) => g.key)
    expect(keys).toEqual([
      'provenanceClass', 'licence', 'dependencies', 'applicability',
      'failureCounterExamples', 'userJudgement', 'migrationStatus',
    ])
    for (const gap of CAPABILITY_SOURCE_GAPS) {
      expect(gap.question.length).toBeGreaterThan(4)
      expect(gap.reason.length).toBeGreaterThan(8)
    }
  })

  it('the provenance gap states the five classes as the unanswered question — nothing more', () => {
    const gap = CAPABILITY_SOURCE_GAPS.find((g) => g.key === 'provenanceClass')!
    for (const cls of PROVENANCE_CLASSES) expect(gap.question).toContain(cls)
  })
})

describe('workspaceSourceFacts', () => {
  it('absent key, empty list and rows are three different answers', () => {
    expect(workspaceSourceFacts(mkSnap())).toEqual({ kind: 'ABSENT' }) // fixture workspace is {}
    expect(workspaceSourceFacts(mkSnap({ workspace: { sources: [] } }))).toEqual({ kind: 'EMPTY' })
    const facts = workspaceSourceFacts(mkSnap({
      workspace: { sources: [{ path: 'taskpacks/current/error-ledger.json', evidenceKind: 'HISTORY', loadedAt: '2026-10-09T00:00:00Z' }] },
    }))
    expect(facts.kind).toBe('ROWS')
    if (facts.kind === 'ROWS') expect(facts.rows[0].path).toBe('taskpacks/current/error-ledger.json')
  })

  it('the capability declared sources are checked by exact path, and the current allow-list shows none of them', () => {
    const ledger = workspaceSourceFacts(mkSnap({
      workspace: { sources: [
        { path: '.project/governance/generated/CURRENT_STATE.json', evidenceKind: 'STATIC_BASELINE', loadedAt: 't' },
        { path: 'taskpacks/current/error-ledger.json', evidenceKind: 'HISTORY', loadedAt: 't' },
      ] },
    }))
    expect(capabilityDeclarationsInSources(ledger)).toEqual([])
    expect(capabilityDeclarationsMissingFromSources(ledger)).toEqual([...CAPABILITY_DECLARED_SOURCES])
    const withMatrix = workspaceSourceFacts(mkSnap({
      workspace: { sources: [{ path: 'config/capability-matrix.json', evidenceKind: 'CAPABILITY', loadedAt: 't' }] },
    }))
    expect(capabilityDeclarationsInSources(withMatrix)).toEqual(['config/capability-matrix.json'])
    expect(capabilityDeclarationsMissingFromSources(withMatrix)).toEqual([
      'config/adapter-registry.json', 'config/capability-conformance.json',
    ])
  })

  it('a null snapshot is ABSENT, never an empty ledger', () => {
    expect(workspaceSourceFacts(null)).toEqual({ kind: 'ABSENT' })
  })
})
