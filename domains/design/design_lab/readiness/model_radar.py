# SPDX-License-Identifier: MIT
"""DL-P1-100: candidate model radar (registry + fail-closed resolver).

Module boundary: this module owns the *registry contract* for candidate models
(image/video generation, upscaling, segmentation, OCR, ASR, TTS, 3D) and the
resolver that a runtime must consult before touching one. It reads only the
registry document: no download, no cache probe, no load, no inference, no GPU.
`machine_state` reuses the `design_lab.analysis.model_manifest` stage vocabulary
rather than inventing a parallel one, and every local claim cites the existing
external-asset registry (`design-lab/config/external-assets-index.json`) or a
recorded inventory path instead of creating a second registry.

Fail-closed rules added here (not present elsewhere in the repository):
  * `default_enabled` may only be true for `radar_state == "QUALIFIED_LOCAL"`,
    and such an entry must additionally reach `machine_state` >= `LOAD_VERIFIED`
    with a nonzero recorded weight hash;
  * no entry may claim `INFERENCE_VERIFIED` without a non-empty evidence
    reference;
  * a `BLOCKED_BY_LICENSE` entry may never be `default_enabled` and may not
    carry `hardware_fit.verdict == "FITS"` (which would read as readiness);
  * `resolve()` refuses unknown, unqualified, licence-blocked, and
    hardware-exceeding models with a distinct message per reason.

The licence question for the local MiniMax H3 components is NOT decided here:
they are recorded as `BLOCKED_BY_LICENSE` with `commercial_use: "UNKNOWN"` and
the adjudication is left to the project owner.
"""
from __future__ import annotations


from jsonschema import Draft202012Validator

from ..runtime.state_resources import repo_resource
from . import ReadinessError

TASK_ID = "DL-P1-100"
SCHEMA_VERSION = "design-lab/readiness-model-radar/v1"
SCHEMA_PATH = repo_resource('schemas/readiness-model-radar.schema.json')
REGISTRY_PATH = repo_resource('readiness/model-radar.json')
EXTERNAL_ASSETS_REF = "design-lab/config/external-assets-index.json"
INVENTORY_REF = "reports/current/MACHINE_INVENTORY.json"

#: Reused verbatim from design_lab.analysis.model_manifest.STAGES.
MACHINE_STATES = ("ABSENT", "METADATA_ONLY", "WEIGHTS_COMPLETE", "LOAD_VERIFIED", "INFERENCE_VERIFIED")
RADAR_STATES = ("WATCH", "EVALUATING", "QUALIFIED_LOCAL", "REJECTED", "BLOCKED_BY_LICENSE")
HARDWARE_VERDICTS = ("FITS", "TIGHT", "EXCEEDS", "UNKNOWN")
COMMERCIAL_USE = ("PERMITTED", "RESTRICTED", "UNKNOWN")
QUALIFIED = "QUALIFIED_LOCAL"
BLOCKED = "BLOCKED_BY_LICENSE"
ZERO_HASH = "0" * 64
#: Resolution refusal codes, one per distinct reason.
REFUSAL_UNKNOWN = "UNKNOWN_MODEL"
REFUSAL_UNQUALIFIED = "UNQUALIFIED_RADAR_STATE"
REFUSAL_LICENSE = "BLOCKED_BY_LICENSE"
REFUSAL_HARDWARE = "HARDWARE_EXCEEDS"


def _document(path, label: str) -> dict:
    from .host_matrix import load_document

    document = load_document(path)
    if not isinstance(document, dict):
        raise ReadinessError(f"{label} must be a JSON object")
    return document


