#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 — build the DL-* -> W -> DL-R5-* crosswalk and audit path existence.

Provenance discipline: this crosswalk is DERIVED from the task pack itself
(§1 per-W "映射:" lines give W->R5; §2 table gives DL-*->W). It is NOT an
authoritative crosswalk; AGENTS.md requires one before dispatch, so this
artifact is the candidate for owner ratification. Every derivation is printed
so a reviewer can check each edge.

Also audits: does every path the pack names actually exist in this checkout?
"""
from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(r"D:\All projects\DESIGN-LAB")
PACK = ROOT / ".project-local/task-artifacts/designlab-followup-taskpack-20260928/02_EXECUTION_TASKS.md"
LEDGER = ROOT / "design-lab/config/task-ledger-r3.json"

text = PACK.read_text(encoding="utf-8")

# ---------------------------------------------------------------- W blocks
blocks: dict[str, dict] = {}
for m in re.finditer(r"^### (W\d\d)｜(.+?)（([^）]*)）\s*$(.*?)(?=^### |\Z)",
                     text, re.M | re.S):
    wid, title, prio, body = m.group(1), m.group(2), m.group(3), m.group(4)
    maps = re.search(r"^- 映射：(.*)$", body, re.M)
    paths = []
    for line in body.splitlines():
        if re.match(r"^- (目标位置|位置|读取)：", line):
            paths.append(line.split("：", 1)[1].strip())
    blocks[wid] = {"title": title, "priority": prio,
                   "maps_raw": maps.group(1).strip() if maps else "",
                   "path_lines": paths}


def expand(tokens: str) -> list[str]:
    """'DL-UI-04/09/10' -> DL-UI-04, DL-UI-09, DL-UI-10 ; 'R5-010/028' -> ..."""
    out: list[str] = []
    for raw in re.split(r"[；;，,、\s]+", tokens):
        raw = raw.strip().rstrip("。")
        if not raw:
            continue
        m = re.fullmatch(r"(DL(?:-[A-Z]+)?|R5)-(\d{2,3}(?:/\d{2,3})*)", raw)
        if m:
            prefix, nums = m.group(1), m.group(2)
            for n in nums.split("/"):
                out.append(f"{prefix}-{n}")
        elif re.fullmatch(r"DL-\d+", raw):
            out.append(raw)
    return out


w_to_r5: dict[str, list[str]] = {}
w_to_dl: dict[str, list[str]] = {}
for wid, b in blocks.items():
    toks = expand(b["maps_raw"])
    w_to_r5[wid] = [t for t in toks if t.startswith("R5-")]
    w_to_dl[wid] = [t for t in toks if t.startswith("DL")]

# ------------------------------------------------------------- §2 table
dl_to_w: dict[str, list[str]] = defaultdict(list)
for m in re.finditer(r"^\|(DL-[^|]+)\|(W\d\d)\|", text, re.M):
    dlcell, wid = m.group(1).strip(), m.group(2).strip()
    for dl in expand(dlcell):
        dl_to_w[dl].append(wid)

# ------------------------------------------------------------- ledger
ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
r5_ids = [t["id"] for t in ledger["tasks"]]
r5_by_id = {t["id"]: t for t in ledger["tasks"]}

# ------------------------------------------------------------- compose
dl_to_r5: dict[str, set[str]] = {}
for dl, ws in dl_to_w.items():
    acc: set[str] = set()
    for w in ws:
        acc.update(w_to_r5.get(w, []))
    dl_to_r5[dl] = acc

r5_to_dl: dict[str, set[str]] = defaultdict(set)
for dl, r5s in dl_to_r5.items():
    for r in r5s:
        r5_to_dl[r].add(dl)

covered = sorted(r for r in r5_ids if r in r5_to_dl)
uncovered = sorted(r for r in r5_ids if r not in r5_to_dl)

print("=" * 78)
print("W00-3  CROSSWALK  DL-* -> W -> DL-R5-*   (DERIVED, not authoritative)")
print("=" * 78)
print(f"\nW blocks parsed      : {len(blocks)}  ({', '.join(sorted(blocks))})")
print(f"DL-* ids in pack §2  : {len(dl_to_w)}")
print(f"R5 ids in ledger     : {len(r5_ids)}")

print(f"\n--- W -> R5 (from §1 '映射:' lines) ---")
for w in sorted(blocks):
    print(f"  {w}  R5={w_to_r5[w] or '-'}   DL={w_to_dl[w] or '-'}")

print(f"\n--- DL-* -> W -> R5 ---")
for dl in sorted(dl_to_r5, key=lambda s: (s.split('-')[1] if '-' in s else '', s)):
    ws = dl_to_w[dl]
    rs = sorted(dl_to_r5[dl]) or ['-']
    print(f"  {dl:<14} W={','.join(ws):<8} R5={','.join(rs)}")

print(f"\n--- R5 coverage ---")
print(f"  COVERED   ({len(covered):>2}): {', '.join(covered)}")
print(f"  UNCOVERED ({len(uncovered):>2}): {', '.join(uncovered)}")

print(f"\n--- R5 -> DL-* (reverse) ---")
for r in r5_ids:
    print(f"  {r}  <- {sorted(r5_to_dl.get(r, [])) or '(no DL-* mapped)'}")

# ------------------------------------------------------------- path audit
print("\n" + "=" * 78)
print("W00-3b  PATH EXISTENCE AUDIT  (every path the pack names)")
print("=" * 78)
candidates: set[str] = set()
for b in blocks.values():
    for line in b["path_lines"]:
        for tok in re.split(r"[、,，;；\s]+", line):
            tok = tok.strip().strip("。（）()")
            if "/" in tok and not tok.startswith("http"):
                candidates.add(tok)
candidates.update({
    "src/design_lab/design_layer.py", "src/design_lab/workbench.py",
    "apps/workbench/style.css", "apps/workbench/shell.ts", "apps/workbench/main.ts",
    "apps/workbench/workbench.ts", "apps/workbench/index.html", "apps/workbench/design.ts",
    "apps/workbench/vite.config.ts", "apps/workbench/package.json",
    "packages/design-system", "integrations/hosts/adobe", "design-lab/config/task-ledger-r3.json",
    "design-lab/config/adapter-registry.json", "integrations/adapter-registry.json",
    "docs/decisions/NEUTRALITY_POLICY.md", "docs/decisions/EVIDENCE_POLICY.md",
    "docs/decisions/ADAPTER_POLICY.md", "D:/All projects/UI套件",
})
missing = []
for p in sorted(candidates):
    ok = Path(p).exists() if p.startswith("D:") else (ROOT / p).exists()
    if not ok:
        missing.append(p)
    print(f"  {'OK   ' if ok else 'MISS '} {p}")
print(f"\n  candidates={len(candidates)}  missing={len(missing)}")
for p in missing:
    print(f"    MISSING: {p}")

# ------------------------------------------------------------- dump
dst = PACK.parent / "W00-CROSSWALK.json"
dst.write_text(json.dumps({
    "provenance": "DERIVED from 02_EXECUTION_TASKS.md (§1 per-W 映射 lines + §2 mapping table). "
                  "NOT authoritative; AGENTS.md requires an owner-ratified crosswalk before dispatch.",
    "w_blocks": blocks,
    "w_to_r5": w_to_r5,
    "dl_to_w": {k: v for k, v in dl_to_w.items()},
    "dl_to_r5": {k: sorted(v) for k, v in dl_to_r5.items()},
    "r5_ids": r5_ids,
    "r5_covered": covered,
    "r5_uncovered": uncovered,
    "paths_missing": missing,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
