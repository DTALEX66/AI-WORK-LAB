-- SPDX-License-Identifier: MIT
-- E-SLICE-01 vertical slice (Project -> Brief -> Reference -> Direction -> DesignSystem):
-- design-layer additive migration. Extends the SINGLE local state database; it
-- introduces no second store, no second writer and no host call. Existing v1 /
-- assets / attempt / creative tables stay frozen; this file only ADDS tables and
-- append-only guards.
--
-- One source of truth per fact:
--   * design_brief / design_direction / design_system_binding are versioned records
--     (version + superseded_by) so a revision appends a new version, never rewrites.
--   * design_direction.chosen + actor/actor_kind is the single record of the human
--     "direction choice" (Golden Workflow 1). There is no parallel decision table.
--   * design_system_binding.design_system_name must match a catalog design-system
--     manifest (validated in the design_layer module against the packaged catalog).
-- Idempotency reuses the shared operation_intent table + creative store helpers.
PRAGMA foreign_keys = ON;

CREATE TABLE design_brief (
  brief_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL UNIQUE REFERENCES operation_intent(operation_id),
  project_id TEXT NOT NULL REFERENCES project(project_id),
  title TEXT NOT NULL,
  goals_json TEXT NOT NULL,
  constraints_json TEXT,
  reference_asset_ids TEXT,
  spec_sha256 TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  superseded_by TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_design_brief_project ON design_brief(project_id, brief_id);

CREATE TABLE design_direction (
  direction_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL UNIQUE REFERENCES operation_intent(operation_id),
  project_id TEXT NOT NULL REFERENCES project(project_id),
  brief_id TEXT NOT NULL REFERENCES design_brief(brief_id),
  title TEXT NOT NULL,
  style_notes_json TEXT,
  color_mood TEXT,
  typography_mood TEXT,
  chosen INTEGER NOT NULL DEFAULT 0 CHECK (chosen IN (0,1)),
  actor TEXT,
  actor_kind TEXT CHECK (actor_kind IS NULL OR actor_kind IN ('human','agent')),
  spec_sha256 TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  superseded_by TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_design_direction_project ON design_direction(project_id, direction_id);
CREATE INDEX idx_design_direction_brief ON design_direction(brief_id);

-- The chosen direction binds exactly one catalog design system.
CREATE TABLE design_system_binding (
  binding_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL UNIQUE REFERENCES operation_intent(operation_id),
  project_id TEXT NOT NULL REFERENCES project(project_id),
  direction_id TEXT NOT NULL REFERENCES design_direction(direction_id),
  design_system_name TEXT NOT NULL,
  spec_sha256 TEXT NOT NULL,
  version INTEGER NOT NULL DEFAULT 1 CHECK (version >= 1),
  superseded_by TEXT,
  created_at TEXT NOT NULL
);
CREATE INDEX idx_design_system_binding_direction ON design_system_binding(direction_id);

-- A binding is versioned: rebinding appends a new version pointing at the previous one.
CREATE TRIGGER design_system_binding_no_update BEFORE UPDATE ON design_system_binding
  BEGIN SELECT RAISE(ABORT, 'design-system binding versions are append-only'); END;
CREATE TRIGGER design_system_binding_no_delete BEFORE DELETE ON design_system_binding
  BEGIN SELECT RAISE(ABORT, 'design-system binding versions are append-only'); END;
