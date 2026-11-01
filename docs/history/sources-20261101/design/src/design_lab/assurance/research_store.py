# SPDX-License-Identifier: MIT
"""Persist ResearchFinding documents against the state database.

``design-lab/schemas/research-finding.schema.json`` declared ``finding_id``/``claim``/
``sourceRefs`` for a long time with nothing in ``src/`` loading it, while
``design-lab/config/object-model.json`` already named the object and pointed at that file.
The declared-but-unread shape is the false-green this repository's own ledger gate exists to
convict, so this module's whole design constraint is: **the schema file is the check.** The
field list, the required trio, the confidence enum and the closed property set are read out
of the file on every run (:func:`contract`), never copied here -- a second copy is a second
authority able to disagree with the first.

What is enforced here is what a JSON Schema cannot see:

* the finding must belong to a project this state database actually has;
* **a finding with no source is a guess.** The schema already declares ``sourceRefs`` as
  required with ``minItems: 1``, and that is only as strong as the validator's arithmetic:
  ``[" "]`` and ``["", ""]`` satisfy ``minItems``. So the rule is enforced in its spirit --
  the list must hold at least one real reference the caller can name, every entry must be a
  non-blank string, and listing one source twice does not make it two. The list field is
  found structurally (:func:`source_ref_field`: the required field the contract declares as
  an array), so a contract that renames it moves this guard with it instead of leaving it
  checking a name nobody uses any more;
* history is append-only. A changed mind is a NEW row carrying ``supersedes``, one row cannot
  be superseded twice, and a supersede must stay inside the same project -- otherwise a later
  filing could retire a finding of another project and both projects would read a chain that
  does not exist. ``supersedes`` is a *column*, never a document field, because the contract
  closes its properties and does not declare one. Immutability itself belongs to the database
  (the triggers in ``design-lab-state-research-v1.sql``), not to a convention of this module;
* every stored row is re-validated on the way out (:func:`list_findings`), including that the
  source list in the bytes still matches the count column it was stored with.

The actor rule, and why it is NOT the rights rule. A research finding is working state, not a
human gate: AGENTS.md puts the Quality/Rights/Production gates behind human approval and puts
research findings on neither. So an agent may record one -- refusing that would just hide who
said it -- but it may not record one **as a human**. Three facts are kept apart instead of
collapsed into one word: an actor that DECLARES ``HUMAN``/``PANEL`` while naming automation is
refused outright (``RESEARCH_NOT_HUMAN``: a machine signing itself as a person is the lie this
guard exists for); an actor whose declared kind is in neither vocabulary is refused
(``RESEARCH_ACTOR_KIND_UNKNOWN``: a reader cannot be asked to guess); and a caller that states
nothing is stored with ``recorded_by`` NULL and reported in ``unattributed_findings``, which is
what every HTTP-filed finding is, because the closed contract has no field to carry an author.
A declared kind is a stronger claim than an absent one and is stored in its own column so the
read-back can tell the three apart. No function here invents an identity.

This is also where the long-term-knowledge boundary is stated rather than assumed. DESIGN-LAB
owns the audited working finding; ArcheAxis owns the truth, and a finding leaves only as a
rights-checked, human-approved ``KnowledgeCandidate``. Nothing in this module exports,
promotes, or reads anything as knowledge: :data:`DOES_NOT_PROVE` says so on every read-back,
and the row itself carries no state field that could be mistaken for one -- which is why there
is deliberately no ``recorded_at`` column either. The contract declares no timestamp and this
store will not invent a moment nobody stated, so ordering is insertion order and the read-back
says it does not know when anything was said.

Every refusal is a :class:`ResearchStoreError` with a distinct ``code``: "that project does not
exist here", "that document is not a finding", "that finding cites no source" and "a machine
tried to sign as a person" are four different facts, and an operator told "invalid" can act on
none of them.

Boundary: no provider call, no host access, no web fetch, no corpus read. It stores what a
caller claimed to have found and where it says it came from, and refuses everything else.
"""
from __future__ import annotations

from typing import Mapping
from functools import lru_cache
import json
import re
import sqlite3
import uuid

from . import AssuranceError, human_jury, require_text
from ..runtime.state_resources import repo_resource, state_schema

_RESEARCH = state_schema('design-lab-state-research-v1.sql')

