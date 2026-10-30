# SPDX-License-Identifier: MIT
"""DL-P1-130: OpenTimelineIO timeline contract (OTIO ``Timeline.1`` JSON).

Ownership boundary (read this first)
------------------------------------
**DESIGN-LAB does not own video rendering.** It produces an editorial plan -- a
clip layout with rational time and asset references -- and hands it to a video
host (Premiere / After Effects / Resolve class tool) through the
OpenTimelineIO ``.otio`` JSON interchange format. This module validates that
document, converts it to and from the small internal design-side plan
``{"tracks": [{"kind", "clips": [{"clip_id", "asset_ref", "start_seconds",
"duration_seconds", "rate", "metadata"}]}]}``, and reports layout facts. It
renders nothing, imports no OTIO library, starts no process and never probes the
filesystem.

``OTIO_SCHEMA_VERSION = "Timeline.1"`` is the OTIO schema label this module
targets: OTIO carries version identity in per-object ``OTIO_SCHEMA`` labels
(``Timeline.1``, ``Stack.1``, ``Track.1``, ``Clip.1``, ``Gap.1``,
``Transition.1``, ``TimeRange.1``, ``RationalTime.1``), and the ``.otio`` JSON
file -- not a DESIGN-LAB format -- is the interchange file between the two sides.

Semantic rules enforced in Python (a JSON Schema cannot express them)
--------------------------------------------------------------------
* track ``kind`` restricted to ``Video``/``Audio``; every item's schema label must
  match the container it sits in (a ``Track.1`` may only appear inside the
  timeline ``tracks`` stack);
* every rational time needs a positive ``rate``; every ``Gap.1`` needs a
  ``source_range``; every ``Clip.1`` needs a ``source_range`` too, because a clip
  whose extent would have to be read from a media reference ``available_range``
  cannot be resolved structurally (that is an unresolvable duration, not a default);
* ids declared under ``metadata.design_lab`` must be unique across the document;
* plan conversion is exact under one documented rounding rule: seconds are carried
  as ``RationalTime(value, rate)`` and read back as ``round(value / rate, 9)``.
  Plans must therefore express times with at most 9 decimal places (nanosecond
  resolution, the finest a professional timecode handoff needs);
* ``validate_against_assets`` fails closed when a clip references an asset that is
  not declared, or carries no resolvable external media reference at all.

Official ``Transition.1`` semantics, and the overlap formula this module reports
------------------------------------------------------------------------------
A ``Transition.1`` is not laid out sequentially: it consumes no track time and is
applied to the two items on either side. Its ``in_offset`` and ``out_offset`` are
``RationalTime`` values relative to the transition, and the range the transition
covers is::

    covered_range(transition) = [ transition_start - in_offset,
                                  transition_start + out_offset ]

where ``transition_start`` is the point in track time at which the two
neighbouring items meet -- the sequential end of the item before the transition,
because the transition itself takes no track time. The transition therefore covers
part of *both* neighbours: up to the last ``in_offset`` of the outgoing item and up
to the first ``out_offset`` of the incoming item, each clamped by that item's own
extent. :func:`overlaps` reports exactly that intersection; it keeps no second,
conflicting notion of overlap truth (in particular it does not report "the two
clips overlap by ``in_offset + out_offset``"), and it fails closed when a
transition sits at a track boundary or directly next to another transition, where
the covered range would be undefined.

:func:`overlaps` reports two kinds of record:

* ``"transition"`` -- one record per side, carrying the covered range and the
  length of its intersection with that neighbouring item;
* ``"parallel-stack"`` -- children of a ``Stack.1`` (including the tracks of
  ``Timeline.tracks``, which OTIO lays out in parallel) whose ranges genuinely
  intersect.

A sequential ``Track.1`` has no overlap other than the ones a transition creates.

Evidence: everything reachable from this module is E1 (STRUCTURAL). No OTIO
library run, no host import and no render is claimed.
"""
from __future__ import annotations

from ..runtime.paths import PROJECT_ROOT
from . import InteropError, load_schema, schema_errors

#: The OTIO schema label DESIGN-LAB targets; ``.otio`` JSON is the interchange format.
OTIO_SCHEMA_VERSION = "Timeline.1"

TIMELINE_SCHEMA = "Timeline.1"
STACK_SCHEMA = "Stack.1"
TRACK_SCHEMA = "Track.1"
CLIP_SCHEMA = "Clip.1"
GAP_SCHEMA = "Gap.1"
TRANSITION_SCHEMA = "Transition.1"
TIME_RANGE_SCHEMA = "TimeRange.1"
RATIONAL_TIME_SCHEMA = "RationalTime.1"
EXTERNAL_REFERENCE_SCHEMA = "ExternalReference.1"
OTHER_REFERENCE_SCHEMAS = (
    "MissingReference.1",
    "GeneratorReference.1",
    "ImageSequenceReference.1",
)

