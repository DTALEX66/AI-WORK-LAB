"""Is the committed workbench bundle the bytes these sources produce?

Three JS gates (``apps/workbench/tests/unit.mjs``, ``appshell.mjs``,
``shape-notice-coverage.mjs``) read ``apps/workbench/build/main.js``, so the artifact they
validate *is* the claim. Measured here: the previous bytes on disk digested
``b465af83…`` while a fresh build of the same sources digests ``1a2d735c…``, and all three
gates went green on both. They cannot tell stale from current, and nothing else could either,
because the fused repo's generic ``build/`` ignore rule -- copied from the source repo without
the two negation lines that sat under it there -- made the artifact invisible to Git. An
artifact Git does not see is an artifact no diff can staleness-check.

So this tool checks the three things that were each silently untrue:
  * Git can see the file (``IGNORED_ARTIFACT`` / ``BUNDLE_UNTRACKED``);
  * the build runs offline at all (``NODE_ABSENT`` / ``VITE_ABSENT`` / ``BUILD_FAILED``);
  * the bytes in HEAD equal what the current sources produce (``MATCH`` / ``DRIFT``, and
    ``UNCOMMITTED_BYTES`` when they do but the file on disk -- the one the gates read -- was
    hand-edited since; ``COMMIT_BLOB_ABSENT`` when HEAD has nothing to compare against).

One JSON document on stdout. Exit codes: 0 ``MATCH``, 1 a real refusal, 2 usage, 3 the
environment cannot measure it -- which is a named conclusion, never a silent pass.

Run:  .venv/Scripts/python.exe -B -X utf8 scripts/check_workbench_bundle_drift.py
      --repo-root <copy-of-the-repo>   (relocate the subject, for falsifiers)
"""
import argparse
import hashlib
import json
import shutil
import subprocess
import sys
import time
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELPATH = "apps/workbench/build/main.js"


def git(args, cwd):
    return subprocess.run(["git"] + args, cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def emit(document, rc):
    print(json.dumps(document, ensure_ascii=True, sort_keys=True))
    return rc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--repo-root", default=None,
                        help="repo whose Git visibility is judged (a falsifier points it at a copy)")
    args = parser.parse_args()

    repo = Path(args.repo_root).resolve() if args.repo_root else ROOT
    workbench = repo / "apps/workbench"
    bundle = workbench / "build/main.js"
    started = time.time()
    document = {"relpath": RELPATH, "bundle_exists": bundle.is_file()}

    ignored = git(["check-ignore", "--no-index", "-q", RELPATH], repo).returncode == 0
    tracked = git(["ls-files", "--error-unmatch", RELPATH], repo).returncode == 0
    document["ignored_by_rule"] = ignored
    document["tracked"] = tracked
    if ignored and not tracked:
        document["verdict"] = "IGNORED_ARTIFACT"
        document["why"] = ("an ignore rule hides the artifact the JS gates read; nothing can "
                           "staleness-check what Git does not see")
        return emit(document, 1)
    if not tracked:
        document["verdict"] = "BUNDLE_UNTRACKED"
        document["why"] = "the artifact is visible to Git but not committed"
        return emit(document, 1)

    if not bundle.is_file():
        document["verdict"] = "BUNDLE_ABSENT"
        document["why"] = "no bytes on disk for the JS gates to read"
        return emit(document, 1)
    document["working_tree_digest"] = digest(bundle)
    # the audited claim is about the COMMITTED artifact, so read the committed blob itself:
    # hashing the working-tree file under this name is what let a hand-edited bundle pass as
    # "verified bytes" (found by the independent review, not by me)
    shown = subprocess.run(["git", "show", "HEAD:" + RELPATH], cwd=str(repo), capture_output=True)
    if shown.returncode != 0:
        document["verdict"] = "COMMIT_BLOB_ABSENT"
        document["why"] = "visible to Git, but HEAD carries no such blob: nothing committed to verify"
        return emit(document, 3)
    document["committed_digest"] = hashlib.sha256(shown.stdout).hexdigest()
    document["working_tree_equals_commit"] = (document["working_tree_digest"]
                                              == document["committed_digest"])

    node = shutil.which("node")
    vite = workbench / "node_modules/vite/bin/vite.js"
    document["node"] = node
    document["vite_cli_present"] = vite.is_file()
    if node is None:
        document["verdict"] = "NODE_ABSENT"
        return emit(document, 3)
    if not vite.is_file():
        document["verdict"] = "VITE_ABSENT"
        document["why"] = "vite is declared in package.json but not provisioned in node_modules"
        return emit(document, 3)
    package = json.loads((workbench / "node_modules/vite/package.json").read_text(encoding="utf-8"))
    document["vite_version"] = package.get("version")

    out_dir = repo / (".project-local/runs/workbench-drift-%s" % uuid.uuid4().hex[:8])
    try:
        build = subprocess.run([node, str(vite), "build", "--outDir", str(out_dir), "--emptyOutDir"],
                               cwd=str(workbench), capture_output=True, text=True,
                               encoding="utf-8", errors="replace")
        rebuilt = out_dir / "main.js"
        rebuilt_digest = digest(rebuilt) if rebuilt.is_file() else None
    finally:
        shutil.rmtree(out_dir, ignore_errors=True)
    if build.returncode != 0 or rebuilt_digest is None:
        document["verdict"] = "BUILD_FAILED"
        document["build_rc"] = build.returncode
        document["stderr_tail"] = (build.stderr or "").strip().splitlines()[-3:]
        return emit(document, 1)
    document["rebuilt_digest"] = rebuilt_digest
    if rebuilt_digest != document["committed_digest"]:
        document["verdict"] = "DRIFT"
        document["why"] = ("the committed artifact is not what these sources produce -- the gates "
                           "would be validating old bytes")
    elif not document["working_tree_equals_commit"]:
        document["verdict"] = "UNCOMMITTED_BYTES"
        document["why"] = ("HEAD's artifact does match the sources, but the bytes on disk -- the ones "
                           "the JS gates read -- are somebody's uncommitted edit")
    else:
        document["verdict"] = "MATCH"
    document["elapsed_ms"] = int((time.time() - started) * 1000)
    return emit(document, 0 if document["verdict"] == "MATCH" else 1)


if __name__ == "__main__":
    sys.exit(main())
