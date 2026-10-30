# SPDX-License-Identifier: MIT
"""Fail-closed validation and canonicalization for the supported SVG subset."""
from __future__ import annotations

import base64
import binascii
import math
import re
import xml.etree.ElementTree as StdET
from dataclasses import dataclass
from io import BytesIO
from typing import Iterator

from defusedxml import ElementTree as DefusedET
from defusedxml.common import DefusedXmlException
from PIL import Image, UnidentifiedImageError

SVG_NAMESPACE = "http://www.w3.org/2000/svg"
XLINK_NAMESPACE = "http://www.w3.org/1999/xlink"
SVG_DEFAULT_STROKE_WIDTH = 1.0
SVG_DEFAULT_STROKE_LINEJOIN = "miter"
SVG_DEFAULT_STROKE_LINECAP = "butt"
SVG_DEFAULT_STROKE_MITERLIMIT = 4.0
StdET.register_namespace("", SVG_NAMESPACE)
MAX_SVG_BYTES = 16 * 1024 * 1024
MAX_EMBEDDED_PNG_BYTES = 12 * 1024 * 1024
MAX_ELEMENTS = 10_000
MAX_NESTING_DEPTH = 128
MAX_ATTRIBUTE_LENGTH = 2_000_000
MAX_TEXT_LENGTH = 1_000_000
MAX_PATH_BYTES = 1_000_000
MAX_PATH_COMMANDS = 100_000
MAX_POLYGON_POINTS = 100_000
MAX_CANVAS_AXIS = 65_536
MAX_CANVAS_PIXELS = 100_000_000
MAX_RASTER_PIXELS = 100_000_000
MAX_STROKE_MITERLIMIT = 16.0


class UnsafeSVGError(ValueError):
    """SVG bytes violate the deterministic renderer safety profile."""


@dataclass(frozen=True)
class PathInspection:
    """Conservative geometry and closure facts derived from validated path tokens."""

    min_x: float
    min_y: float
    max_x: float
    max_y: float
    subpaths_closed: tuple[bool, ...]

    @property
    def has_close(self) -> bool:
        return any(self.subpaths_closed)

    @property
    def every_subpath_closed(self) -> bool:
        return bool(self.subpaths_closed) and all(self.subpaths_closed)

    @property
    def no_subpath_closed(self) -> bool:
        return not any(self.subpaths_closed)


_COMMON_PAINT = frozenset(
    {
        "id",
        "fill",
        "stroke",
        "stroke-width",
        "fill-rule",
        "stroke-linecap",
        "stroke-linejoin",
        "stroke-miterlimit",
        "opacity",
        "display",
        "clip-path",
        "mask",
        "style",
    }
)
ALLOWED_ATTRIBUTES: dict[str, frozenset[str]] = {
    "svg": frozenset({"width", "height", "viewBox", "version"}),
    "g": frozenset({"id", "opacity", "display", "clip-path", "mask", "style"}),
    "path": _COMMON_PAINT | {"d"},
    "rect": _COMMON_PAINT | {"x", "y", "width", "height", "rx", "ry"},
    "circle": _COMMON_PAINT | {"cx", "cy", "r"},
    "ellipse": _COMMON_PAINT | {"cx", "cy", "rx", "ry"},
    "line": _COMMON_PAINT | {"x1", "y1", "x2", "y2"},
    "polyline": _COMMON_PAINT | {"points"},
    "polygon": _COMMON_PAINT | {"points"},
    "text": frozenset(
        {
            "id",
            "x",
            "y",
            "fill",
            "opacity",
            "display",
            "font-family",
            "font-size",
            "font-style",
            "font-weight",
            "text-anchor",
            "style",
            "clip-path",
            "mask",
        }
    ),
    "defs": frozenset({"id"}),
    "linearGradient": frozenset(
        {"id", "x1", "y1", "x2", "y2", "gradientUnits"}
    ),
    "radialGradient": frozenset(
        {"id", "cx", "cy", "r", "fx", "fy", "gradientUnits"}
    ),
    "stop": frozenset({"offset", "stop-color", "stop-opacity"}),
    "clipPath": frozenset({"id", "clipPathUnits"}),
    "mask": frozenset({"id", "maskUnits", "x", "y", "width", "height"}),
    "image": frozenset(
        {
            "id",
            "x",
            "y",
            "width",
            "height",
            "href",
            "opacity",
            "display",
            "preserveAspectRatio",
            "clip-path",
            "mask",
            "style",
        }
    ),
}
ALLOWED_ELEMENTS = frozenset(ALLOWED_ATTRIBUTES)

