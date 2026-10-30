# SPDX-License-Identifier: MIT
"""E-SLICE-01 design layer: Brief / Direction / DesignSystem vertical slice.

This is the single writer for the three design-layer tables added by
``design-lab-state-design-layer-v1.sql`` (schema v2 adds the DB-level
single-choice index, v3 the append-only event log). It is NOT a second runtime,
backend or ledger: it reuses the one local state database, opens it through the
existing creative store connection (which applies the additive design-layer
migration),
and reuses the shared ``operation_intent`` idempotency table for crash-safe,
retried-but-not-duplicated writes.

The slice is structural, not a Host run and not a Human-Jury acceptance:
  * a Brief is the recorded "what we are designing and why";
  * a Direction is one concrete visual stance under a brief; choosing one sets
    ``chosen`` as the single source of truth for that decision;
  * a DesignSystem binding binds the chosen direction to ONE catalog design
    system (validated against the packaged ``design-lab/design-systems``
    manifests), so a future Build/Review step has a fixed design contract.

Readback is the persisted record itself; evidence is the recorded spec digests,
the chosen-actor fact and the binding spec digest. Nothing here claims E3/E4.

F-2a revision model (``design-lab-state-design-layer-v3.sql``): the content rows
are immutable, the history is ONE append-only ``design_layer_event`` log, and
``chosen`` stays the materialized record of the human choice. Every write path
appends its event inside the SAME transaction as the state change it describes;
``revise_brief`` / ``revise_direction`` append a NEW content row
(version = old + 1) and only move the superseded row's ``superseded_by``
pointer (no content column is ever rewritten); ``lineage_brief`` /
``lineage_direction`` read the chain back, oldest version first.
"""
from __future__ import annotations

import json
import re
import sqlite3
from contextlib import closing
from pathlib import Path

from .creative import store as cstore
from .creative.store import CreativeError
from .interop import InteropError, dtcg, schema_errors
from .runtime import asset_store as assets
from .runtime.paths import PROJECT_ROOT, PathPolicyError
from .runtime.state_resources import repo_resource

# P0-07: the design-system catalog (source of the design contracts a direction
# may bind to) is packaged into the wheel under design_lab/resources/
# design-systems, and also lives in the source checkout. _catalog_root()
# resolves it packaged-first (installed wheel via importlib.resources) with a
# source-checkout fallback, mirroring workbench.resource(): in an installed
# environment PROJECT_ROOT does not point at the design-systems tree, so the
# catalog must come from the package.
_CATALOG_PKG = ('design_lab', 'resources', 'design-systems')
_CATALOG_SOURCE = ('design-lab', 'design-systems')

#: The brief readback's own contract. ``design-lab/schemas/design-brief.schema.json`` declares a
#: content model -- discipline, objective, audience, deliverables, success_metrics, brand_assets --
#: that no code in this repository stores, serves or validates, while the route answers with a
#: versioned record (title, goals, constraints, reference ids, spec digest, chain pointers). Rather
#: than leave the served payload described only by a TypeScript interface in the page, the payload
#: gets the contract it actually satisfies; the divergence of the two shapes stays an open decision.
BRIEF_READBACK_SCHEMA_VERSION = 'design-lab/brief-readback/v1'
# repo_resource, not PROJECT_ROOT: the installed wheel's PROJECT_ROOT is the interpreter's own Lib,
# so a source-green run cannot see that the brief read-back contract is simply absent there.
BRIEF_READBACK_SCHEMA_PATH = repo_resource('schemas/brief-readback.schema.json')


def _brief_readback_schema():
    from .interop import load_schema
    schema = load_schema(BRIEF_READBACK_SCHEMA_PATH)
    if not (schema.get('$defs') or {}).get('brief'):
        raise DesignLayerError(500, 'BRIEF_CONTRACT_VIOLATION',
                               [f'{BRIEF_READBACK_SCHEMA_PATH.name} declares no $defs.brief record'])
    return schema


def _check_brief_readback(payload, *, envelope: bool):
    """Refuse to serve a brief that does not satisfy the readback contract.

    Every field here is written by this module, so a mismatch means code and contract have diverged
    -- a renamed key, a dropped ``sha256:`` prefix, a null replaced by an empty string. Without this
    the page would receive a short record and a reader would call the project empty; with it the
    failure is a named 500 carrying the field paths.
    """
    schema = _brief_readback_schema()
    target = schema if envelope else {**(schema['$defs']['brief']), '$defs': schema['$defs']}
    try:
        problems = schema_errors(target, payload)
    except InteropError as exc:
        raise DesignLayerError(500, 'BRIEF_CONTRACT_VIOLATION', [str(exc)]) from exc
    if problems:
        raise DesignLayerError(500, 'BRIEF_CONTRACT_VIOLATION', problems)
    return payload


#: The four envelopes this family answered with no version of its own, measured 2026-10-23 off a
#: live `make_server` boot rather than read off the source: a one-record wrapper (`{brief: …}`,
#: `{direction: …}`, `{binding: …}`) served by ten routes, a live-row list (`{directions: …}`,
#: `{token_documents: …}`), a version chain (`{lineage: …}`) and the roll-up (`{design_layer: …}`).
#: Each gets ONE document and ONE version; the record shapes inside them are `$ref`'d from the file
#: that already owns them, so paying this debt does not create a second description of a row.
DESIGN_RECORD_SCHEMA_VERSION = 'design-lab/design-record/v1'
DESIGN_COLLECTION_SCHEMA_VERSION = 'design-lab/design-collection/v1'
DESIGN_LINEAGE_SCHEMA_VERSION = 'design-lab/design-lineage/v1'
DESIGN_LAYER_ROLLUP_SCHEMA_VERSION = 'design-lab/design-layer-rollup/v1'

# repo_resource, as for the brief read-back: an installed wheel's PROJECT_ROOT is the interpreter's
# own Lib, and a check that cannot open its schema must not answer as a verdict about the work.
DESIGN_RECORD_SCHEMA_PATH = repo_resource('schemas/design-record-v1.schema.json')
DESIGN_COLLECTION_SCHEMA_PATH = repo_resource('schemas/design-collection-v1.schema.json')
DESIGN_LINEAGE_SCHEMA_PATH = repo_resource('schemas/design-lineage-v1.schema.json')
DESIGN_LAYER_ROLLUP_SCHEMA_PATH = repo_resource('schemas/design-layer-rollup-v1.schema.json')

#: Every document the four envelopes can `$ref` into, including themselves. The set is named here
#: because a reference that resolves to nothing is reported by jsonschema as a defect in the
#: PAYLOAD, which would blame a project's records for a packaging fault in this build.
_DESIGN_CONTRACT_FILES = (
    ('design-lab/schemas/brief-readback.schema.json', lambda: BRIEF_READBACK_SCHEMA_PATH),
    ('design-lab/schemas/design-record-v1.schema.json', lambda: DESIGN_RECORD_SCHEMA_PATH),
    ('design-lab/schemas/design-collection-v1.schema.json',
     lambda: DESIGN_COLLECTION_SCHEMA_PATH),
    ('design-lab/schemas/design-lineage-v1.schema.json', lambda: DESIGN_LINEAGE_SCHEMA_PATH),
    ('design-lab/schemas/design-layer-rollup-v1.schema.json',
     lambda: DESIGN_LAYER_ROLLUP_SCHEMA_PATH),
)

#: Distinguishes "this list has no cursor field at all" from "this list is on its last page".
_UNSET = object()


def _design_contracts():
    """Load the envelope documents and the one they borrow the brief shape from, offline."""
    from .interop import load_schema, resource_registry
    documents = {}
    for label, get_path in _DESIGN_CONTRACT_FILES:
        document = load_schema(get_path())
        ident = document.get('$id')
        if not isinstance(ident, str) or not ident:
            raise DesignLayerError(500, 'DESIGN_CONTRACT_UNREADABLE',
                                  [f'{label} declares no `$id`, so the envelope that `$ref`'
                                   's it cannot resolve the reference'])
        documents[ident] = document
    dtcg_document = dtcg.load_schema()
    documents.setdefault(dtcg_document['$id'], dtcg_document)
    return resource_registry(documents)


