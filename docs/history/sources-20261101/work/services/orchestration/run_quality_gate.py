from __future__ import annotations

import argparse
import ast
import hashlib
import importlib.util
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import Any, Callable, NamedTuple

ROOT = Path(__file__).resolve().parents[2]

# The runner hands its children `PYTHONIOENCODING=utf-8` (see _run below) but its OWN stdout was left at the
# Windows console default. Measured 2026-10-10: a mandatory test whose output contains `↔` reached
# `_report_governance_failure`, the `print` raised UnicodeEncodeError ('gbk' codec), and the failure report —
# the one artifact that says WHICH of ~230 modules went red — was destroyed mid-line. A verdict that cannot be
# printed is not a verdict, so the parent speaks UTF-8 and replaces anything a console still cannot render.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass
RETIRED_ORDINARY_TESTS = {
    "test_design_token_compliance.py",
    "test_figma_sync.py",
    "test_fixture_separation.py",
    "test_renderer_contract.py",
}

# Converged module roots exposed on PYTHONPATH for unittest imports (WL-DIR migration).
MODULE_PYTHONPATH = os.pathsep.join(
    [
        str(ROOT / "services" / "authority"),
        str(ROOT / "services" / "orchestration"),
        str(ROOT / "services" / "policy"),
        str(ROOT / "services" / "receipts"),
        str(ROOT / "packages" / "client-neutral-core" / "scripts"),
        str(ROOT / "packages" / "client-neutral-core" / "bin"),
        str(ROOT / "integrations" / "executors" / "codex"),
        str(ROOT / "integrations" / "executors" / "hermes"),
        str(ROOT / "integrations" / "executors" / "dsh"),
        str(ROOT / "tests" / "workflow-assistance"),
        str(ROOT / "tests" / "ci"),
        str(ROOT / "tests" / "contracts"),
    ]
)
REQUIRED_PYTHON_MODULES = {
    "yaml": "PyYAML>=6,<7",
    "jsonschema": "jsonschema>=4,<5",
}


class Gate(NamedTuple):
    name: str
    description: str
    runner: Callable[[], int]


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def dependency_preflight() -> int:
    missing = [
        requirement
        for module, requirement in REQUIRED_PYTHON_MODULES.items()
        if importlib.util.find_spec(module) is None
    ]
    if missing:
        print(
            "QUALITY_GATE_DEPENDENCY_FAIL missing="
            + ",".join(missing)
            + " install=python -m pip install -r requirements.txt"
        )
        return 2
    print("QUALITY_GATE_DEPENDENCY_PASS modules=" + ",".join(REQUIRED_PYTHON_MODULES))
    return 0


