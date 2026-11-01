#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 — crosswalk rev 6 (FINAL, asserted).

rev 6 fix: W16's line is `R5-008/016–022/024–027` — EN-DASH RANGES. rev 5 did not
expand them, so it reported 10 R5 tasks as "uncovered by the pack". They are in
fact all mapped (by W16). Reporting them uncovered would mis-scope the plan.

Also adds the distinction that actually matters for scheduling:
  MAINLINE  = mapped by W00..W15  -> actionable in the P0/P1 plan
  FEDERAL   = mapped by W11/W12   -> cross-project branch, must not block mainline
  EXTENSION = mapped ONLY by W16/W17 -> P2, conditional on W15 passing
"Mapped" is NOT "scheduled".

Asserts: DL-* == 41, pack R5 all exist in ledger, every ledger R5 is mapped.
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
RANGE_RE = re.compile(r"(\d{2,3})\s*[–—\-]\s*(\d{2,3})")

MAINLINE = [f"W{i:02d}" for i in range(0, 16)]     # W00..W15
FEDERAL = ["W11", "W12"]
EXTENSION = ["W16", "W17"]


def expand(tokens: str) -> list[str]:
    out: list[str] = []
    last: str | None = None
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
                continue
            if last:
                r = RANGE_RE.fullmatch(part)
                if r:                                  # rev 6
                    a, b = int(r.group(1)), int(r.group(2))
                    for n in range(min(a, b), max(a, b) + 1):
                        out.append(f"{last}-{n:03d}")
                    continue
                if re.fullmatch(r"\d+", part):
                    out.append(f"{last}-{int(part):03d}")
    return list(dict.fromkeys(out))


def norm_r5(t: str) -> str:
    return t if t.startswith("DL-R5-") else "DL-" + t


blocks: dict[str, dict] = {}
for m in re.finditer(r"^### (W\d\d)｜(.+?)（([^）]*)）\s*$(.*?)(?=^### |\Z)", text, re.M | re.S):
    wid, title, prio, body = m.group(1), m.group(2), m.group(3), m.group(4)
    g = lambda pat: (re.search(pat, body, re.M).group(1).strip() if re.search(pat, body, re.M) else "")
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
r5_to_w: dict[str, set[str]] = defaultdict(set)
for w, rs in w_to_r5.items():
    for r in rs:
        r5_to_w[r].add(w)

pack_r5 = sorted({r for rs in w_to_r5.values() for r in rs})
not_in_ledger = [r for r in pack_r5 if r not in r5_by_id]
unmapped = [r for r in r5_ids if r not in r5_to_w]

assert len(dl_to_w) == 41, f"DL-* {len(dl_to_w)} != 41"
assert not not_in_ledger, f"unknown R5: {not_in_ledger}"
assert not unmapped, f"ledger R5 not mapped anywhere: {unmapped}"

mainline = [r for r in r5_ids if r5_to_w[r] & set(MAINLINE)]
extension_only = [r for r in r5_ids if not (r5_to_w[r] & set(MAINLINE))]

print("=" * 78)
print("W00 FINAL  DL-* -> W -> DL-R5-*  crosswalk  (DERIVED; needs ratification)")
print("=" * 78)
print(f"  W blocks              : {len(blocks)}")
print(f"  distinct DL-* in §2   : {len(dl_to_w)}   == pack's 41            [assert OK]")
print(f"  distinct R5 in §1     : {len(pack_r5)}")
print(f"  R5 in ledger          : {len(r5_ids)}")
print(f"  pack R5 not in ledger : {not_in_ledger or 'none'}                [assert OK]")
print(f"  ledger R5 unmapped    : {unmapped or 'none'}                     [assert OK]")
print(f"  MAINLINE (W00-W15)    : {len(mainline)}/28")
print(f"  EXTENSION-ONLY (W16/17): {len(extension_only)}/28")

print("\n--- MAINLINE: R5 -> W ---")
for r in mainline:
    print(f"  {r}  {r5_title[r][:24]:<26} W={','.join(sorted(r5_to_w[r]))}")

print("\n--- EXTENSION-ONLY (P2, conditional on W15) ---")
for r in extension_only:
    print(f"  {r}  {r5_title[r][:24]:<26} W={','.join(sorted(r5_to_w[r]))}")

print("\n--- FEDERAL (W11/W12) ---")
for r in r5_ids:
    if r5_to_w[r] & set(FEDERAL):
        print(f"  {r}  {r5_title[r][:24]:<26} W={','.join(sorted(r5_to_w[r]))}")

dst = PACK.parent / "W00-CROSSWALK.json"
dst.write_text(json.dumps({
    "provenance": "DERIVED from 02_EXECUTION_TASKS.md; NOT authoritative; needs owner ratification (AGENTS.md).",
    "notation_finding": "pack writes 'R5-NNN'; ledger writes 'DL-R5-NNN' (same entity).",
    "parser_findings": [
        "§2 multi-W cells (|DL-UI-09 / DL-UI-10|W02/W03/W14|)",
        "§1 Chinese joiners (011或012, R5-006及...)",
        "§2 groups split across whitespace chunks (DL-WL-01 / 02 / 03)",
        "W16 EN-DASH ranges (R5-008/016–022/024–027)",
    ],
    "counts": {"w_blocks": len(blocks), "dl_ids": len(dl_to_w), "r5_referenced": len(pack_r5),
               "r5_mapped": len(r5_ids) - len(unmapped), "mainline": len(mainline),
               "extension_only": len(extension_only)},
    "caveat": "'mapped' is NOT 'scheduled': W16/W17 are P2 and conditional on W15.",
    "w_blocks_meta": blocks, "w_to_r5": w_to_r5, "w_to_dl": w_to_dl,
    "dl_to_w": dict(dl_to_w), "dl_to_r5": dl_to_r5,
    "r5_to_w": {k: sorted(v) for k, v in r5_to_w.items()},
    "mainline_r5": mainline, "extension_only_r5": extension_only,
    "pack_r5_not_in_ledger": not_in_ledger, "ledger_r5_unmapped": unmapped,
    "wave_a": ["W00", "W01", "W02", "W03"],
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
