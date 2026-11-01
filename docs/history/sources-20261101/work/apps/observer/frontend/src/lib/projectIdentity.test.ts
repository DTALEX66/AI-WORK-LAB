// WUI-04 · the identity module is the single place that decides what a project IS in this UI, so the
// rules it exists to enforce are tested here rather than inferred from a page render.
import { describe, it, expect } from 'vitest'

import {
  PROJECT_IDENTITY_GAPS, duplicateDisplayNames, identityKeyOf, participantsOf, workingAreaFacts,
} from './projectIdentity'
import { mkProject, mkExecution, mkSnap } from '@/test/snapshotFixture'

describe('project identity (WUI-04)', () => {
  it('keys a project by projectId and nothing else', () => {
    expect(identityKeyOf(mkProject({ projectId: 'a', displayName: 'Same' }))).toBe('a')
    expect(identityKeyOf(mkProject({ projectId: 'b', displayName: 'Same' }))).toBe('b')
  })

  it('flags a display name shared by several ids without merging the rows', () => {
    const projects = [
      mkProject({ projectId: 'a', displayName: 'Same' }),
      mkProject({ projectId: 'b', displayName: 'Same' }),
      mkProject({ projectId: 'c', displayName: 'Other' }),
      mkProject({ projectId: 'd', displayName: null }),
    ]
    const duplicates = duplicateDisplayNames(projects)
    expect([...duplicates]).toEqual(['Same'])
    // a null display name is an absence, not a collision between the nulls
    expect(duplicates.has('')).toBe(false)
    expect(duplicateDisplayNames([projects[2]])).toEqual(new Set())
  })

  it('collects participating software from the project and its own executions only', () => {
    const snap = mkSnap({
      projects: [mkProject({ projectId: 'a', agentPlatform: 'codex' })],
      executions: [
        mkExecution({ executionId: 'e1', anchorProjectId: 'a', agent: 'hermes' }),
        mkExecution({ executionId: 'e2', anchorProjectId: 'a', agent: 'hermes' }),
        mkExecution({ executionId: 'e3', anchorProjectId: 'other', agent: 'dsh' }),
        mkExecution({ executionId: 'e4', anchorProjectId: 'a', agent: null }),
      ],
    })
    expect(participantsOf(snap, snap.projects[0])).toEqual(['codex', 'hermes'])
    expect(participantsOf(null, snap.projects[0])).toEqual(['codex'])
    expect(participantsOf(snap, mkProject({ projectId: 'z', agentPlatform: null }))).toEqual([])
  })

  it('says what the projection cannot answer, and never claims to have resolved it', () => {
    const keys = PROJECT_IDENTITY_GAPS.map((gap) => gap.key)
    expect(keys).toEqual(expect.arrayContaining(
      ['repositories', 'worktree', 'conflict', 'perProjectObservation']))
    for (const gap of PROJECT_IDENTITY_GAPS) {
      expect(gap.question.trim().length).toBeGreaterThan(0)
      // a gap without a producer reason is an apology, not an explanation
      expect(gap.reason, `${gap.key} has no producer reason`).toMatch(/snapshot_api|composition_root|不|未|never|only/)
    }
  })

  it('reads an empty working-area list as an aggregated absence, not as no directory', () => {
    const facts = workingAreaFacts(mkProject({ workingAreas: [] }))
    expect(facts.areas).toEqual([])
    expect(facts.aggregatedFromExecutions).toBe(true)
  })
})
