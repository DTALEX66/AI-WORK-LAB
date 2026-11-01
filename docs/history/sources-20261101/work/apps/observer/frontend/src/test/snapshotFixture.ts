/** The shared v3 snapshot fixture for the render-level truth tests.
 *
 * One builder, several sweeps. `renderTruthContract.test.tsx` pinned the panel-level rules and
 * `laneTransportTruth.sweep.test.tsx` walks every registry lane with it; if each kept its own copy,
 * a change to "what a healthy snapshot looks like" would silently split the two standards.
 *
 * Everything here is a declared value, never a default: a fixture that quietly filled in `0` or
 * `LIVE` would make a fabricated UI state look correct.
 */
import type { ArtifactHandle, ArtifactHandlesSummary, Execution, Project, SnapshotV3, TaskRecord } from '@/types'

/** A fully-populated canonical-store task record (the shape `snapshot_api.py::project_task_record` emits).
 *  Every field is declared, never defaulted: a fixture that padded `0` or `''` would make a fabricated
 *  Inspector value look correct. */
export function mkTaskRecord(over: Partial<TaskRecord> = {}): TaskRecord {
  return {
    taskId: 'WL-900', projectId: 'work-lab', status: 'WAITING_APPROVAL',
    createdAt: '2026-10-08T01:00:00Z', updatedAt: '2026-10-08T01:20:00Z',
    leaseHolder: 'worker-9', leaseExpiresAt: '2026-10-08T01:30:00Z', fencingToken: 7,
    checkpointPresent: true, checkpointKeys: ['cursor', 'stage'],
    checkpointDigest: 'b'.repeat(64),
    ...over,
  }
}

/** An execution row as the v3 projection carries it (no timestamps: the timeline gap is a real gap). */
export function mkExecution(over: Partial<Execution> = {}): Execution {
  return {
    executionId: 'ex-9', anchorProjectId: 'work-lab', workingArea: 'apps/observer',
    state: 'RUNNING', stateQuality: 'strong', agent: 'codex', sessionId: 'sess-42',
    sourceRef: 'git:origin/main@abc1234',
    ...over,
  } as Execution
}

export function mkProject(over: Partial<Project> = {}): Project {
  return {
    projectId: 'work-lab', displayName: 'WORK-LAB', agentPlatform: 'codex',
    identityState: 'RESOLVED', activityState: 'ACTIVE',
    attentionState: 'NONE', activeExecutionCount: 2, workingAreas: ['apps/observer'],
    visibility: 'LOCAL', quality: 'EXACT', lastStrongEvidenceAt: '2026-10-07T08:59:59Z',
    repositories: [],
    git: {
      localSha: 'abc1234def5678', remoteSha: 'abc1234def5678', matchState: 'MATCH',
      branch: 'main', dirtyCount: 3, observedAt: '2026-10-07T09:00:00Z',
      quality: 'EXACT', freshness: 'FRESH', sourceRef: null,
      sourceProjectId: 'work-lab',
    },
    token: { inputTokens: 64391, outputTokens: 26821, totalTokens: 91212, costQuality: 'ESTIMATED' },
    ci: [], executionIds: ['e1'], sourceRefs: [],
    ...over,
  }
}

export const UNKNOWN_GOVERNANCE: SnapshotV3['governance'] = {
  state: 'UNKNOWN',
  families: {
    rules: { state: 'UNKNOWN', current: null, drift: null },
    skills: { state: 'UNKNOWN', current: null, drift: null },
    memory: { state: 'UNKNOWN', current: null, drift: null },
    adapters: { state: 'UNKNOWN', current: null, drift: null },
  },
}

