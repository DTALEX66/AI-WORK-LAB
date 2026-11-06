# SPDX-License-Identifier: MIT
"""V35: the owner's decision channel decides nothing until a named person decides something.

``L10#0`` blocks this batch on 32 source files that no machine may classify. Two earlier
weaknesses made that queue cost more than it should and say less than it did:

* the register's own ``decision_how`` told the owner to write the category into the
  ``authority`` column of ``migration/source-coverage-*.csv`` -- but ``class`` is recomputed by
  ``adjudicate_unregistered()`` on every rebuild, so a hand-written decision was overwritten by
  the next generator run. The instruction and the mechanism disagreed;
* the rows arrived as bare paths with no evidence attached, so answering them meant re-deriving
  the whole list again (which is exactly why the count used to be a one-off script's output).

``config/unregistered-adjudications.json`` is the channel that fixes both: per row a proposed
category, a cite whose anchor names the text it points at (``path::符号`` in code, ``path::#片段``
in prose and in generated rows -- a bare line number was shown here to point at the wrong row and
the wrong sentence while still "resolving"), and a ``decided_by`` that is null until a person
fills it. The nodes below pin the property that makes that safe -- an undecided row stays pending
however the file is written -- the byte-binding that stops a decision about one revision being
reused for another, and the fact that an anchor can actually break.
"""
from __future__ import annotations

import ast
import importlib
import json
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = TARGET_ROOT / "scripts"
CHANNEL = TARGET_ROOT / "config" / "unregistered-adjudications.json"
sys.path.insert(0, str(SCRIPTS))
import build_source_coverage as coverage  # noqa: E402

CATEGORIES = coverage.DECISION_OPTIONS


def _channel() -> dict:
    return json.loads(CHANNEL.read_text(encoding="utf-8-sig"))


def _queue() -> list[dict]:
    import build_blocker_register as blockers
    return blockers.owner_queue()


def test_the_shipped_channel_proposes_every_pending_row_and_decides_none():
    """32 proposals, 0 decisions: the gate must still refuse, and the register must say so."""
    document = _channel()
    rows = document["rows"]
    queue = _queue()
    assert rows, "通道里一行证据都没有，下面所有断言都成空话"
    assert len(rows) == len(queue), (len(rows), len(queue))
    queue_keys = {(row["repo"], row["path"], row["source_sha256"]) for row in queue}
    channel_keys = {(row["repo"], row["path"], row["source_sha256"]) for row in rows}
    assert queue_keys == channel_keys, (sorted(queue_keys - channel_keys),
                                       sorted(channel_keys - queue_keys))
    assert all(row["proposed_category"] in CATEGORIES for row in rows)
    assert all(not str(row.get("decided_by") or "").strip() for row in rows), \
        "执行器把自己写的提议标成了决定"
    assert document["counts"]["decided"] == 0, document["counts"]


def test_every_cite_is_a_content_anchor_that_resolves():
    """Every row's authority must name the text it points at; a bare line number is not evidence.

    The node that shipped first accepted ``path:NNN`` as "in range and not blank", and that is why
    two rows went on citing ``PROJECT_CURRENT.md:212`` after a §五 edit moved that line onto an
    unrelated sentence, and why six rows cited a *neighbouring* row of the very coverage register
    they describe: a line number is a fact about the last build, not about the claim. Now a row
    whose anchor matches no line, or matches more than one, is a failure of this file.
    """
    tracked = {p.decode("utf-8", "surrogateescape") for p in subprocess.run(
        ["git", "ls-files", "-z"], cwd=str(TARGET_ROOT), capture_output=True,
        timeout=300).stdout.split(b"\0") if p}
    module = importlib.import_module("build_unregistered_adjudications")
    bare, unresolved = [], []
    for row in _channel()["rows"]:
        cite = row["authority"]
        if "::" not in cite:
            bare.append((row["path"], cite))
            continue
        path_text, _, anchor = cite.rpartition("::")
        if path_text not in tracked:
            unresolved.append((row["path"], cite, "target not tracked"))
            continue
        if anchor.startswith("#"):
            hits = [line for line in (TARGET_ROOT / path_text).read_text(
                encoding="utf-8", errors="replace").splitlines() if anchor[1:] in line]
            if len(hits) != 1:
                unresolved.append((row["path"], cite, "%d lines carry the anchor" % len(hits)))
            continue
        tree = ast.parse((TARGET_ROOT / path_text).read_text(encoding="utf-8"))
        defined = set()
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                defined.add(node.name)
            elif isinstance(node, ast.Assign):
                defined.update(t.id for t in node.targets if isinstance(t, ast.Name))
        if anchor not in defined:
            unresolved.append((row["path"], cite, "symbol not defined"))
    assert bare == [], ("这些格的出处仍是行号，被引文件一改就悄悄指错：" + str(bare))
    assert unresolved == [], unresolved
    # the generator must reach the same answer from its own side, or the two readings of
    # "resolved" would drift apart and the register would keep printing 0 unresolved
    stale = [row["authority"] for row in _channel()["rows"]
             if not module.cite_resolves(module.check_cite(row["authority"]))]
    assert stale == [], stale


