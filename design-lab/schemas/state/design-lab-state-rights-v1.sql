-- SPDX-License-Identifier: MIT
-- Human RIGHTS gate decisions. design-lab/schemas/state/design-lab-state-rights-v1.sql
--
-- The RIGHTS gate had a contract and no store: design-lab/schemas/contracts/
-- rights-decision.schema.json closed its properties and froze its decision enum,
-- design-lab/config/rights-registry.json recorded 74 licence subjects, and nothing in
-- src/ read either of them. An unstored decision is a decision no verb, no route and
-- no release check can cite, so the gate could not be reached from the product. This
-- table is that store, and it adds ONE table to the same local state database the jury
-- and quality records live in: no second store, no second writer, no host call.
--
-- Append-only, for the reason the jury table gives: a recorded rights decision is the
-- thing a later delivery or release decision cites, and editing it in place would move
-- the legal position under a decision already taken. A changed mind inserts a NEW row
-- whose `supersedes` names the row it replaces.
--
-- One source of truth per fact:
--   * document_json IS the rights decision (contracts/rights-decision.schema.json is
--     its contract and assurance/rights_ledger.py loads and validates it); the columns
--     below are projections of it, never independent fields a writer may set on its own;
--   * the decision CHECK list mirrors that schema's enum. It is restated here because a
--     database cannot load a JSON Schema, and design-lab/tests/test_rights_ledger.py
--     re-reads both sides and fails if they ever disagree -- a restatement with no
--     reconciliation is how a second authority gets born;
--   * the contract closes its properties and declares NO actor kind, so the signing
--     actor's declared kind lives here as a column the document cannot carry. It may be
--     NULL (the actor was name-checked only) and it may never name automation: that
--     CHECK is the database-level half of "no agent signs a human gate", so a writer
--     changed above rights_ledger.py still cannot store MODEL / AGENT / SYSTEM as the
--     party that cleared a licence.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS rights_decision (
  decision_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(project_id),
  use_scope TEXT NOT NULL CHECK (length(trim(use_scope)) > 0),
  decision TEXT NOT NULL
    CHECK (decision IN ('APPROVED','DENIED','PENDING_REVIEW','BLOCKED_BY_LICENSE')),
  decided_by TEXT NOT NULL CHECK (length(trim(decided_by)) > 0),
  actor_kind TEXT CHECK (actor_kind IS NULL OR actor_kind IN ('HUMAN','PANEL')),
  territory TEXT,
  license_ref TEXT,
  note TEXT,
  document_json TEXT NOT NULL,
  decided_at TEXT NOT NULL CHECK (length(trim(decided_at)) > 0),
  supersedes TEXT REFERENCES rights_decision(decision_id),
  UNIQUE(project_id, decision_id)
);

-- A signed decision is an attestation, not a mutable field. The CHECKs above keep the
-- vocabulary closed; these keep history from being rewritten.
CREATE TRIGGER IF NOT EXISTS rights_decision_no_update BEFORE UPDATE ON rights_decision
  BEGIN SELECT RAISE(ABORT, 'a signed rights decision is immutable'); END;
CREATE TRIGGER IF NOT EXISTS rights_decision_no_delete BEFORE DELETE ON rights_decision
  BEGIN SELECT RAISE(ABORT, 'a signed rights decision cannot be deleted'); END;

-- Read models: the decisions filed for one use scope, and the ones nothing replaced.
CREATE INDEX IF NOT EXISTS rights_decision_scope ON rights_decision(project_id, use_scope);
CREATE INDEX IF NOT EXISTS rights_decision_state ON rights_decision(project_id, decision);
