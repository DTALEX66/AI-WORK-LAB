"""Gate: the default agent material says what this project is now, and every path it cites is real.

Why this exists (WUI-16): `.agents/skills/work-lab-workflow/SKILL.md` is the file a new session reads by
default. It was generated 2026-09-xx and still described the pre-UI-priority state -- `services/ + packages/
+ integrations/` as the owner (the machine authority says exactly two module roots), `E:\\` as the only
forbidden drive (both E: and F: are), and nothing about client-neutral positioning, the three-project
boundary, desktop-only scope, or the truth discipline that the whole project rests on. A stale default
document is worse than an absent one: every new session inherits its wrongness without noticing.

The two clauses the taskpack asks for are checked as behaviour, not as prose review:
  * "regenerate from current source, two runs with no unexplained drift" -> the generator is run twice here
    and the emitted bytes must be identical, and the header's content hash must equal the hash of the body
    under it;
  * "traceability gaps shown" -> every repository-relative path the skill cites must be a tracked file, so a
    reference that no longer resolves fails the gate instead of silently misleading a reader.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import hashlib
import importlib.util
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "projections" / "agents" / "source" / "work-lab-workflow" / "SKILL.md"
PROJECTION = ROOT / ".agents" / "skills" / "work-lab-workflow" / "SKILL.md"
GENERATOR = ROOT / "projections" / "agents" / "generate.py"

# What a new session must be told, verbatim enough that a rewrite cannot quietly drop the meaning.
REQUIRED_MARKERS = (
    "client-neutral",
    "ArcheAxis-Knowledge-OS",
    "DESIGN-LAB",
    "packages/client-neutral-core",
    "apps/observer",
    "read-only",
    "Mobile is out of",
    "Unknown is never padded to zero",
    "turn_end",
    "?palette=master",
    "python services/orchestration/run_quality_gate.py verify",
)
FORBIDDEN_DRIVES = ("E:\\", "F:\\")
SIZE_BUDGET_BYTES = 10240  # AGENTS.md dimension 4: skills stay under 10KB each, loaded on demand

# A cited path: something that looks like a repo-relative file, in prose or a fence.
CITED = re.compile(r"`([A-Za-z0-9_.\-/]+\.[A-Za-z0-9]{1,6})`")


def load_generator():
    spec = importlib.util.spec_from_file_location("agents_projection_generate", GENERATOR)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tracked_files() -> set[str]:
    raw = subprocess.run(["git", "-c", "core.quotePath=false", "ls-files", "-z"],
                         cwd=ROOT, capture_output=True).stdout.split(b"\0")
    return {name.decode("utf-8", "replace") for name in raw if name}


def repository_bytes(rel: str) -> bytes | None:
    """The bytes git holds for `rel`, or None when it is not tracked.

    `.gitattributes` sets `* text=auto`, so a Windows checkout of this generated projection is CRLF
    while the generator emits LF. Comparing the checkout against the generator makes the gate answer
    "drifted" on Windows and "clean" on Linux for one unchanged file. The index is the repository's own
    answer and is identical on every platform -- the same rule the material catalog now uses (ERR-275).
    """
    proc = subprocess.run(["git", "show", ":" + rel], cwd=ROOT, capture_output=True, check=False)
    if proc.returncode != 0:
        return None
    return proc.stdout


class AgentDefaultMaterialTests(unittest.TestCase):
    def test_the_projection_exists_and_is_marked_generated(self) -> None:
        self.assertTrue(PROJECTION.is_file(), f"{PROJECTION} is missing -- run projections/agents/generate.py")
        text = PROJECTION.read_text(encoding="utf-8")
        self.assertIn("GENERATED — DO NOT EDIT", text,
                      "the projection lost its generated marker, so an editor will hand-fix derived bytes")

    def test_two_generations_produce_the_same_bytes(self) -> None:
        # The committed projection is read from the index: on Windows the working copy is CRLF while
        # the generator emits LF, so a working-tree read would report drift for an unchanged file.
        before = repository_bytes(PROJECTION.relative_to(ROOT).as_posix())
        assert before is not None, f"{PROJECTION} is not tracked"
        generator = load_generator()
        try:
            generator.generate()
            first = PROJECTION.read_bytes()
            generator.generate()
            second = PROJECTION.read_bytes()
        finally:
            PROJECTION.write_bytes(before)
        self.assertEqual(first, second,
                         "the generator drifted between two runs over the same source -- output is not "
                         "deterministic, so CI's delete-and-regenerate check cannot mean anything")
        self.assertEqual(second, before,
                         "the committed projection is not what the current source generates: it was edited "
                         "by hand or the source moved without regenerating")

    def test_the_content_hash_header_describes_the_body_under_it(self) -> None:
        text = PROJECTION.read_text(encoding="utf-8")
        lines = text.split("\n")
        header_lines = 0
        while header_lines < len(lines) and lines[header_lines].startswith("<!--"):
            header_lines += 1
        self.assertGreater(header_lines, 0, "no generated-header lines at the top of the projection")
        body = "\n".join(lines[header_lines:])
        self.assertEqual(body, SOURCE.read_text(encoding="utf-8"),
                         "the projection body is not the source body byte for byte")
        declared = re.search(r"content_hash: sha256:([0-9a-f]{64})", text)
        self.assertIsNotNone(declared, "no content_hash line to verify against")
        self.assertEqual(declared.group(1), hashlib.sha256(body.encode("utf-8")).hexdigest(),
                         "the recorded content hash does not match the bytes it sits above")

    def test_the_default_material_states_the_current_positioning(self) -> None:
        text = SOURCE.read_text(encoding="utf-8")
        missing = [marker for marker in REQUIRED_MARKERS if marker not in text]
        self.assertEqual(missing, [],
                         f"the default agent skill no longer says: {missing} -- a new session would inherit "
                         "an out-of-date description of what this product is")
        for drive in FORBIDDEN_DRIVES:
            self.assertIn(drive, text,
                          f"{drive} is a forbidden external root in project-data-boundary.json; naming only "
                          "one drive teaches the next session to walk into the other")

    def test_every_cited_path_resolves_in_the_repository(self) -> None:
        tracked = tracked_files()
        cited = {match.group(1) for match in CITED.finditer(SOURCE.read_text(encoding="utf-8"))}
        self.assertGreaterEqual(len(cited), 5,
                                f"the scan found only {len(cited)} citations; below 5 it is probably blind")
        unresolved = sorted(path for path in cited if path not in tracked)
        self.assertEqual(unresolved, [],
                         f"the skill cites paths that are not tracked files: {unresolved} -- a traceability "
                         "gap must be written as a gap, not as a reference")

    def test_the_skill_stays_within_its_load_budget(self) -> None:
        size = SOURCE.stat().st_size
        self.assertLess(size, SIZE_BUDGET_BYTES,
                        f"{SOURCE} is {size} bytes, over the {SIZE_BUDGET_BYTES} budget every managed skill "
                        "must stay under so guidance loads on demand instead of blocking startup")


TIMESTAMP_LINE = re.compile(r'^\s*("generated_at"|Generated at: `)')


def generate_current_state(work: Path, tag: str) -> tuple[list[str], list[str]]:
    """Run the current-state generator into temp paths and return (json lines, markdown lines)."""
    json_out = work / f"{tag}.json"
    md_out = work / f"{tag}.md"
    result = subprocess.run(
        [sys.executable, "scripts/ci/generate_current_state.py",
         "--json-out", str(json_out), "--markdown-out", str(md_out)],
        cwd=ROOT, capture_output=True, check=False)
    assert result.returncode == 0, (
        f"CURRENT_STATE generator exited {result.returncode}: "
        f"{result.stdout.decode('utf-8', 'replace')[-400:]}")
    return json_out.read_text(encoding="utf-8").splitlines(), md_out.read_text(encoding="utf-8").splitlines()


class DerivedProjectionDriftTests(unittest.TestCase):
    """The taskpack's clause is "two runs, no UNEXPLAINED drift", not "two runs, no difference".

    So the test names the one field that is allowed to move and convicts everything else. A generator whose
    output silently changes in a second place would otherwise pass any equality check by being excluded.
    """

    def test_the_current_state_projection_moves_only_its_timestamp(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            work = Path(tmp)
            first_json, first_md = generate_current_state(work, "run1")
            second_json, second_md = generate_current_state(work, "run2")
            self.assertEqual(len(first_json), len(second_json),
                             "the JSON projection changed length between two runs over the same tree")
            self.assertEqual(len(first_md), len(second_md),
                             "the Markdown projection changed length between two runs over the same tree")
            moved = [(number, line, other)
                     for number, (line, other) in enumerate(zip(first_json, second_json)) if line != other]
            moved += [(number, line, other)
                      for number, (line, other) in enumerate(zip(first_md, second_md)) if line != other]
            self.assertEqual(len(moved), 2,
                             "more than one line moved between two generations -- the second one is a real "
                             f"drift, not the clock: {[line[:120] for _, line, _ in moved[:6]]}")
            for _, before, after in moved:
                self.assertTrue(TIMESTAMP_LINE.match(before),
                                f"a non-timestamp line drifts: {before[:160]}")
                self.assertNotEqual(before, after)

    def test_the_context_pack_moves_only_its_generation_stamp_between_renders(self) -> None:
        """Byte equality across two renders was FALSE, and the batch caught it.

        My first version of this case asserted the two renders were identical. It passed on its own because
        both renders fell inside the same second, and failed inside the governance batch two minutes later:
        the pack prints `- Generated UTC: <timestamp>`, so two renders differ by construction. A check that
        passes by timing luck is worse than no check, because it certifies stability it never tested. The
        pack also carries Branch and HEAD, which must NOT move between two renders of the same working state
        -- so the honest assertion names the one line that may move and convicts every other difference.
        """
        def render() -> list[str]:
            result = subprocess.run(
                [sys.executable, "packages/client-neutral-core/scripts/build_context_pack.py",
                 "--project", ".", "--stdout"],
                cwd=ROOT, capture_output=True, check=False)
            self.assertEqual(result.returncode, 0,
                             f"context pack exited {result.returncode}: "
                             f"{result.stderr.decode('utf-8', 'replace')[-300:]}")
            return result.stdout.decode("utf-8", "replace").splitlines()

        first, second = render(), render()
        self.assertGreater(len(first), 20, "the pack rendered nearly empty; equality would prove nothing")
        stamp_first = [line for line in first if line.startswith("- Generated UTC:")]
        stamp_second = [line for line in second if line.startswith("- Generated UTC:")]
        self.assertEqual(len(stamp_first), 1,
                         f"the pack has {len(stamp_first)} generation stamps; the test's exclusion rule "
                         "assumes exactly one and would silently excuse anything else")
        self.assertEqual(len(stamp_second), 1)
        # Compare with the stamp removed rather than requiring it to have moved: two renders inside the
        # same second are a legitimate outcome, and asserting "it must differ" would make the case flaky
        # in the harmless direction. What must never differ is everything else.
        body_first = [line for line in first if not line.startswith("- Generated UTC:")]
        body_second = [line for line in second if not line.startswith("- Generated UTC:")]
        self.assertEqual(body_first, body_second,
                         "the handoff context pack moved a line other than its generation stamp, so a "
                         "session cannot quote it as stable material -- "
                         + str([(number + 1, a, b) for number, (a, b) in enumerate(zip(body_first, body_second))
                                if a != b][:3]))
        self.assertIn("- Branch:", "\n".join(body_first[:12]),
                      "the pack stopped naming the branch and HEAD it was rendered from; a handoff without "
                      "its own provenance cannot be checked later")
        for needle in ("BEGIN PRIVATE KEY", "password=", "Authorization:"):
            self.assertNotIn(needle, "\n".join(first),
                             f"the pack carries something redaction was supposed to remove ({needle})")


if __name__ == "__main__":
    if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    unittest.main()
