#!/usr/bin/env python
"""Measure two citation populations over the tracked tree, and say who owns each byte.

Both numbers in this project's entry document come out of here, for a specific reason: measured once by
an ad-hoc script under ``.project-local`` a figure is unreviewable from a clone, and two such figures
have already been wrong in this way -- "322 tracked files contain the machine account name" (a loose
substring match that also counted the public repo owner ``DTALEX66``, which contains the same letters)
and "621 prose ``.py:line`` cites" (a count whose exclusions differed between runs). A measurement a
reader cannot re-run is a claim, so this tool is tracked, deterministic (no timestamps, no machine
paths in its output) and refuses loudly instead of returning a reassuring zero.

Populations:
  * ``line_cites``   -- ``<path>.py:123`` (optionally a range) mentions of Python line numbers,
                        including the ones in prose, which no register guard resolves.
  * ``machine_names`` -- mentions of this checkout's OS account name, split into standalone tokens,
                        whole absolute machine paths, and the repo-owner token that must not be
                        confused with either.

The two machine-name counters are deliberately not symmetric. ``account_mentions`` is case-SENSITIVE:
the account's own spelling is what appears in a leaked path or a quoted user name, and a case-insensitive
token sweeps in *other people* -- the tracked tree holds archive objects naming "Alex Atallah" and "Alex
Garcia" and an avatar labelled ``Alex``, none of which is this machine's account. Counting them would
repeat the mistake that inflated 218 into 322, in the opposite direction. Lowercase spellings of a real
path are not lost: ``absolute_machine_paths`` is case-insensitive because it keys on the drive or
``/home``-``/Users`` shape, which a person's name cannot produce. The split is pinned by
``tests/unified/test_v32_population_measurements.py``.

Ownership comes from the ledgers (``migration/copies.json`` and the history MANIFEST), matched at
prefix boundaries: an earlier version used ``endswith`` and claimed ``AGENTS.md`` was a byte-for-byte
copy of a source-repo file, which is how a probe manufactures a wrong bucket.

    python -B -X utf8 scripts/measure_citation_population.py
    python -B -X utf8 scripts/measure_citation_population.py --json-out out.json
"""
from __future__ import annotations

import argparse
import csv
import io
import json
import os
import pathlib
import re
import subprocess
import sys

REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
COPIES = REPO_ROOT / "migration" / "copies.json"
MANIFEST = REPO_ROOT / "docs" / "history" / "sources-20261101" / "MANIFEST.csv"
# owner-delivered task pack and the October authority snapshots: records, not our prose
FROZEN_INPUTS = ("docs/audits-20261103-cloud-audit/", "docs/authority-202610/", "docs/history/")
APPEND_ONLY = ("docs/CODEX-AUDIT-ENTRY.md",)
GENERATED = ("migration/", "config/")
OUR_OWN_CODE = ("scripts/", "tests/", "backend/", "domains/work/")

LINE_CITE = re.compile(r"[\w./-]+\.py:\d+(?:-\d+)?")
ABS_WIN = r"[A-Za-z]:[\\/][^\s\"'`<|]*"
#: Git-Bash rewrites ``D:\x`` as ``/d/x``, so the home-shaped prefixes include that spelling
ABS_POSIX = r"(?:/home|/(?:[a-z]/)?users)/"
#: a Windows home path that stops at the account directory: ``C:\\Users\\<account>`` with nothing after
#: it (the placeholder is deliberate -- spelling this box's name here is the leak the guard looks for).
#: Insisting that ``users``/``home`` sit directly behind the drive prefix is what keeps ``https:`` from
#: being read as a drive letter here.
ABS_HOME_DIR = r"[A-Za-z]:[\\/](?:users|home)[\\/]"
#: a home path written as a fragment -- ``（Users/<account>/AppData/Temp/…）`` -- with no drive in front of it
#: and nothing before the word but a non-path character. Requiring a separator *after* the name keeps
#: ``GitHub users/name`` style prose out, and measured over this tree the branch adds exactly one file,
#: which is the fragment it was written for.
ABS_HOME_SEGMENT = r"(?<![A-Za-z0-9_./\\-])(?:users|home)[\\/]"


