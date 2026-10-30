-- SPDX-License-Identifier: MIT
-- Knowledge feedback candidates and their revocation receipts.
-- design-lab/schemas/state/design-lab-state-knowledge-v1.sql
--
-- The candidate document in src/design_lab/assurance/knowledge_feedback.py is a
-- validated contract (design-lab/assurance-knowledge-candidate/v2). This table is
-- what makes a review survive a restart, so the Workbench can read back what a
-- person actually decided instead of an empty panel.
--
-- History is append-only: creating a candidate writes revision 1, and every
-- review or revocation appends the next revision of the same document. Editing a
-- row in place would silently rewrite the state a human signed, so update and
-- delete are refused by trigger. A candidate id is unique inside one project; the
-- façade treats an identical resubmission as a replay and a different payload
-- under the same id as a conflict.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS knowledge_candidate (
  project_id TEXT NOT NULL REFERENCES project(project_id),
  candidate_id TEXT NOT NULL,
  revision INTEGER NOT NULL CHECK (revision >= 1),
  candidate_type TEXT NOT NULL
    CHECK (candidate_type IN ('METHOD','JURY_CORRECTION','PRODUCTION_LESSON')),
  review_state TEXT NOT NULL
    CHECK (review_state IN ('PENDING_HUMAN_APPROVAL','APPROVED','REJECTED')),
  revocation_state TEXT NOT NULL CHECK (revocation_state IN ('ACTIVE','REVOKED')),
  document_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  PRIMARY KEY (project_id, candidate_id, revision)
);

CREATE TRIGGER IF NOT EXISTS knowledge_candidate_no_update
  BEFORE UPDATE ON knowledge_candidate
  BEGIN SELECT RAISE(ABORT, 'a knowledge candidate revision is immutable'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_candidate_no_delete
  BEFORE DELETE ON knowledge_candidate
  BEGIN SELECT RAISE(ABORT, 'a knowledge candidate revision cannot be deleted'); END;

CREATE INDEX IF NOT EXISTS knowledge_candidate_state
  ON knowledge_candidate(project_id, review_state, revocation_state);

-- The standalone revocation record is the receipt a reader can quote: it names
-- the candidate, the reason, the actor and the timestamp, and says export is
-- blocked. It is stored beside the candidate revision because applying it to the
-- document is not the same act as recording that a revocation was requested.
CREATE TABLE IF NOT EXISTS knowledge_revocation (
  project_id TEXT NOT NULL,
  candidate_id TEXT NOT NULL,
  document_json TEXT NOT NULL,
  recorded_at TEXT NOT NULL,
  PRIMARY KEY (project_id, candidate_id)
);

CREATE TRIGGER IF NOT EXISTS knowledge_revocation_no_update
  BEFORE UPDATE ON knowledge_revocation
  BEGIN SELECT RAISE(ABORT, 'a knowledge revocation receipt is immutable'); END;
CREATE TRIGGER IF NOT EXISTS knowledge_revocation_no_delete
  BEFORE DELETE ON knowledge_revocation
  BEGIN SELECT RAISE(ABORT, 'a knowledge revocation receipt cannot be deleted'); END;
