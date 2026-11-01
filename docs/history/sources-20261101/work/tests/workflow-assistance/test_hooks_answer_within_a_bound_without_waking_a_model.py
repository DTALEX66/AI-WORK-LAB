"""Gate: the two pre-tool hooks answer within a stated bound, and have no way to wake a model.

WUI-18's remaining "low overhead" clause. Both hooks run before *every* terminal/tool call in the managed
client, so two things have to be provable rather than assumed:

* the metadata lookups they make cannot hang. Before this change neither file passed ``timeout=`` to any of
  its five ``subprocess.run`` call sites, so a locked index or a credential prompt would sit in front of every
  tool call, and the guard would eventually look like a slow client rather than a stuck ``git``.
* "fast" is measured, not declared. The tests below time the real guard process and the real root lookup, and
  one of them forces the timeout to fire so the bound is known to be a bound and not decoration.

"Does not wake a model" is checked structurally: neither hook imports an HTTP, socket or model client, so there
is no call path from a pre-tool hook to a provider. A deliberate refusal is also distinguished from an
unanswered question -- a stalled ``git`` must not be reported as "this workdir is not a Git project", because
that sends the owner to look for a repository problem that does not exist (the ERR-222 class).

Discovered dynamically by ``run_quality_gate.py governance``.
"""
from __future__ import annotations

import ast
import importlib.util
import json
import statistics
import subprocess
import sys
import time
import unittest
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[2]
BIN = ROOT / "packages/client-neutral-core/bin"
GUARD = BIN / "hermes-project-terminal-guard.py"
WRAPPER = BIN / "hermes-project-data.py"
HOOKS = (GUARD, WRAPPER)

# Call sites that run the *user's* command. Bounding those would be a feature change, not a guard: the whole
# point of `run -- <cmd>` is to execute whatever the user asked for, for however long it takes.
USER_COMMAND_FUNCTIONS = frozenset({"run_command", "run_kanban_command"})
METADATA_CALL_SITE_FLOOR = 5
MODEL_CHANNELS = ("requests", "httpx", "urllib.request", "socket", "openai", "anthropic", "http.client")


