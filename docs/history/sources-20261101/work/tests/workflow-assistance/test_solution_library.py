"""CL-06 gate: a solution is solidified from a repair that closed, not from one that sounded finished.

The library's whole value is the distinction it keeps:

* **verification and solidification are two steps.** The happy path builds a real repair record (BLOCKED
  task -> pack -> record -> approval -> imported result -> independent re-read -> SUCCEEDED) and only then
  solidifies. Draft and failed records are refused by name.
* **a revision never changes under a citation.** Editing revision 1 in place is refused, a gap is refused,
  and revision N+1 must name N as the thing it supersedes.
* **unverified material stays visibly unverified.** The import route only accepts `UNVERIFIED` + `MANUAL`
  and never recommends it; promotion is a new revision from solidify, not an in-place status flip.
* **search is local and says what it compared.** Chinese bigrams and ASCII tokens match stored text, the
  version relation is named (SAME / CHANGED / UNKNOWN), the recipe's own limits travel with the hit, and
  the summary records that no model and no AAOS call were involved.
"""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
for entry in (ROOT / "packages" / "client-neutral-core" / "scripts",
              ROOT / "services" / "orchestration"):
    sys.path.insert(0, str(entry))

import issue_projection  # noqa: E402
import project_temp  # noqa: E402
import repair_pack_projection as projection  # noqa: E402
import repair_state  # noqa: E402
import solution_library  # noqa: E402
from canonical_store import CanonicalStore  # noqa: E402

GENERATED_AT = "2026-10-23T06:00:00Z"
PROJECT_ID = "work-lab"
TASK_ID = "WL-CL06-1"
TARGET_VERSION = "2026.10.23"
REGISTRY = {"entries": [
    {"id": "codex", "display_name": "Codex", "support_level": "deep",
     "operations": ["detect", "capabilities", "plan", "apply", "invoke", "observe", "rollback"]},
]}


class SolutionLibraryTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.fixture = project_temp.fixture_dir("solution-library-")
        self.runtime = Path(self.fixture)
        self.project_root = self.runtime / "project"
        gate = self.project_root / projection.OWN_GATE_RELATIVE_PATH
        gate.parent.mkdir(parents=True, exist_ok=True)
        gate.write_text("# gate fixture\n", encoding="utf-8")
        self.store = CanonicalStore(self.runtime / "canonical.sqlite")
        self.store.register_project(PROJECT_ID, str(self.project_root), display_name="work-lab")
        self.store.upsert_task({
            "task_id": TASK_ID, "project_id": PROJECT_ID, "status": "BLOCKED",
            "created_at": "2026-10-23T01:00:00Z", "updated_at": "2026-10-23T02:00:00Z",
        })
        issues, summary, absent = issue_projection.load_issues(self.store, generated_at=GENERATED_AT)
        self.assertIsNotNone(issues, absent)
        self.assertIsNotNone(summary)
        built = projection.project_repair_packs(
            issues=issues, projects=self.store.list_projects(), registry=REGISTRY,
            adapters=["codex"], generated_at=GENERATED_AT)
        self.pack = built["packs"][0]
        self.plan_id = self.pack["packId"]

    def tearDown(self) -> None:
        self.store.close()
        project_temp.force_release(self.fixture)

    # -- lifecycle ------------------------------------------------------------------------------------

    def _through_approval(self) -> dict:
        recorded = repair_state.record_pack(self.store, self.pack)
        approved = repair_state.approve_pack(
            self.store, self.plan_id, authorization_ref="grant-cl06",
            grants={"grant-cl06": f"work-unit:{self.plan_id}"},
            expected_version=recorded["version"], approved_at="2026-10-23T06:10:00Z")
        return repair_state.declare_handoff(
            self.store, self.plan_id, claim="userDeclaredHandoff", channel="local-tool",
            claimed_recipient="cl06-local-repair", target_version=TARGET_VERSION,
            declared_at="2026-10-23T06:20:00Z", expected_version=approved["version"])

    def _close_record(self) -> dict:
        declared = self._through_approval()
        imported = repair_state.import_external_result(
            self.store, self.plan_id,
            {"schemaVersion": "worklab/external-repair-result/v1", "resultId": "R-CL06-1",
             "packId": self.plan_id, "projectId": PROJECT_ID, "targetVersion": TARGET_VERSION,
             "producedAt": "2026-10-23T06:30:00Z", "producer": "cl06-local-repair",
             "claimedOutcome": "SUCCEEDED", "evidenceRefs": [],
             "summary": "blocked task returned to RUNNING"},
            accepted_at="2026-10-23T06:31:00Z", expected_version=declared["version"])
        self.store.upsert_task({
            "task_id": TASK_ID, "project_id": PROJECT_ID, "status": "RUNNING",
            "created_at": "2026-10-23T01:00:00Z", "updated_at": "2026-10-23T06:40:00Z",
        })
        closed = repair_state.verify_record(self.store, self.plan_id,
                                            verified_at="2026-10-23T06:45:00Z",
                                            expected_version=imported["version"])
        self.assertEqual("SUCCEEDED", closed["status"], closed["payload"]["verifications"])
        return closed

    def _document(self, *, revision: int = 1, status: str = "VERIFIED",
                  source_ref: str | None = None, evidence_refs: list[str] | None = None,
                  issue_refs: list[str] | None = None, version: str = "0.2.1",
                  version_source: str = "DECLARED", software_id: str = "dsh",
                  keywords: list[str] | None = None, title: str | None = None,
                  supersedes: dict | None = None) -> dict:
        return solution_library.build_solution(
            solution_id="sol-dsh-blocked-session",
            title=title or "清理 DSH 缓存后恢复被阻塞的会话任务",
            software={"softwareId": software_id, "softwareVersion": version,
                      "platform": "win32", "versionSource": version_source},
            source={"kind": "REPAIR_RECORD",
                    "ref": source_ref or f"action_plan:{self.plan_id}#verification:v1",
                    "updatedAt": "2026-10-23T06:45:00Z"},
            preconditions=["客户端已完全退出"],
            steps=["备份缓存目录", "删除缓存目录", "重新启动并等待会话列表恢复"],
            expected=["任务从 BLOCKED 回到 RUNNING"],
            verification_steps=["重新读取任务状态，确认不再产生同一指纹"],
            invalid_when=["新版客户端改用其他缓存目录"],
            risks=[{"risk": "误删会话数据", "recovery": "操作前先复制缓存目录到备份路径"}],
            limits=["仅适用于 Windows 桌面版"],
            evidence_refs=evidence_refs if evidence_refs is not None else (
                list(self.pack["binds"]["evidenceRefs"])
                + [f"action_plan:{self.plan_id}#verification:v1"]),
            issue_refs=issue_refs if issue_refs is not None else list(
                self.pack["binds"]["issueFingerprints"]),
            keywords=keywords or ["缓存", "会话", "dsh", "blocked"],
            changes=f"revision {revision}",
            revision=revision,
            status=status,
            supersedes=supersedes,
        )

    # -- the two steps --------------------------------------------------------------------------------

    def test_a_closed_record_solidifies_into_a_verified_revision_that_survives_a_restart(self) -> None:
        self._close_record()
        document = self._document()
        self.assertEqual([], solution_library.validate_solution(
            document, schema=solution_library.load_schema()))
        result = solution_library.solidify_solution(self.store, self.plan_id, document,
                                                    schema=solution_library.load_schema())
        self.assertEqual("SOLIDIFIED", result["status"])
        self.assertFalse(result["contentIncluded"])
        self.assertEqual("independent", result["evidenceLevel"])
        self.assertTrue(result["recommended"], "the first verified revision is the current recipe")

        self.store.close()
        reopened = CanonicalStore(self.runtime / "canonical.sqlite")
        try:
            stored = reopened.read_solution("sol-dsh-blocked-session")
            self.assertIsNotNone(stored, "a restarted store lost the solution it just solidified")
            self.assertEqual("VERIFIED", stored["status"])
            self.assertEqual("1", str(stored["revision"]))
            self.assertTrue(stored["recommended"])
            self.assertIn("备份缓存目录", stored["payload"]["steps"])
            hit = solution_library.store_view(reopened, query="缓存", current_version="0.2.1")
            self.assertEqual("OK", hit["status"])
            self.assertEqual(1, hit["summary"]["returned"])
            self.assertEqual("SAME_VERSION", hit["results"][0]["versionHint"]["state"])
        finally:
            reopened.close()
            self.store = CanonicalStore(self.runtime / "canonical.sqlite")

    def test_a_draft_record_cannot_become_a_verified_solution(self) -> None:
        repair_state.record_pack(self.store, self.pack)
        with self.assertRaises(ValueError) as caught:
            solution_library.solidify_solution(self.store, self.plan_id, self._document(),
                                               schema=solution_library.load_schema())
        self.assertIn("SOLUTION_RECORD_NOT_SUCCEEDED", str(caught.exception))
        self.assertEqual([], self.store.list_solutions(), "a refused solidification left a row behind")

    def test_a_failed_record_cannot_become_a_verified_solution(self) -> None:
        declared = self._through_approval()
        imported = repair_state.import_external_result(
            self.store, self.plan_id,
            {"schemaVersion": "worklab/external-repair-result/v1", "resultId": "R-CL06-F",
             "packId": self.plan_id, "projectId": PROJECT_ID, "targetVersion": TARGET_VERSION,
             "producedAt": "2026-10-23T06:30:00Z", "producer": "cl06-local-repair",
             "claimedOutcome": "FAILED", "evidenceRefs": [],
             "summary": "fix did not hold"},
            accepted_at="2026-10-23T06:31:00Z", expected_version=declared["version"])
        failed = repair_state.verify_record(self.store, self.plan_id,
                                           verified_at="2026-10-23T06:45:00Z",
                                           expected_version=imported["version"])
        self.assertEqual("FAILED", failed["status"])
        with self.assertRaises(ValueError) as caught:
            solution_library.solidify_solution(self.store, self.plan_id, self._document(),
                                               schema=solution_library.load_schema())
        self.assertIn("SOLUTION_RECORD_NOT_SUCCEEDED", str(caught.exception))

    def test_the_recipe_must_carry_the_closed_packs_evidence_and_issues(self) -> None:
        self._close_record()
        missing_evidence = self._document(evidence_refs=[
            f"action_plan:{self.plan_id}#verification:v1"])
        with self.assertRaises(ValueError) as caught:
            solution_library.solidify_solution(self.store, self.plan_id, missing_evidence,
                                               schema=solution_library.load_schema())
        self.assertIn("SOLUTION_EVIDENCE_MISSING", str(caught.exception))

        wrong_issues = self._document(issue_refs=["f" * 16])
        with self.assertRaises(ValueError) as caught:
            solution_library.solidify_solution(self.store, self.plan_id, wrong_issues,
                                               schema=solution_library.load_schema())
        self.assertIn("SOLUTION_ISSUE_REFS_MISMATCH", str(caught.exception))

        wrong_source = self._document(source_ref="action_plan:another-pack#verification:v1")
        with self.assertRaises(ValueError) as caught:
            solution_library.solidify_solution(self.store, self.plan_id, wrong_source,
                                               schema=solution_library.load_schema())
        self.assertIn("SOLUTION_SOURCE_MISMATCH", str(caught.exception))

        unverified = self._document(status="UNVERIFIED")
        with self.assertRaises(ValueError) as caught:
            solution_library.solidify_solution(self.store, self.plan_id, unverified,
                                               schema=solution_library.load_schema())
        self.assertIn("SOLUTION_NOT_VERIFIED", str(caught.exception))
        self.assertEqual([], self.store.list_solutions())

    # -- revision rules -------------------------------------------------------------------------------

    def test_a_revision_is_immutable_and_a_gap_is_refused(self) -> None:
        self._close_record()
        first = solution_library.solidify_solution(self.store, self.plan_id, self._document(),
                                                   schema=solution_library.load_schema())
        self.assertEqual("SOLIDIFIED", first["status"])
        retry = solution_library.solidify_solution(self.store, self.plan_id, self._document(),
                                                   schema=solution_library.load_schema())
        self.assertEqual("UNCHANGED", retry["status"], "a retried solidification minted a revision")
        self.assertEqual(1, len(self.store.list_solutions()))

        changed = self._document()
        changed["steps"].append("第四步：清理旧日志")
        with self.assertRaises(ValueError) as caught:
            self.store.save_solution({"solutionId": changed["solutionId"], "revision": 1,
                                      "title": changed["title"], "status": changed["status"],
                                      "keywords": changed["keywords"], "payload": changed})
        self.assertIn("SOLUTION_REVISION_IMMUTABLE", str(caught.exception))

        gap = self._document(revision=3, supersedes={"solutionId": "sol-dsh-blocked-session",
                                                     "revision": 2})
        with self.assertRaises(ValueError) as caught:
            self.store.save_solution({"solutionId": gap["solutionId"], "revision": 3,
                                      "title": gap["title"], "status": gap["status"],
                                      "keywords": gap["keywords"], "payload": gap})
        self.assertIn("SOLUTION_REVISION_GAP", str(caught.exception))

        no_ancestor = self._document(revision=2)
        with self.assertRaises(ValueError) as caught:
            self.store.save_solution({"solutionId": no_ancestor["solutionId"], "revision": 2,
                                      "title": no_ancestor["title"], "status": no_ancestor["status"],
                                      "keywords": no_ancestor["keywords"], "payload": no_ancestor})
        self.assertIn("SOLUTION_SUPERSEDES_MISMATCH", str(caught.exception))

        second = self._document(revision=2, supersedes={"solutionId": "sol-dsh-blocked-session",
                                                        "revision": 1})
        second["keywords"] = ["缓存", "会话", "dsh", "blocked", "重启"]
        saved = self.store.save_solution({"solutionId": second["solutionId"], "revision": 2,
                                          "title": second["title"], "status": second["status"],
                                          "keywords": second["keywords"], "payload": second})
        self.assertTrue(saved["changed"])
        self.assertFalse(saved["recommended"], "a new revision does not silently become current")
        listed = self.store.list_solutions()
        self.assertEqual([2], [row["revision"] for row in listed],
                         "the library list must show one current revision per recipe")
        self.assertTrue(self.store.recommend_solution("sol-dsh-blocked-session", 2)["recommended"])
        self.assertFalse(self.store.read_solution("sol-dsh-blocked-session", 1)["recommended"])

    # -- unverified material --------------------------------------------------------------------------

    def test_unverified_material_stays_unverified_and_is_never_recommended(self) -> None:
        document = solution_library.build_solution(
            solution_id="sol-manual-note",
            title="同事口述的缓存清理办法",
            software={"softwareId": "dsh", "softwareVersion": "", "platform": "win32",
                      "versionSource": "UNKNOWN"},
            source={"kind": "MANUAL", "ref": "owner-note-2026-10-23", "updatedAt": GENERATED_AT},
            steps=["删除缓存目录后重启"],
            verification_steps=["尚未验证"],
            keywords=["缓存", "口述"],
            changes="initial note")
        self.assertIn(solution_library.UNKNOWN_VERSION_LIMIT, document["limits"])
        result = solution_library.import_unverified(self.store, document,
                                                    schema=solution_library.load_schema())
        self.assertEqual("IMPORTED", result["status"])
        self.assertEqual("UNVERIFIED", result["documentStatus"])
        self.assertFalse(result["recommended"])
        stored = self.store.read_solution("sol-manual-note")
        self.assertEqual("UNVERIFIED", stored["status"])
        self.assertFalse(stored["recommended"])

        with self.assertRaises(ValueError) as caught:
            solution_library.import_unverified(self.store, self._document(),
                                               schema=solution_library.load_schema())
        self.assertIn("SOLUTION_IMPORT_ONLY_UNVERIFIED", str(caught.exception))

        hit = solution_library.store_view(self.store, query="缓存")
        states = {item["solutionId"]: item["status"] for item in hit["results"]}
        self.assertEqual("UNVERIFIED", states["sol-manual-note"],
                         "the unverified note must stay distinguishable in search results")
        self.assertEqual("UNKNOWN", hit["results"][0]["versionHint"]["state"])

    # -- search ---------------------------------------------------------------------------------------

    def _seed_two_versions(self) -> None:
        old = solution_library.build_solution(
            solution_id="sol-dsh-cache-old",
            title="清理缓存目录修复启动失败",
            software={"softwareId": "dsh", "softwareVersion": "0.2.0", "platform": "win32",
                      "versionSource": "MEASURED"},
            source={"kind": "MANUAL", "ref": "note-1", "updatedAt": GENERATED_AT},
            steps=["删除 %LOCALAPPDATA% 下的缓存目录"],
            verification_steps=["重启后确认能进入会话"],
            keywords=["缓存", "启动"],
            limits=["只验证过 0.2.0"],
            changes="initial")
        new = solution_library.build_solution(
            solution_id="sol-dsh-cache-new",
            title="清理认证缓存目录后恢复登录",
            software={"softwareId": "dsh", "softwareVersion": "0.2.1", "platform": "win32",
                      "versionSource": "MEASURED"},
            source={"kind": "MANUAL", "ref": "note-2", "updatedAt": GENERATED_AT},
            steps=["删除 auth-cache 目录"],
            verification_steps=["重新登录并确认会话出现"],
            keywords=["缓存", "登录"],
            changes="initial")
        self.store.save_solution({"solutionId": old["solutionId"], "revision": 1,
                                  "title": old["title"], "status": old["status"],
                                  "softwareId": "dsh", "softwareVersion": "0.2.0", "platform": "win32",
                                  "keywords": old["keywords"], "payload": old})
        self.store.save_solution({"solutionId": new["solutionId"], "revision": 1,
                                  "title": new["title"], "status": new["status"],
                                  "softwareId": "dsh", "softwareVersion": "0.2.1", "platform": "win32",
                                  "keywords": new["keywords"], "payload": new})

    def test_search_matches_chinese_and_names_the_version_relation(self) -> None:
        self._seed_two_versions()
        changed = solution_library.store_view(self.store, query="缓存", current_version="0.2.1")
        self.assertEqual(2, changed["summary"]["matched"])
        hints = {item["solutionId"]: item["versionHint"]["state"] for item in changed["results"]}
        self.assertEqual("VERSION_CHANGED", hints["sol-dsh-cache-old"])
        self.assertEqual("SAME_VERSION", hints["sol-dsh-cache-new"])
        old = next(item for item in changed["results"] if item["solutionId"] == "sol-dsh-cache-old")
        self.assertIn("只验证过 0.2.0", old["limits"],
                      "a hit must carry the recipe's own limits, not only its title")
        self.assertIn("版本", old["versionHint"]["message"])

        unknown = solution_library.search_solutions(self.store.list_solutions(), query="启动")
        self.assertEqual("UNKNOWN", unknown["results"][0]["versionHint"]["state"],
                         "no current version supplied means the relation cannot be computed")
        ascii_hit = solution_library.search_solutions(self.store.list_solutions(), query="auth-cache")
        self.assertEqual(["sol-dsh-cache-new"], [item["solutionId"] for item in ascii_hit["results"]])

    def test_a_term_that_ends_a_sentence_is_still_findable(self) -> None:
        """The token class admits `.` inside a word, so a prose sentence's last word carried the period.

        Measured on the first real corpus: 253 folded ledger root causes end in `.`, and querying the very
        word written in the record (`denylist`) returned NO_MATCH. Terms are derived at query time from the
        same text, so the fix belongs in `_terms`, applied to both sides -- not in the stored documents.
        """
        document = solution_library.build_solution(
            solution_id="sol-sentence-final-term",
            title="命名与全局敏感键冲突",
            software={"softwareId": "dsh", "softwareVersion": "0.2.0", "platform": "win32",
                      "versionSource": "MEASURED"},
            source={"kind": "MANUAL", "ref": "taskpacks/current/error-ledger.json#ERR-003",
                    "updatedAt": "2026-10-25T00:00:00Z"},
            steps=["The budget field name collided with the global sensitive-key denylist."],
            verification_steps=["python tests/ci/test_x.py"],
            keywords=["命名", "conflict"],
            changes="首版：守护句末标点的分词",
        )
        self.store.save_solution({
            "solutionId": document["solutionId"], "revision": document["revision"],
            "title": document["title"], "status": document["status"],
            "keywords": document["keywords"], "payload": document,
        })
        hit = solution_library.search_solutions(self.store.list_solutions(), query="denylist")
        self.assertIn("sol-sentence-final-term", [item["solutionId"] for item in hit["results"]],
                      "a word that happens to end a sentence must remain findable")
        self.assertEqual(["denylist"], hit["summary"]["terms"])

    def test_an_issue_fingerprint_hit_ranks_first_and_the_summary_is_self_describing(self) -> None:
        self._seed_two_versions()
        with_fingerprint = self.store.read_solution("sol-dsh-cache-old")["payload"]
        with_fingerprint["revision"] = 1
        # The fingerprint has to be ON the stored document; a fixture that only passes it to search
        # would prove nothing about ranking.
        fingerprint = "a" * 16
        with_fingerprint["issueRefs"] = [fingerprint]
        with_fingerprint["solutionId"] = "sol-dsh-fingerprint"
        with_fingerprint["keywords"] = ["缓存", "指纹"]
        self.store.save_solution({"solutionId": "sol-dsh-fingerprint", "revision": 1,
                                  "title": "带指纹的方案", "status": "VERIFIED",
                                  "softwareId": "dsh", "softwareVersion": "0.2.0",
                                  "platform": "win32", "keywords": ["缓存", "指纹"],
                                  "payload": with_fingerprint})
        outcome = solution_library.search_solutions(
            self.store.list_solutions(), query="缓存", fingerprints=[fingerprint], limit=2)
        self.assertEqual("sol-dsh-fingerprint", outcome["results"][0]["solutionId"])
        self.assertTrue(outcome["results"][0]["issueMatch"])
        summary = outcome["summary"]
        self.assertEqual(3, summary["solutionsRead"])
        self.assertEqual(3, summary["matched"])
        self.assertTrue(summary["truncated"], "a cap of 2 over 3 matches must be disclosed")
        self.assertFalse(summary["aaosRequired"])
        self.assertIsNone(summary["modelUsed"])
        self.assertFalse(summary["inferencePerformed"])
        self.assertFalse(summary["contentIncluded"])

    def test_the_cli_refuses_to_create_an_absent_store(self) -> None:
        empty = self.runtime / "absent-runtime"
        empty.mkdir()
        completed = subprocess.run(
            [sys.executable, str(ROOT / "packages" / "client-neutral-core" / "scripts"
                                 / "solution_library.py"), "list", "--runtime-root", str(empty)],
            cwd=str(ROOT), capture_output=True, text=True, encoding="utf-8", errors="replace",
            timeout=60)
        self.assertEqual(3, completed.returncode)
        self.assertIn("SOLUTION_LIBRARY_NO_STORE", completed.stdout)
        self.assertFalse((empty / "canonical.sqlite").exists(),
                         "the refused CLI created the store it said was missing")


if __name__ == "__main__":
    unittest.main()
