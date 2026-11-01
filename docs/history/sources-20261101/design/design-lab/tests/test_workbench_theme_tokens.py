# SPDX-License-Identifier: MIT
"""A registered design token must either be read by a rule, or say why it isn't -- and its value
must equal the source it names.

Why this gate exists (measured 2026-10-11). The optional ``ui2026`` theme registers 47 ``--uif-*``
tokens and its own comment said the typography/layout block "登记 20261009 值供新面消费". Three
things were false at once: ``--uif-font-h1`` was 29px where the pack says 27; the layout row read
232/40/26 where the pack says 256/216/30/22 (and neither 232 nor 29 appears anywhere in the repo or
the pack); and eleven of the 47 tokens -- ``--uif-font-h1/h2``, the sidebar and both gutters among
them -- were read by nobody, while the pack's body/small/h3/micro sizes genuinely were. A number
written into a file the reader trusts, consumed by no rule, is the same class of defect as a verdict
word no surface renders: it states something about the product that the product does not answer.

So the gate asks two questions per token, both bidirectional:

1. **Is it consumed?** Each token needs a ``var(--token)`` in the Workbench sources or an entry in
   :data:`REGISTERED_NOT_CONSUMED` with a reason. A token that gets wired up and stays registered is
   red too, so the register only shrinks by being emptied honestly.
2. **Does its number equal the source it names?** :data:`SPEC_PROVENANCE` maps tokens onto
   ``specs/design_tokens.json`` fields; anything that deliberately departs must sit in
   :data:`DOCUMENTED_DEVIATIONS` naming the pack value it refuses. Silent drift and silent
   re-alignment both fail.
"""
from __future__ import annotations
import json
import re
import unittest
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
STYLE = REPO / "apps/workbench/style.css"
SPEC = REPO / "docs/history/taskpacks/20261009-r2-inputs/ui-r2/specs/design_tokens.json"

DECL_RE = re.compile(r"(--uif-[a-z0-9-]+)\s*:\s*([^;}]+)")

#: token -> dotted path inside the pack's design_tokens.json. Claiming provenance means the number
#: has to match it.
SPEC_PROVENANCE = {
    "--uif-dark-bg": "dark.background",
    "--uif-dark-surface": "dark.surface",
    "--uif-dark-raised": "dark.raised",
    "--uif-dark-text": "dark.text",
    "--uif-dark-muted": "dark.muted",
    "--uif-dark-border": "dark.border",
    "--uif-dark-accent": "dark.accent",
    "--uif-dark-accent-text": "dark.accent_text",
    "--uif-dark-success": "dark.success",
    "--uif-dark-warning": "dark.warning",
    "--uif-dark-danger": "dark.danger",
    "--uif-light-bg": "light.background",
    "--uif-light-surface": "light.surface",
    "--uif-light-raised": "light.raised",
    "--uif-light-text": "light.text",
    "--uif-light-muted": "light.muted",
    "--uif-light-border": "light.border",
    "--uif-light-accent": "light.accent",
    "--uif-light-accent-text": "light.accent_text",
    "--uif-light-success": "light.success",
    "--uif-light-warning": "light.warning",
    "--uif-light-danger": "light.danger",
    "--uif-font-h1": "typography.size_css_px.h1",
    "--uif-font-h2": "typography.size_css_px.h2",
    "--uif-font-h3": "typography.size_css_px.h3",
    "--uif-font-body": "typography.size_css_px.body",
    "--uif-font-small": "typography.size_css_px.small",
    "--uif-font-micro": "typography.size_css_px.micro",
    "--uif-body-line-height": "typography.body_line_height",
    "--uif-space-1": "spacing_css_px.0",
    "--uif-space-2": "spacing_css_px.1",
    "--uif-space-3": "spacing_css_px.2",
    "--uif-space-4": "spacing_css_px.3",
    "--uif-space-6": "spacing_css_px.4",
    "--uif-space-8": "spacing_css_px.5",
    "--uif-space-10": "spacing_css_px.6",
    "--uif-radius-control": "radius_css_px.controls",
    "--uif-radius-card": "radius_css_px.cards",
    "--uif-radius-hero": "radius_css_px.hero",
    "--uif-border-width": "border_width_css_px",
    "--uif-motion-fast": "motion.recommended_ms.0",
    "--uif-motion-base": "motion.recommended_ms.1",
    "--uif-sidebar": "layout.sidebar",
    "--uif-sidebar-compact": "layout.compact_sidebar",
    "--uif-gutter-desktop": "layout.desktop_gutter",
    "--uif-gutter-compact": "layout.compact_gutter",
    "--uif-drawer": "layout.drawer_width",
}

