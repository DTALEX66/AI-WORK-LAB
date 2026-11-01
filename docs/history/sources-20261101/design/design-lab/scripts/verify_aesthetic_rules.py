#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL: verify aesthetic rules registry (fail-closed, stdlib only).

美学评估分层契约：确定性元数据规则（仓库内可算）+ 模型美学（provider E0 声明）。
不得把模型能力当作已实现（RULE 5/9）。
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REG = ROOT.parent / "packages" / "capabilities" / "quality" / "profiles" / "aesthetic-rules.json"
PROVIDERS = ROOT / "config" / "provider-capabilities.json"


def main() -> int:
    errors: list[str] = []
    rules = json.loads(REG.read_text(encoding="utf-8"))
    if rules.get("schemaVersion") != "design-lab/aesthetic-rules/v1":
        errors.append("schemaVersion mismatch")
    rs = rules.get("rules", [])
    if len(rs) < 5:
        errors.append(f"too few rules: {len(rs)}")
    computable = {r.get("computable") for r in rs}
    for r in rs:
        if not r.get("id") or not r.get("name"):
            errors.append("rule missing id/name")
        if r.get("severity") not in ("low", "medium", "high", "blocker"):
            errors.append(f"{r.get('id')}: bad severity")
        if r.get("computable") not in ("deterministic-metadata", "model-aesthetic", "model-ocr"):
            errors.append(f"{r.get('id')}: bad computable")
    # 诚实分界：model-* 规则必须有对应 provider 声明（E0）
    provs = json.loads(PROVIDERS.read_text(encoding="utf-8")).get("providers", [])
    caps = {c for p in provs for c in p.get("capabilities", [])}
    if "model-aesthetic" in computable and "quality.aesthetic_score" not in caps:
        errors.append("model-aesthetic rules require provider quality.aesthetic_score (E0 declared)")
    if "model-ocr" in computable and "document.ocr" not in caps:
        errors.append("model-ocr rules require provider document.ocr (E0 declared)")
    if "deterministic-metadata" in computable and not any(r["computable"] == "deterministic-metadata" for r in rs):
        errors.append("no deterministic-metadata rule")
    print(f"AESTHETIC_RULES={'FAIL' if errors else 'PASS'} rules={len(rs)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
