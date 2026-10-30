-- SPDX-License-Identifier: MIT
-- Human Jury records. design-lab/schemas/state/design-lab-state-jury-v1.sql
--
-- The contract in src/design_lab/assurance/human_jury.py has existed for weeks
-- while nothing could store a verdict, so no route could serve one and the UI had
-- nothing honest to show. This table is append-only: a re-judgement inserts a new
-- record whose `supersedes` points at the one it replaces. Editing or deleting a
-- verdict in place would silently rewrite the acceptance a human signed.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS jury_record (
  jury_record_id TEXT PRIMARY KEY,
  kind TEXT NOT NULL CHECK (kind IN ('JURY_VERDICT','JURY_PROPOSAL')),
  project_id TEXT NOT NULL REFERENCES project(project_id),
  subject_ref TEXT NOT NULL,
  artifact_sha256 TEXT NOT NULL,
  verdict TEXT CHECK (verdict IN ('APPROVE','REJECT')),
  juror_id TEXT,
  juror_kind TEXT,
  attestation TEXT,
  document_json TEXT NOT NULL,
  decided_at TEXT NOT NULL,
  supersedes TEXT REFERENCES jury_record(jury_record_id),
  UNIQUE(project_id, jury_record_id)
);

-- A verdict is a human attestation, not a mutable field. The CHECK constraints
-- above keep the vocabulary closed; these keep history from being rewritten.
CREATE TRIGGER IF NOT EXISTS jury_record_no_update BEFORE UPDATE ON jury_record
  BEGIN SELECT RAISE(ABORT, 'a signed jury record is immutable'); END;
CREATE TRIGGER IF NOT EXISTS jury_record_no_delete BEFORE DELETE ON jury_record
  BEGIN SELECT RAISE(ABORT, 'a signed jury record cannot be deleted'); END;

-- An agent proposal carries no juror and must never carry a verdict: that is the
-- whole difference between proposing and deciding.
CREATE INDEX IF NOT EXISTS jury_record_subject ON jury_record(project_id, subject_ref);
