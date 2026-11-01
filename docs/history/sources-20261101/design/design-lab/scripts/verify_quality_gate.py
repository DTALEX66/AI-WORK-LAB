#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-E: verify quality gate (fail-closed).

1. quality-gate schema 有效；commercial-visual-v2 profile 满足 schema
2. blocker 存在时 decision 必须 fail（加权平均不能覆盖）
3. 维度低于 minimum 时 fail
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "quality-gate.schema.json"
PROFILE = ROOT.parent / "packages" / "capabilities" / "quality" / "profiles" / "commercial-visual-v2.json"
CORE = ROOT / "core"


def main() -> int:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    profile = json.loads(PROFILE.read_text(encoding="utf-8"))
    try:
        jsonschema.validate(profile, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"profile invalid: {exc.message}")

    spec = importlib.util.spec_from_file_location("dl_core_quality_gate", str(CORE / "quality_gate.py"))
    gm = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = gm
    spec.loader.exec_module(gm)

    # blocker 存在 -> fail（即使总分 100）
    res = gm.evaluate(
        {"composition": 100, "typography": 100, "color": 100, "hierarchy": 100,
         "brand_fidelity": 100, "asset_fidelity": 100, "commercial_goal": 100, "production_readiness": 100},
        profile, ["insufficient_bleed"],
    )
    if res["decision"] != "fail":
        errors.append("blocker must fail regardless of weighted average")

    # 维度低于 minimum -> fail
    res2 = gm.evaluate(
        {"composition": 91, "typography": 87, "brand_fidelity": 92, "production_readiness": 68,
         "color": 80, "hierarchy": 80, "asset_fidelity": 80, "commercial_goal": 80},
        profile, [],
    )
    if res2["decision"] != "fail":
        errors.append("below-minimum dimension must fail")
    if not any("production_readiness_below_minimum" in b for b in res2["blocking_issues"]):
        errors.append("production_readiness below-minimum not flagged")

    # 全绿 -> pass
    res3 = gm.evaluate(
        {"composition": 90, "typography": 88, "color": 86, "hierarchy": 87,
         "brand_fidelity": 88, "asset_fidelity": 90, "commercial_goal": 85, "production_readiness": 96},
        profile, [],
    )
    if res3["decision"] != "pass" or res3["score"] < 82:
        errors.append(f"clean artifact must pass (got {res3['decision']} {res3['score']})")

    print(f"QUALITY_GATE={'FAIL' if errors else 'PASS'}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
