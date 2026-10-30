# SPDX-License-Identifier: MIT
"""DL-P1-150: Blender host adapter contract plus a real GLB/glTF validator.

The adapter declaration is structural: Blender is not installed on this machine
and this module never launches it, never renders, never exports and never reads
a ``.blend`` file. ``blender_handoff`` describes what a future live adapter
would do and ends with ``requires a live Blender run: NOT_EXECUTED``.

The validators are real: :func:`validate_glb` walks the binary glTF container
byte by byte (header, chunk table, alignment, bounds, trailing bytes), parses
the JSON chunk and checks glTF 2.0 reference integrity; :func:`validate_gltf_json`
applies the same reference rules to the JSON variant without a BIN chunk. Only
the standard library is used - no glTF third-party library is imported - and no
file is opened: the caller supplies bytes.

Offset convention for errors: container violations carry the absolute byte
offset in ``data`` at which the violation was detected. Document-level
violations carry the byte offset of the JSON chunk payload (its first byte),
which is the exact byte where the offending document begins; ``.gltf``
documents have no container, so their offset is ``0`` (document start). Range
violations that overrun a BIN chunk carry the byte offset at which the overrun
would begin.

Where the raw bytes live: :func:`parse_glb` is the only public function of this
module that returns raw chunk payloads. :func:`validate_glb`,
:func:`summarize_glb`, :func:`diagnose_glb` and :func:`validate_gltf_json`
return JSON-serializable records only - a raw payload is replaced by its
``sha256:<64 hex>`` digest and its byte length - so a validation record can be
stored as evidence inside a JSON record.

Accessor arithmetic (implemented). Scalars and vectors are densely packed, so
their element size is ``columns * rows * component_size``. glTF 2.0 pads **each
matrix column** to a 4-byte boundary, so a matrix element size is
``columns * ceil(rows * component_size / 4) * 4`` - e.g. ``MAT3`` of
``UNSIGNED_BYTE`` is 3 columns x 4 bytes = 12 bytes, not 9. Enforced here:
componentType alignment of ``accessor.byteOffset`` and of the accessed
``bufferView.byteOffset``; ``byteStride`` bounds (an integer, a multiple of 4,
never above 252, never below the element size); the range
``byteOffset + byteStride * (count - 1) + element_size`` against
``bufferView.byteLength`` (the glTF 2.0 last-element bound, which equals the
``byteOffset + count * byteStride`` bound whenever ``byteStride`` equals the
element size); and sparse ``indices``/``values`` componentType, alignment and
range rules. A sparse accessor may legitimately declare no ``bufferView``.

Deliberately NOT implemented: semantic/geometry validation (normals,
manifoldness, units, materials, animation samplers) and resolution or fetching
of external ``uri`` buffers.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any, Mapping

from . import (
    MediaError,
    NOT_EXECUTED,
    STRUCTURAL_EVIDENCE,
    request_hash,
    require_mapping,
    require_text,
    validate_against,
)

__all__ = [
    "ADAPTER_ID",
    "BIN_CHUNK_TYPE",
    "GLB_HEADER_LENGTH",
    "GLB_MAGIC",
    "GLB_VERSION",
    "JSON_CHUNK_TYPE",
    "blender_adapter_declaration",
    "blender_adapter_report",
    "blender_capabilities",
    "blender_handoff",
    "build_glb",
    "diagnose_glb",
    "glb_report_summary",
    "gltf_element_size",
    "parse_glb",
    "summarize_glb",
    "validate_glb",
    "validate_gltf_json",
]

ADAPTER_ID = "design-lab.blender-adapter.structural"
ADAPTER_VERSION = "0.1.0-structural-e1"

GLB_MAGIC = b"glTF"
GLB_VERSION = 2
GLB_HEADER_LENGTH = 12
JSON_CHUNK_TYPE = 0x4E4F534A  # b"JSON" read little-endian
BIN_CHUNK_TYPE = 0x004E4942  # b"BIN\0" read little-endian
_CHUNK_HEADER_LENGTH = 8

#: Capability names this adapter declares but cannot execute.
_BLENDER_CAPABILITIES = (
    ("open-blend-file", "open a .blend document through the Blender CLI"),
    ("headless-render", "run ``--background`` renders on a fixed frame range"),
    ("gltf-export", "export a scene to .gltf or .glb"),
    ("geometry-readback", "read object counts, bounds and units back from a scene"),
    ("material-readback", "read material and texture bindings back from a scene"),
)

_SCHEMA_ARTIFACTS = [
    "src/design_lab/creative/media/three_d.py",
    "design-lab/schemas/media-three-d-adapter.schema.json",
]

#: glTF 2.0 componentType -> size of one component in bytes.
_GLTF_COMPONENT_SIZE = {5120: 1, 5121: 1, 5122: 2, 5123: 2, 5125: 4, 5126: 4}
#: glTF 2.0 accessor type -> (columns, rows).
_GLTF_ACCESSOR_SHAPE = {
    "SCALAR": (1, 1),
    "VEC2": (2, 1),
    "VEC3": (3, 1),
    "VEC4": (4, 1),
    "MAT2": (2, 2),
    "MAT3": (3, 3),
    "MAT4": (4, 4),
}
#: Accessor types whose columns are padded to a 4-byte boundary.
_GLTF_MATRIX_TYPES = frozenset({"MAT2", "MAT3", "MAT4"})
#: The only componentTypes glTF 2.0 allows for ``sparse.indices``.
_GLTF_SPARSE_INDEX_COMPONENT_TYPES = (5121, 5123, 5125)
#: Largest ``byteStride`` glTF 2.0 allows.
_GLTF_MAX_BYTE_STRIDE = 252


def _error(code: str, offset: int, detail: str) -> MediaError:
    return MediaError(code, f"offset={offset}: {detail}")


def _sha256_of(payload: bytes) -> str:
    """Digest of a raw payload: the JSON-safe stand-in for the payload itself."""
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def gltf_element_size(component_type: Any, accessor_type: Any) -> int | None:
    """Element size in bytes, or ``None`` when either enum value is unknown.

    Scalars and vectors are densely packed: ``columns * rows * component_size``.
    A matrix pads **each column** to a 4-byte boundary, so its element size is
    ``columns * ceil(rows * component_size / 4) * 4``; ``MAT3`` of
    ``UNSIGNED_BYTE`` is therefore 3 * 4 = 12 bytes, not 9.
    """
    if type(component_type) is not int or not isinstance(accessor_type, str):
        return None
    component_size = _GLTF_COMPONENT_SIZE.get(component_type)
    shape = _GLTF_ACCESSOR_SHAPE.get(accessor_type)
    if component_size is None or shape is None:
        return None
    columns, rows = shape
    if accessor_type in _GLTF_MATRIX_TYPES:
        column_size = -(-(rows * component_size) // 4) * 4
        return columns * column_size
    return columns * rows * component_size


def blender_capabilities() -> list:
    """Declared Blender capabilities; every one is unsupported in this build."""
    return [
        {
            "name": name,
            "supported": False,
            "note": (
                f"declared only - {subject}. Blender is not installed on this "
                "machine, so this build cannot execute or measure it"
            ),
        }
        for name, subject in _BLENDER_CAPABILITIES
    ]


def blender_adapter_declaration() -> dict:
    """The Blender adapter contract, validated against adapter-contract.schema.json.

    ``status`` is ``structural`` and ``mode`` is ``external-cli``: the CLI shape
    is declared, but no Blender binary exists on this host and no install path
    was probed, so no capability may be advertised as supported.
    """
    declaration = {
        "adapter_id": ADAPTER_ID,
        "tool": "blender",
        "status": "structural",
        "mode": "external-cli",
        "license": "GPL-3.0-or-later",
        "capabilities": blender_capabilities(),
        "fallback": (
            "no Blender fallback exists in this build: 3D artifacts are accepted "
            "only as already-produced GLB or glTF files and are validated "
            "structurally by design_lab.creative.media.three_d.validate_glb"
        ),
        "evidence": {
            "level": STRUCTURAL_EVIDENCE,
            "runtime_version": None,
            "task_ids": ["DL-P1-150"],
            "artifact_paths": list(_SCHEMA_ARTIFACTS),
            "note": (
                "Blender is not installed on this machine (declared, not probed); "
                "no Blender process was started, no scene was opened and no render "
                "or export was executed. A live Blender version, install path and "
                "readback remain NOT_EXECUTED"
            ),
        },
        "rollback": (
            "nothing to roll back structurally: this adapter writes no Blender "
            "file, preference or addon. A future live run must roll back by "
            "deleting only the artifacts it wrote under the project-local task "
            "runtime root, by releasing the headless process lease, and by "
            "restoring the scene file from its pre-run hash-checked copy"
        ),
    }
    return validate_against("adapter-contract", declaration)


def _check_uri(uri: Any, index: int, offset: int) -> str:
    if not isinstance(uri, str) or not uri:
        raise _error(
            "GLTF_BUFFER_URI_INVALID", offset, f"buffers[{index}].uri is empty or not a string"
        )
    if uri.startswith("data:"):
        raise MediaError(
            "GLTF_BUFFER_URI_DATA_URI_UNSUPPORTED",
            f"offset={offset}: buffers[{index}].uri is a data URI; embedded base64 "
            "payloads are not resolved structurally",
        )
    if "\\" in uri:
        raise _error(
            "GLTF_BUFFER_URI_UNSAFE",
            offset,
            f"buffers[{index}].uri {uri!r} uses a backslash path separator",
        )
    if uri.startswith("/") or (len(uri) > 1 and uri[1] == ":"):
        raise _error(
            "GLTF_BUFFER_URI_UNSAFE",
            offset,
            f"buffers[{index}].uri {uri!r} is an absolute path",
        )
    if ".." in uri.split("/"):
        raise _error(
            "GLTF_BUFFER_URI_UNSAFE",
            offset,
            f"buffers[{index}].uri {uri!r} traverses upwards",
        )
    return uri


def _require_alignment(*, offset: int, code: str, what: str, byte_offset: int,
                       view_offset: int, component_size: int) -> None:
    """glTF 2.0 data alignment: both offsets are multiples of the component size.

    The normative rule is that ``byteOffset`` and ``byteOffset +
    bufferView.byteOffset`` are multiples of the component size; checking each
    offset separately is the same rule expressed twice, and it names the exact
    offset that broke it.
    """
    for field, value in (("byteOffset", byte_offset),
                         ("bufferView.byteOffset", view_offset)):
        if value % component_size:
            raise _error(
                code,
                offset,
                f"{what} {field} {value} is not a multiple of the componentType "
                f"size {component_size}",
            )


def _sparse_view(block: Mapping, label: str, owner: str, offset: int,
                 buffer_views: list, view_lengths: list) -> tuple[int, int, int]:
    """Resolve ``sparse.<label>.bufferView`` to (index, byteOffset, byteLength)."""
    target = block.get("bufferView")
    if type(target) is not int or not 0 <= target < len(buffer_views):
        raise _error(
            "GLTF_SPARSE_BUFFERVIEW_INDEX",
            offset,
            f"{owner}.{label}.bufferView {target!r} does not reference a declared "
            f"bufferView (declared: {len(buffer_views)})",
        )
    view = buffer_views[target]
    view_offset = view.get("byteOffset", 0)
    if type(view_offset) is not int or view_offset < 0:
        view_offset = 0  # already refused by the bufferViews pass
    return target, view_offset, view_lengths[target]


def _check_sparse_accessor(sparse: Mapping, *, index: int, offset: int,
                           component_size: int | None, element: int | None,
                           count: Any, buffer_views: list,
                           view_lengths: list) -> None:
    """Validate a ``sparse`` block: counts, index componentType, ranges, alignment."""
    owner = f"accessors[{index}].sparse"
    sparse_count = sparse.get("count")
    if type(sparse_count) is not int or sparse_count <= 0:
        raise _error(
            "GLTF_SPARSE_COUNT",
            offset,
            f"{owner}.count must be a positive integer, got {sparse_count!r}",
        )
    if type(count) is int and 0 <= count < sparse_count:
        raise _error(
            "GLTF_SPARSE_COUNT",
            offset,
            f"{owner}.count {sparse_count} exceeds accessors[{index}].count {count}",
        )
    indices = sparse.get("indices")
    if not isinstance(indices, Mapping):
        raise _error("GLTF_SPARSE_INDICES", offset, f"{owner}.indices is missing")
    values = sparse.get("values")
    if not isinstance(values, Mapping):
        raise _error("GLTF_SPARSE_VALUES", offset, f"{owner}.values is missing")

    index_component_type = indices.get("componentType")
    if index_component_type not in _GLTF_SPARSE_INDEX_COMPONENT_TYPES:
        raise _error(
            "GLTF_SPARSE_INDICES_COMPONENT_TYPE",
            offset,
            f"{owner}.indices.componentType {index_component_type!r} is not one of "
            f"{list(_GLTF_SPARSE_INDEX_COMPONENT_TYPES)}",
        )
    index_size = _GLTF_COMPONENT_SIZE[index_component_type]
    indices_offset = indices.get("byteOffset", 0)
    if type(indices_offset) is not int or indices_offset < 0:
        raise _error(
            "GLTF_SPARSE_BYTEOFFSET",
            offset,
            f"{owner}.indices.byteOffset must be a non-negative integer",
        )
    _, indices_view_offset, indices_view_length = _sparse_view(
        indices, "indices", owner, offset, buffer_views, view_lengths
    )
    _require_alignment(
        offset=offset,
        code="GLTF_SPARSE_ALIGNMENT",
        what=f"{owner}.indices",
        byte_offset=indices_offset,
        view_offset=indices_view_offset,
        component_size=index_size,
    )
    indices_end = indices_offset + sparse_count * index_size
    if indices_end > indices_view_length:
        raise _error(
            "GLTF_SPARSE_RANGE",
            offset,
            f"{owner}.indices needs {indices_end} bytes but its bufferView "
            f"declares {indices_view_length}",
        )

    values_offset = values.get("byteOffset", 0)
    if type(values_offset) is not int or values_offset < 0:
        raise _error(
            "GLTF_SPARSE_BYTEOFFSET",
            offset,
            f"{owner}.values.byteOffset must be a non-negative integer",
        )
    _, values_view_offset, values_view_length = _sparse_view(
        values, "values", owner, offset, buffer_views, view_lengths
    )
    if component_size is None or element is None:
        return  # unknown accessor enums: the index half was still fully checked
    _require_alignment(
        offset=offset,
        code="GLTF_SPARSE_ALIGNMENT",
        what=f"{owner}.values",
        byte_offset=values_offset,
        view_offset=values_view_offset,
        component_size=component_size,
    )
    values_end = values_offset + sparse_count * element
    if values_end > values_view_length:
        raise _error(
            "GLTF_SPARSE_RANGE",
            offset,
            f"{owner}.values needs {values_end} bytes but its bufferView "
            f"declares {values_view_length}",
        )


def _check_accessor(accessor: Mapping, *, index: int, offset: int,
                    buffer_views: list, view_lengths: list) -> None:
    """Reference, alignment, stride and range rules for one accessor."""
    owner = f"accessors[{index}]"
    target = accessor.get("bufferView")
    if "bufferView" in accessor:
        if type(target) is not int or not 0 <= target < len(buffer_views):
            raise _error(
                "GLTF_ACCESSOR_BUFFERVIEW_INDEX",
                offset,
                f"{owner}.bufferView {target!r} does not reference a declared "
                f"bufferView (declared: {len(buffer_views)})",
            )
    else:
        target = None
        if not isinstance(accessor.get("sparse"), Mapping):
            raise _error(
                "GLTF_ACCESSOR_BUFFERVIEW_MISSING",
                offset,
                f"{owner} has no bufferView and no sparse block",
            )

    component_type = accessor.get("componentType")
    component_size = (
        _GLTF_COMPONENT_SIZE.get(component_type) if type(component_type) is int else None
    )
    element = gltf_element_size(component_type, accessor.get("type"))
    count = accessor.get("count")

    element_offset = accessor.get("byteOffset", 0)
    if type(element_offset) is not int or element_offset < 0:
        raise _error(
            "GLTF_ACCESSOR_BYTEOFFSET",
            offset,
            f"{owner}.byteOffset must be a non-negative integer",
        )

    sparse = accessor.get("sparse")
    if isinstance(sparse, Mapping):
        _check_sparse_accessor(
            sparse,
            index=index,
            offset=offset,
            component_size=component_size,
            element=element,
            count=count,
            buffer_views=buffer_views,
            view_lengths=view_lengths,
        )
    elif sparse is not None:
        raise _error("GLTF_SPARSE_NOT_OBJECT", offset, f"{owner}.sparse is not an object")

    if (target is None or component_size is None or element is None
            or type(count) is not int or count < 0):
        return  # unknown enum values stay tolerated by this structural validator
    view = buffer_views[target]
    view_length = view_lengths[target]
    view_offset = view.get("byteOffset", 0)
    if type(view_offset) is not int or view_offset < 0:
        view_offset = 0  # already refused by the bufferViews pass
    _require_alignment(
        offset=offset,
        code="GLTF_ACCESSOR_ALIGNMENT",
        what=owner,
        byte_offset=element_offset,
        view_offset=view_offset,
        component_size=component_size,
    )
    stride = view.get("byteStride")
    if stride is not None and stride < element:
        raise _error(
            "GLTF_ACCESSOR_BYTESTRIDE",
            offset,
            f"{owner} needs an element of {element} bytes but bufferViews[{target}] "
            f"declares byteStride {stride}",
        )
    if stride is not None:
        required = element_offset + max(count - 1, 0) * stride + element
    else:
        required = element_offset + count * element
    if required > view_length:
        raise _error(
            "GLTF_ACCESSOR_RANGE",
            offset,
            f"{owner} needs {required} bytes but bufferViews[{target}] "
            f"declares {view_length}",
        )


def _check_document(document: Any, *, container: str, offset: int,
                    bin_chunk_lengths: list | None) -> dict:
    """glTF 2.0 reference integrity shared by the GLB and .gltf containers.

    Covers buffers, bufferViews (including ``byteStride`` bounds) and the full
    accessor matrix: componentType x accessor-type element size, alignment,
    stride and range, plus sparse ``indices``/``values``.
    """
    if not isinstance(document, Mapping):
        raise _error(
            "GLTF_DOCUMENT_NOT_OBJECT", offset, f"top level is {type(document).__name__}"
        )
    asset = document.get("asset")
    if not isinstance(asset, Mapping):
        raise _error("GLTF_ASSET_MISSING", offset, "required member 'asset' is missing")
    version = asset.get("version")
    if version != "2.0":
        raise _error(
            "GLTF_ASSET_VERSION",
            offset,
            f"asset.version is {version!r}, expected '2.0'",
        )

    buffers = document.get("buffers", [])
    if not isinstance(buffers, list):
        raise _error("GLTF_BUFFERS_NOT_ARRAY", offset, "'buffers' must be an array")
    buffer_lengths = []
    external_assets = []
    for index, buffer in enumerate(buffers):
        if not isinstance(buffer, Mapping):
            raise _error(
                "GLTF_BUFFER_NOT_OBJECT", offset, f"buffers[{index}] is not an object"
            )
        byte_length = buffer.get("byteLength")
        if type(byte_length) is not int or byte_length < 0:
            raise _error(
                "GLTF_BUFFER_BYTELENGTH",
                offset,
                f"buffers[{index}].byteLength must be a non-negative integer",
            )
        if "uri" in buffer:
            uri = _check_uri(buffer["uri"], index, offset)
            external_assets.append(
                {
                    "kind": "buffer",
                    "index": index,
                    "uri": uri,
                    "byteLength": byte_length,
                    "resolution": "NOT_PROBED",
                    "note": "declared external asset; never resolved or fetched",
                }
            )
        elif bin_chunk_lengths is None:
            raise _error(
                "GLTF_BUFFER_REQUIRES_URI",
                offset,
                f"buffers[{index}] has no uri and the gltf container has no BIN "
                "chunk to resolve it",
            )
        else:
            if index >= len(bin_chunk_lengths):
                raise _error(
                    "GLB_BUFFER_BINARY_CHUNK_MISSING",
                    offset,
                    f"buffers[{index}] declares no uri but only "
                    f"{len(bin_chunk_lengths)} BIN chunk(s) exist",
                )
            chunk = bin_chunk_lengths[index]
            if byte_length > chunk["length"]:
                raise _error(
                    "GLB_BUFFER_BYTELENGTH_EXCEEDS_CHUNK",
                    chunk["data_offset"] + max(chunk["length"], 0),
                    f"buffers[{index}].byteLength {byte_length} exceeds BIN chunk "
                    f"{index} length {chunk['length']}",
                )
        buffer_lengths.append(byte_length)

    buffer_views = document.get("bufferViews", [])
    if not isinstance(buffer_views, list):
        raise _error("GLTF_BUFFERVIEWS_NOT_ARRAY", offset, "'bufferViews' must be an array")
    view_lengths: list = []
    for index, view in enumerate(buffer_views):
        if not isinstance(view, Mapping):
            raise _error(
                "GLTF_BUFFERVIEW_NOT_OBJECT", offset, f"bufferViews[{index}] is not an object"
            )
        target = view.get("buffer")
        if type(target) is not int or not 0 <= target < len(buffer_lengths):
            raise _error(
                "GLTF_BUFFERVIEW_BUFFER_INDEX",
                offset,
                f"bufferViews[{index}].buffer {target!r} does not reference a "
                f"declared buffer (declared: {len(buffer_lengths)})",
            )
        view_length = view.get("byteLength")
        if type(view_length) is not int or view_length < 0:
            raise _error(
                "GLTF_BUFFERVIEW_BYTELENGTH",
                offset,
                f"bufferViews[{index}].byteLength must be a non-negative integer",
            )
        view_offset = view.get("byteOffset", 0)
        if type(view_offset) is not int or view_offset < 0:
            raise _error(
                "GLTF_BUFFERVIEW_BYTEOFFSET",
                offset,
                f"bufferViews[{index}].byteOffset must be a non-negative integer",
            )
        if view_offset + view_length > buffer_lengths[target]:
            raise _error(
                "GLTF_BUFFERVIEW_RANGE",
                offset,
                f"bufferViews[{index}] spans {view_offset}+{view_length} bytes but "
                f"buffers[{target}].byteLength is {buffer_lengths[target]}",
            )
        stride = view.get("byteStride")
        if stride is not None:
            if type(stride) is not int or stride < 0:
                raise _error(
                    "GLTF_BUFFERVIEW_BYTESTRIDE",
                    offset,
                    f"bufferViews[{index}].byteStride must be a non-negative integer",
                )
            if stride % 4:
                raise _error(
                    "GLTF_BUFFERVIEW_BYTESTRIDE",
                    offset,
                    f"bufferViews[{index}].byteStride {stride} is not a multiple of 4",
                )
            if stride > _GLTF_MAX_BYTE_STRIDE:
                raise _error(
                    "GLTF_BUFFERVIEW_BYTESTRIDE",
                    offset,
                    f"bufferViews[{index}].byteStride {stride} exceeds the glTF "
                    f"maximum of {_GLTF_MAX_BYTE_STRIDE}",
                )
        view_lengths.append(view_length)

    accessors = document.get("accessors", [])
    if not isinstance(accessors, list):
        raise _error("GLTF_ACCESSORS_NOT_ARRAY", offset, "'accessors' must be an array")
    for index, accessor in enumerate(accessors):
        if not isinstance(accessor, Mapping):
            raise _error(
                "GLTF_ACCESSOR_NOT_OBJECT", offset, f"accessors[{index}] is not an object"
            )
        _check_accessor(
            accessor,
            index=index,
            offset=offset,
            buffer_views=buffer_views,
            view_lengths=view_lengths,
        )

    return {
        "asset_version": version,
        "counts": {
            "buffers": len(buffers),
            "bufferViews": len(buffer_views),
            "accessors": len(accessors),
            "meshes": len(document.get("meshes", []) or []),
            "nodes": len(document.get("nodes", []) or []),
            "materials": len(document.get("materials", []) or []),
            "scenes": len(document.get("scenes", []) or []),
        },
        "external_assets": external_assets,
        "container": container,
    }


def validate_gltf_json(document: Mapping) -> dict:
    """Validate a ``.gltf`` JSON document without a BIN chunk.

    Every ``buffer`` must declare a ``uri``; those URIs are recorded as declared
    external assets and are never resolved, opened or fetched. The container has
    no bytes, so reported offsets are ``0`` (document start).
    """
    checks = _check_document(document, container="gltf", offset=0, bin_chunk_lengths=None)
    return {
        "status": "VALID",
        "evidence_level": STRUCTURAL_EVIDENCE,
        "container": "gltf",
        "byte_length": None,
        "header": None,
        "chunk_table": [],
        "asset_version": checks["asset_version"],
        "counts": checks["counts"],
        "external_assets": checks["external_assets"],
        "json_chunk": None,
        "bin_chunks": [],
        "document": dict(document),
    }


def parse_glb(data: bytes) -> dict:
    """Low-level GLB container walk. Reads bytes only; opens no file.

    This is the **only** function in this module that returns raw chunk
    payloads: ``json_chunk["body"]``, each ``bin_chunks[i]["body"]`` (the payload
    truncated to the declared ``buffers[i].byteLength``), each
    ``bin_chunks[i]["data"]`` (the full 4-byte padded payload) and the
    ``binary_chunks`` list are ``bytes``. Use :func:`validate_glb` when the
    record must be JSON-serializable.
    """
    if not isinstance(data, (bytes, bytearray, memoryview)):
        raise MediaError(
            "GLB_INPUT_NOT_BYTES", f"expected bytes, got {type(data).__name__}"
        )
    data = bytes(data)
    if len(data) < GLB_HEADER_LENGTH:
        raise _error(
            "GLB_HEADER_TRUNCATED",
            0,
            f"only {len(data)} bytes present, the glTF header needs 12",
        )
    if data[0:4] != GLB_MAGIC:
        raise _error(
            "GLB_HEADER_MAGIC", 0, f"magic is {data[0:4]!r}, expected {GLB_MAGIC!r}"
        )
    version = int.from_bytes(data[4:8], "little")
    if version != GLB_VERSION:
        raise _error("GLB_HEADER_VERSION", 4, f"version is {version}, expected 2")
    declared_length = int.from_bytes(data[8:12], "little")
    if declared_length != len(data):
        raise _error(
            "GLB_HEADER_LENGTH",
            8,
            f"declared length {declared_length} != actual {len(data)} bytes",
        )

    chunks = []
    bin_chunks = []
    json_chunk = None
    offset = GLB_HEADER_LENGTH
    while offset < len(data):
        if len(data) - offset < _CHUNK_HEADER_LENGTH:
            raise _error(
                "GLB_CHUNK_HEADER_TRUNCATED",
                offset,
                f"{len(data) - offset} trailing bytes cannot hold an 8-byte chunk header",
            )
        chunk_length = int.from_bytes(data[offset:offset + 4], "little")
        chunk_type = int.from_bytes(data[offset + 4:offset + 8], "little")
        data_offset = offset + _CHUNK_HEADER_LENGTH
        end = data_offset + chunk_length
        if chunk_length % 4:
            raise _error(
                "GLB_CHUNK_ALIGNMENT",
                offset,
                f"chunk length {chunk_length} is not 4-byte aligned",
            )
        if end > len(data):
            raise _error(
                "GLB_CHUNK_BOUNDS",
                offset,
                f"chunk length {chunk_length} at {offset} overruns the "
                f"{len(data)}-byte container",
            )
        body = data[data_offset:end]
        if chunk_type == JSON_CHUNK_TYPE:
            if json_chunk is not None:
                raise _error("GLB_CHUNK_ORDER", offset, "a second JSON chunk is present")
            if chunks:
                raise _error(
                    "GLB_CHUNK_ORDER", offset, "the JSON chunk must be the first chunk"
                )
            json_chunk = {
                "index": len(chunks),
                "header_offset": offset,
                "data_offset": data_offset,
                "length": chunk_length,
                "body": body,
            }
            chunks.append(
                {
                    "index": len(chunks),
                    "type": "JSON",
                    "chunk_type": chunk_type,
                    "header_offset": offset,
                    "data_offset": data_offset,
                    "length": chunk_length,
                }
            )
        elif chunk_type == BIN_CHUNK_TYPE:
            if json_chunk is None:
                raise _error(
                    "GLB_CHUNK_ORDER", offset, "a BIN chunk appears before the JSON chunk"
                )
            bin_chunks.append(
                {
                    "index": len(bin_chunks),
                    "header_offset": offset,
                    "data_offset": data_offset,
                    "length": chunk_length,
                    "body": body,
                }
            )
            chunks.append(
                {
                    "index": len(chunks),
                    "type": "BIN",
                    "chunk_type": chunk_type,
                    "header_offset": offset,
                    "data_offset": data_offset,
                    "length": chunk_length,
                }
            )
        else:
            raise _error(
                "GLB_CHUNK_TYPE_UNKNOWN",
                offset,
                f"chunk type {chunk_type:#010x} is neither JSON nor BIN",
            )
        offset = end

    if offset != len(data):
        raise _error("GLB_TRAILING_BYTES", offset, "unparsed trailing bytes remain")
    if json_chunk is None:
        raise _error("GLB_JSON_CHUNK_MISSING", len(data), "no JSON chunk is present")

    raw_json = data[json_chunk["data_offset"]:json_chunk["data_offset"] + json_chunk["length"]]
    try:
        text = raw_json.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise _error(
            "GLB_JSON_ENCODING", json_chunk["data_offset"], f"JSON chunk is not UTF-8: {exc}"
        ) from exc
    stripped = text.rstrip(" ")
    json_chunk["padding"] = len(text) - len(stripped)
    try:
        document = json.loads(stripped)
    except json.JSONDecodeError as exc:
        raise _error(
            "GLB_JSON_PARSE",
            json_chunk["data_offset"],
            f"JSON chunk does not parse: {exc.msg} at column {exc.colno}",
        ) from exc
    if not isinstance(document, Mapping):
        raise _error(
            "GLB_JSON_NOT_OBJECT",
            json_chunk["data_offset"],
            f"JSON chunk decoded to {type(document).__name__}, expected an object",
        )

    buffers = document.get("buffers", [])
    if not isinstance(buffers, list):
        buffers = []
    parsed_chunks = []
    for chunk in bin_chunks:
        buffer = buffers[chunk["index"]] if chunk["index"] < len(buffers) else {}
        declared = buffer.get("byteLength") if isinstance(buffer, Mapping) else None
        body = chunk["body"]
        if type(declared) is int:
            padding_nonzero = any(byte != 0 for byte in body[declared:])
        else:
            padding_nonzero = False
        parsed_chunks.append(
            {
                "index": chunk["index"],
                "header_offset": chunk["header_offset"],
                "data_offset": chunk["data_offset"],
                "length": chunk["length"],
                "declared_byte_length": declared,
                "body": body[:declared] if type(declared) is int else body,
                "data": body,
                "padding_nonzero": padding_nonzero,
            }
        )
    return {
        "container": "glb",
        "byte_length": len(data),
        "header": {"magic": "glTF", "version": GLB_VERSION, "length": declared_length},
        "chunk_table": [dict(entry) for entry in chunks],
        "json_chunk": json_chunk,
        "bin_chunks": parsed_chunks,
        "binary_chunks": [chunk["data"] for chunk in parsed_chunks],
        "document": dict(document),
    }


def validate_glb(data: bytes) -> dict:
    """Structurally validate a GLB container and return a JSON-safe record.

    The return value contains no ``bytes`` object anywhere: every raw chunk
    payload is replaced by its ``sha256:<64 hex>`` digest and its byte length, so
    ``json.dumps(validate_glb(data))`` always succeeds and the record can be
    stored as evidence. Use :func:`parse_glb` when the raw payloads are needed.
    """
    parsed = parse_glb(data)
    json_chunk = parsed["json_chunk"]
    document = parsed["document"]
    bin_chunks = parsed["bin_chunks"]

    checks = _check_document(
        document,
        container="glb",
        offset=json_chunk["data_offset"],
        bin_chunk_lengths=bin_chunks,
    )
    buffers = document.get("buffers", [])
    if not isinstance(buffers, list):
        buffers = []
    public_chunks = []
    for chunk in bin_chunks:
        buffer = buffers[chunk["index"]] if chunk["index"] < len(buffers) else {}
        declared = buffer.get("byteLength") if isinstance(buffer, Mapping) else None
        public_chunks.append(
            {
                "index": chunk["index"],
                "header_offset": chunk["header_offset"],
                "data_offset": chunk["data_offset"],
                "length": chunk["length"],
                "byte_length": chunk["length"],
                "declared_byte_length": declared,
                "sha256": _sha256_of(chunk["data"]),
                "padding_nonzero": bool(chunk["padding_nonzero"]),
            }
        )
    return {
        "status": "VALID",
        "evidence_level": STRUCTURAL_EVIDENCE,
        "container": "glb",
        "byte_length": parsed["byte_length"],
        "header": dict(parsed["header"]),
        "chunk_table": [dict(entry) for entry in parsed["chunk_table"]],
        "json_chunk": {
            "index": json_chunk["index"],
            "header_offset": json_chunk["header_offset"],
            "data_offset": json_chunk["data_offset"],
            "length": json_chunk["length"],
            "byte_length": json_chunk["length"],
            "padding": json_chunk.get("padding", 0),
            "sha256": _sha256_of(json_chunk["body"]),
        },
        "bin_chunks": public_chunks,
        "asset_version": checks["asset_version"],
        "counts": checks["counts"],
        "external_assets": checks["external_assets"],
        "document": dict(document),
    }


def summarize_glb(data: bytes) -> dict:
    """Compact JSON-safe GLB summary for an evidence record.

    Holds the container kind, the byte length, the 12-byte header, a digest of
    the whole chunk table, the document counts, the asset version, the verdict
    and the declared external assets - no chunk payload, no document body and no
    ``bytes`` value anywhere, so it is safe to embed in a JSON evidence record
    even though the full validation record stays available beside it.
    """
    record = validate_glb(data)
    chunk_table = [dict(entry) for entry in record["chunk_table"]]
    return {
        "status": record["status"],
        "verdict": record["status"],
        "evidence_level": STRUCTURAL_EVIDENCE,
        "container": record["container"],
        "byte_length": record["byte_length"],
        "header": dict(record["header"]),
        "chunk_table": {
            "count": len(chunk_table),
            "types": [entry["type"] for entry in chunk_table],
            "sha256": request_hash({"chunk_table": chunk_table}),
        },
        "counts": dict(record["counts"]),
        "asset_version": record["asset_version"],
        "external_assets": [dict(asset) for asset in record["external_assets"]],
    }


def diagnose_glb(data: bytes) -> dict:
    """Non-raising wrapper around :func:`validate_glb` for triage and reporting.

    The embedded record is the JSON-safe one returned by :func:`validate_glb`,
    so a diagnosis can be serialized as-is.
    """
    try:
        return {"valid": True, "record": validate_glb(data), "error": None}
    except MediaError as exc:
        return {"valid": False, "record": None, "error": str(exc)}


def glb_report_summary(record: Mapping) -> dict:
    """The schema-shaped subset of a :func:`validate_glb` record.

    ``media-three-d-adapter.schema.json`` pins this exact shape, so the digest
    and byte_length fields of the full record are deliberately not re-exported
    here.
    """
    require_mapping(record, "record")
    json_chunk = record.get("json_chunk")
    return {
        "status": require_text(record.get("status"), "status"),
        "container": require_text(record.get("container"), "container"),
        "evidence_level": STRUCTURAL_EVIDENCE,
        "byte_length": record.get("byte_length"),
        "asset_version": require_text(record.get("asset_version"), "asset_version"),
        "counts": dict(record.get("counts", {})),
        "external_assets": [
            dict(asset) for asset in record.get("external_assets", [])
        ],
        "json_chunk": None if json_chunk is None else {
            "index": json_chunk["index"],
            "header_offset": json_chunk["header_offset"],
            "data_offset": json_chunk["data_offset"],
            "length": json_chunk["length"],
            "padding": json_chunk.get("padding", 0),
        },
        "bin_chunks": [
            {
                "index": chunk["index"],
                "header_offset": chunk["header_offset"],
                "data_offset": chunk["data_offset"],
                "length": chunk["length"],
                "declared_byte_length": chunk.get("declared_byte_length"),
                "padding_nonzero": bool(chunk.get("padding_nonzero")),
            }
            for chunk in record.get("bin_chunks", [])
        ],
    }


def build_glb(json_document: Mapping, binary_chunk: bytes | None = None) -> bytes:
    """Build a GLB container from a JSON document and an optional BIN chunk.

    JSON padding is spaces and BIN padding is zeros, as glTF 2.0 requires, so
    ``parse_glb(build_glb(document, chunk))`` returns the document unchanged and
    the chunk body byte for byte, and ``validate_glb`` reports the same container
    with the payload replaced by its digest.
    """
    if not isinstance(json_document, Mapping):
        raise MediaError(
            "GLB_DOCUMENT_NOT_OBJECT",
            f"expected a mapping, got {type(json_document).__name__}",
        )
    try:
        payload = json.dumps(
            dict(json_document), ensure_ascii=False, separators=(",", ":"), allow_nan=False
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise MediaError("GLB_DOCUMENT_NOT_SERIALIZABLE", str(exc)) from exc
    padded_json = payload + b" " * (-len(payload) % 4)
    body = (
        len(padded_json).to_bytes(4, "little")
        + JSON_CHUNK_TYPE.to_bytes(4, "little")
        + padded_json
    )
    if binary_chunk is not None:
        if not isinstance(binary_chunk, (bytes, bytearray, memoryview)):
            raise MediaError(
                "GLB_CHUNK_NOT_BYTES", f"expected bytes, got {type(binary_chunk).__name__}"
            )
        raw = bytes(binary_chunk)
        padded_bin = raw + b"\x00" * (-len(raw) % 4)
        body += (
            len(padded_bin).to_bytes(4, "little")
            + BIN_CHUNK_TYPE.to_bytes(4, "little")
            + padded_bin
        )
    total = GLB_HEADER_LENGTH + len(body)
    header = GLB_MAGIC + GLB_VERSION.to_bytes(4, "little") + total.to_bytes(4, "little")
    return header + body


def blender_handoff(plan: Mapping) -> dict:
    """Describe the live handoff a real Blender adapter would perform.

    Nothing here is executed: the plan is validated, the steps are described and
    the record ends with ``requires a live Blender run: NOT_EXECUTED``.
    """
    plan = require_mapping(plan, "plan", code="BLENDER_HANDOFF_PLAN_INVALID")
    allowed = {
        "handoff_id", "scene_ref", "script_ref", "output_ref", "blender_ref",
        "frames",
    }
    if set(plan) - allowed:
        raise MediaError(
            "BLENDER_HANDOFF_PLAN_INVALID",
            f"unexpected plan keys: {sorted(set(plan) - allowed)}",
        )
    handoff_id = require_text(
        plan.get("handoff_id"), "handoff_id", code="BLENDER_HANDOFF_PLAN_INVALID"
    )
    scene_ref = require_text(
        plan.get("scene_ref"), "scene_ref", code="BLENDER_HANDOFF_PLAN_INVALID"
    )
    script_ref = require_text(
        plan.get("script_ref"), "script_ref", code="BLENDER_HANDOFF_PLAN_INVALID"
    )
    output_ref = require_text(
        plan.get("output_ref"), "output_ref", code="BLENDER_HANDOFF_PLAN_INVALID"
    )
    blender_ref = plan.get("blender_ref", "os-toolchain")
    require_text(blender_ref, "blender_ref", code="BLENDER_HANDOFF_PLAN_INVALID")
    frames = plan.get("frames")
    if frames is not None:
        if (not isinstance(frames, list) or len(frames) != 2
                or any(type(value) is not int or value < 0 for value in frames)
                or frames[1] < frames[0]):
            raise MediaError(
                "BLENDER_HANDOFF_PLAN_INVALID",
                "frames must be an inclusive [first, last] pair of non-negative integers",
            )
    steps = [
        {
            "step": 1,
            "action": (
                f"probe the Blender install path through the declared alias "
                f"'{blender_ref}' (never an absolute path) and record the exact "
                "binary version string"
            ),
            "status": NOT_EXECUTED,
            "requires": (
                "a live Blender installation resolvable through the declared "
                "alias; no install path was probed in this build"
            ),
        },
        {
            "step": 2,
            "action": (
                f"run headless: blender --background {scene_ref} --python "
                f"{script_ref} -- {output_ref}"
                + ("" if frames is None else f" --frames {frames[0]}..{frames[1]}")
            ),
            "status": NOT_EXECUTED,
            "requires": (
                "a live Blender run; this build starts no process and opens no scene"
            ),
        },
        {
            "step": 3,
            "action": (
                f"read back the produced file at '{output_ref}': hash it, compare "
                "with the exporter declaration and validate the container with "
                "validate_glb"
            ),
            "status": NOT_EXECUTED,
            "requires": (
                "an artifact produced by step 2; nothing was produced here, so no "
                "hash exists to read back"
            ),
        },
        {
            "step": 4,
            "action": (
                "roll back by deleting only the artifacts written under the "
                "project-local task runtime root and releasing the process lease"
            ),
            "status": NOT_EXECUTED,
            "requires": "a live run to have written something first",
        },
    ]
    return {
        "handoff_id": handoff_id,
        "task_ids": ["DL-P1-150"],
        "evidence_level": STRUCTURAL_EVIDENCE,
        "scene_ref": scene_ref,
        "script_ref": script_ref,
        "output_ref": output_ref,
        "blender_ref": blender_ref,
        "frames": frames,
        "steps": steps,
        "requires_live_host": True,
        "host_execution": NOT_EXECUTED,
        "note": "requires a live Blender run: NOT_EXECUTED",
    }


def blender_adapter_report(*, glb_validation: Mapping | None = None,
                           handoff: Mapping | None = None) -> dict:
    """Adapter report validated by ``media-three-d-adapter.schema.json``.

    The embedded ``adapter_contract`` is the same document that
    :func:`blender_adapter_declaration` validates against the repository's
    ``adapter-contract.schema.json``; the report schema only fixes its summary
    shape.
    """
    declaration = blender_adapter_declaration()
    report = {
        "schemaVersion": "design-lab/media-three-d-adapter/v1",
        "adapter_id": declaration["adapter_id"],
        "task_ids": ["DL-P1-150"],
        "evidence_level": STRUCTURAL_EVIDENCE,
        "host": {
            "tool": "blender",
            "status": "structural",
            "mode": "external-cli",
            "installed": False,
            "install_state": "NOT_PROBED_ON_THIS_HOST",
            "note": (
                "Blender is not installed on this machine (declared, not probed); "
                "no install path was searched and no host run was executed"
            ),
        },
        "capabilities": [dict(item) for item in declaration["capabilities"]],
        "adapter_contract": declaration,
        "handoff": None if handoff is None else dict(handoff),
        "glb_validation": (
            None if glb_validation is None else glb_report_summary(glb_validation)
        ),
    }
    return validate_against("media-three-d-adapter", report)
