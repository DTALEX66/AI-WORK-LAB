#!/usr/bin/env python3
"""Run the root `tests/ci/` governance suite as a discovery-driven gate.

WHY THIS EXISTS (2026-10-01). The canonical gate ran 43 `tests/workflow-assistance/`
modules and **zero** of the 22 `tests/ci/` ones. That is a real blind spot, and it was
not hypothetical: while reconciling the independent audit I edited the shared
`taskpacks/current/error-ledger.json`, ran the canonical gate to green, pushed, and CI
failed on `scripts/ci/verify_error_ledger.py` — a verifier the local gate never
invoked. Two defects (an invalid `phase` enum value and the original-failure
`exit_code` being 0) were only found by CI. Running this module catches that whole
class locally, before a push.

DISCOVERY, NOT A LIST. The suite is globbed, so a new `tests/ci/test_*.py` is covered
the moment it lands instead of being silently skipped — the exact failure mode above.
Only a module this gate declares as POST_MERGE is excluded, and an exclusion must be
justified in EXCLUSIONS and have its reason asserted below, so the list cannot quietly
grow into "whatever was failing".

Read-only. Exit 0 = all pass, 1 = a failure, 2 = discovery problem.
"""
from __future__ import annotations

import re
import ast
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TESTS_CI = ROOT / "tests" / "ci"
RAN_LINE = re.compile(r"^Ran (\d+) tests", re.M)

# Measured 2026-10-20: the report loop died with UnicodeEncodeError ('gbk' codec can't encode '\ufffd')
# while printing a failed module's own output, so `modules_failed=3` arrived with one detail and the
# runner's exit status became unreadable. The replacement character comes from decoding the *child*,
# which is correct and must survive; only the console it is spoken to was wrong. Same reason as
# services/orchestration/run_quality_gate.py: a verdict that cannot be printed is not a verdict.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (ValueError, OSError):
            pass


def vacuity_reason(returncode: int, output: str) -> str | None:
    """Why a green exit cannot be trusted, or None when the module showed it ran.

    A module with no ``unittest.main()`` entry point executes zero tests and exits 0, so discovery
    alone would report it as coverage. Measured 2026-10-25 on the live suite: 59 executed modules, every
    one printing something, none printing ``Ran 0 tests`` -- so this refuses nothing today, while
    ``shape_reason`` covers the case where a module runs *some* tests and silently skips the rest.
    """
    if returncode != 0:
        return None
    if not output.strip():
        return "SILENT_MODULE(Exited 0 without printing anything -- no evidence it ran a test)"
    match = RAN_LINE.search(output)
    if match is not None and int(match.group(1)) == 0:
        return "ZERO_TESTS(Ran 0 tests is not coverage)"
    return None


# Modules that assert POST-MERGE repository state and therefore cannot pass on an
# unpublished branch. Each entry must carry a reason naming the state it asserts.
EXCLUSIONS = {
    "test_exact_tree_review.py": (
        "asserts report['head'] == report['originMain'] and a clean worktree, i.e. "
        "post-merge state; on a PR branch HEAD is necessarily ahead of origin/main, "
        "so this is a release-time re-check, not a pre-merge gate. It is deliberately "
        "NOT referenced by the CI integration job for the same reason."
    ),
}


def shape_reason(path: Path) -> str | None:
    """Why this module's shape cannot be executed faithfully as a script, or None when it can.

    This suite runs every module with `python <file>`, so anything defined after the `unittest.main()` call is
    never collected -- measured 2026-10-25: `test_cdp_harness_waits_for_mount.py` ran 14 tests as a script while
    pytest collected 21, and the seven invisible ones were two classes appended below the guard. Discovery and the
    vacuity check cannot see that, because the module looks healthy and prints `Ran 14 tests`.
    """
    try:
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)
    except (SyntaxError, UnicodeDecodeError, OSError) as error:
        return f"UNPARSEABLE({type(error).__name__})"
    guard_line = None
    for node in tree.body:
        if isinstance(node, ast.If) and "unittest.main(" in (ast.get_source_segment(text, node) or ""):
            guard_line = node.lineno
            break
    if guard_line is None:
        return None
    below = [node.name for node in tree.body
             if isinstance(node, ast.ClassDef) and node.lineno > guard_line
             and any(isinstance(child, ast.FunctionDef) and child.name.startswith("test")
                     for child in node.body)]
    return f"CLASS_BELOW_MAIN_GUARD({', '.join(below)})" if below else None


def _discover() -> list[Path]:
    if not TESTS_CI.is_dir():
        raise SystemExit(f"CI_ROOT_GOVERNANCE_DISCOVERY_FAIL: {TESTS_CI} missing")
    modules = sorted(p for p in TESTS_CI.glob("test_*.py") if p.is_file())
    if not modules:
        raise SystemExit(
            "CI_ROOT_GOVERNANCE_DISCOVERY_FAIL: no tests/ci/test_*.py discovered; the "
            "suite cannot silently be empty"
        )
    return modules


def main() -> int:
    modules = _discover()
    for name in EXCLUSIONS:
        if Path(name).name not in {m.name for m in modules}:
            raise SystemExit(
                f"CI_ROOT_GOVERNANCE_EXCLUSION_STALE: {name} is excluded but no longer "
                "exists; drop the exclusion so the list stays meaningful"
            )

    ran = 0
    failures: list[str] = []
    failed_modules = 0
    for module in modules:
        if module.name in EXCLUSIONS:
            continue
        completed = subprocess.run(
            [sys.executable, str(module)],
            cwd=str(ROOT),
            capture_output=True,
            text=True, encoding="utf-8", errors="replace",
        )
        ran += 1
        output = completed.stdout + completed.stderr
        if completed.returncode != 0:
            verdict = f"rc={completed.returncode}"
        else:
            # The shape check comes before the vacuity check: a module whose tail is unreachable still
            # prints a healthy `Ran N tests`, so silence is not the only way to report no coverage.
            verdict = shape_reason(module) or vacuity_reason(completed.returncode, output)
        if verdict is not None:
            failed_modules += 1
            failures.append(f"{module.name} ({verdict})")
            for line in output.strip().splitlines()[-6:]:
                failures.append(f"    {line}")

    if failures:
        # `failed=` used to count printed lines, so a two-module red read as "failed=14" and sent the
        # reader chasing twelve faults that did not exist
        print(f"CI_ROOT_GOVERNANCE_FAIL modules_ran={ran} modules_failed={failed_modules} "
              f"detail_lines={len(failures)}")
        for line in failures:
            print(f"  {line}")
        return 1

    skipped = len(modules) - ran
    print(
        f"CI_ROOT_GOVERNANCE_PASS modules={ran} excluded_post_merge={skipped} "
        f"discovered={len(modules)}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
