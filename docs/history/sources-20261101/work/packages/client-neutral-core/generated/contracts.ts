// GENERATED FILE — do not edit by hand.
// Source of truth: JSON Schema contracts referenced by the catalog
// (.project/governance/contracts/contract-catalog.json).
// Regenerate: python scripts/ci/generate_contract_types.py
// Each `// @contract <id>` marker is consumed by
// scripts/ci/verify_contract_ssot.py to prove generated == catalog.

export type ContractId =
  "action-plan"
  | "adapter-capability"
  | "archive-manifest"
  | "blocker"
  | "capability-conformance"
  | "ci-observation"
  | "config-ownership"
  | "control-operation"
  | "control-operation-result"
  | "dashboard-projection"
  | "data-quality"
  | "domain-pack"
  | "evidence-envelope"
  | "evidence-manifest"
  | "execution-parallel-dispatch"
  | "gate-plan"
  | "gate-registry"
  | "global-agent-policy"
  | "growth-candidate"
  | "memory-record"
  | "model-policy"
  | "module-profile"
  | "observer-event"
  | "observer-pricing"
  | "platform-identity"
  | "policy-projection-contract"
  | "policy-projection-loss-report"
  | "project-profile"
  | "quick-entry-request"
  | "release-manifest"
  | "repair-pack"
  | "rule-asset"
  | "rule-drift"
  | "runtime-lock"
  | "skill-package"
  | "software-installation-identity"
  | "software-update-postflight"
  | "software-update-preflight"
  | "solution"
  | "source-ledger"
  | "task-card"
  | "task-ledger-event"
  | "workflow-evidence-envelope"
  | "workflow-observer-event"
  | "workflow-snapshot-v3"
  | "workflow-operation-progress-v1"
  | "workflow-isolated-trial-v1";

// @contract action-plan
// schema: packages/contracts/schemas/workflow/action-plan.schema.json
export type ActionPlan = {
    schema_version: "workflow/action-plan/v1",
    plan_id: string,
    task_id?: string,
    status: "DRAFT" | "WAITING_APPROVAL" | "APPROVED" | "EXECUTING" | "SUCCEEDED" | "FAILED" | "BLOCKED" | "ROLLED_BACK",
    target: {
    adapter: string,
    operation: string,
    project_root: string
  },
    steps: ({
    id: string,
    action: string,
    mode: "read" | "write" | "execute",
    side_effects: string[]
  })[],
    approval: {
    approval_required: true,
    status: "PENDING" | "APPROVED" | "REJECTED",
    approved_by?: string
  },
    rollback: {
    available: true,
    strategy: string,
    artifact?: string
  },
    constraints?: {
    allowed_paths?: string[],
    forbidden_paths?: string[],
    network?: "none" | "explicit"
  }
  };

// @contract adapter-capability
// schema: packages/contracts/schemas/workflow/client-adapter.schema.json
export type AdapterCapability = {
    schema_version: "workflow/client-adapter/v1",
    interface: ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"],
    entries: ({
    id: string,
    display_name: string,
    support_level: "deep" | "manifest-only" | "experimental" | "blocked",
    operations: ("detect" | "capabilities" | "plan" | "apply" | "invoke" | "observe" | "rollback")[],
    detection: {
    mode: "static" | "isolated" | "runtime" | "external",
    evidence_state: "NOT_RUN" | "PASS" | "FAIL" | "BLOCKED" | "UNVERIFIED" | "SKIPPED_OPTIONAL"
  }
  })[]
  };

// @contract archive-manifest
// schema: .project/governance/contracts/archive-manifest.schema.json
export type ArchiveManifest = {
    archiveId: string,
    source: string,
    classification: "product-history" | "fixture-source" | "reference-only" | "regenerate-or-exclude",
    recovery: {
    repository: string,
    refs: string[],
    verification: string
  },
    status: "planned" | "recorded" | "verified" | "blocked"
  };

// @contract blocker
// schema: packages/contracts/schemas/workflow/blocker.schema.json
export type Blocker = {
    schema_version: "workflow/blocker/v1",
    blocker_id: string,
    class: "CODE_DEFECT" | "TEST_FAILURE" | "POLICY_VIOLATION" | "APPROVAL_REQUIRED" | "MISSING_CAPABILITY" | "REMOTE_DIVERGENCE" | "CI_OUTAGE" | "CI_QUEUE_STALLED" | "CI_RATE_LIMITED" | "FLAKY_GATE" | "ENVIRONMENT_UNAVAILABLE",
    scope: "task" | "batch" | "gate" | "delivery" | "release" | "observation",
    retry_policy: "never" | "once_after_recovery" | "retry_after_retry_after" | "budgeted_diagnostic",
    fingerprint: string,
    message: string,
    created_at: string,
    resolved_at?: string | null
  };

// @contract capability-conformance
// schema: .project/governance/contracts/capability-conformance.schema.json
export type CapabilityConformance = {
    "$schema"?: string,
    schemaVersion: "work-lab/capability-conformance/v1",
    scope: ["workflow-assistance", "work-lab-observer"],
    acp: unknown,
    skills: unknown,
    mcp: unknown
  };

// @contract ci-observation
// schema: packages/contracts/schemas/workflow/ci-observation.schema.json
export type CiObservation = {
    schema_version: "workflow/ci-observation/v1",
    observation_id: string,
    repository: string,
    commit: string,
    state: "NOT_REQUESTED" | "TRIGGER_EXPECTED" | "DISCOVERING" | "QUEUED_NO_JOB" | "QUEUED_WITH_JOB" | "RUNNING" | "SUCCEEDED" | "FAILED_PRODUCT" | "FAILED_INFRASTRUCTURE" | "CI_OUTAGE" | "PLATFORM_OUTAGE" | "CI_RATE_LIMITED" | "TIMED_OUT" | "CANCELLED" | "STALE" | "BLOCKED" | "DEFERRED_CI",
    workflow?: string | null,
    run_id?: number | string | null,
    attempt?: number | null,
    queue_age_seconds?: number | null,
    job_count?: number | null,
    observed_at: string,
    next_observation_at?: string | null,
    retry_budget: number,
    message?: string
  };

// @contract config-ownership
// schema: packages/contracts/schemas/workflow/config-ownership.schema.json
export type ConfigOwnership = {
    schema_version: "workflow/config-ownership/v2",
    single_authority: true,
    note: string,
    layers: Record<string, unknown>,
    operation_modes: ("MANAGE" | "OBSERVE" | "IGNORE" | "FORBIDDEN")[],
    default_unknown: {
    mode: "OBSERVE",
    quarantine: true
  },
    adapter_defaults: Record<string, unknown>,
    fields: ({
    path: string,
    layer: string,
    mode: "MANAGE" | "OBSERVE" | "IGNORE" | "FORBIDDEN",
    adapter: string,
    scope?: string,
    apply_supported?: boolean,
    merge?: "overlay" | "replace" | "append" | "map-merge",
    safety?: "normal" | "high" | "critical",
    secret?: boolean,
    compatibility?: "compatible" | "degraded" | "breaking"
  })[],
    rules: Record<string, unknown>
  };

