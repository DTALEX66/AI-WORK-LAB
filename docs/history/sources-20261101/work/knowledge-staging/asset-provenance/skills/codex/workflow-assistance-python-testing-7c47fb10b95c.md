---
name: workflow-assistance-python-testing
version: 1.0.0
author: "UNKNOWN"
license: UNKNOWN
platforms: [windows, linux, macos]
workflow_software: codex
archived_at: 2026-08-21
source_path: D:/All projects/WORK-LAB/10-workflow/workflow-assistance/codex-assets/skills/workflow-assistance-python-testing/SKILL.md
---

---
name: workflow-assistance-python-testing
description: "Use when writing, changing, debugging, or running Python tests with unittest, pytest, virtual environments, or Windows path constraints."
---

# Python testing

- Inspect `pyproject.toml`, lock files, test configuration, neighboring tests, and the actual interpreter before choosing commands.
- On Windows, distinguish `python`, `python3`, `pip`, and project virtual environments; do not assume they point to the same interpreter.
- Before running an optional format lane, use the read-only preflight with the
  intended interpreter and modules, for example `python
  scripts/workflow/execution_preflight.py --project . --require-module
  pdfminer --require-module pdfplumber`. Record the exact executable. Missing
  modules in a non-project venv are environment failures, not product failures.
- For new behavior or a bug fix, write a focused failing test, observe the expected failure, implement the minimum fix, and rerun it.
- Use real filesystem and process behavior when practical; avoid tests that only prove mock configuration.
- Put temporary environments and caches inside the project runtime boundary.
- Run the smallest targeted test first. Broaden according to the project's risk
  policy, then run the canonical gate once on the final aggregate tree rather
  than after every mechanical edit.
- Report skipped tests and warnings separately; do not hide them inside a pass count.
