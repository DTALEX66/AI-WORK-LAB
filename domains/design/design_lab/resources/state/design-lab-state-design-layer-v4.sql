-- SPDX-License-Identifier: MIT
-- design-layer-v4: design-system TOKEN documents get the version model the brief /
-- direction / binding rows already have.
--
-- Until this migration a design system had only a BINDING (design_system_binding
-- names a catalog contract); nothing in the product could record the token VALUES
-- themselves. W06-TOKEN-WRITE-GAP.md measured that gap (G1/G2/G3) and asked for the
-- smallest honest chain: write -> persist -> version -> read back. This file is the
-- persist + version half. It adds ONE table to the single local state database; no
-- second store, no second writer, no host call, no file-based token truth.
--
-- One source of truth per fact:
--   * document_json is the DTCG document (design_lab.interop.dtcg is its contract);
--     the CSS projection stays a projection and is never stored as truth;
--   * (project_id, design_system_name, version) is unique, so a project's token
--     document for one design system is one versioned chain, not a pile of edits;
--   * the LIVE document is the row whose superseded_by IS NULL -- the same read
--     model design_brief / design_direction use.
--
-- Append-only is a database property here, not a convention. A revision appends a
-- NEW row and moves ONLY the previous row's superseded_by pointer, so the columns
-- below are fenced off by a BEFORE UPDATE OF trigger: no path -- this build or a
-- hand-edited one -- can rewrite a recorded version's content in place. DELETE is
-- refused for the same reason: dropping a version would silently erase history.
PRAGMA foreign_keys = ON;

CREATE TABLE design_system_token (
  token_document_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL UNIQUE REFERENCES operation_intent(operation_id),
  project_id TEXT NOT NULL REFERENCES project(project_id),
  design_system_name TEXT NOT NULL,
  document_json TEXT NOT NULL,
  -- A DTCG document with zero tokens is not a design system; dtcg refuses it too,
  -- and the CHECK keeps a future writer from relaxing the module into an empty row.
  token_count INTEGER NOT NULL CHECK (token_count >= 1),
  dtcg_schema_version TEXT NOT NULL,
  spec_sha256 TEXT NOT NULL,
  actor TEXT,
  actor_kind TEXT CHECK (actor_kind IS NULL OR actor_kind IN ('human','agent')),
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  superseded_by TEXT,
  created_at TEXT NOT NULL,
  UNIQUE (project_id, design_system_name, version)
);
CREATE INDEX idx_design_system_token_live
  ON design_system_token(project_id, design_system_name, superseded_by);
CREATE INDEX idx_design_system_token_project
  ON design_system_token(project_id, token_document_id);

-- The ONLY column a revision may touch on an existing row is superseded_by; every
-- content column (and the identity/project/name/version coordinates that place the
-- row in the chain) is immutable once written.
CREATE TRIGGER design_system_token_content_no_update BEFORE UPDATE OF
  token_document_id, operation_id, project_id, design_system_name, document_json,
  token_count, dtcg_schema_version, spec_sha256, actor, actor_kind, version, created_at
  ON design_system_token
  BEGIN SELECT RAISE(ABORT, 'design-system token versions are append-only'); END;
CREATE TRIGGER design_system_token_no_delete BEFORE DELETE ON design_system_token
  BEGIN SELECT RAISE(ABORT, 'design-system token versions are append-only'); END;
