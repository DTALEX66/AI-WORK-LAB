# SPDX-License-Identifier: MIT
"""V26: the numbers in the closure table are the numbers this machine measured.

Split from `test_v25_audit_item_closure.py` on purpose. Half of that file's claims can be
checked in a fresh clone; these two cannot, because they compare tracked registers against
run artefacts that live under ``.project-local`` -- the closure receipt and the isolated
install's own ``verify-report.json`` -- and ``.gitignore`` excludes that tree.

`tests/unified/test_v23_clone_repro.py` scans each test file's own source and puts any file
naming such a prerequisite into the machine-bound set, which it must *name* rather than
ignore. That is why these assertions live here: in a clone this file is reported as
"needs the audit machine", and the register's rows answer with
``未在本机测量（…收据…不在 Git 内）`` instead of carrying a stale figure. On the machine
that ran the measurements, the figures are re-read and compared, so a register cannot keep
a number after the run moved on.
"""
from __future__ import annotations

import csv
import glob
import hashlib
import io
import json
import os
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
REGISTER = TARGET_ROOT / "migration" / "audit-item-closure.csv"
VERDICT = TARGET_ROOT / "config" / "isolated-install-verdict.json"
VERDICT_BUILDER = TARGET_ROOT / "scripts" / "build_isolated_install_verdict.py"
RECEIPT = (TARGET_ROOT / ".project-local" / "audit" / "20261031-fullclosure"
           / "CLOSURE-STATE.json")
# the install report is written under .project-local/build/, which Git does not carry
BUILD_GLOB = str(TARGET_ROOT / ".project-local" / "build" / "*" / "verify-report.json")
UNMEASURED_PREFIX = "未在本机测量"


def _rows() -> list[dict]:
    raw = REGISTER.read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw, newline="")))


def test_the_measured_figures_are_the_ones_the_named_receipt_carries():
    """The register names the receipt it was measured from, and that file is what is checked.

    ``CLOSURE-STATE.json`` is re-written in place by every measurement run, so comparing the
    published register against "whichever receipt happens to be newest" would make the two
    artifacts chase each other: refreshing the receipt invalidates a tracked file, which moves
    the candidate the next receipt describes. The register therefore cites an archived receipt
    by name (under its own candidate digest) and this test reads *that* file.
    """
    rows = _rows()
    named = {row["运行收据"] for row in rows}
    if all(value.startswith(UNMEASURED_PREFIX) for value in named):
        stale = [row["ID"] for row in rows
                 if not row["真实exit_code"].startswith(UNMEASURED_PREFIX)]
        assert stale == [], (
            "本机没有命名收据，但这些行仍带着具体数字：" + str(stale))
        return
    assert len(named) == 1, "一轮登记只能绑一份测量收据：" + str(sorted(named))
    archive = (TARGET_ROOT / ".project-local" / "audit" / "20261031-fullclosure"
               / named.pop())
    assert archive.is_file(), "登记命名的收据不在本机：" + str(archive)
    receipt = json.loads(archive.read_text(encoding="utf-8-sig"))
    stem = archive.name[len("CLOSURE-STATE-"):-len(".json")]
    assert receipt["candidate_digest"].startswith(stem), (
        "收据文件名与它自己的候选摘要不一致：" + stem)
    stamped = "\n".join(row["受测候选摘要"] for row in rows)
    assert receipt["candidate_digest"][:16] in stamped, (
        "登记的候选摘要与命名收据不一致：收据 %s…" % receipt["candidate_digest"][:16])
    assert receipt["head_commit"][:12] in stamped, (
        "登记的提交与命名收据不一致：收据 %s" % receipt["head_commit"][:12])
    proven = subprocess.run(["git", "merge-base", receipt["head_commit"], "HEAD"],
                            cwd=str(TARGET_ROOT), capture_output=True, text=True,
                            encoding="utf-8", errors="replace").stdout.strip()
    assert proven == receipt["head_commit"], (
        "收据描述的提交 %s 不是当前 HEAD 的祖先：登记表不能指向一个不在本分支上的候选"
        % receipt["head_commit"][:12])
    measured = {str(receipt["suite"]["exit_code"]), str(receipt["gate"]["exit_code"]),
                str(receipt["boot_probe"]["exit_code"]), str(receipt["migration"]["exit_code"])}
    for row in rows:
        figure = row["真实exit_code"]
        if "（全量回归）" in figure:
            assert figure.split("（")[0] == str(receipt["suite"]["exit_code"]), row["ID"]
        elif figure.isdigit():
            assert figure in measured, (
                row["ID"], figure, "登记了一个命名收据里没有的 exit code")
    # the substantive claim a reviewer will re-run: this receipt must record a green suite
    assert receipt["suite"]["failed"] == 0 and receipt["suite"]["errors"] == 0, receipt["suite"]


