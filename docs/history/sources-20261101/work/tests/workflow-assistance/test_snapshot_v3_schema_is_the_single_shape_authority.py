#!/usr/bin/env python3
"""WUI-15: `workflow/snapshot/v3` has a JSON Schema in the contract SSOT, and three spellings answer to it.

Before this file the snapshot's shape lived in two places that nothing compared: the Python producer
(`packages/client-neutral-core/scripts/snapshot_api.py`) plus its semantic validator, and a hand-maintained
TypeScript model (`apps/observer/frontend/src/types.ts`). That is how ERR-225 happened — the producer emitted
`entryProbe`/`versionDrift` the front model never declared, so the facts could not be rendered and every gate
stayed green. Registering the schema in `.project/governance/contracts/contract-catalog.json` gave the shape an
authority; this file proves the authority is not decorative by checking it against both consumers.

What is deliberately NOT duplicated here: the semantic invariants (capability-ladder monotonicity, checkpoint
digest shape, duplicate handles, truncation without an ordering key) stay in `snapshot_validator.py`, which
expresses rules JSON Schema cannot state. The schema owns the key set, each key's optionality and the primitive
types; this test owns the claim that the schema, the producer and the front model agree.

Two findings this test produced on its first runs, both recorded rather than patched away:
  * `coverage.scope` is `None` in the producer's minimal output. The schema's first draft said `string`, read
    off a single full readback. The front model was already right (`types.ts` said `string | null`), so the
    schema was the wrong party and is the one that changed.
  * `GitMatchState` declared `'MATCH' | 'UNVERIFIED' | 'DRIFT' | 'UNKNOWN'` while `_git_match_state` returns
    six values, three of which were un-declarable and two of which could never arrive. The union and five test
    fixtures moved to the producer's real vocabulary; `test_git_match_state_union_covers_every_producer_branch`
    is the guard that keeps the three sides together.
"""
from __future__ import annotations

import copy
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "packages" / "client-neutral-core" / "scripts"))

import snapshot_api  # noqa: E402  (path injection above is how every test here imports the producer)
from jsonschema import Draft202012Validator  # noqa: E402

SCHEMA_PATH = ROOT / "packages/contracts/schemas/workflow/snapshot-v3.schema.json"
TYPES_PATH = ROOT / "apps/observer/frontend/src/types.ts"
CATALOG_PATH = ROOT / ".project/governance/contracts/contract-catalog.json"

MIN_PRODUCER_KEYS = 20  # measured floor; a parse that sees fewer keys has not parsed the payload
OPTIONAL_KEYS = {"software", "taskRecords", "adapterCapabilities",
                 "artifactHandles", "artifactHandlesSummary", "collectors",
                 # Added 2026-10-13. Both are optional for the same reason as the five above and it has to
                 # be said explicitly rather than inherited: absent means nothing read the source, and the
                 # snapshot_api builder only emits each section when a producer handed it rows
                 # (`**({"operationProgress": operation_progress} if operation_progress is not None else {})`).
                 # An empty array would claim "read it, there was nothing"; the key being absent says
                 # "nobody read it", which is the honest one. This gate was RED at HEAD before this line and
                 # nothing could see it: the module is pytest-style (module-level `def test_*()` with bare
                 # asserts) while the canonical gate discovers unittest classes, so the runner never
                 # collected it. Found by running the module directly.
                 "operationProgress", "isolatedTrials",
                 # Added 2026-10-22 with the issue centre. Same rule, stated again because it is the rule
                 # and not an accident of one section: absent means no source answered, [] means every
                 # source answered and held nothing. The producer (issue_projection.load_issues) returns
                 # (None, None, reason) in the first case, so the builder emits neither key at all.
                 "issues", "issuesSummary"}


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def minimal_payload() -> dict:
    """What the producer answers with nothing upstream: the shape the Observer actually shows offline."""
    return snapshot_api.build_snapshot(revision=7)


