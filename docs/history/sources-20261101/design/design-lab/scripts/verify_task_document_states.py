#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-REC-29: task-document state gate (fail-closed).

Answers one question that the repository could not answer before 2026-10-08:
for every task document that exists under the planning and history faces, what
is its declared state, and what makes that declaration true?

The registry it audits (design-lab/config/task-document-states.json) is a
RECORD, not an authority: .project/governance/authority-index.json stays the
classification truth, and this gate fails the moment the two disagree. That is
deliberate — a second mutable truth source is exactly the failure mode AGENTS.md
forbids ("不建第二 ledger").

Checks (all fail-closed):
 1. registry parses, carries task-document-states/v1, and its subordinateTo
    files exist;
 2. every declared document path is a TRACKED file (existence answered from the
    repo, not from this machine's disk);
 3. exactly one role=DISPATCH_ENTRY, its state is CURRENT, and it equals the
    index's taskpackClassificationRule.currentIntegrated;
 4. every state=CURRENT declaration is listed in the index's current array, or
    carries a non-empty indexOmitted reason (an asymmetry must be recorded, not
    smoothed over);
 5. every index current path is declared here;
 6. every tracked file under the audited prefixes is covered by a declaration
    or a prefix rule — no document may sit unclassified, which is what made
    "next round cannot find the task" possible;
 7. imported bytes may never claim CURRENT/DISPATCH_ENTRY, and every state used
    by the import manifest is inside the declared vocabulary;
 8. the files pinned by SHA-256 in scripts/verify_top_level_authority.py are
    declared frozen here (that script is the single source of the pin list);
 9. every REQUESTED declaration carries a non-empty ownerActionPending, and
    every supersededBy / replacement / perFileStateSource target exists;
10. a `.license` sidecar inherits the declaration of its binary instead of
    needing its own entry.

The gate writes nothing.

Usage:
    python design-lab/scripts/verify_task_document_states.py
"""
from __future__ import annotations

import fnmatch
import json
import re
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
REGISTRY = "design-lab/config/task-document-states.json"
INDEX = ".project/governance/authority-index.json"
AUDITED_PREFIXES = (
    "docs/taskpacks/",
    "docs/history/taskpacks/",
    "docs/history/archive-2026-10-19/handoffs/",
    "docs/current/",
    "docs/history/record-imports-2026-10-08/",
)
SCHEMA = "design-lab/task-document-states/v1"


def tracked_files() -> list[str]:
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True,
                         encoding="utf-8", errors="replace").stdout
    return sorted(p for p in out.split("\0") if p)


def is_sidecar(rel: str, declared: set[str]) -> bool:
    return rel.endswith(".license") and rel[: -len(".license")] in declared


def relocations() -> dict[str, str]:
    """`recorded path -> current path` for every document an archive pass moved.

    Frozen records (the Record-import manifest, the pinned R3 ledger snapshot) name the
    path the bytes landed on at the time. Their own bytes are hash-sealed, so the honest
    fix for a move is to resolve the pointer through the archive manifest, never to
    rewrite the record. A path absent from both the tree and the manifest stays a failure.
    """
    table: dict[str, str] = {}
    for manifest in sorted((REPO / "docs/history").glob("archive-*/MANIFEST.json")):
        try:
            data = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        for group in data.get("groups", []):
            for entry in group.get("files", []):
                if entry.get("from") and entry.get("to"):
                    table[entry["from"]] = entry["to"]
    return table


class Checker:
    def __init__(self) -> None:
        self.checks: list[dict] = []

    def add(self, name: str, ok: bool, detail: str) -> None:
        self.checks.append({"check": name, "result": "PASS" if ok else "FAIL", "detail": detail})


def main() -> int:
    ck = Checker()
    files = tracked_files()
    tracked = set(files)
    moved = relocations()

    def resolves(rel: str) -> bool:
        """Tracked where named, or tracked where an archive pass moved it."""
        return rel in tracked or moved.get(rel, rel) in tracked

    registry = None
    index = None
    # 1 ---------------------------------------------------------------------
    try:
        registry = json.loads((REPO / REGISTRY).read_text(encoding="utf-8"))
        assert registry.get("schemaVersion") == SCHEMA, f"schemaVersion != {SCHEMA}"
        missing_parents = [p for p in registry.get("subordinateTo", []) if p not in tracked]
        ck.add("registry-valid", not missing_parents,
               f"docs={len(registry.get('documents', []))} rules={len(registry.get('prefixRules', []))} "
               f"untracked subordinateTo={missing_parents}" if missing_parents
               else f"{len(registry['documents'])} per-file declarations, "
                    f"{len(registry['prefixRules'])} prefix rules, subordinate surface tracked")
    except (OSError, AssertionError, json.JSONDecodeError) as exc:
        ck.add("registry-valid", False, f"cannot read {REGISTRY}: {exc}")
    # 2 ---------------------------------------------------------------------
    if registry:
        dangling = [d.get("path") for d in registry["documents"] if not resolves(d.get("path", ""))]
        ck.add("declared-paths-tracked", not dangling,
               f"untracked declarations: {dangling}" if dangling
               else f"all {len(registry['documents'])} declared paths are tracked files "
                    f"({len([d for d in registry['documents'] if d['path'] not in tracked])} "
                    "resolved through an archive-move manifest)")
        bad_rules = [r.get("glob") for r in registry["prefixRules"]
                     if not any(fnmatch.fnmatch(f, r["glob"]) for f in files)]
        ck.add("prefix-rules-match-something", not bad_rules,
               f"prefix rules matching no tracked file: {bad_rules}" if bad_rules
               else f"{len(registry['prefixRules'])} prefix rules all match tracked files")
    try:
        index = json.loads((REPO / INDEX).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        ck.add("index-readable", False, f"cannot read {INDEX}: {exc}")
    else:
        ck.add("index-readable", True, f"authorityId={index.get('authorityId')}")
    # 3 ---------------------------------------------------------------------
    if registry and index:
        dispatch = [d for d in registry["documents"] if d.get("role") == "DISPATCH_ENTRY"]
        integrated = index.get("taskpackClassificationRule", {}).get("currentIntegrated")
        ok = (len(dispatch) == 1 and dispatch[0].get("state") == "CURRENT"
              and dispatch[0]["path"] == integrated)
        ck.add("single-dispatch-entry", ok,
               f"declared={[d['path'] for d in dispatch]} states={[d.get('state') for d in dispatch]} "
               f"indexCurrentIntegrated={integrated}")
        # 4 -----------------------------------------------------------------
        current_doc = [d for d in registry["documents"] if d.get("state") == "CURRENT"]
        idx_current = set(index.get("current", []))
        off = [d["path"] for d in current_doc if d["path"] not in idx_current
               and not str(d.get("indexOmitted", "")).strip()]
        ck.add("current-matches-index", not off,
               f"declared CURRENT but absent from index.current without a recorded reason: {off}"
               if off else f"{len(current_doc)} CURRENT declarations, "
                           f"{len([d for d in current_doc if d['path'] not in idx_current])} "
                           "carrying an explicit indexOmitted reason")
        # 5 -----------------------------------------------------------------
        declared = {d["path"] for d in registry["documents"]}
        rules = [r["glob"] for r in registry["prefixRules"]]
        covered = [p for p in idx_current
                   if p in declared or any(fnmatch.fnmatch(p, g) for g in rules)]
        unc = [p for p in idx_current if p not in covered]
        ck.add("index-current-all-declared", not unc,
               f"index.current entries with no declaration here: {unc}" if unc
               else f"all {len(idx_current)} index.current paths declared")
        # 6 -----------------------------------------------------------------
        audited = [f for f in files if f.startswith(AUDITED_PREFIXES)]
        undeclared = [f for f in audited if f not in declared
                      and not any(fnmatch.fnmatch(f, g) for g in rules)
                      and not is_sidecar(f, declared)]
        ck.add("no-undeclared-task-document", not undeclared,
               f"{len(undeclared)} tracked task documents carry no declared state: "
               f"{undeclared[:12]}" if undeclared
               else f"{len(audited)} tracked files under the audited prefixes, every one covered")
        # 7 -----------------------------------------------------------------
        vocab = set(registry.get("vocabulary", {}))
        manifest_rel = None
        for r in registry["prefixRules"]:
            manifest_rel = r.get("perFileStateSource") or manifest_rel
        problems: list[str] = []
        if manifest_rel:
            if manifest_rel not in tracked:
                problems.append(f"per-file state source not tracked: {manifest_rel}")
            else:
                try:
                    man = json.loads((REPO / manifest_rel).read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    problems.append(f"import manifest unreadable: {exc}")
                else:
                    entries = man.get("entries", [])
                    landed = [e for e in entries if e.get("action") == "LANDED"]
                    for e in entries:
                        st = e.get("state")
                        if st not in vocab:
                            problems.append(f"state outside vocabulary: {st}")
                            break
                    for e in landed:
                        tgt = e.get("target")
                        if not resolves(tgt):
                            problems.append(f"landed row not tracked: {tgt}")
                            break
                        if e.get("state") in ("CURRENT", "CURRENT_BUT_DRIFTED") \
                                or e.get("role") == "DISPATCH_ENTRY":
                            problems.append(f"imported bytes claim current authority: {tgt}")
                            break
                    ck.add("import-manifest-consistent", not problems,
                           f"{len(landed)} landed rows / {len(entries)} manifest rows: "
                           + ("; ".join(problems) if problems else "every state inside the "
                              "vocabulary, every landed byte tracked, nothing claiming CURRENT"))
        else:
            ck.add("import-manifest-consistent", False, "no perFileStateSource declared")
    # 8 ---------------------------------------------------------------------
    pin_src = REPO / "scripts" / "verify_top_level_authority.py"
    if registry and pin_src.is_file():
        text = pin_src.read_text(encoding="utf-8")
        block = text.split("R2_RELEASE_HASHES = {", 1)
        pinned: list[str] = []
        if len(block) == 2:
            for line in block[1].split("}", 1)[0].splitlines():
                part = line.split('"')
                if len(part) >= 3 and part[1].count("/") >= 0 and part[1].endswith((".md", ".json")):
                    pinned.append(part[1])
        declared_by_path = {d["path"]: d for d in registry["documents"]}
        bad = [p for p in pinned if not declared_by_path.get(p, {}).get("frozen")]
        ck.add("pinned-files-declared-frozen", bool(pinned) and not bad,
               f"pinned={len(pinned)} not declared frozen={bad}" if bad or not pinned
               else f"all {len(pinned)} SHA-256-pinned release files declared frozen")
    # 9 ---------------------------------------------------------------------
    if registry:
        req = [d["path"] for d in registry["documents"]
               if d.get("state") == "REQUESTED" and not str(d.get("ownerActionPending", "")).strip()]
        rules_req = [r["glob"] for r in registry["prefixRules"]
                     if r.get("state") == "REQUESTED" and not str(r.get("ownerActionPending", "")).strip()]
        targets = []
        for item in registry["documents"] + registry["prefixRules"]:
            for key in ("supersededBy", "replacement", "perFileStateSource"):
                val = item.get(key)
                if val:
                    targets.append(val)
        dead = sorted({t for t in targets if not resolves(t)})
        ok = not req and not rules_req and not dead
        ck.add("reasons-and-pointers-complete", ok,
               f"REQUESTED without ownerActionPending={req + rules_req} dead pointers={dead}"
               if not ok else f"REQUESTED entries all state the pending owner ruling; "
                              f"{len(targets)} pointers all resolve to tracked files")
    # 11 -------------------------------------------------------------------
    # The accretion defect, checked by name shape rather than by a list of known offenders. A
    # dated sibling of the canonical entry is how the old copies got there in the first place:
    # the entry was minted per round, so last round's file stayed in docs/current/ and kept being
    # cited as "the current one". One dated copy is enough to restart that loop.
    rule = (registry or {}).get("promptEntryRule") or {}
    canonical = str(rule.get("canonical") or "")
    if canonical and canonical in tracked:
        stem, _, ext = canonical.rpartition(".")
        pattern = re.compile(re.escape(stem) + r"-\d{4}-\d{2}-\d{2}\." + re.escape(ext) + r"$")
        dated = sorted(f for f in files if pattern.match(f))
        ck.add("entry-not-dated-again", not dated,
               f"dated siblings of {canonical}: {dated}" if dated
               else f"no dated sibling of {canonical} exists")
    # 12 -------------------------------------------------------------------
    # Dangling references in the surfaces that direct a session. A handoff may quote an old path
    # (that is a record of what was said); the guidance surfaces may not, because a path there is
    # an instruction, and an instruction pointing at moved bytes is the whole complaint this
    # check exists to make impossible.
    guidance = [f for f in ("AGENTS.md", "README.md", "AUTHORITY.md",
                            "docs/current/NEXT-AGENT-PROMPT.md") if f in tracked]
    if guidance:
        ref = re.compile(r"(?<![\w/.-])(docs/[A-Za-z0-9_./-]+\.(?:md|json))")
        dangling = []
        for rel in guidance:
            try:
                text = (REPO / rel).read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for match in ref.finditer(text):
                target = match.group(1)
                if target not in tracked:
                    dangling.append(f"{rel}:{target}")
        ck.add("guidance-paths-resolve", not dangling,
               f"dangling references: {sorted(set(dangling))[:4]}" if dangling
               else f"{len(guidance)} guidance surfaces, every docs/ path they name is tracked")

    for c in ck.checks:
        print(f"{c['result']:6s} {c['check']:34s} {c['detail']}")
    failed = [c["check"] for c in ck.checks if c["result"] != "PASS"]
    print(f"TASK_DOC_STATE_GATE={'PASS' if not failed else 'FAIL'} "
          f"checks={len(ck.checks)} failed={failed or 'none'}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
