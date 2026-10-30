# SPDX-License-Identifier: MIT
"""Deterministic serialization from validated RIR into the safe SVG subset."""
from __future__ import annotations

import base64
import math
import os
import re
import stat
import xml.etree.ElementTree as ET
from io import BytesIO
from pathlib import Path, PurePosixPath
from typing import Any

from PIL import Image, UnidentifiedImageError

from .contracts import ContractError, validate_rir
from .svg_safety import (
    MAX_CANVAS_AXIS,
    MAX_EMBEDDED_PNG_BYTES,
    MAX_RASTER_PIXELS,
    SVG_NAMESPACE,
    SVG_DEFAULT_STROKE_LINECAP,
    SVG_DEFAULT_STROKE_LINEJOIN,
    SVG_DEFAULT_STROKE_MITERLIMIT,
    SVG_DEFAULT_STROKE_WIDTH,
    UnsafeSVGError,
    sanitize_svg,
    stroke_visual_padding,
    validate_canvas_dimensions,
    validate_font_size,
    validate_path_data,
)

_REPARSE_POINT = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
_PROJECT_PATH_SCHEME = re.compile(r"^[A-Za-z][A-Za-z0-9+.-]*:")
_MAX_NODES = 10_000
_MAX_NODE_DEPTH = 128


def _format_number(value: int | float) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise UnsafeSVGError("geometry requires a numeric value")
    number = float(value)
    if not math.isfinite(number):
        raise UnsafeSVGError("geometry contains a non-finite value")
    if number == 0:
        return "0"
    if number.is_integer():
        return str(int(number))
    return format(number, ".15g")


def _tag(name: str) -> str:
    return f"{{{SVG_NAMESPACE}}}{name}"


def _safe_id(node_id: str) -> str:
    import hashlib

    return "rir-" + hashlib.sha256(node_id.encode("utf-8")).hexdigest()[:24]


def _is_reparse(path: Path) -> bool:
    try:
        metadata = path.lstat()
    except OSError as exc:
        raise UnsafeSVGError(f"cannot inspect asset path safely: {exc}") from None
    return path.is_symlink() or bool(
        getattr(metadata, "st_file_attributes", 0) & _REPARSE_POINT
    )


def _assert_plain_components(root: Path, target: Path) -> None:
    current = Path(target.anchor)
    root_parts = len(root.parts)
    for index, part in enumerate(target.parts[1:] if target.anchor else target.parts, start=1):
        current /= part
        if index < root_parts:
            continue
        if not current.exists() and not current.is_symlink():
            raise UnsafeSVGError("raster asset path does not exist")
        if _is_reparse(current):
            raise UnsafeSVGError("raster asset crosses a symlink/reparse boundary")


