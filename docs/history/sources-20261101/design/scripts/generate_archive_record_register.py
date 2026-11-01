#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Regenerate the 2026-10-19 archive-wave register in docs/RECORD-ARCHIVE-INDEX.md.

The register is the answer to "where did the old material go and how do I get it back", so its
numbers must come from the repository, not from a chat log. Every digest here is read from
`git cat-file blob HEAD:<path>` because `core.autocrlf=true` on this machine means the worktree bytes
of a tracked file are not its committed bytes — hashing a local file would register a value that no
fresh clone reproduces. Counts cited inside the section are cross-checked against the records
themselves before anything is written, so a record that disagrees with its own summary aborts the run.

Idempotent: the section is identified by its heading and rewritten whole, so re-running after the
next commit refreshes the register instead of stacking a second copy.

    python scripts/generate_archive_record_register.py
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from collections import OrderedDict
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "docs" / "RECORD-ARCHIVE-INDEX.md"
HEADING = "## 2026-10-19 新增：归档与移除波次的五份记录（owner 2026-10-19 指令）"

ARCHIVE = "docs/history/archive-2026-10-19"
PATHS = [
    f"{ARCHIVE}/MANIFEST.json",
    f"{ARCHIVE}/REMOVALS.json",
    f"{ARCHIVE}/HANDOFF-PROMPT-DIGEST.json",
    f"{ARCHIVE}/AGGREGATED-RECORD-2026-10-19.md",
    "docs/audits/DESIGN-LAB-ARCHIVE-AND-REMOVAL-2026-10-19.md",
]
ALIASES = {
    "MANIFEST.json": "档案清单 / 移动清单 / move manifest",
    "REMOVALS.json": "移除清单 / 删除登记 / removal record",
    "HANDOFF-PROMPT-DIGEST.json": "交接与提示词汇总登记 / digest",
    "AGGREGATED-RECORD-2026-10-19.md": "归档汇总与追溯记录 / 可读汇总",
    "DESIGN-LAB-ARCHIVE-AND-REMOVAL-2026-10-19.md": "波次交付报告 / 审计正文",
}
TRACKED_TOOLS = {
    "register": "scripts/generate_archive_record_register.py",
    "verify": "scripts/verify_archive_record_register.py",
    "resolver": "scripts/archive_records.py",
}


def git(*args: str) -> bytes:
    done = subprocess.run(["git", "-C", str(REPO), *args], capture_output=True)
    if done.returncode != 0:
        raise SystemExit(f"git {' '.join(args)} failed: {done.stderr.decode('utf-8', 'replace').strip()}")
    return done.stdout


