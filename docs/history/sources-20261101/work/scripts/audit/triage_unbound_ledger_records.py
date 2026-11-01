"""Read-only triage of the ledger's unbound PASS records.

Records that claim PASS but carry no fixedCommit leave nothing pinning which change made them true. This
partitions them by what is checkable today: whether the record's own regression command points at a file
that exists, and when that file entered the tree relative to the record's date. The count is printed by the
run, never written here, because a number in this docstring goes stale the moment a row is appended.

Run AFTER `ledger_regression_command_targets.py`. This reads that audit's labels as the authority for where a
record's operand lives; regenerating this file against a stale targets audit writes states that
`test_ledger_unbound_triage.py` then contradicts (measured 2026-10-10: 'RESOLVES' vs 'NOT_IN_TARGETS_AUDIT').

It binds nothing. A fix commit is only honest when the record points at it; where the guard file predates
the record by many commits the candidate is ambiguous and must be decided per record, not in a batch — that
is the ERR-16 failure mode (a binder generating plausible provenance faster than a gate can reject it).
"""
import json
import subprocess
from collections import Counter
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
LEDGER = ROOT / "taskpacks/current/error-ledger.json"
TARGETS = ROOT / "docs/audits/LEDGER_REGRESSION_COMMAND_TARGETS_2026-10-07.json"
OUT = ROOT / "docs/audits/LEDGER_UNBOUND_TRIAGE_2026-10-07.json"
# A guard file added within this many days of the record is treated as a same-round fix, so the binding
# candidate is the commit that introduced it rather than one of the later commits that merely touched it.
CLEAR_WINDOW_DAYS = 3

ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
targets = json.loads(TARGETS.read_text(encoding="utf-8"))
state_of = {r["errorId"]: r for r in targets["rows"]}
records = {e["error_id"]: e for e in ledger["errors"]}

unbound = [eid for eid, e in records.items()
           if e.get("status_after") == "PASS"
           and not (e.get("lifecycle") or {}).get("fixedCommit")]

first_commit_cache: dict[str, tuple[str, str]] = {}


def first_commit(path: str) -> tuple[str, str]:
    if path not in first_commit_cache:
        out = subprocess.run(["git", "log", "--diff-filter=A", "--format=%h|%aI", "--", path],
                             cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                             errors="replace").stdout.strip().splitlines()
        first_commit_cache[path] = (out[-1].split("|") + [""])[:2] if out else ("", "")
    return first_commit_cache[path]


kinds: Counter[str] = Counter()
rows = []
for eid in sorted(unbound):
    record = records[eid]
    target = state_of.get(eid, {})
    state = target.get("state", "NOT_IN_TARGETS_AUDIT")
    operand = (target.get("operands") or [{}])[0].get("operand", "")
    kinds[state] += 1
    entry = {"errorId": eid, "date": record.get("date"), "state": state, "operand": operand,
             "command": (target.get("command") or "")[:120]}
    if state == "RESOLVES" and operand:
        added, when = first_commit(operand)
        entry["guardFirstCommit"] = added
        entry["guardAddedAt"] = when[:10]
        days = None
        if when and record.get("date"):
            try:
                days = (datetime.fromisoformat(when[:10]) -
                        datetime.fromisoformat(record["date"])).days
            except ValueError:
                days = None
        entry["guardVsRecordDays"] = days
    rows.append(entry)

clear = [r for r in rows if r.get("state") == "RESOLVES"
         and r.get("guardVsRecordDays") is not None
         and abs(r["guardVsRecordDays"]) <= CLEAR_WINDOW_DAYS]
undated = [r for r in rows if r.get("state") == "RESOLVES" and r.get("guardVsRecordDays") is None]
# `distant` and the held partition are settled after the birth-commit pass below: a record that no commit
# has ever carried cannot be a binding candidate however close its guard file sits to the record date, and
# calling it one would let the audit promise a SHA that does not exist. Measured 2026-10-10: the six
# in-window records included ERR-245, whose fix is in the uncommitted working set -- the typed ceiling of
# five caught it, which is the ceiling's whole purpose.
distant: list[dict] = []
# The 2026-08 batch records carry no date field at all, so the window rule cannot be applied to them;
# naming that reason keeps "ambiguous" from reading like "decided against".

