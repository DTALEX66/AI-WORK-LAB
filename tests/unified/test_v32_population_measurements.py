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
    (tmp_path / "paths.md").write_text("C:\\Users\\alex\\work\n", encoding="utf-8")
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
    (tmp_path / "person.md").write_text("Alex Atallah and Alex Garcia were both quoted\n",
                                        encoding="utf-8")
    (tmp_path / "path.md").write_text("cache = C:/users/alex/models/snap.safetensors\n",
                                      encoding="utf-8")
    document = module.measure(root=tmp_path, account="ALEX", claimed=set(),
                              files=["person.md", "path.md"])
    buckets = document["by_ownership"]
    total = {field: sum(buckets[key][field] for key in buckets)
             for field in ("account_mentions", "absolute_machine_paths")}
    assert total["account_mentions"] == 0, (
        "另一个人的名字被算成本机账号名，人群又会虚涨：%s" % buckets)
    assert total["absolute_machine_paths"] == 1, (
        "小写拼法的真实路径漏掉了：机器路径判据不能跟着大小写走 %s" % buckets)


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
    (tmp_path / "gone.md").write_text("C:\\Users\\alex\\work\\secret.md\n", encoding="utf-8")
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
            for field in ("files", "line_cites", "account_mentions", "absolute_machine_paths")}
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


def test_own_code_line_cites_point_at_bytes_that_are_still_there(module):
    """Every number written into our own prose has to still exist in the file it names.

    The ``own_code_and_checks`` population (146 cites) is dense evidence commentary: a cite spanning
    dozens of lines in ``canonical_store`` names a *region*, so swapping each cite for the enclosing
    symbol would lose which part of the function the sentence is about. What cannot be allowed is
    silence -- a cite whose line has scrolled past the end of its file reads exactly like a live one.
    This node enumerates the tracked tree itself (never a hand-listed file set) and accepts a basename
    that is ambiguous -- most of these name two tracked files, ours and a frozen source copy -- as long
    as *some* candidate still has that line, because demanding a unique answer today would flag the
    whole population instead of the rot.
    """
    files = [row for row in module.tracked_files()
             if row.startswith(("scripts/", "tests/", "backend/", "domains/work/"))]
    assert len(files) > 100, "the own-code population collapsed: %d files" % len(files)

    by_name: dict[str, list[str]] = {}
    for rel in module.tracked_files():
        by_name.setdefault(pathlib.PurePosixPath(rel).name, []).append(rel)

    seen, broken, exempt_hits = set(), [], set()
    for rel in files:
        try:
            text = (TARGET_ROOT / rel).read_text(encoding="utf-8", errors="replace")
        except (OSError, UnicodeDecodeError):
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for cite in CITE_IN_TEXT.findall(line):
                seen.add((rel, cite))
                head, kind, tail = _split_cite(cite)
                tail_key = ("%d-%d" % tail) if kind == "line" and tail[0] != tail[1] else str(
                    tail[0]) if kind == "line" else tail
                if (rel, head, tail_key) in SYNTHETIC_LOCATIONS:
                    exempt_hits.add((rel, head, tail_key))
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
                    broken.append("%s:%d %s -> 候选文件里已经没有这个位置" % (rel, number, cite))

    dead = sorted(key for key in SYNTHETIC_LOCATIONS if key not in exempt_hits)
    assert not dead, "具名豁免已不再被引用，留着会掩护下一个真损坏：%s" % dead
    assert not broken, "本仓散文里的引用不再指向存在的内容：\n" + "\n".join(broken[:12])
