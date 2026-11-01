from __future__ import annotations

import subprocess
import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path
from unittest.mock import patch

from run_taskpack_agent import (
    DEFAULT_SKILLS,
    AgentResult,
    CodexReviewBackend,
    GitRepository,
    HermesAgentBackend,
    RunnerError,
    TaskPackRunner,
    discover_ci_identity,
    effective_task_risk,
    resolve_ci_identity,
    _parse_args,
)
from task_ledger import TaskLedger


@dataclass
class FakeRepo:
    head_value: str = "base"
    staged_tree_value: str = "tree-base"
    status_value: str = ""
    released: bool = False
    release_args: tuple[str, ...] = ()

    def head(self) -> str:
        return self.head_value

    def head_tree(self) -> str:
        return "tree-base"

    def staged_tree(self) -> str:
        return self.staged_tree_value

    def snapshot(self) -> tuple[str, str]:
        return self.staged_tree_value, self.status_value

    def verify_released(self, *args: str, require_ci: bool = True) -> None:
        self.release_args = args
        if not args or args[0] != "base":
            raise AssertionError(f"unexpected baseline: {args}")
        self.released = True


class FakeAgent:
    def __init__(self, repo: FakeRepo, decisions: list[str]) -> None:
        self.repo = repo
        self.decisions = iter(decisions)
        self.writer_calls: list[tuple[str | None, str]] = []
        self.review_calls: list[str] = []

    def run_writer(self, prompt: str, *, resume: str | None = None) -> AgentResult:
        self.writer_calls.append((resume, prompt))
        if resume is None:
            self.repo.staged_tree_value = "tree-v1"
            self.repo.status_value = "M  shared/migration.py"
        elif "NO-GO" in prompt:
            self.repo.staged_tree_value = "tree-v2"
        elif "GO" in prompt:
            self.repo.head_value = "released"
            self.repo.status_value = ""
        return AgentResult(stdout="writer complete", stderr="", session_id="session-A")

    def run_reviewer(self, prompt: str) -> str:
        self.review_calls.append(prompt)
        return next(self.decisions)


