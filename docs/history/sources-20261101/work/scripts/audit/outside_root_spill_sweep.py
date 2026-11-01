"""Sweep the places this project's tools can leave bytes outside the Git root, and test attribution.

`.project/governance/project-data-boundary.json` says every project artifact stays inside the Git root
and that any write outside it is a spill that must be traceable, locatable, cleanable and migratable,
recorded one JSONL line per write in `.project-local/artifacts/spill-ledger.jsonl`. That is a
declaration; this is the measurement against it, in two independent directions:

  attribution — does anything outside the Git root carry a WORK-LAB-attributable name? Probed at the
                four declared shared roots, the tool caches the sanctioned runners would touch
                (uv interpreter installs, uv/pip caches, cargo registry, HF and modelscope caches,
                ollama blobs), `%TEMP%`, and the sibling project directories. A name hit is a spill to
                explain; a miss is a negative proven by enumeration, scoped to exactly the places a
                Python/Node/Rust tool on this machine writes.
  ledger      — does each recorded line satisfy the declared rule (timestamp, actor, action, source,
                target, the four spill properties), and is each `outOfRoot: true` target outside the
                Git root as claimed?

The tracked summary carries labels, counts and digests of path sets — never machine-local absolute
paths, which stay in the ignored detail report per the boundary declaration. Read-only: it writes no
file outside the Git root and never follows links or junctions.

Usage: python scripts/audit/outside_root_spill_sweep.py [--json-out PATH]
Exit: 0 when no spill-attributable finding and no ledger violation; 1 otherwise; 2 on a scan error.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
BOUNDARY = REPO / ".project/governance/project-data-boundary.json"
EXTERNAL_INDEX = REPO / ".project/governance/external-libraries-index.json"
SPILL_LEDGER = REPO / ".project-local" / "artifacts" / "spill-ledger.jsonl"


def _ledger_digest(row: dict) -> str:
    """Content identity for one ledger line, so a waiver cannot drift onto a different record."""
    basis = json.dumps({"at": row.get("at"), "actor": row.get("actor"), "action": row.get("action"),
                        "tool": row.get("tool"), "manifest": row.get("manifest")},
                       sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(basis.encode("utf-8")).hexdigest()


# Append-only history cannot be edited to look compliant, so pre-rule lines are named here with the reason
# each one is let stand. The list can only shrink -- a new non-conforming line is a violation, and a waived
# line that later turns out to be absent is caught by the coverage test that counts these digests.
LEDGER_LEGACY_WAIVERS: dict[str, str] = {
    # written 2026-10-07T08:24:53Z by the tool before its own ledger line carried the
    # declared ten fields; the tool is fixed in this round, and the historical line stays as
    # evidence rather than being rewritten to look compliant
    "b592f9dcc201ed68e37ce5f1137ca3c87b3e6170badb8c0ea873901c124a5480": (
        "pre-fix chrome-profile release record (actor=scripts/audit/release_chrome_profile_residue.py, "
        "at=20261007T082453Z): emitted ten informative fields but not the declared ones; the manifest it "
        "names still lists every file by path, length and sha256"),
}
TRACKED_SUMMARY = REPO / "docs" / "audits" / "OUTSIDE_ROOT_SPILL_SWEEP_2026-10-07.json"
DETAIL_OUT_DEFAULT = ".project-local/runs/convergence-20261007-h/spill_sweep_detail.json"

ATTRIBUTION = re.compile(r"(work[-_ ]?lab|wl3|workflow[-_]assistance|WORK-LAB|worklab|atlas-gap)", re.I)
SKIP_DIRS = {"node_modules", ".git", "site-packages", "venv", ".venv", "__pycache__",
             "target", "dist", "build"}

# A name hit outside the Git root is not one kind of thing. The sweep used to answer "SPILL_TO_EXPLAIN"
# for all of them, which reported the owner's own handover material and the agent runtime's scratch with
# the same verb as a spill this repository authored and left unrecovered. Each rule below therefore
# carries the tracked record that justifies the class, and a hit no rule matches stays UNADJUDICATED
# and keeps the run failing — the classification can never be used to hide a finding.
ADJUDICATION_RULES = [
    {"rule": "record-owner-material", "category": "siblingProject", "under": "Record",
     "namePrefix": None, "cls": "inboundOwnerMaterial", "projectAuthored": False, "recoveredIn": False,
     "basis": "`.project/governance/blueprint-coverage.json` lists two files under this root as "
              "authoritative inputs (the 20261006 blueprint docx and the authority-repair txt); "
              "OPEN-TASK-REGISTER row AG-20b describes `D:\\All projects\\Record` as the user's Record "
              "material root, read-only, and AG-19b enumerated it under that authorization",
     "disposition": "left exactly where it is — AGENTS.md forbids migrating, cleaning or writing "
                    "anything outside this project"},
    {"rule": "design-lab-handoff-document", "category": "siblingProject", "under": "DESIGN-LAB",
     "namePrefix": "WORK-LAB-DESIGN-MODULE-FINAL-HANDOFF", "cls": "siblingProjectOwnedDocument",
     "projectAuthored": None, "recoveredIn": False,
     "basis": "this repository archives that project's own `V4_MIGRATION_FINAL_STATE.md` at "
              "`docs/history/archive/session-history/DESIGN-LAB/docs/V4_MIGRATION_FINAL_STATE.md`, "
              "whose document table lists this file as an accurate historical record to keep (准确（历史"
              "记录，保留）)",
     "disposition": "left in place; authorship in either direction is not established by the sweep, "
                    "and DESIGN-LAB owns its own domain per AGENTS.md"},
    {"rule": "authority-reference-temp-residue", "category": "runtimeScratch", "under": "auth-ref-",
     "namePrefix": None, "cls": "projectAuthoredTempResidue", "projectAuthored": True,
     "recoveredIn": False,
     "basis": "written by `tests/ci/test_project_authority_reference.py::_make_fixture` through "
              "`tempfile.mkdtemp(prefix=\"auth-ref-\")` with no `dir=`, i.e. by this repository's own "
              "test code into the user's temp directory (ERR-140)",
     "disposition": "root cause fixed (the fixture is now built under `.project-local/runs/`) and the "
                    "19 leaked mirrors released with a per-file manifest by "
                    "`scripts/maintenance/release_authority_reference_temp_residue.py`; the rule stays "
                    "so a recurrence fails the verdict"},
    {"rule": "client-runtime-preview-scratch", "category": "runtimeScratch",
     "under": "codex-file-preview-", "namePrefix": None, "cls": "clientRuntimeScratch",
     "projectAuthored": False, "recoveredIn": False,
     "basis": "`git grep codex-file-preview` over the tracked tree returns nothing, so no code in this "
              "repository writes that prefix; it is the managed client's own preview scratch for a "
              "project taskpack zip",
     "disposition": "disclosed, not deleted — cleaning another program's scratch is outside this "
                    "project's authority"},
    {"rule": "shared-root-dependency-register", "category": "declaredSharedRoot",
     "under": "docs", "namePrefix": "WORK-LAB-SHARED-DEPENDENCIES-2026-08-15.md",
     "cls": "projectAuthoredPreLedgerOriginal", "projectAuthored": True, "recoveredIn": True,
     "basis": "the file self-identifies as WORK-LAB-authored (`来源项目：WORK-LAB`) and predates the "
              "spill ledger, whose earliest line is 2026-10-06, so no per-write record of it exists; "
              "it was mirrored in byte-identically (3,763 B, sha256 3a71b7be…) by "
              "`scripts/maintenance/recover_shared_root_original.py` and registered as a recovered "
              "original",
     "disposition": "the repository now holds the bytes; the declared-root original is left untouched "
                    "as the authoritative source"},
]


def classify_hit(category: str, under: str, name: str) -> dict | None:
    """The first adjudication rule that covers this hit, or None when nothing justifies it yet."""
    under = under or ""
    for r in ADJUDICATION_RULES:
        if r["category"] != category:
            continue
        if r["under"] and not under.startswith(r["under"]):
            continue
        prefix = r["namePrefix"]
        if prefix and not name.startswith(prefix):
            continue
        return r
    return None


FORBIDDEN_PREFIXES = ("E:\\", "F:\\", "E:/", "F:/")


def forbidden_hit(path: object) -> bool:
    """True when a scan target falls inside a protected data volume.

    E:/ and F:/ are denied by `.project/governance/project-data-boundary.json` without an explicit
    per-path, per-operation authorization, and that applies to a read-only enumeration too — so this
    is checked before any walk, and the gate refuses the whole run if a probe ever resolves there.
    """
    return str(path).startswith(FORBIDDEN_PREFIXES)


def env_root(*parts: str) -> Path | None:
    for base_name in ("APPDATA", "LOCALAPPDATA", "USERPROFILE", "TEMP", "CARGO_HOME", "HOME"):
        base = os.environ.get(base_name)
        if not base:
            continue
        p = Path(base, *parts)
        if p.exists():
            return p
    return None


def probe_roots() -> list[tuple[str, Path, str]]:
    declared = json.loads(EXTERNAL_INDEX.read_text(encoding="utf-8")).get("sharedRoots", {})
    out = [("declared:" + k, Path(v), "declared shared root for material libraries")
           for k, v in declared.items()]
    out += [
        ("uv-managed-python", env_root("uv", "python") or Path(r"C:/nonexistent-uv"),
         "uv downloads CPython builds here; the sanctioned runner calls `uv venv --python 3.12`"),
        ("uv-cache", env_root("uv", "cache") or env_root("uv", "data", "cache")
         or env_root("uv", "dirs", "cache") or Path(r"C:/nonexistent-uv-cache"), "uv wheel/download cache"),
        ("pip-cache", env_root("pip", "Cache") or env_root("pip", "cache")
         or Path(r"C:/nonexistent-pip-cache"), "pip http cache"),
        ("cargo-registry", Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))) / "registry"
         if (Path(os.environ.get("CARGO_HOME", str(Path.home() / ".cargo"))) / "registry").exists()
         else Path(r"C:/nonexistent-cargo"), "shared cargo registry"),
        ("huggingface-cache", env_root(".cache", "huggingface") or Path(r"C:/nonexistent-hf"),
         "HF hub cache"),
        ("modelscope-cache", env_root(".cache", "modelscope") or Path(r"C:/nonexistent-ms"),
         "modelscope cache"),
        ("ollama-models", env_root(".ollama", "models", "blobs") or Path(r"C:/nonexistent-ollama"),
         "ollama content-addressed blobs"),
        ("temp", Path(os.environ.get("TEMP", str(Path.cwd()))) if os.environ.get("TEMP")
         else Path(r"C:/nonexistent-temp"), "only WORK-LAB-named entries are reported here"),
    ]
    siblings = REPO.parent  # the directory holding this checkout and its sibling projects
    out.append(("sibling-projects", siblings, "other checkouts under the same parent directory"))
    return out


def measure(label: str, root: Path, max_depth: int = 3, name_only: bool = False,
            exclude: Path | None = None) -> dict:
    """Enumerate names to a bounded depth.

    Deliberately bounded: the declared shared roots hold 45 GB of model weights and the sibling
    directory holds other people's projects. A full recursive byte walk would take minutes and would
    still not justify saying "no spill anywhere" — so the probe reports how far it actually looked,
    and the verdict below is phrased over the enumerated set only. Name matching is what detects an
    attributable spill; sizes are context, not the claim.
    """
    if not root.is_dir():
        return {"probe": label, "root": str(root), "exists": False}
    base_depth = len(root.parts)
    entries = files = 0
    total = 0
    newest = 0.0
    hits = []
    truncated = False
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dp = Path(dirpath)
        depth = len(dp.parts) - base_depth
        if depth >= max_depth and dirnames:
            truncated = True          # children existed here but were not entered
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames
                       if d not in SKIP_DIRS and not (dp / d).is_symlink()]
        if exclude is not None and dp == root:
            # this checkout is a sibling of itself; counting it would turn the sweep into a hit on
            # the very repository that is doing the looking
            dirnames[:] = [d for d in dirnames if (root / d) != exclude]
        entries += len(dirnames) + len(filenames)
        if ATTRIBUTION.search(dp.name) and depth > 0:
            hits.append({"kind": "dir-name", "relative": dp.name, "depth": depth})
        for f in filenames:
            files += 1
            if ATTRIBUTION.search(f):
                hits.append({"kind": "file-name", "relative": f[:120], "under": dp.name})
            if name_only:
                continue
            try:
                st = (dp / f).stat()
            except OSError:
                continue
            total += st.st_size
            newest = max(newest, st.st_mtime)
        if entries > 200000:
            truncated = True
            break
    return {"probe": label, "root": str(root), "exists": True, "maxDepth": max_depth,
            "nameOnly": name_only, "truncatedAtCap": truncated, "files": files,
            "bytes": total if not name_only else None,
            "newestMtime": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(newest))
            if newest else None, "attributionHits": len(hits), "hits": hits,
            "sampleHits": hits[:25]}


def ledger_review() -> dict:
    if not SPILL_LEDGER.is_file():
        return {"present": False}
    lines = [json.loads(l) for l in SPILL_LEDGER.read_text(encoding="utf-8").splitlines() if l.strip()]
    # The field list is read from the declaration that defines it, not restated here. The sweep used to
    # hardcode eleven names while `project-data-boundary.json` declares ten, so the verifier enforced a
    # superset of the contract: a line could be faithful to the declared schema and still be convicted,
    # and nobody could tell which of the two was authoritative without reading both.
    declared = json.loads(BOUNDARY.read_text(encoding="utf-8"))
    required = tuple(declared["spillGovernance"]["ledger"]["requiredFields"])
    problems = []
    for i, r in enumerate(lines):
        if _ledger_digest(r) in LEDGER_LEGACY_WAIVERS:
            continue
        missing = [f for f in required if f not in r]
        if missing:
            problems.append({"line": i + 1, "problem": f"missing fields {missing}"})
        if r.get("outOfRoot") is True:
            target = str(r.get("target") or "")
            if not target:
                problems.append({"line": i + 1, "problem": "outOfRoot=true with no target"})
            # the declaration's own rule for an out-of-root line: a reversibility statement, in whatever
            # field the writer chose, so prose like `recoverability` is not silently treated as absent
            if not any(str(r.get(field) or "").strip()
                       for field in ("reversible", "recoverability", "reversibility", "migrate")):
                problems.append({"line": i + 1,
                                 "problem": "outOfRoot=true carries no reversibility statement"})
            if "WORK-LAB" in target or "work-lab" in target:
                # a recorded out-of-root spill naming this project must be locatable, not a bare phrase
                if not re.search(r"[A-Za-z]:[\\/]|\\$[A-Z_]+\\|\$[A-Z_]+/", target):
                    problems.append({"line": i + 1,
                                     "problem": "spill target is not a resolvable path"})
    return {"present": True, "lines": len(lines),
            "outOfRootTrue": sum(1 for r in lines if r.get("outOfRoot") is True),
            "inRoot": sum(1 for r in lines if not r.get("outOfRoot")),
            "dates": sorted({str(r.get("at", ""))[:10] for r in lines}),
            "problems": problems}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--json-out", default=DETAIL_OUT_DEFAULT)
    ap.add_argument("--summary", default=str(TRACKED_SUMMARY))
    args = ap.parse_args()

    forbidden = [str(x) for x in json.loads(BOUNDARY.read_text(encoding="utf-8"))
                 .get("spillGovernance", {}).get("protectedDataVolume", {}).values()]
    results = []
    for label, root, why in probe_roots():
        if forbidden_hit(root):
            print(f"REFUSED_FORBIDDEN_ROOT {label} -> {root}")
            return 2
        category = ("declaredSharedRoot" if label.startswith("declared:")
                    else "runtimeScratch" if label == "temp"
                    else "siblingProject" if label == "sibling-projects"
                    else "toolCache")
        if label == "sibling-projects":
            res = measure(label, root, max_depth=1, name_only=True, exclude=REPO)
        else:
            res = measure(label, root, max_depth=1 if label == "temp" else 3,
                          name_only=(label == "temp"))
        res["whyScanned"] = why
        res["category"] = category
        for hit in res.get("sampleHits", []):
            hit["probeCategory"] = category
        results.append(res)

    def tally(*categories: str) -> int:
        """Total hits from each probe's own counter — never the length of an example list.

        `sampleHits` is capped, which once made `spillHits` report 8 where the probes had counted 34.
        """
        return sum(r.get("attributionHits", 0) for r in results if r["category"] in categories)

    adjudicated = []
    for r in results:
        for h in r.get("hits", []):
            under = h.get("under", "")
            if r["category"] == "runtimeScratch":
                # %TEMP% entries carry a random suffix; the tracked record publishes the stable
                # prefix only, so an unadjudicated hit cannot leak a machine-specific token either
                under = re.sub(r"-[A-Za-z0-9_]{6,}$", "-", under)
            rule = classify_hit(r["category"], under, h["relative"])
            row = {"probe": r["probe"], "category": r["category"], "kind": h["kind"],
                   "under": under, "relative": h["relative"]}
            if rule is None:
                row.update({"rule": None, "class": "UNADJUDICATED", "projectAuthored": None,
                            "recoveredIn": False})
            else:
                row.update({"rule": rule["rule"], "class": rule["cls"],
                            "projectAuthored": rule["projectAuthored"],
                            "recoveredIn": rule["recoveredIn"]})
            adjudicated.append(row)
    by_class: dict[str, int] = {}
    for row in adjudicated:
        by_class[row["class"]] = by_class.get(row["class"], 0) + 1
    unadjudicated = [row for row in adjudicated if row["class"] == "UNADJUDICATED"]
    unrecovered = [row for row in adjudicated
                   if row["projectAuthored"] is True and not row["recoveredIn"]]
    spill_total = tally("toolCache", "siblingProject")
    disclosed_total = tally("declaredSharedRoot", "runtimeScratch")
    digest = hashlib.sha256("\n".join(sorted(f"{r['probe']}:{r.get('files', 0)}:{r.get('bytes')}"
                                             for r in results)).encode("utf-8")).hexdigest()
    detail = {"schemaVersion": "work-lab/outside-root-spill-sweep/v1",
              "at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
              "tool": "scripts/audit/outside_root_spill_sweep.py",
              "gitRoot": str(REPO), "probes": results,
              "adjudicated": adjudicated, "ledger": ledger_review()}
    out = REPO / args.json_out
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = {"schemaVersion": "work-lab/outside-root-spill-sweep-summary/v3",
               "at": detail["at"], "tool": detail["tool"],
               "scopeStatement": ("enumerated every declared shared root plus the tool caches this "
                                  "project's sanctioned runners can reach, %TEMP% and the sibling "
                                  "project directories, without following links or junctions and "
                                  "without entering E:/ or F:/ (the forbidden data volumes). "
                                  "Depth-bounded name matching: the summary reports how far it "
                                  "looked, and a cap hit is disclosed, not averaged away."),
               "stateDigest": digest,
               "counts": {"probes": len(results),
                          "probesPresent": sum(1 for r in results if r.get("exists")),
                          "probesTruncatedAtDepthCap": sum(1 for r in results
                                                           if r.get("truncatedAtCap")),
                          "spillHitsInToolCachesOrSiblings": spill_total,
                          "namedButDisclosedElsewhere": disclosed_total,
                          "hitsTotal": len(adjudicated),
                          "hitsByClass": by_class,
                          "unadjudicatedHits": len(unadjudicated),
                          "projectAuthoredUnrecovered": len(unrecovered),
                          "ledgerLines": detail["ledger"].get("lines", 0),
                          "ledgerOutOfRoot": detail["ledger"].get("outOfRootTrue", 0),
                          "ledgerViolations": len(detail["ledger"].get("problems", []))},
               "probes": [{"probe": r["probe"], "category": r["category"],
                           "exists": r.get("exists", False), "files": r.get("files", 0),
                           "bytes": r.get("bytes"), "maxDepth": r.get("maxDepth"),
                           "nameOnly": r.get("nameOnly"),
                           "truncatedAtCap": r.get("truncatedAtCap", False),
                           "newestMtime": r.get("newestMtime"),
                           "attributionHits": r.get("attributionHits", 0)}
                          for r in results],
               "adjudicationRules": [{k: r[k] for k in
                                      ("rule", "category", "under", "namePrefix", "cls",
                                       "projectAuthored", "recoveredIn", "basis", "disposition")}
                                     for r in ADJUDICATION_RULES],
               "hits": adjudicated[:40],
               "unadjudicatedHits": unadjudicated[:20],
               "disclosure": ("A WORK-LAB-attributable name outside the Git root is not one kind of "
                              "thing, and the sweep no longer answers with one verb. The owner's "
                              "handover material under the Record root and the sibling project's own "
                              "historical handoff are inbound and are never touched, per AGENTS.md; "
                              "the client runtime's preview scratch is not this project's to delete; "
                              "the declared shared-root dependency register was mirrored in "
                              "byte-identically and registered, with the original left as the "
                              "authoritative source; and the %TEMP% authority-reference residue was "
                              "authored by this repository's own test, so it was released with a "
                              "per-file manifest and its root cause fixed. Every hit is matched to a "
                              "rule whose basis names the tracked record behind it; anything left "
                              "unmatched fails the run instead of being folded into a clean verdict."),
               "verdict": ("NAMED_OUTSIDE_ROOT_UNADJUDICATED" if unadjudicated
                           else "PROJECT_AUTHORED_SPILL_OUTSIDE_ROOT" if unrecovered
                           else "LEDGER_RULE_VIOLATION" if detail["ledger"].get("problems")
                           else "NAMED_OUTSIDE_ROOT_ADJUDICATED_AND_RECOVERED"
                           if adjudicated else "NO_NAMED_HIT_OUTSIDE_ROOT"),
               "verdictMeaning": ("every name hit outside the Git root is matched to a rule with a "
                                  "tracked basis, none of them is a project-authored write left "
                                  "unrecovered, and the spill ledger violates no declared field"),
               "notClaimed": ["a name-based sweep finds spills that carry this project's name; a file "
                              "written outside the root under a generic cache key is invisible to it. "
                              "The stronger property is the ledger, which is append-per-write",
                              "the tracked summary holds no machine-local absolute paths; those stay "
                              "in the ignored detail report per the boundary declaration",
                              "nothing outside the Git root was modified by this tool",
                              "the enumerated roots were walked to a bounded depth; probes flagged "
                              "truncatedAtCap were not searched below that depth"]}
    Path(args.summary).write_bytes(json.dumps(summary, ensure_ascii=False, indent=2)
                                   .replace("\n", "\r\n").encode())
    print(f"probes={len(results)} present={summary['counts']['probesPresent']} "
          f"truncated={summary['counts']['probesTruncatedAtDepthCap']} "
          f"hits={len(adjudicated)} unadjudicated={len(unadjudicated)} "
          f"projectAuthoredUnrecovered={len(unrecovered)} "
          f"spillHits={spill_total} disclosedNamedOutsideRoot={disclosed_total} "
          f"ledgerLines={summary['counts']['ledgerLines']} "
          f"ledgerViolations={summary['counts']['ledgerViolations']}")
    for r in results:
        size = r.get("bytes")
        print(f"  {r['probe']:24s} {r['category']:18s} exists={str(r.get('exists', False)):5s} "
              f"files={r.get('files', 0):>8} bytes={(size or 0):>14,} "
              f"depth={r.get('maxDepth')} trunc={str(r.get('truncatedAtCap', False)):5s} "
              f"newest={r.get('newestMtime')} hits={r.get('attributionHits', 0)}")
    print(f"VERDICT {summary['verdict']}")
    for cls, n in sorted(by_class.items()):
        print(f"  {n:>4}  {cls}")
    print(f"summary -> {Path(args.summary).relative_to(REPO).as_posix()}")
    print(f"detail  -> {out.relative_to(REPO).as_posix()}")
    return 1 if (unadjudicated or unrecovered
                  or summary["counts"]["ledgerViolations"]) else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
