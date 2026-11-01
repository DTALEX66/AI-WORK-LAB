#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 — crosswalk rev 4 (FINAL).

rev 4 fix: the pack joins ids with Chinese particles — `R5-004/005/009/010/011或012`
(W07, the "one real host" choice) and `R5-006及已有provider模块映射` (W12). rev 3
dropped those, which silently erased R5-011 / R5-012 (the two Adobe host chains)
and R5-006 (software/model qualification) from the crosswalk — erasing exactly
the ids that decide which host is closed first.

Normalisation: split on strong separators, then rewrite the in-group particles
或/及/至 to '/', then apply prefix inheritance.
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
    for chunk in re.split(r"[；;，,、\s]+", tokens.strip().rstrip("。")):
        if not chunk:
            continue
        chunk = re.sub(r"[或及至]", "/", chunk)          # rev 4
        last = None
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

print("=" * 78)
print("W00 FINAL  DL-* -> W -> DL-R5-* crosswalk   (DERIVED; needs ratification)")
print("=" * 78)
print(f"  W blocks              : {len(blocks)}")
print(f"  distinct DL-* in §2   : {len(dl_to_w)}   (pack claims 41)")
print(f"  distinct R5 in §1     : {len(pack_r5)}")
print(f"  R5 in ledger          : {len(r5_ids)}")
print(f"  pack R5 not in ledger : {not_in_ledger or 'none'}")
print(f"  R5 COVERED            : {len(covered)}/28")
print(f"  R5 UNCOVERED          : {len(uncovered)}/28")

print("\n--- COVERED: R5 -> W ---")
for r in covered:
    ws = sorted({w for dl in r5_to_dl[r] for w in dl_to_w.get(dl, [])})
    print(f"  {r}  {r5_title[r][:24]:<26} W={','.join(ws)}")

print("\n--- UNCOVERED: R5 (pack says nothing about these) ---")
for r in uncovered:
    print(f"  {r}  {r5_title[r]}")

print("\n--- W07 / W12 mapping lines (the ones rev 3 mis-parsed) ---")
for w in ("W07", "W12"):
    print(f"  {w} maps_raw = {blocks[w]['maps_raw']}")
    print(f"      -> R5 = {[x.replace('DL-','') for x in w_to_r5[w]]}")

dst = PACK.parent / "W00-CROSSWALK.json"
dst.write_text(json.dumps({
    "provenance": "DERIVED from 02_EXECUTION_TASKS.md; NOT authoritative; needs owner ratification (AGENTS.md).",
    "notation_finding": "pack writes 'R5-NNN'; ledger writes 'DL-R5-NNN' (same entity).",
    "parser_findings": [
        "§2 has multi-W cells (|DL-UI-09 / DL-UI-10|W02/W03/W14|) — single-W regex dropped 7 rows",
        "§1 joins ids with Chinese particles (011或012, R5-006及...) — must be treated as separators",
    ],
    "w_blocks": blocks, "w_to_r5": w_to_r5, "w_to_dl": w_to_dl,
    "dl_to_w": dict(dl_to_w), "dl_to_r5": dl_to_r5,
    "r5_covered": covered, "r5_uncovered": uncovered,
    "pack_r5_not_in_ledger": not_in_ledger, "wave_a": ["W00", "W01", "W02", "W03"],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
