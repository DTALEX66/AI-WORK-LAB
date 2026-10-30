# SPDX-License-Identifier: MIT
"""DL-TP-T06 (MULTIMODAL-2026-09-05): planar decomposition object mapping (structural).

Structural layer only. Objects carry an honest mapping_state; host_object_id is
only ever set by a host-side verifier, never inferred here. OCR and vector
tracing are replaceable module seams (Protocol) - this module never claims one
of them ran or succeeded.

Invariants:
- text objects with no verified host object stay mapping_state='unmapped';
- a locked object cannot be silently re-mapped by another module;
- font substitutions are explicit (matched/substituted/missing), never hidden.
"""
from __future__ import annotations

import json
import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any, Protocol


class DecomposeModule(Protocol):
    """Replaceable planar-analysis module (OCR / vector trace / heuristic)."""

    module_id: str

    def detect(self, source_path: str) -> list[dict[str, Any]]:
        """Return candidate objects with kind/region; must not set host ids."""


class DecompositionError(RuntimeError):
    pass


@dataclass(frozen=True)
class CanvasRegion:
    x: float
    y: float
    width: float
    height: float


@dataclass
class PlanObject:
    object_id: str
    kind: str  # text/shape/image/occlusion/group/unknown
    region: CanvasRegion
    module: str | None = None
    text_content: str | None = None
    font_status: str = "unknown"
    mapping_state: str = "unmapped"  # unmapped/auto/corrected/locked/unrecovered
    host_object_id: str | None = None
    note: str | None = None
    confidence: float | None = None
    source_polygon: tuple[tuple[float, float], ...] | None = None

    def validate(self) -> None:
        if not self.object_id or not self.kind:
            raise DecompositionError(f"object {self.object_id!r} incomplete")
        if self.mapping_state not in ("unmapped", "auto", "corrected", "locked", "unrecovered"):
            raise DecompositionError(f"object {self.object_id}: invalid mapping_state")
        if self.font_status not in ("matched", "substituted", "missing", "unknown"):
            raise DecompositionError(f"object {self.object_id}: invalid font_status")
        if self.mapping_state == "unmapped" and self.host_object_id is not None:
            raise DecompositionError(f"object {self.object_id}: unmapped cannot carry host_object_id")
        if self.host_object_id is not None and self.mapping_state == "unrecovered":
            raise DecompositionError(f"object {self.object_id}: unrecovered cannot carry host_object_id")

    def lock(self) -> None:
        self.validate()
        if self.mapping_state == "unrecovered":
            raise DecompositionError(f"object {self.object_id}: unrecovered cannot be locked")
        if self.host_object_id is None:
            raise DecompositionError(f"object {self.object_id}: cannot lock without a host object")
        self.mapping_state = "locked"

    def mark_host_mapping(self, host_object_id: str, *, by_user: bool = False) -> None:
        """Host-side verification result (called by a verifier, never by a module)."""
        if self.mapping_state == "locked":
            raise DecompositionError(f"object {self.object_id}: locked; user must unlock to remap")
        self.host_object_id = host_object_id
        self.mapping_state = "corrected" if by_user else "auto"


