# SPDX-License-Identifier: MIT
"""Build the authoritative migration map for AI-WORK-LAB from the handoff baseline.

Inputs (read-only): the handoff package CSVs under AI-WORK-LAB_HANDOFF_20261029/
and the tracked files of the two source repos.

Outputs (all relative to the fixed target root, written via Path.write_text):
* migration/mapping.csv              - one row per source entry with disposition
* migration/design-tasks.csv         - the 50 current design tasks, definitions preserved
* migration/review/unclassified-review.json - the 8 unclassified entries, reviewed
* migration/duplicate-candidates.json - cross-repo identical-blob candidates
* migration/sources.json             - machine-readable baseline + counts

Deterministic and idempotent: rerunning overwrites the same bytes instead of
appending records (V07). It never writes to the source repos.

Path policy: every opened path goes through contain(), which resolves the path
and requires it to stay inside the given root via Path.relative_to; any
parent-directory segment is rejected before resolution. All outputs are
composed in memory and written with pathlib only.
"""
from __future__ import annotations

import csv
import hashlib
import io
import json
import os
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

TARGET_ROOT = Path(r"D:\All projects\AI-WORK-LAB")
WORK_SOURCE_ROOT = Path(r"D:\All projects\WORK-LAB")
DESIGN_SOURCE_ROOT = Path(r"D:\All projects\DESIGN-LAB")

HANDOFF_DIRNAME = "AI-WORK-LAB_HANDOFF_20261029"
OUT_DIR = Path("migration")
OUT_REVIEW_DIR = Path("migration") / "review"


class PathViolation(Exception):
    """A scanned path tried to escape its root."""


def contain(root: Path, *rel: str | Path) -> Path:
    """Resolve root/rel and require containment inside root, else raise."""
    if any(part == os.pardir for part in Path(*rel).parts):
        raise PathViolation(f"parent segment rejected: {rel}")
    resolved = (root / Path(*rel)).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        raise PathViolation(f"escapes root {root}: {resolved}") from None
    return resolved


WORK_ANCHOR = "a8cc2fbce2832a9a27605334fd750b57257b4e42"
DESIGN_ANCHOR = "9882a89c21fe52507ec64e14b83ff4c3477cbe85"

# family -> (disposition, target module, phase, acceptance refs)
FAMILY_RULES = {
    "project": ("MERGE", "core/projects", "P1", "V02"),
    "task": ("MERGE", "core/tasks", "P1", "V03,V04,V05"),
    "execution": ("REPAIR", "integrations/agents", "P1人工;P2单连接;P3多Agent", "V09"),
    "permissions": ("MERGE", "core/permissions", "P1", "V02"),
    "telemetry": ("RETAIN", "domains/work/monitoring", "P1", "V02"),
    "usage": ("MERGE", "core/usage", "P1", "V02"),
    "issues": ("RETAIN", "domains/work/issues", "P1", "V02"),
    "solutions": ("RETAIN", "domains/work/solutions", "P1", "V06"),
    "software": ("MERGE", "core/environment", "P1", "V09"),
    "configuration": ("MERGE", "core/configuration", "P1", "V02"),
    "evidence": ("MERGE", "core/evidence", "P1", "V10"),
    "session": ("MERGE", "core/context", "P1既有;P2协议接续", "V09"),
    "candidate": ("RETAIN", "integrations/knowledge-candidate", "P1合同;P3深度AAOS", "V09"),
    "cleanup": ("RETAIN", "core/maintenance", "P1", "V07"),
    "radar": ("MERGE", "core/radar", "P1", "V02"),
    "design-knowledge": ("RETAIN", "domains/design/knowledge", "P1", "V06"),
    "design-prompt": ("REPAIR", "domains/design/prompt", "P1既有;P3模型执行", "V09"),
    "design-plan": ("RETAIN", "domains/design/plans", "P1", "V04"),
    "design-target": ("MERGE", "domains/design/targets", "P1", "V04"),
    "design-domain": ("RETAIN", "domains/design/domains", "P1", "V08"),
    "design-assets": ("RETAIN", "domains/design/assets", "P1", "V08"),
    "design-reconstruction": ("REPAIR", "domains/design/reconstruction", "P1既有;P3复杂新增", "V09"),
    "design-quality": ("RETAIN", "domains/design/quality", "P1既有;P2宿主;P3复杂Jury", "V09"),
    "design-tools": ("REPAIR", "integrations/design-tools", "P1全量保留;P2可用宿主", "V09"),
    "desktop": ("MERGE", "apps/desktop", "STITCH设计;P1后端合同", "V02"),
    "contracts": ("MERGE", "packages/contracts", "P1", "V08"),
    "research": ("RETAIN", "research", "P1保留来源;联网检索延期", "V09"),
    "evolution": ("REPAIR", "core/evolution", "P1任务类型与诚实合同;P3完整执行", "V10"),
    "build-test": ("RETAIN", "tooling", "P1", "V08"),
}

