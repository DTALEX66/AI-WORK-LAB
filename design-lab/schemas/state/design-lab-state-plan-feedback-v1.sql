-- SPDX-License-Identifier: MIT
-- DESIGN-LAB — voluntary external-use feedback on one assistance plan revision.
--
-- DL-KB-16. The loop the owner asked for ends with "用户自愿记录外部使用反馈": a person takes the
-- material to an external tool, comes back, and says what happened. This table is that statement
-- and nothing else.
--
--   plan_feedback  one row per recorded statement, append-only. `feedback_no` grows per plan so a
--                  correction is a new row and the earlier statement stays readable; the list
--                  route serves the whole history, not a merged "current" value, because "it worked
--                  in Meshy" and "it did not work in Meshy" are both facts someone may need later.
--
-- What this table deliberately does NOT do:
--   * it has no column that could flip the plan's 已保存/已提供/已选用 states, and none that could
--     make 外部未验证 read as verified. The plan's own readback keeps computing those four facts and
--     `external.verified` stays a constant false; a feedback row is a person's report, not the
--     system's confirmation. The two are different verbs and the contract keeps them apart.
--   * actor_kind is CHECKed to 'human' at the storage layer, exactly like assistance_plan_choice,
--     so an application bug cannot file a machine's guess as somebody's experience.
--   * there is no "sent", "delivered" or "executed" field, because this service has no outbound
--     transport and never observes an external run.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS plan_feedback (
  plan_id      TEXT NOT NULL REFERENCES assistance_plan(plan_id),
  revision     INTEGER NOT NULL CHECK (revision >= 1),
  feedback_no  INTEGER NOT NULL CHECK (feedback_no >= 1),
  outcome      TEXT NOT NULL CHECK (outcome IN ('MATCHES', 'PARTIALLY_MATCHES', 'DOES_NOT_MATCH')),
  target_key   TEXT NOT NULL,
  actor        TEXT NOT NULL CHECK (length(trim(actor)) > 0),
  actor_kind   TEXT NOT NULL CHECK (actor_kind = 'human'),
  note         TEXT,
  source_ref   TEXT NOT NULL,
  recorded_at  TEXT NOT NULL,
  document_json TEXT NOT NULL CHECK (length(trim(document_json)) > 0),
  content_sha256 TEXT NOT NULL CHECK (length(content_sha256) = 71
                                      AND substr(content_sha256, 1, 7) = 'sha256:'),
  PRIMARY KEY (plan_id, feedback_no),
  FOREIGN KEY (plan_id, revision) REFERENCES assistance_plan_revision(plan_id, revision)
);

CREATE INDEX IF NOT EXISTS plan_feedback_by_plan
  ON plan_feedback(plan_id, feedback_no);

CREATE TRIGGER IF NOT EXISTS plan_feedback_no_update
BEFORE UPDATE ON plan_feedback
BEGIN
  SELECT RAISE(ABORT, 'plan_feedback is append-only; record a new statement');
END;

CREATE TRIGGER IF NOT EXISTS plan_feedback_no_delete
BEFORE DELETE ON plan_feedback
BEGIN
  SELECT RAISE(ABORT, 'plan_feedback is append-only; a recorded statement is never withdrawn');
END;