def _validated_asset(asset_root: Path, reference: str) -> tuple[bytes, int, int]:
    if not isinstance(reference, str) or not reference or "\\" in reference:
        raise UnsafeSVGError("raster asset must use a non-empty POSIX relative path")
    if _PROJECT_PATH_SCHEME.match(reference):
        raise UnsafeSVGError("raster asset URL or URI scheme is forbidden")
    pure = PurePosixPath(reference)
    if pure.is_absolute() or any(part in {"", ".", ".."} for part in pure.parts):
        raise UnsafeSVGError("raster asset must not be absolute or parent-relative")
    lexical_root = Path(os.path.abspath(os.fspath(asset_root)))
    if not lexical_root.exists() or not lexical_root.is_dir() or _is_reparse(lexical_root):
        raise UnsafeSVGError("asset root must be an existing plain directory")
    try:
        exact_root = lexical_root.resolve(strict=True)
    except OSError as exc:
        raise UnsafeSVGError(f"cannot resolve asset root safely: {exc}") from None
    if exact_root != lexical_root:
        raise UnsafeSVGError("asset root resolves through a symlink/reparse boundary")
    lexical_target = exact_root.joinpath(*pure.parts)
    try:
        lexical_target.relative_to(exact_root)
    except ValueError:
        raise UnsafeSVGError("raster asset escapes asset root") from None
    _assert_plain_components(exact_root, lexical_target)
    try:
        exact_target = lexical_target.resolve(strict=True)
        exact_target.relative_to(exact_root)
    except (OSError, ValueError) as exc:
        raise UnsafeSVGError(f"raster asset escapes or cannot resolve safely: {exc}") from None
    if exact_target != lexical_target or not exact_target.is_file() or _is_reparse(exact_target):
        raise UnsafeSVGError("raster asset is not an exact plain file below asset root")
    if exact_target.suffix.casefold() != ".png":
        raise UnsafeSVGError("raster asset must have a .png extension")
    try:
        before = exact_target.stat()
        if before.st_size > MAX_EMBEDDED_PNG_BYTES:
            raise UnsafeSVGError("raster PNG exceeds the embedding size ceiling")
        payload = exact_target.read_bytes()
        after = exact_target.stat()
    except UnsafeSVGError:
        raise
    except OSError as exc:
        raise UnsafeSVGError(f"cannot read validated raster asset: {exc}") from None
    if not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise UnsafeSVGError("raster asset is not a PNG")
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format != "PNG":
                raise UnsafeSVGError("raster asset does not decode as PNG")
            dimensions = image.size
            if (
                image.width <= 0
                or image.height <= 0
                or image.width > MAX_CANVAS_AXIS
                or image.height > MAX_CANVAS_AXIS
                or image.width * image.height > MAX_RASTER_PIXELS
            ):
                raise UnsafeSVGError("raster PNG dimensions exceed the safety ceiling")
            image.verify()
    except UnsafeSVGError:
        raise
    except (OSError, ValueError, UnidentifiedImageError):
        raise UnsafeSVGError("raster PNG is corrupt") from None
    identity_fields = ("st_dev", "st_ino", "st_size", "st_mtime_ns")
    if any(getattr(before, name) != getattr(after, name) for name in identity_fields) or _is_reparse(exact_target):
        raise UnsafeSVGError("raster asset identity changed while it was read")
    return payload, dimensions[0], dimensions[1]


def _assert_bounds(bounds: dict[str, Any], width: float, height: float, field: str) -> None:
    x = float(bounds["x"])
    y = float(bounds["y"])
    bound_width = float(bounds["width"])
    bound_height = float(bounds["height"])
    if not all(math.isfinite(value) for value in (x, y, bound_width, bound_height)):
        raise UnsafeSVGError(f"{field}: bounds contain non-finite values")
    if bound_width < 0 or bound_height < 0 or x < 0 or y < 0:
        raise UnsafeSVGError(f"{field}: bounds are negative")
    if x + bound_width > width or y + bound_height > height:
        raise UnsafeSVGError(f"{field}: bounds exceed the canvas")


def _assert_geometry_within_declared_bounds(
    node: dict[str, Any],
    min_x: float,
    min_y: float,
    max_x: float,
    max_y: float,
    *,
    padding: float = 0,
) -> None:
    bounds = node["bounds"]
    if not (
        bounds["x"] <= min_x - padding
        and bounds["y"] <= min_y - padding
        and max_x + padding <= bounds["x"] + bounds["width"]
        and max_y + padding <= bounds["y"] + bounds["height"]
    ):
        raise UnsafeSVGError(
            f"node {node['id']!r}: vector geometry exceeds declared bounds"
        )


def _stroke_padding(
    node: dict[str, Any], canvas_width: float, canvas_height: float
) -> float:
    style = node.get("style", {})
    if style.get("stroke") in {None, "none"}:
        return 0
    width = float(style.get("strokeWidth", SVG_DEFAULT_STROKE_WIDTH))
    line_join = style.get("lineJoin", SVG_DEFAULT_STROKE_LINEJOIN)
    line_cap = style.get("lineCap", SVG_DEFAULT_STROKE_LINECAP)
    return stroke_visual_padding(
        width,
        line_join,
        line_cap,
        SVG_DEFAULT_STROKE_MITERLIMIT,
        canvas_width,
        canvas_height,
    )