TRACK_KINDS = ("Video", "Audio")
ITEM_SCHEMAS = (CLIP_SCHEMA, GAP_SCHEMA, STACK_SCHEMA, TRANSITION_SCHEMA)

#: Seconds are read back at nanosecond resolution (see the module docstring).
TO_SECONDS_DECIMALS = 9
SECONDS_EPSILON = 10 ** (-TO_SECONDS_DECIMALS)

#: Official OTIO ``Transition.1`` semantics, written as the formula ``overlaps()``
#: implements. ``transition_start`` is the point at which the two neighbouring
#: items meet; ``in_offset``/``out_offset`` are rational times relative to it.
TRANSITION_COVERED_RANGE = (
    "covered_range(Transition.1) = [transition_start - in_offset, "
    "transition_start + out_offset]"
)

SCHEMA_PATH = PROJECT_ROOT / "design-lab/schemas/interop-timeline-otio.schema.json"

DEFAULT_TIMELINE_NAME = "design-lab-timeline"
#: Reserved key DESIGN-LAB owns inside OTIO's free-form metadata map.
METADATA_KEY = "design_lab"
TASK_ID = "DL-P1-130"


def _fail(message: str) -> "InteropError":
    return InteropError(message)


def _number(value, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{where} must be a number")
    return float(value)


def _text(value, where: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise _fail(f"{where} must be a nonempty string")
    return value


def _schema_errors(document) -> list[str]:
    return schema_errors(load_schema(SCHEMA_PATH), document)


def _label(node, where: str) -> str:
    if not isinstance(node, dict):
        raise _fail(f"{where} must be an OTIO object")
    return node.get("OTIO_SCHEMA")


def _require_schema(node, where: str, expected) -> dict:
    label = _label(node, where)
    allowed = expected if isinstance(expected, (tuple, list)) else (expected,)
    if label not in allowed:
        rendered = repr(allowed[0]) if len(allowed) == 1 else "one of " + ", ".join(
            repr(item) for item in allowed
        )
        raise _fail(f"{where} must carry OTIO_SCHEMA {rendered}; found {label!r}")
    return node


# --------------------------------------------------------------------------- #
# rational time
# --------------------------------------------------------------------------- #

def rational_time(seconds, rate) -> dict:
    """Build a ``RationalTime.1`` from seconds.

    ``value = seconds * rate``; an integral product is written as an integer so the
    JSON stays readable. A non-integral product keeps full float precision, because
    :func:`seconds_from` recovers seconds by rounding the quotient, not the product.
    """
    _number(seconds, "seconds")
    rate = _number(rate, "rate")
    if rate <= 0:
        raise _fail(f"RationalTime rate must be positive; got {rate!r}")
    product = float(seconds) * rate
    if abs(product - round(product)) < SECONDS_EPSILON:
        value = int(round(product))
    else:
        value = product
    return {"OTIO_SCHEMA": RATIONAL_TIME_SCHEMA, "rate": rate, "value": value}


def seconds_from(rational) -> float:
    """Read seconds back from a ``RationalTime.1`` under the documented rounding rule."""
    _require_schema(rational, "rational time", RATIONAL_TIME_SCHEMA)
    rate = _number(rational["rate"], "rational time rate")
    if rate <= 0:
        raise _fail(f"rational time rate must be positive; got {rate!r}")
    value = _number(rational["value"], "rational time value")
    return round(value / rate, TO_SECONDS_DECIMALS)


def time_range(start_seconds, duration_seconds, rate) -> dict:
    """Build a ``TimeRange.1``."""
    return {
        "OTIO_SCHEMA": TIME_RANGE_SCHEMA,
        "start_time": rational_time(start_seconds, rate),
        "duration": rational_time(duration_seconds, rate),
    }


def _range_seconds(value, where: str):
    _require_schema(value, where, TIME_RANGE_SCHEMA)
    return (seconds_from(value["start_time"]), seconds_from(value["duration"]))


def _metadata(node: dict, where: str) -> dict:
    metadata = node.get("metadata", {})
    if metadata is None:
        metadata = {}
    if not isinstance(metadata, dict):
        raise _fail(f"{where} metadata must be a free-form object")
    return metadata


def _design_lab_metadata(node: dict, where: str) -> dict:
    block = _metadata(node, where).get(METADATA_KEY)
    if block is None:
        return {}
    if not isinstance(block, dict):
        raise _fail(f"{where} metadata.{METADATA_KEY} must be an object")
    return block


def _item_id(node: dict, where: str):
    """The DESIGN-LAB identity of an item, when it declares one."""
    block = _design_lab_metadata(node, where)
    for key in ("clip_id", "id"):
        value = block.get(key)
        if value is not None:
            return _text(value, f"{where} metadata.{METADATA_KEY}.{key}")
    return None


def _label_of(node, where: str) -> str:
    identity = _item_id(node, where)
    if identity:
        return identity
    name = node.get("name")
    if isinstance(name, str) and name:
        return name
    return where


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def _register(node, where: str, report: dict, ids: dict) -> None:
    label = _label(node, where)
    if label == TIMELINE_SCHEMA:
        report["timeline_count"] += 1
    elif label == TRACK_SCHEMA:
        report["track_kinds"].append(node.get("kind"))
    elif label == CLIP_SCHEMA:
        report["clip_count"] += 1
    elif label == GAP_SCHEMA:
        report["gap_count"] += 1
    elif label == TRANSITION_SCHEMA:
        report["transition_count"] += 1
    identity = _item_id(node, where)
    if identity is not None:
        if identity in ids:
            raise _fail(
                f"duplicate DESIGN-LAB id {identity!r} at {where}; it is already used at {ids[identity]}"
            )
        ids[identity] = where


def _validate_item(node, where: str, allowed) -> dict:
    label = _label(node, where)
    if label not in allowed:
        raise _fail(
            f"{where} carries OTIO_SCHEMA {label!r}; this container accepts "
            + ", ".join(repr(item) for item in allowed)
        )
    if label == TRANSITION_SCHEMA:
        for key in ("in_offset", "out_offset"):
            if key not in node:
                raise _fail(f"{where} is a Transition.1 without {key}")
            seconds_from(node[key])
        if node.get("name") is not None:
            _text(node["name"], f"{where}.name", allow_empty=True)
    if label == GAP_SCHEMA:
        if "source_range" not in node:
            raise _fail(f"{where} is a Gap.1 without source_range; its duration would be undefined")
        _range_seconds(node["source_range"], f"{where} source_range")
    if label == STACK_SCHEMA:
        if not isinstance(node.get("children"), list):
            raise _fail(f"{where} children must be an array")
    if label == CLIP_SCHEMA:
        if node.get("source_range") is not None:
            _range_seconds(node["source_range"], f"{where} source_range")
        reference = node.get("media_reference")
        if reference is not None:
            _require_schema(
                reference,
                f"{where} media_reference",
                (EXTERNAL_REFERENCE_SCHEMA, *OTHER_REFERENCE_SCHEMAS),
            )
    if label == TRACK_SCHEMA and node.get("kind") not in TRACK_KINDS:
        raise _fail(
            f"{where} kind must be one of {', '.join(TRACK_KINDS)}; found {node.get('kind')!r}"
        )
    return node


def _walk(node, path: str, report: dict, ids: dict, *, allowed_children=ITEM_SCHEMAS) -> None:
    label = _label(node, path)
    _register(node, path, report, ids)
    if label == TIMELINE_SCHEMA:
        stack = _require_schema(node["tracks"], f"{path}.tracks", STACK_SCHEMA)
        _walk(stack, f"{path}.tracks", report, ids, allowed_children=(TRACK_SCHEMA,))
        return
    if label in (STACK_SCHEMA, TRACK_SCHEMA):
        children = node.get("children")
        if not isinstance(children, list):
            raise _fail(f"{path} children must be an array")
        for index, child in enumerate(children):
            where = f"{path}[{index}]"
            _validate_item(child, where, allowed_children)
            _walk(child, where, report, ids)


def validate_timeline(document) -> dict:
    """Validate an OTIO ``Timeline.1`` document; return a structural report.

    Structural rules come from ``interop-timeline-otio.schema.json``; the semantic
    rules listed in the module docstring are enforced here. Raises
    :class:`InteropError` naming the offending path, and never repairs input.
    """
    problems = _schema_errors(document)
    if problems:
        raise InteropError(f"timeline violates {SCHEMA_PATH.name}: " + "; ".join(problems))
    if document.get("OTIO_SCHEMA") != OTIO_SCHEMA_VERSION:
        raise _fail(
            f"timeline OTIO_SCHEMA must be {OTIO_SCHEMA_VERSION!r}; found "
            f"{document.get('OTIO_SCHEMA')!r}"
        )
    global_start = document.get("global_start_time")
    if global_start is not None:
        seconds_from(global_start)

    report = {"track_kinds": [], "clip_count": 0, "gap_count": 0, "transition_count": 0,
              "timeline_count": 0}
    ids: dict[str, str] = {}
    _walk(document, "timeline", report, ids)
    return {
        "schemaVersion": OTIO_SCHEMA_VERSION,
        "schema_path": SCHEMA_PATH.relative_to(PROJECT_ROOT).as_posix(),
        "track_count": len(report["track_kinds"]),
        "track_kinds": sorted(set(report["track_kinds"])),
        "clip_count": report["clip_count"],
        "gap_count": report["gap_count"],
        "transition_count": report["transition_count"],
        "declared_ids": sorted(ids),
        "duration_seconds": duration_seconds(document),
        "overlaps": overlaps(document),
    }


# --------------------------------------------------------------------------- #
# duration and layout
# --------------------------------------------------------------------------- #

def _children(node, where: str) -> list:
    children = node.get("children")
    if not isinstance(children, list):
        raise _fail(f"{where} children must be an array")
    return children


def _item_duration(node, where: str) -> float:
    label = _label(node, where)
    if label == TRANSITION_SCHEMA:
        return 0.0
    if label == GAP_SCHEMA:
        _start, duration = _range_seconds(node["source_range"], f"{where} source_range")
        if duration < 0:
            raise _fail(f"{where} has a negative duration")
        return duration
    if label == CLIP_SCHEMA:
        if node.get("source_range") is None:
            raise _fail(
                f"{where} is a Clip.1 without source_range; its timeline duration would have to "
                "come from the media reference available_range, which DESIGN-LAB cannot resolve "
                "structurally"
            )
        _start, duration = _range_seconds(node["source_range"], f"{where} source_range")
        if duration <= 0:
            raise _fail(f"{where} has a non-positive duration")
        return duration
    if label in (STACK_SCHEMA, TRACK_SCHEMA):
        # A Stack lays its children out in parallel; a Track sequences them.
        spans = [_item_duration(child, f"{where} child[{index}]")
                 for index, child in enumerate(_children(node, where))]
        if not spans:
            return 0.0
        return max(spans) if label == STACK_SCHEMA else sum(spans)
    raise _fail(f"{where} carries unsupported OTIO_SCHEMA {label!r}")


def duration_seconds(node) -> float:
    """Total duration in seconds of a ``Track.1``, ``Stack.1`` or ``Timeline.1``.

    A ``Track.1`` is sequential, so its duration is the sum of its children; a
    ``Stack.1`` (and the ``Timeline.tracks`` stack, whose tracks run in parallel)
    lasts as long as its longest child. ``Transition.1`` consumes no track time.
    """
    if not isinstance(node, dict):
        raise _fail("duration_seconds expects an OTIO object")
    label = _label(node, "node")
    if label == TIMELINE_SCHEMA:
        return duration_seconds(node["tracks"])
    if label in (TRACK_SCHEMA, STACK_SCHEMA):
        return round(_item_duration(node, label.lower()), TO_SECONDS_DECIMALS)
    raise _fail(f"duration_seconds expects a Timeline.1, Stack.1 or Track.1; found {label!r}")


def _stack_ranges(stack, where: str = "stack") -> list[dict]:
    """Timeline ranges of a stack's children, which OTIO lays out in parallel.

    Every child starts at the stack origin, so two children with a positive extent
    genuinely overlap. A ``Transition.1`` is not a child range of its own: it
    covers parts of the two items it sits between (see :func:`overlaps`).
    """
    ranges = []
    for index, child in enumerate(_children(stack, where)):
        child_where = f"{where}[{index}]"
        if _label(child, child_where) == TRANSITION_SCHEMA:
            continue
        duration = _item_duration(child, child_where)
        ranges.append({
            "id": _label_of(child, child_where),
            "start_seconds": 0.0,
            "end_seconds": duration,
            "duration_seconds": duration,
            "where": child_where,
        })
    return ranges


def _sequential_ranges(track, where: str = "track") -> list[dict]:
    """Timeline ranges of a track's items in track time.

    A ``Track.1`` sequences its children, so an item starts where the previous one
    ends. A ``Transition.1`` is skipped: OTIO applies it to the items on either
    side instead of laying it out, so it consumes no track time and has no range of
    its own. The ``index`` of each entry is the child's index among *all* the
    track's children, so it can be matched back to a transition's neighbours.
    """
    ranges = []
    cursor = 0.0
    for index, child in enumerate(_children(track, where)):
        item_where = f"{where}[{index}]"
        if _label(child, item_where) == TRANSITION_SCHEMA:
            continue
        duration = _item_duration(child, item_where)
        start = round(cursor, TO_SECONDS_DECIMALS)
        cursor = round(cursor + duration, TO_SECONDS_DECIMALS)
        ranges.append({
            "index": index,
            "id": _label_of(child, item_where),
            "start_seconds": start,
            "end_seconds": cursor,
            "duration_seconds": duration,
            "where": item_where,
        })
    return ranges


def _ordered(records: list[dict]) -> list[dict]:
    return sorted(records, key=lambda record: (record["reason"], record["a"], record["b"]))


def _transition_records(track, where: str = "track") -> list[dict]:
    """Overlaps a ``Transition.1`` creates, from the official covered-range formula.

    ``covered_range = [transition_start - in_offset, transition_start + out_offset]``
    (see :data:`TRANSITION_COVERED_RANGE` and the module docstring), intersected with
    each neighbouring item's own range. The intersection can be shorter than the
    offset when the offset reaches past that item.
    """
    children = _children(track, where)
    sequential = {entry["index"]: entry for entry in _sequential_ranges(track, where)}
    records: list[dict] = []
    for index, child in enumerate(children):
        item_where = f"{where}[{index}]"
        if _label(child, item_where) != TRANSITION_SCHEMA:
            continue
        if index == 0 or index + 1 >= len(children):
            raise _fail(
                f"{item_where} is a Transition.1 at a track boundary; a transition needs an item "
                "on both sides"
            )
        for neighbour_index in (index - 1, index + 1):
            neighbour_where = f"{where}[{neighbour_index}]"
            if _label(children[neighbour_index], neighbour_where) == TRANSITION_SCHEMA:
                raise _fail(
                    f"{item_where} is a Transition.1 directly next to another Transition.1 at "
                    f"{neighbour_where}; OTIO applies a transition to the two items on either side, "
                    "so the covered range of two adjacent transitions is undefined"
                )
        offsets = {"in_offset": seconds_from(child["in_offset"]),
                   "out_offset": seconds_from(child["out_offset"])}
        for key, value in offsets.items():
            if value < 0:
                raise _fail(f"{item_where} {key} must not be negative; got {value}")
        transition_start = sequential[index - 1]["end_seconds"]
        covered_start = round(transition_start - offsets["in_offset"], TO_SECONDS_DECIMALS)
        covered_end = round(transition_start + offsets["out_offset"], TO_SECONDS_DECIMALS)
        for neighbour_index, side in ((index - 1, "in_offset"), (index + 1, "out_offset")):
            entry = sequential[neighbour_index]
            span = min(covered_end, entry["end_seconds"]) - max(covered_start,
                                                                entry["start_seconds"])
            if span <= SECONDS_EPSILON:
                continue
            records.append({
                "reason": "transition",
                "a": entry["id"],
                "b": _label_of(child, item_where),
                "covered_side": side,
                "in_offset_seconds": offsets["in_offset"],
                "out_offset_seconds": offsets["out_offset"],
                "transition_start_seconds": transition_start,
                "covered_start_seconds": covered_start,
                "covered_end_seconds": covered_end,
                "overlap_seconds": round(span, TO_SECONDS_DECIMALS),
                "where": item_where,
            })
    return _ordered(records)


def _stack_records(stack, where: str) -> list[dict]:
    """Parallel-overlap records of a stack's children, plus transitions inside its tracks."""
    ranges = _stack_ranges(stack, where)
    records: list[dict] = []
    for first in range(len(ranges)):
        for second in range(first + 1, len(ranges)):
            left, right = ranges[first], ranges[second]
            span = min(left["end_seconds"], right["end_seconds"]) - max(
                left["start_seconds"], right["start_seconds"]
            )
            if span <= SECONDS_EPSILON:
                continue
            records.append({
                "reason": "parallel-stack",
                "a": left["id"],
                "b": right["id"],
                "overlap_seconds": round(span, TO_SECONDS_DECIMALS),
                "where": f"{left['where']} + {right['where']}",
            })
    for index, child in enumerate(_children(stack, where)):
        child_where = f"{where}[{index}]"
        if _label(child, child_where) == TRACK_SCHEMA:
            # A stacked Track.1 runs in parallel with its siblings, and its own
            # transitions still cover parts of its neighbouring clips.
            records.extend(_transition_records(child, child_where))
    return records


def overlaps(node) -> list[dict]:
    """Report the time ranges that genuinely overlap, in a deterministic order.

    The definition is derived from official OTIO transition semantics; there is no
    locally invented second notion of overlap truth. Documented formula::

        covered_range(transition) = [ transition_start - in_offset,
                                      transition_start + out_offset ]

    with ``transition_start`` the point at which the two neighbouring items meet
    (the sequential end of the item before the transition, since a ``Transition.1``
    consumes no track time). Each covered range is intersected with the two
    neighbouring clips; a record is emitted per non-empty intersection.

    Each record names its ``reason``:

    * ``"transition"`` -- one record per side of a ``Transition.1``. ``a`` is the
      neighbouring item the transition covers, ``b`` is the transition, and
      ``overlap_seconds`` is the length of ``[covered_start_seconds,
      covered_end_seconds]`` inside that item's range -- never ``in_offset +
      out_offset``. A sequential ``Track.1`` without transitions has no overlaps by
      construction.
    * ``"parallel-stack"`` -- the children of a ``Stack.1`` start at the same point,
      so any two children with intersecting extents overlap. This includes the
      tracks of ``Timeline.tracks``: OTIO lays stacked tracks out in parallel, so
      genuinely parallel tracks in a ``Stack`` are reported. Overlaps *inside* those
      tracks (their transitions) are reported as well; separate tracks are not
      otherwise treated as sequential.

    A transition at a track boundary, or directly next to another transition, fails
    closed: its covered range would be undefined.
    """
    if not isinstance(node, dict):
        raise _fail("overlaps expects an OTIO object")
    label = _label(node, "node")
    if label == TIMELINE_SCHEMA:
        stack = _require_schema(node["tracks"], "timeline.tracks", STACK_SCHEMA)
        return _ordered(_stack_records(stack, "timeline.tracks"))
    if label == TRACK_SCHEMA:
        return _transition_records(node, "track")
    if label == STACK_SCHEMA:
        return _ordered(_stack_records(node, "stack"))
    raise _fail(f"overlaps expects a Timeline.1, Stack.1 or Track.1; found {label!r}")


# --------------------------------------------------------------------------- #
# asset declaration check
# --------------------------------------------------------------------------- #

def _asset_ref(clip, where: str) -> str:
    reference = clip.get("media_reference")
    if reference is None:
        raise _fail(f"{where} has no media_reference; its asset is undeclared")
    label = reference.get("OTIO_SCHEMA")
    if label != EXTERNAL_REFERENCE_SCHEMA:
        raise _fail(
            f"{where} references {label!r}; only ExternalReference.1 names a declared asset. "
            "Offline (MissingReference.1) and generated media cannot be checked against "
            "declared assets"
        )
    return _text(reference.get("target_url"), f"{where} media_reference.target_url")


def _declared_assets(asset_refs) -> set[str]:
    if isinstance(asset_refs, dict):
        declared = {_text(key, f"asset_refs key {key!r}") for key in asset_refs}
    elif isinstance(asset_refs, (list, tuple, set, frozenset)):
        declared = set()
        for index, entry in enumerate(asset_refs):
            if isinstance(entry, str):
                declared.add(_text(entry, f"asset_refs[{index}]"))
            elif isinstance(entry, dict):
                value = entry.get("asset_ref", entry.get("ref", entry.get("target_url")))
                declared.add(_text(value, f"asset_refs[{index}].asset_ref"))
            else:
                raise _fail(f"asset_refs[{index}] must be a string or a record with asset_ref")
    else:
        raise _fail("asset_refs must be a sequence of asset references or a mapping of them")
    if not declared:
        raise _fail("asset_refs must declare at least one asset")
    return declared


def validate_against_assets(timeline, asset_refs) -> dict:
    """Fail closed when a clip references an asset that is not declared.

    Every ``Clip.1`` must carry an ``ExternalReference.1`` whose ``target_url`` is
    one of the declared asset references. Offline and generated media, and clips
    with no media reference at all, are rejected by name rather than assumed.
    """
    validate_timeline(timeline)
    declared = _declared_assets(asset_refs)
    used: dict[str, list[str]] = {}
    counts = {"clips": 0}

    def walk(node, path):
        label = _label(node, path)
        if label == CLIP_SCHEMA:
            counts["clips"] += 1
            ref = _asset_ref(node, path)
            if ref not in declared:
                raise _fail(
                    f"clip {path} references undeclared asset {ref!r}; declared assets are: "
                    + ", ".join(sorted(declared))
                )
            used.setdefault(ref, []).append(_label_of(node, path))
        if label == TIMELINE_SCHEMA:
            walk(node["tracks"], f"{path}.tracks")
        elif label in (STACK_SCHEMA, TRACK_SCHEMA):
            for index, child in enumerate(_children(node, path)):
                walk(child, f"{path}[{index}]")

    walk(timeline, "timeline")
    return {
        "clip_count": counts["clips"],
        "declared_asset_count": len(declared),
        "referenced_assets": sorted(used),
        "unused_assets": sorted(declared - set(used)),
        "clips_per_asset": {ref: len(used[ref]) for ref in sorted(used)},
    }


# --------------------------------------------------------------------------- #
# plan <-> timeline
# --------------------------------------------------------------------------- #

def _free_metadata(carrier, where: str) -> dict:
    metadata = carrier.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise _fail(f"{where} metadata must be an object")
    if METADATA_KEY in metadata:
        raise _fail(
            f"{where} metadata may not use the reserved key {METADATA_KEY!r}; DESIGN-LAB owns it "
            "inside OTIO metadata"
        )
    return dict(metadata)


def _plan_clip(clip, where: str) -> dict:
    clip_id = _text(clip.get("clip_id"), f"{where}.clip_id")
    asset_ref = _text(clip.get("asset_ref"), f"{where}.asset_ref")
    rate = _number(clip.get("rate", 24), f"{where}.rate")
    if rate <= 0:
        raise _fail(f"{where}.rate must be positive")
    start = _number(clip.get("start_seconds"), f"{where}.start_seconds")
    duration = _number(clip.get("duration_seconds"), f"{where}.duration_seconds")
    if duration <= 0:
        raise _fail(f"{where}.duration_seconds must be positive")
    source_start = _number(clip.get("source_start_seconds", 0.0), f"{where}.source_start_seconds")
    if start < 0 or source_start < 0:
        raise _fail(f"{where} start times must not be negative")
    return {
        "clip_id": clip_id,
        "asset_ref": asset_ref,
        "source_start_seconds": source_start,
        "start_seconds": start,
        "duration_seconds": duration,
        "rate": rate,
        "metadata": _free_metadata(clip, where),
    }


def canonical_plan(plan) -> dict:
    """Fill every optional plan field with its default and sort clips by layout.

    ``from_timeline(to_timeline(plan)) == canonical_plan(plan)`` is the exact
    round-trip guarantee: the canonical plan always states ``name``, ``metadata``
    and ``global_start_time_seconds``, every track states ``name``, ``kind`` and
    ``metadata``, and every clip states ``clip_id``, ``asset_ref``,
    ``source_start_seconds``, ``start_seconds``, ``duration_seconds``, ``rate`` and
    ``metadata``. Clips are ordered by ``(start_seconds, clip_id)``.
    """
    if not isinstance(plan, dict):
        raise _fail("timeline plan must be an object")
    tracks = plan.get("tracks", [])
    if not isinstance(tracks, list):
        raise _fail("timeline plan tracks must be an array")
    name = _text(plan.get("name", DEFAULT_TIMELINE_NAME), "plan name")
    metadata = plan.get("metadata") or {}
    if not isinstance(metadata, dict):
        raise _fail("plan metadata must be an object")
    if METADATA_KEY in metadata:
        raise _fail(f"plan metadata may not use the reserved key {METADATA_KEY!r}")
    global_start = plan.get("global_start_time_seconds")
    if global_start is not None:
        _number(global_start, "plan global_start_time_seconds")
    canonical = {
        "name": name,
        "metadata": dict(metadata),
        "global_start_time_seconds": global_start,
        "tracks": [],
    }
    for index, track in enumerate(tracks):
        where = f"plan tracks[{index}]"
        if not isinstance(track, dict):
            raise _fail(f"{where} must be an object")
        kind = track.get("kind")
        if kind not in TRACK_KINDS:
            raise _fail(f"{where}.kind must be one of {', '.join(TRACK_KINDS)}; got {kind!r}")
        clips = track.get("clips", [])
        if not isinstance(clips, list):
            raise _fail(f"{where}.clips must be an array")
        resolved = [_plan_clip(clip, f"{where}.clips[{clip_index}]")
                    for clip_index, clip in enumerate(clips)]
        canonical["tracks"].append({
            "name": _text(track.get("name", kind), f"{where}.name"),
            "kind": kind,
            "metadata": _free_metadata(track, where),
            "clips": sorted(resolved, key=lambda clip: (clip["start_seconds"], clip["clip_id"])),
        })
    return canonical


def to_timeline(plan) -> dict:
    """Convert a design-side plan into an OTIO ``Timeline.1`` document.

    Clips are laid out on their track at ``start_seconds``; the space before a clip
    is filled with a ``Gap.1`` so OTIO's sequential layout matches the plan exactly.
    Clips that would overlap fail closed: the internal plan has no overlap concept
    (author a ``Stack.1`` directly in OTIO for layered composites).
    """
    canonical = canonical_plan(plan)
    tracks = []
    for track_index, track in enumerate(canonical["tracks"]):
        where = f"plan tracks[{track_index}]"
        children: list[dict] = []
        cursor = 0.0
        seen_ids: set[str] = set()
        for clip in track["clips"]:
            if clip["clip_id"] in seen_ids:
                raise _fail(f"{where} declares clip_id {clip['clip_id']!r} more than once")
            seen_ids.add(clip["clip_id"])
            start = round(clip["start_seconds"], TO_SECONDS_DECIMALS)
            if start < cursor - SECONDS_EPSILON:
                raise _fail(
                    f"{where} clip {clip['clip_id']!r} starts at {start}s but the track is already "
                    f"occupied until {cursor}s; the internal plan has no overlap concept"
                )
            gap = round(start - cursor, TO_SECONDS_DECIMALS)
            if gap > 0:
                children.append({
                    "OTIO_SCHEMA": GAP_SCHEMA,
                    "source_range": time_range(0.0, gap, clip["rate"]),
                    "metadata": {},
                })
            children.append({
                "OTIO_SCHEMA": CLIP_SCHEMA,
                "name": clip["clip_id"],
                "metadata": {
                    **clip["metadata"],
                    METADATA_KEY: {
                        "task_id": TASK_ID,
                        "clip_id": clip["clip_id"],
                        "rate": clip["rate"],
                        "source_start_seconds": clip["source_start_seconds"],
                    },
                },
                "source_range": time_range(clip["source_start_seconds"], clip["duration_seconds"],
                                           clip["rate"]),
                "media_reference": {
                    "OTIO_SCHEMA": EXTERNAL_REFERENCE_SCHEMA,
                    "target_url": clip["asset_ref"],
                    "available_range": None,
                    "metadata": {},
                },
            })
            cursor = round(start + clip["duration_seconds"], TO_SECONDS_DECIMALS)
        tracks.append({
            "OTIO_SCHEMA": TRACK_SCHEMA,
            "name": track["name"],
            "kind": track["kind"],
            "metadata": {**track["metadata"], METADATA_KEY: {"task_id": TASK_ID}},
            "source_range": None,
            "children": children,
        })
    global_start = canonical["global_start_time_seconds"]
    return {
        "OTIO_SCHEMA": TIMELINE_SCHEMA,
        "name": canonical["name"],
        "global_start_time": None if global_start is None else rational_time(global_start, 1),
        "metadata": {
            **canonical["metadata"],
            METADATA_KEY: {
                "task_id": TASK_ID,
                "otio_schema_version": OTIO_SCHEMA_VERSION,
                "interchange_format": ".otio JSON (OpenTimelineIO)",
                "evidence": "E1_STRUCTURAL_ONLY",
                "rendering": "NOT_OWNED_BY_DESIGN_LAB",
            },
        },
        "tracks": {
            "OTIO_SCHEMA": STACK_SCHEMA,
            "name": "tracks",
            "metadata": {},
            "source_range": None,
            "children": tracks,
        },
    }


def from_timeline(document) -> dict:
    """Convert an OTIO ``Timeline.1`` document into the design-side plan.

    Only the plan's vocabulary survives: clips with an external reference, gaps,
    tracks and rational time. A ``Transition.1`` or a nested ``Stack.1`` inside a
    track is rejected by name -- the internal plan has no representation for them,
    and silently dropping editorial structure would be a false round trip.
    """
    validate_timeline(document)
    plan = {
        "name": document.get("name", DEFAULT_TIMELINE_NAME),
        "metadata": {key: value for key, value in _metadata(document, "timeline").items()
                     if key != METADATA_KEY},
        "global_start_time_seconds": (None if document.get("global_start_time") is None
                                      else seconds_from(document["global_start_time"])),
        "tracks": [],
    }
    for track_index, track in enumerate(document["tracks"]["children"]):
        where = f"tracks[{track_index}]"
        cursor = 0.0
        clips = []
        for child_index, child in enumerate(track["children"]):
            child_where = f"{where}.children[{child_index}]"
            label = _label(child, child_where)
            if label == GAP_SCHEMA:
                _start, gap_duration = _range_seconds(child["source_range"],
                                                      f"{child_where} source_range")
                cursor = round(cursor + gap_duration, TO_SECONDS_DECIMALS)
                continue
            if label == TRANSITION_SCHEMA:
                raise _fail(
                    f"{child_where} is a Transition.1; the internal design-side plan has no "
                    "transition concept and dropping it would lose editorial structure"
                )
            if label == STACK_SCHEMA:
                raise _fail(
                    f"{child_where} is a nested Stack.1; the internal design-side plan is flat per "
                    "track. Read the OTIO document directly for stacked layers"
                )
            source_start, duration = _range_seconds(child["source_range"],
                                                    f"{child_where} source_range")
            block = _design_lab_metadata(child, child_where)
            clip_id = block.get("clip_id")
            if clip_id is None:
                name = child.get("name")
                clip_id = _text(name, f"{child_where} name", allow_empty=True) or None
            else:
                _text(clip_id, f"{child_where} metadata.{METADATA_KEY}.clip_id")
            if not clip_id:
                raise _fail(
                    f"{child_where} carries neither metadata.{METADATA_KEY}.clip_id nor a name; "
                    "the plan needs a stable clip identity"
                )
            rate = block.get("rate")
            if rate is None:
                rate = _number(child["source_range"]["duration"]["rate"],
                               f"{child_where} source_range rate")
            else:
                _number(rate, f"{child_where} metadata.{METADATA_KEY}.rate")
            clips.append({
                "clip_id": clip_id,
                "asset_ref": _asset_ref(child, child_where),
                "source_start_seconds": source_start,
                "start_seconds": round(cursor, TO_SECONDS_DECIMALS),
                "duration_seconds": duration,
                "rate": rate,
                "metadata": {key: value for key, value in _metadata(child, child_where).items()
                             if key != METADATA_KEY},
            })
            cursor = round(cursor + duration, TO_SECONDS_DECIMALS)
        plan["tracks"].append({
            "name": track.get("name", track["kind"]),
            "kind": track["kind"],
            "metadata": {key: value for key, value in _metadata(track, where).items()
                         if key != METADATA_KEY},
            "clips": clips,
        })
    return plan


def roundtrip(plan) -> dict:
    """``from_timeline(to_timeline(plan))`` -- exact for canonical plans."""
    return from_timeline(to_timeline(plan))
