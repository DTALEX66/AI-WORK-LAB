"""Gate: a reader-facing document must not tell a reader to operate at a path that no longer exists.

U02's read-only path convergence was recorded as done for README and PROJECT_POSITIONING while five
documents under `docs/current/` still said "run from `10-workflow/workflow-assistance`" — a directory
the 2026-09 convergence stopped tracking. One of them paired that instruction with
`python services/authority/machine_identity.py`, a repository-root path, so the published recipe
could not run as written at all.

The rule is stated as a shape, not a blocklist of two files: a superseded path may appear in a
reader-facing document only on a line that also says it is superseded. That keeps honest history
("2026-09 收敛前为 …") and rejects the imperative form ("从 X 运行：").
"""
from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
READER_FACING = re.compile(r"^(README\.md|docs/current/|docs/decisions/|config/|apps/observer/README\.md)")
# A filename ending in a date marks a frozen record of what was true then — the project's own
# precedence rule calls historical records non-normative — so `…/SUBTRACTION_AUDIT_2026-08-18.md`
# naming the pre-convergence paths is correct, and rewriting it would be the falsification.
# Undated documents in the same directory (the global execution standard) stay in scope.
DATED_RECORD = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}\.md$")
SUPERSEDED = ("10-workflow/workflow-assistance", "30-observer/work-lab-observer")
HISTORY_MARKERS = ("收敛", "前为", "历史", "不再", "SUPERSEDED", "superseded", "no longer",
                   "按它执行会找不到路径", "已废弃", "旧文档", "已不再被跟踪")
# Prose wraps, so a marker legitimately lands on the next line or two: the deepseek guide's
# sentence says "…已在 2026-09 目录收敛中拆分" with the superseded path at the end of the line above.
LOOKAHEAD_LINES = 2


def reader_facing_files() -> list[str]:
    listing = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True)
    paths = [p.decode("utf-8", "replace") for p in listing.stdout.split(b"\x00") if p]
    return sorted(p for p in paths
                  if READER_FACING.match(p) and not DATED_RECORD.search("/" + p))


def offending(text: str) -> list[str]:
    lines = text.splitlines()
    out = []
    for number, line in enumerate(lines, 1):
        if not any(token in line for token in SUPERSEDED):
            continue
        window = "\n".join(lines[number - 1:number - 1 + 1 + LOOKAHEAD_LINES])
        if not any(marker in window for marker in HISTORY_MARKERS):
            out.append(f"{number}: {line.strip()[:110]}")
    return out


class SupersededPathInstructionGate(unittest.TestCase):
    def test_the_rule_has_files_to_watch_at_all(self) -> None:
        # A vacuous pass would look identical to convergence being finished.
        self.assertGreaterEqual(len(reader_facing_files()), 40)
        self.assertTrue(any(p.startswith("docs/current/") for p in reader_facing_files()))

    def test_no_reader_facing_document_instructs_work_at_a_superseded_path(self) -> None:
        offenders = {}
        for path in reader_facing_files():
            found = offending((ROOT / path).read_text(encoding="utf-8", errors="replace"))
            if found:
                offenders[path] = found
        self.assertEqual({}, offenders,
                         "reader-facing documents still issue live instructions at a path this "
                         "repository stopped tracking")

    def test_the_detector_fires_on_the_shape_it_exists_to_catch(self) -> None:
        bad = "从 `10-workflow/workflow-assistance` 运行：\n"
        self.assertEqual(1, len(offending(bad)))
        good = "由 Workflow 模块 `packages/client-neutral-core`（2026-09 收敛前为 " \
               "`10-workflow/workflow-assistance`）管理\n"
        self.assertEqual([], offending(good))
        other = "30-observer/work-lab-observer 已不再被跟踪\n"
        self.assertEqual([], offending(other))

    def test_the_re_pointed_targets_exist_in_the_tree(self) -> None:
        for rel in ("config/codex-enhancement-boundary.json",
                    "services/authority/machine_identity.py",
                    "integrations/executors/codex/sync_codex_global_assets.py",
                    "packages/client-neutral-core/workflow-manifest.yaml",
                    "AGENTS.md"):
            self.assertTrue((ROOT / rel).exists(), rel)

    def test_dated_records_are_out_of_scope_and_that_is_load_bearing(self) -> None:
        # If the exclusion did nothing, this test would pass for the wrong reason; if someone
        # widened it, a live instruction in an undated doc would start passing too.
        frozen = "docs/decisions/SUBTRACTION_AUDIT_2026-08-18.md"
        self.assertTrue((ROOT / frozen).is_file(), frozen)
        self.assertIn("10-workflow/workflow-assistance", (ROOT / frozen).read_text(
            encoding="utf-8", errors="replace"))
        self.assertNotIn(frozen, reader_facing_files())
        undated = [p for p in reader_facing_files() if p.startswith("docs/decisions/")]
        self.assertTrue(undated, "docs/decisions contributes nothing, so the exclusion is untested")
        for path in undated:
            self.assertFalse(DATED_RECORD.search("/" + path), path)

    def test_agents_md_keeps_its_historical_note_marked(self) -> None:
        # The rule's own window logic is reused rather than re-implemented per file: AGENTS.md wraps
        # "…split out at the 2026-09" with "no longer tracked" on the following line, and a
        # single-line check would flag a sentence that is already explicit.
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("10-workflow/workflow-assistance", text)
        self.assertEqual([], offending(text))


if __name__ == "__main__":
    unittest.main(verbosity=2)
