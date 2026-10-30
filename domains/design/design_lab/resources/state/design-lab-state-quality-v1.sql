-- SPDX-License-Identifier: MIT
-- Sealed Quality records. design-lab/schemas/state/design-lab-state-quality-v1.sql
--
-- The Quality gate was not reachable from the product: assurance/qa_plane.py and
-- assurance/quality_record.py could seal a record and refuse an automated judge,
-- but nothing could STORE one, so no verb and no later route could serve one, and
-- the three modules' guarantee ("PASS is structurally unreachable without a human
-- verdict") had no durable subject to be true about. This table is that store. It
-- adds ONE table to the single local state database; no second store, no second
-- writer, no host call, no file-based quality truth.
--
-- Append-only, for the same reason the jury table is: a recorded assessment is the
-- evidence a later release decision cites, and rewriting it in place would silently
-- move the goalposts under a decision already taken. A re-assessment inserts a NEW
-- record whose `supersedes` points at the one it replaces.
--
-- One source of truth per fact:
--   * document_json IS the sealed QualityRecord (assurance-quality-record.schema.json
--     is its contract, quality_record.py validates it); the columns below are
--     projections of it, never independent fields a writer may set on its own;
--   * (project_id, quality_record_id) is unique, so one project owns one chain of
--     assessments instead of a pile of edits;
--   * final_gate is stored, but it is DERIVED by the record module from the
--     deterministic and human planes; the CHECK below keeps a row from ever claiming
--     PASS without the human APPROVE that makes PASS reachable.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS quality_record (
  quality_record_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(project_id),
  subject_ref TEXT NOT NULL,
  artifact_sha256 TEXT NOT NULL,
  final_gate TEXT NOT NULL CHECK (final_gate IN ('BLOCKED','NEEDS_HUMAN_VERDICT','PASS')),
  -- Projections of document_json.human_jury. Nullable because a record may be sealed
  -- before the human gate is reached; those rows report NEEDS_HUMAN_VERDICT or BLOCKED.
  human_verdict TEXT CHECK (human_verdict IS NULL OR human_verdict IN ('APPROVE','REJECT')),
  juror_id TEXT,
  -- The vocabulary is the human jury's: only a HUMAN or a named PANEL can appear
  -- here at all, so a row cannot record MODEL / AGENT / SYSTEM as its signing actor
  -- even if the writer above it were changed to allow one.
  juror_kind TEXT CHECK (juror_kind IS NULL OR juror_kind IN ('HUMAN','PANEL')),
  attestation TEXT,
  document_json TEXT NOT NULL,
  created_at TEXT NOT NULL,
  supersedes TEXT REFERENCES quality_record(quality_record_id),
  UNIQUE(project_id, quality_record_id),
  -- PASS is not a state a row may assert: it is the consequence of a signed human
  -- APPROVE. Kept at the database level so no path -- this build or a hand-edited
  -- one -- can store a gate the sealed document cannot derive. COALESCE is load-
  -- bearing: `final_gate <> 'PASS' OR human_verdict = 'APPROVE'` evaluates to NULL
  -- for a row whose human_verdict is NULL, and SQLite accepts a NULL CHECK, so the
  -- naive form would have let a no-human row store PASS (measured, then corrected).
  CHECK (final_gate <> 'PASS' OR COALESCE(human_verdict, '') = 'APPROVE'),
  -- A claimed human verdict without an actor and an attestation is the shape of an
  -- automated judge wearing a human signature, so the three travel together.
  CHECK (human_verdict IS NULL OR (juror_id IS NOT NULL AND juror_id <> ''
                                    AND attestation IS NOT NULL AND attestation <> '')),
  -- The digest rule is the record contract's own (assurance-quality-record.schema.json
  -- `sha256`: lowercase, 64 hex, never all-zero). Restated here because an all-zero
  -- digest is not evidence of anything, and a row is the thing a later reader trusts.
  CHECK (length(artifact_sha256) = 71
         AND artifact_sha256 GLOB 'sha256:[0-9a-f]*'
         AND replace(artifact_sha256, '0', '') <> 'sha256:')
);

CREATE TRIGGER IF NOT EXISTS quality_record_no_update BEFORE UPDATE ON quality_record
  BEGIN SELECT RAISE(ABORT, 'a sealed quality record is immutable'); END;
CREATE TRIGGER IF NOT EXISTS quality_record_no_delete BEFORE DELETE ON quality_record
  BEGIN SELECT RAISE(ABORT, 'a sealed quality record cannot be deleted'); END;

-- Read models: the assessments of one subject, and the current one per project.
CREATE INDEX IF NOT EXISTS quality_record_subject ON quality_record(project_id, subject_ref);
CREATE INDEX IF NOT EXISTS quality_record_gate ON quality_record(project_id, final_gate);
