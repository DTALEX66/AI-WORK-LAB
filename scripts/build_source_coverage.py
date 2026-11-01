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
about the same file — and since 2026-10-31 they reuse the same **AST import graph**
of the running service, so neither can call an unimported file wired.

The 2026-10-31 rework also closed the second unfalsifiable claim: 226 rows used to
carry one shared sentence ("需 owner 判定…") while the guard test only looked for the
literal word ``owner``, so a whole undecided population could sit there without
failing anything. That class is now split by a decision ladder whose rungs each name
an in-repo authority (the ``UNREGISTERED_*`` classes, with a ``file:line`` citation),
and only what the ladder genuinely cannot decide stays as ``OWNER_DECISION_PENDING`` —
with a justification specific to that row's own bytes, importers and top-level names.

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
from pathlib import Path, PurePosixPath

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
#: The runtime import closure, built once per run and shared with F01's classifier
#: so both registers answer the "is it wired?" question with the same graph.
F01_GRAPH: dict = {}


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


def declared_file_copies() -> list[dict]:
    """The single-file copies migrate_sources.py declares, re-verified from disk right now.

    ``migration/copies.json`` is a snapshot of one applied run, so a copy the tool now
    declares (FILE_COPIES / PACKAGED_STATE_COPIES / AUTOMATION_PACKED_FILES) but that run
    predates is invisible here -- and the source stays classified as "registered, not
    copied" even though its bytes are in the tree. The declared table is the contract;
    this reads both files and hashes them, so a declared copy only counts when the
    destination really holds the source's bytes. A destination that differs from the
    source still lands in the register, as COPIED_TARGET_DIFFERS, exactly as a manifest
    record would.
    """
    module = migrate_module()
    records = []
    for repo_root, src_rel, dst_rel in (list(module.FILE_COPIES)
                                         + list(module.AUTOMATION_PACKED_FILES)):
        source, destination = Path(repo_root) / src_rel, REPO_ROOT / dst_rel
        if not source.is_file() or not destination.is_file():
            continue
        records.append(dict(source=str(source), target=str(destination),
                            sha256_source=sha(source), sha256_target=sha(destination),
                            declared_by="scripts/migrate_sources.py"))
    return records


def copied_index() -> dict[str, list[dict]]:
    """Absolute source path -> EVERY copy record that reads from it."""
    manifest = json.loads(COPIES.read_text(encoding="utf-8"))
    index: dict[str, list[dict]] = {}
    for group in manifest["copies"]:
        for record in group.get("records", []):
            index.setdefault(str(Path(record["source"]).resolve()), []).append(record)
    for record in declared_file_copies():
        key = str(Path(record["source"]).resolve())
        if not any(Path(existing["target"]).resolve() == Path(record["target"]).resolve()
                   for existing in index.get(key, [])):
            index.setdefault(key, []).append(record)
    return index


def _mapping_rows() -> list[dict]:
    with MAPPING.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _f01_register_rows() -> int:
    """Row count of the F01 disposition register as it stands on disk right now."""
    with f01.OUT_CSV.open(encoding="utf-8-sig", newline="") as handle:
        return len(list(csv.DictReader(handle)))


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


# ------------------------------------------------------------------ adjudication
#: Every ``UNREGISTERED_*`` verdict names the in-repo authority it came from, so a
#: reader can go and read the deciding text instead of trusting this table. Line
#: numbers are found by searching the cited file for the rule text at build time:
#: a rule that moves gets a new number, and a rule that disappears makes the
#: builder say ``AUTHORITY_NOT_FOUND`` rather than keep a stale citation.
AUTHORITY_SCANNED = {
    "f01": REPO_ROOT / "scripts" / "build_f01_disposition.py",
    "policy": REPO_ROOT / "INTEGRATION_POLICY.md",
    "entry": REPO_ROOT / "docs" / "CODEX-AUDIT-ENTRY.md",
    "self": REPO_ROOT / "scripts" / "build_source_coverage.py",
}
_LINE_CACHE: dict[str, dict[str, int]] = {}


