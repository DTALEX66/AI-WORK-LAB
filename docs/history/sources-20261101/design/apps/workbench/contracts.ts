// SPDX-License-Identifier: MIT
// Workbench API contracts — strict TypeScript types for DESIGN-LAB service
// responses (taskpack 26: API responses must not be `any`; cross-language
// enum vocabularies come from generated types / JSON Schema, never hand-copied).
//
// Type-only surface: everything here erases at runtime (tsc noEmit / esbuild /
// Node type stripping), so the served browser script keeps zero runtime imports.

export interface TaskAttempt {
  attempt_no: number;
  attempt_id: string;
  state: string;
}

export interface TaskCancel {
  requested: boolean;
  acknowledged: boolean;
}

export interface TaskRecord {
  kind: string;
  state: string;
  job_id: string;
  // The service emits both flags for every attempt, so a receipted task can be told apart
  // from one whose cancellation the operator asked for and the host never acknowledged.
  cancel: TaskCancel;
  attempt: TaskAttempt;
}

export interface EventRecord {
  at: string;
  attempt_no: number;
  from_state?: string;
  to_state: string;
}

export interface AssetRecord {
  // Key set measured against the live route, not copied from an assumption:
  // src/design_lab/image_assets.py::_verified returns exactly
  // id, version_id, sha256, byte_size, rights, width, height, media_type for both the list and
  // the single-read branch. `kind` and `version_no` used to be declared here and were never
  // emitted, so the reference picker painted the literal word "undefined" in front of every
  // asset. The raster-only scope is a WHERE clause on the route (asset_kind='raster'), so the
  // page may not read a kind off the row; it reads what the service actually says.
  id: string;
  version_id: string;
  sha256: string;
  byte_size: number;
  rights: string;
  width: number;
  height: number;
  media_type: string;
}

export interface NativeAssetRecord {
  id: string;
  kind: string;
  version_no: number;
  version_id: string;
  byte_size: number;
  sha256: string;
  rights: string;
  verification: string;
}

export interface AutomationConnectorRow {
  // Key set measured against the live route (src/design_lab/automation_connectors.py::build).
  // `design_lab_state` is NOT_PROBED for every row: it is this project's own reading, and the
  // pack's MCP_READY/UNAVAILABLE words are reported separately as its evidence, never adopted.
  id: string;
  transport: string | null;
  handshaked_in_pack_evidence: boolean;
  tools_listed_in_pack_evidence: number | null;
  native_tool_called_in_pack_evidence: boolean | null;
  design_lab_state: string;
  design_lab_enabled: boolean;
  activation: string;
  same_named_project_adapters: string[];
  rights: string;
}

export interface AutomationConnectorsView {
  meaning: string;
  unprobedMeans: string;
  registry_state: string;
  pack_state: string;
  counts: {
    connectors: number; handshaked_in_pack_evidence: number;
    tools_listed_total_in_pack_evidence: number; native_tool_calls_executed: number;
    probed_by_design_lab: number; enabled: number; project_adapters: number;
  };
  connectors: AutomationConnectorRow[];
  pack: {
    zip_bytes: number | null; zip_sha256: string | null;
    declared_connections: number | null; verification: Record<string, number> | null;
  };
  not_activated: string[];
  inert_instruction_blobs: number | null;
  evidence_ceiling: string;
  claims_not_made: string[];
}

export interface ProjectSummary {
  id: string;
  name: string;
  created_at: string;
}

