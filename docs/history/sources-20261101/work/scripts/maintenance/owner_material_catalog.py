"""Locate, read back and verify registered owner materials without scanning private stores.

The register preserves source aliases. ZIP member chains locate exact originals inside
lossless historical containers; they do not authorize executing the source documents.
"""
from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import hashlib
import html
import io
import json
import os
import subprocess
from pathlib import Path, PurePosixPath
import sys
from urllib.parse import quote
import zipfile

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "docs/history/owner-inputs"
REGISTER = BASE / "RECORD-ARCHIVE-REGISTER.json"
MEMBERS = BASE / "RECORD-ARCHIVE-MEMBERS.jsonl"


def load():
    data = json.loads(REGISTER.read_text(encoding="utf-8"))
    members = [json.loads(line) for line in MEMBERS.read_text(encoding="utf-8").splitlines()]
    return data, members


def inside(path: str) -> Path:
    candidate = ROOT / path
    if not candidate.resolve().is_relative_to(ROOT.resolve()):
        raise ValueError("Path escapes project: " + path)
    return candidate


def repository_bytes(path: str) -> bytes | None:
    """The bytes git holds for `path`, or None when it is not tracked.

    A Windows checkout of a text file is CRLF while the blob is LF, so hashing the
    working copy on Windows produces a digest that is true of no repository anywhere.
    The index is the repository's own answer and is identical on every platform.
    """
    try:
        completed = subprocess.run(
            ["git", "show", ":" + path],
            cwd=ROOT,
            capture_output=True,
            check=False,
        )
    except OSError:
        return None
    if completed.returncode != 0:
        return None
    body = completed.stdout
    # A file stored through git LFS is a POINTER in the index, not its content. Reading
    # the index there would hand back the pointer text and every zip member would look
    # corrupt, so those fall back to the working file, which holds the real bytes.
    if body.startswith(b"version https://git-lfs.github.com/spec/v1"):
        return None
    return body


def read_locator(path: str, chain: list[str], cache=None) -> bytes:
    if cache is not None and path in cache:
        body = cache[path]
    else:
        body = None
        if not chain:
            body = repository_bytes(path)
        if body is None:
            body = inside(path).read_bytes()
        if cache is not None:
            cache[path] = body
    for name in chain:
        with zipfile.ZipFile(io.BytesIO(body)) as archive:
            body = archive.read(name)
    return body


def digest(body):
    return hashlib.sha256(body).hexdigest()


def enumerate_archive(body, chain=()):
    if len(chain) >= 12:
        raise ValueError("Archive nesting limit")
    with zipfile.ZipFile(io.BytesIO(body)) as archive:
        seen = set()
        for member in archive.infolist():
            if member.is_dir():
                continue
            if member.filename in seen:
                raise ValueError("Ambiguous duplicate archive member: " + member.filename)
            seen.add(member.filename)
            data = archive.read(member)
            location = (*chain, member.filename)
            yield location, len(data), digest(data)
            if member.filename.lower().endswith(".zip"):
                yield from enumerate_archive(data, location)


