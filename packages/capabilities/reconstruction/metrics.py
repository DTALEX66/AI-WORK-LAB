# SPDX-License-Identifier: MIT
"""Pixelmatch v7.2.0/YIQ and fixed-profile deterministic fidelity gates."""
from __future__ import annotations

import hashlib
import io
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import numpy as np
from PIL import Image
from skimage.filters import sobel
from skimage.metrics import structural_similarity

from .render import (
    ArtifactBindingEvidence,
    RenderError,
    RenderProfile,
    _InputBinding,
    _WriteConstraints,
    _bind_contract_input,
    _bounded_output,
    _load_registry,
    _open_checked_png_header,
    _probe_png_dimensions,
    _revalidate_write_constraints,
    _snapshot_regular_file,
    _validate_profile,
    _validated_write_constraints,
    _verify_committed_target,
    load_render_profile,
)


class FidelityError(ValueError):
    """Images or metrics violate the deterministic fidelity contract."""


@dataclass(frozen=True)
class DiffComponent:
    """One deterministic 8-connected mismatch component."""

    bounds: tuple[int, int, int, int]
    pixel_count: int
    density: float


@dataclass(frozen=True)
class FidelityMetrics:
    """Complete deterministic-renderer comparison evidence."""

    width: int
    height: int
    profile_id: str
    pixelmatch_version: str
    pixel_threshold: float
    anti_alias_detection: bool
    match_minimum: float
    ssim_minimum: float
    mae_limit_version: str
    mae_limit: float | None
    edge_metric: str
    match_ratio: float
    mismatch_count: int
    excluded_aa_count: int
    ssim: float
    mean_rgba_error: float
    alpha_mean_error: float
    edge_error: float
    max_diff_window: int
    components: tuple[DiffComponent, ...]
    dense_regions: tuple[DiffComponent, ...]
    mismatch_mask: bytes
    mismatch_mask_sha256: str
    excluded_aa_mask: bytes
    diff_path: Path | None
    diff_sha256: str
    failure_reasons: tuple[str, ...]
    passed: bool
    lifecycle_status: str
    registry_digest: str
    metric_max_pixels: int
    metric_max_bytes: int
    metric_budget_version: str
    reference_icc_profile_id: str
    reference_icc_profile_sha256: str | None
    reference_raw_icc_sha256: str | None
    reference_canonical_icc_sha256: str | None
    reference_icc_canonicalization: str
    actual_icc_profile_id: str
    actual_icc_profile_sha256: str | None
    actual_raw_icc_sha256: str | None
    actual_canonical_icc_sha256: str | None
    actual_icc_canonicalization: str
    input_authority: str
    input_bindings: tuple[ArtifactBindingEvidence, ...]


def _decode_rgba(image: Image.Image, source: Path) -> np.ndarray:
    try:
        image.load()
        return np.asarray(image.convert("RGBA"), dtype=np.uint8).copy()
    except (OSError, ValueError) as exc:
        raise FidelityError(f"cannot read comparison image: {source}: {exc}") from None


def _color_delta(
    image1: np.ndarray,
    image2: np.ndarray,
    y: int,
    x: int,
    background: tuple[int, int, int, int],
) -> float:
    """Literal mapbox/pixelmatch v7.2.0 YIQ delta on a white background."""

    r1, g1, b1, a1 = (float(value) for value in image1[y, x])
    r2, g2, b2, a2 = (float(value) for value in image2[y, x])
    dr = r1 - r2
    dg = g1 - g2
    db = b1 - b2
    da = a1 - a2
    if a1 < 255 or a2 < 255:
        dr = (r1 * a1 - r2 * a2 - background[0] * da) / 255
        dg = (g1 * a1 - g2 * a2 - background[1] * da) / 255
        db = (b1 * a1 - b2 * a2 - background[2] * da) / 255
    yiq_y = dr * 0.29889531 + dg * 0.58662247 + db * 0.11448223
    yiq_i = dr * 0.59597799 - dg * 0.27417610 - db * 0.32180189
    yiq_q = dr * 0.21147017 - dg * 0.52261711 + db * 0.31114694
    delta = 0.5053 * yiq_y * yiq_y + 0.299 * yiq_i * yiq_i + 0.1957 * yiq_q * yiq_q
    return -delta if yiq_y > 0 else delta