#: The identity this store is written against. The bound contract declares **no**
#: ``schemaVersion`` property -- its ``additionalProperties: false`` set is exactly
#: finding_id/claim/sourceRefs/confidence/notDesignRule -- so there is no version const to
#: compare and a submitted finding that carried one would (correctly) be refused. ``$id`` is
#: the only identity the file binds, so that is what :func:`contract` compares: a one-sided
#: move, or a different document placed at this path, fails closed here instead of silently
#: validating findings against a contract nobody meant.
CONTRACT_ID = 'https://dtalex66.local/schemas/research-finding.json'
# D09 (batch 22): resolved packaged-first. PROJECT_ROOT is parents[3] of this module,
# which is the checkout in a source tree but `Lib/` once installed -- the old spelling
# made an installed wheel answer 500 for every research route.
CONTRACT_PATH = repo_resource('schemas/research-finding.schema.json')

#: Fields a caller may try to smuggle into the document. Each belongs somewhere else:
#: ``supersedes``/``recorded_by``/``actor_kind`` are columns on the row (the contract closes
#: its properties and declares none of them), and ``schemaVersion`` belongs to the other
#: assurance contracts, not this one. Named here so the refusal says what the caller sent
#: rather than reporting a closed-schema violation nobody can act on.
_COLUMN_FIELDS = ('actor_kind', 'project_id', 'recorded_by', 'supersedes')
_FOREIGN_VERSION_FIELDS = ('schemaVersion',)

#: Names that identify automation when one appears in a `recorded_by` value. Seeded from
#: `human_jury.AGENT_ACTOR_KINDS` rather than copied, so the two gates cannot drift apart on
#: what "an agent" is; the additions are the concrete ids this repository's own tooling runs
#: as. Used ONLY to refuse a *claimed* human signature -- see the module docstring.
_MULTI_CHAR_AGENT_NAMES = (
    'agent', 'assistant', 'automated', 'bot', 'chatbot', 'claude', 'codex', 'copilot',
    'cursor', 'deepseek', 'gemini', 'gpt', 'llm', 'machine', 'model', 'openai',
    'pipeline', 'qoder', 'script', 'service', 'system', 'tool', 'worker',
)
#: Matched only as a whole token: 'ai' is a substring of ordinary human names.
_TOKEN_ONLY_AGENT_NAMES = ('ai',)

#: What no stored finding proves. Published with every read-back, because the reader most
#: likely to over-read a populated research panel is the one who filed it.
DOES_NOT_PROVE = (
    'a finding is a claim somebody says they sourced. Nothing here re-reads, re-checks or '
    'resolves a `sourceRefs` entry: the strings stored are the ones the caller supplied, and '
    'a source that does not exist still makes a row that does',
    'a stored finding is DESIGN-LAB working state for one project. It is not a '
    'KnowledgeCandidate and not an export to ArcheAxis: long-term knowledge truth belongs to '
    'ArcheAxis and leaves only through the rights check and the human approval AGENTS.md '
    'requires, neither of which exists in this module',
    'a finding is not a design rule. The contract marks this explicitly (notDesignRule) and '
    'the table can store no other value, but a rule nobody approved is a direction gate that '
    'has not been held, and no count in this read-back stands in for holding it',
    'a populated research panel proves nothing about design quality, accessibility or anti-AI '
    'fingerprint: the Quality gate is assurance/quality_store.py, the Jury is '
    'assurance/human_jury.py, and neither reads this table',
    'this store records no timestamp and cannot say when anything was found: the contract '
    'declares none and this module invents none, so ordering is insertion order only',
    'the count of findings is not a denominator: nothing here knows how many findings a '
    'project ought to have, and an empty panel reads as "nobody recorded anything", never as '
    '"nothing is left to find"',
)

