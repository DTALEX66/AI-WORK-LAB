# SPDX-License-Identifier: MIT
"""Explicit-project CLI; no inferred install-directory or user-profile writes."""
import argparse
import hashlib
import json
import sqlite3
import sys

from . import __version__
from .runtime.asset_store import AssetError
from .runtime.paths import PathPolicyError
from .runtime.project_backup import BackupError
from .service import ProjectService


def _recovery_summary(readback):
    """Compact "what needs a decision and why".

    Never serializes stored jobs, authorization receipts or file paths: the
    fields below are ledger state words and reason codes only.
    """
    return {'status': readback['status'], 'error': readback.get('error'),
            'pending': readback['pending'], 'actionable': readback['actionable'],
            'listed': readback['listed'], 'truncated': readback['truncated'],
            'needsDecision': [{'attempt_id': d['attempt_id'], 'project_id': d['project_id'],
                               'host': d['host'], 'state': d['state'],
                               'operation': d['operation'], 'action': d['action'],
                               'reason': d['reason'], 'worker_active': d['worker_active'],
                               'receipt_persisted': d['receipt_persisted'],
                               'request_bound': d['request_bound'],
                               'quiescence_recorded': d['quiescence_recorded'],
                               'blocking_attempt_id': d.get('blocking_attempt_id'),
                               'host_guard': d['host_guard']}
                              for d in readback['decisions']]}


def _quality_criteria(raw_items):
    """Parse `--criterion id:weight:score[:note]` into criterion documents.

    Shape only: the weights-summing-to-one, the score range and the "an extreme
    score needs a note" rules belong to human_jury, which validates what this
    returns. Silently defaulting a weight or a score here would put words in the
    juror's mouth, so a malformed part raises instead.
    """
    documents = []
    for raw in (raw_items or ()):
        parts = str(raw).split(':', 3)
        if len(parts) < 3:
            raise ValueError(f'--criterion {raw!r} must be criterion_id:weight:score[:note]')
        try:
            weight = float(parts[1])
            score = float(parts[2])
        except ValueError:
            raise ValueError(f'--criterion {raw!r} carries a weight or score that is not a '
                             'number') from None
        documents.append({'criterion_id': parts[0].strip(), 'weight': weight, 'score': score,
                          'note': parts[3].strip() if len(parts) > 3 else None})
    return documents