#: A registered value that deliberately differs from the pack, naming the pack value it refuses.
#: Fixing the deviation means deleting the entry; keeping it while the numbers agree is red.
DOCUMENTED_DEVIATIONS = {
    "--uif-topbar": {
        "spec": "layout.topbar",
        "reason": "78px is what the shipped shell renders and three rules already read it; the pack "
                  "declares 64. Either side moving changes landed layout, so this is owner ruling B "
                  "in DESIGNLAB-UI-R2-DESIGN-QA-2026-10-09.md, not a transcription error.",
    },
    "--uif-font-micro": {
        "spec": "typography.size_css_px.micro",
        "reason": "the 20261023 pack states 元数据至少 12px, and the contrast ruler grades that floor "
                  "on the painted document (CT_SPEC below12, asserted 0 under the pack theme): 119 "
                  "text runs measured under 12px before the raise. So the 20261009 registration of 11 "
                  "is refused on measured legibility grounds, not re-typed silently -- putting 11 back "
                  "turns the themed contrast gate red and this entry becomes the thing to delete.",
    },
}

#: Tokens allowed to sit unread, each with a reason. The register can only shrink.
#: Measured 2026-10-11: 8 of 48 registered tokens are read by nothing. The pack's body/small/h3/micro
#: sizes ARE consumed by the UI-first surfaces, so the unresolved part of the type scale is exactly
#: h1 and h2 -- the two roles the interface has no single owner for.
REGISTERED_NOT_CONSUMED = {
    "--uif-font-h1": "the shell has no single h1 role to map it onto: .brand h1 is 17px and "
                     "body > header h1 is 26px. Registered, not applied -- owner ruling B.",
    "--uif-font-h2": ".page-head h2 is 32px and .route-view h2 is 24px; the pack's h2 (19px) fits "
                     "neither role without a design decision. Owner ruling B.",
    "--uif-radius-hero": "no hero surface ships in the Workbench yet, so no rule could read it",
    "--uif-motion-fast": "the landed transitions use the pre-existing --motion-* tokens; re-wiring "
                         "them is a behaviour change, not a token change",
    "--uif-motion-base": "same as --uif-motion-fast",
    "--uif-space-6": "the 24px step is unused so far; new surfaces take --uif-space-2/3/4",
    "--uif-space-10": "same as --uif-space-6 for the 40px step",
    "--uif-light-accent-text": "the light scheme re-points --tag-ink at the dark accent text on "
                               "measured contrast grounds; see the comment in the light block",
}


def declarations(css: str) -> dict[str, str]:
    return {name: value.strip() for name, value in DECL_RE.findall(css)}


def consumer_counts(css: str, declared) -> dict[str, int]:
    sources = [STYLE] + sorted((REPO / "apps/workbench").glob("*.ts"))
    texts = [(path.read_text(encoding="utf-8") if path != STYLE else css) for path in sources]
    return {name: sum(len(re.findall(rf"var\(\s*{re.escape(name)}\s*\)", text)) for text in texts)
            for name in declared}


def _spec_value(spec: dict, dotted: str):
    node = spec
    for part in dotted.split("."):
        node = node[int(part)] if isinstance(node, list) else node[part]
    return node


def _number(css_value: str) -> float:
    match = re.fullmatch(r"(-?[0-9]*\.?[0-9]+)(?:px|ms|rem)?", css_value)
    if not match:
        raise ValueError(f"not a plain number: {css_value!r}")
    return float(match.group(1))


def consumption_failures(css: str, spec) -> list[str]:
    declared = declarations(css)
    counts = consumer_counts(css, declared)
    unread = sorted(name for name, count in counts.items() if count == 0)
    failures = [f"{name} is declared, read by nothing, and not registered"
                for name in unread if name not in REGISTERED_NOT_CONSUMED]
    failures += [f"{name} is registered as unread but a rule now reads it -- delete the entry"
                 for name in sorted(REGISTERED_NOT_CONSUMED) if counts.get(name, 0) > 0]
    failures += [f"{name} is registered but no longer declared"
                 for name in sorted(REGISTERED_NOT_CONSUMED) if name not in declared]
    failures += [f"{name} sits in the unread register without a usable reason"
                 for name, reason in REGISTERED_NOT_CONSUMED.items() if len(reason) <= 20]
    return failures