def usable_bash() -> str | None:
    candidates: list[str] = []
    found = shutil.which("bash")
    if found:
        candidates.append(found)
    if os.name == "nt":
        candidates.extend(
            [
                "C:/Program Files/Git/bin/bash.exe",
                "C:/Program Files/Git/usr/bin/bash.exe",
                "C:/Program Files (x86)/Git/bin/bash.exe",
            ]
        )

    seen: set[str] = set()
    for candidate in candidates:
        path = Path(candidate)
        key = str(path).lower()
        if key in seen or not path.exists():
            continue
        seen.add(key)
        if os.name == "nt" and "windows/system32/bash.exe" in key.replace("\\", "/"):
            continue
        result = subprocess.run(
            [str(path), "--version"],
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        if result.returncode == 0 and "GNU bash" in result.stdout:
            return str(path)
    return None


def project_runtime_environment(root: Path) -> dict[str, str]:
    # WL-010/020/030: Runtime Boundary V2 — .project-local/ is the single runtime root
    runtime = (root / ".project-local" / "runs").resolve()
    paths = {
        "tmp": runtime / "tmp",
        "cache": runtime / "cache",
        "logs": runtime / "logs",
        "artifacts": root / ".project-local" / "artifacts",
        "pip-cache": runtime / "pip-cache",
        "pycache": runtime / "pycache",
    }
    for path in paths.values():
        path.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    env.update(
        {
            "TMP": str(paths["tmp"]),
            "TEMP": str(paths["tmp"]),
            "TMPDIR": str(paths["tmp"]),
            "XDG_CACHE_HOME": str(paths["cache"]),
            "PIP_CACHE_DIR": str(paths["pip-cache"] / "pip"),
            "UV_CACHE_DIR": str(paths["cache"] / "uv"),
            "NPM_CONFIG_CACHE": str(paths["cache"] / "npm"),
            "npm_config_cache": str(paths["cache"] / "npm"),
            "YARN_CACHE_FOLDER": str(paths["cache"] / "yarn"),
            "PLAYWRIGHT_BROWSERS_PATH": str(paths["cache"] / "playwright-browsers"),
            "CARGO_TARGET_DIR": str(paths["cache"] / "cargo-target"),
            "RUFF_CACHE_DIR": str(paths["cache"] / "ruff"),
            "MYPY_CACHE_DIR": str(paths["cache"] / "mypy"),
            "PRE_COMMIT_HOME": str(paths["cache"] / "pre-commit"),
            "PYTHONPYCACHEPREFIX": str(paths["pycache"]),
            "HERMES_PROJECT_RUNTIME_ROOT": str(runtime),
            "HERMES_PROJECT_ARTIFACTS": str(paths["artifacts"]),
            "HERMES_PROJECT_LOGS": str(paths["logs"]),
            "HERMES_KANBAN_HOME": str(root / ".project-local" / "kanban"),
        }
    )
    return env


def run(argv: list[str], *, cwd: Path = ROOT, env_updates: dict[str, str] | None = None) -> int:
    printable = " ".join(argv)
    print(f"\n=== {printable} ===")
    env = project_runtime_environment(cwd)
    if env_updates:
        env.update(env_updates)
    result = subprocess.run(
        argv,
        cwd=cwd,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=env,
    )
    print(f"=== exit {result.returncode}: {printable} ===")
    return result.returncode


def run_python(args: list[str], *, env_updates: dict[str, str] | None = None) -> int:
    return run([sys.executable, *args], env_updates=env_updates)


def tracked_python_files() -> list[str]:
    """Every tracked Python file.

    This used to enumerate five roots (`packages/client-neutral-core/{bin,scripts}`,
    `services/orchestration`, `scripts/security`, `tests/workflow-assistance`) and call the result the
    repository's compile check. A mechanical edit that put `keyword argument repeated` into
    `apps/observer/scripts/write_artifact_receipt.py` -- which no local suite imports -- shipped as a green
    local gate and a red CI, because that path was simply not in the list. Syntax is a property of every
    tracked file, so the input set is now exactly `git ls-files *.py`.
    """
    raw = subprocess.run(
        ["git", "-c", "core.quotePath=false", "ls-files", "-z", "*.py"],
        cwd=ROOT,
        capture_output=True,
        check=True,
    ).stdout
    return sorted(name.decode("utf-8", "replace") for name in raw.split(b"\0") if name)


MANDATORY_TEST_GLOBS = ("test_*.py", "nf*.py")


def governance_test_files() -> list[str]:
    """P0-05: unified mandatory discovery — ordinary + negative-control tests.

    Both the ordinary behavior tests (`test_*.py`) and the negative-control
    tests (`nf*.py`) are mandatory and discovered dynamically from disk. There
    is no hard-coded list and no hard-coded count, so adding a new negative
    control can never silently drop out of the gate (the "compile PASS !=
    behavior PASS" gap this closes).
    """
    selected: set[str] = set()
    for glob in MANDATORY_TEST_GLOBS:
        for path in (ROOT / "tests" / "workflow-assistance").glob(glob):
            if path.name in RETIRED_ORDINARY_TESTS:
                continue
            selected.add(path.relative_to(ROOT).as_posix())
    return sorted(selected)


def mandatory_discovery_modules() -> list[str]:
    """Member ids for the mandatory set (P0-05), one per discovered file, routed by AST.

    A unittest member is addressed by its importable module stem (that is what `-m unittest` takes); a
    pytest member and a check script are addressed by their repository-relative path (what `-m pytest` and
    `python <file>` take). The id shape is only the addressing convention: `_run_governance_batch`
    re-derives the route from the syntax tree, so an id can never smuggle a module into the wrong runner.
    """
    members: list[str] = []
    for path in governance_test_files():
        full = ROOT / path
        members.append(Path(path).stem if governance_member_kind(full) == "unittest" else path)
    return members


class MemberOutcome(NamedTuple):
    """What one discovered member really executed.

    `collected` is what the framework found, `ran` what it started, `skipped` what it declined, `executed`
    the cases that reached a verdict. A member with `executed == 0` contributed nothing to coverage, and
    the batch now treats that as failure rather than as a smaller green number.
    """

    kind: str
    collected: int
    ran: int
    skipped: int
    executed: int
    exit_code: int


GOVERNANCE_TEST_ROOT = ROOT / "tests" / "workflow-assistance"
_VENDOR_TEST_BASES = frozenset({"TestCase", "IsolatedAsyncioTestCase"})

# NF31 (2026-10-26): the classifier this replaces asked whether the literal text `unittest` appeared
# anywhere in the file. That is not a fact about test frameworks, it is a fact about substrings, and both
# directions of the error were live on the tree:
#   * `test_snapshot_v3_schema_is_the_single_shape_authority.py` is a pytest module (17 bare `def test_*`)
#     that mentions `unittest` inside a comment, so it went to `python -m unittest` and printed
#     `Ran 0 tests / OK / rc=0`;
#   * nine genuine pytest modules went to `python <file>`, imported cleanly, printed nothing and exited 0.
# Ten members, 78 cases that had never been executed by anything, and a batch that printed PASS because
# its only evidence was one shared `Ran N` banner plus a returncode. A returncode says a process did not
# crash; it says nothing about whether a test ran.


def _ast_base_names(expression: ast.expr) -> list[str]:
    """Class names a base expression can denote, resolved textually (the module is never imported here)."""
    if isinstance(expression, ast.Attribute):
        return [expression.attr]
    if isinstance(expression, ast.Name):
        return [expression.id]
    if isinstance(expression, ast.Subscript):  # `TestCase[Some]`-style generic bases
        return _ast_base_names(expression.value)
    if isinstance(expression, ast.Call):  # vendor factories such as `parametrize(...)` bases
        return _ast_base_names(expression.func)
    return []


def governance_member_kind(path: Path) -> str:
    """`unittest` | `pytest` | `script`, from the syntax tree rather than from a substring.

    pytest iff the file declares module-level `def test_*` functions; unittest iff it owns a
    `unittest.TestCase` subclass. A file with BOTH goes to pytest: pytest collects TestCase subclasses as
    well as bare functions, while `python -m unittest` silently drops the functions -- routing the mixed
    shape to unittest is precisely how cases become invisible. A file with neither is a self-executing
    check script and must prove it ran by printing (see `_run_governance_batch`).
    """
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except (OSError, SyntaxError, UnicodeDecodeError):
        # Unparseable does NOT mean "carries no tests". Send it to the script route and let the child's
        # own traceback convict it: a SyntaxError exits non-zero, which fails the batch.
        return "script"
    module_tests = [
        node for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test")
    ]
    classes = [node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
    case_classes = {
        node.name for node in classes
        if any(base in _VENDOR_TEST_BASES for base in _all_bases(node))
    }
    # A mixin (`class _Guard(unittest.TestCase)` + `class TestThing(_Guard)`) is still a TestCase subclass;
    # judging only the literal base name would call nf08-style modules pytest and lose every one of them.
    changed = True
    while changed:
        changed = False
        for node in classes:
            if node.name in case_classes:
                continue
            if any(base in case_classes for base in _all_bases(node)):
                case_classes.add(node.name)
                changed = True
    if module_tests:
        return "pytest"
    return "unittest" if case_classes else "script"


def _all_bases(node: ast.ClassDef) -> list[str]:
    names: list[str] = []
    for base in node.bases:
        names.extend(_ast_base_names(base))
    return names


def governance_member_path(member: str) -> Path:
    """The file behind a member id: stems live in the mandatory test root, paths are repo-relative."""
    if member.endswith(".py"):
        return ROOT / Path(member)
    return GOVERNANCE_TEST_ROOT / f"{member}.py"


def governance_member_route(member: str) -> str:
    """The route for a member id, re-derived from disk (never trusted from the id's shape)."""
    path = governance_member_path(member)
    if not path.is_file():
        # An id with no file behind it keeps the unittest route, where the child fails loudly
        # (`ModuleNotFoundError`), instead of being reclassified into a script that exits 0 having done
        # nothing. This is also the shape a mocked batch takes.
        return "unittest"
    return governance_member_kind(path)


# One started test per match. unittest prints `<method> (<module>.<Class>.<method>) ... ok`, and when the
# method has a docstring the description spans two lines so the `... <outcome>` tail lands on the FOLLOWING
# line -- counting case-start lines (never outcome lines) is the only shape that neither loses a test with
# a docstring nor double-counts the traceback's `FAIL: <method> (<path>)` header.
GOVERNANCE_CASE_START = re.compile(
    r"^(?P<case>[^\s]+) \((?P<path>[^()]*)\)(?: \[[^\]]*\])?(?P<tail>.*)$", re.MULTILINE
)
GOVERNANCE_CASE_OUTCOME = re.compile(r"\.\.\.\s+(ok|FAIL|ERROR|skipped)")
GOVERNANCE_RAN_BANNER = re.compile(r"^Ran (\d+) tests? in", re.MULTILINE)


def _unittest_member_outcomes(
    members: list[str], output: str, exit_code: int
) -> dict[str, MemberOutcome]:
    """Per-module attribution of ONE batched `python -m unittest -v` run.

    Attribution is by the leading module component of the case id, because that component is exactly the
    stem the batch passed on the command line. An import that blew up is reported against
    `unittest.loader._FailedTest.<target>`, whose first component is the loader, not the member -- handled
    separately so a broken module is attributed instead of vanishing.
    """
    known = set(members)
    counters: dict[str, list[int]] = {member: [0, 0] for member in members}
    for match in GOVERNANCE_CASE_START.finditer(output):
        dotted = match.group("path")
        if "." not in dotted:
            continue  # the summary line `OK (skipped=3)` is not a case
        components = dotted.split(".")
        member = components[0]
        if member not in known:
            if not dotted.startswith("unittest.loader._FailedTest."):
                continue
            member = next((part for part in components[3:] if part in known), "")
            if not member:
                continue
        counters[member][0] += 1
        window = match.group("tail") + "\n" + output[match.end():match.end() + 300]
        outcome = GOVERNANCE_CASE_OUTCOME.search(window)
        if outcome and outcome.group(1) == "skipped":
            counters[member][1] += 1
    outcomes: dict[str, MemberOutcome] = {}
    for member in members:
        ran, skipped = counters[member]
        outcomes[member] = MemberOutcome("unittest", ran, ran, skipped, ran - skipped, exit_code)
    return outcomes


PYTEST_STATE_COUNTS = re.compile(r"(?P<count>\d+) (?P<state>passed|failed|errors?|error|skipped|xfailed|xpassed|deselected)")
PYTEST_COLLECTED_LINE = re.compile(r"(?P<count>\d+) tests? collected")


def _pytest_counts(summary: str) -> dict[str, int]:
    """`{"passed": 17, "skipped": 1, ...}` from pytest's own summary line."""
    counts: dict[str, int] = {}
    for match in PYTEST_STATE_COUNTS.finditer(summary):
        state = match.group("state").rstrip("s")
        counts[state] = counts.get(state, 0) + int(match.group("count"))
    return counts


def _pytest_summary_line(output: str) -> str:
    """The last line that states counts -- pytest's terminal short summary.

    Scanned from the bottom because a failure report repeats the word `passed` inside assertion text, and
    reading an arbitrary line would invent cases.
    """
    for line in reversed(output.splitlines()):
        stripped = line.strip().strip("=").strip()
        if not stripped:
            continue
        if PYTEST_STATE_COUNTS.search(stripped) or "no tests ran" in stripped or "collected" in stripped:
            return stripped
    return ""


def _pytest_member_output(output: str, exit_code: int, collected: int) -> MemberOutcome:
    counts = _pytest_counts(_pytest_summary_line(output))
    verdicts = sum(counts.get(state, 0) for state in ("passed", "failed", "xfailed", "xpassed"))
    # pytest states collection/fixture blow-ups as `errors`, and an error is not a case that reached a
    # verdict: a module that explodes on import reports `1 error` while executing zero tests. Counting it
    # as execution would let the collection-error shape back into the hole this closes.
    ran = verdicts + counts.get("skipped", 0) + counts.get("error", 0)
    skipped = counts.get("skipped", 0)
    return MemberOutcome("pytest", collected, ran, skipped, verdicts, exit_code)


def _script_member_output(stdout_and_stderr: str, exit_code: int) -> MemberOutcome:
    """Evidence for a member that owns no test framework at all.

    It has no per-case granularity, so its unit of evidence is one self-reported verdict run -- and the only
    proof it produced a verdict is that it PRINTED. Measured 2026-10-26: nine of the ten silently-green
    members printed absolutely nothing and exited 0. Silence is zero, and zero is a failure.
    """
    spoke = 1 if stdout_and_stderr.strip() else 0
    return MemberOutcome("script", spoke, spoke, 0, spoke, exit_code)


def governance_hollow_members(members: list[str], outcomes: dict[str, MemberOutcome]) -> list[str]:
    """`ZERO_EXECUTED <member>` for every discovered member that ran nothing.

    A member missing from `outcomes` counts as hollow: the accounting, not the returncode, is the evidence,
    so an unwritten row can never be read as a pass.
    """
    hollow = []
    for member in members:
        outcome = outcomes.get(member)
        if outcome is None or outcome.executed <= 0:
            hollow.append(f"ZERO_EXECUTED {member}")
    return hollow


def _governance_batch_env() -> dict[str, str]:
    pythonpath = MODULE_PYTHONPATH
    existing = os.environ.get("PYTHONPATH")
    if existing:
        pythonpath += os.pathsep + existing
    env = project_runtime_environment(ROOT)
    env["PYTHONPATH"] = pythonpath
    return env


def _run_governance_batch(
    members: list[str],
) -> tuple[int, str, dict[str, MemberOutcome]]:
    """Run the mandatory members as one fail-closed batch and ACCOUNT FOR EVERY ONE OF THEM.

    Returns (process exit code, combined stdout+stderr, per-member outcomes). Three routes, chosen by
    `governance_member_kind`: unittest members share one `-m unittest -v` process (unchanged, and their
    per-member counts are attributed from the verbose case lines); pytest members each get
    `-m pytest -q --collect-only` then `-m pytest -q -rs`, because a summary line can only be read per
    module if the module is run alone; check scripts keep `python <file>`.

    Per-member accounting exists because a shared banner is not coverage: one `Ran N` for 250 modules lets
    ten empty modules hide inside a big number, and a returncode only proves no process crashed.
    """
    env = _governance_batch_env()
    # Both ends pinned: mandatory modules print Chinese in failure text, and a `text=True` pipe with no
    # encoding decodes with the host locale. On this machine that is cp936, so a UTF-8 byte sequence
    # killed subprocess's own reader thread, `communicate()` returned None for that stream, and the
    # concatenation below raised TypeError -- which destroyed the whole gate receipt while CI (UTF-8
    # locale) could never show it. See ERR-211.
    env["PYTHONIOENCODING"] = "utf-8"
    routes = {member: governance_member_route(member) for member in members}
    outcomes: dict[str, MemberOutcome] = {}
    combined: list[str] = []
    overall = 0

    def absorb(code: int) -> None:
        nonlocal overall
        if code != 0 and overall == 0:
            overall = code

    unittest_members = [member for member in members if routes[member] == "unittest"]
    if unittest_members:
        result = subprocess.run(
            [sys.executable, "-m", "unittest", "-v", *unittest_members],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        output = result.stdout + result.stderr
        combined.append(output)
        absorb(result.returncode)
        outcomes.update(_unittest_member_outcomes(unittest_members, output, result.returncode))

    for member in members:
        if routes[member] != "pytest":
            continue
        collected_run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--collect-only", member],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        run = subprocess.run(
            [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "-rs", member],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        collected_match = PYTEST_COLLECTED_LINE.search(collected_run.stdout + collected_run.stderr)
        collected = int(collected_match.group("count")) if collected_match else 0
        output = (
            f"--- pytest --collect-only {member} ---\n"
            f"{collected_run.stdout}{collected_run.stderr}\n"
            f"--- pytest {member} (rc={run.returncode}) ---\n"
            f"{run.stdout}{run.stderr}"
        )
        combined.append(output)
        # A collection error (rc=2) is a real failure even when the run itself reports nothing.
        absorb(run.returncode or collected_run.returncode)
        outcomes[member] = _pytest_member_output(run.stdout + run.stderr, run.returncode, collected)

    for member in members:
        if routes[member] != "script":
            continue
        result = subprocess.run(
            [sys.executable, member],
            cwd=ROOT,
            env=env,
            text=True,
            encoding="utf-8",
            errors="replace",
            capture_output=True,
        )
        output = result.stdout + result.stderr
        combined.append(output)
        absorb(result.returncode)
        outcomes[member] = _script_member_output(output, result.returncode)

    return overall, "\n".join(combined), outcomes


def _git_head_identity() -> tuple[str, str]:
    """Best-effort (head commit, head tree) for failure provenance. Never raises."""
    def _git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            ).stdout.strip()
        except Exception:
            return ""
    commit = _git("rev-parse", "HEAD") or "unknown"
    tree = _git("rev-parse", "HEAD^{tree}") or "unknown"
    return commit, tree


_GOVERNANCE_SECRET_RE = re.compile(
    r"(?:api[_-]?key|secret|password|authorization|cookie|private[_-]?key)\s*[:=]\s*\S+"
    r"|\b(?:Bearer|Basic)\s+[A-Za-z0-9._~+/=-]{8,}"
    r"|\b(?:sk-|gh[pousr]_|xox[baprs]-)[A-Za-z0-9_-]{8,}",
    re.I,
)


def _redact_governance_text(text: str) -> str:
    """Bounded credential redaction so a failure log never carries secrets."""
    return _GOVERNANCE_SECRET_RE.sub("[REDACTED]", text)


def _governance_failure_markers(output: str) -> list[str]:
    """Which test/command failed — bounded, deduped, so a batch failure is diagnosable.

    Both runners are covered now that the batch has two: unittest writes `FAIL: <case> (<path>)`, pytest
    writes `FAILED <file>::<test> - <reason>`. A pytest failure that produces no marker is a red the reader
    cannot act on, which is the same class of blindness as a silent member.
    """
    markers: list[str] = []
    for line in output.splitlines():
        s = line.strip()
        if (
            s.startswith("FAIL: ")
            or s.startswith("ERROR: ")
            or re.match(r"^FAILED \S+::", s)
            or re.match(r"^ERROR \S+::", s)
            or re.match(r"^FAILED \((?:failures|errors)=", s)
            or "AssertionError" in s
            or "ModuleNotFoundError" in s
            or "No module named" in s
        ):
            markers.append(s)
    seen: set[str] = set()
    out: list[str] = []
    for m in markers:
        if m not in seen:
            seen.add(m)
            out.append(m)
    return out[:60]


# W11 (2026-10-17): the machine-readable chain a stage has to carry. Before this, triage started with "which
# module failed?", and the answer existed only inside a ~2500-line stdout that CI keeps behind a log URL --
# so the first step of every diagnosis was fetching and grepping that log. Gates OPT IN by recording here; a
# gate that records nothing is written as `chain: not-reported`, never as "nothing to report", because the
# absence of a record and a record of absence are different facts.
STAGE_CHAIN: dict[str, dict[str, object]] = {}
CURRENT_GATE: str = ""


def record_stage_chain(**fields: object) -> None:
    """Attach machine-readable detail to the stage currently running (no-op outside a stage)."""
    if not CURRENT_GATE:
        return
    STAGE_CHAIN.setdefault(CURRENT_GATE, {}).update(fields)


def _report_governance_failure(
    members: list[str], exit_code: int, output: str, hollow: list[str] | None = None
) -> None:
    """A3: make a governance-batch failure diagnosable without leaking secrets.

    Surfaces (1) the failing test/command names, (2) a bounded redacted error
    summary, (3) where the full redacted log was written, (4) the actual exit
    code, and (5) the commit/tree under test. The full environment is never
    dumped and credential-like values are redacted.

    NF31 adds (6) the members that executed nothing: a batch can go red both because a case failed and
    because a module stopped contributing cases, and only the second explains a shrinking `executed=`.
    """
    commit, tree = _git_head_identity()
    log_dir = ROOT / ".project-local" / "runs"
    try:
        log_dir.mkdir(parents=True, exist_ok=True)
        log_path = log_dir / "quality-gate-governance-fail.log"
        log_path.write_text(_redact_governance_text(output), encoding="utf-8")
        log_rel = log_path.relative_to(ROOT).as_posix()
    except Exception:
        log_rel = "(could not write log)"
    markers = _governance_failure_markers(output)
    hollow = hollow or []
    # W11: the failing members ARE the triage answer; record them instead of leaving them in the log only.
    record_stage_chain(exit=exit_code, member_count=len(members),
                       failing_members=markers, full_log=log_rel, zero_executed=hollow[:40])
    print(f"QUALITY_GATE_GOVERNANCE_FAIL exit={exit_code}")
    print(f"  failing_members=[{'; '.join(markers) if markers else 'unknown-see-log'}]")
    print(f"  modules_run={len(members)}")
    if hollow:
        print(f"  zero_executed={len(hollow)} [{'; '.join(hollow[:20])}]")
    print(f"  head_commit={commit} head_tree={tree}")
    print(f"  full_log={log_rel}")
    for line in _redact_governance_text(output).splitlines()[-25:]:
        print(f"    | {line}")


GOVERNANCE_SKIP_LINE = re.compile(r"^(?P<case>.*?) \.\.\. skipped (?P<reason>.+)$", re.MULTILINE)
# pytest states a skip on its own line (`-rs`), not in the unittest verbose shape, so a batch that now runs
# pytest modules on their own route would otherwise count skips it could not name.
GOVERNANCE_PYTEST_SKIP_LINE = re.compile(
    r"^SKIPPED(?: \[\d+\])? (?P<case>[^\n:]+:\d+): (?P<reason>.+)$", re.MULTILINE
)


def governance_skip_identities(output: str) -> list[tuple[str, str]]:
    """Every skip the batch reported, as (case, reason) pairs.

    Until now a PASS discarded the captured batch output and printed only ``skipped=N``, which reads
    identically whether the N are environment boundaries or checks that quietly stopped being
    collected. The reason is the actionable half, and it was thrown away.
    """
    found = []
    for match in GOVERNANCE_SKIP_LINE.finditer(output):
        case = match.group("case").strip().split("\n")[-1].strip()
        found.append((case or "<unnamed-case>", match.group("reason").strip()))
    for match in GOVERNANCE_PYTEST_SKIP_LINE.finditer(output):
        found.append((match.group("case").strip(), match.group("reason").strip()))
    return found


def _governance_skip_truth(execution: str, identities: list[tuple[str, str]]) -> tuple[int, bool]:
    """(reported, agrees): does the number of named skips equal the banner's count?

    Disagreement is a failure, not a notice: a skip nobody can name is indistinguishable from a check
    that stopped running, and the whole point of the count was to tell those two apart.
    """
    m = re.search(r"skipped=(\d+)", execution)
    reported = int(m.group(1)) if m else 0
    return reported, reported == len(identities)


def _governance_execution_truth(output: str, has_unittest: bool) -> tuple[bool, str]:
    """C4: describe what the shared unittest banner says. Since NF31 this is NOT the batch verdict.

    A ``Ran N tests`` banner with N == 0, or all N skipped, is NOT execution.
    The old single-regex check (``^Ran \\d+ tests?``) matched ``Ran 0 tests``
    and reported a hollow batch as executed; every hollow outcome here fails
    closed with a named state: not-run / zero-tests / all-skipped.

    The `has_unittest == False` branch used to be how an all-script batch PASSED: it answered "yes,
    executed" from nothing but a returncode, which is exactly how ten silently-green modules stayed green.
    `gate_governance` no longer consults this function for the verdict -- per-member accounting decides --
    and the branch only keeps its shape because `test_recovery_materials_gates.py` pins this helper's
    contract. It is a description, never a pass.
    """
    if not has_unittest:
        return True, "script-only-batch(descriptive only: per-member ZERO_EXECUTED accounting decides)"
    m = re.search(r"^Ran (\d+) tests? in", output, flags=re.MULTILINE)
    if not m:
        return False, "not-run (no unittest execution banner found)"
    total = int(m.group(1))
    if total == 0:
        return False, "zero-tests (Ran 0 tests: required tests did not execute)"
    skipped_matches = re.findall(r"skipped=(\d+)", output)
    skipped = int(skipped_matches[-1]) if skipped_matches else 0
    executed = total - skipped
    if executed <= 0:
        return False, f"all-skipped (Ran {total} tests, skipped={skipped}: nothing actually executed)"
    return True, f"executed={executed} ran={total} skipped={skipped}"


def gate_governance() -> int:
    """P0-05 + C4 + NF31: run the mandatory tests, fail-closed on any hollow outcome.

    missing          != PASS  (empty mandatory set is a red flag, not a clean pass)
    ZERO_EXECUTED    != PASS  (NF31: a member that executed nothing fails the batch by name)
    attribution gap  != PASS  (NF31: cases the shared banner ran but no member can account for)
    not-run          != PASS  (clean exit but no execution banner)
    zero-tests       != PASS  (C4: ``Ran 0 tests`` is a hollow outcome)
    all-skipped      != PASS  (C4: skips are not executions)
    cancelled/failed != PASS  (non-zero batch exit; subcommand failures presented)

    The verdict is the per-member accounting, not `_governance_execution_truth`: one banner over 250
    modules is a sum, and a sum cannot tell a contributor that ran from a contributor that printed nothing.
    """
    members = mandatory_discovery_modules()
    # W11: the batch's subcommands are its member modules; the test ids come from the failure markers above.
    record_stage_chain(member_count=len(members), members=list(members[:300]))
    if not members:
        print("QUALITY_GATE_GOVERNANCE_FAIL empty-mandatory-set")
        return 1
    exit_code, output, outcomes = _run_governance_batch(members)
    hollow = governance_hollow_members(members, outcomes)
    record_stage_chain(
        collected=sum(o.collected for o in outcomes.values()),
        executed=sum(o.executed for o in outcomes.values()),
        zero_executed=len(hollow),
        zero_executed_members=hollow[:40],
    )
    if exit_code != 0:
        _report_governance_failure(members, exit_code, output, hollow)
        return exit_code
    if hollow:
        print(f"QUALITY_GATE_GOVERNANCE_FAIL {'; '.join(hollow[:20])}"
              f"{'' if len(hollow) <= 20 else ' ...'} (hollow={len(hollow)} of modules={len(members)}: "
              f"a member that executed zero tests is not coverage)")
        return 1
    unittest_ran = sum(o.ran for o in outcomes.values() if o.kind == "unittest")
    banner = GOVERNANCE_RAN_BANNER.search(output)
    if banner and int(banner.group(1)) != unittest_ran:
        print(f"QUALITY_GATE_GOVERNANCE_FAIL ATTRIBUTION_GAP banner_ran={banner.group(1)} "
              f"attributed={unittest_ran} — the batch ran cases no member can account for, so the "
              f"per-module numbers below are not trustworthy")
        return 1
    ran = sum(o.ran for o in outcomes.values())
    skipped = sum(o.skipped for o in outcomes.values())
    executed = sum(o.executed for o in outcomes.values())
    execution = f"executed={executed} ran={ran} skipped={skipped}"
    if executed <= 0:
        print(f"QUALITY_GATE_GOVERNANCE_FAIL zero-tests ({execution}: required tests did not execute)")
        return 1
    identities = governance_skip_identities(output)
    reported, agrees = _governance_skip_truth(execution, identities)
    if not agrees:
        print(f"QUALITY_GATE_GOVERNANCE_FAIL skip_identity_unproven reported={reported} "
              f"named={len(identities)} — a skip that cannot be named is indistinguishable from a "
              f"check that stopped being collected")
        return 1
    # The route tally comes from the accounting rows, not from re-classifying the disk a second time: the
    # number that matters is how each member was ACTUALLY run, which is what produced these counts.
    by_route = {
        kind: sum(1 for outcome in outcomes.values() if outcome.kind == kind)
        for kind in ("unittest", "pytest", "script")
    }
    print(f"QUALITY_GATE_GOVERNANCE_PASS modules={len(members)} {execution}")
    print(f"GOVERNANCE_ROUTES unittest={by_route['unittest']} pytest={by_route['pytest']} "
          f"script={by_route['script']} "
          f"pytest_executed={sum(o.executed for o in outcomes.values() if o.kind == 'pytest')}")

    if reported:
        by_reason: dict[str, int] = {}
        for _, reason in identities:
            by_reason[reason] = by_reason.get(reason, 0) + 1
        print(f"GOVERNANCE_SKIPS named={len(identities)} reasons={len(by_reason)}")
        for reason, count in sorted(by_reason.items(), key=lambda kv: (-kv[1], kv[0])):
            cases = ", ".join(sorted(c for c, r in identities if r == reason)[:4])
            print(f"  SKIPPED x{count} {reason} :: {cases}")
    return 0



def gate_compile() -> int:
    # Chunked, not one argv: the tracked set is 644 files, which is ~29 KB of command line against the
    # 32,767-character CreateProcess ceiling. A repository that grows 10% would otherwise fail to start the
    # compiler at all -- and a gate that cannot launch reports nothing, which reads as no defects.
    files = tracked_python_files()
    worst = 0
    batches = 0
    for start in range(0, len(files), 80):
        batches += 1
        worst = max(worst, run_python(["-m", "py_compile", *files[start:start + 80]]))
    print(f"COMPILE_SCOPE files={len(files)} batches={batches} exit={worst}")
    return worst


def gate_security() -> int:
    return run_python(
        [
            "packages/client-neutral-core/scripts/security/scan_agent_rules.py",
            "packages/client-neutral-core/templates",
            "packages/client-neutral-core/skills",
            "integrations/executors/codex",
            "docs",
            "scripts",
            "README.md",
        ]
    )


def gate_skill_provenance() -> int:
    return run_python(
        [
            "packages/client-neutral-core/scripts/security/check_skill_provenance.py",
            "--manifest",
            "config/skill-provenance.yaml",
        ]
    )


def gate_context_pack() -> int:
    return run_python(["packages/client-neutral-core/scripts/build_context_pack.py", "--max-chars", "30000"])


def gate_portable_install() -> int:
    return run_python(["packages/client-neutral-core/scripts/verify_portable_install.py"])


def gate_client_neutral_manifest() -> int:
    return run_python(["packages/client-neutral-core/scripts/verify_client_neutral_manifest.py"])


def gate_core_schemas() -> int:
    return run_python(["packages/client-neutral-core/scripts/verify_core_schemas.py", "--schema-dir", "packages/contracts/schemas/workflow"])


def gate_adapter_registry() -> int:
    return run_python(
        [
            "packages/client-neutral-core/scripts/verify_adapter_registry.py",
            "--registry",
            "config/adapter-registry.json",
            "--schema",
            "packages/contracts/schemas/workflow/adapter-registry.schema.json",
            "--root",
            ".",
        ]
    )


def gate_capability_matrix() -> int:
    """WL3-100: capability-matrix.json stays consistent with adapter-registry.json."""
    return run_python(["packages/client-neutral-core/scripts/verify_capability_matrix.py"])


def gate_model_registry_integrity() -> int:
    """AG-05: model/provider/runtime registries stay internally consistent.

    Fail-closed checks that a provider's `binds_to_model` resolves to a model id
    (or a declared external asset), that `binds_to_runtime` resolves to an HTTP
    runtime or an explicitly declared in-process library, that `binding_status`
    cannot contradict the model lifecycle, that a runtime-scoped operationalStatus
    does not use serving vocabulary for an unserved binding, and that a digest is
    either COMPLETE with a 64-hex sha256 or TRUNCATED with a stated reason. Reads
    JSON only: never downloads, installs, or touches runtime or global config.
    """
    return run_python(["scripts/ci/verify_model_registry_integrity.py"])


def gate_acp_adapter_honesty() -> int:
    """AG-06: the ACP surface reports declared/implemented/executable/native_verified.

    Fail-closed: an execution capability may not be advertised when its operation
    produces no real effect, an operation may not be reported executable unless the
    probe avoided a degraded status, and native_verified requires a native receipt.
    Probing is read-only and never launches an executor process.
    """
    return run_python(["scripts/ci/verify_acp_adapter_honesty.py"])


def gate_observer_readonly_boundary() -> int:
    """AG-15 prerequisite: the Observer read-only split is machine-enforced repo-wide.

    Three fail-closed rules: the serving surface denies every non-GET method, the
    Observer frontend never issues a write verb, and no authoritative write control
    is rendered without an explicit disabled guard. Complements the per-view
    runtime assertions in l10-views.test.tsx, which only cover one rendered lane.
    """
    return run_python(["scripts/ci/verify_observer_readonly_boundary.py"])


def gate_observer_frontend_contracts() -> int:
    """Run the two front-end suites CI runs and this gate did not.

    Measured twice in one day: `run_quality_gate.py verify` printed GATE_EXIT=0 while the CI `observer`
    job went red — first on the legibility micro-role rule in
    `apps/observer/tests/run_all_tests.js`, then on a vitest failure in `src/App.behavior.test.tsx`.
    Both suites are authoritative about the shipped surface, and neither had a local route, which is
    the ERR-151 class in a new costume: a check that only exists in CI cannot protect the commit you
    are about to push.

    The route resolves Node from `.project/governance/toolchain-declarations.json` rather than from
    PATH, and a host where that resolution fails prints `OBSERVER_FRONTEND_CONTRACTS_NOT_RUN` and
    returns non-zero — a skipped required check is a failure, not a pass with a shrug.
    """
    return run_python(["apps/observer/scripts/frontend_toolchain.py", "contracts"])


def gate_registry_closure_report() -> int:
    """AG-05: produce the field-level closure report for the three registries.

    The Atlas closed gap G05 as "close it field by field"; this is the aggregate
    answer an auditor actually asks (which fields are CLOSED / EXPLICITLY_OPEN /
    UNCLOSED). It reports rather than fails, because an unclosed field is a hole
    to surface, not a reason to hide one — but the report must be produced, and
    the accompanying negative controls (`nf26`) prove it can detect each hole.
    """
    return run_python(["scripts/ci/report_registry_closure.py"])


EVIDENCE_TIER_BUNDLES = (
    "reports/audit-evidence/assets-20260930/MANIFEST.json",
    "reports/audit-evidence/assets-20260930/CLEANUP-CANDIDATES.json",
    "reports/audit-evidence/assets-20260930/global-workflow-coverage.json",
    "reports/audit-evidence/assets-20260930/inventory-verification.json",
    "reports/audit-evidence/assets-20260930/asset-inventory.json",
    "reports/audit-archive/20260930/ARCHIVE-INDEX.json",
    "reports/audit-archive/20260930",
)


def gate_root_governance_suite() -> int:
    """AG-06t: run the root `tests/ci/` governance suite (the push-time blind spot).

    The canonical gate ran 43 `tests/workflow-assistance/` modules and ZERO of the 22
    `tests/ci/` ones, so editing the shared error ledger could go green locally and
    still fail CI — which is exactly what happened (an invalid `phase` enum and a
    zero original-failure `exit_code` were found only by CI). The module globs the
    suite so a new check is covered automatically; the single post-merge-state module
    is excluded with its reason asserted in the script.
    """
    return run_python(["scripts/ci/run_root_governance_suite.py"])


def gate_evidence_tiering() -> int:
    """AG-06i (audit F15/F16): a bundle may not read as proof it cannot be.

    The motivating defect was a package whose every digest matched while it still
    invited a conclusion it could not support (`external_roots_touched: []` cannot
    show a root was never read; a secret scan whose scanner source was not
    retained cannot be re-derived). The gate refuses a behavioural claim that
    carries no tier, and refuses a sub-VERIFIED tier that names nothing it cannot
    establish.
    """
    return run_python(
        ["scripts/ci/verify_evidence_tiering.py", *EVIDENCE_TIER_BUNDLES]
    )


def gate_policy_coverage() -> int:
    """U17.7/27: Global Agent Policy coverage + freshness.

    Fail-closed check that the derived policy-coverage surfaces (loss reports,
    the capability-matrix coverage block, the golden projections) are fresh with
    respect to their sources (the policy SSOT + per-software extensions).
    Hand-editing a generated artifact without moving the source policy is drift.
    """
    return run_python(["scripts/ci/verify_policy_coverage.py"])


def gate_blueprint_projection() -> int:
    """The blueprint coverage projection must equal what its mutable sources say now.

    Measured cause: the CI integration job went red at d76deef0 and again at cdfd27d4 with
    BLUEPRINT_COVERAGE_FAIL, while the canonical local gate printed PASS on the same tree. The
    projection restates register cells verbatim, so rewriting 12 dangling register pins made it
    stale -- and only CI could see it, because this check ran nowhere but the integration job. A
    freshness rule a writer cannot run before pushing is a rule that will be broken by honest
    edits to its source.
    """
    return run_python(["scripts/ci/verify_blueprint_coverage.py"])


def gate_context_control_plane() -> int:
    """Context Control Plane: stable prefix, cache truth, drift guard tests."""
    return run_python(["tests/workflow-assistance/test_context_control_plane.py"])


def gate_external_libraries_index() -> int:
    """External libraries index: structure is fatal, root discovery is reported.

    The docstring promised "sharedRoots resolve + assets present" while the call never
    passed --authorized-discovery, so every run reported NOT_SEARCHED for all four roots
    and the promise was never actually checked. Discovery states stay non-fatal by the
    verifier's own design (a volume that is offline is not evidence of missing
    software); what changes is that this machine's roots are now really searched.
    """
    return run_python(["packages/client-neutral-core/scripts/verify_external_libraries_index.py",
                       "--authorized-discovery"])


def gate_protected_drives_consistency() -> int:
    """WS-3: E/F protected-drive truth consistent across all three governed surfaces.

    The user standing rule protects BOTH data drives (E: and F:). The gate reads the
    SSOT (config/global-agent-policy.yaml protected_drives), projects.json forbiddenRoots,
    and project-data-boundary.json (forbiddenExternalRoots + protectedDataVolume.roots)
    and fails if any surface drops a drive. In-script runner (not a test file) mirrors
    gate_external_libraries_index: deterministic, offline, stdlib-only.
    """
    return run_python(
        ["packages/client-neutral-core/scripts/verify_protected_drives_consistency.py"]
    )


def gate_three_project_boundary() -> int:
    """V2: control-plane / knowledge / design ownership split — boundary marked + gated.

    Fail-closed: proves every three-project boundary split is recorded in the SSOT,
    has a dir marker (BOUNDARY.md), an ArcheAxis seam, and a migration-manifest entry.
    In-script runner, deterministic, offline, stdlib-only.
    """
    return run_python(["scripts/ci/verify_three_project_boundary.py"])


def gate_github_delivery() -> int:
    """GitHub delivery accelerator: upload/review contracts (offline tests)."""
    return run_python(["tests/workflow-assistance/test_github_delivery.py"])


def gate_adapter_conformance() -> int:
    return run_python(["tests/workflow-assistance/test_adapter_conformance.py"])


def gate_acp_conformance() -> int:
    """NX-200: ACP protocol/capability conformance + Qwen Code pilot probe."""
    code = run_python(["packages/client-neutral-core/scripts/verify_acp_conformance.py"])
    if code != 0:
        return code
    return run_python(["tests/workflow-assistance/test_acp_adapter.py"])


def gate_otel_mapping() -> int:
    """NX-300: OTel/OpenInference semantic mapping + privacy negative control."""
    code = run_python(["packages/client-neutral-core/scripts/verify_otel_mapping.py"])
    if code != 0:
        return code
    return run_python(["tests/workflow-assistance/test_otel_mapping.py"])


def gate_usage_ingestion() -> int:
    """NX-310: cross-agent usage ingestion + coverage matrix."""
    code = run_python(["packages/client-neutral-core/scripts/verify_usage_ingestion.py"])
    if code != 0:
        return code
    return run_python(["tests/workflow-assistance/test_usage_ingestion.py"])


def gate_memory_contamination() -> int:
    """NX-400: memory contamination adversarial negative controls."""
    code = run_python(["packages/client-neutral-core/scripts/verify_memory_contamination.py"])
    if code != 0:
        return code
    return run_python(["tests/workflow-assistance/test_memory_contamination.py"])


def gate_task_ledger_replay() -> int:
    """NX-410: Task Ledger replay + side-effect consistency harness."""
    code = run_python(["packages/client-neutral-core/scripts/verify_task_ledger_replay.py"])
    if code != 0:
        return code
    return run_python(["tests/workflow-assistance/test_task_ledger_replay.py"])


def gate_portable_install_runtime() -> int:
    if not command_exists("hermes"):
        print("\n=== FAIL portable-install-runtime: hermes CLI not found; runtime compatibility is required ===")
        return 1
    return run_python(["packages/client-neutral-core/scripts/verify_portable_install.py", "--runtime"])


def gate_plugin_inventory_honesty() -> int:
    """AG-06l (audit F07): a plugin record may not outrun its evidence.

    F07's visible half was `commit: null` beside a declared revision. Its
    important half is the caveat: a revision string cannot prove the installed
    bytes match that commit — verified live, where chrome-profiles' declared
    revision is correct while its working tree is locally modified. The gate also
    refuses presence without observation and an observation that hides a delta.
    """
    return run_python(
        ["scripts/ci/verify_plugin_inventory.py", "config/plugin-inventory.json"]
    )


def gate_provider_inventory() -> int:
    return run_python(
        [
            "packages/client-neutral-core/scripts/provider_health.py",
            "--config",
            "config/config.yaml",
            "--output",
            ".project-local/artifacts/provider-health.json",
        ]
    )


def gate_mcp_audit() -> int:
    return run_python(
        [
            "packages/client-neutral-core/scripts/mcp_candidate_audit.py",
            "--write-template",
            ".project-local/artifacts/mcp-candidate-template.yaml",
        ]
    )


def gate_shell() -> int:
    bash = usable_bash()
    if not bash:
        # AGENTS.md: a failed, cancelled, MISSING or skipped required job fails the aggregate. Printing a
        # SKIP and returning 0 certified a syntax check that never ran, so an environment without bash
        # (or without Git Bash on Windows) reports exactly the verdict a healthy tree would.
        print("\nQUALITY_GATE_NOT_RUN gate=shell reason=BASH_ABSENT")
        return 3
    return run([bash, "-n", "scripts/setup-workflow.sh"])


def gate_runtime_convergence() -> int:
    """WL3-400/410/500/510/600: canonical store, durable worker, collectors, SSE."""
    tests = (
        "tests/workflow-assistance/test_canonical_store.py",
        "tests/workflow-assistance/test_canonical_store_v2.py",
        "tests/workflow-assistance/test_durable_worker.py",
        "tests/workflow-assistance/test_project_registry.py",
        "tests/workflow-assistance/test_collectors.py",
        "tests/workflow-assistance/test_sse_hub.py",
        "tests/workflow-assistance/test_snapshot_sse_live.py",
        "tests/workflow-assistance/test_platform_discovery.py",
        "tests/workflow-assistance/test_skill_package_digest.py",
        "tests/workflow-assistance/test_config_ownership.py",
        "tests/workflow-assistance/test_config_coordinator.py",
        "tests/workflow-assistance/test_memory_governance.py",
        "tests/workflow-assistance/test_skill_plugin_scan.py",
        "tests/workflow-assistance/test_controlled_repro.py",
        "tests/workflow-assistance/test_model_lane_billing.py",
        "tests/workflow-assistance/test_real_adapters.py",
        "tests/workflow-assistance/test_tiered_adapters.py",
        "tests/workflow-assistance/test_swap_and_size.py",
        "tests/workflow-assistance/test_growth_watcher_collector.py",
        "tests/workflow-assistance/test_active_projects.py",
        "tests/workflow-assistance/test_product_project.py",
        "tests/workflow-assistance/test_project_identity_resolver.py",
        "tests/workflow-assistance/test_execution_anchor.py",
        "tests/workflow-assistance/test_project_candidate_discovery.py",
        "tests/workflow-assistance/test_execution_evidence.py",
        "tests/workflow-assistance/test_collector_scheduler.py",
        "tests/workflow-assistance/test_adapter_sdk.py",
        "tests/workflow-assistance/test_agent_adapters.py",
        "tests/workflow-assistance/test_fallback_collectors.py",
        "tests/workflow-assistance/test_evidence_aggregator.py",
        "tests/workflow-assistance/test_wlgm_privacy.py",
    )
    pythonpath = MODULE_PYTHONPATH
    existing = os.environ.get("PYTHONPATH")
    if existing:
        pythonpath += os.pathsep + existing
    code = run_python(
        ["-m", "unittest", "-v", *(Path(test).stem for test in tests)],
        env_updates={"PYTHONPATH": pythonpath},
    )
    if code != 0:
        return code
    # GATE-RUNTIME-CONVERGENCE acceptance (9/10 locally; #9 Tauri PENDING by toolchain).
    return run_python(
        ["packages/client-neutral-core/scripts/verify_gate_runtime_convergence.py"],
        env_updates={"PYTHONPATH": pythonpath},
    )


def gate_powershell() -> int:
    pwsh = shutil.which("pwsh") or shutil.which("powershell.exe")
    if not pwsh:
        print("\nQUALITY_GATE_NOT_RUN gate=powershell reason=PWSH_ABSENT")
        return 3
    script = (
        "$tokens = $null; $errors = $null; "
        "[System.Management.Automation.Language.Parser]::ParseFile((Resolve-Path ./scripts/setup-workflow.ps1), [ref]$tokens, [ref]$errors) | Out-Null; "
        "if ($errors.Count -gt 0) { $errors | ForEach-Object { Write-Error $_ }; exit 1 }"
    )
    return run([pwsh, "-NoProfile", "-Command", script])


# ---------- WLGM §7 named quality gates ----------

def _run_wlgm_tests(test_names: tuple[str, ...]) -> int:
    pythonpath = MODULE_PYTHONPATH
    existing = os.environ.get("PYTHONPATH")
    if existing:
        pythonpath += os.pathsep + existing
    return run_python(
        ["-m", "unittest", "-v", *(Path(t).stem for t in test_names)],
        env_updates={"PYTHONPATH": pythonpath},
    )


def gate_project_identity_contract() -> int:
    """§7: product project identity + resolver contracts."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_product_project.py", "tests/workflow-assistance/test_project_identity_resolver.py"))


def gate_agent_adapter_readonly_contract() -> int:
    """§7: adapters are read-only; missing capabilities are explicit."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_adapter_sdk.py", "tests/workflow-assistance/test_agent_adapters.py"))


