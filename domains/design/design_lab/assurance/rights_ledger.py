# SPDX-License-Identifier: MIT
"""Persist Human RIGHTS gate decisions against the state database.

The RIGHTS gate was the only human gate with a contract and no store.
``design-lab/schemas/contracts/rights-decision.schema.json`` closed its properties and
froze its decision enum; ``design-lab/config/rights-registry.json`` recorded 74 licence
subjects; ``assurance/handoff_readiness.py`` computed ``_rights_gates`` verdicts. Nothing
in ``src/`` read any of them, so no verb, no route and no release check could cite a
rights decision, and an untouched gate had no word left that could not be mistaken for
"somebody is about to close it".

This module owns *storage* only. Every structural rule stays with the contract that
already had it: the document is validated against ``rights-decision.schema.json`` **as
loaded from disk** -- the field list, the required trio and the decision enum are read out
of that file, never copied here, because a second copy is a second authority able to
disagree with the first. What is enforced here instead is what a JSON schema cannot see:

* the decision must belong to a project this state database actually has;
* history is append-only. A changed mind is a NEW row carrying ``supersedes``, one row
  cannot be superseded twice, and a decision may only supersede a decision about the same
  ``use_scope`` -- otherwise a later filing could hide an unfavourable scope behind an
  unrelated id. ``supersedes`` is a *column*, never a document field: the contract closes
  its properties and does not declare it, so a submission that tried to smuggle one in is
  refused as an unknown field rather than silently stored. The immutability itself is the
  database's (the triggers in ``design-lab-state-rights-v1.sql``), not a convention of this
  module;
* **absence is not a review.** This module deliberately offers no "open a review", "request
  a decision" or default-decision function. A scope nobody filed has no entry in
  :func:`current_decisions`, and nothing here can synthesise the ``PENDING_REVIEW`` that the
  contract allows as a *human* answer. An untouched gate reads ``NOT_REVIEWED`` at the
  façade; ``PENDING_REVIEW`` appears only because a person filed it. That is the same
  load-bearing rule ``creative/approval.py`` applies to the projected gates;
* no decision may be signed by automation.

The actor rule, stated honestly. The contract closes its properties and declares **no**
actor kind, so :func:`human_jury.assert_not_agent_signed` -- which reads a ``juror`` object
-- does not apply to a rights decision, and there is no in-document kind to check. What is
done instead is refusal by name: an actor whose declared ``actor_kind`` is not human is
refused, and an actor whose ``decided_by`` *names* automation is refused outright
(``review-agent``, ``MODEL``, ``SYSTEM``, ``codex``, ...). A name check proves the record
does not declare itself automation. It cannot prove a human typed it, and no function here
invents a human identity: the out-of-band E4 Human Gate attestation still owns that proof,
exactly as ``human_jury.py`` states of its own limit. A declared kind is stronger than a
name check and is stored in its own column, so a reader can tell the two apart instead of
being shown one confident word for both.

Every refusal is a :class:`RightsLedgerError` with a distinct ``code``: "that project does
not exist here", "that document is not a rights decision" and "an agent tried to sign a
human gate" are three different facts, and an operator told "invalid" can act on none of
them.

Boundary: no host access, no provider call, no legal opinion, no registry read. It stores
what a human decided and refuses everything else.
"""
from __future__ import annotations

from typing import Mapping
from functools import lru_cache
import json
import re
import sqlite3
import uuid

from . import AssuranceError, human_jury, require_rfc3339, require_text
from ..runtime.state_resources import repo_resource, state_schema

_RIGHTS = state_schema('design-lab-state-rights-v1.sql')

#: The version the bound contract binds. Written as a value this module compares, not as a
#: restatement of the contract's contents: `contract()` refuses a schema file that binds
#: anything else, so a one-sided bump fails closed here instead of validating a document
#: against a contract nobody meant.
CONTRACT_VERSION = 'design-lab/rights-decision/v1'
# D09 (batch 22): packaged-first, for the same reason as the research contract --
# PROJECT_ROOT resolves to `Lib/` in an installed wheel, which made every rights
# route answer 500 instead of a verdict.
CONTRACT_PATH = repo_resource('schemas/contracts/rights-decision.schema.json')

