-- SPDX-License-Identifier: MIT
-- R3-05 migration: caller owns BEGIN IMMEDIATE; preserve v1 terminal history.
ALTER TABLE attempt_state RENAME TO attempt_state_v1;
CREATE TABLE attempt_state (
  attempt_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES job(job_id),
  attempt_no INTEGER NOT NULL CHECK (attempt_no > 0),
  state TEXT NOT NULL CHECK (state IN
    ('PENDING','RUNNING','OUTCOME_UNKNOWN','CANCEL_REQUESTED','RECONCILING',
     'RECEIPTED','FAILED','TIMED_OUT','CANCELLED')),
  started_at TEXT NOT NULL,
  ended_at TEXT,
  note TEXT,
  UNIQUE(job_id, attempt_no)
);
INSERT INTO attempt_state SELECT * FROM attempt_state_v1;
DROP TABLE attempt_state_v1;
CREATE TABLE operation_state (
  operation_id TEXT PRIMARY KEY REFERENCES operation_intent(operation_id),
  state TEXT NOT NULL CHECK (state IN
    ('PENDING','DISPATCHING','OUTCOME_UNKNOWN','RECONCILING','CANCEL_REQUESTED',
     'RETRYABLE','SUCCEEDED','CANCELLED','PAUSED_NEEDS_USER')),
  updated_at TEXT NOT NULL
);
-- Legacy receipts lack output/readback evidence: preserve, then requalify.
INSERT INTO operation_state
  SELECT operation_id, 'OUTCOME_UNKNOWN', created_at FROM operation_intent;
CREATE TABLE attempt_resolution (
  attempt_id TEXT PRIMARY KEY REFERENCES attempt_state(attempt_id),
  proof TEXT NOT NULL,
  evidence_json TEXT,
  cancel_requested INTEGER NOT NULL DEFAULT 0 CHECK (cancel_requested IN (0,1)),
  cancel_acked INTEGER NOT NULL DEFAULT 0 CHECK (cancel_acked IN (0,1)),
  updated_at TEXT NOT NULL
);
CREATE TABLE attempt_event (
  event_no INTEGER PRIMARY KEY AUTOINCREMENT,
  attempt_id TEXT NOT NULL REFERENCES attempt_state(attempt_id),
  from_state TEXT,
  to_state TEXT NOT NULL,
  detail TEXT NOT NULL,
  at TEXT NOT NULL
);
INSERT INTO attempt_event (attempt_id, from_state, to_state, detail, at)
  SELECT attempt_id, NULL, state, 'v1 snapshot; outcome requires reconciliation', started_at
  FROM attempt_state;
CREATE TRIGGER terminal_attempt_no_update BEFORE UPDATE ON attempt_state
  WHEN OLD.state IN ('RECEIPTED','FAILED','TIMED_OUT','CANCELLED')
  BEGIN SELECT RAISE(ABORT, 'terminal attempt is immutable'); END;
CREATE TRIGGER attempt_no_delete BEFORE DELETE ON attempt_state
  BEGIN SELECT RAISE(ABORT, 'attempt history is append-only'); END;
CREATE TRIGGER attempt_event_no_update BEFORE UPDATE ON attempt_event
  BEGIN SELECT RAISE(ABORT, 'attempt events are append-only'); END;
CREATE TRIGGER attempt_event_no_delete BEFORE DELETE ON attempt_event
  BEGIN SELECT RAISE(ABORT, 'attempt events are append-only'); END;
