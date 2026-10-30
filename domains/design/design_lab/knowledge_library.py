# SPDX-License-Identifier: MIT
"""The knowledge library: entries a person wrote down, their revisions, and one rebuildable index.

DL-KB-02/03/04. Before this module the repository could *review* a knowledge candidate that a
production run had produced, but there was nowhere to put a piece of knowledge a person wanted to
keep -- a rule, a method, a prompt pattern, a note about a model, a recipe, a case. This is that
place, and it is deliberately small:

* one authoritative writer. Every revision -- created, revised or imported -- goes through
  ``_write_revision``; nothing else inserts into ``knowledge_entry_revision``. The list and detail
  routes read; they never repair, never promote and never fill a gap they noticed.
* one mutable truth source. The canonical bytes live in ``knowledge_entry_revision.document_json``;
  the FTS5 table is derived and ``rebuild_index`` reconstructs it from those rows. The index is
  therefore allowed to be thrown away, and the rebuild route is the proof rather than a comment.
* append-only. A correction is a new revision; the previous one keeps its bytes. "Current" is
  MAX(revision) at read time -- no ``active`` column, because a mutable current-marker is how a
  second truth source is born.

What an entry is NOT: it is not a reviewed KnowledgeCandidate (that flow lives in
``knowledge_review.py`` and has its own human gate), and it is not a verified source. ``source``
uses SourceRecord's own field names (``design-lab/schemas/source-record.schema.json``) so the two
records speak one vocabulary, but it relaxes that record's strictness in exactly one direction:
a field a person did not fill is the literal ``UNKNOWN`` instead of a schema refusal. Nothing is
upgraded to reviewed by being written -- ``source.verification`` is always ``UNVERIFIED``, and the
store refuses a caller that claims otherwise. "The link exists" is not "the source was checked".

Search (DL-KB-04) is FTS5 with ``tokenize='trigram'`` plus a mandatory LIKE fallback. The fallback
is not defensive decoration: a trigram index cannot match a query shorter than three characters,
which is most two-character Chinese words -- ``分镜``, ``粒子``, ``品牌``. The test asserts that the
index alone misses those queries (so the fallback has a failing control), and that the public
search still finds the entries. A search answer also carries *why* each row matched: the field names
and the terms found in them, computed from the stored bytes of the row being returned.
"""
from __future__ import annotations

from contextlib import closing, contextmanager
import hashlib
import json
import re
import sqlite3
import uuid

from .assurance import utc_now_rfc3339
from .interop import InteropError, load_schema, resource_registry, schema_errors
from .runtime.state_resources import repo_resource, state_schema

ENTRY_VERSION = 'design-lab/knowledge-entry/v1'
READBACK_VERSION = 'design-lab/knowledge-entry-readback/v1'
LIBRARY_VERSION = 'design-lab/knowledge-library/v1'
IMPORT_VERSION = 'design-lab/knowledge-import/v1'
WRITE_VERSION = 'design-lab/knowledge-entry-write/v1'
INDEX_VERSION = 'design-lab/knowledge-index-rebuild/v1'

ENTRY_SCHEMA_PATH = repo_resource('schemas/knowledge-entry-v1.schema.json')
_READBACK_SCHEMA_PATH = repo_resource('schemas/knowledge-entry-readback-v1.schema.json')
_LIBRARY_SCHEMA_PATH = repo_resource('schemas/knowledge-library-readback-v1.schema.json')
_IMPORT_SCHEMA_PATH = repo_resource('schemas/knowledge-import-v1.schema.json')
_WRITE_SCHEMA_PATH = repo_resource('schemas/knowledge-entry-write-v1.schema.json')
_INDEX_SCHEMA_PATH = repo_resource('schemas/knowledge-index-rebuild-v1.schema.json')
_STATE = state_schema('design-lab-state-knowledge-library-v1.sql')
#: Recorded judgements (DL-KB-05 D5). Separate resource, same database: the entry's revision rows
#: stay append-only, and a judgement made later is a new row of its own.
_JUDGEMENT_STATE = state_schema('design-lab-state-knowledge-judgement-v1.sql')
JUDGEMENT_KINDS = ('RECOMMENDATION', 'SOURCE_STATE')
RECOMMENDATION_VALUE = 'RECOMMENDED'
SOURCE_STATES = ('ACTIVE', 'INVALID')

ENTRY_TYPES = ('STANDARD', 'METHOD', 'PROMPT', 'MODEL_GUIDE', 'RECIPE', 'CASE')
#: The six types as the screen names them. Kept here (not in the view) so the wire's machine
#: words and the Chinese labels are one table; a second copy in TypeScript would be a second
#: vocabulary able to drift, which is what verify_state_vocabularies.py exists to prevent.
TYPE_LABELS = {'STANDARD': '规范', 'METHOD': '方法', 'PROMPT': '提示词',
               'MODEL_GUIDE': '模型指南', 'RECIPE': '配方', 'CASE': '案例'}
UNKNOWN = 'UNKNOWN'
SOURCE_KEYS = ('sourceId', 'origin', 'author', 'license', 'licenseStatus', 'allowedUsage',
               'citationScope', 'version', 'observedAt', 'contentHash', 'verification')
LICENSE_STATES = ('reviewed', 'unknown', 'reference-only')
#: The fields the content digest covers. Identity (id, revision), bookkeeping (created_at/by) and
#: the recommendation flag are outside it: rewriting identical content with a different
#: recommendation is not a content change, and a digest that moved would say it was.
CONTENT_FIELDS = ('entry_type', 'title', 'summary', 'domain_tags', 'task_tags', 'target_tools',
                  'body', 'applicability', 'limits', 'source', 'related_capability_ids')
SEARCH_FIELDS = ('title', 'summary', 'body', 'domain_tags', 'task_tags', 'target_tools')
#: Published performance claim (taskpack §14: 1,000 records, p95 ≤ 300 ms). The test seeds 1,000
#: entries, times 30 searches and compares against this number, so the sentence in the docs and the
#: measurement cannot drift apart.
SEARCH_P95_BUDGET_MS = 300
DEFAULT_LIMIT = 50
MAX_LIMIT = 200
MAX_QUERY = 200

CLAIMS_NOT_MADE = (
    'storing an entry is not verifying its source: source.verification stays UNVERIFIED, and no '
    'fetch is made to check that a link resolves or that the bytes at it are the ones cited',
    'an entry is not a reviewed KnowledgeCandidate; that flow has its own human gate and its own '
    'candidates, and nothing here approves an export',
    'a recommended revision is a recorded judgement, not a computed ranking',
    'searching this library runs no model: it is FTS5 plus a substring fallback, with no synonym '
    'expansion and no embedding',
)

IMPORT_CLAIMS = (
    'an import writes a record; it does not fetch the source, so source.contentHash is the '
    "caller's claim and not something this service measured",
    'a duplicate answer means the same source, version and content digest are already stored; it '
    'does not mean the entry was reviewed',
)