def gate_execution_state_machine() -> int:
    """§7: execution state machine has no illegal transitions."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_evidence_aggregator.py",))


def gate_collector_noninterference() -> int:
    """§7: collectors never block the writer; bounded, breakered."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_collector_scheduler.py", "tests/workflow-assistance/test_fallback_collectors.py"))


def gate_canonical_single_writer() -> int:
    """§7: canonical SQLite is the single writer; migrations recoverable."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_canonical_store_v2.py",))


def gate_observer_no_business_write() -> int:
    """§7: observer surface has no business-write path."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_wlgm_privacy.py",))


def gate_snapshot_schema_v3() -> int:
    """§7: snapshot v3 schema validation + projection contract."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_snapshot_validator.py", "tests/workflow-assistance/test_snapshot_sse_live.py"))


def gate_sse_browser_reconnect() -> int:
    """§7: persistent SSE revision + reconnect recovery semantics."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_snapshot_sse_live.py",))


def gate_field_quality_no_fabrication() -> int:
    """§7: unknown/unsupported never fabricated as 0/LIVE/exact."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_wlgm_privacy.py", "tests/workflow-assistance/test_evidence_aggregator.py"))


def gate_privacy_redaction() -> int:
    """§7: credentials/prompt bodies never enter canonical or snapshot."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_execution_evidence.py", "tests/workflow-assistance/test_wlgm_privacy.py"))