// @contract control-operation
// schema: packages/contracts/schemas/workflow/control-operation.schema.json
export type ControlOperation = {
    schema_version: "worklab/control-operation/v1",
    operation: "work-unit.create" | "work-unit.materialize" | "work-unit.revise" | "work-unit.dispatch" | "approval.decide" | "execution.cancel" | "execution.retry" | "execution.resume" | "config.discover" | "config.diff" | "config.apply" | "config.readback" | "config.rollback",
    project_id: string,
    task_id: string | null,
    revision: number | null,
    attempt: number | null,
    scope: {
    boundaries: string[],
    granted_by: string
  },
    expected_version: string | null,
    idempotency_key: string,
    actor: string,
    requested_at: string,
    payload: Record<string, unknown>
  };

// @contract control-operation-result
// schema: packages/contracts/schemas/workflow/control-operation-result.schema.json
export type ControlOperationResult = {
    schema_version: "worklab/control-operation-result/v1",
    operation: string,
    idempotency_key: string,
    status: "ACCEPTED" | "PLANNED" | "REFUSED" | "NEEDS_HUMAN" | "NOT_IMPLEMENTED" | "FAILED" | "READBACK_MISMATCH",
    reason_code: string,
    reason: string,
    task_id: string | null,
    receipt: {
    receipt_id: string,
    kind: string,
    observed_at: string,
    digest: string | null
  } | null,
    readback: Record<string, unknown> | null,
    evidence_level: "NO_EVIDENCE" | "SIMULATED" | "SYNTHETIC" | "INTEGRATED" | "REAL",
    observed_at: string,
    next_action: string | null
  };

// @contract dashboard-projection
// schema: apps/observer/schemas/dashboard-projection.schema.json
export type DashboardProjection = {
    schemaVersion: "work-lab/observer-projection/v2",
    mode: "LIVE" | "SNAPSHOT" | "FIXTURE" | "STALE" | "OFFLINE" | "UNKNOWN",
    generatedAt: string,
    window?: {
    from?: string,
    to?: string
  },
    freshness: {
    state: string,
    ageSeconds?: number | null,
    lastGoodAt?: string | null
  },
    summary: {
    registeredProjects: number,
    activeProjects: number,
    tasks?: Record<string, unknown>
  },
    projects: ({
    projectId: string,
    displayName?: string,
    repository?: string,
    agentPlatform?: string,
    task?: unknown,
    state: string,
    stage?: unknown,
    durationSeconds?: number | null,
    blockerSummary?: unknown,
    branch?: string,
    headSha?: unknown,
    ciState?: unknown,
    lastEventAt?: unknown,
    quality?: {
    evidenceCompleteness?: string,
    dataQuality?: string,
    freshness?: string,
    sourceRef?: string
  }
  })[],
    primaryBlocker?: Record<string, unknown> | null,
    usage: {
    inputTokens?: number | null,
    outputTokens?: number | null,
    reasoningTokens?: number | null,
    cacheReadTokens?: number | null,
    cacheWriteTokens?: number | null,
    cost?: {
    amount?: number | null,
    currency?: string | null,
    status?: string,
    billingType?: string,
    sourceRef?: unknown,
    effectiveAt?: unknown
  },
    subscriptionUsage?: string | null,
    series?: unknown[],
    quality?: {
    evidenceCompleteness?: string,
    dataQuality?: string,
    freshness?: string
  }
  },
    ci: {
    exactShaBound?: number,
    exactShaRequired?: number,
    queuedNoJob?: number,
    running?: number,
    passed?: number,
    failed?: number,
    unknown?: number,
    quality?: {
    evidenceCompleteness?: string,
    dataQuality?: string,
    freshness?: string
  }
  },
    governance: {
    rules?: {
    current?: number | null,
    drift?: number | null,
    quarantined?: number | null,
    conflicts?: number | null,
    stale?: number | null
  },
    skills?: Record<string, unknown>,
    adapters?: Record<string, unknown>,
    memoryContext?: {
    current?: number | null,
    drift?: number | null,
    quarantined?: number | null,
    conflicts?: number | null,
    stale?: number | null
  }
  },
    quality: {
    sourceCoverage: {
    numerator: number,
    denominator: number,
    scope: string
  },
    evidenceCompleteness: string,
    freshness?: string,
    unknown?: number,
    malformed?: number,
    dropped?: number,
    duplicate?: number,
    projectionLagMs?: unknown,
    lastGoodAt?: unknown
  },
    sourceRefs?: unknown[],
    mutationSurface?: {
    externalMutation?: boolean,
    ledgerMutation?: boolean,
    approvalMutation?: boolean,
    gitControl?: boolean
  }
  };

// @contract data-quality
// schema: apps/observer/schemas/data-quality.schema.json
export type DataQuality = {
    quality: "source-exact" | "deduplicated" | "partial" | "unknown",
    coverage: "full" | "partial" | "unknown",
    sourceCount: number,
    acceptedCount: number,
    rejectedCount: number,
    reason?: string
  };

// @contract domain-pack
// schema: packages/contracts/schemas/workflow/domain-pack.schema.json
export type DomainPack = {
    schema_version: "workflow/domain-pack/v1",
    pack_id: string,
    version: string,
    display_name: string,
    description: string,
    capabilities: string[],
    entrypoints: {
    human: string[],
    machine: string[]
  },
    evidence_policy: {
    minimum_level: "E0" | "E1" | "E2" | "E3" | "E4" | "E5",
    required_artifacts: string[]
  },
    safety: {
    approval_required: true,
    forbidden_paths: string[],
    redaction_required: true
  }
  };

// @contract evidence-envelope
// schema: .project/governance/contracts/evidence-envelope.schema.json
export type EvidenceEnvelope = {
    schemaVersion: "work-lab/evidence-envelope/v1",
    taskId: string,
    runId: string,
    status: "PASS" | "FAIL" | "BLOCKED" | "UNKNOWN",
    source: string,
    contentBodies?: "excluded",
    credentials?: "excluded"
  };

// @contract evidence-manifest
// schema: packages/contracts/schemas/workflow/evidence-manifest.schema.json
export type EvidenceManifest = {
    schema_version: "workflow/evidence-manifest/v1",
    manifest_id: string,
    source_identity: unknown,
    plan: {
    digest: unknown,
    base_oid: string,
    head_oid: string
  },
    evidence: ({
    gate_id: string,
    state: "PASS" | "FAIL" | "BLOCKED" | "UNVERIFIED" | "NOT_RUN" | "SKIPPED_OPTIONAL",
    coverage: "targeted" | "module" | "full" | "release",
    input_fingerprint: unknown,
    log_digest: unknown,
    started_at: string,
    completed_at: string,
    duration_ms: number
  })[],
    redaction: {
    policy: "secrets-never-stored",
    secrets_stored: false
  }
  };

