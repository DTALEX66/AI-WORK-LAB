#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-AUTHORITY-2026-09-18-R2 — top-level Authority consistency gate.

Deterministic, stdlib-only verifier for the top-level Authority release. It
is the *successor* consistency gate; the DeepSeek predecessor chain
(``scripts/verify_authority_gates.py``) keeps running and stays subordinate —
this gate checks the R2 top-level surface and never re-implements the
DeepSeek lineage chain.

Checks (all fail-closed; any FAIL makes the exit code 1):

1.  ``AUTHORITY.md`` exists at the repository root;
2.  ``.project/governance/authority-index.json`` parses as JSON, is a
    non-empty object, and its ``authorityId`` equals the ID declared in
    ``AUTHORITY.md``;
3.  every path listed in the index ``current`` array exists in the tree;
4.  no path listed as ``current`` is also claimed as historical — a path
    matching ``historicalGlobs`` or listed in ``historicalSpecific`` may
    not be CURRENT;
5.  the current integrated TaskPack (``taskpackClassificationRule.
    currentIntegrated``) exists;
6.  root ``AGENTS.md`` is Authority-first: it carries the
    ``TOP-LEVEL AUTHORITY — MUST READ FIRST`` section and names both the
    authority ID and ``/AUTHORITY.md``;
7.  the UCR convergence handoff, if present, carries the
    ``HISTORICAL_EXECUTION_RECORD / NON_AUTHORITATIVE`` banner and no
    longer claims to be a tracked authority handoff;
8.  the single Ruff fact: ``docs/architecture/LANGUAGE-POLICY.md`` does
    not still carry the stale ``DECLARED_NOT_ENFORCED`` wording;
9.  R2 release integrity: the four landed release files byte-match the
    published R2 MANIFEST hashes (static fact of this release; dynamic
    state such as branch counts or CI numbers are deliberately NOT
    frozen here — they must be live-read on every audit).

The gate is read-only against the working tree: it writes nothing except an
ignored run record under ``.project-local/task-artifacts/`` so the CI job
and the clean-tree gate observe identical facts.

Usage:
    python scripts/verify_top_level_authority.py
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
RECORD = REPO / ".project-local/task-artifacts/top-authority-gates/latest.json"

sys.path.insert(0, str(Path(__file__).resolve().parent))
from archive_records import RecordUnavailable, read_record  # noqa: E402

AUTHORITY_ID = "DL-AUTHORITY-2026-09-18-R2"

