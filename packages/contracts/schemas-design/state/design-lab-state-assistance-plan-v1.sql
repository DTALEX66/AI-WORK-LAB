-- SPDX-License-Identifier: MIT
-- DESIGN-LAB — the assistance plan: one neutral intent, its append-only revisions, and the
-- record of a named person adopting one revision.
--
-- DL-KB-07. A plan is the object a short task needs: an objective, an output type, the neutral
-- creative the task is aiming at, brand/role constraints, lens/sound requirements, external
-- steps, known gaps and the material revisions the plan was built from. It reuses the existing
-- objects for everything it can (project, brief, direction, prompt result, asset) and stores
-- references to them instead of copying their bytes.
--
--   assistance_plan           one row per plan identity; the owning project is fixed here and
--                             never moves, because a plan that changed project would change who
--                             may read it;
--   assistance_plan_revision  the plan's content, append-only, one row per revision. "Current"
--                             is MAX(revision) at read time -- there is no `active` flag, as the
--                             ACTIVE-version invariant requires;
--   assistance_plan_choice    one row per revision a named human adopted. This is a recorded
--                             judgement, not a computed ranking, and only a human may write it:
--                             the CHECK refuses any other actor_kind at the storage layer, so an
--                             application bug cannot file an agent's choice as a person's.
--
-- Append-only is enforced here, not by convention: UPDATE and DELETE on all three tables abort.
-- A correction is a new revision, and a chosen revision keeps its bytes even after a newer
-- revision exists (the readback says which revision was chosen and whether it is still current).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS assistance_plan (
  plan_id    TEXT PRIMARY KEY CHECK (plan_id GLOB 'aplan-*'),
  project_id TEXT NOT NULL REFERENCES project(project_id),
  created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS assistance_plan_by_project
  ON assistance_plan(project_id, created_at);

CREATE TABLE IF NOT EXISTS assistance_plan_revision (
  plan_id        TEXT NOT NULL REFERENCES assistance_plan(plan_id),
  revision       INTEGER NOT NULL CHECK (revision >= 1),
  objective      TEXT NOT NULL CHECK (length(trim(objective)) > 0),
  output_type    TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 71
                                      AND substr(content_sha256, 1, 7) = 'sha256:'),
  created_at     TEXT NOT NULL,
  created_by     TEXT NOT NULL,
  document_json  TEXT NOT NULL CHECK (length(trim(document_json)) > 0),
  PRIMARY KEY (plan_id, revision)
);

CREATE TABLE IF NOT EXISTS assistance_plan_choice (
  plan_id    TEXT NOT NULL,
  revision   INTEGER NOT NULL,
  actor      TEXT NOT NULL CHECK (length(trim(actor)) > 0),
  actor_kind TEXT NOT NULL CHECK (actor_kind = 'human'),
  chosen_at  TEXT NOT NULL,
  PRIMARY KEY (plan_id, revision),
  FOREIGN KEY (plan_id, revision) REFERENCES assistance_plan_revision(plan_id, revision)
);

CREATE TRIGGER IF NOT EXISTS assistance_plan_no_update
BEFORE UPDATE ON assistance_plan
BEGIN
  SELECT RAISE(ABORT, 'assistance_plan is append-only');
END;

CREATE TRIGGER IF NOT EXISTS assistance_plan_no_delete
BEFORE DELETE ON assistance_plan
BEGIN
  SELECT RAISE(ABORT, 'assistance_plan is append-only');
END;

CREATE TRIGGER IF NOT EXISTS assistance_plan_revision_no_update
BEFORE UPDATE ON assistance_plan_revision
BEGIN
  SELECT RAISE(ABORT, 'assistance_plan_revision is append-only; write a new revision');
END;

CREATE TRIGGER IF NOT EXISTS assistance_plan_revision_no_delete
BEFORE DELETE ON assistance_plan_revision
BEGIN
  SELECT RAISE(ABORT, 'assistance_plan_revision is append-only; a revision is never withdrawn');
END;

CREATE TRIGGER IF NOT EXISTS assistance_plan_choice_no_update
BEFORE UPDATE ON assistance_plan_choice
BEGIN
  SELECT RAISE(ABORT, 'assistance_plan_choice is append-only');
END;

CREATE TRIGGER IF NOT EXISTS assistance_plan_choice_no_delete
BEFORE DELETE ON assistance_plan_choice
BEGIN
  SELECT RAISE(ABORT, 'assistance_plan_choice is append-only');
END;