def _brightness_delta(
    image: np.ndarray,
    center_y: int,
    center_x: int,
    neighbor_y: int,
    neighbor_x: int,
    background: tuple[int, int, int, int],
) -> float:
    r1, g1, b1, a1 = (float(value) for value in image[center_y, center_x])
    r2, g2, b2, a2 = (float(value) for value in image[neighbor_y, neighbor_x])
    dr = r1 - r2
    dg = g1 - g2
    db = b1 - b2
    da = a1 - a2
    if not dr and not dg and not db and not da:
        return 0.0
    if a1 < 255 or a2 < 255:
        dr = (r1 * a1 - r2 * a2 - background[0] * da) / 255
        dg = (g1 * a1 - g2 * a2 - background[1] * da) / 255
        db = (b1 * a1 - b2 * a2 - background[2] * da) / 255
    return dr * 0.29889531 + dg * 0.58662247 + db * 0.11448223


def _has_many_siblings(image: np.ndarray, x: int, y: int) -> bool:
    height, width, _ = image.shape
    x0 = max(x - 1, 0)
    y0 = max(y - 1, 0)
    x2 = min(x + 1, width - 1)
    y2 = min(y + 1, height - 1)
    zeroes = 1 if x == x0 or x == x2 or y == y0 or y == y2 else 0
    value = image[y, x]
    for nx in range(x0, x2 + 1):
        for ny in range(y0, y2 + 1):
            if nx == x and ny == y:
                continue
            if np.array_equal(value, image[ny, nx]):
                zeroes += 1
                if zeroes > 2:
                    return True
    return False


def _antialiased(
    image: np.ndarray,
    x: int,
    y: int,
    other: np.ndarray,
    background: tuple[int, int, int, int],
) -> bool:
    height, width, _ = image.shape
    x0 = max(x - 1, 0)
    y0 = max(y - 1, 0)
    x2 = min(x + 1, width - 1)
    y2 = min(y + 1, height - 1)
    zeroes = 1 if x == x0 or x == x2 or y == y0 or y == y2 else 0
    minimum = 0.0
    maximum = 0.0
    min_xy = (0, 0)
    max_xy = (0, 0)
    for nx in range(x0, x2 + 1):
        for ny in range(y0, y2 + 1):
            if nx == x and ny == y:
                continue
            delta = _brightness_delta(image, y, x, ny, nx, background)
            if delta == 0:
                zeroes += 1
                if zeroes > 2:
                    return False
            elif delta < minimum:
                minimum = delta
                min_xy = (nx, ny)
            elif delta > maximum:
                maximum = delta
                max_xy = (nx, ny)
    if minimum == 0 or maximum == 0:
        return False
    min_x, min_y = min_xy
    max_x, max_y = max_xy
    return (
        _has_many_siblings(image, min_x, min_y)
        and _has_many_siblings(other, min_x, min_y)
    ) or (
        _has_many_siblings(image, max_x, max_y)
        and _has_many_siblings(other, max_x, max_y)
    )