def load(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def subprocess_calls(path: Path) -> list[tuple[str, bool]]:
    """(enclosing function, carries a timeout) for every ``subprocess.run`` in the file."""
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found: list[tuple[str, bool]] = []

    def visit(node: ast.AST, function: str) -> None:
        if isinstance(node, ast.FunctionDef):
            function = node.name
        if isinstance(node, ast.Call) and ast.unparse(node.func) == "subprocess.run":
            found.append((function, any(kw.arg == "timeout" for kw in node.keywords)))
        for child in ast.iter_child_nodes(node):
            visit(child, function)

    visit(tree, "<module>")
    return found


def timed(payload: dict, repeats: int = 12) -> list[float]:
    durations: list[float] = []
    for _ in range(repeats):
        start = time.perf_counter()
        subprocess.run([sys.executable, str(GUARD)], input=json.dumps(payload),
                       capture_output=True, text=True, encoding="utf-8", errors="replace",
                       check=False, timeout=60)
        durations.append((time.perf_counter() - start) * 1000)
    return durations


class HookCallSiteTests(unittest.TestCase):
    def test_every_metadata_lookup_in_both_hooks_is_bounded(self) -> None:
        unbounded = [(path.name, function) for path in HOOKS
                     for function, has_timeout in subprocess_calls(path)
                     if not has_timeout and function not in USER_COMMAND_FUNCTIONS]
        self.assertEqual([], unbounded,
                         f"these guard lookups can hang with no ceiling: {unbounded}")

    def test_the_census_actually_reaches_the_call_sites(self) -> None:
        seen = sum(len(subprocess_calls(path)) for path in HOOKS)
        self.assertGreaterEqual(seen, METADATA_CALL_SITE_FLOOR,
                                f"only {seen} subprocess.run sites were read across both hooks; below "
                                f"{METADATA_CALL_SITE_FLOOR} the first test is comparing an empty list")

    def test_the_two_unbounded_sites_are_named_as_user_command_runs(self) -> None:
        named = [(path.name, function) for path in HOOKS
                 for function, has_timeout in subprocess_calls(path) if not has_timeout]
        self.assertTrue(set(function for _name, function in named) <= set(USER_COMMAND_FUNCTIONS),
                        f"an unbounded call is not a user-command run: {named}")

    def test_neither_hook_has_a_channel_to_a_model(self) -> None:
        for path in HOOKS:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imported = set()
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    imported.update(alias.name for alias in node.names)
                elif isinstance(node, ast.ImportFrom) and node.module:
                    imported.add(node.module)
            channels = sorted(imported & set(MODEL_CHANNELS))
            self.assertEqual([], channels, f"{path.name} imports a network/model channel: {channels}")


class GuardTimeoutTests(unittest.TestCase):
    def setUp(self) -> None:
        self.guard = load(GUARD, "terminal_guard_under_test")

    def test_a_stalled_git_is_refused_within_the_bound_and_said_as_unresolved(self) -> None:
        class Stalled:
            # The hook reads subprocess.TimeoutExpired in its except clause, so a replacement for the module
            # has to carry that name too or the test dies on the harness rather than on the behaviour.
            TimeoutExpired = subprocess.TimeoutExpired

            def run(self, *args, **kwargs):  # mirrors subprocess.run's signature
                raise subprocess.TimeoutExpired(cmd=list(args[0]), timeout=kwargs.get("timeout") or 0)

        original = self.guard.subprocess
        self.guard.subprocess = Stalled()
        try:
            reason = self.guard.validate({"tool_name": "terminal",
                                          "tool_input": {"workdir": str(ROOT), "command": "true"}})
        finally:
            self.guard.subprocess = original
        self.assertIsNotNone(reason, "a guard whose root lookup never answered returned an approval")
        self.assertIn("unresolved", reason or "")
        self.assertNotIn("not a Git project", reason or "",
                         "a stall was reported as a claim about the user's repository")

    def test_the_bound_is_a_bound_and_not_a_number_that_cannot_be_hit(self) -> None:
        """Force the real timeout path with an absurdly small ceiling on a real Git call."""
        with self.assertRaises(self.guard.RootCheckUnresolved):
            self.guard.project_root(str(ROOT), timeout=1e-06)

    def test_the_declared_bound_is_far_above_the_measured_root_lookup(self) -> None:
        durations: list[float] = []
        for _ in range(12):
            start = time.perf_counter()
            self.guard.project_root(str(ROOT))
            durations.append((time.perf_counter() - start) * 1000)
        p95 = statistics.quantiles(durations, n=20, method="inclusive")[18]
        print(f"\nGUARD_ROOT_LOOKUP p50_ms={statistics.median(durations):.1f} p95_ms={p95:.1f} "
              f"max_ms={max(durations):.1f} bound_s={self.guard.ROOT_CHECK_TIMEOUT_SECONDS}")
        self.assertLess(p95, self.guard.ROOT_CHECK_TIMEOUT_SECONDS * 1000,
                        "the declared ceiling sits below the tool's own normal latency, so it would fire "
                        "on ordinary runs")


class GuardProcessTimingTests(unittest.TestCase):
    def test_the_guard_process_returns_on_both_paths_inside_its_own_bound(self) -> None:
        blocked = timed({"tool_name": "terminal",
                         "tool_input": {"workdir": str(ROOT), "command": "echo hi > out.txt"}})
        allowed = timed({"tool_name": "terminal",
                         "tool_input": {"workdir": str(ROOT),
                                        "command": "python $HERMES_HOME/bin/hermes-project-data.py "
                                                   "--project . check"}})
        bound = load(GUARD, "guard_for_bound").ROOT_CHECK_TIMEOUT_SECONDS * 1000
        for label, samples in (("block", blocked), ("allow", allowed)):
            p95 = statistics.quantiles(samples, n=20, method="inclusive")[18]
            print(f"\nGUARD_PROCESS_{label} p50_ms={statistics.median(samples):.1f} "
                  f"p95_ms={p95:.1f} max_ms={max(samples):.1f}")
            self.assertLess(p95, bound,
                            f"the {label} path is slower than the bound the guard declares for its own "
                            "Git lookup, so the hook cannot promise a fast return")


class WrapperBoundaryTests(unittest.TestCase):
    def test_an_unanswered_ignore_check_is_not_read_as_ignored(self) -> None:
        wrapper = load(WRAPPER, "project_data_under_test")

        class Stalled:
            TimeoutExpired = subprocess.TimeoutExpired

            def run(self, *args, **kwargs):
                raise subprocess.TimeoutExpired(cmd=list(args[0]), timeout=kwargs.get("timeout") or 0)

        original = wrapper.subprocess
        wrapper.subprocess = Stalled()
        try:
            with self.assertRaises(wrapper.ProjectDataBoundaryError) as caught:
                wrapper.is_git_ignored(ROOT, Path(".project-local/runs/probe"))
        finally:
            wrapper.subprocess = original
        message = str(caught.exception)
        self.assertIn("unproven", message)
        print(f"\nWRAPPER_IGNORE_REFUSAL {message}")

    def test_the_wrapper_still_ignores_what_git_ignores(self) -> None:
        """The positive control: with the real Git, a genuinely ignored path answers True.

        Without this the refusal test would pass equally well against a wrapper that always raised."""
        wrapper = load(WRAPPER, "project_data_positive")
        self.assertTrue(wrapper.is_git_ignored(ROOT, Path(".project-local/runs/probe")),
                        "git ignores .project-local, so the real call must say so")
        self.assertFalse(wrapper.is_git_ignored(ROOT, Path("AGENTS.md")),
                         "a tracked file is not ignored; a call that always returned True would fake this")


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
