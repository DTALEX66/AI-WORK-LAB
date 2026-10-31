"""Refresh the live-derived fields of ``docs/AUDIT-STATE.json``.

A tracked document cannot name the commit that carries it, so the audited commit is the
last commit whose tree was measured and is an ancestor of HEAD by the time a reader checks
it. This script is the only sanctioned way to move those numbers: it re-reads git, the
pre-push hook, the registers and the two read-only sources, and leaves every field it does
not compute untouched, so an older document keeps the keys its tests still assert.

Usage: after committing a candidate, run
    python scripts/build_audit_state.py --audited-commit <that commit>
and commit the resulting one-line-per-round change.
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
SOURCES = {"work": pathlib.Path(r"D:\All projects\WORK-LAB"),
           "design": pathlib.Path(r"D:\All projects\DESIGN-LAB")}
sys.path.insert(0, str(ROOT / "scripts"))
import candidate_snapshot  # noqa: E402  same 口径 as the closure clause


def git(args: list[str], cwd: pathlib.Path | None = None) -> str:
    return subprocess.run(["git"] + args, cwd=str(cwd or ROOT), capture_output=True,
                          text=True, encoding="utf-8", errors="replace").stdout.strip()


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
            "prepush_hook": hook_facts(),
            "core_hooks_path": git(["config", "--get", "core.hooksPath"]) or None,
        },
        "registers": {name: register_rows(name) for name in REGISTERS},
        "source_repos": {name: dict(root=str(path), head_observed=git(["rev-parse", "HEAD"],
                                                                      cwd=path))
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
                merged["candidate_manifest"] = manifest
        else:
            merged[key] = value
    return merged


#: Fields the record cannot pin without lying about itself (self-reference) or restarting
#: the clock. ``audited_candidate_files`` and ``commit_count_observed`` belong here too: a
#: commit that carries this document changes both by construction.
ROTATING_FIELDS = ("generated_at", "head_sha_now", "audited_head_sha", "audited_head_tree",
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
    """
    folded = json.loads(json.dumps(document))
    for key in ROTATING_FIELDS:
        folded.pop(key, None)
    facts = folded.get("upload_facts")
    if isinstance(facts, dict):
        for key in ROTATING_NESTED:
            facts.pop(key, None)
    return folded


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--audited-commit")
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv[1:])

    updates = live_fields(args.audited_commit)
    existing = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
    document = merge(existing, updates)
    # a stale audited commit is only legitimate if it really is in this branch's history
    ancestry = subprocess.run(["git", "merge-base", "--is-ancestor",
                               document["audited_head_sha"], "HEAD"],
                              cwd=str(ROOT), capture_output=True, text=True)
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        tracked = json.loads(OUT.read_text(encoding="utf-8")) if OUT.is_file() else {}
        stale = _without_rotating(tracked) != _without_rotating(document)
        # the ancestry claim worth checking is the one already published, not the rebuilt
        # document's own HEAD (that one is true by construction)
        published = tracked.get("audited_head_sha") or document["audited_head_sha"]
        ancestry = subprocess.run(["git", "merge-base", "--is-ancestor", published, "HEAD"],
                                  cwd=str(ROOT), capture_output=True, text=True)
        print(json.dumps(dict(matches=not stale, stale=stale,
                              published_audited=published[:12],
                              audited=document["audited_head_sha"][:12],
                              head_is_ancestor=ancestry.returncode == 0,
                              folded_rotating=sorted(ROTATING_FIELDS)
                              + ["upload_facts/" + key for key in ROTATING_NESTED]),
                         ensure_ascii=True))
        return 1 if (stale or ancestry.returncode != 0) else 0
    OUT.write_text(text, encoding="utf-8", newline="\n")
    print(json.dumps(dict(written=str(OUT), audited_head_sha=document["audited_head_sha"],
                          candidate_files=document["audited_candidate_files"],
                          head_is_ancestor=ancestry.returncode == 0,
                          hook_sha256=document["upload_facts"]["prepush_hook"]
                          ["sha256_observed"][:12] + "…"), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
