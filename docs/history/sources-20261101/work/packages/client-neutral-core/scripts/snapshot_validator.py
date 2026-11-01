"""Snapshot v3 schema validator (WLGM-150).

Validates a canonical v3 snapshot structure with explicit error reporting.
Unknown/absent fields never get padded to zero; validation failures return a
clear error list instead of partial pseudo-success.

Rules:
- schemaVersion must equal workflow/snapshot/v3;
- revision must be a non-negative integer;
- generatedAt must be a valid RFC3339 timestamp;
- projects[].projectId required, non-empty string;
- executions[].executionId + state required;
- tokenSummary numeric fields are int|null (never coerced);
- transport/coverage shape enforced when present.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path, PurePath
from typing import Any

SNAPSHOT_SCHEMA_VERSION = "workflow/snapshot/v3"

# The handle vocabulary is imported from the module that produces it, never restated here: a validator with
# its own copy of the surface names, the kind names, or the content-bearing keys is a second opinion that
# drifts the moment the projection changes. If the import fails the sets stay EMPTY, which then refuses
# every handle row — a degraded read path is visible, a permissive one is not.
try:  # pragma: no cover - the fallback is a deployment fault, not a normal branch
    from artifact_handle_projection import (
        ARTIFACT_KINDS as _VOCAB_ARTIFACT_KINDS,
        CONTENT_BEARING_KEYS as _VOCAB_CONTENT_KEYS,
        KNOWN_SURFACES as _VOCAB_SURFACES,
    )
    PROJECTION_VOCABULARY_SOURCE = "artifact_handle_projection"
except Exception as _vocabulary_error:  # noqa: BLE001 - fail closed and name the fault
    _VOCAB_ARTIFACT_KINDS = frozenset()
    _VOCAB_CONTENT_KEYS = frozenset()
    _VOCAB_SURFACES = frozenset()
    PROJECTION_VOCABULARY_SOURCE = f"unavailable:{type(_vocabulary_error).__name__}"

ARTIFACT_KINDS: frozenset[str] = _VOCAB_ARTIFACT_KINDS
EVIDENCE_SURFACES: frozenset[str] = _VOCAB_SURFACES
# A digest is 64 hex characters or it is not the same identity claim the record made.
DIGEST_HEX_LENGTH = 64
HEXDIGITS = frozenset("0123456789abcdefABCDEF")
CONTENT_BEARING_ROW_KEYS = frozenset(str(key).lower() for key in _VOCAB_CONTENT_KEYS)

# The fixed evidence vocabulary (WORK-LAB-AUTHORITY.md §10). A projection may report a lower level than
# a caller hopes for; it may never spell a higher one.
EVIDENCE_LEVELS = frozenset({"NO_EVIDENCE", "SIMULATED", "SYNTHETIC", "INTEGRATED", "REAL"})
# The seven capability layers, bottom first. A test binds this tuple to the projection's own LAYER_ORDER so
# the validator cannot quietly disagree with the code that builds the ladder.
CAPABILITY_LAYERS = ("REGISTERED", "INSTALLED", "LOADED_CONNECTED", "QUALIFIED",
                     "ENABLED_FOR_TASK", "NATIVE_PROJECTION", "OBSERVED_IN_EXECUTION")
RFC3339_RE = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d+)?(Z|[+-]\d{2}:\d{2})$"
)

# The per-verb dimension (the open register item the adapter probe closed): one row per contract verb a
# client actually answers. Its row rules and its verb vocabulary live with the projection that builds them,
# never restated here — a validator with its own copy of MET-requires-a-source, NOT_PROBED-requires-a-reason
# or the closed verb list is a second opinion that drifts the moment the probe changes. So both are imported
# from `adapter_capability_projection`: `validate_verb_evidence` for the per-row refusals and
# `contract_verb_vocabulary` for the closed verb set (which cross-checks schema + matrix and raises on
# drift). The vocabulary is a tracked-schema enum, so it is resolved lazily from the repo root only when a
# card actually carries verb rows. If either the import or the vocabulary read is unavailable, a card that
# carries verb rows is refused rather than waved through — a degraded read path is visible, a permissive
# one is not — while cards without the dimension are untouched and still validate exactly as before.
_REPO_ROOT = Path(__file__).resolve().parents[3]
try:  # pragma: no cover - the fallback is a deployment fault, not a normal branch
    from adapter_capability_projection import (
        contract_verb_vocabulary as _contract_verb_vocabulary,
        validate_verb_evidence as _validate_verb_rows,
    )
    VERB_VOCABULARY_SOURCE = "adapter_capability_projection"
except Exception as _verb_vocabulary_error:  # noqa: BLE001 - fail closed and name the fault
    _contract_verb_vocabulary = None
    _validate_verb_rows = None
    VERB_VOCABULARY_SOURCE = f"unavailable:{type(_verb_vocabulary_error).__name__}"

_VERB_VOCABULARY_RESOLVED = False
_VERB_VOCABULARY_CACHE: tuple[str, ...] | None = None


def _verb_vocabulary() -> tuple[str, ...] | None:
    """The closed adapter verb list, read once through the projection's own discovery helper."""
    global _VERB_VOCABULARY_RESOLVED, _VERB_VOCABULARY_CACHE
    if _VERB_VOCABULARY_RESOLVED:
        return _VERB_VOCABULARY_CACHE
    _VERB_VOCABULARY_RESOLVED = True
    if _contract_verb_vocabulary is None:
        _VERB_VOCABULARY_CACHE = None
    else:
        try:
            _VERB_VOCABULARY_CACHE = _contract_verb_vocabulary(_REPO_ROOT)
        except Exception:  # noqa: BLE001 - an unreadable vocabulary makes every verb row unverifiable
            _VERB_VOCABULARY_CACHE = None
    return _VERB_VOCABULARY_CACHE