DOES_NOT_SAY = (
    '检索没有调用模型，也没有做近义词扩写或向量召回',
    '一条条目被读到，不代表它的来源链接已被核验',
    '推荐版本是一条记录，不是自动排序得出的"最好版本"',
)

_TERM = re.compile(r'[^\s,，、;；]+')
_ID = re.compile(r'^kentry-[0-9a-f]{32}$')
_HEX32 = re.compile(r'^[0-9a-f]{32}$')


class KnowledgeLibraryError(ValueError):
    """A store refusal carrying the status and code the route answers with."""

    def __init__(self, status, code, detail=None):
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the shared state database with the knowledge-library tables present."""
    from .runtime.asset_store import connect as connect_assets

    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    try:
        connection.executescript(_STATE.read_text(encoding='utf-8'))
        connection.executescript(_JUDGEMENT_STATE.read_text(encoding='utf-8'))
    except sqlite3.OperationalError as exc:
        # The derived index needs FTS5 with the trigram tokenizer. A build without it must not
        # degrade into "search silently returns the whole library": no index, no Chinese search,
        # and the honest answer is to refuse the route and name the missing capability.
        raise KnowledgeLibraryError(
            500, 'KNOWLEDGE_INDEX_UNAVAILABLE',
            f'the state database could not create the FTS5 trigram index: {exc}. Chinese search '
            'cannot be served without it, so the library refuses rather than answering an '
            'unindexed list as if it were a search') from None
    connection.commit()
    return connection


def _now() -> str:
    return utc_now_rfc3339()


def _canonical(document) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def _digest(document) -> str:
    return 'sha256:' + hashlib.sha256(
        _canonical(document).encode('utf-8')).hexdigest()


def _content_digest(document) -> str:
    return _digest({key: document[key] for key in CONTENT_FIELDS})


_registry = None


def _ref_registry():
    """Resolve the readback contracts' ``$ref`` into the entry contract offline.

    Same shape as prompt_results._ref_registry: the entry schema's own ``$id`` is the URI the
    readback schema points at, so loading it from the same packaged path the writer validates
    against is the only way the two can never describe different documents.
    """
    global _registry
    if _registry is None:
        try:
            document = load_schema(ENTRY_SCHEMA_PATH)
        except (InteropError, OSError) as exc:
            raise KnowledgeLibraryError(
                500, 'KNOWLEDGE_CONTRACT_UNREADABLE',
                f'cannot load {ENTRY_SCHEMA_PATH.name} for $ref resolution: {exc}') from None
        identifier = document.get('$id')
        if not isinstance(identifier, str):
            raise KnowledgeLibraryError(
                500, 'KNOWLEDGE_CONTRACT_UNREADABLE',
                f'{ENTRY_SCHEMA_PATH.name} carries no $id, so a $ref into it cannot be resolved '
                'offline')
        _registry = resource_registry({identifier: document})
    return _registry


def _check(document, path, label, *, registry=None):
    try:
        problems = schema_errors(load_schema(path), document, registry=registry)
    except (InteropError, OSError) as exc:
        raise KnowledgeLibraryError(500, 'KNOWLEDGE_CONTRACT_UNREADABLE',
                                    f'cannot load {path.name} for {label}: {exc}') from None
    if problems:
        raise KnowledgeLibraryError(500, 'KNOWLEDGE_CONTRACT_VIOLATION', problems)
    return document


def _text(value, field):
    if value is None:
        return UNKNOWN
    if not isinstance(value, str):
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_FIELD_MALFORMED',
                                    f'{field} must be a string (or absent); got '
                                    f'{type(value).__name__}')
    return value.strip() or UNKNOWN


def _tags(value, field, *, unknown_when_empty=True):
    if value is None:
        return [UNKNOWN] if unknown_when_empty else []
    if not isinstance(value, list):
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_FIELD_MALFORMED',
                                    f'{field} must be a list of strings (or absent)')
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise KnowledgeLibraryError(400, 'KNOWLEDGE_FIELD_MALFORMED',
                                        f'{field} contains an empty or non-string tag')
        out.append(item.strip())
    if out:
        return out
    # A tag list nobody filled is UNKNOWN -- "no tag was given" is a missing field, and the
    # taskpack says a missing field is written as UNKNOWN rather than left as an empty array
    # that reads like "this entry applies nowhere". A reference list is different: an entry
    # that names no capability really is related to none, so `related_capability_ids` may be [].
    return [UNKNOWN] if unknown_when_empty else []


def _source(value):
    """Normalise one source object, filling UNKNOWN where the caller left a field out.

    Two rules are refusals rather than normalisations: an unknown licence cannot be labelled
    ``reviewed`` (that would manufacture a licence), and ``verification`` cannot be
    ``VERIFIED`` (nothing in this service fetches a source, so a caller's claim of verification
    would be a claim this service cannot make).
    """
    if value is None:
        value = {}
    if not isinstance(value, dict):
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_SOURCE_MALFORMED',
                                    'source must be an object (or absent)')
    extra = sorted(set(value) - set(SOURCE_KEYS))
    if extra:
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_SOURCE_UNKNOWN_FIELD',
                                    f'source carries field(s) this record does not define: {extra}')
    verification = value.get('verification')
    if verification not in (None, '', 'UNVERIFIED'):
        raise KnowledgeLibraryError(
            409, 'KNOWLEDGE_SOURCE_VERIFICATION_UNSUPPORTED',
            'source.verification is always UNVERIFIED: this service does not fetch the origin, '
            "so it cannot certify that a link resolves or that the bytes behind it are the ones "
            "cited. Recording VERIFIED would be a claim the service never measured")
    status = value.get('licenseStatus')
    status = 'unknown' if status in (None, '') else status
    if status not in LICENSE_STATES:
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_LICENSE_STATUS_INVALID',
                                    f'source.licenseStatus must be one of {LICENSE_STATES}; '
                                    f'got {status!r}')
    source = {key: _text(value.get(key), f'source.{key}') for key in SOURCE_KEYS}
    source['licenseStatus'] = status
    source['verification'] = 'UNVERIFIED'
    if source['license'] == UNKNOWN and status != 'unknown':
        raise KnowledgeLibraryError(
            400, 'KNOWLEDGE_LICENSE_UNKNOWN_CONTRADICTION',
            f'source.license is {UNKNOWN} but licenseStatus is {status!r}; an unknown licence '
            "cannot be labelled reviewed or reference-only")
    return source


def _fields(value, *, for_revision):
    fields = {
        'entry_type': value['entry_type'],
        'title': _text(value['title'], 'title'),
        'summary': _text(value['summary'], 'summary'),
        'domain_tags': _tags(value['domain_tags'], 'domain_tags'),
        'task_tags': _tags(value['task_tags'], 'task_tags'),
        'target_tools': _tags(value['target_tools'], 'target_tools'),
        'body': _text(value['body'], 'body'),
        'applicability': _text(value['applicability'], 'applicability'),
        'limits': _text(value['limits'], 'limits'),
        'source': _source(value['source']),
        'related_capability_ids': _tags(value.get('related_capability_ids'),
                                        'related_capability_ids', unknown_when_empty=False),
        'recommended': value.get('recommended'),
    }
    if fields['entry_type'] not in ENTRY_TYPES:
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_TYPE_INVALID',
                                    f'entry_type must be one of {ENTRY_TYPES}; '
                                    f'got {fields["entry_type"]!r}')
    for key in ('title', 'summary', 'body'):
        if fields[key] == UNKNOWN:
            raise KnowledgeLibraryError(
                400, 'KNOWLEDGE_CONTENT_MISSING',
                f'{key} is required: an entry without it is a label, not knowledge. A field that '
                'can be unknown (applicability, limits, source fields) is written as UNKNOWN; '
                'these three cannot')
    recommended = fields['recommended']
    if recommended is None:
        recommended = not for_revision
    if not isinstance(recommended, bool):
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_FIELD_MALFORMED',
                                    'recommended must be a boolean when present')
    fields['recommended'] = recommended
    return fields


def _document(entry_id, revision, fields, *, created_at, created_by, supersedes):
    document = {
        'schemaVersion': ENTRY_VERSION,
        'knowledge_entry_id': entry_id,
        'revision': revision,
        'entry_type': fields['entry_type'],
        'title': fields['title'],
        'summary': fields['summary'],
        'domain_tags': list(fields['domain_tags']),
        'task_tags': list(fields['task_tags']),
        'target_tools': list(fields['target_tools']),
        'body': fields['body'],
        'applicability': fields['applicability'],
        'limits': fields['limits'],
        'source': dict(fields['source']),
        'related_capability_ids': list(fields['related_capability_ids']),
        'content_sha256': '',
        'supersedes': supersedes,
        'recommended': fields['recommended'],
        'created_at': created_at,
        'created_by': created_by,
        'claims_not_made': list(CLAIMS_NOT_MADE),
    }
    document['content_sha256'] = _content_digest(document)
    return _check(document, ENTRY_SCHEMA_PATH, 'knowledge entry')


def _import_id(source_id, version):
    """The identity of an imported entry: its source and the version of it that was read.

    Deliberately NOT the content digest. If the id moved with the content, re-importing a
    corrected file would look like a brand-new source instead of a second reading of the same
    version, and "the same source at different versions is retained" (acceptance A4) would be
    satisfied by accident -- every import would be new. With the version inside the id, the three
    outcomes are distinguishable: same id + same digest is a duplicate, same id + different digest
    is a contradiction the caller has to resolve, different id from the same sourceId is a version.
    """
    seed = f'{source_id}\x00{version}'.encode('utf-8')
    return 'kentry-' + hashlib.sha256(seed).hexdigest()[:32]


def _fts_row(document):
    return (document['knowledge_entry_id'], document['revision'], document['title'],
            document['summary'], document['body'],
            ', '.join(document['domain_tags'] + document['task_tags']),
            ', '.join(document['target_tools']))


def _fts_terms(term):
    """The FTS5 query for one term, quoted so punctuation cannot become syntax.

    A double quote inside a quoted FTS5 string is escaped by doubling it. The term is quoted
    whole, which is what makes a CJK run one token instead of an expression.
    """
    return '"' + term.replace('"', '""') + '"'


def _fts_matches(conn, term):
    """Ids the trigram index answers for one term -- the measurement the fallback exists for."""
    try:
        rows = conn.execute(
            'SELECT DISTINCT entry_id FROM knowledge_entry_fts WHERE knowledge_entry_fts MATCH ?',
            (_fts_terms(term),)).fetchall()
    except sqlite3.OperationalError:
        return []
    return [row['entry_id'] if isinstance(row, sqlite3.Row) else row[0] for row in rows]


def _contains(haystack, needle):
    return needle.casefold() in haystack.casefold()


def _field_text(document, field):
    value = document[field]
    return ', '.join(value) if isinstance(value, list) else value


def _statuses(conn):
    """Which entries are superseded, and by whom; and each entry's recommended revision.

    A recorded RECOMMENDATION judgement outranks the flag written with the revision: the flag can
    only ever say what was recommended when those bytes were created, while the judgement is the
    later act of moving the recommendation back (DL-KB-05 D5). Entries with no judgement keep the
    flag, so nothing changes for a library nobody has re-ranked.
    """
    superseded_by = {}
    for row in conn.execute(
            'SELECT entry_id, supersedes FROM knowledge_entry WHERE supersedes IS NOT NULL'
            ' ORDER BY created_at, entry_id'):
        # Ordered, because `setdefault` keeps the first row it sees and an unordered scan makes
        # "which successor is current" depend on SQLite's mood. The trigger in the state schema now
        # refuses a second successor, so no library written from here on can fork a chain; a
        # library that already holds one from before stays readable and now reports the same
        # successor on every read instead of an arbitrary one.
        superseded_by.setdefault(row['supersedes'], row['entry_id'])
    recommended = {row['entry_id']: row['top'] for row in conn.execute(
        'SELECT entry_id, MAX(revision) AS top FROM knowledge_entry_revision'
        ' WHERE recommended=1 GROUP BY entry_id')}
    for entry_id, judgement in _latest_judgements(conn).get('RECOMMENDATION', {}).items():
        recommended[entry_id] = judgement['revision']
    return superseded_by, recommended


def _latest_judgements(conn, entry_id=None):
    """The newest judgement of each kind, per entry, optionally for one entry only.

    `rowid` is the record order because the table is append-only: no UPDATE can move an older
    judgement to the top, so "latest" is a fact about insertion order rather than a clock reading.
    """
    sql = ('SELECT j.* FROM knowledge_judgement j WHERE j.rowid = (SELECT MAX(k.rowid)'
           ' FROM knowledge_judgement k WHERE k.entry_id=j.entry_id AND k.kind=j.kind)')
    args = ()
    if entry_id is not None:
        sql += ' AND j.entry_id=?'
        args = (entry_id,)
    latest = {}
    for row in conn.execute(sql, args):
        latest.setdefault(row['kind'], {})[row['entry_id']] = _judgement_view(row)
    return latest


def _judgement_view(row):
    """One judgement row in the shape the readback carries: no rowid, no duplicate entry id."""
    return {
        'judgement_id': row['judgement_id'],
        'kind': row['kind'],
        'revision': row['revision'],
        'value': row['value'],
        'replaced_by': row['replaced_by'],
        'reason': row['reason'],
        'recorded_by': row['recorded_by'],
        'recorded_at': row['recorded_at'],
    }


def _judgement_history(conn, entry_id):
    """Every judgement recorded about one entry, oldest first -- the audit trail D5 asks for."""
    return [_judgement_view(row) for row in conn.execute(
        'SELECT * FROM knowledge_judgement WHERE entry_id=? ORDER BY rowid', (entry_id,))]


def _index_state(conn):
    receipt = conn.execute(
        'SELECT rebuilt_at FROM knowledge_index_state WHERE name=?',
        ('knowledge_entry_fts',)).fetchone()
    rows = conn.execute(
        'SELECT COUNT(DISTINCT entry_id) FROM knowledge_entry_revision').fetchone()[0]
    indexed = conn.execute(
        'SELECT COUNT(DISTINCT entry_id) FROM knowledge_entry_fts').fetchone()[0]
    return {'rows': rows, 'indexed': indexed,
            'rebuilt_at': receipt['rebuilt_at'] if receipt is not None else None}


def _readings(conn):
    """Every entry's current revision, parsed, newest revision per entry.

    Unreadable rows are counted and skipped: a row whose JSON cannot be parsed is still a row, so
    it must not make the library look empty -- the count is what says it happened.
    """
    rows = conn.execute(
        'SELECT r.entry_id, r.revision, r.entry_type, r.title, r.content_sha256, r.recommended,'
        ' r.created_at, r.created_by, r.document_json FROM knowledge_entry_revision r'
        ' WHERE r.revision = (SELECT MAX(x.revision) FROM knowledge_entry_revision x'
        '                     WHERE x.entry_id = r.entry_id)').fetchall()
    documents, unreadable = {}, 0
    for row in rows:
        try:
            document = json.loads(row['document_json'])
        except (TypeError, ValueError):
            unreadable += 1
            continue
        documents[row['entry_id']] = document
    return documents, unreadable


def _superseded_detail(supersedes, taken):
    """The one wording for "this entry already has a successor", from both refusals.

    The application guard and the trigger's `IntegrityError` fallback used to say nearly the same
    thing differently, and the shorter one omitted the successor's id -- which is the only piece the
    operator can act on. One function, so the difference cannot come back.
    """
    return (f'{supersedes} is already superseded by {", ".join(taken[:3])}'
            + f'{", …" if len(taken) > 3 else ""}; two rows replacing one entry would make '
            '"which one is current" unanswerable. Revise the successor instead of adding a '
            'second one beside it')


def _supersedes_guard(conn, supersedes):
    """The whole rule about `supersedes`, asked the same way by every route that can start a chain.

    `create` refused a second successor; `import_entry` validated the shape and the existence but
    never asked whether the entry was already replaced, so the fork the UI blocked was writable
    through the import route (owner audit 2026-10-26, finding 2). One function now, so the two
    routes cannot drift apart again, and the same words whichever one refused you.
    """
    if supersedes is None:
        return
    if not isinstance(supersedes, str) or _ID.match(supersedes) is None:
        raise KnowledgeLibraryError(400, 'KNOWLEDGE_SUPERSEDES_MALFORMED',
                                    'supersedes must be a knowledge entry id or null')
    if conn.execute('SELECT 1 FROM knowledge_entry WHERE entry_id=?',
                    (supersedes,)).fetchone() is None:
        raise KnowledgeLibraryError(
            404, 'KNOWLEDGE_SUPERSEDES_UNKNOWN',
            f'{supersedes} is not an entry in this library, so nothing can replace it')
    taken = [row['entry_id'] for row in conn.execute(
        'SELECT entry_id FROM knowledge_entry WHERE supersedes=? ORDER BY created_at, entry_id',
        (supersedes,))]
    if taken:
        raise KnowledgeLibraryError(409, 'KNOWLEDGE_SUPERSESSION_CONFLICT',
                                    _superseded_detail(supersedes, taken))


class KnowledgeLibrary:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return connect(self.paths.database_path(self.service.database),
                       project_root=self.paths.project_root)

    @contextmanager
    def _write_transaction(self, conn):
        """Take the write lock BEFORE the caller reads, because every guard here is read-then-write.

        With the default deferred transaction, two writers can both run `_supersedes_guard`, both
        see no successor, and both insert. BEGIN IMMEDIATE serialises them, so the loser waits
        (15 s busy timeout) and then sees the winner's row. The trigger in the state schema is
        still what protects a writer that never calls this.
        """
        conn.execute('BEGIN IMMEDIATE')
        try:
            yield
        finally:
            if conn.in_transaction:
                # Only reached on a path that returned without committing -- the duplicate-import
                # read. Nothing was written, but holding the lock until the connection closes would
                # stall every other writer for nothing.
                conn.rollback()

    # -- the one writer -----------------------------------------------------------

    def _write_revision(self, conn, entry_id, revision, fields, *, created_by, supersedes):
        document = _document(entry_id, revision, fields, created_at=_now(),
                             created_by=created_by, supersedes=supersedes)
        try:
            conn.execute(
                'INSERT INTO knowledge_entry_revision (entry_id, revision, entry_type, title,'
                ' summary, content_sha256, recommended, created_at, created_by, document_json)'
                ' VALUES (?,?,?,?,?,?,?,?,?,?)',
                (entry_id, revision, document['entry_type'], document['title'],
                 document['summary'], document['content_sha256'],
                 1 if document['recommended'] else 0, document['created_at'],
                 document['created_by'], _canonical(document)))
        except sqlite3.IntegrityError as exc:
            conn.rollback()
            raise KnowledgeLibraryError(409, 'KNOWLEDGE_ENTRY_CONCURRENT_UPDATE',
                                        f'the state database refused the revision: {exc}') from None
        # The index holds the CURRENT revision only, so the previous row for this entry is
        # removed here -- inside the same transaction as the write that replaces it.
        conn.execute('DELETE FROM knowledge_entry_fts WHERE entry_id=?', (entry_id,))
        conn.execute(
            'INSERT INTO knowledge_entry_fts (entry_id, revision, title, summary, body, tags,'
            ' targets) VALUES (?,?,?,?,?,?,?)', _fts_row(document))
        return document

    def _insert_entry_row(self, conn, entry_id, supersedes, created_by):
        """INSERT the entry row, and give a losing racer the same refusal the guard gives.

        The state schema's `knowledge_entry_one_successor` trigger is the last line of defence
        against a fork. When it fires, the writer that lost the race must not surface a bare
        sqlite3.IntegrityError as a 500: it is being told the same thing `_supersedes_guard` would
        have told it, one moment too late -- including WHICH entry holds the claim, because the
        operator's next action is to go read that one. `RAISE(ABORT)` rolls back only the failed
        statement, so the successor is still queryable on this connection.
        """
        try:
            conn.execute(
                'INSERT INTO knowledge_entry (entry_id, supersedes, created_at, created_by)'
                ' VALUES (?,?,?,?)', (entry_id, supersedes, _now(), created_by))
        except sqlite3.IntegrityError as exc:
            if 'at most one successor' not in str(exc):
                raise
            taken = [row['entry_id'] for row in conn.execute(
                'SELECT entry_id FROM knowledge_entry WHERE supersedes=?'
                ' ORDER BY created_at, entry_id', (supersedes,))]
            raise KnowledgeLibraryError(
                409, 'KNOWLEDGE_SUPERSESSION_CONFLICT',
                _superseded_detail(supersedes, taken)) from None

    def create(self, value) -> dict:
        fields = _fields(value, for_revision=False)
        created_by = _text(value['created_by'], 'created_by')
        if created_by == UNKNOWN:
            raise KnowledgeLibraryError(
                400, 'KNOWLEDGE_AUTHOR_REQUIRED',
                'created_by is required: an entry nobody signed cannot be corrected or questioned '
                'later')
        supersedes = value['supersedes']
        entry_id = 'kentry-' + uuid.uuid4().hex
        with closing(self._connect()) as conn:
            with self._write_transaction(conn):
                _supersedes_guard(conn, supersedes)
                self._insert_entry_row(conn, entry_id, supersedes, created_by)
                document = self._write_revision(conn, entry_id, 1, fields,
                                                created_by=created_by, supersedes=supersedes)
                conn.commit()
        return _check({'schemaVersion': WRITE_VERSION,
                       'status': 'KNOWLEDGE_ENTRY', 'stored': True, 'entry': document,
                       'revision': 1, 'claims_not_made': list(CLAIMS_NOT_MADE)},
                      _WRITE_SCHEMA_PATH, 'knowledge entry write', registry=_ref_registry())

    def revise(self, entry_id, value) -> dict:
        fields = _fields(value, for_revision=True)
        created_by = _text(value['created_by'], 'created_by')
        if created_by == UNKNOWN:
            raise KnowledgeLibraryError(400, 'KNOWLEDGE_AUTHOR_REQUIRED',
                                        'created_by is required on every revision')
        expected = value['expected_revision']
        if not isinstance(expected, int) or isinstance(expected, bool) or expected < 1:
            raise KnowledgeLibraryError(
                400, 'KNOWLEDGE_EXPECTED_REVISION_REQUIRED',
                'expected_revision must be the revision this write was prepared against; without '
                'it a second writer silently overwrites the first one\'s correction')
        with closing(self._connect()) as conn:
            entry = conn.execute('SELECT supersedes FROM knowledge_entry WHERE entry_id=?',
                                 (entry_id,)).fetchone()
            if entry is None:
                raise KnowledgeLibraryError(404, 'KNOWLEDGE_ENTRY_NOT_FOUND')
            current = conn.execute(
                'SELECT MAX(revision) AS top FROM knowledge_entry_revision WHERE entry_id=?',
                (entry_id,)).fetchone()['top']
            if current is None:
                raise KnowledgeLibraryError(404, 'KNOWLEDGE_ENTRY_NOT_FOUND')
            if expected != current:
                raise KnowledgeLibraryError(
                    409, 'KNOWLEDGE_ENTRY_REVISION_CONFLICT',
                    f'the entry is at revision {current}, not {expected}; re-read it and write '
                    'against the revision you actually saw')
            document = self._write_revision(conn, entry_id, current + 1, fields,
                                            created_by=created_by, supersedes=entry['supersedes'])
            conn.commit()
        return _check({'schemaVersion': WRITE_VERSION,
                       'status': 'KNOWLEDGE_ENTRY', 'stored': True, 'entry': document,
                       'revision': current + 1, 'claims_not_made': list(CLAIMS_NOT_MADE)},
                      _WRITE_SCHEMA_PATH, 'knowledge entry write', registry=_ref_registry())

    def import_entry(self, value) -> dict:
        fields = _fields(value, for_revision=False)
        imported_by = _text(value['imported_by'], 'imported_by')
        if imported_by == UNKNOWN:
            raise KnowledgeLibraryError(400, 'KNOWLEDGE_AUTHOR_REQUIRED',
                                        'imported_by is required on an import')
        source = fields['source']
        if source['sourceId'] == UNKNOWN or source['version'] == UNKNOWN:
            raise KnowledgeLibraryError(
                400, 'KNOWLEDGE_IMPORT_SOURCE_INCOMPLETE',
                'an import needs source.sourceId and source.version. Without both, a re-import '
                'cannot be told from a new version of the same source -- every import would look '
                'new, and acceptance A4 asks for the opposite')
        entry_id = _import_id(source['sourceId'], source['version'])
        with closing(self._connect()) as conn:
            siblings = [row['entry_id'] for row in conn.execute(
                'SELECT DISTINCT entry_id FROM knowledge_entry_revision WHERE entry_id <> ?'
                ' AND json_extract(document_json, "$.source.sourceId") = ?',
                (entry_id, source['sourceId']))]
            # A sibling from the same source is only "another version" when its version differs.
            # An entry a person typed by hand can carry the same source and version under a
            # different id; calling that VERSIONED would claim a new version exists when the
            # library actually holds two records of one version.
            same_version = [row['entry_id'] for row in conn.execute(
                'SELECT DISTINCT entry_id FROM knowledge_entry_revision WHERE entry_id <> ?'
                ' AND json_extract(document_json, "$.source.sourceId") = ?'
                ' AND json_extract(document_json, "$.source.version") = ?',
                (entry_id, source['sourceId'], source['version']))]
            other_versions = [sibling for sibling in siblings if sibling not in same_version]
            existing = conn.execute(
                'SELECT revision, content_sha256, document_json FROM knowledge_entry_revision'
                ' WHERE entry_id=? ORDER BY revision DESC LIMIT 1', (entry_id,)).fetchone()
            if existing is not None:
                if existing['content_sha256'] != _preview_digest(fields):
                    raise KnowledgeLibraryError(
                        409, 'KNOWLEDGE_IMPORT_VERSION_CONFLICT',
                        f'{source["sourceId"]} version {source["version"]} is already stored with '
                        f'digest {existing["content_sha256"]}, and this document digests to '
                        f'{_preview_digest(fields)}. One version cannot have two contents; correct '
                        'the version pin or import it as a new version')
                document = json.loads(existing['document_json'])
                return _check({
                    'schemaVersion': IMPORT_VERSION,
                    'outcome': 'DUPLICATE',
                    'explanation': (
                        f'no write: {source["sourceId"]} version {source["version"]} is already '
                        f'stored as {entry_id} at revision {existing["revision"]} with the same '
                        'content digest'),
                    'knowledge_entry_id': entry_id,
                    'revision': existing['revision'],
                    'related_entries': siblings,
                    'entry': document,
                    'claims_not_made': list(IMPORT_CLAIMS),
                }, _IMPORT_SCHEMA_PATH, 'knowledge import', registry=_ref_registry())
            supersedes = value['supersedes']
            with self._write_transaction(conn):
                # The same guard `create` runs, including the one it alone used to enforce: an
                # import that named an already-superseded entry forked the chain the UI refused
                # (owner audit 2026-10-26, finding 2).
                _supersedes_guard(conn, supersedes)
                self._insert_entry_row(conn, entry_id, supersedes, imported_by)
                document = self._write_revision(conn, entry_id, 1, fields,
                                                created_by=imported_by, supersedes=supersedes)
                conn.commit()
        outcome = 'VERSIONED' if other_versions else 'CREATED'
        if outcome == 'VERSIONED':
            explanation = (
                f'kept beside {len(other_versions)} existing '
                f'entr{"y" if len(other_versions) == 1 else "ies"} from the same source at other '
                f'versions: {", ".join(other_versions[:5])}')
        elif same_version:
            explanation = (
                f'the library already holds {len(same_version)} '
                f'entr{"y" if len(same_version) == 1 else "ies"} for {source["sourceId"]} '
                f'version {source["version"]} under a different id '
                f'({", ".join(same_version[:5])}); this import adds a second record of that '
                'version rather than replacing one. Revise the existing entry instead if they '
                'are meant to be one')
        else:
            explanation = ('nothing with this source and version was stored; the entry was '
                           'created')
        return _check({
            'schemaVersion': IMPORT_VERSION,
            'outcome': outcome,
            'explanation': explanation,
            'knowledge_entry_id': entry_id,
            'revision': 1,
            'related_entries': siblings,
            'entry': document,
            'claims_not_made': list(IMPORT_CLAIMS),
        }, _IMPORT_SCHEMA_PATH, 'knowledge import', registry=_ref_registry())

    # -- reading ------------------------------------------------------------------

    def detail(self, entry_id) -> dict:
        with closing(self._connect()) as conn:
            entry = conn.execute('SELECT supersedes, created_at, created_by FROM knowledge_entry'
                                 ' WHERE entry_id=?', (entry_id,)).fetchone()
            if entry is None:
                raise KnowledgeLibraryError(404, 'KNOWLEDGE_ENTRY_NOT_FOUND')
            rows = conn.execute(
                'SELECT revision, entry_type, title, content_sha256, recommended, created_at,'
                ' created_by, document_json FROM knowledge_entry_revision WHERE entry_id=?'
                ' ORDER BY revision', (entry_id,)).fetchall()
            superseded_by, _recommended = _statuses(conn)
            recorded = _latest_judgements(conn, entry_id)
            history = _judgement_history(conn, entry_id)
            index = _index_state(conn)
        documents, unreadable = {}, 0
        revisions = []
        for row in rows:
            try:
                document = json.loads(row['document_json'])
            except (TypeError, ValueError):
                unreadable += 1
                document = None
            if document is not None:
                documents[row['revision']] = document
            revisions.append({
                'revision': row['revision'],
                'content_sha256': row['content_sha256'],
                'entry_type': row['entry_type'],
                'title': row['title'],
                'recommended': bool(row['recommended']),
                'created_at': row['created_at'],
                'created_by': row['created_by'],
                'readable': document is not None,
            })
        latest = rows[-1]['revision'] if rows else None
        recommended = max((row['revision'] for row in rows if row['recommended']), default=None)
        # A recorded judgement outranks the flag written with the revision, and it is the only way
        # the recommendation can move BACK: the revision rows are append-only by trigger, so their
        # flags never change. Every other revision stays exactly as stored, which is what keeps a
        # plan that pinned an older one reading the same bytes.
        recommendation = recorded.get('RECOMMENDATION', {}).get(entry_id)
        if recommendation is not None:
            recommended = recommendation['revision']
        source_state = recorded.get('SOURCE_STATE', {}).get(entry_id)
        current = documents.get(latest)
        recommended_document = documents.get(recommended) if recommended is not None else None
        return _check({
            'schemaVersion': READBACK_VERSION,
            'knowledge_entry_id': entry_id,
            'status': 'SUPERSEDED' if entry_id in superseded_by else 'ACTIVE',
            'latest_revision': latest,
            'recommended_revision': recommended,
            'current': current,
            # Rendering the same bytes twice when the two numbers agree is noise, so only a
            # *different* recommended revision carries its document.
            'recommended': (None if recommended_document is None or recommended == latest
                            else recommended_document),
            'superseded_by': superseded_by.get(entry_id),
            # Which of the two possible owners decided `recommended_revision`, said plainly: a
            # reader must be able to tell "recommended when the bytes were written" from "a person
            # moved it here later", and neither is a computed ranking.
            'recommendation_basis': ('recorded-judgement' if recommendation is not None
                                     else ('written-flag' if recommended is not None else None)),
            'recommendation_judgement': recommendation,
            # null means nobody has ever said -- not "the source is fine".
            'source_state': source_state,
            'judgements': history,
            'revisions': revisions,
            'unreadable_count': unreadable,
            'index': index,
            'does_not_say': list(DOES_NOT_SAY),
        }, _READBACK_SCHEMA_PATH, 'knowledge entry readback', registry=_ref_registry())

    def record_judgement(self, entry_id, value) -> dict:
        """Record a later human judgement about an entry (DL-KB-05 D5), then read it back.

        Two kinds share this one writer because they are the same act: RECOMMENDATION moves the
        recommended revision (including back to an older one), SOURCE_STATE marks the source
        INVALID and names what replaces it. Neither writes a revision, so no stored document,
        digest or timestamp moves -- an entry pinned to revision 2 by an older plan keeps reading
        exactly those bytes. `recorded_at` is stamped here rather than accepted from the caller:
        a judgement about who decided what is not something the client gets to date.
        """
        kind = value.get('kind')
        if kind not in JUDGEMENT_KINDS:
            raise KnowledgeLibraryError(
                400, 'KNOWLEDGE_JUDGEMENT_KIND_INVALID',
                f'kind must be one of {list(JUDGEMENT_KINDS)} (got {kind!r})')
        if value.get('recorded_by_kind') != 'HUMAN':
            raise KnowledgeLibraryError(
                400, 'KNOWLEDGE_HUMAN_JUDGEMENT_REQUIRED',
                'an agent may not move a recommendation or declare a source dead: '
                "recorded_by_kind must be 'HUMAN' with a named person in recorded_by "
                f"(got {value.get('recorded_by_kind')!r})")
        recorded_by = value.get('recorded_by')
        if not isinstance(recorded_by, str) or not recorded_by.strip():
            raise KnowledgeLibraryError(
                400, 'RECORDED_BY_REQUIRED',
                'recorded_by must name the person who made the judgement')
        reason = value.get('reason')
        if not isinstance(reason, str) or not reason.strip():
            raise KnowledgeLibraryError(
                400, 'REASON_REQUIRED',
                'a judgement without a stated reason is a ranking wearing a costume; put the '
                'why in reason')
        revision = value.get('revision')
        state_value = value.get('value')
        replaced_by = value.get('replaced_by')
        if kind == 'RECOMMENDATION':
            if not isinstance(revision, int) or isinstance(revision, bool) or revision < 1:
                raise KnowledgeLibraryError(
                    400, 'KNOWLEDGE_JUDGEMENT_REVISION_REQUIRED',
                    f'a RECOMMENDATION judgement names the revision it recommends, got {revision!r}')
            if state_value not in (None, RECOMMENDATION_VALUE):
                raise KnowledgeLibraryError(
                    400, 'KNOWLEDGE_JUDGEMENT_VALUE_INVALID',
                    f'a RECOMMENDATION judgement carries value={RECOMMENDATION_VALUE!r} or null, '
                    f'got {state_value!r}')
            state_value = RECOMMENDATION_VALUE
            if replaced_by is not None:
                raise KnowledgeLibraryError(
                    400, 'KNOWLEDGE_JUDGEMENT_FIELD_NOT_APPLICABLE',
                    'replaced_by belongs to a SOURCE_STATE judgement, not a recommendation')
        else:
            if state_value not in SOURCE_STATES:
                raise KnowledgeLibraryError(
                    400, 'KNOWLEDGE_JUDGEMENT_VALUE_INVALID',
                    f'a SOURCE_STATE judgement carries value in {list(SOURCE_STATES)}, '
                    f'got {state_value!r}')
            if revision is not None:
                raise KnowledgeLibraryError(
                    400, 'KNOWLEDGE_JUDGEMENT_FIELD_NOT_APPLICABLE',
                    'revision belongs to a RECOMMENDATION judgement; a source judgement is about '
                    'where the content came from, not which revision is current')
            if state_value == 'INVALID':
                if not isinstance(replaced_by, str) or _ID.match(replaced_by) is None:
                    raise KnowledgeLibraryError(
                        400, 'KNOWLEDGE_SOURCE_REPLACEMENT_REQUIRED',
                        'marking a source INVALID must name a knowledge entry id in replaced_by, '
                        f'or the entry has to be re-sourced instead (got {replaced_by!r})')
                if replaced_by == entry_id:
                    raise KnowledgeLibraryError(
                        400, 'KNOWLEDGE_SOURCE_REPLACEMENT_SELF',
                        'an entry cannot replace itself: the source is either re-sourced from '
                        'outside or replaced by another entry')
        with closing(self._connect()) as conn:
            if conn.execute('SELECT 1 FROM knowledge_entry WHERE entry_id=?',
                            (entry_id,)).fetchone() is None:
                raise KnowledgeLibraryError(404, 'KNOWLEDGE_ENTRY_NOT_FOUND')
            if kind == 'RECOMMENDATION' and conn.execute(
                    'SELECT 1 FROM knowledge_entry_revision WHERE entry_id=? AND revision=?',
                    (entry_id, revision)).fetchone() is None:
                raise KnowledgeLibraryError(
                    404, 'KNOWLEDGE_REVISION_NOT_FOUND',
                    f'entry {entry_id!r} has no revision {revision}; a judgement cannot recommend '
                    'bytes that were never stored')
            if (kind == 'SOURCE_STATE' and state_value == 'INVALID' and conn.execute(
                    'SELECT 1 FROM knowledge_entry WHERE entry_id=?', (replaced_by,)).fetchone()
                    is None):
                raise KnowledgeLibraryError(
                    404, 'KNOWLEDGE_SOURCE_REPLACEMENT_UNKNOWN',
                    f'replaced_by {replaced_by!r} is not an entry this library holds; naming a '
                    'replacement the reader cannot open is not a replacement')
            current = _latest_judgements(conn, entry_id).get(kind, {}).get(entry_id)
            if current and (current['value'] == state_value and current['revision'] == revision
                            and (current['replaced_by'] or '') == (replaced_by or '')
                            and current['recorded_by'] == recorded_by.strip()
                            and current['reason'] == reason.strip()):
                # The same judgement sent twice is one judgement. Replaying it must not stack a
                # second row, or a double click would read as a re-decision.
                return self.detail(entry_id)
            conn.execute(
                'INSERT INTO knowledge_judgement (judgement_id, entry_id, kind, revision, value,'
                ' replaced_by, reason, recorded_by, recorded_at) VALUES (?,?,?,?,?,?,?,?,?)',
                ('kjudge-' + uuid.uuid4().hex, entry_id, kind, revision, state_value,
                 replaced_by, reason.strip(), recorded_by.strip(), _now()))
            conn.commit()
        return self.detail(entry_id)

    def search(self, *, query=None, entry_type=None, domain=None, task=None, target=None,
               offset=0, limit=DEFAULT_LIMIT) -> dict:
        if entry_type is not None and entry_type not in ENTRY_TYPES:
            # A typo in a filter must not come back as "this library has no such entries": the
            # empty answer would be true and misleading at the same time.
            raise KnowledgeLibraryError(400, 'KNOWLEDGE_TYPE_INVALID',
                                        f'entry_type filter must be one of {ENTRY_TYPES}; '
                                        f'got {entry_type!r}')
        for name, value in (('domain', domain), ('task', task), ('target', target)):
            if value is not None and (not isinstance(value, str) or not value.strip()):
                raise KnowledgeLibraryError(400, 'KNOWLEDGE_FILTER_MALFORMED',
                                            f'{name} must be a single non-empty filter value')
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise KnowledgeLibraryError(400, 'KNOWLEDGE_OFFSET_INVALID', 'offset must be >= 0')
        if not isinstance(limit, int) or isinstance(limit, bool) or not 1 <= limit <= MAX_LIMIT:
            raise KnowledgeLibraryError(400, 'KNOWLEDGE_LIMIT_INVALID',
                                        f'limit must be between 1 and {MAX_LIMIT}')
        if query is not None and len(query) > MAX_QUERY:
            # MAX_QUERY was declared at module scope and read by nothing, so the bound existed
            # only in the source text: a caller could paste a document as a query and this
            # method would `_TERM.findall` it and contains-scan every field of every stored
            # revision for it. Refusing is the honest way to make the declared number true;
            # silently truncating the query would answer a question the caller did not ask.
            raise KnowledgeLibraryError(400, 'KNOWLEDGE_QUERY_TOO_LONG',
                                        f'query must be at most {MAX_QUERY} characters, '
                                        f'got {len(query)}')
        terms = _TERM.findall(query or '')[:8]
        with closing(self._connect()) as conn:
            documents, _unreadable = _readings(conn)
            superseded_by, recommended = _statuses(conn)
            index = _index_state(conn)
            fts_hits = {term: set(_fts_matches(conn, term)) for term in terms}
        filtered = []
        for entry_id, document in documents.items():
            if entry_type is not None and document['entry_type'] != entry_type:
                continue
            if domain is not None and domain not in document['domain_tags']:
                continue
            if task is not None and task not in document['task_tags']:
                continue
            if target is not None and target not in document['target_tools']:
                continue
            filtered.append((entry_id, document))

        # Which mechanisms actually select rows. A term of three characters or more is gated by
        # the FTS5 trigram index; anything shorter cannot be answered by it at all. A term the
        # index answered with nothing runs the substring fallback for that term, because a
        # derived index with a missing row must not hide every entry from a query.
        indexed = {term for term in terms if len(term) >= 3 and fts_hits[term]}
        scanned = [term for term in terms if term not in indexed]
        used = set()
        if any(len(term) >= 3 for term in terms):
            # Consulted even when it answered nothing: "the index has no row for this term" and
            # "this term is too short to ask" are different states and the caller sees which.
            used.add('TRIGRAM')
        if scanned:
            used.add('SHORT_FALLBACK')
        strategy = ('MIXED' if len(used) > 1 else used.pop()) if used else 'BROWSE'

        rows = []
        if terms:
            for entry_id, document in filtered:
                if any(entry_id not in fts_hits[term] for term in indexed):
                    continue
                fields, hits = [], set()
                for term in terms:
                    # The canonical bytes still decide: an index row that survives a correction
                    # must not resurrect a term the current revision no longer contains.
                    for field in SEARCH_FIELDS:
                        if _contains(_field_text(document, field), term):
                            fields.append(field)
                            hits.add(term)
                if len(hits) != len(terms):
                    continue
                relevance = (8 * ('title' in fields) + 4 * ('summary' in fields)
                             + 2 * ('domain_tags' in fields or 'task_tags' in fields)
                             + 2 * ('target_tools' in fields) + 1 * ('body' in fields))
                rows.append((entry_id, document, fields, hits, relevance))
            rows.sort(key=lambda item: (-item[4], item[1]['title'], item[0]))
        else:
            rows = [(entry_id, document, [], set(), 0) for entry_id, document in filtered]
            rows.sort(key=lambda item: (item[1]['created_at'], item[1]['title'], item[0]),
                      reverse=True)

        total = len(rows)
        page = rows[offset:offset + limit]
        entries = [self._row(entry_id, document, fields, hits, superseded_by, recommended)
                   for entry_id, document, fields, hits, _ in page]
        explanation = None
        if not rows:
            explanation = self._explanation(terms, documents,
                                            {'type': entry_type, 'domain': domain,
                                             'task': task, 'target': target})
        return _check({
            'schemaVersion': LIBRARY_VERSION,
            'query': query,
            'filters': {'type': entry_type, 'domain': domain, 'task': task, 'target': target},
            # The six type names travel with the answer instead of being copied into the
            # view: TYPE_LABELS is the one table, and an offline page that never read it
            # must show no options rather than a hand-typed second vocabulary.
            'entryTypes': [{'value': value, 'label': TYPE_LABELS[value]}
                           for value in ENTRY_TYPES],
            # The three licence states travel for the same reason: the write form must not
            # offer a word the service would refuse, nor hide one it accepts.
            'licenseStates': list(LICENSE_STATES),
            'strategy': strategy,
            'matched_terms': sorted(terms),
            'total': total,
            'offset': offset,
            'limit': limit,
            'returned': len(entries),
            'next_offset': (offset + len(entries)) if offset + len(entries) < total else None,
            'entries': entries,
            'explanation': explanation,
            'index': index,
            'does_not_say': list(DOES_NOT_SAY),
        }, _LIBRARY_SCHEMA_PATH, 'knowledge library readback')

    def _row(self, entry_id, document, fields, hits, superseded_by, recommended):
        latest = document['revision']
        recommended_revision = recommended.get(entry_id)
        return {
            'knowledge_entry_id': entry_id,
            'revision': latest,
            'latest_revision': latest,
            'recommended_revision': recommended_revision,
            'recommended_is_latest': recommended_revision == latest,
            'entry_type': document['entry_type'],
            'title': document['title'],
            'summary': document['summary'],
            'domain_tags': list(document['domain_tags']),
            'task_tags': list(document['task_tags']),
            'target_tools': list(document['target_tools']),
            'status': 'SUPERSEDED' if entry_id in superseded_by else 'ACTIVE',
            'content_sha256': document['content_sha256'],
            'updated_at': document['created_at'],
            'license': document['source']['license'],
            'license_status': document['source']['licenseStatus'],
            'source_id': document['source']['sourceId'],
            'source_version': document['source']['version'],
            'matched_fields': list(dict.fromkeys(fields)),
            'matched_terms': sorted(hits),
        }

    def _explanation(self, terms, documents, filters):
        active = [f'{name}={value}' for name, value in filters.items() if value is not None]
        if not documents:
            return ('库中还没有任何条目。可以用「新增」写一条，或从文件「导入」一份已有的条目；'
                    '本页不会为了填满列表而编造示例条目。')
        if terms:
            head = f'没有命中「{" ".join(terms)}」的条目。'
            if active:
                head += f'当前筛选：{"、".join(active)}。'
            return (head + f'库中现有 {len(documents)} 条；检索只匹配标题、摘要、正文、'
                    '领域/任务标签和目标工具，不做近义词扩写，也不推荐未命中的相关条目。')
        if active:
            return (f'当前筛选（{"、".join(active)}）下没有条目；库中共有 {len(documents)} 条，'
                    '去掉筛选可以重新浏览。本页不会推荐"相近"的条目来填空。')
        return (f'当前没有可显示的条目；库中共有 {len(documents)} 条。清空搜索词可以重新浏览，'
                '本页不推荐"相近"的条目来填空。')

    # -- index maintenance ---------------------------------------------------------

    def rebuild_index(self) -> dict:
        """Repopulate the derived index from the one canonical table.

        This is the whole claim that the index is rebuildable: it deletes every derived row and
        reconstructs them from ``knowledge_entry_revision``. It is exercised by a test that
        clears the index first and then asserts the strategy the search reports moves back from
        the fallback to the index -- a rebuild nobody can observe is indistinguishable from a
        no-op.
        """
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT r.entry_id, r.revision, r.document_json FROM knowledge_entry_revision r'
                ' WHERE r.revision = (SELECT MAX(x.revision) FROM knowledge_entry_revision x'
                '                     WHERE x.entry_id = r.entry_id)').fetchall()
            conn.execute('DELETE FROM knowledge_entry_fts')
            indexed = 0
            for row in rows:
                try:
                    document = json.loads(row['document_json'])
                except (TypeError, ValueError):
                    continue
                conn.execute(
                    'INSERT INTO knowledge_entry_fts (entry_id, revision, title, summary, body,'
                    ' tags, targets) VALUES (?,?,?,?,?,?,?)', _fts_row(document))
                indexed += 1
            rebuilt_at = _now()
            conn.execute(
                'INSERT INTO knowledge_index_state (name, rebuilt_at, rows) VALUES (?,?,?)'
                ' ON CONFLICT(name) DO UPDATE SET rebuilt_at=excluded.rebuilt_at,'
                ' rows=excluded.rows', ('knowledge_entry_fts', rebuilt_at, indexed))
            conn.commit()
            index = _index_state(conn)
        return _check({'schemaVersion': INDEX_VERSION, 'status': 'KNOWLEDGE_INDEX_REBUILT',
                       'rebuilt_at': rebuilt_at, 'indexed': indexed, 'index': index,
                       'does_not_say': ['重建索引不修改任何条目；它只重建检索用的派生表']},
                      _INDEX_SCHEMA_PATH, 'knowledge index rebuild')


def _preview_digest(fields):
    """The digest an import would store, computed without writing a row.

    Needed before the row exists: the duplicate check compares the stored digest with the one this
    document *would* have, and building a throwaway document with a placeholder id is how that is
    answered without a second definition of the digest.
    """
    document = {key: fields[key] for key in CONTENT_FIELDS}
    return _digest(document)
