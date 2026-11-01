// WORK-LAB Observer — typed model of the REAL v3 snapshot
// (packages/client-neutral-core/scripts/snapshot_api.py::build_snapshot,
//  authoritative in tests/workflow-assistance/test_sidecar_v3_snapshot.py).
//
// The legacy front rendered a PHANTOM schema (agents[]/models[]/cost[]/
// resources{cpu,mem}/services[]/memory[]). None of those exist in v3. This
// file mirrors ONLY the fields build_snapshot actually emits. U07 (taskpack
// 20260919) front-truth discipline: no frontend price/FX/quota — the only cost
// truth the back end projects is tokenSummary.costQuality.

export type SchemaVersion = 'workflow/snapshot/v3'

export type TransportState = 'LIVE' | 'DELAYED' | 'OFFLINE' | 'CONNECTING' | 'UNKNOWN'
export type FreshnessState = 'FRESH' | 'STALE' | 'UNKNOWN'
/**
 * The six values `snapshot_api.py::_git_match_state` (lines 366-380) can actually return, listed in the
 * order the function tests them. This union used to read `'MATCH' | 'UNVERIFIED' | 'DRIFT' | 'UNKNOWN'`:
 * three of the four real outcomes (`LOCAL_REMOTE_MATCH`, `LOCAL_CI_MATCH`, `MISMATCH`) plus
 * `NO_LOCAL_CLAIM` were un-declarable, while `DRIFT` and `UNKNOWN` could never arrive — so a component
 * switching on `DRIFT` was dead code and the shipped row printed the real token raw. The WUI-15 schema
 * conformance test now pins this union against the schema enum in both directions.
 */
export type GitMatchState =
  | 'MATCH' | 'LOCAL_REMOTE_MATCH' | 'LOCAL_CI_MATCH'
  | 'NO_LOCAL_CLAIM' | 'UNVERIFIED' | 'MISMATCH'
export type FamilyState = 'CLEAN' | 'DRIFT' | 'UNKNOWN'
export type ProjectActivityState = 'ACTIVE' | 'REGISTERED' | 'IDLE' | 'UNKNOWN'
export type ExecutionState =
  | 'RUNNING' | 'STARTING' | 'WAITING_USER' | 'WAITING_APPROVAL' | 'BLOCKED'
  | 'COMPLETED' | 'FAILED' | 'UNKNOWN'
export type CostQuality = 'EXACT' | 'ESTIMATED' | 'UNKNOWN'

export interface SnapshotTransport {
  transportState: TransportState
  freshnessState: FreshnessState
  connectedSince: string | null
  eventsUrl: string | null
  eventStreamConnected?: boolean
  lastHeartbeatAt?: string | null
  writerWatermarkAt?: string | null
}

export interface SnapshotCoverage {
  numerator: number | null
  denominator: number | null
  scope: string | null
}

export interface GovernanceFamily {
  state: FamilyState
  current: unknown | null
  drift: number | null
}

export interface SnapshotGovernance {
  /** The schema enum, and the three values `_governance_projection` can compute for a family set. */
  state: FamilyState
  families: {
    rules: GovernanceFamily
    skills: GovernanceFamily
    memory: GovernanceFamily
    adapters: GovernanceFamily
  }
}

export interface ProjectGit {
  localSha: string | null
  remoteSha: string | null
  matchState: GitMatchState
  branch: string | null
  dirtyCount: number | null
  observedAt: string | null
  quality: string | null
  freshness: string | null
  sourceRef: string | null
  /** WL-L01: whose Git observation this block shows. Own project id, or null when the project has
   *  no Git row of its own. Never another project's id — that fallback was the defect. */
  sourceProjectId: string | null
}

export interface ProjectToken {
  inputTokens: number | null
  outputTokens: number | null
  totalTokens: number | null
  costQuality: CostQuality
}

export interface CiRun {
  runId: string | null
  workflow: string | null
  headSha: string | null
  status: string | null
  conclusion: string | null
  sourceRef: string | null
}