#: The closed vocabulary of refusal codes this store may raise. Declared here so a route, a
#: verb and a table can show an operator every way the gate says no, and so a new refusal
#: cannot quietly invent a code nobody reads: an unlisted code is a bug in this module.
REFUSAL_CODES = frozenset({
    'RESEARCH_PROJECT_NOT_RECORDED',
    'RESEARCH_DOCUMENT_MALFORMED',
    'RESEARCH_CONTRACT_UNREADABLE',
    'RESEARCH_CONTRACT_UNBOUND',
    'RESEARCH_FINDING_INVALID',
    'RESEARCH_SOURCE_REFS_EMPTY',
    'RESEARCH_SOURCE_REF_INVALID',
    'RESEARCH_ACTOR_MISSING',
    'RESEARCH_ACTOR_KIND_UNKNOWN',
    'RESEARCH_NOT_HUMAN',
    'RESEARCH_SUPERSEDES_UNKNOWN',
    'RESEARCH_SUPERSEDES_FOREIGN_PROJECT',
    'RESEARCH_ALREADY_SUPERSEDED',
    'RESEARCH_FINDING_ID_TAKEN',
    'RESEARCH_DATABASE_REFUSED',
    'RESEARCH_STORED_RECORD_INVALID',
})


class ResearchStoreError(RuntimeError):
    """A research finding was refused; ``code`` names which rule refused it."""

    def __init__(self, message: str, *, code: str):
        super().__init__(message)
        if code not in REFUSAL_CODES:
            # Never let a refusal go out under a label nothing documents.
            raise AssertionError(f'undocumented research refusal code {code!r}')
        self.code = code


def new_finding_id() -> str:
    """A fresh finding id, so a caller that states none cannot collide with a stored one.

    The identity is not a formality: an explicit id is what makes a retry recognisable as a
    replay instead of a second filing, which is why the CLI offers ``--finding-id`` and this
    is only the fallback for a caller that does not care what the id is.
    """
    return 'rf-' + uuid.uuid4().hex


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the state database with the research tables present.

    The asset store is asked to open its own database rather than this module re-applying
    schema files: ``asset_store.connect`` carries the path policy, the foreign-key pragma and
    the assets-v2 migration with its pre-migration backup. Doing it twice here would be a
    second implementation of the same migration, and the two would drift. (``jury_store``,
    ``quality_store`` and ``rights_ledger`` are the precedent.)
    """
    from ..runtime.asset_store import connect as connect_assets
    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    connection.executescript(_RESEARCH.read_text(encoding='utf-8'))
    connection.commit()
    return connection


@lru_cache(maxsize=1)
def contract() -> dict:
    """The ResearchFinding contract, read from disk, never copied into this module."""
    try:
        document = json.loads(CONTRACT_PATH.read_text(encoding='utf-8'))
    except (OSError, ValueError) as exc:
        raise ResearchStoreError(
            f'research findings cannot be validated because the contract is unreadable at '
            f'{CONTRACT_PATH.name}: {exc}', code='RESEARCH_CONTRACT_UNREADABLE')
    if not isinstance(document, dict):
        raise ResearchStoreError(
            f'{CONTRACT_PATH.name} is not a schema object; failing closed rather than '
            'accepting every document', code='RESEARCH_CONTRACT_UNREADABLE')
    if document.get('$id') != CONTRACT_ID:
        raise ResearchStoreError(
            f'{CONTRACT_PATH.name} binds {document.get("$id")!r}, not the {CONTRACT_ID!r} this '
            'store is written against; one side moved and the two would silently disagree about '
            'which document a finding is', code='RESEARCH_CONTRACT_UNBOUND')
    properties = document.get('properties') or {}
    if not properties:
        raise ResearchStoreError(
            f'{CONTRACT_PATH.name} declares no properties, so a finding has no shape to be '
            'refused for breaking', code='RESEARCH_CONTRACT_UNBOUND')
    if not (properties.get('confidence') or {}).get('enum'):
        raise ResearchStoreError(
            f'{CONTRACT_PATH.name} declares no confidence enum, so the read-back has no '
            'vocabulary to report findings against', code='RESEARCH_CONTRACT_UNBOUND')
    if document.get('additionalProperties') is not False:
        raise ResearchStoreError(
            f'{CONTRACT_PATH.name} no longer closes its properties, so a submission could '
            'carry a field this store would silently never store',
            code='RESEARCH_CONTRACT_UNBOUND')
    return document


def field_names() -> tuple:
    """The contract's closed property set -- what a submission may and may not carry."""
    return tuple(contract()['properties'])


def required_field_names() -> tuple:
    return tuple(contract().get('required') or ())


def optional_field_names() -> tuple:
    required = set(required_field_names())
    return tuple(name for name in field_names() if name not in required)


