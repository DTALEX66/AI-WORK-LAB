---
name: python-test-discovery-truth
description: Verify a Python test gate runs its tests, not just imports.
category: software-development
---

# Python Test Discovery Truth

Class: verify that a Python test gate / CI runner actually **executes** the repo's tests — not merely imports or compiles the files. Catches "fake test systems" where a file is in the discovery glob and imports cleanly, but 0 of its tests ever ran, so the gate is green while assertions were never checked. Also covers unittest<->pytest runner migration.

## Core rule
Import/compile != execute. A test file that `python -m unittest <module>` accepts can still contribute ZERO executed tests. Always count the tests that actually RUN per file; never treat "the file is in the glob / imported / compiled" as "the tests ran."
WHY: `python -m unittest` discovers only `unittest.TestCase` subclasses. A module with only module-level `def test_*` functions imports fine, prints nothing, and runs 0 tests — the gate passes while every assertion is skipped.

## Classify file shapes before deciding anything
Four shapes, by AST:
- **TESTCASE** — has a TestCase subclass, no module-level test funcs. Runs under unittest.
- **FLAT_ONLY** — only module-level `def test_*`, no TestCase. Silent 0-execute no-op under `python -m unittest`; runs under pytest.
- **MIXED** — both. unittest runs only the class part; the flat part is skipped.
- **NO_TEST** — no test funcs at all (helper/config file).

Compare the gate's *reported* executed total against the AST count. If gate-executes < pytest-executes, the runner is silently dropping the flat files.

## Pitfalls
1. **Match both base forms.** Real classes are written `class X(unittest.TestCase)`, whose AST base is an `Attribute(attr="TestCase")`, not a bare `Name("TestCase")`. A classifier that only checks `base.id == "TestCase"` mislabels every real class-based file as FLAT_ONLY and invents a fake-system problem that isn't there. Match `Name("TestCase")` OR `Attribute(attr="TestCase")`.
2. **Decide the runner on the CI chain, not the bare interpreter.** When migrating the gate to pytest, confirm pytest is available where the gate actually runs (dependency lock + `uv run --frozen` / CI env), not just the shell you're in. A local "No module named pytest" is a setup-state gap, not proof CI can't run it. Run the decision experiment under the gate's reconstructed PYTHONPATH (its module roots) — flat test files often import from repo-root package dirs that the bare interpreter lacks on its path, so collection fails spuriously otherwise.
3. **A single unified runner often eliminates the fake-system class in one move.** pytest collects unittest.TestCase AND module-level `def test_*`. Switching the gate to one runner + one manifest is usually less invasive than rewriting dozens of FLAT_ONLY files into TestCase classes.
4. **BOM in source files.** A UTF-8 BOM (`U+FEFF`) at a `.py`'s start is accepted by the CPython byte-compiler but makes `ast.parse(open(...).read())` raise "invalid non-printable character U+FEFF". Read source with `encoding="utf-8-sig"` in any AST scanner; strip a stray BOM only if a real tool is failing on it, not as drive-by cleanup.

## Support
- `scripts/classify_test_shapes.py` — re-runnable AST probe: per .py in a dir, prints shape + how many tests unittest vs pytest would execute, and flags the "0-under-unittest but >0-under-pytest" fake-system files. Re-run after any test change and confirm the unittest-executes total equals what the gate reports.
