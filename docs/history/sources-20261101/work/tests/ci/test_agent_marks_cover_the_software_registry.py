"""Every software the registry knows about must have a mark, and every category it uses must be decided.

Why this is a source sweep in Python rather than a browser assertion: the population is
`config/software-registry.json`, and the thing being checked is coverage of a declaration -- the front end
can only render what the snapshot hands it, so a test that mounts components can never notice a software id
that nobody drew a glyph for. That is the same blind spot that let CL-15 report "brand applied" while the
surface the desktop window shows had none.

The category tripwire is the important half. `agent-runtime` and `agent-harness` are monitored agents;
`platform`, `provider-switch` and `design-client` are not. A category the file has never seen must fail
here, because the alternative is that a new kind of software is silently drawn into the agent HUD -- or
silently dropped from it -- by whichever list happens to be shorter.
"""

from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / "packages" / "client-neutral-core" / "scripts"))

REGISTRY = REPO / "config/software-registry.json"
MARKS = REPO / "apps/observer/frontend/src/daily/agentMarks.tsx"

# The categories the shell treats as "a monitored agent runtime", read back from the module that decides it.
AGENT_CATEGORIES = ["agent-runtime", "agent-harness"]
# Everything else the registry is allowed to say today. A new value has to be added here deliberately, which
# is the argument the HUD's membership list is supposed to be the record of.
DECLARED_NON_AGENT = ["platform", "provider-switch", "design-client"]


def _registry() -> list[dict]:
    return json.loads(REGISTRY.read_text(encoding="utf-8"))["software"]


def _source() -> str:
    return MARKS.read_text(encoding="utf-8")


def _marked_ids(source: str) -> set[str]:
    """The keys of the `AGENT_MARKS` record, whatever quote style they are written in.

    TypeScript accepts four shapes for the same entry -- `'deepseek-harness': fn`, `"hermes": fn`,
    `codex: fn` and the shorthand `hermes,` -- and a reader that only understands some of them reports a
    mark as absent. Both wrong halves of that have already happened on this file: the first version looked
    only for `key:` and missed the shorthands, the second was reformatting the record to one explicit
    `key: value` per line with single quotes and then read back zero keys. So the quote style is part of the
    tested surface, and the count floor in the first test is what stops a silent empty set from passing.
    """
    block = re.search(r"export const AGENT_MARKS[^=]*=\s*\{(.*?)\}", source, re.S)
    assert block, "AGENT_MARKS is not declared the way this gate reads it -- update the gate, do not delete it"
    keys: set[str] = set()
    for raw in block.group(1).splitlines():
        line = raw.split("/*")[0].split("//")[0].strip().rstrip(",")
        if not line:
            continue
        found = re.match(r"""^(?:"([^"]+)"|'([^']+)'|([A-Za-z]\w*))\s*(?::|$)""", line)
        if found:
            keys.add(next(group for group in found.groups() if group is not None))
    return keys


class AgentMarkCoverage(unittest.TestCase):
    def test_the_registry_and_the_marks_are_read_from_disk_not_assumed(self) -> None:
        self.assertTrue(REGISTRY.is_file(), f"{REGISTRY} is missing; the gate would pass on an empty set")
        self.assertGreaterEqual(len(_registry()), 5, "the software registry shrank to nothing useful")
        self.assertGreaterEqual(len(_marked_ids(_source())), 5, "no marks are declared")

    def test_every_registered_software_has_its_own_mark(self) -> None:
        missing = sorted({str(e.get("softwareId")) for e in _registry()} - _marked_ids(_source()))
        self.assertEqual([], missing,
                         "these software ids are in the registry but have no glyph, so they render as the "
                         "UNKNOWN figure: " + ", ".join(missing))

    def test_no_mark_exists_for_a_software_the_registry_does_not_know(self) -> None:
        stale = sorted(_marked_ids(_source()) - {str(e.get("softwareId")) for e in _registry()}
                       - {"UNKNOWN"})
        self.assertEqual([], stale, f"these marks belong to nothing: {stale}")

    def test_the_mark_reader_understands_every_key_shape_typescript_allows(self) -> None:
        """The parser is code, so it gets a test of its own.

        Without this, a regression in `_marked_ids` shows up as "the registry has no marks" and the fix
        becomes a fight with the data file. Each of these four lines is the same entry written a different
        legal way.
        """
        shapes = {
            "single_quoted": ("'a-b': fn,", {"a-b"}),
            "double_quoted": ('"a-b": fn,', {"a-b"}),
            "bare_paired": ("alpha: fn,", {"alpha"}),
            "shorthand": ("alpha,", {"alpha"}),
        }
        for name, (entry, expected) in shapes.items():
            with self.subTest(shape=name):
                source = "export const AGENT_MARKS: Record<string, Glyph> = {\n  %s\n}\n" % entry
                self.assertEqual(expected, _marked_ids(source))

    def test_the_agent_predicate_is_the_declared_categories_and_nothing_else(self) -> None:
        source = _source()
        listed = re.search(r"export const AGENT_CATEGORIES[^=]*=\s*\[([^\]]*)\]", source)
        self.assertIsNotNone(listed, "AGENT_CATEGORIES is not declared where this gate reads it")
        values = [v.strip().strip("'\"") for v in (listed.group(1) if listed else "").split(",") if v.strip()]
        self.assertEqual(AGENT_CATEGORIES, values)

    def test_every_category_the_registry_uses_is_decided_one_way_or_the_other(self) -> None:
        used = {str(e.get("category") or "UNKNOWN") for e in _registry()}
        undecided = sorted(used - set(AGENT_CATEGORIES) - set(DECLARED_NON_AGENT) - {"UNKNOWN"})
        self.assertEqual([], undecided,
                         f"new software category {undecided}: decide whether it is a monitored agent, then "
                         "add it to AGENT_CATEGORIES or to DECLARED_NON_AGENT here -- the HUD must not pick "
                         "by name")

    def test_the_delivery_platform_is_not_an_agent(self) -> None:
        """The measured reason this whole change exists: GitHub was drawn in the agent HUD."""
        github = next(e for e in _registry() if e.get("softwareId") == "github")
        self.assertNotIn(github.get("category"), AGENT_CATEGORIES,
                         "GitHub is the delivery platform; moving it into an agent category has to be an "
                         "argument in the registry, not a side effect of a filter")


if __name__ == "__main__":
    unittest.main()
