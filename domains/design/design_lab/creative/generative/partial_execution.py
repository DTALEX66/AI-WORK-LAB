# SPDX-License-Identifier: MIT
"""DL-P0-081 Partial regeneration: re-run the minimum, reuse only what is safe.

ComfyUI's partial execution re-runs a node and everything downstream of it. That
rule is a safety property, not an optimisation: reusing a node whose ancestor
changed would publish an artifact that no recorded operation produced. This
module computes the minimal sound plan over a validated graph and proves it:
``reuse`` and ``downstream(changed)`` must never intersect.

The plan is structural. It decides what *would* run; it never dispatches.
"""
from __future__ import annotations

from .errors import GenerativeError
from .workflow_provider import validate_ui_workflow


def _edges(document) -> dict:
    """node id -> ids it feeds."""
    targets = {node["id"]: set() for node in document["nodes"]}
    for raw in document["links"]:
        targets[raw[1]].add(raw[3])
    return targets


def _incoming(document) -> dict:
    sources = {node["id"]: set() for node in document["nodes"]}
    for raw in document["links"]:
        sources[raw[3]].add(raw[1])
    return sources


def verify_acyclic(document) -> None:
    """A workflow that contradicts the execution order cannot be planned."""
    validate_ui_workflow(document)
    edges = _edges(document)
    indegree = {node: 0 for node in edges}
    for children in edges.values():
        for child in children:
            indegree[child] += 1
    ready = [node for node, degree in indegree.items() if degree == 0]
    visited = 0
    while ready:
        node = ready.pop()
        visited += 1
        for child in edges[node]:
            indegree[child] -= 1
            if indegree[child] == 0:
                ready.append(child)
    if visited != len(edges):
        stuck = sorted(node for node, degree in indegree.items() if degree > 0)
        raise GenerativeError(f"workflow cycle detected among nodes {stuck}")


def downstream_of(document, node_ids) -> list:
    """Every node transitively fed by the given nodes (excluding themselves)."""
    edges = _edges(document)
    changed = set(node_ids)
    seen, pending = set(), list(changed)
    while pending:
        node = pending.pop()
        for child in edges.get(node, ()):
            if child not in seen:
                seen.add(child)
                pending.append(child)
    return sorted(seen - changed)


def upstream_of(document, node_ids) -> list:
    sources = _incoming(document)
    start = set(node_ids)
    seen, pending = set(), list(start)
    while pending:
        node = pending.pop()
        for parent in sources.get(node, ()):
            if parent not in seen:
                seen.add(parent)
                pending.append(parent)
    return sorted(seen - start)


def plan(document, changed, *, cached=(), terminal=None) -> dict:
    """Minimal sound re-execution plan for a validated workflow.

    ``changed``   node ids whose inputs or parameters changed;
    ``cached``    node ids a caller believes can be reused (checked, not trusted);
    ``terminal``  the output nodes whose artifacts the job actually delivers;
                  defaults to the graph's sink nodes (no outgoing link).
    """
    summary = validate_ui_workflow(document)
    verify_acyclic(document)
    known = set(summary["node_ids"])
    changed = sorted(set(changed))
    if not changed:
        raise GenerativeError("a partial plan requires at least one changed node")
    unknown = sorted(set(changed) - known)
    if unknown:
        raise GenerativeError(f"changed nodes are not in the workflow: {unknown}")
    if terminal is None:
        edges = _edges(document)
        terminals = sorted(node for node in known if not edges[node])
        if not terminals:
            raise GenerativeError("workflow has no terminal node to deliver")
    else:
        terminals = sorted(set(terminal))
    unknown_terminals = sorted(set(terminals) - known)
    if unknown_terminals:
        raise GenerativeError(f"terminal nodes are not in the workflow: {unknown_terminals}")

    stale = set(downstream_of(document, changed))
    rerun = sorted(stale | set(changed))
    requested = set(cached)
    unsafe = sorted(requested & (stale | set(changed)))
    if unsafe:
        raise GenerativeError(f"cannot reuse nodes that changed or are downstream of a change: {unsafe}")
    reuse = sorted(known - set(rerun))
    invalidated = sorted(set(terminals) & set(rerun))
    return {
        "changed": changed,
        "rerun": rerun,
        "reuse": reuse,
        "requested_reuse_honoured": sorted(requested & set(reuse)),
        "invalidated_terminals": invalidated,
        "reused_terminals": sorted(set(terminals) & set(reuse)),
        "delivery_blocked": bool(invalidated),
        "node_count": summary["node_count"],
        "note": "structural plan only; no node was executed",
    }


def assert_plan_sound(plan: dict, document) -> None:
    """Re-derive the safety property from the graph and refuse a bad plan."""
    changed = set(plan["changed"])
    stale = set(downstream_of(document, changed))
    unsafe = sorted(set(plan["reuse"]) & (stale | changed))
    if unsafe:
        raise GenerativeError(f"unsound plan: reuse intersects the re-run set at {unsafe}")
    if not changed <= set(plan["rerun"]):
        raise GenerativeError("unsound plan: a changed node is not scheduled to re-run")
    if set(plan["rerun"]) & set(plan["reuse"]):
        raise GenerativeError("unsound plan: a node is both re-run and reused")
    missing = sorted(set(plan["rerun"]) - {node["id"] for node in document["nodes"]})
    if missing:
        raise GenerativeError(f"unsound plan: unknown nodes scheduled for re-run: {missing}")


def plan_from_lineage(document, node_versions, changed_versions) -> dict:
    """Map a lineage impact set onto a workflow re-run plan.

    ``node_versions``  {node_id: produced version id};
    ``changed_versions`` version ids that changed (already-served artifacts).
    """
    reverse = {}
    for node_id, version_id in node_versions.items():
        reverse.setdefault(version_id, []).append(node_id)
    unknown = sorted(version for version in changed_versions if version not in reverse)
    if unknown:
        raise GenerativeError(f"changed versions are not produced by any workflow node: {unknown}")
    changed_nodes = sorted({node for version in changed_versions for node in reverse[version]})
    result = plan(document, changed_nodes)
    result["changed_versions"] = sorted(changed_versions)
    result["changed_nodes_from_lineage"] = changed_nodes
    return result
