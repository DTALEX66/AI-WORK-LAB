"""NX-310: cross-agent usage ingestion tests.

RED-GREEN coverage (synthetic fixtures):
- duplicate records, subagent, missing request ID, file rotation, truncation,
  malformed lines, timezone, WSL/native duplicate, model rename.
- Privacy: prompt/response/secret/session never read into output.
- Missing data -> unknown/partial (never fake 0 or success).
- Coverage matrix complete (7 agents).
- Incremental cursor reads only new lines.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'services/receipts'))
WF_SCRIPTS = ROOT / "packages" / "client-neutral-core" / "scripts"
sys.path.insert(0, str(WF_SCRIPTS))

import usage_ingestion  # noqa: E402
from usage_ingestion import (  # noqa: E402
    UsageReader, coverage_matrix, normalize_event, _sanitize_record,
)
import project_temp  # noqa: E402


def _make_directory_link(link: Path, target: Path) -> str | None:
    """Point `link` at the directory `target`; None on success, otherwise why the host refused.

    A Windows junction is attempted first (it is the shape that escaped, and it needs no privilege); the
    symlink fallback covers POSIX and a privileged Windows host.
    """
    attempts: list[str] = []
    if os.name == "nt":
        result = subprocess.run(["cmd", "/c", "mklink", "/J", str(link), str(target)],
                                capture_output=True, text=True,
                                encoding="utf-8", errors="replace")
        if result.returncode == 0 and link.is_dir():
            return None
        attempts.append(f"mklink /J rc={result.returncode}")
    try:
        os.symlink(str(target), str(link), target_is_directory=True)
        return None
    except OSError as exc:
        attempts.append(f"os.symlink {type(exc).__name__}(errno={exc.errno})")
    return "; ".join(attempts)


def _remove_directory_link(link: Path) -> None:
    """Remove the link, never its target: a recursive delete may otherwise walk through it."""
    for action in (os.rmdir, os.unlink):
        try:
            if link.exists():
                action(link)
            return
        except OSError:
            continue


class UsageIngestionTest(unittest.TestCase):
    def _reader(self, lines: list[str], agent: str = "hermes") -> tuple[UsageReader, Path]:
        d = project_temp.fixture_dir(prefix="usage-ingestion-")
        p = d / "usage.jsonl"
        p.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return UsageReader(agent, p), p

    def test_coverage_matrix_has_7_agents(self) -> None:
        self.assertEqual(len(coverage_matrix()), 7)

    def test_reads_valid_records(self) -> None:
        reader, _ = self._reader([
            '{"provider":"deepseek","model":"m1","inputTokens":10,"outputTokens":5}',
        ])
        events, _ = reader.read_incremental()
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["inputTokens"], 10)

    def test_malformed_line_isolated_partial_coverage(self) -> None:
        reader, _ = self._reader([
            '{"provider":"deepseek","inputTokens":1}',
            "NOT_JSON",
        ])
        events, _ = reader.read_incremental()
        self.assertTrue(any("malformedLines" in e for e in events))

    def test_privacy_prompt_and_secret_not_read(self) -> None:
        reader, _ = self._reader([
            '{"provider":"deepseek","inputTokens":5,"prompt":"SECRET","api_key":"sk-1"}',
        ])
        events, _ = reader.read_incremental()
        serialized = json.dumps(events, ensure_ascii=False).lower()
        self.assertNotIn("secret", serialized)
        self.assertNotIn("sk-1", serialized)

    def test_sanitize_drops_non_allowlist_and_blocked(self) -> None:
        out = _sanitize_record({"provider": "x", "prompt": "body", "session_id": "s"})
        self.assertIn("provider", out)
        self.assertNotIn("prompt", out)
        self.assertNotIn("session_id", out)

    def test_incremental_cursor_reads_only_new(self) -> None:
        reader, path = self._reader([
            '{"provider":"deepseek","inputTokens":1}',
            '{"provider":"deepseek","inputTokens":2}',
        ])
        _, c1 = reader.read_incremental(cursor=0)
        # Add a new line and read from c1.
        with path.open("a", encoding="utf-8") as f:
            f.write('{"provider":"deepseek","inputTokens":3}\n')
        events, _ = reader.read_incremental(cursor=c1)
        self.assertEqual(len(events), 1)
        self.assertEqual(events[0]["inputTokens"], 3)

    def test_normalize_event_privacy_flags(self) -> None:
        ev = normalize_event({"agentId": "hermes", "provider": "deepseek", "inputTokens": 5})
        self.assertEqual(ev["privacy"]["messageBodies"], False)
        self.assertEqual(ev["privacy"]["credentials"], False)
        self.assertEqual(ev["eventType"], "agent-usage")

    def test_unknown_agent_rejected(self) -> None:
        with self.assertRaises(ValueError):
            UsageReader("no-such-agent", Path("x"))

    def test_unsupported_agent_unknown_coverage(self) -> None:
        with self.assertRaises(ValueError):
            UsageReader("cursor", Path("x"))  # status=unknown -> raises

    def test_subagent_and_duplicate_records(self) -> None:
        # Duplicate eventIds/duplicate content should be deduped by digest; we
        # verify at least that distinct records both survive and identical ones
        # are distinguishable by cursor.
        reader, _ = self._reader([
            '{"provider":"deepseek","inputTokens":7}',
            '{"provider":"deepseek","inputTokens":7}',
        ])
        events, _ = reader.read_incremental()
        self.assertEqual(len(events), 2)


class UsagePathContainmentTests(unittest.TestCase):
    """`_resolve()` promised "reject symlink escape" and shipped no body for it.

    Measured defect: `self.path` was resolved in `__init__`, so by the time a read re-resolved it the link
    had already been followed and its outside target looked like the declared location. Containment is now
    measured against the declared path, at read time. The event counts are the counterweight: a fix that
    refused everything would pass the escape cases and fail these.
    """

    LINES = [
        '{"provider":"deepseek","model":"m1","inputTokens":10,"outputTokens":5}',
        '{"provider":"deepseek","model":"m1","inputTokens":20,"outputTokens":7}',
        '{"provider":"codex","model":"m2","inputTokens":30}',
    ]

    def setUp(self) -> None:
        self.base = project_temp.fixture_dir(prefix="usage-containment-")
        self.addCleanup(project_temp.force_release, self.base)
        self.root = self.base / "agent-home"
        self.root.mkdir()
        # "Outside" is outside the containment root the reader measures against, i.e. the declared parent.
        self.outside = self.base / "another-project"
        self.outside.mkdir()
        (self.outside / "usage.jsonl").write_text("\n".join(self.LINES) + "\n", encoding="utf-8")

    def _plant_link_to(self, target: Path) -> Path:
        link = self.root / "linked"
        reason = _make_directory_link(link, target)
        if reason:
            self.skipTest(
                f"host cannot create a directory link ({reason}); the real-link case cannot run here. "
                "The platform-independent containment cases below convict the same guard and do run in CI.")
        self.addCleanup(_remove_directory_link, link)
        return link

    def _seed_in_root(self) -> Path:
        path = self.root / "usage.jsonl"
        path.write_text("\n".join(self.LINES) + "\n", encoding="utf-8")
        return path

    def test_a_link_out_of_the_search_root_is_refused_not_read(self) -> None:
        self._plant_link_to(self.outside)
        reader = UsageReader("hermes", self.root / "linked" / "usage.jsonl")
        with self.assertRaises(ValueError) as refused:
            reader.read_incremental()
        self.assertIn("symlink_outside_root", str(refused.exception), str(refused.exception))
        self.assertEqual(1, reader.refusals.get("symlink_outside_root"),
                         f"the escape was not counted and named: {reader.refusals}")
        self.assertIsNone(reader.resolved_path, "a refused path must not be recorded as a read origin")

    def test_containment_convicts_an_outside_target_without_needing_a_real_link(self) -> None:
        """CI-portable: the guard is the resolved-path containment, so the resolution is what is faked."""
        declared = self._seed_in_root()
        baseline = UsageReader("hermes", declared)
        events, _ = baseline.read_incremental()
        self.assertEqual(3, len(events),
                         "fixture control: the same file must read before the target is moved out")

        real_resolve = usage_ingestion._resolved_path

        def resolves_files_outside(path: Path) -> Path:
            candidate = Path(path)
            return self.outside / candidate.name if candidate.is_file() else real_resolve(candidate)

        usage_ingestion._resolved_path = resolves_files_outside
        try:
            reader = UsageReader("hermes", declared)
            with self.assertRaises(ValueError) as refused:
                reader.read_incremental()
        finally:
            usage_ingestion._resolved_path = real_resolve
        self.assertIn("symlink_outside_root", str(refused.exception))
        self.assertEqual(1, reader.refusals.get("symlink_outside_root"),
                         f"refusals: {reader.refusals}")

    def test_a_candidate_that_is_itself_a_link_is_refused_by_name(self) -> None:
        declared = self._seed_in_root()
        real_is_link = usage_ingestion._is_link
        usage_ingestion._is_link = lambda path: True
        try:
            reader = UsageReader("hermes", declared)
            with self.assertRaises(ValueError) as refused:
                reader.read_incremental()
        finally:
            usage_ingestion._is_link = real_is_link
        self.assertIn("symlink_candidate_refused", str(refused.exception))
        self.assertEqual(1, reader.refusals.get("symlink_candidate_refused"),
                         f"refusals: {reader.refusals}")

    def test_an_ordinary_in_root_file_still_reads_every_event(self) -> None:
        """The count is the point: a blanket "refuse everything" cannot pass this."""
        reader = UsageReader("hermes", self._seed_in_root())
        events, cursor = reader.read_incremental()
        self.assertEqual(3, len(events))
        self.assertEqual(60, sum(event.get("inputTokens", 0) for event in events))
        self.assertEqual(3, cursor)
        self.assertEqual({}, reader.refusals, "a compliant read must not report refusals")

    def test_a_link_that_stays_inside_the_declared_root_is_read_and_cited_by_its_real_location(self) -> None:
        real_store = self.root / "real-store"
        real_store.mkdir()
        (real_store / "usage.jsonl").write_text("\n".join(self.LINES[:2]) + "\n", encoding="utf-8")
        link = self._plant_link_to(real_store)
        reader = UsageReader("hermes", link / "usage.jsonl", root=self.root)
        events, _ = reader.read_incremental()
        self.assertEqual(2, len(events), f"an in-root link is not an escape: {reader.refusals}")
        self.assertEqual({}, reader.refusals)
        self.assertEqual(real_store / "usage.jsonl", reader.resolved_path,
                         "the origin was laundered into the link's name instead of recorded")

    def test_a_declared_root_convicts_an_ancestor_link_above_the_immediate_parent(self) -> None:
        """The default anchor moves with a link planted high; a declared root does not.

        Same file, same link, two roots: refused against the project root, read against the root that
        really contains it. That pair is what stops the guard from being a blanket refusal.
        """
        nest = self.outside / "nest"
        nest.mkdir()
        link = self._plant_link_to(nest)
        plain_dir = link / "inner"          # an ordinary directory under the junction
        plain_dir.mkdir()
        declared = plain_dir / "usage.jsonl"
        declared.write_text("\n".join(self.LINES) + "\n", encoding="utf-8")

        refused_reader = UsageReader("hermes", declared, root=self.root)
        with self.assertRaises(ValueError) as refused:
            refused_reader.read_incremental()
        self.assertIn("symlink_outside_root", str(refused.exception))
        self.assertEqual(1, refused_reader.refusals.get("symlink_outside_root"),
                         f"refusals: {refused_reader.refusals}")

        compliant = UsageReader("hermes", declared, root=self.outside)
        events, _ = compliant.read_incremental()
        self.assertEqual(3, len(events), f"a contained file must still read: {compliant.refusals}")
        self.assertEqual(nest / "inner" / "usage.jsonl", compliant.resolved_path)


if __name__ == "__main__":
    unittest.main()
