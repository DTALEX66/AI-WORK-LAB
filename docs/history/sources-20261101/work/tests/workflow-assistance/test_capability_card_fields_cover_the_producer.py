#!/usr/bin/env python3
"""WUI-06 / WUI-15 · the frontend's card type must cover every key the producer emits.

Why this exists: `adapter_capability_projection.py` added `entryProbe` and `versionDrift` to every
capability card, and `apps/observer/frontend/src/types.ts` never learned about them. Nothing broke — a
missing field is invisible to a TypeScript interface that is hand-maintained, and the UI simply stopped
being able to render a fact the backend already answers. That is the silent half of a front/back contract:
an extra field in the payload is harmless, a field the type does not name is unrenderable, and neither
direction is checked by any schema because the v3 contract is code plus tests, not a JSON Schema
(`apps/observer/schemas/*.json` describe the legacy v2 `/api/dashboard` payload).

The test therefore reads both sides from source and fails on the set difference. It also refuses to pass
on a parse failure: the producer set must be at least as large as the number this file measured, so a
refactor that moves the `cards.append({...})` literal makes the test red rather than vacuously green.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PRODUCER = ROOT / "packages/client-neutral-core/scripts/adapter_capability_projection.py"
TYPES = ROOT / "apps/observer/frontend/src/types.ts"

# measured 2026-10-09 against the shipped producer; a lower count means the extraction stopped working
MIN_PRODUCER_KEYS = 20


def producer_card_keys() -> set[str]:
    """Every quoted key in the `cards.append({...})` literal, plus the keys added afterwards.

    `verbEvidence` and friends are attached to the last card conditionally (`cards[-1]["verbEvidence"] =
    ...`), which is a real emitted field with a real absence rule — leaving them out of the emitted set
    would make the reverse check call them inventions of the frontend.
    """
    text = PRODUCER.read_text(encoding="utf-8")
    start = text.index("cards.append({")
    # walk to the matching close: the literal contains nested braces, so brace depth is the only way
    depth = 0
    for index in range(start + len("cards.append"), len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                keys = set(re.findall(r'^\s*"([A-Za-z]\w*)"\s*:', text[start:index], re.M))
                keys |= set(re.findall(r'cards\[-1\]\["([A-Za-z]\w*)"\]', text))
                return keys
    raise AssertionError("unterminated cards.append({...}) literal in " + str(PRODUCER))


def declared_card_keys() -> set[str]:
    """Every property named in `export interface AdapterCapabilityCard { ... }`."""
    text = TYPES.read_text(encoding="utf-8")
    match = re.search(r"export interface AdapterCapabilityCard \{", text)
    if not match:
        raise AssertionError("AdapterCapabilityCard is not declared in " + str(TYPES))
    depth = 0
    for index in range(match.end() - 1, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                body = text[match.end():index]
                body = re.sub(r"/\*.*?\*/", "", body, flags=re.S)   # strip block comments
                body = re.sub(r"//[^\n]*", "", body)                 # strip line comments
                return set(re.findall(r"^\s*([A-Za-z]\w*)\??\s*:", body, re.M))
    raise AssertionError("unterminated AdapterCapabilityCard interface")


SNAPSHOT_API = ROOT / "packages/client-neutral-core/scripts/snapshot_api.py"

# Measured from a live readback of the running sidecar on 2026-10-09
# (.project-local/runs/wui-20261009/snapshot-readback2.json), not copied from the type file: the point is
# to catch a key that exists on one side only. Limitation stated plainly: this list is curated, so a
# producer that gains a NEW top-level key is caught only by the extraction floor below, not automatically.
EXPECTED_SNAPSHOT_KEYS = [
    "adapterCapabilities", "artifactHandles", "artifactHandlesSummary", "ci", "coverage", "executions",
    "generatedAt", "git", "governance", "projects", "revision", "schemaVersion", "software", "sourceRefs",
    "sourceWatermark", "taskRecords", "tasks", "tokenSummary", "transport", "workspace",
]


def snapshot_return_literal_keys() -> set[str]:
    """Quoted keys inside `build_snapshot`'s returned dict literal, spreads included."""
    text = SNAPSHOT_API.read_text(encoding="utf-8")
    start = text.index("    return {")
    depth = 0
    for index in range(start + len("    return"), len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return set(re.findall(r'"([A-Za-z]\w*)"\s*:', text[start:index]))
    raise AssertionError("unterminated return literal in " + str(SNAPSHOT_API))


def declared_snapshot_keys() -> set[str]:
    text = TYPES.read_text(encoding="utf-8")
    match = re.search(r"export interface SnapshotV3 \{", text)
    if not match:
        raise AssertionError("SnapshotV3 is not declared in " + str(TYPES))
    depth = 0
    for index in range(match.end() - 1, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                body = re.sub(r"/\*.*?\*/", "", text[match.end():index], flags=re.S)
                body = re.sub(r"//[^\n]*", "", body)
                # only top-level members: nested object literals appear after a `{` on the same entry
                return set(re.findall(r"^\s{2}([A-Za-z]\w*)\??\s*:", body, re.M))
    raise AssertionError("unterminated SnapshotV3 interface")


def check_snapshot_surface() -> list[str]:
    problems: list[str] = []
    emitted = snapshot_return_literal_keys()
    declared = declared_snapshot_keys()
    if len(emitted) < len(EXPECTED_SNAPSHOT_KEYS):
        problems.append(f"producer extraction found {len(emitted)} keys, floor is "
                        f"{len(EXPECTED_SNAPSHOT_KEYS)} - the return literal moved")
    for key in EXPECTED_SNAPSHOT_KEYS:
        if key not in emitted:
            problems.append(f"producer no longer emits snapshot key {key}")
        if key not in declared:
            problems.append(f"types.ts SnapshotV3 does not declare snapshot key {key}")
    return problems


def main() -> int:
    emitted = producer_card_keys()
    declared = declared_card_keys()
    problems: list[str] = []
    if len(emitted) < MIN_PRODUCER_KEYS:
        problems.append(f"producer extraction found {len(emitted)} keys, floor is {MIN_PRODUCER_KEYS} "
                        "- the literal moved and this test is now vacuous")
    missing = sorted(emitted - declared)
    if missing:
        problems.append("types.ts does not declare producer-emitted card fields: " + ", ".join(missing))
    # the reverse direction is a lie in the other shape: a field the UI types but the producer never
    # sends renders as a permanent empty cell that reads like a real answer.
    invented = sorted(declared - emitted)
    if invented:
        problems.append("types.ts declares card fields the producer never emits: " + ", ".join(invented))

    snapshot_problems = check_snapshot_surface()
    problems.extend(snapshot_problems)

    print(f"CAPABILITY_CARD_FIELDS producer={len(emitted)} declared={len(declared)}")
    print(f"SNAPSHOT_SURFACE expected={len(EXPECTED_SNAPSHOT_KEYS)} "
          f"problems={len(snapshot_problems)}")
    for problem in problems:
        print("FAIL " + problem)
    if problems:
        return 1
    print("CAPABILITY_CARD_FIELDS_PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