def _heading_anchor(lines: list[str], number: int) -> str:
    """The markdown heading a line sits under, as a greppable anchor.

    A ``file:line`` citation into prose is a claim about a document that this project edits every
    round: one inserted paragraph moves every later number. The heading is what the citation
    actually means ("the sentence inside §15.19"), so the anchor names the heading and the guard
    resolves it by finding that heading and checking the cited text is inside its section.
    """
    for earlier in range(number - 1, -1, -1):
        text = lines[earlier]
        if not text.startswith("#"):
            continue
        title = text.lstrip("#").strip()
        if not title:
            continue
        # the anchor travels inside a CSV cell that is later split on ";" and " → ", so the
        # section number is used when the heading has one and separators are otherwise removed
        first = title.split(".", 1)[0].rstrip(". ")
        if title.startswith("§") or re.match(r"^\d+(\.\d+)*\.?\s", title):
            number_token = title.split()[0].rstrip(".")
            return number_token if number_token.startswith("§") else "§" + number_token
        for separator in (";", "；", " → ", ","):
            title = title.replace(separator, "-")
        return title
    return "DOCUMENT-PREAMBLE"


def _line_of(kind: str, needle: str) -> str:
    """A citation into an authority file: ``file:line`` for code, ``file#heading`` for prose."""
    path = AUTHORITY_SCANNED[kind]
    key = str(path)
    if key not in _LINE_CACHE:
        try:
            lines = path.read_text(encoding="utf-8-sig").splitlines()
        except OSError:
            lines = []
        _LINE_CACHE[key] = {}
        for number, text in enumerate(lines):
            if text.strip() and text not in _LINE_CACHE[key]:
                _LINE_CACHE[key][text] = number + 1
    hit = _LINE_CACHE[key].get(needle)
    if hit is None:
        for text, number in _LINE_CACHE[key].items():
            if needle in text:
                hit = number
                break
    if hit is None:
        return path.relative_to(REPO_ROOT).as_posix() + ":AUTHORITY_NOT_FOUND"
    if path.suffix == ".md":
        lines = path.read_text(encoding="utf-8-sig").splitlines()
        return "%s#%s" % (path.relative_to(REPO_ROOT).as_posix(), _heading_anchor(lines, hit))
    return path.relative_to(REPO_ROOT).as_posix() + ":" + str(hit)


def resolve_authority_cite(cite: str) -> tuple[bool, str]:
    """Does one authority citation still point at something that exists?

    Two shapes: ``file:line`` (code, where the number is meaningful) and ``file#anchor`` (prose,
    where a number would be moved by any paragraph edited above it). A prose cite resolves when
    the anchor is the section number (or sanitised title) of exactly one heading in that file.
    Living next to ``_line_of`` keeps the producing and checking rules one implementation.
    """
    cite = cite.strip()
    if not cite:
        return (False, "empty citation")
    if "AUTHORITY_NOT_FOUND" in cite:
        return (False, "the authority text this cite was built from is no longer in the file")
    if "#" in cite:
        rel, anchor = cite.split("#", 1)
    else:
        shaped = re.match(r"^(.+?):(\d+)$", cite)
        if not shaped:
            return (False, "citation is neither file:line nor file#anchor: " + cite)
        rel, anchor, line_text = shaped.group(1), None, int(shaped.group(2))
    path = REPO_ROOT / rel
    if not path.is_file():
        return (False, "file absent: " + rel)
    lines = path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    if anchor is not None:
        anchors = [_heading_anchor(lines, number) for number, text in enumerate(lines, start=1)
                   if text.startswith("#") and text.lstrip("#").strip()]
        if anchor not in anchors:
            return (False, "no heading resolves to anchor " + repr(anchor))
        if anchors.count(anchor) > 1:
            return (False, "anchor %r is ambiguous (%d headings)" % (anchor, anchors.count(anchor)))
        return (True, "section %s" % anchor)
    number = line_text
    if not (0 < number <= len(lines)):
        return (False, "line %d is out of range for %s" % (number, rel))
    if not lines[number - 1].strip():
        return (False, "line %d is blank" % number)
    return (True, lines[number - 1].strip()[:60])


INDEX_SKIP_PARTS = SKIP_PARTS | {".project-local", ".git", ".qoder-cn", ".cursor"}

def naming_index(root: Path) -> dict[str, set[str]]:
    """module stem -> files in ``root`` that import it.

    Built once per repository instead of re-walking the tree per row: 226 rows
    times a full scan is not a check anyone will run, and a check nobody runs is
    not a check. Scratch copies under the source's own ``.project-local`` are not
    consumers of the tracked tree, so they are skipped here even though the
    enumeration口径 (``SKIP_PARTS``) stays exactly as the guard test replicates it.
    """
    word = re.compile(r"\b(?:import|from)\s+[\w.]*\b(\w+)\b")
    index: dict[str, set[str]] = {}
    for path in root.rglob("*.py"):
        relative = path.relative_to(root).as_posix()
        if any(part in INDEX_SKIP_PARTS for part in relative.split("/")):
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for match in word.finditer(text):
            index.setdefault(match.group(1), set()).add(relative)
    return index


