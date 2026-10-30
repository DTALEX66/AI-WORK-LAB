-- SPDX-License-Identifier: MIT
-- ResearchFinding storage. design-lab/schemas/state/design-lab-state-research-v1.sql
--
-- design-lab/schemas/research-finding.schema.json has declared finding_id/claim/sourceRefs
-- since before this table existed, and design-lab/config/object-model.json names the object
-- with that schemaRef -- yet NOTHING in src/ ever loaded the file, so no document had ever
-- been validated against it and no verb, route or read-back could cite a finding. The
-- Workbench panel said so honestly ("no persistence route for research findings"), which
-- made the gap visible rather than false-green; this file closes it.
--
-- WHAT THIS TABLE IS, stated where the data lives. Per AUTHORITY.md / AGENTS.md, DESIGN-LAB
-- owns audited WORKING findings and ArcheAxis owns long-term knowledge truth. So every row
-- here is per-project, re-derivable working state: it is not a knowledge export, it is not a
-- KnowledgeCandidate, and nothing in this schema promotes it. A project's findings can be
-- re-derived from their sources; a finding nobody can name a source for is a guess, which is
-- why `source_ref_count > 0` is a column CHECK and not only a Python rule.
--
-- Append-only, for the same reason the rights and jury tables give: a finding is the thing a
-- later direction or jury discussion cites, and rewriting one in place would move the claim
-- under a decision already taken. A correction is a NEW row whose `supersedes` names the row
-- it replaces (src/design_lab/assurance/research_store.py refuses a row superseded twice).
--
-- One source of truth per fact:
--   * document_json IS the ResearchFinding (design-lab/schemas/research-finding.schema.json
--     is its contract and assurance/research_store.py loads and validates against it -- the
--     field list is never copied into Python, and this table adds no document field);
--   * `confidence` restates the contract's enum because a database cannot load a JSON Schema.
--     design-lab/tests/test_research_store.py re-reads both sides and fails if they disagree;
--     an unreconciled restatement is how a second authority gets born;
--   * `recorded_by` / `actor_kind` are columns the closed contract cannot carry (it declares
--     no actor at all, so an HTTP submission cannot state one). A research finding is NOT a
--     human gate -- an agent may record one -- but it may not record one AS A HUMAN: the
--     declared kind is stored so a reader can tell a human-authored finding from a
--     machine-authored one from one whose author was never stated, which three different
--     facts are and may not be shown as one word;
--   * `not_design_rule` may only ever be 1 or NULL. The contract's const is `true` and its
--     description is the whole point: 研究结论不能直接冒充设计规则. A row cannot record
--     itself as a design rule, and a NULL ("the author never disclaimed it") is reported as
--     exactly that rather than being read as a disclaimer;
--   * there is NO timestamp column on purpose. The contract declares none and this module
--     will not invent one: `recorded_at` would be a moment nobody stated, so ordering is
--     insertion order (rowid) and the read-back says it does not know when anything was said.
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS research_finding (
  finding_id TEXT PRIMARY KEY,
  project_id TEXT NOT NULL REFERENCES project(project_id),
  claim TEXT NOT NULL CHECK (length(trim(claim)) > 0),
  confidence TEXT
    CHECK (confidence IN ('high','medium','low','speculative') OR confidence IS NULL),
  source_refs_json TEXT NOT NULL CHECK (length(trim(source_refs_json)) > 0
                                        AND source_refs_json <> '[]'),
  source_ref_count INTEGER NOT NULL CHECK (source_ref_count > 0),
  not_design_rule INTEGER CHECK (not_design_rule IS NULL OR not_design_rule = 1),
  recorded_by TEXT CHECK (recorded_by IS NULL OR length(trim(recorded_by)) > 0),
  actor_kind TEXT CHECK (actor_kind IS NULL OR actor_kind IN
    ('HUMAN','PANEL','AGENT','AI','ASSISTANT','AUTOMATED','BOT','LLM','MACHINE','MODEL',
     'PIPELINE','SCRIPT','SERVICE','SYSTEM','TOOL')),
  document_json TEXT NOT NULL,
  supersedes TEXT REFERENCES research_finding(finding_id),
  UNIQUE(project_id, finding_id)
);

-- A filed finding is a record, not a mutable field. The CHECKs above keep the vocabularies
-- closed; these keep history from being rewritten or erased.
CREATE TRIGGER IF NOT EXISTS research_finding_no_update BEFORE UPDATE ON research_finding
  BEGIN SELECT RAISE(ABORT, 'a filed research finding is immutable'); END;
CREATE TRIGGER IF NOT EXISTS research_finding_no_delete BEFORE DELETE ON research_finding
  BEGIN SELECT RAISE(ABORT, 'a filed research finding cannot be deleted'); END;

-- Read models: the findings of one project, and the supersede links between them.
CREATE INDEX IF NOT EXISTS research_finding_project ON research_finding(project_id, confidence);
CREATE INDEX IF NOT EXISTS research_finding_supersedes ON research_finding(supersedes);