def pixelmatch_masks(
    image1: np.ndarray,
    image2: np.ndarray,
    *,
    threshold: float = 0.1,
    include_aa: bool = False,
    background: tuple[int, int, int, int] = (255, 255, 255, 255),
) -> tuple[np.ndarray, np.ndarray]:
    """Return counted and excluded-AA masks with pixelmatch v7.2.0 semantics."""

    if (
        not isinstance(image1, np.ndarray)
        or not isinstance(image2, np.ndarray)
        or image1.dtype != np.uint8
        or image2.dtype != np.uint8
        or image1.ndim != 3
        or image1.shape[-1] != 4
        or image1.shape != image2.shape
    ):
        raise FidelityError("pixelmatch inputs must be equal-size uint8 RGBA arrays")
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)) or not math.isfinite(float(threshold)) or not 0 <= threshold <= 1:
        raise FidelityError("pixelmatch threshold must be finite and between zero and one")
    if (
        not isinstance(background, tuple)
        or len(background) != 4
        or not all(isinstance(channel, int) and not isinstance(channel, bool) and 0 <= channel <= 255 for channel in background)
        or background[3] != 255
    ):
        raise FidelityError("pixelmatch comparison background must be opaque RGBA")
    height, width, _ = image1.shape
    mismatch = np.zeros((height, width), dtype=np.uint8)
    excluded_aa = np.zeros((height, width), dtype=np.uint8)
    max_delta = 35215 * float(threshold) * float(threshold)
    differing = np.argwhere(np.any(image1 != image2, axis=2))
    for y_value, x_value in differing:
        y = int(y_value)
        x = int(x_value)
        delta = _color_delta(image1, image2, y, x, background)
        if abs(delta) <= max_delta:
            continue
        excluded = not include_aa and (
            _antialiased(image1, x, y, image2, background)
            or _antialiased(image2, x, y, image1, background)
        )
        if excluded:
            excluded_aa[y, x] = 1
        else:
            mismatch[y, x] = 1
    return mismatch, excluded_aa


def _composite_rgba(image: np.ndarray, background: tuple[int, int, int, int]) -> np.ndarray:
    if background[3] != 255:
        raise FidelityError("fixed comparison background must be opaque")
    alpha = image[..., 3:4].astype(np.float64) / 255.0
    rgb = image[..., :3].astype(np.float64)
    base = np.asarray(background[:3], dtype=np.float64)
    return rgb * alpha + base * (1.0 - alpha)


def _components(mask: np.ndarray) -> tuple[DiffComponent, ...]:
    height, width = mask.shape
    visited = np.zeros_like(mask, dtype=bool)
    result: list[DiffComponent] = []
    for y in range(height):
        for x in range(width):
            if not mask[y, x] or visited[y, x]:
                continue
            stack = [(x, y)]
            visited[y, x] = True
            min_x = max_x = x
            min_y = max_y = y
            count = 0
            while stack:
                current_x, current_y = stack.pop()
                count += 1
                min_x = min(min_x, current_x)
                max_x = max(max_x, current_x)
                min_y = min(min_y, current_y)
                max_y = max(max_y, current_y)
                for dy in (-1, 0, 1):
                    for dx in (-1, 0, 1):
                        if dx == 0 and dy == 0:
                            continue
                        nx = current_x + dx
                        ny = current_y + dy
                        if 0 <= nx < width and 0 <= ny < height and mask[ny, nx] and not visited[ny, nx]:
                            visited[ny, nx] = True
                            stack.append((nx, ny))
            component_width = max_x - min_x + 1
            component_height = max_y - min_y + 1
            density = count / (component_width * component_height)
            result.append(
                DiffComponent(
                    bounds=(min_x, min_y, component_width, component_height),
                    pixel_count=count,
                    density=float(density),
                )
            )
    return tuple(result)


def _max_window_count(mask: np.ndarray, size: int) -> int:
    height, width = mask.shape
    window_height = min(size, height)
    window_width = min(size, width)
    integral = np.pad(mask.astype(np.int64), ((1, 0), (1, 0))).cumsum(0).cumsum(1)
    totals = (
        integral[window_height:, window_width:]
        - integral[:-window_height, window_width:]
        - integral[window_height:, :-window_width]
        + integral[:-window_height, :-window_width]
    )
    return int(totals.max(initial=0))


def _diff_png(mask: np.ndarray, excluded_aa: np.ndarray) -> bytes:
    height, width = mask.shape
    heatmap = np.zeros((height, width, 4), dtype=np.uint8)
    heatmap[excluded_aa.astype(bool)] = (255, 255, 0, 255)
    heatmap[mask.astype(bool)] = (255, 0, 0, 255)
    stream = io.BytesIO()
    Image.fromarray(heatmap, mode="RGBA").save(stream, format="PNG", optimize=False)
    return stream.getvalue()


