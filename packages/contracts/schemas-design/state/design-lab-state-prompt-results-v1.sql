-- SPDX-License-Identifier: MIT
-- Prompt result storage. design-lab/schemas/state/design-lab-state-prompt-results-v1.sql
--
-- WHAT THIS TABLE IS. The two prompt routes have always produced a complete, versioned document and
-- then thrown it away: `apps/workbench/shell.ts` says so on screen ("服务端不持久化这份文档"), and the
-- 18-hop chain could only prove that several routes answered on one server, not that one professional
-- artifact travelled through analysis, acceptance and reuse. One row here is one such document, kept,
-- addressed, and bound to the records it was assembled from.
--
-- WHY IT IS A SEPARATE TABLE FROM model_selection. A selection is who the operator picked; a result is
-- what the product produced under that selection. Collapsing them would let "a model was chosen" be
-- read as "a prompt exists", and the composition carries source ids and a content digest that a
-- selection row has no business holding.
--
-- WHAT A ROW IS NOT. It is not a run record and not a verdict: `executed` is a stored constant 0,
-- because nothing in this repository loads a model or sends a request (there is no outbound
-- transport). Acceptance lives in `prompt_result_review`, which is a different act by a different
-- party at a different time -- composing a prompt has never meant anybody agreed to use it.
--
-- APPEND-ONLY, like the model-selection, research, rights and jury stores. Changing the brief, the
-- direction or the recorded selection produces a NEW result id (the id is a digest over exactly those
-- inputs), so a superseded result stays readable instead of being rewritten -- and an acceptance that
-- quoted the old digest stops matching, which is the invalidation rule stated in
-- design-lab/tests/test_prompt_results.py rather than implied.
--
-- WHY reviewer_kind IS PINNED TO 'human' IN THE TABLE. Owner ruling 2026-10-21: local acceptance and
-- outbound approval both stay human-only (「现在都没有真实测试过呢 怎么批准」). A self-issued agent
-- acceptance would be a second E4 that no person signed, so the storage itself refuses it; relaxing
-- that is a contract change needing a new owner ruling, not a code edit.
--
-- One source of truth per fact: `document_json` IS the prompt document, whose contract is
-- design-lab/schemas/prompt-composition-v1.schema.json or prompt-reversal-v1.schema.json; the scalar
-- columns restate what the database must enforce or index, and the tests re-read both sides so a
-- restatement that drifts from the document fails loudly. There is no `active` flag -- "current" is
-- MAX(revision) computed per query, exactly as the ACTIVE-version invariant requires.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS prompt_result (
  project_id TEXT NOT NULL REFERENCES project(project_id),
  revision INTEGER NOT NULL CHECK (revision > 0),
  result_id TEXT NOT NULL CHECK (result_id GLOB 'prompt-*' OR result_id GLOB 'reversal-*'),
  kind TEXT NOT NULL CHECK (kind IN ('COMPOSITION', 'REVERSAL')),
  document_version TEXT NOT NULL CHECK (document_version IN
    ('design-lab/prompt-composition/v1', 'design-lab/prompt-reversal/v1')),
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 71
                                      AND substr(content_sha256, 1, 7) = 'sha256:'),
  target TEXT,
  brief_id TEXT,
  brief_version INTEGER,
  brief_spec_sha256 TEXT,
  direction_id TEXT,
  direction_version INTEGER,
  asset_id TEXT,
  asset_sha256 TEXT,
  selection_revision INTEGER,
  executed INTEGER NOT NULL DEFAULT 0 CHECK (executed = 0),
  created_at TEXT NOT NULL,
  document_json TEXT NOT NULL CHECK (length(trim(document_json)) > 0),
  -- The kind and the document version travel together: a REVERSAL row carrying a composition
  -- version would let a read-side branch on either and get two different answers.
  CHECK ((kind = 'COMPOSITION' AND document_version = 'design-lab/prompt-composition/v1'
          AND brief_id IS NOT NULL AND length(trim(brief_id)) > 0)
         OR (kind = 'REVERSAL' AND document_version = 'design-lab/prompt-reversal/v1'
             AND asset_id IS NOT NULL AND length(trim(asset_id)) > 0
             AND asset_sha256 IS NOT NULL)),
  -- A composition names a target; a reversal names the asset it described. Neither may be blank
  -- in the other's place.
  CHECK ((kind = 'REVERSAL' AND target IS NULL) OR (kind = 'COMPOSITION' AND target IS NOT NULL
                                                    AND length(trim(target)) > 0)),
  PRIMARY KEY (project_id, revision),
  UNIQUE (project_id, result_id)
);

CREATE TRIGGER IF NOT EXISTS prompt_result_no_update BEFORE UPDATE ON prompt_result
  BEGIN SELECT RAISE(ABORT, 'a stored prompt result is immutable — recompose to get a new id'); END;
CREATE TRIGGER IF NOT EXISTS prompt_result_no_delete BEFORE DELETE ON prompt_result
  BEGIN SELECT RAISE(ABORT, 'a stored prompt result cannot be deleted'); END;

-- Read models: the newest result, and the whole path per project.
CREATE INDEX IF NOT EXISTS prompt_result_project ON prompt_result(project_id, revision DESC);

CREATE TABLE IF NOT EXISTS prompt_result_review (
  project_id TEXT NOT NULL REFERENCES project(project_id),
  review_revision INTEGER NOT NULL CHECK (review_revision > 0),
  result_id TEXT NOT NULL,
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 71
                                      AND substr(content_sha256, 1, 7) = 'sha256:'),
  decision TEXT NOT NULL CHECK (decision IN ('ACCEPTED', 'DECLINED')),
  reviewer TEXT NOT NULL CHECK (length(trim(reviewer)) > 0),
  reviewer_kind TEXT NOT NULL CHECK (reviewer_kind = 'human'),
  reviewed_at TEXT NOT NULL,
  note TEXT,
  document_json TEXT NOT NULL CHECK (length(trim(document_json)) > 0),
  -- An acceptance is only about a result this project stored, and it quotes the digest it was
  -- signed against; the FK is what makes "the reviewed artifact does not exist" impossible rather
  -- than merely unlikely.
  FOREIGN KEY (project_id, result_id) REFERENCES prompt_result(project_id, result_id),
  PRIMARY KEY (project_id, review_revision)
);

CREATE TRIGGER IF NOT EXISTS prompt_result_review_no_update
  BEFORE UPDATE ON prompt_result_review
  BEGIN SELECT RAISE(ABORT, 'a recorded prompt review is immutable'); END;
CREATE TRIGGER IF NOT EXISTS prompt_result_review_no_delete
  BEFORE DELETE ON prompt_result_review
  BEGIN SELECT RAISE(ABORT, 'a recorded prompt review cannot be deleted'); END;

CREATE INDEX IF NOT EXISTS prompt_result_review_target
  ON prompt_result_review(project_id, result_id, review_revision DESC);
