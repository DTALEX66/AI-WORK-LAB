#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""DL-ROUTE-PAYLOAD-CONTRACTS: a bound route must answer with a payload that its schema accepts.

Why this gate exists. ``design-lab/config/contract-bindings.json`` recorded, as named debt,
that a set of routes answers with a payload carrying a ``schemaVersion`` for which NO schema
file exists anywhere -- ``design-lab/jury-readback/v1``, ``design-lab/task-resource-preflight/v1``,
``design-lab/path-diagnostic/v1``, ``design-lab/capability-library/v1`` and
``design-lab/domain-pack-readback/v1``. A version string with nothing behind it is the
artifact-preflight gap (commit 1ea64bbe) repeated five times: a reader sees
``schemaVersion`` and assumes a boundary is enforced.

Each debt has now been closed one way or the other, and this script is what keeps it closed.
Three more were paid here on 2026-10-20 -- GET /api/models, GET .../model-selection and GET
.../knowledge-candidates/<id>/export -- each added with the live payload that produced it, in the
same move as the schema and the ledger row, because a schema nobody feeds a real response to is a
reader-visible claim of enforcement.
It does not trust a ledger row that says BOUND_SCHEMA -- it drives the product over a real
socket and checks what came back:

1. PAYLOADS ARE THE PRODUCT'S. One ``design_lab.http_service.make_server`` boot against a
   scratch project root; every payload compared here is the bytes that route wrote,
   ``json.loads`` of the response body. Nothing in this file assembles an example. If the
   emitter's shape changes, what lands in the comparison is the changed shape.
2. THE SCHEMA IS A VALID draft 2020-12 document, and every real payload validates against it
   (SCHEMA_VIOLATION).