#: Names that identify automation when they appear in a `decided_by` value. Kept separate
#: from `human_jury.AGENT_ACTOR_KINDS` (a *kind* vocabulary the rights contract cannot
#: carry) and seeded from it rather than copied, so the two gates cannot drift apart on
#: what "an agent" is. The additions are the concrete agent ids this repository's own
#: tooling runs as: `runtime/migration_preview.py` looks for `.codex` and `.claude`, the
#: jury fixtures sign as `codex`, and the route payload harness proposes as `qoder-agent`.
_MULTI_CHAR_AGENT_NAMES = (
    'agent', 'assistant', 'automated', 'bot', 'chatbot', 'claude', 'codex', 'copilot',
    'cursor', 'deepseek', 'gemini', 'gpt', 'llm', 'machine', 'model', 'openai',
    'pipeline', 'qoder', 'script', 'service', 'system', 'tool', 'worker',
)
#: Matched only as a whole token: 'ai' is a substring of ordinary human names.
_TOKEN_ONLY_AGENT_NAMES = ('ai',)

#: A document carrying one of these is not a rights decision at all: it is a jury proposal
#: or a verdict wearing another label. The closed schema refuses them too, but as a field
#: message; they are named first so the reason reaches the caller.
_FOREIGN_ACTOR_FIELDS = ('actor_kind', 'attestation', 'is_verdict', 'juror', 'juror_id',
                         'proposal_id', 'proposer', 'suggested_verdict', 'supersedes')

#: What no stored rights decision proves. Published with every read-back, because the
#: person most likely to over-read a CLEARED is the person who filed it.
DOES_NOT_PROVE = (
    'a recorded decision is a named actor stating a licence position; it is not proof that a '
    'human with authority read the licence text. Over the HTTP boundary the actor kind '
    'cannot arrive at all (the contract closes its properties), so those rows are '
    'name-checked only and the read-back says which ones in `name_checked_only`',
    'CLEARED covers the use scopes this project has actually filed a decision for. It is not '
    'a statement that every subject needing one has been listed: this ledger records '
    'decisions, it holds no requirements list, and design-lab/config/rights-registry.json is '
    'not read by it',
    'no licence file, no territory text and no third-party terms were re-read by recording a '
    'decision: the stored words are the ones a human supplied',
    'a rights decision clears none of the quality, production or release gates; each is a '
    'separate human gate with its own record',
)

#: The closed vocabulary of refusal codes this store may raise. Declared here so a route, a
#: verb and a table can show an operator every way the gate says no, and so a new refusal
#: cannot quietly invent a code nobody reads: an unlisted code is a bug in this module, not
#: something the caller has to guess at.
REFUSAL_CODES = frozenset({
    'RIGHTS_PROJECT_NOT_RECORDED',
    'RIGHTS_DOCUMENT_MALFORMED',
    'RIGHTS_CONTRACT_UNREADABLE',
    'RIGHTS_CONTRACT_UNBOUND',
    'RIGHTS_DECISION_INVALID',
    'RIGHTS_ACTOR_MISSING',
    'RIGHTS_NOT_HUMAN',
    'RIGHTS_TIMESTAMP_INVALID',
    'RIGHTS_SUPERSEDES_UNKNOWN',
    'RIGHTS_ALREADY_SUPERSEDED',
    'RIGHTS_SUPERSEDES_SCOPE_MISMATCH',
    'RIGHTS_DECISION_ID_TAKEN',
    'RIGHTS_DATABASE_REFUSED',
    'RIGHTS_STORED_RECORD_INVALID',
})


