-- SPDX-License-Identifier: MIT
-- E-SLICE-01 P0-A+ DB-level single-choice invariant.
--
-- design-layer-v1 introduced the tables; its application transaction already
-- de-selects sibling choices within one brief (P0-01). This v2 migration adds
-- the LAST-LINE-DEFENCE database constraint so that no database state -- even
-- a hand-edited or legacy one -- can ever hold more than one "final" chosen
-- direction per active brief:
--
--   * at most one design_direction row may carry chosen=1 per (active) brief;
--   * a live row is never superseded in place (revision appends a NEW row and
--     leaves the live one with superseded_by NULL), so the WHERE clause keys
--     the index on the live rows only.
--
-- The migration runner PRE-CHECKS for existing duplicate choices and fails
-- closed (listing the offending briefs) rather than auto-picking a winner with
-- MAX(direction_id); that would make a Human design decision on the user's
-- behalf. Fresh/empty databases have no duplicates and apply cleanly.
CREATE UNIQUE INDEX IF NOT EXISTS ux_design_direction_one_chosen_per_brief
ON design_direction(brief_id)
WHERE chosen = 1
  AND superseded_by IS NULL;
