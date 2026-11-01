#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Keep status vocabularies from being hand-copied into disagreement.

LANGUAGE-POLICY §5: enums and status words are not copied by hand between Python,
TypeScript and host JS; the contract file is the authority and each language
either validates against it or generates from it. A hand copy already drifted
once -- the Workbench advertised the preflight verdict as "PASS / BLOCKED" while
runtime/task_resources.py only ever emits READY or BLOCKED -- so this checks the
contract against BOTH sides rather than trusting either.

FAILS when:
  * a Python source no longer matches the recorded vocabulary (two-way);
  * the Workbench's triage sets match neither the contract nor each other;
  * a verdict/status literal appears in the UI that the service cannot emit
    (the 'PASS' class of false claim), including inside the built bundle;
  * the rights block's clearance or decision words are not exactly what
    src/design_lab/rights_review.py emits and what the bound rights-decision
    contract allows -- or when a block names a source file that is not there.
    The rights words are deliberately NOT admitted into the UI status-word check
    below: that check guards the attempt / task-preflight / artifact-preflight
    planes, and 'APPROVED' becoming legal there is the loosening this file was
    written to refuse. Wiring the rights panel's own UI emitter is a later step
    and has to be wired by name.

Read-only. Pure stdlib.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
CONTRACT = REPO / 'design-lab' / 'config' / 'state-vocabularies.json'
JOB_STORE = REPO / 'src' / 'design_lab' / 'runtime' / 'job_store.py'
TASK_RESOURCES = REPO / 'src' / 'design_lab' / 'runtime' / 'task_resources.py'
PRODUCTION_PREFLIGHT = (REPO / 'src' / 'design_lab' / 'assurance' /
                        'production_preflight.py')
# 2026-10-08 rights-gate reachability. The clearance words are produced by the facade, the
# decision words by the bound contract, which `assurance/rights_ledger.py` LOADS rather than
# copies -- so this check compares the contract file against what the contract file says,
# and a Python copy that drifted from either side is a finding.
RIGHTS_REVIEW = REPO / 'src' / 'design_lab' / 'rights_review.py'
RIGHTS_LEDGER = REPO / 'src' / 'design_lab' / 'assurance' / 'rights_ledger.py'
RIGHTS_CONTRACT = (REPO / 'design-lab' / 'schemas' / 'contracts' /
                   'rights-decision.schema.json')
SHELL_TS = REPO / 'apps' / 'workbench' / 'shell.ts'
BUNDLE = REPO / 'apps' / 'workbench' / 'build' / 'main.js'


def quoted(text: str) -> set[str]:
    """Upper-snake identifiers inside either quote style (TS uses single quotes)."""
    return set(re.findall(r"""['"]([A-Z][A-Z0-9_]{2,})['"]""", text))


def py_plan_feedback_outcomes(emitter_path: Path) -> set[str]:
    """Read plan_feedback's OUTCOMES tuple literally, so the contract cannot be judged by a copy.

    A missing tuple returns the empty set: the caller then reports the disagreement as a finding
    instead of raising, so one malformed source names itself rather than crashing the whole gate.
    """
    text = emitter_path.read_text(encoding='utf-8')
    match = re.search(r'(?m)^OUTCOMES = \((.*?)\)', text, re.S)
    if not match:
        return set()
    return set(re.findall(r"'([A-Z][A-Z0-9_]{2,})'", match.group(1)))


def py_attempt_states() -> tuple[set[str], set[str]]:
    text = JOB_STORE.read_text(encoding='utf-8')
    terminal = quoted(re.search(r'^TERMINAL = \{(.*?)\}', text, re.S | re.M).group(1))
    allowed = re.search(r'^ALLOWED = \{(.*?)^\}', text, re.S | re.M).group(1)
    keys = set(re.findall(r'^\s*"([A-Z_]+)":', allowed, re.M))
    return keys | terminal, terminal


def py_preflight() -> tuple[set[str], set[str], set[str], set[str]]:
    text = TASK_RESOURCES.read_text(encoding='utf-8')
    verdict = set(re.findall(r'verdict = "([A-Z_]+)" if', text))
    verdict |= {v for v in quoted(text) if v in {'READY', 'BLOCKED', 'PASS'}}
    states = set(re.findall(r'"state": "([A-Z_]+)"', text))
    # `state = "RESOLVED" if executable else "UNAVAILABLE"` -- both branches count.
    for a, b in re.findall(r'state = "([A-Z_]+)" if .*? else "([A-Z_]+)"', text):
        states |= {a, b}
    block_match = re.search(
        r'blocked = \[r for r in results if r\.get\("state"\) in \((.*?)\)\]', text, re.S)
    blocking = set(re.findall(r'"([A-Z_]+)"', block_match.group(1))) if block_match else set()
    registry = set(re.findall(r'registry_state = "([A-Z_]+)"', text))
    return verdict, states, registry, blocking