/** A project's CI rows are selected from the same whole rows by `projectId` (`snapshot_api.py:268`), so
 *  each one carries the key that selected it. That key is a string, not a nullable one: a row without it
 *  can never equal a project id and therefore never reaches this list. */
export interface ProjectCiRun extends CiRun {
  projectId: string
}

export interface Project {
  projectId: string
  displayName: string | null
  agentPlatform: string | null
  identityState: string
  activityState: ProjectActivityState
  attentionState: string
  activeExecutionCount: number
  workingAreas: string[]
  visibility: string
  quality: string
  lastStrongEvidenceAt: string | null
  repositories: unknown[]
  git: ProjectGit
  token: ProjectToken
  ci: ProjectCiRun[]
  executionIds: string[]
  sourceRefs: string[]
}

export interface Execution {
  executionId: string
  anchorProjectId: string | null
  workingArea: string | null
  state: ExecutionState
  stateQuality: string
  agent: string | null
  sessionId: string | null
  sourceRef: string | null
}

// P1-02: one task record projected from the canonical store by the unique Snapshot API
// (packages/client-neutral-core/scripts/snapshot_api.py::project_task_record). checkpoint VALUES never
// cross the read-only boundary — the projection carries whether a checkpoint exists, its key names,
// and a digest that moves when it changes.
export interface TaskRecord {
  // `canonical_store.tasks` declares task_id PRIMARY KEY and project_id/status NOT NULL, so a projected
  // row never carries null here; the earlier `| null` made the hand model wider than the schema.
  taskId: string
  projectId: string
  status: string
  createdAt: string | null
  updatedAt: string | null
  leaseHolder: string | null
  leaseExpiresAt: string | null
  fencingToken: number | null
  checkpointPresent: boolean
  checkpointKeys: string[]
  checkpointDigest: string | null
}

// P1-03 / F1: the seven-layer capability ladder, projected by
// packages/client-neutral-core/scripts/adapter_capability_projection.py. Each layer is its own claim:
// MET requires a named source, and anything unprobed arrives as NOT_PROBED carrying the reason for the
// gap. A card may not promote a layer because a neighbouring layer succeeded.
export type CapabilityLayer =
  | 'REGISTERED' | 'INSTALLED' | 'LOADED_CONNECTED' | 'QUALIFIED'
  | 'ENABLED_FOR_TASK' | 'NATIVE_PROJECTION' | 'OBSERVED_IN_EXECUTION'

export interface CapabilityLayerState {
  layer: CapabilityLayer
  state: 'MET' | 'NOT_PROBED' | 'NOT_SUPPORTED'
  evidenceLevel: 'NO_EVIDENCE' | 'SIMULATED' | 'SYNTHETIC' | 'INTEGRATED' | 'REAL'
  source: string | null
  reason: string
}

// P1-03 open item, the verb dimension: the seven layers say what a CLIENT is; they cannot say which verbs of
// the adapter interface the client actually answers. This orthogonal row set is projected by
// packages/client-neutral-core/scripts/adapter_capability_projection.py from the read-only probe record in
// docs/audits/EXECUTOR_LIVE_PROBE_2026-10-08.json#verbProbe. One row per contract verb, each either MET from
// a named read-only call, NOT_SUPPORTED from a named declaration, or NOT_PROBED carrying the concrete
// refusal reason. `attempted` is what separates two very different NOT_PROBED statements — the probe ran
// the call and the answer was not creditable (attempted=true) versus the probe refused to run it at all
// (attempted=false). A verb row never promotes a layer.
//
// On the card the whole dimension is OPTIONAL: an absent probe record emits NO `verbEvidence` key at all
// rather than an empty list, because an empty list would render as "declares nothing" where the truth is
// "I did not look". The Observer renders that absence as the named source gap, never as zero rows.
export type VerbEvidenceState = 'MET' | 'NOT_PROBED' | 'NOT_SUPPORTED'
export type VerbEvidenceLevel = 'NO_EVIDENCE' | 'SIMULATED' | 'SYNTHETIC' | 'INTEGRATED' | 'REAL'