export function mkSnap(over: Partial<SnapshotV3> = {}): SnapshotV3 {
  return {
    schemaVersion: 'workflow/snapshot/v3',
    revision: 11,
    generatedAt: '2026-10-07T09:12:33Z',
    sourceWatermark: '2026-10-07T09:12:30Z',
    transport: { transportState: 'LIVE', freshnessState: 'FRESH', connectedSince: null, eventsUrl: null },
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
    projects: [mkProject(), mkProject({ projectId: 'design-lab', displayName: 'DESIGN-LAB', activeExecutionCount: 0 })],
    executions: [],
    tasks: { PENDING: 2 },
    tokenSummary: { inputTokens: 64391, outputTokens: 26821, totalTokens: 91212, costQuality: 'ESTIMATED' },
    git: { localSha: 'abc1234', remoteSha: 'abc1234', ciSha: 'abc1234', matchState: 'MATCH' },
    ci: [],
    sourceRefs: [],
    ...over,
  } as unknown as SnapshotV3
}

/* ---------------------------------------------------------------------------
 * WUI-15 · the artifact-handle projection (added 2026-10-20).
 *
 * `artifactHandles` / `artifactHandlesSummary` ride the live v3 payload — 200 rows of identity metadata
 * plus the scope report — and until this round no view rendered either key (`scripts/ci/
 * verify_snapshot_keys_rendered.py` is the gate that caught it). These builders copy the MEASURED key
 * shapes rather than a tidied model:
 *
 *  * every row carries exactly the seven `ArtifactHandle` keys; `digest` + `digestSource` ride only the
 *    recorded rows (40 of 200), so a test can tell "not recorded" from "recorded but unprojected";
 *  * `modifiedAt` is whole-second precision, and the list arrives pre-ordered (newest first, ties by
 *    handle ascending) because the producer, not the front end, owns the order;
 *  * `refused.droppedOnVerification` is emitted as an OBJECT by the live producer while
 *    `types.ts::ArtifactHandlesSummary` declares a number. The drift is kept on purpose: the lane must
 *    show 未提供 for a value that is not a count, and a fixture that typed `0` in here would make the
 *    padded cell look correct.
 *
 * `orderingKey`, `orderingRule` and `schemaVersion` are fixture-chosen stand-ins for the live strings —
 * the lane renders them verbatim and the test asserts the rendered text EQUALS the fixture value, which
 * is what proves the component does not hardcode either the wording or the counts.
 * ------------------------------------------------------------------------ */

/** The capacity facts of the measured payload: a 200-row window over 4898 enumerated candidates. */
export const HANDLES_CAP = 200
export const HANDLES_ENUMERATED = 4898
export const HANDLES_OMITTED = 4698
export const HANDLES_SENSITIVE_NAMES_REFUSED = 195
export const HANDLES_PRUNED_REGENERABLE = 112
export const HANDLES_ROWS_WITH_DIGEST = 40

const HANDLES_BASE: Record<string, { surface: string; surfaceRoot: string; kind: string }> = {
  runtime: { surface: 'runtime', surfaceRoot: '.project-local/runs', kind: 'structured-record' },
  telemetry: { surface: 'telemetry', surfaceRoot: '.project-local/runs/telemetry', kind: 'structured-record' },
  receipts: { surface: 'receipts', surfaceRoot: '.project-local/artifacts', kind: 'json-receipt' },
  reports: { surface: 'reports', surfaceRoot: 'reports', kind: 'markdown-report' },
}

/** `artifact_handle_projection.py` stamps second precision, so the fixture must not carry milliseconds. */
const isoSecond = (epochSeconds: number): string =>
  new Date(epochSeconds * 1000).toISOString().replace('.000Z', 'Z')

const HANDLES_NEWEST_EPOCH = Math.floor(Date.parse('2026-10-19T08:31:22Z') / 1000)

/** One projected handle row: the seven schema keys, plus `digest` / `digestSource` when recorded. */
export function mkArtifactHandle(over: Record<string, unknown> = {}): ArtifactHandle {
  return {
    handle: 'D:/All projects/WORK-LAB/.project-local/runs/runtime/record-0000.json',
    kind: 'structured-record',
    surface: 'runtime',
    surfaceRoot: '.project-local/runs',
    sizeBytes: 4096,
    modifiedAt: '2026-10-19T08:31:22Z',
    digestRecorded: false,
    ...over,
  } as ArtifactHandle
}

