# SPDX-License-Identifier: MIT
"""V29: the root entry of the fused repository says what is true -- and can be shown wrong.

WORK-LAB and DESIGN-LAB are one project now, but that decision is not a migration report, and the
three root files a new agent reads first (`README.md`, `AGENTS.md`, `PROJECT_CURRENT.md`) are where a
stale figure does the most damage: whatever they assert becomes the premise the next session reasons
from. `scripts/check_project_current.py` re-derives every figure the entry quotes from the registers
on disk, resolves every repository path the entries cite, and refuses on mismatch.

These nodes do two things a "the file exists" test cannot:

* they run that check against the real entry and require it to come back clean;
* they **plant each defect** and require the specific finding to appear. A guard that cannot fail
  guards nothing -- every negative case below is the check being driven at a doctored copy, with the
  real registers still behind it, so the only variable is the document.
"""
from __future__ import annotations

import contextlib
import hashlib
import io
import json
import re
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
CHECKER = TARGET_ROOT / "scripts" / "check_project_current.py"
ENTRY = TARGET_ROOT / "PROJECT_CURRENT.md"
README = TARGET_ROOT / "README.md"
AGENTS = TARGET_ROOT / "AGENTS.md"
FIGURES_START = "<!-- entry-figures:start -->"
FIGURES_END = "<!-- entry-figures:end -->"


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", "-X", "utf8", str(CHECKER), *argv],
                          cwd=str(TARGET_ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)


def _report(result: subprocess.CompletedProcess) -> dict:
    assert result.stdout.strip(), (result.returncode, result.stderr[-800:])
    # one JSON document and nothing else: a pretty-printed report is still exactly one document,
    # so parsing the whole stdout is what pins "the tool printed only its receipt"
    return json.loads(result.stdout.strip())


def _figures(text: str) -> dict:
    body = text.split(FIGURES_START, 1)[1].split(FIGURES_END, 1)[0]
    return {m.group(1): int(m.group(2))
            for m in re.finditer(r"^([a-z][a-z0-9_]+) = (\d+)$", body, re.MULTILINE)}


def _doctored(tmp_path: Path, mutated) -> Path:
    """The real entry with one deliberate change, written beside nothing else."""
    text = ENTRY.read_text(encoding="utf-8")
    destination = tmp_path / "PROJECT_CURRENT.md"
    destination.write_text(mutated(text), encoding="utf-8", newline="\n")
    return destination


def test_the_root_entry_passes_the_anti_drift_check():
    """rc=0 with no findings, or the document is not allowed to keep its conclusions."""
    result = _run("--check")
    report = _report(result)
    assert report["verdict"] == "PASS", report["findings"]
    assert report["finding_count"] == 0, report["findings"]
    assert result.returncode == 0, (result.returncode, report["findings"])


def test_the_entry_carries_the_figures_the_registers_derive(tmp_path):
    """--print-block is the only place numbers come from, and the entry must equal it."""
    derived = _figures(_run("--print-block").stdout)
    stated = _figures(ENTRY.read_text(encoding="utf-8"))
    assert derived, "生成器没有给出任何数字"
    assert stated == derived, {key: (stated.get(key), derived.get(key))
                               for key in set(stated) | set(derived)
                               if stated.get(key) != derived.get(key)}


def test_a_stale_figure_in_the_entry_is_caught(tmp_path):
    """Plant around the figure the entry carries now -- a hardcoded number rots into a no-op.

    This node used to replace the literal `7108`. When the register moved to 7109 the replacement
    matched nothing, so no defect was planted, the checker stayed clean, and the falsifier quietly
    stopped falsifying while still passing.
    """
    current = re.search(r"^source_rows_total = (\d+)$", ENTRY.read_text(encoding="utf-8"),
                        re.MULTILINE)
    assert current, "入口里已经没有这一行，这个反例就没有可种的故障"
    real = int(current.group(1))
    planted = real - 1
    entry = _doctored(tmp_path, lambda text: text.replace("source_rows_total = %d" % real,
                                                          "source_rows_total = %d" % planted))
    report = _report(_run("--check", "--entry", str(entry)))
    stale = [f for f in report["findings"] if f.startswith("FIGURE_STALE")]
    assert stale == ["FIGURE_STALE source_rows_total 文档=%d 寄存器=%d" % (planted, real)], (
        report["findings"])


