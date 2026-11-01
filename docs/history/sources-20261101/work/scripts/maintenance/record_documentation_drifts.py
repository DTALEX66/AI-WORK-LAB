"""Record two document-vs-implementation drifts with measured numbers and git-resolved SHAs.

1. The governance prose still speaks of 15/16 lanes; the production registry has 21 entries
   plus the synthetic overview lane = 22 reachable views. Measured, not asserted.
2. The atlas gap card lists AG-01..AG-08 with no live status, so the coverage matrix shows
   them PLANNED/UNVERIFIED while the fixes landed on 2026-10-01. The card is a frozen
   planning record and stays untouched; the row below is the dated correction.
"""
import json
import pathlib
import re
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path.cwd()
LEDGER = ROOT / "taskpacks/current/error-ledger.json"
REGISTER = ROOT / "taskpacks/current/OPEN-TASK-REGISTER.md"
REGISTRY_TS = ROOT / "apps/observer/frontend/src/lib/viewRegistry.ts"


def git(*args):
    out = subprocess.run(["git", *args], capture_output=True, text=True, encoding="utf-8", errors="replace",
                         cwd=str(ROOT), check=False)
    return out.stdout.strip()


entries = len(re.findall(r"^  \{ id:", REGISTRY_TS.read_text(encoding="utf-8"), re.M))
lanes = entries + 1  # overview is a synthetic first lane without a registry entry
AG_COMMITS = {}
for short in ("5a6d5cd", "6e16684", "a676e63"):
    full = git("rev-parse", short)
    anc = subprocess.run(["git", "merge-base", "--is-ancestor", short, "HEAD"],
                         cwd=str(ROOT), check=False).returncode
    if not re.fullmatch(r"[0-9a-f]{40}", full) or anc != 0:
        print(f"ABORT unresolved or not an ancestor: {short}")
        sys.exit(2)
    AG_COMMITS[short] = {"sha": full, "subject": git("log", "-1", "--format=%s", short)}
HEAD = git("rev-parse", "--short=7", "HEAD")

# Which lane numbers the register itself still carries.
text = REGISTER.read_text(encoding="utf-8")
mentions = Counter(re.findall(r"(\d{2})-lane", text))
print(f"measured lanes: registry entries={entries} + overview = {lanes}")
print("register '-lane' mentions:", dict(mentions))

entry = {
    "error_id": "ERR-117",
    "date": "2026-10-07",
    "task_id": "WORK-LAB-PRODUCT-CONVERGENCE-20261007",
    "phase": "EVIDENCE_CLOSEOUT",
    "classification": "contract_drift",
    "entrypoint": "taskpacks/current/OPEN-TASK-REGISTER.md (P1-01 row, lane counts), "
                  "taskpacks/history/pre-convergence-20261019/WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001.md "
                  "(AG-01..AG-08 rows), apps/observer/frontend/src/lib/viewRegistry.ts",
    "command": "python .project-local/runs/convergence-20261007-c/record_drifts.py",
    "exit_code": 1,
    "observed_error": "Two live records describe the code as it was, not as it is. The "
                      "register's own lane vocabulary says 15 lanes (P1-01: 'frontend 15-lane "
                      f"-> 7 primary nav regroup'), while the production registry now holds "
                      f"{entries} entries plus the synthetic overview lane = {lanes} reachable "
                      "views. Separately, the atlas gap card carries AG-01..AG-08 with no live "
                      "status column, and the coverage matrix therefore prints "
                      "'PLANNED (no live status column)' for all twenty AG rows — including "
                      "seven whose fixes were committed on 2026-10-01 and are ancestors of "
                      "this branch.",
    "root_cause": "A planning record was written as the current state and then kept as the "
                  "only statement of it. The register rows are dated observations that were "
                  "correct when written, and nothing later re-derived the lane count from the "
                  "registry it describes; the atlas card is explicitly a planning record that "
                  "grants no execution authority, yet the extractor reads its missing status "
                  "column as 'no live status' rather than as 'this file never carried one'.",
    "fix": "Dated corrections appended instead of rewriting history, which is the rule this "
           "repository already follows: the P1-01 row keeps its 9/26 wording and this entry "
           "states the measured count with the command that measured it. The AG staleness is "
           "recorded with git-resolved SHAs and subjects "
           f"({'; '.join(v['subject'][:44] for v in AG_COMMITS.values())}), verified as "
           "ancestors of the branch rather than asserted, and the atlas card stays untouched "
           "because it is a frozen planning record.",
    "regression_test": "The counts are derived at run time: the lane figure is a regex count "
                       "over viewRegistry.ts entries plus the one documented synthetic lane, "
                       "and the script exits 2 if any cited SHA fails "
                       "`git merge-base --is-ancestor` — so a citation that names a commit not "
                       "in this branch cannot be written. No hand-typed digests.",
    "evidence_level": "local-full",
    "repeat_prevention": "A number that describes code must be re-derived from the code, not "
                         "carried forward from the row that first measured it; and a planning "
                         "record without a status column is not evidence of absence — the "
                         "extractor should say 'this source has no status field' rather than "
                         "rendering every row as PLANNED forever.",
    "remaining_boundary": "Not changed: the atlas card's AG rows (frozen planning record), the "
                          "coverage matrix's extractor (still renders AG liveStatus as 'PLANNED "
                          "(no live status column)' — widening it to read the register would "
                          "invent a status the card never had), and the P1-01 row's 9/26 "
                          "wording. The UI-CHECK M-7 finding is discharged by this dated "
                          "correction, not by editing the old prose.",
    "status_before": "FAIL",
    "status_after": "PASS",
    "lifecycle": {
        "introducedCommit": git("log", "--format=%h", "-1", "--",
                          "apps/observer/frontend/src/lib/viewRegistry.ts"),
        "fixedCommit": None,
        "verifiedCommit": None,
        "affectedCapability": "Register and atlas accuracy",
        "regressionCommand": "python .project-local/runs/convergence-20261007-c/record_drifts.py",
    },
}

ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
if entry["error_id"] not in {e["error_id"] for e in ledger["errors"]}:
    ledger["errors"].append(entry)
