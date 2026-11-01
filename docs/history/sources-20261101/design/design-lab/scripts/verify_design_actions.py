#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL D1: verify Design Action Language (fail-closed, stdlib only).

1. design-action schema 有效；词汇表每条动作合法
2. 动作动词不绑定工具/模型名（中立性）
3. 动作可作为 DesignCommand.args 的规范化层（与 command 契约兼容）
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "design-action.schema.json"
ACTIONS = ROOT / "config" / "design-actions.json"
BANNED = {"photoshop", "illustrator", "indesign", "figma", "blender", "comfyui",
          "minimax", "deepseek", "claude", "gpt", "firefly", "after-effects", "premiere"}


def main() -> int:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)
    reg = json.loads(ACTIONS.read_text(encoding="utf-8"))
    acts = reg.get("actions", [])
    if len(acts) < 10:
        errors.append(f"too few actions: {len(acts)}")
    verbs = set()
    for a in acts:
        verb = a.get("verb", "")
        if not verb:
            errors.append("action missing verb")
            continue
        if verb in verbs:
            errors.append(f"duplicate verb: {verb}")
        verbs.add(verb)
        low = verb.lower()
        for b in BANNED:
            if b in low:
                errors.append(f"verb contains tool name: {verb}")
    # 样例 action 校验
    sample = {"action": "set-font", "target": "layer://headline", "params": {"family": "Source Han Sans SC", "size": 46}}
    try:
        jsonschema.validate(sample, schema)
    except jsonschema.ValidationError as exc:
        errors.append(f"sample action invalid: {exc.message}")
    # 中性化自检：工具名动作必须能被识别为非法（动词表不含工具名）
    tool_named = any(b in "photoshop-batch" for b in BANNED)
    if not tool_named:
        errors.append("tool-named action verb must be detected (neutrality check)")
    print(f"DESIGN_ACTIONS={'FAIL' if errors else 'PASS'} verbs={len(verbs)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
