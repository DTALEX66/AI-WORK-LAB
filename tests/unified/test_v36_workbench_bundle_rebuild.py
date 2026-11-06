# SPDX-License-Identifier: MIT
"""V36: the committed workbench bundle really is these sources' output -- on a machine that can build.

This file is deliberately separate from ``test_v33_workbench_bundle_truth.py``: the claim it checks
needs a provisioned ``apps/workbench/node_modules`` (vite and its dependency closure), which a fresh
clone does not carry. test_v23's scan classifies it as machine-bound for exactly that reason, and
the same claim in a bare clone is not a pass or a skip -- ``check_workbench_bundle_drift.py`` answers
``NODE_ABSENT`` / ``VITE_ABSENT`` with exit 3, and those two classes are checked by the clone-safe
file. Splitting the files keeps the strong assertion strong instead of diluting it into an either/or.

The assertion itself: build the bundle a second time from these sources into a throwaway outDir and
require the digest to equal the digest of the blob HEAD carries.
"""
from __future__ import annotations

import json
import pathlib
import subprocess
import sys

TARGET_ROOT = pathlib.Path(__file__).resolve().parents[2]
TOOL = TARGET_ROOT / "scripts" / "check_workbench_bundle_drift.py"


def run():
    done = subprocess.run([sys.executable, "-B", "-X", "utf8", str(TOOL)],
                          cwd=str(TARGET_ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])


def test_committed_bundle_equals_a_fresh_offline_build():
    """The claim the two registers used to be unable to make: current sources, current bytes.

    ``working_tree_equals_commit`` is asserted too, because the gates read the file on disk: an
    uncommitted edit to the artifact is a refusal even when HEAD's blob is perfectly rebuilt. The
    digest named ``committed_digest`` comes from ``git show HEAD:...``, not from the working tree
    -- the independent review caught this file hashing the tree and calling it the commit.
    """
    rc, receipt = run()
    assert rc == 0, receipt
    assert receipt["verdict"] == "MATCH", receipt
    assert receipt["tracked"] is True and receipt["ignored_by_rule"] is False, receipt
    assert receipt["working_tree_equals_commit"] is True, receipt
    assert receipt["committed_digest"] == receipt["rebuilt_digest"], receipt
    assert len(receipt["committed_digest"]) == 64, receipt


