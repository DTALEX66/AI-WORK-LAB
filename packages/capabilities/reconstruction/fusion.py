# SPDX-License-Identifier: MIT
"""Fail-closed fusion of normalized transparent layers into reconstruction RIR."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence
from defusedxml import ElementTree as DefusedET

from .contracts import validate_rir
from .matting import LayerProposal
from .svg_safety import sanitize_svg
from .vector_candidates import VectorCandidate, select_candidates_by_object


PROJECT_ROOT = Path(__file__).resolve().parents[3]
_RASTER_BUDGET_PROFILES = frozenset({"flat", "ui"})


class ReferenceOverlayError(ValueError):
    """An opaque full-canvas reference raster was offered as reconstructed content."""


class RasterBudgetExceeded(ValueError):
    """A profile exceeded its bounded semantic-raster allowance."""


@dataclass(frozen=True)
class SceneAnalysis:
    width: int
    height: int
    profile: str


def _bounds(crop: tuple[int, int, int, int]) -> dict[str, int]:
    left, top, right, bottom = crop
    return {"x": left, "y": top, "width": right - left, "height": bottom - top}


def _relative_project_path(path: Path) -> str:
    try:
        return path.resolve(strict=False).relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        raise ReferenceOverlayError("layer raster path escapes the project") from None


def _area(layer: LayerProposal) -> int:
    left, top, right, bottom = layer.crop
    return max(0, right - left) * max(0, bottom - top)


def _reference_overlay(analysis: SceneAnalysis, layer: LayerProposal) -> bool:
    full_canvas = layer.crop == (0, 0, analysis.width, analysis.height)
    semantic = layer.semantic_name.lower()
    return full_canvas and not layer.inferred and "reference" in semantic


def _raster_node(layer: LayerProposal) -> dict:
    bounds = _bounds(layer.crop)
    return {
        "id": layer.id,
        "type": "raster",
        "name": layer.semantic_name,
        "opacity": 1.0,
        "bounds": bounds,
        "inferred": layer.inferred,
        "zOrder": layer.z_index,
        "visible": True,
        "locked": False,
        "blendMode": "normal",
        "raster": {
            "path": _relative_project_path(layer.asset_path),
            "crop": bounds,
            "alpha": 1.0,
            "sourceMappings": [],
        },
    }


def _local_name(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _number(attributes: dict[str, str], name: str, default: float = 0.0) -> float:
    value = attributes.get(name)
    if value is None:
        return default
    try:
        return float(value)
    except ValueError:
        raise ValueError(f"sanitized SVG {name} is not a number") from None


def _style(attributes: dict[str, str]) -> dict:
    style: dict[str, object] = {"fill": attributes.get("fill"), "stroke": attributes.get("stroke")}
    if "stroke-width" in attributes:
        style["strokeWidth"] = _number(attributes, "stroke-width")
    return style


def _candidate_nodes(candidate: VectorCandidate, z_start: int) -> list[dict]:
    """Convert a sanitized SVG subset into editable RIR primitives/path nodes."""

    root = DefusedET.fromstring(sanitize_svg(candidate.svg_fragment))
    nodes: list[dict] = []
    for index, element in enumerate(list(root)):
        kind = _local_name(element.tag)
        attributes = dict(element.attrib)
        node_id = candidate.object_id if index == 0 else f"{candidate.object_id}-{index}"
        if kind == "rect":
            x = _number(attributes, "x")
            y = _number(attributes, "y")
            width = _number(attributes, "width")
            height = _number(attributes, "height")
            if width < 0 or height < 0:
                raise ValueError("sanitized SVG rectangle dimensions are negative")
            parameters: dict[str, float] = {"x1": x, "y1": y, "x2": x + width, "y2": y + height}
            if "rx" in attributes:
                parameters["rx"] = _number(attributes, "rx")
            if "ry" in attributes:
                parameters["ry"] = _number(attributes, "ry")
            nodes.append({
                "id": node_id,
                "type": "primitive",
                "name": candidate.object_id,
                "opacity": _number(attributes, "opacity", 1.0),
                "bounds": {"x": x, "y": y, "width": width, "height": height},
                "inferred": False,
                "zOrder": z_start + index,
                "visible": True,
                "locked": False,
                "blendMode": "normal",
                "primitive": {"kind": "rect", "parameters": parameters},
                "style": _style(attributes),
                "masks": [],
            })
        elif kind == "path" and "d" in attributes:
            nodes.append({
                "id": node_id,
                "type": "path",
                "name": candidate.object_id,
                "opacity": _number(attributes, "opacity", 1.0),
                "bounds": {"x": 0.0, "y": 0.0, "width": 0.0, "height": 0.0},
                "inferred": False,
                "zOrder": z_start + index,
                "visible": True,
                "locked": False,
                "blendMode": "normal",
                "geometry": {"pathData": attributes["d"], "closed": True},
                "style": _style(attributes),
                "masks": [],
            })
        else:
            raise ValueError(f"sanitized SVG element is not editable RIR input: {kind}")
    if not nodes:
        raise ValueError("sanitized SVG candidate contains no editable nodes")
    return nodes


def fuse_scene(
    analysis: SceneAnalysis,
    layers: Sequence[LayerProposal],
    candidates: Sequence[VectorCandidate],
) -> dict:
    """Fuse only bounded semantic rasters; vector candidates remain sanitized proposals."""

    if (
        isinstance(analysis.width, bool)
        or isinstance(analysis.height, bool)
        or not isinstance(analysis.width, int)
        or not isinstance(analysis.height, int)
        or analysis.width <= 0
        or analysis.height <= 0
    ):
        raise ValueError("scene canvas dimensions must be positive integers")
    if any(_reference_overlay(analysis, layer) for layer in layers):
        raise ReferenceOverlayError("full-canvas reference layer is forbidden")
    if analysis.profile in _RASTER_BUDGET_PROFILES:
        covered = sum(_area(layer) for layer in layers)
        if covered > analysis.width * analysis.height * 0.05:
            raise RasterBudgetExceeded("flat/UI semantic raster area exceeds 5 percent")
    vector_nodes: list[dict] = []
    for selected in select_candidates_by_object(tuple(candidates)):
        vector_nodes.extend(_candidate_nodes(selected, len(layers) + len(vector_nodes)))
    rir = {
        "schemaVersion": "design-lab/reconstruction-ir/v1",
        "canvas": {"width": analysis.width, "height": analysis.height, "colorSpace": "srgb"},
        "layers": [
            *[_raster_node(layer) for layer in sorted(layers, key=lambda item: (item.z_index, item.id))],
            *vector_nodes,
        ],
    }
    validate_rir(rir)
    return rir