def py_artifact_preflight() -> tuple[set[str], set[str]]:
    """VERDICTS, plus the outcome constants the module declares."""
    text = PRODUCTION_PREFLIGHT.read_text(encoding='utf-8')
    body = re.search(r'^VERDICTS = \((.*?)\)$', text, re.M).group(1)
    verdicts = set(re.findall(r"'([A-Z]{3,12})'", body))
    outcomes = {value for _name, value in
                re.findall(r"^([A-Z_]{3,15}) = '([A-Z_]{3,15})'$", text, re.M)}
    return verdicts, outcomes


def py_rights() -> tuple[set[str], set[str], list[str]]:
    """(clearance words the facade can emit, decision words the bound contract allows, notes).

    The clearance set is read out of `CLEARANCE_STATES = (A, B)` with each name resolved
    through the module's own `NAME = 'WORD'` assignments, so a docstring that quotes a word
    is prose and not an emission -- the same rule `verify_contract_bindings.py` applies to
    emitted versions. The decision set is read from the contract FILE, which is the point:
    `rights_ledger.py` loads that enum instead of copying it, so a word the contract does not
    allow cannot be declared here and a word the contract dropped cannot stay on show.
    """
    notes: list[str] = []
    clearance: set[str] = set()
    if RIGHTS_REVIEW.is_file():
        text = RIGHTS_REVIEW.read_text(encoding='utf-8')
        assigned = dict(re.findall(r"^([A-Z][A-Z0-9_]*) = '([A-Z][A-Z0-9_]*)'$", text, re.M))
        anchor = re.search(r'^CLEARANCE_STATES = \((.*?)\)$', text, re.M)
        if anchor is None:
            notes.append('rights_review.py declares no CLEARANCE_STATES tuple, so the '
                         'clearance vocabulary cannot be read from its emitter')
        else:
            names = re.findall(r'[A-Z][A-Z0-9_]*', anchor.group(1))
            unresolved = [name for name in names if name not in assigned]
            if unresolved:
                notes.append(f'CLEARANCE_STATES names {unresolved}, which rights_review.py '
                             'does not assign to a word, so the vocabulary is not resolvable')
            clearance = {assigned[name] for name in names if name in assigned}
    else:
        notes.append(f'{RIGHTS_REVIEW.relative_to(REPO)} does not exist')
    decisions: set[str] = set()
    if RIGHTS_LEDGER.is_file():
        if 'decision_vocabulary' not in RIGHTS_LEDGER.read_text(encoding='utf-8',
                                                                 errors='replace'):
            notes.append('rights_ledger.py no longer defines decision_vocabulary(), so nothing '
                         'loads the contract enum the rights block declares')
    else:
        notes.append(f'{RIGHTS_LEDGER.relative_to(REPO)} does not exist')
    if RIGHTS_CONTRACT.is_file():
        try:
            doc = json.loads(RIGHTS_CONTRACT.read_text(encoding='utf-8'))
        except ValueError as exc:
            notes.append(f'rights-decision.schema.json is not readable JSON: {exc}')
            doc = {}
        enum = ((doc.get('properties') or {}).get('decision') or {}).get('enum')
        if not isinstance(enum, list) or not enum:
            notes.append('rights-decision.schema.json declares no decision enum; a rights gate '
                         'with no closed vocabulary accepts any word')
        else:
            decisions = set(enum)
    else:
        notes.append(f'{RIGHTS_CONTRACT.relative_to(REPO)} does not exist')
    return clearance, decisions, notes


def declared_source_files(contract: dict) -> list[tuple[str, str]]:
    """Every (label, path) this contract names as an emitter.

    A `sources` entry pointing at a file that is not there is the decoration this file exists
    to refuse: a reader would believe the vocabulary has an emitter behind it.
    """
    named: list[tuple[str, str]] = []

    def collect(block: dict, label: str) -> None:
        for key, value in (block.get('sources') or {}).items():
            path = str(value).split(' ')[0].split('(')[0].strip()
            if path.startswith(('src/', 'apps/', 'design-lab/')):
                named.append((f'{label}.{key}', path))

    collect(contract, 'top')
    for name, block in contract.items():
        if isinstance(block, dict) and isinstance(block.get('sources'), dict):
            collect(block, name)
    return named