def _account_token(account: str, inside_path: bool) -> str:
    """The account name with the boundaries that stop a *person* being read as this machine.

    ``DTALEX66`` holds the account letters, which is what inflated 218 into 322 once. Outside a path the
    token must not touch a separator either, so a URL segment naming the account is not a standalone
    account mention.
    """
    before = r"(?<![A-Za-z0-9_.\-])" if inside_path else r"(?<![A-Za-z0-9_.\-/])"
    return before + re.escape(account) + r"(?![A-Za-z0-9_.\-])"


def machine_path_rule(account: str) -> re.Pattern:
    """A whole absolute path that contains this machine's account, in any spelling of the case.

    Case-insensitive on purpose: the forward-slash, lowercase spelling of a home path leaks exactly what
    the backslashed, upper-case one does,
    and a case-sensitive rule let the lowercase spellings -- which is what Git-Bash and most JSON dumps
    write -- out of the population entirely.

    Four shapes, not one. The drive branch needs the account to sit *inside* a path (a separator after
    it); the third branch is the path that stops at the account directory itself -- drive, ``\\Users\\``,
    the name, nothing after it -- which the first branch cannot see and which five frozen inputs do write;
    the fourth is the home fragment inside a table cell (``（Users/<account>/AppData/…）``), with no drive
    and no leading slash in front of it, which one more frozen input writes and which no counter saw at
    all -- the cost of admitting it, measured here, is one file for one file.
    Both bounds on that first branch are load-bearing, and the cost of loosening each one is measured, not
    assumed: letting the span cross whitespace adds three files that are not paths at all
    (``https://app.notion.com/…-DT alex/tag`` and two archive objects), and dropping the trailing
    separator as well takes it to fourteen, because ``s:`` from ``https:`` is a perfectly plausible drive
    letter. Over-counting a leak is recoverable; counting other people's names as this machine is the
    mistake that turned 218 into 322.
    """
    token = _account_token(account, inside_path=True)
    return re.compile(r"(?:%s%s[\\/]|%s%s|%s%s|%s%s[\\/])"
                      % (ABS_WIN, token, ABS_POSIX, token, ABS_HOME_DIR, token,
                         ABS_HOME_SEGMENT, token), re.IGNORECASE)


def account_name() -> str:
    """This checkout's OS account name, or "" when it cannot be determined -- never a guess."""
    home = str(pathlib.Path.home())
    tail = re.split(r"[\\/]", home.strip("\\"))[-1]
    return tail if len(tail) >= 2 else ""


def tracked_files() -> list[str]:
    listed = subprocess.run(["git", "ls-files", "-z"], cwd=str(REPO_ROOT), capture_output=True,
                            check=True).stdout
    return [p.decode("utf-8", "replace") for p in listed.split(b"\0") if p]


def read_tracked_text(path: pathlib.Path):
    """Text of a tracked byte, or None when the disk refuses -- which the caller must report.

    ``D:\\``-style paths stop at 259 characters, so a deep frozen input reads as
    ``FileNotFoundError`` on the path the index actually stores. The long-form prefix is tried before
    anything is called absent, because an earlier instrument of exactly this shape dropped 860 cites by
    skipping files it never mentioned.
    """
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        if os.name != "nt":
            return None
        try:
            with open("\\\\?\\" + str(path.absolute()), "r", encoding="utf-8",
                      errors="replace") as handle:
                return handle.read()
        except OSError:
            return None


def to_relative(value: str) -> str:
    value = (value or "").replace("\\", "/").strip()
    if not value:
        return ""
    marker = REPO_ROOT.name + "/"
    if marker in value:
        return value.split(marker, 1)[1].lstrip("/")
    return value.lstrip("/")


def ledger_targets() -> set[str]:
    """Relative paths the ledgers claim as copies -- read for shape, never assumed."""
    if not COPIES.is_file():
        # str(), not relative_to(): a caller may point these at a sandbox, and a traceback is not a
        # named refusal
        raise SystemExit("MEASUREMENT_LEDGER_ABSENT: %s" % COPIES)
    claimed: set[str] = set()
    document = json.loads(COPIES.read_text(encoding="utf-8-sig"))
    if not isinstance(document, dict) or "copies" not in document:
        raise SystemExit("MEASUREMENT_LEDGER_SHAPE: %s 没有 copies 键，无法判定归属"
                         % COPIES)
    for row in document.get("copies", []):
        target = to_relative(row.get("target", ""))
        if target:
            claimed.add(target)
        for record in row.get("records") or []:
            nested = to_relative(record.get("target", ""))
            if nested:
                claimed.add(nested)
    for row in document.get("patches", []):
        if row.get("file"):
            claimed.add(to_relative(row["file"]))
    for row in document.get("inits", []):
        if isinstance(row, str) and row:
            claimed.add(to_relative(row))
    if MANIFEST.is_file():
        with MANIFEST.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                target = to_relative(row.get("target_rel") or "")
                if target:
                    claimed.add(target)
    else:
        # the manifest is the second of the two ownership sources; without it a file under a copied
        # tree could be read as ours, so this is a named gap rather than a quiet narrower scan
        # the second ownership source; without it a file under a copied tree would be read as our
        # own prose, which is how a rewrite of a frozen record gets looks-legitimate. str(), not
        # relative_to(): a caller may point these at a sandbox, and a traceback is not a refusal.
        raise SystemExit("MEASUREMENT_LEDGER_ABSENT: %s" % MANIFEST)
    return claimed