// @contract execution-parallel-dispatch
// schema: packages/contracts/schemas/workflow/execution-parallel-dispatch.schema.json
export type ExecutionParallelDispatch = {
    schema_version: "workflow/execution-parallel-dispatch/v1",
    op: "NEW" | "PROMPT",
    executors: string[],
    payload?: Record<string, unknown>,
    adapter_kind?: "new" | "prompt",
    per_executor_timeout?: number,
    fail_fast?: boolean,
    status: "OK" | "PARTIAL" | "DEGRADED" | "FAILED",
    per_executor?: Record<string, unknown>,
    succeeded?: string[],
    failed?: string[],
    timed_out?: string[],
    unknown?: string[],
    events: {
    executor: string,
    phase: string,
    ts: number,
    ok: boolean,
    status: string
  }[],
    events_stream?: {
    executor: string,
    phase: string,
    ts: number,
    ok: boolean,
    status: string
  }[],
    streamed?: boolean,
    notes?: string[]
  };

// @contract gate-plan
// schema: packages/contracts/schemas/workflow/gate-plan.schema.json
export type GatePlan = {
    schema_version: "workflow/gate-plan/v1",
    plan_id: string,
    source_identity: unknown,
    changed_paths: string[],
    unclassified_paths?: {
    path: string,
    reason: string,
    needs: string
  }[],
    ci_jobs?: Record<string, unknown>,
    required_gates: string[],
    skipped_gates: {
    gate_id: string,
    reason: string
  }[],
    risk: "low" | "medium" | "high" | "critical",
    delivery_effect: "none" | "commit" | "push" | "pull_request" | "merge" | "release",
    platform_scope: string[],
    plan_digest: unknown,
    generated_at: string
  };

// @contract gate-registry
// schema: packages/contracts/schemas/workflow/gate-registry.schema.json
export type GateRegistry = {
    schema_version: "workflow/gate-registry/v1",
    gate: unknown
  };

// @contract global-agent-policy
// schema: packages/contracts/schemas/workflow/global-agent-policy.schema.json
export type GlobalAgentPolicy = {
    schema_version: "workflow/global-agent-policy/v1",
    policy_id: string,
    revision?: number,
    created?: string,
    supersedes?: string,
    ownership: {
    layer: "USER_OVERLAY",
    mode: "MANAGE",
    single_source: true,
    is_authority: false,
    note?: string
  },
    communication: {
    default_language: string,
    proceed_on_obvious_default?: boolean,
    avoid_low_value_clarification: boolean,
    ask_only_when_scope_risk_or_side_effect_changes?: boolean
  },
    execution: {
    proportionate_to_scale_and_risk: boolean,
    finish_to_closure?: boolean,
    keep_concise_plan_for_multistep?: boolean,
    one_actively_owned_item?: boolean,
    preserve_dirty_work: boolean
  },
    authority_discovery: {
    resolve_current_main_first: boolean,
    read_top_authority_before_history?: boolean,
    historical_records_non_normative: boolean,
    precedence?: string[]
  },
    authorization: {
    valid_within_task: boolean,
    grants_do_not_outlive_their_task: boolean,
    low_value_confirmation_avoided?: boolean,
    task_grant_respects_platform_hard_limits: boolean,
    explicit_side_effects_require_explicit_authorization?: boolean,
    privilege_ladder: string[]
  },
    task_grant?: {
    granular_permissions_required?: boolean,
    read_only_default?: boolean,
    side_effects_default?: string,
    cannot_override_platform_hard_limits?: boolean
  },
    workspace_boundary: {
    default_scope: string,
    keep_task_data_in_project: boolean,
    never_spill_to_user_home_or_other_projects?: boolean,
    project_local_runtime_root?: string,
    external_output_requires_exact_auth?: boolean
  },
    protected_storage: {
    protected_drives: string[],
    drive_default: "deny",
    authorization_granularity: "exact_path_and_operation",
    forbid_before_authorization?: string[]
  },
    credentials: {
    plaintext_forbidden: true,
    never_print_or_commit: true,
    session_access_default?: string,
    session_access_ladder?: string[],
    raw_body_min_needed_only?: boolean,
    project_rules_cannot_weaken_credential_boundary?: boolean
  },
    session_privacy: {
    default: string,
    minimum_necessary_access: boolean,
    redacted_summary_preferred?: boolean,
    permission_denial_is_a_correct_boundary_signal?: boolean,
    never_elevate_to_bypass_a_denied_private_path?: boolean
  },
    network: {
    public_read_scoped_to_current_sandbox_or_tool?: boolean,
    authenticated_write_requires_auth?: boolean,
    upload_requires_auth?: boolean,
    paid_model_call_requires_auth?: boolean,
    paid_service_requires_auth?: boolean
  },
    git_safety: {
    preserve_dirty_work: boolean,
    stage_owned_changes_only: boolean,
    no_default_git_add_all: boolean,
    no_default_reset_or_clean?: boolean,
    no_force_push_default: boolean,
    do_not_rewrite_history_default?: boolean
  },
    dependency_policy?: {
    prefer_project_interpreter_and_locked_deps?: boolean,
    lockfile_regeneration_is_destructive?: boolean,
    save_exact_diff_before_regenerating?: boolean,
    no_unsolicited_new_dependencies?: boolean
  },
    evidence_semantics: {
    unknown_is_zero: false,
    unknown_is_success: false,
    simulated_is_real: false,
    local_test_is_ci: false,
    build_is_runtime: false,
    merge_is_installed: false,
    plan_equals_write: false,
    apply_equals_verified: false,
    real_evidence_requires_readback: true,
    missing_is_unknown_never_fabricated?: boolean,
    evidence_levels?: string[]
  },
    verification: {
    report_layers_independently: boolean,
    structural_check_separate_from_runtime?: boolean,
    failed_or_skipped_required_check_is_not_pass?: boolean,
    honest_status_vocabulary: string[],
    independent_readback_required_for_verified?: boolean
  },
    parallelism: {
    independent_reads: string,
    isolated_writers?: string,
    overlapping_writes: "serial",
    one_writer_owns_a_checkout: boolean
  },
    skills?: {
    scan_before_executing?: boolean,
    load_matching_skill_before_manual_attempt?: boolean,
    complex_techniques_are_on_demand_skills_not_global_policy?: boolean,
    skill_is_guidance_not_authorization?: boolean
  },
    model_neutrality: {
    preserve_user_provider: true,
    preserve_user_model: true,
    preserve_user_reasoning: true,
    preserve_user_auth: true,
    no_hardcoded_model_id_default: true,
    no_global_cost_or_rate_clamp_default?: boolean,
    user_model_is_user_owned_not_worklab_managed: true
  },
    tool_truth?: {
    use_real_command_output?: boolean,
    never_fabricate_or_invent_state?: boolean,
    do_not_invent_files_apis_or_commands?: boolean,
    keep_working_until_verified_or_exact_blocker?: boolean
  },
    historical_record_policy?: {
    frozen_and_non_normative?: boolean,
    current_authority_first?: boolean,
    never_bulk_search_history_by_default?: boolean,
    history_retrievable_from_frozen_commit?: boolean
  }
  };