def full_payload() -> dict:
    return snapshot_api.build_snapshot(
        revision=9,
        projects=[{"projectId": "work-lab", "displayName": "WORK-LAB",
                    "agentPlatform": "codex", "workingAreas": ["apps/observer"]}],
        executions=[{"executionId": "ex-1", "state": "RUNNING",
                     "anchorProjectId": "work-lab", "sourceRef": "git:1"}],
        ci_runs=[{"runId": "r1", "projectId": "work-lab", "workflow": "w", "headSha": "a" * 40,
                  "status": "completed", "conclusion": "success", "sourceRef": "gh:1"}],
        usage=[{"inputTokens": 10, "outputTokens": 5, "cachedTokens": 2, "provider": "p",
               "model": "m", "costUsd": 0.1, "costQuality": "EXACT"}],
        git_state={"localSha": "a" * 40, "remoteSha": "a" * 40, "ciSha": "a" * 40},
        transport={"transportState": "LIVE", "freshnessState": "FRESH",
                   "eventsUrl": "http://127.0.0.1:1/api/v1/events", "eventStreamConnected": True},
        governance={"state": "CLEAN"},
        workspace={"plan": {}},
        source_watermark="2026-10-09T00:00:00Z",
        generated_at="2026-10-09T00:00:01.5Z",
        software=[{"softwareId": "hermes", "displayName": "Hermes",
                   "locationStatus": "FOUND", "duplicateInstallation": False}],
        task_records=[{"taskId": "WL-1", "projectId": "work-lab", "status": "WAITING_APPROVAL",
                      "checkpointPresent": False, "checkpointKeys": []}],
        adapter_capabilities=[{"clientId": "codex",
                               "layers": [{"layer": "REGISTERED", "state": "MET"}]}],
        artifact_handles=[{"handle": "D:/x/y.txt", "surface": "reports", "kind": "report",
                           "sizeBytes": 10, "modifiedAt": "2026-10-09T00:00:00Z",
                           "surfaceRoot": "D:/x", "digestRecorded": False}],
        artifact_handles_summary={"schemaVersion": "work-lab/artifact-handles-summary/v1",
                                  "cap": 200, "enumeratedCount": 1, "projectedCount": 1,
                                  "omittedCount": 0, "truncated": False,
                                  "orderingKey": "modifiedAt", "refused": {"sensitiveNames": 0}},
        collector_delivery=[{"collector": "usage-files", "totalRuns": 4,
                             "lastRunAt": "2026-10-10T00:00:00Z", "lastSuccessAt": "2026-10-10T00:00:00Z",
                             "consecutiveFailures": 0, "circuitOpen": False, "droppedEvents": 1,
                             "refusedRows": 2, "deliveredRows": 11,
                             "lastRefusalReason": "2 row(s) refused, most frequent reason: ValueError: "
                                                  "sensitive value(s) at: ['provider'] (first seen at usage.jsonl:7)",
                             "fresh": True}],
    )


def declared_front_model() -> tuple[set[str], set[str]]:
    """(required, optional) names from `export interface SnapshotV3 { ... }`, parsed the same way the
    production-surface static contract parses it, so the two checks cannot quietly disagree."""
    types = TYPES_PATH.read_text(encoding="utf-8")
    block = re.search(r"export interface SnapshotV3 \{([\s\S]*?)\n\}", types)
    assert block, "types.ts must declare SnapshotV3 — if it was renamed, this check has to say so"
    required: set[str] = set()
    optional: set[str] = set()
    for name, mark in re.findall(r"^\s+(\w+)(\??):", block.group(1), re.M):
        (optional if mark == "?" else required).add(name)
    return required, optional


def validator() -> Draft202012Validator:
    Draft202012Validator.check_schema(schema())
    return Draft202012Validator(schema())


def errors_of(payload: dict) -> list[str]:
    return sorted(f"{list(e.path)}: {e.message}" for e in validator().iter_errors(payload))


def test_schema_is_a_valid_draft_2020_12_document() -> None:
    Draft202012Validator.check_schema(schema())


