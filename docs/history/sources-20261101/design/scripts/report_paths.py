#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Print a report path without assuming the report lives inside the repository.

Owner audit 2026-10-26, finding 7: `scripts/audit_workbench_ui.py` wrote its JSON and then did
`out_path.relative_to(REPO)` while printing, so pointing `--out` (or `E2E_EVIDENCE_DIR`) at any
directory outside the checkout raised `ValueError` AFTER a successful scan -- the measurement was
fine and the run still died. The same shape sat in two places in `run_design_review_plugin.py`.
"""
from __future__ import annotations

from pathlib import Path


def display_path(path: Path, repo: Path) -> str:
    """Repo-relative when it genuinely is, absolute when it is not. Never raises."""
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(Path(repo).resolve()).as_posix()
    except ValueError:
        return resolved.as_posix()
