"""Closure audit for the owner's 2026-11-01 rules: orchestrate the real gates, and add only what none of them checks.

Why this file is allowed to exist: it was first written as eleven self-contained checks, and that was
wrong -- seven of them reimplemented guards that already own those bytes (`check_project_current.py`
verifies every promoted and imported digest, `build_test_census.py` pins declared test counts,
`test_v14` holds the disposition-enumeration差集, `test_v26` binds the register to its named receipt).
A second implementation of a check is a second place to be wrong, and two of my own seven were:
the index's separator row was counted as a promoted file, and the blocker register's `blocking` field
does not exist (the counts live in `counts`). Both produced FAILs against a repository that was fine.

What remains is deliberately small: it runs each existing gate and records its real exit code, and it
owns three probes that nothing else covers --

* no raster material is tracked under the history areas (owner: 「截图照片去掉」);
* the source-repo probe answers with a named absence instead of crashing when the root is gone,
  which is the whole "can this repo stand after the sources are deleted" question;
* the full-suite receipt actually describes the commit it is being read at, with zero failures.

`--root` points the three probes at a fixture tree, so they can be shown failing; a check that cannot
fail does not earn a place in the repository either.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PY = sys.executable
RASTER = (".png", ".jpg", ".jpeg", ".gif", ".bmp", ".webp", ".tiff", ".ico")
# each gate is named by the artefact that owns the claim, not by this script's opinion
GATES = (
    ("顶层入口数字与引用现算相等", ("scripts/check_project_current.py", "--check")),
    ("测试文件声明节点数没有被悄悄改小", ("scripts/build_test_census.py", "--check")),
    ("来源文件去向与登记枚举差集为 0", ("scripts/build_source_coverage.py", "--check")),
    ("验收子句登记与生成一致", ("scripts/build_task_acceptance_register.py", "--check")),
    ("阻断与延期登记与生成一致", ("scripts/build_blocker_register.py", "--check")),
    ("审计项闭环登记表绑在那张命名收据上", ("scripts/build_audit_item_closure.py", "--check")),
    ("审计状态记录不比当前树旧", ("scripts/build_audit_state.py", "--check")),
    ("迁移计划无未登记目标", ("scripts/migrate_sources.py", "--plan")),
)

def run(argv, cwd=None, timeout=1800):
    return subprocess.run(argv, cwd=str(cwd or ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def git(root, *args):
    return run(["git", *args], cwd=root, timeout=600).stdout.strip()


def probe_raster_not_tracked(root: Path) -> dict:
    listed = git(root, "ls-files", "--", "docs/history", "docs/authority-202610")
    hits = [line for line in listed.splitlines() if line.lower().endswith(RASTER)]
    return {"status": "PASS" if not hits else "FAIL",
            "tracked_raster": hits[:10], "tracked_raster_count": len(hits)}


def probe_source_root_absent(root: Path) -> dict:
    """Ask the real probe against a root that does not exist: it must answer, not raise."""
    script = (Path(root) / "scripts" / "build_audit_state.py").read_text(encoding="utf-8")
    match = re.search(r"^SOURCE_ROOT_ABSENT\s*=\s*(.+)$", script, re.MULTILINE)
    missing = (root.drive or "D:") + "\\awl-gone-WORK-LAB"
    driver = ("import pathlib,sys;sys.path.insert(0,r'scripts');import build_audit_state as m;"
              "print(m.git(['rev-parse','HEAD'],cwd=pathlib.Path(r'" + missing + "')))")
    completed = run([PY, "-B", "-X", "utf8", "-c", driver], cwd=root, timeout=300)
    crashed = "NotADirectoryError" in completed.stderr or completed.returncode != 0
    sentinel = match.group(1).strip().strip('"') if match else None
    if crashed:
        status = "FAIL"
    elif not sentinel:
        status = "FAIL"
    elif sentinel not in completed.stdout:
        status = "FAIL"
    else:
        status = "PASS"
    return {"status": status, "asked_about": missing, "sentinel_declared": sentinel,
            "rc": completed.returncode, "stdout": completed.stdout.strip()[:160],
            "stderr_tail": completed.stderr.strip()[-200:]}


def probe_receipt_describes_this_commit(root: Path) -> dict:
    path = root / ".project-local" / "audit" / "20261031-fullclosure" / "CLOSURE-STATE.json"
    if not path.is_file():
        return {"status": "PENDING", "error": "本机没有这张收据"}
    receipt = json.loads(path.read_text(encoding="utf-8-sig"))
    suite, head = receipt["suite"], git(root, "rev-parse", "HEAD")
    moved = receipt.get("measurement_integrity", {}).get("tracked_bytes_moved_during_run")
    if suite.get("failed") or suite.get("errors"):
        return {"status": "FAIL", "suite_line": suite["line"],
                "failed_nodes": suite.get("failed_nodes", "字段不存在（旧收据）"),
                "head_of_receipt": receipt["head_commit"][:12], "head_now": head[:12]}
    if receipt["head_commit"] != head:
        return {"status": "PENDING", "reason": "收据描述的不是当前提交，重取后才算绑上",
                "head_of_receipt": receipt["head_commit"][:12], "head_now": head[:12],
                "suite_line": suite["line"]}
    return {"status": "PASS", "suite_line": suite["line"],
            "failed_nodes_field": suite.get("failed_nodes"),
            "tracked_bytes_moved_during_run": moved,
            "candidate_files": receipt["candidate_files"],
            "digest": receipt["candidate_digest"][:16]}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None,
                       help="run the three unique probes against another checkout (for tests)")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    root = args.root or ROOT

    def gate(name, argv):
        """Run a gate that already owns its claim, and never call a broken caller a repo FAIL.

        Exit 2 is argparse's usage error: if this script ever invokes a gate wrongly, the report has
        to say INSTRUMENT_ERROR. The first version of this file did exactly that by accident -- it
        splatted the flag string into characters and reported all eight gates as failing, which was
        a bug in the caller, not eight regressions in the repository.
        """
        completed = run([PY, "-B", "-X", "utf8", str(root / argv[0]), *argv[1:]], cwd=root,
                        timeout=3600)
        if completed.returncode == 2:
            return {"clause": name, "status": "INSTRUMENT_ERROR", "rc": 2,
                    "stderr_tail": completed.stderr.strip()[-200:]}
        return {"clause": name, "status": "PASS" if completed.returncode == 0 else "FAIL",
                "rc": completed.returncode, "evidence": " ".join(argv)}

    clauses = [gate(name, (script, flag)) for name, (script, flag) in GATES]
    clauses.append({"clause": "截图照片不在仓库里（owner 2026-11-01）",
                    **probe_raster_not_tracked(root)})
    clauses.append({"clause": "来源根缺失时给具名结论而不是崩溃",
                    **probe_source_root_absent(root)})
    clauses.append({"clause": "全量收据描述当前提交且没有失败", **probe_receipt_describes_this_commit(root)})

    counts = {key: sum(1 for c in clauses if c["status"] == key)
              for key in ("PASS", "FAIL", "PENDING", "INSTRUMENT_ERROR")}
    verdict = ("CLOSED" if not counts["FAIL"] and not counts["PENDING"]
               and not counts["INSTRUMENT_ERROR"] else "NOT CLOSED")
    report = {"verdict": verdict, "head": git(root, "rev-parse", "--short", "HEAD"),
              "clauses": len(clauses), "counts": counts, "items": clauses}
    if args.list:
        for clause in clauses:
            print("%-8s %s" % (clause["status"], clause["clause"]))
        print("%s  %s" % (verdict, counts))
    else:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if verdict == "CLOSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