def owner_of(relative: str, claimed: set[str]) -> str:
    """Which of the four kinds of custody this byte stream is under -- boundaries, not suffixes."""
    if relative.startswith(APPEND_ONLY):
        return "append_only_history"
    if relative.startswith(FROZEN_INPUTS):
        return "frozen_source_input"
    if any(relative == target or relative.startswith(target + "/") for target in claimed):
        return "migrated_copy"
    if relative.startswith(GENERATED):
        return "generated_register"
    if relative.startswith(OUR_OWN_CODE):
        return "own_code_and_checks"
    return "own_other"


OWNERSHIPS = ("append_only_history", "frozen_source_input", "migrated_copy", "generated_register",
              "own_code_and_checks", "own_other")


def measure(root: pathlib.Path = REPO_ROOT, account: str | None = None,
            claimed: set[str] | None = None, files: list[str] | None = None) -> dict:
    """The two populations, bucketed by custody, over the tracked tree of ``root``."""
    root = pathlib.Path(root)
    account = account_name() if account is None else account
    if not account:
        raise SystemExit("MEASUREMENT_PREREQ_MISSING: 这台机器的账号名无法确定，"
                         "账号名人群不做（返回 0 会被读成「没有泄漏」）")
    claimed = ledger_targets() if claimed is None else claimed
    bare = re.compile(_account_token(account, inside_path=False))
    abs_path = machine_path_rule(account)
    if files is None:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=str(root), capture_output=True,
                                check=True).stdout
        files = [row.decode("utf-8", "replace") for row in listed.split(b"\0") if row]
    buckets = {kind: {"files": 0, "line_cites": 0, "account_mentions": 0,
                      "absolute_machine_paths": 0,
                      "files_with_line_cites": 0, "files_with_account_mentions": 0,
                      "files_with_absolute_paths": 0, "files_with_account_mention_and_path": 0,
                      "paths": []} for kind in OWNERSHIPS}
    unreadable: list[str] = []
    scanned = 0
    for relative in sorted(files):
        text = read_tracked_text(root / relative)
        if text is None:
            unreadable.append(relative)
            continue
        scanned += 1
        kind = owner_of(relative, claimed)
        bucket = buckets[kind]
        cites = len(LINE_CITE.findall(text))
        mentions = len(bare.findall(text))
        absolute = len(abs_path.findall(text))
        bucket["line_cites"] += cites
        bucket["account_mentions"] += mentions
        bucket["absolute_machine_paths"] += absolute
        if cites:
            bucket["files_with_line_cites"] += 1
        if mentions:
            bucket["files_with_account_mentions"] += 1
        if absolute:
            bucket["files_with_absolute_paths"] += 1
        if mentions and absolute:
            # §15.45 published "218 files carry the account name, 168 of them also a whole machine path".
            # The second number is an intersection inside the first population, not "files with a path"
            # over the whole tree (that is a different, larger set), so it needs its own counter or the
            # next reader recomputes it with a scratch script and gets a third answer.
            bucket["files_with_account_mention_and_path"] += 1
        if cites or mentions or absolute:
            bucket["files"] += 1
            if len(bucket["paths"]) < 12:
                bucket["paths"].append(relative)
    return {"files_scanned": scanned, "files_tracked": len(files),
            "files_unreadable": len(unreadable),
            "unreadable_paths": unreadable[:12],
            "account_name_length": len(account),
            "ledger_claimed_targets": len(claimed),
            "totals": {key: sum(bucket[key] for bucket in buckets.values())
                       for key in ("files", "line_cites", "account_mentions",
                                   "absolute_machine_paths", "files_with_line_cites",
                                   "files_with_account_mentions", "files_with_absolute_paths",
                                   "files_with_account_mention_and_path")},
            "by_ownership": {key: {field: value for field, value in bucket.items()
                                   if field != "paths"}
                             for key, bucket in buckets.items()},
            "samples": {key: bucket["paths"] for key, bucket in buckets.items() if bucket["paths"]}}


