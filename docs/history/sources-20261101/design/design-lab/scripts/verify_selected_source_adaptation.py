#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-FINAL-T07: a selected source may be distilled, but registering it is not integrating it.

`packages/capabilities/selected-sources.json` records the few external sources this
task actually read, what method was taken from each, where that method lands in
DESIGN-LAB, and what execution qualification the landing can honestly carry. The
acceptance clauses it exists to enforce are:

  * popularity is a filter, never a selection reason or a quality claim -- the star
    count is copied into `adoptionFilter` and may not be restated as a basis;
  * registration is not integration -- `REGISTERED_ONLY` is the default, and a landing
    may only say `MAPPED` when the target file really carries the distilled rule id,
    and `CONSUMED` only with a test that drives the target and an evidence level the
    adapter registry can support;
  * the revision, licence and removal path are COPIED FROM the candidate taxonomy, byte
    for byte, so a record cannot quietly upgrade a licence or invent a pinned commit;
  * execution qualification comes from the published vocabulary in
    `design-lab/config/capability-status.json`, and a state above `declared-only` needs
    evidence references that resolve through the same reader-root predicate the ledger
    uses -- a pass word with no evidence is a finding;
  * an unpinned revision quarantines the whole record (nothing above
    `declared-only`, no mapped landing);
  * every distilled method is cited by file + line range, and the quote is re-read from
    the vendored blob when that blob is on disk.

It also derives one real validator out of the distilled motion rule and runs it over the
Workbench stylesheet: the count is reported, and a recorded deviation that no longer
matches -- or a new one that is not recorded -- is a finding.

Read-only. Fails when the scan matches nothing, so a broken scan and a clean tree never
share a verdict.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
DEFAULT_DOC = REPO / 'packages' / 'capabilities' / 'selected-sources.json'
TAXONOMY = REPO / 'research' / 'candidates' / 'CANDIDATE-TAXONOMY.json'
CAPABILITY_STATUS = REPO / 'design-lab' / 'config' / 'capability-status.json'
POLICY = REPO / 'packages' / 'capabilities' / 'governance' / 'OPEN_SOURCE_ABSORPTION_POLICY.md'
ADAPTERS = REPO / 'integrations' / 'adapter-registry.json'
SELF = Path(__file__).resolve()

MAX_SELECTED = 12
KINDS = {'Quality', 'Method', 'Adapter', 'DomainPack'}
MODES = ('REGISTERED_ONLY', 'MAPPED', 'CONSUMED')
MODE_RANK = {mode: rank for rank, mode in enumerate(MODES)}
# adapter-registry.json status_model, ordered by what it can support.
ADAPTER_RANK = {'missing': -1, 'BLOCKED_BY_LICENSE': -1, 'declared': 0,
               'structural': 1, 'runtime': 2}
# capabilityStates are ranked by the promotion rules in capability-status.json.
STATE_RANK = {'missing': 0, 'declared-only': 1, 'structural-pass': 2, 'isolated-pass': 3,
              'runtime-pass': 4, 'release-verified': 5, 'commercially-proven': 6,
              'blocked': 0, 'superseded': 0}
LEVEL_MAX_STATE = {'candidate': 'declared-only', 'quarantined': 'declared-only',
                   'statically_verified': 'structural-pass', 'runtime_loaded': 'isolated-pass',
                   'task_proven': 'runtime-pass', 'commercially_proven': 'commercially-proven'}
POPULARITY = re.compile(r'\bstar(?:s|Count)?\b|\bforks?\b|热度|流行|热门|trending|viral|popular',
                        re.I)
NEGATION = re.compile(r'无关|不是|不等于|不得|不作|不纳入|not\s+a\s|never|refut', re.I)
EVIDENCE_ONLY_ABOVE_DECLARED = {'missing', 'declared-only'}

LAYOUT = re.compile(r'(?<![a-z-])(width|height|top|left|right|bottom|margin|margin-\w+|'
                    r'padding|padding-\w+)(?![a-z-])')
