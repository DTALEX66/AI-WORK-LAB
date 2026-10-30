# SPDX-License-Identifier: MIT
"""Pinned, explicit and bounded deterministic SVG rendering."""
from __future__ import annotations

import hashlib
import io
import json
import math
import os
import re
import stat
import struct
import subprocess
import tempfile
import warnings
import zlib
from copy import deepcopy
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO, Iterator

from PIL import Image, ImageCms, UnidentifiedImageError

from .contracts import ContractError, validate_run_contract
from .runtime_roots import RUNTIME_PARENT as _CANONICAL_RUNTIME_ROOT
from .svg_safety import MAX_CANVAS_PIXELS, UnsafeSVGError, sanitize_svg

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_REGISTRY_PATH = _PROJECT_ROOT / "design-lab" / "config" / "reconstruction-tools.json"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_TRUSTED_REGISTRY_SHA256 = "99c00e1d0be93ed28184f05aed2f11fa66c775a01532d99264a91f07a5705142"
_PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"
_QUALIFIED_METRIC_MAX_PIXELS = 4_194_304
_QUALIFIED_METRIC_MAX_BYTES = 67_108_864
_METRIC_BUDGET_VERSION = "c4-metric-memory-v1"
_MAX_PNG_CHUNK_BYTES = 64 * 1024 * 1024
_MAX_PNG_METADATA_BYTES = 8 * 1024 * 1024
_MAX_ICC_PROFILE_BYTES = 4 * 1024 * 1024
_PNG_CRITICAL_CHUNKS = frozenset({b"IHDR", b"PLTE", b"IDAT", b"IEND"})
_PNG_ANCILLARY_CHUNKS = frozenset({b"cHRM", b"gAMA", b"iCCP", b"sRGB", b"pHYs"})
_PNG_COLOR_SPACE_CHUNKS = frozenset({b"cHRM", b"gAMA", b"iCCP", b"sRGB"})
_SRGB_CHROMATICITIES = (31270, 32900, 64000, 33000, 30000, 60000, 15000, 6000)


class RenderError(RuntimeError):
    """A render request would weaken the pinned renderer contract."""


@dataclass(frozen=True)
class RenderProfile:
    """The sole versioned owner of every deterministic comparison parameter."""

    profile_id: str
    width: int
    height: int
    color_space: str
    rgba_background: tuple[int, int, int, int]
    renderer_id: str
    renderer_version: str
    renderer_sha256: str
    renderer_binary: Path | None
    pixelmatch_version: str
    pixelmatch_algorithm: str
    pixel_threshold: float
    anti_alias_detection: bool
    match_minimum: float
    ssim_minimum: float
    metric_max_pixels: int
    metric_max_bytes: int
    metric_budget_version: str
    mae_limit_version: str
    mae_limit: float | None
    edge_metric: str
    edge_normalization: int
    dense_connectivity: int
    dense_bbox_exclusive_limit: int
    dense_density_minimum: float
    dense_window_size: int
    registry_sha256: str


@dataclass(frozen=True)
class RenderResult:
    """Read-back evidence for one successful deterministic render."""

    output_path: Path
    output_sha256: str
    width: int
    height: int
    profile_id: str
    renderer_id: str
    renderer_version: str
    renderer_sha256: str
    registry_digest: str
    metric_max_pixels: int
    metric_max_bytes: int
    metric_budget_version: str
    output_icc_profile_id: str
    output_icc_profile_sha256: str | None
    output_raw_icc_sha256: str | None
    output_canonical_icc_sha256: str | None
    output_icc_canonicalization: str
    input_bindings: tuple["ArtifactBindingEvidence", ...]
    lifecycle_status: str = "RENDERED"


@dataclass(frozen=True)
class _WriteConstraints:
    """Immutable result of revalidating one C1-authorized output target."""

    contract: dict[str, Any]
    target: Path
    run_root: Path
    run_id: str
    target_artifact: dict[str, Any]


@dataclass(frozen=True)
class _FileIdentity:
    device: int
    inode: int
    size: int
    modified_ns: int


@dataclass(frozen=True)
class _InputBinding:
    path: Path
    identity: _FileIdentity
    sha256: str
    role: str = ""
    producer: str = ""
    icc_profile_id: str = "not-applicable"
    icc_profile_sha256: str | None = None
    raw_icc_sha256: str | None = None
    canonical_icc_sha256: str | None = None
    icc_canonicalization: str = "none"


@dataclass(frozen=True)
class ArtifactBindingEvidence:
    path: Path
    role: str
    producer: str
    sha256: str
    icc_profile_id: str
    icc_profile_sha256: str | None
    raw_icc_sha256: str | None
    canonical_icc_sha256: str | None
    icc_canonicalization: str


@dataclass(frozen=True)
class _IccProfileEvidence:
    profile_id: str
    raw_sha256: str | None
    canonical_sha256: str | None
    canonicalization: str


@dataclass(frozen=True)
class _PngHeader:
    dimensions: tuple[int, int]
    bit_depth: int
    color_type: int
    row_bytes: int


def _validate_png_keyword(keyword: bytes) -> None:
    if not 1 <= len(keyword) <= 79:
        raise RenderError("PNG iCCP keyword must contain 1..79 Latin-1 bytes")
    if not all(32 <= value <= 126 or 161 <= value <= 255 for value in keyword):
        raise RenderError("PNG iCCP keyword contains an invalid Latin-1 character")
    if keyword[0] == 32 or keyword[-1] == 32 or b"  " in keyword:
        raise RenderError(
            "PNG iCCP keyword cannot have leading, trailing or consecutive spaces"
        )


class _IccpPreflight:
    """Streaming validation for one bounded PNG iCCP payload."""

    def __init__(self) -> None:
        self.keyword = bytearray()
        self.phase = "keyword"
        self.decompressor = zlib.decompressobj()
        self.decoded_bytes = 0
        self.profile_bytes = bytearray()

    def _feed_compressed(self, payload: bytes) -> None:
        pending = payload
        try:
            while pending:
                pending_size = len(pending)
                output_limit = min(
                    1 << 20,
                    max(1, _MAX_ICC_PROFILE_BYTES - self.decoded_bytes + 1),
                )
                decoded = self.decompressor.decompress(pending, output_limit)
                pending = self.decompressor.unconsumed_tail
                self.decoded_bytes += len(decoded)
                if self.decoded_bytes > _MAX_ICC_PROFILE_BYTES:
                    raise RenderError(
                        f"PNG iCCP profile exceeds {_MAX_ICC_PROFILE_BYTES} decoded bytes"
                    )
                self.profile_bytes.extend(decoded)
                if self.decompressor.unused_data:
                    raise RenderError(
                        "PNG iCCP contains trailing or concatenated zlib stream data"
                    )
                if len(pending) == pending_size and not decoded:
                    raise RenderError("PNG iCCP zlib stream made no bounded progress")
        except zlib.error as exc:
            raise RenderError(f"PNG iCCP zlib stream is invalid: {exc}") from None

    def feed(self, payload: bytes) -> None:
        cursor = 0
        if self.phase == "keyword":
            separator = payload.find(b"\x00")
            if separator < 0:
                self.keyword.extend(payload)
                if len(self.keyword) > 79:
                    raise RenderError("PNG iCCP keyword exceeds 79 bytes")
                return
            self.keyword.extend(payload[:separator])
            _validate_png_keyword(bytes(self.keyword))
            self.phase = "method"
            cursor = separator + 1
        if self.phase == "method":
            if cursor >= len(payload):
                return
            if payload[cursor] != 0:
                raise RenderError("PNG iCCP compression method must be zero")
            self.phase = "compressed"
            cursor += 1
        if cursor < len(payload):
            self._feed_compressed(payload[cursor:])

    def finish(self) -> bytes:
        if self.phase != "compressed":
            raise RenderError("PNG iCCP keyword/compression method is truncated")
        try:
            while True:
                output_limit = min(
                    1 << 20,
                    max(1, _MAX_ICC_PROFILE_BYTES - self.decoded_bytes + 1),
                )
                decoded = self.decompressor.decompress(b"", output_limit)
                if not decoded:
                    break
                self.decoded_bytes += len(decoded)
                if self.decoded_bytes > _MAX_ICC_PROFILE_BYTES:
                    raise RenderError(
                        f"PNG iCCP profile exceeds {_MAX_ICC_PROFILE_BYTES} decoded bytes"
                    )
                self.profile_bytes.extend(decoded)
        except zlib.error as exc:
            raise RenderError(f"PNG iCCP zlib stream is invalid: {exc}") from None
        if not self.decompressor.eof:
            raise RenderError("PNG iCCP zlib stream is truncated")
        if self.decompressor.unused_data or self.decompressor.unconsumed_tail:
            raise RenderError(
                "PNG iCCP contains trailing or concatenated zlib stream data"
            )
        if self.decoded_bytes == 0:
            raise RenderError("PNG iCCP profile decompresses to an empty payload")
        return bytes(self.profile_bytes)