def verify(data, members, source_root=None):
    errors = []
    cache = {}
    for item in data["records"]:
        try:
            body = read_locator(item["archivePath"], item.get("archiveMemberChain", []), cache)
            if len(body) != item["bytes"] or digest(body) != item["sha256"]:
                errors.append(item["id"] + ": archive bytes/hash mismatch")
            if source_root:
                source = source_root / item["sourceRelativePath"]
                if not source.resolve().is_relative_to(source_root.resolve()):
                    raise ValueError("Source outside authorized root")
                original = source.read_bytes()
                if item["sourceMember"]:
                    with zipfile.ZipFile(io.BytesIO(original)) as archive:
                        original = archive.read(item["sourceMember"])
                if len(original) != item["bytes"] or digest(original) != item["sha256"]:
                    errors.append(item["id"] + ": Record original changed/missing")
        except (OSError, ValueError, KeyError, zipfile.BadZipFile) as exc:
            errors.append(item["id"] + ": " + str(exc))
    groups = {}
    for member in members:
        key = tuple(member["memberChain"])
        expected = groups.setdefault(member["archivePath"], {})
        if key in expected:
            errors.append("Duplicate physical member locator: " + member["archivePath"])
        expected[key] = (member["bytes"], member["sha256"])
    for path, expected in groups.items():
        try:
            body = read_locator(path, [], cache)
            actual = {chain: (size, sha) for chain, size, sha in enumerate_archive(body)}
            if actual != expected:
                errors.append(path + f": member census drift (expected={len(expected)}, actual={len(actual)})")
        except (OSError, ValueError, zipfile.BadZipFile) as exc:
            errors.append(path + ": " + str(exc))
    for container in data.get("storageContainers", []):
        body = read_locator(container["archivePath"], [], cache)
        if digest(body) != container["sha256"] or len(body) != container["bytes"]:
            errors.append(container["id"] + ": container hash mismatch")
    census = json.loads((BASE / "RECORD-SOURCE-CENSUS.json").read_text(encoding="utf-8"))
    mixed = json.loads((BASE / "RECORD-MIXED-ARCHIVE-SCOPE.json").read_text(encoding="utf-8"))
    selected = {x["sourceMember"] for x in data["records"] if x["sourceRelativePath"] == mixed["sourceRelativePath"]}
    if selected != set(mixed["archivedMembers"]):
        errors.append("Mixed source selected members not fully registered")
    if len(selected) + len(mixed["excludedMembers"]) != mixed["totalFileMembers"]:
        errors.append("Mixed source member dispositions incomplete")
    registered = {x["sourceRelativePath"] for x in data["records"]}
    expected_sources = {x["sourceRelativePath"] for x in census["files"] if x["disposition"] != "EXCLUDED_FOREIGN"}
    if registered != expected_sources or census["unresolved"] != 0:
        errors.append("Source-file disposition / register coverage mismatch")
    if source_root:
        if digest((source_root / mixed["sourceRelativePath"]).read_bytes()) != mixed["sourceSha256"]:
            errors.append("Mixed original ZIP hash changed")
        # Metadata only for explicitly excluded trees; never read their bodies.
        actual_files = set()
        for path in source_root.rglob("*"):
            if path.is_symlink():
                errors.append("Source reparse requires review: " + path.relative_to(source_root).as_posix())
            elif path.is_file():
                actual_files.add(path.relative_to(source_root).as_posix())
        if actual_files != {x["sourceRelativePath"] for x in census["files"]}:
            errors.append("Record file inventory drift; reclassify new/missing materials")
    result = {
        "status": "PASS" if not errors else "FAIL",
        "registeredMaterials": len(data["records"]),
        "indexedArchiveMembersIncludingNested": len(members),
        "sourceFilesInventoried": census["enumeratedFileCount"],
        "relatedSourceFiles": census["archivedSourceFileCount"],
        "excludedForeignFiles": census["excludedForeignFileCount"],
        "mixedRelatedMembers": len(selected),
        "unresolvedSourceFiles": census["unresolved"],
        "sourceReadback": "PASS" if source_root and not errors else ("FAIL" if source_root else "NOT_EXECUTED"),
        "sourceModified": False,
        "productImplementation": "NOT_EXECUTED",
        "errors": errors,
    }
    return result