def test_the_isolated_install_record_matches_the_report_it_was_generated_from():
    reports = sorted(glob.glob(BUILD_GLOB), key=os.path.getmtime)
    document = json.loads(VERDICT.read_text(encoding="utf-8-sig"))
    if not reports:
        finished = subprocess.run(
            [sys.executable, "-B", "-X", "utf8", str(VERDICT_BUILDER), "--check"],
            cwd=str(TARGET_ROOT), capture_output=True, text=True, encoding="utf-8",
            errors="replace")
        assert finished.returncode == 2, (finished.returncode, finished.stdout[-400:])
        assert "NO_ISOLATED_INSTALL_REPORT" in finished.stderr, finished.stderr[-400:]
        assert document["observed_from"]["sha256"], (
            "本机没有安装报告，跟踪记录必须至少钉住它自己来自哪一份报告的字节")
        return
    report = Path(reports[-1])
    blob = report.read_bytes()
    local = json.loads(blob.decode("utf-8-sig"))
    assert hashlib.sha256(blob).hexdigest() == document["observed_from"]["sha256"], (
        "本机最新的安装报告已经变化，但跟踪记录没有重新生成：登记 %s…，现读 %s…"
        % (document["observed_from"]["sha256"][:12], hashlib.sha256(blob).hexdigest()[:12]))
    assert document["overall"] == local["overall"], (
        "跟踪记录的 overall 与报告不一致")
    assert [check["id"] for check in document["checks"]] == [
        check["id"] for check in local["checks"]], "检查项集合与报告不一致"
    for tracked, original in zip(document["checks"], local["checks"]):
        assert tracked["verdict"] == original["verdict"], (tracked["id"], original["verdict"])
    assert document["blocked"] == (local.get("blocked") or [])
    assert document["failed_required"] == (local.get("failed_required") or [])
    # and the check itself refuses a stale record: --check compares, writes nothing
    before = VERDICT.read_bytes()
    finished = subprocess.run(
        [sys.executable, "-B", "-X", "utf8", str(VERDICT_BUILDER), "--check"],
        cwd=str(TARGET_ROOT), capture_output=True, text=True, encoding="utf-8",
        errors="replace")
    assert finished.returncode == 0, (finished.stdout[-500:], finished.stderr[-500:])
    assert json.loads(finished.stdout)["drift"] is False
    assert VERDICT.read_bytes() == before, "--check 不得写跟踪记录"


def test_the_planted_stale_record_is_caught_by_this_same_comparison(tmp_path):
    """Falsification for the check above: a record whose digest no longer matches must go red.

    Without this, ``test_..._matches_the_report`` only ever passes -- it compares a record
    that was generated from the report, so nothing shows the comparison can disagree.
    """
    reports = sorted(glob.glob(BUILD_GLOB), key=os.path.getmtime)
    if not reports:
        return  # nothing to falsify without the artefact; the refusal path is covered above
    document = json.loads(VERDICT.read_text(encoding="utf-8-sig"))
    planted = dict(document, observed_from=dict(document["observed_from"],
                                               sha256="0" * 64))
    copy = tmp_path / "isolated-install-verdict.json"
    copy.write_text(json.dumps(planted, ensure_ascii=False, indent=2), encoding="utf-8",
                    newline="\n")
    blob = Path(reports[-1]).read_bytes()
    assert hashlib.sha256(blob).hexdigest() != planted["observed_from"]["sha256"], (
        "被种下的假摘要与真报告相同：这个反例什么都没测")
