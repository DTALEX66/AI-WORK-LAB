#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-RIGHTS-REGISTRY: the RIGHTS requirements list must be internally true and classified.

Why this gate exists. ``design-lab/config/rights-registry.json`` is the only place in the
repository that enumerates what the RIGHTS human gate has to rule on: 74 licence subjects,
each with four recorded positions (``territory.state``, ``use_restriction``,
``output_restriction``, ``redistribution``). The registry's own ``field_meaning`` says an
unrecorded position means "the decision owner must supply one. The registry never guesses a
legal position." ``src/design_lab/assurance/handoff_readiness.py`` classified those positions
into blocking / restricting / clean bands -- as a **hand-written copy of the value set** under
a comment calling it "the frozen rights-registry.json set". A copy is a second authority able
to disagree with the first, and the disagreement went one way only: a state value that appeared
in the registry but in none of the three bands fell into an ``else`` that emitted a WARNING,
and ``READY_FOR_HANDOFF`` requires an empty BLOCKER list. An unruled licence position -- a new
state added under another taskpack, or a misspelling of ``FORBIDDEN`` -- therefore read as
"nothing blocks". That is a fail-open on the RIGHTS link, and it is fixed in the module, not
here; this file keeps the copy honest.

What it enforces, each with its own refusal code:

1. LIVENESS -- the file must exist, parse, bind ``design-lab/rights-registry/v1``, and carry at
   least one entry. Zero entries is red: a registry that lists nothing requires nothing, and a
   verdict computed over it is vacuous rather than clean.
2. SHAPE -- every entry must state a ``subject_id`` and no subject may be listed twice. A
   duplicated subject would be counted as two satisfied positions and shrink the gate.
3. BAND COVERAGE -- every value present in the file, over all four fields, must fall in one of
   the bands the *live module* defines (imported, never re-typed here). The unclassified value
   also blocks inside the combiner now, so a drift can neither pass silently nor stay invisible.
4. DERIVED FIELD HONESTY -- ``counts`` is a hand-maintained summary of ``entries``. All four of
   its numbers are recomputed here from the entries, under definitions stated in this file, and
   each must equal the recorded number. A summary nobody recomputes is how a projection rots.
5. PROVENANCE RESOLVES -- every path in ``generated_from`` and every per-entry
   ``evidence_source`` must exist under the repository root. A licence subject whose cited
   evidence file is gone is not evidence; it is a claim with a filename in it.

Freshness is reported, not enforced: ``generated_at`` and the entry-level ``refresh_policy`` are
printed so an operator sees how old the observation is, and the enforcement already exists in
band 3 -- 70 of the 74 subjects are ``NOT_ADJUDICATED``, which is a BLOCKER in the combiner, so
an ageing registry cannot reach a ready verdict on its own.

Nothing here supplies a legal position. The gate reads what the registry recorded, refuses a
registry that contradicts itself, and never decides which subjects a project actually uses --
that selection is the owner's RIGHTS gate decision and is deliberately not invented here.

Exit 0 with ``RIGHTS_REGISTRY=OK``, or 1 with ``RIGHTS_REGISTRY=FAIL`` and one line per finding.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO / 'src'))

REGISTRY_REL = 'design-lab/config/rights-registry.json'
MODULE_REL = 'src/design_lab/assurance/handoff_readiness.py'
REGISTRY_VERSION = 'design-lab/rights-registry/v1'

#: The four positions a subject's licence state is recorded in. Read from the combiner so this
#: gate classifies the fields the product actually reads, not a list this file maintains.
BLOCKING = 'BLOCKER'
BANDS = ('BLOCKER', 'WARNING', 'CLEAN', 'ABSENT', 'UNCLASSIFIED')

REFUSALS = (
    'REGISTRY_UNREADABLE',
    'REGISTRY_UNBOUND',
    'REGISTRY_EMPTY',
    'ENTRY_MALFORMED',
    'SUBJECT_DUPLICATE',
    'COMBINER_UNREADABLE',
    'STATE_UNCLASSIFIED',
    'COUNT_DISAGREES',
    'CITATION_UNRESOLVED',
    'FIELD_LIST_EMPTY',
)


