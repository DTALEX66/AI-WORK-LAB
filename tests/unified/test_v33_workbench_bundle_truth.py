# SPDX-License-Identifier: MIT
"""V33: the bytes the workbench JS gates read are the bytes these sources produce.

``apps/workbench/tests/unit.mjs``, ``appshell.mjs`` and ``shape-notice-coverage.mjs`` all read
one artifact, ``apps/workbench/build/main.js``. Measured on this tree: the bytes that were on disk
digested ``b465af83…`` while a fresh build of the same sources digests ``1a2d735c…``, and all three
gates passed on both. A gate that passes over stale bytes is not a gate -- and nothing upstream
could have caught it either, because the generic ``build/`` ignore rule copied into this repo
without the two negation lines that sat under it in the source repository demoted the audited
artifact to a file Git does not see.

So the face of this guard is three answers that must not collapse into each other:
the artifact invisible to Git (a defect), the artifact not yet committed (a defect), and the
build environment missing (``*_ABSENT``, exit 3 -- a named conclusion, never a green).
The stale-bytes plant itself is not here: it would have to rewrite a tracked artifact, and the
repo's falsifier script is where byte plants belong.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
TOOL = TARGET_ROOT / "scripts" / "check_workbench_bundle_drift.py"
RELPATH = "apps/workbench/build/main.js"


def run(repo: Path | None = None):
    argv = [sys.executable, "-B", "-X", "utf8", str(TOOL)]
    if repo is not None:
        argv += ["--repo-root", str(repo)]
    done = subprocess.run(argv, cwd=str(TARGET_ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return done.returncode, json.loads(done.stdout.strip().splitlines()[-1])


def _planted_repo(root: Path, *, gitignore: str | None, staged: bool) -> Path:
    """A repository whose only content is the artifact, so the Git-visibility classes are separable.

    ``VISIBLE_IGNORE`` carries both negation lines on purpose: a ``!`` over the file alone does
    nothing while its parent directory is still excluded, which is exactly the half-copy that made
    the artifact invisible in the first place.
    """
    root.mkdir(parents=True, exist_ok=True)
    (root / "apps/workbench/build").mkdir(parents=True)
    (root / "apps/workbench/build/main.js").write_bytes(b"// not a real bundle\n")
    if gitignore is not None:
        (root / ".gitignore").write_text(gitignore, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=str(root), capture_output=True, text=True)
    if staged:
        subprocess.run(["git", "add", RELPATH], cwd=str(root), capture_output=True, text=True)
    return root


BLANKET = "node_modules/\nbuild/\n"
#: One of the two negation lines, as a half-copy would leave it -- the parent directory stays
#: excluded, so the file is still invisible. This is the shape that shipped.
HALF_IGNORE = "node_modules/\nbuild/\n!apps/workbench/build/**\n"
VISIBLE_IGNORE = ("node_modules/\nbuild/\n!apps/workbench/build/\n!apps/workbench/build/**\n")


def test_committed_bundle_equals_a_fresh_offline_build():
    """The claim the two registers used to be unable to make: current sources, current bytes."""
    rc, receipt = run()
    assert rc == 0, receipt
    assert receipt["verdict"] == "MATCH", receipt
    assert receipt["tracked"] is True and receipt["ignored_by_rule"] is False, receipt
    assert receipt["committed_digest"] == receipt["rebuilt_digest"], receipt
    assert len(receipt["committed_digest"]) == 64, receipt


def test_an_ignore_rule_over_the_artifact_refusal(tmp_path):
    """Restoring the blanket ``build/`` rule -- the defect as it was shipped -- must go red.

    Red here is the whole point: an artifact Git cannot see cannot be staleness-checked by
    anything, which is why the gates stayed green over stale bytes. The half-copy counts too:
    negating only the file, while its parent directory stays excluded, re-includes nothing.
    """
    for name, gitignore in (("blanket", BLANKET), ("half-negation", HALF_IGNORE)):
        repo = _planted_repo(tmp_path / name, gitignore=gitignore, staged=False)
        rc, receipt = run(repo)
        assert rc == 1, (name, receipt)
        assert receipt["verdict"] == "IGNORED_ARTIFACT", (name, receipt)
        assert receipt["ignored_by_rule"] is True and receipt["tracked"] is False, receipt


def test_an_untracked_but_visible_artifact_refuses(tmp_path):
    """Visible to Git is not the same as committed: the negation alone does not restore the invariant."""
    repo = _planted_repo(tmp_path, gitignore=VISIBLE_IGNORE, staged=False)
    rc, receipt = run(repo)
    assert rc == 1, receipt
    assert receipt["verdict"] == "BUNDLE_UNTRACKED", receipt
    assert receipt["ignored_by_rule"] is False and receipt["tracked"] is False, receipt


def test_a_missing_build_environment_is_measurable_as_absent_not_green(tmp_path):
    """Exit 3 with a ``*_ABSENT`` verdict: refusing to claim what it did not check.

    Zero would be a fabricated pass and one would read as drift; only the third code can say
    "this machine cannot measure it" without pretending the artifact is fine.
    """
    repo = _planted_repo(tmp_path, gitignore=VISIBLE_IGNORE, staged=True)
    rc, receipt = run(repo)
    assert rc == 3, receipt
    assert receipt["verdict"].endswith("_ABSENT"), receipt
    assert receipt["verdict"] != "MATCH" and "rebuilt_digest" not in receipt, receipt