def validate_registry(document, *, schema_path=None) -> dict:
    """Schema-validate the radar registry and enforce the readiness rules.

    Returns the document unchanged on success; raises `ReadinessError` listing
    every violation on failure. Never invents a hash, licence, or machine fact.
    """
    if not isinstance(document, dict):
        raise ReadinessError("model radar registry must be a JSON object")
    schema = _document(SCHEMA_PATH if schema_path is None else schema_path, "model radar schema")
    errors = sorted(Draft202012Validator(schema).iter_errors(document),
                    key=lambda error: list(error.absolute_path))
    if errors:
        rendered = [f"{'/'.join(str(part) for part in error.absolute_path) or '<root>'}: {error.message}"
                    for error in errors]
        raise ReadinessError("model radar schema violation: " + "; ".join(rendered[:8]))
    if document.get("schema_version") != SCHEMA_VERSION:
        raise ReadinessError(f"model radar schema_version must be {SCHEMA_VERSION}")

    ceiling = document["hardware"]["available_vram_mib"]
    seen: set = set()
    for entry in document["entries"]:
        model_id = entry["model_id"]
        if model_id in seen:
            raise ReadinessError(f"duplicate model_id in radar registry: {model_id}")
        seen.add(model_id)
        state = entry["radar_state"]
        machine = entry["machine_state"]
        fit = entry["hardware_fit"]
        verdict = fit["verdict"]
        required = fit.get("vram_gib_required")

        hashes = entry.get("weights_sha256") or []
        for digest in hashes:
            if digest == ZERO_HASH:
                raise ReadinessError(f"{model_id}: zero weight hash is not evidence")
        if entry.get("default_enabled") and state != QUALIFIED:
            raise ReadinessError(
                f"{model_id}: default_enabled requires radar_state == {QUALIFIED}, found {state!r}")
        if state == QUALIFIED:
            if MACHINE_STATES.index(machine) < MACHINE_STATES.index("LOAD_VERIFIED"):
                raise ReadinessError(
                    f"{model_id}: {QUALIFIED} requires machine_state >= LOAD_VERIFIED, found {machine!r}")
            if not hashes:
                raise ReadinessError(
                    f"{model_id}: {QUALIFIED} requires a nonzero recorded weight hash; none is recorded for this "
                    "machine, so the entry cannot be qualified from this repository")
            if not (entry.get("qualified_by") or "").strip():
                raise ReadinessError(f"{model_id}: {QUALIFIED} requires qualified_by (who qualified it)")
        if machine == "INFERENCE_VERIFIED" and not (entry.get("evidence_ref") or "").strip():
            raise ReadinessError(f"{model_id}: INFERENCE_VERIFIED requires a non-empty evidence_ref")
        if state == BLOCKED:
            if entry.get("default_enabled"):
                raise ReadinessError(f"{model_id}: {BLOCKED} entries may not be default_enabled")
            if verdict == "FITS":
                raise ReadinessError(
                    f"{model_id}: {BLOCKED} may not carry a FITS hardware verdict, which would read as readiness")
            if entry["rights"]["commercial_use"] == "PERMITTED":
                raise ReadinessError(
                    f"{model_id}: {BLOCKED} conflicts with commercial_use PERMITTED; adjudicate before re-labelling")
            if not (entry.get("blocking_reason") or "").strip():
                raise ReadinessError(f"{model_id}: {BLOCKED} requires blocking_reason")

        if verdict == "UNKNOWN":
            # An unmeasured fit may still carry the declared requirement; it may
            # never carry a FITS/TIGHT/EXCEEDS judgement it did not earn.
            if required is not None and (isinstance(required, bool) or not isinstance(required, int)
                                         or required <= 0):
                raise ReadinessError(
                    f"{model_id}: declared vram_gib_required must be a positive integer or null")
        else:
            if not isinstance(required, int) or isinstance(required, bool) or required <= 0:
                raise ReadinessError(
                    f"{model_id}: a {verdict} verdict requires a positive integer vram_gib_required")
            required_mib = required * 1024
            if verdict == "FITS" and required_mib > ceiling:
                raise ReadinessError(
                    f"{model_id}: FITS contradicts the declared ceiling of {ceiling} MiB")
            if verdict == "EXCEEDS" and required_mib <= ceiling:
                raise ReadinessError(
                    f"{model_id}: EXCEEDS contradicts the declared ceiling of {ceiling} MiB; use FITS or TIGHT")
        if machine == "ABSENT" and entry.get("local_path"):
            raise ReadinessError(f"{model_id}: ABSENT entries may not record a local_path")
        if machine != "ABSENT" and not entry.get("local_path"):
            raise ReadinessError(f"{model_id}: a present machine_state requires a local_path reference")
        if entry["source"]["kind"] == "local" and not entry.get("local_path"):
            raise ReadinessError(f"{model_id}: local source requires a local_path reference")
    return document


