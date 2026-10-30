# SPDX-License-Identifier: MIT
"""DL-P0-080 ComfyUI workflow provider: validate the graph, never run it here.

ComfyUI already defines the workflow format and the REST/WebSocket API. This
module adopts both instead of inventing a node-graph dialect:

* the *UI* workflow document (``nodes``/``links`` arrays as ComfyUI saves them);
* the *API* prompt graph (``{node_id: {class_type, inputs}}``) that the API
  actually accepts.

It validates graph integrity, binds declared inputs to recorded asset versions,
and computes a position-independent fingerprint so the same design intent keeps
one identity when a node is merely moved on the canvas. ``execute`` is not
implemented by design: dispatching to a live ComfyUI server belongs to the host
side and stays NOT_EXECUTED here.
"""
from __future__ import annotations

import copy
import json

from jsonschema import Draft202012Validator

from ...adapters.spi import ProviderAdapter
from ...runtime.attempt_contract import request_hash
from ...runtime.paths import PROJECT_ROOT
from .errors import GenerativeError

ADAPTER_CONTRACT_SCHEMA = PROJECT_ROOT / "design-lab/schemas/adapter-contract.schema.json"
PROVIDER_SCHEMA = PROJECT_ROOT / "design-lab/schemas/provider-capability.schema.json"
UI_SCHEMA_VERSIONS = (0.4,)
LINK_FIELDS = 6
CAPABILITY = "image.generate.workflow"


def _require(condition, message):
    if not condition:
        raise GenerativeError(message)


def _nodes(document) -> dict:
    return {node["id"]: node for node in document["nodes"]}


def _slot_names(node, key) -> list:
    return [entry.get("name") for entry in node.get(key, [])]


def validate_ui_workflow(document) -> dict:
    """Validate a ComfyUI UI workflow graph; return a normalized summary.

    Structural integrity only: identity, link endpoints and slot bounds. The
    observed document version is reported, never assumed.
    """
    _require(isinstance(document, dict), "workflow document must be an object")
    _require(isinstance(document.get("nodes"), list), "workflow requires a nodes array")
    _require(isinstance(document.get("links"), list), "workflow requires a links array")
    version = document.get("version")
    if version is not None:
        _require(version in UI_SCHEMA_VERSIONS,
                 f"unsupported ComfyUI workflow version {version!r}; supported: {list(UI_SCHEMA_VERSIONS)}")
    nodes, seen = {}, set()
    for node in document["nodes"]:
        _require(isinstance(node, dict), "every node must be an object")
        node_id, class_type = node.get("id"), node.get("type")
        _require(isinstance(node_id, int) and not isinstance(node_id, bool), "node id must be an integer")
        _require(node_id not in seen, f"duplicate node id {node_id}")
        _require(isinstance(class_type, str) and class_type.strip(), f"node {node_id} requires a class type")
        for key in ("inputs", "outputs"):
            _require(isinstance(node.get(key, []), list), f"node {node_id} {key} must be an array")
        seen.add(node_id)
        nodes[node_id] = node

    links, link_ids = {}, set()
    for raw in document["links"]:
        _require(isinstance(raw, (list, tuple)) and len(raw) >= LINK_FIELDS,
                 "a link must be [link_id, origin_id, origin_slot, target_id, target_slot, type]")
        link_id, origin_id, origin_slot, target_id, target_slot = raw[:5]
        _require(link_id not in link_ids, f"duplicate link id {link_id}")
        link_ids.add(link_id)
        _require(origin_id in nodes, f"link {link_id} references unknown origin node {origin_id}")
        _require(target_id in nodes, f"link {link_id} references unknown target node {target_id}")
        _require(isinstance(origin_slot, int) and 0 <= origin_slot < len(nodes[origin_id].get("outputs", [])),
                 f"link {link_id} origin slot {origin_slot} is out of range on node {origin_id}")
        _require(isinstance(target_slot, int) and 0 <= target_slot < len(nodes[target_id].get("inputs", [])),
                 f"link {link_id} target slot {target_slot} is out of range on node {target_id}")
        links[link_id] = tuple(raw[:LINK_FIELDS])

    for node_id, node in nodes.items():
        for index, entry in enumerate(node.get("inputs", [])):
            link_id = entry.get("link") if isinstance(entry, dict) else None
            if link_id is None:
                continue
            _require(link_id in links, f"node {node_id} input {index} references unknown link {link_id}")
            _require(links[link_id][3] == node_id and links[link_id][4] == index,
                     f"link {link_id} does not target node {node_id} input {index}")
    return {"version": version, "node_count": len(nodes), "link_count": len(links),
            "class_types": sorted({node["type"] for node in nodes.values()}),
            "node_ids": sorted(nodes)}


