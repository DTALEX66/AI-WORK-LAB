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
        assert row["独立复审"] == "NOT_RUN", (
            row["ID"], "本候选尚未被独立复审；只有真实发生的复审可以替换这个值")


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
    before = REGISTER.read_bytes()
    finished = subprocess.run([sys.executable, "-B", "-X", "utf8", str(BUILDER), "--check"],
                              cwd=str(TARGET_ROOT), capture_output=True, text=True,
                              encoding="utf-8", errors="replace")
    assert finished.returncode == 0, (finished.stdout[-900:], finished.stderr[-900:])
    assert json.loads(finished.stdout)["register_drift"] is False
    assert REGISTER.read_bytes() == before, "--check 不得写跟踪登记"


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
