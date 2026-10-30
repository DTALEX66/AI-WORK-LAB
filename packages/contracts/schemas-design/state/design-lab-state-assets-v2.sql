-- SPDX-License-Identifier: MIT
-- R3-06 additive migration. Existing IDs/paths and bytes remain unchanged.
CREATE TABLE asset_publication (
  publication_id TEXT PRIMARY KEY,
  asset_id TEXT NOT NULL REFERENCES asset(asset_id),
  store_root TEXT NOT NULL,
  stage_path TEXT NOT NULL,
  final_path TEXT NOT NULL,
  quarantine_path TEXT NOT NULL,
  sha256 TEXT NOT NULL,
  holder_attempt_id TEXT NOT NULL,
  generation INTEGER NOT NULL,
  state TEXT NOT NULL CHECK (state IN ('PREPARED','COMMITTED','QUARANTINED','MISSING')),
  version_id TEXT REFERENCES asset_version(version_id),
  created_at TEXT NOT NULL
);
