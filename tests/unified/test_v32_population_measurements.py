"""Guards for ``scripts/measure_citation_population.py`` -- the tool two entry numbers came from.

This project has now published two wrong figures of exactly this kind: a "322 tracked files carry the
machine account name" that also counted the public repo owner ``DTALEX66`` (same letters), and a
"621 prose ``.py:line`` cites" produced by a script that quietly skipped ``docs/history/`` -- 860 of
the real 1482 cites, silently, which is a truncated listing read as an absence. So the tool is
tracked, and these nodes are what keep it honest: the ownership rule is checked at prefix boundaries
(a copied tree must not claim ``domains/design_lab``, and ``AGENTS.md`` is not a copy of anything), the
account pattern must not fire on the repo-owner token, a missing ledger or an undeterminable account
name must abort rather than return a reassuring zero, and the bucket sums must equal the totals the
entry quotes.
"""
from __future__ import annotations

import importlib.util
import json
import pathlib
import re
import sys

import pytest

TARGET_ROOT = pathlib.Path(__file__).resolve().parents[2]
SCRIPT = TARGET_ROOT / "scripts" / "measure_citation_population.py"


def _machine_path(account):
    """A home path for a synthetic account, spelled at run time.

    Writing the finished string into this file would put a machine path in tracked bytes -- the very
    population the tool measures and the guard below refuses to find outside one register.
    """
    return "C:\\Users\\%s\\work" % account


@pytest.fixture(scope="module")
def module():
    spec = importlib.util.spec_from_file_location("measure_citation_population_live", SCRIPT)
    document = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = document
    spec.loader.exec_module(document)
    return document


def test_ownership_is_decided_at_prefix_boundaries_not_by_a_suffix(module):
    """The rule that made ``AGENTS.md`` look like a migrated copy, fixed and then pinned."""
    claimed = {"domains/design", "domains/design/design_lab/runtime/paths.py"}
    assert module.owner_of("domains/design/thing.py", claimed) == "migrated_copy"
    assert module.owner_of("domains/design/design_lab/runtime/paths.py", claimed) == "migrated_copy"
    # a sibling whose name merely starts with the same letters is NOT inside the copied tree
    assert module.owner_of("domains/design_lab/other.py", claimed) != "migrated_copy", (
        "prefix matching without a boundary swallowed a sibling tree -- the same defect that would"
        " have made a source-record count look smaller than it is")
    # and a root file ending in the same text as a ledger entry is not that entry
    assert module.owner_of("AGENTS.md", claimed | {"design-lab/AGENTS.md"}) != "migrated_copy", (
        "an endswith-style match claimed this repo's own root instruction file as a source copy")
    assert module.owner_of("backend/v1.py", set()) == "own_code_and_checks"
    assert module.owner_of("migration/copies.json", set()) == "generated_register"
    assert module.owner_of("docs/CODEX-AUDIT-ENTRY.md", set()) == "append_only_history"
    assert module.owner_of("docs/authority-202610/anything.md", set()) == "frozen_source_input"


def test_the_repo_owner_token_is_not_an_account_mention(module, tmp_path):
    """``DTALEX66`` contains the account letters; counting it is what inflated 218 into 322."""
    (tmp_path / "owner.md").write_text("cloned from DTALEX66/AI-WORK-LAB\n", encoding="utf-8")
    (tmp_path / "paths.md").write_text(_machine_path("alex") + "\n", encoding="utf-8")
    (tmp_path / "bare.md").write_text("user alex signed off here\n", encoding="utf-8")
    document = module.measure(root=tmp_path, account="alex", claimed=set(),
                              files=["owner.md", "paths.md", "bare.md"])
    buckets = document["by_ownership"]
    total = {field: sum(buckets[key][field] for key in buckets)
             for field in ("account_mentions", "absolute_machine_paths")}
    assert total["account_mentions"] == 2, (
        "the repo-owner token was counted as an account mention again: %s" % buckets)
    assert total["absolute_machine_paths"] == 1, buckets
    assert document["totals"]["files"] == 2, buckets


