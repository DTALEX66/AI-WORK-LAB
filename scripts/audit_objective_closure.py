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
# each gate is named by the artefact that owns the claim, not by this script's opinion.
# 2026-11-02: the set is the whole gate surface, aligned with the independence instrument. The
# two that were missing here (the deferral register and the isolated-install verdict) are exactly
# the two whose clone-state readings a reviewer could not otherwise see.
GATES = (
    ("顶层入口数字与引用现算相等", ("scripts/check_project_current.py", "--check")),
    ("测试文件声明节点数没有被悄悄改小", ("scripts/build_test_census.py", "--check")),
    ("来源文件去向与登记枚举差集为 0", ("scripts/build_source_coverage.py", "--check")),
    ("验收子句登记与生成一致", ("scripts/build_task_acceptance_register.py", "--check")),
    ("阻断与延期登记与生成一致", ("scripts/build_blocker_register.py", "--check")),
    ("待判定行每一格的出处锚仍能现查到唯一一行",
     ("scripts/build_unregistered_adjudications.py", "--check")),
    ("延期登记与生成一致", ("scripts/build_deferral_register.py", "--check")),
    ("审计项闭环登记表绑在那张命名收据上", ("scripts/build_audit_item_closure.py", "--check")),
    ("离线安装回执与跟踪记录一致", ("scripts/build_isolated_install_verdict.py", "--check")),
    ("审计状态记录不比当前树旧", ("scripts/build_audit_state.py", "--check")),
    # 2026-11-06: the workbench bundle is a tracked artefact whose bytes nobody outside the suite
    # compared against the commit's own blob, so "the JS gates are green" was not visible here.
    # A clone answers by name (no node_modules / no vite), which this audit records as PENDING --
    # an unmet prerequisite, never a pass.
    ("workbench 产物字节等于被审提交里的 blob",
     ("scripts/check_workbench_bundle_drift.py",)),
    ("迁移计划无未登记目标", ("scripts/migrate_sources.py", "--plan")),
)

def run(argv, cwd=None, timeout=1800):
    return subprocess.run(argv, cwd=str(cwd or ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=timeout)


def git(root, *args):
    return run(["git", *args], cwd=root, timeout=600).stdout.strip()


def probe_history_bytes_claimed(root: Path) -> dict:
    """#58: every tracked byte under the history area is named by one of the four ledgers.

    Driven as a subprocess against the tree being audited, because ``check_project_current`` pins
    its own root at import: importing it here would audit this checkout while claiming to audit
    the clone. The population comes from ``git ls-files``, never from a ledger -- starting from
    the ledger would only prove the ledger agrees with itself.
    """
    driver = ("import json,sys;sys.path.insert(0,'scripts');import check_project_current as c;"
              "tracked, errors = c.tracked_history_files();"
              "claims = {} if errors else c.history_claims();"
              "print(json.dumps({'tracked': len(tracked), 'claimed': len(claims),"
              "'findings': errors or c.unclaimed_history_findings(tracked, claims)}))")
    completed = run([PY, "-B", "-X", "utf8", "-c", driver], cwd=root, timeout=900)
    if "Traceback" in completed.stderr or completed.returncode != 0:
        return {"status": "INSTRUMENT_ERROR", "rc": completed.returncode,
                "stderr_tail": completed.stderr.strip()[-300:]}
    try:
        answer = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"status": "INSTRUMENT_ERROR", "error": "the probe printed no JSON answer",
                "stdout": completed.stdout.strip()[:200]}
    return {"status": "PASS" if not answer["findings"] else "FAIL",
            "tracked_history_files": answer["tracked"],
            "named_by_a_ledger": answer["claimed"],
            "findings": answer["findings"][:12],
            "finding_count": len(answer["findings"])}


def probe_raster_not_tracked(root: Path) -> dict:
    listed = git(root, "ls-files", "--", "docs/history", "docs/authority-202610")
    hits = [line for line in listed.splitlines() if line.lower().endswith(RASTER)]
    return {"status": "PASS" if not hits else "FAIL",
            "tracked_raster": hits[:10], "tracked_raster_count": len(hits)}


