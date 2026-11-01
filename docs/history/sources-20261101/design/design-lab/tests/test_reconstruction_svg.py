# SPDX-License-Identifier: MIT
"""Deterministic and adversarial SVG reconstruction tests."""
from __future__ import annotations

import copy
import os
import shutil
import subprocess
import sys
import unittest
import uuid
from pathlib import Path
from unittest import mock

DESIGN_LAB = Path(__file__).resolve().parents[1]
PROJECT_ROOT = DESIGN_LAB.parent
FIXTURE = DESIGN_LAB / "tests" / "fixtures" / "reconstruction" / "flat-64.png"
if str(DESIGN_LAB) not in sys.path:
    sys.path.insert(0, str(DESIGN_LAB))
    sys.path.insert(0, str(PROJECT_ROOT / "packages" / "capabilities"))

from reconstruction.svg import serialize_svg  # noqa: E402
from reconstruction import svg_safety as svg_safety_module  # noqa: E402
from reconstruction.svg_safety import (  # noqa: E402
    MAX_CANVAS_PIXELS,
    UnsafeSVGError,
    sanitize_svg,
)


def base_layer(layer_id: str, node_type: str, z_order: int = 0) -> dict:
    return {
        "id": layer_id,
        "type": node_type,
        "name": layer_id,
        "opacity": 1.0,
        "bounds": {"x": 0, "y": 0, "width": 64, "height": 64},
        "inferred": False,
        "zOrder": z_order,
        "visible": True,
        "locked": False,
        "blendMode": "normal",
    }


def style() -> dict:
    return {
        "fill": "#336699",
        "stroke": "#000000",
        "strokeWidth": 1,
        "fillRule": "nonzero",
        "lineCap": "round",
        "lineJoin": "bevel",
    }


def rectangle_layer(layer_id: str = "rectangle", z_order: int = 0) -> dict:
    layer = base_layer(layer_id, "primitive", z_order)
    layer.update(
        {
            "primitive": {
                "kind": "rect",
                "parameters": {"x1": 4, "y1": 5, "x2": 60, "y2": 59, "rx": 2, "ry": 3},
            },
            "style": style(),
            "masks": [],
        }
    )
    return layer


def path_layer(layer_id: str = "path", z_order: int = 0) -> dict:
    layer = base_layer(layer_id, "path", z_order)
    layer.update(
        {
            "geometry": {"pathData": "M1 1 C 10 5 20 30 63 63 Z", "closed": True},
            "style": style(),
            "masks": [],
        }
    )
    return layer


def text_layer(layer_id: str = "text", z_order: int = 0) -> dict:
    layer = base_layer(layer_id, "text", z_order)
    layer["bounds"] = {"x": 2, "y": 3, "width": 50, "height": 20}
    layer["text"] = {
        "content": "A < B & C",
        "disposition": "live",
        "fontCandidates": [
            {"family": "Arial", "weight": 400, "style": "normal", "confidence": 1.0}
        ],
        "outlineFallback": {"available": False, "pathData": None},
    }
    return layer


def raster_layer(path: str, layer_id: str = "raster", z_order: int = 0) -> dict:
    layer = base_layer(layer_id, "raster", z_order)
    layer["raster"] = {
        "path": path,
        "crop": {"x": 0, "y": 0, "width": 64, "height": 64},
        "alpha": 1.0,
        "sourceMappings": [],
    }
    return layer


def rir(*layers: dict) -> dict:
    return {
        "schemaVersion": "design-lab/reconstruction-ir/v1",
        "canvas": {"width": 64, "height": 64, "colorSpace": "srgb"},
        "layers": list(layers),
    }


