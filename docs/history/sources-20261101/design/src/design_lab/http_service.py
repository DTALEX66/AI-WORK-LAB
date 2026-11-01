# SPDX-License-Identifier: MIT
"""Loopback-only metadata transport; no host execution or arbitrary file API."""
import hmac
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import re
import sqlite3
from urllib.parse import parse_qsl, urlsplit

from . import __version__
from .runtime.asset_store import AssetError
from .runtime.paths import PathPolicyError
from .asset_analysis import AssetAnalysis, AssetAnalysisError
from .prompt_intelligence import PromptIntelligence, PromptIntelligenceError
from .prompt_results import (PROMPT_RESULT_LIMIT, PromptResults, PromptResultError)
# DL-KB-02 (2026-10-23): the knowledge library is a global surface like /api/capabilities -- it
# belongs to the operator, not to a project, and nothing on it is scoped by a project id.
from .knowledge_library import DEFAULT_LIMIT, KnowledgeLibrary, KnowledgeLibraryError
# DL-KB-07 (2026-10-24): the neutral assistance plan a short task is written down in. It reuses
# the existing brief/direction/prompt-result/asset objects by reference and owns no second copy
# of their bytes.
from .assistance_plan import (AssistancePlanError, AssistancePlans,
                              DEFAULT_LIMIT as PLAN_DEFAULT_LIMIT)
# DL-KB-09 (2026-10-24): the target profile registry -- software x model x entry, graded field by
# field. Project-independent on purpose: a profile describes somebody else's product, so a copy per
# project would be N tables claiming one fact.
from .target_profile import (TargetProfileError, TargetProfiles,
                             DEFAULT_LIMIT as PROFILE_DEFAULT_LIMIT,
                             MAX_LIMIT as PROFILE_MAX_LIMIT)
# DL-KB-16 (2026-10-24): a voluntary report about what happened when a plan's material was
# taken to an external tool. It is a separate record from the plan's four readback states on
# purpose: a person's word about an external run is not the system confirming one.
from .plan_feedback import (PlanFeedback, PlanFeedbackError,
                            DEFAULT_LIMIT as FEEDBACK_DEFAULT_LIMIT,
                            MAX_LIMIT as FEEDBACK_MAX_LIMIT)
# DL-KB-11 (2026-10-24): the handoff materials one stored plan revision renders into -- markdown,
# plain text, structured JSON and the 分镜 CSV -- all four from one builder, each answer carrying the
# revision it exported, the pinned reference snapshot and the not-executed statement. This route
# reads and renders; it writes nothing, changes no state, and sends nothing to anybody.
from .plan_export import PlanExport, PlanExportError, material_table
from .project_index import ProjectIndex, ProjectIndexError
from .image_assets import ImageAssets, ImageAssetError
from .task_queries import TaskQueries, TaskReadbackError
from .task_commands import TaskCommands
from .native_submissions import NativeSubmissions
from .native_patch_submissions import NativePatchSubmissions
from .native_tasks import NativeTaskError
from .native_workers import NativeWorkers
from .native_assets import Bundles, NativeAssets
from .native_delivery import NativeDelivery
from .design_layer import (DesignLayer, DesignLayerError, DESIGN_SYSTEM_NAME_PATTERN,
                           TOKEN_WRITE_FIELDS)
from .jury_review import JuryReview, JuryReviewError
from .rights_review import RightsReview, RightsReviewError, write_fields
from .research_review import (ResearchReview, ResearchReviewError,
                              write_fields as research_write_fields)
from .knowledge_review import KnowledgeReview, KnowledgeReviewError
# DL-UI-U06 (2026-10-10): the read-only observation surface over the native runtime tables.
# The action routes (run/cancel/patch/bundle) already existed; nothing projected the state
# those actions leave behind, so no page could say which host is currently held.
from .native_runtime import NativeRuntimeError, readback as native_runtime_readback
from .assurance.production_preflight import PreflightError, preflight_bundle
from .governance.evidence_readback import EvidenceReadbackError, projection as evidence_projection
from . import workbench


#: A readback that cannot be produced is not a readback with nothing in it. The status carries
#: whether the operator can fix it by looking (503: this checkout has no ledger / no git subject)
#: or whether code and contract have diverged and a person must change something (500).
EVIDENCE_READBACK_STATUS = {
    'EVIDENCE_LEDGER_ABSENT': 503,
    'EVIDENCE_CONTRACT_ABSENT': 503,
    'EVIDENCE_SUBJECT_UNRESOLVABLE': 503,
    'EVIDENCE_LEDGER_REJECTED': 500,
    'EVIDENCE_CONTRACT_UNLOADABLE': 500,
    'EVIDENCE_CONTRACT_VIOLATION': 500,
    'EVIDENCE_PROJECTION_OVERFLOW': 500,
}


class RequestError(ValueError):
    def __init__(self, status, code):
        self.status, self.code = status, code


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError('duplicate JSON key')
        result[key] = value
    return result


class Route:
    """One authenticated API route: what it matches, which Handler method answers.

    `exact` routes compare the whole target for equality instead of running a regex.
    `path_only` drops the query string before matching (task-preflight and the knowledge list
    do: their queries are parsed by the handler, and a missing/blank value must answer its own
    code rather than 404). `when` is the extra predicate a pattern cannot say:
    the task-detail pattern also admits `/events` but must refuse a bare `?after=`.
    """
    __slots__ = ('method', 'pattern', 'action', 'exact', 'path_only', 'when')

    def __init__(self, method, pattern, action, *, exact=False, path_only=False,
                 when=None):
        self.method, self.pattern, self.action = method, pattern, action
        self.exact, self.path_only, self.when = exact, path_only, when

    def accepts(self, match):
        return self.when is None or bool(self.when(match))


