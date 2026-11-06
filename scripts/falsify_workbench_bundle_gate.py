"""Every verdict ``check_workbench_bundle_drift.py`` can name is put in front of it, here.

Why this file is tracked while the rest of a batch's probes are not: the bundle gate reported
``MATCH`` over stale bytes for a whole batch, and the fix that followed could itself rot in exactly
the same way -- the tool grew ten named outcomes and only three of them had ever been observed by
anything (measured this batch, not assumed). A one-shot script under ``.project-local`` proves that
reading once; it cannot prove the *set* stays covered, because nobody can run it from a clone.

So this script is the reproducible form, and it publishes its own coverage in ``VERDICT_CASES``:
``test_v33_workbench_bundle_truth.py`` compares that set against the verdict literals the tool can
actually assign, so adding an eleventh name without putting it in front of the gate turns that node
red. The in-suite nodes cover what a repository state alone can reach; the two classes that need a
byte plant in *this* checkout (``DRIFT``, ``UNCOMMITTED_BYTES``) are applied here to tracked files
and restored from the bytes saved at the start, verified by digest -- which is why they are a script
and not a test.

What each case claims, in the tool's own words:

  IGNORED_ARTIFACT / BUNDLE_UNTRACKED / BUNDLE_ABSENT / COMMIT_BLOB_ABSENT
      four Git-visibility states, planted as throwaway repositories.
  NODE_ABSENT / VITE_ABSENT
      the runtime or the bundler is not reachable. ``NODE_ABSENT`` drops every PATH entry that
      provides a node binary -- this machine has two node installs, and removing only the one
      ``shutil.which`` picks leaves a plant that tests the edit rather than the absence.
  BUILD_FAILED
      a stub ``vite.js`` that exits non-zero and prints a marker. It proves the gate's error path
      is reachable and refuses; it is never evidence that a build succeeded -- that claim is
      ``test_v36``'s real offline build.
  DRIFT / UNCOMMITTED_BYTES
      real bytes in this checkout, edited and restored.
  MATCH
      the baseline, before any plant.

Exit 0 only when every name above was observed with the expected verdict *and* rc, and the checkout
ended where it started. Exit 1 names what did not match.

Run:  .venv/Scripts/python.exe -B -X utf8 scripts/falsify_workbench_bundle_gate.py
"""
from __future__ import annotations

import hashlib
import json
import os
import pathlib
import shutil
import stat
import subprocess
import sys
import tempfile

ROOT = pathlib.Path(__file__).resolve().parents[1]
TOOL = ROOT / "scripts/check_workbench_bundle_drift.py"
SOURCE = ROOT / "apps/workbench/shell.ts"
BUNDLE = ROOT / "apps/workbench/build/main.js"
PYTHON = sys.executable
RELPATH = "apps/workbench/build/main.js"
BUNDLE_BYTES = b"// not a real bundle\n"
#: A build that runs and does not succeed. The marker proves the stderr the gate carries is the
#: stderr this fixture produced.
FAILING_VITE = ('process.stderr.write("PLANTED-BUILD-FAILURE\\n");\nprocess.exit(2);\n')
OK_VITE = "process.exit(0);\n"

#: verdict -> the rc the tool must answer with. Read by the in-suite guard as this script's own
#: coverage claim; do not treat an entry here as a claim that the checkout is in that state.
VERDICT_CASES = {
    "MATCH": 0,
    "IGNORED_ARTIFACT": 1,
    "BUNDLE_UNTRACKED": 1,
    "BUNDLE_ABSENT": 1,
    "COMMIT_BLOB_ABSENT": 3,
    "NODE_ABSENT": 3,
    "VITE_ABSENT": 3,
    "BUILD_FAILED": 1,
    "DRIFT": 1,
    "UNCOMMITTED_BYTES": 1,
}