def test_the_contract_is_catalogued_and_generated() -> None:
    catalog = json.loads(CATALOG_PATH.read_text(encoding="utf-8"))
    entry = next((c for c in catalog["contracts"] if c["id"] == "workflow-snapshot-v3"), None)
    assert entry, "workflow/snapshot/v3 must be in the contract catalog to be part of the SSOT"
    assert entry["schemaPath"].endswith("snapshot-v3.schema.json")
    assert "observer" in entry["consumers"], "the reading side must be a named consumer"
    generated = (ROOT / "packages/client-neutral-core/generated/contracts.ts").read_text(encoding="utf-8")
    assert "// @contract workflow-snapshot-v3" in generated, (
        "the catalog entry exists but the generated TypeScript projection does not carry it; re-run "
        "scripts/ci/generate_contract_types.py")


def test_producer_output_validates_minimal_and_full() -> None:
    assert errors_of(minimal_payload()) == [], "the producer's own minimal answer must satisfy the SSOT"
    assert errors_of(full_payload()) == [], "the producer's full answer must satisfy the SSOT"


def test_schema_key_set_equals_the_front_model_declaration_in_both_directions() -> None:
    doc = schema()
    declared = set(doc["properties"])
    required, optional = declared_front_model()
    assert declared, "parsed no properties from the schema"
    assert len(declared) >= MIN_PRODUCER_KEYS, (
        f"schema declares {len(declared)} top-level keys, below the measured floor "
        f"{MIN_PRODUCER_KEYS}; a schema that lost sections reads as a clean document")
    assert required == set(doc["required"]), (
        "required keys differ between the schema and types.ts: "
        f"schema-only={sorted(required ^ set(doc['required']))}")
    assert optional == declared - required, (
        "optional keys differ between the schema and types.ts: "
        f"schema-only={sorted((declared - required) ^ optional)}")
    assert optional == OPTIONAL_KEYS, (
        "the optional set changed; each member is optional because absent means the source was not read, "
        f"and that has to be adjudicated, not inherited: {sorted(optional)}")
    for payload in (minimal_payload(), full_payload()):
        absent = required - set(payload)
        assert not absent, f"producer omitted required keys: {sorted(absent)}"
        unexpected = set(payload) - declared
        assert not unexpected, f"payload carries keys outside the SSOT: {sorted(unexpected)}"
        # Every key the producer does emit beyond `required` must be one the front model marked optional;
        # a key emitted always but declared `?` in TypeScript is the same lie in the other direction.
        emitted_optional = set(payload) & optional
        assert set(payload) - required == emitted_optional, (
            "the producer emits a key that no side classifies as optional")


def test_an_undeclared_top_level_key_is_refused() -> None:
    """additionalProperties:false is the whole point of registering the shape: a producer that starts
    emitting a new key must fail here instead of arriving as a field the UI cannot name."""
    payload = full_payload()
    payload["brandNewProjection"] = {"anything": 1}
    messages = errors_of(payload)
    assert any("brandNewProjection" in m for m in messages), (
        "a top-level key outside the SSOT validated clean — the schema stopped being an authority")


def test_the_handle_list_and_its_scope_report_travel_together() -> None:
    handles = full_payload()
    assert errors_of(handles) == []

    list_without_scope = copy.deepcopy(handles)
    del list_without_scope["artifactHandlesSummary"]
    assert errors_of(list_without_scope), (
        "artifactHandles without artifactHandlesSummary validated: an enumeration with no stated scope "
        "reads as a complete list whether or not it is one")

    scope_without_list = copy.deepcopy(handles)
    del scope_without_list["artifactHandles"]
    assert errors_of(scope_without_list), (
        "artifactHandlesSummary without artifactHandles validated: a scope report for a list the snapshot "
        "does not carry is a claim about a payload nobody is reading")


def test_the_schema_agrees_with_the_python_validators_own_refusals() -> None:
    """Two authorities that disagree are worse than one. Where both sides state a rule, they must refuse
    the same payload; the Python validator keeps the semantic rules and this checks the shared ones."""
    broken = minimal_payload()
    broken["revision"] = -1
    assert errors_of(broken), "schema accepted a negative revision the validator refuses"
    result = _run_semantic_validator(broken)
    assert not result["valid"], "snapshot_validator accepted a negative revision; the two sides differ"

    wrong_version = minimal_payload()
    wrong_version["schemaVersion"] = "workflow/snapshot/v2"
    assert errors_of(wrong_version)
    assert not _run_semantic_validator(wrong_version)["valid"]


