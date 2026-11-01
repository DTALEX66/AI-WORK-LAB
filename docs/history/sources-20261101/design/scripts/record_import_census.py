#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Read-only census of the external Record volume.

Classifies every top-level entry by CONTENT evidence (marker counts in text,
zip member names, docx/xlsx internals) rather than by filename, so the import
manifest for task DL-REC-29 can justify each decision with measured numbers.

Writes only under .project-local/ (gitignored). Never deletes, moves or
modifies anything in the source volume.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(r"D:\All projects\Record")
HASH_CAP = 64 * 1024 * 1024          # do not hash files above this
TEXT_SUFFIXES = {".md", ".txt", ".json", ".csv", ".html", ".yaml", ".yml", ".htm"}
XML_SUFFIXES = {".docx", ".xlsx", ".pptx"}

MARKERS = {
    "design": (r"DESIGN[\s\-_]?LAB", r"设计实验室", r"DL-TP-", r"DL-R5-", r"DL-AUTHORITY", r"designlab"),
    "work": (r"WORK[\s\-_]?LAB", r"WORKLAB"),
    "arche": (r"ARCHEAXIS", r"ArcheAxis", r"archeaxis"),
    "aaos": (r"AAOS"),
}


def digest(path: Path) -> str | None:
    try:
        if path.stat().st_size > HASH_CAP:
            return None
    except OSError:
        return None
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(1 << 20), b""):
                h.update(chunk)
    except OSError:
        return None
    return "sha256:" + h.hexdigest()


def marker_counts(text: str) -> dict[str, int]:
    out = {}
    for family, patterns in MARKERS.items():
        n = 0
        for pat in patterns:
            n += len(re.findall(pat, text, flags=re.IGNORECASE if family in ("design", "work") else 0))
        out[family] = n
    return out


def text_of(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    return raw.decode("utf-8", errors="replace")


def office_xml_text(path: Path) -> str:
    """Concatenate the XML parts of a docx/xlsx/pptx so markers are countable."""
    parts: list[str] = []
    try:
        with zipfile.ZipFile(path) as zf:
            for name in zf.namelist():
                if not name.endswith((".xml", ".rels")):
                    continue
                if not (name.startswith("word/") or name.startswith("xl/")
                        or name.startswith("ppt/") or name.startswith("docProps/")):
                    continue
                try:
                    parts.append(zf.read(name).decode("utf-8", errors="replace"))
                except (OSError, KeyError):
                    continue
    except (OSError, zipfile.BadZipFile):
        return ""
    joined = "\n".join(parts)
    return re.sub(r"<[^>]+>", " ", joined)


def zip_report(path: Path) -> dict:
    members = []
    try:
        with zipfile.ZipFile(path) as zf:
            bad = zf.testzip()
            for info in zf.infolist():
                if info.is_dir():
                    continue
                members.append({
                    "name": info.filename,
                    "size": info.file_size,
                    "compress_size": info.compress_size,
                    "crc32": f"{info.CRC & 0xFFFFFFFF:08x}",
                    "design": bool(re.search(r"DESIGN[\s\-_]?LAB|designlab|DL-TP-|DL-R5-|设计实验室",
                                             info.filename, re.IGNORECASE)),
                })
            total = sum(m["size"] for m in members)
    except (OSError, zipfile.BadZipFile) as exc:
        return {"zip_error": str(exc), "members": [], "member_count": 0,
                "uncompressed_bytes": 0, "crc_ok": False}
    return {"zip_error": None, "crc_ok": bad is None, "bad_member": bad,
            "member_count": len(members), "uncompressed_bytes": total,
            "design_member_count": sum(1 for m in members if m["design"]),
            "members": members}


def scan_file(path: Path) -> dict:
    suffix = path.suffix.lower()
    rec: dict = {"kind": "file", "bytes": path.stat().st_size, "sha256": digest(path)}
    if suffix in TEXT_SUFFIXES:
        rec["markers"] = marker_counts(text_of(path))
    elif suffix in XML_SUFFIXES:
        rec["markers"] = marker_counts(office_xml_text(path))
        rec["office_container"] = True
    elif suffix == ".zip":
        zr = zip_report(path)
        rec["markers"] = {"design": zr["design_member_count"], "work": 0, "arche": 0, "aaos": 0}
        rec["zip"] = {k: v for k, v in zr.items() if k != "members"}
        rec["zip_members"] = zr["members"]
    return rec


def scan_dir(path: Path) -> dict:
    children = []
    total = 0
    count = 0
    for child in sorted(path.rglob("*")):
        if not child.is_file():
            continue
        count += 1
        try:
            size = child.stat().st_size
        except OSError:
            size = 0
        total += size
        rel = str(child.relative_to(path))
        entry = {"rel": rel, "bytes": size}
        if size <= HASH_CAP:
            entry["sha256"] = digest(child)
        suffix = child.suffix.lower()
        if suffix in TEXT_SUFFIXES and size <= 8 * 1024 * 1024:
            entry["markers"] = marker_counts(text_of(child))
        elif suffix in XML_SUFFIXES:
            entry["markers"] = marker_counts(office_xml_text(child))
        elif suffix == ".zip":
            zr = zip_report(child)
            entry["markers"] = {"design": zr["design_member_count"], "work": 0, "arche": 0, "aaos": 0}
            entry["zip"] = {k: v for k, v in zr.items() if k != "members"}
        children.append(entry)
    agg = {k: 0 for k in MARKERS}
    for c in children:
        for k, v in (c.get("markers") or {}).items():
            agg[k] += v
    return {"kind": "dir", "file_count": count, "bytes": total,
            "markers_agg": agg, "children": children}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", default=str(DEFAULT_SOURCE))
    ap.add_argument("--out", required=True)
    ap.add_argument("--members", action="store_true", help="include full zip member tables")
    args = ap.parse_args()

    source = Path(args.source)
    if not source.is_dir():
        print(f"CENSUS ABORT: source not a directory: {source}")
        return 2

    entries = {}
    for child in sorted(source.iterdir()):
        rec = scan_dir(child) if child.is_dir() else scan_file(child)
        rec["name"] = child.name
        rec["source_path"] = str(child)
        entries[child.name] = rec

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    payload = {"schemaVersion": "design-lab/record-census/v1",
               "source": str(source), "entry_count": len(entries),
               "total_bytes": sum(e.get("bytes", 0) for e in entries.values()),
               "entries": entries}
    if not args.members:
        for e in entries.values():
            e.pop("zip_members", None)
            e.pop("children", None)
    out.write_text(json.dumps(payload, ensure_ascii=False, indent=1), encoding="utf-8")

    lines = ["# RECORD CENSUS", "",
             f"source: {source}", f"entries: {len(entries)}",
             f"total_bytes: {payload['total_bytes']:,}", "",
             "| entry | kind | bytes | design | work | arche | aaos |", "|---|---|---|---|---|---|---|"]
    for name, e in entries.items():
        if e["kind"] == "dir":
            m = e["markers_agg"]
        else:
            m = e.get("markers") or {}
        lines.append(f"| {name} | {e['kind']} | {e.get('bytes', 0):,} | "
                     f"{m.get('design', '-')} | {m.get('work', '-')} | "
                     f"{m.get('arche', '-')} | {m.get('aaos', '-')} |")
    md = out.with_suffix(".md")
    md.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"CENSUS entries={len(entries)} total_bytes={payload['total_bytes']:,}")
    print(f"JSON {out}")
    print(f"MD   {md}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
