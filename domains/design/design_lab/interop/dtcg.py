# SPDX-License-Identifier: MIT
"""DL-P0-110: DTCG design-token documents (Design Tokens Community Group, 2025.10).

What this module does
---------------------
It adopts the DTCG token format (``SCHEMA_VERSION = "2025.10"``) as DESIGN-LAB's
token interchange format instead of inventing a local one, and provides the
contract that token documents are judged against:

* ``validate_document`` -- structural validation against
  ``design-lab/schemas/interop-dtcg-document.schema.json`` (draft 2020-12) plus
  the semantic rules a JSON Schema cannot express: ``$type`` inheritance down the
  group tree, alias references written as ``{group.token}`` that must resolve,
  rejection of alias cycles, composite member completeness and per-type value
  shape.
* ``flatten`` / ``to_document`` / ``roundtrip`` -- a lossless flat projection and
  its inverse.
* ``to_css_variables`` -- a deterministic CSS custom-property projection. A
  projection is *not* the source of truth; the DTCG document is.

Relationship to the existing repository entry points
----------------------------------------------------
``design-lab/scripts/convert_tokens_dtcg.py`` remains the conversion entry point
that *writes* a DTCG document from a ``design-tokens.json`` source and
``design-lab/scripts/verify_dtcg_tokens.py`` remains the alignment check for the
in-repo design systems. This module is the contract provider those artifacts are
compared against, not a replacement for them.

Boundary of this module
-----------------------
JSON in, JSON out. It never opens a design application, never starts a process,
never touches the network and never writes a file. All evidence it can produce is
E1 (STRUCTURAL); no live token-tool run and no third-party round trip is claimed.

Canonical strictness (DTCG 2025.10 stable)
-----------------------------------------
``validate_document``, ``flatten`` and ``roundtrip`` accept **canonical** DTCG
documents only, and none of them takes a permissive flag:

* the ``typography`` composite requires all five members -- ``fontFamily``,
  ``fontSize``, ``fontWeight``, ``letterSpacing`` and ``lineHeight``. A missing
  ``letterSpacing`` is a validation error, not a tolerated deviation.
* ``string`` and ``boolean`` are pre-2025.10 types emitted by the in-repo
  converter (``theme``, ``reduce-enabled``). They are not DTCG 2025.10 types, so
  the canonical path rejects them outright; the canonical schema file is not
  relaxed for them either.

Legacy tolerance lives in a separate, explicitly named adapter
-------------------------------------------------------------
:func:`from_legacy_document` converts a pre-2025.10 document into canonical form
and :func:`validate_legacy_document` is the adapter's validation entry point.
Neither widens the canonical contract, and neither is reachable by accident: the
canonical entry points no longer have an ``allow_legacy_types`` option.

What the adapter does, and what it refuses to guess:

* a legacy ``string``/``boolean`` token has no canonical DTCG 2025.10 type. The
  adapter does not coerce it into a canonical type it is not; it moves the token
  *verbatim* into the document ``$extensions`` map under
  ``com.design-lab.legacy-adapter``, keyed by its flattened path, and reports it
  as unmapped.
* a legacy ``typography`` token whose ``$value`` omits ``letterSpacing`` gets CSS
  ``normal`` tracking written as ``"0px"``, and the token records the synthesized
  member under ``$extensions`` so the addition is never silent.

Both in-repo ``design-tokens.dtcg.json`` files are **legacy** documents: they
carry ``$type: "string"``/``"boolean"`` and their ``typography`` tokens omit
``letterSpacing``. They are read through the adapter.
"""
from __future__ import annotations

import functools
import json
import re

from ..runtime.state_resources import repo_resource
from . import InteropError, load_schema as _load_schema, schema_errors

SCHEMA_VERSION = "2025.10"
SCHEMA_PATH = repo_resource('schemas/interop-dtcg-document.schema.json')
SCHEMA_REPOSITORY_PATH = 'design-lab/schemas/interop-dtcg-document.schema.json'

#: The token types defined by DTCG 2025.10.
TOKEN_TYPES = (
    "color",
    "dimension",
    "duration",
    "fontFamily",
    "fontWeight",
    "number",
    "cubicBezier",
    "strokeStyle",
    "typography",
    "shadow",
    "border",
    "transition",
    "gradient",
)

#: Types whose value is a structured object rather than a scalar.
COMPOSITE_TYPES = ("typography", "shadow", "border", "transition", "gradient")

#: Members DTCG 2025.10 requires on a ``typography`` value. All five are required;
#: the canonical path has no relaxation (see the module docstring).
TYPOGRAPHY_MEMBERS = ("fontFamily", "fontSize", "fontWeight", "letterSpacing", "lineHeight")

#: Pre-2025.10 types emitted by the existing in-repo converter. Not DTCG 2025.10
#: types: the canonical path rejects them and only the legacy adapter sees them.
LEGACY_TYPES = ("string", "boolean")

#: Vendor extension namespace the legacy adapter writes into ``$extensions``.
LEGACY_ADAPTER_NAMESPACE = "com.design-lab.legacy-adapter"
#: Value the adapter writes for a ``typography`` value that omits ``letterSpacing``
#: (CSS ``normal`` tracking).
LEGACY_LETTER_SPACING = "0px"