OWN_CODE_PREFIXES = ("scripts/", "tests/", "backend/", "domains/work/")
#: root-level documents and build config are ours to edit and they cite code: ``pyproject.toml`` explains
#: the install-tree layout with seven ``file.py:line`` references, and those were outside the checked face
#: until now -- a cite nobody recomputes is a cite that silently rots when the file it names grows.
ROOT_TEXT_SUFFIXES = (".md", ".toml")


def in_own_face(relative: str) -> bool:
    """Is this tracked byte our own prose -- code, checks, or a root-level document?"""
    return relative.startswith(OWN_CODE_PREFIXES) or (
        "/" not in relative and relative.endswith(ROOT_TEXT_SUFFIXES))
#: the three shapes a citation to a Python file can take in prose or in a message string
CITE_SHAPE = re.compile(r"(?P<cite>[\w./-]+\.py(?:::[A-Za-z_]\w*|:\d+(?:-\d+)?|#[^\s,;)\]\"`]+))")
#: migration-map identity keys name a file in the SOURCE repository's layout: a row's id, not a location
FOREIGN_SOURCE_PREFIXES = ("src/design_lab/", "src/work/", "design-lab/", "work-lab/")
DEF_OR_BIND = re.compile(r"^\s*(?:def|class)\s+(?P<name>[A-Za-z_]\w*)|^\s*(?P<bound>[A-Za-z_]\w*)\s*[:=]")


def _symbols_defined_once(path: pathlib.Path) -> set[str]:
    """Names a file defines exactly once, as a def/class header or a name binding."""
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except (OSError, UnicodeDecodeError):
        return set()
    counts: dict[str, int] = {}
    for text in lines:
        match = DEF_OR_BIND.match(text)
        if not match:
            continue
        name = match.group("name") or match.group("bound")
        counts[name] = counts.get(name, 0) + 1
    return {name for name, hits in counts.items() if hits == 1}


def _cite_parts(cite: str):
    if "::" in cite:
        head, _sep, name = cite.partition("::")
        return head, "symbol", name
    shaped = re.match(r"^(?P<path>[\w./-]+\.py):(?P<start>\d+)(?:-(?P<end>\d+))?$", cite)
    if shaped:
        start = int(shaped.group("start"))
        return shaped.group("path"), "line", (start, int(shaped.group("end") or shaped.group("start")))
    head, _sep, anchor = cite.partition("#")
    return head, "anchor", anchor