def test_a_different_person_named_alex_is_not_this_machines_account(module, tmp_path):
    """The two machine-name counters are asymmetric on purpose, and that asymmetry is what this pins.

    ``account_mentions`` is case-sensitive -- the account's own spelling is what shows up in a leaked path
    or a quoted user name. The tracked tree contains frozen archive objects naming "Alex Atallah" and
    "Alex Garcia"; a case-insensitive token would add them to the population, which is the 218-into-322
    mistake running backwards. A lowercase *path* is still the same leak though, so
    ``absolute_machine_paths`` keys on the drive shape case-insensitively -- a person's name cannot
    produce ``C:/users/...``.
    """
    (tmp_path / "person.md").write_text("Zzq Atallah and Zzq Garcia were both quoted\n",
                                        encoding="utf-8")
    (tmp_path / "path.md").write_text("cache = D:/work/zzq/models/snap.safetensors\n",
                                      encoding="utf-8")
    (tmp_path / "url.md").write_text("remote https://github.com/DTALEX66/AI-WORK-LAB.git\n",
                                     encoding="utf-8")
    document = module.measure(root=tmp_path, account="ZZQ", claimed=set(),
                              files=["person.md", "path.md", "url.md"])
    buckets = document["by_ownership"]
    total = {field: sum(buckets[key][field] for key in buckets)
             for field in ("account_mentions", "absolute_machine_paths")}
    assert total["account_mentions"] == 0, (
        "另一个人的名字被算成本机账号名，人群又会虚涨：%s" % buckets)
    assert total["absolute_machine_paths"] == 1, (
        "小写拼法的真实路径漏掉了，或公开仓库主名的 URL 被当成机器路径：%s" % buckets)


def test_a_home_path_may_end_at_the_account_directory_but_a_url_may_not_start_one(module, tmp_path):
    """Three bounds of one rule, each found by measuring the population rather than guessing at it.

    ``C:\\Users\\alex`` -- a home path that stops at the account directory -- was invisible: the drive
    branch demanded a separator *after* the name. Five frozen inputs write that shape. A sixth writes the
    home fragment a table cell uses -- ``（Users/<account>/AppData/…）``, no drive in front, no leading
    slash -- and carries no standalone account token either, so that one sat outside **both** counters at
    once; admitting it costs one file for one file on this tree, which is why it was measured first.
    The other bound is the no-whitespace span: measured over this tree, letting the rule cross whitespace
    to reach the name counts three files that are not paths (``https://app.notion.com/…-DT alex/tag`` and
    two archive objects), and dropping the trailing separator as well takes it to fourteen -- ``s:`` from
    ``https:`` is a perfectly plausible drive letter. Over-counting a leak is recoverable; counting other
    people's names as this machine is the mistake that turned 218 into 322.
    """
    (tmp_path / "ends-here.md").write_text("home = C:\\Users\\zzq\n", encoding="utf-8")
    (tmp_path / "url.md").write_text("read s://app.notion.com-DT zzq/tag, and OpenZZQ too\n",
                                     encoding="utf-8")
    (tmp_path / "fragment.md").write_text("| 镜像 | （Users/zzq/AppData/Temp/a0） |\n", encoding="utf-8")
    (tmp_path / "prose.md").write_text("GitHub users/zzq 这种写法不是目录\n", encoding="utf-8")

    def totals(*names):
        document = module.measure(root=tmp_path, account="zzq", claimed=set(), files=list(names))
        return document["totals"]

    ends = totals("ends-here.md")
    assert ends["absolute_machine_paths"] == 1, (
        "以账号目录收尾的主目录没算进机器路径——盘符分支要求名字后面还有一个分隔符，那一格于是整体漏计：%s"
        % ends)
    assert ends["account_mentions"] == 1, ends
    url = totals("url.md")
    assert url["absolute_machine_paths"] == 0, (
        "URL 里的 s: 被当成盘符：含空白的那段文本不是路径，盘符前缀后面必须紧跟 users/home 才算目录：%s"
        % url)
    assert url["account_mentions"] == 1, (
        "独立 token 的口径变了，账号名人群就不是原来那一个：%s" % url)
    fragment = totals("fragment.md")
    assert fragment["absolute_machine_paths"] == 1, (
        "没有盘符、前面只有一个全角括号的 home 片段没被计入——那是现数里最后一个漏计的形状：%s" % fragment)
    assert fragment["account_mentions"] == 0, (
        "片段里账号名前是斜杠，不该同时算成独立 token，人群会重复计数：%s" % fragment)
    prose = totals("prose.md")
    assert prose["absolute_machine_paths"] == 0, (
        "`users/zzq` 后面没有分隔符就不是目录，散文里的仓库路径不该进机器路径人群：%s" % prose)
    all_four = totals("ends-here.md", "url.md", "fragment.md", "prose.md")
    assert (all_four["files_with_absolute_paths"], all_four["files_with_account_mentions"]) == (2, 2), (
        "四个形状的文件级计数不是一路径、一提及各两个：%s" % all_four)


