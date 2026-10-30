# SPDX-License-Identifier: MIT
"""DL-P1-131 / DLDS-F080: video ownership boundary rule engine over capability ids.

Declares, as machine-readable data, which side owns each video-delivery
operation. DESIGN-LAB owns the visual design, the design IR, the timeline
contract, the handoff bundle and the delivery receipt. A video host (Premiere
Pro, Media Encoder, After Effects class of tool) owns rendering, encoding,
colour-managed export, audio mixdown and hardware acceleration. Shared
operations are listed with the side that must produce the evidence.

Every host-side requirement is a **versioned capability-registry id**, never a
free string and never a product name. DLDS-F080 abolishes the descriptive
``host_classes`` list this module used to carry: a rule that branches on
``"Premiere Pro class non-linear editor"`` branches on prose, which cannot be
versioned, cannot be looked up and silently re-points at a different capability
when a vendor renames a product.

The grammar is ``capability:<domain>/<name>@<integer version>``
(for example ``capability:video/render@1``). Why this shape:

* it mirrors the provider style already frozen by
  ``design-lab/schemas/provider-capability.schema.json``
  (``provider:<domain>/<name>``), so one prefix discipline covers both
  registries and a reader can tell at a glance which registry an id belongs to;
* the ``@<integer version>`` is what makes a reference *versioned*. A capability
  registry entry may change behaviour between versions, so an unversioned
  reference would re-point at a different capability without any edit to this
  boundary: the version is part of the identity, not decoration;
* the separator between domain and name accepts both ``/`` (the canonical form,
  matching the provider style) and ``.`` (the spelling used by the DLDS-F080
  example ``capability:video.render@1``). Both are the same grammar - a domain,
  a separator, a name, ``@`` and an integer version - and both are refused if
  the prefix, the separator or the version is missing.

A human-readable label exists only for display, in the separate
``display_label`` field, and :func:`capability_labels` is the only function in
this module that reads it. No rule branches on a label: the ownership rules read
``host_capability_refs`` and the closed operation vocabulary only.

This module does NOT render, encode, transcode, colour-manage, mix audio or
touch a GPU, and it does NOT call any host. It is a rule engine over a
structural document: it refuses a request that asks DESIGN-LAB to do host work,
it fails closed when a rule references a capability the document does not
declare, and it lists the claims a handoff bundle cannot support with E1
evidence only. Nothing here upgrades an evidence level: a claim that would need
a host run is reported as ``NOT_EXECUTED``.
"""
from __future__ import annotations

import re
from typing import Any, Mapping

from . import (
    HOST_EVIDENCE_PREFIX,
    HOST_EVIDENCE_REFERENCE,
    MEASURED_EVIDENCE_LEVELS,
    MediaError,
    NOT_EXECUTED,
    STRUCTURAL_EVIDENCE,
    require_evidence_level,
    require_mapping,
    require_text,
    validate_against,
)

__all__ = [
    "BOUNDARY_ID",
    "BOUNDARY_VERSION",
    "CAPABILITY_PREFIX",
    "CAPABILITY_REF_PATTERN",
    "HOST_CAPABILITIES",
    "OPERATIONS",
    "OWNERS",
    "RENDER_OR_ENCODE_OPERATIONS",
    "assert_within_boundary",
    "boundary_document",
    "boundary_entries_by_operation",
    "capability_labels",
    "require_capability_ref",
    "unsupported_video_claims",
    "validate_boundary",
    "validate_capability_refs",
]

BOUNDARY_ID = "DL-P1-131-video-boundary"
BOUNDARY_VERSION = "design-lab/media-video-boundary/v2"
OWNERS = ("design-lab", "host", "shared")

#: Registry prefix of a versioned capability reference.
CAPABILITY_PREFIX = "capability:"
#: ``capability:<domain>/<name>@<integer version>``; see the module docstring for
#: why the reference carries a version and why both separators are one grammar.
CAPABILITY_REF_PATTERN = re.compile(
    r"^capability:[a-z][a-z0-9-]*[/.][a-z][a-z0-9.-]*@(0|[1-9][0-9]*)$"
)