// @contract growth-candidate
// schema: packages/contracts/schemas/workflow/growth-candidate.schema.json
export type GrowthCandidate = {
    schema_version: "workflow/growth-candidate/v1",
    candidateId: string,
    origin: string,
    classification: "curator" | "learn" | "manual" | "hub" | "upstream" | "deployment",
    status: "discovered" | "isolated" | "scanned" | "evaluated" | "candidate" | "approved" | "blocked" | "retired",
    risk: "low" | "medium" | "high" | "critical",
    sourceDigest?: string
  };

// @contract memory-record
// schema: packages/contracts/schemas/workflow/memory-record.schema.json
export type MemoryRecord = {
    schema_version: "workflow/runtime-context-record/v1",
    ttlSeconds: number,
    authoritative: false,
    memory_id: string,
    layer: "ephemeral" | "session" | "project" | "domain" | "global",
    kind: "fact" | "preference" | "procedure" | "candidate" | "event",
    status: "observed" | "proposed" | "approved" | "blocked" | "retired",
    project_id: string,
    scope?: "project" | "domain" | "global",
    valid_from?: string | null,
    valid_to?: string | null,
    ttl_days?: number | null,
    supersedes?: string | null,
    conflicts_with?: string[] | null,
    last_used_at?: string | null,
    pinned_context?: boolean,
    source_digest: string,
    content_digest: string,
    confidence: "low" | "medium" | "high",
    promotion: "never" | "manual-approval",
    redaction: {
    prompt_response_bodies: "excluded",
    credentials: "excluded"
  }
  };

// @contract model-policy
// schema: packages/contracts/schemas/workflow/model-policy.schema.json
export type ModelPolicy = {
    schema_version: "workflow/model-policy/v1",
    policy_id: string,
    task_class: "planning" | "coding" | "review" | "observer" | "design" | "recovery",
    model_class: "reasoning" | "general" | "fast" | "local" | "unknown",
    selection: "user-selected" | "capability-match" | "offline-fixture" | "unavailable",
    context_budget: {
    input_tokens: number,
    output_tokens: number,
    reserved_tokens: number,
    overflow: "fail-closed" | "summarize" | "drop-oldest"
  },
    cost: {
    mode: "unknown" | "estimated" | "subscription" | "not-metered" | "reconciled",
    currency?: string,
    unit_price_per_million_tokens?: number,
    effective_at?: string,
    source: string
  },
    redaction: {
    prompt_response_bodies: "excluded",
    credentials: "excluded"
  },
    degradation: "unknown-when-unavailable" | "blocked-when-unavailable"
  };

// @contract module-profile
// schema: .project/governance/contracts/module-profile.schema.json
export type ModuleProfile = {
    schemaVersion: "work-lab/module-profile/v1",
    id: string,
    path: string,
    owner: string,
    role: string,
    releasePrefix: string,
    dependsOn: string[],
    evidencePath?: string,
    externalMutationDefault?: false
  };

// @contract observer-event
// schema: apps/observer/schemas/observer-event.schema.json
export type ObserverEvent = {
    eventId: string,
    schemaVersion: "work-lab/observer-event/v1",
    eventType: string,
    sourceModule: string,
    sourceId?: string,
    projectId?: string,
    taskId?: string,
    taskTitle?: string,
    runId?: string,
    observedAt: string,
    occurredAt?: string,
    originId?: string,
    causationId?: string,
    correlationId?: string,
    contentDigest: string,
    coverage?: "full" | "partial" | "unknown",
    quality: "source-exact" | "deduplicated" | "partial" | "unknown",
    usage?: {
    input_tokens: number | null,
    output_tokens: number | null,
    total_tokens: number | null,
    records: number | null,
    observation_state: "observed" | "estimated" | "unknown"
  },
    evidenceRefs?: string[],
    telemetry?: {
    operation?: string,
    provider?: string,
    model?: string,
    input_tokens?: number,
    output_tokens?: number,
    total_tokens?: number,
    reasoning_tokens?: number,
    latency_ms?: number,
    cache_read_tokens?: number,
    cache_write_tokens?: number,
    outcome?: string,
    error_class?: string
  }
  };

// @contract observer-pricing
// schema: apps/observer/schemas/observer-pricing.schema.json
export type ObserverPricing = Record<string, unknown>;

// @contract platform-identity
// schema: packages/contracts/schemas/workflow/platform-identity.schema.json
export type PlatformIdentity = {
    schema_version: "workflow/platform-identity/v1",
    platform_id: string,
    logical_instance_id: string,
    package_identity: string,
    publisher: string,
    install_channel: "store" | "official-installer" | "package-manager" | "portable" | "source" | "unknown",
    executable_realpath: string,
    binary_digest: string,
    discovered_version: string,
    launcher_id: string,
    launcher_target: string,
    arguments: string[],
    working_directory: string,
    effective_config_root: string,
    profile_id: string,
    user_context: "current-user" | "service-user" | "unknown",
    capabilities: string[],
    evidence_source: string[],
    observed_at: string,
    freshness: "CURRENT" | "STALE" | "UNKNOWN",
    state: "UNIQUE" | "ALIAS_DUPLICATE" | "STALE_SHORTCUT" | "CONFIG_SPLIT" | "VERSION_COLLISION" | "DUAL_INSTALLATION" | "PROFILE_SPLIT" | "IDENTITY_AMBIGUOUS" | "UNAVAILABLE"
  };

// @contract policy-projection-contract
// schema: packages/contracts/schemas/workflow/policy-projection-contract.schema.json
export type PolicyProjectionContract = {
    schema_version: "workflow/policy-projection-contract/v1",
    adapter: string,
    policy_version: string,
    renderer: string,
    capability_states: Record<string, unknown>,
    detect_supported?: boolean,
    plan_supported?: boolean,
    apply_supported?: boolean,
    readback_supported?: boolean,
    rollback_supported?: boolean,
    drift_supported?: boolean,
    native_targets?: string[],
    extensions_path?: string,
    loss_report?: Record<string, unknown> | null
  };

// @contract policy-projection-loss-report
// schema: packages/contracts/schemas/workflow/policy-projection-loss-report.schema.json
export type PolicyProjectionLossReport = {
    schema_version: "workflow/policy-projection-loss-report/v1",
    adapter: string,
    policy_version: string,
    projection_state?: "UNSUPPORTED" | "DETECTED" | "PLANNED" | "WAITING_AUTHORIZATION" | "APPLIED" | "APPLIED_UNVERIFIED" | "READBACK_VERIFIED" | "DRIFT" | "ROLLBACK_REQUIRED" | "ROLLBACK_VERIFIED",
    native_enforced: string[],
    native_guidance: string[],
    workflow_guard: string[],
    observe_only: string[],
    unsupported: string[],
    readback_verified?: boolean,
    notes?: string
  };