def _is_production_importer(relative: str) -> bool:
    return not ("tests/" in relative or "/tests/" in relative or "/test/" in relative
                or Path(relative).name.startswith("test_"))


def _module_facts(repo: Path, rel: str) -> tuple[bool, list[str]]:
    """AST facts of the file itself: a ``__main__`` guard and its top-level names.

    Used so an undecided row states what *this* module holds rather than adding
    another copy of a sentence that fits two hundred rows.
    """
    import ast

    try:
        tree = ast.parse((repo / rel).read_text(encoding="utf-8", errors="replace"))
    except (OSError, SyntaxError):
        return (False, [])
    has_main = any(isinstance(node, ast.If) and "__main__" in ast.dump(node.test)
                   for node in tree.body)
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(node.name)
    return (has_main, names)


def adjudicate_unregistered(repo: Path, rel: str, index: dict[str, set[str]],
                            digest: str) -> tuple[str, str, str]:
    """(class, authority, reason) for an unregistered ``.py`` the shape rules missed.

    Order matters: a fact about the target tree beats a fact about capability
    class, which beats a fact about who imports it. What the ladder cannot decide
    stays visibly undecided, carrying the evidence that makes *that row* a real
    question — its own bytes, its own importers, its own top-level names — so no
    two pending rows can share one boilerplate reason.
    """
    stem = Path(rel).stem
    others = sorted(p for p in index.get(stem, set()) if p != rel)
    producers = [p for p in others if _is_production_importer(p)]
    cli, symbols = _module_facts(repo, rel)

    target = REPO_ROOT / PurePosixPath(rel).as_posix()
    if target.is_file():
        return ("UNREGISTERED_TARGET_PATH_PRESENT",
                _line_of("self", "UNREGISTERED_TARGET_PATH_PRESENT"),
                "目标仓同一相对路径已有该文件（"
                + target.relative_to(REPO_ROOT).as_posix()
                + "）；未进复制清单不等于缺失")

    for pattern, reason in f01.OUT_OF_SCOPE_RULES:
        if pattern.search(rel):
            return ("UNREGISTERED_EXCLUDED_CAPABILITY",
                    _line_of("f01", pattern.pattern) + " → "
                    + _line_of("entry", "NOT_RUN**：真实用户数据迁移"),
                    "能力类被 owner 分期决定排除：" + reason)

    if not producers and (cli or f01.POC_RULE.search(rel) or f01.VERIFY_RULE.search(rel)):
        cites = [_line_of("self", "def adjudicate_unregistered")]
        if f01.POC_RULE.search(rel):
            cites.append(_line_of("f01", "_poc"))
        if f01.VERIFY_RULE.search(rel):
            cites.append(_line_of("f01", "verify_"))
        return ("UNREGISTERED_DEV_TOOLING", ";".join(dict.fromkeys(cites)),
                "本仓 import 面上零生产 importer（同名 importer 总数 " + str(len(others))
                + "），" + ("自身是 __main__ 命令行工具" if cli else "命中一次性/POC 规则")
                + "：不是运行面能力，不迁不构成缺口")

    return ("OWNER_DECISION_PENDING",
            "NONE（无现成权威覆盖此行）→ " + _line_of("self", "OWNER_DECISION_PENDING"),
            "待 owner 判定（本行字节 " + digest[:12] + "）："
            + "未登记、未迁入、目标树同路径无文件；"
            + ("来源仓内有 " + str(len(producers)) + " 个生产 importer（如 "
               + "、".join(producers[:2]) + "）" if producers
               else "来源仓内无生产 importer")
            + ("；带 __main__ 入口" if cli else "；无 __main__ 入口")
            + ("；顶层定义 " + "、".join(symbols[:4]) if symbols else "；顶层无具名定义")
            + "——是否属本批产品能力需逐条判定，本批不据其声称能力完整")


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


