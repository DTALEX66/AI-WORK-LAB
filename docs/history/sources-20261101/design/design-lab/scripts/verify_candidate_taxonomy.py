#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Enforce the global-capability intake's anti-fabrication rules.

`research/candidates/CANDIDATE-TAXONOMY.json` classifies external design
candidates on many axes. A file like that is trivially able to launder popularity
into quality, invent precise aesthetic scores, or claim a human review that never
happened -- so the rules are checked here instead of being asked for in prose:

  * the schema is validated (draft 2020-12);
  * every declared domain names an EXISTING design-lab/domain-packs directory
    (adding a parallel product taxonomy is forbidden);
  * a non-null axis level must carry an evidence reference -- an unmeasured axis
    is `null`, never a made-up number;
  * a score can only be claimed where something measured it, and tier S/A needs a
    real benchmark;
  * adoption of a parent repository is kept separate from the candidate's own
    signal, so a skill inside a 150k-star repo cannot be reported as 150k stars;
  * an unknown licence caps the disposition before CONDITIONAL_POC;
  * ABSORBED/BENCHMARKED require benchmark + runtime evidence;
  * `reviewedBy`/`reviewedAt` are human responsibility fields: an agent may not
    set them, and they require a human approval reference;
  * placeholder domains (example.*, localhost, TODO) are rejected outright.

Read-only. Pure stdlib + jsonschema.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
TAXONOMY = REPO / 'research' / 'candidates' / 'CANDIDATE-TAXONOMY.json'
SCHEMA = REPO / 'design-lab' / 'schemas' / 'candidate-taxonomy.schema.json'
DOMAIN_PACKS = REPO / 'design-lab' / 'domain-packs'

PLACEHOLDER = re.compile(r'example\.(com|org|invalid)|localhost|127\.0\.0\.1|TODO|TBD|placeholder')
NO_LICENCE_OK = {'DISCOVERED', 'QUARANTINE', 'REFERENCE_ONLY'}
REQUIRES_BENCHMARK = {'ABSORBED', 'BENCHMARKED'}


def measured_fields(entry: dict) -> tuple[list[tuple[str, dict]], list[str]]:
    """Non-null axis values, plus the names of malformed ones.

    Malformed values are returned rather than raising: a hand-edited taxonomy with
    `"minimal": "high"` must fail closed with a message, not crash the gate.
    """
    good: list[tuple[str, dict]] = []
    malformed: list[str] = []
    for group in ('aestheticAxes', 'designQuality'):
        for axis, value in (entry.get(group) or {}).items():
            if value is None:
                continue
            if isinstance(value, dict):
                good.append((f'{group}.{axis}', value))
            else:
                malformed.append(f'{group}.{axis}={value!r}')
    return good, malformed


