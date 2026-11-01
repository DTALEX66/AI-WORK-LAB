#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Project raw observations into research/candidates/CANDIDATE-TAXONOMY.json.

WHY A SCRIPT
------------
The taxonomy is generated, never hand-edited: every field it writes must be
traceable to a raw observation produced by `scripts/collect_design_capability_candidates.py`.
This builder is the only writer; re-running it against a newer observation file
regenerates the file deterministically.

WHAT IT REFUSES TO DO
---------------------
- No scoring: `tier` stays null, `designQuality` stays empty, `benchmarkStatus`
  stays 'none' -- nothing here has measured design quality.
- No human fields: `reviewedBy` / `reviewedAt` / `humanApprovalRef` stay null.
- No star laundering: `parentRepoStars` is always paired with an explicit
  `skillSpecificSignal` string saying what the number is and is NOT.
- No licence guesses: the licence is recorded from the repository's OWN LICENSE
  file (with its sha256) when GitHub served it; otherwise the API label is
  recorded as inferred-only in `rightsNotes`.
- No fake classification: `sourceType` comes from declared keyword rules over
  GitHub metadata, and EVERY rule hit (including the fallback) is recorded in
  `risk.notes` as CLASSIFICATION for human re-triage. Capability layers, domains
  and aesthetic axes stay EMPTY until a human/method classifies them.

PROVENANCE SPLIT
----------------
Entries already present in the previous taxonomy file are preserved verbatim --
they are the declared seed -- EXCEPT that their `adoption` block and
`pinnedCommitSHA` / `lastActivityAt` are refreshed when a fresh observation
exists for the same `canonicalRepo`. Everything else is machine-projected.
`tool-control` (no single canonical upstream) keeps its null canonicalUrl and
its explanatory rightsNotes, exactly as the README records it.

Usage:
    python scripts/build_candidate_taxonomy.py \
        --observation research/candidates/observations/github-observation-<ts>.json
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
TAXONOMY = REPO / 'research' / 'candidates' / 'CANDIDATE-TAXONOMY.json'
SCHEMA = REPO / 'design-lab' / 'schemas' / 'candidate-taxonomy.schema.json'
DEFAULT_PREVIOUS = TAXONOMY

OBSERVATION_SCHEMA = 'design-lab/candidate-observation/v1'
TAXONOMY_SCHEMA = 'design-lab/candidate-taxonomy/v1'

# ---------------------------------------------------------------------------
# sourceType rules. Ordered; first hit wins. Each rule is a (rule_id, pattern set,
# sourceType) triple evaluated against name + topics + description, all lowercased.
# The fallback exists so the schema-required field is never null, and it is the
# LOUDEST possible signal that a human still has to look at the row.
# ---------------------------------------------------------------------------
SOURCE_TYPE_RULES: list[tuple[str, tuple[str, ...], str]] = [
    ('R-MCP', ('mcp',), 'MCP'),
    ('R-PLUGIN', ('plugin', 'addon', 'extension'), 'plugin'),
    ('R-COMPONENT-LIB', ('component library', 'component-library', 'ui kit',
                         'ui-kit', 'uikit', 'component-set'), 'component-library'),
    ('R-DESIGN-SYSTEM', ('design system', 'design-system', 'design token',
                         'design-token', 'style-dictionary', 'style dictionary',
                         'theming'), 'design-system'),
    ('R-BENCHMARK', ('benchmark', 'leaderboard', 'eval set', 'evaluation set'),
     'benchmark'),
    ('R-AUDIT-TOOL', ('audit', 'linter', 'linting', 'critique', 'review tool',
                      'quality check'), 'audit-tool'),
    ('R-HOST-ADAPTER', ('host adapter', 'host-adapter', 'tool adapter'), 'host-adapter'),
    ('R-GENERATOR', ('generator', 'generated'), 'generator'),
    ('R-REFERENCE-DATASET', ('awesome-', 'awesome list', 'curated list',
                             'resources', 'dataset', 'collection of'), 'reference-dataset'),
    ('R-SKILL-NAME', (), 'skill'),          # name-shape rule, evaluated separately
    ('R-SKILL-TEXT', ('skill', 'agent skill', 'claude', 'cursor rules',
                      'agent-ready'), 'skill'),
]
SOURCE_TYPE_FALLBACK = ('workflow', 'R-FALLBACK')  # (sourceType, rule_id)


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _slug(text: str) -> str:
    s = text.lower()
    s = re.sub(r'[^a-z0-9._-]+', '-', s).strip('-')
    return re.sub(r'-{2,}', '-', s)[:64] or 'candidate'