export interface ProjectRecord extends ProjectSummary {
  // null means that surface's table has never been created on this checkout; 0 means it exists and
  // this project holds none. The two are never interchangeable -- see `surfaceRule` below.
  objects: {
    assets: number | null; briefs: number | null; currentBriefs: number | null;
    directions: number | null; designSystemBindings: number | null;
    designLayerEvents: number | null; promptResults: number | null;
    knowledgeCandidates: number | null; juryRecords: number | null;
    rightsDecisions: number | null; researchFindings: number | null;
    creativeJobs: number | null; modelSelectionRevisions: number | null;
    qualityRecords: number | null;
  };
  absentSurfaces: string[];
  last_activity_at: string | null;
  waiting: {
    promptResultsUnsigned: number | null; promptResultsNotCurrent: number | null;
    knowledgeCandidatesPendingReview: number | null;
    knowledgeCandidatesExportReady: number | null;
  };
}

export interface ProjectListResponse {
  schemaVersion: string;
  projects: ProjectRecord[];
  surfaceRule: string;
  does_not_say: string[];
}

// What the shipped screens read from /api/projects today. The roll-up fields are declared on
// `ProjectRecord`/`ProjectListResponse` because the route sends them; a seam must not claim to
// expect fields no panel reads yet, or the shape guard reports a "missing" field the page ignores.
export type ProjectListView = Pick<ProjectListResponse, 'projects'>;

export interface TaskListResponse {
  tasks: TaskRecord[];
  next_cursor: string | null;
}

// DL-UI-U06 (2026-10-10) — the read-only runtime observation over the native tables.
// `NOT_READ` is NOT a value the service emits: it exists only in the offline fallback below,
// so a disconnected page can never render "this service never ran a native attempt" (ABSENT)
// from bytes it never received. The service keeps ABSENT and PRESENT apart; the page keeps
// both apart from "we did not ask successfully".
export type NativeRuntimeTableState = 'PRESENT' | 'ABSENT' | 'NOT_READ';

export interface NativeRuntimeSection {
  table: NativeRuntimeTableState;
  rows: Array<Record<string, string | null>> | null;
}

export interface NativeRuntimeResponse {
  schemaVersion: string;
  project_id: string;
  host_guard: NativeRuntimeSection;
  quiescence: NativeRuntimeSection;
  reconciliation: NativeRuntimeSection;
  recovery_protocol: NativeRuntimeSection;
  executions: NativeRuntimeSection;
  counts: {
    hosts_held: number | null;
    attempts_quiescent_receipted: number | null;
    reconciliations_open: number | null;
    executions_receipted: number | null;
    executions_with_result: number | null;
  };
  budget: null;
  budget_reason: string;
  proves_production_ready: boolean;
  is_host_action_performed: boolean;
  does_not_say: string[];
}

export interface EventListResponse {
  events: EventRecord[];
  next_cursor: string | null;
}

export interface AssetListResponse {
  assets: AssetRecord[];
}

export interface NativeAssetListResponse {
  assets: NativeAssetRecord[];
  next_cursor: string | null;
}

export interface AssetContentResponse {
  asset: AssetRecord;
  content_base64: string;
}

export interface NativeAssetVerifyResponse {
  asset: NativeAssetRecord;
}

export interface ProjectCreateResponse {
  project: ProjectSummary;
}

export interface TaskDispatchResponse {
  worker: string;
}

export interface TaskActionResponse {
  task: TaskRecord;
}

export interface BundleDownloadResponse {
  bundle: { sha256: string; byte_size: number };
  download_path: string;
}

// Project delivery read-back: GET /api/projects/<id>/bundles lists the
// project's design bundles (its deliveries), read from the persisted store.
// `kind` is the API response label 'design-bundle' -- NOT the stored column
// value ('other'), which is the measured predicate the query filters on.
export interface BundleRecord {
  id: string;
  kind: string;
  version_id: string;
  version_no: number;
  byte_size: number;
  sha256: string;
  rights: string;
  verification: string;
}

export interface BundleListResponse {
  bundles: BundleRecord[];
}

export interface NativePlanResponse {
  task: TaskRecord;
}

export interface PatchResponse {
  task: TaskRecord;
  parent: { version_id: string };
}