export interface AdapterVerbEvidenceRow {
  verb: string
  state: VerbEvidenceState
  evidenceLevel: VerbEvidenceLevel
  source: string | null
  reason: string | null
  attempted: boolean
  probedAt?: string | null
  command?: string[]
  exitCode?: number | null
  outputDigest?: string
  outputLines?: number
  detail?: string
  basis?: string
  declaredIn?: Record<string, boolean>
  declaresDrift?: string
  entryResolution?: string
  checkedPaths?: string[]
  ref?: string
}

/** The entry-point readback as its own fact (`adapter_capability_projection.py::_card_probe`): an
 *  executable answered, which is NOT a live session. `null` means no probe record exists at all. */
export interface EntryProbeFact {
  status: string
  entryPoint: string | null
  argv: string[]
  exitCode: number | null
  outputDigest?: string
  detail?: string | null
  probedAt: string | null
}

export interface AdapterCapabilityCard {
  clientId: string
  displayName: string
  supportLevel: string
  declaredOperations: string[]
  matrixOperations: string[]
  operationsDrift: boolean
  registryStatus: string
  writePolicy: string
  // Declared by the operator in config/capability-matrix.json#clients[].role and projected by the
  // producer. Optional because the schema does not require it: a card without a role is a source gap,
  // and the surfaces read that as UNKNOWN rather than guessing from the name.
  role?: 'agent_runtime' | 'provider_router' | 'vcs_host' | 'design_client' | 'UNKNOWN'
  risk: string
  runtimeAdapter: string | null
  configOwnershipDefault: { layer?: string, mode?: string, preserve_unknown?: boolean } | null
  clientNote?: string | null
  declaredVersion: string | null
  versionReadbackMethod: string | null
  versionObservedAt: string | null
  versionSource: string | null
  detectionMode: string | null
  detectionEvidenceState: string
  protocolConformance: Record<string, string>
  observedAt: string | null
  layers: CapabilityLayerState[]
  nativeStatus: 'NOT_IMPLEMENTED' | 'NOT_PROBED' | 'NATIVELY_VERIFIED'
  // Optional per-verb dimension (see AdapterVerbEvidenceRow). ABSENT (no key) is the probe-record gap and
  // renders as such; it is never synthesised into an empty list.
  verbEvidence?: AdapterVerbEvidenceRow[]
  verbEvidenceCounts?: Partial<Record<VerbEvidenceState, number>> & Record<string, number>
  verbEvidenceProbedAt?: string | null
  /**
   * WUI-06: the producer has emitted these two since the entry probe existed
   * (`adapter_capability_projection.py:339,342`) and `types.ts` did not carry them — the drift
   * `tests/workflow-assistance/test_capability_card_fields_cover_the_producer.py` now fails on.
   * `versionDrift` is a live-entry disagreement with the declared version; both strings stay visible,
   * because the registry is not the truth and a stale note about it is not either.
   */
  entryProbe?: EntryProbeFact | null
  versionDrift?: boolean
}

export interface TokenSummary {
  inputTokens: number | null
  outputTokens: number | null
  totalTokens: number | null
  costQuality: CostQuality
}

export interface TopGit {
  localSha: string | null
  remoteSha: string | null
  ciSha: string | null
  matchState: GitMatchState
}