#: The host capabilities this boundary is allowed to reference. The second
#: element of each pair is a display label: it is never read by any rule.
HOST_CAPABILITIES = (
    ("capability:video/nonlinear-edit@1", "Premiere Pro class non-linear editor"),
    ("capability:video/render@1", "frame rendering engine of the host"),
    ("capability:video/encode@1", "Media Encoder class encoding tool"),
    ("capability:video/composite@1", "After Effects class compositing and motion tool"),
    ("capability:video/colour-managed-export@1",
     "colour-managed export with an applied output transform"),
    ("capability:video/audio-mixdown@1", "audio mixdown and loudness normalisation"),
    ("capability:video/hardware-acceleration@1", "hardware encode/decode accelerator"),
)

#: The closed operation vocabulary of the boundary.
OPERATIONS = (
    "visual-design",
    "design-ir",
    "timeline-contract",
    "handoff-bundle",
    "delivery-receipt",
    "render",
    "encode",
    "colour-managed-export",
    "audio-mixdown",
    "hardware-acceleration",
    "colour-space-declaration",
    "frame-accuracy-contract",
    "media-asset-packaging",
)

#: Operations that produce rendered or encoded bytes. DESIGN-LAB may never own
#: one of these without a measured host-live receipt.
RENDER_OR_ENCODE_OPERATIONS = frozenset(
    {
        "render",
        "encode",
        "colour-managed-export",
        "audio-mixdown",
        "hardware-acceleration",
        "frame-accuracy-contract",
    }
)

#: Operations that only DESIGN-LAB may own; a host must never be declared the
#: owner of the design record itself.
DESIGN_OWNED_OPERATIONS = frozenset(
    {"visual-design", "design-ir", "timeline-contract", "handoff-bundle", "delivery-receipt"}
)

#: Operations a host or a shared handoff cannot perform without declaring at
#: least one host capability.
_HANDS_OFF_TO_HOST = ("host", "shared")

_ENTRIES = (
    {
        "id": "video-boundary-visual-design",
        "subject": "visual design decisions: composition, type, colour intent, motion language",
        "operation": "visual-design",
        "owner": "design-lab",
        "host_capability_refs": (),
        "rule": (
            "DESIGN-LAB owns every visual design decision and records it in the "
            "design record; a host may never be the source of truth for it"
        ),
    },
    {
        "id": "video-boundary-design-ir",
        "subject": "the design IR document that carries the design between tools",
        "operation": "design-ir",
        "owner": "design-lab",
        "host_capability_refs": (),
        "rule": (
            "DESIGN-LAB owns the design IR, its schema and its version; a host "
            "receives a snapshot and may not redefine it"
        ),
    },
    {
        "id": "video-boundary-timeline-contract",
        "subject": "the timeline contract: sequence, track roles, in and out points",
        "operation": "timeline-contract",
        "owner": "design-lab",
        "host_capability_refs": ("capability:video/nonlinear-edit@1",),
        "rule": (
            "DESIGN-LAB declares the timeline contract that the host must honour; "
            "the host may report back that it cannot honour part of it"
        ),
    },
    {
        "id": "video-boundary-handoff-bundle",
        "subject": "the handoff bundle assembled for the video host",
        "operation": "handoff-bundle",
        "owner": "design-lab",
        "host_capability_refs": (),
        "rule": (
            "DESIGN-LAB owns bundle assembly, manifest and hashes; the host owns "
            "whatever it does with the bundle after opening it"
        ),
    },
    {
        "id": "video-boundary-delivery-receipt",
        "subject": "the delivery receipt that closes an operation",
        "operation": "delivery-receipt",
        "owner": "design-lab",
        "host_capability_refs": (),
        "rule": (
            "DESIGN-LAB owns the delivery receipt and records the host readings "
            "inside it; a receipt without a host reading stays structural"
        ),
    },
    {
        "id": "video-boundary-render",
        "subject": "rendering frames of a sequence to image data",
        "operation": "render",
        "owner": "host",
        "host_capability_refs": ("capability:video/render@1",),
        "rule": (
            "the host renders; DESIGN-LAB never renders and never claims a "
            "rendered frame without a host-live readback receipt"
        ),
    },
    {
        "id": "video-boundary-encode",
        "subject": "encoding rendered frames into a delivery codec container",
        "operation": "encode",
        "owner": "host",
        "host_capability_refs": ("capability:video/encode@1",),
        "rule": (
            "the host encodes; DESIGN-LAB only declares the required codec, "
            "bitrate and container profile as a contract"
        ),
    },
    {
        "id": "video-boundary-colour-managed-export",
        "subject": "colour-managed export with an applied output transform",
        "operation": "colour-managed-export",
        "owner": "host",
        "host_capability_refs": ("capability:video/colour-managed-export@1",),
        "rule": (
            "the host performs the colour-managed export and reports the applied "
            "transform; DESIGN-LAB declares the intended colour space only"
        ),
    },
    {
        "id": "video-boundary-audio-mixdown",
        "subject": "audio mixdown and loudness normalisation of the sequence",
        "operation": "audio-mixdown",
        "owner": "host",
        "host_capability_refs": ("capability:video/audio-mixdown@1",),
        "rule": (
            "the host performs the mixdown; DESIGN-LAB supplies levels as a "
            "contract and reads back the measured loudness from the host"
        ),
    },
    {
        "id": "video-boundary-hardware-acceleration",
        "subject": "hardware-accelerated encode or decode paths",
        "operation": "hardware-acceleration",
        "owner": "host",
        "host_capability_refs": ("capability:video/hardware-acceleration@1",),
        "rule": (
            "the host owns GPU and hardware encoder selection; this project never "
            "requests, drives or measures an accelerator"
        ),
    },
    {
        "id": "video-boundary-colour-space-declaration",
        "subject": "the intended colour space and transfer function of a delivery",
        "operation": "colour-space-declaration",
        "owner": "shared",
        "host_capability_refs": ("capability:video/colour-managed-export@1",),
        "rule": (
            "DESIGN-LAB declares the intended colour space and the host applies "
            "it; the delivered file's embedded colour space is a host reading"
        ),
    },
    {
        "id": "video-boundary-frame-accuracy-contract",
        "subject": "frame-accurate timing between the timeline contract and the export",
        "operation": "frame-accuracy-contract",
        "owner": "shared",
        "host_capability_refs": (
            "capability:video/nonlinear-edit@1",
            "capability:video/render@1",
        ),
        "rule": (
            "DESIGN-LAB declares frame-accurate intent and the host proves it "
            "with a measured frame count and duration readback"
        ),
    },
    {
        "id": "video-boundary-media-asset-packaging",
        "subject": "packaging of source media, fonts and design assets for handoff",
        "operation": "media-asset-packaging",
        "owner": "shared",
        "host_capability_refs": (
            "capability:video/nonlinear-edit@1",
            "capability:video/composite@1",
        ),
        "rule": (
            "DESIGN-LAB packages and hashes the assets it owns; the host owns "
            "linking, relinking and media cache management inside its project"
        ),
    },
)