// @contract project-profile
// schema: packages/contracts/schemas/workflow/project-profile.schema.json
export type ProjectProfile = {
    schema_version: "workflow/project-profile/v1",
    project: {
    id: string,
    root_policy: "discover_git_root" | "explicit_git_root",
    windows_native_first: boolean
  },
    configuration: {
    precedence: ("global_defaults" | "project_profile" | "local_runtime" | "environment" | "cli")[]
  },
    modules: Record<string, unknown>,
    risk_zones: Record<string, unknown>,
    gates: Record<string, unknown>,
    ci: {
    stable_aggregate_check: string,
    stable_aggregate_job?: string,
    workflow_file?: string,
    workflow_name?: string,
    release_workflow?: string,
    observation_privacy_policy?: string,
    watcher_policy?: {
    base_delay_seconds?: number,
    max_delay_seconds?: number,
    observation_window_seconds?: number,
    queue_stall_seconds?: number,
    retry_budget?: number
  },
    exact_sha_required_for: string[],
    outage_blocks: string[]
  }
  };

// @contract quick-entry-request
// schema: packages/contracts/schemas/workflow/quick-entry-request.schema.json
export type QuickEntryRequest = {
    schema_version: "work-lab/quick-entry-request/v1",
    requestId: string,
    verb: "publish" | "view" | "resume" | "adjust" | "return",
    input: {
    baseRevision: string,
    currentRevision: string
  },
    project: {
    projectId: string
  },
    permission: {
    mode: "observe" | "propose" | "execute",
    reason?: string
  },
    client: {
    hostId: string,
    declaredAvailable?: boolean
  },
    recovery?: {
    attempt: number,
    previousOutcome?: "FAILED" | "TIMED_OUT" | "PARTIAL" | "ABANDONED",
    carriedForward?: string[]
  },
    cancellation?: {
    requested: boolean,
    sideEffectsAlreadyMade?: boolean
  }
  };

// @contract release-manifest
// schema: .project/governance/contracts/release-manifest.schema.json
export type ReleaseManifest = {
    schemaVersion: "work-lab/release-manifest/v1",
    releaseId: string,
    module: string,
    version: string,
    source: {
    repository: string,
    commit: string
  },
    artifacts: {
    path: string,
    sha256: string
  }[],
    evidence: string[],
    approval: {
    status: "PENDING" | "APPROVED" | "REJECTED",
    scope?: string
  }
  };

// @contract repair-pack
// schema: packages/contracts/schemas/workflow/repair-pack.schema.json
export type RepairPack = {
    schemaVersion: "workflow/repair-pack/v1",
    packId: string,
    generatedAt: string,
    status: "WAITING_APPROVAL" | "BLOCKED",
    readiness: {
    state: "READY" | "BLOCKED",
    reasons: ("no-open-issues" | "adapter-not-declared" | "adapter-does-not-declare-invoke" | "project-unregistered" | "project-root-missing" | "issue-has-no-project" | "verification-command-unknown" | "pack-cap-reached")[]
  },
    target: {
    kind: "ADAPTER_INVOKE" | "MANUAL_COPY",
    projectId: string,
    projectName: string | null,
    projectRoot: string,
    projectStatus: string | null,
    adapter: string | null,
    adapterDisplayName: string | null,
    adapterSupportLevel: string | null,
    declaredOperations: ("detect" | "capabilities" | "plan" | "apply" | "invoke" | "observe" | "rollback")[],
    operation: "invoke" | "copy-handoff",
    routingSource: "caller-choice"
  },
    binds: {
    issueFingerprints: string[],
    evidenceRefs: string[],
    classes: ("SOURCE_CIRCUIT_OPEN" | "SOURCE_REFUSAL" | "SOURCE_FAILURE" | "SOURCE_DATA_DROPPED" | "SOURCE_STALE" | "SOURCE_INCOMPLETE_COVERAGE" | "EXECUTION_STALLED" | "EXECUTION_CONFLICT" | "TASK_BLOCKED" | "TASK_FAILED")[],
    priorities: ("P1" | "P2" | "P3")[],
    issueCount: number,
    softwareIds: string[],
    unattributedCount: number
  },
    verification: {
    known: boolean,
    command: string,
    basis: string
  },
    handoff: {
    mode: "manual-copy",
    copyable: true,
    sent: false,
    dispatched: false,
    copiedByUser: {
    declared: false,
    declaredAt: unknown,
    channel: unknown
  },
    userDeclaredHandoff: {
    declared: false,
    declaredAt: unknown,
    channel: unknown,
    claimedRecipient: unknown
  },
    externalReceipt: {
    received: false,
    receivedAt: unknown,
    externalId: unknown,
    source: unknown
  },
    authorizationRef: unknown,
    requiresOwnerAction: string
  },
    provenance: {
    derivationScope: "open-issue-rows-plus-registered-projects-plus-adapter-registry" | "open-issue-rows-plus-registered-projects",
    inferencePerformed: false,
    contentIncluded: false,
    authorityClaimed: false,
    applied: false
  },
    plan: {
    schema_version: "workflow/action-plan/v1",
    plan_id: string,
    task_id?: string,
    status: "DRAFT" | "WAITING_APPROVAL" | "APPROVED" | "EXECUTING" | "SUCCEEDED" | "FAILED" | "BLOCKED" | "ROLLED_BACK",
    target: {
    adapter: string,
    operation: string,
    project_root: string
  },
    steps: ({
    id: string,
    action: string,
    mode: "read" | "write" | "execute",
    side_effects: string[]
  })[],
    approval: {
    approval_required: true,
    status: "PENDING" | "APPROVED" | "REJECTED",
    approved_by?: string
  },
    rollback: {
    available: true,
    strategy: string,
    artifact?: string
  },
    constraints?: {
    allowed_paths?: string[],
    forbidden_paths?: string[],
    network?: "none" | "explicit"
  }
  }
  };

// @contract rule-asset
// schema: packages/contracts/schemas/workflow/rule-asset.schema.json
export type RuleAsset = {
    schema_version: "workflow/rule-asset/v1",
    id: string,
    version: string,
    origin: string,
    scope: "session" | "project" | "domain" | "client" | "global",
    risk: "low" | "medium" | "high" | "critical",
    status: "candidate" | "isolated" | "approved" | "deployed" | "blocked" | "retired",
    packageDigest?: string
  };

// @contract rule-drift
// schema: packages/contracts/schemas/workflow/rule-drift.schema.json
export type RuleDrift = {
    schema_version: "workflow/rule-drift/v1",
    drift_id: string,
    rule_id: string,
    baseline_digest: string | null,
    observed_digest: string | null,
    state: "unchanged" | "changed" | "missing" | "new",
    severity: "info" | "medium" | "high",
    action: "report-only" | "quarantine" | "manual-review"
  };