def probe_source_root_absent(root: Path) -> dict:
    """Drive the real generator through the environment switch and require a named answer.

    The first version scraped ``SOURCE_ROOT_ABSENT`` out of ``build_audit_state.py``'s text and
    hard-coded a drive letter, so it proved that one path on one machine did not raise -- and
    proved nothing about the switch that is the whole point of the cut. Now the probe sets the
    override the same way a reviewer would, asks the resolver what root it settled on, and
    fails if the answer is a different path, a traceback, or a record without the named
    absence.
    """
    driver = (
        "import json, os, sys; sys.path.insert(0, 'scripts');"
        "import source_roots as sr;"
        "missing = sr.sample_absent_root();"
        "os.environ[sr.ENVIRONMENT['work']] = str(missing);"
        "import build_audit_state as m;"
        "record = m.source_repo_record('work', sr.work_root());"
        "print(json.dumps({'asked': str(missing), 'resolved': str(sr.work_root()),"
        "'head_observed': record['head_observed'], 'sentinel': sr.SOURCE_ROOT_ABSENT,"
        "'named_absence': bool(record.get(m.SOURCE_NOT_OBSERVED_KEY))}))"
    )
    completed = run([PY, "-B", "-X", "utf8", "-c", driver], cwd=root, timeout=300)
    if "Traceback" in completed.stderr or completed.returncode != 0:
        return {"status": "FAIL", "error": "crashed instead of answering",
                "rc": completed.returncode, "stderr_tail": completed.stderr.strip()[-200:]}
    try:
        answer = json.loads(completed.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        return {"status": "INSTRUMENT_ERROR", "error": "the driver printed no JSON answer",
                "rc": completed.returncode, "stdout": completed.stdout.strip()[:200],
                "stderr_tail": completed.stderr.strip()[-200:]}
    reasons = []
    if answer["resolved"] != answer["asked"]:
        reasons.append("the environment override did not reach the resolver")
    if answer["head_observed"] != answer["sentinel"]:
        reasons.append("the generator did not answer with the named sentinel")
    if not answer["named_absence"]:
        reasons.append("the record does not say which root this machine could not observe")
    return {"status": "PASS" if not reasons else "FAIL",
            "asked_about": answer["asked"], "sentinel_declared": answer["sentinel"],
            "refusals": reasons, "rc": completed.returncode,
            "stdout": completed.stdout.strip()[:160]}


#: what may legitimately be committed after a receipt was taken: the rebind itself, the entry's
#: regenerated figures and the registers whose own builders are in this script's gate set. Never code
#: or tests -- those would need a fresh receipt. `config/` is enumerated file by file on purpose: most
#: of it is hand-edited baseline, and a blanket allow would let a registry change ride on an old run.
#: A Markdown file at the repository root is prose by shape, so the branch is a pattern, not the four
#: names it used to list: enumerating them made `INTEGRATION_POLICY.md` -- which is precisely where
#: AGENTS.md §3 requires an authorization to be recorded -- read as code, and a policy paragraph would
#: then demand a fresh 25-minute suite run to certify a sentence nobody imports.
REBIND_OK = re.compile(r"^(docs/|migration/"
                       r"|config/(blocker-register|isolated-install-verdict)\.json$"
                       r"|[^/]+\.md$)")


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
    # Uncommitted tracked edits belong to no commit, so neither this receipt nor the registers can
    # speak for them: an audit run over a dirty tree would certify bytes that were never measured.
    dirty = [name for name in git(root, "diff", "--name-only", "HEAD", "-z").split(chr(0)) if name]
    if dirty:
        return {"status": "FAIL", "reason": "本机还有未提交的跟踪改动，这张收据替不了它们",
                "uncommitted_tracked_files": sorted(dirty)[:12]}
    # The receipt is not required to name HEAD exactly, and requiring it was the defect: rebinding
    # the registers and rendering the measured section necessarily produce commits *after* the one
    # that was run, so strict equality left this clause at PENDING forever. What has to hold is that
    # HEAD descends from it and that every tracked file in between is a document or a generated
    # register -- a code or test file inside that range was never in the suite that went green.
    allowed, unexpected = [], []
    if receipt["head_commit"] != head:
        listing = subprocess.run(["git", "diff", "--name-only",
                                  "%s..HEAD" % receipt["head_commit"], "-z"],
                                 cwd=str(root), capture_output=True, text=True,
                                 encoding="utf-8", errors="replace").stdout
        for rel in [x for x in listing.split(chr(0)) if x]:
            bucket = allowed if REBIND_OK.match(rel) else unexpected
            bucket.append(rel)
        if unexpected:
            return {"status": "FAIL", "reason": "收据之后动了代码或测试，那张收据不能替它们作证",
                    "unexpected": unexpected[:12]}
        ancestor = subprocess.run(["git", "merge-base", "--is-ancestor",
                                   receipt["head_commit"], "HEAD"],
                                  cwd=str(root), capture_output=True, text=True)
        if ancestor.returncode != 0:
            return {"status": "FAIL", "reason": "收据的提交不是 HEAD 的祖先"}
    return {"status": "PASS", "suite_line": suite["line"],
            "failed_nodes_field": suite.get("failed_nodes"),
            "tracked_bytes_moved_during_run": moved,
            "receipt_commit": receipt["head_commit"][:12], "head": head[:12],
            "commited_after_receipt_documents_and_registers_only": allowed,
            "candidate_files": receipt["candidate_files"],
            "digest": receipt["candidate_digest"][:16]}


def refusal_name(completed) -> str | None:
    """The word a gate itself uses for its refusal, read out of its own report.

    A designed absence and a defect must not be told apart by this script's opinion, and a gate
    that refuses without naming why is not a designed absence. Some gates print one JSON line and
    some print an indented document, so both shapes are read; the name comes from the gate's own
    ``error``/``verdict`` field, never from a table kept here.
    """
    for stream in (completed.stdout, completed.stderr):
        text = (stream or "").strip()
        if not text:
            continue
        for candidate in (text, text.splitlines()[-1]):
            try:
                payload = json.loads(candidate)
            except ValueError:
                continue
            if isinstance(payload, dict):
                for key in ("error", "verdict"):
                    value = payload.get(key)
                    if isinstance(value, str) and value.isupper():
                        return value
            break
    return None


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=None,
                       help="run the gates and the named probes against another checkout "
                            "(this is how a clone is measured)")
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args(argv)
    root = args.root or ROOT

    def gate(name, argv):
        """Run a gate that already owns its claim, and never call a broken caller a repo FAIL.

        rc semantics, published once here because every gate must land in one of the four:
        0 = it observed what it claims and agrees; 1 = it disagrees (a defect, never excused by
        an absent root); 2 or 3 with a name = this machine could not run the observation at all,
        recorded as PENDING so the verdict cannot silently become CLOSED; 2 with no name =
        INSTRUMENT_ERROR, i.e. this caller invoked the gate wrongly. The first version of this
        file did exactly that by accident -- it splatted the flag string into characters and
        reported all gates as failing, which was a bug in the caller, not a regression here.
        """
        completed = run([PY, "-B", "-X", "utf8", str(root / argv[0]), *argv[1:]], cwd=root,
                        timeout=3600)
        rc = completed.returncode
        if rc == 0:
            return {"clause": name, "status": "PASS", "rc": 0, "evidence": " ".join(argv)}
        if rc == 1:
            return {"clause": name, "status": "FAIL", "rc": rc,
                    "note": "the gate disagrees; a missing prerequisite never lands here",
                    "evidence": " ".join(argv),
                    "stdout_tail": completed.stdout.strip()[-300:]}
        named = refusal_name(completed)
        if named:
            return {"clause": name, "status": "PENDING", "rc": rc, "refusal": named,
                    "reason": "this machine cannot observe what the gate measures",
                    "evidence": " ".join(argv)}
        if rc == 2:
            return {"clause": name, "status": "INSTRUMENT_ERROR", "rc": 2,
                    "stderr_tail": completed.stderr.strip()[-200:]}
        return {"clause": name, "status": "FAIL", "rc": rc, "evidence": " ".join(argv),
                "stderr_tail": completed.stderr.strip()[-300:],
                "note": "a non-zero rc that names nothing is not a designed absence"}

    clauses = [gate(name, list(argv)) for name, argv in GATES]
    clauses.append({"clause": "截图照片不在仓库里（owner 2026-11-01）",
                    **probe_raster_not_tracked(root)})
    clauses.append({"clause": "历史区每个字节都被某本台账点名（#58）",
                    **probe_history_bytes_claimed(root)})
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
