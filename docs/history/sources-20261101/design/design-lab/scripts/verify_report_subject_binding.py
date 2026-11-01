#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Every tracked projection that claims a subject must name a commit, or say why it cannot.

Found while fixing something else. `verify_supply_chain.py` stores `subject_sha` from
`git("rev-parse HEAD")` -- one argv element, which git rejects, so the helper returned empty
stdout and the field was `""`. Scanning every tracked projection showed **nine** records in the
same state, and nothing checked it: a provenance field that names nothing reads exactly like a
provenance field nobody filled in yet, and consumers (`deepseek_final_closeout.py`, the
`#<check>` evidence pointers in the ledger) cite these files as if they were bound to a head.

Two rules, both about shape rather than trust:

1. A tracked JSON under `reports/current/` or `design-lab/config/` carrying `subject_sha` or
   `subjectSha` must hold a full 40-hex commit, or appear in
   `design-lab/config/report-subject-debt.json` with the script that writes it and the date the
   gap was declared. The register only shrinks: a record that becomes bound while still listed is
   itself a finding, so the debt cannot silently grow back.
2. The call shape that caused all of this is refused outright -- a `git(...)` helper invoked with
   a single string containing a space. Splitting inside the helper is not the fix: repository
   paths on this machine contain spaces, so an argument may legitimately hold one; a *subcommand*
   never does.