def test_an_anchor_that_matches_no_line_or_several_is_not_a_resolution():
    """The anchors can fail: absent text refuses, and so does text that is not unique.

    Without the ambiguous half, an anchor like ``#OWNER_DECISION_PENDING`` would "resolve" against
    a register where every second row contains it, and the row would look evidenced while pointing
    at nothing in particular.
    """
    module = importlib.import_module("build_unregistered_adjudications")
    absent = module.check_cite("AGENTS.md::#这一句在本仓里不存在 xyzzy")
    assert not module.cite_resolves(absent), absent
    ambiguous = module.check_cite("migration/source-coverage-work.csv::#OWNER_DECISION_PENDING")
    assert not module.cite_resolves(ambiguous), ambiguous
    unique = module.check_cite("migration/source-coverage-work.csv::#work,apps/observer/scripts/"
                               "u19_webview_e2e.py")
    assert module.cite_resolves(unique), unique


def test_the_channel_builder_checks_without_writing_and_refuses_an_unknown_flag():
    """``--check`` used to be no flag at all: an unknown argument was ignored and the file was written.

    Discovered by typing it: the register came back "verified" with ``written`` in the output while
    nobody asked for a write. A mode that does not exist has to be an error, and a check must not
    move a byte.
    """
    module = importlib.import_module("build_unregistered_adjudications")
    shipped = CHANNEL.read_bytes()
    assert module.main(["build_unregistered_adjudications.py", "--chek"]) == 2, (
        "一个不存在的旗标被当成没看见，下一句就是写盘")
    assert CHANNEL.read_bytes() == shipped, "未知旗标那一趟还是改了登记表字节"

    control = CHANNEL
    assert module.main(["build_unregistered_adjudications.py", "--check"]) == 0
    assert CHANNEL.read_bytes() == shipped, "--check 写了字节：它必须只是读者"

    other = CHANNEL.with_name("unregistered-adjudications.mutated.json")
    other.write_bytes(b"{\n  \"rows\": []\n}\n")
    original = module.OUT
    try:
        module.OUT = other
        assert module.main(["build_unregistered_adjudications.py", "--check"]) == 1, (
            "登记表与现算结果不一致时 --check 仍然报 0")
    finally:
        module.OUT = original
        other.unlink()


def test_a_proposal_without_a_decider_changes_no_class(tmp_path):
    """Pointing the adjudicator at proposed-only rows must fall through to the pending answer."""
    module = _reloaded_with_channel(tmp_path, decided=[])
    rel = _channel()["rows"][0]["path"]
    digest = _channel()["rows"][0]["source_sha256"]
    verdict = module.adjudicate_unregistered(Path(tmp_path / "no-such-source-repo"), rel, {}, digest)
    assert verdict[0] == "OWNER_DECISION_PENDING", verdict


def test_a_named_decision_applies_to_those_bytes_and_to_no_others(tmp_path):
    """The two properties that make the channel safe to fill in: a name, and the exact bytes.

    Planting is done against a temporary copy of the channel file, never against the tracked
    one, and the missing-source-root path proves the ruling short-circuits before any disk read
    -- so it cannot quietly be the ladder's own answer dressed up as the owner's.
    """
    row = _channel()["rows"][0]
    decided = dict(row, category="UNREGISTERED_DEV_TOOLING", decided_by="DTALEX66",
                   decided_at="2026-11-06", reason="样例：具名真人的判定")
    module = _reloaded_with_channel(tmp_path, decided=[decided])
    gone = Path(tmp_path / "no-such-source-repo")

    verdict = module.adjudicate_unregistered(gone, row["path"], {}, row["source_sha256"])
    assert verdict[0] == "UNREGISTERED_DEV_TOOLING", verdict
    assert "unregistered-adjudications.json" in verdict[1], verdict
    assert "DTALEX66" in verdict[2], verdict

    other = module.adjudicate_unregistered(gone, row["path"], {}, "0" * 64)
    assert other[0] == "OWNER_DECISION_PENDING", \
        ("换了字节还沿用同一条判定：那判定说的是另一个版本的内容", other)


def test_an_unnamed_or_unclassifiable_decision_is_refused_not_ignored(tmp_path):
    """A row that claims to be decided but cannot say by whom, or into what, is a defect."""
    row = _channel()["rows"][0]
    for broken, expect in (
            (dict(row, category="UNREGISTERED_INVENTED_CLASS", decided_by="someone"),
             "OWNER_DECISION_CATEGORY_UNKNOWN"),
            (dict(row, category="UNREGISTERED_DEV_TOOLING", decided_by="x", authority=""),
             "OWNER_DECISION_WITHOUT_AUTHORITY")):
        module = _reloaded_with_channel(tmp_path, decided=[broken])
        try:
            module.adjudicate_unregistered(Path(tmp_path / "gone"), row["path"], {},
                                           row["source_sha256"])
        except SystemExit as exit_error:
            assert expect in str(exit_error), (expect, str(exit_error))
        else:
            raise AssertionError("坏判定被静默接受：%s" % expect)


def _reloaded_with_channel(tmp_path: Path, decided: list[dict]):
    """A module whose channel is a temp copy: proposals plus the planted decisions."""
    rows = [dict(row, decided_by=None) for row in _channel()["rows"]]
    by_path = {(row["repo"], row["path"], row["source_sha256"]): row for row in rows}
    for row in decided:
        by_path[(row["repo"], row["path"], row["source_sha256"])].update(row)
    path = tmp_path / "unregistered-adjudications.json"
    path.write_text(json.dumps(dict(rows=rows), ensure_ascii=False), encoding="utf-8")
    sys.modules.pop("build_source_coverage", None)
    module = importlib.import_module("build_source_coverage")
    module.ADJUDICATIONS = path
    module._DECISIONS = None
    return module