MOTION_DECL = re.compile(r'(transition|animation)\s*:\s*([^;{}]*)')


class Load:
    """Everything the gate compares the record against, read once."""

    def __init__(self, root: Path):
        self.root = root
        self.taxonomy = json.loads((root / TAXONOMY.relative_to(REPO)).read_text(encoding='utf-8'))
        self.entries = {e['candidateId']: e for e in self.taxonomy['entries']}
        status = json.loads((root / CAPABILITY_STATUS.relative_to(REPO)).read_text(encoding='utf-8'))
        self.states = list(status['capabilityStates'])
        self.levels = [lv['id'] for lv in status['evidenceLevels']]
        registry = json.loads((root / ADAPTERS.relative_to(REPO)).read_text(encoding='utf-8'))
        self.adapters = {r['adapter_id']: r for r in registry['adapters']}
        self.adapter_status = registry.get('status_model', {})
        self.ladder = self._ladder(root / POLICY.relative_to(REPO))

    @staticmethod
    def _ladder(path: Path) -> list:
        for line in path.read_text(encoding='utf-8').splitlines():
            stripped = line.strip().strip('`')
            if stripped.startswith('candidate ->'):
                return [p.strip() for p in stripped.split('->')]
        raise ValueError('no promotion ladder line ("candidate -> ...") in '
                         f'{path.name}; the record cannot be graded against a missing ladder')

    def rel(self, value: str) -> Path:
        return (self.root / value)


def reader_permitted(root: Path, relative: str):
    """Resolve a cited path through the ledger reader's own root policy.

    Shared, never re-typed: `design-lab` receipts already reject paths outside the
    declared public roots, and a record that cites `.project-local/cache/...` must meet
    the same refusal here, or the two lists would drift apart.
    """
    sys.path.insert(0, str(root / 'src'))
    from design_lab.governance.reporting import _safe  # noqa: E402  (the live predicate)
    return _safe(root, relative)


def composited_motion_violations(root: Path, relative_files) -> list:
    """SRC-T07-MOTION-COMPOSITED as a deterministic check over CSS."""
    found = []
    for rel in relative_files:
        path = root / rel
        if not path.is_file():
            found.append({'file': rel, 'line': 0, 'property': 'FILE_MISSING',
                          'declaration': ''})
            continue
        for lineno, line in enumerate(path.read_text(encoding='utf-8', errors='replace')
                                      .splitlines(), 1):
            for match in MOTION_DECL.finditer(line):
                hit = LAYOUT.search(match.group(2))
                if hit:
                    found.append({'file': rel, 'line': lineno, 'property': hit.group(1),
                                  'declaration': f'{match.group(1)}: {match.group(2).strip()}'})
    return found


def _popularity_as_reason(text: str) -> str:
    """Return the offending clause when popularity is used as a reason, not refuted."""
    for match in POPULARITY.finditer(text):
        window = text[max(0, match.start() - 40):match.end() + 40]
        if not NEGATION.search(window):
            return match.group(0)
    return ''


VERDICT_KEY = re.compile(r'(status|state|level|claim|mode|usedfor)$', re.I)


def _status_fields(node, path='record'):
    """Every verdict-shaped key in the record, so an invented PASS word is visible.

    Matched on the key's ENDING, not anywhere inside it: `statement` contains the
    letters of `state`, and convicting a prose field made this check fire on every
    record in the file on its first run.
    """
    out = []
    if isinstance(node, dict):
        for key, value in node.items():
            if VERDICT_KEY.search(key) and isinstance(value, str):
                out.append((f'{path}.{key}', value))
            out.extend(_status_fields(value, f'{path}.{key}'))
    elif isinstance(node, list):
        for index, item in enumerate(node):
            out.extend(_status_fields(item, f'{path}[{index}]'))
    return out


