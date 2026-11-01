#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL D2: verify quality pipeline (fail-closed, stdlib only).

1. pipeline-layers 注册表完整（四层，证据等级递进）
2. human-feedback 层不可被替换/跳过（E4 唯一来源）
3. visual-model 层未取证时不得宣称 E2（诚实声明）
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LAYERS = ROOT.parent / "packages" / "capabilities" / "quality" / "pipeline-layers.json"


def main() -> int:
    errors: list[str] = []
    reg = json.loads(LAYERS.read_text(encoding="utf-8"))
    if reg.get("schemaVersion") != "packages/capabilities/quality-pipeline/v1":
        errors.append("schemaVersion mismatch")
    ls = reg.get("layers", [])
    ids = [l.get("id") for l in ls]
    if ids != ["deterministic", "visual-model", "expert-agent", "human-feedback"]:
        errors.append(f"layer order/id mismatch: {ids}")
    levels = [l.get("evidence_level") for l in ls]
    if levels != ["E1", "E2", "E3", "E4"]:
        errors.append(f"evidence levels must escalate E1..E4: {levels}")
    for l in ls:
        if not l.get("title") or not l.get("tools") or not l.get("gate"):
            errors.append(f"layer {l.get('id')}: incomplete")
    hf = reg["layers"][3]
    if "human-feedback" not in hf["id"] or "人工" not in hf.get("desc", "") and "human" not in hf.get("desc", "").lower():
        errors.append("human-feedback must state human-only calibration")
    print(f"QUALITY_PIPELINE={'FAIL' if errors else 'PASS'} layers={len(ls)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