def confidence_vocabulary() -> tuple:
    """The confidence enum as the contract states it. The only place this module learns it."""
    return tuple(contract()['properties']['confidence']['enum'])


def source_ref_field() -> str:
    """The required field the contract declares as an array: the source list, by structure.

    Derived from the loaded schema instead of named as a literal so that the "no source is a
    guess" rule follows the contract if the contract moves. A schema that stops declaring a
    required array is not silently tolerated -- it refuses, because at that point there is no
    place in the document for a source to be stated at all.
    """
    document = contract()
    properties = document.get('properties') or {}
    for name in document.get('required') or ():
        if (properties.get(name) or {}).get('type') == 'array':
            return name
    raise ResearchStoreError(
        f'{CONTRACT_PATH.name} declares no required array field, so a finding cannot state a '
        'source at all and "a claim with no source is a guess" has nothing to be enforced '
        'against', code='RESEARCH_CONTRACT_UNBOUND')


def _agent_name_hit(name: str) -> list:
    """Which automation words this actor id declares. Empty means "names no automation"."""
    lowered = name.strip().lower()
    tokens = [token for token in re.split(r'[^a-z0-9]+', lowered) if token]
    hits = [token for token in _TOKEN_ONLY_AGENT_NAMES if token in tokens]
    hits += [token for token in _MULTI_CHAR_AGENT_NAMES if token in lowered]
    hits += [kind.lower() for kind in human_jury.AGENT_ACTOR_KINDS
             if kind.lower() in tokens and kind.lower() not in hits]
    return sorted(set(hits))


def _check_actor(*, recorded_by, actor_kind) -> tuple:
    """Establish what may be claimed about the author. Returns (name, kind) normalised.

    The order is deliberate and every branch fails closed: an unusable declared kind is
    refused before anything else, because "HUMAN" and "MODEL" must never arrive at the same
    check; a name that cannot be established is stored as absent, never assumed; and the only
    name check that refuses is the one making a claim it cannot support -- a human kind signed
    by something that names automation.
    """
    if actor_kind is not None:
        if not isinstance(actor_kind, str) or not actor_kind.strip():
            raise ResearchStoreError(
                'an actor kind was supplied that is not a name, so nothing is established '
                'about who authored this finding', code='RESEARCH_ACTOR_MISSING')
        actor_kind = actor_kind.strip().upper()
        if actor_kind not in human_jury.HUMAN_JUROR_KINDS + human_jury.AGENT_ACTOR_KINDS:
            raise ResearchStoreError(
                f'the declared actor kind {actor_kind!r} is neither one of '
                f'{", ".join(human_jury.HUMAN_JUROR_KINDS)} nor one of '
                f'{", ".join(human_jury.AGENT_ACTOR_KINDS)}: a reader cannot be asked to guess '
                'whether a finding was written by a person or a machine',
                code='RESEARCH_ACTOR_KIND_UNKNOWN')
    if recorded_by is None:
        if actor_kind is not None:
            raise ResearchStoreError(
                f'an actor kind of {actor_kind!r} was declared with no `recorded_by` to go with '
                'it: a kind nobody is attributed to establishes nothing',
                code='RESEARCH_ACTOR_MISSING')
        return None, None
    if not isinstance(recorded_by, str) or not recorded_by.strip():
        raise ResearchStoreError(
            'the author was stated as an empty name, so nothing is established about who '
            'authored this finding', code='RESEARCH_ACTOR_MISSING')
    name = recorded_by.strip()
    if actor_kind in human_jury.HUMAN_JUROR_KINDS:
        found = _agent_name_hit(name)
        if found:
            raise ResearchStoreError(
                f'{actor_kind} is refused for this author: `recorded_by` {name!r} names '
                f'automation ({", ".join(found)}). An agent may record a finding and be stored '
                'as what it is, but no function here turns a run into a human statement',
                code='RESEARCH_NOT_HUMAN')
    return name, actor_kind


