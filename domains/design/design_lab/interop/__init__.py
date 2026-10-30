# SPDX-License-Identifier: MIT
"""DESIGN-LAB interop contracts (DL-P0-110, DL-P1-130, DL-P0-160, DL-P0-161, DL-P1-111).

This package adopts external interchange formats instead of inventing local ones:

* ``dtcg`` -- DTCG design tokens (Design Tokens Community Group, ``2025.10`` stable).
  The canonical contract is strict (``typography`` requires all five members, and
  the pre-2025.10 ``string``/``boolean`` types are rejected); legacy documents go
  through the explicitly named adapter ``from_legacy_document`` /
  ``validate_legacy_document``, which never widens the canonical schema.
* ``timeline`` -- OpenTimelineIO ``Timeline.1`` documents as the handoff contract
  to a video host (DESIGN-LAB does not render video). ``overlaps()`` is derived
  from the official ``Transition.1`` covered-range formula.
* ``provenance`` -- delivery provenance projected onto a C2PA 2.4 claim structure
  (``c2pa.claim.v2`` / ``c2pa.signature``), unsigned and never signed. The
  DESIGN-LAB Asset Graph stays the source of truth for that projection.
* ``delivery_receipt`` -- the deterministic DeliveryReceipt V2 for a delivery.
* ``penpot`` -- the Penpot adapter declaration, its file boundary, a structural
  ``.penpot`` archive validator and a read-only import plan.

Boundary of the whole package: every module here is a contract layer. It reads
and writes JSON documents that belong to an external standard, validates them
structurally (JSON Schema, draft 2020-12) and semantically (Python rules), and
fails closed whenever a live host interaction would be required. No module
imports a design application, opens a socket, starts a process, signs an asset,
reads a user library or writes to disk -- callers own all I/O. Everything this
package can produce is E1 (STRUCTURAL) evidence: schemas, static validation and
unit tests. It never claims an E2+ host/runtime result and never claims that a
signed asset exists.
"""
from __future__ import annotations

import functools
import json
from pathlib import Path

DRAFT_2020_12 = "https://json-schema.org/draft/2020-12/schema"


class InteropError(RuntimeError):
    """Interop contract violation: document, binding or claim is not valid.

    Raised with a precise message naming the offending path, field or the exact
    external resource that would be required to continue.
    """


@functools.lru_cache(maxsize=None)
def load_schema(path) -> dict:
    """Load a draft 2020-12 JSON Schema from this checkout, offline.

    A schema is read from the repository only; it is never fetched from its
    ``$id`` URL. Missing, unreadable, malformed or non-2020-12 schemas fail
    closed with the absolute path in the message.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise InteropError(f"JSON Schema is missing or unreadable: {path} ({exc})") from exc
    try:
        schema = json.loads(text)
    except json.JSONDecodeError as exc:
        raise InteropError(f"JSON Schema is not valid JSON: {path} ({exc})") from exc
    if not isinstance(schema, dict) or schema.get("$schema") != DRAFT_2020_12:
        raise InteropError(f"JSON Schema is not draft 2020-12: {path}")
    return schema


def _jsonschema():
    try:
        import jsonschema
    except ImportError as exc:  # pragma: no cover - environment guard
        raise InteropError(
            "structural validation requires the 'jsonschema' package in the active "
            "interpreter; it is not importable"
        ) from exc
    return jsonschema


@functools.lru_cache(maxsize=None)
def _validator(schema_json: str):
    return _jsonschema().Draft202012Validator(json.loads(schema_json))


def schema_errors(schema, document, *, registry=None, limit: int = 10) -> list[str]:
    """Return human-readable draft 2020-12 validation errors, deterministically ordered.

    ``registry`` is an optional ``referencing`` registry used to resolve ``$ref``
    targets that live in another in-repo schema; without it such a reference fails
    closed instead of reaching the network.
    """
    jsonschema = _jsonschema()
    try:
        if registry is None:
            validator = _validator(json.dumps(schema, sort_keys=True))
        else:
            validator = jsonschema.Draft202012Validator(schema, registry=registry)
    except Exception as exc:  # unresolvable $ref, invalid keyword, ...
        raise InteropError(f"JSON Schema cannot be prepared for validation: {exc}") from exc
    try:
        errors = sorted(
            validator.iter_errors(document),
            key=lambda error: [str(part) for part in error.absolute_path],
        )
    except Exception as exc:
        raise InteropError(f"JSON Schema validation could not run: {exc}") from exc
    return [
        f"{'/'.join(str(part) for part in error.absolute_path) or '<document>'}: {error.message}"
        for error in errors[:limit]
    ]


def resource_registry(pairs: dict):
    """Build an offline ``referencing`` registry from ``{uri: schema}`` pairs."""
    try:
        from referencing import Registry, Resource
    except ImportError as exc:  # pragma: no cover - environment guard
        raise InteropError(
            "resolving an in-repo $ref requires the 'referencing' package that ships with "
            "jsonschema; it is not importable"
        ) from exc
    registry = Registry()
    for uri, schema in pairs.items():
        registry = registry.with_resource(uri, Resource.from_contents(schema))
    return registry


__all__ = [
    "DRAFT_2020_12",
    "InteropError",
    "load_schema",
    "resource_registry",
    "schema_errors",
]