def test_a_missing_ledger_aborts_instead_of_narrowing_the_scan(module, tmp_path, monkeypatch):
    """Zero looks like a clean bill of health; here an unreadable ledger must be a refusal."""
    with pytest.raises(SystemExit) as abort:
        module.measure(root=tmp_path, account="", claimed=set(), files=["x.py"])
    assert "MEASUREMENT_PREREQ_MISSING" in str(abort.value)

    missing = tmp_path / "nope"
    missing.mkdir()
    monkeypatch.setattr(module, "COPIES", missing / "copies.json")
    with pytest.raises(SystemExit) as abort:
        module.ledger_targets()
    assert "MEASUREMENT_LEDGER_ABSENT" in str(abort.value)

    (missing / "migration").mkdir()
    (missing / "migration" / "copies.json").write_text('{"copies": []}', encoding="utf-8")
    monkeypatch.setattr(module, "COPIES", missing / "migration" / "copies.json")
    monkeypatch.setattr(module, "MANIFEST", missing / "MANIFEST.csv")
    with pytest.raises(SystemExit) as abort:
        module.ledger_targets()
    assert "MEASUREMENT_LEDGER_ABSENT" in str(abort.value), (
        "the history MANIFEST is the second ownership source; dropping it silently would reclassify"
        " source records as our own prose and make a rewrite look authorised")

    # a ledger of the wrong shape is refused too -- a key typo is how claimed came back empty once
    (missing / "migration" / "copies.json").write_text('{"generated_at": "x"}', encoding="utf-8")
    monkeypatch.setattr(module, "MANIFEST", TARGET_ROOT / "docs" / "history" / "sources-20261101"
                        / "MANIFEST.csv")
    with pytest.raises(SystemExit) as abort:
        module.ledger_targets()
    assert "MEASUREMENT_LEDGER_SHAPE" in str(abort.value)


def test_the_tool_scans_every_tracked_byte_or_names_the_ones_it_missed(module):
    """A denominator that counts files the reader never opened would shrink the population quietly.

    One frozen input sits at a 260-character path (``docs/history/sources-20261101/design/docs/audits/
    DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/session/hermes-legacy/runtime/reconstruction/
    c4-4768-.../source-swap.svg``); a plain Windows read reports that as ``FileNotFoundError``, so the
    first version of this tool scanned 7310 of 7311 tracked files and said nothing about it. The
    hazard gate already reads through the long-form prefix; the measurement has to cover the same tree.
    """
    tracked = module.tracked_files()
    document = module.measure()
    assert document["files_tracked"] == len(tracked), (
        "the scan list and the index disagree: %s vs %s"
        % (document["files_tracked"], len(tracked)))
    assert document["files_unreadable"] == 0, (
        "tracked bytes the reader could not open are outside both populations: %s"
        % document["unreadable_paths"])
    assert document["files_scanned"] == len(tracked), (
        "files_scanned dropped below the index while the published totals kept quoting the whole tree")


def test_a_tracked_byte_the_disk_refuses_to_open_is_named_not_dropped(module, tmp_path):
    """A file that cannot be read is not a file with zero cites.

    The first version of the tool ended its read in ``except OSError: continue``, which is how a tree of
    7311 tracked files was measured as 7310 scanned -- one frozen input sits at a 260-character path, so
    a plain Windows read calls it ``FileNotFoundError``. The count moved by nothing here (that file has
    no cites), but the denominator lied, and a *hit* living in such a file would have vanished.
    """
    import subprocess
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True, capture_output=True)
    (tmp_path / "keep.md").write_text("nothing to see\n", encoding="utf-8")
    (tmp_path / "gone.md").write_text(_machine_path("alex") + "\\secret.md\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", "-A"], check=True, capture_output=True)
    (tmp_path / "gone.md").unlink()
    listed = subprocess.run(["git", "-C", str(tmp_path), "ls-files", "-z"],
                            capture_output=True, check=True).stdout
    files = [row.decode("utf-8", "replace") for row in listed.split(b"\0") if row]
    document = module.measure(root=tmp_path, account="alex", claimed=set(), files=files)
    assert document["files_tracked"] == 2 and document["files_scanned"] == 1, document
    assert document["files_unreadable"] == 1 and document["unreadable_paths"] == ["gone.md"], (
        "an unopenable tracked byte must be named in the receipt, not absorbed into a smaller scan: %s"
        % document)
    assert document["totals"]["absolute_machine_paths"] == 0, (
        "the unreadable byte is excluded from the population -- which is exactly why it has to be"
        " printed instead of hidden")


