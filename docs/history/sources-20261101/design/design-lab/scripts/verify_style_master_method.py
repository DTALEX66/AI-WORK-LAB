#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Verify the structural floor for the style-master method capability.

This check proves only E1 structural integrity: declared counts, record shape,
unique IDs, method-card safety markers, and lineage/analysis-card convergence.
It does not promote research sources, runtime use, human review, or commercial
readiness.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RESEARCH = ROOT / "design-lab" / "research"
MASTER_PATH = RESEARCH / "master-studies" / "MASTER_REGISTRY.json"
CARD_PATH = RESEARCH / "master-studies" / "ANCHOR_METHOD_CARDS.json"
LINEAGE_PATH = RESEARCH / "style-lineages" / "STYLE_LINEAGES.json"
ANALYSIS_PATH = RESEARCH / "style-lineages" / "STYLE_ANALYSIS_CARDS.json"


def load_json(path: Path, errors: list[str]) -> object:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # pragma: no cover - diagnostic path
        errors.append(f"{path.relative_to(ROOT)}: JSON_LOAD {exc}")
        return None


def list_value(data: object, key: str, label: str, errors: list[str]) -> list[object]:
    value = data.get(key) if isinstance(data, dict) else None
    if not isinstance(value, list):
        errors.append(f"{label}: missing list {key}")
        return []
    return value


def verify() -> tuple[list[str], dict[str, int]]:
    errors: list[str] = []
    master = load_json(MASTER_PATH, errors)
    cards = load_json(CARD_PATH, errors)
    lineages = load_json(LINEAGE_PATH, errors)
    analysis = load_json(ANALYSIS_PATH, errors)

    masters = list_value(master, "masters", "master registry", errors)
    anchor_cards = list_value(cards, "cards", "anchor cards", errors)
    style_lineages = list_value(lineages, "lineages", "style lineages", errors)
    analysis_cards = list_value(analysis, "cards", "style analysis cards", errors)

    if isinstance(master, dict) and master.get("count") != len(masters):
        errors.append(f"master registry count mismatch declared={master.get('count')} actual={len(masters)}")
    if isinstance(cards, dict) and cards.get("count") != len(anchor_cards):
        errors.append(f"anchor cards count mismatch declared={cards.get('count')} actual={len(anchor_cards)}")

    master_ids: set[object] = set()
    for index, item in enumerate(masters):
        if not isinstance(item, dict):
            errors.append(f"master[{index}] is not object")
            continue
        for field in ("id", "name", "study_status", "generation_eligibility"):
            if not isinstance(item.get(field), str) or not item[field].strip():
                errors.append(f"master[{index}] missing non-empty {field}")
        if not isinstance(item.get("disciplines"), list) or not item["disciplines"]:
            errors.append(f"master[{index}] missing non-empty disciplines")
        item_id = item.get("id")
        if item_id in master_ids:
            errors.append(f"duplicate master id {item_id}")
        master_ids.add(item_id)
        if item.get("generation_eligibility") not in {
            "research-only-until-method-card-created",
            "translated-methods-only",
        }:
            errors.append(f"master[{index}] invalid generation eligibility")

    card_ids: set[object] = set()
    for index, item in enumerate(anchor_cards):
        if not isinstance(item, dict):
            errors.append(f"card[{index}] is not object")
            continue
        for field in ("id", "name", "thesis", "transferable_methods", "shallow_mimicry_risks"):
            if field not in item:
                errors.append(f"card[{index}] missing {field}")
        if not isinstance(item.get("transferable_methods"), list) or len(item.get("transferable_methods", [])) < 3:
            errors.append(f"card[{index}] transferable_methods < 3")
        if not isinstance(item.get("shallow_mimicry_risks"), list) or not item.get("shallow_mimicry_risks"):
            errors.append(f"card[{index}] shallow_mimicry_risks empty")
        item_id = item.get("id")
        if item_id in card_ids:
            errors.append(f"duplicate card id {item_id}")
        card_ids.add(item_id)
        text = json.dumps(item, ensure_ascii=False).lower()
        if "generation_prompt" in text or "prompt injection" in text:
            errors.append(f"card[{index}] contains a direct-generation marker")

    if len(style_lineages) != 47:
        errors.append(f"style lineages count expected=47 actual={len(style_lineages)}")
    if len(analysis_cards) != 47:
        errors.append(f"style analysis cards count expected=47 actual={len(analysis_cards)}")

    counts = {
        "masters": len(masters),
        "anchor_cards": len(anchor_cards),
        "style_lineages": len(style_lineages),
        "analysis_cards": len(analysis_cards),
    }
    return errors, counts


def main() -> int:
    errors, counts = verify()
    print(
        "STYLE_MASTER_METHOD="
        f"{'PASS' if not errors else 'FAIL'} "
        f"masters={counts['masters']} cards={counts['anchor_cards']} "
        f"lineages={counts['style_lineages']} analysis_cards={counts['analysis_cards']} "
        f"errors={len(errors)}"
    )
    for error in errors[:50]:
        print(f"  ERROR {error}")
    return 0 if not errors else 1


if __name__ == "__main__":
    raise SystemExit(main())
