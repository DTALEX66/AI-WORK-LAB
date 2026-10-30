# SPDX-License-Identifier: MIT
"""DL-P0-160: delivery provenance projected onto a C2PA 2.4 claim structure.

What this module is, and what it is not
---------------------------------------
It maps a DESIGN-LAB delivery record onto the structure of a C2PA 2.4 manifest
(``C2PA_SPEC_VERSION = "2.4"``): the 2.x claim structure
``CLAIM_VERSION = "c2pa.claim.v2"``, the reserved signature assertion label
``SIGNATURE_ASSERTION = "c2pa.signature"``, ``claim_generator``, ``assertions``
carrying ``c2pa.actions``, one ``c2pa.ingredient`` per declared input, and
``c2pa.creative-work`` / ``c2pa.training-mining`` where the rights profile
requires them. The manifest names ``c2pa.claim.v2`` and ``c2pa.signature`` so a
later signing pipeline has the exact labels to work with; it carries no signature
*material* and no ``c2pa.signature`` assertion.

The DESIGN-LAB Asset Graph stays the source of truth
----------------------------------------------------
The delivery record -- deliverable identity, artifact digest, producer, lineage
inputs and rights profile -- is DESIGN-LAB's internal Asset Graph, and it is the
**source**. The C2PA document is a *projection* of it: a read-only rendering for
interchange. C2PA never replaces the Asset Graph here -- nothing in this module
writes back into the delivery record, no field of the manifest is authoritative
over it, and :func:`build_manifest` is a pure function from the delivery record to
the projection (``design_lab.projection_of`` records that direction in every
manifest).

**It never signs, never embeds and never claims that a signed asset exists.**
``SIGNING_STATUS = "UNSIGNED_STRUCTURAL_ONLY"`` is written into every manifest and
enforced on every read. :func:`sign` exists only to fail closed with the exact
list of what is missing. Provenance *structure* is the deliverable here; the
signing step (a C2PA signing library, a certificate chain and a private key) plus
embedding into the asset file belong to a release pipeline that DESIGN-LAB has not
run -- and no part of this module has run it either.

Two documented deviations from a signed C2PA manifest, both deliberate
----------------------------------------------------------------------
1. The ingredient hash is carried in DESIGN-LAB's canonical ``sha256:<64 hex>``
   form under ``sha256``. Translating it into the C2PA assertion's binary
   ``c2pa.hash.data`` structure is a signing-library concern, and inventing that
   shape without running a signing library would be guesswork. :func:`sign` names
   this in its failure message.
2. ``format`` carries DESIGN-LAB's asset kind (``raster``, ``vector``, ...) rather
   than a MIME type, because DESIGN-LAB does not own that mapping.

Boundary: JSON in, JSON out. No network, no process, no file write, no signature.
All evidence reachable from this module is E1 (STRUCTURAL).
"""
from __future__ import annotations

from datetime import datetime

from ..runtime.attempt_contract import canonical_hash, request_hash
from ..runtime.state_resources import repo_resource
from . import InteropError, load_schema, schema_errors

C2PA_SPEC_VERSION = "2.4"
#: C2PA 2.x claim structure label this module builds (the v1 ``c2pa.claim`` is not used).
CLAIM_VERSION = "c2pa.claim.v2"
#: The reserved C2PA signature assertion label. The manifest *names* it so a signing
#: pipeline knows where the signature goes; it never carries the assertion itself.
SIGNATURE_ASSERTION = "c2pa.signature"
SIGNING_STATUS = "UNSIGNED_STRUCTURAL_ONLY"
#: DESIGN-LAB's internal lineage structure. The C2PA document is a projection of it,
#: never a replacement for it.
SOURCE_OF_TRUTH = "design-lab-asset-graph"
TASK_ID = "DL-P0-160"

SCHEMA_PATH = repo_resource('schemas/interop-c2pa-manifest.schema.json')
SCHEMA_REPOSITORY_PATH = 'design-lab/schemas/interop-c2pa-manifest.schema.json'

