#!/usr/bin/env python3
"""One CSS custom property must mean one value per theme, whichever sheet declares it.

Measured 2026-10-08 on the shipped sheets: `--radius-sm` is declared `4px` in `src/index.css` and `12px` in
`src/skins/b10.css`, both under `:root`. b10.css loads second (src/main.tsx imports index.css, then
skins/b10.css, then skins/l10b-shell.css), so every consumer of `--radius-sm` renders **12px**, while
`src/theme/tokens.ts`, its unit test, and DESIGN.md's machine-readable `rounded:` block all state 4px, and the
contract test in tests/workflow-assistance/test_design_md_is_a_machine_readable_contract.py validates DESIGN.md
against index.css -- the one file whose value the browser ignores. A coherent contract can still describe
pixels that never happen.

The same shape decides `--shadow` and `--shadow-soft`, except there the two declarations are the same colour
written differently, which is formatting rather than drift -- so values are normalised before they are compared,
and a name that agrees after normalisation is not reported.
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path

SHEETS = ("apps/observer/frontend/src/index.css",
          "apps/observer/frontend/src/skins/b10.css",
          "apps/observer/frontend/src/skins/l10b-shell.css")
DECL = re.compile(r"(--[a-z0-9]+(?:-[a-z0-9]+)*)\s*:\s*([^;{}]+)")
COMMENT = re.compile(r"/\*.*?\*/", re.S)
NUMBER = re.compile(r"(-?\d*\.?\d+)")
# A hex colour has to survive `normalise` verbatim: it is a literal, not arithmetic. Lowercasing happens
# before this runs, so only lowercase digits matter here. The negative lookahead keeps `#ff` from matching
# inside a longer run like `#fff0`.
HEX_LITERAL = re.compile(r"#[0-9a-f]{3,8}(?![0-9a-f])")
# a declaration belongs to a theme scope only when its enclosing selector says so; anything else (a component
# rule that happens to set a variable) is judged in the "local" bucket, because a component override is a
# different claim from a theme token and must not be compared against :root
THEME_OF = (("^html.light", "light"), ("^:root", "dark"), ("^\\[data-theme=.?light", "light"),
            ("^\\[data-theme=.?dark", "dark"))
MIN_NAMES = 40
MIN_SCOPED = 30


def normalise(value: str) -> str:
    """Canonical spacing and numbers, so rgba(0, 0, 0, 0.35) and rgba(0,0,0,.35) are one value.

    Numbers are rewritten where they stand rather than by splitting on commas: a comma split leaves the
    leading `rgba(0` and the trailing `0.35)` glued to punctuation, which is exactly the pair this function
    has to equate (measured on the shipped sheets, --shadow and --shadow-soft differ only this way).

    Hex colours are literals, not numbers, and are hidden before the rewrite. Measured 2026-10-14: the
    rewrite turned `#050d16` into `#50d16` — a leading zero is its own digit run — so a VALID colour would
    have compared EQUAL to an invalid one, and a real collision between `#050d16` and `#50d16` would have
    been published as agreement. The placeholders are private-use characters: no digits, so the number
    rewrite cannot reach them either.
    """
    text = " ".join(value.split()).lower()
    text = re.sub(r"\s*([(),])\s*", r"\1", text)
    hidden: list[str] = []

    def hide(match: re.Match[str]) -> str:
        hidden.append(match.group(0))
        return chr(0xE000 + len(hidden) - 1)

    text = HEX_LITERAL.sub(hide, text)
    text = NUMBER.sub(lambda match: f"{float(match.group(1)):g}", text)
    for index, original in enumerate(hidden):
        text = text.replace(chr(0xE000 + index), original)
    return text


def selector_of(stack: list[str]) -> str:
    return " ".join((stack[-1] if stack else "").split())


def theme_of(selector: str) -> str:
    for pattern, theme in THEME_OF:
        if re.search(pattern, selector):
            return theme
    return "local"


def declarations(text: str) -> list[tuple[str, str, str]]:
    """(theme, name, normalised value) walking a sheet and tracking the enclosing selector."""
    text = COMMENT.sub("", text)
    stack: list[str] = []
    buffer = ""
    out: list[tuple[str, str, str]] = []
    for ch in text:
        if ch == "{":
            stack.append(selector_of([buffer]))
            buffer = ""
        elif ch == "}":
            if stack:
                stack.pop()
            buffer = ""
        elif ch == ";":
            statement = " ".join(buffer.split())
            match = DECL.fullmatch(statement) if statement else None
            if match:
                out.append((theme_of(stack[-1] if stack else ""), match.group(1),
                            normalise(match.group(2))))
            buffer = ""
        else:
            buffer += ch
    return out


def collect(root: Path) -> dict[tuple[str, str], dict[str, list[str]]]:
    """(theme, name) -> {sheet: [values]} over the shipped sheets."""
    found: dict[tuple[str, str], dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
    for sheet in SHEETS:
        path = root / sheet
        if not path.is_file():
            continue
        for theme, name, value in declarations(path.read_text(encoding="utf-8")):
            found[(theme, name)][sheet].append(value)
    return found


def collisions(found) -> list[tuple[str, str, dict[str, list[str]]]]:
    """Names declared by more than one sheet in the same theme with values that do not agree."""
    out = []
    for (theme, name), by_sheet in found.items():
        if theme == "local" or len(by_sheet) < 2:
            continue
        distinct = {value for values in by_sheet.values() for value in values}
        if len(distinct) > 1:
            out.append((theme, name, dict(by_sheet)))
    return sorted(out)


def repo_root() -> Path:
    current = Path(__file__).resolve()
    for parent in [current, *current.parents]:
        if (parent / ".git").exists() and (parent / "services").is_dir():
            return parent
    raise SystemExit("CSS_TOKEN_MIRROR_FAIL cannot locate WORK-LAB root")


def main(argv: list[str] | None = None) -> int:
    root = repo_root()
    found = collect(root)
    themed = [key for key in found if key[0] != "local"]
    bad = collisions(found)
    print(f"CSS_TOKEN_MIRROR_TOTAL names={len({name for _, name in found})} "
          f"scoped_declarations={len(themed)} sheets={len(SHEETS)} collisions={len(bad)}")
    if len({name for _, name in found}) < MIN_NAMES:
        print(f"CSS_TOKEN_MIRROR_FAIL the sheets produced {len({name for _, name in found})} custom "
              f"properties, below the measured floor {MIN_NAMES} -- a parser that reads almost nothing "
              "cannot report a clean tree")
        return 1
    if len(themed) < MIN_SCOPED:
        # measured on the first run of this guard: the selector was captured with its leading newline, so
        # nothing matched a theme scope, every declaration landed in "local", and the guard printed a
        # spotless collisions=0 over a real defect. A theme classifier that classifies nothing is broken.
        print(f"CSS_TOKEN_MIRROR_FAIL only {len(themed)} declarations were placed in a theme scope, below "
              f"the measured floor {MIN_SCOPED} -- the walker is not reading the selectors, so no "
              "collision could be found")
        return 1
    for theme, name, by_sheet in bad:
        where = " | ".join(f"{Path(sheet).name}={values}" for sheet, values in sorted(by_sheet.items()))
        print(f"  CSS_TOKEN_MIRROR_COLLISION theme={theme} {name} {where}")
    if bad:
        print("CSS_TOKEN_MIRROR_FAIL one name carries different values per sheet in the same theme; the "
              "cascade decides which renders, and the token records and the contract test do not know")
        return 1
    print("CSS_TOKEN_MIRROR_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