class RightsLedgerError(RuntimeError):
    """A rights decision was refused; ``code`` names which rule refused it."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        if code not in REFUSAL_CODES:
            # Never let a refusal go out under a label nothing documents.
            raise AssertionError(f'undocumented rights refusal code {code!r}')
        self.code = code


def new_decision_id() -> str:
    """A fresh decision id, so a caller that states none cannot collide with a stored one.

    The identity is not a formality: an explicit id is what makes a retry recognisable as a
    replay instead of a second signature, which is why the CLI offers `--decision-id` and
    this is only the fallback for an operator who does not care what the id is.
    """
    return 'rd-' + uuid.uuid4().hex


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the state database with the rights tables present.

    The asset store is asked to open its own database rather than this module re-applying
    schema files: ``asset_store.connect`` carries the path policy, the foreign-key pragma
    and the assets-v2 migration with its pre-migration backup. Doing it twice here would be
    a second implementation of the same migration, and the two would drift.
    (``jury_store.connect`` and ``quality_store.connect`` are the precedent.)
    """
    from ..runtime.asset_store import connect as connect_assets
    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    connection.executescript(_RIGHTS.read_text(encoding='utf-8'))
    connection.commit()
    return connection


@lru_cache(maxsize=1)
def contract() -> dict:
    """The rights-decision contract, read from disk, never copied into this module."""
    try:
        document = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise RightsLedgerError(
            f'the rights gate cannot validate a decision because its own contract is '
            f'unreadable at {CONTRACT_PATH.name}: {exc}', code='RIGHTS_CONTRACT_UNREADABLE')
    if not isinstance(document, dict):
        raise RightsLedgerError(
            f'{CONTRACT_PATH.name} is not a schema object; failing closed rather than '
            'accepting every document', code='RIGHTS_CONTRACT_UNREADABLE')
    properties = document.get('properties') or {}
    bound = (properties.get('schemaVersion') or {}).get('const')
    if bound != CONTRACT_VERSION:
        raise RightsLedgerError(
            f'{CONTRACT_PATH.name} binds {bound!r}, not the {CONTRACT_VERSION!r} this store '
            'is written against; one side moved and the two would silently disagree',
            code='RIGHTS_CONTRACT_UNBOUND')
    if not (properties.get('decision') or {}).get('enum'):
        raise RightsLedgerError(
            f'{CONTRACT_PATH.name} declares no decision enum, so the gate has no vocabulary '
            'to enforce', code='RIGHTS_CONTRACT_UNBOUND')
    return document


def decision_vocabulary() -> tuple:
    """The decision enum as the contract states it. The only place this module learns it."""
    return tuple(contract()['properties']['decision']['enum'])


def field_names() -> tuple:
    """The contract's closed property set -- what a submission may and may not carry."""
    return tuple(contract()['properties'])


def required_field_names() -> tuple:
    return tuple(contract().get('required') or ())


def optional_field_names() -> tuple:
    required = set(required_field_names())
    return tuple(name for name in field_names() if name not in required)


def _agent_name_hit(name: str) -> list:
    """Which automation words this actor id declares. Empty means "names no automation"."""
    lowered = name.strip().lower()
    tokens = [token for token in re.split(r'[^a-z0-9]+', lowered) if token]
    hits = [token for token in _TOKEN_ONLY_AGENT_NAMES if token in tokens]
    hits += [token for token in _MULTI_CHAR_AGENT_NAMES if token in lowered]
    # `human_jury`'s kind vocabulary is tested as names too: an actor signing itself `MODEL`
    # or `SYSTEM` is declaring what it is, whatever the contract cannot carry.
    hits += [kind.lower() for kind in human_jury.AGENT_ACTOR_KINDS
             if kind.lower() in tokens and kind.lower() not in hits]
    return sorted(set(hits))


