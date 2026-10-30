-- SPDX-License-Identifier: MIT
-- DESIGN-LAB — the knowledge library's one mutable truth source, plus its derived index.
--
-- Two canonical tables and one derived one, and the split is the whole point of the design:
--
--   knowledge_entry           one row per entry identity (what a later entry may supersede);
--   knowledge_entry_revision  the entry's content, append-only, one row per revision. The
--                             revision's whole document is stored as canonical JSON so a reader
--                             can re-validate the bytes it serves, and "current" is
--                             MAX(revision) computed at read time -- there is no `active` flag,
--                             because a mutable current-marker is how a second truth source is
--                             born (the ACTIVE-version invariant this repository already holds);
--   knowledge_entry_fts       an FTS5 trigram index over the current revision's searchable
--                             fields. It is DERIVED: deleting every row here loses no fact, and
--                             src/design_lab/knowledge_library.py rebuilds it from the revision
--                             table. No trigger keeps it in sync on purpose -- a trigger would
--                             make the index a second writer, and the rebuild is the proof that
--                             the two can never disagree for long.
--
-- Trigram is chosen for CJK substring search, and it cannot match a query shorter than three
-- characters (measured on this host's SQLite: MATCH '分镜' answers zero rows). That is not a
-- comment to be trusted later -- design-lab/tests/test_knowledge_library.py asserts the short
-- query really does miss the index, so the LIKE fallback in the module has a failing control
-- rather than an assumption.
--
-- Append-only is enforced here, not by convention: UPDATE and DELETE on either canonical table
-- raise ABORT. A correction is a new revision, and a superseded entry keeps every revision it
-- ever had (DL-KB-02 acceptance A4: the same source at different versions is retained).

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS knowledge_entry (
  entry_id      TEXT PRIMARY KEY,
  -- The entry this one replaces, decided once at creation and never rewritten: supersession is
  -- about identity, not about which revision a reader happened to look at.
  supersedes    TEXT REFERENCES knowledge_entry(entry_id),
  created_at    TEXT NOT NULL,
  created_by    TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS knowledge_entry_revision (
  entry_id       TEXT NOT NULL,
  revision       INTEGER NOT NULL CHECK (revision >= 1),
  entry_type     TEXT NOT NULL CHECK (entry_type IN
                   ('STANDARD', 'METHOD', 'PROMPT', 'MODEL_GUIDE', 'RECIPE', 'CASE')),
  title          TEXT NOT NULL CHECK (length(title) > 0),
  summary        TEXT NOT NULL CHECK (length(summary) > 0),
  -- Digest over the content-bearing fields only (not id, revision, timestamps or the
  -- recommendation flag), so "same content, new revision" and "new content" are distinguishable.
  content_sha256 TEXT NOT NULL CHECK (content_sha256 LIKE 'sha256:%'),
  -- The recommendation is a property of a revision, recorded when that revision is written.
  -- A newer revision may leave it at 0, which is how "latest" and "recommended" are allowed to
  -- differ (DL-KB-03: 推荐版本与最新版本分开呈现) without a mutable pointer anywhere.
  recommended    INTEGER NOT NULL CHECK (recommended IN (0, 1)),
  created_at     TEXT NOT NULL,
  created_by     TEXT NOT NULL,
  document_json  TEXT NOT NULL,
  PRIMARY KEY (entry_id, revision),
  FOREIGN KEY (entry_id) REFERENCES knowledge_entry(entry_id)
);

CREATE INDEX IF NOT EXISTS knowledge_entry_revision_by_type
  ON knowledge_entry_revision(entry_type);
CREATE INDEX IF NOT EXISTS knowledge_entry_revision_by_digest
  ON knowledge_entry_revision(content_sha256);

-- The index receipt: when the derived table was last rebuilt and from how many canonical rows.
-- It is a measurement about the index, never a source of truth about an entry.
CREATE TABLE IF NOT EXISTS knowledge_index_state (
  name       TEXT PRIMARY KEY,
  rebuilt_at TEXT NOT NULL,
  rows       INTEGER NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS knowledge_entry_fts USING fts5(
  entry_id UNINDEXED,
  revision UNINDEXED,
  title,
  summary,
  body,
  tags,
  targets,
  tokenize = 'trigram'
);

CREATE TRIGGER IF NOT EXISTS knowledge_entry_no_update
BEFORE UPDATE ON knowledge_entry
BEGIN
  SELECT RAISE(ABORT, 'knowledge_entry is append-only');
END;

CREATE TRIGGER IF NOT EXISTS knowledge_entry_no_delete
BEFORE DELETE ON knowledge_entry
BEGIN
  SELECT RAISE(ABORT, 'knowledge_entry is append-only');
END;

CREATE TRIGGER IF NOT EXISTS knowledge_entry_one_successor
BEFORE INSERT ON knowledge_entry
WHEN NEW.supersedes IS NOT NULL
BEGIN
  -- One entry may be replaced by at most one entry. The routes check this before writing, but a
  -- check that reads before it writes is only a likelihood: two writers can both see "no
  -- successor yet". This trigger is what makes it a guarantee, and it covers any writer that
  -- forgets the application check. It fires only on new rows, so a library that already holds a
  -- fork from before this rule stays readable instead of refusing to open.
  SELECT RAISE(ABORT, 'knowledge entry may have at most one successor')
  WHERE EXISTS (SELECT 1 FROM knowledge_entry WHERE supersedes = NEW.supersedes);
END;

CREATE TRIGGER IF NOT EXISTS knowledge_entry_revision_no_update
BEFORE UPDATE ON knowledge_entry_revision
BEGIN
  SELECT RAISE(ABORT, 'knowledge_entry_revision is append-only; write a new revision');
END;

CREATE TRIGGER IF NOT EXISTS knowledge_entry_revision_no_delete
BEFORE DELETE ON knowledge_entry_revision
BEGIN
  SELECT RAISE(ABORT, 'knowledge_entry_revision is append-only; a revision is never withdrawn');
END;