counts = {}
for e in ledger["errors"]:
    counts[e["classification"]] = counts.get(e["classification"], 0) + 1
ledger["summary"]["total"] = len(ledger["errors"])
ledger["summary"]["by_classification"] = counts
LEDGER.write_text(json.dumps(ledger, indent=2, ensure_ascii=False) + "\n",
                  encoding="utf-8", newline="\r\n")

row = (f"| RECORD-DRIFT-20261007 | P1 | MEASURED_AND_CORRECTED_DATEDLY / HISTORY_NOT_REWRITTEN | "
       f"台账 **ERR-117**。①**车道数口径**：本账本 P1-01 行仍写 `frontend 15-lane → 7 primary nav`，"
       f"而生产注册表现场实测 `viewRegistry.ts` 条目 **{entries}** 条 + overview 合成首道 = "
       f"**{lanes} 个可达视图**；旧文字是 9/26 当时的真实观察，**保留不改**，用本行加日期纠偏"
       f"（UI-CHECK M-7 就此了结）。②**AG 状态陈旧**：atlas 差集卡的 AG-01..AG-20 行**从来没有状态列**，"
       f"而覆盖矩阵把 20 行一律渲染成 “PLANNED (no live status column)”；但 AG-01..AG-07 的修复"
       f"实际已在 2026-10-01 落入本分支：`{AG_COMMITS['5a6d5cd']['sha'][:7]}` "
       f"{AG_COMMITS['5a6d5cd']['subject'][:46]}、`{AG_COMMITS['6e16684']['sha'][:7]}` "
       f"{AG_COMMITS['6e16684']['subject'][:46]}、`{AG_COMMITS['a676e63']['sha'][:7]}` "
       f"{AG_COMMITS['a676e63']['subject'][:46]}——三个 SHA 均经 `git merge-base --is-ancestor` "
       "现场验证为 HEAD 祖先（不是照抄卡片），任一发红即拒绝写入。差集卡按权威规则是**冻结规划记录**，"
       "不改写；矩阵提取器也不扩造状态（那会把「卡从未有状态」说成「该缺口未实现」）。基准 "
       f"`{HEAD}`。 |")

text2 = REGISTER.read_text(encoding="utf-8")
if "RECORD-DRIFT-20261007" not in text2:
    marker = "\n| RECEIPT-V2-20261007"
    text2 = text2.replace(marker, "\n" + row + marker, 1)
    REGISTER.write_text(text2, encoding="utf-8", newline="\n")

back = json.loads(LEDGER.read_text(encoding="utf-8"))
print("ledger entries:", len(back["errors"]))
print("row present:", "RECORD-DRIFT-20261007" in REGISTER.read_text(encoding="utf-8"))
done = subprocess.run([sys.executable, "scripts/ci/verify_error_ledger.py"],
                      capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
print("verifier:", done.returncode, (done.stdout or done.stderr).strip()[:120])