def validate_api_workflow(graph) -> dict:
    """Validate the API prompt graph ComfyUI accepts (no UI wrapper fields)."""
    _require(isinstance(graph, dict) and graph, "api workflow must be a nonempty object")
    for node_id, node in graph.items():
        _require(isinstance(node_id, str), "api workflow keys are node ids as strings")
        _require(isinstance(node, dict), f"api node {node_id} must be an object")
        _require(isinstance(node.get("class_type"), str) and node["class_type"].strip(),
                 f"api node {node_id} requires class_type")
        _require(isinstance(node.get("inputs"), dict), f"api node {node_id} requires an inputs object")
        for name, value in node["inputs"].items():
            if isinstance(value, list) and len(value) == 2 and isinstance(value[0], str):
                _require(value[0] in graph, f"api node {node_id} input {name} references unknown node {value[0]}")
    return {"node_count": len(graph),
            "class_types": sorted({node["class_type"] for node in graph.values()})}


def _canonical_graph(document) -> list:
    """Position-independent view: identity, class, widget values and wiring."""
    nodes = _nodes(document)
    links = {raw[0]: raw for raw in document["links"]}
    canonical = []
    for node_id in sorted(nodes):
        node = nodes[node_id]
        wiring = []
        for name, entry in zip(_slot_names(node, "inputs"), node.get("inputs", [])):
            link_id = entry.get("link") if isinstance(entry, dict) else None
            if link_id is None:
                wiring.append([name, None])
                continue
            link = links[link_id]
            wiring.append([name, [link[1], link[2]]])
        canonical.append([node_id, node["type"], node.get("widgets_values", []), wiring])
    return canonical


def graph_fingerprint(document) -> str:
    """Order- and position-independent identity of a workflow graph."""
    validate_ui_workflow(document)
    return request_hash({"nodes": _canonical_graph(document)})


def widget_names(node) -> list:
    """Widget input names, in the order ``widgets_values`` is stored.

    ComfyUI keeps a node's widget values positionally, in the order of its
    widget inputs; a plain link input contributes no widget value.
    """
    names = []
    for entry in node.get("inputs", []):
        if isinstance(entry, dict) and isinstance(entry.get("widget"), dict):
            name = entry["widget"].get("name")
            if name is not None:
                names.append(name)
    return names


def bind_input(document, node_id: int, input_name: str, value) -> dict:
    """Return a copy with one widget value bound (the original is kept)."""
    validate_ui_workflow(document)
    _require(node_id in _nodes(document), f"unknown node {node_id}")
    clone = copy.deepcopy(document)
    node = _nodes(clone)[node_id]
    names = widget_names(node)
    if input_name not in names:
        raise GenerativeError(f"node {node_id} has no widget input named {input_name!r}; "
                              f"declared widgets: {names}")
    index = names.index(input_name)
    values = list(node.get("widgets_values", []))
    while len(values) <= index:
        values.append(None)
    values[index] = value
    node["widgets_values"] = values
    return clone


def changed_nodes(before, after) -> list:
    """Node ids whose class, widget values or wiring differ between two graphs."""
    validate_ui_workflow(before)
    validate_ui_workflow(after)
    left = {row[0]: row[1:] for row in _canonical_graph(before)}
    right = {row[0]: row[1:] for row in _canonical_graph(after)}
    return sorted(node_id for node_id in set(left) | set(right) if left.get(node_id) != right.get(node_id))


