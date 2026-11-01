#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W02 step 1 — coverage of B07's 45-component contract by what already exists.

Answers the question that must precede any component-library decision:
"can the existing CSS/DOM express B07's 45 components and their 4 states?"
Only if the answer is 'no, and here is exactly what is missing' is evaluating an
external library justified.

Also cross-checks a hypothesis: B10's extracted-style.css ships 28 classes that
B10's own HTML never renders ("library extras"). Some of those may be exactly the
component primitives B07's registry requires.

Read-only. No file is written except the JSON evidence dump.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
UI = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals"
STYLE = (ROOT / "apps/workbench/style.css").read_text(encoding="utf-8")
SHELL = (ROOT / "apps/workbench/shell.ts").read_text(encoding="utf-8")
B10HTML = (UI / "B10/index.html").read_text(encoding="utf-8")
# B10 ships NO separate CSS file: the stylesheet is inline in index.html.
# (Verified in round 1: that inline block is line-identical to the previously
# extracted extracted-style.css, 520/520 lines, 0 diffs.)
_s = B10HTML.index("<style>")
_e = B10HTML.index("</style>")
B10CSS = B10HTML[_s + len("<style>"):_e]

registry = json.loads((UI / "B07/shared-ui-core/component-registry.json").read_text(encoding="utf-8"))
components = [c["component"] for c in registry]
families = {c["component"]: c["family"] for c in registry}

# Candidate evidence per B07 component: CSS class selectors that should exist,
# plus DOM markers in shell.ts. Empty list = no candidate identified.
CAND: dict[str, dict[str, list[str]]] = {
    "AppShell":            {"css": [".app"], "dom": ["class: 'app'"]},
    "Sidebar":             {"css": [".sidebar"], "dom": ["class: 'sidebar'"]},
    "Topbar":              {"css": [".topbar"], "dom": ["class: 'topbar'"]},
    "Breadcrumb":          {"css": [], "dom": []},
    "Tabs":                {"css": [], "dom": []},
    "CommandPalette":      {"css": [".palette"], "dom": ["class: 'palette'"]},
    "Button":              {"css": [".primary-btn", ".ghost-btn"], "dom": ["class: 'primary-btn'"]},
    "IconButton":          {"css": [".icon"], "dom": []},
    "Input":               {"css": [".input"], "dom": ["class: 'input"]},
    "SearchInput":         {"css": [".search"], "dom": ["class: 'search'"]},
    "Select":              {"css": [], "dom": []},
    "MultiSelect":         {"css": [], "dom": []},
    "TagInput":            {"css": [], "dom": []},
    "DateRange":           {"css": [], "dom": []},
    "Card":                {"css": [".panel"], "dom": ["class: 'panel"]},
    "KPI":                 {"css": [".kpi"], "dom": ["class: 'panel kpi'"]},
    "Table":               {"css": [".table", ".table-wrap"], "dom": ["class: 'table"]},
    "List":                {"css": [".list", ".list-item"], "dom": ["class: 'list"]},
    "Tree":                {"css": [], "dom": []},
    "Timeline":            {"css": [], "dom": []},
    "Graph":               {"css": [".graph-stage"], "dom": []},
    "Badge":               {"css": [".tag"], "dom": ["class: 'tag"]},
    "Avatar":              {"css": [".avatar"], "dom": ["class: 'avatar'"]},
    "Progress":            {"css": [".progress"], "dom": ["class: 'progress'"]},
    "Toast":               {"css": [".toast"], "dom": ["class: 'toast'"]},
    "InlineAlert":         {"css": [], "dom": []},
    "EmptyState":          {"css": [".empty"], "dom": []},
    "LoadingSkeleton":     {"css": [], "dom": ["class: 'view-loading'"]},
    "ErrorState":          {"css": [], "dom": ["class: 'error'"]},
    "OfflineState":        {"css": [], "dom": ["id: 'b10-offline'"]},
    "Modal":               {"css": [".modal", ".overlay"], "dom": ["class: 'modal'", "class: 'overlay'"]},
    "Drawer":              {"css": [".drawer"], "dom": ["class: 'drawer'"]},
    "Popover":             {"css": [], "dom": []},
    "ContextMenu":         {"css": [], "dom": []},
    "Tooltip":             {"css": [], "dom": []},
    "ConfirmDialog":       {"css": [], "dom": []},
    "ApprovalStep":        {"css": [], "dom": []},
    "VersionCompare":      {"css": [], "dom": []},
    "ConflictResolver":    {"css": [], "dom": []},
    "PermissionGate":      {"css": [], "dom": []},
    "AuditEvent":          {"css": [], "dom": []},
    "PageHeader":          {"css": [".page-head"], "dom": ["class: 'page-head'"]},
    "Section":             {"css": [], "dom": []},
    "SplitPane":           {"css": [".split"], "dom": []},
    "ResizablePanel":      {"css": [], "dom": []},
    "ResponsiveGrid":      {"css": [".responsive-grid"], "dom": []},
}

