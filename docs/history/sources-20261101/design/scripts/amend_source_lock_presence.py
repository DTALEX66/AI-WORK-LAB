# SPDX-License-Identifier: MIT
"""Record whether each vendor/sources.lock.json byte claim is reachable at all.

The lock lists 46 sources with a `files` count and a `path`, and
`verify_source_registry.py` answers `SOURCE_REGISTRY=PASS` without ever opening a
single one of those paths. Measured on `main` = `b7f82ac0`, that PASS covers three
very different situations:

  * 3 `ABSORB_MINIMAL` sources whose files are committed, so a clone has them;
  * 37 `CONDITIONAL_POC` sources whose `path` is `.project-local/cache/vendor/<id>`,
    a gitignored directory that exists only on the machine that acquired them
    (`docs/THIRD_PARTY_ISOLATION.md` calls it 保真副本 in cache, by policy);
  * 6 `LOCK_REFERENCE` sources whose `design-lab/intelligence/*` paths were deleted
    from Git on 2026-09-04 and are not anywhere on disk either.

This script writes what is *measured* rather than what is claimed: a `presence`
class derived from `git ls-files` plus the filesystem, a file count from each side,
and a content digest over the bytes that are actually there. It adds no policy and
removes no record; the point is that a reader can no longer mistake "hashed on one
machine" for "in the repository".

Output is deterministic (no timestamps), so the projections that digest this file
stay byte-stable across runs and platforms.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
LOCK = REPO / "vendor" / "sources.lock.json"
ISOLATION_DOC = REPO / "docs" / "THIRD_PARTY_ISOLATION.md"
# `.project-local/` is PROJECT_LOCAL_ROOT and is gitignored, so a path under it can
# never be in Git on any machine. Presence must be derived from rules that hold in a
# fresh clone, not from whether this machine happens to still have the cache.
VOLATILE_ROOT = ".project-local/"
PRESENCE = ("IN_REPO", "LOCAL_CACHE_ONLY", "ABSENT_FROM_GIT")


def tracked_paths() -> list[str]:
    out = subprocess.run(["git", "-C", str(REPO), "ls-files", "-z"],
                         capture_output=True, check=True).stdout
    return [p.decode("utf-8").replace("\\", "/") for p in out.split(b"\0") if p]


def retired_in_doc(path: str) -> bool:
    """True only when the isolation record names this exact path.

    Substring-on-directory is enough here because the doc lists the deleted files by
    full path (`design-lab/intelligence/claude-design-skill/AGENTS.md`), so a source
    whose directory never appears stays visibly unbacked rather than being retro-fitted
    with a reason nobody recorded.
    """
    if not ISOLATION_DOC.is_file():
        return False
    text = ISOLATION_DOC.read_text(encoding="utf-8", errors="replace")
    return path in text


def digest_dir(root: Path) -> tuple[int, str | None]:
    """(file count, sha256 over sorted `relpath\\0<sha256(bytes)>\\0`).

    Sorting the relative paths makes the digest independent of directory order, and
    hashing content rather than mtimes makes it reproducible for any identical set
    of bytes. Returns None when the directory itself is absent.
    """
    if not root.is_dir():
        return 0, None
    files = sorted((p for p in root.rglob("*") if p.is_file()),
                   key=lambda p: p.relative_to(root).as_posix())
    if not files:
        # An empty directory has no content to attest. Returning the digest of
        # nothing (e3b0c442…) would make "the cache folder is here but empty"
        # indistinguishable from "these bytes were verified", which is the one
        # confusion this record exists to prevent.
        return 0, None
    h = hashlib.sha256()
    for p in files:
        h.update(p.relative_to(root).as_posix().encode("utf-8"))
        h.update(b"\0")
        h.update(hashlib.sha256(p.read_bytes()).hexdigest().encode("ascii"))
        h.update(b"\0")
    return len(files), h.hexdigest()


def git(*args: str) -> str:
    r = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        return ""
    return r.stdout.strip()


def retired_provenance(path: str) -> dict:
    """Recover from Git what the working tree no longer holds for a retired path.

    A reference whose directory was deleted is not an unresolvable claim: the deletion
    commit, the tree it removed (an immutable content identity) and the SOURCE.md inside
    that tree are all still in this repository's history. Everything here is read from
    git, never typed: a hand-copied hash is the exact failure this record exists to
    prevent. When history holds no SOURCE.md, that is stated as `sourceRecordPresent:
    false` rather than left blank, because "no revision was recorded at vendoring time"
    and "nobody looked" are different facts.
    """
    deletion = git("log", "--diff-filter=D", "-1", "--format=%H%x09%ad",
                   "--date=format:%Y-%m-%d", "--", path)
    if not deletion:
        return {"retiredIn": None}
    sha, _, date = deletion.partition("\t")
    tree = git("rev-parse", "--verify", "--quiet", f"{sha}^:{path}")
    source_md = git("show", f"{sha}^:{path}/SOURCE.md") if tree else ""
    fields: dict[str, str] = {}
    for line in source_md.splitlines():
        match = re.match(r"^\s*[-*]?\s*\**\s*(repo|来源|license|许可|branch[/ ]?commit|branch|commit)"
                         r"\s*\**\s*[:：]\s*(\S.*)$", line, re.I)
        if match:
            # `https://github.com/x/y（MIT）` and `MIT License（LICENSE 副本随附）` both carry
            # prose after the value in the same field; the full-width paren is not part of
            # a URL, so the value ends where whitespace or a bracket begins.
            value = re.split(r"[\s（(]", match.group(2).strip())[0]
            fields.setdefault(match.group(1).lower().replace("branch/commit", "commit"), value)
    repo_url = next((v for k, v in fields.items() if k in ("repo", "来源") and v.startswith("http")), None)
    record_license = next((v for k, v in fields.items() if k in ("license", "许可")), None)
    # `MIT License（LICENSE 副本随附）` style values carry prose after the SPDX id.
    if record_license:
        record_license = re.split(r"[\s（(]", record_license.strip())[0]
    # `branch/commit:` may carry a SHA (a real pin) or a branch name (not a pin);
    # `branch:` alone is the same statement in the other field, so both spellings resolve
    # to "branch only, commit never recorded" rather than to silence or to a fake pin.
    revision = next((fields[k] for k in ("commit", "branch") if fields.get(k)), None)
    is_commit_sha = bool(revision and re.fullmatch(r"[0-9a-f]{7,40}", revision))
    return {
        "retiredIn": sha,
        "retiredOn": date,
        "retiredTreeSha": tree or None,
        "sourceRecordPresent": bool(source_md),
        "upstreamRepo": repo_url,
        "sourceRecordLicense": record_license,
        # A branch name is not a revision: `main` cannot be re-fetched byte-identically,
        # so it is recorded as what it is (`upstreamRefWithoutCommit`) and the source stays
        # visibly unresolved rather than claiming a pinned commit.
        "upstreamRevision": revision if is_commit_sha else None,
        "upstreamRefWithoutCommit": None if revision is None or is_commit_sha else revision,
        # Every retired reference must be able to answer "what was pinned?" in one of
        # three honest ways: a commit, a branch that was never pinned to a commit, or the
        # statement that its own source record named neither. The third is generated from
        # the fields the record actually carries, so it cannot become a blanket excuse.
        "revisionStatement": (
            f"commit {revision} recorded in SOURCE.md" if is_commit_sha else
            f"branch `{revision}` only; no commit was recorded at vendoring time" if revision else
            "the retired SOURCE.md names no branch and no commit; fields present: "
            + (", ".join(sorted(fields)) or "none")) if source_md else
            "no SOURCE.md in the retired tree; see provenanceAbsentReason",
    }


def classify(source: dict, tracked: list[str]) -> dict:
    path = str(source.get("path") or "").replace("\\", "/").strip("/")
    prefix = path + "/"
    git_files = sorted(t for t in tracked if t.startswith(prefix))
    disk_count, disk_digest = digest_dir(REPO / path)
    if git_files:
        presence = "IN_REPO"
    elif path.startswith(VOLATILE_ROOT):
        presence = "LOCAL_CACHE_ONLY"
    else:
        presence = "ABSENT_FROM_GIT"
    recorded = source.get("files")
    facts = {
        "presence": presence,
        "gitFiles": len(git_files),
        "diskFiles": disk_count,
        "countMatchesRecord": recorded == (len(git_files) if git_files else disk_count),
        # a cache digest is only meaningful as cache-integrity evidence, which is
        # why `presence` travels with it and why CI on a fresh clone simply sees
        # diskFiles=0 and cannot treat the recorded value as verified.
        "contentDigest": disk_digest if presence in ("IN_REPO", "LOCAL_CACHE_ONLY") else None,
        "pathNamedInIsolationRecord": retired_in_doc(path),
    }
    if presence == "ABSENT_FROM_GIT":
        facts.update(retired_provenance(path))
    return facts


def path_of(source: dict) -> str:
    return str(source.get("path") or "").replace("\\", "/").strip("/")


def main() -> int:
    lock = json.loads(LOCK.read_text(encoding="utf-8"))
    sources = lock.get("sources") or []
    if not sources:
        raise SystemExit("SOURCE_LOCK_UNREADABLE: no sources array")
    tracked = tracked_paths()
    counts = {}
    license_mismatch: list[dict] = []
    for source in sources:
        facts = classify(source, tracked)
        source["presence"] = facts["presence"]
        source["gitFiles"] = facts["gitFiles"]
        source["diskFiles"] = facts["diskFiles"]
        source["contentDigest"] = facts["contentDigest"]
        source["countMatchesRecord"] = facts["countMatchesRecord"]
        source["pathNamedInIsolationRecord"] = facts["pathNamedInIsolationRecord"]
        for key in ("retiredIn", "retiredOn", "retiredTreeSha", "sourceRecordPresent",
                    "upstreamRepo", "sourceRecordLicense", "upstreamRevision",
                    "upstreamRefWithoutCommit", "revisionStatement"):
            if key in facts:
                source[key] = facts[key]
        if "canonicalUrl" not in source and facts.get("upstreamRepo"):
            # The lock's own url field was empty for every retired reference, which is why
            # `url=39/46` read as unfixable: the bytes were gone from the working tree. They
            # are not gone from git history, so the canonical URL is recovered from the
            # SOURCE.md inside the deleted tree and marked with where it came from.
            source["canonicalUrl"] = facts["upstreamRepo"]
            source["canonicalUrlSource"] = (f"recovered from {(facts.get('retiredIn') or '')[:8]}^:"
                                            f"{path_of(source)}/SOURCE.md on 2026-10-08")
        if facts.get("sourceRecordLicense") and facts["sourceRecordLicense"] != source.get("license"):
            license_mismatch.append({
                "id": source["id"],
                "lockSays": source.get("license"),
                "sourceRecordSays": facts["sourceRecordLicense"],
                "readFrom": f"{facts['retiredIn'][:8]}^:{path_of(source)}/SOURCE.md",
            })
        counts[facts["presence"]] = counts.get(facts["presence"], 0) + 1
    unbacked = sorted(s["id"] for s in sources
                      if s["presence"] == "ABSENT_FROM_GIT" and not s["pathNamedInIsolationRecord"])
    lock["presenceAudit"] = {
        "schemaVersion": "design-lab/vendor-presence/v1",
        "method": "git ls-files + filesystem walk; contentDigest is sha256 over "
                  "sorted relpath and per-file sha256 of bytes. Presence is derived "
                  f"from git plus the `{VOLATILE_ROOT}` rule, never from whether this "
                  "machine still has a directory, so a clone recomputes the same value.",
        "presenceMeans": {
            "IN_REPO": "bytes are committed; a clone can recompute contentDigest",
            "LOCAL_CACHE_ONLY": f"bytes live only under `{VOLATILE_ROOT}` (gitignored, "
                                "PROJECT_LOCAL_ROOT) on the machine that acquired them; "
                                "a clone cannot recompute, so this is not absorbed",
            "ABSENT_FROM_GIT": "no bytes anywhere; the record is a historical "
                               "reference, not an absorbed source",
        },
        "counts": dict(sorted(counts.items())),
        # surfaced, not rewritten: why a reference lost its path is an owner call, and
        # silently deleting the record would destroy the only trace it existed.
        "absentReferencesNotNamedInIsolationRecord": unbacked,
        # A retired reference may keep its record only while its provenance is readable:
        # which commit deleted it, the tree that was deleted, and what its own SOURCE.md
        # said. Anything absent here is a reference nobody can re-derive.
        "absentReferencesWithRecoveredProvenance": sorted(
            s["id"] for s in sources
            if s["presence"] == "ABSENT_FROM_GIT" and s.get("retiredTreeSha")),
        # surfaced, not silently merged: the lock and the recovered source record naming a
        # different license is a rights question, and both values are reported so the
        # correction is a decision with evidence rather than a guess.
        "licenseRecordMismatch": license_mismatch,
    }
    # newline="\n": Path.write_text translates "\n" to os.linesep on Windows, which
    # would make this file's bytes platform-dependent and re-dirty the projections on
    # every developer's machine.
    with LOCK.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(lock, ensure_ascii=False, indent=2) + "\n")
    print("SOURCE_LOCK_PRESENCE=WRITTEN " + json.dumps(lock["presenceAudit"]["counts"], sort_keys=True)
          + f" unbacked_absent_references={len(unbacked)}"
          + f" license_record_mismatch={len(license_mismatch)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