def test_a_stale_receipt_pointer_in_the_entry_is_caught(tmp_path):
    """The commit SHA in the entry's prose pointer is a claim about the registers, and can be planted.

    The marker block was re-derived and checked; the line above it -- "which tree the full-suite
    receipt measured" -- was checked by nothing, so the entry could keep naming an older binding
    while every derived figure had moved on.
    """
    text = ENTRY.read_text(encoding="utf-8")
    line = next((row for row in text.splitlines() if row.lstrip().startswith("- 依托提交")), "")
    assert line, "入口已经没有「- 依托提交」这一行，这个反例就没有可种的故障"
    stated = re.search(r"`([0-9a-f]{7,40})`", line)
    assert stated, "依托提交那行没有反引号里的提交 SHA，反例无从种起"
    planted = "0" * 7 if stated.group(1) != "0" * 7 else "1" * 7
    entry = _doctored(tmp_path, lambda body: body.replace(
        line, line.replace("`%s`" % stated.group(1), "`%s`" % planted, 1), 1))
    report = _report(_run("--check", "--entry", str(entry)))
    assert any(row.startswith("RECEIPT_POINTER_STALE 文档=%s" % planted)
               for row in report["findings"]), report["findings"]


def test_a_missing_figures_block_is_refused(tmp_path):
    """Silence is not agreement: an entry without the auditable block cannot be trusted."""
    def strip(text: str) -> str:
        start = text.index(FIGURES_START)
        end = text.index(FIGURES_END) + len(FIGURES_END)
        return text[:start] + text[end:]

    report = _report(_run("--check", "--entry", str(_doctored(tmp_path, strip))))
    assert "MISSING_FIGURES_BLOCK" in report["findings"], report["findings"]


def test_an_unparseable_figure_line_is_not_skipped(tmp_path):
    """A word where a number belongs must stop the check, not drop the row from the comparison."""
    entry = _doctored(tmp_path, lambda text: text.replace("capability_families = 30",
                                                          "capability_families = thirty"))
    report = _report(_run("--check", "--entry", str(entry)))
    assert any(f.startswith("UNPARSEABLE_FIGURE_LINE") for f in report["findings"]), \
        report["findings"]


def test_the_entry_must_name_the_blocking_owner_queue(tmp_path):
    """L10#0 is why the gate says REFUSED; an entry that quietly omits it would read as 'ready'."""
    entry = _doctored(tmp_path, lambda text: text.replace("L10#0", "该队列"))
    report = _report(_run("--check", "--entry", str(entry)))
    assert "BLOCKING_QUEUE_NOT_DISCLOSED L10#0" in report["findings"], report["findings"]


def test_the_read_order_puts_the_root_entry_first():
    """The order is the product: this session itself started under a source repository's rules."""
    agents = AGENTS.read_text(encoding="utf-8")
    assert "必读顺序" in agents and "更新责任" in agents
    first_item = agents.split("## 1. 必读顺序", 1)[1].splitlines()
    numbered = [line for line in first_item if re.match(r"^1\.\s", line)]
    assert numbered and "PROJECT_CURRENT.md" in numbered[0], numbered[:1]
    # the source repositories must be declared history here, or their AGENTS.md keeps governing
    assert "来源仓" in agents and "只读" in agents


def test_readme_reaches_the_entry_without_scrolling():
    readme = README.read_text(encoding="utf-8")
    head = "\n".join(readme.splitlines()[:10])
    assert "PROJECT_CURRENT.md" in head, head
    assert "合并" in head, head


def test_no_root_markdown_calls_itself_the_top_authority_but_one():
    """A second 'current' document is how two parallel authorities come back after a merge."""
    claimants = sorted(path.name for path in TARGET_ROOT.glob("*.md")
                       if "唯一顶层入口" in path.read_text(encoding="utf-8", errors="replace"))
    assert claimants == ["PROJECT_CURRENT.md"], claimants


def _gate_module():
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    import check_project_current
    return check_project_current


IMPORT_HEADER = """sha256,bytes,category,original_name,archive_path,action,target_rel,member_count,reason"""


