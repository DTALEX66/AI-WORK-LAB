-- SPDX-License-Identifier: MIT
-- DL-P0-020/021/022/030/031/032/040 (Deep Adaptation Wave B): Creative
-- Execution OS additive migration. v1 tables, existing IDs and existing bytes
-- stay frozen; this file only adds columns, tables and append-only guards.
-- No second database is introduced: it extends .project-local/state/design-lab.db.
--
-- MIGRATION STATUS: MIGRATION_CANDIDATE_PENDING_AUDIT
-- (DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-F010). Rehearsed on a database
-- copy: backup -> migrate -> legacy readback -> new writes -> restart -> rerun
-- migration -> trigger behaviour -> rollback, all 15 steps passing
-- (reports/current/CREATIVE-MIGRATION-REHEARSAL.json). A passing rehearsal
-- permits the production label; only the owner or Codex may grant it.
PRAGMA foreign_keys = ON;

-- DL-P0-022: AssetVersion V2 lineage fields. NULL parent = root of a branch.
ALTER TABLE asset_version ADD COLUMN parent_version_id TEXT REFERENCES asset_version(version_id);
ALTER TABLE asset_version ADD COLUMN branch TEXT NOT NULL DEFAULT 'main';
ALTER TABLE asset_version ADD COLUMN label TEXT;
ALTER TABLE asset_version ADD COLUMN generation INTEGER NOT NULL DEFAULT 1;

-- DL-P0-020: CreativeJob binds a design job to brief/direction/deliverables.
CREATE TABLE creative_job (
  job_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL REFERENCES operation_intent(operation_id),
  project_id TEXT NOT NULL REFERENCES project(project_id),
  brief_ref TEXT NOT NULL,
  direction_ref TEXT,
  rights_profile TEXT NOT NULL,
  spec_json TEXT NOT NULL,
  spec_sha256 TEXT NOT NULL,
  created_at TEXT NOT NULL
);

CREATE TABLE creative_job_deliverable (
  job_id TEXT NOT NULL REFERENCES creative_job(job_id),
  deliverable_id TEXT NOT NULL,
  asset_kind TEXT NOT NULL CHECK (asset_kind IN
    ('raster','vector','text','audio','video','blend','psd','ai','doc','other')),
  host_target TEXT NOT NULL,
  editable INTEGER NOT NULL DEFAULT 1 CHECK (editable IN (0,1)),
  PRIMARY KEY (job_id, deliverable_id)
);

-- DL-P0-021: one lineage row per operation; a version has exactly one producer.
CREATE TABLE operation_lineage (
  lineage_id TEXT PRIMARY KEY,
  operation_id TEXT NOT NULL UNIQUE REFERENCES operation_intent(operation_id),
  job_id TEXT NOT NULL REFERENCES creative_job(job_id),
  provider_id TEXT NOT NULL,
  model_id TEXT,
  params_sha256 TEXT NOT NULL,
  attempt_id TEXT,
  recorded_at TEXT NOT NULL
);

CREATE TABLE lineage_input (
  lineage_id TEXT NOT NULL REFERENCES operation_lineage(lineage_id),
  version_id TEXT NOT NULL REFERENCES asset_version(version_id),
  role TEXT NOT NULL DEFAULT 'input',
  PRIMARY KEY (lineage_id, version_id, role)
);

CREATE TABLE lineage_output (
  lineage_id TEXT NOT NULL REFERENCES operation_lineage(lineage_id),
  version_id TEXT NOT NULL REFERENCES asset_version(version_id),
  role TEXT NOT NULL DEFAULT 'output',
  PRIMARY KEY (lineage_id, version_id, role),
  UNIQUE (version_id)
);

