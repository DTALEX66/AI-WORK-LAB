# SPDX-License-Identifier: MIT
"""A gate entry point that exists but refuses to be run -- existence is the only thing asserted.

`domains/work/workflow_core/repair_pack_projection.py:_verification` names a verification command
only when ``services/orchestration/run_quality_gate.py`` really exists under the target project root.
`tests/conftest.py:work_project` registers the directory holding this file so the unified tests get a
real *approvable* project without depending on a repository outside the checkout.

It raises instead of returning quietly on purpose: if some future test ever shells out to the named
command, it must fail here rather than have a stub exit 0 and turn an unrunnable gate into a
fabricated PASS.
"""
import sys


def main() -> int:
    print("fixture gate: this file exists to satisfy the target-root probe; it is not a real "
          "quality gate and must never report success", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
