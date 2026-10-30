# SPDX-License-Identifier: MIT
"""Immutable, deterministic raster intake for reconstruction runs."""
from __future__ import annotations

import hashlib
import os
import re
import stat
import tempfile
from dataclasses import dataclass
from enum import Enum
from io import BytesIO
from pathlib import Path

import numpy as np
from PIL import Image, ImageCms, UnidentifiedImageError

from .contracts import ContractError, validate_run_contract
from .runtime_roots import RUNTIME_PARENT as _CANONICAL_RUNTIME_ROOT
from .runtime_roots import runtime_root as _canonical_runtime_root

_SUPPORTED_FORMATS = frozenset({"PNG", "JPEG", "WEBP"})
_SUPPORTED_MODES = frozenset({"RGB", "RGBA"})
_NORMALIZED_NAME = "reference.normalized.png"
_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_STABLE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")


class IntakeError(ValueError):
    """An input cannot be normalized without weakening the intake contract."""


class ReconstructionProfile(str, Enum):
    """Deterministic visual-complexity class used by downstream providers."""

    FLAT = "flat"
    UI = "ui"
    MIXED = "mixed"
    PHOTOGRAPHIC = "photographic"


@dataclass(frozen=True)
class SourceIdentity:
    """Exact immutable identity observed before and after source decoding."""

    resolved_path: Path
    sha256: str
    size_bytes: int
    modified_time_ns: int
    device: int
    file_id: int


@dataclass(frozen=True)
class ColorProfileMetadata:
    """Declared origin and identity of the profile used for conversion."""

    origin: str
    name: str
    icc_sha256: str | None


@dataclass(frozen=True)
class AnalysisTile:
    """One complete analysis tile in the source canvas coordinate system."""

    index: int
    x: int
    y: int
    width: int
    height: int

    @property
    def right(self) -> int:
        return self.x + self.width

    @property
    def bottom(self) -> int:
        return self.y + self.height


@dataclass(frozen=True)
class IntakeResult:
    """Complete immutable result of normalizing one source image."""

    source_sha256: str
    normalized_sha256: str
    width: int
    height: int
    mode: str
    normalized_path: Path
    source_format: str
    original_mode: str
    source_identity: SourceIdentity
    color_profile: ColorProfileMetadata
    profile: ReconstructionProfile
    tiles: tuple[AnalysisTile, ...]


@dataclass(frozen=True)
class _ContractConstraints:
    """Validated immutable constraints passed into the single private writer."""

    source_path: Path
    source_sha256: str
    run_dir: Path
    normalized_path: Path
    width: int
    height: int
    profile: ReconstructionProfile
    max_axis: int


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


_SRGB_PROFILE_HEX = (
    "0000024c6c636d73044000006d6e74725247422058595a2007d0000100010000"
    "00000000616373704d5346540000000000000000000000000000000000000000"
    "000000000000f6d6000100000000d32d6c636d73000000000000000000000000"
    "0000000000000000000000000000000000000000000000000000000000000000"
    "0000000b64657363000001080000003663707274000001400000004c77747074"
    "0000018c0000001463686164000001a00000002c7258595a000001cc00000014"
    "6258595a000001e0000000146758595a000001f4000000147254524300000208"
    "000000206754524300000208000000206254524300000208000000206368726d"
    "00000228000000246d6c756300000000000000010000000c656e55530000001a"
    "0000001c00730052004700420020006200750069006c0074002d0069006e0000"
    "6d6c756300000000000000010000000c656e5553000000300000001c004e006f"
    "00200063006f0070007900720069006700680074002c00200075007300650020"
    "0066007200650065006c007958595a20000000000000f6d6000100000000d32d"
    "736633320000000000010c42000005defffff325000007930000fd90fffffba1"
    "fffffda2000003dc0000c06e58595a200000000000006fa0000038f500000390"
    "58595a20000000000000249f00000f840000b6c358595a200000000000006297"
    "0000b787000018d9706172610000000000030000000266660000f2a700000d59"
    "000013d000000a5b6368726d00000000000300000000a3d70000547b00004ccd"
    "0000999a0000266600000f5c"
)


def _canonical_srgb_profile_bytes() -> bytes:
    """Return the pinned canonical sRGB ICC profile (lcms 2.19 bytes, creation date fixed).

    Hard-coded instead of generated at runtime so the normalized PNG ICC digest is
    identical on every platform regardless of the Pillow wheel's bundled lcms
    version (Windows and manylinux wheels ship different lcms builds, which would
    otherwise produce different sRGB profiles and break cross-platform ICC
    digest verification against the approved registry).
    """
    return bytes.fromhex(_SRGB_PROFILE_HEX)