def _renderer_key() -> str:
    """Select the pinned resvg renderer registry entry for this platform."""
    return "resvgWindows" if os.name == "nt" else "resvgLinux"


def _load_registry() -> tuple[dict[str, Any], str]:
    try:
        payload = _REGISTRY_PATH.read_bytes()
        registry = json.loads(payload.decode("utf-8", errors="strict"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RenderError(f"cannot read reconstruction tool registry: {exc}") from None
    digest = hashlib.sha256(payload).hexdigest()
    if digest != _TRUSTED_REGISTRY_SHA256:
        raise RenderError(
            "reconstruction tool registry digest does not match the trusted build anchor"
        )
    if registry.get("schemaVersion") != "design-lab/reconstruction-tools/v1":
        raise RenderError("unsupported reconstruction tool registry schema")
    _approved_icc_profiles(registry)
    return registry, digest


def _approved_icc_profiles(registry: dict[str, Any]) -> dict[tuple[int, str], dict[str, Any]]:
    profiles = registry.get("approvedIccProfiles")
    if not isinstance(profiles, list) or len(profiles) != 1:
        raise RenderError("trusted registry must declare one approved ICC profile")
    profile = profiles[0]
    expected = {
        "id": "canonical-srgb-pillow-12.3.0-lcms-2.19",
        "source": "Pillow ImageCms.createProfile('sRGB')",
        "generator": "Pillow.ImageCms.ImageCmsProfile.tobytes/v1 then canonicalize",
        "pillowVersion": "12.3.0",
        "lcmsVersion": "2.19",
        "byteLength": 588,
        "sha256": "215d9fadbfc938862a82f2633b51fee128b58767f7d7ac55d32cb7e00031bb0d",
        "colorSpace": "sRGB IEC61966-2.1",
        "canonicalization": "zero-icc-header-creation-date-v1",
    }
    if not isinstance(profile, dict) or profile != expected:
        raise RenderError("trusted registry approved ICC profile declaration is invalid")
    return {(expected["byteLength"], expected["sha256"]): profile}


def _validate_icc_profile(
    payload: bytes,
    approved_profiles: dict[tuple[int, str], dict[str, Any]],
) -> _IccProfileEvidence:
    if len(payload) < 132:
        raise RenderError("PNG ICC profile is shorter than its header/tag table")
    declared_size = struct.unpack(">I", payload[:4])[0]
    if declared_size != len(payload):
        raise RenderError("PNG ICC declared size does not equal decoded byte length")
    if payload[36:40] != b"acsp":
        raise RenderError("PNG ICC profile is missing the acsp signature")
    if payload[12:16] != b"mntr":
        raise RenderError("PNG ICC device class is not the approved display profile class")
    if payload[16:20] != b"RGB ":
        raise RenderError("PNG ICC data color space must be RGB")
    if payload[20:24] != b"XYZ ":
        raise RenderError("PNG ICC profile connection space must be XYZ")
    creation_date = payload[24:36]
    if creation_date != bytes(12):
        try:
            datetime(*struct.unpack(">6H", creation_date))
        except (ValueError, OverflowError):
            raise RenderError("PNG ICC header creationDate is invalid") from None
    raw_digest = hashlib.sha256(payload).hexdigest()
    canonical = bytearray(payload)
    canonical[24:36] = bytes(12)
    canonical_digest = hashlib.sha256(canonical).hexdigest()
    approved = approved_profiles.get((len(payload), canonical_digest))
    if approved is None:
        raise RenderError("PNG ICC canonical digest is not in the approved registry")
    tag_count = struct.unpack(">I", payload[128:132])[0]
    if tag_count > 128:
        raise RenderError("PNG ICC approved profile tag count exceeds 128")
    if tag_count > (len(payload) - 132) // 12:
        raise RenderError("PNG ICC tag table exceeds decoded profile bounds")
    table_end = 132 + tag_count * 12
    ranges: list[tuple[int, int]] = []
    signatures: set[bytes] = set()
    for index in range(tag_count):
        entry = 132 + index * 12
        signature = payload[entry : entry + 4]
        offset, size = struct.unpack(">II", payload[entry + 4 : entry + 12])
        if not all(32 <= value <= 126 for value in signature):
            raise RenderError("PNG ICC tag signature is not four printable bytes")
        if signature in signatures:
            raise RenderError("PNG ICC tag signatures must be unique")
        signatures.add(signature)
        if offset < table_end or offset % 4 or size < 8 or offset + size > len(payload):
            raise RenderError("PNG ICC tag table contains an invalid bounds entry")
        ranges.append((offset, offset + size))
    ranges.sort()
    previous: tuple[int, int] | None = None
    for current in ranges:
        if previous is not None and current != previous and current[0] < previous[1]:
            raise RenderError("PNG ICC tag payload ranges overlap")
        if previous is None or current != previous:
            previous = current
    return _IccProfileEvidence(
        profile_id=approved["id"],
        raw_sha256=raw_digest,
        canonical_sha256=canonical_digest,
        canonicalization=approved["canonicalization"],
    )


def _require_number(value: Any, field: str, *, minimum: float, maximum: float) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise RenderError(f"{field} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not minimum <= number <= maximum:
        raise RenderError(f"{field} is outside its finite allowed range")
    return number


def _require_integer(value: Any, field: str, *, minimum: int, maximum: int) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise RenderError(f"{field} must be an integer")
    if not minimum <= value <= maximum:
        raise RenderError(f"{field} is outside its allowed range")
    return value


def load_render_profile(
    width: int,
    height: int,
    renderer_binary: Path | None = None,
    *,
    rgba_background: tuple[int, int, int, int] | None = None,
) -> RenderProfile:
    """Load the one repository-owned profile for explicit canvas dimensions."""

    if isinstance(width, bool) or isinstance(height, bool) or not isinstance(width, int) or not isinstance(height, int):
        raise RenderError("render profile dimensions must be integers")
    if width <= 0 or height <= 0:
        raise RenderError("render profile dimensions must be positive")
    if renderer_binary is not None and not isinstance(renderer_binary, Path):
        raise RenderError("renderer_binary must be a pathlib.Path or None")
    binary = None if renderer_binary is None else Path(os.path.abspath(renderer_binary))
    registry, registry_sha256 = _load_registry()
    fixed = registry.get("renderProfile", {})
    renderer = registry.get("renderers", {}).get(_renderer_key(), {})
    pixelmatch = registry.get("metrics", {}).get("pixelmatch", {})
    mae = fixed.get("maeLimit", {})
    edge = fixed.get("edgeMetric", {})
    dense = fixed.get("denseRegion", {})
    background = fixed.get("rgbaBackground") if rgba_background is None else list(rgba_background)
    if not (
        isinstance(background, list)
        and len(background) == 4
        and all(isinstance(channel, int) and not isinstance(channel, bool) and 0 <= channel <= 255 for channel in background)
    ):
        raise RenderError("render profile RGBA background is invalid")
    sha256 = renderer.get("executableSha256")
    if not isinstance(sha256, str) or not _SHA256.fullmatch(sha256):
        raise RenderError("renderer executable SHA-256 is invalid")
    profile = RenderProfile(
        profile_id=fixed.get("id"),
        width=width,
        height=height,
        color_space=fixed.get("colorSpace"),
        rgba_background=tuple(background),
        renderer_id=renderer.get("repository"),
        renderer_version=renderer.get("version"),
        renderer_sha256=sha256,
        renderer_binary=binary,
        pixelmatch_version=pixelmatch.get("version"),
        pixelmatch_algorithm=pixelmatch.get("algorithm"),
        pixel_threshold=_require_number(fixed.get("pixelThreshold"), "pixelThreshold", minimum=0, maximum=1),
        anti_alias_detection=fixed.get("antiAliasDetection"),
        match_minimum=_require_number(fixed.get("matchMinimum"), "matchMinimum", minimum=0, maximum=1),
        ssim_minimum=_require_number(fixed.get("ssimMinimum"), "ssimMinimum", minimum=0, maximum=1),
        metric_max_pixels=_require_integer(fixed.get("metricMaxPixels"), "metricMaxPixels", minimum=1, maximum=MAX_CANVAS_PIXELS),
        metric_max_bytes=_require_integer(fixed.get("metricMaxBytes"), "metricMaxBytes", minimum=1, maximum=1 << 30),
        metric_budget_version=fixed.get("metricBudgetVersion"),
        mae_limit_version=mae.get("version"),
        mae_limit=None if mae.get("value") is None else _require_number(mae.get("value"), "maeLimit.value", minimum=0, maximum=1),
        edge_metric=edge.get("id"),
        edge_normalization=edge.get("normalization"),
        dense_connectivity=dense.get("connectivity"),
        dense_bbox_exclusive_limit=dense.get("bboxExclusiveLimit"),
        dense_density_minimum=_require_number(dense.get("densityMinimum"), "denseRegion.densityMinimum", minimum=0, maximum=1),
        dense_window_size=dense.get("windowSize"),
        registry_sha256=registry_sha256,
    )
    _validate_profile(profile)
    return profile


def _validate_profile(profile: RenderProfile) -> None:
    if not isinstance(profile, RenderProfile):
        raise RenderError("profile must be a RenderProfile")
    if (
        isinstance(profile.width, bool)
        or isinstance(profile.height, bool)
        or not isinstance(profile.width, int)
        or not isinstance(profile.height, int)
    ):
        raise RenderError("render profile dimensions must be strict integers")
    if profile.width <= 0 or profile.height <= 0:
        raise RenderError("render profile dimensions must be positive")
    if profile.renderer_binary is not None and not isinstance(profile.renderer_binary, Path):
        raise RenderError("renderer_binary must be a pathlib.Path or None")
    if profile.width * profile.height > _QUALIFIED_METRIC_MAX_PIXELS:
        raise RenderError(
            f"render profile exceeds the C4 qualified operational metric pixel ceiling {_QUALIFIED_METRIC_MAX_PIXELS}"
        )
    registry, registry_sha256 = _load_registry()
    fixed = registry["renderProfile"]
    renderer = registry["renderers"][_renderer_key()]
    pixelmatch = registry["metrics"]["pixelmatch"]
    mae = fixed["maeLimit"]
    edge = fixed["edgeMetric"]
    dense = fixed["denseRegion"]
    expected = {
        "profile_id": fixed["id"],
        "color_space": fixed["colorSpace"],
        "renderer_id": renderer["repository"],
        "renderer_version": renderer["version"],
        "renderer_sha256": renderer["executableSha256"],
        "pixelmatch_version": pixelmatch["version"],
        "pixelmatch_algorithm": pixelmatch["algorithm"],
        "pixel_threshold": fixed["pixelThreshold"],
        "anti_alias_detection": fixed["antiAliasDetection"],
        "match_minimum": fixed["matchMinimum"],
        "ssim_minimum": fixed["ssimMinimum"],
        "metric_max_pixels": fixed["metricMaxPixels"],
        "metric_max_bytes": fixed["metricMaxBytes"],
        "metric_budget_version": fixed["metricBudgetVersion"],
        "mae_limit_version": mae["version"],
        "mae_limit": mae["value"],
        "edge_metric": edge["id"],
        "edge_normalization": edge["normalization"],
        "dense_connectivity": dense["connectivity"],
        "dense_bbox_exclusive_limit": dense["bboxExclusiveLimit"],
        "dense_density_minimum": dense["densityMinimum"],
        "dense_window_size": dense["windowSize"],
        "registry_sha256": registry_sha256,
    }
    for field, value in expected.items():
        if getattr(profile, field) != value:
            raise RenderError(f"render profile mismatch: {field}")
    if (
        profile.metric_max_pixels != _QUALIFIED_METRIC_MAX_PIXELS
        or profile.metric_max_bytes != _QUALIFIED_METRIC_MAX_BYTES
        or profile.metric_budget_version != _METRIC_BUDGET_VERSION
    ):
        raise RenderError("render profile metric resource budget is not qualified")
    if (
        not isinstance(profile.rgba_background, tuple)
        or len(profile.rgba_background) != 4
        or not all(
            isinstance(channel, int)
            and not isinstance(channel, bool)
            and 0 <= channel <= 255
            for channel in profile.rgba_background
        )
        or profile.rgba_background[3] != 255
    ):
        raise RenderError("render profile mismatch: rgba_background must be opaque RGBA")


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1 << 20), b""):
                digest.update(chunk)
    except OSError as exc:
        raise RenderError(f"cannot hash renderer binary: {exc}") from None
    return digest.hexdigest()


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise RenderError(f"cannot inspect path safely: {path}: {exc}") from None
    return path.is_symlink() or bool(getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT)


def _assert_plain_existing_components(path: Path) -> None:
    current = Path(path.anchor)
    parts = path.parts[1:] if path.anchor else path.parts
    for part in parts:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        if _is_reparse(current):
            raise RenderError(f"path crosses a symlink/reparse boundary: {current}")


def _validated_write_constraints(
    run_contract: dict | None,
    target: Path,
    profile: RenderProfile,
    *,
    allowed_kinds: frozenset[str],
    operation: str,
    required_suffix: str = ".png",
    artifact_role: str,
    artifact_producer: str,
) -> _WriteConstraints:
    if run_contract is None:
        raise RenderError("a validated run contract is required before any public write")
    try:
        snapshot = deepcopy(run_contract)
    except Exception as exc:
        raise RenderError(f"run contract cannot be snapshotted safely: {exc}") from None
    try:
        validate_run_contract(snapshot)
    except ContractError as exc:
        raise RenderError(f"run contract validation failed: {exc}") from None
    if snapshot["lifecycle"]["state"] not in {"authorized", "running"}:
        raise RenderError("run contract lifecycle does not permit C4 writes")
    if operation not in snapshot["requestedOperations"]:
        raise RenderError(f"run contract does not authorize the {operation!r} operation")
    if snapshot["registries"]["toolRegistry"] != "design-lab/config/reconstruction-tools.json":
        raise RenderError("run contract is not bound to the C4 tool registry")
    canvas = snapshot["canvasPolicy"]
    if (canvas["width"], canvas["height"], canvas["colorSpace"]) != (
        profile.width,
        profile.height,
        "srgb",
    ):
        raise RenderError("run contract canvas dimensions/profile do not match RenderProfile")

    lexical_target = Path(os.path.abspath(os.fspath(target)))
    try:
        target_relative = lexical_target.relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        raise RenderError("write target is outside the project and cannot be authorized") from None
    matching = [
        artifact
        for artifact in snapshot["artifacts"]
        if artifact["path"] == target_relative
    ]
    if (
        len(matching) != 1
        or matching[0]["kind"] not in allowed_kinds
        or matching[0].get("role") != artifact_role
        or matching[0].get("producer") != artifact_producer
    ):
        expected_kinds = ",".join(sorted(allowed_kinds))
        raise RenderError(
            "write target is not an exact authorized artifact declaration with kind "
            f"{expected_kinds}"
        )
    if lexical_target.suffix.lower() != required_suffix:
        raise RenderError(f"write target must use the exact {required_suffix} extension")
    runtime_relative = snapshot["roots"]["runtime"].rstrip("/")
    runtime_root = _PROJECT_ROOT.joinpath(*runtime_relative.split("/"))
    try:
        lexical_target.relative_to(runtime_root)
    except ValueError:
        raise RenderError("C4 writes must stay below the exact contract runtime root") from None
    if runtime_root != _CANONICAL_RUNTIME_ROOT / snapshot["runId"]:
        raise RenderError("run contract runtime root/runId binding is not canonical")
    return _WriteConstraints(
        contract=snapshot,
        target=lexical_target,
        run_root=runtime_root,
        run_id=snapshot["runId"],
        target_artifact=matching[0],
    )


def _revalidate_write_constraints(
    constraints: _WriteConstraints,
    input_bindings: tuple[_InputBinding, ...] = (),
) -> None:
    _load_registry()
    try:
        validate_run_contract(constraints.contract)
    except ContractError as exc:
        raise RenderError(f"run contract expired or became invalid before commit: {exc}") from None
    if constraints.contract["lifecycle"]["state"] not in {"authorized", "running"}:
        raise RenderError("run contract lifecycle no longer permits C4 writes")
    for binding in input_bindings:
        _verify_input_binding(binding)


def _png_prefix_header(prefix: bytes) -> _PngHeader:
    if len(prefix) != 33 or prefix[:8] != _PNG_SIGNATURE:
        raise RenderError("PNG signature/IHDR header is missing or truncated")
    length, kind = struct.unpack(">I4s", prefix[8:16])
    if length != 13 or kind != b"IHDR":
        raise RenderError("PNG must begin with one exact 13-byte IHDR chunk")
    payload = prefix[16:29]
    expected_crc = struct.unpack(">I", prefix[29:33])[0]
    if zlib.crc32(kind + payload) & 0xFFFFFFFF != expected_crc:
        raise RenderError("PNG IHDR CRC mismatch")
    width, height, bit_depth, color_type, compression, filtering, interlace = struct.unpack(
        ">IIBBBBB", payload
    )
    if width <= 0 or height <= 0:
        raise RenderError("PNG header contains invalid dimensions")
    if width * height > _QUALIFIED_METRIC_MAX_PIXELS:
        raise RenderError(
            f"PNG exceeds the C4 qualified operational metric pixel ceiling {_QUALIFIED_METRIC_MAX_PIXELS}"
        )
    legal_depths = {
        0: {1, 2, 4, 8, 16},
        2: {8, 16},
        3: {1, 2, 4, 8},
        4: {8, 16},
        6: {8, 16},
    }
    if color_type not in legal_depths or bit_depth not in legal_depths[color_type]:
        raise RenderError("PNG IHDR bit depth/color type combination is invalid")
    if compression != 0 or filtering != 0 or interlace != 0:
        raise RenderError("PNG IHDR contains unsupported compression/filter/interlace")
    samples = {0: 1, 2: 3, 3: 1, 4: 2, 6: 4}[color_type]
    return _PngHeader(
        dimensions=(width, height),
        bit_depth=bit_depth,
        color_type=color_type,
        row_bytes=(width * samples * bit_depth + 7) // 8,
    )


def _png_prefix_dimensions(prefix: bytes) -> tuple[int, int]:
    return _png_prefix_header(prefix).dimensions


def _probe_png_dimensions(path: Path) -> tuple[int, int]:
    """Read only signature/IHDR after registry trust is established."""

    if not isinstance(path, Path):
        raise RenderError("PNG path must be a pathlib.Path")
    source = Path(os.path.abspath(os.fspath(path)))
    _assert_plain_existing_components(source)
    try:
        with source.open("rb") as stream:
            before = os.fstat(stream.fileno())
            if not stat.S_ISREG(before.st_mode):
                raise RenderError(f"PNG input is not a regular file: {source}")
            if before.st_size > _QUALIFIED_METRIC_MAX_BYTES:
                raise RenderError(
                    f"PNG exceeds the C4 qualified metric file-size limit {_QUALIFIED_METRIC_MAX_BYTES}"
                )
            prefix = _read_exact(stream, 33, field="signature/IHDR header")
            dimensions = _png_prefix_dimensions(prefix)
            after = os.fstat(stream.fileno())
        if _identity(before) != _identity(after) or _identity(after) != _identity(source.stat()):
            raise RenderError("PNG identity changed during raw IHDR probe")
        return dimensions
    except RenderError:
        raise
    except OSError as exc:
        raise RenderError(f"cannot read PNG IHDR: {source}: {exc}") from None


def _read_exact(stream: BinaryIO, length: int, *, field: str) -> bytes:
    payload = stream.read(length)
    if len(payload) != length:
        raise RenderError(f"PNG {field} is truncated")
    return payload


def _stream_png_preflight(
    stream: BinaryIO,
    file_size: int,
    approved_icc_profiles: dict[tuple[int, str], dict[str, Any]],
) -> tuple[_PngHeader, str, _IccProfileEvidence]:
    if file_size > _QUALIFIED_METRIC_MAX_BYTES:
        raise RenderError(
            f"PNG exceeds the C4 qualified metric file-size limit {_QUALIFIED_METRIC_MAX_BYTES}"
        )
    digest = hashlib.sha256()
    signature = _read_exact(stream, 8, field="signature")
    digest.update(signature)
    if signature != _PNG_SIGNATURE:
        raise RenderError("PNG signature is invalid")
    metadata_bytes = 0
    chunk_index = 0
    png_header: _PngHeader | None = None
    found_idat = False
    idat_ended = False
    found_iend = False
    found_plte = False
    seen_ancillary: set[bytes] = set()
    decompressor: zlib.Decompress | None = None
    decoded_bytes = 0
    scanline_offset = 0
    expected_decoded_bytes = 0
    scanline_bytes = 0
    active_iccp: _IccpPreflight | None = None
    icc_evidence = _IccProfileEvidence(
        profile_id="implicit-sRGB-none",
        raw_sha256=None,
        canonical_sha256=None,
        canonicalization="none",
    )
    consumed = 8

    def consume_scanlines(payload: bytes) -> None:
        nonlocal decoded_bytes, scanline_offset
        if decoded_bytes + len(payload) > expected_decoded_bytes:
            raise RenderError("PNG deflate output exceeds exact scanline length")
        cursor = 0
        while cursor < len(payload):
            if scanline_offset == 0 and payload[cursor] > 4:
                raise RenderError("PNG scanline contains an invalid filter byte")
            take = min(scanline_bytes - scanline_offset, len(payload) - cursor)
            scanline_offset = (scanline_offset + take) % scanline_bytes
            cursor += take
        decoded_bytes += len(payload)

    def feed_idat(payload: bytes) -> None:
        if decompressor is None:
            raise RenderError("PNG IDAT appeared before a valid IHDR")
        pending = payload
        try:
            while pending:
                pending_size = len(pending)
                output_limit = min(
                    1 << 20, max(1, expected_decoded_bytes - decoded_bytes + 1)
                )
                decoded = decompressor.decompress(pending, output_limit)
                pending = decompressor.unconsumed_tail
                consume_scanlines(decoded)
                if decompressor.unused_data:
                    raise RenderError("PNG IDAT contains trailing deflate stream data")
                if len(pending) == pending_size and not decoded:
                    raise RenderError("PNG IDAT deflate stream made no bounded progress")
        except zlib.error as exc:
            raise RenderError(f"PNG IDAT zlib/deflate stream is invalid: {exc}") from None

    def finish_idat() -> None:
        if decompressor is None:
            raise RenderError("PNG is missing its IDAT deflate stream")
        try:
            while True:
                output_limit = min(
                    1 << 20, max(1, expected_decoded_bytes - decoded_bytes + 1)
                )
                decoded = decompressor.decompress(b"", output_limit)
                if not decoded:
                    break
                consume_scanlines(decoded)
        except zlib.error as exc:
            raise RenderError(f"PNG IDAT zlib/deflate stream is invalid: {exc}") from None
        if not decompressor.eof:
            raise RenderError("PNG IDAT deflate stream is truncated")
        if decompressor.unused_data or decompressor.unconsumed_tail:
            raise RenderError("PNG IDAT contains trailing deflate stream data")
        if decoded_bytes != expected_decoded_bytes or scanline_offset != 0:
            raise RenderError("PNG decompressed scanline length is not exact")

    while consumed < file_size:
        header = _read_exact(stream, 8, field="chunk header")
        digest.update(header)
        consumed += 8
        length, kind = struct.unpack(">I4s", header)
        if not all(
            ord("A") <= value <= ord("Z") or ord("a") <= value <= ord("z")
            for value in kind
        ):
            raise RenderError("PNG chunk type must contain exactly four ASCII letters")
        if not ord("A") <= kind[2] <= ord("Z"):
            raise RenderError("PNG chunk type reserved bit must be uppercase")
        if kind[0] <= ord("Z") and kind not in _PNG_CRITICAL_CHUNKS:
            raise RenderError(
                f"PNG contains unknown critical chunk {kind.decode('ascii')}"
            )
        if kind[0] >= ord("a") and kind not in _PNG_ANCILLARY_CHUNKS:
            raise RenderError(
                f"PNG contains unknown ancillary chunk {kind.decode('ascii')}"
            )
        if length > _MAX_PNG_CHUNK_BYTES:
            raise RenderError("PNG chunk exceeds the bounded chunk policy")
        if consumed + length + 4 > file_size:
            raise RenderError("PNG chunk payload is truncated")
        if chunk_index == 0 and (kind != b"IHDR" or length != 13):
            raise RenderError("PNG must begin with one exact 13-byte IHDR chunk")
        if chunk_index > 0 and kind == b"IHDR":
            raise RenderError("PNG contains a duplicate IHDR chunk")
        if found_iend:
            raise RenderError("PNG contains a chunk after IEND")
        if kind == b"PLTE":
            if found_plte:
                raise RenderError("PNG contains a duplicate PLTE chunk")
            if found_idat:
                raise RenderError("PNG PLTE must appear before IDAT")
            if length == 0 or length > 768 or length % 3:
                raise RenderError("PNG PLTE length is invalid")
        if kind in _PNG_ANCILLARY_CHUNKS:
            if kind in seen_ancillary:
                raise RenderError(
                    f"PNG contains duplicate {kind.decode('ascii')} ancillary chunk"
                )
            if found_idat:
                raise RenderError(
                    f"PNG {kind.decode('ascii')} ancillary chunk must precede IDAT"
                )
            if kind in _PNG_COLOR_SPACE_CHUNKS and found_plte:
                raise RenderError(
                    f"PNG {kind.decode('ascii')} color-space chunk must appear before PLTE"
                )
            if kind == b"iCCP" and b"sRGB" in seen_ancillary:
                raise RenderError("PNG iCCP and sRGB chunks are mutually exclusive")
            if kind == b"sRGB" and b"iCCP" in seen_ancillary:
                raise RenderError("PNG iCCP and sRGB chunks are mutually exclusive")
            if kind != b"iCCP":
                required_length = {
                    b"cHRM": 32,
                    b"gAMA": 4,
                    b"sRGB": 1,
                    b"pHYs": 9,
                }[kind]
                if length != required_length:
                    raise RenderError(
                        f"PNG {kind.decode('ascii')} length is invalid"
                    )
            seen_ancillary.add(kind)
        active_iccp = _IccpPreflight() if kind == b"iCCP" else None
        if found_idat and kind != b"IDAT" and not idat_ended:
            finish_idat()
            idat_ended = True
        crc = zlib.crc32(kind)
        captured = bytearray()
        remaining = length
        while remaining:
            block = _read_exact(
                stream, min(remaining, 1 << 20), field=f"{kind!r} chunk payload"
            )
            digest.update(block)
            crc = zlib.crc32(block, crc)
            if kind in {b"IHDR", b"PLTE"} or (
                kind in _PNG_ANCILLARY_CHUNKS and kind != b"iCCP"
            ):
                captured.extend(block)
            if kind == b"IDAT":
                feed_idat(block)
            if active_iccp is not None:
                active_iccp.feed(block)
            remaining -= len(block)
        crc_bytes = _read_exact(stream, 4, field=f"{kind!r} chunk CRC")
        digest.update(crc_bytes)
        consumed += length + 4
        expected_crc = struct.unpack(">I", crc_bytes)[0]
        if crc & 0xFFFFFFFF != expected_crc:
            raise RenderError(f"PNG {kind.decode('ascii', errors='replace')} chunk CRC mismatch")
        if active_iccp is not None:
            icc_evidence = _validate_icc_profile(
                active_iccp.finish(), approved_icc_profiles
            )
        if kind == b"IHDR":
            png_header = _png_prefix_header(signature + header + captured + crc_bytes)
            scanline_bytes = png_header.row_bytes + 1
            expected_decoded_bytes = scanline_bytes * png_header.dimensions[1]
            decompressor = zlib.decompressobj()
        elif kind == b"PLTE":
            if png_header is None:
                raise RenderError("PNG PLTE appeared before IHDR")
            entries = length // 3
            if png_header.color_type in {0, 4}:
                raise RenderError(
                    f"PNG color type {png_header.color_type} forbids PLTE"
                )
            if png_header.color_type == 3 and entries > 1 << png_header.bit_depth:
                raise RenderError("PNG indexed PLTE exceeds the bit-depth entry limit")
            if png_header.color_type in {2, 6} and entries > 256:
                raise RenderError("PNG suggested PLTE exceeds 256 entries")
            found_plte = True
        elif kind == b"sRGB":
            if length != 1 or captured[0] > 3:
                raise RenderError("PNG sRGB rendering intent is invalid")
        elif kind == b"gAMA":
            gamma = struct.unpack(">I", captured)[0]
            if gamma == 0:
                raise RenderError("PNG gAMA value must be positive")
            if gamma != 45455:
                raise RenderError("PNG gAMA value is inconsistent with fixed sRGB")
        elif kind == b"cHRM":
            chromaticities = struct.unpack(">8I", captured)
            if chromaticities != _SRGB_CHROMATICITIES:
                raise RenderError("PNG cHRM values are inconsistent with fixed sRGB")
        elif kind == b"pHYs" and (length != 9 or captured[8] not in {0, 1}):
            raise RenderError("PNG pHYs payload is invalid")
        if kind not in {b"IDAT", b"IEND"}:
            metadata_bytes += length
            if metadata_bytes > _MAX_PNG_METADATA_BYTES:
                raise RenderError("PNG metadata exceeds the bounded metadata policy")
        if kind == b"IDAT":
            if png_header is None or found_iend or idat_ended:
                raise RenderError("PNG IDAT chunk is out of order")
            found_idat = True
        if kind == b"IEND":
            if length != 0 or not found_idat:
                raise RenderError("PNG IEND chunk is malformed or precedes IDAT")
            found_iend = True
            break
        chunk_index += 1
    if not found_iend:
        raise RenderError("PNG is missing its final IEND chunk")
    if consumed != file_size or stream.read(1):
        raise RenderError("PNG contains trailing bytes after IEND")
    if png_header is None:
        raise RenderError("PNG is missing IHDR dimensions")
    if png_header.color_type == 3 and not found_plte:
        raise RenderError("PNG indexed color type 3 requires PLTE")
    return png_header, digest.hexdigest(), icc_evidence


def _open_checked_png_header(
    path: Path,
) -> tuple[Image.Image, _InputBinding, BinaryIO]:
    """Bounded raw PNG preflight before Pillow sees any metadata chunk."""

    if not isinstance(path, Path):
        raise RenderError("PNG path must be a pathlib.Path")
    source = Path(os.path.abspath(os.fspath(path)))
    registry, _ = _load_registry()
    approved_icc_profiles = _approved_icc_profiles(registry)
    _assert_plain_existing_components(source)
    stream: BinaryIO | None = None
    try:
        stream = source.open("rb")
        before = _identity(os.fstat(stream.fileno()))
        png_header, png_sha256, icc_evidence = _stream_png_preflight(
            stream, before.size, approved_icc_profiles
        )
        dimensions = png_header.dimensions
        if png_header.bit_depth != 8 or png_header.color_type not in {2, 6}:
            raise RenderError("PNG comparison subset requires 8-bit RGB or RGBA")
        after = _identity(os.fstat(stream.fileno()))
        path_after = _identity(source.stat())
        if before != after or after != path_after:
            raise RenderError("PNG identity changed during bounded snapshot")
        binding = _InputBinding(
            path=source,
            identity=after,
            sha256=png_sha256,
            icc_profile_id=icc_evidence.profile_id,
            icc_profile_sha256=icc_evidence.canonical_sha256,
            raw_icc_sha256=icc_evidence.raw_sha256,
            canonical_icc_sha256=icc_evidence.canonical_sha256,
            icc_canonicalization=icc_evidence.canonicalization,
        )
        stream.seek(0)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", Image.DecompressionBombWarning)
            image = Image.open(stream)
    except Image.DecompressionBombError:
        if stream is not None:
            stream.close()
        raise RenderError(
            f"PNG exceeds the C4 qualified operational metric pixel ceiling {_QUALIFIED_METRIC_MAX_PIXELS}"
        ) from None
    except RenderError:
        if stream is not None:
            stream.close()
        raise
    except (OSError, UnidentifiedImageError) as exc:
        if stream is not None:
            stream.close()
        raise RenderError(f"cannot read PNG header: {source}: {exc}") from None
    except Exception:
        if stream is not None:
            stream.close()
        raise
    try:
        if image.format != "PNG":
            raise RenderError(f"comparison/render output must be PNG: {source}")
        if image.mode not in {"RGB", "RGBA"}:
            raise RenderError(f"PNG must be RGB or RGBA before decode: {source}")
        if image.size != dimensions:
            raise RenderError("Pillow PNG dimensions diverge from raw IHDR preflight")
        embedded = image.info.get("icc_profile")
        raw_has_iccp = icc_evidence.raw_sha256 is not None
        if raw_has_iccp != bool(embedded):
            raise RenderError("Pillow ICC metadata diverges from raw iCCP declaration")
        if embedded:
            try:
                parsed = ImageCms.ImageCmsProfile(io.BytesIO(embedded))
            except (OSError, TypeError, ValueError, ImageCms.PyCMSError) as exc:
                raise RenderError(f"PNG has invalid color profile: {exc}") from None
            if hashlib.sha256(embedded).hexdigest() != icc_evidence.raw_sha256:
                raise RenderError("Pillow ICC bytes diverge from raw approved digest")
            color_space = str(getattr(parsed.profile, "xcolor_space", "")).strip()
            if color_space != "RGB":
                raise RenderError("Pillow ICC defense check did not report RGB")
        assert stream is not None
        return image, binding, stream
    except Exception:
        image.close()
        if stream is not None:
            stream.close()
        raise


def _bounded_output(output_path: Path) -> tuple[Path, Path]:
    lexical = Path(os.path.abspath(os.fspath(output_path)))
    try:
        relative = lexical.relative_to(_CANONICAL_RUNTIME_ROOT)
    except ValueError:
        raise RenderError("output must be below the exact canonical run root") from None
    if len(relative.parts) < 2 or not _RUN_ID.fullmatch(relative.parts[0]):
        raise RenderError("output must be below one exact canonical run root")
    run_root = _CANONICAL_RUNTIME_ROOT / relative.parts[0]
    _assert_plain_existing_components(lexical.parent)
    try:
        lexical.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise RenderError(f"cannot create output parent: {exc}") from None
    _assert_plain_existing_components(lexical.parent)
    if run_root.resolve(strict=True) != run_root:
        raise RenderError("canonical run root resolves through a reparse boundary")
    return lexical, run_root


def _identity(metadata: os.stat_result) -> _FileIdentity:
    return _FileIdentity(
        device=metadata.st_dev,
        inode=metadata.st_ino,
        size=metadata.st_size,
        modified_ns=metadata.st_mtime_ns,
    )


def _snapshot_regular_file(path: Path, *, role: str) -> tuple[_InputBinding, bytes]:
    if not isinstance(path, Path):
        raise RenderError(f"{role} path must be a pathlib.Path")
    lexical = Path(os.path.abspath(os.fspath(path)))
    _assert_plain_existing_components(lexical)
    if not lexical.is_file():
        raise RenderError(f"{role} input is missing or not a regular file")
    try:
        with lexical.open("rb") as stream:
            before = _identity(os.fstat(stream.fileno()))
            if before.size > _QUALIFIED_METRIC_MAX_BYTES:
                raise RenderError(
                    f"{role} input exceeds the C4 qualified metric byte limit"
                )
            payload = stream.read()
            after = _identity(os.fstat(stream.fileno()))
        path_after = _identity(lexical.stat())
    except OSError as exc:
        raise RenderError(f"cannot snapshot {role} input safely: {exc}") from None
    if before != after or after != path_after:
        raise RenderError(f"{role} input identity changed during snapshot")
    return (
        _InputBinding(
            path=lexical,
            identity=after,
            sha256=hashlib.sha256(payload).hexdigest(),
        ),
        payload,
    )


def _verify_input_binding(binding: _InputBinding) -> None:
    _assert_plain_existing_components(binding.path)
    try:
        observed = _identity(binding.path.stat())
    except OSError as exc:
        raise RenderError(f"bound input disappeared before commit: {exc}") from None
    if observed != binding.identity or _sha256_file(binding.path) != binding.sha256:
        raise RenderError(f"bound input changed before commit: {binding.path}")


def _bind_contract_input(
    constraints: _WriteConstraints,
    path: Path,
    *,
    kind: str,
    suffix: str,
    role: str,
    artifact_role: str,
    artifact_producer: str,
    normalized_reference: bool = False,
) -> tuple[_InputBinding, bytes]:
    lexical = Path(os.path.abspath(os.fspath(path)))
    try:
        relative = lexical.relative_to(_PROJECT_ROOT).as_posix()
    except ValueError:
        raise RenderError(f"{role} input is outside the project") from None
    matching = [
        artifact
        for artifact in constraints.contract["artifacts"]
        if artifact["path"] == relative
    ]
    if (
        len(matching) != 1
        or matching[0]["kind"] != kind
        or matching[0].get("role") != artifact_role
        or matching[0].get("producer") != artifact_producer
        or "sha256" not in matching[0]
    ):
        raise RenderError(f"{role} input must be one exact {kind} input artifact")
    if lexical.suffix.lower() != suffix:
        raise RenderError(f"{role} input must use the exact {suffix} extension")
    if normalized_reference and (
        constraints.contract["source"]["normalizedReferenceTarget"] != relative
    ):
        raise RenderError(
            "reference input must equal source.normalizedReferenceTarget exactly"
        )
    binding, payload = _snapshot_regular_file(lexical, role=role)
    expected_sha256 = matching[0]["sha256"]
    if binding.sha256 != expected_sha256:
        raise RenderError(
            f"{role} input does not match the contract expected sha256"
        )
    return (
        _InputBinding(
            path=binding.path,
            identity=binding.identity,
            sha256=binding.sha256,
            role=artifact_role,
            producer=artifact_producer,
        ),
        payload,
    )


def _validate_renderer_binary_location(profile: RenderProfile) -> Path:
    binary = profile.renderer_binary
    if binary is None:
        raise RenderError("rendering requires an explicit authorized renderer binary")
    if not isinstance(binary, Path):
        raise RenderError("renderer_binary must be a pathlib.Path")
    if not binary.is_absolute():
        raise RenderError("renderer binary must be an explicit absolute path")
    _assert_plain_existing_components(binary)
    if not binary.is_file():
        raise RenderError("explicit renderer binary is missing")
    return binary


def _snapshot_explicit_renderer(profile: RenderProfile) -> bytes:
    binary = _validate_renderer_binary_location(profile)
    try:
        with binary.open("rb") as stream:
            before = _identity(os.fstat(stream.fileno()))
            payload = stream.read()
            after = _identity(os.fstat(stream.fileno()))
        path_after = _identity(binary.stat())
    except OSError as exc:
        raise RenderError(f"cannot snapshot renderer binary safely: {exc}") from None
    if before != after or after != path_after:
        raise RenderError("renderer source identity changed during verified copy")
    observed = hashlib.sha256(payload).hexdigest()
    if observed != profile.renderer_sha256:
        raise RenderError(
            f"renderer binary SHA-256 mismatch: expected {profile.renderer_sha256}, observed {observed}"
        )
    return payload


def _stage_renderer(profile: RenderProfile, directory: Path) -> tuple[Path, _FileIdentity]:
    payload = _snapshot_explicit_renderer(profile)
    descriptor = -1
    staged: Path | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=".verified-resvg.", suffix=".exe", dir=directory
        )
        staged = Path(name)
        with os.fdopen(descriptor, "wb") as stream:
            descriptor = -1
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        if os.name != "nt":
            staged.chmod(0o500)
        _assert_plain_existing_components(staged)
        observed = _sha256_file(staged)
        if observed != profile.renderer_sha256:
            raise RenderError("run-local renderer staging SHA-256 mismatch")
        return staged, _identity(staged.stat())
    except Exception as primary:
        cleanup_failures: list[OSError] = []
        if descriptor >= 0:
            try:
                os.close(descriptor)
            except OSError as cleanup:
                cleanup_failures.append(cleanup)
        if staged is not None and (staged.exists() or staged.is_symlink()):
            try:
                staged.unlink()
            except OSError as cleanup:
                cleanup_failures.append(cleanup)
        if cleanup_failures:
            residue = staged if staged is not None else directory
            raise RenderError(
                f"renderer staging failed ({primary}); additionally, cleanup left "
                f"explicit residue/descriptor at {residue}: {cleanup_failures}"
            ) from ExceptionGroup(
                "renderer staging primary failure and cleanup failure",
                [primary, *cleanup_failures],
            )
        raise