def _small_canvas_ssim(reference_rgb: np.ndarray, actual_rgb: np.ndarray) -> float:
    """Deterministic global SSIM fallback where a 3x3 local window cannot fit."""

    if np.array_equal(reference_rgb, actual_rgb):
        return 1.0
    c1 = (0.01 * 255.0) ** 2
    c2 = (0.03 * 255.0) ** 2
    channel_scores: list[float] = []
    for channel in range(3):
        left = reference_rgb[..., channel].astype(np.float64).ravel()
        right = actual_rgb[..., channel].astype(np.float64).ravel()
        left_mean = float(left.mean())
        right_mean = float(right.mean())
        left_centered = left - left_mean
        right_centered = right - right_mean
        left_variance = float(np.mean(left_centered * left_centered))
        right_variance = float(np.mean(right_centered * right_centered))
        covariance = float(np.mean(left_centered * right_centered))
        luminance = (2 * left_mean * right_mean + c1) / (
            left_mean * left_mean + right_mean * right_mean + c1
        )
        contrast_structure = (2 * covariance + c2) / (
            left_variance + right_variance + c2
        )
        channel_scores.append(luminance * contrast_structure)
    return max(-1.0, min(1.0, float(np.mean(channel_scores))))


def _atomic_write(
    path: Path,
    payload: bytes,
    constraints: _WriteConstraints,
    input_bindings: tuple[_InputBinding, ...],
) -> Path:
    try:
        bounded, run_root = _bounded_output(path)
    except RenderError as exc:
        raise FidelityError(str(exc)) from None
    if bounded != constraints.target or run_root != constraints.run_root:
        raise FidelityError("prepared diff output diverges from the validated run contract")
    temporary: Path | None = None
    descriptor = -1
    primary: FidelityError | None = None
    try:
        descriptor, name = tempfile.mkstemp(
            prefix=f".{bounded.name}.", suffix=".tmp", dir=bounded.parent
        )
        temporary = Path(name)
        stream = os.fdopen(descriptor, "wb")
        descriptor = -1
        with stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        staged_binding, staged_payload = _snapshot_regular_file(
            temporary, role="diff staging"
        )
        if staged_binding.sha256 != hashlib.sha256(payload).hexdigest() or staged_payload != payload:
            raise FidelityError("diff staging integrity mismatch before commit")
        expected_output_sha256 = constraints.target_artifact.get("sha256")
        if (
            expected_output_sha256 is not None
            and expected_output_sha256 != staged_binding.sha256
        ):
            raise FidelityError("diff output does not match contract expected sha256")
        try:
            _bounded_output(bounded)
        except RenderError as exc:
            raise FidelityError(str(exc)) from None
        _revalidate_write_constraints(constraints, input_bindings)
        os.replace(temporary, bounded)
        temporary = None
        try:
            _verify_committed_target(
                bounded,
                expected_sha256=staged_binding.sha256,
                expected_identity=staged_binding.identity,
                role="diff output",
            )
        except RenderError as exc:
            raise FidelityError(str(exc)) from exc
    except FidelityError as exc:
        primary = exc
    except RenderError as exc:
        primary = FidelityError(str(exc))
        primary.__cause__ = exc
    except OSError as exc:
        primary = FidelityError(f"cannot write deterministic diff atomically: {exc}")
        primary.__cause__ = exc
    except Exception as exc:
        primary = FidelityError(f"unexpected diff commit failure: {exc}")
        primary.__cause__ = exc

    cleanup_failures: list[OSError] = []
    if descriptor >= 0:
        try:
            os.close(descriptor)
        except OSError as exc:
            cleanup_failures.append(exc)
    if temporary is not None and (temporary.exists() or temporary.is_symlink()):
        try:
            temporary.unlink()
        except OSError as exc:
            cleanup_failures.append(exc)
    if cleanup_failures:
        residue = temporary if temporary is not None else bounded.parent
        message = (
            f"diff cleanup left explicit residue/descriptor at {residue}: "
            f"{cleanup_failures}"
        )
        if primary is not None:
            combined = FidelityError(f"{primary}; additionally, {message}")
            raise combined from ExceptionGroup(
                "diff primary failure and temporary cleanup failure",
                [primary, *cleanup_failures],
            )
        if len(cleanup_failures) == 1:
            raise FidelityError(message) from cleanup_failures[0]
        raise FidelityError(message) from ExceptionGroup(
            "multiple diff temporary cleanup failures", cleanup_failures
        )
    if primary is not None:
        raise primary
    return bounded


