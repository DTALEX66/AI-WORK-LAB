"""Gate: a fixture root must be readable by the evidence reader that shares the project boundary.

This is the member of the random-name flake class that actually caused a red on a green tree. Measured
2026-10-08, on commit `3700cb53` with every other gate green:

    FAIL: test_every_refusal_is_typed_and_carries_no_content (test_evidence_range_reader.RefusalTests)
    AssertionError: 'SENSITIVE_NAME' != 'NOT_A_FILE'

`test_evidence_range_reader` creates its fixture with `project_temp.fixture_dir(prefix="range-reader-")`
and then asserts that reading the *fixture root* is refused as `NOT_A_FILE`. `tempfile.mkdtemp` appends
eight random characters drawn from `[a-z0-9_]`; `evidence_range_reader.name_is_sensitive` splits each
path component on `[^a-z0-9]+` and refuses a component holding a whole sensitive word; and
`SENSITIVE_WORDS` contains two- and three-letter tokens. So a suffix shaped like `a1_db_2c` makes the
fixture root itself a credential-looking name, the reader answers `SENSITIVE_NAME` before it ever asks
whether the handle is a file, and the assertion goes red for a reason that has nothing to do with the
code under test. Because the reader judges *every* ancestor, anything created under such a root is
refused with it — the exposure is not limited to one directory-handle test.

Two fixes were available. Loosening the matcher would weaken the owner's no-read law, and teaching one
test to dodge its own fixture name would leave the other call sites exposed to the same coin toss —
measured 2026-10-08: 53 `fixture_dir` calls pass a literal prefix (44 distinct prefixes), and the census
below checks every one of them. The rule stays; the helper that mints the name now asks the rule before
handing the root out, and this module pins that it cannot hand out a root the reader refuses.

The 1-in-20,000 rate and the `db`-only collision vocabulary are measured on this host the same day by
`.project-local/runs/qoder-20261008-d/probe_refusal_name_flake.py` and recorded as ERR-215.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import ast
import random
import re
import subprocess
import sys
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import evidence_range_reader as err  # noqa: E402
import project_temp  # noqa: E402

NAME_SPLIT = re.compile(r"[^a-z0-9]+")
COLLIDING = "project-temp-a1_db_2c"


def accepted(tag: str) -> str:
    """A fixture name the reader accepts, unique per assertion so no test can see another's root."""
    return f"project-temp-keep-{tag}"

# Every literal prefix in the repository is enumerated by the census below; a floor makes a broken scan
# (wrong glob, git failure swallowed) report "no offenders" instead of a false pass.
CENSUS_FLOOR = 40


class TheCollisionIsRealTests(unittest.TestCase):
    """Before pinning the fix, pin that the fault it defends against is reachable and how it is reached."""

    def test_a_random_suffix_can_become_a_whole_sensitive_token(self) -> None:
        self.assertIn("db", NAME_SPLIT.split(COLLIDING.lower()), "the planted collision is not carried by `db`")
        self.assertTrue(err.name_is_sensitive(Path(COLLIDING)), "the collision shape is not refused by the reader")

    def test_the_token_must_be_delimited_on_both_sides(self) -> None:
        # This is why the character set matters: `db` forged inside a longer run is not a token, so only
        # the `_` that `mkdtemp` can emit creates the collision. A matcher that over-refused substrings
        # would collide on almost every root, and this gate would be defending the wrong thing.
        self.assertFalse(err.name_is_sensitive(Path("project-temp-a1db2c3d")))
        self.assertFalse(err.name_is_sensitive(Path(accepted("clean"))))

    def test_collisions_are_reachable_from_the_actual_generator_character_set(self) -> None:
        # A fixed seed asserts reachability of the class, not a rate, so this test cannot flake either way.
        rng = random.Random(20261008)
        alphabet = "abcdefghijklmnopqrstuvwxyz0123456789_"
        for _ in range(200_000):
            suffix = "".join(rng.choice(alphabet) for _ in range(8))
            if any(word in err.SENSITIVE_WORDS for word in NAME_SPLIT.split(f"root-{suffix}")):
                return
        self.fail("8 random characters cannot forge a sensitive token, so the retry this gate protects is dead code")