def unmeasured(value) -> bool:
    """The taxonomy's own way of saying "nobody measured this".

    `nullMeansUnmeasured` is the declared policy, but the machine projection leaves
    `designQuality` as an EMPTY OBJECT rather than null, so treating only `None` as
    unmeasured read a never-scored axis as a score -- and let an unmeasured row claim
    the opposite of what was measured.
    """
    return value is None or (isinstance(value, (dict, list, str)) and not value)


def check_record(rec: dict, load: Load, findings: list, stats: dict) -> None:
    sid = rec.get('sourceId', '<missing sourceId>')
    entry = load.entries.get(sid)
    if entry is None:
        findings.append(f'{sid}: not a row in CANDIDATE-TAXONOMY.json -- a selected source must '
                        f'already be a registered candidate')
        return
    if entry['disposition'] != 'CONDITIONAL_POC':
        findings.append(f'{sid}: disposition is {entry["disposition"]}, not CONDITIONAL_POC -- '
                        f'only human-triaged candidates may be distilled this way')

    # --- copied by reference, never retyped --------------------------------------------
    for field, expected, label in (
        ('pinnedCommitSHA', (rec.get('revision') or {}).get('pinnedCommitSHA'), 'revision'),
        ('removalPath', (rec.get('withdrawal') or {}).get('removalPath'), 'withdrawal.removalPath'),
    ):
        if entry.get(field) != expected:
            findings.append(f'{sid}: {label} says {expected!r} but the taxonomy row says '
                            f'{entry.get(field)!r} -- it must be copied from the taxonomy')
    rights = (entry.get('rights') or {}).get('license')
    if (rec.get('license') or {}).get('id') != rights:
        findings.append(f'{sid}: license.id {rec.get("license", {}).get("id")!r} != taxonomy '
                        f'rights.license {rights!r} -- a record may not upgrade a licence')
    metrics = (entry.get('adoption') or {}).get('metrics') or {}
    filt = rec.get('adoptionFilter') or {}
    if filt.get('usedFor') != 'FILTER_ONLY' or filt.get('qualitySignal') is not False:
        findings.append(f'{sid}: adoptionFilter must be usedFor=FILTER_ONLY with '
                        f'qualitySignal=false (policy: popularityIsNotQuality)')
    for key in ('stargazerCount', 'forkCount'):
        if filt.get(key) != metrics.get(key):
            findings.append(f'{sid}: adoptionFilter.{key} {filt.get(key)!r} != taxonomy '
                            f'{metrics.get(key)!r} -- adoption is copied, not restated')

    # --- popularity cannot be a reason -------------------------------------------------
    for reason in rec.get('selectionBasis') or []:
        bad = _popularity_as_reason(str(reason))
        if bad:
            findings.append(f'{sid}: selectionBasis uses {bad!r} as a reason; adoption may only '
                            f'be copied into adoptionFilter (FILTER_ONLY) or refuted')
    if not rec.get('selectionBasis'):
        findings.append(f'{sid}: no selectionBasis -- a source cannot be selected without a '
                        f'stated capability reason')

    # --- quality is not claimed until a human measured it ------------------------------
    unmeasured_quality = unmeasured(entry.get('designQuality')) and unmeasured(entry.get('tier'))
    if unmeasured_quality and rec.get('qualityClaim') != 'NOT_MEASURED':
        findings.append(f'{sid}: qualityClaim {rec.get("qualityClaim")!r} while the taxonomy row '
                        f'is still unmeasured (designQuality/tier empty -- unmeasured is never a '
                        f'claim)')
    if not unmeasured_quality and rec.get('qualityClaim') != 'NOT_MEASURED' and not entry.get('humanApprovalRef'):
        findings.append(f'{sid}: a measured quality claim needs humanApprovalRef in the taxonomy '
                        f'row (policy: humanReviewOnly)')

    # --- revision / quarantine ladder --------------------------------------------------
    sha = entry.get('pinnedCommitSHA')
    declared_status = (rec.get('revision') or {}).get('status')
    want_status = 'PINNED' if sha else 'UNPINNED'
    if declared_status != want_status:
        findings.append(f'{sid}: revision.status must be {want_status} for pinnedCommitSHA '
                        f'{sha!r}')
    unpinned = not sha
    level = rec.get('promotionLevel')
    if level not in load.ladder:
        findings.append(f'{sid}: promotionLevel {level!r} is not in the ladder published by '
                        f'OPEN_SOURCE_ABSORPTION_POLICY.md {load.ladder}')
    mapped = [l for l in rec.get('landing') or [] if l.get('mode') in ('MAPPED', 'CONSUMED')]
    want_level = 'quarantined' if unpinned else ('statically_verified' if mapped else 'candidate')
    if level != want_level:
        findings.append(f'{sid}: promotionLevel says {level!r} but the recorded evidence supports '
                        f'{want_level!r} (unpinned revision quarantines the record; a landing is '
                        f'MAPPED only when the rule id is present in the target)')

    # --- landings ----------------------------------------------------------------------
    methods = {m.get('id') for m in rec.get('method') or []}
    applies_to = []
    for land in rec.get('landing') or []:
        mode = land.get('mode')
        path = land.get('path')
        if mode not in MODES:
            findings.append(f'{sid}: landing mode {mode!r} not in {MODES}')
            continue
        if land.get('kind') not in KINDS:
            findings.append(f'{sid}: landing kind {land.get("kind")!r} not in {sorted(KINDS)}')
        target = load.rel(path or '')
        if not path or not target.exists():
            findings.append(f'{sid}: landing path {path!r} does not exist -- a landing must name a '
                            f'real DESIGN-LAB component, not a wish')
            continue
        if land['kind'] == 'DomainPack' and not path.startswith('design-lab/domain-packs/'):
            findings.append(f'{sid}: DomainPack landing {path!r} is outside design-lab/domain-packs '
                            f'-- no parallel domain taxonomy')
        if mode == 'REGISTERED_ONLY':
            stats['registered_only'] += 1
            if not land.get('notYetReason'):
                findings.append(f'{sid}: REGISTERED_ONLY landing {path!r} needs notYetReason -- '
                                f'registration must say what is still missing')
            if land.get('ruleId'):
                findings.append(f'{sid}: REGISTERED_ONLY landing {path!r} carries ruleId '
                                f'{land["ruleId"]!r}; a registered-only landing has not written '
                                f'anything into the target')
        else:
            rule = land.get('ruleId')
            if not rule:
                findings.append(f'{sid}: {mode} landing {path!r} must name the distilled ruleId')
                continue
            if land.get('derivedFromMethod') not in methods:
                findings.append(f'{sid}: {mode} landing {path!r} derivedFromMethod '
                                f'{land.get("derivedFromMethod")!r} is not a method id in this record')
            body = target.read_text(encoding='utf-8', errors='replace')
            if rule not in body:
                findings.append(f'{sid}: {mode} landing {path!r} does not contain {rule!r} -- '
                                f'registering a source is not integrating it')
            else:
                stats['mapped'] += 1
            if mode == 'CONSUMED':
                stats['mapped'] -= 1
                stats['consumed'] += 1
                proof = land.get('proof') or {}
                test = load.rel(proof.get('testPath') or '')
                if not test.is_file():
                    findings.append(f'{sid}: CONSUMED landing {path!r} proof.testPath '
                                    f'{proof.get("testPath")!r} is not a file')
                else:
                    text = test.read_text(encoding='utf-8', errors='replace')
                    if rule not in text or Path(path).name not in text:
                        findings.append(f'{sid}: CONSUMED landing {path!r} needs a test that names '
                                        f'both {rule!r} and {Path(path).name!r}')
                if (rec.get('executionQualification') or {}).get('evidenceLevel') in (None, 'E0', 'E1'):
                    findings.append(f'{sid}: CONSUMED requires evidence level E2 or above; the '
                                    f'record still says {(rec.get("executionQualification") or {}).get("evidenceLevel")!r}')
        if land['kind'] == 'Adapter':
            aid = land.get('adapterId')
            row = load.adapters.get(aid) if aid else None
            if aid and row is None:
                findings.append(f'{sid}: adapterId {aid!r} has no row in adapter-registry.json -- '
                                f'an adapter claim without a registry row is not integration')
                continue
            if row is not None:
                rank = ADAPTER_RANK.get(row.get('status'), -2)
                if rank < 0 and mode != 'REGISTERED_ONLY':
                    findings.append(f'{sid}: adapter {aid} is {row.get("status")} in the registry, '
                                    f'so the record may not claim {mode}')
                if mode in ('MAPPED', 'CONSUMED') and rank < 1:
                    findings.append(f'{sid}: adapter {aid} registry status {row.get("status")!r} '
                                    f'cannot support a {mode} landing')
        for rel in land.get('appliesTo') or []:
            applies_to.append((rel, land))

    # --- the derived validator against real bytes --------------------------------------
    for rel, land in applies_to:
        if not (load.root / rel).is_file():
            findings.append(f'{sid}: appliesTo {rel} is not a file')
    motion = [(rel, land) for rel, land in applies_to
              if land.get('ruleId') == 'SRC-T07-MOTION-COMPOSITED']
    if motion:
        rel = sorted({r for r, _ in motion})
        live = composited_motion_violations(load.root, rel)
        recorded = motion[0][1].get('knownDeviations') or []
        stats['motion_deviations'] = len(live)
        for item in live:
            if item['declaration'] not in {r.get('declaration') for r in recorded}:
                findings.append(f'{sid}: {item["file"]}:{item["line"]} animates {item["property"]} '
                                f'-- a new deviation from {land.get("ruleId")}; fix the CSS or '
                                f'record it, do not widen silently')
        for item in recorded:
            if item['declaration'] not in {l['declaration'] for l in live}:
                findings.append(f'{sid}: recorded deviation {item["declaration"]!r} no longer '
                                f'exists -- drop it from knownDeviations')

    # --- execution qualification -------------------------------------------------------
    qual = rec.get('executionQualification') or {}
    state = qual.get('capabilityState')
    if state not in load.states:
        findings.append(f'{sid}: capabilityState {state!r} is not a state published by '
                        f'capability-status.json')
    else:
        ceiling = LEVEL_MAX_STATE.get(level)
        if ceiling and STATE_RANK[state] > STATE_RANK[ceiling]:
            findings.append(f'{sid}: capabilityState {state!r} exceeds what promotion level '
                            f'{level!r} can carry (ceiling {ceiling!r})')
    if qual.get('evidenceLevel') not in load.levels:
        findings.append(f'{sid}: evidenceLevel {qual.get("evidenceLevel")!r} is not an evidence '
                        f'level in capability-status.json {load.levels}')
    refs = qual.get('evidenceRefs') or []
    if STATE_RANK.get(state, 0) > STATE_RANK['declared-only']:
        if not refs:
            findings.append(f'{sid}: {state} without evidenceRefs -- a state above declared-only '
                            f'needs the artifact that measured it')
        for ref in refs:
            try:
                resolved = reader_permitted(load.root, ref)
            except Exception as exc:
                findings.append(f'{sid}: evidenceRef {ref!r} is rejected by the ledger reader '
                                f'roots ({exc}) -- it cannot be cited as public evidence')
                continue
            if not resolved.exists():
                findings.append(f'{sid}: evidenceRef {ref!r} does not exist on disk')

    # --- citations ---------------------------------------------------------------------
    if not rec.get('method'):
        findings.append(f'{sid}: no distilled method -- the source is still only a bookmark')
    if not rec.get('counterExamples'):
        findings.append(f'{sid}: no counter-example -- a distilled method with no stated limit '
                        f'is an unbounded claim')
    for meth in rec.get('method') or []:
        cite = meth.get('citation') or {}
        lines = cite.get('lines') or []
        quote = cite.get('quote') or ''
        if len(lines) != 2 or not quote:
            findings.append(f'{sid}: {meth.get("id")} citation needs lines [a,b] and a quote')
            continue
        span = lines[1] - lines[0] + 1
        if cite.get('lineCount') != span or len(quote.splitlines()) != span:
            findings.append(f'{sid}: {meth.get("id")} quote has {len(quote.splitlines())} lines but '
                            f'cites {lines} ({span} lines)')
        if meth.get('derivedCheck'):
            own = SELF.read_text(encoding='utf-8')
            if f'def {meth["derivedCheck"]}(' not in own:
                findings.append(f'{sid}: {meth.get("id")} claims derivedCheck '
                                f'{meth["derivedCheck"]!r} but this gate does not define it')
        source_file = str(cite.get('sourceFile') or '')
        prefix = f'.project-local/cache/vendor/{sid}/'
        if not source_file.startswith(prefix):
            findings.append(f'{sid}: citation sourceFile {source_file!r} is not inside this '
                            f'source\'s blob ({prefix}...)')
            continue
        blob = load.root / prefix / source_file[len(prefix):]
        if blob.is_file():
            body = blob.read_text(encoding='utf-8', errors='replace').splitlines()
            actual = '\n'.join(body[lines[0] - 1:lines[1]])
            stats['crosschecked'] += 1
            if actual != quote:
                findings.append(f'{sid}: {meth.get("id")} quote does not match '
                                f'{Path(source_file).name} lines {lines} on disk -- the excerpt '
                                f'was not taken from there')
        else:
            stats['crosscheck_skipped'] += 1

    # --- task test + withdrawal ---------------------------------------------------------
    test_file = load.rel((rec.get('taskTest') or {}).get('file') or '')
    if not test_file.is_file():
        findings.append(f'{sid}: taskTest.file {test_file.name!r} is not a file')
    else:
        body = test_file.read_text(encoding='utf-8', errors='replace')
        for name in (rec.get('taskTest') or {}).get('tests') or []:
            if f'def {name}(' not in body:
                findings.append(f'{sid}: taskTest names {name}() but that test is not defined in '
                                f'{test_file.relative_to(load.root).as_posix()}')
        if not (rec.get('taskTest') or {}).get('tests'):
            findings.append(f'{sid}: no taskTest -- a selected source must be exercised, not just cited')
    wd = rec.get('withdrawal') or {}
    if not wd.get('restore'):
        findings.append(f'{sid}: withdrawal has no restore path')
    for path in wd.get('restoreCommandPaths') or []:
        if not load.rel(path).is_file():
            findings.append(f'{sid}: restoreCommandPaths entry {path!r} does not exist')

    # --- invented verdict words ---------------------------------------------------------
    vocab = {'status': {'PINNED', 'UNPINNED'},
             'usedfor': {'FILTER_ONLY'},
             'qualityclaim': {'NOT_MEASURED'},
             'promotionlevel': set(load.ladder),
             'capabilitystate': set(load.states),
             'evidencelevel': set(load.levels),
             'mode': set(MODES)}
    for dotted, value in _status_fields(rec, 'record'):
        tail = dotted.split('.')[-1].lower()
        if tail not in vocab:
            if re.search(r'status|state|level|claim|mode', tail, re.I):
                findings.append(f'{sid}: {dotted} is a verdict-shaped field with no published '
                                f'vocabulary; either map it in this gate or remove it')
            continue
        if value not in vocab[tail]:
            findings.append(f'{sid}: {dotted}={value!r} is not in the published vocabulary '
                            f'{sorted(vocab[tail])} -- verdict words are graded, not invented')