_NUMBER = r"[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?"
_NUMBER_RE = re.compile(rf"^{_NUMBER}$")
_PATH_TOKEN_RE = re.compile(rf"[AaCcHhLlMmQqSsTtVvZz]|{_NUMBER}")
_SEPARATOR_RE = re.compile(r"^[\s,]*$")
_COLOR_HEX_RE = re.compile(r"^#(?:[0-9a-fA-F]{3}|[0-9a-fA-F]{4}|[0-9a-fA-F]{6}|[0-9a-fA-F]{8})$")
_ID_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_.:-]{0,255}$")
_INTERNAL_REFERENCE_RE = re.compile(r"^url\(#[A-Za-z_][A-Za-z0-9_.:-]{0,255}\)$")
_DATA_PNG_PREFIX = "data:image/png;base64,"
_CONTROL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")

_NUMERIC_ATTRIBUTES = frozenset(
    {
        "x",
        "y",
        "x1",
        "y1",
        "x2",
        "y2",
        "cx",
        "cy",
        "r",
        "rx",
        "ry",
        "width",
        "height",
        "stroke-width",
        "stroke-miterlimit",
        "opacity",
        "stop-opacity",
        "font-size",
        "fx",
        "fy",
    }
)
_PATH_ARITY = {
    "M": 2,
    "L": 2,
    "H": 1,
    "V": 1,
    "C": 6,
    "S": 4,
    "Q": 4,
    "T": 2,
    "A": 7,
    "Z": 0,
}


def _split_expanded_name(name: str) -> tuple[str, str]:
    if name.startswith("{"):
        namespace, separator, local = name[1:].partition("}")
        if not separator or not local:
            raise UnsafeSVGError(f"malformed XML expanded name: {name!r}")
        return namespace, local
    return "", name