def _check_design_envelope(code, schema_path, version, payload):
    """Refuse to serve an envelope that does not satisfy its own contract.

    The emitter writes every key in these documents, so a mismatch means code and contract have
    already diverged -- a renamed wrapper key, a record that grew a field, a version bumped on one
    side only. Serving it anyway is the failure this guard exists for: the page would read a short
    record and call the project empty. The version is compared against the file before validating,
    because a schema that binds a different version than the emitter stamps is one defect that
    looks like none.
    """
    from .interop import load_schema
    try:
        schema = load_schema(schema_path)
    except InteropError as exc:
        raise DesignLayerError(500, code, [str(exc)]) from exc
    bound = ((schema.get('properties') or {}).get('schemaVersion') or {}).get('const')
    if bound != version:
        raise DesignLayerError(500, code,
                               [f'{schema_path.name} binds {bound!r}, not {version!r} -- the '
                                'contract and the emitter disagree about which version this is'])
    try:
        problems = schema_errors(schema, payload, registry=_design_contracts())
    except (InteropError, KeyError, TypeError) as exc:
        raise DesignLayerError(500, code, [str(exc)]) from exc
    if problems:
        raise DesignLayerError(500, code, problems)
    return payload


def _check_design_record(kind, record):
    """The one-record answer a brief/direction/binding read or write gives."""
    if kind not in ('brief', 'direction', 'binding'):
        raise DesignLayerError(500, 'DESIGN_RECORD_CONTRACT_VIOLATION',
                               [f'{kind!r} is not a record kind this envelope can carry'])
    return _check_design_envelope(
        'DESIGN_RECORD_CONTRACT_VIOLATION', DESIGN_RECORD_SCHEMA_PATH,
        DESIGN_RECORD_SCHEMA_VERSION,
        {'schemaVersion': DESIGN_RECORD_SCHEMA_VERSION, 'record_kind': kind, kind: record})


def _check_design_collection(kind, rows, next_cursor=_UNSET):
    """The live-row list of one design-layer collection, paged or not as the writer actually is."""
    payload = {'schemaVersion': DESIGN_COLLECTION_SCHEMA_VERSION, 'collection': kind, kind: rows}
    if next_cursor is not _UNSET:
        payload['next_cursor'] = next_cursor
    return _check_design_envelope('DESIGN_COLLECTION_CONTRACT_VIOLATION',
                                  DESIGN_COLLECTION_SCHEMA_PATH, DESIGN_COLLECTION_SCHEMA_VERSION,
                                  payload)


def _check_design_lineage(subject_kind, node):
    return _check_design_envelope(
        'DESIGN_LINEAGE_CONTRACT_VIOLATION', DESIGN_LINEAGE_SCHEMA_PATH,
        DESIGN_LINEAGE_SCHEMA_VERSION,
        {'schemaVersion': DESIGN_LINEAGE_SCHEMA_VERSION, 'subject_kind': subject_kind,
         'lineage': node})


def _check_design_rollup(node):
    return _check_design_envelope(
        'DESIGN_LAYER_ROLLUP_CONTRACT_VIOLATION', DESIGN_LAYER_ROLLUP_SCHEMA_PATH,
        DESIGN_LAYER_ROLLUP_SCHEMA_VERSION,
        {'schemaVersion': DESIGN_LAYER_ROLLUP_SCHEMA_VERSION, 'design_layer': node})


def _catalog_root():
    """Return the first design-system catalog root that actually has manifests."""
    from importlib.resources import files
    candidates = []
    try:
        candidates.append(files(_CATALOG_PKG[0]).joinpath(*_CATALOG_PKG[1:]))
    except (FileNotFoundError, ModuleNotFoundError, AttributeError):
        pass
    candidates.append(Path(PROJECT_ROOT).joinpath(*_CATALOG_SOURCE))
    for candidate in candidates:
        try:
            if candidate.is_dir() and list(candidate.glob('*/manifest.json')):
                return candidate
        except (OSError, RuntimeError):
            continue
    return candidates[0] if candidates else None


class DesignLayerError(ValueError):
    def __init__(self, status, code, detail=None):
        self.status, self.code = status, code
        # Field-path-qualified reasons for the refusals a reviewer can act on
        # ("color.brand.$value is not a CSS color string"). ``code`` stays the
        # machine word; ``detail`` is the extra, and it is absent for every
        # pre-existing refusal so their response bodies do not change shape.
        self.detail = list(detail) if detail else []


def _text(value, field, *, max_len=400):
    if not isinstance(value, str) or not value.strip():
        raise DesignLayerError(400, 'INVALID_FIELD')
    value = value.strip()
    if len(value) > max_len:
        raise DesignLayerError(400, 'FIELD_TOO_LONG')
    return value


def _string_list(value, field, *, limit=64, item_max=300):
    if value is None:
        return []
    if not isinstance(value, list) or len(value) > limit:
        raise DesignLayerError(400, 'INVALID_LIST')
    out = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or len(item.strip()) > item_max:
            raise DesignLayerError(400, 'INVALID_LIST_ITEM')
        out.append(item.strip())
    return out


def _json_field(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False)


def _record_intent(conn, *, scope, key, document):
    """Idempotent intent recording with a precise HTTP conflict contract.

    The shared creative store fails closed when the same idempotency key is
    reused with different content. Surface that as a 409 (``IDEMPOTENCY_CONFLICT``)
    rather than an opaque store error so the design-layer API keeps a clean,
    deterministic error face without a second store or ledger.
    """
    try:
        return cstore.record_intent(conn, scope=scope, key=key, document=document)
    except CreativeError:
        raise DesignLayerError(409, 'IDEMPOTENCY_CONFLICT')


# F-2a: the event kinds the v3 schema's CHECK accepts. Appending anything else
# would be a schema violation, so the module fails closed first.
EVENT_KINDS = (
    'brief-created', 'brief-revised',
    'direction-created', 'direction-revised',
    'direction-chosen', 'direction-unchosen',
    'binding-created', 'binding-rebound',
)


def _append_event(conn, *, project_id, kind, payload, brief_id=None, direction_id=None,
                  binding_id=None, actor=None, actor_kind=None, event_id=None):
    """Append ONE design-layer event inside the CALLER's open transaction.

    Append-only is a property of this write, not a convention: it is a plain
    INSERT (no ``OR REPLACE`` / ``OR IGNORE``), so a repeated ``event_id`` fails
    closed with a PRIMARY KEY violation instead of silently overwriting history,
    and the v3 schema adds BEFORE UPDATE/DELETE triggers that abort any other
    mutation of the log. The caller's transaction is the same one that performs
    the state change the event describes, so the change and its event commit (or
    roll back) together -- there is no window in which one exists without the
    other.
    """
    if kind not in EVENT_KINDS:
        raise DesignLayerError(400, 'UNKNOWN_EVENT_KIND')
    conn.execute(
        "INSERT INTO design_layer_event (event_id, project_id, kind, brief_id, direction_id,"
        " binding_id, payload_json, actor, actor_kind, created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (event_id or cstore.new_id('event'), project_id, kind, brief_id, direction_id,
         binding_id, _json_field(payload), actor, actor_kind, cstore.now()))


# P0-05: a reference asset id is the shape the image import layer mints
# (``img-`` + 64 hex). Anything else is rejected before it can reach the DB.
_ASSET_ID_SHAPE = re.compile(r'img-[0-9a-f]{64}')