def test_the_published_totals_recompute_and_the_buckets_account_for_every_file(module):
    """The number quoted in the entry must be reproducible from the tool, and internally closed."""
    first = module.measure()
    second = module.measure()
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True), (
        "the measurement is not deterministic, so no register may quote it")
    sums = {field: sum(bucket[field] for bucket in first["by_ownership"].values())
            for field in ("files", "line_cites", "account_mentions", "absolute_machine_paths",
                          "files_with_line_cites", "files_with_account_mentions",
                          "files_with_absolute_paths", "files_with_account_mention_and_path")}
    assert sums == first["totals"], "bucketed counts do not add up to the published totals"
    assert first["files_scanned"] > 7000, first["files_scanned"]
    # the whole tree, with docs/history included -- the earlier instrument lost 860 cites that way
    assert first["by_ownership"]["frozen_source_input"]["line_cites"] > 800, (
        "docs/history/ stopped being counted; the entry's cite population just shrank by ~860"
        " without anyone saying so")
    # samples are capped per bucket, so inclusion is asserted by count and by the rule itself,
    # not by hoping a history path survives the cap
    assert module.owner_of("docs/history/sources-20261101/MANIFEST.csv", set()) == (
        "frozen_source_input")
    assert first["by_ownership"]["own_code_and_checks"]["line_cites"] > 0, (
        "the subset a guard may widen into is empty -- check the ownership prefixes")


def test_per_shape_file_counts_keep_the_two_denominators_apart(module, tmp_path):
    """Every shape needs its own file counter, or a published file count cannot be re-run.

    §15.45 said 218 tracked files carry the account name and 168 of those also carry a whole machine path.
    Neither figure came out of the tracked tool: ``totals.files`` counts a file once for *any* shape, so
    the pair came from a scratch script run over a mention-only population. A reader who instead took
    "files with a path" from the whole tree gets 389 today -- a different denominator wearing the same
    sentence. Both figures are now produced by this tool, intersection included.
    """
    (tmp_path / "mention.md").write_text("user zzq signed off, see scripts/x.py:12\n",
                                         encoding="utf-8")
    (tmp_path / "path.md").write_text("cache = /home/zzq/models/snap.safetensors\n", encoding="utf-8")
    (tmp_path / "both.md").write_text(_machine_path("zzq") + "\n", encoding="utf-8")
    (tmp_path / "quiet.md").write_text("nothing here\n", encoding="utf-8")
    document = module.measure(root=tmp_path, account="zzq", claimed=set(),
                              files=["mention.md", "path.md", "both.md", "quiet.md"])
    totals = document["totals"]
    assert totals["files_with_account_mentions"] == 2, totals
    assert totals["files_with_absolute_paths"] == 2, totals
    assert totals["files_with_account_mention_and_path"] == 1, (
        "交集就是 168 那一格的定义，写成\"任一形态\"会把冻结来源的故事用一个更大的数重讲一遍：%s"
        % totals)
    assert totals["files_with_line_cites"] == 1, totals
    assert totals["files"] == 3, "一个没有任何命中的文件进了人群：%s" % totals

    real = module.measure()
    fields = ("files_with_line_cites", "files_with_account_mentions",
              "files_with_absolute_paths", "files_with_account_mention_and_path")
    assert {field: sum(bucket[field] for bucket in real["by_ownership"].values())
            for field in fields} == {field: real["totals"][field] for field in fields}, (
        "逐形态文件数与桶不自洽")
    assert real["totals"]["files_with_account_mentions"] > 100, real["totals"]
    assert real["totals"]["files_with_account_mention_and_path"] > 100, (
        "交集计数根本没被加上，面一收窄这条必须红：%s" % real["totals"])
    assert real["totals"]["files_with_account_mention_and_path"] <= min(
        real["totals"]["files_with_account_mentions"],
        real["totals"]["files_with_absolute_paths"]), "交集大于它的任一侧，计数写错了"