# Static release integrity facts: the four R2 landing files and the byte
# hashes published in the R2 package MANIFEST. These pin the release
# content; they do not pin any dynamic repository state.
#
# 2026-09-20 re-pin (AUTHORITY §17: owner intent = "全部授权"; reason = P1-D/P1-E
# close-out below; superseded = the R2 values; impact = the gate re-pins to the
# post-R2 content, so a stale drift entry can no longer be enforced as truth):
#   AUTHORITY.md                   49e21069… -> f7c1e6ad…  (§15 P0 close-out)
#   authority-index.json           465f8eba… -> 38c01eb0…  (P1-E: cleared the two
#     drift entries that no longer exist — AGENTS already mandates Authority
#     first-read; the LANGUAGE-POLICY Node-build wording was corrected)
# CI readback: `scripts/verify_top_level_authority.py` (canonical-verify.yml
# line 116) must return TOP_AUTHORITY_GATE=PASS checks=10 failed=[].
#
# 2026-09-27 re-pin (AUTHORITY §17: owner intent = "整理梳理本项目，更新 AUTHORITY.md 的
# 动态事实快照"; reason = §13 is the *establishment* snapshot but its numbers were being
# read as current — live readback gives 9 required checks / 1 remote branch / 10 workbench
# files against the file's 7 / 28 / 3; superseded = f7c1e6ad…; impact = §13.1 added as an
# explicitly dated live readback (the historical §13 snapshot is preserved verbatim) and
# the three present-tense "7 项 required checks" claims in §15 corrected, so the file no
# longer asserts stale dynamic facts; no static release content removed; checks count
# unchanged at 10):
#   AUTHORITY.md                   f7c1e6ad… -> 7b29d3ea…  (§13.1 live readback)
# 2026-10-12 re-pin: AUTHORITY.md alone, after correcting its stale "commit=NOT_EXECUTED / do not
# claim the remote is synced" claims. Reason and superseded digest:/n# docs/history/taskpacks/20261009-adoption/AUTHORITY-PIN-CHANGE.json revisions[]. Checks stay at 10.
# 2026-10-09 owner adoption: see docs/taskpacks/20261009-ui-first/CONVERSATION-DECISIONS.md; old bytes in docs/history/taskpacks/20261009-adoption/pre-adoption/.
# New dispatch is additionally pinned; the old taskpack bytes stay pinned as frozen lineage.
# 2026-10-19 re-pin for the owner direction adoption: AUTHORITY.md and the authority index name
# docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md as the sole current pack, and that
# pack is pinned here and declared frozen. The predecessor pins stay so lineage bytes remain
# checked. Reason and superseded digests: docs/history/taskpacks/20261009-adoption/
# AUTHORITY-PIN-CHANGE.json revisions[]. Checks stay at 10.
# 2026-10-19 archive re-pin (owner instruction: stale material must leave the visible tree and
# old paths must stop resolving): the UCR handoff moved to docs/history/archive-2026-10-19/
# handoffs/, so AUTHORITY.md, the authority index and HISTORY-FREEZE-RULES.md now name that
# path. Reason, superseded digests and the checks run: docs/history/taskpacks/20261009-adoption/
# AUTHORITY-PIN-CHANGE.json revisions[]. Checks stay at 10.
# 2026-10-19 removal re-pin: the UCR handoff, the DeepSeek R5/H3 handoffs and the dated prompt copies
# were deleted on owner order after being aggregated, so these three surfaces now name the aggregate
# record and the removal manifest instead of a file that is no longer in the tree. Only those path
# sentences changed. Reason, from/to digests and the checks run: docs/history/taskpacks/20261009-adoption/
# AUTHORITY-PIN-CHANGE.json revisions[]. Checks stay at 10.
# 2026-10-20 re-pin (AUTHORITY §17: owner intent = 「1 可以做」「不锁死 做好菜单导航和接口 用户自行选择本地
# 或者是云端模型」「编号问题留出可填写位置」「三方素材和字库不在本项目范围内」「设计规范按照网上最专业的先
# 收入库里 后期落地我自行测试」; reason = 定点解冻与范围收口; superseded = the 2026-10-19 digests; impact =
# AUTHORITY.md gains the UNFREEZE-20261020-R1 adoption block and marks its own 「不实施产品功能」 clause as
# lifted for exactly three segments, and the index gains unfreezeAdoption so a later session reads the
# unfreeze list from the machine surface instead of re-deriving it from chat. The pinned direction taskpack
# bytes are NOT touched — it stays frozen lineage, superseded in part by the newer owner clause):
#   AUTHORITY.md                        4f7bd6c0… -> 7cd2db03…
#   authority-index.json                7658dfc5… -> fd01ce37…
# 2026-10-28 second re-pin (AUTHORITY §17: the same adoption; reason = the first AUTHORITY.md bytes wrote a pack-internal file path as if it were a repository path, and scripts/verify_path_refs.py resolves every backticked ref in AUTHORITY.md/AGENTS.md -- PATH_REF_GATE=FAIL checks=10 failed=['path-refs-resolve'] named evidence/relocation.json; the reference was reworded to say it is a file inside the delivered pack, not a repo path, rather than adding it to the allowlist_missing policy, which would have taught the gate to ignore a genuinely wrong reference; superseded = the first 2026-10-28 digests; impact = AUTHORITY.md bytes only, authority-index.json unchanged this time):
#   AUTHORITY.md                        e31fb1fa… -> 2bec69fc
# 2026-10-28 second re-pin (AUTHORITY §17: the same adoption; reason = the first AUTHORITY.md bytes wrote a pack-internal file path as if it were a repository path, and scripts/verify_path_refs.py resolves every backticked ref in AUTHORITY.md/AGENTS.md -- PATH_REF_GATE=FAIL checks=10 failed=['path-refs-resolve'] named evidence/relocation.json; the reference was reworded to say it is a file inside the delivered pack, not a repo path, rather than adding it to the allowlist_missing policy, which would have taught the gate to ignore a genuinely wrong reference; superseded = the first 2026-10-28 digests; impact = AUTHORITY.md bytes only, authority-index.json unchanged this time):
#   AUTHORITY.md                        e31fb1fa… -> 2bec69fc
# 2026-10-28 re-pin (AUTHORITY §17: owner intent = 「取消冻结的自动化任务  （D:\All projects\Record\新建文件夹     把这里的内容吃透）」「前端也同步上去自动化的菜单导航等」「并行执行 项目体积清理与规范化  执行合并迁移清理等相关执行，任何过时的陈旧的冗余的，该归档的归档 包括目录子文件夹等」「全部吸收融入本项目  和原先冻结的自动化任务进行合并」; reason = 外部软件自动化由冻结项转为可派工能力类、外来移植包按逐字节登记吸收、派生物清理与PR 收口获授权; superseded = the 2026-10-23 digests, and within desktopKbAdoption.stillFrozen the single entry EXTERNAL_SOFTWARE_AUTOMATION; impact = AUTHORITY.md gains the AUTOMATION-20261028-R1 adoption block and marks the 2026-10-23 「外部软件自动操作属未来能力」 sentence as a dated reading rather than deleting it, and authority-index.json gains automationAdoption and moves authorityRevision. HISTORY-FREEZE-RULES.md and the three pinned taskpacks are NOT touched -- the direction and desktop-KB packs stay byte-frozen and pinned, superseded in one clause each, never rewritten. Neither pin move removes a check:
#   AUTHORITY.md                        00126066… -> e31fb1fa
#   authority-index.json                9a0e1a58… -> 7ffe85d1)
# 2026-10-23 re-pin (AUTHORITY §17: owner intent = 「读取分析，按照这个执行（前端UI有新规划），并且归档到统一项目里,
# 更新覆盖替换到权威和规划里」「先分析拆解，加入到优先到任务台账里」; reason = 桌面 UI 与知识库进入当前派工、Record 投递包
# 归档、权威与规划覆盖替换; superseded = the 2026-10-20 digests; impact = AUTHORITY.md gains the
# DESKTOP-KB-20261023-R1 adoption block and marks the 2026-10-19 「当前唯一 integrated TaskPack」 sentence as a
# dated reading, and authority-index.json gains desktopKbAdoption plus the current/classification repoint to
# docs/taskpacks/DESIGN-LAB-DESKTOP-KB-INTEGRATED-TASKPACK-2026-10-23.md. The three pinned taskpacks and
# HISTORY-FREEZE-RULES.md are NOT touched — the direction pack stays frozen lineage, superseded in its
# dispatch-entry role only):
#   AUTHORITY.md                        7cd2db03… -> 00126066
#   authority-index.json                fd01ce37… -> 9a0e1a58
R2_RELEASE_HASHES = {
    "AUTHORITY.md": "2bec69fcc77939d82476ab12d5316c439469c4e7c53ceef0270fcd8ffa139fce",
    ".project/governance/authority-index.json": "7ffe85d1f4043c10940f889a84c9cebc30b36597b044da7f0cc95bc2a5c5051b",
    "docs/current/HISTORY-FREEZE-RULES.md": "3573b88df6c04be6fa6932327aff94ad8c547a43bfcbc6a3337d4bad50a71322",
    "docs/taskpacks/DESIGN-LAB-FINAL-AUTHORITY-CONVERGENCE-TASKPACK-2026-09-18.md": "62f43ef295d4e90462d1e49e657e490400c4b5568f4e4ad1db3e268e12bb10c7",
    "docs/taskpacks/DESIGN-LAB-UI-FIRST-INTEGRATED-TASKPACK-2026-10-09.md": "2cfd84627352e9f1b29b42787fa43466cd9a836130d826d43678b7733856ffda",
    "docs/taskpacks/DESIGN-LAB-DIRECTION-ALIGNMENT-2026-10-19.md": "98e7d2210181de8a4a3a0c2d8c15c4846b332e3e418a02446a0bb001a1c2e116",
}