def catalog():
    """The read-only design-system catalog (packaged manifests, no writes)."""
    systems = []
    catalog_root = _catalog_root()
    if catalog_root is not None:
        for manifest in sorted(catalog_root.glob('*/manifest.json')):
            data = json.loads(manifest.read_text(encoding='utf-8'))
            name = data.get('name')
            if not isinstance(name, str) or not name:
                continue
            systems.append({
                'name': name,
                'title': data.get('title') or name,
                'version': data.get('version') or '0.0.0',
                'evidence_level': (data.get('evidence') or {}).get('level', 'E0'),
            })
    return systems


# --------------------------------------------------------------------------- #
# Design-system TOKEN documents (closes W06-TOKEN-WRITE-GAP G1/G2/G3/G4)
# --------------------------------------------------------------------------- #

#: The exact body keys the token write route accepts. Declared here rather than
#: inline at the route so ``design-lab/tests/test_design_system_token_form_contract.py``
#: can prove the page posts this set and nothing else (the same trick the jury
#: form contract plays with JURY_CRITERIA).
TOKEN_WRITE_FIELDS = frozenset({'document', 'expected_version', 'actor', 'actor_kind',
                                'idempotency_key'})

#: Design-system names are catalog directory names (``uiux-commercial-light``);
#: the route pattern and the service both use this shape, so a name can never be
#: a path, a URL fragment or an overlong blob.
DESIGN_SYSTEM_NAME_PATTERN = r'[a-z0-9][a-z0-9-]{0,63}'
_DESIGN_SYSTEM_NAME_RE = re.compile(DESIGN_SYSTEM_NAME_PATTERN)

#: The token document is a DTCG document, so its writer lease is scoped to the
#: (project, design system) pair the chain belongs to.
TOKEN_LEASE_PREFIX = 'design-system-tokens:'
TOKEN_LEASE_SECONDS = 30.0

#: Cap on the submitted document size; enforced again by the route's body limit.
TOKEN_DOCUMENT_MAX_KEYS = 4096
#: Cap on nesting depth (DTCG group trees are shallow by design; a deep document is
#: an attack surface on the validator, not a design system).
TOKEN_DOCUMENT_MAX_DEPTH = 40


def _token_lease_key(project_id, design_system_name):
    return f'{TOKEN_LEASE_PREFIX}{project_id}:{design_system_name}'


def _count_nodes(value):
    """Rough JSON node count, for the size guard. Not a validation rule."""
    if isinstance(value, dict):
        return 1 + sum(_count_nodes(item) for item in value.values())
    if isinstance(value, list):
        return 1 + sum(_count_nodes(item) for item in value)
    return 1


def _json_shape_problems(value, path='document', depth=0):
    """A submitted token document must be JSON-shaped before a schema can judge it.

    Over HTTP the body already came from ``json.loads``, so keys are strings and
    NaN cannot appear; this guard exists for the direct service call, where a
    Python int key makes jsonschema's patternProperties raise a TypeError that
    would otherwise be read as a validator failure, and a NaN would make the
    canonical hash refuse later with no path attached. Depth is capped so a
    pathological document fails closed here instead of in the recursion limit.
    """
    if depth > TOKEN_DOCUMENT_MAX_DEPTH:
        return [f'{path}: nests deeper than {TOKEN_DOCUMENT_MAX_DEPTH} levels']
    problems: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                problems.append(f'{path}: object keys must be strings, '
                                f'got {type(key).__name__}')
                continue
            problems.extend(_json_shape_problems(item, f'{path}.{key}', depth + 1))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            problems.extend(_json_shape_problems(item, f'{path}[{index}]', depth + 1))
    elif isinstance(value, float) and (value != value
                                       or value in (float('inf'), float('-inf'))):
        problems.append(f'{path}: NaN and Infinity are not JSON numbers')
    return problems[:10]


def validate_token_document(document):
    """Validate a submitted DTCG token document; return ``(report, problems)``.

    ``problems`` is a list of field-path-qualified messages (G4 asked for exactly
    that, because a bare INVALID_REQUEST tells the reviewer nothing to fix). Two
    layers run, both already in the repo, neither weakened here:

    * the structural draft 2020-12 schema ``interop-dtcg-document.schema.json``,
      via ``interop.schema_errors``, which is what names the offending path;
    * :func:`design_lab.interop.dtcg.validate_document`, the canonical semantic
      contract ($type inheritance, alias resolution and cycle rejection, composite
      member completeness, per-type value shape).

    The canonical path is what runs: a pre-2025.10 document (``string``/``boolean``
    types, a ``typography`` value without ``letterSpacing``) is REFUSED with the
    adapter named in the message rather than quietly adapted, because adapting on
    the server's behalf would write values the reviewer never typed. If no schema
    validator is importable this fails closed (a token document that cannot be
    validated must not be persisted); nothing is invented and nothing is skipped.
    """
    if not isinstance(document, dict) or not document:
        return None, ['document: a DTCG token document must be a nonempty JSON object']
    if _count_nodes(document) > TOKEN_DOCUMENT_MAX_KEYS:
        return None, [f'document: exceeds the {TOKEN_DOCUMENT_MAX_KEYS} JSON node cap']
    shape = _json_shape_problems(document)
    if shape:
        return None, shape
    try:
        problems = schema_errors(dtcg.load_schema(), document)
    except InteropError as exc:
        message = str(exc)
        # A schema the build cannot load, or a validator that is not installed, is
        # this product's failure, not the reviewer's: say so and refuse to write
        # rather than reporting their document as invalid.
        if message.startswith(('JSON Schema', 'structural validation requires')) \
                and 'could not run' not in message:
            raise DesignLayerError(503, 'TOKEN_VALIDATOR_UNAVAILABLE', [message]) from None
        raise DesignLayerError(400, 'TOKEN_DOCUMENT_INVALID', [f'document: {message}']) from None
    if problems:
        return None, [f'document: {problem}' for problem in problems]
    try:
        return dtcg.validate_document(document), []
    except InteropError as exc:
        return None, [f'document: {exc}']