def main(argv=None):
    parser = argparse.ArgumentParser(prog='design-lab')
    parser.add_argument('--version', action='version', version=__version__)
    parser.add_argument('--project', required=True, help='explicit owning project directory')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('paths', help='read-only project path diagnosis')
    server = commands.add_parser('serve', help='loopback metadata API; launcher supplies temporary token on stdin')
    server.add_argument('--port', type=int, default=0)
    workbench = commands.add_parser(
        'workbench',
        help='start the service and print the sign-in URL and one-time token (no external launcher)')
    workbench.add_argument('--port', type=int, default=0)
    workbench.add_argument('--no-browser', action='store_true',
                           help='print the URL instead of opening the local browser')
    workbench.add_argument('--manual-connect', action='store_true',
                           help='compatibility mode: print a temporary token instead of '
                                'connecting the launched page automatically')
    worker = commands.add_parser('native-worker', help='execute one persisted approved native attempt')
    worker.add_argument('--attempt', required=True)
    recovery_command = commands.add_parser(
        'native-recovery',
        help='list persisted native attempts whose outcome is unknown; decide one only with '
             'explicit operator authorization')
    recovery_command.add_argument('--attempt', default=None,
                          help='unresolved attempt to decide; omit to list without acting')
    recovery_command.add_argument('--actor', default=None,
                         help='operator identity recorded on the decision (required with --attempt)')
    recovery_command.add_argument('--receipt', default=None,
                         help='the operator statement authorizing this decision (required with --attempt)')
    trail = commands.add_parser(
        'audit-trail',
        help='read back the writer journal: lease takeovers and versions created by an attempt')
    trail.add_argument('--limit', type=int, default=20,
                       help='rows to read, newest first (1-200)')
    # 2026-10-08: the Quality gate reachable from the product. Every input below is
    # optional AT THE PARSER LEVEL on purpose: a missing one is refused in this file's
    # own JSON error vocabulary (like native-recovery does), not as argparse usage
    # text, so an operator scripting this verb always gets a machine-readable reason.
    quality = commands.add_parser(
        'quality',
        help='record one sealed quality assessment, or --record omitted: read back what is '
             'recorded, whether any of it is human acceptance, and what none of it proves')
    quality.add_argument('--project-id', default=None, help='owning project id (32 hex)')
    quality.add_argument('--record', action='store_true',
                         help='append one assessment; without it this verb reads back and '
                              'writes nothing')
    quality.add_argument('--subject', default=None,
                         help='"version:<id>" the assessment is about (required with --record)')
    quality.add_argument('--digest', default=None,
                         help='artifact_sha256 being judged; it must be the digest that version '
                              'holds (required with --record)')
    quality.add_argument('--actor', default=None,
                         help='who signs the human acceptance (required with --record)')
    quality.add_argument('--actor-kind', dest='actor_kind', default=None,
                         help='HUMAN or PANEL; an automated kind is refused by name '
                              '(required with --record)')
    quality.add_argument('--attestation', default=None,
                         help='what that actor actually looked at and how '
                              '(required with --record)')
    quality.add_argument('--verdict', default=None,
                         help='APPROVE or REJECT, signed by the actor above '
                              '(required with --record)')
    quality.add_argument('--criterion', action='append', dest='criteria', default=None,
                         help='criterion_id:weight:score[:note] the verdict was judged on '
                              '(repeatable; weights must sum to 1.0)')
    quality.add_argument('--evidence', action='append', dest='evidence_refs', default=None,
                         help='evidence ref supporting a REJECT (repeatable)')
    quality.add_argument('--member', action='append', dest='panel_members', default=None,
                         help='named member of a PANEL juror (repeatable)')
    quality.add_argument('--supersedes', default=None,
                         help='quality_record_id this assessment replaces (append-only: the '
                              'replaced record stays readable)')
    quality.add_argument('--record-id', dest='record_id', default=None,
                         help='explicit quality_record_id, so a retry of a submission is '
                              'refused as taken instead of appending a second record')
    # 2026-10-08: the RIGHTS gate reachable from the product, in the same shape as
    # `quality` above. Every write input is optional at the parser level so a missing one
    # is answered in this file's own JSON error vocabulary rather than as argparse usage
    # text -- an operator scripting this verb gets a machine-readable reason either way.
    rights = commands.add_parser(
        'rights',
        help='record one human rights decision, or --record omitted: read back what is '
             'filed, what stands per use scope, and what none of it proves')
    rights.add_argument('--project-id', default=None, help='owning project id (32 hex)')
    rights.add_argument('--record', action='store_true',
                        help='append one decision; without it this verb reads back and writes '
                             'nothing')
    rights.add_argument('--scope', default=None,
                        help='use_scope the decision is about, e.g. commercial-print '
                             '(required with --record)')
    rights.add_argument('--decision', default=None,
                        help='one of the contract enum: APPROVED, DENIED, PENDING_REVIEW, '
                             'BLOCKED_BY_LICENSE (required with --record)')
    rights.add_argument('--decided-by', dest='decided_by', default=None,
                        help='who signed the decision; an actor that names automation is '
                             'refused by name (required with --record)')
    rights.add_argument('--decided-at', dest='decided_at', default=None,
                        help='RFC 3339 timestamp of the decision, e.g. 2026-10-08T00:00:00Z; '
                             'nothing is defaulted, because a timestamp this verb invented is '
                             'not the moment a human decided (required with --record)')
    rights.add_argument('--actor-kind', dest='actor_kind', default=None,
                        help='HUMAN or PANEL; declared as a column the contract cannot carry, '
                             'so a CLI-filed decision is a declared human signature rather '
                             'than a name-checked one (required with --record)')
    rights.add_argument('--decision-id', dest='decision_id', default=None,
                        help='explicit decision_id, so a retry of a submission is refused as '
                             'taken instead of appending a second decision')
    rights.add_argument('--territory', default=None,
                        help='territory the approval covers (optional)')
    rights.add_argument('--license-ref', dest='license_ref', default=None,
                        help='the licence or terms this decision was taken under (optional)')
    rights.add_argument('--note', default=None,
                        help='what the decision-maker stated about it (optional)')
    rights.add_argument('--supersedes', default=None,
                        help='decision_id this decision replaces (append-only: the replaced '
                             'decision stays readable, and it must be about the same scope)')
    # 2026-10-08: research findings become citable state. Same shape as `rights` above, and
    # deliberately NOT a gate verb: every write input is optional at the parser level so a
    # missing one is answered in this file's own JSON error vocabulary rather than as argparse
    # usage text, and no claim, no source and no author is ever defaulted by this verb.
    research = commands.add_parser(
        'research',
        help='record one research finding against a project, or --record omitted: read back '
             'what is filed, how much of it cites a source, and what none of it proves')
    research.add_argument('--project-id', default=None, help='owning project id (32 hex)')
    research.add_argument('--record', action='store_true',
                          help='append one finding; without it this verb reads back and writes '
                               'nothing')
    research.add_argument('--claim', default=None,
                          help='the finding being recorded (required with --record)')
    research.add_argument('--source', action='append', dest='source_refs', default=None,
                          help='a source this finding rests on, e.g. interview-07 or '
                               'bench-figma-2026-05 (repeatable, required with --record: a '
                               'claim with no source is a guess, and the store refuses one)')
    research.add_argument('--confidence', default=None,
                          help='one of the contract enum: high, medium, low, speculative '
                               '(optional; nothing is defaulted, because an unstated '
                               'confidence is a different record from an invented one)')
    research.add_argument('--not-design-rule', dest='not_design_rule', action='store_true',
                          help='state explicitly that this finding is not a design rule. The '
                               'contract can only ever carry `true`, so the flag adds the '
                               'disclaimer; omitting it stores no disclaimer rather than '
                               'assuming one')
    research.add_argument('--finding-id', dest='finding_id', default=None,
                          help='explicit finding_id, so a retry of a submission is refused as '
                               'taken instead of appending a second finding')
    research.add_argument('--recorded-by', dest='recorded_by', default=None,
                          help='who or what authored the finding (optional; omitted, it is '
                               'stored unattributed and the read-back lists it as such)')
    research.add_argument('--actor-kind', dest='actor_kind', default=None,
                          help='HUMAN/PANEL or an automated kind. A finding is not a human '
                               'gate, so an agent may record one -- but declaring HUMAN while '
                               'naming automation is refused by name (see RESEARCH_NOT_HUMAN)')
    research.add_argument('--supersedes', default=None,
                          help='finding_id this finding replaces (append-only: the replaced '
                               'finding stays readable, and it must be a finding of the same '
                               'project)')
    projects = commands.add_parser('projects').add_subparsers(dest='action', required=True)
    projects.add_parser('list')
    projects.add_parser('create').add_argument('--name', required=True)
    delivery = commands.add_parser(
        'delivery-receipt',
        help='read back the persisted delivery receipt of one published bundle version, '
             'with the claims it does not make')
    delivery.add_argument('--project-id', required=True, help='owning project id (32 hex)')
    delivery.add_argument('--bundle', required=True, help='bundle asset id published by a delivery')
    delivery.add_argument('--version', required=True, help='bundle version id of that delivery')
    backup = commands.add_parser('backup',
                                 help='archive the durable project state into one verified zip')
    backup.add_argument('--out', default=None, help='target directory or .zip path')
    backup.add_argument('--member', action='append', dest='members',
                        help='local-root-relative path to include (repeatable)')
    restore = commands.add_parser('restore', help='unpack a backup and re-verify every hash')
    restore.add_argument('--from', dest='archive', required=True)
    restore.add_argument('--into', default=None,
                         help='target local root; defaults to this project\'s own')
    restore.add_argument('--force', action='store_true',
                         help='allow restoring over a non-empty target')
    restore.add_argument('--allow-upgrade', action='store_true',
                         help='restore despite a version or state-schema mismatch')
    analyze = commands.add_parser(
        'analyze',
        help='lower one stored raster asset plus an explicit observation file into a '
             'reconstruction-ir/v1 document; it runs no model and proves no host call')
    analyze.add_argument('--project-id', required=True, help='owning project id (32 hex)')
    analyze.add_argument('--asset', required=True,
                         help='the img-… identifier the import route returned')
    analyze.add_argument('--observations', required=True,
                         help='JSON file holding {"module": …, "detections": [{text, confidence, '
                              'polygon}]}; observations are supplied, never inferred here')
    prompt = commands.add_parser(
        'prompt', help='Prompt Intelligence: compose a visual prompt from stored records, or '
                       'reverse-describe one stored asset from an explicit observation file')
    prompt_action = prompt.add_subparsers(dest='action', required=True)
    prompt_generate = prompt_action.add_parser(
        'generate',
        help='assemble a prompt-composition/v1 document from one live brief (and, when one is '
             'chosen or named, its direction); nothing is invented and no model runs')
    prompt_generate.add_argument('--project-id', required=True, help='owning project id (32 hex)')
    prompt_generate.add_argument('--brief', required=True,
                                 help='the brief-… identifier the brief route returned')
    prompt_generate.add_argument('--direction', default=None,
                                 help='optional direction-…; without it the single chosen direction '
                                      'of that brief is used, and with none the prompt says so')
    prompt_generate.add_argument('--target', default='image-generation',
                                 help='a visual family recorded in design-lab/readiness/'
                                      'model-radar.json (image-generation, video-generation, 3d)')
    prompt_reverse = prompt_action.add_parser(
        'reverse',
        help='restate one stored asset as a prompt from an explicit observation file; it describes '
             'what was observed, never what the picture depicts')
    prompt_reverse.add_argument('--project-id', required=True, help='owning project id (32 hex)')
    prompt_reverse.add_argument('--asset', required=True,
                                help='the img-… identifier the import route returned')
    prompt_reverse.add_argument('--observations', required=True,
                                help='the same {"module", "detections"} file analyze accepts')
    exporting = commands.add_parser(
        'export-candidate',
        help='produce the two outbound projections of one stored knowledge candidate; nothing is '
             'sent, because this repository has no ArcheAxis transport')
    exporting.add_argument('--project-id', required=True, help='owning project id (32 hex)')
    exporting.add_argument('--candidate', required=True,
                           help='the candidate id the knowledge-candidates route returned')
    models = commands.add_parser(
        'models', help='the model catalogue and this project\'s recorded choice; listing and '
                       'choosing run no model and send nothing')
    models_action = models.add_subparsers(dest='action', required=True)
    models_action.add_parser('list', help='print GET /api/models as assembled from the registries')
    models_show = models_action.add_parser('show', help='read back one project\'s recorded choice')
    models_show.add_argument('--project-id', required=True, help='owning project id (32 hex)')
    models_choose = models_action.add_parser(
        'choose', help='record a choice for one project: a catalogue model_id, or --unused')
    models_choose.add_argument('--project-id', required=True, help='owning project id (32 hex)')
    models_choose.add_argument('--model', default=None,
                               help='a model_id exactly as GET /api/models reports it; the service '
                                    'copies its facts, it does not accept yours')
    models_choose.add_argument('--unused', action='store_true',
                               help='record the explicit decision not to use a model')
    models_choose.add_argument('--actor', required=True,
                               help='who made this choice (required: an unattributed choice is not '
                                    'a decision anyone can read back)')
    models_choose.add_argument('--actor-kind', default='human', choices=('human', 'agent'),
                               help='the design layer\'s vocabulary, not a second one')
    args = parser.parse_args(argv)
    if hasattr(sys.stdout, 'reconfigure'):
        sys.stdout.reconfigure(encoding='utf-8')
    try:
        service = ProjectService(args.project)
        if args.command == 'serve':
            from .http_service import make_server
            if sys.stdin.isatty():
                raise ValueError('SERVICE_REQUIRES_LAUNCHER_STDIN')
            token = sys.stdin.readline(66).rstrip('\r\n')
            reconciled = service.reconcile_interrupted_attempts()
            recovery_summary = _recovery_summary(service.recovery_readback())
            with make_server(service, token, args.port) as httpd:
                print(json.dumps({'status': 'LISTENING', 'host': '127.0.0.1',
                                  'port': httpd.server_port,
                                  'reconciled_attempts': len(reconciled),
                                  'recovery': recovery_summary}), flush=True)
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    pass
            return 0
        elif args.command == 'workbench':
            import secrets
            from .http_service import make_server
            token = secrets.token_hex(32)
            reconciled = service.reconcile_interrupted_attempts()
            recovery_summary = _recovery_summary(service.recovery_readback())
            with make_server(service, token, args.port,
                             local_session=not args.manual_connect) as httpd:
                url = f'http://127.0.0.1:{httpd.server_port}/workbench'
                # The token is the sign-in the Workbench asks for; it lives only in
                # this process and this terminal, never in argv, a file or a URL.
                # In the default mode it is not even printed: the launched page
                # picks it up through the same-origin handshake, so nothing has to
                # be copied, and a stray terminal scrollback cannot carry a secret.
                print(json.dumps({'status': 'LISTENING', 'url': url,
                                  'port': httpd.server_port,
                                  'reconciled_attempts': len(reconciled),
                                  'recovery': recovery_summary,
                                  **({'token': token,
                                      'token_ttl': 'until this process exits'}
                                     if args.manual_connect
                                     else {'connection': 'automatic'})}), flush=True)
                if not args.no_browser:
                    import webbrowser
                    webbrowser.open(url)
                try:
                    httpd.serve_forever()
                except KeyboardInterrupt:
                    pass
            return 0
        elif args.command == 'backup':
            from datetime import datetime, timezone
            from pathlib import Path
            from .runtime.project_backup import create_backup
            local_root = Path(service.paths.local_root)
            members = tuple(args.members) if args.members else None
            stamp = datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
            destination = Path(args.out) if args.out else local_root / 'backups'
            if destination.suffix.lower() == '.zip':
                destination.parent.mkdir(parents=True, exist_ok=True)
            else:
                destination.mkdir(parents=True, exist_ok=True)
                destination = destination / f'design-lab-backup-{stamp}.zip'
            manifest = create_backup(local_root, destination, members=members,
                                     version=__version__)
            result = {'status': 'BACKUP_CREATED', 'archive': destination.name,
                      'fileCount': manifest['fileCount'],
                      'totalBytes': manifest['totalBytes'],
                      'sha256': hashlib.sha256(destination.read_bytes()).hexdigest(),
                      'createdAt': manifest['createdAt']}
        elif args.command == 'restore':
            from pathlib import Path
            from .runtime.project_backup import restore_backup, state_schema_version
            target = Path(args.into) if args.into else service.paths.local_root
            result = restore_backup(
                args.archive, target, force=args.force, allow_upgrade=args.allow_upgrade,
                version=__version__,
                local_state_schema_version=state_schema_version(service.paths.local_root))
            result['status'] = 'RESTORE_VERIFIED'
            result['target'] = Path(target).name
        elif args.command == 'audit-trail':
            from .runtime.audit_trail import recent as _audit_recent
            try:
                print(json.dumps({'status': 'AUDIT_TRAIL',
                                  'journal': _audit_recent(service, limit=args.limit)},
                                 ensure_ascii=False, sort_keys=True))
            except ValueError as exc:
                # The limit is the caller's mistake, not the store's; say which so the
                # operator does not go looking for a broken database.
                print(json.dumps({'status': 'ERROR', 'error': 'INVALID_AUDIT_TRAIL_REQUEST',
                                  'detail': str(exc)}, ensure_ascii=False, sort_keys=True))
                return 2
        elif args.command == 'quality':
            from contextlib import closing
            from .assurance import AssuranceError, quality_store
            if not args.project_id:
                print(json.dumps({'status': 'ERROR', 'error': 'QUALITY_PROJECT_REQUIRED',
                                  'detail': 'quality needs --project-id; the state database '
                                            'holds every project of this owner and a read must '
                                            'not guess one'}, ensure_ascii=False))
                return 2
            if service.get_project(args.project_id) is None:
                # Checked before anything opens the database: a read for an unknown
                # project id must not create runtime state, and it must not read as an
                # empty honest "nothing recorded yet" for a project that does not exist.
                print(json.dumps({'status': 'ERROR', 'error': 'QUALITY_PROJECT_UNKNOWN',
                                  'detail': f'project {args.project_id} is not recorded in '
                                            'this owner root', 'create_with': 'design-lab '
                                            '--project <dir> projects create --name <name>'},
                                 ensure_ascii=False))
                return 2
            if args.record:
                missing_inputs = [name for name, value in (
                    ('--subject', args.subject), ('--digest', args.digest),
                    ('--actor', args.actor), ('--actor-kind', args.actor_kind),
                    ('--attestation', args.attestation), ('--verdict', args.verdict))
                    if not (isinstance(value, str) and value.strip())]
                if missing_inputs:
                    # No default actor, no default attestation, no default verdict: an
                    # assessment this verb cannot attribute to a named human is not one
                    # the product may file for them.
                    print(json.dumps({'status': 'ERROR',
                                      'error': 'QUALITY_RECORD_INPUTS_REQUIRED',
                                      'detail': 'recording needs ' + ', '.join(missing_inputs)
                                                + '; omit --record to read the assessments '
                                                  'already recorded'}, ensure_ascii=False))
                    return 2
                try:
                    criterion_docs = _quality_criteria(args.criteria)
                except ValueError as exc:
                    # A mistyped --criterion is the operator's mistake, not the gate's;
                    # naming it here keeps the store from being blamed for a typo.
                    print(json.dumps({'status': 'ERROR', 'error': 'INVALID_QUALITY_CRITERION',
                                      'detail': str(exc)}, ensure_ascii=False))
                    return 2
                if not criterion_docs:
                    print(json.dumps({'status': 'ERROR',
                                      'error': 'QUALITY_CRITERION_MISSING',
                                      'detail': 'recording a human acceptance needs at least '
                                                'one --criterion id:weight:score[:note]; a '
                                                'verdict nobody described certifies nothing'},
                                     ensure_ascii=False))
                    return 2
            with closing(quality_store.connect(
                    service.paths.database_path(service.database),
                    project_root=service.paths.project_root)) as quality_conn:
                try:
                    if args.record:
                        verdict_document = quality_store.human_acceptance(
                            actor=args.actor, actor_kind=args.actor_kind,
                            attestation=args.attestation, verdict=args.verdict,
                            subject_ref=args.subject, artifact_sha256=args.digest,
                            criteria=criterion_docs, members=args.panel_members or (),
                            evidence_refs=args.evidence_refs or ())
                        stored_record = quality_store.record(
                            quality_conn, project_id=args.project_id,
                            subject_ref=args.subject, artifact_sha256=args.digest,
                            human_verdict=verdict_document, supersedes=args.supersedes,
                            quality_record_id=args.record_id)
                        readback_view = quality_store.summary(quality_conn, args.project_id)
                        # The receipt repeats the limits instead of summarising them away:
                        # the person recording is the person most likely to over-read a PASS.
                        result = {'status': 'QUALITY_RECORDED',
                                  'record': stored_record,
                                  'final_gate': stored_record['final_gate'],
                                  'human_acceptance': readback_view['human_acceptance'],
                                  'record_count': readback_view['record_count'],
                                  'does_not_prove': readback_view['does_not_prove']}
                    else:
                        result = {'status': 'QUALITY_READBACK',
                                  **quality_store.summary(quality_conn, args.project_id)}
                except quality_store.QualityStoreError as exc:
                    # Every refusal this verb makes carries the code that names the rule,
                    # so an operator can tell a wrong digest from an unknown project from
                    # an automated judge trying to sign a human gate.
                    print(json.dumps({'status': 'ERROR', 'error': exc.code, 'detail': str(exc),
                                      'project_id': args.project_id}, ensure_ascii=False))
                    return 2
                except AssuranceError as exc:
                    # Should not be reachable: the store labels every contract refusal.
                    # Kept because a refusal that escaped unlabelled must not traceback.
                    print(json.dumps({'status': 'ERROR', 'error': 'QUALITY_RECORD_REFUSED',
                                      'detail': str(exc)}, ensure_ascii=False))
                    return 2
        elif args.command == 'rights':
            from contextlib import closing
            from .assurance import rights_ledger
            from .rights_review import readback as rights_readback
            if not args.project_id:
                print(json.dumps({'status': 'ERROR', 'error': 'RIGHTS_PROJECT_REQUIRED',
                                  'detail': 'rights needs --project-id; the state database '
                                            'holds every project of this owner and a read must '
                                            'not guess one'}, ensure_ascii=False))
                return 2
            if service.get_project(args.project_id) is None:
                # Checked before anything opens the database: a read for an unknown project
                # id must not create runtime state, and it must not read as an empty honest
                # "nothing filed yet" for a project that does not exist.
                print(json.dumps({'status': 'ERROR', 'error': 'RIGHTS_PROJECT_UNKNOWN',
                                  'detail': f'project {args.project_id} is not recorded in '
                                            'this owner root', 'create_with': 'design-lab '
                                            '--project <dir> projects create --name <name>'},
                                 ensure_ascii=False))
                return 2
            if args.record:
                missing_inputs = [name for name, value in (
                    ('--scope', args.scope), ('--decision', args.decision),
                    ('--decided-by', args.decided_by), ('--decided-at', args.decided_at),
                    ('--actor-kind', args.actor_kind))
                    if not (isinstance(value, str) and value.strip())]
                if missing_inputs:
                    # No default actor, no default timestamp, no default decision: a rights
                    # decision this verb cannot attribute to a named human is not one the
                    # product may file on anyone's behalf.
                    print(json.dumps({'status': 'ERROR',
                                      'error': 'RIGHTS_RECORD_INPUTS_REQUIRED',
                                      'detail': 'recording needs ' + ', '.join(missing_inputs)
                                                + '; omit --record to read the decisions '
                                                  'already filed'}, ensure_ascii=False))
                    return 2
                # The document is assembled from the flags and validated against the loaded
                # contract; this verb owns no copy of the contract's field list. An optional
                # field the operator did not state stays absent rather than being filled in.
                document = {'schemaVersion': rights_ledger.CONTRACT_VERSION,
                            'decision_id': args.decision_id or rights_ledger.new_decision_id(),
                            'use_scope': args.scope, 'decision': args.decision,
                            'decided_by': args.decided_by, 'decided_at': args.decided_at}
                for _flag, name in (('--territory', 'territory'),
                                    ('--license-ref', 'license_ref'), ('--note', 'note')):
                    value = getattr(args, name)
                    if isinstance(value, str) and value.strip():
                        document[name] = value
            with closing(rights_ledger.connect(
                    service.paths.database_path(service.database),
                    project_root=service.paths.project_root)) as rights_conn:
                try:
                    if args.record:
                        stored = rights_ledger.record(rights_conn, project_id=args.project_id,
                                                      document=document,
                                                      actor_kind=args.actor_kind,
                                                      supersedes=args.supersedes)
                        view = rights_readback(rights_conn, args.project_id)
                        # The receipt repeats the limits rather than summarising them away:
                        # the person filing a licence approval is the person most likely to
                        # over-read a CLEARED.
                        result = {'status': 'RIGHTS_RECORDED', 'decision': stored,
                                  'rights_clearance': view['rights_clearance'],
                                  'approved_scope_count': view['approved_scope_count'],
                                  'filed_scope_count': view['filed_scope_count'],
                                  'decision_count': view['decision_count'],
                                  'does_not_prove': view['does_not_prove']}
                    else:
                        result = {'status': 'RIGHTS_READBACK',
                                  **rights_readback(rights_conn, args.project_id)}
                except rights_ledger.RightsLedgerError as exc:
                    # Every refusal carries the code that names the rule, so an operator can
                    # tell an unknown project from a bad decision word from an agent trying to
                    # sign a human gate.
                    print(json.dumps({'status': 'ERROR', 'error': exc.code, 'detail': str(exc),
                                      'project_id': args.project_id}, ensure_ascii=False))
                    return 2
        elif args.command == 'research':
            from contextlib import closing
            from .assurance import research_store
            from .research_review import readback as research_readback
            if not args.project_id:
                print(json.dumps({'status': 'ERROR', 'error': 'RESEARCH_PROJECT_REQUIRED',
                                  'detail': 'research needs --project-id; the state database '
                                            'holds every project of this owner and a read must '
                                            'not guess one'}, ensure_ascii=False))
                return 2
            if service.get_project(args.project_id) is None:
                # Checked before anything opens the database: a read for an unknown project id
                # must not create runtime state, and it must not read as an empty honest
                # "nothing filed yet" for a project that does not exist.
                print(json.dumps({'status': 'ERROR', 'error': 'RESEARCH_PROJECT_UNKNOWN',
                                  'detail': f'project {args.project_id} is not recorded in '
                                            'this owner root', 'create_with': 'design-lab '
                                            '--project <dir> projects create --name <name>'},
                                 ensure_ascii=False))
                return 2
            if args.record:
                missing_inputs = []
                if not (isinstance(args.claim, str) and args.claim.strip()):
                    missing_inputs.append('--claim')
                if not args.source_refs:
                    missing_inputs.append('--source')
                if missing_inputs:
                    # No default claim, no default source, no default author: a finding this
                    # verb cannot attribute or ground is a guess, and the product does not file
                    # guesses on anyone's behalf.
                    print(json.dumps({'status': 'ERROR',
                                      'error': 'RESEARCH_RECORD_INPUTS_REQUIRED',
                                      'detail': 'recording needs ' + ', '.join(missing_inputs)
                                                + '; a finding with no source is a guess, and '
                                                  'omitting --record reads the findings already '
                                                  'filed'}, ensure_ascii=False))
                    return 2
                # Assembled from the flags and validated against the loaded contract; this verb
                # owns no copy of the contract's field list. Note there is no schemaVersion
                # here: the research-finding contract closes its properties without declaring
                # one, so a finding that carried the field the OTHER contracts use would be
                # refused for it. An optional field the operator did not state stays absent.
                document = {'finding_id': args.finding_id or research_store.new_finding_id(),
                            'claim': args.claim, 'sourceRefs': list(args.source_refs)}
                if isinstance(args.confidence, str) and args.confidence.strip():
                    document['confidence'] = args.confidence.strip()
                if args.not_design_rule:
                    document['notDesignRule'] = True
            with closing(research_store.connect(
                    service.paths.database_path(service.database),
                    project_root=service.paths.project_root)) as research_conn:
                try:
                    if args.record:
                        stored = research_store.record(research_conn,
                                                       project_id=args.project_id,
                                                       document=document,
                                                       recorded_by=args.recorded_by,
                                                       actor_kind=args.actor_kind,
                                                       supersedes=args.supersedes)
                        view = research_readback(research_conn, args.project_id)
                        # The receipt repeats the limits rather than summarising them away:
                        # the person who just filed a finding is the person most likely to read
                        # a populated panel as a finished piece of research.
                        result = {'status': 'RESEARCH_RECORDED', 'finding': stored,
                                  'finding_count': view['finding_count'],
                                  'current_finding_count': view['current_finding_count'],
                                  'sourced_finding_count': view['sourced_finding_count'],
                                  'research_verdict': view['research_verdict'],
                                  'proves_design_quality': view['proves_design_quality'],
                                  'is_knowledge_export': view['is_knowledge_export'],
                                  'does_not_prove': view['does_not_prove']}
                    else:
                        result = {'status': 'RESEARCH_READBACK',
                                  **research_readback(research_conn, args.project_id)}
                except research_store.ResearchStoreError as exc:
                    # Every refusal carries the code that names the rule, so an operator can
                    # tell an unknown project from an unsourced claim from a machine claiming a
                    # human authorship -- and `does_not_prove` is on the read-back either way.
                    print(json.dumps({'status': 'ERROR', 'error': exc.code, 'detail': str(exc),
                                      'project_id': args.project_id,
                                      'does_not_prove': list(research_store.DOES_NOT_PROVE)},
                                     ensure_ascii=False))
                    return 2
        elif args.command == 'native-recovery':
            from .native_tasks import NativeTaskError
            from .runtime.job_store import AttemptError
            if not args.attempt:
                # Same shape as the start-up announcement, so the operator reads one
                # vocabulary in both places.
                result = {'status': 'RECOVERY_READBACK',
                          'recovery': _recovery_summary(service.recovery_readback())}
            else:
                # No default actor and no default receipt: a decision the operator
                # did not sign for is not one the product may take on their behalf.
                if not (args.actor and args.receipt):
                    print(json.dumps({'status': 'ERROR',
                                      'error': 'RECOVERY_DECISION_AUTHORIZATION_REQUIRED',
                                      'detail': 'deciding needs --actor and --receipt; '
                                                'listing without --attempt takes no action'},
                                     ensure_ascii=False))
                    return 2
                try:
                    decided = service.decide_native_recovery(args.attempt, authorization=dict(
                        actor=args.actor, scope='project-native-test', receipt=args.receipt))
                except (NativeTaskError, AttemptError) as exc:
                    reason = (exc.attempt.get('reason')
                              if isinstance(getattr(exc, 'attempt', None), dict) else None)
                    print(json.dumps({'status': 'ERROR', 'error': str(exc), 'reason': reason,
                                      'state': (exc.attempt.get('state')
                                                if reason else None)}, ensure_ascii=False))
                    return 2
                attempt = decided['result']['attempt']
                result = {'status': 'RECOVERY_DECIDED', 'attempt_id': args.attempt,
                          'action': decided['decision']['action'],
                          'state': attempt['state'], 'note': attempt['note'],
                          'artifacts_accepted': attempt['state'] == 'RECEIPTED'}
        elif args.command == 'native-worker':
            from .native_tasks import NativeTasks, NativeTaskError
            try:
                task = NativeTasks(service).execute_queued(args.attempt)
            except NativeTaskError as exc:
                # Never serialize stored jobs, authorization receipts or paths.
                print(json.dumps({'status':'ERROR','error':str(exc)}))
                return 2
            result = {'attempt_id':task['attempt']['attempt_id'],'state':task['attempt']['state']}
        elif args.command == 'delivery-receipt':
            from .image_assets import ImageAssetError
            from .interop import InteropError, delivery_receipt
            from .native_delivery import NativeDelivery
            try:
                readback = NativeDelivery(service).readback(args.project_id, args.bundle,
                                                            args.version)
                document = readback['receipt']
                # loads() already verified the document; this report is what the
                # operator reads: the schema it was validated against, every claim
                # the receipt does not make, and -- since the envelope landed -- whether
                # the restore point the receipt names still exists in this ledger.
                result = {'status': 'DELIVERY_RECEIPT',
                          'verification': delivery_receipt.verify_receipt(document),
                          'rollback_state': readback['rollback_state'],
                          'rollback_proofs': readback['rollback_proofs'],
                          'does_not_prove': readback['does_not_prove'],
                          'receipt': document}
            except ImageAssetError as exc:
                print(json.dumps({'status': 'ERROR', 'error': exc.code,
                                  'http_status': exc.status}, ensure_ascii=False))
                return 2
            except InteropError as exc:
                print(json.dumps({'status': 'ERROR', 'error': 'DELIVERY_RECEIPT_UNVERIFIED',
                                  'detail': str(exc)}, ensure_ascii=False))
                return 2
        elif args.command == 'analyze':
            from .asset_analysis import AssetAnalysis, AssetAnalysisError
            from .image_assets import ImageAssetError
            try:
                with open(args.observations, encoding='utf-8') as handle:
                    observations = json.load(handle)
            except (OSError, ValueError) as exc:
                print(json.dumps({'status': 'ERROR', 'error': 'UNREADABLE_OBSERVATIONS',
                                  'detail': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False))
                return 2
            if not isinstance(observations, dict) or set(observations) != {'module', 'detections'}:
                print(json.dumps({'status': 'ERROR', 'error': 'INVALID_OBSERVATIONS_DOCUMENT',
                                  'detail': 'the file must be one object holding exactly module and '
                                            'detections; nothing is inferred on your behalf'},
                                 ensure_ascii=False))
                return 2
            try:
                result = AssetAnalysis(service).derive(
                    args.project_id, args.asset, module=observations['module'],
                    detections=observations['detections'])
            except (AssetAnalysisError, ImageAssetError) as exc:
                print(json.dumps({'status': 'ERROR', 'error': getattr(exc, 'code', None)
                                            or type(exc).__name__, 'detail': str(exc)},
                                 ensure_ascii=False))
                return 2
        elif args.command == 'prompt':
            from .prompt_intelligence import PromptIntelligence, PromptIntelligenceError
            intelligence = PromptIntelligence(service)
            if args.action == 'generate':
                try:
                    document = intelligence.compose(args.project_id, brief_id=args.brief,
                                                   direction_id=args.direction, target=args.target)
                except PromptIntelligenceError as exc:
                    print(json.dumps({'status': 'ERROR', 'error': exc.code, 'detail': exc.detail},
                                     ensure_ascii=False))
                    return 2
            else:
                try:
                    with open(args.observations, encoding='utf-8') as handle:
                        observations = json.load(handle)
                except (OSError, ValueError) as exc:
                    print(json.dumps({'status': 'ERROR', 'error': 'UNREADABLE_OBSERVATIONS',
                                      'detail': f'{type(exc).__name__}: {exc}'}, ensure_ascii=False))
                    return 2
                if not isinstance(observations, dict) or set(observations) != {'module', 'detections'}:
                    print(json.dumps({'status': 'ERROR', 'error': 'INVALID_OBSERVATIONS_DOCUMENT',
                                      'detail': 'the file must be one object holding exactly module and '
                                                'detections; nothing is inferred on your behalf'},
                                     ensure_ascii=False))
                    return 2
                try:
                    document = intelligence.reverse(args.project_id, args.asset,
                                                    module=observations['module'],
                                                    detections=observations['detections'])
                except PromptIntelligenceError as exc:
                    print(json.dumps({'status': 'ERROR', 'error': exc.code, 'detail': exc.detail},
                                     ensure_ascii=False))
                    return 2
            result = PromptIntelligence.readback(document)
        elif args.command == 'export-candidate':
            from .knowledge_review import KnowledgeReview, KnowledgeReviewError
            try:
                result = KnowledgeReview(service).export_document(args.project_id, args.candidate)
            except KnowledgeReviewError as exc:
                print(json.dumps({'status': 'ERROR', 'error': exc.code, 'detail': exc.detail},
                                 ensure_ascii=False))
                return 2
        elif args.command == 'models':
            from .model_catalog import ModelCatalogError, catalog as model_catalog
            from .model_selection import ModelSelection, ModelSelectionError
            try:
                if args.action == 'list':
                    result = model_catalog()
                elif args.action == 'show':
                    result = ModelSelection(service).readback(args.project_id)
                else:
                    result = ModelSelection(service).record(
                        args.project_id, model_id=args.model, declared_unused=args.unused,
                        actor=args.actor, actor_kind=args.actor_kind)
            except (ModelCatalogError, ModelSelectionError) as exc:
                print(json.dumps({'status': 'ERROR', 'error': getattr(exc, 'code', None)
                                            or type(exc).__name__,
                                  'detail': getattr(exc, 'detail', None) or str(exc)},
                                 ensure_ascii=False))
                return 2
        elif args.command == 'paths':
            result = service.paths.describe()
        elif args.action == 'list':
            # Same roll-up the HTTP surface answers, so the two cannot disagree about what a
            # project holds or who still has to sign for it.
            from .project_index import ProjectIndex
            result = ProjectIndex(service).list()
        else:
            result = {'project': service.create_project(args.name)}
    except (ValueError, OSError, sqlite3.Error, AssetError, PathPolicyError,
            BackupError) as exc:
        print(json.dumps({'status': 'ERROR', 'error': type(exc).__name__, 'detail': str(exc)}, ensure_ascii=False))
        return 2
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0