HISTORICAL_GLOB_FILES = (
    "docs/history/archive-2026-10-19/handoffs/DESIGN-LAB-UCR-CONVERGENCE-20260918-HANDOFF.md",
)


def load_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def check_authority_md(checks: list[dict]) -> str:
    path = REPO / "AUTHORITY.md"
    if not path.is_file():
        checks.append({"check": "authority-md-exists", "result": "FAIL", "detail": "AUTHORITY.md missing at repository root"})
        return "FAIL"
    text = path.read_text(encoding="utf-8")
    ids = re.findall(r"DL-AUTHORITY-[0-9]{4}-[0-9]{2}-[0-9]{2}-R[0-9]+", text)
    if AUTHORITY_ID not in text:
        checks.append({"check": "authority-id-declared", "result": "FAIL", "detail": f"{AUTHORITY_ID} not declared in AUTHORITY.md"})
        return "FAIL"
    others = [i for i in ids if i != AUTHORITY_ID]
    if others:
        checks.append({"check": "single-authority-id", "result": "FAIL", "detail": f"foreign authority IDs declared: {others}"})
        return "FAIL"
    checks.append({"check": "authority-md-exists", "result": "PASS", "detail": AUTHORITY_ID})
    return "PASS"


def check_index(checks: list[dict]) -> tuple[dict, str]:
    path = REPO / ".project" / "governance" / "authority-index.json"
    if not path.is_file():
        checks.append({"check": "authority-index-exists", "result": "FAIL", "detail": "authority-index.json missing under .project/governance/"})
        return {}, "FAIL"
    try:
        index = load_json(path)
    except (json.JSONDecodeError, OSError) as exc:
        checks.append({"check": "authority-index-valid", "result": "FAIL", "detail": f"index does not parse: {exc}"})
        return {}, "FAIL"
    if not isinstance(index, dict) or not index:
        checks.append({"check": "authority-index-valid", "result": "FAIL", "detail": "index must be a non-empty JSON object"})
        return {}, "FAIL"
    if index.get("authorityId") != AUTHORITY_ID:
        checks.append({"check": "authority-id-consistent", "result": "FAIL",
                      "detail": f"index authorityId={index.get('authorityId')!r} != {AUTHORITY_ID}"})
        return index, "FAIL"
    checks.append({"check": "authority-index-valid", "result": "PASS", "detail": AUTHORITY_ID})
    checks.append({"check": "authority-id-consistent", "result": "PASS", "detail": "index and AUTHORITY.md agree"})
    return index, "PASS"


