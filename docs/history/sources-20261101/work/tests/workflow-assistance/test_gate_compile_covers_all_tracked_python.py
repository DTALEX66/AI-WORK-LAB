"""Gate: the compile step must cover every tracked Python file, and must use a check that can fail.

Two measured defects from 2026-10-08 live here.

First, coverage. `tracked_python_files()` enumerated five roots and the gate called the result the
repository's syntax check. A mechanical edit then put `keyword argument repeated` into
`apps/observer/scripts/write_artifact_receipt.py`, a file no local suite imports; the canonical gate printed
PASS and CI went red on `SyntaxError` in the observer fail-fast group. A check over 5 of the repo's roots is
not a repo-wide check no matter what it is named -- the tree has 644 tracked `.py` files across
`apps/`, `services/`, `scripts/ci`, `scripts/audit`, `scripts/maintenance`, `integrations/` and `tests/ci`.

Second, the guard that let the bad edit through: `ast.parse` does **not** reject a repeated keyword
argument. Measured on this machine's interpreter: `ast.parse` accepted the duplicate and `compile()` raised
`SyntaxError: keyword argument repeated: errors`. So "validated by re-parsing" was a weaker claim than it
sounded, and any tool of mine that guards a source rewrite with `ast.parse` alone can ship exactly this.
The control test below pins that difference so it cannot be forgotten again.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import ast
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "services" / "orchestration"))
import run_quality_gate as gate  # noqa: E402

DUPLICATE_KWARG = (
    "import subprocess\n"
    "subprocess.run(['x'], text=True, encoding='utf-8', errors='replace', errors='replace')\n"
)
# Proof that the compile scope reaches the roots the old version skipped. Concrete paths, not a count: a
# count can be satisfied by a pile of files in one directory.
MUST_INCLUDE = (
    "apps/observer/scripts/write_artifact_receipt.py",
    "scripts/ci/verify_register_ci_claims_live.py",
    "scripts/audit/tool_inventory_readback.py",
    "scripts/maintenance/release_temp_fixture_residue.py",
    "tests/ci/test_register_table_shape_is_uniform.py",
    "integrations/executors/hermes/hermes_workflow_doctor.py",
    "services/receipts/evidence_aggregator.py",
)


class CompileScopeTests(unittest.TestCase):
    def test_the_compile_set_is_exactly_the_tracked_python_set(self) -> None:
        listed = gate.tracked_python_files()
        raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z", "*.py"],
                             cwd=ROOT, capture_output=True, check=True).stdout
        expected = sorted(name.decode("utf-8", "replace") for name in raw.split(b"\0") if name)
        self.assertEqual(listed, expected,
                         "the gate's compile input is not `git ls-files *.py`, so some tracked file is "
                         "never syntax-checked locally")
        self.assertGreater(len(listed), 600,
                           f"only {len(listed)} files are compiled; the measured tracked set is 644, so the "
                           "enumeration has narrowed back into a root list")

    def test_the_scope_reaches_every_root_the_old_list_missed(self) -> None:
        missing = [rel for rel in MUST_INCLUDE if rel not in set(gate.tracked_python_files())]
        self.assertEqual(missing, [], f"roots the five-directory list skipped are absent again: {missing}")

    def test_compile_rejects_a_duplicate_keyword_that_ast_parse_accepts(self) -> None:
        # The reason my sweep's own guard missed this: it checked the weaker predicate and believed it was
        # the stronger one.
        ast.parse(DUPLICATE_KWARG)  # must NOT raise, or the premise of the fix has changed
        with self.assertRaises(SyntaxError) as caught:
            compile(DUPLICATE_KWARG, "<control>", "exec")
        self.assertIn("repeated", str(caught.exception))

    def test_the_gate_compiles_in_batches_not_one_argv(self) -> None:
        # 644 paths is ~29 KB of command line against a 32,767-character ceiling: unbatched, the check
        # cannot launch as the tree grows, and a gate that fails to start reports no defects.
        source = (ROOT / "services" / "orchestration" / "run_quality_gate.py").read_text(encoding="utf-8")
        start = source.index("def gate_compile")
        body = source[start:source.index("\ndef ", start + 1)]
        self.assertIn("range(0, len(files)", body,
                      "gate_compile passes the whole tracked set in one argv again")


if __name__ == "__main__":
    unittest.main()