def _validate_against_contract(document: dict) -> None:
    """The contract's own job: required trio, closed properties, confidence enum, formats."""
    from jsonschema import Draft202012Validator

    errors = sorted(Draft202012Validator(contract()).iter_errors(document),
                    key=lambda error: list(error.path))
    if errors:
        first = errors[0]
        where = '/'.join(str(part) for part in first.path)
        raise ResearchStoreError(
            f'the finding was refused by its own contract {CONTRACT_PATH.name}'
            f'{("/" + where) if where else ""}: {first.message}',
            code='RESEARCH_FINDING_INVALID')


def _validate_source_refs(document: dict) -> list:
    """The rule ``minItems: 1`` cannot express: a source list must hold a REAL reference.

    ``minItems`` is arithmetic, not judgement -- ``[]`` is refused by it, but ``[" "]``,
    ``["", ""]`` and ``["x", "x"]`` all pass and each is a finding with no evidence. Absent or
    non-list is left to the contract, which names that fact better than this function can.
    """
    field = source_ref_field()
    if field not in document or not isinstance(document[field], list):
        return []
    entries = document[field]
    if any(not isinstance(entry, str) for entry in entries):
        # A non-string entry is a type violation the contract names exactly ("is not of type
        # 'string'"), which is a better report than anything this rule can write about the
        # field as a whole. Left to the schema; the empty-list rule below must not hijack it.
        return []
    named = []
    blanks = 0
    for entry in entries:
        if isinstance(entry, str) and entry.strip():
            named.append(entry.strip())
        else:
            blanks += 1
    if not named:
        raise ResearchStoreError(
            f'{field} states no source anyone can name, and a design finding with no source is '
            f'a guess: {field} must carry at least one real reference',
            code='RESEARCH_SOURCE_REFS_EMPTY')
    if blanks:
        raise ResearchStoreError(
            f'{field} carries {blanks} entry that is not a reference anyone can name (a blank '
            'or whitespace-only string): a blank entry is not a source and does not count '
            'toward the one real source the list needs',
            code='RESEARCH_SOURCE_REF_INVALID')
    duplicates = sorted({entry for entry in named if named.count(entry) > 1})
    if duplicates:
        raise ResearchStoreError(
            f'{field} lists {", ".join(duplicates)} more than once: repeating one source is '
            'not a second source, and a finding whose strength comes from a duplicated entry '
            'misstates its own evidence', code='RESEARCH_SOURCE_REF_INVALID')
    return named


def _validate_text_shapes(document: dict) -> None:
    """``minLength: 1`` accepts a single space, so the two scalars are checked here.

    Applied through the package's own primitive rather than restated as a field list: the
    names come from the contract's required trio, and only the ones the schema declares as
    strings are tested (the source list is judged by :func:`_validate_source_refs`).
    """
    for name in ('finding_id', 'claim'):
        try:
            require_text(document.get(name), name)
        except AssuranceError as exc:
            raise ResearchStoreError(str(exc), code='RESEARCH_FINDING_INVALID') from None


def _foreign_fields(document: Mapping) -> list:
    """Fields the caller sent that belong elsewhere. Named for the message, enforced by the
    closed schema; refusing them here first means the reason an operator reads is about the
    field, not about a JSON Schema violation of a property they never meant to set."""
    smuggled = [name for name in _FOREIGN_VERSION_FIELDS if name in document]
    smuggled += [name for name in _COLUMN_FIELDS if name in document]
    return sorted(set(smuggled))