def check_current_paths(index: dict, checks: list[dict]) -> None:
    missing = [p for p in index.get("current", []) if not (REPO / p).is_file()]
    if missing:
        checks.append({"check": "current-paths-exist", "result": "FAIL", "detail": f"current paths missing: {missing}"})
        return
    checks.append({"check": "current-paths-exist", "result": "PASS", "detail": f"{len(index.get('current', []))} current paths present"})


def check_history_conflict(index: dict, checks: list[dict]) -> None:
    current = set(index.get("current", []))
    specific = {e.get("path") for e in index.get("historicalSpecific", []) if isinstance(e, dict)}
    # A path may be BOTH a designated lineage reference (frozen PRODUCT LINEAGE,
    # e.g. the R5 tasks.json under docs/history/) AND live under a historical
    # location: that is the intended classification, not a collision. Only a
    # CURRENT entry that matches a historical glob/specific AND is NOT in
    # taskpackClassificationRule.lineage is a genuine CURRENT-vs-HISTORICAL
    # contradiction.
    lineage = set(index.get("taskpackClassificationRule", {}).get("lineage", []))
    globs = index.get("historicalGlobs", [])
    import fnmatch

    def is_glob(path: str) -> bool:
        return any(fnmatch.fnmatch(path, g) for g in globs)

    conflict = sorted(p for p in current if p in specific and p not in lineage)
    glob_hit = sorted(p for p in current if is_glob(p) and p not in lineage)
    if conflict or glob_hit:
        checks.append({"check": "no-historical-collision", "result": "FAIL",
                       "detail": f"paths claimed CURRENT but historical (not lineage): {conflict + glob_hit}"})
        return
    checks.append({"check": "no-historical-collision", "result": "PASS",
                   "detail": "CURRENT set disjoint from historical globs/specifics (lineage references exempt)"})


def check_taskpack(index: dict, checks: list[dict]) -> None:
    rule = index.get("taskpackClassificationRule", {})
    integrated = rule.get("currentIntegrated", "")
    if not integrated:
        checks.append({"check": "current-integrated-taskpack", "result": "FAIL", "detail": "taskpackClassificationRule.currentIntegrated missing"})
        return
    if not (REPO / integrated).is_file():
        checks.append({"check": "current-integrated-taskpack", "result": "FAIL", "detail": f"{integrated} missing"})
        return
    checks.append({"check": "current-integrated-taskpack", "result": "PASS", "detail": integrated})


def check_agents(checks: list[dict]) -> None:
    path = REPO / "AGENTS.md"
    if not path.is_file():
        checks.append({"check": "agents-authority-first", "result": "FAIL", "detail": "AGENTS.md missing"})
        return
    text = path.read_text(encoding="utf-8")
    problems = []
    if "TOP-LEVEL AUTHORITY" not in text:
        problems.append("no 'TOP-LEVEL AUTHORITY' section")
    if AUTHORITY_ID not in text:
        problems.append(f"does not name {AUTHORITY_ID}")
    if "/AUTHORITY.md" not in text:
        problems.append("does not point to /AUTHORITY.md")
    # the section must precede the operational taskpack section so it is read first
    marker = text.find("TOP-LEVEL AUTHORITY")
    taskpack = text.find("当前任务包")
    if marker != -1 and taskpack != -1 and marker > taskpack:
        problems.append("authority section is not first")
    if problems:
        checks.append({"check": "agents-authority-first", "result": "FAIL", "detail": "; ".join(problems)})
        return
    checks.append({"check": "agents-authority-first", "result": "PASS", "detail": "AGENTS.md names the top authority first"})