def test_the_root_build_config_is_inside_the_checked_cite_face(module, tmp_path):
    """A cite written outside the four source prefixes used to age in silence; pyproject has seven.

    ``pyproject.toml`` explains why the install tree mirrors the repository root and names seven
    locations to do it. The checked face was ``scripts/ tests/ backend/ domains/work/``, so those seven
    were verified by hand once and by nothing since. Root-level markdown is in the same face now.
    """
    (tmp_path / "tiny.py").write_text("def a():\n    return 1\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("# the reason lives in tiny.py:99\n", encoding="utf-8")
    report = module.own_cite_liveness(root=tmp_path, files=["tiny.py", "pyproject.toml"])
    assert [row["cite"] for row in report["broken"]] == ["tiny.py:99"], (
        "根级构建配置里的引用没进检查面：面一旦收窄，这条必须红，而不是安静地少测一条：%s"
        % report["broken"])
    assert report["summary"]["cites"] == 1, report["summary"]
    assert report["by_shape"] == {"anchor": 0, "line": 1, "symbol": 0}, report["by_shape"]

    real = module.own_cite_liveness()
    rows = {row["file"]: row for row in real["by_file"]}
    assert "pyproject.toml" in rows, "本仓的构建配置不在逐件清单里：%s" % sorted(rows)[:8]
    assert rows["pyproject.toml"]["broken"] == 0, rows["pyproject.toml"]
    assert sum(real["by_shape"].values()) == real["summary"]["cites"], (
        "形态分列与总条数不一致，说明有一类引用没被分类：%s vs %s"
        % (real["by_shape"], real["summary"]["cites"]))


#: Cites that resolve to a tracked file but name a location inside it that is deliberately false: the
#: node asserts the *refusal*, so that pointer must stay broken. Keyed by (citing file, target file,
#: tail) instead of by the whole cite, because writing the whole cite here would put a fresh
#: file-number pointer into the very population this node scans -- the guard would fail on its own
#: exemption list. Each entry carries its reason, and a dead entry fails: an exemption nobody needs
#: would cover the next real breakage.
#:
#: Cites whose path is not in the tracked tree at all are NOT listed here. Those are syntax examples and
#: sandbox fixtures (a generic ``test_method`` in a docstring, a builder file the test creates inside a
#: tmp_path, a receipt path under ``.project-local``); there is no byte of ours for them to have drifted
#: away from, and forcing a per-row exemption for each would turn the guard into a list someone deletes
#: to get green -- the exact failure this project has already had once.
SYNTHETIC_LOCATIONS = {
    ("tests/unified/test_v16_traceability.py", "backend/v1.py", "999999"):
        "故意越界的行号，节点断言的正是它被拒",
    ("tests/unified/test_v16_traceability.py", "tests/unified/test_v02_surface.py",
     "test_no_such_test_anywhere"):
        "伪造的测试名，验证证据读回会拒绝它",
    ("tests/unified/test_v16_traceability.py", "scripts/migrate_sources.py", "prune_reportX"):
        "沙箱里另造的符号名，用来断言同名歧义时不认锚点",
    ("tests/unified/test_v25_audit_item_closure.py", "tests/unified/test_v25_audit_item_closure.py",
     "test_this_name_does_not_exist"):
        "自闭环审计的伪造节点名，断言的是它读不回来",
    ("scripts/build_task_acceptance_register.py", "tests/conftest.py", "build_server"):
        "登记注里明说这是当初写错的出处（真正的定义在 backend/app.py 的 build_server），"
        "留着是说明改正过程，不是让读者去那里找实现",
}

#: Custody classes whose bytes this repo may not rewrite: owner-delivered inputs, byte-for-byte migrated
#: copies claimed by ``migration/copies.json`` by digest, and the append-only audit history. A dead cite
#: found inside them is a declaration problem (DECLARED_REWORK + ledger re-capture), never an excuse to
#: edit the copy -- which is exactly the mistake this batch had to revert.
UNEDITABLE_CUSTODY = frozenset({"frozen_source_input", "migrated_copy", "append_only_history"})
#: dead cites that currently live in those frozen bytes, named so nothing edits them. Empty by measurement:
#: the only frozen-copy cite in the tree points at a script that is not tracked here at all, so the
#: liveness rule never evaluates it.
FROZEN_DEAD_CITES: set[tuple[str, str]] = set()

CITE_IN_TEXT = re.compile(r"(?P<cite>[\w./-]+\.py(?:::[A-Za-z_]\w*|:\d+(?:-\d+)?|#[^\s,;)\]\"`]+))")
#: identity keys of the migration map name a file in the SOURCE repository's layout. They are a row's id,
#: not a claim about where our implementation lives, so the liveness rule must not be pointed at them.
FOREIGN_SOURCE_PREFIXES = ("src/design_lab/", "src/work/", "design-lab/", "work-lab/")
DEF_NAME = re.compile(r"^\s*(?:def|class)\s+(?P<name>[A-Za-z_]\w*)")
BIND_NAME = re.compile(r"^\s*(?P<name>[A-Za-z_]\w*)\s*[:=]")


def _line_count(path):
    try:
        return len(path.read_text(encoding="utf-8", errors="replace").splitlines())
    except (OSError, UnicodeDecodeError):
        return 0


def _defines_exactly_once(path, name):
    hits = 0
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, UnicodeDecodeError):
        return False
    for text in lines:
        match = DEF_NAME.match(text) or BIND_NAME.match(text)
        if match and match.group("name") == name:
            hits += 1
    return hits == 1