def classify_source_type(repo: str, topics: list[str], description: str | None) -> tuple[str, str, str]:
    """Return (sourceType, rule_id, evidence) from observable GitHub metadata only."""
    name = repo.split('/')[-1].lower()
    blob = ' '.join([name, ' '.join(topics), description or '']).lower()
    for rule_id, needles, kind in SOURCE_TYPE_RULES:
        if rule_id == 'R-SKILL-NAME':
            continue
        hit = next((n for n in needles if n in blob), None)
        if hit:
            return kind, rule_id, f'matched {hit!r} in name/topics/description'
    # name-shape rule: <something>-skill(s) or a skills collection
    if name.endswith('-skill') or name.endswith('-skills') or name == 'skills':
        return 'skill', 'R-SKILL-NAME', f"repository name {name!r} ends in 'skill(s)'"
    kind, rule_id = SOURCE_TYPE_FALLBACK
    return kind, rule_id, 'no declared rule matched; UNVERIFIED fallback, needs human triage'


def observation_index(observation_path: Path) -> dict[str, dict]:
    """Load one observation file into {canonicalRepo: {facts, observedAt, ...}}."""
    document = json.loads(observation_path.read_text(encoding='utf-8'))
    if document.get('schemaVersion') != OBSERVATION_SCHEMA:
        raise SystemExit(f'{observation_path}: expected schema {OBSERVATION_SCHEMA}, '
                         f'got {document.get("schemaVersion")!r}')
    index: dict[str, dict] = {}
    for obs in document.get('observations') or []:
        repo = obs.get('canonicalRepo')
        if repo and obs.get('facts', {}).get('resolved'):
            index[repo] = obs
    return index, document


def refresh_adoption(entry: dict, obs: dict, observation_name: str) -> None:
    """Refresh only the measured adoption/pinning fields of an existing entry."""
    facts = obs.get('facts') or {}
    stars = facts.get('stargazers_count')
    entry['adoption'] = {
        'observedAt': obs.get('observedAt'),
        'source': f'{observation_name} (GitHub GraphQL API v4 via gh CLI)',
        'parentRepoStars': stars,
        'skillSpecificSignal': (
            'repo-as-candidate: the observed repository is itself the candidate unit, '
            'so stargazerCount is its own adoption signal; no separate sub-candidate '
            'metric has been measured yet'
            if stars is not None else None),
        'metrics': {
            'stargazerCount': stars,
            'forkCount': facts.get('forks_count'),
        },
    }
    if facts.get('head_commit_sha'):
        entry['pinnedCommitSHA'] = facts['head_commit_sha']
    if facts.get('pushed_at'):
        entry['lastActivityAt'] = facts['pushed_at']