def check_handoff_demoted(checks: list[dict]) -> None:
    rel = HISTORICAL_GLOB_FILES[0]
    try:
        raw, where = read_record(rel)
    except RecordUnavailable as exc:
        checks.append({"check": "handoff-demoted", "result": "FAIL", "detail": str(exc)})
        return
    text = raw.decode("utf-8", errors="replace")
    problems = []
    if "HISTORICAL_EXECUTION_RECORD" not in text or "NON_AUTHORITATIVE" not in text:
        problems.append("missing HISTORICAL_EXECUTION_RECORD / NON_AUTHORITATIVE banner")
    if "tracked 权威交接" in text:
        problems.append("still claims to be a tracked authority handoff")
    if problems:
        checks.append({"check": "handoff-demoted", "result": "FAIL", "detail": "; ".join(problems)})
        return
    checks.append({"check": "handoff-demoted", "result": "PASS",
                   "detail": f"UCR handoff carries the historical banner (read from {where})"})


def check_ruff_fact(checks: list[dict]) -> None:
    path = REPO / "docs" / "architecture" / "LANGUAGE-POLICY.md"
    if not path.is_file():
        checks.append({"check": "single-ruff-fact", "result": "FAIL", "detail": "LANGUAGE-POLICY.md missing"})
        return
    text = path.read_text(encoding="utf-8")
    if "DECLARED_NOT_ENFORCED" in text:
        checks.append({"check": "single-ruff-fact", "result": "FAIL",
                       "detail": "stale DECLARED_NOT_ENFORCED wording remains; the single fact is CONFIGURED_NOT_ENFORCED"})
        return
    if "CONFIGURED_NOT_ENFORCED" not in text:
        checks.append({"check": "single-ruff-fact", "result": "FAIL", "detail": "CONFIGURED_NOT_ENFORCED not stated"})
        return
    checks.append({"check": "single-ruff-fact", "result": "PASS", "detail": "ruff: CONFIGURED_NOT_ENFORCED"})


def check_release_integrity(checks: list[dict]) -> None:
    import hashlib

    problems = []
    for rel, expected in R2_RELEASE_HASHES.items():
        path = REPO / rel
        if not path.is_file():
            problems.append(f"{rel} missing")
            continue
        actual = hashlib.sha256(path.read_bytes()).hexdigest()
        if actual != expected:
            problems.append(f"{rel} hash {actual[:12]} != published {expected[:12]}")
    if problems:
        checks.append({"check": "r2-release-integrity", "result": "FAIL", "detail": "; ".join(problems)})
        return
    checks.append({"check": "r2-release-integrity", "result": "PASS", "detail": f"{len(R2_RELEASE_HASHES)} lineage/current files match the owner-adopted integrity pins"})


def main() -> int:
    checks: list[dict] = []
    check_authority_md(checks)
    index, _ = check_index(checks)
    if isinstance(index, dict) and index:
        check_current_paths(index, checks)
        check_history_conflict(index, checks)
        check_taskpack(index, checks)
    check_agents(checks)
    check_handoff_demoted(checks)
    check_ruff_fact(checks)
    check_release_integrity(checks)

    failed = [c for c in checks if c["result"] not in ("PASS",)]
    verdict = "PASS" if not failed else "FAIL"
    record = {
        "schemaVersion": "design-lab/top-authority-gate/v1",
        "authorityId": AUTHORITY_ID,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "checks": checks,
        "failed": [c["check"] for c in failed],
        "verdict": verdict,
        "meaning": "PASS = the owner-amended top-level Authority surface is internally consistent; "
                   "dynamic facts (branches/PRs/CI) are intentionally NOT frozen here and "
                   "must be live-read on every audit",
    }
    RECORD.parent.mkdir(parents=True, exist_ok=True)
    RECORD.write_text(json.dumps(record, indent=2, ensure_ascii=False) + "\n", encoding="utf-8", newline="\n")
    for c in checks:
        print(f"{c['result']:6s} {c['check']:28s} {c['detail']}")
    print(f"TOP_AUTHORITY_GATE={verdict} checks={len(checks)} failed={record['failed'] or 'none'}")
    return 0 if verdict == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
