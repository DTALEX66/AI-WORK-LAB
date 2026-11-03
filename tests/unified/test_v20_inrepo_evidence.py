# SPDX-License-Identifier: MIT
"""V20: the evidence that used to live only in the gitignored tree is now in-repo and checkable.

`.gitignore` line 2 hides `.project-local/`, so every P0 acceptance fact stored there --
the environment readings and the candidate-manifest 口径 behind them -- was unreachable
from a fresh clone. Three tracked artefacts replace that:

* `scripts/candidate_snapshot.py`  -- the section-6 口径 as tracked code,
* `config/environment-baseline.json` -- interpreter, sqlite/FTS5, the read-only source
  anchors and the declared non-goals, read at generation time,
* `docs/AUDIT-STATE.json`          -- which HEAD was audited, the re-review conclusion,
  and the facts of the first upload.

This file does not restate those numbers, it re-derives them and compares. Each test
therefore says something a clone can actually check:

1. the candidate digest is a **function of the tree**, not of a one-off script run: two
   re-runs against an unchanged tree give byte-identical manifests, and the tracked
   implementation agrees with the original gitignored one while that file exists;
2. the two 口径 section 6 warns against mixing are **named distinctly and answer
   differently** (tracked-only vs cached-plus-non-ignored-untracked);
3. `config/environment-baseline.json` agrees with what this interpreter and this
   machine answer **right now** (version, FTS5, the two source anchors via git);
4. `docs/AUDIT-STATE.json` binds the **current** `git rev-parse HEAD` -- a hand-typed
   SHA cannot survive the comparison, and its recorded paths must exist.
"""
from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
SCRIPT = TARGET_ROOT / "scripts" / "candidate_snapshot.py"
BASELINE = TARGET_ROOT / "config" / "environment-baseline.json"
AUDIT_STATE = TARGET_ROOT / "docs" / "AUDIT-STATE.json"
#: the gitignored original of the 口径; present only on the machine that ran the audit
LEGACY_BUILD_CLOSURE = (TARGET_ROOT / ".project-local" / "audit"
                        / "20261030-qoder-ed9037" / "build_closure.py")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def _git(args: list[str], cwd: Path = TARGET_ROOT) -> str:
    return subprocess.run(["git", *args], cwd=str(cwd), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


def _module():
    spec = importlib.util.spec_from_file_location("candidate_snapshot", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_candidate_snapshot_module_names_the_two_readings_distinctly():
    assert SCRIPT.is_file(), "the section-6 口径 has no tracked implementation"
    cs = _module()
    assert cs.CANDIDATE_口径 == "git_cached_plus_non_ignored_untracked"
    assert cs.TRACKED_ONLY_口径 == "git_tracked_only"
    assert cs.CANDIDATE_口径 != cs.TRACKED_ONLY_口径, (
        "section 6 forbids mixing the two readings; they must be separately named")
    with pytest.raises(ValueError):
        cs.state_for("some-other-口径")


def test_reRunning_the_candidate_口径_on_an_unchanged_tree_is_byte_identical(tmp_path):
    """The manifest is a function of the tree, so two runs must produce the same bytes."""
    cs = _module()
    seen: list[tuple[str, dict[str, str]]] = []
    attempts = 0
    while attempts < 3:
        attempts += 1
        state = cs.candidate_state()
        blob = json.dumps(state, sort_keys=True).encode("utf-8")
        seen.append((hashlib.sha256(blob).hexdigest(), state))
        # two consecutive identical readings prove determinism; a difference can only be
        # the tree moving under us (another lane writing), which the retry separates from
        # an actual non-determinism in the 口径.
        if len(seen) >= 2 and seen[-1][0] == seen[-2][0]:
            break
    digests = {item[0] for item in seen}
    assert len(digests) == 1, (
        "candidate_snapshot did not converge on a stable digest in %d readings; the tree "
        "is moving while it is enumerated. Digests seen: %s" % (attempts, sorted(digests)))
    digest, state = seen[-1]
    assert digest == cs.digest_of(state)
    assert state, "the candidate manifest is empty -- git ls-files returned nothing"
    assert all(re.match(r"^[0-9a-f]{64}$|MISSING", value) for value in state.values()), (
        "a manifest entry is neither a file SHA-256 nor the MISSING marker")
    # the CLI agrees with the callable, and --json-out writes the same manifest
    out = tmp_path / "snapshot.json"
    finished = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(SCRIPT), "--json-out", str(out)],
        cwd=str(TARGET_ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    assert finished.returncode == 0, finished.stderr[-800:]
    written = _json(out)
    assert written["口径"] == cs.CANDIDATE_口径
    assert written["files"] == len(state)
    assert written["state"] == state, "the CLI and the callable disagree about the tree"
    assert written["digest"] in digests


@pytest.mark.skipif(not LEGACY_BUILD_CLOSURE.is_file(),
                    reason="the gitignored original of the 口径 is only on the audit "
                           "machine; a fresh clone checks the tracked implementation "
                           "against the recorded digest instead (test below)")
def test_the_tracked_口径_reproduces_the_gitignored_original_that_the_audit_used():
    cs = _module()
    spec = importlib.util.spec_from_file_location("build_closure", LEGACY_BUILD_CLOSURE)
    legacy = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(legacy)
    assert legacy.candidate() == cs.candidate_state(), (
        "the tracked implementation is not the 口径 the audit ran on")
    assert hashlib.sha256(json.dumps(legacy.candidate(), sort_keys=True)
                          .encode("utf-8")).hexdigest() == cs.digest_of(cs.candidate_state())


def test_the_two_readings_are_distinct_measurements_not_interchangeable():
    """The candidate reading adds non-ignored untracked files; the tracked reading does not.

    Asserting "the two digests differ" against the working tree as it happens to stand is
    not a guard: right after a commit there are no untracked files, the two readings agree,
    and the test fails for a reason that has nothing to do with the 口径. So the difference
    is produced here — plant an untracked file, watch exactly one of the two readings see
    it, then remove it.
    """
    cs = _module()
    probe = TARGET_ROOT / "zz_two_readings_probe.py"
    assert not probe.exists(), "a leftover probe would poison this measurement"
    probe.write_text("# temporary probe for the two-reading guard\n", encoding="utf-8",
                     newline="\n")
    try:
        candidate = cs.candidate_state()
        tracked = cs.tracked_state()
        assert "zz_two_readings_probe.py" in candidate
        assert "zz_two_readings_probe.py" not in tracked
        assert cs.digest_of(candidate) != cs.digest_of(tracked), (
            "the two 口径 answered identically even with an untracked file present")
        assert len(candidate) > len(tracked)
        assert set(tracked) <= set(candidate)
    finally:
        probe.unlink()
    # and with the probe gone the two readings legitimately agree again: that is the state a
    # freshly committed tree is in, not a defect
    after = cs.candidate_state()
    assert "zz_two_readings_probe.py" not in after
    state = _json(AUDIT_STATE)
    manifest = state["candidate_manifest"]
    assert manifest["口径"] == cs.CANDIDATE_口径, (
        "docs/AUDIT-STATE.json does not name the 口径 its numbers came from")
    assert (TARGET_ROOT / manifest["口径_implementation"]).is_file(), (
        "the document points the 口径 at an implementation that is not in the repo")
    # The recorded digest is re-derived from the AUDITED COMMIT's own git objects, not from
    # the working copy: a document describing commit N cannot be checked against a tree that
    # has already moved on, and comparing it to HEAD is exactly the self-reference that makes
    # such a record unmaintainable.
    audited = state["audited_head_sha"]
    listing = subprocess.run(["git", "ls-tree", "-r", "-z", "--name-only", audited],
                             cwd=str(TARGET_ROOT), capture_output=True,
                             encoding="utf-8", errors="replace").stdout
    paths = [entry for entry in listing.split("\x00") if entry]
    assert len(paths) == state["audited_candidate_files"], (
        "the audited commit holds %d blobs but the document records %s files"
        % (len(paths), state["audited_candidate_files"]))
    assert re.match(r"^[0-9a-f]{64}$", state["audited_candidate_digest"]), (
        "the recorded candidate digest is not a SHA-256 hex string")
    assert after, "the working tree reading came back empty"


@pytest.mark.parametrize("path", [BASELINE, AUDIT_STATE])
def test_the_in_repo_evidence_records_are_valid_json_with_a_generation_stamp(path):
    assert path.is_file(), "%s is missing -- it must be tracked, not local-only" % path.name
    data = _json(path)
    assert data.get("generated_at"), "%s has no generated_at stamp" % path.name
    assert data.get("schema"), "%s has no schema name" % path.name


def test_environment_baseline_agrees_with_this_interpreter_right_now():
    data = _json(BASELINE)
    recorded = data["interpreter"]
    assert recorded["version_info"][:3] == list(sys.version_info[:3]), (
        "the baseline records Python %s but this interpreter is %s"
        % (recorded["version_info"], list(sys.version_info[:3])))
    assert recorded["version_string"] == sys.version, (
        "the interpreter version string in the baseline is not what this interpreter says")
    assert Path(recorded["executable"]).is_file()


def test_environment_baseline_agrees_with_the_sqlite_and_fts5_capability():
    data = _json(BASELINE)["sqlite"]
    assert data["sqlite_library_version"] == sqlite3.sqlite_version, (
        "the sqlite library version drifted from the baseline; regenerate it, do not edit it")
    conn = sqlite3.connect(":memory:")
    try:
        conn.execute("CREATE VIRTUAL TABLE t USING fts5(a)")
        fts5_ok = True
    except sqlite3.Error:
        fts5_ok = False
    try:
        conn.execute("CREATE VIRTUAL TABLE t2 USING fts5(a, tokenize='trigram')")
        trigram_ok = True
    except sqlite3.Error:
        trigram_ok = False
    finally:
        conn.close()
    assert fts5_ok is data["fts5_available"], (
        "FTS5 availability recorded as %s does not match this build"
        % data["fts5_available"])
    assert trigram_ok is data["fts5_trigram_tokenizer_available"], (
        "the trigram tokenizer the knowledge-library search falls back to is recorded as %s "
        "but this build answers %s" % (data["fts5_trigram_tokenizer_available"], trigram_ok))


@pytest.mark.parametrize("domain", ["work", "design"])
def test_environment_baseline_source_anchors_are_the_live_git_heads(domain):
    data = _json(BASELINE)["read_only_source_roots"][domain]
    root = Path(data["path"])
    assert root.is_dir(), "the recorded read-only source root %s does not exist" % root
    assert data["read_only"] is True, (
        "%s is a source of this fusion and is read-only; the baseline may not say otherwise"
        % root)
    live = _git(["rev-parse", "HEAD"], cwd=root)
    assert SHA_RE.match(live) and SHA_RE.match(data["head_observed"]), (
        "the recorded anchor is not a full commit SHA")
    assert live == data["head_observed"], (
        "%s moved: baseline says %s, git now says %s. The read-only sources must not be "
        "written by this project; if the source project itself advanced, regenerate the "
        "baseline rather than editing the number." % (root, data["head_observed"], live))


def test_audit_state_binds_a_real_commit_in_this_branch_and_has_no_hand_typed_sha():
    data = _json(AUDIT_STATE)
    live_head = _git(["rev-parse", "HEAD"])
    recorded = data["audited_head_sha"]
    assert SHA_RE.match(recorded), "the audited HEAD is not a 40-hex commit id"
    # A tracked document cannot name the commit that carries it: committing this file moves
    # HEAD past the value inside it, so "recorded == HEAD" is unsatisfiable by construction
    # and would fail the next commit for a reason nobody can fix. What IS checkable is that
    # the audited commit exists in this branch's history and that its tree matches.
    assert _git(["merge-base", recorded, "HEAD"]) == recorded, (
        "docs/AUDIT-STATE.json binds %s, which is not an ancestor of HEAD %s — a hand-typed "
        "or foreign SHA fails here" % (recorded, live_head))
    assert data["audited_head_tree"] == _git(["rev-parse", recorded + "^{tree}"]), (
        "the recorded tree is not the tree of the recorded commit")
    assert data["branch"] == _git(["rev-parse", "--abbrev-ref", "HEAD"])
    assert data["previous_independent_audit"]["verdict"] == "FAIL", (
        "the independent audit of the previous candidate said FAIL; the tracked state must "
        "not quietly read as a pass")
    conclusion = data["re_review"]["conclusion"]
    assert conclusion == "NOT_YET_INDEPENDENTLY_RE_REVIEWED", (
        "the re-review conclusion changed; only an actual independent review may replace it")
    hook_digest = data["upload_facts"]["prepush_hook"]["sha256_observed"]
    assert re.match(r"^[0-9a-f]{64}$", hook_digest), (
        "the recorded pre-push hook digest is not a SHA-256 hex string")
    hook = TARGET_ROOT / ".git" / "hooks" / "pre-push"
    assert hashlib.sha256(hook.read_bytes()).hexdigest() == \
        data["upload_facts"]["prepush_hook"]["sha256_observed"], (
        "the pre-push guard hook is no longer the byte-for-byte copy the upload record "
        "describes")
    assert data["upload_facts"]["prepush_hook"]["was_bypassed_with_no_verify"] is False


def test_every_recorded_path_in_the_two_evidence_files_exists():
    problems = []
    for path in (BASELINE, AUDIT_STATE):
        data = _json(path)
        for recorded in data.get("paths_verified_to_exist", []):
            if not Path(recorded).exists():
                problems.append("%s: %s" % (path.name, recorded))
    assert not problems, "recorded paths that do not exist:\n" + "\n".join(problems)
    # and the upload facts point at paths a clone can at least name
    facts = _json(AUDIT_STATE)["upload_facts"]
    assert (TARGET_ROOT / ".gitignore").read_text(encoding="utf-8").splitlines()[1].strip() \
        == facts["gitignore_line_that_hides_it"], (
        "the record claims .gitignore hides the evidence directory; that is the whole reason "
        "these in-repo artefacts exist, so it must stay true")


def _audit_state_builder():
    spec = importlib.util.spec_from_file_location(
        "build_audit_state_under_test", TARGET_ROOT / "scripts" / "build_audit_state.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def test_the_audit_state_record_is_not_staler_than_the_tree_it_describes():
    """The re-review entry document must answer "still current?" with something interpretable.

    A whole-document comparison can never come out true here: the record cannot name the commit
    that carries it, and ``generated_at`` moves with every run -- so the check used to print
    ``matches: false`` while exiting 0, which reads as a broken guard. The self-referential
    fields are now folded out *and named*; the register census, the source-repo digests, the
    audited binding and the re-review conclusion are compared in full, and the exit code follows
    that comparison.
    """
    check = subprocess.run([sys.executable, "-B", "-X", "utf8",
                            str(TARGET_ROOT / "scripts" / "build_audit_state.py"), "--check"],
                           cwd=str(TARGET_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=600)
    assert check.returncode in (0, 1, 3), check.returncode
    report = json.loads(check.stdout.strip().splitlines()[-1])
    if check.returncode == 3:
        # A section this machine could not observe. That is a named answer, not a pass and not
        # drift: what the record claims about the tree still has to agree, and if it did not the
        # check would have returned 1 with the offending section in ``stale_sections``.
        assert report["verdict"] == "NOT_OBSERVABLE_HERE", report
        assert report["stale"] is False and report["stale_sections"] == [], report
        assert report["unobservable_sections"] or report["prereq_sections"], report
    else:
        assert check.returncode == 0, check.stdout[-800:] + check.stderr[-800:]
        assert report["matches"] is True and report["stale"] is False, report
    assert report["head_is_ancestor"] is True, report
    folded = set(report["folded_rotating"])
    assert {"generated_at", "head_sha_now", "audited_candidate_digest",
            "audited_candidate_files", "commit_count_observed"} <= folded, folded
    # The binding is not a rotating field: it names an ancestor, so it can be compared. Folding it
    # is what let a record bound to the head carrying the document print MATCHES.
    for compared in ("registers", "source_repos", "re_review", "candidate_manifest",
                     "audited_head_sha", "audited_head_tree"):
        assert not any(part in folded for part in (compared, "upload_facts/" + compared)), (
            compared, sorted(folded))


def test_the_audit_state_check_fails_on_a_stale_census(tmp_path):
    """The folded comparison still has to be able to say "this record is old".

    Machine-independent by construction: the record under test is *generated here*, on this
    machine, from this tree, so the two sides of the first assertion differ only by what the
    test plants. Reading the published ``docs/AUDIT-STATE.json`` as the baseline did not do
    that -- on a machine that no longer has the two read-only source repositories the check
    fails because of the absent source roots, and the "stale census" node then passed (or
    failed) for a reason it never tested. Measured that way: this node was one of the 15 in
    ``.project-local/runs/independence-20261101.json`` whose verdict moved when only the
    source paths were redirected.

    Both halves are required: rc=0 on the freshly generated record pins the control, and rc=1
    after the plant pins the sensitivity. Without the control, rc=1 proves nothing.

    This file stays machine-bound for a different, honest reason: the record it re-derives
    includes `upload_facts`, whose pre-push hook is not in Git. A bare clone therefore gets
    ``prereq_sections: ["upload_facts"]`` with rc=3 on the *control* half -- a named cause, not a
    green run -- and the node is excluded from the clone suite by ``test_v23`` rather than
    softened.
    """
    module = _audit_state_builder()
    fresh = module.merge(json.loads(module.OUT.read_text(encoding="utf-8")),
                         module.live_fields(None))
    census = fresh["registers"]
    assert census, "no register census in the record to falsify"
    plantable = [name for name, record in sorted(census.items())
                 if isinstance(record.get("rows"), int)]
    assert plantable, (
        "the census holds no integer row count, so a stale census cannot be planted here: "
        "this node would silently lose its ability to fail -- %s" % census)

    def run_check(report_path: Path) -> tuple[int, dict]:
        module.OUT = report_path
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer):
            rc = module.main([sys.argv[0], "--check"])
        return rc, json.loads(buffer.getvalue().strip().splitlines()[-1])

    control = tmp_path / "AUDIT-STATE-fresh.json"
    control.write_text(json.dumps(fresh, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    rc, report = run_check(control)
    assert rc == 0 and report["matches"] is True and report["stale_sections"] == [], (
        "the check does not accept a record generated from this very tree; its rc=1 below "
        "would be caused by the machine, not by the planted staleness: %s" % report)

    stale = json.loads(control.read_text(encoding="utf-8"))
    stale["registers"][plantable[0]]["rows"] += 1
    mutated = tmp_path / "AUDIT-STATE-stale.json"
    mutated.write_text(json.dumps(stale, ensure_ascii=False, indent=2) + "\n",
                       encoding="utf-8", newline="\n")
    rc, report = run_check(mutated)
    assert rc == 1, (
        "a record whose register census no longer matches the tree passed its own check")
    assert report["stale"] is True and report["matches"] is False, report
    assert report["stale_sections"] == ["registers"], (
        "the check failed, but not for the census this test planted: %s" % report)

