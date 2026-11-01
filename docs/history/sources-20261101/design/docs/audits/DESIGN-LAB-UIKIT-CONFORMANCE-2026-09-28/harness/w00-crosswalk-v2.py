#!/usr/bin/env python
# SPDX-License-Identifier: MIT
"""W00 — DL-* -> W -> DL-R5-* crosswalk + path audit (rev 2).

rev 2 fixes two parser/notation defects found in rev 1:
  1. §2 table cells abbreviate groups as "DL-WL-01 / 02 / 03 / ..." — rev 1 only
     captured the first member. Now handled by prefix-inheritance on '/'.
  2. The pack writes R5 ids as "R5-010" while the ledger uses "DL-R5-010" — the
     same entity under two spellings. rev 1 compared them raw and reported
     0/28 covered. Now normalised, and the notation split is reported as its own
     finding (it is a real dispatch hazard, not a cosmetic one).

Provenance: the crosswalk is DERIVED from the pack (§1 映射 lines, §2 table).
It is NOT authoritative; AGENTS.md requires an owner-ratified crosswalk.
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
    """Prefix-inheritance expansion: 'DL-WL-01 / 02 / 03' -> all three;
    'DL-00 / DL-01' -> both; 'R5-001/002' -> both."""
    out: list[str] = []
    last: str | None = None
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


def norm_r5(tok: str) -> str:
    """'R5-010' -> 'DL-R5-010' (ledger spelling). Idempotent."""
    return tok if tok.startswith("DL-R5-") else "DL-" + tok


# --------------------------------------------------------------- W blocks
blocks: dict[str, dict] = {}
for m in re.finditer(r"^### (W\d\d)｜(.+?)（([^）]*)）\s*$(.*?)(?=^### |\Z)",
                     text, re.M | re.S):
    wid, title, prio, body = m.group(1), m.group(2), m.group(3), m.group(4)
    maps = re.search(r"^- 映射：(.*)$", body, re.M)
    blocks[wid] = {
        "title": title, "priority": prio,
        "maps_raw": maps.group(1).strip() if maps else "",
        "path_lines": [l.split("：", 1)[1].strip() for l in body.splitlines()
                       if re.match(r"^- (目标位置|位置|读取|读取：)", l)],
    }

w_to_r5, w_to_dl = {}, {}
for wid, b in blocks.items():
    toks = expand(b["maps_raw"])
    w_to_r5[wid] = sorted({norm_r5(t) for t in toks if t.startswith(("R5-", "DL-R5-"))})
    w_to_dl[wid] = sorted({t for t in toks if t.startswith("DL-") and not t.startswith("DL-R5-")})

# --------------------------------------------------------------- §2 table
dl_to_w: dict[str, list[str]] = defaultdict(list)
for m in re.finditer(r"^\|(DL-[^|]+)\|(W\d\d)\|", text, re.M):
    for dl in expand(m.group(1)):
        if dl not in dl_to_w[dl] if False else True:
            pass
        if m.group(2).strip() not in dl_to_w[dl]:
            dl_to_w[dl].append(m.group(2).strip())

ledger = json.loads(LEDGER.read_text(encoding="utf-8"))
r5_ids = [t["id"] for t in ledger["tasks"]]
r5_by_id = {t["id"]: t for t in ledger["tasks"]}

# --------------------------------------------------------------- compose
dl_to_r5 = {dl: sorted({r for w in ws for r in w_to_r5.get(w, [])}) for dl, ws in dl_to_w.items()}
r5_to_dl: dict[str, set[str]] = defaultdict(set)
for dl, rs in dl_to_r5.items():
    for r in rs:
        r5_to_dl[r].add(dl)

covered = [r for r in r5_ids if r in r5_to_dl]
uncovered = [r for r in r5_ids if r not in r5_to_dl]
pack_r5 = sorted({r for rs in w_to_r5.values() for r in rs})
pack_r5_not_in_ledger = [r for r in pack_r5 if r not in r5_by_id]

print("=" * 78)
print("W00  CROSSWALK  DL-* -> W -> DL-R5-*   (DERIVED, needs owner ratification)")
print("=" * 78)
print(f"\nW blocks parsed       : {len(blocks)}")
print(f"distinct DL-* in §2   : {len(dl_to_w)}   (pack claims 41)")
print(f"distinct R5 ids in §1 : {len(pack_r5)}")
print(f"R5 ids in ledger      : {len(r5_ids)}")

print("\n--- DL-* -> W -> R5 ---")
for dl in sorted(dl_to_r5, key=lambda s: (len(s.split('-')), s)):
    print(f"  {dl:<13} W={','.join(dl_to_w[dl]):<10} R5={','.join(x.replace('DL-','') for x in dl_to_r5[dl]) or '-'}")

print(f"\n--- R5 coverage of the pack ---")
print(f"  COVERED   ({len(covered):>2}): {', '.join(x.replace('DL-','') for x in covered)}")
print(f"  UNCOVERED ({len(uncovered):>2}): {', '.join(x.replace('DL-','') for x in uncovered)}")
print(f"\n  pack R5 ids NOT present in the ledger: {pack_r5_not_in_ledger or 'none'}")

print(f"\n--- R5 -> DL-* (reverse; shows which R5 axis a W work package feeds) ---")
for r in r5_ids:
    dls = sorted(r5_to_dl.get(r, []))
    ws = sorted({w for dl in dls for w in dl_to_w.get(dl, [])})
    print(f"  {r:<12} DL={(','.join(dls) or '-'):<22} W={(','.join(ws) or '-')}")

# --------------------------------------------------------------- path audit
print("\n" + "=" * 78)
print("W00  PATH EXISTENCE AUDIT (ASCII path-shaped tokens only)")
print("=" * 78)
cand: set[str] = set()
for b in blocks.values():
    for line in b["path_lines"]:
        for tok in re.split(r"[、,，;；\s]+", line):
            tok = tok.strip().strip("。（）()")
            if re.fullmatch(r"[A-Za-z0-9_./\-]+", tok) and "/" in tok:
                cand.add(tok)
cand.update({
    "src/design_lab/design_layer.py", "src/design_lab/workbench.py",
    "apps/workbench/style.css", "apps/workbench/shell.ts", "apps/workbench/main.ts",
    "apps/workbench/workbench.ts", "apps/workbench/index.html", "apps/workbench/design.ts",
    "apps/workbench/vite.config.ts", "apps/workbench/package.json",
    "packages/design-system", "integrations/hosts/adobe",
    "integrations/adapter-registry.json", "design-lab/config/task-ledger-r3.json",
    "docs/decisions/NEUTRALITY_POLICY.md", "docs/decisions/EVIDENCE_POLICY.md",
    "docs/decisions/ADAPTER_POLICY.md",
})
missing = []
for p in sorted(cand):
    ok = (ROOT / p).exists() if "/" in p and not p.startswith("D:") else Path(p).exists()
    if not ok:
        missing.append(p)
    print(f"  {'OK  ' if ok else 'MISS'} {p}")
print(f"\n  candidates={len(cand)}  missing={len(missing)}  -> {missing}")

dst = PACK.parent / "W00-CROSSWALK.json"
dst.write_text(json.dumps({
    "provenance": "DERIVED from 02_EXECUTION_TASKS.md; NOT authoritative; needs owner ratification (AGENTS.md).",
    "notation_finding": "pack writes 'R5-NNN', ledger writes 'DL-R5-NNN'; normalised here. "
                        "Dispatch must normalise or nothing matches.",
    "w_blocks": blocks, "w_to_r5": w_to_r5, "w_to_dl": w_to_dl,
    "dl_to_w": dict(dl_to_w), "dl_to_r5": dl_to_r5,
    "r5_covered": covered, "r5_uncovered": uncovered,
    "pack_r5_not_in_ledger": pack_r5_not_in_ledger,
    "paths_missing": missing,
}, ensure_ascii=False, indent=2), encoding="utf-8")
print(f"\nwrote {dst}")
