# SPDX-License-Identifier: MIT
"""Fail-closed local font matching over explicit, authorized font files."""
from __future__ import annotations

import hashlib
import os
import stat
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from PIL import Image, ImageChops, ImageDraw, ImageFont


@dataclass(frozen=True)
class FontFace:
    """A caller-enumerated font; no family-name or system-font lookup is allowed."""

    face_id: str
    path: Path
    authorized_root: Path
    point_size: int
    index: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.face_id, str) or not self.face_id or len(self.face_id) > 128:
            raise ValueError("font face id must be a bounded non-empty string")
        if not self.path.is_absolute() or not self.authorized_root.is_absolute():
            raise ValueError("font path and authorized root must be explicit absolute paths")
        if not isinstance(self.point_size, int) or not 1 <= self.point_size <= 1024:
            raise ValueError("font point size is outside the bounded range")
        if not isinstance(self.index, int) or self.index < 0:
            raise ValueError("font index is invalid")


@dataclass(frozen=True)
class FontMatch:
    face_id: str | None
    keep_editable_text: bool
    fallback: str | None
    score: float


def _absolute(path: Path) -> Path:
    return Path(os.path.abspath(os.fspath(path)))


def _within(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError:
        return True
    attributes = int(getattr(metadata, "st_file_attributes", 0))
    return path.is_symlink() or stat.S_ISLNK(metadata.st_mode) or bool(
        attributes & int(getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400))
    )


def _authorized_regular_file(path: Path, root: Path) -> Path | None:
    """Verify the complete lexical root-to-target chain without resolving links."""

    lexical_root, lexical_path = _absolute(root), _absolute(path)
    if not _within(lexical_path, lexical_root):
        return None
    try:
        root_state = lexical_root.lstat()
    except OSError:
        return None
    if _is_reparse(lexical_root) or not stat.S_ISDIR(root_state.st_mode):
        return None
    current = lexical_root
    for part in lexical_path.relative_to(lexical_root).parts:
        current = current / part
        try:
            state = current.lstat()
        except OSError:
            return None
        if _is_reparse(current):
            return None
        if current != lexical_path and not stat.S_ISDIR(state.st_mode):
            return None
    try:
        state = lexical_path.stat()
    except OSError:
        return None
    if not stat.S_ISREG(state.st_mode) or state.st_nlink != 1:
        return None
    return lexical_path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _snapshot(path: Path) -> tuple[int, int, int, int, int] | None:
    try:
        state = path.stat()
    except OSError:
        return None
    return (state.st_dev, state.st_ino, state.st_size, state.st_mtime_ns, state.st_nlink)


def _stable_hash(path: Path, root: Path) -> tuple[Path, tuple[int, int, int, int, int], str] | None:
    checked = _authorized_regular_file(path, root)
    if checked is None:
        return None
    before = _snapshot(checked)
    if before is None:
        return None
    try:
        digest = _sha256_file(checked)
    except OSError:
        return None
    after = _snapshot(checked)
    if after != before or _authorized_regular_file(checked, root) != checked:
        return None
    return checked, before, digest


def _unchanged(path: Path, root: Path, snapshot: tuple[int, int, int, int, int], digest: str) -> bool:
    current = _stable_hash(path, root)
    return current is not None and current[1] == snapshot and current[2] == digest


def render_text_crop(text: str, face: FontFace) -> Image.Image:
    """Render a tight crop from one explicit, currently stable authorized file."""

    if not isinstance(text, str) or not text:
        raise ValueError("text must be non-empty")
    stable = _stable_hash(face.path, face.authorized_root)
    if stable is None:
        raise ValueError("font candidate is outside its authorized stable file boundary")
    path, snapshot, digest = stable
    font = ImageFont.truetype(path, face.point_size, index=face.index)
    bounds = font.getbbox(text)
    if bounds[2] <= bounds[0] or bounds[3] <= bounds[1]:
        raise ValueError("text has no renderable glyph bounds")
    image = Image.new("RGBA", (bounds[2] - bounds[0], bounds[3] - bounds[1]), (0, 0, 0, 0))
    ImageDraw.Draw(image).text((-bounds[0], -bounds[1]), text, font=font, fill=(0, 0, 0, 255))
    if not _unchanged(path, face.authorized_root, snapshot, digest):
        image.close()
        raise ValueError("font changed while being rendered")
    return image


def _outline(score: float = 0.0) -> FontMatch:
    return FontMatch(None, False, "outline", score)


def match_font(text: str, crop: Path, candidates: Sequence[FontFace], *, crop_root: Path) -> FontMatch:
    """Keep editable text only after stable, exact local raster comparison.

    All paths are explicitly authorized by the caller. This function neither scans
    font directories nor copies/stores font contents or source paths in its result.
    """

    if not isinstance(text, str) or not text:
        return _outline()
    if not isinstance(candidates, Sequence) or isinstance(candidates, (str, bytes)) or not 1 <= len(candidates) <= 64:
        return _outline()
    crop_state = _stable_hash(crop, crop_root)
    if crop_state is None:
        return _outline()
    crop_path, crop_snapshot, crop_digest = crop_state
    try:
        with Image.open(crop_path) as source:
            reference = source.convert("RGBA")
    except (OSError, ValueError):
        return _outline()
    if not _unchanged(crop_path, crop_root, crop_snapshot, crop_digest):
        reference.close()
        return _outline()
    best_score = 0.0
    try:
        for face in candidates:
            if not isinstance(face, FontFace):
                return _outline()
            try:
                candidate = render_text_crop(text, face)
            except (OSError, ValueError):
                continue
            try:
                if candidate.size != reference.size:
                    score = 0.0
                else:
                    difference = ImageChops.difference(reference, candidate)
                    changed = sum(1 for pixel in difference.get_flattened_data() if pixel != (0, 0, 0, 0))
                    difference.close()
                    score = 1.0 - changed / (reference.width * reference.height)
                    if changed == 0 and _unchanged(crop_path, crop_root, crop_snapshot, crop_digest):
                        return FontMatch(face.face_id, True, None, 1.0)
                best_score = max(best_score, score)
            finally:
                candidate.close()
        return _outline(best_score)
    finally:
        reference.close()