def require_capability_ref(value: Any, field: str = "capability_ref") -> str:
    """Return a versioned ``capability:`` registry id, or fail closed.

    Refused: a non-string, an empty or blank value, a reference without the
    ``capability:`` prefix, and a reference without an ``@<integer version>``.
    A free string such as ``"editor"`` or a product name is refused as well,
    because neither can be resolved in a capability registry.
    """
    if not isinstance(value, str) or not value.strip():
        raise MediaError(
            "VIDEO_CAPABILITY_REF_INVALID",
            f"{field} must be a nonempty versioned capability id such as "
            f"'capability:video/render@1'; got {value!r}",
        )
    if not value.startswith(CAPABILITY_PREFIX):
        raise MediaError(
            "VIDEO_CAPABILITY_REF_INVALID",
            f"{field} {value!r} must start with '{CAPABILITY_PREFIX}': a host "
            "requirement is a capability-registry reference, never a free string "
            "or a product name",
        )
    if not CAPABILITY_REF_PATTERN.match(value):
        raise MediaError(
            "VIDEO_CAPABILITY_REF_INVALID",
            f"{field} {value!r} is not a versioned capability id; expected "
            "'capability:<domain>/<name>@<integer version>' "
            "(for example 'capability:video/render@1')",
        )
    return value