_COLOR_SPACES = (
    "srgb", "srgb-linear", "display-p3", "a98-rgb", "prophoto-rgb", "rec2020",
    "xyz-d65", "xyz-d50", "lab", "lch", "oklab", "oklch",
)
_DIMENSION_UNITS = ("px", "rem", "em", "%", "pt", "cm", "mm", "in", "vw", "vh")
_DURATION_UNITS = ("ms", "s")
_FONT_WEIGHT_KEYWORDS = (
    "thin", "extralight", "ultralight", "light", "normal", "regular", "book",
    "medium", "semibold", "demibold", "bold", "extrabold", "ultrabold", "black",
    "heavy", "extrablack", "ultrablack",
)
_STROKE_STYLE_KEYWORDS = (
    "solid", "dashed", "dotted", "double", "groove", "ridge", "outset", "inset",
)
_LINE_CAPS = ("round", "butt", "square")
_RESERVED_GROUP_KEYS = ("$type", "$description", "$extensions", "$deprecated")
_RESERVED_DOCUMENT_KEYS = ("$schema", *_RESERVED_GROUP_KEYS)

_ALIAS_RE = re.compile(r"^\{(?P<target>[^{}\s][^{}]*)\}$")
_DIMENSION_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:%s)$" % "|".join(_DIMENSION_UNITS))
_DURATION_RE = re.compile(r"^-?\d+(?:\.\d+)?(?:%s)$" % "|".join(_DURATION_UNITS))
_HEX_COLOR_RE = re.compile(r"^#[0-9a-fA-F]{3,8}$")
_COLOR_FUNCTION_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*\([^;{}]*\)$")
_COLOR_KEYWORD_RE = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]*$")
_CSS_NAME_RE = re.compile(r"^[A-Za-z0-9_-]+$")


def _fail(message: str) -> "InteropError":
    return InteropError(message)


@functools.lru_cache(maxsize=1)
def load_schema() -> dict:
    """Load the structural DTCG schema from the repository (never from the network)."""
    schema = _load_schema(SCHEMA_PATH)
    if not str(schema.get("$id", "")).endswith("interop-dtcg-document.schema.json"):
        raise InteropError(f"unexpected $id in DTCG structural schema: {schema.get('$id')!r}")
    return schema


def _schema_errors(document) -> list[str]:
    return schema_errors(load_schema(), document)


# --------------------------------------------------------------------------- #
# value helpers
# --------------------------------------------------------------------------- #

def _number(value, where: str):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise _fail(f"{where} must be a number, got {type(value).__name__}")
    return value