def git(cwd, *args):
    done = subprocess.run(["git", *args], cwd=str(cwd), capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    assert done.returncode == 0, (args, done.returncode, (done.stderr or "")[-400:])


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_tool(repo=None, drop_node=False):
    env = dict(os.environ)
    if drop_node:
        gone = {p.casefold() for p in _path_entries_providing("node")}
        env["PATH"] = os.pathsep.join(
            p for p in os.environ.get("PATH", "").split(os.pathsep)
            if p and p.casefold() not in gone)
        # both halves have to hold at once, or the verdict printed is about neither: the runtime
        # gone, and the git the gate shells out to still reachable
        assert shutil.which("node", path=env["PATH"]) is None, "node survived the PATH filter"
        assert shutil.which("git", path=env["PATH"]), "the PATH filter also removed git"
    argv = [PYTHON, "-B", "-X", "utf8", str(TOOL)]
    if repo is not None:
        argv += ["--repo-root", str(repo)]
    done = subprocess.run(argv, cwd=str(ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=env)
    lines = [l for l in (done.stdout or "").strip().splitlines() if l.strip()]
    document = json.loads(lines[-1]) if lines else {"verdict": "NO_JSON"}
    return done.returncode, document


def _path_entries_providing(binary):
    out = []
    for entry in os.environ.get("PATH", "").split(os.pathsep):
        if not entry:
            continue
        directory = pathlib.Path(entry)
        try:
            kids = [k.name for k in directory.iterdir()] if directory.is_dir() else []
        except OSError:
            continue
        if any(k.lower().startswith(binary.lower())
               and k.lower().endswith((".exe", ".cmd", ".bat")) for k in kids):
            out.append(entry)
    return out


def remove_repo(path):
    """Delete a fixture repository, and refuse to do it quietly.

    Git writes its object pack read-only, and ``rmtree(ignore_errors=True)`` walks past those and
    returns success with the tree still on disk -- measured on this script's first run, where each
    survivor was half a gigabyte. A leftover ``bb-*`` repo is how a later clean-up reading counts
    somebody else's fixture, so the read-only bit is cleared and the caller asserts the path is gone.
    """
    def clear(func, target, exc):
        os.chmod(target, stat.S_IWRITE)
        func(target)
    shutil.rmtree(path, onerror=clear)


def _planted(tmp, *, state, gitignore=None, vite=None):
    git(tmp, "init", "-q")
    (tmp / "README.md").write_text("planted\n", encoding="utf-8")
    git(tmp, "add", "README.md")
    git(tmp, "-c", "user.name=plant", "-c", "user.email=plant@example.invalid",
        "commit", "-q", "-m", "planted: HEAD exists without the artifact")
    if gitignore is not None:
        (tmp / ".gitignore").write_text(gitignore, encoding="utf-8")
    build = tmp / "apps/workbench/build"
    build.mkdir(parents=True)
    (tmp / "apps/workbench/shell.ts").write_text("export const plant = 1;\n", encoding="utf-8")
    bundle = build / "main.js"
    bundle.write_bytes(BUNDLE_BYTES)
    if vite is not None:
        stub = tmp / "apps/workbench/node_modules/vite"
        (stub / "bin").mkdir(parents=True)
        (stub / "package.json").write_text(json.dumps({"name": "vite", "version": "0.0.0-stub"}),
                                           encoding="utf-8")
        (stub / "bin/vite.js").write_text(vite, encoding="utf-8")
    if state in ("committed", "committed_then_deleted", "staged"):
        git(tmp, "add", "--", RELPATH)
        if state != "staged":
            git(tmp, "-c", "user.name=plant", "-c", "user.email=plant@example.invalid",
                "commit", "-q", "-m", "planted artifact")
        if state == "committed_then_deleted":
            bundle.unlink()
    return tmp


BLANKET = "node_modules/\nbuild/\n"
VISIBLE_IGNORE = ("node_modules/\nbuild/\n!apps/workbench/build/\n!apps/workbench/build/**\n")

#: name -> (expected verdict, kwargs for ``_planted``, whether node must be hidden)
REPO_CASES = {
    "IGNORED_ARTIFACT": ("IGNORED_ARTIFACT", dict(state="untracked", gitignore=BLANKET), False),
    "BUNDLE_UNTRACKED": ("BUNDLE_UNTRACKED", dict(state="untracked", gitignore=VISIBLE_IGNORE),
                         False),
    "BUNDLE_ABSENT": ("BUNDLE_ABSENT", dict(state="committed_then_deleted",
                                            gitignore=VISIBLE_IGNORE), False),
    "COMMIT_BLOB_ABSENT": ("COMMIT_BLOB_ABSENT", dict(state="staged", gitignore=VISIBLE_IGNORE),
                           False),
    "NODE_ABSENT": ("NODE_ABSENT", dict(state="committed", gitignore=VISIBLE_IGNORE, vite=OK_VITE),
                    True),
    "VITE_ABSENT": ("VITE_ABSENT", dict(state="committed", gitignore=VISIBLE_IGNORE), False),
    "BUILD_FAILED": ("BUILD_FAILED", dict(state="committed", gitignore=VISIBLE_IGNORE,
                                          vite=FAILING_VITE), False),
}


def byte_plant(label, path, mutate, want):
    """Edit a tracked file, read the verdict, restore -- and prove the restore by digest."""
    original = path.read_bytes()
    try:
        path.write_bytes(mutate(original))
        rc, document = run_tool()
        ok = document.get("verdict") == want and rc == VERDICT_CASES[want]
        print("%-20s verdict=%-20s rc=%-3s expect=%s/%s -> %s"
              % (label, document.get("verdict"), rc, want, VERDICT_CASES[want],
                 "OK" if ok else "WRONG"))
        return ok
    finally:
        path.write_bytes(original)
        assert sha(path) == hashlib.sha256(original).hexdigest(), "restore failed: " + label


def _edit_nav_array(data: bytes) -> bytes:
    """Add one entry to a declared navigation array -- a change that must reach the bundle.

    A comment would be the obvious plant and the wrong one: esbuild may drop it, and then "source
    edited" would report ``MATCH``, which the tool is only allowed to mean "rebuilt from these
    sources".
    """
    needle = b"'settings'];"
    assert data.count(needle) == 1, "plant needle no longer unique in shell.ts: %d" % data.count(needle)
    return data.replace(needle, b"'settings', 'awl-plant'];")


def main() -> int:
    observed = {}
    rc, baseline = run_tool()
    print("%-20s verdict=%-20s rc=%-3s -> %s" % ("MATCH(baseline)", baseline.get("verdict"), rc,
                                                 "OK" if rc == 0 and baseline.get("verdict")
                                                 == "MATCH" else "WRONG"))
    observed["MATCH"] = rc == 0 and baseline.get("verdict") == "MATCH"

    base = pathlib.Path(tempfile.mkdtemp(prefix="awl-bundle-falsify-"))
    try:
        for name, (want, kwargs, hide_node) in REPO_CASES.items():
            tmp = pathlib.Path(tempfile.mkdtemp(prefix="bb-", dir=str(base)))
            try:
                _planted(tmp, **kwargs)
                rc, document = run_tool(repo=tmp, drop_node=hide_node)
                ok = document.get("verdict") == want and rc == VERDICT_CASES[want]
                if ok and want == "BUILD_FAILED":
                    ok = "PLANTED-BUILD-FAILURE" in " ".join(document.get("stderr_tail") or [])
                print("%-20s verdict=%-20s rc=%-3s expect=%s/%s -> %s"
                      % (name, document.get("verdict"), rc, want, VERDICT_CASES[want],
                         "OK" if ok else "WRONG"))
                observed[name] = ok
            finally:
                remove_repo(tmp)
                assert not tmp.exists(), "fixture repo survived: " + str(tmp)
    finally:
        remove_repo(base)

    observed["DRIFT"] = byte_plant("DRIFT", SOURCE, _edit_nav_array, "DRIFT")
    observed["UNCOMMITTED_BYTES"] = byte_plant(
        "UNCOMMITTED_BYTES", BUNDLE, lambda data: data + b"\n// planted stale bytes\n",
        "UNCOMMITTED_BYTES")

    rc, after = run_tool()
    restored = rc == 0 and after.get("verdict") == "MATCH"
    print("checkout restored to MATCH: %s" % ("OK" if restored else "WRONG"))
    missing = sorted(name for name, ok in observed.items() if not ok)
    undeclared = sorted(set(VERDICT_CASES) - set(observed))
    print("observed %d/%d; declared but not run: %s"
          % (len(observed) - len(missing), len(observed), undeclared or "none"))
    if missing or undeclared or not restored:
        print("FAILED: " + ", ".join(missing + undeclared + (["not-restored"] if not restored
                                                             else [])))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