def validate_capability_refs(refs: Any, field: str, *, declared=None) -> list:
    """Validate one list of capability references and return it as a list.

    Refuses a value that is not a list, an empty or malformed reference, a
    duplicated reference inside the list, and - when ``declared`` is given - a
    reference the boundary document does not declare in ``host_capabilities``.
    """
    if isinstance(refs, (str, bytes, Mapping)) or not isinstance(refs, (list, tuple)):
        raise MediaError(
            "VIDEO_CAPABILITY_REFS_INVALID",
            f"{field} must be a list of versioned capability ids such as "
            "'capability:video/render@1'",
        )
    collected = []
    seen = set()
    for index, ref in enumerate(refs):
        checked = require_capability_ref(ref, f"{field}[{index}]")
        if checked in seen:
            raise MediaError(
                "VIDEO_CAPABILITY_DUPLICATE",
                f"{field}[{index}] repeats {checked!r}; a duplicated capability id "
                "makes the requirement ambiguous",
            )
        seen.add(checked)
        if declared is not None and checked not in declared:
            raise MediaError(
                "VIDEO_CAPABILITY_UNDECLARED",
                f"{field}[{index}] references {checked!r}, which the boundary document "
                "does not declare in 'host_capabilities'; a rule may only reference a "
                "declared capability id, and an undeclared one fails closed",
            )
        collected.append(checked)
    return collected


def capability_labels(document: Mapping | None = None) -> dict:
    """Display-only lookup ``capability_ref -> display_label``.

    This is the only function in this module that reads ``display_label``. No
    ownership rule, no validation and no boundary decision may branch on a
    label: labels are prose for a human reader, and prose is not a contract.
    """
    document = boundary_document() if document is None else validate_boundary(document)
    return {
        item["capability_ref"]: item.get("display_label")
        for item in document["host_capabilities"]
    }


def _declared_capability_refs(document: Mapping) -> list:
    """The boundary document's declared capability ids, duplicate-free."""
    return validate_capability_refs(
        [item["capability_ref"] for item in document["host_capabilities"]],
        "host_capabilities[].capability_ref",
    )


def _document() -> dict:
    return {
        "schemaVersion": BOUNDARY_VERSION,
        "boundary_id": BOUNDARY_ID,
        "task_ids": ["DL-P1-131"],
        "evidence_level": STRUCTURAL_EVIDENCE,
        "host_execution": NOT_EXECUTED,
        "owners": list(OWNERS),
        "operations": list(OPERATIONS),
        "host_capabilities": [
            {"capability_ref": ref, "display_label": label}
            for ref, label in HOST_CAPABILITIES
        ],
        "entries": [
            {
                "id": entry["id"],
                "subject": entry["subject"],
                "operation": entry["operation"],
                "owner": entry["owner"],
                "host_capability_refs": list(entry["host_capability_refs"]),
                "rule": entry["rule"],
                "evidence": STRUCTURAL_EVIDENCE,
            }
            for entry in _ENTRIES
        ],
        "notes": [
            "DESIGN-LAB owns the design record and the handoff; the host owns "
            "every byte of rendered or encoded output",
            "every host requirement is a versioned capability-registry id "
            "('capability:<domain>/<name>@<version>'); 'display_label' is prose for "
            "a human reader and no rule may branch on it",
            "no host was launched for this document: it is a structural rule "
            "set, not a host capability report",
            "a design-lab ownership claim over rendered or encoded work is legal "
            f"only with a measured '{HOST_EVIDENCE_PREFIX}<id>' receipt",
        ],
    }


def boundary_document() -> dict:
    """The boundary document, schema-validated; a fresh copy on every call."""
    document = _document()
    return validate_boundary(document)


