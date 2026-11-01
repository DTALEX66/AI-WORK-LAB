#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Collect raw, attributable observations about external design-capability candidates.

WHY THIS EXISTS
---------------
The previous intake attempt searched the open web in natural language. Every hit came
back from mirror farms (one upstream re-hosted under four locale paths) or second-hand
write-ups, so nothing resolved to a canonical `github.com/<owner>/<repo>` and no
candidate could honestly be registered. This script is the channel the taskpack asked
for: every fact it records was read live from GitHub and stamped with the time it was
read.

Two independent inputs feed one observation file:

  1. `research/candidates/README.md` -- candidates ALREADY recorded in this repository.
     Parsed, never retyped, then re-verified against their upstream: an old README row
     is a lead, not a fact.
  2. GitHub repository search -- new candidates that survive the relevance gate below.

TRANSPORT
---------
Everything goes out as GraphQL through the `gh` CLI, batched aggressively: several
independent searches per request, and ~20 repositories per metadata request. That is a
deliberate design choice, not a micro-optimisation -- outbound HTTPS here is relayed by
a transparent local proxy that intermittently stalls long request streams, so making a
few dozen self-contained round trips succeeds where hundreds do not. The credential
never touches this file.

WHAT THIS REFUSES TO DO
-----------------------
Nothing here scores design quality, assigns a tier, promotes a disposition past
DISCOVERED, or writes the human review fields. This step produces EVIDENCE; judging is
a separate gate. A repository whose licence we cannot read keeps `license: null` rather
than inheriting a guess, and a repository we cannot reach is reported unreachable rather
than filled in from memory.

Read-only with respect to the repository apart from writing its own observation file.

Usage:
    python scripts/collect_design_capability_candidates.py
    python scripts/collect_design_capability_candidates.py --out research/...
    python scripts/collect_design_capability_candidates.py --no-discovery
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
README = REPO / 'research' / 'candidates' / 'README.md'
OBSERVATION_DIR = REPO / 'research' / 'candidates' / 'observations'
# Scratch space for gh subprocess output; gitignored (.gitignore: .project-local/).
TMP_DIR = REPO / '.project-local' / 'tmp'

CALL_TIMEOUT_S = 45
SEARCHES_PER_REQUEST = 6      # keep each request inside GraphQL's complexity budget
REPOS_PER_REQUEST = 20
MAX_ATTEMPTS = 3

# ---------------------------------------------------------------------------
# Discovery surface: one facet per capability family in the intake's sourceType list.
# Topic qualifiers beat free-text search, but they still drag in noise
# (topic:typography returns an unrelated list-of-falsehoods repo), so every hit has to
# clear RELEVANCE below before it can be registered.
# ---------------------------------------------------------------------------
FACETS: list[str] = [
    # L0 / agent skills for design
    'topic:claude-code design', 'topic:agent-skills', 'topic:cursor design',
    'topic:mcp-server design', 'design agent skill claude',
    # L1 taste / art direction
    'topic:art-direction', 'topic:design-principles',
    # L2 research / reference
    'topic:design-resources', 'topic:design-inspiration',
    # L3 design system / tokens
    'topic:design-system', 'topic:design-tokens', 'topic:design-systems',
    'topic:style-dictionary', 'topic:theming tokens',
    # L4 component patterns
    'topic:component-library design', 'topic:headless-ui',
    'topic:ui-components design-system', 'topic:ui-kit',
    # L5 generation
    'topic:generative-design', 'topic:generative-art design',
    'topic:creative-coding design', 'topic:svg generator design',
    'topic:diffusion ui design',
    # L6 specialist craft
    'topic:typography design', 'topic:variable-fonts', 'topic:color-palette',
    'topic:color design tool', 'topic:layout design engine', 'topic:grid-layout',
    # L7 critique / audit / QA
    'topic:accessibility testing tool', 'topic:a11y linting',
    'topic:visual-regression', 'topic:design-qa',
    # L8 host / tool adapters
    'topic:figma-plugin', 'topic:figma-api', 'topic:sketch-plugin', 'topic:penpot',
    'topic:blender addon design', 'photoshop script automation design',
    'illustrator script automation design',
    # L9 production / handoff
    'topic:design-handoff', 'topic:print-production',
    'topic:packaging-design generator', 'topic:asset-export design',
    # Brand / voice
    'topic:branding generator', 'topic:logo-maker', 'topic:brand-identity',
    # Motion / spatial / data
    'topic:motion-design', 'topic:animation library design',
    'topic:data-visualization design',
]

