#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 — crosswalk rev 5 (FINAL). Fixes rev4's regression.

rev 4 moved the prefix-inheritance cursor INSIDE the chunk loop, which broke
§2 cells that split across chunks ("DL-WL-01 / 02 / 03 / 04 / 05 / 06"): the
cursor reset after each chunk, so only the first member survived. DL-* count
fell 41 -> 24. rev 5 keeps the 或/及/至 rewrite (rev 4's real fix) AND keeps the
cursor across chunks (rev 3's behaviour).

Verified expectations: DL-* == 41, R5 covered == 18, pack R5 not in ledger == none.
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
    out: list[str] = []
    last: str | None = None            # cursor persists ACROSS chunks (rev 5)
    for chunk in re.split(r"[；;，,、\s]+", tokens.strip().rstrip("。")):
        if not chunk:
            continue
        chunk = re.sub(r"[或及至]", "/", chunk)
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
    return list(dict.fromkeys(out))


def norm_r5(t: str) -> str:
    return t if t.startswith("DL-R5-") else "DL-" + t


blocks: dict[str, dict] = {}
for m in re.finditer(r"^### (W\d\d)｜(.+?)（([^）]*)）\s*$(.*?)(?=^### |\Z)", text, re.M | re.S):
    wid, title, prio, body = m.group(1), m.group(2), m.group(3), m.group(4)
    g = lambda pat: (re.search(pat, body, re.M).group(1).strip()
                     if re.search(pat, body, re.M) else "")
    blocks[wid] = {"title": title, "priority": prio,
                   "maps_raw": g(r"^- 映射：(.*)$"), "depends_raw": g(r"^- 依赖：(.*)$"),
                   "path_lines": [l.split("：", 1)[1].strip() for l in body.splitlines()
                                  if re.match(r"^- (目标位置|位置)：", l)]}

w_to_r5, w_to_dl = {}, {}
for wid, b in blocks.items():
    toks = expand(b["maps_raw"])
    w_to_r5[wid] = sorted({norm_r5(t) for t in toks if t.startswith(("R5-", "DL-R5-"))})
    w_to_dl[wid] = sorted({t for t in toks if t.startswith("DL-") and not t.startswith("DL-R5-")})

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

assert len(dl_to_w) == 41, f"DL-* count {len(dl_to_w)} != 41"
assert not not_in_ledger, f"pack references unknown R5 ids: {not_in_ledger}"

print("=" * 78)
print("W00 FINAL  DL-* -> W -> DL-R5-* crosswalk   (DERIVED; needs ratification)")
print("=" * 78)
print(f"  W blocks              : {len(blocks)}")
print(f"  distinct DL-* in §2   : {len(dl_to_w)}   == pack's 41  OK")
print(f"  distinct R5 in §1     : {len(pack_r5)}")
print(f"  R5 in ledger          : {len(r5_ids)}")
print(f"  pack R5 not in ledger : {not_in_ledger or 'none'}  OK")
print(f"  R5 COVERED            : {len(covered)}/28")
print(f"  R5 UNCOVERED          : {len(uncovered)}/28")

print("\n--- COVERED: R5 -> W ---")
for r in covered:
    ws = sorted({w for dl in r5_to_dl[r] for w in dl_to_w.get(dl, [])})
    print(f"  {r}  {r5_title[r][:24]:<26} W={','.join(ws)}")

print("\n--- UNCOVERED: R5 ---")
for r in uncovered:
    print(f"  {r}  {r5_title[r]}")

dst = PACK.parent / "W00-CROSSWALK.json"
dst.write_text(json.dumps({
    "provenance": "DERIVED from 02_EXECUTION_TASKS.md; NOT authoritative; needs owner ratification (AGENTS.md).",
    "notation_finding": "pack writes 'R5-NNN'; ledger writes 'DL-R5-NNN' (same entity).",
    "parser_findings": [
        "§2 has multi-W cells (|DL-UI-09 / DL-UI-10|W02/W03/W14|)",
        "§1 joins ids with Chinese particles (011或012, R5-006及...)",
        "§2 groups split across whitespace chunks (DL-WL-01 / 02 / 03) need a cross-chunk cursor",
    ],
    "counts": {"w_blocks": len(blocks), "dl_ids": len(dl_to_w), "r5_referenced": len(pack_r5),
               "r5_covered": len(covered), "r5_uncovered": len(uncovered)},
    "w_blocks_meta": blocks, "w_to_r5": w_to_r5, "w_to_dl": w_to_dl,
    "dl_to_w": dict(dl_to_w), "dl_to_r5": dl_to_r5,
    "r5_covered": covered, "r5_uncovered": uncovered,
    "pack_r5_not_in_ledger": not_in_ledger, "wave_a": ["W00", "W01", "W02", "W03"],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