def gate_windows_project_resolution() -> int:
    """§7: Windows path case/slash containment + space-path resolution."""
    return _run_wlgm_tests(("tests/workflow-assistance/test_project_identity_resolver.py", "tests/workflow-assistance/test_project_terminal_guard.py"))


def gate_tauri_readonly_shell() -> int:
    """§7 (static): Tauri shell accepts only loopback v3 snapshot; strict CSP.

    Rust compilation requires a toolchain; this gate verifies the contract
    statically (endpoint validation source + CSP config).
    """
    errors: list[str] = []
    # The Tauri shell lives at apps/observer/src-tauri under the repository root.
    # ROOT already IS that root; the previous ROOT.parent.parent was written when
    # ROOT meant the workflow-assistance module root, and after the directory
    # migration it resolved to the parent of the repository.
    repo_root = ROOT
    tauri_root = repo_root / "apps" / "observer" / "src-tauri"
    lib = tauri_root / "src" / "lib.rs"
    if lib.is_file():
        source = lib.read_text(encoding="utf-8")
        if "/api/v1/snapshot" not in source:
            errors.append("lib.rs does not accept /api/v1/snapshot")
        if "is_loopback()" not in source:
            errors.append("lib.rs lacks loopback-only validation")
        if "url.query().is_none()" not in source or "url.fragment().is_none()" not in source:
            errors.append("lib.rs does not reject query/fragment endpoints")
        # R2 third batch: the retired /api/dashboard entry must be rejected
        # (production allow-list pattern; test assertions on .is_none() are fine).
        if re.search(r'url\.path\(\)\s*==\s*"/api/dashboard"', source):
            errors.append("lib.rs still tolerates the retired /api/dashboard entry")
    else:
        errors.append("Tauri lib.rs missing")
    conf = tauri_root / "tauri.conf.json"
    if conf.is_file():
        import json as _json

        data = _json.loads(conf.read_text(encoding="utf-8"))
        csp = data.get("app", {}).get("security", {}).get("csp")
        if not isinstance(csp, str) or "script-src" not in csp or "connect-src" not in csp:
            errors.append("tauri.conf.json CSP is not strict")
    else:
        errors.append("Tauri tauri.conf.json missing")
    if errors:
        print("TAURI_READONLY_SHELL_FAIL " + "; ".join(errors))
        return 1
    print("TAURI_READONLY_SHELL_PASS (static contract; Rust compile requires toolchain)")
    return 0


