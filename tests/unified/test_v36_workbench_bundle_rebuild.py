# SPDX-License-Identifier: MIT
"""V36: the committed workbench bundle really is these sources' output -- on a machine that can build.

This file is deliberately separate from ``test_v33_workbench_bundle_truth.py``: the claim it checks
needs a provisioned ``apps/workbench/node_modules`` (vite and its dependency closure), which a fresh
clone does not carry. test_v23's scan classifies it as machine-bound for exactly that reason, and
the same claim in a bare clone is not a pass or a skip -- ``check_workbench_bundle_drift.py`` answers
``NODE_ABSENT`` / ``VITE_ABSENT`` with exit 3, and those two classes are checked by the clone-safe
file. Splitting the files keeps the strong assertion strong instead of diluting it into an either/or.
The second node in this file needs an interpreter but not the real dependency closure: it plants a
``vite`` that fails, which is the other half of the same split -- what happens once a build runs.

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


def run(repo=None):
    argv = [sys.executable, "-B", "-X", "utf8", str(TOOL)]
    if repo is not None:
        argv += ["--repo-root", str(repo)]
    done = subprocess.run(argv, cwd=str(TARGET_ROOT), capture_output=True, text=True,
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


#: Prints a marker and exits non-zero, so the failure the gate reports is provably the failure
#: planted here rather than something that happened to be broken on the machine.
FAILING_VITE = ('process.stderr.write("PLANTED-BUILD-FAILURE\\n");\n'
                'process.exit(2);\n')


def _repo_with_a_vite_that_fails(root):
    """A committed artifact plus a ``node_modules/vite`` that cannot build -- and nothing else.

    The stub stands only for "the build ran and did not succeed": it is the one way to reach this
    branch without breaking the checkout, and it is never evidence that a build succeeded. The
    real-build claim is the node above, on the real toolchain.
    """
    build = root / "apps/workbench/build"
    build.mkdir(parents=True)
    (build / "main.js").write_bytes(b"// not a real bundle\n")
    stub = root / "apps/workbench/node_modules/vite"
    (stub / "bin").mkdir(parents=True)
    (stub / "package.json").write_text('{"name": "vite", "version": "0.0.0-stub"}',
                                       encoding="utf-8")
    (stub / "bin/vite.js").write_text(FAILING_VITE, encoding="utf-8")
    for argv in (["init", "-q"], ["add", "-A"],
                 ["-c", "user.name=plant", "-c", "user.email=plant@example.invalid",
                  "commit", "-q", "-m", "planted a vite that fails"]):
        subprocess.run(["git", *argv], cwd=str(root), capture_output=True, text=True, check=True)
    return root


def test_a_build_that_does_not_succeed_refuses_instead_of_comparing_stale_bytes(tmp_path):
    """``BUILD_FAILED`` has to be reachable, or the gate's own error path is a rumour.

    Before this node the branch had never been taken anywhere in the repo: nine of the tool's ten
    named outcomes were asserted, and this one was only printed in a docstring. A build that exits
    non-zero -- or exits zero without producing the artifact -- must refuse with rc=1 and carry the
    stderr it saw, because the alternative is reaching ``rebuilt_digest = None`` and calling the
    comparison something it is not.
    """
    repo = _repo_with_a_vite_that_fails(tmp_path)
    rc, receipt = run(repo)
    assert rc == 1, receipt
    assert receipt["verdict"] == "BUILD_FAILED", receipt
    assert receipt["build_rc"] == 2, receipt
    assert "rebuilt_digest" not in receipt, receipt
    assert "PLANTED-BUILD-FAILURE" in " ".join(receipt["stderr_tail"]), receipt


