-- DL-TP-T05 (MULTIMODAL-2026-09-05): asset/artifact/dependency versioning + single-writer lock
-- Companion to design-lab-state-v1.sql (v1 stays frozen). Project/AssetVersion/
-- Artifact minimal data set per MULTIMODAL plan §8. No host dependency.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS project (
  project_id TEXT PRIMARY KEY,
  display_name TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS asset (
  asset_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(project_id),
  asset_kind TEXT NOT NULL CHECK (asset_kind IN ('raster','vector','text','audio','video','blend','psd','ai','doc','other')),
  created_at TEXT NOT NULL,
  UNIQUE(project_id, asset_id)
);

CREATE TABLE IF NOT EXISTS asset_version (
  version_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES asset(asset_id),
  version_no INTEGER NOT NULL,
  content_sha256 TEXT NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PENDING','ACTIVE','SUPERSEDED','FAILED','CANCELLED')),
  created_at TEXT NOT NULL,
  UNIQUE(asset_id, version_no),
  UNIQUE(asset_id, content_sha256)
);

CREATE TABLE IF NOT EXISTS artifact (
  artifact_id TEXT PRIMARY KEY,
  version_id TEXT NOT NULL REFERENCES asset_version(version_id),
  path TEXT NOT NULL,
  sha256 TEXT,
  byte_size INTEGER,
  role TEXT NOT NULL DEFAULT 'output'
);

CREATE TABLE IF NOT EXISTS asset_dependency (
  depends_on_version_id TEXT NOT NULL REFERENCES asset_version(version_id),
  required_by_version_id TEXT NOT NULL REFERENCES asset_version(version_id),
  PRIMARY KEY (depends_on_version_id, required_by_version_id)
);

-- Single-writer document lock: one writer per document at a time; a takeover
-- must be explicit (user handover), never silent (MULTIMODAL §8).
CREATE TABLE IF NOT EXISTS asset_writer_lock (
  resource_key TEXT PRIMARY KEY,
  holder_attempt_id TEXT NOT NULL,
  generation INTEGER NOT NULL DEFAULT 1,
  state TEXT NOT NULL DEFAULT 'HELD',
  acquired_at TEXT NOT NULL,
  expires_at TEXT
);