def ts_set(name: str) -> set[str]:
    if not SHELL_TS.is_file():
        return set()
    text = SHELL_TS.read_text(encoding='utf-8')
    match = re.search(rf'const {name} = new Set\(\[(.*?)\]\)', text, re.S)
    return quoted(match.group(1)) if match else set()


def main() -> int:
    errors: list[str] = []
    try:
        contract = json.loads(CONTRACT.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError) as exc:
        print(f'STATE_VOCABULARIES=FAIL contract unreadable: {exc}')
        return 1
    if contract.get('schemaVersion') != 'design-lab/state-vocabularies/v1':
        print('STATE_VOCABULARIES=FAIL wrong schemaVersion')
        return 1

    attempts = contract['attemptStates']
    declared_all = set(attempts['all'])
    declared_terminal = set(attempts['terminal'])

    py_all, py_terminal = py_attempt_states()
    if py_all != declared_all:
        errors.append(f'job_store ALLOWED/TERMINAL = {sorted(py_all)} but contract says '
                      f'{sorted(declared_all)}')
    if py_terminal != declared_terminal:
        errors.append(f'job_store TERMINAL = {sorted(py_terminal)} but contract says '
                      f'{sorted(declared_terminal)}')

    for name, key in (('FAILED_STATES', 'failed'), ('HUMAN_STATES', 'needsHuman'),
                      ('IN_FLIGHT_STATES', 'inFlight')):
        in_ui = ts_set(name)
        if not in_ui:
            errors.append(f'{name} not found in apps/workbench/shell.ts; the UI vocabulary '
                          f'cannot be verified')
            continue
        expected = set(attempts[key])
        if in_ui != expected:
            errors.append(f'{name} = {sorted(in_ui)} but contract says {sorted(expected)}')

    ui_sets = set().union(*(ts_set(n) for n in
                            ('FAILED_STATES', 'HUMAN_STATES', 'IN_FLIGHT_STATES')))
    if ui_sets and ui_sets > declared_all:
        errors.append(f'UI triage uses states the service cannot emit: '
                      f'{sorted(ui_sets - declared_all)}')

    # DL-KB-16: the three outcome words are checked against the emitter rather than trusted from
    # either side -- a hand copy into the screen is exactly the drift this file exists to catch.
    feedback = contract.get('planFeedback')
    if feedback is None:
        errors.append('the contract declares no planFeedback block; the feedback outcome words '
                      'would be hand-copied into the screen with nothing to compare them to')
    else:
        declared_feedback = set(feedback['outcomes'])
        emitter_path = REPO / feedback['emitter']
        if not emitter_path.is_file():
            errors.append(f"planFeedback names {feedback['emitter']} which is not a file")
        else:
            emitted_feedback = py_plan_feedback_outcomes(emitter_path)
            if emitted_feedback != declared_feedback:
                errors.append(f'plan_feedback OUTCOMES = {sorted(emitted_feedback)} but the '
                              f'contract says {sorted(declared_feedback)}')
            emitted_verdicts = re.findall(
                r"(?m)^DIMENSION_VERDICTS = \((.*?)\)",
                emitter_path.read_text(encoding='utf-8'), re.S)
            verdict_words = set(re.findall(r"'([A-Z][A-Z0-9_]{2,})'", emitted_verdicts[0])) \
                if emitted_verdicts else set()
            if verdict_words != set(feedback['dimensionVerdicts']):
                errors.append(f'plan_feedback DIMENSION_VERDICTS = {sorted(verdict_words)} but '
                              f'the contract says {sorted(feedback["dimensionVerdicts"])}')
            unused = feedback.get('unusedLiteral')
            if unused and f"'{unused}'" not in emitter_path.read_text(encoding='utf-8'):
                errors.append(f'planFeedback declares the unused literal {unused!r} but '
                              f'{feedback["emitter"]} does not write it')

    verdict, states, registry, blocking = py_preflight()
    declared_verdicts = set(contract['taskResourcePreflight']['verdicts'])
    for label, actual, key in (('verdict', verdict, 'verdicts'),
                               ('resource state', states, 'resourceStates'),
                               ('blocking resource state', blocking, 'blockingResourceStates'),
                               ('registry_state', registry, 'registryStates')):
        expected = set(contract['taskResourcePreflight'][key])
        if actual != expected:
            errors.append(f'task_resources {label} = {sorted(actual)} but contract says '
                          f'{sorted(expected)}')

    artifact_verdicts, artifact_outcomes = py_artifact_preflight()
    declared_artifact_verdicts = set(contract['artifactPreflight']['verdicts'])
    declared_artifact_outcomes = set(contract['artifactPreflight']['outcomes'])
    if artifact_verdicts != declared_artifact_verdicts:
        errors.append(f'production_preflight VERDICTS = {sorted(artifact_verdicts)} '
                      f'but the contract says {sorted(declared_artifact_verdicts)}')
    missing = declared_artifact_outcomes - artifact_outcomes
    if missing:
        errors.append(f'the contract declares outcome words the emitter does not '
                      f'define: {sorted(missing)}')

    # The rights vocabulary, 2026-10-08. Declared words are compared with the emitter that
    # produces them, and an empty comparison is a finding rather than a silence.
    rights_block = contract.get('rights')
    if not isinstance(rights_block, dict):
        errors.append('the contract declares no rights vocabulary, so the words the rights '
                      'gate shows are a hand copy nobody checks')
    else:
        emitted_clearance, emitted_decisions, rights_notes = py_rights()
        errors.extend(f'rights: {note}' for note in rights_notes)
        for label, declared, emitted in (
                ('clearance', set(rights_block.get('clearance') or []), emitted_clearance),
                ('decision', set(rights_block.get('decisions') or []), emitted_decisions)):
            if not declared:
                errors.append(f'rights: NOTHING_TO_COMPARE the contract declares no '
                              f'{label} words')
            elif not emitted:
                errors.append(f'rights: NOTHING_TO_COMPARE no emitter produces any {label} '
                              'word, so the declared vocabulary proved nothing')
            elif declared != emitted:
                errors.append(f'rights {label} = {sorted(declared)} but the emitter produces '
                              f'{sorted(emitted)} -- the UI would show a word nobody can '
                              'produce, or lose one that is real')
        if set(rights_block.get('clearance') or []) & {'PENDING', 'PENDING_REVIEW'}:
            errors.append('rights: the clearance vocabulary offers a PENDING word. An '
                          'untouched gate was never asked anything; only a human decision may '
                          'say PENDING_REVIEW')

    for label, path in declared_source_files(contract):
        if not (REPO / path).is_file():
            errors.append(f'sources/{label} names {path}, which does not exist -- a '
                          'vocabulary with an unread source is a hand copy in disguise')

    # The specific regression this file exists for: the UI taught a verdict word
    # the service cannot emit. Look for the verdict-shaped literal only, so an
    # unrelated use of the word elsewhere cannot produce a false alarm.
    for path, label in ((SHELL_TS, 'shell.ts'), (BUNDLE, 'build/main.js')):
        if not path.is_file():
            continue
        body = path.read_text(encoding='utf-8', errors='replace')
        # A status word is legitimate when SOME declared emitter produces it. This is
        # looser than the original file-wide ban on 'PASS', and the reason is recorded in
        # the contract rather than left implicit: assurance/production_preflight.py really
        # does verdict PASS / WARN / BLOCKED / INCOMPLETE. The original shape of the lie --
        # an artifact-style verdict pasted onto the task-resource preflight, which emits
        # only READY or BLOCKED -- is denied by name below, and a word no emitter produces
        # is still caught by both rules.
        vocabularies = [declared_verdicts, declared_artifact_verdicts,
                        declared_artifact_outcomes, declared_all]
        denied_pairs = {'BLOCKED / PASS': 'the task-resource preflight emits READY or '
                                          'BLOCKED only'}
        for hit in re.findall(r"['\"]([A-Z]{3,10}(?:\s*/\s*[A-Z]{3,10})+)['\"]", body):
            words = {word.strip() for word in hit.split('/')}
            shape = ' / '.join(sorted(words))
            if shape in denied_pairs:
                errors.append(f'{label} advertises the verdict pair {hit!r}: '
                              f'{denied_pairs[shape]}')
            elif not any(words <= vocabulary for vocabulary in vocabularies):
                errors.append(f'{label} advertises the status {hit!r}, which no declared '
                              'emitter produces')
        for hit in re.findall(r"['\"](PASS|FAIL|OKAY|APPROVED)['\"]", body):
            if not any(hit in vocabulary for vocabulary in vocabularies):
                errors.append(f'{label} advertises {hit!r} as a status; no declared emitter '
                              f'produces it (task preflight: {sorted(declared_verdicts)}, '
                              f'artifact preflight: {sorted(declared_artifact_verdicts)})')

    print(f'STATE_VOCABULARIES attempt_states={len(declared_all)} verdicts='
          f'{contract["taskResourcePreflight"]["verdicts"]} errors={len(errors)}')
    for err in errors[:12]:
        print('ERROR:', err)
    print('STATE_VOCABULARIES=' + ('FAIL' if errors else 'OK'))
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