def build_entry(repo: str, obs: dict, recorded: dict | None,
                observation_name: str, candidate_id: str) -> dict:
    """Project one observation into a schema-valid taxonomy entry.

    `candidate_id` is decided by the CALLER (it owns collision handling); this
    function never re-derives it, or two repos with the same name would both
    emit the same candidateId and the verifier would rightly go red.
    """
    facts = obs.get('facts') or {}
    owner, name = repo.split('/', 1)
    topics = facts.get('topics') or []
    description = None
    discovered = obs.get('discovered') or {}
    stars = facts.get('stargazers_count')

    if recorded is not None:
        disposition = recorded.get('recorded_disposition') or 'CONDITIONAL_POC'
        recorded_license = recorded.get('recorded_license')
        provenance = 'research/candidates/README.md (recorded row, re-verified live)'
    else:
        disposition = 'DISCOVERED'
        recorded_license = None
        provenance = (f"GitHub search facet {discovered.get('discovered_via')!r} "
                      f"(relevance: {discovered.get('relevance_bucket')})")

    source_type, rule_id, evidence = classify_source_type(repo, topics, description)

    licence_read = facts.get('license_file_status') == 200
    licence = (facts.get('license_file_spdx') if licence_read
               else facts.get('license_api_spdx'))
    if recorded_license and recorded_license != licence:
        # The README's recorded licence and today's upstream disagree: surface it,
        # never silently overwrite either side.
        licence = recorded_license
        licence_note = (f'licence {recorded_license} as recorded in README.md; live '
                        f'upstream now reports {facts.get("license_api_spdx")!r} '
                        f'(MISMATCH -- needs human check)')
    elif licence_read:
        licence_note = (f'licence read from the repository\'s own LICENSE file '
                        f'(sha256 {facts.get("license_sha256")})')
    else:
        licence_note = ('licence label inferred from GitHub API metadata only; the '
                        'repository\'s own LICENSE file was not served')

    classification_note = (f'CLASSIFICATION: sourceType={source_type} by rule {rule_id} '
                           f'({evidence}); auto-generated from GitHub metadata, human '
                           f'triage not performed')
    risk_notes = ' ; '.join([classification_note,
                             f'provenance: {provenance}',
                             'risk axes unmeasured (null by policy)'])

    return {
        'candidateId': candidate_id,
        'canonicalName': name,
        'canonicalUrl': f'https://github.com/{repo}',
        'canonicalRepo': repo,
        'upstreamOwner': owner,
        'sourceType': source_type,
        'currentVersion': None,
        'pinnedCommitSHA': facts.get('head_commit_sha'),
        'discoveredAt': facts.get('created_at'),
        'lastActivityAt': facts.get('pushed_at'),
        'capabilityLayers': [],
        'domains': [],
        'artifactTypes': [],
        'styleArchetypes': [],
        'referenceLineages': [],
        'aestheticAxes': {},
        'adoption': {
            'observedAt': obs.get('observedAt'),
            # Same string refresh_adoption() writes, so re-projecting a generated
            # file is idempotent. Per-candidate provenance lives in risk.notes.
            'source': f'{observation_name} (GitHub GraphQL API v4 via gh CLI)',
            'parentRepoStars': stars,
            'skillSpecificSignal': (
                'repo-as-candidate: the observed repository is itself the candidate '
                'unit, so stargazerCount is its own adoption signal; no separate '
                'sub-candidate metric has been measured yet'
                if stars is not None else None),
            'metrics': {
                'stargazerCount': stars,
                'forkCount': facts.get('forks_count'),
            },
        },
        'designQuality': {},
        'tier': None,
        'disposition': disposition,
        'rights': {
            'license': licence,
            'licenseURL': facts.get('license_html_url') if licence_read else None,
            'rightsNotes': licence_note,
        },
        'risk': {
            'sideEffects': None,
            'destructiveCapability': None,
            'network': None,
            'credentials': None,
            'notes': risk_notes,
        },
        'benchmarkStatus': 'none',
        'evidenceLevel': 'E0',
        'removalPath': (f'remove research/candidates/CANDIDATE-TAXONOMY.json entry '
                        f'{candidate_id} (+ .project-local/cache/vendor/{candidate_id} '
                        f'if a vendor cache exists)'),
        'reviewedBy': None,
        'reviewedAt': None,
        'humanApprovalRef': None,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description='Project observations into the taxonomy.')
    ap.add_argument('--observation', required=True,
                    help='observation file produced by collect_design_capability_candidates.py')
    ap.add_argument('--previous', default=str(DEFAULT_PREVIOUS),
                    help='existing taxonomy file whose seed entries are preserved')
    ap.add_argument('--out', default=str(TAXONOMY))
    ap.add_argument('--check', action='store_true',
                    help='verify the file on disk is exactly what would be generated')
    args = ap.parse_args()

    observation_path = Path(args.observation)
    if not observation_path.is_file():
        print(f'build: observation file not found: {observation_path}', file=sys.stderr)
        return 2
    index, document = observation_index(observation_path)
    observation_name = observation_path.name

    recorded_rows: dict[str, dict] = {}
    sys.path.insert(0, str(REPO / 'scripts'))
    from collect_design_capability_candidates import parse_readme_records  # noqa: E402
    for rec in parse_readme_records():
        recorded_rows.setdefault(rec['canonical_repo'], rec)

    previous: dict = {}
    previous_path = Path(args.previous)
    if previous_path.is_file():
        previous = json.loads(previous_path.read_text(encoding='utf-8'))
        if previous.get('schemaVersion') != TAXONOMY_SCHEMA:
            print(f'build: {previous_path} has schema {previous.get("schemaVersion")!r}, '
                  f'expected {TAXONOMY_SCHEMA}', file=sys.stderr)
            return 2

    preserved: dict[str, dict] = {}
    for entry in previous.get('entries') or []:
        preserved[entry['candidateId']] = dict(entry)

    entries: list[dict] = []
    seen_ids: set[str] = set()
    # De-duplicate by REPOSITORY, not by id. A previous file already contains every
    # repo this projection would emit (possibly under a widened id); keying by id
    # alone would re-add the same upstream under a second id and the verifier
    # would rightly reject the duplicates.
    known_repos: set[str] = {e['canonicalRepo'] for e in previous.get('entries') or []
                             if e.get('canonicalRepo')}
    refreshed = 0
    kept_verbatim = 0
    for entry in previous.get('entries') or []:
        candidate = dict(entry)
        repo = candidate.get('canonicalRepo')
        obs = index.get(repo) if repo else None
        if obs is not None:
            refresh_adoption(candidate, obs, observation_name)
            refreshed += 1
        else:
            kept_verbatim += 1
        entries.append(candidate)
        seen_ids.add(candidate['candidateId'])

    new_entries: list[dict] = []
    skipped_no_observation = 0
    for repo, rec in sorted(recorded_rows.items()):
        obs = index.get(repo)
        if obs is None:
            skipped_no_observation += 1
            continue
        if repo in known_repos:
            continue
        candidate_id = rec.get('cache_key') or rec.get('candidate_id') or _slug(repo.split('/')[-1])
        if candidate_id in seen_ids:
            continue
        new_entries.append(build_entry(repo, obs, rec, observation_name, candidate_id))
        seen_ids.add(candidate_id)
        known_repos.add(repo)

    for repo in sorted(index):
        if repo in known_repos:
            continue
        owner, name = repo.split('/', 1)
        candidate_id = _slug(name)
        if len(candidate_id) < 2 or candidate_id in seen_ids:
            # The schema id pattern needs >= 2 chars, and a bare name may already be
            # taken by a different owner (e.g. primer/css vs webpixels/css); widen
            # with the owner rather than silently dropping an observed upstream.
            candidate_id = _slug(f'{owner}-{name}')
        if candidate_id in seen_ids:
            print(f'build: skipping {repo}: candidateId {candidate_id!r} already taken',
                  flush=True)
            continue
        new_entries.append(build_entry(repo, index[repo], None, observation_name,
                                       candidate_id))
        seen_ids.add(candidate_id)
        known_repos.add(repo)

    new_entries.sort(key=lambda e: e['candidateId'])
    entries.extend(new_entries)

    counts = document.get('counts') or {}
    generated = {
        'schemaVersion': TAXONOMY_SCHEMA,
        'generatedAt': _utcnow(),
        'policy': {
            'nullMeansUnmeasured': True,
            'popularityIsNotQuality': True,
            'humanReviewOnly': True,
            'notes': (
                'Generated by scripts/build_candidate_taxonomy.py from '
                f'{observation_name} (observation counts: '
                + ', '.join(f'{k}={v}' for k, v in counts.items())
                + '). Seed entries from the previous file are preserved verbatim '
                'except their measured adoption/pinning fields; everything else is '
                'machine-projected with sourceType from declared keyword rules '
                '(recorded per-entry in risk.notes) and EMPTY capability layers, '
                'domains and aesthetic axes until human triage. tier/designQuality '
                'are null/empty by policy: nothing here has measured design quality. '
                'reviewedBy/reviewedAt stay null: human responsibility fields.'),
        },
        'entries': entries,
    }

    out_path = Path(args.out)
    payload = json.dumps(generated, indent=2, ensure_ascii=False) + '\n'
    if args.check:
        current_text = out_path.read_text(encoding='utf-8') if out_path.is_file() else ''
        # generatedAt is a wall-clock stamp, not content: compare everything else,
        # or --check would report drift every second after generation.
        current = json.loads(current_text) if current_text else {}
        candidate = json.loads(payload)
        current.pop('generatedAt', None)
        candidate.pop('generatedAt', None)
        if current != candidate:
            if os.environ.get('TAXONOMY_DEBUG'):
                debug = REPO / '.project-local' / 'tmp'
                debug.mkdir(parents=True, exist_ok=True)
                (debug / 'check-current.json').write_text(
                    json.dumps(current, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                (debug / 'check-candidate.json').write_text(
                    json.dumps(candidate, indent=2, ensure_ascii=False) + '\n', encoding='utf-8')
                print(f'debug: dumped to {debug}/check-*.json', flush=True)
            print(f'build: DRIFT -- {out_path} does not match the projection of '
                  f'{observation_name}', file=sys.stderr)
            return 1
        print(f'build: {out_path} matches the projection of {observation_name}')
        return 0

    out_path.write_text(payload, encoding='utf-8')
    print(f'build: wrote {out_path}')
    print(f'  preserved={len(previous.get("entries") or [])} '
          f'(adoption refreshed={refreshed}, verbatim={kept_verbatim}) '
          f'projected_new={len(new_entries)} '
          f'recorded_without_observation={skipped_no_observation} '
          f'total={len(entries)}')
    by_disposition: dict[str, int] = {}
    for entry in entries:
        by_disposition[entry['disposition']] = by_disposition.get(entry['disposition'], 0) + 1
    print('  by disposition: '
          + ', '.join(f'{k}={v}' for k, v in sorted(by_disposition.items())))
    return 0


if __name__ == '__main__':
    sys.exit(main())
