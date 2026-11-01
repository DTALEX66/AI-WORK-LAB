"""Adjudicate every unbound PASS record whose recorded check contains a gone path.

"PATH_GONE" as a single label per record hides three different situations: the guard was moved (so the claim
still has a home and only the citation is stale), the guard was deleted outright (so the PASS has no check
behind it any more), and only one operand of a multi-operand command is gone while the rest still resolve.
This separates them by looking at every operand the command names, by searching the tree for the missing
basename, and by asking git whether that exact path was ever deleted.
"""
import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TARGETS = ROOT / "docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json"
TRIAGE = ROOT / "docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json"
OUT = ROOT / "docs/audits/LEDGER_GONE_GUARD_ADJUDICATION_2026-10-07.json"

targets = {r["errorId"]: r for r in json.loads(TARGETS.read_text(encoding="utf-8"))["rows"]}
triage = json.loads(TRIAGE.read_text(encoding="utf-8"))
tracked = subprocess.run(["git", "ls-files"], cwd=ROOT, capture_output=True, text=True,
                         encoding="utf-8", errors="replace").stdout.split()
by_name: dict[str, list[str]] = {}
for path in tracked:
    by_name.setdefault(Path(path).name, []).append(path)


def was_deleted(path: str) -> list[str]:
    return subprocess.run(["git", "log", "--format=%h %aI %s", "--diff-filter=D", "--", path],
                          cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout.strip().splitlines()[:2]


rows = []
for eid in [r["errorId"] for r in triage["rows"] if r["state"] == "PATH_GONE"]:
    row = targets[eid]
    operands = row.get("operands") or []
    # The per-operand category is GONE, not the row label PATH_GONE - and `all()` over an empty list is
    # True, so matching the wrong word made every record read as "moved" in a first version of this tool.
    # A verdict now requires a non-empty gone list.
    gone_all = [o["operand"] for o in operands if o.get("category") == "GONE"]
    live = [o["operand"] for o in operands if o.get("category") == "RESOLVES"]
    # The upstream matcher calls any slash-containing token a path, so the GONE list also holds a URL
    # (`http://tauri.localhost`), a fraction (`3/3`), an identifier pair (`P0-02/P0-03`) and a bare
    # directory (`apps/`, which git never tracks and so was never "deleted"). Those are matcher
    # false-negatives, not lost guards, and they must not be counted as either.
    file_suffixes = (".py", ".js", ".ts", ".tsx", ".mjs", ".cjs", ".json", ".md", ".yaml", ".yml",
                     ".sh", ".ps1", ".txt", ".html", ".css")
    not_paths, gone = [], []
    for token in gone_all:
        if "://" in token or re.fullmatch(r"\d+(?:/\d+)+", token) or not token.lower().endswith(file_suffixes):
            not_paths.append(token)
        else:
            gone.append(token)
    if not_paths:
        base = {"notPathTokensTreatedAsGone": not_paths}
    else:
        base = {}
    if not gone:
        rows.append({"errorId": eid, "verdict": "GONE_LABEL_WITHOUT_A_GONE_FILE_OPERAND",
                     "goneOperands": [], "stillResolvingOperands": live,
                     "sameNameNowTracked": {}, "deletionCommits": {},
                     "command": row.get("command", "")[:160], **base})
        continue
    moved = {g: by_name.get(Path(g).name, []) for g in gone}
    deletions = {g: was_deleted(g) for g in gone if not by_name.get(Path(g).name)}
    verdict = ("MOVED_ONLY_CITATION_STALE" if all(moved[g] for g in gone)
               else "PARTIALLY_GONE" if live
               else "DELETED_NO_SUCCEEDER")
    rows.append({"errorId": eid, "verdict": verdict, "goneOperands": gone,
                 "stillResolvingOperands": live,
                 "sameNameNowTracked": {g: moved[g] for g in gone if moved[g]},
                 "deletionCommits": {g: deletions[g] for g in gone if deletions.get(g)},
                 "command": row.get("command", "")[:160], **base})

doc = {"schemaVersion": "work-lab/ledger-gone-guard-adjudication/v1",
       "tool": "scripts/audit/adjudicate_gone_guards.py",
       "readOnly": True,
       "whyItMatters": "a PASS record whose check no longer exists is a claim without a test; whether the "
                       "check moved or died decides if the citation or the status is what must change",
       "counts": {"records": len(rows),
                  "verdicts": {v: sum(1 for r in rows if r["verdict"] == v) for v in
                               sorted({r["verdict"] for r in rows})}},
       "rows": rows}
OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps(doc["counts"], ensure_ascii=False))
for r in rows:
    print(f"  {r['errorId']:9s} {r['verdict']:26s} gone={r['goneOperands'][:2]} "
          f"live={len(r['stillResolvingOperands'])} moved={list(r['sameNameNowTracked'].values())[:1]}")
print("adjudication ->", OUT)