def provenance_failures(css: str, spec) -> list[str]:
    declared = declarations(css)
    failures = []
    for name, dotted in SPEC_PROVENANCE.items():
        if name not in declared:
            failures.append(f"{name} claims pack provenance but is not declared")
            continue
        if name in DOCUMENTED_DEVIATIONS:
            continue
        try:
            expected = _spec_value(spec, dotted)
        except (KeyError, IndexError, TypeError) as exc:
            failures.append(f"{name} points at a missing pack field {dotted}: {exc}")
            continue
        value = declared[name]
        if value.startswith("#"):
            if value.lower() != str(expected).lower():
                failures.append(f"{name}={value} but pack {dotted}={expected}")
            continue
        try:
            actual = _number(value)
        except ValueError:
            failures.append(f"{name}={value!r} is neither a colour nor a number")
            continue
        if float(expected) != actual:
            failures.append(f"{name}={value} but pack {dotted}={expected}")
    return failures


def deviation_failures(css: str, spec) -> list[str]:
    declared = declarations(css)
    failures = []
    for name, entry in DOCUMENTED_DEVIATIONS.items():
        if name not in declared:
            failures.append(f"{name} is documented as a deviation but is not declared")
            continue
        expected = float(_spec_value(spec, entry["spec"]))
        actual = _number(declared[name])
        if actual == expected:
            failures.append(f"{name} now equals the pack -- delete it from DOCUMENTED_DEVIATIONS")
        if len(entry["reason"]) <= 40:
            failures.append(f"{name} deviation carries no usable reason")
    return failures


