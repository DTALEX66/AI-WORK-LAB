"""Refresh the live-derived fields of ``docs/AUDIT-STATE.json``.

A tracked document cannot name the commit that carries it, so the audited commit is the
last commit whose tree was measured and is an ancestor of HEAD by the time a reader checks
it. This script is the only sanctioned way to move those numbers: it re-reads git, the
pre-push hook, the registers and the two read-only sources, and leaves every field it does
not compute untouched, so an older document keeps the keys its tests still assert.

Usage: after committing a candidate, run
    python scripts/build_audit_state.py --audited-commit <that commit>
and commit the resulting one-line-per-round change. Without the flag the document is refreshed
in place and the binding stays where the last measurement put it; a run that republished the
remote facts must not be able to move what is claimed to have been measured.
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT = ROOT / "docs" / "AUDIT-STATE.json"
HOOK = ROOT / ".git" / "hooks" / "pre-push"
REGISTERS = ("migration/task-acceptance.csv", "migration/route-surface.csv",
             "migration/ui-entry-disposition.csv",
             "migration/capability-family-register.csv",
             "migration/requirement-traceability.csv", "migration/deferral-register.json",
             "config/blocker-register.json",
             # 2026-10-31: the closure table the handoff §七 asked for, and the two
             # source-coverage registers whose row/path difference is now an invariant
             "migration/audit-item-closure.csv",
             "migration/source-coverage-work.csv", "migration/source-coverage-design.csv")
sys.path.insert(0, str(ROOT / "scripts"))
import candidate_snapshot  # noqa: E402  same 口径 as the closure clause
import source_roots  # noqa: E402  the one place roots outside this checkout are resolved

SOURCES = {"work": source_roots.work_root(), "design": source_roots.design_root()}


#: What ``git()`` returns when the requested cwd is not a directory on this machine. The
#: generator used to raise ``NotADirectoryError`` (Windows, WinError 267) there and the whole
#: record -- registers, upload facts, re-review conclusion included -- died with it, on exactly
#: the machines the audit entry invites to re-run it: a clone of a repo whose two read-only
#: sources have been archived away. A named sentinel instead, so the record can say "this
#: machine could not observe it" and ``--check`` can still print a verdict.
SOURCE_ROOT_ABSENT = source_roots.SOURCE_ROOT_ABSENT
#: Field added to a ``source_repos`` entry that could not be observed. Like ``register_rows``'
#: ``missing: True`` it appears only in the failure case, so a machine that does have the
#: sources rebuilds the record byte-for-byte and ``--check`` still answers 0 there.
SOURCE_NOT_OBSERVED_KEY = "not_observed"


def git(args: list[str], cwd: pathlib.Path | None = None) -> str:
    where = cwd or ROOT
    if not where.is_dir():
        return SOURCE_ROOT_ABSENT
    try:
        return subprocess.run(["git"] + args, cwd=str(where), capture_output=True,
                              text=True, encoding="utf-8", errors="replace").stdout.strip()
    except OSError:
        # the directory vanished between the check and the call, or is unreadable here: the
        # same honest answer as "not a directory", never a traceback that kills the record.
        return SOURCE_ROOT_ABSENT


def hook_facts() -> dict:
    facts = {"path": ".git/hooks/pre-push", "present": HOOK.is_file()}
    if HOOK.is_file():
        blob = HOOK.read_bytes()
        facts.update(sha256_observed=hashlib.sha256(blob).hexdigest(), bytes=len(blob),
                     blocks_push_when_invoked=b"exit 1" in blob)
    else:
        facts.update(sha256_observed=None, bytes=0, blocks_push_when_invoked=False)
    return facts


def register_rows(relative: str) -> dict:
    path = ROOT / relative
    if not path.is_file():
        return {"rows": None, "missing": True}
    if relative.endswith(".json"):
        document = json.loads(path.read_text(encoding="utf-8"))
        return {"rows": len(document.get("items") or document.get("entries") or [])}
    import csv
    with open(path, encoding="utf-8-sig", newline="") as handle:
        return {"rows": len(list(csv.DictReader(handle)))}


def source_repo_record(name: str, path: pathlib.Path) -> dict:
    """One side of ``source_repos``: what this machine observed, or why it could not.

    ``head_observed`` always exists; when the root is absent it carries the named sentinel
    rather than an empty string, and the entry gains ``not_observed`` saying which root was
    missing on this machine. The absence fields are added only in the failure case (the same
    shape ``register_rows`` uses for ``missing: True``), because a record that always gained
    them would no longer reproduce byte-for-byte on the machine that has the sources -- and
    that record is tracked, so ``--check`` would report a drift that is only the generator's
    own schema change.
    """
    record = {"root": str(path), "head_observed": git(["rev-parse", "HEAD"], cwd=path)}
    if record["head_observed"] == SOURCE_ROOT_ABSENT:
        record[SOURCE_NOT_OBSERVED_KEY] = {
            "repository": name,
            "root_absent": str(path),
            "reason": ("this machine has no %s repository at %s, so its HEAD could not be "
                       "observed; the record was written on a machine that did"
                       % (name, path)),
        }
    return record


def live_fields(audited_commit: str | None) -> dict:
    audited = git(["rev-parse", audited_commit or "HEAD"])
    state = candidate_snapshot.candidate_state()
    branch = git(["rev-parse", "--abbrev-ref", "HEAD"])
    remote_ref = ""
    try:
        remote_ref = git(["ls-remote", "--heads", "origin", branch]).split("\t")[0]
    except OSError:
        remote_ref = ""
    return {
        "generated_at": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        "observed_from": "git and the filesystem, read by scripts/build_audit_state.py",
        "audited_head_sha": audited,
        "audited_head_tree": git(["rev-parse", audited + "^{tree}"]),
        "audited_candidate_files": len(state),
        "audited_candidate_digest": candidate_snapshot.digest_of(state),
        "branch": branch,
        "commit_count_observed": int(git(["rev-list", "--count", "HEAD"]) or 0),
        "head_sha_now": git(["rev-parse", "HEAD"]),
        "upload_facts": {
            "remote_name": "origin",
            "remote_url": git(["remote", "get-url", "origin"]),
            "remote_ref_observed": remote_ref,
            "default_branch": git(["symbolic-ref", "--short", "HEAD"]),
            # Read from local remote-tracking refs, not `ls-remote`: a register that needs the network to
            # reproduce itself would stop being checkable on the very machine that deleted the sources.
            "remote_branches_observed": sorted(
                line.strip() for line in
                git(["branch", "-r", "--format=%(refname:short)"]).splitlines()
                if "/" in line.strip()),
            "prepush_hook": hook_facts(),
            "core_hooks_path": git(["config", "--get", "core.hooksPath"]) or None,
        },
        "registers": {name: register_rows(name) for name in REGISTERS},
        "source_repos": {name: source_repo_record(name, path)
                         for name, path in SOURCES.items()},
    }


def merge(existing: dict, updates: dict) -> dict:
    """Replace the computed keys, keep everything this generator does not know about.

    ``upload_facts`` and ``upload_facts.prepush_hook`` merge one level deeper: the earlier
    round recorded fields there (was_bypassed_with_no_verify and friends) that a reader is
    still entitled to, and a generator that silently drops them would look like the fact
    disappeared rather than like the generator never computed it.

    ``candidate_manifest`` is refreshed in place when it already exists. Leaving it would
    put two digests in one document, one of them a stale number the tests still read.
    """
    merged = dict(existing)
    for key, value in updates.items():
        if key == "upload_facts" and isinstance(merged.get(key), dict):
            facts = dict(merged[key])
            for sub, sub_value in value.items():
                if sub == "prepush_hook" and isinstance(facts.get(sub), dict):
                    hook = dict(facts[sub])
                    hook.update(sub_value)
                    facts[sub] = hook
                else:
                    facts[sub] = sub_value
            merged[key] = facts
        elif key == "audited_head_sha":
            merged[key] = value
            # candidate_manifest documents the 口径 (implementation, distinct reading,
            # recompute command); the numbers themselves live in audited_candidate_* so a
            # reader cannot get two competing file counts out of one document.
            manifest = merged.get("candidate_manifest")
            if isinstance(manifest, dict):
                manifest = dict(manifest)
                manifest["口径_implementation"] = "scripts/candidate_snapshot.py"
                manifest["what_audited_candidate_names_read"] = (
                    "the working tree at run time (%s), not the tree of audited_head_sha; "
                    "audited_head_tree is that commit's own tree and is compared in full"
                    % manifest.get("口径", "git_cached_plus_non_ignored_untracked"))
                merged["candidate_manifest"] = manifest
        else:
            merged[key] = value
    return merged


#: Fields the record cannot pin without lying about itself (self-reference) or restarting
#: the clock. ``audited_candidate_files`` and ``commit_count_observed`` belong here too: a
#: commit that carries this document changes both by construction.
#: ``audited_head_sha`` and ``audited_head_tree`` used to sit in this list as well, on the
#: reasoning that a tracked document cannot name its own commit. That is true of
#: ``head_sha_now``, not of the *binding*: the binding names an ancestor, so comparing it costs
#: nothing, and a ``--check --audited-commit X`` run against a record naming Y now says DRIFT
#: instead of agreeing with both. What this comparison cannot decide is whether the published
#: binding was ever measured at all -- only the suite receipt says that, and the clause that
#: reads it lives in ``audit_objective_closure``, not here.
#: What genuinely rotates is the ``audited_candidate_*`` pair: that 口径 reads the working tree
#: (git cached plus non-ignored untracked), so it changes whenever an uncommitted document
#: changes, even while the binding stays put.
ROTATING_FIELDS = ("generated_at", "head_sha_now",
                   "audited_candidate_digest", "audited_candidate_files",
                   "commit_count_observed")
ROTATING_NESTED = ("remote_ref_observed",)


def _without_rotating(document: dict) -> dict:
    """Drop the fields that must rotate the moment this document is committed.

    The record cannot name the commit that carries it, and ``generated_at`` moves with every
    run, so a byte comparison of the whole document printed a permanent ``matches: false`` --
    a check whose verdict cannot come out true tells a reviewer nothing. These fields are
    folded out and *named* in the output, which is how the closure register treats its
    receipt-bound columns. Everything else -- the register census, the source-repo digests,
    the re-review conclusion -- is compared in full.

    Consequence, stated rather than hidden: a machine without the two read-only sources
    cannot reproduce their digests, so ``--check`` reports a mismatch there. That is the
    honest reading, and the report now names it (``stale_sections`` plus
    ``source_roots_absent_on_this_machine``) instead of raising; nothing here is folded away
    to make that machine look green.
    """
    folded = json.loads(json.dumps(document))
    for key in ROTATING_FIELDS:
        folded.pop(key, None)
    facts = folded.get("upload_facts")
    if isinstance(facts, dict):
        for key in ROTATING_NESTED:
            facts.pop(key, None)
    return folded


def _stale_sections(tracked: dict, rebuilt: dict) -> list[str]:
    """Top-level sections that disagree. Kept as the raw comparison; the taxonomy is below."""
    before, after = _without_rotating(tracked), _without_rotating(rebuilt)
    return sorted(key for key in set(before) | set(after) if before.get(key) != after.get(key))


#: The fields of ``source_repos`` that a machine without that repository cannot produce: which
#: root it looked at, what HEAD it read there, and the note saying it could not. A disagreement
#: in any *other* field is drift, and an absent root must not be allowed to excuse it.
ABSENCE_FIELDS = frozenset({"root", "head_observed", SOURCE_NOT_OBSERVED_KEY})
#: The fields of ``upload_facts`` that describe this machine rather than the repository: the
#: pre-push hook is not in Git, and the remote wiring a clone inherits points at wherever it was
#: cloned from. ``pushed_branch`` and the bypass facts are deliberately absent from this list --
#: they are claims about the project, so writing them as a false value is drift, not a missing
#: prerequisite.
MACHINE_LOCAL_FACTS = frozenset({"remote_name", "remote_url", "remote_ref_observed",
                                 "default_branch", "remote_branches_observed", "prepush_hook",
                                 "core_hooks_path"})


def _changed_fields(before, after) -> set | None:
    """Which keys disagree inside one section, or ``None`` if the section is a bare value."""
    if not isinstance(before, dict) or not isinstance(after, dict):
        return None
    return {key for key in set(before) | set(after) if before.get(key) != after.get(key)}


def _source_repos_is_unobservable(before, after) -> bool:
    """Every disagreement in ``source_repos`` sits inside a root this machine could not read.

    The section is keyed by repository, so the comparison is one level deeper than a section:
    ``{"work": {...}, "design": {...}}`` disagreeing in a *field* those entries hold is drift,
    while disagreeing only in ``root``/``head_observed``/``not_observed`` for a repository the
    rebuilt record itself says it could not open is not.
    """
    before, after = before or {}, after or {}
    if set(before) != set(after):
        return False
    absent = {value[SOURCE_NOT_OBSERVED_KEY].get("repository") for value in after.values()
              if isinstance(value, dict) and value.get(SOURCE_NOT_OBSERVED_KEY)}
    if not absent:
        return False
    for name in sorted(after):
        diff = _changed_fields(before.get(name), after.get(name))
        if not diff:
            continue
        if name not in absent or not diff <= ABSENCE_FIELDS:
            return False
    return True


def _section_classes(tracked: dict, rebuilt: dict) -> tuple[list[str], list[str], list[str]]:
    """Split the disagreement into drift / unobservable / machine-prerequisite.

    Three different answers, and collapsing them is what makes a deletion look like a defect:
    ``drift`` means the published record no longer agrees with a tree this run could read, and is
    the only class that returns 1. ``unobservable`` means a read-only source root is not on this
    machine, and ``prereq`` means the section records the hook or the remote of *this* checkout.
    Both of the latter return 3 and name themselves, so a reviewer who clones the repository sees
    "this machine cannot observe it" instead of a red that accuses the register.
    """
    before, after = _without_rotating(tracked), _without_rotating(rebuilt)
    drift, unobservable, prereq = [], [], []
    for key in set(before) | set(after):
        if before.get(key) == after.get(key):
            continue
        if key == "source_repos":
            (unobservable if _source_repos_is_unobservable(before.get(key), after.get(key))
             else drift).append(key)
        elif key == "upload_facts":
            fields = _changed_fields(before.get(key), after.get(key))
            (prereq if fields is not None and fields <= MACHINE_LOCAL_FACTS
             else drift).append(key)
        else:
            drift.append(key)
    return sorted(drift), sorted(unobservable), sorted(prereq)


def _absent_source_roots(document: dict) -> list[dict]:
    """The source roots this machine could not read, as the record states them."""
    return [entry["not_observed"] for entry in (document.get("source_repos") or {}).values()
            if isinstance(entry, dict) and entry.get(SOURCE_NOT_OBSERVED_KEY)]


def binding_commit(existing: dict, requested: str | None) -> str:
    """Which commit the record binds to: re-pinning is an explicit act, never a side effect.

    Omitting ``--audited-commit`` used to mean HEAD, so the ordinary act of publishing a fresh
    observation (the remote ref after a push, today) silently moved the binding onto the head
    carrying this very document -- a tree no receipt can describe -- while ``--check`` folded
    ``audited_head_sha`` and still printed ``MATCHES``. That combination is how a fake binding
    survives a green gate, so the flag is now the only thing that moves it.
    """
    if requested:
        # ``rev-parse`` echoes an unresolvable argument back on stdout and only signals failure in
        # its exit code, which this module's git() does not read; --verify prints nothing instead,
        # so a typo arrives as an empty answer the caller refuses rather than as a literal ref
        # written into the record as if it were a commit.
        return git(["rev-parse", "--verify", requested + "^{commit}"])
    published = (existing.get("audited_head_sha") or "").strip()
    return published or git(["rev-parse", "--verify", "HEAD^{commit}"])


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audited-commit")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv[1:])

    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    binding = binding_commit(existing, args.audited_commit)
    if not binding:
        # An empty answer here would make live_fields fall back to HEAD, which is the re-pin this
        # function exists to forbid: a typo in the flag must refuse, not silently measure nothing.
        print(json.dumps({"error": "AUDITED_COMMIT_UNRESOLVABLE",
                          "requested": args.audited_commit}, ensure_ascii=True))
        return 1
    updates = live_fields(binding)
    document = merge(existing, updates)
    # a stale audited commit is only legitimate if it really is in this branch's history
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor",
                               document["audited_head_sha"], "HEAD"],
                              cwd=str(ROOT), capture_output=True, text=True)
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        tracked = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
        drift, unobservable, prereq = _section_classes(tracked, document)
        sections = _stale_sections(tracked, document)
        stale = bool(drift)
        absent = _absent_source_roots(document)
        # the ancestry claim worth checking is the one already published, not the rebuilt
        # document's own HEAD (that one is true by construction)
        published = tracked.get("audited_head_sha") or document["audited_head_sha"]
        ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", published, "HEAD"],
                                  cwd=str(ROOT), capture_output=True, text=True)
        print(json.dumps(dict(matches=not sections,
                              stale=stale,
                              stale_sections=drift,
                              unobservable_sections=unobservable,
                              prereq_sections=prereq,
                              verdict=("DRIFT" if stale else
                                       "NOT_OBSERVABLE_HERE" if unobservable or prereq
                                       else "MATCHES"),
                              published_audited=published[:12],
                              audited=document["audited_head_sha"][:12],
                              head_is_ancestor=ancestry.returncode == 0,
                              source_roots_absent_on_this_machine=absent,
                              folded_rotating=sorted(ROTATING_FIELDS)
                              + ["upload_facts/" + key for key in ROTATING_NESTED]),
                         ensure_ascii=True))
        if stale or ancestry.returncode != 0:
            return 1
        return 3 if (unobservable or prereq) else 0
    if ancestry.returncode != 0:
        # Writing this document would be publishing a binding to a tree that is not in this
        # branch, which is the one claim a reader cannot check after the fact. Refuse instead.
        print(json.dumps({"error": "AUDITED_COMMIT_NOT_IN_THIS_BRANCH",
                          "audited_head_sha": document["audited_head_sha"],
                          "head_now": document["head_sha_now"]}, ensure_ascii=True))
        return 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    # A clone has no hook file, so sha256_observed is None there. Slicing it unconditionally made
    # the write path raise exactly where the record is meant to say "this machine did not have one".
    hook_digest = document["upload_facts"]["prepush_hook"]["sha256_observed"]
    print(json.dumps(dict(written=str(OUT), audited_head_sha=document["audited_head_sha"],
                          candidate_files=document["audited_candidate_files"],
                          head_is_ancestor=ancestry.returncode == 0,
                          hook_sha256=(hook_digest[:12] + "…" if hook_digest else None),
                          binding_moved_this_run=(
                              existing.get("audited_head_sha") != document["audited_head_sha"])),
                      ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