class RegistryError(RuntimeError):
    def __init__(self, message: str, code: str):
        super().__init__(message)
        if code not in REFUSALS:
            raise AssertionError(f'undocumented rights-registry refusal code {code!r}')
        self.code = code


def load_registry(root: Path) -> dict:
    path = root / REGISTRY_REL
    try:
        doc = json.loads(path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RegistryError(f'{REGISTRY_REL} cannot be read as JSON: {exc}',
                            'REGISTRY_UNREADABLE')
    if not isinstance(doc, dict):
        raise RegistryError(f'{REGISTRY_REL} is {type(doc).__name__}, not an object',
                            'REGISTRY_UNREADABLE')
    if doc.get('schemaVersion') != REGISTRY_VERSION:
        raise RegistryError(
            f'{REGISTRY_REL} binds {doc.get("schemaVersion")!r}, not {REGISTRY_VERSION!r}',
            'REGISTRY_UNBOUND')
    return doc


def load_combiner():
    """The live band classification, imported from the module that makes the decision."""
    try:
        from design_lab.assurance import handoff_readiness
    except Exception as exc:  # a module that will not import cannot be the authority
        raise RegistryError(f'{MODULE_REL} cannot be imported: {exc}', 'COMBINER_UNREADABLE')
    for name in ('RIGHTS_FIELDS', 'rights_band'):
        if not hasattr(handoff_readiness, name):
            raise RegistryError(f'{MODULE_REL} declares no {name}', 'COMBINER_UNREADABLE')
    if not handoff_readiness.RIGHTS_FIELDS:
        raise RegistryError(f'{MODULE_REL} classifies no rights field at all', 'FIELD_LIST_EMPTY')
    return handoff_readiness


def check_entries(entries, fields, rights_band) -> tuple[list, dict]:
    findings: list = []
    seen: dict = {}
    tally = {band: 0 for band in BANDS}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise RegistryError(f'entries[{index}] is {type(entry).__name__}, not an object',
                                'ENTRY_MALFORMED')
        subject = entry.get('subject_id')
        if not isinstance(subject, str) or not subject.strip():
            raise RegistryError(f'entries[{index}] states no subject_id, so it cannot be '
                                'matched to a decision', 'ENTRY_MALFORMED')
        if subject in seen:
            findings.append(
                f'SUBJECT_DUPLICATE entries[{index}] repeats subject {subject!r} first seen at '
                f'entries[{seen[subject]}]: one subject counted twice is one position the gate '
                'can believe it has covered')
        else:
            seen[subject] = index
        for field in fields:
            state = state_of(entry, field)
            band = rights_band(state)
            tally[band] += 1
            if band == 'UNCLASSIFIED':
                findings.append(
                    f'STATE_UNCLASSIFIED {subject}:{field}={state!r} is in no rights band; the '
                    f'combiner blocks it, and the band table must say what it means')
    return findings, tally


def state_of(entry: dict, field: str):
    if field == 'territory.state':
        return (entry.get('territory') or {}).get('state')
    return entry.get(field)


def recompute_counts(entries, fields) -> dict:
    """The four summary numbers, derived from the entries under stated definitions."""
    awaiting = lambda e: any(state_of(e, f) == 'NOT_ADJUDICATED' for f in fields)  # noqa: E731
    return {
        'subjects': len(entries),
        'adjudicated': sum(1 for e in entries if not awaiting(e)),
        'awaiting_adjudication': sum(1 for e in entries if awaiting(e)),
        'blocked_pending_owner': sum(1 for e in entries
                                     if e.get('refresh_policy') == 'BLOCKED_PENDING_OWNER'),
    }


def check_counts(doc, entries, fields) -> list:
    findings: list = []
    recorded = doc.get('counts')
    if not isinstance(recorded, dict):
        raise RegistryError('the registry carries no counts object, so nothing summarises it',
                            'COUNT_DISAGREES')
    derived = recompute_counts(entries, fields)
    for name, value in derived.items():
        if recorded.get(name) != value:
            findings.append(
                f'COUNT_DISAGREES counts.{name} says {recorded.get(name)!r} but the entries '
                f'derive {value} under this gate\'s definition '
                '(subjects=entries, adjudicated=no NOT_ADJUDICATED position, '
                'awaiting_adjudication=at least one, blocked_pending_owner=refresh_policy)')
    return findings


def check_citations(doc, entries, root: Path) -> list:
    findings: list = []
    declared = list(doc.get('generated_from') or [])
    findings += _unresolved(declared, root, 'generated_from')
    per_entry = sorted({str(e.get('evidence_source')) for e in entries
                        if isinstance(e.get('evidence_source'), str) and e['evidence_source']})
    findings += _unresolved(per_entry, root, 'evidence_source')
    if not declared and not per_entry:
        findings.append('CITATION_UNRESOLVED the registry names no source at all, so its 74 '
                        'licence positions rest on nothing traceable')
    return findings


def _unresolved(paths, root: Path, label: str) -> list:
    out = []
    anchor = root.resolve()
    for raw in paths:
        text = str(raw)
        # Resolve first: `Path(root, '../x')` keeps the `..` in it, so a bare relative_to()
        # would call an escape "inside the repository" and then report it as merely missing.
        candidate = (root / text).resolve()
        try:
            candidate.relative_to(anchor)
        except ValueError:
            out.append(f'CITATION_UNRESOLVED {label} {text!r} points outside the repository')
            continue
        if not candidate.exists():
            out.append(f'CITATION_UNRESOLVED {label} {text!r} does not exist under the '
                       f'repository root, so the position it evidences is uncited')
    return out


def scan(root: Path = REPO) -> tuple[list, dict]:
    findings: list = []
    doc = load_registry(root)
    entries = doc.get('entries')
    if not isinstance(entries, list):
        raise RegistryError(f'entries is {type(entries).__name__}, not a list', 'ENTRY_MALFORMED')
    if not entries:
        raise RegistryError('the registry records zero licence subjects, so the RIGHTS gate has '
                            'no requirements list to satisfy', 'REGISTRY_EMPTY')
    combiner = load_combiner()
    fields = tuple(combiner.RIGHTS_FIELDS)
    entry_findings, tally = check_entries(entries, fields, combiner.rights_band)
    findings += entry_findings
    findings += check_counts(doc, entries, fields)
    findings += check_citations(doc, entries, root)
    distinct = sorted({str(state_of(e, f)) for e in entries for f in fields})
    summary = {
        'registry': REGISTRY_REL,
        'combiner': MODULE_REL,
        'entries': len(entries),
        'fields': list(fields),
        'distinct_states': distinct,
        'band_tally': tally,
        'counts_recorded': doc.get('counts'),
        'counts_derived': recompute_counts(entries, fields),
        'citations': sorted({str(e.get('evidence_source')) for e in entries}),
        'generated_at': doc.get('generated_at'),
        'decision_owner': doc.get('decision_owner'),
    }
    return findings, summary


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    wide = '--verbose' in argv
    try:
        findings, summary = scan()
    except RegistryError as exc:
        print(f'RIGHTS_REGISTRY=FAIL {exc.code}: {exc}')
        return 1
    for line in findings:
        print(f'RIGHTS_REGISTRY=FAIL {line}')
    tally = summary['band_tally']
    print(f"RIGHTS_REGISTRY={'FAIL' if findings else 'OK'} "
          f"entries={summary['entries']} fields={len(summary['fields'])} "
          f"states={len(summary['distinct_states'])} "
          f"blocker={tally['BLOCKER']} restricting={tally['WARNING']} clean={tally['CLEAN']} "
          f"absent={tally['ABSENT']} unclassified={tally['UNCLASSIFIED']} "
          f"generated_at={summary['generated_at']} owner={summary['decision_owner']}")
    if wide:
        print(json.dumps(summary, indent=2, ensure_ascii=False, sort_keys=True))
    return 1 if findings else 0


if __name__ == '__main__':
    raise SystemExit(main())
