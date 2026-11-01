"""Bind owed PASS records to a commit, but only when the commit can be proven to be that record's fix.

99 PASS records carry no `fixedCommit`. Two bases are tried, and both must pass three guards, because a
wrong SHA in a traceability record is worse than a gap (ERR-125/ERR-134 exist for that reason):

  basis A — regression-operand-introduction: the record promises a regression file that is tracked
           today; `git log --diff-filter=A` names the commit that added it. Accepted only when that
           commit's date is within seven days of the record's own date (most old records carry no date
           at all, so this basis reaches few of them and says so).
  basis B — ledger-entry-introduction: the commit that first wrote this record's id into the ledger.

  guard 1 (bulk): the commit must not add many records. A branch cutover added 86 records across 1,276
          files; my first version of this tool counted that as "+1 record" because it ran
          `git show <c> -- <path>` with the commit placed after the `--`, which reads an empty diff, and
          it would have bound 99 records to a migration. The counter now runs the real diff.
  guard 2 (promise): if the record's `lifecycle.regressionCommand` names a script, that script must
          exist in the candidate commit. The binding gate enforces exactly this, and it caught ERR-124
          promising `node_modules/vitest/vitest.mjs` — an untracked path no commit contains.
  guard 3 (semantics): the commit must change at least one path the record itself names in
          `entrypoint` or in a resolving `regression_test` operand. A commit that writes the record but
          touches nothing it talks about is bookkeeping, not the fix.
  guard 4 (collision): never bind a record to its own `introducedCommit` — ERR-089 was once bound to the
          squash merge that introduced it, and ancestry between the two fields then told a lie.

`verifiedCommit` is never invented here: it stays null until an exact-SHA CI readback covers a head that
contains the record.

Usage:
    python scripts/audit/bind_ledger_fixes_with_guards.py            # dry run
    python scripts/audit/bind_ledger_fixes_with_guards.py --apply
Exit: 0 always; the gap is a finding, not a crash. 2 only if the ledger cannot be read.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys

REPO = pathlib.Path(__file__).resolve().parents[2]
LEDGER = REPO / "taskpacks/current/error-ledger.json"
PATH_IN_LEDGER = "taskpacks/current/error-ledger.json"
OPERAND_RE = re.compile(r"[\w./\\-]*\.(?:py|js|cjs|mjs|ts|tsx|sh|ps1|cmd|rs|json|md|yaml|yml)")
PROMISE_RE = re.compile(r"(?:python|node)\s+(?:-\w+\s+)*([\w./-]+\.(?:py|js|cjs|mjs))")
WINDOW_DAYS = 7


def git(*args: str) -> tuple[int, str]:
    proc = subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, proc.stdout.strip()


def out(*args: str) -> str:
    return git(*args)[1]


def ids_added_by(commit: str) -> int:
    diff = out("show", commit, "--format=", "--unified=0", "--", PATH_IN_LEDGER)
    return len({m.group(1) for m in re.finditer(r'^\+.*"error_id":\s*"(ERR-\d+)"', diff, re.M)})


def files_touched(commit: str) -> set[str]:
    return {line.strip() for line in
            out("show", commit, "--format=", "--name-only", "--root").splitlines() if line.strip()}


def commit_date(commit: str):
    raw = out("show", "-s", "--format=%cI", commit)
    try:
        return dt.datetime.fromisoformat(raw).date()
    except (TypeError, ValueError):
        return None                              # an unparseable date must fail closed


def promise_script(regression_command: str) -> str | None:
    m = PROMISE_RE.search(str(regression_command or ""))
    return m.group(1).lstrip("./") if m else None


def in_tree(commit: str, rel: str) -> bool:
    return git("cat-file", "-e", f"{commit}:{rel}")[0] == 0


def named_paths(record: dict) -> set[str]:
    names: set[str] = set()
    for token in str(record.get("entrypoint") or "").split(","):
        token = token.strip().replace("\\", "/")
        if "/" in token:
            names.add(token)
    for m in OPERAND_RE.findall(str(record.get("regression_test") or "")):
        clean = m.replace("\\", "/").lstrip("./")
        if (REPO / clean).is_file():
            names.add(clean)
    return names


def candidate_commits(record: dict) -> list[tuple[str, str]]:
    """(commit, basis) pairs worth testing for this record, in order of strength."""
    cands: list[tuple[str, str]] = []
    entry = out("log", "--reverse", "--format=%H", "-S", f'"{record["error_id"]}"',
                "--", PATH_IN_LEDGER).splitlines()
    if entry:
        cands.append((entry[0], "ledger-entry-introduction"))
    operand = next((p for p in sorted(named_paths(record)) if in_tree("HEAD", p)
                    and p in str(record.get("regression_test") or "")), None)
    if operand:
        added = out("log", "--diff-filter=A", "--format=%H", "--reverse", "--", operand).splitlines()
        if added:
            cands.append((added[0], f"regression-operand-introduction:{operand}"))
    return cands


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--apply", action="store_true")
    ap.add_argument("--max-ids", type=int, default=3)
    args = ap.parse_args()

    data = json.loads(LEDGER.read_text(encoding="utf-8"))
    bulk_cache: dict[str, int] = {}
    touch_cache: dict[str, set[str]] = {}
    bound, refused = [], []
    for e in data["errors"]:
        if e.get("status_after") != "PASS" or (e.get("lifecycle") or {}).get("fixedCommit"):
            continue
        tried = []
        for sha, basis in candidate_commits(e):
            if sha not in bulk_cache:
                bulk_cache[sha] = ids_added_by(sha)
                touch_cache[sha] = files_touched(sha)
            added, touched = bulk_cache[sha], touch_cache[sha]
            if added > args.max_ids:
                tried.append(f"{sha[:7]}: adds {added} records (migration)")
                continue
            promise = promise_script((e.get("lifecycle") or {}).get("regressionCommand"))
            if promise and not in_tree(sha, promise):
                tried.append(f"{sha[:7]}: promised {promise} is not in that tree")
                continue
            overlap = sorted(p for p in named_paths(e) if p in touched)
            if not overlap:
                tried.append(f"{sha[:7]}: touches nothing the record names")
                continue
            if basis.startswith("regression-operand-introduction"):
                date, record_date = commit_date(sha), str(e.get("date") or "")
                if date is None or not record_date:
                    tried.append(f"{sha[:7]}: undateable operand basis")
                    continue
                if abs((date - dt.date.fromisoformat(record_date)).days) > WINDOW_DAYS:
                    tried.append(f"{sha[:7]}: operand date outside the record's window")
                    continue
            life = e.setdefault("lifecycle", {})
            if life.get("introducedCommit") and sha.startswith(str(life["introducedCommit"])):
                tried.append(f"{sha[:7]}: equals introducedCommit")
                continue
            subject = out("show", "-s", "--format=%s", sha)[:70]
            bound.append({"id": e["error_id"], "commit": sha[:7], "basis": basis,
                          "overlap": overlap[0], "promise": promise, "subject": subject})
            if args.apply:
                life["fixedCommit"] = sha[:7]
                life["bindingBasis"] = (f"{basis}: this commit adds only {added} record(s), it changes "
                                        f"{overlap[0]} which the record names"
                                        + (f", and the promised {promise} exists in it" if promise
                                           else ", and the record promises no script"))
                life["bindingNote"] = (f"bound 2026-10-07 by scripts/audit/"
                                       f"bind_ledger_fixes_with_guards.py; commit subject: {subject}. "
                                       "verifiedCommit stays null until an exact-SHA CI readback covers "
                                       "a head containing this record")
            break
        else:
            refused.append((e["error_id"], " | ".join(tried) or "no candidate commit"))

    if args.apply:
        LEDGER.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n",
                          encoding="utf-8", newline="\n")
    print(f"{'APPLIED' if args.apply else 'DRY RUN'}: bound={len(bound)} refused={len(refused)}")
    for b in bound[:14]:
        print(f"   {b['id']:9s} -> {b['commit']} {b['basis'][:42]:42s} {b['overlap'][:38]}")
    print("  refused (first 12, with every reason tried):")
    for r in refused[:12]:
        print(f"   {r[0]:9s} {r[1][:120]}")
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    raise SystemExit(main())
