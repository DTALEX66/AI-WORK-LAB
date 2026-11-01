#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Generate deterministic PNG references from tracked original source definitions."""
from __future__ import annotations

import binascii
import json
import struct
import zlib
from pathlib import Path


DESIGN_LAB = Path(__file__).resolve().parents[1]
EVAL_ROOT = DESIGN_LAB / "evals" / "reconstruction"


def _colour(value: str) -> tuple[int, int, int, int]:
    if not isinstance(value, str) or len(value) != 7 or not value.startswith("#"):
        raise ValueError(f"invalid colour: {value!r}")
    return tuple(int(value[index:index + 2], 16) for index in (1, 3, 5)) + (255,)


def _set(pixels: bytearray, width: int, height: int, x: int, y: int, colour: tuple[int, int, int, int]) -> None:
    if 0 <= x < width and 0 <= y < height:
        offset = (y * width + x) * 4
        pixels[offset:offset + 4] = bytes(colour)


def _rect(pixels: bytearray, width: int, height: int, element: dict[str, object]) -> None:
    colour = _colour(str(element["fill"]))
    for y in range(int(element["y"]), int(element["y"]) + int(element["h"])):
        for x in range(int(element["x"]), int(element["x"]) + int(element["w"])):
            _set(pixels, width, height, x, y, colour)


def _circle(pixels: bytearray, width: int, height: int, element: dict[str, object]) -> None:
    colour = _colour(str(element["fill"]))
    cx, cy, radius = int(element["cx"]), int(element["cy"]), int(element["r"])
    for y in range(cy - radius, cy + radius + 1):
        for x in range(cx - radius, cx + radius + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= radius ** 2:
                _set(pixels, width, height, x, y, colour)


def _line(pixels: bytearray, width: int, height: int, element: dict[str, object]) -> None:
    x1, y1, x2, y2 = (int(element[key]) for key in ("x1", "y1", "x2", "y2"))
    colour = _colour(str(element["fill"]))
    radius = max(0, int(element["width"]) // 2)
    dx, dy = abs(x2 - x1), -abs(y2 - y1)
    step_x, step_y = (1 if x1 < x2 else -1), (1 if y1 < y2 else -1)
    error = dx + dy
    while True:
        for y in range(y1 - radius, y1 + radius + 1):
            for x in range(x1 - radius, x1 + radius + 1):
                _set(pixels, width, height, x, y, colour)
        if x1 == x2 and y1 == y2:
            return
        twice = 2 * error
        if twice >= dy:
            error += dy
            x1 += step_x
        if twice <= dx:
            error += dx
            y1 += step_y


def _chunk(kind: bytes, payload: bytes) -> bytes:
    return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", binascii.crc32(kind + payload) & 0xFFFFFFFF)


def _png(width: int, height: int, pixels: bytearray) -> bytes:
    rows = b"".join(b"\x00" + bytes(pixels[index * width * 4:(index + 1) * width * 4]) for index in range(height))
    return b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 6, 0, 0, 0)) + _chunk(b"IDAT", zlib.compress(rows, 9)) + _chunk(b"IEND", b"")


def main() -> int:
    source = json.loads((EVAL_ROOT / "sources.json").read_text(encoding="utf-8"))
    width, height = int(source["canvas"]["width"]), int(source["canvas"]["height"])
    for case in source["cases"]:
        pixels = bytearray(bytes(_colour(case["background"])) * width * height)
        for element in case["elements"]:
            {"rect": _rect, "circle": _circle, "line": _line}[element["type"]](pixels, width, height, element)
        target = EVAL_ROOT / "cases" / case["caseId"] / "reference.png"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_png(width, height, pixels))
        print(target.relative_to(DESIGN_LAB).as_posix())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
