"""Gate: every path cited in the two inbound v2 CSVs resolves, or is declared ABSENT.

These two files (40-row interface binding matrix, 44-row acceptance checklist) are the traceability
artifacts the owner's pack asked for, and I filled them from research reports. That is exactly where a
wrong path does the most damage: a citation that does not resolve reads as provenance. Measured
2026-10-10, after the rows were written: 58 of 232 citations were shorthand (a bare filename, or `src/...`
relative to the front end) that a reader following them from the repository root cannot open, and one
named `apps/observer/frontend/src/lib/shared_rule_adaptation.ts` -- a file that has never existed, carried
in from a transcribed subagent report nobody re-checked (ERR-239).

So the rule is: a citation either resolves to a file in this repository, or is prefixed `ABSENT:` to say
the producer does not exist. The predicate is exercised against synthetic cells too, because a scanner that
finds nothing also "passes".

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import csv
import json
import os
import re
import subprocess
import sys
import unittest
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / "docs/history/archive/ui-priority-20261009/UIV2-INTERFACE-BINDING-MATRIX.csv"
CHECKLIST = ROOT / "docs/history/archive/ui-priority-20261009/UIV2-ACCEPTANCE-CHECKLIST.csv"
MOVE_RECORD = ROOT / "docs/history/archive/MOVED-PATHS-20261019.json"

CITATION = re.compile(r"(?<![\w:./-])(ABSENT:)?([A-Za-z0-9_./\-]+\.(?:py|tsx|ts|json|yaml|yml|csv|md|js))(:\d+)?")
# What must never decide whether a citation resolves: the runtime root (not checkout-verifiable),
# the build and dependency trees, and the frozen/reference copies this checkout carries -- a
# `.ui-reference/WORK-LAB/**` twin would make a stale path look alive (the same trap the document
# citation guard records for bare names).
EXCLUDED_INDEX_PREFIXES = (".project-local", ".ui-reference", "node_modules", "dist", ".git")
PRUNED_DIRECTORY_NAMES = frozenset({".git", "node_modules", "dist", "__pycache__", ".venv",
                                    "target", "build"})
CITED_FIELDS = frozenset({"current_contract", "actual_field_paths", "source_file_or_symbol",
                          "error_mapping", "evidence", "evidence_path"})
EXPECTED = [(MATRIX, 40, ("id", "area", "component", "required_semantics", "authority", "mode",
                          "unknown_or_error_ui", "gate", "current_contract", "actual_field_paths",
                          "source_file_or_symbol", "error_mapping", "evidence", "binding_status")),
            (CHECKLIST, 44, ("id", "phase", "trigger", "expected", "required_evidence", "blocking",
                             "actual_result", "evidence_path", "commit"))]
# A scan that sees fewer citations than this is not looking at the files it claims to police. The two CSVs
# measured 235 citations on 2026-10-10; the floor sits low so ordinary edits can only raise it.
CITATION_FLOOR = 120
# A `path:line` pointer decays silently: measured 2026-10-10, seven of the matrix's 149 line-bearing
# citations sat one to two lines off the code they quote, and one of them (`collectors.py:267` -> 268)
# drifted because *this session* deleted a line from that file. Nothing looked wrong until someone opened
# it, so the pointer is now checked against the file, not just against its name.
POINTER = re.compile(r"([A-Za-z0-9_./\-]+\.(?:py|tsx|ts|json|yaml|yml|csv|md|js)):(\d+)(?:-(\d+))?"
                     r"(?:\s+`([^`]+)`)?")
POINTER_FLOOR = 140
CJK = re.compile(r"[㐀-鿿]")


def normalize(text: str) -> str:
    return " ".join(text.replace("“", '"').replace("”", '"').replace("'", '"').split())


def code_like(snippet: str) -> bool:
    """Only an unambiguous code span can be content-checked; a truncated Chinese sentence cannot.

    Four citations quote a sentence ending in `…` or embed CJK; demanding a match there would force the
    data to be rewritten into code it never claimed to be. Skipping them is stated, not silent: the
    `pointer_findings` return value reports how many were checked.
    """
    if not snippet or "…" in snippet or CJK.search(snippet) or "`" in snippet:
        return False
    return len(snippet.strip()) >= 12


def file_index() -> tuple[set[str], defaultdict]:
    """Tracked paths plus every other file the checkout holds, keyed also by basename.

    The walk is repo-wide rather than a list of directories I thought of: measured 2026-10-10, a
    directory-shaped index (`scripts/audit`, `apps/observer/frontend/src`, …) convicted
    `packages/client-neutral-core/scripts/operation_progress.py` -- a file that exists, in a root the pack's
    own rows cite over and over -- because the gate only added the directories it had been taught. A guard
    that reports "resolves to no file" about a file that is present is worse than no guard, so the walk
    covers the tree and prunes only what must never give a name its meaning: the runtime root, the build
    trees, and the frozen/reference copies that live inside the checkout. Pruning happens during traversal,
    because walking into `.project-local` would read another machine's toolchain before answering.
    """
    tracked = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                             cwd=ROOT, capture_output=True).stdout.split(b"\0")
    paths: set[str] = set()
    by_name: dict[str, list[str]] = defaultdict(list)

    def add(rel: str) -> None:
        if rel and rel not in paths:
            paths.add(rel)
            by_name[Path(rel).name].append(rel)

    for raw in tracked:
        add(raw.decode("utf-8", "replace"))
    for dirpath, dirnames, filenames in os.walk(ROOT):
        base = Path(dirpath)
        relative = base.relative_to(ROOT).as_posix()
        relative = "" if relative == "." else relative
        def keep(name: str) -> bool:
            # The child path is spelled from the root when there is no prefix: an earlier version required a
            # non-empty `relative`, so `.project-local` at the top of the tree matched nothing, was walked,
            # and put runtime files into an index whose whole job is to exclude them.
            child = f"{relative}/{name}" if relative else name
            return not child.startswith(EXCLUDED_INDEX_PREFIXES) and name not in PRUNED_DIRECTORY_NAMES

        dirnames[:] = [name for name in sorted(dirnames) if keep(name)]
        for name in filenames:
            add(f"{relative}/{name}" if relative else name)
    return paths, by_name


def unresolved_citations(paths: set[str], by_name: dict[str, list[str]]) -> list[str]:
    problems: list[str] = []
    for csv_path, _, _ in EXPECTED:
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for field in CITED_FIELDS & set(row):
                    for match in CITATION.finditer(row[field] or ""):
                        absent, token = match.group(1), match.group(2)
                        if absent:
                            continue
                        if token.startswith(".project-local/"):
                            continue  # runtime root, checked separately: it is not checkout-verifiable
                        if token in paths:
                            continue
                        if any((root + token) in paths for root in
                               ("apps/observer/frontend/", "packages/client-neutral-core/scripts/",
                                "services/orchestration/", "scripts/audit/")):
                            problems.append(f"{csv_path.name}:{row['id']}:{field}: shorthand {token} "
                                            "does not resolve from the repository root")
                            continue
                        problems.append(f"{csv_path.name}:{row['id']}:{field}: {token} resolves to no file")
    return problems


def rows_from_disk() -> dict[str, list[dict]]:
    tables: dict[str, list[dict]] = {}
    for csv_path, _, _ in EXPECTED:
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            tables[csv_path.name] = list(csv.DictReader(handle))
    return tables


def pointer_findings(files: dict[str, list[str]],
                     tables: dict[str, list[dict]] | None = None) -> tuple[list[str], int]:
    problems: list[str] = []
    checked = 0
    for name, rows in (tables or rows_from_disk()).items():
        for row in rows:
            for field in CITED_FIELDS & set(row):
                for match in POINTER.finditer(row[field] or ""):
                    rel, first, last, snippet = match.groups()
                    if rel.startswith(".project-local/") or rel not in files:
                        continue
                    body = files[rel]
                    low = int(first)
                    high = int(last) if last else low
                    checked += 1
                    if high > len(body) or low < 1 or low > high:
                        problems.append(f"{name}:{row['id']}:{field}: {rel}:{low}-{high} "
                                        f"lies outside 1..{len(body)}")
                        continue
                    window = normalize("\n".join(body[low - 1:high]))
                    if not window.strip():
                        problems.append(f"{name}:{row['id']}:{field}: {rel}:{low} lands on a "
                                        "blank line, so the pointer proves nothing")
                        continue
                    if snippet and code_like(snippet) and normalize(snippet)[:48] not in window:
                        problems.append(f"{name}:{row['id']}:{field}: {rel}:{low}-{high} "
                                        f"does not contain the quoted code {snippet[:48]!r}")
    return problems, checked


def as_of_commits() -> dict[str, str]:
    """The commit each archived table was certified at, read from the move record.

    A dated record can only be judged against the tree it dates. This gate used to read the checkout, so it
    demanded that two frozen CSVs track HEAD: every line added to any cited source ordered a rewrite of the
    bytes that `docs/history/archive/FROZEN-MANIFEST.json` and
    `docs/history/archive/MOVED-PATHS-20261019.json` both pin by hash (ERR-280). Checking the pointers
    against `measuredAtHead` keeps the claim readable -- the table said real things about real files --
    without making a frozen document expire.
    """
    doc = json.loads(MOVE_RECORD.read_text(encoding="utf-8"))
    return {move["to"]: move["measuredAtHead"] for move in doc["moves"]
            if move.get("measuredAtHead") and move.get("to")}


def blob_lines(commit: str, rel: str) -> list[str]:
    """The lines of one file as the recorded commit held it."""
    probe = subprocess.run(["git", "cat-file", "-e", f"{commit}:{rel}"], cwd=ROOT, capture_output=True)
    if probe.returncode != 0:
        return []
    shown = subprocess.run(["git", "-c", "core.quotePath=false", "show", f"{commit}:{rel}"],
                           cwd=ROOT, capture_output=True, check=True)
    return shown.stdout.decode("utf-8", "replace").splitlines()


def tracked_file_bodies() -> dict[str, list[str]]:
    """Line arrays for every path the tables cite, from the commit each table was certified at."""
    commits = as_of_commits()
    bodies: dict[str, list[str]] = {}
    for csv_path, _, _ in EXPECTED:
        rel_csv = csv_path.relative_to(ROOT).as_posix()
        commit = commits.get(rel_csv)
        if commit is None:
            raise AssertionError(f"{rel_csv} is frozen history but has no measuredAtHead in "
                                 f"{MOVE_RECORD.relative_to(ROOT).as_posix()} -- that record is the only "
                                 "place which can say what tree its citations were written against")
        with csv_path.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                for field in CITED_FIELDS & set(row):
                    for match in POINTER.finditer(row[field] or ""):
                        rel = match.group(1)
                        if rel in bodies or rel.startswith(".project-local/"):
                            continue
                        lines = blob_lines(commit, rel)
                        if lines:
                            bodies[rel] = lines
    return bodies


class UiV2CitationTests(unittest.TestCase):
    def test_both_csvs_keep_the_packs_own_shape(self) -> None:
        for csv_path, row_count, columns in EXPECTED:
            self.assertTrue(csv_path.is_file(), f"{csv_path} is missing")
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                reader = csv.DictReader(handle)
                rows = list(reader)
            self.assertEqual(reader.fieldnames, list(columns),
                             f"{csv_path.name} column shape changed from the pack's own header")
            self.assertEqual(len(rows), row_count,
                             f"{csv_path.name} must stay {row_count} rows, found {len(rows)}")
            # A row with an extra field is invisible above: DictReader drops the surplus under a `None` key and
            # the two assertions still hold. Measured 2026-10-10 -- a citation rewrite that put a comma into an
            # unquoted field grew B34 to 15 columns, and only `csv.reader` counts see it.
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                table = list(csv.reader(handle))
            ragged = [(row[0] if row else "?", len(row)) for row in table[1:] if len(row) != len(columns)]
            self.assertEqual(ragged, [], f"{csv_path.name} rows whose field count is not {len(columns)}: {ragged}")

    def test_every_citation_resolves_or_is_declared_absent(self) -> None:
        paths, by_name = file_index()
        problems = unresolved_citations(paths, by_name)
        self.assertEqual(problems, [], f"{len(problems)} citation(s) do not resolve: {problems[:8]}")

    def test_the_index_is_the_checkout_and_not_a_list_of_directories_i_thought_of(self) -> None:
        """A new, untracked source file in a module root must resolve, or the gate convicts real code.

        Measured the way it happened: `packages/client-neutral-core/scripts/operation_progress.py` was written
        this session, is cited by four matrix rows, and did not exist as far as a directory-list index was
        concerned. That regression is still what this test guards, but the way it was proved was wrong: the
        population was asserted to be STRICTLY BIGGER than `git ls-files`, i.e. the test passed only while some
        untracked file happened to sit in the walked tree. In a clean checkout every cited file is tracked, so
        the walk contributes nothing extra and the control can never pass -- CI read
        `2483 not greater than 2484` at 47d13507 while this box stayed green on the strength of its own residue.
        A gate whose population is the property it audits measures the machine, not the repository (ERR-142's
        rule, in a new costume). The canary is therefore PLANTED here, in a walked module root, so the same
        bytes prove the same thing on every machine.
        """
        # Bytes, decoded here:  with no encoding= hands the pipe to the console codepage, and on a
        # cp936 machine a Chinese path kills the reader thread -- the call still reports returncode 0 with a
        # None stdout, so the comparison would have read an empty tracked set and passed for the wrong reason.
        raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                             cwd=ROOT, capture_output=True).stdout
        tracked_only = {rel for rel in raw.decode("utf-8", "replace").split("\0") if rel}

        canary_dir = ROOT / "packages" / "client-neutral-core" / "scripts"
        canary = canary_dir / f"_index_walk_canary_{os.getpid()}.py"
        canary.write_text("# planted by test_ui_v2_csv_citations_resolve; removed in finally\n",
                          encoding="utf-8", newline="\n")
        try:
            paths, _ = file_index()
            self.assertNotIn("", paths, "the index accepted an empty path -- `-z` output has a trailing NUL")
            self.assertIn(canary.relative_to(ROOT).as_posix(), paths,
                          "the walk does not see an untracked file in a module root, so a citation to newly "
                          "written code would be convicted as resolving to no file")
            missing = sorted(tracked_only - paths)
            self.assertEqual([], missing[:6],
                             f"{len(missing)} tracked paths are absent from the walked index, e.g. "
                             f"{missing[:3]}; a tracked file the walk cannot see makes the whole gate's "
                             "'resolves' verdict mean less than it claims")
            self.assertIn("packages/client-neutral-core/scripts/operation_progress.py", paths,
                          "the module root this session added a producer to is not indexed")
            leaked = sorted(rel for rel in paths if rel.startswith(".project-local/"))
            self.assertEqual([], leaked[:4],
                             f"the walk reached the runtime root: {leaked[:4]}; a file that only exists on "
                             "this machine must not be what makes a citation resolve")
        finally:
            canary.unlink(missing_ok=True)
            self.assertFalse(canary.exists(), "the planted canary survived the run")

    def test_the_scan_actually_sees_the_citations_it_claims(self) -> None:
        paths, _ = file_index()
        seen = 0
        for csv_path, _, _ in EXPECTED:
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    for field in CITED_FIELDS & set(row):
                        seen += len(list(CITATION.finditer(row[field] or "")))
        self.assertGreaterEqual(seen, CITATION_FLOOR,
                                f"only {seen} citations scanned; below {CITATION_FLOOR} an empty problem "
                                "list means the regex went blind, not that the files are clean")
        # Deliberately no assertion about how many `ABSENT:` markers the data carries: a gap that was never
        # written as a path needs no marker, so demanding a count would push the file toward inventing paths
        # just to strike them out. What is enforced is the inverse -- a path that resolves nowhere must say
        # so, which is `unresolved_citations` above.

    def test_every_line_pointer_lands_on_the_code_it_quotes(self) -> None:
        """A `path:line` citation is a claim about a file, and a claim the gate can read -- as of the tree
        the table was certified against, because these two tables are frozen history (ERR-280)."""
        problems, checked = pointer_findings(tracked_file_bodies())
        self.assertGreaterEqual(checked, POINTER_FLOOR,
                                f"only {checked} line pointers examined; below {POINTER_FLOOR} the empty "
                                "problem list would mean the matcher stopped seeing citations, not that the "
                                "pointers are right")
        self.assertEqual([], problems, f"{len(problems)} line pointer(s) do not land where they claim")

    def test_the_pointer_predicate_convicts_three_ways_and_absolves_the_real_case(self) -> None:
        """Synthetic cells: past EOF, onto a blank line, onto different code. Plus the honest case.

        ``pointer_findings`` takes its table from an argument so a control can be planted without
        editing the shipped CSVs -- a guard whose only test is the real data cannot show it can fail.
        """
        snippet = "reason: 'a longer code-shaped sentence that is quoted'"
        files = {"a.py": ["first line of code here,", "second line of code,", "", "   ", snippet]}

        def tables(line: str) -> dict[str, list[dict]]:
            return {"T.csv": [{"id": "X1", "source_file_or_symbol": f"a.py:{line} `{snippet}`"}]}

        problems, checked = pointer_findings(files, tables("9"))
        self.assertEqual(1, checked)
        self.assertTrue(any("lies outside 1..5" in p for p in problems), problems)
        problems, _ = pointer_findings(files, tables("3"))
        self.assertTrue(any("blank line" in p for p in problems), problems)
        problems, _ = pointer_findings(files, tables("1"))
        self.assertTrue(any("does not contain the quoted code" in p for p in problems), problems)
        problems, _ = pointer_findings(files, tables("5"))
        self.assertEqual([], problems, "the honest pointer must be silent")
        problems, checked = pointer_findings(files, {"T.csv": [{"id": "X1",
                                                                "source_file_or_symbol": "a.py"}]})
        self.assertEqual(([], 0), (problems, checked),
                         "a citation with no line number must not inflate the census")

    def test_a_runtime_receipt_citation_is_not_invented(self) -> None:
        """`.project-local/` citations are exempt in a fresh checkout but must not be fabricated here.

        Two claims, only one of which is a repository fact, and the test used to assert them as if they were
        the same: `present > 0` required this box to still hold the round's receipts, so a runner that creates
        its own `.project-local/` (CI writes gate logs there) reached the assertion with nothing cited-present
        and failed at 47d13507 with `0 not greater than 0 : no runtime receipt is cited at all`. What is
        verifiable from the checkout is that the tables DO cite runtime receipts -- that is the counter that
        must not be decoration. Whether each cited receipt is real bytes is a fact about a machine, so it is
        judged on a machine that holds any of them, and reported as unjudgable on one that holds none
        (ERR-142's rule: answer existence from the repository, and say so when the box cannot answer).
        """
        missing: list[str] = []
        cited = 0
        present = 0
        for csv_path, _, _ in EXPECTED:
            with csv_path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    for field in CITED_FIELDS & set(row):
                        for match in CITATION.finditer(row[field] or ""):
                            token = match.group(2)
                            if not token.startswith(".project-local/"):
                                continue
                            cited += 1
                            if (ROOT / token).is_file():
                                present += 1
                            else:
                                missing.append(f"{csv_path.name}:{row['id']}:{field}: {token}")
        self.assertGreater(cited, 0,
                           "the tables cite no runtime receipt at all, so this counter is decoration — the "
                           "matcher or the fields it reads stopped reaching `.project-local/` paths")
        if present == 0:
            self.skipTest(f"this checkout holds none of the {cited} cited runtime receipts; a receipt "
                          "citation cannot be judged from bytes that are not here")
        self.assertEqual(missing, [],
                         f"a receipt cited as evidence does not exist on this machine: {missing[:6]}")

    def test_the_predicate_convicts_a_broken_path_and_forgives_a_declared_gap(self) -> None:
        # Without this, "no problems" could mean the matcher stopped recognising citations at all.
        paths, _ = file_index()
        sample = ("apps/observer/frontend/src/lib/shared_rule_adaptation.ts:5 is a claim; "
                  "ABSENT:apps/observer/frontend/src/lib/shared_rule_adaptation.ts:5 is a named gap; "
                  "services/orchestration/composition_root.py:289 is real")
        found = [(bool(match.group(1)), match.group(2)) for match in CITATION.finditer(sample)]
        self.assertEqual(len(found), 3,
                         f"the citation regex found {len(found)} of the 3 shapes it must see")
        self.assertEqual(found[0], (False, "apps/observer/frontend/src/lib/shared_rule_adaptation.ts"),
                         "a plain citation must not be read as an absence")
        self.assertEqual(found[1], (True, "apps/observer/frontend/src/lib/shared_rule_adaptation.ts"),
                         "the ABSENT prefix is not captured, so declared gaps would be convicted")
        self.assertTrue("services/orchestration/composition_root.py" in paths,
                        "the positive control path is not in the index -- the index, not the data, is broken")


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
