-- SPDX-License-Identifier: MIT
-- DESIGN-LAB — recorded judgements about a knowledge entry (DL-KB-05 acceptance D5).
--
-- Why a table at all: `knowledge_entry_revision.recommended` is written with the revision and can
-- only ever say "this revision was recommended when it was created". Rolling the recommendation
-- BACK to an older revision, or marking a source dead and naming its replacement, are judgements
-- made LATER about bytes that must not change. There was nowhere to put them, so D5 had no route
-- and no field -- and a mutable pointer on the revision row would have broken the append-only
-- triggers that are the entry's whole history guarantee.
--
-- So a judgement is its own append-only fact:
--   kind='RECOMMENDATION'  revision=N, value='RECOMMENDED'  -- the newest row of this kind wins;
--   kind='SOURCE_STATE'    value='ACTIVE'|'INVALID', replaced_by=<another entry id or null>.
-- Neither touches a stored document, a content digest or the revision chain, which is what makes
-- "旧方案仍可读" true by construction: a plan pinned to revision 2 keeps reading exactly the bytes
-- it pinned while the entry's recommended pointer moves back to 1.
--
-- `recorded_by` is a named person and the service refuses an agent recording one (same rule as the
-- export approval in src/design_lab/knowledge_review.py). `reason` is required because a
-- recommendation moved without a stated why is a ranking wearing a costume.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS knowledge_judgement (
  -- SQLite has no regex in CHECK; GLOB would need 32 character classes, so the shape is asserted
  -- where it is minted (src/design_lab/knowledge_library.py) and only the prefix is pinned here.
  judgement_id TEXT PRIMARY KEY CHECK (substr(judgement_id, 1, 7) = 'kjudge-'),
  entry_id     TEXT NOT NULL REFERENCES knowledge_entry(entry_id),
  kind         TEXT NOT NULL CHECK (kind IN ('RECOMMENDATION', 'SOURCE_STATE')),
  -- Required for RECOMMENDATION, null for SOURCE_STATE: a source judgement is about where the
  -- content came from, not about which revision is current.
  revision     INTEGER CHECK (revision IS NULL OR revision >= 1),
  value        TEXT NOT NULL CHECK (length(value) > 0),
  -- The entry that takes over a dead source. Enforced as a real foreign key as well as by the
  -- writer, because "replaced by something the reader cannot open" is the failure this guards.
  replaced_by  TEXT REFERENCES knowledge_entry(entry_id),
  reason       TEXT NOT NULL CHECK (length(reason) > 0),
  recorded_by  TEXT NOT NULL CHECK (length(recorded_by) > 0),
  recorded_at  TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS knowledge_judgement_by_entry
  ON knowledge_judgement(entry_id, kind);

CREATE TRIGGER IF NOT EXISTS knowledge_judgement_no_update
BEFORE UPDATE ON knowledge_judgement
BEGIN
  SELECT RAISE(ABORT, 'knowledge_judgement is append-only; record a later judgement');
END;

CREATE TRIGGER IF NOT EXISTS knowledge_judgement_no_delete
BEFORE DELETE ON knowledge_judgement
BEGIN
  SELECT RAISE(ABORT, 'knowledge_judgement is append-only; a judgement is never withdrawn');
END;
