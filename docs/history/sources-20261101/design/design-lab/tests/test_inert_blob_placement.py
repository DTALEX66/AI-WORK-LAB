# SPDX-License-Identifier: MIT
"""DL-GOV-INERT: third-party agent-instruction blobs must stay out of active paths.

AGENTS.md requires upstream `AGENTS / CLAUDE / cursorrules / SKILL / install /
affiliate` text to be kept as inert source blobs that never enter root
instructions, prompt assembly, tool discovery, or capability counts. This repo
marks third-party provenance with a sibling `SOURCE.md`, so the precise,
machine-checkable violation surface is: a tracked `SKILL.md` sitting next to a
tracked `SOURCE.md` outside an inert root.

`huashu-design` lived at `packages/capabilities/production/huashu-design/` with
exactly that shape -- upstream trigger phrases ("触发词：做原型、PPT…") and
second-person instructions to whoever executes it -- while
`QUARANTINE_REGISTRY.json` already listed it as quarantined. The registration was
true and the bytes were not, which is what this test exists to prevent.

Scope this test does NOT claim: `integrations/hosts/open-design/expert-suite/skills/`
and `design-lab/skills/` hold `SKILL.md` files with no `SOURCE.md` sibling, so they
are not matched here. Whether the Open Design expert-suite skills are first-party or
vendored is a separate provenance determination this predicate cannot settle.
"""
from __future__ import annotations

import subprocess
import unittest
from collections import defaultdict
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]

INERT_ROOTS = (
    "design-lab/research/quarantine/",
    "docs/history/",
    "reports/history/",
    "research/candidates/",
)


def is_inert_location(rel_posix: str) -> bool:
    """Whether a repo-relative path sits in a root that is allowed to hold inert blobs."""
    return rel_posix.startswith(INERT_ROOTS)


def is_third_party_skill_dir(dir_rel_posix: str, tracked_names: frozenset[str]) -> bool:
    """A directory counts as a third-party skill blob only when it holds BOTH the
    agent-instruction file and this repo's own provenance marker."""
    return "SKILL.md" in tracked_names and "SOURCE.md" in tracked_names


def violating_skill_dirs() -> list[str]:
    """Every tracked directory that pairs SKILL.md with SOURCE.md outside an inert root."""
    out = subprocess.run(["git", "-C", str(REPO), "ls-files"],
                         capture_output=True, text=True, encoding="utf-8").stdout
    by_dir: dict[str, set[str]] = defaultdict(set)
    for line in out.splitlines():
        rel = Path(line).as_posix()
        by_dir[rel.rsplit("/", 1)[0] if "/" in rel else ""].add(rel.rsplit("/", 1)[-1])
    return sorted(d for d, names in by_dir.items()
                  if is_third_party_skill_dir(d, frozenset(names)) and not is_inert_location(d + "/"))


class InertBlobPlacementTests(unittest.TestCase):
    def test_no_third_party_skill_in_active_paths(self) -> None:
        offenders = violating_skill_dirs()
        self.assertEqual(
            offenders, [],
            "third-party SKILL.md found outside an inert root; move it under "
            "design-lab/research/quarantine/ and update its provenance records: "
            f"{offenders}")

    def test_predicate_fires_on_an_active_path(self) -> None:
        """A guard that never matches anything passes for the wrong reason. This is
        the mutation case: same file pair, non-inert location, must be flagged."""
        names = frozenset({"SKILL.md", "SOURCE.md", "LICENSE"})
        self.assertTrue(is_third_party_skill_dir("packages/capabilities/production/x", names))
        self.assertFalse(is_inert_location("packages/capabilities/production/x/"))

    def test_predicate_stays_quiet_on_the_two_exempt_shapes(self) -> None:
        names = frozenset({"SKILL.md", "SOURCE.md"})
        self.assertTrue(is_inert_location("design-lab/research/quarantine/x/"),
                        "the quarantine root must be recognised as inert")
        self.assertFalse(is_third_party_skill_dir("design-lab/skills/own",
                                                  frozenset({"SKILL.md", "references"})),
                         "a first-party SKILL.md with no SOURCE.md sibling is out of scope")
        self.assertFalse(is_third_party_skill_dir("packages/capabilities/standards/x",
                                                  frozenset({"README.md", "SOURCE.md", "LICENSE"})),
                         "a vendored reference without SKILL.md is not an agent-instruction blob")

    def test_quarantine_registration_matches_bytes(self) -> None:
        """The failure mode that hid this was a registry claiming 'quarantined' while
        the files stayed put, so the record and the bytes must be checked together."""
        self.assertTrue((REPO / "design-lab/research/quarantine/huashu-design/SKILL.md").is_file(),
                        "huashu-design is registered as inert but its bytes are not there")


if __name__ == "__main__":
    unittest.main()
