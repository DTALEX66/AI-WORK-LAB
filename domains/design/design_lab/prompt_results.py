# SPDX-License-Identifier: MIT
"""Storing the prompt documents this product produces, and the human acceptance over one of them.

Before this module the two prompt routes assembled a complete, versioned document and dropped it.
``apps/workbench/shell.ts`` said so on screen ("服务端不持久化这份文档"), and the acceptance test for
the standalone chain could only show that several routes answered on one server -- it could not show
that one professional artifact travelled from generation through review into a stored record, because
after the response body scrolled away there was nothing left to travel.

What a row is: one document this service produced, kept under the id the document itself carries,
bound to the stored records it was assembled from (brief version, direction version, asset digest)
and to the model-selection revision in force at that moment. What it is not:

* a run record. ``executed`` is stored as the constant ``0`` and the table refuses anything else --
  nothing here loads a model, and this repository has no outbound transport;
* a verdict. Acceptance is a separate append-only row naming a human; composing a prompt has never
  meant anybody agreed to use it, and the composition's own ``claims_not_made`` says so.

Reviews quote the ``content_sha256`` they were signed against. Recomposing after the brief changed
produces a different ``result_id`` and a different digest, so an earlier acceptance stops describing
the current document without anybody having to rewrite it -- the invalidation the audit asked for is
a consequence of the identity rule, not a flag someone has to remember to clear.

Append-only, like the model-selection, research, rights and jury stores: ``revision`` is per project,
"current" is MAX(revision) computed at read time, and the table's own triggers refuse UPDATE and
DELETE. There is no ``active`` column, because this repository's ACTIVE-version invariant says a
mutable current-marker is how a second truth source gets born.
"""
from __future__ import annotations

from contextlib import closing
import hashlib
import json
from pathlib import Path
import re
import sqlite3

from .assurance import utc_now_rfc3339
from .interop import (InteropError, load_schema, resource_registry, schema_errors)
from .prompt_intelligence import (COMPOSITION_SCHEMA_PATH, REVERSAL_SCHEMA_PATH,
                                  COMPOSITION_VERSION, REVERSAL_VERSION)
from .runtime.state_resources import repo_resource, state_schema

RESULT_VERSION = 'design-lab/prompt-result/v1'
READBACK_VERSION = 'design-lab/prompt-result-readback/v1'
REVIEW_VERSION = 'design-lab/prompt-result-review/v1'
# The list is bounded the way the knowledge and assistance-plan lists are: a default page, an
# explicit maximum, and an envelope that says whether more exists. `reviews` is deliberately NOT
# paginated -- truncating the acceptance history would hide decisions, which is the one thing a
# Human Gate readback must never do.
PROMPT_RESULT_LIMIT = 100
MAX_PROMPT_RESULT_LIMIT = 200
RESULT_SCHEMA_PATH = repo_resource('schemas/prompt-result-v1.schema.json')
_READBACK_SCHEMA_PATH = repo_resource('schemas/prompt-result-readback-v1.schema.json')
_REVIEW_SCHEMA_PATH = repo_resource('schemas/prompt-result-review-v1.schema.json')
_STATE = state_schema('design-lab-state-prompt-results-v1.sql')

#: The readback envelope references the two prompt contracts instead of restating them, so the
#: store-side check needs them resolvable offline. Paths come from the module that owns them --
#: repeating the literals here would be a second pointer able to drift from the contract the
#: production path already validates against.
_REFERENCED_SCHEMAS = (COMPOSITION_SCHEMA_PATH, REVERSAL_SCHEMA_PATH, _REVIEW_SCHEMA_PATH)
_registry = None