def _split_cite(cite):
    """``path``, kind and the tail -- the three shapes a prose cite can take."""
    if "::" in cite:
        head, _sep, name = cite.partition("::")
        return head, "symbol", name
    match = re.match(r"^(?P<path>[\w./-]+\.py):(?P<start>\d+)(?:-(?P<end>\d+))?$", cite)
    if match:
        return (match.group("path"), "line",
                (int(match.group("start")), int(match.group("end") or match.group("start"))))
    head, _sep, anchor = cite.partition("#")
    return head, "anchor", anchor


def _candidate_ok(root, rel, kind, tail):
    path = root / rel
    if kind == "symbol":
        return _defines_exactly_once(path, tail)
    if kind == "line":
        start, end = tail
        count = _line_count(path)
        return 0 < start <= count and end <= count
    if tail.isdigit():
        return int(tail) <= _line_count(path)
    return _defines_exactly_once(path, tail)


def _cite_is_live(root, cite, candidates):
    """Does this citation still point at content that exists -- checked against the file it resolves to."""
    _head, kind, tail = _split_cite(cite)
    return any(_candidate_ok(root, cand, kind, tail) for cand in candidates)


def _ledger_key(rel, cite):
    """The shape the exemption ledger is keyed by: citing file, target file, tail -- never the whole
    cite, because writing a whole cite inside this file would add it to the population under test."""
    head, kind, tail = _split_cite(cite)
    if kind == "line":
        tail_key = "%d-%d" % tail if tail[0] != tail[1] else str(tail[0])
    else:
        tail_key = str(tail)
    return (rel, head, tail_key)