def test_the_imported_object_list_can_be_shown_wrong(tmp_path, monkeypatch):
    """A row saying "this object is in the repo" must be contradicted by the repo itself.

    Without this the coverage check only ever passes: it reads a manifest generated from the bytes
    that are already there, so nothing demonstrates the two ways it can disagree -- the file
    vanishing, and the file holding different bytes than the row claims.
    """
    gate = _gate_module()
    fake = tmp_path / "docs" / "history" / "archive-objects-20261101"
    (fake / "by-sha").mkdir(parents=True)
    # the coverage check reads the reconciliation register first and refuses without it, so the
    # fixture carries one too -- this node is about the import manifest, not about a missing register
    register = tmp_path / "migration"
    register.mkdir(parents=True)
    (register / "archive-object-reconciliation-20261101.csv").write_text(
        "sha256,bytes,archive_path,projects,category,disposition,evidence,source_hint\n"
        + "a" * 64 + ",10,_资料库/a.md,[x],历史方案,ARCHIVED_IN_REPO,,Record/a.md\n",
        encoding="utf-8", newline="\n")
    payload = b'{"real": true}'
    (fake / "by-sha" / "aaaa.json").write_bytes(payload)
    digest = hashlib.sha256(payload).hexdigest()
    rows = [
        # a row whose bytes really are on disk
        digest + ",14,历史方案,x.json,_资料库/x.json,ARCHIVED_IN_REPO,"
        "docs/history/archive-objects-20261101/by-sha/aaaa.json,0,逐字节复验相符",
        # a row that claims the same thing about a file that is not there
        "0" * 64 + ",9,历史方案,y.json,_资料库/y.json,ARCHIVED_IN_REPO,"
        "docs/history/archive-objects-20261101/by-sha/missing.json,0,盘上没有这个文件",
    ]
    (fake / "ARCHIVE-OBJECTS-MANIFEST.csv").write_text(
        IMPORT_HEADER + "\n" + "\n".join(rows) + "\n", encoding="utf-8", newline="\n")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    kinds = [entry.split()[0] for entry in gate.check_archive_coverage()]
    assert "ARCHIVE_IMPORT_MANIFEST_MISSING" not in kinds, kinds
    assert "IMPORTED_BYTES_MISSING" in kinds, kinds
    assert "IMPORTED_DIGEST_STALE" not in kinds, (
        "逐字节相符的那行被报成摘要不符，说明比较的对象不是盘上的字节", kinds)


def test_a_destination_that_was_never_decided_is_refused(tmp_path, monkeypatch):
    """`ARCHIVE_ONLY` -- "we have not decided where this goes" -- is the drift state; it must be red.

    So must a disposition nobody defined: an enumeration the register can grow silently is how a
    coverage table starts meaning something other than what the checker tests.
    """
    gate = _gate_module()
    register = tmp_path / "migration"
    register.mkdir(parents=True)
    (register / "archive-object-reconciliation-20261101.csv").write_text(
        "sha256,bytes,archive_path,projects,category,disposition,evidence,source_hint\n"
        + "b" * 64 + ",10,_资料库/b.md,[x],历史方案,ARCHIVE_ONLY,,Record/b.md\n"
        + "c" * 64 + ",10,_资料库/c.md,[x],历史方案,SOMETHING_MADE_UP,,Record/c.md\n",
        encoding="utf-8", newline="\n")
    monkeypatch.setattr(gate, "ROOT", tmp_path)
    kinds = [entry.split()[0] for entry in gate.check_archive_coverage()]
    assert "DESTINATION_UNDECIDED" in kinds, kinds
    assert "UNKNOWN_DISPOSITION" in kinds, kinds


def test_an_unexplained_top_level_directory_is_refused(tmp_path):
    """The rule that names an undocumented root directory is driven at a tree that actually has one."""
    gate = _gate_module()
    (tmp_path / "PROJECT_CURRENT.md").write_text("# 入口\n\n只提到 apps 和 scripts。\n",
                                                 encoding="utf-8")
    (tmp_path / "apps").mkdir()
    (tmp_path / "mystery").mkdir()
    saved = gate.ROOT
    try:
        gate.ROOT = tmp_path
        findings, _machine_only = gate.check_entries(tmp_path / "PROJECT_CURRENT.md")
    finally:
        gate.ROOT = saved
    undocumented = [entry for entry in findings if entry.startswith("ROOT_DIR_UNDOCUMENTED")]
    assert any(entry.endswith("mystery") for entry in undocumented), findings
    assert not any("apps" in entry for entry in undocumented), (
        "被说明过的目录也被报未说明，这条规则测的就不是它声称的东西", undocumented)