ASSERTION_ACTIONS = "c2pa.actions"
ASSERTION_INGREDIENT = "c2pa.ingredient"
ASSERTION_CREATIVE_WORK = "c2pa.creative-work"
ASSERTION_TRAINING_MINING = "c2pa.training-mining"
ASSERTION_LABELS = (
    ASSERTION_ACTIONS,
    ASSERTION_INGREDIENT,
    ASSERTION_CREATIVE_WORK,
    ASSERTION_TRAINING_MINING,
)

#: The C2PA action values DESIGN-LAB maps onto. Any other value fails closed.
ACTION_VALUES = ("c2pa.created", "c2pa.edited", "c2pa.placed")
INGREDIENT_RELATIONSHIPS = ("parentOf", "componentOf", "inputTo")
TRAINING_ENTRIES = (
    "c2pa.ai_training",
    "c2pa.ai_generative_training",
    "c2pa.ai_inference",
    "c2pa.ai_model_training",
)
TRAINING_USES = ("allowed", "notAllowed", "constrained")

CLAIM_GENERATOR = (
    "DESIGN-LAB interop.provenance (C2PA " + C2PA_SPEC_VERSION +
    " structural mapping; no signing library; " + SIGNING_STATUS + ")"
)

#: Fields that would only exist on a signed manifest. Their presence fails closed.
#: ``signature`` is deliberately *not* listed here: in this projection that key names
#: the reserved assertion label (:data:`SIGNATURE_ASSERTION`) and carries no material,
#: and :func:`assert_not_a_signed_asset` checks its value instead.
SIGNATURE_MATERIAL_FIELDS = (
    "signature_info",
    "claim_signature",
    "signing_credential",
    "certificate",
    "x5chain",
    "private_key",
)

#: Rights-profile presets. ``training`` maps every C2PA training entry to a use.
RIGHTS_PROFILES = {
    "all-rights-reserved": {"creative_work": True,
                            "training": {entry: "notAllowed" for entry in TRAINING_ENTRIES}},
    "attribution-required": {"creative_work": True,
                             "training": {entry: "notAllowed" for entry in TRAINING_ENTRIES}},
    "open-license": {"creative_work": True,
                     "training": {entry: "allowed" for entry in TRAINING_ENTRIES}},
    "internal-review-only": {"creative_work": True,
                             "training": {entry: "notAllowed" for entry in TRAINING_ENTRIES}},
    "no-rights-declared": {"creative_work": False, "training": None},
}


def _fail(message: str) -> "InteropError":
    return InteropError(message)