def _paint_attributes(style: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    mapping = {
        "fill": "fill",
        "stroke": "stroke",
        "strokeWidth": "stroke-width",
        "fillRule": "fill-rule",
        "lineCap": "stroke-linecap",
        "lineJoin": "stroke-linejoin",
    }
    for source, target in mapping.items():
        value = style.get(source)
        if value is None:
            if source in {"fill", "stroke"}:
                result[target] = "none"
            continue
        result[target] = _format_number(value) if source == "strokeWidth" else str(value)
    if style.get("stroke") not in {None, "none"}:
        result["stroke-width"] = _format_number(
            style.get("strokeWidth", SVG_DEFAULT_STROKE_WIDTH)
        )
        result["stroke-linejoin"] = str(
            style.get("lineJoin", SVG_DEFAULT_STROKE_LINEJOIN)
        )
        result["stroke-linecap"] = str(
            style.get("lineCap", SVG_DEFAULT_STROKE_LINECAP)
        )
        result["stroke-miterlimit"] = _format_number(
            SVG_DEFAULT_STROKE_MITERLIMIT
        )
    return result


def _node_attributes(node: dict[str, Any]) -> dict[str, str]:
    attributes = {"id": _safe_id(node["id"])}
    if node["opacity"] != 1:
        attributes["opacity"] = _format_number(node["opacity"])
    if not node["visible"]:
        attributes["display"] = "none"
    if node["blendMode"] != "normal":
        attributes["style"] = f"mix-blend-mode:{node['blendMode']}"
    return attributes


def _assert_no_masks(node: dict[str, Any]) -> None:
    if node.get("masks"):
        raise UnsafeSVGError("RIR masks are not yet supported and cannot be silently dropped")


def _serialize_primitive(node: dict[str, Any], width: float, height: float) -> ET.Element:
    _assert_no_masks(node)
    primitive = node["primitive"]
    parameters = primitive["parameters"]
    common = _node_attributes(node) | _paint_attributes(node["style"])
    kind = primitive["kind"]
    if kind in {"rect", "ellipse", "line"}:
        required = {"x1", "y1", "x2", "y2"}
        optional = {"rx", "ry"} if kind == "rect" else set()
        if not required.issubset(parameters) or not set(parameters).issubset(required | optional):
            raise UnsafeSVGError(f"primitive {kind} requires exact bounded parameters")
        x1, y1, x2, y2 = (float(parameters[name]) for name in ("x1", "y1", "x2", "y2"))
        if not all(math.isfinite(value) for value in (x1, y1, x2, y2)):
            raise UnsafeSVGError("primitive contains non-finite geometry")
        if kind == "line":
            if not (
                0 <= x1 <= width
                and 0 <= x2 <= width
                and 0 <= y1 <= height
                and 0 <= y2 <= height
            ):
                raise UnsafeSVGError("line primitive geometry is outside the canvas")
        elif not (0 <= x1 <= x2 <= width and 0 <= y1 <= y2 <= height):
            raise UnsafeSVGError("primitive geometry is outside the canvas")
        _assert_geometry_within_declared_bounds(
            node,
            min(x1, x2),
            min(y1, y2),
            max(x1, x2),
            max(y1, y2),
            padding=_stroke_padding(node, width, height),
        )
        if kind == "rect":
            attrs = common | {
                "x": _format_number(x1),
                "y": _format_number(y1),
                "width": _format_number(x2 - x1),
                "height": _format_number(y2 - y1),
            }
            for radius in ("rx", "ry"):
                if radius in parameters:
                    value = float(parameters[radius])
                    if not math.isfinite(value) or value < 0:
                        raise UnsafeSVGError("rectangle radius is invalid")
                    attrs[radius] = _format_number(value)
            return ET.Element(_tag("rect"), attrs)
        if kind == "ellipse":
            return ET.Element(
                _tag("ellipse"),
                common
                | {
                    "cx": _format_number((x1 + x2) / 2),
                    "cy": _format_number((y1 + y2) / 2),
                    "rx": _format_number((x2 - x1) / 2),
                    "ry": _format_number((y2 - y1) / 2),
                },
            )
        return ET.Element(
            _tag("line"),
            common
            | {
                "x1": _format_number(x1),
                "y1": _format_number(y1),
                "x2": _format_number(x2),
                "y2": _format_number(y2),
            },
        )
    if kind == "polygon":
        if set(parameters) != {"points"} or len(parameters["points"]) < 3:
            raise UnsafeSVGError("polygon requires at least three points and no other parameters")
        points: list[str] = []
        for point in parameters["points"]:
            x, y = float(point["x"]), float(point["y"])
            if not (math.isfinite(x) and math.isfinite(y) and 0 <= x <= width and 0 <= y <= height):
                raise UnsafeSVGError("polygon point is outside the canvas")
            points.append(f"{_format_number(x)},{_format_number(y)}")
        xs = [float(point["x"]) for point in parameters["points"]]
        ys = [float(point["y"]) for point in parameters["points"]]
        _assert_geometry_within_declared_bounds(
            node,
            min(xs),
            min(ys),
            max(xs),
            max(ys),
            padding=_stroke_padding(node, width, height),
        )
        return ET.Element(_tag("polygon"), common | {"points": " ".join(points)})
    raise UnsafeSVGError(f"unsupported primitive kind: {kind}")


def _serialize_node(node: dict[str, Any], asset_root: Path, width: float, height: float) -> ET.Element:
    _assert_bounds(node["bounds"], width, height, f"node {node['id']!r}")
    node_type = node["type"]
    if node_type == "group":
        element = ET.Element(_tag("g"), _node_attributes(node))
        for child in sorted(node["children"], key=lambda item: item["zOrder"]):
            child_bounds = child["bounds"]
            _assert_geometry_within_declared_bounds(
                node,
                child_bounds["x"],
                child_bounds["y"],
                child_bounds["x"] + child_bounds["width"],
                child_bounds["y"] + child_bounds["height"],
            )
            element.append(_serialize_node(child, asset_root, width, height))
        return element
    if node_type == "primitive":
        return _serialize_primitive(node, width, height)
    if node_type == "path":
        _assert_no_masks(node)
        path_data = node["geometry"]["pathData"]
        inspection = validate_path_data(path_data, width, height)
        declared_closed = bool(node["geometry"].get("closed", False))
        if declared_closed and not inspection.every_subpath_closed:
            raise UnsafeSVGError("path closed metadata requires every subpath closed")
        if not declared_closed and not inspection.no_subpath_closed:
            raise UnsafeSVGError("path closed metadata requires every subpath open")
        _assert_geometry_within_declared_bounds(
            node,
            inspection.min_x,
            inspection.min_y,
            inspection.max_x,
            inspection.max_y,
            padding=_stroke_padding(node, width, height),
        )
        return ET.Element(
            _tag("path"),
            _node_attributes(node) | _paint_attributes(node["style"]) | {"d": path_data},
        )
    if node_type == "text":
        payload = node["text"]
        disposition = payload["disposition"]
        fallback = payload["outlineFallback"]
        if disposition == "outlined":
            if not fallback["available"] or not fallback["pathData"]:
                raise UnsafeSVGError("outlined text requires a validated path fallback")
            inspection = validate_path_data(fallback["pathData"], width, height)
            _assert_geometry_within_declared_bounds(
                node,
                inspection.min_x,
                inspection.min_y,
                inspection.max_x,
                inspection.max_y,
            )
            return ET.Element(
                _tag("path"),
                _node_attributes(node) | {"d": fallback["pathData"], "fill": "black"},
            )
        if disposition == "hybrid":
            raise UnsafeSVGError("hybrid text is not yet supported and cannot be silently flattened")
        if disposition != "live" or not payload["fontCandidates"]:
            raise UnsafeSVGError("live text requires at least one font candidate")
        candidate = sorted(
            payload["fontCandidates"],
            key=lambda item: (-item["confidence"], item["family"], item["weight"], item["style"]),
        )[0]
        bounds = node["bounds"]
        validate_font_size(float(bounds["height"]), width, height)
        element = ET.Element(
            _tag("text"),
            _node_attributes(node)
            | {
                "x": _format_number(bounds["x"]),
                "y": _format_number(bounds["y"] + bounds["height"]),
                "font-family": candidate["family"],
                "font-weight": str(candidate["weight"]),
                "font-style": candidate["style"],
                "font-size": _format_number(bounds["height"]),
                "fill": "black",
            },
        )
        element.text = payload["content"]
        return element
    if node_type == "raster":
        payload, pixel_width, pixel_height = _validated_asset(
            asset_root, node["raster"]["path"]
        )
        crop = node["raster"]["crop"]
        if (
            crop["x"] != 0
            or crop["y"] != 0
            or crop["width"] != pixel_width
            or crop["height"] != pixel_height
        ):
            raise UnsafeSVGError(
                "raster crop must exactly describe the tightly cropped embedded PNG"
            )
        bounds = node["bounds"]
        attributes = _node_attributes(node) | {
            "x": _format_number(bounds["x"]),
            "y": _format_number(bounds["y"]),
            "width": _format_number(bounds["width"]),
            "height": _format_number(bounds["height"]),
            "href": "data:image/png;base64," + base64.b64encode(payload).decode("ascii"),
            "preserveAspectRatio": "none",
        }
        if node["raster"]["alpha"] != 1:
            attributes["opacity"] = _format_number(node["raster"]["alpha"] * node["opacity"])
        return ET.Element(_tag("image"), attributes)
    raise UnsafeSVGError(f"unsupported RIR node type: {node_type}")


def _count_nodes(nodes: list[dict[str, Any]]) -> int:
    count = 0
    stack = [(node, 0) for node in nodes]
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > _MAX_NODES:
            raise UnsafeSVGError("RIR exceeds the node complexity ceiling")
        if depth > _MAX_NODE_DEPTH:
            raise UnsafeSVGError("RIR nesting depth exceeds the complexity ceiling")
        if isinstance(node, dict) and node.get("type") == "group" and isinstance(node.get("children"), list):
            stack.extend((child, depth + 1) for child in node["children"])
    return count


def serialize_svg(rir: dict, asset_root: Path) -> bytes:
    """Serialize validated RIR to canonical, self-contained safe SVG bytes."""

    if not isinstance(asset_root, Path):
        asset_root = Path(asset_root)
    if isinstance(rir, dict) and isinstance(rir.get("layers"), list):
        _count_nodes(rir["layers"])
    try:
        validate_rir(rir)
    except ContractError:
        raise
    canvas = rir["canvas"]
    width, height = float(canvas["width"]), float(canvas["height"])
    validate_canvas_dimensions(width, height)
    root = ET.Element(
        _tag("svg"),
        {
            "width": _format_number(width),
            "height": _format_number(height),
            "viewBox": f"0 0 {_format_number(width)} {_format_number(height)}",
            "version": "1.1",
        },
    )
    if "background" in canvas:
        root.append(
            ET.Element(
                _tag("rect"),
                {
                    "x": "0",
                    "y": "0",
                    "width": _format_number(width),
                    "height": _format_number(height),
                    "fill": canvas["background"]["color"],
                },
            )
        )
    for node in sorted(rir["layers"], key=lambda item: item["zOrder"]):
        root.append(_serialize_node(node, asset_root, width, height))
    raw = ET.tostring(root, encoding="utf-8", short_empty_elements=True)
    return sanitize_svg(raw)