_SRGB_PROFILE_BYTES = _canonical_srgb_profile_bytes()


def _srgb_profile() -> ImageCms.ImageCmsProfile:
    return ImageCms.ImageCmsProfile(BytesIO(_SRGB_PROFILE_BYTES))


def _profile_metadata(image: Image.Image) -> tuple[ImageCms.ImageCmsProfile, ColorProfileMetadata]:
    embedded = image.info.get("icc_profile")
    if embedded is None:
        profile = _srgb_profile()
        return profile, ColorProfileMetadata(
            origin="assumed-srgb",
            name="sRGB",
            icc_sha256=None,
        )
    if not isinstance(embedded, bytes) or not embedded:
        raise IntakeError("embedded color profile is not valid ICC bytes")
    try:
        profile = ImageCms.ImageCmsProfile(BytesIO(embedded))
        name = ImageCms.getProfileName(profile).strip().rstrip("\x00")
    except (OSError, TypeError, ValueError, ImageCms.PyCMSError) as exc:
        raise IntakeError(f"invalid embedded color profile: {exc}") from None
    if not name:
        name = "embedded ICC profile"
    return profile, ColorProfileMetadata(
        origin="embedded",
        name=name,
        icc_sha256=_sha256_bytes(embedded),
    )


def _path_is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise IntakeError(f"cannot inspect destination path safely: {path}: {exc}") from None
    return path.is_symlink() or bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _assert_existing_components_are_plain(path: Path) -> None:
    current = Path(path.anchor)
    parts = path.parts[1:] if path.anchor else path.parts
    for part in parts:
        current /= part
        if not current.exists() and not current.is_symlink():
            continue
        if _path_is_reparse(current):
            raise IntakeError(f"destination crosses a symlink/reparse boundary: {current}")


def _canonical_run_directory(run_dir: Path) -> Path:
    run_dir = Path(run_dir)
    if any(part == ".." for part in run_dir.parts):
        raise IntakeError("run directory must not contain parent traversal")
    lexical_run_dir = Path(os.path.abspath(os.fspath(run_dir)))
    if lexical_run_dir.parent != _CANONICAL_RUNTIME_ROOT:
        raise IntakeError(
            "run directory must be one direct run-id child of the canonical reconstruction root"
        )
    if not _STABLE_RUN_ID.fullmatch(lexical_run_dir.name):
        raise IntakeError("run directory name must be a stable run id")

    _assert_existing_components_are_plain(_CANONICAL_RUNTIME_ROOT)
    try:
        _CANONICAL_RUNTIME_ROOT.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntakeError(f"cannot create canonical runtime root: {exc}") from None
    _assert_existing_components_are_plain(_CANONICAL_RUNTIME_ROOT)
    try:
        exact_runtime_root = _CANONICAL_RUNTIME_ROOT.resolve(strict=True)
    except OSError as exc:
        raise IntakeError(f"cannot resolve canonical runtime root safely: {exc}") from None
    if exact_runtime_root != _CANONICAL_RUNTIME_ROOT:
        raise IntakeError("canonical runtime root resolves through a reparse boundary")
    return lexical_run_dir


def _prepare_destination(run_dir: Path, source: Path) -> tuple[Path, Path]:
    lexical_run_dir = _canonical_run_directory(run_dir)
    _assert_existing_components_are_plain(lexical_run_dir)
    try:
        lexical_run_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise IntakeError(f"cannot create run directory: {exc}") from None
    _assert_existing_components_are_plain(lexical_run_dir)
    try:
        exact_run_dir = lexical_run_dir.resolve(strict=True)
    except OSError as exc:
        raise IntakeError(f"cannot resolve run directory safely: {exc}") from None
    if exact_run_dir != lexical_run_dir:
        raise IntakeError("run directory does not resolve to its exact lexical path")

    destination = exact_run_dir / _NORMALIZED_NAME
    if destination.exists() or destination.is_symlink():
        if _path_is_reparse(destination):
            raise IntakeError("normalized output is an existing symlink/reparse point")
        try:
            resolved_destination = destination.resolve(strict=True)
        except OSError as exc:
            raise IntakeError(f"cannot resolve existing output safely: {exc}") from None
        if resolved_destination.parent != exact_run_dir:
            raise IntakeError("normalized output escapes the exact run directory")
    if source == destination:
        raise IntakeError("normalized output would overwrite the immutable source")
    return exact_run_dir, destination


