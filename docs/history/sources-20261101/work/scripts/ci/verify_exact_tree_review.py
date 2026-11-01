#!/usr/bin/env python3
"""NX-720 exact-tree review verifier."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts" / "ci"))

from exact_tree_review import ACTIVE_MODULES, REQUIRED_TASKS, review_tree  # noqa: E402


def verify() -> dict[str, object]:
    report = review_tree()
    assert report["head"] == report["originMain"], "local main must equal origin/main"
    assert report["worktreeClean"] is True
    assert report["trackedFiles"] > 0
    assert len(report["trackedTreeDigest"]) == 64
    assert all(report["activeModulePresence"].values())
    assert report["transferredScopeTracked"] == []
    assert report["forbiddenTrackedPaths"] == []
    assert all(report["taskStatus"][task] == "COMPLETED" for task in REQUIRED_TASKS)
    assert all(report["requiredHandoffsPresent"])
    assert all(report["requiredVerifiersPresent"].values())
    assert report["ciWorkflowPresent"] is True
    assert report["reviewerMode"] == "READ_ONLY"
    assert report["credentialContentsRead"] is False
    assert report["externalWrites"] is False
    return report


def main() -> int:
    try:
        report = verify()
    except (AssertionError, KeyError, OSError, ValueError) as exc:
        print(f"EXACT_TREE_REVIEW_FAIL {exc}")
        return 1
    print(
        "EXACT_TREE_REVIEW_PASS "
        f"head={report['head'][:8]} tracked_files={report['trackedFiles']} "
        f"tree_digest={report['trackedTreeDigest'][:16]} modules=2 tasks={len(REQUIRED_TASKS)} "
        "forbidden=0 transferred=0 reviewer=read_only release=approval_pending"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