// @contract runtime-lock
// schema: .project/governance/contracts/runtime-lock.schema.json
export type RuntimeLock = {
    schemaVersion: "work-lab/runtime-lock/v1",
    runId: string,
    root: Record<string, unknown>,
    modules: Record<string, unknown>
  };

// @contract skill-package
// schema: packages/contracts/schemas/workflow/skill-package.schema.json
export type SkillPackage = {
    schema_version: "workflow/skill-package/v1",
    id: string,
    version: string,
    source: string,
    packageDigest: string,
    status: "candidate" | "isolated" | "approved" | "deployed" | "blocked" | "retired",
    risk?: "low" | "medium" | "high" | "critical"
  };

// @contract software-installation-identity
// schema: packages/contracts/schemas/workflow/software-installation-identity.schema.json
export type SoftwareInstallationIdentity = {
    schema_version: "workflow/software-installation-identity/v1",
    software_id: string,
    package_identity?: string | null,
    installed: boolean,
    install_type?: "community_desktop_release" | "isolated_source_checkout" | "native_package_manager" | "os_managed" | "store_appx" | "portable" | "unknown" | null | null,
    install_root?: string | null,
    executable_realpath?: string | null,
    launcher_targets?: (string | null)[],
    config_root?: string | null,
    data_root?: string | null,
    cache_root?: string | null,
    runtime_root?: string | null,
    discovered_version?: string | null,
    release_channel?: "stable" | "beta" | "canary" | "dev" | "unknown" | null | null,
    active_process_path?: string | null,
    discovery_sources?: ("user_declared" | "observed_existing" | "os_registered" | "package_manager" | "project_adapter_known_candidate" | "running_process" | "start_menu_launcher" | "desktop_launcher" | "vendor_default" | "worklab_recommended" | "none")[],
    user_declared_location?: string | null,
    observed_existing_location?: string | null,
    os_registered_location?: string | null,
    location_status: "NOT_INSTALLED" | "SINGLE_VERIFIED" | "SINGLE_UNVERIFIED" | "LOCATION_DRIFT" | "DUAL_INSTALLATION" | "MISSING_EXPECTED_INSTALL" | "RELOCATION_REQUESTED" | "OS_MANAGED",
    location_basis?: string | null,
    binary_digest?: string | null,
    verified_at?: string | null
  };

// @contract software-update-postflight
// schema: packages/contracts/schemas/workflow/software-update-postflight.schema.json
export type SoftwareUpdatePostflight = {
    schema_version: "workflow/software-update-postflight/v1",
    software_id: string,
    target_version: string,
    before: Record<string, unknown>,
    after: Record<string, unknown>,
    checks: ({
    name: "version_readback" | "body_integrity" | "launcher_pinning" | "data_root_pinning" | "c_residue" | "runtime_health" | "location_readback",
    status: "PASS" | "FAIL" | "UNVERIFIED",
    expected: unknown,
    observed: unknown
  })[],
    location_readback_passed: boolean,
    overall: "PASS" | "FAIL" | "PENDING",
    reasons: ("POSTFLIGHT_ALL_CHECKS_PASS" | "VERSION_READBACK_FAIL" | "BODY_INTEGRITY_FAIL" | "LAUNCHER_PINNING_FAIL" | "DATA_ROOT_PINNING_FAIL" | "C_RESIDUE_DETECTED" | "LOCATION_READBACK_FAIL" | "RUNTIME_HEALTH_UNVERIFIED" | "RUNTIME_HEALTH_FAIL" | "POSTFLIGHT_INCOMPLETE")[]
  };

// @contract software-update-preflight
// schema: packages/contracts/schemas/workflow/software-update-preflight.schema.json
export type SoftwareUpdatePreflight = {
    schema_version: "workflow/software-update-preflight/v1",
    software_id: string,
    update_mode: "IN_PLACE_ONLY" | "RELOCATION" | "FRESH_INSTALL" | "BLOCKED" | "PRESERVE_OFFICIAL_CHANNEL",
    location_status: "NOT_INSTALLED" | "SINGLE_VERIFIED" | "SINGLE_UNVERIFIED" | "LOCATION_DRIFT" | "DUAL_INSTALLATION" | "MISSING_EXPECTED_INSTALL" | "RELOCATION_REQUESTED" | "OS_MANAGED",
    approved_operation?: "UPDATE" | "RELOCATION" | null | null,
    relocation_approved?: boolean,
    before?: {
    install_root: string | null,
    executable_realpath: string | null,
    launcher?: string | null,
    version?: string | null
  },
    after?: {
    install_root: string | null,
    executable_realpath: string | null,
    launcher?: string | null,
    version?: string | null
  },
    location_readback_required: boolean,
    location_readback_passed?: boolean | null,
    overall?: "PASS" | "FAIL" | "PENDING",
    reasons?: ("IN_PLACE_UPDATE_OK" | "INSTALL_ROOT_CHANGE_REQUIRES_EXPLICIT_RELOCATION" | "DUAL_INSTALLATION_UPDATE_BLOCKED" | "LOCATION_DRIFT_UPDATE_BLOCKED" | "MISSING_EXPECTED_INSTALL_NO_VENDOR_FALLBACK" | "SINGLE_UNVERIFIED_IDENTITY_VALIDATION_FIRST" | "OS_MANAGED_PRESERVE_OFFICIAL_CHANNEL" | "LOCATION_READBACK_FAIL" | "RELOCATION_APPROVED" | "RELOCATION_NOT_APPROVED")[]
  };

// @contract solution
// schema: packages/contracts/schemas/workflow/solution.schema.json
export type Solution = {
    schemaVersion: "workflow/solution/v1",
    solutionId: string,
    revision: number,
    title: string,
    status: "VERIFIED" | "UNVERIFIED",
    software: {
    softwareId: string,
    softwareVersion: string,
    platform: string,
    versionSource: "MEASURED" | "DECLARED" | "UNKNOWN"
  },
    source: {
    kind: "REPAIR_RECORD" | "MANUAL",
    ref: string,
    updatedAt: string
  },
    preconditions: string[],
    steps: string[],
    expected: string[],
    verificationSteps: string[],
    invalidWhen: string[],
    risks: {
    risk: string,
    recovery: string
  }[],
    limits: string[],
    evidenceRefs: string[],
    issueRefs: string[],
    keywords: string[],
    recommended: boolean,
    supersedes: {
    solutionId: string,
    revision: number
  } | null,
    changes: string
  };

// @contract source-ledger
// schema: .project/governance/contracts/source-ledger.schema.json
export type SourceLedger = {
    "$schema"?: string,
    schemaVersion: "work-lab/source-ledger/v4",
    ledgerVersion: 4,
    scope: ["workflow-assistance", "work-lab-observer"],
    entries: unknown[]
  };