class WorkbenchThemeTokenContract(unittest.TestCase):
    def setUp(self) -> None:
        self.css = STYLE.read_text(encoding="utf-8")
        self.spec = json.loads(SPEC.read_text(encoding="utf-8"))

    def test_current_tree_passes_all_three_checks(self) -> None:
        for label, failures in (("CONSUMPTION", consumption_failures(self.css, self.spec)),
                                ("PROVENANCE", provenance_failures(self.css, self.spec)),
                                ("DEVIATION", deviation_failures(self.css, self.spec))):
            self.assertEqual(failures, [], f"{label}: " + "; ".join(failures))

    def test_the_geometry_wired_this_session_is_actually_read(self) -> None:
        counts = consumer_counts(self.css, declarations(self.css))
        for name in ("--uif-sidebar", "--uif-sidebar-compact", "--uif-gutter-desktop",
                     "--uif-gutter-compact"):
            self.assertGreaterEqual(counts[name], 2,
                                    f"{name} must drive the rail and the content offset")
        compact = self.css.replace(" ", "")
        self.assertIn(':root[data-palette="ui2026"].app-nav{width:var(--uif-sidebar)}', compact)
        self.assertIn('@media(min-width:768px)and(max-width:1199px){', compact)

    def test_default_palette_geometry_is_untouched(self) -> None:
        """Owner boundary: the existing palette keeps rendering exactly as before, so only a rule
        that names the optional palette may take the rail width from a pack token.

        Two matching traps are handled here deliberately: the selector is compared as a whole
        selector, because `.app-nav-item` also contains "app-nav"; and the pre-existing unscoped
        rules -- the 168px base and the <=760px collapse (`width:auto`) -- are asserted to still
        exist, since a theme that deleted them would change the default palette's layout.
        """
        offenders = []
        for match in re.finditer(r"([^{}]+)\{([^{}]*)\}", self.css):
            selector, body = match.group(1), match.group(2)
            if "var(--uif-sidebar" not in body.replace(" ", ""):
                continue
            if 'data-palette="ui2026"' not in selector:
                offenders.append(selector.strip()[:70] or "(no selector)")
        self.assertEqual(offenders, [], "a rail width taken from a pack token outside the theme")

        self.assertRegex(self.css, r"\.app-nav\{[^}]*width:168px")
        self.assertRegex(self.css, r"\.app-nav\{[^}]*inset:auto 0 0 0[^}]*width:auto")
        scoped = re.findall(r':root\[data-palette="ui2026"\]\s+\.app-nav\{width:[^}]*\}', self.css)
        self.assertEqual(len(scoped), 2, f"expected one rule per breakpoint, got {scoped}")

    def test_plant_misregistered_value_is_convicted_by_name(self) -> None:
        """The exact defect this gate was written for: a layout row that claims the pack and holds
        232/40/26 instead of 256/30/22."""
        planted = (self.css.replace("--uif-sidebar:256px", "--uif-sidebar:232px", 1)
                          .replace("--uif-gutter-desktop:30px", "--uif-gutter-desktop:40px", 1))
        self.assertNotEqual(planted, self.css, "the plant moved no bytes")
        failures = provenance_failures(planted, self.spec)
        self.assertEqual(len(failures), 2, failures)
        self.assertTrue(any("--uif-sidebar=232px" in line for line in failures), failures)
        self.assertTrue(any("layout.sidebar=256" in line for line in failures), failures)

    def test_plant_unread_unregistered_token_is_convicted(self) -> None:
        planted = self.css + "\n--uif-planted-orphan:13px;\n"
        self.assertNotEqual(planted, self.css, "the plant moved no bytes")
        failures = consumption_failures(planted, self.spec)
        self.assertEqual(failures, ["--uif-planted-orphan is declared, read by nothing, "
                                   "and not registered"], failures)

    def test_plant_stale_register_entry_is_convicted(self) -> None:
        """Wiring a token up must not leave it filed as unread -- the register only shrinks."""
        planted = self.css.replace("--uif-radius-hero:12px", "--uif-radius-hero:12px;", 1) + \
            "\n.x{border-radius:var(--uif-radius-hero)}\n"
        self.assertNotEqual(planted, self.css, "the plant moved no bytes")
        failures = consumption_failures(planted, self.spec)
        self.assertIn("--uif-radius-hero is registered as unread but a rule now reads it "
                      "-- delete the entry", failures)

    def test_plant_silent_realignment_of_a_deviation_is_convicted(self) -> None:
        planted = self.css.replace("--uif-topbar:78px", "--uif-topbar:64px", 1)
        self.assertNotEqual(planted, self.css, "the plant moved no bytes")
        failures = deviation_failures(planted, self.spec)
        self.assertEqual(failures, ["--uif-topbar now equals the pack -- delete it from "
                                   "DOCUMENTED_DEVIATIONS"], failures)

    def test_plant_missing_declaration_is_convicted(self) -> None:
        planted = self.css.replace("--uif-sidebar-compact:216px;", "", 1)
        self.assertNotEqual(planted, self.css, "the plant moved no bytes")
        failures = provenance_failures(planted, self.spec)
        self.assertIn("--uif-sidebar-compact claims pack provenance but is not declared", failures)


    #: Every custom property the sheet declares, not just the pack's own `--uif-*` family.
    #: `declarations()` above is deliberately scoped to `--uif-` because it serves the
    #: provenance check; borrowing it for a whole-sheet census returns [] for anything else,
    #: so the guard would have been a green that could not fail. Comments are stripped first:
    #: a name written inside an explanatory comment is not a declaration.
    ALL_DECL_RE = re.compile(r'(--[A-Za-z0-9]+[A-Za-z0-9-]*)\s*:\s*[^;\n]+')

    def all_declared(self, css: str) -> list:
        bare = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
        seen = []
        for name in self.ALL_DECL_RE.findall(bare):
            if name not in seen:
                seen.append(name)
        return seen

    def unconsumed(self, css: str) -> list:
        counts = consumer_counts(css, self.all_declared(css))
        provenanced = set(SPEC_PROVENANCE)
        return sorted(name for name, count in counts.items()
                      if count == 0 and name not in provenanced)

    def test_no_custom_property_is_declared_and_never_read(self) -> None:
        """A stylesheet that declares tokens nobody reads is not a design system; it is a
        vocabulary that says the system exists.

        Swept 2026-10-25: 24 of 133 declared custom properties were read by no `var()` in the
        sheet and by no product source, gate, test or package file at all. They came from the
        absorbed B07 `shared-ui-core/base-tokens.css` reference set, and the only places their
        names still appeared were that reference corpus and a design-debt listing recording
        them as unused. The pre-existing CONSUMPTION check missed them because its population is
        the pack's own named fields -- a coverage gate only ever proves the list it carries.

        So this extends the population to EVERY declared property and lets `SPEC_PROVENANCE`
        decide the exception, rather than hand-writing an allowlist: a token may sit unread if
        it exists to carry a pack value into the provenance check, and that reason has to be
        registered in the map that already states it.
        """
        dead = self.unconsumed(self.css)
        self.assertEqual(
            dead, [],
            'declared but read by nothing, and not registered as carrying pack provenance: %s'
            % ', '.join(dead))

    def test_a_dead_declaration_is_convicted(self) -> None:
        """The guard above must be able to fail, or it is decoration on a clean-looking sheet."""
        planted = self.css.replace("  --motion-fast:120ms;",
                                   "  --motion-fast:120ms;\n  --space-dead-99:4px;", 1)
        self.assertNotEqual(planted, self.css, "the plant moved no bytes")
        self.assertIn('--space-dead-99', self.all_declared(planted),
                      'the census does not even see the planted declaration')
        self.assertEqual(self.unconsumed(planted), ['--space-dead-99'],
                         'the population check accepted an unconsumed declaration')
        # And the real sheet is clean, so the conviction is about the plant, not about noise
        # that would make the assertion impossible to satisfy.
        self.assertEqual(self.unconsumed(self.css), [])


if __name__ == "__main__":
    unittest.main()