def _ref_registry():
    global _registry
    if _registry is None:
        pairs = {}
        for path in _REFERENCED_SCHEMAS:
            try:
                document = load_schema(path)
            except (InteropError, OSError) as exc:
                raise PromptResultError(500, 'PROMPT_RESULT_CONTRACT_UNREADABLE',
                                        f'cannot load {path.name} for $ref resolution: {exc}') from None
            identifier = document.get('$id')
            if not isinstance(identifier, str):
                raise PromptResultError(
                    500, 'PROMPT_RESULT_CONTRACT_UNREADABLE',
                    f'{path.name} carries no $id, so a $ref into it cannot be resolved offline')
            pairs[identifier] = document
        _registry = resource_registry(pairs)
    return _registry

#: The two documents this store accepts, and how each one identifies itself.
_KINDS = {COMPOSITION_VERSION: ('COMPOSITION', 'composition_id'),
          REVERSAL_VERSION: ('REVERSAL', 'reversal_id')}
DECISIONS = ('ACCEPTED', 'DECLINED')
REVIEWER_KIND_HUMAN = 'human'
#: Review states a reader may see, kept apart on purpose: UNREVIEWED means nobody signed anything
#: about this document, NOT_CURRENT means a signature exists but quotes a different document.
ACCEPTANCE_STATES = ('UNREVIEWED', 'ACCEPTED', 'DECLINED', 'NOT_CURRENT')
RFC3339_PATTERN = re.compile(r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$')

CLAIMS_NOT_MADE = (
    'a stored result is not a run: no model was loaded, no inference happened and nothing was sent',
    'storing a prompt does not accept it; acceptance is a separate row naming a human',
    'the stored sources are what was on file when this document was assembled, not what is on file now',
    'an acceptance quotes the content_sha256 it judged; it says nothing about a later document',
)


class PromptResultError(ValueError):
    """A store or review refusal, carrying the status and code the route answers with."""

    def __init__(self, status, code, detail=None):
        super().__init__(detail or code)
        self.status = status
        self.code = code
        self.detail = detail


def connect(db_path, *, project_root=None) -> sqlite3.Connection:
    """Open the shared state database with the prompt-result tables present."""
    from .runtime.asset_store import connect as connect_assets

    connection = connect_assets(db_path, project_root=project_root)
    connection.row_factory = sqlite3.Row
    connection.executescript(_STATE.read_text(encoding='utf-8'))
    connection.commit()
    return connection


def _state_of(latest, content_sha256):
    """The only place a stored acceptance is judged.

    ``readback`` and the project roll-up both call this, so the desk's front page cannot count a
    signature as current while the detail page says it describes other bytes -- and vice versa.
    """
    if latest is None:
        return 'UNREVIEWED'
    if latest['content_sha256'] != content_sha256:
        return 'NOT_CURRENT'
    return latest['decision']


def _canonical(document) -> str:
    return json.dumps(document, ensure_ascii=False, sort_keys=True)


def _digest(document) -> str:
    return 'sha256:' + hashlib.sha256(
        _canonical(document).encode('utf-8')).hexdigest()


def _check(document, path, label, *, registry=None):
    try:
        problems = schema_errors(load_schema(path), document, registry=registry)
    except (InteropError, OSError) as exc:
        raise PromptResultError(500, 'PROMPT_RESULT_CONTRACT_UNREADABLE',
                                f'cannot load {path.name} for {label}: {exc}') from None
    if problems:
        raise PromptResultError(500, 'PROMPT_RESULT_CONTRACT_VIOLATION', problems)
    return document


def _source_columns(document, kind):
    """Pull the identity columns out of the document, refusing a document that cannot say so.

    The columns are not decoration: a row whose brief version drifted from its own document would
    let a reader index one thing and quote another. ``_locked_columns`` below re-derives them on the
    read path and the tests compare both sides.
    """
    model = document.get('model') or {}
    selection = model.get('selected') or {}
    if kind == 'COMPOSITION':
        # `observed` is the per-section provenance list, and every entry is tagged
        # ``kind: 'stored'`` -- the record it names is identified by which id key it carries, not by
        # that tag. Matching on the tag would silently find nothing and store a source-less row.
        brief = next((entry for entry in document.get('observed') or []
                      if 'brief_id' in entry), {})
        direction = next((entry for entry in document.get('observed') or []
                          if 'direction_id' in entry), {})
        return {'target': document['target'], 'brief_id': brief.get('brief_id'),
                'brief_version': brief.get('version'),
                'brief_spec_sha256': brief.get('spec_sha256'),
                'direction_id': direction.get('direction_id'),
                'direction_version': direction.get('version'),
                'asset_id': None, 'asset_sha256': None,
                'selection_revision': selection.get('revision')}
    asset = document.get('asset') or {}
    return {'target': None, 'brief_id': None, 'brief_version': None,
            'brief_spec_sha256': None, 'direction_id': None, 'direction_version': None,
            'asset_id': asset.get('id'), 'asset_sha256': asset.get('sha256'),
            'selection_revision': selection.get('revision')}


class PromptResults:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    def _connect(self):
        return connect(self.paths.database_path(self.service.database),
                       project_root=self.paths.project_root)

    def _check_project(self, project_id):
        if self.service.get_project(project_id) is None:
            raise PromptResultError(404, 'PROJECT_NOT_FOUND')

    # -- writing ------------------------------------------------------------------

    def store(self, project_id, document) -> dict:
        """Keep one produced prompt document, or replay the identical one."""
        self._check_project(project_id)
        if not isinstance(document, dict):
            raise PromptResultError(400, 'PROMPT_RESULT_DOCUMENT_MALFORMED',
                                    'the document must be one prompt object')
        version = document.get('schemaVersion')
        if version not in _KINDS:
            raise PromptResultError(
                400, 'PROMPT_RESULT_UNKNOWN_VERSION',
                f'{version!r} is not a document this store keeps; it must be '
                f'{COMPOSITION_VERSION!r} or {REVERSAL_VERSION!r}')
        kind, id_field = _KINDS[version]
        result_id = document.get(id_field)
        if not isinstance(result_id, str) or not result_id.strip():
            raise PromptResultError(400, 'PROMPT_RESULT_ID_MISSING',
                                    f'{id_field} is absent, so this document cannot be addressed '
                                    'later; storing an unaddressable result is the same as not '
                                    'storing it')
        if document.get('project_id') != project_id:
            raise PromptResultError(400, 'PROMPT_RESULT_PROJECT_MISMATCH',
                                   'the document names a different project than the one storing it')
        if (document.get('model') or {}).get('executed') is not False:
            raise PromptResultError(
                400, 'PROMPT_RESULT_EXECUTED_ASSERTED',
                'model.executed must be false: this repository runs no model and sends nothing, so a '
                'document claiming inference cannot be stored')
        columns = _source_columns(document, kind)
        if kind == 'COMPOSITION' and not columns['brief_id']:
            raise PromptResultError(400, 'PROMPT_RESULT_SOURCE_UNNAMED',
                                    'a composition must carry the brief it was assembled from; a '
                                    'prompt with no named source cannot be re-checked later')
        if kind == 'REVERSAL' and not (columns['asset_id'] and columns['asset_sha256']):
            raise PromptResultError(400, 'PROMPT_RESULT_SOURCE_UNNAMED',
                                    'a reversal must name the asset and its digest for the same '
                                    'reason')

        record = _check({
            'schemaVersion': RESULT_VERSION,
            'project_id': project_id,
            'result_id': result_id,
            'kind': kind,
            'document_version': version,
            'content_sha256': _digest(document),
            'created_at': _now(),
            'document': document,
            'claims_not_made': list(CLAIMS_NOT_MADE),
        }, RESULT_SCHEMA_PATH, 'stored result')

        with closing(self._connect()) as conn:
            existing = conn.execute(
                'SELECT revision, document_json FROM prompt_result WHERE project_id=? AND'
                ' result_id=?', (project_id, result_id)).fetchone()
            if existing is not None:
                stored = json.loads(existing['document_json'])['document']
                if _digest(stored) != record['content_sha256']:
                    # The id is a digest over the inputs that produced it, so an identical id with
                    # different bytes is not a re-run -- it is two documents claiming to be one.
                    raise PromptResultError(
                        409, 'PROMPT_RESULT_ID_COLLISION',
                        f'{result_id} is stored with different content; the id is derived from the '
                        'sources, so this means the emitter and the digest disagree')
                return {'status': 'PROMPT_RESULT', 'stored': True, 'replayed': True,
                        'revision': existing['revision'],
                        'result_id': result_id, 'kind': kind,
                        'content_sha256': record['content_sha256'],
                        'claims_not_made': list(CLAIMS_NOT_MADE)}
            current = conn.execute(
                'SELECT MAX(revision) AS top FROM prompt_result WHERE project_id=?',
                (project_id,)).fetchone()['top']
            revision = 0 if current is None else current
            try:
                conn.execute(
                    'INSERT INTO prompt_result (project_id, revision, result_id, kind,'
                    ' document_version, content_sha256, target, brief_id, brief_version,'
                    ' brief_spec_sha256, direction_id, direction_version, asset_id, asset_sha256,'
                    ' selection_revision, executed, created_at, document_json) VALUES'
                    ' (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,0,?,?)',
                    (project_id, revision + 1, result_id, kind, version,
                     record['content_sha256'], columns['target'], columns['brief_id'],
                     columns['brief_version'], columns['brief_spec_sha256'],
                     columns['direction_id'], columns['direction_version'],
                     columns['asset_id'], columns['asset_sha256'],
                     columns['selection_revision'], record['created_at'], _canonical(record)))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise PromptResultError(409, 'PROMPT_RESULT_CONCURRENT_UPDATE',
                                        f'{type(exc).__name__}: {exc}') from None
        return {'status': 'PROMPT_RESULT', 'stored': True, 'replayed': False,
                'revision': revision + 1, 'result_id': result_id, 'kind': kind,
                'content_sha256': record['content_sha256'],
                'claims_not_made': list(CLAIMS_NOT_MADE)}

    def review(self, project_id, *, result_id, decision, reviewer, reviewer_kind, reviewed_at,
               note=None):
        """Append one human acceptance or refusal of a stored result, quoting its digest."""
        self._check_project(project_id)
        if decision not in DECISIONS:
            raise PromptResultError(400, 'INVALID_DECISION',
                                    f'decision must be one of {", ".join(DECISIONS)}')
        if reviewer_kind != REVIEWER_KIND_HUMAN:
            raise PromptResultError(
                400, 'PROMPT_REVIEW_HUMAN_REQUIRED',
                'a prompt result is accepted or refused by a named human: reviewer_kind must be '
                f'{REVIEWER_KIND_HUMAN!r} (got {reviewer_kind!r}). Owner ruling 2026-10-21 keeps '
                'local acceptance human-only as well as the outbound approval, so no agent signature '
                'is stored here at all')
        if not isinstance(reviewer, str) or not reviewer.strip():
            raise PromptResultError(400, 'REVIEWER_REQUIRED',
                                    'an acceptance must say who signed it; an unattributed verdict '
                                    'is not evidence anybody reviewed anything')
        if not isinstance(reviewed_at, str) or RFC3339_PATTERN.match(reviewed_at) is None:
            raise PromptResultError(400, 'INVALID_REVIEWED_AT',
                                    'reviewed_at must be an RFC3339 date-time with an explicit '
                                    'UTC offset')
        with closing(self._connect()) as conn:
            row = conn.execute(
                'SELECT content_sha256 FROM prompt_result WHERE project_id=? AND result_id=?',
                (project_id, result_id)).fetchone()
            if row is None:
                raise PromptResultError(
                    404, 'PROMPT_RESULT_NOT_STORED',
                    f'{result_id} is not a stored result of this project; a review can only be about '
                    'a document this service actually produced and kept')
            current = conn.execute(
                'SELECT MAX(review_revision) AS top FROM prompt_result_review WHERE project_id=?',
                (project_id,)).fetchone()['top']
            revision = 0 if current is None else current
            record = _check({
                'schemaVersion': REVIEW_VERSION,
                'project_id': project_id,
                'review_revision': revision + 1,
                'result_id': result_id,
                'content_sha256': row['content_sha256'],
                'decision': decision,
                'reviewer': reviewer.strip(),
                'reviewer_kind': reviewer_kind,
                'reviewed_at': reviewed_at,
                'note': note,
                'claims_not_made': [
                    'this review judges the document whose content_sha256 is quoted here, and no '
                    'other document',
                    'a review is local acceptance; it does not export anything and does not approve '
                    'a KnowledgeCandidate for sending',
                ],
            }, _REVIEW_SCHEMA_PATH, 'prompt review')
            try:
                conn.execute(
                    'INSERT INTO prompt_result_review (project_id, review_revision, result_id,'
                    ' content_sha256, decision, reviewer, reviewer_kind, reviewed_at, note,'
                    ' document_json) VALUES (?,?,?,?,?,?,?,?,?,?)',
                    (project_id, revision + 1, result_id, row['content_sha256'], decision,
                     record['reviewer'], reviewer_kind, reviewed_at, note, _canonical(record)))
                conn.commit()
            except sqlite3.IntegrityError as exc:
                conn.rollback()
                raise PromptResultError(409, 'PROMPT_REVIEW_CONCURRENT_UPDATE',
                                        f'the state database refused the review: {exc}') from None
        return {'status': 'PROMPT_RESULT_REVIEW', 'review': record,
                'revision': revision + 1, 'claims_not_made': list(record['claims_not_made'])}

    # -- reading ------------------------------------------------------------------

    def readback(self, project_id, offset=0, limit=PROMPT_RESULT_LIMIT) -> dict:
        """One page of the stored results, with the acceptance that still describes them.

        Counts (`result_count`, `unreadable_count`, `accepted_count`) and the `newest`/`state`
        verdict are computed over the WHOLE row set before any slicing, so paging a list can never
        turn a project that produced 400 prompts into one that reads as if it produced 100.
        """
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise PromptResultError(400, 'PROMPT_RESULT_OFFSET_INVALID',
                                    f'offset must be an integer >= 0, got {offset!r}')
        if (not isinstance(limit, int) or isinstance(limit, bool)
                or not 1 <= limit <= MAX_PROMPT_RESULT_LIMIT):
            raise PromptResultError(
                400, 'PROMPT_RESULT_LIMIT_INVALID',
                f'limit must be an integer between 1 and {MAX_PROMPT_RESULT_LIMIT}, got {limit!r}')
        self._check_project(project_id)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT revision, result_id, kind, document_version, content_sha256, target,'
                ' brief_id, brief_version, direction_id, direction_version, asset_id,'
                ' asset_sha256, selection_revision, executed, document_json FROM prompt_result'
                ' WHERE project_id=? ORDER BY revision', (project_id,)).fetchall()
            reviews = [json.loads(row['document_json']) for row in conn.execute(
                'SELECT document_json FROM prompt_result_review WHERE project_id=?'
                ' ORDER BY review_revision', (project_id,)).fetchall()]
        unreadable = 0
        results = []
        for row in rows:
            try:
                record = json.loads(row['document_json'])
            except (TypeError, ValueError):
                unreadable += 1
                continue
            latest = next((review for review in reversed(reviews)
                           if review['result_id'] == row['result_id']), None)
            state = _state_of(latest, row['content_sha256'])
            # The columns are a restatement of the document; say so loudly instead of preferring
            # whichever one is easier to read.
            columns_match = _source_columns(record['document'], row['kind'])
            results.append({
                'revision': row['revision'],
                'result_id': row['result_id'],
                'kind': row['kind'],
                'document_version': row['document_version'],
                'content_sha256': row['content_sha256'],
                'executed': bool(row['executed']),
                'created_at': record['created_at'],
                'document': record['document'],
                'review_state': state,
                'review': latest if state in DECISIONS else None,
                'columns_match_document': (
                    columns_match['brief_id'] == row['brief_id']
                    and columns_match['asset_id'] == row['asset_id']
                    and columns_match['target'] == row['target']
                    and columns_match['selection_revision'] == row['selection_revision']),
            })
        newest = results[-1] if results else None
        accepted = [item for item in results if item['review_state'] == 'ACCEPTED']
        # `state` describes the ROWS, not the readable subset: a project whose only row cannot be
        # parsed still produced a prompt, so it must not read as NONE. `unreadable_count` says which
        # of the two it is, and the contract below refuses NONE together with a nonzero count.
        state = ('NONE' if not rows
                 else newest['review_state'] if newest is not None
                 else 'UNREVIEWED')
        # Sliced only after every count and verdict above has been taken from the full set.
        page = results[offset:offset + limit]
        following = offset + len(page)
        truncated = following < len(results)
        return _check({
            'schemaVersion': READBACK_VERSION,
            'project_id': project_id,
            'state': state,
            'result_count': len(rows),
            'unreadable_count': unreadable,
            'accepted_count': len(accepted),
            'newest': newest,
            'total_readable': len(results),
            'offset': offset,
            'limit': limit,
            'returned': len(page),
            'truncated': truncated,
            'next_offset': following if truncated else None,
            'results': page,
            'reviews': reviews,
            'review_state_vocabulary': list(ACCEPTANCE_STATES),
            'decision_vocabulary': list(DECISIONS),
            'claims_not_made': list(CLAIMS_NOT_MADE),
            'does_not_say': [
                'NONE 是这台服务没产过提示词；UNREVIEWED 是产过但没人签过。两件事不能混为一谈。',
                'ACCEPTED 只说明有人对引用的那份 content_sha256 点过头，不说明它被导出、被发送或被'
                '任何模型执行过。',
                'NOT_CURRENT 表示存在一份签名，但它签的是另一份字节；旧签名不会被改写，只是不再描述现在。',
                'results 是这一页，不是全部：result_count 数的是数据库行（含解析不了的），'
                'total_readable 数的是能读出来的全部，returned/truncated/next_offset 说这一页占其中多少。'
                '把列表翻页不代表评审历史被截——reviews 永远是全量，因为截断签收记录就是隐藏决定。',
            ],
        }, _READBACK_SCHEMA_PATH, 'prompt-result readback', registry=_ref_registry())

    def pending_counts(self, project_id) -> dict:
        """How many stored results no signature currently describes, without reading the documents.

        Deliberately cheaper than :meth:`readback`: the judgement needs only the stored row digests
        and the review rows, so a per-project roll-up does not have to parse and schema-validate
        every document just to say how many are waiting for a person. The verdict itself is
        ``_state_of``, the same one the read-back uses.
        """
        self._check_project(project_id)
        with closing(self._connect()) as conn:
            rows = conn.execute(
                'SELECT result_id, content_sha256 FROM prompt_result WHERE project_id=?'
                ' ORDER BY revision', (project_id,)).fetchall()
            reviews = [json.loads(row['document_json']) for row in conn.execute(
                'SELECT document_json FROM prompt_result_review WHERE project_id=?'
                ' ORDER BY review_revision', (project_id,)).fetchall()]
        counts = {'total': len(rows), 'unreviewed': 0, 'accepted': 0,
                  'declined': 0, 'not_current': 0}
        for row in rows:
            latest = next((review for review in reversed(reviews)
                           if review['result_id'] == row['result_id']), None)
            counts[_state_of(latest, row['content_sha256']).lower()] += 1
        return counts


def _now() -> str:
    return utc_now_rfc3339()