#: The authenticated API surface, in dispatch order. This table is the single route
#: inventory: dispatch() matches from it, verify_contract_bindings.py reads it (every
#: route must have a boundary row), and verify_workbench_route_calls.py holds the
#: TypeScript call sites against it in both directions.
ROUTES = (
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/bundles/(bundle-native-[0-9a-f]{64})/versions/(v-[0-9a-f]{32})/content',
          '_read_delivery_content'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/bundles/(bundle-native-[0-9a-f]{64})/versions/(v-[0-9a-f]{32})/receipt',
          '_read_delivery_receipt'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/native-assets(?:\?after=(native-[0-9a-f]{64}))?',
          '_list_native_assets'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/native-assets/(native-[0-9a-f]{64})/verify',
          '_verify_native_asset'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/bundles',
          '_list_bundles'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/tasks(?:\?after=((?:native-)?job-[0-9a-f]{64}))?',
          '_list_tasks'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/tasks/((?:native-)?job-[0-9a-f]{64})(/events)?(?:\?after=([0-9]{1,16}))?',
          '_task_detail_or_events', when=lambda match: (match[3] or match[4] is None)),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/assets(?:/(img-[0-9a-f]{64})/content)?',
          '_list_or_read_assets'),
    Route('GET', '/api/health', '_health', exact=True),
    Route('GET', '/api/environment', '_environment', exact=True),
    Route('GET', '/api/capabilities', '_capabilities', exact=True),
    Route('GET', '/api/models', '_models', exact=True),
    Route('GET', '/api/automation-connectors', '_automation_connectors', exact=True),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/model-selection',
          '_read_model_selection'),
    Route('GET', '/api/domains', '_domains', exact=True),
    Route('GET', '/api/task-preflight', '_task_preflight', exact=True, path_only=True),
    # DL-KB-02/DL-KB-04. Search lives on its own path so the collection path carries exactly one
    # answer: POST /api/knowledge-entries creates an entry, and a GET there would make one ledger
    # row describe two different documents. Browsing is the same route with no `q` (strategy
    # BROWSE). The query (q/type/domain/task/target/offset/limit) is parsed inside the handler the
    # same way task-preflight does, so a malformed parameter answers a named refusal instead of 404.
    Route('GET', '/api/knowledge-entries/search', '_search_knowledge_entries', exact=True,
          path_only=True),
    Route('POST', '/api/knowledge-entries', '_create_knowledge_entry', exact=True),
    Route('POST', '/api/knowledge-entries/import', '_import_knowledge_entry', exact=True),
    Route('POST', '/api/knowledge-entries/index-rebuild', '_rebuild_knowledge_index',
          exact=True),
    Route('GET', r'/api/knowledge-entries/(kentry-[0-9a-f]{32})', '_get_knowledge_entry'),
    Route('POST', r'/api/knowledge-entries/(kentry-[0-9a-f]{32})/revisions',
          '_revise_knowledge_entry'),
    # DL-KB-05 D5: a later human judgement about an entry -- moving the recommended revision
    # (including back to an older one) or marking its source invalid with a replacement. It writes
    # no revision, so every stored document and digest stays where it was.
    Route('POST', r'/api/knowledge-entries/(kentry-[0-9a-f]{32})/judgements',
          '_record_knowledge_judgement'),
    Route('GET', '/api/projects', '_list_projects', exact=True),
    Route('GET', '/api/evidence-projection', '_evidence_projection', exact=True),
    Route('GET', '/api/design-systems', '_list_design_systems', exact=True),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/design-layer',
          '_get_design_layer'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/jury',
          '_list_jury'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/rights',
          '_list_rights'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/research',
          '_list_research'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/native-runtime',
          '_get_native_runtime'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/knowledge-candidates',
          '_list_knowledge_candidates'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/knowledge-candidates'
            r'/([A-Za-z0-9_.:-]{1,80})/export',
          '_export_knowledge_candidate'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/briefs(?:\?after=(brief-[0-9a-f]{32}))?',
          '_list_briefs'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})',
          '_get_brief'),
    # DL-KB-07 (2026-10-24). Create answers on the bare collection path; the list names its query
    # in the route itself so one ledger row still describes one document (the same reason
    # /api/knowledge-entries keeps search on its own path). offset/limit are parsed inside the
    # handler, and a malformed number answers ASSISTANCE_PLAN_OFFSET_INVALID / LIMIT_INVALID
    # instead of a 404.
    # DL-KB-08. The initial screen must name an output type before any project exists, so the
    # closed vocabulary travels on its own project-independent read; the list route cannot answer
    # it, and a copy in TypeScript would be a second table.
    Route('GET', '/api/assistance-plan-output-types', '_assistance_plan_output_types',
          exact=True),
    # DL-KB-09. The axes route carries the closed vocabulary the selection panel builds its
    # selects from, so the screen cannot offer a word the service refuses; the list is
    # project-independent for the same reason the output types are.
    Route('GET', '/api/target-profile-axes', '_target_profile_axes', exact=True),
    Route('GET',
          r'/api/target-profiles(?:\?[^#]*)?', '_list_target_profiles'),
    Route('GET', r'/api/target-profiles/(tprof-[0-9a-f]{32})', '_get_target_profile'),
    Route('POST', '/api/target-profiles', '_create_target_profile', exact=True),
    Route('POST', r'/api/target-profiles/(tprof-[0-9a-f]{32})/validate',
          '_validate_target_profile'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/assistance-plans(?:\?[^#]*)?',
          '_list_assistance_plans'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})',
          '_get_assistance_plan'),
    # DL-KB-12. One stored revision, so the comparison page reads two real documents instead of the
    # newest one twice. The revision number is a path segment and there is deliberately NO query
    # string on this route: dispatch matches a non-`path_only` Route against the raw target, so this
    # pattern refuses `?revision=2` as a 404 rather than honouring a parameter it does not define --
    # the same reason the plain detail route above carries no flags either, unlike `/export`, whose
    # pattern names its `format` query so one ledger row describes one document.
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/revisions/([1-9][0-9]{0,8})',
          '_get_assistance_plan_revision'),
    # DL-KB-11. The handoff material for one stored revision. The query is named in the pattern the
    # way the plan list names its own, so one ledger row describes one document; `format` is parsed
    # inside the handler and a missing or unknown word answers a named refusal (PLAN_EXPORT_FORMAT_
    # REQUIRED / _INVALID) instead of a 404 the page could not tell apart from a deleted plan.
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/export(?:\?[^#]*)?',
          '_export_assistance_plan'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/directions(?:\?after=(direction-[0-9a-f]{32}))?',
          '_list_directions'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})',
          '_get_direction'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})/lineage',
          '_lineage_brief_scoped'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/lineage',
          '_lineage_direction_scoped'),
    Route('GET',
          r'/api/design-briefs/(brief-[0-9a-f]{32})/lineage',
          '_lineage_brief_by_id'),
    Route('GET',
          r'/api/design-directions/(direction-[0-9a-f]{32})/lineage',
          '_lineage_direction_by_id'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/design-system-tokens',
          '_list_token_documents'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/design-system-tokens/('
            + DESIGN_SYSTEM_NAME_PATTERN + r')(/lineage)?',
          '_get_token_document_or_lineage'),
    Route('GET',
          r'/api/projects/([0-9a-f]{32})',
          '_get_project'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/patch',
          '_submit_task_patch'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/run',
          '_start_task_run'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/native-plans',
          '_submit_native_plan'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/cancel',
          '_cancel_task'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/tasks/(native-job-[0-9a-f]{64})/bundle',
          '_create_bundle'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/assets',
          '_import_asset'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/assets/(img-[0-9a-f]{64})/analysis',
          '_derive_asset_analysis'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/model-selection/choose',
          '_record_model_selection'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/prompts',
          '_compose_prompt'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/assets/(img-[0-9a-f]{64})/prompt-reversal',
          '_reverse_asset_prompt'),
    # The list names its own query the way the knowledge search and the assistance-plan list do:
    # `path_only` lets a present query reach the handler, which parses it and answers a NAMED
    # refusal for a malformed number instead of the 404 a pattern-only route would give.
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/prompt-results',
          '_list_prompt_results', path_only=True),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/prompt-results'
            r'/((?:prompt|reversal)-[0-9a-f]{32})/review',
          '_review_prompt_result'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/bundles'
            r'/(bundle-native-[0-9a-f]{64})/preflight'
            r'(?:\?profile=(print|digital|video))?',
          '_preflight_bundle'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/jury/verdict',
          '_record_jury_verdict'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/jury/proposal',
          '_record_jury_proposal'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/rights'
            r'(?:\?supersedes=([A-Za-z0-9_.:-]{1,80}))?',
          '_record_rights'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/research'
            r'(?:\?supersedes=([A-Za-z0-9_.:-]{1,80}))?',
          '_record_research'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/knowledge-candidates'
            r'(?:\?supersedes=([A-Za-z0-9_.:-]{1,80}))?',
          '_create_knowledge_candidate'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/knowledge-candidates'
            r'/([A-Za-z0-9_.:-]{1,80})/review',
          '_review_knowledge_candidate'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/knowledge-candidates'
            r'/([A-Za-z0-9_.:-]{1,80})/revoke',
          '_revoke_knowledge_candidate'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/briefs',
          '_create_brief'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/directions',
          '_create_direction'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/assistance-plans',
          '_create_assistance_plan'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/revisions',
          '_revise_assistance_plan'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/choose',
          '_choose_assistance_plan'),
    # DL-KB-16. The GET carries its paging inside the pattern so one ledger row describes one
    # document, the same way the assistance-plan list does.
    Route('GET',
          r'/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/feedback'
          r'(?:\?[^#]*)?',
          '_list_plan_feedback'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/assistance-plans/(aplan-[0-9a-f]{32})/feedback',
          '_record_plan_feedback'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/choose',
          '_choose_direction'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/bind',
          '_bind_design_system'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/briefs/(brief-[0-9a-f]{32})/revisions',
          '_revise_brief_scoped'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/directions/(direction-[0-9a-f]{32})/revisions',
          '_revise_direction_scoped'),
    Route('POST',
          r'/api/design-briefs/(brief-[0-9a-f]{32})/revisions',
          '_revise_brief_by_id'),
    Route('POST',
          r'/api/design-directions/(direction-[0-9a-f]{32})/revisions',
          '_revise_direction_by_id'),
    Route('POST',
          r'/api/projects/([0-9a-f]{32})/design-system-tokens/('
            + DESIGN_SYSTEM_NAME_PATTERN + r')',
          '_write_tokens'),
    Route('POST', '/api/projects', '_create_project', exact=True),
)


