# SPDX-License-Identifier: MIT
"""DL-P0-021 Operation lineage: why a version exists, and what depends on it.

Every producing operation records its provider, model, parameter digest and the
exact input versions it consumed. Two invariants are enforced:

* one version has exactly one producing operation (re-producing creates a new
  version, never a silent rewrite);
* ``produced_from`` relationships are acyclic, so impact analysis terminates.

The same graph answers the partial-regeneration question (DL-P0-081): given a
changed version, which downstream outputs are stale.
"""
from __future__ import annotations

import sqlite3

from .store import CreativeError, hash_document, new_id, now, require_job, transaction


def _version(conn, version_id: str) -> None:
    if not isinstance(version_id, str) or not version_id.strip():
        raise CreativeError("version_id must be a nonempty string")
    if not conn.execute("SELECT 1 FROM asset_version WHERE version_id=?", (version_id,)).fetchone():
        raise CreativeError(f"unknown asset version: {version_id!r}")


def _links(items, field: str) -> list:
    links = []
    for item in items:
        if isinstance(item, dict):
            version_id, role = item.get("version_id"), item.get("role", field)
        elif isinstance(item, (tuple, list)) and len(item) == 2:
            version_id, role = item
        else:
            raise CreativeError(f"{field} entries must be (version_id, role) pairs or objects")
        if not isinstance(role, str) or not role.strip():
            raise CreativeError(f"{field} role must be a nonempty string")
        links.append((version_id, role))
    if len({(v, r) for v, r in links}) != len(links):
        raise CreativeError(f"duplicate {field} link")
    return links


def record_operation(conn, *, job_id: str, operation_id: str, provider_id: str, inputs=(), outputs=(),
                     model_id=None, params=None, attempt_id=None) -> dict:
    """Record one producing operation. Identical replay is idempotent."""
    require_job(conn, job_id)
    if not isinstance(operation_id, str) or not operation_id.strip():
        raise CreativeError("operation_id must be a nonempty string")
    if not conn.execute("SELECT 1 FROM operation_intent WHERE operation_id=?", (operation_id,)).fetchone():
        raise CreativeError("unknown operation: register the operation intent before recording its lineage")
    if not isinstance(provider_id, str) or not provider_id.strip():
        raise CreativeError("provider_id must be a nonempty string")
    link_in = _links(inputs, "input")
    link_out = _links(outputs, "output")
    if not link_out:
        raise CreativeError("a producing operation must declare at least one output version")
    for version_id, _ in link_in + link_out:
        _version(conn, version_id)
    params_sha256 = hash_document(params or {})
    if model_id is not None and (not isinstance(model_id, str) or not model_id.strip()):
        raise CreativeError("model_id must be a nonempty string or null")

    with transaction(conn):
        existing = conn.execute("SELECT lineage_id, job_id, provider_id, model_id, params_sha256, attempt_id "
                                "FROM operation_lineage WHERE operation_id=?", (operation_id,)).fetchone()
        if existing:
            recorded = _links([(row[0], row[1]) for row in
                               conn.execute("SELECT version_id, role FROM lineage_input WHERE lineage_id=?",
                                            (existing[0],))], "input")
            produced = sorted(row[0] for row in
                              conn.execute("SELECT version_id FROM lineage_output WHERE lineage_id=?",
                                           (existing[0],)))
            if (existing[1:5] != (job_id, provider_id, model_id, params_sha256)
                    or sorted(recorded) != sorted(link_in) or produced != sorted(v for v, _ in link_out)):
                raise CreativeError("operation lineage is immutable: replay does not match the recorded operation")
            return {"lineage_id": existing[0], "operation_id": operation_id, "created": False,
                    "params_sha256": params_sha256}
        lineage_id = new_id("lin")
        try:
            conn.execute("INSERT INTO operation_lineage VALUES (?,?,?,?,?,?,?,?)",
                         (lineage_id, operation_id, job_id, provider_id, model_id, params_sha256, attempt_id, now()))
            for version_id, role in link_in:
                conn.execute("INSERT INTO lineage_input VALUES (?,?,?)", (lineage_id, version_id, role))
            for version_id, role in link_out:
                conn.execute("INSERT INTO lineage_output VALUES (?,?,?)", (lineage_id, version_id, role))
        except sqlite3.IntegrityError as exc:
            raise CreativeError(f"lineage conflict: the version already has a producing operation ({exc})") from exc
        return {"lineage_id": lineage_id, "operation_id": operation_id, "created": True,
                "params_sha256": params_sha256}


def lineage(conn, operation_id: str) -> dict:
    row = conn.execute("SELECT lineage_id, job_id, provider_id, model_id, params_sha256, attempt_id, recorded_at "
                       "FROM operation_lineage WHERE operation_id=?", (operation_id,)).fetchone()
    if not row:
        raise CreativeError(f"no recorded lineage for operation: {operation_id!r}")
    return {"lineage_id": row[0], "operation_id": operation_id, "job_id": row[1], "provider_id": row[2],
            "model_id": row[3], "params_sha256": row[4], "attempt_id": row[5], "recorded_at": row[6],
            "inputs": inputs_of(conn, operation_id), "outputs": outputs_of(conn, operation_id)}


def inputs_of(conn, operation_id: str) -> list:
    return [{"version_id": row[0], "role": row[1]} for row in conn.execute(
        "SELECT i.version_id, i.role FROM lineage_input i JOIN operation_lineage l USING (lineage_id) "
        "WHERE l.operation_id=? ORDER BY i.version_id, i.role", (operation_id,))]