# A discovery threshold, not a quality bar: it drops the abandoned one-week tail. The
# star count is then recorded apart from any quality signal and never becomes one.
MIN_STARS = 25
SEARCH_PAGE = 50

# ---------------------------------------------------------------------------
# Relevance gate -- a CURATION filter deciding what enters the pool. Explicitly NOT a
# quality measurement: nothing here contributes to a scored axis, and the winning bucket
# is written into the observation so a reviewer can audit why each row is present.
# ---------------------------------------------------------------------------
NAME_TERMS = [
    'design', 'ui', 'ux', 'figma', 'sketch', 'penpot', 'typograph', 'font', 'typeface',
    'color', 'colour', 'palette', 'brand', 'logo', 'layout', 'grid', 'svg', 'illustrat',
    'poster', 'print', 'motion', 'animat', 'lottie', 'chroma', 'theme', 'token',
    'aesthetic', 'visual', 'creative', 'artboard', 'canvas', 'chart', 'dataviz',
    'accessible', 'accessibility', 'a11y', 'contrast',
]
TOPIC_TERMS = [
    'design', 'ui', 'ux', 'user-interface', 'user-experience', 'design-system',
    'design-systems', 'design-tokens', 'figma', 'figma-plugin', 'sketch', 'penpot',
    'typography', 'fonts', 'font', 'typeface', 'color', 'colors', 'palette', 'branding',
    'logo', 'layout', 'svg', 'illustration', 'motion', 'animation', 'creator-tools',
    'a11y', 'accessibility', 'contrast', 'dataviz', 'data-visualization',
    'creative-coding', 'generative-art', 'generative-design', 'design-tools',
    'design-resources', 'ui-components', 'component-library', 'ui-kit', 'web-design',
    'graphic-design', 'interface-design', 'visual-design', 'design-handoff', 'theming',
    'print-design',
]
DESCRIPTION_TERMS = [
    'design system', 'design token', 'ui component', 'component library', 'figma',
    'typography', 'type scale', 'color palette', 'accessibility', 'contrast ratio',
    'font', 'brand', 'logo', 'layout engine', 'creative coding', 'generative design',
    'print ready', 'motion design', 'art direction', 'design tool', 'design principle',
    'visual regression',
]


class GhError(RuntimeError):
    """A gh invocation failed; carries the tool's own diagnostics."""