def test_a_silently_shrinking_test_file_is_refused(tmp_path, monkeypatch):
    """The guard my own truncation proved was missing: "green" must not survive lost test functions.

    A rebuild of this very file cut it at the wrong index and dropped it from 12 nodes to 3, and the
    suite stayed green because the three survivors all passed. So this drives the census at a tree
    where a file lost declared tests and requires it to name the file and the from/to counts. The
    write path is covered too: shrinking is refused unless the loss is declared with --allow.
    """
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    import build_test_census as census_tool

    published = {"schema": "ai-work-lab/test-node-census/v1", "files": 2, "tests": 15,
                 "nodes": {"tests/unified/test_a.py": {"tests": 12, "bytes": 100, "sha256": "x"},
                           "tests/unified/test_b.py": {"tests": 3, "bytes": 50, "sha256": "y"}}}
    census_path = tmp_path / "node-census.json"
    census_path.write_text(json.dumps(published), encoding="utf-8", newline="\n")
    monkeypatch.setattr(census_tool, "OUT", census_path)
    truncated = dict(published, tests=6,
                     nodes={"tests/unified/test_a.py": {"tests": 3, "bytes": 30, "sha256": "z"},
                            "tests/unified/test_b.py": published["nodes"]["tests/unified/test_b.py"]})
    monkeypatch.setattr(census_tool, "census", lambda: truncated)

    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = census_tool.main(["--check"])
    report = json.loads(buffer.getvalue())
    assert rc == 1, "少了一半节点还报匹配，这个闸门就是装饰"
    assert report["drift"]["files_that_lost_tests"] == [["tests/unified/test_a.py", 12, 3]], report
    assert (report["tests_published"], report["tests_now"]) == (15, 6), report

    with contextlib.redirect_stdout(io.StringIO()):
        write_rc = census_tool.main([])
    assert write_rc == 3, "删测试应当被拒，而不是顺手把清单改小来迎合它"
    assert json.loads(census_path.read_text(encoding="utf-8"))["tests"] == 15, (
        "被拒之后清单必须还是原来那份")


def test_the_declared_test_census_still_matches_this_checkout():
    """The census is a tracked artefact, so it has to be re-derivable from the tree it describes.

    This is the positive control for the guard above, run against the real repository: if somebody
    edits a suite file without regenerating the census, or regenerates it after losing nodes, this
    is where it surfaces -- not as a silently smaller suite.
    """
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    import build_test_census as census_tool
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = census_tool.main(["--check"])
    report = json.loads(buffer.getvalue())
    assert rc == 0, report.get("drift") or report
    assert report["matches"] is True, report
    assert report["tests_now"] > 400, "套件读数不可能这么小：扫描范围错了"


def test_the_figure_writer_repairs_a_stale_copy_then_changes_nothing(tmp_path):
    """`--write-block` must be able to do its job, and must not restamp a document that is already right.

    The entry's tail is generated, so the writer is the only legitimate way to move those numbers.
    Two properties make it safe to run before a measurement instead of only after one: it repairs a
    doctored copy (proving it is not a no-op that always reports success), and a second run on the
    repaired file leaves the bytes alone (proving a refresh does not silently move tracked bytes and
    take a receipt off the tree it describes).
    """
    copy = tmp_path / "PROJECT_CURRENT.md"
    original = ENTRY.read_bytes()
    stale = original.decode("utf-8").replace("suite_test_nodes = ", "suite_test_nodes_planted = ")
    copy.write_bytes(stale.encode("utf-8"))
    first = _report(_run("--write-block", "--entry", str(copy)))
    assert first["verdict"] == "WRITTEN", first
    assert b"suite_test_nodes_planted" not in copy.read_bytes(), (
        "写回必须按现算的键名替换，被改坏的键留着就等于检查器看不见它")
    check = _report(_run("--check", "--entry", str(copy)))
    assert check["verdict"] == "PASS" and check["finding_count"] == 0, check["findings"]
    after_repair = copy.read_bytes()
    second = _report(_run("--write-block", "--entry", str(copy)))
    assert second["verdict"] == "UNCHANGED", second
    assert copy.read_bytes() == after_repair, "第二次写把已经正确的文件又改了一次：生成器在重戳"