export interface WorkspaceEvidence {
  plan?: {
    status?: string
    counts?: Record<string, number>
    tasks?: { taskId?: string; [k: string]: unknown }[]
    approvals?: { state?: string; [k: string]: unknown }[]
  }
  // `workspace_evidence.py:148` emits None when the governance file is unreadable, so the field is
  // `number | null`, not `number | undefined`: "counted zero contracts", "could not read the file" and
  // "the key is absent" are three different answers and the type must be able to hold all three.
  governance?: { contracts?: number | null; [k: string]: unknown }
  history?: { totalErrors?: number; recentErrors?: { errorId?: string; [k: string]: unknown }[]; [k: string]: unknown }
  // packages/client-neutral-core/scripts/workspace_evidence.py appends one row per loaded surface:
  // {path, evidenceKind, loadedAt} (+ generatedAt for the JSON projections). `path` is a repository-RELATIVE
  // POSIX path — the projection has no project root to absolutize it with, which is exactly why an
  // evidence-range read of it comes back refused rather than empty.
  sources?: { evidenceKind?: string; path?: string; loadedAt?: string; generatedAt?: string; [k: string]: unknown }[]
  [k: string]: unknown
}

// S31/32 (taskpack 20260919): read-only software installation-identity
// projection. The Observer projects this (U17/P0-07 contract) when the backend
// carries it; when absent the panel shows UNKNOWN, NEVER a fabricated "Healthy".
// It is NOT a second Update Authority — no relocation / delete / act-on.
export type SoftwareLocationStatus =
  | 'NOT_INSTALLED' | 'SINGLE_VERIFIED' | 'SINGLE_UNVERIFIED'
  | 'LOCATION_DRIFT' | 'DUAL_INSTALLATION' | 'MISSING_EXPECTED_INSTALL'
  | 'RELOCATION_REQUESTED' | 'OS_MANAGED' | 'UNKNOWN'

export interface SoftwareIdentity {
  softwareId: string
  displayName: string | null
  installRoot: string | null
  executableRealpath: string | null
  discoveredVersion: string | null
  releaseChannel: string | null
  updateAvailable: boolean | null
  duplicateInstallation: boolean
  expectedLocation: string | null
  observedLocation: string | null
  locationStatus: SoftwareLocationStatus
  lastVerified: string | null
  discoverySource: string | null
}

/**
 * The scope report the producer publishes alongside the handle list
 * (`artifact_handle_projection.py:640-660`). It is the only projected field that can distinguish
 * "the projection enumerated everything" from "it stopped at a cap or refused entries", which is why
 * WUI-11's 局部故障 state reads it rather than an absence of rows.
 *
 * `contentIncluded: false` is a statement about the payload, not a gap: the handles are metadata, and
 * the byte-range read endpoint is the only way to reach content.
 */
export interface ArtifactHandlesSummary {
  // The producer emits both keys on every summary (`artifact_handle_projection.py`), and the schema
  // requires them; they were the two facts the hand model could not name.
  schemaVersion: string
  orderingKey: string
  enumeratedCount: number
  projectedCount: number
  omittedCount: number
  cap: number
  truncated: boolean
  complete: boolean
  refused: {
    sensitiveNames: number
    reparseDirectories: number
    notRegularFiles: number
    droppedOnVerification: Record<string, number>
    unreadableEntries: number
    prunedRegenerableDirectories: number
  }
  enumerationScope: string
  digestIndex: { rowsWithDigest: number; rowsWithoutDigest: number; computedByHashing: boolean; [k: string]: unknown }
  contentIncluded: boolean
  [k: string]: unknown
}

export interface CollectorDelivery {
  collector: string
  totalRuns: number
  lastRunAt: string | null
  lastSuccessAt: string | null
  consecutiveFailures: number
  /** derived boolean: the stored `circuit_open_until` is a monotonic value from another process */
  circuitOpen: boolean
  /** events dropped from this collector's bounded queue — NOT the same fault as a refused row */
  droppedEvents: number
  /** rows the source offered that the store refused, accumulated since the collector was first seen */
  refusedRows: number
  /** rows that reached the store, accumulated — the other half of "delivered vs refused" */
  deliveredRows: number
  lastRefusalReason: string | null
  /** the same predicate `coverage.numerator` is counted with, so the two lanes cannot disagree */
  fresh: boolean
}

/** One row of `artifactHandles` (`artifact_handle_projection.py::_verify`/projected): identity metadata
 *  only. The schema names these seven fields, so the generator can project them instead of collapsing
 *  the list to `unknown[]`. */
