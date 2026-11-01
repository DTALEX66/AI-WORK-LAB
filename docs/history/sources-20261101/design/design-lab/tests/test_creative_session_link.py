# SPDX-License-Identifier: MIT
"""DL-P0-040 WORK-LAB session link: correlation only, no session content."""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from design_lab.creative import creative_job, session_link, store  # noqa: E402


def brief():
    return {
        "schemaVersion": "design-lab/creative-job/v1",
        "project_id": "p-session",
        "brief_ref": {"brief_id": "brief-session", "sha256": "sha256:" + "a" * 64},
        "rights_profile": {"profile_id": "rights-1", "gate_state": "CHECKED"},
        "deliverables": [{"deliverable_id": "poster", "asset_kind": "psd",
                          "host_target": "photoshop-2025", "editable": True}],
        "host_targets": [{"host_id": "photoshop-2025", "mode": "process-isolated",
                          "editable_source": True, "evidence_level": "E2"}],
    }


class SessionLinkTests(unittest.TestCase):
    def setUp(self):
        parent = ROOT / '.project-local/task-runtime/creative-session-tests'
        parent.mkdir(parents=True, exist_ok=True)
        temporary = tempfile.TemporaryDirectory(dir=parent)
        self.addCleanup(temporary.cleanup)
        self.conn = store.connect(Path(temporary.name) / 'creative.db')
        self.addCleanup(self.conn.close)
        created = creative_job.create_job(self.conn, brief(), idempotency_scope="s", idempotency_key="job")
        self.job_id = created["job_id"]

    def test_link_is_idempotent(self):
        first = session_link.link_session(self.conn, self.job_id, session_ref="wl-2026-09-13-001")
        second = session_link.link_session(self.conn, self.job_id, session_ref="wl-2026-09-13-001")
        self.assertTrue(first["created"])
        self.assertFalse(second["created"])
        self.assertEqual(first["link_id"], second["link_id"])

    def test_reference_must_be_opaque_not_a_path_or_payload(self):
        for bad in ("../../secrets", "C:/Users/ALEX/session.json", "session ref", "a" * 65, "",
                    "user@example.com"):
            with self.subTest(bad=bad), self.assertRaises(store.CreativeError):
                session_link.link_session(self.conn, self.job_id, session_ref=bad)

    def test_session_content_cannot_be_attached(self):
        with self.assertRaisesRegex(store.CreativeError, "correlation only"):
            session_link.assert_correlation_only({"session_ref": "wl-1", "transcript": "user: hi"})
        with self.assertRaisesRegex(store.CreativeError, "refused fields"):
            session_link.assert_correlation_only({"session_ref": "wl-1", "prompt": "make it pop"})
        session_link.assert_correlation_only({"session_ref": "wl-1", "source_system": "WORK-LAB",
                                              "note": "requested by the packaging review"})

    def test_note_is_a_short_remark_not_a_transcript(self):
        with self.assertRaisesRegex(store.CreativeError, "not transcript content"):
            session_link.link_session(self.conn, self.job_id, session_ref="wl-1",
                                      note="line one\nline two")
        with self.assertRaisesRegex(store.CreativeError, "short correlation remark"):
            session_link.link_session(self.conn, self.job_id, session_ref="wl-1", note="x" * 201)

    def test_unknown_source_system_is_refused(self):
        with self.assertRaisesRegex(store.CreativeError, "unknown source system"):
            session_link.link_session(self.conn, self.job_id, session_ref="wl-1", source_system="OpenHuman")

    def test_summary_projects_counts_and_opaque_ids_only(self):
        session_link.link_session(self.conn, self.job_id, session_ref="wl-1", note="requested by review")
        session_link.link_session(self.conn, self.job_id, session_ref="wl-2", source_system="ArcheAxis")
        summary = session_link.summary(self.conn, self.job_id)
        self.assertEqual(summary["link_count"], 2)
        self.assertEqual(summary["session_refs"], ["wl-1", "wl-2"])
        self.assertFalse(summary["contains_session_content"])
        self.assertEqual(set(summary), {"job_id", "link_count", "session_refs", "source_systems",
                                        "contains_session_content", "boundary"})

    def test_links_can_be_withdrawn_by_reference(self):
        session_link.link_session(self.conn, self.job_id, session_ref="wl-1")
        session_link.link_session(self.conn, self.job_id, session_ref="wl-2")
        self.assertEqual(session_link.strip_links(self.conn, "wl-1"), 1)
        self.assertEqual([item["session_ref"] for item in session_link.links(self.conn, self.job_id)], ["wl-2"])

    def test_unlink_removes_a_single_link(self):
        link = session_link.link_session(self.conn, self.job_id, session_ref="wl-1")
        self.assertTrue(session_link.unlink(self.conn, link["link_id"]))
        self.assertFalse(session_link.unlink(self.conn, link["link_id"]))


    def test_a_relink_under_another_source_answers_from_the_row_and_then_refuses(self):
        """The response and the persisted record must never disagree about who correlated the job.

        `link_session` used to return the CALL ARGUMENT for an existing link while the row is
        write-once -- no UPDATE exists and UNIQUE(job_id, session_ref) blocks a second insert -- so
        re-linking the same pair under another source reported that new source while the database
        kept the first one (owner audit 2026-10-26, finding 7: 「会话关联响应与持久化来源可能不同」).
        """
        linked = session_link.link_session(self.conn, self.job_id, session_ref="wl-2026-09-13-002",
                                           source_system="WORK-LAB")
        again = session_link.link_session(self.conn, self.job_id, session_ref="wl-2026-09-13-002",
                                          source_system="WORK-LAB")
        self.assertEqual(linked["source_system"], again["source_system"])
        self.assertEqual("WORK-LAB", session_link.links(self.conn, self.job_id)[0]["source_system"],
                         "the stored row does not carry the source the answer reported")
        with self.assertRaisesRegex(store.CreativeError, "not rewritten by a second"):
            session_link.link_session(self.conn, self.job_id, session_ref="wl-2026-09-13-002",
                                       source_system="ArcheAxis")
        self.assertEqual(["WORK-LAB"],
                         [item["source_system"] for item in session_link.links(self.conn,
                                                                               self.job_id)],
                         "the refused relink changed the stored provenance anyway")
        self.assertEqual(1, len(session_link.links(self.conn, self.job_id)),
                         "the refused relink wrote a second link")

    def test_nothing_reaches_this_module_yet_so_the_divergence_was_not_user_visible(self):
        """Recorded as an assertion, not as prose, because it decides the evidence level.

        The surface population is enumerated from the git index -- the service routes, the CLI, the
        workbench sources and the workflow files -- and none of them names this module, so the
        defect above was latent in an unwired surface: E2 at the module level, not E3 in a real
        product flow. Inventory files that merely LIST this module (the report index, the creative
        package's re-export, the CI bookkeeping scripts, the migration table census) are not
        reachability and are not counted here. The day someone wires a route, this test goes red and
        that person owes the read-back proof instead of inheriting my claim.
        """
        import subprocess
        listing = subprocess.run(["git", "ls-files", "-z"], cwd=str(ROOT), capture_output=True,
                                 check=True).stdout.decode("utf-8").split("\0")
        surface = [rel for rel in listing
                   if (rel.startswith("src/design_lab/") and rel.endswith(".py")
                       and rel not in ("src/design_lab/creative/session_link.py",
                                       "src/design_lab/creative/__init__.py"))
                   or rel.startswith("apps/workbench/") and rel.endswith((".ts", ".html"))
                   or rel.startswith(".github/workflows/")]
        self.assertGreater(len(surface), 60,
                           "the surface population collapsed to %s files, so this test would be "
                           "reading an empty set and calling it a pass" % len(surface))
        reached = []
        for rel in surface:
            text = (ROOT / rel).read_text(encoding="utf-8")
            if "session_link" in text or "link_session" in text:
                reached.append(rel)
        self.assertEqual([], reached,
                         "these reachable-surface files now name session correlation, so the "
                         "unwired claim above is stale and an E3 read-back is owed: %s"
                         % sorted(reached))


if __name__ == "__main__":
    unittest.main()