class ComfyWorkflowProvider(ProviderAdapter):
    """Structural provider for ComfyUI workflows. Never dispatches here."""

    adapter_id = "provider:comfy/workflow"
    adapter_type = "provider"
    version = "design-lab/comfy-workflow-provider/v1"

    def probe(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "status": "STRUCTURAL", "evidence_level": "E1",
                "live_probe": "NOT_EXECUTED",
                "capabilities": [{"name": CAPABILITY, "supported": False,
                                  "note": "graph validation and planning only; live dispatch is host-side"}],
                "requires": ["comfyui_server_endpoint", "gpu", "owner_approved_rights_record"]}

    def prepare(self, ctx: dict) -> dict:
        document = ctx.get("workflow")
        _require(document is not None, "prepare requires a workflow document")
        summary = validate_ui_workflow(document)
        return {"adapter_id": self.adapter_id, "workflow_fingerprint": graph_fingerprint(document),
                "summary": summary, "prepared": True, "dispatched": False}

    def execute(self, envelope: dict) -> dict:
        raise GenerativeError(
            "NOT_EXECUTED_STRUCTURAL_ONLY: live ComfyUI dispatch requires a running server endpoint, "
            "GPU execution and a rights-cleared model record; this build performs none of them")

    def observe(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "observed": False, "reason": "NOT_EXECUTED",
                "expected_observations": ["queue state", "history entry", "node timings"]}

    def readback(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "readback": "NOT_EXECUTED",
                "expected_readback": ["output artifact digest", "reopened workflow fingerprint"]}

    def rollback(self, ctx: dict) -> dict:
        return {"adapter_id": self.adapter_id, "rollback": "PLAN_ONLY",
                "steps": ["discard staged outputs for the attempt",
                          "release the asset writer lease",
                          "restore the previous active version reference"]}


def provider_declaration() -> dict:
    """Adapter declaration; validates against the repository adapter contract."""
    declaration = {
        "adapter_id": "adobe-free:comfyui-workflow",
        "tool": "ComfyUI",
        "capabilities": [
            {"name": CAPABILITY, "supported": False, "note": "graph validation only in this build"},
            {"name": "image.generate.dispatch", "supported": False, "note": "requires a live server"},
        ],
        "status": "structural",
        "mode": "external-local-api",
        "license": "unverified",
        "fallback": "manual graph authoring plus structural validation",
        "evidence": {"level": "E1", "runtime_version": None, "task_ids": ["DL-P0-080"],
                     "artifact_paths": [], "note": "structural provider; no live run performed"},
        "rollback": "discard staged outputs and release the asset writer lease",
    }
    schema = json.loads(ADAPTER_CONTRACT_SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(declaration))
    if errors:
        raise GenerativeError(f"provider declaration violates the adapter contract: {errors[0].message}")
    return declaration


def registry_entry() -> dict:
    """Provider-capability registry entry for the shared provider registry."""
    entry = {
        "provider_id": "provider:generative/comfy-workflow",
        "schemaVersion": "design-lab/provider-capability/v1",
        "endpoint_ref": "provider:generative/comfy-workflow",
        "model_ref": None,
        "capabilities": [CAPABILITY],
        "local_first": True,
        "license": "unverified",
        "source": "ComfyUI workflow JSON (UI graph and API prompt graph)",
        "evidence_level": "E1",
        "license_risk": "unknown",
        "license_risk_note": "the ComfyUI distribution licence and the licence of every checkpoint "
                             "must be adjudicated by the owner before bundled delivery (DL-P0-190)",
    }
    schema = json.loads(PROVIDER_SCHEMA.read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema).iter_errors(entry))
    if errors:
        raise GenerativeError(f"registry entry violates the provider capability schema: {errors[0].message}")
    return entry