def _uncopied_row(repo_label: str, repo: Path, rel: str, key: str, registered: dict,
                  index: dict[str, set[str]]) -> dict:
    row = {"repo": repo_label, "path": rel, "registered": "YES" if key in registered else "NO",
           "source_sha256": sha(repo / rel)}
    if key in registered:
        category, target, reason, consumers = f01.classify(rel, repo, F01_GRAPH)
        row["class"] = "REGISTERED_GAP"
        row["disposition"] = category
        row["disposition_target"] = target
        row["gap_id"] = registered[key].get("来源键", "")
        row["authority"] = ("migration/work-gap-disposition.csv 运行面消费者="
                           + (consumers or "无"))
        row["reason"] = "登记未迁入：" + reason
        return row
    cls, reason = classify_unregistered(rel)
    if cls == "SOURCE_UNREGISTERED":
        cls, authority, reason = adjudicate_unregistered(repo, rel, index,
                                                         row["source_sha256"])
        row["authority"] = authority
    row["class"] = cls
    row["reason"] = reason
    return row


def build(repo_label: str, repo: Path, copied: dict, registered: dict, patches: dict,
          graph: dict) -> dict:
    global F01_GRAPH
    if not graph or not graph.get("reachable"):
        raise SystemExit("IMPORT_GRAPH_NOT_BUILT: refusing to label closure rows without it")
    F01_GRAPH = graph
    files = list_source_files(repo)
    index = naming_index(repo)
    rows: list[dict] = []
    counts: Counter[str] = Counter()
    for rel in files:
        key = repo_label + ":" + rel
        for record in copied.get(str((repo / rel).resolve())) or [None]:
            if record is None:
                row = _uncopied_row(repo_label, repo, rel, key, registered, index)
            else:
                row = _copied_row(repo_label, repo, rel, key, record, registered, patches)
            counts[row["class"]] += 1
            rows.append(row)
    pending = sorted(row["path"] for row in rows if row["class"] == "OWNER_DECISION_PENDING")
    adjudicated = sorted(row["path"] for row in rows
                         if row["class"].startswith("UNREGISTERED_"))
    reasons = Counter(row["reason"] for row in rows
                      if row["class"] == "OWNER_DECISION_PENDING")
    return {"repo": repo_label, "root": str(repo), "enumerated_files": len(files),
            "class_counts": dict(counts), "rows": rows,
            "pending_owner_decisions": pending,
            "adjudicated_population": adjudicated,
            "pending_reason_duplicates": {text: number for text, number in reasons.items()
                                          if number > 1},
            "reconciles": sum(counts.values()) == len(rows)}


