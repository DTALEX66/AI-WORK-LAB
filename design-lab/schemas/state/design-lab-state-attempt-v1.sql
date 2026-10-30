-- DL-TP-T05 (MULTIMODAL-2026-09-05): attempt state persistence extension
-- Companion to design-lab-state-v1.sql. v1's job_attempt carries only
-- (job_id, attempt_no, started_at); this adds the durable terminal-state
-- ledger so a restart can recover attempt status and a failed/cancelled
-- attempt can never be reported as completed.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS attempt_state (
  attempt_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES job(job_id),
  attempt_no INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PENDING','RUNNING','RECEIPTED','FAILED','TIMED_OUT','CANCELLED')),
  started_at TEXT NOT NULL,
  ended_at TEXT,
  note TEXT,
  UNIQUE(job_id, attempt_no)
);