// --- E-SLICE-01 design layer: Brief -> Reference -> Direction -> DesignSystem ---
export interface DesignBrief {
  brief_id: string;
  title: string;
  goals: string[];
  constraints: string | null;
  reference_asset_ids: string[];
  spec_sha256: string;
  version: number;
  superseded_by: string | null;
  created_at: string;
}

export interface DesignDirection {
  direction_id: string;
  brief_id: string;
  title: string;
  style_notes: string[] | null;
  color_mood: string | null;
  typography_mood: string | null;
  chosen: boolean;
  actor: string | null;
  actor_kind: string | null;
  spec_sha256: string;
  version: number;
  superseded_by: string | null;
  created_at: string;
}

export interface DesignSystemBinding {
  binding_id: string;
  direction_id: string;
  design_system_name: string;
  spec_sha256: string;
  version: number;
  superseded_by: string | null;
  created_at: string;
}

export interface DesignSystemRecord {
  name: string;
  title: string;
  version: string;
  evidence_level: string;
}

export interface BriefListResponse {
  briefs: DesignBrief[];
  next_cursor: string | null;
}

export interface DirectionListResponse {
  directions: DesignDirection[];
  next_cursor: string | null;
}

export interface BriefGetResponse {
  brief: DesignBrief;
}

export interface DirectionGetResponse {
  direction: DesignDirection;
}

export interface DesignSystemListResponse {
  design_systems: DesignSystemRecord[];
}

export interface DesignLayerReadback {
  briefs: DesignBrief[];
  directions: DesignDirection[];
  chosen_direction: DesignDirection | null;
  bindings: DesignSystemBinding[];
  active_binding: DesignSystemBinding | null;
  design_systems: DesignSystemRecord[];
}

export interface DesignLayerResponse {
  design_layer: DesignLayerReadback;
}

// --- F-2b revision flow: append a new version, read the chain back ---------
export interface BriefRevisionResponse {
  brief: DesignBrief;
}

export interface DirectionRevisionResponse {
  direction: DesignDirection;
}

export interface BriefLineage {
  brief_id: string;
  root_id: string;
  requested_id: string;
  live_id: string | null;
  versions: DesignBrief[];
}

export interface DirectionLineage {
  direction_id: string;
  root_id: string;
  requested_id: string;
  live_id: string | null;
  versions: DesignDirection[];
}

export interface BriefLineageResponse {
  lineage: BriefLineage;
}

export interface DirectionLineageResponse {
  lineage: DirectionLineage;
}

// --- Prompt intelligence: POST /api/projects/<id>/prompts and the per-asset reversal ---
// Typed from the two schemas the emitter validates itself
// (`design-lab/schemas/prompt-composition-v1.schema.json`, `.../prompt-reversal-v1.schema.json`,
// checked by `prompt_intelligence.check_document`). Two rules follow from how the module is
// written and are the reason these shapes are boring:
//   * `source.kind` is only ever `stored` or `framing` — the page shows what the record says and
//     never re-labels it, so the field stays an open string here rather than a hand-copied enum
//     (LANGUAGE-POLICY §5: no enum is copied between languages without a check on both sides);
//   * `model.executed` is `false` in every document this service can produce, and `selected` is
//     always null. Both are rendered as read, not as a page-side claim.
export interface PromptSectionSource {
  kind: string;
  brief_id?: string;
  direction_id?: string;
  version?: number;
  spec_sha256?: string;
  rule?: string;
}

export interface PromptSection {
  kind: string;
  text: string;
  source: PromptSectionSource;
}

/** One thing the prompt does not know, in the emitter's own words. */
export interface PromptUnknown {
  field: string;
  reason: string;
}

export interface PromptModelBlock {
  selected: string | null;
  executed: boolean;
}

export interface PromptCompositionDocument {
  schemaVersion: string;
  composition_id: string;
  project_id: string;
  target: string;
  prompt_text: string;
  sections: PromptSection[];
  observed: PromptSectionSource[];
  framing: PromptSectionSource[];
  unknown: PromptUnknown[];
  model: PromptModelBlock;
  claims_not_made: string[];
}