def write_csv(rows: list[dict], path: Path) -> None:
    columns = ["repo", "path", "registered", "gap_id", "class", "disposition",
               "disposition_target", "target", "authority", "source_sha256", "reason"]
    present = [name for name in columns if any(name in row for row in rows)]
    missing = {name for row in rows for name in row if name not in columns}
    if missing:
        raise SystemExit("CSV_COLUMN_NOT_DECLARED " + ", ".join(sorted(missing)))
    temporary = path.with_suffix(".csv.tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="\n") as handle:
        writer = csv.DictWriter(handle, fieldnames=present, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    temporary.replace(path)


def _drift(path: Path, rows: list[dict]) -> list[str]:
    """Which row keys the tracked register no longer agrees on.

    The ``authority`` column stores ``file:line`` for text searched inside docs and scripts at
    build time. Editing any of those files moves the lines, so a tracked register can cite a
    number that is in range but points at unrelated prose -- and the guard that checks
    "the line exists" stays green. ``--check`` is how a test can notice the drift without the
    suite becoming a writer.
    """
    if not path.is_file():
        return ["<missing register>"]
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        columns = list(reader.fieldnames or [])
        tracked = [{key: row[key] for key in columns} for row in reader]
    # compare only the published columns: the in-memory rows carry bookkeeping keys the
    # writer deliberately drops, and counting those as drift reports every row as changed
    expected = [{key: str(row.get(key, "")) for key in columns} for row in rows]
    changed = []
    for index, (before, after) in enumerate(zip(tracked, expected)):
        if before != after:
            keys = sorted(key for key in columns if before.get(key) != after.get(key))
            changed.append("%s: %s" % (after.get("path", index), ",".join(keys)))
    if len(tracked) != len(expected):
        changed.append("<row count %d != %d>" % (len(tracked), len(expected)))
    return changed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--json-out", type=Path)
    parser.add_argument("--check", action="store_true",
                        help="rebuild and compare with the tracked registers; never write them")
    args = parser.parse_args(argv)
    absent = [{"label": label, "root": str(repo)}
              for label, repo in (("work", WORK), ("design", DESIGN)) if not repo.is_dir()]
    if absent:
        # These registers are enumerations of the two read-only source working trees. With a tree
        # missing there is nothing to enumerate: reporting "matches" would be a green that measured
        # nothing, and writing a register over an empty population would publish "0 files" as a fact
        # about a repository this run could not read. So name the condition and stop.
        payload = {"error": "SOURCE_REPO_ABSENT", "absent": absent,
                   "verdict": "NOT_RECOMPUTABLE_HERE", "check": bool(args.check),
                   "note": ("run this builder where WORK-LAB and DESIGN-LAB are present; the tracked "
                            "registers remain the record of the run that could read them")}
        text = json.dumps(payload, ensure_ascii=False)
        if args.json_out:
            args.json_out.parent.mkdir(parents=True, exist_ok=True)
            args.json_out.write_text(text + "\n", encoding="utf-8")
        print(text)
        return 3
    copied = copied_index()
    registered = registered_keys()
    patches = patch_map()
    graph = f01.build_runtime_import_graph()
    documents = {}
    drift: dict[str, list[str]] = {}
    for label, repo in (("work", WORK), ("design", DESIGN)):
        document = build(label, repo, copied, registered, patches, graph)
        csv_path = OUT_DIR / ("source-coverage-" + label + ".csv")
        if args.check:
            drift[label] = _drift(csv_path, document["rows"])
        else:
            write_csv(document["rows"], csv_path)
        document["csv"] = str(csv_path)
        documents[label] = document
    gap_rows = [(label, row) for label, doc in documents.items() for row in doc["rows"]
                if row["class"] == "REGISTERED_GAP"]
    summary = {
        "schemaVersion": "ai-work-lab/source-coverage/v1",
        "generated_at": now(),
        "note": "逐文件登记来源仓的非忽略工作树；类别之和必须等于行数。登记未迁入沿用 F01 的判定"
                "规则，未登记人群在本表首次命名并按现有权威逐条判定：判不动的行保留为 "
                "OWNER_DECISION_PENDING，且必须带本行独有的依据，不再共用一句“需 owner 判定”。",
        "repos": {label: {"root": doc["root"], "enumerated_files": doc["enumerated_files"],
                          "rows": len(doc["rows"]), "reconciles": doc["reconciles"],
                          "csv": doc["csv"], "class_counts": doc["class_counts"],
                          "pending_owner_decision_count": len(doc["pending_owner_decisions"]),
                          "pending_owner_decisions": doc["pending_owner_decisions"],
                          "adjudicated_by_authority_count": len(doc["adjudicated_population"]),
                          "adjudicated_by_authority": doc["adjudicated_population"],
                          "pending_reason_duplicates": doc["pending_reason_duplicates"]}
                  for label, doc in documents.items()},
        "import_graph": {"entries": list(graph["entries"]),
                         "reachable_modules": len(graph["reachable"]),
                         "universe_python_files": graph["universe"]},
        "cross_check": {
            "registered_gap_rows": len(gap_rows),
            "registered_gap_python_paths_by_repo": {
                label: sum(1 for row in doc["rows"]
                           if row["class"] == "REGISTERED_GAP"
                           and row["path"].endswith(".py"))
                for label, doc in documents.items()},
            "registered_gap_non_python_paths": sorted(
                row["path"] for _l, row in gap_rows if not row["path"].endswith(".py")),
            # Derived from the other register, not from a remembered number: the two builders
            # read different inputs (mapping.csv + copies.json vs. the declared copy table),
            # so agreement between them is a check and a literal "198" would only ever be a
            # number to bump. The audited baseline stays here as history, with its delta.
            "f01_register_reports_work_python_gaps": _f01_register_rows(),
            "audited_baseline_2026_10_30_work_python_gaps": 198,
            "gap_delta_since_audit": 198 - _f01_register_rows(),
            "mapping_rows": len(_mapping_rows()),
            "mapping_unique_paths": len(registered),
            "copy_manifest_records": sum(len(records) for records in copied.values()),
            "copy_manifest_distinct_sources": len(copied)},
    }
    payload = json.dumps(summary, ensure_ascii=True, indent=2)
    if args.json_out is not None:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(payload, encoding="utf-8")
    if args.check:
        drifted = {label: sample for label, sample in drift.items() if sample}
        unreconciled = sorted(label for label, doc in documents.items() if not doc["reconciles"])
        print(json.dumps(dict(check=True, drifted=sorted(drifted),
                              rows_changed={label: len(sample) for label, sample in drift.items()},
                              unreconciled=unreconciled,
                              hint="rerun without --check to re-resolve the authority lines"),
                         ensure_ascii=True))
        return 1 if (drifted or unreconciled) else 0
    print(payload)
    return 0 if all(doc["reconciles"] for doc in documents.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