def _text(value, where: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise _fail(f"{where} must be a nonempty string")
    return value


def _digest(value, where: str) -> str:
    try:
        return canonical_hash(value)
    except ValueError as exc:
        raise _fail(f"{where}: {exc}") from exc


def _when(value, where: str) -> str:
    text = _text(value, where)
    try:
        datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError as exc:
        raise _fail(f"{where} must be an ISO-8601 timestamp; got {text!r}") from exc
    return text


def _schema_errors(document) -> list[str]:
    return schema_errors(load_schema(SCHEMA_PATH), document)


# --------------------------------------------------------------------------- #
# delivery -> manifest
# --------------------------------------------------------------------------- #

def _normalize_rights(rights_profile) -> dict:
    """Normalize a rights profile into ``{"label", "creative_work", "training", ...}``."""
    if isinstance(rights_profile, str):
        preset = RIGHTS_PROFILES.get(rights_profile)
        if preset is None:
            raise _fail(
                f"unknown rights_profile {rights_profile!r}; known profiles are: "
                + ", ".join(sorted(RIGHTS_PROFILES))
                + ". Pass a mapping with explicit 'creative_work' and 'training' keys instead."
            )
        return {
            "label": rights_profile,
            "creative_work": preset["creative_work"],
            "training": (None if preset["training"] is None else dict(preset["training"])),
            "copyright": None,
            "author": None,
        }
    if not isinstance(rights_profile, dict) or not rights_profile:
        raise _fail(
            "rights_profile must be a profile name or a nonempty mapping; an undeclared rights "
            "profile cannot be mapped onto C2PA assertions"
        )
    label = rights_profile.get("profile")
    if label is not None:
        _text(label, "rights_profile.profile")
    creative_work = rights_profile.get("creative_work")
    if creative_work is None:
        raise _fail(
            "rights_profile.creative_work must state whether a c2pa.creative-work assertion is "
            "required; DESIGN-LAB does not guess a rights obligation"
        )
    if not isinstance(creative_work, bool):
        raise _fail("rights_profile.creative_work must be a boolean")
    training = rights_profile.get("training")
    if training is not None:
        if not isinstance(training, dict) or not training:
            raise _fail("rights_profile.training must be a nonempty mapping of C2PA training entries")
        for entry, use in training.items():
            if entry not in TRAINING_ENTRIES:
                raise _fail(
                    f"rights_profile.training entry {entry!r} is not a C2PA training entry; "
                    "expected one of " + ", ".join(TRAINING_ENTRIES)
                )
            if use not in TRAINING_USES:
                raise _fail(
                    f"rights_profile.training[{entry!r}] must be one of {', '.join(TRAINING_USES)}"
                )
    author = rights_profile.get("author")
    if author is not None:
        if isinstance(author, str):
            author = {"@type": "Person", "name": _text(author, "rights_profile.author")}
        elif isinstance(author, dict):
            author = {"@type": author.get("@type", "Person"),
                      "name": _text(author.get("name"), "rights_profile.author.name")}
        else:
            raise _fail("rights_profile.author must be a name or a mapping with a name")
    copyright_text = rights_profile.get("copyright")
    if copyright_text is not None:
        copyright_text = _text(copyright_text, "rights_profile.copyright")
    return {
        "label": label or "explicit",
        "creative_work": creative_work,
        "training": None if training is None else dict(training),
        "copyright": copyright_text,
        "author": author,
    }


def _normalize_delivery(delivery) -> dict:
    if not isinstance(delivery, dict):
        raise _fail("delivery record must be an object")
    deliverable_id = _text(delivery.get("deliverable_id"), "delivery.deliverable_id")
    artifact = _digest(delivery.get("artifact_sha256"), "delivery.artifact_sha256")
    asset_kind = _text(delivery.get("asset_kind"), "delivery.asset_kind")
    producer = delivery.get("producer")
    if not isinstance(producer, dict):
        raise _fail("delivery.producer must be an object")
    producer_id = _text(producer.get("provider_id"), "delivery.producer.provider_id")
    model_id = producer.get("model_id")
    if model_id is not None:
        model_id = _text(model_id, "delivery.producer.model_id")
    normalized_producer = {
        "operation_id": _text(producer.get("operation_id"), "delivery.producer.operation_id"),
        "provider_id": producer_id,
        "model_id": model_id,
    }
    created_at = delivery.get("created_at")
    if created_at is not None:
        created_at = _when(created_at, "delivery.created_at")

    inputs = delivery.get("inputs", [])
    if not isinstance(inputs, list):
        raise _fail("delivery.inputs must be an array (empty when nothing was consumed)")
    normalized_inputs = []
    seen_versions: set[str] = set()
    for index, entry in enumerate(inputs):
        where = f"delivery.inputs[{index}]"
        if not isinstance(entry, dict):
            raise _fail(f"{where} must be an object")
        version_id = _text(entry.get("version_id"), f"{where}.version_id")
        if version_id in seen_versions:
            raise _fail(
                f"{where}.version_id {version_id!r} is declared twice; every input version must map "
                "to exactly one ingredient assertion"
            )
        seen_versions.add(version_id)
        relationship = entry.get("relationship", "inputTo")
        if relationship not in INGREDIENT_RELATIONSHIPS:
            raise _fail(
                f"{where}.relationship must be one of {', '.join(INGREDIENT_RELATIONSHIPS)}; "
                f"got {relationship!r}"
            )
        normalized_inputs.append({
            "version_id": version_id,
            "sha256": _digest(entry.get("sha256"), f"{where}.sha256"),
            "relationship": relationship,
        })

    actions = delivery.get("actions")
    if not isinstance(actions, list) or not actions:
        raise _fail("delivery.actions must be a nonempty array; a manifest without an action is empty")
    normalized_actions = []
    for index, entry in enumerate(actions):
        where = f"delivery.actions[{index}]"
        if not isinstance(entry, dict):
            raise _fail(f"{where} must be an object")
        action = entry.get("action")
        if action not in ACTION_VALUES:
            raise _fail(f"{where}.action must be one of {', '.join(ACTION_VALUES)}; got {action!r}")
        software_agent = entry.get("software_agent")
        if software_agent is not None:
            software_agent = _text(software_agent, f"{where}.software_agent")
        normalized_actions.append({
            "action": action,
            "when": _when(entry.get("when"), f"{where}.when"),
            "softwareAgent": software_agent or CLAIM_GENERATOR,
        })

    return {
        "deliverable_id": deliverable_id,
        "artifact_sha256": artifact,
        "asset_kind": asset_kind,
        "producer": normalized_producer,
        "inputs": normalized_inputs,
        "actions": normalized_actions,
        "created_at": created_at,
        "rights": _normalize_rights(delivery.get("rights_profile")),
    }


def build_manifest(delivery) -> dict:
    """Project a DESIGN-LAB delivery record onto a C2PA 2.4 claim structure.

    The delivery record is the source: this is a pure function of it onto the C2PA
    shape (``claim_version = c2pa.claim.v2``, the reserved signature assertion label
    ``c2pa.signature``), and nothing is written back into the delivery record. C2PA
    does not replace the internal Asset Graph.

    Returns an **unsigned** structure: ``signing_status`` is
    ``UNSIGNED_STRUCTURAL_ONLY``, ``signature`` only *names* the assertion a signing
    pipeline would produce, there is no signature material, no ``c2pa.signature``
    assertion and nothing is embedded into the artifact. The result is deterministic
    -- the same delivery always produces the same manifest and therefore the same
    :func:`manifest_digest`.
    """
    record = _normalize_delivery(delivery)
    inputs = record["inputs"]
    rights = record["rights"]

    instance_seed = request_hash({
        "deliverable_id": record["deliverable_id"],
        "artifact_sha256": record["artifact_sha256"],
    })
    assertions: list[dict] = [{
        "label": ASSERTION_ACTIONS,
        "data": {"actions": [dict(action) for action in record["actions"]]},
    }]
    for entry in inputs:
        assertions.append({
            "label": ASSERTION_INGREDIENT,
            "data": {
                "relationship": entry["relationship"],
                "dc:title": entry["version_id"],
                "instanceID": entry["version_id"],
                "sha256": entry["sha256"],
            },
        })
    if rights["creative_work"]:
        creative: dict = {
            "@context": "https://schema.org",
            "@type": "CreativeWork",
            "name": record["deliverable_id"],
            "dateCreated": record["created_at"] or record["actions"][0]["when"],
        }
        if rights["copyright"]:
            creative["copyright"] = rights["copyright"]
        if rights["author"]:
            creative["author"] = [dict(rights["author"])]
        assertions.append({"label": ASSERTION_CREATIVE_WORK, "data": creative})
    if rights["training"]:
        assertions.append({
            "label": ASSERTION_TRAINING_MINING,
            "data": {
                "entries": {entry: {"use": rights["training"][entry]}
                            for entry in sorted(rights["training"])}
            },
        })

    return {
        "claim_generator": CLAIM_GENERATOR,
        "c2pa_spec_version": C2PA_SPEC_VERSION,
        "claim_version": CLAIM_VERSION,
        "signing_status": SIGNING_STATUS,
        "signature": SIGNATURE_ASSERTION,
        "title": record["deliverable_id"],
        "format": record["asset_kind"],
        "instance_id": "xmp:iid:" + instance_seed.removeprefix("sha256:")[:32],
        "assertions": assertions,
        "design_lab": {
            "task_id": TASK_ID,
            "deliverable_id": record["deliverable_id"],
            "artifact_sha256": record["artifact_sha256"],
            "rights_profile": rights["label"],
            "producer": dict(record["producer"]),
            "input_count": len(inputs),
            "projection_of": SOURCE_OF_TRUTH,
        },
    }


# --------------------------------------------------------------------------- #
# validation
# --------------------------------------------------------------------------- #

def assert_not_a_signed_asset(manifest) -> dict:
    """Guard: refuse to treat anything as a signed asset.

    Raises :class:`InteropError` when the manifest

    * claims a signing state other than ``UNSIGNED_STRUCTURAL_ONLY``;
    * carries a ``signature`` value other than the reserved label
      :data:`SIGNATURE_ASSERTION` (``c2pa.signature``) -- naming the label is a
      declaration of where a signature would go, any other value is signature
      material;
    * carries a signature-material field (``signature_info``, ``claim_signature``,
      ``signing_credential``, ``certificate``, ``x5chain``, ``private_key``); or
    * carries an assertion labelled ``c2pa.signature``, which would be the signature
      block of a signed manifest.

    Returns the manifest unchanged when it is clean. Docstring of every public
    function in this module carries the same promise: nothing here signs.
    """
    if not isinstance(manifest, dict):
        raise _fail("manifest must be an object")
    status = manifest.get("signing_status")
    if status != SIGNING_STATUS:
        raise _fail(
            f"manifest signing_status must be {SIGNING_STATUS!r}; found {status!r}. DESIGN-LAB has "
            "no C2PA signing run and must not present a manifest as a signed asset"
        )
    declared = manifest.get("signature")
    if declared is not None and declared != SIGNATURE_ASSERTION:
        raise _fail(
            f"manifest.signature must name the reserved signature assertion "
            f"{SIGNATURE_ASSERTION!r} and carry no signature material; found {declared!r}. This "
            "module builds unsigned provenance structure only and never signs or embeds"
        )
    present = sorted(field for field in SIGNATURE_MATERIAL_FIELDS if field in manifest)
    if present:
        raise _fail(
            "manifest carries signature material (" + ", ".join(present) + "); this module builds "
            "unsigned provenance structure only and never signs or embeds"
        )
    assertions = manifest.get("assertions")
    if isinstance(assertions, list):
        for index, assertion in enumerate(assertions):
            if isinstance(assertion, dict) and assertion.get("label") == SIGNATURE_ASSERTION:
                raise _fail(
                    f"assertions[{index}] carries a {SIGNATURE_ASSERTION!r} assertion; a manifest "
                    "with a signature block is a signed manifest and DESIGN-LAB has not run a "
                    "signing pipeline"
                )
    return manifest


def sign(*_args, **_kwargs):
    """Always fails closed: DESIGN-LAB cannot sign a C2PA manifest.

    Named blockers: no C2PA signing library (``c2pa``/``c2patool``) is available to
    this interpreter, no signing certificate chain and no private key are
    configured in this repository, and no host/release pipeline has been given a
    signing mandate. The manifest stays ``UNSIGNED_STRUCTURAL_ONLY``; signing and
    embedding into the asset file must happen in that pipeline.
    """
    raise InteropError(
        "C2PA signing is not implemented in DESIGN-LAB and no signed asset exists: missing a C2PA "
        "signing library (c2pa / c2patool), a signing certificate chain and a private key, plus an "
        "approved release-pipeline mandate. provenance.py builds the unsigned structure only "
        f"(SIGNING_STATUS={SIGNING_STATUS}, CLAIM_VERSION={CLAIM_VERSION}); the "
        f"{SIGNATURE_ASSERTION!r} assertion a signing pipeline would produce is only named here, and "
        "embedding into the asset file is out of scope."
    )


def validate_manifest(manifest, *, expected_inputs=None) -> dict:
    """Validate a C2PA-shaped manifest; return a structural report.

    Checks the structural schema, the action enum, ingredient relationships,
    ``sha256:<64 hex>`` nonzero ingredient digests, one ingredient assertion per
    input version (exactly one, no extras), the 2.x baseline labels
    (``claim_version = c2pa.claim.v2`` and the reserved ``c2pa.signature``
    assertion label, enforced by the schema and by
    :func:`assert_not_a_signed_asset`) and that nothing claims to be signed.
    ``expected_inputs`` is the delivery's input list (version ids or input
    mappings); when supplied, ingredient coverage is checked exhaustively.
    """
    assert_not_a_signed_asset(manifest)
    problems = _schema_errors(manifest)
    if problems:
        raise InteropError(f"manifest violates {SCHEMA_PATH.name}: " + "; ".join(problems))

    actions = 0
    ingredients: dict[str, str] = {}
    creative_work = 0
    training_entries = 0
    for index, assertion in enumerate(manifest["assertions"]):
        where = f"assertions[{index}]"
        label = assertion["label"]
        data = assertion["data"]
        if label == ASSERTION_ACTIONS:
            for action_index, action in enumerate(data["actions"]):
                if action["action"] not in ACTION_VALUES:
                    raise _fail(
                        f"{where}.data.actions[{action_index}].action must be one of "
                        + ", ".join(ACTION_VALUES) + f"; got {action['action']!r}"
                    )
                actions += 1
        elif label == ASSERTION_INGREDIENT:
            relationship = data["relationship"]
            if relationship not in INGREDIENT_RELATIONSHIPS:
                raise _fail(
                    f"{where}.data.relationship must be one of "
                    + ", ".join(INGREDIENT_RELATIONSHIPS) + f"; got {relationship!r}"
                )
            _digest(data["sha256"], f"{where}.data.sha256")
            version = _text(data.get("instanceID", data.get("dc:title")),
                            f"{where}.data.instanceID")
            if version in ingredients:
                raise _fail(
                    f"input version {version!r} has more than one ingredient assertion "
                    f"({ingredients[version]} and {where}); every input produces exactly one"
                )
            ingredients[version] = where
        elif label == ASSERTION_CREATIVE_WORK:
            creative_work += 1
        elif label == ASSERTION_TRAINING_MINING:
            for entry, payload in data["entries"].items():
                if entry not in TRAINING_ENTRIES:
                    raise _fail(f"{where}.data.entries has unknown entry {entry!r}")
                if payload["use"] not in TRAINING_USES:
                    raise _fail(
                        f"{where}.data.entries[{entry!r}].use must be one of "
                        + ", ".join(TRAINING_USES)
                    )
                training_entries += 1

    if actions == 0:
        raise _fail("manifest has no c2pa.actions assertion; provenance without an action is empty")

    if expected_inputs is not None:
        if not isinstance(expected_inputs, (list, tuple)):
            raise _fail("expected_inputs must be a sequence of version ids or input mappings")
        declared = []
        for index, entry in enumerate(expected_inputs):
            value = entry.get("version_id") if isinstance(entry, dict) else entry
            declared.append(_text(value, f"expected_inputs[{index}]"))
        if len(set(declared)) != len(declared):
            raise _fail("expected_inputs declares the same version twice")
        missing = sorted(set(declared) - set(ingredients))
        extra = sorted(set(ingredients) - set(declared))
        if missing or extra:
            raise _fail(
                "ingredient coverage does not match the delivery inputs; missing: "
                f"{missing or 'none'}, unexpected: {extra or 'none'}"
            )

    return {
        "schemaVersion": manifest["c2pa_spec_version"],
        "schema_path": SCHEMA_REPOSITORY_PATH,
        "claim_version": manifest["claim_version"],
        "signature_assertion": manifest["signature"],
        "projection_of": manifest["design_lab"]["projection_of"],
        "signing_status": SIGNING_STATUS,
        "signed": False,
        "action_count": actions,
        "ingredient_count": len(ingredients),
        "ingredient_versions": sorted(ingredients),
        "creative_work_assertions": creative_work,
        "training_entries": training_entries,
        "manifest_sha256": manifest_digest(manifest),
    }


def manifest_digest(manifest) -> str:
    """Order-independent digest of the manifest structure (never of a signature)."""
    if not isinstance(manifest, dict):
        raise _fail("manifest must be an object")
    try:
        return request_hash(manifest)
    except (TypeError, ValueError) as exc:
        raise _fail(f"manifest is not canonical JSON: {exc}") from exc
