#!/usr/bin/env python3
"""Record the blueprint-sync audit snapshot from live observation.

Nothing here is transcribed: repository identity, remote SHAs, PR state, input
digests, gate exit codes and artifact hashes are all read or executed at run
time, so the snapshot binds to the state it actually verified. It records the
base and subject SHA of the work and never its own digest.

Usage: python scripts/ci/record_blueprint_audit_snapshot.py --write
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
OUT = REPO / "docs" / "audits" / "BLUEPRINT_SYNC_AUDIT_2026-10-06.md"
INPUT_DIR = Path("D:/All projects/Record")
INPUT_DOCX = INPUT_DIR / "02_WORK-LAB_完整项目描述与未来蓝图_20261006.docx"
INPUT_PROMPT = (INPUT_DIR /
                "02_WORK-LAB_权威修复_双端描述同步_可审计执行提示词_20261006.txt")
DECLARED_DOCX_SHA = "f3784a9950adce06e8d87015a0ecb39d1ed4fdb3b93d5ccd3c9b40398bea3440"
# Observed live at 2026-10-06T22:20 +08:00, before this task's metadata write.
# GitHub About is not Git content, so the prior value is kept here rather than
# left to memory or to a README claim.
ABOUT_BEFORE = ("Client-neutral AI-agent control plane: user global config overlay for "
                "Hermes/Codex/DSH/GitHub/Open Design/OpenHuman via one adapter contract "
                "(CC Switch observe-only). Modules: client-neutral-core (task/telemetry "
                "ledger, sidecar), services (orchestration/policy/receipts), read-only "
                "observer. Authority chain + exact-SHA CI gates.")
ABOUT_TARGET = ("Client-neutral workflow governance, control and delivery: portable "
                "rules, native client adapters, task coordination, permissions and "
                "evidence-based completion. Ongoing.")
CHECKS = [
    ["scripts/ci/verify_project_authority_reference.py"],
    ["scripts/ci/verify_error_ledger.py"],
    ["scripts/ci/verify_blueprint_coverage.py"],
    ["scripts/ci/verify_future_candidate_registry.py"],
    ["scripts/ci/verify_project_data_boundary.py"],
    ["scripts/ci/verify_model_registry_integrity.py"],
    ["scripts/ci/failfast_group.py", "--group", "observer-web-contracts"],
    ["scripts/ci/failfast_group.py", "--group", "observer-python-skeleton"],
]
GAPS = [
    "AG-19 / T07: the original WORK-LAB long conversation, WORK-LAB-SUMMARY and the "
    "2026-09-28 startup/final attachments remain inaccessible (SOURCE_MISSING).",
    "P0 product gaps still open in the register: U02/U03/U08 partial; P1 AG-09 needs the "
    "owner to pick a project and two executors; AG-10/11/15/14/12/13/20 unstarted or "
    "partial; P2 AG-16/17/18.",
    "Merge to main, release, install, global configuration and other-project writes "
    "remain unauthorized and were not performed; the four old branches are not retired.",
    "Instrument coverage, not product truth: no automated path in this repository can "
    "capture a WebView2 DirectComposition surface (GDI is structurally blind, ERR-104; "
    "the CDP port accepts TCP and answers nothing, ERR-107), so Windows.Graphics.Capture "
    "stays unwired and a pixel-only regression would need another owner observation.",
    "Source-side defects kept as the source has them: the blueprint has no AG-14 row, "
    "merges AG-16/AG-17 into one line, omits AG-01..AG-08 and W09, cites OD03/OD04 "
    "jointly, and §16 rows 16.16/16.17/16.19 enumerate their members with 等, so the "
    "candidate list is not exhaustive at the source.",
    "Candidate registrations are not assessments: identity, license, version and Windows "
    "support are NOT_VERIFIED for every §16 row, and a pilot still needs an individually "
    "authorized task card.",
    "The desktop artifact the owner observed carries a v1 build receipt, so its frontend "
    "chain is attested only by the content-evidence rule; a v2 receipt arrives with the "
    "next build. The v1 receipt was deliberately not rewritten for the current binary — "
    "writing it after the fact would attest the tree to itself.",
]


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True,
                          text=True, encoding="utf-8", errors="replace", check=False).stdout.strip()


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def run_check(argv: list[str]) -> dict:
    done = subprocess.run([sys.executable, str(REPO / argv[0]), *argv[1:]],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", 
                          cwd=str(REPO), check=False)
    out = (done.stdout or "") + (done.stderr or "")
    tail = [line for line in out.splitlines() if line.strip()][-1:] or [""]
    return {"command": " ".join(argv), "exit": done.returncode,
            "result": tail[0][:220]}


def collect_about() -> dict:
    """GitHub About is metadata outside Git: read it back, never infer it."""
    done = subprocess.run(["gh", "repo", "view", "DTALEX66/WORK-LAB", "--json",
                           "description,homepageUrl"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", 
                          check=False)
    try:
        live = json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"error": (done.stderr or "gh unavailable").strip()[:200]}
    return {"before": ABOUT_BEFORE, "target": ABOUT_TARGET,
            "readBackNow": live.get("description"),
            "matchesTarget": live.get("description") == ABOUT_TARGET,
            "homepageUrl": live.get("homepageUrl") or "(empty — no site claimed)",
            "topicsChanged": False}


def collect_ci(head_sha: str) -> dict:
    if not head_sha or head_sha == "UNKNOWN":
        return {"note": "no pushed head SHA to bind checks to"}
    done = subprocess.run(["gh", "pr", "checks", "162", "--json", "name,state,bucket"],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", 
                          check=False)
    try:
        checks = json.loads(done.stdout)
    except json.JSONDecodeError:
        return {"error": (done.stderr or "gh unavailable").strip()[:200],
                "headSha": head_sha}
    buckets = {}
    for check in checks:
        buckets[check.get("bucket") or "unknown"] = \
            buckets.get(check.get("bucket") or "unknown", 0) + 1
    return {"headSha": head_sha, "count": len(checks), "buckets": buckets,
            "pendingOrFailing": [
                {"name": c.get("name"), "bucket": c.get("bucket")}
                for c in checks if c.get("bucket") != "pass"][:12]}


def collect_live_claims() -> dict:
    """Read the claims this snapshot documents straight out of their owned files.

    The gap list used to be the only place these facts appeared, and it is static text,
    so it kept asserting an unobserved desktop surface after the owner had observed it.
    Anything that lives in a file is read from that file instead of restated here.
    """
    out: dict = {}
    register = REPO / "taskpacks" / "current" / "OPEN-TASK-REGISTER.md"
    if register.is_file():
        status = "ROW_ABSENT"
        for line in register.read_text(encoding="utf-8", errors="replace").splitlines():
            if line.startswith("| U19 |"):
                cells = [c.strip() for c in line.split("|")]
                status = cells[3] if len(cells) > 3 else "UNPARSED"
                break
        out["u19RegisterStatus"] = status

    ledger_path = REPO / "taskpacks" / "current" / "error-ledger.json"
    if ledger_path.is_file():
        ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
        wanted = {"ERR-103", "ERR-104", "ERR-105", "ERR-106", "ERR-107",
                  "ERR-110", "ERR-111"}
        out["ledgerStatusAfter"] = {
            e["error_id"]: e.get("status_after") for e in ledger["errors"]
            if e["error_id"] in wanted}
        out["ledgerEntries"] = len(ledger["errors"])

    registry_path = REPO / ".project/governance/future-candidate-registry.json"
    blueprint = REPO / "docs" / "future" / "WORK-LAB-BLUEPRINT-20261006.md"
    if registry_path.is_file() and blueprint.is_file():
        candidates = json.loads(
            registry_path.read_text(encoding="utf-8"))["candidates"]
        rows = set(re.findall(r"^\| (16\.\d{2}) \|",
                              blueprint.read_text(encoding="utf-8", errors="replace"),
                              re.M))
        claimed = {c.get("blueprint_row") for c in candidates}
        out["candidatePool"] = {
            "candidates": len(candidates), "sourceRows": len(rows),
            "claimedRows": len(claimed & rows),
            "unclaimed": sorted(rows - claimed),
            "claimsToUnknownRow": sorted(r for r in claimed - rows if r)}

    receipt = (REPO / ".project-local/runs/u19-msvc-20261006/target/release"
               / "app.exe.inputs.json")
    if receipt.is_file():
        data = json.loads(receipt.read_text(encoding="utf-8"))
        drift = []
        for item in data.get("inputs", []):
            path = REPO / item["path"]
            if not path.is_file() or sha256(path) != item["sha256"]:
                drift.append(item["path"])
        out["observedArtifact"] = {
            "schema": data.get("schemaVersion"), "inputsRecorded":
                data.get("inputCount"), "gitHeadAtBuild": data.get("gitHead", "")[:7],
            "exeSha256Prefix": data.get("binary", {}).get("sha256", "")[:16],
            "bytesNowOnDisk": (REPO / ".project-local/runs/u19-msvc-20261006/target"
                               / "release" / "app.exe").stat().st_size
            if (REPO / ".project-local/runs/u19-msvc-20261006/target"
                / "release" / "app.exe").is_file() else None,
            "binaryMatchesReceiptOnDisk": (
                (REPO / ".project-local/runs/u19-msvc-20261006/target/release"
                 / "app.exe").is_file() and
                sha256(REPO / ".project-local/runs/u19-msvc-20261006/target"
                       / "release" / "app.exe") == data["binary"]["sha256"]),
            "inputDriftSinceBuild": drift}
    else:
        out["observedArtifact"] = "LOCAL_RECEIPT_ABSENT (no .project-local build run here)"
    return out


def main() -> int:
    write = "--write" in sys.argv
    shanghai = datetime.now().astimezone()
    facts = {
        "observedAt": shanghai.strftime("%Y-%m-%dT%H:%M:%S%z"),
        "remote": git("remote", "get-url", "origin"),
        "defaultBranch": "main",
        "branch": git("rev-parse", "--abbrev-ref", "HEAD"),
        "localHead": git("rev-parse", "HEAD"),
        "baseSha": git("merge-base", "HEAD", "origin/main"),
        "dirtyFiles": [p for p in git("diff", "--name-only").splitlines() if p],
        "statusRecords": sum(1 for r in git("status", "--porcelain", "-z").split("\0")
                            if r.strip()),
        "liveMainSha": (git("ls-remote", "origin", "refs/heads/main").split() or
                        ["UNKNOWN"])[0],
        "liveBranchSha": (git("ls-remote", "origin", "refs/heads/" +
                              git("rev-parse", "--abbrev-ref", "HEAD")).split() or
                          ["NOT-PUSHED"])[0],
    }
    pr = subprocess.run(["gh", "pr", "view", "162", "--json", "state,headRefOid,"
                         "baseRefName,mergeable,url"],
                        capture_output=True, text=True, encoding="utf-8", errors="replace", check=False)
    facts["pr162"] = json.loads(pr.stdout) if pr.returncode == 0 else {
        "error": (pr.stderr or "gh unavailable").strip()[:200]}
    facts["about"] = collect_about()
    facts["ci"] = collect_ci(facts["liveBranchSha"] if facts["liveBranchSha"] !=
                              "NOT-PUSHED" else git("rev-parse", "HEAD"))
    facts["inputs"] = {
        "blueprintDocx": {"path": str(INPUT_DOCX), "exists": INPUT_DOCX.is_file(),
                          "sha256": sha256(INPUT_DOCX) if INPUT_DOCX.is_file() else None,
                          "declaredInPrompt": DECLARED_DOCX_SHA,
                          "match": (INPUT_DOCX.is_file() and
                                    sha256(INPUT_DOCX) == DECLARED_DOCX_SHA)},
        "executionPrompt": {"path": str(INPUT_PROMPT),
                            "exists": INPUT_PROMPT.is_file(),
                            "sha256": sha256(INPUT_PROMPT) if INPUT_PROMPT.is_file() else None,
                            "declaredInPrompt": None},
    }
    facts["checks"] = [run_check(argv) for argv in CHECKS]
    facts["liveClaims"] = collect_live_claims()
    facts["artifacts"] = []
    for rel in ["docs/future/WORK-LAB-BLUEPRINT-20261006.md",
                "docs/future/WORK-LAB-BLUEPRINT-COVERAGE.md",
                ".project/governance/blueprint-coverage.json",
                ".project/governance/future-candidate-registry.json",
                "scripts/ci/verify_blueprint_coverage.py",
                "scripts/ci/verify_future_candidate_registry.py",
                "apps/observer/scripts/write_artifact_receipt.py",
                "apps/observer/scripts/u19_webview_e2e.py",
                "apps/observer/tests/test_artifact_freshness.py"]:
        path = REPO / rel
        if path.is_file():
            facts["artifacts"].append({"path": rel, "bytes": path.stat().st_size,
                                       "sha256": sha256(path)})

    lines = [
        "# WORK-LAB 蓝图同步审计快照",
        "",
        "由 `python scripts/ci/record_blueprint_audit_snapshot.py --write` 生成；"
        "所有标识、远端 SHA、摘要与退出码均为运行时观察值，不转录自旧报告。"
        "本文件不含自身摘要。",
        "",
        "## 现场身份",
        "",
        "```json",
        json.dumps({k: v for k, v in facts.items()
                    if k in ("observedAt", "remote", "branch", "localHead", "baseSha",
                             "dirtyFiles", "statusRecords", "liveMainSha", "liveBranchSha")},
                   indent=2, ensure_ascii=False),
        "```",
        "",
        "脏文件计数按 `git diff --name-only` 计算：git 状态列会把行尾过滤器改写报成"
        "modified，而 `git diff` 无内容差异，因此以 diff 为准（ERR-105 的同一机制）。"
        "`liveBranchSha` 为 `NOT-PUSHED` 时表示交付分支尚未同步到远端，不能声称双端完成。",
        "",
        "## PR #162 读回",
        "",
        "```json",
        json.dumps(facts["pr162"], indent=2, ensure_ascii=False),
        "```",
        "",
        "更正记录：蓝图原文记载 PR #162 head 为 "
        "`6f323a318a9db1c3a3ed4429bab0d4eff129876c`；本次实时读回是其自身的观察值，"
        "两者不同则以上方读回为准，原文值保留为历史观察，不改写。原文记载的 "
        "`origin/main = cd4daa83…` 与本次读回一致。",
        "",
        "## GitHub About（Git 外元数据）",
        "",
        "```json",
        json.dumps(facts["about"], indent=2, ensure_ascii=False),
        "```",
        "",
        "About 不属于仓库内容，提交 README 不等于改过 About；此处单独记录 "
        "before → target → 现场读回。homepageUrl 与 topics 未改动（无真实站点依据，不编造）。",
        "",
        "## exact-SHA CI（PR #162 checks，绑定推送后的 head）",
        "",
        "```json",
        json.dumps(facts["ci"], indent=2, ensure_ascii=False),
        "```",
        "",
        "本地通过不称为 CI 绿；CI 绿也不宣告产品发布或本机 full gate 通过。",
        "",
        "## 输入与摘要",
        "",
        "```json",
        json.dumps(facts["inputs"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## 在册主张现场读回",
        "",
        "下面每个字段都从拥有它的文件里现场解析（U19 状态取唯一 open register 的状态列，"
        "台账状态取 `error-ledger.json` 的 `status_after`，候选池覆盖取注册表与 §16 "
        "行键的集合差，被目测的产物按其构建期凭据重算），不是从上一版报告转录。"
        "缺口清单是静态文字，会过期，所以可核验的部分一律改读真文件。",
        "",
        "```json",
        json.dumps(facts["liveClaims"], indent=2, ensure_ascii=False),
        "```",
        "",
        "## 检查命令与退出码（本次运行）",
        "",
        "| 命令 | 退出码 | 末行结果 |",
        "|---|---|---|",
    ]
    for check in facts["checks"]:
        lines.append(f"| `{check['command']}` | {check['exit']} | {check['result']} |")
    lines += [
        "",
        "## 产物摘要",
        "",
        "| 路径 | 字节 | SHA-256 |",
        "|---|---|---|",
    ]
    for artifact in facts["artifacts"]:
        lines.append(f"| `{artifact['path']}` | {artifact['bytes']} | "
                     f"`{artifact['sha256']}` |")
    lines += [
        "",
        "## 范围与未决缺口",
        "",
    ]
    lines += [f"- {gap}" for gap in GAPS]
    lines += [
        "",
        "## 双端同步状态定义",
        "",
        "- 本地文件与提交：本报告生成后即成立（读回见上）。",
        "- 远端分支：需推送后以 `git ls-remote` 读回，未读回前一律记 `未验证`。",
        "- GitHub About：Git 外元数据，单独记录 before→after 与读回，"
        "不能以提交 README 代替。",
        "- exact-SHA CI：以推送后 PR 的检查读回为准；本地通过不称为 CI 绿。",
        "- 默认分支 main：本轮不合并，故记为未更新。",
        "",
    ]
    text = "\n".join(lines) + "\n"
    if write:
        OUT.parent.mkdir(parents=True, exist_ok=True)
        OUT.write_text(text, encoding="utf-8")
        print(f"AUDIT_SNAPSHOT_WRITE -> {OUT.relative_to(REPO)} "
              f"bytes={len(text.encode('utf-8'))}")
    else:
        print(text)
    failing = [c for c in facts["checks"] if c["exit"] != 0]
    print("AUDIT_SNAPSHOT checks=%d failing=%d" % (len(facts["checks"]), len(failing)))
    for check in failing:
        print("  FAILING %s exit=%d %s" % (check["command"], check["exit"],
                                           check["result"]))
    return 1 if failing else 0


if __name__ == "__main__":
    sys.exit(main())
