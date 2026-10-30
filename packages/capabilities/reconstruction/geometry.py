# SPDX-License-Identifier: MIT
"""Closed, deterministic geometry normalization for untrusted proposals."""
from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from PIL import Image


class ProposalValidationError(ValueError):
    """A model proposal is malformed, unsafe, or geometrically degenerate."""


_DIRECTIONS = {"ltr", "rtl", "ttb"}
_PRIMITIVE_KINDS = {"rectangle", "circle", "gradient"}


def _finite_number(value: Any, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ProposalValidationError(f"{label} must be finite")
    return float(value)


def _canvas_size(canvas: Sequence[int | float]) -> tuple[float, float]:
    if not isinstance(canvas, Sequence) or isinstance(canvas, (str, bytes)) or len(canvas) != 2:
        raise ProposalValidationError("canvas must contain width and height")
    width, height = (_finite_number(value, "canvas dimension") for value in canvas)
    if width <= 0 or height <= 0:
        raise ProposalValidationError("canvas dimensions must be positive")
    return width, height


def _clamp(value: float, maximum: float) -> float:
    return min(max(value, 0.0), maximum)


def _polygon_area(points: Sequence[tuple[float, float]]) -> float:
    return abs(sum(
        first[0] * second[1] - second[0] * first[1]
        for first, second in zip(points, points[1:] + points[:1])
    )) / 2.0


@dataclass(frozen=True)
class TextHypothesis:
    """OCR text with polygon coordinates normalized to the complete canvas."""

    text: str
    polygon: tuple[tuple[float, float], ...]
    confidence: float
    direction: str = "ltr"

    def __post_init__(self) -> None:
        if not isinstance(self.text, str) or not self.text.strip() or len(self.text) > 4096:
            raise ProposalValidationError("text must be a non-empty bounded string")
        if not isinstance(self.direction, str) or self.direction not in _DIRECTIONS:
            raise ProposalValidationError("direction is not in the closed direction set")
        if not (isinstance(self.polygon, tuple) and 3 <= len(self.polygon) <= 64):
            raise ProposalValidationError("polygon must contain between three and sixty-four points")
        normalized: list[tuple[float, float]] = []
        for index, point in enumerate(self.polygon):
            if not isinstance(point, tuple) or len(point) != 2:
                raise ProposalValidationError(f"polygon[{index}] must be a coordinate pair")
            x = _finite_number(point[0], f"polygon[{index}].x")
            y = _finite_number(point[1], f"polygon[{index}].y")
            if not 0.0 <= x <= 1.0 or not 0.0 <= y <= 1.0:
                raise ProposalValidationError("polygon coordinates must be normalized to the global canvas")
            normalized.append((x, y))
        if _polygon_area(normalized) <= 1e-12:
            raise ProposalValidationError("polygon is degenerate after canvas clamping")
        confidence = _finite_number(self.confidence, "confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ProposalValidationError("confidence outside [0, 1]")
        object.__setattr__(self, "polygon", tuple(normalized))
        object.__setattr__(self, "confidence", confidence)


@dataclass(frozen=True)
class PrimitiveHypothesis:
    """A deterministic primitive proposal in normalized global coordinates."""

    kind: str
    bounds: tuple[float, float, float, float]
    fill: str | None
    stroke: str | None
    radius: tuple[float, float] | None
    confidence: float

    def __post_init__(self) -> None:
        if not isinstance(self.kind, str) or self.kind not in _PRIMITIVE_KINDS:
            raise ProposalValidationError("primitive kind is not in the closed kind set")
        if not isinstance(self.bounds, tuple) or len(self.bounds) != 4:
            raise ProposalValidationError("bounds must be a four-value normalized rectangle")
        left, top, right, bottom = (_finite_number(value, "bounds") for value in self.bounds)
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ProposalValidationError("bounds must be non-degenerate global normalized coordinates")
        if self.fill is not None and (not isinstance(self.fill, str) or not self.fill or len(self.fill) > 128):
            raise ProposalValidationError("fill must be a bounded color description or null")
        if self.stroke is not None and (not isinstance(self.stroke, str) or not self.stroke or len(self.stroke) > 128):
            raise ProposalValidationError("stroke must be a bounded color description or null")
        if self.radius is not None:
            if not isinstance(self.radius, tuple) or len(self.radius) != 2:
                raise ProposalValidationError("radius must be a normalized x/y pair or null")
            radius_x = _finite_number(self.radius[0], "radius.x")
            radius_y = _finite_number(self.radius[1], "radius.y")
            if radius_x < 0 or radius_y < 0 or radius_x > (right - left) / 2 + 1e-12 or radius_y > (bottom - top) / 2 + 1e-12:
                raise ProposalValidationError("radius is invalid for bounds")
            object.__setattr__(self, "radius", (radius_x, radius_y))
        confidence = _finite_number(self.confidence, "confidence")
        if not 0.0 <= confidence <= 1.0:
            raise ProposalValidationError("confidence outside [0, 1]")
        object.__setattr__(self, "bounds", (left, top, right, bottom))
        object.__setattr__(self, "confidence", confidence)


def clamp_polygon(points: Any, canvas: Sequence[int | float]) -> tuple[tuple[float, float], ...]:
    """Clamp pixel-space points then return canonical global normalized coordinates."""

    width, height = _canvas_size(canvas)
    if not isinstance(points, (list, tuple)) or not 3 <= len(points) <= 64:
        raise ProposalValidationError("polygon must contain between three and sixty-four points")
    normalized: list[tuple[float, float]] = []
    for index, point in enumerate(points):
        if not isinstance(point, (list, tuple)) or len(point) != 2:
            raise ProposalValidationError(f"polygon[{index}] must be a coordinate pair")
        x = _clamp(_finite_number(point[0], f"polygon[{index}].x"), width) / width
        y = _clamp(_finite_number(point[1], f"polygon[{index}].y"), height) / height
        normalized.append((x, y))
    if _polygon_area(normalized) <= 1e-12:
        raise ProposalValidationError("polygon is degenerate after canvas clamping")
    return tuple(normalized)


def normalize_text_detection(raw: Mapping[str, Any], canvas: Sequence[int | float]) -> TextHypothesis:
    """Convert one OCR response into a closed, global-coordinate hypothesis."""

    if not isinstance(raw, Mapping) or set(raw) not in ({"text", "polygon", "confidence"}, {"text", "polygon", "confidence", "direction"}):
        raise ProposalValidationError("OCR detection has unknown or missing fields")
    return TextHypothesis(
        raw["text"],
        clamp_polygon(raw["polygon"], canvas),
        _finite_number(raw["confidence"], "confidence"),
        raw.get("direction", "ltr"),
    )


def normalize_primitive_detection(raw: Mapping[str, Any], canvas: Sequence[int | float]) -> PrimitiveHypothesis:
    """Convert a model/classical primitive response into closed normalized geometry."""

    expected = {"kind", "bounds", "fill", "stroke", "radius", "confidence"}
    if not isinstance(raw, Mapping) or set(raw) != expected:
        raise ProposalValidationError("primitive detection has unknown or missing fields")
    width, height = _canvas_size(canvas)
    bounds = raw["bounds"]
    if not isinstance(bounds, (list, tuple)) or len(bounds) != 4:
        raise ProposalValidationError("primitive bounds must be x, y, width, height")
    x, y, extent_x, extent_y = (_finite_number(value, "bounds") for value in bounds)
    left, top = _clamp(x, width), _clamp(y, height)
    right, bottom = _clamp(x + extent_x, width), _clamp(y + extent_y, height)
    if right <= left or bottom <= top:
        raise ProposalValidationError("primitive bounds are degenerate after canvas clamping")
    radius = raw["radius"]
    if radius is not None:
        # Raw radius is in reference pixels; retain both global canvas axes.
        radius_value = _finite_number(radius, "radius")
        radius = (radius_value / width, radius_value / height)
    return PrimitiveHypothesis(
        raw["kind"], (left / width, top / height, right / width, bottom / height), raw["fill"], raw["stroke"], radius, raw["confidence"],
    )


def _hex(pixel: tuple[int, int, int, int]) -> str:
    return "#" + "".join(f"{part:02x}" for part in pixel[:3])


def _is_continuous_gradient(values: Sequence[tuple[int, int, int, int]]) -> bool:
    if len(set(values)) < 3:
        return False
    for channel in range(4):
        samples = [value[channel] for value in values]
        if all(left <= right for left, right in zip(samples, samples[1:])) or all(
            left >= right for left, right in zip(samples, samples[1:])
        ):
            if samples[0] != samples[-1]:
                return True
    return False


def _full_canvas_axis_gradient(pixels: Any, width: int, height: int) -> tuple[str, tuple[int, int, int, int], tuple[int, int, int, int]] | None:
    horizontal = [pixels[x, 0] for x in range(width)]
    if _is_continuous_gradient(horizontal) and all(
        [pixels[x, y] for x in range(width)] == horizontal for y in range(height)
    ):
        return "horizontal", horizontal[0], horizontal[-1]
    vertical = [pixels[0, y] for y in range(height)]
    if _is_continuous_gradient(vertical) and all(
        [pixels[x, y] for y in range(height)] == vertical for x in range(width)
    ):
        return "vertical", vertical[0], vertical[-1]
    return None


def analyze_primitives(image: Image.Image | Path) -> tuple[PrimitiveHypothesis, ...]:
    """Classify one flat fixture as rectangle, circle, or gradient without a model."""

    close = False
    if isinstance(image, Path):
        image = Image.open(image)
        close = True
    try:
        rgba = image.convert("RGBA")
        width, height = rgba.size
        pixels = rgba.load()
        all_pixels = [pixels[x, y] for y in range(height) for x in range(width)]
        colors = set(all_pixels)
        if len(colors) == 1:
            return (PrimitiveHypothesis("rectangle", (0.0, 0.0, 1.0, 1.0), _hex(all_pixels[0]), None, (0.0, 0.0), 1.0),)
        axis_gradient = _full_canvas_axis_gradient(pixels, width, height)
        if axis_gradient is not None:
            direction, start, end = axis_gradient
            return (PrimitiveHypothesis("gradient", (0.0, 0.0, 1.0, 1.0), f"{direction}({_hex(start)},{_hex(end)})", None, None, 1.0),)
        border = [
            pixels[x, y]
            for x, y in {
                *((x, 0) for x in range(width)),
                *((x, height - 1) for x in range(width)),
                *((0, y) for y in range(height)),
                *((width - 1, y) for y in range(height)),
            }
        ]
        background = Counter(border).most_common(1)[0][0]
        foreground = [(x, y) for y in range(height) for x in range(width) if pixels[x, y] != background]
        if not foreground:
            return (PrimitiveHypothesis("gradient", (0.0, 0.0, 1.0, 1.0), f"linear({_hex(all_pixels[0])},{_hex(all_pixels[-1])})", None, None, 1.0),)
        left, right = min(x for x, _ in foreground), max(x for x, _ in foreground) + 1
        top, bottom = min(y for _, y in foreground), max(y for _, y in foreground) + 1
        colors = {pixels[x, y] for x, y in foreground}
        bounds = (left / width, top / height, right / width, bottom / height)
        if len(colors) > 2:
            return (PrimitiveHypothesis("gradient", bounds, f"linear({_hex(pixels[left, top])},{_hex(pixels[right - 1, top])})", None, None, 1.0),)
        corners = ((left, top), (right - 1, top), (left, bottom - 1), (right - 1, bottom - 1))
        kind = "circle" if any(pixels[x, y] == background for x, y in corners) else "rectangle"
        fill = _hex(next(iter(colors)))
        radius = ((right - left) / (2 * width), (bottom - top) / (2 * height)) if kind == "circle" else (0.0, 0.0)
        return (PrimitiveHypothesis(kind, bounds, fill, None, radius, 1.0),)
    finally:
        if close:
            image.close()
