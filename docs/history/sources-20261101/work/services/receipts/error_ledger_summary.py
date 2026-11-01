"""error_ledger_summary.py — 长期记忆自动沉淀（增强规划 #4，2026-08-12）

从 error-ledger.json 聚合为项目知识文件：每种错误分类 → 根因 → 修复 →
回归测试。消费方（新会话）通过该文件快速查询"某类问题为何发生、怎么修"，
无需重读全量 ledger。

用法:
  python scripts/workflow/error_ledger_summary.py --ledger taskpacks/current/error-ledger.json --out taskpacks/current/error-ledger-lessons.md

输出: tracked 知识文件（与 error-ledger.json 同目录），CI 可校验 freshness。
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path


def build_summary(rows: list[dict[str, object]]) -> str:
    by_class: dict[str, list[dict[str, object]]] = defaultdict(list)
    for row in rows:
        by_class[str(row.get("classification") or "unclassified")].append(row)

    lines = [
        "# Error-Ledger Lessons（长期记忆，自动生成）",
        "",
        "> 由 `error_ledger_summary.py` 从 error-ledger.json 自动聚合。",
        "> 查询方式：按分类名搜索；修复模式可直接复用。",
        "",
        f"共 {len(rows)} 条记录，{len(by_class)} 个分类。",
        "",
    ]
    for classification in sorted(by_class):
        records = by_class[classification]
        lines.append(f"## {classification}（{len(records)} 条）")
        for record in records:
            fix = str(record.get("fix") or "—")
            root = str(record.get("root_cause") or "—")
            regression = str(record.get("regression_test") or "")
            line = f"- `{record.get('error_id')}` [{record.get('phase')}] 根因: {root} → 修复: {fix}"
            if regression:
                line += f"（回归: {regression}）"
            lines.append(line)
        lines.append("")
    lines.append(f"_生成时间: {datetime.now(timezone.utc).isoformat(timespec='seconds')} UTC_")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", required=True, type=Path, help="error-ledger.json 路径")
    parser.add_argument("--out", required=True, type=Path, help="生成的 lessons 知识文件路径")
    args = parser.parse_args()

    data = json.loads(args.ledger.read_text(encoding="utf-8"))
    rows = data.get("errors", [])
    if not isinstance(rows, list) or not rows:
        print(f"error: ledger 无 errors 列表（{args.ledger}）", file=sys.stderr)
        return 1
    summary = build_summary(rows)
    args.out.write_text(summary, encoding="utf-8")
    print(f"wrote {len(rows)} records -> {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