# The 8 unclassified entries (P0 review per handoff 3.1): manual semantic review.
UNCLASSIFIED_REVIEW = [
    {
        "source_key": "design:src/design_lab/http_service.py#L144",
        "reviewed_family": "contracts",
        "reason": "GET /api/health 是服务健康投影路由；并入统一后端 /api/v1/health（REPLACE_EQUIVALENT，保留兼容说明）",
        "disposition": "REPLACE_EQUIVALENT",
        "target": "backend/service (routes/health)",
    },
    {
        "source_key": "design:src/design_lab/http_service.py#L146",
        "reviewed_family": "contracts",
        "reason": "GET /api/capabilities 是能力目录路由；并入统一后端 /api/v1/capabilities（REPLACE_EQUIVALENT）",
        "disposition": "REPLACE_EQUIVALENT",
        "target": "backend/service (routes/capabilities)",
    },
    {
        "source_key": "design:src/design_lab/__init__.py#module",
        "reviewed_family": "build-test",
        "reason": "design_lab 包初始化；作为 domains/design 迁移包结构保留（RETAIN）",
        "disposition": "RETAIN",
        "target": "domains/design (package init)",
    },
    {
        "source_key": "design:src/design_lab/__main__.py#module",
        "reviewed_family": "build-test",
        "reason": "python -m design_lab 入口；并入统一启动入口（MERGE）",
        "disposition": "MERGE",
        "target": "backend/__main__ (unified entry)",
    },
    {
        "source_key": "design:src/design_lab/cli.py#module",
        "reviewed_family": "build-test",
        "reason": "CLI 入口（含恢复摘要与质量判据）；并入统一后端 CLI（MERGE，保留恢复/质量语义）",
        "disposition": "MERGE",
        "target": "backend/cli (unified entry)",
    },
    {
        "source_key": "design:src/design_lab/design_layer.py#module",
        "reviewed_family": "contracts",
        "reason": "design 契约与信封校验（_design_contracts/_check_design_envelope）；迁入 packages/contracts（RETAIN）",
        "disposition": "RETAIN",
        "target": "packages/contracts (design envelope)",
    },
    {
        "source_key": "design:src/design_lab/http_service.py#module",
        "reviewed_family": "project",
        "reason": "stdlib HTTP 服务骨架（Route/make_server/RequestError）；作为统一后端服务内核复用（MERGE）",
        "disposition": "MERGE",
        "target": "backend/service (server kernel)",
    },
    {
        "source_key": "design:src/design_lab/service.py#module",
        "reviewed_family": "project",
        "reason": "ProjectService 是项目服务真值；并入 core/projects（MERGE）",
        "disposition": "MERGE",
        "target": "core/projects",
    },
]

# kinds that always change disposition regardless of family
KIND_OVERRIDES = {
    "HTTP_ROUTE": "REPLACE_EQUIVALENT",
}