def _assert_human_signer(document, *, actor_kind=None) -> str:
    """Refuse, by name, a decision whose actor is automation. Returns the actor id.

    The order is deliberate: a document *shaped* like a jury record is named for what it
    is, an automation actor kind is refused by name, and only then is the ``decided_by``
    value itself tested. Every one of these fails closed -- an actor that cannot be
    established is not quietly treated as human.
    """
    if not isinstance(document, Mapping):
        raise RightsLedgerError(
            'a rights decision must be a JSON object; nothing was established about who '
            'signed it', code='RIGHTS_DOCUMENT_MALFORMED')
    foreign = sorted(name for name in _FOREIGN_ACTOR_FIELDS if name in document)
    if foreign:
        raise RightsLedgerError(
            f'the document carries the field(s) {", ".join(foreign)}, which belong to a jury '
            'record or to this store, not to a rights decision: the contract closes its '
            'properties and no agent-authored record becomes one by relabelling',
            code='RIGHTS_DECISION_INVALID')
    if actor_kind is not None:
        if actor_kind in human_jury.AGENT_ACTOR_KINDS:
            raise RightsLedgerError(
                f'an agent-signed rights decision is refused: the declared actor kind '
                f'{actor_kind!r} is automation, and no agent may sign a human gate',
                code='RIGHTS_NOT_HUMAN')
        if actor_kind not in human_jury.HUMAN_JUROR_KINDS:
            raise RightsLedgerError(
                f'the declared actor kind {actor_kind!r} is not one of '
                f'{", ".join(human_jury.HUMAN_JUROR_KINDS)}; failing closed rather than '
                'assuming a human', code='RIGHTS_NOT_HUMAN')
    actor = document.get('decided_by')
    if not isinstance(actor, str) or not actor.strip():
        raise RightsLedgerError(
            'the decision states no actor in `decided_by`, so no human is established; a '
            'rights gate is not signed by whoever wrote the request',
            code='RIGHTS_ACTOR_MISSING')
    found = _agent_name_hit(actor)
    if found:
        raise RightsLedgerError(
            f'an agent-signed rights decision is refused: `decided_by` {actor!r} names '
            f'automation ({", ".join(found)}), and a human gate is signed by a human; no '
            'function in this store converts a proposal or a run into a decision',
            code='RIGHTS_NOT_HUMAN')
    return actor.strip()


