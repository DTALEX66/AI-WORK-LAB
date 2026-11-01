#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Measure the design-debt stock DESIGN.md §4 states in prose, and register the colours
that are not in the palette so an actual ruling can be made about each one.

Why this exists: §4's numbers (18 literal colours / 360 literal px / 9 shadows) were
hand-counted in `docs/audits/DESIGNLAB-LAUNCH-REVIEW-PREFLIGHT-2026-10-08.md` §36.4 and
no rule reproduces them. The external design-review plugin, first run on 2026-10-08,
disagreed with all three over the same bytes -- partly because it is right that the count
needs a unit, and partly because it counts matches inside comments and grades a
`box-shadow:none` reset as a value. A contract about to become an acceptance standard
cannot carry an unrestorable figure, and it cannot carry a debt list that nobody owns.

The rule is declared here and nowhere else:
  scope      the Workbench's own UI sources (SCOPE below)
  unit       one count per literal OCCURRENCE (not per line, not per declaration)
  skipped    a line that declares a custom property (that is the token, not the debt),
             everything inside a CSS or TypeScript comment (documenting a value is not
             hard-coding it), and a shadow declaration that assigns `none`/`inherit`/
             `unset`/`initial` (removing an elevation is not inventing one)
  colours    #rgb/#rgba/#rrggbb/#rrggbbaa outside the allowlist, plus rgb()/rgba()/
             hsl()/hsla() literals
  px         `\\b[2-9]px\\b` and `\\b[1-9]\\d{1,3}px\\b` -- 0px and 1px are structural,
             not scale decisions (identical to the plugin's regex, so the two are
             directly comparable)
  shadows    every `box-shadow:` value assignment, and how many of those read a var()

Verified non-issue, recorded so nobody re-litigates it: a trailing `//` note after code
leaks ZERO literals into these counts (measured 2026-10-08 over the whole scope), which is
why the comment rule stays the conservative whole-line form rather than a quote-aware one
that would chew through `https://` inside strings.

Usage:
    python scripts/design_debt_baseline.py --show
    python scripts/design_debt_baseline.py --check      # DESIGN.md and the register must match
    python scripts/design_debt_baseline.py --register   # write/merge the off-palette register
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
CONTRACT = REPO / "DESIGN.md"
REGISTER = REPO / "design-lab" / "config" / "ui-off-palette-colours.json"

SCOPE = ("apps/workbench/style.css",
         "apps/workbench/main.ts",
         "apps/workbench/shell.ts",
         "apps/workbench/workbench.ts",
         "apps/workbench/design.ts",
         "apps/workbench/contracts.ts",
         "apps/workbench/index.html")

HEX = re.compile(r"(?<![\w])#(?:[0-9a-fA-F]{3,4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})(?![\w])")
FUNCTIONAL = re.compile(r"\b(?:rgb|rgba|hsl|hsla)\([^)]*\)")
PX = re.compile(r"\b(?:[2-9]|[1-9]\d{1,3})px\b")
SHADOW = re.compile(r"\bbox-shadow\s*:([^;}]*)")
RESET_VALUE = re.compile(r"^\s*(?:none|inherit|unset|initial|revert)\b")
TOKEN_DECLARATION = re.compile(r"^\s*--[A-Za-z0-9-_]+\s*:")
ALLOWED_COLORS = {"#fff", "#000", "transparent"}

CSS_COMMENT = re.compile(r"/\*[\s\S]*?\*/")
LINE_COMMENT = re.compile(r"^\s*//.*$", re.MULTILINE)

# A neutral alpha is a scrim, a shadow or a state layer: still a literal, but it is not a
# new hue competing with the brand. Keeping the two apart is what makes the register
# actionable instead of a wall of numbers.
NEUTRAL_ALPHA = re.compile(r"^(?:rgba?\(\s*(?:0,\s*0,\s*0|255,\s*255,\s*255)\s*,|transparent$)")


