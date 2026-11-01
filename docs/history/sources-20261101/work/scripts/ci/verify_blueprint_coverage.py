#!/usr/bin/env python3
"""Fail-closed check for the blueprint coverage matrix, and its projection.

Roles: the matrix in .project/governance/blueprint-coverage.json is the single
mutable source; docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md is a generated
projection. AG and U rows are extracted from the live repository files rather
than retyped, so a row cannot be quietly dropped or invented.

Exit 0 prints BLUEPRINT_COVERAGE_PASS. Every structural problem exits 1; a
source that cannot be read is reported as missing, never passed silently.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
MATRIX = REPO / ".project" / "governance" / "blueprint-coverage.json"
PROJECTION = REPO / "docs" / "future" / "WORK-LAB-BLUEPRINT-COVERAGE.md"
BLUEPRINT = REPO / "docs" / "future" / "WORK-LAB-BLUEPRINT-20261006.md"
SNAPSHOT = REPO / "docs" / "audits" / "BLUEPRINT_SYNC_AUDIT_2026-10-06.md"
ATLAS = REPO / "taskpacks" / "history" / "pre-convergence-20261019" / "WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001.md"
REGISTER = REPO / "taskpacks" / "current" / "OPEN-TASK-REGISTER.md"

ALLOWED_STATUS = {"NOT_RUN", "FAIL", "UNVERIFIED", "PASS", "PARTIAL", "BLOCKED"}
ALLOWED_DISPOSITION = {"RETAINED", "SUPERSEDED", "RETIRED", "PENDING_CONFIRMATION",
                       "SOURCE_MISSING"}
# Reused from scripts/ci/verify_error_ledger.py so the matrix never invents a
# parallel task-state enum.
REQUIRED_CHAPTERS = [f"CH-{i:02d}" for i in range(1, 20)] + ["CH-APP"]
REQUIRED_T = [f"T{i:02d}" for i in range(1, 10)]
REQUIRED_OD = [f"OD0{i}" for i in range(1, 6)]
REQUIRED_W = [f"W{i:02d}" for i in range(1, 11)]
# Anti-drift phrases: dropping any of these removes a boundary the owner's
# blueprint states, which is the failure this check exists to catch.
ANTI_DRIFT_PHRASES = [
    "UNKNOWN ≠ 0", "STALE ≠ LIVE", "HTTP 200 ≠ 任务完成", "UI success ≠ 原生副作用",
    "estimated usage ≠ 实付", "NO_EVIDENCE", "NOT_IMPLEMENTED", "Ongoing",
    "不替代", "本轮文档交付不执行", "不得暗中降标", "相同单词",
]


def fail(message: str) -> int:
    print(f"BLUEPRINT_COVERAGE_FAIL {message}")
    return 1


def load_rows(data: dict) -> list[dict]:
    return data.get("rows") or []


def extract_ag_rows() -> list[dict]:
    """AG-01..AG-20 from the live atlas gap task card, never retyped."""
    if not ATLAS.is_file():
        raise FileNotFoundError(str(ATLAS))
    text = ATLAS.read_text(encoding="utf-8", errors="replace")
    frozen = "FROZEN_ARCHIVED / NO_EXECUTION_AUTHORITY" in text
    rows = []
    for match in re.finditer(r"^\|\s*\*\*(AG-\d{2})\*\*\s*([^|]*)\|([^|]*)\|(.*)$",
                             text, re.M):
        identifier, title, priority, body = (g.strip() for g in match.groups())
        linked = re.search(r"\bU(\d{2}[a-z]?)\b", body)
        rows.append({
            "id": identifier, "kind": "atlas-gap",
            "title": re.sub(r"\s*—.*$", "", title)[:90],
            "decision": ("frozen historical row; priority " if frozen else "planning record row; priority ") + (priority or "UNKNOWN"),
            "anchors": ["taskpacks/history/pre-convergence-20261019/WORK-LAB-ATLAS-GAP-REMEDIATION-TASKCARD-20261001.md"],
            "status": "UNVERIFIED", "liveStatus": ("FROZEN_ARCHIVED (historical, no dispatch)" if frozen else "PLANNED (no live status column)"),
            "evidence": ("corresponds to open register row U" + linked.group(1)
                         if linked else "no live register cross-reference in its own row"),
            "disposition": "SUPERSEDED" if frozen else "RETAINED",
            "nextOrBlocked": ("follow current WUI register; this historical row is not a pending task" if frozen else "planning record only: grants no execution authority"),
        })
    return rows


def extract_u_rows() -> list[dict]:
    """Every U row of the single live open-task register."""
    if not REGISTER.is_file():
        raise FileNotFoundError(str(REGISTER))
    rows = []
    for match in re.finditer(r"^\|\s*(U\d{2}[a-z]?)\s*\|\s*([^|]*)\|\s*([^|]*)\|(.*)$",
                             REGISTER.read_text(encoding="utf-8", errors="replace"),
                             re.M):
        identifier, priority, live_status = (g.strip() for g in match.groups()[:3])
        status = next((token for token in sorted(ALLOWED_STATUS)
                       if token in live_status.upper()), "UNVERIFIED")
        rows.append({
            "id": identifier, "kind": "register-row",
            "title": f"open register row ({priority})",
            "decision": "liveness is owned by the register, not by the blueprint",
            "anchors": ["taskpacks/current/OPEN-TASK-REGISTER.md"],
            "status": status, "liveStatus": live_status,
            "evidence": "read from the single live open-task register at run time",
            "disposition": "RETAINED",
            "nextOrBlocked": "see the register cell for the current blocker",
        })
    return rows


def build_matrix(data: dict) -> list[dict]:
    hand = load_rows(data)
    return hand + extract_ag_rows() + extract_u_rows()


def render(rows: list[dict], data: dict) -> str:
    order = ["chapter", "appendix", "closed-loop-task", "owner-default",
             "input-source", "atlas-gap", "register-row"]
    label = {
        "chapter": "蓝图章节（整理稿 → 仓库承接）",
        "appendix": "来源附录",
        "closed-loop-task": "闭环任务 T01—T09",
        "owner-default": "owner 默认裁决 OD01—OD05",
        "input-source": "输入来源与追溯",
        "atlas-gap": "在册差集项 AG（抽自 atlas gap task card）",
        "register-row": "唯一 open register（抽自账本）",
    }
    lines = [
        "# WORK-LAB 蓝图覆盖矩阵（生成投影，勿手改）",
        "",
        f"可变源：`.project/governance/blueprint-coverage.json`  ",
        f"生成命令：`{data['generatedBy']}`  ",
        f"观察时刻：{data['observedAt']}（Asia/Shanghai）  ",
        f"基准提交：`{data['baseSha']}`  ",
        f"行数：{len(rows)}（章 {sum(1 for r in rows if r['kind'] == 'chapter')} · "
        f"T {sum(1 for r in rows if r['kind'] == 'closed-loop-task')} · "
        f"AG {sum(1 for r in rows if r['kind'] == 'atlas-gap')} · "
        f"U {sum(1 for r in rows if r['kind'] == 'register-row')}）",
        "",
        "状态词表复用 `scripts/ci/verify_error_ledger.py` 的 "
        "`NOT_RUN / FAIL / UNVERIFIED / PASS / PARTIAL / BLOCKED`；"
        "处置词表为 `RETAINED / SUPERSEDED / RETIRED / PENDING_CONFIRMATION / SOURCE_MISSING`。"
        "本投影不含自身摘要（防自引用哈希）。",
        "",
        data["note"],
        "",
    ]
    for kind in order:
        group = [r for r in rows if r["kind"] == kind]
        if not group:
            continue
        lines += [f"## {label[kind]}", "",
                  "| ID | 主题 | 有效决定 / 承接 | 状态 | 处置 | 锚点 | 证据与缺口 | 下一步或阻塞 |",
                  "|---|---|---|---|---|---|---|---|"]
        for row in group:
            anchors = "<br>".join(f"`{a}`" for a in row["anchors"])
            evidence = row["evidence"]
            if row.get("liveStatus"):
                evidence = f"live: {row['liveStatus']} · {evidence}"
            cells = [row["id"], row["title"], row["decision"], row["status"],
                     row["disposition"], anchors, evidence,
                     row["nextOrBlocked"]]
            lines.append("| " + " | ".join(
                c.replace("|", "\\|").replace("\n", " ") for c in cells) + " |")
        lines.append("")
    lines.append("## 输入登记")
    lines.append("")
    lines.append("| source_id | 类型 | 路径 | 摘要 | 读取范围与限制 |")
    lines.append("|---|---|---|---|---|")
    for source in data["inputs"]:
        lines.append("| {} | {} | {} | {} | {} |".format(
            source["sourceId"], source["kind"],
            f"`{source['path']}`" if source.get("path") else "UNKNOWN（无文件）",
            source.get("sha256") or "UNKNOWN（原件未哈希）",
            f"{source['readRange']} — {source['limits']}"))
    lines.append("")
    return "\n".join(lines)


def check(data: dict, rows: list[dict]) -> list[str]:
    problems: list[str] = []
    ids = [r["id"] for r in rows]
    duplicates = {i for i in ids if ids.count(i) > 1}
    if duplicates:
        problems.append(f"duplicate ids: {sorted(duplicates)}")
    for required in (REQUIRED_CHAPTERS + REQUIRED_T + REQUIRED_OD + REQUIRED_W):
        if required not in ids:
            problems.append(f"missing required row {required}")
    for row in rows:
        for key in ("id", "kind", "title", "decision", "anchors", "status",
                    "disposition", "evidence", "nextOrBlocked"):
            value = row.get(key)
            if key == "anchors":
                if not value or not all(isinstance(a, str) and a for a in value):
                    problems.append(f"{row.get('id')} anchors must be non-empty paths")
                continue
            if not isinstance(value, str) or not value.strip():
                problems.append(f"{row.get('id')} {key} must be non-empty text")
        if row.get("status") not in ALLOWED_STATUS:
            problems.append(f"{row.get('id')} status {row.get('status')!r} outside the "
                            "reused register vocabulary")
        if row.get("disposition") not in ALLOWED_DISPOSITION:
            problems.append(f"{row.get('id')} disposition {row.get('disposition')!r} unknown")
        for anchor in row.get("anchors", []):
            path = anchor.split("#")[0]
            if not (REPO / path).exists():
                problems.append(f"{row.get('id')} anchor does not resolve: {path}")
    if data.get("baseSha") and not re.fullmatch(r"[0-9a-f]{40}", data["baseSha"]):
        problems.append("baseSha is not a full commit sha")
    # No self-referential or cyclic digests. A file cannot contain its own hash,
    # so testing that would always pass and prove nothing; what can actually
    # happen is generated documents hashing each other, which makes every write
    # invalidate the evidence it recorded. So: the matrix and the projection must
    # not carry each other's digest or the snapshot's, and the snapshot must not
    # carry its own.
    generated = {"matrix": MATRIX, "projection": PROJECTION, "snapshot": SNAPSHOT}
    digests = {}
    for name, path in generated.items():
        if path.is_file():
            digests[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    for name in ("matrix", "projection"):
        blob = generated[name].read_text(encoding="utf-8", errors="replace")
        for other, value in digests.items():
            if other == name:
                continue
            if value in blob:
                problems.append(
                    f"{name} embeds the digest of {other}: generated artifacts must "
                    "not hash each other, or every regeneration invalidates its own "
                    "evidence")
    if "snapshot" in digests:
        snap_text = SNAPSHOT.read_text(encoding="utf-8", errors="replace")
        if digests["snapshot"] in snap_text:
            problems.append("snapshot embeds its own digest")
    if not BLUEPRINT.is_file():
        problems.append(f"blueprint landing document missing: {BLUEPRINT.name}")
    else:
        text = BLUEPRINT.read_text(encoding="utf-8", errors="replace")
        for phrase in ANTI_DRIFT_PHRASES:
            if phrase not in text:
                problems.append(f"anti-drift phrase absent from the blueprint: {phrase!r}")
    for source in data.get("inputs", []):
        if not source.get("sourceId") or not source.get("limits"):
            problems.append("every input must carry sourceId and limits")
    return problems


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--write", action="store_true",
                    help="regenerate the projection from the mutable source")
    args = ap.parse_args()
    if not MATRIX.is_file():
        return fail(f"matrix missing: {MATRIX}")
    try:
        data = json.loads(MATRIX.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        return fail(f"matrix is not valid JSON: {exc}")
    if data.get("schemaVersion") != "work-lab/blueprint-coverage/v1":
        return fail(f"unexpected schema {data.get('schemaVersion')!r}")
    try:
        rows = build_matrix(data)
    except FileNotFoundError as exc:
        return fail(f"live source unreadable: {exc}")
    if args.write:
        PROJECTION.parent.mkdir(parents=True, exist_ok=True)
        PROJECTION.write_text(render(rows, data), encoding="utf-8")
        print(f"BLUEPRINT_COVERAGE_WRITE rows={len(rows)} -> {PROJECTION.name}")
    if not PROJECTION.is_file():
        return fail(f"projection missing: {PROJECTION.name} (run with --write)")

    problems = check(data, rows)
    # The source's own defects are reported ahead of drift: a stale projection is
    # usually a symptom, and naming it first hides which row is actually wrong.
    if not problems and not args.write and \
            PROJECTION.read_text(encoding="utf-8") != render(rows, data):
        problems.append(
            "projection does not match the mutable source: it is stale or was "
            "hand-edited — run scripts/ci/verify_blueprint_coverage.py --write")
    if problems:
        return fail("; ".join(problems[:12]) + ("" if len(problems) <= 12 else
                                                f" (+{len(problems) - 12} more)"))
    counts = {}
    for row in rows:
        counts[row["kind"]] = counts.get(row["kind"], 0) + 1
    print("BLUEPRINT_COVERAGE_PASS "
          f"rows={len(rows)} kinds={counts} "
          f"status_vocabulary=reused dispositions=owner_prompt_set "
          f"self_digest=false anchors_resolve=true anti_drift={len(ANTI_DRIFT_PHRASES)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
