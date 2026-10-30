# SPDX-License-Identifier: MIT
"""Central reconstruction runtime-root resolver (DL-TP-R0-003 / PR115-F06).

All reconstruction run/evidence/cache/tmp/lock writes resolve through this
module. The canonical runtime root is PROJECT_LOCAL_ROOT (.project-local/);
legacy .hermes roots are never produced by mainline code. Module-level
constants exist so contract validation, packaging, rollback and tests agree on
one root vocabulary.
"""
from __future__ import annotations

from pathlib import Path
import sys

PROJECT_ROOT = Path(__file__).resolve().parents[3]
# Compatibility bootstrap for the pre-installable reconstruction entrypoints.
# R3-09 will expose the same package through installation, not a second resolver.
if str(PROJECT_ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT / 'src'))
from design_lab.runtime.paths import resolve_paths

_PATHS = resolve_paths(project_root=PROJECT_ROOT)
PROJECT_LOCAL_ROOT = _PATHS.local_root

# Canonical reconstruction namespace under .project-local/ (trailing-slash
# repo-relative strings used by run contracts and the evidence bundle).
RUNTIME_REL = (_PATHS.runtime_root / 'reconstruction').relative_to(PROJECT_ROOT).as_posix()
EVIDENCE_REL = (_PATHS.evidence_root / 'reconstruction').relative_to(PROJECT_ROOT).as_posix()

# Legacy roots that must never be produced by active mainline code (R0-003).
LEGACY_RUNTIME_REL = ".hermes/task-runtime/reconstruction"
LEGACY_EVIDENCE_REL = ".hermes/task-artifacts/reconstruction"

RUNTIME_PARENT = PROJECT_LOCAL_ROOT / "task-runtime" / "reconstruction"
EVIDENCE_PARENT = PROJECT_LOCAL_ROOT / "task-artifacts" / "reconstruction"


def runtime_root(run_id: str) -> str:
    """Repo-relative trailing-slash runtime root for one run id."""
    return _PATHS.task_dir('reconstruction', run_id).relative_to(PROJECT_ROOT).as_posix() + '/'


def evidence_root(run_id: str) -> str:
    """Repo-relative trailing-slash evidence root for one run id."""
    return _PATHS.task_dir('reconstruction', run_id, evidence=True).relative_to(PROJECT_ROOT).as_posix() + '/'