def _validate_verb_evidence(index: int, rows: Any) -> list[str]:
    """Refuse a malformed verb dimension on one card; delegate the row rules to their single owner.

    Absent (no key) is legal and means "the producer did not read the verb record" — that is handled by the
    caller not invoking this. An empty list present is NOT legal: it reads as "this client declares no
    verbs", the exact opposite claim from "nothing was probed", and the projection never emits it.
    """
    if _validate_verb_rows is None:
        return [f"adapterCapabilities[{index}].verbEvidence cannot be validated — the verb row rules are "
                f"unavailable (source: {VERB_VOCABULARY_SOURCE})"]
    if not isinstance(rows, list):
        return [f"adapterCapabilities[{index}].verbEvidence must be a list when present"]
    if not rows:
        return [f"adapterCapabilities[{index}].verbEvidence is an empty list — absent evidence stays absent "
                "(no key); an empty list reads as 'declares nothing', not 'I did not look'"]
    verbs = _verb_vocabulary()
    if verbs is None:
        return [f"adapterCapabilities[{index}].verbEvidence cannot be validated — the contract verb "
                f"vocabulary could not be read from the tracked schema (source: {VERB_VOCABULARY_SOURCE})"]
    return [f"adapterCapabilities[{index}].{error}" for error in _validate_verb_rows(rows, verbs=verbs)]