/**
 * The projected window, in the order the producer publishes it. Five rows share a second, then the
 * second steps back, and inside a tie the handle rises — so a front end that re-sorted by anything else
 * would visibly disagree with the snapshot's own `orderingRule` disclosure.
 */
export function mkArtifactHandleRows(count = HANDLES_CAP): ArtifactHandle[] {
  const faces = Object.values(HANDLES_BASE)
  const rows: ArtifactHandle[] = []
  for (let index = 0; index < count; index += 1) {
    const face = faces[index % faces.length]
    const group = Math.floor(index / faces.length)
    const tie = index % faces.length
    const recorded = index % 5 === 0
    const name = `evidence-${String(count - group).padStart(4, '0')}-${String(tie).padStart(2, '0')}.json`
    rows.push(mkArtifactHandle({
      handle: `D:/All projects/WORK-LAB/${face.surfaceRoot}/${name}`,
      surface: face.surface,
      kind: face.kind,
      surfaceRoot: face.surfaceRoot,
      sizeBytes: 512 + index * 13,
      modifiedAt: isoSecond(HANDLES_NEWEST_EPOCH - group),
      digestRecorded: recorded,
      ...(recorded
        ? { digest: index.toString(16).padStart(2, '0').repeat(32), digestSource: 'ledger-record' }
        : {}),
    }))
  }
  return rows
}

/** The scope report that travels with the window (`artifact_handle_projection.py:640-660`). */
export function mkArtifactHandlesSummary(over: Partial<ArtifactHandlesSummary> = {}): ArtifactHandlesSummary {
  return {
    schemaVersion: 'worklab/artifact-handles-summary/v1',
    cap: HANDLES_CAP,
    complete: false,
    contentIncluded: false,
    cost: { elapsedMs: 412, entriesScanned: HANDLES_ENUMERATED },
    digestIndex: {
      computedByHashing: false,
      pairsIndexed: HANDLES_ROWS_WITH_DIGEST,
      recordsScanned: 128,
      recordsUnreadable: 3,
      rowsWithDigest: HANDLES_ROWS_WITH_DIGEST,
      rowsWithoutDigest: HANDLES_CAP - HANDLES_ROWS_WITH_DIGEST,
    },
    enumeratedCount: HANDLES_ENUMERATED,
    enumerationScope: 'declared-evidence-surfaces-only',
    generatedAt: '2026-10-19T08:31:22Z',
    omittedCount: HANDLES_OMITTED,
    order: 'descending',
    orderingKey: 'modifiedAt,handle',
    orderingRule: '按 modifiedAt 从新到旧排列；同一秒内的把手按 handle 字典序升序排列；'
      + '被 cap 截断的投影保持这个顺序，读者看到的顺序就是生产者发布的顺序。',
    projectedCount: HANDLES_CAP,
    refused: {
      // measured: the live producer emits an object here, not a count (see the header note).
      droppedOnVerification: {} as unknown as number,
      notRegularFiles: 7,
      prunedRegenerableDirectories: HANDLES_PRUNED_REGENERABLE,
      reparseDirectories: 3,
      sensitiveNames: HANDLES_SENSITIVE_NAMES_REFUSED,
      unreadableEntries: 2,
    },
    selection: 'cap-window',
    surfaceState: { surfacesEnumerated: Object.keys(HANDLES_BASE).length },
    surfaces: Object.keys(HANDLES_BASE),
    truncated: true,
    ...over,
  } as unknown as ArtifactHandlesSummary
}

/** A snapshot that carries the handle projection — the shape the loopback sidecar actually returns. */
export function mkSnapWithArtifactHandles(over: Partial<SnapshotV3> = {}): SnapshotV3 {
  return mkSnap({
    artifactHandles: mkArtifactHandleRows(),
    artifactHandlesSummary: mkArtifactHandlesSummary(),
    ...over,
  })
}
