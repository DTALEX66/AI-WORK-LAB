#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 — final crosswalk (rev 3). Fixes rev2's multi-W table cells.

rev 3 fix: §2 rows like `|DL-UI-09 / DL-UI-10|W02/W03/W14|` carry SEVERAL W
values; rev 2's regex required a single `W\\d\\d` and silently dropped 7 such
rows, so 7 DL-* ids (DL-BE-01/03/05/06, DL-UI-04/09/10) were missing from the
crosswalk -- and those are precisely the ones feeding the first waves.

Also emits the Wave-A (W00-W03) first-batch scope with verified paths.
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
ID_RE = re.compile(r"(DL-R5|DL(?:-[A-Z]+)?|R5)-(\d+)")


def expand(tokens: str) -> list[str]:
    out, last = [], None
    for chunk in re.split(r"[；;，,、\s]+", tokens.strip().rstrip("。")):
        if not chunk:
            continue
        for part in chunk.split("/"):
            part = part.strip()
            if not part:
                continue
            m = ID_RE.fullmatch(part)
            if m:
                last = m.group(1)
                out.append(f"{last}-{m.group(2)}")
            elif re.fullmatch(r"\d+", part) and last:
                out.append(f"{last}-{part}")
    return out


def norm_r5(t: str) -> str:
    return t if t.startswith("DL-R5-") else "DL-" + t


blocks: dict[str, dict] = {}
for m in re.finditer(r"^### (W\d\d)｜(.+?)（([^）]*)）\s*$(.*?)(?=^### |\Z)", text, re.M | re.S):
    wid, title, prio, body = m.group(1), m.group(2), m.group(3), m.group(4)
    maps = re.search(r"^- 映射：(.*)$", body, re.M)
    deps = re.search(r"^- 依赖：(.*)$", body, re.M)
    blocks[wid] = {
        "title": title, "priority": prio,
        "maps_raw": maps.group(1).strip() if maps else "",
        "depends_raw": deps.group(1).strip() if deps else "",
        "path_lines": [l.split("：", 1)[1].strip() for l in body.splitlines()
                       if re.match(r"^- (目标位置|位置)：", l)],
    }

w_to_r5, w_to_dl = {}, {}
for wid, b in blocks.items():
    toks = expand(b["maps_raw"])
    w_to_r5[wid] = sorted({norm_r5(t) for t in toks if t.startswith(("R5-", "DL-R5-"))})
    w_to_dl[wid] = sorted({t for t in toks if t.startswith("DL-") and not t.startswith("DL-R5-")})

# §2 table — allow MODULE rows AND multi-W value cells
dl_to_w: dict[str, list[str]] = defaultdict(list)
for m in re.finditer(r"^\|\s*(DL-[^|]+?)\s*\|\s*(W\d\d(?:/W\d\d)*)\s*\|", text, re.M):
    for dl in expand(m.group(1)):
        for w in m.group(2).split("/"):
            w = w.strip()
            if w and w not in dl_to_w[dl]:
                dl_to_w[dl].append(w)

ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
r5_ids = [t["id"] for t in ledger["tasks"]]
r5_by_id = {t["id"]: t for t in ledger["tasks"]}
r5_title = {t["id"]: t["title"] for t in ledger["tasks"]}

dl_to_r5 = {dl: sorted({r for w in ws for r in w_to_r5.get(w, [])}) for dl, ws in dl_to_w.items()}
r5_to_dl: dict[str, set[str]] = defaultdict(set)
for dl, rs in dl_to_r5.items():
    for r in rs:
        r5_to_dl[r].add(dl)

covered = [r for r in r5_ids if r in r5_to_dl]
uncovered = [r for r in r5_ids if r not in r5_to_dl]
pack_r5 = sorted({r for rs in w_to_r5.values() for r in rs})
not_in_ledger = [r for r in pack_r5 if r not in r5_by_id]

print("=" * 78)
print("W00 FINAL  DL-* -> W -> DL-R5-* crosswalk   (DERIVED; needs ratification)")
print("=" * 78)
print(f"\nW blocks                : {len(blocks)}")
print(f"distinct DL-* in §2     : {len(dl_to_w)}   <- pack claims 41")
print(f"distinct R5 in §1       : {len(pack_r5)}")
print(f"R5 in ledger            : {len(r5_ids)}")
print(f"pack R5 not in ledger   : {not_in_ledger or 'none'}")
print(f"R5 COVERED by the pack  : {len(covered)}/28")
print(f"R5 UNCOVERED            : {len(uncovered)}/28")

print("\n--- COVERED R5 -> W (what work package feeds which ledger task) ---")
for r in covered:
    ws = sorted({w for dl in r5_to_dl[r] for w in dl_to_w.get(dl, [])})
    print(f"  {r}  {r5_title[r][:26]:<28} W={','.join(ws)}")

print("\n--- UNCOVERED R5 (the pack says nothing about these) ---")
for r in uncovered:
    print(f"  {r}  {r5_title[r]}")

print("\n--- Wave A first batch (W00-W03) scope ---")
for w in ("W00", "W01", "W02", "W03"):
    b = blocks[w]
    print(f"\n  {w} [{b['priority']}] {b['title']}")
    print(f"    depends : {b['depends_raw']}")
    print(f"    R5      : {', '.join(x.replace('DL-','') for x in w_to_r5[w]) or '-'}")
    print(f"    DL      : {', '.join(w_to_dl[w]) or '-'}")
    for pl in b["path_lines"]:
        for tok in re.split(r"[、,，;；\s]+", pl):
            tok = tok.strip().strip("。（）()")
            if re.fullmatch(r"[A-Za-z0-9_./\-]+", tok) and "/" in tok:
                print(f"    path    : {'OK  ' if (ROOT/tok).exists() else 'MISS'} {tok}")

dst = PACK.parent / "W00-CROSSWALK.json"
dst.write_text(json.dumps({
    "provenance": "DERIVED from 02_EXECUTION_TASKS.md; NOT authoritative; needs owner ratification (AGENTS.md).",
    "notation_finding": "pack writes 'R5-NNN'; ledger writes 'DL-R5-NNN' (same entity). Normalise or nothing matches.",
    "w_blocks": blocks, "w_to_r5": w_to_r5, "w_to_dl": w_to_dl,
    "dl_to_w": dict(dl_to_w), "dl_to_r5": dl_to_r5,
    "r5_covered": covered, "r5_uncovered": uncovered,
    "pack_r5_not_in_ledger": not_in_ledger,
    "wave_a": ["W00", "W01", "W02", "W03"],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
