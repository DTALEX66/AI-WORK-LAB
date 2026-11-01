#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P1-F: reference E2E verifier (contract-level, CI-runnable).

一条 ecommerce.hero 全链（非 H3）：brief -> project stages -> commands -> quality gate
-> preflight -> delivery manifest。不执行真实工具渲染（证据 E1 结构，诚实）。
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
CORE = ROOT / "core"
SAMPLE = ROOT / "evals" / "e2e-reference" / "ecommerce-hero-v1.json"


def _load(name):
    p = CORE / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"dl_e2e_{name}", p)
    m = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = m
    spec.loader.exec_module(m)
    return m


def main() -> int:
    errors: list[str] = []
    data = json.loads(SAMPLE.read_text(encoding="utf-8"))

    ps = _load("project_state")
    cm = _load("commands")
    qg = _load("quality_gate")

    # 1) brief 有效（design-brief schema）
    brief_schema = json.loads((ROOT / "schemas" / "design-brief.schema.json").read_text(encoding="utf-8"))
    try:
        jsonschema.validate(data["brief"], brief_schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"brief invalid: {exc.message}")

    # 2) 阶段全链合法（含回退 critique->revision->critique->approved）
    p = ps.DesignProject(project_id=data["brief"]["project_id"], domain=data["domain"], user_mode=data["user_mode"])
    for s in data["stages"]:
        try:
            p.transition(s, f"e2e step {s}")
        except ps.ProjectTransitionError as exc:
            errors.append(f"stage {s}: {exc}")
    if p.stage != "delivered":
        errors.append(f"chain did not end at delivered (got {p.stage})")

    # 3) 命令 capability 有效且中性
    for cmd in data["commands"]:
        errs = cm.validate_command(cmd)
        for e in errs:
            errors.append(f"command {cmd.get('command_id')}: {e}")
        if cm.is_tool_name(cmd["capability"]):
            errors.append(f"command {cmd.get('command_id')}: tool name in capability")

    # 4) quality gate pass（无 blocker + 全维度达标）
    gate = json.loads((ROOT.parent / "packages" / "capabilities" / "quality" / "profiles" / "commercial-visual-v2.json").read_text(encoding="utf-8"))
    res = qg.evaluate(data["quality_scores"], gate, data.get("quality_blockers", []))
    if res["decision"] != "pass":
        errors.append(f"quality gate failed: {res['decision']} {res['blocking_issues']}")

    # 5) preflight 全 pass
    for chk in data["preflight"]["checks"]:
        if chk["status"] != "pass":
            errors.append(f"preflight {chk['id']} not pass")

    # 6) delivery manifest 含 artifact + quality-report + provenance
    arts = data["delivery_manifest"]["artifacts"]
    for required in ("quality-report.json", "provenance.json"):
        if required not in arts:
            errors.append(f"delivery manifest missing {required}")

    print(f"REFERENCE_E2E={'FAIL' if errors else 'PASS'} workflow={data['workflow_id']} evidence={data['evidence_level']}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