def _run_semantic_validator(payload: dict) -> dict:
    import snapshot_validator
    return snapshot_validator.validate_snapshot(payload)


def test_git_match_state_union_covers_every_producer_branch() -> None:
    """The union in types.ts, the enum in the schema, and the six branches of _git_match_state are the same
    fact stated three times. Before this check two of the six were un-nameable in TypeScript and the union
    carried two values the function never returns."""
    cases = [
        ({"localSha": "a", "remoteSha": "a", "ciSha": "a"}, "MATCH"),
        ({"localSha": "a", "remoteSha": "a", "ciSha": "b"}, "LOCAL_REMOTE_MATCH"),
        ({"localSha": "a", "remoteSha": "b", "ciSha": "a"}, "LOCAL_CI_MATCH"),
        ({"localSha": None, "remoteSha": None, "ciSha": None}, "NO_LOCAL_CLAIM"),
        ({"localSha": "a", "remoteSha": None, "ciSha": None}, "UNVERIFIED"),
        ({"localSha": "a", "remoteSha": "b", "ciSha": "c"}, "MISMATCH"),
    ]
    produced = set()
    for state, expected in cases:
        got = snapshot_api._git_match_state(state)
        assert got == expected, f"_git_match_state({state}) returned {got!r}, expected {expected!r}"
        produced.add(got)

    doc_enum = set(schema()["properties"]["git"]["properties"]["matchState"]["enum"])
    assert doc_enum == produced, (
        f"schema enum and producer branches differ: schema-only={sorted(doc_enum - produced)} "
        f"producer-only={sorted(produced - doc_enum)}")

    types_text = TYPES_PATH.read_text(encoding="utf-8")
    # types.ts writes unions without semicolons, so the declaration is bounded by its own leading-pipe
    # lines rather than by a terminator that does not exist in this file.
    declaration = re.search(r"export type GitMatchState =((?:\s*\|[^\n]*)+)", types_text)
    assert declaration, "types.ts no longer declares GitMatchState as a leading-pipe union"
    members = set(re.findall(r"'([A-Z_]+)'", declaration.group(1)))
    assert members == doc_enum


# The row level got the same treatment as the top level, because the top level was not enough. ERR-225 was
# counted at the top level only: `projects.items` declared seven of the seventeen keys the row builder emits
# and left additionalProperties unset, so ten projected facts — including the whole `git` and `token` blocks —
# sat outside the SSOT while every gate here stayed green.

def project_row(**overrides: object) -> dict:
    """One row straight from the producer, so the guard reads the code rather than a fixture I typed."""
    import snapshot_api
    base: dict = {"projectId": "work-lab", "displayName": "WORK-LAB"}
    base.update(overrides)
    return snapshot_api._project_projection(base, [], {}, None, [])


def declared_interface(name: str) -> tuple[dict[str, str], set[str]]:
    """`export interface <name> { ... }` -> (field -> TS type text, names carrying `?`).

    One parser for every interface these guards read, so a nested section cannot be checked by a different
    reading of the front model than the project row is.
    """
    types = TYPES_PATH.read_text(encoding="utf-8")
    block = re.search(rf"export interface {name} \{{([\s\S]*?)\n\}}", types)
    assert block, f"types.ts must declare interface {name} — if it was renamed, this check has to say so"
    fields: dict[str, str] = {}
    optional: set[str] = set()
    for field_name, mark, ts_type in re.findall(r"^\s+(\w+)(\??):\s*([^;]+?)$", block.group(1), re.M):
        fields[field_name] = ts_type.strip()
        if mark == "?":
            optional.add(field_name)
    assert fields, f"parsed no fields from interface {name}"
    return fields, optional


def declared_row_model() -> tuple[dict[str, str], set[str]]:
    return declared_interface("Project")


def schema_allows_null(prop: dict) -> bool:
    declared = prop.get("type")
    if isinstance(declared, list):
        return "null" in declared
    if declared == "null":
        return True
    return "null" in prop.get("enum", [])


