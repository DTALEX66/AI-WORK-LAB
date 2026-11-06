# SPDX-License-Identifier: MIT
"""V37: the entry's receipt-anchor line is rebuilt from the registers, and a duplicate is refused.

This file is machine-bound, and says so in the words the clone scan reads: the claim is about a line
derived from the run receipt under `.project-local/audit/20261031-fullclosure/`, and that directory
is a run product -- Git does not track it, so a fresh checkout has nothing to derive from. The
honest alternatives were rejected: leaving the node in ``test_v29`` makes a clone fail for a reason
that is not a defect (measured: the clone's own suite run reported exactly this one failure), and
turning the assertion into "either it rewrites or there is nothing to rewrite" would dilute the
strong claim into an either/or for the sake of a green. So the strong claim stays here, where the
artifact exists, and ``test_v23``'s partition names it.

What is verified: the line that used to carry three hand-typed values -- commit, suite tally, file
count -- is rewritten from the registers, one line is required, a hand-typed placeholder does not
survive, the check passes afterwards, and a second such line is refused rather than averaged.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[2]
CHECKER = TARGET_ROOT / "scripts" / "check_project_current.py"
ENTRY = TARGET_ROOT / "PROJECT_CURRENT.md"


def _run(*argv: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-B", "-X", "utf8", str(CHECKER), *argv],
                          cwd=str(TARGET_ROOT), capture_output=True, text=True,
                          encoding="utf-8", errors="replace", timeout=300)


def _report(result: subprocess.CompletedProcess) -> dict:
    assert result.stdout.strip(), (result.returncode, result.stderr[-800:])
    return json.loads(result.stdout.strip())


def _receipt_is_readable_here() -> bool:
    """State the prerequisite as a check, so an unmet machine says so instead of passing quietly.

    Mirrors what ``check_project_current.receipt_line`` needs: exactly one receipt named by the
    closure register, that file present on this machine, and an audited commit of usable length.
    """
    import csv
    with (TARGET_ROOT / "migration/audit-item-closure.csv").open(
            encoding="utf-8-sig", newline="") as handle:
        names = {row["运行收据"] for row in csv.DictReader(handle)}
    names = [name for name in names if name and not name.startswith("UNMEASURED")]
    if len(names) != 1:
        return False
    if not (TARGET_ROOT / ".project-local/audit/20261031-fullclosure" / names[0]).is_file():
        return False
    audited = json.loads((TARGET_ROOT / "docs/AUDIT-STATE.json")
                         .read_text(encoding="utf-8-sig")).get("audited_head_sha", "")
    return len(audited) >= 12


def test_the_receipt_anchor_line_is_derived_and_a_second_one_is_refused(tmp_path):
    """The line that names the measured tree is derived, and duplicates are a refusal.

    Requires the archived receipt this machine's register names -- see the module docstring for why
    that makes the claim machine-bound rather than a clone-safe one.
    """
    assert _receipt_is_readable_here(), (
        "本格的先决条件不成立：登记表点名的运行收据不在本机，任何结论都无从现算")

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
