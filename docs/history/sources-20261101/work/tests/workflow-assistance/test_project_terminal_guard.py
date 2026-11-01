from __future__ import annotations

import importlib.util
import json
import subprocess
import tempfile
import unittest
import unittest.mock as mock
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "packages" / "client-neutral-core" / "bin" / "hermes-project-terminal-guard.py"


def load_module():
    spec = importlib.util.spec_from_file_location("project_terminal_guard", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ProjectTerminalGuardTests(unittest.TestCase):
    def make_repo(self) -> Path:
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        repo = Path(raw.name) / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        return repo

    def payload(self, repo: Path, command: str, *, workdir: str | None = None) -> dict[str, object]:
        return {
            "hook_event_name": "pre_tool_call",
            "tool_name": "terminal",
            "tool_input": {"command": command, **({"workdir": workdir} if workdir is not None else {"workdir": str(repo)})},
            "session_id": "test-session",
        }

    def test_blocks_sibling_prefix_path_when_project_name_contains_space(self) -> None:
        """P0-8 regression: root \"repo with space\", external sibling \"repo\"
        is its character prefix -> must BLOCK (was silently allowed)."""
        module = load_module()
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        repo = Path(raw.name) / "repo with space"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        sibling = Path(raw.name) / "repo"  # character-prefix sibling
        sibling.mkdir()
        outside = sibling / "outside file.txt"  # space triggers regex truncation
        outside.write_text("x", encoding="utf-8")

        for child in (
            f"python -c \"open('{outside.as_posix()}')\"",  # quoted full external path (space)
            f"python -c \"open('{sibling.as_posix()}')\"",  # bare sibling (no space)
        ):
            with self.subTest(child=child):
                reason = module.validate(
                    self.payload(
                        repo,
                        'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
                    )
                )
                self.assertIn("project", reason)

    def test_blocks_ancestor_prefix_path_when_ancestor_contains_space(self) -> None:
        """P0-8 regression: ancestor \"parent with space\" truncated fragment is
        the root's character prefix -> must BLOCK."""
        module = load_module()
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        parent = Path(raw.name) / "parent with space"
        parent.mkdir()
        repo = parent / "repo"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        outside = parent / "outside file.txt"
        outside.write_text("x", encoding="utf-8")

        child = f"python -c \"open('{outside.as_posix()}')\""
        reason = module.validate(
            self.payload(
                repo,
                'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
            )
        )
        self.assertIn("project", reason)

    def test_permits_quoted_inner_path_with_spaces(self) -> None:
        """P0-8 guard: a quoted INNER path (root contains a space) still passes."""
        module = load_module()
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        repo = Path(raw.name) / "repo with space"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        inner = repo / "inner file.txt"
        inner.write_text("x", encoding="utf-8")

        child = f"python -c \"open('{inner.as_posix()}')\""
        reason = module.validate(
            self.payload(
                repo,
                'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
            )
        )
        self.assertIsNone(reason)

    def test_permits_single_project_wrapper_run(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(self.payload(repo, 'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python -m pytest'))

        self.assertIsNone(reason)

    def test_blocks_raw_terminal_command(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(self.payload(repo, "python -m pytest"))

        self.assertIn("hermes-project-data.py", reason)

    def test_blocks_wrapper_run_with_external_absolute_output_path(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(
            self.payload(
                repo,
                'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- '
                'python -c "open(\\"C:/outside-task-artifact.txt\\", \\"w\\")"',
            )
        )

        self.assertIn("project", reason)

    def test_blocks_wrapper_run_with_embedded_posix_absolute_path(self) -> None:
        module = load_module()
        repo = self.make_repo()

        for child in (
            'python -c "write(--output=/tmp/outside-task-artifact.txt)"',
            'python -c "write(--output:/tmp/outside-task-artifact.txt)"',
            'python -c "write(/tmp/outside-task-artifact.txt)"',
        ):
            with self.subTest(child=child):
                reason = module.validate(
                    self.payload(
                        repo,
                        'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
                    )
                )
                self.assertIn("project", reason)

    def test_blocks_wrapper_run_with_unc_absolute_path(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(
            self.payload(
                repo,
                r'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- '
                r'python --output=\\server\share\outside-task-artifact.txt',
            )
        )

        self.assertIn("project", reason)

    def test_blocks_wrapper_run_with_embedded_unc_absolute_path(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(
            self.payload(
                repo,
                r'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- '
                r'python -c "write(path:\\server\share\outside.txt)"',
            )
        )

        self.assertIn("project", reason)

    def test_blocks_windows_backslash_paths_and_parent_traversal_before_shlex(self) -> None:
        module = load_module()
        repo = self.make_repo()

        for child in (
            r'python -c "open(\"C:\\tmp\\outside-task-artifact.txt\", \"w\")"',
            r'python --dest=C:\\tmp\\outside-task-artifact.txt',
            r'python -c "open(\"..\\outside-task-artifact.txt\", \"w\")"',
            r'python -c "open(\"../outside-task-artifact.txt\", \"w\")"',
        ):
            with self.subTest(child=child):
                reason = module.validate(
                    self.payload(
                        repo,
                        'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
                    )
                )
                self.assertIn("project", reason)

    def test_permits_ellipsis_and_git_range_text(self) -> None:
        module = load_module()
        repo = self.make_repo()

        for child in (
            r"echo ...",
            r"git log HEAD..origin/main",
            r"python -c 'print(\"...\")'",
            r"echo a..b",
        ):
            with self.subTest(child=child):
                reason = module.validate(
                    self.payload(
                        repo,
                        'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
                    )
                )
                self.assertIsNone(reason)

    def test_blocks_real_parent_traversal_forms(self) -> None:
        module = load_module()
        repo = self.make_repo()

        for child in (
            r"python -c 'open(\"../outside.txt\")'",
            r"python -c 'open(\"scripts/../../secret.txt\")'",
            r"python -c 'open(\"..\\outside.txt\")'",
            r"ls ..",
            r"cat ../../etc/passwd",
        ):
            with self.subTest(child=child):
                reason = module.validate(
                    self.payload(
                        repo,
                        'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
                    )
                )
                self.assertIsNotNone(reason)

    def test_permits_inner_project_absolute_path_with_spaces(self) -> None:
        module = load_module()
        raw = tempfile.TemporaryDirectory()
        self.addCleanup(raw.cleanup)
        repo = Path(raw.name) / "repo with space"
        repo.mkdir()
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        inside = repo / "inner file.txt"
        inside.write_text("x", encoding="utf-8")

        reason = module.validate(
            self.payload(
                repo,
                'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- '
                f'python -c "open(\'{inside.as_posix()}\')"',
            )
        )

        self.assertIsNone(reason)

    def test_blocks_external_absolute_path_with_spaces(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(
            self.payload(
                repo,
                'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- '
                r'python -c "open(\'C:/outside dir/file.txt\')"',
            )
        )

        self.assertIn("project", reason)

    def test_blocks_known_windows_external_spill_roots(self) -> None:
        module = load_module()
        repo = self.make_repo()

        for child in (
            r'python -c "open(\"D:\\tmp\\outside.txt\", \"w\")"',
            r'python --dest=D:\\d\\outside.txt',
            r'python --dest=D:\\dev\\outside.txt',
            r'python --dest=D:\\a\\outside.txt',
        ):
            with self.subTest(child=child):
                reason = module.validate(
                    self.payload(
                        repo,
                        'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
                    )
                )
                self.assertIn("project-local cache/temp redirection", reason)

    def test_blocks_shell_expansion_that_runs_before_the_wrapper(self) -> None:
        module = load_module()
        repo = self.make_repo()

        for child in (
            r'python -c "open(\"$HOME/outside-task-artifact.txt\", \"w\")"',
            r'python -c "open(\"${TMPDIR}/outside-task-artifact.txt\", \"w\")"',
            r'$(python -c "print(\"unsafe\")") python -m pytest',
            r'`python -c "print(\"unsafe\")"` python -m pytest',
        ):
            with self.subTest(child=child):
                reason = module.validate(
                    self.payload(
                        repo,
                        'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- ' + child,
                    )
                )
                self.assertIn("shell expansion", reason)

    def test_blocks_wrapper_prefix_variable_that_is_not_hermes_home(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(
            self.payload(
                repo,
                '$HERMES_HOME_EVASION python "$HERMES_HOME/bin/hermes-project-data.py" --project . check',
            )
        )

        self.assertIn("shell expansion", reason)

    def test_blocks_single_ampersand_shell_chaining(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(
            self.payload(
                repo,
                'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python -m pytest & echo unsafe',
            )
        )

        self.assertIn("chaining", reason)

    def test_permits_shell_control_characters_inside_quoted_child_text(self) -> None:
        module = load_module()
        repo = self.make_repo()

        reason = module.validate(
            self.payload(
                repo,
                "python \"$HERMES_HOME/bin/hermes-project-data.py\" --project . run -- "
                "python -c 'print(\"literal; &\")'",
            )
        )

        self.assertIsNone(reason)

    def test_blocks_implicit_or_non_git_workdir(self) -> None:
        module = load_module()
        repo = self.make_repo()

        self.assertIn("explicit", module.validate(self.payload(repo, "echo hi", workdir="")))
        self.assertIn("Git project", module.validate(self.payload(repo, "echo hi", workdir=str(Path(repo.anchor)))))

    def test_blocks_wrong_wrapper_project_and_shell_chaining(self) -> None:
        module = load_module()
        repo = self.make_repo()

        wrong_project = module.validate(self.payload(repo, 'python "$HERMES_HOME/bin/hermes-project-data.py" --project ../other run -- python -m pytest'))
        chained = module.validate(self.payload(repo, 'python "$HERMES_HOME/bin/hermes-project-data.py" --project . run -- python -m pytest && echo unsafe'))

        self.assertIn("--project .", wrong_project)
        self.assertIn("chaining", chained)

    def test_blocks_text_that_only_mentions_the_wrapper(self) -> None:
        module = load_module()
        repo = self.make_repo()

        fake_echo = module.validate(self.payload(repo, "echo hermes-project-data.py --project . check"))
        fake_python = module.validate(self.payload(repo, "python fake.py hermes-project-data.py --project . check"))

        self.assertIn("executable", fake_echo)
        self.assertIn("executable", fake_python)

    def test_blocks_absolute_fake_wrapper_with_the_same_filename(self) -> None:
        module = load_module()
        repo = self.make_repo()
        fake = repo / "hermes-project-data.py"
        fake.write_text("# fake\n", encoding="utf-8")

        reason = module.validate(self.payload(repo, f'python "{fake}" --project . check'))

        self.assertIn("canonical", reason)

    def test_ignores_other_tool_calls(self) -> None:
        module = load_module()

        self.assertIsNone(module.validate({"tool_name": "read_file", "tool_input": {"path": "C:/outside.txt"}}))

    def test_main_outputs_hermes_block_wire_shape(self) -> None:
        module = load_module()
        repo = self.make_repo()
        payload = self.payload(repo, "git status")

        reason = module.validate(payload)
        self.assertTrue(reason)
        self.assertEqual(module.BLOCK_PREFIX, "PROJECT DATA BOUNDARY BLOCKED:")
        self.assertEqual(json.loads(json.dumps({"action": "block", "message": f"{module.BLOCK_PREFIX} {reason}"}))["action"], "block")


class BothHostBranchesAreExercisedOnThisMachine(unittest.TestCase):
    """The guard's `os.name != "nt"` branches only ever ran on the ubuntu job.

    Twenty-five tests covered the NT side here and the POSIX side was covered only by CI passing there, so
    a regression in the non-NT arm had no local signal at all. Forcing the attribute makes both arms
    testable on one machine. What they encode is path *syntax*, not a host privilege: on a POSIX host a UNC
    share or a drive-qualified path can never be inside this project, while on Windows a drive path may be,
    and must then be compared to the real root rather than refused.
    """

    def setUp(self) -> None:
        self.guard = load_module()
        self.root = Path("D:/All projects/WORK-LAB")

    def test_a_posix_host_blocks_a_unc_share(self) -> None:
        command = 'net use "\\\\SERVER\\share\\x"'
        with mock.patch.object(self.guard.os, "name", "posix"):
            self.assertEqual("\\\\SERVER\\share\\x",
                             self.guard.external_raw_unc(command, self.root))

    def test_a_posix_host_blocks_a_drive_qualified_path(self) -> None:
        command = 'type "C:/Windows/win.ini"'
        with mock.patch.object(self.guard.os, "name", "posix"):
            found = self.guard.external_raw_windows_path(command, self.root)
        self.assertIsNotNone(found, "the non-NT arm did not flag a drive path at all")
        self.assertIn("C:", found)

    def test_a_windows_host_blocks_an_external_drive_but_not_its_own_project(self) -> None:
        with mock.patch.object(self.guard.os, "name", "nt"):
            self.assertIsNotNone(
                self.guard.external_raw_windows_path('type "D:/elsewhere/x.txt"', self.root),
                "a sibling project on the same drive must be flagged")
            self.assertIsNone(
                self.guard.external_raw_windows_path(
                    'type "D:/All projects/WORK-LAB/config/x.yaml"', self.root),
                "a path inside the declared root must not be flagged")

    def test_a_windows_host_blocks_a_unc_share_that_is_not_the_project(self) -> None:
        with mock.patch.object(self.guard.os, "name", "nt"):
            self.assertEqual("\\\\SERVER\\share\\x", self.guard.external_raw_unc(
                'copy "\\\\SERVER\\share\\x" .', self.root))


if __name__ == "__main__":
    unittest.main()