class TaskPackAgentRunnerTests(unittest.TestCase):
    def test_declared_low_cannot_bypass_forced_high_task_risk(self) -> None:
        self.assertEqual(effective_task_risk("low", "update config/managed-config-schema.yaml"), "high")
        self.assertEqual(effective_task_risk("low", "update CONFIG/managed-config-schema.yaml"), "high")
        self.assertEqual(effective_task_risk("low", "update ./.github/workflows/governance.yml"), "high")
        self.assertEqual(effective_task_risk("low", "rotate credentials and deploy"), "high")
        self.assertEqual(effective_task_risk("low", "commit and push the already verified documentation"), "low")
        self.assertEqual(effective_task_risk("low", "open a pull request after local verification"), "low")
        self.assertEqual(effective_task_risk("low", "prepare a release"), "high")
        self.assertEqual(effective_task_risk("low", "add a pure adapter"), "low")

    def test_empty_required_workflows_is_explicit_ci_blocker_not_constructor_success(self) -> None:
        repo = GitRepository(Path.cwd(), required_workflows=())
        with self.assertRaisesRegex(RunnerError, "BLOCKED"):
            repo.observe_ci("commit")

    def test_ci_identity_uses_work_lab_profile_and_aggregate_job(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(resolve_ci_identity(root), (("work-lab-gate",), "aggregate"))

    def test_ci_identity_discovers_workflow_without_profile(self) -> None:
        root = Path(__file__).resolve().parents[2]
        self.assertEqual(discover_ci_identity(root), (("work-lab-gate",), "aggregate"))

    def test_hermes_backend_resumes_without_agent_timeout(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            return subprocess.CompletedProcess(
                command,
                0,
                stdout="writer complete\n",
                stderr="\nsession_id: continued-session\n",
            )

        with tempfile.TemporaryDirectory() as raw:
            with patch("run_taskpack_agent.shutil.which", return_value="hermes"), patch(
                "run_taskpack_agent.subprocess.run", side_effect=fake_run
            ):
                result = HermesAgentBackend(Path(raw), hermes="hermes").run_writer(
                    "continue work", resume="initial-session"
                )

        self.assertEqual(result.session_id, "continued-session")
        self.assertEqual(calls[0][0][calls[0][0].index("--resume") + 1], "initial-session")
        self.assertNotIn("timeout", calls[0][1])
        self.assertIn("HERMES_PROJECT_RUNTIME_ROOT", calls[0][1]["env"])
        self.assertEqual(calls[0][1]["env"]["TEMP"], calls[0][1]["env"]["TMP"])

    def test_high_risk_runner_resumes_one_writer_lineage_until_review_go(self) -> None:
        repo = FakeRepo()
        agent = FakeAgent(repo, ["NO-GO\nshared/migration.py:10 missing proof", "GO"])

        TaskPackRunner(repo=repo, agent=agent, max_review_rounds=3, publish=True).run(
            "repair the migration", risk="high"
        )

        self.assertEqual([resume for resume, _ in agent.writer_calls], [None, "session-A", "session-A"])
        self.assertEqual(len(agent.review_calls), 2)
        self.assertIn("tree-v1", agent.review_calls[0])
        self.assertIn("tree-v2", agent.review_calls[1])
        self.assertTrue(repo.released)

    def test_reviewer_cannot_change_frozen_tree(self) -> None:
        repo = FakeRepo()
        agent = FakeAgent(repo, ["GO"])

        def editing_review(_prompt: str) -> str:
            repo.status_value = "M  shared/migration.py\n?? reviewer-note.txt"
            return "GO"

        agent.run_reviewer = editing_review  # type: ignore[method-assign]
        with self.assertRaisesRegex(RunnerError, "reviewer changed"):
            TaskPackRunner(repo=repo, agent=agent).run("repair", risk="high")

    def test_low_risk_runner_uses_configured_release_ref(self) -> None:
        repo = FakeRepo()
        agent = FakeAgent(repo, [])

        TaskPackRunner(repo=repo, agent=agent, release_ref="origin/feat/sleep", publish=True).run(
            "add a pure adapter", risk="low"
        )

        prompt = agent.writer_calls[0][1]
        self.assertIn("origin/feat/sleep", prompt)
        self.assertNotIn("HEAD equal to origin/main", prompt)
        self.assertTrue(repo.released)

    def test_low_risk_publish_skips_exact_sha_ci_wait(self) -> None:
        # WLG-040: low-risk (TARGETED/STAGE) publish must verify remote sync
        # only, not block on exact-SHA CI; CI is reserved for RC/RELEASE.
        repo = FakeRepo()
        agent = FakeAgent(repo, [])
        runner = TaskPackRunner(repo=repo, agent=agent, publish=True)
        with patch.object(repo, "verify_released", wraps=repo.verify_released) as verify:
            runner.run("add a pure adapter", risk="low")
            verify.assert_called_once()
            kwargs = verify.call_args.kwargs
            self.assertEqual(kwargs.get("require_ci"), False)

    def test_high_risk_release_requires_exact_sha_ci(self) -> None:
        # WLG-040: high-risk / RC-RELEASE delivery keeps exact-SHA CI.
        repo = FakeRepo()
        agent = FakeAgent(repo, ["GO"])
        runner = TaskPackRunner(repo=repo, agent=agent, publish=True)
        with patch.object(repo, "verify_released", wraps=repo.verify_released) as verify:
            runner.run("repair a governed boundary", risk="high")
            verify.assert_called_once()
            self.assertTrue(verify.call_args.kwargs.get("require_ci", True))

    def test_runner_uses_task_ledger_lease_checkpoint_and_release(self) -> None:
        repo = FakeRepo()
        agent = FakeAgent(repo, [])
        with tempfile.TemporaryDirectory() as raw:
            ledger = TaskLedger(Path(raw) / "ledger")
            runner = TaskPackRunner(repo=repo, agent=agent, ledger=ledger)
            runner.run("ledger-backed bounded task", risk="low")
            self.assertIsNotNone(runner.last_task_id)
            task = ledger.get(runner.last_task_id or "")
            self.assertEqual(task["status"], "COMPLETED")
            self.assertIsNone(task["lease"])
            self.assertEqual(task["checkpoint"]["phase"], "runner_complete")

    def test_high_risk_runner_uses_configured_release_ref(self) -> None:
        repo = FakeRepo()
        agent = FakeAgent(repo, ["GO"])

        TaskPackRunner(repo=repo, agent=agent, release_ref="origin/feat/sleep", publish=True).run(
            "repair a governed boundary", risk="high"
        )

        release_prompt = agent.writer_calls[-1][1]
        self.assertIn("origin/feat/sleep", release_prompt)
        self.assertNotIn("HEAD equal to origin/main", release_prompt)

    def test_high_risk_release_binds_delivery_to_reviewed_frozen_tree(self) -> None:
        repo = FakeRepo()
        agent = FakeAgent(repo, ["GO"])

        TaskPackRunner(repo=repo, agent=agent, publish=True).run(
            "release only the reviewed tree", risk="high"
        )

        self.assertEqual(repo.release_args, ("base", "tree-v1"))

    def test_release_fetches_remote_selected_by_remote_ref(self) -> None:
        calls: list[tuple[str, ...]] = []
        repo = GitRepository(
            Path("."), remote_ref="upstream/release", required_workflows=("workflow-governance",)
        )

        def fake_git(*args: str) -> str:
            calls.append(args)
            values = {
                ("status", "--porcelain=v1", "--untracked-files=all"): "",
                ("write-tree",): "index-tree",
                ("rev-parse", "HEAD"): "release",
                ("rev-parse", "HEAD^{tree}"): "reviewed-tree",
                ("rev-parse", "upstream/release"): "release",
            }
            return values.get(args, "")

        with patch.object(repo, "_git", side_effect=fake_git), patch.object(repo, "_wait_for_ci"):
            repo.verify_released("base", "reviewed-tree")

        self.assertIn(("fetch", "--prune", "upstream"), calls)

    def test_exact_sha_ci_rejects_completed_unrelated_workflow(self) -> None:
        repo = GitRepository(
            Path("."), required_workflows=("workflow-governance",), ci_timeout_seconds=1, ci_poll_seconds=0
        )
        result = subprocess.CompletedProcess(
            ["gh"],
            0,
            stdout='[{"status":"completed","conclusion":"success","name":"unrelated"}]',
            stderr="",
        )
        with patch("run_taskpack_agent.shutil.which", return_value="gh"), patch(
            "run_taskpack_agent.subprocess.run", return_value=result
        ), patch.object(repo, "_github_repository", return_value="owner/repository"), patch(
            "run_taskpack_agent.time.monotonic", side_effect=[0, 0, 2]
        ), self.assertRaisesRegex(RunnerError, "required workflow"):
            repo._wait_for_ci("release")

    def test_exact_sha_ci_accepts_latest_success_for_required_workflow(self) -> None:
        repo = GitRepository(
            Path("."),
            required_workflows=("workflow-governance",),
            ci_timeout_seconds=1,
            ci_poll_seconds=0,
        )
        result = subprocess.CompletedProcess(
            ["gh"],
            0,
            stdout=(
                '[{"status":"completed","conclusion":"success",'
                '"name":"workflow-governance","url":"https://example.invalid/run/42",'
                '"databaseId":42,"headSha":"release","attempt":2,'
                '"createdAt":"2026-07-26T12:00:00Z"}]'
            ),
            stderr="",
        )
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return result

        with patch("run_taskpack_agent.shutil.which", return_value="gh"), patch(
            "run_taskpack_agent.subprocess.run", side_effect=fake_run
        ), patch.object(repo, "_github_repository", return_value="owner/repository"), patch(
            "run_taskpack_agent.time.monotonic", side_effect=[0, 0]
        ):
            repo._wait_for_ci("release")

        self.assertEqual(calls[0][0:5], ["gh", "run", "list", "--repo", "owner/repository"])

    def test_exact_sha_ci_reads_stable_aggregate_job_for_selected_run(self) -> None:
        repo = GitRepository(
            Path("."),
            required_workflows=("work-lab-gate",),
            stable_aggregate_job="aggregate",
            ci_timeout_seconds=1,
            ci_poll_seconds=0,
        )
        run_list = subprocess.CompletedProcess(
            ["gh"],
            0,
            stdout=(
                '[{"status":"completed","conclusion":"success",'
                '"name":"work-lab-gate","url":"https://example.invalid/run/42",'
                '"databaseId":42,"headSha":"release","attempt":1}]'
            ),
            stderr="",
        )
        aggregate = subprocess.CompletedProcess(
            ["gh"],
            0,
            stdout='{"headSha":"release","jobs":[{"name":"aggregate","status":"completed","conclusion":"success"}]}',
            stderr="",
        )
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            return run_list if command[1:3] == ["run", "list"] else aggregate

        with patch("run_taskpack_agent.shutil.which", return_value="gh"), patch(
            "run_taskpack_agent.subprocess.run", side_effect=fake_run
        ), patch.object(repo, "_github_repository", return_value="owner/repository"), patch(
            "run_taskpack_agent.time.monotonic", side_effect=[0, 0]
        ):
            repo._wait_for_ci("release")

        self.assertEqual(calls[1][0:4], ["gh", "run", "view", "42"])
        self.assertIn("headSha,jobs", calls[1])

    def test_release_repository_marks_empty_required_workflow_contract_blocked_at_observation(self) -> None:
        repo = GitRepository(Path("."), required_workflows=())
        with self.assertRaisesRegex(RunnerError, "BLOCKED"):
            repo.observe_ci("release")

    def test_default_runner_stages_without_releasing(self) -> None:
        repo = FakeRepo()
        agent = FakeAgent(repo, [])

        TaskPackRunner(repo=repo, agent=agent).run("stage a bounded task", risk="low")

        self.assertFalse(repo.released)
        self.assertIn("Do not commit, push", agent.writer_calls[0][1])

    def test_default_skills_are_global_not_cognitive_os_specific(self) -> None:
        skills = DEFAULT_SKILLS.split(",")
        self.assertIn("project-data-boundary", skills)
        self.assertNotIn("cognitive-loop-os", skills)

    def test_cli_requires_an_explicit_remote_ref(self) -> None:
        with patch(
            "sys.argv",
            ["run_taskpack_agent.py", "--risk", "low", "--mission", "bounded task"],
        ):
            with self.assertRaises(SystemExit):
                _parse_args()

    def test_codex_reviewer_preflights_flags_and_preserves_user_layer(self) -> None:
        calls: list[tuple[list[str], dict[str, object]]] = []

        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append((command, kwargs))
            if command[-1:] == ["--version"]:
                return subprocess.CompletedProcess(command, 0, stdout="codex-cli test", stderr="")
            if command[-2:] == ["exec", "--help"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="--sandbox --ephemeral --output-last-message --output-schema",
                    stderr="",
                )
            output_file = Path(command[command.index("--output-last-message") + 1])
            output_file.write_text('{"decision": "GO", "findings": []}', encoding="utf-8")
            return subprocess.CompletedProcess(command, 0, stdout="process transcript", stderr="")

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / "codex.exe"
            codex.write_text("placeholder", encoding="utf-8")
            with patch("run_taskpack_agent.subprocess.run", side_effect=fake_run):
                review = CodexReviewBackend(root, codex=str(codex)).run_reviewer("review tree")

        self.assertEqual(review, "GO\nCodex structured exact-tree review found no findings")
        self.assertEqual(calls[0][0][-1:], ["--version"])
        self.assertEqual(calls[1][0][-2:], ["exec", "--help"])
        command, kwargs = calls[2]
        self.assertEqual(command[:5], [str(codex), "exec", "--sandbox", "read-only", "--ephemeral"])
        self.assertIn("--output-last-message", command)
        self.assertIn("--output-schema", command)
        self.assertNotIn("--ignore-user-config", command)
        self.assertNotIn("--ignore-rules", command)
        self.assertTrue(command[command.index("--output-schema") + 1].endswith(".json"))
        self.assertEqual(command[-1:], ["review tree"])
        self.assertNotIn("--dangerously-bypass-approvals-and-sandbox", command)
        self.assertNotIn("--dangerously-bypass-hook-trust", command)
        self.assertEqual(kwargs["cwd"], root.resolve())

    def test_codex_reviewer_fails_closed_for_any_non_no_findings_output(self) -> None:
        def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
            if command[-1:] == ["--version"]:
                return subprocess.CompletedProcess(command, 0, stdout="codex-cli test", stderr="")
            if command[-2:] == ["exec", "--help"]:
                return subprocess.CompletedProcess(
                    command,
                    0,
                    stdout="--sandbox --ephemeral --output-last-message --output-schema",
                    stderr="",
                )
            output_file = Path(command[command.index("--output-last-message") + 1])
            output_file.write_text(
                '{"decision": "NO-GO", "findings": [{"severity": "high", "file": "x.py", "line": 1, "detail": "test gap"}]}',
                encoding="utf-8",
            )
            return subprocess.CompletedProcess(command, 0, stdout="process transcript", stderr="")

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / "codex.exe"
            codex.write_text("placeholder", encoding="utf-8")
            with patch("run_taskpack_agent.subprocess.run", side_effect=fake_run):
                review = CodexReviewBackend(root, codex=str(codex)).run_reviewer("ignored")

        self.assertIn("NO-GO\nCodex native pre-review:\n", review)
        self.assertIn('"severity": "high"', review)

    def test_codex_reviewer_fails_closed_before_execution_when_required_flag_is_missing(self) -> None:
        calls: list[list[str]] = []

        def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
            calls.append(command)
            if command[-1:] == ["--version"]:
                return subprocess.CompletedProcess(command, 0, stdout="codex-cli test", stderr="")
            return subprocess.CompletedProcess(command, 0, stdout="--sandbox --ephemeral", stderr="")

        with tempfile.TemporaryDirectory() as raw:
            root = Path(raw)
            codex = root / "codex.exe"
            codex.write_text("placeholder", encoding="utf-8")
            with patch("run_taskpack_agent.subprocess.run", side_effect=fake_run):
                with self.assertRaisesRegex(RunnerError, "missing required flags"):
                    CodexReviewBackend(root, codex=str(codex)).run_reviewer("ignored")

        self.assertEqual(len(calls), 2)
        self.assertEqual(calls[0][-1:], ["--version"])
        self.assertEqual(calls[1][-2:], ["exec", "--help"])

    def test_codex_reviewer_fails_closed_before_help_when_version_probe_fails_or_is_empty(self) -> None:
        for returncode, stdout, stderr in ((1, "", "version failure"), (0, "", "")):
            with self.subTest(returncode=returncode, stdout=stdout, stderr=stderr):
                calls: list[list[str]] = []

                def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
                    calls.append(command)
                    return subprocess.CompletedProcess(command, returncode, stdout=stdout, stderr=stderr)

                with tempfile.TemporaryDirectory() as raw:
                    root = Path(raw)
                    codex = root / "codex.exe"
                    codex.write_text("placeholder", encoding="utf-8")
                    with patch("run_taskpack_agent.subprocess.run", side_effect=fake_run):
                        with self.assertRaisesRegex(RunnerError, "version discovery"):
                            CodexReviewBackend(root, codex=str(codex)).run_reviewer("ignored")

                self.assertEqual(len(calls), 1)
                self.assertEqual(calls[0][-1:], ["--version"])

    def test_cli_rejects_codex_reviewer_for_low_risk_taskpack(self) -> None:
        with patch(
            "sys.argv",
            [
                "run_taskpack_agent.py",
                "--risk", "low",
                "--reviewer", "codex",
                "--remote-ref", "origin/main",
                "--mission", "bounded task",
            ],
        ):
            with self.assertRaises(SystemExit):
                _parse_args()

    def test_cli_accepts_repeatable_required_workflow_contract(self) -> None:
        with patch(
            "sys.argv",
            [
                "run_taskpack_agent.py",
                "--risk", "high",
                "--remote-ref", "origin/main",
                "--required-workflow", "workflow-governance",
                "--required-workflow", "release-verification",
                "--mission", "bounded task",
            ],
        ):
            args = _parse_args()

        self.assertEqual(args.required_workflow, ["workflow-governance", "release-verification"])

    def test_high_risk_runner_can_use_independent_reviewer_backend(self) -> None:
        repo = FakeRepo()
        writer = FakeAgent(repo, [])

        class IndependentReviewer:
            def __init__(self) -> None:
                self.calls: list[str] = []

            def run_reviewer(self, prompt: str) -> str:
                self.calls.append(prompt)
                return "GO"

        reviewer = IndependentReviewer()
        TaskPackRunner(repo=repo, agent=writer, reviewer=reviewer).run("review independently", risk="high")
        self.assertEqual(len(reviewer.calls), 1)
        self.assertEqual(writer.review_calls, [])


if __name__ == "__main__":
    unittest.main()
