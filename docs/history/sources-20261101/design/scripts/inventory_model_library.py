# SPDX-License-Identifier: MIT
"""Refresh the external-assets index from what the declared model library holds.

`design-lab/config/external-assets-index.json` claims to be the inventory of this
project's assets in the shared roots. It listed 5 entries with `generated_at` of
2026-08-16; a walk of the declared `model-library` root finds 20+ model weights,
including a complete SDXL image-generation stack (diffusion model, both text encoders,
VAE), a Qwen2.5-VL vision-language pair, Qwen3 embedding and reranker GGUFs, and two
sherpa-onnx ASR engines -- none of which the index, the model radar, or any capability
count knows about.

This is deliberately a *local* tool, and it refuses rather than writing an empty
inventory: the shared root exists on the machine that owns it and not on a CI runner,
so a CI-invoked version of this script would "successfully" erase every asset.

Ownership is recorded honestly. A file found in a shared root is not DESIGN-LAB's just
because this project noticed it: anything not already in the index comes back
`unattributed` and `review-required`, which is also the rights-gate queue, since several
of these licences (SDXL's openRAIL-M family, Qwen's, sherpa's per-model terms) are not
the project's MIT and must not be folded into the project licence face.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
INDEX = REPO / "design-lab" / "config" / "external-assets-index.json"
SCHEMA_ID = "../../schemas/external-assets-index.schema.json"
MODEL_SUFFIXES = {".safetensors", ".gguf", ".onnx", ".pt", ".pth", ".bin"}
# Directories that are not assets: a scratch download area and archive duplicates.
RESIDUE_DIRS = ("runtimes-tmp/",)
CATEGORY_BY_DIR = {
    "diffusion_models": "image-or-video diffusion",
    "text_encoders": "text encoder",
    "vae": "vae",
    "whisper": "asr",
    "sherpa-onnx": "asr",
}


def resolve_library_root() -> Path | None:
    """The declared shared root, from .project/paths.json -- never a guess."""
    sys.path.insert(0, str(REPO / "src"))
    from design_lab.runtime.paths import resolve_paths

    layout = resolve_paths(project_root=REPO)
    declared = layout.shared_inputs.get("model-library")
    if not declared:
        return None
    return Path(str(declared))


def make_id(relative: str) -> str:
    stem = re.sub(r"[^a-z0-9]+", "-", relative.lower()).strip("-")
    for suffix in ("-safetensors", "-gguf", "-onnx", "-pt", "-bin", "-pth"):
        if stem.endswith(suffix):
            stem = stem[: -len(suffix)]
    return stem[:96]


def radar_referenced_dirs() -> dict[str, str]:
    """Relative paths the model radar already points at, keyed by directory.

    The radar stores `model-library:<relative>` aliases. A discovered file under one of
    those directories is not "unattributed": the project already references it, and
    saying otherwise would make the index contradict the radar -- the same two-paths-one-
    answer defect recorded for model_cache in the DL-R5-007 review.
    """
    out: dict[str, str] = {}
    path = REPO / "design-lab" / "readiness" / "model-radar.json"
    if not path.is_file():
        return out
    for entry in json.loads(path.read_text(encoding="utf-8")).get("entries", []):
        local = entry.get("local_path")
        if isinstance(local, str) and local.startswith("model-library:"):
            relative = local.split(":", 1)[1].strip("/")
            out[relative.split("/")[0] if "/" not in relative else str(Path(relative).parent)] = \
                str(entry.get("model_id"))
            out[str(Path(relative).parent)] = str(entry.get("model_id"))
    return out


def classify(relative: Path) -> tuple[str, str]:
    parts = relative.parts
    parent = parts[-2].lower() if len(parts) >= 2 else ""
    category = CATEGORY_BY_DIR.get(parent, "")
    if not category:
        lowered = str(relative).lower()
        if "vl" in lowered or "vision" in lowered:
            category = "vision-language"
        elif "embed" in lowered:
            category = "embedding"
        elif "rerank" in lowered:
            category = "reranker"
        elif "sense-voice" in lowered or "zipformer" in lowered:
            category = "asr"
        else:
            category = "unclassified"
    # Ownership is never inferred from a directory name. The ComfyUI/ subtree holds both
    # this project's H3 weights and ordinary community downloads (sd_xl_base, clip_l),
    # and "this file sits next to ours" is not evidence that ours placed it.
    return category, "unattributed"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true",
                        help="write the index; without it this is a report")
    args = parser.parse_args(argv)

    root = resolve_library_root()
    if root is None or not root.is_dir():
        # Fail closed: writing here would replace a real inventory with an empty one.
        print(f"MODEL_LIBRARY_REFUSAL: declared root unavailable ({root})")
        return 2

    index = json.loads(INDEX.read_text(encoding="utf-8"))
    known = {a["relative_path"].replace("\\", "/") for a in index["assets"]}
    found = sorted(p for p in root.rglob("*")
                   if p.is_file() and p.suffix.lower() in MODEL_SUFFIXES)

    new_entries, residue = [], []
    radar = radar_referenced_dirs()
    for path in found:
        relative = path.relative_to(root).as_posix()
        if relative in known:
            continue
        if relative.startswith(RESIDUE_DIRS):
            residue.append((relative, path.stat().st_size))
            continue
        category, owner = classify(path.relative_to(root))
        referenced = next((model_id for directory, model_id in radar.items()
                           if relative == directory or relative.startswith(directory + "/")),
                          None)
        new_entries.append({
            "id": make_id(relative),
            "shared_root": "model-library",
            "relative_path": relative,
            "kind": "model-weight",
            "category": category,
            "size_bytes": path.stat().st_size,
            "owned_by": owner,
            # review-required even when the radar references it: a reference is not a
            # licence adjudication, and several of these are not the project's MIT.
            "status": "review-required",
            "note": ("discovered by scripts/inventory_model_library.py walking the declared "
                     "model-library root; licence not adjudicated"
                     + (f"; already referenced by model-radar entry {referenced}"
                        if referenced else "")),
        })

    ids = [a["id"] for a in index["assets"]] + [e["id"] for e in new_entries]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        print(f"REFUSING: duplicate asset ids would be written: {duplicates}")
        return 2

    print(f"walked={len(found)} already_listed={len(known)} new={len(new_entries)} "
          f"residue_skipped={len(residue)}")
    for entry in new_entries:
        print(f"   + {entry['owned_by']:12s} {entry['status']:16s} {entry['category']:26s} "
              f"{entry['relative_path']}")
    for relative, size in residue:
        print(f"   ! residue {relative} ({size:,} bytes) -- not registered as an asset")

    if not args.apply:
        print("DRY_RUN: index untouched; re-run with --apply")
        return 0

    index["assets"].extend(new_entries)
    index["assets"].sort(key=lambda a: (a["shared_root"], a["relative_path"]))
    index["$schema"] = SCHEMA_ID
    with INDEX.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(json.dumps(index, ensure_ascii=False, indent=2) + "\n")
    print(f"EXTERNAL_ASSETS_INDEX=WRITTEN assets={len(index['assets'])} "
          f"added={len(new_entries)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
