# SPDX-License-Identifier: MIT
"""Walk every POST row the contract ledger declares, against objects this service really wrote.

The read side got this treatment first (`test_standalone_chain_http.GET_READS`): every ledger GET
row is called, and what cannot be called is named. The write side had never been measured that way.
Per-route POST tests exist, but each one seeds its own fixture and imports `src` from the checkout,
so "every write route answers inside the installed package" was never a claim anything held open --
a POST row could keep answering 500 in a wheel while its own module stayed green.

The table is asserted in both directions against `design-lab/config/contract-bindings.json`, so a
POST route added to the ledger must be walked here or explicitly refused here. Every walked row is
read back through a GET route, because a POST that returns 201 without the written object being
reachable is a claim about a response body, not about the service.
"""
from __future__ import annotations

import base64
import hashlib
import http.client
import io
import json
import os
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT / 'design-lab' / 'tests') not in sys.path:
    sys.path.insert(0, str(ROOT / 'design-lab' / 'tests'))
# Only the package resolution changes under the flag -- the same rule the read sweep applies.
INSTALLED_MODE = os.environ.get('DL_LAUNCH_INSTALLED') == '1'
if not INSTALLED_MODE and str(ROOT / 'src') not in sys.path:
    sys.path.insert(0, str(ROOT / 'src'))

# The module is imported, not its class: a `TestCase` that lands in this namespace would be
# collected a second time every run of this file, inflating the suite with the read sweep's cases.
import test_standalone_chain_http as chain  # noqa: E402

LEDGER = 'design-lab/config/contract-bindings.json'

TOKENS = {'color': {'$type': 'color', 'brand': {'$value': '#2563EB'},
                   'surface': {'$value': '{color.brand}'}},
          'scale': {'$type': 'dimension', 'space': {'md': {'$value': '16px'}}}}

#: DL-KB-02 (batch K). One knowledge entry, written by the create route and then revised,
#: imported and indexed by the three write routes beside it. The source is the same vocabulary
#: SourceRecord uses, with UNKNOWN where a person said nothing -- the store's own relaxation, and
#: the reason this body is a real request instead of a shortcut around the contract.
KNOWLEDGE_SOURCE = {'sourceId': 'sweep-knowledge', 'origin': 'UNKNOWN', 'author': 'sweep',
                    'license': 'UNKNOWN', 'licenseStatus': 'unknown',
                    'allowedUsage': 'UNKNOWN', 'citationScope': 'UNKNOWN', 'version': '1',
                    'observedAt': '2026-10-23T00:00:00Z', 'contentHash': 'UNKNOWN',
                    'verification': 'UNVERIFIED'}
KNOWLEDGE_ENTRY = {
    'entry_type': 'METHOD', 'title': '分镜拆解三步法',
    'summary': '把一段脚本拆成镜头表：先定节拍，再定景别，最后定转场。',
    'domain_tags': ['film'], 'task_tags': ['storyboard'], 'target_tools': ['storyboarder'],
    'body': '第一步按段落切节拍。第二步给每个节拍选景别。第三步只标必要的转场。',
    'applicability': '适合 30-90 秒短片的分镜前置。',
    'limits': '不适用于需要精确口型对位的动画。',
    'source': KNOWLEDGE_SOURCE, 'related_capability_ids': [], 'recommended': True,
    'created_by': 'sweep', 'supersedes': None,
}

#: DL-KB-07 (batch K). One neutral plan, its second revision and a named human's choice. The
#: reference names only `{kind, id}`: the store resolves the revision and digest from the live
#: object, so the body states neither. External ids are left out (the store writes UNUSED) or
#: supplied literally, never minted here.
ASSISTANCE_PLAN = {
    'objective': '为秋季新品做一张克制的主视觉海报',
    'output_type': 'IMAGE',
    'neutral_creative': '一束侧光穿过纸纤维，留出大面积空白承载标题。',
    'brand_constraints': ['只用两种油墨'], 'role_constraints': [],
    'lens': None, 'sound': None,
    'references': [{'kind': 'ASSET', 'id': '{asset}'}],
    'external_steps': [{'step': '手动导出印刷 PDF', 'tool': 'Illustrator',
                        'job_id': None, 'operation_id': 'op-sweep-1024'}],
    'known_gaps': ['目标纸张未定'], 'limits': ['未包含多语言排版'],
    'created_by': 'sweep',
}

_SLOT = re.compile(r'\{(\w+)\}')


def _fill(value, slots):
    """Substitute `{slot}` through a path or body.

    A string that is exactly one placeholder is replaced by the slot value itself, so a document
    slot stays a document instead of becoming `repr()` of one. `\\w+` cannot match `{color.brand}`,
    so a DTCG alias inside a token document survives substitution rather than being read as a slot.
    """
    if isinstance(value, str):
        whole = _SLOT.fullmatch(value)
        if whole and whole.group(1) in slots:
            return slots[whole.group(1)]
        return _SLOT.sub(lambda match: str(slots.get(match.group(1), match.group(0))), value)
    if isinstance(value, dict):
        return {key: _fill(child, slots) for key, child in value.items()}
    if isinstance(value, list):
        return [_fill(child, slots) for child in value]
    return value


def _unfilled(value):
    """Slot names a row still asks for after substitution -- a red, not a literal request."""
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False)
    return sorted(set(_SLOT.findall(text)))


def _dig(payload, dotted, route):
    """Read a captured slot out of a response, refusing to invent it when the field is absent."""
    node = payload
    for part in dotted.split('.'):
        if not isinstance(node, dict) or part not in node:
            raise AssertionError(f'{route} answered without the field this sweep captures '
                                 f'`{dotted}` from: '
                                 f'{json.dumps(payload, ensure_ascii=False)[:300]}')
        node = node[part]
    return node


def _png_bytes() -> bytes:
    stream = io.BytesIO()
    from PIL import Image
    Image.new('RGB', (8, 6), 'white').save(stream, format='PNG')
    return stream.getvalue()


def _post_rows(ledger):
    """Every ledger row this sweep owes an answer for: any method string carrying POST."""
    return [row['route'] for row in ledger['routes'] if 'POST' in row['method']]


def _coverage(rows, walked, excluded):
    """Routes the ledger declares with no entry here, and entries here for rows it no longer has."""
    named = set(walked) | set(excluded)
    return sorted(set(rows) - named), sorted(named - set(rows))


def _refusal_diff(refused, allowed):
    """5xx that appeared without being earned, and named refusals that did not happen."""
    return (sorted(f'{route} -> {code} (answered here, not earned)'
                   for route, (status, code) in refused.items()
                   if allowed.get(route) != (status, code)),
            sorted(f'{route} -> {allowed[route]} (named, never answered)'
                   for route in allowed if route not in refused))