def strip_comments(text: str) -> str:
    """Blank out comments, keeping line structure so line numbers stay meaningful."""
    def blank(match: re.Match[str]) -> str:
        return re.sub(r"[^\n]", " ", match.group(0))
    return LINE_COMMENT.sub(blank, CSS_COMMENT.sub(blank, text))


def classify(value: str) -> str:
    return "neutral-alpha" if NEUTRAL_ALPHA.match(value.lower()) else "chromatic"


def measure() -> dict:
    colors = pixels = shadows = shadow_tokened = resets = 0
    sites: list[dict] = []
    for rel in SCOPE:
        path = REPO / rel
        if not path.is_file():
            raise SystemExit(f"MEASURE_ABORT: scope file missing: {rel}")
        text = strip_comments(path.read_text(encoding="utf-8", errors="replace"))
        for number, line in enumerate(text.splitlines(), start=1):
            if TOKEN_DECLARATION.match(line):
                continue
            literals = [h for h in HEX.findall(line) if h.lower() not in ALLOWED_COLORS]
            literals += FUNCTIONAL.findall(line)
            colors += len(literals)
            pixels += len(PX.findall(line))
            for match in SHADOW.finditer(line):
                if RESET_VALUE.match(match.group(1)):
                    resets += 1
                    continue
                shadows += 1
                if "var(" in match.group(1):
                    shadow_tokened += 1
            for value in literals:
                sites.append({"value": value.lower(), "file": rel, "line": number,
                              "kind": classify(value),
                              "declaration": line.strip()[:160]})
    # Identity is (file, value, which occurrence of it), not the line number: an unrelated
    # edit that shifts a line must not read as one debt removed and another added.
    seen: dict[tuple[str, str], int] = {}
    for site in sites:
        seen[(site["file"], site["value"])] = seen.get((site["file"], site["value"]), 0) + 1
        site["occurrence"] = seen[(site["file"], site["value"])]
    return {"literalColors": colors, "literalPx": pixels,
            "shadowDeclarations": shadows, "shadowDeclarationsReadingAVar": shadow_tokened,
            "shadowResetsSkipped": resets,
            "chromaticLiterals": sum(1 for s in sites if s["kind"] == "chromatic"),
            "neutralAlphaLiterals": sum(1 for s in sites if s["kind"] == "neutral-alpha"),
            "sites": sites}


def contract_statement(values: dict) -> tuple[bool, str]:
    """DESIGN.md must quote the measured stock exactly, with the rule named next to it."""
    text = CONTRACT.read_text(encoding="utf-8") if CONTRACT.is_file() else ""
    expected = (f"字面色值 {values['literalColors']} 处、字面 px {values['literalPx']} 处、"
                f"阴影声明 {values['shadowDeclarations']} 条"
                f"（其中 {values['shadowDeclarationsReadingAVar']} 条已读 var()）")
    return expected in text, expected


def site_key(site: dict) -> tuple:
    return (site["file"], site["value"], site["occurrence"])


def load_register() -> dict:
    if not REGISTER.is_file():
        return {"schemaVersion": "design-lab/ui-off-palette-colours/v1",
                "measuredBy": "scripts/design_debt_baseline.py --register", "entries": []}
    return json.loads(REGISTER.read_text(encoding="utf-8"))