rows, have_css, have_dom, have_any, missing = [], 0, 0, 0, []
for name in components:
    spec = CAND.get(name, {"css": [], "dom": []})
    css_hits = [s for s in spec["css"] if re.search(re.escape(s) + r"(?![a-zA-Z0-9_-])", STYLE)]
    dom_hits = [s for s in spec["dom"] if s in SHELL]
    ok = bool(css_hits) or bool(dom_hits)
    if css_hits:
        have_css += 1
    if dom_hits:
        have_dom += 1
    if ok:
        have_any += 1
    else:
        missing.append(name)
    rows.append({"component": name, "family": families[name], "css": css_hits,
                 "dom": dom_hits, "covered": ok})

print("=" * 92)
print("W02-1  B07 45-COMPONENT CONTRACT  vs  EXISTING CSS/DOM")
print("=" * 92)
print(f"  B07 components        : {len(components)}")
print(f"  covered (css or dom)  : {have_any}/{len(components)}")
print(f"  covered by CSS class  : {have_css}")
print(f"  covered by DOM marker : {have_dom}")

by_fam: dict[str, list] = {}
for r in rows:
    by_fam.setdefault(r["family"], []).append(r)
print("\n--- per family ---")
for fam in sorted(by_fam):
    tot = len(by_fam[fam])
    ok = sum(1 for r in by_fam[fam] if r["covered"])
    print(f"  {fam:<12} {ok}/{tot}")

print(f"\n--- COVERED ({have_any}) ---")
for r in rows:
    if r["covered"]:
        print(f"  {r['component']:<18} fam={r['family']:<11} css={','.join(r['css']) or '-':<22} dom={','.join(r['dom']) or '-'}")

print(f"\n--- NOT COVERED ({len(missing)}) ---")
for m in missing:
    print(f"  {m:<18} fam={families[m]}")

# ---------------------------------------------------------------- hypothesis
print("\n" + "=" * 92)
print("W02-1b  HYPOTHESIS: B10 ships 'library extras' that B07's registry needs")
print("=" * 92)
b10_classes = sorted(set(re.findall(r"\.([a-zA-Z][a-zA-Z0-9_-]*)", B10CSS)))
b10_used = set(re.findall(r'class="([^"]*)"', B10HTML))
used_flat = {c for group in b10_used for c in group.split()}
extras = [c for c in b10_classes if c not in used_flat]
print(f"  B10 CSS classes        : {len(b10_classes)}")
print(f"  B10 HTML actually uses : {len(used_flat)}")
print(f"  B10 'library extras'   : {len(extras)}  {extras}")
hit = [e for e in extras if re.search(r"\." + re.escape(e) + r"(?![a-zA-Z0-9_-])", STYLE)]
print(f"  of those, present in workbench style.css: {len(hit)}  {hit}")

dst = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/W02-COMPONENT-COVERAGE.json"
dst.write_text(json.dumps({
    "sha": "d116b14995fcdbba1b165ec5bc3124f5daed3d15",
    "question": "can existing CSS/DOM express B07's 45 components before any library is chosen?",
    "totals": {"components": len(components), "covered": have_any,
               "covered_by_css": have_css, "not_covered": len(missing)},
    "by_family": {f: {"total": len(v), "covered": sum(1 for r in v if r["covered"])}
                  for f, v in by_fam.items()},
    "rows": rows, "not_covered": missing,
    "b10_library_extras": {"count": len(extras), "names": extras,
                           "present_in_workbench": hit},
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