def _number(value: str, field: str) -> float:
    if not _NUMBER_RE.fullmatch(value):
        raise UnsafeSVGError(f"{field}: expected a finite decimal number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise UnsafeSVGError(f"{field}: non-finite number")
    return parsed


def validate_canvas_dimensions(width: float, height: float) -> None:
    """Apply the fixed renderer's per-axis and total-pixel canvas limits."""

    if not (
        math.isfinite(width)
        and math.isfinite(height)
        and 0 < width <= MAX_CANVAS_AXIS
        and 0 < height <= MAX_CANVAS_AXIS
    ):
        raise UnsafeSVGError("canvas dimensions exceed the supported axis range")
    pixels = width * height
    if not math.isfinite(pixels) or pixels > MAX_CANVAS_PIXELS:
        raise UnsafeSVGError("canvas dimensions exceed the total pixel ceiling")


def stroke_visual_padding(
    stroke_width: float,
    line_join: str,
    line_cap: str,
    miter_limit: float,
    canvas_width: float,
    canvas_height: float,
) -> float:
    """Validate finite SVG stroke expansion and return conservative padding."""

    product = stroke_width * miter_limit
    if not math.isfinite(product):
        raise UnsafeSVGError("stroke-width/miterlimit product is non-finite")
    maximum_dimension = max(canvas_width, canvas_height)
    if not math.isfinite(stroke_width) or not 0 <= stroke_width <= maximum_dimension:
        raise UnsafeSVGError("stroke-width exceeds the canvas-derived safe limit")
    if not math.isfinite(miter_limit) or not 1 <= miter_limit <= MAX_STROKE_MITERLIMIT:
        raise UnsafeSVGError("stroke-miterlimit exceeds the qualified range")
    if product > 2 * maximum_dimension:
        raise UnsafeSVGError("stroke visual extent exceeds the canvas-derived safe limit")
    if line_join not in {"miter", "round", "bevel"}:
        raise UnsafeSVGError("unsupported stroke-linejoin")
    if line_cap not in {"butt", "round", "square"}:
        raise UnsafeSVGError("unsupported stroke-linecap")
    join_padding = product / 2 if line_join == "miter" else stroke_width / 2
    cap_padding = stroke_width / 2 if line_cap in {"round", "square"} else 0
    return max(join_padding, cap_padding)


def validate_font_size(font_size: float, width: float, height: float) -> None:
    if not (
        math.isfinite(font_size)
        and 0 < font_size <= max(width, height)
    ):
        raise UnsafeSVGError("font-size must be positive and within the canvas profile")


def _validate_color(value: str, field: str) -> None:
    if value in {"none", "transparent", "black", "white"} or _COLOR_HEX_RE.fullmatch(value):
        return
    raise UnsafeSVGError(f"{field}: unsupported or unsafe color")


def _validate_style(value: str) -> None:
    if "url" in value.casefold() or "javascript" in value.casefold() or "expression" in value.casefold():
        raise UnsafeSVGError("style: URL or script behavior is forbidden")
    declarations = [part.strip() for part in value.split(";") if part.strip()]
    if len(declarations) != 1:
        raise UnsafeSVGError("style: only one allowlisted declaration is supported")
    name, separator, style_value = declarations[0].partition(":")
    if separator != ":" or name.strip() != "mix-blend-mode":
        raise UnsafeSVGError("style: unsupported CSS property")
    if style_value.strip() not in {"normal", "multiply", "screen", "overlay", "darken", "lighten"}:
        raise UnsafeSVGError("style: unsupported blend mode")


def _validate_png_data_uri(value: str) -> None:
    if not value.startswith(_DATA_PNG_PREFIX):
        raise UnsafeSVGError("image href must be an embedded PNG data URI")
    encoded = value[len(_DATA_PNG_PREFIX) :]
    if not encoded or len(encoded) > ((MAX_EMBEDDED_PNG_BYTES + 2) // 3) * 4:
        raise UnsafeSVGError("embedded PNG is empty or exceeds the size ceiling")
    try:
        payload = base64.b64decode(encoded, validate=True)
    except (binascii.Error, ValueError):
        raise UnsafeSVGError("embedded PNG base64 is malformed") from None
    if len(payload) > MAX_EMBEDDED_PNG_BYTES or not payload.startswith(b"\x89PNG\r\n\x1a\n"):
        raise UnsafeSVGError("embedded image is not a PNG")
    try:
        with Image.open(BytesIO(payload)) as image:
            if image.format != "PNG":
                raise UnsafeSVGError("embedded image is not a decoded PNG")
            if (
                image.width <= 0
                or image.height <= 0
                or image.width > MAX_CANVAS_AXIS
                or image.height > MAX_CANVAS_AXIS
                or image.width * image.height > MAX_RASTER_PIXELS
            ):
                raise UnsafeSVGError("embedded PNG dimensions exceed the safety ceiling")
            image.verify()
    except UnsafeSVGError:
        raise
    except (OSError, ValueError, UnidentifiedImageError):
        raise UnsafeSVGError("embedded PNG is corrupt") from None


def _tokens(value: str) -> list[str]:
    if len(value.encode("utf-8")) > MAX_PATH_BYTES:
        raise UnsafeSVGError("path data exceeds the complexity byte ceiling")
    tokens: list[str] = []
    position = 0
    for match in _PATH_TOKEN_RE.finditer(value):
        if not _SEPARATOR_RE.fullmatch(value[position : match.start()]):
            raise UnsafeSVGError("path data contains unsupported syntax")
        tokens.append(match.group(0))
        position = match.end()
    if not _SEPARATOR_RE.fullmatch(value[position:]) or not tokens:
        raise UnsafeSVGError("path data contains unsupported or empty syntax")
    return tokens


def validate_path_data(value: str, width: float, height: float) -> PathInspection:
    """Validate bounded SVG path grammar without rendering or filesystem access."""

    tokens = _tokens(value)
    command_count = sum(token.isalpha() for token in tokens)
    if command_count > MAX_PATH_COMMANDS:
        raise UnsafeSVGError("path data exceeds the command complexity ceiling")
    index = 0
    command: str | None = None
    current_x = current_y = start_x = start_y = 0.0
    group_count = 0
    total_groups = 0
    saw_moveto = False
    subpaths_closed: list[bool] = []
    subpath_started = False
    current_subpath_closed = False
    min_x = min_y = math.inf
    max_x = max_y = -math.inf

    def record(x: float, y: float) -> None:
        nonlocal min_x, min_y, max_x, max_y
        bounded(x, y)
        min_x = min(min_x, x)
        min_y = min(min_y, y)
        max_x = max(max_x, x)
        max_y = max(max_y, y)

    def bounded(x: float, y: float) -> None:
        if not (0 <= x <= width and 0 <= y <= height):
            raise UnsafeSVGError("path coordinate is outside the canvas")

    while index < len(tokens):
        token = tokens[index]
        if token.isalpha():
            command = token
            if not saw_moveto and command.upper() != "M":
                raise UnsafeSVGError("path data must start with moveto")
            if command.upper() == "M":
                if subpath_started:
                    subpaths_closed.append(current_subpath_closed)
                subpath_started = True
                current_subpath_closed = False
                saw_moveto = True
            elif current_subpath_closed and command.upper() != "Z":
                raise UnsafeSVGError("a closed subpath must be followed by moveto")
            index += 1
            group_count = 0
            if command.upper() == "Z":
                if current_subpath_closed:
                    raise UnsafeSVGError("a path subpath cannot be closed twice")
                current_subpath_closed = True
                current_x, current_y = start_x, start_y
                record(current_x, current_y)
                continue
        elif command is None or command.upper() == "Z":
            raise UnsafeSVGError("path data has parameters without a command")

        assert command is not None
        upper = command.upper()
        arity = _PATH_ARITY[upper]
        if index + arity > len(tokens) or any(t.isalpha() for t in tokens[index : index + arity]):
            raise UnsafeSVGError(f"path command {command} has incomplete parameters")
        raw_values = tokens[index : index + arity]
        values = [_number(t, "path") for t in raw_values]
        index += arity
        group_count += 1
        total_groups += 1
        if total_groups > MAX_PATH_COMMANDS:
            raise UnsafeSVGError("path data exceeds the command complexity ceiling")
        relative = command.islower()

        if upper in {"S", "T"}:
            raise UnsafeSVGError(
                "shorthand curve commands are unsupported without explicit control bounds"
            )

        if upper == "H":
            x = values[0] + (current_x if relative else 0)
            record(x, current_y)
            current_x = x
        elif upper == "V":
            y = values[0] + (current_y if relative else 0)
            record(current_x, y)
            current_y = y
        elif upper == "A":
            rx, ry, _rotation, large, sweep, x, y = values
            if raw_values[3] not in {"0", "1"} or raw_values[4] not in {"0", "1"}:
                raise UnsafeSVGError("arc flags must use the exact lexemes 0 or 1")
            if rx < 0 or ry < 0 or large not in {0.0, 1.0} or sweep not in {0.0, 1.0}:
                raise UnsafeSVGError("arc radii or flags are invalid")
            raise UnsafeSVGError(
                "arc commands are unsupported pending exact endpoint-to-center qualification"
            )
        else:
            pairs = list(zip(values[0::2], values[1::2], strict=True))
            adjusted: list[tuple[float, float]] = []
            for x, y in pairs:
                if relative:
                    x += current_x
                    y += current_y
                record(x, y)
                adjusted.append((x, y))
            current_x, current_y = adjusted[-1]
            if upper == "M" and group_count == 1:
                start_x, start_y = current_x, current_y
                command = "l" if relative else "L"

    if math.isinf(min_x):
        raise UnsafeSVGError("path data has no geometry")
    if subpath_started:
        subpaths_closed.append(current_subpath_closed)
    if any(subpaths_closed) and not all(subpaths_closed):
        raise UnsafeSVGError("mixed open and closed path subpaths are unsupported")
    return PathInspection(min_x, min_y, max_x, max_y, tuple(subpaths_closed))


def _validate_points(
    value: str, width: float, height: float, *, minimum_points: int
) -> None:
    numbers = re.findall(_NUMBER, value)
    scrubbed = re.sub(_NUMBER, "", value)
    if not _SEPARATOR_RE.fullmatch(scrubbed) or len(numbers) % 2:
        raise UnsafeSVGError("points: malformed coordinate list")
    if len(numbers) < minimum_points * 2:
        if minimum_points == 3:
            raise UnsafeSVGError("polygon requires at least 3 points")
        raise UnsafeSVGError("points: malformed coordinate list")
    if len(numbers) // 2 > MAX_POLYGON_POINTS:
        raise UnsafeSVGError("points: complexity ceiling exceeded")
    for x_text, y_text in zip(numbers[0::2], numbers[1::2], strict=True):
        x, y = _number(x_text, "points"), _number(y_text, "points")
        if not (0 <= x <= width and 0 <= y <= height):
            raise UnsafeSVGError("point coordinate is outside the canvas")


def _iter_elements(root: StdET.Element) -> Iterator[tuple[StdET.Element, str]]:
    count = 0
    stack = [(root, 0)]
    while stack:
        node, depth = stack.pop()
        count += 1
        if count > MAX_ELEMENTS:
            raise UnsafeSVGError("SVG element complexity ceiling exceeded")
        if depth > MAX_NESTING_DEPTH:
            raise UnsafeSVGError("SVG nesting depth exceeds the complexity ceiling")
        if not isinstance(node.tag, str):
            raise UnsafeSVGError("comments and processing instructions are forbidden")
        namespace, local = _split_expanded_name(node.tag)
        if namespace not in {"", SVG_NAMESPACE}:
            raise UnsafeSVGError(f"unknown element namespace: {namespace}")
        if local not in ALLOWED_ELEMENTS:
            raise UnsafeSVGError(f"forbidden element: {local}")
        yield node, local
        stack.extend((child, depth + 1) for child in reversed(list(node)))


def _streaming_preflight(svg: bytes) -> None:
    """Bound hostile XML allocation before constructing the retained tree."""

    count = 0
    depth = 0
    try:
        events = DefusedET.iterparse(
            BytesIO(svg),
            events=("start", "end", "start-ns", "comment", "pi"),
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
        for event, value in events:
            if event in {"comment", "pi"}:
                raise UnsafeSVGError("comments and processing instructions are forbidden")
            if event == "start-ns":
                _prefix, namespace = value
                if namespace not in {SVG_NAMESPACE, XLINK_NAMESPACE}:
                    raise UnsafeSVGError(f"unknown namespace declaration: {namespace}")
            elif event == "start":
                count += 1
                depth += 1
                if count > MAX_ELEMENTS:
                    raise UnsafeSVGError("SVG element complexity ceiling exceeded")
                if depth - 1 > MAX_NESTING_DEPTH:
                    raise UnsafeSVGError("SVG nesting depth exceeds the complexity ceiling")
            elif event == "end":
                value.clear()
                depth -= 1
    except UnsafeSVGError:
        raise
    except (DefusedXmlException, StdET.ParseError, ValueError, TypeError) as exc:
        raise UnsafeSVGError(f"unsafe or malformed XML: {exc}") from None


def _canvas(root: StdET.Element) -> tuple[float, float]:
    namespace, local = _split_expanded_name(root.tag)
    if namespace not in {"", SVG_NAMESPACE} or local != "svg":
        raise UnsafeSVGError("root element must be svg")
    try:
        width = _number(root.attrib["width"], "svg.width")
        height = _number(root.attrib["height"], "svg.height")
        view_box = root.attrib["viewBox"].split()
    except KeyError:
        raise UnsafeSVGError("svg requires width, height, and viewBox") from None
    validate_canvas_dimensions(width, height)
    if len(view_box) != 4:
        raise UnsafeSVGError("viewBox must contain four finite numbers")
    values = [_number(part, "viewBox") for part in view_box]
    if values != [0.0, 0.0, width, height]:
        raise UnsafeSVGError("viewBox must exactly match 0 0 width height")
    return width, height


def _required_attributes(local: str, attributes: dict[str, str]) -> None:
    required = {
        "svg": {"width", "height", "viewBox"},
        "path": {"d"},
        "rect": {"x", "y", "width", "height"},
        "circle": {"cx", "cy", "r"},
        "ellipse": {"cx", "cy", "rx", "ry"},
        "line": {"x1", "y1", "x2", "y2"},
        "polyline": {"points"},
        "polygon": {"points"},
        "text": {"x", "y"},
        "linearGradient": {"id", "x1", "y1", "x2", "y2", "gradientUnits"},
        "radialGradient": {"id", "cx", "cy", "r", "gradientUnits"},
        "stop": {"offset", "stop-color"},
        "clipPath": {"id", "clipPathUnits"},
        "mask": {"id", "maskUnits", "x", "y", "width", "height"},
        "image": {"x", "y", "width", "height", "href"},
    }.get(local, set())
    missing = required.difference(attributes)
    if missing:
        raise UnsafeSVGError(f"{local}: missing required attributes: {sorted(missing)}")


def _validate_geometry(local: str, attributes: dict[str, str], width: float, height: float) -> None:
    def n(name: str) -> float:
        return _number(attributes[name], f"{local}.{name}")

    if local in {"rect", "image", "mask"}:
        x, y, item_width, item_height = n("x"), n("y"), n("width"), n("height")
        if item_width < 0 or item_height < 0 or x < 0 or y < 0:
            raise UnsafeSVGError(f"{local}: negative geometry is forbidden")
        if x + item_width > width or y + item_height > height:
            raise UnsafeSVGError(f"{local}: geometry exceeds the canvas")
    elif local == "circle":
        cx, cy, radius = n("cx"), n("cy"), n("r")
        if radius < 0 or cx - radius < 0 or cy - radius < 0 or cx + radius > width or cy + radius > height:
            raise UnsafeSVGError("circle: geometry exceeds the canvas")
    elif local == "ellipse":
        cx, cy, rx, ry = n("cx"), n("cy"), n("rx"), n("ry")
        if rx < 0 or ry < 0 or cx - rx < 0 or cy - ry < 0 or cx + rx > width or cy + ry > height:
            raise UnsafeSVGError("ellipse: geometry exceeds the canvas")
    elif local == "line":
        coordinates = (n("x1"), n("y1"), n("x2"), n("y2"))
        if not (0 <= coordinates[0] <= width and 0 <= coordinates[2] <= width):
            raise UnsafeSVGError("line: x coordinate exceeds the canvas")
        if not (0 <= coordinates[1] <= height and 0 <= coordinates[3] <= height):
            raise UnsafeSVGError("line: y coordinate exceeds the canvas")
    elif local == "text":
        x, y = n("x"), n("y")
        if not (0 <= x <= width and 0 <= y <= height):
            raise UnsafeSVGError("text: anchor exceeds the canvas")
    elif local == "linearGradient":
        coordinates = (n("x1"), n("y1"), n("x2"), n("y2"))
        if not (
            0 <= coordinates[0] <= width
            and 0 <= coordinates[2] <= width
            and 0 <= coordinates[1] <= height
            and 0 <= coordinates[3] <= height
        ):
            raise UnsafeSVGError("linearGradient geometry exceeds the canvas")
    elif local == "radialGradient":
        cx, cy, radius = n("cx"), n("cy"), n("r")
        if not (
            radius >= 0
            and cx - radius >= 0
            and cy - radius >= 0
            and cx + radius <= width
            and cy + radius <= height
        ):
            raise UnsafeSVGError("radialGradient circle exceeds the canvas")
        for x_name, y_name in (("fx", "fy"),):
            if x_name in attributes or y_name in attributes:
                if x_name not in attributes or y_name not in attributes:
                    raise UnsafeSVGError("radialGradient focus requires both fx and fy")
                if not (0 <= n(x_name) <= width and 0 <= n(y_name) <= height):
                    raise UnsafeSVGError("radialGradient focus exceeds the canvas")


def _validate_visual_numbers(
    local: str, attributes: dict[str, str], width: float, height: float
) -> None:
    stroke = attributes.get("stroke")
    if stroke not in {None, "none"}:
        stroke_visual_padding(
            _number(
                attributes.get("stroke-width", str(SVG_DEFAULT_STROKE_WIDTH)),
                f"{local}.stroke-width",
            ),
            attributes.get("stroke-linejoin", SVG_DEFAULT_STROKE_LINEJOIN),
            attributes.get("stroke-linecap", SVG_DEFAULT_STROKE_LINECAP),
            _number(
                attributes.get(
                    "stroke-miterlimit", str(SVG_DEFAULT_STROKE_MITERLIMIT)
                ),
                f"{local}.stroke-miterlimit",
            ),
            width,
            height,
        )
    if "font-size" in attributes:
        validate_font_size(_number(attributes["font-size"], "font-size"), width, height)


_GRAPHICAL_CHILDREN = frozenset(
    {"g", "path", "rect", "circle", "ellipse", "line", "polyline", "polygon", "text", "image"}
)
_ALLOWED_CHILDREN: dict[str, frozenset[str]] = {
    "svg": _GRAPHICAL_CHILDREN | {"defs"},
    "g": _GRAPHICAL_CHILDREN,
    "defs": frozenset({"linearGradient", "radialGradient", "clipPath", "mask"}),
    "linearGradient": frozenset({"stop"}),
    "radialGradient": frozenset({"stop"}),
    "clipPath": _GRAPHICAL_CHILDREN - {"image"},
    "mask": _GRAPHICAL_CHILDREN,
    "path": frozenset(),
    "rect": frozenset(),
    "circle": frozenset(),
    "ellipse": frozenset(),
    "line": frozenset(),
    "polyline": frozenset(),
    "polygon": frozenset(),
    "text": frozenset(),
    "stop": frozenset(),
    "image": frozenset(),
}


def _validate_topology(root: StdET.Element) -> None:
    for parent, parent_local in _iter_elements(root):
        allowed = _ALLOWED_CHILDREN[parent_local]
        for child in parent:
            _namespace, child_local = _split_expanded_name(child.tag)
            if child_local not in ALLOWED_ELEMENTS:
                raise UnsafeSVGError(f"forbidden element: {child_local}")
            if child_local not in allowed:
                raise UnsafeSVGError(
                    f"SVG subset topology forbids {child_local} below {parent_local}"
                )


def _validate_tree(root: StdET.Element) -> None:
    width, height = _canvas(root)
    _validate_topology(root)
    ids: dict[str, str] = {}
    references: list[tuple[str, str]] = []
    for node, local in _iter_elements(root):
        if node.tail and node.tail.strip():
            raise UnsafeSVGError("non-whitespace element tails are forbidden")
        if local != "text" and node.text and node.text.strip():
            raise UnsafeSVGError(f"text content is forbidden in {local}")
        if local == "text":
            content = node.text or ""
            if len(content) > MAX_TEXT_LENGTH or _CONTROL_RE.search(content):
                raise UnsafeSVGError("text content exceeds the safe profile")

        allowed = ALLOWED_ATTRIBUTES[local]
        for raw_name, value in node.attrib.items():
            namespace, name = _split_expanded_name(raw_name)
            if namespace:
                if namespace == XLINK_NAMESPACE:
                    raise UnsafeSVGError("xlink attributes are forbidden")
                raise UnsafeSVGError(f"unknown attribute namespace: {namespace}")
            if name.casefold().startswith("on"):
                raise UnsafeSVGError(f"event attribute is forbidden: {name}")
            if name not in allowed:
                raise UnsafeSVGError(f"attribute {name!r} is forbidden on {local}")
            if len(value) > MAX_ATTRIBUTE_LENGTH or _CONTROL_RE.search(value):
                raise UnsafeSVGError(f"attribute {name!r} exceeds the safe profile")
            if name == "id":
                if not _ID_RE.fullmatch(value) or value in ids:
                    raise UnsafeSVGError("element id is malformed or duplicated")
                ids[value] = local
            elif name == "href":
                _validate_png_data_uri(value)
            elif name == "style":
                _validate_style(value)
            elif name in {"fill", "stroke", "stop-color"}:
                if value.startswith("url("):
                    if name != "fill" or not _INTERNAL_REFERENCE_RE.fullmatch(value):
                        raise UnsafeSVGError(f"{name}: external or malformed URL is forbidden")
                    references.append(("gradient", value[5:-1]))
                else:
                    _validate_color(value, name)
            elif name in {"clip-path", "mask"}:
                if not _INTERNAL_REFERENCE_RE.fullmatch(value):
                    raise UnsafeSVGError(f"{name}: only a local fragment reference is allowed")
                references.append((name, value[5:-1]))
            elif name == "d":
                validate_path_data(value, width, height)
            elif name == "points":
                _validate_points(
                    value,
                    width,
                    height,
                    minimum_points=3 if local == "polygon" else 2,
                )
            elif name in _NUMERIC_ATTRIBUTES:
                number = _number(value, f"{local}.{name}")
                if name in {"opacity", "stop-opacity"} and not 0 <= number <= 1:
                    raise UnsafeSVGError(f"{name}: expected a value in [0, 1]")
                if name in {"width", "height", "r", "rx", "ry", "stroke-width", "font-size"} and number < 0:
                    raise UnsafeSVGError(f"{name}: expected a non-negative value")
                if name == "stroke-miterlimit" and number < 1:
                    raise UnsafeSVGError("stroke-miterlimit must be at least 1")
            elif name == "fill-rule" and value not in {"nonzero", "evenodd"}:
                raise UnsafeSVGError("unsupported fill-rule")
            elif name == "stroke-linecap" and value not in {"butt", "round", "square"}:
                raise UnsafeSVGError("unsupported stroke-linecap")
            elif name == "stroke-linejoin" and value not in {"miter", "round", "bevel"}:
                raise UnsafeSVGError("unsupported stroke-linejoin")
            elif name == "display" and value != "none":
                raise UnsafeSVGError("only display=none is supported")
            elif name == "font-style" and value not in {"normal", "italic", "oblique"}:
                raise UnsafeSVGError("unsupported font-style")
            elif name == "font-weight":
                weight = _number(value, "font-weight")
                if int(weight) != weight or not 1 <= weight <= 1000:
                    raise UnsafeSVGError("font-weight is outside the supported range")
            elif name == "text-anchor" and value not in {"start", "middle", "end"}:
                raise UnsafeSVGError("unsupported text-anchor")
            elif name == "preserveAspectRatio" and value != "none":
                raise UnsafeSVGError("only preserveAspectRatio=none is supported")
            elif name in {"gradientUnits", "clipPathUnits", "maskUnits"} and value != "userSpaceOnUse":
                raise UnsafeSVGError(f"unsupported {name}")
            elif name == "offset":
                offset = _number(value, "stop.offset")
                if not 0 <= offset <= 1:
                    raise UnsafeSVGError("gradient stop offset is outside [0, 1]")
            elif name == "version" and value != "1.1":
                raise UnsafeSVGError("unsupported SVG version")

        _required_attributes(local, node.attrib)
        _validate_geometry(local, node.attrib, width, height)
        _validate_visual_numbers(local, node.attrib, width, height)

    for kind, reference in references:
        expected = {
            "gradient": {"linearGradient", "radialGradient"},
            "clip-path": {"clipPath"},
            "mask": {"mask"},
        }[kind]
        if ids.get(reference) not in expected:
            raise UnsafeSVGError(f"{kind} references a missing or incompatible id")
    _validate_resource_reference_cycles(root)


def _validate_resource_reference_cycles(root: StdET.Element) -> None:
    resources: dict[str, StdET.Element] = {}
    for node, local in _iter_elements(root):
        if local in {"clipPath", "mask"}:
            resources[node.attrib["id"]] = node

    graph: dict[str, set[str]] = {resource_id: set() for resource_id in resources}
    for resource_id, resource in resources.items():
        stack = [resource]
        while stack:
            node = stack.pop()
            for attribute in ("clip-path", "mask"):
                value = node.attrib.get(attribute)
                if value and _INTERNAL_REFERENCE_RE.fullmatch(value):
                    target = value[5:-1]
                    if target in resources:
                        graph[resource_id].add(target)
            stack.extend(list(node))

    indegree = {resource_id: 0 for resource_id in graph}
    for targets in graph.values():
        for target in targets:
            indegree[target] += 1
    ready = [resource_id for resource_id, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        resource_id = ready.pop()
        visited += 1
        for target in graph[resource_id]:
            indegree[target] -= 1
            if indegree[target] == 0:
                ready.append(target)
    if visited != len(graph):
        raise UnsafeSVGError("clipPath/mask resource reference cycle is forbidden")


def sanitize_svg(svg: bytes) -> bytes:
    """Reject unsafe SVG and return deterministic canonical UTF-8 XML bytes."""

    if not isinstance(svg, bytes):
        raise TypeError("svg must be bytes")
    if not svg or len(svg) > MAX_SVG_BYTES:
        raise UnsafeSVGError("SVG is empty or exceeds the size ceiling")
    folded = svg.upper()
    if b"<!DOCTYPE" in folded or b"<!ENTITY" in folded:
        raise UnsafeSVGError("DTD and entity declarations are forbidden")
    _streaming_preflight(svg)
    try:
        root = DefusedET.fromstring(
            svg,
            forbid_dtd=True,
            forbid_entities=True,
            forbid_external=True,
        )
    except (DefusedXmlException, StdET.ParseError, ValueError, TypeError) as exc:
        raise UnsafeSVGError(f"unsafe or malformed XML: {exc}") from None
    _validate_tree(root)
    try:
        xml = StdET.tostring(root, encoding="unicode", short_empty_elements=True)
        canonical = StdET.canonicalize(xml_data=xml, with_comments=False)
    except (StdET.ParseError, ValueError) as exc:
        raise UnsafeSVGError(f"cannot canonicalize SVG safely: {exc}") from None
    return canonical.encode("utf-8")
