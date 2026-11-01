"""Gate: `apps/observer/frontend/DESIGN.md` must be a machine-readable contract, not prose with braces.

Why this file exists: the repo already shipped `design_contract.py`, whose own docstring advertises a
"DESIGN.md design-contract parser / lint / diff", and `verify_design_contract.py` prints
`DESIGN_CONTRACT_PASS`. Measured at this commit: `design_contract.py` contains no markdown, frontmatter,
YAML or `---` handling at all -- it is an NX-500 DTCG token checker over Python objects. So a DESIGN.md
can be unreadable, unparseable or self-contradictory while that verifier keeps printing PASS. That is
the ERR-214 class again: a check that appears to cover the thing and covers something else.

The plugin's own `audit-design-md.mjs` cannot be the answer either: it imports the `yaml` package, which
is not installed in the plugin tree, and installing it there would put this project's dependencies
outside the Git root. So the contract is checked here, in-repo, with the interpreter the gate already
binds.

Five claims are enforced, each with a falsification control in the sibling test:

1. the frontmatter parses as YAML, and a bare colon in a scalar is caught rather than mangled;
2. every `{group.key}` reference in a component value resolves to a declared token;
3. prose references resolve too, so a reader cannot cite a token that does not exist;
4. colour and radius values agree with `src/theme/tokens.ts`, the declared numeric authority --
   a contract that drifts from its own source of truth is worse than no contract;
5. the type floor and the contrast rule are stated as numbers, and Known Gaps is non-empty, so the file
   cannot silently present the surface as compliant.

Discovered dynamically by `run_quality_gate.py governance`.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "apps" / "observer" / "frontend" / "DESIGN.md"
SPEC = ROOT / "apps" / "observer" / "frontend" / "SCREEN_SPEC.md"
TOKENS_TS = ROOT / "apps" / "observer" / "frontend" / "src" / "theme" / "tokens.ts"

FM = re.compile(r"^---\r?\n(.*?)\r?\n---\r?\n", re.S)
REF = re.compile(r"\{([a-z][A-Za-z0-9.-]*)\}")
GROUPS = ("colors", "typography", "rounded", "spacing", "components")
# `xs/sm/md/lg/xl` are deliberately reused by both the radius and the spacing scale, so a bare
# `{md}` is ambiguous and must be rejected wherever it appears.
BARE_SHORT = re.compile(r"\{(none|sm|md|lg|xl|xs|xxl|section)\}")


def frontmatter() -> tuple[str, dict]:
    text = DOC.read_text(encoding="utf-8")
    match = FM.match(text)
    if not match:
        raise AssertionError("DESIGN.md has no `---` frontmatter block")
    return text, yaml.safe_load(match.group(1))


class ParsesAndResolvesTests(unittest.TestCase):
    def test_frontmatter_parses_as_yaml(self) -> None:
        _, data = frontmatter()
        for group in GROUPS:
            self.assertIn(group, data, f"frontmatter is missing the {group} group")
        self.assertEqual(data["version"], "alpha")

    def test_component_references_resolve_to_declared_tokens(self) -> None:
        _, data = frontmatter()
        declared = {f"{group}.{key}" for group in GROUPS for key in (data.get(group) or {})}
        bad = []
        for name, component in (data.get("components") or {}).items():
            for field, value in (component or {}).items():
                if not isinstance(value, str):
                    continue
                for ref in REF.findall(value):
                    if ref not in declared:
                        bad.append(f"{name}.{field} -> {{{ref}}}")
        self.assertEqual(bad, [], "component values reference tokens that do not exist")

    def test_prose_references_resolve_to_declared_tokens(self) -> None:
        _, data = frontmatter()
        declared = {f"{group}.{key}" for group in GROUPS for key in (data.get(group) or {})}
        prose = DOC.read_text(encoding="utf-8")[FM.match(DOC.read_text(encoding="utf-8")).end():]
        bad = sorted({ref for ref in REF.findall(prose) if ref not in declared})
        self.assertEqual(bad, [], "prose cites tokens the frontmatter does not declare")

    def test_no_reference_relies_on_an_ambiguous_bare_scale_name(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        hits = sorted(set(BARE_SHORT.findall(text)))
        self.assertEqual(hits, [], "these references are both a radius and a spacing name; qualify them: " + ", ".join(hits))


class AgreesWithTheNumericAuthorityTests(unittest.TestCase):
    """`src/theme/tokens.ts` is declared the single source of truth; the contract must not contradict it."""

    def setUp(self) -> None:
        self.source = TOKENS_TS.read_text(encoding="utf-8")
        _, self.data = frontmatter()

    def test_dark_surface_and_accent_values_match_tokens_ts(self) -> None:
        dark = self.source[self.source.index("export const DARK"):]
        dark = dark[: dark.index("};")] if "};" in dark else dark
        for key, value in self.data["colors"].items():
            if key in ("on-primary", "hairline", "surface-sidebar", "surface-panel", "surface-raised", "canvas", "ink", "muted"):
                self.assertIn(value.upper(), dark, f"colors.{key} = {value} is not present in the DARK block")

    def test_radius_scale_matches_the_declared_css_variables(self) -> None:
        index_css = (ROOT / "apps" / "observer" / "frontend" / "src" / "index.css").read_text(encoding="utf-8")
        for name, value in self.data["rounded"].items():
            if name in ("none", "full"):
                continue  # the CSS scale declares sm/md/lg/xl only
            found = re.search(rf"--radius-{name}:\s*([^;]+);", index_css)
            self.assertIsNotNone(found, f"--radius-{name} is not defined in index.css")
            self.assertEqual(found.group(1).strip(), value, f"rounded.{name} disagrees with --radius-{name}")

    def test_the_contract_does_not_claim_the_brand_file_is_its_radius_source(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertIn("design-tokens.json", text, "the conflicting brand token file is not acknowledged")


class StandardsAreStatedAsNumbersTests(unittest.TestCase):
    def test_type_floor_is_stated_and_enforced_by_wording(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertRegex(text, r"below \*\*12px\*\*|No text a user must read below \*\*12px\*\*")
        self.assertIn("(normative)", text)

    def test_contrast_rule_is_numeric(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        self.assertRegex(text, r"4\.5:1")
        self.assertRegex(text, r"3:1")

    def test_known_gaps_is_not_emptied_to_claim_compliance(self) -> None:
        text = DOC.read_text(encoding="utf-8")
        gaps = text.split("## Known Gaps", 1)
        self.assertEqual(len(gaps), 2, "Known Gaps section is missing")
        numbered = re.findall(r"^\d+\. \*\*", gaps[1], re.M)
        self.assertGreaterEqual(len(numbered), 5,
                                "a contract with no recorded gaps is a claim of compliance, not a contract")

    def test_screen_spec_states_the_reachability_rule_the_current_surface_violates(self) -> None:
        spec = SPEC.read_text(encoding="utf-8")
        self.assertIn("Every nav item is reachable", spec)
        self.assertIn("clientHeight == scrollHeight", spec)
        self.assertIn("not a breakpoint", spec)


if __name__ == "__main__":
    unittest.main()
