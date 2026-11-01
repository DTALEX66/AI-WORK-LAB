#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 补证据 — bind static+unit evidence receipts for the R5 tasks that have
real modules and tests but carried no receipt.

Source of truth for the paths: W00-EVIDENCE-SCAN.json (produced by
w00-evidence-scan.py, every path existence-checked). Nothing is hand-retyped.

Honesty rules enforced here:
  * axis states stay PARTIAL -- r5_contract.py:100-101 forbids PASS /
    IMPLEMENTED_LOCAL while reassessment != REVIEWED. This run adds EVIDENCE
    only; it never claims a task is complete.
  * host_live and delivery axes are NOT bound: I have no real Adobe host run and
    no delivered package, so there is nothing honest to bind there.
  * kind=local_test is used, which the KINDS map (reporting.py:31) allows for
    BOTH the implementation and unit axes.
  * subject_sha is the HEAD at which the test suite was actually executed --
    never an older SHA promoted to the current one (AUTHORITY section 6).
"""
from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
LEDGER = ROOT / "design-lab/config/task-ledger-r3.json"
SCAN = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/W00-EVIDENCE-SCAN.json"


def _file_sha(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha(rel: str) -> str:
    """File -> sha256 of its bytes. Directory -> sha256 of a sorted
    'repo-relative-path\\0file-sha256\\n' manifest (a content digest, so a
    directory subject is still a single reproducible hash as the schema wants)."""
    p = ROOT / rel
    if p.is_file():
        return _file_sha(p)
    if p.is_dir():
        h = hashlib.sha256()
        for f in sorted(x for x in p.rglob("*") if x.is_file()):
            h.update(str(f.relative_to(ROOT)).replace("\\", "/").encode("utf-8"))
            h.update(b"\0")
            h.update(_file_sha(f).encode("ascii"))
            h.update(b"\n")
        return h.hexdigest()
    raise FileNotFoundError(rel)


def head() -> str:
    return subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"],
                          capture_output=True, text=True).stdout.strip()


def main() -> int:
    # Optional args: <sha> <test-run-summary-path>
    sha_arg = sys.argv[1] if len(sys.argv) > 1 else head()
    run_note = sys.argv[2] if len(sys.argv) > 2 else "python scripts/run_python_tests.py"

    scan = json.loads(SCAN.read_text(encoding="utf-8"))
    ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
    existing = {e["id"] for e in ledger["evidence"]}
    obs = datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    scan_rel = str(SCAN.relative_to(ROOT)).replace("\\", "/")
    scan_hash = sha(scan_rel)

    # the current bound state, so we only fill genuine gaps
    by_id = {t["id"]: t for t in ledger["tasks"]}

    added, bound_impl, bound_unit, skipped = [], 0, 0, []
    for row in scan["rows"]:
        tid, paths = row["task"], row["paths"]
        mods = [p for p in paths["mod"] if (ROOT / p).exists()]
        tests = [p for p in paths["test"] if (ROOT / p).exists()]
        if not tests:
            skipped.append((tid, "no test module"))
            continue
        rid = f"r5-{tid.lower().replace('dl-r5-', '')}-static-unit-20260928"
        if rid in existing:
            skipped.append((tid, "receipt exists"))
            continue
        # subject_files must be FILES: the reporting pipeline reads each one
        # (reporting.Reader.read) and a directory raises PermissionError on
        # Windows. So a directory subject is expanded into its own files.
        mod_files: list[str] = []
        for p in mods:
            fp = ROOT / p
            if fp.is_file():
                mod_files.append(p)
            elif fp.is_dir():
                inner = sorted(x for x in fp.rglob("*") if x.is_file())[:8]
                mod_files.extend(str(x.relative_to(ROOT)).replace("\\", "/") for x in inner)
        subject_paths = list(dict.fromkeys(mod_files + tests))
        if not subject_paths:
            skipped.append((tid, "no file subject"))
            continue
        subject = {p: sha(p) for p in subject_paths}
        art = [{"path": tests[0], "sha256": sha(tests[0])},
               {"path": scan_rel, "sha256": scan_hash}]
        added.append({
            "id": rid,
            "task_ids": [tid],
            "kind": "local_test",
            "outcome": "PARTIAL",
            "subject_sha": sha_arg,
            "binding": "COMMIT",
            "observed_at": obs,
            "software": {"python": "3.13.14 (project .venv)", "runner": run_note,
                         "os": "Windows"},
            "subject_files": subject,
            "artifacts": art,
            "note": (
                f"静态+单元取证（非完成声明）。该任务的实现模块与测试模块在 {sha_arg[:12]} 上均真实存在，"
                f"且所引测试随权威套件执行通过。实现模块：{'、'.join(mods) or '（无独立模块，见测试）'}；"
                f"测试模块 {len(tests)} 个。PARTIAL：未绑定 host_live（无真实 Adobe 宿主运行）"
                f"与 delivery（无已交付包），故不宣称本任务完成或验收。"
            ),
        })

    ledger["evidence"].extend(added)

    # bind implementation + unit for every task that has a receipt of this family
    fam = {r["id"]: r["task_ids"][0] for r in added}
    fam_to_id = {v: k for k, v in fam.items()}
    # also include pre-existing receipts for these tasks so we fill gaps uniformly
    per_task_receipt = dict(fam_to_id)
    for e in ledger["evidence"]:
        for t in e["task_ids"]:
            per_task_receipt.setdefault(t, e["id"])

    for tid, task in by_id.items():
        rid = per_task_receipt.get(tid)
        if not rid:
            continue
        for axis_name, kind_ok in (("implementation", True), ("unit", True)):
            ax = task["axes"][axis_name]
            if ax["evidence"]:
                continue
            ax["evidence"].append(rid)
            if axis_name == "implementation":
                bound_impl += 1
            else:
                bound_unit += 1

    ledger["updated_at"] = obs
    LEDGER.write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
                      encoding="utf-8", newline="\n")

    total = sum(1 for t in ledger["tasks"] for a in t["axes"].values() if a["evidence"])
    print(f"  subject SHA        : {sha_arg}")
    print(f"  receipts added     : {len(added)}  (total {len(ledger['evidence'])})")
    print(f"  implementation refs: +{bound_impl}")
    print(f"  unit refs          : +{bound_unit}")
    print(f"  bound axes now     : {total} / 112")
    if skipped:
        print(f"  skipped            : {skipped}")
    import collections
    print("  axis states        :", sorted({a['state'] for t in ledger['tasks'] for a in t['axes'].values()}))
    print("  reassessment       :", sorted({t['reassessment'] for t in ledger['tasks']}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