def partition_analysis_tiles(
    width: int,
    height: int,
    max_axis: int = 4096,
) -> tuple[AnalysisTile, ...]:
    """Partition a canvas into non-overlapping row-major global-coordinate tiles."""

    for name, value in (("width", width), ("height", height), ("max_axis", max_axis)):
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise IntakeError(f"{name} must be a positive integer")
    tiles: list[AnalysisTile] = []
    for y in range(0, height, max_axis):
        tile_height = min(max_axis, height - y)
        for x in range(0, width, max_axis):
            tiles.append(
                AnalysisTile(
                    index=len(tiles),
                    x=x,
                    y=y,
                    width=min(max_axis, width - x),
                    height=tile_height,
                )
            )
    return tuple(tiles)


def classify_reconstruction_profile(pixels: np.ndarray) -> ReconstructionProfile:
    """Classify an RGBA uint8 pixel array without I/O or mutable global state."""

    if (
        not isinstance(pixels, np.ndarray)
        or pixels.dtype != np.uint8
        or pixels.ndim != 3
        or pixels.shape[0] <= 0
        or pixels.shape[1] <= 0
        or pixels.shape[2] != 4
    ):
        raise IntakeError("classifier expects a non-empty HxWx4 uint8 RGBA array")

    visible = pixels[:, :, 3] > 0
    if not bool(np.any(visible)):
        return ReconstructionProfile.FLAT
    rgb = pixels[:, :, :3]
    visible_rgb = rgb[visible]
    quantized = visible_rgb >> 3
    unique_colors = int(np.unique(quantized, axis=0).shape[0])

    luma = (
        rgb[:, :, 0].astype(np.int32) * 54
        + rgb[:, :, 1].astype(np.int32) * 183
        + rgb[:, :, 2].astype(np.int32) * 19
    ) >> 8
    horizontal_visible = visible[:, :-1] & visible[:, 1:]
    vertical_visible = visible[:-1, :] & visible[1:, :]
    horizontal = (np.abs(np.diff(luma, axis=1)) >= 16) & horizontal_visible
    vertical = (np.abs(np.diff(luma, axis=0)) >= 16) & vertical_visible
    edge_samples = int(np.count_nonzero(horizontal_visible)) + int(
        np.count_nonzero(vertical_visible)
    )
    edge_density = (
        (int(np.count_nonzero(horizontal)) + int(np.count_nonzero(vertical))) / edge_samples
        if edge_samples
        else 0.0
    )

    if unique_colors <= 16:
        return ReconstructionProfile.UI if edge_density >= 0.08 else ReconstructionProfile.FLAT
    if unique_colors >= 128 and edge_density >= 0.20:
        return ReconstructionProfile.PHOTOGRAPHIC
    return ReconstructionProfile.MIXED


def _normalize_pixels(
    image: Image.Image,
    source_profile: ImageCms.ImageCmsProfile,
) -> Image.Image:
    try:
        return ImageCms.profileToProfile(
            image.convert("RGBA"),
            source_profile,
            _srgb_profile(),
            renderingIntent=ImageCms.Intent.RELATIVE_COLORIMETRIC,
            outputMode="RGBA",
        )
    except (OSError, TypeError, ValueError, ImageCms.PyCMSError) as exc:
        raise IntakeError(f"color conversion failed: {exc}") from None


def _png_bytes(image: Image.Image) -> bytes:
    output = BytesIO()
    image.save(
        output,
        format="PNG",
        optimize=False,
        compress_level=9,
        icc_profile=_SRGB_PROFILE_BYTES,
    )
    return output.getvalue()


def _source_identity(path: Path, sha256: str, metadata: os.stat_result) -> SourceIdentity:
    return SourceIdentity(
        resolved_path=path,
        sha256=sha256,
        size_bytes=metadata.st_size,
        modified_time_ns=metadata.st_mtime_ns,
        device=metadata.st_dev,
        file_id=metadata.st_ino,
    )


def _source_is_unchanged(
    path: Path,
    before: os.stat_result,
    before_hash: str,
) -> bool:
    try:
        after = path.stat()
        after_hash = _sha256_file(path)
    except OSError:
        return False
    return (
        after.st_dev == before.st_dev
        and after.st_ino == before.st_ino
        and after.st_size == before.st_size
        and after.st_mtime_ns == before.st_mtime_ns
        and after_hash == before_hash
    )


def _after_output_commit(_source: Path, _destination: Path) -> None:
    """Deterministic no-op seam for exercising a final source-identity race check."""


def _after_contract_validation(
    _source: Path,
    _constraints: _ContractConstraints,
) -> None:
    """No-op seam for proving post-validation source replacement fails closed."""