def validate_boundary(document: Mapping) -> Mapping:
    """Schema validation plus the ownership and capability integrity rules.

    Rules beyond the schema:

    * every declared capability id is a versioned ``capability:`` reference and
      is declared once (the schema cannot compare the ``capability_ref`` values
      of two objects, so duplicates are refused here);
    * a rule may only reference a capability id the document declares, and a
      host- or shared-owned operation must reference at least one;
    * every operation in :data:`OPERATIONS` is declared exactly once, and no
      step declares an operation twice (a duplicated operation is ambiguous);
    * a ``design-lab`` owner over rendered or encoded work requires a measured
      ``host-live:<id>`` evidence reference;
    * the design record itself may never be owned by a host.
    """
    require_mapping(document, "boundary document", code="VIDEO_BOUNDARY_INVALID")
    validate_against("media-video-boundary", document)

    declared = set(_declared_capability_refs(document))

    entries = document["entries"]
    seen = {}
    for position, entry in enumerate(entries):
        operation = entry["operation"]
        if operation in seen:
            raise MediaError(
                "VIDEO_BOUNDARY_DUPLICATE_OPERATION",
                f"entries[{position}] declares '{operation}' which entries"
                f"[{seen[operation]}] already declares; ownership would be ambiguous",
            )
        seen[operation] = position
        # Ownership first: who may act on an operation outranks what capability
        # they must bring to it, so a foreign owner is named as such.
        if entry["owner"] == "design-lab" and operation in RENDER_OR_ENCODE_OPERATIONS:
            reference = entry.get("host_live_evidence_ref")
            if not isinstance(reference, str) or not HOST_EVIDENCE_REFERENCE.match(reference):
                raise MediaError(
                    "VIDEO_BOUNDARY_OWNERSHIP_UNPROVEN",
                    f"entries[{position}] ('{entry['id']}') declares design-lab "
                    f"ownership of '{operation}' without a measured "
                    f"'{HOST_EVIDENCE_PREFIX}<id>' host-live evidence reference",
                )
        if entry["owner"] == "host" and operation in DESIGN_OWNED_OPERATIONS:
            raise MediaError(
                "VIDEO_BOUNDARY_FOREIGN_OWNERSHIP",
                f"entries[{position}] ('{entry['id']}') assigns the design-owned "
                f"operation '{operation}' to a host",
            )
        refs = validate_capability_refs(
            entry["host_capability_refs"],
            f"entries[{position}].host_capability_refs",
            declared=declared,
        )
        if entry["owner"] in _HANDS_OFF_TO_HOST and not refs:
            raise MediaError(
                "VIDEO_CAPABILITY_MISSING",
                f"entries[{position}] ('{entry['id']}') hands '{operation}' to "
                f"'{entry['owner']}' without declaring any host capability; the "
                "requirement must name the versioned capability id it depends on",
            )

    declared_operations = set(document["operations"])
    if declared_operations != set(OPERATIONS):
        raise MediaError(
            "VIDEO_BOUNDARY_OPERATION_SET",
            f"operations must be exactly the closed vocabulary; missing="
            f"{sorted(set(OPERATIONS) - declared_operations)} unexpected="
            f"{sorted(declared_operations - set(OPERATIONS))}",
        )
    missing = sorted(set(OPERATIONS) - set(seen))
    if missing:
        raise MediaError(
            "VIDEO_BOUNDARY_OPERATION_UNDECLARED",
            f"no entry declares the operation(s) {missing}",
        )
    return document


def boundary_entries_by_operation(document: Mapping | None = None) -> dict:
    """Lookup table operation -> entry, over a validated document."""
    document = boundary_document() if document is None else validate_boundary(document)
    return {entry["operation"]: entry for entry in document["entries"]}


def assert_within_boundary(request: Mapping, *, document: Mapping | None = None) -> dict:
    """Fail closed when a request asks a side to do the other side's work.

    Returns ``{"allowed": True, "owner": ..., "reason": ...}`` when the request
    matches the boundary, and raises :class:`MediaError` otherwise: an unknown
    operation, an unknown owner and a conflicting owner all fail closed. The
    answer carries the entry's ``host_capability_refs`` so a caller can bind the
    decision to the versioned capability ids it depends on.
    """
    request = require_mapping(request, "request", code="VIDEO_REQUEST_INVALID")
    operation = require_text(
        request.get("operation"), "operation", code="VIDEO_REQUEST_INVALID"
    )
    requested_owner = require_text(
        request.get("requested_owner"), "requested_owner", code="VIDEO_REQUEST_INVALID"
    )
    if requested_owner not in OWNERS:
        raise MediaError(
            "VIDEO_BOUNDARY_OWNER_UNKNOWN",
            f"requested_owner {requested_owner!r} is not one of {OWNERS}",
        )
    entries = boundary_entries_by_operation(document)
    entry = entries.get(operation)
    if entry is None:
        raise MediaError(
            "VIDEO_BOUNDARY_OPERATION_UNKNOWN",
            f"operation {operation!r} is not declared by the boundary document",
        )
    owner = entry["owner"]
    refs = list(entry["host_capability_refs"])
    if owner == "shared":
        return {
            "allowed": True,
            "operation": operation,
            "owner": "shared",
            "requested_owner": requested_owner,
            "host_capability_refs": refs,
            "rule": entry["rule"],
            "reason": (
                f"operation '{operation}' is shared: '{requested_owner}' may act, "
                "but the evidence for it must name the side that produced it"
            ),
        }
    if requested_owner != owner:
        raise MediaError(
            "VIDEO_BOUNDARY_OWNERSHIP_CONFLICT",
            f"operation '{operation}' is owned by '{owner}', not by "
            f"'{requested_owner}': {entry['rule']}",
        )
    return {
        "allowed": True,
        "operation": operation,
        "owner": owner,
        "requested_owner": requested_owner,
        "host_capability_refs": refs,
        "rule": entry["rule"],
        "reason": f"operation '{operation}' is owned by '{owner}' as requested",
    }