def test_own_code_line_cites_point_at_bytes_that_are_still_there(module):
    """Every number written into our own prose has to still exist in the file it names.

    The own-prose population -- our code, our checks, and the root-level documents -- is dense evidence
    commentary: a cite spanning
    dozens of lines in ``canonical_store`` names a *region*, so swapping each cite for the enclosing
    symbol would lose which part of the function the sentence is about. What cannot be allowed is
    silence -- a cite whose line has scrolled past the end of its file reads exactly like a live one.
    This node enumerates the tracked tree itself (never a hand-listed file set) and accepts a basename
    that is ambiguous -- most of these name two tracked files, ours and a frozen source copy -- as long
    as *some* candidate still has that line, because demanding a unique answer today would flag the
    whole population instead of the rot.
    """
    files = [row for row in module.tracked_files()
             if row.startswith(("scripts/", "tests/", "backend/", "domains/work/"))
             or ("/" not in row and row.endswith((".md", ".toml")))]
    assert len(files) > 100, "the own-code population collapsed: %d files" % len(files)

    by_name: dict[str, list[str]] = {}
    for rel in module.tracked_files():
        by_name.setdefault(pathlib.PurePosixPath(rel).name, []).append(rel)

    seen, broken, exempt_hits, frozen = set(), [], set(), []
    for rel in files:
        try:
            text = (TARGET_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for cite in CITE_IN_TEXT.findall(line):
                seen.add((rel, cite))
                head, kind, tail = _split_cite(cite)
                if _ledger_key(rel, cite) in SYNTHETIC_LOCATIONS:
                    exempt_hits.add(_ledger_key(rel, cite))
                    continue
                if (TARGET_ROOT / head).is_file():
                    candidates = [head]
                else:
                    candidates = by_name.get(pathlib.PurePosixPath(head).name, [])
                if not candidates:
                    # an example or a sandbox fixture: no tracked byte of ours to have drifted away
                    continue
                if not _cite_is_live(TARGET_ROOT, cite, candidates):
                    # a migration-map identity key names a file in the SOURCE repository's layout; it is
                    # a row's id, not a claim about where our code lives
                    if "source_key" in line and cite.startswith(FOREIGN_SOURCE_PREFIXES):
                        continue
                    where = "%s:%d %s -> 候选文件里已经没有这个位置" % (rel, number, cite)
                    if module.owner_of(rel, module.ledger_targets()) in UNEDITABLE_CUSTODY:
                        frozen.append((rel, cite, where))
                    else:
                        broken.append(where)

    # a dead cite inside bytes we may not rewrite is not a task to rewrite them: that is how a green
    # test ends up buying itself a DECLARED_REWORK violation. It is named here instead, and the list is
    # empty because the one such cite in the tree points outside the tracked tree and is never checked.
    unexpected_frozen = [row for row in frozen if (row[0], row[1]) not in FROZEN_DEAD_CITES]
    assert not unexpected_frozen, (
        "冻结字节里出现新的坏引用，只能走具名返工声明 + 台账补采，不能改写复制件：%s"
        % [row[2] for row in unexpected_frozen[:6]])
    dead_frozen = sorted(key for key in FROZEN_DEAD_CITES
                         if key not in {(row[0], row[1]) for row in frozen})
    assert not dead_frozen, "冻结件的坏引用登记已不再成立：%s" % dead_frozen

    dead = sorted(key for key in SYNTHETIC_LOCATIONS if key not in exempt_hits)
    assert not dead, "具名豁免已不再被引用，留着会掩护下一个真损坏：%s" % dead
    assert not broken, "本仓散文里的引用不再指向存在的内容：\n" + "\n".join(broken[:12])


#: Register cells whose published anchor is deliberately not a live location. Keyed the same way as
#: SYNTHETIC_LOCATIONS -- (register, target file, tail) -- so naming the exception here does not add a
#: fresh cite to the very population the prose guard scans.
REGISTER_ANCHOR_EXEMPTIONS = {
    ("migration/task-acceptance.csv", "tests/conftest.py", "build_server"):
        "这一格引用的是登记当初写错的出处（真正的定义在 backend/app.py 的 build_server），"
        "注里已明说它是调用点引用而非实现位置；改掉字节等于抹掉改正记录",
}


def test_published_register_anchors_point_at_content_that_is_still_there(module):
    """Every cite a register *publishes* is checked against the tree, not just the ones in our prose.

    The location and evidence columns carry anchors for non-Python targets too --
    ``apps/workbench/shell.ts:346``, a handoff ``12_来源基线.json:6``, ``.ui-reference/.../routes.ts:13`` --
    and the register's Python-only anchor grammar never resolved any of them. Measured now: 870 anchors in
    141,587 register cells, 869 alive, and the one exception is the cell below. A cite that has scrolled
    past the end of its file, or that names two tracked files, prints exactly like a trustworthy one, which
    is why this is a gate rather than a report.
    """
    report = module.register_cite_liveness()
    summary = report["summary"]
    # the enumerated face must be the whole register set, not a list of files someone remembered
    assert summary["cells"] > 100000, summary
    assert summary["anchors"] > 500, summary
    seen = set()
    unexpected = []
    for failure in report["failures"]:
        register = failure["cell"].split(":", 1)[0]
        key = _ledger_key(register, failure["anchor"])
        seen.add(key)
        if key not in REGISTER_ANCHOR_EXEMPTIONS:
            unexpected.append("%s %s -> %s" % (failure["cell"], failure["anchor"], failure["why"]))
    assert not unexpected, "登记里发布了不再成立的锚点：\n" + "\n".join(unexpected[:8])
    dead = sorted(key for key in REGISTER_ANCHOR_EXEMPTIONS if key not in seen)
    assert not dead, "登记锚点豁免已不再被引用，留着会掩护下一个真损坏：%s" % dead
    # both shapes must be inside the face, or a whole class of cites is checked by name only
    shapes = {"symbol": 0, "line": 0}
    for rel, column, number, value in module.register_cells():
        shapes["symbol"] += len(module.SYMBOL_ANCHOR.findall(value))
        shapes["line"] += len(module.ANY_ANCHOR.findall(value))
    assert shapes["symbol"] > 100 and shapes["line"] > 100, (
        "登记锚点的一种形态没有真正进入检查面：%s" % shapes)


def test_the_account_name_survives_only_where_it_is_accounted_for(module):
    """#16's end state, as a gate: outside the byte-frozen inputs, one file may carry the account name.

    The delivered task packs and the migrated copies hold the account name by nature (they are records of
    another machine's run), and rewriting them would be editing source evidence. Everything else is ours,
    and after this round it is exactly one register -- ``config/adapter-registry.json``, four probed
    absolute paths, guarded elsewhere by the rule that a machine path must still sit next to
    未探测/未合格. A new file that spells the account name here is a leak, not a stylistic choice, so the
    permitted set is a named subset rather than a size threshold. On another machine -- same repo,
    different username -- the set is legitimately empty, which is why the claim is "no new files" plus a
    count check on the one file that is allowed, not an equality against this box's account name.
    Both shapes are swept now -- the standalone token *and* the whole machine path, because the path rule
    is case-insensitive and a lowercase spelling inside our own test fixtures stayed invisible to the
    token-only version of this guard.
    """
    account = module.account_name()
    claimed = module.ledger_targets()
    token = re.compile(r"(?<![A-Za-z0-9_.\-/])" + re.escape(account) + r"(?![A-Za-z0-9_.\-/])")
    path_rule = module.machine_path_rule(account)
    frozen_custody = {"frozen_source_input", "migrated_copy", "append_only_history"}
    found = {}
    found_paths = {}
    for rel in module.tracked_files():
        if module.owner_of(rel, claimed) in frozen_custody:
            continue
        text = module.read_tracked_text(TARGET_ROOT / rel)
        if text is None:
            continue
        hits = len(token.findall(text))
        paths = len(path_rule.findall(text))
        if hits:
            found[rel] = hits
        if paths:
            found_paths[rel] = paths
    assert set(found) <= {"config/adapter-registry.json"}, (
        "本仓可自修部分里出现了带本机账号名的新文件：%s" % sorted(found.items()))
    assert set(found_paths) <= {"config/adapter-registry.json"}, (
        "本仓可自修部分里出现了带本机绝对路径的新文件（小写拼法也算，路径形态本来就是大小写无关的）："
        "%s" % sorted(found_paths.items()))
    # the one permitted file is permitted only while it still carries what the other guard recognises:
    # probed absolute paths sitting next to 未探测/未合格. Two accounts, one box -- on another machine the
    # set is legitimately empty, so this is a subset claim, not an equality against this box's username.
    if "config/adapter-registry.json" in found:
        assert found["config/adapter-registry.json"] == 4, (
            "那格注册表带的账号名数量变了，相邻性规则覆盖的就不再是同一批字节：%s" % found)


def test_the_producer_and_this_guard_reach_the_same_verdict_on_the_same_cites(module):
    """Two implementations of one rule, or the agreement is worthless.

    ``own_cite_liveness`` is the instrument a reader can re-run; the walk above is written separately so
    neither one is the only witness. If they disagree -- over the enumerated face, over what counts as
    outside the tracked tree, or over which cites are broken -- then at least one is wrong, and the number
    the audit entry quotes would be a claim about one piece of code rather than a fact about the
    repository. The ledger is asserted to be exactly the broken set, so a new broken cite can only be
    silenced by naming it above with a reason.
    """
    report = module.own_cite_liveness()
    tool_broken = {_ledger_key(row["citing"], row["cite"]) for row in report["broken"]}
    assert tool_broken == set(SYNTHETIC_LOCATIONS), (
        "工具与守卫认定的损坏集合不一致，工具多出：%s；守卫多出：%s"
        % (sorted(tool_broken - set(SYNTHETIC_LOCATIONS)),
           sorted(set(SYNTHETIC_LOCATIONS) - tool_broken)))

    own_files = [row for row in module.tracked_files()
                 if row.startswith(("scripts/", "tests/", "backend/", "domains/work/"))
                 or ("/" not in row and row.endswith((".md", ".toml")))]
    assert report["summary"]["files"] == len(own_files), (
        "两侧的枚举面不同：工具 %s vs git ls-files %s"
        % (report["summary"]["files"], len(own_files)))
    independent = {rel: CITE_IN_TEXT.findall(
        (TARGET_ROOT / rel).read_text(encoding="utf-8", errors="replace")) for rel in own_files}
    assert report["summary"]["cites"] == sum(len(v) for v in independent.values()), (
        "两侧识别出的引用条数不一致，正则已经分叉")
    # the same rule written twice has to agree file by file, not merely in total: a face that lost one
    # file and gained another would still add up
    assert [row["file"] for row in report["by_file"]] == sorted(k for k, v in independent.items() if v), (
        "逐件清单与本守卫独立数出的文件集不同")
    assert report["summary"]["files_with_cites"] == len([v for v in independent.values() if v]), (
        "带引用的文件数与独立枚举不符：%s vs %s"
        % (report["summary"]["files_with_cites"], len([v for v in independent.values() if v])))
    shapes = {"symbol": 0, "line": 0, "anchor": 0}
    for cites in independent.values():
        for cite in cites:
            shapes[_split_cite(cite)[1]] += 1
    assert report["by_shape"] == shapes, (
        "形态分列与本守卫独立分类的结果不同，两侧对同一句话的判读已经分叉：%s vs %s"
        % (report["by_shape"], shapes))
    assert report["summary"]["broken"] == len(report["broken"]), "摘要与明细自相矛盾"
    assert report["summary"]["outside_tracked_tree"] > 0, (
        "示例与沙箱件这一类本来就该存在，为 0 说明枚举面收窄了")
