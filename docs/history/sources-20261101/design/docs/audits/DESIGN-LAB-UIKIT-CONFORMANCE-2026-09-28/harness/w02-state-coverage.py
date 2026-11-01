#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W02 — B07's component-registry declares states ['default','hover','focus',
'disabled'] for ALL 46 components. Check which implemented component classes
actually carry each state, and whether `.seg` (the only primitive behind B07's
`Tabs`) is usable outside a toolbar.

Read-only analysis; the fix is a separate CSS change.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
UI = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals"
STYLE = (ROOT / "apps/workbench/style.css").read_text(encoding="utf-8")

registry = json.loads((UI / "B07/shared-ui-core/component-registry.json").read_text(encoding="utf-8"))
states = sorted({s for c in registry for s in c.get("states", [])})
print(f"B07 registry: {len(registry)} components, declared states = {states}")

# implemented component class -> the selector that IS the component
IMPL = {
    "Button":      ".primary-btn|.ghost-btn",
    "Input":       ".input",
    "SearchInput": ".search",
    "Card":        ".panel",
    "KPI":         ".kpi",
    "Table":       ".table",
    "List":        ".list-item",
    "Badge":       ".tag",
    "Avatar":      ".avatar",
    "Progress":    ".progress",
    "Toast":       ".toast",
    "Modal":       ".modal",
    "Drawer":      ".drawer",
    "CommandPalette": ".palette",
    "PageHeader":  ".page-head",
    "Sidebar nav": ".nav button",
    "Tabs(primitive)": ".seg button",
}

print(f"\n{'component':<18}{'default':>8}{'hover':>7}{'focus':>7}{'disabled':>9}   selectors present")
for comp, sel in IMPL.items():
    base = sel.split("|")[0]
    def has(suffix):
        pat = re.escape(base) + re.escape(suffix) + r"(?![a-zA-Z0-9_-])"
        return bool(re.search(pat, STYLE))
    row = {
        "default": has(""),
        "hover": has(":hover"),
        "focus": has(":focus") or has(":focus-visible"),
        "disabled": has(":disabled"),
    }
    print(f"{comp:<18}{str(row['default']):>8}{str(row['hover']):>7}{str(row['focus']):>7}{str(row['disabled']):>9}"
          f"   {sel}")

print("\n" + "=" * 78)
print("`.seg` usability — B10 only ships it scoped to .toolbar")
print("=" * 78)
for pat in (r"\.toolbar \.seg(?![a-zA-Z0-9_-])", r"(?<![\w-])\.seg(?![a-zA-Z0-9_-])"):
    hits = re.findall(pat, STYLE)
    print(f"  pattern {pat!r:<44} matches={len(hits)}")
seg_rules = re.findall(r"([^{}]*\.seg[^{}]*)\{([^{}]*)\}", STYLE)
print("\n  rules mentioning .seg:")
for sel, body in seg_rules:
    print(f"    {' '.join(sel.split())} {{ {' '.join(body.split())[:90]} }}")
print("\n  => B07's `Tabs` maps to the segmented-control primitive, and B10 only")
print("     defines it under `.toolbar`, so it cannot be used standalone.")