class FixtureDirRefusesItsOwnNameTests(unittest.TestCase):
    def setUp(self) -> None:
        self.root = project_temp.temp_root()
        self._real_tempfile = project_temp.tempfile
        self.addCleanup(setattr, project_temp, "tempfile", self._real_tempfile)
        self.created_by_fake: list[Path] = []

    def tearDown(self) -> None:
        for path in self.created_by_fake:
            if path.exists():
                project_temp.force_release(path)

    def _patch(self, names: list[str]) -> _FakeMkdtemp:
        fake = _FakeMkdtemp(names, self.created_by_fake)
        project_temp.tempfile = fake  # type: ignore[assignment]
        return fake

    def test_a_refused_first_name_is_discarded_and_a_readable_one_is_returned(self) -> None:
        fake = self._patch([COLLIDING, accepted("retry")])
        path = project_temp.fixture_dir(prefix="project-temp-")
        self.assertEqual(Path(path).name, accepted("retry"), "fixture_dir handed out a name the reader refuses")
        self.assertEqual(fake.calls, [COLLIDING, accepted("retry")], "the retry did not ask the generator a second time")

    def test_the_refused_root_is_released_rather_than_left_behind(self) -> None:
        fake = self._patch([COLLIDING, accepted("release")])
        project_temp.fixture_dir(prefix="project-temp-")
        self.assertFalse(fake.created[0].exists(), "a discarded fixture root became residue")

    def test_only_the_accepted_root_is_registered_for_release(self) -> None:
        fake = self._patch([COLLIDING, accepted("tracked")])
        path = project_temp.fixture_dir(prefix="project-temp-")
        tracked = list(project_temp.pending_fixtures())
        self.assertEqual(tracked.count(path), 1, "the root handed out is not registered for release exactly once")
        self.assertNotIn(fake.created[0], tracked, "the discarded root is registered for release")

    def test_an_unreadable_prefix_fails_loudly_and_releases_every_refused_root(self) -> None:
        names = [f"project-temp-discard-{index}" for index in range(project_temp._NAME_ATTEMPTS)]  # noqa: SLF001
        fake = self._patch(names)
        # Exhaustion is a property of the prefix, so the control pins the rule to refuse every leaf instead
        # of passing a credential-shaped prefix: a literal `auth-store-` call site here would be exactly the
        # thing the census below forbids, and a gate must not plant its own false positive. The vocabulary
        # that makes such a prefix unreadable is asserted directly, one line down.
        with mock.patch.object(project_temp, "name_is_sensitive", return_value=True):
            with self.assertRaises(RuntimeError) as caught:
                project_temp.fixture_dir(prefix="project-temp-")
        message = str(caught.exception)
        self.assertIn("project-temp-", message, "the failure does not name the prefix the caller must fix")
        self.assertEqual(len(fake.calls), project_temp._NAME_ATTEMPTS)  # noqa: SLF001
        for created in fake.created:
            self.assertFalse(created.exists(), f"a refused root survived the failure: {created}")
        self.assertTrue(
            err.name_is_sensitive(Path("auth-store-")),
            "the rule no longer refuses an auth-named root, so the prefix census guards nothing",
        )

    def test_the_name_rule_is_asked_about_the_generated_leaf_only(self) -> None:
        # The helper may only judge a name it minted itself. If it were handed the full path, one host's
        # directory spelling (a user profile named `db`, a temp variable pointing at a backup called
        # `auth`) would fail every fixture creation here instead of only refusing evidence reads.
        seen: list[Path] = []

        def record(candidate: Path) -> bool:
            seen.append(candidate)
            return err.name_is_sensitive(candidate)

        with mock.patch.object(project_temp, "name_is_sensitive", record):
            path = project_temp.fixture_dir(prefix="project-temp-")
        self.addCleanup(project_temp.force_release, Path(path))
        self.assertEqual(
            seen, [Path(Path(path).name)],
            "the guard judged something other than the single leaf name it minted",
        )


