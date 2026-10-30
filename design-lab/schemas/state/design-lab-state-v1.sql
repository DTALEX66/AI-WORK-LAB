-- DL-TP-R2-013: LocalStateStore schema v1 (.project-local/state/design-lab.db)
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS operation_intent (
  operation_id TEXT PRIMARY KEY,
  idempotency_scope TEXT NOT NULL,
  idempotency_key TEXT NOT NULL,
  request_hash TEXT NOT NULL,
  created_at TEXT NOT NULL,
  UNIQUE(idempotency_scope, idempotency_key)
);

CREATE TABLE IF NOT EXISTS job (
  job_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL REFERENCES operation_intent(operation_id),
  schemaVersion TEXT NOT NULL DEFAULT 'design-lab/job-spec/v1'
);

CREATE TABLE IF NOT EXISTS job_attempt (
  job_id TEXT NOT NULL REFERENCES job(job_id),
  attempt_no INTEGER NOT NULL,
  started_at TEXT,
  PRIMARY KEY (job_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS operation_receipt (
  receipt_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL,
  attempt_id TEXT NOT NULL,
  status TEXT NOT NULL,
  stale_fence INTEGER NOT NULL DEFAULT 0,
  received_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lease (
  resource_key TEXT PRIMARY KEY,
  holder_run_id TEXT,
  generation INTEGER NOT NULL DEFAULT 1,
  state TEXT NOT NULL DEFAULT 'ACTIVE',
  acquired_at TEXT,
  expires_at TEXT,
  takeover_requested INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS audit_event (
  audit_id TEXT PRIMARY KEY,
  actor TEXT NOT NULL,
  action TEXT NOT NULL,
  at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS outbox (
  event_id TEXT PRIMARY KEY,
  event_type TEXT NOT NULL,
  payload TEXT NOT NULL,
  delivered INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS approval (
  approval_id TEXT PRIMARY KEY,
  action_kind TEXT NOT NULL,
  actor TEXT,
  state TEXT NOT NULL DEFAULT 'PENDING'
);