class InstalledWriteSurfaceTests(unittest.TestCase):
    """One server, one project, every POST row, in the order the objects depend on each other."""

    # Borrowed whole: the temp root, the token, the server and the installed-layout guard are the
    # same harness the read sweep runs on, so a layout that silently imports the checkout fails
    # here exactly as it fails there.
    setUp = chain.StandaloneChainTests.setUp
    call = chain.StandaloneChainTests.call

    #: 5xx this sweep may see, per layout. Empty in a source checkout: every POST row is answered
    #: there. An entry for the installed layout is only allowed after the refusal has been read,
    #: and the list is compared in both directions -- a refusal that stops happening is as stale as
    #: one that appears unearned, and an unused entry would excuse the next one.
    EXPECTED_REFUSALS = {
        'source': {},
        'installed': {},
    }

    #: Rows deliberately not POSTed, each with the reason. A body this sweep *could* build is not
    #: the same as a write it is allowed to perform, so the two kinds are named apart.
    EXCLUDED = {
        '/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/run':
            'FROZEN-BY-POLICY: the body is one attempt_id and this sweep has one, but '
            'native_workers.start() spawns a child process running `design_lab native-worker`, '
            'which dispatches to a real creative host. Host execution stays frozen (owner '
            '2026-10-19 and 2026-10-21) and this batch promises no real host or model run, so the '
            'row is recorded as not walked rather than walked under a patch that would no longer '
            'be the route the desktop calls.',
    }

    #: Each row: the ledger route, the concrete POST, the status that counts as written, the slots
    #: to capture out of the answer, and the read-back. Order is the dependency order.
    WRITES = (
        {'route': '/api/projects', 'label': 'project', 'status': 201,
         'path': '/api/projects', 'body': {'name': 'Write sweep'},
         'capture': {'project': 'project.id'}, 'check': 'check_project'},
        {'route': '/api/projects/([0-9a-f]{32})/assets', 'label': 'asset', 'status': 201,
         'path': '/api/projects/{project}/assets',
         'body': {'content_base64': '{png}', 'idempotency_key': 'sweep-asset'},
         'capture': {'asset': 'asset.id', 'asset_version': 'asset.version_id',
                     'asset_sha256': 'asset.sha256'},
         'check': 'check_asset'},
        {'route': '/api/projects/([0-9a-f]{32})/briefs', 'label': 'brief', 'status': 201,
         'path': '/api/projects/{project}/briefs',
         'body': {'title': 'Sweep brief', 'goals': ['write sweep'], 'constraints': None,
                  'reference_asset_ids': ['{asset}'], 'idempotency_key': 'sweep-brief'},
         'capture': {'brief': 'brief.brief_id'}, 'check': 'check_brief'},
        {'route': '/api/projects/([0-9a-f]{32})/directions', 'label': 'direction', 'status': 201,
         'path': '/api/projects/{project}/directions',
         'body': {'brief_id': '{brief}', 'title': 'Sweep direction',
                  'style_notes': ['measured'], 'color_mood': 'warm', 'typography_mood': 'sans',
                  'idempotency_key': 'sweep-direction'},
         'capture': {'direction': 'direction.direction_id'}, 'check': 'check_direction'},
        {'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/choose',
         'label': 'choose', 'status': 200,
         'path': '/api/projects/{project}/directions/{direction}/choose',
         'body': {'actor': 'dtalex66', 'actor_kind': 'human',
                  'idempotency_key': 'sweep-choose'},
         'check': 'check_choose'},
        {'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/bind',
         'label': 'bind', 'status': 201,
         'path': '/api/projects/{project}/directions/{direction}/bind',
         'body': {'design_system_name': '{system}', 'idempotency_key': 'sweep-bind'},
         'capture': {'binding': 'binding.binding_id'}, 'check': 'check_bind'},
        {'route': '/api/projects/([0-9a-f]{32})/design-system-tokens/(<DESIGN_SYSTEM_NAME_PATTERN>)',
         'label': 'tokens', 'status': 201,
         'path': '/api/projects/{project}/design-system-tokens/{system}',
         'body': {'document': TOKENS, 'expected_version': 0, 'actor': 'ALEX',
                  'actor_kind': 'human', 'idempotency_key': 'a' * 64},
         'capture': {'token_document': 'token_document.token_document_id'},
         'check': 'check_tokens'},
        {'route': '/api/projects/([0-9a-f]{32})/assets/(img-[0-9a-f]{64})/analysis',
         'label': 'analysis', 'status': 201,
         'path': '/api/projects/{project}/assets/{asset}/analysis',
         'body': {'module': 'ocr-fixture', 'decomposition_id': None,
                  'detections': [{'text': 'SWEEP', 'confidence': 0.81,
                                  'polygon': [[1, 1], [4, 1], [4, 3], [1, 3]]}]},
         'check': 'check_analysis'},
        {'route': '/api/projects/([0-9a-f]{32})/model-selection/choose', 'label': 'model-choose',
         'status': 201, 'path': '/api/projects/{project}/model-selection/choose',
         'body': {'model_id': '{model}', 'declared_unused': False,
                  'actor': 'sweep-operator', 'actor_kind': 'human'},
         'check': 'check_model_choice'},
        {'route': '/api/projects/([0-9a-f]{32})/prompts', 'label': 'compose', 'status': 201,
         'path': '/api/projects/{project}/prompts',
         'body': {'brief_id': '{brief}', 'direction_id': '{direction}',
                  'target': 'image-generation'},
         'capture': {'composition': 'document.composition_id',
                     'composition_sha': 'document_sha256'},
         'check': 'check_composition'},
        {'route': '/api/projects/([0-9a-f]{32})/assets/(img-[0-9a-f]{64})/prompt-reversal',
         'label': 'reverse', 'status': 201,
         'path': '/api/projects/{project}/assets/{asset}/prompt-reversal',
         'body': {'module': 'ocr-fixture', 'decomposition_id': None,
                  'detections': [{'text': 'SWEEP', 'confidence': 0.81,
                                  'polygon': [[1, 1], [4, 1], [4, 3], [1, 3]]}]},
         'capture': {'reversal': 'document.reversal_id'}, 'check': 'check_reversal'},
        {'route': ('/api/projects/([0-9a-f]{32})/prompt-results'
                   '/((?:prompt|reversal)-[0-9a-f]{32})/review'),
         'label': 'prompt-sign', 'status': 201,
         'path': '/api/projects/{project}/prompt-results/{composition}/review',
         'body': {'decision': 'ACCEPTED', 'reviewer': 'dtalex66', 'reviewer_kind': 'human',
                  'reviewed_at': '2026-10-22T00:00:00Z',
                  'note': 'signed against the digest this sweep published'},
         'check': 'check_prompt_signature'},
        {'route': '/api/projects/([0-9a-f]{32})/jury/verdict', 'label': 'jury-verdict',
         'status': 201, 'path': '/api/projects/{project}/jury/verdict',
         'body': {'schemaVersion': 'design-lab/assurance-jury-record/v2',
                  'kind': 'JURY_VERDICT', 'jury_record_id': 'jury-sweep-1',
                  'subject_ref': 'version:{asset_version}', 'artifact_sha256': '{asset_sha256}',
                  'juror': {'juror_id': 'dtalex66', 'kind': 'HUMAN', 'members': [],
                            'attestation': 'reviewed the imported artwork'},
                  'criteria': '{criteria}', 'verdict': 'APPROVE',
                  'decided_at': '2026-10-22T00:00:00Z', 'supersedes': None, 'evidence_refs': []},
         'check': 'check_jury_verdict'},
        {'route': '/api/projects/([0-9a-f]{32})/jury/proposal', 'label': 'jury-proposal',
         'status': 201, 'path': '/api/projects/{project}/jury/proposal',
         'body': {'schemaVersion': 'design-lab/assurance-jury-proposal/v2',
                  'kind': 'JURY_PROPOSAL', 'proposal_id': 'prop-sweep-1',
                  'subject_ref': 'version:{asset_version}', 'artifact_sha256': '{asset_sha256}',
                  'proposer': 'review-agent', 'criteria': '{criteria}',
                  'suggested_verdict': 'APPROVE', 'rationale': 'weighted mean above the floor',
                  'created_at': '2026-10-22T00:00:00Z'},
         'check': 'check_jury_proposal'},
        {'route': ('/api/projects/([0-9a-f]{32})/rights'
                   '(?:\\?supersedes=([A-Za-z0-9_.:-]{1,80}))?'),
         'label': 'rights', 'status': 201, 'path': '/api/projects/{project}/rights',
         'body': '{rights_decision}', 'check': 'check_rights'},
        {'route': ('/api/projects/([0-9a-f]{32})/research'
                   '(?:\\?supersedes=([A-Za-z0-9_.:-]{1,80}))?'),
         'label': 'research', 'status': 201, 'path': '/api/projects/{project}/research',
         'body': '{research_finding}', 'check': 'check_research'},
        {'route': ('/api/projects/([0-9a-f]{32})/knowledge-candidates'
                   '(?:\\?supersedes=([A-Za-z0-9_.:-]{1,80}))?'),
         'label': 'candidate', 'status': 201, 'prepare': 'prepare_candidate',
         'path': '/api/projects/{project}/knowledge-candidates',
         'body': '{candidate}', 'capture': {'candidate': 'candidate_id'},
         'check': 'check_candidate_pending'},
        {'route': ('/api/projects/([0-9a-f]{32})/knowledge-candidates'
                   '/([A-Za-z0-9_.:-]{1,80})/review'),
         'label': 'candidate-review', 'status': 200,
         'path': '/api/projects/{project}/knowledge-candidates/{candidate}/review',
         'body': {'decision': 'APPROVE', 'reviewer_id': 'dtalex66', 'reviewer_kind': 'human',
                  'reviewed_at': '2026-10-22T00:00:00Z', 'note': None, 'reason': None},
         'check': 'check_candidate_approved'},
        {'route': ('/api/projects/([0-9a-f]{32})/knowledge-candidates'
                   '/([A-Za-z0-9_.:-]{1,80})/revoke'),
         'label': 'candidate-revoke', 'status': 200,
         'path': '/api/projects/{project}/knowledge-candidates/{candidate}/revoke',
         'body': {'reason': 'this sweep withdraws its own record', 'revoked_by': 'dtalex66',
                  'revoked_at': '2026-10-22T00:00:00Z'},
         'check': 'check_candidate_revoked'},
        {'route': '/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})/revisions',
         'label': 'brief-rev', 'status': 201,
         'path': '/api/projects/{project}/briefs/{brief}/revisions',
         'body': {'title': 'Sweep brief v2', 'goals': ['write sweep', 'second'],
                  'constraints': None, 'reference_asset_ids': ['{asset}'],
                  'idempotency_key': 'sweep-brief-rev'},
         'capture': {'brief_v2': 'brief.brief_id'}, 'check': 'check_brief_revision'},
        {'route': '/api/design-briefs/(brief-[0-9a-f]{32})/revisions',
         'label': 'brief-rev-by-id', 'status': 201,
         'path': '/api/design-briefs/{brief_v2}/revisions',
         'body': {'title': 'Sweep brief v3', 'goals': ['write sweep'], 'constraints': None,
                  'reference_asset_ids': ['{asset}'], 'idempotency_key': 'sweep-brief-by-id'},
         'capture': {'brief_v3': 'brief.brief_id'}, 'check': 'check_brief_revision_by_id'},
        {'route': '/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/revisions',
         'label': 'direction-rev', 'status': 201,
         'path': '/api/projects/{project}/directions/{direction}/revisions',
         'body': {'title': 'Sweep direction v2', 'style_notes': ['measured', 'warmer'],
                  'color_mood': 'cool', 'typography_mood': 'sans',
                  'idempotency_key': 'sweep-direction-rev'},
         'capture': {'direction_v2': 'direction.direction_id'},
         'check': 'check_direction_revision'},
        {'route': '/api/design-directions/(direction-[0-9a-f]{32})/revisions',
         'label': 'direction-rev-by-id', 'status': 201,
         'path': '/api/design-directions/{direction_v2}/revisions',
         'body': {'title': 'Sweep direction v3', 'style_notes': ['measured'],
                  'color_mood': 'warm', 'typography_mood': 'serif',
                  'idempotency_key': 'sweep-direction-by-id'},
         'capture': {'direction_v3': 'direction.direction_id'},
         'check': 'check_direction_revision_by_id'},
        {'route': '/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/bundle',
         'label': 'bundle', 'status': 201, 'prepare': 'prepare_native_attempt',
         'path': '/api/projects/{project}/tasks/{job}/bundle', 'body': {},
         'capture': {'bundle': 'bundle.id', 'bundle_version': 'bundle.version_id',
                     'bundle_sha256': 'bundle.sha256'},
         'check': 'check_bundle'},
        {'route': ('/api/projects/([0-9a-f]{32})/bundles/(bundle-native-[0-9a-f]{64})/preflight'
                   '(?:\\?profile=(print|digital|video))?'),
         'label': 'preflight', 'status': 200,
         'path': '/api/projects/{project}/bundles/{bundle}/preflight', 'body': {},
         'check': 'check_preflight'},
        {'route': '/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/patch',
         'label': 'patch', 'status': 202, 'path': '/api/projects/{project}/tasks/{job}/patch',
         'body': {'source_attempt_id': '{attempt}', 'idempotency_key': 'sweep-patch',
                  'patch': {'kind': 'text', 'id': 'title', 'text': 'After'}},
         'capture': {'patched_attempt': 'task.attempt.attempt_id', 'patched_job': 'task.job_id'},
         'check': 'check_patch'},
        {'route': '/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/cancel',
         'label': 'cancel', 'status': 202,
         'path': '/api/projects/{project}/tasks/{patched_job}/cancel',
         'body': {'attempt_id': '{patched_attempt}'}, 'check': 'check_cancel'},
        {'route': '/api/projects/([0-9a-f]{32})/native-plans', 'label': 'native-plan',
         'status': 202, 'path': '/api/projects/{project}/native-plans',
         'body': {'host': 'photoshop', 'rir': '{rir}', 'text_styles': {},
                  'idempotency_key': 'sweep-plan'},
         'capture': {'plan_job': 'task.job_id'}, 'check': 'check_native_plan'},
        # DL-KB-02 (batch K): the library's three writes and its index rebuild. None is
        # project-scoped -- the library is global like /api/capabilities -- so the paths carry no
        # {project} slot.
        {'route': '/api/knowledge-entries', 'label': 'knowledge-create', 'status': 201,
         'path': '/api/knowledge-entries', 'body': KNOWLEDGE_ENTRY,
         'capture': {'kentry': 'entry.knowledge_entry_id'}, 'check': 'check_knowledge_create'},
        {'route': '/api/knowledge-entries/(kentry-[0-9a-f]{32})/revisions',
         'label': 'knowledge-revise', 'status': 201,
         'path': '/api/knowledge-entries/{kentry}/revisions',
         'body': {key: value for key, value in KNOWLEDGE_ENTRY.items()
                  if key not in ('created_by', 'supersedes')}
                 | {'title': '分镜拆解三步法（修订）', 'recommended': False,
                    'created_by': 'sweep', 'expected_revision': 1},
         'check': 'check_knowledge_revision'},
        {'route': '/api/knowledge-entries/import', 'label': 'knowledge-import', 'status': 201,
         'path': '/api/knowledge-entries/import',
         'body': {key: value for key, value in KNOWLEDGE_ENTRY.items()
                  if key not in ('created_by',)}
                 | {'source': dict(KNOWLEDGE_SOURCE, sourceId='sweep-knowledge-import'),
                    'imported_by': 'sweep'},
         'capture': {'kentry_imported': 'knowledge_entry_id'},
         'check': 'check_knowledge_import'},
        {'route': '/api/knowledge-entries/index-rebuild', 'label': 'knowledge-index-rebuild',
         'status': 200, 'path': '/api/knowledge-entries/index-rebuild', 'body': {},
         'check': 'check_knowledge_index_rebuild'},
        # DL-KB-05 D5: a named person's later judgement about the entry the sweep already wrote.
        # Revision 2 arrived with recommended:false, so this POST is the only way the recommendation
        # can move at all -- the revision rows are append-only by trigger.
        {'route': '/api/knowledge-entries/(kentry-[0-9a-f]{32})/judgements',
         'label': 'knowledge-judgement', 'status': 201,
         'path': '/api/knowledge-entries/{kentry}/judgements',
         'body': {'kind': 'RECOMMENDATION', 'revision': 2, 'value': None, 'replaced_by': None,
                  'reason': '复核后确认修订版的景别更好用。', 'recorded_by': '张工',
                  'recorded_by_kind': 'HUMAN'},
         'check': 'check_knowledge_judgement'},
        # DL-KB-07 (batch K): the plan object's create, revise and human choice. The revise row
        # carries `expected_revision` -- the revision it was prepared against -- so a second
        # writer is answered with a conflict instead of silently overwriting the first.
        {'route': '/api/projects/([0-9a-f]{32})/assistance-plans',
         'label': 'assistance-plan', 'status': 201,
         'path': '/api/projects/{project}/assistance-plans', 'body': ASSISTANCE_PLAN,
         'capture': {'aplan': 'plan.plan_id'}, 'check': 'check_assistance_plan'},
        {'route': ('/api/projects/([0-9a-f]{32})/assistance-plans'
                   '/(aplan-[0-9a-f]{32})/revisions'),
         'label': 'assistance-revise', 'status': 201,
         'path': '/api/projects/{project}/assistance-plans/{aplan}/revisions',
         'body': {key: value for key, value in ASSISTANCE_PLAN.items()
                  if key != 'created_by'}
                 | {'neutral_creative': '两束交叉光，标题压在右下角的留白里。',
                    'created_by': 'sweep', 'expected_revision': 1},
         'check': 'check_assistance_revision'},
        {'route': '/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/choose',
         'label': 'assistance-choose', 'status': 200,
         'path': '/api/projects/{project}/assistance-plans/{aplan}/choose',
         'body': {'actor': 'dtalex66', 'actor_kind': 'human', 'revision': 2},
         'check': 'check_assistance_choose'},
        # DL-KB-09 (batch K4): a user draft, then one validation asked of it. The draft is the only
        # way a combination that is not in the tracked config can exist at all, and the validation is
        # the write-shaped POST that must never be able to grant executability -- so the checks below
        # read `executable` back rather than trusting the route to be honest.
        {'route': '/api/target-profiles', 'label': 'target-profile-draft', 'status': 201,
         'path': '/api/target-profiles',
         'body': {'software': 'Illustrator', 'agent': None, 'model': None, 'provider': None,
                  'version': None, 'entry': 'DESKTOP_CLIENT', 'task_mode': '导出分镜表 CSV',
                  'actor': 'sweep', 'source_ref': None, 'fields': {}},
         'capture': {'tprof_draft': 'profile.profile_id'},
         'check': 'check_target_profile_draft'},
        {'route': '/api/target-profiles/(tprof-[0-9a-f]{32})/validate',
         'label': 'target-profile-validate', 'status': 200,
         'path': '/api/target-profiles/{tprof_draft}/validate',
         'body': {'dimensions': {'modality': 'text', 'aspect': '16:9'}},
         'check': 'check_target_profile_validate'},
        # DL-KB-16: the voluntary external-use report. Its proof is that the report lands AND the plan
        # it describes does not move -- those are two different claims and the card depends on both.
        {'route': ('/api/projects/([0-9a-f]{32})/assistance-plans'
                   '/(aplan-[0-9a-f]{32})/feedback'),
         'label': 'plan-feedback', 'status': 201,
         'path': '/api/projects/{project}/assistance-plans/{aplan}/feedback',
         'body': {'outcome': 'PARTIALLY_MATCHES', 'target_key': 'elevenlabs--web-app--music',
                  'actor': 'dtalex66', 'note': '标题落点可用，时长要手改',
                  'source_ref': None, 'revision': 2, 'target_model': None,
                  'dimensions': [{'name': '画幅', 'verdict': 'PARTIALLY_MATCHES', 'note': None}],
                  'issue_timecodes': ['00:03-00:05']},
         'check': 'check_plan_feedback'},
    )

    # -- the walk ---------------------------------------------------------------------
    def test_every_ledger_post_row_is_walked_or_named_in_this_layout(self):
        """POST each row for real, read it back, and name every refusal that actually happened."""
        ledger = json.loads((ROOT / LEDGER).read_text(encoding='utf-8'))
        rows = _post_rows(ledger)
        self.assertEqual(len(rows), len(set(rows)),
                         'a POST route appears twice in the ledger, so coverage cannot be asserted '
                         'against it: ' + str(rows))
        walked = [row['route'] for row in self.WRITES]
        self.assertEqual(len(walked), len(set(walked)), 'a route is walked twice in this table')
        missing, extra = _coverage(rows, walked, self.EXCLUDED)
        self.assertEqual(missing, [],
                         'these ledger POST rows have no entry here, so they would be silently '
                         'unmeasured: ' + str(missing))
        self.assertEqual(extra, [],
                         'this table names POST routes the ledger no longer declares: ' + str(extra))
        layout = 'installed' if INSTALLED_MODE else 'source'

        systems = self.call('GET', '/api/design-systems')[1]
        names = [entry['name'] for entry in systems['design_systems']]
        self.assertTrue(names, 'the design-system catalog named nothing to bind or write tokens to')
        catalogue = self.call('GET', '/api/models')[1]
        from test_jury_http import CRITERIA
        from test_research_http import finding
        from test_rights_http import decision
        slots = {'png': base64.b64encode(_png_bytes()).decode('ascii'), 'system': names[0],
                 'model': catalogue['models'][0]['model_id'], 'criteria': CRITERIA,
                 'rights_decision': decision(decision_id='rd-sweep-1'),
                 'research_finding': finding(finding_id='rf-sweep-1')}
        self._slots = slots
        self.read_backs = []
        written, refused = [], {}
        for row in self.WRITES:
            self.assertNotIn(row['label'], written)
            for name in row.get('capture', {}):
                self.assertNotIn(name, slots, f'slot {name} is captured twice')
            if row.get('prepare'):
                getattr(self, row['prepare'])(slots)
            path, body = _fill(row['path'], slots), _fill(row['body'], slots)
            holes = _unfilled(path) + _unfilled(body)
            self.assertEqual(holes, [], f'{row["label"]} still needs slots this sweep never '
                                        f'captured: {holes}')
            status, payload = self.call('POST', path, body)
            if status >= 500:
                earned = self.EXPECTED_REFUSALS[layout].get(row['route'])
                code = payload.get('error', '') if isinstance(payload, dict) else ''
                if earned != (status, code):
                    self.fail(f'{row["route"]} answered {status} {code!r} '
                              f'{json.dumps(payload, ensure_ascii=False)[:300]}: an unearned 5xx is '
                              'either a contract file the packaged service could not open or a '
                              'refusal nobody read yet -- inspect it, then name it or pay it')
                refused[row['route']] = (status, code)
                continue
            self.assertEqual(status, row['status'],
                             f'{row["label"]} ({path}) answered {status}: '
                             + json.dumps(payload, ensure_ascii=False)[:400])
            for name, dotted in row.get('capture', {}).items():
                slots[name] = _dig(payload, dotted, row['route'])
            before = len(self.read_backs)
            getattr(self, row['check'])(row, payload, slots)
            self.assertGreater(len(self.read_backs), before,
                               f'{row["route"]} was POSTed but nothing was read back, so this table '
                               'would claim a write it never proved is reachable')
            written.append(row['label'])

        unearned, stale = _refusal_diff(refused, self.EXPECTED_REFUSALS[layout])
        self.assertEqual(unearned + stale, [],
                         'the set of permitted 5xx does not match what this layout answered: '
                         + str(unearned + stale))
        # A revision mints a NEW head row. If one ever reused its parent's id, every later row would
        # stay green while the version chain quietly stopped existing.
        self.assertNotEqual(slots['brief'], slots['brief_v3'])
        self.assertNotEqual(slots['direction'], slots['direction_v3'])
        print('POST_SWEEP layout=' + layout + ' rows=' + str(len(rows))
              + ' walked=' + str(len(walked)) + ' written=' + str(len(written))
              + ' read_backs=' + str(len(self.read_backs)) + ' refused=' + str(len(refused))
              + ' excluded=' + str(len(self.EXCLUDED)))
        print('POST_SWEEP_WRITTEN ' + ' '.join(written))
        for route, why in sorted(self.EXCLUDED.items()):
            print('POST_SWEEP_EXCLUDED ' + route + ' :: ' + why[:150])

    def read_back(self, row, path):
        """A GET this sweep treats as the proof that the POST reached the service, not the body."""
        filled = _fill(path, self._slots)
        status, payload = self.call('GET', filled, None)
        self.assertEqual(status, 200, f'reading {row["label"]} back through {filled} answered '
                                      f'{status}: {json.dumps(payload, ensure_ascii=False)[:300]}')
        self.read_backs.append((row['route'], filled))
        return payload

    # -- one read-back per row --------------------------------------------------------
    def check_project(self, row, payload, slots):
        listed = self.read_back(row, '/api/projects')
        self.assertEqual('design-lab/project-list/v1', listed['schemaVersion'])
        self.assertIn(slots['project'], [entry['id'] for entry in listed['projects']],
                      'the created project is not in the list the desktop reads')

    def check_asset(self, row, payload, slots):
        stored = next((item for item in
                       self.read_back(row, '/api/projects/{project}/assets')['assets']
                       if item['id'] == slots['asset']), None)
        self.assertIsNotNone(stored, 'the imported asset is not in the asset read')
        self.assertEqual(slots['asset_sha256'], stored['sha256'],
                         'the digest the import published is not the one the store answers')

    def check_brief(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/briefs/{brief}')['brief']
        self.assertEqual(1, read['version'])
        self.assertEqual('Sweep brief', read['title'])
        self.assertIsNone(read['superseded_by'])

    def check_direction(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/directions/{direction}')['direction']
        self.assertEqual(slots['brief'], read['brief_id'])
        self.assertFalse(read['chosen'], 'a direction is not chosen until a human chooses it')

    def check_choose(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/directions/{direction}')['direction']
        self.assertTrue(read['chosen'], 'the choice was not written')
        self.assertEqual('dtalex66', read['actor'])
        self.assertEqual('human', read['actor_kind'])

    def check_bind(self, row, payload, slots):
        layer = self.read_back(row, '/api/projects/{project}/design-layer')['design_layer']
        self.assertEqual(slots['binding'], layer['active_binding']['binding_id'],
                         'the binding the POST returned is not the one the aggregate calls active')
        self.assertIn(slots['system'], {entry['design_system_name']
                                        for entry in layer['bindings']})

    def check_tokens(self, row, payload, slots):
        read = self.read_back(
            row, '/api/projects/{project}/design-system-tokens/{system}')['token_document']
        self.assertEqual(TOKENS, read['document'], 'the token document did not survive the trip')
        self.assertEqual(1, read['version'])
        self.assertEqual(slots['token_document'], read['token_document_id'])
        self.assertEqual(3, read['token_count'])

    def check_analysis(self, row, payload, slots):
        # A derivation persists nothing, so what this proves is the binding: the derived IR cites the
        # bytes the asset store actually holds, which is what the asset read answers.
        stored = next(item for item in
                      self.read_back(row, '/api/projects/{project}/assets')['assets']
                      if item['id'] == slots['asset'])
        self.assertEqual(stored['sha256'], payload['asset']['sha256'],
                         'the analysis answers for bytes the store does not hold')
        self.assertEqual('design-lab/reconstruction-ir/v1', payload['rir']['schemaVersion'])
        self.assertTrue(payload['rir']['layers'], 'the derived document carried no layers')
        self.assertGreater(payload['object_count'], 0)

    def check_model_choice(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/model-selection')
        self.assertEqual('CHOSEN', read['state'])
        self.assertEqual(slots['model'], read['selection']['model_id'])
        self.assertFalse(read['selection']['declared_unused'])

    def check_composition(self, row, payload, slots):
        stored = self.read_back(row, '/api/projects/{project}/prompt-results')
        item = next((row_item for row_item in stored['results']
                     if row_item['result_id'] == slots['composition']), None)
        self.assertIsNotNone(item, 'the composition was answered but never stored')
        self.assertEqual(slots['composition_sha'], item['content_sha256'],
                         'the stored digest is not the digest the composing route published')
        self.assertEqual('UNREVIEWED', item['review_state'],
                         'a result nobody signed must not arrive pre-accepted')
        self.assertEqual(slots['model'], item['document']['model']['selected']['model_id'],
                         'the composition does not carry the model choice this sweep recorded')

    def check_reversal(self, row, payload, slots):
        stored = self.read_back(row, '/api/projects/{project}/prompt-results')
        item = next((row_item for row_item in stored['results']
                     if row_item['result_id'] == slots['reversal']), None)
        self.assertIsNotNone(item, 'the reversal was answered but never stored')
        self.assertEqual(slots['asset_sha256'], item['document']['asset']['sha256'],
                         'the reversal is not bound to the bytes this sweep imported')
        self.assertIn('SWEEP', item['document']['prompt_text'],
                      'the observation this sweep posted never reached the reversal text')

    def check_prompt_signature(self, row, payload, slots):
        stored = self.read_back(row, '/api/projects/{project}/prompt-results')
        signed = next(item for item in stored['results']
                      if item['result_id'] == slots['composition'])
        self.assertEqual('ACCEPTED', signed['review_state'],
                         'the human decision was not written against the composition')
        self.assertEqual(signed['content_sha256'], payload['review']['content_sha256'],
                         'the signature does not quote the bytes it says it judged')
        self.assertEqual(1, stored['accepted_count'])

    def check_jury_verdict(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/jury')
        self.assertEqual(1, read['verdict_count'])
        self.assertIn('version:' + slots['asset_version'],
                      [record['subject_ref'] for record in read['records']],
                      'the verdict is not filed against the version this sweep imported')

    def check_jury_proposal(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/jury')
        self.assertEqual(1, read['proposal_count'])
        self.assertEqual(1, read['verdict_count'],
                         'an agent proposal must be counted beside the verdicts, not as one')

    def check_rights(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/rights')
        self.assertEqual(1, read['decision_count'])
        self.assertEqual('CLEARED', read['rights_clearance'],
                         'an approved scope must clear rights; NOT_REVIEWED here would mean the '
                         'write never landed')

    def check_research(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/research')
        self.assertEqual(1, read['finding_count'])
        self.assertEqual(1, read['sourced_finding_count'],
                         'the finding came back without the sources it was filed with')

    def check_candidate_pending(self, row, payload, slots):
        stored = self.candidate_row(row)
        self.assertEqual('PENDING_HUMAN_APPROVAL', stored['review_state'],
                         'a fresh candidate must not arrive pre-approved')
        # The candidate must cite the artifact THIS sweep produced and signed, not a stand-in digest:
        # an agent may not mint provenance and then display it as evidence.
        self.assertEqual(slots['composition_sha'], payload['source']['evidence_sha256'],
                         'the candidate does not cite the composition this sweep wrote')
        self.assertEqual('UNUSED', payload['source']['job_id'],
                         'the provenance id the owner did not fill must come back as UNUSED')

    def check_candidate_approved(self, row, payload, slots):
        self.assertEqual('APPROVED', self.candidate_row(row)['review_state'],
                         'the named-human decision was not written')

    def check_candidate_revoked(self, row, payload, slots):
        self.assertEqual('REVOKED', self.candidate_row(row)['revocation_state'],
                         'the revocation was answered but never persisted')
        self.assertIn('entrypoint', payload,
                      'the revocation receipt lost the entry point it is supposed to name')

    def candidate_row(self, row):
        read = self.read_back(row, '/api/projects/{project}/knowledge-candidates')
        return next(item for item in read['candidates']
                    if item['candidate_id'] == self._slots['candidate'])

    def check_brief_revision(self, row, payload, slots):
        head = self.read_back(row, '/api/projects/{project}/briefs/{brief_v2}')['brief']
        self.assertEqual(2, head['version'])
        self.assertEqual('Sweep brief v2', head['title'])
        old = self.read_back(row, '/api/projects/{project}/briefs/{brief}')['brief']
        self.assertEqual(slots['brief_v2'], old['superseded_by'],
                         'the revision did not mark the row it replaced')

    def check_brief_revision_by_id(self, row, payload, slots):
        head = self.read_back(row, '/api/projects/{project}/briefs/{brief_v3}')['brief']
        self.assertEqual(3, head['version'], 'the id-scoped revision did not extend the chain')
        lineage = self.read_back(row, '/api/design-briefs/{brief}/lineage')['lineage']
        self.assertEqual(slots['brief_v3'], lineage['live_id'],
                         'the id-scoped write is invisible to the chain the root id resolves to')
        self.assertEqual(3, len(lineage['versions']))

    def check_direction_revision(self, row, payload, slots):
        head = self.read_back(row, '/api/projects/{project}/directions/{direction_v2}')['direction']
        self.assertEqual(2, head['version'])
        old = self.read_back(row, '/api/projects/{project}/directions/{direction}')['direction']
        self.assertEqual(slots['direction_v2'], old['superseded_by'])

    def check_direction_revision_by_id(self, row, payload, slots):
        head = self.read_back(row, '/api/projects/{project}/directions/{direction_v3}')['direction']
        self.assertEqual(3, head['version'])
        self.assertTrue(head['chosen'], 'the chosen flag did not move with the direction head')
        lineage = self.read_back(row, '/api/design-directions/{direction}/lineage')['lineage']
        self.assertEqual(slots['direction_v3'], lineage['live_id'])

    def check_bundle(self, row, payload, slots):
        stored = next((item for item in
                       self.read_back(row, '/api/projects/{project}/bundles')['bundles']
                       if item['id'] == slots['bundle']), None)
        self.assertIsNotNone(stored, 'the delivered bundle is not in the bundle read')
        self.assertEqual(slots['bundle_version'], stored['version_id'])
        self.assertEqual('sha256:' + slots['bundle_sha256'], stored['sha256'],
                         'the digest the export published is not the one the store answers')
        self.assertEqual('METADATA_ONLY', stored['verification'],
                         'the bundle read started claiming byte verification it does not perform')

    def check_preflight(self, row, payload, slots):
        # The verdict must be about the archive that is actually stored, so the read-back is the
        # bundle bytes themselves: their digest has to equal the one the export published.
        raw = self.read_back_bytes(row, '/api/projects/{project}/bundles/{bundle}/versions/'
                                        '{bundle_version}/content')
        self.assertEqual(slots['bundle_sha256'], hashlib.sha256(raw).hexdigest(),
                         'preflight answered for a bundle whose stored bytes are not the ones the '
                         'export published')
        from design_lab.assurance import production_preflight as pp
        self.assertIn(payload['verdict'], pp.VERDICTS)
        self.assertEqual(sum(payload['counts'].values()), len(payload['findings']),
                         'the preflight counts do not add up to its findings')

    def check_patch(self, row, payload, slots):
        task = self.read_back(row, '/api/projects/{project}/tasks/{patched_job}')['task']
        self.assertEqual('PENDING', task['attempt']['state'],
                         'the queued patch attempt is not waiting for a worker')
        self.assertEqual(slots['patched_attempt'], task['attempt']['attempt_id'])
        base = self.read_back(row, '/api/projects/{project}/tasks/{job}')['task']
        self.assertEqual('RECEIPTED', base['attempt']['state'],
                         'queueing a patch rewrote the attempt that was already receipted')

    def check_cancel(self, row, payload, slots):
        task = self.read_back(row, '/api/projects/{project}/tasks/{patched_job}')['task']
        self.assertEqual('CANCELLED', task['attempt']['state'],
                         'the cancel request did not move the queued attempt')
        events = self.read_back(row, '/api/projects/{project}/tasks/{patched_job}/events')['events']
        self.assertIn('CANCELLED', [item['to_state'] for item in events],
                      'the attempt log has no transition for the cancel this sweep asked for')
        self.assertIn('does_not_say', payload,
                      'the cancel readback stopped saying what it does not claim: the host never '
                      'reports a stop, so an acknowledged cancellation would be a lie')

    def check_native_plan(self, row, payload, slots):
        task = self.read_back(row, '/api/projects/{project}/tasks/{plan_job}')['task']
        self.assertEqual('photoshop-native', task['kind'])
        self.assertEqual('PENDING', task['attempt']['state'],
                         'a plan submission must queue, never dispatch a host inline')
        # Scoped to the plan's own staging tree: the native attempt this sweep already ran left its
        # controlled artifacts under `runtime/`, and those are not evidence about the plan.
        staged = self.service.paths.category_dir('projects', slots['project'], 'native-plans')
        self.assertFalse(staged.exists() and list(staged.rglob('master.psd')),
                         'a plan submission produced host output without a host run')

    def check_knowledge_create(self, row, payload, slots):
        detail = self.read_back(row, '/api/knowledge-entries/{kentry}')
        self.assertEqual('ACTIVE', detail['status'], 'a fresh entry is not readable as ACTIVE')
        self.assertEqual(1, detail['latest_revision'])
        self.assertEqual(KNOWLEDGE_ENTRY['title'], detail['current']['title'],
                         'the bytes the read route answers are not the ones the create route wrote')
        self.assertEqual('UNVERIFIED', detail['current']['source']['verification'],
                         'storing an entry upgraded a source nobody checked')

    def check_knowledge_revision(self, row, payload, slots):
        detail = self.read_back(row, '/api/knowledge-entries/{kentry}')
        self.assertEqual(2, detail['latest_revision'],
                         'the revision did not become the newest bytes')
        self.assertEqual(1, detail['recommended_revision'],
                         'revision 2 was written with recommended:false, so the recommendation '
                         'must still point at revision 1')
        self.assertIsNotNone(detail['recommended'],
                             'the recommended revision is not the latest, so the read must carry '
                             'its document instead of leaving the page to guess')
        self.assertEqual([1, 2], [item['revision'] for item in detail['revisions']],
                         'the revision replaced its parent instead of appending to it')

    def check_knowledge_import(self, row, payload, slots):
        detail = self.read_back(row, '/api/knowledge-entries/{kentry_imported}')
        self.assertEqual('sweep-knowledge-import', detail['current']['source']['sourceId'])
        listed = self.read_back(row, '/api/knowledge-entries/search?q=%E5%88%86%E9%95%9C')
        self.assertIn(slots['kentry_imported'],
                      [entry['knowledge_entry_id'] for entry in listed['entries']],
                      'the imported entry is not reachable from the search the page uses')

    def check_knowledge_index_rebuild(self, row, payload, slots):
        self.assertEqual(payload['indexed'], payload['index']['indexed'],
                         'the rebuild counted rows it did not leave in the index')
        listed = self.read_back(row, '/api/knowledge-entries/search?q=%E5%88%86%E9%95%9C')
        self.assertGreaterEqual(listed['total'], 2,
                                'after a rebuild the two-character query no longer finds the '
                                'entries this sweep wrote: the derived index was rebuilt empty')
        self.assertEqual(payload['rebuilt_at'], listed['index']['rebuilt_at'],
                         'the read reports an index state the rebuild did not write')

    def check_knowledge_judgement(self, row, payload, slots):
        detail = self.read_back(row, '/api/knowledge-entries/{kentry}')
        self.assertEqual(2, detail['recommended_revision'],
                         'a recorded judgement did not move the recommendation the page reads')
        self.assertEqual('recorded-judgement', detail['recommendation_basis'],
                         'the answer could not say who decided the recommendation')
        self.assertEqual(2, detail['latest_revision'],
                         'recording a judgement wrote a revision; it is a statement, not content')
        self.assertEqual([1, 2], [item['revision'] for item in detail['revisions']])
        self.assertEqual(1, len(detail['judgements']),
                         'the sweep sent one judgement and the trail answers more than that')
        self.assertEqual('张工', detail['judgements'][0]['recorded_by'],
                         'the trail lost the name of the person who decided')
        self.assertIsNone(detail['source_state'],
                          'a source nobody has judged read back as though it had been cleared')
        self.assertEqual(detail, payload,
                         'the write answered a different document than the read route serves')

    def check_assistance_plan(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/assistance-plans/{aplan}')
        self.assertEqual(1, read['latest_revision'])
        self.assertEqual(payload['plan'], read['current'],
                         'the bytes the read answers are not the ones the create route stored')
        self.assertEqual({'saved': True, 'provided': True, 'chosen': False,
                          'externally_verified': False}, read['states'],
                         'a saved plan with a creative is saved and provided, and nothing more: '
                         'no human has chosen it and no external step was verified')
        status = read['reference_status'][0]
        self.assertEqual('CURRENT', status['state'])
        self.assertEqual(slots['asset_sha256'], status['recorded_sha256'],
                         'the digest the plan pinned is not the one the asset read answers')
        # The `reverse` row above stored a reversal for this exact asset digest, so the plan's
        # reference must read ANALYZED -- the evidence is looked up, not inferred from the mention.
        self.assertEqual('ANALYZED', status['analysis'])
        self.assertEqual({'analyzed': 1, 'linked_only': 0}, read['analysis_summary'])
        self.assertFalse(read['external']['verified'])
        self.assertEqual(1, read['external']['steps'])
        self.assertEqual(['op-sweep-1024'], read['external']['supplied_ids'],
                         'only the label the caller supplied may be echoed as a supplied id')
        self.assertEqual('UNUSED', read['current']['external_steps'][0]['job_id'],
                         'the id nobody supplied must stay the literal UNUSED')

    def check_assistance_revision(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/assistance-plans/{aplan}')
        self.assertEqual(2, read['latest_revision'], 'the revision did not become the newest bytes')
        self.assertEqual([1, 2], [item['revision'] for item in read['revisions']],
                         'the revision replaced its parent instead of appending to it')
        self.assertEqual(payload['plan'], read['current'])
        self.assertEqual('两束交叉光，标题压在右下角的留白里。',
                         read['current']['neutral_creative'])
        self.assertEqual(slots['asset_sha256'], read['reference_status'][0]['recorded_sha256'],
                         'the second revision lost the digest it was built from')

    def check_assistance_choose(self, row, payload, slots):
        read = self.read_back(row, '/api/projects/{project}/assistance-plans/{aplan}')
        self.assertTrue(read['states']['chosen'],
                        'the human choice was answered but the readback does not show it')
        self.assertEqual('dtalex66', read['choice']['actor'])
        self.assertEqual('human', read['choice']['actor_kind'])
        self.assertEqual(2, read['choice']['revision'])
        self.assertTrue(read['choice']['is_latest'], 'revision 2 is still the head')
        self.assertFalse(read['states']['externally_verified'],
                         'recording a choice is not external verification')

    def check_target_profile_draft(self, row, payload, slots):
        listed = self.read_back(row, '/api/target-profiles')
        self.assertIn(slots['tprof_draft'], [entry['profile_id'] for entry in listed['profiles']],
                      'the draft this sweep wrote is not in the list the selection panel reads')
        stored = self.read_back(row, '/api/target-profiles/{tprof_draft}')
        self.assertEqual('USER_DRAFT', stored['support_state'],
                         'a draft somebody wrote does not come back as a draft')
        # The owner's rule on identifiers: an absent one stays the literal UNUSED. A stored draft
        # that came back with an invented source would be the page showing a provenance nobody gave.
        self.assertEqual('UNUSED', stored['source_ref'],
                         'a blank external identifier was replaced by something this module made up')
        self.assertFalse(stored['executable'],
                         'a stored draft reports itself executable -- nothing in this repository runs')

    def check_target_profile_validate(self, row, payload, slots):
        from design_lab.target_profile import VERDICTS
        stored = self.read_back(row, '/api/target-profiles/{tprof_draft}')
        self.assertEqual(stored['profile_id'], payload['profile_id'],
                         'the validation answered about a profile other than the one stored')
        self.assertTrue(payload['verdicts'], 'two contracted dimensions were asked and nothing answered')
        for verdict in payload['verdicts']:
            self.assertIn(verdict['verdict'], VERDICTS,
                          'a verdict outside the closed vocabulary: ' + str(verdict))
            # The per-row flag is the real guard: a validation that answered SUPPORT for a
            # dimension must still not be able to say the combination can be executed.
            self.assertFalse(verdict['grants_execution'],
                             'a verdict granted execution: ' + json.dumps(verdict,
                                                                          ensure_ascii=False))
            self.assertTrue(verdict['reason'], 'a verdict with no stated reason: ' + str(verdict))
        self.assertFalse(payload['executable'],
                         'a verdict granted executability; the contract says a validation never may')
        self.assertIn('没有', payload['execution_note'],
                      'the execution note stopped saying what the validation does not answer')

    def check_plan_feedback(self, row, payload, slots):
        history = self.read_back(
            row, '/api/projects/{project}/assistance-plans/{aplan}/feedback')
        self.assertEqual(1, len(history['records']),
                         'the voluntary report is not the single row the sweep wrote: '
                         + str(len(history['records'])))
        record = history['records'][0]
        self.assertEqual('PARTIALLY_MATCHES', record['outcome'])
        self.assertEqual('部分符合', record['outcome_label'],
                         'the served label does not match the served outcome word')
        self.assertEqual('UNUSED', record['source_ref'],
                         'a blank 外部编号 must stay the literal, not become an invented one')
        self.assertEqual('画幅', record['dimensions'][0]['name'])
        self.assertEqual('00:03-00:05', record['issue_timecodes'][0])
        # The other half of the card: a report about a plan is not a change to the plan.
        plan = self.read_back(row, '/api/projects/{project}/assistance-plans/{aplan}')
        self.assertTrue(payload['plan_states_unchanged'],
                        'the write envelope claims the plan did not move; the readback must agree')
        self.assertEqual(2, len(plan['revisions']),
                         'a feedback record appended a revision to the plan')
        self.assertEqual('dtalex66', plan['choice']['actor'],
                         'the named choice the sweep recorded was rewritten by a feedback write')
        self.assertFalse(plan['states']['externally_verified'],
                         'a person saying 部分符合 is not the system verifying an external run')
        self.assertEqual(1, history['outcome_histogram']['PARTIALLY_MATCHES'])
        self.assertEqual(0, history['outcome_histogram']['MATCHES'])

    # -- machinery the table depends on -----------------------------------------------
    def prepare_candidate(self, slots):
        """Cite the composition this sweep actually produced, instead of a stand-in digest.

        An agent may not mint provenance it then displays as evidence, so the candidate's
        `evidence_sha256` is the digest the compose row published, and both id slots stay the
        literal UNUSED the owner fills.
        """
        from test_knowledge_http import candidate
        slots['candidate'] = candidate(
            candidate_id='kc-sweep-1',
            source={'design_lab_sha': 'a' * 40, 'job_id': 'UNUSED', 'operation_id': 'UNUSED',
                    'evidence_sha256': slots['composition_sha']},
            payload={'title': 'write a route, then read it back',
                     'statement': 'a POST that is never read back proves a response body, not a '
                                  f'stored object; this sweep read every row back, including the '
                                  f'composition {slots["composition"]} it signed',
                     'applies_to': ['editorial', 'brand']})

    def prepare_native_attempt(self, slots):
        """Produce one receipted native attempt the bundle, patch and cancel rows can act on.

        The dispatch is patched, so this stays a controlled runtime, not a host run: the artifacts
        are real bytes registered by id, which is all three rows below need. Unlike the read sweep's
        delivery leg, this job carries a text layer, because `POST …/patch` patches text.
        """
        from unittest.mock import patch
        from design_lab.native_tasks import NativeTasks
        run = self.service.paths.category_dir('runtime', 'write-sweep')
        run.mkdir(parents=True, exist_ok=True)
        job = dict(schemaVersion='design-lab/photoshop-native-job/v1', jobId='sweep-ps',
                   runRoot=str(run), width=8, height=6, assets=[], outputName='master.psd',
                   previewName='master.png',
                   layers=[dict(id='title', kind='text', text='Before', font='ArialMT', size=2,
                                position=[1, 2], color=[0, 0, 0])])

        def native(_host, current, **_kwargs):
            outputs = {'psd': run / 'master.psd', 'png': run / 'master.png'}
            outputs['psd'].write_bytes(b'8BPS\x00\x01' + b'\0' * 6 + b'\x00\x03'
                                       + (6).to_bytes(4, 'big') + (8).to_bytes(4, 'big')
                                       + b'\x00\x08\x00\x03')
            outputs['png'].write_bytes(b'controlled sweep preview')
            return dict(status='NATIVE_READBACK', job_id=current['jobId'], host_version='26.7.0',
                        job_sha256=hashlib.sha256(json.dumps(current, sort_keys=True,
                                                             ensure_ascii=True,
                                                             separators=(',', ':')).encode()
                                                  ).hexdigest(),
                        inputs={}, bridge_sha256='b' * 64,
                        artifacts={kind: dict(sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
                                              byte_size=path.stat().st_size)
                                   for kind, path in outputs.items()},
                        documents_before=0, documents_after=0)
        with patch('design_lab.native_tasks._dispatch', side_effect=native):
            attempt = NativeTasks(self.service).execute(
                slots['project'], 'photoshop', job, idempotency_key='sweep-ps',
                approved_root=run,
                authorization=dict(actor='sweep', scope='project-native-test',
                                   receipt='controlled boundary'))
        slots['job'] = attempt['attempt']['job_id']
        slots['attempt'] = attempt['attempt']['attempt_id']
        slots['rir'] = dict(
            schemaVersion='design-lab/reconstruction-ir/v1',
            canvas=dict(width=8, height=6, colorSpace='srgb'),
            layers=[dict(id='image', name='image', type='raster', opacity=1,
                         bounds=dict(x=0, y=0, width=8, height=6), inferred=True, zOrder=0,
                         visible=True, locked=False, blendMode='normal',
                         raster=dict(path=slots['asset'], crop=dict(x=0, y=0, width=8, height=6),
                                     alpha=1, sourceMappings=[]))])

    def read_back_bytes(self, row, path):
        """A read-back whose body is bytes: a bundle archive is not JSON and may not be assumed."""
        filled = _fill(path, self._slots)
        conn = http.client.HTTPConnection('127.0.0.1', self.port, timeout=20)
        try:
            conn.request('GET', filled,
                         headers={'Authorization': 'Bearer ' + self.token,
                                  'Host': f'127.0.0.1:{self.port}',
                                  'Origin': f'http://127.0.0.1:{self.port}',
                                  'Sec-Fetch-Site': 'same-origin'})
            response = conn.getresponse()
            self.assertEqual(response.status, 200,
                             f'reading {row["label"]} back through {filled} answered '
                             f'{response.status}')
            self.read_backs.append((row['route'], filled))
            return response.read()
        finally:
            conn.close()

    # -- the table's own shape --------------------------------------------------------
    def test_a_write_route_that_builds_an_envelope_names_the_contract_not_the_request(self):
        """The conviction this batch's plant produced, pinned so it cannot come back.

        `POST …/tasks/<job>/bundle` builds the same task envelope the two read routes do, but it is
        not one of the handlers wrapped locally. With the packaged `config/state-vocabularies.json`
        moved out of an installed wheel, that route answered 400 INVALID_REQUEST -- a verdict about a
        request that was well formed, caused by a file the server could not open. The refusal has to
        arrive as the contract's own code and status, or the next operator debugs their own JSON.
        """
        from unittest.mock import patch
        from design_lab.task_queries import TaskQueries, TaskReadbackError
        status, created = self.call('POST', '/api/projects', {'name': 'Envelope refusal'})
        self.assertEqual(status, 201, created)
        project = created['project']['id']
        with patch.object(TaskQueries, 'get', side_effect=TaskReadbackError(
                503, 'TASK_VOCABULARY_UNREADABLE',
                'fixture: the state vocabulary file could not be read')):
            refused = self.call('POST', f'/api/projects/{project}/tasks/'
                                       f'native-job-{"0" * 64}/bundle', {})
        self.assertEqual(503, refused[0], refused[1])
        self.assertEqual('TASK_VOCABULARY_UNREADABLE', refused[1]['error'])
        self.assertIn('could not be read', refused[1]['detail'],
                      'the refusal arrived as a code with nothing to act on')

    def test_the_exclusions_are_real_ledger_rows_and_every_row_has_a_check(self):
        """A table that names a method nobody wrote, or excludes a row the ledger never had, is a
        silent hole: this reads the ledger and the class and convicts both kinds."""
        ledger = json.loads((ROOT / LEDGER).read_text(encoding='utf-8'))
        rows = set(_post_rows(ledger))
        self.assertEqual(sorted(set(self.EXCLUDED) - rows), [],
                         'an exclusion names a route the ledger does not declare, so it excuses '
                         'nothing and hides the real coverage')
        for row in self.WRITES:
            self.assertIn(row['route'], rows)
            self.assertTrue(callable(getattr(self, row['check'], None)),
                            f'{row["check"]} is not a read-back check')
            if row.get('prepare'):
                self.assertTrue(callable(getattr(self, row['prepare'], None)),
                                f'{row["prepare"]} is not a preparer')

    def test_a_post_row_added_to_the_ledger_without_an_entry_here_is_convicted(self):
        """The falsifier for the coverage claim: plant a row and check that the plant moves."""
        ledger = json.loads((ROOT / LEDGER).read_text(encoding='utf-8'))
        planted = '/api/projects/([0-9a-f]{32})/planted-write-route'
        rows = _post_rows(ledger) + [planted]
        missing, extra = _coverage(rows, [row['route'] for row in self.WRITES], self.EXCLUDED)
        self.assertEqual(missing, [planted],
                         'a ledger POST row with no entry here must be reported as unmeasured')
        self.assertEqual(extra, [])
        missing, _ = _coverage(rows, [], {})
        self.assertEqual(len(missing), len(rows),
                         'dropping the whole table must report every row as unmeasured, not none')
        # An entry that is neither walked nor excluded is the other half of the same hole.
        missing, extra = _coverage(_post_rows(ledger),
                                   [row['route'] for row in self.WRITES], {})
        self.assertEqual(missing, sorted(self.EXCLUDED),
                         'the excluded row must show as unmeasured once its exclusion is removed')

    def test_a_refusal_list_is_compared_in_both_directions(self):
        """A named refusal that stopped happening must be as loud as an unearned one appearing."""
        unearned, stale = _refusal_diff({'/x': (503, 'NEW')}, {'/y': (503, 'OLD')})
        self.assertEqual(len(unearned), 1, 'an unearned 5xx was not reported')
        self.assertEqual(len(stale), 1, 'a refusal that no longer happens was not reported')
        self.assertEqual(_refusal_diff({'/x': (503, 'A')}, {'/x': (503, 'A')}), ([], []),
                         'the honest pair must agree -- if this fails, the comparison is broken')
        self.assertTrue(_refusal_diff({'/x': (500, 'A')}, {'/x': (503, 'A')})[0],
                        'a refusal that changed status must not be excused by its route name')

    def test_a_slot_this_sweep_never_captured_is_reported_rather_than_sent_literally(self):
        """A leftover `{brief}` in a path would be a 400 nobody reads as a coverage hole."""
        self.assertEqual(_unfilled('/api/projects/{project}/briefs/{brief}'), ['brief', 'project'])
        self.assertEqual(_unfilled(_fill('/api/projects/{project}/x', {'project': 'p1'})), [])
        self.assertEqual(_unfilled(_fill({'a': '{color.brand}'}, {})), [],
                         'a DTCG alias must not be read as a slot')
        self.assertIs(_fill('{doc}', {'doc': TOKENS}), TOKENS,
                      'a whole-string slot must keep its type, not become repr')


if __name__ == '__main__':
    unittest.main(verbosity=2)
