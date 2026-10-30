-- SPDX-License-Identifier: MIT
-- DESIGN-LAB — the target profile: software x model x entry x task mode, and where each
-- capability field's claim came from.
--
-- DL-KB-09. The five seeded profiles are NOT stored here: they are served read-only from
-- design-lab/config/target-profiles.json, so one byte has exactly one owner and a config edit
-- cannot drift out of sync with a database copy. This file holds only what a person adds at the
-- screen -- draft profiles that are marked unverified by construction.
--
--   target_profile_draft  one row per draft, append-only revisions, "current" is MAX(revision).
--                         No `active` flag, per the ACTIVE-version invariant. The CHECK on
--                         support_state accepts USER_DRAFT only: a draft cannot be written as a
--                         documented claim, because nothing in this round read an official page
--                         for it or ran it.
--
-- Append-only is enforced here, not by convention: UPDATE and DELETE abort, so a corrected draft
-- is a new revision and the earlier bytes stay readable.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS target_profile_draft (
  profile_id   TEXT NOT NULL CHECK (profile_id GLOB 'tprof-*'),
  revision     INTEGER NOT NULL CHECK (revision >= 1),
  support_state TEXT NOT NULL CHECK (support_state = 'USER_DRAFT'),
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 71
                                      AND substr(content_sha256, 1, 7) = 'sha256:'),
  document_json TEXT NOT NULL CHECK (length(trim(document_json)) > 0),
  created_at   TEXT NOT NULL,
  created_by   TEXT NOT NULL CHECK (length(trim(created_by)) > 0),
  PRIMARY KEY (profile_id, revision)
);

CREATE INDEX IF NOT EXISTS target_profile_draft_by_key
  ON target_profile_draft(profile_id, revision);

CREATE TRIGGER IF NOT EXISTS target_profile_draft_no_update
BEFORE UPDATE ON target_profile_draft
BEGIN
  SELECT RAISE(ABORT, 'target_profile_draft is append-only; write a new revision');
END;

CREATE TRIGGER IF NOT EXISTS target_profile_draft_no_delete
BEFORE DELETE ON target_profile_draft
BEGIN
  SELECT RAISE(ABORT, 'target_profile_draft is append-only; a revision is never withdrawn');
END;
