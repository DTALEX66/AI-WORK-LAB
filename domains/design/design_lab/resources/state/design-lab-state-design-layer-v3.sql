-- SPDX-License-Identifier: MIT
-- E-SLICE-01 F-2a: real revision for the design layer (append-only event log).
--
-- v1 introduced the three versioned design-layer tables; v2 pinned the
-- single-choice invariant at the database level. Both left the revision columns
-- structurally present but unwritten: every write path inserted version=1 and
-- superseded_by stayed NULL, i.e. a version-ready schema without versioning.
--
-- This migration adds the ONE append-only record of design-layer history. Every
-- write path appends a typed event inside the SAME transaction as the state
-- change it describes, so a revision is: a NEW content row (version = old + 1)
-- plus a superseded_by pointer moved on the old row plus one brief-revised /
-- direction-revised event carrying old_id and new_id. No content column of a
-- superseded row is ever rewritten.
--
-- One source of truth per fact:
--   * the design_brief / design_direction / design_system_binding rows stay the
--     read model (and ``chosen`` stays the materialized human Direction choice);
--   * design_layer_event is the history: it is append-only by DDL, not by
--     convention.
PRAGMA foreign_keys = ON;

CREATE TABLE design_layer_event (
  event_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(project_id),
  kind TEXT NOT NULL CHECK (kind IN (
    'brief-created', 'brief-revised',
    'direction-created', 'direction-revised',
    'direction-chosen', 'direction-unchosen',
    'binding-created', 'binding-rebound')),
  brief_id TEXT,
  direction_id TEXT,
  binding_id TEXT,
  payload_json TEXT NOT NULL,
  actor TEXT,
  actor_kind TEXT CHECK (actor_kind IS NULL OR actor_kind IN ('human','agent')),
  created_at TEXT NOT NULL
);
CREATE INDEX idx_design_layer_event_project ON design_layer_event(project_id, created_at);

-- Append-only is a database property here. The module appends with a plain
-- INSERT (no OR REPLACE / OR IGNORE), so a repeated event_id fails closed with a
-- PRIMARY KEY violation instead of silently overwriting history, and these
-- triggers abort any later UPDATE or DELETE of an event row.
CREATE TRIGGER design_layer_event_no_update BEFORE UPDATE ON design_layer_event
  BEGIN SELECT RAISE(ABORT, 'design-layer events are append-only'); END;
CREATE TRIGGER design_layer_event_no_delete BEFORE DELETE ON design_layer_event
  BEGIN SELECT RAISE(ABORT, 'design-layer events are append-only'); END;