def make_server(service, token, port=0, *, local_session=False):
    """Caller owns server lifetime; token is supplied in memory, never logged.

    `local_session` is the official personal launcher's handshake: the page this
    server itself opened may ask for the token, so nobody has to copy it out of a
    terminal. It is not an account system and not an auth relaxation -- see the
    `/api/local-session` handler for exactly who is answered.
    """
    if not isinstance(token, str) or not re.fullmatch(r'[0-9a-f]{64}', token):
        raise ValueError('INVALID_SERVICE_TOKEN')
    if type(port) is not int or not 0 <= port <= 65535:
        raise ValueError('INVALID_SERVICE_PORT')
    workers = NativeWorkers(service)

    class Handler(BaseHTTPRequestHandler):
        server_version = 'DESIGN-LAB'
        sys_version = ''

        def setup(self):
            self.request.settimeout(3)
            super().setup()

        def log_message(self, format, *args):
            # Request targets and payloads are not audit-safe diagnostic logs.
            pass

        def send_json(self, status, value):
            self.drain_body()
            payload = json.dumps(value, ensure_ascii=True).encode('utf-8')
            self.send_response(status)
            self.send_header('Content-Type', 'application/json; charset=utf-8')
            self.send_header('Content-Length', str(len(payload)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('Connection', 'close')
            self.end_headers()
            self.close_connection = True
            self.wfile.write(payload)

        def drain_body(self):
            """Discard an unconsumed request body so the socket closes with FIN.

            ``guard()`` / ``body()`` can fail before the client's body bytes are
            read. Closing a socket that still has unread data in its receive
            buffer makes the kernel reset the connection, so a client awaiting
            the error response sees connection-aborted (WinError 10053) instead
            of the deterministic 4xx. Best-effort: any failure here is ignored;
            repeated calls are no-ops.
            """
            if self.command not in ('POST', 'PUT', 'PATCH'):
                return
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or not re.fullmatch(r'[0-9]{1,8}', lengths[0]):
                return
            remaining = int(lengths[0]) - getattr(self, '_body_read', 0)
            try:
                while remaining > 0:
                    chunk = self.rfile.read(min(remaining, 65536))
                    if not chunk:
                        break
                    remaining -= len(chunk)
            except OSError:
                # The docstring above promises "any failure here is ignored", and this is the
                # only place that promise was unenforced: a socket timeout raised inside an
                # except handler escapes to handle_one_request, which is precisely the
                # connection-aborted (WinError 10053) path this helper exists to prevent.
                return

        def guard(self, require_auth=True):
            authority = f'127.0.0.1:{self.server.server_port}'
            if self.headers.get_all('Host', []) != [authority]:
                raise RequestError(403, 'HOST_DENIED')
            origins = self.headers.get_all('Origin', [])
            if origins and origins != ['http://' + authority]:
                raise RequestError(403, 'ORIGIN_DENIED')
            sites = self.headers.get_all('Sec-Fetch-Site', [])
            if sites and sites not in (['same-origin'], ['none']):
                raise RequestError(403, 'CROSS_SITE_DENIED')
            if not require_auth:
                return
            auth = self.headers.get_all('Authorization', [])
            if (len(auth) != 1 or not hmac.compare_digest(
                    auth[0].encode('utf-8'), ('Bearer ' + token).encode('ascii'))):
                raise RequestError(401, 'UNAUTHORIZED')

        def body(self, *, fields=frozenset({'name'}), limit=16384,
                 optional=frozenset()):
            # `fields` is still the exact key set a caller must state; `optional` names the keys a
            # route accepts but does not demand. It exists for one reason: a field added to an
            # existing write contract (DL-KB-11's `shots`) must stay writable-by-those-who-have-it
            # and ignorable-by-those-who-don't, so clients that predate the field keep answering the
            # same way they did. An unlisted key is still refused with the same code, and a missing
            # required key is still refused -- the strictness is unchanged where nothing was added.
            if self.headers.get_all('Transfer-Encoding', []):
                raise RequestError(400, 'TRANSFER_ENCODING_DENIED')
            lengths = self.headers.get_all('Content-Length', [])
            if len(lengths) != 1 or not re.fullmatch(r'[0-9]{1,8}', lengths[0]):
                raise RequestError(400, 'INVALID_CONTENT_LENGTH')
            size = int(lengths[0])
            if size > limit:
                raise RequestError(413, 'BODY_TOO_LARGE')
            types = self.headers.get_all('Content-Type', [])
            if types not in (['application/json'], ['application/json; charset=utf-8']):
                raise RequestError(415, 'JSON_REQUIRED')
            data = self.rfile.read(size)
            self._body_read = len(data)
            if len(data) != size:
                raise RequestError(400, 'INCOMPLETE_BODY')
            try:
                value = json.loads(data.decode('utf-8'), object_pairs_hook=_unique_object)
            except (ValueError, UnicodeError, RecursionError):
                raise RequestError(400, 'INVALID_JSON') from None
            named = set(value) if isinstance(value, dict) else set()
            if (not isinstance(value, dict) or not set(fields) <= named
                    or not named <= (set(fields) | set(optional))):
                raise RequestError(400, 'INVALID_PROJECT_FIELDS')
            return value


        def dispatch(self):
            try:
                if (self.command == 'GET' and self.path == '/api/local-session'
                        and local_session):
                    self.guard(require_auth=False)
                    # `guard` already pins Host to 127.0.0.1:<port> (which is what
                    # stops DNS rebinding) and allows an absent Sec-Fetch-Site.
                    # Absent is not enough here: any local process can forge that,
                    # so only a browser that this very server served is answered.
                    if self.headers.get_all('Sec-Fetch-Site', []) != ['same-origin']:
                        raise RequestError(403, 'SAME_ORIGIN_REQUIRED')
                    return self.send_json(200, {'token': token})
                # The page routes are matched on the PATH, not on `self.path`, which
                # BaseHTTPRequestHandler hands back WITH the query string. A browser that
                # reloads `?palette=ui2026` (the theme control writes exactly that URL) was
                # therefore not a known page at all: it fell through to the authenticated
                # branch and answered 401 UNAUTHORIZED -- the cloud DOT audit finding D13,
                # reproduced by my own capture driver, which had to set the <html> attributes
                # directly because "the service dispatches /workbench by exact path, so a
                # query string is not an option". Traversal-shaped paths are still refused:
                # stripping a query cannot turn `/workbench/main.ts` into a file read, and the
                # served bytes are asserted byte-identical to the plain page in the test.
                route_path = urlsplit(self.path).path
                if self.command == 'GET' and route_path in workbench.ROUTES:
                    self.guard(require_auth=False)
                    payload, mime = workbench.resource(route_path)
                    if local_session and route_path == '/workbench':
                        # The page asks for the session only when its own server
                        # says auto-connect is on; a bundle copied elsewhere must not
                        # knock on a door that will never answer.
                        payload = payload.replace(b'<body>', b'<body data-local-session="auto">', 1)
                    self.send_response(200)
                    self.send_header('Content-Type', mime + '; charset=utf-8')
                    self.send_header('Content-Length', str(len(payload)))
                    self.send_header('Content-Security-Policy', workbench.CSP)
                    self.send_header('X-Content-Type-Options', 'nosniff')
                    self.send_header('Referrer-Policy', 'no-referrer')
                    self.send_header('Cache-Control', 'no-store')
                    self.send_header('Connection', 'close')
                    self.end_headers()
                    self.close_connection = True
                    self.wfile.write(payload)
                    return
                self.guard()
                for route in ROUTES:
                    if route.method != self.command:
                        continue
                    target = route_path if route.path_only else self.path
                    if route.exact:
                        if target == route.pattern:
                            return getattr(self, route.action)(None)
                        continue
                    match = re.fullmatch(route.pattern, target)
                    if match is not None and route.accepts(match):
                        return getattr(self, route.action)(match)
                if self.command in ('GET', 'POST'):
                    raise RequestError(404, 'NOT_FOUND')
                raise RequestError(405, 'METHOD_NOT_ALLOWED')
            except RequestError as exc:
                self.send_json(exc.status, {'error': exc.code})
            except ImageAssetError as exc:
                self.send_json(exc.status, {'error': exc.code})
            except NativeTaskError:
                self.send_json(409, {'error':'NATIVE_TASK_REQUIRES_RECONCILIATION'})
            except EvidenceReadbackError as exc:
                # Carried with its detail, like the design-layer refusal below: "this checkout has no
                # ledger" and "the readback does not satisfy its own contract" are different problems
                # for the operator, and a bare error word would leave the reviewer with a red card and
                # no way to tell which.
                payload = {'error': exc.code}
                if exc.details:
                    payload['detail'] = exc.details[:10]
                self.send_json(EVIDENCE_READBACK_STATUS.get(exc.code, 500), payload)
            except DesignLayerError as exc:
                # Before the generic ValueError clause, and with its detail when it
                # has one: a refused token document carries the field paths
                # ("document: color.brand.$value is not a CSS color string"), and
                # collapsing it into INVALID_REQUEST would leave the reviewer with
                # a JSON box and no idea what to change.
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail[:10]
                self.send_json(exc.status, payload)
            # Before the generic ValueError clause: a refused jury signature carries
            # the reason ("an agent-signed verdict is refused: juror kind 'CODEX'"),
            # and collapsing it to INVALID_REQUEST would hide why a human gate was
            # not granted.
            except JuryReviewError as exc:
                self.send_json(exc.status, {'error': exc.code})
            # Same position and same reasoning as the jury clause above: a refused rights
            # signature has to arrive as the rule that refused it (RIGHTS_NOT_HUMAN) with
            # the name it refused, and a stored row that no longer satisfies its own
            # contract has to arrive as a 409, not as a retryable 400. The code is what a
            # caller branches on; the detail is what an operator reads.
            except RightsReviewError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            # Same position and same reasoning as the rights clause: "that finding cites no
            # source", "that chain belongs to another project" and "a machine signed this as a
            # human statement" are three different refusals an operator has to be able to act
            # on, and folding them into INVALID_REQUEST would leave a page guessing which one
            # it hit.
            except ResearchReviewError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            # Same position and reasoning again: a candidate refused by its own
            # contract (bad digest, empty rationale, rights not CHECKED) and a
            # store that holds a row no longer satisfying it are different answers,
            # and the page needs the code plus the sentence that explains it.
            except KnowledgeReviewError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            # The library's refusals are the operator's next instruction: "the entry moved to a
            # newer revision, re-read it", "this version is already stored with another digest",
            # "an import needs a source id and a version". Folded into the generic 400 below,
            # every one of them would arrive as INVALID_REQUEST and the page could not tell a
            # stale write from a malformed one.
            except KnowledgeLibraryError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            # Assistance plans refuse revisions and choices for reasons the page has to branch
            # on: "the plan moved to revision 4, re-read it", "a reference belongs to another
            # project", "a machine tried to record a human choice". The generic 400 would tell
            # the page its request was malformed and hide which of the three happened.
            except AssistancePlanError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            # The export route refuses for reasons the page has to act on differently: "no format
            # was named", "this plan has no shot rows, so a 分镜表 cannot be rendered -- write them
            # first", "the newest revision is unreadable". A generic 400/409 would leave the screen
            # offering a download that produces nothing, which is the false-green this card forbids.
            except PlanExportError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            except PlanFeedbackError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            except TargetProfileError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            # DL-UI-U06: an unreadable state database is 503 (retry once the writer is done),
            # while an unknown project is 404. Collapsing them would tell a page to go find a
            # project that does exist when the real answer is "the database refused the read".
            except NativeRuntimeError as exc:
                payload = {'error': exc.code}
                if exc.detail:
                    payload['detail'] = exc.detail
                self.send_json(exc.status, payload)
            # The task envelope guards its own contract, and the write routes that build one on the
            # way to an answer (bundle, patch, cancel, plan submission) are not the two read routes
            # wrapped locally. `TaskReadbackError` is a ValueError, so without this clause it lands
            # on the generic 400 below and tells the caller their request was invalid when the real
            # answer is that the envelope could not be assembled. Measured 2026-10-23 by moving the
            # packaged `config/state-vocabularies.json` out of an installed wheel: POST
            # …/tasks/<job>/bundle answered 400 INVALID_REQUEST.
            except TaskReadbackError as exc:
                self.send_json(exc.status, {'error': exc.code, 'detail': str(exc)})
            # A preflight refusal is a statement about the artifact ("the archive
            # digest does not match what was approved", "a manifest member is
            # missing"), so it must reach the page intact.
            except PreflightError as exc:
                self.send_json(400, {'error': str(exc)})
            except ImportError:
                self.send_json(503, {'error': 'IMAGE_DEPENDENCY_UNAVAILABLE'})
            except (ValueError, PathPolicyError):
                self.send_json(400, {'error': 'INVALID_REQUEST'})
            except OSError as exc:
                # winerror 206 is ERROR_FILENAME_EXCED_RANGE: the project lives
                # under a path Windows cannot address. Folding that into "store
                # unavailable" sends the user to look at the database instead of
                # at where the project is stored.
                code = ('PROJECT_PATH_TOO_LONG' if getattr(exc, 'winerror', None) == 206
                        else 'PROJECT_STORE_UNAVAILABLE')
                self.send_json(503, {'error': code})
            except (sqlite3.Error, AssetError):
                self.send_json(503, {'error': 'PROJECT_STORE_UNAVAILABLE'})
            except Exception:
                # Terminal clause. Anything outside the named taxonomy (a
                # RecursionError from deeply nested RIR JSON, for instance) used to
                # escape dispatch, so socketserver printed a traceback to stderr and
                # dropped the connection: the client saw a reset, the dashboard kept
                # showing stale state, and no machine-readable error existed. The
                # type name is deliberately NOT echoed -- it can carry module and
                # path detail, and this surface is authenticated but still local.
                self.send_json(500, {'error': 'INTERNAL'})


        def _read_delivery_content(self, match):
            with NativeDelivery(service).content(*match.groups()) as (stream,size,digest):
                self.send_response(200)
                self.send_header('Content-Type','application/zip')
                self.send_header('Content-Disposition','attachment; filename="design-lab-delivery.zip"')
                self.send_header('Content-Length',str(size))
                self.send_header('X-Content-SHA256',digest)
                self.send_header('X-Content-Type-Options','nosniff')
                self.send_header('Cache-Control','no-store')
                self.send_header('Connection','close')
                self.end_headers();self.close_connection=True
                try:
                    for block in iter(lambda:stream.read(1024*1024),b''):
                        self.wfile.write(block)
                except OSError:
                    # Headers are already sent; never append JSON to
                    # a truncated ZIP stream. Client verifies length/hash.
                    return
            return

        def _read_delivery_receipt(self, match):
            # The DeliveryReceipt V2 the `delivery-receipt` CLI verb reads
            # (cli.py), now readable over the same boundary NativeDelivery
            # already owns. Nothing is caught and re-raised here on purpose:
            # NativeDelivery.receipt verifies the persisted document and its
            # own digest on every read, and dispatch() maps ImageAssetError by
            # its status AND code two clauses above the generic ValueError
            # one. So a version that was never receipted stays
            # 404 DELIVERY_RECEIPT_NOT_FOUND ("we wrote no document about this
            # delivery") while a stored document its own bytes contradict
            # stays 409 DELIVERY_RECEIPT_UNVERIFIED ("we refuse to certify
            # these"). Folding either into INVALID_REQUEST would read as a bad
            # request the operator could go back and fix, which is a different
            # fact about different bytes.
            # The envelope, not the bare document: a receipt's rollback record names an
            # immutable source version and nothing used to look it up on the way out.
            # The document itself is still returned byte-for-byte under `receipt`, so
            # its self-digest keeps describing exactly the bytes it covers.
            return self.send_json(200,NativeDelivery(service).readback(*match.groups()))

        def _list_native_assets(self, match):
            return self.send_json(200,NativeAssets(service).list(match[1],match[2] or ''))

        def _verify_native_asset(self, match):
            return self.send_json(200,NativeAssets(service).verify(*match.groups()))

        def _list_bundles(self, match):
            # Project bundle/delivery list: read-back of the project's design
            # bundles (its deliveries). The Bundles query class landed in
            # native_assets.py first (tests only); this route is what makes
            # it reachable from the service and the workbench UI.
            return self.send_json(200,Bundles(service).list(match[1]))

        def _list_tasks(self, match):
            # 200 with the envelope; a contract refusal is mapped once, in `dispatch`, by the clause
            # that names `TaskReadbackError` -- the read routes and the write routes that build the
            # same envelope must not each own their copy of that answer.
            return self.send_json(200, TaskQueries(service).list(match[1], match[2] or ''))

        def _task_detail_or_events(self, match):
            query = TaskQueries(service)
            if match[3]:
                return self.send_json(200, query.events(match[1], match[2],
                                                        int(match[4] or 0)))
            return self.send_json(200, query.get(match[1], match[2]))

        def _list_or_read_assets(self, match):
            images = ImageAssets(service)
            return self.send_json(200, images.content(*match.groups()) if match[2] else
                                  {'assets': images.list(match[1])})

        def _health(self, match):
            # bundleSha256/bundleOrigin are not decoration: an installed
            # wheel copy of the UI wins over the checkout, so this is how
            # an operator (and the wheel-install gate) sees WHICH bytes
            # are actually being served.
            return self.send_json(200, {'status': 'OK', 'version': __version__,
                                        'scope': 'project-metadata',
                                        'bundleSha256': workbench.served_bundle_sha256(),
                                        'bundleOrigin': workbench.bundle_origin()})

        def _environment(self, match):
            return self.send_json(200, service.paths.describe())

        def _capabilities(self, match):
            # UI plan: the capability library is a read-only projection of
            # the source lock, the vendor revision record and the model
            # radar. It installs, qualifies and licenses nothing, and it
            # reads the committed records, never a machine-local cache.
            from .analysis.capability_library import build
            return self.send_json(200, build())

        def _models(self, match):
            # The picker's read: two registries side by side with the join left unclaimed, and
            # counts taken from what the records actually hold (qualified_local 0, recorded weight
            # hashes 0) so the page cannot render a readiness chip the radar does not support.
            # A registry that refuses to load is 503 with a named code -- an empty list here would
            # read as "no candidates exist", which is a different fact.
            from .model_catalog import ModelCatalogError, catalog
            try:
                return self.send_json(200, catalog())
            except ModelCatalogError as exc:
                return self.send_json(503, {'status': 'ERROR', 'error': 'MODEL_CATALOG_UNAVAILABLE',
                                            'detail': str(exc)})

        def _automation_connectors(self, match):
            # owner 2026-10-28 lifted the freeze on the automation capability class, so the
            # first surface for it is a read of what is REGISTERED, not a control panel that
            # offers to launch something. The projection opens two committed JSON records and
            # no process: every connector answers NOT_PROBED with enabled:false until a probe
            # is actually run and receipted, which is a per-action Human Gate decision.
            from . import automation_connectors
            return self.send_json(200, automation_connectors.build())

        def _domains(self, match):
            # Same class of read as /api/capabilities: committed repository
            # records, not project or machine state, so the root is the
            # package's own repository root. Domain Pack SPEC V2 asks for a
            # structural check, and this serves the verdict
            # design-lab/scripts/verify_domain_pack_v2.py itself gives each
            # pack -- a read path with its own copy of the rules would be a
            # second authority able to disagree with CI. Read-only by design:
            # no POST/PUT/DELETE form of this path is dispatched below.
            from . import domain_packs
            return self.send_json(200, domain_packs.build())

        def _task_preflight(self, match):
            # DL-AUDIT-20260914-04: the same preflight the CLI doctor
            # uses, so workbench and CLI can never disagree. Read-only.
            # FA-11 (DL-TP-20260918-UCR-014): parse the query with a real
            # URL parser (urlsplit + parse_qsl), not string surgery. Match
            # on the path component so a present query no longer 404s; a
            # missing/empty `task` maps to TASK_REQUIRED and a malformed
            # task to TASK_PREFLIGHT_REJECTED (never the other way round).
            from .runtime.task_resources import TaskResourceError, preflight
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))
            task = params.get('task', '')
            if not task:
                raise RequestError(400, 'TASK_REQUIRED')
            try:
                value = preflight(service.paths.project_root, task,
                                  paths_describe=service.paths.describe())
            except TaskResourceError:
                return self.send_json(400, {'error': 'TASK_PREFLIGHT_REJECTED'})
            return self.send_json(200, value)

        def _list_projects(self, match):
            # Refused rather than degraded when the roll-up contradicts its own contract: a project
            # list that reports "0 待签" for a surface it never opened is worse than no list at all.
            try:
                return self.send_json(200, ProjectIndex(service).list())
            except ProjectIndexError as exc:
                return self.send_json(500, {'status': 'ERROR',
                                            'error': 'PROJECT_LIST_CONTRACT_VIOLATION',
                                            'detail': str(exc)})

        def _evidence_projection(self, match):
            # Not a project view: this is the state of the evidence link for the whole
            # checkout the service is running from, recomputed from the ledger and the
            # object database on every call. It is served because a person has to be able
            # to ask "is any of this actually verified" without reading the projection file
            # or trusting a green page; a refusal is returned as a named error, never as an
            # empty receipt list that would read as "nothing is wrong".
            return self.send_json(200, evidence_projection())

        def _list_design_systems(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.design_systems())

        def _get_design_layer(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.get_design_layer(match[1]))

        def _list_jury(self, match):
            return self.send_json(200, JuryReview(service).list(match[1]))

        def _list_rights(self, match):
            # The rights read-back is the same class of read as /jury: what a
            # human filed, what stands now, and the clearance word the stored
            # rows actually support. An empty ledger answers 200 with
            # NOT_REVIEWED rather than a 404 the page would have to guess at.
            return self.send_json(200, RightsReview(service).list(match[1]))

        def _list_research(self, match):
            # Same class of read again, with one deliberate difference: research
            # has NO project-level verdict word to publish, so an empty panel
            # answers 200 with counts of zero and `research_verdict` null rather
            # than a 404 the page would have to invent a word for, and rather than
            # a "cleared"-shaped field that would read as a gate nobody put here.
            return self.send_json(200, ResearchReview(service).list(match[1]))

        def _get_native_runtime(self, match):
            # Read-only by construction: `native_runtime.readback` opens the state
            # database `mode=ro` and never creates a table, so an absent table stays
            # ABSENT instead of being conjured into an empty one. No host is
            # contacted and no attempt is started by reaching this line.
            return self.send_json(200, native_runtime_readback(service, match[1]))

        def _list_knowledge_candidates(self, match):
            # A read that states its own limits: `outbound` is NOT_CONNECTED because
            # no ArcheAxis transport exists here, and `export_ready` is a local
            # contract check. The readback also reports store/contract conflicts by
            # name instead of dropping the rows they concern.
            return self.send_json(200, KnowledgeReview(service).list(match[1]))

        def _export_knowledge_candidate(self, match):
            # Produces the two outbound projections and nothing more: no transport exists, so a
            # successful answer means "assembled and contract-valid", never "sent". A candidate the
            # contract will not release answers 409 with the refusal sentence, not 200 with a body.
            return self.send_json(200, KnowledgeReview(service).export_document(
                match[1], match[2]))

        def _list_briefs(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.list_briefs(match[1], match[2] or ''))

        def _get_brief(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.get_brief(*match.groups()))

        def _list_directions(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.list_directions(match[1], after=match[2] or ''))

        def _get_direction(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.get_direction(*match.groups()))

        def _lineage_brief_scoped(self, match):
            layer = DesignLayer(service)
            # F-2a lineage reads. The project-scoped form is the one that
            # can name a foreign project (its 404 is the cross-project
            # boundary); the id-scoped form resolves the owner from the
            # record itself and fails closed on an unknown id.
            return self.send_json(200, layer.lineage_brief(*match.groups()))

        def _lineage_direction_scoped(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.lineage_direction(*match.groups()))

        def _lineage_brief_by_id(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.lineage_brief(
                layer.project_of_brief(match[1]), match[1]))

        def _lineage_direction_by_id(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.lineage_direction(
                layer.project_of_direction(match[1]), match[1]))

        def _list_token_documents(self, match):
            layer = DesignLayer(service)
            # Design-system TOKEN documents (W06 G1/G2/G3). The list form is
            # what the workbench column reads, so an empty ledger answers an
            # empty list rather than a 404 the page would have to guess at.
            return self.send_json(200, layer.list_token_documents(match[1]))

        def _get_token_document_or_lineage(self, match):
            layer = DesignLayer(service)
            return self.send_json(200, layer.token_lineage(match[1], match[2])
                                  if match[3] else layer.get_tokens(match[1], match[2]))

        def _get_project(self, match):
            project = service.get_project(match[1])
            if project is None:
                # Every sibling module answers an unknown project with this word
                # (image_assets.py:46, jury_review.py:33, model_selection.py:121 …).
                # Falling off the end here handed the client an empty reply on a
                # connection with no status line, so "the project is not there" and
                # "the service broke mid-answer" were indistinguishable at the UI.
                raise RequestError(404, 'PROJECT_NOT_FOUND')
            return self.send_json(200, {'project': project})

        def _submit_task_patch(self, match):
            value=self.body(fields={'source_attempt_id','patch','idempotency_key'},limit=1_000_000)
            return self.send_json(202,NativePatchSubmissions(service).submit(*match.groups(),**value))

        def _start_task_run(self, match):
            value=self.body(fields={'attempt_id'})
            return self.send_json(202,workers.start(*match.groups(),value['attempt_id']))

        def _submit_native_plan(self, match):
            value=self.body(fields={'host','rir','text_styles','idempotency_key'},limit=4_000_000)
            return self.send_json(202,NativeSubmissions(service).submit(match[1],**value))

        def _cancel_task(self, match):
            value = self.body(fields={'attempt_id'})
            return self.send_json(202,TaskCommands(service).cancel(*match.groups(),value['attempt_id']))

        def _create_bundle(self, match):
            self.body(fields=set())
            return self.send_json(201,NativeDelivery(service).create(*match.groups()))

        def _import_asset(self, match):
            value = self.body(fields={'content_base64', 'idempotency_key'}, limit=45_000_256)
            return self.send_json(201, ImageAssets(service).import_image(match[1], **value))

        def _derive_asset_analysis(self, match):
            # Observations arrive from the caller: no local OCR backend is qualified, so this route
            # lowers what it is given and refuses to invent any. `body()` requires the exact key set,
            # so `decomposition_id` must be present; send it as null to let the service derive a
            # reproducible identity from the stored bytes.
            value = self.body(fields={'module', 'detections', 'decomposition_id'}, limit=262_144)
            try:
                result = AssetAnalysis(service).derive(
                    match[1], match[2], module=value['module'], detections=value['detections'],
                    decomposition_id=value['decomposition_id'])
            except AssetAnalysisError as exc:
                return self.send_json(400, {'status': 'ERROR', 'error': exc.code, 'detail': exc.detail})
            return self.send_json(201, result)

        def _read_model_selection(self, match):
            # Three states stay three states: CHOSEN, DECLINED (the operator said "not used") and
            # NEVER_ASKED. Collapsing the last two is how a picker ends up reporting a decision
            # nobody made.
            from .model_selection import ModelSelection, ModelSelectionError
            try:
                return self.send_json(200, ModelSelection(service).readback(match[1]))
            except ModelSelectionError as exc:
                return self.send_json(exc.status, {'status': 'ERROR', 'error': exc.code,
                                                   'detail': exc.detail})

        def _record_model_selection(self, match):
            # Exact key set: a choice either names a catalogue model or declines, and the actor is
            # required because an unattributed selection is not a decision anyone can read back.
            from .model_selection import ModelSelection, ModelSelectionError
            value = self.body(fields={'model_id', 'declared_unused', 'actor', 'actor_kind'})
            try:
                result = ModelSelection(service).record(
                    match[1], model_id=value['model_id'],
                    declared_unused=value['declared_unused'], actor=value['actor'],
                    actor_kind=value['actor_kind'])
            except ModelSelectionError as exc:
                return self.send_json(exc.status, {'status': 'ERROR', 'error': exc.code,
                                                   'detail': exc.detail})
            return self.send_json(201, result)

        def _compose_prompt(self, match):
            # Exact key set, nullable direction: a prompt over a brief alone is a real answer,
            # an absent key is a caller bug. The document is derived from the stored brief/direction
            # rows, so re-POSTing the same request re-computes the same id -- and now keeps it: the
            # composition is stored as an addressable revision (see prompt_results.py) and the
            # response says which revision it wrote.
            value = self.body(fields={'brief_id', 'direction_id', 'target'}, limit=65_536)
            try:
                document = PromptIntelligence(service).compose(
                    match[1], brief_id=value['brief_id'],
                    direction_id=value['direction_id'], target=value['target'])
            except PromptIntelligenceError as exc:
                return self.send_json(exc.status, {'status': 'ERROR', 'error': exc.code,
                                                   'detail': exc.detail})
            return self._answered_prompt(match[1], document)

        def _reverse_asset_prompt(self, match):
            # The observations are supplied, never inferred: no qualified vision backend exists, so
            # a reversal that read the pixels would be a fabricated observation wearing a document.
            value = self.body(fields={'module', 'detections', 'decomposition_id'}, limit=262_144)
            try:
                document = PromptIntelligence(service).reverse(
                    match[1], match[2], module=value['module'], detections=value['detections'],
                    decomposition_id=value['decomposition_id'])
            except PromptIntelligenceError as exc:
                return self.send_json(exc.status, {'status': 'ERROR', 'error': exc.code,
                                                   'detail': exc.detail})
            return self._answered_prompt(match[1], document)

        def _answered_prompt(self, project_id, document):
            """Keep the document this service just produced, then answer exactly as before.

            The store is written before the response, and a store refusal is the answer -- not a
            warning. A route that returned 201 while keeping nothing is exactly the shape this
            slice exists to remove: the caller would hold a document with no address, no version
            and nothing a human could accept later. The response body itself is unchanged, because
            prompt-composition-v1 and prompt-reversal-v1 close their key sets: what the document
            IS stays defined by those contracts, and the storage facts (revision, digest, review
            state) are read from GET /api/projects/<id>/prompt-results instead of being smuggled
            into a closed document.
            """
            try:
                PromptResults(service).store(project_id, document)
            except PromptResultError as exc:
                return self.send_json(exc.status, {'status': 'ERROR', 'error': exc.code,
                                                   'detail': exc.detail})
            return self.send_json(201, PromptIntelligence.readback(document))

        def _list_prompt_results(self, match):
            # offset/limit travel on the query and are parsed here, the way the knowledge search
            # parses its own; the route declares path_only so a query cannot become a 404, and a
            # value that is not a number answers a named refusal the ledger can cite.
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))

            def number(name, default):
                raw = params.get(name)
                if raw is None or raw == '':
                    return default
                try:
                    return int(raw)
                except ValueError:
                    raise PromptResultError(
                        400, 'PROMPT_RESULT_FILTER_MALFORMED',
                        f'{name} must be an integer, got {raw!r}') from None

            try:
                envelope = PromptResults(service).readback(
                    match[1], offset=number('offset', 0),
                    limit=number('limit', PROMPT_RESULT_LIMIT))
            except PromptResultError as exc:
                return self.send_json(exc.status, {'status': 'ERROR', 'error': exc.code,
                                                   'detail': exc.detail})
            return self.send_json(200, envelope)

        def _review_prompt_result(self, match):
            value = self.body(fields={'decision', 'reviewer', 'reviewer_kind', 'reviewed_at',
                                      'note'}, limit=65_536)
            try:
                record = PromptResults(service).review(
                    match[1], result_id=match[2], decision=value['decision'],
                    reviewer=value['reviewer'], reviewer_kind=value['reviewer_kind'],
                    reviewed_at=value['reviewed_at'], note=value['note'])
            except PromptResultError as exc:
                return self.send_json(exc.status, {'status': 'ERROR', 'error': exc.code,
                                                   'detail': exc.detail})
            return self.send_json(201, record)

        def _preflight_bundle(self, match):
            # The bundle is resolved from the state database by id and
            # restricted to this project; no path arrives from the page.
            # The profile is validated here rather than trusted downstream.
            return self.send_json(200, preflight_bundle(
                service, match[1], match[2], profile=match[3] or 'digital'))

        def _record_jury_verdict(self, match):
            # The exact key set is the point: an unknown field is refused
            # rather than silently dropped, and `juror`/`criteria` stay
            # nested for the contract layer to validate.
            value = self.body(fields={
                'schemaVersion', 'kind', 'jury_record_id', 'subject_ref',
                'artifact_sha256', 'juror', 'criteria', 'verdict',
                'decided_at', 'supersedes', 'evidence_refs'}, limit=65536)
            return self.send_json(201, JuryReview(service).record_verdict(
                match[1], value))

        def _record_jury_proposal(self, match):
            value = self.body(fields={
                'schemaVersion', 'kind', 'proposal_id', 'subject_ref',
                'artifact_sha256', 'proposer', 'criteria', 'suggested_verdict',
                'rationale', 'created_at'}, limit=65536)
            return self.send_json(201, JuryReview(service).record_proposal(
                match[1], value))

        def _record_rights(self, match):
            # Exact key set, loaded from the contract itself (rights_review
            # .write_fields) rather than restated here: an unknown field is
            # refused rather than silently dropped, and a supersession link is
            # a column on the row, not a document field the closed schema never
            # declared. Superseding is how a human withdraws an approval without
            # editing history.
            value = self.body(fields=write_fields(), limit=65536)
            return self.send_json(201, RightsReview(service).record(
                match[1], value, supersedes=match[2]))

        def _record_research(self, match):
            # Exact key set again, loaded from the research-finding contract
            # (research_review.write_fields) rather than restated here, so an
            # unknown field is refused instead of dropped -- including the
            # `schemaVersion` a caller of the rights or jury routes would send by
            # habit, which this closed contract does not declare. A supersede link
            # is a column on the row, never a document field.
            value = self.body(fields=research_write_fields(), limit=65536)
            return self.send_json(201, ResearchReview(service).record(
                match[1], value, supersedes=match[2]))

        def _create_knowledge_candidate(self, match):
            # The document is built server-side by the contract module; the caller
            # supplies only the inputs it validated. `schemaVersion` is not an
            # input: letting a caller choose it would let a stale client write a
            # version the read path no longer knows. A supersede link is a query
            # parameter, the same shape the rights and research routes use: it
            # names the row being replaced, and the document contract has no field
            # a caller could disagree with it through.
            value = self.body(fields={
                'candidate_id', 'candidate_type', 'source', 'rights', 'payload',
                'created_at', 'revocation_entrypoint'}, limit=65536)
            return self.send_json(201, KnowledgeReview(service).create(
                match[1], value, supersedes=match[2]))

        def _review_knowledge_candidate(self, match):
            # `reviewer_kind` is a field of the request, not an assumption: the
            # service refuses anything but a named human, and the refusal travels
            # as KNOWLEDGE_HUMAN_REVIEW_REQUIRED rather than as a generic 400.
            value = self.body(fields={
                'decision', 'reviewer_id', 'reviewer_kind', 'reviewed_at',
                'note', 'reason'}, limit=16384)
            return self.send_json(200, KnowledgeReview(service).review(
                match[1], match[2], value))

        def _revoke_knowledge_candidate(self, match):
            value = self.body(fields={'reason', 'revoked_by', 'revoked_at'},
                              limit=16384)
            return self.send_json(200, KnowledgeReview(service).revoke(
                match[1], match[2], value))

        # DL-KB-02/04: the library a person writes into, as opposed to the candidate a run
        # produced. The six routes share one store (knowledge_library.KnowledgeLibrary) and one
        # writer inside it; these methods only translate HTTP into its calls.
        def _search_knowledge_entries(self, match):
            # A global read, like /api/capabilities: no project id is needed to search a prompt
            # library, and scoping it per project would make the same entry invisible from the
            # next project. The query is parsed with urlsplit + parse_qsl for the same reason
            # _task_preflight does it -- the route declares path_only, so a present query must
            # reach the handler instead of turning into a 404.
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))

            def number(name, default):
                raw = params.get(name)
                if raw is None or raw == '':
                    return default
                try:
                    return int(raw)
                except ValueError:
                    raise KnowledgeLibraryError(
                        400, 'KNOWLEDGE_FILTER_MALFORMED',
                        f'{name} must be an integer, got {raw!r}') from None

            return self.send_json(200, KnowledgeLibrary(service).search(
                query=params.get('q') or None,
                entry_type=params.get('type') or None,
                domain=params.get('domain') or None,
                task=params.get('task') or None,
                target=params.get('target') or None,
                offset=number('offset', 0),
                limit=number('limit', DEFAULT_LIMIT)))

        def _get_knowledge_entry(self, match):
            return self.send_json(200, KnowledgeLibrary(service).detail(match[1]))

        def _create_knowledge_entry(self, match):
            # Exact key set: an unknown field is refused instead of dropped, so a client that
            # believes it set `source.license` cannot have its typo silently discarded.
            # `schemaVersion` is deliberately not a field -- the store writes its own, and a
            # caller choosing it could write a version the read path does not know.
            value = self.body(fields={
                'entry_type', 'title', 'summary', 'domain_tags', 'task_tags', 'target_tools',
                'body', 'applicability', 'limits', 'source', 'related_capability_ids',
                'recommended', 'created_by', 'supersedes'}, limit=262144)
            return self.send_json(201, KnowledgeLibrary(service).create(value))

        def _revise_knowledge_entry(self, match):
            value = self.body(fields={
                'entry_type', 'title', 'summary', 'domain_tags', 'task_tags', 'target_tools',
                'body', 'applicability', 'limits', 'source', 'related_capability_ids',
                'recommended', 'created_by', 'expected_revision'}, limit=262144)
            return self.send_json(201, KnowledgeLibrary(service).revise(
                match[1], value))

        def _record_knowledge_judgement(self, match):
            # `recorded_at` is not a caller field: the service stamps the moment it accepts the
            # judgement, so a client cannot date its own decision. The answer is the entry's own
            # readback, which now carries the judgement and the moved pointer.
            value = self.body(fields={
                'kind', 'revision', 'value', 'replaced_by', 'reason', 'recorded_by',
                'recorded_by_kind'}, limit=65536)
            return self.send_json(201, KnowledgeLibrary(service).record_judgement(
                match[1], value))

        def _import_knowledge_entry(self, match):
            # Same document contract as create, plus `imported_by` and the same optional
            # `supersedes` link: an import is how an authoritative document replaces a rough
            # note, and a set of fields that quietly differed from create would be a second
            # contract for the same document.
            value = self.body(fields={
                'entry_type', 'title', 'summary', 'domain_tags', 'task_tags', 'target_tools',
                'body', 'applicability', 'limits', 'source', 'related_capability_ids',
                'recommended', 'imported_by', 'supersedes'}, limit=262144)
            return self.send_json(201, KnowledgeLibrary(service).import_entry(value))

        def _rebuild_knowledge_index(self, match):
            # The rebuild is the index's proof of derivability, not a repair of a read: an
            # empty body keeps it from taking parameters it would have to pretend to honour.
            self.body(fields=set(), limit=1024)
            return self.send_json(200, KnowledgeLibrary(service).rebuild_index())

        def _list_assistance_plans(self, match):
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))

            def number(name, default):
                raw = params.get(name)
                if raw is None or raw == '':
                    return default
                try:
                    return int(raw)
                except ValueError:
                    raise AssistancePlanError(
                        400, 'ASSISTANCE_PLAN_FILTER_MALFORMED',
                        f'{name} must be an integer, got {raw!r}') from None

            return self.send_json(200, AssistancePlans(service).list(
                match[1], offset=number('offset', 0),
                limit=number('limit', PLAN_DEFAULT_LIMIT)))

        def _assistance_plan_output_types(self, match):
            # The material table is the exporter's own list, handed to the plan store here at the
            # composition root: `assistance_plan.py` cannot import `plan_export` (the exporter
            # imports the plan store), and the screen must not type the four format words a second
            # time. The store then validates the merged envelope against one contract.
            return self.send_json(200, AssistancePlans(service).output_types(material_table()))

        def _get_assistance_plan(self, match):
            return self.send_json(200, AssistancePlans(service).detail(match[1], match[2]))

        def _get_assistance_plan_revision(self, match):
            # One stored revision, read back as the bytes that row holds. The number arrives as a
            # path segment, so a page that asked for r1 of a two-revision plan cannot be answered
            # with r2: that fallback is the defect this route exists to remove, and the store
            # refuses an unstored number with ASSISTANCE_PLAN_REVISION_NOT_FOUND naming the highest
            # revision that does exist. Reading a revision says nothing about whether anything ran.
            return self.send_json(200, AssistancePlans(service).revision(
                match[1], match[2], int(match[3])))

        def _export_assistance_plan(self, match):
            # One read, four renderings, zero writes. `format` is parsed here rather than in the
            # pattern so an absent or unknown word keeps its own code: a 404 would tell the page the
            # plan is gone when the plan is perfectly there and only the requested material was not
            # named. A 分镜 CSV of a plan with no shot rows is refused 409 by the emitter, never
            # answered as an empty table.
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))
            return self.send_json(200, PlanExport(service).export(
                match[1], match[2], params.get('format')))

        def _create_assistance_plan(self, match):
            # The exact key set a plan's create accepts. A caller cannot state a reference's
            # revision or digest (the store resolves them), and cannot name an `executed` flag:
            # an unknown field is refused, not dropped. `shots` (DL-KB-11) is the one optional key:
            # the plan's own shot rows are data a person writes, they are what the 分镜 CSV renders
            # from, and a caller that has none simply does not send the key -- a plan stored before
            # the field existed stays valid, which is why demanding it here would be a break.
            value = self.body(fields={
                'objective', 'output_type', 'neutral_creative', 'brand_constraints',
                'role_constraints', 'lens', 'sound', 'references', 'external_steps',
                'known_gaps', 'limits', 'created_by'}, optional={'shots'}, limit=262144)
            return self.send_json(201, AssistancePlans(service).create(match[1], value))

        def _revise_assistance_plan(self, match):
            value = self.body(fields={
                'objective', 'output_type', 'neutral_creative', 'brand_constraints',
                'role_constraints', 'lens', 'sound', 'references', 'external_steps',
                'known_gaps', 'limits', 'created_by', 'expected_revision'},
                optional={'shots'}, limit=262144)
            return self.send_json(201, AssistancePlans(service).revise(
                match[1], match[2], value))

        def _choose_assistance_plan(self, match):
            value = self.body(fields={'actor', 'actor_kind', 'revision'}, limit=4096)
            return self.send_json(200, AssistancePlans(service).choose(
                match[1], match[2], value))
        def _list_plan_feedback(self, match):
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))

            def number(name, default, *, maximum=None):
                raw = params.get(name)
                if raw is None or raw == '':
                    return default
                try:
                    value = int(raw)
                except ValueError:
                    raise PlanFeedbackError(
                        400, 'PLAN_FEEDBACK_FILTER_MALFORMED',
                        f'{name} must be an integer, got {raw!r}') from None
                if maximum is not None and value > maximum:
                    raise PlanFeedbackError(400, 'PLAN_FEEDBACK_FILTER_MALFORMED',
                                            f'{name} may not exceed {maximum}')
                return value

            return self.send_json(200, PlanFeedback(service).list(
                match[1], match[2], offset=number('offset', 0),
                limit=number('limit', FEEDBACK_DEFAULT_LIMIT, maximum=FEEDBACK_MAX_LIMIT)))

        def _record_plan_feedback(self, match):
            # `revision` is required: a report is about the material somebody actually took away, so
            # it has to name the revision it describes. There is no `verified` key the caller could
            # set -- the store refuses to let a feedback row speak for the system.
            value = self.body(fields={'outcome', 'target_key', 'target_model', 'dimensions',
                                      'issue_timecodes', 'actor', 'note', 'source_ref',
                                      'revision'}, limit=16384)
            return self.send_json(201, PlanFeedback(service).record(match[1], match[2], value))

        def _target_profile_axes(self, match):
            return self.send_json(200, TargetProfiles(service).axes())

        def _list_target_profiles(self, match):
            params = dict(parse_qsl(urlsplit(self.path).query, keep_blank_values=True))

            def number(name, default, *, maximum=None):
                raw = params.get(name)
                if raw is None or raw == '':
                    return default
                try:
                    value = int(raw)
                except ValueError:
                    raise TargetProfileError(
                        400, 'TARGET_PROFILE_FILTER_MALFORMED',
                        f'{name} must be an integer, got {raw!r}') from None
                if maximum is not None and value > maximum:
                    raise TargetProfileError(400, 'TARGET_PROFILE_FILTER_MALFORMED',
                                             f'{name} may not exceed {maximum}')
                return value

            return self.send_json(200, TargetProfiles(service).list(
                offset=number('offset', 0),
                limit=number('limit', PROFILE_DEFAULT_LIMIT, maximum=PROFILE_MAX_LIMIT)))

        def _get_target_profile(self, match):
            return self.send_json(200, TargetProfiles(service).detail(match[1]))

        def _create_target_profile(self, match):
            # The exact key set a draft accepts. A caller cannot state support_state or executable:
            # a draft is marked unverified by the store, and the table's CHECK refuses any other
            # support state, so no write path can relabel a person's guess as a documented claim.
            value = self.body(fields={'software', 'agent', 'model', 'provider', 'version',
                                      'entry', 'task_mode', 'actor', 'source_ref', 'fields'},
                              limit=262144)
            return self.send_json(201, TargetProfiles(service).create(value))

        def _validate_target_profile(self, match):
            value = self.body(fields={'dimensions'}, limit=65536)
            return self.send_json(200, TargetProfiles(service).validate(match[1], value))

        def _create_brief(self, match):
            layer = DesignLayer(service)
            value = self.body(fields={'title', 'goals', 'constraints', 'reference_asset_ids', 'idempotency_key'})
            return self.send_json(201, layer.create_brief(match[1], **value))

        def _create_direction(self, match):
            layer = DesignLayer(service)
            value = self.body(fields={'brief_id', 'title', 'style_notes', 'color_mood', 'typography_mood', 'idempotency_key'})
            return self.send_json(201, layer.create_direction(match[1], **value))

        def _choose_direction(self, match):
            layer = DesignLayer(service)
            value = self.body(fields={'actor', 'actor_kind', 'idempotency_key'})
            return self.send_json(200, layer.choose_direction(match[1], match[2], **value))

        def _bind_design_system(self, match):
            layer = DesignLayer(service)
            value = self.body(fields={'design_system_name', 'idempotency_key'})
            return self.send_json(201, layer.bind_design_system(match[1], match[2], **value))

        def _revise_brief_scoped(self, match):
            layer = DesignLayer(service)
            # F-2a revisions: appending the next version of a brief or a
            # direction. The full content is re-sent (a revision is a new
            # immutable row); the project-scoped form fails closed on a
            # foreign project, the id-scoped form resolves the owner and
            # fails closed on an unknown id.
            value = self.body(fields={'title', 'goals', 'constraints',
                                       'reference_asset_ids', 'idempotency_key'})
            return self.send_json(201, layer.revise_brief(match[1], match[2], **value))

        def _revise_direction_scoped(self, match):
            layer = DesignLayer(service)
            value = self.body(fields={'title', 'style_notes', 'color_mood',
                                       'typography_mood', 'idempotency_key'})
            return self.send_json(201, layer.revise_direction(match[1], match[2], **value))

        def _revise_brief_by_id(self, match):
            layer = DesignLayer(service)
            value = self.body(fields={'title', 'goals', 'constraints',
                                       'reference_asset_ids', 'idempotency_key'})
            return self.send_json(201, layer.revise_brief(
                layer.project_of_brief(match[1]), match[1], **value))

        def _revise_direction_by_id(self, match):
            layer = DesignLayer(service)
            value = self.body(fields={'title', 'style_notes', 'color_mood',
                                       'typography_mood', 'idempotency_key'})
            return self.send_json(201, layer.revise_direction(
                layer.project_of_direction(match[1]), match[1], **value))

        def _write_tokens(self, match):
            layer = DesignLayer(service)
            # Exact-key body again: an unknown field is refused rather
            # than dropped, and `expected_version` is what makes a lost
            # concurrent revision visible instead of silent.
            value = self.body(fields=TOKEN_WRITE_FIELDS, limit=262_144)
            return self.send_json(201, layer.write_tokens(match[1], match[2], **value))

        def _create_project(self, match):
            value = self.body()
            return self.send_json(201, {'project': service.create_project(value['name'])})

        do_GET = dispatch
        do_POST = dispatch
        do_DELETE = dispatch
        do_PUT = dispatch
        do_PATCH = dispatch
        do_OPTIONS = dispatch

    return HTTPServer(('127.0.0.1', port), Handler)