def _assert_staged_identity(
    path: Path,
    expected: _FileIdentity,
    expected_sha256: str,
) -> None:
    _assert_plain_existing_components(path)
    try:
        observed = _identity(path.stat())
    except OSError as exc:
        raise RenderError(f"cannot revalidate staged renderer identity: {exc}") from None
    if observed != expected:
        raise RenderError("run-local staged renderer identity changed")
    if _sha256_file(path) != expected_sha256:
        raise RenderError("run-local staged renderer hash changed")


def _verify_committed_target(
    path: Path,
    *,
    expected_sha256: str,
    expected_identity: _FileIdentity,
    role: str,
) -> str:
    primary: RenderError | None = None
    try:
        _assert_plain_existing_components(path)
        if not path.is_file():
            raise RenderError(f"{role} commit readback is missing or not a regular file")
        observed_identity = _identity(path.stat())
        observed_sha256 = _sha256_file(path)
        if observed_identity != expected_identity or observed_sha256 != expected_sha256:
            raise RenderError(f"{role} commit readback integrity mismatch")
        return observed_sha256
    except RenderError as exc:
        primary = exc
    cleanup: OSError | None = None
    if path.exists() or path.is_symlink():
        try:
            path.unlink()
        except OSError as exc:
            cleanup = exc
    if cleanup is not None:
        raise RenderError(
            f"{primary}; additionally, invalid {role} target residue remains at {path}: {cleanup}"
        ) from ExceptionGroup(
            f"{role} commit integrity failure and invalid-target cleanup failure",
            [primary, cleanup],
        )
    raise primary