def own_cite_liveness(root: pathlib.Path = REPO_ROOT, files: list[str] | None = None) -> dict:
    """Do the line numbers written into our own prose still point at content that exists?

    A ``file.py:1234`` sentence reads the same whether line 1234 is the guard it describes or a blank line
    fifty rows below it, and this repo has already published one of each. The registers refuse line
    numbers; this walks the prose. Cites whose path is not in the tracked tree are counted separately and
    never judged: they are docstring examples, sandbox fixtures, and ``.project-local`` receipt paths --
    there is no tracked byte for them to have drifted away from.

    The exemption ledger lives with the guard (``tests/unified/test_v32_population_measurements.py``), not
    here, so a broken cite cannot be made to disappear by editing the instrument that finds it.
    """
    root = pathlib.Path(root)
    if files is None:
        listed = subprocess.run(["git", "ls-files", "-z"], cwd=str(root), capture_output=True,
                                check=True).stdout
        files = [row.decode("utf-8", "replace") for row in listed.split(b"\0") if row]
    own = sorted(rel for rel in files if in_own_face(rel))
    by_name: dict[str, list[str]] = {}
    for rel in sorted(files):
        by_name.setdefault(pathlib.PurePosixPath(rel).name, []).append(rel)

    counts: dict[str, int] = {"cites": 0, "outside_tracked_tree": 0, "foreign_identity_keys": 0}
    shapes: dict[str, int] = {"symbol": 0, "line": 0, "anchor": 0}
    broken: list[dict] = []
    per_file: dict[str, dict[str, int]] = {}
    lengths: dict[str, int] = {}
    for rel in own:
        text = read_tracked_text(root / rel)
        if text is None:
            continue
        for number, line in enumerate(text.splitlines(), 1):
            for cite in CITE_SHAPE.findall(line):
                counts["cites"] += 1
                head, kind, tail = _cite_parts(cite)
                shapes[kind] += 1
                row = per_file.setdefault(rel, {"cites": 0, "broken": 0})
                row["cites"] += 1
                if (root / head).is_file():
                    candidates = [head]
                else:
                    candidates = by_name.get(pathlib.PurePosixPath(head).name, [])
                if not candidates:
                    counts["outside_tracked_tree"] += 1
                    continue
                if "source_key" in line and cite.startswith(FOREIGN_SOURCE_PREFIXES):
                    counts["foreign_identity_keys"] += 1
                    continue
                live = False
                for cand in candidates:
                    if cand not in lengths:
                        body = read_tracked_text(root / cand)
                        lengths[cand] = 0 if body is None else len(body.splitlines())
                    if kind == "symbol" or (kind == "anchor" and not str(tail).isdigit()):
                        live = tail in _symbols_defined_once(root / cand)
                    else:
                        start, end = tail if kind == "line" else (int(tail), int(tail))
                        live = 0 < start <= lengths[cand] and end <= lengths[cand]
                    if live:
                        break
                if not live:
                    row["broken"] += 1
                    broken.append({"citing": rel, "line": number, "cite": cite, "kind": kind})
    counts["files"] = len(own)
    counts["broken"] = len(broken)
    counts["files_with_cites"] = len(per_file)
    return {"summary": dict(sorted(counts.items())),
            "by_shape": dict(sorted(shapes.items())),
            "by_file": [{"file": rel, "cites": row["cites"], "broken": row["broken"]}
                        for rel, row in sorted(per_file.items())],
            "broken": broken}


REGISTER_DIRS = ("migration", "config")
#: a published anchor may name any tracked text file, not only Python -- ``apps/workbench/shell.ts:346``
#: and ``AI-WORK-LAB_HANDOFF_20261029/12_来源基线.json:6`` are 当前实现位置 values in real registers, and
#: the Python-only anchor grammar never looked at them
ANY_ANCHOR = re.compile(r"(?P<path>[\w./一-鿿-]+\.(?:py|toml|json|md|csv|html|ts|tsx|js|mjs|yaml|yml))"
                        r":(?P<line>\d+)(?:-(?P<end>\d+))?")
#: the durable shape a register may use for Python targets; it is verified here too, because an anchor
#: that names a symbol nobody defines is the same lie as a line number that has scrolled off the end
SYMBOL_ANCHOR = re.compile(r"(?P<path>[\w./一-鿿-]+\.\w+)::(?P<name>[A-Za-z_]\w*)")


def anchor_candidates(cited, root, all_files, by_name):
    """Which tracked file does a published cite mean? Exact path, unique suffix, then unique basename."""
    if (root / cited).is_file():
        return [cited]
    suffixes = [rel for rel in all_files if rel.endswith(cited)]
    if suffixes:
        return suffixes
    return by_name.get(pathlib.PurePosixPath(cited).name, [])


def register_cells(root: pathlib.Path = REPO_ROOT, files: list[str] | None = None):
    """Every string cell of every tracked register, with the column it came from.

    Enumerated from ``git ls-files migration config`` rather than a list of filenames: the first pass over
    this population used a hand-written set of registers and therefore missed
    ``migration/requirement-traceability.csv``, which is the file holding the ``repo:branch`` claims.
    """
    root = pathlib.Path(root)
    if files is None:
        listed = subprocess.run(["git", "ls-files", "-z", *REGISTER_DIRS], cwd=str(root),
                                capture_output=True, check=True).stdout
        files = [row.decode("utf-8", "replace") for row in listed.split(b"\0") if row]
    for rel in sorted(files):
        text = read_tracked_text(root / rel)
        if text is None:
            continue
        if rel.endswith(".csv"):
            rows = list(csv.reader(io.StringIO(text)))
            header = rows[0] if rows else []
            for number, row in enumerate(rows[1:], 2):
                for index, value in enumerate(row):
                    yield rel, (header[index] if index < len(header) else "#%d" % index), number, \
                        value or ""
        elif rel.endswith(".json"):
            document = json.loads(text)

            def walk(node, breadcrumb):
                if isinstance(node, str):
                    yield breadcrumb, node
                elif isinstance(node, dict):
                    for key, value in node.items():
                        yield from walk(value, "%s/%s" % (breadcrumb, key))
                elif isinstance(node, list):
                    for index, value in enumerate(node):
                        yield from walk(value, "%s[%d]" % (breadcrumb, index))

            for breadcrumb, value in walk(document, "(json)"):
                yield rel, breadcrumb, 1, value