def test_the_receipt_anchor_line_is_derived_and_a_second_one_is_refused(tmp_path):
    """The line that names the measured tree is now derived, and duplicates are a refusal.

    It used to hold three hand-typed values -- the commit, the suite tally and the file count --
    which are the first things a rebinding moves. An entry can otherwise say "the receipt measured
    `78b3866`" for months after the receipt changed, and the prose looks completely sane.
    """
    copy = tmp_path / "PROJECT_CURRENT.md"
    original = ENTRY.read_text(encoding="utf-8")
    stale = original.replace("全量收据所测的那棵树是 `", "全量收据所测的那棵树是 `000000000000` （手写占位 `")
    copy.write_text(stale, encoding="utf-8")
    first = _report(_run("--write-block", "--entry", str(copy)))
    assert first["verdict"] == "WRITTEN", first
    line = [row for row in copy.read_text(encoding="utf-8").splitlines()
            if row.startswith("- 依托提交：")]
    assert len(line) == 1, line
    assert "000000000000` （手写占位" not in line[0], line[0]
    check = _report(_run("--check", "--entry", str(copy)))
    assert check["finding_count"] == 0, check["findings"]

    duplicated = copy.read_text(encoding="utf-8").replace(
        line[0], line[0] + chr(10) + line[0], 1)
    copy.write_text(duplicated, encoding="utf-8")
    refused = _report(_run("--write-block", "--entry", str(copy)))
    assert refused["verdict"] == "REFUSED" and "恰好一行" in refused["error"], refused


def test_the_figure_writer_refuses_a_document_missing_its_markers(tmp_path):
    """No markers means the block is hand-written prose, and prose is not this tool's to replace."""
    copy = tmp_path / "no-markers.md"
    copy.write_text("# 一份没有 figures 标记的文档\n\nsuite_test_nodes = 1\n",
                    encoding="utf-8", newline="\n")
    report = _report(_run("--write-block", "--entry", str(copy)))
    assert report["verdict"] == "REFUSED", report
    assert copy.read_text(encoding="utf-8").count("suite_test_nodes") == 1, (
        "拒绝必须一个字都不写")



