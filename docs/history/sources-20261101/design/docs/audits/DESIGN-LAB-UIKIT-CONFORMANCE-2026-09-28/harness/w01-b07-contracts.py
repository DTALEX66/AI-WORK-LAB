#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W01 — read the B07 DESIGN-LAB front-end governance contracts and diff them
against the current workbench's own route/page surface."""
from __future__ import annotations

import json
import re
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
B07 = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/ui-originals/B07"


def j(rel):
    return json.loads((B07 / rel).read_text(encoding="utf-8"))


print("=" * 78)
print("B07 component-registry.json")
print("=" * 78)
reg = j("shared-ui-core/component-registry.json")
print("top keys:", list(reg))


def outline(o, depth=0, maxd=2):
    pad = "  " * depth
    if isinstance(o, dict):
        for k, v in list(o.items())[:20]:
            n = f" [{len(v)}]" if isinstance(v, (list, dict)) else ""
            print(f"{pad}{k} <{type(v).__name__}{n}>")
            if depth < maxd:
                outline(v, depth + 1, maxd)
    elif isinstance(o, list) and o and depth < maxd:
        outline(o[0], depth + 1, maxd)


outline(reg, 0, 1)

print("\n" + "=" * 78)
print("B07 routes / pages / state-machine")
print("=" * 78)
for f in ("routes/routes.json", "pages/page-map.json", "state/domain-state-machine.json"):
    d = j(f)
    print(f"\n--- {f}  keys={list(d)[:8]}")
    print("   ", json.dumps(d, ensure_ascii=False)[:600])

print("\n" + "=" * 78)
print("路由对比：B07 原稿  vs  workbench 实现")
print("=" * 78)
b07_routes = j("routes/routes.json")
def collect_routes(o, acc):
    if isinstance(o, dict):
        if "path" in o and isinstance(o["path"], str):
            acc.append((o.get("id") or o.get("name") or "", o["path"]))
        for v in o.values():
            collect_routes(v, acc)
    elif isinstance(o, list):
        for v in o:
            collect_routes(v, acc)
acc: list = []
collect_routes(b07_routes, acc)
print("B07 routes:", acc or json.dumps(b07_routes, ensure_ascii=False)[:400])

shell = (ROOT / "apps/workbench/shell.ts").read_text(encoding="utf-8")
impl = re.findall(r"\{ route: '([^']+)', label: '([^']+)', hash: '([^']+)' \}", shell)
print("\n实现 (shell.ts B10_NAV):")
for r, l, h in impl:
    print(f"   {h:<20} {l:<12} view={r}")
print(f"\n   B07 routes={len(acc)}   impl routes={len(impl)}")

print("\n" + "=" * 78)
print("Token 承载情况：原稿有哪些族，实现有没有")
print("=" * 78)
base = (B07 / "shared-ui-core/base-tokens.css").read_text(encoding="utf-8")
theme = (B07 / "theme/tokens.css").read_text(encoding="utf-8")
orig_fams = {
    "color": re.findall(r"(--color-[a-z0-9-]+):", theme),
    "radius": re.findall(r"(--radius-[a-z]+):", theme),
    "space": re.findall(r"(--space-[0-9]+):", base),
    "font": re.findall(r"(--font-[a-z0-9]+):", base),
    "motion": re.findall(r"(--motion-[a-z]+):", base),
    "breakpoint": re.findall(r"(--bp-[a-z]+):", base),
}
css = (ROOT / "apps/workbench/style.css").read_text(encoding="utf-8")
print(f"{'family':<12}{'orig':>5}{'impl':>6}   missing in impl")
for fam, names in orig_fams.items():
    missing = [n for n in names if n not in css]
    print(f"{fam:<12}{len(names):>5}{len(names)-len(missing):>6}   {', '.join(missing) or '-'}")

b04 = json.loads((ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928"
                  "/ui-originals/B04/DESIGN-LAB_design_tokens.json").read_text(encoding="utf-8"))
print("\nB04 density 原稿:", b04.get("density"), " -> 实现中出现 --density:",
      "--density" in css)
print("B04 radius 原稿  :", b04.get("radius"), " -> 实现 radius-xl:", "--radius-xl" in css)
print("B04 typography   :", b04.get("typography"))
print("B07 base --font-*:", dict(re.findall(r"(--font-[a-z0-9]+):\s*([0-9]+px)", base)))
print("  ^ B04 与 B07 在 body/caption 上不一致 —— 原稿之间自相矛盾")
