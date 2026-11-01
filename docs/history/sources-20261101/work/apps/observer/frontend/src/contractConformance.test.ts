// WUI-15 · the seam that makes the front model consume the generated contract, checked at runtime too.
//
// `contractConformance.ts` does its work in the type system (`tsc` fails if a path stops refining), so this
// file asserts the things a type-level assertion cannot say out loud: that the inventories are populated,
// that every path they name is a key the projection actually carries, and that a real fixture value can be
// handed to the generated contract's own field types. A name in a list that no longer exists anywhere is the
// failure mode this catches -- the compile-time assertions would simply stop covering it and stay green.
import { describe, expect, it } from 'vitest'
import type { WorkflowSnapshotV3 } from '../../../../packages/client-neutral-core/generated/contracts'
import {
  GENERATED_COLLAPSED_PATHS,
  GENERATED_CONTRACT_MODULE,
  PINNED_REFINEMENT_PATHS,
} from '@/contractConformance'
import type { SnapshotV3 } from '@/types'
import { mkSnap } from '@/test/snapshotFixture'

const snap = mkSnap({})
const PATH_SHAPE = /^[a-z][\w]*(\[])?(\.[a-z][\w]*)?$/

describe('contractConformance', () => {
  it('names the generated module by the path the repository actually uses', () => {
    expect(GENERATED_CONTRACT_MODULE).toBe('packages/client-neutral-core/generated/contracts')
  })

  it('pins at least eight paths, all of them keys the projection really carries', () => {
    // A guard that pins nothing is the failure this floor exists for: `tsc` would still compile, and the
    // front model would quietly stop being checked against the generated artifact.
    expect(PINNED_REFINEMENT_PATHS.length).toBeGreaterThanOrEqual(8)
    expect(new Set(PINNED_REFINEMENT_PATHS).size).toBe(PINNED_REFINEMENT_PATHS.length)
    const keys = Object.keys(snap as unknown as Record<string, unknown>)
    // WUI-15 pins the optional sections too, and a bare fixture omits them by design. They are admitted
    // from the declared key set, which is typed `keyof SnapshotV3`, so a rename fails the compile.
    const declaredOptional: (keyof SnapshotV3)[] = ['software', 'taskRecords', 'adapterCapabilities',
                                                   'artifactHandles', 'artifactHandlesSummary',
                                                   'collectors', 'operationProgress', 'isolatedTrials',
                                                   // CL-07 pinned the problem centre once IssueCenter consumed
                                                   // both keys; absent still means no source answered.
                                                   'issues', 'issuesSummary']
    for (const path of PINNED_REFINEMENT_PATHS) {
      const present = keys.includes(path) || (declaredOptional as string[]).includes(path)
      expect(present, `pinned path ${path} is not on the projection`).toBe(true)
    }
  })

  it('lists the generated collapses as distinct, well-formed paths whose leaves exist', () => {
    // The floor tracks the generator, not a frozen number: WUI-21 (2026-10-11) added the isolated-trial
    // sections, whose `isolation` object is free-form in the contract and so one more measured collapse;
    // WUI-15 (2026-10-18) removed two because the schema now names both `ci` levels. What must hold is the
    // one-for-one equality with the generated block, and that is asserted in BOTH directions by the Python
    // gate (`tests/workflow-assistance/test_generated_contract_types_project_the_schema.py`), which reads
    // the generated text itself. Pinning an exact count here would only make the honest growth red.
    expect(GENERATED_COLLAPSED_PATHS.length).toBeGreaterThanOrEqual(6)
    expect(new Set(GENERATED_COLLAPSED_PATHS).size).toBe(GENERATED_COLLAPSED_PATHS.length)
    for (const path of GENERATED_COLLAPSED_PATHS) {
      expect(path).toMatch(PATH_SHAPE)
    }
    // The top-level ones must still be real keys; the nested ones are checked by the Python gate against
    // the generated text, which is where a collapse can only appear or disappear. Optional sections are
    // absent on a bare fixture by design, so they are admitted from the declared key set -- and that set is
    // typed as `keyof SnapshotV3`, so a rename fails the compile rather than passing quietly.
    const keys = Object.keys(snap as unknown as Record<string, unknown>)
    const declaredOptional: (keyof SnapshotV3)[] = ['software', 'taskRecords', 'adapterCapabilities',
                                                   'artifactHandles', 'artifactHandlesSummary',
                                                   'collectors', 'operationProgress', 'isolatedTrials',
                                                   // The problem centre (2026-10-22). Optional by the same rule
                                                   // as every section above: absent means no source answered.
                                                   // CL-07 renders both sections in IssueCenter and pins them,
                                                   // so this admission is about fixture shape only.
                                                   'issues', 'issuesSummary']
    for (const path of GENERATED_COLLAPSED_PATHS) {
      const head = path.split('.')[0].replace('[]', '')
      const present = keys.includes(head)
                || (declaredOptional as string[]).includes(head)
      expect(present, `collapsed path ${path} no longer starts at a projected key`).toBe(true)
    }
  })

  it('hands a real fixture value to the generated contract’s own field types', () => {
    // These are assignments, not casts: if the front model drifts away from the generated projection the
    // compile fails here as well, and the fixture is the producer-shaped object the app renders.
    const whole: WorkflowSnapshotV3 = snap
    const transport: WorkflowSnapshotV3['transport'] = snap.transport
    const coverage: WorkflowSnapshotV3['coverage'] = snap.coverage
    const executions: WorkflowSnapshotV3['executions'] = snap.executions
    const tokenSummary: WorkflowSnapshotV3['tokenSummary'] = snap.tokenSummary
    // WUI-15: the row is handed over whole. It could not be before: `ci` collapsed to `unknown[]` and an
    // interface is not assignable to an index signature, so only the generator-named part was checked.
    const row: WorkflowSnapshotV3['projects'][number] = snap.projects[0]
    const rowIdentifiers: WorkflowSnapshotV3['projects'][number]['executionIds'] = snap.projects[0].executionIds
    const rowGit: WorkflowSnapshotV3['projects'][number]['git'] = snap.projects[0].git
    expect(whole.projects.length).toBe(snap.projects.length)
    expect(row.ci.length).toBe(snap.projects[0].ci.length)
    expect(transport.transportState).toBe(snap.transport.transportState)
    expect(rowIdentifiers).toEqual(snap.projects[0].executionIds)
    expect(rowGit.matchState).toBe(snap.projects[0].git.matchState)
    expect(executions.length).toBe(snap.executions.length)
    expect(tokenSummary.costQuality).toBe(snap.tokenSummary.costQuality)
    expect(coverage.denominator).toBe(snap.coverage.denominator)
  })

  it('keeps the optional sections optional in the consumed shape', () => {
    // The renderer distinguishes ABSENT from empty for these, so the GENERATED contract has to say the
    // same thing the front model does: the key may be missing. Asserted at type level, because "optional"
    // is a property of the type, not of one fixture. (WUI-15: the whole object is assignable as of the ci
    // collapse fix, but "optional" is still not something one bare fixture can demonstrate.)
    type Expect<T extends true> = T
    type IsOptional<T, K extends keyof T> = {} extends Pick<T, K> ? true : false
    type Generated = WorkflowSnapshotV3
    type Hand = SnapshotV3
    type GeneratedOptional = Expect<IsOptional<Generated, 'software'>>
    type GeneratedTaskRecords = Expect<IsOptional<Generated, 'taskRecords'>>
    type GeneratedAdapters = Expect<IsOptional<Generated, 'adapterCapabilities'>>
    type GeneratedHandles = Expect<IsOptional<Generated, 'artifactHandles'>>
    type GeneratedCollectors = Expect<IsOptional<Generated, 'collectors'>>
    type HandCollectors = Expect<IsOptional<Hand, 'collectors'>>
    type HandHandlesSummary = Expect<IsOptional<Hand, 'artifactHandlesSummary'>>
    const bare = mkSnap({}) as unknown as Record<string, unknown>
    for (const key of ['artifactHandles', 'adapterCapabilities', 'collectors']) {
      expect(key in bare, `${key} must stay absent on a bare fixture, not empty`).toBe(false)
    }
  })
})
