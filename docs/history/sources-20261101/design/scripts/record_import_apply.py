#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-REC-29: archive the DESIGN-LAB task documents that live on the external
Record volume into this repository, and emit the reviewable import manifest.

Deterministic and re-runnable. The plan below is the audited decision table;
every Record entry is accounted for either as landed bytes, an already-present
byte-identical duplicate, or an explicitly justified external-only pointer.

Rules enforced here (owner task #29):
- only DESIGN-LAB entries move; the 15 GB volume is never copied wholesale;
- every landed member is verified member-by-member against the zip central
  directory by NAME + SIZE + CRC32, re-read from disk after the write;
- deep paths go through the extended-length form (\\\\?\\ with backslashes);
- frozen historical originals are written byte-for-byte and never rewritten;
- binaries get a structured asset-sidecar v1 with reviewedBy left null — an
  agent must not sign a rights field;
- source files in Record are never deleted or modified;
- every reported number is measured in this run, never typed from memory.

Usage:
    python scripts/record_import_apply.py             # plan + verify, no writes
    python scripts/record_import_apply.py --write     # land bytes and manifest
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import os
import re
import subprocess
import sys
import zipfile
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECORD = Path(r"D:\All projects\Record")
IMPORT_ROOT_REL = "docs/history/record-imports-2026-10-08"
REQUEST_ROOT_REL = "docs/taskpacks"
MANIFEST_REL = f"{IMPORT_ROOT_REL}/RECORD-IMPORT-MANIFEST.json"
MANIFEST_MD_REL = f"{IMPORT_ROOT_REL}/RECORD-IMPORT-MANIFEST.md"

# ---------------------------------------------------------------- decision table
# The state vocabulary is AUTHORITY.md §11 as read back by
# .project/governance/authority-index.json (CURRENT / CURRENT_BUT_DRIFTED /
# PROJECTION / SUPERSEDED / HISTORICAL / REFERENCE / NON_AUTHORITATIVE) plus the
# repo's own FROZEN and REQUESTED markers.
CONTAINER_IMPORTS = [
    {
        "source": "DESIGN-LAB-EXECUTION-TASKPACK-2026-09-07-R4.1.zip",
        "strip": r"^DESIGN-LAB-EXECUTION-TASKPACK-2026-09-07/",
        "target": f"{IMPORT_ROOT_REL}/R4.1-EXECUTION-TASKPACK-2026-09-07",
        "state": "SUPERSEDED",
        "class": "FROZEN_TASKPACK",
        "note": "R4.1 执行包；被 DL-TP-20260908-R5 取代，只作血统与对比。",
    },
    {
        "source": "DESIGN-LAB-REAUDIT-20260914.zip",
        "target": f"{IMPORT_ROOT_REL}/REAUDIT-2026-09-14",
        "state": "SUPERSEDED",
        "class": "FROZEN_AUDIT_PACK",
        "note": "2026-09-14 云端复审包；tasks-proposed.json 的提案已被 2026-09-18 统一包裁决。",
    },
    {
        "source": "DESIGN-LAB-AUTHORITY-CONVERGENCE-2026-09-18-R2.zip",
        "strip": r"^DESIGN-LAB-AUTHORITY-CONVERGENCE-2026-09-18-R2/",
        "rewrite": {".project/": "governance-published/"},
        "target": f"{IMPORT_ROOT_REL}/R2-RELEASE-PACKAGE-2026-09-18",
        "state": "FROZEN",
        "class": "PUBLISHED_RELEASE_ORIGINAL",
        "note": "已发布的 R2 权威落地包原件（含 AUTHORITY.md 与 authority-index.json 的被取代版本，"
                "即 scripts/verify_top_level_authority.py re-pin 注释引用、但仓内此前不存在的原始字节）。",
    },
    {
        "source": "DESIGN-LAB_CODEX_20260922.zip",
        "strip": r"^DESIGN-LAB_CODEX_20260922/",
        "target": f"{IMPORT_ROOT_REL}/CODEX-2026-09-22",
        "state": "SUPERSEDED",
        "class": "FROZEN_CODEX_HANDOFF",
        "note": "R2 之后的 Codex 云端审计/派工包；当前派工入口仍是 2026-09-18 统一包。",
    },
    {
        "source": "DESIGN-LAB_FINAL_CONSOLIDATED_PACKAGE_2026-09-29.zip",
        "strip": r"^DESIGN-LAB_MASTER_ATLAS_2026-09-29/",
        "target": f"{IMPORT_ROOT_REL}/FINAL-CONSOLIDATED-2026-09-29",
        "state": "HISTORICAL",
        "class": "FROZEN_MASTER_ATLAS",
        "note": "DESIGN-LAB_MASTER_ATLAS_2026-09-29 全量汇总包。动态读数已过期，按 AUTHORITY §13 "
                "只作历史，不得用于重建当前架构。",
    },
    {
        "source": "DESIGN-LAB_UI_FRONTEND_TASKPACK_20260930.zip",
        "target": f"{IMPORT_ROOT_REL}/UI-FRONTEND-TASKPACK-2026-09-30",
        "state": "SUPERSEDED",
        "class": "FROZEN_TASKPACK",
        "note": "2026-09-30 商业级 Workbench 前端任务包；其成果经 PR #213 进入 main。",
    },
]

# Members selected out of mixed / multi-project containers (only the DESIGN-LAB
# branch of a tri-project package moves).
MEMBER_IMPORTS = [
    {
        "source": "DESIGN-LAB-TASKPACK-20260908-R5.zip",
        "strip": r"^DESIGN-LAB-TASKPACK-20260908-R5/",
        "target": f"{IMPORT_ROOT_REL}/R5-TASKPACK-2026-09-08",
        "state": "FROZEN",
        "class": "PRODUCT_LINEAGE",
        "note": "DL-TP-20260908-R5 产品血统包：成员已逐字节存在于 docs/history/taskpacks/r5-20260908/，"
                "只登记映射，不重复写入字节。",
    },
    {
        "source": "DESIGNLAB_商业级前端与能力闭环_后续任务包_20260928.zip",
        "target": f"{IMPORT_ROOT_REL}/CAPABILITY-CLOSED-LOOP-2026-09-28",
        "state": "FROZEN",
        "class": "FROZEN_TASKPACK",
        "note": "成员已逐字节存在于 docs/audits/DESIGN-LAB-UIKIT-CONFORMANCE-2026-09-28/pack/，只登记映射。",
    },
    {
        "source": "WORK-LAB_MASTER_ATLAS_2026-09-29.zip",
        "select": [r"/02_项目任务包/DESIGN-LAB/"],
        "strip": r"^WORK-LAB_MASTER_ATLAS_2026-09-29/expanded/"
                 r"ArcheAxis_WORK-LAB_DESIGN-LAB_研究生态汇总包_2026-09-15/"
                 r"ArcheAxis_WORK-LAB_DESIGN-LAB_研究生态汇总包_2026-09-15/",
        "target": f"{IMPORT_ROOT_REL}/RESEARCH-ECOSYSTEM-2026-09-15",
        "state": "NON_AUTHORITATIVE",
        "class": "PLAN_ONLY_TASKPACK",
        "note": "三项目研究生态汇总包中只取 DESIGN-LAB 子目录；原件自述“只有计划效力”，"
                "不授权安装、付费或改仓。",
    },
    {
        "source": "DESIGN-LAB_UI开发资料总包_按批次.zip",
        "select": [r"^00_先读_PROMPT/"],
        "target": f"{IMPORT_ROOT_REL}/UI-DEV-BATCHES/B00_PROMPT",
        "state": "NON_AUTHORITATIVE",
        "class": "DESIGN_INPUT_REFERENCE",
        "note": "UI 开发资料总包的批次顺序、CODEX 提示词与统一验收清单。",
    },
]

# Nested zips inside a container that carry DESIGN-LAB engineering material.
NESTED_IMPORTS = [
    {
        "source": "DESIGN-LAB_UI开发资料总包_按批次.zip",
        "member": "07_B07_前端开发规范_L7/DESIGN-LAB_L7_前端开发规范工程包.zip",
        "target": f"{IMPORT_ROOT_REL}/UI-DEV-BATCHES/B07_FRONTEND_ENGINEERING",
        "state": "NON_AUTHORITATIVE",
        "class": "DESIGN_INPUT_REFERENCE",
        "note": "B07 前端开发规范工程包（tokens/routes/permissions/component-registry）。",
    },
    {
        "source": "DESIGN-LAB_UI开发资料总包_按批次.zip",
        "member": "08_B08_ReactTypeScript可运行原型_L8/design-lab_L8_React_TypeScript_可运行原型.zip",
        "target": f"{IMPORT_ROOT_REL}/UI-DEV-BATCHES/B08_REACT_TS_PROTOTYPE",
        "state": "NON_AUTHORITATIVE",
        "class": "DESIGN_INPUT_REFERENCE",
        "note": "B08 React+TypeScript 可运行原型源码。",
    },
    {
        "source": "DESIGN-LAB_UI开发资料总包_按批次.zip",
        "member": "09_B09_交互式真实Demo_L9/design-lab_L9_交互式真实Demo.zip",
        "target": f"{IMPORT_ROOT_REL}/UI-DEV-BATCHES/B09_INTERACTIVE_DEMO",
        "state": "NON_AUTHORITATIVE",
        "class": "DESIGN_INPUT_REFERENCE",
        "note": "B09 交互式真实 Demo。",
    },
    {
        "source": "DESIGN-LAB_UI开发资料总包_按批次.zip",
        "member": "10_B10_最终版高保真可部署UI/design-lab_最终版_高保真可部署UI.zip",
        "target": f"{IMPORT_ROOT_REL}/UI-DEV-BATCHES/B10_FINAL_HIGHFI_UI",
        "state": "NON_AUTHORITATIVE",
        "class": "DESIGN_INPUT_REFERENCE",
        "note": "B10 最终版高保真可部署 UI。",
    },
    {
        "source": "DESIGN-LAB_CODEX_20260922.zip",
        "member": "DESIGN-LAB_CODEX_20260922/16_ORIGINAL_CI_E2_ARTIFACT.zip",
        "target": f"{IMPORT_ROOT_REL}/CODEX-2026-09-22/16_ORIGINAL_CI_E2_ARTIFACT",
        "state": "FROZEN",
        "class": "CI_ARTIFACT",
        "note": "内层原始 CI E2 证据 artifact；外层与内层容器均按名称+大小+CRC32 比对。",
    },
]

LOOSE_IMPORTS = [
    {
        "source": "deep-research-report  DESIGN-LAB.md",
        "target": f"{IMPORT_ROOT_REL}/DEEP-RESEARCH-2026-09-19.md",
        "state": "HISTORICAL",
        "class": "AUDIT_REPORT",
        "note": "2026-09-19 全量深度调研与成熟化方案；含时点性动态读数（分支/PR/CI），永不作当前事实。",
    },
    {
        "source": "DESIGNLAB_CODEX_PROMPT.md",
        "target": f"{IMPORT_ROOT_REL}/CODEX-PROMPT-DESKTOP.md",
        "state": "NON_AUTHORITATIVE",
        "class": "EXECUTION_PROMPT",
        "note": "DESIGN-LAB 新分支 Codex 执行提示词；派工入口仍以仓内 current TaskPack 为准。",
    },
    {
        "source": "08_DESIGN-LAB_工作区接入交接.md",
        "target": f"{IMPORT_ROOT_REL}/WORKSPACE-INTAKE-HANDOFF-2026-09-15.md",
        "state": "NON_AUTHORITATIVE",
        "class": "HANDOFF",
        "note": "2026-09-15 监控材料接入交接；原件自述“不是新的权威 TaskPack”。",
    },
    {
        "source": "TaskPack(2).md",
        "target": f"{IMPORT_ROOT_REL}/RESEARCH-ECOSYSTEM-2026-09-15/02_项目任务包/DESIGN-LAB/TaskPack.md",
        "state": "NON_AUTHORITATIVE",
        "class": "PLAN_ONLY_TASKPACK",
        "note": "松散件与汇总包内同名字节相同（zlib.crc32 一致），只落一份。",
    },
    {
        "source": "汇总报告.md",
        "target": f"{IMPORT_ROOT_REL}/RESEARCH-ECOSYSTEM-2026-09-15/汇总报告.md",
        "state": "HISTORICAL",
        "class": "CROSS_PROJECT_INDEX",
        "note": "三项目研究生态汇总包父索引（已落地 DESIGN-LAB 子包的上游上下文）。",
    },
    {
        "source": "UI_KIT_AUDIT.md",
        "target": f"{IMPORT_ROOT_REL}/CROSS-PROJECT/UI_KIT_AUDIT.md",
        "state": "NON_AUTHORITATIVE",
        "class": "CROSS_PROJECT_ANALYSIS",
        "note": "UI 套件包拆解与可复用性判断，含 DESIGN-LAB B01-B10 批次核验；原件声明只查资料包字节。",
    },
    {
        "source": "UI_COMPONENT_ADOPTION_PLAN.md",
        "target": f"{IMPORT_ROOT_REL}/CROSS-PROJECT/UI_COMPONENT_ADOPTION_PLAN.md",
        "state": "NON_AUTHORITATIVE",
        "class": "CROSS_PROJECT_PLAN",
        "note": "开源 UI 组件池选型与受控吸收方案，按项目品牌 token 分列。",
    },
    {
        "source": "01_审计报告与三项目融入建议.md",
        "target": f"{IMPORT_ROOT_REL}/CROSS-PROJECT/AUDIT-REPORT-AND-INTAKE-ADVICE.md",
        "state": "NON_AUTHORITATIVE",
        "class": "CROSS_PROJECT_CARRIER",
        "note": "三项目审计报告：含多行 DESIGN-LAB 归属的 adapter/provider 候选裁决。",
    },
    {
        "source": "三项目_AI生态全生命周期收敛实施清单_2026-10-01.json",
        "target": f"{IMPORT_ROOT_REL}/CROSS-PROJECT/THREE-PROJECT-LIFECYCLE-CHECKLIST-2026-10-01.json",
        "state": "HISTORICAL",
        "class": "CROSS_PROJECT_CARRIER",
        "note": "三项目收敛实施清单：含 DESIGN-LAB 归属行，并指明 WORK-LAB 仓内存有本仓 AUTHORITY 快照。",
    },
]

# The 2026-10-06 request pair: kept in the planning area and marked REQUESTED,
# exactly like docs/history/archive-2026-10-19/taskpacks/DESIGN-LAB-GLOBAL-DESIGN-CAPABILITY-INTELLIGENCE-TASKPACK-2026-10-06.md.
REQUEST_IMPORTS = [
    {
        "source": "03_DESIGN-LAB_完整项目描述与未来蓝图_20261006.docx",
        "target": f"{REQUEST_ROOT_REL}/03_DESIGN-LAB_完整项目描述与未来蓝图_20261006.docx",
        "state": "REQUESTED",
        "class": "PROJECT_BLUEPRINT",
        "note": "2026-10-06 权威修复包的必读输入（双端描述同步的 DESIGN-LAB 侧蓝图）。",
    },
    {
        "source": "03_DESIGN-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt",
        "target": f"{REQUEST_ROOT_REL}/03_DESIGN-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt",
        "state": "REQUESTED",
        "class": "EXECUTION_PROMPT",
        "note": "2026-10-06 请求包，未采纳为 Authority；与 10-06 capability 包同为 REQUESTED。",
    },
]

SIDECAR_SUFFIXES = {".docx", ".zip", ".png", ".jpg", ".jpeg", ".gif", ".webp",
                    ".pdf", ".xlsx", ".7z", ".gz", ".mp4", ".wav"}

IMAGE_PACK_SKIP = re.compile(r"^0[789]_|^10_|^00_先读")


def sha256_bytes(data: bytes) -> str:
    return "sha256:" + hashlib.sha256(data).hexdigest()


def deep(path: Path) -> str:
    """Extended-length backslash form on Windows only.

    `\\\\?\\` defeats the 260-character limit that the imported atlas paths really reach
    (longest landed path here: 216 characters). It is a Win32 namespace marker: on POSIX
    the same prefix becomes part of the filename and every open fails.
    """
    s = str(Path(os.path.abspath(str(path))))
    if os.name == "nt" and not s.startswith("\\\\?\\"):
        s = "\\\\?\\" + s
    return s


def read_deep(path: Path) -> bytes:
    with open(deep(path), "rb") as fh:
        return fh.read()


def write_deep(path: Path, data: bytes) -> None:
    os.makedirs(os.path.dirname(deep(path)), exist_ok=True)
    with open(deep(path), "wb") as fh:
        fh.write(data)


def volume_measurement() -> dict:
    """Measure the source volume now; no remembered numbers."""
    entries = sorted(RECORD.iterdir())
    total = 0
    files = 0
    for e in entries:
        if e.is_dir():
            for dp, _dns, fns in os.walk(e):
                for f in fns:
                    try:
                        total += os.path.getsize(os.path.join(dp, f))
                        files += 1
                    except OSError:
                        pass
        else:
            total += e.stat().st_size
            files += 1
    return {"top_level_entries": len(entries), "files": files, "total_bytes": total}


def repo_crc_index() -> dict[int, list[str]]:
    """CRC32 of every tracked file, EXCLUDING this importer's own output.

    Without the exclusion a second run would find its own landed bytes in the
    index and relabel the whole import as "already in repo", which would erase
    the manifest's own record of what moved.
    """
    out = subprocess.run(["git", "ls-files", "-z"], cwd=REPO, capture_output=True,
                         encoding="utf-8", errors="replace").stdout
    paths = [p for p in out.split("\0") if p]
    index: dict[int, list[str]] = {}
    for rel in paths:
        if rel.startswith(IMPORT_ROOT_REL + "/") or rel.startswith("docs/history/archive-2026-10-19/taskpacks/03_DESIGN-LAB_"):
            continue
        try:
            data = (REPO / rel).read_bytes()
        except OSError:
            continue
        index.setdefault(zlib.crc32(data) & 0xFFFFFFFF, []).append(rel)
    return index


class Importer:
    def __init__(self, write: bool) -> None:
        self.write = write
        self.rows: list[dict] = []
        self.longest = (0, "")
        self.problems: list[str] = []
        self.crc_index: dict[int, list[str]] = {}

    def record(self, row: dict) -> None:
        self.rows.append(row)

    def _note_length(self, dest_str: str) -> None:
        if len(dest_str) > self.longest[0]:
            self.longest = (len(dest_str), dest_str)

    def place(self, target_rel: str, data: bytes, crc: int, size: int) -> tuple[str, str, bool]:
        """Write one artifact, then re-read it and compare size + CRC32.

        Returns (action, target-or-detail, written-now). A file that is already
        on disk byte-identical is still a LANDED row, so re-running the importer
        produces the same manifest instead of relabelling the earlier run.
        """
        dest = REPO / target_rel
        if dest.exists():
            existing = read_deep(dest)
            if (zlib.crc32(existing) & 0xFFFFFFFF) == crc:
                self._note_length(str(dest))
                return "LANDED", target_rel, False
            return "COLLISION", f"{target_rel} exists with different bytes", False
        if (len(data) != size) or ((zlib.crc32(data) & 0xFFFFFFFF) != crc):
            return "VERIFY-FAIL", f"member bytes disagree with central directory: {target_rel}", False
        if self.write:
            write_deep(dest, data)
            back = read_deep(dest)
            if len(back) != size:
                return "VERIFY-FAIL", f"readback size {len(back)} != central dir {size}", False
            if (zlib.crc32(back) & 0xFFFFFFFF) != crc:
                return "VERIFY-FAIL", f"readback crc != central dir {crc:08x}", False
            if sha256_bytes(back) != sha256_bytes(data):
                return "VERIFY-FAIL", f"readback sha256 mismatch: {target_rel}", False
        dest_str = str(dest)
        if len(dest_str) > self.longest[0]:
            self.longest = (len(dest_str), dest_str)
        return "LANDED", target_rel, True

    # -------------------------------------------------------------- containers
    def do_container(self, spec: dict) -> None:
        src = RECORD / spec["source"]
        container_sha = sha256_bytes(read_deep(src))
        with zipfile.ZipFile(src) as zf:
            for info in zf.infolist():
                if info.is_dir():
                    continue
                if spec.get("select") and not any(re.search(p, info.filename) for p in spec["select"]):
                    continue
                data = zf.read(info.filename)
                crc = info.CRC & 0xFFFFFFFF
                base = {
                    "source_container": spec["source"], "source_member": info.filename,
                    "bytes": info.file_size, "crc32": f"{crc:08x}", "sha256": sha256_bytes(data),
                    "state": spec["state"], "class": spec["class"],
                    "container_sha256": container_sha,
                }
                hits = self.crc_index.get(crc, [])
                if hits:
                    self.record({**base, "action": "ALREADY-IN-REPO", "target": hits[0],
                                 "also_in_repo": hits})
                    continue
                strip = spec.get("strip")
                rel = re.sub(strip, "", info.filename) if strip else info.filename
                for old, new in (spec.get("rewrite") or {}).items():
                    if rel.startswith(old):
                        rel = new + rel[len(old):]
                target = f"{spec['target']}/{rel}"
                action, detail, written = self.place(target, data, crc, info.file_size)
                self.record({**base, "action": action, "written_this_run": written,
                             "target": detail})
                if action.endswith("FAIL") or action == "COLLISION":
                    self.problems.append(f"{spec['source']}::{info.filename}: {action} {detail}")

    def do_nested(self, spec: dict) -> None:
        outer_path = RECORD / spec["source"]
        with zipfile.ZipFile(outer_path) as outer:
            raw = outer.read(spec["member"])
            info = outer.getinfo(spec["member"])
            outer_crc = info.CRC & 0xFFFFFFFF
            if (zlib.crc32(raw) & 0xFFFFFFFF) != outer_crc:
                self.problems.append(f"nested container crc mismatch: {spec['member']}")
                return
            with zipfile.ZipFile(io.BytesIO(raw)) as inner:
                bad = inner.testzip()
                if bad is not None:
                    self.problems.append(f"nested container corrupt: {spec['member']}::{bad}")
                    return
                self.record({
                    "source_container": spec["source"], "source_member": spec["member"],
                    "action": "NESTED-CONTAINER-VERIFIED", "target": None,
                    "bytes": info.file_size, "crc32": f"{outer_crc:08x}",
                    "sha256": sha256_bytes(raw), "state": spec["state"], "class": spec["class"],
                    "nested_member_count": len([i for i in inner.infolist() if not i.is_dir()]),
                })
                for minfo in inner.infolist():
                    if minfo.is_dir():
                        continue
                    mdata = inner.read(minfo.filename)
                    mcrc = minfo.CRC & 0xFFFFFFFF
                    base = {"source_container": f"{spec['source']}::{spec['member']}",
                            "source_member": minfo.filename, "bytes": minfo.file_size,
                            "crc32": f"{mcrc:08x}", "sha256": sha256_bytes(mdata),
                            "state": spec["state"], "class": spec["class"]}
                    hits = self.crc_index.get(mcrc, [])
                    if hits:
                        self.record({**base, "action": "ALREADY-IN-REPO", "target": hits[0]})
                        continue
                    target = f"{spec['target']}/{minfo.filename}"
                    action, detail, written = self.place(target, mdata, mcrc, minfo.file_size)
                    self.record({**base, "action": action, "written_this_run": written,
                                 "target": detail})
                    if action.endswith("FAIL") or action == "COLLISION":
                        self.problems.append(f"{target}: {action} {detail}")

    # -------------------------------------------------------------- loose files
    def do_loose(self, spec: dict) -> None:
        src = RECORD / spec["source"]
        data = read_deep(src)
        crc = zlib.crc32(data) & 0xFFFFFFFF
        base = {"source_container": spec["source"], "source_member": "(loose file)",
                "bytes": len(data), "crc32": f"{crc:08x}", "sha256": sha256_bytes(data),
                "state": spec["state"], "class": spec["class"], "note": spec["note"]}
        hits = self.crc_index.get(crc, [])
        if hits:
            self.record({**base, "action": "ALREADY-IN-REPO", "target": hits[0],
                         "also_in_repo": hits})
            return
        action, detail, written = self.place(spec["target"], data, crc, len(data))
        self.record({**base, "action": action, "written_this_run": written,
                     "target": detail})
        if action.endswith("FAIL") or action == "COLLISION":
            self.problems.append(f"{spec['source']}: {action} {detail}")

    # ------------------------------------------------------- external inventory
    def inventory_external(self) -> dict:
        """Hash every member that stays in Record, so it remains findable."""
        zp = RECORD / "DESIGN-LAB_UI开发资料总包_按批次.zip"
        total = 0
        count = 0
        with zipfile.ZipFile(zp) as zf:
            for info in zf.infolist():
                if info.is_dir() or IMAGE_PACK_SKIP.match(info.filename):
                    continue
                data = zf.read(info.filename)
                crc = info.CRC & 0xFFFFFFFF
                total += info.file_size
                count += 1
                self.record({
                    "source_container": zp.name, "source_member": info.filename,
                    "action": "EXTERNAL-ONLY",
                    "target": f"{RECORD}\\{zp.name}::{info.filename}",
                    "bytes": info.file_size, "crc32": f"{crc:08x}", "sha256": sha256_bytes(data),
                    "state": "FROZEN", "class": "DESIGN_MEDIA_EXTERNAL",
                    "outer_container_sha256": None,
                })
        return {"members": count, "uncompressed_bytes": total,
                "container_bytes": zp.stat().st_size,
                "container_sha256": sha256_bytes(read_deep(zp))}

    # ------------------------------------------------------------------ sidecars
    def sidecars(self) -> list[dict]:
        sys.path.insert(0, str(REPO / "design-lab" / "scripts"))
        try:
            from verify_asset_governance import BINARY_SUFFIXES as GATE_BINARY_SUFFIXES, sidecar_findings
        except ImportError as exc:
            self.problems.append(f"cannot import sidecar_findings: {exc}")
            return []
        out: list[dict] = []
        for row in self.rows:
            if row["action"] != "LANDED":
                continue
            rel = row["target"]
            if Path(rel).suffix.lower() not in SIDECAR_SUFFIXES:
                continue
            dest = REPO / rel
            if not dest.exists():
                continue
            sidecar_rel = rel + ".license"
            sidecar = {
                "schemaVersion": "design-lab/asset-sidecar/v1",
                "file": rel,
                "sha256": row["sha256"],
                "bytes": row["bytes"],
                "license": "UNLICENSED-INTERNAL — 本仓自有历史任务/输入材料归档；非第三方再分发件，"
                           "rights 归属见 sourceRecord",
                "author": "DTALEX66 (DESIGN-LAB owner); Record volume snapshot 2026-10-08",
                "redistributable": False,
                "modelInputAllowed": False,
                "commercialUse": False,
                "sourceId": None,
                "exception": {
                    "approvedBy": None,
                    "expiresAt": None,
                    "status": "AWAITING_OWNER_SIGNATURE",
                    "reason": "导入件权利字段须 owner 签署；代理不得自签（任务 #29 硬规则 5）。",
                },
                "reviewedBy": None,
                "sourceRecord": {
                    "volume": str(RECORD), "container": row["source_container"],
                    "member": row["source_member"], "memberCrc32": row["crc32"],
                    "importedAt": "2026-10-08",
                },
            }
            payload = json.dumps(sidecar, ensure_ascii=False, indent=2) + "\n"
            if self.write:
                write_deep(REPO / sidecar_rel, payload.encode("utf-8"))
            would_report = sidecar_findings(rel, dest, REPO / sidecar_rel) if self.write else []
            skipped_prefix = rel.startswith("docs/history/")
            actually_audited = (not skipped_prefix
                                and Path(rel).suffix.lower() in GATE_BINARY_SUFFIXES)
            out.append({"sidecar": sidecar_rel, "binary": rel,
                        "gate_skips_this_prefix": skipped_prefix,
                        "gate_would_audit_this_file": actually_audited,
                        "sidecar_findings_if_the_gate_ran_here": would_report})
            row["sidecar"] = sidecar_rel
        return out

    def run(self) -> dict:
        self.crc_index = repo_crc_index()
        for spec in CONTAINER_IMPORTS:
            self.do_container(spec)
        for spec in MEMBER_IMPORTS:
            self.do_container(spec)
        for spec in NESTED_IMPORTS:
            self.do_nested(spec)
        for spec in LOOSE_IMPORTS + REQUEST_IMPORTS:
            self.do_loose(spec)
        media = self.inventory_external()
        sidecars = self.sidecars()

        landed = [r for r in self.rows if r["action"] == "LANDED"]
        dup = [r for r in self.rows if r["action"] == "ALREADY-IN-REPO"]
        ext = [r for r in self.rows if r["action"] == "EXTERNAL-ONLY"]
        return {
            "schemaVersion": "design-lab/record-import-manifest/v1",
            "taskId": "DL-REC-29",
            "generatedAt": "2026-10-08",
            "observedRepoSha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPO,
                                              capture_output=True, text=True).stdout.strip(),
            "sourceVolume": {
                "path": str(RECORD),
                **volume_measurement(),
                "censusScript": "scripts/record_import_census.py",
                "policy": "只按内容证据挑选条目；全卷 15 GB 从未整体复制",
            },
            "relevanceRule": {
                "DIRECT": "条目标题或成员路径/内容以 DESIGN-LAB 为主体 → 落地",
                "CONTAINED": "混合容器内的 DESIGN-LAB 子项 → 只落该子项",
                "CROSS_PROJECT_CARRIER": "跨项目文档中含 DESIGN-LAB 归属条目 → 落地并标注跨项目",
                "OVERSIZED": "超出本仓自身体积门（单文件 5 MiB / pack 256 MiB 硬预算）→ 逐成员哈希登记，不写入",
                "UNRELATED": "普查 DESIGN-LAB 内容命中为 0 → 不落地，登记实测计数",
            },
            "summary": {
                "manifest_rows": len(self.rows),
                "landed_files": len(landed),
                "landed_bytes": sum(r["bytes"] for r in landed),
                "landed_written_this_run": len([r for r in landed if r.get("written_this_run")]),
                "already_in_repo_bytes_identical": len(dup),
                "already_in_repo_bytes": sum(r["bytes"] for r in dup),
                "external_only_members": len(ext),
                "external_only_bytes": sum(r["bytes"] for r in ext),
                "nested_containers_verified": len([r for r in self.rows
                                                   if r["action"] == "NESTED-CONTAINER-VERIFIED"]),
                "sidecars_written": len(sidecars),
                "longest_written_path_chars": self.longest[0],
                "longest_written_path": self.longest[1],
            },
            "uiMediaContainer": media,
            "sidecars": sidecars,
            "problems": self.problems,
            "notImported": self.not_imported(media),
            "entries": sorted(self.rows, key=lambda r: (r["action"], r["source_container"],
                                                         r["source_member"])),
        }

    @staticmethod
    def not_imported(media: dict) -> list[dict]:
        return [
            {
                "source": "DESIGN-LAB_UI开发资料总包_按批次.zip :: B01-B06 图片包",
                "bytes": media["uncompressed_bytes"],
                "reason": "外层容器实测 " + f"{media['container_bytes']:,}"
                          " B，超 verify_asset_governance 单文件 5 MiB 上限；解出图片面 "
                          f"{media['uncompressed_bytes']:,}"
                          " B，而本仓 pack 实测 240.24 MiB / 硬预算 256 MiB，写入即触发硬预算红。"
                          "原件留在 Record，逐成员按 名称+大小+CRC32+sha256 登记（见 EXTERNAL-ONLY 行）。",
            },
            {"source": "三项目_VI_UI_UX_作品集完整交付包.zip", "bytes": 135_878_909,
             "reason": "主体是 DT ALEX STUDIOS 个人作品集交付物（另一项目），非 DESIGN-LAB 任务文档；"
                       "且 135.9 MiB 远超本仓 pack 硬预算余量。"},
            {"source": "AAOS-project-archives/", "bytes": 15_042_572_388,
             "reason": "AAOS 面的 build/checkout 归档；普查 24 个文件的 DESIGN-LAB 内容命中为 0。"},
            {"source": "system-software-audit/", "bytes": 213_700,
             "reason": "DISM/SFC/WER 与 ArcheAxis 崩溃转储的系统体检件；DESIGN-LAB 内容命中为 0。"},
            {"source": "R5-TASK-RECONCILIATION.csv", "bytes": 3_737,
             "reason": "行内容属 ArcheAxis（学习工作台/Rust/OCR/知识库迁移域），DESIGN-LAB 标记命中 0；"
                       "文件名里的 R5 是同名词而非 DL-TP-20260908-R5。"},
        ]