3. BOTH DIRECTIONS OF FIELD DISAGREEMENT ARE RED. A field the schema ``required`` that the
   route did not send is MISSING_FROM_EMITTER; a field the route sent that a closed schema
   does not declare is UNDECLARED_BY_SCHEMA. Nested locations are compared too, including
   map values (``tools.*``, ``current_verdicts.*``) and the branches of an ``anyOf``.
   ``$ref`` is followed into the document that owns the shape, so a jury record is compared
   against ``assurance-jury-record-v2.schema.json` rather than restated here.
4. THE VERSION IS ONE VALUE ON BOTH SIDES. The schema's ``schemaVersion`` const, the binding's
   declared version, and a literal the emitter source still produces or compares must agree
   (VERSION_DRIFT). This is the check a one-sided bump cannot pass.
5. THE LEDGER AND THIS FILE MUST AGREE, IN BOTH DIRECTIONS. Every binding here must appear in
   ``contract-bindings.json`` as a BOUND_SCHEMA row naming the same schema, version and emitter
   file (LEDGER_DISAGREES); every BOUND_SCHEMA row naming one of these schemas must have a
   binding here (UNVALIDATED_BINDING). Deleting the row, or quietly downgrading it to
   SCHEMA_LESS with the ``version`` and ``emitter`` fields removed, is red here as well as in
   design-lab/scripts/verify_contract_bindings.py -- the debt line is not removable.
6. NOTHING TO COMPARE IS A FAILURE. Zero bindings, a binding whose files are missing, zero
   payloads, a payload that is not a mapping, or a schema that binds no object location the
   payload reaches are each red. A gate that matched nothing must not report a pass.

Usage:
    python design-lab/scripts/verify_route_payload_contracts.py
Exit 0 when every binding holds, 1 otherwise. The last line printed is
``VERIFY_ROUTE_PAYLOAD_CONTRACTS=PASS|FAIL ...``.
"""
from __future__ import annotations

import ast
import hashlib
import http.client
import importlib.util
import json
import os
import secrets
import shutil
import sys
import tempfile
import threading
from contextlib import closing
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SRC = REPO / 'src'
SCHEMA_DIR = REPO / 'design-lab' / 'schemas'
LEDGER_REL = 'design-lab/config/contract-bindings.json'
SCRATCH_PARENT = REPO / '.project-local' / 'task-runtime'

try:
    import jsonschema
    import referencing
except ImportError as exc:  # pragma: no cover - a missing validator is a harness fault
    print(f'ERROR: IMPORT_FAULT {exc} -- this gate validates real payloads and needs '
          'jsonschema + referencing', file=sys.stderr)
    raise SystemExit(2)

JURY_RECORD_ID = 'https://dtalex66.local/schemas/assurance-jury-record-v2.json'


class Harness:
    """One live server, one scratch project, real records filed through the routes.

    The scratch project root carries the same committed inputs the real one does --
    design-lab/config/task-resources.json, and .project/paths.json when the machine has one --
    so /api/task-preflight and /api/environment answer with the shapes production answers with,
    while every write lands under the scratch tree.
    """

    def __init__(self):
        self.root = Path(tempfile.mkdtemp(prefix='route-payload-contracts-', dir=str(SCRATCH_PARENT)))
        self.saved_local_root = os.environ.pop('PROJECT_LOCAL_ROOT', None)
        self.httpd = None
        self.thread = None
        self._bodies: dict[str, dict] = {}

    def __enter__(self):
        project = self.root / 'project'
        (project / 'design-lab' / 'config').mkdir(parents=True)
        (project / '.project').mkdir(parents=True)
        (project / 'AGENTS.md').write_text('# route payload contract fixture project',
                                           encoding='utf-8')
        shutil.copy(REPO / 'design-lab/config/task-resources.json',
                    project / 'design-lab/config/task-resources.json')
        machine = REPO / '.project/paths.json'
        if machine.is_file():
            shutil.copy(machine, project / '.project/paths.json')
        if str(SRC) not in sys.path:
            sys.path.insert(0, str(SRC))
        from design_lab.assurance import jury_store
        from design_lab.http_service import make_server
        from design_lab.model_catalog import catalog
        from design_lab.runtime import asset_store as assets
        from design_lab.service import ProjectService
        self.jury_store = jury_store
        self.assets = assets
        self.service = ProjectService(project)
        self.filled = self.service.create_project('Payload Contract Filled')['id']
        self.empty = self.service.create_project('Payload Contract Empty')['id']
        self.declined = self.service.create_project('Payload Contract Declined')['id']
        self.version_id, self.digest = self._publish(b'artwork under review')
        self.token = secrets.token_hex(32)
        self.httpd = make_server(self.service, self.token, 0)
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()
        self._file_jury_records()
        self.brief_id = self._seed_briefs()
        self.candidate_id = self._file_candidate_for_export()
        self.chosen_model_id = self._file_model_choices(catalog())
        self._file_rights_decisions()
        self._file_research_findings()
        self._produce_prompt_results()
        self._seed_design_layer()
        self._seed_knowledge()
        self._seed_assistance()
        self._seed_plan_export()
        self._seed_target()
        self._seed_plan_feedback()
        return self

    def _produce_prompt_results(self):
        """Compose for real, then have a named human accept one of the two.

        Three review states have to be rows rather than adjectives: a stored-and-accepted result, a
        stored-and-nobody-signed one, and a project that never produced anything. The composition is
        produced by POSTing the route the page uses, so the bytes in the store are the bytes the
        route published -- not a document assembled here. The current brief id is read back from
        GET .../briefs because composing from a superseded revision is a real refusal, and a
        hard-coded id would turn this harness red for the wrong reason the day the fixture moves.
        """
        for project in (self.filled, self.declined):
            if project == self.declined:
                status, body = self.call('POST', f'/api/projects/{project}/briefs', {
                    'title': 'Store the prompt, then judge it', 'goals': ['traceable'],
                    'constraints': None, 'reference_asset_ids': [],
                    'idempotency_key': 'brief-for-results'})
                if status != 201:
                    raise RuntimeError(f'BRIEF_FOR_PROMPT_REFUSED {status} {body}')
            _status, listing = self.call('GET', f'/api/projects/{project}/briefs')
            brief_id = next(row['brief_id'] for row in listing['briefs']
                            if row['superseded_by'] is None)
            status, body = self.call('POST', f'/api/projects/{project}/prompts',
                                     {'brief_id': brief_id, 'direction_id': None,
                                      'target': 'image-generation'})
            if status != 201:
                raise RuntimeError(f'PROMPT_COMPOSE_REFUSED {project} {status} {body}')
            stored = body['document']
            if stored['composition_id'] not in json.dumps(
                    self.get(f'/api/projects/{project}/prompt-results')):
                raise RuntimeError(f'PROMPT_RESULT_NOT_KEPT {stored["composition_id"]}')
            if project == self.filled:
                status, body = self.call(
                    'POST', f'/api/projects/{project}/prompt-results'
                            f'/{stored["composition_id"]}/review',
                    {'decision': 'ACCEPTED', 'reviewer': 'dtalex66', 'reviewer_kind': 'human',
                     'reviewed_at': '2026-10-22T00:00:00Z',
                     'note': 'every sentence in the text is a field I filed'})
                if status != 201:
                    raise RuntimeError(f'PROMPT_REVIEW_REFUSED {status} {body}')
                self.prompt_result_id = stored['composition_id']

    def _file_rights_decisions(self):
        """One cleared project and one refused project, through the write route.

        Both clearance branches have to be real rows: the envelope's load-bearing claim is that
        `CLEARED` needs a filed scope AND a current APPROVED for every filed scope, and a schema
        written only against the empty read would let an emitter start clearing 0-of-0. The
        refused project carries an APPROVED and a DENIED, so `unapproved_scopes`,
        `approved_scope_count` and `filed_scope_count` are compared against a fork a reader can
        check by hand instead of a word they are asked to trust.
        """
        def document(decision_id, scope, decision):
            return {
                'schemaVersion': 'design-lab/rights-decision/v1', 'decision_id': decision_id,
                'use_scope': scope, 'decision': decision, 'decided_by': 'dtalex66',
                'decided_at': '2026-10-08T00:00:00Z', 'territory': 'worldwide',
                'license_ref': 'OFL-1.1', 'note': 'judged against rows filed through this '
                                                  'boundary',
            }
        for project, documents in (
                (self.filled, [document('rd-payload-1', 'commercial-print', 'APPROVED')]),
                (self.declined, [document('rd-payload-2', 'commercial-print', 'APPROVED'),
                                 document('rd-payload-3', 'web', 'DENIED')])):
            for body_document in documents:
                status, body = self.call('POST', f'/api/projects/{project}/rights',
                                         body_document)
                if status != 201:
                    raise RuntimeError(f'RIGHTS_WRITE_REFUSED '
                                       f'{body_document["decision_id"]} {status} {body}')

    def _file_research_findings(self):
        """A live finding, the row that superseded it, and a project that has none.

        `superseded_finding_count` is only ever nonzero when a real chain was filed, so the
        second write goes through `?supersedes=` instead of being simulated. The writer refuses a
        finding with no `sourceRefs`, which is why `unsourced_finding_count` is bound here as a
        counted field rather than a constant.
        """
        first = {'finding_id': 'rf-payload-1',
                 'claim': 'the reference set carries two fonts, so the pairing is a decision '
                          'somebody already made',
                 'sourceRefs': ['interview-07'], 'confidence': 'medium', 'notDesignRule': True}
        second = {'finding_id': 'rf-payload-2',
                  'claim': 'the same pairing is a default, not a decision: both references came '
                           'from one bundle',
                  'sourceRefs': ['bench-competitor-2026-05', 'interview-07'],
                  'confidence': 'high', 'notDesignRule': True}
        status, body = self.call('POST', f'/api/projects/{self.declined}/research', first)
        if status != 201:
            raise RuntimeError(f'RESEARCH_WRITE_REFUSED rf-payload-1 {status} {body}')
        status, body = self.call('POST',
                                 f'/api/projects/{self.declined}/research'
                                 f'?supersedes=rf-payload-1', second)
        if status != 201:
            raise RuntimeError(f'RESEARCH_SUPERSEDE_REFUSED rf-payload-2 {status} {body}')

    def native_runtime_cases(self):
        """The same route read before and after a native attempt was recorded.

        Order is the contract: the first read has to happen while the tables do not exist,
        because creating them belongs to `native_tasks._connect` and this read may not. The rows
        seeded here are the ones the projection publishes -- a held host, a quiescence carrying a
        receipt, an open reconciliation, its os-lock-v1 protocol, and an execution carrying both a
        receipt and a result -- under the attempt chain the guard's foreign key requires.
        """
        absent = self.get(f'/api/projects/{self.empty}/native-runtime')
        from design_lab.native_tasks import NativeTasks
        conn = NativeTasks(self.service)._connect()
        try:
            conn.execute('INSERT INTO operation_intent VALUES (?,?,?,?,?)',
                         ('op-payload-1', f'native:{self.filled}:photoshop', 'key-payload-1',
                          'c' * 64, '2026-10-08T00:00:00Z'))
            conn.execute("INSERT INTO job (job_id, operation_id) VALUES ('job-payload-1', "
                         "'op-payload-1')")
            conn.execute("INSERT INTO job_attempt VALUES ('job-payload-1', 1, "
                         "'2026-10-08T00:00:00Z')")
            for number, attempt in enumerate(('att-payload-guard', 'att-payload-exec',
                                              'att-payload-qui', 'att-payload-rec'), start=1):
                conn.execute("INSERT INTO attempt_state VALUES (?,?,?,'RUNNING',"
                             "'2026-10-08T00:00:00Z',NULL,'payload contract')",
                             (attempt, 'job-payload-1', number))
            conn.execute('INSERT INTO native_host_guard_v1 VALUES (?,?,?)',
                         ('photoshop', 'att-payload-guard', '2026-10-08T00:00:00Z'))
            conn.execute('INSERT INTO native_execution_v1 VALUES (?,?,?,?,?,?)',
                         ('att-payload-exec', self.filled, 'photoshop', '{"action":"payload"}',
                          '{"receipt":"payload"}', '{"result":"payload"}'))
            conn.execute('INSERT INTO native_quiescence_v1 VALUES (?,?,?,?)',
                         ('att-payload-qui', '{"authorization":"payload"}',
                          '2026-10-08T00:00:00Z', '{"receipt":"payload"}'))
            conn.execute('INSERT INTO native_reconciliation_v1 VALUES (?,?,?)',
                         ('att-payload-rec', '{"authorization":"payload"}',
                          '2026-10-08T00:00:00Z'))
            conn.execute('INSERT INTO native_recovery_protocol_v2 VALUES (?,?)',
                         ('att-payload-rec', 'os-lock-v1'))
            conn.commit()
        finally:
            conn.close()
        present = self.get(f'/api/projects/{self.filled}/native-runtime')
        return [('GET .../native-runtime with no native table yet', absent),
                ('GET .../native-runtime after a recorded attempt', present)]

    def task_readback_cases(self):
        """The three task reads, one of them carrying a cancellation the adapter acknowledged.

        Seeded through the product's own writers (`job_store.begin_attempt/transition/
        request_cancel/acknowledge_cancel`) rather than raw INSERTs: the point of this binding is
        that the emitted state words and the cancel flags are what the state machine actually
        produced, so a fixture that hand-wrote them could pass a schema that no longer matches the
        machine.
        """
        from design_lab.runtime import job_store

        if getattr(self, '_task_cases', None) is not None:
            # Two bindings read the same four payloads: re-running the state machine would ask it
            # to re-take a transition it already made, and that refusal is a real signal, not noise.
            return self._task_cases
        empty = self.get(f'/api/projects/{self.empty}/tasks')
        # Opened through job_store, not NativeTasks._connect(): the latter creates the native
        # execution tables, and the native-runtime binding's first case is the payload read while
        # that table was still ABSENT. A seed that opens it here would quietly turn that case into
        # PRESENT and retire the distinction it exists to protect.
        conn = job_store.connect(self.service.database,
                                 project_root=self.service.paths.project_root)
        try:
            job_id = 'job-' + 'a' * 64
            attempt = job_store.begin_attempt(
                conn, job_id, operation_id='op-' + 'b' * 64,
                idempotency_scope=f'native:{self.filled}:photoshop',
                idempotency_key='payload-contract-cancel', request_hash='c' * 64)
            job_store.transition(conn, attempt['attempt_id'], 'RUNNING')
            job_store.request_cancel(conn, attempt['attempt_id'])
            job_store.acknowledge_cancel(conn, attempt['attempt_id'])
            conn.commit()
        finally:
            conn.close()
        self._task_cases = [('GET .../tasks with nothing recorded', empty),
                            ('GET .../tasks after an acknowledged cancellation',
                             self.get(f'/api/projects/{self.filled}/tasks')),
                            ('GET .../tasks/<job>',
                             self.get(f'/api/projects/{self.filled}/tasks/{job_id}')),
                            ('GET .../tasks/<job>/events',
                             self.get(f'/api/projects/{self.filled}/tasks/{job_id}/events'))]
        return self._task_cases

    def _file_candidate_for_export(self):
        """A real candidate, approved by a named human, so the export route can answer 200.

        Written through the two write routes rather than by hand: an approved document assembled
        here would bind a shape the store cannot hold, and the export envelope's whole claim is
        that it projects a *stored* row. ``rights_gate_state`` is CHECKED because an unchecked
        rights gate is refused with its own reason -- a 409 would be a finding, not a skip.
        """
        document = {
            'candidate_id': 'kc-payload-1',
            'candidate_type': 'METHOD',
            'source': {'design_lab_sha': 'a' * 40, 'job_id': 'job-payload-1',
                       'operation_id': 'UNUSED', 'evidence_sha256': 'sha256:' + 'b' * 64},
            'rights': {'license_id': 'MIT', 'rights_gate_state': 'CHECKED',
                       'contains_client_asset': False, 'contains_third_party_asset': False,
                       'redaction_note': None},
            'payload': {'title': 'judge hierarchy before decoration',
                        'statement': 'type and image outrank a decorative device when they conflict',
                        'applies_to': ['editorial', 'brand']},
            'created_at': '2026-10-18T00:00:00Z',
            'revocation_entrypoint': 'design-lab/knowledge/revoke',
        }
        status, body = self.call('POST', f'/api/projects/{self.filled}/knowledge-candidates',
                                 document)
        if status != 201:
            raise RuntimeError(f'CANDIDATE_WRITE_REFUSED {status} {body}')
        status, body = self.call(
            'POST', f'/api/projects/{self.filled}/knowledge-candidates/kc-payload-1/review',
            {'decision': 'APPROVE', 'reviewer_id': 'dtalex66', 'reviewer_kind': 'human',
             'reviewed_at': '2026-10-18T00:00:00Z', 'note': None, 'reason': None})
        if status != 200:
            raise RuntimeError(f'CANDIDATE_REVIEW_REFUSED {status} {body}')
        return 'kc-payload-1'

    def _file_model_choices(self, catalogue_document):
        """One pick and one explicit 「不用」, so all three read-back states are real rows.

        The model id is taken from the catalogue this same server serves -- not typed into this
        file -- because a choice can only be made from what the registries record, and a
        hard-coded id would turn into a refusal the day the radar moves. ``UNUSED`` is the
        declination branch: DECLINED and NEVER_ASKED are different facts and both are compared.
        """
        model_id = catalogue_document['models'][0]['model_id']
        for project_id, payload in (
                (self.filled, {'model_id': model_id, 'declared_unused': False}),
                (self.declined, {'model_id': None, 'declared_unused': True})):
            body = {'actor': 'dtalex66', 'actor_kind': 'human', **payload}
            status, answer = self.call('POST',
                                       f'/api/projects/{project_id}/model-selection/choose', body)
            if status != 201:
                raise RuntimeError(f'MODEL_CHOICE_REFUSED {project_id} {status} {answer}')
        return model_id

    def _seed_briefs(self):
        """A real brief plus a real revision of it, through the write routes.

        Two versioned rows so the compared payload exercises more than the single-record case:
        the list carries both, ``next_cursor`` stays null because the page is not full, and the
        reference id is a genuine asset of the same project (the writer refuses anything else),
        so the schema is judged against a record that could not have been assembled by hand.
        """
        ref_id = 'img-' + 'a1' * 32
        with closing(self.assets.connect(self.service.database,
                                         project_root=self.service.paths.project_root)) as conn:
            conn.execute('INSERT INTO asset VALUES (?, ?, "psd", ?)',
                         (ref_id, self.filled, '2026-10-08T00:00:00Z'))
            conn.commit()
        status, body = self.call('POST', f'/api/projects/{self.filled}/briefs', {
            'title': 'Launch poster, zh-CN first', 'goals': ['modern', 'warm', 'restrained'],
            'constraints': 'must survive single-colour print', 'reference_asset_ids': [ref_id],
            'idempotency_key': 'brief-contract-create'})
        if status != 201:
            raise RuntimeError(f'BRIEF_WRITE_REFUSED {status} {body}')
        brief_id = body['brief']['brief_id']
        status, body = self.call('POST', f'/api/projects/{self.filled}/briefs/{brief_id}/revisions',
                                 {'title': 'Launch poster, zh-CN first',
                                  'goals': ['modern', 'warm', 'restrained', 'no stock shapes'],
                                  'constraints': 'must survive single-colour print',
                                  'reference_asset_ids': [ref_id],
                                  'idempotency_key': 'brief-contract-revise'})
        if status != 201:
            raise RuntimeError(f'BRIEF_REVISION_REFUSED {status} {body}')
        return brief_id

    # -- design-layer family (batch I, 2026-10-23) ------------------------------------------
    #: The exact request fields these routes take -- the same five and six the page posts and the
    #: write sweep sends, restated here as field sets, not as a second fixture vocabulary. Every
    #: payload compared below is the answer the product wrote in response to one of these.
    BRIEF_FIELDS = {'title': 'Family brief, measured', 'goals': ['bound', 'restrained'],
                    'constraints': None, 'reference_asset_ids': []}
    DIRECTION_FIELDS = {'title': 'Family direction, measured', 'style_notes': ['restrained'],
                        'color_mood': 'cool', 'typography_mood': 'sans'}

    def post(self, label, path, body):
        """A real write through a real socket, kept as the response the route produced.

        The caller names the idempotency key in the body, so a replay case is the SAME key sent
        twice and lands in the emitter's `SELECT ... WHERE operation_id=?` branch instead of
        quietly creating a second row.
        """
        if 'idempotency_key' not in body:
            raise AssertionError(f'{label}: a write case must name its own idempotency key')
        status, answer = self.call('POST', path, body)
        if status not in (200, 201):
            raise RuntimeError(f'DESIGN_WRITE_REFUSED {path} -> {status} {answer}')
        return (f'{label} [{status}]', answer)

    def new_brief(self, key):
        status, answer = self.call('POST', f'/api/projects/{self.filled}/briefs',
                                   dict(self.BRIEF_FIELDS, idempotency_key=key))
        if status != 201:
            raise RuntimeError(f'BRIEF_SEED_REFUSED {key} -> {status} {answer}')
        return answer['brief']['brief_id']

    def new_direction(self, key, brief_id):
        status, answer = self.call('POST', f'/api/projects/{self.filled}/directions',
                                   dict(self.DIRECTION_FIELDS, brief_id=brief_id,
                                        idempotency_key=key))
        if status != 201:
            raise RuntimeError(f'DIRECTION_SEED_REFUSED {key} -> {status} {answer}')
        return answer['direction']['direction_id']

    def _seed_design_layer(self):
        """A brief chain, a direction chain, a human choice, a binding and one token document.

        Seeded once, through the routes that serve them, because the reads and the writes in this
        family answer about *chains*: a revision must target the live tip (an already-superseded row
        answers 409 STALE_REVISION by design), and a lineage read of a superseded version is a
        different branch from a read of the tip. The ids kept here are therefore both ends.
        """
        self.design_system = self.get('/api/design-systems')['design_systems'][0]['name']
        self.dl_brief_v1 = self.new_brief('family-brief-seed')
        self.dl_brief_tip = self.post('POST .../briefs/<id>/revisions seeds the tip',
                                      f'/api/projects/{self.filled}/briefs'
                                      f'/{self.dl_brief_v1}/revisions',
                                      dict(self.BRIEF_FIELDS,
                                           title='Family brief, measured v2',
                                           idempotency_key='family-brief-rev-seed'))[
            1]['brief']['brief_id']
        self.dl_direction_v1 = self.new_direction('family-direction-seed', self.dl_brief_tip)
        self.dl_direction_tip = self.post('POST .../directions/<id>/revisions seeds the tip',
                                          f'/api/projects/{self.filled}/directions'
                                          f'/{self.dl_direction_v1}/revisions',
                                          dict(self.DIRECTION_FIELDS,
                                               title='Family direction, measured v2',
                                               idempotency_key='family-direction-seed-v2'))[
            1]['direction']['direction_id']
        self.post('POST .../directions/<id>/choose seeds the human choice',
                  f'/api/projects/{self.filled}/directions/{self.dl_direction_tip}/choose',
                  {'actor': 'dtalex66', 'actor_kind': 'human',
                   'idempotency_key': 'family-choose-seed'})
        self.post('POST .../directions/<id>/bind seeds the binding',
                  f'/api/projects/{self.filled}/directions/{self.dl_direction_tip}/bind',
                  {'design_system_name': self.design_system,
                   'idempotency_key': 'family-bind-seed'})
        self.post('POST .../design-system-tokens/<name> seeds one document',
                  f'/api/projects/{self.filled}/design-system-tokens/{self.design_system}',
                  {'document': {'color': {'$type': 'color', 'brand': {'$value': '#2563EB'}}},
                   'expected_version': 0, 'actor': 'ALEX', 'actor_kind': 'human',
                   'idempotency_key': 'family-token-seed'})

    # -- knowledge library family (batch K, 2026-10-23) --------------------------------------
    #: The create route's exact field set. `recommended: True` on revision 1 and `False` on the
    #: revision is deliberate: it is the only way to produce the branch where the newest bytes and
    #: the recommended revision are different documents, which the detail readback renders as two
    #: separate numbers plus the recommended document.
    KNOWLEDGE_FIELDS = {
        'entry_type': 'METHOD',
        'title': '分镜拆解三步法',
        'summary': '把一段脚本拆成镜头表：先定节拍，再定景别，最后定转场。',
        'domain_tags': ['film'],
        'task_tags': ['storyboard'],
        'target_tools': ['storyboarder'],
        'body': '第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。',
        'applicability': '适合 30-90 秒短片的分镜前置。',
        'limits': '不适用于需要精确口型对位的动画。',
        'source': {'sourceId': 'payload-contracts', 'origin': 'UNKNOWN',
                   'author': 'payload-contracts', 'license': 'UNKNOWN',
                   'licenseStatus': 'unknown', 'allowedUsage': 'UNKNOWN',
                   'citationScope': 'UNKNOWN', 'version': '1',
                   'observedAt': '2026-10-23T00:00:00Z', 'contentHash': 'UNKNOWN',
                   'verification': 'UNVERIFIED'},
        'related_capability_ids': [],
        'recommended': True,
        'created_by': 'payload-contracts',
        'supersedes': None,
    }

    def _seed_knowledge(self):
        """One real entry, its revision, a search that hits it and an import, through the routes.

        The search case asks for ``分镜`` -- a two-character Chinese word the FTS5 trigram index
        cannot answer -- so the payload compared here is the one produced by the fallback the
        product actually ships, not a query that would have passed on the index alone. The import
        case is sent twice: the first answer is CREATED and the second DUPLICATE, and both are
        route answers a caller can receive.
        """
        status, created = self.call('POST', '/api/knowledge-entries', dict(self.KNOWLEDGE_FIELDS))
        if status != 201:
            raise RuntimeError(f'KNOWLEDGE_CREATE_REFUSED {status} {created}')
        entry_id = created['entry']['knowledge_entry_id']
        revision = dict(self.KNOWLEDGE_FIELDS, title='分镜拆解三步法（修订）', recommended=False,
                        expected_revision=1)
        revision.pop('supersedes')
        status, revised = self.call('POST', f'/api/knowledge-entries/{entry_id}/revisions',
                                    revision)
        if status != 201:
            raise RuntimeError(f'KNOWLEDGE_REVISION_REFUSED {status} {revised}')
        imported = {key: value for key, value in self.KNOWLEDGE_FIELDS.items()
                    if key != 'created_by'}
        imported['imported_by'] = 'payload-contracts'
        status, imported_once = self.call('POST', '/api/knowledge-entries/import', imported)
        if status != 201:
            raise RuntimeError(f'KNOWLEDGE_IMPORT_REFUSED {status} {imported_once}')
        status, imported_twice = self.call('POST', '/api/knowledge-entries/import', imported)
        if status != 201:
            raise RuntimeError(f'KNOWLEDGE_IMPORT_REPLAY_REFUSED {status} {imported_twice}')
        status, rebuilt = self.call('POST', '/api/knowledge-entries/index-rebuild', {})
        if status != 200:
            raise RuntimeError(f'KNOWLEDGE_REBUILD_REFUSED {status} {rebuilt}')
        self.knowledge = {
            'create': ('POST /api/knowledge-entries', created),
            'revise': ('POST .../revisions appends revision 2', revised),
            'detail': (f'GET /api/knowledge-entries/{entry_id}',
                       self.get(f'/api/knowledge-entries/{entry_id}')),
            'search': ('GET .../search?q=分镜 (two characters, fallback)',
                       self.get('/api/knowledge-entries/search?q=%E5%88%86%E9%95%9C')),
            'import': ('POST .../import creates', imported_once),
            'import-replay': ('POST .../import replays the same source version', imported_twice),
            'rebuild': ('POST .../index-rebuild', rebuilt),
        }
        # DL-KB-05 D5 (2026-10-24). A judgement is a LATER act, so these two readbacks are taken
        # after the written flags exist: `recommendation_basis` flips from written-flag to
        # recorded-judgement and the recommended number moves BACK, and `source_state` goes from
        # null ("nobody has said") to a named replacement entry. The 'detail' case above stays the
        # pre-judgement shape, so the null branch of both fields is compared too.
        status, successor = self.call('POST', '/api/knowledge-entries', dict(
            self.KNOWLEDGE_FIELDS, title='分镜拆解（替代来源）', recommended=False))
        if status != 201:
            raise RuntimeError(f'KNOWLEDGE_SUCCESSOR_REFUSED {status} {successor}')
        status, moved_back = self.call(
            'POST', f'/api/knowledge-entries/{entry_id}/judgements',
            {'kind': 'RECOMMENDATION', 'revision': 1, 'value': None, 'replaced_by': None,
             'reason': '第二步的景别在实际项目里更常用，把推荐退回 r1。',
             'recorded_by': 'dtalex66', 'recorded_by_kind': 'HUMAN'})
        if status != 201:
            raise RuntimeError(f'KNOWLEDGE_RECOMMENDATION_JUDGEMENT_REFUSED {status} {moved_back}')
        status, dead_source = self.call(
            'POST', f'/api/knowledge-entries/{entry_id}/judgements',
            {'kind': 'SOURCE_STATE', 'revision': None, 'value': 'INVALID',
             'replaced_by': successor['entry']['knowledge_entry_id'],
             'reason': '原来源下架，替代条目已入库。',
             'recorded_by': 'dtalex66', 'recorded_by_kind': 'HUMAN'})
        if status != 201:
            raise RuntimeError(f'KNOWLEDGE_SOURCE_JUDGEMENT_REFUSED {status} {dead_source}')
        self.knowledge['judgement'] = (
            'POST .../judgements moves the recommendation back to revision 1', moved_back)
        self.knowledge['judgement-source'] = (
            'POST .../judgements marks the source INVALID with a stored replacement', dead_source)

    def knowledge_cases(self, *names):
        return [self.knowledge[name] for name in names]

    # -- assistance plan family (batch K3, 2026-10-24) -------------------------------------
    #: The create route's exact field set. The creative is present on the plan that gets a second
    #: revision and a human choice; the draft below leaves it out on purpose, because "saved" and
    #: "provided" are two different facts the readback has to keep apart.
    ASSISTANCE_FIELDS = {
        'objective': '为秋季新品做一张克制的主视觉海报',
        'output_type': 'IMAGE',
        'neutral_creative': '一束侧光穿过纸纤维，留出大面积空白承载标题。',
        'brand_constraints': ['只用两种油墨'],
        'role_constraints': [],
        'lens': None,
        'sound': None,
        'references': [],
        'external_steps': [{'step': '手动导出印刷 PDF', 'tool': 'Illustrator',
                            'job_id': None, 'operation_id': 'op-payload-1024'}],
        'known_gaps': ['目标纸张未定'],
        'limits': ['未包含多语言排版'],
        'created_by': 'payload-contracts',
    }

    def _seed_assistance(self):
        """One plan with two revisions and a human choice, a draft, and an empty collection.

        The referenced asset is a stored ``asset_version`` of this same project, inserted with the
        same call the brief fixture uses -- the plan writer resolves the live revision and digest
        itself, so what is compared is the readback's own measurement. No reversal exists for it,
        which is why the compared payload carries LINKED_ONLY rather than ANALYSIS the caller
        claimed.
        """
        asset_id = 'img-' + 'b2' * 32
        with closing(self.assets.connect(self.service.database,
                                         project_root=self.service.paths.project_root)) as conn:
            conn.execute('INSERT INTO asset VALUES (?, ?, "raster", ?)',
                         (asset_id, self.filled, '2026-10-24T00:00:00Z'))
            conn.execute('INSERT INTO asset_version (version_id, asset_id, version_no,'
                         ' content_sha256, state, created_at) VALUES (?,?,?,?,?,?)',
                         ('v-' + 'b2' * 16, asset_id, 1, 'sha256:' + 'b' * 64, 'ACTIVE',
                          '2026-10-24T00:00:00Z'))
            conn.commit()
        status, created = self.call('POST', f'/api/projects/{self.filled}/assistance-plans',
                                    dict(self.ASSISTANCE_FIELDS,
                                         references=[{'kind': 'ASSET', 'id': asset_id}]))
        if status != 201:
            raise RuntimeError(f'ASSISTANCE_CREATE_REFUSED {status} {created}')
        plan_id = created['plan']['plan_id']
        status, revised = self.call(
            'POST', f'/api/projects/{self.filled}/assistance-plans/{plan_id}/revisions',
            dict(self.ASSISTANCE_FIELDS, references=[{'kind': 'ASSET', 'id': asset_id}],
                 objective='为秋季新品做一张克制的主视觉海报（修订）', expected_revision=1))
        if status != 201:
            raise RuntimeError(f'ASSISTANCE_REVISION_REFUSED {status} {revised}')
        status, chosen = self.call(
            'POST', f'/api/projects/{self.filled}/assistance-plans/{plan_id}/choose',
            {'actor': 'dtalex66', 'actor_kind': 'human', 'revision': 2})
        if status != 200:
            raise RuntimeError(f'ASSISTANCE_CHOICE_REFUSED {status} {chosen}')
        status, draft = self.call(
            'POST', f'/api/projects/{self.filled}/assistance-plans',
            dict(self.ASSISTANCE_FIELDS, neutral_creative=None,
                 objective='只有目标，还写不出创意'))
        if status != 201:
            raise RuntimeError(f'ASSISTANCE_DRAFT_REFUSED {status} {draft}')
        self.assistance = {
            'create': ('POST .../assistance-plans', created),
            'revise': ('POST .../assistance-plans/<id>/revisions appends revision 2', revised),
            'choose': ('POST .../assistance-plans/<id>/choose names a human', chosen),
            'detail': (f'GET .../assistance-plans/{plan_id}',
                       self.get(f'/api/projects/{self.filled}/assistance-plans/{plan_id}')),
            'draft': (f'GET .../assistance-plans/{draft["plan"]["plan_id"]} (saved, not provided)',
                      self.get(f'/api/projects/{self.filled}/assistance-plans'
                               f'/{draft["plan"]["plan_id"]}')),
            'list': ('GET .../assistance-plans',
                     self.get(f'/api/projects/{self.filled}/assistance-plans')),
            'list-empty': ('GET .../assistance-plans with nothing filed',
                           self.get(f'/api/projects/{self.empty}/assistance-plans')),
            'output-types': ('GET /api/assistance-plan-output-types (no project needed)',
                             self.get('/api/assistance-plan-output-types')),
            # DL-KB-12. Both revisions of the one plan above, read through the single-revision
            # route: r1 (not latest, not chosen -- the human adopted r2) and r2 (latest, chosen).
            # Two cases rather than one is the point of the route: a payload set that only ever
            # read the newest row would pass with an emitter that ignored the number it was given.
            'revision-older': (f'GET .../assistance-plans/{plan_id}/revisions/1 (the row r1 '
                               'actually stores, below the revision a human chose)',
                               self.get(f'/api/projects/{self.filled}/assistance-plans'
                                        f'/{plan_id}/revisions/1')),
            'revision-latest': (f'GET .../assistance-plans/{plan_id}/revisions/2 (the newest row, '
                                'the one a human adopted)',
                                self.get(f'/api/projects/{self.filled}/assistance-plans'
                                         f'/{plan_id}/revisions/2')),
        }
        self.assistance_plan_id = plan_id

    def assistance_cases(self, *names):
        return [self.assistance[name] for name in names]

    #: DL-KB-11: a plan that carries shot rows, because a 分镜 CSV rendered from an object with no
 #: rows would be a fabricated deliverable and the route refuses that (409 PLAN_EXPORT_NO_SHOTS).
    #: The purpose text of the second row holds a double quote, a comma and a newline on purpose --
    #: the same cell the unit test round-trips through csv.DictReader, arriving here as a real
    #: response body rather than as a fixture this file assembled.
    EXPORT_SEED_FIELDS = {
        'objective': '把秋季新品的主视觉做成一段十五秒的门店大屏动效',
        'output_type': 'MOTION',
        'neutral_creative': '侧光缓慢移动，标题以一次落定收束，全程留白承载品牌名。',
        'brand_constraints': ['只用两种油墨'],
        'role_constraints': ['面向线下门店大屏'],
        'lens': '固定机位为主，一次缓推',
        'sound': '无对白，一条低频垫底',
        'shots': [
            {'index': 1, 'duration_s': 4, 'purpose': '开场：侧光落在纸纤维上',
             'camera': '缓推', 'sound': None, 'reference_role': '主参考'},
            {'index': 2, 'duration_s': None,
             'purpose': '中景：标题落定，副标题带"引号"、逗号, 与\n换行的说明',
             'camera': None, 'sound': '低频垫底，无对白', 'reference_role': None},
        ],
        'references': [],
        'external_steps': [{'step': '手动导出 MP4', 'tool': 'After Effects',
                            'job_id': None, 'operation_id': 'op-plan-export'}],
        'known_gaps': ['节奏点未定'],
        'limits': ['不含多语言字幕', '不产出可编辑源文件'],
        'created_by': 'payload-contracts',
    }

    def _seed_plan_export(self):
        """File one shot-bearing plan and read all four materials back from the route."""
        from design_lab.plan_export import FORMATS
        status, created = self.call('POST', f'/api/projects/{self.filled}/assistance-plans',
                                    dict(self.EXPORT_SEED_FIELDS))
        if status != 201:
            raise RuntimeError(f'PLAN_EXPORT_SEED_REFUSED {status} {created}')
        plan_id = created['plan']['plan_id']
        self.exports = [(f'GET .../assistance-plans/{plan_id}/export?format={fmt}',
                         self.get(f'/api/projects/{self.filled}/assistance-plans'
                                  f'/{plan_id}/export?format={fmt}'))
                        for fmt in FORMATS]
        # The refusal is proven in design-lab/tests/test_plan_export.py rather than bound here: a
        # refusal answers {'error', 'detail'}, which is the shape every route in this repository
        # shares and no schema in this gate binds -- binding it would claim a document contract
        # that does not exist anywhere else.
        return plan_id

    def export_cases(self):
        return list(self.exports)

    TARGET_DRAFT_FIELDS = {
        'input_modality': {'state': 'DOCUMENTED', 'value': '文本', 'provenance': 'USER_FEEDBACK',
                            'source': 'owner 在面板里填写'},
        'ranges': {'state': 'UNKNOWN', 'value': None, 'provenance': 'USER_FEEDBACK',
                   'reason': '草稿没有记录时长范围'},
    }

    def _seed_target(self):
        """The five seeded profiles, one draft, and validations on a documented and an unreached row.

        Nothing here invents a capability: the seeded answers are the config's own bytes, and the
        two validation answers are chosen because they are the two branches the acceptance names --
        a documented incompatibility (FLUX.2 has no negative prompt) and an entry nobody reached
        (Meshy, whose four failed fetch attempts are recorded in its own row).
        """
        listing = self.get('/api/target-profiles')
        meshy = next(p for p in listing['profiles']
                     if p['profile_key'].startswith('meshy'))
        flux = next(p for p in listing['profiles']
                    if p['profile_key'].startswith('flux2'))
        if meshy['support_state'] != 'UNREACHED' or flux['support_state'] != 'DOCUMENTED_CLAIM':
            raise RuntimeError('TARGET_SEED_SHAPE_MOVED: the compared payloads would be guesses')
        status, created = self.call('POST', '/api/target-profiles', {
            # The route's whole accepted key set: `body()` compares sets, so a caller that omits
            # an axis is refused rather than silently storing a partial identity.
            'software': 'Payload 合同的草稿目标', 'agent': None, 'model': None,
            'provider': None, 'version': None, 'entry': 'DESKTOP_CLIENT',
            'task_mode': '海报排版', 'actor': 'payload-contracts',
            'source_ref': None, 'fields': dict(self.TARGET_DRAFT_FIELDS)})
        if status != 201:
            raise RuntimeError(f'TARGET_DRAFT_REFUSED {status} {created}')
        draft_id = created['profile']['profile_id']
        status, unknown_check = self.call(
            'POST', f'/api/target-profiles/{meshy["profile_id"]}/validate',
            {'dimensions': {'modality': 'image', 'asset_count': 1}})
        if status != 200:
            raise RuntimeError(f'TARGET_VALIDATE_UNKNOWN_REFUSED {status} {unknown_check}')
        status, documented_check = self.call(
            'POST', f'/api/target-profiles/{flux["profile_id"]}/validate',
            {'dimensions': {'negative_input': 'no people', 'asset_count': 9,
                            'parameter': 'guidance'}})
        if status != 200:
            raise RuntimeError(f'TARGET_VALIDATE_DOCUMENTED_REFUSED {status} {documented_check}')
        self.target = {
            'axes': ('GET /api/target-profile-axes (no project needed)',
                     self.get('/api/target-profile-axes')),
            'list': ('GET /api/target-profiles (seeded plus one draft)', listing),
            'detail-seed': (f'GET /api/target-profiles/<unreached meshy>',
                            self.get(f'/api/target-profiles/{meshy["profile_id"]}')),
            'detail-draft': (f'GET /api/target-profiles/<draft>',
                             self.get(f'/api/target-profiles/{draft_id}')),
            'create': ('POST /api/target-profiles (a marked-unverified draft)', created),
            'validate': ('POST /api/target-profiles/<id>/validate on a documented and an '
                         'unreached entry', unknown_check),
            'validate-documented': ('POST .../validate where the doc says "does not support"',
                                    documented_check),
        }

    def target_cases(self, *names):
        return [self.target[name] for name in names]

    def _seed_plan_feedback(self):
        """Two voluntary reports on one plan revision, plus the empty collection before them.

        The empty answer is compared as its own case: `total=0` and a non-empty `records` are
        different documents for the screen, and a list route that never gets read while empty would
        let an offline answer hide as "no reports yet".
        """
        plan_id = self.assistance['create'][1]['plan']['plan_id']
        base = f'/api/projects/{self.filled}/assistance-plans/{plan_id}/feedback'
        empty = self.get(base)
        if empty['total'] != 0 or empty['records']:
            raise RuntimeError(f'TARGET_FEEDBACK_NOT_EMPTY: {empty["total"]}')
        status, first = self.call('POST', base, {
            'outcome': 'MATCHES', 'target_key': 'elevenlabs--web-app--music',
            'target_model': 'eleven_v4', 'dimensions': [
                {'name': '曲风', 'verdict': 'MATCHES', 'note': None},
                {'name': '人声', 'verdict': 'DOES_NOT_MATCH', 'note': '不该有人声'}],
            'issue_timecodes': ['00:12-00:18'],
            'actor': 'dtalex66', 'note': '参考曲拿去 ElevenLabs 走了一遍，前 30 秒可用。',
            'source_ref': None, 'revision': 1})
        if status != 201:
            raise RuntimeError(f'FEEDBACK_FIRST_REFUSED {status} {first}')
        status, second = self.call('POST', base, {
            'outcome': 'PARTIALLY_MATCHES', 'target_key': 'elevenlabs--web-app--music',
            'target_model': None, 'dimensions': [], 'issue_timecodes': [],
            'actor': 'dtalex66', 'note': '同一目标第二次：结尾被模型填满了沉默，只部分符合。',
            'source_ref': 'op-77', 'revision': 2})
        if status != 201:
            raise RuntimeError(f'FEEDBACK_SECOND_REFUSED {status} {second}')
        self.feedback = {
            'list-empty': ('GET .../feedback with nothing recorded', empty),
            'record': ('POST .../feedback names a human and an outcome', first),
            'record-correction': ('POST .../feedback appends a second statement', second),
            'list': ('GET .../feedback after two reports', self.get(base)),
        }

    def feedback_cases(self, *names):
        return [self.feedback[name] for name in names]


    def design_write_cases(self, group):
        """The write answers of one route, each produced now, plus its idempotent replay.

        Two cases per row on purpose: the create/append branch and the replay branch are different
        code paths in the emitter (`SELECT ... WHERE operation_id=?` returning the stored row), and
        both are route answers a caller can receive. They are compared against the same envelope.
        """
        if group == 'briefs':
            return [self.post('POST .../briefs creates', f'/api/projects/{self.filled}/briefs',
                              dict(self.BRIEF_FIELDS, idempotency_key='case-brief-create')),
                    self.post('POST .../briefs replays the same key',
                              f'/api/projects/{self.filled}/briefs',
                              dict(self.BRIEF_FIELDS, idempotency_key='case-brief-create'))]
        if group == 'directions':
            brief_id = self.new_brief('case-direction-parent')
            body = dict(self.DIRECTION_FIELDS, brief_id=brief_id,
                        idempotency_key='case-direction-create')
            path = f'/api/projects/{self.filled}/directions'
            return [self.post('POST .../directions creates', path, body),
                    self.post('POST .../directions replays the same key', path, body)]
        if group == 'choose':
            brief_id = self.new_brief('case-choose-parent')
            direction_id = self.new_direction('case-choose-direction', brief_id)
            path = f'/api/projects/{self.filled}/directions/{direction_id}/choose'
            body = {'actor': 'dtalex66', 'actor_kind': 'human',
                    'idempotency_key': 'case-choose-once'}
            return [self.post('POST .../directions/<id>/choose records the human choice', path, body),
                    self.post('POST .../directions/<id>/choose replays the same key', path, body)]
        if group == 'bind':
            path = f'/api/projects/{self.filled}/directions/{self.dl_direction_tip}/bind'
            body = {'design_system_name': self.design_system,
                    'idempotency_key': f'case-bind-{secrets.token_hex(8)}'}
            return [self.post('POST .../directions/<id>/bind appends a binding version', path, body),
                    self.post('POST .../directions/<id>/bind replays the same key', path, body)]
        if group == 'brief-revisions-scoped':
            parent = self.new_brief('case-brief-rev-scoped-parent')
            path = f'/api/projects/{self.filled}/briefs/{parent}/revisions'
            body = dict(self.BRIEF_FIELDS, title='Family brief, revised in place',
                        idempotency_key='case-brief-rev-scoped')
            return [self.post('POST .../briefs/<id>/revisions appends', path, body),
                    self.post('POST .../briefs/<id>/revisions replays the same key', path, body)]
        if group == 'brief-revisions-by-id':
            parent = self.new_brief('case-brief-rev-byid-parent')
            path = f'/api/design-briefs/{parent}/revisions'
            body = dict(self.BRIEF_FIELDS, title='Family brief, revised by id',
                        idempotency_key='case-brief-rev-byid')
            return [self.post('POST /api/design-briefs/<id>/revisions appends', path, body),
                    self.post('POST /api/design-briefs/<id>/revisions replays the same key',
                              path, body)]
        if group == 'direction-revisions-scoped':
            brief_id = self.new_brief('case-direction-rev-scoped-brief')
            parent = self.new_direction('case-direction-rev-scoped-parent', brief_id)
            path = f'/api/projects/{self.filled}/directions/{parent}/revisions'
            body = dict(self.DIRECTION_FIELDS, title='Family direction, revised in place',
                        idempotency_key='case-direction-rev-scoped')
            return [self.post('POST .../directions/<id>/revisions appends', path, body),
                    self.post('POST .../directions/<id>/revisions replays the same key', path, body)]
        if group == 'direction-revisions-by-id':
            brief_id = self.new_brief('case-direction-rev-byid-brief')
            parent = self.new_direction('case-direction-rev-byid-parent', brief_id)
            path = f'/api/design-directions/{parent}/revisions'
            body = dict(self.DIRECTION_FIELDS, title='Family direction, revised by id',
                        idempotency_key='case-direction-rev-byid')
            return [self.post('POST /api/design-directions/<id>/revisions appends', path, body),
                    self.post('POST /api/design-directions/<id>/revisions replays the same key',
                              path, body)]
        raise AssertionError(f'no design-layer write cases for {group!r}')

    def __exit__(self, *exc):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            if self.thread is not None:
                self.thread.join(timeout=5)
        if self.saved_local_root is not None:
            os.environ['PROJECT_LOCAL_ROOT'] = self.saved_local_root
        shutil.rmtree(self.root, ignore_errors=True)
        return False

    def _publish(self, payload: bytes):
        asset_id, project_id = 'a1', self.filled
        store = self.service.paths.category_dir('projects', project_id, 'assets')
        incoming = Path(self.service.paths.runtime_root) / 'contract-incoming.psd'
        incoming.parent.mkdir(parents=True, exist_ok=True)
        incoming.write_bytes(payload)
        digest = 'sha256:' + hashlib.sha256(payload).hexdigest()
        with closing(self.assets.connect(self.service.database,
                                         project_root=self.service.paths.project_root)) as conn:
            conn.execute('INSERT INTO asset VALUES (?, ?, "psd", ?)',
                         (asset_id, project_id, '2026-10-08T00:00:00Z'))
            conn.commit()
            resource = f'asset:{asset_id}'
            if not self.assets.acquire_writer(conn, resource, 'attempt-contract'):
                raise RuntimeError('WRITER_LEASE_REFUSED')
            generation = self.assets.writer_token(conn, resource, 'attempt-contract')
            version_id = self.assets.publish_version(
                conn, asset_id, incoming, store_root=store, artifact_name='native.psd',
                expected_sha256=digest, holder_attempt_id='attempt-contract',
                generation=generation)
            self.assets.release_writer(conn, resource, 'attempt-contract', generation=generation)
        return version_id, digest

    def _file_jury_records(self):
        """A real human verdict and a real agent proposal, through the write routes."""
        criteria = [{'criterion_id': 'composition', 'weight': 0.4, 'score': 4.2, 'note': 'ok'},
                    {'criterion_id': 'typography', 'weight': 0.3, 'score': 3.8, 'note': 'ok'},
                    {'criterion_id': 'brand-fit', 'weight': 0.3, 'score': 4.0, 'note': 'ok'}]
        subject = f'{self.jury_store.SUBJECT_PREFIX}{self.version_id}'
        status, body = self.call('POST', f'/api/projects/{self.filled}/jury/verdict', {
            'schemaVersion': 'design-lab/assurance-jury-record/v2', 'kind': 'JURY_VERDICT',
            'jury_record_id': 'jury-contract-1', 'subject_ref': subject,
            'artifact_sha256': self.digest,
            'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN', 'members': [],
                      'attestation': 'reviewed the exported artwork at 100%'},
            'criteria': criteria, 'verdict': 'APPROVE',
            'decided_at': '2026-10-08T00:00:00Z', 'supersedes': None, 'evidence_refs': []})
        if status != 201:
            raise RuntimeError(f'VERDICT_WRITE_REFUSED {status} {body}')
        status, body = self.call('POST', f'/api/projects/{self.filled}/jury/proposal', {
            'schemaVersion': 'design-lab/assurance-jury-record/v2', 'kind': 'JURY_PROPOSAL',
            'proposal_id': 'proposal-contract-1', 'subject_ref': subject,
            'artifact_sha256': self.digest, 'proposer': 'qoder-agent', 'criteria': criteria,
            'suggested_verdict': 'APPROVE',
            'rationale': 'weighted score clears the floor; typography alignment holds',
            'created_at': '2026-10-08T00:00:00Z'})
        if status != 201:
            raise RuntimeError(f'PROPOSAL_WRITE_REFUSED {status} {body}')

    def call(self, method, path, body=None):
        headers = {'Authorization': 'Bearer ' + self.token}
        if body is not None:
            headers['Content-Type'] = 'application/json'
        with closing(http.client.HTTPConnection('127.0.0.1', self.httpd.server_port,
                                                timeout=30)) as conn:
            conn.request(method, path, body=None if body is None else json.dumps(body),
                         headers=headers)
            response = conn.getresponse()
            raw = response.read()
            return response.status, (json.loads(raw) if raw else None)

    def get(self, path):
        """The body this route wrote, serialised exactly as the client received it."""
        if path not in self._bodies:
            status, body = self.call('GET', path)
            if status != 200:
                raise RuntimeError(f'ROUTE_REFUSED {path} -> {status} {body}')
            self._bodies[path] = body
        return self._bodies[path]

    def fresh_root_rollup(self):
        """The same read on a checkout nothing has opened yet.

        A throwaway synthetic root gets only the base tables, so this is the branch where every
        unopened surface has to come back null and named in absentSurfaces -- the one distinction
        the contract refuses to swap, and the one this harness can never show from its own root,
        because the earlier cases already created those tables here.
        """
        from design_lab.project_index import ProjectIndex
        from design_lab.service import ProjectService

        temp = tempfile.TemporaryDirectory(dir=self.root)
        saved = os.environ.get('PROJECT_LOCAL_ROOT')
        try:
            fresh = Path(temp.name)
            (fresh / 'AGENTS.md').write_text('# synthetic unopened checkout', encoding='utf-8')
            os.environ['PROJECT_LOCAL_ROOT'] = str(fresh / '.project-local')
            service = ProjectService(str(fresh))
            service.create_project('Nothing Opened Yet')
            return ProjectIndex(service).list()
        finally:
            if saved is None:
                os.environ.pop('PROJECT_LOCAL_ROOT', None)
            else:
                os.environ['PROJECT_LOCAL_ROOT'] = saved
            temp.cleanup()


#: name -> the route it serves, the schema that binds it, the emitter that writes the version,
#: and the real payloads to compare. Adding a row is how the next unschema'd payload gets
#: caught; a row whose files are missing, or whose route refuses, is red -- not skipped.
def build_bindings():
    return [
        {
            'name': 'path-diagnostic',
            'route': '/api/environment',
            'method': 'GET',
            'schema': 'design-lab/schemas/path-diagnostic.schema.json',
            'emitter': 'src/design_lab/runtime/paths.py',
            'version': 'design-lab/path-diagnostic/v1',
            'cases': lambda h: [('GET /api/environment', h.get('/api/environment'))],
        },
        {
            'name': 'capability-library',
            'route': '/api/capabilities',
            'method': 'GET',
            'schema': 'design-lab/schemas/capability-library.schema.json',
            'emitter': 'src/design_lab/analysis/capability_library.py',
            'version': 'design-lab/capability-library/v1',
            'cases': lambda h: [('GET /api/capabilities', h.get('/api/capabilities'))],
        },
        {
            'name': 'project-list',
            'route': '/api/projects',
            'method': 'GET',
            'schema': 'design-lab/schemas/project-list-v1.schema.json',
            'emitter': 'src/design_lab/project_index.py',
            'version': 'design-lab/project-list/v1',
            # Two real branches, both from live bytes: this checkout, where several surfaces have
            # been opened by earlier cases so their counts are integers; and a throwaway root where
            # only the base tables exist, so every unopened surface has to come back null and named
            # in absentSurfaces. A schema that only fit the populated branch would be a nicer
            # document than the code.
            'cases': lambda h: [
                ('GET /api/projects on this checkout', h.get('/api/projects')),
                ('GET /api/projects on a checkout nothing has opened', h.fresh_root_rollup()),
            ],
        },
        {
            'name': 'task-readback-list',
            'route': r'/api/projects/([0-9a-f]{32})/tasks(?:\?after=((?:native-)?job-[0-9a-f]{64}))?',
            'method': 'GET',
            'schema': 'design-lab/schemas/task-readback-v1.schema.json',
            'emitter': 'src/design_lab/task_queries.py',
            'version': 'design-lab/task-readback/v1',
            'cases': lambda h: h.task_readback_cases()[:2],
        },
        {
            'name': 'task-readback-detail',
            'route': '/api/projects/([0-9a-f]{32})/tasks/((?:native-)?job-[0-9a-f]{64})'
                     r'(/events)?(?:\?after=([0-9]{1,16}))?',
            'method': 'GET',
            'schema': 'design-lab/schemas/task-readback-v1.schema.json',
            'emitter': 'src/design_lab/task_queries.py',
            'version': 'design-lab/task-readback/v1',
            # One envelope, two surfaces: the detail read and the event page differ only in which
            # payload key they carry, and the contract refuses a surface shipping the other one's.
            'cases': lambda h: h.task_readback_cases()[2:],
        },
        {
            'name': 'domain-pack-readback',
            'route': '/api/domains',
            'method': 'GET',
            'schema': 'design-lab/schemas/domain-pack-readback.schema.json',
            'emitter': 'src/design_lab/domain_packs.py',
            'version': 'design-lab/domain-pack-readback/v1',
            'cases': lambda h: [('GET /api/domains', h.get('/api/domains'))],
        },
        {
            'name': 'jury-readback',
            'route': '/api/projects/([0-9a-f]{32})/jury',
            'method': 'GET',
            'schema': 'design-lab/schemas/jury-readback.schema.json',
            'emitter': 'src/design_lab/jury_review.py',
            'version': 'design-lab/jury-readback/v1',
            # Both branches the emitter can produce: a filed review and an empty one. A schema
            # that only fits the populated case would be nicer than the code.
            'cases': lambda h: [
                ('GET .../jury with a verdict and a proposal', h.get(f'/api/projects/{h.filled}/jury')),
                ('GET .../jury with nothing filed', h.get(f'/api/projects/{h.empty}/jury')),
            ],
        },
        {
            'name': 'brief-readback',
            'route': '/api/projects/([0-9a-f]{32})/briefs(?:\\?after=(brief-[0-9a-f]{32}))?',
            'method': 'GET',
            'schema': 'design-lab/schemas/brief-readback.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/brief-readback/v1',
            # A project whose brief was created AND revised (two versioned rows, a live chain)
            # against a project that has never had one. The empty branch is the one a page must
            # not be able to read as a failure, and the populated branch carries a reference id
            # that only exists because the writer accepted a real asset of the same project.
            'cases': lambda h: [
                ('GET .../briefs with a revised brief', h.get(f'/api/projects/{h.filled}/briefs')),
                ('GET .../briefs with nothing filed', h.get(f'/api/projects/{h.empty}/briefs')),
            ],
        },
        {
            'name': 'evidence-projection',
            'route': '/api/evidence-projection',
            'method': 'GET',
            'schema': 'design-lab/schemas/evidence-projection.schema.json',
            'emitter': 'src/design_lab/governance/evidence_readback.py',
            'version': 'design-lab/evidence-projection/v1',
            # The readback is recomputed per call over the checkout the server is running from, so the
            # payload compared here is the ledger's own state at this commit -- not a fixture. Calling
            # it twice is deliberate: two answers for one subject would mean the readback is not a
            # function of the bytes it claims to describe.
            'cases': lambda h: [
                ('GET /api/evidence-projection', h.get('/api/evidence-projection')),
                ('GET /api/evidence-projection again', h.get('/api/evidence-projection')),
            ],
        },
        {
            'name': 'task-resource-preflight',
            'route': '/api/task-preflight',
            'method': 'GET',
            'schema': 'design-lab/schemas/task-resource-preflight.schema.json',
            'emitter': 'src/design_lab/runtime/task_resources.py',
            'version': 'design-lab/task-resource-preflight/v1',
            # Three real tasks: tools only (one absent from PATH), a host declaration plus a
            # tool, and a blocked task. Together they reach every resource branch the emitter has.
            'cases': lambda h: [
                ('GET ?task=DLDS-H020', h.get('/api/task-preflight?task='
                                              'DL-TP-20260914-DEEPSEEK-AUTHORITY-R1%3A%3ADLDS-H020')),
                ('GET ?task=DL-R5-012', h.get('/api/task-preflight?task='
                                              'DL-TP-20260914-DEEPSEEK-AUTHORITY-R1%3A%3ADL-R5-012')),
                ('GET ?task=DL-R5-008', h.get('/api/task-preflight?task='
                                              'DL-TP-20260914-DEEPSEEK-AUTHORITY-R1%3A%3ADL-R5-008')),
            ],
        },
        {
            'name': 'model-catalog',
            'route': '/api/models',
            'method': 'GET',
            'schema': 'design-lab/schemas/model-catalog-v1.schema.json',
            'emitter': 'src/design_lab/model_catalog.py',
            'version': 'design-lab/model-catalog/v1',
            # The picker document the owner asked for on 2026-10-20 (「不锁死 做好菜单导航和接口
            # 用户自行选择本地或者是云端模型」). Its rows are copied from the two registries the
            # repository keeps, so what is compared here is a recount of those files, not a fixture:
            # the fail-closed counters (qualified_local, default_enabled_true, weights_recorded) are
            # the page's only defence against a readiness chip the registry does not support, and
            # they are bound here as invariants against the rows they summarise.
            'cases': lambda h: [('GET /api/models', h.get('/api/models'))],
        },
        {
            'name': 'model-selection-readback',
            'route': '/api/projects/([0-9a-f]{32})/model-selection',
            'method': 'GET',
            'schema': 'design-lab/schemas/model-selection-readback-v1.schema.json',
            'emitter': 'src/design_lab/model_selection.py',
            'version': 'design-lab/model-selection-readback/v1',
            # All three states the envelope exists to keep apart, each from a real row: a pick made
            # through the write route, an explicit 「不用」, and a project nobody has asked. Two of
            # them look the same in an empty list, which is exactly the misreading the schema
            # forbids by binding `state`, `selection` and `revision_count` together.
            'cases': lambda h: [
                ('GET .../model-selection after a pick',
                 h.get(f'/api/projects/{h.filled}/model-selection')),
                ('GET .../model-selection after a declination',
                 h.get(f'/api/projects/{h.declined}/model-selection')),
                ('GET .../model-selection never asked',
                 h.get(f'/api/projects/{h.empty}/model-selection')),
            ],
        },
        {
            'name': 'knowledge-candidate-export',
            'route': '/api/projects/([0-9a-f]{32})/knowledge-candidates'
                     '/([A-Za-z0-9_.:-]{1,80})/export',
            'method': 'GET',
            'schema': 'design-lab/schemas/assurance-knowledge-candidate-export-envelope-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_review.py',
            'version': 'design-lab/assurance-knowledge-candidate-export-envelope/v1',
            # The envelope `export_payload` never had a version of: it wraps two bound projections
            # ($defs/export and candidate-knowledge v1) and said nothing about itself. Now it says
            # schemaVersion, and the schema keeps the honesty half of the claim machine-checked --
            # transport NOT_CONNECTED, sent_count 0, and a provenance echo that can only be a
            # supplied id or the literal UNUSED.
            'cases': lambda h: [('GET .../export of an approved candidate',
                                 h.get(f'/api/projects/{h.filled}/knowledge-candidates'
                                       f'/{h.candidate_id}/export'))],
        },
        {
            'name': 'rights-readback',
            'route': '/api/projects/([0-9a-f]{32})/rights',
            'method': 'GET',
            'schema': 'design-lab/schemas/rights-readback.schema.json',
            'emitter': 'src/design_lab/rights_review.py',
            'version': 'design-lab/rights-readback/v1',
            # Three real clearances, not three copies of one: a project that reads CLEARED, a
            # project where a human refused one scope, and a project nobody filed. The empty read
            # is the branch that tempts an emitter into reporting 0-of-0 as cleared, so it is
            # compared against the same required fields rather than a lenient variant.
            'cases': lambda h: [
                ('GET .../rights after one APPROVED scope',
                 h.get(f'/api/projects/{h.filled}/rights')),
                ('GET .../rights with an APPROVED and a DENIED scope',
                 h.get(f'/api/projects/{h.declined}/rights')),
                ('GET .../rights with nothing filed',
                 h.get(f'/api/projects/{h.empty}/rights')),
            ],
        },
        {
            'name': 'research-readback',
            'route': '/api/projects/([0-9a-f]{32})/research',
            'method': 'GET',
            'schema': 'design-lab/schemas/research-readback.schema.json',
            'emitter': 'src/design_lab/research_review.py',
            'version': 'design-lab/research-readback/v1',
            # A superseded chain and an empty project. The envelope is bound to `research_verdict:
            # null` on purpose: this surface publishes counts because writing findings down clears
            # no gate, and an emitter that starts inventing a completion word has to change the
            # contract first.
            'cases': lambda h: [
                ('GET .../research with a superseded finding',
                 h.get(f'/api/projects/{h.declined}/research')),
                ('GET .../research with nothing filed',
                 h.get(f'/api/projects/{h.empty}/research')),
            ],
        },
        {
            'name': 'native-runtime-readback',
            'route': '/api/projects/([0-9a-f]{32})/native-runtime',
            'method': 'GET',
            'schema': 'design-lab/schemas/native-runtime-readback.schema.json',
            'emitter': 'src/design_lab/native_runtime.py',
            'version': 'design-lab/native-runtime-readback/v1',
            # The absent/present split is the whole reason this route exists, so both sides are
            # compared, and in that order -- the first read happens before any native table was
            # created by the attempt chain seeded below it.
            'cases': lambda h: h.native_runtime_cases(),
        },
        {
            'name': 'prompt-result-readback',
            'route': '/api/projects/([0-9a-f]{32})/prompt-results',
            'method': 'GET',
            'schema': 'design-lab/schemas/prompt-result-readback-v1.schema.json',
            'emitter': 'src/design_lab/prompt_results.py',
            'version': 'design-lab/prompt-result-readback/v1',
            # The gap this closes is that a prompt used to exist only in the response body. Three
            # states are compared because they are three different sentences: a stored result a
            # named human accepted, a stored result nobody signed, and a project where nothing was
            # ever produced. NOT_CURRENT is in the vocabulary as the corruption branch -- no write
            # path can create it today, since a review copies the digest out of the stored row --
            # and this file does not pretend to have observed it.
            'cases': lambda h: [
                ('GET .../prompt-results with an accepted composition',
                 h.get(f'/api/projects/{h.filled}/prompt-results')),
                ('GET .../prompt-results with an unreviewed composition',
                 h.get(f'/api/projects/{h.declined}/prompt-results')),
                ('GET .../prompt-results with nothing produced',
                 h.get(f'/api/projects/{h.empty}/prompt-results')),
            ],
        },
        # ---- the design-layer family, paid 2026-10-23 (batch I) ------------------------------
        # Seventeen routes that answered with a wrapper carrying no version of their own. The
        # objects below are not a fixture vocabulary: each one is produced by posting to the write
        # routes with the same field sets the page and the write sweep send, and what is compared is
        # the answer the route wrote. Two families of branch are deliberately doubled out --
        # the live tip versus a superseded member of the same chain, and a project that holds
        # something versus a project that holds nothing -- because those are the readings a page
        # can silently confuse and the only ones an empty list cannot show.
        {
            'name': 'design-layer-rollup',
            'route': '/api/projects/([0-9a-f]{32})/design-layer',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-layer-rollup-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-layer-rollup/v1',
            'cases': lambda h: [
                ('GET .../design-layer with a chosen and bound direction',
                 h.get(f'/api/projects/{h.filled}/design-layer')),
                ('GET .../design-layer of a project with nothing filed',
                 h.get(f'/api/projects/{h.empty}/design-layer')),
            ],
        },
        {
            'name': 'design-record-brief-detail',
            'route': '/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: [
                ('GET .../briefs/<id> of the live tip',
                 h.get(f'/api/projects/{h.filled}/briefs/{h.dl_brief_tip}')),
                ('GET .../briefs/<id> of a superseded version',
                 h.get(f'/api/projects/{h.filled}/briefs/{h.dl_brief_v1}')),
            ],
        },
        {
            'name': 'design-record-direction-detail',
            'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            # The chosen direction and its superseded parent are two different answers: only one of
            # them carries actor, actor_kind and chosen=true, which is the whole record of the
            # Human Gate decision. A schema that could not tell them apart would let a page read an
            # unchosen version as the choice.
            'cases': lambda h: [
                ('GET .../directions/<id> of the chosen tip',
                 h.get(f'/api/projects/{h.filled}/directions/{h.dl_direction_tip}')),
                ('GET .../directions/<id> of the superseded version',
                 h.get(f'/api/projects/{h.filled}/directions/{h.dl_direction_v1}')),
            ],
        },
        {
            'name': 'design-collection-directions',
            'route': '/api/projects/([0-9a-f]{32})/directions(?:\\?after=(direction-[0-9a-f]{32}))?',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-collection-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-collection/v1',
            'cases': lambda h: [
                ('GET .../directions with two versions filed',
                 h.get(f'/api/projects/{h.filled}/directions')),
                ('GET .../directions with nothing filed',
                 h.get(f'/api/projects/{h.empty}/directions')),
            ],
        },
        {
            'name': 'design-collection-tokens',
            'route': '/api/projects/([0-9a-f]{32})/design-system-tokens',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-collection-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-collection/v1',
            # The branch the discriminator exists for: this collection has NO next_cursor, because
            # the reader takes every live row. Compared against a project with a document and one
            # without, so an emitter that grew a cursor field here would be convicted rather than
            # flattered.
            'cases': lambda h: [
                ('GET .../design-system-tokens with one live document',
                 h.get(f'/api/projects/{h.filled}/design-system-tokens')),
                ('GET .../design-system-tokens with none',
                 h.get(f'/api/projects/{h.empty}/design-system-tokens')),
            ],
        },
        {
            'name': 'design-collection-systems',
            'route': '/api/design-systems',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-collection-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-collection/v1',
            # The catalog rows are the same objects the roll-up serves under design_layer
            # .design_systems -- which is exactly why this route needed its own binding: two routes
            # answering one shape must be compared against the SAME document from both sides, or
            # the roll-up's copy quietly becomes the only place the shape is judged. One case is
            # honest here: catalog() has no empty branch to show -- the packaged manifests are
            # either in the build or the product has no design systems at all.
            'cases': lambda h: [('GET /api/design-systems', h.get('/api/design-systems'))],
        },
        {
            'name': 'design-lineage-brief-scoped',
            'route': '/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})/lineage',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-lineage-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-lineage/v1',
            # Asked from the tip and from the superseded member: the chain is resolved through the
            # revision events, so any member must return the same two versions with the same
            # root_id and live_id. One id asked twice, two answers, is the defect this pair catches.
            'cases': lambda h: [
                ('GET .../briefs/<tip>/lineage',
                 h.get(f'/api/projects/{h.filled}/briefs/{h.dl_brief_tip}/lineage')),
                ('GET .../briefs/<superseded>/lineage',
                 h.get(f'/api/projects/{h.filled}/briefs/{h.dl_brief_v1}/lineage')),
            ],
        },
        {
            'name': 'design-lineage-direction-scoped',
            'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/lineage',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-lineage-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-lineage/v1',
            'cases': lambda h: [
                ('GET .../directions/<tip>/lineage',
                 h.get(f'/api/projects/{h.filled}/directions/{h.dl_direction_tip}/lineage')),
                ('GET .../directions/<superseded>/lineage',
                 h.get(f'/api/projects/{h.filled}/directions/{h.dl_direction_v1}/lineage')),
            ],
        },
        {
            'name': 'design-lineage-brief-by-id',
            'route': '/api/design-briefs/(brief-[0-9a-f]{32})/lineage',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-lineage-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-lineage/v1',
            # The id-scoped twin of the project-scoped read: same document, owner resolved from the
            # record itself. Both ends of the chain are fed to it because the emitter has to reach
            # the same lineage from either.
            'cases': lambda h: [
                ('GET /api/design-briefs/<tip>/lineage',
                 h.get(f'/api/design-briefs/{h.dl_brief_tip}/lineage')),
                ('GET /api/design-briefs/<superseded>/lineage',
                 h.get(f'/api/design-briefs/{h.dl_brief_v1}/lineage')),
            ],
        },
        {
            'name': 'design-lineage-direction-by-id',
            'route': '/api/design-directions/(direction-[0-9a-f]{32})/lineage',
            'method': 'GET',
            'schema': 'design-lab/schemas/design-lineage-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-lineage/v1',
            'cases': lambda h: [
                ('GET /api/design-directions/<tip>/lineage',
                 h.get(f'/api/design-directions/{h.dl_direction_tip}/lineage')),
                ('GET /api/design-directions/<superseded>/lineage',
                 h.get(f'/api/design-directions/{h.dl_direction_v1}/lineage')),
            ],
        },
        {
            'name': 'design-record-brief-create',
            'route': '/api/projects/([0-9a-f]{32})/briefs',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: h.design_write_cases('briefs'),
        },
        {
            'name': 'design-record-direction-create',
            'route': '/api/projects/([0-9a-f]{32})/directions',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: h.design_write_cases('directions'),
        },
        {
            'name': 'design-record-direction-choose',
            'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/choose',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            # The Human Gate's own answer. Binding it says nothing about who may choose -- the
            # emitter refuses a non-human actor_kind with 403 HUMAN_DIRECTION_CHOICE_REQUIRED before
            # it writes -- it binds what the caller is handed back once that refusal has passed.
            'cases': lambda h: h.design_write_cases('choose'),
        },
        {
            'name': 'design-record-direction-bind',
            'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/bind',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: h.design_write_cases('bind'),
        },
        {
            'name': 'design-record-brief-revise-scoped',
            'route': '/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})/revisions',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: h.design_write_cases('brief-revisions-scoped'),
        },
        {
            'name': 'design-record-direction-revise-scoped',
            'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/revisions',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: h.design_write_cases('direction-revisions-scoped'),
        },
        {
            'name': 'design-record-brief-revise-by-id',
            'route': '/api/design-briefs/(brief-[0-9a-f]{32})/revisions',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: h.design_write_cases('brief-revisions-by-id'),
        },
        {
            'name': 'design-record-direction-revise-by-id',
            'route': '/api/design-directions/(direction-[0-9a-f]{32})/revisions',
            'method': 'POST',
            'schema': 'design-lab/schemas/design-record-v1.schema.json',
            'emitter': 'src/design_lab/design_layer.py',
            'version': 'design-lab/design-record/v1',
            'cases': lambda h: h.design_write_cases('direction-revisions-by-id'),
        },
        # DL-KB-02/04 (batch K, 2026-10-23). Every payload below is the answer the product
        # produced to a real request through a real socket; the entry, its revision and the
        # import were written by the routes themselves, not assembled here.
        {
            'name': 'knowledge-library-search',
            'route': '/api/knowledge-entries/search',
            'method': 'GET',
            'schema': 'design-lab/schemas/knowledge-library-readback-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_library.py',
            'version': 'design-lab/knowledge-library/v1',
            # The query is 分镜 -- two characters, which the trigram index cannot answer, so the
            # compared payload is the fallback's answer rather than one the index alone produced.
            'cases': lambda h: h.knowledge_cases('search'),
        },
        {
            'name': 'knowledge-entry-write-create',
            'route': '/api/knowledge-entries',
            'method': 'POST',
            'schema': 'design-lab/schemas/knowledge-entry-write-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_library.py',
            'version': 'design-lab/knowledge-entry-write/v1',
            'cases': lambda h: h.knowledge_cases('create'),
        },
        {
            'name': 'knowledge-entry-write-revise',
            'route': '/api/knowledge-entries/(kentry-[0-9a-f]{32})/revisions',
            'method': 'POST',
            'schema': 'design-lab/schemas/knowledge-entry-write-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_library.py',
            'version': 'design-lab/knowledge-entry-write/v1',
            # Revision 2 is written with recommended:false, so this is the branch a client
            # reads as "the newest bytes are not the recommended ones".
            'cases': lambda h: h.knowledge_cases('revise'),
        },
        {
            'name': 'knowledge-entry-import',
            'route': '/api/knowledge-entries/import',
            'method': 'POST',
            'schema': 'design-lab/schemas/knowledge-import-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_library.py',
            'version': 'design-lab/knowledge-import/v1',
            # Both answers: the first import writes, the second is recognised as a duplicate
            # with no write. A schema that only fit the created branch would be a nicer document
            # than the code.
            'cases': lambda h: h.knowledge_cases('import', 'import-replay'),
        },
        {
            'name': 'knowledge-entry-readback',
            'route': '/api/knowledge-entries/(kentry-[0-9a-f]{32})',
            'method': 'GET',
            'schema': 'design-lab/schemas/knowledge-entry-readback-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_library.py',
            'version': 'design-lab/knowledge-entry-readback/v1',
            'cases': lambda h: h.knowledge_cases('detail'),
        },
        {
            'name': 'knowledge-entry-judgement',
            'route': '/api/knowledge-entries/(kentry-[0-9a-f]{32})/judgements',
            'method': 'POST',
            'schema': 'design-lab/schemas/knowledge-entry-readback-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_library.py',
            'version': 'design-lab/knowledge-entry-readback/v1',
            # The same readback the GET serves, reached through the write that moved it: one case
            # with a recorded recommendation, one with a dead source and its replacement.
            'cases': lambda h: h.knowledge_cases('judgement', 'judgement-source'),
        },
        {
            'name': 'knowledge-index-rebuild',
            'route': '/api/knowledge-entries/index-rebuild',
            'method': 'POST',
            'schema': 'design-lab/schemas/knowledge-index-rebuild-v1.schema.json',
            'emitter': 'src/design_lab/knowledge_library.py',
            'version': 'design-lab/knowledge-index-rebuild/v1',
            'cases': lambda h: h.knowledge_cases('rebuild'),
        },
        # DL-KB-07 (batch K3, 2026-10-24). A plan is written through the routes and read back
        # through them; the referenced asset is a real stored version of the same project, and
        # its status in the compared payload is the readback's own measurement (LINKED_ONLY --
        # no reversal exists), not a value this file supplied.
        {
            'name': 'assistance-plan-write-create',
            'route': '/api/projects/([0-9a-f]{32})/assistance-plans',
            'method': 'POST',
            'schema': 'design-lab/schemas/assistance-plan-write-v1.schema.json',
            'emitter': 'src/design_lab/assistance_plan.py',
            'version': 'design-lab/assistance-plan-write/v1',
            'cases': lambda h: h.assistance_cases('create'),
        },
        {
            'name': 'assistance-plan-write-revise',
            'route': '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/revisions',
            'method': 'POST',
            'schema': 'design-lab/schemas/assistance-plan-write-v1.schema.json',
            'emitter': 'src/design_lab/assistance_plan.py',
            'version': 'design-lab/assistance-plan-write/v1',
            'cases': lambda h: h.assistance_cases('revise'),
        },
        {
            'name': 'assistance-plan-readback',
            'route': '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})',
            'method': 'GET',
            'schema': 'design-lab/schemas/assistance-plan-readback-v1.schema.json',
            'emitter': 'src/design_lab/assistance_plan.py',
            'version': 'design-lab/assistance-plan-readback/v1',
            # Three readings of the same shape: a plan with a creative, a choice and a linked
            # asset; a draft with no creative (saved, not provided); and the answer the choose
            # route returns, which is the same readback rather than a second envelope.
            'cases': lambda h: h.assistance_cases('detail', 'draft', 'choose'),
        },
        {
            'name': 'assistance-plan-list',
            'route': '/api/projects/([0-9a-f]{32})/assistance-plans(?:\\?[^#]*)?',
            'method': 'GET',
            'schema': 'design-lab/schemas/assistance-plan-list-v1.schema.json',
            'emitter': 'src/design_lab/assistance_plan.py',
            'version': 'design-lab/assistance-plan-list/v1',
            'cases': lambda h: h.assistance_cases('list', 'list-empty'),
        },
        # DL-KB-08. Read with no project in the path on purpose: the initial screen offers an
        # output type before a workspace exists, so the vocabulary cannot be verified only on
        # the project-scoped collection.
        {
            'name': 'assistance-plan-output-types',
            'route': '/api/assistance-plan-output-types',
            'method': 'GET',
            'schema': 'design-lab/schemas/assistance-plan-output-types-v1.schema.json',
            'emitter': 'src/design_lab/assistance_plan.py',
            'version': 'design-lab/assistance-plan-output-types/v1',
            'cases': lambda h: h.assistance_cases('output-types'),
        },
        {
            'name': 'assistance-plan-choose',
            'route': '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/choose',
            'method': 'POST',
            'schema': 'design-lab/schemas/assistance-plan-readback-v1.schema.json',
            'emitter': 'src/design_lab/assistance_plan.py',
            'version': 'design-lab/assistance-plan-readback/v1',
            'cases': lambda h: h.assistance_cases('choose'),
        },
        # DL-KB-12 (2026-10-24): one stored revision, read back as its own bytes. Two real answers
        # from the same two-revision plan, because the defect this route exists to prevent is a
        # comparison page reading the newest revision twice: the older case is the only payload here
        # whose `revision` is below `latest_revision` and whose `document` is not the readback's
        # `current`, and the newest case is the one a named human chose. The envelope $refs the plan
        # document rather than restating it, so these two payloads also compare the stored document
        # against the contract the write path filed it under.
        {
            'name': 'assistance-plan-revision',
            'route': '/api/projects/([0-9a-f]{32})/assistance-plans'
                     r'/(aplan-[0-9a-f]{32})/revisions/([1-9][0-9]{0,8})',
            'method': 'GET',
            'schema': 'design-lab/schemas/assistance-plan-revision-v1.schema.json',
            'emitter': 'src/design_lab/assistance_plan.py',
            'version': 'design-lab/assistance-plan-revision/v1',
            'cases': lambda h: h.assistance_cases('revision-older', 'revision-latest'),
        },
        # DL-KB-11 (2026-10-24): the handoff material. Four real answers from one plan, because the
        # card's B4 is that the three prose materials carry the same content -- and the only way to
        # compare them is to have the route produce all four. The CSV case is the fourth one, and it
        # exists only because this plan has shot rows: the same route refuses a plan without them.
        {
            'name': 'plan-export',
            'route': '/api/projects/([0-9a-f]{32})/assistance-plans'
                     r'/(aplan-[0-9a-f]{32})/export(?:\?[^#]*)?',
            'method': 'GET',
            'schema': 'design-lab/schemas/plan-export-v1.schema.json',
            'emitter': 'src/design_lab/plan_export.py',
            'version': 'design-lab/plan-export/v1',
            'cases': lambda h: h.export_cases(),
        },
        # DL-KB-09 (2026-10-24): the target profile registry. The five seeded answers are the
        # tracked config's own bytes, so a payload here is a real read of what the registry claims
        # and where it says it does not know -- not a fixture written to match the schema.
        {
            'name': 'target-profile-axes',
            'route': '/api/target-profile-axes',
            'method': 'GET',
            'schema': 'design-lab/schemas/target-profile-axes-v1.schema.json',
            'emitter': 'src/design_lab/target_profile.py',
            'version': 'design-lab/target-profile-axes/v1',
            'cases': lambda h: h.target_cases('axes'),
        },
        {
            'name': 'target-profile-list',
            'route': r'/api/target-profiles(?:\?[^#]*)?',
            'method': 'GET',
            'schema': 'design-lab/schemas/target-profile-list-v1.schema.json',
            'emitter': 'src/design_lab/target_profile.py',
            'version': 'design-lab/target-profile-list/v1',
            'cases': lambda h: h.target_cases('list'),
        },
        {
            'name': 'target-profile-detail',
            'route': r'/api/target-profiles/(tprof-[0-9a-f]{32})',
            'method': 'GET',
            'schema': 'design-lab/schemas/target-profile-v1.schema.json',
            'emitter': 'src/design_lab/target_profile.py',
            'version': 'design-lab/target-profile/v1',
            'cases': lambda h: h.target_cases('detail-seed', 'detail-draft'),
        },
        {
            'name': 'target-profile-create',
            'route': '/api/target-profiles',
            'method': 'POST',
            'schema': 'design-lab/schemas/target-profile-write-v1.schema.json',
            'emitter': 'src/design_lab/target_profile.py',
            'version': 'design-lab/target-profile-write/v1',
            'cases': lambda h: h.target_cases('create'),
        },
        {
            'name': 'target-profile-validate',
            'route': r'/api/target-profiles/(tprof-[0-9a-f]{32})/validate',
            'method': 'POST',
            'schema': 'design-lab/schemas/target-profile-validate-v1.schema.json',
            'emitter': 'src/design_lab/target_profile.py',
            'version': 'design-lab/target-profile-validate/v1',
            'cases': lambda h: h.target_cases('validate', 'validate-documented'),
        },
        # DL-KB-16 (2026-10-24): the voluntary external-use reports. The empty list, one record and
        # the correction are three different answers, and the second record is what proves the
        # history is append-only rather than a mutable current marker.
        {
            'name': 'plan-feedback-list',
            'route': (r'/api/projects/([0-9a-f]{32})/assistance-plans/'
                      r'(aplan-[0-9a-f]{32})/feedback(?:\?[^#]*)?'),
            'method': 'GET',
            'schema': 'design-lab/schemas/plan-feedback-list-v1.schema.json',
            'emitter': 'src/design_lab/plan_feedback.py',
            'version': 'design-lab/plan-feedback-list/v1',
            'cases': lambda h: h.feedback_cases('list-empty', 'list'),
        },
        {
            'name': 'plan-feedback-record',
            'route': (r'/api/projects/([0-9a-f]{32})/assistance-plans/'
                      r'(aplan-[0-9a-f]{32})/feedback'),
            'method': 'POST',
            'schema': 'design-lab/schemas/plan-feedback-write-v1.schema.json',
            'emitter': 'src/design_lab/plan_feedback.py',
            'version': 'design-lab/plan-feedback-write/v1',
            'cases': lambda h: h.feedback_cases('record', 'record-correction'),
        },
    ]


