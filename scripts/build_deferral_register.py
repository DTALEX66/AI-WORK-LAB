# SPDX-License-Identifier: MIT
"""Generate ``migration/deferral-register.json``: every deferred item must name its seam.

The pack freezes L03 as 「延期有来源/依赖/接缝/验收」. Before this file, deferrals lived in
the capability catalog as a ``phase`` string, so "有接缝" was a hope rather than a pointer.
Each row therefore names real files, and the builder refuses to emit a row whose seam does
not exist in this tree — a deferral that points at nothing is exactly how deferred work
gets lost.
"""
from __future__ import annotations

import argparse
import datetime
import json
import sys
from pathlib import Path

TARGET_ROOT = Path(__file__).resolve().parents[1]
PACK = TARGET_ROOT / "AI-WORK-LAB_HANDOFF_20261029" / "09_任务分期与验收.json"
OUT = TARGET_ROOT / "migration" / "deferral-register.json"

#: capability id -> (seam files, what would lift it). Seams are checked, not asserted.
CAPABILITY_SEAMS = {
    "design.native_hosts": (["domains/design/design_lab/adapters/photoshop_com.py",
                             "domains/design/design_lab/adapters/illustrator_com.py"],
                            "owner 逐次授权真实宿主启动与原生文档写入；桥接资产已在包内并逐字节相同"),
    "design.reconstruction": (["packages/capabilities/reconstruction"],
                              "P3：重建管线深度扩展不在本批，保留既有实现"),
    "design.generative": (["domains/design/design_lab/creative/session_link.py"],
                          "P3：生成管线与外部模型真实调用不在本批"),
    "work.executors": (["domains/work/orchestration", "config/adapter-registry.json"],
                       "本地契约可先验证；需网络的真实调用本轮不执行，替身不算真实资格"),
    "work.execution_federation": (["domains/work/orchestration", "backend/core/capabilities.py"],
                                  "P3：多 Agent/跨机协作，接入点是能力目录行 + 编排包"),
    "work.collectors": (["domains/work/orchestration"],
                        "P2：采集器实现保留，其中 git_collector 现记 MIGRATED_PRESENT_UNWIRED"
                        "（导入图零消费者），接线需新的 owner 决定"),
    "core.evolution": (["backend/core/capabilities.py"],
                       "P3：完整自改写与升级恢复，含候选隔离/独立验收/版本与数据回退"),
    "integrations.knowledge_candidate": (["domains/design/design_lab/knowledge_review.py",
                                          "packages/contracts/schemas-design"],
                                         "P1 合同面已实现；P3 深度 AAOS 联调不是本项目的门"),
    "work.session_continuity": (["backend/core/capabilities.py",
                                 "domains/design/design_lab/creative/session_link.py"],
                                "P2：跨会话续接无接缝路由，接入点先记在能力目录，"
                                "落地需新增 /api/v1/sessions 与验收用例"),
}


def build() -> dict:
    pack = json.loads(PACK.read_text(encoding="utf-8-sig"))
    tasks = {task["id"]: task for task in pack["tasks"]}
    entries = []
    for capability, (seams, lift) in CAPABILITY_SEAMS.items():
        missing = [seam for seam in seams if not (TARGET_ROOT / seam).exists()]
        if missing:
            raise SystemExit("DEFERRAL_SEAM_ABSENT " + capability + ": " + str(missing))
        entries.append(dict(kind="capability", id=capability, seams=seams,
                            lift_condition=lift))

    # every non-mandatory task in the pack gets its dependency and acceptance text
    for task_id, task in tasks.items():
        if task["phase"] not in ("P2", "P3"):
            continue
        entries.append(dict(kind="task", id=task_id, phase=task["phase"],
                            title=task["title"], depends_on=task["depends_on"],
                            acceptance=task["acceptance"], seams=_seams_for(task_id)))
    return dict(
        generated_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
        rule="延期项必须点名接缝（真实存在的文件或包）、依赖与验收条款；"
             "接缝缺失时本生成器直接失败，不输出「已保留接缝」的空话",
        pack=str(PACK), entries=entries,
        counts=dict(capabilities=sum(1 for e in entries if e["kind"] == "capability"),
                    tasks=sum(1 for e in entries if e["kind"] == "task")),
    )


TASK_SEAMS = {
    "L20": ["domains/design/design_lab/adapters/photoshop_com.py",
            "domains/design/design_lab/adapters/illustrator_com.py"],
    "L21": ["domains/work/orchestration", "config/adapter-registry.json"],
    "L30": ["domains/work/orchestration", "backend/core/capabilities.py"],
    "L31": ["packages/capabilities/reconstruction",
            "domains/design/design_lab/resources/repo/design-lab/domain-packs"],
    "L32": ["backend/core/capabilities.py", "backend/v1.py"],
}


def _seams_for(task_id: str) -> list[str]:
    seams = TASK_SEAMS[task_id]
    missing = [seam for seam in seams if not (TARGET_ROOT / seam).exists()]
    if missing:
        raise SystemExit("DEFERRAL_SEAM_ABSENT for task " + task_id + ": " + str(missing))
    return seams


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv[1:])
    document = build()
    text = json.dumps(document, ensure_ascii=False, indent=2) + "\n"
    if args.check:
        current = OUT.read_text(encoding="utf-8") if OUT.is_file() else ""
        same = json.loads(current)["entries"] == document["entries"]
        print(json.dumps(dict(matches=same, entries=len(document["entries"])),
                         ensure_ascii=True))
        return 0 if same else 1
    OUT.write_text(text, encoding="utf-8", newline="\n")
    read_back = json.loads(OUT.read_text(encoding="utf-8"))
    print(json.dumps(dict(written=str(OUT), entries=len(read_back["entries"]),
                          counts=read_back["counts"]), ensure_ascii=True))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