def load_registry(path=None) -> dict:
    """Load and validate the repository radar registry; fail closed on either step."""
    return validate_registry(_document(REGISTRY_PATH if path is None else path, "model radar registry"))


def resolve(registry: dict, model_id: str):
    """Resolve one model for runtime use, or refuse with a reason-specific error.

    Refusal codes: UNKNOWN_MODEL, UNQUALIFIED_RADAR_STATE, BLOCKED_BY_LICENSE,
    HARDWARE_EXCEEDS. The returned mapping is detached from the registry.
    """
    if not isinstance(model_id, str) or not model_id.strip():
        raise ReadinessError(f"{REFUSAL_UNKNOWN}: model_id must be a non-empty string")
    matches = [entry for entry in registry["entries"] if entry["model_id"] == model_id]
    if not matches:
        raise ReadinessError(f"{REFUSAL_UNKNOWN}: no radar entry for {model_id!r}; nothing may be loaded")
    entry = matches[0]
    state = entry["radar_state"]
    if state == BLOCKED:
        raise ReadinessError(
            f"{REFUSAL_LICENSE}: {model_id} is BLOCKED_BY_LICENSE ({entry.get('blocking_reason', '')}); "
            "licence adjudication is the project owner's decision and default_enabled must stay false")
    if state != QUALIFIED:
        raise ReadinessError(
            f"{REFUSAL_UNQUALIFIED}: {model_id} radar_state is {state!r}, not {QUALIFIED}; no runtime may use it")
    verdict = entry["hardware_fit"]["verdict"]
    if verdict == "EXCEEDS":
        raise ReadinessError(
            f"{REFUSAL_HARDWARE}: {model_id} hardware_fit is EXCEEDS "
            f"({entry['hardware_fit']['vram_gib_required']} GiB required); declared ceiling is "
            f"{registry['hardware']['available_vram_mib']} MiB")
    if verdict == "UNKNOWN":
        raise ReadinessError(
            f"{REFUSAL_HARDWARE}: {model_id} hardware_fit is UNKNOWN; an unmeasured fit may not be loaded")
    return {"model_id": model_id, "family": entry["family"], "machine_state": entry["machine_state"],
            "hardware_fit": dict(entry["hardware_fit"]), "source": dict(entry["source"]),
            "rights": dict(entry["rights"]), "local_path": entry.get("local_path"),
            "weights_sha256": list(entry.get("weights_sha256") or [])}


def radar_report(registry: dict) -> dict:
    """Counts by radar/machine state plus the explicit refusal list."""
    entries = registry["entries"]
    by_radar = {state: 0 for state in RADAR_STATES}
    by_machine = {state: 0 for state in MACHINE_STATES}
    refused = []
    for entry in entries:
        by_radar[entry["radar_state"]] += 1
        by_machine[entry["machine_state"]] += 1
        reasons = []
        if entry["radar_state"] == BLOCKED:
            reasons.append(REFUSAL_LICENSE)
        elif entry["radar_state"] != QUALIFIED:
            reasons.append(REFUSAL_UNQUALIFIED)
        if entry["hardware_fit"]["verdict"] in ("EXCEEDS", "UNKNOWN"):
            reasons.append(REFUSAL_HARDWARE)
        if reasons:
            refused.append({"model_id": entry["model_id"], "radar_state": entry["radar_state"],
                            "machine_state": entry["machine_state"],
                            "hardware_verdict": entry["hardware_fit"]["verdict"],
                            "refusal_codes": reasons})
    return {
        "task_id": TASK_ID,
        "entries_total": len(entries),
        "by_radar_state": by_radar,
        "by_machine_state": by_machine,
        "default_enabled": [entry["model_id"] for entry in entries if entry["default_enabled"]],
        "refused_by_resolver": refused,
        "licence_adjudication_pending": [entry["model_id"] for entry in entries
                                         if entry["radar_state"] == BLOCKED],
        "available_vram_mib": registry["hardware"]["available_vram_mib"],
        "network_used": "NONE",
        "inference_executed": "NONE",
    }
