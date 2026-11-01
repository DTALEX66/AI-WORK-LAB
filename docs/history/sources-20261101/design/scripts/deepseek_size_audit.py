#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DLDS-D000 — repository size audit, six artifacts.

Measures what the repository actually holds, separating Git-tracked content from
ignored runtime data, and classifies every large or binary object so the later
cleanup tasks act on evidence rather than on a guess.

Writes:
    reports/current/REPOSITORY-SIZE.json
    reports/current/LARGEST-FILES.json
    reports/current/SIZE-BY-DIRECTORY.json
    reports/current/SIZE-BY-EXTENSION.json
    reports/current/TRACKED-BINARY.json
    reports/current/UNTRACKED-RUNTIME.json

Usage:
    python scripts/deepseek_size_audit.py
    python scripts/deepseek_size_audit.py --check
"""
from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
OUT = REPO / "reports/current"
TASK_KEY = "DL-TP-20260914-DEEPSEEK-AUTHORITY-R1::DLDS-D000"
# Runtime roots that are ignored by Git but still occupy the working volume.
IGNORED_ROOTS = (".project-local", ".hermes", ".venv", ".pytest_cache")
# Extensions that must never be tracked in a product repository.
BINARY_CLASSES = {
    "model-weights": {".safetensors", ".ckpt", ".pt", ".pth", ".onnx", ".bin", ".gguf", ".h5",
                      ".msgpack", ".pkl", ".npz"},
    "media": {".mp4", ".mov", ".webm", ".flac", ".wav", ".mp3", ".webp", ".png", ".jpg", ".jpeg",
              ".gif", ".tif", ".tiff", ".psd", ".ai", ".blend", ".prproj", ".aep"},
    "archive": {".zip", ".tar", ".gz", ".7z", ".rar", ".xz", ".whl", ".jar", ".apk"},
    "font": {".ttf", ".otf", ".woff", ".woff2", ".eot"},
    "document": {".pdf", ".docx", ".xlsx", ".pptx", ".sketch", ".fig"},
    "executable": {".exe", ".dll", ".so", ".dylib", ".bin"},
}
BUDGET_WARNING_MIB = 224.0
BUDGET_LIMIT_MIB = 256.0


def git(*args: str) -> str:
    return subprocess.run(["git", "-C", str(REPO), *args], capture_output=True, text=True,
                          encoding="utf-8", errors="replace").stdout


def tracked_blobs() -> list:
    blobs = []
    for line in git("ls-tree", "-rl", "HEAD").splitlines():
        if "\t" not in line:
            continue
        meta, path = line.split("\t", 1)
        parts = meta.split()
        if len(parts) >= 4 and parts[1] == "blob":
            blobs.append({"path": path, "bytes": int(parts[3]), "object": parts[2]})
    return blobs


def walk_ignored(root: Path, limit_files: int = 400_000) -> dict:
    total_files = 0
    total_bytes = 0
    by_subdir = {}
    oldest = None
    newest = None
    for path in root.rglob("*"):
        try:
            if not path.is_file():
                continue
            stat = path.stat()
        except OSError:
            continue
        total_files += 1
        total_bytes += stat.st_size
        if total_files > limit_files:
            break
        rel = path.relative_to(root)
        key = rel.parts[0] if len(rel.parts) > 1 else "(root)"
        bucket = by_subdir.setdefault(key, {"files": 0, "bytes": 0})
        bucket["files"] += 1
        bucket["bytes"] += stat.st_size
        stamp = stat.st_mtime
        oldest = stamp if oldest is None else min(oldest, stamp)
        newest = stamp if newest is None else max(newest, stamp)
    return {"files": total_files, "bytes": total_bytes, "by_subdir": by_subdir,
            "oldest_mtime": oldest, "newest_mtime": newest}


def category_for(path: str) -> tuple:
    suffix = Path(path).suffix.lower()
    for name, suffixes in BINARY_CLASSES.items():
        if suffix in suffixes:
            return name, suffix
    return "other", suffix


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    blobs = tracked_blobs()
    tracked_bytes = sum(b["bytes"] for b in blobs)
    pack = dict(line.split(":", 1) for line in git("count-objects", "-vH").splitlines() if ":" in line)
    size_pack = float(pack.get("size-pack", "0 MiB").strip().split()[0])
    status = ("OVER_LIMIT" if size_pack > BUDGET_LIMIT_MIB
              else "WARNING" if size_pack >= BUDGET_WARNING_MIB else "OK")

    by_directory = {}
    by_extension = Counter()
    by_extension_bytes = Counter()
    for blob in blobs:
        area = blob["path"].split("/")[0]
        entry = by_directory.setdefault(area, {"files": 0, "bytes": 0})
        entry["files"] += 1
        entry["bytes"] += blob["bytes"]
        suffix = Path(blob["path"]).suffix.lower() or "(none)"
        by_extension[suffix] += 1
        by_extension_bytes[suffix] += blob["bytes"]

    binaries = []
    for blob in blobs:
        category, suffix = category_for(blob["path"])
        if category != "other":
            binaries.append({**blob, "category": category, "extension": suffix})
    binaries.sort(key=lambda item: -item["bytes"])

    models = [b for b in binaries if b["category"] == "model-weights"]
    ignored = {}
    for name in IGNORED_ROOTS:
        root = REPO / name
        if root.is_dir():
            ignored[name] = walk_ignored(root)

    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    documents = {}
    documents["REPOSITORY-SIZE.json"] = {
        "schemaVersion": "design-lab/repository-size-audit/v1",
        "task_key": TASK_KEY,
        "measured_at": now,
        "subject_sha": git("rev-parse", "HEAD").strip(),
        "tracked": {"files": len(blobs), "bytes": tracked_bytes, "mib": round(tracked_bytes / 1048576, 2)},
        "git_objects": {"in_pack": int(pack.get("in-pack", "0").strip()),
                        "packs": int(pack.get("packs", "0").strip()),
                        "size_pack_mib": size_pack,
                        "loose_objects": int(pack.get("count", "0").strip())},
        "budget": {"warning_mib": BUDGET_WARNING_MIB, "limit_mib": BUDGET_LIMIT_MIB,
                   "status": status, "basis": "measured pack size compared with the thresholds "
                                              "pinned by design-lab/scripts/verify_repository_size.py"},
        "ignored_roots": {name: {"files": info["files"], "mib": round(info["bytes"] / 1048576, 2)}
                          for name, info in ignored.items()},
        "tracked_binary_objects": len(binaries),
        "tracked_model_weight_objects": len(models),
        "note": "pack size is dominated by history, not by the current tree; the audit is "
                "observational and authorises no history rewrite",
    }
    documents["LARGEST-FILES.json"] = {
        "schemaVersion": "design-lab/largest-files/v1",
        "task_key": TASK_KEY,
        "measured_at": now,
        "tracked_top": sorted(blobs, key=lambda b: -b["bytes"])[:50],
        "ignored_top": {
            name: sorted(
                ({"path": str(p.relative_to(REPO)).replace("\\", "/"), "bytes": p.stat().st_size}
                 for p in (REPO / name).rglob("*") if p.is_file()),
                key=lambda item: -item["bytes"])[:25]
            for name in IGNORED_ROOTS if (REPO / name).is_dir()},
    }
    documents["SIZE-BY-DIRECTORY.json"] = {
        "schemaVersion": "design-lab/size-by-directory/v1",
        "task_key": TASK_KEY,
        "measured_at": now,
        "tracked_by_area": {k: {**v, "mib": round(v["bytes"] / 1048576, 2)}
                            for k, v in sorted(by_directory.items(), key=lambda kv: -kv[1]["bytes"])},
        "ignored_by_subdir": {name: {k: {**v, "mib": round(v["bytes"] / 1048576, 2)}
                                     for k, v in sorted(info["by_subdir"].items(),
                                                        key=lambda kv: -kv[1]["bytes"])}
                              for name, info in ignored.items()},
    }
    documents["SIZE-BY-EXTENSION.json"] = {
        "schemaVersion": "design-lab/size-by-extension/v1",
        "task_key": TASK_KEY,
        "measured_at": now,
        "tracked": [{"extension": ext, "files": by_extension[ext], "bytes": by_extension_bytes[ext],
                     "mib": round(by_extension_bytes[ext] / 1048576, 3)}
                    for ext in sorted(by_extension, key=lambda e: -by_extension_bytes[e])[:40]],
    }
    documents["TRACKED-BINARY.json"] = {
        "schemaVersion": "design-lab/tracked-binary-inventory/v1",
        "task_key": TASK_KEY,
        "measured_at": now,
        "count": len(binaries),
        "by_category": dict(Counter(b["category"] for b in binaries)),
        "model_weight_objects": models,
        "objects": binaries[:200],
        "verdict": "NO_MODEL_WEIGHTS_TRACKED" if not models else "MODEL_WEIGHTS_TRACKED",
    }
    documents["UNTRACKED-RUNTIME.json"] = {
        "schemaVersion": "design-lab/untracked-runtime-census/v1",
        "task_key": TASK_KEY,
        "measured_at": now,
        "roots": {name: {"files": info["files"], "bytes": info["bytes"],
                         "mib": round(info["bytes"] / 1048576, 2),
                         "oldest_mtime": info["oldest_mtime"], "newest_mtime": info["newest_mtime"],
                         "by_subdir": {k: {**v, "mib": round(v["bytes"] / 1048576, 2)}
                                       for k, v in sorted(info["by_subdir"].items(),
                                                          key=lambda kv: -kv[1]["bytes"])}}
                  for name, info in ignored.items()},
        "total_mib": round(sum(info["bytes"] for info in ignored.values()) / 1048576, 2),
        "classification_pending": "DLDS-D030/D040 and Wave 4 classify and act; nothing is deleted here",
    }

    if args.check:
        drift = [name for name, payload in documents.items()
                 if not (OUT / name).is_file()
                 or json.loads((OUT / name).read_text(encoding="utf-8")).get("task_key") != payload["task_key"]]
        print("SIZE_AUDIT=" + ("PASS" if not drift else f"DRIFT {drift}"))
        return 0 if not drift else 1
    OUT.mkdir(parents=True, exist_ok=True)
    for name, payload in documents.items():
        (OUT / name).write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
                                encoding="utf-8", newline="\n")
        print(f"wrote reports/current/{name}")
    print(f"tracked files={len(blobs)} mib={tracked_bytes / 1048576:.2f} | pack_mib={size_pack} "
          f"status={status}")
    print(f"tracked binaries={len(binaries)} model-weights={len(models)} "
          f"| ignored total={sum(i['bytes'] for i in ignored.values()) / 1048576:.1f} MiB")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
