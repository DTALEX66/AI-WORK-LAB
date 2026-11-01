/** UI design semantics only. Map these fields to existing WORK-LAB contracts.
 * This file neither grants permissions nor declares a production API. */
export type Precision = 'exact' | 'estimated' | 'mixed' | 'unknown';
export type Completeness = 'complete_scope' | 'known_subset' | 'unknown';
export type MetricUnit = 'token' | 'credit' | 'currency' | 'byte' | 'second' | 'count' | 'ratio';
export interface SourceRef {
  namespace: string;
  sourceId: string;
  revision: string | null;
  eventAt: string | null;
  emittedAt: string | null;
  receivedAt: string | null;
  sequence: string | null;
  historyReadback: 'supported' | 'unsupported' | 'unknown';
}
export type ObservedValue =
  | {kind: 'value'; value: number; unit: MetricUnit; precision: Precision; completeness: Completeness; scope: string; source: SourceRef}
  | {kind: 'missing' | 'unsupported' | 'privacy_hidden'; value: null; unit: MetricUnit; reason: string; source: SourceRef | null}
  | {kind: 'not_computable'; value: null; unit: 'ratio'; reason: 'zero_denominator' | 'unknown_denominator' | 'incompatible_scope'};
export interface ProjectSummary {
  projectId: string;
  displayName: string;
  directories: readonly {directoryId: string; displayPath: string; role: 'primary' | 'worktree' | 'related'}[];
  softwareParticipants: readonly Participant[];
  work: readonly string[]; // Keep multiple states; translate from actual contract.
  health: string;
  observation: string;
  latestVisibleSource: SourceRef | null;
  usage: readonly ObservedValue[];
  collaboration: CollaborationSummary | null;
}
export interface Participant {
  installationId: string;
  runtimeInstanceId: string | null;
  softwareName: string;
  softwareVersion: string | null;
  surface: 'cli' | 'ide' | 'desktop' | 'web' | 'cloud';
  adapterRevision: string | null;
  enabledFields: readonly string[];
  qualification: 'not_connected' | 'limited' | 'qualified_scope' | 'recheck_required';
  work: string;
  health: string;
  observation: string;
  latestVisibleSource: SourceRef | null;
}
export interface VersionedResult {
  objectId: string;
  revision: string;
  contentDigest: string;
  owner: 'WORK-LAB' | 'AAOS' | 'DESIGN-LAB';
  evidenceId: string | null;
  status: string; // Do not derive one product-wide SUCCESS.
}
export interface CollaborationSummary {
  localCandidate: VersionedResult | null;
  outboundPermission: 'not_granted' | 'granted_scope' | 'unknown';
  sendResult: VersionedResult | null;
  realReception: VersionedResult | null;
  knowledgeDecision: VersionedResult | null;
  teachingArtifact: VersionedResult | null;
  professionalAcceptance: VersionedResult | null;
  teachingTechnicalCheck: VersionedResult | null;
  humanLearningSummary: VersionedResult | null;
  responsibilityFeedback: readonly VersionedResult[];
  measuredWorkEffect: VersionedResult | null;
}
export interface CommandAvailability {
  commandId: string;
  objectId: string;
  mode: 'observe' | 'suggest' | 'managed_command';
  available: boolean; // A server decision for the current identity/scope, not a frontend grant.
  reasons: readonly string[];
  expectedRevision: string | null;
  expectedBeforeDigest: string | null;
  authorizationRef: string | null;
  idempotencyKey: string | null;
  expiresAt: string | null;
}
export interface CapabilityMigration {
  source: VersionedResult;
  sourceEvaluation: VersionedResult | null;
  licenseStatus: string;
  dependencies: readonly string[];
  targetInstallationId: string | null;
  targetVersion: string | null;
  adapterRevision: string | null;
  losses: readonly string[];
  trialResult: VersionedResult | null;
  targetVerification: VersionedResult | null;
  deployment: VersionedResult | null;
  recoveryPoint: string | null;
  command: CommandAvailability;
}