class DesignLayer:
    def __init__(self, service):
        self.service = service
        self.paths = service.paths

    # -- connection helpers -------------------------------------------------
    def _check_project(self, project_id) -> None:
        if self.service.get_project(project_id) is None:
            raise DesignLayerError(404, 'PROJECT_NOT_FOUND')

    def _db_path(self):
        return self.paths.database_path(self.service.database)

    def _ro(self):
        # Read path reuses the SAME guarded connection the write path uses, so
        # the design-layer tables (from GUARDED_MIGRATIONS) are guaranteed to
        # exist before any read. A bare read-only sqlite3.connect would skip the
        # additive migration and fail with "no such table" on a project that
        # has not yet recorded a brief/direction/binding.
        return cstore.connect(self._db_path(), project_root=self.paths.project_root)

    def _rows(self, sql, params=()):
        with closing(self._ro()) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute(sql, params).fetchall()]

    # -- readback shapes ----------------------------------------------------
    @staticmethod
    def _brief(row) -> dict:
        return {
            'brief_id': row['brief_id'],
            'title': row['title'],
            'goals': json.loads(row['goals_json']),
            'constraints': json.loads(row['constraints_json']) if row['constraints_json'] else None,
            'reference_asset_ids': json.loads(row['reference_asset_ids']) if row['reference_asset_ids'] else [],
            'spec_sha256': 'sha256:' + row['spec_sha256'],
            'version': row['version'],
            'superseded_by': row['superseded_by'],
            'created_at': row['created_at'],
        }

    @staticmethod
    def _direction(row) -> dict:
        return {
            'direction_id': row['direction_id'],
            'brief_id': row['brief_id'],
            'title': row['title'],
            'style_notes': json.loads(row['style_notes_json']) if row['style_notes_json'] else None,
            'color_mood': row['color_mood'],
            'typography_mood': row['typography_mood'],
            'chosen': bool(row['chosen']),
            'actor': row['actor'],
            'actor_kind': row['actor_kind'],
            'spec_sha256': 'sha256:' + row['spec_sha256'],
            'version': row['version'],
            'superseded_by': row['superseded_by'],
            'created_at': row['created_at'],
        }

    @staticmethod
    def _binding(row) -> dict:
        return {
            'binding_id': row['binding_id'],
            'direction_id': row['direction_id'],
            'design_system_name': row['design_system_name'],
            'spec_sha256': 'sha256:' + row['spec_sha256'],
            'version': row['version'],
            'superseded_by': row['superseded_by'],
            'created_at': row['created_at'],
        }

    @staticmethod
    def _verify_references(conn, project_id, refs):
        """P0-05: every reference_asset_id must be a real asset of THIS project.

        Deduped in order; a malformed id, an unknown id and an id owned by a
        different project all fail closed (no arbitrary ``img-…`` string may be
        persisted into a brief). The ``asset`` table is visible on this same
        guarded connection, so no second store or cross-database read is needed.
        """
        seen = []
        for ref in refs:
            if ref not in seen:
                seen.append(ref)
        for ref in seen:
            if not _ASSET_ID_SHAPE.fullmatch(ref):
                raise DesignLayerError(400, 'INVALID_REFERENCE_ASSET_ID')
            row = conn.execute(
                "SELECT project_id FROM asset WHERE asset_id=?", (ref,)).fetchone()
            if row is None:
                raise DesignLayerError(404, 'REFERENCE_ASSET_NOT_FOUND')
            if row['project_id'] != project_id:
                raise DesignLayerError(409, 'REFERENCE_ASSET_PROJECT_MISMATCH')
        return seen

    # -- briefs -------------------------------------------------------------
    def create_brief(self, project_id, *, title, goals, constraints,
                     reference_asset_ids, idempotency_key):
        self._check_project(project_id)
        title = _text(title, 'title')
        goals = _string_list(goals, 'goals')
        if not goals:
            raise DesignLayerError(400, 'GOALS_REQUIRED')
        constraints = _text(constraints, 'constraints', max_len=2000) if constraints else None
        refs = _string_list(reference_asset_ids, 'reference_asset_ids', limit=32, item_max=72)
        # P0-05: dedupe now (in order) so the persisted + hashed reference list is the
        # canonical one; the per-id asset existence / project-ownership checks happen on
        # the write connection below.
        refs = list(dict.fromkeys(refs))

        document = {'title': title, 'goals': goals, 'constraints': constraints,
                    'reference_asset_ids': refs}
        spec = cstore.hash_document(document)
        with closing(cstore.connect(self._db_path(), project_root=self.paths.project_root)) as conn:
            with cstore.transaction(conn):
                conn.row_factory = sqlite3.Row
                operation_id, _ = _record_intent(
                    conn, scope='brief:' + project_id, key=idempotency_key, document=document)
                existing = conn.execute(
                    "SELECT * FROM design_brief WHERE operation_id=?", (operation_id,)).fetchone()
                if existing is not None:
                    return _check_design_record('brief', self._brief(dict(existing)))
                # P0-05: fail closed before persisting — every reference must be a
                # real asset of this project (malformed / unknown / cross-project).
                refs = self._verify_references(conn, project_id, refs)
                brief_id = cstore.new_id('brief')
                conn.execute(
                    "INSERT INTO design_brief (brief_id, operation_id, project_id, title, goals_json,"
                    " constraints_json, reference_asset_ids, spec_sha256, version, created_at)"
                    " VALUES (?,?,?,?,?,?,?,?,1,?)",
                    (brief_id, operation_id, project_id, title, _json_field(goals),
                     # P0-04: store constraints as a JSON-encoded string (""text""), not as
                     # {"constraints":"text"}; readback below json.loads it back to the same
                     # string|null so the frontend and backend share ONE contract (no
                     # [object Object] double truth).
                     _json_field(constraints) if constraints else None,
                     _json_field(refs) if refs else None,
                     spec.removeprefix('sha256:'), cstore.now()))
                _append_event(
                    conn, project_id=project_id, kind='brief-created', brief_id=brief_id,
                    payload={'brief_id': brief_id, 'version': 1, 'spec_sha256': spec})
                created = conn.execute(
                    'SELECT * FROM design_brief WHERE brief_id=?', (brief_id,)).fetchone()
        return _check_design_record('brief', self._brief(dict(created)))

    def list_briefs(self, project_id, after=''):
        self._check_project(project_id)
        rows = self._rows(
            "SELECT * FROM design_brief WHERE project_id=? AND brief_id>? ORDER BY brief_id LIMIT 101",
            (project_id, after))
        return _check_brief_readback(
            {'schemaVersion': BRIEF_READBACK_SCHEMA_VERSION,
             'briefs': [self._brief(r) for r in rows[:100]],
             'next_cursor': rows[99]['brief_id'] if len(rows) > 100 else None}, envelope=True)

    def get_brief(self, project_id, brief_id):
        self._check_project(project_id)
        rows = self._rows(
            "SELECT * FROM design_brief WHERE project_id=? AND brief_id=?", (project_id, brief_id))
        if not rows:
            raise DesignLayerError(404, 'BRIEF_NOT_FOUND')
        return _check_design_record(
            'brief', _check_brief_readback(self._brief(rows[0]), envelope=False))

    def revise_brief(self, project_id, brief_id, *, title, goals, constraints,
                     reference_asset_ids, idempotency_key):
        """Append the NEXT version of an existing brief (F-2a, content revision).

        The parent row is never rewritten: this INSERTs a new brief row with
        ``version = parent.version + 1`` and moves ONLY the parent's
        ``superseded_by`` pointer at it, in the same transaction as the
        ``brief-revised`` event. Every content column of the parent (title,
        goals, constraints, references, spec_sha256, created_at) keeps its
        original bytes -- a revision is an append, not an edit.

        Idempotency reuses the shared intent table, so a replayed key returns the
        SAME new brief identity and a key reused with different content fails
        closed (409 IDEMPOTENCY_CONFLICT). Revising an already-superseded version
        would fork the chain, so it fails closed too (409 STALE_REVISION): revise
        the live tip returned by the previous revision.
        """
        self._check_project(project_id)
        title = _text(title, 'title')
        goals = _string_list(goals, 'goals')
        if not goals:
            raise DesignLayerError(400, 'GOALS_REQUIRED')
        constraints = _text(constraints, 'constraints', max_len=2000) if constraints else None
        refs = list(dict.fromkeys(_string_list(reference_asset_ids, 'reference_asset_ids',
                                               limit=32, item_max=72)))
        # spec_sha256 is the digest of the CONTENT document (identity-free), so
        # the same content has the same digest across versions. The intent
        # document adds the parent id, so reusing a key against a different
        # parent is a genuine conflict, not a replay.
        content = {'title': title, 'goals': goals, 'constraints': constraints,
                   'reference_asset_ids': refs}
        spec = cstore.hash_document(content)
        document = {'parent_brief_id': brief_id, **content}
        with closing(cstore.connect(self._db_path(), project_root=self.paths.project_root)) as conn:
            with cstore.transaction(conn):
                conn.row_factory = sqlite3.Row
                parent = conn.execute(
                    "SELECT * FROM design_brief WHERE project_id=? AND brief_id=?",
                    (project_id, brief_id)).fetchone()
                if parent is None:
                    raise DesignLayerError(404, 'BRIEF_NOT_FOUND')
                operation_id, _ = _record_intent(
                    conn, scope='brief-revision:' + project_id, key=idempotency_key,
                    document=document)
                existing = conn.execute(
                    "SELECT * FROM design_brief WHERE operation_id=?", (operation_id,)).fetchone()
                if existing is not None:
                    # Idempotent replay: the same key returns the same new
                    # version, and appends nothing new.
                    return _check_design_record('brief', self._brief(dict(existing)))
                if parent['superseded_by'] is not None:
                    raise DesignLayerError(409, 'STALE_REVISION')
                refs = self._verify_references(conn, project_id, refs)
                version = int(parent['version']) + 1
                revised_id = cstore.new_id('brief')
                conn.execute(
                    "INSERT INTO design_brief (brief_id, operation_id, project_id, title,"
                    " goals_json, constraints_json, reference_asset_ids, spec_sha256, version,"
                    " created_at) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (revised_id, operation_id, project_id, title, _json_field(goals),
                     _json_field(constraints) if constraints else None,
                     _json_field(refs) if refs else None,
                     spec.removeprefix('sha256:'), version, cstore.now()))
                # The ONLY column a revision may touch on the parent row.
                conn.execute(
                    "UPDATE design_brief SET superseded_by=? WHERE brief_id=?",
                    (revised_id, brief_id))
                _append_event(
                    conn, project_id=project_id, kind='brief-revised', brief_id=revised_id,
                    payload={'old_id': brief_id, 'new_id': revised_id, 'version': version,
                             'previous_version': int(parent['version']), 'spec_sha256': spec})
                created = conn.execute(
                    "SELECT * FROM design_brief WHERE brief_id=?", (revised_id,)).fetchone()
        return _check_design_record('brief', self._brief(dict(created)))

    # -- directions ---------------------------------------------------------
    def create_direction(self, project_id, *, brief_id, title, style_notes,
                         color_mood, typography_mood, idempotency_key):
        self._check_project(project_id)
        if not self._rows("SELECT brief_id FROM design_brief WHERE project_id=? AND brief_id=?",
                          (project_id, brief_id)):
            raise DesignLayerError(404, 'BRIEF_NOT_FOUND')
        title = _text(title, 'title')
        style_notes = _string_list(style_notes, 'style_notes') or None
        color_mood = _text(color_mood, 'color_mood') if color_mood else None
        typography_mood = _text(typography_mood, 'typography_mood') if typography_mood else None

        document = {'brief_id': brief_id, 'title': title, 'style_notes': style_notes,
                    'color_mood': color_mood, 'typography_mood': typography_mood}
        spec = cstore.hash_document(document)
        with closing(cstore.connect(self._db_path(), project_root=self.paths.project_root)) as conn:
            with cstore.transaction(conn):
                conn.row_factory = sqlite3.Row
                operation_id, _ = _record_intent(
                    conn, scope='direction:' + project_id, key=idempotency_key, document=document)
                existing = conn.execute(
                    "SELECT direction_id FROM design_direction WHERE operation_id=?",
                    (operation_id,)).fetchone()
                if existing is not None:
                    row = conn.execute(
                        "SELECT * FROM design_direction WHERE direction_id=?", (existing[0],)).fetchone()
                    return _check_design_record('direction', self._direction(dict(row)))
                direction_id = cstore.new_id('direction')
                conn.execute(
                    "INSERT INTO design_direction (direction_id, operation_id, project_id, brief_id,"
                    " title, style_notes_json, color_mood, typography_mood, spec_sha256, version,"
                    " created_at) VALUES (?,?,?,?,?,?,?,?,?,1,?)",
                    (direction_id, operation_id, project_id, brief_id, title,
                     _json_field(style_notes) if style_notes else None, color_mood,
                     typography_mood, spec.removeprefix('sha256:'), cstore.now()))
                _append_event(
                    conn, project_id=project_id, kind='direction-created', brief_id=brief_id,
                    direction_id=direction_id,
                    payload={'direction_id': direction_id, 'brief_id': brief_id, 'version': 1,
                             'spec_sha256': spec})
                created = conn.execute(
                    'SELECT * FROM design_direction WHERE direction_id=?', (direction_id,)).fetchone()
        return _check_design_record('direction', self._direction(dict(created)))

    def list_directions(self, project_id, brief_id=None, after=''):
        self._check_project(project_id)
        sql = "SELECT * FROM design_direction WHERE project_id=?"
        params = [project_id]
        if brief_id:
            sql += " AND brief_id=?"
            params.append(brief_id)
        sql += " AND direction_id>? ORDER BY direction_id LIMIT 101"
        params.append(after)
        rows = self._rows(sql, params)
        return _check_design_collection(
            'directions', [self._direction(r) for r in rows[:100]],
            next_cursor=rows[99]['direction_id'] if len(rows) > 100 else None)

    def get_direction(self, project_id, direction_id):
        self._check_project(project_id)
        rows = self._rows("SELECT * FROM design_direction WHERE project_id=? AND direction_id=?",
                          (project_id, direction_id))
        if not rows:
            raise DesignLayerError(404, 'DIRECTION_NOT_FOUND')
        return _check_design_record('direction', self._direction(rows[0]))

    def revise_direction(self, project_id, direction_id, *, title, style_notes, color_mood,
                         typography_mood, idempotency_key):
        """Append the NEXT version of a direction (F-2a, content revision).

        Same contract as :meth:`revise_brief`: a new row with
        ``version = parent.version + 1`` plus a ``direction-revised`` event in one
        transaction, and only the parent's ``superseded_by`` pointer moves -- the
        parent's content columns keep their original bytes.

        The human Choice follows the lineage: when the revised version was the
        chosen one, the parent releases ``chosen``/``actor`` (materialized state,
        not content) and the new version carries the same choice, recorded in the
        event payload as ``chosen_moved``. A design-system binding, however, stays
        attached to the version it was bound to (its row is append-only and may
        not be repointed), so after revising a bound chosen direction the read
        model's ``active_binding`` is null until the contract is bound again.
        """
        self._check_project(project_id)
        title = _text(title, 'title')
        style_notes = _string_list(style_notes, 'style_notes') or None
        color_mood = _text(color_mood, 'color_mood') if color_mood else None
        typography_mood = _text(typography_mood, 'typography_mood') if typography_mood else None
        with closing(cstore.connect(self._db_path(), project_root=self.paths.project_root)) as conn:
            with cstore.transaction(conn):
                conn.row_factory = sqlite3.Row
                parent = conn.execute(
                    "SELECT * FROM design_direction WHERE project_id=? AND direction_id=?",
                    (project_id, direction_id)).fetchone()
                if parent is None:
                    raise DesignLayerError(404, 'DIRECTION_NOT_FOUND')
                content = {'brief_id': parent['brief_id'], 'title': title,
                           'style_notes': style_notes, 'color_mood': color_mood,
                           'typography_mood': typography_mood}
                spec = cstore.hash_document(content)
                document = {'parent_direction_id': direction_id, **content}
                operation_id, _ = _record_intent(
                    conn, scope='direction-revision:' + project_id, key=idempotency_key,
                    document=document)
                existing = conn.execute(
                    "SELECT * FROM design_direction WHERE operation_id=?",
                    (operation_id,)).fetchone()
                if existing is not None:
                    return _check_design_record('direction', self._direction(dict(existing)))
                if parent['superseded_by'] is not None:
                    raise DesignLayerError(409, 'STALE_REVISION')
                version = int(parent['version']) + 1
                carried = bool(int(parent['chosen']))
                revised_id = cstore.new_id('direction')
                # Retire the parent FIRST when the choice moves, so the brief never
                # holds two LIVE chosen rows: the v2 partial UNIQUE index keys on
                # (brief_id) WHERE chosen=1 AND superseded_by IS NULL.
                conn.execute(
                    "UPDATE design_direction SET superseded_by=?, chosen=?, actor=?, actor_kind=?"
                    " WHERE direction_id=?",
                    (revised_id, 0 if carried else parent['chosen'],
                     None if carried else parent['actor'],
                     None if carried else parent['actor_kind'], direction_id))
                conn.execute(
                    "INSERT INTO design_direction (direction_id, operation_id, project_id, brief_id,"
                    " title, style_notes_json, color_mood, typography_mood, chosen, actor, actor_kind,"
                    " spec_sha256, version, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                    (revised_id, operation_id, project_id, parent['brief_id'], title,
                     _json_field(style_notes) if style_notes else None, color_mood,
                     typography_mood, 1 if carried else 0,
                     parent['actor'] if carried else None,
                     parent['actor_kind'] if carried else None,
                     spec.removeprefix('sha256:'), version, cstore.now()))
                _append_event(
                    conn, project_id=project_id, kind='direction-revised',
                    brief_id=parent['brief_id'], direction_id=revised_id,
                    actor=parent['actor'] if carried else None,
                    actor_kind=parent['actor_kind'] if carried else None,
                    payload={'old_id': direction_id, 'new_id': revised_id, 'version': version,
                             'previous_version': int(parent['version']),
                             'brief_id': parent['brief_id'], 'spec_sha256': spec,
                             'chosen_moved': carried,
                             'previous_chosen_direction_id': direction_id if carried else None})
                created = conn.execute(
                    "SELECT * FROM design_direction WHERE direction_id=?", (revised_id,)).fetchone()
        return _check_design_record('direction', self._direction(dict(created)))

    def choose_direction(self, project_id, direction_id, *, actor, actor_kind, idempotency_key):
        """Record which direction is chosen (the Golden Workflow 1 "Human Choice").

        Structural: sets ``chosen`` + the acting fact on the row. It is NOT a host
        run and NOT a quality-jury acceptance of a produced artifact.
        """
        self._check_project(project_id)
        if actor_kind not in ('human', 'agent'):
            raise DesignLayerError(400, 'INVALID_ACTOR_KIND')
        if actor_kind != 'human':
            raise DesignLayerError(403, 'HUMAN_DIRECTION_CHOICE_REQUIRED')
        actor = _text(actor, 'actor')
        document = {'direction_id': direction_id, 'actor': actor, 'actor_kind': actor_kind}
        with closing(cstore.connect(self._db_path(), project_root=self.paths.project_root)) as conn:
            with cstore.transaction(conn):
                conn.row_factory = sqlite3.Row
                row = dict(conn.execute(
                    "SELECT * FROM design_direction WHERE project_id=? AND direction_id=?",
                    (project_id, direction_id)).fetchone() or {})
                if not row:
                    raise DesignLayerError(404, 'DIRECTION_NOT_FOUND')
                operation_id, _ = _record_intent(
                    conn, scope='choose:' + direction_id, key=idempotency_key, document=document)
                # F-2a: the previous choice is read BEFORE the de-select below,
                # because the direction-chosen event must record which direction
                # (if any) this choice replaced. The append set is decided from
                # the state transition, so an idempotent replay of the same
                # choice appends nothing and the log stays one entry per
                # transition instead of one entry per HTTP retry.
                previous = conn.execute(
                    "SELECT direction_id FROM design_direction WHERE brief_id=? AND chosen=1"
                    " AND direction_id<>?", (row['brief_id'], direction_id)).fetchone()
                previous_chosen_id = previous['direction_id'] if previous else None
                transitioned = (not int(row['chosen']) or previous_chosen_id is not None
                                or row['actor'] != actor or row['actor_kind'] != actor_kind)
                # P0-01 single-choice invariant: within this ONE transaction, de-select
                # every other chosen direction under the SAME brief, then select this
                # direction. Both updates share the single transaction, so the database
                # can never end up in a "all cleared but the new choice not set"
                # intermediate state. (Choosing across different briefs is unaffected:
                # each brief keeps at most one chosen direction.)
                conn.execute(
                    "UPDATE design_direction SET chosen=0, actor=NULL, actor_kind=NULL "
                    "WHERE brief_id=? AND chosen=1 AND direction_id<>?",
                    (row['brief_id'], direction_id))
                conn.execute(
                    "UPDATE design_direction SET chosen=1, actor=?, actor_kind=? WHERE direction_id=?",
                    (actor, actor_kind, direction_id))
                if transitioned:
                    if previous_chosen_id is not None:
                        _append_event(
                            conn, project_id=project_id, kind='direction-unchosen',
                            brief_id=row['brief_id'], direction_id=previous_chosen_id,
                            actor=actor, actor_kind=actor_kind,
                            payload={'direction_id': previous_chosen_id,
                                     'brief_id': row['brief_id'],
                                     'unchosen_by_direction_id': direction_id})
                    _append_event(
                        conn, project_id=project_id, kind='direction-chosen',
                        brief_id=row['brief_id'], direction_id=direction_id,
                        actor=actor, actor_kind=actor_kind,
                        payload={'direction_id': direction_id, 'brief_id': row['brief_id'],
                                 'previous_chosen_direction_id': previous_chosen_id,
                                 'actor': actor, 'actor_kind': actor_kind})
                updated = conn.execute(
                    "SELECT * FROM design_direction WHERE direction_id=?", (direction_id,)).fetchone()
        return _check_design_record('direction', self._direction(dict(updated)))

    # -- design-system binding ---------------------------------------------
    def bind_design_system(self, project_id, direction_id, *, design_system_name,
                           idempotency_key):
        """Bind the chosen direction to ONE catalog design system (design contract)."""
        self._check_project(project_id)
        name = _text(design_system_name, 'design_system_name')
        catalog_names = {s['name'] for s in catalog()}
        if name not in catalog_names:
            raise DesignLayerError(400, 'UNKNOWN_DESIGN_SYSTEM')
        document = {'direction_id': direction_id, 'design_system_name': name}
        spec = cstore.hash_document(document)
        with closing(cstore.connect(self._db_path(), project_root=self.paths.project_root)) as conn:
            with cstore.transaction(conn):
                conn.row_factory = sqlite3.Row
                # P0-03: a binding is the design contract OF THE CHOSEN direction.
                # Fail closed when the target direction exists but is not chosen
                # (a specific 4xx, never the generic INVALID_REQUEST).
                dr = conn.execute(
                    "SELECT chosen, actor_kind FROM design_direction WHERE project_id=? AND direction_id=?",
                    (project_id, direction_id)).fetchone()
                if dr is None:
                    raise DesignLayerError(404, 'DIRECTION_NOT_FOUND')
                if not int(dr['chosen']):
                    raise DesignLayerError(409, 'DIRECTION_NOT_CHOSEN')
                if dr['actor_kind'] != 'human':
                    # Upgrade guard: databases created before the human-only
                    # choice rule may already contain an agent-chosen row.
                    # It remains visible for audit, but cannot advance to a
                    # design-system binding until a human chooses it.
                    raise DesignLayerError(409, 'HUMAN_DIRECTION_CHOICE_REQUIRED')
                operation_id, _ = _record_intent(
                    conn, scope='bind:' + direction_id, key=idempotency_key, document=document)
                existing = conn.execute(
                    "SELECT binding_id FROM design_system_binding WHERE operation_id=?",
                    (operation_id,)).fetchone()
                if existing is not None:
                    row = conn.execute(
                        "SELECT * FROM design_system_binding WHERE binding_id=?",
                        (existing[0],)).fetchone()
                    return _check_design_record('binding', self._binding(dict(row)))
                # F-2a: a binding for this direction that already exists means this
                # write REPLACES it -- recorded as binding-rebound carrying the
                # replaced id. The replaced row is left exactly as written (the v1
                # schema's no-update trigger forbids touching it); the new row is
                # the next version, so the read model's "latest revision of the
                # chosen direction's bindings" (get_design_layer) stays correct.
                replaced = conn.execute(
                    "SELECT * FROM design_system_binding WHERE direction_id=?"
                    " ORDER BY version DESC, created_at DESC, binding_id DESC LIMIT 1",
                    (direction_id,)).fetchone()
                binding_id = cstore.new_id('bind')
                version = int(replaced['version']) + 1 if replaced is not None else 1
                conn.execute(
                    "INSERT INTO design_system_binding (binding_id, operation_id, project_id,"
                    " direction_id, design_system_name, spec_sha256, version, created_at)"
                    " VALUES (?,?,?,?,?,? ,?,?)",
                    (binding_id, operation_id, project_id, direction_id, name,
                     spec.removeprefix('sha256:'), version, cstore.now()))
                _append_event(
                    conn, project_id=project_id,
                    kind='binding-rebound' if replaced is not None else 'binding-created',
                    brief_id=None, direction_id=direction_id, binding_id=binding_id,
                    payload={'binding_id': binding_id, 'direction_id': direction_id,
                             'design_system_name': name, 'version': version,
                             'spec_sha256': spec,
                             'replaced_binding_id': replaced['binding_id'] if replaced is not None
                                                   else None})
                created = conn.execute(
                    "SELECT * FROM design_system_binding WHERE binding_id=?", (binding_id,)).fetchone()
        return _check_design_record('binding', self._binding(dict(created)))

    # -- design-system token documents (write + readback) -------------------
    @staticmethod
    def _token_document(row) -> dict:
        return {
            'token_document_id': row['token_document_id'],
            'project_id': row['project_id'],
            'design_system_name': row['design_system_name'],
            'document': json.loads(row['document_json']),
            'token_count': row['token_count'],
            'dtcg_schema_version': row['dtcg_schema_version'],
            'spec_sha256': 'sha256:' + row['spec_sha256'],
            'actor': row['actor'],
            'actor_kind': row['actor_kind'],
            'version': row['version'],
            'superseded_by': row['superseded_by'],
            'created_at': row['created_at'],
        }

    def _live_token_rows(self, project_id, design_system_name=None):
        """The live (not superseded) token rows of a project, by design system."""
        sql = ("SELECT * FROM design_system_token WHERE project_id=?"
               " AND superseded_by IS NULL")
        params = [project_id]
        if design_system_name is not None:
            sql += " AND design_system_name=?"
            params.append(design_system_name)
        return self._rows(sql + " ORDER BY design_system_name", params)

    def write_tokens(self, project_id, design_system_name, *, document, expected_version,
                     actor, actor_kind, idempotency_key):
        """Append ONE version of a project's DTCG token document for a design system.

        The chain contract is the one ``revise_brief`` already uses, and the
        reasons below are the refusals, each with its own code so the page can say
        what to fix instead of showing one grey INVALID_REQUEST:

        * ``UNKNOWN_DESIGN_SYSTEM`` (400) -- the name is not in the packaged
          catalog, so no token document may be recorded against a system that does
          not exist here;
        * ``TOKEN_DOCUMENT_INVALID`` (400, with field-path ``detail``) -- the
          document fails the DTCG schema or the canonical semantic contract;
          validation runs BEFORE anything is persisted, and a pre-2025.10 document
          is refused with the adapter named rather than silently converted;
        * ``TOKEN_VALIDATOR_UNAVAILABLE`` (503) -- no schema validator importable,
          so the document cannot be judged and is not written (fail closed);
        * ``STALE_REVISION`` (409) -- ``expected_version`` is not the live tip, so
          this write would supersede a version its author never saw; the caller
          re-reads the tip and re-applies, exactly the recovery path the brief
          revisions already document;
        * ``TOKEN_DOCUMENT_AMBIGUOUS`` (409) -- more than one live row for the
          pair, which this build cannot produce and refuses to guess a winner for;
        * ``IDEMPOTENCY_CONFLICT`` (409) -- the shared intent table's rule: a
          replayed key with different content;
        * ``TOKEN_WRITER_BUSY`` / ``TOKEN_WRITER_LEASE_LOST`` (409) -- the repo's
          ONE writer lease (``runtime/asset_store.py``) fenced by generation.

        A published version is never mutated: the new row is an append and the
        previous row only moves its ``superseded_by`` pointer, and the v4 schema's
        BEFORE UPDATE OF trigger makes rewriting a content column a database error
        even for a caller that bypasses this method.
        """
        self._check_project(project_id)
        name = _text(design_system_name, 'design_system_name', max_len=64)
        if not _DESIGN_SYSTEM_NAME_RE.fullmatch(name):
            raise DesignLayerError(400, 'INVALID_DESIGN_SYSTEM_NAME')
        if name not in {entry['name'] for entry in catalog()}:
            raise DesignLayerError(400, 'UNKNOWN_DESIGN_SYSTEM')
        if isinstance(expected_version, bool) or not isinstance(expected_version, int) \
                or expected_version < 0:
            raise DesignLayerError(400, 'INVALID_EXPECTED_VERSION')
        if actor_kind not in ('human', 'agent'):
            raise DesignLayerError(400, 'INVALID_ACTOR_KIND')
        actor = _text(actor, 'actor')
        report, problems = validate_token_document(document)
        if problems:
            raise DesignLayerError(400, 'TOKEN_DOCUMENT_INVALID', problems)

        content = {'design_system_name': name, 'document': document}
        spec = cstore.hash_document(content)
        intent = {'expected_version': expected_version, 'actor': actor,
                  'actor_kind': actor_kind, **content}
        resource = _token_lease_key(project_id, name)
        holder = cstore.new_id('token-writer')
        with closing(cstore.connect(self._db_path(), project_root=self.paths.project_root)) as conn:
            try:
                acquired = assets.acquire_writer(conn, resource, holder,
                                                 lease_seconds=TOKEN_LEASE_SECONDS)
            except assets.AssetError:
                raise DesignLayerError(503, 'TOKEN_WRITER_LEASE_UNAVAILABLE') from None
            if not acquired:
                # Another writer holds this document's lease. Refusing is the whole
                # point: two concurrent appends would each pass the
                # expected_version check they read before the other committed.
                raise DesignLayerError(409, 'TOKEN_WRITER_BUSY')
            generation = assets.writer_token(conn, resource, holder)
            try:
                with cstore.transaction(conn):
                    conn.row_factory = sqlite3.Row
                    # Same fence the publication path uses, asserted inside this
                    # transaction: a lease that lapsed while the document was being
                    # judged rolls the append back instead of landing unopposed.
                    assets.assert_writer_fence(conn, resource, holder, generation)
                    # Read the tip on THIS connection, not through _rows(): a second
                    # connection would read the pre-transaction state and, in WAL,
                    # could block behind the writer lock this transaction holds.
                    live = conn.execute(
                        "SELECT * FROM design_system_token WHERE project_id=?"
                        " AND design_system_name=? AND superseded_by IS NULL"
                        " ORDER BY version DESC", (project_id, name)).fetchall()
                    if len(live) > 1:
                        raise DesignLayerError(409, 'TOKEN_DOCUMENT_AMBIGUOUS')
                    tip = live[0] if live else None
                    operation_id, _ = _record_intent(
                        conn, scope='design-system-tokens:' + project_id,
                        key=idempotency_key, document=intent)
                    existing = conn.execute(
                        "SELECT * FROM design_system_token WHERE operation_id=?",
                        (operation_id,)).fetchone()
                    if existing is not None:
                        # Idempotent replay: the same key returns the version it
                        # already appended and appends nothing new.
                        return {'token_document': self._token_document(dict(existing))}
                    current = int(tip['version']) if tip else 0
                    if current != expected_version:
                        raise DesignLayerError(409, 'STALE_REVISION')
                    version = current + 1
                    token_document_id = cstore.new_id('tokdoc')
                    conn.execute(
                        "INSERT INTO design_system_token (token_document_id, operation_id,"
                        " project_id, design_system_name, document_json, token_count,"
                        " dtcg_schema_version, spec_sha256, actor, actor_kind, version,"
                        " created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (token_document_id, operation_id, project_id, name,
                         _json_field(document), report['token_count'],
                         report['schemaVersion'], spec.removeprefix('sha256:'),
                         actor, actor_kind, version, cstore.now()))
                    if tip is not None:
                        # The ONLY column a revision may touch on the previous row.
                        conn.execute(
                            "UPDATE design_system_token SET superseded_by=?"
                            " WHERE token_document_id=?",
                            (token_document_id, tip['token_document_id']))
                    created = conn.execute(
                        "SELECT * FROM design_system_token WHERE token_document_id=?",
                        (token_document_id,)).fetchone()
                    return {'token_document': self._token_document(dict(created))}
            except assets.AssetError:
                # _fence refuses a stale or expired generation; that is a
                # concurrency fact the page can recover from, not a store failure.
                raise DesignLayerError(409, 'TOKEN_WRITER_LEASE_LOST') from None
            finally:
                assets.release_writer(conn, resource, holder, generation=generation)

    def list_token_documents(self, project_id):
        """The project's LIVE token documents -- an honest empty list when none."""
        self._check_project(project_id)
        return _check_design_collection(
            'token_documents', [self._token_document(row)
                                for row in self._live_token_rows(project_id)])

    def get_tokens(self, project_id, design_system_name):
        """The live token document of one design system in this project."""
        self._check_project(project_id)
        rows = self._live_token_rows(project_id, design_system_name)
        if not rows:
            raise DesignLayerError(404, 'TOKEN_DOCUMENT_NOT_FOUND')
        return {'token_document': self._token_document(rows[0])}

    def token_lineage(self, project_id, design_system_name):
        """Every recorded version of one document chain, oldest first (read-only).

        Unlike ``lineage_brief`` this walks the ``superseded_by`` pointers alone:
        the token chain has no row in ``design_layer_event`` (its CHECK constraint
        enumerates the brief/direction/binding kinds and a v1-v3 table's CHECK
        cannot be widened by an additive migration). Per-version actor, actor_kind,
        created_at and spec digest are columns on the row itself, so the history
        still says who wrote what.
        """
        self._check_project(project_id)
        rows = self._rows(
            "SELECT * FROM design_system_token WHERE project_id=?"
            " AND design_system_name=? ORDER BY version, created_at, token_document_id",
            (project_id, design_system_name))
        if not rows:
            raise DesignLayerError(404, 'TOKEN_DOCUMENT_NOT_FOUND')
        live = [row for row in rows if row['superseded_by'] is None]
        if len(live) != 1:
            raise DesignLayerError(409, 'TOKEN_DOCUMENT_AMBIGUOUS')
        return {'lineage': {
            'design_system_name': design_system_name, 'project_id': project_id,
            'root_id': rows[0]['token_document_id'],
            'requested_version': rows[-1]['version'],
            'live_id': live[0]['token_document_id'],
            'versions': [self._token_document(row) for row in rows]}}

    # -- F-2a lineage (read-only) ------------------------------------------
    def project_of_brief(self, brief_id):
        """Owner project of a brief id.

        The id-addressed revision/lineage routes carry no project path, so the
        owner is resolved from the record itself; an unknown id fails closed.
        """
        rows = self._rows("SELECT project_id FROM design_brief WHERE brief_id=?", (brief_id,))
        if not rows:
            raise DesignLayerError(404, 'BRIEF_NOT_FOUND')
        return rows[0]['project_id']

    def project_of_direction(self, direction_id):
        """Owner project of a direction id (see :meth:`project_of_brief`)."""
        rows = self._rows("SELECT project_id FROM design_direction WHERE direction_id=?",
                          (direction_id,))
        if not rows:
            raise DesignLayerError(404, 'DIRECTION_NOT_FOUND')
        return rows[0]['project_id']

    def lineage_brief(self, project_id, brief_id):
        """The brief's version chain, oldest version first (read-only)."""
        self._check_project(project_id)
        chain = self._chain(project_id, brief_id,
                            "SELECT * FROM design_brief WHERE project_id=?", 'brief_id',
                            'brief-revised', 'BRIEF_NOT_FOUND', self._brief)
        for record in chain['versions']:
            _check_brief_readback(record, envelope=False)
        return _check_design_lineage('brief', {'brief_id': brief_id, **chain})

    def lineage_direction(self, project_id, direction_id):
        """The direction's version chain, oldest version first (read-only)."""
        self._check_project(project_id)
        return _check_design_lineage('direction', {'direction_id': direction_id, **self._chain(
            project_id, direction_id, "SELECT * FROM design_direction WHERE project_id=?",
            'direction_id', 'direction-revised', 'DIRECTION_NOT_FOUND', self._direction)})

    def _chain(self, project_id, row_id, select_sql, id_column, revised_kind, not_found, shape):
        """Resolve one record's version chain from the append-only events.

        The edge record is the log, not the version numbers: the ``*-revised``
        payloads map ``new_id -> old_id``, so ANY member of the chain resolves to
        the same full lineage (an older version included). The chain is then
        walked forward through ``superseded_by``, so a caller reads history
        instead of guessing which row is current; the live tip is named
        explicitly. Nothing here writes.
        """
        rows = {row[id_column]: row for row in self._rows(select_sql, (project_id,))}
        if row_id not in rows:
            raise DesignLayerError(404, not_found)
        parents = {}
        for event in self._rows(
                "SELECT payload_json FROM design_layer_event WHERE project_id=? AND kind=?"
                " ORDER BY created_at, rowid", (project_id, revised_kind)):
            payload = json.loads(event['payload_json'])
            old_id, new_id = payload.get('old_id'), payload.get('new_id')
            if old_id in rows and new_id in rows:
                parents[new_id] = old_id
        root, seen = row_id, {row_id}
        while parents.get(root) in rows and parents[root] not in seen:
            root = parents[root]
            seen.add(root)
        chain, cursor, walked = [], root, set()
        while cursor in rows and cursor not in walked:
            walked.add(cursor)
            chain.append(rows[cursor])
            cursor = rows[cursor]['superseded_by']
        chain.sort(key=lambda row: (int(row['version']), row['created_at'], row[id_column]))
        return {'root_id': root, 'requested_id': row_id,
                'live_id': chain[-1][id_column] if chain else None,
                'versions': [shape(row) for row in chain]}

    # -- design-system catalog ---------------------------------------------
    def design_systems(self):
        """Read-only catalog of packaged design systems (the bindable contracts)."""
        return _check_design_collection('design_systems', catalog())

    # -- readback: the full slice ------------------------------------------
    def get_design_layer(self, project_id):
        """Read back the whole vertical slice for a project (the evidence shape)."""
        self._check_project(project_id)
        briefs = self.list_briefs(project_id)['briefs']
        directions = self.list_directions(project_id)['directions']
        bindings = self._rows(
            "SELECT * FROM design_system_binding WHERE project_id=? ORDER BY binding_id",
            (project_id,))
        chosen = [d for d in directions if d['chosen']]
        # P0-02: chosen_direction reflects ONLY a real chosen direction. There is
        # no fallback to the most-recently-created direction, which would fabricate
        # a Human Choice that never happened. No chosen -> null.
        chosen_dir = chosen[0] if chosen else None
        # P0-D: active_binding is the binding attached to THE CHOSEN direction --
        # never a stray binding left on some now-unchosen direction. Switching
        # the choice (A -> B) leaves B unbound, so active_binding must go null,
        # not point at A's binding. Among a chosen direction's own bindings we
        # take the latest revision (version, then created_at, then id).
        active_binding = None
        if chosen_dir is not None:
            owned = [b for b in bindings
                     if b['direction_id'] == chosen_dir['direction_id']]
            if owned:
                active_binding = max(
                    owned,
                    key=lambda b: (int(b['version']), b['created_at'], b['binding_id']))
        return _check_design_rollup({
            'briefs': briefs,
            'directions': directions,
            'chosen_direction': chosen_dir,
            'bindings': [self._binding(b) for b in bindings],
            'active_binding': self._binding(dict(active_binding)) if active_binding else None,
            'design_systems': catalog(),
        })