def test_the_project_row_key_set_is_agreed_by_producer_schema_and_front_model() -> None:
    producer_keys = set(project_row())
    section = schema()["properties"]["projects"]["items"]
    schema_keys = set(section["properties"])
    ts_fields, ts_optional = declared_row_model()
    assert producer_keys, "the producer emitted no keys — the row builder was not reached"
    assert len(producer_keys) >= 10, (
        f"the row builder emitted {len(producer_keys)} keys; below the measured floor, so the probe lost its "
        "inputs rather than the producer losing keys")
    assert schema_keys == producer_keys, (
        f"schema row and producer row disagree: schema-only={sorted(schema_keys - producer_keys)} "
        f"producer-only={sorted(producer_keys - schema_keys)}")
    assert set(ts_fields) == producer_keys, (
        f"types.ts Project and the producer row disagree: ts-only={sorted(set(ts_fields) - producer_keys)} "
        f"producer-only={sorted(producer_keys - set(ts_fields))}")
    assert set(section["required"]) == producer_keys, (
        "the row builder emits every key on every row, so an optional key in the schema is a promise the "
        "front end may rely on and the producer never made")
    assert not ts_optional, (
        f"types.ts marks row keys optional: {sorted(ts_optional)} — the producer always emits them, and an "
        "optional field on the reading side licenses null-handling for data that is never null")
    assert section["additionalProperties"] is False, (
        "the row section is open again, which is the exact hole that let ten keys ride outside the SSOT")


def test_row_field_nullability_matches_between_schema_and_front_model() -> None:
    """`string | null` and `string` are different claims about the same field, and the UI branches on them."""
    section = schema()["properties"]["projects"]["items"]["properties"]
    ts_fields, _ = declared_row_model()
    mismatched = []
    for name, ts_type in sorted(ts_fields.items()):
        if name not in section:
            continue
        ts_nullable = "| null" in ts_type
        if ts_nullable != schema_allows_null(section[name]):
            mismatched.append((name, ts_type, section[name].get("type")))
    assert not mismatched, f"nullability disagrees: {mismatched}"


def test_the_row_identifier_lists_carry_no_null_item() -> None:
    """`executionIds` used to be a bare .get() while `sourceRefs` right below it filtered, and types.ts
    declared string[] for both. An id the projection does not have must not be announced as one."""
    import snapshot_api
    section = schema()["properties"]["projects"]["items"]["properties"]
    for name in ("executionIds", "sourceRefs", "workingAreas"):
        items = section[name]["items"]
        assert items == {"type": "string"}, f"{name} items must be exactly string, got {items}"

    row = snapshot_api._project_projection(
        {"projectId": "p"}, [{"executionId": None, "anchorProjectId": "p", "state": "RUNNING"}],
        {}, None, [])
    assert row["executionIds"] == [], (
        f"the join emitted {row['executionIds']!r} for an execution with no id")
    assert row["activeExecutionCount"] == 1, (
        "dropping the id must not drop the activity count — the execution really is there, it just has no name")
    with_id = snapshot_api._project_projection(
        {"projectId": "p"}, [{"executionId": "ex-1", "anchorProjectId": "p", "state": "RUNNING"}],
        {}, None, [])
    assert with_id["executionIds"] == ["ex-1"]


def test_an_undeclared_key_inside_a_project_row_is_refused() -> None:
    payload = full_payload()
    assert errors_of(payload) == []
    payload["projects"][0]["brandNewRowFact"] = {"anything": 1}
    messages = errors_of(payload)
    assert any("brandNewRowFact" in m for m in messages), (
        "a key inside projects[] that no side declares validated clean — the nested section stopped being "
        "an authority even though the top level still refuses")


def test_a_row_missing_one_of_its_own_required_keys_is_refused() -> None:
    """Closing the section proves what arrives; `required` proves what must. A row that lost `git` would
    otherwise render an empty column instead of a named gap."""
    payload = full_payload()
    del payload["projects"][0]["git"]
    messages = errors_of(payload)
    assert any("git" in m for m in messages), f"a row without its git block validated: {messages}"