def record(conn, *, project_id: str, document: dict, recorded_by: str | None = None,
           actor_kind: str | None = None, supersedes: str | None = None) -> dict:
    """Validate one research finding, then append it. Returns the stored document.

    ``recorded_by``, ``actor_kind`` and ``supersedes`` are out-of-document on purpose: the
    contract closes its properties and declares none of them, so an HTTP submission cannot
    supply them and a caller that does state one (the CLI, which asks the operator) is stored
    in its own column rather than in the bytes the contract describes.
    """
    if not isinstance(document, Mapping):
        raise ResearchStoreError(
            'a research finding must be a JSON object; nothing was written',
            code='RESEARCH_DOCUMENT_MALFORMED')
    normalized = json.loads(json.dumps(dict(document), allow_nan=False))
    if conn.execute('SELECT 1 FROM project WHERE project_id = ?', (project_id,)).fetchone() is \
            None:
        raise ResearchStoreError(
            f'project {project_id!r} is not recorded in this state database: a finding cannot '
            'be filed against a project that does not exist here',
            code='RESEARCH_PROJECT_NOT_RECORDED')
    foreign = _foreign_fields(normalized)
    if foreign:
        raise ResearchStoreError(
            f'the document carries the field(s) {", ".join(foreign)}, which are columns of this '
            'store or belong to another contract: the research-finding schema closes its '
            'properties and declares none of them, so no submission becomes a finding of this '
            'contract by relabelling', code='RESEARCH_FINDING_INVALID')
    name, kind = _check_actor(recorded_by=recorded_by, actor_kind=actor_kind)
    # The source rule is checked before the schema, so an empty list is refused with the word
    # that names why ("a finding with no source is a guess"), not with `minItems` arithmetic
    # that an operator would have to translate. The contract still owns every other shape.
    sources = _validate_source_refs(normalized)
    _validate_against_contract(normalized)
    _validate_text_shapes(normalized)

    if supersedes is not None:
        if supersedes == normalized['finding_id']:
            raise ResearchStoreError('a research finding may not supersede itself',
                                     code='RESEARCH_SUPERSEDES_UNKNOWN')
        anywhere = conn.execute(
            'SELECT project_id FROM research_finding WHERE finding_id = ?',
            (supersedes,)).fetchone()
        if anywhere is not None and anywhere['project_id'] != project_id:
            raise ResearchStoreError(
                f'supersedes {supersedes!r} is a finding of project '
                f'{anywhere["project_id"]!r}, not of {project_id!r}: retiring another '
                'project\'s finding from this one would leave a chain that project never '
                'filed and a current finding its read-back does not know about',
                code='RESEARCH_SUPERSEDES_FOREIGN_PROJECT')
        if conn.execute('SELECT 1 FROM research_finding WHERE finding_id = ? AND project_id = ?',
                        (supersedes, project_id)).fetchone() is None:
            raise ResearchStoreError(
                f'supersedes {supersedes!r} is not a finding of this project',
                code='RESEARCH_SUPERSEDES_UNKNOWN')
        if conn.execute('SELECT 1 FROM research_finding WHERE supersedes = ?',
                        (supersedes,)).fetchone():
            raise ResearchStoreError(
                f'{supersedes} has already been superseded; a second replacement would fork '
                'the chain and leave "the current finding" undefined',
                code='RESEARCH_ALREADY_SUPERSEDED')

    try:
        conn.execute(
            'INSERT INTO research_finding (finding_id, project_id, claim, confidence,'
            ' source_refs_json, source_ref_count, not_design_rule, recorded_by, actor_kind,'
            ' document_json, supersedes) VALUES (?,?,?,?,?,?,?,?,?,?,?)',
            (normalized['finding_id'], project_id, normalized['claim'],
             normalized.get('confidence'), json.dumps(sources, ensure_ascii=False),
             len(sources), 1 if normalized.get('notDesignRule') else None, name, kind,
             json.dumps(normalized, ensure_ascii=False, sort_keys=True), supersedes))
        conn.commit()
    except sqlite3.IntegrityError as exc:
        # The triggers and CHECKs in the schema are the last line; reaching them means
        # something above this module is wrong, so it is reported, never retried.
        text = str(exc)
        code = ('RESEARCH_FINDING_ID_TAKEN'
                if 'research_finding.finding_id' in text else 'RESEARCH_DATABASE_REFUSED')
        raise ResearchStoreError(f'the state database refused the finding: {text}',
                                 code=code) from None
    # The row is stored; nothing else here is claimed about what the finding is worth.
    return normalized


_CURRENT_WHERE = (
    ' NOT EXISTS (SELECT 1 FROM research_finding child'
    '  WHERE child.supersedes = research_finding.finding_id)')


