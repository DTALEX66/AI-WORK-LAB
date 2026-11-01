// WUI-08 · the migration chain's own truth rules, tested without a DOM.
//
// The tests here are the negative half of the slice: a chain that lets a strong source evaluation advance a
// downstream step is exactly the lie the taskpack names (源成功不代替目标成功), so the strongest card in the
// suite is the one used to prove the downstream steps stay NOT_PROJECTED.
import { describe, expect, it } from 'vitest'
import { MIGRATION_STAGES, chainCounts, migrationChain } from '@/lib/capabilityMigration'
import type { AdapterCapabilityCard, CapabilityLayer, CapabilityLayerState } from '@/types'

const LAYERS: CapabilityLayer[] = ['REGISTERED', 'INSTALLED', 'LOADED_CONNECTED', 'QUALIFIED',
                                  'ENABLED_FOR_TASK', 'NATIVE_PROJECTION', 'OBSERVED_IN_EXECUTION']

function ladder(state: CapabilityLayerState['state'], evidence: CapabilityLayerState['evidenceLevel'])
  : CapabilityLayerState[] {
  return LAYERS.map((layer) => ({
    layer, state, evidenceLevel: evidence, source: state === 'MET' ? 'probe://x' : null, reason: 'test fixture',
  }))
}

function mkCard(over: Partial<AdapterCapabilityCard> = {}): AdapterCapabilityCard {
  return {
    clientId: 'codex', displayName: 'Codex', supportLevel: 'MANAGE',
    declaredOperations: ['apply'], matrixOperations: ['apply'], operationsDrift: false,
    registryStatus: 'ACTIVE', writePolicy: 'apply_supported=false', risk: 'LOW',
    runtimeAdapter: null, configOwnershipDefault: { layer: 'USER_GLOBAL', mode: 'OBSERVE' },
    declaredVersion: '1.2.3', versionReadbackMethod: 'version', versionObservedAt: null,
    versionSource: null, detectionMode: 'registry', detectionEvidenceState: 'INTEGRATED',
    protocolConformance: {}, observedAt: null, layers: ladder('MET', 'REAL'),
    nativeStatus: 'NATIVELY_VERIFIED', ...over,
  }
}

describe('capabilityMigration', () => {
  it('always answers with the six contracted steps, in order', () => {
    const ids = migrationChain(mkCard()).map((stage) => stage.id)
    expect(ids).toEqual(MIGRATION_STAGES.map((stage) => stage.id))
    expect(new Set(ids).size).toBe(6)
  })

  it('a fully verified source does not advance a single downstream step', () => {
    // The card here is the strongest one expressible: every layer MET at REAL evidence and
    // NATIVELY_VERIFIED. If any downstream step moves, the projection has started borrowing the source's
    // success for the target's verdict.
    const stages = migrationChain(mkCard({ layers: ladder('MET', 'REAL'), nativeStatus: 'NATIVELY_VERIFIED' }))
    const byId = new Map(stages.map((stage) => [stage.id, stage]))
    expect(byId.get('sourceEvaluation')?.state).toBe('PROJECTED')
    for (const id of ['targetChosen', 'differenceLoss', 'isolatedTrial', 'targetVerification'] as const) {
      expect(byId.get(id)?.state, `${id} advanced on source-side success`).toBe('NOT_PROJECTED')
    }
    const counts = chainCounts(stages)
    expect(counts).toEqual({ projected: 2, notProjected: 4 })
  })

  it('names an owning producer for every gap and never a fake zero', () => {
    for (const stage of migrationChain(mkCard())) {
      expect(stage.owner.length, `${stage.id} has no owner`).toBeGreaterThan(4)
      expect(stage.basis.length, `${stage.id} has no basis`).toBeGreaterThan(3)
      expect(stage.detail).not.toMatch(/未开始|已完成 0|0 项|失败 0/)
      if (stage.state === 'NOT_PROJECTED') {
        // "no producer emitted this" must stay a statement about the projection, not about the world.
        expect(stage.detail).toMatch(/没有|未|无从|需要/)
      }
    }
  })

  it('keeps the write policy as the only reachable part of the last step', () => {
    const observe = migrationChain(mkCard({ configOwnershipDefault: { mode: 'OBSERVE' } }))
                     .find((stage) => stage.id === 'deployReadback')
    expect(observe?.detail).toContain('只观察，不写入')
    const writable = migrationChain(mkCard({ configOwnershipDefault: { mode: 'MANAGE' }, writePolicy: 'apply_supported=true' }))
                       .find((stage) => stage.id === 'deployReadback')
    expect(writable?.detail).toContain('目标侧验证读回')
    expect(writable?.detail).not.toContain('已部署')
  })

  it('reports the whole chain as unjudgeable when the source cards are absent', () => {
    const stages = migrationChain(null)
    expect(stages).toHaveLength(6)
    expect(stages.every((stage) => stage.state === 'NOT_PROJECTED')).toBe(true)
    expect(stages[0].detail).toContain('能力卡未投影')
    expect(chainCounts(stages).projected).toBe(0)
  })

  it('carries the ladder it renders, so the two sections cannot disagree', () => {
    const mixed = ladder('NOT_PROBED', 'NO_EVIDENCE').map((row, index) =>
      (index < 2 ? { ...row, state: 'MET' as const, evidenceLevel: 'INTEGRATED' as const } : row))
    const card = mkCard({ layers: mixed })
    const detail = migrationChain(card).find((stage) => stage.id === 'sourceEvaluation')?.detail ?? ''
    expect(detail).toContain('2 / 7 层')
    expect(detail).toContain('最高到 INSTALLED')
    expect(detail).toContain('NATIVELY_VERIFIED')
  })
})