def render_index(data, members):
    keys = ["id", "sourceRelativePath", "sourceMember", "archivePath", "archiveMemberChain", "storageKind", "contentId", "bytes", "sha256", "ownership", "category", "status", "classificationBasis"]
    with (BASE / "RECORD-ARCHIVE-REGISTER.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, keys, extrasaction="ignore")
        writer.writeheader()
        for item in data["records"]:
            writer.writerow({**item, "archiveMemberChain": " ! ".join(item.get("archiveMemberChain", []))})
    keys = ["materialId", "materialIds", "archivePath", "memberChain", "contentId", "bytes", "sha256", "crc32", "status"]
    with (BASE / "RECORD-ARCHIVE-MEMBERS.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, keys)
        writer.writeheader()
        for item in members:
            writer.writerow({**item, "memberChain": " ! ".join(item["memberChain"]), "materialIds": " | ".join(item.get("materialIds", []))})
    count = len(data["records"])
    intro = """# WORK-LAB 资料总入口

查文件先从本页进入；按原文件名、日期、任务编号或包内成员检索，不再依赖 Record 外部路径。
这是资料导航和历史来源登记，不是新的任务权威。当前执行仍读取 WORK-LAB-AUTHORITY.md 与唯一 CURRENT。

## 当前任务与历史摘要

- [当前权威收敛任务包](../../../taskpacks/current/WORK-LAB-AUTHORITY-CONVERGENCE-TASKPACK-20261019.md)
- [当前路线图](../../current/authority-convergence-20261019/ROADMAP.md)
- [权威收敛报告](../../current/authority-convergence-20261019/AUTHORITY-CONVERGENCE-20261019.md)
- [UI 历史交接（FROZEN_20261019，2026-10-19 汇总归档）](../archive/HANDOFFS-AND-PROMPTS-20261019-MANIFEST.json)：成员 NEXT-AGENT-PROMPT.md
- [历史关键信息与沿用边界](HISTORICAL-KEY-POINTS.md)
- [本次归档、去重、压缩及验证记录](RECORD-ARCHIVE-REPORT.md)
- [可搜索文件目录](CATALOG.html)：可按文件名、包内路径、材料分类、原位置筛选。
- [完整文件登记 JSON](RECORD-ARCHIVE-REGISTER.json) / [CSV](RECORD-ARCHIVE-REGISTER.csv)
- [完整包内成员登记 JSONL](RECORD-ARCHIVE-MEMBERS.jsonl) / [CSV](RECORD-ARCHIVE-MEMBERS.csv)
- [全部 Record 文件归属盘点](RECORD-SOURCE-CENSUS.json)：包括明确排除的其他项目材料。
- [去重登记](RECORD-DEDUPLICATION.json) / [合并压缩登记](RECORD-CONSOLIDATION.json) / [混合包范围](RECORD-MIXED-ARCHIVE-SCOPE.json)

## 如何定位与提取

在项目根用已有 Python 执行 `scripts/maintenance/owner_material_catalog.py find "关键词"`。
`find` 同时查原文件名、分类、别名和包内成员，返回资料 ID、仓内路径与完整嵌套成员链。`--limit 0` 显示全部命中。
`extract WL-REC-0001` 将指定资料提取到 `.project-local/artifacts/material-lookup/`，校验摘要，不执行材料中的命令。
`verify` 校验仓内全部文件和压缩包成员；显式加 `--source-root "D:/All projects/Record"` 才核对源目录。
当前机器 Python 入口为 `.project-local/toolchains/wl-py311/Scripts/python.exe`；其他机器动态发现现有解释器。

登记规则：相同 SHA-256/大小归为同一内容身份；所有源文件名、来源及成员路径保留为别名。
同名不同内容保留不同版本；历史报告的 PASS、SHA、安装状态只代表原报告时间，不能用作当前事实。
历史资料合并为无损 ZIP；现行输入不改字节。不可变 ZIP 内部的重复成员只在目录中分组，不改写原包。

后续增量材料先核对已有摘要，再追加源别名/版本和包内成员登记，运行 `build-index` 与 `verify`。
不要另建第二个资料目录或任务账本；没有找到文件时报告具体 ID/路径/摘要缺口，不用新摘要冒充原件。

## 原文件及别名目录

"""
    lines = [intro, f"本次登记 **{count} 条资料**及 **{len(members)} 条包内成员**。下表链接指向规范存储；压缩资料的成员链在 JSON/CSV 和可搜索目录中完整列出。\n"]
    lines += ["\n## 项目派生归档容器\n", "以下为既有资料整理或用户授权的项目内交接归档；不冒充 Record 源文件，不改变 Record 来源盘点。成员可通过 find 查询。\n"]
    for container in data.get("storageContainers", []):
        relative = Path(os.path.relpath(inside(container["archivePath"]), BASE)).as_posix()
        lines.append(f"- {container['id']}：[{Path(container['archivePath']).name}](<{relative}>)；{container['status']}。")
    for group in ("TASK_HANDOFF", "AUDIT", "BLUEPRINT_RESEARCH", "UI_REFERENCE", "UI_ASSET"):
        lines += [f"\n### {group}\n", "| ID | 原位置 / 包内位置 | 身份 | 规范存储 |", "| --- | --- | --- | --- |"]
        for item in data["records"]:
            if item["category"] != group:
                continue
            location = item["sourceRelativePath"] + (" ! " + item["sourceMember"] if item["sourceMember"] else "")
            relative = Path(os.path.relpath(inside(item["archivePath"]), BASE)).as_posix()
            state = "当前输入" if item["status"].startswith("CURRENT") else ("共享历史" if item["ownership"] == "SHARED_CONTEXT" else "项目历史")
            label = "压缩包成员" if item.get("archiveMemberChain") else "原件"
            lines.append(f"| {item['id']} | {location.replace('|', '/')} | {state} | [{label}](<{relative}>) |")
    (BASE / "INDEX.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    # The local catalog embeds metadata only; no source body, external service or dependency.
    all_rows = []
    for item in data["records"]:
        all_rows.append({"id": item["id"], "source": item["sourceRelativePath"] + (" ! " + item["sourceMember"] if item["sourceMember"] else ""), "category": item["category"], "status": item["status"], "path": item["archivePath"], "chain": item.get("archiveMemberChain", []), "sha": item["sha256"], "bytes": item["bytes"]})
    for member in members:
        all_rows.append({"id": member["materialId"], "source": " ! ".join(member["memberChain"]), "category": "ARCHIVE_MEMBER", "status": member["status"], "path": member["archivePath"], "chain": member["memberChain"], "sha": member["sha256"], "bytes": member["bytes"]})
    for item in all_rows:
        item["href"] = quote(Path(os.path.relpath(inside(item["path"]), BASE)).as_posix(), safe="/")
    payload = json.dumps(all_rows, ensure_ascii=False).replace("<", "\\u003c")
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><title>WORK-LAB 资料目录</title>
<style>body{font:15px system-ui;margin:28px;line-height:1.6;color:#182333}input{width:75%;padding:12px;font:inherit}table{border-collapse:collapse;width:100%;margin-top:18px}td,th{text-align:left;border-bottom:1px solid #ddd;padding:9px;vertical-align:top}small{display:block;color:#596677;overflow-wrap:anywhere}a{color:#125fb1}.chain{max-width:650px}</style>
<h1>WORK-LAB 资料目录</h1><p>原文件名、别名、日期、包内成员均可查。历史资料只作来源；当前任务见 INDEX.md。</p>
<input id="q" aria-label="搜索资料" placeholder="搜索：首页、TASKPACK、MASTER_ATLAS、Logo、20261009…"><label><input id="unique" type="checkbox" checked style="width:auto">相同内容只显示一条</label><p id="count"></p><table><thead><tr><th>资料 / 来源</th><th>规范存储和成员链</th><th>分类 / 内容身份</th></tr></thead><tbody id="rows"></tbody></table>
<script>const data=PAYLOAD;const q=document.querySelector('#q'),unique=document.querySelector('#unique'),rows=document.querySelector('#rows');
function render(){const terms=q.value.toLowerCase().split(/\\s+/).filter(Boolean);let hits=data.filter(r=>terms.every(t=>JSON.stringify(r).toLowerCase().includes(t)));const total=hits.length;if(unique.checked){const seen=new Set;hits=hits.filter(r=>{if(seen.has(r.sha))return false;seen.add(r.sha);return true})}document.querySelector('#count').textContent=`命中 ${total} 个来源/位置，显示 ${hits.length} 个条目；全部登记 ${data.length} 条。`;rows.replaceChildren();for(const r of hits){const tr=document.createElement('tr');const a=document.createElement('td');a.textContent=r.id+' · '+r.source;const b=document.createElement('td');b.className='chain';const link=document.createElement('a');link.href=r.href;link.textContent=r.path;b.append(link);const sub=document.createElement('small');sub.textContent=r.chain.length?'成员链：'+r.chain.join(' ! '):'直接文件';b.append(sub);const c=document.createElement('td');c.textContent=r.category;const small=document.createElement('small');small.textContent=r.status+' · '+r.bytes+' B · SHA-256 '+r.sha;c.append(small);tr.append(a,b,c);rows.append(tr)}}q.addEventListener('input',render);unique.addEventListener('change',render);render();</script></html>'''.replace("PAYLOAD", payload)
    (BASE / "CATALOG.html").write_text(page + "\n", encoding="utf-8")
    return {"status": "PASS", "index": "docs/history/owner-inputs/INDEX.md", "catalogRows": len(all_rows)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    find = commands.add_parser("find")
    find.add_argument("keyword")
    find.add_argument("--limit", type=int, default=25, help="0 means all")
    check = commands.add_parser("verify")
    check.add_argument("--source-root", type=Path)
    check.add_argument("--report", help="optional repo-local JSON report")
    commands.add_parser("build-index")
    extract = commands.add_parser("extract")
    extract.add_argument("id")
    extract.add_argument("--dest", help="optional exact file under .project-local/artifacts")
    args = parser.parse_args()
    data, members = load()
    if args.command == "find":
        terms = args.keyword.casefold().split()
        records = [{**r, "absoluteArchivePath": str(inside(r["archivePath"]))} for r in data["records"] if all(t in json.dumps(r, ensure_ascii=False).casefold() for t in terms)]
        archive_members = [r for r in members if all(t in json.dumps(r, ensure_ascii=False).casefold() for t in terms)]
        result = {"materialMatches": len(records), "memberMatches": len(archive_members), "records": records[:args.limit or None], "members": archive_members[:args.limit or None]}
    elif args.command == "build-index":
        result = render_index(data, members)
    elif args.command == "verify":
        if args.source_root and args.source_root.resolve() != Path(data["sourceRoot"]).resolve():
            parser.error("Only the explicitly registered Record source root is allowed")
        result = verify(data, members, args.source_root)
        if args.report:
            target = inside(args.report)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    else:
        item = next((r for r in data["records"] if r["id"] == args.id), None)
        if item is None:
            parser.error("Unknown material ID")
        name = PurePosixPath(item["sourceMember"] or item["sourceRelativePath"]).name
        target = inside(args.dest or f".project-local/artifacts/material-lookup/{item['id']}/{name}")
        if not target.resolve().is_relative_to((ROOT / ".project-local/artifacts").resolve()):
            parser.error("Extraction must stay under .project-local/artifacts")
        body = read_locator(item["archivePath"], item.get("archiveMemberChain", []))
        if digest(body) != item["sha256"] or len(body) != item["bytes"]:
            parser.error("Canonical content hash mismatch; extraction refused")
        if target.exists() and target.read_bytes() != body:
            parser.error("Existing destination has different bytes; overwrite refused")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(body)
        ledger = ROOT / ".project-local/artifacts/spill-ledger.jsonl"
        with ledger.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({
                "at": datetime.now(timezone.utc).isoformat(),
                "actor": "owner_material_catalog",
                "action": "extract pinned owner material for local lookup",
                "outOfRoot": False,
                "target": target.relative_to(ROOT).as_posix(),
                "source": item["archivePath"],
                "trace": item["sha256"],
                "locate": item["id"],
                "clean": "one regenerable lookup copy under project artifacts",
                "migrate": "already within project boundary",
                "reversible": "canonical archive untouched; lookup copy may be regenerated",
                "memberChain": item.get("archiveMemberChain", []),
            }, ensure_ascii=False) + "\n")
        result = {"status": "PASS", "id": item["id"], "path": str(target), "bytes": len(body), "sha256": digest(body), "sourceExecuted": False}
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 1 if result.get("status") == "FAIL" else 0


if __name__ == "__main__":
    sys.exit(main())
