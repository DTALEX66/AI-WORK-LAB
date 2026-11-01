// WUI-08 · the migration chain as the user actually opens it: mounted in the capabilities lane.
//
// The read model has its own unit tests; this file exists because a state matrix nobody can open is not a
// feature (that mistake was recorded before this round). So every assertion here renders the lane through the
// same registry the shell uses and asserts on the DOM: the six steps appear, the projected ones name their
// field, the unprojected ones name their owner, and the section contains no control at all — a settings
// switch or a "start migration" button in the Observer would be a write affordance wearing a read-only face.
import { describe, expect, it } from 'vitest'
import { render } from '@testing-library/react'
import React from 'react'
import { CapabilityAssetsView } from '@/views/CapabilityAssetsView'
import { MIGRATION_STAGES } from '@/lib/capabilityMigration'
import type { AdapterCapabilityCard, CapabilityLayer } from '@/types'
import { mkSnap } from '@/test/snapshotFixture'

const LAYERS: CapabilityLayer[] = ['REGISTERED', 'INSTALLED', 'LOADED_CONNECTED', 'QUALIFIED',
                                  'ENABLED_FOR_TASK', 'NATIVE_PROJECTION', 'OBSERVED_IN_EXECUTION']

function fullyVerifiedCard(): AdapterCapabilityCard {
  return {
    clientId: 'codex', displayName: 'Codex', supportLevel: 'MANAGE',
    declaredOperations: [], matrixOperations: [], operationsDrift: false,
    registryStatus: 'ACTIVE', writePolicy: 'apply_supported=false', risk: 'LOW', runtimeAdapter: null,
    configOwnershipDefault: { layer: 'USER_GLOBAL', mode: 'OBSERVE' },
    declaredVersion: null, versionReadbackMethod: null, versionObservedAt: null, versionSource: null,
    detectionMode: null, detectionEvidenceState: 'INTEGRATED', protocolConformance: {}, observedAt: null,
    layers: LAYERS.map((layer) => ({ layer, state: 'MET' as const, evidenceLevel: 'REAL' as const,
                                     source: 'probe://x', reason: 'fixture' })),
    nativeStatus: 'NATIVELY_VERIFIED',
  }
}

function renderLane(snap: Parameters<typeof CapabilityAssetsView>[0]['snap']) {
  return render(<CapabilityAssetsView snap={snap} />).container
}

describe('capability migration chain on the capabilities lane', () => {
  it('renders all six contracted steps for each card the lane shows', () => {
    const container = renderLane(mkSnap({ adapterCapabilities: [fullyVerifiedCard()] }))
    const steps = container.querySelectorAll('[data-migration-stage]')
    expect(steps).toHaveLength(MIGRATION_STAGES.length)
    expect(container.querySelector('[data-migration-chain="Codex"]')).not.toBeNull()
    for (const stage of MIGRATION_STAGES) {
      expect(container.querySelector(`[data-migration-stage="${stage.id}"]`), stage.id).not.toBeNull()
    }
  })

  it('keeps four steps unprojected even when every layer of the source is MET at REAL', () => {
    const container = renderLane(mkSnap({ adapterCapabilities: [fullyVerifiedCard()] }))
    const states = Array.from(container.querySelectorAll('[data-migration-stage]'))
                         .map((node) => [node.getAttribute('data-migration-stage'),
                                         node.getAttribute('data-stage-state')])
    const unprojected = states.filter(([, state]) => state === 'NOT_PROJECTED').map(([id]) => id)
    expect(unprojected.sort()).toEqual(['differenceLoss', 'isolatedTrial', 'targetChosen',
                                        'targetVerification'])
    // 源成功不代替目标成功: the source step is the only one that may claim anything here.
    expect(states.find(([id]) => id === 'targetVerification')?.[1]).toBe('NOT_PROJECTED')
  })

  it('names a field as the basis of a projected step and a producer as the owner of a gap', () => {
    const container = renderLane(mkSnap({ adapterCapabilities: [fullyVerifiedCard()] }))
    const source = container.querySelector('[data-migration-stage="sourceEvaluation"]')?.textContent ?? ''
    expect(source).toContain('snap.adapterCapabilities[].layers')
    expect(source).toContain('7 / 7 层')
    const trial = container.querySelector('[data-migration-stage="isolatedTrial"]')?.textContent ?? ''
    expect(trial).toContain('WUI-21')
    expect(trial).toContain('没有试用记录被投影')
  })

  it('states the write policy instead of implying a deployment, and offers nothing to click', () => {
    const container = renderLane(mkSnap({ adapterCapabilities: [fullyVerifiedCard()] }))
    const deploy = container.querySelector('[data-migration-stage="deployReadback"]')?.textContent ?? ''
    expect(deploy).toContain('只观察，不写入')
    expect(deploy).not.toMatch(/已部署|部署成功/)
    // The lane is a read-only projection: no button, no input anywhere in what this section renders.
    const controls = Array.from(container.querySelectorAll('button, input, select, textarea'))
    expect(controls.length).toBe(0)
  })

  it('shows the whole chain as unjudgeable when the lane has no cards at all', () => {
    const container = renderLane(mkSnap({ adapterCapabilities: undefined }))
    expect(container.querySelector('[data-migration-chain="absent"]')?.textContent)
      .toContain('没有能力卡可判')
    const steps = Array.from(container.querySelectorAll('[data-migration-stage]'))
    expect(steps).toHaveLength(6)
    expect(steps.every((node) => node.getAttribute('data-stage-state') === 'NOT_PROJECTED')).toBe(true)
  })
})