-- DL-P0-032: rejection is terminal and append-only; the guard never rewrites
-- asset_version state, so historical evidence keeps its original meaning.
CREATE TABLE version_rejection (
  version_id TEXT PRIMARY KEY REFERENCES asset_version(version_id),
  reason TEXT NOT NULL,
  actor TEXT NOT NULL,
  evidence_ref TEXT NOT NULL,
  rejected_at TEXT NOT NULL
);

CREATE TABLE requirement_event (
  event_no INTEGER PRIMARY KEY AUTOINCREMENT,
  req_id TEXT NOT NULL,
  job_id TEXT NOT NULL REFERENCES creative_job(job_id),
  kind TEXT NOT NULL CHECK (kind IN ('DEFINED','VERIFIED','FAILED','WAIVED','CONTRADICTED','REOPENED')),
  status TEXT NOT NULL CHECK (status IN ('OPEN','MET','FAILED','WAIVED','CONTRADICTED')),
  statement TEXT,
  acceptance TEXT,
  priority TEXT CHECK (priority IS NULL OR priority IN ('MUST','SHOULD','MAY')),
  evidence_ref TEXT,
  artifact_sha256 TEXT,
  readback_sha256 TEXT,
  actor TEXT NOT NULL,
  note TEXT,
  at TEXT NOT NULL
);

CREATE TABLE decision_event (
  event_no INTEGER PRIMARY KEY AUTOINCREMENT,
  dec_id TEXT NOT NULL,
  job_id TEXT NOT NULL REFERENCES creative_job(job_id),
  kind TEXT NOT NULL CHECK (kind IN ('PROPOSED','DECIDED','SUPERSEDED','REVERSED')),
  gate TEXT CHECK (gate IS NULL OR gate IN
    ('DIRECTION','QUALITY','RIGHTS','PRODUCTION','RELEASE','METHOD')),
  actor TEXT NOT NULL,
  actor_kind TEXT NOT NULL CHECK (actor_kind IN ('human','agent')),
  options_json TEXT,
  chosen TEXT,
  rationale TEXT,
  requirement_refs TEXT,
  supersedes TEXT,
  at TEXT NOT NULL
);

-- DL-P0-040: correlation only. No session content, transcript or credentials.
CREATE TABLE worklab_session_link (
  link_id TEXT PRIMARY KEY,
  job_id TEXT NOT NULL REFERENCES creative_job(job_id),
  session_ref TEXT NOT NULL,
  source_system TEXT NOT NULL DEFAULT 'WORK-LAB',
  note TEXT,
  linked_at TEXT NOT NULL,
  UNIQUE (job_id, session_ref)
);

CREATE TRIGGER version_rejection_no_update BEFORE UPDATE ON version_rejection
  BEGIN SELECT RAISE(ABORT, 'version rejection is terminal'); END;
CREATE TRIGGER version_rejection_no_delete BEFORE DELETE ON version_rejection
  BEGIN SELECT RAISE(ABORT, 'version rejection is append-only'); END;
CREATE TRIGGER requirement_event_no_update BEFORE UPDATE ON requirement_event
  BEGIN SELECT RAISE(ABORT, 'requirement events are append-only'); END;
CREATE TRIGGER requirement_event_no_delete BEFORE DELETE ON requirement_event
  BEGIN SELECT RAISE(ABORT, 'requirement events are append-only'); END;
CREATE TRIGGER decision_event_no_update BEFORE UPDATE ON decision_event
  BEGIN SELECT RAISE(ABORT, 'decision events are append-only'); END;
CREATE TRIGGER decision_event_no_delete BEFORE DELETE ON decision_event
  BEGIN SELECT RAISE(ABORT, 'decision events are append-only'); END;
CREATE TRIGGER operation_lineage_no_update BEFORE UPDATE ON operation_lineage
  BEGIN SELECT RAISE(ABORT, 'operation lineage is immutable'); END;
CREATE TRIGGER operation_lineage_no_delete BEFORE DELETE ON operation_lineage
  BEGIN SELECT RAISE(ABORT, 'operation lineage is immutable'); END;
