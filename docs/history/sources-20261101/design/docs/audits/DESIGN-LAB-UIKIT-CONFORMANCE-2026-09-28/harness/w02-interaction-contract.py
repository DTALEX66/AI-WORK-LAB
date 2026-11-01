#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W02 — diff B07's "Shared interaction contract" (component-contracts.md) and
shared-ui-core utilities against the current implementation.

The interaction contract carries concrete numbers, so each can be checked:
  Hover 120ms / Focus 2px ring + 2px offset / Pressed scale(0.99) 80ms /
  Modal 220ms / Drawer 280ms / Toast 4s / Cmd-Ctrl+K / Escape closes topmost.

Also records a defect in the ORIGINAL: `.responsive-grid` is only ever given
`grid-template-columns` -- B07 never declares `display:grid` for it, so the
class cannot function as published.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
UI = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals"
STYLE = (ROOT / "apps/workbench/style.css").read_text(encoding="utf-8")
SHELL = (ROOT / "apps/workbench/shell.ts").read_text(encoding="utf-8")
B07 = UI / "B07"

bp = (B07 / "shared-ui-core/breakpoints.css").read_text(encoding="utf-8")
mo = (B07 / "shared-ui-core/motion.css").read_text(encoding="utf-8")


def rule(css: str, sel_regex: str) -> str | None:
    m = re.search(r"([^{}]*?" + sel_regex + r"[^{}]*?)\{([^{}]*)\}", css)
    return " ".join(m.group(2).split()) if m else None


print("=" * 90)
print("B07 shared-ui-core UTILITIES  vs  implementation")
print("=" * 90)
UTILS = {
    "responsive-grid (base display:grid)": r"\.responsive-grid(?![a-zA-Z0-9_-])",
    "desktop-only": r"\.desktop-only(?![a-zA-Z0-9_-])",
    "ui-motion-fast": r"\.ui-motion-fast(?![a-zA-Z0-9_-])",
    "ui-motion-base": r"\.ui-motion-base(?![a-zA-Z0-9_-])",
    "ui-motion-slow": r"\.ui-motion-slow(?![a-zA-Z0-9_-])",
    "focus-ring": r"\.focus-ring(?![a-zA-Z0-9_-])",
    "pressable": r"\.pressable(?![a-zA-Z0-9_-])",
}
for label, rx in UTILS.items():
    in_origin = bool(re.search(rx, bp) or re.search(rx, mo))
    impl = re.search(rx, STYLE)
    print(f"  {label:<34} origin={'Y' if in_origin else 'n'}  impl={'Y' if impl else 'N'}")
print("\n  NOTE: B07 sets grid-template-columns for .responsive-grid in three media")
print("        queries but NEVER declares display:grid -> the published class cannot")
print("        work on its own. That is a defect in the original, recorded not hidden.")

print("\n" + "=" * 90)
print("B07 'Shared interaction contract'  vs  implementation")
print("=" * 90)
CHECKS = [
    ("Hover 120ms", "transition:.2s ease",
     rule(STYLE, r"\.ghost-btn,\.soft-btn,\.primary-btn,\.danger-btn")),
    ("Focus ring 2px + offset 2px", "outline:2px solid; outline-offset:2px",
     rule(STYLE, r"input:focus,select:focus,button:focus-visible")),
    ("Drawer 280ms", "0.28s", rule(STYLE, r"\.drawer(?![a-zA-Z0-9_-])")),
    ("Modal 220ms", "220ms / .22s", rule(STYLE, r"\.modal(?![a-zA-Z0-9_-])")),
    ("Toast 4s default", "4000ms", "(JS timer in shell.ts)"),
]
for label, expected, actual in CHECKS:
    print(f"  {label:<32} 契约={expected:<24} 实现={actual}")

print("\n  Toast timer in shell.ts:")
for m in re.finditer(r"setTimeout\(\(\) => toast\.classList\.remove\('show'\), (\d+)\)", SHELL):
    print(f"    {m.group(1)} ms")
print("\n  Escape closes topmost overlay:")
print("    ", "Y" if "e.key === 'Escape'" in SHELL else "N",
      "(shell.ts keydown handler)")
print("  Cmd/Ctrl+K command palette:")
print("    ", "Y" if "(e.ctrlKey || e.metaKey)" in SHELL and "'k'" in SHELL else "N")

print("\n" + "=" * 90)
print("B07 folder-structure.md / PageTemplate example")
print("=" * 90)
print((B07 / "shared-ui-core/folder-structure.md").read_text(encoding="utf-8"))
print("--- examples/PageTemplate.tsx ---")
print((B07 / "examples/PageTemplate.tsx").read_text(encoding="utf-8"))
