# SPDX-License-Identifier: MIT
"""The evidence link has to be readable by a person, not only by an axis rule.

`project_ledger` already answers "does this receipt still hold", and since 2026-10-08 it answers two
separate questions -- integrity (are the bytes this receipt hashed still where the receipt says they
came from) and currency (does this receipt still describe the bytes we are running). Until now the
only consumer of those fields was the axis rule inside reporting.py itself: no route, no page, no gate
read them. An answer nobody can look at is not an answer, and a chain whose last link is only visible
to the code that wrote it is exactly where false greens hide.

This module recomputes the projection over the CURRENT checkout -- the ledger file plus the object
database -- and refuses to say anything it cannot support. It never reads `reports/current/`, because
a generated projection is bound to whatever commit it was written at, and serving that as the state of
the code you are running would be the same substitution of stale evidence for observation that the
ledger has been fighting all week. If the ledger is absent, if git cannot name a subject commit, or if
the record set has outgrown the contract's bound, the call raises with a named code instead of
answering an empty list that a reader would call "no evidence problems".
"""
from __future__ import annotations

from collections import Counter
from hashlib import sha256
import json
from pathlib import Path

from design_lab.governance import reporting
from design_lab.interop import InteropError, schema_errors
from design_lab.runtime.state_resources import repo_resource

EVIDENCE_PROJECTION_SCHEMA_VERSION = 'design-lab/evidence-projection/v1'
# REPO_ROOT stays: this projection describes the checkout the service runs from, and in a wheel
# there is no such checkout -- that is a fact about the install, not a path to paper over.
REPO_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_REPOSITORY_PATH = 'design-lab/schemas/evidence-projection.schema.json'
SCHEMA_PATH = repo_resource('schemas/evidence-projection.schema.json')

#: The contract bounds the record list; refusing beats truncating, because a cut list would still
#: carry a `totals` block that reads as complete.
MAX_RECEIPTS = 400


class EvidenceReadbackError(RuntimeError):
    """A named refusal. The route maps these to an HTTP status without inventing a payload."""

    def __init__(self, code: str, details=None):
        super().__init__(code)
        self.code = code
        self.details = list(details or [])


_SCHEMA_CACHE: dict = {}


def _schema() -> dict:
    key = str(SCHEMA_PATH)
    if key not in _SCHEMA_CACHE:
        if not SCHEMA_PATH.is_file():
            raise EvidenceReadbackError(
                'EVIDENCE_CONTRACT_ABSENT', [f'{SCHEMA_REPOSITORY_PATH} is not on disk'])
        _SCHEMA_CACHE[key] = json.loads(SCHEMA_PATH.read_text(encoding='utf-8'))
    return _SCHEMA_CACHE[key]


def _check(payload: dict) -> dict:
    """Refuse to serve a readback that does not satisfy its own contract.

    Every field here is written by this module, so a mismatch means code and contract have diverged --
    a renamed key, a new reason token registered in code but not in the schema, a field that leaked in
    from the underlying record. The failure is a named error carrying the field paths.
    """
    try:
        problems = schema_errors(_schema(), payload)
    except InteropError as exc:
        raise EvidenceReadbackError('EVIDENCE_CONTRACT_UNLOADABLE', [str(exc)]) from exc
    if problems:
        raise EvidenceReadbackError('EVIDENCE_CONTRACT_VIOLATION', problems)
    return payload


def _token(reason: str) -> str:
    """The reason vocabulary, without the path the reason names.

    Counts are keyed by bare token because the contract closes that vocabulary: a token the schema has
    never heard of is a refusal, so a new reason cannot silently join the readback without somebody
    registering what it means.
    """
    return reason.split(':', 1)[0]


def _receipt(entry: dict) -> dict:
    return {
        'id': entry['id'],
        'taskIds': list(entry.get('task_ids') or []),
        'kind': entry['kind'],
        'outcome': entry['outcome'],
        'subjectSha': entry['subject_sha'],
        'binding': entry.get('binding') or reporting.WORKTREE_BINDING,
        'observedAt': entry['observed_at'],
        'verified': bool(entry['verified']),
        'current': bool(entry['current']),
        'integrityReasons': list(entry['integrity_reasons']),
        'currencyReasons': list(entry['currency_reasons']),
    }


def projection(root=None, subject_sha=None) -> dict:
    """Recompute the ledger's evidence state for `subject_sha` and return the contract payload."""
    root = Path(root) if root is not None else REPO_ROOT
    ledger_path = root / reporting.LEDGER
    if not ledger_path.is_file():
        raise EvidenceReadbackError(
            'EVIDENCE_LEDGER_ABSENT', [f'{reporting.LEDGER} is not in this checkout'])
    if subject_sha is None:
        try:
            subject_sha = reporting._git(root, 'rev-parse', 'HEAD')
        except ValueError as exc:
            raise EvidenceReadbackError('EVIDENCE_SUBJECT_UNRESOLVABLE', [str(exc)]) from exc
    try:
        ledger = json.loads(ledger_path.read_text(encoding='utf-8'))
        projected = reporting.project_ledger(root, ledger, subject_sha)
    except (ValueError, OSError, KeyError) as exc:
        # A ledger that will not project is not an empty ledger: say which, refuse to guess.
        raise EvidenceReadbackError('EVIDENCE_LEDGER_REJECTED', [str(exc)]) from exc
    receipts = [_receipt(entry) for entry in projected['evidence']]
    if len(receipts) > MAX_RECEIPTS:
        raise EvidenceReadbackError(
            'EVIDENCE_PROJECTION_OVERFLOW',
            [f'{len(receipts)} receipts exceed the contract bound of {MAX_RECEIPTS}; '
             'raise it deliberately or split the readback, never truncate it here'])
    integrity = Counter(_token(reason) for entry in receipts
                        for reason in entry['integrityReasons'])
    currency = Counter(_token(reason) for entry in receipts
                       for reason in entry['currencyReasons'])
    payload = {
        'schemaVersion': EVIDENCE_PROJECTION_SCHEMA_VERSION,
        'subjectSha': subject_sha,
        'ledger': reporting.LEDGER,
        'totals': {
            'records': len(receipts),
            'outcomePass': sum(1 for entry in receipts if entry['outcome'] == 'PASS'),
            'verified': sum(1 for entry in receipts if entry['verified']),
            'unverified': sum(1 for entry in receipts if not entry['verified']),
            'current': sum(1 for entry in receipts if entry['current']),
        },
        'reasonCounts': {'integrity': dict(integrity), 'currency': dict(currency)},
        'receipts': receipts,
        'taskCounts': dict(projected['counts']),
    }
    return _check(payload)


def digest(payload: dict) -> str:
    """A stable fingerprint of one readback, so a caller can tell two answers apart by content."""
    return 'sha256:' + sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True).encode('utf-8')).hexdigest()