class ReconstructionSVGTests(unittest.TestCase):
    def setUp(self) -> None:
        self.scratch = (
            PROJECT_ROOT
            / ".project-local"
            / "task-runtime"
            / "reconstruction-svg-tests"
            / f"{os.getpid()}-{uuid.uuid4().hex}"
        )
        self.scratch.mkdir(parents=True)

    def tearDown(self) -> None:
        if self.scratch.exists():
            shutil.rmtree(self.scratch)

    def assert_sanitize_rejected_without_handoff(
        self, payload: bytes, reason: str
    ) -> None:
        with (
            mock.patch("pathlib.Path.open", side_effect=AssertionError("filesystem read")) as opened,
            mock.patch.object(
                svg_safety_module.Image,
                "open",
                side_effect=AssertionError("image decode handoff"),
            ) as image_opened,
            mock.patch(
                "subprocess.run", side_effect=AssertionError("renderer/host handoff")
            ) as renderer,
            self.assertRaisesRegex(UnsafeSVGError, reason),
        ):
            sanitize_svg(payload)
        opened.assert_not_called()
        image_opened.assert_not_called()
        renderer.assert_not_called()

    def assert_serialize_rejected_without_handoff(
        self, value: dict, reason: str
    ) -> None:
        with (
            mock.patch("pathlib.Path.open", side_effect=AssertionError("filesystem read")) as opened,
            mock.patch.object(
                svg_safety_module.Image,
                "open",
                side_effect=AssertionError("image decode handoff"),
            ) as image_opened,
            mock.patch(
                "subprocess.run", side_effect=AssertionError("renderer/host handoff")
            ) as renderer,
            self.assertRaisesRegex((UnsafeSVGError, ValueError), reason),
        ):
            serialize_svg(value, PROJECT_ROOT)
        opened.assert_not_called()
        image_opened.assert_not_called()
        renderer.assert_not_called()

    def test_primitive_serializes_with_exact_viewbox_and_canonical_bytes(self) -> None:
        value = rir(rectangle_layer())
        first = serialize_svg(value, PROJECT_ROOT)
        second = serialize_svg(copy.deepcopy(value), PROJECT_ROOT)
        self.assertEqual(first, second)
        self.assertIn(b'viewBox="0 0 64 64"', first)
        self.assertIn(b"<rect", first)
        self.assertEqual(first, sanitize_svg(first))

    def test_every_supported_node_type_serializes_in_stable_z_order(self) -> None:
        group = base_layer("group", "group", 1)
        group["children"] = [rectangle_layer("child", 0)]
        outlined = text_layer("outlined", 2)
        outlined["text"] = {
            "content": "ignored",
            "disposition": "outlined",
            "fontCandidates": [],
            "outlineFallback": {"available": True, "pathData": "M2 3L10 3L10 10Z"},
        }
        value = rir(
            raster_layer("design-lab/tests/fixtures/reconstruction/flat-64.png", z_order=4),
            text_layer(z_order=3),
            outlined,
            path_layer(z_order=0),
            group,
        )
        svg = serialize_svg(value, PROJECT_ROOT)
        self.assertIn(b"<path", svg)
        self.assertIn(b"<g", svg)
        self.assertIn(b"<rect", svg)
        self.assertIn(b"<text", svg)
        self.assertIn(b"data:image/png;base64,", svg)
        self.assertLess(svg.index(b"<path"), svg.index(b"<g"))
        self.assertLess(svg.index(b"<text"), svg.index(b"<image"))

    def test_every_primitive_kind_serializes_including_reverse_line(self) -> None:
        ellipse = rectangle_layer("ellipse", 0)
        ellipse["primitive"] = {
            "kind": "ellipse",
            "parameters": {"x1": 2, "y1": 4, "x2": 30, "y2": 40},
        }
        line = rectangle_layer("line", 1)
        line["primitive"] = {
            "kind": "line",
            "parameters": {"x1": 60, "y1": 50, "x2": 3, "y2": 2},
        }
        polygon = rectangle_layer("polygon", 2)
        polygon["primitive"] = {
            "kind": "polygon",
            "parameters": {
                "points": [{"x": 1, "y": 1}, {"x": 63, "y": 1}, {"x": 32, "y": 63}]
            },
        }
        svg = serialize_svg(rir(ellipse, line, polygon), PROJECT_ROOT)
        self.assertIn(b"<ellipse", svg)
        self.assertIn(b"<line", svg)
        self.assertIn(b"<polygon", svg)

    def test_mapping_insertion_order_does_not_change_serialization(self) -> None:
        first = rir(rectangle_layer())
        source = first["layers"][0]
        reordered = {
            "layers": [
                {
                    "masks": [],
                    "style": dict(reversed(list(source["style"].items()))),
                    "primitive": {
                        "parameters": dict(
                            reversed(list(source["primitive"]["parameters"].items()))
                        ),
                        "kind": "rect",
                    },
                    **{
                        key: source[key]
                        for key in reversed(list(base_layer("rectangle", "primitive").keys()))
                    },
                }
            ],
            "canvas": {"colorSpace": "srgb", "height": 64, "width": 64},
            "schemaVersion": "design-lab/reconstruction-ir/v1",
        }
        self.assertEqual(
            serialize_svg(first, PROJECT_ROOT),
            serialize_svg(reordered, PROJECT_ROOT),
        )

    def test_script_events_unknowns_and_external_resources_are_rejected(self) -> None:
        root = b'<svg width="64" height="64" viewBox="0 0 64 64"'
        payloads = (
            (root + b"><script/></svg>", "forbidden element"),
            (root + b' onload="x()"/>', "event attribute"),
            (root + b' xmlns:x="urn:evil" x:onload="x()"/>', "namespace"),
            (root + b"><foreignObject/></svg>", "forbidden element"),
            (root + b'><animate attributeName="x"/></svg>', "forbidden element"),
            (root + b'><filter id="f"/></svg>', "forbidden element"),
            (root + b' unexpected="1"/>', "attribute"),
            (root + b' xmlns:e="urn:evil"/>', "unknown namespace declaration"),
            (root + b' xmlns:e="urn:evil"><e:path/></svg>', "namespace"),
            (root + b'><image x="0" y="0" width="1" height="1" href="https://example.test/x.png"/></svg>', "embedded PNG"),
            (root + b'><image x="0" y="0" width="1" height="1" href="file:///C:/x.png"/></svg>', "embedded PNG"),
            (root + b'><image x="0" y="0" width="1" height="1" href="\\\\server\\share\\x.png"/></svg>', "embedded PNG"),
            (root + b'><path d="M0 0" style="fill:url(https://example.test/x)"/></svg>', "URL or script"),
            (root + b'><path d="M0 0" fill="url(https://example.test/x)"/></svg>', "URL"),
            (root + b' xmlns:xlink="http://www.w3.org/1999/xlink"><image x="0" y="0" width="1" height="1" xlink:href="x"/></svg>', "xlink"),
            (root + b"><!-- hidden --></svg>", "comments"),
        )
        for payload, reason in payloads:
            with self.subTest(payload=payload):
                self.assert_sanitize_rejected_without_handoff(payload, reason)

    def test_dtd_entities_and_malformed_xml_fail_before_any_file_read(self) -> None:
        payloads = (
            b'<!DOCTYPE svg [<!ENTITY xxe SYSTEM "file:///C:/secret">]><svg>&xxe;</svg>',
            b'<!DOCTYPE svg [<!ENTITY lol "lol">]><svg>&lol;</svg>',
            b"<svg><path></svg>",
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assert_sanitize_rejected_without_handoff(payload, "DTD|malformed")

    def test_data_uri_must_be_strict_base64_and_decoded_png(self) -> None:
        root = b'<svg width="64" height="64" viewBox="0 0 64 64">'
        image = b'<image x="0" y="0" width="1" height="1" href="'
        payloads = (
            (root + image + b'data:image/jpeg;base64,AA=="/></svg>', "embedded PNG"),
            (root + image + b'data:image/png;base64,not base64"/></svg>', "base64"),
            (root + image + b'data:image/png;base64,dGV4dA=="/></svg>', "not a PNG"),
            (root + image + b'../x.png"/></svg>', "embedded PNG"),
        )
        for payload, reason in payloads:
            with self.subTest(payload=payload):
                self.assert_sanitize_rejected_without_handoff(payload, reason)

    def test_non_finite_out_of_canvas_and_path_complexity_fail_closed(self) -> None:
        payloads = (
            b'<svg width="64" height="64" viewBox="0 0 64 64"><rect x="NaN" y="0" width="1" height="1"/></svg>',
            b'<svg width="64" height="64" viewBox="0 0 64 64"><path d="M0 0L65 1"/></svg>',
            b'<svg width="64" height="64" viewBox="0 0 64 64"><polygon points="0,0 1,Infinity 2,2"/></svg>',
        )
        for payload in payloads:
            with self.subTest(payload=payload):
                self.assert_sanitize_rejected_without_handoff(
                    payload, "finite|outside|malformed"
                )

        too_complex = path_layer()
        too_complex["geometry"]["pathData"] = "M0 0 " + "L1 1 " * 100_001
        self.assert_serialize_rejected_without_handoff(
            rir(too_complex), "complexity"
        )

    def test_malformed_path_and_canvas_geometry_fail_for_their_exact_reason(self) -> None:
        root = '<svg width="64" height="64" viewBox="0 0 64 64">{}</svg>'
        cases = (
            (root.format('<path d="L1 1"/>').encode(), "start with moveto"),
            (root.format('<path d="M0 0 C 1 2 3"/>').encode(), "incomplete"),
            (root.format('<path d="M0 0 B 1 1"/>').encode(), "unsupported syntax"),
            (root.format('<path d="M10 10 S 20 20 30 30"/>').encode(), "shorthand curve"),
            (root.format('<rect x="60" y="0" width="5" height="1"/>').encode(), "exceeds"),
            (root.format('<line x1="0" y1="0" x2="65" y2="1"/>').encode(), "exceeds"),
        )
        for payload, reason in cases:
            with self.subTest(payload=payload):
                self.assert_sanitize_rejected_without_handoff(payload, reason)

    def test_unsupported_hybrid_text_and_non_exact_crop_are_not_silently_flattened(self) -> None:
        hybrid = text_layer()
        hybrid["text"]["disposition"] = "hybrid"
        hybrid["text"]["outlineFallback"] = {
            "available": True,
            "pathData": "M1 1L10 1L10 10Z",
        }
        self.assert_serialize_rejected_without_handoff(rir(hybrid), "hybrid")

        raster = raster_layer("design-lab/tests/fixtures/reconstruction/flat-64.png")
        raster["raster"]["crop"]["width"] = 63
        with (
            mock.patch(
                "subprocess.run", side_effect=AssertionError("renderer/host handoff")
            ) as renderer,
            self.assertRaisesRegex(UnsafeSVGError, "crop"),
        ):
            serialize_svg(rir(raster), PROJECT_ROOT)
        renderer.assert_not_called()

    def test_svg_and_rir_nesting_depth_have_explicit_ceilings(self) -> None:
        nested_svg = (
            b'<svg width="64" height="64" viewBox="0 0 64 64">'
            + b"<g>" * 130
            + b"</g>" * 130
            + b"</svg>"
        )
        self.assert_sanitize_rejected_without_handoff(nested_svg, "nesting depth")

        child = rectangle_layer("leaf")
        for index in range(130):
            group = base_layer(f"group-{index}", "group")
            group["children"] = [child]
            child = group
        self.assert_serialize_rejected_without_handoff(
            rir(child), "nesting depth"
        )

    def test_streaming_preflight_rejects_element_and_depth_bombs_before_full_tree(self) -> None:
        element_bomb = (
            b'<svg width="64" height="64" viewBox="0 0 64 64">'
            + b"<g/>" * 10_001
            + b"</svg>"
        )
        depth_bomb = (
            b'<svg width="64" height="64" viewBox="0 0 64 64">'
            + b"<g>" * 129
            + b"</g>" * 129
            + b"</svg>"
        )
        for payload, reason in (
            (element_bomb, "element complexity"),
            (depth_bomb, "nesting depth"),
        ):
            with self.subTest(reason=reason), mock.patch.object(
                svg_safety_module.DefusedET,
                "fromstring",
                side_effect=AssertionError("full tree was built"),
            ) as full_tree:
                self.assert_sanitize_rejected_without_handoff(payload, reason)
                full_tree.assert_not_called()

    def test_equal_z_order_preserves_declared_sibling_order_at_both_levels(self) -> None:
        lower = rectangle_layer("first-declared", 0)
        lower["style"]["fill"] = "#ff000080"
        upper = rectangle_layer("second-declared", 0)
        upper["style"]["fill"] = "#0000ff80"
        group = base_layer("group", "group", 0)
        nested_lower = rectangle_layer("nested-first", 0)
        nested_lower["style"]["fill"] = "#00ff0080"
        nested_upper = rectangle_layer("nested-second", 0)
        nested_upper["style"]["fill"] = "#ffff0080"
        group["children"] = [nested_lower, nested_upper]

        svg = serialize_svg(rir(lower, upper, group), PROJECT_ROOT)
        self.assertLess(svg.index(b'#ff000080'), svg.index(b'#0000ff80'))
        self.assertLess(svg.index(b'#00ff0080'), svg.index(b'#ffff0080'))

    def test_vector_geometry_must_fit_declared_bounds_and_match_closed_semantics(self) -> None:
        outside_path = path_layer()
        outside_path["bounds"] = {"x": 0, "y": 0, "width": 2, "height": 2}
        outside_path["geometry"] = {"pathData": "M1 1 L63 63", "closed": False}
        self.assert_serialize_rejected_without_handoff(
            rir(outside_path), "declared bounds"
        )

        inconsistent_closed = path_layer()
        inconsistent_closed["geometry"] = {
            "pathData": "M1 1 L63 63",
            "closed": True,
        }
        self.assert_serialize_rejected_without_handoff(
            rir(inconsistent_closed), "closed"
        )

        outside_primitive = rectangle_layer()
        outside_primitive["bounds"] = {"x": 0, "y": 0, "width": 8, "height": 8}
        self.assert_serialize_rejected_without_handoff(
            rir(outside_primitive), "declared bounds"
        )

    def test_subset_topology_polygon_arity_and_arc_flag_lexemes_are_strict(self) -> None:
        root = '<svg width="64" height="64" viewBox="0 0 64 64">{}</svg>'
        topology_cases = (
            '<stop offset="0" stop-color="#fff"/>',
            '<linearGradient id="g" x1="0" y1="0" x2="1" y2="1" gradientUnits="userSpaceOnUse"/>',
            '<defs><image x="0" y="0" width="1" height="1" href="data:image/png;base64,AA=="/></defs>',
            '<text x="0" y="1"><rect x="0" y="0" width="1" height="1"/></text>',
            '<image x="0" y="0" width="1" height="1" href="data:image/png;base64,AA=="><path d="M0 0"/></image>',
            '<defs><linearGradient id="g" x1="0" y1="0" x2="1" y2="1" gradientUnits="userSpaceOnUse"><rect x="0" y="0" width="1" height="1"/></linearGradient></defs>',
            '<defs><clipPath id="c" clipPathUnits="userSpaceOnUse"><image x="0" y="0" width="1" height="1" href="data:image/png;base64,AA=="/></clipPath></defs>',
            '<g><svg width="1" height="1" viewBox="0 0 1 1"/></g>',
        )
        for child in topology_cases:
            payload = root.format(child).encode()
            with self.subTest(child=child):
                self.assert_sanitize_rejected_without_handoff(payload, "topology")

        two_point_polygon = root.format(
            '<polygon points="0,0 1,1" fill="#fff"/>'
        ).encode()
        self.assert_sanitize_rejected_without_handoff(two_point_polygon, "at least 3")

        for large, sweep in (("1.0", "0"), ("1", "0.0"), ("+1", "0")):
            payload = root.format(
                f'<path d="M20 20 A5 5 0 {large} {sweep} 30 30"/>'
            ).encode()
            with self.subTest(large=large, sweep=sweep):
                self.assert_sanitize_rejected_without_handoff(payload, "arc flags")

    def test_all_arcs_fail_closed_before_render_handoff(self) -> None:
        root = '<svg width="64" height="64" viewBox="0 0 64 64">{}</svg>'
        paths = (
            "M20 20 A5 5 0 1 0 30 30",
            "M5 5 A1 1 0 0 1 60 60",
            "M20 20 a5 5 45 0 1 10 10",
        )
        for path_data in paths:
            payload = root.format(f'<path d="{path_data}"/>').encode()
            with self.subTest(path_data=path_data):
                self.assert_sanitize_rejected_without_handoff(
                    payload, "arc commands are unsupported"
                )

        arc_node = path_layer()
        arc_node["geometry"] = {
            "pathData": "M20 20 A5 5 0 0 1 30 30",
            "closed": False,
        }
        self.assert_serialize_rejected_without_handoff(
            rir(arc_node), "arc commands are unsupported"
        )

    def test_complete_defs_topology_remains_supported_without_arcs(self) -> None:
        payload = b'''<svg width="64" height="64" viewBox="0 0 64 64">
          <defs>
            <linearGradient id="gradient" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse">
              <stop offset="0" stop-color="#fff"/><stop offset="1" stop-color="#000"/>
            </linearGradient>
            <clipPath id="clip" clipPathUnits="userSpaceOnUse"><path d="M1 1L63 1L63 63Z"/></clipPath>
            <mask id="mask" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
              <rect x="0" y="0" width="64" height="64" fill="#fff"/>
            </mask>
          </defs>
          <path d="M20 20 L30 30" fill="url(#gradient)" clip-path="url(#clip)" mask="url(#mask)"/>
        </svg>'''
        sanitized = sanitize_svg(payload)
        self.assertIn(b"M20 20 L30 30", sanitized)

    def test_closure_is_tracked_for_every_path_subpath(self) -> None:
        cases = (
            ("M1 1L2 2 M3 3L4 4Z", False, "closed"),
            ("M1 1L2 2Z M3 3L4 4", True, "closed"),
            ("M1 1L2 2Z M3 3L4 4Z", True, None),
            ("M1 1L2 2 M3 3L4 4", False, None),
            ("m1 1l1 1 m2 2l1 1", False, None),
        )
        for index, (path_data, closed, error) in enumerate(cases):
            node = path_layer(f"subpaths-{index}")
            node["geometry"] = {"pathData": path_data, "closed": closed}
            if error:
                self.assert_serialize_rejected_without_handoff(rir(node), error)
            else:
                self.assertIn(path_data.encode(), serialize_svg(rir(node), PROJECT_ROOT))

    def test_stroke_defaults_are_explicit_and_used_for_visual_bounds(self) -> None:
        node = path_layer("default-stroke")
        node["geometry"] = {"pathData": "M4 4L60 60", "closed": False}
        node["style"] = {"fill": None, "stroke": "#000000"}
        node["bounds"] = {"x": 4, "y": 4, "width": 56, "height": 56}
        self.assert_serialize_rejected_without_handoff(
            rir(node), "declared bounds"
        )

        node["bounds"] = {"x": 2, "y": 2, "width": 60, "height": 60}
        svg = serialize_svg(rir(node), PROJECT_ROOT)
        self.assertIn(b'stroke-width="1"', svg)
        self.assertIn(b'stroke-linejoin="miter"', svg)
        self.assertIn(b'stroke-linecap="butt"', svg)
        self.assertIn(b'stroke-miterlimit="4"', svg)

    def test_clip_and_mask_resource_reference_cycles_fail_closed(self) -> None:
        root = '<svg width="64" height="64" viewBox="0 0 64 64"><defs>{}</defs></svg>'
        resources = (
            '''<mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
                 <rect x="0" y="0" width="64" height="64" mask="url(#m)"/>
               </mask>''',
            '''<clipPath id="c" clipPathUnits="userSpaceOnUse"><path d="M1 1L63 63" mask="url(#m)"/></clipPath>
               <mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
                 <rect x="0" y="0" width="64" height="64" clip-path="url(#c)"/>
               </mask>''',
            '''<clipPath id="c1" clipPathUnits="userSpaceOnUse"><path d="M1 1L63 63" mask="url(#m1)"/></clipPath>
               <mask id="m1" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
                 <rect x="0" y="0" width="64" height="64" clip-path="url(#c2)"/>
               </mask>
               <clipPath id="c2" clipPathUnits="userSpaceOnUse"><path d="M1 1L63 63" clip-path="url(#c1)"/></clipPath>''',
        )
        for resource_xml in resources:
            payload = root.format(resource_xml).encode()
            with self.subTest(resource_xml=resource_xml):
                self.assert_sanitize_rejected_without_handoff(
                    payload, "resource reference cycle"
                )

    def test_acyclic_clip_mask_resource_chain_is_supported(self) -> None:
        payload = b'''<svg width="64" height="64" viewBox="0 0 64 64">
          <defs>
            <mask id="m" maskUnits="userSpaceOnUse" x="0" y="0" width="64" height="64">
              <rect x="0" y="0" width="64" height="64" fill="#fff"/>
            </mask>
            <clipPath id="c" clipPathUnits="userSpaceOnUse">
              <path d="M1 1L63 1L63 63Z" mask="url(#m)"/>
            </clipPath>
          </defs>
          <rect x="0" y="0" width="64" height="64" clip-path="url(#c)"/>
        </svg>'''
        self.assertIn(b'clip-path="url(#c)"', sanitize_svg(payload))

    def test_invalid_model_output_is_rejected_before_asset_read(self) -> None:
        invalid = raster_layer("../outside.png")
        self.assert_serialize_rejected_without_handoff(rir(invalid), ".*")

        unsupported_mask = path_layer()
        unsupported_mask["masks"] = [
            {
                "id": "mask-1",
                "pathData": "M0 0H64V64H0Z",
                "operation": "exclude",
                "opacity": 1.0,
            }
        ]
        self.assert_serialize_rejected_without_handoff(
            rir(unsupported_mask), "mask"
        )

    def test_asset_root_escape_non_png_and_reparse_asset_fail_closed(self) -> None:
        text_asset = self.scratch / "not-png.png"
        text_asset.write_bytes(b"not a png")
        relative_text = text_asset.relative_to(PROJECT_ROOT).as_posix()
        with (
            mock.patch.object(
                svg_safety_module.Image,
                "open",
                side_effect=AssertionError("image decode handoff"),
            ) as image_opened,
            mock.patch(
                "subprocess.run", side_effect=AssertionError("renderer/host handoff")
            ) as renderer,
            self.assertRaisesRegex(UnsafeSVGError, "PNG"),
        ):
            serialize_svg(rir(raster_layer(relative_text)), PROJECT_ROOT)
        image_opened.assert_not_called()
        renderer.assert_not_called()

        outside = self.scratch / "outside"
        outside.mkdir()
        (outside / "asset.png").write_bytes(FIXTURE.read_bytes())
        asset_root = self.scratch / "asset-root"
        asset_root.mkdir()
        link = asset_root / "linked"
        if os.name == "nt":
            completed = subprocess.run(
                ["cmd.exe", "/d", "/c", "mklink", "/J", str(link), str(outside)],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
            )
            if completed.returncode != 0:
                self.skipTest(f"junction unavailable: {completed.stdout}{completed.stderr}")
        else:
            link.symlink_to(outside, target_is_directory=True)
        try:
            project_relative = (link / "asset.png").relative_to(PROJECT_ROOT).as_posix()
            with (
                mock.patch.object(
                    Path,
                    "read_bytes",
                    side_effect=AssertionError("asset read past reparse rejection"),
                ) as asset_read,
                mock.patch(
                    "subprocess.run", side_effect=AssertionError("renderer/host handoff")
                ) as renderer,
                self.assertRaisesRegex(UnsafeSVGError, "reparse|symlink"),
            ):
                serialize_svg(rir(raster_layer(project_relative)), PROJECT_ROOT)
            asset_read.assert_not_called()
            renderer.assert_not_called()
        finally:
            if os.name == "nt" and link.exists():
                os.rmdir(link)
            elif link.is_symlink():
                link.unlink()

    def test_canonical_sanitization_sorts_attributes(self) -> None:
        first = sanitize_svg(
            b'<svg viewBox="0 0 64 64" height="64" width="64"><rect y="2" x="1" height="4" width="3" fill="#fff"/></svg>'
        )
        second = sanitize_svg(
            b'<svg width="64" height="64" viewBox="0 0 64 64"><rect fill="#fff" width="3" height="4" x="1" y="2"/></svg>'
        )
        self.assertEqual(first, second)

    def test_canvas_total_pixel_ceiling_has_exact_boundary_and_overflow_guards(self) -> None:
        self.assertEqual(MAX_CANVAS_PIXELS, 100_000_000)
        boundary = b'<svg width="10000" height="10000" viewBox="0 0 10000 10000"></svg>'
        with mock.patch(
            "subprocess.run", side_effect=AssertionError("renderer/host handoff")
        ) as renderer:
            self.assertIn(b'viewBox="0 0 10000 10000"', sanitize_svg(boundary))
        renderer.assert_not_called()

        over_by_one = b'<svg width="10000" height="10000.0001" viewBox="0 0 10000 10000.0001"></svg>'
        maximum_axes = b'<svg width="65536" height="65536" viewBox="0 0 65536 65536"></svg>'
        for payload in (over_by_one, maximum_axes):
            with self.subTest(payload=payload):
                self.assert_sanitize_rejected_without_handoff(payload, "pixel ceiling")

        boundary_rir = {
            "schemaVersion": "design-lab/reconstruction-ir/v1",
            "canvas": {"width": 10_000, "height": 10_000, "colorSpace": "srgb"},
            "layers": [],
        }
        with mock.patch(
            "subprocess.run", side_effect=AssertionError("renderer/host handoff")
        ) as renderer:
            self.assertIn(b'width="10000"', serialize_svg(boundary_rir, PROJECT_ROOT))
        renderer.assert_not_called()
        over_rir = copy.deepcopy(boundary_rir)
        over_rir["canvas"] = {
            "width": 10_001,
            "height": 10_000,
            "colorSpace": "srgb",
        }
        self.assert_serialize_rejected_without_handoff(over_rir, "pixel ceiling")

    def test_extreme_visual_numbers_fail_closed_and_boundaries_remain_valid(self) -> None:
        root = '<svg width="64" height="64" viewBox="0 0 64 64">{}</svg>'
        invalid = (
            ('<path d="M32 32" stroke="#000" stroke-width="1e308" stroke-miterlimit="1e308"/>', "product"),
            ('<path d="M32 32" stroke="#000" stroke-width="65"/>', "stroke-width"),
            ('<path d="M32 32" stroke="#000" stroke-miterlimit="17"/>', "miterlimit"),
            ('<path d="M32 32" stroke="#000" stroke-width="64" stroke-miterlimit="16"/>', "visual extent"),
            ('<text x="0" y="1" font-size="0">x</text>', "font-size"),
            ('<text x="0" y="1" font-size="1e308">x</text>', "font-size"),
            ('<defs><linearGradient id="g" x1="0" y1="0" x2="1e308" y2="64" gradientUnits="userSpaceOnUse"/></defs>', "linearGradient"),
            ('<defs><linearGradient id="g" x1="0" y1="0" x2="65" y2="64" gradientUnits="userSpaceOnUse"/></defs>', "linearGradient"),
            ('<defs><radialGradient id="g" cx="32" cy="32" r="33" gradientUnits="userSpaceOnUse"/></defs>', "radialGradient"),
            ('<defs><radialGradient id="g" cx="1e308" cy="32" r="1" gradientUnits="userSpaceOnUse"/></defs>', "radialGradient"),
        )
        for child, reason in invalid:
            payload = root.format(child).encode()
            with self.subTest(child=child):
                self.assert_sanitize_rejected_without_handoff(payload, reason)

        valid = root.format(
            '''<defs>
                 <linearGradient id="linear" x1="0" y1="0" x2="64" y2="64" gradientUnits="userSpaceOnUse"/>
                 <radialGradient id="radial" cx="32" cy="32" r="32" gradientUnits="userSpaceOnUse"/>
               </defs>
               <path d="M32 32" stroke="#000" stroke-width="8" stroke-miterlimit="16"/>
               <text x="0" y="64" font-size="64">x</text>'''
        ).encode()
        sanitized = sanitize_svg(valid)
        self.assertIn(b'stroke-miterlimit="16"', sanitized)
        self.assertIn(b'font-size="64"', sanitized)

        extreme_stroke = path_layer("extreme-stroke")
        extreme_stroke["style"] = {
            "fill": None,
            "stroke": "#000000",
            "strokeWidth": 1e308,
        }
        self.assert_serialize_rejected_without_handoff(
            rir(extreme_stroke), "product"
        )

        zero_font = text_layer("zero-font")
        zero_font["bounds"]["height"] = 0
        self.assert_serialize_rejected_without_handoff(
            rir(zero_font), "font-size"
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