@dataclass
class Plan:
    decomposition_id: str
    source_ref: str
    source_sha256: str
    canvas: CanvasRegion
    objects: list[PlanObject] = field(default_factory=list)

    @classmethod
    def from_ocr(cls, *, decomposition_id: str, source_ref: str,
                 source_sha256: str, canvas: tuple[int, int], module: str,
                 detections: list[dict[str, Any]]) -> Plan:
        """Map pixel-space OCR observations; no inference, file I/O or host proof.

        Callers bind source bytes and backend provenance separately. This seam
        accepts only bounded convex quadrilaterals, preserving text confidence
        independently from unknown fonts and unrecovered non-text content.
        """
        if (not all(isinstance(v, str) and 0 < len(v) <= 4096
                    for v in (decomposition_id, source_ref, module))
                or not isinstance(source_sha256, str)
                or not re.fullmatch(r'sha256:[0-9a-f]{64}', source_sha256)
                or not isinstance(canvas, (tuple, list)) or len(canvas) != 2
                or any(type(v) is not int or not 1 <= v <= 16383 for v in canvas)
                or canvas[0] * canvas[1] > 25_000_000):
            raise DecompositionError('invalid OCR source identity or canvas')
        if not isinstance(detections, list) or len(detections) > 256:
            raise DecompositionError('OCR detections must be a bounded list')
        plan = cls(decomposition_id, source_ref, source_sha256, CanvasRegion(0, 0, *canvas))
        total = 0
        for raw in detections:
            if not isinstance(raw, dict) or set(raw) != {'text', 'confidence', 'polygon'}:
                raise DecompositionError('invalid OCR fields; host claims are forbidden')
            text, confidence, polygon = raw['text'], raw['confidence'], raw['polygon']
            if (not isinstance(text, str) or not text.strip() or len(text) > 4096
                    or type(confidence) not in (int, float) or not math.isfinite(confidence)
                    or not 0 <= confidence <= 1):
                raise DecompositionError('invalid OCR text or confidence')
            total += len(text)
            if total > 16384:
                raise DecompositionError('OCR text exceeds aggregate limit')
            if not isinstance(polygon, (list, tuple)) or len(polygon) != 4:
                raise DecompositionError('OCR requires a convex quadrilateral')
            points = []
            for point in polygon:
                if (not isinstance(point, (list, tuple)) or len(point) != 2
                        or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
                        or not 0 <= point[0] <= canvas[0] or not 0 <= point[1] <= canvas[1]):
                    raise DecompositionError('OCR polygon escapes canvas or is malformed')
                points.append(tuple(float(v) for v in point))
            turns = []
            for i in range(4):
                a, b, c = points[i], points[(i+1)%4], points[(i+2)%4]
                turns.append((b[0]-a[0])*(c[1]-b[1])-(b[1]-a[1])*(c[0]-b[0]))
            if not (all(t > 0 for t in turns) or all(t < 0 for t in turns)):
                raise DecompositionError('OCR polygon is degenerate or non-convex')
            # Canonicalize winding/start vertex, not detector list order or score.
            variants = [points[i:]+points[:i] for i in range(4)]
            reverse = list(reversed(points))
            variants += [reverse[i:]+reverse[:i] for i in range(4)]
            identity = json.dumps([source_sha256, text, min(variants)], ensure_ascii=False,
                                  allow_nan=False, separators=(',', ':'))
            object_id = 'ocr-' + hashlib.sha256(identity.encode('utf-8')).hexdigest()[:24]
            xs, ys = [p[0] for p in points], [p[1] for p in points]
            plan.objects.append(PlanObject(object_id, 'text',
                CanvasRegion(min(xs), min(ys), max(xs)-min(xs), max(ys)-min(ys)),
                module=module, text_content=text, confidence=float(confidence),
                source_polygon=tuple(points), note='OCR hypothesis; font, style and host mapping unverified'))
        plan.objects.append(PlanObject('unrecovered-content', 'unknown', CanvasRegion(0, 0, *canvas),
            module=module, mapping_state='unrecovered',
            note='Non-text content and occlusion remain unanalyzed; not a recovered background layer'))
        plan.validate()
        return plan

    def to_contract(self) -> dict[str, Any]:
        return {
            "decomposition_id": self.decomposition_id,
            "schemaVersion": "design-lab/planar-decomposition/v1",
            "source_ref": {"path": self.source_ref, "sha256": self.source_sha256},
            "canvas": {
                "width": int(self.canvas.width),
                "height": int(self.canvas.height),
            },
            "objects": [
                {
                    "object_id": o.object_id,
                    "kind": o.kind,
                    "region": {
                        "x": o.region.x,
                        "y": o.region.y,
                        "width": o.region.width,
                        "height": o.region.height,
                    },
                    "text_content": o.text_content,
                    "font_status": o.font_status,
                    "mapping_state": o.mapping_state,
                    "host_object_id": o.host_object_id,
                    "module": o.module,
                    "note": o.note or "",
                    **({"confidence": o.confidence} if o.confidence is not None else {}),
                    **({"source_polygon": [list(p) for p in o.source_polygon]}
                       if o.source_polygon is not None else {}),
                }
                for o in self.objects
            ],
        }

    def to_json(self) -> str:
        return json.dumps(self.to_contract(), ensure_ascii=False, sort_keys=True)

    def validate(self) -> None:
        if not self.decomposition_id or not self.source_ref:
            raise DecompositionError("decomposition identity incomplete")
        ids = [o.object_id for o in self.objects]
        if len(ids) != len(set(ids)):
            raise DecompositionError("duplicate object_id")
        for o in self.objects:
            o.validate()