def write_register(values: dict) -> dict:
    """Merge measured sites into the register without touching what only a human may write.

    `adjudication` is the owner's field. A regeneration must never invent a ruling, and must
    never drop one that was recorded -- so entries are keyed by (file, value, occurrence) and
    the adjudication survives a rewrite and a moved line.
    """
    existing = {site_key(e): e for e in load_register().get("entries", [])}
    entries = []
    for site in values["sites"]:
        previous = existing.get(site_key(site), {})
        entries.append({
            **site,
            "adjudication": previous.get("adjudication"),
            "adjudicatedBy": previous.get("adjudicatedBy"),
            "adjudicatedOn": previous.get("adjudicatedOn"),
        })
    document = {"schemaVersion": "design-lab/ui-off-palette-colours/v1",
                "measuredBy": "scripts/design_debt_baseline.py --register",
                "rule": "literals outside a custom-property declaration and outside comments, "
                        "over the Workbench UI sources; #fff/#000/transparent allowlisted",
                "adjudicationIsOwnerOnly": True,
                "counts": {k: v for k, v in values.items() if k != "sites"},
                "entries": sorted(entries, key=lambda e: (e["file"], e["value"],
                                                           e["occurrence"]))}
    # newline="": the register is a tracked file. Writing platform line endings would make
    # a regeneration on Windows differ in bytes from the committed form, and any future
    # byte-level cleanliness check would read that as drift.
    with open(REGISTER, "w", encoding="utf-8", newline="") as handle:
        handle.write(json.dumps(document, indent=2, ensure_ascii=False) + "\n")
    return document


def check_register(values: dict) -> tuple[list[str], list[str]]:
    """Fail on stock movement; report, never fail, on the ruling that is still the owner's."""
    problems: list[str] = []
    notices: list[str] = []
    document = load_register()
    if not document.get("entries"):
        return ["REGISTER_MISSING: run scripts/design_debt_baseline.py --register"], notices
    stored = {site_key(e): e for e in document["entries"]}
    live = {site_key(s): s for s in values["sites"]}
    for key in sorted(set(live) - set(stored)):
        problems.append(f"UNREGISTERED-LITERAL {key[0]} {key[2]} (occurrence {key[1]}) "
                        "-- the contract says this stock may not grow")
    for key in sorted(set(stored) - set(live)):
        problems.append(f"STALE-REGISTER-ENTRY {key[0]} {key[2]} (occurrence {key[1]}) "
                        "-- the literal is gone, so remove its row")
    for key, entry in sorted(stored.items()):
        if key in live and entry.get("adjudication") and not entry.get("adjudicatedBy"):
            problems.append(f"UNSIGNABLE-ADJUDICATION {key[0]} {key[2]} "
                            "has a ruling with no named human behind it")
    pending = [e for e in document["entries"] if site_key(e) in live and not e.get("adjudication")]
    if pending:
        notices.append("PENDING-OWNER-ADJUDICATION count=%s values=%s "
                       "-- an agent must not fill this field"
                       % (len(pending), sorted({e["value"] for e in pending})))
    return problems, notices


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--show", action="store_true")
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--register", action="store_true")
    args = parser.parse_args()
    if not (args.show or args.check or args.register):
        args.show = True

    values = measure()
    print("DESIGN_DEBT_SCOPE files=%d %s" % (len(SCOPE), " ".join(SCOPE)))
    print("DESIGN_DEBT literal_colors=%(literalColors)s literal_px=%(literalPx)s "
          "shadow_declarations=%(shadowDeclarations)s shadow_reading_var=%"
          "(shadowDeclarationsReadingAVar)s shadow_resets_skipped=%(shadowResetsSkipped)s "
          "chromatic=%(chromaticLiterals)s neutral_alpha=%(neutralAlphaLiterals)s" % values)
    if args.register:
        document = write_register(values)
        print("DESIGN_DEBT_REGISTER=WRITTEN %s entries=%s"
              % (REGISTER.relative_to(REPO).as_posix(), len(document["entries"])))
        return 0
    if not args.check:
        return 0

    problems, notices = [], []
    stated, expected = contract_statement(values)
    if not stated:
        problems.append("DESIGN.md §4 does not state this exact sentence: " + expected)
    register_problems, register_notices = check_register(values)
    problems += register_problems
    notices += register_notices
    for notice in notices:
        print("DESIGN_DEBT_BASELINE=NOTICE " + notice)
    if problems:
        for problem in problems:
            print("DESIGN_DEBT_BASELINE=DRIFT " + problem)
        return 1
    print("DESIGN_DEBT_BASELINE=PASS prose matches the measurement and every literal site "
          "is registered")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