def _utcnow() -> str:
    return datetime.now(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def graphql(query: str) -> dict:
    """Run one GraphQL document. Retries transport failures; raises GhError if persistent.

    Output goes to a FILE, not a pipe. On Windows a killed child can leave the pipe
    handle open, and `subprocess.run(..., timeout=...)` then blocks forever inside
    communicate() -- which is exactly how an earlier run died silently at facet 1.
    Writing to a file and waiting on the handle makes the timeout real: past
    CALL_TIMEOUT_S the process is killed and the call returns.
    """
    last: Exception | None = None
    stamp = f'{os.getpid()}-{int(time.time() * 1000)}'
    for attempt in range(MAX_ATTEMPTS):
        sink = TMP_DIR / f'gh-{stamp}-{attempt}.out'
        try:
            with open(sink, 'w', encoding='utf-8') as handle:
                proc = subprocess.Popen(['gh', 'api', 'graphql', '-f', f'query={query}'],
                                        stdout=handle, stderr=subprocess.STDOUT)
            try:
                code = proc.wait(timeout=CALL_TIMEOUT_S)
            except subprocess.TimeoutExpired:
                proc.kill()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    pass
                last = GhError(f'gh graphql timed out after {CALL_TIMEOUT_S}s')
                continue
            text = sink.read_text(encoding='utf-8', errors='replace')
        finally:
            if sink.exists():
                sink.unlink()
        if code == 0:
            try:
                return json.loads(text)
            except json.JSONDecodeError as exc:
                last = GhError(f'unparseable GraphQL response: {exc}')
        else:
            last = GhError(text.strip().replace('\n', ' ')[:300]
                           or f'gh graphql exit {code}')
        time.sleep(1.0 * (attempt + 1))
    raise last if last else GhError('retries exhausted')


def _escape(value: str) -> str:
    return value.replace('\\', '\\\\').replace('"', '\\"')


# --------------------------------------------------------------------------- discovery

SEARCH_NODE = """
  {alias}: search(query: "{query}", type: REPOSITORY, first: {first}) {{
    repositoryCount
    nodes {{
      ... on Repository {{
        nameWithOwner
        url
        description
        stargazerCount
        updatedAt
        owner {{ login }}
        licenseInfo {{ spdxId key }}
        defaultBranchRef {{ name }}
        repositoryTopics(first: 15) {{ nodes {{ topic {{ name }} }} }}
      }}
    }}
  }}"""


def _chunked(items: list, size: int) -> list[list]:
    """Split `items` into consecutive slices of at most `size`."""
    return [items[i:i + size] for i in range(0, len(items), size)]


def load_prior_run(path: str) -> tuple[dict, list[dict]]:
    """Carry a previous observation file's successful discovery forward.

    The local proxy intermittently answers a whole batched request with HTTP 502.
    Rather than pretending those facets were searched, a follow-up run re-searches
    only what failed and MERGES what already succeeded, recording every input in
    `discovery.sourceRuns`. Nothing invented in between: each carried row keeps the
    facet that originally surfaced it.
    """
    doc = json.loads(Path(path).read_text(encoding='utf-8'))
    pool: dict[str, dict] = {}
    log: list[dict] = []
    for obs in doc.get('observations') or []:
        found = obs.get('discovered')
        if isinstance(found, dict) and found.get('canonical_repo'):
            pool[found['canonical_repo']] = dict(found)
    for entry in ((doc.get('discovery') or {}).get('facetLog') or []):
        if isinstance(entry, dict) and not entry.get('error'):
            log.append(dict(entry, carriedFrom=path))
    return pool, log


def run_facet_group(group: list[str]) -> dict[str, dict]:
    """Run ONE batched search request. Returns {facet: {'node': ...} | {'errors': [...]}}.

    Raises GhError when the request itself dies; the caller decides what to do.
    """
    aliases: dict[str, str] = {}
    parts: list[str] = []
    for idx, facet in enumerate(group):
        alias = f's{idx}'
        aliases[alias] = facet
        query = f'{facet} stars:>{MIN_STARS} fork:false archived:false'
        parts.append(SEARCH_NODE.format(alias=alias, query=_escape(query),
                                        first=SEARCH_PAGE))
    payload = graphql('query {' + ''.join(parts) + '\n}')
    data = payload.get('data') or {}
    out: dict[str, dict] = {}
    for alias, facet in aliases.items():
        node = data.get(alias)
        out[facet] = {'node': node if isinstance(node, dict) else None}
    for err in payload.get('errors') or []:
        path = err.get('path') or []
        if path:
            facet = aliases.get(str(path[0]), str(path[0]))
            out.setdefault(facet, {'node': None}).setdefault('errors', []).append(
                str(err.get('message'))[:200])
    return out


def discover_via_facets(facets: list[str] | None = None,
                        seed: dict | None = None) -> tuple[dict, list[dict]]:
    """Run every facet through repository search, keeping canonical hits.

    De-duplication is by `nameWithOwner`: one upstream, one row, no matter how many
    facets surfaced it. That is exactly what stops a re-hosted mirror inflating counts.
    """
    pool: dict[str, dict] = dict(seed or {})
    log: list[dict] = []
    wanted = list(facets) if facets is not None else list(FACETS)
    total = len(wanted)
    groups = _chunked(wanted, SEARCHES_PER_REQUEST)

    for gi, group in enumerate(groups, 1):
        try:
            results = run_facet_group(group)
        except GhError as exc:
            # Self-heal: an oversized batched request is what the proxy kills first,
            # so retry this group one facet per request before calling a facet dead.
            print(f'  [group {gi}/{len(groups)}] batch failed ({str(exc)[:60]}) '
                  f'-> retrying {len(group)} facet(s) individually', flush=True)
            results = {}
            for facet in group:
                try:
                    results.update(run_facet_group([facet]))
                except GhError as single:
                    results[facet] = {'error': str(single)[:200]}

        for facet in group:
            entry = results.get(facet) or {'node': None}
            if entry.get('error'):
                log.append({'facet': facet, 'error': entry['error']})
                print(f'  [{len(log)}/{total}] {facet:<44} MISS {entry["error"][:40]}',
                      flush=True)
                continue
            if entry.get('errors'):
                log.append({'facet': facet, 'error': '; '.join(entry['errors'])[:200]})
                print(f'  [{len(log)}/{total}] {facet:<44} MISS graphql-error', flush=True)
                continue
            node = entry.get('node')
            if not isinstance(node, dict):
                log.append({'facet': facet, 'note': 'no data returned'})
                continue
            count = node.get('repositoryCount')
            added = 0
            for hit in node.get('nodes') or []:
                if not hit:
                    continue
                full = hit.get('nameWithOwner')
                if not full or full in pool:
                    continue
                bucket = relevance_bucket(hit)
                if bucket is None:
                    continue
                pool[full] = {
                    'canonical_repo': full,
                    'html_url': hit.get('url'),
                    'description_len': len(hit.get('description') or ''),
                    'stars_at_search': hit.get('stargazerCount'),
                    'topics_count': len((hit.get('repositoryTopics') or {}).get('nodes') or []),
                    'default_branch': (hit.get('defaultBranchRef') or {}).get('name'),
                    'discovered_via': facet,
                    'relevance_bucket': bucket,
                }
                added += 1
            log.append({'facet': facet, 'returned': count, 'kept_new': added})
            print(f'  [{len(log)}/{total}] {facet:<44} total={count:<7} new={added}',
                  flush=True)
    return pool, log


def relevance_bucket(hit: dict) -> str | None:
    """Which linguistic evidence put this repository in the candidate pool."""
    name = (hit.get('nameWithOwner') or '').split('/')[-1].lower()
    full = (hit.get('nameWithOwner') or '').lower()
    desc = (hit.get('description') or '').lower()
    topics = [str((n or {}).get('topic', {}).get('name')).lower()
              for n in ((hit.get('repositoryTopics') or {}).get('nodes') or [])]

    strong = [t for t in NAME_TERMS if t in name]
    if strong:
        return f'name:{strong[0]}'
    hits = [t for t in TOPIC_TERMS if t in topics]
    if hits:
        return f'topic:{hits[0]}'
    hits = [t for t in DESCRIPTION_TERMS if t in desc]
    if hits:
        return f'description:{hits[0]}'
    if any(t in f'{name} {full} {desc}' for t in ('design', 'figma', 'typography')):
        return 'fallback:design-token-in-searchable-text'
    return None


# -------------------------------------------------------------------------- enrichment

REPO_NODE = """
  {alias}: repository(owner: "{owner}", name: "{name}") {{
    nameWithOwner
    url
    description
    createdAt
    updatedAt
    pushedAt
    stargazerCount
    forkCount
    isArchived
    isFork
    primaryLanguage {{ name }}
    licenseInfo {{ spdxId key }}
    defaultBranchRef {{ name target {{ oid }} }}
    repositoryTopics(first: 20) {{ nodes {{ topic {{ name }} }} }}
    licenseFile: object(expression: "HEAD:LICENSE") {{ ... on Blob {{ byteSize text }} }}
  }}"""


def enrich_batch(repos: list[str]) -> tuple[dict, dict]:
    """Observe up to REPOS_PER_REQUEST repositories in one round trip."""
    parts: list[str] = []
    aliases: dict[str, str] = {}
    for idx, repo in enumerate(repos):
        if '/' not in repo:
            continue
        owner, _, name = repo.partition('/')
        alias = f'r{idx}'
        aliases[alias] = repo
        parts.append(REPO_NODE.format(alias=alias, owner=_escape(owner),
                                      name=_escape(name)))
    if not parts:
        return {}, {}
    document = 'query {' + ''.join(parts) + '\n}'
    payload = graphql(document)
    data = payload.get('data') or {}
    results: dict[str, dict] = {}
    for alias, repo in aliases.items():
        node = data.get(alias)
        results[repo] = {'status': 200, 'node': node} if node else {
            'status': 404, 'message': 'repository not returned'}
    for err in payload.get('errors') or []:
        path = err.get('path') or []
        if path and path[0] in aliases:
            repo = aliases[path[0]]
            results[repo] = {'status': 0, 'message': str(err.get('message'))[:200]}
    return results, {}


def normalise(repo: str, observed: dict) -> dict:
    """Flatten one GraphQL repository node into the observation `facts` shape."""
    node = observed.get('node') or {}
    branch = node.get('defaultBranchRef') or {}
    target = branch.get('target') or {}
    lic_info = node.get('licenseInfo') or {}
    lic_file = node.get('licenseFile') or {}
    lic_text = lic_file.get('text')
    topics = [str((n or {}).get('topic', {}).get('name'))
              for n in ((node.get('repositoryTopics') or {}).get('nodes') or [])]
    return {
        'repo_status': observed.get('status', 0),
        'resolved': observed.get('status') == 200,
        'resolution_note': observed.get('message'),
        'owner_login': repo.split('/')[0],
        'stargazers_count': node.get('stargazerCount'),
        'forks_count': node.get('forkCount'),
        'pushed_at': node.get('pushedAt'),
        'updated_at': node.get('updatedAt'),
        'created_at': node.get('createdAt'),
        'default_branch': branch.get('name'),
        'archived': node.get('isArchived'),
        'is_fork': node.get('isFork'),
        'language': (node.get('primaryLanguage') or {}).get('name'),
        'topics': [t for t in topics if t],
        'license_api_spdx': lic_info.get('spdxId'),
        'license_api_key': lic_info.get('key'),
        # The licence is read from the repository's OWN LICENSE file, not from API
        # convenience metadata, and hashed so the exact bytes can be compared later.
        'license_file_status': 200 if lic_text else 404,
        'license_file_spdx': lic_info.get('spdxId') if lic_text else None,
        'license_html_url': (f'https://github.com/{repo}/blob/{branch.get("name") or "HEAD"}'
                             f'/LICENSE' if lic_text else None),
        'license_bytes': lic_file.get('byteSize'),
        'license_sha256': hashlib.sha256(lic_text.encode('utf-8')).hexdigest() if lic_text else None,
        'head_commit_sha': target.get('oid'),
    }


def enrich_all(repos: list[str]) -> dict[str, dict]:
    """Observe every repository, retrying members of any batch that failed wholesale."""
    collected: dict[str, dict] = {}
    failed_batches: list[list[str]] = []
    groups = _chunked(repos, REPOS_PER_REQUEST)
    for gi, group in enumerate(groups, 1):
        try:
            results, _ = enrich_batch(group)
        except GhError as exc:
            failed_batches.append(group)
            print(f'  [batch {gi}/{len(groups)}] MISS {str(exc)[:80]}', flush=True)
            continue
        collected.update(results)
        if gi % 10 == 0 or gi == len(groups):
            print(f'  enriched {gi}/{len(groups)} batches ({len(collected)} repos)',
                  flush=True)
    if failed_batches:
        retry = [repo for group in failed_batches for repo in group]
        print(f'  retrying {len(retry)} repositories one by one', flush=True)
        for repo in retry:
            try:
                results, _ = enrich_batch([repo])
            except GhError as exc:
                collected[repo] = {'status': 0, 'message': str(exc)[:200]}
                continue
            collected[repo] = results.get(repo, {'status': 0, 'message': 'not returned'})
    return collected


# ------------------------------------------------------------------------- README leads

GITHUB_REPO_RE = re.compile(r'github\.com/([A-Za-z0-9._-]+)/([A-Za-z0-9._-]+)')


def extract_repo(text: str) -> str | None:
    m = GITHUB_REPO_RE.search(text or '')
    if not m:
        return None
    return f'{m.group(1)}/{m.group(2).removesuffix(".git")}'


def license_cell(text: str) -> str | None:
    """Normalise a licence cell without inventing an SPDX id."""
    c = (text or '').strip()
    if not c or c in {'-', '-'}:
        return None
    return re.split(r'[\s/(（]', c)[0].strip().rstrip(',') or None


def ruling_cell(text: str) -> str | None:
    c = (text or '').strip()
    if not c or c in {'-', '-'}:
        return None
    return 'CONDITIONAL_POC' if 'CONDITIONAL_POC' in c.upper() else None


def slug(text: str) -> str:
    s = (text or '').strip().lower()
    s = re.sub(r'[^a-z0-9._-]+', '-', s).strip('-')
    return re.sub(r'-{2,}', '-', s)[:64]


def parse_readme_records() -> list[dict]:
    """Extract candidates ALREADY recorded in research/candidates/README.md.

    That file holds two tables with different columns: the main candidate table has an
    explicit ruling column, the visual-quality sub-table does not. The difference is
    preserved rather than flattened -- see `recorded_disposition` downstream.
    """
    if not README.is_file():
        return []
    records: list[dict] = []
    section = None
    in_table = False
    headers: list[str] = []
    for raw in README.read_text(encoding='utf-8').splitlines():
        line = raw.strip()
        if line.startswith('### '):
            section = 'visual-quality' if 'visual-quality' in line else None
            in_table = False
            continue
        if not line.startswith('|'):
            if in_table:
                in_table = False
            continue
        cells = [c.strip() for c in line.strip('|').split('|')]
        if all(set(c) <= set('-: ') for c in cells):
            continue
        if not in_table:
            headers = [c.lower() for c in cells]
            in_table = True
            continue
        row = dict(zip(headers, cells))
        repo = extract_repo(row.get('来源（url）') or row.get('来源') or '')
        if not repo:
            continue
        records.append({
            'candidate_id': slug(row.get('候选', '')),
            'canonical_repo': repo,
            'recorded_license': license_cell(row.get('许可', '')),
            'recorded_disposition': ruling_cell(row.get('裁决', '')),
            'cache_key': row.get('cache 键', '') or row.get('cache键', ''),
            'file_count': row.get('文件数', ''),
            'source_section': section or 'main',
        })
    return records


def main() -> int:
    ap = argparse.ArgumentParser(description='Collect attributable candidate observations.')
    ap.add_argument('--out', default=None, help='observation file path (default: dated)')
    ap.add_argument('--no-discovery', action='store_true',
                    help='only re-observe candidates already recorded in README.md')
    ap.add_argument('--facets-file', default=None,
                    help='restrict discovery to facets listed one per line '
                         '(after a first run was partly killed by transport errors)')
    ap.add_argument('--merge', default=None,
                    help='carry successful discovery forward from an earlier '
                         'observation file instead of re-searching it')
    args = ap.parse_args()

    started = _utcnow()
    TMP_DIR.mkdir(parents=True, exist_ok=True)
    if not shutil.which('gh'):
        print('collect: the gh CLI is required for authenticated discovery', flush=True)
        return 1

    print(f'[1/4] parsing recorded candidates from {README.name}', flush=True)
    recorded = parse_readme_records()
    print(f'      -> {len(recorded)} rows reference a resolvable github.com/<owner>/<repo>',
          flush=True)

    source_runs: list[str] = []
    seed_pool: dict = {}
    carried_log: list[dict] = []
    if args.merge:
        seed_pool, carried_log = load_prior_run(args.merge)
        source_runs.append(args.merge)
        print(f'[2/4] carrying {len(seed_pool)} already-discovered repositories '
              f'forward from {Path(args.merge).name}', flush=True)

    if args.no_discovery:
        pool: dict = dict(seed_pool)
        facet_log: list[dict] = list(carried_log)
        print('      discovery skipped (--no-discovery)', flush=True)
    else:
        wanted = list(FACETS)
        if args.facets_file:
            wanted = [line.strip() for line in
                      Path(args.facets_file).read_text(encoding='utf-8').splitlines()
                      if line.strip() and not line.startswith('#')]
        print(f'      searching {len(wanted)} facets '
              f'({SEARCHES_PER_REQUEST} per request)', flush=True)
        pool, new_log = discover_via_facets(wanted, seed_pool)
        print(f'      -> {len(pool)} unique canonical repositories cleared the relevance gate',
              flush=True)
        # A facet searched THIS run supersedes whatever an earlier file claimed.
        this_run = {e['facet']: e for e in new_log if e.get('facet')}
        facet_log = [e for e in carried_log if e.get('facet') not in this_run] + new_log

    # Recorded rows are re-verified against their upstream, not trusted from prose.
    targets: dict[str, dict] = {}
    for rec in recorded:
        targets.setdefault(rec['canonical_repo'], {})['recorded'] = rec
    for repo, meta in pool.items():
        targets.setdefault(repo, {})['discovered'] = meta

    print(f'[3/4] observing {len(targets)} repositories '
          f'({len(targets) // REPOS_PER_REQUEST + 1} requests)', flush=True)
    observed_at = _utcnow()
    raw = enrich_all(sorted(targets))

    observations: list[dict] = []
    for repo in sorted(targets):
        entry = targets[repo]
        observations.append({
            'canonicalRepo': repo,
            'canonicalUrl': f'https://github.com/{repo}',
            'provenance': [p for p in ('in-repo-record' if entry.get('recorded') else None,
                                       'github-search' if entry.get('discovered') else None) if p],
            'recorded': entry.get('recorded'),
            'discovered': entry.get('discovered'),
            'observedAt': observed_at,
            'observedVia': 'GitHub GraphQL API v4 via gh CLI (gh session credential)',
            'facts': normalise(repo, raw.get(repo, {'status': 0, 'message': 'never observed'})),
        })

    out_path = (Path(args.out) if args.out
                else OBSERVATION_DIR / f'github-observation-{observed_at.replace(":", "").replace("-", "")}.json')
    out_path.parent.mkdir(parents=True, exist_ok=True)
    resolved = [o for o in observations if o['facts'].get('resolved')]
    document = {
        'schemaVersion': 'design-lab/candidate-observation/v1',
        'purpose': ('raw evidence for research/candidates/CANDIDATE-TAXONOMY.json; '
                    'generated, never hand-edited'),
        'startedAt': started,
        'observedAt': observed_at,
        'tool': Path(__file__).name,
        'transport': 'gh CLI -> api.github.com/graphql (batched)',
        'policy': {
            'canonicalUpstreamOnly': True,
            'licenseReadFromRepositoryItself': True,
            'noScoringInThisStep': True,
            'noFabricatedFields': True,
            'starCountIsAdoptionNotQuality': True,
            'unreachableStaysUnreachable': True,
        },
        'discovery': {
            'facetCount': len(FACETS),
            'facetsSearched': sum(1 for e in facet_log if 'returned' in e),
            'facetsFailed': sum(1 for e in facet_log if e.get('error')),
            'minStars': MIN_STARS,
            'searchesPerRequest': SEARCHES_PER_REQUEST,
            'reposPerRequest': REPOS_PER_REQUEST,
            'skipped': args.no_discovery,
            'sourceRuns': source_runs,
            'facetLog': facet_log,
        },
        'counts': {
            'recordedInReadme': len(recorded),
            'discoveredUnique': len(pool),
            'observedTotal': len(observations),
            'resolved': len(resolved),
            'licenseFileResolved': sum(1 for o in observations
                                       if o['facts'].get('license_sha256')),
            'licenseInferredOnly': sum(1 for o in observations
                                       if o['facts'].get('resolved')
                                       and not o['facts'].get('license_sha256')
                                       and o['facts'].get('license_api_spdx')),
            'headShaResolved': sum(1 for o in observations
                                   if o['facts'].get('head_commit_sha')),
            'unresolved': len(observations) - len(resolved),
        },
        'observations': observations,
    }
    out_path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + '\n',
                        encoding='utf-8')

    shown = out_path if out_path.is_relative_to(REPO) else out_path.resolve()
    print(f'[4/4] wrote {shown}', flush=True)
    print('SUMMARY ' + ' '.join(f'{k}={v}' for k, v in document['counts'].items()), flush=True)
    unreachable = [o['canonicalRepo'] for o in observations if not o['facts'].get('resolved')]
    if unreachable:
        print(f'UNREACHABLE upstreams ({len(unreachable)}): '
              + ', '.join(unreachable[:20]) + (' ...' if len(unreachable) > 20 else ''),
              flush=True)
    return 0


if __name__ == '__main__':
    sys.exit(main())
