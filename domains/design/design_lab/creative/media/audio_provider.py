# SPDX-License-Identifier: MIT
"""DL-P1-140: audio pipeline provider contract (ASR / TTS / SFX / music).

Declares the provider lifecycle, the capability table, the local external model
registry and the evidence contract that a future audio stage must satisfy. It
does NOT ship, download or bundle a model, does NOT run inference of any kind,
does NOT touch a GPU, does NOT read or write a transcript, and does NOT verify
a model file's bytes. ``execute()`` therefore always fails closed, and every
capability is ``supported: false`` at evidence level E1 (STRUCTURAL) until a
caller supplies a measured host-live receipt. Models are *local external
assets*: they are identified by an alias key, never by an absolute user path.

Models are only ``QUALIFIED`` after a host-live qualification receipt exists;
``resolve_audio_model`` refuses everything else (unknown, unqualified, zero
hash, unknown alias, missing file, license conflict).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
import re
from typing import Any, Iterable, Mapping

from ...adapters.spi import ProviderAdapter
from ...runtime.attempt_contract import request_hash
from . import (
    HOST_EVIDENCE_PREFIX,
    HOST_EVIDENCE_REFERENCE,
    MEASURED_EVIDENCE_LEVELS,
    MediaError,
    NOT_EXECUTED,
    STRUCTURAL_EVIDENCE,
    normalize_sha256,
    reject_absolute_paths,
    require_evidence_level,
    require_mapping,
    require_text,
    validate_against,
)

__all__ = [
    "ADAPTER_ID",
    "ADAPTER_VERSION",
    "AUDIO_STAGES",
    "AudioJobRecord",
    "AudioModelRegistry",
    "AudioProvider",
    "QUALIFICATION_STATES",
    "UNQUALIFIED_DECLARED",
    "evidence_requirements",
    "resolve_audio_model",
]

ADAPTER_ID = "design-lab.audio-provider.structural"
ADAPTER_VERSION = "0.1.0-structural-e1"

#: The three capability families required by DL-P1-140. ``sfx`` and ``music``
#: are the two generation stages; both are declared separately because a future
#: model will almost certainly qualify for one and not the other.
AUDIO_STAGES = ("asr", "tts", "sfx", "music")
GENERATION_STAGES = ("sfx", "music")

UNQUALIFIED_DECLARED = "UNQUALIFIED_DECLARED"
QUALIFICATION_STATES = (
    "UNQUALIFIED_DECLARED",
    "UNQUALIFIED_NOT_INSTALLED",
    "UNQUALIFIED_CHECKSUM",
    "DISABLED_LICENSE_CONFLICT",
    "QUALIFIED",
)

#: A path alias key: a bare name, never a path. Mirrors the alias vocabulary of
#: ``.project/paths.json`` ``shared_inputs``.
_ALIAS_KEY = re.compile(r"^[a-z0-9][a-z0-9._-]{0,63}$")
_MODEL_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")

_STAGE_SUBJECT = {
    "asr": "speech recognition (audio in, text out)",
    "tts": "speech synthesis (text in, audio out)",
    "sfx": "sound-effect generation (prompt in, audio out)",
    "music": "music generation (prompt in, audio out)",
}

_COMMON_EVIDENCE_REQUIREMENTS = (
    "a declared local external model whose file bytes match its recorded "
    "sha256 on the host that runs the stage (a declaration alone is E0/E1)",
    "a host-live qualification receipt referenced as 'host-live:<id>' naming "
    "adapter version, model revision, OS, device and the exact command",
    "a license decision recorded for the model and for the produced audio",
    "a rights decision for the input text or audio that is fed to the stage",
    "an output artifact read back from disk with its own sha256 and byte size",
)

_STAGE_EVIDENCE_REQUIREMENTS = {
    "asr": (
        "a measured word-error or character-error check on a fixed synthetic "
        "fixture with a known reference transcript",
        "a measured language and sample-rate readback of the produced text side",
        "proof that transcript text stayed inside the project-local runtime and "
        "only its sha256 was recorded",
    ),
    "tts": (
        "a measured sample-rate, channel count and duration readback of the "
        "produced audio",
        "a determinism note recording seed, temperature and voice identity",
        "a measured intelligibility check on a fixed synthetic input text",
    ),
    "sfx": (
        "a measured sample-rate, channel count, duration and peak-level "
        "readback of the produced audio",
        "a determinism note recording seed and sampler settings",
        "a rights decision for the prompt and for any reference audio used",
    ),
    "music": (
        "a measured sample-rate, channel count, duration and loudness readback "
        "of the produced audio",
        "a determinism note recording seed, tempo and arrangement controls",
        "a rights and provenance decision for every conditioning input",
    ),
}

#: Keys that would indicate raw transcript text was about to be persisted.
_FORBIDDEN_TRANSCRIPT_KEYS = frozenset(
    {"transcript", "transcript_text", "text", "words", "segments_text"}
)


def evidence_requirements(stage: str) -> list:
    """What must be proven before ``stage`` may be called E2 or higher.

    This is a declaration of the evidence contract, not evidence. Passing these
    requirements is what a future host-live run must demonstrate; nothing in
    this module demonstrates any of them.
    """
    if stage not in AUDIO_STAGES:
        raise MediaError(
            "AUDIO_STAGE_UNKNOWN", f"stage {stage!r} is not one of {AUDIO_STAGES}"
        )
    return [*_COMMON_EVIDENCE_REQUIREMENTS, *_STAGE_EVIDENCE_REQUIREMENTS[stage]]


def _checked_audio_hash(value: Any, field_name: str) -> Any:
    if value is None:
        return None
    return normalize_sha256(value, field_name)


@dataclass(frozen=True)
class AudioJobRecord:
    """One declared audio operation.

    A record is a *declaration*: it may be built before a run exists, in which
    case the output fields stay ``None`` and ``host_execution`` stays
    ``NOT_EXECUTED``. Transcripts are private user content: only
    ``transcript_sha256`` is storable, and any attempt to carry transcript text
    inside ``readback`` fails closed.
    """

    operation_id: str
    stage: str
    model_id: Any = None
    input_sha256: Any = None
    output_sha256: Any = None
    sample_rate: Any = None
    duration_seconds: Any = None
    language: Any = None
    transcript_sha256: Any = None
    readback: Mapping = field(default_factory=dict)
    evidence_level: str = STRUCTURAL_EVIDENCE
    host_execution: str = NOT_EXECUTED

    def __post_init__(self) -> None:
        require_text(self.operation_id, "operation_id", code="AUDIO_RECORD_INVALID")
        if self.stage not in AUDIO_STAGES:
            raise MediaError(
                "AUDIO_RECORD_INVALID",
                f"stage {self.stage!r} is not one of {AUDIO_STAGES}",
            )
        if self.model_id is not None:
            require_text(self.model_id, "model_id", code="AUDIO_RECORD_INVALID")
        for name in ("input_sha256", "output_sha256", "transcript_sha256"):
            object.__setattr__(
                self, name, _checked_audio_hash(getattr(self, name), name)
            )
        if self.sample_rate is not None:
            if type(self.sample_rate) is not int or self.sample_rate <= 0:
                raise MediaError(
                    "AUDIO_RECORD_INVALID", "sample_rate must be a positive integer"
                )
        if self.duration_seconds is not None:
            if type(self.duration_seconds) not in (int, float) or self.duration_seconds < 0:
                raise MediaError(
                    "AUDIO_RECORD_INVALID",
                    "duration_seconds must be a non-negative number",
                )
        if self.language is not None:
            require_text(self.language, "language", code="AUDIO_RECORD_INVALID")
        require_mapping(self.readback, "readback", code="AUDIO_RECORD_INVALID")
        require_evidence_level(self.evidence_level, "evidence_level")
        require_text(self.host_execution, "host_execution", code="AUDIO_RECORD_INVALID")
        leaked = _FORBIDDEN_TRANSCRIPT_KEYS.intersection(self.readback)
        if leaked:
            raise MediaError(
                "AUDIO_TRANSCRIPT_TEXT_MUST_NOT_BE_STORED",
                f"readback carries {sorted(leaked)}; store transcript_sha256 only",
            )

    def to_dict(self) -> dict:
        """Exact, JSON-native representation; ``from_dict`` inverts it exactly."""
        document = {
            "operation_id": self.operation_id,
            "stage": self.stage,
            "model_id": self.model_id,
            "input_sha256": self.input_sha256,
            "output_sha256": self.output_sha256,
            "sample_rate": self.sample_rate,
            "duration_seconds": self.duration_seconds,
            "language": self.language,
            "transcript_sha256": self.transcript_sha256,
            "readback": dict(self.readback),
            "evidence_level": self.evidence_level,
            "host_execution": self.host_execution,
        }
        return document

    @classmethod
    def from_dict(cls, document: Mapping) -> "AudioJobRecord":
        require_mapping(document, "AudioJobRecord", code="AUDIO_RECORD_INVALID")
        expected = {
            "operation_id", "stage", "model_id", "input_sha256", "output_sha256",
            "sample_rate", "duration_seconds", "language", "transcript_sha256",
            "readback", "evidence_level", "host_execution",
        }
        if set(document) != expected:
            missing = sorted(expected - set(document))
            extra = sorted(set(document) - expected)
            raise MediaError(
                "AUDIO_RECORD_INVALID",
                f"record keys must be exact; missing={missing} unexpected={extra}",
            )
        return cls(
            operation_id=document["operation_id"],
            stage=document["stage"],
            model_id=document["model_id"],
            input_sha256=document["input_sha256"],
            output_sha256=document["output_sha256"],
            sample_rate=document["sample_rate"],
            duration_seconds=document["duration_seconds"],
            language=document["language"],
            transcript_sha256=document["transcript_sha256"],
            readback=document["readback"],
            evidence_level=document["evidence_level"],
            host_execution=document["host_execution"],
        )


class AudioModelRegistry:
    """Declarations of local external audio models, plus alias resolution.

    Registration never reads the model, never hashes it and never enables it:
    an entry is recorded as ``UNQUALIFIED_DECLARED`` with ``defaultEnabled``
    ``False``. Only :meth:`qualify_local_model` (which demands a measured
    ``host-live:`` receipt) may produce a ``QUALIFIED`` entry.
    """

    def __init__(self, *, alias_roots: Mapping | None = None,
                 denied_licenses: Iterable | None = None) -> None:
        self._alias_roots: dict = {}
        for alias, root in (alias_roots or {}).items():
            self.declare_alias(alias, root)
        self._denied_licenses = set()
        for license_id in (denied_licenses or ()):
            self._denied_licenses.add(
                require_text(license_id, "denied license", code="AUDIO_LICENSE_INVALID")
            )
        self._entries: dict = {}

    # -- aliases ---------------------------------------------------------
    def declare_alias(self, alias: str, root: Any) -> None:
        """Bind an alias key to a host directory. Never written into a document."""
        if not isinstance(alias, str) or not _ALIAS_KEY.match(alias):
            raise MediaError(
                "AUDIO_ALIAS_INVALID",
                f"alias {alias!r} must be a bare lowercase alias key, not a path",
            )
        if root is None:
            raise MediaError("AUDIO_ALIAS_INVALID", f"alias {alias!r} has no root")
        self._alias_roots[alias] = root

    def alias_root(self, alias: str) -> Any:
        if alias not in self._alias_roots:
            raise MediaError(
                "AUDIO_MODEL_ALIAS_UNKNOWN",
                f"path alias {alias!r} is not declared; declared aliases: "
                f"{sorted(self._alias_roots)}",
            )
        return self._alias_roots[alias]

    @property
    def declared_aliases(self) -> list:
        return sorted(self._alias_roots)

    # -- declarations ----------------------------------------------------
    def register_local_model(self, model_id: str, *, path_ref: str, sha256: str,
                             license_id: str) -> dict:
        """Record a local external model. Declared only; never enabled."""
        if not isinstance(model_id, str) or not _MODEL_ID.match(model_id):
            raise MediaError("AUDIO_MODEL_ID_INVALID", f"model_id {model_id!r}")
        if model_id in self._entries:
            raise MediaError("AUDIO_MODEL_ID_DUPLICATE", f"model_id {model_id!r}")
        if not isinstance(path_ref, str) or not _ALIAS_KEY.match(path_ref):
            raise MediaError(
                "AUDIO_MODEL_PATH_REF_INVALID",
                f"path_ref {path_ref!r} must be a path alias key, never an "
                "absolute or relative user path",
            )
        if not isinstance(license_id, str) or not license_id.strip():
            raise MediaError("AUDIO_MODEL_LICENSE_INVALID", f"license_id {license_id!r}")
        entry = {
            "model_id": model_id,
            "path_ref": path_ref,
            "sha256": normalize_sha256(sha256, "sha256"),
            "license_id": license_id,
            "qualification": UNQUALIFIED_DECLARED,
            "defaultEnabled": False,
            "evidence": STRUCTURAL_EVIDENCE,
            "note": (
                "declared local external asset; not probed, not hashed on this "
                "host, not enabled and not qualified"
            ),
        }
        self._entries[model_id] = entry
        return dict(entry)

    def qualify_local_model(self, model_id: str, *, host_live_reference: str) -> dict:
        """Promote a declaration to ``QUALIFIED`` using a measured receipt.

        A structural build cannot produce such a receipt, so the reference must
        already exist and must be ``host-live:<id>``.
        """
        entry = self._require_entry(model_id)
        if not isinstance(host_live_reference, str) or not HOST_EVIDENCE_REFERENCE.match(
            host_live_reference
        ):
            raise MediaError(
                "AUDIO_QUALIFICATION_UNPROVEN",
                f"model {model_id!r} cannot be qualified without a measured "
                f"'{HOST_EVIDENCE_PREFIX}<id>' receipt",
            )
        if entry["license_id"] in self._denied_licenses:
            raise MediaError(
                "AUDIO_MODEL_LICENSE_CONFLICT",
                f"model {model_id!r} license {entry['license_id']!r} is denied",
            )
        entry["qualification"] = "QUALIFIED"
        entry["host_live_reference"] = host_live_reference
        entry["defaultEnabled"] = False
        entry["note"] = (
            "qualified against a declared host-live receipt; this build did not "
            "reproduce that receipt and never enables the model by default"
        )
        return dict(entry)

    def mark_license_conflict(self, model_id: str, reason: str) -> dict:
        entry = self._require_entry(model_id)
        entry["qualification"] = "DISABLED_LICENSE_CONFLICT"
        entry["defaultEnabled"] = False
        entry["note"] = require_text(reason, "reason", code="AUDIO_LICENSE_INVALID")
        return dict(entry)

    def deny_license(self, license_id: str) -> None:
        self._denied_licenses.add(
            require_text(license_id, "license_id", code="AUDIO_LICENSE_INVALID")
        )

    def license_denied(self, license_id: str) -> bool:
        return license_id in self._denied_licenses

    def import_declarations(self, document: Mapping) -> list:
        """Re-read declarations exactly as a stored document claims them.

        This is the one deliberately lenient entry point: the hash is recorded
        verbatim, so a corrupted or legacy document can place a zero hash into
        the registry. :func:`resolve_audio_model` is what refuses it, which is
        the point - the guard must exist on the resolution path, not only on the
        registration path.
        """
        require_mapping(document, "declaration document", code="AUDIO_REGISTRY_INVALID")
        models = document.get("models")
        if not isinstance(models, list):
            raise MediaError("AUDIO_REGISTRY_INVALID", "models must be a list")
        imported = []
        for index, raw in enumerate(models):
            raw = require_mapping(
                raw, f"models[{index}]", code="AUDIO_REGISTRY_INVALID"
            )
            qualification = raw.get("qualification", UNQUALIFIED_DECLARED)
            if qualification not in QUALIFICATION_STATES:
                raise MediaError(
                    "AUDIO_REGISTRY_INVALID",
                    f"models[{index}].qualification {qualification!r} is not closed",
                )
            entry = {
                "model_id": require_text(
                    raw.get("model_id"), f"models[{index}].model_id",
                    code="AUDIO_REGISTRY_INVALID",
                ),
                "path_ref": require_text(
                    raw.get("path_ref"), f"models[{index}].path_ref",
                    code="AUDIO_REGISTRY_INVALID",
                ),
                "sha256": require_text(
                    raw.get("sha256"), f"models[{index}].sha256",
                    code="AUDIO_REGISTRY_INVALID",
                ),
                "license_id": require_text(
                    raw.get("license_id"), f"models[{index}].license_id",
                    code="AUDIO_REGISTRY_INVALID",
                ),
                "qualification": qualification,
                "defaultEnabled": False,
                "evidence": raw.get("evidence", STRUCTURAL_EVIDENCE),
                "note": raw.get(
                    "note", "imported declaration; not probed on this host"
                ),
            }
            if "host_live_reference" in raw:
                entry["host_live_reference"] = raw["host_live_reference"]
            self._entries[entry["model_id"]] = entry
            imported.append(dict(entry))
        return imported

    def _require_entry(self, model_id: str) -> dict:
        if model_id not in self._entries:
            raise MediaError("AUDIO_MODEL_UNKNOWN", f"model_id {model_id!r} is not declared")
        return self._entries[model_id]

    def entry(self, model_id: str) -> Any:
        """Return a copy of the declaration, or ``None`` when it is unknown."""
        found = self._entries.get(model_id)
        return None if found is None else dict(found)

    @property
    def model_ids(self) -> list:
        return sorted(self._entries)

    def qualified_model_ids(self) -> list:
        return sorted(
            model_id for model_id, entry in self._entries.items()
            if entry["qualification"] == "QUALIFIED"
        )

    def to_dict(self) -> dict:
        """Schema-checked declaration document; contains no absolute path."""
        document = {
            "schemaVersion": "design-lab/media-audio-provider/v1",
            "provider_id": ADAPTER_ID,
            "adapter_version": ADAPTER_VERSION,
            "evidence_level": STRUCTURAL_EVIDENCE,
            "host_execution": NOT_EXECUTED,
            "declared_aliases": self.declared_aliases,
            "stages": [
                {
                    "stage": stage,
                    "supported": False,
                    "evidence": STRUCTURAL_EVIDENCE,
                    "note": (
                        f"{_STAGE_SUBJECT[stage]}: declared only; no model is "
                        "qualified on this host and no inference was executed"
                    ),
                    "evidence_requirements": evidence_requirements(stage),
                }
                for stage in AUDIO_STAGES
            ],
            "models": [
                self._entries[model_id] for model_id in sorted(self._entries)
            ],
        }
        reject_absolute_paths(document, "audio model declaration")
        return validate_against("media-audio-provider", document)


def resolve_audio_model(registry: Any, model_id: str, *, verify_file: bool = True) -> dict:
    """Resolve a declared model for execution, or fail closed.

    Raises for: unknown model, unqualified model, zero or malformed hash, denied
    license, unknown path alias, and (when ``verify_file``) a missing asset.
    The hash is *not* recomputed here: recomputation is a host-live measurement
    that belongs to a qualified run, not to a structural build.
    """
    if not isinstance(registry, AudioModelRegistry):
        raise MediaError(
            "AUDIO_REGISTRY_INVALID",
            f"registry must be an AudioModelRegistry, got {type(registry).__name__}",
        )
    entry = registry.entry(model_id)
    if entry is None:
        raise MediaError("AUDIO_MODEL_UNKNOWN", f"model_id {model_id!r} is not declared")
    if entry["qualification"] != "QUALIFIED":
        raise MediaError(
            "AUDIO_MODEL_UNQUALIFIED",
            f"model {model_id!r} is {entry['qualification']}; only QUALIFIED may run",
        )
    digest = entry["sha256"]
    if not isinstance(digest, str) or digest.removeprefix("sha256:").lower() == "0" * 64:
        raise MediaError(
            "AUDIO_MODEL_HASH_ZERO",
            f"model {model_id!r} has a zero or missing hash and cannot run",
        )
    digest = normalize_sha256(digest, f"models[{model_id}].sha256")
    if registry.license_denied(entry["license_id"]):
        raise MediaError(
            "AUDIO_MODEL_LICENSE_CONFLICT",
            f"model {model_id!r} license {entry['license_id']!r} is denied",
        )
    root = registry.alias_root(entry["path_ref"])
    resolved = None
    if verify_file:
        resolved = Path(root)
        if not resolved.is_dir():
            raise MediaError(
                "AUDIO_MODEL_FILE_MISSING",
                f"model {model_id!r} alias {entry['path_ref']!r} does not resolve "
                "to an existing local asset directory",
            )
    return {
        "status": "QUALIFIED",
        "model_id": model_id,
        "path_ref": entry["path_ref"],
        "sha256": digest,
        "license_id": entry["license_id"],
        "evidence": entry["evidence"],
        "host_live_reference": entry.get("host_live_reference"),
        "resolved_path": None if resolved is None else resolved.as_posix(),
        "hash_reverified": False,
        "note": (
            "alias resolved for a qualified model; the recorded hash was NOT "
            "recomputed in this structural build"
        ),
    }


class AudioProvider(ProviderAdapter):
    """The DL-P1-140 provider adapter. Structural only; ``execute`` fails closed."""

    adapter_id = ADAPTER_ID
    adapter_type = "provider"
    version = ADAPTER_VERSION

    def __init__(self, *, registry: AudioModelRegistry | None = None) -> None:
        if registry is not None and not isinstance(registry, AudioModelRegistry):
            raise MediaError(
                "AUDIO_REGISTRY_INVALID",
                f"registry must be an AudioModelRegistry, got {type(registry).__name__}",
            )
        self.registry = registry if registry is not None else AudioModelRegistry()

    # -- declared capability table ---------------------------------------
    def declare_capabilities(self, measured_evidence: Mapping | None = None) -> list:
        """Declared capabilities. A stage is only ``supported`` with E2+ proof."""
        supplied = {}
        if measured_evidence is not None:
            require_mapping(measured_evidence, "measured_evidence")
            for stage, receipt in measured_evidence.items():
                if stage not in AUDIO_STAGES:
                    raise MediaError(
                        "AUDIO_STAGE_UNKNOWN",
                        f"measured_evidence has unknown stage {stage!r}",
                    )
                receipt = require_mapping(receipt, f"measured_evidence[{stage}]")
                level = require_evidence_level(
                    receipt.get("level"), f"measured_evidence[{stage}].level"
                )
                if level not in MEASURED_EVIDENCE_LEVELS:
                    raise MediaError(
                        "AUDIO_EVIDENCE_NOT_MEASURED",
                        f"stage {stage!r} claims {level}; E2 or higher requires a "
                        "real run on a fixed, versioned host",
                    )
                reference = require_text(
                    receipt.get("reference"),
                    f"measured_evidence[{stage}].reference",
                    code="AUDIO_EVIDENCE_NOT_MEASURED",
                )
                supplied[stage] = {"level": level, "reference": reference}
        capabilities = []
        for stage in AUDIO_STAGES:
            receipt = supplied.get(stage)
            capabilities.append(
                {
                    "stage": stage,
                    "subject": _STAGE_SUBJECT[stage],
                    "supported": receipt is not None,
                    "evidence": STRUCTURAL_EVIDENCE if receipt is None else receipt["level"],
                    "reference": None if receipt is None else receipt["reference"],
                    "note": (
                        "declared capability; no qualified model and no inference "
                        "exists in this build"
                        if receipt is None
                        else "supported by a caller-supplied measured receipt that "
                             "this build did not reproduce"
                    ),
                }
            )
        return capabilities

    def _evidence(self, note: str) -> dict:
        return {
            "level": STRUCTURAL_EVIDENCE,
            "task_ids": ["DL-P1-140"],
            "host_execution": NOT_EXECUTED,
            "artifact_paths": [
                "src/design_lab/creative/media/audio_provider.py",
                "design-lab/schemas/media-audio-provider.schema.json",
            ],
            "note": note,
        }

    def register_local_model(self, model_id: str, *, path_ref: str, sha256: str,
                             license_id: str) -> dict:
        return self.registry.register_local_model(
            model_id, path_ref=path_ref, sha256=sha256, license_id=license_id
        )

    # -- SPI lifecycle ---------------------------------------------------
    def probe(self, ctx: dict) -> dict:
        """Report declarations only. Never stats a model and never starts a host."""
        ctx = require_mapping(ctx, "ctx")
        capabilities = self.declare_capabilities(ctx.get("measured_evidence"))
        return {
            "adapter_id": self.adapter_id,
            "adapter_type": self.adapter_type,
            "version": self.version,
            "status": "structural",
            "mode": "none",
            "capabilities": capabilities,
            "declared_only": True,
            "probed": [],
            "models": {
                "declared": len(self.registry.model_ids),
                "qualified": len(self.registry.qualified_model_ids()),
                "declared_aliases": self.registry.declared_aliases,
                "default_enabled": [],
                "resolution": NOT_EXECUTED,
            },
            "streaming_support": {
                "asr_partial_results": False,
                "tts_streaming": False,
                "note": "declared false; no measurement exists",
            },
            "host_execution": NOT_EXECUTED,
            "evidence": self._evidence(
                "probe reports declarations only; no model file was opened, no "
                "audio device was accessed and no host run was executed"
            ),
        }

    def prepare(self, ctx: dict) -> dict:
        """Validate an audio request and return a plan that is not executable."""
        ctx = require_mapping(ctx, "ctx")
        operation_id = require_text(
            ctx.get("operation_id"), "operation_id", code="AUDIO_REQUEST_INVALID"
        )
        stage = ctx.get("stage")
        if stage not in AUDIO_STAGES:
            raise MediaError(
                "AUDIO_STAGE_UNKNOWN",
                f"stage {stage!r} is not one of {AUDIO_STAGES}",
            )
        model_id = ctx.get("model_id")
        if model_id is not None:
            model_id = require_text(model_id, "model_id", code="AUDIO_REQUEST_INVALID")
            if self.registry.entry(model_id) is None:
                raise MediaError(
                    "AUDIO_MODEL_UNKNOWN", f"model_id {model_id!r} is not declared"
                )
        capabilities = self.declare_capabilities(ctx.get("measured_evidence"))
        declared = next(item for item in capabilities if item["stage"] == stage)
        request = {
            "operation_id": operation_id,
            "stage": stage,
            "model_id": model_id,
            "declared_supported": declared["supported"],
        }
        blocked_by = ["AUDIO_INFERENCE_NOT_AUTHORIZED_IN_STRUCTURAL_BUILD"]
        if not declared["supported"]:
            blocked_by.append("AUDIO_STAGE_UNSUPPORTED_NO_MEASURED_EVIDENCE")
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "operation_id": operation_id,
            "stage": stage,
            "model_id": model_id,
            "request_hash": request_hash(request),
            "status": "PREPARED_STRUCTURAL_ONLY",
            "model_resolution": NOT_EXECUTED,
            "blocked_by": blocked_by,
            "evidence_requirements": evidence_requirements(stage),
            "host_execution": NOT_EXECUTED,
            "evidence": self._evidence(
                "prepare validates and hashes the request only; the model alias "
                "was not resolved and no audio work was executed"
            ),
        }

    def execute(self, envelope: dict) -> dict:
        """Always fails closed: this build may not run audio inference."""
        envelope = require_mapping(envelope, "envelope", code="AUDIO_ENVELOPE_INVALID")
        stage = envelope.get("stage")
        if stage is not None and stage not in AUDIO_STAGES:
            raise MediaError(
                "AUDIO_STAGE_UNKNOWN", f"stage {stage!r} is not one of {AUDIO_STAGES}"
            )
        raise MediaError(
            "AUDIO_EXECUTION_NOT_EXECUTED_STRUCTURAL_ONLY",
            "DL-P1-140 ships declared audio contracts only; executing a stage "
            "would require a QUALIFIED local model, a measured host-live "
            "qualification receipt, an approved audio device and an output "
            "readback, none of which exist in this build. Missing: "
            "host-live qualification, model resolution, device approval, "
            "artifact readback. NOT_EXECUTED",
        )

    def observe(self, ctx: dict) -> dict:
        """Declare what observation would collect; observe nothing."""
        ctx = require_mapping(ctx, "ctx")
        stage = ctx.get("stage")
        if stage is not None and stage not in AUDIO_STAGES:
            raise MediaError(
                "AUDIO_STAGE_UNKNOWN", f"stage {stage!r} is not one of {AUDIO_STAGES}"
            )
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "operation_id": ctx.get("operation_id"),
            "stage": stage,
            "status": NOT_EXECUTED,
            "observations": [],
            "observation_contract": [
                "artifact sha256 and byte size read back from disk",
                "sample rate and channel count of the produced audio",
                "duration in seconds measured from the produced container",
                "peak and integrated loudness of the produced audio",
                "language tag actually used, not the language requested",
                "transcript length and sha256 (never the transcript text)",
            ],
            "host_execution": NOT_EXECUTED,
            "evidence": self._evidence(
                "nothing was observed: no audio stage was executed in this build"
            ),
        }

    def readback(self, ctx: dict) -> dict:
        """Declare the readback contract; never claim a successful readback."""
        ctx = require_mapping(ctx, "ctx")
        record = ctx.get("record")
        parsed = None
        if record is not None:
            parsed = (
                record if isinstance(record, AudioJobRecord)
                else AudioJobRecord.from_dict(require_mapping(record, "record"))
            )
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "operation_id": ctx.get("operation_id") or (
                None if parsed is None else parsed.operation_id
            ),
            "status": NOT_EXECUTED,
            "artifact_readback": NOT_EXECUTED,
            "record": None if parsed is None else parsed.to_dict(),
            "readback_contract": [
                "recompute the artifact sha256 on the host and compare",
                "reopen the artifact and confirm the container still decodes",
                "confirm the recorded duration and sample rate still match",
            ],
            "evidence": self._evidence(
                "no artifact was opened and no hash was recomputed; readback is "
                "declared, not performed"
            ),
        }

    def rollback(self, ctx: dict) -> dict:
        """Declare the rollback contract. This build wrote nothing to undo."""
        ctx = require_mapping(ctx, "ctx")
        return {
            "adapter_id": self.adapter_id,
            "version": self.version,
            "operation_id": ctx.get("operation_id"),
            "status": NOT_EXECUTED,
            "executed": False,
            "actions": [
                "delete the produced audio artifact under the project-local runtime root",
                "delete the operation's interim cached tensors under the project-local cache root",
                "release the audio device lease held for the operation",
            ],
            "reason": (
                "no audio stage was executed in this build, so there is nothing "
                "to roll back; these actions are the contract a live run must follow"
            ),
            "evidence": self._evidence(
                "rollback was not executed because no audio job ran"
            ),
        }