def test_the_collector_row_keys_are_agreed_by_producer_schema_and_front_model() -> None:
    """The section ERR-256 made durable: same key set on all three sides, closed row, declared nullability."""
    import composition_root
    import project_temp
    from canonical_store import CanonicalStore

    directory = project_temp.fixture_dir("schema-collector-row-")
    store = CanonicalStore(directory / "canonical.sqlite")
    try:
        store.upsert_collector_health({"name": "usage-files", "totalRuns": 3,
                                       "lastRunAt": "2026-10-10T00:00:00Z",
                                       "lastSuccessAt": "2026-10-10T00:00:00Z", "consecutiveFailures": 0,
                                       "circuitOpenUntil": None, "droppedCount": 1, "refusedRows": 2,
                                       "lastRefusalReason": "2 row(s) refused"})
        emitted = composition_root._collector_delivery_rows(store)
    finally:
        store.close()
        project_temp.force_release(directory)
    assert emitted and len(emitted) == 1
    producer_keys = set(emitted[0])

    section = schema()["properties"]["collectors"]["items"]
    assert set(section["properties"]) == producer_keys, (
        f"schema row and producer row disagree: schema-only={sorted(set(section['properties']) - producer_keys)} "
        f"producer-only={sorted(producer_keys - set(section['properties']))}")
    assert set(section["required"]) == producer_keys
    assert section["additionalProperties"] is False, (
        "the collectors row is open again — ERR-255's nested-section hole, re-dug in a new section")

    ts_fields, ts_optional = declared_interface("CollectorDelivery")
    assert set(ts_fields) == producer_keys, (
        f"types.ts CollectorDelivery disagrees with the producer: ts-only={sorted(set(ts_fields) - producer_keys)} "
        f"producer-only={sorted(producer_keys - set(ts_fields))}")
    assert not ts_optional, f"row fields marked optional in the front model: {sorted(ts_optional)}"
    mismatched = [(name, ts_fields[name], section["properties"][name].get("type"))
                  for name in sorted(ts_fields)
                  if ("| null" in ts_fields[name]) != schema_allows_null(section["properties"][name])]
    assert not mismatched, f"nullability disagrees on the collector row: {mismatched}"
    # The monotonic clock value must never reach the payload; only the derived boolean may.
    assert "circuitOpenUntil" not in producer_keys and "circuitOpen" in producer_keys, (
        "`circuit_open_until` is another process's time.monotonic() reading; projecting it invites a reader "
        "to interpret a number that means nothing outside its process")


def test_the_collector_section_is_absent_rather_than_empty_when_health_cannot_be_read() -> None:
    payload = minimal_payload()
    assert "collectors" not in payload, (
        "the minimal producer output must not carry a section the producer never built — presence of the key "
        "is the claim that health was read")
    assert errors_of(payload) == []

    with_none = full_payload()
    del with_none["collectors"]
    assert errors_of(with_none) == [], "the section must stay optional"

    empty = full_payload()
    empty["collectors"] = []
    assert errors_of(empty) == [], "an empty list is a legitimate different statement, not an error"


def test_an_undeclared_key_inside_a_collector_row_is_refused() -> None:
    payload = full_payload()
    assert errors_of(payload) == []
    payload["collectors"][0]["inventedFact"] = 7
    messages = errors_of(payload)
    assert any("inventedFact" in m for m in messages), (
        f"a key inside collectors[] validated clean: {messages}")


def test_a_negative_counter_in_a_collector_row_is_refused() -> None:
    """`minimum: 0` is what keeps a refused-row count from being displayed as a negative delivery."""
    payload = full_payload()
    payload["collectors"][0]["refusedRows"] = -3
    assert any("refusedRows" in m for m in errors_of(payload)), (
        "a negative refusal count validated: the floor is decoration")


# The rule "no v3 snapshot object is embedded in the production front" is NOT re-implemented here. It already
# lives in apps/observer/tests/test_production_surface_static_contract.js, which anchors on the assignment
# shape (`schemaVersion: "workflow/snapshot/v3"` as a property of a payload) precisely so that api.ts's own
# parseSnapshotPayload — which COMPARES the id — is not convicted. A first draft of this file grepped for the
# bare string instead and failed on types.ts, api.ts and the excluded fixture directory: three correct hits
# and a false premise. One guard per question, and the disagreement is recorded rather than duplicated.