State on 2026-10-09: all nine joined calls are repaired, so `callSites` is empty and the register
carries only the data debt. Nine records still hold `subject_sha: ""` and are deliberately left
that way -- re-running any of their generators rewrites the whole record, and each of the nine is
cited as evidence by a task that the machine ledger already marks DONE (`task_key` and status are
recorded per row, read from `reports/current/DEEPSEEK-AUTHORITY-LEDGER-2026-09-14.json`). Closing
a row is therefore an explicit decision to re-base that task's evidence, not a `python scripts/...`
away, and each row states that. A row may not keep describing a defect its producer no longer has:
`producerFixedOn` is checked against the source as it stands.
"""
from __future__ import annotations

import argparse
import ast
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SCHEMA_VERSION = "design-lab/report-subject-debt/v1"
SUBJECT_KEYS = ("subject_sha", "subjectSha")
SCOPES = ("reports/current", "design-lab/config")
GIT_ARG_SCANS = ("scripts", "design-lab/scripts")
SHA40 = re.compile(r"^[0-9a-f]{40}$")
MAX_BYTES = 3_000_000


def subject_records(root: Path = REPO) -> list[tuple[str, str, object]]:
    """(relpath, key, value) for every tracked-scope JSON that carries a subject field."""
    found: list[tuple[str, str, object]] = []
    for scope in SCOPES:
        directory = root / scope
        for path in sorted(directory.glob("*.json")) if directory.is_dir() else []:
            try:
                if path.stat().st_size > MAX_BYTES:
                    continue
                document = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                continue
            if not isinstance(document, dict):
                continue
            for key in SUBJECT_KEYS:
                if key in document:
                    rel = path.relative_to(root).as_posix()
                    found.append((rel, key, document[key]))
    return found


def joined_git_call_sites(root: Path = REPO) -> list[tuple[str, str, int]]:
    """(script relpath, joined argument, line) for every `git("sub command")` call.

    Parsed from the AST, not from text: the shape is the bug, and a text rule would be satisfied
    by a reformat. Only calls whose function name is exactly `git` are considered, because that is
    the helper these generators share.
    """
    sites: list[tuple[str, str, int]] = []
    for directory in GIT_ARG_SCANS:
        base = root / directory
        if not base.is_dir():
            continue
        for path in sorted(base.glob("*.py")):
            try:
                tree = ast.parse(path.read_text(encoding="utf-8"))
            except (OSError, SyntaxError, UnicodeDecodeError):
                continue
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Name):
                    continue
                if node.func.id != "git":
                    continue
                for argument in node.args:
                    if (isinstance(argument, ast.Constant) and isinstance(argument.value, str)
                            and " " in argument.value):
                        sites.append((path.relative_to(root).as_posix(), argument.value,
                                      node.lineno))
    return sites


def describe(site: tuple[str, str, int]) -> str:
    return f"{site[0]}:{site[2]} git({site[1]!r})"


def debt_path(root: Path) -> Path:
    return root / "design-lab" / "config" / "report-subject-debt.json"


def read_register(root: Path = REPO) -> tuple[dict[str, dict], dict[str, dict], list[str]]:
    """Parse the debt register once: (record rows by `path#key`, call rows by script, findings).

    One read, not two. Reading it twice made a single unreadable file produce the same finding
    twice, which is the kind of duplicate a consumer learns to ignore -- and a register nobody
    trusts is a register that silently grows.
    """
    path = debt_path(root)
    if not path.is_file():
        # A repository with no debt at all has no register. Absent is not an error here: the
        # findings that matter (REPORT-SUBJECT-UNBOUND) come from the records themselves, so
        # demanding a file would only add a second complaint about one defect.
        return {}, {}, []
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return {}, {}, [f"REPORT-DEBT-UNREADABLE {path.name}: {exc}"]
    problems: list[str] = []
    if document.get("schemaVersion") != SCHEMA_VERSION:
        problems.append(f"REPORT-DEBT-SCHEMA says {document.get('schemaVersion')!r}, expected "
                        f"{SCHEMA_VERSION!r}")

    rows: dict[str, dict] = {}
    for row in document.get("records") or []:
        rel = str(row.get("path") or "")
        key = str(row.get("key") or "")
        if not rel or not key:
            problems.append("REPORT-DEBT-ROW-INCOMPLETE a row needs both `path` and `key`; a "
                            "record may bind its subject under one spelling and leave the other "
                            "empty, which is two facts, not one")
            continue
        ident = f"{rel}#{key}"
        if ident in rows:
            problems.append(f"REPORT-DEBT-DUPLICATE {ident} is declared twice")
            continue
        for field in ("producer", "reason", "declaredOn", "whatWouldCloseIt"):
            if not str(row.get(field) or "").strip():
                problems.append(f"REPORT-DEBT-ROW-INCOMPLETE {ident} has no {field}; a debt "
                                "without a producer, a reason and the action that would close it "
                                "is not a declaration")
        if "producerFixedOn" not in row:
            problems.append(f"REPORT-DEBT-ROW-INCOMPLETE {ident} does not say whether its "
                            "producer still has the joined call (`producerFixedOn`, null while it "
                            "does) -- without that, a row keeps blaming a defect that was fixed")
        rows[ident] = row

    call_rows: dict[str, dict] = {}
    for row in document.get("callSites") or []:
        script = str(row.get("script") or "")
        command = str(row.get("joinedArgument") or "")
        if not script or not command:
            problems.append("CALL-DEBT-ROW-INCOMPLETE a row needs both `script` and "
                            "`joinedArgument`")
            continue
        if script in call_rows:
            problems.append(f"CALL-DEBT-DUPLICATE {script} is declared twice")
            continue
        for field in ("reason", "declaredOn", "writesRecord"):
            if not str(row.get(field) or "").strip():
                problems.append(f"CALL-DEBT-ROW-INCOMPLETE {script} has no {field}; an undeclared "
                                "shape is a defect, a declared one is a booked debt")
        if not (root / script).is_file():
            problems.append(f"CALL-DEBT-PRODUCER-MISSING {script} no longer exists; delete the "
                            "row -- either the file is gone or the call was fixed")
        call_rows[script] = row
    return rows, call_rows, problems


def check(root: Path = REPO) -> tuple[list[str], int, int, int]:
    problems: list[str] = []
    records = subject_records(root)
    rows, call_rows, register_problems = read_register(root)
    problems += register_problems
    declared = 0
    # Computed first: the record rows are graded against the producer source as it stands now,
    # so a row cannot describe a defect that has already been repaired.
    sites = joined_git_call_sites(root)
    seen_scripts = {script for script, _command, _line in sites}

    # A record can carry both spellings; a consumer reading one gets whatever that key holds.
    by_record: dict[str, dict[str, object]] = {}
    for rel, key, value in records:
        by_record.setdefault(rel, {})[key] = value

    for rel, key, value in records:
        text = "" if value is None else str(value)
        ident = f"{rel}#{key}"
        row = rows.get(ident)
        sibling = next((str(other) for other_key, other in by_record[rel].items()
                        if other_key != key and SHA40.match(str(other or ""))), "")
        if SHA40.match(text):
            if row is not None:
                problems.append(f"REPORT-DEBT-CLOSED-NOT-REMOVED {ident} now binds "
                                f"{text[:12]}... but is still listed as unbound; the register "
                                "only shrinks when the debt is really gone")
            continue
        if row is None:
            extra = (f" while the same record binds {sibling[:12]}... under the other spelling, so "
                     "anything reading this key gets nothing" if sibling else "")
            problems.append(f"REPORT-SUBJECT-UNBOUND {rel} records {key}={text!r}, which names no "
                            f"commit{extra}, and the field is not declared in "
                            "design-lab/config/report-subject-debt.json")
            continue
        declared += 1
        if text:
            problems.append(f"REPORT-SUBJECT-SHAPE {rel} records {key}={text[:20]!r}, which is "
                            "neither empty nor a 40-hex commit")
        producer = str(row.get("producer") or "")
        if producer and not (root / producer).is_file():
            problems.append(f"REPORT-DEBT-PRODUCER-MISSING {ident} names {producer}, which no "
                            "longer exists -- the writer moved or died, so re-derive the row")
        if not (root / rel).is_file():
            problems.append(f"REPORT-DEBT-ORPHAN {ident} is declared but the record is gone")
        if producer and "producerFixedOn" in row:
            still_joined = producer in seen_scripts
            fixed_on = str(row.get("producerFixedOn") or "")
            if still_joined and fixed_on:
                problems.append(f"RECORD-PRODUCER-STILL-BROKEN {ident} claims the joined call was "
                                f"fixed on {fixed_on} but {producer} still contains it")
            if not still_joined and not fixed_on:
                problems.append(f"RECORD-DEFECT-STILL-CLAIMED {ident} still describes {producer} "
                                "as carrying the joined call, which it no longer does: say when "
                                "it was fixed, and keep the record row for the field that is "
                                "still unbound")

    # Both directions: a row for a field that no longer exists is a live entry in a register
    # that is supposed to shrink only by fixing the thing it names.
    scanned = {f"{rel}#{key}" for rel, key, _value in records}
    for ident in sorted(set(rows) - scanned):
        problems.append(f"REPORT-DEBT-UNSCANNED {ident} is declared but no such subject field is "
                        "read anywhere in scope -- the record moved, the key changed spelling, "
                        "or the row was typed for a file that never had one")

    for script, command, line in sites:
        row = call_rows.get(script)
        if row is None:
            problems.append(f"GIT-ARG-JOINED {script}:{line} calls git({command!r}) as one "
                            "argument, so git rejects it and the value the generator stores is "
                            "empty. Pass them separately -- a joined subcommand is never a "
                            "legitimate single argument, so there is nothing to declare here")
            continue
        if str(row.get("joinedArgument")) != command:
            problems.append(f"CALL-DEBT-ARG-MISMATCH {script} is declared for "
                            f"{row.get('joinedArgument')!r} and actually calls {command!r}")

    for script in sorted(set(call_rows) - seen_scripts):
        problems.append(f"CALL-DEBT-CLOSED-NOT-REMOVED {script} no longer contains a joined git "
                        "call, so its row must be deleted together with the record it regenerates")
    return problems, len(records), declared, len(seen_scripts)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--list-debt", action="store_true",
                        help="print the declared rows and the still-unbound records")
    args = parser.parse_args(argv)
    problems, records, declared, joined = check()
    for problem in problems:
        print("VERIFY_REPORT_SUBJECT_BINDING=FAIL " + problem)
    if args.list_debt:
        for rel, key, value in subject_records():
            if not SHA40.match("" if value is None else str(value)):
                print(f"  UNBOUND {rel} {key}")
        record_rows, call_row_map, _problems = read_register()
        for rel, row in sorted(record_rows.items()):
            print(f"  DECLARED-RECORD {rel} producer={row.get('producer')} "
                  f"declaredOn={row.get('declaredOn')}")
        for script, row in sorted(call_row_map.items()):
            print(f"  DECLARED-CALLSITE {script} writes={row.get('writesRecord')} "
                  f"declaredOn={row.get('declaredOn')}")
    verdict = "OK" if not problems else "FAIL"
    print(f"VERIFY_REPORT_SUBJECT_BINDING={verdict} records={records} "
          f"bound={records - declared} declared_unbound={declared} "
          f"joined_call_sites={joined} findings={len(problems)}")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
