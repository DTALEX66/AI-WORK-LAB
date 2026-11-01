"""Pytest bootstrap: expose the converged module layout to all tests.

After the WL-DIR migration the workflow modules moved out of
the legacy numbered layout into domain directories
(services/*, packages/client-neutral-core/scripts, integrations/executors/*).
Legacy test files still insert ``ROOT / "scripts/workflow"``; this conftest
adds the real module roots so their imports resolve without editing 100+ files.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

_MODULE_ROOTS = [
    "services/authority",
    "services/orchestration",
    "services/policy",
    "services/receipts",
    "packages/client-neutral-core/scripts",
    "integrations/executors/codex",
    "integrations/executors/hermes",
    "integrations/executors/dsh",
]

for rel in _MODULE_ROOTS:
    p = ROOT / rel
    if p.is_dir():
        sys.path.insert(0, str(p))