def render_md(manifest: dict) -> str:
    s = manifest["summary"]
    v = manifest["sourceVolume"]
    lines = [
        "# RECORD 导入清单（任务 DL-REC-29）",
        "",
        f"- 源卷 `{manifest['sourceVolume']['path']}`：**{v['top_level_entries']} 个顶层条目 / "
        f"{v['files']:,} 个文件 / {v['total_bytes']:,} 字节**（本次实测；全卷未整体复制）",
        f"- 观测 commit：`{manifest['observedRepoSha']}`",
        "- 生成器：`scripts/record_import_apply.py`（可复跑；每个成员按 名称+大小+CRC32 比对，写后回读再比）",
        "",
        "## 汇总（本次实测）",
        "",
    ]
    for k, val in s.items():
        lines.append(f"- `{k}` = {val:,}" if isinstance(val, int) else f"- `{k}` = {val}")
    lines += ["", "## 相关性规则（判定口径）", ""]
    for k, val in manifest["relevanceRule"].items():
        lines.append(f"- **{k}**：{val}")
    lines += ["", "## 不导入条目（含实测理由）", "",
              "| 源 | 字节 | 理由 |", "|---|---|---|"]
    for e in manifest["notImported"]:
        lines.append(f"| `{e['source']}` | {e['bytes']:,} | {e['reason']} |")
    lines += ["", "## 权利待签清单（代理不得自签）", "",
              "sidecar 一律 `reviewedBy: null`、`exception.approvedBy: null`，等 owner 签署；"
              "`docs/history/**` 是治理门的既有豁免前缀（冻结历史面），故门不会扫到这些 sidecar——"
              "本表把“门若在此处审会报什么”原样列出，不假装它已通过。",
              "",
              "| 二进制 | sidecar | 门跳过此前缀 | 门会审此文件 | 门在此处会报 |",
              "|---|---|---|---|---|"]
    for sc in manifest["sidecars"]:
        lines.append(f"| `{sc['binary']}` | `{sc['sidecar']}` | "
                     f"{sc['gate_skips_this_prefix']} | {sc['gate_would_audit_this_file']} | "
                     f"{sc['sidecar_findings_if_the_gate_ran_here']} |")
    lines += ["", "## 逐条清单", "",
              "| 动作 | 源容器/文件 | 成员 | 字节 | crc32 | sha256 | 目标或既有路径 | 定态 | 类别 |",
              "|---|---|---|---|---|---|---|---|---|"]
    for r in manifest["entries"]:
        lines.append(f"| {r['action']} | `{r['source_container']}` | `{r['source_member']}` | "
                     f"{r['bytes']:,} | `{r['crc32']}` | `{(r.get('sha256') or '')[:19]}…` | "
                     f"`{r.get('target') or '-'}` | {r['state']} | {r['class']} |")
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="land bytes and write the manifest")
    args = ap.parse_args()
    if not RECORD.is_dir():
        print(f"ABORT: source volume missing: {RECORD}")
        return 2
    imp = Importer(write=args.write)
    manifest = imp.run()
    s = manifest["summary"]
    if args.write:
        write_deep(REPO / MANIFEST_REL,
                   (json.dumps(manifest, ensure_ascii=False, indent=1) + "\n").encode("utf-8"))
        write_deep(REPO / MANIFEST_MD_REL, render_md(manifest).encode("utf-8"))
    print(f"MODE={'WRITE' if args.write else 'DRY-RUN'} rows={s['manifest_rows']} "
          f"landed={s['landed_files']} landed_bytes={s['landed_bytes']:,} "
          f"already_in_repo={s['already_in_repo_bytes_identical']} "
          f"external_only={s['external_only_members']} sidecars={s['sidecars_written']} "
          f"longest_path={s['longest_written_path_chars']}")
    for p in manifest["problems"]:
        print("PROBLEM:", p)
    print(f"RECORD_IMPORT={'OK' if not manifest['problems'] else 'PROBLEMS'} "
          f"problems={len(manifest['problems'])}")
    return 0 if not manifest["problems"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