// @contract task-card
// schema: packages/contracts/schemas/workflow/task-card.schema.json
export type TaskCard = {
    schema_version: "work-lab/task-card/v1",
    id: string,
    title: string,
    scope: string,
    action: string,
    acceptance: string,
    phase?: string,
    priority?: "P0" | "P1" | "P2" | "P3",
    constraints?: string[]
  };

// @contract task-ledger-event
// schema: packages/contracts/schemas/workflow/run-event.schema.json
export type TaskLedgerEvent = {
    schema_version: "workflow/run-event/v1",
    event_id: string,
    run_id: string,
    task_id: string,
    phase: "planning" | "approval" | "execution" | "observation" | "delivery" | "review" | "rollback",
    status: "QUEUED" | "PLANNING" | "WAITING_APPROVAL" | "RUNNING" | "RETRYING" | "PAUSED" | "BLOCKED" | "REVIEWING" | "COMPLETED" | "FAILED" | "CANCELLED",
    timestamp: string,
    sequence?: number,
    payload?: {
    adapter?: string,
    operation?: string,
    checkpoint?: string,
    error_code?: string
  }
  };

// @contract workflow-evidence-envelope
// schema: packages/contracts/schemas/workflow/evidence-envelope.schema.json
export type WorkflowEvidenceEnvelope = {
    schema_version: "workflow/evidence-envelope/v1",
    evidence_id: string,
    task_id: string,
    state: "NOT_RUN" | "PASS" | "FAIL" | "BLOCKED" | "UNVERIFIED" | "SKIPPED_OPTIONAL",
    level: "E0" | "E1" | "E2" | "E3" | "E4" | "E5",
    source: {
    kind: "static" | "isolated" | "runtime" | "ci" | "external",
    identity: string
  },
    artifacts: {
    path: string,
    sha256: string,
    kind: string,
    size?: number
  }[],
    redaction: {
    policy: "secrets-never-stored",
    secrets_stored: false,
    notes?: string
  },
    checks?: string[],
    message?: string
  };

// @contract workflow-observer-event
// schema: packages/contracts/schemas/workflow/observer-event.schema.json
export type WorkflowObserverEvent = {
    schema_version: "workflow/observer-event/v1",
    sequence: number,
    event_id: string,
    run_id: string,
    task_id: string,
    event_type: string,
    occurred_at: string,
    source: string,
    projection_key?: string,
    payload: Record<string, unknown>
  };