export interface ArtifactHandle {
  handle: string
  surface: string
  kind: string
  sizeBytes?: number | null
  modifiedAt?: string | null
  surfaceRoot?: string
  digestRecorded?: boolean
}

export interface SnapshotV3 {
  schemaVersion: SchemaVersion
  revision: number
  /** `build_snapshot` substitutes `_now()` when no source timestamp is passed, and the schema requires
   *  an RFC3339 string; `null` was a front-only allowance the producer never emitted. */
  generatedAt: string
  sourceWatermark: string | null
  transport: SnapshotTransport
  coverage: SnapshotCoverage
  governance: SnapshotGovernance
  workspace: WorkspaceEvidence
  projects: Project[]
  executions: Execution[]
  tasks: Record<string, number>
  tokenSummary: TokenSummary
  git: TopGit
  ci: CiRun[]
  sourceRefs: string[]
  // Optional install-identity projection (U17/P0-07) when the backend carries
  // it. Absent => the software panel shows UNKNOWN (never a fake Healthy).
  software?: SoftwareIdentity[]
  // P1-02 deep-link target records. ABSENT means the producer did not query the task table, which is a
  // different statement from an empty list (queried, nothing there). The Work lane renders the first as
  // 后端未提供 and only the second as 无任务 — never a padded 0.
  taskRecords?: TaskRecord[]
  // P1-03: per-client capability cards with the seven-layer ladder. ABSENT (producer could not read the
  // declared sources) is reported as a source gap, not as "no adapters".
  adapterCapabilities?: AdapterCapabilityCard[]
  // WUI-15: emitted by `snapshot_api.py:114-115` and validated by
  // `snapshot_validator.py:364-372`. The item fields are the schema's seven; `unknown[]` could not be
  // assigned to the generated row once the schema named them, and the producer really emits them.
  artifactHandles?: ArtifactHandle[]
  artifactHandlesSummary?: ArtifactHandlesSummary
  // WUI-18(e)/WUI-11: per-collector delivery and refusal counts. ABSENT means the health table could not be
  // read; an empty list means it was read and no collector is registered. The diagnostics lane renders the
  // first as a source gap and only the second as "no collectors" — never a padded zero.
  collectors?: CollectorDelivery[]
  // WUI-21: the isolated-trial read models, carried verbatim as their contract documents
  // (`worklab/operation-progress/v1`, `worklab/isolated-trial/v1`). ABSENT means the producer was not
  // wired; an empty array would mean it was wired and there is nothing — a different statement, so the
  // trial pages render the two differently and never pad either to a zero.
  operationProgress?: OperationProgressRecord[]
  isolatedTrials?: IsolatedTrialRecord[]
  // The problem centre (audit 2026-10-22, 闭环距离 row 2). CL-07 renders it in
  // `views/IssueCenter.tsx` on the 项目监控 lane. Absent means no source answered; `[]` with
  // `issuesSummary.complete=true` means every source was read and nothing was wrong. The centre keeps
  // those two apart and shows UNKNOWN for the first, never a zero.
  issues?: IssueRecord[]
  issuesSummary?: IssuesSummary
}

/**
 * One problem derived from a fact the canonical store already holds
 * (`packages/client-neutral-core/scripts/issue_projection.py::_issue`). `evidenceRef` is the table and key
 * to re-read, `priorityRule` is the sentence that set `priority`, and `occurrences` counts the source rows
 * that folded into this fingerprint. Nothing here states a cause. The optionality mirrors the schema's
 * `required` list exactly: widening any of it stops the generated contract from being assignable.
 */