def check(doc: dict, load: Load) -> tuple[list, dict]:
    findings: list = []
    stats = {'registered_only': 0, 'mapped': 0, 'consumed': 0, 'motion_deviations': 0,
             'crosschecked': 0, 'crosscheck_skipped': 0}
    records = doc.get('selected') or []
    if not records:
        return [f'{DEFAULT_DOC.relative_to(REPO).as_posix()} selects nothing -- an empty selection '
                f'is not a pass, it means the scan verified nothing'], stats
    if len(records) > MAX_SELECTED:
        findings.append(f'{len(records)} selected sources exceed the {MAX_SELECTED}-source bound of '
                        f'this task (acceptance: not all 980 candidates have to be absorbed)')
    seen = set()
    for rec in records:
        sid = rec.get('sourceId')
        if sid in seen:
            findings.append(f'{sid}: listed twice')
        seen.add(sid)
        check_record(rec, load, findings, stats)
    uni = doc.get('universe') or {}
    poc = sum(1 for e in load.taxonomy['entries'] if e['disposition'] == 'CONDITIONAL_POC')
    if uni.get('taxonomyEntries') != len(load.taxonomy['entries']):
        findings.append(f'universe.taxonomyEntries {uni.get("taxonomyEntries")!r} != '
                        f'{len(load.taxonomy["entries"])} rows now in the taxonomy')
    if uni.get('conditionalPoc') != poc:
        findings.append(f'universe.conditionalPoc {uni.get("conditionalPoc")!r} != {poc} now')
    if uni.get('selected') != len(records):
        findings.append(f'universe.selected {uni.get("selected")!r} != {len(records)} records')
    if uni.get('absorbAllRequired') is not False:
        findings.append('universe.absorbAllRequired must be false -- this task does not absorb the pool')
    for ref in doc.get('authorityRefs') or []:
        if not load.rel(ref).exists():
            findings.append(f'authorityRefs entry {ref!r} does not exist')
    if not doc.get('authorityRefs'):
        findings.append('no authorityRefs: the record cites no policy, so its rules are decoration')
    return findings, stats


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--root', default=str(REPO),
                        help='repository root to check against (a test may point this at a fixture)')
    parser.add_argument('--doc', default=None, help='selected-sources.json override (fixtures)')
    args = parser.parse_args()
    root = Path(args.root)
    doc_path = Path(args.doc) if args.doc else root / DEFAULT_DOC.relative_to(REPO)
    if not doc_path.is_file():
        print(f'SELECTED_SOURCES=FAIL doc_missing={doc_path.relative_to(root) if doc_path.is_relative_to(root) else doc_path}')
        return 1
    try:
        load = Load(root)
    except Exception as exc:
        print(f'SELECTED_SOURCES=FAIL inputs_unreadable={type(exc).__name__}: {exc}')
        return 1
    doc = json.loads(doc_path.read_text(encoding='utf-8'))
    findings, stats = check(doc, load)
    for finding in findings:
        print(f'  FINDING: {finding}')
    summary = (f'records={len(doc.get("selected") or [])} '
               f'registered_only={stats["registered_only"]} mapped={stats["mapped"]} '
               f'consumed={stats["consumed"]} motion_deviations={stats["motion_deviations"]} '
               f'citations=VERIFIED({stats["crosschecked"]})/SKIPPED({stats["crosscheck_skipped"]})')
    if findings:
        print(f'SELECTED_SOURCES=FAIL findings={len(findings)} {summary}')
        return 1
    print(f'SELECTED_SOURCES=OK {summary}')
    # Printed on a PASSING run too, deliberately. This note used to live inside the
    # `if findings:` branch, so the one case where it mattered most was the case that never
    # printed it: a clean clone, where the vendored blobs are absent, every citation is
    # skipped, the count reads VERIFIED(0), and the run is green while having re-read
    # nothing. "Green" and "checked" have to be separable by whoever reads the line.
    if stats['crosscheck_skipped']:
        print('  note: SKIPPED citations are inside the gitignored vendor cache; CI cannot '
              're-read them, so the recorded line spans are the only check that ran there')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