def gate_work_lab_os_canary() -> int:
    """§7: WORK-LAB self-canary; external OS-project canary stays PENDING.

    P0-7: the canary runner's exit code IS the gate verdict — a failing
    self-canary must fail the gate (no more print-FAIL-but-exit-0).

    The runner lives under services/orchestration (it moved in the directory
    migration) and imports from several module roots, so the gate supplies the
    project's standard module PYTHONPATH rather than a single directory.
    """
    return run_python([str(ROOT / "services" / "orchestration" / "canary_runner.py")],
                      env_updates={"PYTHONPATH": MODULE_PYTHONPATH})


_EXACT_SHA_CI_PROVIDER_OK = {"github-actions", "gh-actions", "github_actions", "actions"}
_EXACT_SHA_CI_LOCAL_SELF = {"local", "self", "self-filled", "manually-authored", ""}


def _is_git_sha(value: object) -> bool:
    import re as _re
    return isinstance(value, str) and bool(_re.fullmatch(r"[0-9a-fA-F]{40}", value))


def exact_sha_ci_evidence_digest(evidence: dict) -> str:
    """C3: canonical identity digest over the tamper-bearing fields of an
    exact-SHA CI evidence object. A reader recomputes this over the same core
    fields and compares to the recorded ``content_sha256`` — that is the
    integrity + read-back check, so a locally self-filled / edited success is
    detectable, not trusted on presence alone.
    """
    import hashlib
    import json as _json
    core = {
        "repository": evidence.get("repository"),
        "commit": evidence.get("commit"),
        "tree": evidence.get("tree"),
        "ci_identity": {
            "provider": str(evidence.get("ci", {}).get("provider", "")),
            "run_id": evidence.get("ci", {}).get("run_id"),
            "head_sha": evidence.get("ci", {}).get("head_sha"),
        },
        "required_checks": sorted(evidence.get("required_checks", [])),
        "jobs": sorted(
            (
                {"name": j.get("name"), "conclusion": j.get("conclusion")}
                for j in evidence.get("ci", {}).get("jobs", [])
            ),
            key=lambda d: _json.dumps(d, ensure_ascii=False, sort_keys=True),
        ),
    }
    canonical = _json.dumps(core, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def validate_exact_sha_ci_evidence(
    evidence: dict,
    *,
    expected_repo: str,
    expected_commit: str,
    expected_tree: str,
) -> list[str]:
    """C3: structural + truth checks an exact-SHA CI evidence object must pass
    before it counts as valid CI evidence. Returns a list of issues (empty =
    valid). Fails closed on every hollow outcome; a locally self-filled success
    is refused.
    """
    issues: list[str] = []
    if not isinstance(evidence, dict):
        return ["evidence root is not an object"]

    # schema / provenance fields
    if not evidence.get("schema_version"):
        issues.append("schema_version missing")
    if not evidence.get("observed_at"):
        issues.append("observed_at missing")
    produced_by = str(evidence.get("produced_by", "")).strip().lower()
    if produced_by in _EXACT_SHA_CI_LOCAL_SELF:
        issues.append("evidence source unverifiable (locally/self-filled success is not CI evidence)")

    # repository identity
    if str(evidence.get("repository", "")).strip() != expected_repo:
        issues.append(f"repository mismatch (evidence={evidence.get('repository')!r} expected={expected_repo!r})")

    # subject commit/tree under validation (exact-SHA binding)
    if not _is_git_sha(evidence.get("commit")):
        issues.append("commit not a 40-hex git SHA")
    elif evidence["commit"] != expected_commit:
        issues.append(f"commit mismatch (evidence={evidence['commit']} expected={expected_commit})")
    if not _is_git_sha(evidence.get("tree")):
        issues.append("tree not a 40-hex git tree")
    elif evidence["tree"] != expected_tree:
        issues.append(f"tree mismatch (evidence={evidence['tree']} expected={expected_tree})")

    # CI run/job identity
    ci = evidence.get("ci") or {}
    provider = str(ci.get("provider", "")).strip().lower()
    if provider not in _EXACT_SHA_CI_PROVIDER_OK:
        issues.append(f"ci.provider not a recognized hosted CI provider (got {provider!r})")
    if not str(ci.get("run_id", "")).strip():
        issues.append("ci.run_id missing")
    head_sha = ci.get("head_sha")
    if not _is_git_sha(head_sha):
        issues.append("ci.head_sha not a 40-hex git SHA")
    elif _is_git_sha(evidence.get("commit")) and head_sha != evidence["commit"]:
        issues.append("ci.head_sha does not equal the subject commit")

    # required checks: each must have an actual success conclusion (skipped != pass)
    required = evidence.get("required_checks") or []
    if not isinstance(required, list) or not required:
        issues.append("required_checks missing or empty")
    else:
        jobs = ci.get("jobs") or []
        by_name: dict[str, str] = {}
        for j in jobs:
            if isinstance(j, dict) and j.get("name"):
                by_name[str(j["name"]).lower()] = str(j.get("conclusion", "")).strip().lower()
        for check in required:
            key = str(check).lower()
            if key not in by_name:
                issues.append(f"required check missing in CI jobs: {check}")
            elif by_name[key] != "success":
                issues.append(f"required check not success: {check} (conclusion={by_name[key]})")

    # integrity / read-back digest
    recorded = evidence.get("content_sha256")
    recomputed = exact_sha_ci_evidence_digest(evidence)
    if not recorded or recorded != recomputed:
        issues.append("content_sha256 missing or does not match recomputed identity digest")

    return issues


def _git_origin_repo_identity() -> str:
    """Owner/name of the origin remote, or '' when it cannot be resolved.

    Accepts both ``https://host/owner/name.git`` and scp-like
    ``git@host:owner/name.git`` URL forms; anything else (no remote, local
    path remote) yields '' — an unverifiable identity fails the content check
    rather than being guessed.
    """
    try:
        out = subprocess.run(["git", "config", "--get", "remote.origin.url"],
                             cwd=ROOT, capture_output=True, text=True, timeout=30,
                             encoding="utf-8", errors="replace").stdout.strip()
    except Exception:
        out = ""
    if not out:
        return ""
    url = out
    if "://" in url:
        url = url.split("://", 1)[1]
    url = url.replace(":", "/")  # scp-like git@host:owner/name
    parts = [p for p in url.split("/") if p]
    if len(parts) < 3:
        return ""
    owner, name = parts[-2], parts[-1]
    if name.endswith(".git"):
        name = name[: -4]
    return f"{owner}/{name}"


def gate_exact_sha_ci() -> int:
    """§7 + C3: exact-SHA CI evidence. required=true verifies the evidence
    file's CONTENT, not just its existence.

    P0-7: only a required context (WLGM_EXACT_SHA_CI_REQUIRED=1) fails on
    missing evidence; the ordinary local structural check stays PENDING=0.
    C3: when required, the evidence is parsed and content-validated —
    repository identity, subject commit/tree, CI run/job identity, the actual
    conclusion of every required check, a verifiable (non-self-filled)
    source, and a recomputable integrity digest. Empty file / bad JSON /
    wrong repo / wrong SHA / a failed-or-missing required check / an
    unverifiable source all fail closed.
    """
    import json as _json
    required = os.environ.get("WLGM_EXACT_SHA_CI_REQUIRED", "").strip().lower() in ("1", "true", "yes")
    if not required:
        print("EXACT_SHA_CI PENDING (requires GitHub Actions run; local gate cannot verify)")
        return 0
    evidence_path = ROOT / ".project-local" / "artifacts" / "exact-sha-ci.json"
    if not evidence_path.is_file():
        print(f"EXACT_SHA_CI_FAIL required=true evidence_missing={evidence_path}")
        return 1
    try:
        evidence = _json.loads(evidence_path.read_text(encoding="utf-8"))
    except Exception as exc:
        print(f"EXACT_SHA_CI_FAIL required=true evidence_invalid_json ({exc})")
        return 1
    commit, tree = _git_head_identity()
    repo = _git_origin_repo_identity()
    issues = validate_exact_sha_ci_evidence(
        evidence, expected_repo=repo, expected_commit=commit, expected_tree=tree
    )
    if issues:
        print("EXACT_SHA_CI_FAIL required=true content_invalid:")
        for item in issues:
            print(f"  - {item}")
        print(f"  (subject commit={commit[:12]} tree={tree[:12]} repo={repo or 'unresolved'})")
        return 1
    print(
        f"EXACT_SHA_CI_PASS required=true evidence={evidence_path} "
        f"commit={commit[:12]} tree={tree[:12]} checks={len(evidence.get('required_checks', []))}"
    )
    return 0


GATES: dict[str, Gate] = {
    "governance": Gate("governance", "Run all mandatory workflow + negative-control (nf*) tests in one fail-closed batch.", gate_governance),
    "compile": Gate("compile", "Compile repository Python workflow/security/test files.", gate_compile),
    "skill-provenance": Gate("skill-provenance", "Validate source skill metadata, references, and provenance hashes.", gate_skill_provenance),
    "security": Gate("security", "Scan templates, skills, docs, scripts and README for prompt/security hazards.", gate_security),
    "context-pack": Gate("context-pack", "Generate the safe ignored Context Pack smoke artifact.", gate_context_pack),
    "client-neutral-manifest": Gate(
        "client-neutral-manifest",
        "Verify the client-neutral product and adapter manifest without a Hermes runtime.",
        gate_client_neutral_manifest,
    ),
    "core-schemas": Gate(
        "core-schemas",
        "Verify client-neutral ActionPlan, Domain Pack, Adapter, and evidence schemas.",
        gate_core_schemas,
    ),
    "adapter-registry": Gate(
        "adapter-registry",
        "Verify adapter provenance, risk, status, and package hash evidence.",
        gate_adapter_registry,
    ),
    "capability-matrix": Gate(
        "capability-matrix",
        "WL3-100: verify capability-matrix.json stays consistent with the adapter registry.",
        gate_capability_matrix,
    ),
    "model-registry-integrity": Gate(
        "model-registry-integrity",
        "AG-05: provider/model/runtime registries have no dangling foreign key, "
        "contradictory binding status, or unverifiable digest.",
        gate_model_registry_integrity,
    ),
    "acp-adapter-honesty": Gate(
        "acp-adapter-honesty",
        "AG-06: ACP operations report declared/implemented/executable/native_verified "
        "separately; no execution capability is advertised without a real effect.",
        gate_acp_adapter_honesty,
    ),
    "observer-readonly-boundary": Gate(
        "observer-readonly-boundary",
        "AG-15: the Observer read-only split is enforced repo-wide (no non-GET "
        "handler, no write verb, no unguarded authoritative write control).",
        gate_observer_readonly_boundary,
    ),
    "observer-frontend-contracts": Gate(
        "observer-frontend-contracts",
        "Run the observer JS static contract suite and vitest locally, so a green verify "
        "cannot disagree with the CI observer job (ERR-151 class, front-end edition).",
        gate_observer_frontend_contracts,
    ),
    "registry-closure-report": Gate(
        "registry-closure-report",
        "AG-05: field-level closure report for provider/model/runtime registries "
        "(CLOSED / EXPLICITLY_OPEN / UNCLOSED).",
        gate_registry_closure_report,
    ),
    "evidence-tiering": Gate(
        "evidence-tiering",
        "AG-06i (audit F15/F16): an evidence bundle that makes a behavioural "
        "claim must tier it, and a claim below VERIFIED must name what it cannot "
        "establish, so a declared claim cannot be read as proof.",
        gate_evidence_tiering,
    ),
    "root-governance-suite": Gate(
        "root-governance-suite",
        "AG-06t: run the root tests/ci/ governance suite, which the canonical gate "
        "previously skipped entirely, so a green local run can no longer hide a CI "
        "failure in the shared ledgers and contracts.",
        gate_root_governance_suite,
    ),
    "policy-coverage": Gate(
        "policy-coverage",
        "U17.7/27: verify Global Agent Policy coverage + freshness (loss reports, matrix block, golden projections).",
        gate_policy_coverage,
    ),
    "blueprint-projection": Gate(
        "blueprint-projection",
        "The blueprint coverage projection must match its mutable sources right now, not on CI only.",
        gate_blueprint_projection,
    ),
    "context-control-plane": Gate(
        "context-control-plane",
        "Context Control Plane: stable prefix + cache truth + drift guard.",
        gate_context_control_plane,
    ),
    "external-libraries-index": Gate(
        "external-libraries-index",
        "External libraries index: JSON valid + roots resolve + assets listed (content stays local).",
        gate_external_libraries_index,
    ),
    "protected-drives-consistency": Gate(
        "protected-drives-consistency",
        "WS-3: E/F protected-drive truth consistent across policy SSOT, projects.json, and project-data-boundary.json.",
        gate_protected_drives_consistency,
    ),
    "three-project-boundary": Gate(
        "three-project-boundary",
        "V2: WORK-LAB control-plane vs ArcheAxis knowledge vs DESIGN-LAB design ownership split — "
        "boundary SSOT + dir markers + ArcheAxis seams + migration manifest, fail-closed.",
        gate_three_project_boundary,
    ),
    "github-delivery": Gate(
        "github-delivery",
        "GitHub delivery accelerator: upload/review contracts (offline tests).",
        gate_github_delivery,
    ),
    "adapter-conformance": Gate(
        "adapter-conformance",
        "Run adapter conformance checks.",
        gate_adapter_conformance,
    ),
    "acp-conformance": Gate(
        "acp-conformance",
        "NX-200: ACP protocol/capability conformance + Qwen Code pilot.",
        gate_acp_conformance,
    ),
    "otel-mapping": Gate(
        "otel-mapping",
        "NX-300: OTel/OpenInference semantic mapping + privacy negative control.",
        gate_otel_mapping,
    ),
    "usage-ingestion": Gate(
        "usage-ingestion",
        "NX-310: cross-agent usage ingestion + coverage matrix.",
        gate_usage_ingestion,
    ),
    "memory-contamination": Gate(
        "memory-contamination",
        "NX-400: memory contamination adversarial negative controls.",
        gate_memory_contamination,
    ),
    "task-ledger-replay": Gate(
        "task-ledger-replay",
        "NX-410: Task Ledger replay + side-effect consistency harness.",
        gate_task_ledger_replay,
    ),
    "portable-install": Gate("portable-install", "Verify an isolated empty Hermes home can receive the package.", gate_portable_install),
    "portable-install-runtime": Gate(
        "portable-install-runtime",
        "Run the real Hermes config check against an isolated portable home.",
        gate_portable_install_runtime,
    ),
    "provider-inventory": Gate("provider-inventory", "Generate the secret-free configured provider/model inventory.", gate_provider_inventory),
    "plugin-inventory-honesty": Gate(
        "plugin-inventory-honesty",
        "AG-06l (audit F07): a plugin record may not claim presence without an "
        "observation, and an observation may not hide a local delta; a revision "
        "string alone never proves the installed bytes match that commit.",
        gate_plugin_inventory_honesty,
    ),
    "mcp-audit": Gate("mcp-audit", "Smoke the MCP candidate audit template generator.", gate_mcp_audit),
    "shell": Gate("shell", "Parse scripts/setup-workflow.sh with bash -n when bash is available.", gate_shell),
    "runtime-convergence": Gate(
        "runtime-convergence",
        "WL3 Wave 1: canonical store, durable worker, registry, collectors, SSE.",
        gate_runtime_convergence,
    ),
    "powershell": Gate("powershell", "Parse scripts/setup-workflow.ps1 with PowerShell AST when pwsh/powershell.exe is available.", gate_powershell),
    # WLGM §7 named gates.
    "project-identity-contract": Gate("project-identity-contract", "WLGM §7: product project identity + resolver contracts.", gate_project_identity_contract),
    "agent-adapter-readonly-contract": Gate("agent-adapter-readonly-contract", "WLGM §7: adapters read-only, capabilities explicit.", gate_agent_adapter_readonly_contract),
    "execution-state-machine": Gate("execution-state-machine", "WLGM §7: execution state machine transitions.", gate_execution_state_machine),
    "collector-noninterference": Gate("collector-noninterference", "WLGM §7: collectors never block the writer.", gate_collector_noninterference),
    "canonical-single-writer": Gate("canonical-single-writer", "WLGM §7: single canonical writer + recoverable migration.", gate_canonical_single_writer),
    "observer-no-business-write": Gate("observer-no-business-write", "WLGM §7: observer has no business-write path.", gate_observer_no_business_write),
    "snapshot-schema-v3": Gate("snapshot-schema-v3", "WLGM §7: snapshot v3 schema validation.", gate_snapshot_schema_v3),
    "sse-browser-reconnect": Gate("sse-browser-reconnect", "WLGM §7: persistent SSE revision + reconnect.", gate_sse_browser_reconnect),
    "field-quality-no-fabrication": Gate("field-quality-no-fabrication", "WLGM §7: unknown never fabricated.", gate_field_quality_no_fabrication),
    "privacy-redaction": Gate("privacy-redaction", "WLGM §7: credentials never enter canonical/snapshot.", gate_privacy_redaction),
    "windows-project-resolution": Gate("windows-project-resolution", "WLGM §7: Windows path resolution contract.", gate_windows_project_resolution),
    "tauri-readonly-shell": Gate("tauri-readonly-shell", "WLGM §7 (static): Tauri loopback-only + strict CSP.", gate_tauri_readonly_shell),
    "work-lab-os-canary": Gate("work-lab-os-canary", "WLGM §7: WORK-LAB self-canary (external PENDING).", gate_work_lab_os_canary),
    "exact-sha-ci": Gate("exact-sha-ci", "WLGM §7: exact-SHA CI evidence (PENDING locally).", gate_exact_sha_ci),
}

VERIFY_ORDER = (
    "governance",
    "compile",
    "skill-provenance",
    "security",
    "context-pack",
    "client-neutral-manifest",
    "core-schemas",
    "adapter-registry",
    "capability-matrix",
    "model-registry-integrity",
    "acp-adapter-honesty",
    "observer-readonly-boundary",
    "observer-frontend-contracts",
    "registry-closure-report",
    "evidence-tiering",
    "root-governance-suite",
    "policy-coverage",
    "blueprint-projection",
    "context-control-plane",
    "external-libraries-index",
    "protected-drives-consistency",
    "three-project-boundary",
    "github-delivery",
    "adapter-conformance",
    "acp-conformance",
    "otel-mapping",
    "usage-ingestion",
    "memory-contamination",
    "task-ledger-replay",
    "portable-install",
    "provider-inventory",
    "plugin-inventory-honesty",
    "mcp-audit",
    "shell",
    "runtime-convergence",
    "powershell",
    # WLGM §7 named gates (after core gates).
    "project-identity-contract",
    "agent-adapter-readonly-contract",
    "execution-state-machine",
    "collector-noninterference",
    "canonical-single-writer",
    "observer-no-business-write",
    "snapshot-schema-v3",
    "sse-browser-reconnect",
    "field-quality-no-fabrication",
    "privacy-redaction",
    "windows-project-resolution",
    "tauri-readonly-shell",
    "work-lab-os-canary",
    "exact-sha-ci",
)


def _source_binding() -> tuple[str, str, str, int]:
    """(head commit, head tree, digest of the worktree state, count of changed-or-untracked paths).

    The receipt has to name the bytes it judged. A head hash alone is not enough: the gates read the working
    tree, so a verification run against a dirty checkout certifies bytes that no commit will ever carry, and
    a run whose tree changed halfway certifies nothing at all. `git status --porcelain -uall` is 35ms here
    because `.project-local/` -- where the receipts themselves are written -- is ignored, so the act of
    recording cannot move the digest it records.
    """
    def _git(*args: str) -> str:
        try:
            return subprocess.run(
                ["git", *args], cwd=ROOT, capture_output=True, text=True,
                encoding="utf-8", errors="replace"
            ).stdout
        except Exception:
            return ""
    commit, tree = _git_head_identity()
    status = _git("status", "--porcelain=v1", "-uall")
    paths = [line for line in status.splitlines() if line.strip()]
    return commit, tree, hashlib.sha256("\n".join(paths).encode("utf-8")).hexdigest()[:16], len(paths)


def _tool_versions() -> str:
    """Which interpreters ran. Node is resolved per gate here, so say so rather than print a misleading absent."""
    node = os.environ.get("NODE") or shutil.which("node")
    version = "not-on-PATH(observer-frontend-contracts resolves its own managed runtime)"
    if node:
        try:
            version = subprocess.run([node, "--version"], capture_output=True, text=True,
                                     encoding="utf-8", errors="replace").stdout.strip()
        except Exception:
            version = "unresolvable"
    return (f"GATE_TOOLS python={platform.python_version()}({sys.executable}) "
            f"node={node or 'unset'}@{version}")


def run_gate_sequence(names: tuple[str, ...], command: str = "") -> int:
    # Stamp the head FIRST, before any gate runs. A receipt that never says which commit it describes
    # cannot distinguish "verified and red" from "never verified", and the second one is not evidence
    # about the first. `scripts/ci/push_permit.py` reads this line; the verdict comes from GATE_EXIT.
    start_commit, start_tree, start_dirty, start_paths = _source_binding()
    # GATE_FULL is the property a push decision actually turns on: a receipt from one cheap gate must
    # not be readable as "the head was verified". Derived, never passed in, so a new call site cannot
    # forget to set it.
    full = "yes" if set(names) == set(VERIFY_ORDER) else "no"
    # W11: one process, one sequence. Clearing means a second call in the same process cannot inherit the
    # first call's chain -- a stale chain would attribute one stage's members to another.
    global CURRENT_GATE
    STAGE_CHAIN.clear()
    stage_records: list[dict[str, object]] = []
    print(f"GATE_HEAD={start_commit} GATE_TREE={start_tree} GATE_FULL={full} gates={len(names)}")
    print(f"GATE_DIRTY={start_dirty} dirty_paths={start_paths}")
    print(_tool_versions())
    if command:
        print(f"GATE_COMMAND={command}")

    def finish(code: int, ran: int, failed_gate: str = "") -> int:
        """Close the receipt: the end binding, whether the source moved, then the verdict line.

        Every path lands here, including the red one. The completion line is written by this process and
        nowhere else -- a receipt a wrapper has to complete by hand is a receipt that eventually is not,
        and a token printed only on the pass path makes 'ran and failed' indistinguishable from 'never ran'.
        """
        end_commit, end_tree, end_dirty, end_paths = _source_binding()
        drift = (end_commit, end_tree, end_dirty) != (start_commit, start_tree, start_dirty)
        # W10/W11 (2026-10-17): the per-stage record, written on BOTH paths. It exists because the run
        # produced no artifacts at all, so auditing a red run meant reading the log -- and the two facts an
        # auditor needs first (which stage failed, with what exit and how long) were the two hardest to find.
        # A failure to write it is reported by name and does NOT change the verdict: this file is auxiliary,
        # and the verdict is GATE_EXIT.
        try:
            record_path = ROOT / ".project-local" / "runs" / "ci" / "gate-stages.json"
            record_path.parent.mkdir(parents=True, exist_ok=True)
            record_path.write_text(json.dumps({
                "schemaVersion": "work-lab/gate-stages/v1",
                "source": {"commit": end_commit, "tree": end_tree},
                "requested_gates": list(names),
                "full": full == "yes",
                "stages": stage_records,
                "failed_gate": failed_gate or None,
                "exit": code,
            }, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8", newline="\n")
            print(f"GATE_STAGE_RECORD={record_path.relative_to(ROOT).as_posix()} stages={len(stage_records)}")
        except Exception as exc:  # noqa: BLE001 - named, not swallowed
            print(f"GATE_STAGE_RECORD_FAIL {type(exc).__name__}: {exc} "
                  f"(the verdict below is unaffected; the record is auxiliary)")
        print(f"GATE_HEAD_END={end_commit} GATE_TREE_END={end_tree} "
              f"GATE_DIRTY_END={end_dirty} dirty_paths_end={end_paths}")
        print(f"GATE_STAGES ran={ran} planned={len(names)} full={full}"
              + (f" failed_gate={failed_gate}" if failed_gate else ""))
        print(f"GATE_SOURCE_DRIFT={'yes' if drift else 'no'}")
        if drift and code == 0:
            # A pass over bytes that are gone is not a pass over these bytes. Refuse rather than let the
            # oldest still-valid-looking line carry the verdict.
            print("QUALITY_GATE_SOURCE_CHANGED head/tree/worktree moved during the run; "
                  "the stages above did not all see the same source")
            code = 70
        if failed_gate:
            print(f"QUALITY_GATE_FAIL gate={failed_gate} exit_code={code}")
        print(f"GATE_EXIT={code}")
        return code

    for index, name in enumerate(names):
        gate = GATES[name]
        print(f"\n### gate: {gate.name} — {gate.description}")
        started = time.monotonic()
        CURRENT_GATE = gate.name
        exit_code = gate.runner()
        elapsed = time.monotonic() - started
        # Per-stage seconds and exit code: the tier split below is only defensible if the receipt says what
        # each stage cost, and a red receipt that names no failing stage cannot be triaged without a rerun.
        print(f"GATE_STAGE gate={gate.name} exit={exit_code} seconds={elapsed:.1f}")
        stage_records.append({
            "index": index,
            "gate": gate.name,
            "exit": exit_code,
            "seconds": round(elapsed, 1),
            "description": gate.description,
            # `not-reported` is the honest value for a gate that records nothing: it says the chain was not
            # captured, which is different from "this stage has no members".
            "chain": STAGE_CHAIN.get(gate.name, "not-reported"),
        })
        CURRENT_GATE = ""
        if exit_code != 0:
            print("")
            return finish(exit_code, ran=index + 1, failed_gate=gate.name)
    print("\nQUALITY_GATE_PASS gates=" + ",".join(names))
    # The GATE_HEAD/GATE_FULL stamp is emitted at the top of this function, before any gate runs, so a
    # red receipt identifies its head too.
    # P1-3: never present an environment-limited local pass as full completion.
    print(
        "GATE_SEMANTICS STRUCTURAL_LOCAL_PASS=yes "
        "RUNTIME_CANARY_PENDING=yes(without WORKLAB_CANARY_PROJECT_ROOTS) "
        "TAURI_WINDOWS_PENDING=yes(real desktop WebView2 E2E not executed in this run) "
        "EXACT_SHA_CI_UNVERIFIED=yes(local only, no exact-SHA Actions run)"
    )
    return finish(0, ran=len(names))


# WLOSS-700: changed-files -> relevant gates.
#
# C5: this table is the LOCAL convenience mapping for `--changed` quick runs.
# The canonical gate-selection authority is the project profile consumed by
# impact_planner.build_plan / scripts/ci/emit_gate_plan.py — CI consumes the
# canonical planner, never this table. The table's path scopes are kept in
# lock-step with the current repository tree (dead paths fixed in C5); when
# the canonical planner fully retires local `--changed`, this table follows.
# Unknown (unscoped) changed paths fail safe to the full VERIFY_ORDER so a
# local convenience mapping can never drop a necessary check to save CI.
GATE_PATH_SCOPES: dict[str, tuple[str, ...]] = {
    "governance": ("tests/workflow-assistance/", "packages/client-neutral-core/scripts/", "config/"),
    "compile": ("scripts/", "packages/client-neutral-core/scripts/", "apps/observer/src/"),
    "skill-provenance": ("packages/client-neutral-core/skills/", "integrations/executors/codex/skills/", "config/skill-provenance.yaml"),
    "security": ("config/", "integrations/executors/codex/", "README.md", "docs/"),
    "context-pack": ("packages/client-neutral-core/scripts/build_context_pack.py",),
    "client-neutral-manifest": ("packages/client-neutral-core/workflow-manifest.yaml",),
    "core-schemas": ("packages/contracts/schemas/", "config/"),
    "adapter-registry": ("config/adapter-registry.json", "packages/client-neutral-core/scripts/verify_adapter_registry.py"),
    "capability-matrix": ("config/capability-matrix.json", "packages/client-neutral-core/scripts/verify_capability_matrix.py"),
    "model-registry-integrity": (".project/governance/provider-registry.json", ".project/governance/model-registry.json", ".project/governance/runtime-registry.json", "scripts/ci/verify_model_registry_integrity.py"),
    "acp-adapter-honesty": ("services/execution-federation/", "scripts/ci/verify_acp_adapter_honesty.py"),
    "observer-readonly-boundary": ("apps/observer/frontend/src/", "services/orchestration/sidecar.py", "scripts/ci/verify_observer_readonly_boundary.py"),
    "registry-closure-report": (".project/governance/provider-registry.json", ".project/governance/model-registry.json", ".project/governance/runtime-registry.json", "scripts/ci/report_registry_closure.py"),
    "evidence-tiering": ("reports/audit-evidence/", "reports/audit-archive/", "scripts/ci/verify_evidence_tiering.py"),
    "root-governance-suite": ("tests/ci/", "scripts/ci/run_root_governance_suite.py", "taskpacks/current/error-ledger.json"),
    "policy-coverage": ("config/global-agent-policy.yaml", "config/loss-reports/", "config/capability-matrix.json", "config/adapter-registry.json", "services/policy/policy_projection.py", "integrations/executors/codex/codex_policy_renderer.py", "integrations/executors/hermes/hermes_policy_renderer.py", "integrations/executors/codex/codex-policy-extension.yaml", "integrations/executors/hermes/hermes-policy-extension.yaml", "integrations/executors/codex/global-guidance.md", "config/SOUL.md", "scripts/ci/verify_policy_coverage.py", "tests/workflow-assistance/test_policy_projection.py"),
    "context-control-plane": ("packages/client-neutral-core/scripts/context_control_plane.py", "packages/client-neutral-core/scripts/context_bundle.py", "packages/client-neutral-core/scripts/context_drift_guard.py"),
    "external-libraries-index": (".project/governance/external-libraries-index.json", "packages/client-neutral-core/scripts/verify_external_libraries_index.py"),
    "github-delivery": ("packages/client-neutral-core/scripts/github_common.py", "packages/client-neutral-core/scripts/github_upload_accelerator.py", "packages/client-neutral-core/scripts/github_review_accelerator.py"),
    "adapter-conformance": ("packages/client-neutral-core/scripts/adapter_conformance.py", "tests/workflow-assistance/test_adapter_conformance.py"),
    "acp-conformance": ("integrations/executors/codex/acp_adapter.py", "tests/workflow-assistance/test_acp_adapter.py"),
    "otel-mapping": ("services/receipts/otel_mapper.py", "tests/workflow-assistance/test_otel_mapping.py"),
    "usage-ingestion": ("services/receipts/usage_ingestion.py", "tests/workflow-assistance/test_usage_ingestion.py"),
    "memory-contamination": ("packages/client-neutral-core/scripts/memory_contamination.py",),
    "task-ledger-replay": ("packages/client-neutral-core/scripts/task_ledger_replay.py",),
    "portable-install": ("packages/client-neutral-core/scripts/verify_portable_install.py",),
    "provider-inventory": ("config/config.yaml",),
    "plugin-inventory-honesty": ("config/plugin-inventory.json", "scripts/ci/verify_plugin_inventory.py"),
    "mcp-audit": ("packages/client-neutral-core/scripts/mcp_candidate_audit.py",),
    "shell": ("scripts/setup-workflow.sh",),
    "runtime-convergence": ("packages/client-neutral-core/scripts/canonical_store.py", "services/orchestration/durable_worker.py", "packages/client-neutral-core/scripts/collectors.py", "services/orchestration/sse_hub.py", "tests/workflow-assistance/"),
    "powershell": ("scripts/setup-workflow.ps1",),
    "project-identity-contract": ("packages/client-neutral-core/scripts/product_project.py", "packages/client-neutral-core/scripts/project_identity_resolver.py", "tests/workflow-assistance/test_product_project.py", "tests/workflow-assistance/test_project_identity_resolver.py"),
    "agent-adapter-readonly-contract": ("packages/client-neutral-core/scripts/adapter_sdk.py", "integrations/executors/hermes/hermes_adapter.py", "integrations/executors/codex/codex_adapter.py"),
    "execution-state-machine": ("services/receipts/evidence_aggregator.py",),
    "collector-noninterference": ("services/orchestration/collector_scheduler.py", "packages/client-neutral-core/scripts/process_collector.py", "packages/client-neutral-core/scripts/git_collector.py"),
    "canonical-single-writer": ("packages/client-neutral-core/scripts/canonical_store.py", "tests/workflow-assistance/test_canonical_store_v2.py"),
    "observer-no-business-write": ("services/receipts/execution_evidence.py", "apps/observer/frontend/src", "tests/workflow-assistance/test_wlgm_privacy.py"),
    "snapshot-schema-v3": ("packages/client-neutral-core/scripts/snapshot_api.py", "packages/client-neutral-core/scripts/snapshot_validator.py", "tests/workflow-assistance/test_snapshot_validator.py", "tests/workflow-assistance/test_snapshot_sse_live.py"),
    "sse-browser-reconnect": ("services/orchestration/sse_revision.py", "services/orchestration/live_gate.py", "tests/workflow-assistance/test_snapshot_sse_live.py"),
    "field-quality-no-fabrication": ("services/orchestration/live_gate.py", "services/receipts/evidence_aggregator.py", "tests/workflow-assistance/test_evidence_aggregator.py"),
    "privacy-redaction": ("services/receipts/execution_evidence.py", "packages/client-neutral-core/scripts/canonical_store.py", "tests/workflow-assistance/test_execution_evidence.py", "tests/workflow-assistance/test_wlgm_privacy.py"),
    "windows-project-resolution": ("packages/client-neutral-core/scripts/project_identity_resolver.py", "packages/client-neutral-core/bin/hermes-project-terminal-guard.py", "tests/workflow-assistance/test_project_identity_resolver.py", "tests/workflow-assistance/test_project_terminal_guard.py"),
    "tauri-readonly-shell": ("apps/observer/src-tauri/", "services/orchestration/sidecar_endpoint.py", "tests/workflow-assistance/test_sidecar_endpoint.py"),
    "work-lab-os-canary": ("services/orchestration/canary_runner.py",),
    "exact-sha-ci": (),
}


# C5: recognized fast-gate-only surface prefixes. A change that ONLY hits
# these runs the always-on fast sanity gate (``compile``) and nothing else.
# These are surfaces with no dedicated gate of their own: the fast compile
# scope plus the workflow-definition surface (``.github``), whose contract is
# covered by the fast compile check. A change that hits NEITHER a gate's
# scope NOR any fast-only prefix is genuinely unknown and must fail safe to
# the full canonical verify (never skip necessary checks to save CI).
_FAST_GATE_ONLY_PREFIXES: frozenset[str] = frozenset(
    {
        "scripts/",
        "packages/client-neutral-core/scripts/",
        "apps/observer/src/",
        ".github/",
    }
)


def _is_known_fast_gate_only(scope: str) -> bool:
    s = scope.replace("\\", "/")
    return any(s == p or s.startswith(p) for p in _FAST_GATE_ONLY_PREFIXES)


def _is_uncovered(path: str) -> bool:
    """True when the path matches no gate's scope (genuinely unknown)."""
    s = path.replace("\\", "/")
    for gate, scopes in GATE_PATH_SCOPES.items():
        if gate not in GATES:
            continue
        for scope in scopes:
            scope_n = scope.replace("\\", "/")
            if s == scope_n or s.startswith(scope_n.rstrip("/") + "/"):
                return False
    return True


def select_gates_for_changed(changed_paths: list[str]) -> tuple[str, ...]:
    """Return the gates relevant to the changed paths (WLOSS-700).

    Paths may be monorepo-relative (packages/client-neutral-core/...) or
    module-relative (scripts/...); both forms are matched.

    C5 safety fallback: a change that matches no gate's scope at all is
    unknown — instead of silently running nothing we escalate to the full
    canonical verify (``VERIFY_ORDER``) so necessary checks are never
    dropped. Changes that only hit the fast-gate-only surface (``.github``
    workflows, the fast ``compile`` sanity scope) keep their pinned fast
    selection.
    """
    variants: list[str] = []
    for raw in changed_paths:
        path = raw.replace("\\", "/")
        variants.append(path)
        # Module-relative variant (strip the monorepo module prefix).
        for prefix in ("packages/client-neutral-core/", "apps/observer/"):
            if path.startswith(prefix):
                variants.append(path[len(prefix):])
    selected: set[str] = set()
    for gate, scopes in GATE_PATH_SCOPES.items():
        if gate not in GATES:
            continue
        for scope in scopes:
            scope_n = scope.replace("\\", "/")
            if any(v == scope_n or v.startswith(scope_n.rstrip("/") + "/") for v in variants):
                selected.add(gate)
                break
    # Always include the fast sanity gates for any change.
    selected |= {"compile"}
    # C5: unknown changes (no recognized scope) fail safe to the full suite.
    # Pinned fast-gate-only surface (.github workflows) is NOT unknown.
    if not all(
        not _is_uncovered(v) or _is_known_fast_gate_only(v)
        for v in variants
    ):
        return tuple(VERIFY_ORDER)
    order = [name for name in VERIFY_ORDER if name in selected]
    return tuple(order)


PROJECT_PROFILE = ROOT / ".project/governance/work-lab.project-profile.yaml"


def canonical_impact_plan(changed_paths: list[str]) -> tuple[dict[str, Any] | None, str]:
    """Ask the ONE canonical impact planner (the one CI consumes) about these paths.

    Two vocabularies exist and are not merged here: the profile names CI *jobs* (workflow, observer,
    token-monitor, supply-chain-security, integration) while this runner names *local gates*. Merging
    them is a delivery-structure decision, so the planner is consulted for the two things the local table
    cannot honestly decide on its own — whether a change is classified at all, and whether it is
    critical — and for reporting the CI jobs the same change would require.

    Returns (plan, note). A missing or unreadable plan is a NOTE plus None: the caller treats that as
    "not classified" and runs the full suite. A convenience lookup that fails must never widen scope
    reduction.
    """
    sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))
    try:
        from impact_planner import build_plan, load_profile  # noqa: PLC0415
    except Exception as error:  # noqa: BLE001 - reported, then the caller escalates
        return None, f"planner unavailable ({type(error).__name__}: {error})"
    try:
        profile = load_profile(PROJECT_PROFILE)
    except Exception as error:  # noqa: BLE001
        return None, f"profile unreadable ({type(error).__name__}: {error})"
    try:
        plan = build_plan(
            profile,
            repository="DTALEX66/WORK-LAB",
            commit=_head_commit(),
            tree=_head_tree(),
            changed_paths=changed_paths,
            plan_id="local-changed",
        )
    except Exception as error:  # noqa: BLE001
        return None, f"plan rejected ({type(error).__name__}: {error})"
    return plan, "ok"


def _head_commit() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True,
                            capture_output=True, check=False, encoding="utf-8", errors="replace")
    return result.stdout.strip() if result.returncode == 0 else "unresolved"


