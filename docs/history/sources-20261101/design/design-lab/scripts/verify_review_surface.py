#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-V2 P2-G: verify Review Surface generator (fail-closed, read-only projection)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GEN = ROOT / "scripts" / "generate_review_surface.py"
SAMPLE = ROOT / "evals" / "e2e-reference" / "project-state-sample.json"


def main() -> int:
    errors: list[str] = []
    if not GEN.exists():
        errors.append("missing generate_review_surface.py")
        return 1
    # The generator prints Chinese section headings, so the parent must decode its
    # output as UTF-8 explicitly. With the locale codec (cp936 here) and a child that
    # emits UTF-8, this call raised UnicodeDecodeError and the aggregate chain died
    # instead of reporting the step.
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    r = subprocess.run([sys.executable, str(GEN), str(SAMPLE)], capture_output=True,
                       text=True, encoding="utf-8", errors="replace", env=env)
    if r.returncode != 0:
        errors.append(f"generator failed: {r.stderr}")
    md = r.stdout or ""
    for needle in ("当前阶段", "项目对象", "阶段历史", "待用户判断节点", "交付与证据", "只读投影"):
        if needle not in md:
            errors.append(f"review surface missing section: {needle}")
    # 非状态源声明
    if "非状态源" not in md:
        errors.append("must declare read-only projection (non-state-source)")
    # 输入是合法 v2 状态
    state = json.loads(SAMPLE.read_text(encoding="utf-8"))
    if state.get("schemaVersion") != "design-lab/design-project-state/v2":
        errors.append("sample state must be v2")
    print(f"REVIEW_SURFACE={'FAIL' if errors else 'PASS'}")
    for e in errors:
        print("ERROR:", e)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
