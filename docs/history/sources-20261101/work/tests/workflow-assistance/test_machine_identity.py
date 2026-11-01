from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "services/authority/machine_identity.py"
spec = importlib.util.spec_from_file_location("machine_identity", SCRIPT)
assert spec and spec.loader
module = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = module
spec.loader.exec_module(module)

sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
import project_temp  # noqa: E402


class MachineIdentityTests(unittest.TestCase):
    def setUp(self) -> None:
        # Every throwaway project is registered with project_temp, so a killed run leaves an orphan
        # the bound gate can see and the reclaim tool can release. These used to be bare `mkdtemp`
        # dirs dropped straight into `.project-local/runs`, where 50+ of them piled up unowned.
        self._tmp_projects: list[Path] = []

    def tearDown(self) -> None:
        for p in self._tmp_projects:
            project_temp.force_release(p)

    def make_project(self) -> Path:
        project = project_temp.fixture_dir(prefix="machine-identity-")
        self._tmp_projects.append(project)
        (project / ".git").mkdir()
        (project / ".hermes" / "task-runtime").mkdir(parents=True)
        profile = project / module.PROFILE_RELATIVE
        profile.parent.mkdir(parents=True)
        profile.write_text('{"profile_mode":"USER_OVERLAY_ONLY"}\n', encoding="utf-8")
        return project

    def test_status_is_uninitialized_without_writing(self) -> None:
        project = self.make_project()
        result = module.status(project)
        self.assertEqual(result["machine_state"], "IDENTITY_NOT_INITIALIZED")
        self.assertIsNone(result["machine_id"])
        self.assertFalse((project / module.LOCAL_STATE_RELATIVE).exists())

    def test_init_plan_does_not_write_and_write_generates_opaque_v4_id(self) -> None:
        project = self.make_project()
        plan = module.init_local_identity(project, write=False)
        self.assertEqual(plan["status"], "PLAN_ONLY")
        self.assertFalse((project / module.LOCAL_STATE_RELATIVE).exists())
        written = module.init_local_identity(project, write=True)
        self.assertEqual(written["status"], "PLAN_ONLY")
        self.assertRegex(written["machine_id"], module.UUID_RE)
        self.assertNotIn("profile_mode", json.dumps(written))
        self.assertFalse((project / module.LOCAL_STATE_RELATIVE).exists())

    def test_unregistered_identity_is_new_machine_until_explicit_record(self) -> None:
        project = self.make_project()
        identity = self.write_identity(project)
        before = module.status(project)
        self.assertEqual(before["machine_state"], "NEW_MACHINE")
        plan = module.record_machine(project, label="office-pc", write=False)
        self.assertEqual(plan["status"], "PLAN_ONLY")
        self.assertFalse((project / module.REGISTRY_RELATIVE).exists())
        self.assertEqual(identity["machine_id"], before["machine_id"])

    def test_profile_change_requires_review_not_apply(self) -> None:
        project = self.make_project()
        identity = self.write_identity(project)
        registry = project / module.REGISTRY_RELATIVE
        registry.parent.mkdir(parents=True, exist_ok=True)
        registry.write_text(json.dumps({"schema_version": module.REGISTRY_SCHEMA_VERSION, "machines": [{"machine_id": identity["machine_id"], "identity_scope": "project_local_installation", "label": "office-pc", "first_seen": "2026-08-13T00:00:00Z"}]}), encoding="utf-8")
        profile = project / module.PROFILE_RELATIVE
        profile.write_text('{"profile_mode":"USER_OVERLAY_ONLY","revision":2}\n', encoding="utf-8")
        result = module.status(project)
        self.assertEqual(result["machine_state"], "CONFIGURATION_REVIEW_REQUIRED")
        self.assertEqual(result["next_action"], "review_profile_and_run_plan_verify")

    def test_explicit_e_drive_path_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            module._project_root("E:/protected")

    def test_explicit_f_drive_path_is_rejected(self) -> None:
        # Standing user rule: the F: data drive is protected alongside E:.
        with self.assertRaises(ValueError):
            module._project_root("F:/protected")

    def test_registry_path_cannot_escape_project_root(self) -> None:
        project = self.make_project()
        with self.assertRaises(ValueError):
            module.status(project, Path("..") / "outside.json")

    def test_non_project_directory_is_rejected_before_status_or_write(self) -> None:
        outside = project_temp.fixture_dir(prefix="machine-identity-outside-")
        self._tmp_projects.append(outside)
        with self.assertRaises(ValueError):
            module.status(outside)
        with self.assertRaises(ValueError):
            module.init_local_identity(outside, write=True)
        self.assertFalse((outside / module.LOCAL_STATE_RELATIVE).exists())

    def test_registry_record_is_plan_only_even_when_write_is_requested(self) -> None:
        project = self.make_project()
        self.write_identity(project)
        result = module.record_machine(project, label="office-pc", write=True)
        self.assertEqual(result["status"], "PLAN_ONLY")
        self.assertFalse((project / module.REGISTRY_RELATIVE).exists())

    @unittest.skipUnless(hasattr(Path, "symlink_to"), "symlink API unavailable")
    def test_identity_write_rejects_existing_symlink_target(self) -> None:
        project = self.make_project()
        path = project / module.LOCAL_STATE_RELATIVE
        path.parent.mkdir(parents=True, exist_ok=True)
        target = project / "target.json"
        try:
            path.symlink_to(target)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        with self.assertRaises(ValueError):
            module.init_local_identity(project, write=True)
        self.assertFalse(target.exists())

    def write_identity(self, project: Path) -> dict[str, str]:
        identity = {
            "schema_version": module.SCHEMA_VERSION,
            "identity_scope": "project_local_installation",
            "machine_id": "12345678-1234-4234-8234-123456789abc",
            "created_at": "2026-08-13T00:00:00Z",
            "profile_digest": module._profile_digest(project),
        }
        path = project / module.LOCAL_STATE_RELATIVE
        path.write_text(json.dumps(identity), encoding="utf-8")
        return identity

    def test_device_identity_file_cannot_escape_project_root(self) -> None:
        project = self.make_project()
        with self.assertRaises(ValueError):
            module.init_local_identity(
                project,
                write=False,
                scope="device",
                identity_file=Path("..") / "device.json",
            )

    def test_private_state_path_is_rejected(self) -> None:
        project = self.make_project()
        with self.assertRaises(ValueError):
            module.status(project, registry_path=Path("auth.json"))

    @unittest.skipUnless(hasattr(Path, "symlink_to"), "symlink API unavailable")
    def test_symlinked_runtime_ancestor_is_rejected(self) -> None:
        project = self.make_project()
        link = project / "link"
        try:
            link.symlink_to(project, target_is_directory=True)
        except OSError as exc:
            self.skipTest(f"symlink creation unavailable: {exc}")
        # A creation call that SUCCEEDS is not proof of a link. Measured on this host (2026-07-12):
        # symlink creation returned without raising on both NTFS volumes and left a plain directory
        # behind -- lstat reports FILE_ATTRIBUTE_DIRECTORY (0x10) and no FILE_ATTRIBUTE_REPARSE_POINT
        # (0x400). Skipping states that the premise could not be built; it does not excuse the check,
        # which runs everywhere a real link can be made.
        if not link.is_symlink() and not (getattr(link.lstat(), "st_file_attributes", 0) & 0x0400):
            self.skipTest("this filesystem downgrades symlink creation to a plain directory, "
                          "so a linked ancestor cannot be constructed here")
        with self.assertRaises(ValueError):
            module.status(project, registry_path=Path("link") / "registry.json")

    def test_cli_default_root_is_monorepo_root_when_run_from_module(self) -> None:
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "status"],
            cwd=ROOT,
            text=True, encoding="utf-8", errors="replace",
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertNotEqual(payload["profile_digest"], "PROFILE_NOT_FOUND")


if __name__ == "__main__":
    unittest.main()
