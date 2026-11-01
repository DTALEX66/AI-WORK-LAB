# SPDX-License-Identifier: MIT
"""Derive commit-pinned revisions for vendor/sources.lock.json entries.

The lock file records 46 vendored sources with disposition, licence, path and
files -- but no source revision and no structured source URL. AUTHORITY.md §9
requires an ABSORBED source to carry source AND revision, so as it stands none of
these entries can satisfy the rule they were filed under, and no check noticed.

37 of the 46 are recoverable without any network call: the repository URL is
present in the free-text `notes`, and research/candidates/CANDIDATE-TAXONOMY.json
pins `pinnedCommitSHA` per candidate. This script performs that join by exact
normalised repo path only -- never by fuzzy name -- and writes the result plus the
explicit list of what could NOT be recovered.
"""
import json, re, pathlib, sys, io

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8")
REPO = pathlib.Path(".")
URL = re.compile(r"https?://github\.com/([A-Za-z0-9._-]+/[A-Za-z0-9._-]+)")


def norm(raw: str):
    name = raw.strip().lower().rstrip("/")
    name = re.sub(r"^https?://", "", name)
    if name.endswith(".git"):
        name = name[:-4]
    return name if "/" in name and " " not in name else None


def taxonomy_index():
    tax = json.loads((REPO / "research/candidates/CANDIDATE-TAXONOMY.json").read_text(encoding="utf-8"))
    entries = tax.get("candidates") or tax.get("entries") or []
    out = {}
    for e in entries:
        sha = None
        for field in ("pinnedCommitSHA", "pinnedCommit", "commitSha"):
            value = e.get(field)
            if isinstance(value, str) and re.fullmatch(r"[0-9a-fA-F]{7,40}", value.strip()):
                sha = value.strip().lower()
                break
        for field in ("canonicalUrl", "canonicalRepo", "url", "repoUrl"):
            key = norm(e.get(field) or "")
            if key:
                prev = out.get(key)
                if prev is None or (not prev and sha):
                    out[key] = sha
    return out


def build():
    lock = json.loads((REPO / "vendor/sources.lock.json").read_text(encoding="utf-8"))
    tax = taxonomy_index()
    resolved, unresolved = {}, []
    for src in lock.get("sources", []):
        sid = src.get("id")
        found = None
        for raw in URL.findall(src.get("notes") or ""):
            key = norm(raw)
            if key and key in tax:
                found = (key, tax[key])
                break
        if found and found[1]:
            resolved[sid] = {"repo": found[0], "revision": found[1]}
        else:
            unresolved.append({
                "id": sid,
                "disposition": src.get("disposition"),
                "reason": ("no github url recorded in notes" if not URL.findall(src.get("notes") or "")
                           else "url present but no CANDIDATE-TAXONOMY entry"),
            })
    total = len(lock.get("sources", []))
    return {
        "schemaVersion": "design-lab/vendor-revisions/v1",
        "meaning": ("commit-pinned source revisions recovered by exact repository-path join "
                    "against research/candidates/CANDIDATE-TAXONOMY.json. Absence from `sources` "
                    "means NOT VERIFIED, never absence of provenance."),
        "method": "exact normalised github.com/<owner>/<repo> match only; no fuzzy or name-based matching",
        "lockEntries": total,
        "resolvedCount": len(resolved),
        "unresolvedCount": len(unresolved),
        "sources": dict(sorted(resolved.items())),
        "unresolved": sorted(unresolved, key=lambda x: str(x["id"])),
    }


if __name__ == "__main__":
    doc = build()
    dest = REPO / "vendor/sources.revisions.json"
    text = json.dumps(doc, ensure_ascii=False, indent=2) + "\n"
    dest.write_text(text, encoding="utf-8", newline="\n")
    back = json.loads(dest.read_bytes().decode("utf-8"))
    assert back == doc, "written bytes do not round-trip"
    print(f"wrote {dest}: resolved={doc['resolvedCount']} unresolved={doc['unresolvedCount']} "
          f"of {doc['lockEntries']}")
    for u in doc["unresolved"]:
        print(f"  UNRESOLVED {u['id']} [{u['disposition']}]: {u['reason']}")
