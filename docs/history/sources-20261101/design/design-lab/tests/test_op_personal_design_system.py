# SPDX-License-Identifier: MIT
from __future__ import annotations

import json
import importlib.util
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parent
# DL-DIR-MIG-R1: open-design host tree moved to repo-root integrations/,
# capability catalogs to packages/capabilities/, research stays under design-lab/.
OPEN_DESIGN = REPO_ROOT / "integrations" / "hosts" / "open-design"
SKILLS = OPEN_DESIGN / "expert-suite" / "skills"
DESIGN_SYSTEMS = ROOT / "design-systems"
PLUGINS = REPO_ROOT / "packages" / "capabilities" / "plugins"
BUNDLES = REPO_ROOT / "packages" / "capabilities" / "bundles"
SCENARIOS = REPO_ROOT / "packages" / "capabilities" / "scenarios"
RESEARCH = ROOT / "research"
INSTALLER = OPEN_DESIGN / "installer" / "install_op_expert_suite.py"


class PersonalDesignSystemTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        spec = importlib.util.spec_from_file_location("install_op_expert_suite", INSTALLER)
        assert spec and spec.loader
        cls.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.installer)

    def project_temporary_directory(self):
        runtime_tmp = REPO_ROOT / ".project-local" / "task-runtime" / "tmp"
        runtime_tmp.mkdir(parents=True, exist_ok=True)
        return tempfile.TemporaryDirectory(dir=runtime_tmp)

    def test_personal_design_systems_are_packaged(self):
        """All design-systems/*/DESIGN.md must have a matching manifest.json."""
        actual = {path.parent.name for path in DESIGN_SYSTEMS.glob("*/DESIGN.md")}
        self.assertGreaterEqual(len(actual), 3)
        for name in actual:
            manifest = DESIGN_SYSTEMS / name / "manifest.json"
            self.assertTrue(manifest.is_file(), f"missing manifest for {name}")


    def test_fifteen_task_oriented_personal_skills_are_packaged(self):
        skill_files = list(SKILLS.glob("*/SKILL.md"))
        self.assertEqual(len(skill_files), 15)
        for skill_file in skill_files:
            body = skill_file.read_text(encoding="utf-8")
            self.assertTrue(body.startswith("---\n"), skill_file)
            self.assertLess(skill_file.stat().st_size, 10 * 1024, skill_file)

    def test_master_material_is_governed_by_three_translation_skills(self):
        expected = {
            "master-method-translator",
            "style-lineage-composer",
            "design-source-curator",
        }
        self.assertTrue(expected.issubset({path.parent.name for path in SKILLS.glob("*/SKILL.md")}))

        master_registry = json.loads(
            (RESEARCH / "master-studies" / "MASTER_REGISTRY.json").read_text(encoding="utf-8")
        )
        method_cards = json.loads(
            (RESEARCH / "master-studies" / "ANCHOR_METHOD_CARDS.json").read_text(encoding="utf-8")
        )
        lineages = json.loads(
            (RESEARCH / "style-lineages" / "STYLE_LINEAGES.json").read_text(encoding="utf-8")
        )
        self.assertEqual(master_registry["count"], 497)
        self.assertEqual(method_cards["count"], 77)
        self.assertEqual(len(lineages["lineages"]), 47)

    def test_minigame_skill_is_general_design_capability_not_anomaly_fixture(self):
        body = (SKILLS / "minigame-hud-designer" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        required = {
            "核心循环",
            "玩法规则",
            "关卡与内容",
            "UX/UI",
            "经济与商业化",
            "平台适配",
            "质量与交付",
        }
        self.assertTrue(required.issubset(set(required & set(body.split("；"))) | {term for term in required if term in body}))
        self.assertIn("MINIGAME 仅作为案例", body)
        self.assertIn("CCTV 仅作为可选视觉方向", body)
        self.assertNotIn("中央游戏/CCTV 画面必须主导", body)

    def test_minigame_plugin_defaults_follow_the_brief(self):
        manifest = json.loads(
            (PLUGINS / "minigame-ui-director" / "open-design.json").read_text(
                encoding="utf-8"
            )
        )
        inputs = {item["name"]: item.get("default") for item in manifest["od"]["inputs"]}
        self.assertEqual(manifest["title"], "Minigame Design Director")
        self.assertEqual(inputs["genre"], "auto")
        self.assertEqual(inputs["visualDirection"], "brief-driven")
        self.assertEqual(inputs["monetization"], "brief-driven")
        self.assertNotIn("anomaly-monitor-dark", json.dumps(manifest))

        body = (PLUGINS / "minigame-ui-director" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        for genre in ("益智", "动作", "模拟", "放置", "合成", "塔防", "节奏", "派对"):
            self.assertIn(genre, body)
        self.assertIn("保留兼容 ID", body)

    def test_anomaly_monitor_is_optional_specialization_not_minigame_default(self):
        manifest = json.loads(
            (PLUGINS / "anomaly-monitor-hud" / "open-design.json").read_text(
                encoding="utf-8"
            )
        )
        inputs = {item["name"]: item.get("default") for item in manifest["od"]["inputs"]}
        self.assertEqual(inputs["scene"], "custom")
        body = (PLUGINS / "anomaly-monitor-hud" / "SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("可选视觉专精", body)
        self.assertIn("不要把所有小游戏默认设计成 CCTV", body)

    def test_research_library_is_not_copied_into_personal_skill_bodies(self):
        skill_bytes = sum(path.stat().st_size for path in SKILLS.glob("*/SKILL.md"))
        research_bytes = sum(path.stat().st_size for path in RESEARCH.rglob("*") if path.is_file())
        self.assertLess(skill_bytes, 30 * 1024)
        self.assertGreater(research_bytes, skill_bytes * 10)

    def test_twelve_personal_expert_resources_are_managed_by_installer(self):
        resources = self.installer.EXPERT_RESOURCE_SOURCES
        self.assertEqual(len(resources), 12)
        self.assertEqual(sum(kind == "plugins" for kind, _ in resources), 7)
        self.assertEqual(sum(kind == "bundles" for kind, _ in resources), 3)
        self.assertEqual(sum(kind == "scenarios" for kind, _ in resources), 2)
        for kind, name in resources:
            base_dir = {
                "plugins": PLUGINS,
                "bundles": BUNDLES,
                "scenarios": SCENARIOS,
                "design-systems": DESIGN_SYSTEMS,
            }.get(kind, ROOT)
            manifest = base_dir / name / "open-design.json"
            self.assertTrue(manifest.is_file(), manifest)
            data = json.loads(manifest.read_text(encoding="utf-8"))
            self.assertEqual(data["name"], name)

    def test_bundle_scenario_refs_are_installer_managed(self):
        managed_scenarios = {
            name
            for kind, name in self.installer.EXPERT_RESOURCE_SOURCES
            if kind == "scenarios"
        }
        referenced_scenarios = set()
        for manifest_path in BUNDLES.glob("*/open-design.json"):
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            referenced_scenarios.update(
                skill["ref"]
                for skill in manifest.get("od", {}).get("context", {}).get("skills", [])
                if isinstance(skill, dict) and isinstance(skill.get("ref"), str)
            )
        self.assertTrue(referenced_scenarios)
        self.assertTrue(referenced_scenarios <= managed_scenarios)
        for name in referenced_scenarios:
            self.assertTrue((SCENARIOS / name / "open-design.json").is_file(), name)

    def test_workspace_selection_uses_personal_not_active_team(self):
        directory = {
            "activeWorkspaceId": "team-1",
            "items": [
                {
                    "workspaceId": "team-1",
                    "workspaceMemberId": "member-team",
                    "workspaceType": "team",
                    "role": "member",
                    "memberStatus": "active",
                    "lifecycleState": "active",
                },
                {
                    "workspaceId": "personal-1",
                    "workspaceMemberId": "member-personal",
                    "workspaceType": "personal",
                    "role": "owner",
                    "memberStatus": "active",
                    "lifecycleState": "active",
                },
            ],
        }
        with mock.patch.object(self.installer, "api_request", return_value=(200, directory)):
            headers = self.installer.select_workspace("http://op")
        self.assertEqual(headers["x-od-workspace-id"], "personal-1")
        self.assertEqual(headers["x-od-workspace-type"], "personal")

    def test_workspace_authority_is_forwarded_without_elevation(self):
        directory = {
            "activeWorkspaceId": "personal-1",
            "items": [
                {
                    "workspaceId": "personal-1",
                    "workspaceMemberId": "member-1",
                    "workspaceType": "personal",
                    "role": "member",
                    "memberStatus": "active",
                    "lifecycleState": "active",
                }
            ],
        }
        with mock.patch.object(self.installer, "api_request", return_value=(200, directory)):
            headers = self.installer.select_workspace("http://op")
        self.assertEqual(headers["x-od-workspace-role"], "member")
        self.assertNotIn("x-od-workspace-can-share-projects", headers)
        self.assertNotIn("x-od-workspace-can-write-synced-files", headers)

        del directory["items"][0]["role"]
        with mock.patch.object(self.installer, "api_request", return_value=(200, directory)):
            with self.assertRaises(self.installer.ApiError):
                self.installer.select_workspace("http://op")

    def test_non_active_personal_workspace_lifecycle_fails_closed(self):
        directory = {
            "activeWorkspaceId": "personal-1",
            "items": [
                {
                    "workspaceId": "personal-1",
                    "workspaceMemberId": "member-1",
                    "workspaceType": "personal",
                    "role": "owner",
                    "memberStatus": "active",
                    "lifecycleState": "suspended",
                }
            ],
        }
        with mock.patch.object(self.installer, "api_request", return_value=(200, directory)):
            with self.assertRaisesRegex(self.installer.ApiError, "active Personal Workspace"):
                self.installer.select_workspace("http://op")

    def test_multiple_personal_workspaces_fail_closed(self):
        items = [
            {
                "workspaceId": f"personal-{index}",
                "workspaceMemberId": f"member-{index}",
                "workspaceType": "personal",
                "role": "owner",
                "memberStatus": "active",
                "lifecycleState": "active",
            }
            for index in (1, 2)
        ]
        with mock.patch.object(
            self.installer,
            "api_request",
            return_value=(200, {"activeWorkspaceId": "team", "items": items}),
        ):
            with self.assertRaises(self.installer.ApiError):
                self.installer.select_workspace("http://op")

    def test_active_namespace_is_discovered_from_current_web_log(self):
        with self.project_temporary_directory() as tmp:
            appdata = Path(tmp)
            old_log = (
                appdata
                / "Open Design"
                / "namespaces"
                / "old-channel"
                / "logs"
                / "web"
                / "latest.log"
            )
            current_log = (
                appdata
                / "Open Design"
                / "namespaces"
                / "current-channel"
                / "logs"
                / "web"
                / "latest.log"
            )
            old_log.parent.mkdir(parents=True)
            current_log.parent.mkdir(parents=True)
            old_log.write_text("listening http://127.0.0.1:1111", encoding="utf-8")
            current_log.write_text("listening http://127.0.0.1:2222", encoding="utf-8")
            old_log_mtime = old_log.stat().st_mtime - 10
            import os

            os.utime(old_log, (old_log_mtime, old_log_mtime))

            with mock.patch.dict("os.environ", {"APPDATA": str(appdata)}):
                self.assertEqual(
                    self.installer.default_app_url(), "http://127.0.0.1:2222"
                )
                self.assertEqual(
                    self.installer.namespace_data_root("http://127.0.0.1:2222"),
                    appdata
                    / "Open Design"
                    / "namespaces"
                    / "current-channel"
                    / "data",
                )

    def test_namespace_data_root_is_bound_to_explicit_app_url(self):
        with self.project_temporary_directory() as tmp:
            appdata = Path(tmp)
            expected_log = (
                appdata / "Open Design" / "namespaces" / "expected" / "logs" / "web" / "latest.log"
            )
            newer_log = (
                appdata / "Open Design" / "namespaces" / "newer" / "logs" / "web" / "latest.log"
            )
            expected_log.parent.mkdir(parents=True)
            newer_log.parent.mkdir(parents=True)
            expected_log.write_text("listening http://127.0.0.1:2222", encoding="utf-8")
            newer_log.write_text("listening http://127.0.0.1:3333", encoding="utf-8")
            with mock.patch.dict("os.environ", {"APPDATA": str(appdata)}):
                self.assertEqual(
                    self.installer.namespace_data_root("http://127.0.0.1:2222"),
                    appdata / "Open Design" / "namespaces" / "expected" / "data",
                )

    def test_sidecar_health_must_confirm_bound_app_url(self):
        with mock.patch.object(
            self.installer, "api_request", return_value=(200, {"ok": True, "version": "0.19.0"})
        ):
            self.installer.verify_sidecar_health("http://127.0.0.1:2222")
        with mock.patch.object(
            self.installer, "api_request", return_value=(200, {"ok": False})
        ):
            with self.assertRaisesRegex(self.installer.ApiError, "health check failed"):
                self.installer.verify_sidecar_health("http://127.0.0.1:2222")

    def test_unmanaged_same_title_design_system_is_rejected(self):
        existing = {
            "Personal Design Intelligence": {
                "id": "user:personal-design-intelligence",
                "title": "Personal Design Intelligence",
                "source": "user",
                "isEditable": True,
                "sourceNotes": "Created and edited by the user.",
            }
        }
        with mock.patch.object(
            self.installer, "list_user_design_systems", return_value=existing
        ):
            with mock.patch.object(
                self.installer,
                "read_design_system",
                return_value={"body": "# User-owned different content"},
            ):
                with self.assertRaisesRegex(
                    self.installer.ApiError, "unmanaged design system"
                ):
                    self.installer.sync_design_systems(
                        "http://op", {}, "workspace", dry_run=True
                    )

    def test_duplicate_editable_design_system_titles_fail_closed(self):
        response = {
            "designSystems": [
                {
                    "id": "user:first",
                    "title": "Personal Design Intelligence",
                    "source": "user",
                    "isEditable": True,
                },
                {
                    "id": "user:second",
                    "title": "Personal Design Intelligence",
                    "source": "user",
                    "isEditable": True,
                },
            ]
        }
        with mock.patch.object(
            self.installer, "api_request", return_value=(200, response)
        ):
            with self.assertRaisesRegex(
                self.installer.ApiError, "multiple editable user design systems"
            ):
                self.installer.list_user_design_systems("http://op", {})

    def test_legacy_design_system_is_adopted_only_when_body_matches_repo(self):
        spec = self.installer.DESIGN_SYSTEM_SOURCES[0]
        body = (
            self.installer.DESIGN_SYSTEMS_ROOT / spec["slug"] / "DESIGN.md"
        ).read_text(encoding="utf-8")
        existing = {
            spec["title"]: {
                "id": "user:legacy-system",
                "title": spec["title"],
                "source": "user",
                "isEditable": True,
                "sourceNotes": None,
            }
        }
        with mock.patch.object(
            self.installer, "list_user_design_systems", return_value=existing
        ):
            with mock.patch.object(
                self.installer, "read_design_system", return_value={"body": body}
            ):
                created, updated = self.installer.sync_design_systems(
                    "http://op", {}, "workspace", dry_run=True
                )
        self.assertEqual((created, updated), (0, 0))

    def test_skill_rollback_staging_stays_inside_project_runtime(self):
        current = {
            "id": "sample",
            "name": "sample",
            "description": "old description",
            "triggers": ["old"],
            "mode": "personal",
            "category": "test",
            "body": "# Old body",
        }
        observed = []

        def install(_app_url, _headers, _skill_id, source_dir):
            observed.append(Path(source_dir))
            if len(observed) == 1:
                raise self.installer.ApiError("new install failed")
            return {"id": "sample"}

        with mock.patch.object(self.installer, "delete_skill"):
            with mock.patch.object(self.installer, "install_skill", side_effect=install):
                with self.assertRaisesRegex(
                    self.installer.ApiError, "restored previous skill"
                ):
                    self.installer.refresh_skill_safely(
                        "http://op", {}, "sample", Path("new-source"), current
                    )
        self.assertEqual(len(observed), 2)
        self.assertTrue(
            observed[1].is_relative_to(
                ROOT.parent / ".project-local" / "task-runtime" / "tmp"
            ),
            observed[1],
        )

    def test_stable_source_transaction_can_roll_back_after_install_failure(self):
        with self.project_temporary_directory() as tmp:
            data_root = Path(tmp)
            target = data_root / "local-plugin-sources" / "design-lab"
            target.mkdir(parents=True)
            (target / "marker.txt").write_text("old", encoding="utf-8")
            with mock.patch.object(self.installer, "namespace_data_root", return_value=data_root):
                with mock.patch.object(self.installer, "copy_expert_resource_sources") as copy_sources:
                    copy_sources.side_effect = lambda destination: (
                        destination.mkdir(parents=True, exist_ok=True),
                        (destination / "marker.txt").write_text("new", encoding="utf-8"),
                    )
                    transaction = self.installer.begin_stable_resource_source_update("http://op")
            self.assertEqual((target / "marker.txt").read_text(encoding="utf-8"), "new")
            transaction.rollback()
            self.assertEqual((target / "marker.txt").read_text(encoding="utf-8"), "old")

    def test_stable_mirror_contains_atoms_and_resolves_every_asset_reference(self):
        runtime_tmp = REPO_ROOT / ".project-local" / "task-runtime" / "tmp"
        runtime_tmp.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=runtime_tmp) as tmp:
            mirror = Path(tmp)
            self.installer.copy_expert_resource_sources(mirror)
            self.assertEqual(len(list((mirror / "atoms").glob("*/open-design.json"))), 21)
            for kind, name in self.installer.EXPERT_RESOURCE_SOURCES:
                manifest_path = mirror / kind / name / "open-design.json"
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                for relative in manifest.get("od", {}).get("context", {}).get("assets", []):
                    self.assertTrue(
                        (manifest_path.parent / relative).resolve().is_file(), relative
                    )

    def test_expert_resource_failure_reports_partial_catalog_mutation(self):
        transaction = mock.Mock()
        calls = []

        def install(_app_url, _headers, kind, name):
            calls.append((kind, name))
            if len(calls) == 5:
                raise self.installer.ApiError("fifth install failed")

        with mock.patch.object(self.installer, "begin_stable_resource_source_update", return_value=transaction):
            with mock.patch.object(
                self.installer,
                "list_plugin_catalog",
                side_effect=[
                    {"anomaly-monitor-hud": {"id": "anomaly-monitor-hud", "version": "0.1.0"}},
                    {
                        "anomaly-monitor-hud": {"id": "anomaly-monitor-hud", "version": "0.2.0"},
                        "brand-visual-director": {"id": "brand-visual-director", "version": "0.1.0"},
                    },
                ],
                create=True,
            ):
                with mock.patch.object(
                    self.installer, "install_expert_resource", side_effect=install
                ) as install_resource:
                    with self.assertRaisesRegex(
                        self.installer.ApiError,
                        "partial catalog mutation.*brand-visual-director.*anomaly-monitor-hud",
                    ):
                        self.installer.install_expert_resources_transactionally(
                            "http://op", {}
                        )
        transaction.rollback.assert_called_once_with()
        transaction.commit.assert_not_called()
        self.assertEqual(install_resource.call_count, 5)

    def test_plugin_catalog_snapshot_excludes_unmanaged_ids(self):
        managed_id = self.installer.EXPERT_RESOURCE_SOURCES[0][1]
        response = {
            "plugins": [
                {"id": managed_id, "version": "1.0.0", "sourceKind": "local"},
                {"id": "user-concurrent-plugin", "version": "9.0.0"},
            ]
        }
        with mock.patch.object(
            self.installer, "api_request", return_value=(200, response)
        ):
            catalog = self.installer.list_plugin_catalog("http://op", {})
        self.assertEqual(set(catalog), {managed_id})

    def test_generated_personal_counts_and_plugin_index_links_are_portable(self):
        counts = json.loads(
            (ROOT / "config" / "asset-counts.json").read_text(encoding="utf-8")
        )
        self.assertEqual(counts["personal_skills"], 15)
        self.assertEqual(counts["design_systems"], 3)
        index = (PLUGINS / "INDEX.md").read_text(encoding="utf-8")
        self.assertNotIn("(packages/capabilities/plugins/", index)

    def test_gitignore_uses_portable_root_uuid_pattern(self):
        ignore = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        self.assertIn("/[0-9a-f]", ignore)
        self.assertNotIn("/1d864770-e234-43fe-8994-27bf9350690a/", ignore)
        self.assertNotIn("/244d938a-abaf-42bd-880b-6fca4b651799/", ignore)

    def test_skill_refresh_restores_previous_skill_when_install_fails(self):
        current = {
            "id": "sample",
            "name": "sample",
            "description": "old description",
            "triggers": ["old"],
            "mode": "personal",
            "category": "test",
            "body": "# Old body",
        }
        with mock.patch.object(self.installer, "delete_skill") as delete:
            with mock.patch.object(
                self.installer,
                "install_skill",
                side_effect=[self.installer.ApiError("new install failed"), {"id": "sample"}],
            ) as install:
                with self.assertRaisesRegex(self.installer.ApiError, "restored previous skill"):
                    self.installer.refresh_skill_safely(
                        "http://op", {}, "sample", Path("new-source"), current
                    )
        delete.assert_called_once()
        self.assertEqual(install.call_count, 2)

    def test_upgrade_stable_source_avoids_versioned_payload_and_temp_staging(self):
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("data/local-plugin-sources/design-lab", source)
        self.assertNotIn("versions/0.19.0", source)
        self.assertNotIn("_hermes_workspace_plugin_stage", source)
        self.assertIn("EXPERT_RESOURCE_READBACK=PASS", source)
        self.assertIn("USER_CONFIG_PRESERVED=PASS", source)

    def test_installer_retries_only_empty_transient_http_400(self):
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("exc.code == 400 and not raw.strip()", source)
        self.assertIn("attempt < 3", source)
        self.assertIn("status == 400 and not data and attempt < 5", source)

    def test_installer_refreshes_only_changed_personal_skills(self):
        source = INSTALLER.read_text(encoding="utf-8")
        self.assertIn("def read_skill(", source)
        self.assertIn("def skill_matches_source(", source)
        self.assertIn("(content matches)", source)
        self.assertNotIn("(already installed)", source)

    def test_changed_unmanaged_skill_is_rejected(self):
        current = {
            "id": "sample",
            "source": "user",
            "upstream": "https://example.invalid/user-skill",
        }
        source = mock.Mock()
        with mock.patch.object(
            self.installer,
            "parse_skill_source",
            return_value={
                "name": "sample",
                "description": "managed",
                "triggers": [],
                "mode": "personal",
                "category": "test",
                "upstream": "https://github.com/DTALEX66/DESIGN-LAB",
                "body": "managed body",
            },
        ):
            with self.assertRaisesRegex(self.installer.ApiError, "unmanaged skill"):
                self.installer.require_managed_skill(current, source)

    def test_skill_matches_source_ignores_metadata_when_body_is_identical(self):
        current = {
            "id": "sample",
            "name": "renamed-by-user",
            "description": "different description",
            "triggers": ["other"],
            "mode": "personal",
            "category": "other",
            "upstream": "https://example.invalid/user-edit",
            "body": "# 同一正文\r\nline2\n",
        }
        source = mock.Mock()
        with mock.patch.object(
            self.installer,
            "parse_skill_source",
            return_value={
                "name": "sample",
                "description": "managed",
                "triggers": [],
                "mode": "personal",
                "category": "test",
                "upstream": "https://github.com/DTALEX66/DESIGN-LAB",
                "body": "# 同一正文\nline2",
            },
        ):
            self.assertTrue(self.installer.skill_matches_source(current, source))

    def test_skill_matches_source_is_false_when_body_differs(self):
        current = {
            "id": "sample",
            "name": "sample",
            "description": "managed",
            "triggers": [],
            "mode": "personal",
            "category": "test",
            "upstream": "https://github.com/DTALEX66/DESIGN-LAB",
            "body": "# 不同的正文",
        }
        source = mock.Mock()
        with mock.patch.object(
            self.installer,
            "parse_skill_source",
            return_value={
                "name": "sample",
                "description": "managed",
                "triggers": [],
                "mode": "personal",
                "category": "test",
                "upstream": "https://github.com/DTALEX66/DESIGN-LAB",
                "body": "# 仓库正文",
            },
        ):
            self.assertFalse(self.installer.skill_matches_source(current, source))


if __name__ == "__main__":
    unittest.main(verbosity=2)