def registry():
    """Every schema in design-lab/schemas that carries an $id, so a $ref resolves to its owner.

    assurance-jury-record-v2.schema.json is in this set: the readback envelope references the
    record instead of restating it, which is the only way this file can stay honest when the
    record's own contract moves.

    design-lab/schemas/contracts/ is loaded second and only for ids nothing else claims. The
    rights decision lives there (design-lab/schemas/contracts/rights-decision.schema.json is the
    file rights_ledger.py actually validates writes against), and a readback that restated those
    fields would be a second authority able to disagree with the write path -- so the owner's own
    document has to be reachable. Loading it after the top-level set keeps every resolution an
    existing binding already relies on exactly as it was.
    """
    resources, docs = [], {}
    for path in sorted(SCHEMA_DIR.rglob('*.schema.json')):
        if 'contracts' in path.parts:
            continue
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get('$id'), str):
            continue
        if doc['$id'] in docs:
            continue
        resources.append((doc['$id'], referencing.Resource.from_contents(doc)))
        docs[doc['$id']] = doc
    for path in sorted((SCHEMA_DIR / 'contracts').glob('*.schema.json')):
        try:
            doc = json.loads(path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            continue
        if not isinstance(doc, dict) or not isinstance(doc.get('$id'), str):
            continue
        if doc['$id'] in docs:
            continue
        resources.append((doc['$id'], referencing.Resource.from_contents(doc)))
        docs[doc['$id']] = doc
    return referencing.Registry(resources), docs


def resolve_ref(ref: str, docs: dict, current_root):
    """`$ref` -> (owning document, subschema), for `$defs` walking and drift comparison."""
    base, _, fragment = ref.partition('#')
    doc = docs.get(base) if base else current_root
    if not isinstance(doc, dict):
        return None, None
    node = doc
    for part in [p for p in fragment.split('/') if p]:
        part = part.replace('~1', '/').replace('~0', '~')
        if not isinstance(node, dict) or part not in node:
            return None, None
        node = node[part]
    return doc, node



def absolutise(node, base_id: str):
    """A copy of `node` with every relative `$ref` rewritten against `base_id`.

    An ``anyOf`` branch is tested on its own to decide which branch a real payload actually
    satisfies, and a bare ``{"$ref": "#/$defs/toolResource"}`` has no base URI of its own --
    jsonschema then reports PointerToNowhere and the branch would be skipped, silently
    switching the nested drift check off. Rewriting makes the probe self-contained.
    """
    if isinstance(node, dict):
        out = {}
        for key, value in node.items():
            if key == '$ref' and isinstance(value, str) and value.startswith('#'):
                out[key] = f'{base_id}{value}'
            else:
                out[key] = absolutise(value, base_id)
        return out
    if isinstance(node, list):
        return [absolutise(item, base_id) for item in node]
    return node


def strip_required(node):
    """A copy of a subschema with every object-level `required` list removed, recursively.

    The branch filter must decide which variant a payload's SHAPE is, not which variant the
    schema currently claims is complete: if a mutation adds a bogus `required` to one branch,
    filtering on the mutated branch would drop that branch from the comparison and the drift
    would go silent. Discriminators (`const`/`enum` on `kind`, `state`) are kept, so a host
    resource still fails the tool branch on shape alone.

    `not` / `if` / `then` / `else` are copied untouched. assurance-jury-record-v2 refuses a
    verdict carrying proposal fields with `{"not": {"required": [...]}}`; stripping inside that
    would leave `{"not": {}}`, which rejects every instance, and the filter would then report
    that no branch fits a perfectly good record.
    """
    if isinstance(node, dict):
        return {key: (value if key in ('not', 'if', 'then', 'else') else strip_required(value))
                for key, value in node.items() if key != 'required'}
    if isinstance(node, list):
        return [strip_required(item) for item in node]
    return node


def branch_probe(branch, root_doc, docs):
    """(subschema with absolute refs, owner id) for one combinator branch."""
    owner = root_doc if isinstance(root_doc, dict) else {}
    node = branch
    if isinstance(node, dict) and isinstance(node.get('$ref'), str):
        base, resolved = resolve_ref(node['$ref'], docs, root_doc)
        if resolved is None:
            return None, None
        node, owner = resolved, base
    ident = owner.get('$id') if isinstance(owner, dict) else None
    if not isinstance(ident, str):
        return None, None
    return absolutise(node, ident), ident


def comparisons(schema, instance, path, out, docs, root_doc, reg):
    """Pair every object location the instance reaches with the schema node that binds it."""
    if not isinstance(schema, dict):
        return out
    if '$ref' in schema:
        base, node = resolve_ref(schema['$ref'], docs, root_doc)
        if node is None:
            return out
        root_doc = base
        schema = node
    if isinstance(instance, dict):
        if isinstance(schema.get('properties'), dict):
            props = schema['properties']
            required = set(schema.get('required') or [])
            out.append({'path': path, 'required': required, 'declared': set(props),
                        'produced': set(instance),
                        'closed': schema.get('additionalProperties') is False})
            for key, subschema in props.items():
                if key in instance:
                    comparisons(subschema, instance[key], f'{path}.{key}', out, docs,
                                root_doc, reg)
        for key, value in instance.items():
            # A map value (tools.*, roots.*, shared_inputs.*, current_verdicts.*) is bound by
            # additionalProperties or by a patternProperty, not by a named property, and it is
            # exactly where a state word or a required field goes missing.
            node = schema.get('additionalProperties')
            if isinstance(node, dict):
                comparisons(node, value, f'{path}.*', out, docs, root_doc, reg)
            pattern_map = schema.get('patternProperties')
            if isinstance(pattern_map, dict):
                for _pattern, pattern_node in pattern_map.items():
                    comparisons(pattern_node, value, f'{path}.*', out, docs, root_doc, reg)
        for combinator in ('allOf', 'anyOf', 'oneOf'):
            branches = schema.get(combinator) or []
            if not branches:
                continue
            # allOf branches all apply, so each is compared. For anyOf/oneOf only the branches
            # whose SHAPE the real payload satisfies are compared, otherwise a host resource
            # would be reported as "missing resolved_path". If no branch matches, every branch
            # is compared rather than none: silence is the one outcome this gate may not produce.
            selected = list(branches)
            if combinator != 'allOf':
                matched = []
                for branch in branches:
                    probe, _ident = branch_probe(branch, root_doc, docs)
                    if probe is None:
                        continue
                    try:
                        if jsonschema.Draft202012Validator(strip_required(probe),
                                                           registry=reg).is_valid(instance):
                            matched.append(branch)
                    except Exception:  # noqa: BLE001 - an unusable probe compares everything
                        matched.append(branch)
                if matched:
                    selected = matched
            for index, branch in enumerate(branches):
                if branch not in selected:
                    continue
                comparisons(branch, instance, f'{path}#{combinator}[{index}]', out, docs,
                            root_doc, reg)
    if isinstance(instance, list) and isinstance(schema.get('items'), dict):
        for index, item in enumerate(instance):
            comparisons(schema['items'], item, f'{path}[{index}]', out, docs, root_doc, reg)
    return out


def drift_errors(name, schema, payload, case_label, docs, reg):
    errors = []
    for node in comparisons(schema, payload, '$', [], docs, schema, reg):
        missing = sorted(node['required'] - node['produced'])
        if missing:
            errors.append(f'{name}/{case_label}@{node["path"]}: MISSING_FROM_EMITTER {missing} '
                          '-- the schema requires fields the route did not send')
        if node['closed']:
            extra = sorted(node['produced'] - node['declared'])
            if extra:
                errors.append(f'{name}/{case_label}@{node["path"]}: UNDECLARED_BY_SCHEMA '
                              f'{extra} -- the route sends fields a closed schema does not declare')
    return errors


def version_literals(path: Path, version: str) -> int:
    """How many times this source handles the version as a value it produces or compares."""
    try:
        tree = ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
    except (OSError, SyntaxError):
        return 0
    return sum(1 for node in ast.walk(tree)
               if isinstance(node, ast.Constant) and node.value == version)


def schema_const(doc):
    return ((doc.get('properties') or {}).get('schemaVersion') or {}).get('const')


def ledger_route_rows():
    doc = json.loads((REPO / LEDGER_REL).read_text(encoding='utf-8'))
    return doc.get('routes') or []


def ledger_errors(binding, rows):
    """Rule 5: the ledger row and this binding must describe the same boundary."""
    matches = [row for row in rows if row.get('route') == binding['route']]
    if not matches:
        return [f'{binding["name"]}: LEDGER_DISAGREES no route row for {binding["route"]} -- '
                f'this payload is validated here but the ledger does not account for it']
    row = matches[0]
    errors = []
    if row.get('kind') != 'BOUND_SCHEMA':
        errors.append(f'{binding["name"]}: LEDGER_DISAGREES {binding["route"]} is listed as '
                      f'{row.get("kind")!r} while its payload is validated against '
                      f'{Path(binding["schema"]).name} here -- the debt is paid, the ledger '
                      'says it is not')
    if row.get('schema') != binding['schema']:
        errors.append(f'{binding["name"]}: LEDGER_DISAGREES the row binds {row.get("schema")!r}, '
                      f'not {binding["schema"]!r}')
    if row.get('version') != binding['version']:
        errors.append(f'{binding["name"]}: LEDGER_DISAGREES the row declares '
                      f'{row.get("version")!r} while the schema and the emitter bind '
                      f'{binding["version"]!r}')
    emitter = (row.get('emitter') or '').split(':', 1)[0]
    if emitter != binding['emitter']:
        errors.append(f'{binding["name"]}: LEDGER_DISAGREES the row names emitter {emitter!r}, '
                      f'not {binding["emitter"]!r}')
    return errors


def unvalidated_binding_errors(bindings, rows):
    """Rule 5, the other direction, keyed on the ROUTE.

    A ledger may not point any route at one of these schemas -- not even a second route that
    happens to serve the same document -- unless a real response from that route is fed to it
    here. Set membership on the schema alone would let `.../briefs` claim to be bound by
    jury-readback.schema.json because `.../jury` already is, which is the declared-but-unread
    shape this surface exists to name.
    """
    covered = {(binding['route'], binding['schema']) for binding in bindings}
    claims = {(row.get('route'), row.get('schema')) for row in rows
              if row.get('kind') == 'BOUND_SCHEMA'
              and row.get('schema') in {schema for _route, schema in covered}}
    return [f'UNVALIDATED_BINDING {route} is declared BOUND_SCHEMA against {schema} with no '
            'payload binding in design-lab/scripts/verify_route_payload_contracts.py -- a schema '
            'nobody feeds a real response to is a reader-visible claim of enforcement'
            for route, schema in sorted(claims - covered)]


def check_binding(binding, harness=None, docs=None, reg=None, rows=None,
                  schema_doc=None, cases=None):
    """Every check for one binding. `schema_doc`, `cases` and `rows` are injectable so the
    teeth of this gate can be falsified against a weakened COPY without touching a shipped
    file or rebooting the server; `cases=None` means "ask the live route", which is what the
    shipped run does."""
    errors, notes = [], []
    schema_path = REPO / binding['schema']
    emitter_path = REPO / binding['emitter']
    if not schema_path.is_file():
        return [f'{binding["name"]}: NOTHING_TO_COMPARE schema {binding["schema"]} does not '
                'exist -- this row names debt that was never written down'], notes
    if not emitter_path.is_file():
        return [f'{binding["name"]}: NOTHING_TO_COMPARE emitter {binding["emitter"]} does not '
                'exist'], notes
    if schema_doc is None:
        schema = json.loads(schema_path.read_text(encoding='utf-8'))
    else:
        schema = schema_doc
        if not schema_path.is_file():
            return [f'{binding["name"]}: NOTHING_TO_COMPARE schema is absent'], notes
    if docs is None or reg is None:
        reg, docs = registry()
    try:
        jsonschema.Draft202012Validator.check_schema(schema)
    except jsonschema.SchemaError as exc:
        return [f'{binding["name"]}: the schema is not a valid draft 2020-12 document: {exc.message}'], notes

    const = schema_const(schema)
    if const != binding['version']:
        errors.append(f'{binding["name"]}: VERSION_DRIFT {Path(binding["schema"]).name} binds '
                      f'{const!r} while this gate declares {binding["version"]!r}')
    elif not version_literals(emitter_path, const):
        errors.append(f'{binding["name"]}: VERSION_DRIFT {binding["emitter"]} no longer carries '
                      f'{const!r} as a value it produces or compares -- one side moved and the '
                      'other did not')

    if rows is None:
        rows = ledger_route_rows()
    errors.extend(ledger_errors(binding, rows))

    if cases is None:
        try:
            cases = list(binding['cases'](harness))
        except Exception as exc:  # noqa: BLE001 - a refused route is a finding, not a skip
            return errors + [f'{binding["name"]}: NOTHING_TO_COMPARE the route refused: '
                             f'{type(exc).__name__} {exc}'], notes
    normalised = []
    for item in cases:
        try:
            label, payload = item
        except (TypeError, ValueError):
            errors.append(f'{binding["name"]}: NOTHING_TO_COMPARE the case producer returned '
                          f'{item!r}, which is not a (label, payload) pair -- nothing was '
                          'compared for it')
            continue
        normalised.append((label, payload))
    cases = normalised
    if not cases:
        if not errors:
            errors.append(f'{binding["name"]}: NOTHING_TO_COMPARE -- no payload was produced, '
                          'so this binding proves nothing')
    validator = jsonschema.Draft202012Validator(schema, registry=reg)
    compared = 0
    for label, payload in cases:
        if not isinstance(payload, dict) or not payload:
            errors.append(f'{binding["name"]}/{label}: NOTHING_TO_COMPARE -- the route returned '
                          'no mapping to check')
            continue
        nodes = comparisons(schema, payload, '$', [], docs, schema, reg)
        if not nodes:
            errors.append(f'{binding["name"]}/{label}: NOTHING_TO_COMPARE -- the schema declares '
                          'no object location this payload reaches')
            continue
        compared += len(nodes)
        if not any(node['required'] for node in nodes):
            errors.append(f'{binding["name"]}/{label}: NOTHING_TO_COMPARE -- no schema node '
                          'requires anything, so a wrong payload would sail through')
        for error in sorted(validator.iter_errors(payload),
                            key=lambda e: list(e.absolute_path)):
            spot = '/'.join(str(part) for part in error.absolute_path) or '<root>'
            errors.append(f'{binding["name"]}/{label}@{spot}: SCHEMA_VIOLATION {error.message[:300]}')
        errors.extend(drift_errors(binding['name'], schema, payload, label, docs, reg))
    notes.append(f'{binding["name"]}: cases={len(cases)} object locations compared={compared}')
    return errors, notes


def run(bindings=None):
    effective = build_bindings() if bindings is None else list(bindings)
    if not effective:
        return (['NOTHING_TO_COMPARE: no route payload binding is declared at all -- a gate with '
                 'no case cannot catch a drift'], [])
    rows = ledger_route_rows()
    errors, notes = list(unvalidated_binding_errors(effective, rows)), []
    reg, docs = registry()
    with Harness() as harness:
        for binding in effective:
            case_errors, case_notes = check_binding(binding, harness=harness, docs=docs,
                                                    reg=reg, rows=rows)
            errors.extend(case_errors)
            notes.extend(case_notes)
    return errors, notes


def main(argv=None) -> int:
    errors, notes = run()
    for note in notes:
        print('  compared', note)
    for error in errors:
        print('ERROR:', error)
    # The verdict is the LAST line and starts with VERIFY_ on purpose: verify_design_lab.py
    # summarises each gate by scanning its output from the end for a line starting with VERIFY_.
    print(f'VERIFY_ROUTE_PAYLOAD_CONTRACTS={"FAIL" if errors else "PASS"} '
          f'bindings={len(build_bindings())} failures={len(errors)}')
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
