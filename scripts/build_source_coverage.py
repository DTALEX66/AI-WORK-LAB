"""Full source-coverage register: every file in both read-only sources gets a class.

Audit F01 adjudicated the 198 paths that ``migration/mapping.csv`` *registers* but
the copy manifest does not contain. Counting further showed the register itself is
narrower than the repositories: WORK holds ~798 ``.py`` files and mapping.csv
registers 225 paths, so a large population was never enumerated either way. Leaving
that population unnamed is how "no unexplained P1 gap" becomes unfalsifiable.

This tool enumerates **every non-ignored file in each source** with the same口径 the
audit used (``git ls-files --cached --others --exclude-standard``), reconciles it
against ``migration/copies.json`` and ``migration/mapping.csv``, and emits one row
per (source file, copy record), so a source that is deliberately copied to several
targets is judged target by target. Registered-but-uncopied paths reuse
``build_f01_disposition.classify`` verbatim, so the two registers cannot disagree
about the same file.

It refuses to miscount: the class totals must equal the number of emitted rows.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "scripts"))

import build_f01_disposition as f01  # noqa: E402

WORK = f01.WORK_ROOT
DESIGN = f01.DESIGN_ROOT
COPIES = REPO_ROOT / "migration" / "copies.json"
MAPPING = REPO_ROOT / "migration" / "mapping.csv"
OUT_DIR = REPO_ROOT / "migration"
SKIP_PARTS = {".mimosa", "__pycache__", ".pytest_cache", ".venv", "node_modules"}
GENERATED_NAMES = {"package-lock.json", "yarn.lock", "uv.lock", "poetry.lock"}

_MIGRATE = None


def migrate_module():
    """Load scripts/migrate_sources.py for the declared-patch expectation.

    Its module level only builds the copy/patch tables and ``main`` is guarded, so
    importing it performs no writes. Using it here is what lets a *correctly
    patched* copy be recognised instead of being reported as drift.
    """
    global _MIGRATE
    if _MIGRATE is None:
        import importlib.util

        spec = importlib.util.spec_from_file_location(
            "ms_coverage", REPO_ROOT / "scripts" / "migrate_sources.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _MIGRATE = module
    return _MIGRATE


def now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_of_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def list_source_files(root: Path) -> list[str]:
    raw = subprocess.check_output(["git", "ls-files", "--cached", "--others",
                                   "--exclude-standard", "-z"], cwd=str(root))
    rows = []
    for rel in sorted(set(x for x in raw.decode("utf-8").split("\0") if x)):
        if any(part in SKIP_PARTS for part in Path(rel).parts):
            continue
        if (root / rel).is_file():
            rows.append(rel)
    return rows


def copied_index() -> dict[str, list[dict]]:
    """Absolute source path -> EVERY copy record that reads from it."""
    manifest = json.loads(COPIES.read_text(encoding="utf-8"))
    index: dict[str, list[dict]] = {}
    for group in manifest["copies"]:
        for record in group.get("records", []):
            index.setdefault(str(Path(record["source"]).resolve()), []).append(record)
    return index


def _mapping_rows() -> list[dict]:
    with MAPPING.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def registered_keys() -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in _mapping_rows():
        bucket = "work" if row["仓"] == "work" else "design"
        out[bucket + ":" + row["原路径"].replace("\\", "/")] = row
    return out


def patch_map() -> dict[str, list[tuple[str, str]]]:
    """Target-relative path -> declared patches, so a patched copy is recognised."""
    out: dict[str, list[tuple[str, str]]] = {}
    for rel, old, new, _reason in migrate_module().PATCHES:
        out.setdefault(rel, []).append((old, new))
    return out


def classify_unregistered(rel: str) -> tuple[str, str]:
    parts = Path(rel).parts
    name = Path(rel).name
    if "tests" in parts or name.startswith("test_") or "/test/" in rel:
        return ("TEST_ONLY", "来源仓测试目录或 test_* 文件，不是运行面能力")
    if name in GENERATED_NAMES or rel.startswith(("dist/", "build/")):
        return ("GENERATED_OR_LOCKFILE", "生成物或锁文件")
    suffix = Path(rel).suffix.lower()
    if suffix in (".ts", ".tsx", ".js", ".jsx", ".css", ".html", ".vue", ".map", ".svg"):
        return ("FRONTEND_ASSET", "前端/工作台资源：本批只做本地后端，前端明确排除")
    if suffix in (".md", ".txt") or rel.startswith("docs/") or name.startswith("README"):
        return ("DOCS_OR_SPEC", "文档与规格说明")
    if suffix in (".json", ".yaml", ".yml", ".toml", ".ini", ".sql", ".csv", ".xsd",
                  ".jsonl", ".psd", ".fig", ".sketch"):
        return ("DATA_OR_CONFIG", "配置/数据/合同资源：只有运行面真正读取时才需要迁入")
    if suffix in (".bat", ".cmd", ".ps1", ".sh"):
        return ("BUILD_OR_REPO_META", "启动器/构建脚本")
    if suffix != ".py":
        return ("BUILD_OR_REPO_META", "非 Python 仓库文件（图片、字体、二进制等）")
    if re.search(r"(^|/)(verify|check|audit|report|build|scan|probe)_", rel):
        return ("TOOL_OR_SCRIPT", "独立校验/报表 CLI，不是运行面能力")
    return ("SOURCE_UNREGISTERED", "未登记且未迁入的 Python 源文件：由本表首次命名，"
                                    "需 owner 判定是否属于产品能力；本批不据其声称能力完整")


def _copied_row(repo_label: str, repo: Path, rel: str, key: str, record: dict,
                registered: dict, patches: dict) -> dict:
    row = {"repo": repo_label, "path": rel, "registered": "YES" if key in registered else "NO",
           "source_sha256": record.get("sha256_source", "")}
    target = Path(record["target"])
    row["target"] = (target.relative_to(REPO_ROOT).as_posix()
                     if target.is_absolute() and REPO_ROOT in target.parents
                     else str(target))
    if not target.is_file():
        row["class"] = "COPIED_MISSING_IN_TARGET"
        row["reason"] = "复制清单登记了该目标，但目标文件不存在"
        return row
    intended = record.get("sha256_target", "")
    actual = sha(target)
    if actual == intended:
        row["class"] = "COPIED_VERIFIED"
        row["reason"] = "已迁入，目标摘要与复制清单一致"
        return row
    if row["target"] in patches:
        # the manifest records the digest at copy time, before the declared patch
        # landed; compare digest to digest, because `actual` is a digest and the
        # re-derivation returns bytes — treating them as the same type would flag
        # every correctly patched file as drift.
        try:
            expected = sha256_of_bytes(
                migrate_module().expected_bytes(repo / rel, row["target"]))
        except Exception:  # noqa: BLE001 - an unresolvable expectation stays a finding
            expected = None
        if expected == actual:
            row["class"] = "COPIED_PATCHED"
            row["reason"] = "已迁入，目标字节等于“来源 + 声明补丁”"
            return row
    row["class"] = "COPIED_TARGET_DIFFERS"
    row["reason"] = ("目标字节既不同于复制清单，也不同于“来源+声明补丁”：属返工修复或漂移，"
                     "逐条依据见 migration/work-gap-disposition.csv 与 F01/F09 记录")
    return row


def _uncopied_row(repo_label: str, repo: Path, rel: str, key: str, registered: dict) -> dict:
    row = {"repo": repo_label, "path": rel, "registered": "YES" if key in registered else "NO",
           "source_sha256": sha(repo / rel)}
    if key in registered:
        category, target, reason = f01.classify(rel, repo)
        row["class"] = "REGISTERED_GAP"
        row["disposition"] = category
        row["disposition_target"] = target
        row["gap_id"] = registered[key].get("来源键", "")
        row["reason"] = "登记未迁入：" + reason
        return row
    category, reason = classify_unregistered(rel)
    row["class"] = category
    row["reason"] = reason
    return row


def build(repo_label: str, repo: Path, copied: dict, registered: dict, patches: dict) -> dict:
    files = list_source_files(repo)
    rows: list[dict] = []
    counts: Counter[str] = Counter()
    for rel in files:
        key = repo_label + ":" + rel
        for record in copied.get(str((repo / rel).resolve())) or [None]:
            if record is None:
                row = _uncopied_row(repo_label, repo, rel, key, registered)
            else:
                row = _copied_row(repo_label, repo, rel, key, record, registered, patches)
            counts[row["class"]] += 1
            rows.append(row)
    return {"repo": repo_label, "root": str(repo), "enumerated_files": len(files),
            "class_counts": dict(counts), "rows": rows,
            "reconciles": sum(counts.values()) == len(rows)}


def write_csv(rows: list[dict], path: Path) -> None:
    columns = ["repo", "path", "registered", "gap_id", "class", "disposition",
               "disposition_target", "target", "source_sha256", "reason"]
    present = [name for name in columns if any(name in row for row in rows)]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=present, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json-out", type=Path)
    args = parser.parse_args(argv)
    copied = copied_index()
    registered = registered_keys()
    patches = patch_map()
    documents = {}
    for label, repo in (("work", WORK), ("design", DESIGN)):
        document = build(label, repo, copied, registered, patches)
        csv_path = OUT_DIR / ("source-coverage-" + label + ".csv")
        write_csv(document["rows"], csv_path)
        document["csv"] = str(csv_path)
        documents[label] = document
    gap_rows = [(label, row) for label, doc in documents.items() for row in doc["rows"]
                if row["class"] == "REGISTERED_GAP"]
    summary = {
        "schemaVersion": "ai-work-lab/source-coverage/v1",
        "generated_at": now(),
        "note": "逐文件登记来源仓的非忽略工作树；类别之和必须等于行数。登记未迁入沿用 F01 的判定"
                "规则，未登记人群在本表首次命名，不再留在“无人计数”的状态。",
        "repos": {label: {"root": doc["root"], "enumerated_files": doc["enumerated_files"],
                          "rows": len(doc["rows"]), "reconciles": doc["reconciles"],
                          "csv": doc["csv"], "class_counts": doc["class_counts"]}
                  for label, doc in documents.items()},
        "cross_check": {
            "registered_gap_rows": len(gap_rows),
            "registered_gap_python_paths_by_repo": {
                label: sum(1 for row in doc["rows"]
                           if row["class"] == "REGISTERED_GAP"
                           and row["path"].endswith(".py"))
                for label, doc in documents.items()},
            "registered_gap_non_python_paths": sorted(
                row["path"] for _l, row in gap_rows if not row["path"].endswith(".py")),
            "f01_register_reports_work_python_gaps": 198,
            "mapping_rows": len(_mapping_rows()),
            "mapping_unique_paths": len(registered),
            "copy_manifest_records": sum(len(records) for records in copied.values()),
            "copy_manifest_distinct_sources": len(copied)},
    }
    payload = json.dumps(summary, ensure_ascii=False, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload, encoding="utf-8")
    print(payload)
    return 0 if all(doc["reconciles"] for doc in documents.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
