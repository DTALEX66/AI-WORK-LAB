#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W02 step 2 — read the CSS of B10's 28 'library extras' and judge which of
B07's 21 uncovered components they can actually serve.

Doing this BEFORE choosing a library matters: if the primitives already exist,
the honest answer to "do we need Spectrum Web Components?" may be 'not for these'.
"""
from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
UI = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals"
STYLE = (ROOT / "apps/workbench/style.css").read_text(encoding="utf-8")
B10HTML = (UI / "B10/index.html").read_text(encoding="utf-8")
B10CSS = B10HTML[B10HTML.index("<style>") + 7:B10HTML.index("</style>")]

EXTRAS = ['active', 'back', 'bad', 'big-number', 'canvas', 'core', 'danger-btn', 'empty',
          'flipped', 'flow-svg', 'graph-stage', 'icon', 'label', 'meta', 'metric-box',
          'metric-ring', 'metric-row', 'mono', 'node', 'node-dot', 'open', 'review-card',
          'review-face', 'review-inner', 'seg', 'show', 'soft-btn', 'title']

print("=" * 92)
print("B10 'library extras' — actual CSS rules (present in workbench style.css)")
print("=" * 92)
for name in EXTRAS:
    rules = []
    for m in re.finditer(r"([^{}]*?\." + re.escape(name) + r"(?![a-zA-Z0-9_-])[^{}]*?)\{([^{}]*)\}",
                         B10CSS):
        sel = " ".join(m.group(1).split())
        body = " ".join(m.group(2).split())
        rules.append(f"      {sel} {{ {body[:150]} }}")
    print(f"\n  .{name}")
    for r in (rules[:4] or ["      (no standalone rule in B10 CSS)"]):
        print(r)

print("\n" + "=" * 92)
print("REFINED MAPPING — B07 uncovered components vs available B10 primitives")
print("=" * 92)
REFINED = {
    "Tabs":            (".seg", "B10 .seg is a segmented control (button group) — Tabs could reuse it"),
    "Section":         (".metric-row / .metric-box", "metric grid primitives exist as layout containers"),
    "InlineAlert":     (".soft-btn?", "no alert primitive; .soft-btn is a button variant"),
    "Tree":            (".node / .node-dot", "B10 node primitives exist (graph nodes, not a tree view)"),
    "Timeline":        (".review-card?", "review-card is a 3D flip card, not a timeline"),
    "Popover":         (".overlay?", "overlay/modal exist; popover is a distinct anchored surface"),
    "ContextMenu":     (".palette?", "palette is a command list, not an anchored context menu"),
    "Tooltip":         ("none", "no tooltip primitive"),
    "ConfirmDialog":   (".modal", "modal exists and IS used for confirmation today"),
    "Breadcrumb":      ("none", "no breadcrumb primitive"),
    "Select":          ("none", "native <select> used; no styled combobox primitive"),
    "MultiSelect":     ("none", "absent"),
    "TagInput":        ("none", "absent"),
    "DateRange":       ("none", "absent"),
    "ApprovalStep":    ("none", "workflow family entirely absent"),
    "VersionCompare":  ("none", "workflow family entirely absent"),
    "ConflictResolver": ("none", "workflow family entirely absent"),
    "PermissionGate":  ("none", "workflow family entirely absent"),
    "AuditEvent":      ("none", "workflow family entirely absent"),
    "ResizablePanel":  (".split?", ".split is a static 2-col grid, not resizable"),
    "ResponsiveGrid":  (".metric-row?", "metric-row is a fixed 4-col grid; B07 wants 1/2/12 responsive"),
}
served, absent = [], []
for comp, (prim, note) in REFINED.items():
    real = prim.strip("?").split(" / ")[0]
    # real already carries the leading dot; escape only the bare name
    bare = real.lstrip(".")
    ok = bool(bare) and real != "none" and re.search(
        r"\." + re.escape(bare) + r"(?![a-zA-Z0-9_-])", STYLE)
    # a primitive scoped under another class (e.g. `.toolbar .seg`) is NOT a
    # standalone reusable primitive -- report that distinction honestly
    scoped = re.search(r"[.#][a-zA-Z0-9_-]+\s+\.?" + re.escape(bare) + r"(?![a-zA-Z0-9_-])", STYLE)
    tag = "PARTIAL" if ok else "ABSENT "
    if ok and scoped:
        tag = "SCOPED "
    (served if ok else absent).append(comp)
    print(f"  {comp:<18} primitive={prim:<24} {tag:8} {note}")

print(f"\n  can be partially served by an existing B10 primitive : {len(served)}  {served}")
print(f"  genuinely absent (no primitive at all)               : {len(absent)}  {absent}")
print(f"\n  => B07 coverage after refinement: {25 + len(served)}/46"
      f"  (25 already covered + {len(served)} reusable primitives)")
print(f"  => genuinely missing contract items: {len(absent)}/46")