def blob_of(rel: str) -> dict:
    data = git("cat-file", "blob", f"HEAD:{rel}")
    return {
        "path": rel,
        "sha1": git("rev-parse", f"HEAD:{rel}").decode().strip(),
        "bytes": len(data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "data": data,
        "worktree": (REPO / rel).stat().st_size if (REPO / rel).exists() else None,
    }


def num(value: int) -> str:
    return f"{value:,}"


def headings(text: str) -> int:
    return text.count("\n## ") + (1 if text.startswith("## ") else 0)


def _report_sections(text: str) -> str:
    """Name the report's own `##` sections instead of hand-listing them.

    The register used to hard-code "§1 … / §6 六个缺陷 + §6.5 第七个 / §7 …", which went stale the moment
    the report gained a section — twice this pass. Reading the titles out of the committed blob means the
    register can only ever describe the report as it is.
    """
    titles = re.findall(r"^## (.+)$", text, re.M)
    if not titles:
        raise SystemExit("delivery report has no '##' sections — cannot register its shape")
    return f"{len(titles)} 个 `##` 小节，标题逐条读自报告正文：" + " / ".join(titles)


def build() -> tuple[list[dict], str]:
    rec = OrderedDict((p, blob_of(p)) for p in PATHS)
    move = json.loads(rec[PATHS[0]]["data"].decode("utf-8"))
    rem = json.loads(rec[PATHS[1]]["data"].decode("utf-8"))
    dig = json.loads(rec[PATHS[2]]["data"].decode("utf-8"))
    agg = rec[PATHS[3]]["data"].decode("utf-8")
    rep = rec[PATHS[4]]["data"].decode("utf-8")

    # A register may only cite numbers the records themselves agree on.
    move_rows = sum(len(g["files"]) for g in move["groups"])
    move_dests = sum(d["files"] for d in move["destinations"])
    if not move_rows == move_dests == move["summary"]["files"]:
        raise SystemExit(f"move manifest disagrees with itself: rows={move_rows} "
                         f"destinations={move_dests} summary={move['summary']['files']}")
    if len(rem["entries"]) != rem["summary"]["files"]:
        raise SystemExit("removal entries do not match the removal summary count")
    if dig["counts"]["deleted"] != rem["summary"]["files"]:
        raise SystemExit("digest deleted tally differs from the removal list")
    if dig["counts"]["deletedBytes"] != rem["summary"]["bytes"]:
        raise SystemExit("digest deleted bytes differ from the removal list")
    if dig["counts"]["entries"] != len(dig["dispositions"]):
        raise SystemExit("digest entry count differs from its dispositions")
    roots: dict[str, int] = {}
    for entry in rem["entries"]:
        top = "/".join(str(entry["path"]).split("/")[:2]) + "/**"
        roots[top] = roots.get(top, 0) + 1
    if sum(roots.values()) != rem["summary"]["files"]:
        raise SystemExit("removal rows do not partition into their declared roots")
    if any(len(str(e["sha256"])) != 71 or not str(e["sha256"]).startswith("sha256:")
           for e in rem["entries"]):
        raise SystemExit("a removal row carries a sha256 that is not a full 64-hex digest")
    if len({e["restoreAt"] for e in rem["entries"]}) != 1:
        raise SystemExit("removal rows disagree on their recovery anchor")
    for rel, item in rec.items():
        if "\ufffd" in item["data"].decode("utf-8"):
            raise SystemExit(f"{rel} contains a replacement character")

    divergent = []
    for p in PATHS:
        item = rec[p]
        if item["worktree"] is None or item["worktree"] == item["bytes"]:
            continue
        if (REPO / p).read_bytes().replace(b"\r\n", b"\n") == item["data"]:
            divergent.append((p, item["worktree"] - item["bytes"]))

    rows = [
        dict(idx=str(i + 1), rec=rec[p], alias=ALIASES[p.rsplit("/", 1)[1]], version=version, what=what)
        for i, (p, version, what) in enumerate([
            (PATHS[0], move["schemaVersion"],
             f"40 组 / {num(move['summary']['files'])} 文件 / {num(move['summary']['bytes'])} B 的整目录移动台账；"
             f"组行与目的地两个方向都求和回 `{num(move_rows)}`；"
             f"`byteIdentityVerified={move['summary']['byteIdentityVerified']}`、"
             f"`removedSinceThisPass={move['summary']['removedSinceThisPass']}`、"
             f"`bytesRewritten={move['summary']['bytesRewritten']}`"),
            (PATHS[1], rem["schemaVersion"],
             f"{num(rem['summary']['files'])} 份旧交接/提示词原件的移除登记（{num(rem['summary']['bytes'])} B），跨 "
             + " + ".join(f"`{k}` {v} 份" for k, v in sorted(roots.items())) + "；"
             "逐条含 `blobSha1`/`sha256`/`crc32`/`bytes`/`restoreAt`/`recoverWith`，"
             f"统一锚点 `restoreAt={rem['restoreAt']}`，`keptAuditInputs={rem['summary']['keptAuditInputs']}`"
             "（owner 提供的 R3 审计输入不删）"),
            (PATHS[2], dig["schemaVersion"],
             f"读取于 `readAtCommit={dig['readAtCommit'][:8]}`、对 `verifiedAgainstHead={dig['verifiedAgainstHead'][:8]}` 复核；"
             f"{dig['counts']['entries']} 条目 → 删除 {dig['counts']['deleted']} / 保留 {dig['counts']['kept']}，"
             f"合计 {num(dig['counts']['totalBytes'])} B；`blobIdsReDerived={dig['blobIdsReDerived']}`"),
            (PATHS[3], "无 schemaVersion（Markdown 汇总件）",
             f"{headings(agg)} 个 `##` 小节；承载被删文档的标题/自述/结论/取代关系与只有它记载的事实，"
             "使第 2 项的删除是退役而不是丢失"),
            (PATHS[4], "无 schemaVersion（交付报告）",
             _report_sections(rep)),
        ])
    ]

    tip = git("rev-parse", "HEAD").decode().strip()
    source_tip = git("log", "-1", "--format=%H", "--", PATHS[4]).decode().strip()

    lines = [
        HEADING,
        "",
        "本节登记 2026-10-19 归档波次产出的**五份记录**本身。波次过程与逐条缺陷不在这里重述，读第 5 项那份交付报告；",
        f"本节由 `{TRACKED_TOOLS['register']}` 生成、由 `{TRACKED_TOOLS['verify']}` 反向核对"
        "（两脚本均在 Git 里，克隆后可重跑）。",
        "",
        "**哈希一律取自提交对象**（`git cat-file blob HEAD:<路径>` 的字节做 SHA-256）。"
        f"本机 `core.autocrlf=true`，工作树里有 {len(divergent)} 份被还原成 CRLF"
        + ("（" + "、".join(f"`{Path(p).name}` 多 {num(d)} B" for p, d in divergent) + "）" if divergent else "")
        + "，所以直接对本地文件算出的不是下表的值；这不是漂移，别去『修』它。",
        "",
        "| # | canonical 路径 | 别名 | 版本 / 定态 | blob SHA-1 | 体量 | blob SHA-256 | 内容与计数 |",
        "|---|---|---|---|---|---|---|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['idx']} | `{row['rec']['path']}` | {row['alias']} | {row['version']} | "
            f"`{row['rec']['sha1'][:12]}` | {num(row['rec']['bytes'])} B | `{row['rec']['sha256'][:16]}…` | "
            f"{row['what']} |"
        )
    lines += ["", "完整 SHA-256（逐条，便于跨机器核对）：", ""]
    for row in rows:
        lines.append(f"- {row['idx']}. `{row['rec']['path']}` → `{row['rec']['sha256']}`")
    lines += [
        "",
        "**五份记录是怎么产出的**：",
        "",
        f"- 第 1 项 `{ARCHIVE}/MANIFEST.json`：波次脚本逐行重读 git index，比对移动前记录的 blob SHA-1 与字节数；",
        "- 第 2 项 `REMOVALS.json`：每条先用 `git show <restoreAt>:<path>` 读回原文，再算 sha256/crc32，读不到即中止；",
        "- 第 3、4 项 `HANDOFF-PROMPT-DIGEST.json` 与 `AGGREGATED-RECORD-2026-10-19.md`：由汇总脚本产出，"
        "blob 标识全部从 git 重新导出（该步实测纠正过 1 处 39 位的手抄截断）；",
        "- 第 5 项交付报告：面向 `docs/taskpacks/20261019-direction/source/ACCEPTANCE.md` 的「必交付」与"
        "「最终报告格式」两份清单写成，§0 结论取自同轮 CI 与闸门实测读数。",
        "",
        f"> **这三类产出脚本不在 Git 里**：它们是一次性波次工装，留在 `.project-local/task-runtime/`"
        "（该根被 Git 忽略，且第 1、2 项的脚本会改写 `docs/history/**` 冻结件，不宜作为常备面）。"
        "本节的数字**不需要**它们即可复现：哈希与体量按上面的 `git cat-file` 一条命令就能重算，"
        f"计数直接从各记录自己的 `summary`/`counts` 字段读——这条复现路由 `{TRACKED_TOOLS['verify']}` 执行，"
        "它只读、不改任何记录。",
        "",
        "**取代与被取代关系**：",
        "",
        "- 这五份记录**不取代** `docs/history/record-archive-2026-10-09/ARCHIVE-MANIFEST.json`，也不并入其 "
        "101/180/111 普查读数；那批 Record 导入的清单仍是它自己那一份。",
        "- 第 1 项答复「路径去了哪里」，第 2 项答复「原件为何不在、怎么取回」。读侧消费者已接上：`"
        + TRACKED_TOOLS["resolver"] + "`、`src/design_lab/governance/reporting.py`、`scripts/record_import_verify.py`、"
        "`design-lab/scripts/verify_evidence_artifact_presence.py`、"
        "`design-lab/scripts/verify_task_document_states.py`。旧路径因此不能再被索引为可达资料，但按 blob 取回始终可证。",
        "- 第 2 项引用的 `restoreAt` 是**读取锚点**，不是当前 HEAD；当前 SHA 一律 `git rev-parse HEAD` 自读。",
        "",
        "**一致性实测**（由生成脚本当场校验，任一不等即中止）：",
        "",
        f"- 移动：组行 {num(move_rows)} ＝ 目的地求和 {num(move_dests)} ＝ `summary.files="
        f"{num(move['summary']['files'])}`；",
        f"- 移除：`REMOVALS.summary.files={rem['summary']['files']}` ＝ `entries` 长度 ＝ 摘要 `counts.deleted="
        f"{dig['counts']['deleted']}`，按根拆为 " + " + ".join(f"{v}（`{k}`）" for k, v in sorted(roots.items())) + "；",
        f"- 字节：`REMOVALS.summary.bytes={num(rem['summary']['bytes'])}` ＝ 摘要 `counts.deletedBytes="
        f"{num(dig['counts']['deletedBytes'])}`；",
        f"- {rem['summary']['files']} 条 `sha256` 全是 `sha256:` + 64 位十六进制，`restoreAt` 同值一条；",
        "- 五份记录均可 UTF-8 解码且不含 `U+FFFD`（中文正文若被写成乱码字节，这里会先炸）。",
        "",
        f"**本节测于哪个提交**：五个 blob 在 `{tip[:8]}` 上逐条重算；交付报告最后一次被改写于 "
        f"`{source_tip[:8]}`。本节所在提交装不下自己的哈希，所以两个读数都写出来。"
        "五个值指向的都是不可变提交对象，本节不会随时间失效；真正会变的情形只有「记录本身被改写」。"
        "四份在 `docs/history/archive-2026-10-19/**`，属 `docs/current/HISTORY-FREEZE-RULES.md` 认定的冻结家族，"
        "按规则不该再编辑；第五份是 dated 交付报告，若以后确实要补它，就重跑 "
        f"`python {TRACKED_TOOLS['register']}` 让本节跟着更新，别留下和仓库不一致的哈希。",
        "",
        "**定态**：五份都是**波次的登记件**，不是能力索引、不是派工入口，也不改变 `currentExecution` 34 项的 "
        "`FROZEN_DEFERRED`。真值仍读 `design-lab/config/capability-evidence-index.json`、"
        "`design-lab/config/capability-status.json` 与 `docs/current/NEXT-AGENT-PROMPT.md`。",
        "",
    ]
    return rows, "\n".join(lines) + "\n"


def main() -> int:
    rows, block = build()
    raw = INDEX.read_bytes()
    if b"\r" in raw:
        raise SystemExit("docs/RECORD-ARCHIVE-INDEX.md must be LF on disk before rewriting")
    text = raw.decode("utf-8")
    if HEADING in text:
        head = text.split(HEADING, 1)[0]
    else:
        head = text.rstrip("\n") + "\n\n"
    updated = (head + block).encode("utf-8")
    INDEX.write_bytes(updated)

    back = INDEX.read_bytes()
    if b"\r" in back:
        raise SystemExit("rewritten index contains CR — newline shape changed")
    back_text = back.decode("utf-8")
    if back_text.count(HEADING) != 1:
        raise SystemExit("register heading is not exactly one after the rewrite")
    if head and not back_text.startswith(head[: min(len(head), 200)]):
        raise SystemExit("bytes before the register section were not preserved")
    print(f"records={len(rows)} bytes {len(raw)}->{len(back)} head_preserved_bytes={len(head.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