export interface PromptReversalLayer {
  id: string;
  type: string;
  name: string;
  bounds: { x: number; y: number; width: number; height: number };
  confidence: { score: number; method: string };
}

export interface PromptReversalDocument {
  schemaVersion: string;
  reversal_id: string;
  project_id: string;
  asset: { id: string; sha256: string; width: number; height: number; media_type: string };
  observation: {
    module: string;
    decomposition_id: string;
    rir_sha256: string;
    object_count: number;
  };
  prompt_text: string;
  layers: PromptReversalLayer[];
  unknown: PromptUnknown[];
  model: PromptModelBlock;
  claims_not_made: string[];
}

/** The 201 envelope both routes answer with: the document plus a digest over its own bytes. */
export interface PromptCompositionReadback {
  status: string;
  document: PromptCompositionDocument;
  document_sha256: string;
}

export interface PromptReversalReadback {
  status: string;
  document: PromptReversalDocument;
  document_sha256: string;
}

// --- model catalogue: GET /api/models (the picker's read of two registries) --
// `src/design_lab/model_catalog.py` assembles this from the model radar and the provider
// capability record and returns them as TWO sections with `join.key` null, because no field is
// shared between model_id and provider_id. The page therefore renders two tables and never one
// merged one — a joined row would fabricate a relationship the data cannot support. Status words
// (radar_state, machine_state, hardware_fit, placement, evidence_level) are carried as read
// strings: this file must not become a second copy of the radar's vocabulary.
export interface ModelCatalogModelRow {
  model_id: string;
  family: string;
  placement: string | null;
  source_ref: string | null;
  radar_state: string;
  machine_state: string | null;
  hardware_fit: string | null;
  vram_gib_required: number | null;
  commercial_use: string | null;
  license_id: string | null;
  default_enabled: boolean;
  weights_recorded: number;
  blocking_reason: string | null;
  evidence_ref: string | null;
}

export interface ModelCatalogEndpointRow {
  provider_id: string;
  endpoint_ref: string;
  capabilities: string[] | null;
  local_first: boolean | null;
  license: string | null;
  license_risk: string | null;
  evidence_level: string | null;
  source: string | null;
}

export interface ModelCatalogResponse {
  schemaVersion: string;
  observed_at: string | null;
  sources: Record<string, string>;
  hardware: Record<string, unknown>;
  policy: Record<string, unknown>;
  counts: {
    models: number;
    endpoints: number;
    qualified_local: number;
    default_enabled_true: number;
    weights_recorded: number;
    placement: Record<string, number>;
  };
  models: ModelCatalogModelRow[];
  endpoints: ModelCatalogEndpointRow[];
  join: { key: string | null; reason: string };
  selection: { mode: string; rules: string[]; transport: string; executed: boolean };
  claims_not_made: string[];
}

// --- model selection: GET / POST .../model-selection(/choose) ----------------
// A recorded act of choosing, per project, with the catalogue's facts copied in at that moment.
// The three states are the point of the read: CHOSEN, DECLINED (the operator said 不用) and
// NEVER_ASKED are different facts and the page must not merge them. `executed` appears nowhere in
// these shapes: a choice is not a run, and the type must not be able to say otherwise.
export interface ModelSelectionSnapshot {
  placement: string | null;
  radar_state: string | null;
  machine_state: string | null;
  commercial_use: string | null;
  weights_recorded: number | null;
  qualified_local: boolean;
}

export interface ModelSelectionRecord {
  schemaVersion: string;
  project_id: string;
  revision: number;
  model_id: string | null;
  declared_unused: boolean;
  snapshot: ModelSelectionSnapshot | null;
  actor: string;
  actor_kind: string;
  recorded_at: string;
  claims_not_made: string[];
}