def validate_snapshot(snapshot: dict[str, Any]) -> dict[str, Any]:
    """Return {'valid': bool, 'errors': [str], 'warnings': [str]}."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(snapshot, dict):
        return {"valid": False, "errors": ["snapshot must be an object"], "warnings": []}

    if snapshot.get("schemaVersion") != SNAPSHOT_SCHEMA_VERSION:
        errors.append(f"schemaVersion must be {SNAPSHOT_SCHEMA_VERSION}")

    revision = snapshot.get("revision")
    if not isinstance(revision, int) or isinstance(revision, bool) or revision < 0:
        errors.append(f"revision must be a non-negative integer, got {revision!r}")

    generated_at = snapshot.get("generatedAt")
    if generated_at is not None:
        if not isinstance(generated_at, str) or not RFC3339_RE.match(generated_at):
            errors.append(f"generatedAt must be RFC3339, got {generated_at!r}")
    else:
        errors.append("generatedAt is required")

    projects = snapshot.get("projects")
    if not isinstance(projects, list):
        errors.append("projects must be a list")
    else:
        seen: set[str] = set()
        for index, project in enumerate(projects):
            if not isinstance(project, dict):
                errors.append(f"projects[{index}] must be an object")
                continue
            pid = project.get("projectId")
            if not isinstance(pid, str) or not pid:
                errors.append(f"projects[{index}].projectId required")
            elif pid in seen:
                warnings.append(f"duplicate projectId {pid!r}")
            else:
                seen.add(pid)
            count = project.get("activeExecutionCount")
            if count is not None and (not isinstance(count, int) or isinstance(count, bool) or count < 0):
                errors.append(f"projects[{index}].activeExecutionCount must be int|null, got {count!r}")

    executions = snapshot.get("executions")
    if executions is not None:
        if not isinstance(executions, list):
            errors.append("executions must be a list")
        else:
            for index, execution in enumerate(executions):
                if not isinstance(execution, dict):
                    errors.append(f"executions[{index}] must be an object")
                    continue
                eid = execution.get("executionId")
                if not isinstance(eid, str) or not eid:
                    errors.append(f"executions[{index}].executionId required")
                state = execution.get("state")
                if not isinstance(state, str) or not state:
                    errors.append(f"executions[{index}].state required")
                anchor = execution.get("anchorProjectId")
                if anchor is not None and not isinstance(anchor, str):
                    errors.append(f"executions[{index}].anchorProjectId must be str|null, got {anchor!r}")

    token_summary = snapshot.get("tokenSummary")
    if token_summary is not None:
        if not isinstance(token_summary, dict):
            errors.append("tokenSummary must be an object")
        else:
            for field in ("inputTokens", "outputTokens", "totalTokens"):
                value = token_summary.get(field)
                if value is not None and (not isinstance(value, int) or isinstance(value, bool)):
                    errors.append(f"tokenSummary.{field} must be int|null, got {value!r}")
            quality = token_summary.get("costQuality")
            if quality is not None and quality not in ("EXACT", "ESTIMATED", "UNKNOWN"):
                errors.append(f"tokenSummary.costQuality must be EXACT|ESTIMATED|UNKNOWN|null, got {quality!r}")

    task_records = snapshot.get("taskRecords")
    if task_records is not None:
        if not isinstance(task_records, list):
            errors.append("taskRecords must be a list when present")
        else:
            seen_task_ids: set[str] = set()
            for index, record in enumerate(task_records):
                if not isinstance(record, dict):
                    errors.append(f"taskRecords[{index}] must be an object")
                    continue
                tid = record.get("taskId")
                if not isinstance(tid, str) or not tid:
                    errors.append(f"taskRecords[{index}].taskId required (non-empty string)")
                elif tid in seen_task_ids:
                    errors.append(f"taskRecords[{index}].taskId duplicates {tid!r}")
                else:
                    seen_task_ids.add(tid)
                for field in ("projectId", "status"):
                    value = record.get(field)
                    if not isinstance(value, str) or not value:
                        errors.append(f"taskRecords[{index}].{field} required (non-empty string)")
                fencing = record.get("fencingToken")
                if fencing is not None and (not isinstance(fencing, int) or isinstance(fencing, bool)):
                    errors.append(f"taskRecords[{index}].fencingToken must be int|null, got {fencing!r}")
                present = record.get("checkpointPresent")
                if not isinstance(present, bool):
                    errors.append(f"taskRecords[{index}].checkpointPresent must be boolean, got {present!r}")
                keys = record.get("checkpointKeys")
                if not isinstance(keys, list) or any(not isinstance(item, str) for item in keys):
                    errors.append(f"taskRecords[{index}].checkpointKeys must be a list of key names")
                digest = record.get("checkpointDigest")
                shaped = isinstance(digest, str) and len(digest) == 64 and all(
                    character in "0123456789abcdefABCDEF" for character in digest)
                if present and not isinstance(digest, str):
                    errors.append(
                        f"taskRecords[{index}].checkpointDigest must be a digest when a checkpoint exists"
                    )
                if not present:
                    if digest is not None:
                        errors.append(
                            f"taskRecords[{index}].checkpointDigest must be null when no checkpoint exists"
                        )
                    if keys:
                        errors.append(
                            f"taskRecords[{index}].checkpointKeys must be empty when no checkpoint exists"
                        )
                elif digest is not None and not shaped:
                    errors.append(
                        f"taskRecords[{index}].checkpointDigest is present but is not a 64-hex digest"
                    )
                register = record.get("register")
                if register is not None:
                    # The register half of this list is prose the owner wrote, capped so a 18k-character
                    # cell can ride every snapshot. A cap the reader cannot see is the same defect as a
                    # filter they cannot see, so the disclosed length has to actually describe the text:
                    # JSON Schema bounds `work` (maxLength) but cannot state that `workTruncated` agrees
                    # with it, and cannot say that a marker row owes the reader a reason.
                    if not isinstance(register, dict):
                        errors.append(f"taskRecords[{index}].register must be an object, got {register!r}")
                    else:
                        work = register.get("work")
                        chars = register.get("workChars")
                        truncated = register.get("workTruncated")
                        if isinstance(work, str) and isinstance(chars, int) and not isinstance(chars, bool):
                            if chars < len(work):
                                errors.append(
                                    f"taskRecords[{index}].register.workChars={chars} is smaller than the "
                                    f"{len(work)} characters actually projected")
                            if truncated is not (chars > len(work)):
                                errors.append(
                                    f"taskRecords[{index}].register.workTruncated={truncated!r} disagrees "
                                    f"with workChars={chars} against len(work)={len(work)}")
                        else:
                            errors.append(
                                f"taskRecords[{index}].register.work/workChars must be str/int")
                        if register.get("state") not in ("READ", "UNREADABLE", "ID_CONFLICT"):
                            errors.append(
                                f"taskRecords[{index}].register.state must be READ|UNREADABLE|ID_CONFLICT, "
                                f"got {register.get('state')!r}")
                        if register.get("state") != "READ" and not register.get("reason"):
                            errors.append(
                                f"taskRecords[{index}].register is a {register.get('state')!r} marker that "
                                "names no reason — a gap a reader cannot investigate")

    adapter_cards = snapshot.get("adapterCapabilities")
    if adapter_cards is not None:
        if not isinstance(adapter_cards, list):
            errors.append("adapterCapabilities must be a list when present")
        else:
            for index, card in enumerate(adapter_cards):
                if not isinstance(card, dict):
                    errors.append(f"adapterCapabilities[{index}] must be an object")
                    continue
                client_id = card.get("clientId")
                if not isinstance(client_id, str) or not client_id:
                    errors.append(f"adapterCapabilities[{index}].clientId required")
                layers = card.get("layers")
                if not isinstance(layers, list):
                    errors.append(f"adapterCapabilities[{index}].layers must be a list")
                    continue
                names = [str(layer.get("layer")) for layer in layers if isinstance(layer, dict)]
                if len(names) != len(layers):
                    errors.append(f"adapterCapabilities[{index}].layers contains a non-object entry")
                if len(set(names)) != len(names):
                    errors.append(f"adapterCapabilities[{index}].layers repeats a layer name")
                unknown = sorted(name for name in set(names) if name not in CAPABILITY_LAYERS)
                if unknown:
                    errors.append(
                        f"adapterCapabilities[{index}].layers names are outside the ladder: {unknown}"
                    )
                # Monotonicity: "the ladder cannot be climbed from the top" has to be a rule, not a comment.
                # Before this, a card listing only OBSERVED_IN_EXECUTION=MET with a hand-written source
                # string validated clean -- the two lower layers were simply absent rather than unproven.
                met_layers = {str(layer.get("layer")) for layer in layers
                              if isinstance(layer, dict) and layer.get("state") == "MET"}
                for name in sorted(met_layers & set(CAPABILITY_LAYERS)):
                    position = CAPABILITY_LAYERS.index(name)
                    missing_below = [lower for lower in CAPABILITY_LAYERS[:position] if lower not in met_layers]
                    if missing_below:
                        errors.append(
                            f"adapterCapabilities[{index}].layers claims {name}=MET while "
                            f"{missing_below} are not MET"
                        )
                for layer_index, layer in enumerate(layers):
                    if not isinstance(layer, dict):
                        continue
                    state = layer.get("state")
                    if state not in ("MET", "NOT_PROBED", "NOT_SUPPORTED"):
                        errors.append(
                            f"adapterCapabilities[{index}].layers[{layer_index}].state "
                            f"must be MET|NOT_PROBED|NOT_SUPPORTED, got {state!r}"
                        )
                    evidence = layer.get("evidenceLevel")
                    if evidence not in EVIDENCE_LEVELS:
                        errors.append(
                            f"adapterCapabilities[{index}].layers[{layer_index}].evidenceLevel "
                            f"must be one of {sorted(EVIDENCE_LEVELS)}, got {evidence!r}"
                        )
                    reason = layer.get("reason")
                    if not isinstance(reason, str) or not reason.strip():
                        errors.append(
                            f"adapterCapabilities[{index}].layers[{layer_index}].reason required — "
                            "an unprobed layer must say what is missing"
                        )
                    source = layer.get("source")
                    if state == "MET":
                        if not isinstance(source, str) or not source.strip():
                            errors.append(
                                f"adapterCapabilities[{index}].layers[{layer_index}] claims MET "
                                "without a named source"
                            )
                        if evidence == "NO_EVIDENCE":
                            errors.append(
                                f"adapterCapabilities[{index}].layers[{layer_index}] claims MET "
                                "with NO_EVIDENCE"
                            )
                status = card.get("nativeStatus")
                if status not in ("NOT_IMPLEMENTED", "NOT_PROBED", "NATIVELY_VERIFIED"):
                    errors.append(
                        f"adapterCapabilities[{index}].nativeStatus must be "
                        f"NOT_IMPLEMENTED|NOT_PROBED|NATIVELY_VERIFIED, got {status!r}"
                    )
                elif status == "NATIVELY_VERIFIED":
                    observed = next((layer for layer in layers
                                    if isinstance(layer, dict)
                                    and layer.get("layer") == "OBSERVED_IN_EXECUTION"), None)
                    if not observed or observed.get("state") != "MET":
                        errors.append(
                            f"adapterCapabilities[{index}] claims NATIVELY_VERIFIED while "
                            "OBSERVED_IN_EXECUTION is not MET — the ladder cannot be climbed from the top"
                        )
                # The per-verb dimension is orthogonal to the ladder: it never promotes a layer, and a
                # malformed row is refused here exactly as it is refused by the probe that wrote it. An
                # absent key is legal ("the verb record was not read"); a present-but-bad list is not.
                verb_rows = card.get("verbEvidence")
                if verb_rows is not None:
                    errors.extend(_validate_verb_evidence(index, verb_rows))

    transport = snapshot.get("transport")
    if transport is not None and not isinstance(transport, dict):
        errors.append("transport must be an object")

    errors.extend(_validate_artifact_handles(snapshot))
    errors.extend(_validate_issues(snapshot))

    return {"valid": not errors, "errors": errors, "warnings": warnings}


def _validate_artifact_handles(snapshot: dict[str, Any]) -> list[str]:
    """REQ-RANGE-20261007: the artifact handle list and the enumeration scope that produced it.

    Absent is legal and means "the producer did not enumerate". Present means every row is a handle the
    evidence-range route can be asked about: absolute, unique, on a surface this project declares, sized,
    timestamped, and carrying a digest ONLY when some project record states one. A row that carries file
    content, a digest that was not recorded, a list longer than its declared cap, a capped list that names
    no ordering key, or a list without the scope report that produced it is refused here rather than
    discovered by a broken viewer.
    """
    errors: list[str] = []
    handles = snapshot.get("artifactHandles")
    summary = snapshot.get("artifactHandlesSummary")
    if handles is None:
        if summary is not None:
            errors.append("artifactHandlesSummary without artifactHandles — a scope report of a list "
                          "this snapshot does not carry")
        return errors
    if not isinstance(handles, list):
        errors.append("artifactHandles must be a list when present")
        return errors
    if summary is None:
        errors.append("artifactHandles requires artifactHandlesSummary — an enumeration without its stated "
                      "scope reads as a complete list whether or not it is one")
        return errors
    if not isinstance(summary, dict):
        errors.append("artifactHandlesSummary must be an object")
        return errors

    seen: set[str] = set()
    for index, row in enumerate(handles):
        if not isinstance(row, dict):
            errors.append(f"artifactHandles[{index}] must be an object")
            continue
        carried = sorted(key for key in row if str(key).lower() in CONTENT_BEARING_ROW_KEYS)
        if carried:
            errors.append(f"artifactHandles[{index}] carries content field(s) {carried} — a handle list "
                          "projects identity, and bytes are read through /api/v1/evidence-range by interval")
        handle = row.get("handle")
        if not isinstance(handle, str) or not handle.strip():
            errors.append(f"artifactHandles[{index}].handle required (non-empty string)")
        elif PurePath(handle).is_absolute() is False:
            errors.append(f"artifactHandles[{index}].handle must be an absolute path, got {handle!r} — "
                          "a relative handle means a different file under a different working directory")
        elif handle in seen:
            errors.append(f"artifactHandles[{index}].handle duplicates {handle!r}")
        else:
            seen.add(handle)
        surface = row.get("surface")
        if surface not in EVIDENCE_SURFACES:
            errors.append(f"artifactHandles[{index}].surface must be one of {sorted(EVIDENCE_SURFACES)}, "
                          f"got {surface!r}")
        kind = row.get("kind")
        if kind not in ARTIFACT_KINDS:
            errors.append(f"artifactHandles[{index}].kind must be one of {sorted(ARTIFACT_KINDS)}, "
                          f"got {kind!r}")
        size = row.get("sizeBytes")
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            errors.append(f"artifactHandles[{index}].sizeBytes must be a non-negative int, got {size!r}")
        modified = row.get("modifiedAt")
        if not isinstance(modified, str) or not RFC3339_RE.match(modified):
            errors.append(f"artifactHandles[{index}].modifiedAt must be RFC3339 UTC, got {modified!r}")
        digest = row.get("digest")
        recorded = row.get("digestRecorded")
        if not isinstance(recorded, bool):
            errors.append(f"artifactHandles[{index}].digestRecorded must be boolean — a reader must be able "
                          "to tell 'no digest exists' from 'nobody looked'")
        if "digest" in row and digest is None:
            errors.append(f"artifactHandles[{index}].digest must be absent, not null — a null digest would "
                          "be a padded identity")
        if digest is not None:
            if not isinstance(digest, str) or len(digest) != DIGEST_HEX_LENGTH or any(
                    character not in HEXDIGITS for character in digest):
                errors.append(f"artifactHandles[{index}].digest must be 64 hex characters, got {digest!r}")
            if recorded is not True:
                errors.append(f"artifactHandles[{index}] carries a digest while digestRecorded is not True")
            source = row.get("digestSource")
            if not isinstance(source, str) or not source.strip():
                errors.append(f"artifactHandles[{index}].digestSource required — a recorded digest must name "
                              "the record it was read from, or it is an invented one")
        elif recorded is True:
            errors.append(f"artifactHandles[{index}] claims a recorded digest but carries none")
        if not isinstance(row.get("surfaceRoot"), str) or not row.get("surfaceRoot"):
            errors.append(f"artifactHandles[{index}].surfaceRoot required — the declared surface the row was "
                          "enumerated from")

    projected = summary.get("projectedCount")
    if not isinstance(projected, int) or isinstance(projected, bool):
        errors.append(f"artifactHandlesSummary.projectedCount must be an int, got {projected!r}")
    elif projected != len(handles):
        errors.append(f"artifactHandlesSummary.projectedCount {projected} does not match the "
                      f"{len(handles)} projected artifactHandles")
    cap = summary.get("cap")
    if not isinstance(cap, int) or isinstance(cap, bool) or cap <= 0:
        errors.append(f"artifactHandlesSummary.cap must be a positive int, got {cap!r}")
    elif isinstance(projected, int) and projected > cap:
        errors.append(f"artifactHandles carries {projected} rows above its declared cap {cap} — an oversized "
                      "enumeration may be capped, it may never be quietly over-cap")
    enumerated = summary.get("enumeratedCount")
    if not isinstance(enumerated, int) or isinstance(enumerated, bool) or enumerated < 0:
        errors.append(f"artifactHandlesSummary.enumeratedCount must be a non-negative int, got {enumerated!r}")
    elif isinstance(projected, int) and projected > enumerated:
        errors.append(f"artifactHandlesSummary projects {projected} rows from {enumerated} enumerated")
    truncated = summary.get("truncated")
    if not isinstance(truncated, bool):
        errors.append("artifactHandlesSummary.truncated must be boolean — the list is either capped or it "
                      "is not, and a reader cannot be left to guess")
    elif isinstance(enumerated, int) and isinstance(projected, int) and truncated != (enumerated > projected):
        errors.append(f"artifactHandlesSummary.truncated={truncated} contradicts enumerated={enumerated} "
                      f"vs projected={projected}")
    # A cap keeps some rows and drops others, so the rule that chose which ones is part of the list's
    # identity, not a comment on it. Without a stated ordering key a truncated list is walk order wearing
    # the clothes of a policy: two readers of the same revision cannot tell whether they were shown the
    # same evidence, and neither can this validator.
    ordering_key = summary.get("orderingKey")
    if truncated is True and not (isinstance(ordering_key, str) and ordering_key.strip()):
        errors.append("artifactHandlesSummary.orderingKey required when truncated is true — a capped "
                      "enumeration must name the key that ranked the rows it kept, or the reader cannot "
                      "tell which artifacts are missing or on what grounds")
    elif ordering_key is not None and not (isinstance(ordering_key, str) and ordering_key.strip()):
        errors.append(f"artifactHandlesSummary.orderingKey must be a non-empty string, got {ordering_key!r}")
    if summary.get("contentIncluded") is not False:
        errors.append("artifactHandlesSummary.contentIncluded must be false — this projection never carries "
                      "artifact bytes, and a true or missing value says otherwise")
    digest_index = summary.get("digestIndex")
    if not isinstance(digest_index, dict):
        errors.append("artifactHandlesSummary.digestIndex required — how many digests were read from records")
    else:
        if digest_index.get("computedByHashing") is not False:
            errors.append("artifactHandlesSummary.digestIndex.computedByHashing must be false — a digest this "
                          "projection hashed itself out of file bytes is not a recorded digest")
        with_digest = digest_index.get("rowsWithDigest")
        if isinstance(with_digest, int) and isinstance(projected, int) and with_digest > projected:
            errors.append(f"artifactHandlesSummary.digestIndex.rowsWithDigest {with_digest} exceeds the "
                          f"projected rows {projected}")
    generated = summary.get("generatedAt")
    if not isinstance(generated, str) or not RFC3339_RE.match(generated):
        errors.append(f"artifactHandlesSummary.generatedAt must be RFC3339, got {generated!r}")
    if not isinstance(summary.get("surfaces"), list) or not summary.get("surfaces"):
        errors.append("artifactHandlesSummary.surfaces required — which declared surfaces were enumerated")
    state = summary.get("surfaceState")
    if not isinstance(state, list):
        errors.append("artifactHandlesSummary.surfaceState required — each declared surface with whether it "
                      "exists on this machine, so an absent source is reported instead of read as empty")
    return errors


def snapshot_to_json(snapshot: dict[str, Any]) -> str:
    """Serialize a snapshot with strict null preservation (never pad to 0)."""
    return json.dumps(snapshot, ensure_ascii=False, sort_keys=True)

ISSUE_CLASSES = ("SOURCE_CIRCUIT_OPEN", "SOURCE_REFUSAL", "SOURCE_FAILURE", "SOURCE_DATA_DROPPED",
                 "SOURCE_STALE", "SOURCE_INCOMPLETE_COVERAGE", "EXECUTION_STALLED", "EXECUTION_CONFLICT",
                 "TASK_BLOCKED", "TASK_FAILED")
_ISSUE_REQUIRED = ("schemaVersion", "fingerprint", "class", "origin", "evidenceRef", "priority",
                   "priorityRule", "occurrences", "status", "softwareId", "softwareVersion",
                   "softwareVersionSource")
_SOFTWARE_STATES = ("discovered", "not-discovered", "unmatched", "ambiguous",
                    "source-names-no-software", "identity-source-absent")
# Content fields are refused by name, the way the handle list refuses them: an issue row is a pointer to
# evidence, and a row that also carried the bytes would make the range route's read-on-demand rule moot.
_ISSUE_CONTENT_FIELDS = ("content", "body", "payload", "text", "lines")


def _validate_issues(snapshot: dict[str, Any]) -> list[str]:
    """Runtime rules for the issue centre, mirroring the enumeration-scope rules of the handle list.

    Absent is legal and means no source answered. Present means each row names a fact the store already
    holds, and the scope report has to add up: emitted + omitted must equal the distinct count, a capped
    list must name its ordering key, a fold that absorbed nothing cannot claim a denominator, and
    `complete` cannot be true while any source went unread.
    """
    errors: list[str] = []
    issues = snapshot.get("issues")
    summary = snapshot.get("issuesSummary")
    if issues is None:
        if summary is not None:
            errors.append("issuesSummary without issues — a scope report of a list this snapshot does not carry")
        return errors
    if not isinstance(issues, list):
        errors.append("issues must be a list when present")
        return errors
    if summary is None:
        errors.append("issues requires issuesSummary — a problem list without its stated scope reads as "
                      "the complete set whether or not it is one")
        return errors
    if not isinstance(summary, dict):
        errors.append("issuesSummary must be an object")
        return errors

    if summary.get("inferencePerformed") is not False:
        errors.append("issuesSummary.inferencePerformed must be false: this projection relates facts, it "
                      "does not diagnose causes")
    if summary.get("contentIncluded") is not False:
        errors.append("issuesSummary.contentIncluded must be false — no issue row may carry file content")
    if summary.get("derivationScope") != "canonical-store-facts-only":
        errors.append("issuesSummary.derivationScope must be canonical-store-facts-only")

    seen: set[str] = set()
    for index, row in enumerate(issues):
        if not isinstance(row, dict):
            errors.append(f"issues[{index}] must be an object")
            continue
        missing = [key for key in _ISSUE_REQUIRED if key not in row]
        if missing:
            errors.append(f"issues[{index}] missing {missing}")
            continue
        fingerprint = row["fingerprint"]
        if not (isinstance(fingerprint, str) and len(fingerprint) == 16
                and all(char in "0123456789abcdef" for char in fingerprint)):
            errors.append(f"issues[{index}].fingerprint must be 16 hex chars")
        if fingerprint in seen:
            errors.append(f"issues[{index}].fingerprint repeats — the fold did not happen, so occurrences "
                          "would double-count the same problem across rows")
        seen.add(fingerprint)
        if row["class"] not in ISSUE_CLASSES:
            errors.append(f"issues[{index}].class {row['class']!r} is outside the declared vocabulary")
        if row["priority"] not in ("P1", "P2", "P3"):
            errors.append(f"issues[{index}].priority must be P1/P2/P3")
        if not str(row["priorityRule"] or "").strip():
            errors.append(f"issues[{index}].priorityRule must state the rule that set the priority")
        if not str(row["evidenceRef"] or "").strip():
            errors.append(f"issues[{index}].evidenceRef must point at the row a reader can re-read")
        if row["status"] != "OPEN":
            errors.append(f"issues[{index}].status must be OPEN; anything else is a claim this projection "
                          "cannot make without a verification source")
        occurrences = row["occurrences"]
        if not isinstance(occurrences, int) or isinstance(occurrences, bool) or occurrences < 1:
            errors.append(f"issues[{index}].occurrences must be an integer >= 1")
        detail = row.get("detail")
        if isinstance(detail, str) and len(detail) > 160:
            errors.append(f"issues[{index}].detail exceeds the 160-char bound")
        for field in _ISSUE_CONTENT_FIELDS:
            if field in row:
                errors.append(f"issues[{index}] must not carry {field!r} — an issue row is a pointer, "
                              "not a copy of the evidence")

    emitted = summary.get("emittedCount")
    if emitted != len(issues):
        errors.append(f"issuesSummary.emittedCount={emitted} disagrees with the {len(issues)} rows present")
    distinct = summary.get("distinctIssueCount")
    omitted = summary.get("omittedCount")
    if isinstance(distinct, int) and isinstance(omitted, int) and distinct != emitted + omitted:
        errors.append(f"issuesSummary distinctIssueCount={distinct} != emittedCount({emitted}) "
                      f"+ omittedCount({omitted}) — the cap's tail must be counted exactly once")
    cap = summary.get("cap")
    if isinstance(cap, int) and len(issues) > cap:
        errors.append(f"issues holds {len(issues)} rows above its declared cap={cap}")
    if omitted and not str(summary.get("orderingKey") or "").strip():
        errors.append("a list that dropped rows without an orderingKey is a truncation that cannot be audited")
    if summary.get("truncated") and not omitted:
        errors.append("issuesSummary.truncated is true while omittedCount is 0 — one of them is lying")

    # `complete` is a statement about the four problem sources. The software identity list is a fifth entry
    # in `sources` and is disclosed by softwareAttribution.identitySourceAbsent instead: a complete problem
    # list whose identities were never built is a real, reportable state, not a half-read enumeration.
    problem_sources = [item for item in (summary.get("sources") or [])
                       if isinstance(item, dict) and item.get("source") != "software"]
    unread = [item.get("source") for item in problem_sources if item.get("state") != "read"]
    if summary.get("complete") and unread:
        errors.append(f"issuesSummary.complete cannot be true while sources did not answer: {unread}")
    identity_absent = any(isinstance(item, dict) and item.get("source") == "software"
                          and item.get("state") != "read" for item in (summary.get("sources") or []))
    declared = (summary.get("softwareAttribution") or {}).get("identitySourceAbsent")
    if isinstance(declared, bool) and declared is not identity_absent:
        errors.append("issuesSummary.softwareAttribution.identitySourceAbsent disagrees with the state "
                      f"reported for the software source (declared {declared}, sources say {identity_absent})")
    scanned = summary.get("rowsScanned")
    per_source = [item.get("rowsScanned") for item in (summary.get("sources") or [])
                  if isinstance(item, dict) and isinstance(item.get("rowsScanned"), int)]
    if isinstance(scanned, int) and sum(per_source) != scanned:
        errors.append(f"issuesSummary.rowsScanned={scanned} disagrees with the per-source counts {per_source}")
    attribution = summary.get("softwareAttribution")
    if not isinstance(attribution, dict):
        errors.append("issuesSummary.softwareAttribution must state how each row was attributed")
    else:
        buckets = sum(int(attribution.get(key) or 0) for key in ("attributed", "unmatched", "ambiguous",
                                                                "unattributable"))
        if buckets != len(issues):
            errors.append(f"issuesSummary.softwareAttribution covers {buckets} of {len(issues)} rows — "
                          "every row is in exactly one attribution bucket")
        known = int(attribution.get("versionKnown") or 0)
        with_version = sum(1 for row in issues if isinstance(row, dict) and row.get("softwareVersion"))
        if known != with_version:
            errors.append(f"versionKnown={known} disagrees with the {with_version} rows carrying a version")
    for index, row in enumerate(issues):
        if not isinstance(row, dict):
            continue
        state = row.get("softwareVersionSource")
        if state is not None and state not in _SOFTWARE_STATES:
            errors.append(f"issues[{index}].softwareVersionSource {state!r} is outside the vocabulary")
        if row.get("softwareVersion") and not row.get("softwareId"):
            errors.append(f"issues[{index}] reports a version with no product identity")
        if row.get("softwareId") and state not in ("discovered", "not-discovered"):
            errors.append(f"issues[{index}] is attributed to a product without saying how that was known")
    counts = summary.get("priorityCounts")
    if isinstance(counts, dict) and sum(v for v in counts.values() if isinstance(v, int)) != len(issues):
        errors.append("issuesSummary.priorityCounts does not add up to the rows emitted")
    return errors