def _text(value, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{where} must be a nonempty string")
    return value


def _alias_target(value):
    """Return the referenced token path when *value* is a bare ``{a.b}`` alias."""
    if isinstance(value, str):
        match = _ALIAS_RE.match(value)
        if match:
            return match.group("target").strip()
    return None


def _check_members(value, where, required, optional, checkers):
    if not isinstance(value, dict):
        raise _fail(f"{where} must be an object")
    extra = sorted(set(value) - set(required) - set(optional))
    if extra:
        raise _fail(f"{where} has unsupported member(s): {', '.join(extra)}")
    for member in required:
        if member not in value:
            raise _fail(f"{where} is missing required member {member!r}")
    for member, checker in checkers.items():
        if member in value:
            checker(value[member], f"{where}.{member}")


def _check_color(value, where):
    if isinstance(value, str):
        _text(value, where)
        if ";" in value or "{" in value or "}" in value:
            raise _fail(f"{where} is not a CSS color string: {value!r}")
        if not (_HEX_COLOR_RE.match(value) or _COLOR_FUNCTION_RE.match(value)
                or _COLOR_KEYWORD_RE.match(value)):
            raise _fail(f"{where} is not a CSS color string: {value!r}")
        return
    if not isinstance(value, dict):
        raise _fail(f"{where} must be a CSS color string or a DTCG color object")
    space = value.get("colorSpace")
    if space not in _COLOR_SPACES:
        raise _fail(f"{where}.colorSpace must be one of {', '.join(_COLOR_SPACES)}; got {space!r}")
    extra = sorted(set(value) - {"colorSpace", "components", "alpha", "hex"})
    if extra:
        raise _fail(f"{where} color object has unsupported member(s): {', '.join(extra)}")
    components = value.get("components")
    if not isinstance(components, list) or len(components) not in (3, 4):
        raise _fail(f"{where}.components must be an array of three or four numbers")
    for index, component in enumerate(components):
        if component == "none":
            continue
        _number(component, f"{where}.components[{index}]")
    if "alpha" in value:
        alpha = _number(value["alpha"], f"{where}.alpha")
        if not 0 <= alpha <= 1:
            raise _fail(f"{where}.alpha must be within 0..1")
    if "hex" in value and not _HEX_COLOR_RE.match(str(value["hex"])):
        raise _fail(f"{where}.hex must be a hex color such as #RRGGBB")


def _check_dimension(value, where):
    if isinstance(value, str):
        if not _DIMENSION_RE.match(value):
            raise _fail(f"{where} is not a dimension string such as '16px' or '1rem': {value!r}")
        return
    _check_members(
        value, where, ("value", "unit"), (),
        {"value": lambda v, w: _number(v, w),
         "unit": lambda v, w: _unit(v, w, ("px", "rem"))},
    )


def _unit(value, where, allowed):
    if value not in allowed:
        raise _fail(f"{where} must be one of {', '.join(allowed)}; got {value!r}")


def _check_duration(value, where):
    if isinstance(value, str):
        if not _DURATION_RE.match(value):
            raise _fail(f"{where} is not a duration string such as '200ms' or '1.5s': {value!r}")
        return
    _check_members(
        value, where, ("value", "unit"), (),
        {"value": lambda v, w: _number(v, w),
         "unit": lambda v, w: _unit(v, w, _DURATION_UNITS)},
    )


def _check_number(value, where):
    _number(value, where)


def _check_font_family(value, where):
    if isinstance(value, str):
        _text(value, where)
        return
    if isinstance(value, list) and value:
        for index, item in enumerate(value):
            _text(item, f"{where}[{index}]")
        return
    raise _fail(f"{where} must be a font family string or a nonempty array of strings")


def _check_font_weight(value, where):
    if isinstance(value, str):
        if value not in _FONT_WEIGHT_KEYWORDS:
            raise _fail(f"{where} must be a font weight keyword; got {value!r}")
        return
    weight = _number(value, where)
    if not 1 <= weight <= 1000:
        raise _fail(f"{where} must be a numeric weight within 1..1000")


def _check_cubic_bezier(value, where):
    if not isinstance(value, list) or len(value) != 4:
        raise _fail(f"{where} must be an array of four numbers")
    for index, item in enumerate(value):
        _number(item, f"{where}[{index}]")


def _check_stroke_style(value, where):
    if isinstance(value, str):
        if value not in _STROKE_STYLE_KEYWORDS:
            raise _fail(
                f"{where} must be a stroke style keyword ({', '.join(_STROKE_STYLE_KEYWORDS)}) "
                "or a dash-array object"
            )
        return
    if not isinstance(value, dict):
        raise _fail(f"{where} must be a stroke style keyword or a dash-array object")
    extra = sorted(set(value) - {"dashArray", "lineCap"})
    if extra:
        raise _fail(f"{where} stroke style object has unsupported member(s): {', '.join(extra)}")
    dash = value.get("dashArray")
    if not isinstance(dash, list) or not dash:
        raise _fail(f"{where}.dashArray must be a nonempty array of dimensions")
    for index, item in enumerate(dash):
        _check_dimension(item, f"{where}.dashArray[{index}]")
    if "lineCap" in value and value["lineCap"] not in _LINE_CAPS:
        raise _fail(f"{where}.lineCap must be one of {', '.join(_LINE_CAPS)}")


def _check_typography(value, where):
    # DTCG 2025.10 requires all five members of the typography composite. There is
    # no canonical relaxation: a legacy document that omits letterSpacing goes
    # through from_legacy_document first.
    _check_members(
        value, where, TYPOGRAPHY_MEMBERS, (),
        {"fontFamily": _check_font_family,
         "fontSize": _check_dimension,
         "fontWeight": _check_font_weight,
         "letterSpacing": _check_dimension,
         "lineHeight": lambda v, w: _number(v, w)},
    )


def _check_shadow_item(value, where):
    _check_members(
        value, where, ("color", "offsetX", "offsetY", "blur", "spread"), (),
        {"color": _check_color,
         "offsetX": _check_dimension,
         "offsetY": _check_dimension,
         "blur": _check_dimension,
         "spread": _check_dimension},
    )


def _check_shadow(value, where):
    if isinstance(value, list):
        if not value:
            raise _fail(f"{where} must not be an empty shadow array")
        for index, item in enumerate(value):
            _check_shadow_item(item, f"{where}[{index}]")
        return
    _check_shadow_item(value, where)


def _check_border(value, where):
    _check_members(
        value, where, ("color", "width", "style"), (),
        {"color": _check_color, "width": _check_dimension, "style": _check_stroke_style},
    )


def _check_transition(value, where):
    _check_members(
        value, where, ("duration", "delay", "timingFunction"), (),
        {"duration": _check_duration, "delay": _check_duration,
         "timingFunction": _check_cubic_bezier},
    )


def _check_gradient(value, where):
    if not isinstance(value, list) or len(value) < 2:
        raise _fail(f"{where} must be an array of at least two gradient stops")
    for index, stop in enumerate(value):
        stop_where = f"{where}[{index}]"
        _check_members(
            stop, stop_where, ("color", "position"), (),
            {"color": _check_color,
             "position": lambda v, w: _bounded_position(v, w)},
        )


def _bounded_position(value, where):
    position = _number(value, where)
    if not 0 <= position <= 1:
        raise _fail(f"{where} must be within 0..1")


_VALUE_CHECKERS = {
    "color": _check_color,
    "dimension": _check_dimension,
    "duration": _check_duration,
    "fontFamily": _check_font_family,
    "fontWeight": _check_font_weight,
    "number": _check_number,
    "cubicBezier": _check_cubic_bezier,
    "strokeStyle": _check_stroke_style,
    "typography": _check_typography,
    "shadow": _check_shadow,
    "border": _check_border,
    "transition": _check_transition,
    "gradient": _check_gradient,
}


def _check_legacy(value, type_name, where):
    """Only the legacy adapter calls this: canonical documents never carry these types."""
    if type_name == "string":
        # The legacy converter emits plain strings, including the empty theme id.
        if not isinstance(value, str):
            raise _fail(f"{where} must be a string")
        return
    if not isinstance(value, bool):
        raise _fail(f"{where} must be a boolean")


# --------------------------------------------------------------------------- #
# collection, resolution, validation
# --------------------------------------------------------------------------- #

def _join(path, name):
    return f"{path}.{name}" if path else name


def _collect(document):
    """Walk a canonical DTCG document into token records, group metadata and order."""
    if not isinstance(document, dict) or not document:
        raise InteropError("DTCG document must be a nonempty JSON object")

    tokens: dict[str, dict] = {}
    groups: dict[str, dict] = {}
    order: list[str] = []

    def add_token(key_path, node, inherited_type, *, is_root, group_path):
        if key_path in tokens:
            raise InteropError(
                f"DTCG path collision at {key_path!r}: a $root token and a token of the "
                "same name would flatten onto one path"
            )
        if not isinstance(node, dict):
            raise InteropError(f"DTCG token {key_path!r} must be an object")
        if "$value" not in node:
            raise InteropError(f"DTCG token {key_path!r} has no $value")
        explicit = "$type" in node
        effective = node["$type"] if explicit else inherited_type
        record = {
            "path": key_path,
            "group": group_path,
            "name": "$root" if is_root else key_path.rsplit(".", 1)[-1],
            "is_root": is_root,
            "raw": node["$value"],
            "type": effective,
            "type_source": "explicit" if explicit else "inherited",
            "declared_at": key_path if explicit else None,
        }
        for extra in ("$description", "$extensions", "$deprecated"):
            if extra in node:
                record[extra] = node[extra]
        unknown = sorted(set(node) - {"$value", "$type", "$description", "$extensions", "$deprecated"})
        if unknown:
            raise InteropError(
                f"DTCG token {key_path!r} has unsupported member(s): {', '.join(unknown)}"
            )
        if not isinstance(record.get("$description", ""), str):
            raise InteropError(f"DTCG token {key_path!r} $description must be a string")
        if not isinstance(record.get("$extensions", {}), dict):
            raise InteropError(f"DTCG token {key_path!r} $extensions must be an object")
        if "$deprecated" in record and not isinstance(record["$deprecated"], bool):
            raise InteropError(f"DTCG token {key_path!r} $deprecated must be a boolean")
        tokens[key_path] = record
        order.append(key_path)

    def visit_group(node, path, inherited_type):
        inherited = node.get("$type", inherited_type)
        if path:
            groups[path] = {key: node[key] for key in _RESERVED_GROUP_KEYS if key in node}
        for key, child in node.items():
            if key == "$root":
                if not path:
                    raise InteropError(
                        "the DTCG document root is a group; a top-level $root token has no "
                        "flattened path and is not supported"
                    )
                add_token(path, child, inherited, is_root=True, group_path=path.rsplit(".", 1)[0] if "." in path else "")
                continue
            if key.startswith("$"):
                continue
            child_path = _join(path, key)
            if not isinstance(child, dict):
                raise InteropError(
                    f"DTCG group member {child_path!r} must be an object (a token needs $value, "
                    "a nested group is an object)"
                )
            if "$value" in child:
                group_path = path
                add_token(child_path, child, inherited, is_root=False, group_path=group_path)
            else:
                visit_group(child, child_path, inherited)

    for key in document:
        if key.startswith("$") and key not in _RESERVED_DOCUMENT_KEYS:
            raise InteropError(f"DTCG document has unsupported reserved member {key!r}")
    root_meta = {key: document[key] for key in _RESERVED_DOCUMENT_KEYS if key in document}
    for key in ("$description", "$extensions"):
        if key in root_meta and not isinstance(root_meta[key], (str, dict)):
            raise InteropError(f"DTCG document {key} has an unsupported value type")
    if "$extensions" in root_meta and not isinstance(root_meta["$extensions"], dict):
        raise InteropError("DTCG document $extensions must be an object")
    visit_group(document, "", root_meta.get("$type"))

    if not tokens:
        raise InteropError("DTCG document declares no tokens")

    for key, record in tokens.items():
        name = record["type"]
        where = f"DTCG token {key!r}"
        if name is None:
            raise _fail(
                f"{where} has no $type and no ancestor group declares one; DTCG requires a "
                "resolvable $type"
            )
        if name in LEGACY_TYPES:
            raise _fail(
                f"{where} uses the pre-2025.10 type {name!r}, which is not a DTCG {SCHEMA_VERSION} "
                "type and is not accepted by the canonical contract. Convert the document first "
                "with dtcg.from_legacy_document (the legacy adapter), or use "
                "dtcg.validate_legacy_document, which adapts and then validates strictly"
            )
        if name not in TOKEN_TYPES:
            raise _fail(
                f"{where} uses unknown $type {name!r}; DTCG {SCHEMA_VERSION} types are: "
                f"{', '.join(TOKEN_TYPES)}"
            )
    return tokens, groups, order, root_meta


def _resolve_deep(value, tokens, stack, chain, owner):
    target = _alias_target(value)
    if target is not None:
        if target not in tokens:
            raise InteropError(
                f"DTCG alias {{{target}}} used at {owner!r} does not resolve: the document "
                "declares no token at that path"
            )
        if target in stack:
            raise InteropError("DTCG alias cycle: " + " -> ".join([*stack, target]))
        chain.append(target)
        return _resolve_deep(tokens[target]["raw"], tokens, [*stack, target], chain, target)
    if isinstance(value, dict):
        return {key: _resolve_deep(item, tokens, stack, chain, owner) for key, item in value.items()}
    if isinstance(value, list):
        return [_resolve_deep(item, tokens, stack, chain, owner) for item in value]
    return value


def _resolve(tokens):
    """Resolve every token; return (resolved values, alias chains)."""
    values: dict[str, object] = {}
    chains: dict[str, list[str]] = {}
    for path in tokens:
        chain: list[str] = []
        values[path] = _resolve_deep(tokens[path]["raw"], tokens, [path], chain, path)
        chains[path] = chain
    return values, chains


def _check_resolved(tokens, values):
    for path, record in tokens.items():
        where = f"DTCG token {path!r} (type {record['type']!r})"
        _VALUE_CHECKERS[record["type"]](values[path], where)


def validate_document(document) -> dict:
    """Validate a **canonical** DTCG 2025.10 token document; return a structural report.

    Structural rules come from ``interop-dtcg-document.schema.json``; semantic
    rules ($type inheritance, alias resolution, cycle rejection, composite member
    completeness -- all five ``typography`` members included -- and per-type value
    shape) are enforced here. Raises :class:`InteropError` on the first class of
    failure and never repairs input.

    There is no permissive flag: a pre-2025.10 document (``string``/``boolean``
    types, ``typography`` without ``letterSpacing``) is rejected. Convert it with
    :func:`from_legacy_document` first, or call :func:`validate_legacy_document`.
    """
    problems = _schema_errors(document)
    if problems:
        raise InteropError(
            f"DTCG document violates {SCHEMA_PATH.name}: " + "; ".join(problems[:10])
        )
    tokens, _groups, _order, root_meta = _collect(document)
    values, chains = _resolve(tokens)
    _check_resolved(tokens, values)
    type_counts: dict[str, int] = {}
    for record in tokens.values():
        type_counts[record["type"]] = type_counts.get(record["type"], 0) + 1
    return {
        "schemaVersion": SCHEMA_VERSION,
        "schema_path": SCHEMA_REPOSITORY_PATH,
        "canonical": True,
        "token_count": len(tokens),
        "group_count": len(_groups),
        "types": {name: type_counts[name] for name in sorted(type_counts)},
        "alias_tokens": sum(1 for chain in chains.values() if chain),
        "root_tokens": sorted(path for path, record in tokens.items() if record["is_root"]),
        "document_keys": sorted(root_meta),
        "typography_letterSpacing": "required",
        "typography_members": list(TYPOGRAPHY_MEMBERS),
        "legacy_adapter": "from_legacy_document",
    }


# --------------------------------------------------------------------------- #
# flatten / to_document / roundtrip
# --------------------------------------------------------------------------- #

def flatten(document) -> dict:
    """Flatten a canonical DTCG document into ``{"path.to.token": record}``.

    Each record carries ``$type`` (effective, after inheritance), ``$value``
    (aliases resolved), ``alias_chain`` (alias targets traversed, in encounter
    order; ``[]`` when the token is not an alias), ``$raw`` (the value exactly as
    written, so ``to_document`` can restore alias references), ``type_source``,
    ``is_root`` and the optional ``$description``/``$extensions``/``$deprecated``.
    ``$root`` tokens flatten onto their group's own path.

    Group-level structure needed for a lossless round trip is carried by the
    reserved ``$meta`` key. Every key whose name starts with ``$`` is reserved by
    the DTCG format, so ``$meta`` cannot collide with a token path.
    """
    report = validate_document(document)
    tokens, groups, order, root_meta = _collect(document)
    values, chains = _resolve(tokens)

    flat: dict[str, dict] = {}
    for path in order:
        record = {
            "$type": tokens[path]["type"],
            "$value": values[path],
            "alias_chain": list(chains[path]),
            "$raw": tokens[path]["raw"],
            "type_source": tokens[path]["type_source"],
            "is_root": tokens[path]["is_root"],
        }
        for extra in ("$description", "$extensions", "$deprecated"):
            if extra in tokens[path]:
                record[extra] = tokens[path][extra]
        flat[path] = record
    flat["$meta"] = {
        "schemaVersion": SCHEMA_VERSION,
        "document": root_meta,
        "groups": {path: dict(meta) for path, meta in groups.items()},
        "order": list(order),
        "report": report,
    }
    return flat


def to_document(flat) -> dict:
    """Rebuild a DTCG document from a flattened token map.

    Inverse of :func:`flatten`. ``$raw`` is preferred over ``$value`` so alias
    references survive. Group metadata is restored from ``$meta`` when present;
    without it, groups are invented from the dotted paths and every token gets an
    explicit ``$type`` (a valid but not byte-identical document). No validation is
    performed here -- call :func:`validate_document` on the result if needed.
    """
    if not isinstance(flat, dict) or not flat:
        raise InteropError("flattened DTCG token map must be a nonempty object")
    meta = flat.get("$meta")
    if meta is not None and not isinstance(meta, dict):
        raise InteropError("flattened DTCG token map $meta must be an object")
    token_items = {key: value for key, value in flat.items() if not key.startswith("$")}
    if not token_items:
        raise InteropError("flattened DTCG token map declares no tokens")

    document: dict = {}
    if meta:
        document.update(meta.get("document") or {})

    def ensure_group(group_path: str) -> dict:
        if not group_path:
            return document
        node = document
        walked = ""
        for part in group_path.split("."):
            if not part:
                raise InteropError(f"invalid group path {group_path!r} in flattened map")
            walked = _join(walked, part)
            existing = node.get(part)
            if existing is None:
                if walked in token_items and not token_items[walked].get("is_root"):
                    raise InteropError(
                        f"flattened map declares both a token {walked!r} and child tokens below it"
                    )
                existing = {}
                node[part] = existing
            elif not isinstance(existing, dict) or "$value" in existing:
                raise InteropError(
                    f"flattened map needs group {walked!r} but the map declares a token there"
                )
            node = existing
        return node

    if meta:
        for group_path in (meta.get("groups") or {}):
            if group_path:
                ensure_group(group_path)
        for group_path, group_meta in (meta.get("groups") or {}).items():
            if not isinstance(group_meta, dict):
                raise InteropError(f"group metadata for {group_path!r} must be an object")
            target = ensure_group(group_path)
            for key, value in group_meta.items():
                if key not in _RESERVED_GROUP_KEYS:
                    raise InteropError(f"group metadata for {group_path!r} has unsupported key {key!r}")
                target[key] = value

    ordered = list(token_items)
    if meta and isinstance(meta.get("order"), list):
        declared = [path for path in meta["order"] if path in token_items]
        leftover = [path for path in ordered if path not in declared]
        ordered = declared + leftover
    for path in ordered:
        record = token_items[path]
        if not isinstance(record, dict):
            raise InteropError(f"flattened token {path!r} must be an object")
        if "$type" not in record:
            raise InteropError(f"flattened token {path!r} has no $type")
        if record.get("is_root"):
            # A $root token flattens onto its own group's path.
            group_path, entry = path, "$root"
        else:
            group_path, _, entry = path.rpartition(".")
            if not entry:
                raise InteropError(f"flattened token path {path!r} has no token name")
        group = ensure_group(group_path)
        token: dict = {}
        inherited = record.get("type_source") == "inherited"
        if inherited and not meta:
            raise InteropError(
                f"flattened token {path!r} declares an inherited $type but the map carries no "
                "$meta group metadata to inherit it from"
            )
        if not inherited:
            token["$type"] = record["$type"]
        raw = record.get("$raw", record.get("$value"))
        if raw is None and "$value" not in record:
            raise InteropError(f"flattened token {path!r} has neither $raw nor $value")
        token["$value"] = raw
        for extra in ("$description", "$extensions", "$deprecated"):
            if extra in record:
                token[extra] = record[extra]
        if entry in group:
            raise InteropError(f"flattened map places two tokens at {path!r}")
        group[entry] = token
    if not document:
        raise InteropError("flattened map produced an empty DTCG document")
    return document


def roundtrip(document) -> dict:
    """``to_document(flatten(document))`` -- lossless for canonical documents.

    Lossless means deep equality against the input for: nested groups, ``$type``
    inheritance (including a group ``$type`` that every descendant overrides),
    ``$root`` tokens, alias references, ``$description``/``$extensions``/
    ``$deprecated`` and every DTCG 2025.10 token type. Comments, key order inside
    JSON objects and duplicate keys are outside the guarantee.

    The input must be canonical; a legacy document goes through
    :func:`from_legacy_document` first (the round trip then guarantees losslessness
    for the *adapted* document).
    """
    validate_document(document)
    return to_document(flatten(document))


# --------------------------------------------------------------------------- #
# legacy adapter: pre-2025.10 documents -> canonical documents
# --------------------------------------------------------------------------- #

def _scan_unvalidated(document):
    """Walk a document without validating token types.

    Returns ``(tokens, groups)``. ``tokens`` maps a flattened path to
    ``{"node", "parent", "name", "group", "type", "explicit"}``, where ``type`` is
    the effective type after ``$type`` inheritance. Unlike :func:`_collect` this
    never rejects a type, so the legacy adapter can see ``string``/``boolean``
    tokens. Nothing is copied: ``node`` and ``parent`` are the live objects of
    *document*, which lets the adapter rewrite the tree in place.
    """
    if not isinstance(document, dict) or not document:
        raise InteropError("legacy DTCG document must be a nonempty JSON object")
    tokens: dict[str, dict] = {}
    groups: dict[str, dict] = {}

    def add(path, node, parent, name, inherited, group):
        explicit = "$type" in node
        tokens[path] = {
            "node": node,
            "parent": parent,
            "name": name,
            "group": group,
            "type": node["$type"] if explicit else inherited,
            "explicit": explicit,
        }

    def visit_group(node, path, inherited_type):
        inherited = node.get("$type", inherited_type)
        if path:
            groups[path] = node
        for key, child in node.items():
            if key == "$root":
                if not path:
                    continue
                if not isinstance(child, dict):
                    raise InteropError(f"legacy DTCG group member {path!r} $root must be an object")
                add(path, child, node, "$root", inherited, path)
                continue
            if key.startswith("$"):
                continue
            child_path = _join(path, key)
            if not isinstance(child, dict):
                raise InteropError(
                    f"legacy DTCG group member {child_path!r} must be an object (a token needs "
                    "$value, a nested group is an object)"
                )
            if "$value" in child:
                add(child_path, child, node, key, inherited, path)
            else:
                visit_group(child, child_path, inherited)

    visit_group(document, "", document.get("$type"))
    return tokens, groups


def _adapt_legacy_document(document, *, letter_spacing=LEGACY_LETTER_SPACING):
    """Adapt a pre-2025.10 document in place on a deep copy; return it with a record."""
    if not isinstance(letter_spacing, str) or not letter_spacing.strip():
        raise _fail("the adapter's synthesized letterSpacing must be a nonempty dimension string")
    try:
        adapted = json.loads(json.dumps(document))
    except (TypeError, ValueError) as exc:
        raise InteropError(f"legacy DTCG document must be JSON-serializable: {exc}") from exc
    tokens, _groups = _scan_unvalidated(adapted)

    unmapped: dict[str, dict] = {}
    legacy_types: set[str] = set()
    for path in list(tokens):
        entry = tokens[path]
        type_name = entry["type"]
        if type_name not in LEGACY_TYPES:
            continue
        node = entry["node"]
        _check_legacy(node["$value"], type_name, f"legacy DTCG token {path!r}")
        record = {"$type": type_name, "$value": node["$value"]}
        for extra in ("$description", "$extensions", "$deprecated"):
            if extra in node:
                record[extra] = node[extra]
        record["reason"] = (
            f"pre-2025.10 type {type_name!r} has no canonical DTCG {SCHEMA_VERSION} equivalent; "
            "the adapter preserves the token verbatim instead of coercing it into a type it is not"
        )
        unmapped[path] = record
        legacy_types.add(type_name)
        del entry["parent"][entry["name"]]

    tokens, _groups = _scan_unvalidated(adapted)
    synthesized: dict[str, list[str]] = {}
    for path, entry in tokens.items():
        if entry["type"] != "typography":
            continue
        node = entry["node"]
        value = node["$value"]
        if not isinstance(value, dict) or "letterSpacing" in value:
            continue
        if _alias_target(value) is not None:
            # An aliased typography value is adapted at the token it points to.
            continue
        value["letterSpacing"] = letter_spacing
        extensions = node.setdefault("$extensions", {})
        if not isinstance(extensions, dict):
            raise _fail(f"legacy DTCG token {path!r} $extensions must be an object")
        extensions[LEGACY_ADAPTER_NAMESPACE] = {
            "synthesized_members": ["letterSpacing"],
            "value": letter_spacing,
            "reason": (
                f"DTCG {SCHEMA_VERSION} requires letterSpacing on typography; the legacy document "
                "omitted it and the adapter wrote CSS 'normal' tracking as an explicit dimension"
            ),
        }
        synthesized[path] = ["letterSpacing"]

    summary = {
        "legacy_types": sorted(legacy_types),
        "unmapped_tokens": unmapped,
        "synthesized_members": synthesized,
    }
    if unmapped or synthesized:
        extensions = adapted.setdefault("$extensions", {})
        if not isinstance(extensions, dict):
            raise _fail("legacy DTCG document $extensions must be an object")
        extensions[LEGACY_ADAPTER_NAMESPACE] = summary
    return adapted, summary


def from_legacy_document(document, *, letter_spacing=LEGACY_LETTER_SPACING) -> dict:
    """The legacy adapter: convert a pre-2025.10 document into canonical form.

    Adapter, not a relaxation -- the canonical contract is unchanged and the
    canonical schema file is untouched. Two conversions happen, both recorded in
    the result's ``$extensions`` under :data:`LEGACY_ADAPTER_NAMESPACE`:

    * every ``string``/``boolean`` token (effective type, so inherited types count)
      is removed from the token tree and preserved verbatim in the document
      ``$extensions`` summary under ``unmapped_tokens``. A pre-2025.10 scalar has no
      canonical DTCG 2025.10 type, and inventing one would be a false claim.
    * a ``typography`` value that omits ``letterSpacing`` gets an explicit
      ``"0px"`` (CSS ``normal`` tracking, the value the omission means) and the
      token carries a ``$extensions`` marker naming the synthesized member.

    A canonical document is returned unchanged (deep copy), so this is safe to call
    unconditionally. The input is never mutated. The result is canonical: it is
    accepted by :func:`validate_document`.
    """
    adapted, _summary = _adapt_legacy_document(document, letter_spacing=letter_spacing)
    return adapted


def validate_legacy_document(document, *, letter_spacing=LEGACY_LETTER_SPACING) -> dict:
    """Adapter entry point: adapt a legacy document, then validate it strictly.

    Returns the canonical report from :func:`validate_document` extended with the
    adapter's record: ``canonical_source``, ``legacy_types``,
    ``unmapped_legacy_tokens`` and ``synthesized_members``. The strictness of
    :func:`validate_document` is not weakened -- this function adapts first and then
    applies exactly the same canonical validation.
    """
    adapted, summary = _adapt_legacy_document(document, letter_spacing=letter_spacing)
    report = validate_document(adapted)
    report["canonical_source"] = "legacy-adapter"
    report["legacy_types"] = summary["legacy_types"]
    report["unmapped_legacy_tokens"] = sorted(summary["unmapped_tokens"])
    report["synthesized_members"] = {
        path: list(members) for path, members in sorted(summary["synthesized_members"].items())
    }
    return report


# --------------------------------------------------------------------------- #
# CSS projection
# --------------------------------------------------------------------------- #

def _css_name(prefix: str, path: str) -> str:
    if not prefix or not prefix.startswith("--"):
        raise InteropError(f"CSS variable prefix must start with '--'; got {prefix!r}")
    raw = f"{prefix}-{path.replace('.', '-')}"
    name = re.sub(r"[^A-Za-z0-9_-]", "-", raw)
    if not _CSS_NAME_RE.fullmatch(name) or name == "--":
        raise InteropError(f"token path {path!r} does not project to a valid CSS variable name")
    return name


def _number_text(value) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InteropError(f"expected a number for a CSS projection, got {type(value).__name__}")
    if isinstance(value, int):
        return str(value)
    text = f"{value:.10f}".rstrip("0").rstrip(".")
    if text in ("", "-0", "-"):
        return "0"
    return text


def _css_quoted_family(name: str) -> str:
    if re.fullmatch(r"[A-Za-z][A-Za-z0-9-]*", name):
        return name
    return '"%s"' % name.replace('"', "")


def _css_color(value) -> str:
    if isinstance(value, str):
        return value
    if "hex" in value:
        return str(value["hex"])
    space = "xyz" if value["colorSpace"] == "xyz-d65" else value["colorSpace"]
    components = " ".join(component if component == "none" else _number_text(component)
                          for component in value["components"])
    alpha = f" / {_number_text(value['alpha'])}" if "alpha" in value else ""
    return f"color({space} {components}{alpha})"


def _css_projection(record):
    """Return the CSS value for one flattened token, or None with a reason."""
    type_name = record["$type"]
    value = record["$value"]
    if type_name == "color":
        return _css_color(value), None
    if type_name == "dimension":
        if isinstance(value, str):
            return value, None
        return f"{_number_text(value['value'])}{value['unit']}", None
    if type_name == "duration":
        if isinstance(value, str):
            return value, None
        return f"{_number_text(value['value'])}{value['unit']}", None
    if type_name == "number":
        return _number_text(value), None
    if type_name == "fontWeight":
        return _number_text(value) if not isinstance(value, str) else value, None
    if type_name == "fontFamily":
        if isinstance(value, str):
            return _css_quoted_family(value), None
        return ", ".join(_css_quoted_family(item) for item in value), None
    if type_name == "cubicBezier":
        return "cubic-bezier(%s)" % ", ".join(_number_text(item) for item in value), None
    if type_name == "strokeStyle" and isinstance(value, str):
        return value, None
    return None, (
        f"type {type_name!r} has no single CSS custom-property representation; "
        "read the DTCG document instead"
    )


def to_css_variables(document, *, prefix: str = "--dl") -> dict:
    """Project a DTCG document onto CSS custom properties (a projection only).

    Returns ``{"projection", "source_of_truth": False, "note", "prefix",
    "variables": {name: value}, "omitted": {token_path: reason}}``. The DTCG
    document stays the source of truth: composite types that have no single CSS
    value (``typography``, ``shadow``, ``border``, ``transition``, ``gradient``
    and the object form of ``strokeStyle``) are listed in ``omitted`` rather than
    being flattened into a made-up string. The result is deterministic: tokens are
    visited in sorted path order and a name collision after sanitising fails
    closed. The input must be a canonical document (see :func:`from_legacy_document`).
    """
    flat = flatten(document)
    variables: dict[str, str] = {}
    omitted: dict[str, str] = {}
    seen: dict[str, str] = {}
    for path in sorted(key for key in flat if not key.startswith("$")):
        record = flat[path]
        value, reason = _css_projection(record)
        name = _css_name(prefix, path)
        if reason is not None:
            omitted[path] = reason
            continue
        if name in seen:
            raise InteropError(
                f"token paths {seen[name]!r} and {path!r} both project to CSS variable {name!r}"
            )
        seen[name] = path
        variables[name] = value
    return {
        "projection": "css-custom-properties",
        "source_of_truth": False,
        "note": ("CSS custom properties are a projection of the DTCG document; the DTCG "
                 "document is the source of truth and this map is not round-trippable."),
        "prefix": prefix,
        "schemaVersion": SCHEMA_VERSION,
        "variables": variables,
        "omitted": omitted,
    }