def _validate_against_contract(document: dict) -> None:
    """The contract's own job: enum, closed properties, required trio, declared formats."""
    from jsonschema import Draft202012Validator

    errors = sorted(Draft202012Validator(contract()).iter_errors(document),
                    key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        where = '/'.join(str(part) for part in first.path)
        raise RightsLedgerError(
            f'the decision was refused by its own contract {CONTRACT_PATH.name}'
            f'{("/" + where) if where else ""}: {first.message}',
            code='RIGHTS_DECISION_INVALID')


def _validate_value_shapes(document: dict) -> None:
    """The two rules ``format`` cannot enforce here, applied through the package's own
    primitives instead of restated as a second field list.

    The installed jsonschema has no ``date-time`` checker (see ``assurance/__init__.py``),
    so a ``decided_at`` of "last tuesday" satisfies the schema and would become a permanent
    row in an append-only table. ``minLength: 1`` likewise accepts a single space.
    """
    for name in ('decision_id', 'use_scope', 'decided_by'):
        try:
            require_text(document.get(name), name)
        except AssuranceError as exc:
            raise RightsLedgerError(str(exc), code='RIGHTS_ACTOR_MISSING'
                                    if name == 'decided_by' else 'RIGHTS_DECISION_INVALID')
    for name in ('territory', 'license_ref'):
        if document.get(name) is not None:
            try:
                require_text(document.get(name), name)
            except AssuranceError as exc:
                raise RightsLedgerError(str(exc), code='RIGHTS_DECISION_INVALID') from None
    try:
        require_rfc3339(document.get('decided_at'), 'decided_at')
    except AssuranceError as exc:
        raise RightsLedgerError(str(exc), code='RIGHTS_TIMESTAMP_INVALID') from None


def record(conn, *, project_id: str, document: dict, actor_kind: str | None = None,
           supersedes: str | None = None) -> dict:
    """Validate one rights decision, then append it. Returns the stored document.

    ``actor_kind`` and ``supersedes`` are out-of-document on purpose. The contract has no
    field for either: an HTTP submission cannot supply them, and a caller that does state a
    kind (the CLI, which asks the operator) is held to ``HUMAN`` or ``PANEL`` while a
    name-checked row stores a NULL kind and reports itself as one.
    """
    if not isinstance(document, Mapping):
        raise RightsLedgerError(
            'a rights decision must be a JSON object; nothing was written',
            code='RIGHTS_DOCUMENT_MALFORMED')
    normalized = json.loads(json.dumps(dict(document), allow_nan=False))
    if conn.execute('SELECT 1 FROM project WHERE project_id = ?', (project_id,)).fetchone() is None:
        raise RightsLedgerError(
            f'project {project_id!r} is not recorded in this state database: a rights '
            'decision cannot be filed against a project that does not exist here',
            code='RIGHTS_PROJECT_NOT_RECORDED')
    _assert_human_signer(normalized, actor_kind=actor_kind)
    _validate_against_contract(normalized)
    _validate_value_shapes(normalized)
    if normalized['decision'] not in decision_vocabulary():  # pragma: no cover - the enum is
        # loaded from the contract, so the schema check above already pinned this. It stays
        # because a refusal that depends only on a library version is not a guard.
        raise RightsLedgerError(
            f'decision {normalized["decision"]!r} is outside the contract vocabulary '
            f'{list(decision_vocabulary())}', code='RIGHTS_DECISION_INVALID')

    if supersedes is not None:
        if supersedes == normalized['decision_id']:
            raise RightsLedgerError('a rights decision may not supersede itself',
                                    code='RIGHTS_SUPERSEDES_UNKNOWN')
        previous = conn.execute(
            'SELECT use_scope FROM rights_decision WHERE decision_id = ? AND project_id = ?',
            (supersedes, project_id)).fetchone()
        if previous is None:
            raise RightsLedgerError(
                f'supersedes {supersedes!r} is not a decision of this project',
                code='RIGHTS_SUPERSEDES_UNKNOWN')
        if previous['use_scope'] != normalized['use_scope']:
            raise RightsLedgerError(
                f'{supersedes} decides {previous["use_scope"]!r}, not '
                f'{normalized["use_scope"]!r}: superseding a decision about one use scope '
                'with a decision about another would leave the first one unreferenced and '
                'uncountable', code='RIGHTS_SUPERSEDES_SCOPE_MISMATCH')
        if conn.execute('SELECT 1 FROM rights_decision WHERE supersedes = ?',
                        (supersedes,)).fetchone():
            raise RightsLedgerError(
                f'{supersedes} has already been superseded; a second replacement would fork '
                'the rights chain and leave the current decision undefined',
                code='RIGHTS_ALREADY_SUPERSEDED')

    try:
        conn.execute(
            'INSERT INTO rights_decision (decision_id, project_id, use_scope, decision,'
            ' decided_by, actor_kind, territory, license_ref, note, document_json,'
            ' decided_at, supersedes) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)',
            (normalized['decision_id'], project_id, normalized['use_scope'],
             normalized['decision'], normalized['decided_by'], actor_kind,
             normalized.get('territory'), normalized.get('license_ref'),
             normalized.get('note'),
             json.dumps(normalized, ensure_ascii=False, sort_keys=True),
             normalized['decided_at'], supersedes))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        # The triggers and CHECKs in the schema are the last line; reaching them means
        # something above this module is wrong, so it is reported, never retried.
        text = str(exc)
        code = ('RIGHTS_DECISION_ID_TAKEN'
                if 'rights_decision.decision_id' in text else 'RIGHTS_DATABASE_REFUSED')
        raise RightsLedgerError(f'the state database refused the decision: {text}',
                                code=code) from None
    return normalized


def list_decisions(conn, *, project_id: str) -> list:
    """Every decision of one project, oldest first, re-validated on read.

    A row that no longer satisfies the contract is a tamper signal, not something to serve
    quietly: the append-only triggers make that unreachable in normal operation, so reaching
    it means the schema or the policy moved underneath the data. It is reported as a
    refusal, because a partially trusted rights list is worse than none.
    """
    rows = conn.execute(
        'SELECT document_json FROM rights_decision WHERE project_id = ?'
        ' ORDER BY decided_at, decision_id', (project_id,)).fetchall()
    decisions = []
    for row in rows:
        document = json.loads(row['document_json'])
        try:
            _validate_against_contract(document)
        except RightsLedgerError as exc:
            raise RightsLedgerError(
                f'the stored decision {document.get("decision_id")!r} no longer satisfies the '
                f'rights-decision contract: {exc}',
                code='RIGHTS_STORED_RECORD_INVALID') from None
        decisions.append(document)
    return decisions


_CURRENT_WHERE = (
    ' NOT EXISTS (SELECT 1 FROM rights_decision child'
    '  WHERE child.supersedes = rights_decision.decision_id)')


def current_decisions(conn, *, project_id: str) -> dict:
    """``use_scope`` -> the decision nothing has replaced. Nothing is invented here.

    A scope with no row has no entry: the caller sees an absent key, which the façade reads
    as NOT_REVIEWED. It is never defaulted to ``PENDING_REVIEW``, which claims somebody was
    asked, and no code path in this module can produce that word for a scope nobody filed.
    The only subject axis the contract offers is ``use_scope`` -- it closes its properties
    and names no subject id -- so one live decision per scope is what "current" means here,
    and the newest filed decision wins when two rows point at one scope with no supersede
    link between them (a data bug, not a choice to make silently).
    """
    rows = conn.execute(
        'SELECT document_json FROM rights_decision WHERE project_id = ? AND' + _CURRENT_WHERE
        + ' ORDER BY decided_at, decision_id', (project_id,)).fetchall()
    current = {}
    for row in rows:
        item = json.loads(row['document_json'])
        current[item['use_scope']] = item
    return current


def filed_scopes(conn, *, project_id: str) -> list:
    """Every scope a decision was ever filed for, superseded rows included.

    The denominator a reader needs: `current_decisions` answers "what stands now", this
    answers "what has anybody filed at all", so a scope superseded out of the current set
    cannot make a clearance quietly cover less than it did.
    """
    return [row['use_scope'] for row in conn.execute(
        'SELECT DISTINCT use_scope FROM rights_decision WHERE project_id = ?'
        ' ORDER BY use_scope', (project_id,)).fetchall()]


def unlinked_scope_conflicts(conn, *, project_id: str) -> list:
    """Scopes carrying more than one live decision -- a chain that forked without supersing.

    :func:`current_decisions` keeps the newest word for such a scope, because there is no
    defensible other answer, but a reader must not have to trust that tie-break silently: a
    fork means "the current rights position" is undefined for that scope. Publishing it is
    what keeps "nothing replaced this row" from quietly meaning "whatever I picked".
    """
    rows = conn.execute(
        'SELECT use_scope, COUNT(*) AS live, GROUP_CONCAT(decision_id) AS ids'
        ' FROM rights_decision WHERE project_id = ? AND' + _CURRENT_WHERE
        + ' GROUP BY use_scope HAVING live > 1 ORDER BY use_scope', (project_id,)).fetchall()
    return [{'use_scope': row['use_scope'],
             'decision_ids': sorted(value for value in (row['ids'] or '').split(',') if value)}
            for row in rows]


def name_checked_only(conn, *, project_id: str) -> list:
    """Scopes whose current decision states no declared actor kind.

    The contract cannot carry an actor kind, so an HTTP-filed decision is name-checked
    rather than declared human. Reporting which ones are which is the difference between a
    limit stated and a limit hidden.
    """
    rows = conn.execute(
        'SELECT use_scope FROM rights_decision WHERE project_id = ? AND actor_kind IS NULL'
        ' AND' + _CURRENT_WHERE + ' ORDER BY use_scope', (project_id,)).fetchall()
    return [row['use_scope'] for row in rows]


def project_row(conn, project_id):
    return conn.execute('SELECT project_id, display_name FROM project WHERE project_id = ?',
                        (project_id,)).fetchone()