export interface ModelSelectionReadback {
  schemaVersion?: string;
  project_id?: string;
  state?: 'CHOSEN' | 'DECLINED' | 'NEVER_ASKED' | string;
  selection?: ModelSelectionRecord | null;
  revision_count?: number;
  unreadable_count?: number;
  history?: ModelSelectionRecord[];
  claims_not_made?: string[];
  does_not_say?: string[];
}

export interface ModelSelectionWritten {
  status?: string;
  selection?: ModelSelectionRecord | null;
  replayed?: boolean;
  revision_count?: number;
  state?: string;
  claims_not_made?: string[];
}

// --- design-system TOKEN documents (W06 token write chain) -----------------
// The record the service persists and reads back. `document` is the DTCG token
// document exactly as written; the CSS custom-property map is a projection and is
// never stored, so it has no field here.
export interface TokenDocumentRecord {
  token_document_id: string;
  project_id: string;
  design_system_name: string;
  document: Record<string, unknown>;
  token_count: number;
  dtcg_schema_version: string;
  spec_sha256: string;
  actor: string | null;
  actor_kind: string | null;
  version: number;
  superseded_by: string | null;
  created_at: string;
}

export interface TokenDocumentListResponse {
  token_documents: TokenDocumentRecord[];
}

export interface TokenDocumentGetResponse {
  token_document: TokenDocumentRecord;
}

// A refusal that carries field paths: TOKEN_DOCUMENT_INVALID arrives with the
// DTCG schema/semantic reasons, which is the only form a reviewer can fix.
export interface TokenWriteError {
  error: string;
  detail?: string[];
}

// --- UI convergence slice 2: service diagnostics read back by AppShell views ---
export interface HealthResponse {
  status: string;
  version: string;
  scope: string;
}

export interface EnvironmentResponse {
  schemaVersion: string;
  status: string;
  project_root: string;
  project_local_root: string;
  sources: Record<string, string>;
  roots: Record<string, { path: string; ownership: string; writable: boolean }>;
  shared_inputs: Record<string, { path: string; writable: boolean; status: string }>;
  agent_profile: { status: string; writable: boolean };
  write_trace: string;
  migration: string;
}

export interface TaskPreflightResource {
  ref: string;
  kind: string;
  state: string;
  meaning: string;
  host_scope?: string;
  path?: string | null;
  licence?: string | null;
}

/** Projection of vendor/sources.lock.json + sources.revisions.json + model-radar. */
export interface CapabilityRecord {
  id: string;
  kind: string;
  domain: string | null;
  title: string;
  disposition: string | null;
  license: string | null;
  presence: string | null;
  url: string | null;
  revision: string | null;
  revisionState: string;
  revisionReason: string | null;
  repo: string | null;
  observedAt: string | null;
  contentDigest: string | null;
  /** null means no host run and no human acceptance exists yet - not `false`. */
  qualified: boolean | null;
  /** The recorded evidence references, when a qualification record exists at all.
   *  Corrected on 2026-10-09: the emitter produces a list (`_qualification`), and the
   *  previous `string | null` would have accepted a shape no record ever sends. */
  qualificationEvidence: readonly string[] | null;
  /** Why `qualified` is null, in the service's own words. An unknown without a stated
   *  reason reads like a missing feature rather than an unmade judgement. */
  qualificationReason: string | null;
  /** The seven classification axes with their **values** (DL-FINAL-T06). An empty list
   *  means the taxonomy carries the field and nobody classified this candidate;
   *  null means the row has no such field. The UI must keep those two apart. */
  axes: Readonly<Record<string, string | readonly string[] | Readonly<Record<string, unknown>> | null>>;
  sourceType: string | null;
  evidenceLevel: string | null;
  upstreamOwner: string | null;
  licenseUrl: string | null;
  rightsNotes: string | null;
  removalPath: string | null;
  popularity: {
    stargazerCount: number | null;
    forkCount: number | null;
    observedAt: string | null;
    source: string | null;
    isNotQuality: boolean;
  } | null;
  unclassifiedAxes: string[];
}

