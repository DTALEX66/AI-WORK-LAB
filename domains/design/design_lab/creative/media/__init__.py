# SPDX-License-Identifier: MIT
"""DL-P1-140 / DL-P1-150 / DL-P1-131: media capability boundary package.

This package holds three structural contracts for the media domain:

* ``audio_provider``  - DL-P1-140, the ASR/TTS/SFX/music provider contract with
  local external model declarations.
* ``three_d``         - DL-P1-150, the Blender host adapter contract plus a
  standard-library GLB/glTF structural validator.
* ``video_boundary``  - DL-P1-131, the video ownership boundary rule engine.

What this package does NOT do: it never launches Blender, ComfyUI, ffmpeg or any
other application; it never runs audio inference, rendering or encoding; it
never opens a network socket; it never downloads or bundles a model; and it
never writes an absolute user path into a repository file. Everything produced
here is E1 (STRUCTURAL) evidence. Any code path that would require a real tool
fails closed with a :class:`MediaError` naming exactly what is missing, and any
claim that would need a host run is reported as ``NOT_EXECUTED``.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any, Mapping

from ...runtime.attempt_contract import canonical_hash, request_hash
from ...runtime.paths import PROJECT_ROOT
from ...governance.evidence_levels import EVIDENCE_LEVELS

__all__ = [
    "EVIDENCE_LEVELS",
    "HOST_EVIDENCE_PREFIX",
    "MEASURED_EVIDENCE_LEVELS",
    "MediaError",
    "NOT_EXECUTED",
    "PROJECT_ROOT",
    "SCHEMA_DIR",
    "STRUCTURAL_EVIDENCE",
    "canonical_hash",
    "load_schema",
    "normalize_sha256",
    "reject_absolute_paths",
    "request_hash",
    "require_evidence_level",
    "require_mapping",
    "require_text",
    "schema_path",
    "validate_against",
]

SCHEMA_DIR = PROJECT_ROOT / "design-lab" / "schemas"

#: Levels that require a measured execution on a real host.
MEASURED_EVIDENCE_LEVELS = ("E2", "E3", "E4", "E5")
STRUCTURAL_EVIDENCE = "E1"
NOT_EXECUTED = "NOT_EXECUTED"
#: Prefix of a measured host-live receipt reference (never a path, never a URL).
HOST_EVIDENCE_PREFIX = "host-live:"
HOST_EVIDENCE_REFERENCE = re.compile(r"^host-live:[^\s]+$")

# Absolute-path detection mirrors the vocabulary of
# packages/capabilities/reconstruction/providers/registry.py so that one leak
# rule is shared across the repository instead of being re-invented here.
_WINDOWS_ABSOLUTE = re.compile(r"(?<![A-Za-z0-9_])[A-Za-z]:[\\/]")
_UNC_ABSOLUTE = re.compile(r"(?<![A-Za-z0-9_])\\\\[^\\/\s]+[\\/]")
_POSIX_ABSOLUTE = re.compile(r"(?<![A-Za-z0-9_:/])/(?!/)[^\s)]*")


class MediaError(RuntimeError):
    """A media contract violation; the message always names the failed rule.

    The first argument is a stable ``CODE`` so callers and tests can assert on
    the failing rule instead of on prose. Nothing is ever "repaired" silently:
    ambiguity fails closed.
    """

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(f"{code}: {detail}" if detail else code)


def schema_path(name: str) -> Path:
    """Repository schema path for ``name``; never resolved against the cwd."""
    if not isinstance(name, str) or not name or "/" in name or "\\" in name:
        raise MediaError("MEDIA_SCHEMA_NAME_INVALID", repr(name))
    return SCHEMA_DIR / f"{name}.schema.json"


def load_schema(name: str) -> dict:
    """Load one repository JSON Schema document."""
    path = schema_path(name)
    if not path.is_file():
        raise MediaError("MEDIA_SCHEMA_MISSING", path.as_posix())
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MediaError("MEDIA_SCHEMA_UNREADABLE", f"{path.as_posix()}: {exc}") from exc
    if not isinstance(document, dict):
        raise MediaError("MEDIA_SCHEMA_UNREADABLE", f"{path.as_posix()}: not an object")
    return document


def validate_against(name: str, document: Any) -> Any:
    """Validate ``document`` with ``Draft202012Validator``; return it unchanged."""
    import jsonschema  # imported lazily: schema checks must not cost on import

    schema = load_schema(name)
    validator = jsonschema.Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(document), key=lambda item: list(item.path))
    if errors:
        first = errors[0]
        location = "/".join(str(part) for part in first.path) or "<root>"
        raise MediaError(
            "MEDIA_SCHEMA_INVALID", f"{name} at {location}: {first.message}"
        )
    return document


def require_mapping(value: Any, field: str, *, code: str = "MEDIA_FIELD_INVALID") -> Mapping:
    if not isinstance(value, Mapping):
        raise MediaError(code, f"{field} must be a mapping, got {type(value).__name__}")
    return value


def require_text(value: Any, field: str, *, code: str = "MEDIA_FIELD_INVALID") -> str:
    if not isinstance(value, str) or not value.strip():
        raise MediaError(code, f"{field} must be a nonempty string")
    return value


def require_evidence_level(value: Any, field: str) -> str:
    if value not in EVIDENCE_LEVELS:
        raise MediaError(
            "MEDIA_EVIDENCE_LEVEL_INVALID",
            f"{field} must be one of {EVIDENCE_LEVELS}, got {value!r}",
        )
    return value


def normalize_sha256(value: Any, field: str = "sha256") -> str:
    """Reuse the runtime contract: nonzero ``sha256:<64 hex>`` or fail closed."""
    try:
        return canonical_hash(value)
    except ValueError as exc:
        raise MediaError("MEDIA_SHA256_INVALID", f"{field}: {exc}") from exc


def reject_absolute_paths(document: Any, field: str) -> None:
    """Refuse to serialise an absolute user path into a repository document.

    Model and host assets are located by *alias key* only; a concrete machine
    path must never reach a checked-in schema, registry or evidence document.
    Apply this to documents whose string values are identifiers and short
    notes, not to free prose that may legitimately contain a separator.
    """
    stack = [document]
    while stack:
        item = stack.pop()
        if isinstance(item, str):
            for pattern in (_WINDOWS_ABSOLUTE, _UNC_ABSOLUTE, _POSIX_ABSOLUTE):
                if pattern.search(item) is not None:
                    raise MediaError(
                        "MEDIA_ABSOLUTE_PATH_LEAK",
                        f"{field} contains an absolute path value: {item!r} "
                        "(declare an alias key instead)",
                    )
        elif isinstance(item, Mapping):
            stack.extend(item.keys())
            stack.extend(item.values())
        elif isinstance(item, (list, tuple)):
            stack.extend(item)