export interface IssueRecord {
  schemaVersion: 'workflow/issue/v1'
  fingerprint: string
  class: 'SOURCE_CIRCUIT_OPEN' | 'SOURCE_REFUSAL' | 'SOURCE_FAILURE' | 'SOURCE_DATA_DROPPED'
  | 'SOURCE_STALE' | 'SOURCE_INCOMPLETE_COVERAGE' | 'EXECUTION_STALLED' | 'EXECUTION_CONFLICT'
  | 'TASK_BLOCKED' | 'TASK_FAILED'
  projectId?: string | null
  subject?: string
  origin: string
  evidenceRef: string
  priority: 'P1' | 'P2' | 'P3'
  priorityRule: string
  safeToReread?: boolean
  firstSeenAt?: string | null
  lastSeenAt?: string | null
  occurrences: number
  magnitude?: Record<string, unknown>
  detail?: string
  status: 'OPEN'
  /** Attribution, three fields, one of six states. A row whose source names no product says so; a name the
   *  identity list resolves to two products is `ambiguous` and keeps `softwareId: null` — guessing which
   *  install was meant would attribute a problem to software that may not be involved. */
  softwareId: string | null
  softwareVersion: string | null
  softwareVersionSource: 'discovered' | 'not-discovered' | 'unmatched' | 'ambiguous'
  | 'source-names-no-software' | 'identity-source-absent'
}

/** The scope report of that exact list: which sources answered, what the scan limit absorbed, what the cap
 *  dropped. A list without this block is a claim that nothing was omitted. */
export interface IssuesSummary {
  schemaVersion: 'worklab/issues-summary/v1'
  generatedAt?: string
  sources?: Array<{source: string, state: 'read' | 'absent' | 'error', rowsScanned?: number | null,
    issuesDerived?: number | null}>
  sourcesRead: number
  sourcesAbsent: number
  rowsScanned: number
  scanLimits?: {telemetry_events?: number | null}
  scanTruncated?: {telemetry_events?: boolean}
  distinctIssueCount: number
  emittedCount: number
  omittedCount: number
  foldedOccurrences: number
  cap: number
  truncated: boolean
  complete?: boolean
  priorityCounts?: {P1?: number, P2?: number, P3?: number}
  /** Every emitted row sits in exactly one of the four buckets; `identitySourceAbsent` is why
   *  `attributed: 0` must never be read as "no problem belongs to any software". */
  softwareAttribution: {attributed: number, unmatched: number, ambiguous: number, unattributable: number,
    versionKnown: number, identitySourceAbsent: boolean}
  classesPresent?: string[]
  classVocabulary?: string[]
  projectsCovered?: Array<string | null>
  unattributedCount?: number
  order?: string
  orderingKey: string
  orderingRule?: string
  derivationScope?: 'canonical-store-facts-only'
  inferencePerformed?: false
  contentIncluded?: false
  sourceErrors?: string[]
  cost?: {elapsedMs?: number}
}

/** One separated trial stage. `basis` is the evidence; `status` without it is a claim. */
export interface IsolatedTrialStage {
  status: string
  basis: 'LEDGER_STATE' | 'EXTERNAL_EFFECT_RECONCILED' | 'WORKTREE_ID' | 'SESSION_ID' | 'NONE' | 'NO_PRODUCER' | string
  note: string
}

export interface IsolatedTrialRecord {
  schema_version: 'worklab/isolated-trial/v1'
  trial_id: string | null
  parent_task_id: string | null
  child_task_id: string | null
  observed_at: string
  isolation: { basis: string; value: string | null }
  separated_results: {
    write: IsolatedTrialStage
    native_readback: IsolatedTrialStage
    target_behaviour: IsolatedTrialStage
  }
  producer_gaps: string[]
}

export interface OperationProgressRecord {
  schema_version: 'worklab/operation-progress/v1'
  task_id: string | null
  observed_at: string
  state: string
  ledger_status: string | null
  last_trusted_progress: { state: string | null; at: string | null; basis: string }
  transport_state: string | null
  producer_gaps: string[]
  // Absent unless a reconciled external effect answered it (`operation_progress.py`); null is the
  // explicit "no producer" record. `unknown` here could not be handed to the generated field.
  target_behaviour?: Record<string, unknown> | null
}
