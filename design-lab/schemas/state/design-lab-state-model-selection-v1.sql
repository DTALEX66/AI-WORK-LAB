-- SPDX-License-Identifier: MIT
-- Model selection storage. design-lab/schemas/state/design-lab-state-model-selection-v1.sql
--
-- WHAT THIS TABLE IS. The owner un-locked model choice on 2026-10-20:
-- 「大模型可以 但为什么要锁死呢？不锁死 做好菜单导航和接口 用户自行选择本地或者是云端模型」.
-- A picker that lists candidates but remembers nothing makes the user choose on every request,
-- which is the same lock wearing a different face. One row here is one recorded act of choosing,
-- per project.
--
-- WHAT IT IS NOT. It is not a qualification, not a licence grant and not a capability claim:
-- `src/design_lab/readiness/model_radar.py` keeps the fail-closed rules about which model may be
-- default-enabled, and this table cannot move any of them. It is not a run record either — no
-- model was loaded, no inference happened and nothing was sent (this repository has no outbound
-- transport), so there is deliberately no result, duration, cost or output column here. A row
-- says only "this actor chose this, and these were the catalogue's facts at that moment".
--
-- WHY THE SNAPSHOT COLUMNS EXIST. `radar_state`, `machine_state`, `placement`, `commercial_use`
-- and `weights_recorded` restate what `GET /api/models` reported when the choice was made, not
-- what it reports now. Without them, a selection made while a model was `WATCH` with zero
-- recorded weight hashes would read, after a later registry edit, as if the person had chosen a
-- qualified model. `qualified_local_at_choice` is the same protection as a single bit: it lets a
-- reader see that the choice was made against an unqualified candidate. The values are copied in
-- by `src/design_lab/model_selection.py` from the catalogue row it validated against, so a
-- submission cannot assert its own qualification.
--
-- WHY "NOT USED" IS A ROW AND NOT AN ABSENCE. The same ruling says the operator may choose not
-- to use a model at all (「用户自行填写或者选择用没用」). Silence and a declared non-use are
-- different facts: with no row a reader cannot tell whether the person never visited the picker
-- or visited it and declined. `declared_unused = 1` carries no model_id and no snapshot, so it
-- cannot be mistaken for a choice that was made and then lost.
--
-- APPEND-ONLY, like the research, rights and jury stores: a superseded choice is evidence of the
-- decision path, and rewriting it would move the ground under anything that cited it. Changing
-- one's mind appends `revision + 1` —  the triggers below refuse UPDATE and DELETE outright.
--
-- One source of truth per fact: `document_json` IS the selection document
-- (design-lab/schemas/model-selection-v1.schema.json is its contract and model_selection.py
-- loads and validates against it) —  the scalar columns restate fields the database has to be able
-- to enforce or index, and design-lab/tests/test_model_selection.py re-reads both sides so a
-- restatement that disagrees with the document fails loudly instead of becoming a second
-- authority. There is no `applied_to_runs` or `active` flag: "current" is MAX(revision) per
-- project, declared at query time, exactly as the ACTIVE-version invariant in this repository
-- requires.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS model_selection (
  project_id TEXT NOT NULL REFERENCES project(project_id),
  revision INTEGER NOT NULL CHECK (revision > 0),
  model_id TEXT,
  declared_unused INTEGER NOT NULL DEFAULT 0 CHECK (declared_unused IN (0, 1)),
  placement TEXT CHECK (placement IS NULL OR placement IN ('local', 'huggingface', 'vendor')),
  radar_state TEXT CHECK (radar_state IS NULL OR radar_state IN
    ('WATCH', 'EVALUATING', 'QUALIFIED_LOCAL', 'REJECTED', 'BLOCKED_BY_LICENSE')),
  machine_state TEXT CHECK (machine_state IS NULL OR machine_state IN
    ('ABSENT', 'METADATA_ONLY', 'WEIGHTS_COMPLETE', 'LOAD_VERIFIED', 'INFERENCE_VERIFIED')),
  commercial_use TEXT CHECK (commercial_use IS NULL OR commercial_use IN
    ('PERMITTED', 'RESTRICTED', 'UNKNOWN')),
  weights_recorded INTEGER CHECK (weights_recorded IS NULL OR weights_recorded >= 0),
  qualified_local_at_choice INTEGER NOT NULL CHECK (qualified_local_at_choice IN (0, 1)),
  actor TEXT NOT NULL CHECK (length(trim(actor)) > 0),
  actor_kind TEXT NOT NULL CHECK (actor_kind IN ('human', 'agent')),
  recorded_at TEXT NOT NULL,
  document_json TEXT NOT NULL CHECK (length(trim(document_json)) > 0),
  -- A choice names a model — a declination names nothing. Both are total, so no third shape is
  -- storable: "a model with no name" and "no model but with a snapshot" are refused even by
  -- direct SQL. Table constraints come after every column definition because SQLite's grammar
  -- requires it — a column following a table constraint is a syntax error, measured on 3.53.1.
  CHECK ((declared_unused = 0 AND model_id IS NOT NULL AND length(trim(model_id)) > 0)
         OR (declared_unused = 1 AND model_id IS NULL)),
  -- The snapshot belongs to a named model and to nothing else.
  CHECK ((declared_unused = 1 AND placement IS NULL AND radar_state IS NULL
          AND machine_state IS NULL AND commercial_use IS NULL AND weights_recorded IS NULL
          AND qualified_local_at_choice = 0)
         OR declared_unused = 0),
  PRIMARY KEY (project_id, revision)
);

CREATE TRIGGER IF NOT EXISTS model_selection_no_update BEFORE UPDATE ON model_selection
  BEGIN SELECT RAISE(ABORT, 'a recorded model choice is immutable — append the next revision'); END;
CREATE TRIGGER IF NOT EXISTS model_selection_no_delete BEFORE DELETE ON model_selection
  BEGIN SELECT RAISE(ABORT, 'a recorded model choice cannot be deleted'); END;

-- Read models: the current selection (MAX revision) and the decision path.
CREATE INDEX IF NOT EXISTS model_selection_project ON model_selection(project_id, revision DESC);