def _stored_documents(conn, *, project_id: str, where: str = '') -> list:
    """Rows of one project, in the order they were filed, each re-validated on read.

    A row that no longer satisfies the contract is a tamper signal, not something to serve
    quietly: the append-only triggers make that unreachable in normal operation, so reaching
    it means the schema or the policy moved underneath the data. It is reported as a refusal,
    because a partially trusted finding list is worse than none.
    """
    rows = conn.execute(
        'SELECT document_json, source_ref_count, recorded_by, actor_kind FROM research_finding'
        ' WHERE project_id = ?' + where + ' ORDER BY rowid, finding_id', (project_id,)).fetchall()
    findings = []
    for row in rows:
        document = json.loads(row['document_json'])
        try:
            sources = _validate_source_refs(document)
            _validate_against_contract(document)
            _validate_text_shapes(document)
        except ResearchStoreError as exc:
            raise ResearchStoreError(
                f'the stored finding {document.get("finding_id")!r} no longer satisfies the '
                f'research-finding contract: {exc}',
                code='RESEARCH_STORED_RECORD_INVALID') from None
        if len(sources) != row['source_ref_count']:
            # The column and the bytes must agree or a count published from one is a count
            # nobody can trace: `source_ref_count` exists so a query can count sources without
            # parsing documents, which is only honest while it is the same number.
            raise ResearchStoreError(
                f'the stored finding {document.get("finding_id")!r} carries '
                f'{len(sources)} real source refs in its document but was written with '
                f'source_ref_count {row["source_ref_count"]}: the row and its bytes disagree, '
                'so neither can be published', code='RESEARCH_STORED_RECORD_INVALID')
        findings.append(document)
    return findings


def list_findings(conn, *, project_id: str) -> list:
    """Every finding of one project, oldest first, re-validated on read."""
    return _stored_documents(conn, project_id=project_id)


def current_findings(conn, *, project_id: str) -> dict:
    """``finding_id`` -> the finding nothing has replaced. Nothing is invented here.

    Unlike the rights ledger there is no single slot per project to be "the current" answer
    for: several findings legitimately stand at once, and a superseded one keeps being listed
    by :func:`list_findings`. So this maps the live rows and the read-back publishes both
    counts, because "how many exist" and "how many still stand" are different questions and
    one number for both would be a claim about neither.
    """
    return {document['finding_id']: document for document in
            _stored_documents(conn, project_id=project_id, where=' AND' + _CURRENT_WHERE)}


def source_counts(conn, *, project_id: str) -> dict:
    """finding_id -> how many real source refs that row's bytes still carry.

    Derived from the documents, not read off the column, so a published number can be traced
    to the strings it counted.
    """
    return {document['finding_id']: len(document[source_ref_field()])
            for document in list_findings(conn, project_id=project_id)}


def unattributed_findings(conn, *, project_id: str) -> list:
    """Live findings whose author was never stated.

    The contract has no author field, so everything filed over HTTP lands here. Reporting
    which rows carry no declared author is the difference between a limit stated and a limit
    hidden -- a reader shown a count and no such list would assume a person said each one.
    """
    rows = conn.execute(
        'SELECT finding_id FROM research_finding WHERE project_id = ? AND recorded_by IS NULL'
        ' AND' + _CURRENT_WHERE + ' ORDER BY rowid, finding_id', (project_id,)).fetchall()
    return [row['finding_id'] for row in rows]


def undeclared_disclaimer(conn, *, project_id: str) -> list:
    """Live findings that never stated ``notDesignRule``.

    The contract makes it optional, so absence is legal and must not be read as a disclaimer:
    a finding nobody disclaimed as non-rule is a weaker record than one that says so, and the
    read-back publishes the two separately instead of showing one word for both.
    """
    rows = conn.execute(
        'SELECT finding_id FROM research_finding WHERE project_id = ? AND not_design_rule IS NULL'
        ' AND' + _CURRENT_WHERE + ' ORDER BY rowid, finding_id', (project_id,)).fetchall()
    return [row['finding_id'] for row in rows]


def actor_kinds(conn, *, project_id: str) -> dict:
    """finding_id -> the declared author kind (or None), for the live rows.

    Published so a reader can tell "a person said this", "a machine said this" and "nobody
    said who" apart. Deriving it from the row rather than from the document is the point: the
    closed contract cannot carry a kind, so any document claiming one would have been refused.
    """
    rows = conn.execute(
        'SELECT finding_id, actor_kind FROM research_finding WHERE project_id = ? AND'
        + _CURRENT_WHERE + ' ORDER BY rowid, finding_id', (project_id,)).fetchall()
    return {row['finding_id']: row['actor_kind'] for row in rows}


def project_row(conn, project_id):
    return conn.execute('SELECT project_id, display_name FROM project WHERE project_id = ?',
                        (project_id,)).fetchone()