@contextmanager
def _hold_staged_executable(path: Path) -> Iterator[None]:
    """Deny staged executable writes/replacement while Windows opens it to run."""

    if os.name != "nt":
        descriptor = os.open(path, os.O_RDONLY)
        try:
            yield
        finally:
            os.close(descriptor)
        return

    import ctypes
    from ctypes import wintypes

    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    create_file = kernel32.CreateFileW
    create_file.argtypes = [
        wintypes.LPCWSTR,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.LPVOID,
        wintypes.DWORD,
        wintypes.DWORD,
        wintypes.HANDLE,
    ]
    create_file.restype = wintypes.HANDLE
    close_handle = kernel32.CloseHandle
    close_handle.argtypes = [wintypes.HANDLE]
    close_handle.restype = wintypes.BOOL
    handle = create_file(
        os.fspath(path),
        0x80000000,
        0x00000001,
        None,
        3,
        0x00000080,
        None,
    )
    invalid = wintypes.HANDLE(-1).value
    if handle == invalid:
        raise RenderError(
            f"cannot lock staged renderer identity: WinError {ctypes.get_last_error()}"
        )
    try:
        yield
    finally:
        if not close_handle(handle):
            raise RenderError(
                f"cannot release staged renderer identity: WinError {ctypes.get_last_error()}"
            )