export interface CapabilityLibraryResponse {
  schemaVersion: string;
  meaning: string;
  unmeasuredMeans: string;
  classification?: {
    joined: number;
    unclassifiedAxes: string[];
    note: string;
  };
  counts: {
    total: number;
    byKind: Record<string, number>;
    byLicense: Record<string, number>;
    byRevisionState: Record<string, number>;
    // Four numbers, not one: "how many carry a qualification verdict" and "how many are
    // qualified" are different claims, and the single key read like the second one.
    qualificationVerdicts: number;
    qualifiedTrue: number;
    qualifiedFalse: number;
    qualificationNotAdjudicated: number;
  };
  sources: Record<string, string>;
  capabilities: CapabilityRecord[];
}

export interface TaskPreflightResponse {
  schemaVersion: string;
  task_full_id: string;
  taskpack_id: string;
  task_key: string;
  registry_state: string;
  local_config_fallback: string | null;
  resources: TaskPreflightResource[];
  blocked_resources: string[];
  verdict: string;
  machine_scope: string;
  authority_source: string;
  permissions: { install: boolean; licence_accept: boolean; external_traverse: boolean; meaning: string };
  install_executed: boolean;
  licence_accepted: boolean;
  meaning: string;
}

// --- Domain Pack readback: GET /api/domains --------------------------------
// The four words are the closed vocabulary of src/design_lab/domain_packs.py. They are
// declared here rather than free strings because a page that invented a fifth verdict
// ("approved", "accepted") would be claiming a judgement no emitter produces; the
// two-way equality with the Python tuple is pinned by
// design-lab/tests/test_domain_pack_readback.py (LANGUAGE-POLICY §5 — enums are not
// hand-copied between languages without a check that both sides match).
export type DomainPackValidation = 'VALIDATES' | 'INVALID' | 'UNREADABLE' | 'NOT_CHECKED';

/** One pack directory, with the identity its own manifest declares. */
export interface DomainPackRecord {
  directory: string;
  /** null = the manifest does not declare it (or could not be read). Not "none", not "". */
  packId: string | null;
  version: string | null;
  displayName: string | null;
  /** A workflow/domain-pack/v1 manifest has no `domain` field at all. */
  domain: string | null;
  manifestSchemaVersion: string | null;
  dependencies: string[] | null;
  validation: DomainPackValidation;
  validationErrors: string[];
  validationErrorCount: number;
  note: string | null;
}

export interface DomainListResponse {
  schemaVersion: string;
  meaning: string;
  unmeasuredMeans: string;
  root: string;
  rootState: string;
  validationVocabulary: string[];
  checker: { path: string; state: string; note: string | null };
  sources: Record<string, string>;
  counts: { packs: number; byValidation: Record<string, number> };
  packs: DomainPackRecord[];
}

// --- Assistance plan readback: GET /api/projects/{id}/assistance-plans ------
// Key set measured against src/design_lab/assistance_plan.py::AssistancePlans.list, which
// selects the LATEST revision of every plan in the project and orders it
// `created_at DESC, plan_id DESC`. That ordering is why a page may call this list 最近方案:
// it is the service's own recency reading, not a client-side sort. The row carries no
// verdict words — `provided` and `chosen_revision` are facts the page computes its own
// sentence from, and the choice row is a separate table the list joins in.
export interface AssistancePlanRow {
  plan_id: string;
  revision: number;
  objective: string;
  output_type: string;
  created_at: string;
  created_by: string;
  reference_count: number;
  provided: boolean;
  chosen_revision: number | null;
}

export interface AssistancePlanListView {
  schemaVersion: string;
  total: number;
  offset: number;
  limit: number;
  returned: number;
  next_offset: number | null;
  plans: AssistancePlanRow[];
}

