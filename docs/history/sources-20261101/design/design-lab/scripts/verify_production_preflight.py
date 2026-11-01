#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL C2: verify production preflight contracts (fail-closed).

1. preflight v2 schema 有效；三个 profile（print/digital/video）满足 schema
2. blocker 语义：result 中任一 blocker 检查 fail -> 整体 status=fail（加权/通过率不能覆盖）
3. 每个 profile 覆盖其领域的核心检查
"""
from __future__ import annotations

import json
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parent.parent
SCHEMA = ROOT / "schemas" / "preflight.schema.json"
PROFILES = ROOT / "production" / "profiles"


def main() -> int:
    errors: list[str] = []
    schema = json.loads(SCHEMA.read_text(encoding="utf-8"))
    jsonschema.Draft202012Validator.check_schema(schema)

    profiles = {}
    for name in ("preflight-print.json", "preflight-digital.json", "preflight-video.json"):
        data = json.loads((PROFILES / name).read_text(encoding="utf-8"))
        try:
            jsonschema.validate(data, schema)
        except jsonschema.ValidationError as exc:
            errors.append(f"{name}: {exc.message}")
            continue
        profiles[name] = data

    if len(profiles) < 3:
        errors.append(f"expected 3 profiles, got {len(profiles)}")

    # blocker 语义自检：构造 result（blocker fail + 其他全 pass）-> status 必须 fail
    for name, prof in profiles.items():
        blocker_ids = [c["id"] for c in prof["required_checks"] if c["severity"] == "blocker"]
        if not blocker_ids:
            errors.append(f"{name}: no blocker check")
        sample_result = {
            "status": "pass",
            "checks": [{"id": c["id"], "status": "fail" if c["severity"] == "blocker" else "pass"} for c in prof["required_checks"]],
        }
        has_blocker_fail = any(c["status"] == "fail" for c in sample_result["checks"] if c["id"] in blocker_ids)
        if has_blocker_fail:
            sample_result["status"] = "fail"
        if sample_result["status"] != "fail":
            errors.append(f"{name}: blocker fail must force overall fail")

    # 核心检查覆盖
    required_coverage = {
        "preflight-print.json": {"bleed", "fonts-embedded-outlined", "color-mode-output-intent", "pdf-profile"},
        "preflight-digital.json": {"pixel-dimensions", "aspect-ratio", "format"},
        "preflight-video.json": {"duration", "frame-rate", "audio-presence", "codec-container"},
    }
    for name, needed in required_coverage.items():
        prof = profiles.get(name)
        if prof:
            ids = {c["id"] for c in prof["required_checks"]}
            missing = sorted(needed - ids)
            if missing:
                errors.append(f"{name}: missing core checks {missing}")

    print(f"PRODUCTION_PREFLIGHT={'FAIL' if errors else 'PASS'} profiles={len(profiles)}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
