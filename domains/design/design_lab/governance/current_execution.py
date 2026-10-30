# SPDX-License-Identifier: MIT
"""Current dispatch partition in the existing ledger; R5 receipts remain frozen.

Owner adoption 2026-10-09. Definitions are immutable input; task states and new
evidence live only under currentExecution. Implementation readiness and acceptance
readiness are deliberately separate, so reviewable desktop UI can precede host,
human or cross-project acceptance. Historical receipts never qualify new tasks.
"""
from __future__ import annotations

from collections import Counter
import hashlib
import json

STATES = ['NOT_STARTED', 'IN_PROGRESS', 'PARTIAL', 'BLOCKED', 'DONE', 'FROZEN_DEFERRED']


def schema():
    string = {'type': 'string', 'minLength': 1}
    strings = {'type': 'array', 'items': string, 'uniqueItems': True}
    source = {'type': 'object', 'additionalProperties': False,
              'required': ['path', 'sha256'], 'properties': {
                  'path': string, 'sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'}}}
    return {'type': 'object', 'additionalProperties': False,
            'x-contract-delegated': 'design_lab.governance.current_execution.validate',
            'required': ['taskpack', 'plan_path', 'source', 'decision_path', 'legacy_snapshot',
                         'legacy_disposition', 'mobile', 'tasks', 'evidence', 'note'],
            'properties': {
                'taskpack': string, 'plan_path': string, 'source': source,
                'decision_path': string, 'legacy_snapshot': source,
                'legacy_disposition': {'const': 'FROZEN_EVIDENCE_ONLY_NOT_DISPATCH'},
                'mobile': {'const': 'FROZEN_DEFERRED'}, 'note': string,
                'tasks': {'type': 'array', 'minItems': 1, 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'required': ['id', 'state', 'evidence'], 'properties': {
                        'id': string, 'state': {'enum': STATES}, 'evidence': strings}}},
                'evidence': {'type': 'array', 'items': {
                    'type': 'object', 'additionalProperties': False,
                    'required': ['id', 'task_id', 'axis', 'outcome', 'subject_sha',
                                 'artifact_path', 'artifact_sha256', 'command', 'exit_code', 'observed_at'],
                    'properties': {'id': string, 'task_id': string, 'axis': string,
                        'outcome': {'enum': ['PASS', 'FAIL', 'PARTIAL', 'BLOCKED', 'NOT_EXECUTED']},
                        'subject_sha': {'type': 'string', 'pattern': '^[0-9a-f]{40}$'},
                        'artifact_path': string,
                        'artifact_sha256': {'type': 'string', 'pattern': '^[0-9a-f]{64}$'},
                        'command': string, 'exit_code': {'type': 'integer'},
                        'observed_at': {'type': 'string', 'format': 'date-time'}}}}}}


def _bound(reader, source):
    raw = reader.read(source['path'])
    if hashlib.sha256(raw).hexdigest() != source['sha256']:
        raise ValueError('current dispatch source/snapshot hash differs: ' + source['path'])
    return json.loads(raw)


def validate(reader, ledger):
    from jsonschema import Draft202012Validator, FormatChecker
    execution = ledger.get('currentExecution')
    if execution is None:
        return None
    errors = list(Draft202012Validator(schema(), format_checker=FormatChecker()).iter_errors(execution))
    if errors:
        raise ValueError('invalid currentExecution: ' + errors[0].message)
    source = _bound(reader, execution['source'])
    frozen = _bound(reader, execution['legacy_snapshot'])
    for field in ('tasks', 'evidence', 'source', 'predecessor', 'taskpack', 'plan_path', 'baseline_sha'):
        if ledger[field] != frozen[field]:
            raise ValueError('frozen predecessor partition changed: ' + field)
    reader.read(execution['plan_path'])
    reader.read(execution['decision_path'])
    if source['id'] != execution['taskpack'] or source['mobile'] != execution['mobile']:
        raise ValueError('current dispatch identity/scope differs from frozen definitions')
    definitions = {t['id']: t for t in source['tasks']}
    tasks = {t['id']: t for t in execution['tasks']}
    if len(definitions) != len(source['tasks']) or len(tasks) != len(execution['tasks']) or set(tasks) != set(definitions):
        raise ValueError('current task inventory missing/duplicated')
    evidence = {e['id']: e for e in execution['evidence']}
    if len(evidence) != len(execution['evidence']):
        raise ValueError('duplicate current evidence IDs')
    for graph in ('implementation_depends_on', 'acceptance_depends_on'):
        visiting, visited = set(), set()
        def visit(identity):
            if identity not in tasks:
                raise ValueError('missing current dependency: ' + identity)
            if identity in visiting:
                raise ValueError('cyclic current ' + graph)
            if identity in visited:
                return
            visiting.add(identity)
            for dep in definitions[identity][graph]:
                visit(dep)
            visiting.remove(identity)
            visited.add(identity)
        for identity in tasks:
            visit(identity)
    for record in evidence.values():
        if record['task_id'] not in tasks:
            raise ValueError('evidence references missing current task')
        raw = reader.read(record['artifact_path'])
        if hashlib.sha256(raw).hexdigest() != record['artifact_sha256']:
            raise ValueError('current evidence artifact hash differs')
        if record['outcome'] == 'PASS' and record['exit_code'] != 0:
            raise ValueError('nonzero exit cannot qualify current PASS')
    for identity, task in tasks.items():
        if any(eid not in evidence or evidence[eid]['task_id'] != identity for eid in task['evidence']):
            raise ValueError('unknown or wrong-task current evidence')
        if task['state'] == 'DONE':
            required = set(definitions[identity]['evidence_requirements'])
            passing = {evidence[eid]['axis'] for eid in task['evidence'] if evidence[eid]['outcome'] == 'PASS'}
            if not required <= passing:
                raise ValueError('current DONE lacks required independent evidence axes')
            if any(tasks[dep]['state'] != 'DONE' for dep in definitions[identity]['acceptance_depends_on']):
                raise ValueError('current DONE has unmet acceptance dependencies')
    return definitions