# The signal that actually identifies a binding candidate: the commit that BORN the record. When that same
# commit also touches a path the record names and contains the script the record promises to run, the
# cause is pinned by the repository itself rather than inferred from file proximity. This is how ERR-123
# turned out to be bindable to 763a77f while its guard file pointed somewhere else.
for r in rows:
    eid = r["errorId"]
    birth = subprocess.run(["git", "log", "--format=%h|%s", "--reverse",
                            "-S", f'"{eid}"', "--", "taskpacks/current/error-ledger.json"],
                           cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                           errors="replace").stdout.strip().splitlines()
    if not birth:
        r["birthCommit"] = None
        continue
    sha, subject = birth[0].split("|", 1)
    r["birthCommit"] = sha
    r["birthSubject"] = subject[:90]
    # How many records did that commit bring in? Thirteen of these rows are born in the 2026-09 cutover
    # import, which added the whole 2026-08-11 batch at once. An import commit is not a fix commit, so the
    # count is published per row and a binding candidate must have added at most one record (ERR-16).
    def total(rev: str):
        text = subprocess.run(["git", "show", f"{rev}:taskpacks/current/error-ledger.json"],
                              cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", errors="replace").stdout
        try:
            return json.loads(text)["summary"]["total"]
        except (json.JSONDecodeError, KeyError):
            return -1
    r["birthAddedRecords"] = total(sha) - total(f"{sha}^")
    touched = set(subprocess.run(["git", "show", "--format=", "--name-only", sha],
                                 cwd=ROOT, capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout.split())
    named = {r.get("operand")} - {None}
    record = records[eid]
    for key in ("regression_test", "entrypoint", "command"):
        for token in str(record.get(key) or "").replace("&&", " ").split():
            if "/" in token and not token.startswith("-"):
                named.add(token.strip("`'\"(),"))
    r["birthTouchesNamedPath"] = sorted(named & touched)
    promised = (record.get("lifecycle") or {}).get("regressionCommand") or record.get("command") or ""
    script = next((t for t in str(promised).split() if t.endswith((".py", ".js", ".ts", ".tsx", ".mjs"))), "")
    if script:
        r["birthContainsPromisedScript"] = subprocess.run(
            ["git", "cat-file", "-e", f"{sha}:{script}"], cwd=ROOT,
            capture_output=True).returncode == 0
    else:
        r["birthContainsPromisedScript"] = None

bindable = [r for r in rows if r.get("birthTouchesNamedPath")
            and r.get("birthContainsPromisedScript")
            and 0 <= (r.get("birthAddedRecords") or 99) <= 1]

born_in_import = [r for r in rows if r.get("birthCommit")
                  and (r.get("birthAddedRecords") or 0) > 1]

# The window can only be settled now: a record no commit has ever carried has nothing to bind to, however
# close its guard file sits to the record date.
held = [r for r in clear if not r.get("birthCommit")]
clear = [r for r in clear if r.get("birthCommit")]
distant = [r for r in rows if r.get("state") == "RESOLVES"
           and r.get("guardVsRecordDays") is not None
           and r not in clear and r not in held]

doc = {"schemaVersion": "work-lab/ledger-unbound-triage/v1",
       "tool": "scripts/audit/triage_unbound_ledger_records.py",
       "generatedByCommand": "python scripts/audit/triage_unbound_ledger_records.py",
       "readOnly": True,
       "bindsNothing": True,
       "whyItMatters": "a PASS record without fixedCommit claims an outcome with no pinned cause; this "
                       "splits that debt into what a commit can actually answer for and what it cannot",
       "clearWindowDays": CLEAR_WINDOW_DAYS,
       "counts": {"unboundPassRecords": len(unbound), "byState": dict(kinds),
                  "clearCandidates": len(clear),
                  "resolvesGuardUndatedRecord": len(undated),
                  "resolvesGuardDistant": len(distant),
                  "noResolvableOperand": len(unbound) - sum(
                      1 for r in rows if r.get("state") == "RESOLVES"),
                  "bindableByBirthCommit": len(bindable),
                  "inWindowButUncommittedRecord": len(held),
                  "bornInAnImportCommit": len(born_in_import)},
       "clearCandidates": [r["errorId"] for r in clear],
       "heldForUncommittedRecord": [r["errorId"] for r in held],
       "bindableByBirthCommit": [r["errorId"] for r in bindable],
       "bornInAnImportCommit": [r["errorId"] for r in born_in_import],
       "resolvesGuardUndatedRecord": [r["errorId"] for r in undated],
       "resolvesGuardDistant": [r["errorId"] for r in distant],
       "rows": rows}
OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

print("unboundPass", len(unbound), "byState", dict(kinds))
print("clear", len(clear), "heldUncommitted", len(held), "undated", len(undated),
      "distant", len(distant), "bindableByBirth", len(bindable))
for r in clear[:12]:
    print(f"  {r['errorId']} record={r['date']} guard={r['guardFirstCommit']} "
          f"added={r['guardAddedAt']} delta={r['guardVsRecordDays']}d {r['operand']}")
print("triage ->", OUT)