def main() -> int:
    errors: list[str] = []
    if not TAXONOMY.is_file() or not SCHEMA.is_file():
        print('CANDIDATE_TAXONOMY=FAIL missing taxonomy or schema')
        return 1
    try:
        taxonomy = json.loads(TAXONOMY.read_text(encoding='utf-8'))
        schema = json.loads(SCHEMA.read_text(encoding='utf-8'))
    except json.JSONDecodeError as exc:
        print(f'CANDIDATE_TAXONOMY=FAIL unreadable JSON: {exc}')
        return 1

    try:
        from jsonschema import Draft202012Validator
    except ImportError:
        print('CANDIDATE_TAXONOMY=FAIL jsonschema unavailable; refusing to skip validation')
        return 1
    validator = Draft202012Validator(schema)
    for problem in sorted(validator.iter_errors(taxonomy), key=lambda e: list(e.path)):
        where = '/'.join(str(p) for p in problem.path) or '<root>'
        errors.append(f'schema {where}: {problem.message[:200]}')

    packs = {p.name for p in DOMAIN_PACKS.iterdir() if p.is_dir()} if DOMAIN_PACKS.is_dir() else set()
    if not packs:
        errors.append('no domain packs found; refusing to validate domain mappings against nothing')

    seen: set[str] = set()
    raw = TAXONOMY.read_text(encoding='utf-8')
    for entry in taxonomy.get('entries', []):
        cid = entry.get('candidateId', '?')
        prefix = f'{cid}'
        if cid in seen:
            errors.append(f'{prefix}: duplicate candidateId')
        seen.add(cid)

        for domain in entry.get('domains', []):
            if domain not in packs:
                errors.append(f'{prefix}: domain {domain!r} is not an existing '
                              f'design-lab/domain-packs directory')

        for name, value in measured_fields(entry)[0]:
            if not value.get('evidenceRef'):
                errors.append(f'{prefix}: {name} claims level '
                              f'{value.get("level")!r} without an evidenceRef '
                              f'(unmeasured axes must be null)')
        for bad in measured_fields(entry)[1]:
            errors.append(f'{prefix}: malformed axis value {bad}; a measured axis must be '
                          f'an object with level + evidenceRef, or null')

        tier = entry.get('tier')
        benchmark = entry.get('benchmarkStatus')
        if tier in {'S', 'A'} and benchmark == 'none':
            errors.append(f'{prefix}: tier {tier} requires a benchmark; benchmarkStatus is none')
        if tier in {'S', 'A'} and not measured_fields(entry)[0]:
            errors.append(f'{prefix}: tier {tier} with no measured quality field')

        license_value = (entry.get('rights') or {}).get('license')
        disposition = entry.get('disposition')
        if not license_value and disposition not in NO_LICENCE_OK:
            errors.append(f'{prefix}: no licence recorded but disposition is {disposition}; '
                          f'an unknown licence may not advance past DISCOVERED/QUARANTINE/REFERENCE_ONLY')
        if disposition in REQUIRES_BENCHMARK:
            if benchmark not in {'partial', 'complete'}:
                errors.append(f'{prefix}: disposition {disposition} needs benchmarkStatus '
                              f'partial/complete, got {benchmark!r}')
            if entry.get('evidenceLevel') not in {'E2', 'E3', 'E4', 'E5'}:
                errors.append(f'{prefix}: disposition {disposition} needs runtime evidence '
                              f'(E2+), got {entry.get("evidenceLevel")!r}')

        adoption = entry.get('adoption') or {}
        if adoption.get('parentRepoStars') is not None and not adoption.get('skillSpecificSignal'):
            errors.append(f'{prefix}: parentRepoStars is set without a separate '
                          f'skillSpecificSignal -- that is star laundering')

        if entry.get('canonicalUrl') is None and not (entry.get('rights') or {}).get('rightsNotes'):
            errors.append(f'{prefix}: canonicalUrl is null without rightsNotes explaining '
                          f'why no single canonical upstream exists')

        reviewed = entry.get('reviewedBy') or entry.get('reviewedAt')
        if reviewed and not entry.get('humanApprovalRef'):
            errors.append(f'{prefix}: reviewedBy/reviewedAt set without humanApprovalRef; '
                          f'only a human may mark a source reviewed (DL-KNW-001)')
        if entry.get('humanApprovalRef') and not reviewed:
            errors.append(f'{prefix}: humanApprovalRef present but reviewedBy/reviewedAt missing')

    for hit in set(PLACEHOLDER.findall(raw)):
        errors.append(f'placeholder domain or marker present in the taxonomy: {hit!r}')
    if re.search(r'example\.(com|org|invalid)', raw):
        errors.append('placeholder domain present in the taxonomy')

    print(f'CANDIDATE_TAXONOMY entries={len(taxonomy.get("entries", []))} '
          f'domain_packs={len(packs)} errors={len(errors)}')
    for err in errors:
        print('ERROR:', err)
    print('CANDIDATE_TAXONOMY=' + ('FAIL' if errors else 'OK'))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