def outputs_of(conn, operation_id: str) -> list:
    return [{"version_id": row[0], "role": row[1]} for row in conn.execute(
        "SELECT o.version_id, o.role FROM lineage_output o JOIN operation_lineage l USING (lineage_id) "
        "WHERE l.operation_id=? ORDER BY o.version_id, o.role", (operation_id,))]


def producer_of(conn, version_id: str) -> dict:
    row = conn.execute("SELECT l.operation_id, l.provider_id, l.model_id, l.params_sha256, l.job_id, l.attempt_id "
                       "FROM lineage_output o JOIN operation_lineage l USING (lineage_id) WHERE o.version_id=?",
                       (version_id,)).fetchone()
    if not row:
        raise CreativeError(f"version has no recorded producer (root or unrecorded): {version_id!r}")
    return {"version_id": version_id, "operation_id": row[0], "provider_id": row[1], "model_id": row[2],
            "params_sha256": row[3], "job_id": row[4], "attempt_id": row[5]}


def explain_version(conn, version_id: str) -> dict:
    """Provenance chain for one version, stopping at unrecorded roots."""
    chain, frontier, seen = [], [version_id], set()
    while frontier:
        current = frontier.pop()
        if current in seen:
            continue
        seen.add(current)
        try:
            produced = producer_of(conn, current)
        except CreativeError:
            chain.append({"version_id": current, "operation": None, "origin": "ROOT_OR_UNRECORDED"})
            continue
        chain.append({"version_id": current, "operation": produced["operation_id"],
                      "provider_id": produced["provider_id"], "model_id": produced["model_id"],
                      "params_sha256": produced["params_sha256"], "origin": "RECORDED"})
        frontier.extend(link["version_id"] for link in inputs_of(conn, produced["operation_id"]))
    return {"version_id": version_id, "chain": chain, "complete": all(n["origin"] == "RECORDED" for n in chain)}


def ancestors(conn, version_id: str) -> list:
    """Every version this one transitively consumed (excluding itself)."""
    return sorted(_walk(conn, {version_id}, _upstream) - {version_id})


def descendants(conn, version_id: str) -> list:
    """Every version transitively derived from this one (impact set)."""
    return sorted(_walk(conn, {version_id}, _downstream) - {version_id})


def impacted_outputs(conn, version_ids) -> list:
    changed = set(version_ids)
    for version_id in list(changed):
        _version(conn, version_id)
    return sorted(_walk(conn, set(changed), _downstream) - changed)


def _upstream(conn, version_id: str) -> set:
    try:
        produced = producer_of(conn, version_id)
    except CreativeError:
        return set()
    return {link["version_id"] for link in inputs_of(conn, produced["operation_id"])}


def _downstream(conn, version_id: str) -> set:
    consumers = conn.execute("SELECT DISTINCT l.operation_id FROM lineage_input i "
                             "JOIN operation_lineage l USING (lineage_id) WHERE i.version_id=?",
                             (version_id,)).fetchall()
    result = set()
    for (operation_id,) in consumers:
        result.update(link["version_id"] for link in outputs_of(conn, operation_id))
    return result


def _walk(conn, frontier: set, step) -> set:
    seen = set()
    pending = list(frontier)
    while pending:
        current = pending.pop()
        if current in seen:
            continue
        seen.add(current)
        pending.extend(step(conn, current) - seen)
    return seen


def verify_acyclic(conn) -> int:
    """Fail closed on a lineage cycle; returns the number of versions visited."""
    colors, visited = {}, 0

    def visit(version_id, stack):
        nonlocal visited
        color = colors.get(version_id)
        if color == "GREY":
            raise CreativeError("lineage cycle detected: " + " -> ".join([*stack, version_id]))
        if color == "BLACK":
            return
        colors[version_id] = "GREY"
        for child in _downstream(conn, version_id):
            visit(child, [*stack, version_id])
        colors[version_id] = "BLACK"
        visited += 1

    for (version_id,) in conn.execute("SELECT version_id FROM asset_version").fetchall():
        visit(version_id, [])
    return visited


def job_graph(conn, job_id: str) -> dict:
    require_job(conn, job_id)
    rows = conn.execute("SELECT operation_id, provider_id, model_id, params_sha256 FROM operation_lineage "
                        "WHERE job_id=? ORDER BY operation_id", (job_id,)).fetchall()
    nodes, edges = [], []
    for operation_id, provider_id, model_id, params_sha256 in rows:
        produced = [link["version_id"] for link in outputs_of(conn, operation_id)]
        consumed = [link["version_id"] for link in inputs_of(conn, operation_id)]
        nodes.append({"operation_id": operation_id, "provider_id": provider_id, "model_id": model_id,
                      "params_sha256": params_sha256, "inputs": consumed, "outputs": produced})
        edges.extend({"from_version": version_id, "to_version": output}
                     for version_id in consumed for output in produced)
    try:
        verify_acyclic(conn)
    except CreativeError as exc:
        return {"job_id": job_id, "nodes": nodes, "edges": edges, "acyclic": False, "note": str(exc)}
    return {"job_id": job_id, "nodes": nodes, "edges": edges, "acyclic": True}


def params_digest(params) -> str:
    """Public helper so callers hash provider parameters the same way."""
    return hash_document(params or {})