def compare_images(
    reference: Path,
    actual: Path,
    *,
    profile: RenderProfile | None = None,
    diff_output_path: Path | None = None,
    run_contract: dict | None = None,
) -> FidelityMetrics:
    """Compare exact-size PNGs under the sole fixed deterministic profile."""

    reference_path = Path(os.path.abspath(os.fspath(reference)))
    actual_path = Path(os.path.abspath(os.fspath(actual)))
    try:
        if profile is None:
            _load_registry()
            reference_dimensions = _probe_png_dimensions(reference_path)
            actual_dimensions = _probe_png_dimensions(actual_path)
            if reference_dimensions != actual_dimensions:
                raise FidelityError(
                    "reference and actual dimensions do not match; scaling/cropping is forbidden"
                )
            profile = load_render_profile(*reference_dimensions)
        else:
            _validate_profile(profile)
    except RenderError as exc:
        raise FidelityError(str(exc)) from None
    try:
        reference_image, reference_header_binding, reference_stream = _open_checked_png_header(reference_path)
    except RenderError as exc:
        raise FidelityError(str(exc)) from None
    try:
        try:
            actual_image, actual_header_binding, actual_stream = _open_checked_png_header(actual_path)
        except RenderError as exc:
            raise FidelityError(str(exc)) from None
        try:
            if reference_image.size != actual_image.size:
                raise FidelityError(
                    "reference and actual dimensions do not match; scaling/cropping is forbidden"
                )
            width, height = reference_image.size
            if (width, height) != (profile.width, profile.height):
                raise FidelityError("image dimensions do not match fixed profile dimensions")
            write_constraints: _WriteConstraints | None = None
            if run_contract is not None or diff_output_path is not None:
                try:
                    if diff_output_path is not None:
                        write_constraints = _validated_write_constraints(
                            run_contract,
                            diff_output_path,
                            profile,
                            allowed_kinds=frozenset({"evidence"}),
                            operation="verify",
                            artifact_role="diff-evidence",
                            artifact_producer="fidelity-metrics-v1",
                        )
                    else:
                        write_constraints = _validated_write_constraints(
                            run_contract,
                            actual_path,
                            profile,
                            allowed_kinds=frozenset({"evidence"}),
                            operation="verify",
                            artifact_role="render-preview",
                            artifact_producer="resvg-v0.47.0",
                        )
                    reference_binding, _ = _bind_contract_input(
                        write_constraints,
                        reference_path,
                        kind="normalized-source",
                        suffix=".png",
                        role="normalized reference",
                        artifact_role="normalized-reference",
                        artifact_producer="intake-normalizer-v1",
                        normalized_reference=True,
                    )
                    actual_binding, _ = _bind_contract_input(
                        write_constraints,
                        actual_path,
                        kind="evidence",
                        suffix=".png",
                        role="actual preview",
                        artifact_role="render-preview",
                        artifact_producer="resvg-v0.47.0",
                    )
                except RenderError as exc:
                    raise FidelityError(str(exc)) from None
                if diff_output_path is not None and len(
                    {
                        reference_path,
                        actual_path,
                        Path(os.path.abspath(os.fspath(diff_output_path))),
                    }
                ) != 3:
                    raise FidelityError("reference, actual preview and diff target must be distinct")
                if (
                    (
                        reference_binding.path,
                        reference_binding.identity,
                        reference_binding.sha256,
                    )
                    != (
                        reference_header_binding.path,
                        reference_header_binding.identity,
                        reference_header_binding.sha256,
                    )
                    or (
                        actual_binding.path,
                        actual_binding.identity,
                        actual_binding.sha256,
                    )
                    != (
                        actual_header_binding.path,
                        actual_header_binding.identity,
                        actual_header_binding.sha256,
                    )
                ):
                    raise FidelityError("comparison input changed during contract binding")
                reference_binding = _InputBinding(
                    path=reference_binding.path,
                    identity=reference_binding.identity,
                    sha256=reference_binding.sha256,
                    role=reference_binding.role,
                    producer=reference_binding.producer,
                    icc_profile_id=reference_header_binding.icc_profile_id,
                    icc_profile_sha256=reference_header_binding.icc_profile_sha256,
                    raw_icc_sha256=reference_header_binding.raw_icc_sha256,
                    canonical_icc_sha256=reference_header_binding.canonical_icc_sha256,
                    icc_canonicalization=reference_header_binding.icc_canonicalization,
                )
                actual_binding = _InputBinding(
                    path=actual_binding.path,
                    identity=actual_binding.identity,
                    sha256=actual_binding.sha256,
                    role=actual_binding.role,
                    producer=actual_binding.producer,
                    icc_profile_id=actual_header_binding.icc_profile_id,
                    icc_profile_sha256=actual_header_binding.icc_profile_sha256,
                    raw_icc_sha256=actual_header_binding.raw_icc_sha256,
                    canonical_icc_sha256=actual_header_binding.canonical_icc_sha256,
                    icc_canonicalization=actual_header_binding.icc_canonicalization,
                )
                input_bindings = (reference_binding, actual_binding)
                input_authority = "CONTRACT_BOUND_AUTHORITATIVE"
            else:
                input_bindings = ()
                input_authority = "UNBOUND_LOCAL_COMPARISON"
            reference_rgba = _decode_rgba(reference_image, reference_path)
            actual_rgba = _decode_rgba(actual_image, actual_path)
        finally:
            actual_image.close()
            actual_stream.close()
    finally:
        reference_image.close()
        reference_stream.close()

    mismatch, excluded_aa = pixelmatch_masks(
        reference_rgba,
        actual_rgba,
        threshold=profile.pixel_threshold,
        include_aa=not profile.anti_alias_detection,
        background=profile.rgba_background,
    )
    mismatch_count = int(mismatch.sum())
    excluded_count = int(excluded_aa.sum())
    match_ratio = 1.0 - mismatch_count / (width * height)

    reference_rgb = _composite_rgba(reference_rgba, profile.rgba_background)
    actual_rgb = _composite_rgba(actual_rgba, profile.rgba_background)
    minimum_axis = min(width, height)
    if minimum_axis < 3:
        ssim_score = _small_canvas_ssim(reference_rgb, actual_rgb)
    else:
        window_size = min(7, minimum_axis)
        if window_size % 2 == 0:
            window_size -= 1
        ssim_score = float(
            structural_similarity(
                reference_rgb,
                actual_rgb,
                channel_axis=2,
                data_range=255.0,
                win_size=window_size,
            )
        )
    rgba_delta = np.abs(reference_rgba.astype(np.float64) - actual_rgba.astype(np.float64)) / 255.0
    mean_rgba_error = float(np.mean(rgba_delta))
    alpha_mean_error = float(np.mean(rgba_delta[..., 3]))
    reference_edges = np.stack(
        [sobel(reference_rgb[..., channel] / profile.edge_normalization) for channel in range(3)],
        axis=2,
    )
    actual_edges = np.stack(
        [sobel(actual_rgb[..., channel] / profile.edge_normalization) for channel in range(3)],
        axis=2,
    )
    edge_error = float(np.mean(np.abs(reference_edges - actual_edges)))
    components = _components(mismatch)
    dense_regions = tuple(
        component
        for component in components
        if component.bounds[2] > profile.dense_bbox_exclusive_limit
        and component.bounds[3] > profile.dense_bbox_exclusive_limit
        and component.density >= profile.dense_density_minimum
    )
    max_diff_window = _max_window_count(mismatch, profile.dense_window_size)

    finite_metrics = (match_ratio, ssim_score, mean_rgba_error, alpha_mean_error, edge_error)
    if not all(math.isfinite(value) for value in finite_metrics):
        raise FidelityError("comparison produced a non-finite metric")

    failure_reasons: list[str] = []
    if match_ratio < profile.match_minimum:
        failure_reasons.append("MATCH_RATIO_BELOW_MINIMUM")
    if ssim_score < profile.ssim_minimum:
        failure_reasons.append("SSIM_BELOW_MINIMUM")
    if dense_regions:
        failure_reasons.append("DENSE_DIFF_REGION")
    if profile.mae_limit is not None and mean_rgba_error > profile.mae_limit:
        failure_reasons.append("MAE_LIMIT_EXCEEDED")

    mask_bytes = mismatch.tobytes(order="C")
    aa_bytes = excluded_aa.tobytes(order="C")
    diff_payload = _diff_png(mismatch, excluded_aa)
    diff_sha256 = hashlib.sha256(diff_payload).hexdigest()
    diff_path = (
        None
        if diff_output_path is None
        else _atomic_write(
            diff_output_path, diff_payload, write_constraints, input_bindings
        )
    )
    if input_bindings and diff_output_path is None:
        try:
            assert write_constraints is not None
            _revalidate_write_constraints(write_constraints, input_bindings)
        except RenderError as exc:
            raise FidelityError(str(exc)) from None
    passed = not failure_reasons
    return FidelityMetrics(
        width=width,
        height=height,
        profile_id=profile.profile_id,
        pixelmatch_version=profile.pixelmatch_version,
        pixel_threshold=profile.pixel_threshold,
        anti_alias_detection=profile.anti_alias_detection,
        match_minimum=profile.match_minimum,
        ssim_minimum=profile.ssim_minimum,
        mae_limit_version=profile.mae_limit_version,
        mae_limit=profile.mae_limit,
        edge_metric=profile.edge_metric,
        match_ratio=match_ratio,
        mismatch_count=mismatch_count,
        excluded_aa_count=excluded_count,
        ssim=ssim_score,
        mean_rgba_error=mean_rgba_error,
        alpha_mean_error=alpha_mean_error,
        edge_error=edge_error,
        max_diff_window=max_diff_window,
        components=components,
        dense_regions=dense_regions,
        mismatch_mask=mask_bytes,
        mismatch_mask_sha256=hashlib.sha256(mask_bytes).hexdigest(),
        excluded_aa_mask=aa_bytes,
        diff_path=diff_path,
        diff_sha256=diff_sha256,
        failure_reasons=tuple(failure_reasons),
        passed=passed,
        lifecycle_status=(
            "PIXEL_VERIFIED_DETERMINISTIC"
            if passed and input_authority == "CONTRACT_BOUND_AUTHORITATIVE"
            else "MEASURED"
        ),
        registry_digest=profile.registry_sha256,
        metric_max_pixels=profile.metric_max_pixels,
        metric_max_bytes=profile.metric_max_bytes,
        metric_budget_version=profile.metric_budget_version,
        reference_icc_profile_id=reference_header_binding.icc_profile_id,
        reference_icc_profile_sha256=reference_header_binding.icc_profile_sha256,
        reference_raw_icc_sha256=reference_header_binding.raw_icc_sha256,
        reference_canonical_icc_sha256=reference_header_binding.canonical_icc_sha256,
        reference_icc_canonicalization=reference_header_binding.icc_canonicalization,
        actual_icc_profile_id=actual_header_binding.icc_profile_id,
        actual_icc_profile_sha256=actual_header_binding.icc_profile_sha256,
        actual_raw_icc_sha256=actual_header_binding.raw_icc_sha256,
        actual_canonical_icc_sha256=actual_header_binding.canonical_icc_sha256,
        actual_icc_canonicalization=actual_header_binding.icc_canonicalization,
        input_authority=input_authority,
        input_bindings=tuple(
            ArtifactBindingEvidence(
                path=binding.path,
                role=binding.role,
                producer=binding.producer,
                sha256=binding.sha256,
                icc_profile_id=binding.icc_profile_id,
                icc_profile_sha256=binding.icc_profile_sha256,
                raw_icc_sha256=binding.raw_icc_sha256,
                canonical_icc_sha256=binding.canonical_icc_sha256,
                icc_canonicalization=binding.icc_canonicalization,
            )
            for binding in input_bindings
        ),
    )
