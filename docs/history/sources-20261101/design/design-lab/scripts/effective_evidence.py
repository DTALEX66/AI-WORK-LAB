#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Recorded vs effective capability evidence (P1-B, DL-EVD-002/003).

A recorded evidence level is a historical observation, bound to the tree where it
was produced. It must never satisfy the floor of the *current* tree: a green run
on another SHA is not evidence for this checkout. This module keeps the two axes
apart:

- the recording stays in ``design-lab/config/capability-evidence-index.json``
  untouched (it documents what was once observed, and requalification is flagged,
  not erased);
- the effective level is computed here for a current SHA, and only the effective
  level may be compared against ``minimumRequiredEvidence``.

Pure stdlib, deterministic: no clock, no network, no state beyond the index read.
"""
from __future__ import annotations

import json
from pathlib import Path

LEVEL = {"E0": 0, "E1": 1, "E2": 2, "E3": 3, "E4": 4, "E5": 5}
STRUCTURAL_FLOOR = "E1"
INDEX_PARTS = ("design-lab", "config", "capability-evidence-index.json")


def effective_evidence(record, current_sha, structural_pass):
    """Return the evidence level the record may claim on the current tree.

    ``recorded`` (``record["evidenceLevel"]``) is the historical claim. It is
    downgraded to the structural ceiling when requalification is required, or when
    the record binds a subject SHA other than the current one. ``structural_pass``
    says whether the capability still passes its structural (E1) checks on this
    tree, so the best a stale runtime claim may keep is E1 -- and E0 when even the
    structural layer is unproven. Otherwise the recorded level stands as-is.
    """
    recorded = record.get("evidenceLevel")
    if record.get("requiresRequalification"):
        return STRUCTURAL_FLOOR if structural_pass else "E0"
    subject_sha = record.get("subjectSha")
    if subject_sha is not None and subject_sha != current_sha:
        return STRUCTURAL_FLOOR if structural_pass else "E0"
    return recorded


def structural_pass_from_recorded(recorded):
    """Deterministic structural-pass proxy for a recorded level.

    A recording at or above E1 means the structural checks passed when it was
    written. E0 -- or an unknown/missing level -- proves no structural pass, so a
    requalified capability must fall to E0 rather than keep a borrowed E1.
    """
    return LEVEL.get(recorded, -1) >= LEVEL[STRUCTURAL_FLOOR]


def meets_floor(level, floor):
    """``LEVEL[level] >= LEVEL[floor]``; fails closed on unknown levels/floors."""
    if level not in LEVEL or floor not in LEVEL:
        return False
    return LEVEL[level] >= LEVEL[floor]


def index_path(repo):
    """Resolve the evidence index from either the repo root or design-lab/."""
    repo = Path(repo)
    direct = repo.joinpath(*INDEX_PARTS)
    if direct.is_file():
        return direct
    return repo / "config" / "capability-evidence-index.json"


def load_index(repo):
    """Read the capability evidence index (raises on unreadable/invalid input)."""
    path = index_path(repo)
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"capability evidence index must be a JSON object: {path}")
    return data


def requalified(index):
    """``{capability_id: True}`` for every capability flagged requiresRequalification.

    These capabilities keep only their structural ceiling on the current tree until
    a runtime requalification re-binds them to a fresh subject SHA.
    """
    flagged: dict[str, bool] = {}
    capabilities = index.get("capabilities", []) if isinstance(index, dict) else []
    if not isinstance(capabilities, list):
        return flagged
    for capability in capabilities:
        if not isinstance(capability, dict):
            continue
        if capability.get("requiresRequalification") is True:
            capability_id = capability.get("id")
            if isinstance(capability_id, str) and capability_id:
                flagged[capability_id] = True
    return flagged