#: Claim classes that only a measured host run can support.
_CLAIM_RULES = (
    (
        "frame-accuracy",
        ("frame-accurate", "frame accurate", "frame accuracy", "frame-exact"),
        "a host-live frame-accuracy receipt with a measured frame count and duration",
    ),
    (
        "colour-managed-encode",
        ("colour-managed", "color-managed", "colour managed", "color managed",
         "colourspace", "color space", "colour space"),
        "a host-live colour-managed export receipt naming the applied transform",
    ),
    (
        "hardware-encode",
        ("hardware encode", "hardware-encoded", "gpu encode", "hardware acceleration",
         "gpu acceleration"),
        "a host-live receipt naming the accelerator and its driver version",
    ),
    (
        "rendered-preview",
        ("rendered preview", "render preview", "preview render", "rendered output",
         "rendered frames", "final render"),
        "a host-live render receipt plus the artifact hash read back from disk",
    ),
)


def _classify_claim(claim: str) -> Any:
    lowered = claim.lower()
    for name, tokens, required in _CLAIM_RULES:
        if any(token in lowered for token in tokens):
            return {"name": name, "required": required}
    return None


def unsupported_video_claims(bundle: Mapping) -> list:
    """List the bundle claims that current structural evidence cannot support.

    A claim is supported only by a receipt that is both measured (E2 or higher)
    and referenced as ``host-live:<id>``, in the same claim class. Everything
    else - including a claim class this engine does not recognise - is reported
    as unsupported, because structural evidence (E1) proves contracts, not
    rendered or encoded output.
    """
    bundle = require_mapping(bundle, "bundle", code="VIDEO_BUNDLE_INVALID")
    claims = bundle.get("claims")
    if not isinstance(claims, list) or not claims:
        raise MediaError(
            "VIDEO_CLAIMS_MISSING",
            "bundle must declare a nonempty 'claims' list; an empty bundle "
            "cannot be checked and is refused rather than assumed clean",
        )
    for position, claim in enumerate(claims):
        require_text(claim, f"claims[{position}]", code="VIDEO_BUNDLE_INVALID")

    receipts = bundle.get("host_live_receipts", [])
    if not isinstance(receipts, list):
        raise MediaError("VIDEO_BUNDLE_INVALID", "'host_live_receipts' must be a list")
    measured = []
    for position, receipt in enumerate(receipts):
        receipt = require_mapping(
            receipt, f"host_live_receipts[{position}]", code="VIDEO_BUNDLE_INVALID"
        )
        claim = require_text(
            receipt.get("claim"), f"host_live_receipts[{position}].claim",
            code="VIDEO_BUNDLE_INVALID",
        )
        reference = require_text(
            receipt.get("receipt_ref"), f"host_live_receipts[{position}].receipt_ref",
            code="VIDEO_BUNDLE_INVALID",
        )
        level = require_evidence_level(
            receipt.get("evidence_level"),
            f"host_live_receipts[{position}].evidence_level",
        )
        classified = _classify_claim(claim)
        if (
            classified is not None
            and level in MEASURED_EVIDENCE_LEVELS
            and HOST_EVIDENCE_REFERENCE.match(reference)
        ):
            measured.append(classified["name"])

    unsupported = []
    for claim in claims:
        classified = _classify_claim(claim)
        if classified is None:
            unsupported.append(
                f"{claim}: unrecognised claim class; structural evidence cannot "
                f"verify it ({NOT_EXECUTED})"
            )
        elif classified["name"] not in measured:
            unsupported.append(
                f"{claim}: requires {classified['required']}; this build has only "
                f"E1 structural evidence ({NOT_EXECUTED})"
            )
    return unsupported