class TheSurfacesThemselvesAreReadableTests(unittest.TestCase):
    """The retry checks the leaf only, so the directories it hands out must be readable on their own names.

    This is a statement about this repository's spelling, and it is here because it would fail loudly if
    the project were ever cloned under a directory whose name the reader refuses — a host condition no
    amount of leaf-name retrying could fix.
    """

    def test_the_temp_root_and_every_declared_evidence_root_pass_the_name_rule(self) -> None:
        subjects = [project_temp.temp_root(), project_temp.REPO_ROOT]
        subjects += [project_temp.REPO_ROOT / rel for rel in err.declared_evidence_roots(project_temp.REPO_ROOT)]
        for subject in subjects:
            self.assertFalse(
                err.name_is_sensitive(subject.resolve()),
                f"the evidence reader refuses every handle under {subject}; its name is a sensitive kind",
            )


class NoCallerAsksForAnUnreadablePrefixTests(unittest.TestCase):
    def test_every_fixture_dir_call_in_the_repository_names_a_readable_prefix(self) -> None:
        """Both helpers count: `fixture_root()` delegates to `fixture_dir()`, so it inherits the rule.

        Measured 2026-10-10 -- a production self-test converted to `fixture_root(prefix='token-monitor-
        selftest-')` passed this gate and then died at runtime with "5 consecutive fixture names ... were
        refused", because the scan's vocabulary was only `fixture_dir`. A guard over call sites must list
        every name the callers actually use.
        """
        offenders: list[str] = []
        inspected = 0
        for path in _tracked_python_files():
            tree = _parse(path)
            if tree is None:
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or _call_name(node.func) not in ("fixture_dir",
                                                                                   "fixture_root"):
                    continue
                prefix = _literal_prefix(node)
                if prefix is None:
                    continue
                inspected += 1
                if err.name_is_sensitive(Path(prefix)):
                    offenders.append(f"{path.relative_to(ROOT)}:{node.lineno} prefix={prefix!r}")
        self.assertGreaterEqual(
            inspected, CENSUS_FLOOR,
            f"the census saw {inspected} literal prefixes; it is not reaching the call sites",
        )
        self.assertEqual(offenders, [], "these call sites ask for a root the evidence reader will refuse")


class _FakeMkdtemp:
    """`tempfile.mkdtemp` that returns prepared names and creates each directory for real."""

    def __init__(self, names: list[str], sink: list[Path]) -> None:
        self._names = list(names)
        self._sink = sink
        self.calls: list[str] = []

    @property
    def created(self) -> list[Path]:
        return list(self._sink)

    def mkdtemp(self, prefix: str = "", dir: str | None = None, **kwargs) -> str:  # noqa: A002
        name = self._names.pop(0)
        path = Path(dir) / name
        path.mkdir()
        self._sink.append(path)
        self.calls.append(name)
        return str(path)


def _tracked_python_files() -> list[Path]:
    result = subprocess.run(
        ["git", "-C", str(ROOT), "ls-files", "-z", "*.py"],
        capture_output=True, text=True, encoding="utf-8", errors="replace", check=True,
    )
    return [ROOT / item for item in result.stdout.split("\0") if item]


def _parse(path: Path) -> ast.AST | None:
    try:
        return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, ValueError):
        return None


def _call_name(func: ast.AST | None) -> str:
    if isinstance(func, ast.Attribute):
        return func.attr
    if isinstance(func, ast.Name):
        return func.id
    return ""


def _literal_prefix(node: ast.Call) -> str | None:
    for keyword in node.keywords:
        if keyword.arg == "prefix":
            value = keyword.value
            return value.value if isinstance(value, ast.Constant) and isinstance(value.value, str) else None
    if node.args and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str):
        return node.args[0].value
    return None


if __name__ == "__main__":
    unittest.main()