def test_a_regeneration_with_identical_readings_writes_no_bytes(tmp_path, monkeypatch):
    """The census lives under `tests/`, where the receipt clause allows nothing -- so it must not restamp.

    Re-running the producers after a receipt is the normal closing move, and the census is one of
    them. If it rewrote `generated_at` on identical readings, the rebinding commit would carry a
    tracked change under `tests/`, the receipt clause would (correctly) refuse it, and the only way
    out would be a third measurement for a number that did not change. Both directions are asserted:
    identical readings keep the file byte-for-byte, a real gain still gets written.
    """
    sys.path.insert(0, str(TARGET_ROOT / "scripts"))
    import build_test_census as census_tool

    published = {"schema": "ai-work-lab/test-node-census/v1",
                 "generated_at": "2026-01-01T00:00:00+00:00", "files": 2, "tests": 15,
                 "unified_tests": 15, "legacy_tests": 0,
                 "scope": "tests/ only", "observed_from": "static scan",
                 "nodes": {"tests/unified/test_a.py": {"tests": 12, "bytes": 100, "sha256": "x"},
                           "tests/unified/test_b.py": {"tests": 3, "bytes": 50, "sha256": "y"}}}
    census_path = tmp_path / "node-census.json"
    original_bytes = (json.dumps(published, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    census_path.write_bytes(original_bytes)
    monkeypatch.setattr(census_tool, "OUT", census_path)

    same = dict(published, generated_at="2026-11-02T09:00:00+00:00")
    monkeypatch.setattr(census_tool, "census", lambda: same)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = census_tool.main([])
    assert rc == 0, buffer.getvalue()
    assert json.loads(buffer.getvalue())["verdict"] == "UNCHANGED", buffer.getvalue()
    assert census_path.read_bytes() == original_bytes, (
        "读数一模一样却换了时间戳：这次写会把收据从它描述的树上摘下来")

    grown = dict(same, tests=16, nodes=dict(same["nodes"], **{
        "tests/unified/test_a.py": {"tests": 13, "bytes": 110, "sha256": "x2"}}))
    monkeypatch.setattr(census_tool, "census", lambda: grown)
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        rc = census_tool.main([])
    assert rc == 0, buffer.getvalue()
    assert "verdict" not in json.loads(buffer.getvalue()), (
        "真的有新增节点时必须写：不写的话清单就永远落后于套件")
    assert json.loads(census_path.read_text(encoding="utf-8"))["tests"] == 16


def test_a_register_that_nothing_reads_or_declares_is_refused():
    """The hygiene gate must name an orphan register, and must stop naming it once it is declared.

    A tracked file under `migration/` or `config/` that no script touches and the entry does not
    vouch for is a second truth: it keeps reading as current long after whatever produced it is
    gone. The population is enumerated from git in production; here the pure function is driven so
    the refusal -- and the release -- are both observable.
    """
    checker = _gate_module()
    registers = ["migration/live.csv", "migration/orphan-20261102.json", "config/kept.json"]
    vocabulary = "open(ROOT / 'live.csv')  # generated and read\n" + "kept.json"
    entry_text = "| 现行登记 | `migration/live.csv`、`config/kept.json` | 链接 |"
    findings = checker.register_declaration_findings(registers, entry_text, vocabulary)
    assert len(findings) == 1, findings
    assert findings[0].startswith("REGISTER_UNDECLARED migration/orphan-20261102.json"), findings
    # declaring it in the entry is what releases it -- not deleting the gate's population
    declared = entry_text + " | 血统件 | `migration/orphan-20261102.json` | 后继是 live.csv |"
    assert checker.register_declaration_findings(registers, declared, vocabulary) == []
    # and the real tree is clean: every tracked register is read by a script or vouched by the entry
    real = checker.registers_on_disk()
    assert len(real) > 20, "the enumeration came back with almost nothing to check: %s" % real
    entry_full = (TARGET_ROOT / "PROJECT_CURRENT.md").read_text(encoding="utf-8")
    assert checker.register_declaration_findings(
        real, entry_full, checker.register_vocabulary()) == [], (
        "有登记既不接进任何生成器，也没在入口 §四 声明角色：%s"
        % checker.register_declaration_findings(real, entry_full, checker.register_vocabulary()))


def test_a_tracked_file_this_run_cannot_read_refuses_instead_of_shrinking_the_count(tmp_path):
    """The denominators may only change when a file really changes.

    Measured this round: the entry said 736 LF-tracked files while the register computed 737, and
    neither was wrong about its own run -- the difference was one archived file sitting past
    Windows' 260-character limit, which ``path.is_file()`` reports as absent. A count that depends
    on where the checkout happens to live is not a fact about the repository, and skipping the
    unreadable file made the omission invisible.
    """
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "checker_refuse", TARGET_ROOT / "scripts" / "check_project_current.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    try:
        checker._refuse_unreadable("line_endings", ["docs/history/deep.md"])
    except SystemExit as exit_error:
        assert "TRACKED_FILE_UNREADABLE" in str(exit_error) and "docs/history/deep.md" in str(exit_error)
    else:
        raise AssertionError("读不到的跟踪件被静默跳过：分母少一格而无人说话")
    checker._refuse_unreadable("line_endings", [])


def test_the_deepest_tracked_files_are_actually_read():
    """The extended-length fallback must work on the real tree, not only in the helper."""
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "checker_deep", TARGET_ROOT / "scripts" / "check_project_current.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)

    deepest = max((rel for rel in checker._tracked_files()), key=lambda rel: len(str(checker.ROOT / rel)))
    assert len(str(checker.ROOT / deepest)) > 250, (
        "本仓不再有超过 MAX_PATH 的跟踪件了？那这条守卫要按现读改写：%s 个字符"
        % len(str(checker.ROOT / deepest)))
    assert checker._read_tracked(deepest) is not None,         "最深的跟踪件仍然读不到：分母又会按检出位置变化（%s）" % deepest
    counts = checker.line_endings()
    assert counts["crlf"] + counts["lf"] > 0, counts


def _checker(name: str):
    import importlib.util
    spec = importlib.util.spec_from_file_location(name, CHECKER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_a_prose_copy_of_a_derived_figure_that_drifts_is_named():
    """The managed block is derived; the same numbers repeated in prose were checked by nothing.

    The independent review at `f616fb5` found ``694`` / ``217,126,876`` still standing in §二 and
    §五 long after the register said 692 / 215,124,851 -- the 2026-11-02 credential withdrawal
    moved the figure and only the managed block moved with it.
    """
    checker = _checker("checker_prose_figures")
    derived = checker.derive_figures()
    text = ENTRY.read_text(encoding="utf-8")
    assert checker.prose_figure_findings(text, derived) == [], (
        "入口散文里已经有一处抄件与派生值不符，这个反例就不是唯一变量："
        + str(checker.prose_figure_findings(text, derived)))
    planted = text.replace("`1212` 个唯一对象", "`1213` 个唯一对象", 1)
    assert planted != text, "种故障用的那句话不在入口里，种下去的是空气"
    findings = checker.prose_figure_findings(planted, derived)
    assert any(item.startswith("PROSE_FIGURE_STALE archive_objects") for item in findings), findings


def test_a_prose_duplicate_that_no_shape_binds_is_named():
    """A number may repeat a figure value only under a bound sentence shape.

    Without this half the table would just record the occurrences the author happened to notice:
    the next hand-typed copy -- equal to today's value, so harmless today -- is the one that rots.
    """
    checker = _checker("checker_prose_unbound")
    derived = checker.derive_figures()
    text = ENTRY.read_text(encoding="utf-8") + "\n- 抽查一句：这里写 30 个不属于任何形状的量。\n"
    findings = checker.prose_figure_findings(text, derived)
    assert any(item.startswith("PROSE_FIGURE_UNBOUND") and "30" in item for item in findings), (
        "一处与派生值同数的散文抄件被当成巧合放过了：" + str(findings))


def test_a_present_tense_suite_reading_outside_the_derived_line_is_named():
    """§五 used to say "收据现在测 `520 passed…`" -- true for one commit, a lie for every later one.

    A suite line is not a figure key, so the number guard cannot re-derive it. What can be
    checked is the *tense*: the derived 「- 依托提交：」 line is the only place allowed to state
    a current receipt reading, and anything else has to name which section it came from.
    """
    checker = _checker("checker_receipt_claim")
    text = ENTRY.read_text(encoding="utf-8")
    receipt = checker.named_receipt(checker.ROOT)
    if receipt is None:
        # a fresh clone carries no archived receipt: the contract there is that this guard says
        # nothing at all rather than inventing a comparison -- asserted, not skipped
        assert checker.receipt_claim_findings(text, None) == []
        return
    assert checker.receipt_claim_findings(text, receipt) == [], (
        "入口已经有第二处现在时的收据读数：" + str(checker.receipt_claim_findings(text, receipt)))
    planted = text + "\n- 抽查：收据现在测 `1 passed / 0 failed`，它绑在某棵树上。\n"
    findings = checker.receipt_claim_findings(planted, receipt)
    assert any(item.startswith("RECEIPT_CLAIM_NOT_DERIVED") for item in findings), findings
    # a dated reading that says where it came from must stay legal, or the guard would push the
    # entry to delete history it is entitled to keep
    dated = text + "\n- 抽查：§15.32 那次重测记 `363 passed, 1 warning`（当时的读数）。\n"
    assert checker.receipt_claim_findings(dated, receipt) == [], (
        "点名出处的历史读数被误判成现在时抄件")


def test_a_shape_or_exemption_kept_past_the_sentence_it_guarded_is_named():
    """Both tables must be able to rot loudly, not quietly become decoration."""
    checker = _checker("checker_prose_dead")
    derived = checker.derive_figures()
    text = ENTRY.read_text(encoding="utf-8")
    shapes = checker.PROSE_FIGURE_SHAPES
    try:
        checker.PROSE_FIGURE_SHAPES = (("archive_objects", r"入口里不存在这句话 ([\d,]+)"),)
        findings = checker.prose_figure_findings(text, derived)
        assert any("PROSE_FIGURE_SHAPE_DEAD" in item for item in findings), findings
    finally:
        checker.PROSE_FIGURE_SHAPES = shapes
    exemptions = checker.PROSE_FIGURE_COINCIDENTAL
    try:
        checker.PROSE_FIGURE_COINCIDENTAL = (
            (r"入口里不存在这句豁免", ("route_endpoints",), "只为反例存在"),)
        findings = checker.prose_figure_findings(text, derived)
        assert any("PROSE_FIGURE_EXEMPT_DEAD" in item for item in findings), findings
    finally:
        checker.PROSE_FIGURE_COINCIDENTAL = exemptions