def _run_renderer(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="strict",
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.SubprocessError, UnicodeError) as exc:
        raise RenderError(f"renderer invocation failed: {exc}") from None


def _renderer_version(binary: Path, expected_version: str, run_root: Path) -> None:
    completed = _run_renderer([os.fspath(binary), "--version"], cwd=run_root)
    if completed.returncode != 0:
        raise RenderError(f"renderer version check failed with exit {completed.returncode}")
    observed = completed.stdout.strip()
    if observed not in {expected_version, f"resvg {expected_version}"}:
        raise RenderError(
            f"renderer version mismatch: expected resvg {expected_version!s}, observed {observed!r}"
        )


def _raise_render_outcome(
    primary: RenderError | None,
    cleanup_failures: list[tuple[Path, OSError]],
) -> None:
    if cleanup_failures:
        residue = "; ".join(f"{path}: {error}" for path, error in cleanup_failures)
        message = f"temporary render cleanup left explicit residue: {residue}"
        cleanup_errors = [error for _, error in cleanup_failures]
        if primary is not None:
            combined = RenderError(f"{primary}; additionally, {message}")
            raise combined from ExceptionGroup(
                "render primary failure and temporary cleanup failure",
                [primary, *cleanup_errors],
            )
        cleanup_error = RenderError(message)
        if len(cleanup_errors) == 1:
            raise cleanup_error from cleanup_errors[0]
        raise cleanup_error from ExceptionGroup(
            "multiple temporary render cleanup failures", cleanup_errors
        )
    if primary is not None:
        raise primary