def projection(reader, ledger):
    definitions = validate(reader, ledger)
    execution = ledger['currentExecution']
    states = {t['id']: t['state'] for t in execution['tasks']}
    tasks = []
    for task in execution['tasks']:
        definition = definitions[task['id']]
        tasks.append({**task, 'title': definition['title'], 'kind': definition['kind'],
            'batch': definition['batch'], 'priority': definition['priority'],
            'implementation_unmet': [d for d in definition['implementation_depends_on'] if states[d] != 'DONE'],
            'acceptance_unmet': [d for d in definition['acceptance_depends_on'] if states[d] != 'DONE'],
            'evidence_level': 'NO_EVIDENCE' if not task['evidence'] else 'SEE_BOUND_RECEIPTS'})
    return {'taskpack': execution['taskpack'], 'plan_path': execution['plan_path'],
            'ledger_partition': 'currentExecution', 'mobile': execution['mobile'],
            'tasks': tasks, 'counts': dict(Counter(t['state'] for t in tasks)),
            'meaning': 'Parent/subtask inventory is not a capability count or completion percentage. '
                       'Definition adoption does not implement product tasks; R5 evidence is historical.'}


def update_reports(reader, ledger, reports, common):
    """Keep the existing generated report paths, replacing dispatch with current scope."""
    if 'currentExecution' not in ledger:
        return reports
    p = projection(reader, ledger)
    common = {**common, 'taskpackId': p['taskpack'], 'taskpackHash': hashlib.sha256(reader.read(p['plan_path'])).hexdigest(),
              'authorityTaskpackId': p['taskpack'], 'authorityTaskpackHash': hashlib.sha256(reader.read(p['plan_path'])).hexdigest()}
    for name, raw in list(reports.items()):
        if name.endswith('.json') and name != 'TASK_PROGRESS.json':
            reports[name] = (json.dumps({**json.loads(raw), **common}, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
    old = json.loads(reports['TASK_PROGRESS.json'])
    def dump(data):
        return (json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + '\n').encode()
    reports['TASK_PROGRESS.json'] = dump({**common, **p,
        'predecessor': {'state': 'FROZEN_EVIDENCE_ONLY_NOT_DISPATCH',
                        'taskpack': old['taskpack'], 'counts': old['counts'],
                        'snapshot': ledger['currentExecution']['legacy_snapshot']['path']}})
    status = json.loads(reports['PROJECT_STATUS.json'])
    status.update(taskpack=p['taskpack'], plan=p['plan_path'], ledgerPartition='currentExecution',
                  taskCounts=p['counts'], mobile=p['mobile'],
                  predecessorMeaning='R5 receipts and axes are frozen history, not current dispatch')
    reports['PROJECT_STATUS.json'] = dump(status)
    kinds = Counter(t['kind'] for t in p['tasks'])
    frozen = sum(1 for t in p['tasks'] if t['state'] == 'FROZEN_DEFERRED')
    boundary = ('桌面端是唯一交付面；手机端已由 owner 2026-10-19 定为排除项（不是待排期冻结项），'
                '账本 currentExecution.mobile 仍是 schema const FROZEN_DEFERRED，改词需 owner 授权，故未改。'
                + f'{kinds["PARENT_TASK"]} 父任务＋{kinds["UI_SUBTASK"]} UI 子任务，'
                + f'{frozen} 项保持 FROZEN_DEFERRED，{len(p["tasks"]) - frozen} 项是 owner 2026-10-23 '
                + '起进入当前派工的桌面 UI 与知识库纵切；不相加算完成率。')
    lines = ['# PROJECT_STATUS（当前派工投影）', '', f'任务包：{p["taskpack"]}；状态唯一编辑源：{ledger["currentExecution"]["plan_path"]}所指原账本currentExecution。',
             '', f'生成时HEAD：{common["subjectSha"]}；subjectType={common["subjectType"]}；生成时间不是测试时间。',
             '', boundary,
             '旧R5状态和证据冻结，不用于关闭新任务；本投影不实施产品，也不证明任何一项已验收。', '',
             '|任务|类型|批次|状态|证据|', '|---|---|---|---|---|']
    lines += ['|' + '|'.join([t['id'], t['kind'], t['batch'], t['state'], t['evidence_level']]) + '|' for t in p['tasks']]
    lines += ['', '发布：NOT_RELEASED；真实宿主、真人评审、三方学习和部署：NOT_EXECUTED by this adoption.']
    reports['PROJECT_STATUS.md'] = ('\n'.join(lines) + '\n').encode()
    release = json.loads(reports['RELEASE_READINESS.json'])
    release['blockers'] = ['DL-FINAL-T15 acceptance', 'DL-FINAL-T19 real joint learning',
                           'DL-UI-U12 complete desktop acceptance', 'rights/human/release permission', 'exact-SHA delivery']
    reports['RELEASE_READINESS.json'] = dump(release)
    return reports
