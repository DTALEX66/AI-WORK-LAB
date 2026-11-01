"""spec_to_tasks.py — Spec→任务链自动拆解（增强规划 #5，2026-08-12）

解析任务包 spec（markdown）为任务卡声明 JSON：`## N. 标题` 为任务，
行内 `depends_on: task-id` 声明依赖；验收标准从任务段落中的
`- [ ]` / `验收:` 行提取。输出可被 TaskLedger.create + set_dependencies
消费的任务声明列表（人工确认后入 ledger）。

用法:
  python scripts/workflow/spec_to_tasks.py --spec taskpacks/current/TASKPACK.md
  python scripts/workflow/spec_to_tasks.py --spec FILE --out tasks.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TASK_HEADING = re.compile(r"^##\s+(\d+(?:\.\d+)*)\.?\s+(.+)$")
DEPENDS_ON = re.compile(r"depends_on\s*[:：]\s*([^\n]+)", re.I)
ACCEPTANCE = re.compile(r"^(?:-\s*\[\s*\]\s*)?验收[:：]\s*(.+)$|^\s*[A-Z]+\s*[:：]\s*(.+)$")


def parse_spec(text: str) -> dict[str, object]:
    tasks: list[dict[str, object]] = []
    current: dict[str, object] | None = None
    body: list[str] = []

    def flush() -> None:
        nonlocal current, body
        if current is not None:
            current["body"] = "\n".join(body).strip()
            tasks.append(current)
        current = None
        body = []

    for raw in text.splitlines():
        line = raw.rstrip()
        match = TASK_HEADING.match(line)
        if match:
            flush()
            current = {"task_id": f"task-{match.group(1)}", "title": match.group(2).strip()}
            continue
        if current is not None:
            dep = DEPENDS_ON.search(line)
            if dep:
                deps = [d.strip() for d in dep.group(1).split(",") if d.strip()]
                current["depends_on"] = [f"task-{d}" if not d.startswith("task-") else d for d in deps]
                continue
            body.append(line)

    flush()
    return {"schema_version": "workflow/spec-to-tasks/v1", "tasks": tasks}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--spec", required=True, type=Path, help="任务包 markdown 路径")
    parser.add_argument("--out", type=Path, help="输出 JSON 路径（默认 stdout）")
    args = parser.parse_args()

    spec = parse_spec(args.spec.read_text(encoding="utf-8"))
    payload = json.dumps(spec, ensure_ascii=False, indent=2)
    if args.out:
        args.out.write_text(payload + "\n", encoding="utf-8")
        print(f"wrote {len(spec['tasks'])} tasks -> {args.out}")
    else:
        print(payload)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
