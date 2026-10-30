"""Adapter capability projection: one card per managed client, seven layers per card (P1-03 / F1).

The blueprint's capability ladder (WORK-LAB-BLUEPRINT-20261006.md §6) names seven layers that are each a
different claim, and none of them proves the next one:

    Registered -> Installed -> Loaded/Connected -> Qualified -> Enabled for Task
                 -> Native Projection -> Observed in Execution

Before this module the ladder existed only in prose, so a UI could call a manifest entry "installed" or an
adapter "native verified". This module is the single place that decides a layer's state, and the rules that
keep it honest are:

* a layer is MET only from a named source that carries that layer's own evidence; anything else is
  NOT_PROBED with the reason that says what is missing — never blank, never inherited from the layer
  below, never promoted because a sibling succeeded;
* `INSTALLED` never follows from a version string. It follows only from a software install-identity row
  whose location status is RESOLVED (U17), and the card says which status it read;
* the registry's own `detection.evidence_state` is carried through unchanged. A version readback is not a
  package-hash check, so an UNVERIFIED declaration must not be laundered into a pass by projection;
* per-client facts come from `config/capability-matrix.json#clients[]` (status, write policy, risk,
  runtime adapter, config-ownership default). `config/capability-conformance.json` describes PROTOCOLS, so
  it is attached as protocol status and never renamed into a per-client capability list;
* where the registry and the matrix state different verb sets for the same client, both are shown and the
  drift is named. Choosing one as truth is an owner decision, not a projection's;
* the seven layers say what a CLIENT is (declared, installed, observed). They cannot say which verbs of the
  adapter interface it answers, so a card carries an orthogonal `verbEvidence` dimension — one row per verb,
  each either MET from a named read-only call, NOT_SUPPORTED from a named declaration, or NOT_PROBED with a
  concrete refusal reason. An honest NOT_PROBED outranks a fabricated MET: a verb row never promotes a
  layer, never moves `nativeStatus`, and an absent probe record emits NO rows at all rather than an empty
  list that would render as "declared to support nothing".
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

LAYER_ORDER: tuple[str, ...] = (
    "REGISTERED",
    "INSTALLED",
    "LOADED_CONNECTED",
    "QUALIFIED",
    "ENABLED_FOR_TASK",
    "NATIVE_PROJECTION",
    "OBSERVED_IN_EXECUTION",
)

CONFORMANCE_PROTOCOLS = ("acp", "skills", "mcp")

# The per-verb dimension's own vocabulary. `MET` is only legal for a verb that was actually answered by a
# read-only call the row can name; `NOT_SUPPORTED` is a declaration or a measured "not implemented" answer;
# `NOT_PROBED` covers both "this probe refuses to exercise it" and "it was exercised and the answer does not
# carry enough to be credited" — the `reason` says which, and `attempted` says whether a call was made.
VERB_STATES = frozenset({"MET", "NOT_PROBED", "NOT_SUPPORTED"})
VERB_EVIDENCE_LEVELS = frozenset({"NO_EVIDENCE", "SIMULATED", "SYNTHETIC", "INTEGRATED", "REAL"})
VERB_ROW_FIELDS = ("verb", "state", "evidenceLevel", "source", "reason")

# The interface verb list is a closed enum in a tracked schema; nothing in this module assumes a number.
ADAPTER_INTERFACE_SCHEMA_RECORD = "packages/contracts/schemas/workflow/client-adapter.schema.json"
CAPABILITY_MATRIX_RECORD = "config/capability-matrix.json"

# Why the upper layers are unprobed, stated once so every card says the same thing about the same gap.
UNPROBED_REASON = {
    "LOADED_CONNECTED": "没有已接通的原生会话读回：adapter 的 invoke/observe 动词仍返回 NOT_IMPLEMENTED（AG-06/G06）",
    "QUALIFIED": "没有逐能力资格判定：资格需要真实调用与产物，目前没有可引用的判定记录",
    "ENABLED_FOR_TASK": "没有任务级启用记录：派发未实现，没有任何任务把该客户端启用为执行器",
    "NATIVE_PROJECTION": "没有原生投影：原生侧状态（会话/模型/子代理）尚未进入 v3 快照合同",
    "OBSERVED_IN_EXECUTION": "没有执行中观察：需要真实执行链上的 receipt/readback 关联到该客户端",
}


def _layer(layer: str, state: str, *, evidence_level: str, source: str | None, reason: str) -> dict[str, Any]:
    return {
        "layer": layer,
        "state": state,
        "evidenceLevel": evidence_level,
        "source": source,
        "reason": reason,
    }


# `location_status` is the fail-closed enum of workflow/software-installation-identity/v1 (U17/P0-07).
# Each value means something different for the INSTALLED layer, and conflating them is how a card starts
# claiming an installation that was never measured — or reporting "unprobed" for a real measured absence.
INSTALLED_MET_STATUSES = frozenset({"SINGLE_VERIFIED"})
INSTALLED_ABSENT_STATUSES = frozenset({"NOT_INSTALLED"})
# `scripts/audit/executor_live_probe.py` answers on this machine. Both of these prove an entry point
# exists and ran (VERSION_MOVED proves existence while showing the registry's version string is stale —
# that is drift to display, not a reason to call the client uninstalled).
ENTRY_LIVE_STATUSES = frozenset({"LIVE_VERIFIED", "VERSION_MOVED"})


def _card_probe(client_id: str, live_probe: dict[str, Any] | None, probed_at: str | None) -> dict[str, Any] | None:
    """The entry-point readback as its own fact: an executable answered, which is not a live session.

    Field names follow `scripts/audit/executor_live_probe.py`'s record (`state`, `command`, `detail`,
    `probe.exitCode`, `probe.outputSha256`) — the output is kept as a digest of the version line, not the
    line itself, because a card travels into a read-only projection.
    """
    if not live_probe:
        return None
    inner = live_probe.get("probe") or {}
    command = [str(part) for part in (live_probe.get("command") or [])]
    return {
        "status": str(live_probe.get("state") or "UNKNOWN"),
        "entryPoint": command[0] if command else None,
        "argv": command,
        "exitCode": inner.get("exitCode"),
        "outputDigest": inner.get("outputSha256"),
        "detail": live_probe.get("detail"),
        "probedAt": probed_at,
    }


def _installed_layer(client_id: str, software_rows: list[dict[str, Any]],
                     live_probe: dict[str, Any] | None = None) -> dict[str, Any]:
    """Installed comes from a measured install identity or a live entry readback, never a version string."""
    probe_status = str((live_probe or {}).get("state") or "")
    if probe_status in ENTRY_LIVE_STATUSES:
        entry = (live_probe or {}).get("command") or []
        return _layer("INSTALLED", "MET", evidence_level="INTEGRATED",
                      source=f"executor_live_probe[{client_id}] {probe_status} "
                             f"entry={entry[0] if entry else 'UNKNOWN'}",
                      reason="本机对该入口做过一次版本读回并成功返回（版本漂移另列，不影响「存在且可执行」）")
    row = next((item for item in software_rows
                if str(item.get("softwareId") or "") in (client_id, client_id.replace("-", "_"),
                                                          client_id.replace("_", "-"))), None)
    if row is None:
        return _layer("INSTALLED", "NOT_PROBED", evidence_level="NO_EVIDENCE", source=None,
                      reason="软件安装身份投影里没有该客户端的行（发现模块不可用或未登记）")
    location_status = str(row.get("locationStatus") or "UNKNOWN")
    handle = (f"software[{client_id}] locationStatus={location_status} "
              f"root={row.get('installRoot') or 'UNKNOWN'}")
    if location_status in INSTALLED_MET_STATUSES and row.get("installRoot"):
        return _layer("INSTALLED", "MET", evidence_level="INTEGRATED", source=handle,
                      reason="身份发现实测到唯一已验证安装位置")
    if location_status in INSTALLED_ABSENT_STATUSES:
        return _layer("INSTALLED", "NOT_SUPPORTED", evidence_level="INTEGRATED", source=handle,
                      reason="身份发现实测本机未安装（这是测出来的缺失，不是没测）")
    return _layer("INSTALLED", "NOT_PROBED", evidence_level="NO_EVIDENCE", source=handle,
                  reason=f"安装位置状态为 {location_status}：未落到已验证位置，所以不声称已安装")


def _matrix_client(matrix: dict[str, Any], client_id: str) -> dict[str, Any] | None:
    for entry in matrix.get("clients") or []:
        if str(entry.get("id") or "") == client_id:
            return entry
    for entry in matrix.get("manifest_only_clients") or []:
        if str(entry.get("id") or "") == client_id:
            return entry
    return None


def contract_verb_vocabulary(root: Path) -> tuple[str, ...]:
    """Discover the adapter interface's verb set instead of assuming it.

    Three tracked sources name the same closed list and all three must agree, because a card that says
    "this verb is not supported" is only honest if the verb belongs to the contract being refused:
    `client-adapter.schema.json#properties.interface.const` (the contract), its `operations` item enum
    (what a client may declare), and `capability-matrix.json#interface_contract` (the reconciled copy).
    A disagreement raises — resolving which list is truth is an owner decision, not a projection's.
    """
    schema = json.loads((root / ADAPTER_INTERFACE_SCHEMA_RECORD).read_text(encoding="utf-8"))
    interface = (schema.get("properties") or {}).get("interface") or {}
    declared = ((schema.get("properties") or {}).get("entries") or {}).get("items") or {}
    operations = (((declared.get("properties") or {}).get("operations") or {}).get("items") or {})
    matrix = json.loads((root / CAPABILITY_MATRIX_RECORD).read_text(encoding="utf-8"))
    lists = {
        "schema.interface.const": [str(v) for v in (interface.get("const") or [])],
        "schema.operations.enum": [str(v) for v in (operations.get("enum") or [])],
        "capability-matrix#interface_contract": [str(v) for v in (matrix.get("interface_contract") or [])],
    }
    verbs = lists["schema.interface.const"]
    if not verbs:
        raise ValueError("adapter interface verb list is absent from the tracked schema")
    for name, values in lists.items():
        if values != verbs:
            raise ValueError(f"adapter interface verb drift: {name}={values} vs {verbs}")
    return tuple(verbs)


def validate_verb_evidence(rows: list[dict[str, Any]], *, verbs: tuple[str, ...]) -> list[str]:
    """Return the reasons a set of verb rows may not be published; empty means it may.

    The refusals are the same shape as the layer rules, and for the same reason: a row that reads like
    proof but names nothing is worse than a row that admits it measured nothing.
    """
    errors: list[str] = []
    seen: set[str] = set()
    for index, row in enumerate(rows):
        if not isinstance(row, dict):
            errors.append(f"verbEvidence[{index}] must be an object")
            continue
        verb = str(row.get("verb") or "")
        if not verb:
            errors.append(f"verbEvidence[{index}].verb required")
        elif verb not in verbs:
            errors.append(f"verbEvidence[{index}] names {verb!r}, which is not an adapter interface verb "
                          f"{sorted(verbs)}")
        elif verb in seen:
            errors.append(f"verbEvidence[{index}] repeats verb {verb!r}")
        else:
            seen.add(verb)
        state = row.get("state")
        if state not in VERB_STATES:
            errors.append(f"verbEvidence[{index}].state must be MET|NOT_PROBED|NOT_SUPPORTED, got {state!r}")
        evidence = row.get("evidenceLevel")
        if evidence not in VERB_EVIDENCE_LEVELS:
            errors.append(f"verbEvidence[{index}].evidenceLevel must be one of "
                          f"{sorted(VERB_EVIDENCE_LEVELS)}, got {evidence!r}")
        source = row.get("source")
        reason = row.get("reason")
        has_source = isinstance(source, str) and bool(source.strip())
        has_reason = isinstance(reason, str) and bool(reason.strip())
        if state == "MET":
            if not has_source:
                errors.append(f"verbEvidence[{index}] ({verb}) claims MET without a named source")
            if evidence == "NO_EVIDENCE":
                errors.append(f"verbEvidence[{index}] ({verb}) claims MET with NO_EVIDENCE")
            if row.get("attempted") is False:
                errors.append(f"verbEvidence[{index}] ({verb}) claims MET while saying the verb was never "
                              "attempted — a refusal cannot be credited as an answer")
        elif state == "NOT_PROBED" and not has_reason:
            errors.append(f"verbEvidence[{index}] ({verb}) is NOT_PROBED and must say why nothing was "
                          "established (refused, or exercised but not creditable)")
        elif state == "NOT_SUPPORTED":
            if not (has_source or has_reason):
                errors.append(f"verbEvidence[{index}] ({verb}) is NOT_SUPPORTED and must name the "
                              "declaration or the measured answer it rests on")
            if evidence == "NO_EVIDENCE":
                errors.append(f"verbEvidence[{index}] ({verb}) reports NOT_SUPPORTED with NO_EVIDENCE — "
                              "an absence must come from a named source")
    return errors


# The provenance a reader needs to re-run or re-check a verb row. Listed explicitly — and a field that is
# not listed raises rather than being dropped, because silently losing `checkedPaths` is how a probe record
# starts looking tidier than the machine it measured.
VERB_ROW_PROVENANCE = ("command", "exitCode", "outputDigest", "outputLines", "detail", "probedAt",
                       "attempted", "basis", "declaredIn", "declaresDrift", "entryResolution",
                       "checkedPaths", "ref")


def _verb_evidence_rows(client_id: str, verb_rows: dict[str, list[dict[str, Any]]],
                        verbs: tuple[str, ...]) -> list[dict[str, Any]] | None:
    """Normalize this client's verb rows, or return None when the probe record says nothing about it."""
    raw = verb_rows.get(client_id)
    if not raw:
        return None
    errors = validate_verb_evidence(raw, verbs=verbs)
    if errors:
        raise ValueError(f"{client_id} verb evidence refused: {'; '.join(errors)}")
    rows: list[dict[str, Any]] = []
    for item in raw:
        unknown = sorted(set(item) - set(VERB_ROW_FIELDS) - set(VERB_ROW_PROVENANCE))
        if unknown:
            raise ValueError(f"{client_id} verb evidence carries fields this projection does not "
                             f"understand: {unknown}")
        row = {field: item.get(field) for field in VERB_ROW_FIELDS}
        for field in VERB_ROW_PROVENANCE:
            if item.get(field) is not None:
                row[field] = item.get(field)
        rows.append(row)
    return rows


