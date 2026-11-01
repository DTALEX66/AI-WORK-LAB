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
    """The entry quoted 7108 rows once; if a register moves and the prose does not, this is red."""
    entry = _doctored(tmp_path, lambda text: text.replace("source_rows_total = 7108",
                                                          "source_rows_total = 7107"))
    report = _report(_run("--check", "--entry", str(entry)))
    stale = [f for f in report["findings"] if f.startswith("FIGURE_STALE")]
    assert stale == ["FIGURE_STALE source_rows_total 文档=7107 寄存器=7108"], report["findings"]


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
