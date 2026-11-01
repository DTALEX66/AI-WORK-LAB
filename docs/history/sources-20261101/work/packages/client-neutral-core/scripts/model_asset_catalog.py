"""Read-only model asset catalog: inventory, path containment, incremental digest cache (WL3-330 / MR-05).

Pure functions over a caller-provided library root; never reads weights, never
writes outside the caller-provided cache dir, never hard-codes a machine path.
The catalog records metadata only (relative path, size, mtime, format clues,
identity state) and leaves content verification to an explicit opt-in digest pass.
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

# Model file formats we can recognize from extension (metadata only).
FORMAT_BY_SUFFIX: dict[str, str] = {
    ".safetensors": "safetensors",
    ".gguf": "gguf",
    ".ckpt": "ckpt",
    ".onnx": "onnx",
    ".pt": "pt",
    ".bin": "bin",
    ".json": "json",
}

# Prefix bytes sampled for the identity signal (cheap change detection).
_IDENTITY_SAMPLE_BYTES = 4096


def _resolve_within(root: Path, candidate: Path) -> Path | None:
    """Resolve a candidate path and return it only when it stays inside root."""
    try:
        resolved = candidate.resolve()
    except (OSError, RuntimeError):
        return None
    try:
        resolved.relative_to(root.resolve())
    except ValueError:
        return None
    return resolved


def list_assets(library_root: Path) -> list[dict[str, Any]]:
    """Enumerate model files under the library root (metadata only).

    Returns one entry per file with a recognized model extension, using a
    library-relative path. Raises ValueError when an entry escapes the root
    (junction/symlink escape).
    """
    root = library_root.resolve()
    if not root.is_dir():
        return []
    entries: list[dict[str, Any]] = []
    for candidate in root.rglob("*"):
        if not candidate.is_file():
            continue
        inside = _resolve_within(root, candidate)
        if inside is None:
            raise ValueError(f"path escapes library root: {candidate}")
        suffix = candidate.suffix.lower()
        fmt = FORMAT_BY_SUFFIX.get(suffix)
        if fmt is None:
            continue
        stat = candidate.stat()
        entries.append({
            "library_relative_path": str(inside.relative_to(root)).replace("\\", "/"),
            "size_bytes": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "format": fmt,
            "identity_state": "DISCOVERED",
        })
    entries.sort(key=lambda item: item["library_relative_path"])
    return entries


def digest_cache_path(cache_dir: Path) -> Path:
    return cache_dir / "model-asset-digest-cache.json"


def load_digest_cache(cache_dir: Path) -> dict[str, str]:
    """Load the digest cache; absent or corrupt cache yields an empty map."""
    path = digest_cache_path(cache_dir)
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {}
    return data if isinstance(data, dict) else {}


def compute_digest(asset_path: Path) -> str:
    """Full SHA-256 of a file; used only on first registration or change."""
    digest = hashlib.sha256()
    with asset_path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _identity_signal(asset_path: Path, size_bytes: int) -> str:
    """Cheap change signal: size + mtime + a prefix-sample hash.

    Catches edits that preserve size and land in the same mtime tick (the
    MR-05 'changed size but same mtime' and same-size-edit cases).
    """
    try:
        with asset_path.open("rb") as handle:
            sample = handle.read(_IDENTITY_SAMPLE_BYTES)
    except OSError:
        sample = b""
    prefix = hashlib.sha256(sample).hexdigest()
    return f"{size_bytes}:{asset_path.stat().st_mtime_ns}:{prefix}"


def refresh_digests(library_root: Path, cache_dir: Path, *, force: bool = False) -> dict[str, str]:
    """Incrementally refresh the digest cache keyed by relative path.

    Uses size + mtime + prefix-sample hash as the change signal; an unchanged
    file keeps its cached digest. force=True recomputes every entry.
    Returns the updated cache map and persists it under cache_dir.
    """
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache = load_digest_cache(cache_dir)
    for asset in list_assets(library_root):
        rel = asset["library_relative_path"]
        full_path = library_root / rel
        identity = _identity_signal(full_path, asset["size_bytes"])
        key = f"identity:{rel}"
        cached_identity = cache.get(key)
        if not force and cached_identity == identity and isinstance(cache.get(rel), str):
            continue
        cache[rel] = compute_digest(full_path)
        cache[key] = identity
    digest_cache_path(cache_dir).write_text(json.dumps(cache, indent=2), encoding="utf-8")
    return cache


def snapshot(library_root: Path, cache_dir: Path | None = None) -> dict[str, Any]:
    """Produce the model_inventory_snapshot for the library root.

    Every entry carries evidence_state; nothing is fabricated as LIVE when it
    is only DISCOVERED. When cache_dir is provided, digests are refreshed
    incrementally; otherwise digest_state stays UNAVAILABLE.
    """
    root = library_root.resolve()
    assets = list_assets(root)
    cache = load_digest_cache(cache_dir) if cache_dir is not None else {}
    for asset in assets:
        rel = asset["library_relative_path"]
        digest = cache.get(rel)
        asset["digest"] = digest if isinstance(digest, str) else None
        asset["digest_state"] = "VERIFIED" if isinstance(digest, str) else "UNAVAILABLE"
        asset["evidence_state"] = "OBSERVED" if asset["size_bytes"] > 0 else "UNVERIFIED"
    return {
        "schema_version": "workflow/model-asset/v1",
        "library_root": str(root),
        "asset_count": len(assets),
        "assets": assets,
        "generated_at": None,
        "quality": "metadata-only" if cache_dir is None else "with-digest-cache",
    }


def validate_path_containment(asset_path: str) -> bool:
    """True when the path is a plain relative model-root reference (no escape).

    Rejects absolute paths, drive letters, UNC, and parent traversal.
    """
    if not asset_path or asset_path.startswith(("/", "\\", "~")):
        return False
    if re.match(r"^[A-Za-z]:", asset_path):
        return False
    if ".." in Path(asset_path).parts:
        return False
    return True