def _verb_evidence_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"MET": 0, "NOT_PROBED": 0, "NOT_SUPPORTED": 0}
    for row in rows:
        counts[str(row.get("state"))] = counts.get(str(row.get("state")), 0) + 1
    return counts


def project_adapter_capabilities(*, registry: dict[str, Any], conformance: dict[str, Any],
                                matrix: dict[str, Any],
                                software_rows: list[dict[str, Any]] | None = None,
                                live_probe_rows: list[dict[str, Any]] | None = None,
                                live_probe_at: str | None = None,
                                verb_rows: dict[str, list[dict[str, Any]]] | None = None,
                                verb_probe_at: str | None = None,
                                contract_verbs: tuple[str, ...] | None = None,
                                observed_at: str | None = None) -> list[dict[str, Any]]:
    """Build one card per declared adapter. Absent evidence stays NOT_PROBED with its reason.

    Verb evidence is additive and optional: without a probe record carrying rows for a client the card gets
    no `verbEvidence` key at all, and the seven layers keep exactly the meaning they had before.
    """
    software_rows = software_rows or []
    probes = {str(row.get("adapter") or row.get("clientId") or ""): row for row in (live_probe_rows or [])}
    verb_rows = verb_rows or {}
    verbs = tuple(contract_verbs or matrix.get("interface_contract") or ())
    if verb_rows and not verbs:
        raise ValueError("verb evidence needs the adapter interface verb list; none is declared")
    cards: list[dict[str, Any]] = []
    for entry in registry.get("entries") or []:
        client_id = str(entry.get("id") or "")
        if not client_id:
            continue
        provenance = entry.get("provenance") or {}
        readback = provenance.get("version_readback") or {}
        detection = entry.get("detection") or {}
        matrix_entry = _matrix_client(matrix, client_id)
        probe = probes.get(client_id)
        probe_card = _card_probe(client_id, probe, live_probe_at)

        registry_operations = sorted(str(op) for op in entry.get("operations") or [])
        matrix_operations = sorted(str(op) for op in (matrix_entry or {}).get("operations") or [])

        layers = [
            _layer("REGISTERED", "MET", evidence_level="SYNTHETIC",
                   source=f"config/adapter-registry.json#entries[id={client_id}]",
                   reason="登记来自仓库声明文件，是声明不是探测"),
            _installed_layer(client_id, software_rows, probe),
        ]
        layers += [
            _layer(name, "NOT_PROBED", evidence_level="NO_EVIDENCE", source=None,
                   reason=UNPROBED_REASON[name])
            for name in LAYER_ORDER[2:]
        ]

        cards.append({
            "clientId": client_id,
            "displayName": entry.get("display_name") or client_id,
            "supportLevel": entry.get("support_level") or "UNKNOWN",
            "declaredOperations": registry_operations,
            "matrixOperations": matrix_operations,
            "operationsDrift": bool(matrix_entry) and registry_operations != matrix_operations,
            "registryStatus": (matrix_entry or {}).get("registry_status") or "NOT_IN_MATRIX",
            "writePolicy": (matrix_entry or {}).get("writes") or "UNKNOWN",
            # The operator's own declaration of WHAT this software is. Absent from the matrix is UNKNOWN,
            # never a guess from the name: a provider router and a repository host are not agent runtimes,
            # and the surfaces that list them have no other way to tell them apart.
            "role": (matrix_entry or {}).get("role") or "UNKNOWN",
            "risk": (matrix_entry or {}).get("risk") or "UNKNOWN",
            "runtimeAdapter": (matrix_entry or {}).get("runtime_adapter"),
            "configOwnershipDefault": (matrix_entry or {}).get("config_ownership_default"),
            "clientNote": (matrix_entry or {}).get("note") or entry.get("note"),
            "declaredVersion": provenance.get("version") or None,
            "versionReadbackMethod": readback.get("method"),
            "versionObservedAt": readback.get("observed_at"),
            "versionSource": readback.get("source"),
            "detectionMode": detection.get("mode"),
            "entryProbe": probe_card,
            # the registry is not the truth and a stale note about it is not either: when the live entry
            # answers with a different version, both strings stay visible as drift.
            "versionDrift": bool(probe and probe.get("state") == "VERSION_MOVED"),
            "detectionEvidenceState": detection.get("evidence_state") or "UNKNOWN",
            "protocolConformance": {
                protocol: (conformance.get(protocol) or {}).get("status") or "ABSENT"
                for protocol in CONFORMANCE_PROTOCOLS
            },
            "observedAt": observed_at,
            "layers": layers,
            "nativeStatus": "NOT_IMPLEMENTED",
        })
        evidence = _verb_evidence_rows(client_id, verb_rows, verbs)
        if evidence is not None:
            # absent input stays absent: no key at all rather than an empty list a renderer reads as
            # "this client declared no verbs", which is the same lie in a different shape.
            cards[-1]["verbEvidence"] = evidence
            cards[-1]["verbEvidenceCounts"] = _verb_evidence_counts(evidence)
            cards[-1]["verbEvidenceProbedAt"] = verb_probe_at
    return cards