// @contract workflow-snapshot-v3
// schema: packages/contracts/schemas/workflow/snapshot-v3.schema.json
export type WorkflowSnapshotV3 = {
    schemaVersion: "workflow/snapshot/v3",
    revision: number,
    generatedAt: string,
    sourceWatermark: string | null,
    transport: {
    transportState: "LIVE" | "DELAYED" | "OFFLINE" | "CONNECTING" | "UNKNOWN",
    freshnessState: "FRESH" | "STALE" | "UNKNOWN",
    eventsUrl?: string | null,
    connectedSince?: string | null,
    lastHeartbeatAt?: string | null,
    writerWatermarkAt?: string | null,
    eventStreamConnected?: boolean
  },
    coverage: {
    numerator: number | null,
    denominator: number | null,
    scope: string | null
  },
    governance: {
    state: "CLEAN" | "DRIFT" | "UNKNOWN",
    families: Record<string, unknown>
  },
    workspace: Record<string, unknown>,
    projects: ({
    projectId: string,
    agentPlatform: string | null,
    displayName: string | null,
    identityState: string,
    activityState: "ACTIVE" | "REGISTERED" | "IDLE" | "UNKNOWN",
    attentionState: string,
    activeExecutionCount: number,
    workingAreas: string[],
    visibility: string,
    quality: string,
    lastStrongEvidenceAt: string | null,
    repositories: unknown[],
    git: {
    localSha?: string | null,
    remoteSha?: string | null,
    matchState: "MATCH" | "LOCAL_REMOTE_MATCH" | "LOCAL_CI_MATCH" | "NO_LOCAL_CLAIM" | "UNVERIFIED" | "MISMATCH",
    branch?: string | null,
    dirtyCount?: number | null,
    observedAt?: string | null,
    quality?: string | null,
    freshness?: string | null,
    sourceRef?: string | null,
    sourceProjectId?: string | null
  },
    token: {
    inputTokens?: number | null,
    outputTokens?: number | null,
    totalTokens?: number | null,
    costQuality: "EXACT" | "ESTIMATED" | "UNKNOWN"
  },
    ci: ({
    runId: string | null,
    projectId: string,
    workflow: string | null,
    headSha: string | null,
    status: string | null,
    conclusion: string | null,
    sourceRef: string | null
  })[],
    executionIds: string[],
    sourceRefs: string[]
  })[],
    executions: ({
    executionId: string,
    state: "RUNNING" | "STARTING" | "WAITING_USER" | "WAITING_APPROVAL" | "BLOCKED" | "COMPLETED" | "FAILED" | "UNKNOWN",
    anchorProjectId?: string | null
  })[],
    tasks: Record<string, unknown>,
    tokenSummary: {
    inputTokens?: number | null,
    outputTokens?: number | null,
    totalTokens?: number | null,
    costQuality: "EXACT" | "ESTIMATED" | "UNKNOWN"
  },
    git: {
    localSha?: string | null,
    remoteSha?: string | null,
    ciSha?: string | null,
    matchState: "MATCH" | "LOCAL_REMOTE_MATCH" | "LOCAL_CI_MATCH" | "NO_LOCAL_CLAIM" | "UNVERIFIED" | "MISMATCH",
    branch?: string | null,
    dirtyCount?: number | null,
    observedAt?: string | null,
    quality?: string | null,
    freshness?: string | null,
    sourceRef?: string | null
  },
    ci: ({
    runId: string | null,
    workflow: string | null,
    headSha: string | null,
    status: string | null,
    conclusion: string | null,
    sourceRef: string | null
  })[],
    sourceRefs: (string | null)[],
    software?: {
    softwareId: string,
    locationStatus?: string,
    duplicateInstallation?: boolean
  }[],
    taskRecords?: ({
    taskId: string,
    projectId: string,
    status: string,
    fencingToken?: number | null,
    checkpointPresent: boolean,
    checkpointKeys: string[],
    checkpointDigest?: string | null,
    createdAt?: string | null,
    updatedAt?: string | null,
    leaseHolder?: string | null,
    leaseExpiresAt?: string | null,
    register?: {
    source: "OPEN_TASK_REGISTER",
    state: "READ" | "UNREADABLE" | "ID_CONFLICT",
    priority: string | null,
    work: string,
    workChars: number,
    workTruncated: boolean,
    cellsRealigned: boolean,
    evidenceRef: string,
    reason: string | null
  } | null
  })[],
    adapterCapabilities?: ({
    clientId: string,
    layers: ({
    layer: "REGISTERED" | "INSTALLED" | "LOADED_CONNECTED" | "QUALIFIED" | "ENABLED_FOR_TASK" | "NATIVE_PROJECTION" | "OBSERVED_IN_EXECUTION",
    state: "MET" | "NOT_PROBED" | "NOT_SUPPORTED"
  })[],
    role?: "agent_runtime" | "provider_router" | "vcs_host" | "design_client" | "UNKNOWN"
  })[],
    artifactHandles?: ({
    handle: string,
    surface: string,
    kind: string,
    sizeBytes?: number | null,
    modifiedAt?: string | null,
    surfaceRoot?: string,
    digestRecorded?: boolean
  })[],
    artifactHandlesSummary?: {
    schemaVersion: string,
    cap: number,
    enumeratedCount: number,
    projectedCount: number,
    omittedCount: number,
    truncated: boolean,
    complete?: boolean,
    orderingKey: string,
    refused?: Record<string, unknown>
  },
    issues?: ({
    schemaVersion: "workflow/issue/v1",
    fingerprint: string,
    class: "SOURCE_CIRCUIT_OPEN" | "SOURCE_REFUSAL" | "SOURCE_FAILURE" | "SOURCE_DATA_DROPPED" | "SOURCE_STALE" | "SOURCE_INCOMPLETE_COVERAGE" | "EXECUTION_STALLED" | "EXECUTION_CONFLICT" | "TASK_BLOCKED" | "TASK_FAILED",
    projectId?: string | null,
    subject?: string,
    origin: string,
    evidenceRef: string,
    priority: "P1" | "P2" | "P3",
    priorityRule: string,
    safeToReread?: boolean,
    firstSeenAt?: string | null,
    lastSeenAt?: string | null,
    occurrences: number,
    magnitude?: Record<string, unknown>,
    detail?: string,
    status: "OPEN",
    softwareId: string | null,
    softwareVersion: string | null,
    softwareVersionSource: "discovered" | "not-discovered" | "unmatched" | "ambiguous" | "source-names-no-software" | "identity-source-absent"
  })[],
    issuesSummary?: {
    schemaVersion: "worklab/issues-summary/v1",
    generatedAt?: string,
    sources?: ({
    source: string,
    state: "read" | "absent" | "error",
    rowsScanned?: number | null,
    issuesDerived?: number | null
  })[],
    sourcesRead: number,
    sourcesAbsent: number,
    rowsScanned: number,
    scanLimits?: {
    telemetry_events?: number | null
  },
    scanTruncated?: {
    telemetry_events?: boolean
  },
    distinctIssueCount: number,
    emittedCount: number,
    omittedCount: number,
    foldedOccurrences: number,
    cap: number,
    truncated: boolean,
    complete?: boolean,
    softwareAttribution: {
    attributed: number,
    unmatched: number,
    ambiguous: number,
    unattributable: number,
    versionKnown: number,
    identitySourceAbsent: boolean
  },
    priorityCounts?: {
    P1?: number,
    P2?: number,
    P3?: number
  },
    classesPresent?: string[],
    classVocabulary?: string[],
    projectsCovered?: (string | null)[],
    unattributedCount?: number,
    order?: string,
    orderingKey: string,
    orderingRule?: string,
    derivationScope?: "canonical-store-facts-only",
    inferencePerformed?: false,
    contentIncluded?: false,
    sourceErrors?: string[],
    cost?: {
    elapsedMs?: number
  }
  },
    operationProgress?: ({
    schema_version: "worklab/operation-progress/v1",
    task_id: string | null,
    observed_at: string,
    state: string,
    ledger_status: string | null,
    last_trusted_progress: {
    state: string | null,
    at: string | null,
    basis: string
  },
    transport_state: string | null,
    producer_gaps: string[],
    sourceTimes?: Record<string, unknown> | null,
    target_behaviour?: Record<string, unknown> | null
  })[],
    isolatedTrials?: ({
    schema_version: "worklab/isolated-trial/v1",
    trial_id: string | null,
    parent_task_id: string | null,
    child_task_id: string | null,
    observed_at: string,
    isolation: Record<string, unknown>,
    separated_results: {
    write: {
    status: string,
    basis: string,
    note: string
  },
    native_readback: {
    status: string,
    basis: string,
    note: string
  },
    target_behaviour: {
    status: string,
    basis: string,
    note: string
  }
  },
    producer_gaps: string[]
  })[],
    collectors?: ({
    collector: string,
    totalRuns: number,
    lastRunAt: string | null,
    lastSuccessAt: string | null,
    consecutiveFailures: number,
    circuitOpen: boolean,
    droppedEvents: number,
    refusedRows: number,
    deliveredRows: number,
    lastRefusalReason: string | null,
    fresh: boolean
  })[]
  };

// @contract workflow-operation-progress-v1
// schema: packages/contracts/schemas/workflow/operation-progress.schema.json
export type WorkflowOperationProgressV1 = {
    schema_version: "worklab/operation-progress/v1",
    task_id: string,
    observed_at: string,
    state: "NOT_STARTED" | "QUEUED" | "PLANNING" | "WAITING_APPROVAL" | "RUNNING" | "RETRYING" | "PAUSED" | "BLOCKED" | "REVIEWING" | "PASSED" | "FAILED" | "CANCELLED" | "UNKNOWN_OR_TIMEOUT" | "UNKNOWN",
    ledger_status: string | null,
    last_trusted_progress: {
    state: string | null,
    at: string | null,
    basis: "LEDGER_UPDATED_AT" | "LEDGER_HEARTBEAT" | "NONE"
  },
    transport_state: string | null,
    producer_gaps: ("SUBMITTING_STAGE" | "TARGET_BEHAVIOUR_CONFIRMATION" | "TRIAL_ISOLATION" | "DURATION" | "PROGRESS_SEQUENCE")[],
    sourceTimes: {
    createdAt: string | null,
    updatedAt: string | null,
    heartbeatAt: string | null
  },
    target_behaviour?: "CONFIRMED" | "PENDING" | "ABSENT" | "CONFLICT" | null | null
  };

// @contract workflow-isolated-trial-v1
// schema: packages/contracts/schemas/workflow/isolated-trial.schema.json
export type WorkflowIsolatedTrialV1 = {
    schema_version: "worklab/isolated-trial/v1",
    trial_id: string,
    parent_task_id: string,
    child_task_id: string | null,
    observed_at: string,
    isolation: {
    basis: "WORKTREE_ID" | "SESSION_ID" | "NONE",
    value: string | null
  },
    separated_results: {
    write: unknown,
    native_readback: unknown,
    target_behaviour: unknown
  },
    producer_gaps: ("SUBMITTING_STAGE" | "TRIAL_ISOLATION" | "NATIVE_READBACK" | "DURATION" | "TARGET_BEHAVIOUR_CONFIRMATION" | "REUSE_OF_SOURCE_RESULT")[]
  };