HISTORY_PATH_MARKERS = ("docs/history", "90-archive", "/archive/")


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def read_baseline_csv(name: str) -> list[dict]:
    with open(contain(TARGET_ROOT, HANDOFF_DIRNAME, name), encoding="utf-8-sig",
              newline="") as fh:
        return list(csv.DictReader(fh))


def git_tracked_hashes(repo: Path) -> dict[str, list[str]]:
    out = subprocess.run(
        ["git", "ls-files"], cwd=str(repo), capture_output=True, text=True, check=True
    ).stdout.splitlines()
    by_hash: dict[str, list[str]] = {}
    for rel in out:
        try:
            p = contain(repo, rel)
        except PathViolation:
            continue
        if not p.is_file():
            continue
        by_hash.setdefault(sha256_file(p), []).append(f"{repo.name}:{rel}")
    return by_hash


def csv_text(rows: list[dict]) -> str:
    buf = io.StringIO(newline="")
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    return buf.getvalue()


def write_stamped(path: Path, payload: dict, stamp_key: str) -> None:
    """Rewrite only when the substance changed; keep the previous stamp when it did not.

    An audited artefact whose only difference between two runs is a clock reading is not
    a new version of anything — but it does move the candidate's path→SHA-256 manifest,
    which would make a plain rerun look like the audited tree had drifted.
    """
    body = {key: value for key, value in payload.items() if key != stamp_key}
    if path.is_file():
        try:
            previous = json.loads(path.read_text(encoding="utf-8"))
        except ValueError:
            previous = None
        unchanged = isinstance(previous, dict) and \
            {key: value for key, value in previous.items() if key != stamp_key} == body
        if unchanged:
            payload[stamp_key] = previous.get(stamp_key, payload[stamp_key])
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def main() -> int:
    contain(TARGET_ROOT, OUT_REVIEW_DIR).mkdir(parents=True, exist_ok=True)

    families = {r["能力族ID"]: r for r in read_baseline_csv("05_能力族分期.csv")}
    entries = read_baseline_csv("06_来源条目基线.csv")
    tasks = read_baseline_csv("10_现行设计任务映射.csv")

    reviewed = {r["source_key"]: r for r in UNCLASSIFIED_REVIEW}

    mapping_rows = []
    counts: Counter[str] = Counter()
    for e in entries:
        key = e["来源键"]
        fam = (e["初分能力族"] or "").strip()
        path = e["原路径"] or ""
        if key in reviewed:
            rv = reviewed[key]
            disposition, target_module, phase, acceptance = (
                rv["disposition"], rv["target"], "P0复核完成", "V02"
            )
            note = "unclassified→P0人工复核: " + rv["reason"]
        else:
            rule = FAMILY_RULES.get(fam)
            if rule is None:
                disposition, target_module, phase, acceptance = (
                    "OUT_OF_SCOPE_WITH_REASON", "migration/review", "待复核", "V01")
                note = "未知能力族，进入人工复核"
            else:
                disposition, target_module, phase, acceptance = rule
                note = ""
            kind = e["种类"]
            if kind in KIND_OVERRIDES and disposition not in ("HISTORY_ONLY",):
                disposition = KIND_OVERRIDES[kind]
                note = (note + "; " if note else "") + "kind override→统一 /api/v1 兼容表"
            if any(m in path.replace(os.sep, "/") for m in HISTORY_PATH_MARKERS):
                disposition = "HISTORY_ONLY"
                note = (note + "; " if note else "") + "历史材料：保留不可变来源与本地恢复锚点"
        counts[disposition] += 1
        mapping_rows.append({
            "来源键": key,
            "仓": e["仓"],
            "种类": e["种类"],
            "原ID": e["原ID"],
            "初分能力族": fam,
            "处理方式": disposition,
            "目标模块": target_module,
            "运行分期": phase,
            "目标状态": "MAPPED_P0",
            "阻塞原因": "",
            "验收用例": acceptance,
            "备注": note,
            "原路径": path,
            "定位": e["定位"],
            "原提交": e["原提交"],
        })

    (contain(TARGET_ROOT, OUT_DIR, "mapping.csv")).write_text(
        csv_text(mapping_rows), encoding="utf-8-sig")

    # 50 current design tasks: definitions frozen at source, status not inherited.
    design_task_rows = []
    for t in tasks:
        src = t["冻结定义来源"]
        try:
            src_obj = json.loads(src)
            def_path = str(src_obj.get("path", ""))
            def_sha = str(src_obj.get("sha256", ""))
        except (json.JSONDecodeError, TypeError):
            def_path, def_sha = src, ""
        design_task_rows.append({
            "原任务ID": t["原任务ID"],
            "标题": t["标题"],
            "原状态": t["来源原状态"],
            "新仓处理": t["新仓处理建议"],
            "定义来源路径": def_path,
            "定义来源sha256": def_sha,
            "新状态": "DEFERRED_REGISTERED" if t["来源原状态"] == "FROZEN_DEFERRED" else "P0_MAPPED",
            "说明": "定义与状态分离；旧DONE不继承；重叠任务归并到同一新实施项",
        })
    (contain(TARGET_ROOT, OUT_DIR, "design-tasks.csv")).write_text(
        csv_text(design_task_rows), encoding="utf-8-sig")

    write_stamped(contain(TARGET_ROOT, OUT_REVIEW_DIR, "unclassified-review.json"), {
        "reviewed_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "count_required": 8,
        "count_reviewed": len(UNCLASSIFIED_REVIEW),
        "entries": UNCLASSIFIED_REVIEW,
    }, "reviewed_at")

    # Cross-repo identical blobs: dedup CANDIDATES only (handoff 3.3).
    work_hashes = git_tracked_hashes(WORK_SOURCE_ROOT)
    design_hashes = git_tracked_hashes(DESIGN_SOURCE_ROOT)
    shared = sorted(set(work_hashes) & set(design_hashes))
    dup_groups = [
        {"sha256": h, "work": work_hashes[h], "design": design_hashes[h]}
        for h in shared
    ]
    (contain(TARGET_ROOT, OUT_DIR, "duplicate-candidates.json")).write_text(
        json.dumps({
            "policy": "候选仅登记；无消费者与回归依据不删除（handoff 3.3）",
            "group_count": len(dup_groups),
            "groups": dup_groups,
        }, ensure_ascii=False, indent=2), encoding="utf-8")

    sources = {
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "work_anchor": WORK_ANCHOR,
        "design_anchor": DESIGN_ANCHOR,
        "work_head_local": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(WORK_SOURCE_ROOT),
                                          capture_output=True, text=True, check=True).stdout.strip(),
        "design_head_local": subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(DESIGN_SOURCE_ROOT),
                                            capture_output=True, text=True, check=True).stdout.strip(),
        "entry_count": len(entries),
        "entry_counts_by_repo": dict(Counter(e["仓"] for e in entries)),
        "disposition_counts": dict(counts),
        "family_count": len(families),
        "design_task_count": len(design_task_rows),
        "duplicate_candidate_groups": len(dup_groups),
        "inputs_sha256": {
            name: sha256_file(contain(TARGET_ROOT, HANDOFF_DIRNAME, name))
            for name in ("05_能力族分期.csv", "06_来源条目基线.csv", "10_现行设计任务映射.csv")
        },
        "outputs": ["migration/mapping.csv", "migration/design-tasks.csv",
                    "migration/review/unclassified-review.json",
                    "migration/duplicate-candidates.json", "migration/sources.json"],
        "rerun": "python scripts/build_migration_map.py",
    }
    write_stamped(contain(TARGET_ROOT, OUT_DIR, "sources.json"), sources, "generated_at")

    print(f"mapping.csv rows={len(mapping_rows)} dispositions={dict(counts)}")
    print(f"design-tasks rows={len(design_task_rows)} dup_groups={len(dup_groups)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