def register_cite_liveness(root: pathlib.Path = REPO_ROOT) -> dict:
    """Is every ``file:line`` anchor published in a register still pointing inside its file?

    The registers carry anchors for non-Python targets that no check has ever resolved. A line anchor that
    has scrolled past the end of its file prints exactly like a live one, so this verifies each against the
    tree: the named file must be tracked, the target must be unambiguous, and the line (or both ends of a
    range) must still be within it.
    """
    root = pathlib.Path(root)
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=str(root), capture_output=True,
                             check=True).stdout
    all_files = [row.decode("utf-8", "replace") for row in tracked.split(b"\0") if row]
    by_name: dict[str, list[str]] = {}
    for rel in sorted(all_files):
        by_name.setdefault(pathlib.PurePosixPath(rel).name, []).append(rel)

    counts = {"anchors": 0, "alive": 0, "line_out_of_range": 0, "target_not_tracked": 0,
              "target_ambiguous": 0, "symbol_not_defined": 0, "cells": 0}
    failures = []
    lengths: dict[str, int] = {}

    def check(rel, column, number, cited, path_part, verdict):
        """Resolve one published cite and report the first reason it is not trustworthy."""
        counts["anchors"] += 1
        where = {"cell": "%s:%s:%d" % (rel, column, number), "anchor": cited}
        candidates = anchor_candidates(path_part, root, all_files, by_name)
        if not candidates:
            counts["target_not_tracked"] += 1
            failures.append(dict(where, why="target is not a tracked file"))
            return
        if len(candidates) > 1:
            counts["target_ambiguous"] += 1
            failures.append(dict(where, why="%d tracked files share this name" % len(candidates),
                                 candidates=candidates[:3]))
            return
        target = candidates[0]
        if target not in lengths:
            body = read_tracked_text(root / target)
            lengths[target] = 0 if body is None else len(body.splitlines())
        ok, why = verdict(target, lengths[target])
        if ok:
            counts["alive"] += 1
        else:
            counts[why[0]] += 1
            failures.append(dict(where, cell_target=target, why=why[1]))

    def symbol_verdict(name, target, _count):
        """A ``file.py::symbol`` cite is alive when that name is defined exactly once in it."""
        if (root / target).suffix != ".py":
            return True, ""
        if name in _symbols_defined_once(root / target):
            return True, ""
        return False, ("symbol_not_defined",
                      "no single definition of %s in %s" % (name, target))

    def line_verdict(target, count, start, end):
        if 0 < start <= count and end <= count:
            return True, ""
        return False, ("line_out_of_range",
                      "line %d-%d is past the end of %s (%d lines)" % (start, end, target, count))

    for rel, column, number, value in register_cells(root):
        counts["cells"] += 1
        for match in SYMBOL_ANCHOR.finditer(value):
            name = match.group("name")
            check(rel, column, number, match.group(0), match.group("path"),
                  lambda target, count, _name=name: symbol_verdict(_name, target, count))
        for match in ANY_ANCHOR.finditer(value):
            start = int(match.group("line"))
            end = int(match.group("end") or match.group("line"))
            check(rel, column, number, match.group(0), match.group("path"),
                  lambda target, count, _s=start, _e=end: line_verdict(target, count, _s, _e))
    return {"summary": counts, "failures": failures}


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json-out", type=pathlib.Path)
    parser.add_argument("--check-own-cites", action="store_true",
                        help="walk our own prose citations instead of measuring the populations")
    parser.add_argument("--check-register-cites", action="store_true",
                        help="verify every file:line anchor published inside a register cell")
    args = parser.parse_args(argv)
    if args.check_own_cites:
        document = own_cite_liveness()
    elif args.check_register_cites:
        document = register_cite_liveness()
    else:
        document = measure()
    payload = json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True)
    if args.json_out:
        args.json_out.write_text(payload + "\n", encoding="utf-8", newline="\n")
    print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