LIVE_PROBE_RECORD = "docs/audits/EXECUTOR_LIVE_PROBE_2026-10-08.json"


def load_live_probe(root: Path) -> tuple[list[dict[str, Any]], str | None]:
    """Read the executor live probe record if this checkout has one.

    The probe is run by hand (`scripts/audit/executor_live_probe.py`) and its output is a tracked audit
    file, so an absent record is normal and means "not probed", never "not installed". A broken record is
    reported by raising: silently treating a corrupt probe as no-evidence would hide the run that produced it.
    """
    path = root / LIVE_PROBE_RECORD
    if not path.is_file():
        return [], None
    record = json.loads(path.read_text(encoding="utf-8"))
    return list(record.get("results") or []), record.get("at")


def load_verb_probe(root: Path) -> tuple[dict[str, list[dict[str, Any]]], str | None]:
    """Read the per-verb rows of the tracked probe record, keyed by client id.

    The `verbProbe` block is written by `packages/client-neutral-core/scripts/adapter_verb_probe.py` and is
    optional in the same way the entry probe is: no block means no verb was established on this machine,
    which is a NOT_PROBED state, never an empty capability list. A block that exists but is malformed raises
    rather than projecting nothing at all.
    """
    path = root / LIVE_PROBE_RECORD
    if not path.is_file():
        return {}, None
    record = json.loads(path.read_text(encoding="utf-8"))
    block = record.get("verbProbe")
    if not block:
        return {}, None
    rows: dict[str, list[dict[str, Any]]] = {}
    for entry in block.get("results") or []:
        client_id = str(entry.get("client") or entry.get("adapter") or "")
        if not client_id:
            raise ValueError("verb probe record has a result row without a client id")
        rows[client_id] = list(entry.get("verbs") or [])
        if not rows[client_id]:
            raise ValueError(f"verb probe row for {client_id} carries no verbs — drop the row instead")
    return rows, block.get("at")


def load_inputs(root: Path) -> tuple[dict[str, Any], dict[str, Any], dict[str, Any]]:
    """Read the three tracked sources. A missing file raises: a card with no source is not a card."""
    registry = json.loads((root / "config/adapter-registry.json").read_text(encoding="utf-8"))
    conformance = json.loads((root / "config/capability-conformance.json").read_text(encoding="utf-8"))
    matrix = json.loads((root / "config/capability-matrix.json").read_text(encoding="utf-8"))
    return registry, conformance, matrix