def _remove_invalid_output(destination: Path) -> None:
    try:
        destination.unlink(missing_ok=True)
    except OSError as exc:
        raise IntakeError(f"invalid normalized-output cleanup failed: {exc}") from None


def _validated_contract_constraints(run_contract: dict) -> _ContractConstraints:
    try:
        validate_run_contract(run_contract)
    except (ContractError, TypeError, ValueError) as exc:
        raise IntakeError(f"invalid reconstruction run contract: {exc}") from None

    run_id = run_contract["runId"]
    runtime_relative = _canonical_runtime_root(run_id)
    normalized_relative = runtime_relative + _NORMALIZED_NAME
    if run_contract["roots"]["runtime"] != runtime_relative:
        raise IntakeError("run contract runtime root does not bind the declared run id")
    if run_contract["source"]["normalizedReferenceTarget"] != normalized_relative:
        raise IntakeError("run contract normalized target is not the canonical runtime output")

    normalized_artifacts = [
        artifact
        for artifact in run_contract["artifacts"]
        if artifact["kind"] == "normalized-source"
    ]
    if len(normalized_artifacts) != 1 or normalized_artifacts[0]["path"] != normalized_relative:
        raise IntakeError("run contract must authorize exactly one canonical normalized-source artifact")
    authorized_targets = run_contract["writeAuthorization"]["targets"]
    if authorized_targets.count(normalized_relative) != 1:
        raise IntakeError("write authorization does not exactly permit the normalized output")

    canvas_policy = run_contract["canvasPolicy"]
    tile_policy = canvas_policy["tilePolicy"]
    if canvas_policy["globalCoordinates"] != "source-pixel":
        raise IntakeError("intake contract must use source-pixel global coordinates")
    if tile_policy["tileWidth"] != tile_policy["tileHeight"] or tile_policy["overlap"] != 0:
        raise IntakeError("intake contract requires equal non-overlapping analysis tiles")
    contract_max_axis = tile_policy["tileWidth"]
    expected_tiling = (
        canvas_policy["width"] > contract_max_axis
        or canvas_policy["height"] > contract_max_axis
    )
    if tile_policy["enabled"] != expected_tiling:
        raise IntakeError("intake contract tile enablement does not match the canvas")

    run_dir = _PROJECT_ROOT.joinpath(*runtime_relative.rstrip("/").split("/"))
    normalized_path = run_dir / _NORMALIZED_NAME
    source_path = _PROJECT_ROOT.joinpath(*run_contract["source"]["path"].split("/"))
    return _ContractConstraints(
        source_path=source_path,
        source_sha256=run_contract["source"]["sha256"].lower(),
        run_dir=run_dir,
        normalized_path=normalized_path,
        width=canvas_policy["width"],
        height=canvas_policy["height"],
        profile=ReconstructionProfile(run_contract["profile"]),
        max_axis=contract_max_axis,
    )