def _head_tree() -> str:
    result = subprocess.run(["git", "rev-parse", "HEAD^{tree}"], cwd=ROOT, text=True,
                            capture_output=True, check=False, encoding="utf-8", errors="replace")
    return result.stdout.strip() if result.returncode == 0 else "unresolved"


def cli_command(argv: list[str] | None = None) -> str:
    """The command line as typed, for the receipt. A verdict with no command cannot be reproduced."""
    args = list(sys.argv[1:] if argv is None else argv)
    return "python services/orchestration/run_quality_gate.py" + (" " + " ".join(args) if args else "")

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Workflow-assistance local quality gate runner.")
    parser.add_argument(
        "gate",
        nargs="?",
        default="verify",
        choices=("verify", *GATES.keys(), "list"),
        help="Gate to run. 'verify' runs the canonical local suite.",
    )
    parser.add_argument(
        "--changed",
        default=None,
        metavar="PATHS",
        help="Comma-separated changed file paths; runs only the relevant gates (WLOSS-700).",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.gate == "list":
        for name in VERIFY_ORDER:
            gate = GATES[name]
            print(f"{name}: {gate.description}")
        print("verify: Run " + ", ".join(VERIFY_ORDER))
        return 0
    preflight = dependency_preflight()
    if preflight != 0:
        return preflight
    if args.changed:
        changed = [p.strip() for p in args.changed.split(",") if p.strip()]
        selected = select_gates_for_changed(changed)
        # P2-04: the canonical planner is the authority on whether a change is classified at all and
        # whether it is critical. Anything it cannot answer is treated as unclassified — this wiring can
        # only ever widen the run, never narrow it below what the local table chose.
        plan, note = canonical_impact_plan(changed)
        if plan is None:
            selected, why = tuple(VERIFY_ORDER), f"planner said nothing ({note})"
        elif plan["risk"] == "critical" or not plan["required_gates"]:
            selected, why = tuple(VERIFY_ORDER), f"canonical risk={plan['risk']} required={len(plan['required_gates'])}"
        else:
            why = f"canonical risk={plan['risk']} required_jobs={','.join(plan['required_gates'])}"
        print(f"WLOSS_700 changed={len(changed)} files -> {why}; "
              f"gates={','.join(selected) or 'none'} executed={len(selected)}")
        if not selected:
            return 0
        return run_gate_sequence(selected, command=cli_command())
    if args.gate == "verify":
        return run_gate_sequence(VERIFY_ORDER, command=cli_command())
    return run_gate_sequence((args.gate,), command=cli_command())


if __name__ == "__main__":
    raise SystemExit(main())
