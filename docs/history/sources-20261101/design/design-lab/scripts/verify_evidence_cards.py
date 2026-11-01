#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Fail-closed verifier for Open Design benchmark evidence cards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
CARD_SCHEMA = json.loads((ROOT / "schemas/visual-quality/evidence-card.schema.json").read_text(encoding="utf-8"))
CARD_VALIDATOR = Draft202012Validator(CARD_SCHEMA)
REGISTRY = ROOT / "evals/benchmarks/benchmark-registry.json"
REQUIRED_GATES = {"no-signature-copy", "source-and-license-record"}
# DL-CLOUDAUDIT-B5 (R13): evidence_id is the canonical sha256 of the record's
# substantive fields -- every top-level field except the identity-bearing pair
# below. Appending a revision (new content) or a link (supersedes) therefore
# never moves the identity of the record it points at, while any in-place edit
# of a committed record's substantive fields does.
IDENTITY_EXCLUDED = {"evidence_id", "supersedes"}


def content_identity(card: dict) -> str:
    """DL-CLOUDAUDIT-B5 (R13): the immutable content-bound id of a record."""
    substantive = {key: value for key, value in card.items() if key not in IDENTITY_EXCLUDED}
    canonical = json.dumps(substantive, sort_keys=True, separators=(",", ":"))
    return "sha256:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def verify(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        data = _load(path)
        registry = _load(REGISTRY)
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        return [f"evidence card input unreadable: {exc}"]
    cards = data.get("cards") if isinstance(data, dict) else None
    # DL-CLOUDAUDIT-B5 (R13): append-only revisions add records for an
    # existing card, so the record count covers the benchmark count from
    # above; the benchmark id set check at the end still proves that every
    # benchmark has at least one card.
    if not isinstance(cards, list) or len(cards) < len(registry.get("benchmarks", [])):
        errors.append("card records must cover every benchmark")
        cards = cards if isinstance(cards, list) else []
    if data.get("human_calibration_policy", {}).get("required_for_promotion") is not True:
        errors.append("human calibration policy must require promotion review")
    benchmarks = {entry.get("id"): entry for entry in registry.get("benchmarks", []) if isinstance(entry, dict)}
    schema_valid: list[dict] = []
    for card in cards:
        if not isinstance(card, dict):
            errors.append("card must be an object")
            continue
        schema_errors = sorted(CARD_VALIDATOR.iter_errors(card), key=lambda error: list(error.path))
        if schema_errors:
            errors.append(f"{card.get('card_id', '<unknown>')}: {schema_errors[0].message}")
            continue
        card_id = card["card_id"]
        benchmark_id = card["benchmark_id"]
        # DL-CLOUDAUDIT-B5 (R13): a repeated card_id is legal only as an
        # append-only revision carrying a `supersedes` link. Silent
        # duplicates and all chain invariants (one genesis, no fork/cycle/
        # dangling, identity binding) are validated per card_id group in the
        # B5 pass after this loop.
        schema_valid.append(card)
        benchmark = benchmarks.get(benchmark_id)
        if benchmark is None:
            errors.append(f"{card_id}: unknown benchmark {benchmark_id}")
            continue
        references = card["references"]
        for field, registry_field in (("brief", "brief"), ("rubric", "rubric"), ("evidence_schema", "evidence")):
            if references[field] != benchmark[registry_field]:
                errors.append(f"{card_id}: {field} does not match benchmark registry")
            if not (ROOT / references[field]).is_file():
                errors.append(f"{card_id}: missing reference {references[field]}")
        if card["artifact"]["path"] != references["brief"]:
            errors.append(f"{card_id}: artifact must remain a local benchmark fixture")
        if card["card_status"] == "accepted":
            calibration = card["human_calibration"]
            if calibration["status"] != "completed":
                errors.append(f"{card_id}: accepted card requires completed human calibration")
            if any(gate["status"] != "pass" for gate in card["hard_gates"]):
                errors.append(f"{card_id}: accepted card requires passing hard gates")
        if card["card_status"] == "not-run" and card["evidence_level"] != "E0":
            errors.append(f"{card_id}: not-run card must remain E0")
        if card["human_calibration"]["status"] != "completed" and card["card_status"] == "accepted":
            errors.append(f"{card_id}: non-completed calibration is non-authoritative")
        gate_ids = {gate["id"] for gate in card["hard_gates"]}
        # Every card must carry at least one governance hard gate: either
        # originality (no-signature-copy) or source/license record. Domain
        # gates (typography/motion/material/etc.) are per-benchmark and not
        # universally required. Codex review finding 4.
        if not REQUIRED_GATES & gate_ids:
            errors.append(f"{card_id}: missing governance hard gate (need no-signature-copy or source-and-license-record)")
    # DL-CLOUDAUDIT-B5 (R13): append-only evidence identity + supersedes
    # chain. A card's records form one linear chain: a single genesis (no
    # supersedes), revisions append without ever rewriting the superseded
    # record, and no fork/cycle/dangling link anywhere.
    groups: dict[str, list[dict]] = {}
    for card in schema_valid:
        groups.setdefault(card["card_id"], []).append(card)
    for card_id, records in groups.items():
        if len({record["benchmark_id"] for record in records}) > 1:
            errors.append(f"{card_id}: records of one card must keep one benchmark_id")
        by_identity: dict[str, dict] = {}
        for record in records:
            identity = record.get("evidence_id")
            if identity is None:
                continue
            computed = content_identity(record)
            if identity != computed:
                # A committed id that no longer matches the substantive fields
                # means the record was overwritten in place -- fail closed.
                errors.append(
                    f"{card_id}: evidence_id does not match content identity "
                    f"(in-place overwrite; committed {identity[:19]}..., computed {computed[:19]}...)"
                )
            if identity in by_identity:
                errors.append(f"{card_id}: duplicate evidence_id {identity[:19]}... (identity collision)")
            by_identity[identity] = record
        chain = len(records) > 1
        for record in records:
            if chain and "evidence_id" not in record:
                errors.append(f"{card_id}: every record of a supersedes chain requires evidence_id")
            if record.get("card_status") == "accepted" and "evidence_id" not in record:
                errors.append(f"{card_id}: accepted card requires evidence_id (immutable identity)")
            if record.get("supersedes") is not None and "evidence_id" not in record:
                errors.append(f"{card_id}: revision requires evidence_id (immutable identity)")
        child: dict[str, dict] = {}
        for record in records:
            target = record.get("supersedes")
            if target is None:
                continue
            if target not in by_identity:
                errors.append(
                    f"{card_id}: supersedes {target[:19]}... links to no record of this card "
                    "(dangling link -- an append-only revision may only point at an earlier record's evidence_id)"
                )
            elif target in child:
                errors.append(f"{card_id}: two records supersede {target[:19]}... (fork -- the chain must be linear)")
            else:
                child[target] = record
        genesis = [record for record in records if record.get("supersedes") is None]
        if len(genesis) != 1:
            errors.append(
                f"{card_id}: chain must have exactly one genesis record (no supersedes), found {len(genesis)}"
            )
        else:
            walked = 1
            node = genesis[0]
            while node.get("evidence_id") in child:
                node = child[node["evidence_id"]]
                walked += 1
            if walked != len(records):
                errors.append(
                    f"{card_id}: supersedes chain is not a single linear path "
                    f"({walked} of {len(records)} records reachable -- cycle or orphan)"
                )
    if set(card["benchmark_id"] for card in cards if isinstance(card, dict)) != set(benchmarks):
        errors.append("card benchmark id set does not match registry")
    return errors


def main() -> int:
    path = ROOT / "evals/evidence/evidence-cards.json"
    errors = verify(path)
    if errors:
        for error in errors:
            print(f"EVIDENCE_CARDS_FAIL {error}")
        return 1
    data = _load(path)
    cards = data.get("cards") if isinstance(data, dict) else data
    n_cards = len(cards) if isinstance(cards, list) else 0
    accepted = sum(1 for c in cards if isinstance(c, dict) and c.get("card_status") == "accepted")
    chained = sum(1 for c in cards if isinstance(c, dict) and c.get("supersedes") is not None)
    print(f"EVIDENCE_CARDS_PASS cards={n_cards} chained={chained} human_calibration_required=true authoritative_accepts={accepted}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