def _normalize_reference_core(
    source: Path,
    run_dir: Path,
    max_axis: int,
    constraints: _ContractConstraints,
) -> IntakeResult:
    """Private single writer; every constraint is established before final commit."""

    try:
        resolved_source = Path(source).resolve(strict=True)
        contracted_source = constraints.source_path.resolve(strict=True)
        source_stat = resolved_source.stat()
        source_hash = _sha256_file(resolved_source)
    except (OSError, RuntimeError) as exc:
        raise IntakeError(f"cannot resolve source: {exc}") from None
    if not resolved_source.is_file():
        raise IntakeError("source must be a regular file")
    if resolved_source != contracted_source:
        raise IntakeError("source path does not match the validated run contract")
    if source_hash.lower() != constraints.source_sha256:
        raise IntakeError("source hash does not match the validated run contract")
    identity = _source_identity(resolved_source, source_hash, source_stat)

    try:
        with Image.open(resolved_source) as opened:
            opened.load()
            source_format = opened.format
            original_mode = opened.mode
            if source_format not in _SUPPORTED_FORMATS:
                raise IntakeError(f"unsupported decoded image format: {source_format!r}")
            if original_mode not in _SUPPORTED_MODES:
                raise IntakeError(f"unsupported decoded image mode: {original_mode!r}")
            if opened.width <= 0 or opened.height <= 0:
                raise IntakeError("invalid image dimensions")
            source_profile, profile_metadata = _profile_metadata(opened)
            normalized = _normalize_pixels(opened, source_profile)
            width, height = opened.size
    except IntakeError:
        raise
    except (UnidentifiedImageError, OSError, SyntaxError, ValueError) as exc:
        raise IntakeError(f"cannot decode supported image safely: {exc}") from None

    tiles = partition_analysis_tiles(width, height, max_axis)
    pixels = np.asarray(normalized, dtype=np.uint8)
    profile = classify_reconstruction_profile(pixels)
    encoded = _png_bytes(normalized)

    if (width, height) != (constraints.width, constraints.height):
        raise IntakeError("normalized canvas does not match the validated run contract")
    if profile != constraints.profile:
        raise IntakeError("reconstruction profile does not match the validated run contract")
    lexical_run_dir = Path(os.path.abspath(os.fspath(run_dir)))
    if lexical_run_dir != constraints.run_dir:
        raise IntakeError("run directory does not equal the validated contract runtime root")
    if max_axis != constraints.max_axis:
        raise IntakeError("max_axis does not equal the validated contract tile policy")
    if constraints.normalized_path != constraints.run_dir / _NORMALIZED_NAME:
        raise IntakeError("normalized target does not equal the validated contract output")
    if not _source_is_unchanged(resolved_source, source_stat, source_hash):
        raise IntakeError("source identity changed during normalization")
    exact_run_dir, destination = _prepare_destination(source=resolved_source, run_dir=run_dir)
    if exact_run_dir != constraints.run_dir or destination != constraints.normalized_path:
        raise IntakeError("prepared destination diverges from the validated run contract")

    temp_path: Path | None = None
    primary_error: IntakeError | None = None
    try:
        try:
            descriptor, temp_name = tempfile.mkstemp(
                prefix=".reference.normalized.",
                suffix=".tmp",
                dir=exact_run_dir,
            )
            temp_path = Path(temp_name)
            with os.fdopen(descriptor, "wb") as stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            _assert_existing_components_are_plain(exact_run_dir)
            if destination.exists() or destination.is_symlink():
                if _path_is_reparse(destination):
                    raise IntakeError("normalized output became a symlink/reparse point")
            if not _source_is_unchanged(resolved_source, source_stat, source_hash):
                raise IntakeError("source identity changed before final output commit")
            os.replace(temp_path, destination)
            temp_path = None
            _after_output_commit(resolved_source, destination)
            if not _source_is_unchanged(resolved_source, source_stat, source_hash):
                _remove_invalid_output(destination)
                raise IntakeError("source identity changed during final output commit")
        except OSError as exc:
            raise IntakeError(f"cannot write normalized output safely: {exc}") from exc
    except IntakeError as exc:
        primary_error = exc

    cleanup_error: OSError | None = None
    if temp_path is not None:
        try:
            temp_path.unlink(missing_ok=True)
        except OSError as exc:
            cleanup_error = exc
    if cleanup_error is not None:
        cleanup_context = (
            f"temporary normalized-output residue cleanup failed: {cleanup_error}"
        )
        if primary_error is not None:
            combined = IntakeError(f"{primary_error}; additionally, {cleanup_context}")
            failures = ExceptionGroup(
                "normalized output write and temporary cleanup both failed",
                [primary_error, cleanup_error],
            )
            raise combined from failures
        raise IntakeError(cleanup_context) from cleanup_error
    if primary_error is not None:
        raise primary_error

    return IntakeResult(
        source_sha256=source_hash,
        normalized_sha256=_sha256_bytes(encoded),
        width=width,
        height=height,
        mode="RGBA",
        normalized_path=destination,
        source_format=source_format,
        original_mode=original_mode,
        source_identity=identity,
        color_profile=profile_metadata,
        profile=profile,
        tiles=tiles,
    )


def normalize_reference(
    source: Path,
    run_dir: Path,
    max_axis: int = 4096,
    *,
    run_contract: dict,
) -> IntakeResult:
    """Normalize only when a validated run contract authorizes this exact write."""

    constraints = _validated_contract_constraints(run_contract)
    lexical_run_dir = Path(os.path.abspath(os.fspath(run_dir)))
    if lexical_run_dir != constraints.run_dir:
        raise IntakeError("run directory does not equal the validated contract runtime root")
    if max_axis != constraints.max_axis:
        raise IntakeError("max_axis does not equal the validated contract tile policy")
    _after_contract_validation(Path(source), constraints)
    return _normalize_reference_core(source, run_dir, max_axis, constraints)


def normalize_reference_for_contract(
    source: Path,
    run_contract: dict,
    max_axis: int = 4096,
) -> IntakeResult:
    """Derive the exact run directory from a required contract and normalize."""

    constraints = _validated_contract_constraints(run_contract)
    if max_axis != constraints.max_axis:
        raise IntakeError("max_axis does not equal the validated contract tile policy")
    _after_contract_validation(Path(source), constraints)
    return _normalize_reference_core(source, constraints.run_dir, max_axis, constraints)
