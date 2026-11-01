"""Credential-free, metadata-only controlled repro evidence for launcher state drift."""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


def fingerprint_metadata(path: Path) -> dict[str, object]:
    """Record only existence/stat metadata and digest; never return file contents."""
    try:
        stat = path.stat()
    except OSError:
        return {"path_class": path.name, "exists": False}
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    return {"path_class": path.name, "exists": True, "size": stat.st_size, "mtime_ns": stat.st_mtime_ns, "digest": digest}


def controlled_repro(records: Iterable[dict[str, object]]) -> dict[str, object]:
    """Classify before/after metadata without claiming causality."""
    values = list(records)
    changed = [str(r.get("layer", "unknown")) for r in values if r.get("before") != r.get("after")]
    if not changed:
        classification = "NO_METADATA_CHANGE"
    elif any(layer in {"official_config", "project_overlay"} for layer in changed):
        classification = "CONFIG_LAYER_CHANGED"
    elif any(layer in {"desktop_internal", "thread_state", "sandbox_state"} for layer in changed):
        classification = "PLATFORM_INTERNAL_STATE_CHANGED"
    else:
        classification = "UNKNOWN_LAYER_CHANGED"
    return {"schema_version": "workflow/controlled-repro/v1", "observed_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"), "classification": classification, "records": len(values), "changed_layers": sorted(set(changed))}
