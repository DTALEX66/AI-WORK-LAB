# SPDX-License-Identifier: MIT
"""V25: the F01–F10 / A01–A10 closure table is tracked, and its claims resolve.

The 2026-10-30 handoff (§七) asks for a per-item tracking table carrying ID、适用要求、根因、
实际修改文件与调用入口、当前结果、独立命令、真实 exit code、日志/产物路径、受测候选摘要、
限制与下一步, using only PASS/FAIL/BLOCKED/NOT_RUN/DEFERRED, with the evidence kind kept in
its own column so 测试/合成/真实来源 cannot be blended into one completion rate. Until this
round that table lived only under the Git-excluded ``.project-local/`` -- so a clone could
not read it, and could not even answer "what is F04?". ``scripts/build_audit_item_closure.py``
moved it into ``migration/audit-item-closure.csv``, parsing the requirement text out of the
definition files instead of retyping it.

This file is the clone-runnable half: population, vocabulary, the definition each row
quotes, and whether the evidence target still resolves. The half that compares numbers
against a *local run receipt* is in ``test_v26_local_run_receipts.py`` and is named as
machine-bound rather than quietly skipped.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
REGISTER = TARGET_ROOT / "migration" / "audit-item-closure.csv"
VERDICT = TARGET_ROOT / "config" / "isolated-install-verdict.json"
BUILDER = TARGET_ROOT / "scripts" / "build_audit_item_closure.py"
VOCABULARY = ("PASS", "FAIL", "BLOCKED", "NOT_RUN", "DEFERRED")
UNMEASURED_PREFIX = "未在本机测量"
EXPECTED_IDS = ["F%02d" % index for index in range(1, 11)] + \
               ["A%02d" % index for index in range(1, 11)]


def _module():
    import importlib.util
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    spec = importlib.util.spec_from_file_location("closure_under_test", BUILDER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows() -> list[dict]:
    raw = REGISTER.read_bytes().decode("utf-8-sig")
    return list(csv.DictReader(io.StringIO(raw, newline="")))


def test_register_holds_exactly_the_ten_rework_items_and_the_ten_audit_items():
    assert REGISTER.is_file(), "闭环表必须进仓，而不是只留在被忽略的 .project-local"
    rows = _rows()
    ids = sorted(row["ID"] for row in rows)
    assert ids == sorted(EXPECTED_IDS), (
        "交接文档点名的集合是 F01–F10 与 A01–A10，实读 %d 行：%s" % (len(ids), ids))
    # one row per id: two rows for the same item would let one item carry two verdicts
    assert len(rows) == len(ids) == 20


def test_result_and_evidence_kind_stay_in_separate_columns():
    for row in _rows():
        assert row["当前结果"] in VOCABULARY, (row["ID"], row["当前结果"])
        assert row["证据种类"] and row["证据种类"] not in VOCABULARY, (
            row["ID"], "证据种类必须说明是什么种类的证据，不能重述结论——交接文档禁止把"
                       "测试/合成/真实来源混成一个完成率")


def test_the_independent_review_cell_is_derived_and_traceable():
    """NOT_RUN is the default, and the only way out is a record that can be gone and read.

    The column used to be a constant, so the register could never say anything else -- which made
    「不继承上一轮结论」 uncheckable by construction: there was no cell that could hold a review,
    and no rule about what a filled cell would have to prove. Now a row leaves NOT_RUN only when
    `config/independent-reviews.json` names it, and the cell repeats that record's SHA, which must
    be an ancestor of this checkout with the reviewer's artifact present at the recorded path.
    """
    path = TARGET_ROOT / "config" / "independent-reviews.json"
    records = json.loads(path.read_text(encoding="utf-8-sig"))["records"] if path.is_file() else []
    verified: dict[str, dict] = {}
    for record in records:
        assert re.fullmatch(r"[0-9a-f]{40}", record["reviewed_sha"]), record
        assert record["reviewer"] and record["verdict"] in ("PASS", "PASS_WITH_FINDINGS", "FAIL"), \
            record
        assert (TARGET_ROOT / record["artifact"]).is_file(), record
        for item in record["verified_items"]:
            verified[item] = record

    rows = _rows()
    for row in rows:
        cell = row["独立复审"]
        if row["ID"] not in verified:
            assert cell == "NOT_RUN", (row["ID"], "没有复审记录却填了别的东西", cell)
            continue
        record = verified[row["ID"]]
        assert record["reviewed_sha"][:12] in cell, (row["ID"], cell)
        assert record["verdict"] in cell, (row["ID"], cell)
        ancestor = subprocess.run(
            ["git", "merge-base", "--is-ancestor", record["reviewed_sha"], "HEAD"],
            cwd=str(TARGET_ROOT), capture_output=True)
        assert ancestor.returncode == 0, (row["ID"], "复审的提交不在当前检出的历史里",
                                          record["reviewed_sha"])


def test_a_recorded_review_reaches_the_cell_and_an_absent_one_does_not(tmp_path, monkeypatch):
    """The filled branch must be exercised today, not on the day a reviewer first runs.

    A code path that only executes once a human supplies input is a path that can be broken
    unnoticed until the moment it is needed -- this repo has measured that more than once. So the
    record is planted here in a temporary file, and the cell must carry the verdict, the reviewed
    SHA and the artifact pointer, while everything the record did not name has to stay NOT_RUN.
    """
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    import build_audit_item_closure as closure

    artifact = tmp_path / "REVIEW.md"
    artifact.write_text("# planted review\n", encoding="utf-8")
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(TARGET_ROOT),
                         capture_output=True, text=True).stdout.strip()
    record = dict(verdict="PASS_WITH_FINDINGS", reviewed_sha=sha, reviewer="planted-cli 1.0",
                  reviewed_at="2026-11-06T00:00:00+00:00", artifact=str(artifact),
                  verified_items=["F01"])
    path = tmp_path / "independent-reviews.json"
    path.write_text(json.dumps({"records": [record]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(closure, "REVIEWS_JSON", path)
    monkeypatch.setattr(closure, "_REVIEWS", None)

    cell = closure.independent_review_for("F01")
    assert cell.startswith("PASS_WITH_FINDINGS @ " + sha[:12]), cell
    assert "planted-cli 1.0" in cell and "REVIEW.md" in cell, cell
    assert closure.independent_review_for("A01") == "NOT_RUN", "记录没点名的项也被判成已复审"


def test_an_untraceable_review_record_certifies_nothing(tmp_path, monkeypatch):
    """A record is somebody else's claim about a commit; the register must not take it on faith.

    Independent review round 3 planted this and watched it work: a record whose ``reviewed_sha`` was
    forty ``f`` characters produced the cell ``PASS @ ffffffffffff`` for F01. The recorder validates
    the SHA when it writes, and nothing validated it when the value was *read* -- which is the side
    that becomes a project-level statement, and the side a hand-edited or copied-in JSON reaches.

    Three faces, because a guard that only ever refuses is worth the same as one that never does:
    a SHA that is not a commit id at all, a well-formed SHA that is not in this checkout's history,
    and a real commit, which must still inherit its verdict.
    """
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    import build_audit_item_closure as closure

    def cell_for(record):
        path = tmp_path / ("reviews-%s.json" % abs(hash(str(record))))
        path.write_text(json.dumps({"records": [record]}, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(closure, "REVIEWS_JSON", path)
        monkeypatch.setattr(closure, "_REVIEWS", None)
        monkeypatch.setattr(closure, "_ANCESTRY", {})
        return closure.independent_review_for("F01")

    base = dict(reviewer="planted-cli 1.0", reviewed_at="2026-11-06T00:00:00+00:00",
                artifact="REVIEW.md", verified_items=["F01"])

    forged = cell_for(dict(base, verdict="PASS", reviewed_sha="f" * 40))
    assert forged.startswith("RECORD_UNTRACEABLE"), forged
    assert "不在本检出历史里" in forged, forged

    short = cell_for(dict(base, verdict="PASS", reviewed_sha="abc123"))
    assert short.startswith("RECORD_UNTRACEABLE") and "40 位提交号" in short, short

    invented_verdict = cell_for(dict(base, verdict="LOOKS_FINE", reviewed_sha="a" * 40))
    assert invented_verdict.startswith("RECORD_UNTRACEABLE"), invented_verdict

    live = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(TARGET_ROOT),
                          capture_output=True, text=True).stdout.strip()
    real = cell_for(dict(base, verdict="PASS_WITH_FINDINGS", reviewed_sha=live))
    assert real.startswith("PASS_WITH_FINDINGS @ " + live[:12]), real


def test_the_requirement_text_belongs_to_the_file_and_digest_it_cites():
    problems = []
    for row in _rows():
        where, _, line = row["定义出处"].rpartition(":")
        path = TARGET_ROOT / where
        if not path.is_file():
            problems.append((row["ID"], "定义出处指向不存在的文件 " + where))
            continue
        blob = path.read_bytes()
        digest = hashlib.sha256(blob).hexdigest()[:16]
        if digest != row["定义文件摘要"]:
            problems.append((row["ID"], "定义文件已改动：登记 %s，现读 %s"
                             % (row["定义文件摘要"], digest)))
            continue
        text = blob.decode("utf-8")
        anchor = row["适用要求"].splitlines()[0].strip()
        if anchor not in text:
            problems.append((row["ID"], "适用要求不逐字出现在其定义出处中"))
            continue
        if not 1 <= int(line) <= len(text.splitlines()):
            problems.append((row["ID"], "定义出处行号 %s 越界" % line))
    assert problems == [], "定义与登记不一致：\n" + "\n".join(str(item) for item in problems)


def test_every_evidence_target_resolves_on_this_tree_right_now():
    module = _module()
    problems = []
    for row in _rows():
        target = row["机验证据目标"]
        if not target:
            if row["当前结果"] == "PASS":
                problems.append((row["ID"], "PASS 但没有证据目标"))
            continue
        resolved, detail = module._resolve_target(target)
        if not resolved:
            problems.append((row["ID"], detail))
        elif row["机验结果"] != "已解析：" + detail:
            problems.append((row["ID"], "登记「%s」，现读「%s」" % (row["机验结果"],
                                                                  "已解析：" + detail)))
    assert problems == [], "证据目标回读失败：\n" + "\n".join(
        str(item) for item in problems[:8])


def test_a_pass_row_must_name_the_part_that_is_still_unverified():
    naked = [row["ID"] for row in _rows()
             if row["当前结果"] == "PASS" and not row["未验证子项"].strip()]
    assert naked == [], (
        "这些行宣称 PASS 却没有写明边界内仍未验证的部分：" + str(naked)
        + "。真实宿主写入、模型推理、真实用户数据迁移与真人专业签字在本轮始终是 "
          "NOT_RUN/BLOCKED/NOT_PROBED，必须在行内可见，不能只写在文档散文里")


def test_the_builder_refuses_to_publish_a_pass_that_names_nothing_unverified(monkeypatch, capsys):
    """The same rule as the node above, one level earlier: at the builder, breaking it costs an rc.

    Reading the published file catches a naked PASS, but the entry's readiness sentences are quoted
    from that file, so "this register cannot even be produced with a naked PASS" is the stronger
    statement. The plant is the real shape: `PASS` plus a blank boundary is what "the whole item is
    done" looks like when nobody wrote it out loud.
    """
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    import build_audit_item_closure as closure

    planted = {key: dict(value) for key, value in closure.ROWS.items()}
    victim = next(key for key, value in planted.items() if value["result"] == "PASS")
    planted[victim]["unverified"] = "   "
    monkeypatch.setattr(closure, "ROWS", planted)
    rc = closure.main(["build_audit_item_closure.py", "--check"])
    assert rc == 2, ("一行 PASS 没写任何未验证项，生成器还是把表出了", rc)
    report = json.loads(capsys.readouterr().err)
    assert report["error"] == "PASS_WITHOUT_A_NAMED_UNVERIFIED_SUBITEM", report
    assert report["ids"] == [victim], report
    # the refusal must be about that row, not about every row: the authored set still gets past it
    monkeypatch.undo()
    capsys.readouterr()
    assert closure.main(["build_audit_item_closure.py", "--check"]) != 2, \
        "现值这一趟也被同一条拒绝拦了：那条判断没有只看被种坏的那一行"


def test_the_isolated_install_record_is_tracked_and_self_describing():
    assert VERDICT.is_file(), "F06/A08 的安装判定必须进仓"
    document = json.loads(VERDICT.read_text(encoding="utf-8-sig"))
    assert document["schema"] == "ai-work-lab/isolated-install-verdict/v1"
    assert document["overall"] in ("PASS", "PASS_WITH_RECORDED_GAPS", "BLOCKED", "FAIL"), \
        document["overall"]
    assert document["producer_commands"], "记录必须说出重建它的命令"
    assert document["observed_from"]["sha256"], "记录必须钉住它来自的那份报告的字节"
    assert document["observed_from"]["report"].startswith(".project-local/"), (
        "原始报告留在 Git 之外，这一点必须写在记录里，而不是假装记录就是原始证据")
    blob = json.dumps(document, ensure_ascii=False)
    home = str(Path.home())
    for spelling in (home, home.replace("\\", "/")):
        assert spelling not in blob, (
            "用户主目录不得进入跟踪文件（发现 %s）——安装报告里的 argv 是整条命令行，"
            "折叠必须按子串替换，只折叠前缀会漏掉命令串中间的路径" % spelling)
    assert home.split("\\")[-1].split("/")[-1] not in blob.replace("<HOME>", ""), (
        "用户名以任何形式留在记录里")
    assert "<HOME>" in blob or home not in blob, (
        "折叠后的记号应出现（说明命令串里本来就有临时目录）")
    for check in document["checks"]:
        assert check["verdict"] in VOCABULARY + ("NOT_PROBED",), check


def test_the_builder_check_mode_reproduces_the_register_without_writing_it(tmp_path):
    """`--check` must be a reader, and its verdict must be honest about its own reach.

    On the audit machine the comparison is whole-table: the receipt is present, so the exit codes
    and the candidate digest are checked like any other column, and rc=0 is the only acceptable
    answer. In a clone there is no receipt, so those four columns cannot be reproduced by
    construction -- the check compares every other column, *names* the four it exempted, and
    returns 3 instead of 0. A clone that quietly "passed" a comparison of numbers it never had
    would be the pseudo-PASS this round exists to remove, so both directions are asserted:
    drift-free content, and an rc that says which part was not observable here.
    """
    before = REGISTER.read_bytes()
    finished = subprocess.run([sys.executable, "-B", "-X", "utf8", str(BUILDER), "--check"],
                              cwd=str(TARGET_ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    summary = json.loads(finished.stdout)
    expected_rc = 0 if summary["receipt_present"] else 3
    assert finished.returncode == expected_rc, (
        "rc=%d where receipt_present=%s asked for %d: %s"
        % (finished.returncode, summary["receipt_present"], expected_rc,
           (finished.stdout or "")[-500:]))
    assert summary["register_drift"] is False
    assert REGISTER.read_bytes() == before, "--check 不得写跟踪登记"
    if summary["receipt_present"]:
        assert summary["verdict"] == "MATCHES", summary
        assert summary["receipt_columns_exempted"] == [], (
            "本机有收据却免检了列，数字就没人对了")
    else:
        assert summary["verdict"] == "NOT_OBSERVABLE_HERE", summary
        assert summary["receipt_columns_exempted"] == sorted(
            ["真实exit_code", "测量时刻UTC", "受测候选摘要", "运行收据"]), summary


def test_the_exempted_columns_are_the_onlyones_a_clone_cannot_reproduce(tmp_path):
    """Falsification for the exemption: a planted change in a *claimed* column still drifts."""
    module = _module()
    text = REGISTER.read_bytes().decode("utf-8-sig")
    folded = module._without_receipt_columns(text.replace("\r\n", "\n"))
    assert folded == module._without_receipt_columns(text.replace("\r\n", "\n"))
    planted = text.replace("真实进程启动 + loopback HTTP 实测", "真实进程启动 + 改写过的证据种类", 1)
    assert planted != text, "种入的改动没有落到字节上，这个反例什么都没测"
    assert module._without_receipt_columns(planted.replace("\r\n", "\n")) != folded, (
        "免检列之外的改动被吞掉了：克隆里的 --check 就变成永真")
    # and the receipt columns themselves are exactly what a clone is allowed to differ on
    only_receipt = text.replace("1（全量回归）", "0", 1).replace(
        "9e141b8edfa9f105", "0000000000000000", 1)
    if only_receipt != text:
        assert module._without_receipt_columns(
            only_receipt.replace("\r\n", "\n")) == folded


def test_the_resolver_is_not_vacuous_when_a_target_is_wrong():
    module = _module()
    resolved, detail = module._resolve_target(
        "tests/unified/test_v25_audit_item_closure.py::test_this_name_does_not_exist")
    assert not resolved, (resolved, detail)
    resolved, detail = module._resolve_target("migration/audit-item-closure.csv#19")
    assert not resolved, "行数钉错时解析器必须变红，而不是只看文件是否存在"
    assert "20" in detail, detail
    resolved, _ = module._resolve_target("migration/audit-item-closure.csv#20")
    assert resolved
