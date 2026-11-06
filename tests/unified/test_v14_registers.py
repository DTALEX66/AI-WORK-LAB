# SPDX-License-Identifier: MIT
"""V14: the registers and packaged assets this rework now claims, checked as data.

The claims below were made in prose during the rework and prose cannot be audited, so
each is turned into a recomputation here:

* the source-coverage register must account for **every** non-ignored file in both
  read-only sources, with no row in a class that means "we did not look";
* the F01 disposition register must stay at the audited 198 registered-but-uncopied
  WORK paths, each with a digest and a stated reason;
* the two F06 gaps that were closable offline are closed in fact: the host bridge
  script must be reachable at the path the adapter probes and byte-identical to the
  source of truth, and the control plane must parse a YAML document instead of
  reporting `DOCUMENT_UNPARSEABLE`;
* since 2026-11-01, the owner-rule destination columns must carry a closed vocabulary:
  the enumeration the builder declares and the values the published rows actually hold
  differ by the empty set in both directions, every value is recomputed from the
  archive ledger rather than remembered, and each refusal is planted and proven red.
"""
from __future__ import annotations

import csv
import collections
import hashlib
import io
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

TARGET_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(TARGET_ROOT / "scripts"))
import source_roots  # noqa: E402  the one place roots outside this checkout are resolved
#: venv 解释器的布局是平台的，不是机器的：Windows 是 Scripts/python.exe，POSIX 是 bin/python（审计 N05）。
VENV_PYTHON = str(TARGET_ROOT / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python"))
WORK_SOURCE = source_roots.work_root()
DESIGN_SOURCE = source_roots.design_root()
BRIDGE_PACKAGED = (TARGET_ROOT / "domains" / "design" / "design_lab" / "resources"
                   / "adobe" / "photoshop-native-assemble.jsx")
BRIDGE_SOURCE_OF_TRUTH = (TARGET_ROOT / "integrations" / "hosts" / "adobe"
                          / "photoshop-reconstruction" / "legacy-assemble.jsx")
#: owner 2026-11-01 规则的唯一归档台账：覆盖登记表的 archive_* 三列逐行现算自它。
ARCHIVE_LEDGER = (TARGET_ROOT / "docs" / "history" / "sources-20261101" / "MANIFEST.csv")

#: Classes that would mean the register did not actually decide anything.
UNEXPLAINED = {"", "SOURCE_UNREGISTERED", "COPIED_MISSING_IN_TARGET"}

#: The rows the adjudication ladder genuinely could not decide, enumerated by path.
#: This used to be 226 rows sharing one template reason and a guard test that only
#: looked for the literal word "owner" — that cannot fail, so it was not a check.
#: A row may join this set only by a deliberate edit here, and a row that leaves it
#: must be picked up by an authority-backed class instead.
PENDING_OWNER_DECISIONS = {
    "work": frozenset({
        "apps/observer/scripts/u19_webview_e2e.py",
        "apps/observer/scripts/usage_rollup.py",
        "apps/observer/scripts/write_artifact_receipt.py",
        "apps/observer/src/observer_evidence.py",
        "apps/observer/src/observer_runtime.py",
        "apps/observer/src/observer_state_classification.py",
        "apps/observer/src/observer_store.py",
        "integrations/archeaxis/contracts/open_design_client_seam.py",
        "integrations/archeaxis/contracts/promotion_contract.py",
        "scripts/audit/bundle_provenance.py",
        "scripts/audit/hud_strip_geometry_via_cdp.py",
        "scripts/audit/text_legibility_via_cdp.py",
        "scripts/audit/topbar_geometry_via_cdp.py",
        "scripts/maintenance/absorb_local_assets.py",
        "scripts/maintenance/converge_u02_runtime_paths.py",
        "scripts/maintenance/finish_tmp_tree_cleanup.py",
        "scripts/maintenance/record_documentation_drifts.py",
        "services/policy/universal_agent_core.py",
    }),
    "design": frozenset({
        "design-lab/core/__init__.py",
        "design-lab/core/commands.py",
        "design-lab/core/project_state.py",
        "design-lab/core/providers.py",
        "design-lab/core/quality_gate.py",
        "design-lab/core/user_modes.py",
        "design-lab/scripts/effective_evidence.py",
        "design-lab/scripts/resolve_open_design_locator.py",
        "scripts/amend_source_lock_presence.py",
        "scripts/archive_records.py",
        "scripts/collect_design_capability_candidates.py",
        "scripts/deepseek_test_gate_report.py",
        "scripts/generate_current_reports.py",
        "scripts/run_python_tests.py",
    }),
}

#: Classes that must each carry a resolvable ``file:line`` authority citation.
ADJUDICATED_CLASSES = {"UNREGISTERED_TARGET_PATH_PRESENT", "UNREGISTERED_EXCLUDED_CAPABILITY",
                       "UNREGISTERED_DEV_TOOLING"}
_CITATION = re.compile(r"^(.+?):(\d+)$")


def _read(csv_path: Path) -> list[dict]:
    with csv_path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _ledger_rows() -> list[dict]:
    """The 2026-11-01 archive ledger as rows: one per coverage row, fan-out included."""
    return _read(ARCHIVE_LEDGER)


def _ledger_index() -> dict:
    """The same ledger keyed by (repo, path), read independently of the builder.

    Read here rather than taken from the builder so the register and the ledger are
    compared by two separate readers of the same file: a builder that quietly invented
    its own ledger would still have to match these rows. Two verdicts for one source
    file are a refusal, not a last-write-wins.
    """
    out = {}
    for row in _ledger_rows():
        key = (row["repo"], row["path"].replace("\\", "/"))
        if key in out and out[key] != row:
            pytest.fail("同一来源文件在台账里有两种去向：" + key[1])
        out[key] = row
    return out


def _absent_source_note(roots: list[Path]) -> str | None:
    """Name a read-only source root this machine does not have, or ``None`` if all are here.

    Only the *root's* absence is a machine prerequisite. A root that exists still has to
    agree byte for byte with the register, so naming the absence can never swallow the drift
    these nodes exist to catch -- which is the difference between a skip and an excuse.
    """
    missing = [str(root) for root in roots if not root.is_dir()]
    if not missing:
        return None
    named = {entry["name"]: entry["root"] for entry in source_roots.absent_roots()}
    return ("the read-only source root(s) %s are not on this machine (%s); the registers "
            "enumerate those trees, so this run cannot re-verify them here"
            % (", ".join(missing), ", ".join(sorted(named))))


def _coverage(tmp_path_factory) -> dict:
    out = tmp_path_factory.mktemp("coverage") / "source-coverage.json"
    completed = subprocess.run(
        [VENV_PYTHON, "-B", "-X", "utf8",
         str(TARGET_ROOT / "scripts" / "build_source_coverage.py"),
         "--json-out", str(out)],
        cwd=str(TARGET_ROOT), capture_output=True, text=True, timeout=3000,
        encoding="utf-8", errors="replace")
    if completed.returncode == 3:
        # The builder's designed answer to a missing source tree. It is a prerequisite of this
        # machine, not a register defect -- and the refusal is checked by name, so an rc=3 for
        # anything else still fails here instead of being excused.
        payload = json.loads((completed.stdout.strip().splitlines() or ["{}"])[-1])
        assert payload.get("error") == "SOURCE_REPO_ABSENT", payload
        pytest.skip("build_source_coverage refused with SOURCE_REPO_ABSENT: %s"
                    % ", ".join(entry["root"] for entry in payload["absent"]))
    assert completed.returncode == 0, completed.stderr[-2000:]
    return json.loads(out.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def coverage(tmp_path_factory) -> dict:
    return _coverage(tmp_path_factory)


_COVERAGE_MODULE = None


def _coverage_module():
    """The coverage builder as a module object, so one rule has one implementation."""
    global _COVERAGE_MODULE
    if _COVERAGE_MODULE is None:
        import importlib.util
        spec = importlib.util.spec_from_file_location(
            "build_source_coverage_live", TARGET_ROOT / "scripts" / "build_source_coverage.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _COVERAGE_MODULE = module
    return _COVERAGE_MODULE


def test_prose_authority_cites_point_at_a_section_and_stay_valid_when_prose_grows(tmp_path):
    """A citation into prose must survive somebody editing the prose; a line number cannot.

    42 rows used to cite ``docs/CODEX-AUDIT-ENTRY.md:140``. Every section appended below line 140
    left the citation "resolvable" while it silently pointed at whatever had slid into that row,
    and every section appended ABOVE it moved all 42 at once. So the cite now names the section,
    and this test writes a document, cites it, then grows the document inside and after that
    section: the cite still resolves, and an anchor that no heading carries -- or that two do --
    is refused. The planted refusals are the point: without them the resolver could be vacuous.
    """
    module = _coverage_module()
    root = tmp_path / "clone"
    docs = root / "docs"
    docs.mkdir(parents=True)
    original = module.REPO_ROOT
    module.REPO_ROOT = root
    try:
        (docs / "entry.md").write_text(
            "# 标题\n\n## 4. 复核步骤\n\n关键句 NOT_RUN 在这里\n\n## 5. 下一节\n\n别的\n",
            encoding="utf-8")
        assert module.resolve_authority_cite("docs/entry.md#§4") == (True, "section §4")
        # paragraphs added inside and after the cited section must not move the citation
        (docs / "entry.md").write_text(
            "# 标题\n\n## 4. 复核步骤\n\n" + "\n".join("新增段落 %d" % i for i in range(40))
            + "\n\n关键句 NOT_RUN 在这里\n\n## 5. 下一节\n\n"
            + "\n".join("尾部段落 %d" % i for i in range(40)) + "\n", encoding="utf-8")
        assert module.resolve_authority_cite("docs/entry.md#§4")[0] is True
        # and the anchor the builder writes for a needle inside that section is the section
        # itself: the producing rule and the checking rule are the same function
        scanned = module.AUTHORITY_SCANNED
        module.AUTHORITY_SCANNED = dict(scanned, entry=docs / "entry.md")
        try:
            assert module._line_of("entry", "关键句 NOT_RUN 在这里") == "docs/entry.md#§4"
        finally:
            module.AUTHORITY_SCANNED = scanned
        bad = module.resolve_authority_cite("docs/entry.md#§9")
        assert bad[0] is False and "no heading resolves" in bad[1], bad
        (docs / "twin.md").write_text("## 4. a\n\nx\n\n## 4. b\n\ny\n", encoding="utf-8")
        ambiguous = module.resolve_authority_cite("docs/twin.md#§4")
        assert ambiguous[0] is False and "ambiguous" in ambiguous[1], ambiguous
        assert module.resolve_authority_cite("docs/nope.md#§4")[0] is False
        assert module.resolve_authority_cite("docs/entry.md:99999")[0] is False
        assert module.resolve_authority_cite("docs/entry.md:1:2")[0] is False
        assert module.resolve_authority_cite("docs/entry.md:AUTHORITY_NOT_FOUND")[0] is False
        assert module.resolve_authority_cite("")[0] is False
    finally:
        module.REPO_ROOT = original


def test_a_code_authority_is_anchored_on_the_definition_not_on_a_line_number(tmp_path):
    """The register's self-citations moved 152 of 294 rows onto a different construct; now they cannot.

    Measured on 2026-11-04 against the registers as published: 152 of the 294 line-number cites no
    longer sat inside the def, class or assignment that produced them, and every one of them still
    resolved -- a line number is never *wrong*, it is only about a different line than it was. The
    numbers were correct each time the builder ran, which is exactly why the drift looked harmless.
    Code cites therefore anchor on the definition holding the line -- a def, class or module-level
    assignment; where the line is a bare statement no symbol covers, or the name occurs twice, the
    number stays, because a wrong anchor is worse than a moving one.
    """
    module = _coverage_module()
    root = tmp_path / "clone"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    original = module.REPO_ROOT
    module.REPO_ROOT = root
    source = ('"""Builder docstring."""\n'
              'CONST = 1\n'
              'raise SystemExit("boot")\n'
              'def adjudicate(kind):\n'
              '    UNREGISTERED_TARGET_PATH_PRESENT = kind\n'
              '    return UNREGISTERED_TARGET_PATH_PRESENT\n')
    try:
        (scripts / "builder.py").write_text(source, encoding="utf-8")
        scanned = module.AUTHORITY_SCANNED
        module.AUTHORITY_SCANNED = dict(scanned, self=scripts / "builder.py")
        try:
            cite = module._line_of("self", "UNREGISTERED_TARGET_PATH_PRESENT = kind")
            assert cite == "scripts/builder.py::adjudicate", cite
            assert module.resolve_authority_cite(cite) == (True, "symbol adjudicate")
            # 200 lines above the cited text: the anchor must not move
            (scripts / "builder.py").write_text(
                "".join("# pad %d\n" % i for i in range(200)) + source, encoding="utf-8")
            # all three caches are per-run by design (the builder reads each authority once); a test
            # that rewrites the file has to reset them, or it would be asserting on a stale snapshot
            module._LINE_CACHE.clear()
            module._SYMBOL_CACHE.clear()
            module._PROSE_CACHE.clear()
            assert module._line_of("self", "UNREGISTERED_TARGET_PATH_PRESENT = kind") == cite, (
                "the anchor still moved with the line count")
            assert module.resolve_authority_cite(cite)[0] is True
            # a module-level assignment is its own definition, so it anchors too
            assert module._line_of("self", "CONST = 1") == "scripts/builder.py::CONST"
            # a module-level statement no symbol covers keeps the number -- and that number is
            # now 200 lines further down than the file it was written against, which is the whole
            # reason the symbol form exists
            number = module._line_of("self", 'raise SystemExit("boot")')
            assert number == "scripts/builder.py:203", number
            assert module.resolve_authority_cite(number)[0] is True
            # a name defined twice cannot be an anchor -- it would not say which one
            (scripts / "twin.py").write_text("def dup():\n    return 1\n\n\ndef dup():\n    return 2\n",
                                             encoding="utf-8")
            module.AUTHORITY_SCANNED = dict(scanned, self=scripts / "twin.py")
            assert module._line_of("self", "return 2") == "scripts/twin.py:6", (
                "an ambiguous symbol name was anchored anyway: %s"
                % module._line_of("self", "return 2"))
            # and the resolver refuses both a missing name and a file that is not Python
            assert module.resolve_authority_cite("scripts/builder.py::nowhere")[0] is False
            assert module.resolve_authority_cite("scripts/twin.py::dup")[0] is False
        finally:
            module.AUTHORITY_SCANNED = scanned
    finally:
        module.REPO_ROOT = original


def test_a_code_needle_mentioned_in_prose_above_the_statement_cites_the_statement(tmp_path):
    """A fragment lookup for code takes the first line that *is* code -- and prose hides in four places.

    32 rows of the two registers cited line 23 of ``build_source_coverage.py``, a sentence of its own
    module docstring, because the needle is introduced in prose before it is returned in code and the
    lookup stopped at the earliest line containing it. Fixing that to "the first line a symbol spans"
    then produced ``::_line_of`` for the same needle: a docstring *inside* a function is spanned by
    that function, so it is prose that has moved inside a definition. A comment is the third way, and
    a module-level statement that no definition spans is the fourth -- it is code, but it has no
    address to name, so it must not win over a line that does. All four are planted in one synthetic
    file here: drop any one exclusion and the cite names a different place, which is what makes each
    of them a guard rather than decoration.
    """
    module = _coverage_module()
    root = tmp_path / "clone"
    scripts = root / "scripts"
    scripts.mkdir(parents=True)
    original = module.REPO_ROOT
    module.REPO_ROOT = root
    try:
        (scripts / "ladder.py").write_text(
            '"""模块说明里提到 NEEDLE_TOKEN 一次。\n'
            '仅出现在文档字符串里的短语。\n'
            '"""\n'
            'print("NEEDLE_TOKEN")\n'
            'def documented():\n'
            '    """函数文档字符串又提到 NEEDLE_TOKEN。\n'
            '    """\n'
            '    return 1\n'
            '\n'
            'def commented():\n'
            '    # 注释里也提到 NEEDLE_TOKEN\n'
            '    return 2\n'
            '\n'
            'def produces():\n'
            '    return ("NEEDLE_TOKEN", "value")\n', encoding="utf-8")
        scanned = module.AUTHORITY_SCANNED
        module.AUTHORITY_SCANNED = dict(scanned, self=scripts / "ladder.py")
        try:
            cite = module._line_of("self", "NEEDLE_TOKEN")
            assert cite == "scripts/ladder.py::produces", cite
            assert module.resolve_authority_cite(cite) == (True, "symbol produces")
            # a needle that exists only in prose keeps the number rather than being dragged to a def:
            # line 2 is inside the module docstring, which no symbol spans
            prose = module._line_of("self", "仅出现在文档字符串里的短语。")
            assert prose == "scripts/ladder.py:2", prose
            assert module.resolve_authority_cite(prose)[0] is True
            # a needle that is nowhere in the file is refused, not pointed at the nearest neighbour
            missing = module._line_of("self", "NEVER_WRITTEN_ANYWHERE")
            assert missing.endswith("AUTHORITY_NOT_FOUND"), missing
            assert module.resolve_authority_cite(missing)[0] is False
        finally:
            module.AUTHORITY_SCANNED = scanned
    finally:
        module.REPO_ROOT = original

def test_coverage_register_accounts_for_every_source_file(coverage):
    note = _absent_source_note([WORK_SOURCE, DESIGN_SOURCE])
    if note:
        pytest.skip(note)
    for label, repo in (("work", WORK_SOURCE), ("design", DESIGN_SOURCE)):
        document = coverage["repos"][label]
        listed = subprocess.check_output(
            ["git", "ls-files", "--cached", "--others", "--exclude-standard", "-z"],
            cwd=str(repo)).decode("utf-8").split("\0")
        files = sorted(x for x in set(listed) if x
                       and not {".mimosa", "__pycache__", ".pytest_cache", ".venv",
                                "node_modules"} & set(Path(x).parts)
                       and (repo / x).is_file())
        rows = _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv"))
        # 登记人群 = 来源工作树 ∪ 台账点名的来源路径。台账是永久记录，工作树只是某一个分支的检出，
        # 只比工作树就会漏掉"分支头有、检出没展开"的文件——那一行曾经静静少掉一个来源文件。
        ledger_paths = {entry["path"] for entry in _ledger_rows() if entry["repo"] == label}
        assert sorted({row["path"] for row in rows}) == sorted(set(files) | ledger_paths), (
            label + "：登记表人群不等于「工作树 ∪ 台账」，要么漏了盘上的文件，要么丢了台账点名的文件")
        assert document["reconciles"] is True, document["class_counts"]
        assert sum(document["class_counts"].values()) == document["rows"], label


def test_coverage_register_leaves_no_row_undecided(coverage):
    """"无未解释遗漏" as a falsifiable claim, not a substring match.

    The clause V01 checks has two halves. The first is that no row sits in a class
    that means "we did not look". The second, added on 2026-10-31, is that the
    remaining undecided population equals an enumerated set: 226 rows carrying one
    template reason passed the old assertion because that reason contained the
    literal word "owner", which is not a decision and was not a check.
    """
    for label in ("work", "design"):
        rows = _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv"))
        for row in rows:
            assert row["class"], row
            assert row.get("reason") or row["class"].startswith("COPIED_VERIFIED"), row
            assert row["class"] not in UNEXPLAINED, row
            if row["class"] in ADJUDICATED_CLASSES:
                cites = [c.strip() for c in re.split(r";| → ", row.get("authority", ""))]
                assert cites and cites != [""], row
                for cite in cites:
                    ok, why = _coverage_module().resolve_authority_cite(cite)
                    assert ok, (row["class"], cite, why)

        pending = [row for row in rows if row["class"] == "OWNER_DECISION_PENDING"]
        assert frozenset(row["path"] for row in pending) == PENDING_OWNER_DECISIONS[label], (
            label, sorted(frozenset(row["path"] for row in pending)
                          - PENDING_OWNER_DECISIONS[label]),
            sorted(PENDING_OWNER_DECISIONS[label]
                   - frozenset(row["path"] for row in pending)))
        assert len(pending) == len(PENDING_OWNER_DECISIONS[label]), label
        assert pending and all(row["path"].endswith(".py") for row in pending)
        # one row, one justification: no shared template may cover the population
        reasons = [row["reason"] for row in pending]
        assert len(set(reasons)) == len(reasons), [
            reason for reason in set(reasons) if reasons.count(reason) > 1][:3]
        for row in pending:
            assert row["reason"].count("待 owner 判定") == 1, row
            # the justification names this row's own bytes, not the class it fell into
            assert row["reason"].startswith("待 owner 判定（本行字节 "
                                            + row["source_sha256"][:12] + "）"), row
            assert "NONE（无现成权威覆盖此行）" in row["authority"], row
            # the half after the arrow is a citation like any other, and the pending population is
            # exactly the rows the loop above does not reach -- so until now an unresolvable anchor
            # on a pending row would have stayed invisible. The joiner in this template carries no
            # leading space, which is why the split cannot assume one; the resolver's own refusal of
            # a missing name is planted in the anchor node, and this consumes that same function.
            cite = re.split(r";|\s*→\s*", row["authority"])[-1].strip()
            ok, why = _coverage_module().resolve_authority_cite(cite)
            assert ok, (row["path"], cite, why)
        adjudicated = [row for row in rows if row["class"] in ADJUDICATED_CLASSES]
        assert adjudicated, label
        # the register must say which population it adjudicated, per repo
        document = coverage["repos"][label]
        assert document["adjudicated_by_authority_count"] == len(adjudicated), label
        assert sorted(document["adjudicated_by_authority"]) == sorted(
            row["path"] for row in adjudicated), label
        assert document["pending_reason_duplicates"] == {}, document["pending_reason_duplicates"]
        assert document["pending_owner_decision_count"] == len(pending), label


def test_archive_disposition_enumeration_equals_every_published_value(coverage):
    """owner 2026-11-01 规则的去向列：声明词表与实际行值的双向差集必须都是空集。

    三列 ``archive_*`` 由 ``docs/history/sources-20261101/MANIFEST.csv`` 现算，不是第二份
    归档台账。这里同时钉住四件事：每个来源文件都有一个非空去向（"每个来源文件都有一行去向"
    这条不变式不因规则而缩水）、行值全在词表内、词表里没有失效项、以及台账人群与登记表
    人群双向相等。行数不写死在本文件里：它等于台账该仓的行数，来源树一旦移动，红的是台账
    过期而不是一个被手抄的数字。抽样复验的是位置真的持有该来源的字节，不是又一次自我声明。
    """
    module = _coverage_module()
    declared = set(module.ARCHIVE_DISPOSITIONS)
    assert len(declared) == len(module.ARCHIVE_DISPOSITIONS), "词表里有重复项"
    ledger = _ledger_index()
    rows_by_repo = collections.Counter(entry["repo"] for entry in _ledger_rows())
    actual = set()
    for label in ("work", "design"):
        rows = _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv"))
        ledger_paths = {path for (repo, path) in ledger if repo == label}
        assert len(rows) == rows_by_repo[label], (
            label + "：登记表的行数与台账的行数不再是同一个人群（"
            + str(len(rows)) + " vs " + str(rows_by_repo[label]) + "）")
        assert {row["path"] for row in rows} == ledger_paths, label
        assert all({"archive_disposition", "archive_target", "archive_evidence"}
                   <= set(row) for row in rows), label + "：三列必须都已发布"
        blank = [row["path"] for row in rows if not row["archive_disposition"]]
        assert blank == [], (label + "：这些来源文件在 owner 规则下没有去向：" + str(blank[:5]))
        actual |= {row["archive_disposition"] for row in rows}
        findings = module.archive_vocabulary_findings(rows)
        assert findings == [], (label + "：" + " | ".join(findings[:3]))
    assert actual - declared == set(), ("行值不在声明词表内：" + str(sorted(actual - declared)))
    assert declared - actual == set(), ("词表声明了没有任何行使用的失效项："
                                        + str(sorted(declared - actual)))
    # 去向是"位置"，不是"能力已验证"：ARCHIVED_IN_REPO 的行仍由 class 说迁移事实
    archived = [row for label in ("work", "design")
                for row in _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv"))
                if row["archive_disposition"] == "ARCHIVED_IN_REPO"]
    assert archived, "ARCHIVED_IN_REPO 一行都没有：词表已经失效"
    for row in archived[::37]:
        payload = module._read_bytes_any(TARGET_ROOT / row["archive_target"])
        assert payload is not None, (row["path"], row["archive_target"])
        assert hashlib.sha256(payload).hexdigest() == row["source_sha256"], (
            "归档位置并不持有该来源的字节：" + row["archive_target"])


def test_archive_dispositions_are_recomputed_from_the_ledger_not_remembered(coverage):
    """每一行的处置都能由台账的 action 现算出来，且排除行的两种理由分得开。

    台账把 5102 COPIED 与 300 DUPLICATED 记成两类 action；本表把它们归入同一个处置，因为
    两者的字节都在本仓历史区（DUPLICATED 是同 SHA 去重后指回那份原件），上一项测试已逐行
    复验其字节。EXCLUDED 则必须能按 reason 现算出「缓存与构建」和「截图照片」两族，否则
    owner 后加的「截图照片去掉」在登记表里就消失了。台账里一旦出现 FAILED 或任何未登记的
    action，本表拒绝发布——所以这里断言的是映射关系，不是某个记忆住的数字。
    """
    module = _coverage_module()
    ledger = _ledger_index()
    counts = collections.Counter()
    excluded_families = collections.Counter()
    for label in ("work", "design"):
        for row in _read(TARGET_ROOT / ("migration/source-coverage-" + label + ".csv")):
            entry = ledger[(label, row["path"])]
            assert row["archive_disposition"] == module.ARCHIVE_ACTION_LABELS[entry["action"]], (
                label, row["path"], entry["action"], row["archive_disposition"])
            counts[row["archive_disposition"]] += 1
            if row["archive_disposition"] == "EXCLUDED_BY_OWNER_RULE":
                excluded_families[module._excluded_family(entry["reason"])] += 1
                assert "owner 2026-11-01" in row["archive_evidence"], row
                assert row["archive_target"] == "", row
    expected = collections.Counter(
        module.ARCHIVE_ACTION_LABELS[entry["action"]] for entry in _ledger_rows())
    assert dict(counts) == dict(expected), (dict(counts), dict(expected))
    assert set(excluded_families) == {"缓存与构建", "截图照片"}, dict(excluded_families)
    summary = coverage["owner_rule_archive"]
    rows_by_repo = collections.Counter(entry["repo"] for entry in _ledger_rows())
    for label in ("work", "design"):
        assert sum(summary["counts_by_repo"][label].values()) == rows_by_repo[label], label
    assert summary["excluded_by_family"] == dict(excluded_families), summary
    assert summary["ledger_actions"] == dict(collections.Counter(
        entry["action"] for entry in _ledger_rows())), summary
    assert set(summary["ledger_actions"]) <= set(module.ARCHIVE_ACTION_LABELS), summary


def test_the_archive_disposition_guard_can_actually_fail(tmp_path):
    """每种拒绝都要能到达，否则词表只是装饰。

    在临时副本里逐一植入：一个不存在的处置、一个空值、一个指向不存在文件的位置、一个命名了
    位置却被排除的行、以及把一个处置整族抹掉造成的失效枚举项。每次只改一处，并断言对应的
    那句拒绝真的出现——先命中的分支不能把后面的 finding 吃掉。最后一遍用真实登记表证明同
    一个调用返回空集，否则这条守卫只是在永远报警。
    """
    module = _coverage_module()
    rows = _read(TARGET_ROOT / "migration/source-coverage-work.csv")
    assert module.archive_vocabulary_findings(rows) == [], "真实登记表本身就带着拒绝项"

    def planted(mutate):
        copy = [dict(row) for row in rows]
        mutate(copy)
        # 写进临时副本再读回来：守卫检查的是寄存器文件，不是内存里的字典
        out = tmp_path / "source-coverage-work-planted.csv"
        with out.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(copy)
        with out.open(encoding="utf-8-sig", newline="") as handle:
            return module.archive_vocabulary_findings(list(csv.DictReader(handle)))

    def make_bogus(document):
        document[3]["archive_disposition"] = "ARCHIVED_IN_REPO_BUT_NOT_REALLY"
    findings = planted(make_bogus)
    assert any("ARCHIVED_IN_REPO_BUT_NOT_REALLY" in text for text in findings), findings

    def make_blank(document):
        document[4]["archive_disposition"] = ""
    findings = planted(make_blank)
    assert any("空值" in text for text in findings), findings

    def make_ghost(document):
        for row in document:
            if row["archive_disposition"] in module.IN_REPO_ARCHIVE_LABELS:
                row["archive_target"] = "docs/history/sources-20261101/work/nowhere.svg"
                break
    findings = planted(make_ghost)
    assert any("命名的仓内位置不在树上" in text for text in findings), findings

    def name_a_location(document):
        for row in document:
            if row["archive_disposition"] == "EXCLUDED_BY_OWNER_RULE":
                row["archive_target"] = "docs/history/sources-20261101/work/should-not-exist"
                break
    findings = planted(name_a_location)
    assert any("排除行不应命名位置" in text for text in findings), findings

    def drop_a_value(document):
        for row in document:
            if row["archive_disposition"] == "ARCHIVED_ELSEWHERE_LINKED":
                row["archive_disposition"] = "ARCHIVED_IN_REPO"
    findings = planted(drop_a_value)
    assert any("失效的枚举项" in text and "ARCHIVED_ELSEWHERE_LINKED" in text
               for text in findings), findings


def test_f01_register_separates_wired_from_merely_present():
    """The ``目标文件 exists`` claim is not a wiring claim, and is no longer one.

    ``git_collector.py`` sits in the target tree and imports cleanly, so the old
    assertion could never fail; the only ``git_collector`` in running code is an
    inline ``def`` inside ``collectors.py``. The register now carries the graph's
    answer per row, so this checks the answer rather than the file.
    """
    rows = _read(TARGET_ROOT / "migration/work-gap-disposition.csv")
    assert rows and {"运行面消费者", "消费者数"} <= set(rows[0]), list(rows[0])
    wired = [row for row in rows if row["去向类别"] == "MIGRATED_WIRED"]
    for row in wired:
        consumers = [c for c in row["运行面消费者"].split(";") if c]
        assert consumers, row
        assert int(row["消费者数"]) == len(consumers), row
        assert all((TARGET_ROOT / c).is_file() for c in consumers), row
    for row in rows:
        if row["去向类别"] == "MIGRATED_PRESENT_UNWIRED":
            assert row["运行面消费者"] == "" and row["消费者数"] == "0", row
            assert "没有找到任何 importer" in row["判定依据"], row
    by_path = {row["原路径"]: row for row in rows}
    false_claim = "packages/client-neutral-core/scripts/git_collector.py"
    assert by_path[false_claim]["去向类别"] == "MIGRATED_PRESENT_UNWIRED", by_path[false_claim]
    assert by_path[false_claim]["目标文件"] == "domains/work/orchestration/git_collector.py"
    assert (TARGET_ROOT / "domains/work/orchestration/git_collector.py").is_file(), \
        "downgraded does not mean deleted: the bytes stay, the claim changes"


def test_coverage_gap_rows_match_the_f01_register(coverage):
    """The two registers must not disagree about the same file.

    The counts used to be pinned to the literal the audit recorded (198). That made a real
    closure look like a breakage: when ``adapter_conformance.py`` was actually migrated, the
    gap set legitimately became 197 and four remembered numbers went red at once. The check
    is now the one that matters -- the two builders, which read different inputs, must agree
    with each other and with the register file -- with a floor so an emptied population can
    never pass, and with the distance from the audited baseline stated rather than assumed.
    """
    disposition = _read(TARGET_ROOT / "migration/work-gap-disposition.csv")
    check = coverage["cross_check"]
    assert check["f01_register_reports_work_python_gaps"] == len(disposition), check
    assert check["registered_gap_python_paths_by_repo"]["work"] == len(disposition), check
    assert check["gap_delta_since_audit"] == 198 - len(disposition), check
    assert 190 <= len(disposition) <= 198, (
        "去向登记只剩 %d 行：population 缩水到这个程度只会是计算口径坏了，不是缺口被关掉"
        % len(disposition))
    coverage_gaps = {row["path"] for row in
                     _read(TARGET_ROOT / "migration/source-coverage-work.csv")
                     if row["class"] == "REGISTERED_GAP" and row["path"].endswith(".py")}
    assert coverage_gaps == {row["原路径"] for row in disposition}
    for row in disposition:
        assert len(row["来源sha256"]) == 64, row
        assert row["去向类别"] and row["判定依据"], row


def test_registered_non_python_gaps_state_where_the_file_actually_is(coverage):
    """"Not in the copy manifest" is not "absent" — the register has to say which.

    Two of the seven registered non-``.py`` gaps are WORK registry files the F01
    module migration placed at this repository's own ``config/`` root; the rest are
    governance documents and a frontend file. Reporting all of them as gaps would
    be the same mistake the audited close-out made in reverse.
    """
    rows = [row for row in _read(TARGET_ROOT / "migration/source-coverage-work.csv")
            if row["class"] == "REGISTERED_GAP" and not row["path"].endswith(".py")]
    assert len(rows) == 7, [row["path"] for row in rows]
    by_path = {row["path"]: row for row in rows}
    for path in ("config/adapter-registry.json", "config/capability-matrix.json"):
        assert by_path[path]["disposition"].startswith("PRESENT_IN_TARGET"), by_path[path]
        target = TARGET_ROOT / by_path[path]["disposition_target"]
        assert target.is_file(), path
        source = WORK_SOURCE / path
        same = (hashlib.sha256(target.read_bytes()).hexdigest()
                == hashlib.sha256(source.read_bytes()).hexdigest())
        assert same == (by_path[path]["disposition"] == "PRESENT_IN_TARGET"), by_path[path]


def test_duplicate_candidates_are_recomputable_and_deferrals_carry_a_reason():
    """V01's second half — "重复项与延期有理由" — as two checks that can fail.

    Nothing asserted this before: the duplicate register was prose the suite never
    opened, so "identical bytes, therefore a duplicate" could have been stale or
    wrong and the run would still have been green. Each group's digest is recomputed
    from both read-only sources here, and each deferral row must name what it keeps.
    """
    document = json.loads((TARGET_ROOT / "migration" / "duplicate-candidates.json")
                          .read_text(encoding="utf-8"))
    groups = document["groups"]
    assert len(groups) == document["group_count"], "group_count is not the number of groups"
    sources = json.loads((TARGET_ROOT / "migration" / "sources.json").read_text(encoding="utf-8"))
    assert sources["duplicate_candidate_groups"] == len(groups)

    note = _absent_source_note([WORK_SOURCE, DESIGN_SOURCE])
    if note:
        pytest.skip(note)
    verified = 0
    for group in groups:
        digest = group["sha256"]
        assert len(digest) == 64, group
        assert group["work"] and group["design"], \
            "a duplicate candidate must be the same bytes on both sides: " + digest[:12]
        for side, root in (("work", WORK_SOURCE), ("design", DESIGN_SOURCE)):
            for entry in group[side]:
                prefix, _, relative = entry.partition(":")
                assert prefix in {"WORK-LAB", "DESIGN-LAB"}, entry
                path = root / relative
                assert path.is_file(), entry
                assert hashlib.sha256(path.read_bytes()).hexdigest() == digest, entry
                verified += 1
    assert verified >= 2 * len(groups), (verified, len(groups))

    rows = [line for line in (TARGET_ROOT / "migration" / "deferred-register.md")
            .read_text(encoding="utf-8").splitlines() if line.startswith("| D-")]
    assert len(rows) >= 13, len(rows)
    for line in rows:
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        assert len(cells) == 10, cells
        identifier, kept, gap, priority = cells[0], cells[3], cells[4], cells[5]
        assert identifier.startswith("D-"), cells
        assert kept and kept not in {"—", "-"}, ("延期必须写明保留的实现/合同/入口", cells)
        assert gap and priority, ("延期必须有差距与分期", cells)
    excluded = [line for line in rows if "排除" in line]
    assert excluded, "the owner's explicit exclusions must be recorded as exclusions"
    for line in excluded:
        assert "手机" in line or "字库" in line or "素材" in line or "企业" in line, line


def test_host_bridge_script_is_reachable_where_the_adapter_probes():
    """F06 packaging gap, closed on the packaged path rather than by moving code."""
    from design_lab.adapters import photoshop_com
    assert photoshop_com._bridge() == BRIDGE_PACKAGED.read_bytes()
    assert BRIDGE_PACKAGED.read_bytes() == BRIDGE_SOURCE_OF_TRUTH.read_bytes(), \
        "the packaged copy has drifted from the source of truth"


def test_control_plane_parses_yaml_now_that_the_dependency_is_present():
    """The one real import the project venv lacked, and the behaviour it gated."""
    from domains.work.control import control_service
    resolved, state = control_service._field_presence("adapter:\n  verb: save\n", "adapter.verb")
    assert state == "KEY_PATH_RESOLVES" and resolved is True, (resolved, state)
    missing, state_missing = control_service._field_presence("adapter:\n  other: 1\n",
                                                            "adapter.verb")
    assert state_missing == "KEY_PATH_RESOLVES" and missing is False, (missing, state_missing)
    not_mapping, state_bad = control_service._field_presence("- a\n- b\n", "adapter.verb")
    assert (not_mapping, state_bad) == (None, "DOCUMENT_NOT_A_MAPPING")
    absent, state_absent = control_service._field_presence(None, "adapter.verb")
    assert (absent, state_absent) == (None, "FILE_ABSENT")


#: pip subcommands that can reach an index, and therefore must be pinned offline.
PIP_NETWORK_SUBCOMMANDS = {"wheel", "install", "download", "index", "search"}
#: pip invocations that are read-only by construction. Listed explicitly so the
#: test does not quietly widen "every pip line" to lines that cannot carry the
#: switches (``pip config list`` is recorded without ``--isolated`` on purpose —
#: ``--isolated`` is what suppresses the config it is there to read).
PIP_READ_ONLY_SUBCOMMANDS = {"config", "--version"}


def _pip_subcommand(command: list[str]) -> str:
    after = command[command.index("pip") + 1:]
    for token in after:
        if not token.startswith("-"):
            return token
        if token == "--version":
            return token
    return ""


def test_local_dependency_step_is_recorded_and_reversible():
    """The environment change is evidence, not an undocumented mutation.

    What this JSON says about the network is a self-report — the same operation
    wrote it — so the claim is checked against things the record cannot assert
    its way into: the source must be a real local path, no field may name a
    scheme, and the files it claims to have placed must be where it says. The
    pip half of the offline story is checked separately, from command lines.
    """
    document = json.loads((TARGET_ROOT / ".project-local/audit/20261030-qoder-ed9037"
                           / "local-dependency-step.json").read_text(encoding="utf-8"))
    assert document["network_used"] is False
    assert document["source_version"] == "PyYAML 6.0.3"
    assert document["import_probe"]["exit_code"] == 0
    assert document["deliberately_removed_binaries"], "the cp312 extension must not ship"
    # independent of that self-report: no URL, and the "source" really is a path
    blob = json.dumps(document, ensure_ascii=False)
    assert "http://" not in blob and "https://" not in blob and "pip install" not in blob
    source = Path(document["source"])
    assert source.is_dir(), "the claimed offline cache source does not exist locally"
    assert source.is_absolute() and not source.drive.startswith(("E:", "F:"))
    destination = Path(document["destination"])
    assert destination.is_dir(), destination
    for distribution, files in document["packages_added"].items():
        placed = destination / distribution
        assert placed.is_dir(), distribution
        for name in files:
            assert (placed / name).is_file(), (distribution, name)
    for removed in document["deliberately_removed_binaries"]:
        assert not (destination / removed).exists(), removed
    rollback = (TARGET_ROOT / ".project-local/audit/20261030-qoder-ed9037"
                / "rollback-local-dependency-step.ps1")
    assert rollback.is_file()
    text = rollback.read_text(encoding="utf-8")
    assert text.count("Remove-Item") == 2 and "yaml" in text, text


def test_offline_install_pip_command_lines_are_actually_offline():
    """``network_used: false`` is not evidence; the pip argv is.

    Every recorded pip line is re-read from the build reports and checked for the
    two switches that make an index unreachable. A line that runs a
    network-capable subcommand without them, or a network-capable subcommand that
    is not in the declared set, fails here even if the report's own summary says
    the run was offline.
    """
    import importlib.util

    reports = sorted((TARGET_ROOT / ".project-local" / "build").glob("*/build-report.json"))
    assert reports, ("no offline build report on this machine: .project-local is not in "
                     "Git, so this claim can only be re-checked where the build ran")
    spec = importlib.util.spec_from_file_location(
        "offline_install_under_test", TARGET_ROOT / "scripts" / "build_offline_install.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert "--isolated" in module.PIP_GLOBAL, module.PIP_GLOBAL
    assert module.PIP_OFFLINE == ["--no-index"], module.PIP_OFFLINE

    seen = 0
    for report in reports:
        document = json.loads(report.read_text(encoding="utf-8"))
        steps = document.get("steps") or []
        assert steps, report
        for step in steps:
            command = step["command"]
            if "pip" not in command:
                continue
            seen += 1
            subcommand = _pip_subcommand(command)
            assert subcommand in (PIP_NETWORK_SUBCOMMANDS | PIP_READ_ONLY_SUBCOMMANDS), \
                (report, command)
            if subcommand in PIP_NETWORK_SUBCOMMANDS:
                assert "--no-index" in command, (report, command)
                assert "--isolated" in command, (report, command)
                assert "--no-deps" in command, (report, command)
                assert "download" not in command, (report, command)
            else:
                assert subcommand in PIP_READ_ONLY_SUBCOMMANDS, (report, command)
    assert seen >= len(reports), (seen, len(reports))
    # the report's own offline summary must agree with the argv it recorded
    for report in reports:
        document = json.loads(report.read_text(encoding="utf-8"))
        if "network_used" in document:
            assert document["network_used"] is False, document["network_used"]


def _push_authorization_head(path: Path) -> str:
    """The commit a recorded push authorization binds, or "" when the record does not name one.

    Read here rather than inferred from the hook's own output: the guard's prose and the guard's
    verdict must not be the same string, or this comparison proves nothing.
    """
    try:
        return str(json.loads(path.read_bytes().decode("utf-8-sig")).get("head_commit") or "")
    except (ValueError, OSError):
        return ""


def test_pre_push_guard_is_present_and_blocking(tmp_path):
    """A00「不推送不发布」has to be an assertion that can fail, not a sentence in a doc.

    The hook is a mistype-guard, not network isolation. The first-upload round the owner
    authorised moved it out and back by digest without using ``--no-verify``, so this pins
    the three facts that make that exception auditable: the guard is still there, still
    wired at the default path, and still refuses when actually invoked — locally, with a
    dummy ref line on stdin, never a real push.
    """
    import shutil

    hook = TARGET_ROOT / ".git" / "hooks" / "pre-push"
    assert hook.is_file(), "pre-push guard is gone; the mistype-guard was supposed to survive"
    body = hook.read_text(encoding="utf-8", errors="replace")
    assert body.startswith("#!"), body[:40]
    assert "exit 1" in body, body[:200]

    moved = subprocess.run(["git", "config", "--get", "core.hooksPath"], cwd=str(TARGET_ROOT),
                           capture_output=True, text=True, encoding="utf-8", errors="replace")
    assert moved.stdout.strip() == "", ("core.hooksPath points away from .git/hooks: "
                                        + moved.stdout)

    shell = shutil.which("sh") or shutil.which("bash")
    assert shell, "no POSIX shell available to invoke the hook locally"

    # The refusal is proven in a scratch repository, not here. Invoked against this checkout the
    # guard consults `.project-local/push-authorization-*.json`, and once the owner has authorised
    # a push that file names a head -- so this node used to go red for the unrelated reason that
    # HEAD had advanced onto the commit the previous round pushed. A guard that lets an authorised
    # push through is correct, and a test that cannot say so is a test whose verdict is an accident
    # of machine state.
    (tmp_path / "a.txt").write_text("one tracked file so the tree is not empty\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    hooks = tmp_path / ".git" / "hooks"
    hooks.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(str(hook), str(hooks / "pre-push"))
    subprocess.run(["git", "add", "a.txt"], cwd=str(tmp_path), check=True, capture_output=True)
    subprocess.run(["git", "-c", "user.email=t@example.invalid", "-c", "user.name=probe",
                    "commit", "-q", "-m", "probe"], cwd=str(tmp_path), check=True,
                   capture_output=True)
    refused = subprocess.run([shell, str(tmp_path / ".git" / "hooks" / "pre-push"),
                              "origin", "git@example.invalid:nowhere.git"],
                             input="refs/heads/probe " + "0" * 40 + " refs/heads/probe "
                                   + "1" * 40 + "\n",
                             capture_output=True, text=True, encoding="utf-8", errors="replace",
                             cwd=str(tmp_path), timeout=120)
    combined = (refused.stdout or "") + (refused.stderr or "")
    assert refused.returncode != 0, ("the guard pushed with no authorization on disk", combined)
    assert "BLOCKED" in combined, combined
    assert "head_commit" in combined and "授权" in combined, (
        "the guard refused for some reason other than the missing authorization, so the "
        "refusal path this node is about is not the one being exercised: " + combined[-400:])

    probe = subprocess.run([shell, str(hook), "origin", "git@example.invalid:nowhere.git"],
                           input="refs/heads/probe " + "0" * 40 + " refs/heads/probe "
                                + "1" * 40 + "\n",
                           capture_output=True, text=True, encoding="utf-8", errors="replace",
                           cwd=str(TARGET_ROOT), timeout=120)
    head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(TARGET_ROOT),
                          capture_output=True, text=True, encoding="utf-8").stdout.strip()
    # read the authorization records here instead of trusting the hook's own prose, so the two
    # sides of this comparison are not the same value printed twice
    authorised = [path.name for path in (TARGET_ROOT / ".project-local").glob(
        "push-authorization-*.json")
        if _push_authorization_head(path) == head]
    if authorised:
        assert probe.returncode == 0, (
            "an authorization naming this head exists (%s) but the guard still refused: %s"
            % (authorised, (probe.stdout + probe.stderr)[-400:]))
    else:
        assert probe.returncode != 0, (
            "no authorization names this head and yet the guard let the push through: "
            + probe.stdout + probe.stderr)
    # v2 of the guard refuses for a *reason the owner can satisfy*, not a blanket no: it demands a
    # recorded authorization whose head_commit equals the head being pushed, and it runs the tracked
    # public-surface checker. Both facts are pinned so the guard cannot be quietly gutted later.
    assert "push-authorization" in body, "guard no longer requires a recorded push authorization"
    assert "check_public_hazards.py" in body, "guard no longer runs the tracked credential checker"
    executed = [line for line in body.splitlines() if not line.strip().startswith("#")]
    assert not any("--no-verify" in line for line in executed), (
        "the guard may mention --no-verify in a comment, but must not run it")


def test_aws_temporary_key_shape_is_caught_and_a_bad_checksum_does_not_waive_it():
    """GitHub 报的是 `ASIA…`，而这个族从来不在我们的扫描清单里——把它钉死。

    两条性质都直接调扫描器自己的函数：临时会话密钥（`ASIA`）与 CloudFront 密钥对 id（`APKA`）必须是命中；
    而校验和不匹配不得把命中降级成"没事"——正是那套降级逻辑造成了四条告警之下的"0 处活体"自信结论。
    夹具本身也断言：种下去的 body 必须是 16 位。第一版这里种了 21 位，于是"检测失败"其实是夹具错。
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "hazards_under_test", TARGET_ROOT / "scripts" / "check_public_hazards.py")
    haz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(haz)

    planted = {"ASIA": "ABCDEFGHJKLMNPQR", "APKA": "ABCDEFGHIJKLMNOP",
               "AKIA": "ABCDEFGHIJKLMNOP"}
    for prefix, body_text in planted.items():
        assert len(body_text) == 16, "夹具得是 16 位，否则测的是拼写不是检测"
        value = prefix + body_text
        hits = list(haz.FAMILIES["aws-key-id"].finditer(
            "X-Amz-Credential=%s/20260307/us-east-1" % value))
        assert hits, "%s 形态没被抓到：族清单又漏了" % prefix
        assert hits[0].group(1) == prefix
    assert haz.structure_note("AKIA", "ABCDEFGHIJKLMNOP") == "crc-mismatch", "校验和计算本身要能给出信息"
    assert "AKIAABCDEFGHIJKLMNOP" in {v.upper() for v in haz.CANONICAL_EXAMPLES}
    assert haz.SHORTHAND.match("x" * 20) and not haz.SHORTHAND.match("ABCDEFGHJKLMNPQR")
    assert haz.EXAMPLE_LITERAL.match("your_token_here_xxxx")
    assert not haz.EXAMPLE_LITERAL.match("ABCDEFGHJKLMNPQR"), "随机形状不得被示例规则放过"


def test_a_credential_quarantine_that_left_the_bytes_in_repo_is_a_finding(tmp_path):
    """具名处置必须付出代价：说"已隔离"却把字节留在公开面里，就是第二条假绿。"""
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "checker_under_test", TARGET_ROOT / "scripts" / "check_project_current.py")
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    assert "QUARANTINED_CREDENTIALS" in checker.ADMITTED_DISPOSITIONS

    sha = "0" * 64
    rows = [{"sha256": sha, "action": "QUARANTINED_CREDENTIALS", "reason": "写明的理由",
             "target_rel": "x", "bytes": "14"}]
    (tmp_path / (sha + ".json")).write_text("still published", encoding="utf-8")
    assert checker.credential_quarantine_findings(rows, tmp_path, root=tmp_path) == [
        "QUARANTINE_NOT_ACTUAL " + sha[:12]]

    (tmp_path / (sha + ".json")).unlink()
    assert checker.credential_quarantine_findings(rows, tmp_path, root=tmp_path) == []
    rows[0]["reason"] = ""
    assert checker.credential_quarantine_findings(rows, tmp_path, root=tmp_path) == [
        "QUARANTINE_REASON_MISSING " + sha[:12]]


def test_every_adobe_host_bridge_is_packaged_and_byte_identical():
    """Each adapter probes ``design_lab/resources/adobe/<name>`` FIRST, so that copy is
    the product surface — and it must be the source repository's own bytes, not a
    hand-copied look-alike.

    This started as a Photoshop-only guard. The Illustrator bridge was absent from the
    packaged layout and from the migration rules, which made ILLUSTRATOR_BRIDGE_MISSING
    reachable for the wrong reason; both are now declared in ``FILE_COPIES``, so the pair
    is asserted together to keep the second one from drifting back out.
    """
    cases = [
        ("photoshop",
         TARGET_ROOT / "domains/design/design_lab/resources/adobe/photoshop-native-assemble.jsx",
         DESIGN_SOURCE / "integrations/hosts/adobe/photoshop-reconstruction/legacy-assemble.jsx"),
        ("illustrator",
         TARGET_ROOT / "domains/design/design_lab/resources/adobe/reconstruction-assemble.jsx",
         DESIGN_SOURCE / "integrations/hosts/adobe/illustrator/reconstruction-assemble.jsx"),
    ]
    for label, packaged, _truth in cases:
        assert packaged.is_file(), label + " bridge is not packaged where the adapter probes"
    note = _absent_source_note([DESIGN_SOURCE])
    if note:
        # Only the comparison against the source's bytes is unobservable here; the packaged
        # half above ran, and a packaged bridge that no longer matches still fails below.
        pytest.skip(note)
    for label, packaged, truth in cases:
        assert packaged.read_bytes() == truth.read_bytes(), (
            label + " bridge drifted from the source repository's bytes")

    # the adapters must resolve exactly their own packaged path, in source layout
    sys.path.insert(0, str(TARGET_ROOT / "domains" / "design"))
    try:
        from design_lab.adapters import illustrator_com, photoshop_com
    except ImportError as exc:  # pragma: no cover - install layout is asserted elsewhere
        pytest.fail("adapters unimportable in this layout: " + str(exc))
    assert b"illustrator" in illustrator_com._bridge().lower()
    assert photoshop_com is not None


STAMPED_REGISTERS = ("config/blocker-register.json", "migration/deferral-register.json",
                     "config/isolated-install-verdict.json", "migration/api-contract-check.json")


def test_the_shared_stamp_rule_keeps_a_stamp_only_when_the_payload_is_unchanged(tmp_path):
    """`scripts/published_stamp.py` is the single rule behind four tracked registers.

    Three cases, because each is a different way to be wrong: an identical payload must come back
    with the moment already on disk (otherwise a no-op rebuild moves the audited candidate digest);
    a payload whose content changed must take the new moment (otherwise a real edit hides behind an
    old timestamp); and a missing or unparseable file must fall through to a fresh stamp instead of
    declaring equality -- a rule that "kept" a stamp it could not read would pin a stale moment to
    changed bytes and look like stability.
    """
    import importlib.util as _importlib

    spec = _importlib.spec_from_file_location(
        "published_stamp_v14", str(TARGET_ROOT / "scripts" / "published_stamp.py"))
    module = _importlib.module_from_spec(spec)
    spec.loader.exec_module(module)
    keep = module.keeping_the_recorded_stamp

    path = tmp_path / "register.json"
    path.write_text(json.dumps({"generated_at": "T0", "rows": [1, 2]}, ensure_ascii=False),
                    encoding="utf-8")
    same = keep(path, {"generated_at": "T1", "rows": [1, 2]})
    assert same["generated_at"] == "T0", same
    changed = keep(path, {"generated_at": "T1", "rows": [1, 2, 3]})
    assert changed["generated_at"] == "T1", changed
    key_order = keep(path, {"rows": [1, 2], "generated_at": "T1"})
    assert key_order["generated_at"] == "T0", key_order

    absent = tmp_path / "nowhere.json"
    assert keep(absent, {"generated_at": "T1", "rows": []})["generated_at"] == "T1"
    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    assert keep(corrupt, {"generated_at": "T1", "rows": []})["generated_at"] == "T1"


def test_every_stamped_register_in_git_carries_a_parseable_stamp_field():
    """The registers the rule governs are named here, not remembered.

    If one of them stops being JSON with a ``generated_at``, the shared rule silently does nothing
    for it and that file goes back to moving the digest on every build -- so the population is read
    from the list and each member is checked for the shape the rule requires.
    """
    for relative in STAMPED_REGISTERS:
        path = TARGET_ROOT / relative
        assert path.is_file(), relative
        document = json.loads(path.read_text(encoding="utf-8-sig"))
        assert isinstance(document, dict) and "generated_at" in document, relative
        assert document["generated_at"], relative


def test_no_register_carries_a_doubled_line_ending():
    """``write_text`` without ``newline=""`` translates every \\n into \\r\\n, so a CSV that
    already ended rows with \\r\\n comes out as \\r\\r\\n: one phantom empty row per record.

    DictReader skips empty rows silently, so row counts, status histograms and every
    downstream test stayed green while two shipped registers were byte-malformed. This
    guard reads raw bytes because no text-mode reader can see the defect.
    """
    offenders = {}
    for path in sorted((TARGET_ROOT / "migration").rglob("*.csv")):
        blob = path.read_bytes()
        doubled = blob.count(b"\r\r\n")
        if doubled:
            offenders[path.name] = doubled
    assert offenders == {}, ("registers with doubled line endings (phantom empty rows): "
                             + str(offenders))


def test_coverage_row_identity_is_the_pair_and_the_extra_rows_are_the_fan_out():
    """Row count > path count is a property of the register, not a miscount.

    DESIGN emits more rows than it has source files because some files were copied to more
    than one destination and each destination is judged on its own. Nothing checked that:
    a reader comparing the register against the source inventory saw two different numbers
    and no reason, and a genuine accidental duplicate would have hidden inside the same
    difference. So the pair is pinned as the row key, the surplus is recomputed from the
    register's own per-path destination sets (no count is quoted in this docstring -- a
    remembered number here went stale the moment a real migration added one destination),
    no register row may invent a destination the
    copy manifest does not record, and every named destination must be a file in this tree.

    The last half of this test is the two-reading gap the 2026-10-31 sweep found: the copy
    engine walks directories while the registers use ``git ls-files``. The files that exist
    only in the walk are ones the *source repository itself* ignores -- 253 node_modules
    entries and DESIGN-LAB's ``.verify-chain-ok`` pass marker, whose content is ``ok <sha>``
    for a commit of that other repository. That marker had been copied into the tracked
    tree, where it reads as evidence for a verification chain this project never ran; it is
    now excluded by ``SOURCE_IGNORED_NAMES`` and removed, and this test holds both halves
    shut: the walk cannot re-copy it, and the manifest cannot still claim it.
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "migrate_sources_under_coverage_test", TARGET_ROOT / "scripts" / "migrate_sources.py")
    migrator = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migrator)
    assert migrator._skipped(("design-lab", "config", ".verify-chain-ok"))
    assert migrator._skipped(("apps", "workbench", "node_modules", ".bin", "playwright"))
    assert not migrator._skipped(("design-lab", "config", "task-ledger-r3.json"))

    root_text = str(TARGET_ROOT).replace("\\", "/") + "/"
    manifest_targets = {record["target"].replace("\\", "/").removeprefix(root_text)
                        for group in json.loads((TARGET_ROOT / "migration" / "copies.json")
                                                .read_text(encoding="utf-8-sig"))["copies"]
                        for record in group["records"]}
    # A destination may also be justified by the migrator's declared single-file copy table --
    # but only when the bytes are re-hashed here and agree. Recomputed independently of
    # build_source_coverage so the register cannot define "copied" for itself.
    for repo_root, src_rel, dst_rel in (list(migrator.FILE_COPIES)
                                         + list(migrator.AUTOMATION_PACKED_FILES)):
        source, destination = Path(repo_root) / src_rel, TARGET_ROOT / dst_rel
        if source.is_file() and destination.is_file() and \
           hashlib.sha256(source.read_bytes()).hexdigest() == \
           hashlib.sha256(destination.read_bytes()).hexdigest():
            manifest_targets.add(dst_rel.replace("\\", "/"))
    # 第二本台账：历史区的 MANIFEST 也是"这个去向由谁背书"的记录，逐个现算摘要而不是信它的字
    for entry in _ledger_rows():
        if entry["action"] != "COPIED" or not entry["target_rel"]:
            continue
        relative = entry["target_rel"].replace("\\", "/")
        target = TARGET_ROOT / relative
        if target.is_file() and hashlib.sha256(target.read_bytes()).hexdigest() == entry["sha256"]:
            manifest_targets.add(relative)
    for label in ("work", "design"):
        path = TARGET_ROOT / "migration" / ("source-coverage-%s.csv" % label)
        rows = list(csv.DictReader(io.StringIO(path.read_bytes().decode("utf-8-sig"),
                                               newline="")))
        pairs = [(row["path"], row["target"]) for row in rows]
        assert len(pairs) == len(set(pairs)), (
            label + "：同一个 (来源, 去向) 出现多次 —— 那才是真正的重复行")
        per_path = collections.Counter(row["path"] for row in rows)
        surplus = sum(count - 1 for count in per_path.values())
        destinations = collections.defaultdict(set)
        for row in rows:
            if row["target"]:
                destinations[row["path"]].add(row["target"])
        assert surplus == sum(len(set(targets)) - 1 for targets in destinations.values()), (
            label + "：多出来的行数不等于「一来源多去向」的扇出，说明有行不是去向而是重复")
        invented = sorted(row["target"] for row in rows
                          if row["target"] and row["target"].replace("\\", "/")
                          not in manifest_targets)
        assert invented == [], (label + "：登记了两本台账都背不了的去向：" + str(invented[:5]))
        absent = sorted({row["target"] for row in rows if row["target"]
                         and not (TARGET_ROOT / row["target"]).is_file()})
        assert absent == [], ("登记说已经落地的去向在树上不存在：" + str(absent[:5]))

    marker = (TARGET_ROOT / "domains" / "design" / "design_lab" / "resources" / "repo"
              / "design-lab" / "config" / ".verify-chain-ok")
    assert not marker.exists(), "来源仓自己忽略的通过标记不应留在候选里"
    assert not any(".verify-chain-ok" in target for target in manifest_targets), \
        "复制清单不应再记录一个已被排除的去向"



def test_the_tracked_coverage_registers_are_not_stale():
    """The published per-file registers must equal what the builder produces right now.

    Their ``authority`` column stores ``file:line`` for text searched inside this document and
    inside ``build_f01_disposition.py``. Every row that cites ``docs/CODEX-AUDIT-ENTRY.md`` points
    at one line today; a single inserted line above it would move all of those citations onto
    unrelated prose, and the existing guard -- "the cited line number is in range and the file
    exists" -- would stay green. ``--check`` closes that by comparing the rebuilt rows with the
    tracked ones, in memory, so verification is still not a writer.
    """
    check = subprocess.run([sys.executable, "-B", "-X", "utf8",
                            str(TARGET_ROOT / "scripts" / "build_source_coverage.py"), "--check"],
                           cwd=str(TARGET_ROOT), capture_output=True, text=True,
                           encoding="utf-8", errors="replace", timeout=1800)
    assert check.returncode == 0, (
        "覆盖登记比它引用的文本旧了；重跑 scripts/build_source_coverage.py 再重跑下游登记表。"
        + check.stdout[-600:] + check.stderr[-600:])


def test_the_coverage_builder_names_the_absent_source_repo_instead_of_crashing(tmp_path, capsys):
    """In a clone the two read-only source trees are simply not there; that must be a verdict.

    ``--check`` used to die inside ``subprocess`` with ``NotADirectoryError`` because the builder
    walked ``REPO_ROOT.parent/WORK-LAB`` without looking. A traceback is the worst possible answer
    for a gate: a reviewer cannot tell it apart from a broken register, and a caller that treats
    "no output" as "not run" silently loses the check. The refusal is asserted against the real
    entry point with the module's own roots redirected at an empty directory -- the same call with
    the real roots present must still do its work (the test right above proves that).
    """
    import importlib.util

    spec = importlib.util.spec_from_file_location(
        "coverage_builder_for_absent_roots",
        TARGET_ROOT / "scripts" / "build_source_coverage.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    module.WORK = tmp_path / "WORK-LAB"
    module.DESIGN = tmp_path / "DESIGN-LAB"
    before = {name: (TARGET_ROOT / "migration" / name).read_bytes()
              for name in ("source-coverage-work.csv", "source-coverage-design.csv")}
    out = tmp_path / "verdict.json"
    assert module.main(["--check", "--json-out", str(out)]) == 3, "a missing source root must not be 0"
    payload = json.loads(out.read_text(encoding="utf-8"))
    assert payload["error"] == "SOURCE_REPO_ABSENT", payload
    assert sorted(entry["label"] for entry in payload["absent"]) == ["design", "work"], payload
    assert payload["verdict"] == "NOT_RECOMPUTABLE_HERE", payload

    # one present, one absent: the verdict names only the one that is missing, and a present
    # directory that is merely not a repository is still refused (the builder enumerates a tree)
    (tmp_path / "WORK-LAB").mkdir()
    module.WORK = tmp_path / "WORK-LAB"
    assert module.main(["--check"]) == 3, "only one root present is still not enough"
    single = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert [entry["label"] for entry in single["absent"]] == ["design"], single
    # the write path is the dangerous one: in a clone it would publish "0 enumerated files" as a
    # fact about a repository the run could not read. OUT_DIR is redirected at a scratch directory
    # so the assertion can prove the refusal without being able to damage a tracked register.
    module.OUT_DIR = tmp_path / "out"
    assert module.main([]) == 3, "a refused run must refuse in write mode too"
    assert not (tmp_path / "out").exists() or not list((tmp_path / "out").glob("*.csv"))
    after = {name: (TARGET_ROOT / "migration" / name).read_bytes() for name in before}
    assert after == before, "a refused run must not rewrite a tracked register"
def test_a_file_that_only_exists_at_a_branch_tip_still_gets_a_row(tmp_path):
    """The register enumerates working trees; the ledger remembers the population. Neither may drop a file.

    A test file existed only on WORK-LAB's `feat/ledger-truth-20261027`, so the checkout that the
    import walked never showed it, and the register stayed one row short of the ledger while both
    looked complete. The generator now unions the two, and this node drives that new branch at its
    three outcomes -- matching bytes, missing target, differing bytes -- because a synthesized row
    that always reported "verified" would be worse than the row that was missing.
    """
    module = _coverage_module()
    payload = b"BYTES\n"
    digest = module.sha256_of_bytes(payload)
    (tmp_path / "history").mkdir(parents=True)
    (tmp_path / "history" / "ok.ts").write_bytes(payload)
    (tmp_path / "history" / "bad.ts").write_bytes(b"OTHER\n")
    original_root = module.REPO_ROOT
    module.REPO_ROOT = tmp_path
    try:
        row = module._ledger_only_row("work", "a/ok.ts",
                                      {"target_rel": "history/ok.ts", "sha256": digest}, {})
        assert row["path"] == "a/ok.ts" and row["repo"] == "work", row
        assert row["class"] == "COPIED_VERIFIED", row
        assert row["source_sha256"] == digest, row
        assert row["registered"] == "NO", row

        absent = module._ledger_only_row("work", "a/absent.ts",
                                         {"target_rel": "history/nope.ts", "sha256": digest}, {})
        assert absent["class"] == "COPIED_MISSING_IN_TARGET", absent

        drifted = module._ledger_only_row("work", "a/bad.ts",
                                          {"target_rel": "history/bad.ts", "sha256": digest}, {})
        assert drifted["class"] == "COPIED_MISSING_IN_TARGET", (
            "目标字节与台账摘要不同还报 COPIED_VERIFIED，这一行就是在替不存在的字节作证")

        empty = module._ledger_only_row("work", "a/ok.ts", {"target_rel": "", "sha256": digest}, {})
        assert empty["class"] == "COPIED_MISSING_IN_TARGET", (
            "台账行没有目标位置时必须报缺失，而不是拼出一个假路径")
    finally:
        module.REPO_ROOT = original_root


def test_an_archive_link_that_is_not_on_this_machine_stops_claiming_reverification(tmp_path,
                                                                                  monkeypatch):
    """只读统一归档根可能被删除：读不到对象时，登记不许继续说「已按 SHA-256 复验」。

    这一支以前把两种情况合成同一句话——「…已按 SHA-256 复验；本机根缺失时不重新宣告字节」。那句话在
    根还在时读着像复验过，在根被删掉之后**仍然**读着像复验过，于是登记表把一份已经不存在的副本说成
    第二份保险。三个方向都要走到：对象在位且摘要相同 → 证据点名本轮复验；对象不在位 → 同一行的证据
    换成「本机不存在、本轮未复验」并在汇总里计数；对象在位但摘要不符 → 仍然拒绝，不降级成警告。
    """
    module = _coverage_module()
    payload = b"# only in the unified archive\n"
    digest = module.sha256_of_bytes(payload)
    relative = "docs/history/owner-inputs/20261025/WORK-9.svg"
    entry = {"repo": "work", "path": relative, "action": "LINKED_ARCHIVE", "sha256": digest,
             "target_rel": "", "alias_of": "", "linked_location": "_资料库/" + digest + ".md",
             "reason": "容器与非文档格式按 owner 规则不入 Git"}
    root = tmp_path / "Project Archiving"
    monkeypatch.setattr(module, "UNIFIED_ARCHIVE_ROOT", root)
    # The vocabulary guard wants all four dispositions represented; this fixture is one linked row, and
    # that guard has its own falsifier (test_the_archive_disposition_guard_can_actually_fail), so stub it
    # here rather than inventing three more dispositions to satisfy an unrelated rule.
    monkeypatch.setattr(module, "archive_vocabulary_findings", lambda rows: [])
    monkeypatch.setattr(module, "archive_ledger",
                        lambda: ({("work", relative): entry}, {"LINKED_ARCHIVE": 1}))

    def documents():
        return {"work": {"rows": [{"path": relative, "source_sha256": digest}]},
                "design": {"rows": []}}

    absent = documents()
    summary = module.attach_archive_dispositions(absent, {})
    evidence = absent["work"]["rows"][0]["archive_evidence"]
    assert summary["unified_archive_objects_missing_on_this_machine"] == 1, summary
    assert summary["unified_archive_objects_byte_verified"] == 0, summary
    assert "本机不存在" in evidence and "复验一致" not in evidence, evidence
    assert absent["work"]["rows"][0]["archive_disposition"] == "ARCHIVED_ELSEWHERE_LINKED"

    (root / "_资料库").mkdir(parents=True)
    (root / "_资料库" / (digest + ".md")).write_bytes(payload)
    present = documents()
    summary = module.attach_archive_dispositions(present, {})
    assert summary["unified_archive_objects_byte_verified"] == 1, summary
    assert summary["unified_archive_objects_missing_on_this_machine"] == 0, summary
    assert "复验一致" in present["work"]["rows"][0]["archive_evidence"], present["work"]["rows"]

    (root / "_资料库" / (digest + ".md")).write_bytes(b"# somebody else's bytes\n")
    try:
        module.attach_archive_dispositions(documents(), {})
    except SystemExit as refusal:
        assert "UNIFIED_ARCHIVE_DIGEST_MISMATCH" in str(refusal), refusal
    else:
        raise AssertionError("归档对象摘要不符却没有拒绝")


def test_a_copy_record_identifies_its_repo_and_path_not_its_machine_absolute_path():
    """``migration/copies.json`` names a source by repository + path inside it, on any host.

    Measured before this node: ``copied_index()`` keyed by ``Path(source).resolve()`` and
    de-duplicated targets the same way, so the identity of a copied file was the drive layout of
    the machine that ran the copy. On any other root -- another letter, a mirrored tree, a POSIX
    clone where ``D:\\x`` resolves to a path under the current directory -- every lookup missed,
    the register republished each source as "uncopied", and the row counts still printed.
    """
    module = _coverage_module()
    # 合成根，不写这台机器的来源根拼写：克隆复现族禁止测试文件自己拼 "All projects/<仓名>"，
    # 否则环境开关到不了它们（test_v23 / test_v31 会红在这里）。被测的是纯映射，根长什么样不重要。
    roots = {"work": Path("Q:/src/WORK-LAB"), "design": Path("Q:/src/DESIGN-LAB")}
    for source, expected in (
            ("Q:\\src\\WORK-LAB\\packages\\a\\b.py", "work:packages/a/b.py"),
            ("Q:/src/DESIGN-LAB/src/design_lab/z.py", "design:src/design_lab/z.py"),
            # 大小写不同的同一个根：身份不能变
            ("q:/src/work-lab/services/a.py", "work:services/a.py"),
            # 换台的镜像根：配置的根不匹配时按仓名段落回
            ("E:/mirror/WORK-LAB/services/a.py", "work:services/a.py"),
            ("/srv/mirror/DESIGN-LAB/design-lab/config/c.json", "design:design-lab/config/c.json")):
        assert module.source_identity(source, roots) == expected, source
    assert module.source_identity("C:/somewhere/else/x.py", roots) is None
    for target, expected in (
            ("Q:\\fused\\AI-WORK-LAB\\domains\\a\\b.py", "domains/a/b.py"),
            ("/home/you/clone/AI-WORK-LAB/domains/a/b.py", "domains/a/b.py")):
        assert module.target_identity(target) == expected, target


def test_the_copy_index_resolves_one_destination_written_under_two_different_roots(tmp_path,
                                                                                    monkeypatch):
    """A manifest record and a declared copy of the same file are one record, wherever they were written.

    The old comparison resolved both destinations against this machine, so ``D:\\All projects\\…``
    and ``F:/clone/…`` were two different targets and the same source produced two index entries
    under two different keys -- which is how a clone's counts drifted from the published register.
    A source that names neither repository is reported, never silently dropped.
    """
    module = _coverage_module()
    path = tmp_path / "copies.json"
    path.write_text(json.dumps({"copies": [{"records": [
        {"source": "Q:\\src\\WORK-LAB\\packages\\a\\b.py",
         "target": "Q:\\fused\\AI-WORK-LAB\\domains\\a\\b.py",
         "sha256_source": "s", "sha256_target": "t"}]}]}, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(module, "COPIES", path)
    monkeypatch.setattr(module, "declared_file_copies", lambda: [
        {"source": "E:/mirror/WORK-LAB/packages/a/b.py",
         "target": "F:/clone/AI-WORK-LAB/domains/a/b.py",
         "sha256_source": "s2", "sha256_target": "t2", "declared_by": "test"},
        {"source": "C:/other/tree/packages/a/b.py",
         "target": "F:/clone/AI-WORK-LAB/domains/other.py",
         "sha256_source": "s3", "sha256_target": "t3", "declared_by": "test"}])
    index, unmapped = module.copied_index({"work": Path("E:/mirror/WORK-LAB"),
                                           "design": Path("E:/mirror/DESIGN-LAB")})
    assert list(index) == ["work:packages/a/b.py"], sorted(index)
    assert len(index["work:packages/a/b.py"]) == 1, index["work:packages/a/b.py"]
    assert unmapped == ["C:/other/tree/packages/a/b.py"], unmapped


def test_a_foreign_source_defect_does_not_become_this_projects_warning(tmp_path):
    """The register reads AST facts out of read-only foreign files; their Python-style noise stays there.

    Measured in the 2026-11-04 full-suite receipt: exactly ``1 warning``,
    ``<unknown>:5: SyntaxWarning: invalid escape sequence '\\ '` -- the coverage builder parsing a
    WORK-LAB file whose docstring carries an unescaped Windows path. Two responses were wrong:
    editing that file (the source repositories are read-only here, and its bytes are archived under
    ``docs/history/``), or leaving the noise in every receipt so nobody can tell "0 warnings" from
    "one warning nobody explained". So the suppression is scoped to the one parse, and SyntaxError
    still has to mean "no facts".
    """
    import warnings

    module = _coverage_module()
    repo = tmp_path / "source"
    (repo / "scripts").mkdir(parents=True)
    (repo / "scripts" / "escaped.py").write_text(
        '"""A docstring with a Windows path: C:\\ Program Files\\ x."""\n'
        'if __name__ == "__main__":\n    print("hi")\n', encoding="utf-8")
    with warnings.catch_warnings():
        warnings.simplefilter("error", SyntaxWarning)
        has_main, names = module._module_facts(repo, "scripts/escaped.py")
    assert has_main is True, "the parse did not happen at all, so the suppression hides a real failure"
    assert "print" not in names

    (repo / "scripts" / "broken.py").write_text("def oops(:\n", encoding="utf-8")
    assert module._module_facts(repo, "scripts/broken.py") == (False, []), (
        "a file that cannot be parsed must still report no facts -- the widened filter may silence "
        "noise, not swallow real errors")


def test_a_tracked_byte_the_hazard_gate_cannot_open_blocks_instead_of_passing(tmp_path, capsys,
                                                                              monkeypatch):
    """A printed denominator has to mean "I read this many", not "the index lists this many".

    The scanner printed ``scanned_files = len(tracked_files())`` while an unreadable file fell through
    ``except OSError: continue`` -- so a hazard sitting in a byte the gate could not open would have
    been reported as covered, and the run would still look like ``7311 files, 0 blocking``. The same
    shape was caught in the population tool from the other side: one frozen input lives at a
    260-character path, so a plain read raised ``FileNotFoundError`` and the scan silently covered
    7310 of 7311 files.
    """
    import importlib.util
    import json
    import subprocess

    spec = importlib.util.spec_from_file_location(
        "hazards_scan_coverage", TARGET_ROOT / "scripts" / "check_public_hazards.py")
    haz = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(haz)

    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "clean.md").write_text("no secrets here\n", encoding="utf-8")
    # assembled, never written whole: the repo's own bytes must not carry a full key shape, which is
    # why the AWS-prefix node above keeps prefix and body in separate literals
    key_shape = "AKIA" + "ABCDEFGHIJKLMNOP"
    (tmp_path / "hidden.md").write_text(key_shape + "\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    (tmp_path / "hidden.md").unlink()
    monkeypatch.setattr(haz, "ROOT", tmp_path)
    monkeypatch.setattr(haz, "LEDGER", tmp_path / "config" / "secret-scan-adjudications.json")

    rc = haz.main([])
    document = json.loads(capsys.readouterr().out.splitlines()[0])
    assert document["scanned_files"] == 2 and document["files_read"] == 1, document
    assert document["files_unreadable"] == 1 and document["unreadable_paths"] == ["hidden.md"], (
        "an unopenable tracked byte was dropped from the scan while the printed count kept claiming "
        "the whole index: %s" % document)
    assert rc == 1, "a scan that did not cover the tree may not exit 0"

    # positive control: the same tree, same bytes, readable again -- the refusal came from the hole
    (tmp_path / "hidden.md").write_text(key_shape + "\n", encoding="utf-8")
    rc = haz.main([])
    document = json.loads(capsys.readouterr().out.splitlines()[0])
    assert rc == 0 and document["files_read"] == 2 and document["files_unreadable"] == 0, document




def test_the_coverage_check_report_names_the_rows_it_found_different():
    """``rows_changed: {"work": 1579}`` refused without saying what differed -- so it now says.

    Measured the hard way this batch: a clone of the same commit answered rc=1 with counts only,
    and the next three questions were all guesses about which column carried the difference.
    ``_drift`` already returns strings of the shape ``<path>: class,reason``, so publishing a
    bounded sample is free and turns the refusal into something a reader can act on. The report is
    built by a function rather than inline for the same reason: producing ``drift`` costs minutes
    of source-tree hashing, and a guard for the answer should not have to pay that to exist.
    """
    import build_source_coverage as coverage

    drifted = {"work": ["a.py: class,authority", "b.py: reason"], "design": []}
    report = coverage.check_report(drifted, ["design"], ["c.py"])
    assert report["drifted"] == ["work"], report
    assert report["rows_changed"] == {"work": 2, "design": 0}, report
    assert report["drift_sample"] == {"work": ["a.py: class,authority", "b.py: reason"]}, report
    assert report["unreconciled"] == ["design"], report
    assert report["copy_identity_unmapped"] == 1, report

    clean = coverage.check_report({"work": [], "design": []}, [], [])
    assert clean["drifted"] == [] and clean["drift_sample"] == {}, clean

    # a sample longer than the bound is still a bounded sample: the report must not become a
    # multi-megabyte stdout on the day a real drift spans thousands of rows
    many = coverage.check_report({"work": ["row%d: class" % i for i in range(1579)]}, [], [])
    assert len(many["drift_sample"]["work"]) == 5 and many["rows_changed"]["work"] == 1579, many


def test_a_destination_is_published_inside_the_repository_not_on_a_machine():
    r"""A clone of this commit used to publish ``D:\All projects\AI-WORK-LAB\…`` in ``target``.

    The value came from ``migration/copies.json``, which records the absolute path the copy was
    written to, and the generator cut the prefix off against *the checkout that was running*: in
    the machine that ran the migration the prefix matched, in a clone it did not, and the fallback
    published the whole machine path -- while the digest was computed by opening the main
    checkout's file. Measured: 188 work rows and 2,144 design rows differed, plus the ordering
    shift those absolute keys caused.
    """
    import build_source_coverage as coverage

    # the same fact on any host: the anchor is the repository's own name inside the path
    assert coverage.published_target(
        "D:/All projects/AI-WORK-LAB/domains/work/x.py") == "domains/work/x.py"
    assert coverage.published_target(
        "E:/mirror/AI-WORK-LAB/domains/work/x.py") == "domains/work/x.py"
    assert coverage.published_target("domains/work/x.py") == "domains/work/x.py"

    # A destination inside the read-only source repo is not inside any checkout of *this* repo, so
    # it must be refused by name -- and it is spelled through scripts/source_roots.py, because a
    # second literal spelling of an outside root is precisely what test_v23's single-spelling guard
    # exists to refuse. Hand-writing it here would have made this node the thing it tests against.
    from source_roots import resolve as _resolve_root
    source_repo_destination = str(_resolve_root("work")).replace("\\", "/") + "/x.py"
    for unrelated in ("C:/Users/other/elsewhere/x.py", source_repo_destination):
        try:
            coverage.published_target(unrelated)
        except SystemExit as refusal:
            assert "DESTINATION_NOT_INSIDE_ANY_CHECKOUT" in str(refusal), refusal
        else:
            raise AssertionError("一个不属于任何本仓检出的目的地被静默发布了：%s" % unrelated)

    clean = {"work": {"rows": [{"path": "a", "target": "domains/work/x.py",
                                "archive_target": "domains/work/x.py"}]}}
    assert coverage.machine_path_findings(clean) == [], coverage.machine_path_findings(clean)
    dirty = json.loads(json.dumps(clean))
    dirty["work"]["rows"][0]["target"] = "D:/All projects/AI-WORK-LAB/domains/work/x.py"
    findings = coverage.machine_path_findings(dirty)
    assert len(findings) == 1 and "|a:target=" in findings[0], findings


def test_a_destination_under_the_running_checkout_is_measured_from_that_checkout(tmp_path, monkeypatch):
    """The first verification clone of the portable-anchor fix was itself mis-anchored.

    ``declared_file_copies()`` builds destinations as ``REPO_ROOT / dst_rel``, so in a clone the
    value already is a path inside *that* checkout. Cutting only at the repository-name segment --
    which appears once there, at the outside -- left the run directory inside the cell:
    ``.project-local/clonerepro-…/c/domains/x.py``, and 31 work rows changed class because the
    register no longer believed its own destination existed. Measured from the row samples, not
    inferred: this is what the clone's ``--check`` printed before the rule was fixed.
    """
    import build_source_coverage as coverage

    nested = tmp_path / ".project-local" / "clonerepro-1" / "c"
    nested.mkdir(parents=True)
    monkeypatch.setattr(coverage, "REPO_ROOT", nested.resolve())
    assert coverage.published_target(str(nested / "domains" / "work" / "x.py")) \
        == "domains/work/x.py"
    # the identity key must agree with the published cell or the index misses its own rows
    assert coverage.target_identity(str(nested / "domains" / "work" / "x.py")) == "domains/work/x.py"

    # and rule two still carries a path written on a machine nobody is sitting at
    assert coverage.published_target("F:/clone/AI-WORK-LAB/domains/work/x.py") == "domains/work/x.py"
    from source_roots import resolve as _resolve_root
    source_repo_destination = str(_resolve_root("work")).replace("\\", "/") + "/x.py"
    for unrelated in (source_repo_destination, "C:/somewhere/else/x.py"):
        try:
            coverage.published_target(unrelated)
        except SystemExit as refusal:
            assert "DESTINATION_NOT_INSIDE_ANY_CHECKOUT" in str(refusal), refusal
        else:
            raise AssertionError("机器上别处的绝对路径被当成仓内去向发布了：%s" % unrelated)