def render_svg(
    svg_path: Path,
    output_path: Path,
    profile: RenderProfile,
    *,
    run_contract: dict | None = None,
) -> RenderResult:
    """Sanitize and render SVG with the exact authorized binary and no PATH lookup."""

    _validate_profile(profile)
    _validate_renderer_binary_location(profile)
    constraints = _validated_write_constraints(
        run_contract,
        output_path,
        profile,
        allowed_kinds=frozenset({"evidence"}),
        operation="reconstruct",
        artifact_role="render-preview",
        artifact_producer="resvg-v0.47.0",
    )
    output, run_root = _bounded_output(output_path)
    if output != constraints.target or run_root != constraints.run_root:
        raise RenderError("prepared output diverges from the validated run contract")
    source_binding, source_payload = _bind_contract_input(
        constraints,
        svg_path,
        kind="vector-output",
        suffix=".svg",
        role="sanitized SVG",
        artifact_role="sanitized-svg",
        artifact_producer="rir-svg-serializer-v1",
    )
    try:
        sanitized = sanitize_svg(source_payload)
    except UnsafeSVGError as exc:
        raise RenderError(f"SVG input failed deterministic safety validation: {exc}") from None

    svg_temp: Path | None = None
    png_temp: Path | None = None
    staged_renderer: Path | None = None
    primary_error: RenderError | None = None
    output_hash: str | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="wb",
            prefix=f".{output.name}.",
            suffix=".svg",
            dir=output.parent,
            delete=False,
        ) as stream:
            stream.write(sanitized)
            stream.flush()
            os.fsync(stream.fileno())
            svg_temp = Path(stream.name)
        handle, name = tempfile.mkstemp(
            prefix=f".{output.name}.", suffix=".png", dir=output.parent
        )
        os.close(handle)
        png_temp = Path(name)
        staged_renderer, staged_identity = _stage_renderer(profile, output.parent)
        with _hold_staged_executable(staged_renderer):
            _assert_staged_identity(
                staged_renderer, staged_identity, profile.renderer_sha256
            )
            _renderer_version(staged_renderer, profile.renderer_version, run_root)
            _assert_staged_identity(
                staged_renderer, staged_identity, profile.renderer_sha256
            )
            completed = _run_renderer(
                [os.fspath(staged_renderer), os.fspath(svg_temp), os.fspath(png_temp)],
                cwd=run_root,
            )
            if completed.returncode != 0:
                message = (completed.stderr or completed.stdout).strip()
                raise RenderError(
                    f"renderer failed with exit {completed.returncode}: {message}"
                )
            _assert_staged_identity(
                staged_renderer, staged_identity, profile.renderer_sha256
            )
        image, rendered_binding, rendered_stream = _open_checked_png_header(png_temp)
        try:
            image.load()
            if image.size != (profile.width, profile.height):
                raise RenderError(
                    "renderer output dimensions do not match the fixed profile; scaling/cropping is forbidden"
                )
        finally:
            image.close()
            rendered_stream.close()
        _assert_plain_existing_components(output.parent)
        _verify_input_binding(rendered_binding)
        expected_output_sha256 = constraints.target_artifact.get("sha256")
        if (
            expected_output_sha256 is not None
            and expected_output_sha256 != rendered_binding.sha256
        ):
            raise RenderError("render output does not match contract expected sha256")
        _revalidate_write_constraints(constraints, (source_binding,))
        os.replace(png_temp, output)
        png_temp = None
        output_hash = _verify_committed_target(
            output,
            expected_sha256=rendered_binding.sha256,
            expected_identity=rendered_binding.identity,
            role="render output",
        )
    except Exception as exc:
        if isinstance(exc, RenderError):
            primary_error = exc
        else:
            primary_error = RenderError(f"cannot render/write output safely: {exc}")
            primary_error.__cause__ = exc

    cleanup_failures: list[tuple[Path, OSError]] = []
    for temporary in (svg_temp, png_temp, staged_renderer):
        if temporary is not None and (temporary.exists() or temporary.is_symlink()):
            try:
                temporary.unlink(missing_ok=True)
            except OSError as exc:
                cleanup_failures.append((temporary, exc))
    _raise_render_outcome(primary_error, cleanup_failures)
    if output_hash is None:
        raise RenderError("render completed without output hash evidence")

    return RenderResult(
        output_path=output,
        output_sha256=output_hash,
        width=profile.width,
        height=profile.height,
        profile_id=profile.profile_id,
        renderer_id=profile.renderer_id,
        renderer_version=profile.renderer_version,
        renderer_sha256=profile.renderer_sha256,
        registry_digest=profile.registry_sha256,
        metric_max_pixels=profile.metric_max_pixels,
        metric_max_bytes=profile.metric_max_bytes,
        metric_budget_version=profile.metric_budget_version,
        output_icc_profile_id=rendered_binding.icc_profile_id,
        output_icc_profile_sha256=rendered_binding.icc_profile_sha256,
        output_raw_icc_sha256=rendered_binding.raw_icc_sha256,
        output_canonical_icc_sha256=rendered_binding.canonical_icc_sha256,
        output_icc_canonicalization=rendered_binding.icc_canonicalization,
        input_bindings=(
            ArtifactBindingEvidence(
                path=source_binding.path,
                role=source_binding.role,
                producer=source_binding.producer,
                sha256=source_binding.sha256,
                icc_profile_id=source_binding.icc_profile_id,
                icc_profile_sha256=source_binding.icc_profile_sha256,
                raw_icc_sha256=source_binding.raw_icc_sha256,
                canonical_icc_sha256=source_binding.canonical_icc_sha256,
                icc_canonicalization=source_binding.icc_canonicalization,
            ),
        ),
    )
